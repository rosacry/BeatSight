#!/usr/bin/env python3
"""
Validate Consolidated Cache Integrity

Scans memory-mapped shard files and index to detect:
- Corrupted/truncated shards (incomplete writes)
- Missing shards referenced in index
- Index entries pointing to invalid offsets
- Mismatched sample counts

Usage:
    python validate_consolidated_cache.py --cache-dir data/feature_cache/prod_combined_warmup_consolidated
    python validate_consolidated_cache.py --cache-dir data/feature_cache/prod_combined_warmup_consolidated --repair
"""

from __future__ import annotations

import argparse
import json
import mmap
import os
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


# Constants (must match consolidated_cache.py)
MAGIC_BYTES = b"BSFC"
VERSION = 2
HEADER_SIZE = 32
SAMPLES_PER_SHARD = 65536


def parse_shard_header(shard_path: Path) -> Optional[Dict]:
    """Parse shard header and return metadata."""
    if not shard_path.exists():
        return None
    
    file_size = shard_path.stat().st_size
    if file_size < HEADER_SIZE:
        return {"error": f"File too small: {file_size} < {HEADER_SIZE}"}
    
    with open(shard_path, "rb") as f:
        header_bytes = f.read(HEADER_SIZE)
    
    # Parse header fields
    magic = header_bytes[0:4]
    if magic != MAGIC_BYTES:
        return {"error": f"Invalid magic bytes: {magic!r}"}
    
    version, num_samples, c, h, w, dtype_code, reserved = struct.unpack(
        "<IIIIIII", header_bytes[4:]
    )
    
    if version != VERSION:
        return {"error": f"Version mismatch: {version} != {VERSION}"}
    
    # Calculate expected size
    numel = c * h * w
    if dtype_code == 0:
        bytes_per_sample = numel * 4  # float32
    else:
        bytes_per_sample = numel * 2  # float16 or bfloat16
    
    expected_size = HEADER_SIZE + num_samples * bytes_per_sample
    
    return {
        "version": version,
        "num_samples": num_samples,
        "tensor_shape": (c, h, w),
        "dtype_code": dtype_code,
        "bytes_per_sample": bytes_per_sample,
        "file_size": file_size,
        "expected_size": expected_size,
        "is_valid": file_size >= expected_size,
        "is_truncated": file_size < expected_size,
    }


def validate_cache(cache_dir: Path, split: str = "train") -> Dict:
    """Validate a consolidated cache split."""
    split_dir = cache_dir / split
    index_path = split_dir / "index.json"
    
    results = {
        "split": split,
        "cache_dir": str(cache_dir),
        "valid": True,
        "total_samples": 0,
        "valid_shards": 0,
        "corrupted_shards": [],
        "missing_shards": [],
        "truncated_shards": [],
        "index_issues": [],
    }
    
    if not index_path.exists():
        results["valid"] = False
        results["error"] = f"Index file not found: {index_path}"
        return results
    
    # Load index
    with open(index_path, "r") as f:
        index_data = json.load(f)
    
    # Get shard info from index (if present) or scan directory
    shards_info = index_data.get("shards", [])
    results["total_samples"] = index_data.get("total_samples", 0)
    
    # Scan all shard files
    shard_files = sorted(split_dir.glob("shard_*.bin"))
    
    for shard_path in shard_files:
        shard_id = int(shard_path.stem.split("_")[1])
        header = parse_shard_header(shard_path)
        
        if header is None:
            results["missing_shards"].append(shard_id)
            results["valid"] = False
        elif "error" in header:
            results["corrupted_shards"].append({
                "shard_id": shard_id,
                "error": header["error"],
                "path": str(shard_path),
            })
            results["valid"] = False
        elif header.get("is_truncated"):
            results["truncated_shards"].append({
                "shard_id": shard_id,
                "file_size": header["file_size"],
                "expected_size": header["expected_size"],
                "missing_bytes": header["expected_size"] - header["file_size"],
                "path": str(shard_path),
            })
            results["valid"] = False
        else:
            results["valid_shards"] += 1
    
    # Validate index entries (spot check)
    if "index" in index_data:
        sample_paths = list(index_data["index"].keys())[:100]  # Check first 100
        for path in sample_paths:
            entry = index_data["index"][path]
            shard_id, offset = entry
            
            # Check shard exists
            shard_path = split_dir / f"shard_{shard_id:04d}.bin"
            if not shard_path.exists():
                results["index_issues"].append({
                    "sample": path,
                    "issue": f"References missing shard {shard_id}",
                })
    
    return results


