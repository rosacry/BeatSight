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
from typing import Any, Dict, List, Optional

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

        with self.labels_path.open("r", encoding="utf-8") as handle:
            labels_data = json.load(handle)
        if not isinstance(labels_data, list):
            raise ValueError(f"Expected list of labels in {self.labels_path}, found {type(labels_data)!r}")
        self.labels: List[Dict[str, Any]] = labels_data

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int):
        item = self.labels[idx]
        audio_path = self.data_dir / item["file"]
        label = int(item["component_idx"])

        features = None
        cache_path: Optional[Path] = None
        if self.cache_dir is not None:
            cache_path = self._cache_path(audio_path)
            if cache_path.exists():
                try:
                    features = torch.load(cache_path, map_location="cpu")
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


def _normalize_state_dict_keys(state_dict: Dict[str, torch.Tensor]) -> OrderedDict[str, torch.Tensor]:
    """Strip torch.compile's `_orig_mod.` prefix so checkpoints are portable."""

    prefix = "_orig_mod."
    if not any(key.startswith(prefix) for key in state_dict.keys()):
        return OrderedDict(state_dict.items())
    return OrderedDict(
        (key[len(prefix):] if key.startswith(prefix) else key, value) for key, value in state_dict.items()
    )


def stratified_sample_indices(labels: List[Dict[str, Any]], fraction: float, seed: int) -> List[int]:
    """Create stratified subset indices retaining class balance."""

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
) -> tuple[float, float]:
    """Train for one epoch with optional AMP."""

    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    non_blocking = device.type == "cuda"
    accum_steps = max(1, grad_accum_steps)

    optimizer.zero_grad(set_to_none=True)

    pbar = tqdm(dataloader, desc="Training")
    for batch_index, (features, labels) in enumerate(pbar, start=1):
        features = features.to(device, non_blocking=non_blocking)
        labels = labels.to(device, non_blocking=non_blocking)
        if channels_last:
            features = features.to(memory_format=torch.channels_last)

        with autocast(device_type=device.type, dtype=autocast_dtype, enabled=amp_enabled):
            outputs = model(features)
            loss = criterion(outputs, labels)
            loss_for_backward = loss / accum_steps

        if amp_enabled and scaler is not None:
            scaler.scale(loss_for_backward).backward()
            should_step = batch_index % accum_steps == 0 or batch_index == len(dataloader)
            if should_step:
                if grad_clip_norm is not None:
                    scaler.unscale_(optimizer)
                    clip_grad_norm_(model.parameters(), grad_clip_norm)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
        else:
            loss_for_backward.backward()
            should_step = batch_index % accum_steps == 0 or batch_index == len(dataloader)
            if should_step:
                if grad_clip_norm is not None:
                    clip_grad_norm_(model.parameters(), grad_clip_norm)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)

        total_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

        pbar.set_postfix({"loss": f"{loss.item():.4f}", "acc": f"{100 * correct / max(total, 1):.2f}%"})

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
                loss = criterion(outputs, labels)

            total_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    mean_loss = total_loss / max(len(dataloader), 1)
    accuracy = 100 * correct / max(total, 1)
    return mean_loss, accuracy


