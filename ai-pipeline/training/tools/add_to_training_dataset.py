#!/usr/bin/env python3
"""
Add synthesized drum samples to the training dataset.

This script integrates synthesized samples (from synthesize_drum_samples.py)
into the existing training dataset, updating labels and creating a merged
dataset ready for training.

It handles:
1. Computing mel spectrograms for new samples
2. Adding to the feature cache (if using cached training)
3. Merging labels with existing dataset
4. Balancing additions to avoid overwhelming existing data

Usage:
    # Add synthesized samples to dataset
    python add_to_training_dataset.py \
        --synthesized-dir ./synthesized_drums \
        --dataset F:/datasets/prod_v5_fixed_20251212 \
        --feature-cache F:/feature_cache \
        --output F:/datasets/prod_v5_with_synth

    # Preview only (show what would be added)
    python add_to_training_dataset.py \
        --synthesized-dir ./synthesized_drums \
        --dataset F:/datasets/prod_v5_fixed_20251212 \
        --preview-only
"""

import argparse
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

import numpy as np

try:
    import torch
    import torchaudio
    import torchaudio.transforms as T
except ImportError:
    print("ERROR: torch/torchaudio not installed")
    sys.exit(1)

try:
    import soundfile as sf
except ImportError:
    sf = None


# Feature extraction settings (must match train_classifier.py)
FEATURE_CONFIG = {
    "sample_rate": 44100,
    "n_fft": 2048,
    "hop_length": 512,
    "n_mels": 128,
    "fmax": 8000,
    "target_frames": 128,
}


def load_components(dataset_path: Path) -> Dict:
    """Load components.json from dataset."""
    components_file = dataset_path / "components.json"
    if not components_file.exists():
        raise FileNotFoundError(f"components.json not found in {dataset_path}")
    
    with open(components_file) as f:
        return json.load(f)


def load_existing_labels(dataset_path: Path, split: str = "train") -> Tuple[np.ndarray, np.ndarray]:
    """Load existing labels from numpy files."""
    labels_npy = dataset_path / split / "labels.npy"
    ids_npy = dataset_path / split / "ids.npy"
    
    if not labels_npy.exists():
        raise FileNotFoundError(f"Labels not found: {labels_npy}")
    
    labels = np.load(labels_npy)
    ids = np.load(ids_npy)
    
    return ids, labels


def compute_mel_spectrogram(
    audio_path: Path,
    sr: int = 44100,
    n_fft: int = 2048,
    hop_length: int = 512,
    n_mels: int = 128,
    fmax: int = 8000,
    target_frames: int = 128,
) -> Optional[torch.Tensor]:
    """Compute mel spectrogram for an audio file."""
    try:
        waveform, file_sr = torchaudio.load(audio_path)
        
        # Resample if needed
        if file_sr != sr:
            resampler = T.Resample(file_sr, sr)
            waveform = resampler(waveform)
        
        # Convert to mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        
        # Compute mel spectrogram
        mel_transform = T.MelSpectrogram(
            sample_rate=sr,
            n_fft=n_fft,
            hop_length=hop_length,
            n_mels=n_mels,
            f_max=fmax,
        )
        mel_spec = mel_transform(waveform)
        
        # Convert to dB
        db_transform = T.AmplitudeToDB(stype="power")
        mel_db = db_transform(mel_spec)
        
        # Normalize
        mel_db = (mel_db - mel_db.mean()) / (mel_db.std() + 1e-8)
        
        # Pad or trim to target frames
        current_frames = mel_db.shape[-1]
        if current_frames < target_frames:
            pad_size = target_frames - current_frames
            mel_db = torch.nn.functional.pad(mel_db, (0, pad_size))
        elif current_frames > target_frames:
            mel_db = mel_db[..., :target_frames]
        
        return mel_db.squeeze(0)  # Remove channel dim: [n_mels, target_frames]
        
    except Exception as e:
        print(f"WARNING: Failed to process {audio_path}: {e}")
        return None


def scan_synthesized_dir(synth_dir: Path) -> Tuple[List[Dict], Counter]:
    """Scan synthesized directory and count samples per class."""
    samples = []
    counts = Counter()
    
    # Load synthesis labels if available
    labels_file = synth_dir / "synthesis_labels.json"
    if labels_file.exists():
        with open(labels_file) as f:
            labels_data = json.load(f)
        
        for item in labels_data:
            filepath = synth_dir / item["file"]
            if filepath.exists():
                samples.append({
                    "path": filepath,
                    "label": item["label"],
                    "velocity": item.get("velocity", 100),
                    "source": "synthesized",
                })
                counts[item["label"]] += 1
    else:
        # Scan directory structure
        for class_dir in synth_dir.iterdir():
            if not class_dir.is_dir():
                continue
            
            class_name = class_dir.name
            for audio_file in class_dir.glob("*.wav"):
                samples.append({
                    "path": audio_file,
                    "label": class_name,
                    "velocity": 100,
                    "source": "synthesized",
                })
                counts[class_name] += 1
    
    return samples, counts


