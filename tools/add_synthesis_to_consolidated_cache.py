#!/usr/bin/env python3
"""
Add synthesized .pt files to the consolidated cache.

This script:
1. Finds all synthesized lakh_china_*.pt and lakh_splash_*.pt files
2. Creates new shard files for them
3. Updates the cache index.json

Usage:
    python tools/add_synthesis_to_consolidated_cache.py
"""

import json
import mmap
import os
import struct
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch

# Configuration
FEATURE_CACHE_DIR = Path("F:/feature_cache/train")
SAMPLES_PER_SHARD = 65536  # Match existing shard size
DTYPE = torch.float32
TENSOR_SHAPE = (128, 128)  # mel spectrogram shape


def find_synthesized_files(cache_dir: Path) -> List[Path]:
    """Find all synthesized .pt files."""
    pt_files = []
    
    print(f"Scanning {cache_dir} for synthesized .pt files...")
    
    for f in cache_dir.iterdir():
        if f.suffix == '.pt' and (f.name.startswith('lakh_china_') or f.name.startswith('lakh_splash_')):
            pt_files.append(f)
    
    print(f"Found {len(pt_files):,} synthesized .pt files")
    return pt_files


def load_existing_index(cache_dir: Path) -> Dict:
    """Load the existing cache index."""
    index_path = cache_dir / "index.json"
    
    print(f"Loading existing index from {index_path}...")
    start = time.time()
    
    with open(index_path) as f:
        index = json.load(f)
    
    print(f"Loaded {len(index):,} entries in {time.time() - start:.1f}s")
    return index


def load_manifest(cache_dir: Path) -> Dict:
    """Load or create the cache manifest."""
    manifest_path = cache_dir / "cache_manifest.json"
    
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    
    # Manifest doesn't exist - create it from existing shards
    print("  Manifest not found, creating from existing shards...")
    
    shard_files = sorted(cache_dir.glob("shard_*.bin"))
    
    if not shard_files:
        # No shards exist yet
        return {
            "total_samples": 0,
            "tensor_shape": list(TENSOR_SHAPE),
            "dtype": "torch.float32",
            "bytes_per_sample": TENSOR_SHAPE[0] * TENSOR_SHAPE[1] * 4,
            "num_shards": 0,
            "shards": [],
        }
    
    # Infer from existing index and shards
    bytes_per_sample = TENSOR_SHAPE[0] * TENSOR_SHAPE[1] * 4  # float32
    
    shards_info = []
    total_samples = 0
    
    for shard_file in shard_files:
        shard_id = int(shard_file.stem.split('_')[1])
        file_size = shard_file.stat().st_size
        num_samples = file_size // bytes_per_sample
        
        shards_info.append({
            "shard_id": shard_id,
            "num_samples": num_samples,
            "start_idx": total_samples,
        })
        total_samples += num_samples
    
    manifest = {
        "total_samples": total_samples,
        "tensor_shape": list(TENSOR_SHAPE),
        "dtype": "torch.float32",
        "bytes_per_sample": bytes_per_sample,
        "num_shards": len(shards_info),
        "shards": shards_info,
    }
    
    print(f"  Created manifest: {total_samples:,} samples in {len(shards_info)} shards")
    
    return manifest


def save_manifest(cache_dir: Path, manifest: Dict):
    """Save the cache manifest."""
    manifest_path = cache_dir / "cache_manifest.json"
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def create_shard(
    pt_files: List[Path],
    shard_id: int,
    cache_dir: Path,
    tensor_shape: Tuple[int, int],
    dtype: torch.dtype,
) -> Tuple[Dict[str, List], int]:
    """Create a new shard file from .pt files.
    
    Returns:
        Tuple of (index_entries, num_samples)
    """
    shard_path = cache_dir / f"shard_{shard_id:05d}.bin"
    
    # Calculate sizes
    if dtype == torch.float32:
        np_dtype = np.float32
        bytes_per_element = 4
    elif dtype == torch.float16:
        np_dtype = np.float16
        bytes_per_element = 2
    else:
        np_dtype = np.float32
        bytes_per_element = 4
    
    numel = tensor_shape[0] * tensor_shape[1]
    bytes_per_sample = numel * bytes_per_element
    
    index_entries = {}
    num_written = 0
    
    print(f"  Creating shard {shard_id} with {len(pt_files)} samples...")
    
    with open(shard_path, 'wb') as f:
        for i, pt_file in enumerate(pt_files):
            try:
                # Load the .pt file
                tensor = torch.load(pt_file, map_location='cpu')
                
                # Ensure correct shape
                if tensor.shape != tensor_shape:
                    # Try to reshape or pad
                    if tensor.ndim == 2:
                        # Pad or crop to target shape
                        h, w = tensor.shape
                        th, tw = tensor_shape
                        
                        new_tensor = torch.zeros(tensor_shape, dtype=tensor.dtype)
                        copy_h = min(h, th)
                        copy_w = min(w, tw)
                        new_tensor[:copy_h, :copy_w] = tensor[:copy_h, :copy_w]
                        tensor = new_tensor
                    else:
                        print(f"    [SKIP] {pt_file.name}: unexpected shape {tensor.shape}")
                        continue
                
                # Convert to numpy and write
                arr = tensor.numpy().astype(np_dtype)
                f.write(arr.tobytes())
                
                # Record index entry
                file_id = pt_file.stem  # e.g., "lakh_china_abc123"
                index_entries[file_id] = [shard_id, num_written]
                
                num_written += 1
                
                if (i + 1) % 10000 == 0:
                    print(f"    Progress: {i+1}/{len(pt_files)}")
                    
            except Exception as e:
                print(f"    [ERROR] {pt_file.name}: {e}")
                continue
    
    print(f"  Wrote {num_written} samples to {shard_path.name}")
    return index_entries, num_written


