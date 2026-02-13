#!/usr/bin/env python3
"""
Merge STAR Drums extracted samples with existing training dataset.

This script:
1. Computes mel spectrograms for extracted STAR Drums samples
2. Adds them to the feature cache
3. Merges labels with existing dataset

Usage:
    python merge_star_drums.py \
        --star-drums-dir F:/datasets/star_drums_extracted \
        --dataset F:/datasets/prod_v5_fixed_20251212 \
        --feature-cache F:/feature_cache \
        --output F:/datasets/prod_v5_with_star_drums
"""

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import hashlib

import numpy as np

try:
    import torch
    import torchaudio
    import torchaudio.transforms as T
except ImportError:
    print("ERROR: torch/torchaudio not installed")
    sys.exit(1)


# Feature extraction settings (must match train_classifier.py)
FEATURE_CONFIG = {
    "sample_rate": 44100,
    "n_fft": 2048,
    "hop_length": 512,
    "n_mels": 128,
    "fmax": 8000,
    "target_frames": 128,
}


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


def scan_star_drums_dir(star_dir: Path) -> Tuple[List[Dict], Counter]:
    """Scan STAR Drums extracted directory."""
    samples = []
    counts = Counter()
    
    for class_dir in star_dir.iterdir():
        if not class_dir.is_dir():
            continue
        
        class_name = class_dir.name
        for audio_file in class_dir.glob("*.wav"):
            samples.append({
                "path": audio_file,
                "label": class_name,
                "source": "star_drums",
            })
            counts[class_name] += 1
    
    return samples, counts


def load_components(dataset_path: Path) -> Dict:
    """Load components.json from dataset."""
    components_file = dataset_path / "components.json"
    if not components_file.exists():
        raise FileNotFoundError(f"components.json not found in {dataset_path}")
    
    with open(components_file) as f:
        return json.load(f)


def load_existing_data(dataset_path: Path, split: str = "train") -> Tuple[np.ndarray, np.ndarray]:
    """Load existing labels and ids from numpy files."""
    split_dir = dataset_path / split
    
    # Try different naming conventions
    labels_files = [
        (split_dir / "labels.npy", split_dir / "ids.npy"),  # Standard
        (split_dir / f"{split}_labels_labels.npy", split_dir / f"{split}_labels_files.npy"),  # Alternative
    ]
    
    for labels_npy, ids_npy in labels_files:
        if labels_npy.exists() and ids_npy.exists():
            labels = np.load(labels_npy)
            ids = np.load(ids_npy)
            print(f"  Loaded from: {labels_npy.name}, {ids_npy.name}")
            return ids, labels
    
    # Fallback: try to list available files
    available = list(split_dir.glob("*.npy"))
    raise FileNotFoundError(f"Labels not found in {split_dir}. Available: {[f.name for f in available]}")


