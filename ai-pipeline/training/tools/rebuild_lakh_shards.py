#!/usr/bin/env python3
"""
Rebuild Lakh shards with correct format.

The Lakh .pt files are:
- Shape: [128, 128]
- Dtype: float32
- Range: [0, 1] (normalized)

The cache expects:
- Shape: [1, 128, 128]  
- Dtype: float16
- 32-byte header per shard
- 32,768 bytes per sample (16,384 float16 values)

This script:
1. Reads all lakh_*.pt files from F:/feature_cache/
2. Converts them to the correct format
3. Writes them to shards 233+ with proper headers
4. Updates the index.npz with correct shard/offset mappings
"""

import os
import struct
import numpy as np
import torch
from pathlib import Path
from tqdm import tqdm

# Constants matching consolidated_cache.py
MAGIC_BYTES = b"BSFC"
VERSION = 2
HEADER_SIZE = 32
SAMPLES_PER_SHARD = 32768  # Match what we claimed in manifest

# Expected format
TENSOR_SHAPE = (1, 128, 128)
DTYPE = torch.float16
DTYPE_CODE = 1  # 0=float32, 1=float16
BYTES_PER_SAMPLE = 1 * 128 * 128 * 2  # 32768 bytes


def write_shard_header(f, num_samples):
    """Write the 32-byte shard header."""
    header = struct.pack(
        '<4sIIIIIII',
        MAGIC_BYTES,
        VERSION,
        num_samples,
        TENSOR_SHAPE[0],  # channels
        TENSOR_SHAPE[1],  # height (n_mels)
        TENSOR_SHAPE[2],  # width (frames)
        DTYPE_CODE,
        0  # reserved
    )
    f.write(header)


def load_and_convert_tensor(filepath):
    """Load a .pt file and convert to cache format."""
    tensor = torch.load(filepath, weights_only=True)
    
    # Add channel dimension if needed: [128, 128] -> [1, 128, 128]
    if tensor.ndim == 2:
        tensor = tensor.unsqueeze(0)
    
    # Ensure correct shape
    if tensor.shape != TENSOR_SHAPE:
        raise ValueError(f"Unexpected shape {tensor.shape}, expected {TENSOR_SHAPE}")
    
    # Convert to float16
    tensor = tensor.to(DTYPE)
    
    return tensor


