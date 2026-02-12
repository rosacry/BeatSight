#!/usr/bin/env python3
"""Analyze F: drive storage and identify cold data for migration to D:."""

import os
from pathlib import Path

def get_dir_size_fast(path):
    """Get directory size quickly using os.scandir."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_dir_size_fast(entry.path)
    except (PermissionError, OSError):
        pass
    return total

def format_size(size_bytes):
    """Format size in human-readable format."""
    gb = size_bytes / (1024**3)
    if gb >= 1:
        return f"{gb:.2f} GB"
    mb = size_bytes / (1024**2)
    return f"{mb:.1f} MB"

print("=" * 70)
print("F: DRIVE STORAGE ANALYSIS - COLD DATA IDENTIFICATION")
print("=" * 70)

# Analyze datasets
print("\n[1] F:/datasets/ contents:")
datasets_dir = Path("F:/datasets")
sizes = []
for item in datasets_dir.iterdir():
    if item.is_dir():
        print(f"    Scanning {item.name}...", end="", flush=True)
        size = get_dir_size_fast(item)
        sizes.append((size, item.name, "dir"))
        print(f" {format_size(size)}")
    elif item.is_file():
        size = item.stat().st_size
        sizes.append((size, item.name, "file"))

sizes.sort(reverse=True)
total_datasets = sum(s[0] for s in sizes)

print(f"\n  {'Size':>12}  {'Name':<40}  Status")
print(f"  {'-'*12}  {'-'*40}  {'-'*15}")
for size, name, ftype in sizes:
    # Identify cold vs hot data
    if name == "prod_v5_fixed_20251212":
        status = "🔥 HOT (active)"
    elif name in ["lakh_midi", "soundfonts", "star_drums", "star_drums_extracted", "fsd50k"]:
        status = "❄️  COLD (source)"
    elif name in ["lakh_synthesized", "lakh_synthesized_splash", "augmented_rare_classes"]:
        status = "❄️  COLD (intermediate)"
    else:
        status = "❓ Check"
    print(f"  {format_size(size):>12}  {name:<40}  {status}")

print(f"  {'-'*12}  {'-'*40}")
print(f"  {format_size(total_datasets):>12}  TOTAL DATASETS")

# Analyze feature_cache
print("\n[2] F:/feature_cache/ contents:")
cache_dir = Path("F:/feature_cache")
cache_sizes = []
for item in cache_dir.iterdir():
    if item.is_dir():
        print(f"    Scanning {item.name}...", end="", flush=True)
        size = get_dir_size_fast(item)
        cache_sizes.append((size, item.name, "dir"))
        print(f" {format_size(size)}")
    elif item.is_file():
        size = item.stat().st_size
        cache_sizes.append((size, item.name, "file"))

cache_sizes.sort(reverse=True)
total_cache = sum(s[0] for s in cache_sizes)

print(f"\n  {'Size':>12}  {'Name':<40}  Status")
print(f"  {'-'*12}  {'-'*40}  {'-'*15}")
for size, name, ftype in cache_sizes:
    if name in ["train", "val"]:
        status = "🔥 HOT (active)"
    else:
        status = "❄️  COLD (backup)"
    print(f"  {format_size(size):>12}  {name:<40}  {status}")

print(f"  {'-'*12}  {'-'*40}")
print(f"  {format_size(total_cache):>12}  TOTAL CACHE")

# Check for backup files in train cache
print("\n[3] Backup files in F:/feature_cache/train/:")
train_dir = Path("F:/feature_cache/train")
backup_size = 0
backup_files = []
for f in train_dir.glob("*.bak*"):
    size = f.stat().st_size
    backup_size += size
    backup_files.append((size, f.name))
for f in train_dir.glob("*backup*"):
    size = f.stat().st_size
    backup_size += size
    backup_files.append((size, f.name))

if backup_files:
    for size, name in sorted(backup_files, reverse=True)[:10]:
        print(f"  {format_size(size):>12}  {name}")
    print(f"  {format_size(backup_size):>12}  TOTAL BACKUPS (can delete)")
else:
    print("  No backup files found")

# Summary
print("\n" + "=" * 70)
print("SUMMARY - COLD DATA TO MOVE TO D:")
print("=" * 70)

cold_data = []
# Datasets that can be moved
cold_datasets = ["lakh_midi", "soundfonts", "star_drums", "star_drums_extracted", 
                 "fsd50k", "lakh_synthesized", "lakh_synthesized_splash", "augmented_rare_classes"]
for size, name, _ in sizes:
    if name in cold_datasets:
        cold_data.append((size, f"F:/datasets/{name}"))

# Add any backup files
if backup_size > 0:
    cold_data.append((backup_size, "F:/feature_cache/train/*.bak* (DELETE)"))

total_cold = sum(s[0] for s in cold_data)
print(f"\n  {'Size':>12}  Path")
print(f"  {'-'*12}  {'-'*50}")
for size, path in sorted(cold_data, reverse=True):
    print(f"  {format_size(size):>12}  {path}")
print(f"  {'-'*12}")
print(f"  {format_size(total_cold):>12}  TOTAL COLD DATA")

print(f"\n  Total on F: drive: {format_size(total_datasets + total_cache)}")
print(f"  Cold data to move: {format_size(total_cold)}")
print(f"  Would free up: {100*total_cold/(total_datasets + total_cache):.1f}% of used space")
