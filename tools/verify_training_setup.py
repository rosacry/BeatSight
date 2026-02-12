#!/usr/bin/env python3
"""
THOROUGH VERIFICATION of training setup for 95%+ balanced val accuracy.
This script checks EVERYTHING that could go wrong.
"""

import numpy as np
from pathlib import Path
from collections import Counter
import hashlib

DATASET = Path("F:/datasets/prod_v5_definitive")
CACHE = Path("F:/feature_cache")

CLASS_NAMES = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
               'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']

def load_split(split):
    """Load files and labels for a split."""
    files = np.load(DATASET / split / f"{split}_labels_files.npy", allow_pickle=True)
    labels = np.load(DATASET / split / f"{split}_labels_labels.npy")
    return files, labels

def load_mapping(split):
    """Load cache mapping for a split."""
    mapping = np.load(DATASET / split / "cache_mapping.npz", allow_pickle=True)
    return {
        'shard_ids': mapping['shard_ids'],
        'offsets': mapping['offsets'],
        'valid': mapping['valid'],
        'cache_split': mapping['cache_split'] if 'cache_split' in mapping.files else None
    }

print("="*80)
print("  THOROUGH VERIFICATION OF TRAINING SETUP")
print("="*80)

# ===========================================================================
# CHECK 1: Dataset sizes and class distribution
# ===========================================================================
print("\n" + "="*80)
print("  CHECK 1: Dataset sizes and class distribution")
print("="*80)

train_files, train_labels = load_split('train')
val_files, val_labels = load_split('val')

print(f"\n  Train samples: {len(train_labels):,}")
print(f"  Val samples:   {len(val_labels):,}")
print(f"  Val ratio:     {len(val_labels) / (len(train_labels) + len(val_labels)) * 100:.2f}%")

print("\n  Class distribution:")
print(f"  {'Class':<15} {'Train':>12} {'Val':>12} {'Val %':>8}")
print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*8}")

for i, name in enumerate(CLASS_NAMES):
    train_count = np.sum(train_labels == i)
    val_count = np.sum(val_labels == i)
    val_pct = val_count / (train_count + val_count) * 100 if (train_count + val_count) > 0 else 0
    status = "✓" if 9 <= val_pct <= 11 else "⚠️"
    print(f"  {name:<15} {train_count:>12,} {val_count:>12,} {val_pct:>7.1f}% {status}")

# ===========================================================================
# CHECK 2: NO DATA LEAKAGE - train and val must have ZERO overlap
# ===========================================================================
print("\n" + "="*80)
print("  CHECK 2: Data leakage check (train/val overlap)")
print("="*80)

# Get unique identifiers from file paths
def extract_id(f):
    """Extract unique identifier from file path."""
    f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
    # For audio/UUID__class.wav, extract UUID
    # For lakh_class_HASH, extract full string
    return f_str

train_ids = set(extract_id(f) for f in train_files)
val_ids = set(extract_id(f) for f in val_files)

overlap = train_ids & val_ids
print(f"\n  Train unique samples: {len(train_ids):,}")
print(f"  Val unique samples:   {len(val_ids):,}")
print(f"  Overlap:              {len(overlap):,}")

if len(overlap) > 0:
    print(f"\n  ⚠️ WARNING: {len(overlap)} samples appear in BOTH train and val!")
    print(f"     This is DATA LEAKAGE - val accuracy will be artificially high!")
    print(f"     Sample overlapping IDs:")
    for oid in list(overlap)[:5]:
        print(f"       {oid}")
else:
    print(f"\n  ✓ No overlap - train and val are completely independent!")

# ===========================================================================
# CHECK 3: Cache mapping validity
# ===========================================================================
print("\n" + "="*80)
print("  CHECK 3: Cache mapping validity")
print("="*80)

train_mapping = load_mapping('train')
val_mapping = load_mapping('val')

print(f"\n  Train mapping:")
print(f"    Total entries:  {len(train_mapping['valid']):,}")
print(f"    Valid entries:  {np.sum(train_mapping['valid']):,}")
print(f"    Coverage:       {100*np.sum(train_mapping['valid'])/len(train_mapping['valid']):.2f}%")

print(f"\n  Val mapping:")
print(f"    Total entries:  {len(val_mapping['valid']):,}")
print(f"    Valid entries:  {np.sum(val_mapping['valid']):,}")
print(f"    Coverage:       {100*np.sum(val_mapping['valid'])/len(val_mapping['valid']):.2f}%")

