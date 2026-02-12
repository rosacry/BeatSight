#!/usr/bin/env python3
"""
Generate a Direct Index Mapping for Consolidated Cache

This tool creates a mapping from dataset sample index to cache (shard, offset) pairs,
eliminating the O(log n) binary search overhead during training.

Without this mapping:
- Each sample lookup: encode path → binary search (14M entries) → read shard/offset
- ~24 string comparisons per lookup, potentially causing page faults
- Result: ~1-5 it/s on first epoch

With this mapping:
- Each sample lookup: array[idx] → (shard, offset) directly
- O(1) constant time, no string comparisons
- Result: ~30-60 it/s on first epoch

Usage:
    # Generate mapping (run once, ~5-10 minutes for 14M samples)
    python tools/generate_cache_index_mapping.py \\
        --labels data/dataset_index/train_labels_with_velocity_files.npy \\
        --cache data/feature_cache/prod_combined_warmup_consolidated/train \\
        --output data/dataset_index/train_cache_mapping.npz
    
    # Same for validation
    python tools/generate_cache_index_mapping.py \\
        --labels data/dataset_index/val_labels_with_velocity_files.npy \\
        --cache data/feature_cache/prod_combined_warmup_consolidated/val \\
        --output data/dataset_index/val_cache_mapping.npz

The mapping file contains:
- shard_ids: uint16 array of shard IDs for each sample
- offsets: uint32 array of offsets within each shard
- valid: bool array indicating if sample was found in cache

Author: BeatSight Team
License: MIT
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np


def load_cache_index(cache_dir: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load the cache binary index."""
    index_npz = cache_dir / "index.npz"
    if not index_npz.exists():
        raise FileNotFoundError(f"Cache index not found: {index_npz}")
    
    print(f"Loading cache index from {index_npz}...")
    start = time.time()
    
    # Load without mmap for faster access during mapping generation
    data = np.load(index_npz, allow_pickle=False)
    keys = data['keys']
    shards = data['shards']
    offsets = data['offsets']
    
    print(f"  Loaded {len(keys):,} entries in {time.time() - start:.1f}s")
    return keys, shards, offsets


def load_labels_files(labels_path: Path) -> np.ndarray:
    """Load the file paths from labels numpy file."""
    if not labels_path.exists():
        raise FileNotFoundError(f"Labels file not found: {labels_path}")
    
    print(f"Loading labels from {labels_path}...")
    start = time.time()
    
    # Try without pickle first, fall back to allow_pickle for object arrays
    try:
        files = np.load(labels_path, allow_pickle=False)
    except ValueError:
        files = np.load(labels_path, allow_pickle=True)
    print(f"  Loaded {len(files):,} file paths in {time.time() - start:.1f}s")
    return files


