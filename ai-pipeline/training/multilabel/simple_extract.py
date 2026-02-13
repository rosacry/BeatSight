#!/usr/bin/env python3
"""
Simple sequential spectrogram extraction.
Groups by file and processes sequentially for reliability.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from tqdm import tqdm

try:
    import librosa
except ImportError:
    print("Error: librosa not installed")
    sys.exit(1)


# Audio processing parameters
SR = 44100
N_MELS = 128
TARGET_WIDTH = 128
WINDOW_MS = 100.0

# Pre-compute mel filterbank
MEL_FB = librosa.filters.mel(sr=SR, n_fft=2048, n_mels=N_MELS, fmax=8000)


def extract_spectrogram(audio: np.ndarray, onset_time: float) -> np.ndarray:
    """Extract spectrogram at onset time."""
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
    mel_db = mel_db * 2 - 1
    
    return mel_db.astype(np.float32)


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
        
        # Process files sequentially (reliable)
        all_results = []
        failed_files = 0
        
        for audio_path, samples in tqdm(file_samples.items(), desc=f"Extracting {split}"):
            try:
                audio, _ = librosa.load(audio_path, sr=SR, mono=True)
                
                for idx, time, label in samples:
                    try:
                        spec = extract_spectrogram(audio, time)
                        all_results.append((idx, spec, label))
                    except Exception:
                        pass
            except Exception:
                failed_files += 1
        
        if failed_files > 0:
            print(f"  Warning: {failed_files} files failed to load")
        
        # Sort by original index
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
