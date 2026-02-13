#!/usr/bin/env python3
"""
Dataset Class Cleanup Script for BeatSight

Removes problematic classes with too few samples that cause training instability.
This script modifies JSON label files in-place (with backup) and optionally cleans
up the feature cache.

NOTE: This script is for cleaning up EXISTING datasets. For new builds, the
excluded classes are automatically filtered by build_training_dataset.py using
the central config in training/excluded_classes.py.

Usage:
    python cleanup_dataset_classes.py --dataset /path/to/dataset --dry-run
    python cleanup_dataset_classes.py --dataset /path/to/dataset --apply
    python cleanup_dataset_classes.py --dataset /path/to/dataset --apply --cache-dir /path/to/cache
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

# Add parent to path for imports
_THIS_FILE = Path(__file__).resolve()
_PACKAGE_ROOT = _THIS_FILE.parents[2]
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

# Import from central config (single source of truth)
try:
    from training.excluded_classes import EXCLUDED_CLASSES, get_excluded_classes
    CLASSES_TO_REMOVE: Set[str] = get_excluded_classes()
except ImportError:
    # Fallback if running standalone
    CLASSES_TO_REMOVE: Set[str] = {
        "shaker",      # 2 samples - unreliable
        "tambourine",  # 3 samples - unreliable  
        "drum_mix",    # 261 samples - it's a mix, not a single drum component
    }

# Optional: Classes to merge (uncomment if desired)
# MERGE_MAP: Dict[str, str] = {
#     "crash_1": "crash",
#     "crash_2": "crash",
# }
MERGE_MAP: Dict[str, str] = {}  # Empty = no merging


def load_json(path: Path) -> Any:
    """Load JSON file."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any, indent: int = 2) -> None:
    """Save JSON file."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def backup_file(path: Path) -> Path:
    """Create timestamped backup of a file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f".backup_{timestamp}{path.suffix}")
    shutil.copy2(path, backup_path)
    return backup_path


