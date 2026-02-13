#!/usr/bin/env python3
"""
Pre-extract spectrograms from MIDI multi-label dataset.

This extracts all spectrograms upfront for faster training.
OPTIMIZED: Groups samples by audio file to minimize I/O.

Output:
    F:/datasets/multilabel_cached/train/features.npy  (N, 128, 128)
    F:/datasets/multilabel_cached/train/labels.npy    (N, 12)
    F:/datasets/multilabel_cached/val/features.npy
    F:/datasets/multilabel_cached/val/labels.npy

Usage:
    python -m training.multilabel.preextract_spectrograms
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from tqdm import tqdm

# Import librosa for audio processing
try:
    import librosa
except ImportError:
    print("Error: librosa not installed. Install with: pip install librosa")
    sys.exit(1)


# Audio processing parameters
SR = 44100
N_MELS = 128
TARGET_WIDTH = 128
WINDOW_MS = 100.0

# Pre-compute mel filterbank
MEL_FB = librosa.filters.mel(sr=SR, n_fft=2048, n_mels=N_MELS, fmax=8000)


def extract_spectrogram_from_audio(
    audio: np.ndarray,
    onset_time: float,
) -> Optional[np.ndarray]:
    """Extract spectrogram at onset time from pre-loaded audio."""
    try:
        window_samples = int(SR * WINDOW_MS / 1000.0)
        center_sample = int(onset_time * SR)
        
        half_window = window_samples // 2
        start = max(0, center_sample - half_window)
        end = min(len(audio), center_sample + half_window)
        
        segment = audio[start:end]
        
        if len(segment) < window_samples:
            pad_left = (window_samples - len(segment)) // 2
            pad_right = window_samples - len(segment) - pad_left
            segment = np.pad(segment, (pad_left, pad_right), mode='constant')
        
        hop_length = max(1, len(segment) // TARGET_WIDTH)
        
        stft = np.abs(librosa.stft(segment, n_fft=2048, hop_length=hop_length))
        mel_spec = np.dot(MEL_FB, stft)
        mel_db = librosa.amplitude_to_db(mel_spec, ref=np.max)
        
        if mel_db.shape[1] < TARGET_WIDTH:
            pad_width = TARGET_WIDTH - mel_db.shape[1]
            mel_db = np.pad(mel_db, ((0, 0), (0, pad_width)), mode='constant')
        elif mel_db.shape[1] > TARGET_WIDTH:
            mel_db = mel_db[:, :TARGET_WIDTH]
        
        mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
        
        return mel_db.astype(np.float32)
    except Exception:
        return None


def process_audio_file(
    audio_path: str,
    samples: List[Tuple[int, float, np.ndarray]],  # (index, time, label)
) -> List[Tuple[int, np.ndarray, np.ndarray]]:
    """Process all samples from a single audio file."""
    results = []
    
    try:
        audio, _ = librosa.load(audio_path, sr=SR, mono=True)
        
        for idx, time, label in samples:
            spec = extract_spectrogram_from_audio(audio, time)
            if spec is not None:
                results.append((idx, spec, label))
    except Exception:
        pass
    
    return results


def load_source_data(
    metadata_dir: Path,
    source: str,
    split: str,
    drive_remap: Dict[str, str],
) -> Tuple[List[str], List[float], np.ndarray]:
    """Load data from a source."""
    source_dir = metadata_dir / source / split
    
    label_files = list(source_dir.glob('*labels*.npy'))
    meta_files = list(source_dir.glob('*.json'))
    
    if not label_files or not meta_files:
        return [], [], np.array([])
    
    labels = np.load(label_files[0])
    with open(meta_files[0]) as f:
        metadata = json.load(f)
    
    audio_paths = metadata.get('audio_paths', [])
    times = metadata.get('times', [])
    
    # Remap drive letters
    for i in range(len(audio_paths)):
        path = audio_paths[i]
        for old, new in drive_remap.items():
            path = path.replace(old, new)
        audio_paths[i] = path
    
    return audio_paths, times, labels


def main():
    metadata_dir = Path('F:/datasets/multilabel_real')
    output_dir = Path('F:/datasets/multilabel_cached')
    sources = ['groove_midi', 'egmd']
    drive_remap = {'D:': 'F:'}
    num_workers = 8  # ThreadPool can use more workers for I/O
    
    for split in ['train', 'val']:
        print(f"\n{'='*60}")
        print(f"Processing {split} split...")
        print('='*60)
        
        # Load all data
        all_paths = []
        all_times = []
        all_labels = []
        
        for source in sources:
            paths, times, labels = load_source_data(
                metadata_dir, source, split, drive_remap
            )
            if len(paths) > 0:
                print(f"  {source}: {len(paths):,} samples")
                all_paths.extend(paths)
                all_times.extend(times)
                all_labels.append(labels)
        
        if not all_paths:
            print(f"  No data found for {split}")
            continue
        
        all_labels = np.concatenate(all_labels, axis=0)
        print(f"  Total: {len(all_paths):,} samples")
        
        # Group samples by audio file
        file_samples: Dict[str, List[Tuple[int, float, np.ndarray]]] = defaultdict(list)
        for i, (path, time, label) in enumerate(zip(all_paths, all_times, all_labels)):
            file_samples[path].append((i, time, label))
        
        print(f"  Unique audio files: {len(file_samples):,}")
        avg_per_file = len(all_paths) / len(file_samples)
        print(f"  Avg samples per file: {avg_per_file:.1f}")
        
        # Create output directory
        split_dir = output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        
        # Process files using ThreadPoolExecutor (I/O bound)
        all_results = []
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(process_audio_file, path, samples): path
                for path, samples in file_samples.items()
            }
            
            for future in tqdm(as_completed(futures), total=len(futures), 
                               desc=f"Extracting {split}"):
                results = future.result()
                all_results.extend(results)
        
        # Sort by original index and extract features/labels
        all_results.sort(key=lambda x: x[0])
        
        features_list = [r[1] for r in all_results]
        labels_list = [r[2] for r in all_results]
        
        # Convert to arrays
        features_array = np.array(features_list, dtype=np.float32)
        labels_array = np.array(labels_list, dtype=np.float32)
        
        print(f"\n  Extracted: {len(features_array):,} samples")
        print(f"  Features shape: {features_array.shape}")
        print(f"  Labels shape: {labels_array.shape}")
        
        # Multi-label stats
        multilabel = (labels_array.sum(axis=1) > 1).sum()
        print(f"  Multi-label: {multilabel:,} ({100*multilabel/len(labels_array):.1f}%)")
        
        # Save
        np.save(split_dir / 'features.npy', features_array)
        np.save(split_dir / 'labels.npy', labels_array)
        
        print(f"  Saved to {split_dir}")
        
        # Memory stats
        mem_gb = features_array.nbytes / 1024**3
        print(f"  Memory: {mem_gb:.2f} GB")
        
        # Free memory
        del features_array, labels_array, all_results
        import gc; gc.collect()
    
    print("\n" + "="*60)
    print("Extraction complete!")
    print("="*60)


if __name__ == '__main__':
    main()
