#!/usr/bin/env python3
"""
Ingest STAR Drums dataset into BeatSight training format.

STAR Drums contains 2.5M annotated drum events across 18 classes, with isolated
drum stems and corresponding audio. This script extracts individual drum hits
and converts them to the BeatSight training format.

STAR Drums classes -> BeatSight mapping:
    BD  -> kick
    SD  -> snare
    CHH -> hihat_closed
    OHH -> hihat_open
    PHH -> hihat_pedal
    SS  -> cross_stick (RARE - 77K samples!)
    CRC -> crash
    RD  -> ride_bow
    RB  -> ride_bell
    HT  -> tom
    MT  -> tom
    LT  -> tom
    CHC -> china (RARE - 254 samples!)
    SPC -> splash (RARE - 765 samples!)
    CLP -> clap (excluded - not in our taxonomy)
    CL  -> ? (need to verify)
    CB  -> cowbell (excluded - not in our taxonomy)
    TB  -> ? (need to verify)

Usage:
    # Preview what will be extracted
    python ingest_star_drums.py \
        --star-drums-dir F:/datasets/star_drums/STAR_publication \
        --output-dir F:/datasets/star_drums_extracted \
        --preview

    # Extract all rare classes (china, splash, cross_stick)
    python ingest_star_drums.py \
        --star-drums-dir F:/datasets/star_drums/STAR_publication \
        --output-dir F:/datasets/star_drums_extracted \
        --classes china splash cross_stick

    # Extract ALL classes
    python ingest_star_drums.py \
        --star-drums-dir F:/datasets/star_drums/STAR_publication \
        --output-dir F:/datasets/star_drums_extracted \
        --all-classes
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
import concurrent.futures
from dataclasses import dataclass

import numpy as np

# Try to import audio processing libraries
try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
    print("Warning: soundfile not installed. Run: pip install soundfile")

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print("Warning: librosa not installed. Run: pip install librosa")


# STAR Drums class mapping to BeatSight classes
STAR_TO_BEATSIGHT = {
    'BD': 'kick',
    'SD': 'snare',
    'CHH': 'hihat_closed',
    'OHH': 'hihat_open',
    'PHH': 'hihat_pedal',
    'SS': 'cross_stick',     # Side Stick -> cross_stick
    'CRC': 'crash',
    'RD': 'ride_bow',
    'RB': 'ride_bell',
    'HT': 'tom',             # High Tom
    'MT': 'tom',             # Mid Tom
    'LT': 'tom',             # Low Tom
    'CHC': 'china',          # China Cymbal - RARE!
    'SPC': 'splash',         # Splash Cymbal - RARE!
    # Excluded classes (not in BeatSight taxonomy):
    # 'CLP': 'clap',         # Clap - not in our 12 classes
    # 'CB': 'cowbell',       # Cowbell - not in our 12 classes
    # 'CL': ???,             # Unknown
    # 'TB': ???,             # Unknown (possibly tambourine?)
}

# Classes we want to extract (focus on rare classes first)
RARE_CLASSES = {'china', 'splash', 'cross_stick'}
ALL_BEATSIGHT_CLASSES = {'kick', 'snare', 'hihat_closed', 'hihat_open', 'hihat_pedal',
                          'cross_stick', 'crash', 'ride_bow', 'ride_bell', 'tom',
                          'china', 'splash'}


@dataclass
class DrumEvent:
    """A single drum hit event."""
    time: float
    star_class: str
    beatsight_class: str
    velocity: int
    source_file: str
    audio_file: str


def parse_annotation_file(anno_path: Path) -> List[Tuple[float, str, int]]:
    """Parse a STAR Drums annotation file.
    
    Format: timestamp<tab>class<tab>velocity
    Example: 19.215833333333336      BD      103
    """
    events = []
    with open(anno_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3:
                try:
                    time = float(parts[0])
                    star_class = parts[1]
                    velocity = int(parts[2])
                    events.append((time, star_class, velocity))
                except (ValueError, IndexError):
                    continue
    return events


def find_audio_file(anno_path: Path, dataset_dir: Path) -> Optional[Path]:
    """Find the corresponding audio file for an annotation.
    
    STAR Drums structure:
    - annotation/1001890_mix_in_da_house_kit_full.txt
    - audio/re_synthesized_drum/1001890_re_synth_drum_in_da_house_kit_full.flac
    - audio/original_drum/1001890.flac (original drum stem)
    - audio/mix/1001890_mix_in_da_house_kit_full.flac
    
    Priority: re_synthesized_drum (cleanest) > original_drum > mix
    """
    base_name = anno_path.stem  # e.g., "1001890_mix_in_da_house_kit_full"
    audio_dir = dataset_dir / 'audio'
    
    # Extract track ID (first number before _mix_)
    parts = base_name.split('_mix_')
    if len(parts) >= 2:
        track_id = parts[0]  # e.g., "1001890"
        kit_name = parts[1]  # e.g., "in_da_house_kit_full"
        
        # Option 1: Re-synthesized drum (cleanest isolated drums)
        re_synth_path = audio_dir / 're_synthesized_drum' / f"{track_id}_re_synth_drum_{kit_name}.flac"
        if re_synth_path.exists():
            return re_synth_path
        
        # Also try .wav extension
        re_synth_wav = audio_dir / 're_synthesized_drum' / f"{track_id}_re_synth_drum_{kit_name}.wav"
        if re_synth_wav.exists():
            return re_synth_wav
        
        # Option 2: Original drum stem
        orig_drum_path = audio_dir / 'original_drum' / f"{track_id}.flac"
        if orig_drum_path.exists():
            return orig_drum_path
        
        orig_drum_wav = audio_dir / 'original_drum' / f"{track_id}.wav"
        if orig_drum_wav.exists():
            return orig_drum_wav
    
    # Option 3: Mix file (has other instruments, less ideal)
    mix_path = audio_dir / 'mix' / f"{base_name}.flac"
    if mix_path.exists():
        return mix_path
    
    mix_wav = audio_dir / 'mix' / f"{base_name}.wav"
    if mix_wav.exists():
        return mix_wav
    
    return None


def extract_drum_hit(audio_path: Path, event_time: float, 
                     sample_rate: int = 44100,
                     window_before: float = 0.01,
                     window_after: float = 0.28) -> Optional[np.ndarray]:
    """Extract a single drum hit from audio.
    
    Args:
        audio_path: Path to audio file
        event_time: Time of drum hit in seconds
        sample_rate: Target sample rate
        window_before: Seconds before hit to include (attack)
        window_after: Seconds after hit to include (sustain/decay)
        
    Returns:
        Audio array or None if extraction failed
    """
    if not HAS_SOUNDFILE and not HAS_LIBROSA:
        return None
    
    try:
        # Calculate sample positions
        start_time = max(0, event_time - window_before)
        duration = window_before + window_after
        
        if HAS_LIBROSA:
            audio, sr = librosa.load(audio_path, sr=sample_rate, 
                                     offset=start_time, duration=duration,
                                     mono=True)
        else:
            # Use soundfile
            info = sf.info(audio_path)
            start_sample = int(start_time * info.samplerate)
            num_samples = int(duration * info.samplerate)
            audio, sr = sf.read(audio_path, start=start_sample, 
                               stop=start_sample + num_samples)
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)  # Convert to mono
            if sr != sample_rate:
                # Resample if needed
                if HAS_LIBROSA:
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=sample_rate)
        
        return audio
        
    except Exception as e:
        print(f"Error extracting from {audio_path}: {e}")
        return None


def scan_star_drums(star_drums_dir: Path) -> Dict[str, List[DrumEvent]]:
    """Scan STAR Drums dataset and collect all events by class."""
    events_by_class = defaultdict(list)
    
    data_dir = star_drums_dir / 'data'
    
    for split in ['training', 'validation', 'test']:
        split_dir = data_dir / split
        if not split_dir.exists():
            continue
            
        for dataset_dir in split_dir.iterdir():
            if not dataset_dir.is_dir():
                continue
                
            anno_dir = dataset_dir / 'annotation'
            if not anno_dir.exists():
                continue
            
            for anno_file in anno_dir.glob('*.txt'):
                events = parse_annotation_file(anno_file)
                audio_file = find_audio_file(anno_file, dataset_dir)
                
                for time, star_class, velocity in events:
                    beatsight_class = STAR_TO_BEATSIGHT.get(star_class)
                    if beatsight_class:
                        event = DrumEvent(
                            time=time,
                            star_class=star_class,
                            beatsight_class=beatsight_class,
                            velocity=velocity,
                            source_file=str(anno_file),
                            audio_file=str(audio_file) if audio_file else None
                        )
                        events_by_class[beatsight_class].append(event)
    
    return events_by_class


def extract_and_save_samples(events: List[DrumEvent], 
                             output_dir: Path,
                             class_name: str,
                             max_samples: int = None,
                             sample_rate: int = 44100) -> int:
    """Extract audio samples for a class and save to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    extracted = 0
    seen_hashes = set()
    
    # Group events by audio file for efficiency
    events_by_audio = defaultdict(list)
    for event in events:
        if event.audio_file:
            events_by_audio[event.audio_file].append(event)
    
    for audio_file, file_events in events_by_audio.items():
        if max_samples and extracted >= max_samples:
            break
            
        audio_path = Path(audio_file)
        if not audio_path.exists():
            continue
        
        for event in file_events:
            if max_samples and extracted >= max_samples:
                break
            
            audio = extract_drum_hit(audio_path, event.time, sample_rate)
            if audio is None or len(audio) < sample_rate * 0.05:  # Min 50ms
                continue
            
            # Generate unique filename
            content_hash = hashlib.md5(audio.tobytes()[:1000]).hexdigest()[:8]
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            
            # Save audio
            filename = f"{class_name}_{content_hash}_v{event.velocity}.wav"
            output_path = output_dir / filename
            
            try:
                sf.write(output_path, audio, sample_rate)
                extracted += 1
                
                if extracted % 100 == 0:
                    print(f"  Extracted {extracted} {class_name} samples...")
                    
            except Exception as e:
                print(f"Error saving {output_path}: {e}")
    
    return extracted


