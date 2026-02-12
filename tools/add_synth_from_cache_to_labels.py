#!/usr/bin/env python3
"""
Add synthesized samples from cache index to dataset labels.

This script:
1. Scans the cache index for lakh_china_* and lakh_splash_* entries
2. Adds them to the dataset labels (with backup)

Usage:
    python tools/add_synth_from_cache_to_labels.py
    python tools/add_synth_from_cache_to_labels.py --dry-run
"""

import json
import numpy as np
import shutil
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

# Configuration
DATASET_DIR = Path("F:/datasets/prod_v5_fixed_20251212")
CACHE_INDEX = Path("F:/feature_cache/train/index.json")

# 12-class mapping (rimshot merged into snare)
CLASS_TO_IDX = {
    "china": 0,
    "crash": 1,
    "cross_stick": 2,
    "hihat_closed": 3,
    "hihat_open": 4,
    "hihat_pedal": 5,
    "kick": 6,
    "ride_bell": 7,
    "ride_bow": 8,
    "snare": 9,
    "splash": 10,
    "tom": 11,
}


def main(dry_run: bool = False):
    print("=" * 70)
    print("ADD SYNTHESIZED SAMPLES FROM CACHE TO LABELS")
    print("=" * 70)
    
    # Load cache index
    print(f"\n[1/4] Loading cache index from {CACHE_INDEX}...")
    start = time.time()
    with open(CACHE_INDEX) as f:
        cache_index = json.load(f)
    print(f"       Loaded {len(cache_index):,} entries in {time.time() - start:.1f}s")
    
    # Find synthesized entries
    print(f"\n[2/4] Finding synthesized entries...")
    synth_china = [k for k in cache_index.keys() if k.startswith('lakh_china_')]
    synth_splash = [k for k in cache_index.keys() if k.startswith('lakh_splash_')]
    
    print(f"       lakh_china_*: {len(synth_china):,}")
    print(f"       lakh_splash_*: {len(synth_splash):,}")
    print(f"       Total synthesized: {len(synth_china) + len(synth_splash):,}")
    
    if not synth_china and not synth_splash:
        print("\n       No synthesized entries found in cache!")
        return
    
    # Load existing labels
    print(f"\n[3/4] Loading existing labels...")
    train_dir = DATASET_DIR / "train"
    
    files_npy = train_dir / "train_labels_files.npy"
    labels_npy = train_dir / "train_labels_labels.npy"
    
    existing_files = np.load(files_npy, allow_pickle=True)
    existing_labels = np.load(labels_npy, allow_pickle=True)
    
    print(f"       Existing: {len(existing_files):,} samples")
    
    # Check current distribution
    label_counts = Counter(existing_labels)
    print(f"\n       Current distribution:")
    print(f"         china (0): {label_counts.get(0, 0):,}")
    print(f"         splash (10): {label_counts.get(10, 0):,}")
    
    # Check for duplicates
    existing_set = set()
    for f in existing_files:
        if isinstance(f, bytes):
            existing_set.add(f.decode('utf-8'))
        else:
            existing_set.add(str(f))
    
    # Filter out already-existing entries
    new_china = [k for k in synth_china if k not in existing_set]
    new_splash = [k for k in synth_splash if k not in existing_set]
    
    print(f"\n       Already in labels: {len(synth_china) - len(new_china) + len(synth_splash) - len(new_splash):,}")
    print(f"       New to add:")
    print(f"         china: {len(new_china):,}")
    print(f"         splash: {len(new_splash):,}")
    
    total_new = len(new_china) + len(new_splash)
    
    if total_new == 0:
        print("\n       All synthesized samples already in labels!")
        return
    
    if dry_run:
        print(f"\n[DRY RUN] Would add {total_new:,} samples")
        return
    
    # Create backup
    print(f"\n[4/4] Updating labels...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    backup_files = train_dir / f"train_labels_files.npy.bak_synth_{timestamp}"
    backup_labels = train_dir / f"train_labels_labels.npy.bak_synth_{timestamp}"
    
    shutil.copy2(files_npy, backup_files)
    shutil.copy2(labels_npy, backup_labels)
    print(f"       Created backups")
    
    # Build new arrays
    new_file_ids = new_china + new_splash
    new_label_values = [CLASS_TO_IDX["china"]] * len(new_china) + [CLASS_TO_IDX["splash"]] * len(new_splash)
    
    # Combine with existing
    combined_files = np.concatenate([
        existing_files,
        np.array(new_file_ids, dtype=object)
    ])
    combined_labels = np.concatenate([
        existing_labels,
        np.array(new_label_values, dtype=existing_labels.dtype)
    ])
    
    print(f"       Combined: {len(combined_files):,} samples")
    
    # Save
    np.save(files_npy, combined_files)
    np.save(labels_npy, combined_labels)
    print(f"       Saved updated arrays")
    
    # Verify
    final_labels = np.load(labels_npy)
    final_counts = Counter(final_labels)
    
    print(f"\n       FINAL distribution:")
    print(f"         china (0): {label_counts.get(0, 0):,} -> {final_counts.get(0, 0):,} (+{final_counts.get(0, 0) - label_counts.get(0, 0):,})")
    print(f"         splash (10): {label_counts.get(10, 0):,} -> {final_counts.get(10, 0):,} (+{final_counts.get(10, 0) - label_counts.get(10, 0):,})")
    
    # Calculate new imbalance
    max_class = max(final_counts.values())
    min_class = min(final_counts.values())
    imbalance = max_class / min_class
    
    print(f"\n       Total samples: {len(combined_files):,}")
    print(f"       Imbalance ratio: {imbalance:.1f}x (largest/smallest)")
    
    print("\n" + "=" * 70)
    print("SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    main(dry_run)
