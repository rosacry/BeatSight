"""
Consolidated Memory-Mapped Feature Cache for BeatSight

Revolutionary caching system that eliminates I/O bottlenecks by:
1. Consolidating 16M individual .pt files into ~256 large shard files
2. Memory-mapping shards for zero-copy tensor access
3. Maintaining an index for O(1) sample lookups (no filesystem stat calls)

Performance characteristics:
- Individual .pt files: ~3-5 it/s (syscall overhead dominates)
- Consolidated shards: ~100-200 it/s (NVMe throughput utilized)
- Memory-mapped: ~500+ it/s (cached in RAM, zero-copy)

Usage:
    # Convert existing cache (one-time, ~30 min for 16M samples)
    python -m training.utils.consolidated_cache convert \
        --input-dir data/feature_cache/prod_combined_warmup \
        --output-dir data/feature_cache_consolidated

    # Use in training (automatic if consolidated cache exists)
    # The DrumSampleDataset will auto-detect and use consolidated cache

Author: BeatSight Team
License: MIT
"""

from __future__ import annotations

import json
import mmap
import os
import struct
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

import numpy as np
import torch

# Safe print for Windows console encoding issues
try:
    from training.utils.safe_print import safe_print
except ImportError:
    safe_print = print  # Fallback


# =============================================================================
# Constants
# =============================================================================

MAGIC_BYTES = b"BSFC"  # BeatSight Feature Cache
VERSION = 2
SAMPLES_PER_SHARD = 65536  # 64K samples per shard (~2GB each at 34KB/sample)
INDEX_FILENAME = "index.json"
MANIFEST_FILENAME = "manifest.json"

# Header format for each shard:
# - 4 bytes: magic (BSFC)
# - 4 bytes: version (uint32)
# - 4 bytes: num_samples in this shard (uint32)
# - 4 bytes: tensor shape[0] (uint32) - channels
# - 4 bytes: tensor shape[1] (uint32) - height (n_mels)
# - 4 bytes: tensor shape[2] (uint32) - width (frames)
# - 4 bytes: dtype (uint32) - 0=float32, 1=float16, 2=bfloat16
# - 4 bytes: reserved
HEADER_SIZE = 32

DTYPE_MAP = {
    0: torch.float32,
    1: torch.float16,
    2: torch.bfloat16,
}
DTYPE_REVERSE = {v: k for k, v in DTYPE_MAP.items()}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ShardInfo:
    """Metadata for a single shard file."""
    shard_id: int
    filename: str
    num_samples: int
    tensor_shape: Tuple[int, int, int]
    dtype: torch.dtype
    bytes_per_sample: int
    
    @property
    def data_size(self) -> int:
        return self.num_samples * self.bytes_per_sample


@dataclass
class SampleLocation:
    """Location of a sample within the consolidated cache."""
    shard_id: int
    offset_in_shard: int  # Sample index within the shard (not byte offset)


# =============================================================================
# Consolidated Cache Writer
# =============================================================================

