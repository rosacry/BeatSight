#!/usr/bin/env python3
"""
Create a batched dataset from synthesized Lakh samples.

This reads the synthesized china/splash/crash/ride_bell samples from the feature cache
and creates a new dataset source compatible with multilabel_real_v3.
"""

import json
import numpy as np
from pathlib import Path
from tqdm import tqdm
import struct

# Paths
CACHE_DIR = Path("F:/feature_cache/train")
OUTPUT_DIR = Path("F:/datasets/multilabel_real_v3/lakh_synth")  # Add to existing dataset
BATCH_SIZE = 2500  # Samples per batch file

# Class indices from DEFAULT_DRUM_COMPONENTS in training/multilabel/dataset.py:
# 0: china, 1: crash, 2: cross_stick, 3: hihat_closed, 4: hihat_open,
# 5: hihat_pedal, 6: kick, 7: ride_bell, 8: ride_bow, 9: snare, 10: splash, 11: tom
CHINA_IDX = 0   # china is index 0, NOT 9!
CRASH_IDX = 1
RIDE_BELL_IDX = 7
SPLASH_IDX = 10
NUM_CLASSES = 12

# Feature shape (must match training)
FEATURE_SHAPE = (128, 128)
BYTES_PER_SAMPLE = 128 * 128 * 4  # float32


def load_sample_from_cache(cache_dir: Path, shard_id: int, offset: int) -> np.ndarray:
    """Load a single sample from the cache."""
    # Try both 4-digit and 5-digit shard formats
    shard_path_4 = cache_dir / f"shard_{shard_id:04d}.bin"
    shard_path_5 = cache_dir / f"shard_{shard_id:05d}.bin"
    
    if shard_path_5.exists():
        shard_path = shard_path_5
    elif shard_path_4.exists():
        shard_path = shard_path_4
    else:
        raise FileNotFoundError(f"No shard file found for shard_id {shard_id}")
    
    with open(shard_path, 'rb') as f:
        f.seek(offset * BYTES_PER_SAMPLE)
        data = f.read(BYTES_PER_SAMPLE)
    return np.frombuffer(data, dtype=np.float32).reshape(FEATURE_SHAPE)


