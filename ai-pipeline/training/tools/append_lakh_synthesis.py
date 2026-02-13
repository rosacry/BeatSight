#!/usr/bin/env python3
"""
Append Lakh MIDI synthesized samples to the existing prod_v5 dataset.
This modifies the numpy arrays IN-PLACE (with backup) instead of copying the entire dataset.

Usage:
    python append_lakh_synthesis.py
    python append_lakh_synthesis.py --dry-run
"""

import json
import numpy as np
from pathlib import Path
import shutil
from datetime import datetime

# Configuration
EXISTING_DATASET = Path("F:/datasets/prod_v5_fixed_20251212")
FEATURE_CACHE = Path("F:/feature_cache")

# Synthesis manifest locations
MANIFESTS = {
    "china": Path("F:/datasets/lakh_synthesized/synthesis_manifest.json"),
    "splash": Path("F:/datasets/lakh_synthesized_splash/synthesis_manifest.json"),
}

# Class mapping (same as components.json) - 12 classes (rimshot merged into snare)
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


def load_existing_dataset():
    """Load existing dataset arrays."""
    train_dir = EXISTING_DATASET / "train"
    
    files_npy = train_dir / "train_labels_files.npy"
    labels_npy = train_dir / "train_labels_labels.npy"
    
    files = np.load(files_npy, allow_pickle=True)
    labels = np.load(labels_npy, allow_pickle=True)
    
    return files, labels


def get_class_distribution(labels):
    """Get distribution of classes."""
    unique, counts = np.unique(labels, return_counts=True)
    dist = {int(u): int(c) for u, c in zip(unique, counts)}
    return dist


def verify_features_exist(file_ids: list[str]) -> tuple[list[str], list[str]]:
    """Verify that all feature files exist in cache."""
    existing = []
    missing = []
    
    for file_id in file_ids:
        feature_path = FEATURE_CACHE / f"{file_id}.pt"
        if feature_path.exists():
            existing.append(file_id)
        else:
            missing.append(file_id)
    
    return existing, missing


def load_manifests():
    """Load all synthesis manifests."""
    all_file_ids = []
    all_labels = []
    manifest_stats = {}
    
    for class_name, manifest_path in MANIFESTS.items():
        if not manifest_path.exists():
            print(f"  [SKIP] {class_name}: manifest not found at {manifest_path}")
            continue
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        file_ids = manifest.get("file_ids", [])
        label_idx = CLASS_TO_IDX[class_name]
        
        # Verify features exist
        existing, missing = verify_features_exist(file_ids)
        
        if missing:
            print(f"  [WARN] {class_name}: {len(missing)} features missing from cache")
            print(f"         Sample missing: {missing[:3]}")
        
        # Only add existing features
        all_file_ids.extend(existing)
        all_labels.extend([label_idx] * len(existing))
        
        manifest_stats[class_name] = {
            "manifest_count": len(file_ids),
            "verified_count": len(existing),
            "missing_count": len(missing),
            "label_idx": label_idx,
        }
    
    return all_file_ids, all_labels, manifest_stats


def backup_arrays():
    """Create backup of existing arrays."""
    train_dir = EXISTING_DATASET / "train"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    files_npy = train_dir / "train_labels_files.npy"
    labels_npy = train_dir / "train_labels_labels.npy"
    
    backup_files = train_dir / f"train_labels_files.npy.bak_lakh_{timestamp}"
    backup_labels = train_dir / f"train_labels_labels.npy.bak_lakh_{timestamp}"
    
    shutil.copy2(files_npy, backup_files)
    shutil.copy2(labels_npy, backup_labels)
    
    print(f"  Created backups:")
    print(f"    {backup_files}")
    print(f"    {backup_labels}")
    
    return backup_files, backup_labels


def check_duplicates(existing_files, new_files):
    """Check for duplicate file IDs."""
    existing_set = set(existing_files.tolist() if hasattr(existing_files, 'tolist') else existing_files)
    new_set = set(new_files)
    duplicates = existing_set.intersection(new_set)
    return duplicates


