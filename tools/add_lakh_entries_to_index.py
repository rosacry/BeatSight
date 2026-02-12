#!/usr/bin/env python3
"""
Add lakh entries from labels to the cache index.

The labels have entries like 'lakh_splash_8f1331c15bec' which need to be
added to the cache index as 'lakh_splash_8f1331c15bec.pt' mapping to
shards 231-232.
"""

import json
import time
import numpy as np
from pathlib import Path
from collections import Counter


def main():
    labels_dir = Path("F:/datasets/prod_v5_fixed_20251212/train")
    cache_dir = Path("F:/feature_cache/train")
    index_path = cache_dir / "index.json"
    
    # Load labels to get lakh file IDs
    print("Loading labels...")
    files = np.load(labels_dir / "train_labels_files.npy", allow_pickle=True)
    labels = np.load(labels_dir / "train_labels_labels.npy")
    print(f"  Total samples: {len(files):,}")
    
    # Extract lakh entries
    lakh_entries = []
    class_counts = Counter()
    
    for i, f in enumerate(files):
        if isinstance(f, bytes):
            f = f.decode('utf-8')
        
        if f.startswith('lakh_china_') or f.startswith('lakh_splash_'):
            lakh_entries.append((f, int(labels[i])))
            if 'china' in f:
                class_counts['china'] += 1
            else:
                class_counts['splash'] += 1
    
    print(f"\nLakh entries in labels:")
    print(f"  China: {class_counts['china']:,}")
    print(f"  Splash: {class_counts['splash']:,}")
    print(f"  Total: {len(lakh_entries):,}")
    
    # Sort lakh entries to match the order they were written to shards
    # During consolidation, files were sorted by name
    lakh_entries.sort(key=lambda x: x[0])
    
    print(f"\nFirst 5 lakh entries (sorted):")
    for f, label in lakh_entries[:5]:
        print(f"  {f} (class {label})")
    
    # Load existing index
    print(f"\nLoading index from {index_path}...")
    start = time.time()
    with open(index_path) as f:
        index = json.load(f)
    print(f"  Loaded {len(index):,} entries in {time.time()-start:.1f}s")
    
    # Check how many lakh entries already exist
    existing_lakh = sum(1 for k in index if k.startswith('lakh_'))
    print(f"  Existing lakh entries: {existing_lakh}")
    
    # Add lakh entries with .pt suffix
    # Shard 231: first 65536 samples
    # Shard 232: remaining samples
    print(f"\nAdding lakh entries to index...")
    
    added = 0
    skipped = 0
    
    for i, (file_id, label) in enumerate(lakh_entries):
        # Add .pt suffix
        key = f"{file_id}.pt"
        
        if key in index:
            skipped += 1
            continue
        
        # Determine shard and offset
        if i < 65536:
            shard_id = 231
            offset = i
        else:
            shard_id = 232
            offset = i - 65536
        
        index[key] = [shard_id, offset]
        added += 1
    
    print(f"  Added: {added:,}")
    print(f"  Skipped (already exists): {skipped:,}")
    print(f"  Total index entries: {len(index):,}")
    
    # Save index
    print(f"\nBacking up and saving index...")
    backup_path = index_path.with_suffix('.json.bak_before_lakh')
    import shutil
    shutil.copy(index_path, backup_path)
    print(f"  Backed up to {backup_path.name}")
    
    start = time.time()
    with open(index_path, 'w') as f:
        json.dump(index, f)
    print(f"  Saved in {time.time()-start:.1f}s")
    
    # Verify
    test_key = lakh_entries[0][0] + '.pt'
    print(f"\nVerification: '{test_key}' in index: {test_key in index}")
    if test_key in index:
        print(f"  Maps to: {index[test_key]}")
    
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("1. Regenerate binary index:")
    print("   python tools/convert_cache_index_to_binary.py F:/feature_cache/train --force")
    print("2. Run training!")
    print("="*60)


if __name__ == "__main__":
    main()
