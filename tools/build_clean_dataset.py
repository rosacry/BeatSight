#!/usr/bin/env python3
"""
Build a clean dataset with 100% cache coverage.
Removes all samples from dataset labels that don't exist in the feature cache.
"""

import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict
import json
import time


CLASS_NAMES = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
               'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']


def normalize_cache_key(key: str) -> str:
    """Normalize a cache key to match dataset file format."""
    # Cache uses .pt extension and may have backslashes
    # Dataset uses .wav extension and forward slashes
    return key.replace('\\', '/').replace('.pt', '.wav')


def normalize_dataset_file(f: str) -> str:
    """Normalize a dataset file path for comparison."""
    return str(f).replace('\\', '/')


def load_cache_keys(cache_dir: Path) -> set:
    """Load and normalize all keys from the cache index."""
    index_path = cache_dir / "index.npz"
    if not index_path.exists():
        raise FileNotFoundError(f"No index.npz found in {cache_dir}")
    
    print(f"  Loading {index_path}...")
    data = np.load(index_path, allow_pickle=True)
    keys_raw = data['keys']
    
    print(f"  Normalizing {len(keys_raw):,} cache keys...")
    # Decode bytes and normalize
    cache_keys = set()
    for k in keys_raw:
        if isinstance(k, bytes):
            k = k.decode('utf-8')
        cache_keys.add(normalize_cache_key(k))
    
    return cache_keys


def build_clean_dataset(dataset_dir: str, cache_dir: str, output_dir: str = None):
    """Build a clean dataset with only cached samples."""
    
    dataset_path = Path(dataset_dir)
    cache_path = Path(cache_dir)
    output_path = Path(output_dir) if output_dir else dataset_path.parent / f"{dataset_path.name}_clean"
    
    print(f"\n{'='*70}")
    print(f"  BUILDING CLEAN DATASET")
    print(f"{'='*70}")
    print(f"  Source:  {dataset_path}")
    print(f"  Cache:   {cache_path}")
    print(f"  Output:  {output_path}")
    
    stats = {}
    
    for split in ['train', 'val']:
        print(f"\n{'-'*70}")
        print(f"  Processing {split.upper()} split")
        print(f"{'-'*70}")
        
        split_cache = cache_path / split
        split_dataset = dataset_path / split
        split_output = output_path / split
        
        if not split_dataset.exists():
            print(f"  [SKIP] {split_dataset} does not exist")
            continue
        
        # Load cache keys
        print(f"\n  Loading cache keys...")
        t0 = time.time()
        cache_keys = load_cache_keys(split_cache)
        print(f"  Loaded {len(cache_keys):,} cache keys in {time.time()-t0:.1f}s")
        
        # Load dataset
        print(f"\n  Loading dataset labels...")
        # Try different naming conventions
        files_file = split_dataset / f"{split}_labels_files.npy"
        labels_file = split_dataset / f"{split}_labels_labels.npy"
        
        if files_file.exists() and labels_file.exists():
            # prod_v5_definitive format
            files = np.load(files_file, allow_pickle=True)
            labels = np.load(labels_file)
        elif (split_dataset / f"{split}_files.npy").exists():
            # Standard format
            files = np.load(split_dataset / f"{split}_files.npy", allow_pickle=True)
            labels = np.load(split_dataset / f"{split}_labels.npy")
        else:
            raise FileNotFoundError(f"Could not find dataset files in {split_dataset}")
        
        total_samples = len(labels)
        print(f"  Loaded {total_samples:,} samples")
        
        # Find valid samples (those in cache)
        print(f"\n  Finding valid samples...")
        t0 = time.time()
        valid_mask = np.zeros(total_samples, dtype=bool)
        missing_by_class = defaultdict(int)
        
        for i in range(total_samples):
            key = normalize_dataset_file(files[i])
            if key in cache_keys:
                valid_mask[i] = True
            else:
                missing_by_class[labels[i]] += 1
            
            if (i + 1) % 1_000_000 == 0:
                print(f"    Checked {i+1:,}/{total_samples:,}...")
        
        valid_count = valid_mask.sum()
        missing_count = total_samples - valid_count
        print(f"  Completed in {time.time()-t0:.1f}s")
        
        # Report
        print(f"\n  Results:")
        print(f"    Total samples:  {total_samples:,}")
        print(f"    Valid (cached): {valid_count:,} ({100*valid_count/total_samples:.2f}%)")
        print(f"    Missing:        {missing_count:,} ({100*missing_count/total_samples:.2f}%)")
        
        if missing_count > 0:
            print(f"\n  Missing by class:")
            for class_idx in range(len(CLASS_NAMES)):
                count = missing_by_class.get(class_idx, 0)
                class_total = (labels == class_idx).sum()
                if count > 0:
                    pct = 100 * count / class_total if class_total > 0 else 0
                    print(f"    {CLASS_NAMES[class_idx]:15s}: {count:>10,} / {class_total:>10,} ({pct:5.1f}%)")
        
        # Create clean dataset
        print(f"\n  Creating clean dataset...")
        split_output.mkdir(parents=True, exist_ok=True)
        
        clean_labels = labels[valid_mask]
        clean_files = files[valid_mask]
        
        # Save with same naming convention as source
        output_file = split_output / f"{split}_labels_files.npy"
        np.save(output_file, clean_files)
        np.save(split_output / f"{split}_labels_labels.npy", clean_labels)
        # Also save standard naming for compatibility
        np.save(split_output / f"{split}_files.npy", clean_files)
        np.save(split_output / f"{split}_labels.npy", clean_labels)
        
        print(f"  Saved {valid_count:,} samples to {split_output}")
        
        # Copy cache mapping if it exists (will need regeneration anyway)
        
        stats[split] = {
            'original': int(total_samples),
            'clean': int(valid_count),
            'removed': int(missing_count),
            'coverage': float(valid_count / total_samples)
        }
    
    # Save stats
    stats_file = output_path / "clean_dataset_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    for split, s in stats.items():
        print(f"  {split}: {s['original']:,} -> {s['clean']:,} ({100*s['coverage']:.2f}% coverage)")
    print(f"\n  Output: {output_path}")
    print(f"  Stats:  {stats_file}")
    print(f"\n  Next steps:")
    print(f"  1. Generate cache mappings for the clean dataset")
    print(f"  2. Run training with --dataset \"{output_path}\"")
    
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build clean dataset with 100% cache coverage")
    parser.add_argument("--dataset", required=True, help="Source dataset directory")
    parser.add_argument("--cache", required=True, help="Feature cache directory")
    parser.add_argument("--output", help="Output directory (default: <dataset>_clean)")
    
    args = parser.parse_args()
    build_clean_dataset(args.dataset, args.cache, args.output)