def main():
    parser = argparse.ArgumentParser(description='Merge STAR Drums with training dataset')
    parser.add_argument('--star-drums-dir', type=str, required=True,
                        help='Path to extracted STAR Drums samples')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to existing dataset')
    parser.add_argument('--feature-cache', type=str, required=True,
                        help='Path to feature cache directory')
    parser.add_argument('--output', type=str, required=True,
                        help='Output directory for merged dataset')
    parser.add_argument('--preview', action='store_true',
                        help='Preview only, do not merge')
    parser.add_argument('--max-per-class', type=int, default=None,
                        help='Maximum samples per class to add')
    args = parser.parse_args()
    
    star_dir = Path(args.star_drums_dir)
    dataset_dir = Path(args.dataset)
    cache_dir = Path(args.feature_cache)
    output_dir = Path(args.output)
    
    print("=" * 60)
    print(" STAR Drums Dataset Merger")
    print("=" * 60)
    print(f"STAR Drums: {star_dir}")
    print(f"Dataset: {dataset_dir}")
    print(f"Cache: {cache_dir}")
    print(f"Output: {output_dir}")
    print()
    
    # 1. Load existing dataset info
    print("Loading existing dataset...")
    components = load_components(dataset_dir)
    component_to_idx = components["component_index"]  # Key is "component_index"
    
    print(f"Classes: {list(set(component_to_idx.values()))} ({len(set(component_to_idx.values()))} unique)")
    
    # 2. Scan STAR Drums samples
    print("\nScanning STAR Drums extracted samples...")
    samples, star_counts = scan_star_drums_dir(star_dir)
    
    print(f"\nSTAR Drums samples found:")
    for cls in sorted(star_counts.keys(), key=lambda x: -star_counts[x]):
        count = star_counts[cls]
        if cls in component_to_idx:
            print(f"  {cls:15} {count:>8,} samples -> class index {component_to_idx[cls]}")
        else:
            print(f"  {cls:15} {count:>8,} samples -> [SKIPPED - not in taxonomy]")
    
    # Filter to only valid classes
    valid_samples = [s for s in samples if s["label"] in component_to_idx]
    print(f"\nValid samples: {len(valid_samples):,}")
    
    if args.preview:
        print("\n[Preview mode - no merge performed]")
        return
    
    # 3. Load existing training data
    print("\nLoading existing training labels...")
    existing_ids, existing_labels = load_existing_data(dataset_dir, "train")
    print(f"Existing training samples: {len(existing_labels):,}")
    
    # Count existing per class
    existing_counts = Counter(existing_labels)
    print("\nExisting class distribution:")
    for idx in sorted(existing_counts.keys()):
        for cls, cidx in component_to_idx.items():
            if cidx == idx:
                count = existing_counts[idx]
                print(f"  {cls:15} {count:>10,}")
                break
    
    # 4. Compute features and prepare new samples
    print("\n" + "=" * 60)
    print(" Computing mel spectrograms for STAR Drums")
    print("=" * 60)
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    new_ids = []
    new_labels = []
    processed = 0
    skipped = 0
    
    for i, sample in enumerate(valid_samples):
        if args.max_per_class:
            # Check if we've hit the limit for this class
            cls_idx = component_to_idx[sample["label"]]
            current_count = new_labels.count(cls_idx)
            if current_count >= args.max_per_class:
                continue
        
        # Generate unique ID
        audio_hash = hashlib.md5(sample["path"].name.encode()).hexdigest()[:12]
        sample_id = f"star_{sample['label']}_{audio_hash}"
        
        # Check if already in cache
        cache_file = cache_dir / f"{sample_id}.pt"
        
        if cache_file.exists():
            # Already cached
            new_ids.append(sample_id)
            new_labels.append(component_to_idx[sample["label"]])
            processed += 1
        else:
            # Compute features
            mel_spec = compute_mel_spectrogram(
                sample["path"],
                sr=FEATURE_CONFIG["sample_rate"],
                n_fft=FEATURE_CONFIG["n_fft"],
                hop_length=FEATURE_CONFIG["hop_length"],
                n_mels=FEATURE_CONFIG["n_mels"],
                fmax=FEATURE_CONFIG["fmax"],
                target_frames=FEATURE_CONFIG["target_frames"],
            )
            
            if mel_spec is not None:
                # Save to cache
                torch.save(mel_spec, cache_file)
                new_ids.append(sample_id)
                new_labels.append(component_to_idx[sample["label"]])
                processed += 1
            else:
                skipped += 1
        
        if (i + 1) % 1000 == 0:
            print(f"  Processed {i+1:,}/{len(valid_samples):,} samples...")
    
    print(f"\nProcessed: {processed:,}, Skipped: {skipped:,}")
    
    # 5. Merge with existing dataset
    print("\n" + "=" * 60)
    print(" Merging datasets")
    print("=" * 60)
    
    # Copy existing dataset structure (light copy - only essential files)
    if output_dir != dataset_dir:
        print(f"Creating output directory: {output_dir}...")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy components.json
        shutil.copy(dataset_dir / "components.json", output_dir / "components.json")
        
        # Create train directory
        output_train = output_dir / "train"
        output_train.mkdir(parents=True, exist_ok=True)
        
        # Symlink to validation directory (no need to copy - it's the same)
        src_val = dataset_dir / "val"
        if src_val.exists():
            dst_val = output_dir / "val"
            if not dst_val.exists():
                # Try to create symlink, fallback to just noting it
                try:
                    dst_val.symlink_to(src_val)
                    print(f"  Created symlink to validation: {src_val}")
                except (OSError, NotImplementedError):
                    print(f"  Note: Validation at {src_val} (symlink failed, use original)")
    
    # Merge IDs and labels
    merged_ids = np.concatenate([existing_ids, np.array(new_ids)])
    merged_labels = np.concatenate([existing_labels, np.array(new_labels)])
    
    print(f"Original samples: {len(existing_labels):,}")
    print(f"New samples: {len(new_labels):,}")
    print(f"Merged total: {len(merged_labels):,}")
    
    # Save merged data - use the same naming convention as source
    output_train = output_dir / "train"
    output_train.mkdir(parents=True, exist_ok=True)
    
    # Save in both formats for compatibility
    np.save(output_train / "train_labels_files.npy", merged_ids)
    np.save(output_train / "train_labels_labels.npy", merged_labels)
    # Also save standard format
    np.save(output_train / "ids.npy", merged_ids)
    np.save(output_train / "labels.npy", merged_labels)
    
    # Update stats
    merged_counts = Counter(merged_labels)
    print("\nMerged class distribution:")
    for idx in sorted(merged_counts.keys()):
        for cls, cidx in component_to_idx.items():
            if cidx == idx:
                old_count = existing_counts.get(idx, 0)
                new_count = merged_counts[idx]
                diff = new_count - old_count
                print(f"  {cls:15} {new_count:>10,} (+{diff:,})")
                break
    
    # Save metadata
    metadata = {
        "source_dataset": str(dataset_dir),
        "star_drums_source": str(star_dir),
        "original_samples": len(existing_labels),
        "star_drums_added": len(new_labels),
        "total_samples": len(merged_labels),
        "feature_cache": str(cache_dir),
    }
    
    with open(output_dir / "merge_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "=" * 60)
    print(" Merge Complete!")
    print("=" * 60)
    print(f"Output: {output_dir}")
    print(f"Feature cache: {cache_dir}")
    print(f"\nTo train with merged dataset:")
    print(f"  python train_classifier.py \\")
    print(f"    --dataset {output_dir} \\")
    print(f"    --feature-cache-dir {cache_dir}")


if __name__ == "__main__":
    main()
