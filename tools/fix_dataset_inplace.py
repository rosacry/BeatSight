#!/usr/bin/env python3
"""Fix prod_v5_definitive dataset IN PLACE by removing samples not in cache."""

import argparse
import numpy as np
from pathlib import Path
import shutil

def fix_dataset_inplace(dataset_path: str, cache_path: str):
    dataset_path = Path(dataset_path)
    cache_path = Path(cache_path)
    
    print(f"\n{'='*70}")
    print(f"  FIXING DATASET IN PLACE")
    print(f"{'='*70}")
    print(f"  Dataset: {dataset_path}")
    print(f"  Cache:   {cache_path}")
    print(f"  WARNING: This will MODIFY the existing dataset!")
    print(f"{'='*70}\n")
    
    for split in ['train', 'val']:
        split_path = dataset_path / split
        cache_split = cache_path / split
        
        if not split_path.exists():
            print(f"  Skipping {split} - not found")
            continue
            
        print(f"\n{'-'*70}")
        print(f"  Processing {split.upper()} split")
        print(f"{'-'*70}\n")
        
        # Load cache keys
        print(f"  Loading cache keys...")
        index_file = cache_split / "index.npz"
        if not index_file.exists():
            print(f"  ERROR: {index_file} not found!")
            continue
            
        index_data = np.load(index_file, allow_pickle=True)
        cache_keys_raw = index_data['keys']
        
        # Normalize cache keys: bytes -> str, backslash -> forward slash, keep .pt extension
        print(f"  Normalizing {len(cache_keys_raw):,} cache keys...")
        cache_keys = set()
        for k in cache_keys_raw:
            # Decode bytes if needed
            if isinstance(k, bytes):
                k_str = k.decode('utf-8')
            else:
                k_str = str(k)
            # Normalize: forward slashes only (keep .pt extension)
            k_norm = k_str.replace('\\', '/')
            cache_keys.add(k_norm)
        print(f"  Loaded {len(cache_keys):,} unique cache keys")
        
        # Load dataset
        print(f"\n  Loading dataset labels...")
        files_path = split_path / f"{split}_labels_files.npy"
        labels_path = split_path / f"{split}_labels_labels.npy"
        
        files = np.load(files_path, allow_pickle=True)
        labels = np.load(labels_path)
        
        total = len(files)
        print(f"  Loaded {total:,} samples")
        
        # Find valid indices
        print(f"\n  Finding valid samples...")
        valid_indices = []
        for i, f in enumerate(files):
            f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
            f_norm = f_str.replace('\\', '/')
            
            # Different normalization for lakh vs regular samples
            if f_norm.startswith('lakh_'):
                # Lakh samples: add .pt extension
                cache_key = f_norm + '.pt'
            else:
                # Regular samples: audio/xxx.wav -> audio/xxx.pt
                cache_key = f_norm.replace('.wav', '.pt')
            
            if cache_key in cache_keys:
                valid_indices.append(i)
            if (i + 1) % 1_000_000 == 0:
                print(f"    Checked {i+1:,}/{total:,}...")
        
        valid_indices = np.array(valid_indices, dtype=np.int64)
        valid_count = len(valid_indices)
        removed = total - valid_count
        
        print(f"\n  Results:")
        print(f"    Original:  {total:,}")
        print(f"    Valid:     {valid_count:,} ({100*valid_count/total:.2f}%)")
        print(f"    Removing:  {removed:,} ({100*removed/total:.2f}%)")
        
        # Backup original files
        print(f"\n  Backing up original files...")
        backup_dir = split_path / "backup_original"
        backup_dir.mkdir(exist_ok=True)
        shutil.copy(files_path, backup_dir / files_path.name)
        shutil.copy(labels_path, backup_dir / labels_path.name)
        print(f"    Backed up to {backup_dir}")
        
        # Filter and save
        print(f"\n  Saving filtered dataset...")
        new_files = files[valid_indices]
        new_labels = labels[valid_indices]
        
        np.save(files_path, new_files)
        np.save(labels_path, new_labels)
        print(f"    Saved {valid_count:,} samples to {split_path}")
        
        # Delete old cache mapping (will need regeneration)
        cache_mapping = split_path / "cache_mapping.npz"
        if cache_mapping.exists():
            cache_mapping.unlink()
            print(f"    Deleted old cache_mapping.npz (needs regeneration)")
        
        # Show class distribution
        print(f"\n  Class distribution after fix:")
        class_names = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
                       'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']
        for c in range(12):
            count = np.sum(new_labels == c)
            print(f"    {class_names[c]:15}: {count:>10,}")
    
    print(f"\n{'='*70}")
    print(f"  DONE - Dataset fixed in place")
    print(f"{'='*70}")
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
    parser = argparse.ArgumentParser(description="Fix dataset in place")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--cache", required=True)
    args = parser.parse_args()
    fix_dataset_inplace(args.dataset, args.cache)
