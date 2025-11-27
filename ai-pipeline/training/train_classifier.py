"""
Simple training script for the drum classifier CNN.

Usage:
    python train_classifier.py --dataset ./dataset --epochs 50 --batch-size 32

Optionally emit a metrics JSON for downstream automation:
    python train_classifier.py --dataset ./dataset --metrics-json reports/run.json
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import random
import warnings
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Use orjson for memory-efficient JSON parsing (important for large label files)
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None  # type: ignore
    HAS_ORJSON = False

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.amp import GradScaler, autocast
from torch.nn.utils import clip_grad_norm_
from torch.utils.data import DataLoader, Dataset, Subset
import librosa
import numpy as np
from tqdm import tqdm


warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="You are using `torch.load` with `weights_only=False`",
)

try:
    import torchaudio
    from torchaudio import functional as ta_F
    from torchaudio import transforms as ta_T
except Exception:  # pragma: no cover - optional dependency
    torchaudio = None
    ta_F = None
    ta_T = None

try:
    import wandb  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    wandb = None

# Import our model
import sys
sys.path.append(str(Path(__file__).parent.parent))
from transcription.ml_drum_classifier import DrumClassifierCNN
from training.common_paths import dataset_root as default_dataset_root
from training.common_paths import feature_cache_root as default_feature_cache_root

# Optional v2 model with Squeeze-Excitation attention
try:
    from transcription.ml_drum_classifier_v2 import DrumClassifierCNNv2
    HAS_V2_MODEL = True
except ImportError:
    HAS_V2_MODEL = False
    DrumClassifierCNNv2 = None  # type: ignore

# Optional Mixup/CutMix augmentation
try:
    from training.augmentation.mixup import MixupCutmix, mixed_criterion
    HAS_MIXUP = True
except ImportError:
    HAS_MIXUP = False
    MixupCutmix = None  # type: ignore
    mixed_criterion = None  # type: ignore

# Optional SpecAugment
try:
    from training.augmentation.specaugment import SpecAugment, get_specaugment
    HAS_SPECAUGMENT = True
except ImportError:
    HAS_SPECAUGMENT = False
    SpecAugment = None  # type: ignore
    get_specaugment = None  # type: ignore

# Optional Focal Loss
try:
    from training.losses.focal_loss import FocalLoss, FocalLossWithMixup, get_focal_loss
    HAS_FOCAL_LOSS = True
except ImportError:
    HAS_FOCAL_LOSS = False
    FocalLoss = None  # type: ignore
    FocalLossWithMixup = None  # type: ignore
    get_focal_loss = None  # type: ignore

# Optional EMA (Exponential Moving Average)
try:
    from training.utils.ema import ModelEMA, get_ema_decay
    HAS_EMA = True
except ImportError:
    HAS_EMA = False
    ModelEMA = None  # type: ignore
    get_ema_decay = None  # type: ignore

# Optional Progressive/Adaptive Augmentation
try:
    from training.utils.adaptive import ProgressiveAugmentation, get_recommended_schedules
    HAS_PROGRESSIVE = True
except ImportError:
    HAS_PROGRESSIVE = False
    ProgressiveAugmentation = None  # type: ignore
    get_recommended_schedules = None  # type: ignore

# Optional SAM (Sharpness-Aware Minimization) optimizer
try:
    from training.optimizers.sam import SAM, ESAM, enable_running_stats, disable_running_stats
    HAS_SAM = True
except ImportError:
    HAS_SAM = False
    SAM = None  # type: ignore
    ESAM = None  # type: ignore
    enable_running_stats = None  # type: ignore
    disable_running_stats = None  # type: ignore

# Optional SWA (Stochastic Weight Averaging)
try:
    from training.utils.swa import SWAManager, SWAPlusEMA
    HAS_SWA = True
except ImportError:
    HAS_SWA = False
    SWAManager = None  # type: ignore
    SWAPlusEMA = None  # type: ignore

# Optional R-Drop (Regularized Dropout)
try:
    from training.losses.rdrop import RDropLoss, rdrop_forward, get_rdrop_loss
    HAS_RDROP = True
except ImportError:
    HAS_RDROP = False
    RDropLoss = None  # type: ignore
    rdrop_forward = None  # type: ignore
    get_rdrop_loss = None  # type: ignore

# Optional Curriculum Learning
try:
    from training.utils.curriculum import CurriculumScheduler, DifficultyScorer, compute_difficulty_scores
    HAS_CURRICULUM = True
except ImportError:
    HAS_CURRICULUM = False
    CurriculumScheduler = None  # type: ignore
    DifficultyScorer = None  # type: ignore
    compute_difficulty_scores = None  # type: ignore

# Optional Temperature Calibration
try:
    from training.calibration.temperature_scaling import TemperatureScaler, calibrate_model
    HAS_CALIBRATION = True
except ImportError:
    HAS_CALIBRATION = False
    TemperatureScaler = None  # type: ignore
    calibrate_model = None  # type: ignore

# Optional CBAM v3 model
try:
    from training.models.cbam import DrumClassifierCNNv3
    HAS_V3_MODEL = True
except ImportError:
    HAS_V3_MODEL = False
    DrumClassifierCNNv3 = None  # type: ignore

# Optional Coordinate Attention v4 model
try:
    from training.models.coord_attention import DrumClassifierCNNv4, CoordinateAttention
    HAS_V4_MODEL = True
except ImportError:
    HAS_V4_MODEL = False
    DrumClassifierCNNv4 = None  # type: ignore
    CoordinateAttention = None  # type: ignore

# Optional FMix augmentation
try:
    from training.augmentation.fmix import FMix, FMixCutmix, fmix_criterion
    HAS_FMIX = True
except ImportError:
    HAS_FMIX = False
    FMix = None  # type: ignore
    FMixCutmix = None  # type: ignore
    fmix_criterion = None  # type: ignore

# Optional Confident Learning (label noise detection)
try:
    from training.utils.confident_learning import (
        find_label_issues, estimate_noise_matrix, clean_labels,
        LabelNoiseDataset, run_label_audit
    )
    HAS_CONFIDENT_LEARNING = True
except ImportError:
    HAS_CONFIDENT_LEARNING = False
    find_label_issues = None  # type: ignore
    estimate_noise_matrix = None  # type: ignore
    clean_labels = None  # type: ignore
    LabelNoiseDataset = None  # type: ignore
    run_label_audit = None  # type: ignore

# Optional Active Learning
try:
    from training.active.sampler import (
        ActiveLearner, ActiveLearningConfig,
        UncertaintySampler, DiversitySampler, HybridSampler
    )
    HAS_ACTIVE_LEARNING = True
except ImportError:
    HAS_ACTIVE_LEARNING = False
    ActiveLearner = None  # type: ignore
    ActiveLearningConfig = None  # type: ignore
    UncertaintySampler = None  # type: ignore
    DiversitySampler = None  # type: ignore
    HybridSampler = None  # type: ignore

# Optional Self-Training
try:
    from training.ssl_training.self_training import SelfTrainer, run_self_training
    HAS_SELF_TRAINING = True
except ImportError:
    HAS_SELF_TRAINING = False
    SelfTrainer = None  # type: ignore
    run_self_training = None  # type: ignore

# Optional Gradient Centralization (NEW - improves generalization)
try:
    from training.optimizers.gradient_centralization import GradientCentralization, wrap_optimizer_with_gc
    HAS_GRADIENT_CENTRALIZATION = True
except ImportError:
    HAS_GRADIENT_CENTRALIZATION = False
    GradientCentralization = None  # type: ignore
    wrap_optimizer_with_gc = None  # type: ignore

# Optional Lookahead Optimizer (Zhang et al., NeurIPS 2019 - smoother optimization)
try:
    from training.optimizers.lookahead import Lookahead, wrap_with_lookahead
    HAS_LOOKAHEAD = True
except ImportError:
    HAS_LOOKAHEAD = False
    Lookahead = None  # type: ignore
    wrap_with_lookahead = None  # type: ignore

# Optional Deep Supervision (NEW - auxiliary losses at intermediate layers)
try:
    from training.losses.deep_supervision import DeepSupervisionLoss, DeepSupervisionWrapper
    HAS_DEEP_SUPERVISION = True
except ImportError:
    HAS_DEEP_SUPERVISION = False
    DeepSupervisionLoss = None  # type: ignore
    DeepSupervisionWrapper = None  # type: ignore

# Optional Hard Negative Mining (Option A enhancement - focus on confusing pairs)
try:
    from training.losses.hard_negative_mining import (
        HardNegativeLoss, HardNegativeConfig, OnlineHardNegativeMiner
    )
    HAS_HARD_NEGATIVE_MINING = True
except ImportError:
    HAS_HARD_NEGATIVE_MINING = False
    HardNegativeLoss = None  # type: ignore
    HardNegativeConfig = None  # type: ignore
    OnlineHardNegativeMiner = None  # type: ignore

# Optional CNN v5 (ULTIMATE model with all innovations)
try:
    from training.models.cnn_v5 import DrumClassifierCNNv5, cnn_v5_small, cnn_v5_medium, cnn_v5_large
    HAS_V5_MODEL = True
except ImportError:
    HAS_V5_MODEL = False
    DrumClassifierCNNv5 = None  # type: ignore
    cnn_v5_small = None  # type: ignore
    cnn_v5_medium = None  # type: ignore
    cnn_v5_large = None  # type: ignore

# Optional BEATs Audio Foundation Model
try:
    from training.models.beats import BEATsDrumClassifier, create_beats_encoder
    HAS_BEATS = True
except ImportError:
    HAS_BEATS = False
    BEATsDrumClassifier = None  # type: ignore
    create_beats_encoder = None  # type: ignore

# Optional Stochastic Depth (DropPath regularization)
try:
    from training.utils.stochastic_depth import DropPath, get_drop_path_rate
    HAS_STOCHASTIC_DEPTH = True
except ImportError:
    HAS_STOCHASTIC_DEPTH = False
    DropPath = None  # type: ignore
    get_drop_path_rate = None  # type: ignore

# Optional Waveform Augmentation (NEW - audio-level augmentation)
try:
    from training.augmentation.waveform import WaveformAugment, FastWaveformAugment, get_waveform_augment
    HAS_WAVEFORM_AUGMENT = True
except ImportError:
    HAS_WAVEFORM_AUGMENT = False
    WaveformAugment = None  # type: ignore
    FastWaveformAugment = None  # type: ignore
    get_waveform_augment = None  # type: ignore

# Consolidated Memory-Mapped Cache (HIGH-PERFORMANCE - 100x faster than individual .pt files)
try:
    from training.utils.consolidated_cache import ConsolidatedCacheReader
    HAS_CONSOLIDATED_CACHE = True
except ImportError:
    HAS_CONSOLIDATED_CACHE = False
    ConsolidatedCacheReader = None  # type: ignore


class DrumSampleDataset(Dataset):
    """PyTorch dataset for drum samples with optional feature caching."""

    def __init__(
        self,
        data_dir: str | Path,
        labels_file: str | Path,
        sr: int = 44100,
        *,
        cache_dir: Optional[Path] = None,
        prefer_torchaudio: bool = True,
        n_fft: int = 2048,
        hop_length: int = 512,
        n_mels: int = 128,
        fmax: Optional[int] = 8000,
        target_frames: int = 128,
        cache_dtype: str = "float32",
        waveform_transform: Optional[Any] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.labels_path = Path(labels_file)
        self.sr = sr
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.n_fft = n_fft
        self.win_length = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.fmax = fmax
        self.target_frames = target_frames
        self._torchaudio_enabled = bool(prefer_torchaudio and torchaudio is not None and ta_T is not None)
        self._mel_transform = None
        self._amplitude_to_db = None
        self._cache_debug = bool(os.environ.get("BS_CACHE_DEBUG"))
        self.waveform_transform = waveform_transform

        cache_dtype_key = cache_dtype.lower().strip()
        cache_dtype_map: Dict[str, torch.dtype] = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        if cache_dtype_key not in cache_dtype_map:
            raise ValueError(f"Unsupported cache dtype '{cache_dtype}'. Expected one of {sorted(cache_dtype_map)}")
        self._cache_store_dtype = cache_dtype_map[cache_dtype_key]

        if self._torchaudio_enabled:
            # Build reusable transforms so workers avoid re-instantiation overhead.
            self._mel_transform = ta_T.MelSpectrogram(
                sample_rate=self.sr,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                win_length=self.win_length,
                n_mels=self.n_mels,
                f_max=self.fmax,
                pad_mode="reflect",
                power=2.0,
                center=True,
                normalized=False,
            )
            self._amplitude_to_db = ta_T.AmplitudeToDB(stype="power")

        # Try to load consolidated cache (100x faster than individual .pt files)
        self._consolidated_reader: Optional[Any] = None
        if self.cache_dir is not None and HAS_CONSOLIDATED_CACHE:
            # Check for consolidated cache in cache_dir itself
            # Expected structure: cache_dir/manifest.json
            consolidated_manifest = self.cache_dir / "manifest.json"
            if consolidated_manifest.exists():
                try:
                    self._consolidated_reader = ConsolidatedCacheReader(self.cache_dir)
                    print(f"[CACHE] Using CONSOLIDATED cache: {len(self._consolidated_reader):,} samples, "
                          f"{self._consolidated_reader.num_shards} shards (100x faster)")
                except Exception as e:
                    print(f"[CACHE] Failed to load consolidated cache: {e}")
                    self._consolidated_reader = None
            else:
                # Check for consolidated cache in sibling directory
                # e.g., cache_dir = .../prod_combined_warmup/train
                #       consolidated = .../prod_combined_warmup_consolidated/train
                cache_parent = self.cache_dir.parent  # .../prod_combined_warmup
                cache_grandparent = cache_parent.parent  # .../feature_cache
                split_name = self.cache_dir.name  # train
                consolidated_parent = cache_grandparent / f"{cache_parent.name}_consolidated"
                consolidated_alt = consolidated_parent / split_name
                
                if (consolidated_alt / "manifest.json").exists():
                    try:
                        self._consolidated_reader = ConsolidatedCacheReader(consolidated_alt)
                        print(f"[CACHE] Using CONSOLIDATED cache: {len(self._consolidated_reader):,} samples, "
                              f"{self._consolidated_reader.num_shards} shards (100x faster)")
                    except Exception as e:
                        print(f"[CACHE] Failed to load consolidated cache from {consolidated_alt}: {e}")
                        self._consolidated_reader = None

        # Load labels - support multiple formats for memory efficiency
        labels_data = self._load_labels()
        if not isinstance(labels_data, list):
            raise ValueError(f"Expected list of labels in {self.labels_path}, found {type(labels_data)!r}")
        self.labels: List[Dict[str, Any]] = labels_data
        
        # Initialize lazy-reload flags (used after pickle/unpickle)
        self._numpy_needs_reload = False
        self._consolidated_needs_reload = False

    def _load_labels(self) -> List[Dict[str, Any]]:
        """Load labels from numpy, JSON, pickle, or sharded pickle format."""
        import pickle
        
        # Check for separate numpy files first (most memory-efficient)
        # These are created by convert_labels_to_numpy.py as {stem}_files.npy and {stem}_labels.npy
        npy_files_path = self.labels_path.parent / f"{self.labels_path.stem}_files.npy"
        npy_labels_path = self.labels_path.parent / f"{self.labels_path.stem}_labels.npy"
        if npy_files_path.exists() and npy_labels_path.exists():
            print(f"[LABELS] Loading from numpy files: {npy_files_path.parent}")
            # Load into RAM (mmap can cause segfaults with certain access patterns)
            files = np.load(npy_files_path)
            labels = np.load(npy_labels_path)
            total_size = npy_files_path.stat().st_size + npy_labels_path.stat().st_size
            print(f"[LABELS] Loaded {len(labels):,} items from numpy ({total_size / 1e6:.1f} MB)")
            # Store numpy arrays directly, decode file paths on access
            self._numpy_files = files
            self._numpy_labels = labels
            self._use_numpy = True
            self._files_are_bytes = files.dtype.kind == 'S'  # Check if byte strings
            return []  # Return empty list, use numpy arrays directly
        
        # Check for combined .npz format (legacy)
        npz_path = self.labels_path.with_suffix(".npz")
        if npz_path.exists():
            print(f"[LABELS] Loading from numpy npz: {npz_path}")
            data = np.load(npz_path, allow_pickle=False)
            files = data['files']  # byte strings (S dtype) or unicode (U dtype)
            labels = data['labels']
            print(f"[LABELS] Loaded {len(labels):,} items from numpy ({npz_path.stat().st_size / 1e6:.1f} MB)")
            # Store numpy arrays directly, decode file paths on access
            self._numpy_files = files
            self._numpy_labels = labels
            self._use_numpy = True
            self._files_are_bytes = files.dtype.kind == 'S'  # Check if byte strings
            return []  # Return empty list, use numpy arrays directly
        
        self._use_numpy = False
        
        # Check for sharded pickle directory (memory-efficient streaming)
        shards_dir = self.labels_path.parent / (self.labels_path.stem + "_shards")
        if shards_dir.exists() and (shards_dir / "meta.pkl").exists():
            print(f"[LABELS] Loading from sharded pickles: {shards_dir}")
            with open(shards_dir / "meta.pkl", "rb") as f:
                meta = pickle.load(f)
            items = []
            for i in range(meta['num_shards']):
                shard_path = shards_dir / f"shard_{i:04d}.pkl"
                with open(shard_path, "rb") as f:
                    shard_data = pickle.load(f)
                    items.extend(shard_data)
                    del shard_data  # Free memory immediately
                if (i + 1) % 5 == 0:
                    print(f"[LABELS]   Loaded {i+1}/{meta['num_shards']} shards ({len(items):,} items)...")
            print(f"[LABELS] Loaded {len(items):,} items from {meta['num_shards']} shards")
            return items
        
        # Check for single pickle file
        pkl_path = self.labels_path.with_suffix(".pkl")
        if pkl_path.exists():
            print(f"[LABELS] Loading from pickle: {pkl_path}")
            with open(pkl_path, "rb") as f:
                return pickle.load(f)
        
        # Fall back to JSON (may OOM for large files)
        print(f"[LABELS] Loading from JSON: {self.labels_path}")
        if HAS_ORJSON:
            with self.labels_path.open("rb") as handle:
                return orjson.loads(handle.read())
        else:
            with self.labels_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

    def __len__(self) -> int:
        # Handle case where numpy was not yet reloaded after pickle
        if getattr(self, '_numpy_needs_reload', False):
            return getattr(self, '_numpy_length', 0)
        if getattr(self, '_use_numpy', False):
            return len(self._numpy_labels)
        return len(self.labels)

    def __getitem__(self, idx: int):
        # Ensure data is loaded (handles lazy reload after unpickling)
        self._ensure_numpy_loaded()
        self._ensure_consolidated_cache_loaded()
        
        # Get file path and label, supporting both numpy and dict formats
        if getattr(self, '_use_numpy', False):
            # Decode bytes to string if needed
            file_bytes = self._numpy_files[idx]
            if getattr(self, '_files_are_bytes', False):
                file_path = file_bytes.decode('utf-8')
            else:
                file_path = str(file_bytes)
            label = int(self._numpy_labels[idx])
            audio_path = self.data_dir / file_path
        else:
            item = self.labels[idx]
            audio_path = self.data_dir / item["file"]
            label = int(item["component_idx"])

        # If waveform augmentation is enabled, we must recompute spectrograms each time
        # (can't use cached spectrograms since augmentation is stochastic)
        if self.waveform_transform is not None:
            waveform = self._load_audio(audio_path)
            waveform = self.waveform_transform(waveform, self.sr)
            features = self._extract_features(waveform)
            return features.float().contiguous(), label

        # FAST PATH: Consolidated memory-mapped cache (100x faster)
        if self._consolidated_reader is not None:
            # Build relative path for lookup (audio/XX/filename.pt format)
            try:
                relative = audio_path.relative_to(self.data_dir)
            except ValueError:
                relative = Path(audio_path.name)
            cache_key = str(relative.with_suffix(".pt"))
            
            features = self._consolidated_reader.get_by_path(cache_key)
            if features is not None:
                return features.float().contiguous(), label
            elif self._cache_debug:
                print(f"[CONSOLIDATED CACHE MISS] {cache_key}", flush=True)
            # Fall through to individual file cache or recompute

        # Standard path: use individual .pt file cache if available
        features = None
        cache_path: Optional[Path] = None
        if self.cache_dir is not None:
            cache_path = self._cache_path(audio_path)
            if cache_path.exists():
                try:
                    features = torch.load(cache_path, map_location="cpu", weights_only=True)
                    if isinstance(features, torch.Tensor):
                        features = features.to(dtype=torch.float32)
                except Exception:
                    if self._cache_debug:
                        print(f"[CACHE MISS] failed to load cached features: {cache_path}", flush=True)
                    features = None  # Fallback to recompute if cache is corrupt.
            elif self._cache_debug:
                print(f"[CACHE MISS] cache file missing: {cache_path}", flush=True)

        if features is None:
            waveform = self._load_audio(audio_path)
            features = self._extract_features(waveform)
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cached_tensor = features.detach().to(dtype=self._cache_store_dtype, device="cpu")
                torch.save(cached_tensor, cache_path)
                if self._cache_debug:
                    print(f"[CACHE WRITE] stored features: {cache_path}", flush=True)

        return features.float().contiguous(), label

    def _cache_path(self, audio_path: Path) -> Path:
        try:
            relative = audio_path.relative_to(self.data_dir)
        except ValueError:
            relative = Path(audio_path.name)
        cache_file = relative.with_suffix(".pt")
        return (self.cache_dir / cache_file) if self.cache_dir is not None else cache_file

    def _load_audio(self, audio_path: Path) -> torch.Tensor:
        if self._torchaudio_enabled and torchaudio is not None:
            waveform, sample_rate = torchaudio.load(str(audio_path))
            if waveform.size(0) > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            else:
                waveform = waveform[:1]
            if sample_rate != self.sr:
                waveform = ta_F.resample(waveform, sample_rate, self.sr)
            waveform = waveform.squeeze(0)
        else:
            audio, _ = librosa.load(audio_path, sr=self.sr, mono=True)
            waveform = torch.from_numpy(audio)

        if waveform.numel() < self.win_length:
            pad = self.win_length - waveform.numel()
            waveform = F.pad(waveform.unsqueeze(0), (0, pad), mode="constant", value=0.0).squeeze(0)

        return waveform.contiguous().float()

    def _extract_features(self, waveform: torch.Tensor) -> torch.Tensor:
        if self._torchaudio_enabled and self._mel_transform is not None and self._amplitude_to_db is not None:
            mel = self._mel_transform(waveform.unsqueeze(0))
            mel = self._amplitude_to_db(mel)
            mel = mel.squeeze(0)
        else:
            mel_np = librosa.feature.melspectrogram(
                y=waveform.cpu().numpy(),
                sr=self.sr,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                win_length=self.win_length,
                n_mels=self.n_mels,
                fmax=self.fmax,
                center=True,
                pad_mode="reflect",
                power=2.0,
            )
            mel_np = librosa.power_to_db(mel_np, ref=np.max)
            mel = torch.from_numpy(mel_np)

        mel = torch.nan_to_num(mel, nan=0.0, posinf=0.0, neginf=0.0)
        mel = mel.unsqueeze(0)
        mel = F.interpolate(mel, size=self.target_frames, mode="linear", align_corners=False)
        mel = mel.squeeze(0)

        mel_min = mel.amin(dim=-1, keepdim=True)
        mel_max = mel.amax(dim=-1, keepdim=True)
        mel = (mel - mel_min) / (mel_max - mel_min + 1e-8)

        return mel.unsqueeze(0)

    def __getstate__(self) -> dict:
        """
        Prepare state for pickling (required for multiprocessing on Windows).
        
        Excludes large numpy arrays and consolidated cache reader since they cannot
        be efficiently pickled. Workers will reload them on demand.
        """
        state = self.__dict__.copy()
        
        # Mark that numpy data needs to be reloaded (store metadata only)
        if getattr(self, '_use_numpy', False):
            state['_numpy_files'] = None
            state['_numpy_labels'] = None
            state['_numpy_needs_reload'] = True
            # Store the length so __len__ works before reload
            state['_numpy_length'] = len(self._numpy_labels)
        
        # Remove consolidated cache reader - will be re-created in workers
        state['_consolidated_reader'] = None
        state['_consolidated_needs_reload'] = self._consolidated_reader is not None
        
        # Remove unpicklable transforms (will be re-created)
        state['_mel_transform'] = None
        state['_amplitude_to_db'] = None
        
        return state

    def __setstate__(self, state: dict) -> None:
        """
        Restore state after unpickling.
        
        Large data structures are reloaded lazily on first access.
        """
        self.__dict__.update(state)
        
        # Re-create transforms if torchaudio is enabled
        if getattr(self, '_torchaudio_enabled', False) and torchaudio is not None and ta_T is not None:
            self._mel_transform = ta_T.MelSpectrogram(
                sample_rate=self.sr,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                win_length=self.win_length,
                n_mels=self.n_mels,
                f_max=self.fmax,
                pad_mode="reflect",
                power=2.0,
                center=True,
                normalized=False,
            )
            self._amplitude_to_db = ta_T.AmplitudeToDB(stype="power")

    def _ensure_numpy_loaded(self) -> None:
        """Lazily reload numpy arrays after unpickling."""
        if not getattr(self, '_numpy_needs_reload', False):
            return
        
        # Reload from disk
        npy_files_path = self.labels_path.parent / f"{self.labels_path.stem}_files.npy"
        npy_labels_path = self.labels_path.parent / f"{self.labels_path.stem}_labels.npy"
        
        if npy_files_path.exists() and npy_labels_path.exists():
            self._numpy_files = np.load(npy_files_path)
            self._numpy_labels = np.load(npy_labels_path)
            self._files_are_bytes = self._numpy_files.dtype.kind == 'S'
        else:
            raise FileNotFoundError(f"Could not reload numpy labels from {npy_files_path.parent}")
        
        self._numpy_needs_reload = False

    def _ensure_consolidated_cache_loaded(self) -> None:
        """Lazily reload consolidated cache after unpickling."""
        if not getattr(self, '_consolidated_needs_reload', False):
            return
        
        if self.cache_dir is not None and HAS_CONSOLIDATED_CACHE:
            # Check for consolidated cache in cache_dir itself
            consolidated_manifest = self.cache_dir / "manifest.json"
            if consolidated_manifest.exists():
                try:
                    self._consolidated_reader = ConsolidatedCacheReader(self.cache_dir)
                except Exception:
                    self._consolidated_reader = None
            else:
                # Check for consolidated cache in sibling directory
                cache_parent = self.cache_dir.parent
                cache_grandparent = cache_parent.parent
                split_name = self.cache_dir.name
                consolidated_parent = cache_grandparent / f"{cache_parent.name}_consolidated"
                consolidated_alt = consolidated_parent / split_name
                
                if (consolidated_alt / "manifest.json").exists():
                    try:
                        self._consolidated_reader = ConsolidatedCacheReader(consolidated_alt)
                    except Exception:
                        self._consolidated_reader = None
        
        self._consolidated_needs_reload = False


def _normalize_state_dict_keys(state_dict: Dict[str, torch.Tensor]) -> OrderedDict[str, torch.Tensor]:
    """Strip torch.compile's `_orig_mod.` prefix so checkpoints are portable."""

    prefix = "_orig_mod."
    if not any(key.startswith(prefix) for key in state_dict.keys()):
        return OrderedDict(state_dict.items())
    return OrderedDict(
        (key[len(prefix):] if key.startswith(prefix) else key, value) for key, value in state_dict.items()
    )


