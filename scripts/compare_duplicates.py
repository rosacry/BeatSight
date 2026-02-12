#!/usr/bin/env python3
"""
Compare potential duplicate datasets and check if raw data is already processed.
Run this script and share the output.
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime


def format_size(size_bytes):
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def get_dir_stats(path):
    """Get directory statistics: file count, total size, file types."""
    total_size = 0
    file_count = 0
    dir_count = 0
    extensions = {}
    sample_files = []
    
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            dir_count += len(dirnames)
            for f in filenames:
                file_count += 1
                fp = os.path.join(dirpath, f)
                try:
                    size = os.path.getsize(fp)
                    total_size += size
                    
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in extensions:
                        extensions[ext] = {'count': 0, 'size': 0}
                    extensions[ext]['count'] += 1
                    extensions[ext]['size'] += size
                    
                    # Collect sample file names
                    if len(sample_files) < 10:
                        rel_path = os.path.relpath(fp, path)
                        sample_files.append(rel_path)
                except:
                    pass
    except Exception as e:
        print(f"  Error scanning: {e}")
    
    return {
        'total_size': total_size,
        'file_count': file_count,
        'dir_count': dir_count,
        'extensions': extensions,
        'sample_files': sample_files
    }


def compare_directories(path1, path2, name1, name2):
    """Compare two directories to see if they're duplicates."""
    print(f"\nComparing:")
    print(f"  A: {path1}")
    print(f"  B: {path2}")
    print("-" * 80)
    
    p1 = Path(path1)
    p2 = Path(path2)
    
    if not p1.exists():
        print(f"  [ERROR] {name1} does not exist!")
        return
    if not p2.exists():
        print(f"  [ERROR] {name2} does not exist!")
        return
    
    print(f"\nScanning {name1}...")
    stats1 = get_dir_stats(p1)
    print(f"Scanning {name2}...")
    stats2 = get_dir_stats(p2)
    
    print(f"\n{'Metric':<30} {name1:>25} {name2:>25}")
    print("-" * 80)
    print(f"{'Total Size':<30} {format_size(stats1['total_size']):>25} {format_size(stats2['total_size']):>25}")
    print(f"{'File Count':<30} {stats1['file_count']:>25,} {stats2['file_count']:>25,}")
    print(f"{'Directory Count':<30} {stats1['dir_count']:>25,} {stats2['dir_count']:>25,}")
    
    # Compare file types
    print(f"\nFile types in {name1}:")
    for ext, data in sorted(stats1['extensions'].items(), key=lambda x: x[1]['size'], reverse=True)[:10]:
        print(f"  {ext or '(no ext)':<15} {data['count']:>10,} files  {format_size(data['size']):>15}")
    
    print(f"\nFile types in {name2}:")
    for ext, data in sorted(stats2['extensions'].items(), key=lambda x: x[1]['size'], reverse=True)[:10]:
        print(f"  {ext or '(no ext)':<15} {data['count']:>10,} files  {format_size(data['size']):>15}")
    
    # Sample files
    print(f"\nSample files from {name1}:")
    for f in stats1['sample_files'][:5]:
        print(f"  {f}")
    
    print(f"\nSample files from {name2}:")
    for f in stats2['sample_files'][:5]:
        print(f"  {f}")
    
    # Verdict
    print("\n" + "=" * 80)
    print("VERDICT:")
    
    size_diff = abs(stats1['total_size'] - stats2['total_size'])
    size_diff_pct = (size_diff / max(stats1['total_size'], stats2['total_size'])) * 100 if max(stats1['total_size'], stats2['total_size']) > 0 else 0
    
    if stats1['file_count'] == stats2['file_count'] and size_diff_pct < 1:
        print("  [LIKELY DUPLICATE] Same file count and nearly identical size")
        print(f"  -> You can probably delete one copy and save {format_size(min(stats1['total_size'], stats2['total_size']))}")
    elif stats1['file_count'] == stats2['file_count']:
        print("  [POSSIBLE DUPLICATE] Same file count but different sizes")
        print(f"  -> Size difference: {format_size(size_diff)} ({size_diff_pct:.1f}%)")
        print("  -> May have different compression or slight modifications")
    elif abs(stats1['file_count'] - stats2['file_count']) < 100:
        print("  [SIMILAR] Nearly same file count, might be related versions")
    else:
        print("  [DIFFERENT] These appear to be different datasets")
        print(f"  -> File count difference: {abs(stats1['file_count'] - stats2['file_count']):,}")
    
    return stats1, stats2


