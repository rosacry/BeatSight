#!/usr/bin/env python3
"""
Sync labels to match cache exactly - keep only samples that have cache entries.
This ensures 100% cache coverage with no missing samples.
"""
import argparse
import json
import numpy as np
from pathlib import Path
from datetime import datetime
import shutil


def main():
    parser = argparse.ArgumentParser(description="Sync labels to cache entries")
    parser.add_argument("--labels-dir", required=True, help="Directory with train_labels_*.npy files")
    parser.add_argument("--cache-dir", required=True, help="Directory with cache index.json")
    parser.add_argument("--dry-run", action="store_true", help="Only report, don't modify")
    args = parser.parse_args()
    
    labels_dir = Path(args.labels_dir)
    cache_dir = Path(args.cache_dir)
    
    # Determine split from directory name
    split = "train" if "train" in str(labels_dir).lower() else "val"
    
    # Load cache index
    print(f"Loading cache index from {cache_dir}...")
    index_path = cache_dir / "index.json"
    with open(index_path, "r") as f:
        cache_index = json.load(f)
    cache_keys = set(cache_index.keys())
    print(f"  Cache has {len(cache_keys):,} entries")
    
    # Load current labels
    files_path = labels_dir / f"{split}_labels_files.npy"
    labels_path = labels_dir / f"{split}_labels_labels.npy"
    
    print(f"Loading labels from {labels_dir}...")
    files = np.load(files_path, allow_pickle=True)
    labels = np.load(labels_path, allow_pickle=True)
    print(f"  Labels have {len(files):,} entries")
    
    # Build mapping of label paths to cache keys
    valid_indices = []
    missing_count = 0
    missing_by_prefix = {}
    
    print("Checking cache coverage...")
    for i, f in enumerate(files):
        if isinstance(f, bytes):
            f_str = f.decode('utf-8')
        else:
            f_str = str(f)
        
        # Convert label format (audio/uuid__class.wav) to cache key format (audio\uuid__class.pt)
        cache_key = f_str.replace('/', '\\').replace('.wav', '.pt')
        
        if cache_key in cache_keys:
            valid_indices.append(i)
        else:
            missing_count += 1
            # Track by prefix for reporting
            prefix = f_str.split('_')[0] if '_' in f_str else 'unknown'
            missing_by_prefix[prefix] = missing_by_prefix.get(prefix, 0) + 1
    
    print(f"\nResults:")
    print(f"  Valid (in cache): {len(valid_indices):,} ({100*len(valid_indices)/len(files):.2f}%)")
    print(f"  Missing from cache: {missing_count:,}")
    
    if missing_by_prefix:
        print(f"\n  Missing by prefix:")
        for prefix, count in sorted(missing_by_prefix.items(), key=lambda x: -x[1])[:10]:
            print(f"    {prefix}: {count:,}")
    
    if args.dry_run:
        print("\n[DRY RUN] Would create filtered labels with only cached samples")
        return
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    files_backup = labels_dir / f"{split}_labels_files.npy.bak_sync_{timestamp}"
    labels_backup = labels_dir / f"{split}_labels_labels.npy.bak_sync_{timestamp}"
    
    print(f"\nCreating backups...")
    shutil.copy(files_path, files_backup)
    shutil.copy(labels_path, labels_backup)
    print(f"  {files_backup}")
    print(f"  {labels_backup}")
    
    # Filter to valid indices only
    print(f"\nFiltering labels to {len(valid_indices):,} valid entries...")
    valid_indices = np.array(valid_indices)
    filtered_files = files[valid_indices]
    filtered_labels = labels[valid_indices]
    
    # Save
    print(f"Saving filtered labels...")
    np.save(files_path, filtered_files)
    np.save(labels_path, filtered_labels)
    
    print(f"\nDone! Labels now have {len(filtered_files):,} entries (100% cache coverage)")
    
    # Print class distribution
    unique, counts = np.unique(filtered_labels, return_counts=True)
    print(f"\nClass distribution:")
    for cls, cnt in zip(unique, counts):
        print(f"  Class {cls}: {cnt:,}")


if __name__ == "__main__":
    main()