def main():
    parser = argparse.ArgumentParser(description='Ingest STAR Drums dataset')
    parser.add_argument('--star-drums-dir', type=str, required=True,
                        help='Path to STAR_publication directory')
    parser.add_argument('--output-dir', type=str, required=True,
                        help='Output directory for extracted samples')
    parser.add_argument('--classes', nargs='+', default=['china', 'splash', 'cross_stick'],
                        help='Classes to extract (default: rare classes)')
    parser.add_argument('--all-classes', action='store_true',
                        help='Extract all mappable classes')
    parser.add_argument('--max-per-class', type=int, default=None,
                        help='Maximum samples per class')
    parser.add_argument('--preview', action='store_true',
                        help='Preview only, do not extract')
    parser.add_argument('--sample-rate', type=int, default=44100,
                        help='Output sample rate')
    args = parser.parse_args()
    
    star_drums_dir = Path(args.star_drums_dir)
    output_dir = Path(args.output_dir)
    
    if not star_drums_dir.exists():
        print(f"Error: STAR Drums directory not found: {star_drums_dir}")
        sys.exit(1)
    
    print("=" * 60)
    print(" STAR Drums Dataset Ingestion")
    print("=" * 60)
    print(f"Source: {star_drums_dir}")
    print(f"Output: {output_dir}")
    print()
    
    # Scan dataset
    print("Scanning STAR Drums annotations...")
    events_by_class = scan_star_drums(star_drums_dir)
    
    print(f"\nFound {sum(len(v) for v in events_by_class.values()):,} total events")
    print("\nClass distribution (BeatSight mapping):")
    print("-" * 40)
    
    for cls in sorted(events_by_class.keys(), key=lambda x: -len(events_by_class[x])):
        count = len(events_by_class[cls])
        has_audio = sum(1 for e in events_by_class[cls] if e.audio_file)
        rare_marker = " [RARE]" if cls in RARE_CLASSES else ""
        print(f"  {cls:15} {count:>8,} events ({has_audio:,} with audio){rare_marker}")
    
    if args.preview:
        print("\n[Preview mode - no extraction performed]")
        return
    
    # Determine which classes to extract
    if args.all_classes:
        target_classes = list(events_by_class.keys())
    else:
        target_classes = args.classes
    
    print(f"\nExtracting classes: {', '.join(target_classes)}")
    print("-" * 40)
    
    if not HAS_SOUNDFILE:
        print("Error: soundfile required for extraction. Run: pip install soundfile")
        sys.exit(1)
    
    # Extract samples
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_extracted = 0
    extraction_stats = {}
    
    for cls in target_classes:
        if cls not in events_by_class:
            print(f"  {cls}: No events found")
            continue
        
        print(f"\nExtracting {cls}...")
        events = events_by_class[cls]
        
        class_output_dir = output_dir / cls
        extracted = extract_and_save_samples(
            events, 
            class_output_dir, 
            cls,
            max_samples=args.max_per_class,
            sample_rate=args.sample_rate
        )
        
        extraction_stats[cls] = extracted
        total_extracted += extracted
        print(f"  {cls}: Extracted {extracted:,} samples")
    
    # Save metadata
    metadata = {
        'source': 'STAR_Drums',
        'source_dir': str(star_drums_dir),
        'sample_rate': args.sample_rate,
        'extraction_stats': extraction_stats,
        'total_samples': total_extracted,
        'class_mapping': STAR_TO_BEATSIGHT
    }
    
    metadata_path = output_dir / 'metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "=" * 60)
    print(f" Extraction Complete")
    print("=" * 60)
    print(f"Total samples extracted: {total_extracted:,}")
    print(f"Output directory: {output_dir}")
    print(f"Metadata saved to: {metadata_path}")


if __name__ == '__main__':
    main()