def main():
    cache_dir = Path("F:/feature_cache")
    train_dir = cache_dir / "train"
    
    # Find all lakh .pt files
    print("Scanning for Lakh .pt files...")
    lakh_files = sorted([f for f in cache_dir.iterdir() 
                         if f.name.startswith('lakh_') and f.name.endswith('.pt')])
    print(f"Found {len(lakh_files)} Lakh .pt files")
    
    # Separate by class
    china_files = [f for f in lakh_files if 'china' in f.name]
    splash_files = [f for f in lakh_files if 'splash' in f.name]
    print(f"  China: {len(china_files)}")
    print(f"  Splash: {len(splash_files)}")
    
    # Load existing index
    print("\nLoading existing index...")
    index_path = train_dir / "index.npz"
    index_data = np.load(index_path, allow_pickle=False)
    old_keys = index_data['keys']
    old_shards = index_data['shards']
    old_offsets = index_data['offsets']
    
    # Find entries NOT pointing to shards 233-237 (keep original data)
    mask_keep = old_shards < 233
    print(f"Keeping {mask_keep.sum():,} entries from original shards (< 233)")
    print(f"Removing {(~mask_keep).sum():,} entries from broken shards (>= 233)")
    
    kept_keys = old_keys[mask_keep]
    kept_shards = old_shards[mask_keep]
    kept_offsets = old_offsets[mask_keep]
    
    # Delete old broken shards
    print("\nRemoving old broken shards...")
    for shard_id in range(233, 238):
        shard_path = train_dir / f"shard_{shard_id:04d}.bin"
        if shard_path.exists():
            shard_path.unlink()
            print(f"  Deleted {shard_path.name}")
    
    # Create new shards
    print("\nCreating new shards with correct format...")
    
    new_keys = []
    new_shards = []
    new_offsets = []
    
    current_shard_id = 233
    current_offset = 0
    current_shard_file = None
    current_shard_samples = 0
    
    def start_new_shard():
        nonlocal current_shard_file, current_shard_id, current_offset, current_shard_samples
        if current_shard_file is not None:
            # Update header with actual sample count and close
            current_shard_file.seek(0)
            write_shard_header(current_shard_file, current_shard_samples)
            current_shard_file.close()
            print(f"  Finished shard_{current_shard_id:04d}.bin: {current_shard_samples} samples")
            current_shard_id += 1
        
        shard_path = train_dir / f"shard_{current_shard_id:04d}.bin"
        current_shard_file = open(shard_path, 'wb')
        write_shard_header(current_shard_file, 0)  # Placeholder, will update
        current_offset = 0
        current_shard_samples = 0
    
    start_new_shard()
    
    # Process all lakh files
    for pt_file in tqdm(lakh_files, desc="Processing Lakh files"):
        try:
            tensor = load_and_convert_tensor(pt_file)
        except Exception as e:
            print(f"\nWarning: Failed to load {pt_file.name}: {e}")
            continue
        
        # Write to current shard
        tensor_bytes = tensor.numpy().tobytes()
        current_shard_file.write(tensor_bytes)
        
        # Record in index (use backslash path format to match existing)
        # Key format: lakh_china_xxxx.pt (without directory)
        key = pt_file.name.encode('utf-8')
        new_keys.append(key)
        new_shards.append(current_shard_id)
        new_offsets.append(current_offset)
        
        current_offset += 1
        current_shard_samples += 1
        
        # Start new shard if full
        if current_shard_samples >= SAMPLES_PER_SHARD:
            start_new_shard()
    
    # Close final shard
    if current_shard_file is not None:
        current_shard_file.seek(0)
        write_shard_header(current_shard_file, current_shard_samples)
        current_shard_file.close()
        print(f"  Finished shard_{current_shard_id:04d}.bin: {current_shard_samples} samples")
    
    # Merge indices
    print(f"\nMerging indices...")
    print(f"  Original entries (shards < 233): {len(kept_keys):,}")
    print(f"  New Lakh entries: {len(new_keys):,}")
    
    # Convert new keys to fixed-length format matching original
    key_dtype = kept_keys.dtype
    max_len = key_dtype.itemsize
    new_keys_padded = np.array([k.ljust(max_len, b'\x00')[:max_len] for k in new_keys], dtype=key_dtype)
    
    all_keys = np.concatenate([kept_keys, new_keys_padded])
    all_shards = np.concatenate([kept_shards, np.array(new_shards, dtype=kept_shards.dtype)])
    all_offsets = np.concatenate([kept_offsets, np.array(new_offsets, dtype=kept_offsets.dtype)])
    
    # Sort by key for binary search
    print("Sorting index for binary search...")
    sort_idx = np.argsort(all_keys)
    all_keys = all_keys[sort_idx]
    all_shards = all_shards[sort_idx]
    all_offsets = all_offsets[sort_idx]
    
    # Save new index
    print(f"Saving index with {len(all_keys):,} entries...")
    np.savez(
        train_dir / "index.npz",
        keys=all_keys,
        shards=all_shards,
        offsets=all_offsets
    )
    
    # Update manifest
    print("\nUpdating manifest...")
    import json
    manifest_path = train_dir / "manifest.json"
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    # Update shard list
    new_shard_entries = []
    for shard_id in range(233, current_shard_id + 1):
        shard_path = train_dir / f"shard_{shard_id:04d}.bin"
        if shard_path.exists():
            # Read header to get sample count
            with open(shard_path, 'rb') as f:
                header = f.read(HEADER_SIZE)
            _, _, num_samples, _, _, _, _, _ = struct.unpack('<4sIIIIIII', header)
            new_shard_entries.append({
                "shard_id": shard_id,
                "filename": f"shard_{shard_id:04d}.bin",
                "num_samples": num_samples
            })
    
    # Replace shards >= 233
    manifest['shards'] = [s for s in manifest['shards'] if s['shard_id'] < 233] + new_shard_entries
    manifest['total_samples'] = sum(s['num_samples'] for s in manifest['shards'])
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nDone!")
    print(f"Total shards: {len(manifest['shards'])}")
    print(f"Total samples in cache: {manifest['total_samples']:,}")
    
    # Verify
    print("\n=== Verification ===")
    for shard_id in range(233, current_shard_id + 1):
        shard_path = train_dir / f"shard_{shard_id:04d}.bin"
        if shard_path.exists():
            size = shard_path.stat().st_size
            with open(shard_path, 'rb') as f:
                header = f.read(HEADER_SIZE)
            magic, ver, num, c, h, w, dtype, _ = struct.unpack('<4sIIIIIII', header)
            expected_size = HEADER_SIZE + num * BYTES_PER_SAMPLE
            status = "✅" if size == expected_size else f"❌ (expected {expected_size:,})"
            print(f"Shard {shard_id}: {num:,} samples, {size:,} bytes {status}")


if __name__ == "__main__":
    main()
