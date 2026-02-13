#!/usr/bin/env python3
"""
Merge cymbal variant classes into base classes.

This script:
1. Reverts any augmentation (restores pre-augment backup, deletes aug files)
2. Merges crash_1/crash_2 → crash in all label files
3. Updates components.json with new class list
4. Creates backups before any modifications

The rationale: crash_1/crash_2 labels are kit-relative, not acoustically consistent.
A better approach is to detect "crash" generically, then use pitch-based post-processing
to distinguish multiple crashes within a song.

Usage:
    python merge_cymbal_classes.py --dataset E:/data/prod_combined_profile_run --dry-run
    python merge_cymbal_classes.py --dataset E:/data/prod_combined_profile_run --apply
"""

import argparse
import json
import os
import shutil
import glob
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# Classes to merge: source -> target
MERGE_MAP = {
    "crash_1": "crash",
    "crash_2": "crash",
    # Future-proofing: if we ever have these
    # "china_1": "china",
    # "china_2": "china",
    # "splash_1": "splash",
    # "splash_2": "splash",
}

# Classes that will be removed entirely (merged into others)
CLASSES_TO_REMOVE = set(MERGE_MAP.keys())


def find_augmented_files(dataset_path: str) -> List[str]:
    """Find all augmented audio files (contain '_aug' in filename)."""
    audio_dir = Path(dataset_path) / "train" / "audio"
    aug_files = []
    
    if audio_dir.exists():
        # Search all subdirectories
        for pattern in ["**/*_aug*.wav", "**/*_aug*.flac", "**/*_aug*.mp3"]:
            aug_files.extend(glob.glob(str(audio_dir / pattern), recursive=True))
    
    return aug_files


def find_pre_augment_backup(dataset_path: str) -> str | None:
    """Find the most recent pre-augment backup file."""
    train_dir = Path(dataset_path) / "train"
    backups = list(train_dir.glob("train_labels.pre_augment_*.json"))
    
    if backups:
        # Return most recent
        return str(sorted(backups)[-1])
    return None


def load_labels(filepath: str) -> List[dict]:
    """Load labels from JSON file."""
    print(f"  Loading {filepath}...")
    with open(filepath, 'r') as f:
        return json.load(f)


def save_labels(filepath: str, labels: List[dict], backup: bool = True) -> str | None:
    """Save labels to JSON file, optionally creating backup."""
    backup_path = None
    
    if backup and os.path.exists(filepath):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = filepath.replace(".json", f".pre_merge_{timestamp}.json")
        shutil.copy2(filepath, backup_path)
        print(f"  Backed up to: {backup_path}")
    
    print(f"  Saving {filepath}...")
    with open(filepath, 'w') as f:
        json.dump(labels, f)
    
    return backup_path


def merge_labels(labels: List[dict], merge_map: Dict[str, str]) -> Tuple[List[dict], Dict[str, int]]:
    """
    Apply merge map to labels and remove augmented entries.
    
    Returns:
        Tuple of (merged_labels, merge_stats)
    """
    merged = []
    stats = defaultdict(int)
    
    for entry in labels:
        label = entry.get("label", "")
        audio_path = entry.get("audio_path", "")
        
        # Skip augmented samples
        if "_aug" in audio_path:
            stats["skipped_augmented"] += 1
            continue
        
        # Apply merge if needed
        if label in merge_map:
            new_label = merge_map[label]
            stats[f"merged_{label}_to_{new_label}"] += 1
            entry = entry.copy()
            entry["label"] = new_label
        else:
            stats[f"kept_{label}"] += 1
        
        merged.append(entry)
    
    return merged, dict(stats)


def get_class_counts(labels: List[dict]) -> Dict[str, int]:
    """Count samples per class."""
    counts = defaultdict(int)
    for entry in labels:
        counts[entry.get("label", "unknown")] += 1
    return dict(sorted(counts.items()))


def update_components(dataset_path: str, new_classes: List[str], dry_run: bool = True) -> None:
    """Update components.json with new class list."""
    components_path = Path(dataset_path) / "components.json"
    
    if not components_path.exists():
        print(f"  Warning: {components_path} not found")
        return
    
    with open(components_path, 'r') as f:
        components = json.load(f)
    
    old_classes = components.get("classes", [])
    print(f"  Old classes ({len(old_classes)}): {old_classes}")
    print(f"  New classes ({len(new_classes)}): {new_classes}")
    
    if not dry_run:
        # Backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = str(components_path).replace(".json", f".pre_merge_{timestamp}.json")
        shutil.copy2(components_path, backup_path)
        print(f"  Backed up to: {backup_path}")
        
        # Update
        components["classes"] = new_classes
        with open(components_path, 'w') as f:
            json.dump(components, f, indent=2)
        print(f"  Updated: {components_path}")


