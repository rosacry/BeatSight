#!/usr/bin/env python3
"""Prune feature-cache entries that fall outside the active training subset.

Given the dataset root, cache directory, and the subset selection arguments
(--train-fraction/--val-fraction/--subset-seed) used by ``train_classifier.py``,
this tool identifies cached tensors (.pt files) that the upcoming run will never
touch and optionally removes them. This is helpful when cache directories have
accumulated artifacts from older fractions or dtype conversions and you want to
reclaim disk space without nuking the entire tree.

Usage (dry run by default):
    PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/prune_cache_to_subset.py \
        --dataset C:/Users/10ros/OneDrive/Documents/github/BeatSight/data/prod_combined_profile_run \
        --cache-dir C:/Users/10ros/OneDrive/Documents/github/BeatSight/data/feature_cache/prod_combined_warmup \
        --train-fraction 0.08 \
        --val-fraction 0.12 \
        --subset-seed 20251112

Add ``--apply`` to actually delete the extra files once you are satisfied with
the report. Empty directories will be cleaned up automatically when ``--apply``
flag is present.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Set

from training.train_classifier import stratified_sample_indices  # type: ignore


def resolve_labels(dataset_root: Path, split: str, filename: str) -> Path:
    direct = dataset_root / filename
    if direct.exists():
        return direct
    nested = dataset_root / split / filename
    if nested.exists():
        return nested
    raise FileNotFoundError(
        f"Missing label file for split '{split}'. Tried '{direct}' and '{nested}'."
    )


def load_labels(path: Path) -> List[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}, got {type(data).__name__}")
    return data


def iter_cache_files(split_root: Path) -> Iterable[Path]:
    if not split_root.exists():
        return []
    for path in split_root.rglob("*.pt"):
        if path.is_file():
            yield path


def expected_cache_paths(
    dataset_root: Path,
    split: str,
    *,
    fraction: float,
    subset_seed: int,
) -> Set[Path]:
    labels_path = resolve_labels(dataset_root, split, f"{split}_labels.json")
    labels = load_labels(labels_path)
    if not (0.0 < fraction <= 1.0):
        raise ValueError(f"{split} fraction must be in the range (0, 1], got {fraction}")

    if fraction >= 0.999999:
        indices = range(len(labels))
    else:
        indices = stratified_sample_indices(labels, fraction, subset_seed)

    expected: Set[Path] = set()
    for idx in indices:
        entry = labels[idx]
        value = entry.get("file", "")
        if not isinstance(value, str) or not value:
            continue
        relative = Path(value).with_suffix(".pt")
        expected.add(relative)
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description="Prune cached tensors outside the selected subset")
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset root (containing train/val splits)")
    parser.add_argument("--cache-dir", type=Path, required=True, help="Root directory where cache files live")
    parser.add_argument("--train-fraction", type=float, default=1.0, help="Training fraction passed to train_classifier.py")
    parser.add_argument("--val-fraction", type=float, default=1.0, help="Validation fraction passed to train_classifier.py")
    parser.add_argument("--subset-seed", type=int, default=42, help="Subset seed used for stratified sampling")
    parser.add_argument("--splits", nargs="*", choices=["train", "val"], default=["train", "val"], help="Which splits to inspect")
    parser.add_argument("--apply", action="store_true", help="Delete files instead of just reporting")

    args = parser.parse_args()

    dataset_root = args.dataset.expanduser().resolve()
    cache_root = args.cache_dir.expanduser().resolve()

    if not dataset_root.exists():
        raise SystemExit(f"Dataset root not found: {dataset_root}")
    if not cache_root.exists():
        raise SystemExit(f"Cache root not found: {cache_root}")

    total_files = 0
    kept_files = 0
    removed_files = 0
    removed_bytes = 0

    for split in args.splits:
        split_cache = cache_root / split
        if not split_cache.exists():
            print(f"[{split}] cache directory missing → skipping")
            continue

        fraction = args.train_fraction if split == "train" else args.val_fraction
        expected = expected_cache_paths(dataset_root, split, fraction=fraction, subset_seed=args.subset_seed)
        expected_count = len(expected)

        print(f"[{split}] expecting {expected_count} cached clips for fraction {fraction:.4f}")

        for cache_path in iter_cache_files(split_cache):
            total_files += 1
            relative = cache_path.relative_to(split_cache)
            if relative in expected:
                kept_files += 1
                continue

            removed_files += 1
            if args.apply:
                size = cache_path.stat().st_size
                removed_bytes += size
                cache_path.unlink()
            else:
                removed_bytes += cache_path.stat().st_size

        if args.apply:
            # Remove any now-empty directories for tidiness
            for directory in sorted({p.parent for p in iter_cache_files(split_cache)}, reverse=True):
                if directory.exists() and not any(directory.iterdir()):
                    try:
                        directory.rmdir()
                    except OSError:
                        pass

    print()
    print(f"Total cache files inspected: {total_files}")
    print(f"Kept (within subset): {kept_files}")
    print(f"Candidates for removal: {removed_files}")
    if removed_files:
        size_gb = removed_bytes / (1024 ** 3)
        action = "Deleted" if args.apply else "Would delete"
        print(f"{action}: {removed_files} files totaling {size_gb:.2f} GB")
    else:
        print("No extra files detected; cache aligns with requested subset.")


if __name__ == "__main__":
    main()
