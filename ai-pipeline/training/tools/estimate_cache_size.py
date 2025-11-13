#!/usr/bin/env python3
"""Estimate feature-cache storage requirements for a given dataset subset.

This mirrors the subset-selection logic in ``train_classifier.py`` so you can
get a realistic storage projection before filling the cache. Optionally point
at an existing cache directory to subtract files that already exist on disk.

Usage example:
    PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/estimate_cache_size.py \
        --dataset /home/chrig/prod_combined_profile_run \
        --train-fraction 0.08 \
        --val-fraction 0.30 \
        --subset-seed 20251112 \
        --cache-dir /home/chrig/feature_cache/prod_combined_warmup
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Dict, List

# Ensure imports resolve when the script is launched via ``PYTHONPATH=ai-pipeline``
from training.train_classifier import stratified_sample_indices  # type: ignore


def resolve_labels(dataset_root: Path, split: str, filename: str) -> Path:
    """Locate the label JSON file for the requested split."""

    direct = dataset_root / filename
    if direct.exists():
        return direct
    nested = dataset_root / split / filename
    if nested.exists():
        return nested
    raise FileNotFoundError(
        f"Missing label file for {split}: looked for '{direct}' and '{nested}'"
    )


def load_labels(path: Path) -> List[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Label file {path} did not contain a list of entries")
    return data


def bytes_per_sample(n_mels: int, target_frames: int, cache_dtype: str, metadata_overhead: int) -> int:
    dtype_bytes = {
        "float16": 2,
        "bfloat16": 2,
        "float32": 4,
    }
    if cache_dtype not in dtype_bytes:
        raise ValueError(f"Unsupported cache dtype '{cache_dtype}'")

    tensor_bytes = n_mels * target_frames * dtype_bytes[cache_dtype]
    return tensor_bytes + metadata_overhead


def format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    units = ["KB", "MB", "GB", "TB", "PB"]
    scaled = float(value)
    for unit in units:
        scaled /= 1024.0
        if scaled < 1024.0:
            return f"{scaled:.2f} {unit}"
    return f"{scaled:.2f} EB"


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate feature cache footprint for drum classifier subsets")
    parser.add_argument("--dataset", type=Path, required=True, help="Root of the exported dataset (with train/val subfolders)")
    parser.add_argument("--train-fraction", type=float, default=1.0, help="Training subset fraction (same as train_classifier.py)")
    parser.add_argument("--val-fraction", type=float, default=1.0, help="Validation subset fraction (same as train_classifier.py)")
    parser.add_argument("--subset-seed", type=int, default=42, help="Seed used for stratified sampling")
    parser.add_argument("--cache-dtype", choices=["float16", "bfloat16", "float32"], default="float16", help="Cache tensor dtype")
    parser.add_argument("--n-mels", type=int, default=128, help="Number of mel bins (matches --n-mels)")
    parser.add_argument("--target-frames", type=int, default=128, help="Spectrogram frames after resizing (matches --target-frames)")
    parser.add_argument("--metadata-overhead", type=int, default=2048, help="Estimated bytes per file for Torch metadata")
    parser.add_argument("--include-splits", nargs="*", choices=["train", "val"], default=["train", "val"], help="Which splits to include in the estimate")
    parser.add_argument("--cache-dir", type=Path, help="Optional existing cache directory to discount already-cached samples")

    args = parser.parse_args()

    dataset_root = args.dataset.expanduser().resolve()
    if not dataset_root.exists():
        raise SystemExit(f"Dataset root '{dataset_root}' does not exist")

    per_sample_bytes = bytes_per_sample(
        n_mels=args.n_mels,
        target_frames=args.target_frames,
        cache_dtype=args.cache_dtype,
        metadata_overhead=args.metadata_overhead,
    )

    results = []
    total_bytes = 0

    cache_root: Path | None = None
    if args.cache_dir is not None:
        cache_root = args.cache_dir.expanduser().resolve()
        if not cache_root.exists():
            raise SystemExit(f"Provided cache directory '{cache_root}' does not exist")

    total_existing_bytes = 0

    for split in args.include_splits:
        labels_path = resolve_labels(dataset_root, split, f"{split}_labels.json")
        labels = load_labels(labels_path)
        original_count = len(labels)
        fraction = args.train_fraction if split == "train" else args.val_fraction
        if not (0.0 < fraction <= 1.0):
            raise SystemExit(f"{split} fraction must be in the range (0, 1], got {fraction}")

        if math.isclose(fraction, 1.0, rel_tol=1e-6):
            subset_indices = list(range(original_count))
        else:
            subset_indices = stratified_sample_indices(labels, fraction, args.subset_seed)
        subset_count = len(subset_indices)

        existing_count = 0
        if cache_root is not None:
            split_cache_root = cache_root / split
            if split_cache_root.exists():
                for idx in subset_indices:
                    info = labels[idx]
                    file_value = info.get("file", "")
                    if not isinstance(file_value, str) or not file_value:
                        continue
                    relative = Path(file_value)
                    cache_path = split_cache_root / relative.with_suffix(".pt")
                    if cache_path.exists():
                        existing_count += 1

        split_bytes = subset_count * per_sample_bytes
        existing_bytes = existing_count * per_sample_bytes
        missing_bytes = split_bytes - existing_bytes

        total_bytes += missing_bytes if cache_root is not None else split_bytes
        total_existing_bytes += existing_bytes
        results.append(
            {
                "split": split,
                "fraction": fraction,
                "total_clips": original_count,
                "subset_clips": subset_count,
                "bytes_total": split_bytes,
                "cached_clips": existing_count,
                "cached_bytes": existing_bytes,
                "missing_clips": subset_count - existing_count,
                "missing_bytes": missing_bytes,
            }
        )

    print("Dataset:", dataset_root)
    print(f"Cache dtype: {args.cache_dtype} | tensor shape: (1, {args.n_mels}, {args.target_frames})")
    print(f"Estimated bytes per cached sample: {per_sample_bytes} ({format_bytes(per_sample_bytes)})")
    print()
    for entry in results:
        pct = 100.0 * entry["subset_clips"] / max(entry["total_clips"], 1)
        print(f"[{entry['split']}] subset {entry['subset_clips']} / {entry['total_clips']} clips ({pct:.2f}% of split)")
        print(
            "    Estimated cache size:"
            f" {format_bytes(entry['bytes_total'])} ({entry['bytes_total']:,} bytes)"
        )
        if cache_root is not None:
            cached_pct = 100.0 * entry["cached_clips"] / max(entry["subset_clips"], 1)
            print(
                f"    Already cached: {entry['cached_clips']} clips ({cached_pct:.2f}%)"
                f" → {format_bytes(entry['cached_bytes'])}"
            )
            print(
                f"    Missing cache: {entry['missing_clips']} clips"
                f" → {format_bytes(entry['missing_bytes'])} ({entry['missing_bytes']:,} bytes)"
            )
    print()
    if cache_root is not None:
        print(
            f"New cache required: {format_bytes(total_bytes)} ({total_bytes:,} bytes)"
            f" | Already cached: {format_bytes(total_existing_bytes)}"
        )
    else:
        print(f"Total estimated cache size: {format_bytes(total_bytes)} ({total_bytes:,} bytes)")


if __name__ == "__main__":
    main()
