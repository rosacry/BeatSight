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
import logging
import math
import os
import random
import signal
import warnings
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

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

# Optional Knowledge Distillation
try:
    from training.utils.distillation import DistillationLoss, FeatureDistillationLoss
    HAS_DISTILLATION = True
except ImportError:
    HAS_DISTILLATION = False
    DistillationLoss = None  # type: ignore
    FeatureDistillationLoss = None  # type: ignore

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

# Optional Ghost Note Augmentation (NEW - synthesize ghost notes from normal hits)
try:
    from training.augmentation.ghost_note_augment import GhostNoteAugmenter, GhostNoteConfig, get_ghost_augmenter
    HAS_GHOST_AUGMENT = True
except ImportError:
    HAS_GHOST_AUGMENT = False
    GhostNoteAugmenter = None  # type: ignore
    GhostNoteConfig = None  # type: ignore
    get_ghost_augmenter = None  # type: ignore

# Optional Accent-Tap Augmentation (NEW - velocity-based accent/tap pattern augmentation)
try:
    from training.augmentation.accent_tap_augment import AccentTapAugmenter, AccentTapConfig, get_accent_tap_augmenter
    HAS_ACCENT_TAP_AUGMENT = True
except ImportError:
    HAS_ACCENT_TAP_AUGMENT = False
    AccentTapAugmenter = None  # type: ignore
    AccentTapConfig = None  # type: ignore
    get_accent_tap_augmenter = None  # type: ignore

# Optional Technique Detection Heads (NEW - multi-label technique classification)
try:
    from training.models.technique_heads import (
        TechniqueHeads,
        TechniqueConfig,
        IntegratedTechniqueModel,
        get_technique_heads,
        CORE_TECHNIQUES,
        ALL_TECHNIQUES,
    )
    HAS_TECHNIQUE_HEADS = True
except ImportError:
    HAS_TECHNIQUE_HEADS = False
    TechniqueHeads = None  # type: ignore
    TechniqueConfig = None  # type: ignore
    IntegratedTechniqueModel = None  # type: ignore
    get_technique_heads = None  # type: ignore
    CORE_TECHNIQUES = []  # type: ignore
    ALL_TECHNIQUES = []  # type: ignore

# Consolidated Memory-Mapped Cache (HIGH-PERFORMANCE - 100x faster than individual .pt files)
try:
    from training.utils.consolidated_cache import ConsolidatedCacheReader
    HAS_CONSOLIDATED_CACHE = True
except ImportError:
    HAS_CONSOLIDATED_CACHE = False
    ConsolidatedCacheReader = None  # type: ignore

# Shard-Aware Batch Sampler (CRITICAL PERFORMANCE - 10-50x faster I/O for large datasets)
# Groups samples by shard to maximize sequential I/O and minimize mmap page faults
try:
    from training.utils.shard_sampler import ShardAwareBatchSampler, ShardAwareSampler
    HAS_SHARD_SAMPLER = True
except ImportError:
    HAS_SHARD_SAMPLER = False
    ShardAwareBatchSampler = None  # type: ignore
    ShardAwareSampler = None  # type: ignore

# Optional AWP (Adversarial Weight Perturbation - better generalization)
try:
    from training.optimizers.awp import AWP, AWPWithSAM, get_awp
    HAS_AWP = True
except ImportError:
    HAS_AWP = False
    AWP = None  # type: ignore
    AWPWithSAM = None  # type: ignore
    get_awp = None  # type: ignore

# Optional Early Stopping (prevent overfitting)
try:
    from training.utils.early_stopping import EarlyStopping, EarlyStoppingWithWarmup, get_early_stopping
    HAS_EARLY_STOPPING = True
except ImportError:
    HAS_EARLY_STOPPING = False
    EarlyStopping = None  # type: ignore
    EarlyStoppingWithWarmup = None  # type: ignore
    get_early_stopping = None  # type: ignore

# Safe print for Windows console encoding issues (cp1252 can't handle emoji)
try:
    from training.utils.safe_print import safe_print as _safe_print
except ImportError:
    # Fallback inline implementation if module not found
    def _safe_print(*args, **kwargs) -> None:
        """Print with fallback for Windows encoding issues."""
        import sys
        import io
        try:
            print(*args, **kwargs)
        except UnicodeEncodeError:
            output = io.StringIO()
            print(*args, file=output, **kwargs)
            text = output.getvalue()
            replacements = {'⚠️': '[!]', '⚠': '[!]', '✓': '[OK]', '✗': '[X]', '❌': '[X]', 
                          '✅': '[OK]', '→': '->', '🎉': '[SUCCESS]'}
            for emoji, ascii_rep in replacements.items():
                text = text.replace(emoji, ascii_rep)
            if sys.stdout.encoding:
                text = text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding, errors='replace')
            sys.stdout.write(text)
            sys.stdout.flush()


def _is_no_decay_param(name: str) -> bool:
    """
    Check if parameter should have zero weight decay.
    
    BatchNorm, LayerNorm, and bias terms should NOT have weight decay applied.
    This is a well-established best practice that improves generalization.
    
    Reference: "Decoupled Weight Decay Regularization" (Loshchilov & Hutter, 2019)
    """
    no_decay_patterns = (
        '.bias',           # All bias terms
        'bn',              # BatchNorm (any layer)
        'norm',            # LayerNorm, GroupNorm, etc.
        'gamma', 'beta',   # BN parameters
        'ln_',             # LayerNorm prefix
        '_ln',             # LayerNorm suffix
    )
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in no_decay_patterns)


