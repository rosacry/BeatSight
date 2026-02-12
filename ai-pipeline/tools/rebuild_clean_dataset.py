#!/usr/bin/env python3
"""
Build a clean dataset from only samples that exist in the cache.

This eliminates all samples with invalid cache mappings, ensuring training
will not fail due to missing cache entries.

The resulting dataset will have fewer samples but 100% cache hit rate.
"""

import argparse
import json
import numpy as np
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Tuple


# 12 classes in canonical order
CANONICAL_COMPONENTS = [
    'china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open',
    'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom'
]

CLASS_TO_IDX = {name: idx for idx, name in enumerate(CANONICAL_COMPONENTS)}


def load_dataset(dataset_path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load existing dataset."""
    train_dir = dataset_path / "train"
    
    files = np.load(train_dir / "train_labels_files.npy", allow_pickle=True)
    labels = np.load(train_dir / "train_labels_labels.npy")
    
    mapping = np.load(train_dir / "cache_mapping.npz")
    shard_ids = mapping['shard_ids']
    offsets = mapping['offsets']
    valid = mapping['valid']
    
    return files, labels, shard_ids, offsets, valid


def analyze_invalid_samples(files: np.ndarray, labels: np.ndarray, valid: np.ndarray) -> Dict:
    """Analyze which samples are invalid and why."""
    invalid_mask = ~valid
    invalid_files = files[invalid_mask]
    invalid_labels = labels[invalid_mask]
    
    # Count by class
    class_counts = Counter()
    for lbl in invalid_labels:
        class_counts[CANONICAL_COMPONENTS[lbl]] += 1
    
    # Count by source prefix
    source_counts = Counter()
    for f in invalid_files:
        f_str = str(f)
        if 'lakh_' in f_str:
            source_counts['lakh_midi'] += 1
        elif 'star_' in f_str:
            source_counts['star_drums'] += 1
        elif 'audio/' in f_str:
            source_counts['audio_files'] += 1
        else:
            source_counts['other'] += 1
    
    return {
        'total_invalid': invalid_mask.sum(),
        'by_class': dict(class_counts),
        'by_source': dict(source_counts),
    }


def rebuild_clean_dataset(
    dataset_path: Path,
    output_path: Path,
    val_ratio: float = 0.10,
) -> Dict:
    """Rebuild dataset using only valid samples."""
    
    print("=" * 70)
    print("REBUILD CLEAN DATASET")
    print("=" * 70)
    
    # Load original
    print("\n[1/4] Loading original dataset...")
    files, labels, shard_ids, offsets, valid = load_dataset(dataset_path)
    
    print(f"  Total samples: {len(files):,}")
    print(f"  Valid samples: {valid.sum():,}")
    print(f"  Invalid samples: {(~valid).sum():,}")
    
    # Analyze invalid
    print("\n[2/4] Analyzing invalid samples...")
    invalid_info = analyze_invalid_samples(files, labels, valid)
    print(f"  By class:")
    for cls in sorted(invalid_info['by_class'].keys()):
        cnt = invalid_info['by_class'][cls]
        print(f"    {cls}: {cnt:,}")
    print(f"  By source:")
    for src, cnt in sorted(invalid_info['by_source'].items(), key=lambda x: -x[1]):
        print(f"    {src}: {cnt:,}")
    
    # Filter to valid only
    print("\n[3/4] Filtering to valid samples...")
    valid_mask = valid.astype(bool)
    
    clean_files = files[valid_mask]
    clean_labels = labels[valid_mask]
    clean_shard_ids = shard_ids[valid_mask]
    clean_offsets = offsets[valid_mask]
    clean_valid = np.ones(len(clean_files), dtype=bool)
    
    print(f"  Clean samples: {len(clean_files):,}")
    
    # Class distribution
    print("\n  Class distribution after cleaning:")
    class_counts = Counter(clean_labels)
    for idx in sorted(class_counts.keys()):
        cls_name = CANONICAL_COMPONENTS[idx]
        cnt = class_counts[idx]
        print(f"    {cls_name}: {cnt:,}")
    
    # Stratified split
    print("\n[4/4] Creating stratified train/val split...")
    
    train_indices = []
    val_indices = []
    
    for class_idx in range(len(CANONICAL_COMPONENTS)):
        class_mask = clean_labels == class_idx
        class_indices = np.where(class_mask)[0]
        
        np.random.seed(42 + class_idx)  # Reproducible
        np.random.shuffle(class_indices)
        
        n_val = int(len(class_indices) * val_ratio)
        val_indices.extend(class_indices[:n_val])
        train_indices.extend(class_indices[n_val:])
    
    train_indices = np.array(train_indices)
    val_indices = np.array(val_indices)
    
    # Shuffle
    np.random.seed(42)
    np.random.shuffle(train_indices)
    np.random.shuffle(val_indices)
    
    print(f"  Train: {len(train_indices):,}")
    print(f"  Val: {len(val_indices):,}")
    
    # Save
    output_path.mkdir(parents=True, exist_ok=True)
    
    train_dir = output_path / "train"
    val_dir = output_path / "val"
    train_dir.mkdir(exist_ok=True)
    val_dir.mkdir(exist_ok=True)
    
    # Train
    np.save(train_dir / "train_labels_files.npy", clean_files[train_indices])
    np.save(train_dir / "train_labels_labels.npy", clean_labels[train_indices])
    np.savez(
        train_dir / "cache_mapping.npz",
        shard_ids=clean_shard_ids[train_indices],
        offsets=clean_offsets[train_indices],
        valid=np.ones(len(train_indices), dtype=bool),
    )
    
    # Val
    np.save(val_dir / "train_labels_files.npy", clean_files[val_indices])
    np.save(val_dir / "train_labels_labels.npy", clean_labels[val_indices])
    np.savez(
        val_dir / "cache_mapping.npz",
        shard_ids=clean_shard_ids[val_indices],
        offsets=clean_offsets[val_indices],
        valid=np.ones(len(val_indices), dtype=bool),
    )
    
    # Save metadata
    metadata = {
        "name": output_path.name,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_dataset": str(dataset_path),
        "num_classes": len(CANONICAL_COMPONENTS),
        "class_names": CANONICAL_COMPONENTS,
        "train_samples": int(len(train_indices)),
        "val_samples": int(len(val_indices)),
        "val_ratio": val_ratio,
        "removed_invalid": int(invalid_info['total_invalid']),
        "removed_by_class": {k: int(v) for k, v in invalid_info['by_class'].items()},
        "removed_by_source": {k: int(v) for k, v in invalid_info['by_source'].items()},
    }
    
    with open(output_path / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"Output: {output_path}")
    print(f"Train: {len(train_indices):,}")
    print(f"Val: {len(val_indices):,}")
    
    # Final class distribution
    print("\nFinal class distribution:")
    train_labels_final = clean_labels[train_indices]
    val_labels_final = clean_labels[val_indices]
    
    for idx in range(len(CANONICAL_COMPONENTS)):
        cls_name = CANONICAL_COMPONENTS[idx]
        train_cnt = (train_labels_final == idx).sum()
        val_cnt = (val_labels_final == idx).sum()
        val_pct = 100 * val_cnt / (train_cnt + val_cnt)
        print(f"  {cls_name:15s}: train={train_cnt:>8,}  val={val_cnt:>7,}  (val%={val_pct:.2f}%)")
    
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Rebuild clean dataset from valid samples")
    parser.add_argument("--source", type=Path, default=Path("F:/datasets/prod_v5_definitive"),
                       help="Source dataset path")
    parser.add_argument("--output", type=Path, default=Path("F:/datasets/prod_v5_clean"),
                       help="Output dataset path")
    parser.add_argument("--val-ratio", type=float, default=0.10,
                       help="Validation split ratio")
    args = parser.parse_args()
    
    rebuild_clean_dataset(args.source, args.output, args.val_ratio)


if __name__ == "__main__":
    main()
