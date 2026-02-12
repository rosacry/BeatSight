#!/usr/bin/env python3
"""
Sync labels with cache - remove any label entries that don't exist in cache,
and ensure all lakh_* cache entries are in labels.

This fixes the ID mismatch between labels and cache.
"""

import argparse
import json
import numpy as np
from pathlib import Path
from collections import Counter
import time


def sync_labels_with_cache(labels_dir: Path, cache_dir: Path, dry_run: bool = True):
    """Sync labels with cache index."""
    
    # Load labels
    files_npy = labels_dir / "train_labels_files.npy"
    labels_npy = labels_dir / "train_labels_labels.npy"
    
    if not files_npy.exists():
        files_npy = labels_dir / "files.npy"
        labels_npy = labels_dir / "labels.npy"
    
    print(f"Loading labels from {labels_dir}...")
    files = np.load(files_npy, allow_pickle=True)
    labels = np.load(labels_npy)
    print(f"  Labels: {len(files):,} samples")
    
    # Load cache index
    index_json = cache_dir / "index.json"
    print(f"\nLoading cache index from {index_json}...")
    start = time.time()
    with open(index_json) as f:
        cache_index = json.load(f)
    print(f"  Cache: {len(cache_index):,} entries (loaded in {time.time()-start:.1f}s)")
    
    # Build set of cache keys for fast lookup
    cache_keys = set(cache_index.keys())
    
    def normalize_key(file_id):
        """Normalize file ID to match cache key format.
        
        Labels: audio/6ccc3c02-f136-5d43-97f4-399ad4bc645e__hihat_closed.wav
        Cache:  audio\\6ccc3c02-f136-5d43-97f4-399ad4bc645e__hihat_closed.pt
        
        Lakh entries don't need normalization - they should match exactly.
        """
        if isinstance(file_id, bytes):
            file_id = file_id.decode('utf-8')
        
        # Lakh entries: no transformation needed (exact match)
        if file_id.startswith('lakh_'):
            return file_id
        
        # Regular audio entries: convert path format
        # Convert forward slash to backslash (cache uses backslash on Windows)
        file_id = file_id.replace('/', '\\')
        # Replace .wav with .pt
        if file_id.endswith('.wav'):
            file_id = file_id[:-4] + '.pt'
        return file_id
    
    # Analyze current state
    print("\n[ANALYSIS]")
    
    # Count lakh entries in cache
    cache_china = sum(1 for k in cache_keys if k.startswith('lakh_china_'))
    cache_splash = sum(1 for k in cache_keys if k.startswith('lakh_splash_'))
    print(f"  Cache lakh_china_*: {cache_china:,}")
    print(f"  Cache lakh_splash_*: {cache_splash:,}")
    
    # Check which labels are NOT in cache
    missing_from_cache = []
    in_cache = []
    labels_china = labels_splash = 0
    
    for i, f in enumerate(files):
        if isinstance(f, bytes):
            f = f.decode('utf-8')
        
        if f.startswith('lakh_china_'):
            labels_china += 1
        elif f.startswith('lakh_splash_'):
            labels_splash += 1
        
        # Normalize to cache key format
        cache_key = normalize_key(f)
        
        if cache_key in cache_keys:
            in_cache.append(i)
        else:
            missing_from_cache.append((i, f))
    
    print(f"\n  Labels lakh_china_*: {labels_china:,}")
    print(f"  Labels lakh_splash_*: {labels_splash:,}")
    print(f"\n  Labels in cache: {len(in_cache):,}")
    print(f"  Labels NOT in cache: {len(missing_from_cache):,}")
    
    if missing_from_cache:
        print(f"\n  Examples NOT in cache:")
        for i, f in missing_from_cache[:10]:
            print(f"    [{i}] {f}")
    
    # Check which cache lakh entries are NOT in labels
    label_keys_set = set()
    for f in files:
        label_keys_set.add(normalize_key(f))
    
    cache_lakh_not_in_labels = []
    for k in cache_keys:
        if (k.startswith('lakh_china_') or k.startswith('lakh_splash_')) and k not in label_keys_set:
            cache_lakh_not_in_labels.append(k)
    
    print(f"\n  Cache lakh_* NOT in labels: {len(cache_lakh_not_in_labels):,}")
    if cache_lakh_not_in_labels:
        print(f"  Examples:")
        for k in cache_lakh_not_in_labels[:5]:
            print(f"    {k}")
    
    if dry_run:
        print(f"\n[DRY RUN]")
        print(f"  Would remove {len(missing_from_cache):,} entries not in cache")
        print(f"  Would add {len(cache_lakh_not_in_labels):,} cache lakh entries to labels")
        print(f"  Run with --apply to make changes")
        return
    
    # Apply changes
    print(f"\n[APPLYING CHANGES]")
    
    # Step 1: Keep only labels that are in cache
    print(f"  Removing {len(missing_from_cache):,} entries not in cache...")
    good_mask = np.ones(len(files), dtype=bool)
    for i, _ in missing_from_cache:
        good_mask[i] = False
    
    new_files = list(files[good_mask])
    new_labels = list(labels[good_mask])
    
    print(f"  Kept {len(new_files):,} entries")
    
    # Step 2: Add cache lakh entries that aren't in labels
    # Need to determine labels for china (0) and splash (10)
    # Load class names to get correct indices
    class_names_file = labels_dir / "class_names.json"
    if class_names_file.exists():
        with open(class_names_file) as f:
            class_names = json.load(f)
        china_idx = class_names.index('china') if 'china' in class_names else 0
        splash_idx = class_names.index('splash') if 'splash' in class_names else 10
    else:
        # Assume standard 12-class order
        china_idx = 0
        splash_idx = 10
    
    print(f"  Adding {len(cache_lakh_not_in_labels):,} cache lakh entries...")
    print(f"    china -> class {china_idx}")
    print(f"    splash -> class {splash_idx}")
    
    added_china = added_splash = 0
    for k in cache_lakh_not_in_labels:
        new_files.append(k)
        if k.startswith('lakh_china_'):
            new_labels.append(china_idx)
            added_china += 1
        else:
            new_labels.append(splash_idx)
            added_splash += 1
    
    print(f"    Added china: {added_china:,}")
    print(f"    Added splash: {added_splash:,}")
    
    # Convert to numpy
    new_files = np.array(new_files, dtype=object)
    new_labels = np.array(new_labels, dtype=np.int64)
    
    print(f"\n  Final total: {len(new_files):,} samples")
    
    # Backup old files
    backup_suffix = time.strftime("%Y%m%d_%H%M%S")
    files_backup = files_npy.parent / f"{files_npy.stem}.bak_sync_{backup_suffix}{files_npy.suffix}"
    labels_backup = labels_npy.parent / f"{labels_npy.stem}.bak_sync_{backup_suffix}{labels_npy.suffix}"
    
    import shutil
    shutil.copy(files_npy, files_backup)
    shutil.copy(labels_npy, labels_backup)
    print(f"  Backed up to *_sync_{backup_suffix}.*")
    
    # Save new files
    np.save(files_npy, new_files)
    np.save(labels_npy, new_labels)
    print(f"  Saved synced labels")
    
    # Show class distribution
    print(f"\n[FINAL CLASS DISTRIBUTION]")
    unique, counts = np.unique(new_labels, return_counts=True)
    
    if class_names_file.exists():
        with open(class_names_file) as f:
            class_names = json.load(f)
        for cls_idx, count in zip(unique, counts):
            name = class_names[cls_idx] if cls_idx < len(class_names) else f"class_{cls_idx}"
            print(f"    {name}: {count:,}")
    else:
        for cls_idx, count in zip(unique, counts):
            print(f"    Class {cls_idx}: {count:,}")
    
    max_count = max(counts)
    min_count = min(counts)
    print(f"\n  Imbalance: {max_count/min_count:.1f}x")


def main():
    parser = argparse.ArgumentParser(description="Sync labels with cache index")
    parser.add_argument("labels_dir", type=Path, help="Path to labels directory")
    parser.add_argument("cache_dir", type=Path, help="Path to cache directory")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    
    args = parser.parse_args()
    
    sync_labels_with_cache(args.labels_dir, args.cache_dir, dry_run=not args.apply)


if __name__ == "__main__":
    main()