def check_raw_dataset_usage(raw_path, raw_name):
    """Check if a raw dataset is referenced in any processed datasets."""
    print(f"\nChecking if {raw_name} is used in processed datasets...")
    print("-" * 80)
    
    # Get info about the raw dataset
    raw_stats = get_dir_stats(raw_path)
    print(f"\n{raw_name} ({raw_path}):")
    print(f"  Size: {format_size(raw_stats['total_size'])}")
    print(f"  Files: {raw_stats['file_count']:,}")
    
    # Check for references in manifests
    manifest_dir = Path("F:/manifests")
    references_found = []
    
    if manifest_dir.exists():
        print(f"\nSearching F:/manifests for references to '{raw_name}'...")
        for manifest in manifest_dir.rglob("*.json"):
            try:
                content = manifest.read_text(errors='ignore')
                if raw_name.lower() in content.lower():
                    references_found.append(str(manifest))
            except:
                pass
    
    # Check dataset metadata
    datasets_dir = Path("F:/datasets")
    if datasets_dir.exists():
        print(f"\nSearching F:/datasets metadata for references to '{raw_name}'...")
        for metadata in datasets_dir.rglob("metadata.json"):
            try:
                content = metadata.read_text(errors='ignore')
                if raw_name.lower() in content.lower():
                    references_found.append(str(metadata))
            except:
                pass
    
    # Check for source references in dataset configs
    config_patterns = ["**/config*.json", "**/dataset*.json", "**/*manifest*.json"]
    for pattern in config_patterns:
        for config in Path("C:/github/BeatSight").rglob(pattern):
            try:
                content = config.read_text(errors='ignore')
                if raw_name.lower() in content.lower():
                    references_found.append(str(config))
            except:
                pass
    
    if references_found:
        print(f"\nFound {len(references_found)} reference(s) to '{raw_name}':")
        for ref in references_found[:10]:
            print(f"  {ref}")
        if len(references_found) > 10:
            print(f"  ... and {len(references_found) - 10} more")
    else:
        print(f"\nNo direct references to '{raw_name}' found in manifests/configs")
    
    return references_found


def main():
    print("=" * 80)
    print("DUPLICATE AND RAW DATA ANALYSIS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # =========================================================================
    # Question 1: Compare star_drums on D: vs F:
    # =========================================================================
    print("\n" + "=" * 80)
    print("QUESTION 1: Are star_drums datasets duplicates?")
    print("=" * 80)
    
    compare_directories(
        "D:/cold_storage/datasets/star_drums",
        "F:/datasets/star_drums_extracted",
        "D: star_drums",
        "F: star_drums_extracted"
    )
    
    # =========================================================================
    # Question 2: Is cambridge raw data already processed?
    # =========================================================================
    print("\n" + "=" * 80)
    print("QUESTION 2: Is cambridge (640 GB) already processed?")
    print("=" * 80)
    
    # First, let's understand what cambridge contains
    cambridge_path = Path("D:/data/raw/cambridge")
    if cambridge_path.exists():
        print(f"\nAnalyzing D:/data/raw/cambridge structure...")
        
        # Get top-level contents
        print("\nTop-level contents of cambridge/:")
        for item in sorted(cambridge_path.iterdir())[:20]:
            if item.is_dir():
                subcount = len(list(item.iterdir()))
                print(f"  {item.name}/ ({subcount} items)")
            else:
                print(f"  {item.name} ({format_size(item.stat().st_size)})")
        
        # Check references
        check_raw_dataset_usage(cambridge_path, "cambridge")
    
    # =========================================================================
    # Also check other large raw datasets
    # =========================================================================
    print("\n" + "=" * 80)
    print("BONUS: Check other large raw datasets")
    print("=" * 80)
    
    raw_datasets = [
        ("D:/data/raw/egmd", "egmd", "131 GB"),
        ("D:/data/raw/slakh2100", "slakh2100", "100 GB"),
        ("D:/data/raw/MedleyDB", "MedleyDB", "71 GB"),
    ]
    
    for path, name, size in raw_datasets:
        print(f"\n{name} ({size}):")
        refs = check_raw_dataset_usage(Path(path), name)
        if not refs:
            print(f"  -> No references found. May be unused or integrated differently.")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 80)
    print("""
Based on the analysis above:

1. STAR_DRUMS: If the comparison shows they're duplicates (same file count,
   similar size), you can delete the D:/cold_storage/datasets/star_drums
   copy and save ~506 GB.

2. CAMBRIDGE (640 GB): If no references are found in your manifests/configs,
   this raw data may have already been processed into your F:/datasets.
   However, be careful - raw data is often kept as a backup source.

3. OTHER RAW DATA: egmd, slakh2100, MedleyDB - check if these are still
   needed or if they've been fully processed.

BEFORE DELETING anything:
- Make sure you have the processed version in F:/datasets
- Check if any pipeline scripts reference the raw paths
- Consider moving to an external backup drive instead of deleting

To free up space safely, delete in this order:
1. D:/cold_storage/runs/12class_definitive_phase1/ (0 B - empty)
2. D:/cold_storage/runs/12class_phase2_specaug_focal/ (0 B - empty)
3. Duplicate star_drums if confirmed (506 GB)
4. Raw cambridge only if you're 100% sure it's processed (640 GB)
""")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
