#!/usr/bin/env python3
"""
Append STAR Drums extracted samples to the existing prod_v5 dataset.
This modifies the numpy arrays IN-PLACE (with backup) instead of copying the entire dataset.
"""

import json
import numpy as np
from pathlib import Path
import hashlib
import shutil
from datetime import datetime

# Configuration
EXISTING_DATASET = Path("F:/datasets/prod_v5_fixed_20251212")
STAR_DRUMS_EXTRACTED = Path("F:/datasets/star_drums_extracted")
FEATURE_CACHE = Path("F:/feature_cache")

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


def get_cache_key(audio_path: str) -> str:
    """Generate cache key for audio file (same as training code)."""
    return hashlib.md5(audio_path.encode()).hexdigest()


def check_existing_features():
    """Check how many STAR Drums features exist in cache by scanning directly."""
    counts = {"china": 0, "splash": 0, "cross_stick": 0, "ride_bell": 0}
    
    # Scan feature cache directly for star_* files
    for pt_file in FEATURE_CACHE.glob("star_*.pt"):
        name = pt_file.stem  # e.g., star_china_002b3891bb4b
        parts = name.split("_")
        if len(parts) >= 2:
            class_name = parts[1]  # china, splash, etc.
            if class_name in counts:
                counts[class_name] += 1
    
    total = sum(counts.values())
    return total, counts


def scan_star_drums():
    """Scan feature cache directly for STAR Drums features."""
    files = []
    labels = []
    
    for class_name in ["china", "splash", "cross_stick", "ride_bell"]:
        class_idx = CLASS_TO_IDX[class_name]
        
        # Scan feature cache for this class
        pattern = f"star_{class_name}_*.pt"
        found = 0
        
        for pt_file in FEATURE_CACHE.glob(pattern):
            # Use the feature file stem as the ID (without .pt)
            feature_id = pt_file.stem
            files.append(feature_id)
            labels.append(class_idx)
            found += 1
        
        print(f"  [SCAN] {class_name}: {found} features -> class index {class_idx}")
    
    return files, labels


def main():
    print("=" * 60)
    print("STAR Drums -> Existing Dataset Appender")
    print("=" * 60)
    
    # Verify paths exist
    if not EXISTING_DATASET.exists():
        print(f"[ERROR] Dataset not found: {EXISTING_DATASET}")
        return
    
    if not STAR_DRUMS_EXTRACTED.exists():
        print(f"[ERROR] STAR Drums not found: {STAR_DRUMS_EXTRACTED}")
        return
    
    # Check feature cache status
    print("\n[1/5] Checking feature cache...")
    found, counts = check_existing_features()
    print(f"  Features found: {found:,}")
    for cls, cnt in counts.items():
        print(f"    {cls}: {cnt:,}")
    
    if found == 0:
        print("[ERROR] No features found in cache! Run merge_star_drums.py first to compute features.")
        return
    
    # Load existing dataset
    print("\n[2/5] Loading existing dataset...")
    train_dir = EXISTING_DATASET / "train"
    
    existing_files = np.load(train_dir / "train_labels_files.npy", allow_pickle=True)
    existing_labels = np.load(train_dir / "train_labels_labels.npy", allow_pickle=True)
    
    print(f"  Existing samples: {len(existing_files):,}")
    print(f"  Existing labels shape: {existing_labels.shape}")
    
    # Get class distribution before
    unique, counts = np.unique(existing_labels, return_counts=True)
    print("\n  Current rare class counts:")
    for name, idx in [("china", 0), ("splash", 11), ("cross_stick", 2), ("ride_bell", 7)]:
        count = counts[unique == idx][0] if idx in unique else 0
        print(f"    {name}: {count:,}")
    
    # Scan STAR Drums
    print("\n[3/5] Scanning STAR Drums extracted samples...")
    new_files, new_labels = scan_star_drums()
    
    print(f"\n  New samples to add: {len(new_files):,}")
    
    if len(new_files) == 0:
        print("[ERROR] No new samples found!")
        return
    
    # Check for duplicates (by cache key)
    print("\n[4/5] Checking for duplicates...")
    existing_set = set(existing_files.tolist())
    
    unique_files = []
    unique_labels = []
    duplicates = 0
    
    for f, l in zip(new_files, new_labels):
        if f not in existing_set:
            unique_files.append(f)
            unique_labels.append(l)
        else:
            duplicates += 1
    
    print(f"  Duplicates skipped: {duplicates}")
    print(f"  Unique new samples: {len(unique_files):,}")
    
    if len(unique_files) == 0:
        print("[INFO] All STAR Drums samples already in dataset!")
        return
    
    # Backup existing files
    print("\n[5/5] Appending to dataset...")
    backup_dir = train_dir / "backup_before_star_drums"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Backup
    for fname in ["train_labels_files.npy", "train_labels_labels.npy"]:
        src = train_dir / fname
        dst = backup_dir / f"{fname}.{timestamp}.bak"
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"  Backed up: {fname}")
    
    # Append
    new_files_arr = np.array(unique_files, dtype=existing_files.dtype)
    new_labels_arr = np.array(unique_labels, dtype=existing_labels.dtype)
    
    combined_files = np.concatenate([existing_files, new_files_arr])
    combined_labels = np.concatenate([existing_labels, new_labels_arr])
    
    # Save
    np.save(train_dir / "train_labels_files.npy", combined_files)
    np.save(train_dir / "train_labels_labels.npy", combined_labels)
    
    # Also update ids.npy and labels.npy if they exist (some loaders use these)
    if (train_dir / "ids.npy").exists():
        np.save(train_dir / "ids.npy", combined_files)
    if (train_dir / "labels.npy").exists():
        np.save(train_dir / "labels.npy", combined_labels)
    
    print(f"\n  Final sample count: {len(combined_files):,}")
    
    # Show new distribution
    unique, counts = np.unique(combined_labels, return_counts=True)
    print("\n  Updated rare class counts:")
    for name, idx in [("china", 0), ("splash", 11), ("cross_stick", 2), ("ride_bell", 7)]:
        count = counts[unique == idx][0] if idx in unique else 0
        print(f"    {name}: {count:,}")
    
    # Update metadata
    metadata_path = EXISTING_DATASET / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
    else:
        metadata = {}
    
    metadata["star_drums_appended"] = {
        "timestamp": timestamp,
        "samples_added": len(unique_files),
        "total_samples": len(combined_files),
        "source": str(STAR_DRUMS_EXTRACTED)
    }
    
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "=" * 60)
    print("[DONE] STAR Drums appended to existing dataset!")
    print(f"  Dataset: {EXISTING_DATASET}")
    print(f"  Total samples: {len(combined_files):,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