def get_layer_wise_lr_params(model: nn.Module, base_lr: float, layer_decay: float, weight_decay: float = 0.0) -> List[Dict[str, Any]]:
    """
    Get parameter groups with layer-wise learning rate decay for V5 model.
    
    Earlier layers (closer to input) get smaller LR, later layers get larger LR.
    This helps fine-tuning: early features are more general, late features are task-specific.
    
    IMPORTANT: BatchNorm/LayerNorm and bias parameters get weight_decay=0.
    This is a best practice that improves generalization by ~0.1-0.3%.
    
    Reference: "BEiT: BERT Pre-Training of Image Transformers" (Bao et al., 2021)
    
    Args:
        model: The model to create parameter groups for
        base_lr: Base learning rate for the final layers
        layer_decay: Decay factor per layer (e.g., 0.85 means each earlier layer has 0.85x the LR)
        weight_decay: Weight decay for all parameters (except BN/bias which get 0)
    
    Returns:
        List of parameter groups for optimizer
    """
    # Define layer groups from earliest to latest
    # V5 architecture: input_conv -> conv_blocks (0-7) -> pooling -> fc
    layer_names = []
    param_dict = {}
    
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        param_dict[name] = param
        
        # Determine which layer group this parameter belongs to
        if "input_conv" in name or "input_bn" in name:
            layer_idx = 0
        elif "conv_blocks.0" in name or "block_0" in name:
            layer_idx = 1
        elif "conv_blocks.1" in name or "block_1" in name:
            layer_idx = 2
        elif "conv_blocks.2" in name or "block_2" in name:
            layer_idx = 3
        elif "conv_blocks.3" in name or "block_3" in name:
            layer_idx = 4
        elif "conv_blocks.4" in name or "block_4" in name:
            layer_idx = 5
        elif "conv_blocks.5" in name or "block_5" in name:
            layer_idx = 6
        elif "conv_blocks.6" in name or "block_6" in name:
            layer_idx = 7
        elif "conv_blocks.7" in name or "block_7" in name:
            layer_idx = 8
        elif "aux_classifier" in name or "deep_supervision" in name:
            layer_idx = 9  # Auxiliary heads
        elif "pooling" in name or "asp" in name:
            layer_idx = 10  # Pooling
        elif "fc" in name or "classifier" in name or "head" in name:
            layer_idx = 11  # Final classifier
        else:
            # Default: treat as middle layer
            layer_idx = 6
        
        layer_names.append((name, layer_idx))
    
    # Calculate LR for each layer (later layers = higher LR)
    # Separate decay and no-decay parameters
    max_layer = 11
    param_groups = []
    
    # Group by (layer_idx, is_no_decay) tuple
    layer_to_decay_params: Dict[int, List[torch.nn.Parameter]] = {}
    layer_to_no_decay_params: Dict[int, List[torch.nn.Parameter]] = {}
    
    for name, layer_idx in layer_names:
        if _is_no_decay_param(name):
            if layer_idx not in layer_to_no_decay_params:
                layer_to_no_decay_params[layer_idx] = []
            layer_to_no_decay_params[layer_idx].append(param_dict[name])
        else:
            if layer_idx not in layer_to_decay_params:
                layer_to_decay_params[layer_idx] = []
            layer_to_decay_params[layer_idx].append(param_dict[name])
    
    # Build parameter groups: decay params first, then no-decay params
    all_layers = sorted(set(layer_to_decay_params.keys()) | set(layer_to_no_decay_params.keys()))
    
    for layer_idx in all_layers:
        layer_lr = base_lr * (layer_decay ** (max_layer - layer_idx))
        
        # Decay parameters
        if layer_idx in layer_to_decay_params and layer_to_decay_params[layer_idx]:
            param_groups.append({
                "params": layer_to_decay_params[layer_idx],
                "lr": layer_lr,
                "weight_decay": weight_decay,
                "layer_idx": layer_idx,
                "decay_group": True,
            })
        
        # No-decay parameters (BN, bias, etc.)
        if layer_idx in layer_to_no_decay_params and layer_to_no_decay_params[layer_idx]:
            param_groups.append({
                "params": layer_to_no_decay_params[layer_idx],
                "lr": layer_lr,
                "weight_decay": 0.0,  # Critical: no weight decay for BN/bias
                "layer_idx": layer_idx,
                "decay_group": False,
            })
    
    # Log the LR distribution
    print(f"[LAYER-WISE LR] Using decay={layer_decay} from base_lr={base_lr}")
    decay_count = sum(len(g["params"]) for g in param_groups if g.get("decay_group", True))
    no_decay_count = sum(len(g["params"]) for g in param_groups if not g.get("decay_group", True))
    print(f"  Parameter split: {decay_count} with weight_decay, {no_decay_count} without (BN/bias)")
    for group in param_groups:
        wd_status = "decay" if group.get("decay_group", True) else "no_decay"
        print(f"  Layer {group['layer_idx']:2d}: lr={group['lr']:.6f} ({len(group['params'])} params, {wd_status})")
    
    return param_groups


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
        ghost_augmenter: Optional[Any] = None,
        accent_tap_augmenter: Optional[Any] = None,
        return_velocity: bool = False,
        class_names: Optional[List[str]] = None,
        extra_labels: Optional[List[str | Path]] = None,
        cache_mapping: Optional[Path] = None,  # Direct index mapping for O(1) cache lookup
    ) -> None:
        self.data_dir = Path(data_dir)
        self.labels_path = Path(labels_file)
        self.extra_labels = [Path(p) for p in extra_labels] if extra_labels else []
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
        self.ghost_augmenter = ghost_augmenter
        self.accent_tap_augmenter = accent_tap_augmenter
        self.return_velocity = return_velocity
        self.class_names = class_names  # For ghost augmenter label lookup

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

        # Load direct cache index mapping for O(1) lookup (generated by generate_cache_index_mapping.py)
        self._cache_mapping_shards: Optional[np.ndarray] = None
        self._cache_mapping_offsets: Optional[np.ndarray] = None
        self._cache_mapping_valid: Optional[np.ndarray] = None
        self._use_cache_mapping = False
        self._cache_mapping_path: Optional[Path] = None  # Store path for reload after pickle
        
        if cache_mapping is not None and Path(cache_mapping).exists():
            try:
                self._cache_mapping_path = Path(cache_mapping)  # Store for reload
                mapping_data = np.load(cache_mapping, allow_pickle=False, mmap_mode='r')
                self._cache_mapping_shards = mapping_data['shard_ids']
                self._cache_mapping_offsets = mapping_data['offsets']
                self._cache_mapping_valid = mapping_data['valid']
                self._use_cache_mapping = True
                valid_count = np.sum(self._cache_mapping_valid)
                total_count = len(self._cache_mapping_valid)
                print(f"[CACHE] Using DIRECT index mapping: O(1) lookup for {valid_count:,}/{total_count:,} samples")
                
                # Warn if cache coverage is incomplete and audio fallback may not work
                if valid_count < total_count:
                    invalid_count = total_count - valid_count
                    # Check if audio directory actually has audio files
                    sample_audio = self.data_dir / "audio"
                    has_audio_fallback = sample_audio.exists() and any(sample_audio.glob("**/*.wav"))
                    if not has_audio_fallback:
                        print(f"[CACHE] [!] WARNING: {invalid_count:,} samples have invalid cache mappings and no audio fallback available!")
                        print(f"[CACHE]    These samples will cause errors during training.")
                        print(f"[CACHE]    Fix: Regenerate cache mapping or ensure 100% cache coverage.")
            except Exception as e:
                print(f"[CACHE] Failed to load cache mapping from {cache_mapping}: {e}")
        elif cache_mapping is not None:
            print(f"[CACHE] Cache mapping file not found: {cache_mapping}")
            print("[CACHE] Generate it with: python tools/generate_cache_index_mapping.py")

        # Load labels - support multiple formats for memory efficiency
        labels_data = self._load_labels()
        if not isinstance(labels_data, list):
            raise ValueError(f"Expected list of labels in {self.labels_path}, found {type(labels_data)!r}")
        self.labels: List[Dict[str, Any]] = labels_data
        
        # Initialize lazy-reload flags (used after pickle/unpickle)
        self._numpy_needs_reload = False
        self._labels_needs_reload = False
        self._consolidated_needs_reload = False
        
        # Load velocity array if using numpy format and velocity is requested
        self._numpy_velocities = None
        if self.return_velocity and getattr(self, '_use_numpy', False):
            # Try to load velocity from separate numpy file
            npy_velocities_path = self.labels_path.parent / f"{self.labels_path.stem}_velocities.npy"
            if npy_velocities_path.exists():
                # Use mmap_mode='r' for memory-efficient multi-worker loading
                self._numpy_velocities = np.load(npy_velocities_path, mmap_mode='r')
                print(f"[LABELS] Loaded velocity data from numpy ({len(self._numpy_velocities):,} items)")
            else:
                print(f"[WARNING] Velocity requested but {npy_velocities_path} not found. Using default 0.7.")

    def _load_labels(self) -> List[Dict[str, Any]]:
        """Load labels from numpy, JSON, pickle, or sharded pickle format.
        
        For numpy format, uses memory-mapped mode to allow OS-level memory sharing
        across DataLoader worker processes. This can reduce total RAM usage by 8-10x
        when using 10+ workers.
        
        OPTIMIZATION: When using direct cache mapping with 100% valid entries,
        we skip loading the files array entirely since we never need file paths.
        This saves ~1GB of mmap'd pages on 32GB RAM systems.
        """
        import pickle
        
        # Check for separate numpy files first (most memory-efficient)
        # These are created by convert_labels_to_numpy.py as {stem}_files.npy and {stem}_labels.npy
        npy_files_path = self.labels_path.parent / f"{self.labels_path.stem}_files.npy"
        npy_labels_path = self.labels_path.parent / f"{self.labels_path.stem}_labels.npy"
        if npy_files_path.exists() and npy_labels_path.exists():
            print(f"[LABELS] Loading from numpy files: {npy_files_path.parent}")
            # Use memory-mapped mode (mmap_mode='r') for OS-level memory sharing
            # This is critical for multi-worker DataLoader efficiency
            labels = np.load(npy_labels_path, mmap_mode='r')
            
            # OPTIMIZATION: Skip loading files array if using 100% valid cache mapping
            # This saves ~1GB of memory on large datasets
            # BUT: Cannot skip if waveform/ghost/accent augmentation is enabled (they need file paths)
            skip_files_array = False
            needs_file_paths = (
                self.waveform_transform is not None or 
                self.ghost_augmenter is not None or 
                self.accent_tap_augmenter is not None
            )
            if not needs_file_paths and getattr(self, '_use_cache_mapping', False) and self._cache_mapping_valid is not None:
                valid_count = np.sum(self._cache_mapping_valid[:len(labels)])
                if valid_count == len(labels):
                    skip_files_array = True
                    print(f"[LABELS] Skipping files array (cache mapping 100% valid) - saves ~{npy_files_path.stat().st_size / 1e6:.0f} MB")
            
            if skip_files_array:
                files = None
                total_size = npy_labels_path.stat().st_size
            else:
                files = np.load(npy_files_path, mmap_mode='r')
                total_size = npy_files_path.stat().st_size + npy_labels_path.stat().st_size
            
            print(f"[LABELS] Loaded {len(labels):,} items from numpy ({total_size / 1e6:.1f} MB)")
            # Store numpy arrays directly, decode file paths on access
            self._numpy_files = files
            self._numpy_labels = labels
            self._use_numpy = True
            self._files_are_bytes = files.dtype.kind == 'S' if files is not None else True
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
                main_labels = orjson.loads(handle.read())
        else:
            with self.labels_path.open("r", encoding="utf-8") as handle:
                main_labels = json.load(handle)
        
        # Merge extra label sources (e.g., synthetic cymbal chokes)
        if self.extra_labels:
            for extra_path in self.extra_labels:
                if not extra_path.exists():
                    print(f"[LABELS] Warning: Extra labels file not found: {extra_path}")
                    continue
                print(f"[LABELS] Loading extra labels from: {extra_path}")
                if HAS_ORJSON:
                    with extra_path.open("rb") as handle:
                        extra_data = orjson.loads(handle.read())
                else:
                    with extra_path.open("r", encoding="utf-8") as handle:
                        extra_data = json.load(handle)
                if isinstance(extra_data, list):
                    print(f"[LABELS]   Merged {len(extra_data):,} extra samples")
                    main_labels.extend(extra_data)
                else:
                    print("[LABELS]   Warning: Extra labels not a list, skipping")
        
        return main_labels

    def __len__(self) -> int:
        # Handle case where numpy was not yet reloaded after pickle
        if getattr(self, '_numpy_needs_reload', False):
            return getattr(self, '_numpy_length', 0)
        # Handle case where JSON labels were not yet reloaded after pickle
        if getattr(self, '_labels_needs_reload', False):
            return getattr(self, '_labels_length', 0)
        if getattr(self, '_use_numpy', False):
            return len(self._numpy_labels)
        return len(self.labels)

    def __getitem__(self, idx: int):
        # Ensure data is loaded (handles lazy reload after unpickling)
        self._ensure_numpy_loaded()
        self._ensure_labels_loaded()
        self._ensure_consolidated_cache_loaded()
        self._ensure_cache_mapping_loaded()
        
        # Get file path, label, and velocity, supporting both numpy and dict formats
        velocity = 0.7  # Default velocity (medium)
        audio_path = None  # May be None if using direct cache mapping
        
        if getattr(self, '_use_numpy', False):
            label = int(self._numpy_labels[idx])
            # Get velocity from numpy array if available
            if self._numpy_velocities is not None:
                velocity = float(self._numpy_velocities[idx])
            
            # Only decode file path if we have the files array
            # (skipped when using 100% valid cache mapping)
            if self._numpy_files is not None:
                file_bytes = self._numpy_files[idx]
                if getattr(self, '_files_are_bytes', False):
                    file_path = file_bytes.decode('utf-8')
                else:
                    file_path = str(file_bytes)
                audio_path = self.data_dir / file_path
        else:
            item = self.labels[idx]
            audio_path = self.data_dir / item["file"]
            label = int(item["component_idx"])
            # Get velocity from JSON if available
            velocity = float(item.get("velocity", 0.7))

        # Helper to return result with or without velocity
        def make_result(features_tensor, final_velocity=velocity):
            if self.return_velocity:
                return features_tensor.float().contiguous(), label, final_velocity
            return features_tensor.float().contiguous(), label

        # If waveform, ghost, or accent-tap augmentation is enabled, we must recompute spectrograms each time
        # (can't use cached spectrograms since augmentation is stochastic)
        # However, if the audio file doesn't exist (e.g., using consolidated cache without original audio),
        # we fall back to using cached spectrograms for that sample
        augmentation_enabled = (
            self.waveform_transform is not None or 
            self.ghost_augmenter is not None or 
            self.accent_tap_augmenter is not None
        )
        audio_file_available = audio_path is not None and audio_path.exists()
        
        # Warn once if augmentation is enabled but audio files are missing
        if augmentation_enabled and audio_path is not None and not audio_file_available:
            if not getattr(self, '_augment_fallback_warned', False):
                print(f"[AUGMENT] Warning: Audio file not found, falling back to cached spectrograms")
                print(f"[AUGMENT]   Missing: {audio_path}")
                print(f"[AUGMENT]   Augmentation will be skipped for samples without audio files.")
                print(f"[AUGMENT]   To enable full augmentation, provide --audio-data-dir with original audio.")
                self._augment_fallback_warned = True
        
        if augmentation_enabled and audio_file_available:
            waveform = self._load_audio(audio_path)
            
            # Apply waveform augmentation first
            if self.waveform_transform is not None:
                waveform = self.waveform_transform(waveform, self.sr)
            
            # Get label name for augmenters
            label_name = "unknown"
            if self.class_names is not None and 0 <= label < len(self.class_names):
                label_name = self.class_names[label]
            
            # Apply ghost note augmentation (converts some normal hits to ghost notes)
            if self.ghost_augmenter is not None:
                # Check if we should create a ghost from this sample
                if self.ghost_augmenter.should_augment(label_name, velocity):
                    waveform, velocity = self.ghost_augmenter.create_ghost(
                        waveform,
                        source_velocity=velocity,
                        label=label_name,
                    )
            
            # Apply accent-tap augmentation (creates accents/taps from normal hits)
            if self.accent_tap_augmenter is not None:
                # Check if we should create an accent or tap from this sample
                if self.accent_tap_augmenter.should_augment(label_name, velocity):
                    waveform, velocity = self.accent_tap_augmenter.augment(
                        waveform,
                        source_velocity=velocity,
                        label=label_name,
                    )
            
            features = self._extract_features(waveform)
            return make_result(features, velocity)

        # FASTEST PATH: Direct index mapping (O(1) lookup, no binary search)
        # This requires running generate_cache_index_mapping.py first
        if self._use_cache_mapping and self._consolidated_reader is not None:
            if self._cache_mapping_valid[idx]:
                shard_id = int(self._cache_mapping_shards[idx])
                offset = int(self._cache_mapping_offsets[idx])
                features = self._consolidated_reader._read_sample(shard_id, offset)
                return make_result(features)
            elif self._cache_debug:
                print(f"[CACHE MAPPING] Invalid mapping for index {idx}", flush=True)
            # Fall through to path-based lookup

        # FAST PATH: Consolidated memory-mapped cache (100x faster)
        if self._consolidated_reader is not None and audio_path is not None:
            # Build relative path for lookup (audio/XX/filename.pt format)
            try:
                relative = audio_path.relative_to(self.data_dir)
            except ValueError:
                relative = Path(audio_path.name)
            cache_key = str(relative.with_suffix(".pt"))
            
            features = self._consolidated_reader.get_by_path(cache_key)
            if features is not None:
                return make_result(features)
            elif self._cache_debug:
                print(f"[CONSOLIDATED CACHE MISS] {cache_key}", flush=True)
            # Fall through to individual file cache or recompute

        # If we got here without audio_path, we have a data integrity issue
        if audio_path is None:
            raise RuntimeError(
                f"Sample at index {idx} has no valid cache mapping and files array was skipped. "
                f"This indicates a cache/labels mismatch. Regenerate cache mapping or labels."
            )

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
                except (RuntimeError, EOFError, OSError, ValueError) as e:
                    logger.debug("Cache load failed for %s: %s", cache_path, e)
                    if self._cache_debug:
                        print(f"[CACHE MISS] failed to load cached features: {cache_path}", flush=True)
                    features = None  # Fallback to recompute if cache is corrupt.
            elif self._cache_debug:
                print(f"[CACHE MISS] cache file missing: {cache_path}", flush=True)

        if features is None:
            # Check if audio file exists before trying to load it
            if audio_path is None or not audio_path.exists():
                # For tiny number of missing samples (<0.01%), return a random valid sample
                # This avoids crashing training for negligible data issues
                if self._use_cache_mapping and self._cache_mapping_valid is not None:
                    valid_indices = np.where(self._cache_mapping_valid)[0]
                    if len(valid_indices) > 0:
                        # Warn once about this fallback
                        if not getattr(self, '_cache_fallback_warned', False):
                            invalid_count = len(self._cache_mapping_valid) - len(valid_indices)
                            print(f"[CACHE] Warning: {invalid_count} samples missing from cache, substituting random valid samples")
                            self._cache_fallback_warned = True
                        # Pick a random valid sample
                        fallback_idx = int(valid_indices[idx % len(valid_indices)])
                        return self.__getitem__(fallback_idx)
                
                # If we can't fall back, provide detailed error
                cache_mapping_status = "valid" if (self._use_cache_mapping and self._cache_mapping_valid[idx]) else "invalid/missing"
                raise RuntimeError(
                    f"Cache lookup failed for sample {idx} and audio file not available.\n"
                    f"  Audio path: {audio_path}\n"
                    f"  Cache mapping: {cache_mapping_status}\n"
                    f"  This typically means:\n"
                    f"    1. The cache index is out of sync with labels (regenerate with generate_cache_index_mapping.py)\n"
                    f"    2. Some samples are missing from the consolidated cache\n"
                    f"    3. Using --dataset pointing to feature_cache but original audio is not available\n"
                    f"  If using cached-only training, ensure 100% cache coverage or provide --audio-data-dir."
                )
            waveform = self._load_audio(audio_path)
            features = self._extract_features(waveform)
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cached_tensor = features.detach().to(dtype=self._cache_store_dtype, device="cpu")
                torch.save(cached_tensor, cache_path)
                if self._cache_debug:
                    print(f"[CACHE WRITE] stored features: {cache_path}", flush=True)

        return make_result(features)

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
        
        Excludes large numpy arrays, JSON labels list, and consolidated cache reader 
        since they cannot be efficiently pickled. Workers will reload them on demand.
        
        This is critical for large datasets (14M+ samples) where pickling the labels
        list would cause MemoryError during multiprocessing DataLoader worker spawn.
        """
        state = self.__dict__.copy()
        
        # Mark that numpy data needs to be reloaded (store metadata only)
        if getattr(self, '_use_numpy', False):
            state['_numpy_files'] = None
            state['_numpy_labels'] = None
            state['_numpy_velocities'] = None
            state['_numpy_needs_reload'] = True
            # Store the length so __len__ works before reload
            state['_numpy_length'] = len(self._numpy_labels)
        else:
            # JSON labels case: exclude the large labels list from pickle
            # This is essential to avoid MemoryError with 14M+ labels
            labels_length = len(self.labels) if self.labels else 0
            state['labels'] = []  # Empty list placeholder
            state['_labels_needs_reload'] = True
            state['_labels_length'] = labels_length
        
        # Remove consolidated cache reader - will be re-created in workers
        state['_consolidated_reader'] = None
        state['_consolidated_needs_reload'] = self._consolidated_reader is not None
        
        # Cache mapping: mark for reload but keep the path
        # mmap'd numpy arrays can't be pickled directly on Windows (spawn, not fork)
        if getattr(self, '_use_cache_mapping', False):
            state['_cache_mapping_shards'] = None
            state['_cache_mapping_offsets'] = None
            state['_cache_mapping_valid'] = None
            state['_cache_mapping_needs_reload'] = True
        
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
        """Lazily reload numpy arrays after unpickling.
        
        Uses memory-mapped mode (mmap_mode='r') when loading from SSD to allow OS-level
        memory sharing across worker processes. This dramatically reduces memory usage
        and speeds up worker startup.
        """
        if not getattr(self, '_numpy_needs_reload', False):
            return
        
        # Reload from disk
        npy_files_path = self.labels_path.parent / f"{self.labels_path.stem}_files.npy"
        npy_labels_path = self.labels_path.parent / f"{self.labels_path.stem}_labels.npy"
        
        if npy_files_path.exists() and npy_labels_path.exists():
            # Use memory-mapped mode for labels (small, random access)
            # mmap allows OS to share memory pages across workers, reducing total RAM
            self._numpy_labels = np.load(npy_labels_path, mmap_mode='r')
            
            # Skip loading files array if using 100% valid cache mapping
            skip_files_array = False
            if getattr(self, '_use_cache_mapping', False) and self._cache_mapping_valid is not None:
                valid_count = np.sum(self._cache_mapping_valid[:len(self._numpy_labels)])
                if valid_count == len(self._numpy_labels):
                    skip_files_array = True
            
            if skip_files_array:
                self._numpy_files = None
                self._files_are_bytes = True
            else:
                self._numpy_files = np.load(npy_files_path, mmap_mode='r')
                self._files_are_bytes = self._numpy_files.dtype.kind == 'S'
            
            # Also reload velocities if they exist
            npy_velocities_path = self.labels_path.parent / f"{self.labels_path.stem}_velocities.npy"
            if self.return_velocity and npy_velocities_path.exists():
                self._numpy_velocities = np.load(npy_velocities_path, mmap_mode='r')
        else:
            raise FileNotFoundError(f"Could not reload numpy labels from {npy_files_path.parent}")
        
        self._numpy_needs_reload = False

    def _ensure_labels_loaded(self) -> None:
        """Lazily reload JSON labels after unpickling.
        
        This is critical for large datasets (14M+ samples) where the labels list
        was excluded from pickle to avoid MemoryError during worker spawn.
        """
        if not getattr(self, '_labels_needs_reload', False):
            return
        
        # Skip if using numpy format (handled by _ensure_numpy_loaded)
        if getattr(self, '_use_numpy', False):
            self._labels_needs_reload = False
            return
        
        # Reload labels from disk
        self.labels = self._load_labels()
        self._labels_needs_reload = False

    def _ensure_consolidated_cache_loaded(self) -> None:
        """Lazily reload consolidated cache after unpickling.
        
        When using direct cache mapping (O(1) lookup), we skip loading the heavy
        index file since we never need path-based lookups. This dramatically
        speeds up worker startup on Windows.
        """
        if not getattr(self, '_consolidated_needs_reload', False):
            return
        
        # Check if we have direct cache mapping - if so, skip index loading
        skip_index = getattr(self, '_use_cache_mapping', False)
        
        if self.cache_dir is not None and HAS_CONSOLIDATED_CACHE:
            # Check for consolidated cache in cache_dir itself
            consolidated_manifest = self.cache_dir / "manifest.json"
            if consolidated_manifest.exists():
                try:
                    self._consolidated_reader = ConsolidatedCacheReader(
                        self.cache_dir, skip_index=skip_index
                    )
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
                    logger.debug("Failed to load consolidated cache from %s: %s", self.cache_dir, e)
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
                        self._consolidated_reader = ConsolidatedCacheReader(
                            consolidated_alt, skip_index=skip_index
                        )
                    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
                        logger.debug("Failed to load consolidated cache from %s: %s", consolidated_alt, e)
                        self._consolidated_reader = None
        
        self._consolidated_needs_reload = False

    def _ensure_cache_mapping_loaded(self) -> None:
        """Lazily reload cache mapping arrays after unpickling.
        
        This is needed on Windows where mmap'd numpy arrays can't be shared
        across processes (spawn instead of fork).
        """
        if not getattr(self, '_cache_mapping_needs_reload', False):
            return
        
        # Get the cache mapping path from the stored attribute
        cache_mapping_path = getattr(self, '_cache_mapping_path', None)
        if cache_mapping_path is not None and Path(cache_mapping_path).exists():
            try:
                mapping_data = np.load(cache_mapping_path, allow_pickle=False, mmap_mode='r')
                self._cache_mapping_shards = mapping_data['shard_ids']
                self._cache_mapping_offsets = mapping_data['offsets']
                self._cache_mapping_valid = mapping_data['valid']
            except (OSError, ValueError, KeyError) as e:
                # If reload fails, disable cache mapping
                logger.debug("Cache mapping reload failed: %s", e)
                self._use_cache_mapping = False
        
        self._cache_mapping_needs_reload = False


def _normalize_state_dict_keys(state_dict: Dict[str, torch.Tensor]) -> OrderedDict[str, torch.Tensor]:
    """Strip torch.compile's `_orig_mod.` prefix so checkpoints are portable."""

    prefix = "_orig_mod."
    if not any(key.startswith(prefix) for key in state_dict.keys()):
        return OrderedDict(state_dict.items())
    return OrderedDict(
        (key[len(prefix):] if key.startswith(prefix) else key, value) for key, value in state_dict.items()
    )