def add_to_cache(
    samples: List[Dict],
    cache_dir: Path,
    component_index: Dict[str, int],
    start_index: int = 0,
    verbose: bool = True,
) -> Tuple[List[str], List[int], int]:
    """
    Compute features and add to cache.
    
    Returns:
        Tuple of (new_ids, new_labels, num_processed)
    """
    new_ids = []
    new_labels = []
    
    # Find existing shards
    existing_shards = list(cache_dir.glob("shard_*.pt"))
    next_shard_idx = len(existing_shards)
    
    # Process in batches for new shard
    batch_size = 10000  # Samples per shard
    current_batch = []
    current_batch_ids = []
    current_batch_labels = []
    
    processed = 0
    failed = 0
    
    for i, sample in enumerate(samples):
        if verbose and (i + 1) % 500 == 0:
            print(f"  Processing {i+1}/{len(samples)} ({processed} cached, {failed} failed)")
        
        # Compute features
        features = compute_mel_spectrogram(
            sample["path"],
            **FEATURE_CONFIG
        )
        
        if features is None:
            failed += 1
            continue
        
        # Generate unique ID
        sample_id = f"synth_{hashlib.md5(str(sample['path']).encode()).hexdigest()[:16]}"
        
        # Get label index
        label_name = sample["label"]
        if label_name not in component_index:
            print(f"WARNING: Unknown label {label_name}")
            continue
        
        label_idx = component_index[label_name]
        
        current_batch.append(features)
        current_batch_ids.append(sample_id)
        current_batch_labels.append(label_idx)
        
        new_ids.append(sample_id)
        new_labels.append(label_idx)
        processed += 1
        
        # Save shard when batch is full
        if len(current_batch) >= batch_size:
            shard_path = cache_dir / f"shard_{next_shard_idx:04d}.pt"
            torch.save({
                "features": torch.stack(current_batch),
                "ids": current_batch_ids,
                "labels": torch.tensor(current_batch_labels),
            }, shard_path)
            
            if verbose:
                print(f"  Saved shard {next_shard_idx} ({len(current_batch)} samples)")
            
            next_shard_idx += 1
            current_batch = []
            current_batch_ids = []
            current_batch_labels = []
    
    # Save remaining samples
    if current_batch:
        shard_path = cache_dir / f"shard_{next_shard_idx:04d}.pt"
        torch.save({
            "features": torch.stack(current_batch),
            "ids": current_batch_ids,
            "labels": torch.tensor(current_batch_labels),
        }, shard_path)
        
        if verbose:
            print(f"  Saved shard {next_shard_idx} ({len(current_batch)} samples)")
    
    print(f"\nFeature extraction complete: {processed} cached, {failed} failed")
    
    return new_ids, new_labels, processed


def merge_labels(
    existing_ids: np.ndarray,
    existing_labels: np.ndarray,
    new_ids: List[str],
    new_labels: List[int],
) -> Tuple[np.ndarray, np.ndarray]:
    """Merge existing and new labels."""
    
    # Convert new to numpy
    new_ids_arr = np.array(new_ids, dtype=existing_ids.dtype)
    new_labels_arr = np.array(new_labels, dtype=existing_labels.dtype)
    
    # Concatenate
    merged_ids = np.concatenate([existing_ids, new_ids_arr])
    merged_labels = np.concatenate([existing_labels, new_labels_arr])
    
    return merged_ids, merged_labels


def update_cache_index(cache_dir: Path, new_ids: List[str], new_labels: List[int]):
    """Update the cache index JSON file."""
    index_file = cache_dir / "index.json"
    
    # Load existing index
    if index_file.exists():
        with open(index_file) as f:
            index = json.load(f)
    else:
        index = {}
    
    # Add new entries
    for sample_id, label in zip(new_ids, new_labels):
        # Index format: {id: {"shard": X, "idx": Y, "label": Z}}
        # For simplicity, just mark as added (actual lookup happens in shard files)
        index[sample_id] = {"label": label, "source": "synthesized"}
    
    # Save updated index
    with open(index_file, 'w') as f:
        json.dump(index, f)
    
    print(f"Updated cache index: {len(index)} total entries")