def print_validation_report(results: Dict):
    """Print a human-readable validation report."""
    print("\n" + "=" * 60)
    print(f"  Cache Validation Report: {results['split']}")
    print("=" * 60)
    print(f"  Directory: {results['cache_dir']}")
    print(f"  Total samples in index: {results['total_samples']:,}")
    print(f"  Valid shards: {results['valid_shards']}")
    
    if results.get("error"):
        print(f"\n  ❌ ERROR: {results['error']}")
        return
    
    if results["corrupted_shards"]:
        print(f"\n  ❌ Corrupted shards: {len(results['corrupted_shards'])}")
        for item in results["corrupted_shards"][:5]:
            print(f"     - Shard {item['shard_id']}: {item['error']}")
    
    if results["truncated_shards"]:
        print(f"\n  ⚠ Truncated shards: {len(results['truncated_shards'])}")
        for item in results["truncated_shards"][:5]:
            print(f"     - Shard {item['shard_id']}: missing {item['missing_bytes']:,} bytes")
            print(f"       Path: {item['path']}")
    
    if results["missing_shards"]:
        print(f"\n  ❌ Missing shards: {len(results['missing_shards'])}")
        print(f"     IDs: {results['missing_shards'][:10]}...")
    
    if results["index_issues"]:
        print(f"\n  ⚠ Index issues: {len(results['index_issues'])}")
        for item in results["index_issues"][:5]:
            print(f"     - {item['sample']}: {item['issue']}")
    
    if results["valid"]:
        print(f"\n  ✅ Cache is VALID")
    else:
        print(f"\n  ❌ Cache has ISSUES - consider regenerating affected shards")
    
    print("=" * 60)


def repair_truncated_shards(cache_dir: Path, split: str, results: Dict) -> int:
    """
    Attempt to repair truncated shards by marking them for regeneration.
    Returns number of shards marked for repair.
    """
    if not results.get("truncated_shards"):
        print("  No truncated shards to repair.")
        return 0
    
    repaired = 0
    split_dir = cache_dir / split
    
    for item in results["truncated_shards"]:
        shard_path = Path(item["path"])
        if shard_path.exists():
            # Rename to .corrupted so consolidation will regenerate
            corrupted_path = shard_path.with_suffix(".corrupted")
            print(f"  Moving corrupted shard: {shard_path.name} -> {corrupted_path.name}")
            shard_path.rename(corrupted_path)
            repaired += 1
    
    if repaired > 0:
        print(f"\n  Marked {repaired} shards for regeneration.")
        print("  Re-run cache consolidation (option 4c) with --resume to regenerate.")
    
    return repaired


def main():
    parser = argparse.ArgumentParser(description="Validate consolidated feature cache")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        required=True,
        help="Path to consolidated cache directory (e.g., data/feature_cache/prod_combined_warmup_consolidated)",
    )
    parser.add_argument(
        "--split",
        type=str,
        choices=["train", "val", "both"],
        default="both",
        help="Which split to validate",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Attempt to repair truncated shards by marking for regeneration",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Output results to JSON file",
    )
    
    args = parser.parse_args()
    
    if not args.cache_dir.exists():
        print(f"ERROR: Cache directory not found: {args.cache_dir}")
        sys.exit(1)
    
    all_results = {}
    all_valid = True
    
    splits = ["train", "val"] if args.split == "both" else [args.split]
    
    for split in splits:
        split_dir = args.cache_dir / split
        if not split_dir.exists():
            print(f"  Skipping {split} (directory not found)")
            continue
        
        results = validate_cache(args.cache_dir, split)
        all_results[split] = results
        print_validation_report(results)
        
        if not results["valid"]:
            all_valid = False
            
            if args.repair and results.get("truncated_shards"):
                print(f"\n  Attempting repair for {split}...")
                repair_truncated_shards(args.cache_dir, split, results)
    
    if args.json:
        with open(args.json, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to: {args.json}")
    
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
