#!/usr/bin/env python3
"""
Filter labels to only include samples that exist in the consolidated cache.

This script reads the cache index.json and filters the labels numpy files
to exclude samples that don't have cached features.
"""

import argparse
import json
import numpy as np
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Filter labels by cache coverage")
    parser.add_argument("--labels-dir", required=True, help="Directory with train_labels_*.npy files")
    parser.add_argument("--cache-dir", required=True, help="Directory with consolidated cache (index.json)")
    parser.add_argument("--output-dir", required=True, help="Output directory for filtered labels")
    parser.add_argument("--dry-run", action="store_true", help="Don't write, just show stats")
    args = parser.parse_args()

    labels_dir = Path(args.labels_dir)
    cache_dir = Path(args.cache_dir)
    output_dir = Path(args.output_dir)

    # Load cache index
    index_path = cache_dir / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Cache index not found: {index_path}")

    print(f"Loading cache index from {index_path}...")
    with open(index_path, 'r') as f:
        cache_index = json.load(f)
    
    cache_keys = set(cache_index.keys())
    print(f"  Cache contains {len(cache_keys):,} entries")

    # Determine prefix from labels dir name (train or val)
    prefix = labels_dir.name  # 'train' or 'val'
    
    # Load labels
    files_path = labels_dir / f"{prefix}_labels_files.npy"
    labels_path = labels_dir / f"{prefix}_labels_labels.npy"
    
    if not files_path.exists() or not labels_path.exists():
        raise FileNotFoundError(f"Labels not found: {files_path} or {labels_path}")

    print(f"Loading labels from {labels_dir}...")
    files = np.load(files_path, allow_pickle=True)
    labels = np.load(labels_path)
    print(f"  Labels contain {len(labels):,} entries")

    # Find which samples have cache coverage
    print("Checking cache coverage...")
    valid_mask = np.zeros(len(files), dtype=bool)
    
    for i, file_bytes in enumerate(files):
        if i % 1000000 == 0:
            print(f"  Progress: {i:,}/{len(files):,} ({100*i/len(files):.1f}%)")
        
        # Decode file path
        if isinstance(file_bytes, bytes):
            file_path = file_bytes.decode('utf-8')
        else:
            file_path = str(file_bytes)
        
        # Convert to cache key format:
        # Labels use: audio/uuid__class.wav (forward slash, .wav)
        # Cache uses: audio\uuid__class.pt (backslash, .pt)
        cache_key = file_path.replace('/', '\\').replace('.wav', '.pt')
        
        if cache_key in cache_keys:
            valid_mask[i] = True

    valid_count = np.sum(valid_mask)
    missing_count = len(files) - valid_count
    print(f"\nCache coverage:")
    print(f"  Valid: {valid_count:,} ({100*valid_count/len(files):.2f}%)")
    print(f"  Missing: {missing_count:,} ({100*missing_count/len(files):.2f}%)")

    if args.dry_run:
        print("\n[DRY RUN] No files written")
        
        # Show some missing samples
        if missing_count > 0:
            print("\nSample missing entries:")
            missing_indices = np.where(~valid_mask)[0][:10]
            for idx in missing_indices:
                file_bytes = files[idx]
                if isinstance(file_bytes, bytes):
                    file_path = file_bytes.decode('utf-8')
                else:
                    file_path = str(file_bytes)
                print(f"  [{idx}] {file_path}")
        return

    # Filter and save
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filtered_files = files[valid_mask]
    filtered_labels = labels[valid_mask]
    
    out_files_path = output_dir / f"{prefix}_labels_files.npy"
    out_labels_path = output_dir / f"{prefix}_labels_labels.npy"
    
    print(f"\nSaving filtered labels to {output_dir}...")
    np.save(out_files_path, filtered_files)
    np.save(out_labels_path, filtered_labels)
    
    print(f"  Saved {len(filtered_labels):,} entries")
    print("Done!")


if __name__ == "__main__":
    main()
