#!/usr/bin/env python3
"""
Fix lakh synthesis label IDs by removing entries with hex hash IDs
and keeping only the correct numeric IDs.

The problem:
- Old append_lakh_synthesis.py added entries like: lakh_splash_8f1331c15bec (hex hash)
- But cache has entries like: lakh_splash_00001 (numeric)
- This causes cache lookup failures

This script removes the bad hex hash entries.
"""

import argparse
import re
import numpy as np
from pathlib import Path
from collections import Counter


def is_hex_hash_id(file_id: str) -> bool:
    """Check if file_id has a hex hash suffix (wrong format)."""
    if not (file_id.startswith('lakh_china_') or file_id.startswith('lakh_splash_')):
        return False
    
    # Extract suffix after lakh_china_ or lakh_splash_
    if file_id.startswith('lakh_china_'):
        suffix = file_id[len('lakh_china_'):]
    else:
        suffix = file_id[len('lakh_splash_'):]
    
    # Numeric IDs are like "00001", "49999" (5 digits, all numeric)
    # Hex hash IDs are like "8f1331c15bec" (12 chars, hex)
    
    # If it's all digits and 5 chars or less, it's correct
    if suffix.isdigit() and len(suffix) <= 6:
        return False
    
    # If it contains non-digit hex chars (a-f), it's a hex hash
    if re.match(r'^[0-9a-f]+$', suffix, re.IGNORECASE) and len(suffix) > 6:
        return True
    
    # Default: assume it's wrong if it's not a simple number
    return not suffix.isdigit()


def fix_labels(labels_dir: Path, dry_run: bool = True):
    """Remove lakh entries with hex hash IDs from labels."""
    
    # Try both naming conventions
    files_npy = labels_dir / "train_labels_files.npy"
    labels_npy = labels_dir / "train_labels_labels.npy"
    
    if not files_npy.exists():
        files_npy = labels_dir / "files.npy"
        labels_npy = labels_dir / "labels.npy"
    
    if not files_npy.exists() or not labels_npy.exists():
        raise FileNotFoundError(f"Labels not found in {labels_dir}")
    
    # Load labels
    print(f"Loading labels from {labels_dir}...")
    files = np.load(files_npy, allow_pickle=True)
    labels = np.load(labels_npy)
    
    print(f"  Total samples: {len(files):,}")
    
    # Find bad entries
    bad_indices = []
    bad_by_type = Counter()
    
    for i, file_id in enumerate(files):
        if isinstance(file_id, bytes):
            file_id = file_id.decode('utf-8')
        
        if is_hex_hash_id(file_id):
            bad_indices.append(i)
            prefix = file_id.split('_')[1]  # china or splash
            bad_by_type[prefix] += 1
    
    print(f"\n  Bad entries (hex hash IDs): {len(bad_indices):,}")
    for typ, count in sorted(bad_by_type.items()):
        print(f"    lakh_{typ}_*: {count:,}")
    
    if not bad_indices:
        print("\n  No bad entries found! Labels are clean.")
        return
    
    # Show some examples
    print(f"\n  Examples of bad entries:")
    for i in bad_indices[:5]:
        file_id = files[i]
        if isinstance(file_id, bytes):
            file_id = file_id.decode('utf-8')
        print(f"    [{i}] {file_id}")
    
    if dry_run:
        print(f"\n  [DRY RUN] Would remove {len(bad_indices):,} entries")
        print(f"  Run with --apply to actually fix the labels")
        return
    
    # Create mask for good entries
    print(f"\n  Removing {len(bad_indices):,} bad entries...")
    good_mask = np.ones(len(files), dtype=bool)
    good_mask[bad_indices] = False
    
    # Filter arrays
    new_files = files[good_mask]
    new_labels = labels[good_mask]
    
    print(f"  New total: {len(new_files):,} samples")
    
    # Backup old files
    backup_dir = labels_dir / "backup_before_fix"
    backup_dir.mkdir(exist_ok=True)
    
    import shutil
    shutil.copy(files_npy, backup_dir / "files.npy")
    shutil.copy(labels_npy, backup_dir / "labels.npy")
    print(f"  Backed up old labels to {backup_dir}")
    
    # Save new files
    np.save(files_npy, new_files)
    np.save(labels_npy, new_labels)
    print(f"  Saved fixed labels")
    
    # Verify class distribution
    print(f"\n  Class distribution after fix:")
    unique, counts = np.unique(new_labels, return_counts=True)
    for cls_idx, count in zip(unique, counts):
        print(f"    Class {cls_idx}: {count:,}")


def main():
    parser = argparse.ArgumentParser(description="Fix lakh synthesis label IDs")
    parser.add_argument("labels_dir", type=Path, help="Path to labels directory (e.g., F:/datasets/prod_v5_fixed_20251212/train)")
    parser.add_argument("--apply", action="store_true", help="Actually apply the fix (default is dry run)")
    
    args = parser.parse_args()
    
    fix_labels(args.labels_dir, dry_run=not args.apply)


if __name__ == "__main__":
    main()