def main():
    print("=" * 70)
    print("CREATE LAKH SYNTH DATASET")
    print("=" * 70)
    
    # Load cache index
    index_path = CACHE_DIR / "index.json"
    print(f"\nLoading cache index from {index_path}...")
    with open(index_path) as f:
        cache_index = json.load(f)
    print(f"  Total cache entries: {len(cache_index):,}")
    
    # Find existing shards to filter out stale index entries (handles both 4-digit and 5-digit naming)
    existing_shards = set()
    for shard_file in CACHE_DIR.glob("shard_*.bin"):
        # Extract shard number from filename like shard_0123.bin or shard_00123.bin
        shard_num = int(shard_file.stem.replace('shard_', ''))
        existing_shards.add(shard_num)
    print(f"  Existing shards: {len(existing_shards)} (range {min(existing_shards)}-{max(existing_shards)})")
    
    # Find lakh samples - ONLY use list format [shard, offset] entries
    # Dict format entries are stale from old failed runs
    lakh_samples = []
    skipped_dict_format = 0
    skipped_missing_shard = 0
    for file_id, location in cache_index.items():
        if not file_id.startswith('lakh_'):
            continue
        
        # Skip dict format entries (stale from old runs)
        if isinstance(location, dict):
            skipped_dict_format += 1
            continue
        
        shard_id, offset = location
        
        # Skip entries pointing to non-existent shards
        if shard_id not in existing_shards:
            skipped_missing_shard += 1
            continue
        
        if file_id.startswith('lakh_china'):
            lakh_samples.append((file_id, shard_id, offset, CHINA_IDX))
        elif file_id.startswith('lakh_crash'):
            lakh_samples.append((file_id, shard_id, offset, CRASH_IDX))
        elif file_id.startswith('lakh_ride_bell'):
            lakh_samples.append((file_id, shard_id, offset, RIDE_BELL_IDX))
        elif file_id.startswith('lakh_splash'):
            lakh_samples.append((file_id, shard_id, offset, SPLASH_IDX))
    
    print(f"\nFound {len(lakh_samples):,} valid Lakh samples")
    print(f"  Skipped {skipped_dict_format:,} stale dict-format entries")
    print(f"  Skipped {skipped_missing_shard:,} entries with missing shards")
    
    # Count by class
    china_count = sum(1 for s in lakh_samples if s[3] == CHINA_IDX)
    crash_count = sum(1 for s in lakh_samples if s[3] == CRASH_IDX)
    ride_bell_count = sum(1 for s in lakh_samples if s[3] == RIDE_BELL_IDX)
    splash_count = sum(1 for s in lakh_samples if s[3] == SPLASH_IDX)
    print(f"  China: {china_count:,}")
    print(f"  Crash: {crash_count:,}")
    print(f"  Ride Bell: {ride_bell_count:,}")
    print(f"  Splash: {splash_count:,}")
    
    # Shuffle for random split
    np.random.seed(42)
    np.random.shuffle(lakh_samples)
    
    # 90/10 train/val split
    split_idx = int(len(lakh_samples) * 0.9)
    train_samples = lakh_samples[:split_idx]
    val_samples = lakh_samples[split_idx:]
    
    print(f"\nSplit: {len(train_samples):,} train, {len(val_samples):,} val")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    batch_dir = OUTPUT_DIR / "lakh_batches"
    batch_dir.mkdir(exist_ok=True)
    
    # Create batches
    manifest = {
        "dataset": "lakh_synth",
        "total_samples": len(lakh_samples),
        "batch_count": 0,
        "sample_rate": 22050,
        "feature_shape": list(FEATURE_SHAPE),
        "num_classes": NUM_CLASSES,
        "batches": {},
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
    }
    
    batch_id = 0
    
    for split_name, split_samples in [("train", train_samples), ("val", val_samples)]:
        print(f"\nCreating {split_name} batches...")
        
        for batch_start in tqdm(range(0, len(split_samples), BATCH_SIZE)):
            batch_end = min(batch_start + BATCH_SIZE, len(split_samples))
            batch_samples = split_samples[batch_start:batch_end]
            
            # Load features and create labels
            features = []
            labels = []
            
            for file_id, shard_id, offset, class_idx in batch_samples:
                try:
                    feat = load_sample_from_cache(CACHE_DIR, shard_id, offset)
                    features.append(feat)
                    
                    # Multi-hot label (single class for synthesized samples)
                    label = np.zeros(NUM_CLASSES, dtype=np.float32)
                    label[class_idx] = 1.0
                    labels.append(label)
                except Exception as e:
                    print(f"Error loading {file_id}: {e}")
                    continue
            
            if not features:
                continue
            
            # Save batch
            features_arr = np.stack(features, axis=0)
            labels_arr = np.stack(labels, axis=0)
            
            features_file = f"lakh_batches/features_batch_{batch_id}.npy"
            labels_file = f"lakh_batches/labels_batch_{batch_id}.npy"
            
            np.save(OUTPUT_DIR / features_file, features_arr)
            np.save(OUTPUT_DIR / labels_file, labels_arr)
            
            manifest["batches"][str(batch_id)] = {
                "features_file": features_file,
                "labels_file": labels_file,
                "samples": len(features),
                "split": split_name,
            }
            
            batch_id += 1
    
    manifest["batch_count"] = batch_id
    
    # Save manifest
    manifest_path = OUTPUT_DIR / "lakh_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n{'=' * 70}")
    print("DATASET CREATED")
    print(f"{'=' * 70}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Manifest: {manifest_path}")
    print(f"Batches: {batch_id}")
    print(f"Train: {manifest['train_samples']:,}")
    print(f"Val: {manifest['val_samples']:,}")


if __name__ == "__main__":
    main()
