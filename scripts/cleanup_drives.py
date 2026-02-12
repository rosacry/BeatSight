#!/usr/bin/env python3
"""
Cleanup script to move unused/archivable data from C: and F: to D: cold storage.

This script identifies:
1. Old datasets on F: that aren't currently being used for training
2. Old training runs on C: that are no longer needed
3. Other large files that can be archived

It moves files to D:/cold_storage/ while preserving directory structure.
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Optional


# Configuration
ACTIVE_DATASET = "prod_v5_cleaned"  # Current dataset being used for training
ACTIVE_RUN = "v5_phase1"  # Current training run
DRY_RUN = True  # Set to False to actually move files


def format_size(size_bytes):
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def get_dir_size(path, quick=True):
    """Get total size of a directory in bytes.
    
    If quick=True, only scans first level for speed estimate.
    """
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                if quick:
                    # For speed, just check first level of subdirs
                    try:
                        for subentry in os.scandir(entry.path):
                            if subentry.is_file(follow_symlinks=False):
                                total += subentry.stat().st_size
                    except:
                        pass
                else:
                    total += get_dir_size(entry.path, quick=False)
    except (PermissionError, OSError):
        pass
    return total


def get_drive_usage(drive_path):
    """Get drive usage stats."""
    total, used, free = shutil.disk_usage(drive_path)
    return {
        'total': total,
        'used': used,
        'free': free,
        'percent_used': (used / total) * 100
    }


def identify_archivable_datasets(datasets_dir: Path):
    """Identify datasets that can be archived."""
    archivable = []
    keep = []
    
    for ds in sorted(datasets_dir.iterdir()):
        if not ds.is_dir():
            continue
            
        name = ds.name
        size = get_dir_size(ds)
        
        # Always keep active dataset and feature cache (handled separately)
        if name == ACTIVE_DATASET:
            keep.append({
                'name': name,
                'path': ds,
                'size': size,
                'reason': 'ACTIVE - currently being used for training'
            })
        elif name == 'feature_cache':
            keep.append({
                'name': name,
                'path': ds,
                'size': size,
                'reason': 'SHARED - consolidated feature cache'
            })
        elif name in ['soundfonts', 'augmented_rare_classes']:
            # Keep utility folders
            keep.append({
                'name': name,
                'path': ds,
                'size': size,
                'reason': 'UTILITY - needed for processing'
            })
        else:
            # Everything else can be archived
            archivable.append({
                'name': name,
                'path': ds,
                'size': size,
                'reason': 'ARCHIVABLE - old/intermediate dataset version'
            })
    
    return archivable, keep


def identify_archivable_runs(runs_dir: Path):
    """Identify training runs that can be archived."""
    archivable = []
    keep = []
    
    for run in sorted(runs_dir.iterdir()):
        if not run.is_dir():
            continue
            
        name = run.name
        size = get_dir_size(run)
        
        if name == ACTIVE_RUN:
            keep.append({
                'name': name,
                'path': run,
                'size': size,
                'reason': 'ACTIVE - current training run'
            })
        else:
            archivable.append({
                'name': name,
                'path': run,
                'size': size,
                'reason': 'ARCHIVABLE - old training run'
            })
    
    return archivable, keep


def identify_archivable_logs(logs_dir: Path):
    """Identify old logs that can be archived."""
    archivable = []
    keep = []
    
    # Keep recent logs (less than 7 days old)
    cutoff = datetime.now().timestamp() - (7 * 24 * 60 * 60)
    
    for item in sorted(logs_dir.iterdir()):
        if item.is_dir():
            # Check last modification time
            try:
                mtime = item.stat().st_mtime
                size = get_dir_size(item)
                
                if mtime < cutoff:
                    archivable.append({
                        'name': item.name,
                        'path': item,
                        'size': size,
                        'reason': 'ARCHIVABLE - old log directory'
                    })
                else:
                    keep.append({
                        'name': item.name,
                        'path': item,
                        'size': size,
                        'reason': 'RECENT - modified within 7 days'
                    })
            except:
                pass
        elif item.suffix in ['.log', '.json']:
            try:
                mtime = item.stat().st_mtime
                size = item.stat().st_size
                
                if mtime < cutoff and size > 1024 * 1024:  # Only archive logs > 1MB
                    archivable.append({
                        'name': item.name,
                        'path': item,
                        'size': size,
                        'reason': 'ARCHIVABLE - old log file'
                    })
            except:
                pass
    
    return archivable, keep


def move_to_cold_storage(item: dict, cold_storage_base: Path, category: str):
    """Move an item to cold storage."""
    src = item['path']
    dest_dir = cold_storage_base / category
    dest = dest_dir / src.name
    
    if DRY_RUN:
        print(f"  [DRY RUN] Would move: {src}")
        print(f"             To: {dest}")
        return True
    
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        if dest.exists():
            print(f"  [SKIP] Destination already exists: {dest}")
            return False
        
        print(f"  Moving: {src}")
        print(f"      To: {dest}")
        
        if src.is_dir():
            shutil.move(str(src), str(dest))
        else:
            shutil.move(str(src), str(dest))
        
        print(f"  [OK] Moved successfully")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to move: {e}")
        return False


def main():
    print("=" * 70)
    print("DRIVE CLEANUP SCRIPT")
    print(f"Active dataset: {ACTIVE_DATASET}")
    print(f"Active run: {ACTIVE_RUN}")
    print(f"Mode: {'DRY RUN (no changes)' if DRY_RUN else 'LIVE (will move files)'}")
    print("=" * 70)
    print()
    
    # Check drive status
    print("Drive Status:")
    print("-" * 70)
    for drive, name in [('F:/', 'F: (datasets)'), ('D:/', 'D: (cold storage)'), ('C:/', 'C: (system)')]:
        try:
            usage = get_drive_usage(drive)
            print(f"  {name:20} {format_size(usage['used']):>12} used / {format_size(usage['total']):>12} total "
                  f"({usage['percent_used']:.1f}%) - {format_size(usage['free'])} free")
        except:
            print(f"  {name:20} (not accessible)")
    print()
    
    cold_storage = Path("D:/cold_storage")
    
    # Analyze F:/datasets
    print("=" * 70)
    print("F:/datasets analysis")
    print("=" * 70)
    
    datasets_dir = Path("F:/datasets")
    if datasets_dir.exists():
        archivable_datasets, keep_datasets = identify_archivable_datasets(datasets_dir)
        
        print("\n  KEEP (do not move):")
        print("-" * 70)
        for item in keep_datasets:
            print(f"    {item['name']:40} {format_size(item['size']):>12} - {item['reason']}")
        
        print("\n  ARCHIVABLE (can move to D:):")
        print("-" * 70)
        total_archivable = 0
        for item in archivable_datasets:
            print(f"    {item['name']:40} {format_size(item['size']):>12}")
            total_archivable += item['size']
        print(f"    {'TOTAL':40} {format_size(total_archivable):>12}")
    
    # Analyze F:/feature_cache
    print("\n" + "=" * 70)
    print("F:/feature_cache analysis")
    print("=" * 70)
    feature_cache = Path("F:/feature_cache")
    if feature_cache.exists():
        cache_size = get_dir_size(feature_cache)
        print(f"  Size: {format_size(cache_size)}")
        print("  Status: KEEP - shared feature cache, used by training")
    
    # Analyze C:/github/BeatSight/ai-pipeline/runs
    print("\n" + "=" * 70)
    print("C:/ai-pipeline/runs analysis")
    print("=" * 70)
    
    runs_dir = Path("C:/github/BeatSight/ai-pipeline/runs")
    if runs_dir.exists():
        archivable_runs, keep_runs = identify_archivable_runs(runs_dir)
        
        print("\n  KEEP (do not move):")
        print("-" * 70)
        for item in keep_runs:
            print(f"    {item['name']:40} {format_size(item['size']):>12} - {item['reason']}")
        
        print("\n  ARCHIVABLE (can move to D:):")
        print("-" * 70)
        total_archivable_runs = 0
        for item in archivable_runs:
            print(f"    {item['name']:40} {format_size(item['size']):>12}")
            total_archivable_runs += item['size']
        print(f"    {'TOTAL':40} {format_size(total_archivable_runs):>12}")
    
    # Analyze logs
    print("\n" + "=" * 70)
    print("C:/logs analysis")
    print("=" * 70)
    
    logs_dir = Path("C:/github/BeatSight/logs")
    archivable_logs = []
    if logs_dir.exists():
        archivable_logs, keep_logs = identify_archivable_logs(logs_dir)
        
        if archivable_logs:
            print("\n  ARCHIVABLE logs:")
            print("-" * 70)
            total_archivable_logs = 0
            for item in archivable_logs:
                print(f"    {item['name']:40} {format_size(item['size']):>12}")
                total_archivable_logs += item['size']
            print(f"    {'TOTAL':40} {format_size(total_archivable_logs):>12}")
        else:
            print("  No old logs to archive")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total_to_move = sum(x['size'] for x in archivable_datasets) if datasets_dir.exists() else 0
    total_to_move += sum(x['size'] for x in archivable_runs) if runs_dir.exists() else 0
    total_to_move += sum(x['size'] for x in archivable_logs)
    
    d_usage = get_drive_usage('D:/')
    
    print(f"  Total to archive: {format_size(total_to_move)}")
    print(f"  D: drive free space: {format_size(d_usage['free'])}")
    
    if total_to_move > d_usage['free']:
        print("\n  [WARNING] Not enough space on D: drive!")
        print("  You may need to clear some space on D: first, or archive selectively.")
    else:
        print("\n  [OK] Sufficient space available on D:")
    
    # Offer to execute
    if not DRY_RUN:
        print("\n" + "=" * 70)
        print("EXECUTING MOVES")
        print("=" * 70)
        
        # Move datasets
        if archivable_datasets:
            print("\nMoving datasets to D:/cold_storage/datasets/...")
            for item in archivable_datasets:
                move_to_cold_storage(item, cold_storage, 'datasets')
        
        # Move runs
        if archivable_runs:
            print("\nMoving runs to D:/cold_storage/runs/...")
            for item in archivable_runs:
                move_to_cold_storage(item, cold_storage, 'runs')
        
        # Move logs
        if archivable_logs:
            print("\nMoving logs to D:/cold_storage/logs/...")
            for item in archivable_logs:
                move_to_cold_storage(item, cold_storage, 'logs')
        
        print("\n[DONE] Cleanup complete!")
    else:
        print("\n" + "-" * 70)
        print("This was a DRY RUN. To actually move files, set DRY_RUN = False")
        print("and run the script again.")


if __name__ == "__main__":
    main()
