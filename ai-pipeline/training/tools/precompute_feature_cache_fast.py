#!/usr/bin/env python3
"""FAST precompute drum feature cache with async writes.

This is an optimized version that decouples reading/compute from writing:
- Worker processes: load audio → compute mel spectrogram → return (features, path)
- Main thread: receives batches → queues async writes via ThreadPoolExecutor
- Writer threads: handle torch.save() without blocking the pipeline

This avoids the I/O contention issue where synchronous saves block workers.

Usage:
    PYTHONPATH=. python training/tools/precompute_feature_cache_fast.py \
        --dataset C:/temp_dataset/prod_v5_fixed_20251212 \
        --cache-dir C:/temp_dataset/feature_cache_v5 \
        --cache-dtype float16 \
        --num-workers 4 \
        --write-workers 8
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import queue
import threading
import warnings
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="You are using `torch.load` with `weights_only=False`",
)

# Optional torchaudio for faster mel extraction
try:
    import torchaudio
    from torchaudio import transforms as ta_T
    HAS_TORCHAUDIO = True
except ImportError:
    torchaudio = None
    ta_T = None
    HAS_TORCHAUDIO = False

import librosa


class AudioOnlyDataset(Dataset):
    """Minimal dataset that only returns (features, relative_path) - NO disk writes.
    
    This dataset does the compute-heavy work (load audio, compute mel spectrogram)
    but does NOT write cache files. The caller handles writing asynchronously.
    """
    
    def __init__(
        self,
        data_dir: Path,
        labels_file: Path,
        *,
        sr: int = 44100,
        n_fft: int = 2048,
        hop_length: int = 512,
        n_mels: int = 128,
        fmax: Optional[int] = 8000,
        target_frames: int = 128,
        cache_dtype: str = "float16",
        prefer_torchaudio: bool = True,
        indices: Optional[List[int]] = None,  # Subset of indices to process
    ):
        self.data_dir = data_dir
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.fmax = fmax
        self.target_frames = target_frames
        
        # Cache dtype
        dtype_map = {"float32": torch.float32, "float16": torch.float16, "bfloat16": torch.bfloat16}
        self.cache_dtype = dtype_map.get(cache_dtype, torch.float16)
        
        # Torchaudio transforms (faster than librosa)
        self._use_torchaudio = prefer_torchaudio and HAS_TORCHAUDIO
        self._mel_transform = None
        self._amplitude_to_db = None
        
        if self._use_torchaudio:
            self._mel_transform = ta_T.MelSpectrogram(
                sample_rate=sr,
                n_fft=n_fft,
                hop_length=hop_length,
                win_length=n_fft,
                n_mels=n_mels,
                f_max=fmax,
                pad_mode="reflect",
                power=2.0,
                center=True,
                normalized=False,
            )
            self._amplitude_to_db = ta_T.AmplitudeToDB(stype="power")
        
        # Load labels - support numpy format
        self._files: Optional[np.ndarray] = None
        self._labels: Optional[np.ndarray] = None
        self._file_list: Optional[List[str]] = None
        self._indices = indices
        
        npy_files = labels_file.parent / f"{labels_file.stem}_files.npy"
        npy_labels = labels_file.parent / f"{labels_file.stem}_labels.npy"
        
        if npy_files.exists() and npy_labels.exists():
            print(f"[DATASET] Loading from numpy: {npy_files.parent}")
            self._files = np.load(npy_files, mmap_mode='r')
            self._labels = np.load(npy_labels, mmap_mode='r')
            self._files_are_bytes = self._files.dtype.kind == 'S'
            print(f"[DATASET] Loaded {len(self._files):,} items")
        else:
            # Fallback to JSON
            import json
            print(f"[DATASET] Loading from JSON: {labels_file}")
            with open(labels_file, 'r') as f:
                data = json.load(f)
            self._file_list = [item['file'] for item in data]
            print(f"[DATASET] Loaded {len(self._file_list):,} items")
    
    def __len__(self) -> int:
        if self._indices is not None:
            return len(self._indices)
        if self._files is not None:
            return len(self._files)
        return len(self._file_list) if self._file_list else 0
    
    def _get_file_path(self, idx: int) -> str:
        """Get relative file path for index."""
        if self._indices is not None:
            idx = self._indices[idx]
        
        if self._files is not None:
            file_bytes = self._files[idx]
            if self._files_are_bytes:
                return file_bytes.decode('utf-8')
            return str(file_bytes)
        return self._file_list[idx]
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, str]:
        """Returns (features, relative_path) - caller handles caching."""
        rel_path = self._get_file_path(idx)
        audio_path = self.data_dir / rel_path
        
        # Load audio
        if self._use_torchaudio:
            waveform, file_sr = torchaudio.load(audio_path)
            if file_sr != self.sr:
                waveform = torchaudio.functional.resample(waveform, file_sr, self.sr)
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            waveform = waveform.squeeze(0)  # [samples]
        else:
            waveform, _ = librosa.load(audio_path, sr=self.sr, mono=True)
            waveform = torch.from_numpy(waveform)
        
        # Compute mel spectrogram
        features = self._extract_features(waveform)
        
        # Convert to cache dtype
        features = features.to(dtype=self.cache_dtype)
        
        # Return features and the RELATIVE path (for cache file naming)
        return features, rel_path
    
    def _extract_features(self, waveform: torch.Tensor) -> torch.Tensor:
        """Extract mel spectrogram features."""
        if self._use_torchaudio:
            mel = self._mel_transform(waveform)
            mel_db = self._amplitude_to_db(mel)
        else:
            mel = librosa.feature.melspectrogram(
                y=waveform.numpy(),
                sr=self.sr,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                n_mels=self.n_mels,
                fmax=self.fmax,
            )
            mel_db = librosa.power_to_db(mel, ref=np.max)
            mel_db = torch.from_numpy(mel_db)
        
        # Resize to target frames
        if mel_db.dim() == 2:
            mel_db = mel_db.unsqueeze(0)  # Add channel dim
        
        mel_db = torch.nn.functional.interpolate(
            mel_db.unsqueeze(0),
            size=(self.n_mels, self.target_frames),
            mode='bilinear',
            align_corners=False,
        ).squeeze(0)
        
        return mel_db


def find_uncached_indices(
    data_dir: Path,
    cache_dir: Path, 
    labels_file: Path,
    num_threads: int = 16,
) -> List[int]:
    """Find indices of samples that don't have cache files yet."""
    
    # Load file paths
    npy_files = labels_file.parent / f"{labels_file.stem}_files.npy"
    if npy_files.exists():
        files = np.load(npy_files, mmap_mode='r')
        is_bytes = files.dtype.kind == 'S'
        
        def get_path(idx):
            f = files[idx]
            return f.decode('utf-8') if is_bytes else str(f)
        total = len(files)
    else:
        import json
        with open(labels_file) as f:
            data = json.load(f)
        file_list = [item['file'] for item in data]
        
        def get_path(idx):
            return file_list[idx]
        total = len(file_list)
    
    if total == 0:
        return []
    
    # Quick check: if cache dir is empty, return all indices
    cache_files = list(cache_dir.glob("**/*.pt"))[:1]
    if not cache_files:
        print(f"Cache directory empty. Processing all {total:,} items.")
        return list(range(total))
    
    # Check which files exist in parallel
    def check_cached(idx: int) -> Optional[int]:
        rel_path = get_path(idx)
        cache_path = cache_dir / Path(rel_path).with_suffix(".pt")
        return None if cache_path.exists() else idx
    
    print(f"Checking existing cache for {total:,} items...")
    uncached = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(tqdm(
            executor.map(check_cached, range(total)),
            total=total,
            desc="Scanning cache",
            smoothing=0.1,
        ))
    
    uncached = [idx for idx in results if idx is not None]
    cached = total - len(uncached)
    
    if cached > 0:
        print(f"Found {cached:,} cached items. {len(uncached):,} remaining.")
    else:
        print(f"No cache files found. Processing all {total:,} items.")
    
    return uncached


