#!/usr/bin/env python3
"""
Merge rimshot class into snare class.

This script:
1. Updates the dataset numpy arrays (label 9 → 10)
2. Updates components.json (removes rimshot, updates indices)
3. Re-indexes all classes to be contiguous (0-11 instead of 0-12 with gap)

OLD CLASS MAPPING (13 classes):
    0: china, 1: crash, 2: cross_stick, 3: hihat_closed, 4: hihat_open,
    5: hihat_pedal, 6: kick, 7: ride_bell, 8: ride_bow, 9: rimshot,
    10: snare, 11: splash, 12: tom

NEW CLASS MAPPING (12 classes):
    0: china, 1: crash, 2: cross_stick, 3: hihat_closed, 4: hihat_open,
    5: hihat_pedal, 6: kick, 7: ride_bell, 8: ride_bow, 9: snare,
    10: splash, 11: tom

Changes:
    - rimshot (9) → snare (10), then snare becomes 9
    - splash (11) → 10
    - tom (12) → 11

Usage:
    python merge_rimshot_to_snare.py --dataset F:/datasets/prod_v5_fixed_20251212 --dry-run
    python merge_rimshot_to_snare.py --dataset F:/datasets/prod_v5_fixed_20251212
"""

import json
import numpy as np
from pathlib import Path
import shutil
from datetime import datetime
import argparse


# Old mapping
OLD_CLASS_TO_IDX = {
    "china": 0,
    "crash": 1,
    "cross_stick": 2,
    "hihat_closed": 3,
    "hihat_open": 4,
    "hihat_pedal": 5,
    "kick": 6,
    "ride_bell": 7,
    "ride_bow": 8,
    "rimshot": 9,
    "snare": 10,
    "splash": 11,
    "tom": 12,
}

# New mapping (rimshot removed, indices shifted)
NEW_CLASS_TO_IDX = {
    "china": 0,
    "crash": 1,
    "cross_stick": 2,
    "hihat_closed": 3,
    "hihat_open": 4,
    "hihat_pedal": 5,
    "kick": 6,
    "ride_bell": 7,
    "ride_bow": 8,
    "snare": 9,      # Was 10, now 9 (rimshot merged in)
    "splash": 10,    # Was 11, now 10
    "tom": 11,       # Was 12, now 11
}

# Alias mappings for components.json
NEW_ALIAS_MAPPINGS = {
    "tom_high": 11,
    "tom_mid": 11,
    "tom_low": 11,
    "snare_center": 9,
    "snare_cross_stick": 2,
    "snare_rimshot": 9,       # Now maps to snare
    "rimshot": 9,             # Now maps to snare
    "hihat_foot_splash": 5,
    "hihat_splash": 4,
}


def create_label_remap():
    """Create mapping from old labels to new labels."""
    remap = {}
    
    # Classes that stay the same (0-8)
    for old_idx in range(9):
        remap[old_idx] = old_idx
    
    # rimshot (9) → snare (9 in new mapping)
    remap[9] = 9
    
    # snare (10) → snare (9 in new mapping)
    remap[10] = 9
    
    # splash (11) → splash (10 in new mapping)
    remap[11] = 10
    
    # tom (12) → tom (11 in new mapping)
    remap[12] = 11
    
    return remap


