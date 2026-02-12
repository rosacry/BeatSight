#!/usr/bin/env python3
"""
Add lakh synthesis entries to the cache index with .pt suffix.

This script reads the consolidated shards 231 and 232 to get the correct
sample IDs (which we used when consolidating), and adds them to the index
with .pt suffix so the training code can find them.
"""

import json
import struct
import time
from pathlib import Path


def read_shard_keys(shard_path: Path) -> list[tuple[str, int]]:
    """Read sample keys from a consolidated shard file.
    
    The shard format is:
    - Header: magic (4 bytes), version (4 bytes), num_samples (4 bytes)
    - For each sample: key_len (4 bytes), key (key_len bytes), data_len (4 bytes), data (data_len bytes)
    
    Returns list of (key, offset) tuples.
    """
    keys = []
    with open(shard_path, 'rb') as f:
        # Read header
        magic = f.read(4)
        if magic != b'CONS':
            raise ValueError(f"Invalid shard magic: {magic}")
        version = struct.unpack('<I', f.read(4))[0]
        num_samples = struct.unpack('<I', f.read(4))[0]
        
        print(f"  Shard: {shard_path.name}, version={version}, samples={num_samples}")
        
        # Read each sample's key
        for i in range(num_samples):
            key_len = struct.unpack('<I', f.read(4))[0]
            key = f.read(key_len).decode('utf-8')
            data_len = struct.unpack('<I', f.read(4))[0]
            # Skip the data
            f.seek(data_len, 1)
            
            keys.append((key, i))
            
            if (i + 1) % 10000 == 0:
                print(f"    Read {i+1}/{num_samples} keys...")
    
    return keys


def main():
    cache_dir = Path("F:/feature_cache/train")
    index_path = cache_dir / "index.json"
    
    # Load existing index
    print(f"Loading index from {index_path}...")
    start = time.time()
    with open(index_path) as f:
        index = json.load(f)
    print(f"  Loaded {len(index):,} entries in {time.time()-start:.1f}s")
    
    # Check for existing lakh entries
    existing_lakh = sum(1 for k in index if k.startswith('lakh_'))
    print(f"  Existing lakh entries: {existing_lakh:,}")
    
    # Read keys from synthesis shards
    shard_231 = cache_dir / "shard_0231.bin"
    shard_232 = cache_dir / "shard_0232.bin"
    
    if not shard_231.exists():
        print(f"ERROR: {shard_231} not found!")
        return
    if not shard_232.exists():
        print(f"ERROR: {shard_232} not found!")
        return
    
    print(f"\nReading shard 231...")
    keys_231 = read_shard_keys(shard_231)
    
    print(f"\nReading shard 232...")
    keys_232 = read_shard_keys(shard_232)
    
    # Add to index with .pt suffix
    print(f"\nAdding entries to index...")
    added = 0
    
    for key, offset in keys_231:
        new_key = key if key.endswith('.pt') else f"{key}.pt"
        if new_key not in index:
            index[new_key] = [231, offset]
            added += 1
    
    for key, offset in keys_232:
        new_key = key if key.endswith('.pt') else f"{key}.pt"
        if new_key not in index:
            index[new_key] = [232, offset]
            added += 1
    
    print(f"  Added {added:,} new entries")
    print(f"  Total entries: {len(index):,}")
    
    # Save index
    print(f"\nSaving index...")
    start = time.time()
    
    # Backup first
    backup_path = index_path.with_suffix('.json.bak_lakh_fix')
    import shutil
    shutil.copy(index_path, backup_path)
    print(f"  Backed up to {backup_path}")
    
    with open(index_path, 'w') as f:
        json.dump(index, f)
    print(f"  Saved in {time.time()-start:.1f}s")
    
    # Verify
    test_key = 'lakh_splash_8f1331c15bec.pt'
    print(f"\nVerification: {test_key} in index: {test_key in index}")
    
    # Also regenerate binary index
    print("\n" + "="*60)
    print("IMPORTANT: Now regenerate the binary index:")
    print("  python tools/convert_cache_index_to_binary.py F:/feature_cache/train --force")
    print("="*60)


if __name__ == "__main__":
    main()
