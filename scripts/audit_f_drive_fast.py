#!/usr/bin/env python3
"""Fast F: drive audit - only scans top-level, uses sampling for large dirs."""

import os
import json
import shutil
from pathlib import Path


def main():
    f_drive = Path("F:/")
    
    # Get drive usage
    total, used, free = shutil.disk_usage(f_drive)
    print("=" * 70)
    print("F: Drive Usage")
    print(f"  Total: {total/1e9:.2f} GB")
    print(f"  Used:  {used/1e9:.2f} GB")
    print(f"  Free:  {free/1e9:.2f} GB")
    print("=" * 70)
    
    # Quick scan - only top level
    print("\nTop-level directories (quick scan):")
    print("-" * 70)
    
    for item in sorted(f_drive.iterdir()):
        if item.is_dir():
            try:
                # Get size from first-level files only (fast)
                top_files_size = sum(
                    f.stat().st_size for f in item.iterdir() if f.is_file()
                )
                subdir_count = sum(1 for d in item.iterdir() if d.is_dir())
                file_count = sum(1 for f in item.iterdir() if f.is_file())
                print(f"{item.name:40} {file_count:>8} files, {subdir_count:>5} subdirs")
            except Exception as e:
                print(f"{item.name:40} Error: {e}")
    
    print("\n" + "=" * 70)
    print("DATASETS ANALYSIS")
    print("=" * 70)
    
    datasets = f_drive / "datasets"
    if datasets.exists():
        for ds in sorted(datasets.iterdir()):
            if ds.is_dir():
                print(f"\n{ds.name}/")
                
                # Check for metadata.json
                metadata_file = ds / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file) as f:
                            meta = json.load(f)
                        print(f"  Metadata: train={meta.get('train_samples', 'N/A'):,}, val={meta.get('val_samples', 'N/A'):,}")
                    except:
                        print("  Metadata: (error reading)")
                
                # Check train/val structure
                train_dir = ds / "train"
                val_dir = ds / "val"
                
                if train_dir.exists():
                    audio_dir = train_dir / "audio"
                    if audio_dir.exists():
                        # Just count first level items
                        try:
                            items = list(audio_dir.iterdir())[:10]
                            print(f"  train/audio/: exists ({len(items)}+ items)")
                        except:
                            print(f"  train/audio/: exists")
                    else:
                        # Count items in train
                        try:
                            items = list(train_dir.iterdir())[:10]
                            print(f"  train/: {len(items)}+ items")
                        except:
                            print(f"  train/: exists")
                
                if val_dir.exists():
                    print(f"  val/: exists")
                
                # Check for npy files
                npy_files = list(ds.glob("*.npy"))
                if npy_files:
                    print(f"  .npy files: {len(npy_files)}")
                    for nf in npy_files[:3]:
                        print(f"    - {nf.name} ({nf.stat().st_size/1e6:.1f} MB)")
    
    print("\n" + "=" * 70)
    print("FEATURE CACHE ANALYSIS")
    print("=" * 70)
    
    cache_dir = f_drive / "feature_cache"
    if cache_dir.exists():
        # Quick file count and prefixes
        prefixes = {}
        total_files = 0
        sample_sizes = []
        
        for item in cache_dir.iterdir():
            if item.is_file() and item.suffix == '.pt':
                total_files += 1
                prefix = item.name.split('_')[0]
                prefixes[prefix] = prefixes.get(prefix, 0) + 1
                if len(sample_sizes) < 100:
                    sample_sizes.append(item.stat().st_size)
        
        avg_size = sum(sample_sizes) / len(sample_sizes) if sample_sizes else 0
        print(f"\nTotal .pt files: {total_files:,}")
        print(f"Average size: {avg_size/1024:.2f} KB")
        print(f"Estimated total: {total_files * avg_size / 1e9:.2f} GB")
        print("\nBy prefix:")
        for prefix, count in sorted(prefixes.items(), key=lambda x: x[1], reverse=True):
            print(f"  {prefix}_*: {count:,}")
    
    print("\n" + "=" * 70)
    print("RECYCLE BIN")
    print("=" * 70)
    recycle = f_drive / "$RECYCLE.BIN"
    if recycle.exists():
        try:
            items = list(recycle.iterdir())
            print(f"Items in recycle bin: {len(items)}")
            # Can't easily scan recycle bin, just note it exists
        except:
            print("Cannot access recycle bin (permission denied)")
    
    print("\n" + "=" * 70)
    print("MANIFESTS")
    print("=" * 70)
    manifests = f_drive / "manifests"
    if manifests.exists():
        for item in sorted(manifests.iterdir())[:20]:
            if item.is_dir():
                print(f"  {item.name}/")
            else:
                print(f"  {item.name} ({item.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