class ConsolidatedCacheWriter:
    """
    Writes individual .pt feature files into consolidated shard files.
    
    Creates:
    - shard_XXXX.bin: Binary shard files with header + raw tensor data
    - index.json: Maps original file paths to (shard_id, offset) pairs
    - manifest.json: Metadata about the cache (version, shape, dtype, etc.)
    """
    
    def __init__(
        self,
        output_dir: Path,
        tensor_shape: Tuple[int, int, int] = (1, 128, 128),
        dtype: torch.dtype = torch.float32,
        samples_per_shard: int = SAMPLES_PER_SHARD,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.tensor_shape = tensor_shape
        self.dtype = dtype
        self.samples_per_shard = samples_per_shard
        
        # Calculate bytes per sample
        numel = tensor_shape[0] * tensor_shape[1] * tensor_shape[2]
        if dtype == torch.float32:
            self.bytes_per_sample = numel * 4
        elif dtype == torch.float16:
            self.bytes_per_sample = numel * 2
        elif dtype == torch.bfloat16:
            self.bytes_per_sample = numel * 2
        else:
            raise ValueError(f"Unsupported dtype: {dtype}")
        
        # State
        self.current_shard_id = 0
        self.current_shard_samples = 0
        self.current_shard_file: Optional[Any] = None
        self.index: Dict[str, Tuple[int, int]] = {}  # path -> (shard_id, offset)
        self.shard_infos: List[ShardInfo] = []
        self.total_samples = 0
    
    def _open_new_shard(self) -> None:
        """Open a new shard file for writing."""
        if self.current_shard_file is not None:
            self._close_current_shard()
        
        filename = f"shard_{self.current_shard_id:04d}.bin"
        filepath = self.output_dir / filename
        self.current_shard_file = open(filepath, "wb")
        self.current_shard_samples = 0
        
        # Write placeholder header (will be updated when shard is closed)
        self._write_header(0)
    
    def _write_header(self, num_samples: int) -> None:
        """Write shard header."""
        if self.current_shard_file is None:
            return
        
        dtype_code = DTYPE_REVERSE.get(self.dtype, 0)
        header = struct.pack(
            "<4sIIIIIII",
            MAGIC_BYTES,
            VERSION,
            num_samples,
            self.tensor_shape[0],  # channels
            self.tensor_shape[1],  # height
            self.tensor_shape[2],  # width
            dtype_code,
            0,  # reserved
        )
        
        # Seek to beginning and write
        self.current_shard_file.seek(0)
        self.current_shard_file.write(header)
    
    def _close_current_shard(self) -> None:
        """Close current shard and update header."""
        if self.current_shard_file is None:
            return
        
        # Update header with actual sample count
        self._write_header(self.current_shard_samples)
        
        # Record shard info
        filename = f"shard_{self.current_shard_id:04d}.bin"
        self.shard_infos.append(ShardInfo(
            shard_id=self.current_shard_id,
            filename=filename,
            num_samples=self.current_shard_samples,
            tensor_shape=self.tensor_shape,
            dtype=self.dtype,
            bytes_per_sample=self.bytes_per_sample,
        ))
        
        self.current_shard_file.close()
        self.current_shard_file = None
        self.current_shard_id += 1
    
    def add_sample(self, relative_path: str, tensor: torch.Tensor) -> None:
        """
        Add a sample to the cache.
        
        Args:
            relative_path: Original relative path (used as key in index)
            tensor: Feature tensor to store
        """
        # Open new shard if needed
        if self.current_shard_file is None or self.current_shard_samples >= self.samples_per_shard:
            self._open_new_shard()
        
        # Validate and convert tensor
        if tensor.shape != self.tensor_shape:
            # Attempt to reshape if compatible
            if tensor.numel() == self.tensor_shape[0] * self.tensor_shape[1] * self.tensor_shape[2]:
                tensor = tensor.view(self.tensor_shape)
            else:
                raise ValueError(
                    f"Tensor shape {tensor.shape} doesn't match expected {self.tensor_shape}"
                )
        
        # Convert to target dtype and get raw bytes
        tensor = tensor.to(dtype=self.dtype).contiguous()
        raw_bytes = tensor.numpy().tobytes()
        
        # Write to shard
        self.current_shard_file.write(raw_bytes)
        
        # Update index
        self.index[relative_path] = (self.current_shard_id, self.current_shard_samples)
        self.current_shard_samples += 1
        self.total_samples += 1
    
    def finalize(self) -> None:
        """Close all files and write index/manifest."""
        self._close_current_shard()
        
        # Write index
        index_path = self.output_dir / INDEX_FILENAME
        with open(index_path, "w") as f:
            json.dump(self.index, f)
        print(f"[CACHE] Wrote index with {len(self.index):,} entries to {index_path}")
        
        # Write manifest
        manifest = {
            "version": VERSION,
            "total_samples": self.total_samples,
            "tensor_shape": list(self.tensor_shape),
            "dtype": str(self.dtype).split(".")[-1],
            "samples_per_shard": self.samples_per_shard,
            "bytes_per_sample": self.bytes_per_sample,
            "num_shards": len(self.shard_infos),
            "shards": [
                {
                    "shard_id": s.shard_id,
                    "filename": s.filename,
                    "num_samples": s.num_samples,
                }
                for s in self.shard_infos
            ],
        }
        manifest_path = self.output_dir / MANIFEST_FILENAME
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[CACHE] Wrote manifest to {manifest_path}")


# =============================================================================
# Consolidated Cache Reader (Memory-Mapped)
# =============================================================================

class ConsolidatedCacheReader:
    """
    Memory-mapped reader for consolidated feature cache.
    
    Provides O(1) sample access with zero-copy tensor loading.
    Shards are memory-mapped on-demand and cached for reuse.
    """
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        
        # Load manifest
        manifest_path = self.cache_dir / MANIFEST_FILENAME
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        
        with open(manifest_path) as f:
            self.manifest = json.load(f)
        
        # Parse manifest
        self.total_samples = self.manifest["total_samples"]
        self.tensor_shape = tuple(self.manifest["tensor_shape"])
        self.dtype = getattr(torch, self.manifest["dtype"])
        self.bytes_per_sample = self.manifest["bytes_per_sample"]
        self.num_shards = self.manifest["num_shards"]
        
        # Build shard info lookup
        self.shard_infos: Dict[int, Dict] = {
            s["shard_id"]: s for s in self.manifest["shards"]
        }
        
        # Compute cumulative sample offsets for global indexing
        self._cumulative_samples = [0]
        for shard in self.manifest["shards"]:
            self._cumulative_samples.append(
                self._cumulative_samples[-1] + shard["num_samples"]
            )
        
        # Load index (maps relative path -> (shard_id, offset))
        index_path = self.cache_dir / INDEX_FILENAME
        if not index_path.exists():
            raise FileNotFoundError(f"Index not found: {index_path}")
        
        with open(index_path) as f:
            self.index: Dict[str, List[int]] = json.load(f)
        
        # Memory-mapped shard cache (will be re-created in each worker process)
        self._mmap_cache: Dict[int, Tuple[mmap.mmap, Any]] = {}
        
        # Numpy dtype for reading
        if self.dtype == torch.float32:
            self._np_dtype = np.float32
        elif self.dtype == torch.float16:
            self._np_dtype = np.float16
        else:
            # bfloat16 needs special handling
            self._np_dtype = np.uint16
    
    def _get_mmap(self, shard_id: int) -> mmap.mmap:
        """Get or create memory-mapped shard."""
        if shard_id not in self._mmap_cache:
            shard_info = self.shard_infos[shard_id]
            filepath = self.cache_dir / shard_info["filename"]
            
            f = open(filepath, "rb")
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            self._mmap_cache[shard_id] = (mm, f)
        
        return self._mmap_cache[shard_id][0]
    
    def get_by_path(self, relative_path: str) -> Optional[torch.Tensor]:
        """
        Get a sample by its original relative path.
        
        Args:
            relative_path: Original path used when building the cache
        
        Returns:
            Feature tensor, or None if not found
        """
        location = self.index.get(relative_path)
        if location is None:
            return None
        
        shard_id, offset = location
        return self._read_sample(shard_id, offset)
    
    def get_by_index(self, global_index: int) -> torch.Tensor:
        """
        Get a sample by global index.
        
        Args:
            global_index: Index in range [0, total_samples)
        
        Returns:
            Feature tensor
        """
        # Binary search for shard
        shard_id = 0
        for i, cumsum in enumerate(self._cumulative_samples[1:], 1):
            if global_index < cumsum:
                shard_id = i - 1
                break
        
        offset = global_index - self._cumulative_samples[shard_id]
        return self._read_sample(shard_id, offset)
    
    def _read_sample(self, shard_id: int, offset: int) -> torch.Tensor:
        """Read a single sample from a shard."""
        mm = self._get_mmap(shard_id)
        
        # Calculate byte offset (after header)
        byte_offset = HEADER_SIZE + offset * self.bytes_per_sample
        
        # Read raw bytes
        raw_bytes = mm[byte_offset:byte_offset + self.bytes_per_sample]
        
        # Validate we got the expected number of bytes
        if len(raw_bytes) != self.bytes_per_sample:
            # This can happen if the mmap is corrupted or there's a race condition
            # Return a zero tensor as fallback (better than crashing)
            import warnings
            warnings.warn(
                f"Consolidated cache read error: expected {self.bytes_per_sample} bytes, "
                f"got {len(raw_bytes)} at shard {shard_id} offset {offset}. Using zeros."
            )
            return torch.zeros(self.tensor_shape, dtype=torch.float32)
        
        # Convert to tensor
        arr = np.frombuffer(raw_bytes, dtype=self._np_dtype).copy()
        tensor = torch.from_numpy(arr).view(self.tensor_shape)
        
        # Handle bfloat16
        if self.dtype == torch.bfloat16:
            tensor = tensor.view(torch.bfloat16)
        
        return tensor.to(torch.float32)
    
    def __len__(self) -> int:
        return self.total_samples
    
    def __contains__(self, relative_path: str) -> bool:
        return relative_path in self.index
    
    def close(self) -> None:
        """Close all memory-mapped files."""
        for mm, f in self._mmap_cache.values():
            mm.close()
            f.close()
        self._mmap_cache.clear()
    
    def __del__(self):
        self.close()
    
    def __getstate__(self) -> dict:
        """
        Prepare state for pickling (required for multiprocessing on Windows).
        
        Excludes mmap cache since mmap objects cannot be pickled.
        Each worker process will re-create mmaps on demand.
        """
        state = self.__dict__.copy()
        # Remove unpicklable mmap cache - will be re-created in workers
        state['_mmap_cache'] = {}
        return state
    
    def __setstate__(self, state: dict) -> None:
        """
        Restore state after unpickling.
        
        The mmap cache starts empty and will be populated on first access.
        """
        self.__dict__.update(state)
        # Ensure mmap cache is initialized (should already be empty from __getstate__)
        if '_mmap_cache' not in self.__dict__:
            self._mmap_cache = {}


# =============================================================================
# Conversion Utilities
# =============================================================================

def _process_shard_batch(args: Tuple[List[Path], Path, int, Tuple[int, int, int], torch.dtype, Path]) -> Tuple[int, Dict[str, Tuple[int, int]]]:
    """
    Process a batch of .pt files into a single shard.
    
    Returns:
        (num_samples, index_entries)
    """
    pt_files, output_dir, shard_id, tensor_shape, dtype, split_dir = args
    
    # Calculate bytes per sample
    numel = tensor_shape[0] * tensor_shape[1] * tensor_shape[2]
    if dtype == torch.float32:
        bytes_per_sample = numel * 4
    else:
        bytes_per_sample = numel * 2
    
    shard_path = output_dir / f"shard_{shard_id:04d}.bin"
    index_entries: Dict[str, Tuple[int, int]] = {}
    
    with open(shard_path, "wb") as f:
        # Write header
        dtype_code = DTYPE_REVERSE.get(dtype, 0)
        header = struct.pack(
            "<4sIIIIIII",
            MAGIC_BYTES,
            VERSION,
            len(pt_files),
            tensor_shape[0],
            tensor_shape[1],
            tensor_shape[2],
            dtype_code,
            0,
        )
        f.write(header)
        
        # Write samples
        for offset, pt_file in enumerate(pt_files):
            try:
                tensor = torch.load(pt_file, map_location="cpu", weights_only=True)
                if tensor.shape != tensor_shape:
                    if tensor.numel() == numel:
                        tensor = tensor.view(tensor_shape)
                    else:
                        print(f"[WARN] Shape mismatch for {pt_file}: {tensor.shape} vs {tensor_shape}")
                        # Pad/truncate as needed
                        continue
                
                tensor = tensor.to(dtype=dtype).contiguous()
                f.write(tensor.numpy().tobytes())
                
                # Build relative path for index
                # Structure: split_dir/audio/XX/filename.pt -> audio/XX/filename.pt
                try:
                    relative_path = str(pt_file.relative_to(split_dir))
                except ValueError:
                    # Fallback: use just the filename
                    relative_path = pt_file.name
                index_entries[relative_path] = (shard_id, offset)
                
            except Exception as e:
                print(f"[WARN] Failed to process {pt_file}: {e}")
    
    return len(index_entries), index_entries


def convert_individual_to_consolidated(
    input_dir: Path,
    output_dir: Path,
    split: str = "train",
    tensor_shape: Tuple[int, int, int] = (1, 128, 128),
    dtype: torch.dtype = torch.float32,
    num_workers: int = 8,
    samples_per_shard: int = SAMPLES_PER_SHARD,
) -> None:
    """
    Convert a directory of individual .pt files to consolidated shards.
    
    Args:
        input_dir: Directory containing .pt files (e.g., data/feature_cache/prod_combined_warmup)
        output_dir: Output directory for consolidated cache
        split: Dataset split (train/val)
        tensor_shape: Expected tensor shape
        dtype: Storage dtype
        num_workers: Parallel workers for processing
        samples_per_shard: Samples per shard file
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Split-specific output
    split_output = output_dir / split
    split_output.mkdir(parents=True, exist_ok=True)
    
    print(f"[CACHE] Scanning {input_dir / split} for .pt files...")
    
    # Collect all .pt files
    pt_files = list((input_dir / split).rglob("*.pt"))
    print(f"[CACHE] Found {len(pt_files):,} .pt files")
    
    if not pt_files:
        print("[CACHE] No files found, exiting")
        return
    
    # Group into shard batches
    batches: List[List[Path]] = []
    for i in range(0, len(pt_files), samples_per_shard):
        batches.append(pt_files[i:i + samples_per_shard])
    
    print(f"[CACHE] Processing {len(batches)} shards with {num_workers} workers...")
    
    # The split directory for relative path calculation
    split_dir = input_dir / split
    
    # Process in parallel
    all_index_entries: Dict[str, Tuple[int, int]] = {}
    total_samples = 0
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for shard_id, batch in enumerate(batches):
            args = (batch, split_output, shard_id, tensor_shape, dtype, split_dir)
            futures.append(executor.submit(_process_shard_batch, args))
        
        for i, future in enumerate(as_completed(futures)):
            count, entries = future.result()
            all_index_entries.update(entries)
            total_samples += count
            
            if (i + 1) % 10 == 0 or i == len(futures) - 1:
                print(f"[CACHE] Completed {i + 1}/{len(futures)} shards ({total_samples:,} samples)")
    
    # Write index
    index_path = split_output / INDEX_FILENAME
    with open(index_path, "w") as f:
        json.dump(all_index_entries, f)
    print(f"[CACHE] Wrote index with {len(all_index_entries):,} entries")
    
    # Write manifest
    bytes_per_sample = tensor_shape[0] * tensor_shape[1] * tensor_shape[2]
    if dtype == torch.float32:
        bytes_per_sample *= 4
    else:
        bytes_per_sample *= 2
    
    manifest = {
        "version": VERSION,
        "total_samples": total_samples,
        "tensor_shape": list(tensor_shape),
        "dtype": str(dtype).split(".")[-1],
        "samples_per_shard": samples_per_shard,
        "bytes_per_sample": bytes_per_sample,
        "num_shards": len(batches),
        "shards": [
            {
                "shard_id": i,
                "filename": f"shard_{i:04d}.bin",
                "num_samples": min(samples_per_shard, len(pt_files) - i * samples_per_shard),
            }
            for i in range(len(batches))
        ],
    }
    manifest_path = split_output / MANIFEST_FILENAME
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[CACHE] Wrote manifest to {manifest_path}")
    print(f"[CACHE] Conversion complete: {total_samples:,} samples in {len(batches)} shards")


def _process_shard_batch_inplace(args: Tuple[List[Path], Path, int, Tuple[int, int, int], torch.dtype, Path, bool]) -> Tuple[int, Dict[str, Tuple[int, int]], int]:
    """
    Process a batch of .pt files into a single shard, optionally deleting source files.
    
    Returns:
        (num_samples, index_entries, bytes_freed)
    """
    pt_files, output_dir, shard_id, tensor_shape, dtype, split_dir, delete_source = args
    
    # Calculate bytes per sample
    numel = tensor_shape[0] * tensor_shape[1] * tensor_shape[2]
    if dtype == torch.float32:
        bytes_per_sample = numel * 4
    else:
        bytes_per_sample = numel * 2
    
    shard_path = output_dir / f"shard_{shard_id:04d}.bin"
    index_entries: Dict[str, Tuple[int, int]] = {}
    bytes_freed = 0
    
    with open(shard_path, "wb") as f:
        # Write header
        dtype_code = DTYPE_REVERSE.get(dtype, 0)
        header = struct.pack(
            "<4sIIIIIII",
            MAGIC_BYTES,
            VERSION,
            len(pt_files),
            tensor_shape[0],
            tensor_shape[1],
            tensor_shape[2],
            dtype_code,
            0,
        )
        f.write(header)
        
        # Write samples
        for offset, pt_file in enumerate(pt_files):
            try:
                file_size = pt_file.stat().st_size
                tensor = torch.load(pt_file, map_location="cpu", weights_only=True)
                if tensor.shape != tensor_shape:
                    if tensor.numel() == numel:
                        tensor = tensor.view(tensor_shape)
                    else:
                        print(f"[WARN] Shape mismatch for {pt_file}: {tensor.shape} vs {tensor_shape}")
                        continue
                
                tensor = tensor.to(dtype=dtype).contiguous()
                f.write(tensor.numpy().tobytes())
                
                # Build relative path for index
                try:
                    relative_path = str(pt_file.relative_to(split_dir))
                except ValueError:
                    relative_path = pt_file.name
                index_entries[relative_path] = (shard_id, offset)
                
                # Delete source file immediately after successful processing
                if delete_source:
                    pt_file.unlink()
                    bytes_freed += file_size
                
            except Exception as e:
                print(f"[WARN] Failed to process {pt_file}: {e}")
    
    return len(index_entries), index_entries, bytes_freed


def convert_individual_to_consolidated_inplace(
    input_dir: Path,
    output_dir: Path,
    split: str = "train",
    tensor_shape: Tuple[int, int, int] = (1, 128, 128),
    dtype: torch.dtype = torch.float32,
    num_workers: int = 4,  # Lower default for in-place to reduce I/O contention
    samples_per_shard: int = SAMPLES_PER_SHARD,
    delete_source: bool = True,
    resume: bool = False,
) -> None:
    """
    Convert individual .pt files to consolidated shards, deleting source files as we go.
    
    This minimizes peak storage usage by freeing space after each shard is processed.
    Peak storage overhead is approximately: samples_per_shard * 34KB * num_workers
    With defaults (64K samples, 4 workers): ~8.5GB peak overhead
    
    Args:
        input_dir: Directory containing .pt files
        output_dir: Output directory for consolidated cache
        split: Dataset split (train/val)
        tensor_shape: Expected tensor shape
        dtype: Storage dtype
        num_workers: Parallel workers (lower = less peak storage)
        samples_per_shard: Samples per shard file
        delete_source: Whether to delete source .pt files after processing
        resume: If True, skip shards that already exist and load their index entries
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    split_output = output_dir / split
    split_output.mkdir(parents=True, exist_ok=True)
    
    # Check for existing progress if resuming
    existing_index: Dict[str, Tuple[int, int]] = {}
    existing_shards: set = set()
    if resume:
        index_path = split_output / INDEX_FILENAME
        if index_path.exists():
            print(f"[CACHE] RESUME MODE: Loading existing index...")
            with open(index_path) as f:
                existing_index = json.load(f)
            print(f"[CACHE] Found {len(existing_index):,} already-converted samples")
            
            # Find existing shard files
            for shard_file in split_output.glob("shard_*.bin"):
                try:
                    shard_id = int(shard_file.stem.split("_")[1])
                    existing_shards.add(shard_id)
                except (ValueError, IndexError):
                    pass
            print(f"[CACHE] Found {len(existing_shards)} existing shards")
    
    print(f"[CACHE] Scanning {input_dir / split} for .pt files...")
    
    # Collect all .pt files
    pt_files = list((input_dir / split).rglob("*.pt"))
    total_files = len(pt_files)
    print(f"[CACHE] Found {total_files:,} .pt files remaining")
    
    if not pt_files:
        if existing_index:
            print("[CACHE] No new files to process - all files already converted!")
            safe_print(f"[CACHE] ✅ Resume complete with {len(existing_index):,} samples in {len(existing_shards)} shards")
        else:
            print("[CACHE] No files found, exiting")
        return
    
    # Estimate storage
    avg_file_size = 34 * 1024  # ~34KB per file
    total_size_gb = (total_files * avg_file_size) / (1024**3)
    peak_overhead_gb = (samples_per_shard * avg_file_size * num_workers) / (1024**3)
    
    print(f"[CACHE] Estimated remaining size: {total_size_gb:.1f} GB")
    print(f"[CACHE] Peak storage overhead: ~{peak_overhead_gb:.1f} GB (with {num_workers} workers)")
    if delete_source:
        print(f"[CACHE] IN-PLACE MODE: Source files will be deleted after each shard")
    
    # Group into shard batches
    batches: List[List[Path]] = []
    for i in range(0, len(pt_files), samples_per_shard):
        batches.append(pt_files[i:i + samples_per_shard])
    
    # Calculate shard IDs, accounting for existing shards
    if resume and existing_shards:
        start_shard_id = max(existing_shards) + 1
    else:
        start_shard_id = 0
    
    print(f"[CACHE] Processing {len(batches)} new shards (starting at shard {start_shard_id}) with {num_workers} workers...")
    
    split_dir = input_dir / split
    all_index_entries: Dict[str, Tuple[int, int]] = dict(existing_index)  # Start with existing
    total_samples = len(existing_index)
    total_freed_gb = 0.0
    
    # Process shards - use sequential processing with limited parallelism for in-place
    # to ensure we don't have too many files open at once
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit in smaller chunks to control memory/storage pressure
        chunk_size = num_workers * 2
        for chunk_start in range(0, len(batches), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(batches))
            chunk_batches = batches[chunk_start:chunk_end]
            
            futures = []
            for i, batch in enumerate(chunk_batches):
                shard_id = start_shard_id + chunk_start + i
                args = (batch, split_output, shard_id, tensor_shape, dtype, split_dir, delete_source)
                futures.append(executor.submit(_process_shard_batch_inplace, args))
            
            for future in as_completed(futures):
                count, entries, bytes_freed = future.result()
                all_index_entries.update(entries)
                total_samples += count
                total_freed_gb += bytes_freed / (1024**3)
            
            # Save progress after each chunk (enables safe resume)
            index_path = split_output / INDEX_FILENAME
            with open(index_path, "w") as f:
                json.dump(all_index_entries, f)
            
            progress = chunk_end / len(batches) * 100
            print(f"[CACHE] Progress: {chunk_end}/{len(batches)} shards ({progress:.1f}%) | "
                  f"{total_samples:,} samples | {total_freed_gb:.1f} GB freed")
    
    # Calculate total shards (existing + new)
    total_shards = start_shard_id + len(batches)
    
    # Write final index
    index_path = split_output / INDEX_FILENAME
    with open(index_path, "w") as f:
        json.dump(all_index_entries, f)
    print(f"[CACHE] Wrote index with {len(all_index_entries):,} entries")
    
    # Write manifest - enumerate actual shard files to get correct sample counts
    bytes_per_sample = tensor_shape[0] * tensor_shape[1] * tensor_shape[2]
    if dtype == torch.float32:
        bytes_per_sample *= 4
    else:
        bytes_per_sample *= 2
    
    # Build shard list from actual files
    shard_info = []
    for shard_file in sorted(split_output.glob("shard_*.bin")):
        try:
            shard_id = int(shard_file.stem.split("_")[1])
            # Count samples in this shard from index entries
            samples_in_shard = sum(1 for _, (sid, _) in all_index_entries.items() if sid == shard_id)
            shard_info.append({
                "shard_id": shard_id,
                "filename": shard_file.name,
                "num_samples": samples_in_shard,
            })
        except (ValueError, IndexError):
            pass
    
    manifest = {
        "version": VERSION,
        "total_samples": len(all_index_entries),
        "tensor_shape": list(tensor_shape),
        "dtype": str(dtype).split(".")[-1],
        "samples_per_shard": samples_per_shard,
        "bytes_per_sample": bytes_per_sample,
        "num_shards": len(shard_info),
        "shards": shard_info,
    }
    manifest_path = split_output / MANIFEST_FILENAME
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    safe_print(f"[CACHE] ✅ Conversion complete!")
    print(f"[CACHE]    Samples: {len(all_index_entries):,}")
    print(f"[CACHE]    Shards: {len(shard_info)}")
    print(f"[CACHE]    Space freed: {total_freed_gb:.1f} GB")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="BeatSight Consolidated Feature Cache Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Convert train split (keeps original files)
    python -m training.utils.consolidated_cache convert \\
        --input-dir data/feature_cache/prod_combined_warmup \\
        --output-dir data/feature_cache_consolidated \\
        --split train

    # In-place conversion (deletes source files as it goes, minimal storage overhead)
    python -m training.utils.consolidated_cache convert-inplace \\
        --input-dir data/feature_cache/prod_combined_warmup \\
        --output-dir data/feature_cache_consolidated \\
        --split train --split val

    # Verify cache
    python -m training.utils.consolidated_cache verify \\
        --cache-dir data/feature_cache_consolidated/train
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Convert command (preserves source files)
    convert_parser = subparsers.add_parser("convert", help="Convert .pt files to shards (keeps originals)")
    convert_parser.add_argument("--input-dir", type=Path, required=True, help="Input cache directory")
    convert_parser.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    convert_parser.add_argument("--split", type=str, action="append", default=[], help="Splits to convert")
    convert_parser.add_argument("--workers", type=int, default=8, help="Parallel workers")
    convert_parser.add_argument("--samples-per-shard", type=int, default=SAMPLES_PER_SHARD, help="Samples per shard")
    convert_parser.add_argument("--dtype", type=str, default="float16", choices=["float32", "float16"], help="Storage dtype")
    
    # Convert-inplace command (deletes source files as it goes)
    inplace_parser = subparsers.add_parser("convert-inplace", help="Convert .pt files to shards, deleting originals (minimal storage)")
    inplace_parser.add_argument("--input-dir", type=Path, required=True, help="Input cache directory")
    inplace_parser.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    inplace_parser.add_argument("--split", type=str, action="append", default=[], help="Splits to convert")
    inplace_parser.add_argument("--workers", type=int, default=4, help="Parallel workers (lower = less peak storage)")
    inplace_parser.add_argument("--samples-per-shard", type=int, default=SAMPLES_PER_SHARD, help="Samples per shard")
    inplace_parser.add_argument("--dtype", type=str, default="float16", choices=["float32", "float16"], help="Storage dtype")
    inplace_parser.add_argument("--resume", action="store_true", help="Resume from previous run (skip existing shards)")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify consolidated cache")
    verify_parser.add_argument("--cache-dir", type=Path, required=True, help="Consolidated cache directory")
    verify_parser.add_argument("--samples", type=int, default=100, help="Number of samples to verify")
    
    args = parser.parse_args()
    
    if args.command == "convert":
        splits = args.split if args.split else ["train", "val"]
        dtype = torch.float16 if args.dtype == "float16" else torch.float32
        
        for split in splits:
            print(f"\n{'='*60}")
            print(f"Converting {split} split")
            print('='*60)
            convert_individual_to_consolidated(
                input_dir=args.input_dir,
                output_dir=args.output_dir,
                split=split,
                dtype=dtype,
                num_workers=args.workers,
                samples_per_shard=args.samples_per_shard,
            )
    
    elif args.command == "convert-inplace":
        splits = args.split if args.split else ["train", "val"]
        dtype = torch.float16 if args.dtype == "float16" else torch.float32
        
        if args.resume:
            print("\n" + "="*60)
            safe_print("🔄 RESUME MODE - Continuing previous conversion")
            print("="*60)
        else:
            print("\n" + "="*60)
            safe_print("⚠️  IN-PLACE CONVERSION MODE")
            print("="*60)
            print(f"This will DELETE source .pt files after converting each shard.")
            print(f"Peak storage overhead: ~{args.workers * SAMPLES_PER_SHARD * 34 / 1024:.1f} MB")
            print()
            confirm = input("Are you sure you want to proceed? [y/N]: ")
            if confirm.lower() not in ('y', 'yes'):
                print("Cancelled.")
                return
        
        for split in splits:
            print(f"\n{'='*60}")
            print(f"Converting {split} split (IN-PLACE{' - RESUME' if args.resume else ''})")
            print('='*60)
            convert_individual_to_consolidated_inplace(
                input_dir=args.input_dir,
                output_dir=args.output_dir,
                split=split,
                dtype=dtype,
                num_workers=args.workers,
                samples_per_shard=args.samples_per_shard,
                delete_source=True,
                resume=args.resume,
            )
    
    elif args.command == "verify":
        print(f"Verifying cache at {args.cache_dir}...")
        reader = ConsolidatedCacheReader(args.cache_dir)
        print(f"  Total samples: {len(reader):,}")
        print(f"  Tensor shape: {reader.tensor_shape}")
        print(f"  Dtype: {reader.dtype}")
        print(f"  Num shards: {reader.num_shards}")
        
        # Read random samples
        import random
        import time
        
        indices = random.sample(range(len(reader)), min(args.samples, len(reader)))
        
        start = time.perf_counter()
        for idx in indices:
            tensor = reader.get_by_index(idx)
            assert tensor.shape == reader.tensor_shape
        elapsed = time.perf_counter() - start
        
        print(f"\n  Verified {len(indices)} random samples in {elapsed:.3f}s")
        print(f"  Speed: {len(indices)/elapsed:.1f} samples/sec")
        reader.close()


if __name__ == "__main__":
    main()