def main():
    parser = argparse.ArgumentParser(description="Merge cymbal variant classes")
    parser.add_argument("--dataset", required=True, help="Path to dataset directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--keep-augmented", action="store_true", help="Keep augmented files (don't revert)")
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        print("Error: Must specify either --dry-run or --apply")
        return 1
    
    dry_run = args.dry_run
    dataset_path = args.dataset
    
    print("=" * 70)
    print("  CYMBAL CLASS MERGE TOOL")
    print("=" * 70)
    print(f"Dataset: {dataset_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
    print(f"Merges: {MERGE_MAP}")
    print()
    
    # Step 1: Find and handle augmented files
    print("Step 1: Checking for augmented files...")
    aug_files = find_augmented_files(dataset_path)
    print(f"  Found {len(aug_files)} augmented audio files")
    
    if aug_files and not args.keep_augmented:
        if not dry_run:
            print("  Deleting augmented audio files...")
            for f in aug_files:
                os.remove(f)
            print(f"  Deleted {len(aug_files)} files")
        else:
            print(f"  Would delete {len(aug_files)} augmented files")
    print()
    
    # Step 2: Check for pre-augment backup
    print("Step 2: Checking for pre-augment backup...")
    backup = find_pre_augment_backup(dataset_path)
    if backup:
        print(f"  Found backup: {backup}")
    else:
        print("  No pre-augment backup found (will merge from current state)")
    print()
    
    # Step 3: Process train labels
    print("Step 3: Processing train labels...")
    train_labels_path = Path(dataset_path) / "train" / "train_labels.json"
    
    # Use backup if available and we're reverting augmentation
    if backup and not args.keep_augmented:
        print("  Restoring from pre-augment backup...")
        train_labels = load_labels(backup)
    else:
        train_labels = load_labels(str(train_labels_path))
    
    print(f"  Loaded {len(train_labels):,} train samples")
    
    # Show before counts for merged classes
    before_counts = get_class_counts(train_labels)
    print("  Before merge:")
    for cls in list(MERGE_MAP.keys()) + list(set(MERGE_MAP.values())):
        if cls in before_counts:
            print(f"    {cls}: {before_counts[cls]:,}")
    
    # Apply merge
    merged_train, train_stats = merge_labels(train_labels, MERGE_MAP)
    
    print(f"  After merge: {len(merged_train):,} samples")
    print(f"  Merge stats: {train_stats}")
    
    after_counts = get_class_counts(merged_train)
    print("  After merge counts:")
    for cls in set(MERGE_MAP.values()):
        if cls in after_counts:
            print(f"    {cls}: {after_counts[cls]:,}")
    
    if not dry_run:
        save_labels(str(train_labels_path), merged_train, backup=True)
    print()
    
    # Step 4: Process val labels
    print("Step 4: Processing validation labels...")
    val_labels_path = Path(dataset_path) / "val" / "val_labels.json"
    
    if val_labels_path.exists():
        val_labels = load_labels(str(val_labels_path))
        print(f"  Loaded {len(val_labels):,} val samples")
        
        merged_val, val_stats = merge_labels(val_labels, MERGE_MAP)
        print(f"  After merge: {len(merged_val):,} samples")
        print(f"  Merge stats: {val_stats}")
        
        if not dry_run:
            save_labels(str(val_labels_path), merged_val, backup=True)
    else:
        print("  No validation labels found")
        merged_val = []
    print()
    
    # Step 5: Update components.json
    print("Step 5: Updating components.json...")
    all_labels = merged_train + merged_val
    final_classes = sorted(set(entry["label"] for entry in all_labels))
    print(f"  Final class list ({len(final_classes)} classes):")
    for cls in final_classes:
        count = sum(1 for e in all_labels if e["label"] == cls)
        print(f"    {cls}: {count:,}")
    
    update_components(dataset_path, final_classes, dry_run)
    print()
    
    # Step 6: Summary
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"Classes reduced: {len(before_counts)} → {len(final_classes)}")
    print(f"Removed classes: {CLASSES_TO_REMOVE}")
    print(f"Samples after merge: {len(merged_train):,} train, {len(merged_val):,} val")
    
    # Crash specifically
    crash_total = after_counts.get("crash", 0)
    print(f"\nCrash class now has: {crash_total:,} samples (merged from crash + crash_1 + crash_2)")
    
    if dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN COMPLETE - No files were modified")
        print("Run with --apply to make changes")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("MERGE COMPLETE")
        print()
        print("Next steps:")
        print("  1. Update excluded_classes.py to include crash_1, crash_2")
        print("  2. Update ml_drum_classifier.py num_classes to", len(final_classes))
        print("  3. Update ingest scripts to map crash_1/crash_2 → crash")
        print("  4. Clear feature cache if needed")
        print("  5. Run training!")
        print("=" * 70)
    
    return 0


if __name__ == "__main__":
    exit(main())
