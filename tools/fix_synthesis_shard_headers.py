#!/usr/bin/env python3
"""
Add BSFC header to raw synthesis shards.

The synthesis shards were created without headers, but the consolidated
cache reader expects the BSFC format with a 32-byte header.
"""

import struct
import shutil
from pathlib import Path

# From consolidated_cache.py
MAGIC_BYTES = b"BSFC"  # BeatSight Feature Cache
VERSION = 2
HEADER_SIZE = 32

# Feature shape
TENSOR_SHAPE = (128, 128)  # mel spectrogram shape
BYTES_PER_SAMPLE = 128 * 128 * 4  # float32


def add_header_to_shard(shard_path: Path, num_samples: int):
    """Add BSFC header to a raw shard file."""
    
    # Read the raw data
    print(f"Reading {shard_path}...")
    raw_data = shard_path.read_bytes()
    print(f"  Size: {len(raw_data):,} bytes")
    
    # Create header
    dtype_code = 0  # float32
    header = struct.pack(
        "<4sIIIIIII",
        MAGIC_BYTES,
        VERSION,
        num_samples,
        1,  # channels (single channel mel)
        TENSOR_SHAPE[0],  # height
        TENSOR_SHAPE[1],  # width
        dtype_code,
        0,  # reserved
    )
    assert len(header) == HEADER_SIZE, f"Header size mismatch: {len(header)} != {HEADER_SIZE}"
    
    # Backup original
    backup_path = shard_path.with_suffix('.bin.raw_backup')
    print(f"  Backing up to {backup_path.name}...")
    shutil.copy(shard_path, backup_path)
    
    # Write header + data
    print(f"  Writing with header...")
    with open(shard_path, 'wb') as f:
        f.write(header)
        f.write(raw_data)
    
    new_size = shard_path.stat().st_size
    print(f"  New size: {new_size:,} bytes (+{HEADER_SIZE} header)")


def main():
    cache_dir = Path("F:/feature_cache/train")
    
    # Shard 231: 65536 samples
    shard_231 = cache_dir / "shard_0231.bin"
    if shard_231.exists():
        # Check if already has header (magic bytes)
        with open(shard_231, 'rb') as f:
            magic = f.read(4)
        
        if magic == MAGIC_BYTES:
            print(f"{shard_231.name} already has BSFC header")
        else:
            print(f"{shard_231.name} needs header (magic={magic})")
            add_header_to_shard(shard_231, 65536)
    else:
        print(f"ERROR: {shard_231} not found!")
        return
    
    # Shard 232: 34120 samples
    shard_232 = cache_dir / "shard_0232.bin"
    if shard_232.exists():
        with open(shard_232, 'rb') as f:
            magic = f.read(4)
        
        if magic == MAGIC_BYTES:
            print(f"{shard_232.name} already has BSFC header")
        else:
            print(f"{shard_232.name} needs header (magic={magic})")
            add_header_to_shard(shard_232, 34120)
    else:
        print(f"ERROR: {shard_232} not found!")
        return
    
    print("\nDone! Now you need to add lakh entries to index.json with .pt suffix")


if __name__ == "__main__":
    main()