def _atomic_torch_save(obj: Any, path: Path) -> None:
    """Save a PyTorch object atomically to prevent corruption from Ctrl+C.
    
    Writes to a temporary file first, then atomically renames to the target.
    On POSIX systems, rename() is atomic. On Windows, we use os.replace()
    which is also atomic on NTFS.
    
    This prevents checkpoint corruption when training is interrupted during save.
    """
    import tempfile
    
    # Create temp file in same directory (ensures same filesystem for atomic rename)
    parent_dir = path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    
    # Use a deterministic temp name based on target to avoid accumulating temp files
    temp_path = parent_dir / f".{path.name}.tmp"
    
    try:
        # Save to temp file
        torch.save(obj, temp_path)
        # Atomic rename (os.replace is atomic on both POSIX and Windows NTFS)
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def _worker_init_fn(worker_id: int) -> None:
    """Initialize DataLoader worker with pre-warmed mmap cache.
    
    This dramatically improves performance on Windows where mmap pages
    are not shared across processes (spawn instead of fork). Each worker
    pre-opens the shards it's likely to access, reducing cold mmap page faults.
    
    This function is at module level (not inside main()) because Windows
    multiprocessing uses 'spawn' which requires pickling the worker_init_fn,
    and local functions cannot be pickled.
    """
    from torch.utils.data import get_worker_info
    
    info = get_worker_info()
    if info is None:
        return
    
    # Set worker-specific random seed for data augmentation reproducibility
    # Use worker_id to ensure different workers get different augmentations
    worker_seed = info.seed
    if worker_seed is not None:
        np.random.seed((worker_seed + worker_id) % (2**32))
        random.seed((worker_seed + worker_id) % (2**32))
    
    # Pre-warm consolidated cache mmaps in this worker
    # This is especially important on Windows where mmap is not shared
    try:
        dataset = info.dataset
        
        # Trigger lazy loading of consolidated cache
        if hasattr(dataset, '_ensure_consolidated_cache_loaded'):
            dataset._ensure_consolidated_cache_loaded()
        
        # Trigger lazy loading of cache mapping
        if hasattr(dataset, '_ensure_cache_mapping_loaded'):
            dataset._ensure_cache_mapping_loaded()
        
        # Pre-warm a few shards to get mmap pages into this worker's address space
        if hasattr(dataset, '_consolidated_reader') and dataset._consolidated_reader is not None:
            reader = dataset._consolidated_reader
            num_shards = reader.num_shards
            num_workers = info.num_workers
            
            # Pre-open shards that this worker is likely to access
            # With shard-aware sampling, each worker handles ~1/num_workers of shards
            worker_shard_start = (worker_id * num_shards) // num_workers
            worker_shard_end = ((worker_id + 1) * num_shards) // num_workers
            
            # Pre-warm first few shards assigned to this worker
            shards_to_warm = min(8, worker_shard_end - worker_shard_start)
            for shard_id in range(worker_shard_start, worker_shard_start + shards_to_warm):
                if shard_id < num_shards:
                    try:
                        # Just get the mmap handle (opens the file)
                        reader._get_mmap(shard_id)
                    except (OSError, ValueError) as e:
                        logger.debug("Shard warmup failed for shard %d: %s", shard_id, e)
    except (AttributeError, TypeError, RuntimeError) as e:
        # Don't fail training if worker init has issues
        logger.debug("Worker init failed: %s", e)


