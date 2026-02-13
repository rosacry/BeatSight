#!/usr/bin/env python3
"""
Extract Multi-Label Training Data from MIDI Datasets

This script extracts real multi-label drum training data from datasets that have
MIDI files paired with audio. These provide ground truth for simultaneous drum hits.

Supported datasets:
- E-GMD (Expanded Groove MIDI Dataset) - ~25K MIDI files with audio
- Groove MIDI Dataset - Professional drummer recordings
- ENST-Drums - Isolated tracks with annotations
- Slakh2100 - Synthesized multi-track with MIDI

The key advantage over synthetic multi-label data:
- Real recordings of simultaneous hits (kick+hi-hat, snare+crash)
- Natural timing variations and dynamics
- Authentic bleed between drums in audio

Usage:
    # Analyze what's available
    python extract_multilabel_from_midi.py --sources egmd groove_midi --mode analyze

    # Extract multi-label data
    python extract_multilabel_from_midi.py \
        --sources egmd groove_midi enst \
        --output "F:/datasets/multilabel_real" \
        --feature-cache-dir "F:/feature_cache" \
        --mode extract
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

# Import mido for MIDI parsing (lightweight, no fluidsynth dependency)
try:
    import mido
except ImportError:
    print("Error: mido not installed. Install with: pip install mido")
    sys.exit(1)

# Import librosa for audio processing
try:
    import librosa
except ImportError:
    print("Error: librosa not installed. Install with: pip install librosa")
    sys.exit(1)

# Import torch for tensor operations
try:
    import torch
except ImportError:
    print("Error: torch not installed")
    sys.exit(1)

from tqdm import tqdm

# Note: We intentionally don't use pretty_midi because it has a hard dependency
# on fluidsynth which requires system libraries. mido is sufficient for parsing
# drum events from MIDI files.


# =============================================================================
# Audio Feature Extraction
# =============================================================================

def extract_mel_spectrogram(
    audio: np.ndarray,
    sr: int,
    onset_time: float,
    window_ms: float = 100.0,
    n_mels: int = 128,
    target_width: int = 128,
) -> Optional[np.ndarray]:
    """
    Extract a mel-spectrogram centered on an onset time.
    
    Args:
        audio: Audio data as numpy array
        sr: Sample rate
        onset_time: Center time in seconds
        window_ms: Window duration in milliseconds
        n_mels: Number of mel bands
        target_width: Target width for the spectrogram
    
    Returns:
        Normalized mel-spectrogram of shape (n_mels, target_width) or None if invalid
    """
    window_samples = int(sr * window_ms / 1000.0)
    center = int(onset_time * sr)
    
    # Extract window (slightly asymmetric - more audio after the onset)
    start = max(0, center - window_samples // 4)
    end = min(len(audio), center + window_samples)
    
    if end - start < window_samples // 4:
        return None  # Too short
    
    window = audio[start:end]
    
    # Pad if necessary
    if len(window) < window_samples:
        window = np.pad(window, (0, window_samples - len(window)), mode='constant')
    
    # Compute mel-spectrogram
    hop_length = max(1, len(window) // target_width)
    mel_spec = librosa.feature.melspectrogram(
        y=window, sr=sr, n_mels=n_mels, fmax=8000, hop_length=hop_length
    )
    
    # Convert to log scale (dB)
    mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
    
    # Normalize to [0, 1]
    mel_min, mel_max = mel_spec_db.min(), mel_spec_db.max()
    if mel_max - mel_min > 1e-8:
        mel_spec_norm = (mel_spec_db - mel_min) / (mel_max - mel_min)
    else:
        mel_spec_norm = np.zeros_like(mel_spec_db)
    
    # Resize to target width if needed
    if mel_spec_norm.shape[1] != target_width:
        # Use interpolation to resize
        from scipy.ndimage import zoom
        zoom_factor = target_width / mel_spec_norm.shape[1]
        mel_spec_norm = zoom(mel_spec_norm, (1, zoom_factor), order=1)
        # Ensure exact size
        mel_spec_norm = mel_spec_norm[:, :target_width]
        if mel_spec_norm.shape[1] < target_width:
            mel_spec_norm = np.pad(
                mel_spec_norm, 
                ((0, 0), (0, target_width - mel_spec_norm.shape[1])),
                mode='constant'
            )
    
    return mel_spec_norm.astype(np.float32)


def load_audio_file(audio_path: Path, sr: int = 22050) -> Optional[np.ndarray]:
    """Load an audio file, returning None if it fails."""
    try:
        audio, _ = librosa.load(str(audio_path), sr=sr, mono=True)
        return audio
    except Exception as e:
        return None


# =============================================================================
# GM Drum Map (General MIDI Standard)
# =============================================================================

# General MIDI drum map (note number -> drum name)
# WARNING: EGMD/Groove use Roland TD-11 mapping, not GM! Use TD11_DRUM_MAP for those.
GM_DRUM_MAP = {
    35: 'kick', 36: 'kick',  # Acoustic/Electric Bass Drum
    37: 'cross_stick', 38: 'snare', 40: 'snare',  # Side Stick, Snare
    39: 'snare',  # Hand Clap (often used as snare)
    41: 'tom', 43: 'tom', 45: 'tom', 47: 'tom', 48: 'tom', 50: 'tom',  # Toms
    42: 'hihat_closed', 44: 'hihat_pedal', 46: 'hihat_open',  # Hi-hat
    49: 'crash', 52: 'china', 55: 'splash', 57: 'crash',  # Cymbals
    51: 'ride_bow', 53: 'ride_bell', 59: 'ride_bow',  # Ride
    54: 'tambourine', 56: 'cowbell',  # Percussion (skip)
}

# Roland TD-11 Drum Map (used by EGMD and Groove MIDI Dataset)
# IMPORTANT: TD-11 has NO china or splash cymbals - only crash cymbals!
# Reference: https://magenta.tensorflow.org/datasets/e-gmd
TD11_DRUM_MAP = {
    35: 'kick', 36: 'kick',  # Bass Drum
    37: 'cross_stick', 38: 'snare', 40: 'snare',  # Snare variants
    42: 'hihat_closed', 22: 'hihat_closed',  # Closed HH (bow/edge)
    44: 'hihat_pedal',  # Pedal HH
    46: 'hihat_open', 26: 'hihat_open',  # Open HH (bow/edge)
    48: 'tom', 50: 'tom',  # Tom1 (high)
    45: 'tom', 47: 'tom',  # Tom2 (mid)
    43: 'tom', 58: 'tom',  # Tom3 (floor)
    51: 'ride_bow', 59: 'ride_bow',  # Ride (bow/edge)
    53: 'ride_bell',  # Ride Bell
    # ALL crashes on TD-11 - no china or splash!
    49: 'crash',  # Crash1 Bow
    55: 'crash',  # Crash1 Edge (NOT splash!)
    57: 'crash',  # Crash2 Bow
    52: 'crash',  # Crash2 Edge (NOT china!)
}

# Our 12-class mapping
CLASS_NAMES = [
    'china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open',
    'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom'
]
CLASS_TO_IDX = {name: idx for idx, name in enumerate(CLASS_NAMES)}


@dataclass
class DrumEvent:
    """A single drum hit event."""
    time: float  # Time in seconds
    drum_class: str  # Our 12-class name
    velocity: int  # 0-127
    note: int  # MIDI note number
    duration: float = 0.0  # Note duration (if available)


@dataclass
class MultiLabelWindow:
    """A window with potentially multiple simultaneous drum hits."""
    start_time: float
    end_time: float
    labels: Set[str]  # Set of drum classes active in this window
    label_vector: np.ndarray = field(default_factory=lambda: np.zeros(12))
    audio_file: Optional[str] = None
    source_dataset: str = ""


def parse_midi_for_drums(
    midi_path: Path, 
    merge_window_ms: float = 30.0,
    drum_map: Optional[Dict[int, str]] = None,
) -> List[MultiLabelWindow]:
    """
    Parse a MIDI file and extract drum events, merging simultaneous hits.
    
    Args:
        midi_path: Path to MIDI file
        merge_window_ms: Window in milliseconds to merge as "simultaneous"
        drum_map: MIDI note to drum class mapping. Default is GM_DRUM_MAP.
                  Use TD11_DRUM_MAP for EGMD/Groove datasets.
    
    Returns:
        List of MultiLabelWindow objects
    """
    if drum_map is None:
        drum_map = GM_DRUM_MAP
    
    merge_window = merge_window_ms / 1000.0  # Convert to seconds
    
    # Collect all drum events using mido
    events: List[DrumEvent] = []
    
    try:
        mid = mido.MidiFile(str(midi_path))
        tempo = 500000  # Default tempo (120 BPM)
        ticks_per_beat = mid.ticks_per_beat
        
        for track in mid.tracks:
            current_time = 0.0
            for msg in track:
                # Convert delta time to seconds
                current_time += mido.tick2second(msg.time, ticks_per_beat, tempo)
                
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                elif msg.type == 'note_on' and msg.velocity > 0:
                    # Check if this is on drum channel (9) or any channel for drum-only files
                    drum_class = drum_map.get(msg.note)
                    if drum_class and drum_class in CLASS_TO_IDX:
                        events.append(DrumEvent(
                            time=current_time,
                            drum_class=drum_class,
                            velocity=msg.velocity,
                            note=msg.note
                        ))
    except Exception as e:
        print(f"  Warning: Could not parse {midi_path}: {e}")
        return []
    
    if not events:
        return []
    
    # Sort by time
    events.sort(key=lambda e: e.time)
    
    # Merge events within the merge window
    windows: List[MultiLabelWindow] = []
    current_window: Optional[MultiLabelWindow] = None
    
    for event in events:
        if current_window is None:
            # Start new window
            current_window = MultiLabelWindow(
                start_time=event.time,
                end_time=event.time + merge_window,
                labels={event.drum_class}
            )
        elif event.time <= current_window.end_time:
            # Add to current window (simultaneous hit)
            current_window.labels.add(event.drum_class)
            current_window.end_time = max(current_window.end_time, event.time + merge_window)
        else:
            # Finalize current window and start new one
            current_window.label_vector = np.zeros(12)
            for label in current_window.labels:
                current_window.label_vector[CLASS_TO_IDX[label]] = 1
            windows.append(current_window)
            
            current_window = MultiLabelWindow(
                start_time=event.time,
                end_time=event.time + merge_window,
                labels={event.drum_class}
            )
    
    # Don't forget the last window
    if current_window is not None:
        current_window.label_vector = np.zeros(12)
        for label in current_window.labels:
            current_window.label_vector[CLASS_TO_IDX[label]] = 1
        windows.append(current_window)
    
    return windows


def _pool_init_worker():
    """Initializer for multiprocessing Pool workers - ignore SIGINT so main handles Ctrl-C."""
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _process_single_file(args: Tuple[Path, Path, int, Optional[Dict[int, str]]]) -> Tuple[str, Optional[List[np.ndarray]], Optional[List[np.ndarray]]]:
    """
    Worker function to process a single MIDI+audio pair.
    Returns tuple of (midi_path, features_list, labels_list) or (midi_path, None, None) on error.
    
    This runs in a separate process for parallelization.
    
    Args:
        args: Tuple of (midi_file, audio_file, sr, drum_map)
              drum_map: Optional custom drum mapping (e.g., TD11_DRUM_MAP for EGMD/Groove)
    """
    # Support both old 3-tuple and new 4-tuple format for backwards compatibility
    if len(args) == 3:
        midi_file, audio_file, sr = args
        drum_map = None
    else:
        midi_file, audio_file, sr, drum_map = args
    
    midi_path = str(midi_file)
    features = []
    labels = []
    
    try:
        # Parse MIDI for drum events using appropriate drum map
        windows = parse_midi_for_drums(midi_file, drum_map=drum_map)
        if not windows:
            return (midi_path, None, None)
        
        # Load audio
        audio = load_audio_file(audio_file, sr=sr)
        if audio is None:
            return (midi_path, None, None)
        
        # Extract spectrogram for each window
        for w in windows:
            mel_spec = extract_mel_spectrogram(audio, sr, w.start_time)
            if mel_spec is not None:
                features.append(mel_spec)
                labels.append(w.label_vector)
        
        if not features:
            return (midi_path, None, None)
            
        return (midi_path, features, labels)
            
    except Exception:
        return (midi_path, None, None)  # Silently skip problematic files


def analyze_egmd(egmd_path: Path) -> Dict[str, Any]:
    """Analyze E-GMD dataset structure."""
    stats = {
        'total_midi_files': 0,
        'total_audio_files': 0,
        'drummers': [],
        'sessions': [],
        'multi_label_windows': 0,
        'single_label_windows': 0,
        'label_distribution': defaultdict(int),
        'combo_distribution': defaultdict(int),
        'sample_files': [],
    }
    
    # E-GMD structure: egmd/drummer{N}/session{M}/*.mid + *.wav
    for drummer_dir in sorted(egmd_path.glob('drummer*')):
        if not drummer_dir.is_dir():
            continue
        stats['drummers'].append(drummer_dir.name)
        
        for session_dir in sorted(drummer_dir.glob('*session*')):
            if not session_dir.is_dir():
                continue
            stats['sessions'].append(f"{drummer_dir.name}/{session_dir.name}")
            
            midi_files = list(session_dir.glob('*.mid')) + list(session_dir.glob('*.midi'))
            audio_files = list(session_dir.glob('*.wav')) + list(session_dir.glob('*.mp3'))
            
            stats['total_midi_files'] += len(midi_files)
            stats['total_audio_files'] += len(audio_files)
            
            # Sample a few files for analysis - use TD11 mapping for EGMD
            for midi_file in midi_files[:3]:
                windows = parse_midi_for_drums(midi_file, drum_map=TD11_DRUM_MAP)
                for w in windows:
                    if len(w.labels) > 1:
                        stats['multi_label_windows'] += 1
                        combo = tuple(sorted(w.labels))
                        stats['combo_distribution'][str(combo)] += 1
                    else:
                        stats['single_label_windows'] += 1
                    for label in w.labels:
                        stats['label_distribution'][label] += 1
                
                if len(stats['sample_files']) < 5:
                    stats['sample_files'].append({
                        'path': str(midi_file),
                        'windows': len(windows),
                        'multi_label': sum(1 for w in windows if len(w.labels) > 1)
                    })
    
    return stats


def analyze_groove_midi(groove_path: Path) -> Dict[str, Any]:
    """Analyze Groove MIDI dataset structure."""
    stats = {
        'total_midi_files': 0,
        'total_audio_files': 0,
        'multi_label_windows': 0,
        'single_label_windows': 0,
        'label_distribution': defaultdict(int),
        'combo_distribution': defaultdict(int),
    }
    
    # Groove MIDI can have various structures
    midi_files = list(groove_path.rglob('*.mid')) + list(groove_path.rglob('*.midi'))
    audio_files = list(groove_path.rglob('*.wav'))
    
    stats['total_midi_files'] = len(midi_files)
    stats['total_audio_files'] = len(audio_files)
    
    # Sample analysis - use TD11 mapping for Groove MIDI (also uses Roland TD-11)
    for midi_file in midi_files[:20]:
        windows = parse_midi_for_drums(midi_file, drum_map=TD11_DRUM_MAP)
        for w in windows:
            if len(w.labels) > 1:
                stats['multi_label_windows'] += 1
                combo = tuple(sorted(w.labels))
                stats['combo_distribution'][str(combo)] += 1
            else:
                stats['single_label_windows'] += 1
            for label in w.labels:
                stats['label_distribution'][label] += 1
    
    return stats


def analyze_enst(enst_path: Path) -> Dict[str, Any]:
    """Analyze ENST-Drums dataset structure."""
    stats = {
        'total_audio_files': 0,
        'total_annotation_files': 0,
        'drummers': [],
        'recording_types': set(),
    }
    
    # ENST structure: drummer_{N}/audio/{mix,overhead,kick,snare,...}/*.wav
    for drummer_dir in sorted(enst_path.glob('drummer_*')):
        if not drummer_dir.is_dir():
            continue
        stats['drummers'].append(drummer_dir.name)
        
        audio_dir = drummer_dir / 'audio'
        if audio_dir.exists():
            for subdir in audio_dir.iterdir():
                if subdir.is_dir():
                    stats['recording_types'].add(subdir.name)
                    audio_files = list(subdir.glob('*.wav'))
                    stats['total_audio_files'] += len(audio_files)
        
        # Check for annotations
        annotation_dir = drummer_dir / 'annotation'
        if annotation_dir.exists():
            annotation_files = list(annotation_dir.rglob('*.txt')) + list(annotation_dir.rglob('*.csv'))
            stats['total_annotation_files'] += len(annotation_files)
    
    stats['recording_types'] = list(stats['recording_types'])
    return stats


def analyze_slakh(slakh_path: Path) -> Dict[str, Any]:
    """Analyze Slakh2100 dataset structure."""
    stats = {
        'total_tracks': 0,
        'tracks_with_drums': 0,
        'total_midi_files': 0,
    }
    
    # Slakh structure: Track{NNNNN}/MIDI/drums.mid
    for track_dir in slakh_path.glob('Track*'):
        if not track_dir.is_dir():
            continue
        stats['total_tracks'] += 1
        
        midi_dir = track_dir / 'MIDI'
        if midi_dir.exists():
            drum_midi = midi_dir / 'drums.mid'
            if drum_midi.exists():
                stats['tracks_with_drums'] += 1
                stats['total_midi_files'] += 1
    
    return stats


def extract_multilabel_from_egmd(
    egmd_path: Path,
    output_path: Path,
    feature_cache_dir: Optional[Path] = None,
    max_samples: Optional[int] = None,
    sr: int = 22050,
    num_workers: int = 0,
) -> Dict[str, Any]:
    """
    Extract multi-label training data from E-GMD dataset.
    
    This extracts mel-spectrograms centered on each drum hit, with multi-hot labels
    for all drums that sound within the merge window.
    
    Args:
        num_workers: Number of parallel workers. 0 = auto (cpu_count - 2)
    """
    print(f"\n📦 Extracting from E-GMD: {egmd_path}")
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Check if extraction already completed (manifest exists)
    manifest_file = output_path / 'egmd_manifest.json'
    if manifest_file.exists():
        import json
        with open(manifest_file) as f:
            manifest = json.load(f)
        total_samples = manifest.get('total_samples', 0)
        # Calculate train/val from batches if not directly stored
        train_samples = manifest.get('train_samples', 0)
        val_samples = manifest.get('val_samples', 0)
        if train_samples == 0 and 'batches' in manifest:
            batches = manifest['batches']
            # Handle both dict and list formats
            batch_items = batches.values() if isinstance(batches, dict) else batches
            for batch_info in batch_items:
                if isinstance(batch_info, dict):
                    if batch_info.get('split') == 'train':
                        train_samples += batch_info.get('samples', 0)
                    else:
                        val_samples += batch_info.get('samples', 0)
        print(f"   ✅ Already extracted: {total_samples:,} samples")
        print(f"      Train: {train_samples:,}, Val: {val_samples:,}")
        return {
            'samples_extracted': total_samples,
            'train_samples': train_samples,
            'val_samples': val_samples,
        }
    
    train_dir = output_path / 'train'
    val_dir = output_path / 'val'
    train_dir.mkdir(exist_ok=True)
    val_dir.mkdir(exist_ok=True)
    
    # Collect all MIDI + audio pairs
    # EGMD uses Roland TD-11 electronic kit - use TD11 mapping
    pairs = []
    seen_midi_files = set()  # Avoid duplicates from overlapping glob patterns
    for drummer_dir in sorted(egmd_path.glob('drummer*')):
        # E-GMD has session1, session2, eval_session, etc.
        # Use only *session* which matches all session directories
        for session_dir in sorted(drummer_dir.glob('*session*')):
            # Look for both .mid and .midi files
            for midi_file in list(session_dir.glob('*.mid')) + list(session_dir.glob('*.midi')):
                # Skip if already seen (handles .mid/.midi duplicates if any)
                midi_key = str(midi_file)
                if midi_key in seen_midi_files:
                    continue
                seen_midi_files.add(midi_key)
                
                # Find matching audio
                audio_file = midi_file.with_suffix('.wav')
                if not audio_file.exists():
                    audio_file = session_dir / f"{midi_file.stem}.wav"
                if audio_file.exists():
                    # Pass TD11_DRUM_MAP for correct Roland TD-11 mapping
                    pairs.append((midi_file, audio_file, sr, TD11_DRUM_MAP))
    
    print(f"   Found {len(pairs)} MIDI+audio pairs")
    
    if not pairs:
        print("   ⚠️ No MIDI+audio pairs found!")
        return {'samples_extracted': 0}
    
    # Determine number of workers - ProcessPoolExecutor gives true parallelism
    # Use most cores but leave 2 for system + I/O
    if num_workers <= 0:
        import os
        num_workers = max(1, os.cpu_count() - 2)  # 14 workers on 16-thread CPU
    print(f"   Using {num_workers} worker(s)...")
    
    # Setup checkpoint for resume capability
    temp_dir = output_path / 'temp_batches'
    temp_dir.mkdir(exist_ok=True)
    checkpoint_file = temp_dir / 'checkpoint.json'
    
    # Check for existing progress
    processed_files = set()
    batch_num = 0
    total_samples = 0
    
    if checkpoint_file.exists():
        import json
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
        processed_files = set(checkpoint.get('processed_files', []))
        batch_num = checkpoint.get('batch_num', 0)
        total_samples = checkpoint.get('total_samples', 0)
        print(f"   📂 Resuming from checkpoint: {len(processed_files)} files done, {total_samples:,} samples, batch {batch_num}")
    
    # Filter out already processed pairs (4-tuples: midi, audio, sr, drum_map)
    pairs_to_process = [(m, a, s, dm) for m, a, s, dm in pairs if str(m) not in processed_files]
    print(f"   Remaining: {len(pairs_to_process)} files to process")
    
    if not pairs_to_process:
        print("   ✅ All files already processed!")
        # Skip to merge step
    else:
        spec_flush_threshold = 2000  # Flush every 2000 spectrograms (~128 MB) - safe with 32GB RAM
        
        print(f"   Extracting spectrograms from {len(pairs_to_process)} files...")
        print(f"   (Flushing every ~{spec_flush_threshold} spectrograms, {num_workers} workers)")
        
        skipped = 0
        batch_features = []
        batch_labels = []
        newly_processed = []
        interrupted = False
        
        pbar = tqdm(total=len(pairs_to_process), desc="   Processing")
        
        # Use multiprocessing Pool with imap for true parallelism + streaming results
        from multiprocessing import Pool
        
        try:
            with Pool(processes=num_workers, initializer=_pool_init_worker) as pool:
                # imap_unordered gives results as they complete (streaming)
                for result in pool.imap_unordered(_process_single_file, pairs_to_process, chunksize=10):
                    if interrupted:
                        pool.terminate()
                        break
                    
                    midi_path, features, labels = result
                    
                    if features is None:
                        skipped += 1
                    else:
                        for feat, label in zip(features, labels):
                            batch_features.append(feat)
                            batch_labels.append(label)
                    
                    newly_processed.append(midi_path)
                    pbar.update(1)
                    
                    # Flush to disk when we have enough spectrograms
                    if len(batch_features) >= spec_flush_threshold:
                        feat_arr = np.array(batch_features, dtype=np.float32)
                        label_arr = np.array(batch_labels, dtype=np.float32)
                        np.save(temp_dir / f'features_batch_{batch_num}.npy', feat_arr)
                        np.save(temp_dir / f'labels_batch_{batch_num}.npy', label_arr)
                        del feat_arr, label_arr
                        
                        total_samples += len(batch_features)
                        batch_num += 1
                        
                        # Save checkpoint
                        processed_files.update(newly_processed)
                        import json
                        with open(checkpoint_file, 'w') as f:
                            json.dump({
                                'processed_files': list(processed_files),
                                'batch_num': batch_num,
                                'total_samples': total_samples
                            }, f)
                        
                        batch_features.clear()
                        batch_labels.clear()
                        newly_processed.clear()
                        import gc; gc.collect()
                    
                    if max_samples and total_samples >= max_samples:
                        pool.terminate()
                        break
                    
        except KeyboardInterrupt:
            print("\n\n   ⚠️ Interrupted! Saving progress...")
            interrupted = True
        
        # Save remaining samples
        if batch_features:
            feat_arr = np.array(batch_features, dtype=np.float32)
            label_arr = np.array(batch_labels, dtype=np.float32)
            np.save(temp_dir / f'features_batch_{batch_num}.npy', feat_arr)
            np.save(temp_dir / f'labels_batch_{batch_num}.npy', label_arr)
            del feat_arr, label_arr
            total_samples += len(batch_features)
            batch_num += 1
            
            # Final checkpoint
            processed_files.update(newly_processed)
            import json
            with open(checkpoint_file, 'w') as f:
                json.dump({
                    'processed_files': list(processed_files),
                    'batch_num': batch_num,
                    'total_samples': total_samples
                }, f)
            batch_features.clear()
            batch_labels.clear()
        
        pbar.close()
        
        if skipped > 0:
            print(f"   ⚠️ Skipped {skipped} files due to errors/timeouts")
        
        # If interrupted, save checkpoint but don't finalize - user can resume later
        if interrupted:
            print(f"   💾 Progress saved: {len(processed_files)} files, {total_samples:,} samples")
            print(f"   Run again to resume from checkpoint.")
            raise KeyboardInterrupt  # Propagate to stop the whole script
    
    if total_samples == 0:
        print("   ⚠️ No valid samples extracted!")
        return {'samples_extracted': 0}
    
    # Instead of merging (would be ~300GB for 4.6M samples), create a manifest
    # Training will load batches on-demand
    print(f"   Creating manifest for {batch_num} batches ({total_samples:,} samples)...")
    
    # Create manifest file listing all batches
    manifest = {
        'dataset': 'egmd',
        'total_samples': total_samples,
        'batch_count': batch_num,
        'sample_rate': sr,
        'feature_shape': [128, 128],
        'num_classes': 12,
        'batches': []
    }
    
    # Scan batches to get sample counts and compute train/val split
    np.random.seed(42)
    batch_sample_counts = []
    for i in range(batch_num):
        labels = np.load(temp_dir / f'labels_batch_{i}.npy')
        batch_sample_counts.append(len(labels))
        
        # Compute multi-label stats from first few batches
        if i < 10:
            multi_count = np.sum(labels.sum(axis=1) > 1)
            manifest['batches'].append({
                'features': f'features_batch_{i}.npy',
                'labels': f'labels_batch_{i}.npy',
                'samples': len(labels),
                'multi_label_ratio': float(multi_count / len(labels))
            })
        else:
            manifest['batches'].append({
                'features': f'features_batch_{i}.npy',
                'labels': f'labels_batch_{i}.npy',
                'samples': len(labels),
            })
        del labels
    
    # Randomly assign batches to train/val (90/10 by batch)
    batch_indices = np.random.permutation(batch_num)
    n_val_batches = max(1, batch_num // 10)
    val_batch_set = set(batch_indices[:n_val_batches])
    
    for i, batch_info in enumerate(manifest['batches']):
        batch_info['split'] = 'val' if i in val_batch_set else 'train'
    
    # Compute overall multi-label ratio from sampled batches
    sampled_ratios = [b.get('multi_label_ratio', 0) for b in manifest['batches'][:10]]
    manifest['estimated_multi_label_ratio'] = float(np.mean(sampled_ratios)) if sampled_ratios else 0
    
    # Save manifest
    manifest_path = output_path / 'egmd_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Move batch files to organized structure
    egmd_batches_dir = output_path / 'egmd_batches'
    egmd_batches_dir.mkdir(exist_ok=True)
    
    import shutil
    for i in range(batch_num):
        src_feat = temp_dir / f'features_batch_{i}.npy'
        src_label = temp_dir / f'labels_batch_{i}.npy'
        if src_feat.exists():
            shutil.move(str(src_feat), str(egmd_batches_dir / f'features_batch_{i}.npy'))
        if src_label.exists():
            shutil.move(str(src_label), str(egmd_batches_dir / f'labels_batch_{i}.npy'))
    
    # Cleanup temp dir (checkpoint file etc)
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    train_samples = sum(manifest['batches'][i]['samples'] for i in range(batch_num) if i not in val_batch_set)
    val_samples = sum(manifest['batches'][i]['samples'] for i in val_batch_set)
    
    print(f"   ✅ Extracted {total_samples:,} samples across {batch_num} batches")
    print(f"      Train batches: {batch_num - n_val_batches}, Val batches: {n_val_batches}")
    print(f"      Train samples: ~{train_samples:,}, Val samples: ~{val_samples:,}")
    print(f"      Estimated multi-label: {manifest['estimated_multi_label_ratio']*100:.1f}%")
    print(f"      Manifest: {manifest_path}")
    
    return {
        'samples_extracted': total_samples,
        'train_samples': train_samples,
        'val_samples': val_samples,
        'multi_label_ratio': manifest['estimated_multi_label_ratio'],
        'batch_count': batch_num,
        'manifest_path': str(manifest_path),
    }


def extract_multilabel_from_groove_midi(
    groove_path: Path,
    output_path: Path,
    feature_cache_dir: Optional[Path] = None,
    max_samples: Optional[int] = None,
    sr: int = 22050,
    num_workers: int = 0,
) -> Dict[str, Any]:
    """
    Extract multi-label training data from Groove MIDI dataset.
    Computes mel-spectrograms for each drum event using parallel processing.
    """
    print(f"\n📦 Extracting from Groove MIDI: {groove_path}")
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Check if extraction already completed (manifest exists)
    manifest_file = output_path / 'groove_manifest.json'
    if manifest_file.exists():
        import json
        with open(manifest_file) as f:
            manifest = json.load(f)
        total_samples = manifest.get('total_samples', 0)
        train_samples = manifest.get('train_samples', 0)
        val_samples = manifest.get('val_samples', 0)
        print(f"   ✅ Already extracted: {total_samples:,} samples")
        print(f"      Train: {train_samples:,}, Val: {val_samples:,}")
        return {
            'samples_extracted': total_samples,
            'train_samples': train_samples,
            'val_samples': val_samples,
        }
    
    train_dir = output_path / 'train'
    val_dir = output_path / 'val'
    train_dir.mkdir(exist_ok=True)
    val_dir.mkdir(exist_ok=True)
    
    # Groove MIDI: find all MIDI files with matching WAV
    # Groove MIDI also uses Roland TD-11 electronic kit - use TD11 mapping
    pairs = []
    for midi_file in groove_path.rglob('*.mid'):
        audio_file = midi_file.with_suffix('.wav')
        if audio_file.exists():
            pairs.append((midi_file, audio_file, sr, TD11_DRUM_MAP))
    for midi_file in groove_path.rglob('*.midi'):
        audio_file = midi_file.with_suffix('.wav')
        if audio_file.exists():
            pairs.append((midi_file, audio_file, sr, TD11_DRUM_MAP))
    
    print(f"   Found {len(pairs)} MIDI+audio pairs")
    
    if not pairs:
        print("   ⚠️ No MIDI+audio pairs found!")
        return {'samples_extracted': 0}
    
    # Determine number of workers - ThreadPoolExecutor is memory-safe
    if num_workers <= 0:
        import os
        num_workers = min(6, max(1, os.cpu_count() - 2))  # 6 workers for 8-core
    print(f"   Using {num_workers} worker(s)...")
    
    # Setup checkpoint for resume capability
    temp_dir = output_path / 'temp_batches_groove'
    temp_dir.mkdir(exist_ok=True)
    checkpoint_file = temp_dir / 'checkpoint.json'
    
    # Check for existing progress
    processed_files = set()
    batch_num = 0
    total_samples = 0
    
    if checkpoint_file.exists():
        import json
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
        processed_files = set(checkpoint.get('processed_files', []))
        batch_num = checkpoint.get('batch_num', 0)
        total_samples = checkpoint.get('total_samples', 0)
        print(f"   📂 Resuming from checkpoint: {len(processed_files)} files done, {total_samples:,} samples, batch {batch_num}")
    
    # Filter out already processed pairs (4-tuples: midi, audio, sr, drum_map)
    pairs_to_process = [(m, a, s, dm) for m, a, s, dm in pairs if str(m) not in processed_files]
    print(f"   Remaining: {len(pairs_to_process)} files to process")
    
    if not pairs_to_process:
        print("   ✅ All files already processed!")
    else:
        spec_flush_threshold = 2000  # Flush every 2000 spectrograms (~128 MB) - safe with 32GB RAM
        
        print(f"   Extracting spectrograms from {len(pairs_to_process)} files...")
        print(f"   (Flushing to disk every ~{spec_flush_threshold} spectrograms)")
        
        skipped = 0
        batch_features = []
        batch_labels = []
        newly_processed = []
        interrupted = False
        
        pbar = tqdm(total=len(pairs_to_process), desc="   Processing")
        
        # Use multiprocessing Pool with imap for true parallelism + streaming results
        from multiprocessing import Pool
        
        try:
            with Pool(processes=num_workers, initializer=_pool_init_worker) as pool:
                for result in pool.imap_unordered(_process_single_file, pairs_to_process, chunksize=10):
                    if interrupted:
                        pool.terminate()
                        break
                    
                    midi_path, features, labels = result
                    
                    if features is None:
                        skipped += 1
                    else:
                        for feat, label in zip(features, labels):
                            batch_features.append(feat)
                            batch_labels.append(label)
                    
                    newly_processed.append(midi_path)
                    pbar.update(1)
                    
                    # Flush to disk when we have enough spectrograms
                    if len(batch_features) >= spec_flush_threshold:
                        feat_arr = np.array(batch_features, dtype=np.float32)
                        label_arr = np.array(batch_labels, dtype=np.float32)
                        np.save(temp_dir / f'features_batch_{batch_num}.npy', feat_arr)
                        np.save(temp_dir / f'labels_batch_{batch_num}.npy', label_arr)
                        del feat_arr, label_arr
                        
                        total_samples += len(batch_features)
                        batch_num += 1
                        
                        # Save checkpoint
                        processed_files.update(newly_processed)
                        import json
                        with open(checkpoint_file, 'w') as f:
                            json.dump({
                                'processed_files': list(processed_files),
                                'batch_num': batch_num,
                                'total_samples': total_samples
                            }, f)
                        
                        batch_features.clear()
                        batch_labels.clear()
                        newly_processed.clear()
                        import gc; gc.collect()
                    
                    if max_samples and total_samples >= max_samples:
                        pool.terminate()
                        break
                    
        except KeyboardInterrupt:
            print("\n\n   ⚠️ Interrupted! Saving progress...")
            interrupted = True
        
        # Save remaining
        if batch_features:
            feat_arr = np.array(batch_features, dtype=np.float32)
            label_arr = np.array(batch_labels, dtype=np.float32)
            np.save(temp_dir / f'features_batch_{batch_num}.npy', feat_arr)
            np.save(temp_dir / f'labels_batch_{batch_num}.npy', label_arr)
            del feat_arr, label_arr
            total_samples += len(batch_features)
            batch_num += 1
            
            # Final checkpoint
            processed_files.update(newly_processed)
            import json
            with open(checkpoint_file, 'w') as f:
                json.dump({
                    'processed_files': list(processed_files),
                    'batch_num': batch_num,
                    'total_samples': total_samples
                }, f)
            batch_features.clear()
            batch_labels.clear()
        
        pbar.close()
        
        if skipped > 0:
            print(f"   ⚠️ Skipped {skipped} files due to errors/timeouts")
    
    if total_samples == 0:
        print("   ⚠️ No valid samples extracted!")
        return {'samples_extracted': 0}
    
    # Instead of merging, create a manifest for batch-based loading
    print(f"   Creating manifest for {batch_num} batches ({total_samples:,} samples)...")
    
    manifest = {
        'dataset': 'groove_midi',
        'total_samples': total_samples,
        'batch_count': batch_num,
        'sample_rate': sr,
        'feature_shape': [128, 128],
        'num_classes': 12,
        'batches': []
    }
    
    np.random.seed(42)
    for i in range(batch_num):
        labels = np.load(temp_dir / f'labels_batch_{i}.npy')
        multi_count = np.sum(labels.sum(axis=1) > 1) if i < 10 else 0
        batch_info = {
            'features': f'features_batch_{i}.npy',
            'labels': f'labels_batch_{i}.npy',
            'samples': len(labels),
        }
        if i < 10:
            batch_info['multi_label_ratio'] = float(multi_count / len(labels))
        manifest['batches'].append(batch_info)
        del labels
    
    # Assign train/val splits by batch
    batch_indices = np.random.permutation(batch_num)
    n_val_batches = max(1, batch_num // 10)
    val_batch_set = set(batch_indices[:n_val_batches])
    
    for i, batch_info in enumerate(manifest['batches']):
        batch_info['split'] = 'val' if i in val_batch_set else 'train'
    
    sampled_ratios = [b.get('multi_label_ratio', 0) for b in manifest['batches'][:10]]
    manifest['estimated_multi_label_ratio'] = float(np.mean(sampled_ratios)) if sampled_ratios else 0
    
    manifest_path = output_path / 'groove_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Move batches to organized directory
    groove_batches_dir = output_path / 'groove_batches'
    groove_batches_dir.mkdir(exist_ok=True)
    
    import shutil
    for i in range(batch_num):
        src_feat = temp_dir / f'features_batch_{i}.npy'
        src_label = temp_dir / f'labels_batch_{i}.npy'
        if src_feat.exists():
            shutil.move(str(src_feat), str(groove_batches_dir / f'features_batch_{i}.npy'))
        if src_label.exists():
            shutil.move(str(src_label), str(groove_batches_dir / f'labels_batch_{i}.npy'))
    
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    train_samples = sum(manifest['batches'][i]['samples'] for i in range(batch_num) if i not in val_batch_set)
    val_samples = sum(manifest['batches'][i]['samples'] for i in val_batch_set)
    
    print(f"   ✅ Extracted {total_samples:,} samples across {batch_num} batches")
    print(f"      Train batches: {batch_num - n_val_batches}, Val batches: {n_val_batches}")
    print(f"      Train samples: ~{train_samples:,}, Val samples: ~{val_samples:,}")
    print(f"      Estimated multi-label: {manifest['estimated_multi_label_ratio']*100:.1f}%")
    print(f"      Manifest: {manifest_path}")
    
    return {
        'samples_extracted': total_samples, 
        'train_samples': train_samples, 
        'val_samples': val_samples, 
        'multi_label_ratio': manifest['estimated_multi_label_ratio'],
        'batch_count': batch_num,
        'manifest_path': str(manifest_path),
    }


def extract_multilabel_from_slakh(
    slakh_path: Path,
    output_path: Path,
    feature_cache_dir: Optional[Path] = None,
    max_samples: Optional[int] = None,
    sr: int = 22050,
) -> Dict[str, Any]:
    """
    Extract multi-label training data from Slakh2100 dataset.
    
    Slakh2100 structure:
    - Track{NNNNN}/metadata.yaml (contains stem info with is_drum: true/false)
    - Track{NNNNN}/MIDI/{stem_id}.mid (e.g., S01.mid)
    - Track{NNNNN}/stems/{stem_id}.flac (e.g., S01.flac)
    
    Uses GM_DRUM_MAP by default since Slakh uses General MIDI mapping.
    """
    import yaml
    
    print(f"\n📦 Extracting from Slakh2100: {slakh_path}")
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Check if extraction already completed (manifest exists)
    manifest_file = output_path / 'slakh_manifest.json'
    if manifest_file.exists():
        import json
        with open(manifest_file) as f:
            manifest = json.load(f)
        total_samples = manifest.get('total_samples', 0)
        train_samples = manifest.get('train_samples', 0)
        val_samples = manifest.get('val_samples', 0)
        print(f"   ✅ Already extracted: {total_samples:,} samples")
        print(f"      Train: {train_samples:,}, Val: {val_samples:,}")
        return {
            'samples_extracted': total_samples,
            'train_samples': train_samples,
            'val_samples': val_samples,
        }
    
    train_dir = output_path / 'train'
    val_dir = output_path / 'val'
    train_dir.mkdir(exist_ok=True)
    val_dir.mkdir(exist_ok=True)
    
    def find_drum_stem(track_dir: Path) -> Optional[str]:
        """Find the drum stem ID by parsing metadata.yaml"""
        metadata_file = track_dir / 'metadata.yaml'
        if not metadata_file.exists():
            return None
        try:
            with open(metadata_file, 'r') as f:
                metadata = yaml.safe_load(f)
            stems = metadata.get('stems', {})
            for stem_id, stem_info in stems.items():
                if stem_info.get('is_drum', False) and stem_info.get('audio_rendered', False):
                    return stem_id
        except Exception:
            pass
        return None
    
    # Slakh structure: Track{NNNNN}/MIDI/{stem}.mid + stems/{stem}.flac
    pairs = []
    skipped_no_drums = 0
    skipped_no_audio = 0
    
    for split in ['train', 'test', 'validation', '']:
        split_path = slakh_path / split if split else slakh_path
        if not split_path.exists():
            continue
        for track_dir in split_path.glob('Track*'):
            # Find drum stem from metadata
            drum_stem = find_drum_stem(track_dir)
            if not drum_stem:
                skipped_no_drums += 1
                continue
            
            midi_file = track_dir / 'MIDI' / f'{drum_stem}.mid'
            if not midi_file.exists():
                skipped_no_drums += 1
                continue
            
            # Look for .flac audio (Slakh uses FLAC format)
            audio_file = track_dir / 'stems' / f'{drum_stem}.flac'
            if not audio_file.exists():
                # Fallback: try .wav just in case
                audio_file = track_dir / 'stems' / f'{drum_stem}.wav'
            if not audio_file.exists():
                # Last resort: try mix
                audio_file = track_dir / 'mix.flac'
            if audio_file.exists():
                # Use GM mapping for Slakh (General MIDI)
                pairs.append((midi_file, audio_file, sr, GM_DRUM_MAP))
            else:
                skipped_no_audio += 1
    
    print(f"   Found {len(pairs)} MIDI+audio pairs")
    if skipped_no_drums > 0:
        print(f"   Skipped {skipped_no_drums} tracks (no drum stem)")
    if skipped_no_audio > 0:
        print(f"   Skipped {skipped_no_audio} tracks (no audio file)")
    
    if not pairs:
        print("   ⚠️ No MIDI+audio pairs found!")
        return {'samples_extracted': 0}
    
    # Use parallel processing like EGMD/Groove
    import os
    num_workers = max(1, os.cpu_count() - 2)
    print(f"   Using {num_workers} worker(s)...")
    
    # Setup checkpoint for resume capability
    temp_dir = output_path / 'temp_batches_slakh'
    temp_dir.mkdir(exist_ok=True)
    checkpoint_file = temp_dir / 'checkpoint.json'
    
    processed_files = set()
    batch_num = 0
    total_samples = 0
    
    if checkpoint_file.exists():
        import json
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
        processed_files = set(checkpoint.get('processed_files', []))
        batch_num = checkpoint.get('batch_num', 0)
        total_samples = checkpoint.get('total_samples', 0)
        print(f"   📂 Resuming from checkpoint: {len(processed_files)} files done, {total_samples:,} samples")
    
    pairs_to_process = [(m, a, s, dm) for m, a, s, dm in pairs if str(m) not in processed_files]
    print(f"   Remaining: {len(pairs_to_process)} files to process")
    
    if not pairs_to_process:
        print("   ✅ All files already processed!")
    else:
        spec_flush_threshold = 2000
        
        print(f"   Extracting spectrograms from {len(pairs_to_process)} files...")
        print(f"   (Flushing every ~{spec_flush_threshold} spectrograms, {num_workers} workers)")
        
        skipped = 0
        batch_features = []
        batch_labels = []
        newly_processed = []
        interrupted = False
        
        pbar = tqdm(total=len(pairs_to_process), desc="   Processing")
        
        from multiprocessing import Pool
        
        try:
            with Pool(processes=num_workers, initializer=_pool_init_worker) as pool:
                for result in pool.imap_unordered(_process_single_file, pairs_to_process, chunksize=5):
                    if interrupted:
                        pool.terminate()
                        break
                    
                    midi_path, features, labels = result
                    
                    if features is None:
                        skipped += 1
                    else:
                        for feat, label in zip(features, labels):
                            batch_features.append(feat)
                            batch_labels.append(label)
                    
                    newly_processed.append(midi_path)
                    pbar.update(1)
                    
                    if len(batch_features) >= spec_flush_threshold:
                        feat_arr = np.array(batch_features, dtype=np.float32)
                        label_arr = np.array(batch_labels, dtype=np.float32)
                        np.save(temp_dir / f'features_batch_{batch_num}.npy', feat_arr)
                        np.save(temp_dir / f'labels_batch_{batch_num}.npy', label_arr)
                        del feat_arr, label_arr
                        
                        total_samples += len(batch_features)
                        batch_num += 1
                        
                        processed_files.update(newly_processed)
                        import json
                        with open(checkpoint_file, 'w') as f:
                            json.dump({
                                'processed_files': list(processed_files),
                                'batch_num': batch_num,
                                'total_samples': total_samples
                            }, f)
                        
                        batch_features.clear()
                        batch_labels.clear()
                        newly_processed.clear()
                        import gc; gc.collect()
                    
                    if max_samples and total_samples >= max_samples:
                        pool.terminate()
                        break
                        
        except KeyboardInterrupt:
            print("\n\n   ⚠️ Interrupted! Saving progress...")
            interrupted = True
        
        if batch_features:
            feat_arr = np.array(batch_features, dtype=np.float32)
            label_arr = np.array(batch_labels, dtype=np.float32)
            np.save(temp_dir / f'features_batch_{batch_num}.npy', feat_arr)
            np.save(temp_dir / f'labels_batch_{batch_num}.npy', label_arr)
            del feat_arr, label_arr
            total_samples += len(batch_features)
            batch_num += 1
            
            processed_files.update(newly_processed)
            import json
            with open(checkpoint_file, 'w') as f:
                json.dump({
                    'processed_files': list(processed_files),
                    'batch_num': batch_num,
                    'total_samples': total_samples
                }, f)
            batch_features.clear()
            batch_labels.clear()
        
        pbar.close()
        
        if skipped > 0:
            print(f"   ⚠️ Skipped {skipped} files due to errors/timeouts")
        
        if interrupted:
            print(f"   💾 Progress saved: {len(processed_files)} files, {total_samples:,} samples")
            print(f"   Run again to resume from checkpoint.")
            raise KeyboardInterrupt
    
    if total_samples == 0:
        print("   ⚠️ No valid samples extracted!")
        return {'samples_extracted': 0}
    
    # Create manifest
    print(f"   Creating manifest for {batch_num} batches ({total_samples:,} samples)...")
    
    n_val_batches = max(1, batch_num // 10)
    val_batch_set = set(range(batch_num - n_val_batches, batch_num))
    
    manifest = {
        'dataset': 'slakh',
        'total_samples': total_samples,
        'batch_count': batch_num,
        'sample_rate': sr,
        'feature_shape': [128, 128],
        'num_classes': 12,
        'batches': {},
        'estimated_multi_label_ratio': 0.40,
    }
    
    slakh_batches_dir = output_path / 'slakh_batches'
    slakh_batches_dir.mkdir(exist_ok=True)
    
    train_samples = 0
    val_samples = 0
    
    for i in range(batch_num):
        src_feat = temp_dir / f'features_batch_{i}.npy'
        if src_feat.exists():
            feat_data = np.load(src_feat)
            n_samples = len(feat_data)
            del feat_data
        else:
            n_samples = 0
        
        split = 'val' if i in val_batch_set else 'train'
        if split == 'train':
            train_samples += n_samples
        else:
            val_samples += n_samples
            
        manifest['batches'][i] = {
            'features_file': f'slakh_batches/features_batch_{i}.npy',
            'labels_file': f'slakh_batches/labels_batch_{i}.npy',
            'samples': n_samples,
            'split': split,
        }
    
    manifest['train_samples'] = train_samples
    manifest['val_samples'] = val_samples
    
    manifest_path = output_path / 'slakh_manifest.json'
    import json
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Move batch files
    import shutil
    for i in range(batch_num):
        src_feat = temp_dir / f'features_batch_{i}.npy'
        src_label = temp_dir / f'labels_batch_{i}.npy'
        if src_feat.exists():
            shutil.move(str(src_feat), str(slakh_batches_dir / f'features_batch_{i}.npy'))
        if src_label.exists():
            shutil.move(str(src_label), str(slakh_batches_dir / f'labels_batch_{i}.npy'))
    
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    print(f"   ✅ Extracted {total_samples:,} samples across {batch_num} batches")
    print(f"      Train batches: {batch_num - n_val_batches}, Val batches: {n_val_batches}")
    print(f"      Train samples: ~{train_samples:,}, Val samples: ~{val_samples:,}")
    print(f"      Manifest: {manifest_path}")
    
    return {
        'samples_extracted': total_samples,
        'train_samples': train_samples,
        'val_samples': val_samples,
        'batch_count': batch_num,
        'manifest_path': str(manifest_path),
    }


def extract_multilabel_from_idmt(
    idmt_path: Path,
    output_path: Path,
    feature_cache_dir: Optional[Path] = None,
    max_samples: Optional[int] = None,
    sr: int = 22050,
) -> Dict[str, Any]:
    """
    Extract multi-label training data from IDMT-SMT-Drums dataset.
    IDMT has annotation files with drum event timings.
    """
    print(f"\n📦 Extracting from IDMT-SMT-Drums: {idmt_path}")
    
    output_path.mkdir(parents=True, exist_ok=True)
    train_dir = output_path / 'train'
    val_dir = output_path / 'val'
    train_dir.mkdir(exist_ok=True)
    val_dir.mkdir(exist_ok=True)
    
    # IDMT structure varies - look for MIDI + audio pairs
    pairs = []
    for midi_file in idmt_path.rglob('*.mid'):
        audio_file = midi_file.with_suffix('.wav')
        if not audio_file.exists():
            audio_file = midi_file.parent.parent / 'audio' / (midi_file.stem + '.wav')
        if audio_file.exists():
            pairs.append((midi_file, audio_file))
    for midi_file in idmt_path.rglob('*.midi'):
        audio_file = midi_file.with_suffix('.wav')
        if audio_file.exists():
            pairs.append((midi_file, audio_file))
    
    print(f"   Found {len(pairs)} MIDI+audio pairs")
    
    if not pairs:
        print("   ⚠️ No extractable data found (MIDI with audio required)")
        return {'samples_extracted': 0}
    
    all_features = []
    all_labels = []
    audio_cache = {}
    
    print(f"   Extracting spectrograms from {len(pairs)} files...")
    for midi_file, audio_file in tqdm(pairs, desc="   Processing"):
        windows = parse_midi_for_drums(midi_file)
        if not windows:
            continue
        
        audio_key = str(audio_file)
        if audio_key not in audio_cache:
            audio = load_audio_file(audio_file, sr=sr)
            if audio is None:
                continue
            audio_cache[audio_key] = audio
            if len(audio_cache) > 100:
                oldest_key = next(iter(audio_cache))
                del audio_cache[oldest_key]
        else:
            audio = audio_cache[audio_key]
        
        for w in windows:
            mel_spec = extract_mel_spectrogram(audio, sr, w.start_time)
            if mel_spec is not None:
                all_features.append(mel_spec)
                all_labels.append(w.label_vector)
        
        if max_samples and len(all_labels) >= max_samples:
            break
    
    if not all_labels:
        print("   ⚠️ No extractable data found (MIDI with audio required)")
        return {'samples_extracted': 0}
    
    features_array = np.array(all_features, dtype=np.float32)
    labels_array = np.array(all_labels, dtype=np.float32)
    
    n_samples = len(labels_array)
    n_val = int(n_samples * 0.1)
    np.random.seed(42)
    indices = np.random.permutation(n_samples)
    val_indices = indices[:n_val]
    train_indices = indices[n_val:]
    
    np.save(train_dir / 'idmt_features.npy', features_array[train_indices])
    np.save(train_dir / 'idmt_labels.npy', labels_array[train_indices])
    np.save(val_dir / 'idmt_features.npy', features_array[val_indices])
    np.save(val_dir / 'idmt_labels.npy', labels_array[val_indices])
    
    multi_label_count = np.sum(labels_array.sum(axis=1) > 1)
    print(f"   ✅ Extracted {n_samples} samples with spectrograms")
    print(f"      Train: {len(train_indices)}, Val: {len(val_indices)}")
    print(f"      Multi-label samples: {multi_label_count} ({100*multi_label_count/n_samples:.1f}%)")
    print(f"      Feature shape: {features_array.shape}")
    
    return {
        'samples_extracted': n_samples, 
        'train_samples': len(train_indices), 
        'val_samples': len(val_indices), 
        'multi_label_ratio': multi_label_count / n_samples,
        'feature_shape': features_array.shape,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract multi-label data from MIDI datasets")
    parser.add_argument('--sources', nargs='+', default=['egmd'],
                        choices=['egmd', 'groove_midi', 'enst', 'slakh', 'idmt', 'all'],
                        help='Datasets to process')
    parser.add_argument('--egmd-path', type=str, default='D:/data/raw/egmd',
                        help='Path to E-GMD dataset')
    parser.add_argument('--groove-path', type=str, default='D:/data/raw/groove_midi',
                        help='Path to Groove MIDI dataset')
    parser.add_argument('--enst-path', type=str, default='D:/data/raw/ENST-Drums',
                        help='Path to ENST-Drums dataset')
    parser.add_argument('--slakh-path', type=str, default='D:/data/raw/slakh2100',
                        help='Path to Slakh2100 dataset')
    parser.add_argument('--idmt-path', type=str, default='D:/data/raw/idmt_smt_drums_v2',
                        help='Path to IDMT-SMT-Drums dataset')
    parser.add_argument('--output', type=str, default='F:/datasets/multilabel_real',
                        help='Output directory for extracted data')
    parser.add_argument('--feature-cache-dir', type=str, default=None,
                        help='Feature cache directory')
    parser.add_argument('--mode', choices=['analyze', 'extract'], default='analyze',
                        help='Mode: analyze (show stats) or extract (create dataset)')
    parser.add_argument('--merge-window-ms', type=float, default=30.0,
                        help='Window in ms to consider hits as simultaneous')
    parser.add_argument('--max-samples', type=int, default=None,
                        help='Maximum samples to extract (for testing)')
    parser.add_argument('--num-workers', type=int, default=0,
                        help='Number of parallel workers (0 = auto, uses cpu_count - 2)')
    
    args = parser.parse_args()
    
    # mido is required and we exit at import time if missing
    
    sources = args.sources
    if 'all' in sources:
        sources = ['egmd', 'groove_midi', 'slakh', 'idmt']
    
    print("=" * 70)
    print("Multi-Label Data Extraction from MIDI Datasets")
    print("=" * 70)
    
    if args.mode == 'analyze':
        # Analyze each source
        for source in sources:
            print(f"\n📊 Analyzing: {source}")
            print("-" * 50)
            
            if source == 'egmd':
                path = Path(args.egmd_path)
                if path.exists():
                    stats = analyze_egmd(path)
                    print(f"   Drummers: {len(stats['drummers'])}")
                    print(f"   Sessions: {len(stats['sessions'])}")
                    print(f"   MIDI files: {stats['total_midi_files']:,}")
                    print(f"   Audio files: {stats['total_audio_files']:,}")
                    if stats['multi_label_windows'] > 0:
                        total = stats['multi_label_windows'] + stats['single_label_windows']
                        ratio = stats['multi_label_windows'] / total
                        print(f"   Multi-label windows: {stats['multi_label_windows']:,} ({100*ratio:.1f}%)")
                        print(f"   Top combos:")
                        sorted_combos = sorted(stats['combo_distribution'].items(), 
                                               key=lambda x: x[1], reverse=True)[:5]
                        for combo, count in sorted_combos:
                            print(f"      {combo}: {count}")
                else:
                    print(f"   ⚠️ Path not found: {path}")
            
            elif source == 'groove_midi':
                path = Path(args.groove_path)
                if path.exists():
                    stats = analyze_groove_midi(path)
                    print(f"   MIDI files: {stats['total_midi_files']:,}")
                    print(f"   Audio files: {stats['total_audio_files']:,}")
                    if stats['multi_label_windows'] > 0:
                        total = stats['multi_label_windows'] + stats['single_label_windows']
                        ratio = stats['multi_label_windows'] / total
                        print(f"   Multi-label windows (sample): {stats['multi_label_windows']:,} ({100*ratio:.1f}%)")
                else:
                    print(f"   ⚠️ Path not found: {path}")
            
            elif source == 'enst':
                path = Path(args.enst_path)
                if path.exists():
                    stats = analyze_enst(path)
                    print(f"   Drummers: {len(stats['drummers'])}")
                    print(f"   Audio files: {stats['total_audio_files']:,}")
                    print(f"   Annotation files: {stats['total_annotation_files']:,}")
                    print(f"   Recording types: {stats['recording_types']}")
                else:
                    print(f"   ⚠️ Path not found: {path}")
            
            elif source == 'slakh':
                path = Path(args.slakh_path)
                if path.exists():
                    stats = analyze_slakh(path)
                    print(f"   Total tracks: {stats['total_tracks']:,}")
                    print(f"   Tracks with drums: {stats['tracks_with_drums']:,}")
                else:
                    print(f"   ⚠️ Path not found: {path}")
    
    elif args.mode == 'extract':
        output_path = Path(args.output)
        feature_cache = Path(args.feature_cache_dir) if args.feature_cache_dir else None
        
        total_stats = {'total_samples': 0, 'total_train': 0, 'total_val': 0}
        
        for source in sources:
            if source == 'egmd':
                path = Path(args.egmd_path)
                if path.exists():
                    stats = extract_multilabel_from_egmd(
                        path, output_path / 'egmd',
                        feature_cache, args.max_samples,
                        num_workers=args.num_workers
                    )
                    total_stats['total_samples'] += stats.get('samples_extracted', 0)
                    total_stats['total_train'] += stats.get('train_samples', 0)
                    total_stats['total_val'] += stats.get('val_samples', 0)
                else:
                    print(f"\n⚠️ E-GMD path not found: {path}")
            
            elif source == 'groove_midi':
                path = Path(args.groove_path)
                if path.exists():
                    stats = extract_multilabel_from_groove_midi(
                        path, output_path / 'groove_midi',
                        feature_cache, args.max_samples,
                        num_workers=args.num_workers
                    )
                    total_stats['total_samples'] += stats.get('samples_extracted', 0)
                    total_stats['total_train'] += stats.get('train_samples', 0)
                    total_stats['total_val'] += stats.get('val_samples', 0)
                else:
                    print(f"\n⚠️ Groove MIDI path not found: {path}")
            
            elif source == 'slakh':
                path = Path(args.slakh_path)
                if path.exists():
                    stats = extract_multilabel_from_slakh(
                        path, output_path / 'slakh',
                        feature_cache, args.max_samples
                    )
                    total_stats['total_samples'] += stats.get('samples_extracted', 0)
                    total_stats['total_train'] += stats.get('train_samples', 0)
                    total_stats['total_val'] += stats.get('val_samples', 0)
                else:
                    print(f"\n⚠️ Slakh path not found: {path}")
            
            elif source == 'idmt':
                path = Path(args.idmt_path)
                if path.exists():
                    stats = extract_multilabel_from_idmt(
                        path, output_path / 'idmt',
                        feature_cache, args.max_samples
                    )
                    total_stats['total_samples'] += stats.get('samples_extracted', 0)
                    total_stats['total_train'] += stats.get('train_samples', 0)
                    total_stats['total_val'] += stats.get('val_samples', 0)
                else:
                    print(f"\n⚠️ IDMT path not found: {path}")
        
        print("\n" + "=" * 70)
        print("📊 EXTRACTION SUMMARY")
        print("=" * 70)
        print(f"   Total samples extracted: {total_stats['total_samples']:,}")
        print(f"   Total train: {total_stats['total_train']:,}")
        print(f"   Total val: {total_stats['total_val']:,}")
    
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == '__main__':
    main()