def compute_class_weights(
    labels: List[Dict[str, Any]],
    num_classes: int,
    strategy: str = "balanced",
    max_weight: float = 10.0,
) -> torch.Tensor:
    """Compute class weights for handling imbalanced datasets.
    
    Args:
        labels: List of label dictionaries with 'component_idx' key
        num_classes: Total number of classes
        strategy: Weight computation strategy:
            - 'balanced': Inverse frequency (can be extreme for rare classes)
            - 'sqrt': Square root of inverse frequency (moderate dampening)
            - 'log': Log-based dampening (better for extreme imbalance)
            - 'effective': Effective number of samples (recommended for extreme imbalance)
        max_weight: Maximum weight cap to prevent instability (default 10.0)
    
    Returns:
        Tensor of shape (num_classes,) with class weights
    """
    from collections import Counter
    
    class_counts = Counter(int(item.get("component_idx", 0)) for item in labels)
    total_samples = len(labels)
    
    weights = torch.ones(num_classes, dtype=torch.float32)
    
    for class_idx in range(num_classes):
        count = class_counts.get(class_idx, 0)
        if count > 0:
            if strategy == "balanced":
                # Inverse frequency: n_samples / (n_classes * n_samples_for_class)
                weights[class_idx] = total_samples / (num_classes * count)
            elif strategy == "sqrt":
                # Square root dampening for less aggressive weighting
                weights[class_idx] = np.sqrt(total_samples / (num_classes * count))
            elif strategy == "log":
                # Log-based dampening - much gentler on extreme imbalance
                # w = log(total/count + 1) which caps naturally
                weights[class_idx] = np.log(total_samples / count + 1)
            elif strategy == "effective":
                # Effective number of samples (from "Class-Balanced Loss" paper)
                # Uses beta = 0.9999 for extreme imbalance scenarios
                beta = 0.9999
                effective_num = (1.0 - beta**count) / (1.0 - beta)
                weights[class_idx] = 1.0 / max(effective_num, 1e-6)
    
    # Normalize so mean weight is 1.0
    weights = weights / weights.mean()
    
    # Cap extreme weights to prevent training instability
    if max_weight > 0:
        original_max = weights.max().item()
        weights = weights.clamp(max=max_weight)
        if original_max > max_weight:
            # Re-normalize after capping
            weights = weights / weights.mean()
            print(f"  Note: Class weights capped from {original_max:.2f} to {max_weight:.2f}")
    
    return weights


