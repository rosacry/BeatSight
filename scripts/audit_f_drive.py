#!/usr/bin/env python3
"""Audit F: drive to identify redundant and unnecessary data."""

import os
import shutil
from pathlib import Path


def get_dir_size(path):
    """Get total size of a directory in bytes."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_dir_size(entry.path)
    except (PermissionError, OSError):
        pass
    return total


def format_size(size_bytes):
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def main():
    f_drive = Path("F:/")
    
    # Get drive usage
    total, used, free = shutil.disk_usage(f_drive)
    print("=" * 70)
    print(f"F: Drive Usage")
    print(f"  Total: {format_size(total)}")
    print(f"  Used:  {format_size(used)}")
    print(f"  Free:  {format_size(free)}")
    print("=" * 70)
    print()
    
    # List top-level directories
    print("Top-level directories on F:/")
    print("-" * 70)
    
    dirs_with_sizes = []
    for item in f_drive.iterdir():
        if item.is_dir():
            size = get_dir_size(item)
            dirs_with_sizes.append((item.name, size))
    
    # Sort by size descending
    dirs_with_sizes.sort(key=lambda x: x[1], reverse=True)
    
    for name, size in dirs_with_sizes:
        print(f"{name:45} {format_size(size):>15}")
    
    print("-" * 70)
    print()
    
    # Check datasets directory in detail
    datasets_dir = f_drive / "datasets"
    if datasets_dir.exists():
        print("Subdirectories in F:/datasets/")
        print("-" * 70)
        
        subdirs = []
        for item in datasets_dir.iterdir():
            if item.is_dir():
                size = get_dir_size(item)
                subdirs.append((item.name, size))
        
        subdirs.sort(key=lambda x: x[1], reverse=True)
        
        for name, size in subdirs:
            print(f"  {name:43} {format_size(size):>15}")
        print("-" * 70)
    
    # Check feature_cache
    cache_dir = f_drive / "feature_cache"
    if cache_dir.exists():
        print()
        print("Feature cache analysis (F:/feature_cache/)")
        print("-" * 70)
        
        # Count files by prefix
        prefixes = {}
        total_files = 0
        for item in cache_dir.iterdir():
            if item.is_file() and item.suffix == '.pt':
                total_files += 1
                prefix = item.name.split('_')[0]
                prefixes[prefix] = prefixes.get(prefix, 0) + 1
        
        print(f"  Total .pt files: {total_files:,}")
        for prefix, count in sorted(prefixes.items(), key=lambda x: x[1], reverse=True):
            print(f"    {prefix}_*: {count:,} files")
        
        cache_size = get_dir_size(cache_dir)
        print(f"  Total size: {format_size(cache_size)}")
        if total_files > 0:
            avg_size = cache_size / total_files
            print(f"  Average file size: {format_size(avg_size)}")


if __name__ == "__main__":
    main()
