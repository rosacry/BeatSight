#!/usr/bin/env python3
"""Precompute drum feature cache for faster training runs.

This utility iterates through the dataset splits and materialises the
spectrogram tensors on disk using the same caching logic as
``train_classifier.py``. Run it once before long training jobs to avoid
on-the-fly feature extraction overhead.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, Optional
import warnings

import torch
from tqdm import tqdm


warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="You are using `torch.load` with `weights_only=False`",
)

# Reuse the dataset implementation from the training script.
from training.train_classifier import DrumSampleDataset  # type: ignore


def _build_dataset(
    root: Path,
    split: str,
    *,
    cache_dir: Optional[Path],
    sample_rate: int,
    n_fft: int,
    hop_length: int,
    n_mels: int,
    fmax: Optional[int],
    target_frames: int,
    prefer_torchaudio: bool,
    cache_dtype: str,
) -> DrumSampleDataset:
    split_root = root / split
    if not split_root.exists():
        raise FileNotFoundError(f"Split '{split}' not found under {root}")

    labels_file = split_root / f"{split}_labels.json"
    if not labels_file.exists():
        # Support global labels (e.g. train_labels.json at root)
        labels_file = root / f"{split}_labels.json"
        if not labels_file.exists():
            raise FileNotFoundError(
                f"Unable to locate labels for split '{split}'. Tried {split_root / (split + '_labels.json')}"
                f" and {labels_file}."
            )

    dataset = DrumSampleDataset(
        split_root,
        labels_file,
        sr=sample_rate,
        cache_dir=cache_dir,
        prefer_torchaudio=prefer_torchaudio,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
        fmax=fmax,
        target_frames=target_frames,
        cache_dtype=cache_dtype,
    )
    return dataset


def _iter_dataloader(dataset: DrumSampleDataset, batch_size: int, num_workers: int, persistent: bool) -> Iterable:
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=False,
        drop_last=False,
        persistent_workers=persistent and num_workers > 0,
    )
    return loader


def _precompute_split(dataset: DrumSampleDataset, *, batch_size: int, num_workers: int, persistent: bool) -> None:
    loader = _iter_dataloader(dataset, batch_size, num_workers, persistent)
    total = len(dataset)
    with torch.no_grad():
        with tqdm(total=total, desc=f"Caching {dataset.data_dir.name}") as progress:
            for features, _ in loader:
                # Touch the tensor to ensure it is realised. The dataset has
                # already written the cache files during __getitem__.
                _ = features.sum().item()  # noqa: F841 - side-effect only
                progress.update(features.size(0))


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute spectrogram cache for drum datasets")
    parser.add_argument("--dataset", required=True, type=Path, help="Path to dataset root (contains split folders)")
    parser.add_argument(
        "--splits",
        nargs="*",
        default=("train", "val"),
        help="Dataset splits to process (default: train val)",
    )
    parser.add_argument("--cache-dir", type=Path, required=True, help="Destination root for cached tensors")
    parser.add_argument("--sample-rate", type=int, default=44100, help="Audio sample rate (default: 44100)")
    parser.add_argument("--n-fft", type=int, default=2048, help="FFT window size (default: 2048)")
    parser.add_argument("--hop-length", type=int, default=512, help="Hop length (default: 512)")
    parser.add_argument("--n-mels", type=int, default=128, help="Number of mel bins (default: 128)")
    parser.add_argument("--fmax", type=int, default=8000, help="Maximum mel frequency (Hz, <=0 disables)")
    parser.add_argument("--target-frames", type=int, default=128, help="Frame count after resize (default: 128)")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size for caching (default: 128)")
    parser.add_argument("--num-workers", type=int, default=os.cpu_count() or 1, help="DataLoader workers")
    parser.add_argument(
        "--persistent-workers",
        action="store_true",
        help="Reuse DataLoader workers across batches",
    )
    parser.add_argument(
        "--no-torchaudio",
        action="store_true",
        help="Force librosa feature extraction instead of torchaudio",
    )
    parser.add_argument(
        "--cache-dtype",
        choices=["float32", "float16", "bfloat16"],
        default="float32",
        help="Data type for cached tensors (float16 cuts disk usage roughly in half)",
    )

    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.num_workers < 0:
        parser.error("--num-workers must be non-negative")

    dataset_root = args.dataset.resolve()
    cache_root = args.cache_dir.resolve()
    cache_root.mkdir(parents=True, exist_ok=True)

    fmax = None if args.fmax is not None and args.fmax <= 0 else args.fmax

    for split in args.splits:
        split_cache = cache_root / split
        split_cache.mkdir(parents=True, exist_ok=True)
        dataset = _build_dataset(
            dataset_root,
            split,
            cache_dir=split_cache,
            sample_rate=args.sample_rate,
            n_fft=args.n_fft,
            hop_length=args.hop_length,
            n_mels=args.n_mels,
            fmax=fmax,
            target_frames=args.target_frames,
            prefer_torchaudio=not args.no_torchaudio,
            cache_dtype=args.cache_dtype,
        )
        _precompute_split(
            dataset,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            persistent=args.persistent_workers,
        )

    print("Cache precomputation complete. Saved tensors under", cache_root)


if __name__ == "__main__":
    main()