class AsyncCacheWriter:
    """Async cache writer using a thread pool for non-blocking saves."""
    
    def __init__(self, cache_dir: Path, num_workers: int = 8, queue_size: int = 1000):
        self.cache_dir = cache_dir
        self.queue = queue.Queue(maxsize=queue_size)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=num_workers)
        self.pending_futures: List[concurrent.futures.Future] = []
        self.total_written = 0
        self.lock = threading.Lock()
        self._stop = False
    
    def submit(self, features: torch.Tensor, rel_path: str) -> None:
        """Submit a cache write (non-blocking unless queue is full)."""
        cache_path = self.cache_dir / Path(rel_path).with_suffix(".pt")
        
        # Clone tensor to avoid memory issues with DataLoader
        features_cpu = features.detach().cpu().clone()
        
        future = self.executor.submit(self._write_cache, features_cpu, cache_path)
        
        with self.lock:
            self.pending_futures.append(future)
            # Clean up completed futures periodically
            if len(self.pending_futures) > 500:
                self.pending_futures = [f for f in self.pending_futures if not f.done()]
    
    def _write_cache(self, features: torch.Tensor, cache_path: Path) -> None:
        """Write cache file (runs in thread pool)."""
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(features, cache_path)
            with self.lock:
                self.total_written += 1
        except Exception as e:
            print(f"[WRITE ERROR] {cache_path}: {e}")
    
    def wait_completion(self) -> int:
        """Wait for all pending writes to complete."""
        with self.lock:
            futures = self.pending_futures.copy()
        
        if futures:
            concurrent.futures.wait(futures)
        
        self.executor.shutdown(wait=True)
        return self.total_written


def collate_with_paths(batch: List[Tuple[torch.Tensor, str]]) -> Tuple[torch.Tensor, List[str]]:
    """Custom collate that preserves file paths."""
    features = torch.stack([item[0] for item in batch])
    paths = [item[1] for item in batch]
    return features, paths


