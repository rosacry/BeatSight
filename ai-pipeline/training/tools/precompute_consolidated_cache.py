#!/usr/bin/env python3
"""FAST precompute feature cache directly to consolidated shards.

This is the FASTEST approach - writes directly to memory-mapped shard files
instead of 15M individual .pt files. Eliminates NTFS file overhead entirely.

Performance comparison (15M samples on NVMe):
- Individual .pt files: ~16 hours (250 it/s, syscall bound)
- Consolidated shards:  ~2-3 hours (2000+ it/s, I/O throughput bound)

Usage:
    PYTHONPATH=. python training/tools/precompute_consolidated_cache.py \
        --dataset C:/temp_dataset/prod_v5_fixed_20251212 \
        --cache-dir C:/temp_dataset/feature_cache_v5 \
        --cache-dtype float16 \
        --num-workers 8
"""

from __future__ import annotations

import argparse
import json
import mmap
import os
import struct
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.utils.data
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

warnings.filterwarnings("ignore", category=FutureWarning)

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

# Constants for shard format (compatible with ConsolidatedCacheReader)
MAGIC_BYTES = b"BSFC"
VERSION = 2
SAMPLES_PER_SHARD = 65536  # 64K samples per shard
HEADER_SIZE = 32

DTYPE_MAP = {
    "float32": (torch.float32, 0, 4),
    "float16": (torch.float16, 1, 2),
    "bfloat16": (torch.bfloat16, 2, 2),
}


class AudioFeatureDataset(Dataset):
    """Dataset that returns (features, relative_path, index) tuples."""
    
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
    ):
        self.data_dir = data_dir
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.fmax = fmax
        self.target_frames = target_frames
        
        dtype_info = DTYPE_MAP.get(cache_dtype, DTYPE_MAP["float16"])
        self.cache_dtype = dtype_info[0]
        
        self._use_torchaudio = prefer_torchaudio and HAS_TORCHAUDIO
        self._mel_transform = None
        self._amplitude_to_db = None
        
        if self._use_torchaudio:
            self._mel_transform = ta_T.MelSpectrogram(
                sample_rate=sr, n_fft=n_fft, hop_length=hop_length,
                win_length=n_fft, n_mels=n_mels, f_max=fmax,
                pad_mode="reflect", power=2.0, center=True, normalized=False,
            )
            self._amplitude_to_db = ta_T.AmplitudeToDB(stype="power")
        
        # Load file paths from numpy
        npy_files = labels_file.parent / f"{labels_file.stem}_files.npy"
        npy_labels = labels_file.parent / f"{labels_file.stem}_labels.npy"
        
        if npy_files.exists() and npy_labels.exists():
            self._files = np.load(npy_files, mmap_mode='r')
            self._labels = np.load(npy_labels, mmap_mode='r')
            self._files_are_bytes = self._files.dtype.kind == 'S'
            print(f"[DATASET] Loaded {len(self._files):,} items from numpy")
        else:
            with open(labels_file) as f:
                data = json.load(f)
            self._files = np.array([item['file'] for item in data], dtype='U256')
            self._labels = np.array([item['component_idx'] for item in data], dtype=np.int32)
            self._files_are_bytes = False
            print(f"[DATASET] Loaded {len(self._files):,} items from JSON")
    
    def __len__(self) -> int:
        return len(self._files)
    
    def _get_path(self, idx: int) -> str:
        f = self._files[idx]
        return f.decode('utf-8') if self._files_are_bytes else str(f)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, str, int]:
        rel_path = self._get_path(idx)
        audio_path = self.data_dir / rel_path
        
        # Load audio
        try:
            if self._use_torchaudio:
                waveform, file_sr = torchaudio.load(audio_path)
                if file_sr != self.sr:
                    waveform = torchaudio.functional.resample(waveform, file_sr, self.sr)
                if waveform.shape[0] > 1:
                    waveform = waveform.mean(dim=0, keepdim=True)
                waveform = waveform.squeeze(0)
            else:
                waveform, _ = librosa.load(audio_path, sr=self.sr, mono=True)
                waveform = torch.from_numpy(waveform)
            
            # Pad short audio (must be at least n_fft for STFT)
            min_length = self.n_fft + self.hop_length
            if waveform.shape[-1] < min_length:
                pad_needed = min_length - waveform.shape[-1]
                waveform = torch.nn.functional.pad(waveform, (0, pad_needed), mode='constant', value=0)
            
            # Compute mel spectrogram
            features = self._extract_features(waveform)
            features = features.to(dtype=self.cache_dtype)
        except Exception as e:
            # Return zeros for corrupt/unreadable files
            print(f"\n[WARN] Failed to process {rel_path}: {e}")
            features = torch.zeros((1, self.n_mels, self.target_frames), dtype=self.cache_dtype)
        
        return features, rel_path, idx
    
    def _extract_features(self, waveform: torch.Tensor) -> torch.Tensor:
        if self._use_torchaudio:
            mel = self._mel_transform(waveform)
            mel_db = self._amplitude_to_db(mel)
        else:
            mel = librosa.feature.melspectrogram(
                y=waveform.numpy(), sr=self.sr, n_fft=self.n_fft,
                hop_length=self.hop_length, n_mels=self.n_mels, fmax=self.fmax,
            )
            mel_db = torch.from_numpy(librosa.power_to_db(mel, ref=np.max))
        
        if mel_db.dim() == 2:
            mel_db = mel_db.unsqueeze(0)
        
        mel_db = torch.nn.functional.interpolate(
            mel_db.unsqueeze(0),
            size=(self.n_mels, self.target_frames),
            mode='bilinear', align_corners=False,
        ).squeeze(0)
        
        return mel_db


