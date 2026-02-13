#!/usr/bin/env python3
"""
Fix scrambled label indices in train_labels.json and val_labels.json.

The bug: build_training_dataset.py assigned component_idx based on
encounter order in the manifest, NOT alphabetically. This script fixes
the indices in-place without regenerating audio clips.

Usage:
    python fix_label_indices.py --dataset-index /path/to/dataset_index
    python fix_label_indices.py --labels-json /path/to/train_labels.json

The script will:
1. Read existing labels JSON
2. Extract label from each entry (e.g., "snare", "kick", "crash")
3. Assign correct canonical index (alphabetical order)
4. Write corrected JSON back

The canonical 21-class ordering (alphabetical):
    0: aux_percussion
    1: china
    2: crash
    3: cross_stick
    4: cymbal_choke
    5: hihat_closed
    6: hihat_foot_splash
    7: hihat_open
    8: hihat_pedal
    9: hihat_splash
   10: kick
   11: ride_bell
   12: ride_bow
   13: rimshot
   14: snare
   15: snare_center
   16: snare_cross_stick
   17: snare_rimshot
   18: splash
   19: tom_high
   20: tom_low
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Canonical component list - alphabetically sorted
# This MUST match CANONICAL_COMPONENTS in build_training_dataset.py
# and DRUM_COMPONENTS in ml_drum_classifier.py
#
# NOTE: Multi-instance instruments (toms, crashes, chinas, splashes) are
# merged into single classes. Differentiation (high/mid/low) is handled
# via post-processing pitch ranking, since relative pitch is song-specific.
#
# Redundant articulations are also merged:
#   - snare_center → snare (same drum, subtle difference)
#   - snare_cross_stick → cross_stick (same technique)
#   - snare_rimshot → rimshot (rimshots are always on snare)
#   - hihat_foot_splash → hihat_pedal (both are foot-related hi-hat sounds)
#   - hihat_splash → hihat_open (sounds similar to open hihat)
#
# Excluded classes:
#   - aux_percussion (inconsistent grab-bag of misc sounds)
#   - cymbal_choke (detected via post-processing sustain analysis)
CANONICAL_COMPONENTS = [
    "china",          # All china cymbals (pitch-ranked in post-processing)
    "crash",          # All crash cymbals (pitch-ranked in post-processing)
    "cross_stick",    # Cross-stick / side-stick technique
    "hihat_closed",
    "hihat_open",     # Open hihat + hihat_splash merged
    "hihat_pedal",    # Hi-hat foot sounds (pedal, foot_splash)
    "kick",
    "ride_bell",
    "ride_bow",
    "rimshot",        # All rimshots (merged snare_rimshot)
    "snare",          # All snare hits (merged snare_center)
    "splash",         # All splash cymbals (pitch-ranked in post-processing)
    "tom",            # All toms merged (pitch-ranked in post-processing)
]

# Labels that should be merged into a canonical class
# Format: "source_label": "canonical_label"
LABEL_MERGE_MAP: Dict[str, str] = {
    # Toms - merge all variants into single "tom" class
    "tom_high": "tom",
    "tom_mid": "tom",
    "tom_low": "tom",
    # Snare articulations - merge redundant labels
    "snare_center": "snare",
    "snare_cross_stick": "cross_stick",
    "snare_rimshot": "rimshot",
    # Hi-hat variants
    "hihat_foot_splash": "hihat_pedal",  # foot splash is a pedal technique
    "hihat_splash": "hihat_open",         # stick splash sounds like open hihat
}

# Labels to exclude entirely (remove from training)
EXCLUDED_LABELS: set = {
    "aux_percussion",  # Inconsistent grab-bag of misc percussion
    "cymbal_choke",    # Detected via post-processing (sustain cutoff analysis)
}

# Build canonical mapping
LABEL_TO_IDX: Dict[str, int] = {
    label: idx for idx, label in enumerate(CANONICAL_COMPONENTS)
}

# Add merged labels to the index lookup
for source_label, canonical_label in LABEL_MERGE_MAP.items():
    if canonical_label in LABEL_TO_IDX:
        LABEL_TO_IDX[source_label] = LABEL_TO_IDX[canonical_label]


def fix_labels_file(labels_path: Path, dry_run: bool = False) -> Dict[str, int]:
    """
    Fix component_idx values in a labels JSON file.
    
    Returns dict with statistics about changes made.
    """
    print(f"\nProcessing: {labels_path}")
    
    # Check if file exists
    if not labels_path.exists():
        print(f"  ERROR: File not found!")
        return {"error": 1}
    
    # Load labels
    print(f"  Loading labels...")
    try:
        with open(labels_path, "r", encoding="utf-8") as f:
            labels = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse JSON: {e}")
        return {"error": 1}
    
    if not isinstance(labels, list):
        print(f"  ERROR: Expected list, got {type(labels)}")
        return {"error": 1}
    
    print(f"  Loaded {len(labels):,} entries")
    
    # Track statistics
    stats = {
        "total": len(labels),
        "fixed": 0,
        "unchanged": 0,
        "unknown_labels": 0,
        "merged_labels": 0,
        "excluded_labels": 0,
        "label_distribution": {},
    }
    unknown_labels = set()
    merged_counts: Dict[str, int] = {}
    excluded_counts: Dict[str, int] = {}
    filtered_labels = []  # Will hold entries after exclusion
    
    # Fix each entry
    for entry in labels:
        label = entry.get("label", "")
        old_idx = entry.get("component_idx")
        
        # Check if this label should be excluded entirely
        if label in EXCLUDED_LABELS:
            excluded_counts[label] = excluded_counts.get(label, 0) + 1
            stats["excluded_labels"] += 1
            continue  # Skip this entry entirely
        
        # Check if this label needs to be merged
        if label in LABEL_MERGE_MAP:
            canonical_label = LABEL_MERGE_MAP[label]
            merged_counts[f"{label} -> {canonical_label}"] = merged_counts.get(f"{label} -> {canonical_label}", 0) + 1
            stats["merged_labels"] += 1
            # Update the label field to canonical name
            entry["label"] = canonical_label
            label = canonical_label
        
        # Track label distribution
        stats["label_distribution"][label] = stats["label_distribution"].get(label, 0) + 1
        
        if label not in LABEL_TO_IDX:
            unknown_labels.add(label)
            stats["unknown_labels"] += 1
            continue
        
        new_idx = LABEL_TO_IDX[label]
        
        if old_idx != new_idx:
            stats["fixed"] += 1
            entry["component_idx"] = new_idx
        else:
            stats["unchanged"] += 1
        
        filtered_labels.append(entry)
    
    # Report statistics
    print(f"\n  Statistics:")
    print(f"    Total entries:     {stats['total']:,}")
    print(f"    Excluded:          {stats['excluded_labels']:,}")
    print(f"    Remaining:         {len(filtered_labels):,}")
    print(f"    Fixed:             {stats['fixed']:,}")
    print(f"    Merged:            {stats['merged_labels']:,}")
    print(f"    Already correct:   {stats['unchanged']:,}")
    if unknown_labels:
        print(f"    Unknown labels:    {stats['unknown_labels']:,}")
        print(f"      Labels: {sorted(unknown_labels)}")
    
    # Show exclusion summary
    if excluded_counts:
        print(f"\n  Excluded labels:")
        for label, count in sorted(excluded_counts.items()):
            print(f"    {label}: {count:,}")
    
    # Show merge summary
    if merged_counts:
        print(f"\n  Label merges:")
        for merge_key, count in sorted(merged_counts.items()):
            print(f"    {merge_key}: {count:,}")
    
    # Show label distribution
    print(f"\n  Label distribution:")
    sorted_labels = sorted(stats["label_distribution"].items(), key=lambda x: -x[1])
    for label, count in sorted_labels:
        idx = LABEL_TO_IDX.get(label, "?")
        print(f"    {idx:>2}: {label:<20} {count:>10,}")
    
    # Save if not dry run
    if dry_run:
        print(f"\n  DRY RUN: No changes written")
    else:
        backup_path = labels_path.with_suffix(".json.bak")
        print(f"\n  Backing up to: {backup_path}")
        if backup_path.exists():
            print(f"    (removing existing backup)")
            backup_path.unlink()
        labels_path.rename(backup_path)
        
        print(f"  Writing corrected labels...")
        with open(labels_path, "w", encoding="utf-8") as f:
            json.dump(filtered_labels, f, separators=(",", ":"))
        print(f"  Done! Wrote {len(filtered_labels):,} entries (excluded {stats['excluded_labels']:,})")
    
    stats["final_count"] = len(filtered_labels)
    return stats


def update_components_json(components_path: Path, dry_run: bool = False) -> None:
    """Update components.json with canonical ordering."""
    print(f"\nUpdating: {components_path}")
    
    components_data = {
        "num_classes": len(CANONICAL_COMPONENTS),
        "components": CANONICAL_COMPONENTS,
        "component_index": LABEL_TO_IDX,
    }
    
    if dry_run:
        print(f"  DRY RUN: Would write canonical {len(CANONICAL_COMPONENTS)}-class ordering")
    else:
        if components_path.exists():
            backup_path = components_path.with_suffix(".json.bak")
            print(f"  Backing up to: {backup_path}")
            if backup_path.exists():
                print(f"    (removing existing backup)")
                backup_path.unlink()
            components_path.rename(backup_path)
        
        with open(components_path, "w", encoding="utf-8") as f:
            json.dump(components_data, f, indent=2)
        print(f"  Done! Wrote canonical {len(CANONICAL_COMPONENTS)}-class ordering")


def main():
    parser = argparse.ArgumentParser(
        description="Fix scrambled label indices in training dataset"
    )
    parser.add_argument(
        "--dataset-index",
        type=Path,
        help="Path to dataset_index directory containing train_labels.json and val_labels.json"
    )
    parser.add_argument(
        "--labels-json",
        type=Path,
        help="Path to a specific labels JSON file to fix"
    )
    parser.add_argument(
        "--components-json",
        type=Path,
        help="Path to components.json to update with canonical ordering"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files"
    )
    
    args = parser.parse_args()
    
    if not any([args.dataset_index, args.labels_json, args.components_json]):
        parser.print_help()
        print("\nERROR: Must specify at least one of --dataset-index, --labels-json, or --components-json")
        sys.exit(1)
    
    print("=" * 60)
    print("FIX LABEL INDICES")
    print("=" * 60)
    print("\nCanonical 21-class ordering (alphabetical):")
    for idx, label in enumerate(CANONICAL_COMPONENTS):
        print(f"  {idx:2d}: {label}")
    
    all_stats = []
    
    # Process dataset-index directory
    if args.dataset_index:
        for split in ["train", "val"]:
            labels_path = args.dataset_index / f"{split}_labels.json"
            if labels_path.exists():
                stats = fix_labels_file(labels_path, dry_run=args.dry_run)
                all_stats.append(stats)
        
        components_path = args.dataset_index / "components.json"
        update_components_json(components_path, dry_run=args.dry_run)
    
    # Process specific labels file
    if args.labels_json:
        stats = fix_labels_file(args.labels_json, dry_run=args.dry_run)
        all_stats.append(stats)
    
    # Update components.json
    if args.components_json:
        update_components_json(args.components_json, dry_run=args.dry_run)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_fixed = sum(s.get("fixed", 0) for s in all_stats)
    total_entries = sum(s.get("total", 0) for s in all_stats)
    print(f"  Total entries processed: {total_entries:,}")
    print(f"  Total indices fixed:     {total_fixed:,}")
    
    if args.dry_run:
        print("\n  DRY RUN MODE - no files were modified")
        print("  Run without --dry-run to apply changes")
    else:
        print("\n  Changes have been saved!")
        print("  Original files backed up with .bak extension")
        print("\n  NEXT STEPS:")
        print("  1. Regenerate numpy cache (if using numpy loading):")
        print("     python tools/convert_labels_to_numpy.py --labels-dir <dir>")
        print("  2. Regenerate cache index mapping (if using consolidated cache):")
        print("     python tools/generate_cache_index_mapping.py --dataset <dir>")
        print("  3. Restart training from scratch")


if __name__ == "__main__":
    main()