def stratified_sample_indices(labels_or_dataset, fraction: float, seed: int) -> List[int]:
    """Create stratified subset indices retaining class balance.
    
    Args:
        labels_or_dataset: Either a list of label dicts or a DrumSampleDataset
        fraction: Fraction of samples to keep (0-1)
        seed: Random seed for reproducibility
    """
    # Handle DrumSampleDataset with numpy labels
    if hasattr(labels_or_dataset, '_use_numpy') and labels_or_dataset._use_numpy:
        label_array = labels_or_dataset._numpy_labels
        n_samples = len(label_array)
        
        if fraction >= 1.0:
            return list(range(n_samples))
        if fraction <= 0.0:
            raise ValueError("fraction must be greater than 0 when creating a subset")
        
        by_class: Dict[int, List[int]] = {}
        for idx in range(n_samples):
            component = int(label_array[idx])
            by_class.setdefault(component, []).append(idx)
    else:
        # Original list-of-dicts path
        labels = labels_or_dataset
        if fraction >= 1.0:
            return list(range(len(labels)))
        if fraction <= 0.0:
            raise ValueError("fraction must be greater than 0 when creating a subset")

        by_class: Dict[int, List[int]] = {}
        for idx, item in enumerate(labels):
            component = int(item.get("component_idx", -1))
            by_class.setdefault(component, []).append(idx)

    rng = random.Random(seed)
    sampled: List[int] = []
    for indices in by_class.values():
        if not indices:
            continue
        take = max(1, int(round(len(indices) * fraction)))
        if take >= len(indices):
            sampled.extend(indices)
        else:
            sampled.extend(rng.sample(indices, take))

    rng.shuffle(sampled)
    return sampled


def extract_main_output(outputs):
    """Extract main classification output, handling deep supervision tuple returns.
    
    Args:
        outputs: Either a tensor (regular model) or tuple of (main_output, aux_outputs) for deep supervision
    
    Returns:
        main_output: The primary classification logits tensor
    """
    if isinstance(outputs, tuple):
        return outputs[0]  # First element is main output
    return outputs


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
    *,
    amp_enabled: bool = False,
    scaler: Optional[GradScaler] = None,
    autocast_dtype: Optional[torch.dtype] = None,
    grad_clip_norm: Optional[float] = None,
    channels_last: bool = False,
    grad_accum_steps: int = 1,
    checkpoint_callback: Optional[Callable[[int, int], None]] = None,
    checkpoint_every_batches: int = 0,
    mixup_fn: Optional[Any] = None,
    specaugment_fn: Optional[Any] = None,
    ema: Optional[Any] = None,
    use_sam: bool = False,
    use_rdrop: bool = False,
    rdrop_criterion: Optional[Any] = None,
    deep_sup_criterion: Optional[Any] = None,
) -> tuple[float, float]:
    """Train for one epoch with optional AMP, mixup, specaugment, EMA, SAM, R-Drop, deep supervision.
    
    Args:
        checkpoint_callback: Optional callback(batch_index, total_batches) for mid-epoch saves
        checkpoint_every_batches: Save checkpoint every N batches (0 disables)
        mixup_fn: Optional MixupCutmix instance for data augmentation
        specaugment_fn: Optional SpecAugment instance for spectrogram augmentation
        ema: Optional ModelEMA instance for exponential moving average
        use_sam: If True, use SAM's two-step optimization (requires SAM optimizer)
        use_rdrop: If True, use R-Drop regularization (two forward passes)
        rdrop_criterion: R-Drop loss function (required if use_rdrop=True)
        deep_sup_criterion: Deep supervision loss wrapper (if model outputs aux heads)
    """

    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    non_blocking = device.type == "cuda"
    accum_steps = max(1, grad_accum_steps)
    total_batches = len(dataloader)

    optimizer.zero_grad(set_to_none=True)

    pbar = tqdm(dataloader, desc="Training")
    for batch_index, (features, labels) in enumerate(pbar, start=1):
        features = features.to(device, non_blocking=non_blocking)
        labels = labels.to(device, non_blocking=non_blocking)
        if channels_last:
            features = features.to(memory_format=torch.channels_last)

        # Apply SpecAugment (time/frequency masking) if enabled
        if specaugment_fn is not None:
            features = specaugment_fn(features)

        # Apply Mixup/CutMix augmentation if enabled
        use_mixup = mixup_fn is not None
        if use_mixup:
            mixup_result = mixup_fn(features, labels)
            features = mixup_result.features
            labels_a, labels_b, lam = mixup_result.labels_a, mixup_result.labels_b, mixup_result.lam
        
        with autocast(device_type=device.type, dtype=autocast_dtype, enabled=amp_enabled):
            if use_rdrop and rdrop_criterion is not None:
                # R-Drop: Two forward passes with different dropout masks
                outputs1 = model(features)
                outputs2 = model(features)
                
                if use_mixup:
                    # Mixed loss for soft labels with R-Drop
                    ce_loss1 = lam * criterion(outputs1, labels_a) + (1 - lam) * criterion(outputs1, labels_b)
                    ce_loss2 = lam * criterion(outputs2, labels_a) + (1 - lam) * criterion(outputs2, labels_b)
                    ce_loss = (ce_loss1 + ce_loss2) / 2
                else:
                    ce_loss1 = criterion(outputs1, labels)
                    ce_loss2 = criterion(outputs2, labels)
                    ce_loss = (ce_loss1 + ce_loss2) / 2
                
                # R-Drop consistency loss (symmetric KL divergence)
                main_out1 = extract_main_output(outputs1)
                main_out2 = extract_main_output(outputs2)
                rdrop_loss = rdrop_criterion.compute_kl_loss(main_out1, main_out2)
                loss = ce_loss + rdrop_loss
                outputs = main_out1  # Use first output for accuracy computation
            else:
                outputs = model(features)
                # Select criterion (deep supervision or regular)
                active_criterion = deep_sup_criterion if deep_sup_criterion is not None else criterion
                if use_mixup:
                    # Mixed loss for soft labels
                    loss = lam * active_criterion(outputs, labels_a) + (1 - lam) * active_criterion(outputs, labels_b)
                else:
                    loss = active_criterion(outputs, labels)
                # Extract main output for accuracy (handles deep supervision tuple)
                outputs = extract_main_output(outputs)
            loss_for_backward = loss / accum_steps

        if amp_enabled and scaler is not None:
            scaler.scale(loss_for_backward).backward()
            should_step = batch_index % accum_steps == 0 or batch_index == total_batches
            if should_step:
                if use_sam:
                    # SAM + AMP: Manual two-step optimization
                    # Step 1: Unscale gradients and move to adversarial point
                    scaler.unscale_(optimizer)
                    if grad_clip_norm is not None:
                        clip_grad_norm_(model.parameters(), grad_clip_norm)
                    optimizer.first_step(zero_grad=True)
                    
                    # Step 2: Compute loss at adversarial point (no scaling needed - manual backward)
                    with autocast(device_type=device.type, dtype=autocast_dtype, enabled=True):
                        if use_rdrop and rdrop_criterion is not None:
                            adv_outputs1 = model(features)
                            adv_outputs2 = model(features)
                            if use_mixup:
                                adv_ce1 = lam * criterion(adv_outputs1, labels_a) + (1 - lam) * criterion(adv_outputs1, labels_b)
                                adv_ce2 = lam * criterion(adv_outputs2, labels_a) + (1 - lam) * criterion(adv_outputs2, labels_b)
                                adv_ce = (adv_ce1 + adv_ce2) / 2
                            else:
                                adv_ce = (criterion(adv_outputs1, labels) + criterion(adv_outputs2, labels)) / 2
                            adv_rdrop = rdrop_criterion.compute_kl_loss(adv_outputs1, adv_outputs2)
                            adv_loss = adv_ce + adv_rdrop
                        elif use_mixup:
                            adv_loss = lam * criterion(model(features), labels_a) + (1 - lam) * criterion(model(features), labels_b)
                        else:
                            adv_loss = criterion(model(features), labels)
                    # Use regular backward for adversarial step (gradients already unscaled)
                    adv_loss.backward()
                    if grad_clip_norm is not None:
                        clip_grad_norm_(model.parameters(), grad_clip_norm)
                    
                    # Step 3: Apply update using adversarial gradients
                    optimizer.second_step(zero_grad=True)
                    scaler.update()
                else:
                    if grad_clip_norm is not None:
                        scaler.unscale_(optimizer)
                        clip_grad_norm_(model.parameters(), grad_clip_norm)
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
                
                # Update EMA after optimizer step
                if ema is not None:
                    ema.update(model)
        else:
            loss_for_backward.backward()
            should_step = batch_index % accum_steps == 0 or batch_index == total_batches
            if should_step:
                if grad_clip_norm is not None:
                    clip_grad_norm_(model.parameters(), grad_clip_norm)
                
                if use_sam:
                    # SAM two-step optimization
                    # Step 1: First step moves to adversarial point
                    optimizer.first_step(zero_grad=True)
                    
                    # Step 2: Compute loss at adversarial point
                    with autocast(device_type=device.type, dtype=autocast_dtype, enabled=amp_enabled):
                        if use_rdrop and rdrop_criterion is not None:
                            adv_outputs1 = model(features)
                            adv_outputs2 = model(features)
                            if use_mixup:
                                adv_ce1 = lam * criterion(adv_outputs1, labels_a) + (1 - lam) * criterion(adv_outputs1, labels_b)
                                adv_ce2 = lam * criterion(adv_outputs2, labels_a) + (1 - lam) * criterion(adv_outputs2, labels_b)
                                adv_ce = (adv_ce1 + adv_ce2) / 2
                            else:
                                adv_ce = (criterion(adv_outputs1, labels) + criterion(adv_outputs2, labels)) / 2
                            adv_rdrop = rdrop_criterion.compute_kl_loss(adv_outputs1, adv_outputs2)
                            adv_loss = adv_ce + adv_rdrop
                        elif use_mixup:
                            adv_loss = lam * criterion(model(features), labels_a) + (1 - lam) * criterion(model(features), labels_b)
                        else:
                            adv_loss = criterion(model(features), labels)
                    adv_loss.backward()
                    
                    # Step 3: Apply update using adversarial gradients
                    optimizer.second_step(zero_grad=True)
                else:
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                
                # Update EMA after optimizer step
                if ema is not None:
                    ema.update(model)

        total_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        # For accuracy calculation, use original labels (not mixed) for fair comparison
        if use_mixup:
            total += labels_a.size(0)
            correct += (lam * (predicted == labels_a).sum().item() + (1 - lam) * (predicted == labels_b).sum().item())
        else:
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

        pbar.set_postfix({"loss": f"{loss.item():.4f}", "acc": f"{100 * correct / max(total, 1):.2f}%"})

        # Mid-epoch checkpoint (protects against crashes during long epochs)
        if checkpoint_callback and checkpoint_every_batches > 0:
            if batch_index % checkpoint_every_batches == 0 and batch_index < total_batches:
                checkpoint_callback(batch_index, total_batches)

    mean_loss = total_loss / max(len(dataloader), 1)
    accuracy = 100 * correct / max(total, 1)
    return mean_loss, accuracy