def collate_fn(batch):
    features = torch.stack([b[0] for b in batch])
    paths = [b[1] for b in batch]
    indices = [b[2] for b in batch]
    return features, paths, indices


class ConsolidatedShardWriter:
    """Writes features directly to consolidated shard files (no individual .pt files)."""
    
    def __init__(
        self,
        output_dir: Path,
        total_samples: int,
        tensor_shape: Tuple[int, int, int] = (1, 128, 128),
        dtype: str = "float16",
        samples_per_shard: int = SAMPLES_PER_SHARD,
        resume: bool = False,
        existing_index: Optional[Dict[str, Tuple[int, int]]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.total_samples = total_samples
        self.tensor_shape = tensor_shape
        self.samples_per_shard = samples_per_shard
        
        dtype_info = DTYPE_MAP[dtype]
        self.torch_dtype = dtype_info[0]
        self.dtype_code = dtype_info[1]
        self.bytes_per_element = dtype_info[2]
        
        numel = tensor_shape[0] * tensor_shape[1] * tensor_shape[2]
        self.bytes_per_sample = numel * self.bytes_per_element
        
        # Pre-calculate shard info
        self.num_shards = (total_samples + samples_per_shard - 1) // samples_per_shard
        
        # Index: maps relative path -> (shard_id, offset_in_shard)
        self.index: Dict[str, Tuple[int, int]] = existing_index.copy() if existing_index else {}
        
        # Pre-allocate shard files with headers (or reuse existing)
        self._shard_files: Dict[int, Any] = {}
        self._shard_sample_counts: Dict[int, int] = {}
        
        if resume and self._shards_exist():
            print(f"[WRITER] Reusing {self.num_shards} existing shard files...")
            for shard_id in range(self.num_shards):
                self._open_existing_shard(shard_id)
        else:
            print(f"[WRITER] Creating {self.num_shards} shard files...")
            for shard_id in range(self.num_shards):
                samples_in_shard = min(
                    samples_per_shard,
                    total_samples - shard_id * samples_per_shard
                )
                self._create_shard(shard_id, samples_in_shard)
            print(f"[WRITER] Shards created. Total size: {self.num_shards * (HEADER_SIZE + samples_per_shard * self.bytes_per_sample) / 1e9:.1f} GB")
    
    def _shards_exist(self) -> bool:
        """Check if shard files already exist."""
        first_shard = self.output_dir / "shard_0000.bin"
        return first_shard.exists()
    
    def _open_existing_shard(self, shard_id: int) -> None:
        """Open existing shard file for random write access."""
        filename = f"shard_{shard_id:04d}.bin"
        filepath = self.output_dir / filename
        if filepath.exists():
            self._shard_files[shard_id] = open(filepath, "r+b")
        else:
            # Create if missing
            samples_in_shard = min(
                self.samples_per_shard,
                self.total_samples - shard_id * self.samples_per_shard
            )
            self._create_shard(shard_id, samples_in_shard)
    
    def _create_shard(self, shard_id: int, num_samples: int) -> None:
        """Create shard file with header and pre-allocated space."""
        filename = f"shard_{shard_id:04d}.bin"
        filepath = self.output_dir / filename
        
        # Calculate file size
        file_size = HEADER_SIZE + num_samples * self.bytes_per_sample
        
        # Create file with pre-allocated size
        with open(filepath, "wb") as f:
            # Write header
            header = struct.pack(
                "<4sIIIIIII",
                MAGIC_BYTES,
                VERSION,
                num_samples,
                self.tensor_shape[0],
                self.tensor_shape[1],
                self.tensor_shape[2],
                self.dtype_code,
                0,
            )
            f.write(header)
            # Pre-allocate rest of file
            f.seek(file_size - 1)
            f.write(b'\x00')
        
        # Open for random write access
        self._shard_files[shard_id] = open(filepath, "r+b")
        self._shard_sample_counts[shard_id] = 0
    
    def write_sample(self, global_idx: int, rel_path: str, features: torch.Tensor) -> None:
        """Write a sample at its correct position (supports out-of-order writes)."""
        shard_id = global_idx // self.samples_per_shard
        offset_in_shard = global_idx % self.samples_per_shard
        
        # Convert to bytes
        features = features.to(dtype=self.torch_dtype).contiguous()
        raw_bytes = features.numpy().tobytes()
        
        # Seek to correct position and write
        byte_offset = HEADER_SIZE + offset_in_shard * self.bytes_per_sample
        f = self._shard_files[shard_id]
        f.seek(byte_offset)
        f.write(raw_bytes)
        
        # Update index
        # Use .pt suffix for compatibility with ConsolidatedCacheReader path lookup
        cache_key = str(Path(rel_path).with_suffix(".pt"))
        self.index[cache_key] = (shard_id, offset_in_shard)
    
    def save_index_checkpoint(self) -> None:
        """Save index checkpoint for resume capability."""
        index_path = self.output_dir / "index.json"
        with open(index_path, "w") as f:
            json.dump(self.index, f)
    
    def finalize(self) -> None:
        """Close all files and write index + manifest."""
        # Close shard files
        for f in self._shard_files.values():
            f.close()
        
        # Write index.json
        index_path = self.output_dir / "index.json"
        with open(index_path, "w") as f:
            json.dump(self.index, f)
        print(f"[WRITER] Wrote index.json ({len(self.index):,} entries)")
        
        # Write manifest.json
        shards_info = []
        for shard_id in range(self.num_shards):
            samples_in_shard = min(
                self.samples_per_shard,
                self.total_samples - shard_id * self.samples_per_shard
            )
            shards_info.append({
                "shard_id": shard_id,
                "filename": f"shard_{shard_id:04d}.bin",
                "num_samples": samples_in_shard,
            })
        
        manifest = {
            "version": VERSION,
            "total_samples": self.total_samples,
            "tensor_shape": list(self.tensor_shape),
            "dtype": str(self.torch_dtype).split(".")[-1],
            "samples_per_shard": self.samples_per_shard,
            "bytes_per_sample": self.bytes_per_sample,
            "num_shards": self.num_shards,
            "shards": shards_info,
        }
        
        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[WRITER] Wrote manifest.json")


def precompute_consolidated(
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
    num_workers: int = 8,
    batch_size: int = 256,
    prefetch_factor: int = 4,
    resume: bool = True,
) -> int:
    """Generate consolidated cache shards with resume support."""
    
    # Create dataset
    dataset = AudioFeatureDataset(
        data_dir, labels_file,
        sr=sr, n_fft=n_fft, hop_length=hop_length,
        n_mels=n_mels, fmax=fmax, target_frames=target_frames,
        cache_dtype=cache_dtype, prefer_torchaudio=prefer_torchaudio,
    )
    
    total = len(dataset)
    if total == 0:
        print("No samples to process.")
        return 0
    
    # Check for existing partial cache to resume
    manifest_path = cache_dir / "manifest.json"
    index_path = cache_dir / "index.json"
    start_idx = 0
    existing_index: Dict[str, Tuple[int, int]] = {}
    
    if resume and manifest_path.exists() and index_path.exists():
        with open(manifest_path) as f:
            existing_manifest = json.load(f)
        with open(index_path) as f:
            existing_index = json.load(f)
        
        if existing_manifest.get("total_samples") == total:
            # Check how many we already have
            start_idx = len(existing_index)
            if start_idx >= total:
                print(f"Cache already complete with {total:,} samples. Skipping.")
                return 0
            print(f"[RESUME] Found {start_idx:,}/{total:,} cached. Resuming from index {start_idx}...")
    elif resume and manifest_path.exists():
        # Manifest exists but no index - check shard files exist
        with open(manifest_path) as f:
            existing_manifest = json.load(f)
        if existing_manifest.get("total_samples") == total:
            print(f"[RESUME] Shards exist but no index. Will rebuild index while processing...")
    
    # Create writer (will reuse existing shards if they exist)
    tensor_shape = (1, n_mels, target_frames)
    writer = ConsolidatedShardWriter(
        cache_dir,
        total_samples=total,
        tensor_shape=tensor_shape,
        dtype=cache_dtype,
        resume=resume,
        existing_index=existing_index,
    )
    
    # Create subset dataset starting from start_idx
    if start_idx > 0:
        indices_to_process = list(range(start_idx, total))
        subset_dataset = torch.utils.data.Subset(dataset, indices_to_process)
        remaining = len(indices_to_process)
    else:
        subset_dataset = dataset
        remaining = total
    
    # Create dataloader
    loader = DataLoader(
        subset_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=False,
        drop_last=False,
        persistent_workers=num_workers > 0,
        prefetch_factor=prefetch_factor if num_workers > 0 else None,
        collate_fn=collate_fn,
    )
    
    print(f"Processing {remaining:,} samples with {num_workers} workers, batch={batch_size}...")
    
    written = 0
    with tqdm(total=remaining, desc=f"Caching {data_dir.name}", smoothing=0.1, unit="samples", initial=0) as pbar:
        for features_batch, paths_batch, indices_batch in loader:
            for features, rel_path, idx in zip(features_batch, paths_batch, indices_batch):
                writer.write_sample(idx, rel_path, features)
                written += 1
            pbar.update(len(indices_batch))
            
            # Periodic index checkpoint every 100k samples
            if written % 100000 < batch_size:
                writer.save_index_checkpoint()
    
    writer.finalize()
    return written


def main():
    parser = argparse.ArgumentParser(
        description="Precompute feature cache as consolidated shards (FAST)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dataset", required=True, type=Path, help="Dataset root")
    parser.add_argument("--cache-dir", required=True, type=Path, help="Cache output directory")
    parser.add_argument("--splits", nargs="*", default=["train", "val"], help="Splits to process")
    parser.add_argument("--sample-rate", type=int, default=44100)
    parser.add_argument("--n-fft", type=int, default=2048)
    parser.add_argument("--hop-length", type=int, default=512)
    parser.add_argument("--n-mels", type=int, default=128)
    parser.add_argument("--fmax", type=int, default=8000)
    parser.add_argument("--target-frames", type=int, default=128)
    parser.add_argument("--cache-dtype", choices=["float32", "float16", "bfloat16"], default="float16")
    parser.add_argument("--no-torchaudio", action="store_true")
    parser.add_argument("--num-workers", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--prefetch-factor", type=int, default=4)
    parser.add_argument("--no-resume", action="store_true", help="Start fresh, don't resume")
    
    args = parser.parse_args()
    
    dataset_root = args.dataset.resolve()
    cache_root = args.cache_dir.resolve()
    fmax = args.fmax if args.fmax > 0 else None
    
    print(f"Dataset: {dataset_root}")
    print(f"Cache:   {cache_root}")
    print(f"Config:  {args.num_workers} workers, batch={args.batch_size}, dtype={args.cache_dtype}")
    print()
    
    total_written = 0
    for split in args.splits:
        split_dir = dataset_root / split
        if not split_dir.exists():
            print(f"[SKIP] {split}")
            continue
        
        labels_file = split_dir / f"{split}_labels.json"
        if not labels_file.exists():
            labels_file = dataset_root / f"{split}_labels.json"
        if not labels_file.exists():
            print(f"[SKIP] No labels for {split}")
            continue
        
        split_cache = cache_root / split
        
        written = precompute_consolidated(
            split_dir, split_cache, labels_file,
            sr=args.sample_rate, n_fft=args.n_fft, hop_length=args.hop_length,
            n_mels=args.n_mels, fmax=fmax, target_frames=args.target_frames,
            cache_dtype=args.cache_dtype, prefer_torchaudio=not args.no_torchaudio,
            num_workers=args.num_workers, batch_size=args.batch_size,
            prefetch_factor=args.prefetch_factor,
            resume=not args.no_resume,
        )
        total_written += written
        print()
    
    print(f"Done! Total samples cached: {total_written:,}")
    print(f"Cache location: {cache_root}")


if __name__ == "__main__":
    main()
