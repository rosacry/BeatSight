#!/usr/bin/env python3
"""
Convert large JSON label files to sharded pickle format for memory-efficient loading.

For very large datasets (14M+ samples), creates multiple shards that can be loaded
sequentially or memory-mapped.

Usage:
    python tools/convert_labels_to_pickle.py data/dataset_index/train_labels.json
    python tools/convert_labels_to_pickle.py data/dataset_index/val_labels.json
"""

import pickle
import sys
from pathlib import Path

try:
    import ijson
    USE_STREAMING = True
except ImportError:
    print("Warning: ijson not installed, falling back to json.load (may OOM for large files)")
    import json
    USE_STREAMING = False

# Shard size: 1M items per shard keeps memory under ~2GB per shard
SHARD_SIZE = 1_000_000


def convert_json_to_sharded_pickle(json_path: Path, output_dir: Path) -> int:
    """Convert large JSON to sharded pickle files."""
    print(f"Converting {json_path} to sharded pickles in {output_dir}...")
    print(f"  Input size: {json_path.stat().st_size / 1e9:.2f} GB")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    shard_items = []
    shard_idx = 0
    total_items = 0
    
    def save_shard():
        nonlocal shard_items, shard_idx
        if not shard_items:
            return
        shard_path = output_dir / f"shard_{shard_idx:04d}.pkl"
        with open(shard_path, 'wb') as f:
            pickle.dump(shard_items, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"    Saved shard {shard_idx}: {len(shard_items):,} items ({shard_path.stat().st_size / 1e6:.1f} MB)")
        shard_items = []
        shard_idx += 1
    
    if USE_STREAMING:
        with open(json_path, 'rb') as f:
            parser = ijson.items(f, 'item')
            for i, item in enumerate(parser):
                shard_items.append(item)
                total_items += 1
                
                if len(shard_items) >= SHARD_SIZE:
                    save_shard()
                
                if (i + 1) % 1000000 == 0:
                    print(f"  Processed {i+1:,} items...")
    else:
        with open(json_path, 'r', encoding='utf-8') as f:
            items = json.load(f)
        for i, item in enumerate(items):
            shard_items.append(item)
            total_items += 1
            if len(shard_items) >= SHARD_SIZE:
                save_shard()
    
    # Save final partial shard
    save_shard()
    
    # Save metadata
    meta = {
        'total_items': total_items,
        'num_shards': shard_idx,
        'shard_size': SHARD_SIZE,
        'source': str(json_path),
    }
    meta_path = output_dir / "meta.pkl"
    with open(meta_path, 'wb') as f:
        pickle.dump(meta, f)
    
    print(f"  Done! {total_items:,} items in {shard_idx} shards")
    return total_items


def load_sharded_pickle(shard_dir: Path) -> list:
    """Load all shards back into a single list."""
    meta_path = shard_dir / "meta.pkl"
    with open(meta_path, 'rb') as f:
        meta = pickle.load(f)
    
    items = []
    for i in range(meta['num_shards']):
        shard_path = shard_dir / f"shard_{i:04d}.pkl"
        with open(shard_path, 'rb') as f:
            items.extend(pickle.load(f))
    
    return items


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_labels_to_pickle.py <json_file> [output_dir]")
        sys.exit(1)
    
    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Error: {json_path} does not exist")
        sys.exit(1)
    
    if len(sys.argv) >= 3:
        output_dir = Path(sys.argv[2])
    else:
        output_dir = json_path.parent / (json_path.stem + "_shards")
    
    convert_json_to_sharded_pickle(json_path, output_dir)


if __name__ == "__main__":
    main()
