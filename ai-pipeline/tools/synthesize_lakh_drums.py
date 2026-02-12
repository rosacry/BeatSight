#!/usr/bin/env python3
"""
Synthesize drum hits from Lakh MIDI dataset.

This script:
1. Reads drum events from drum_events_rare_only.jsonl
2. Synthesizes each hit using FluidSynth with a GM soundfont
3. Computes mel spectrograms and saves to cache

Requires:
- fluidsynth (pip install pyfluidsynth)
- A GM soundfont (downloads automatically if not present)

Usage:
    python tools/synthesize_lakh_drums.py --target-class china --limit 50000
    python tools/synthesize_lakh_drums.py --target-class splash --limit 50000
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import tempfile
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torchaudio

# Check for fluidsynth
try:
    import fluidsynth
    FLUIDSYNTH_AVAILABLE = True
except ImportError:
    FLUIDSYNTH_AVAILABLE = False
    print("WARNING: pyfluidsynth not installed. Install with: pip install pyfluidsynth")

# MIDI note numbers for rare cymbals (GM drum channel = 9)
GM_DRUM_NOTES = {
    'china': 52,    # Chinese Cymbal
    'splash': 55,   # Splash Cymbal
    'crash': 49,    # Crash Cymbal 1
    'ride_bow': 51, # Ride Cymbal 1
    'ride_bell': 53, # Ride Bell
}

# Class indices matching CANONICAL_COMPONENTS
CLASS_TO_IDX = {
    'china': 0,
    'crash': 1,
    'cross_stick': 2,
    'hihat_closed': 3,
    'hihat_open': 4,
    'hihat_pedal': 5,
    'kick': 6,
    'ride_bell': 7,
    'ride_bow': 8,
    'snare': 9,
    'splash': 10,
    'tom': 11,
}

# Paths
SOUNDFONT_DIR = Path("F:/datasets/soundfonts")
SOUNDFONT_NAME = "FluidR3_GM.sf2"
SOUNDFONT_URL = "https://github.com/urish/cinto/raw/master/media/FluidR3%20GM.sf2"

LAKH_EVENTS_FILE_RARE = Path("F:/datasets/lakh_midi/drum_events_rare_only.jsonl")
LAKH_EVENTS_FILE_CRASH = Path("F:/datasets/lakh_midi/drum_events_crash_ridebell.jsonl")
CACHE_DIR = Path("F:/feature_cache")

# Audio parameters
SAMPLE_RATE = 22050
HIT_DURATION = 0.5  # 500ms per hit
N_MELS = 128
HOP_LENGTH = 512
N_FFT = 2048
TARGET_FRAMES = 128  # Match expected cache shape


def download_soundfont(dest_path: Path) -> bool:
    """Download GM soundfont if not present."""
    if dest_path.exists() and dest_path.stat().st_size > 1_000_000:
        return True
    
    print(f"Downloading soundfont to {dest_path}...")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        urllib.request.urlretrieve(SOUNDFONT_URL, str(dest_path))
        print(f"Downloaded: {dest_path.stat().st_size / 1e6:.1f} MB")
        return True
    except Exception as e:
        print(f"Failed to download soundfont: {e}")
        return False


def init_fluidsynth(soundfont_path: Path) -> Optional[fluidsynth.Synth]:
    """Initialize FluidSynth with soundfont."""
    if not FLUIDSYNTH_AVAILABLE:
        return None
    
    fs = fluidsynth.Synth(samplerate=float(SAMPLE_RATE))
    sfid = fs.sfload(str(soundfont_path))
    fs.program_select(9, sfid, 0, 0)  # Channel 9 for drums (GM standard)
    return fs


def synthesize_hit(fs: fluidsynth.Synth, note: int, velocity: int, duration: float = HIT_DURATION) -> np.ndarray:
    """Synthesize a single drum hit."""
    # Calculate samples
    num_samples = int(duration * SAMPLE_RATE)
    
    # Note on
    fs.noteon(9, note, velocity)
    
    # Get samples
    samples = fs.get_samples(num_samples)
    
    # Note off
    fs.noteoff(9, note)
    
    # Convert to mono float32
    audio = np.array(samples, dtype=np.float32)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    elif len(audio) > num_samples:
        # get_samples returns stereo interleaved
        audio = audio[::2]  # Take left channel
    
    # Normalize
    max_val = np.abs(audio).max()
    if max_val > 0:
        audio = audio / max_val * 0.9
    
    return audio


def compute_mel_spectrogram(audio: np.ndarray) -> torch.Tensor:
    """Compute mel spectrogram matching training pipeline."""
    # Convert to tensor
    waveform = torch.from_numpy(audio).unsqueeze(0)  # (1, samples)
    
    # Mel spectrogram
    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=SAMPLE_RATE,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
        n_mels=N_MELS,
        power=2.0,
    )
    mel_spec = mel_transform(waveform)  # (1, n_mels, time)
    
    # Log scale
    mel_spec = torch.log(mel_spec + 1e-9)
    
    # Remove channel dim -> (n_mels, time)
    mel_spec = mel_spec.squeeze(0)
    
    # Pad/truncate to target frames
    if mel_spec.shape[1] < TARGET_FRAMES:
        pad = TARGET_FRAMES - mel_spec.shape[1]
        mel_spec = torch.nn.functional.pad(mel_spec, (0, pad))
    elif mel_spec.shape[1] > TARGET_FRAMES:
        mel_spec = mel_spec[:, :TARGET_FRAMES]
    
    return mel_spec  # (128, 128)


def load_lakh_events(target_class: str, events_file: Optional[Path] = None) -> List[Dict]:
    """Load Lakh drum events for target class."""
    # Select appropriate events file
    if events_file:
        file_path = events_file
    elif target_class in ['crash', 'ride_bell']:
        file_path = LAKH_EVENTS_FILE_CRASH
    else:
        file_path = LAKH_EVENTS_FILE_RARE
    
    events = []
    
    print(f"Loading Lakh events for class '{target_class}' from {file_path.name}...")
    with open(file_path, 'r') as f:
        for line in f:
            data = json.loads(line)
            if data.get('class') == target_class:
                events.append(data)
    
    print(f"Found {len(events):,} events for {target_class}")
    return events


def get_cache_shard_info(cache_dir: Path, split: str = "train") -> Tuple[int, int]:
    """Get next shard ID and current sample count from cache."""
    split_dir = cache_dir / split
    
    # Load manifest if exists
    manifest_path = split_dir / "cache_manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        return manifest.get("num_shards", 0), manifest.get("total_samples", 0)
    
    # Count existing shards
    shards = list(split_dir.glob("shard_*.bin"))
    return len(shards), 0


def generate_file_id(event: Dict, idx: int) -> str:
    """Generate unique file ID for a synthesized sample."""
    # Use hash of event data for reproducibility
    # Handle both field names: 'midi_file' (old format) and 'file' (new format)
    midi_file = event.get('midi_file') or event.get('file', 'unknown')
    event_str = f"{midi_file}_{event['time']}_{event['note']}_{event['velocity']}"
    hash_suffix = hashlib.md5(event_str.encode()).hexdigest()[:12]
    cls = event.get('class', 'unknown')
    return f"lakh_{cls}_{hash_suffix}"


def write_shard(
    cache_dir: Path,
    split: str,
    shard_id: int,
    tensors: List[torch.Tensor],
    file_ids: List[str],
) -> Dict[str, List]:
    """Write tensors to a shard file and return index entries."""
    split_dir = cache_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)
    
    shard_path = split_dir / f"shard_{shard_id:05d}.bin"
    
    index_entries = {}
    
    with open(shard_path, 'wb') as f:
        for local_idx, (tensor, file_id) in enumerate(zip(tensors, file_ids)):
            # Convert to float32 numpy and write
            arr = tensor.numpy().astype(np.float32)
            f.write(arr.tobytes())
            
            # Index entry: [shard_id, local_offset]
            index_entries[file_id] = [shard_id, local_idx]
    
    print(f"  Wrote {len(tensors)} samples to {shard_path.name}")
    return index_entries


def update_cache_index(cache_dir: Path, split: str, new_entries: Dict[str, List]):
    """Update cache index.json with new entries."""
    split_dir = cache_dir / split
    index_path = split_dir / "index.json"
    
    # Load existing
    if index_path.exists():
        print(f"Loading existing index from {index_path}...")
        with open(index_path) as f:
            index = json.load(f)
        print(f"  Existing entries: {len(index):,}")
    else:
        index = {}
    
    # Merge
    index.update(new_entries)
    
    # Save
    print(f"Saving updated index ({len(index):,} entries)...")
    with open(index_path, 'w') as f:
        json.dump(index, f)


def update_cache_manifest(cache_dir: Path, split: str, new_shards: List[Dict]):
    """Update cache_manifest.json with new shard info."""
    split_dir = cache_dir / split
    manifest_path = split_dir / "cache_manifest.json"
    
    # Load existing
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {
            "total_samples": 0,
            "tensor_shape": [N_MELS, TARGET_FRAMES],
            "dtype": "torch.float32",
            "bytes_per_sample": N_MELS * TARGET_FRAMES * 4,
            "num_shards": 0,
            "shards": [],
        }
    
    # Add new shards
    for shard_info in new_shards:
        manifest["shards"].append(shard_info)
        manifest["total_samples"] += shard_info["num_samples"]
        manifest["num_shards"] += 1
    
    # Save
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Synthesize Lakh drum hits")
    parser.add_argument("--target-class", required=True, 
                       choices=["china", "splash", "crash", "ride_bell"],
                       help="Target class to synthesize")
    parser.add_argument("--limit", type=int, default=50000,
                       help="Maximum samples to generate")
    parser.add_argument("--events-file", type=Path, default=None,
                       help="Custom events file path (optional)")
    parser.add_argument("--batch-size", type=int, default=10000,
                       help="Samples per shard")
    parser.add_argument("--velocity-range", type=int, nargs=2, default=[60, 127],
                       help="Velocity range for synthesis")
    parser.add_argument("--skip-existing", action="store_true",
                       help="Skip samples already in cache")
    args = parser.parse_args()
    
    print("=" * 70)
    print(f"LAKH DRUM SYNTHESIS - {args.target_class.upper()}")
    print("=" * 70)
    
    # Check soundfont
    soundfont_path = SOUNDFONT_DIR / SOUNDFONT_NAME
    if not download_soundfont(soundfont_path):
        print("ERROR: Cannot proceed without soundfont")
        return 1
    
    # Initialize FluidSynth
    if not FLUIDSYNTH_AVAILABLE:
        print("ERROR: pyfluidsynth not available")
        print("Install with: pip install pyfluidsynth")
        print("Also need FluidSynth library: https://github.com/FluidSynth/fluidsynth/releases")
        return 1
    
    print(f"\nInitializing FluidSynth with {soundfont_path}...")
    fs = init_fluidsynth(soundfont_path)
    if fs is None:
        print("ERROR: Failed to initialize FluidSynth")
        return 1
    
    # Load events
    events = load_lakh_events(args.target_class, args.events_file)
    
    if not events:
        print(f"ERROR: No events found for class '{args.target_class}'")
        return 1
    
    # Check existing cache
    existing_ids = set()
    if args.skip_existing:
        index_path = CACHE_DIR / "train" / "index.json"
        if index_path.exists():
            with open(index_path) as f:
                existing_ids = set(json.load(f).keys())
            print(f"Found {len(existing_ids):,} existing cache entries")
    
    # Get starting shard ID
    num_shards, _ = get_cache_shard_info(CACHE_DIR, "train")
    next_shard_id = num_shards
    print(f"Starting from shard ID: {next_shard_id}")
    
    # Synthesize
    note = GM_DRUM_NOTES[args.target_class]
    print(f"\nSynthesizing {args.target_class} hits (MIDI note {note})...")
    
    all_index_entries = {}
    new_shards_info = []
    
    batch_tensors = []
    batch_file_ids = []
    processed = 0
    skipped = 0
    
    start_time = time.time()
    
    for i, event in enumerate(events):
        if processed >= args.limit:
            break
        
        # Generate file ID
        file_id = generate_file_id(event, i)
        
        # Skip if already cached
        if file_id in existing_ids:
            skipped += 1
            continue
        
        # Synthesize with event's velocity (or use provided range)
        velocity = event.get('velocity', 100)
        velocity = max(args.velocity_range[0], min(args.velocity_range[1], velocity))
        
        try:
            audio = synthesize_hit(fs, note, velocity)
            mel_spec = compute_mel_spectrogram(audio)
            
            batch_tensors.append(mel_spec)
            batch_file_ids.append(file_id)
            processed += 1
            
            # Write shard when batch is full
            if len(batch_tensors) >= args.batch_size:
                shard_entries = write_shard(
                    CACHE_DIR, "train", next_shard_id,
                    batch_tensors, batch_file_ids
                )
                all_index_entries.update(shard_entries)
                new_shards_info.append({
                    "shard_id": next_shard_id,
                    "num_samples": len(batch_tensors),
                    "start_idx": sum(s["num_samples"] for s in new_shards_info),
                })
                
                next_shard_id += 1
                batch_tensors = []
                batch_file_ids = []
                
                elapsed = time.time() - start_time
                rate = processed / elapsed
                print(f"  Progress: {processed:,}/{args.limit:,} ({rate:.1f} samples/sec)")
        
        except Exception as e:
            print(f"  ERROR synthesizing {file_id}: {e}")
            continue
    
    # Write remaining batch
    if batch_tensors:
        shard_entries = write_shard(
            CACHE_DIR, "train", next_shard_id,
            batch_tensors, batch_file_ids
        )
        all_index_entries.update(shard_entries)
        new_shards_info.append({
            "shard_id": next_shard_id,
            "num_samples": len(batch_tensors),
            "start_idx": sum(s["num_samples"] for s in new_shards_info[:-1]) if new_shards_info else 0,
        })
    
    # Update index and manifest
    if all_index_entries:
        update_cache_index(CACHE_DIR, "train", all_index_entries)
        update_cache_manifest(CACHE_DIR, "train", new_shards_info)
    
    # Cleanup
    fs.delete()
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("SYNTHESIS COMPLETE")
    print("=" * 70)
    print(f"Synthesized: {processed:,} samples")
    print(f"Skipped: {skipped:,} (already cached)")
    print(f"New shards: {len(new_shards_info)}")
    print(f"Time: {elapsed:.1f}s ({processed/elapsed:.1f} samples/sec)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
