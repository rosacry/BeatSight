#!/usr/bin/env python3
"""
Convert JSON cache index to binary (NPZ) format for memory-efficient loading.

The binary format allows memory-mapped loading, so multiple DataLoader workers
can share the same index data instead of each loading 1GB+ into RAM.

Usage:
    python tools/convert_cache_index_to_binary.py F:/feature_cache/train
    python tools/convert_cache_index_to_binary.py F:/feature_cache/val

This converts index.json to index.npz in each cache directory.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np


def convert_index(cache_dir: Path, verbose: bool = True) -> None:
    """Convert JSON index to sorted binary NPZ format."""
    index_json = cache_dir / "index.json"
    index_npz = cache_dir / "index.npz"
    
    if not index_json.exists():
        raise FileNotFoundError(f"index.json not found in {cache_dir}")
    
    if index_npz.exists():
        print(f"[SKIP] {index_npz} already exists. Delete it first to regenerate.")
        return
    
    # Load JSON index
    print(f"[1/4] Loading {index_json}...")
    start = time.time()
    with open(index_json) as f:
        index = json.load(f)
    print(f"       Loaded {len(index):,} entries in {time.time() - start:.1f}s")
    
    # Extract and sort keys
    print(f"[2/4] Sorting {len(index):,} keys...")
    start = time.time()
    sorted_keys = sorted(index.keys())
    print(f"       Sorted in {time.time() - start:.1f}s")
    
    # Build arrays
    print(f"[3/4] Building binary arrays...")
    start = time.time()
    
    # Encode keys as fixed-length byte strings
    # Find max key length
    max_len = max(len(k.encode('utf-8')) for k in sorted_keys)
    print(f"       Max key length: {max_len} bytes")
    
    # Create arrays
    n = len(sorted_keys)
    keys_array = np.zeros(n, dtype=f'S{max_len}')
    shards_array = np.zeros(n, dtype=np.uint16)
    offsets_array = np.zeros(n, dtype=np.uint32)
    
    for i, key in enumerate(sorted_keys):
        keys_array[i] = key.encode('utf-8')
        entry = index[key]
        # Handle both formats: [shard, offset] or {'shard': X, 'offset': Y}
        if isinstance(entry, list):
            shards_array[i] = entry[0]
            offsets_array[i] = entry[1]
        else:
            shards_array[i] = entry['shard']
            offsets_array[i] = entry['offset']
        
        if verbose and i > 0 and i % 1_000_000 == 0:
            print(f"       Processed {i:,}/{n:,} entries...")
    
    print(f"       Built arrays in {time.time() - start:.1f}s")
    
    # Save as NPZ
    print(f"[4/4] Saving {index_npz}...")
    start = time.time()
    np.savez(
        index_npz,
        keys=keys_array,
        shards=shards_array,
        offsets=offsets_array,
    )
    
    # Report sizes
    json_size = index_json.stat().st_size / (1024 * 1024)
    npz_size = index_npz.stat().st_size / (1024 * 1024)
    print(f"       Saved in {time.time() - start:.1f}s")
    print(f"       JSON size: {json_size:.1f} MB")
    print(f"       NPZ size:  {npz_size:.1f} MB ({npz_size/json_size*100:.1f}% of JSON)")
    print(f"\n[DONE] Binary index created: {index_npz}")
    print(f"       Workers will now use memory-mapped loading (shared across processes)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert cache JSON index to binary NPZ format"
    )
    parser.add_argument(
        "cache_dir",
        type=Path,
        help="Path to cache directory containing index.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing index.npz",
    )
    
    args = parser.parse_args()
    
    if args.force:
        npz_path = args.cache_dir / "index.npz"
        if npz_path.exists():
            print(f"[FORCE] Removing existing {npz_path}")
            npz_path.unlink()
    
    convert_index(args.cache_dir)


if __name__ == "__main__":
    main()