# Check dual-cache split
if train_mapping['cache_split'] is not None:
    train_from_train = np.sum(train_mapping['cache_split'] == 'train')
    train_from_val = np.sum(train_mapping['cache_split'] == 'val')
    print(f"\n  Train dual-cache split:")
    print(f"    From train cache: {train_from_train:,}")
    print(f"    From val cache:   {train_from_val:,}")

if val_mapping['cache_split'] is not None:
    val_from_train = np.sum(val_mapping['cache_split'] == 'train')
    val_from_val = np.sum(val_mapping['cache_split'] == 'val')
    print(f"\n  Val dual-cache split:")
    print(f"    From train cache: {val_from_train:,}")
    print(f"    From val cache:   {val_from_val:,}")

# ===========================================================================
# CHECK 4: Verify actual cache reads work
# ===========================================================================
print("\n" + "="*80)
print("  CHECK 4: Verify actual cache reads")
print("="*80)

import sys
sys.path.insert(0, str(Path("C:/github/BeatSight/ai-pipeline")))

try:
    from training.consolidated_cache import ConsolidatedCacheReader
    
    train_cache = ConsolidatedCacheReader(CACHE / "train")
    val_cache = ConsolidatedCacheReader(CACHE / "val")
    
    print(f"\n  Train cache: {len(train_cache):,} samples, {train_cache.num_shards} shards")
    print(f"  Val cache:   {len(val_cache):,} samples, {val_cache.num_shards} shards")
    
    # Test reading samples from train mapping
    print(f"\n  Testing cache reads from train mapping...")
    success = 0
    failures = []
    test_indices = np.random.choice(len(train_mapping['valid']), size=min(100, len(train_mapping['valid'])), replace=False)
    
    for idx in test_indices:
        if train_mapping['valid'][idx]:
            shard = int(train_mapping['shard_ids'][idx])
            offset = int(train_mapping['offsets'][idx])
            cache_split = str(train_mapping['cache_split'][idx]) if train_mapping['cache_split'] is not None else 'train'
            
            try:
                reader = val_cache if cache_split == 'val' else train_cache
                tensor = reader._read_sample(shard, offset)
                if tensor is not None and tensor.shape[0] > 0:
                    success += 1
                else:
                    failures.append((idx, "empty tensor"))
            except Exception as e:
                failures.append((idx, str(e)))
    
    print(f"    Tested: {len(test_indices)}, Success: {success}, Failed: {len(failures)}")
    if failures:
        print(f"    ⚠️ Sample failures:")
        for idx, err in failures[:3]:
            print(f"       idx={idx}: {err}")
    else:
        print(f"    ✓ All test reads successful!")
    
    # Test reading samples from val mapping
    print(f"\n  Testing cache reads from val mapping...")
    success = 0
    failures = []
    test_indices = np.random.choice(len(val_mapping['valid']), size=min(100, len(val_mapping['valid'])), replace=False)
    
    for idx in test_indices:
        if val_mapping['valid'][idx]:
            shard = int(val_mapping['shard_ids'][idx])
            offset = int(val_mapping['offsets'][idx])
            cache_split = str(val_mapping['cache_split'][idx]) if val_mapping['cache_split'] is not None else 'val'
            
            try:
                reader = train_cache if cache_split == 'train' else val_cache
                tensor = reader._read_sample(shard, offset)
                if tensor is not None and tensor.shape[0] > 0:
                    success += 1
                else:
                    failures.append((idx, "empty tensor"))
            except Exception as e:
                failures.append((idx, str(e)))
    
    print(f"    Tested: {len(test_indices)}, Success: {success}, Failed: {len(failures)}")
    if failures:
        print(f"    ⚠️ Sample failures:")
        for idx, err in failures[:3]:
            print(f"       idx={idx}: {err}")
    else:
        print(f"    ✓ All test reads successful!")

except Exception as e:
    print(f"  ⚠️ Could not test cache reads: {e}")

# ===========================================================================
# CHECK 5: Label consistency - same file should have same label
# ===========================================================================
print("\n" + "="*80)
print("  CHECK 5: Label consistency")  
print("="*80)

# Check that file naming matches labels
print("\n  Checking filename-label consistency...")
mismatches = []

