#!/usr/bin/env python3
"""
Rebuild labels from cache - creates labels that exactly match cache entries.
This guarantees 100% cache coverage.

The cache index maps: cache_key -> (shard_file, offset, length)
Cache key format: audio/uuid__class.pt (with backslash separator)
We reconstruct labels as: audio/uuid__class.wav
"""
import argparse
import json
import numpy as np
from pathlib import Path
from datetime import datetime
import shutil
import re

# 12-class mapping (after rimshot→snare merge)
CLASS_MAPPING = {
    'china': 0,
    'crash': 1,
    'cross_stick': 2, 'crossstick': 2, 'cross-stick': 2,
    'hihat_closed': 3, 'hihatclosed': 3, 'hihat-closed': 3, 'closed_hihat': 3,
    'hihat_open': 4, 'hihatopen': 4, 'hihat-open': 4, 'open_hihat': 4,
    'hihat_pedal': 5, 'hihatpedal': 5, 'hihat-pedal': 5, 'pedal_hihat': 5,
    'kick': 6, 'bass': 6, 'bd': 6,
    'ride_bell': 7, 'ridebell': 7, 'ride-bell': 7, 'bell': 7,
    'ride_bow': 8, 'ridebow': 8, 'ride-bow': 8, 'ride': 8,
    'snare': 9, 'sd': 9, 'rimshot': 9,  # rimshot merged into snare
    'splash': 10,
    'tom': 11, 'tom_hi': 11, 'tom_mid': 11, 'tom_low': 11, 'tom_floor': 11,
    'hightom': 11, 'midtom': 11, 'lowtom': 11, 'floortom': 11,
}


def extract_class_from_key(cache_key):
    """
    Extract class label from cache key.
    Key format examples:
    - audio\\uuid__snare.pt
    - audio\\dataset_uuid__kick.pt
    """
    # Get filename without directory and extension
    filename = cache_key.replace('\\', '/').split('/')[-1]
    if filename.endswith('.pt'):
        filename = filename[:-3]
    
    # Class is after last double underscore
    if '__' in filename:
        class_name = filename.split('__')[-1].lower()
    else:
        # Fallback: last underscore
        parts = filename.rsplit('_', 1)
        class_name = parts[-1].lower() if len(parts) > 1 else filename.lower()
    
    # Clean up any remaining extensions or junk
    class_name = class_name.replace('.wav', '').replace('.pt', '').strip()
    
    return CLASS_MAPPING.get(class_name, -1)


def main():
    parser = argparse.ArgumentParser(description="Rebuild labels from cache index")
    parser.add_argument("--cache-dir", required=True, help="Directory with cache index.json")
    parser.add_argument("--output-dir", required=True, help="Directory to write labels")
    parser.add_argument("--split", default="train", help="Split name (train/val)")
    parser.add_argument("--dry-run", action="store_true", help="Only report stats")
    args = parser.parse_args()
    
    cache_dir = Path(args.cache_dir)
    output_dir = Path(args.output_dir)
    split = args.split
    
    # Load cache index
    print(f"Loading cache index from {cache_dir}...")
    index_path = cache_dir / "index.json"
    with open(index_path, "r") as f:
        cache_index = json.load(f)
    
    print(f"  Found {len(cache_index):,} cache entries")
    
    # Convert cache keys to label format and extract classes
    print("Processing cache entries...")
    files = []
    labels = []
    class_counts = {}
    unknown_classes = {}
    
    for cache_key in cache_index.keys():
        # Convert cache key to label format
        # cache: audio\uuid__class.pt -> label: audio/uuid__class.wav
        label_path = cache_key.replace('\\', '/').replace('.pt', '.wav')
        
        # Extract class
        class_id = extract_class_from_key(cache_key)
        
        if class_id == -1:
            # Unknown class - try to extract for reporting
            filename = cache_key.split('\\')[-1] if '\\' in cache_key else cache_key
            class_part = filename.split('__')[-1].replace('.pt', '') if '__' in filename else 'unknown'
            unknown_classes[class_part] = unknown_classes.get(class_part, 0) + 1
            continue
        
        files.append(label_path)
        labels.append(class_id)
        class_counts[class_id] = class_counts.get(class_id, 0) + 1
    
    print(f"\n  Valid entries: {len(files):,}")
    print(f"  Unknown class entries: {sum(unknown_classes.values()):,}")
    
    if unknown_classes:
        print(f"\n  Unknown classes (top 10):")
        for cls, cnt in sorted(unknown_classes.items(), key=lambda x: -x[1])[:10]:
            print(f"    {cls}: {cnt:,}")
    
    print(f"\n  Class distribution:")
    for cls_id in sorted(class_counts.keys()):
        print(f"    Class {cls_id}: {class_counts[cls_id]:,}")
    
    if args.dry_run:
        print("\n[DRY RUN] Would create labels with above stats")
        return
    
    # Backup existing if present
    files_path = output_dir / f"{split}_labels_files.npy"
    labels_path = output_dir / f"{split}_labels_labels.npy"
    
    if files_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_files = output_dir / f"{split}_labels_files.npy.bak_rebuild_{timestamp}"
        backup_labels = output_dir / f"{split}_labels_labels.npy.bak_rebuild_{timestamp}"
        print(f"\nBacking up existing labels...")
        shutil.copy(files_path, backup_files)
        shutil.copy(labels_path, backup_labels)
    
    # Save new labels
    print(f"\nSaving {len(files):,} entries to {output_dir}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert to numpy arrays
    files_arr = np.array(files, dtype=object)
    labels_arr = np.array(labels, dtype=np.int64)
    
    np.save(files_path, files_arr)
    np.save(labels_path, labels_arr)
    
    print(f"\nDone! Created:")
    print(f"  {files_path}")
    print(f"  {labels_path}")
    print(f"  Total samples: {len(files):,} (100% cache coverage guaranteed)")


if __name__ == "__main__":
    main()