def generate_mapping(
    labels_files: np.ndarray,
    cache_keys: np.ndarray,
    cache_shards: np.ndarray,
    cache_offsets: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate mapping from label indices to cache (shard, offset) pairs.
    
    Returns:
        (shard_ids, offsets, valid) arrays
    """
    n = len(labels_files)
    print(f"Generating mapping for {n:,} samples...")
    start = time.time()
    
    shard_ids = np.zeros(n, dtype=np.uint16)
    offsets = np.zeros(n, dtype=np.uint32)
    valid = np.zeros(n, dtype=np.bool_)
    
    # Determine if files are byte strings or unicode
    is_bytes = labels_files.dtype.kind == 'S'
    cache_is_bytes = cache_keys.dtype.kind == 'S'
    
    found = 0
    for i in range(n):
        # Get file path
        file_path = labels_files[i]
        if is_bytes:
            file_path = file_path.decode('utf-8')
        else:
            file_path = str(file_path)
        
        # Normalize path: convert to forward slashes and change .wav to .pt
        normalized = file_path.replace('\\', '/').replace('/', '\\')
        if normalized.endswith('.wav'):
            normalized = normalized[:-4] + '.pt'
        elif not normalized.endswith('.pt'):
            # Try adding .pt if no extension
            base = normalized.rsplit('.', 1)[0] if '.' in normalized else normalized
            normalized = base + '.pt'
        
        # Encode for comparison
        key = normalized.encode('utf-8') if cache_is_bytes else normalized
        
        # Binary search
        idx = np.searchsorted(cache_keys, key)
        
        if idx < len(cache_keys) and cache_keys[idx] == key:
            shard_ids[i] = cache_shards[idx]
            offsets[i] = cache_offsets[idx]
            valid[i] = True
            found += 1
        
        # Progress update
        if (i + 1) % 500000 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            eta = (n - i - 1) / rate
            print(f"  Progress: {i+1:,}/{n:,} ({100*(i+1)/n:.1f}%) "
                  f"found={found:,} ({100*found/(i+1):.1f}%) "
                  f"ETA: {eta/60:.1f}min")
    
    elapsed = time.time() - start
    miss_rate = 100 * (n - found) / n
    print(f"\nMapping complete in {elapsed:.1f}s")
    print(f"  Found: {found:,}/{n:,} ({100*found/n:.1f}%)")
    print(f"  Misses: {n-found:,} ({miss_rate:.2f}%)")
    
    if miss_rate > 1.0:
        print(f"\n⚠️  High miss rate ({miss_rate:.1f}%) indicates potential issues:")
        print(f"   - Labels and cache may use different path formats")
        print(f"   - Some samples may not be in cache")
        print(f"   Check the first few misses to debug:")
        
        # Show first few misses
        miss_indices = np.where(~valid)[0][:5]
        for idx in miss_indices:
            file_path = labels_files[idx]
            if labels_files.dtype.kind == 'S':
                file_path = file_path.decode('utf-8')
            print(f"     [{idx}] {file_path}")
    
    return shard_ids, offsets, valid


def main():
    parser = argparse.ArgumentParser(
        description="Generate direct index mapping from labels to cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--labels", required=True, type=Path,
        help="Path to labels numpy file (*_files.npy)"
    )
    parser.add_argument(
        "--cache", required=True, type=Path,
        help="Path to consolidated cache directory (contains manifest.json)"
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Output path for mapping file (*.npz)"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify mapping by loading a few samples"
    )
    
    args = parser.parse_args()
    
    # Load cache index
    cache_keys, cache_shards, cache_offsets = load_cache_index(args.cache)
    
    # Load labels files
    labels_files = load_labels_files(args.labels)
    
    # Generate mapping
    shard_ids, offsets, valid = generate_mapping(
        labels_files, cache_keys, cache_shards, cache_offsets
    )
    
    # Save mapping
    print(f"\nSaving mapping to {args.output}...")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        shard_ids=shard_ids,
        offsets=offsets,
        valid=valid,
    )
    print(f"  Saved {args.output.stat().st_size / 1e6:.1f} MB")
    
    # Verify if requested
    if args.verify:
        print("\nVerifying mapping...")
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "ai-pipeline"))
        from training.utils.consolidated_cache import ConsolidatedCacheReader
        
        reader = ConsolidatedCacheReader(args.cache)
        
        # Pick a few valid samples
        valid_indices = np.where(valid)[0]
        test_indices = valid_indices[np.random.choice(len(valid_indices), min(10, len(valid_indices)), replace=False)]
        
        for idx in test_indices:
            shard = int(shard_ids[idx])
            offset = int(offsets[idx])
            
            # Read via mapping
            tensor = reader._read_sample(shard, offset)
            
            # Read via path lookup
            file_path = labels_files[idx]
            if labels_files.dtype.kind == 'S':
                file_path = file_path.decode('utf-8')
            if not file_path.endswith('.pt'):
                base = file_path.rsplit('.', 1)[0] if '.' in file_path else file_path
                file_path = base + '.pt'
            tensor2 = reader.get_by_path(file_path)
            
            if tensor2 is None:
                print(f"  [{idx}] Path lookup failed for {file_path}")
                continue
            
            # Check equality
            if torch.allclose(tensor, tensor2):
                print(f"  [{idx}] ✓ Match (shard={shard}, offset={offset})")
            else:
                print(f"  [{idx}] ✗ MISMATCH! (shard={shard}, offset={offset})")
    
    print("\n✅ Done!")
    print(f"\nTo use this mapping in training, add to train_classifier.py:")
    print(f"   --cache-mapping {args.output}")


if __name__ == "__main__":
    # Import torch only if verifying
    import torch
    main()