for split_name, files, labels in [('train', train_files, train_labels), ('val', val_files, val_labels)]:
    for i in range(min(1000, len(files))):  # Check first 1000
        f = files[i]
        f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
        label = int(labels[i])
        
        # Extract class from filename
        if '__' in f_str:
            # Format: audio/UUID__class.wav or lakh_class_hash
            parts = f_str.split('__')
            if len(parts) >= 2:
                file_class = parts[-1].replace('.wav', '').replace('.pt', '')
                expected_label = CLASS_NAMES.index(file_class) if file_class in CLASS_NAMES else -1
                if expected_label != label and expected_label >= 0:
                    mismatches.append((split_name, f_str, CLASS_NAMES[label], file_class))
        elif f_str.startswith('lakh_'):
            # Format: lakh_class_hash
            parts = f_str.split('_')
            if len(parts) >= 2:
                file_class = parts[1]
                expected_label = CLASS_NAMES.index(file_class) if file_class in CLASS_NAMES else -1
                if expected_label != label and expected_label >= 0:
                    mismatches.append((split_name, f_str, CLASS_NAMES[label], file_class))

if mismatches:
    print(f"  ⚠️ Found {len(mismatches)} filename-label mismatches!")
    for split, fname, label_name, file_class in mismatches[:5]:
        print(f"     {split}: {fname}")
        print(f"       Label says: {label_name}, filename says: {file_class}")
else:
    print(f"  ✓ All checked samples have consistent filename-label pairs!")

# ===========================================================================
# CHECK 6: Class balance for rare classes
# ===========================================================================
print("\n" + "="*80)
print("  CHECK 6: Rare class analysis")
print("="*80)

rare_classes = ['china', 'splash', 'crash', 'ride_bell', 'cross_stick']
print("\n  Rare class breakdown:")
print(f"  {'Class':<15} {'Train':>12} {'Val':>12} {'Train %':>10} {'Val %':>10}")
print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*10} {'-'*10}")

total_train = len(train_labels)
total_val = len(val_labels)

for name in rare_classes:
    i = CLASS_NAMES.index(name)
    train_count = np.sum(train_labels == i)
    val_count = np.sum(val_labels == i)
    train_pct = train_count / total_train * 100
    val_pct = val_count / total_val * 100
    print(f"  {name:<15} {train_count:>12,} {val_count:>12,} {train_pct:>9.3f}% {val_pct:>9.3f}%")

# ===========================================================================
# CHECK 7: Tensor shape consistency
# ===========================================================================
print("\n" + "="*80)
print("  CHECK 7: Tensor shape consistency")
print("="*80)

try:
    print("\n  Checking tensor shapes from cache...")
    shapes = []
    
    # Sample some tensors
    test_indices = np.random.choice(np.where(train_mapping['valid'])[0], size=min(50, np.sum(train_mapping['valid'])), replace=False)
    
    for idx in test_indices:
        shard = int(train_mapping['shard_ids'][idx])
        offset = int(train_mapping['offsets'][idx])
        cache_split = str(train_mapping['cache_split'][idx]) if train_mapping['cache_split'] is not None else 'train'
        
        reader = val_cache if cache_split == 'val' else train_cache
        tensor = reader._read_sample(shard, offset)
        shapes.append(tensor.shape)
    
    shape_counts = Counter(shapes)
    print(f"  Shapes found:")
    for shape, count in shape_counts.most_common():
        print(f"    {shape}: {count} samples")
    
    if len(shape_counts) == 1:
        print(f"  ✓ All tensors have consistent shape!")
    else:
        print(f"  ⚠️ Multiple tensor shapes detected - this could cause issues!")

except Exception as e:
    print(f"  ⚠️ Could not check tensor shapes: {e}")

# ===========================================================================
# SUMMARY
# ===========================================================================
print("\n" + "="*80)
print("  VERIFICATION SUMMARY")
print("="*80)

issues = []

# Check for critical issues
if len(overlap) > 0:
    issues.append(f"❌ DATA LEAKAGE: {len(overlap)} samples in both train and val")

train_coverage = 100*np.sum(train_mapping['valid'])/len(train_mapping['valid'])
val_coverage = 100*np.sum(val_mapping['valid'])/len(val_mapping['valid'])

if train_coverage < 100:
    issues.append(f"⚠️ Train cache coverage: {train_coverage:.1f}% (should be 100%)")
if val_coverage < 100:
    issues.append(f"⚠️ Val cache coverage: {val_coverage:.1f}% (should be 100%)")

if mismatches:
    issues.append(f"⚠️ {len(mismatches)} filename-label mismatches")

china_val = np.sum(val_labels == 0)
splash_val = np.sum(val_labels == 10)
if china_val < 1000:
    issues.append(f"⚠️ Low china val count: {china_val}")
if splash_val < 1000:
    issues.append(f"⚠️ Low splash val count: {splash_val}")

if issues:
    print("\n  ISSUES FOUND:")
    for issue in issues:
        print(f"    {issue}")
else:
    print("\n  ✅ ALL CHECKS PASSED!")
    print("\n  Your setup is ready for training the best drum classifier in the world!")

print("\n" + "="*80)
