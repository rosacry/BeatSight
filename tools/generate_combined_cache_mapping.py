#!/usr/bin/env python3
"""
Generate cache mapping that checks BOTH train and val caches.
Needed after creating combined train/val split from samples in either cache.
"""

import argparse
import time
from pathlib import Path
import numpy as np


def generate_combined_mapping(labels_path: str, cache_base: str, output_path: str):
    cache_base = Path(cache_base)
    labels_path = Path(labels_path)
    output_path = Path(output_path)
    
    print(f"\n{'='*70}")
    print(f"  GENERATING COMBINED CACHE MAPPING")
    print(f"{'='*70}")
    print(f"  Labels: {labels_path}")
    print(f"  Cache:  {cache_base}")
    print(f"  Output: {output_path}")
    
    # Load both cache indices
    all_keys = {}  # key -> (shard, offset, which_cache)
    
    for split in ['train', 'val']:
        index_path = cache_base / split / "index.npz"
        if not index_path.exists():
            print(f"\n  WARNING: {index_path} not found, skipping")
            continue
            
        print(f"\n  Loading {split} cache index...")
        data = np.load(index_path, allow_pickle=True)
        keys = data['keys']
        shards = data['shards']
        offsets = data['offsets']
        
        for i in range(len(keys)):
            k = keys[i]
            k_str = k.decode('utf-8') if isinstance(k, bytes) else str(k)
            k_norm = k_str.replace('\\', '/')
            
            if k_norm not in all_keys:
                all_keys[k_norm] = (int(shards[i]), int(offsets[i]), split)
        
        print(f"    Added {len(keys):,} entries, total unique: {len(all_keys):,}")
    
    # Load labels
    print(f"\n  Loading labels...")
    files = np.load(labels_path, allow_pickle=True)
    n = len(files)
    print(f"    Loaded {n:,} file paths")
    
    # Generate mapping
    print(f"\n  Generating mapping...")
    start = time.time()
    
    shard_ids = np.zeros(n, dtype=np.uint16)
    offsets_arr = np.zeros(n, dtype=np.uint32)
    valid = np.zeros(n, dtype=np.bool_)
    cache_split = []  # which cache each sample is in
    
    found = 0
    train_count = 0
    val_count = 0
    
    for i in range(n):
        f = files[i]
        f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
        f_norm = f_str.replace('\\', '/')
        
        # Generate cache key
        if f_norm.startswith('lakh_'):
            cache_key = f_norm + '.pt'
        else:
            cache_key = f_norm.replace('.wav', '.pt')
        
        if cache_key in all_keys:
            shard, offset, split = all_keys[cache_key]
            shard_ids[i] = shard
            offsets_arr[i] = offset
            valid[i] = True
            cache_split.append(split)
            found += 1
            if split == 'train':
                train_count += 1
            else:
                val_count += 1
        else:
            cache_split.append('')
        
        if (i + 1) % 500_000 == 0:
            print(f"    Progress: {i+1:,}/{n:,} ({100*(i+1)/n:.1f}%) found={found:,} ({100*found/(i+1):.1f}%)")
    
    elapsed = time.time() - start
    print(f"\n  Mapping complete in {elapsed:.1f}s")
    print(f"    Found: {found:,}/{n:,} ({100*found/n:.2f}%)")
    print(f"    From train cache: {train_count:,}")
    print(f"    From val cache: {val_count:,}")
    print(f"    Misses: {n-found:,}")
    
    # Save
    print(f"\n  Saving to {output_path}...")
    np.savez_compressed(
        output_path,
        shard_ids=shard_ids,
        offsets=offsets_arr,
        valid=valid,
        cache_split=np.array(cache_split, dtype='U5')  # 'train' or 'val' or ''
    )
    print(f"    Saved {output_path.stat().st_size / 1e6:.1f} MB")
    
    if n - found > 0:
        print(f"\n  First 5 misses:")
        miss_count = 0
        for i in range(n):
            if not valid[i]:
                f = files[i]
                f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
                print(f"    [{i}] {f_str}")
                miss_count += 1
                if miss_count >= 5:
                    break
    
    print(f"\n{'='*70}")
    print(f"  DONE!")
    print(f"{'='*70}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--cache", required=True, help="Base cache directory (contains train/ and val/)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    generate_combined_mapping(args.labels, args.cache, args.output)