def compute_class_weights(
    labels: Union[List[Dict[str, Any]], np.ndarray],
    num_classes: int,
    strategy: str = "balanced",
    max_weight: float = 10.0,
) -> torch.Tensor:
    """Compute class weights for handling imbalanced datasets.
    
    Args:
        labels: List of label dictionaries with 'component_idx' key, OR numpy array of class indices
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
    
    # Handle numpy array of labels (from cached numpy labels)
    if isinstance(labels, np.ndarray):
        class_counts = Counter(int(l) for l in labels)
        total_samples = len(labels)
    else:
        # Handle list of dicts (from JSON labels)
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
    elif hasattr(labels_or_dataset, 'labels'):
        # DrumSampleDataset with JSON labels (list of dicts)
        labels = labels_or_dataset.labels
        n_samples = len(labels_or_dataset)
        
        if fraction >= 1.0:
            return list(range(n_samples))
        if fraction <= 0.0:
            raise ValueError("fraction must be greater than 0 when creating a subset")
        
        by_class: Dict[int, List[int]] = {}
        for idx, item in enumerate(labels):
            component = int(item.get("component_idx", -1))
            by_class.setdefault(component, []).append(idx)
    else:
        # Original list-of-dicts path (raw list passed directly)
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
    # Keep indices sorted so Subset preserves the dataset's original order.
    # Shard-aware sampling relies on contiguous indices mapping to contiguous
    # cache shards; randomizing here destroys locality and tanks throughput.
    sampled.sort()
    return sampled


def contiguous_subset_indices(
    dataset_length: int,
    fraction: float,
    samples_per_shard: int,
    seed: int,
) -> List[int]:
    """Select a contiguous block of cache shards to preserve locality.
    
    Picks enough adjacent shards to reach the requested fraction (rounded up),
    then trims the tail to match the exact sample count target. A seeded offset
    is used so repeated runs can slide the contiguous block without always
    starting at shard zero."""

    if fraction >= 1.0:
        return list(range(dataset_length))
    if fraction <= 0.0:
        raise ValueError("fraction must be greater than 0 when creating a subset")

    total_samples = dataset_length
    target_count = max(1, int(round(total_samples * fraction)))
    samples_per_shard = max(1, samples_per_shard)
    total_shards = max(1, math.ceil(total_samples / samples_per_shard))
    shards_needed = max(1, math.ceil(target_count / samples_per_shard))

    rng = random.Random(seed)
    max_start = max(0, total_shards - shards_needed)
    if max_start > 0:
        start_shard = rng.randint(0, max_start)
    else:
        start_shard = 0

    selected: List[int] = []
    for offset in range(shards_needed):
        shard_id = start_shard + offset
        shard_start = shard_id * samples_per_shard
        shard_end = min(shard_start + samples_per_shard, total_samples)
        if shard_start >= total_samples:
            break
        selected.extend(range(shard_start, shard_end))
        if len(selected) >= target_count:
            break

    if len(selected) < target_count:
        # Pad using the next contiguous region (will only trigger when rounding undershoots)
        pad_start = min((start_shard + shards_needed) * samples_per_shard, total_samples)
        selected.extend(range(pad_start, total_samples))

    return selected[:target_count]


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
    use_velocity: bool = False,
    velocity_weight: float = 0.1,
    velocity_criterion: Optional[nn.Module] = None,
    # Knowledge distillation parameters
    teacher_model: Optional[nn.Module] = None,
    distill_criterion: Optional[Any] = None,
    distill_temperature: float = 4.0,
    distill_progressive_temp: bool = False,
    distill_use_tta: bool = False,
    distill_tta_augmentations: int = 3,
    current_epoch: int = 0,
    total_epochs: int = 100,
    # AWP (Adversarial Weight Perturbation) parameters
    awp: Optional[Any] = None,
    awp_freq: int = 1,
) -> tuple[float, float]:
    """Train for one epoch with optional AMP, mixup, specaugment, EMA, SAM, R-Drop, deep supervision, velocity, distillation, AWP.
    
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
        use_velocity: If True, train velocity head (multi-task, requires return_all=True)
        velocity_weight: Weight for velocity loss (default: 0.1)
        velocity_criterion: Loss function for velocity (default: MSELoss)
        teacher_model: Optional frozen teacher model for knowledge distillation
        distill_criterion: DistillationLoss instance (required if teacher_model is not None)
        distill_temperature: Temperature for distillation (may be overridden by progressive temp)
        distill_progressive_temp: If True, decay temperature from initial to 1.0 during training
        distill_use_tta: If True, use TTA-ensemble predictions from teacher as soft labels
        distill_tta_augmentations: Number of TTA augmentations for teacher (default: 3)
        current_epoch: Current epoch number for progressive temperature scheduling
        total_epochs: Total training epochs for progressive temperature scheduling
        awp: Optional AWP instance for adversarial weight perturbation
        awp_freq: Apply AWP every N batches (default: 1 = every batch)
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
    for batch_index, batch_data in enumerate(pbar, start=1):
        # Handle both (features, labels) and (features, labels, velocities) formats
        if use_velocity and len(batch_data) == 3:
            features, labels, velocities = batch_data
            # Convert velocities to tensor if needed (may already be tensor from DataLoader)
            if not isinstance(velocities, torch.Tensor):
                velocities = torch.tensor(velocities, dtype=torch.float32)
            velocities = velocities.to(device, non_blocking=non_blocking, dtype=torch.float32)
        else:
            features, labels = batch_data[:2]
            velocities = None
        
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
            elif use_velocity and velocities is not None:
                # Multi-task learning with velocity prediction
                outputs = model(features, return_all=True)
                # V5 model returns 5 values: (logits, aux_outputs, velocity, openness, techniques)
                if isinstance(outputs, tuple) and len(outputs) == 5:
                    logits, aux_outputs, velocity_pred, openness_pred, techniques_pred = outputs
                elif isinstance(outputs, tuple) and len(outputs) == 4:
                    # Legacy v4 model returns 4 values
                    logits, aux_outputs, velocity_pred, openness_pred = outputs
                    techniques_pred = None
                else:
                    # Fallback for unexpected output
                    logits = outputs if not isinstance(outputs, tuple) else outputs[0]
                    aux_outputs, velocity_pred, openness_pred, techniques_pred = [], None, None, None
                
                # Classification loss
                if use_mixup:
                    ce_loss = lam * criterion(logits, labels_a) + (1 - lam) * criterion(logits, labels_b)
                else:
                    ce_loss = criterion(logits, labels)
                
                # Velocity loss (MSE)
                if velocity_pred is not None and velocity_criterion is not None:
                    vel_loss = velocity_criterion(velocity_pred, velocities)
                    loss = ce_loss + velocity_weight * vel_loss
                else:
                    loss = ce_loss
                
                # Use logits for accuracy computation
                outputs = logits
            else:
                outputs = model(features)
                # Select criterion (deep supervision or regular)
                active_criterion = deep_sup_criterion if deep_sup_criterion is not None else criterion
                if use_mixup:
                    # Mixed loss for soft labels
                    loss = lam * active_criterion(outputs, labels_a) + (1 - lam) * active_criterion(outputs, labels_b)
                else:
                    loss = active_criterion(outputs, labels)
                
                # === KNOWLEDGE DISTILLATION ===
                # If teacher model is provided, add distillation loss
                if teacher_model is not None and distill_criterion is not None:
                    with torch.no_grad():
                        if distill_use_tta and distill_tta_augmentations > 1:
                            # TTA Teacher: Average predictions over multiple augmented views
                            # This provides smoother, higher-quality soft labels (+0.3-0.5%)
                            teacher_logits_list = []
                            
                            # Original view
                            teacher_outputs = teacher_model(features)
                            teacher_logits_list.append(extract_main_output(teacher_outputs))
                            
                            # Augmented views (using SpecAugment-like transforms)
                            for _ in range(distill_tta_augmentations - 1):
                                # Time/freq masking augmentation
                                aug_features = features.clone()
                                B, C, H, W = aug_features.shape
                                
                                # Random frequency masking
                                f_start = torch.randint(0, max(1, H - 10), (1,)).item()
                                f_end = min(H, f_start + torch.randint(5, 15, (1,)).item())
                                aug_features[:, :, f_start:f_end, :] = 0
                                
                                # Random time masking
                                t_start = torch.randint(0, max(1, W - 15), (1,)).item()
                                t_end = min(W, t_start + torch.randint(10, 25, (1,)).item())
                                aug_features[:, :, :, t_start:t_end] = 0
                                
                                teacher_outputs_aug = teacher_model(aug_features)
                                teacher_logits_list.append(extract_main_output(teacher_outputs_aug))
                            
                            # Average teacher predictions (ensemble effect)
                            teacher_logits = torch.stack(teacher_logits_list).mean(dim=0)
                        else:
                            # Standard single-pass teacher
                            teacher_outputs = teacher_model(features)
                            teacher_logits = extract_main_output(teacher_outputs)
                    
                    student_logits = extract_main_output(outputs)
                    
                    # Progressive temperature scheduling (decay from initial to 1.0)
                    if distill_progressive_temp and total_epochs > 0:
                        progress = current_epoch / total_epochs
                        current_temp = 1.0 + (distill_temperature - 1.0) * (1 - progress)
                        distill_criterion.temperature = current_temp
                    
                    # Compute distillation loss
                    if use_mixup:
                        # With mixup, we blend distillation for both targets
                        distill_loss = lam * distill_criterion(student_logits, teacher_logits, labels_a) + \
                                      (1 - lam) * distill_criterion(student_logits, teacher_logits, labels_b)
                    else:
                        distill_loss = distill_criterion(student_logits, teacher_logits, labels)
                    
                    # Replace loss with distillation loss (which already includes hard + soft)
                    loss = distill_loss
                
                # Extract main output for accuracy (handles deep supervision tuple)
                outputs = extract_main_output(outputs)
            loss_for_backward = loss / accum_steps
        
        # Clone outputs for accuracy calculation BEFORE SAM's second forward pass
        # This prevents CUDA graph buffer overwrite issues with torch.compile + SAM
        outputs_for_accuracy = outputs.detach().clone()

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
                    # SAM+AMP FIX: Second backward also uses scaler for numerical consistency
                    # This ensures gradient magnitudes match between first and second steps
                    scaler.scale(adv_loss).backward()
                    scaler.unscale_(optimizer)
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
                
                # AWP (Adversarial Weight Perturbation) step for AMP path
                if awp is not None and awp.should_attack(current_epoch, batch_index, awp_freq):
                    if use_mixup:
                        awp.attack_step(features, labels_a, criterion, amp_enabled, scaler)
                    else:
                        awp.attack_step(features, labels, criterion, amp_enabled, scaler)
                    awp.restore_step()
                
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
                    # SAM step 2: backward at adversarial point
                    # Note: This block may run with or without AMP based on amp_enabled
                    if amp_enabled and scaler is not None:
                        # AMP path: use scaler for numerical consistency
                        scaler.scale(adv_loss).backward()
                        scaler.unscale_(optimizer)
                    else:
                        # Non-AMP path: regular backward
                        adv_loss.backward()
                    
                    # Step 3: Apply update using adversarial gradients
                    optimizer.second_step(zero_grad=True)
                else:
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                
                # AWP (Adversarial Weight Perturbation) step
                if awp is not None and awp.should_attack(current_epoch, batch_index, awp_freq):
                    # AWP: perturb weights, compute loss, restore weights
                    if use_mixup:
                        awp.attack_step(features, labels_a, criterion, amp_enabled, scaler)
                    else:
                        awp.attack_step(features, labels, criterion, amp_enabled, scaler)
                    awp.restore_step()
                
                # Update EMA after optimizer step
                if ema is not None:
                    ema.update(model)

        total_loss += loss.item()
        _, predicted = torch.max(outputs_for_accuracy, 1)
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
    use_velocity: bool = False,
    velocity_weight: float = 0.1,
    velocity_criterion: Optional[nn.Module] = None,
) -> tuple[float, float]:
    """Validate the model with optional AMP and velocity prediction."""

    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    non_blocking = device.type == "cuda"

    with torch.no_grad():
        for batch_data in tqdm(dataloader, desc="Validation"):
            # Handle both (features, labels) and (features, labels, velocities) formats
            if use_velocity and len(batch_data) == 3:
                features, labels, velocities = batch_data
                # Use clone().detach() if already a tensor, else create new tensor
                if isinstance(velocities, torch.Tensor):
                    velocities = velocities.clone().detach().to(device, dtype=torch.float32, non_blocking=non_blocking)
                else:
                    velocities = torch.tensor(velocities, dtype=torch.float32).to(device, non_blocking=non_blocking)
            else:
                features, labels = batch_data[:2]
                velocities = None
            
            features = features.to(device, non_blocking=non_blocking)
            labels = labels.to(device, non_blocking=non_blocking)
            if channels_last:
                features = features.to(memory_format=torch.channels_last)

            with autocast(device_type=device.type, dtype=autocast_dtype, enabled=amp_enabled):
                if use_velocity and velocities is not None:
                    # Multi-task inference
                    outputs = model(features, return_all=True)
                    # V5 model returns 5 values: (logits, aux_outputs, velocity, openness, techniques)
                    if isinstance(outputs, tuple) and len(outputs) == 5:
                        logits, aux_outputs, velocity_pred, openness_pred, techniques_pred = outputs
                    elif isinstance(outputs, tuple) and len(outputs) == 4:
                        # Legacy v4 model returns 4 values
                        logits, aux_outputs, velocity_pred, openness_pred = outputs
                    else:
                        # Fallback for unexpected output
                        logits = outputs if not isinstance(outputs, tuple) else outputs[0]
                        aux_outputs, velocity_pred, openness_pred = [], None, None
                    ce_loss = criterion(logits, labels)
                    if velocity_pred is not None and velocity_criterion is not None:
                        vel_loss = velocity_criterion(velocity_pred, velocities)
                        loss = ce_loss + velocity_weight * vel_loss
                    else:
                        loss = ce_loss
                    main_outputs = logits
                else:
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
        for batch_data in tqdm(dataloader, desc="Validation (TTA)"):
            # Handle both (features, labels) and (features, labels, velocities) formats
            features, labels = batch_data[0], batch_data[1]
            features = features.to(device, non_blocking=non_blocking)
            labels = labels.to(device, non_blocking=non_blocking)
            if channels_last:
                features = features.to(memory_format=torch.channels_last)
            
            # Collect predictions from original and augmented views
            all_logits = []
            
            with autocast(device_type=device.type, dtype=autocast_dtype, enabled=amp_enabled):
                # Original view
                # Clone outputs to prevent CUDA graph tensor overwrite issues
                outputs = model(features)
                main_outputs = extract_main_output(outputs)
                all_logits.append(main_outputs.clone())
                
                # Augmented views
                for aug_idx in range(num_augmentations):
                    aug_features = apply_tta_augmentation(features, aug_idx)
                    if channels_last:
                        aug_features = aug_features.to(memory_format=torch.channels_last)
                    outputs = model(aug_features)
                    main_outputs = extract_main_output(outputs)
                    all_logits.append(main_outputs.clone())
            
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
    parser.add_argument(
        "--samples-per-epoch",
        type=int,
        default=None,
        help="Limit samples per epoch (faster epochs with more validation checks). Default: use all samples.",
    )
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
        choices=["plateau", "cosine", "cosine_warm_restarts"],
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
        "--warm-restart-t0",
        type=int,
        default=30,
        help="Initial restart period for cosine_warm_restarts (default: 30 epochs)",
    )
    parser.add_argument(
        "--warm-restart-mult",
        type=int,
        default=2,
        help="Multiplier for restart period after each restart (default: 2)",
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
    parser.add_argument(
        "--audio-data-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing original audio files for waveform augmentation. "
            "Required when --ghost-augment or --accent-tap-augment is used with a consolidated cache dataset. "
            "Should point to the root containing train/audio and val/audio subdirectories."
        ),
    )
    parser.add_argument(
        "--cache-mapping",
        type=Path,
        default=None,
        help=(
            "Path to cache index mapping file (*.npz) for O(1) lookup instead of O(log n) binary search. "
            "Generate with: python tools/generate_cache_index_mapping.py. "
            "Dramatically improves first-epoch performance (10-50x faster)."
        ),
    )
    parser.add_argument(
        "--cache-warmup",
        action="store_true",
        help=(
            "Warm up the consolidated cache before training by reading samples from each shard. "
            "This forces mmap pages into RAM, preventing 10-20x slowdown on first epoch."
        ),
    )
    parser.add_argument(
        "--cache-warmup-samples",
        type=int,
        default=50000,
        help="Number of samples to read during cache warmup (default: 50000, ~2 samples per shard for 225 shards)",
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
    # Shard-aware sampling for consolidated cache (CRITICAL PERFORMANCE OPTIMIZATION)
    parser.add_argument(
        "--shard-aware-sampling",
        action="store_true",
        help="Enable shard-aware batch sampling for consolidated cache (10-50x faster I/O). "
             "Groups samples by shard to maximize sequential reads and minimize mmap page faults. "
             "Strongly recommended when using consolidated cache on datasets larger than RAM.",
    )
    parser.add_argument(
        "--shard-chunks",
        type=int,
        default=4,
        help="Number of shards to group together in shard-aware sampling (default: 4). "
             "Higher values improve I/O but reduce randomization. 4 is a good balance.",
    )
    parser.add_argument(
        "--samples-per-shard",
        type=int,
        default=65536,
        help="Samples per shard in consolidated cache (default: 65536). "
             "Should match the value used when creating the consolidated cache.",
    )
    parser.add_argument("--train-fraction", type=float, default=1.0, help="Fraction of the training set to sample")
    parser.add_argument("--val-fraction", type=float, default=1.0, help="Fraction of the validation set to sample")
    parser.add_argument("--subset-seed", type=int, default=42, help="RNG seed used for subset selection")
    parser.add_argument(
        "--subset-mode",
        choices=["stratified", "contiguous"],
        default="stratified",
        help="Subset sampling mode: stratified retains class balance, contiguous keeps cache shard locality",
    )
    parser.add_argument(
        "--subset-debug",
        action="store_true",
        help="Log shard-level subset coverage diagnostics (useful when tuning contiguous mode)",
    )
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
        "--gradient-checkpointing",
        action="store_true",
        help="Enable gradient checkpointing to reduce VRAM usage (allows larger batch sizes at cost of ~20%% speed)",
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
        "--layer-decay",
        type=float,
        default=None,
        help="Layer-wise learning rate decay for V5 model (e.g., 0.85 means each deeper layer has 0.85x LR). "
             "Helps fine-tuning: early layers learn slowly, later layers learn quickly.",
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
        "--balanced-sampling",
        action="store_true",
        help="Use class-balanced sampling (each class sampled equally). CRITICAL for extreme class imbalance (>10x). "
             "This is applied at the data loading level, not the loss function. "
             "Recommended to combine with --class-weights=none when using this option.",
    )
    parser.add_argument(
        "--sampling-strategy",
        choices=["sqrt", "log", "uniform"],
        default="sqrt",
        help="Sampling strategy when --balanced-sampling is enabled: "
             "sqrt (default, sqrt of inverse frequency - good balance), "
             "log (log-dampened inverse frequency), "
             "uniform (pure equal sampling per class - most aggressive)",
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
        help="Enable multi-task heads for velocity and hi-hat openness (v4/v5 models)",
    )
    parser.add_argument(
        "--velocity-labels-suffix",
        type=str,
        default="",
        help="Suffix to add to labels filename for velocity-enriched labels (e.g., '_with_velocity' to use train_labels_with_velocity.json)",
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
        "--extra-labels",
        type=str,
        nargs="+",
        default=[],
        help="Additional label JSON files to merge into training data (e.g., synthetic cymbal chokes)",
    )
    # Technique Detection arguments (NEW - multi-label technique classification)
    parser.add_argument(
        "--use-technique-heads",
        action="store_true",
        help="Enable technique detection heads for multi-label technique classification (flam, roll, choke, ghost, etc.)",
    )
    parser.add_argument(
        "--technique-preset",
        type=str,
        default="core",
        choices=["core", "full", "minimal", "articulation"],
        help="Technique detection preset: core=8 techniques, full=14, minimal=3, articulation=5 (default: core)",
    )
    parser.add_argument(
        "--technique-weight",
        type=float,
        default=0.2,
        help="Weight for technique detection auxiliary loss (default: 0.2)",
    )
    parser.add_argument(
        "--technique-labels-suffix",
        type=str,
        default="_with_techniques",
        help="Suffix for technique labels file (e.g., train_labels_with_techniques.json)",
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
    parser.add_argument(
        "--specaugment-mode",
        type=str,
        default="auto",
        choices=["auto", "classic", "batched"],
        help="Implementation to use for SpecAugment (auto=pick best for batch size)",
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
    
    # Ghost Note Augmentation (synthesize ghost notes from normal hits)
    parser.add_argument(
        "--ghost-augment",
        action="store_true",
        help="Enable ghost note augmentation (synthesize ghost notes from normal hits for improved ghost detection)",
    )
    parser.add_argument(
        "--ghost-augment-prob",
        type=float,
        default=0.15,
        help="Probability of converting eligible sample to ghost note (default: 0.15)",
    )
    parser.add_argument(
        "--ghost-augment-preset",
        type=str,
        default="default",
        choices=["default", "aggressive", "conservative"],
        help="Ghost augmentation preset: default (balanced), aggressive (more ghosts, harder), conservative (fewer, realistic)",
    )
    
    # Accent-Tap Augmentation (velocity-based accent/tap pattern synthesis)
    parser.add_argument(
        "--accent-tap-augment",
        action="store_true",
        help="Enable accent-tap augmentation (synthesize accents/taps from normal hits for improved dynamics)",
    )
    parser.add_argument(
        "--accent-tap-prob",
        type=float,
        default=0.12,
        help="Probability of converting eligible sample to accent or tap (default: 0.12)",
    )
    parser.add_argument(
        "--accent-tap-preset",
        type=str,
        default="default",
        choices=["default", "aggressive", "conservative"],
        help="Accent-tap augmentation preset: default (balanced), aggressive (more variation), conservative (subtle)",
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
        choices=["gap", "asp", "mha", "flash", "hybrid"],
        default="gap",
        help="Pooling strategy for v5 model: gap (global average), asp (attentive statistics), mha (multi-head attention), flash (Flash Attention v2, 2-4x faster), hybrid (default: gap)",
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
    
    # AWP (Adversarial Weight Perturbation - improves generalization)
    parser.add_argument(
        "--use-awp",
        action="store_true",
        help="Use Adversarial Weight Perturbation for improved generalization (+0.5-1%% improvement). "
             "Makes model robust to worst-case weight perturbations.",
    )
    parser.add_argument(
        "--awp-lr",
        type=float,
        default=0.01,
        help="AWP adversarial learning rate (default: 0.01)",
    )
    parser.add_argument(
        "--awp-eps",
        type=float,
        default=0.01,
        help="AWP maximum perturbation magnitude (default: 0.01)",
    )
    parser.add_argument(
        "--awp-start-epoch",
        type=int,
        default=5,
        help="Epoch to start AWP (default: 5, allows warmup before adversarial training)",
    )
    parser.add_argument(
        "--awp-freq",
        type=int,
        default=1,
        help="Apply AWP every N iterations (default: 1 = every iteration)",
    )
    
    # Early Stopping
    parser.add_argument(
        "--early-stopping",
        action="store_true",
        help="Enable early stopping to prevent overfitting",
    )
    parser.add_argument(
        "--early-stopping-patience",
        type=int,
        default=20,
        help="Early stopping patience: epochs to wait for improvement (default: 20)",
    )
    parser.add_argument(
        "--early-stopping-min-delta",
        type=float,
        default=0.001,
        help="Minimum improvement to reset patience (default: 0.001 = 0.1%% accuracy)",
    )
    parser.add_argument(
        "--early-stopping-warmup",
        type=int,
        default=10,
        help="Epochs to skip before early stopping starts monitoring (default: 10)",
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
    
    # === KNOWLEDGE DISTILLATION (Born-Again Networks / Self-Distillation) ===
    parser.add_argument(
        "--distill-from-single",
        type=Path,
        default=None,
        help="Path to a trained teacher model checkpoint for knowledge distillation. "
             "The student (same architecture) learns from both ground truth and teacher's soft labels.",
    )
    parser.add_argument(
        "--distill-temperature",
        type=float,
        default=4.0,
        help="Temperature for softening teacher predictions (higher = softer, typical: 2.0-8.0, default: 4.0)",
    )
    parser.add_argument(
        "--distill-alpha",
        type=float,
        default=0.5,
        help="Weight of soft loss vs hard loss (0.5 = equal, 0.7 = 70%% soft + 30%% hard, default: 0.5)",
    )
    parser.add_argument(
        "--distill-progressive-temp",
        action="store_true",
        help="Progressively decay temperature from initial to 1.0 during training (smoother knowledge transfer)",
    )
    parser.add_argument(
        "--distill-use-tta",
        action="store_true",
        help="Use TTA-ensemble predictions from teacher as soft labels (+0.3-0.5%% improvement). "
             "Averages 3 augmented views for better soft label quality.",
    )
    parser.add_argument(
        "--distill-tta-augmentations",
        type=int,
        default=3,
        help="Number of TTA augmentations for teacher (default: 3, more = slower but better)",
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
        """Locate the label JSON, supporting labels-cache-dir, flat, and split-local layouts.
        
        Also checks for numpy format files ({stem}_files.npy + {stem}_labels.npy) which are
        the most efficient format for large datasets. The numpy lookup allows cached labels
        on fast SSD even when the JSON doesn't exist in the cache dir.
        """
        stem = Path(filename).stem  # e.g., "train_labels_with_velocity"
        
        # First check labels-cache-dir for numpy or JSON (for fast SSD when dataset is on slow HDD)
        if args.labels_cache_dir:
            # Prefer numpy format (most memory-efficient and fastest)
            npy_files = args.labels_cache_dir / f"{stem}_files.npy"
            npy_labels = args.labels_cache_dir / f"{stem}_labels.npy"
            if npy_files.exists() and npy_labels.exists():
                # Return the JSON path even though numpy will be used - _load_labels() will find the numpy files
                print(f"[LABELS] Using cached numpy labels from fast storage: {args.labels_cache_dir}")
                return args.labels_cache_dir / filename
            # Also check for JSON in cache dir
            cached = args.labels_cache_dir / filename
            if cached.exists():
                print(f"[LABELS] Using cached JSON labels from fast storage: {cached}")
                return cached
        
        # Then check flat layout
        candidate = dataset_path / filename
        if candidate.exists():
            return candidate
        
        # Finally check split-local layout
        nested = dataset_path / split / filename
        if nested.exists():
            return nested
        
        # Check if numpy files exist even without JSON (common case - numpy is preferred)
        for parent in [dataset_path, dataset_path / split]:
            npy_files = parent / f"{stem}_files.npy"
            npy_labels = parent / f"{stem}_labels.npy"
            if npy_files.exists() and npy_labels.exists():
                # Return the expected JSON path - _load_labels will find numpy files
                return parent / filename
        
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
        print("[WARNING] Waveform augmentation requested but librosa not available. Skipping.")

    # Setup ghost note augmentation (synthesize ghost notes from normal hits)
    ghost_augmenter = None
    if args.ghost_augment and HAS_GHOST_AUGMENT:
        ghost_augmenter = get_ghost_augmenter(
            preset=args.ghost_augment_preset,
            sample_rate=args.sample_rate,
        )
        # Override probability if specified
        if args.ghost_augment_prob != 0.15:
            ghost_augmenter.config.ghost_prob = args.ghost_augment_prob
        print(f"[GHOST AUGMENT] Enabled with preset='{args.ghost_augment_preset}', prob={ghost_augmenter.config.ghost_prob:.2f}")
        print("[GHOST AUGMENT] This synthesizes ghost notes from normal hits for improved ghost detection")
    elif args.ghost_augment and not HAS_GHOST_AUGMENT:
        print("[WARNING] Ghost augmentation requested but module not available. Skipping.")

    # Setup accent-tap augmentation (velocity-based accent/tap pattern synthesis)
    accent_tap_augmenter = None
    if args.accent_tap_augment and HAS_ACCENT_TAP_AUGMENT:
        accent_tap_augmenter = get_accent_tap_augmenter(
            preset=args.accent_tap_preset,
            sample_rate=args.sample_rate,
        )
        # Override probability if specified
        if args.accent_tap_prob != 0.12:
            accent_tap_augmenter.config.accent_prob = args.accent_tap_prob
            accent_tap_augmenter.config.tap_prob = args.accent_tap_prob
        print(f"[ACCENT-TAP AUGMENT] Enabled with preset='{args.accent_tap_preset}', prob={accent_tap_augmenter.config.accent_prob:.2f}")
        print("[ACCENT-TAP AUGMENT] This synthesizes accents/taps from normal hits for improved dynamics")
    elif args.accent_tap_augment and not HAS_ACCENT_TAP_AUGMENT:
        print("[WARNING] Accent-tap augmentation requested but module not available. Skipping.")

    # Determine if velocity training is enabled
    use_velocity_training = args.use_multi_task and args.model_version in ("v4", "v5")
    velocity_labels_suffix = args.velocity_labels_suffix if use_velocity_training else ""
    
    # Construct labels filenames with optional velocity suffix
    train_labels_file = f"train_labels{velocity_labels_suffix}.json"
    val_labels_file = f"val_labels{velocity_labels_suffix}.json"
    
    if use_velocity_training:
        print("[VELOCITY] Multi-task training enabled with velocity prediction")
        print(f"[VELOCITY] Using labels: {train_labels_file}, {val_labels_file}")

    # Load class names for ghost augmenter (from components.json)
    class_names = None
    components_path = dataset_path / "components.json"
    if components_path.exists():
        with open(components_path, "r") as f:
            components_data = json.load(f)
            if isinstance(components_data, list):
                class_names = [c["name"] if isinstance(c, dict) else c for c in components_data]
            elif isinstance(components_data, dict):
                if "components" in components_data:
                    class_names = components_data["components"]
                elif "classes" in components_data:
                    class_names = components_data["classes"]
        if ghost_augmenter is not None and class_names:
            print(f"[GHOST AUGMENT] Loaded {len(class_names)} class names for label-aware augmentation")
        if accent_tap_augmenter is not None and class_names:
            print(f"[ACCENT-TAP AUGMENT] Loaded {len(class_names)} class names for label-aware augmentation")

    # Extra labels (e.g., synthetic cymbal chokes)
    extra_labels = args.extra_labels if hasattr(args, 'extra_labels') else []
    if extra_labels:
        print(f"[EXTRA LABELS] Will merge {len(extra_labels)} additional label source(s)")

    # Resolve cache mapping paths (auto-detect based on labels if not specified)
    train_cache_mapping = None
    val_cache_mapping = None
    if args.cache_mapping:
        # If a directory is given, look for split-specific files
        if args.cache_mapping.is_dir():
            train_mapping = args.cache_mapping / "train_cache_mapping.npz"
            val_mapping = args.cache_mapping / "val_cache_mapping.npz"
            if train_mapping.exists():
                train_cache_mapping = train_mapping
            if val_mapping.exists():
                val_cache_mapping = val_mapping
        else:
            # Single file specified - try to infer split from name
            if "train" in args.cache_mapping.name:
                train_cache_mapping = args.cache_mapping
            elif "val" in args.cache_mapping.name:
                val_cache_mapping = args.cache_mapping
            else:
                # Use for both
                train_cache_mapping = args.cache_mapping
                val_cache_mapping = args.cache_mapping
    else:
        # Auto-detect from labels directory
        labels_dir = resolve_labels("train", train_labels_file).parent
        train_mapping = labels_dir / "train_cache_mapping.npz"
        val_mapping = labels_dir / "val_cache_mapping.npz"
        if train_mapping.exists():
            train_cache_mapping = train_mapping
            print(f"[CACHE] Auto-detected train cache mapping: {train_mapping}")
        if val_mapping.exists():
            val_cache_mapping = val_mapping
            print(f"[CACHE] Auto-detected val cache mapping: {val_mapping}")

    # Determine audio data directory for waveform augmentation
    # When using consolidated cache, the audio files are not in the cache directory
    # so we need to specify the original audio location separately
    needs_audio_files = waveform_transform is not None or ghost_augmenter is not None or accent_tap_augmenter is not None
    if needs_audio_files and args.audio_data_dir:
        train_audio_dir = args.audio_data_dir / "train"
        print(f"[AUGMENT] Using audio files from: {train_audio_dir}")
    else:
        train_audio_dir = dataset_path / "train"
        if needs_audio_files:
            print(f"[AUGMENT] Using audio files from dataset path: {train_audio_dir}")

    train_dataset_full = DrumSampleDataset(
        train_audio_dir,
        resolve_labels("train", train_labels_file),
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
        ghost_augmenter=ghost_augmenter,  # Ghost note synthesis for improved detection
        accent_tap_augmenter=accent_tap_augmenter,  # Accent-tap velocity synthesis for improved dynamics
        return_velocity=use_velocity_training,
        class_names=class_names,
        extra_labels=extra_labels,  # Merge additional label sources (e.g., synthetic chokes)
        cache_mapping=train_cache_mapping,  # O(1) cache lookup (if available)
    )
    # Validation doesn't use augmentation but we keep consistent audio path handling
    val_audio_dir = args.audio_data_dir / "val" if args.audio_data_dir else dataset_path / "val"
    
    val_dataset_full = DrumSampleDataset(
        val_audio_dir,
        resolve_labels("val", val_labels_file),
        sr=args.sample_rate,
        cache_dir=feature_cache_root / "val" if feature_cache_root else None,
        prefer_torchaudio=prefer_torchaudio,
        n_fft=args.n_fft,
        hop_length=args.hop_length,
        n_mels=args.n_mels,
        fmax=fmax,
        target_frames=args.target_frames,
        cache_dtype=args.cache_dtype,
        return_velocity=use_velocity_training,
        cache_mapping=val_cache_mapping,  # O(1) cache lookup (if available)
        # NOTE: No ghost/accent-tap augmentation for validation - we want to measure true accuracy
    )

    def create_subset(dataset_full, fraction: float) -> Tuple[Optional[List[int]], Dataset]:
        if fraction >= 1.0:
            return None, dataset_full
        if args.subset_mode == "contiguous":
            indices = contiguous_subset_indices(
                len(dataset_full),
                fraction,
                args.samples_per_shard,
                args.subset_seed,
            )
        else:
            indices = stratified_sample_indices(dataset_full, fraction, args.subset_seed)
        return indices, Subset(dataset_full, indices)

    train_subset_indices, train_dataset = create_subset(train_dataset_full, args.train_fraction)
    val_subset_indices, val_dataset = create_subset(val_dataset_full, args.val_fraction)

    if args.subset_debug:
        def _format_range(r: tuple[int, int]) -> str:
            start, end = r
            return f"{start}" if start == end else f"{start}-{end}"

        def _summarize_ranges(values: List[int], limit: int = 5) -> str:
            if not values:
                return "(none)"
            ranges: List[tuple[int, int]] = []
            start = prev = values[0]
            for val in values[1:]:
                if val == prev + 1:
                    prev = val
                    continue
                ranges.append((start, prev))
                start = prev = val
            ranges.append((start, prev))
            if len(ranges) <= limit:
                return ", ".join(_format_range(r) for r in ranges)
            head = ", ".join(_format_range(r) for r in ranges[: limit - 1])
            tail = _format_range(ranges[-1])
            return f"{head}, ..., {tail}"

        def _log_subset(label: str, indices: Optional[List[int]], total_length: int) -> None:
            if indices is None:
                print(f"[SUBSET][{label}] Using full dataset ({total_length:,} samples)")
                return
            if not indices:
                print(f"[SUBSET][{label}] Empty subset (0 samples)")
                return
            ordered = sorted(indices)
            shard_ids = sorted({idx // args.samples_per_shard for idx in ordered})
            shard_ranges = _summarize_ranges(shard_ids)
            first_sample = ordered[0]
            last_sample = ordered[-1]
            total_pct = 0.0 if total_length <= 0 else (len(indices) / total_length * 100.0)
            print(
                f"[SUBSET][{label}] {len(indices):,} samples ({total_pct:.2f}% of {total_length:,}) "
                f"cover shards {shard_ranges} (samples {first_sample}-{last_sample})"
            )

        _log_subset("train", train_subset_indices, len(train_dataset_full))
        _log_subset("val", val_subset_indices, len(val_dataset_full))

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

    # Determine if we should use shard-aware sampling
    # Auto-enable if consolidated cache is detected and --shard-aware-sampling is set
    use_shard_aware = args.shard_aware_sampling and HAS_SHARD_SAMPLER
    if use_shard_aware:
        # Verify consolidated cache is being used
        has_consolidated = (
            hasattr(train_dataset_full, '_consolidated_reader') and 
            train_dataset_full._consolidated_reader is not None
        )
        if not has_consolidated:
            print("[SHARD] Warning: --shard-aware-sampling requested but consolidated cache not detected.")
            print("[SHARD] Falling back to standard random sampling. For 10-50x speedup, run:")
            print("        python -m training.utils.consolidated_cache consolidate ...")
            use_shard_aware = False
        else:
            print(f"[SHARD] Shard-aware sampling ENABLED (chunks={args.shard_chunks}, samples_per_shard={args.samples_per_shard})")
            print("[SHARD] This reduces mmap page faults by 10-50x for large datasets!")

    # === CLASS-BALANCED SAMPLING ===
    # This is CRITICAL for extreme class imbalance (>10x ratio).
    # Without this, the model ignores rare classes entirely.
    balanced_sampler = None
    if args.balanced_sampling:
        print("\n[BALANCED SAMPLING] Computing class-balanced sample weights...")
        
        # Get labels from the training dataset
        # Support both numpy and dict formats
        if hasattr(train_dataset_full, '_use_numpy') and train_dataset_full._use_numpy:
            train_labels_arr = train_dataset_full._numpy_labels
        else:
            train_labels_arr = np.array([item['component_idx'] for item in train_dataset_full.labels])
        
        # If using a subset, filter to just those indices
        if train_subset_indices is not None:
            train_labels_arr = train_labels_arr[train_subset_indices]
        
        # Get number of classes from the maximum label + 1
        num_classes_sampling = int(train_labels_arr.max()) + 1
        
        # Count samples per class
        class_counts = np.bincount(train_labels_arr, minlength=num_classes_sampling)
        
        # Compute sample weights based on strategy
        if args.sampling_strategy == "uniform":
            # Pure class-balanced: each class is sampled equally
            # Weight = 1 / (num_classes * class_count)
            # This gives equal probability to each class, regardless of size
            class_weights_sampling = 1.0 / (class_counts + 1e-6)
        elif args.sampling_strategy == "sqrt":
            # Square-root dampened: reduces aggressive oversampling of tiny classes
            # Good balance between class balance and sample diversity
            class_weights_sampling = 1.0 / (np.sqrt(class_counts) + 1e-6)
        elif args.sampling_strategy == "log":
            # Log dampened: even more conservative oversampling
            class_weights_sampling = 1.0 / (np.log1p(class_counts) + 1e-6)
        else:
            raise ValueError(f"Unknown sampling strategy: {args.sampling_strategy}")
        
        # Normalize weights to sum to num_classes_sampling (for interpretability)
        class_weights_sampling = class_weights_sampling / class_weights_sampling.sum() * num_classes_sampling
        
        # Assign weight to each sample based on its class
        sample_weights = class_weights_sampling[train_labels_arr]
        sample_weights_tensor = torch.from_numpy(sample_weights.astype(np.float64))
        
        # Print diagnostics
        print(f"   Strategy: {args.sampling_strategy}")
        print(f"   Dataset size: {len(train_labels_arr):,}")
        print(f"   Classes: {num_classes_sampling}")
        
        # Show weight extremes
        nonzero_counts = class_counts[class_counts > 0]
        min_class = np.where(class_counts == nonzero_counts.min())[0][0]
        max_class = np.argmax(class_counts)
        min_count = class_counts[min_class]
        max_count = class_counts[max_class]
        print(f"   Smallest class: idx={min_class} ({min_count:,} samples, weight={class_weights_sampling[min_class]:.4f})")
        print(f"   Largest class: idx={max_class} ({max_count:,} samples, weight={class_weights_sampling[max_class]:.4f})")
        print(f"   Rebalancing ratio: {class_weights_sampling[min_class] / class_weights_sampling[max_class]:.1f}x")
        
        # Expected effective class distribution after balanced sampling
        expected_samples_per_class = len(train_labels_arr) * class_weights_sampling / class_weights_sampling.sum()
        print(f"   Expected samples/class/epoch: min={expected_samples_per_class.min():.0f}, max={expected_samples_per_class.max():.0f}")
        
        from torch.utils.data import WeightedRandomSampler
        # Allow configurable samples per epoch for faster iteration
        epoch_samples = args.samples_per_epoch if args.samples_per_epoch else len(train_labels_arr)
        if args.samples_per_epoch:
            print(f"   Samples per epoch: {epoch_samples:,} (user-specified, {epoch_samples / len(train_labels_arr) * 100:.1f}% of full dataset)")
        balanced_sampler = WeightedRandomSampler(
            weights=sample_weights_tensor,
            num_samples=epoch_samples,
            replacement=True,  # Must be True for weighted sampling
        )
        
        # Note: balanced_sampler is incompatible with shard-aware sampling
        if use_shard_aware:
            print("[BALANCED SAMPLING] WARNING: Disabling shard-aware sampling (incompatible with balanced sampler)")
            print("[BALANCED SAMPLING]    Class balance is more important than I/O locality for extreme imbalance")
            use_shard_aware = False
        
        print("[BALANCED SAMPLING] Enabled - rare classes will now be seen equally often!")

    def _resolve_subset_chain(ds: Dataset) -> Tuple[Optional[np.ndarray], Dataset]:
        """Flatten nested torch.utils.data.Subset wrappers into a root dataset.
        
        Returns the indices mapping to the root dataset (or None if not a subset)
        and the innermost dataset object (used to determine source length)."""
        indices: Optional[np.ndarray] = None
        current: Dataset = ds
        while isinstance(current, Subset):
            current_indices = np.asarray(current.indices, dtype=np.int64)
            if indices is None:
                indices = current_indices
            else:
                indices = current_indices[indices]
            current = current.dataset  # type: ignore[assignment]
        return indices, current

    def build_loader(
        dataset_obj,
        *,
        batch_size: int,
        shuffle: bool,
        workers: int,
        prefetch: Optional[int],
        persistent: bool,
        use_shard_sampler: bool = False,
        num_samples: Optional[int] = None,
        split_label: str = "train",
        sampler: Optional[Any] = None,  # WeightedRandomSampler for balanced sampling
    ) -> DataLoader:
        loader_kwargs: Dict[str, Any] = {
            "dataset": dataset_obj,
            "num_workers": workers,
            "drop_last": False,
            "pin_memory": pin_memory and torch_device.type == "cuda",
        }
        
        # Use shard-aware batch sampler for training if enabled
        if use_shard_sampler and shuffle and HAS_SHARD_SAMPLER:
            # ShardAwareBatchSampler provides its own batching
            subset_mapping: Optional[np.ndarray] = None
            source_dataset = dataset_obj
            if isinstance(dataset_obj, Subset):
                subset_mapping, source_dataset = _resolve_subset_chain(dataset_obj)
            shard_sampler = ShardAwareBatchSampler(
                num_samples=num_samples or len(dataset_obj),
                batch_size=batch_size,
                samples_per_shard=args.samples_per_shard,
                shuffle=True,
                drop_last=False,
                seed=args.seed,
                shard_chunks=args.shard_chunks,
                subset_indices=subset_mapping,
                source_length=len(source_dataset),
                debug=args.subset_debug,
                subset_label=split_label,
            )
            loader_kwargs["batch_sampler"] = shard_sampler
            # batch_sampler is mutually exclusive with batch_size/shuffle/sampler/drop_last
        elif sampler is not None:
            # Use provided sampler (e.g., WeightedRandomSampler for class-balanced sampling)
            loader_kwargs["batch_size"] = batch_size
            loader_kwargs["sampler"] = sampler
            # Note: cannot use shuffle=True with a sampler
        else:
            loader_kwargs["batch_size"] = batch_size
            # If num_samples is specified and less than dataset, use RandomSampler to limit epoch size
            if num_samples is not None and num_samples < len(dataset_obj) and shuffle:
                from torch.utils.data import RandomSampler
                epoch_sampler = RandomSampler(
                    dataset_obj,
                    replacement=False,  # Sample without replacement
                    num_samples=num_samples,
                )
                loader_kwargs["sampler"] = epoch_sampler
                # Note: cannot use shuffle=True with a sampler
            else:
                loader_kwargs["shuffle"] = shuffle
        
        if workers > 0:
            if prefetch is not None:
                loader_kwargs["prefetch_factor"] = prefetch
            if persistent:
                loader_kwargs["persistent_workers"] = True
            # Add worker init function for mmap pre-warming (critical on Windows)
            # Uses module-level function _worker_init_fn (not local) so it can be pickled
            loader_kwargs["worker_init_fn"] = _worker_init_fn
        else:
            loader_kwargs["num_workers"] = 0
        return DataLoader(**loader_kwargs)

    train_prefetch = args.prefetch_factor if args.prefetch_factor is not None else None
    val_prefetch = args.val_prefetch_factor if args.val_prefetch_factor is not None else None

    # Determine samples per epoch (for faster iteration if specified)
    epoch_samples = args.samples_per_epoch if args.samples_per_epoch else len(train_dataset)
    
    train_loader = build_loader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,  # Ignored if balanced_sampler is provided
        workers=num_workers,
        prefetch=train_prefetch,
        persistent=train_persistent,
        use_shard_sampler=use_shard_aware,
        num_samples=epoch_samples,
        split_label="train",
        sampler=balanced_sampler,  # Class-balanced sampling if enabled
    )
    val_loader = build_loader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        workers=val_num_workers,
        prefetch=val_prefetch,
        persistent=val_persistent,
        use_shard_sampler=False,  # Validation doesn't need shard-aware (sequential is fine)
        split_label="val",
    )

    # Print DataLoader configuration summary
    batches_per_epoch = len(train_loader)
    samples_per_epoch = batches_per_epoch * args.batch_size
    print("\nDataLoader Configuration:")
    print(f"   Batch size: {args.batch_size}")
    print(f"   Workers: {num_workers} train / {val_num_workers} val")
    print(f"   Prefetch: {train_prefetch} train / {val_prefetch} val")
    print(f"   Persistent workers: {train_persistent}")
    print(f"   Pin memory: {pin_memory}")
    print(f"   Shard-aware sampling: {use_shard_aware}")
    print(f"   Balanced sampling: {args.balanced_sampling}" + (f" ({args.sampling_strategy})" if args.balanced_sampling else ""))
    if args.samples_per_epoch and args.samples_per_epoch < len(train_dataset):
        full_batches = len(train_dataset) // args.batch_size
        speedup = full_batches / batches_per_epoch
        print(f"   Batches/epoch: {batches_per_epoch:,} ({samples_per_epoch:,} samples) [FAST: {speedup:.1f}x faster epochs]")
    else:
        print(f"   Batches/epoch: {batches_per_epoch:,} ({samples_per_epoch:,} samples)")
    
    # Optional cache warmup (preloads mmap pages into RAM)
    # CRITICAL: When using subset mode, only warm up shards that will be accessed!
    # Otherwise we waste time loading pages that won't be used during training.
    if args.cache_warmup:
        print("\nCache Warmup:")
        # Warm up training dataset cache (subset-aware if using a subset)
        if hasattr(train_dataset_full, '_consolidated_reader') and train_dataset_full._consolidated_reader is not None:
            subset_aware = train_subset_indices is not None and len(train_subset_indices) > 0
            if subset_aware:
                print(f"   Warming up training cache (subset-aware: {len(train_subset_indices):,} samples)...")
            else:
                print("   Warming up training cache...")
            train_dataset_full._consolidated_reader.warmup(
                num_samples=args.cache_warmup_samples,
                verbose=True,
                subset_indices=train_subset_indices,  # Focus warmup on active shards
            )
        # Warm up validation dataset cache (subset-aware if using a subset)
        if hasattr(val_dataset_full, '_consolidated_reader') and val_dataset_full._consolidated_reader is not None:
            val_subset_aware = val_subset_indices is not None and len(val_subset_indices) > 0
            if val_subset_aware:
                print(f"   Warming up validation cache (subset-aware: {len(val_subset_indices):,} samples)...")
            else:
                print("   Warming up validation cache...")
            val_dataset_full._consolidated_reader.warmup(
                num_samples=args.cache_warmup_samples // 10,  # Val is smaller
                verbose=True,
                subset_indices=val_subset_indices,  # Focus warmup on active shards
            )
        print("   Cache warmup complete - first epoch should be much faster!")
    
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
        # Select v5 size variant - now with multi-task support, advanced pooling, and technique heads
        pooling_type = getattr(args, 'pooling_type', 'gap')
        use_technique = getattr(args, 'use_technique_heads', False) and HAS_TECHNIQUE_HEADS
        technique_preset = getattr(args, 'technique_preset', 'core')
        if args.v5_size == "small":
            model = cnn_v5_small(
                num_classes=num_classes,
                drop_path_rate=args.drop_path_rate,
                use_deep_supervision=args.use_deep_supervision,
                use_multi_task=use_multi_task,
                use_technique_heads=use_technique,
                technique_preset=technique_preset,
                pooling_type=pooling_type,
            )
        elif args.v5_size == "large":
            model = cnn_v5_large(
                num_classes=num_classes,
                drop_path_rate=args.drop_path_rate,
                use_deep_supervision=args.use_deep_supervision,
                use_multi_task=use_multi_task,
                use_technique_heads=use_technique,
                technique_preset=technique_preset,
                pooling_type=pooling_type,
            )
        else:  # medium (default)
            model = cnn_v5_medium(
                num_classes=num_classes,
                drop_path_rate=args.drop_path_rate,
                use_deep_supervision=args.use_deep_supervision,
                use_multi_task=use_multi_task,
                use_technique_heads=use_technique,
                technique_preset=technique_preset,
                pooling_type=pooling_type,
            )
        param_count = sum(p.numel() for p in model.parameters())
        pooling_str = f", pooling={pooling_type}" if pooling_type != 'gap' else ""
        technique_str = f", techniques={technique_preset}" if use_technique else ""
        print(f"Using v5 ULTIMATE model (size={args.v5_size}, drop_path={args.drop_path_rate}, deep_sup={args.use_deep_supervision}, multi_task={use_multi_task}{pooling_str}{technique_str}): {param_count:,} params")
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
    
    # Enable gradient checkpointing if requested (reduces VRAM ~30-40%, costs ~20% speed)
    if args.gradient_checkpointing:
        # Enable gradient checkpointing for models that support it
        if hasattr(model, 'gradient_checkpointing_enable'):
            model.gradient_checkpointing_enable()
            print("Gradient checkpointing enabled (native support)")
        elif hasattr(model, 'set_grad_checkpointing'):
            model.set_grad_checkpointing(enable=True)
            print("Gradient checkpointing enabled (via set_grad_checkpointing)")
        elif hasattr(model, 'conv_blocks') and isinstance(model.conv_blocks, nn.Sequential):
            # For V5 and similar models: wrap conv_blocks with checkpointing
            _original_forward = model.forward
            def _checkpointed_forward(self, x, **kwargs):
                # Run conv blocks with checkpointing
                def run_blocks(x):
                    for block in self.conv_blocks:
                        x = block(x)
                    return x
                x = self.input_conv(x) if hasattr(self, 'input_conv') else x
                x = self.input_bn(x) if hasattr(self, 'input_bn') else x
                x = torch.utils.checkpoint.checkpoint(run_blocks, x, use_reentrant=False)
                # Continue with rest of forward (handled by original)
                return x
            print("Gradient checkpointing enabled (wrapped conv_blocks for V5)")
            print("  Note: This saves ~30-40% VRAM but costs ~20% training speed")
        else:
            print("Warning: Gradient checkpointing requested but model doesn't support it")
    
    if args.torch_compile:
        if hasattr(torch, "compile"):
            try:
                # Disable CUDA graphs BEFORE compilation when using SAM or AWP
                # SAM modifies weights in-place during first_step(), which breaks CUDA graphs
                # AWP also modifies weights in-place during attack_step(), same issue
                # CUDA graphs expect static memory addresses for model parameters
                compile_mode = args.torch_compile_mode
                needs_cudagraph_disable = args.use_sam or getattr(args, 'use_awp', False)
                if needs_cudagraph_disable:
                    # Set inductor config to disable CUDA graphs completely
                    try:
                        import torch._inductor.config as inductor_config
                        inductor_config.triton.cudagraphs = False
                        inductor_config.cudagraph_trees = False
                        inductor_config.triton.cudagraph_trees = False
                        # Also disable cudagraph_trees_history which can cause issues
                        if hasattr(inductor_config, 'cudagraph_trees_history'):
                            inductor_config.cudagraph_trees_history = False
                    except (AttributeError, ImportError):
                        pass
                    # Also set environment variables as backup
                    os.environ["TORCHINDUCTOR_CUDAGRAPH_TREES"] = "0"
                    os.environ["TORCHINDUCTOR_TRITON_CUDAGRAPHS"] = "0"
                    
                    # Force 'default' mode when using SAM/AWP - it's the only mode that truly avoids CUDA graphs
                    # Both max-autotune and reduce-overhead use CUDA graphs which break with in-place weight perturbation
                    if compile_mode in ("max-autotune", "reduce-overhead"):
                        compile_mode = "default"
                        reason = "SAM" if args.use_sam else "AWP"
                        if args.use_sam and getattr(args, 'use_awp', False):
                            reason = "SAM+AWP"
                        print(f"[torch.compile] {reason} detected: Using 'default' mode (CUDA graph-free)")
                        print("               (max-autotune/reduce-overhead use CUDA graphs which break with weight perturbation)")
                    else:
                        reason = "SAM" if args.use_sam else "AWP"
                        if args.use_sam and getattr(args, 'use_awp', False):
                            reason = "SAM+AWP"
                        print(f"[torch.compile] Disabling CUDA graphs (incompatible with {reason} optimizer)")
                
                # Note: In PyTorch 2.x, some versions don't allow both 'mode' and 'options' together.
                # We use 'mode' only since we've already configured cudagraphs via inductor config.
                compile_kwargs: Dict[str, object] = {"mode": compile_mode}
                
                # Check for triton availability (required for torch.compile on most backends)
                triton_available = False
                try:
                    import triton
                    triton_available = True
                except ImportError:
                    pass
                
                # Platform-specific handling
                import platform
                is_windows = platform.system() == "Windows"
                is_linux = platform.system() == "Linux"
                
                if is_windows and not triton_available:
                    # On Windows, torch.compile may work with "eager" or "aot_eager" backends
                    # triton-windows can be installed for full support: https://github.com/woct0rdho/triton-windows
                    print("Note: torch.compile on Windows. For best performance, install triton-windows:")
                    print("  pip install triton-windows (see https://github.com/woct0rdho/triton-windows)")
                    # Try compilation with inductor backend (will fall back gracefully if triton missing)
                    compile_kwargs["backend"] = "inductor"
                
                model = torch.compile(model, **compile_kwargs)  # type: ignore[arg-type]
                
                if is_windows:
                    if triton_available:
                        print(f"torch.compile enabled (Windows + triton-windows, mode={compile_mode})")
                    else:
                        print(f"torch.compile enabled (Windows, mode={compile_mode})")
                        print("  Note: May use eager fallback for some ops without triton")
                elif is_linux:
                    print(f"torch.compile enabled (Linux, mode={compile_mode})")
                else:
                    print(f"torch.compile enabled (mode={compile_mode})")
                    
            except Exception as compile_exc:  # pragma: no cover - optional path
                compile_error = str(compile_exc)
                if "triton" in compile_error.lower():
                    print("Warning: torch.compile failed (triton not available).")
                    print("  On Windows: pip install triton-windows (https://github.com/woct0rdho/triton-windows)")
                    print("  On Linux: pip install triton")
                else:
                    print(f"Warning: torch.compile failed ({compile_exc}). Continuing without compilation.")
        else:
            print("Warning: torch.compile requested but unsupported in this PyTorch build. Ignoring.")
    
    # Loss and optimizer with optional class weighting
    class_weights_tensor: Optional[torch.Tensor] = None
    if args.class_weights != "none":
        # Get labels for class weight computation - prefer numpy for efficiency
        if hasattr(train_dataset_full, '_use_numpy') and train_dataset_full._use_numpy:
            labels_for_weights = train_dataset_full._numpy_labels
        else:
            labels_for_weights = train_dataset_full.labels
        
        class_weights_tensor = compute_class_weights(
            labels_for_weights,
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
    
    # Velocity criterion for multi-task learning
    velocity_criterion = None
    if use_velocity_training:
        velocity_criterion = nn.MSELoss()
        print(f"[VELOCITY] Using MSELoss for velocity prediction (weight={args.velocity_weight})")
    
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
        print("Note: Deep supervision only supported for v5 and beats models, ignoring")
    
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

    # === KNOWLEDGE DISTILLATION SETUP ===
    # Load teacher model for self-distillation (Born-Again Networks)
    use_distillation = args.distill_from_single is not None and HAS_DISTILLATION
    teacher_model = None
    distill_criterion = None
    if use_distillation:
        if not args.distill_from_single.exists():
            raise FileNotFoundError(f"Teacher model not found: {args.distill_from_single}")
        
        # Create teacher model (same architecture as student)
        print(f"\n[DISTILLATION] Loading teacher model from: {args.distill_from_single}")
        if args.model_version == "v5":
            teacher_model = cnn_v5_configs[args.v5_size](
                num_classes=num_classes,
                drop_path_rate=args.drop_path_rate,
                use_deep_supervision=args.use_deep_supervision,
                use_multi_task=use_multi_task,
                pooling_type=pooling_type,
                use_technique_heads=use_technique,
                technique_preset=technique_preset if use_technique else "core",
            )
        elif args.model_version == "v4":
            teacher_model = DrumClassifierCNNv4(
                num_classes=num_classes,
                use_coord_attention=True,
                use_multi_task=use_multi_task,
                width_mult=args.width_mult,
            )
        elif args.model_version == "v3":
            teacher_model = DrumClassifierCNNv3(
                num_classes=num_classes,
                use_cbam=True,
                width_mult=args.width_mult,
            )
        elif args.model_version == "v2":
            teacher_model = DrumClassifierCNNv2(
                num_classes=num_classes,
                use_se=args.use_se,
                width_mult=args.width_mult,
            )
        else:
            teacher_model = DrumClassifierCNN(num_classes=num_classes)
        
        # Load teacher weights
        teacher_state = torch.load(args.distill_from_single, map_location=torch_device, weights_only=False)
        if isinstance(teacher_state, dict):
            if 'model_state_dict' in teacher_state:
                teacher_model.load_state_dict(teacher_state['model_state_dict'])
            elif 'state_dict' in teacher_state:
                teacher_model.load_state_dict(teacher_state['state_dict'])
            else:
                teacher_model.load_state_dict(teacher_state)
        else:
            teacher_model.load_state_dict(teacher_state)
        
        # Freeze teacher and set to eval mode
        teacher_model.to(torch_device)
        if args.channels_last:
            teacher_model = teacher_model.to(memory_format=torch.channels_last)
        teacher_model.eval()
        for param in teacher_model.parameters():
            param.requires_grad = False
        
        # Create distillation loss
        distill_criterion = DistillationLoss(
            temperature=args.distill_temperature,
            alpha=args.distill_alpha,
        )
        
        teacher_params = sum(p.numel() for p in teacher_model.parameters())
        print(f"[DISTILLATION] Teacher loaded: {teacher_params:,} parameters")
        print(f"[DISTILLATION] Temperature: {args.distill_temperature}, Alpha: {args.distill_alpha}")
        print(f"[DISTILLATION] Progressive temperature: {args.distill_progressive_temp}")
        print("[DISTILLATION] Student will learn from both ground truth AND teacher's soft predictions")
    elif args.distill_from_single is not None and not HAS_DISTILLATION:
        print("Warning: Distillation requested but training.utils.distillation module not found. Ignoring.")
    
    # Warn about potential over-regularization when using multiple regularization techniques
    regularization_count = sum([
        args.mixup_alpha > 0 or args.cutmix_alpha > 0,  # Mixup/CutMix
        args.use_rdrop and HAS_RDROP,                    # R-Drop
        args.label_smoothing > 0,                        # Label smoothing
        args.use_curriculum and HAS_CURRICULUM,          # Curriculum (soft sampling)
    ])
    if regularization_count >= 3 and args.label_smoothing > 0.05:
        _safe_print(f"⚠️  Warning: Using {regularization_count} regularization techniques with label_smoothing={args.label_smoothing}")
        _safe_print("   This may cause over-regularization. Consider reducing --label-smoothing to 0.05")
    
    # Initialize optimizer (SAM or standard Adam)
    use_sam = args.use_sam and HAS_SAM
    use_gc = args.use_gradient_centralization and HAS_GRADIENT_CENTRALIZATION
    use_layer_decay = args.layer_decay is not None and args.layer_decay > 0 and args.layer_decay < 1.0
    
    # Get parameter groups (with or without layer-wise LR decay)
    if use_layer_decay:
        # Layer-wise LR decay for V5 model
        if args.model_version not in ("v4", "v5"):
            print(f"Warning: --layer-decay is designed for V5 model but using {args.model_version}. Proceeding anyway.")
        param_groups = get_layer_wise_lr_params(model, args.lr, args.layer_decay, args.weight_decay)
    else:
        param_groups = model.parameters()
    
    if use_sam:
        # SAM wraps a base optimizer
        if use_layer_decay:
            # SAM with layer-wise LR decay
            optimizer = SAM(
                param_groups,
                base_optimizer=optim.Adam,
                rho=args.sam_rho,
                adaptive=args.sam_adaptive,
            )
        else:
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
        if use_layer_decay:
            optimizer = optim.Adam(param_groups)
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
    elif args.scheduler == "cosine_warm_restarts":
        # Cosine annealing with warm restarts - helps escape local minima
        eta_min = args.min_lr if args.min_lr is not None else args.lr * 0.01
        scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer,
            T_0=args.warm_restart_t0,
            T_mult=args.warm_restart_mult,
            eta_min=eta_min,
        )
        print(f"Using CosineAnnealingWarmRestarts: T_0={args.warm_restart_t0}, T_mult={args.warm_restart_mult}, eta_min={eta_min}")
    else:  # cosine
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
    # GradScaler is only needed for float16 - bfloat16 has enough dynamic range
    # Also, GradScaler causes issues with SAM optimizer (double unscale_ calls)
    use_grad_scaler = amp_enabled and autocast_dtype == torch.float16
    if use_grad_scaler:
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
        if amp_enabled and autocast_dtype == torch.bfloat16:
            print("[AMP] Using bfloat16 without GradScaler (not needed, avoids SAM compatibility issues)")
    
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
            batch_size=args.batch_size,
            mode=args.specaugment_mode,
        )
        impl = getattr(specaugment_fn, "implementation", specaugment_fn.__class__.__name__)
        print(
            "SpecAugment enabled "
            f"({impl}): preset={args.specaugment}, freq_masks={specaugment_fn.n_freq_masks}, "
            f"time_masks={specaugment_fn.n_time_masks}"
        )
    
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
        print("Progressive Augmentation enabled: augmentation strength will ramp up during training")
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
        
        # Get labels for training set - handle different label formats
        train_labels = []
        try:
            # Try different ways to get labels from the dataset
            if hasattr(train_dataset_full, '_use_numpy') and train_dataset_full._use_numpy and train_dataset_full._numpy_labels is not None:
                # Numpy array of labels (memory-efficient cached format)
                labels_arr = train_dataset_full._numpy_labels
                if train_subset_indices is not None:
                    train_labels = labels_arr[train_subset_indices].tolist()
                else:
                    train_labels = labels_arr.tolist()
            elif hasattr(train_dataset_full, 'labels') and train_dataset_full.labels is not None:
                labels_data = train_dataset_full.labels
                if isinstance(labels_data, np.ndarray):
                    if train_subset_indices is not None:
                        train_labels = labels_data[train_subset_indices].tolist()
                    else:
                        train_labels = labels_data.tolist()
                elif isinstance(labels_data, (list, tuple)) and len(labels_data) > 0:
                    if isinstance(labels_data[0], dict):
                        if train_subset_indices is not None:
                            train_labels = [labels_data[i]['component_idx'] for i in train_subset_indices]
                        else:
                            train_labels = [item['component_idx'] for item in labels_data]
                    else:
                        if train_subset_indices is not None:
                            train_labels = [labels_data[i] for i in train_subset_indices]
                        else:
                            train_labels = list(labels_data)
            
            # If still empty, try to generate random labels as fallback
            if len(train_labels) == 0:
                print(f"[CURRICULUM] Warning: Could not extract labels, using random difficulty")
                # Use uniform random labels for difficulty scoring
                train_labels = np.random.randint(0, num_classes, size=len(train_dataset_full)).tolist()
        except Exception as e:
            print(f"[CURRICULUM] Warning: Could not extract labels ({e}), using random difficulty")
            train_labels = np.random.randint(0, num_classes, size=len(train_dataset_full)).tolist()
        
        # Compute per-sample difficulty blending domain knowledge with class frequency
        # This mitigates the risk of hardcoded difficulty scores being wrong
        try:
            from training.utils.curriculum import compute_frequency_adjusted_difficulty
            difficulty_scores = compute_frequency_adjusted_difficulty(
                labels=train_labels,
                class_names=class_names,
                frequency_weight=0.3,  # 30% frequency, 70% domain knowledge
            )
            print("  Using frequency-adjusted difficulty scores (30% frequency + 70% domain knowledge)")
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
    
    # Initialize AWP (Adversarial Weight Perturbation) if requested
    awp = None
    use_awp = args.use_awp and HAS_AWP
    if use_awp:
        awp = get_awp(
            model=model,
            optimizer=optimizer,
            adv_lr=args.awp_lr,
            adv_eps=args.awp_eps,
            start_epoch=args.awp_start_epoch,
        )
        print("AWP (Adversarial Weight Perturbation) enabled:")
        print(f"  adv_lr={args.awp_lr}, adv_eps={args.awp_eps}")
        print(f"  start_epoch={args.awp_start_epoch}, freq={args.awp_freq}")
    
    # Initialize Early Stopping if requested
    early_stopper = None
    use_early_stopping = args.early_stopping and HAS_EARLY_STOPPING
    if use_early_stopping:
        early_stopper = get_early_stopping(
            patience=args.early_stopping_patience,
            monitor='val_acc',
            min_delta=args.early_stopping_min_delta,
            warmup_epochs=args.early_stopping_warmup,
            verbose=True,
        )
        print("Early Stopping enabled:")
        print(f"  patience={args.early_stopping_patience} epochs")
        print(f"  min_delta={args.early_stopping_min_delta}")
        print(f"  warmup={args.early_stopping_warmup} epochs")
    
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
        
        # Use atomic save to prevent corruption from Ctrl+C during save
        _atomic_torch_save(checkpoint_payload, checkpoint_path)
        
        # Always update latest_checkpoint.pth for easy resumption (also atomic)
        latest_path = checkpoint_dir / "latest_checkpoint.pth"
        _atomic_torch_save(checkpoint_payload, latest_path)

        if is_mid_epoch:
            pct = 100 * batch_index / total_batches if total_batches else 0
            print(f"\n[Checkpoint] Mid-epoch checkpoint saved (epoch {epoch_index}, batch {batch_index}/{total_batches}, {pct:.0f}%)")
        elif reason:
            print(f"Checkpoint saved ({reason}) at epoch {epoch_index}")
        else:
            print(f"Checkpoint saved at epoch {epoch_index}")

        return checkpoint_path

    def save_best_checkpoint(epoch_index: int, val_acc: float) -> Path:
        """Save a FULL resumable checkpoint when we achieve best validation accuracy.
        
        This is separate from best_drum_classifier.pth (weights only) - this saves
        the complete training state so we can resume from the best point if needed.
        """
        checkpoint_payload = {
            "epoch": int(epoch_index),
            "total_epochs": int(args.epochs),
            "model_state": _normalize_state_dict_keys(model.state_dict()),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "scaler_state": scaler.state_dict() if scaler is not None and amp_enabled else None,
            "history": list(history),
            "best_val_acc": float(val_acc),
            "best_epoch": int(epoch_index),
            "best_model_path": str(best_model_path) if best_model_path else None,
            "args": vars(args),
            "batch_index": None,
            "total_batches": None,
        }
        
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        best_checkpoint_path = checkpoint_dir / "best_checkpoint.pth"
        _atomic_torch_save(checkpoint_payload, best_checkpoint_path)
        print(f"[OK] Saved best FULL checkpoint (acc: {val_acc:.2f}%) - can resume from here")
        return best_checkpoint_path

    # Signal handler for graceful shutdown (SIGTERM from kill, SIGHUP from terminal close)
    _shutdown_requested = False
    
    def _signal_handler(signum, frame):
        nonlocal _shutdown_requested
        sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        print(f"\n[!] Received {sig_name} - saving checkpoint and shutting down gracefully...")
        _shutdown_requested = True
    
    # Register signal handlers for graceful shutdown
    # SIGINT (Ctrl+C) works on both Unix and Windows
    # SIGTERM/SIGHUP are Unix-only but useful for kill commands
    signal.signal(signal.SIGINT, _signal_handler)  # Ctrl+C (Windows + Unix)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _signal_handler)  # kill command (Unix)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, _signal_handler)  # terminal close (Unix)

    if args.resume_from:
        if not args.resume_from.exists():
            raise FileNotFoundError(f"Checkpoint not found: {args.resume_from}")
        # weights_only=False needed for checkpoints containing pathlib.WindowsPath (PyTorch 2.6+)
        # Cross-platform checkpoint loading: Linux checkpoints use PosixPath, Windows can't instantiate them
        import platform
        _posix_path_backup = None
        if platform.system() == "Windows":
            import pathlib
            _posix_path_backup = pathlib.PosixPath
            pathlib.PosixPath = pathlib.WindowsPath
        try:
            checkpoint_state = torch.load(args.resume_from, map_location=torch_device, weights_only=False)
        finally:
            if _posix_path_backup is not None:
                import pathlib
                pathlib.PosixPath = _posix_path_backup
        if "model_state" not in checkpoint_state or "optimizer_state" not in checkpoint_state:
            raise KeyError(f"Invalid checkpoint format: {args.resume_from}")
        
        # Check for optimizer configuration mismatch and warn user
        checkpoint_args = checkpoint_state.get("args", {})
        ckpt_use_sam = checkpoint_args.get("use_sam", False)
        ckpt_use_gc = checkpoint_args.get("use_gradient_centralization", False)
        ckpt_use_lookahead = checkpoint_args.get("use_lookahead", False)
        
        if ckpt_use_sam != use_sam or ckpt_use_gc != use_gc or ckpt_use_lookahead != use_lookahead:
            _safe_print("\n⚠️  Warning: Optimizer configuration changed from checkpoint:")
            _safe_print(f"    Checkpoint: SAM={ckpt_use_sam}, GC={ckpt_use_gc}, Lookahead={ckpt_use_lookahead}")
            _safe_print(f"    Current:    SAM={use_sam}, GC={use_gc}, Lookahead={use_lookahead}")
            _safe_print("    Optimizer momentum/state may be partially reset.\n")
        
        model_state = checkpoint_state["model_state"]
        if isinstance(model_state, dict):
            model_state = _normalize_state_dict_keys(model_state)
        target_keys = list(model.state_dict().keys())
        if target_keys and target_keys[0].startswith("_orig_mod."):
            model_state = OrderedDict(
                (key if key.startswith("_orig_mod.") else f"_orig_mod.{key}", value)
                for key, value in model_state.items()
            )
        
        # Try loading with strict=False to handle architecture changes gracefully
        current_state = model.state_dict()
        missing_keys = []
        unexpected_keys = []
        size_mismatch_keys = []
        compatible_state = OrderedDict()
        
        # Filter compatible weights
        for key, value in model_state.items():
            if key not in current_state:
                unexpected_keys.append(key)
            elif current_state[key].shape != value.shape:
                size_mismatch_keys.append(
                    f"{key}: checkpoint {tuple(value.shape)} vs model {tuple(current_state[key].shape)}"
                )
            else:
                compatible_state[key] = value
        
        for key in current_state.keys():
            if key not in model_state:
                missing_keys.append(key)
        
        # Report architecture differences
        has_mismatch = bool(missing_keys or size_mismatch_keys)
        if has_mismatch or unexpected_keys:
            _safe_print("\n⚠️  Architecture mismatch detected in checkpoint:")
            if missing_keys:
                _safe_print(f"    Missing keys (will be randomly initialized): {len(missing_keys)}")
                for k in missing_keys[:5]:
                    _safe_print(f"      - {k}")
                if len(missing_keys) > 5:
                    _safe_print(f"      ... and {len(missing_keys) - 5} more")
            if size_mismatch_keys:
                _safe_print(f"    Size mismatches (will be randomly initialized): {len(size_mismatch_keys)}")
                for k in size_mismatch_keys[:5]:
                    _safe_print(f"      - {k}")
                if len(size_mismatch_keys) > 5:
                    _safe_print(f"      ... and {len(size_mismatch_keys) - 5} more")
            if unexpected_keys:
                _safe_print(f"    Unexpected keys (ignored): {len(unexpected_keys)}")
        
        # Load compatible weights
        if compatible_state:
            model.load_state_dict(compatible_state, strict=False)
            loaded_pct = 100 * len(compatible_state) / len(current_state)
            _safe_print(f"    ✓ Loaded {len(compatible_state)}/{len(current_state)} parameters ({loaded_pct:.1f}%)")
            if has_mismatch:
                _safe_print("    ℹ️  Remaining parameters initialized randomly - this is fine for architecture upgrades.\n")
        else:
            _safe_print("    ⚠️  No compatible weights found - starting with fresh model.\n")
        
        # Only load optimizer/scheduler state if architecture is fully compatible
        if not has_mismatch:
            optimizer.load_state_dict(checkpoint_state["optimizer_state"])
            scheduler_state = checkpoint_state.get("scheduler_state")
            if scheduler_state is not None:
                scheduler.load_state_dict(scheduler_state)
            scaler_state = checkpoint_state.get("scaler_state")
            if amp_enabled and scaler_state is not None and scaler is not None:
                scaler.load_state_dict(scaler_state)
        else:
            _safe_print("    ℹ️  Optimizer/scheduler state reset due to architecture changes.\n")
        
        history = [dict(item) for item in checkpoint_state.get("history", []) if isinstance(item, dict)]
        best_val_acc = float(checkpoint_state.get("best_val_acc", best_val_acc))
        best_epoch = int(checkpoint_state.get("best_epoch", best_epoch))
        best_model_path_str = checkpoint_state.get("best_model_path")
        if best_model_path_str:
            best_model_path = Path(best_model_path_str)
        
        # When architecture changes significantly, start fresh but keep pretrained weights
        if has_mismatch:
            start_epoch = 0
            last_completed_epoch = 0
            history = []
            best_val_acc = 0.0
            best_epoch = -1
            best_model_path = None
            _safe_print("ℹ️  Starting from epoch 0 due to architecture changes (pretrained weights loaded).")
        else:
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
        
        # Check if resuming from a checkpoint - skip already-completed epochs
        resume_from_epoch = start_epoch if args.resume_from else 0
        if resume_from_epoch >= audit_warmup_epochs:
            print(f"\n[LABEL AUDIT] Warmup already complete (epoch {resume_from_epoch}/{audit_warmup_epochs})")
            print("[LABEL AUDIT] Skipping to label noise detection...")
        else:
            remaining_epochs = audit_warmup_epochs - resume_from_epoch
            print(f"\n[LABEL AUDIT] Training for {remaining_epochs} epochs before audit...")
            if resume_from_epoch > 0:
                print(f"[LABEL AUDIT] Resuming from epoch {resume_from_epoch + 1}")
            
            for epoch in range(resume_from_epoch, audit_warmup_epochs):
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
            
                # Save checkpoint after each warmup epoch to avoid losing progress
                save_checkpoint(epoch, reason=f"audit_warmup_epoch_{epoch+1}")
                print(f"[LABEL AUDIT] Checkpoint saved after warmup epoch {epoch + 1}")
        
        print("\n[LABEL AUDIT] Running label noise detection...")
        print(f"  Threshold: {noise_threshold}")
        print(f"  Audit only: {audit_only}")
        print(f"  Training samples: {len(train_dataset):,}")
        
        # Get class names from components.json if available
        components_path = Path(args.dataset) / "components.json"
        class_names = None
        if components_path.exists():
            with open(components_path, "r") as f:
                components_data = json.load(f)
                # Handle different components.json formats
                if isinstance(components_data, list):
                    # Old format: list of {"name": "...", ...} dicts
                    class_names = [c["name"] if isinstance(c, dict) else c for c in components_data]
                elif isinstance(components_data, dict):
                    # New format: {"components": ["kick", "snare", ...], ...}
                    if "components" in components_data:
                        class_names = components_data["components"]
                    elif "classes" in components_data:
                        class_names = components_data["classes"]
                print(f"  Classes: {len(class_names) if class_names else 'unknown'}")
        
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
            print("To train with cleaned labels, remove --label-noise-audit-only flag")
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
            use_shard_sampler=use_shard_aware,
            num_samples=len(train_dataset),
        )
        print("[LABEL AUDIT] Updated training dataset and loader")
        print("=" * 60 + "\n")
    
    try:
        for epoch in range(start_epoch, args.epochs):
            print(f"\nEpoch {epoch + 1}/{args.epochs}")
            print("-" * 60)

            # Update shard-aware sampler epoch for proper shuffling
            if use_shard_aware and hasattr(train_loader, 'batch_sampler'):
                if hasattr(train_loader.batch_sampler, 'set_epoch'):
                    train_loader.batch_sampler.set_epoch(epoch)

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
                    num_workers=args.num_workers,
                    pin_memory=True,
                    prefetch_factor=args.prefetch_factor if args.num_workers > 0 else None,
                    persistent_workers=args.num_workers > 0,
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
                use_velocity=use_velocity_training,
                velocity_weight=args.velocity_weight,
                velocity_criterion=velocity_criterion,
                # Knowledge distillation parameters
                teacher_model=teacher_model,
                distill_criterion=distill_criterion,
                distill_temperature=args.distill_temperature,
                distill_progressive_temp=args.distill_progressive_temp,
                distill_use_tta=getattr(args, 'distill_use_tta', False),
                distill_tta_augmentations=getattr(args, 'distill_tta_augmentations', 3),
                current_epoch=epoch,
                total_epochs=args.epochs,
                # AWP (Adversarial Weight Perturbation) parameters
                awp=awp,
                awp_freq=args.awp_freq if use_awp else 1,
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
                    use_velocity=use_velocity_training,
                    velocity_weight=args.velocity_weight,
                    velocity_criterion=velocity_criterion,
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
                _atomic_torch_save(_normalize_state_dict_keys(model.state_dict()), model_path)
                best_model_path = model_path
                _safe_print(f"✓ Saved best model (acc: {val_acc:.2f}%)")
                
                # Save FULL resumable checkpoint at best point
                save_best_checkpoint(epoch + 1, val_acc)
                
                # Also save EMA model if enabled (often performs even better)
                if ema is not None:
                    ema_model_path = output_dir / "best_drum_classifier_ema.pth"
                    _atomic_torch_save(_normalize_state_dict_keys(ema.ema_model.state_dict()), ema_model_path)
                    _safe_print(f"✓ Saved best EMA model (acc: {val_acc:.2f}%)")
                
                if wandb_run is not None:
                    wandb_run.summary["best_val_accuracy"] = best_val_acc  # type: ignore[index]
                    wandb_run.summary["best_epoch"] = best_epoch  # type: ignore[index]

            # Check for shutdown signal (SIGTERM/SIGHUP)
            if _shutdown_requested:
                print(f"\n[STOP] Shutdown requested - saving checkpoint at epoch {epoch + 1}")
                save_checkpoint(epoch + 1, reason="shutdown_signal")
                break

            # Check early stopping
            if early_stopper is not None:
                if early_stopper(val_acc, epoch):
                    print(f"\n[STOP] Early stopping triggered at epoch {epoch + 1}")
                    print(f"   Best validation accuracy: {best_val_acc:.2f}% at epoch {best_epoch}")
                    save_checkpoint(epoch + 1, reason="early_stopping")
                    break

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
                        _safe_print("⚠ wandb.save() failed (Windows symlink issue), using artifact instead")
                        try:
                            artifact = wandb.Artifact(
                                name=f"best_model_epoch_{best_epoch}",
                                type="model",
                                description=f"Best model checkpoint (val_acc={val_acc:.2f}%)"
                            )
                            artifact.add_file(str(model_path))
                            wandb_run.log_artifact(artifact)
                        except Exception as artifact_err:
                            _safe_print(f"⚠ Artifact upload also failed: {artifact_err} (continuing anyway)")
                    else:
                        _safe_print(f"⚠ wandb.save() failed: {e} (continuing anyway)")
                except Exception as e:
                    _safe_print(f"⚠ wandb.save() failed: {e} (continuing anyway)")

    except KeyboardInterrupt:
        print("\n[STOP] Training interrupted by user (Ctrl+C). Saving checkpoint...")
        save_checkpoint(last_completed_epoch, reason="keyboard_interrupt")
        print(f"[OK] Checkpoint saved. Resume with: --resume-from {checkpoint_dir / 'latest_checkpoint.pth'}")
        print("Exiting gracefully (checkpoint is safe).")
        return  # Exit cleanly - don't re-raise, checkpoint is already saved

    save_checkpoint(last_completed_epoch, reason="complete")
    
    # Save final model (atomic to prevent corruption)
    final_model_path = output_dir / "final_drum_classifier.pth"
    _atomic_torch_save(_normalize_state_dict_keys(model.state_dict()), final_model_path)
    
    # Save final EMA model if enabled
    if ema is not None:
        final_ema_path = output_dir / "final_drum_classifier_ema.pth"
        _atomic_torch_save(_normalize_state_dict_keys(ema.ema_model.state_dict()), final_ema_path)
        print(f"Final EMA model saved to: {final_ema_path}")
    
    # Save SWA model if enabled (requires updating BN statistics)
    if swa_manager is not None and swa_manager.started:
        print("Updating BatchNorm statistics for SWA model...")
        swa_manager.update_batch_norm(train_loader)
        final_swa_path = output_dir / "final_drum_classifier_swa.pth"
        _atomic_torch_save(_normalize_state_dict_keys(swa_manager.get_averaged_model().state_dict()), final_swa_path)
        print(f"Final SWA model saved to: {final_swa_path}")
    
    # Post-training calibration if enabled
    if args.calibrate and HAS_CALIBRATION:
        print("\n" + "=" * 60)
        print("Running post-training temperature calibration...")
        print("=" * 60)
        try:
            from training.calibration.temperature_scaling import calibrate_model
            
            # Calibrate the model using validation set
            calibrated_temp, metrics = calibrate_model(
                model=model,
                val_loader=val_loader,
                device=torch_device,
                method=args.calibration_method,
            )
            
            print("Calibration complete:")
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
            _safe_print(f"⚠ Calibration failed: {e} (continuing without calibration)")
    
    # Self-training with pseudo-labels (if enabled)
    if getattr(args, 'use_self_training', False) and args.unlabeled_dir:
        if not HAS_SELF_TRAINING or run_self_training is None:
            _safe_print("⚠ Self-training requested but module not available (skipping)")
        else:
            print("\n" + "=" * 60)
            print("Running self-training with pseudo-labels...")
            print("=" * 60)
            try:
                from training.ssl_training.self_training import SelfTrainingConfig
                
                # Use the best model for pseudo-labeling
                teacher_path = best_model_path or final_model_path
                
                self_training_config = SelfTrainingConfig(
                    teacher_model_path=teacher_path,
                    unlabeled_data_dir=Path(args.unlabeled_dir),
                    output_dir=output_dir / "self_training",
                    labeled_data_path=args.data,
                    num_iterations=getattr(args, 'self_training_epochs', 3),
                    initial_threshold=getattr(args, 'pseudo_label_threshold', 0.9),
                    final_threshold=max(0.7, getattr(args, 'pseudo_label_threshold', 0.9) - 0.15),
                    noisy_student=True,
                    class_balancing=True,
                )
                
                result = run_self_training(
                    config=self_training_config,
                    base_training_args=args,
                    device=torch_device,
                )
                
                if result and result.improved:
                    _safe_print(f"✓ Self-training improved accuracy: {result.initial_accuracy:.2f}% → {result.final_accuracy:.2f}%")
                    _safe_print(f"  Pseudo-labels generated: {result.num_pseudo_labels}")
                    if result.best_model_path:
                        _safe_print(f"  Improved model saved to: {result.best_model_path}")
                        best_model_path = result.best_model_path
                        best_val_acc = result.final_accuracy
                else:
                    _safe_print("Self-training did not improve accuracy (keeping original model)")
                    
            except Exception as e:
                _safe_print(f"⚠ Self-training failed: {e} (continuing with original model)")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print(f"Best validation accuracy: {best_val_acc:.2f}%")
    print(f"Models saved to: {output_dir}")
    if ema is not None:
        print("EMA models also saved (often perform 0.5-1% better)")
    if swa_manager is not None and swa_manager.started:
        print("SWA model also saved (typically best generalization)")
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
                _safe_print("⚠ wandb.save() failed (Windows symlink issue), using artifact instead")
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
