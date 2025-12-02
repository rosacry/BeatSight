#!/usr/bin/env python3
"""
Convert large label JSON files to memory-efficient numpy format.

This stores only the essential data (file paths as bytes, labels as int8,
and optionally velocities as float16) which uses ~10x less memory than Python dicts.

Usage:
    python tools/convert_labels_to_numpy.py data/dataset_index/train_labels.json
    
For velocity-enriched labels:
    python tools/convert_labels_to_numpy.py data/dataset_index/train_labels_with_velocity.json
"""

import pickle
import sys
import numpy as np
from pathlib import Path

try:
    import ijson
    USE_STREAMING = True
except ImportError:
    print("Warning: ijson not installed, falling back to json (high RAM usage)")
    USE_STREAMING = False


def convert_json_to_numpy(json_path: Path, output_path: Path) -> None:
    """Convert JSON labels to memory-efficient numpy format using memory-mapped file."""
    print(f"Converting {json_path} to {output_path}...")
    print(f"  Input size: {json_path.stat().st_size / 1e9:.2f} GB")
    
    # Stream the JSON and collect data in chunks to avoid OOM
    max_len = 0
    count = 0
    has_velocity = False
    
    # First pass: determine max length, count, and whether velocity is present
    print("  Pass 1: Scanning for dimensions...")
    if USE_STREAMING:
        with open(json_path, 'rb') as f:
            parser = ijson.items(f, 'item')
            for item in parser:
                file_path = item['file']
                max_len = max(max_len, len(file_path.encode('utf-8')))
                if 'velocity' in item and not has_velocity:
                    has_velocity = True
                    print("    Detected velocity field - will save velocities too")
                count += 1
                if count % 2000000 == 0:
                    print(f"    Scanned {count:,} items (max_len={max_len})...")
    else:
        import json
        with open(json_path, 'r') as f:
            data = json.load(f)
        for item in data:
            max_len = max(max_len, len(item['file'].encode('utf-8')))
            if 'velocity' in item:
                has_velocity = True
        count = len(data)
        if has_velocity:
            print("    Detected velocity field - will save velocities too")
    
    print(f"  Found {count:,} items, max path length: {max_len}")
    
    # Use memory-mapped files to avoid RAM limitations
    print("  Pass 2: Building memory-mapped arrays...")
    files_tmp = output_path.with_suffix('.files.tmp')
    labels_tmp = output_path.with_suffix('.labels.tmp')
    velocities_tmp = output_path.with_suffix('.velocities.tmp') if has_velocity else None
    
    # Create memory-mapped arrays on disk
    files_arr = np.memmap(files_tmp, dtype=f'S{max_len}', mode='w+', shape=(count,))
    labels_arr = np.memmap(labels_tmp, dtype=np.int8, mode='w+', shape=(count,))
    velocities_arr = np.memmap(velocities_tmp, dtype=np.float16, mode='w+', shape=(count,)) if has_velocity else None
    
    if USE_STREAMING:
        with open(json_path, 'rb') as f:
            parser = ijson.items(f, 'item')
            for i, item in enumerate(parser):
                files_arr[i] = item['file'].encode('utf-8')
                labels_arr[i] = item['component_idx']
                if velocities_arr is not None:
                    velocities_arr[i] = item.get('velocity', 0.7)
                if (i + 1) % 2000000 == 0:
                    print(f"    Loaded {i+1:,} items...")
                    # Flush to disk periodically
                    files_arr.flush()
                    labels_arr.flush()
                    if velocities_arr is not None:
                        velocities_arr.flush()
    else:
        for i, item in enumerate(data):
            files_arr[i] = item['file'].encode('utf-8')
            labels_arr[i] = item['component_idx']
            if velocities_arr is not None:
                velocities_arr[i] = item.get('velocity', 0.7)
    
    # Flush final data
    files_arr.flush()
    labels_arr.flush()
    if velocities_arr is not None:
        velocities_arr.flush()
    
    # Save as uncompressed .npy files (can't compress without loading into RAM)
    print(f"  Saving to {output_path.parent}...")
    files_npy = output_path.with_name(output_path.stem + '_files.npy')
    labels_npy = output_path.with_name(output_path.stem + '_labels.npy')
    velocities_npy = output_path.with_name(output_path.stem + '_velocities.npy') if has_velocity else None
    
    # Save directly from memmap (no copy needed)
    np.save(files_npy, files_arr)
    np.save(labels_npy, labels_arr)
    if velocities_arr is not None:
        np.save(velocities_npy, velocities_arr)
    
    # Clean up temp files
    del files_arr
    del labels_arr
    files_tmp.unlink()
    labels_tmp.unlink()
    if velocities_arr is not None:
        del velocities_arr
        velocities_tmp.unlink()
    
    total_size = files_npy.stat().st_size + labels_npy.stat().st_size
    if velocities_npy:
        total_size += velocities_npy.stat().st_size
    print(f"  Done! Output size: {total_size / 1e6:.1f} MB")
    print(f"  Files: {files_npy} ({files_npy.stat().st_size / 1e6:.1f} MB)")
    print(f"  Labels: {labels_npy} ({labels_npy.stat().st_size / 1e6:.1f} MB)")
    if velocities_npy:
        print(f"  Velocities: {velocities_npy} ({velocities_npy.stat().st_size / 1e6:.1f} MB)")
    print(f"  {count:,} items")


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_labels_to_numpy.py <json_file> [output.npz]")
        sys.exit(1)
    
    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Error: {json_path} does not exist")
        sys.exit(1)
    
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = json_path.with_suffix('.npz')
    
    convert_json_to_numpy(json_path, output_path)


if __name__ == "__main__":
    main()
