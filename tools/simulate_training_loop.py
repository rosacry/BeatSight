#!/usr/bin/env python3
"""
Final verification: Simulate exactly what the training loop does.
Test the EXACT paths the code takes.
"""

import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, "C:/github/BeatSight/ai-pipeline")

from training.utils.consolidated_cache import ConsolidatedCacheReader

DATASET = Path("F:/datasets/prod_v5_definitive")
CACHE = Path("F:/feature_cache")

CLASS_NAMES = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
               'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']

print("="*80)
print("  SIMULATION OF TRAINING LOOP")
print("="*80)

# Load exactly as train_classifier.py does
print("\nLoading caches...")
train_cache = ConsolidatedCacheReader(CACHE / "train")
val_cache = ConsolidatedCacheReader(CACHE / "val")

print("\nLoading train data...")
train_labels = np.load(DATASET / "train" / "train_labels_labels.npy")

print("\nLoading train cache mapping (as train_classifier does)...")
with np.load(DATASET / "train" / "cache_mapping.npz", allow_pickle=True) as f:
    train_mapping_shards = f['shard_ids']
    train_mapping_offsets = f['offsets']
    train_mapping_valid = f['valid']
    train_mapping_split = f['cache_split'] if 'cache_split' in f.files else None

print(f"  Total samples: {len(train_labels):,}")
print(f"  Cache mapping: {len(train_mapping_valid):,} entries")
print(f"  Has cache_split: {train_mapping_split is not None}")

# Simulate __getitem__ for random indices across all classes
print("\n" + "="*80)
print("  SIMULATING __getitem__ CALLS")
print("="*80)

np.random.seed(12345)
n_samples_per_class = 100

for class_idx, class_name in enumerate(CLASS_NAMES):
    # Get indices for this class
    class_indices = np.where(train_labels == class_idx)[0]
    n_test = min(n_samples_per_class, len(class_indices))
    test_indices = np.random.choice(class_indices, size=n_test, replace=False)
    
    success = 0
    fail = 0
    from_train_cache = 0
    from_val_cache = 0
    
    for idx in test_indices:
        # Exactly as in train_classifier.py
        if train_mapping_valid[idx]:
            shard_id = int(train_mapping_shards[idx])
            offset = int(train_mapping_offsets[idx])
            
            # Select correct cache reader based on cache_split
            reader = train_cache
            if train_mapping_split is not None:
                sample_split = str(train_mapping_split[idx])
                current_cache_is_train = True  # We're training
                if (current_cache_is_train and sample_split == 'val') or \
                   (not current_cache_is_train and sample_split == 'train'):
                    reader = val_cache
                    from_val_cache += 1
                else:
                    from_train_cache += 1
            
            try:
                features = reader._read_sample(shard_id, offset)
                if features is not None and features.shape == (1, 128, 128):
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
        else:
            fail += 1
    
    status = "✓" if fail == 0 else f"❌ {fail} failed"
    print(f"  {class_name:<15} {success:>3}/{n_test:>3} | train_cache: {from_train_cache:>3} | val_cache: {from_val_cache:>3} | {status}")

# Now test val split too
print("\n" + "="*80)
print("  SIMULATING VAL SPLIT __getitem__ CALLS")
print("="*80)

print("\nLoading val data...")
val_labels = np.load(DATASET / "val" / "val_labels_labels.npy")

with np.load(DATASET / "val" / "cache_mapping.npz", allow_pickle=True) as f:
    val_mapping_shards = f['shard_ids']
    val_mapping_offsets = f['offsets']
    val_mapping_valid = f['valid']
    val_mapping_split = f['cache_split'] if 'cache_split' in f.files else None

for class_idx, class_name in enumerate(CLASS_NAMES):
    # Get indices for this class
    class_indices = np.where(val_labels == class_idx)[0]
    n_test = min(n_samples_per_class, len(class_indices))
    test_indices = np.random.choice(class_indices, size=n_test, replace=False)
    
    success = 0
    fail = 0
    from_train_cache = 0
    from_val_cache = 0
    
    for idx in test_indices:
        if val_mapping_valid[idx]:
            shard_id = int(val_mapping_shards[idx])
            offset = int(val_mapping_offsets[idx])
            
            # For val split, we still use dual cache
            # Note: val split uses val as primary, train as alt
            reader = val_cache
            if val_mapping_split is not None:
                sample_split = str(val_mapping_split[idx])
                # For val split, the primary cache is val
                current_cache_is_train = False  # We're validating
                if (current_cache_is_train and sample_split == 'val') or \
                   (not current_cache_is_train and sample_split == 'train'):
                    reader = train_cache  # Use train cache for 'train' samples
                    from_train_cache += 1
                else:
                    from_val_cache += 1
            
            try:
                features = reader._read_sample(shard_id, offset)
                if features is not None and features.shape == (1, 128, 128):
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
        else:
            fail += 1
    
    status = "✓" if fail == 0 else f"❌ {fail} failed"
    print(f"  {class_name:<15} {success:>3}/{n_test:>3} | train_cache: {from_train_cache:>3} | val_cache: {from_val_cache:>3} | {status}")

print("\n" + "="*80)
print("  ✅ TRAINING LOOP SIMULATION COMPLETE")
print("="*80)