def backup_files(dataset_path: Path) -> dict:
    """Create backups of files to be modified."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backups = {}
    
    # Backup train labels
    train_dir = dataset_path / "train"
    for npy_file in ["train_labels_files.npy", "train_labels_labels.npy"]:
        src = train_dir / npy_file
        if src.exists():
            dst = train_dir / f"{npy_file}.bak_rimshot_merge_{timestamp}"
            shutil.copy2(src, dst)
            backups[str(src)] = str(dst)
    
    # Backup val labels
    val_dir = dataset_path / "val"
    for npy_file in ["val_labels_files.npy", "val_labels_labels.npy"]:
        src = val_dir / npy_file
        if src.exists():
            dst = val_dir / f"{npy_file}.bak_rimshot_merge_{timestamp}"
            shutil.copy2(src, dst)
            backups[str(src)] = str(dst)
    
    # Backup components.json
    components_file = dataset_path / "components.json"
    if components_file.exists():
        dst = dataset_path / f"components.json.bak_rimshot_merge_{timestamp}"
        shutil.copy2(components_file, dst)
        backups[str(components_file)] = str(dst)
    
    return backups


def update_labels_array(labels: np.ndarray, remap: dict) -> tuple[np.ndarray, dict]:
    """Update labels array using remap, return new array and stats."""
    old_counts = {}
    new_counts = {}
    
    # Count old distribution
    unique, counts = np.unique(labels, return_counts=True)
    for u, c in zip(unique, counts):
        old_counts[int(u)] = int(c)
    
    # Apply remapping
    new_labels = np.zeros_like(labels)
    for old_idx, new_idx in remap.items():
        mask = labels == old_idx
        new_labels[mask] = new_idx
    
    # Count new distribution
    unique, counts = np.unique(new_labels, return_counts=True)
    for u, c in zip(unique, counts):
        new_counts[int(u)] = int(c)
    
    return new_labels.astype(np.int8), {"old": old_counts, "new": new_counts}


def update_components_json(dataset_path: Path, dry_run: bool = False):
    """Update components.json with new class structure."""
    components_file = dataset_path / "components.json"
    
    new_components = {
        "num_classes": 12,
        "components": [
            "china",
            "crash",
            "cross_stick",
            "hihat_closed",
            "hihat_open",
            "hihat_pedal",
            "kick",
            "ride_bell",
            "ride_bow",
            "snare",
            "splash",
            "tom"
        ],
        "component_index": {
            **NEW_CLASS_TO_IDX,
            **NEW_ALIAS_MAPPINGS
        }
    }
    
    if not dry_run:
        with open(components_file, 'w') as f:
            json.dump(new_components, f, indent=2)
    
    return new_components


def main():
    parser = argparse.ArgumentParser(description="Merge rimshot class into snare")
    parser.add_argument("--dataset", type=str, default="F:/datasets/prod_v5_fixed_20251212",
                        help="Path to dataset directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without modifying files")
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset)
    dry_run = args.dry_run
    
    print("=" * 70)
    print("MERGE RIMSHOT → SNARE")
    print("=" * 70)
    print(f"Dataset: {dataset_path}")
    print(f"Dry run: {dry_run}")
    
    # Create remap
    remap = create_label_remap()
    print("\n[1/5] Label remapping:")
    OLD_NAMES = ["china", "crash", "cross_stick", "hihat_closed", "hihat_open",
                 "hihat_pedal", "kick", "ride_bell", "ride_bow", "rimshot",
                 "snare", "splash", "tom"]
    NEW_NAMES = ["china", "crash", "cross_stick", "hihat_closed", "hihat_open",
                 "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare",
                 "splash", "tom"]
    
    for old_idx, new_idx in remap.items():
        old_name = OLD_NAMES[old_idx]
        new_name = NEW_NAMES[new_idx]
        if old_idx != new_idx or old_name != new_name:
            print(f"  {old_idx} ({old_name}) → {new_idx} ({new_name})")
    
    # Backup files
    if not dry_run:
        print("\n[2/5] Creating backups...")
        backups = backup_files(dataset_path)
        for src, dst in backups.items():
            print(f"  {Path(src).name} → {Path(dst).name}")
    else:
        print("\n[2/5] [DRY RUN] Would create backups")
    
    # Update train labels
    print("\n[3/5] Processing train labels...")
    train_labels_path = dataset_path / "train" / "train_labels_labels.npy"
    if train_labels_path.exists():
        train_labels = np.load(train_labels_path, allow_pickle=True)
        new_train_labels, train_stats = update_labels_array(train_labels, remap)
        
        print(f"  Total samples: {len(train_labels):,}")
        
        # Show rimshot merge stats
        rimshot_count = train_stats["old"].get(9, 0)
        snare_old = train_stats["old"].get(10, 0)
        snare_new = train_stats["new"].get(9, 0)
        print(f"  rimshot (old 9): {rimshot_count:,} samples → merged into snare")
        print(f"  snare (old 10): {snare_old:,} → snare (new 9): {snare_new:,}")
        print(f"  Verification: {rimshot_count} + {snare_old} = {rimshot_count + snare_old} == {snare_new} ✓" 
              if rimshot_count + snare_old == snare_new else "  ❌ Mismatch!")
        
        if not dry_run:
            np.save(train_labels_path, new_train_labels, allow_pickle=True)
            print("  Saved updated train labels")
    
    # Update val labels
    print("\n[4/5] Processing val labels...")
    val_labels_path = dataset_path / "val" / "val_labels_labels.npy"
    if val_labels_path.exists():
        val_labels = np.load(val_labels_path, allow_pickle=True)
        new_val_labels, val_stats = update_labels_array(val_labels, remap)
        
        print(f"  Total samples: {len(val_labels):,}")
        
        # Show rimshot merge stats
        rimshot_count = val_stats["old"].get(9, 0)
        snare_old = val_stats["old"].get(10, 0)
        snare_new = val_stats["new"].get(9, 0)
        print(f"  rimshot (old 9): {rimshot_count:,} samples → merged into snare")
        print(f"  snare (old 10): {snare_old:,} → snare (new 9): {snare_new:,}")
        
        if not dry_run:
            np.save(val_labels_path, new_val_labels, allow_pickle=True)
            print("  Saved updated val labels")
    
    # Update components.json
    print("\n[5/5] Updating components.json...")
    new_components = update_components_json(dataset_path, dry_run)
    print(f"  num_classes: 13 → {new_components['num_classes']}")
    print(f"  Removed: rimshot")
    print(f"  components: {new_components['components']}")
    
    if dry_run:
        print("\n" + "=" * 70)
        print("[DRY RUN] No files modified. Run without --dry-run to apply changes.")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("SUCCESS! Rimshot merged into snare.")
        print("=" * 70)
        print("\nNew class structure (12 classes):")
        for idx, name in enumerate(new_components["components"]):
            print(f"  {idx}: {name}")
        
        print("\n⚠️  IMPORTANT: You need to update these files manually:")
        print("  1. ai-pipeline/transcription/ml_drum_classifier.py - DRUM_COMPONENTS list")
        print("  2. ai-pipeline/transcription/ml_drum_classifier_v2.py - DRUM_COMPONENTS list")
        print("  3. Desktop app C# files - DrumComponentCategory enum")
        print("  4. Frontend TypeScript files - DrumComponent type")
        print("\n⚠️  TRAINING: You need to restart training from scratch (new class count)")


if __name__ == "__main__":
    main()
