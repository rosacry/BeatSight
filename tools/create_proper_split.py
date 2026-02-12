#!/usr/bin/env python3
"""
Create proper train/val split from samples that exist in cache.
This ensures both train and val have high cache coverage.
"""

import numpy as np
from pathlib import Path
from collections import defaultdict

def create_proper_split(dataset_path: str, cache_path: str, val_ratio: float = 0.1):
    dataset_path = Path(dataset_path)
    cache_path = Path(cache_path)
    
    print(f"\n{'='*70}")
    print(f"  CREATING PROPER TRAIN/VAL SPLIT")
    print(f"{'='*70}")
    print(f"  Dataset: {dataset_path}")
    print(f"  Cache:   {cache_path}")
    print(f"  Val ratio: {val_ratio*100:.0f}%")
    
    # Load train cache keys
    print(f"\n  Loading train cache keys...")
    train_index = np.load(cache_path / "train" / "index.npz", allow_pickle=True)
    train_cache_keys = set()
    for k in train_index['keys']:
        k_str = k.decode('utf-8') if isinstance(k, bytes) else str(k)
        # Normalize to forward slash
        k_norm = k_str.replace('\\', '/')
        train_cache_keys.add(k_norm)
    print(f"    Loaded {len(train_cache_keys):,} train cache keys")
    
    # Load val cache keys  
    print(f"  Loading val cache keys...")
    val_index = np.load(cache_path / "val" / "index.npz", allow_pickle=True)
    val_cache_keys = set()
    for k in val_index['keys']:
        k_str = k.decode('utf-8') if isinstance(k, bytes) else str(k)
        k_norm = k_str.replace('\\', '/')
        val_cache_keys.add(k_norm)
    print(f"    Loaded {len(val_cache_keys):,} val cache keys")
    
    # Combine all cache keys
    all_cache_keys = train_cache_keys | val_cache_keys
    print(f"    Combined: {len(all_cache_keys):,} unique cache keys")
    
    # Load original train labels
    print(f"\n  Loading original train labels...")
    train_files = np.load(dataset_path / "train" / "train_labels_files.npy", allow_pickle=True)
    train_labels = np.load(dataset_path / "train" / "train_labels_labels.npy")
    print(f"    Loaded {len(train_files):,} train samples")
    
    # Load original val labels
    print(f"  Loading original val labels...")
    val_files = np.load(dataset_path / "val" / "val_labels_files.npy", allow_pickle=True)
    val_labels = np.load(dataset_path / "val" / "val_labels_labels.npy")
    print(f"    Loaded {len(val_files):,} val samples")
    
    # Combine all samples
    all_files = np.concatenate([train_files, val_files])
    all_labels = np.concatenate([train_labels, val_labels])
    print(f"\n  Combined: {len(all_files):,} total samples")
    
    # Find samples that exist in cache
    print(f"\n  Finding samples in cache...")
    
    def get_cache_key(f):
        """Convert dataset file path to cache key format."""
        f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
        f_norm = f_str.replace('\\', '/')
        
        if f_norm.startswith('lakh_'):
            # Lakh samples: add .pt
            return f_norm + '.pt'
        else:
            # Regular samples: .wav -> .pt
            return f_norm.replace('.wav', '.pt')
    
    valid_indices = []
    for i, f in enumerate(all_files):
        cache_key = get_cache_key(f)
        if cache_key in all_cache_keys:
            valid_indices.append(i)
        if (i + 1) % 1_000_000 == 0:
            print(f"    Checked {i+1:,}/{len(all_files):,}...")
    
    valid_indices = np.array(valid_indices)
    print(f"    Found {len(valid_indices):,} samples in cache ({100*len(valid_indices)/len(all_files):.1f}%)")
    
    # Get valid samples
    valid_files = all_files[valid_indices]
    valid_labels = all_labels[valid_indices]
    
    # Show class distribution before split
    class_names = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
                   'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']
    
    print(f"\n  Valid samples by class:")
    class_counts = {}
    for i, name in enumerate(class_names):
        count = np.sum(valid_labels == i)
        class_counts[i] = count
        print(f"    {name:15}: {count:>10,}")
    
    # Stratified split - ensure each class has val samples
    print(f"\n  Creating stratified split...")
    np.random.seed(42)  # Reproducible
    
    new_train_indices = []
    new_val_indices = []
    
    for class_idx in range(12):
        class_mask = valid_labels == class_idx
        class_indices = np.where(class_mask)[0]
        np.random.shuffle(class_indices)
        
        n_val = max(1, int(len(class_indices) * val_ratio))  # At least 1 val sample
        
        new_val_indices.extend(class_indices[:n_val])
        new_train_indices.extend(class_indices[n_val:])
    
    new_train_indices = np.array(new_train_indices)
    new_val_indices = np.array(new_val_indices)
    
    # Shuffle
    np.random.shuffle(new_train_indices)
    np.random.shuffle(new_val_indices)
    
    new_train_files = valid_files[new_train_indices]
    new_train_labels = valid_labels[new_train_indices]
    new_val_files = valid_files[new_val_indices]
    new_val_labels = valid_labels[new_val_indices]
    
    print(f"\n  New split:")
    print(f"    Train: {len(new_train_files):,}")
    print(f"    Val:   {len(new_val_files):,}")
    
    # Show val class distribution
    print(f"\n  Val samples by class:")
    for i, name in enumerate(class_names):
        count = np.sum(new_val_labels == i)
        print(f"    {name:15}: {count:>10,}")
    
    # Backup and save
    print(f"\n  Saving new split...")
    
    # Backup
    backup_dir = dataset_path / "backup_before_split"
    backup_dir.mkdir(exist_ok=True)
    
    import shutil
    for split in ['train', 'val']:
        split_dir = dataset_path / split
        for f in split_dir.glob("*.npy"):
            shutil.copy(f, backup_dir / f"{split}_{f.name}")
    print(f"    Backed up to {backup_dir}")
    
    # Save new train
    np.save(dataset_path / "train" / "train_labels_files.npy", new_train_files)
    np.save(dataset_path / "train" / "train_labels_labels.npy", new_train_labels)
    
    # Delete old cache mapping
    cache_mapping = dataset_path / "train" / "cache_mapping.npz"
    if cache_mapping.exists():
        cache_mapping.unlink()
    
    # Save new val
    np.save(dataset_path / "val" / "val_labels_files.npy", new_val_files)
    np.save(dataset_path / "val" / "val_labels_labels.npy", new_val_labels)
    
    # Delete old cache mapping
    cache_mapping = dataset_path / "val" / "cache_mapping.npz"
    if cache_mapping.exists():
        cache_mapping.unlink()
    
    print(f"\n{'='*70}")
    print(f"  DONE!")
    print(f"{'='*70}")
    print(f"  Train: {len(new_train_files):,} samples")
    print(f"  Val:   {len(new_val_files):,} samples")
    print(f"\n  Next: Regenerate cache mappings:")
    print(f"    python tools/generate_cache_index_mapping.py \\")
    print(f"      --labels \"{dataset_path}/train/train_labels_files.npy\" \\")
    print(f"      --cache \"{cache_path}/train\" \\")
    print(f"      --output \"{dataset_path}/train/cache_mapping.npz\"")
    print(f"")
    print(f"    python tools/generate_cache_index_mapping.py \\")
    print(f"      --labels \"{dataset_path}/val/val_labels_files.npy\" \\")
    print(f"      --cache \"{cache_path}/val\" \\")
    print(f"      --output \"{dataset_path}/val/cache_mapping.npz\"")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="F:/datasets/prod_v5_definitive")
    parser.add_argument("--cache", default="F:/feature_cache")
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()
    
    create_proper_split(args.dataset, args.cache, args.val_ratio)