def precompute_split_fast(
    data_dir: Path,
    cache_dir: Path,
    labels_file: Path,
    *,
    sr: int = 44100,
    n_fft: int = 2048,
    hop_length: int = 512,
    n_mels: int = 128,
    fmax: Optional[int] = 8000,
    target_frames: int = 128,
    cache_dtype: str = "float16",
    prefer_torchaudio: bool = True,
    num_workers: int = 4,
    write_workers: int = 8,
    batch_size: int = 64,
    prefetch_factor: int = 2,
) -> int:
    """Precompute features with async writes for maximum throughput."""
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Find uncached items
    uncached_indices = find_uncached_indices(data_dir, cache_dir, labels_file)
    
    if not uncached_indices:
        print(f"All items already cached for {data_dir.name}.")
        return 0
    
    # Create dataset with only uncached items
    dataset = AudioOnlyDataset(
        data_dir,
        labels_file,
        sr=sr,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
        fmax=fmax,
        target_frames=target_frames,
        cache_dtype=cache_dtype,
        prefer_torchaudio=prefer_torchaudio,
        indices=uncached_indices,
    )
    
    # Create dataloader - fewer workers since we're decoupling writes
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=False,  # Not needed since we're not using GPU
        drop_last=False,
        persistent_workers=num_workers > 0,
        prefetch_factor=prefetch_factor if num_workers > 0 else None,
        collate_fn=collate_with_paths,
    )
    
    # Create async writer
    writer = AsyncCacheWriter(cache_dir, num_workers=write_workers, queue_size=batch_size * 4)
    
    print(f"Processing {len(uncached_indices):,} items with {num_workers} read workers, {write_workers} write workers...")
    
    # Process batches
    with tqdm(total=len(uncached_indices), desc=f"Caching {data_dir.name}", smoothing=0.1) as pbar:
        for features_batch, paths_batch in loader:
            # Submit each item for async write
            for features, rel_path in zip(features_batch, paths_batch):
                writer.submit(features, rel_path)
            pbar.update(len(paths_batch))
    
    # Wait for all writes to complete
    print("Waiting for write queue to drain...")
    total_written = writer.wait_completion()
    print(f"Wrote {total_written:,} cache files.")
    
    return total_written


def main():
    parser = argparse.ArgumentParser(
        description="FAST precompute feature cache with async writes",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dataset", required=True, type=Path, help="Dataset root (contains train/, val/)")
    parser.add_argument("--cache-dir", required=True, type=Path, help="Cache output directory")
    parser.add_argument("--splits", nargs="*", default=["train", "val"], help="Splits to process")
    parser.add_argument("--sample-rate", type=int, default=44100, help="Audio sample rate")
    parser.add_argument("--n-fft", type=int, default=2048, help="FFT window size")
    parser.add_argument("--hop-length", type=int, default=512, help="Hop length")
    parser.add_argument("--n-mels", type=int, default=128, help="Mel bins")
    parser.add_argument("--fmax", type=int, default=8000, help="Max mel frequency (0 to disable)")
    parser.add_argument("--target-frames", type=int, default=128, help="Target frame count")
    parser.add_argument("--cache-dtype", choices=["float32", "float16", "bfloat16"], default="float16")
    parser.add_argument("--no-torchaudio", action="store_true", help="Use librosa instead of torchaudio")
    parser.add_argument("--num-workers", type=int, default=4, help="DataLoader workers (read/compute)")
    parser.add_argument("--write-workers", type=int, default=8, help="Async write thread pool size")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--prefetch-factor", type=int, default=2, help="Prefetch batches per worker")
    
    args = parser.parse_args()
    
    dataset_root = args.dataset.resolve()
    cache_root = args.cache_dir.resolve()
    fmax = args.fmax if args.fmax > 0 else None
    
    print(f"Dataset: {dataset_root}")
    print(f"Cache:   {cache_root}")
    print(f"Config:  {args.num_workers} read workers, {args.write_workers} write workers, batch={args.batch_size}")
    print()
    
    total_written = 0
    for split in args.splits:
        split_dir = dataset_root / split
        if not split_dir.exists():
            print(f"[SKIP] Split '{split}' not found at {split_dir}")
            continue
        
        labels_file = split_dir / f"{split}_labels.json"
        if not labels_file.exists():
            labels_file = dataset_root / f"{split}_labels.json"
        if not labels_file.exists():
            print(f"[SKIP] Labels not found for '{split}'")
            continue
        
        split_cache = cache_root / split
        
        written = precompute_split_fast(
            split_dir,
            split_cache,
            labels_file,
            sr=args.sample_rate,
            n_fft=args.n_fft,
            hop_length=args.hop_length,
            n_mels=args.n_mels,
            fmax=fmax,
            target_frames=args.target_frames,
            cache_dtype=args.cache_dtype,
            prefer_torchaudio=not args.no_torchaudio,
            num_workers=args.num_workers,
            write_workers=args.write_workers,
            batch_size=args.batch_size,
            prefetch_factor=args.prefetch_factor,
        )
        total_written += written
        print()
    
    print(f"Done! Total cache files written: {total_written:,}")
    print(f"Cache location: {cache_root}")


if __name__ == "__main__":
    main()
