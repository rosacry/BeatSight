#!/usr/bin/env python3
"""
Comprehensive drive audit to find old/unused data for cleanup.
Run this script and share the output.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import json


def format_size(size_bytes):
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def get_dir_size_fast(path, max_depth=2):
    """Get directory size with depth limit for speed."""
    total = 0
    current_depth = 0
    
    def scan(p, depth):
        nonlocal total
        if depth > max_depth:
            return
        try:
            for entry in os.scandir(p):
                if entry.is_file(follow_symlinks=False):
                    try:
                        total += entry.stat().st_size
                    except:
                        pass
                elif entry.is_dir(follow_symlinks=False):
                    scan(entry.path, depth + 1)
        except (PermissionError, OSError):
            pass
    
    scan(path, 0)
    return total


def get_dir_size_full(path):
    """Get full directory size (slower but accurate)."""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except:
                    pass
    except:
        pass
    return total


def check_for_old_class_structures(path):
    """Look for references to old 13-class or 21-class structures."""
    old_patterns = []
    
    # Check folder names
    for item in path.rglob('*'):
        name = item.name.lower()
        if any(p in name for p in ['13class', '13_class', '21class', '21_class', 'class13', 'class21']):
            old_patterns.append(str(item))
        # Also check for old config files
        if item.is_file() and item.suffix in ['.json', '.yaml', '.yml']:
            try:
                content = item.read_text(errors='ignore')
                if '"num_classes": 13' in content or '"num_classes": 21' in content:
                    old_patterns.append(f"{item} (contains old class count)")
                if "'num_classes': 13" in content or "'num_classes': 21" in content:
                    old_patterns.append(f"{item} (contains old class count)")
            except:
                pass
    
    return old_patterns


def main():
    print("=" * 80)
    print("COMPREHENSIVE DRIVE AUDIT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # Drive usage summary
    print("DRIVE USAGE SUMMARY")
    print("-" * 80)
    for drive in ['C:/', 'D:/', 'F:/']:
        try:
            total, used, free = shutil.disk_usage(drive)
            pct = (used / total) * 100
            print(f"  {drive:10} {format_size(used):>12} used / {format_size(total):>12} total "
                  f"({pct:.1f}%) - {format_size(free):>12} free")
        except Exception as e:
            print(f"  {drive:10} Error: {e}")
    print()
    
    # =========================================================================
    # D: DRIVE ANALYSIS (main focus)
    # =========================================================================
    print("=" * 80)
    print("D: DRIVE DETAILED ANALYSIS")
    print("=" * 80)
    
    d_drive = Path("D:/")
    
    # Top-level folders with sizes
    print("\nTop-level folders on D:/:")
    print("-" * 80)
    
    top_level = []
    for item in sorted(d_drive.iterdir()):
        if item.is_dir() and not item.name.startswith('$'):
            print(f"  Scanning {item.name}...", end=" ", flush=True)
            size = get_dir_size_full(item)
            top_level.append((item.name, size, item))
            print(f"{format_size(size)}")
    
    print()
    print("Summary (sorted by size):")
    print("-" * 80)
    for name, size, path in sorted(top_level, key=lambda x: x[1], reverse=True):
        print(f"  {name:40} {format_size(size):>15}")
    
    total_scanned = sum(x[1] for x in top_level)
    print(f"  {'TOTAL SCANNED':40} {format_size(total_scanned):>15}")
    
    # D:/cold_storage breakdown
    print("\n" + "=" * 80)
    print("D:/cold_storage/ BREAKDOWN")
    print("=" * 80)
    
    cold_storage = Path("D:/cold_storage")
    if cold_storage.exists():
        for subdir in sorted(cold_storage.iterdir()):
            if subdir.is_dir():
                print(f"\n{subdir.name}/:")
                print("-" * 60)
                
                items = []
                for item in sorted(subdir.iterdir()):
                    if item.is_dir():
                        size = get_dir_size_full(item)
                        items.append((item.name, size))
                        
                        # Check for old class structures
                        if '13class' in item.name.lower() or '21class' in item.name.lower():
                            print(f"  [OLD?] {item.name:40} {format_size(size):>15}")
                        else:
                            print(f"         {item.name:40} {format_size(size):>15}")
                
                subtotal = sum(x[1] for x in items)
                print(f"         {'SUBTOTAL':40} {format_size(subtotal):>15}")
    
    # D:/data/raw breakdown
    print("\n" + "=" * 80)
    print("D:/data/raw/ BREAKDOWN (raw source datasets)")
    print("=" * 80)
    
    data_raw = Path("D:/data/raw")
    if data_raw.exists():
        items = []
        for item in sorted(data_raw.iterdir()):
            if item.is_dir():
                print(f"  Scanning {item.name}...", end=" ", flush=True)
                size = get_dir_size_full(item)
                items.append((item.name, size))
                print(f"{format_size(size)}")
        
        print()
        print("Summary (sorted by size):")
        print("-" * 80)
        for name, size in sorted(items, key=lambda x: x[1], reverse=True):
            print(f"  {name:40} {format_size(size):>15}")
        
        subtotal = sum(x[1] for x in items)
        print(f"  {'TOTAL':40} {format_size(subtotal):>15}")
    
    # =========================================================================
    # SEARCH FOR OLD CLASS STRUCTURES
    # =========================================================================
    print("\n" + "=" * 80)
    print("SEARCH FOR OLD 13-CLASS / 21-CLASS DATA")
    print("=" * 80)
    
    print("\nSearching D:/cold_storage for old class references...")
    old_refs = []
    cold_storage = Path("D:/cold_storage")
    if cold_storage.exists():
        for item in cold_storage.rglob("*"):
            name = item.name.lower()
            if '13class' in name or '21class' in name or '13_class' in name or '21_class' in name:
                if item.is_dir():
                    size = get_dir_size_fast(item)
                    old_refs.append((str(item), size, 'dir'))
                else:
                    size = item.stat().st_size
                    old_refs.append((str(item), size, 'file'))
    
    if old_refs:
        print("\nFound old class structure references:")
        for path, size, type_ in old_refs:
            print(f"  [{type_:4}] {path}")
            print(f"         Size: {format_size(size)}")
    else:
        print("  No 13-class or 21-class references found in cold_storage")
    
    print("\nSearching D:/data for old class references...")
    data_dir = Path("D:/data")
    if data_dir.exists():
        old_refs_data = []
        for item in data_dir.rglob("*"):
            name = item.name.lower()
            if '13class' in name or '21class' in name:
                if item.is_dir():
                    old_refs_data.append((str(item), 'dir'))
                else:
                    old_refs_data.append((str(item), 'file'))
        
        if old_refs_data:
            print("\nFound old class structure references in D:/data:")
            for path, type_ in old_refs_data:
                print(f"  [{type_:4}] {path}")
        else:
            print("  No 13-class or 21-class references found in D:/data")
    
    # =========================================================================
    # CHECK FOR OLD/STALE DATA
    # =========================================================================
    print("\n" + "=" * 80)
    print("CHECK FOR STALE/OLD DATA (by modification time)")
    print("=" * 80)
    
    # Check cold_storage runs for old dates
    runs_dir = Path("D:/cold_storage/runs")
    if runs_dir.exists():
        print("\nD:/cold_storage/runs/ modification times:")
        print("-" * 80)
        for run in sorted(runs_dir.iterdir()):
            if run.is_dir():
                try:
                    mtime = datetime.fromtimestamp(run.stat().st_mtime)
                    age_days = (datetime.now() - mtime).days
                    size = get_dir_size_fast(run)
                    
                    if age_days > 30:
                        status = "[OLD]"
                    else:
                        status = "     "
                    
                    print(f"  {status} {run.name:40} {mtime.strftime('%Y-%m-%d'):>12} "
                          f"({age_days:>3} days) {format_size(size):>12}")
                except:
                    print(f"        {run.name:40} (error reading)")
    
    # Check datasets in cold_storage
    datasets_dir = Path("D:/cold_storage/datasets")
    if datasets_dir.exists():
        print("\nD:/cold_storage/datasets/ modification times:")
        print("-" * 80)
        for ds in sorted(datasets_dir.iterdir()):
            if ds.is_dir():
                try:
                    mtime = datetime.fromtimestamp(ds.stat().st_mtime)
                    age_days = (datetime.now() - mtime).days
                    size = get_dir_size_fast(ds)
                    
                    if age_days > 60:
                        status = "[OLD]"
                    else:
                        status = "     "
                    
                    print(f"  {status} {ds.name:40} {mtime.strftime('%Y-%m-%d'):>12} "
                          f"({age_days:>3} days) {format_size(size):>12}")
                except:
                    print(f"        {ds.name:40} (error reading)")
    
    # =========================================================================
    # F: DRIVE QUICK CHECK
    # =========================================================================
    print("\n" + "=" * 80)
    print("F: DRIVE DATASETS (for reference)")
    print("=" * 80)
    
    f_datasets = Path("F:/datasets")
    if f_datasets.exists():
        print("\nF:/datasets/ contents:")
        print("-" * 80)
        for ds in sorted(f_datasets.iterdir()):
            if ds.is_dir():
                # Check if it's indexed (has train/val structure)
                train_npy = ds / "train" / "train_labels_labels.npy"
                if train_npy.exists():
                    import numpy as np
                    try:
                        count = len(np.load(train_npy, mmap_mode='r'))
                        print(f"  {ds.name:40} ~{count:,} train samples")
                    except:
                        print(f"  {ds.name:40} (indexed dataset)")
                else:
                    print(f"  {ds.name:40} (raw/utility)")
    
    # =========================================================================
    # RECOMMENDATIONS
    # =========================================================================
    print("\n" + "=" * 80)
    print("CLEANUP RECOMMENDATIONS")
    print("=" * 80)
    
    print("""
Based on the audit above, look for:

1. OLD CLASS STRUCTURES: Any folders with '13class' or '21class' in the name
   are from old experiments and can likely be deleted.

2. OLD TRAINING RUNS: Runs in D:/cold_storage/runs/ that are very old and
   don't have any useful checkpoints you want to keep.

3. DUPLICATE RAW DATA: Check if D:/data/raw/ datasets are also extracted
   elsewhere (like F:/datasets/). Raw archives can often be deleted if
   the extracted versions exist.

4. INTERMEDIATE DATASETS: Dataset versions like 'prod_v4_*' or older
   that predate your current 'prod_v5_cleaned' workflow.

To delete a folder safely:
  import shutil
  shutil.rmtree('D:/path/to/old/folder')

Or move to a 'to_delete' folder first to verify:
  shutil.move('D:/path/to/old', 'D:/to_delete/old')
""")
    
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