def main():
    parser = argparse.ArgumentParser(description="Train Drum Classifier CNN")
    parser.add_argument("--dataset", required=True, help="Path to dataset directory")
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
        help="Optional root directory to cache precomputed features (will mirror dataset structure)",
    )
    parser.add_argument(
        "--cache-dtype",
        choices=["float32", "float16", "bfloat16"],
        default="float32",
        help="Data type used when persisting cached spectrograms (float16 reduces disk usage by ~2x)",
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
    
    args = parser.parse_args()
    
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
        """Locate the label JSON, supporting both flat and split-local layouts."""
        candidate = dataset_path / filename
        if candidate.exists():
            return candidate
        nested = dataset_path / split / filename
        if nested.exists():
            return nested
        raise FileNotFoundError(f"Missing label file for {split}: tried '{candidate}' and '{nested}'")

    fmax = None if args.fmax is not None and args.fmax <= 0 else args.fmax
    feature_cache_root = args.feature_cache_dir
    if feature_cache_root and not feature_cache_root.exists():
        feature_cache_root.mkdir(parents=True, exist_ok=True)
    prefer_torchaudio = not args.no_torchaudio

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
        train_subset_indices = stratified_sample_indices(train_dataset_full.labels, args.train_fraction, args.subset_seed)
        train_dataset = Subset(train_dataset_full, train_subset_indices)
    else:
        train_dataset = train_dataset_full

    val_subset_indices = None
    if args.val_fraction < 1.0:
        val_subset_indices = stratified_sample_indices(val_dataset_full.labels, args.val_fraction, args.subset_seed)
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
    
    # Initialize model
    model = DrumClassifierCNN(num_classes=num_classes)
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
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
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
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = Path(args.checkpoint_dir) if args.checkpoint_dir else output_dir / "checkpoints"
    checkpoint_interval = args.checkpoint_every if args.checkpoint_every > 0 else None

    # Training loop
    best_val_acc = 0.0
    best_epoch = -1
    best_model_path: Path | None = None
    history: List[Dict[str, float]] = []
    start_epoch = 0
    last_completed_epoch = 0
    resumed_from: Optional[str] = str(args.resume_from) if args.resume_from else None

    def save_checkpoint(epoch_index: int, *, reason: Optional[str] = None) -> Path:
        """Persist model/optimizer state for later resumption."""

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
        }

        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch_index:04d}.pth"
        torch.save(checkpoint_payload, checkpoint_path)
        latest_path = checkpoint_dir / "latest_checkpoint.pth"
        torch.save(checkpoint_payload, latest_path)

        if reason:
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
    
    try:
        for epoch in range(start_epoch, args.epochs):
            print(f"\nEpoch {epoch + 1}/{args.epochs}")
            print("-" * 60)

            if args.warmup_epochs > 0 and epoch < args.warmup_epochs:
                warmup_factor = float(epoch + 1) / float(max(1, args.warmup_epochs))
                warmup_lr = args.lr * warmup_factor
                for group in optimizer.param_groups:
                    group["lr"] = warmup_lr

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
            )
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
                if wandb_run is not None:
                    wandb_run.summary["best_val_accuracy"] = best_val_acc  # type: ignore[index]
                    wandb_run.summary["best_epoch"] = best_epoch  # type: ignore[index]
                    wandb_run.save(str(model_path))  # type: ignore[arg-type]

            last_completed_epoch = epoch + 1

            if checkpoint_interval and (epoch + 1) % checkpoint_interval == 0:
                save_checkpoint(epoch + 1, reason="interval")
    except KeyboardInterrupt:
        print("Training interrupted by user. Saving checkpoint before exiting...")
        save_checkpoint(last_completed_epoch, reason="interrupt")
        raise

    save_checkpoint(last_completed_epoch, reason="complete")
    
    # Save final model
    final_model_path = output_dir / "final_drum_classifier.pth"
    torch.save(model.state_dict(), final_model_path)
    
    print("\n" + "=" * 60)
    print(f"Training complete!")
    print(f"Best validation accuracy: {best_val_acc:.2f}%")
    print(f"Models saved to: {output_dir}")
    print("=" * 60)

    if wandb_run is not None:
        wandb_run.summary["final_train_loss"] = history[-1]["train_loss"] if history else None  # type: ignore[index]
        wandb_run.summary["final_val_loss"] = history[-1]["val_loss"] if history else None  # type: ignore[index]
        wandb_run.summary["final_train_accuracy"] = history[-1]["train_accuracy"] if history else None  # type: ignore[index]
        wandb_run.summary["final_val_accuracy"] = history[-1]["val_accuracy"] if history else None  # type: ignore[index]
        wandb_run.summary["best_model_path"] = str(best_model_path) if best_model_path else None  # type: ignore[index]
        wandb_run.summary["final_model_path"] = str(final_model_path)  # type: ignore[index]
        wandb_run.save(str(final_model_path))  # type: ignore[arg-type]
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
