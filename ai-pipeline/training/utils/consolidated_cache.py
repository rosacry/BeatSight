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
import struct
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    
    Performance: Supports both JSON index (legacy) and binary index (10x faster).
    The binary index is used automatically if index.npz exists alongside index.json.
    
    When using direct cache mapping (cache_mapping.npz), the index can be skipped
    entirely for even faster worker startup. Pass skip_index=True to enable this.
    """
    
    def __init__(self, cache_dir: Path, skip_index: bool = False, verbose: bool = True):
        """
        Initialize the consolidated cache reader.
        
        Args:
            cache_dir: Directory containing the consolidated cache shards
            skip_index: If True, skip loading the index file (use when you have
                       direct cache mapping and only need _read_sample). This
                       dramatically speeds up worker startup on Windows.
            verbose: If True, print loading progress. Set False in worker processes
                    to avoid corrupting tqdm progress bars.
        """
        self.cache_dir = Path(cache_dir)
        self._skip_index = skip_index
        self._verbose = verbose
        
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
        self._sample_numel = int(np.prod(self.tensor_shape))
        
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
        
        # Initialize index-related attributes
        self._use_binary_index = False
        self._index_keys = None
        self._index_shards = None
        self._index_offsets = None
        self._index_map = None
        self.index = None
        
        # Skip index loading if requested (when using direct cache mapping)
        # This dramatically speeds up worker startup on Windows
        if skip_index:
            if self._verbose:
                safe_print(f"[CACHE] Skipping index load (using direct cache mapping): {self.num_shards} shards")
        else:
            # Load index - prefer binary format (10x faster than JSON)
            index_npz_path = self.cache_dir / "index.npz"
            index_json_path = self.cache_dir / INDEX_FILENAME
            
            if index_npz_path.exists():
                # Binary index: numpy arrays for O(1) lookup
                # CRITICAL: Use mmap_mode='r' for memory-mapped loading!
                # This allows OS-level memory sharing across DataLoader workers.
                # Without mmap, each of 8 workers would load 1GB of index data = 8GB RAM.
                # With mmap, the OS shares the same physical pages = ~1GB total.
                # Performance: mmap loading is also faster since it's lazy (pages loaded on demand).
                try:
                    data = np.load(index_npz_path, allow_pickle=False, mmap_mode='r')
                    self._index_keys = data['keys']  # byte strings (SORTED)
                    self._index_shards = data['shards']  # uint16 shard IDs
                    self._index_offsets = data['offsets']  # uint32 offsets
                    # Check if sorted (new format uses binary search, no hash table needed)
                    if len(self._index_keys) > 1:
                        # Check sort order by sampling a few positions
                        is_sorted = (self._index_keys[0] <= self._index_keys[len(self._index_keys)//2] <= 
                                    self._index_keys[-1])
                    else:
                        is_sorted = True
                    
                    if is_sorted:
                        # SORTED format: use binary search (no memory overhead!)
                        self._index_map = None
                        if self._verbose:
                            safe_print(f"[CACHE] Using BINARY index (sorted, memory-efficient): {len(self._index_keys):,} entries")
                    else:
                        # OLD format (unsorted): need hash table (rebuild once, ~2GB overhead)
                        if self._verbose:
                            safe_print(f"[CACHE] Building index hash table ({len(self._index_keys):,} entries)... ", end="", flush=True)
                        self._index_map = {k: i for i, k in enumerate(self._index_keys)}
                        if self._verbose:
                            safe_print("done")
                    self._use_binary_index = True
                except Exception as e:
                    if self._verbose:
                        safe_print(f"[CACHE] Failed to load binary index: {e}, falling back to JSON")
                    self._use_binary_index = False
            
            if not self._use_binary_index:
                # Fallback to JSON index
                if not index_json_path.exists():
                    raise FileNotFoundError(f"Index not found: {index_json_path}")
                
                if self._verbose:
                    safe_print("[CACHE] Loading JSON index (this may take a while for large caches)...")
                with open(index_json_path) as f:
                    self.index = json.load(f)
                if self._verbose:
                    safe_print(f"[CACHE] Loaded JSON index: {len(self.index):,} entries")
        
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
        # Ensure index is loaded (handles lazy reload after unpickling)
        self._ensure_index_loaded()
        
        if self._use_binary_index:
            # Binary index: encode key and look up
            key_bytes = relative_path.encode('utf-8')
            
            if self._index_map is not None:
                # Hash table lookup (O(1), but uses ~2GB RAM per worker)
                idx = self._index_map.get(key_bytes)
                if idx is None:
                    return None
            else:
                # Binary search lookup (O(log n), zero extra RAM!)
                idx = np.searchsorted(self._index_keys, key_bytes)
                if idx >= len(self._index_keys) or self._index_keys[idx] != key_bytes:
                    return None
                idx = int(idx)
            
            shard_id = int(self._index_shards[idx])
            offset = int(self._index_offsets[idx])
        else:
            # JSON index: direct dict lookup
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
        bytes_needed = byte_offset + self.bytes_per_sample
        
        # Validate bounds BEFORE attempting to read
        # This prevents ValueError: buffer is smaller than requested size
        if bytes_needed > len(mm):
            import warnings
            shard_info = self.shard_infos.get(shard_id, {})
            shard_name = shard_info.get("filename", f"shard_{shard_id}")
            warnings.warn(
                f"Consolidated cache bounds error: shard {shard_name} has {len(mm):,} bytes, "
                f"but need {bytes_needed:,} bytes for sample at offset {offset}. "
                f"Shard may be truncated/corrupt. Using zeros."
            )
            return torch.zeros(self.tensor_shape, dtype=torch.float32)
        
        # Create numpy array view directly from mmap buffer
        # Use np.frombuffer for zero-copy view, then copy to make writable tensor
        try:
            arr = np.frombuffer(
                mm,
                dtype=self._np_dtype,
                count=self._sample_numel,
                offset=byte_offset,
            )
        except ValueError as e:
            import warnings
            warnings.warn(
                f"Consolidated cache read error at shard {shard_id} offset {offset}: {e}. Using zeros."
            )
            return torch.zeros(self.tensor_shape, dtype=torch.float32)

        if arr.size != self._sample_numel:
            import warnings
            warnings.warn(
                f"Consolidated cache read error: expected {self._sample_numel} values, "
                f"got {arr.size} at shard {shard_id} offset {offset}. Using zeros."
            )
            return torch.zeros(self.tensor_shape, dtype=torch.float32)

        # Create tensor directly from bytes, then reshape
        # Using torch.as_tensor with copy=True is faster than arr.copy() + torch.from_numpy
        tensor = torch.tensor(arr, dtype=torch.float32).view(self.tensor_shape)
        
        # Handle bfloat16 - need special conversion
        if self.dtype == torch.bfloat16:
            # For bfloat16, we loaded as uint16, need to reinterpret
            tensor = tensor.view(torch.bfloat16).to(torch.float32)
        
        return tensor
    
    def close(self) -> None:
        """Close all memory-mapped shards and file handles.
        
        CRITICAL: Must be called when done with the cache to prevent resource leaks.
        With 225+ shards and multiple DataLoader workers, failing to close can
        exhaust system file descriptors and cause 'Too many open files' errors.
        """
        for shard_id, (mm, f) in list(self._mmap_cache.items()):
            try:
                mm.close()
            except Exception:
                pass
            try:
                f.close()
            except Exception:
                pass
        self._mmap_cache.clear()
    
    def __del__(self) -> None:
        """Destructor to ensure resources are freed."""
        self.close()
    
    def __enter__(self) -> "ConsolidatedCacheReader":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close all resources."""
        self.close()
    
    def __len__(self) -> int:
        return self.total_samples
    
    def __contains__(self, relative_path: str) -> bool:
        self._ensure_index_loaded()
        if self._use_binary_index:
            key_bytes = relative_path.encode('utf-8')
            if self._index_map is not None:
                return key_bytes in self._index_map
            else:
                # Binary search
                idx = np.searchsorted(self._index_keys, key_bytes)
                return idx < len(self._index_keys) and self._index_keys[idx] == key_bytes
        return relative_path in self.index
    
    def warmup(
        self, 
        num_samples: int = 10000, 
        verbose: bool = True,
        subset_indices: Optional[Sequence[int]] = None,
    ) -> None:
        """
        Warm up the cache by reading samples to force mmap pages into RAM.
        
        This significantly speeds up subsequent random access. Without warmup,
        first-epoch training can be 10-20x slower as pages are faulted in on demand.
        
        Args:
            num_samples: Number of samples to read for warmup. Default 10000 ensures
                        at least one sample from each shard (with 225 shards).
            verbose: Print progress messages
            subset_indices: Optional list of indices to focus warmup on. When provided,
                           warmup will only touch shards containing these indices.
                           This is critical when using --train-fraction with contiguous
                           subset mode - warming all shards wastes time on unused data.
        """
        import time
        start_time = time.time()
        
        # Determine which shards to warm up
        if subset_indices is not None and len(subset_indices) > 0:
            # Focus warmup on shards that will actually be accessed
            subset_arr = np.asarray(subset_indices, dtype=np.int64)
            target_shards = set()
            for idx in subset_arr:
                # Find which shard this index belongs to
                for i, cumsum in enumerate(self._cumulative_samples[1:], 1):
                    if idx < cumsum:
                        target_shards.add(i - 1)
                        break
            
            if verbose:
                safe_print(f"[CACHE] Warming up {num_samples:,} samples across {len(target_shards)}/{self.num_shards} active shards...")
            
            # Warm up within the subset shards only
            target_shards_list = sorted(target_shards)
            samples_per_shard = max(1, num_samples // len(target_shards_list))
            samples_read = 0
            shards_touched = set()
            
            for shard_id in target_shards_list:
                # Get sample range for this shard
                shard_start = self._cumulative_samples[shard_id] if shard_id > 0 else 0
                shard_end = self._cumulative_samples[shard_id + 1] if shard_id + 1 < len(self._cumulative_samples) else self.total_samples
                shard_size = shard_end - shard_start
                
                # Read evenly spaced samples from this shard
                step = max(1, shard_size // samples_per_shard)
                for i in range(0, shard_size, step):
                    global_idx = shard_start + i
                    try:
                        tensor = self.get_by_index(global_idx)
                        samples_read += 1
                        shards_touched.add(shard_id)
                        if samples_read >= num_samples:
                            break
                    except Exception as e:
                        if verbose:
                            safe_print(f"[CACHE] Warmup warning at index {global_idx}: {e}")
                
                if samples_read >= num_samples:
                    break
        else:
            # Original behavior: warm up evenly across all shards
            if verbose:
                safe_print(f"[CACHE] Warming up {num_samples:,} samples across {self.num_shards} shards...")
            
            step = max(1, self.total_samples // num_samples)
            samples_read = 0
            shards_touched = set()
            
            for global_idx in range(0, self.total_samples, step):
                try:
                    # Read sample (forces mmap page fault)
                    tensor = self.get_by_index(global_idx)
                    samples_read += 1
                    
                    # Track which shards we've touched
                    shard_id = 0
                    for i, cumsum in enumerate(self._cumulative_samples[1:], 1):
                        if global_idx < cumsum:
                            shard_id = i - 1
                            break
                    shards_touched.add(shard_id)
                    
                    if samples_read >= num_samples:
                        break
                except Exception as e:
                    if verbose:
                        safe_print(f"[CACHE] Warmup warning at index {global_idx}: {e}")
        
        elapsed = time.time() - start_time
        if verbose:
            safe_print(f"[CACHE] Warmup complete: {samples_read:,} samples, "
                      f"{len(shards_touched)}/{self.num_shards} shards, {elapsed:.1f}s")
    
    def close(self) -> None:
        """Close all memory-mapped files."""
        # Guard against partially initialized objects (e.g., during multiprocessing fork)
        if not hasattr(self, '_mmap_cache'):
            return
        for mm, f in self._mmap_cache.values():
            mm.close()
            f.close()
        self._mmap_cache.clear()
    
    def __del__(self):
        self.close()
    
    def __getstate__(self) -> dict:
        """
        Prepare state for pickling (required for multiprocessing on Windows).
        
        Excludes mmap cache and large index data since these can't be pickled
        efficiently. Each worker process will re-load from disk.
        
        When skip_index was True during init, workers will also skip index loading.
        """
        state = self.__dict__.copy()
        # Remove unpicklable mmap cache - will be re-created in workers
        state['_mmap_cache'] = {}
        
        # If we skipped index at init, don't mark for reload (there's nothing to reload)
        if getattr(self, '_skip_index', False):
            state['_needs_index_reload'] = False
        else:
            # Mark for lazy reload of index data
            state['_needs_index_reload'] = True
            # Don't pickle the large index structures - workers will reload
            if self._use_binary_index:
                state['_index_keys'] = None
                state['_index_shards'] = None
                state['_index_offsets'] = None
                state['_index_map'] = None
            else:
                state['index'] = None
        return state
    
    def __setstate__(self, state: dict) -> None:
        """
        Restore state after unpickling.
        The mmap cache and index start empty and will be populated on first access.
        """
        self.__dict__.update(state)
        # Ensure mmap cache is initialized
        if '_mmap_cache' not in self.__dict__:
            self._mmap_cache = {}
    
    def _ensure_index_loaded(self) -> None:
        """Lazily reload index after unpickling."""
        if not getattr(self, '_needs_index_reload', False):
            return
        
        # Reload index from disk (same logic as __init__)
        index_npz_path = self.cache_dir / "index.npz"
        
        if self._use_binary_index and index_npz_path.exists():
            # CRITICAL: Use mmap_mode='r' for memory-mapped loading!
            # This allows OS-level memory sharing across DataLoader workers.
            # Without mmap, each of 8 workers would load 1GB of index data = 8GB RAM.
            # With mmap, the OS shares the same physical pages = ~1GB total.
            data = np.load(index_npz_path, allow_pickle=False, mmap_mode='r')
            self._index_keys = data['keys']
            self._index_shards = data['shards']
            self._index_offsets = data['offsets']
            # Use binary search (no hash table rebuild - saves ~2GB RAM per worker!)
            self._index_map = None
        else:
            index_json_path = self.cache_dir / INDEX_FILENAME
            with open(index_json_path) as f:
                self.index = json.load(f)
        
        self._needs_index_reload = False
    
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
            print("[CACHE] RESUME MODE: Loading existing index...")
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
        print("[CACHE] IN-PLACE MODE: Source files will be deleted after each shard")
    
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
    
    safe_print("[CACHE] ✅ Conversion complete!")
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
    
    # Validate command (comprehensive shard integrity check)
    validate_parser = subparsers.add_parser("validate", help="Validate all shard files for size consistency (finds corruption)")
    validate_parser.add_argument("--cache-dir", type=Path, required=True, help="Consolidated cache directory")
    validate_parser.add_argument("--fix", action="store_true", help="Attempt to fix issues (regenerate corrupt shards)")
    
    # Convert-index command (creates binary index for 10x faster worker loading)
    index_parser = subparsers.add_parser("convert-index", help="Convert JSON index to binary format (10x faster loading)")
    index_parser.add_argument("--cache-dir", type=Path, required=True, help="Consolidated cache directory with index.json")
    
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
            print("This will DELETE source .pt files after converting each shard.")
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
    
    elif args.command == "validate":
        # Comprehensive shard integrity check
        print(f"Validating cache at {args.cache_dir}...")
        
        manifest_path = args.cache_dir / MANIFEST_FILENAME
        if not manifest_path.exists():
            print(f"ERROR: Manifest not found: {manifest_path}")
            sys.exit(1)
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        bytes_per_sample = manifest["bytes_per_sample"]
        total_samples = manifest["total_samples"]
        shards = manifest["shards"]
        
        print(f"  Total samples expected: {total_samples:,}")
        print(f"  Bytes per sample: {bytes_per_sample:,}")
        print(f"  Number of shards: {len(shards)}")
        print()
        
        corrupt_shards = []
        missing_shards = []
        total_samples_found = 0
        
        for shard in shards:
            shard_id = shard["shard_id"]
            filename = shard["filename"]
            expected_samples = shard["num_samples"]
            expected_size = HEADER_SIZE + expected_samples * bytes_per_sample
            
            shard_path = args.cache_dir / filename
            
            if not shard_path.exists():
                print(f"  ❌ MISSING: {filename}")
                missing_shards.append(shard)
                continue
            
            actual_size = shard_path.stat().st_size
            
            if actual_size != expected_size:
                print(f"  ❌ CORRUPT: {filename}")
                print(f"       Expected: {expected_size:,} bytes ({expected_samples:,} samples)")
                print(f"       Actual:   {actual_size:,} bytes ({(actual_size - HEADER_SIZE) // bytes_per_sample:,} samples)")
                max_valid_samples = (actual_size - HEADER_SIZE) // bytes_per_sample
                print(f"       Max valid offset: {max_valid_samples - 1}")
                corrupt_shards.append({
                    **shard,
                    "actual_size": actual_size,
                    "expected_size": expected_size,
                    "max_valid_samples": max_valid_samples,
                })
            else:
                total_samples_found += expected_samples
        
        print()
        if corrupt_shards or missing_shards:
            print(f"{'='*60}")
            print("VALIDATION FAILED")
            print(f"{'='*60}")
            print(f"  Missing shards: {len(missing_shards)}")
            print(f"  Corrupt shards: {len(corrupt_shards)}")
            print(f"  Valid samples: {total_samples_found:,} / {total_samples:,}")
            
            if corrupt_shards:
                print()
                print("Corrupt shard details:")
                for s in corrupt_shards:
                    print(f"  - {s['filename']}: has {s['max_valid_samples']:,} samples, expected {s['num_samples']:,}")
            
            if args.fix:
                print()
                print("To fix, you'll need to regenerate the corrupt shards from original data.")
                print("Run option 4r (Rebuild Cache) from the training menu.")
            else:
                print()
                print("Run with --fix to see repair options, or use option 4r to rebuild cache.")
            
            sys.exit(1)
        else:
            print(f"✅ All {len(shards)} shards validated successfully!")
            print(f"   Total samples: {total_samples_found:,}")
    
    elif args.command == "convert-index":
        cache_dir = args.cache_dir
        index_json = cache_dir / INDEX_FILENAME
        index_npz = cache_dir / "index.npz"
        
        if not index_json.exists():
            print(f"ERROR: {index_json} not found")
            sys.exit(1)
        
        if index_npz.exists():
            print(f"Binary index already exists: {index_npz}")
            confirm = input("Overwrite? [y/N]: ")
            if confirm.lower() not in ('y', 'yes'):
                print("Cancelled.")
                return
        
        print(f"Loading JSON index from {index_json}...")
        print("  (This may take a while for large indices)")
        
        import time
        start = time.perf_counter()
        with open(index_json) as f:
            index_data = json.load(f)
        json_load_time = time.perf_counter() - start
        print(f"  Loaded {len(index_data):,} entries in {json_load_time:.1f}s")
        
        print("Converting to binary format (SORTED for memory-efficient binary search)...")
        start = time.perf_counter()
        
        # Pre-allocate arrays
        n = len(index_data)
        keys = []
        shards_list = []
        offsets_list = []
        
        for i, (key, (shard_id, offset)) in enumerate(index_data.items()):
            keys.append(key.encode('utf-8'))
            shards_list.append(shard_id)
            offsets_list.append(offset)
            
            if (i + 1) % 1_000_000 == 0:
                print(f"  Processed {i+1:,}/{n:,} entries...")
        
        # Create byte-string array
        max_len = max(len(k) for k in keys)
        keys_arr = np.array(keys, dtype=f'S{max_len}')
        shards = np.array(shards_list, dtype=np.uint16)
        offsets = np.array(offsets_list, dtype=np.uint32)
        
        # SORT by key for binary search (critical for memory efficiency!)
        print(f"  Sorting {n:,} keys for binary search...")
        sort_indices = np.argsort(keys_arr)
        keys_arr = keys_arr[sort_indices]
        shards = shards[sort_indices]
        offsets = offsets[sort_indices]
        
        convert_time = time.perf_counter() - start
        print(f"  Conversion done in {convert_time:.1f}s")
        
        print(f"Saving binary index to {index_npz}...")
        start = time.perf_counter()
        np.savez(index_npz, keys=keys_arr, shards=shards, offsets=offsets)
        save_time = time.perf_counter() - start
        
        # Report size comparison
        json_size = index_json.stat().st_size / 1e9
        npz_size = index_npz.stat().st_size / 1e9
        
        print("\n✅ Binary index created (SORTED)!")
        print(f"  JSON size: {json_size:.2f} GB")
        print(f"  Binary size: {npz_size:.2f} GB ({100*npz_size/json_size:.0f}% of original)")
        print(f"  JSON load time: {json_load_time:.1f}s")
        print(f"  Binary load time: ~{json_load_time/10:.1f}s (estimated 10x faster)")
        print("\n🚀 Memory-Efficient Mode: Uses binary search (O(log n)) instead of hash table.")
        print("   This saves ~2GB RAM PER WORKER, critical for 10-worker configs!")
        print("\nThe binary index will be used automatically on next training run.")


if __name__ == "__main__":
    main()
