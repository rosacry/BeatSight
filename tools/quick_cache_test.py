#!/usr/bin/env python3
"""Quick verification of cache reads."""

import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, "C:/github/BeatSight/ai-pipeline")

from training.utils.consolidated_cache import ConsolidatedCacheReader

DATASET = Path("F:/datasets/prod_v5_definitive")
CACHE = Path("F:/feature_cache")

print("Loading caches...")
train_cache = ConsolidatedCacheReader(CACHE / "train")
val_cache = ConsolidatedCacheReader(CACHE / "val")
print(f"  Train: {len(train_cache):,} samples, {train_cache.num_shards} shards")
print(f"  Val:   {len(val_cache):,} samples, {val_cache.num_shards} shards")

print("\nLoading train mapping...")
with np.load(DATASET / "train" / "cache_mapping.npz", allow_pickle=True) as f:
    train_shard_ids = f['shard_ids']
    train_offsets = f['offsets']
    train_valid = f['valid']
    train_cache_split = f['cache_split']
print(f"  Entries: {len(train_valid):,}")
print(f"  Valid: {np.sum(train_valid):,}")

# Test 10 reads from train
print("\nTesting 10 train reads...")
valid_indices = np.where(train_valid)[0]
for i in range(10):
    idx = valid_indices[i * 1000]  # Space them out
    shard = int(train_shard_ids[idx])
    offset = int(train_offsets[idx])
    cache_split_val = str(train_cache_split[idx])
    
    reader = val_cache if cache_split_val == 'val' else train_cache
    tensor = reader._read_sample(shard, offset)
    print(f"  {i}: idx={idx}, shard={shard}, offset={offset}, cache={cache_split_val}, shape={tensor.shape}")

print("\nLoading val mapping...")
with np.load(DATASET / "val" / "cache_mapping.npz", allow_pickle=True) as f:
    val_shard_ids = f['shard_ids']
    val_offsets = f['offsets']
    val_valid = f['valid']
    val_cache_split = f['cache_split']
print(f"  Entries: {len(val_valid):,}")
print(f"  Valid: {np.sum(val_valid):,}")

# Test 10 reads from val
print("\nTesting 10 val reads...")
valid_indices = np.where(val_valid)[0]
for i in range(10):
    idx = valid_indices[i * 1000]
    shard = int(val_shard_ids[idx])
    offset = int(val_offsets[idx])
    cache_split_val = str(val_cache_split[idx])
    
    reader = train_cache if cache_split_val == 'train' else val_cache
    tensor = reader._read_sample(shard, offset)
    print(f"  {i}: idx={idx}, shard={shard}, offset={offset}, cache={cache_split_val}, shape={tensor.shape}")

print("\n✓ All reads successful!")