def analyze_labels(labels: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count samples per class."""
    return Counter(item.get("label", "unknown") for item in labels)


def filter_and_remap_labels(
    labels: List[Dict[str, Any]],
    classes_to_remove: Set[str],
    merge_map: Dict[str, str],
    new_component_index: Dict[str, int],
) -> List[Dict[str, Any]]:
    """Filter out removed classes and remap component indices."""
    filtered = []
    
    for item in labels:
        label = item.get("label", "")
        
        # Skip removed classes
        if label in classes_to_remove:
            continue
        
        # Apply merge map
        if label in merge_map:
            label = merge_map[label]
        
        # Create new item with updated label and component_idx
        new_item = dict(item)
        new_item["label"] = label
        new_item["component_idx"] = new_component_index[label]
        filtered.append(new_item)
    
    return filtered


def compute_new_component_index(
    old_components: List[str],
    classes_to_remove: Set[str],
    merge_map: Dict[str, str],
) -> tuple[List[str], Dict[str, int]]:
    """Compute new component list and index mapping."""
    # Build new component list
    seen = set()
    new_components = []
    
    for comp in old_components:
        if comp in classes_to_remove:
            continue
        
        # Apply merge map
        effective_comp = merge_map.get(comp, comp)
        
        if effective_comp not in seen:
            seen.add(effective_comp)
            new_components.append(effective_comp)
    
    # Build index mapping
    new_index = {comp: idx for idx, comp in enumerate(new_components)}
    
    return new_components, new_index


def find_cache_files_to_remove(
    labels: List[Dict[str, Any]],
    classes_to_remove: Set[str],
    cache_dir: Path,
    split: str,
) -> List[Path]:
    """Find cached .pt files for removed classes."""
    files_to_remove = []
    
    for item in labels:
        if item.get("label", "") in classes_to_remove:
            # Convert audio path to cache path
            audio_file = item.get("file", "")
            if audio_file:
                cache_file = cache_dir / split / Path(audio_file).with_suffix(".pt")
                if cache_file.exists():
                    files_to_remove.append(cache_file)
    
    return files_to_remove


def main():
    parser = argparse.ArgumentParser(
        description="Clean up dataset by removing problematic classes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Preview changes (no modifications)
    python cleanup_dataset_classes.py --dataset E:/data/prod_combined_profile_run --dry-run
    
    # Apply changes with backup
    python cleanup_dataset_classes.py --dataset E:/data/prod_combined_profile_run --apply
    
    # Also clean up feature cache
    python cleanup_dataset_classes.py --dataset E:/data/prod_combined_profile_run --apply \\
        --cache-dir C:/github/BeatSight/data/feature_cache/prod_combined_warmup
        """,
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to dataset directory (containing train/, val/, components.json)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Optional path to feature cache directory to clean up",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (creates backups first)",
    )
    parser.add_argument(
        "--remove-classes",
        nargs="+",
        help=f"Override classes to remove (default: {sorted(CLASSES_TO_REMOVE)})",
    )
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        parser.error("Must specify either --dry-run or --apply")
    
    dataset_dir = args.dataset.resolve()
    if not dataset_dir.exists():
        parser.error(f"Dataset directory not found: {dataset_dir}")
    
    classes_to_remove = set(args.remove_classes) if args.remove_classes else CLASSES_TO_REMOVE
    
    print("=" * 60)
    print("BeatSight Dataset Class Cleanup")
    print("=" * 60)
    print(f"Dataset: {dataset_dir}")
    print(f"Mode: {'DRY RUN (no changes)' if args.dry_run else 'APPLY CHANGES'}")
    print(f"Classes to remove: {sorted(classes_to_remove)}")
    if MERGE_MAP:
        print(f"Classes to merge: {MERGE_MAP}")
    print()
    
    # Load components.json
    components_path = dataset_dir / "components.json"
    if not components_path.exists():
        parser.error(f"components.json not found: {components_path}")
    
    components_data = load_json(components_path)
    old_components = components_data.get("components", [])
    old_counts = components_data.get("counts", {})
    
    print(f"Current classes: {len(old_components)}")
    print()
    
    # Show what will be removed
    print("Classes to be REMOVED:")
    total_removed = 0
    for cls in sorted(classes_to_remove):
        count = old_counts.get(cls, 0)
        total_removed += count
        print(f"  - {cls}: {count:,} samples")
    print(f"  Total samples removed: {total_removed:,}")
    print()
    
    # Compute new component mapping
    new_components, new_component_index = compute_new_component_index(
        old_components, classes_to_remove, MERGE_MAP
    )
    
    print(f"New class count: {len(new_components)} (was {len(old_components)})")
    print()
    
    # Process each split
    splits = ["train", "val"]
    all_cache_files_to_remove: List[Path] = []
    
    for split in splits:
        split_dir = dataset_dir / split
        labels_path = split_dir / f"{split}_labels.json"
        
        if not labels_path.exists():
            print(f"Warning: {labels_path} not found, skipping")
            continue
        
        print(f"Processing {split}...")
        labels = load_json(labels_path)
        
        # Analyze before
        before_counts = analyze_labels(labels)
        before_total = len(labels)
        
        # Filter and remap
        filtered_labels = filter_and_remap_labels(
            labels, classes_to_remove, MERGE_MAP, new_component_index
        )
        
        after_total = len(filtered_labels)
        removed_count = before_total - after_total
        
        print(f"  Before: {before_total:,} samples")
        print(f"  After:  {after_total:,} samples")
        print(f"  Removed: {removed_count:,} samples ({100*removed_count/before_total:.4f}%)")
        
        # Find cache files to remove
        if args.cache_dir:
            cache_files = find_cache_files_to_remove(
                labels, classes_to_remove, args.cache_dir, split
            )
            all_cache_files_to_remove.extend(cache_files)
            print(f"  Cache files to remove: {len(cache_files)}")
        
        if args.apply:
            # Backup original
            backup_path = backup_file(labels_path)
            print(f"  Backup: {backup_path}")
            
            # Save filtered labels
            save_json(labels_path, filtered_labels)
            print(f"  Saved: {labels_path}")
        
        print()
    
    # Update components.json
    if args.apply:
        # Recount from filtered labels
        new_counts = {}
        for split in splits:
            labels_path = dataset_dir / split / f"{split}_labels.json"
            if labels_path.exists():
                labels = load_json(labels_path)
                for item in labels:
                    label = item.get("label", "")
                    new_counts[label] = new_counts.get(label, 0) + 1
        
        # Build new components.json
        new_components_data = {
            "components": new_components,
            "num_classes": len(new_components),
            "component_index": new_component_index,
            "counts": new_counts,
        }
        
        # Backup and save
        backup_path = backup_file(components_path)
        print(f"Components backup: {backup_path}")
        save_json(components_path, new_components_data)
        print(f"Saved: {components_path}")
        print()
    
    # Clean up cache files
    if args.cache_dir and all_cache_files_to_remove:
        print(f"Cache files to remove: {len(all_cache_files_to_remove)}")
        if args.apply:
            removed = 0
            for cache_file in all_cache_files_to_remove:
                try:
                    cache_file.unlink()
                    removed += 1
                except Exception as e:
                    print(f"  Warning: Could not remove {cache_file}: {e}")
            print(f"  Removed {removed} cache files")
        else:
            print("  (Would remove in --apply mode)")
        print()
    
    # Summary
    print("=" * 60)
    if args.dry_run:
        print("DRY RUN COMPLETE - No files were modified")
        print("Run with --apply to make changes")
    else:
        print("CLEANUP COMPLETE")
        print()
        print("Next steps:")
        print("  1. Verify the changes: head -c 2000 train/train_labels.json")
        print("  2. Check components.json: cat components.json")
        print("  3. Re-run training with the cleaned dataset")
    print("=" * 60)


if __name__ == "__main__":
    main()