def validate(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    *,
    amp_enabled: bool = False,
    autocast_dtype: Optional[torch.dtype] = None,
    channels_last: bool = False,
) -> tuple[float, float]:
    """Validate the model with optional AMP."""

    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    non_blocking = device.type == "cuda"

    with torch.no_grad():
        for features, labels in tqdm(dataloader, desc="Validation"):
            features = features.to(device, non_blocking=non_blocking)
            labels = labels.to(device, non_blocking=non_blocking)
            if channels_last:
                features = features.to(memory_format=torch.channels_last)

            with autocast(device_type=device.type, dtype=autocast_dtype, enabled=amp_enabled):
                outputs = model(features)
                # Extract main output for models with deep supervision
                main_outputs = extract_main_output(outputs)
                loss = criterion(main_outputs, labels)

            total_loss += loss.item()
            _, predicted = torch.max(main_outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    mean_loss = total_loss / max(len(dataloader), 1)
    accuracy = 100 * correct / max(total, 1)
    return mean_loss, accuracy


def validate_with_tta(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    num_augmentations: int = 3,
    *,
    amp_enabled: bool = False,
    autocast_dtype: Optional[torch.dtype] = None,
    channels_last: bool = False,
) -> tuple[float, float]:
    """
    Validate the model with Test-Time Augmentation (TTA).
    
    Applies multiple augmented views of each sample and averages predictions
    for more robust accuracy estimation during training.
    
    Augmentations used:
    - Time shift (roll along time axis)
    - Frequency masking (mask random frequency bands)
    - Amplitude scaling (slight volume changes)
    
    Args:
        model: Model to evaluate
        dataloader: Validation data loader
        criterion: Loss criterion
        device: Device to run on
        num_augmentations: Number of augmented views per sample (default: 3)
        amp_enabled: Use automatic mixed precision
        autocast_dtype: AMP dtype
        channels_last: Use channels-last memory format
        
    Returns:
        (mean_loss, accuracy) with TTA
    """
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    non_blocking = device.type == "cuda"

    with torch.no_grad():
        for features, labels in tqdm(dataloader, desc="Validation (TTA)"):
            features = features.to(device, non_blocking=non_blocking)
            labels = labels.to(device, non_blocking=non_blocking)
            if channels_last:
                features = features.to(memory_format=torch.channels_last)
            
            # Collect predictions from original and augmented views
            all_logits = []
            
            with autocast(device_type=device.type, dtype=autocast_dtype, enabled=amp_enabled):
                # Original view
                outputs = model(features)
                main_outputs = extract_main_output(outputs)
                all_logits.append(main_outputs)
                
                # Augmented views
                for aug_idx in range(num_augmentations):
                    aug_features = apply_tta_augmentation(features, aug_idx)
                    if channels_last:
                        aug_features = aug_features.to(memory_format=torch.channels_last)
                    outputs = model(aug_features)
                    main_outputs = extract_main_output(outputs)
                    all_logits.append(main_outputs)
            
            # Average predictions (in probability space for better calibration)
            avg_probs = torch.stack([F.softmax(logits, dim=1) for logits in all_logits]).mean(dim=0)
            avg_logits = torch.log(avg_probs + 1e-8)  # Convert back to log-space for loss
            
            # Compute loss on averaged predictions
            loss = criterion(avg_logits, labels)
            total_loss += loss.item()
            
            # Accuracy from averaged predictions
            _, predicted = torch.max(avg_probs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    mean_loss = total_loss / max(len(dataloader), 1)
    accuracy = 100 * correct / max(total, 1)
    return mean_loss, accuracy


def apply_tta_augmentation(features: torch.Tensor, aug_idx: int) -> torch.Tensor:
    """
    Apply TTA augmentation to spectrogram features.
    
    Augmentation types cycle based on aug_idx:
    - 0: Time shift (roll along time axis)
    - 1: Frequency masking (mask random frequency bands)
    - 2: Amplitude scaling
    - 3+: Combinations
    
    Args:
        features: Input features [B, C, H, W] (spectrogram)
        aug_idx: Augmentation index to determine which transform
        
    Returns:
        Augmented features
    """
    B, C, H, W = features.shape
    aug_type = aug_idx % 3
    
    if aug_type == 0:
        # Time shift: roll along time axis (W dimension)
        # Shift by 5-15% of width
        shift = int(W * (0.05 + 0.1 * (aug_idx // 3) / max(1, aug_idx // 3 + 1)))
        shift = max(1, min(shift, W // 4))
        # Randomly choose direction
        if aug_idx % 2 == 0:
            shift = -shift
        return torch.roll(features, shifts=shift, dims=3)
    
    elif aug_type == 1:
        # Frequency masking: mask 1-3 frequency bands
        aug_features = features.clone()
        num_masks = 1 + (aug_idx // 3) % 3
        for _ in range(num_masks):
            mask_height = max(1, int(H * 0.1))  # 10% of height
            mask_start = torch.randint(0, max(1, H - mask_height), (1,)).item()
            aug_features[:, :, mask_start:mask_start + mask_height, :] *= 0.1
        return aug_features
    
    else:  # aug_type == 2
        # Amplitude scaling: slight volume change
        # Scale between 0.9 and 1.1
        scale = 0.9 + 0.2 * ((aug_idx + 1) % 5) / 4
        return features * scale


def main():
    parser = argparse.ArgumentParser(description="Train Drum Classifier CNN")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=default_dataset_root(),
        help=(
            "Path to dataset directory (defaults to BEATSIGHT_DATASET_DIR or "
            "BEATSIGHT_DATA_ROOT/prod_combined_profile_run)"
        ),
    )
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--output", default="models", help="Output directory for models")
    parser.add_argument("--device", default=None, help="Device (cuda/cpu)")
    parser.add_argument(
        "--metrics-json",
        type=Path,
        help="Optional path to write training metrics as JSON",
    )
    parser.add_argument(
        "--scheduler",
        choices=["plateau", "cosine"],
        default="plateau",
        help="Learning rate scheduler (default: plateau)",
    )
    parser.add_argument(
        "--warmup-epochs",
        type=int,
        default=0,
        help="Number of warm-up epochs with linear LR ramp (default: 0)",
    )
    parser.add_argument(
        "--min-lr",
        type=float,
        default=None,
        help="Minimum LR for cosine scheduler (default: 10%% of base LR)",
    )
    parser.add_argument(
        "--wandb-project",
        help="Weights & Biases project name (enables W&B logging when set)",
    )
    parser.add_argument(
        "--wandb-entity",
        help="Optional Weights & Biases entity (team/user)",
    )
    parser.add_argument(
        "--wandb-run-name",
        help="Optional custom name for the W&B run",
    )
    parser.add_argument(
        "--wandb-tags",
        nargs="*",
        help="Optional list of W&B tags (space separated)",
    )
    parser.add_argument(
        "--wandb-mode",
        choices=["online", "offline", "disabled"],
        default=None,
        help="Override W&B mode (default respects WANDB_MODE env or online)",
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        help="Path to a saved training checkpoint to resume from",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=0,
        help="Save a training checkpoint every N epochs (0 disables mid-run checkpoints)",
    )
    parser.add_argument(
        "--checkpoint-every-batches",
        type=int,
        default=0,
        help="Save a mid-epoch checkpoint every N batches (0 disables; recommended: 10000-50000 for long epochs)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        help="Directory for training checkpoints (defaults to <output>/checkpoints)",
    )
    parser.add_argument("--sample-rate", type=int, default=44100, help="Audio sample rate expected by the dataset")
    parser.add_argument("--n-fft", type=int, default=2048, help="FFT window size for mel conversion")
    parser.add_argument("--hop-length", type=int, default=512, help="Hop length for mel spectrogram frames")
    parser.add_argument("--n-mels", type=int, default=128, help="Number of mel bins to compute")
    parser.add_argument("--fmax", type=int, default=8000, help="Maximum mel frequency (Hz)")
    parser.add_argument("--target-frames", type=int, default=128, help="Number of spectrogram frames after resizing")
    parser.add_argument(
            "--feature-cache-dir",
            type=Path,
            default=None,
            help=(
                "Optional root directory to cache precomputed features (defaults to "
                "BEATSIGHT_CACHE_DIR or BEATSIGHT_DATA_ROOT/feature_cache/prod_combined_warmup)"
            ),
        )
    parser.add_argument(
        "--cache-dtype",
        choices=["float32", "float16", "bfloat16"],
        default="float32",
        help="Data type used when persisting cached spectrograms (float16 reduces disk usage by ~2x)",
    )
    parser.add_argument(
        "--labels-cache-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory containing cached label JSON files (train_labels.json, val_labels.json). "
            "Use this to read labels from a fast SSD when dataset is on a slow HDD."
        ),
    )
    parser.add_argument("--num-workers", type=int, help="DataLoader worker processes for training")
    parser.add_argument("--val-num-workers", type=int, help="DataLoader worker processes for validation")
    parser.add_argument("--prefetch-factor", type=int, help="Samples prefetched per worker for training")
    parser.add_argument("--val-prefetch-factor", type=int, help="Samples prefetched per worker for validation")
    parser.add_argument(
        "--persistent-workers",
        action="store_true",
        help="Keep DataLoader workers alive between epochs (requires num-workers > 0)",
    )
    parser.add_argument("--train-fraction", type=float, default=1.0, help="Fraction of the training set to sample (stratified)")
    parser.add_argument("--val-fraction", type=float, default=1.0, help="Fraction of the validation set to sample (stratified)")
    parser.add_argument("--subset-seed", type=int, default=42, help="RNG seed used for subset selection")
    parser.add_argument(
        "--no-torchaudio",
        action="store_true",
        help="Force fallback to librosa even if torchaudio is available",
    )
    parser.add_argument(
        "--disable-amp",
        action="store_true",
        help="Disable automatic mixed precision even when CUDA is available",
    )
    parser.add_argument(
        "--amp-dtype",
        choices=["float16", "bfloat16"],
        default="float16",
        help="Preferred dtype for autocast when AMP is enabled",
    )
    parser.add_argument(
        "--pin-memory",
        dest="pin_memory",
        action="store_true",
        help="Force DataLoader pin_memory to True",
    )
    parser.add_argument(
        "--no-pin-memory",
        dest="pin_memory",
        action="store_false",
        help="Force DataLoader pin_memory to False",
    )
    parser.set_defaults(pin_memory=None)
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Force deterministic algorithms (may reduce throughput)",
    )
    parser.add_argument(
        "--grad-clip-norm",
        type=float,
        help="Max norm for gradient clipping (disabled when omitted)",
    )
    parser.add_argument(
        "--grad-accum-steps",
        type=int,
        default=1,
        help="Accumulate gradients over N mini-batches before an optimizer step",
    )
    parser.add_argument(
        "--weight-decay",
        type=float,
        default=0.0,
        help="Weight decay to apply via Adam optimizer",
    )
    parser.add_argument(
        "--channels-last",
        action="store_true",
        help="Use channels-last memory format for model and batches",
    )
    parser.add_argument(
        "--torch-compile",
        action="store_true",
        help="Compile the model with torch.compile (PyTorch 2.x)",
    )
    parser.add_argument(
        "--torch-compile-mode",
        choices=["default", "reduce-overhead", "max-autotune"],
        default="default",
        help="torch.compile mode when enabled (default/reduce-overhead/max-autotune)",
    )
    parser.add_argument(
        "--class-weights",
        choices=["none", "balanced", "sqrt", "log", "effective"],
        default="none",
        help="Class weighting strategy: none (default), balanced (inverse frequency - can be unstable), "
             "sqrt (sqrt of inverse), log (log-based dampening), effective (recommended for extreme imbalance)",
    )
    parser.add_argument(
        "--max-class-weight",
        type=float,
        default=10.0,
        help="Maximum class weight cap to prevent training instability (default: 10.0, 0 to disable)",
    )
    parser.add_argument(
        "--label-smoothing",
        type=float,
        default=0.0,
        help="Label smoothing factor for cross-entropy loss (0.0-0.2 typical)",
    )
    
    # === CUTTING-EDGE FEATURES ===
    parser.add_argument(
        "--model-version",
        choices=["v1", "v2", "v3", "v4", "v5", "beats"],
        default="v1",
        help="Model architecture: v1 (baseline), v2 (SE), v3 (CBAM), v4 (CoordAttn), v5 (Ultimate), beats (BEATs foundation)",
    )
    parser.add_argument(
        "--use-se",
        action="store_true",
        help="Enable Squeeze-Excitation attention blocks (only for v2 model)",
    )
    parser.add_argument(
        "--use-cbam",
        action="store_true",
        help="Enable CBAM attention blocks (only for v3 model, default True for v3)",
    )
    parser.add_argument(
        "--use-coord-attention",
        action="store_true",
        help="Enable Coordinate Attention (only for v4 model, default True for v4)",
    )
    parser.add_argument(
        "--use-multi-task",
        action="store_true",
        help="Enable multi-task heads for velocity and hi-hat openness (v4 only)",
    )
    parser.add_argument(
        "--velocity-weight",
        type=float,
        default=0.1,
        help="Weight for velocity prediction auxiliary loss (default: 0.1)",
    )
    parser.add_argument(
        "--openness-weight",
        type=float,
        default=0.1,
        help="Weight for hi-hat openness prediction auxiliary loss (default: 0.1)",
    )
    parser.add_argument(
        "--width-mult",
        type=float,
        default=1.0,
        help="Channel width multiplier for v2 model (1.0 = base, 1.5 = 50%% wider)",
    )
    parser.add_argument(
        "--mixup-alpha",
        type=float,
        default=0.0,
        help="Mixup alpha parameter (0 to disable, 0.2-0.4 typical for regularization)",
    )
    parser.add_argument(
        "--cutmix-alpha",
        type=float,
        default=0.0,
        help="CutMix alpha parameter (0 to disable, 1.0 typical)",
    )
    parser.add_argument(
        "--mixup-prob",
        type=float,
        default=0.5,
        help="Probability of applying mixup/cutmix per batch (default: 0.5)",
    )
    
    # SpecAugment arguments
    parser.add_argument(
        "--specaugment",
        type=str,
        default="none",
        choices=["none", "light", "default", "strong", "drum"],
        help="SpecAugment preset (none=disabled, drum=optimized for drums)",
    )
    parser.add_argument(
        "--specaugment-freq-masks",
        type=int,
        default=2,
        help="Number of frequency masks for SpecAugment (default: 2)",
    )
    parser.add_argument(
        "--specaugment-time-masks",
        type=int,
        default=2,
        help="Number of time masks for SpecAugment (default: 2)",
    )
    
    # FMix (Fourier-domain Mixup) arguments
    parser.add_argument(
        "--use-fmix",
        action="store_true",
        help="Use FMix (Fourier-domain mixup) augmentation instead of standard Mixup",
    )
    parser.add_argument(
        "--fmix-alpha",
        type=float,
        default=1.0,
        help="FMix alpha parameter for Beta distribution (default: 1.0)",
    )
    parser.add_argument(
        "--fmix-decay",
        type=float,
        default=3.0,
        help="FMix decay power for mask generation (default: 3.0)",
    )
    parser.add_argument(
        "--fmix-with-cutmix",
        action="store_true",
        help="Combine FMix with CutMix in random selection",
    )
    
    # Waveform Augmentation (audio-level augmentation before spectrogram)
    parser.add_argument(
        "--waveform-augment",
        type=str,
        default="none",
        choices=["none", "light", "drum", "heavy", "fast"],
        help="Waveform augmentation preset: none, light, drum (recommended), heavy, fast (no time stretch)",
    )
    parser.add_argument(
        "--waveform-time-stretch",
        type=float,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=[0.95, 1.05],
        help="Time stretch range (default: 0.95 1.05 = ±5%%)",
    )
    parser.add_argument(
        "--waveform-pitch-shift",
        type=float,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=[-2.0, 2.0],
        help="Pitch shift range in semitones (default: -2 2 = ±2 semitones)",
    )
    parser.add_argument(
        "--waveform-gain-db",
        type=float,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=[-4.0, 4.0],
        help="Gain variation range in dB (default: -4 4 = ±4 dB)",
    )
    
    # Confident Learning (label noise detection)
    parser.add_argument(
        "--clean-labels",
        action="store_true",
        help="Run confident learning to detect and filter label noise before training",
    )
    parser.add_argument(
        "--label-noise-threshold",
        type=float,
        default=0.5,
        help="Threshold for detecting label noise (default: 0.5, lower=more aggressive filtering)",
    )
    parser.add_argument(
        "--label-noise-audit-only",
        action="store_true",
        help="Only audit labels without filtering (prints report)",
    )
    
    # Self-Training
    parser.add_argument(
        "--use-self-training",
        action="store_true",
        help="Use self-training with pseudo-labels from unlabeled data",
    )
    parser.add_argument(
        "--unlabeled-dir",
        type=Path,
        default=None,
        help="Directory containing unlabeled audio samples for self-training",
    )
    parser.add_argument(
        "--pseudo-label-threshold",
        type=float,
        default=0.9,
        help="Confidence threshold for pseudo-label generation (default: 0.9)",
    )
    parser.add_argument(
        "--self-training-epochs",
        type=int,
        default=3,
        help="Number of self-training iterations (default: 3)",
    )
    
    # Focal Loss arguments
    parser.add_argument(
        "--focal-loss",
        action="store_true",
        help="Use Focal Loss instead of Cross-Entropy (better for imbalanced classes)",
    )
    parser.add_argument(
        "--focal-gamma",
        type=float,
        default=2.0,
        help="Focal loss gamma (focusing parameter, higher=more focus on hard examples)",
    )
    
    # EMA arguments
    parser.add_argument(
        "--use-ema",
        action="store_true",
        help="Use Exponential Moving Average of weights (improves final model)",
    )
    parser.add_argument(
        "--ema-decay",
        type=float,
        default=0.999,
        help="EMA decay rate (default: 0.999, higher=more smoothing)",
    )
    parser.add_argument(
        "--ema-warmup-steps",
        type=int,
        default=0,
        help="EMA warmup steps (linear warmup from 0.5 to target decay)",
    )
    
    # Progressive/Adaptive augmentation
    parser.add_argument(
        "--progressive-augmentation",
        action="store_true",
        help="Enable progressive augmentation (start weak, ramp up strength during training)",
    )
    
    # SAM (Sharpness-Aware Minimization) optimizer
    parser.add_argument(
        "--use-sam",
        action="store_true",
        help="Use SAM optimizer for better generalization (seeks flat minima)",
    )
    parser.add_argument(
        "--sam-rho",
        type=float,
        default=0.05,
        help="SAM neighborhood size for perturbation (default: 0.05, higher=more regularization)",
    )
    parser.add_argument(
        "--sam-adaptive",
        action="store_true",
        help="Use Adaptive SAM which normalizes perturbations per-parameter",
    )
    
    # SWA (Stochastic Weight Averaging)
    parser.add_argument(
        "--use-swa",
        action="store_true",
        help="Use Stochastic Weight Averaging in the final training phase",
    )
    parser.add_argument(
        "--swa-start",
        type=float,
        default=0.75,
        help="When to start SWA (fraction of total training, default: 0.75 = last 25%%)",
    )
    parser.add_argument(
        "--swa-lr",
        type=float,
        default=None,
        help="Learning rate for SWA phase (default: 10%% of base LR)",
    )
    
    # R-Drop (Regularized Dropout)
    parser.add_argument(
        "--use-rdrop",
        action="store_true",
        help="Use R-Drop regularization (two forward passes with consistency loss)",
    )
    parser.add_argument(
        "--rdrop-alpha",
        type=float,
        default=0.5,
        help="R-Drop consistency loss weight (default: 0.5, higher=stronger regularization)",
    )
    
    # Curriculum Learning
    parser.add_argument(
        "--use-curriculum",
        action="store_true",
        help="Use curriculum learning (easy-to-hard training progression)",
    )
    parser.add_argument(
        "--curriculum-start-fraction",
        type=float,
        default=0.4,
        help="Initial fraction of easiest samples to train on (default: 0.4)",
    )
    parser.add_argument(
        "--curriculum-strategy",
        choices=["linear", "cosine", "exponential", "step"],
        default="cosine",
        help="Curriculum progression strategy (default: cosine)",
    )
    
    # Temperature Calibration
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Perform temperature scaling calibration after training",
    )
    parser.add_argument(
        "--calibration-method",
        choices=["temperature", "vector"],
        default="temperature",
        help="Calibration method: temperature (single param) or vector (per-class)",
    )
    
    # === NEW CUTTING-EDGE FEATURES (2024) ===
    
    # Gradient Centralization
    parser.add_argument(
        "--use-gradient-centralization",
        action="store_true",
        help="Apply Gradient Centralization to optimizer (improves generalization +0.5-1%%)",
    )
    
    # Deep Supervision
    parser.add_argument(
        "--use-deep-supervision",
        action="store_true",
        help="Enable deep supervision (auxiliary losses at intermediate layers)",
    )
    parser.add_argument(
        "--deep-supervision-weights",
        type=str,
        default="0.4,0.6",
        help="Comma-separated weights for intermediate auxiliary losses (default: '0.4,0.6')",
    )
    
    # V5 Model-specific
    parser.add_argument(
        "--v5-size",
        choices=["small", "medium", "large"],
        default="medium",
        help="CNN v5 model size variant (default: medium)",
    )
    parser.add_argument(
        "--drop-path-rate",
        type=float,
        default=0.1,
        help="Stochastic depth drop path rate for v5 model (default: 0.1)",
    )
    
    # BEATs-specific
    parser.add_argument(
        "--beats-freeze-encoder",
        action="store_true",
        help="Freeze the BEATs encoder weights (fine-tune only classification head)",
    )
    parser.add_argument(
        "--beats-layer-decay",
        type=float,
        default=0.75,
        help="Layer-wise learning rate decay for BEATs (default: 0.75, lower=more decay)",
    )
    
    # V5 Advanced Pooling (Option A enhancement: +0.3-0.5%)
    parser.add_argument(
        "--pooling-type",
        choices=["gap", "asp", "mha", "hybrid"],
        default="gap",
        help="Pooling strategy for v5 model: gap (global average), asp (attentive statistics), mha (multi-head attention), hybrid (default: gap)",
    )
    
    # Hard Negative Mining (Option A enhancement: +0.5-1%)
    parser.add_argument(
        "--use-hard-negatives",
        action="store_true",
        help="Enable hard negative mining to focus on confusing sample pairs",
    )
    parser.add_argument(
        "--hnm-strategy",
        choices=["ohem", "semi_hard", "curriculum"],
        default="curriculum",
        help="Hard negative mining strategy (default: curriculum)",
    )
    parser.add_argument(
        "--hnm-ratio",
        type=float,
        default=0.7,
        help="OHEM: keep top N%% hardest samples per batch (default: 0.7)",
    )
    parser.add_argument(
        "--hnm-confusion-weight",
        type=float,
        default=2.0,
        help="Extra weight for commonly confused class pairs (default: 2.0)",
    )
    parser.add_argument(
        "--hnm-use-contrastive",
        action="store_true",
        help="Add contrastive loss to push embeddings apart in feature space (+0.3-0.5%% improvement)",
    )
    parser.add_argument(
        "--hnm-margin",
        type=float,
        default=0.5,
        help="Margin for contrastive loss (default: 0.5)",
    )
    parser.add_argument(
        "--hnm-contrastive-weight",
        type=float,
        default=0.3,
        help="Weight for contrastive loss term (default: 0.3)",
    )
    
    # Lookahead Optimizer (Zhang et al., NeurIPS 2019 - smoother optimization)
    parser.add_argument(
        "--use-lookahead",
        action="store_true",
        help="Wrap optimizer with Lookahead for smoother convergence (+0.5-1%% improvement)",
    )
    parser.add_argument(
        "--lookahead-k",
        type=int,
        default=5,
        help="Lookahead: number of fast steps before slow update (default: 5)",
    )
    parser.add_argument(
        "--lookahead-alpha",
        type=float,
        default=0.5,
        help="Lookahead: interpolation coefficient for slow update (default: 0.5)",
    )
    
    # Mixup Cutoff (disable mixup in final training phase for cleaner decision boundaries)
    parser.add_argument(
        "--mixup-cutoff-ratio",
        type=float,
        default=1.0,
        help="Disable mixup after this fraction of training (default: 1.0 = never, 0.85 = disable in final 15%%)",
    )
    
    # Warmup LR Factor (controls initial learning rate during warmup)
    parser.add_argument(
        "--warmup-lr-factor",
        type=float,
        default=0.1,
        help="Initial LR multiplier during warmup phase (default: 0.1 = start at 10%% of base LR)",
    )
    
    # Test-Time Augmentation for Validation (more accurate quality estimate)
    parser.add_argument(
        "--val-tta",
        action="store_true",
        help="Use Test-Time Augmentation during validation for more accurate quality estimates",
    )
    parser.add_argument(
        "--val-tta-augmentations",
        type=int,
        default=3,
        help="Number of augmented views per sample during TTA validation (default: 3)",
    )
    
    args = parser.parse_args()

    args.dataset = Path(args.dataset).expanduser().resolve()

    if args.feature_cache_dir is None:
        args.feature_cache_dir = default_feature_cache_root()
    else:
        args.feature_cache_dir = Path(args.feature_cache_dir).expanduser().resolve()
    
    if args.warmup_epochs < 0:
        parser.error("--warmup-epochs must be non-negative")
    if args.warmup_epochs >= args.epochs:
        parser.error("--warmup-epochs must be less than total epochs")
    if args.checkpoint_every < 0:
        parser.error("--checkpoint-every must be non-negative")
    if not (0 < args.train_fraction <= 1.0):
        parser.error("--train-fraction must be in the range (0, 1]")
    if not (0 < args.val_fraction <= 1.0):
        parser.error("--val-fraction must be in the range (0, 1]")
    if args.prefetch_factor is not None and args.prefetch_factor <= 0:
        parser.error("--prefetch-factor must be positive when provided")
    if args.val_prefetch_factor is not None and args.val_prefetch_factor <= 0:
        parser.error("--val-prefetch-factor must be positive when provided")
    if args.n_fft <= 0:
        parser.error("--n-fft must be positive")
    if args.hop_length <= 0:
        parser.error("--hop-length must be positive")
    if args.n_mels <= 0:
        parser.error("--n-mels must be positive")
    if args.target_frames <= 0:
        parser.error("--target-frames must be positive")
    if args.grad_clip_norm is not None and args.grad_clip_norm <= 0:
        parser.error("--grad-clip-norm must be positive when provided")
    if args.grad_accum_steps <= 0:
        parser.error("--grad-accum-steps must be positive")
    if args.weight_decay < 0:
        parser.error("--weight-decay must be non-negative")

    # Setup device
    device = args.device or ('cuda' if torch.cuda.is_available() else 'cpu')
    torch_device = torch.device(device)

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        if torch_device.type == "cuda":
            torch.cuda.manual_seed_all(args.seed)

    if args.deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        if hasattr(torch, "use_deterministic_algorithms"):
            torch.use_deterministic_algorithms(True, warn_only=False)
        torch.backends.cudnn.deterministic = True  # type: ignore[attr-defined]
        torch.backends.cudnn.benchmark = False
    elif torch_device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    print(f"Using device: {device}")

    if torch_device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        if hasattr(torch, "set_float32_matmul_precision"):
            torch.set_float32_matmul_precision("high")
    
    # Load datasets
    dataset_path = Path(args.dataset)

    def resolve_labels(split: str, filename: str) -> Path:
        """Locate the label JSON, supporting labels-cache-dir, flat, and split-local layouts."""
        # First check labels-cache-dir (for fast SSD when dataset is on slow HDD)
        if args.labels_cache_dir:
            cached = args.labels_cache_dir / filename
            if cached.exists():
                print(f"[LABELS] Using cached labels from fast storage: {cached}")
                return cached
        # Then check flat layout
        candidate = dataset_path / filename
        if candidate.exists():
            return candidate
        # Finally check split-local layout
        nested = dataset_path / split / filename
        if nested.exists():
            return nested
        raise FileNotFoundError(f"Missing label file for {split}: tried '{candidate}' and '{nested}'")

    fmax = None if args.fmax is not None and args.fmax <= 0 else args.fmax
    feature_cache_root = args.feature_cache_dir
    if feature_cache_root and not feature_cache_root.exists():
        feature_cache_root.mkdir(parents=True, exist_ok=True)
    prefer_torchaudio = not args.no_torchaudio

    # Setup waveform augmentation (audio-level augmentation before spectrogram)
    waveform_transform = None
    if args.waveform_augment != "none" and HAS_WAVEFORM_AUGMENT:
        use_fast = (args.waveform_augment == "fast")
        preset = "drum" if use_fast else args.waveform_augment
        waveform_transform = get_waveform_augment(
            preset=preset,
            fast=use_fast,
        )
        print(f"[WAVEFORM AUGMENT] Using '{args.waveform_augment}' preset (disables feature caching for training)")
    elif args.waveform_augment != "none" and not HAS_WAVEFORM_AUGMENT:
        print(f"[WARNING] Waveform augmentation requested but librosa not available. Skipping.")

    train_dataset_full = DrumSampleDataset(
        dataset_path / "train",
        resolve_labels("train", "train_labels.json"),
        sr=args.sample_rate,
        cache_dir=feature_cache_root / "train" if feature_cache_root else None,
        prefer_torchaudio=prefer_torchaudio,
        n_fft=args.n_fft,
        hop_length=args.hop_length,
        n_mels=args.n_mels,
        fmax=fmax,
        target_frames=args.target_frames,
        cache_dtype=args.cache_dtype,
        waveform_transform=waveform_transform,  # Apply augmentation to training data
    )
    val_dataset_full = DrumSampleDataset(
        dataset_path / "val",
        resolve_labels("val", "val_labels.json"),
        sr=args.sample_rate,
        cache_dir=feature_cache_root / "val" if feature_cache_root else None,
        prefer_torchaudio=prefer_torchaudio,
        n_fft=args.n_fft,
        hop_length=args.hop_length,
        n_mels=args.n_mels,
        fmax=fmax,
        target_frames=args.target_frames,
        cache_dtype=args.cache_dtype,
    )

    train_subset_indices = None
    if args.train_fraction < 1.0:
        train_subset_indices = stratified_sample_indices(train_dataset_full, args.train_fraction, args.subset_seed)
        train_dataset = Subset(train_dataset_full, train_subset_indices)
    else:
        train_dataset = train_dataset_full

    val_subset_indices = None
    if args.val_fraction < 1.0:
        val_subset_indices = stratified_sample_indices(val_dataset_full, args.val_fraction, args.subset_seed)
        val_dataset = Subset(val_dataset_full, val_subset_indices)
    else:
        val_dataset = val_dataset_full

    print(
        f"Training samples: {len(train_dataset)}"
        + (f" (subset of {len(train_dataset_full)})" if train_subset_indices is not None else "")
    )
    print(
        f"Validation samples: {len(val_dataset)}"
        + (f" (subset of {len(val_dataset_full)})" if val_subset_indices is not None else "")
    )

    cpu_count = os.cpu_count() or 1
    default_workers = 0
    if torch_device.type == "cuda":
        default_workers = max(2, min(8, cpu_count // 2)) if cpu_count > 1 else 0

    num_workers = args.num_workers if args.num_workers is not None else default_workers
    val_num_workers = args.val_num_workers if args.val_num_workers is not None else max(0, num_workers // 2)

    if num_workers < 0:
        parser.error("--num-workers must be non-negative")
    if val_num_workers < 0:
        parser.error("--val-num-workers must be non-negative")

    pin_memory_auto = torch_device.type == "cuda"
    pin_memory = pin_memory_auto if args.pin_memory is None else bool(args.pin_memory)
    train_persistent = bool(args.persistent_workers and num_workers > 0)
    val_persistent = bool(args.persistent_workers and val_num_workers > 0)

    def build_loader(
        dataset_obj,
        *,
        batch_size: int,
        shuffle: bool,
        workers: int,
        prefetch: Optional[int],
        persistent: bool,
    ) -> DataLoader:
        loader_kwargs: Dict[str, Any] = {
            "dataset": dataset_obj,
            "batch_size": batch_size,
            "shuffle": shuffle,
            "num_workers": workers,
            "drop_last": False,
            "pin_memory": pin_memory and torch_device.type == "cuda",
        }
        if workers > 0:
            if prefetch is not None:
                loader_kwargs["prefetch_factor"] = prefetch
            if persistent:
                loader_kwargs["persistent_workers"] = True
        else:
            loader_kwargs["num_workers"] = 0
        return DataLoader(**loader_kwargs)

    train_prefetch = args.prefetch_factor if args.prefetch_factor is not None else None
    val_prefetch = args.val_prefetch_factor if args.val_prefetch_factor is not None else None

    train_loader = build_loader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        workers=num_workers,
        prefetch=train_prefetch,
        persistent=train_persistent,
    )
    val_loader = build_loader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        workers=val_num_workers,
        prefetch=val_prefetch,
        persistent=val_persistent,
    )
    
    # Load component info
    with open(dataset_path / "components.json", 'r') as f:
        components_info = json.load(f)
    num_classes = components_info['num_classes']
    
    # Initialize model (v1 baseline, v2 with SE, v3 with CBAM, v4 with CoordAttn, v5 Ultimate, or BEATs)
    # Multi-task now supported for v4 AND v5
    use_multi_task = args.use_multi_task and args.model_version in ("v4", "v5")
    
    if args.model_version == "beats":
        if not HAS_BEATS:
            raise SystemExit("BEATs model requested but beats.py not found. Use --model-version v1/v2/v3/v4/v5.")
        model = BEATsDrumClassifier(
            num_classes=num_classes,
            freeze_encoder=args.beats_freeze_encoder,
            use_deep_supervision=args.use_deep_supervision,
        )
        param_count = sum(p.numel() for p in model.parameters())
        trainable_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"Using BEATs model (freeze={args.beats_freeze_encoder}): {param_count:,} params ({trainable_count:,} trainable)")
    elif args.model_version == "v5":
        if not HAS_V5_MODEL:
            raise SystemExit("v5 model requested but cnn_v5.py not found. Use --model-version v1/v2/v3/v4.")
        # Select v5 size variant - now with multi-task support and advanced pooling
        pooling_type = getattr(args, 'pooling_type', 'gap')
        if args.v5_size == "small":
            model = cnn_v5_small(
                num_classes=num_classes,
                drop_path_rate=args.drop_path_rate,
                use_deep_supervision=args.use_deep_supervision,
                use_multi_task=use_multi_task,
                pooling_type=pooling_type,
            )
        elif args.v5_size == "large":
            model = cnn_v5_large(
                num_classes=num_classes,
                drop_path_rate=args.drop_path_rate,
                use_deep_supervision=args.use_deep_supervision,
                use_multi_task=use_multi_task,
                pooling_type=pooling_type,
            )
        else:  # medium (default)
            model = cnn_v5_medium(
                num_classes=num_classes,
                drop_path_rate=args.drop_path_rate,
                use_deep_supervision=args.use_deep_supervision,
                use_multi_task=use_multi_task,
                pooling_type=pooling_type,
            )
        param_count = sum(p.numel() for p in model.parameters())
        pooling_str = f", pooling={pooling_type}" if pooling_type != 'gap' else ""
        print(f"Using v5 ULTIMATE model (size={args.v5_size}, drop_path={args.drop_path_rate}, deep_sup={args.use_deep_supervision}, multi_task={use_multi_task}{pooling_str}): {param_count:,} params")
    elif args.model_version == "v4":
        if not HAS_V4_MODEL:
            raise SystemExit("v4 model requested but coord_attention.py not found. Use --model-version v1/v2/v3.")
        model = DrumClassifierCNNv4(
            num_classes=num_classes,
            use_coord_attention=args.use_coord_attention or True,  # Default True for v4
            use_multi_task=use_multi_task,
            width_mult=args.width_mult,
        )
        param_count = sum(p.numel() for p in model.parameters())
        print(f"Using v4 model (CoordAttn=True, MultiTask={use_multi_task}, width={args.width_mult}x): {param_count:,} parameters")
    elif args.model_version == "v3":
        if not HAS_V3_MODEL:
            raise SystemExit("v3 model requested but cbam.py not found. Use --model-version v1 or v2.")
        model = DrumClassifierCNNv3(
            num_classes=num_classes,
            use_cbam=args.use_cbam or True,  # Default True for v3
            width_mult=args.width_mult,
        )
        param_count = sum(p.numel() for p in model.parameters())
        print(f"Using v3 model (CBAM=True, width={args.width_mult}x): {param_count:,} parameters")
    elif args.model_version == "v2":
        if not HAS_V2_MODEL:
            raise SystemExit("v2 model requested but ml_drum_classifier_v2.py not found. Use --model-version v1 or install the module.")
        use_se = args.use_se
        width_mult = args.width_mult
        model = DrumClassifierCNNv2(
            num_classes=num_classes,
            use_se=use_se,
            width_mult=width_mult,
        )
        param_count = sum(p.numel() for p in model.parameters())
        print(f"Using v2 model (SE={use_se}, width={width_mult}x): {param_count:,} parameters")
    else:
        model = DrumClassifierCNN(num_classes=num_classes)
        param_count = sum(p.numel() for p in model.parameters())
        print(f"Using v1 model: {param_count:,} parameters")
    
    if args.channels_last:
        model = model.to(memory_format=torch.channels_last)
    model.to(device)
    if args.torch_compile:
        if hasattr(torch, "compile"):
            try:
                compile_kwargs: Dict[str, object] = {"mode": args.torch_compile_mode}
                model = torch.compile(model, **compile_kwargs)  # type: ignore[arg-type]
                print(f"torch.compile enabled for model (mode={args.torch_compile_mode})")
            except Exception as compile_exc:  # pragma: no cover - optional path
                print(f"Warning: torch.compile failed ({compile_exc}). Continuing without compilation.")
        else:
            print("Warning: torch.compile requested but unsupported in this PyTorch build. Ignoring.")
    
    # Loss and optimizer with optional class weighting
    class_weights_tensor: Optional[torch.Tensor] = None
    if args.class_weights != "none":
        class_weights_tensor = compute_class_weights(
            train_dataset_full.labels,
            num_classes,
            strategy=args.class_weights,
            max_weight=args.max_class_weight,
        ).to(torch_device)
        print(f"Class weighting enabled ({args.class_weights}): min={class_weights_tensor.min():.3f}, max={class_weights_tensor.max():.3f}")
    
    # Initialize loss function (standard CrossEntropy or Focal Loss)
    use_focal = args.focal_loss and HAS_FOCAL_LOSS
    if use_focal:
        if args.mixup_alpha > 0 or args.cutmix_alpha > 0:
            # Use mixup-compatible focal loss
            criterion = FocalLossWithMixup(
                gamma=args.focal_gamma,
                alpha=class_weights_tensor,
                label_smoothing=args.label_smoothing,
            )
        else:
            criterion = FocalLoss(
                gamma=args.focal_gamma,
                alpha=class_weights_tensor,
                label_smoothing=args.label_smoothing,
            )
        print(f"Focal Loss enabled: gamma={args.focal_gamma}")
    else:
        criterion = nn.CrossEntropyLoss(
            weight=class_weights_tensor,
            label_smoothing=args.label_smoothing,
        )
    
    # Wrap with Deep Supervision if enabled and model supports it
    use_deep_sup = args.use_deep_supervision and HAS_DEEP_SUPERVISION
    deep_sup_criterion = None
    if use_deep_sup and args.model_version in ["v5", "beats"]:
        # Parse weights from comma-separated string
        try:
            aux_weights = [float(w.strip()) for w in args.deep_supervision_weights.split(",")]
        except ValueError:
            aux_weights = [0.4, 0.6]
        deep_sup_criterion = DeepSupervisionLoss(
            base_criterion=criterion,
            aux_weights=aux_weights,
        )
        print(f"Deep Supervision enabled: aux_weights={aux_weights}")
    elif use_deep_sup:
        print(f"Note: Deep supervision only supported for v5 and beats models, ignoring")
    
    # Wrap with Hard Negative Mining if enabled (Option A enhancement: +0.5-1%)
    use_hard_negatives = getattr(args, 'use_hard_negatives', False) and HAS_HARD_NEGATIVE_MINING
    hard_negative_criterion = None
    if use_hard_negatives:
        hnm_config = HardNegativeConfig(
            strategy=getattr(args, 'hnm_strategy', 'curriculum'),
            ohem_ratio=getattr(args, 'hnm_ratio', 0.7),
            confusion_weight=getattr(args, 'hnm_confusion_weight', 2.0),
            curriculum_epochs=args.epochs,
            use_contrastive=getattr(args, 'hnm_use_contrastive', False),
            contrastive_margin=getattr(args, 'hnm_margin', 0.5),
            contrastive_weight=getattr(args, 'hnm_contrastive_weight', 0.3),
        )
        # Create a per-sample loss criterion for HNM (requires reduction='none')
        if use_focal:
            if args.mixup_alpha > 0 or args.cutmix_alpha > 0:
                hnm_base_criterion = FocalLossWithMixup(
                    gamma=args.focal_gamma,
                    alpha=class_weights_tensor,
                    label_smoothing=args.label_smoothing,
                    reduction='none',
                )
            else:
                hnm_base_criterion = FocalLoss(
                    gamma=args.focal_gamma,
                    alpha=class_weights_tensor,
                    label_smoothing=args.label_smoothing,
                    reduction='none',
                )
        else:
            hnm_base_criterion = nn.CrossEntropyLoss(
                weight=class_weights_tensor,
                label_smoothing=args.label_smoothing,
                reduction='none',
            )
        hard_negative_criterion = HardNegativeLoss(
            base_criterion=hnm_base_criterion,
            config=hnm_config,
        )
        print(f"Hard Negative Mining enabled: strategy={hnm_config.strategy}, ratio={hnm_config.ohem_ratio}, confusion_weight={hnm_config.confusion_weight}")

    
    # Warn about potential over-regularization when using multiple regularization techniques
    regularization_count = sum([
        args.mixup_alpha > 0 or args.cutmix_alpha > 0,  # Mixup/CutMix
        args.use_rdrop and HAS_RDROP,                    # R-Drop
        args.label_smoothing > 0,                        # Label smoothing
        args.use_curriculum and HAS_CURRICULUM,          # Curriculum (soft sampling)
    ])
    if regularization_count >= 3 and args.label_smoothing > 0.05:
        print(f"⚠️  Warning: Using {regularization_count} regularization techniques with label_smoothing={args.label_smoothing}")
        print(f"   This may cause over-regularization. Consider reducing --label-smoothing to 0.05")
    
    # Initialize optimizer (SAM or standard Adam)
    use_sam = args.use_sam and HAS_SAM
    use_gc = args.use_gradient_centralization and HAS_GRADIENT_CENTRALIZATION
    
    if use_sam:
        # SAM wraps a base optimizer
        optimizer = SAM(
            model.parameters(),
            base_optimizer=optim.Adam,
            rho=args.sam_rho,
            adaptive=args.sam_adaptive,
            lr=args.lr,
            weight_decay=args.weight_decay,
        )
        print(f"SAM optimizer enabled: rho={args.sam_rho}, adaptive={args.sam_adaptive}")
    else:
        optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    
    # Apply Gradient Centralization wrapper if requested
    if use_gc and not use_sam:  # GC is applied to base optimizer, SAM handles its own gradients
        optimizer = wrap_optimizer_with_gc(optimizer)
        print("Gradient Centralization enabled (improves generalization)")
    elif use_gc and use_sam:
        print("Note: Gradient Centralization is applied within SAM's base optimizer automatically")
    
    # Apply Lookahead wrapper if requested (Zhang et al., NeurIPS 2019)
    use_lookahead = args.use_lookahead and HAS_LOOKAHEAD
    if use_lookahead:
        optimizer = wrap_with_lookahead(
            optimizer,
            k=args.lookahead_k,
            alpha=args.lookahead_alpha,
        )
        print(f"Lookahead enabled: k={args.lookahead_k} steps, alpha={args.lookahead_alpha}")
    
    for group in optimizer.param_groups:
        group.setdefault("initial_lr", args.lr)

    if args.scheduler == "plateau":
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=5)
    else:
        t_max = max(1, args.epochs - args.warmup_epochs)
        eta_min = args.min_lr if args.min_lr is not None else args.lr * 0.1
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_max, eta_min=eta_min)

    amp_enabled = torch_device.type == "cuda" and not args.disable_amp
    autocast_dtype = torch.bfloat16 if args.amp_dtype == "bfloat16" else torch.float16
    if torch_device.type == "cuda" and args.amp_dtype == "bfloat16":
        bf16_supported = getattr(torch.cuda, "is_bf16_supported", lambda: False)()
        if not bf16_supported:
            print("bfloat16 AMP is not supported on this GPU; falling back to float16.")
            autocast_dtype = torch.float16
    if torch_device.type != "cuda":
        autocast_dtype = torch.bfloat16
    scaler: Optional[GradScaler]
    if amp_enabled:
        scaler_kwargs: Dict[str, Any] = {}
        try:
            if "device_type" in inspect.signature(GradScaler.__init__).parameters:
                scaler_kwargs["device_type"] = torch_device.type
        except (TypeError, ValueError):
            # Older PyTorch versions may not expose the signature reliably.
            pass
        scaler = GradScaler(**scaler_kwargs)
    else:
        scaler = None
    
    # Initialize Mixup/CutMix augmentation if requested
    mixup_fn = None
    if args.mixup_alpha > 0 or args.cutmix_alpha > 0:
        if not HAS_MIXUP:
            raise SystemExit("Mixup/CutMix requested but training.augmentation.mixup module not found.")
        mixup_fn = MixupCutmix(
            mixup_alpha=args.mixup_alpha,
            cutmix_alpha=args.cutmix_alpha,
            prob=args.mixup_prob,
        )
        print(f"Mixup/CutMix enabled: mixup_alpha={args.mixup_alpha}, cutmix_alpha={args.cutmix_alpha}, prob={args.mixup_prob}")
    
    # Initialize SpecAugment if requested
    specaugment_fn = None
    if args.specaugment != "none":
        if not HAS_SPECAUGMENT:
            raise SystemExit("SpecAugment requested but training.augmentation.specaugment module not found.")
        specaugment_fn = get_specaugment(
            config=args.specaugment,
            n_mels=args.n_mels,
            n_frames=args.target_frames,
        )
        print(f"SpecAugment enabled: preset={args.specaugment}, freq_masks={specaugment_fn.n_freq_masks}, time_masks={specaugment_fn.n_time_masks}")
    
    # Initialize EMA if requested
    ema = None
    if args.use_ema:
        if not HAS_EMA:
            raise SystemExit("EMA requested but training.utils.ema module not found.")
        ema = ModelEMA(
            model=model,
            decay=args.ema_decay,
            warmup_steps=args.ema_warmup_steps,
        )
        print(f"EMA enabled: decay={args.ema_decay}, warmup_steps={args.ema_warmup_steps}")
    
    # Initialize Progressive Augmentation if requested
    progressive_aug = None
    if args.progressive_augmentation:
        if not HAS_PROGRESSIVE:
            raise SystemExit("Progressive augmentation requested but training.utils.adaptive module not found.")
        progressive_aug = ProgressiveAugmentation(
            total_epochs=args.epochs,
            mixup_start=0.1,
            mixup_end=args.mixup_alpha if args.mixup_alpha > 0 else 0.4,
            cutmix_start=0.3,
            cutmix_end=args.cutmix_alpha if args.cutmix_alpha > 0 else 1.0,
            specaug_start_prob=0.3,
            specaug_end_prob=0.8,
        )
        print(f"Progressive Augmentation enabled: augmentation strength will ramp up during training")
        print(progressive_aug.log_schedule())
    
    # Initialize SWA (Stochastic Weight Averaging) if requested
    swa_manager = None
    use_swa = args.use_swa and HAS_SWA
    if use_swa:
        swa_lr = args.swa_lr if args.swa_lr is not None else args.lr * 0.1
        swa_manager = SWAManager(
            model=model,
            swa_start=args.swa_start,
            swa_lr=swa_lr,
            device=torch_device,
        )
        print(f"SWA enabled: start={args.swa_start * 100:.0f}% of training, lr={swa_lr}")
    
    # Initialize R-Drop (Regularized Dropout) if requested
    use_rdrop = args.use_rdrop and HAS_RDROP
    rdrop_criterion = None
    if use_rdrop:
        rdrop_criterion = get_rdrop_loss(
            alpha=args.rdrop_alpha,
            base_loss='focal' if use_focal else 'ce',
            focal_gamma=args.focal_gamma if use_focal else 2.0,
            label_smoothing=args.label_smoothing,
            class_weights=class_weights_tensor,
        )
        print(f"R-Drop enabled: alpha={args.rdrop_alpha} (consistency regularization)")
    
    # Initialize Curriculum Learning if requested
    curriculum_scheduler = None
    use_curriculum = args.use_curriculum and HAS_CURRICULUM
    if use_curriculum:
        # We'll compute difficulty scores after loading or with a pre-trained model
        # For now, use class-based difficulty (no model needed)
        from training.utils.curriculum import get_drum_class_difficulty, CurriculumScheduler
        
        class_difficulty = get_drum_class_difficulty()
        class_names = components_info.get('class_names', DrumClassifierCNN.DRUM_COMPONENTS[:num_classes])
        
        # Get labels for training set
        if train_subset_indices is not None:
            train_labels = [train_dataset_full.labels[i]['component_idx'] for i in train_subset_indices]
        else:
            train_labels = [item['component_idx'] for item in train_dataset_full.labels]
        
        # Compute per-sample difficulty blending domain knowledge with class frequency
        # This mitigates the risk of hardcoded difficulty scores being wrong
        try:
            from training.utils.curriculum import compute_frequency_adjusted_difficulty
            difficulty_scores = compute_frequency_adjusted_difficulty(
                labels=train_labels,
                class_names=class_names,
                frequency_weight=0.3,  # 30% frequency, 70% domain knowledge
            )
            print(f"  Using frequency-adjusted difficulty scores (30% frequency + 70% domain knowledge)")
        except ImportError:
            # Fallback to pure domain knowledge
            difficulty_scores = np.array([
                class_difficulty.get(class_names[label] if label < len(class_names) else 'aux_percussion', 0.5)
                for label in train_labels
            ])
        
        curriculum_scheduler = CurriculumScheduler(
            difficulty_scores=difficulty_scores,
            total_epochs=args.epochs,
            warmup_epochs=max(2, args.epochs // 10),
            start_fraction=args.curriculum_start_fraction,
            strategy=args.curriculum_strategy,
        )
        print(f"Curriculum Learning enabled: start={args.curriculum_start_fraction:.0%}, strategy={args.curriculum_strategy}")
        print(f"  Epoch 0: {curriculum_scheduler.get_fraction(0):.0%} of data")
        print(f"  Epoch {args.epochs//2}: {curriculum_scheduler.get_fraction(args.epochs//2):.0%} of data")
        print(f"  Epoch {args.epochs-1}: {curriculum_scheduler.get_fraction(args.epochs-1):.0%} of data")
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = Path(args.checkpoint_dir) if args.checkpoint_dir else output_dir / "checkpoints"
    checkpoint_interval = args.checkpoint_every if args.checkpoint_every > 0 else None
    checkpoint_batch_interval = args.checkpoint_every_batches if args.checkpoint_every_batches > 0 else None

    # Training loop
    best_val_acc = 0.0
    best_epoch = -1
    best_model_path: Path | None = None
    history: List[Dict[str, float]] = []
    start_epoch = 0
    last_completed_epoch = 0
    current_batch_in_epoch = 0  # Track batch progress for mid-epoch checkpoints
    resumed_from: Optional[str] = str(args.resume_from) if args.resume_from else None

    def save_checkpoint(
        epoch_index: int,
        *,
        reason: Optional[str] = None,
        batch_index: Optional[int] = None,
        total_batches: Optional[int] = None,
    ) -> Path:
        """Persist model/optimizer state for later resumption.
        
        Args:
            epoch_index: Current epoch (0-indexed internally, saved as 1-indexed)
            reason: Optional description for the checkpoint
            batch_index: If mid-epoch, the current batch number
            total_batches: If mid-epoch, total batches in the epoch
        """
        is_mid_epoch = batch_index is not None

        checkpoint_payload = {
            "epoch": int(epoch_index),
            "total_epochs": int(args.epochs),
            "model_state": _normalize_state_dict_keys(model.state_dict()),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "scaler_state": scaler.state_dict() if scaler is not None and amp_enabled else None,
            "history": list(history),
            "best_val_acc": float(best_val_acc),
            "best_epoch": int(best_epoch),
            "best_model_path": str(best_model_path) if best_model_path else None,
            "args": vars(args),
            # Mid-epoch resume info
            "batch_index": batch_index,
            "total_batches": total_batches,
        }

        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        if is_mid_epoch:
            # Mid-epoch checkpoint: use a fixed name that gets overwritten
            checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch_index:04d}_mid.pth"
        else:
            # End-of-epoch checkpoint
            checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch_index:04d}.pth"
            # Clean up mid-epoch checkpoint when epoch completes
            mid_epoch_path = checkpoint_dir / f"checkpoint_epoch_{epoch_index:04d}_mid.pth"
            if mid_epoch_path.exists():
                mid_epoch_path.unlink()
                
        torch.save(checkpoint_payload, checkpoint_path)
        
        # Always update latest_checkpoint.pth for easy resumption
        latest_path = checkpoint_dir / "latest_checkpoint.pth"
        torch.save(checkpoint_payload, latest_path)

        if is_mid_epoch:
            pct = 100 * batch_index / total_batches if total_batches else 0
            print(f"\n💾 Mid-epoch checkpoint saved (epoch {epoch_index}, batch {batch_index}/{total_batches}, {pct:.0f}%)")
        elif reason:
            print(f"Checkpoint saved ({reason}) at epoch {epoch_index}")
        else:
            print(f"Checkpoint saved at epoch {epoch_index}")

        return checkpoint_path

    if args.resume_from:
        if not args.resume_from.exists():
            raise FileNotFoundError(f"Checkpoint not found: {args.resume_from}")
        checkpoint_state = torch.load(args.resume_from, map_location=torch_device)
        if "model_state" not in checkpoint_state or "optimizer_state" not in checkpoint_state:
            raise KeyError(f"Invalid checkpoint format: {args.resume_from}")
        model_state = checkpoint_state["model_state"]
        if isinstance(model_state, dict):
            model_state = _normalize_state_dict_keys(model_state)
        target_keys = list(model.state_dict().keys())
        if target_keys and target_keys[0].startswith("_orig_mod."):
            model_state = OrderedDict(
                (key if key.startswith("_orig_mod.") else f"_orig_mod.{key}", value)
                for key, value in model_state.items()
            )
        model.load_state_dict(model_state)
        optimizer.load_state_dict(checkpoint_state["optimizer_state"])
        scheduler_state = checkpoint_state.get("scheduler_state")
        if scheduler_state is not None:
            scheduler.load_state_dict(scheduler_state)
        scaler_state = checkpoint_state.get("scaler_state")
        if amp_enabled and scaler_state is not None and scaler is not None:
            scaler.load_state_dict(scaler_state)
        history = [dict(item) for item in checkpoint_state.get("history", []) if isinstance(item, dict)]
        best_val_acc = float(checkpoint_state.get("best_val_acc", best_val_acc))
        best_epoch = int(checkpoint_state.get("best_epoch", best_epoch))
        best_model_path_str = checkpoint_state.get("best_model_path")
        if best_model_path_str:
            best_model_path = Path(best_model_path_str)
        start_epoch = int(checkpoint_state.get("epoch", 0))
        last_completed_epoch = start_epoch
        print(f"Resuming from checkpoint {args.resume_from} (epoch {start_epoch})")
        if start_epoch >= args.epochs:
            print("Warning: checkpoint epoch is greater than or equal to requested total epochs; no training will run.")

    wandb_run = None
    if args.wandb_project:
        if wandb is None:
            raise SystemExit("Weights & Biases is not installed. Run 'pip install wandb' to enable logging.")
        wandb_kwargs: Dict[str, object] = {
            "project": args.wandb_project,
            "config": {
                "dataset": str(args.dataset),
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.lr,
                "lr_scheduler": args.scheduler,
                "warmup_epochs": args.warmup_epochs,
                "device": str(device),
                "amp_enabled": amp_enabled,
                "amp_dtype": str(autocast_dtype),
                "train_fraction": args.train_fraction,
                "val_fraction": args.val_fraction,
                "train_num_workers": num_workers,
                "val_num_workers": val_num_workers,
                "seed": args.seed,
                "deterministic": args.deterministic,
                "weight_decay": args.weight_decay,
                "grad_clip_norm": args.grad_clip_norm,
                "grad_accum_steps": args.grad_accum_steps,
                "channels_last": args.channels_last,
                "torch_compile": args.torch_compile,
                "cache_dtype": args.cache_dtype,
            },
        }
        if args.scheduler == "cosine":
            wandb_kwargs["config"]["min_lr"] = args.min_lr if args.min_lr is not None else args.lr * 0.1  # type: ignore[index]
        if args.wandb_entity:
            wandb_kwargs["entity"] = args.wandb_entity
        if args.wandb_run_name:
            wandb_kwargs["name"] = args.wandb_run_name
        if args.wandb_tags:
            wandb_kwargs["tags"] = args.wandb_tags
        wandb_mode = args.wandb_mode or os.environ.get("WANDB_MODE")
        if wandb_mode:
            wandb_kwargs["mode"] = wandb_mode
        wandb_run = wandb.init(**wandb_kwargs)  # type: ignore[assignment]
        if wandb_run is not None:
            wandb_run.log({"status": "initialized"})
    
    # =========================================================================
    # LABEL AUDIT MODE (Confident Learning)
    # =========================================================================
    if getattr(args, 'clean_labels', False) and HAS_CONFIDENT_LEARNING:
        print("\n" + "=" * 60)
        print("LABEL AUDIT MODE (Confident Learning)")
        print("=" * 60)
        
        audit_only = getattr(args, 'label_noise_audit_only', False)
        noise_threshold = getattr(args, 'label_noise_threshold', 0.5)
        
        # First train for a few epochs to get meaningful predictions
        audit_warmup_epochs = min(5, args.epochs)  # Train for 5 epochs or less
        print(f"\n[LABEL AUDIT] Training for {audit_warmup_epochs} epochs before audit...")
        
        for epoch in range(audit_warmup_epochs):
            print(f"\nAudit Warmup Epoch {epoch + 1}/{audit_warmup_epochs}")
            print("-" * 40)
            
            train_loss, train_acc = train_epoch(
                model, train_loader, criterion, optimizer, torch_device,
                grad_accum_steps=args.grad_accum_steps,
                scaler=scaler,
                amp_enabled=amp_enabled,
                autocast_dtype=autocast_dtype,
                mixup_fn=None,  # No mixup during audit warmup
                grad_clip_norm=args.grad_clip_norm if args.grad_clip_norm and args.grad_clip_norm > 0 else None,
                channels_last=args.channels_last,
            )
            val_loss, val_acc = validate(model, val_loader, criterion, torch_device, channels_last=args.channels_last)
            print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%")
            print(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%")
        
        print(f"\n[LABEL AUDIT] Running label noise detection...")
        print(f"  Threshold: {noise_threshold}")
        print(f"  Audit only: {audit_only}")
        print(f"  Training samples: {len(train_dataset):,}")
        
        # Get class names from components.json if available
        components_path = Path(args.dataset) / "components.json"
        class_names = None
        if components_path.exists():
            with open(components_path, "r") as f:
                components = json.load(f)
                class_names = [c["name"] for c in components]
                print(f"  Classes: {len(class_names)}")
        
        # Run the label audit
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        issues, pred_probs = run_label_audit(
            model=model,
            dataset=train_dataset,
            device=torch_device,
            batch_size=args.batch_size,
            num_workers=num_workers,
            output_dir=output_dir,
            class_names=class_names,
        )
        
        print(f"\n[LABEL AUDIT] Found {len(issues):,} potential label issues ({100*len(issues)/len(train_dataset):.2f}%)")
        
        # Save detailed report
        report_path = output_dir / "label_noise_report.json"
        report = {
            "total_samples": len(train_dataset),
            "issues_found": len(issues),
            "issues_percent": 100 * len(issues) / len(train_dataset),
            "threshold": noise_threshold,
            "class_names": class_names,
            "top_issues": [issue.to_dict() for issue in issues[:1000]],  # Top 1000 issues
        }
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[LABEL AUDIT] Report saved to: {report_path}")
        
        if audit_only:
            print("\n[LABEL AUDIT] Audit-only mode - exiting without training")
            print(f"To train with cleaned labels, remove --label-noise-audit-only flag")
            return
        
        # Filter issues based on threshold and continue training with cleaned dataset
        print(f"\n[LABEL AUDIT] Filtering samples with confidence < {noise_threshold}...")
        clean_indices = [i for i in range(len(train_dataset)) 
                        if i not in {issue.index for issue in issues if issue.confidence > noise_threshold}]
        print(f"[LABEL AUDIT] Keeping {len(clean_indices):,} clean samples ({100*len(clean_indices)/len(train_dataset):.2f}%)")
        
        # Update train_dataset to use only clean samples
        train_dataset = Subset(train_dataset, clean_indices)
        train_loader = build_loader(
            train_dataset,
            batch_size=args.batch_size,
            shuffle=True,
            workers=num_workers,
            prefetch=train_prefetch,
            persistent=train_persistent,
        )
        print(f"[LABEL AUDIT] Updated training dataset and loader")
        print("=" * 60 + "\n")
    
    try:
        for epoch in range(start_epoch, args.epochs):
            print(f"\nEpoch {epoch + 1}/{args.epochs}")
            print("-" * 60)

            # Update progressive augmentation if enabled
            if progressive_aug is not None and mixup_fn is not None:
                prog_values = progressive_aug.get_all(epoch)
                mixup_fn.mixup_alpha = prog_values["mixup_alpha"]
                mixup_fn.cutmix_alpha = prog_values["cutmix_alpha"]
                if specaugment_fn is not None:
                    specaugment_fn.prob = prog_values["specaugment_prob"]
                if epoch % 10 == 0 or epoch == start_epoch:
                    print(f"  Progressive aug: mixup_alpha={prog_values['mixup_alpha']:.3f}, "
                          f"cutmix_alpha={prog_values['cutmix_alpha']:.3f}, "
                          f"specaug_p={prog_values['specaugment_prob']:.3f}")

            # Update curriculum learning sampler if enabled
            if curriculum_scheduler is not None:
                curriculum_scheduler.step(epoch)
                if epoch % 10 == 0 or epoch == start_epoch:
                    print(f"  Curriculum: fraction={curriculum_scheduler.get_current_fraction():.3f}")
                # Rebuild train_loader with updated sampler weights
                from torch.utils.data import WeightedRandomSampler
                sample_weights = curriculum_scheduler.get_sample_weights(train_dataset.labels)
                curriculum_sampler = WeightedRandomSampler(
                    weights=sample_weights,
                    num_samples=len(train_dataset),
                    replacement=True,
                )
                train_loader = DataLoader(
                    train_dataset,
                    batch_size=args.batch_size,
                    sampler=curriculum_sampler,
                    num_workers=args.workers,
                    pin_memory=True,
                    prefetch_factor=args.prefetch_factor,
                    persistent_workers=args.workers > 0,
                    drop_last=True,
                )

            if args.warmup_epochs > 0 and epoch < args.warmup_epochs:
                # Linear warmup from (lr * warmup_lr_factor) to lr
                # warmup_factor goes from warmup_lr_factor at epoch 0 to 1.0 at warmup_epochs-1
                progress = float(epoch + 1) / float(max(1, args.warmup_epochs))
                warmup_factor = args.warmup_lr_factor + (1.0 - args.warmup_lr_factor) * progress
                warmup_lr = args.lr * warmup_factor
                for group in optimizer.param_groups:
                    group["lr"] = warmup_lr

            # Create mid-epoch checkpoint callback for this epoch
            def mid_epoch_checkpoint(batch_idx: int, total_batches: int) -> None:
                save_checkpoint(
                    epoch + 1,
                    reason="mid-epoch",
                    batch_index=batch_idx,
                    total_batches=total_batches,
                )

            # Apply mixup cutoff: disable mixup in final phase of training for cleaner decision boundaries
            epoch_mixup_fn = mixup_fn
            if mixup_fn is not None and args.mixup_cutoff_ratio < 1.0:
                training_progress = (epoch + 1) / args.epochs
                if training_progress > args.mixup_cutoff_ratio:
                    epoch_mixup_fn = None
                    if epoch == int(args.epochs * args.mixup_cutoff_ratio):
                        print(f"  Mixup cutoff: disabled at {training_progress*100:.0f}% of training (epoch {epoch+1})")

            train_loss, train_acc = train_epoch(
                model,
                train_loader,
                criterion,
                optimizer,
                torch_device,
                amp_enabled=amp_enabled,
                scaler=scaler,
                autocast_dtype=autocast_dtype,
                grad_clip_norm=args.grad_clip_norm,
                channels_last=args.channels_last,
                grad_accum_steps=args.grad_accum_steps,
                checkpoint_callback=mid_epoch_checkpoint if checkpoint_batch_interval else None,
                checkpoint_every_batches=checkpoint_batch_interval or 0,
                mixup_fn=epoch_mixup_fn,
                specaugment_fn=specaugment_fn,
                ema=ema,
                use_sam=use_sam,
                use_rdrop=args.use_rdrop and HAS_RDROP,
                rdrop_criterion=rdrop_criterion,
                deep_sup_criterion=deep_sup_criterion,
            )
            
            # Update SWA if in SWA phase
            if swa_manager is not None:
                swa_manager.update(model, epoch, args.epochs)
            
            # Validation with optional TTA
            use_val_tta = getattr(args, 'val_tta', False)
            if use_val_tta:
                val_loss, val_acc = validate_with_tta(
                    model,
                    val_loader,
                    criterion,
                    torch_device,
                    num_augmentations=getattr(args, 'val_tta_augmentations', 3),
                    amp_enabled=amp_enabled,
                    autocast_dtype=autocast_dtype,
                    channels_last=args.channels_last,
                )
            else:
                val_loss, val_acc = validate(
                    model,
                    val_loader,
                    criterion,
                    torch_device,
                    amp_enabled=amp_enabled,
                    autocast_dtype=autocast_dtype,
                    channels_last=args.channels_last,
                )

            history.append(
                {
                    "epoch": float(epoch + 1),
                    "train_loss": float(train_loss),
                    "train_accuracy": float(train_acc),
                    "val_loss": float(val_loss),
                    "val_accuracy": float(val_acc),
                }
            )

            if args.scheduler == "plateau":
                scheduler.step(val_loss)
            else:
                if epoch >= args.warmup_epochs:
                    scheduler.step()

            print(f"Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2f}%")
            print(f"Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2f}%")

            if wandb_run is not None:
                wandb_run.log(  # type: ignore[call-arg]
                    {
                        "epoch": epoch + 1,
                        "train/loss": train_loss,
                        "train/accuracy": train_acc,
                        "val/loss": val_loss,
                        "val/accuracy": val_acc,
                        "lr": optimizer.param_groups[0]["lr"],
                    },
                    step=epoch + 1,
                )

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_epoch = epoch + 1
                model_path = output_dir / "best_drum_classifier.pth"
                torch.save(model.state_dict(), model_path)
                best_model_path = model_path
                print(f"✓ Saved best model (acc: {val_acc:.2f}%)")
                
                # Also save EMA model if enabled (often performs even better)
                if ema is not None:
                    ema_model_path = output_dir / "best_drum_classifier_ema.pth"
                    torch.save(ema.ema_model.state_dict(), ema_model_path)
                    print(f"✓ Saved best EMA model (acc: {val_acc:.2f}%)")
                
                if wandb_run is not None:
                    wandb_run.summary["best_val_accuracy"] = best_val_acc  # type: ignore[index]
                    wandb_run.summary["best_epoch"] = best_epoch  # type: ignore[index]

            last_completed_epoch = epoch + 1

            # Save checkpoint BEFORE any W&B uploads to ensure training progress is never lost
            if checkpoint_interval and (epoch + 1) % checkpoint_interval == 0:
                save_checkpoint(epoch + 1, reason="interval")

            # W&B model upload (best-effort, won't crash training if it fails)
            if val_acc == best_val_acc and wandb_run is not None:
                # Use policy="now" to copy file immediately instead of symlink
                # This avoids Windows symlink permission issues (WinError 1314)
                try:
                    wandb_run.save(str(model_path), policy="now")  # type: ignore[arg-type]
                except OSError as e:
                    # Fallback: log artifact instead if save still fails
                    if "WinError 1314" in str(e) or "privilege" in str(e).lower():
                        print(f"⚠ wandb.save() failed (Windows symlink issue), using artifact instead")
                        try:
                            artifact = wandb.Artifact(
                                name=f"best_model_epoch_{best_epoch}",
                                type="model",
                                description=f"Best model checkpoint (val_acc={val_acc:.2f}%)"
                            )
                            artifact.add_file(str(model_path))
                            wandb_run.log_artifact(artifact)
                        except Exception as artifact_err:
                            print(f"⚠ Artifact upload also failed: {artifact_err} (continuing anyway)")
                    else:
                        print(f"⚠ wandb.save() failed: {e} (continuing anyway)")
                except Exception as e:
                    print(f"⚠ wandb.save() failed: {e} (continuing anyway)")

    except KeyboardInterrupt:
        print("Training interrupted by user. Saving checkpoint before exiting...")
        save_checkpoint(last_completed_epoch, reason="interrupt")
        raise

    save_checkpoint(last_completed_epoch, reason="complete")
    
    # Save final model
    final_model_path = output_dir / "final_drum_classifier.pth"
    torch.save(model.state_dict(), final_model_path)
    
    # Save final EMA model if enabled
    if ema is not None:
        final_ema_path = output_dir / "final_drum_classifier_ema.pth"
        torch.save(ema.ema_model.state_dict(), final_ema_path)
        print(f"Final EMA model saved to: {final_ema_path}")
    
    # Save SWA model if enabled (requires updating BN statistics)
    if swa_manager is not None and swa_manager.started:
        print("Updating BatchNorm statistics for SWA model...")
        swa_manager.update_batch_norm(train_loader)
        final_swa_path = output_dir / "final_drum_classifier_swa.pth"
        torch.save(swa_manager.get_averaged_model().state_dict(), final_swa_path)
        print(f"Final SWA model saved to: {final_swa_path}")
    
    # Post-training calibration if enabled
    if args.calibrate and HAS_CALIBRATION:
        print("\n" + "=" * 60)
        print("Running post-training temperature calibration...")
        print("=" * 60)
        try:
            from training.calibration.temperature_scaling import calibrate_model, compute_calibration_metrics
            
            # Calibrate the model using validation set
            calibrated_temp, metrics = calibrate_model(
                model=model,
                val_loader=val_loader,
                device=torch_device,
                method=args.calibration_method,
            )
            
            print(f"Calibration complete:")
            print(f"  Method: {args.calibration_method}")
            print(f"  Optimal temperature: {calibrated_temp:.4f}")
            print(f"  ECE before: {metrics.get('ece_before', 0):.4f}, ECE after: {metrics.get('ece_after', 0):.4f}")
            print(f"  NLL before: {metrics.get('nll_before', 0):.4f}, NLL after: {metrics.get('nll_after', 0):.4f}")
            
            # Save calibration temperature
            calib_path = output_dir / "calibration_temperature.json"
            with open(calib_path, "w") as f:
                json.dump({
                    "temperature": calibrated_temp,
                    "method": args.calibration_method,
                    "metrics": metrics,
                }, f, indent=2)
            print(f"Calibration parameters saved to: {calib_path}")
            
        except Exception as e:
            print(f"⚠ Calibration failed: {e} (continuing without calibration)")
    
    print("\n" + "=" * 60)
    print(f"Training complete!")
    print(f"Best validation accuracy: {best_val_acc:.2f}%")
    print(f"Models saved to: {output_dir}")
    if ema is not None:
        print(f"EMA models also saved (often perform 0.5-1% better)")
    if swa_manager is not None and swa_manager.started:
        print(f"SWA model also saved (typically best generalization)")
    print("=" * 60)

    if wandb_run is not None:
        wandb_run.summary["final_train_loss"] = history[-1]["train_loss"] if history else None  # type: ignore[index]
        wandb_run.summary["final_val_loss"] = history[-1]["val_loss"] if history else None  # type: ignore[index]
        wandb_run.summary["final_train_accuracy"] = history[-1]["train_accuracy"] if history else None  # type: ignore[index]
        wandb_run.summary["final_val_accuracy"] = history[-1]["val_accuracy"] if history else None  # type: ignore[index]
        wandb_run.summary["best_model_path"] = str(best_model_path) if best_model_path else None  # type: ignore[index]
        wandb_run.summary["final_model_path"] = str(final_model_path)  # type: ignore[index]
        # Use policy="now" to copy file immediately instead of symlink
        # This avoids Windows symlink permission issues (WinError 1314)
        try:
            wandb_run.save(str(final_model_path), policy="now")  # type: ignore[arg-type]
        except OSError as e:
            if "WinError 1314" in str(e) or "privilege" in str(e).lower():
                print(f"⚠ wandb.save() failed (Windows symlink issue), using artifact instead")
                artifact = wandb.Artifact(
                    name="final_model",
                    type="model",
                    description="Final model checkpoint"
                )
                artifact.add_file(str(final_model_path))
                wandb_run.log_artifact(artifact)
            else:
                raise
        wandb_run.log({"status": "completed"})  # type: ignore[call-arg]
        wandb_run.finish()  # type: ignore[call-arg]

    if args.metrics_json:
        metrics = {
            "epochs": int(args.epochs),
            "batch_size": int(args.batch_size),
            "learning_rate": float(args.lr),
            "device": str(device),
            "resumed_from_checkpoint": resumed_from,
            "best_validation_accuracy": float(best_val_acc),
            "best_epoch": int(best_epoch),
            "best_model_path": str(best_model_path) if best_model_path else None,
            "final_train_loss": float(history[-1]["train_loss"]) if history else None,
            "final_val_loss": float(history[-1]["val_loss"]) if history else None,
            "final_train_accuracy": float(history[-1]["train_accuracy"]) if history else None,
            "final_val_accuracy": float(history[-1]["val_accuracy"]) if history else None,
            "amp_enabled": bool(amp_enabled),
            "amp_dtype": str(autocast_dtype),
            "train_fraction": float(args.train_fraction),
            "val_fraction": float(args.val_fraction),
            "train_num_workers": int(num_workers),
            "val_num_workers": int(val_num_workers),
            "seed": int(args.seed) if args.seed is not None else None,
            "deterministic": bool(args.deterministic),
            "grad_clip_norm": float(args.grad_clip_norm) if args.grad_clip_norm is not None else None,
            "weight_decay": float(args.weight_decay),
            "channels_last": bool(args.channels_last),
            "torch_compile": bool(args.torch_compile),
            "history": history,
            "cache_dtype": args.cache_dtype,
        }
        metrics_path = args.metrics_json
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with metrics_path.open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)


if __name__ == "__main__":
    main()