def main():
    parser = argparse.ArgumentParser(
        description="Add synthesized drum samples to training dataset",
    )
    
    parser.add_argument("--synthesized-dir", type=Path, required=True,
                        help="Directory containing synthesized samples")
    parser.add_argument("--dataset", type=Path, required=True,
                        help="Existing dataset directory")
    parser.add_argument("--feature-cache", type=Path, default=None,
                        help="Feature cache directory (optional)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output directory for merged dataset (default: modify in-place)")
    parser.add_argument("--preview-only", action="store_true",
                        help="Only preview what would be added, don't modify")
    parser.add_argument("--max-per-class", type=int, default=None,
                        help="Maximum samples to add per class")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose output")
    
    args = parser.parse_args()
    
    # Validate paths
    if not args.synthesized_dir.exists():
        print(f"ERROR: Synthesized directory not found: {args.synthesized_dir}")
        sys.exit(1)
    
    if not args.dataset.exists():
        print(f"ERROR: Dataset not found: {args.dataset}")
        sys.exit(1)
    
    # Load components
    print("Loading dataset configuration...")
    components = load_components(args.dataset)
    component_index = components.get("component_index", {})
    class_names = components.get("components", [])
    
    print(f"Dataset has {len(class_names)} classes:")
    for name in class_names:
        print(f"  - {name}")
    
    # Scan synthesized samples
    print(f"\nScanning synthesized samples in {args.synthesized_dir}...")
    synth_samples, synth_counts = scan_synthesized_dir(args.synthesized_dir)
    
    print(f"\nSynthesized samples found:")
    for class_name, count in sorted(synth_counts.items(), key=lambda x: -x[1]):
        in_dataset = "✓" if class_name in component_index else "✗ NOT IN DATASET"
        print(f"  {class_name}: {count:,} {in_dataset}")
    
    # Load existing labels
    print(f"\nLoading existing dataset labels...")
    existing_ids, existing_labels = load_existing_labels(args.dataset, "train")
    
    existing_counts = Counter(existing_labels.tolist())
    print(f"Existing training samples: {len(existing_labels):,}")
    print(f"\nExisting class distribution:")
    for idx, name in enumerate(class_names):
        count = existing_counts.get(idx, 0)
        synth = synth_counts.get(name, 0)
        print(f"  {name}: {count:,} existing + {synth:,} synth = {count + synth:,}")
    
    if args.preview_only:
        print("\n[Preview only mode - no changes made]")
        return
    
    # Filter samples by max_per_class
    if args.max_per_class:
        filtered_samples = []
        class_added = Counter()
        for sample in synth_samples:
            if class_added[sample["label"]] < args.max_per_class:
                filtered_samples.append(sample)
                class_added[sample["label"]] += 1
        synth_samples = filtered_samples
        print(f"\nLimited to {args.max_per_class} per class: {len(synth_samples)} total")
    
    # Determine output directory
    if args.output:
        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)
        # Copy existing dataset
        print(f"\nCopying dataset to {output_dir}...")
        shutil.copytree(args.dataset, output_dir, dirs_exist_ok=True)
    else:
        output_dir = args.dataset
        print(f"\nModifying dataset in-place: {output_dir}")
    
    # Add to feature cache if provided
    if args.feature_cache:
        print(f"\nAdding features to cache: {args.feature_cache}")
        
        cache_dir = args.feature_cache
        if args.output:
            # Create new cache directory
            new_cache = args.output.parent / f"{args.output.name}_cache"
            shutil.copytree(cache_dir, new_cache, dirs_exist_ok=True)
            cache_dir = new_cache
        
        new_ids, new_labels, num_added = add_to_cache(
            synth_samples,
            cache_dir,
            component_index,
            start_index=len(existing_labels),
            verbose=not args.quiet,
        )
        
        # Update cache index
        update_cache_index(cache_dir, new_ids, new_labels)
    else:
        # Just collect IDs/labels without caching
        new_ids = []
        new_labels = []
        for sample in synth_samples:
            sample_id = f"synth_{hashlib.md5(str(sample['path']).encode()).hexdigest()[:16]}"
            if sample["label"] in component_index:
                new_ids.append(sample_id)
                new_labels.append(component_index[sample["label"]])
    
    # Merge labels
    print(f"\nMerging labels...")
    merged_ids, merged_labels = merge_labels(
        existing_ids, existing_labels, new_ids, new_labels
    )
    
    # Save merged labels
    train_dir = output_dir / "train"
    np.save(train_dir / "ids.npy", merged_ids)
    np.save(train_dir / "labels.npy", merged_labels)
    
    print(f"\nDataset updated:")
    print(f"  Previous samples: {len(existing_labels):,}")
    print(f"  Added samples: {len(new_labels):,}")
    print(f"  Total samples: {len(merged_labels):,}")
    
    # Print new distribution
    new_counts = Counter(merged_labels.tolist())
    print(f"\nNew class distribution:")
    for idx, name in enumerate(class_names):
        old = existing_counts.get(idx, 0)
        new = new_counts.get(idx, 0)
        added = new - old
        print(f"  {name}: {new:,} ({'+' if added >= 0 else ''}{added:,})")
    
    print(f"\n✅ Dataset updated: {output_dir}")
    if args.feature_cache and args.output:
        print(f"✅ Feature cache updated: {cache_dir}")


if __name__ == "__main__":
    main()
