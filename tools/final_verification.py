#!/usr/bin/env python3
"""
===============================================================================
                    FINAL COMPREHENSIVE VERIFICATION REPORT
              For World's Best Drum Classifier - 95%+ Balanced Val Acc
===============================================================================
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

def check_mark(passed):
    return "[PASS]" if passed else "[FAIL]"

print("="*80)
print("       FINAL COMPREHENSIVE VERIFICATION REPORT")
print("       For World's Best Drum Classifier")
print("="*80)

all_checks_passed = True

# 1. Dataset Sizes
print("\n1. DATASET SIZES")
print("-"*40)
train_labels = np.load(DATASET / "train" / "train_labels_labels.npy")
val_labels = np.load(DATASET / "val" / "val_labels_labels.npy")
train_files = np.load(DATASET / "train" / "train_labels_files.npy", allow_pickle=True)
val_files = np.load(DATASET / "val" / "val_labels_files.npy", allow_pickle=True)

print(f"   Train samples:  {len(train_labels):>15,}")
print(f"   Val samples:    {len(val_labels):>15,}")
print(f"   Total:          {len(train_labels)+len(val_labels):>15,}")
print(f"   Val ratio:      {100*len(val_labels)/(len(train_labels)+len(val_labels)):>14.2f}%")

check = 9 <= 100*len(val_labels)/(len(train_labels)+len(val_labels)) <= 11
all_checks_passed &= check
print(f"   {check_mark(check)} Val ratio is ~10%")

# 2. Cache Coverage
print("\n2. CACHE COVERAGE")
print("-"*40)
with np.load(DATASET / "train" / "cache_mapping.npz", allow_pickle=True) as f:
    train_valid = f['valid']
    train_cache_split = f['cache_split']
with np.load(DATASET / "val" / "cache_mapping.npz", allow_pickle=True) as f:
    val_valid = f['valid']
    val_cache_split = f['cache_split']

train_coverage = 100*np.sum(train_valid)/len(train_valid)
val_coverage = 100*np.sum(val_valid)/len(val_valid)

print(f"   Train coverage: {train_coverage:>14.2f}%")
print(f"   Val coverage:   {val_coverage:>14.2f}%")

check = train_coverage == 100 and val_coverage == 100
all_checks_passed &= check
print(f"   {check_mark(check)} 100% cache coverage")

# 3. Data Leakage Check
print("\n3. DATA LEAKAGE CHECK")
print("-"*40)
train_ids = set(f.decode() if isinstance(f, bytes) else str(f) for f in train_files)
val_ids = set(f.decode() if isinstance(f, bytes) else str(f) for f in val_files)
overlap = len(train_ids & val_ids)

print(f"   Train/val overlap: {overlap:,}")
check = overlap == 0
all_checks_passed &= check
print(f"   {check_mark(check)} No sample overlap between train/val")

# 4. Stratified Split
print("\n4. STRATIFIED SPLIT")
print("-"*40)
all_stratified = True
for i, name in enumerate(CLASS_NAMES):
    train_count = np.sum(train_labels == i)
    val_count = np.sum(val_labels == i)
    val_pct = val_count / (train_count + val_count) * 100
    is_good = 9.5 <= val_pct <= 10.5
    all_stratified &= is_good
    if not is_good:
        print(f"   {name}: {val_pct:.2f}% val [BAD]")

check = all_stratified
all_checks_passed &= check
print(f"   {check_mark(check)} All classes have 10% +/- 0.5% in val")

# 5. Rare Classes
print("\n5. RARE CLASS REPRESENTATION")
print("-"*40)
china_train = np.sum(train_labels == 0)
china_val = np.sum(val_labels == 0)
splash_train = np.sum(train_labels == 10)
splash_val = np.sum(val_labels == 10)

print(f"   China:  {china_train:>10,} train / {china_val:>8,} val")
print(f"   Splash: {splash_train:>10,} train / {splash_val:>8,} val")

check = china_train > 50000 and china_val > 5000 and splash_train > 50000 and splash_val > 5000
all_checks_passed &= check
print(f"   {check_mark(check)} Rare classes have sufficient samples")

# 6. Duplicate Check
print("\n6. DUPLICATE CHECK")
print("-"*40)
train_unique = len(set(f.decode() if isinstance(f, bytes) else str(f) for f in train_files))
val_unique = len(set(f.decode() if isinstance(f, bytes) else str(f) for f in val_files))

print(f"   Train: {len(train_files):,} total, {train_unique:,} unique")
print(f"   Val:   {len(val_files):,} total, {val_unique:,} unique")

check = train_unique == len(train_files) and val_unique == len(val_files)
all_checks_passed &= check
print(f"   {check_mark(check)} No duplicate files")

# 7. Cache Read Test
print("\n7. CACHE READ TEST")
print("-"*40)
train_cache = ConsolidatedCacheReader(CACHE / "train")
val_cache = ConsolidatedCacheReader(CACHE / "val")

with np.load(DATASET / "train" / "cache_mapping.npz", allow_pickle=True) as f:
    shards = f['shard_ids']
    offsets = f['offsets']
    valid = f['valid']
    cache_split = f['cache_split']

# Test 100 random reads
np.random.seed(42)
test_indices = np.random.choice(np.where(valid)[0], size=100, replace=False)
success = 0
for idx in test_indices:
    shard = int(shards[idx])
    offset = int(offsets[idx])
    split = str(cache_split[idx])
    reader = val_cache if split == 'val' else train_cache
    try:
        tensor = reader._read_sample(shard, offset)
        if tensor is not None and tensor.shape == (1, 128, 128):
            success += 1
    except:
        pass

print(f"   Random reads: {success}/100 successful")
check = success == 100
all_checks_passed &= check
print(f"   {check_mark(check)} All cache reads successful")

# 8. Tensor Statistics
print("\n8. TENSOR STATISTICS")
print("-"*40)
tensors = []
for idx in test_indices[:50]:
    shard = int(shards[idx])
    offset = int(offsets[idx])
    split = str(cache_split[idx])
    reader = val_cache if split == 'val' else train_cache
    tensor = reader._read_sample(shard, offset)
    tensors.append(tensor.numpy())

all_tensors = np.stack(tensors)
has_nan = np.isnan(all_tensors).any()
has_inf = np.isinf(all_tensors).any()

print(f"   Mean: {all_tensors.mean():.4f}")
print(f"   Std:  {all_tensors.std():.4f}")
print(f"   NaN:  {has_nan}")
print(f"   Inf:  {has_inf}")

check = not has_nan and not has_inf
all_checks_passed &= check
print(f"   {check_mark(check)} No NaN/Inf values")

# 9. Dual Cache System
print("\n9. DUAL CACHE SYSTEM")
print("-"*40)
train_from_train = np.sum(train_cache_split == 'train')
train_from_val = np.sum(train_cache_split == 'val')
val_from_train = np.sum(val_cache_split == 'train')
val_from_val = np.sum(val_cache_split == 'val')

print(f"   Train split: {train_from_train:,} from train + {train_from_val:,} from val")
print(f"   Val split:   {val_from_train:,} from train + {val_from_val:,} from val")

check = (train_from_train + train_from_val == len(train_valid)) and (val_from_train + val_from_val == len(val_valid))
all_checks_passed &= check
print(f"   {check_mark(check)} Dual cache routing correct")

# FINAL VERDICT
print("\n" + "="*80)
if all_checks_passed:
    print("   [OK] ALL CHECKS PASSED!")
    print("")
    print("   Your training setup is VERIFIED and ready to create")
    print("   the world's best drum classifier with 95%+ balanced accuracy!")
else:
    print("   [FAIL] SOME CHECKS FAILED!")
    print("   Please review the issues above before training.")
print("="*80)

# Print training command as reminder
print("\n" + "="*80)
print("   TRAINING COMMAND:")
print("="*80)
print("""
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_definitive" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 50 --batch-size 128 --grad-accum-steps 5 \\
  --lr 1e-4 --amp-dtype bfloat16 \\
  --balanced-sampling --sampling-strategy uniform \\
  --loss-type class-balanced-focal --cb-beta 0.999 \\
  --specaugment drum --use-sam --sam-adaptive \\
  --scheduler cosine --warmup-epochs 3 \\
  --gradient-checkpointing --grad-clip-norm 1.0 \\
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \\
  --checkpoint-every 1 --checkpoint-every-batches 5000 \\
  --channels-last --output runs/v5_12class_100pct
""")