def main():
    print("=" * 70)
    print("ADD SYNTHESIZED SAMPLES TO CONSOLIDATED CACHE")
    print("=" * 70)
    
    # Find synthesized files
    pt_files = find_synthesized_files(FEATURE_CACHE_DIR)
    
    if not pt_files:
        print("\nNo synthesized .pt files found!")
        print("Run the synthesis scripts first:")
        print("  python tools/synthesize_lakh_drums.py --target-class china ...")
        print("  python tools/synthesize_lakh_drums.py --target-class splash ...")
        return
    
    # Separate by class for reporting
    china_files = [f for f in pt_files if 'china' in f.name]
    splash_files = [f for f in pt_files if 'splash' in f.name]
    print(f"\n  China files: {len(china_files):,}")
    print(f"  Splash files: {len(splash_files):,}")
    
    # Load existing index and manifest
    index = load_existing_index(FEATURE_CACHE_DIR)
    manifest = load_manifest(FEATURE_CACHE_DIR)
    
    # Check which files are NOT already in index
    existing_keys = set(index.keys())
    new_files = [f for f in pt_files if f.stem not in existing_keys]
    
    print(f"\nFiles already in index: {len(pt_files) - len(new_files):,}")
    print(f"New files to add: {len(new_files):,}")
    
    if not new_files:
        print("\nAll synthesized files are already in the index!")
        return
    
    # Determine next shard ID
    existing_shards = manifest.get("shards", [])
    if existing_shards:
        max_shard_id = max(s["shard_id"] for s in existing_shards)
    else:
        max_shard_id = -1
    
    next_shard_id = max_shard_id + 1
    print(f"\nStarting from shard ID: {next_shard_id}")
    
    # Create shards
    all_new_entries = {}
    new_shards_info = []
    total_new_samples = 0
    
    # Process in batches of SAMPLES_PER_SHARD
    for batch_start in range(0, len(new_files), SAMPLES_PER_SHARD):
        batch_end = min(batch_start + SAMPLES_PER_SHARD, len(new_files))
        batch_files = new_files[batch_start:batch_end]
        
        shard_id = next_shard_id + (batch_start // SAMPLES_PER_SHARD)
        
        entries, num_samples = create_shard(
            batch_files,
            shard_id,
            FEATURE_CACHE_DIR,
            TENSOR_SHAPE,
            DTYPE,
        )
        
        all_new_entries.update(entries)
        total_new_samples += num_samples
        
        # Record shard info
        new_shards_info.append({
            "shard_id": shard_id,
            "num_samples": num_samples,
            "start_idx": manifest["total_samples"] + total_new_samples - num_samples,
        })
    
    print(f"\nCreated {len(new_shards_info)} new shard(s) with {total_new_samples:,} samples")
    
    # Update index
    print(f"\nUpdating index.json...")
    index.update(all_new_entries)
    
    index_path = FEATURE_CACHE_DIR / "index.json"
    
    # Backup existing index
    backup_path = FEATURE_CACHE_DIR / "index.json.bak_synth"
    if index_path.exists():
        import shutil
        shutil.copy2(index_path, backup_path)
        print(f"  Backed up to {backup_path}")
    
    # Save updated index
    print(f"  Saving {len(index):,} entries...")
    start = time.time()
    with open(index_path, 'w') as f:
        json.dump(index, f)
    print(f"  Saved in {time.time() - start:.1f}s")
    
    # Update manifest
    print(f"\nUpdating manifest...")
    manifest["total_samples"] += total_new_samples
    manifest["num_shards"] += len(new_shards_info)
    manifest["shards"].extend(new_shards_info)
    
    save_manifest(FEATURE_CACHE_DIR, manifest)
    print(f"  Updated: {manifest['total_samples']:,} total samples, {manifest['num_shards']} shards")
    
    # Delete the individual .pt files (now consolidated)
    print(f"\nCleaning up individual .pt files...")
    deleted = 0
    for pt_file in new_files:
        if pt_file.stem in all_new_entries:
            try:
                pt_file.unlink()
                deleted += 1
            except Exception as e:
                print(f"  [WARN] Could not delete {pt_file.name}: {e}")
    
    print(f"  Deleted {deleted:,} .pt files")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUCCESS!")
    print("=" * 70)
    print(f"  Added {total_new_samples:,} synthesized samples to consolidated cache")
    print(f"  New shards: {[s['shard_id'] for s in new_shards_info]}")
    print(f"  Total cache size: {manifest['total_samples']:,} samples")
    print("\nNext steps:")
    print("  1. Update the labels to include these samples")
    print("  2. Optionally convert index to binary: python tools/convert_cache_index_to_binary.py F:/feature_cache/train --force")


if __name__ == "__main__":
    main()
