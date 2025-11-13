#!/usr/bin/env python3
"""Convert cached spectrogram tensors to a target dtype in-place.

This utility walks an existing feature cache tree produced by
``train_classifier.py`` / ``precompute_feature_cache.py`` and rewrites
``.pt`` tensors using a lower precision dtype (e.g. float16) to reduce
storage requirements. Tensors are converted on CPU and files are
rewritten atomically via temporary files to avoid corruption if the
process is interrupted.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

import torch
from tqdm import tqdm


def iter_tensor_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.pt"):
        if path.is_file():
            yield path


def convert_tensor_file(path: Path, dtype: torch.dtype, *, dry_run: bool = False) -> bool:
    tensor = torch.load(path, map_location="cpu")
    if not isinstance(tensor, torch.Tensor):
        return False
    if tensor.dtype == dtype:
        return False

    converted = tensor.to(dtype=dtype)
    if dry_run:
        return True

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    torch.save(converted, tmp_path)
    os.replace(tmp_path, path)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert cached spectrogram tensors to a target dtype")
    parser.add_argument("cache_root", type=Path, help="Root directory of cached tensors")
    parser.add_argument(
        "--dtype",
        choices=["float32", "float16", "bfloat16"],
        default="float16",
        help="Target dtype for cached tensors (default: float16)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report convertible files without rewriting",
    )

    args = parser.parse_args()

    dtype_map = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }
    target_dtype = dtype_map[args.dtype]

    root = args.cache_root.resolve()
    if not root.exists():
        raise SystemExit(f"Cache root not found: {root}")

    converted = 0
    skipped = 0
    processed = 0

    for tensor_path in tqdm(iter_tensor_files(root), desc="Converting cache"):
        processed += 1
        try:
            changed = convert_tensor_file(tensor_path, target_dtype, dry_run=args.dry_run)
        except Exception as exc:  # pylint: disable=broad-except
            skipped += 1
            print(f"[WARN] Failed to convert {tensor_path}: {exc}")
            continue
        if changed:
            converted += 1

    print(f"Processed {processed} files")
    if args.dry_run:
        print(f"Convertible: {converted}, skipped: {skipped}")
    else:
        print(f"Converted: {converted}, skipped: {skipped}")


if __name__ == "__main__":
    main()