def main(dry_run: bool = False):
    print("=" * 70)
    print("APPEND LAKH SYNTHESIS TO DATASET")
    print("=" * 70)
    
    # Load existing dataset
    print("\n[1/5] Loading existing dataset...")
    existing_files, existing_labels = load_existing_dataset()
    print(f"  Existing samples: {len(existing_files):,}")
    
    # Get current distribution
    current_dist = get_class_distribution(existing_labels)
    print("\n  Current class distribution (12 classes, rimshot merged into snare):")
    for cls, name in [(0, "china"), (10, "splash"), (2, "cross_stick"), (9, "snare")]:
        count = current_dist.get(cls, 0)
        print(f"    {name} ({cls}): {count:,}")
    
    # Load manifests
    print("\n[2/5] Loading synthesis manifests...")
    new_file_ids, new_labels, manifest_stats = load_manifests()
    
    print(f"\n  Manifest summary:")
    for class_name, stats in manifest_stats.items():
        print(f"    {class_name}: {stats['verified_count']:,} verified (label={stats['label_idx']})")
    print(f"  Total new samples: {len(new_file_ids):,}")
    
    if len(new_file_ids) == 0:
        print("\n[ERROR] No samples to append!")
        return
    
    # Check for duplicates
    print("\n[3/5] Checking for duplicates...")
    # Convert existing files to strings for comparison
    existing_strs = [f.decode() if isinstance(f, bytes) else str(f) for f in existing_files]
    duplicates = check_duplicates(existing_strs, new_file_ids)
    
    if duplicates:
        print(f"  [WARN] Found {len(duplicates)} duplicates, will skip:")
        for dup in list(duplicates)[:5]:
            print(f"    {dup}")
        
        # Filter out duplicates
        new_file_ids_filtered = []
        new_labels_filtered = []
        for fid, label in zip(new_file_ids, new_labels):
            if fid not in duplicates:
                new_file_ids_filtered.append(fid)
                new_labels_filtered.append(label)
        
        new_file_ids = new_file_ids_filtered
        new_labels = new_labels_filtered
        print(f"  After filtering: {len(new_file_ids):,} samples")
    else:
        print(f"  No duplicates found")
    
    if dry_run:
        print("\n[DRY RUN] Would append:")
        print(f"  {len(new_file_ids):,} new samples")
        
        # Calculate new distribution
        combined_labels = np.concatenate([existing_labels, np.array(new_labels, dtype=np.int8)])
        new_dist = get_class_distribution(combined_labels)
        
        print("\n  New class distribution would be (12 classes):")
        for cls, name in [(0, "china"), (10, "splash"), (2, "cross_stick"), (9, "snare")]:
            old_count = current_dist.get(cls, 0)
            new_count = new_dist.get(cls, 0)
            diff = new_count - old_count
            print(f"    {name} ({cls}): {old_count:,} -> {new_count:,} (+{diff:,})")
        
        print(f"\n  Total would be: {len(existing_files):,} + {len(new_file_ids):,} = {len(existing_files) + len(new_file_ids):,}")
        return
    
    # Create backup
    print("\n[4/5] Creating backup...")
    backup_arrays()
    
    # Append to arrays
    print("\n[5/5] Appending to dataset...")
    
    # Convert new file IDs to bytes (matching existing format)
    new_file_ids_bytes = np.array([fid.encode() if isinstance(fid, str) else fid for fid in new_file_ids], dtype=object)
    new_labels_arr = np.array(new_labels, dtype=np.int8)
    
    # Concatenate
    combined_files = np.concatenate([existing_files, new_file_ids_bytes])
    combined_labels = np.concatenate([existing_labels, new_labels_arr])
    
    print(f"  Original: {len(existing_files):,} samples")
    print(f"  New: {len(new_file_ids):,} samples")
    print(f"  Combined: {len(combined_files):,} samples")
    
    # Save
    train_dir = EXISTING_DATASET / "train"
    np.save(train_dir / "train_labels_files.npy", combined_files, allow_pickle=True)
    np.save(train_dir / "train_labels_labels.npy", combined_labels, allow_pickle=True)
    
    print("\n  Saved updated arrays!")
    
    # Verify
    print("\n  Verifying...")
    reloaded_files = np.load(train_dir / "train_labels_files.npy", allow_pickle=True)
    reloaded_labels = np.load(train_dir / "train_labels_labels.npy", allow_pickle=True)
    
    assert len(reloaded_files) == len(combined_files), "File count mismatch!"
    assert len(reloaded_labels) == len(combined_labels), "Label count mismatch!"
    
    # Final distribution
    final_dist = get_class_distribution(reloaded_labels)
    print("\n  FINAL class distribution (12 classes):")
    for cls, name in [(0, "china"), (10, "splash"), (2, "cross_stick"), (9, "snare")]:
        old_count = current_dist.get(cls, 0)
        new_count = final_dist.get(cls, 0)
        diff = new_count - old_count
        print(f"    {name} ({cls}): {old_count:,} -> {new_count:,} (+{diff:,})")
    
    print(f"\n  Total samples: {len(reloaded_files):,}")
    print("\n" + "=" * 70)
    print("SUCCESS! Dataset updated with Lakh synthesis samples.")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Append Lakh synthesis to dataset")
    parser.add_argument("--dry-run", action="store_true", help="Preview without modifying")
    args = parser.parse_args()
    
    main(dry_run=args.dry_run)
