"""
SpecAugment: Frequency and Time Masking for Audio Spectrograms

This module implements SpecAugment, one of the most effective data augmentation
techniques for audio classification and speech recognition.

Reference: "SpecAugment: A Simple Data Augmentation Method for ASR" (Park et al., 2019)

SpecAugment applies:
1. Frequency masking - masks contiguous frequency bands
2. Time masking - masks contiguous time steps

Why this helps drum classification:
- Forces the model to not rely on any single frequency band
- Improves robustness to variations in drum tuning, mic placement
- Simulates partial occlusion from other instruments
- Complements Mixup/CutMix (they're complementary, not redundant)

Usage:
    from training.augmentation.specaugment import SpecAugment
    
    # Create augmenter
    augmenter = SpecAugment(freq_mask_param=15, time_mask_param=35, n_freq_masks=2, n_time_masks=2)
    
    # In training loop (apply to mel spectrograms):
    features = augmenter(features)  # (batch, 1, n_mels, time)
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn


@dataclass
class SpecAugmentConfig:
    """Configuration for SpecAugment."""
    freq_mask_param: int = 15  # Maximum frequency mask width (F)
    time_mask_param: int = 35  # Maximum time mask width (T)
    n_freq_masks: int = 2      # Number of frequency masks
    n_time_masks: int = 2      # Number of time masks
    mask_value: float = 0.0    # Value to fill masked regions
    inplace: bool = False      # Whether to modify input in-place


class SpecAugment(nn.Module):
    """
    SpecAugment: Frequency and Time Masking for Spectrograms.
    
    Applies random frequency and time masks to mel spectrograms during training.
    This is one of the most effective augmentation techniques for audio tasks.
    
    For drum classification with typical mel spectrograms:
    - n_mels=80, frames=64 -> freq_mask_param=15, time_mask_param=20
    - n_mels=128, frames=128 -> freq_mask_param=27, time_mask_param=35
    
    Args:
        freq_mask_param: Maximum width of frequency mask (F in paper)
        time_mask_param: Maximum width of time mask (T in paper)
        n_freq_masks: Number of frequency masks to apply
        n_time_masks: Number of time masks to apply
        mask_value: Value to fill masked regions (default: 0.0)
        prob: Probability of applying augmentation (default: 1.0)
        inplace: Whether to modify input tensor in-place
    """
    
    def __init__(
        self,
        freq_mask_param: int = 15,
        time_mask_param: int = 35,
        n_freq_masks: int = 2,
        n_time_masks: int = 2,
        mask_value: float = 0.0,
        prob: float = 1.0,
        inplace: bool = False
    ):
        super().__init__()
        self.freq_mask_param = freq_mask_param
        self.time_mask_param = time_mask_param
        self.n_freq_masks = n_freq_masks
        self.n_time_masks = n_time_masks
        self.mask_value = mask_value
        self.prob = prob
        self.inplace = inplace
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply SpecAugment to input spectrogram.
        
        Args:
            x: Input tensor of shape (batch, channels, freq, time) or (batch, freq, time)
            
        Returns:
            Augmented tensor of same shape
        """
        if not self.training:
            return x
        
        if random.random() > self.prob:
            return x
        
        if not self.inplace:
            x = x.clone()
        
        # Handle both 3D and 4D inputs
        if x.dim() == 3:
            # (batch, freq, time) -> treat as (batch, 1, freq, time)
            return self._apply_masks_3d(x)
        elif x.dim() == 4:
            # (batch, channels, freq, time)
            return self._apply_masks_4d(x)
        else:
            raise ValueError(f"Expected 3D or 4D tensor, got {x.dim()}D")
    
    def _apply_masks_3d(self, x: torch.Tensor) -> torch.Tensor:
        """Apply masks to 3D tensor (batch, freq, time)."""
        batch_size, n_freq, n_time = x.shape
        
        for i in range(batch_size):
            # Frequency masks
            for _ in range(self.n_freq_masks):
                f = random.randint(0, min(self.freq_mask_param, n_freq - 1))
                f0 = random.randint(0, max(0, n_freq - f))
                x[i, f0:f0 + f, :] = self.mask_value
            
            # Time masks
            for _ in range(self.n_time_masks):
                t = random.randint(0, min(self.time_mask_param, n_time - 1))
                t0 = random.randint(0, max(0, n_time - t))
                x[i, :, t0:t0 + t] = self.mask_value
        
        return x
    
    def _apply_masks_4d(self, x: torch.Tensor) -> torch.Tensor:
        """Apply masks to 4D tensor (batch, channels, freq, time)."""
        batch_size, n_channels, n_freq, n_time = x.shape
        
        for i in range(batch_size):
            # Frequency masks (applied to all channels)
            for _ in range(self.n_freq_masks):
                f = random.randint(0, min(self.freq_mask_param, n_freq - 1))
                f0 = random.randint(0, max(0, n_freq - f))
                x[i, :, f0:f0 + f, :] = self.mask_value
            
            # Time masks (applied to all channels)
            for _ in range(self.n_time_masks):
                t = random.randint(0, min(self.time_mask_param, n_time - 1))
                t0 = random.randint(0, max(0, n_time - t))
                x[i, :, :, t0:t0 + t] = self.mask_value
        
        return x
    
    def extra_repr(self) -> str:
        return (
            f"freq_mask_param={self.freq_mask_param}, "
            f"time_mask_param={self.time_mask_param}, "
            f"n_freq_masks={self.n_freq_masks}, "
            f"n_time_masks={self.n_time_masks}, "
            f"prob={self.prob}"
        )


class SpecAugmentBatched(nn.Module):
    """
    Vectorized SpecAugment for better GPU performance.
    
    Instead of looping over batch, generates all masks at once.
    Use this for large batch sizes where the loop overhead matters.
    """
    
    def __init__(
        self,
        freq_mask_param: int = 15,
        time_mask_param: int = 35,
        n_freq_masks: int = 2,
        n_time_masks: int = 2,
        mask_value: float = 0.0,
        prob: float = 1.0,
        inplace: bool = False,
    ):
        super().__init__()
        self.freq_mask_param = freq_mask_param
        self.time_mask_param = time_mask_param
        self.n_freq_masks = n_freq_masks
        self.n_time_masks = n_time_masks
        self.mask_value = mask_value
        self.prob = prob
        self.inplace = inplace

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply SpecAugment with vectorized mask generation."""
        if not self.training:
            return x
        
        if random.random() > self.prob:
            return x
        
        if not self.inplace:
            x = x.clone()
        device = x.device
        
        if x.dim() == 3:
            batch_size, n_freq, n_time = x.shape
            n_channels = None
        else:
            batch_size, n_channels, n_freq, n_time = x.shape
        
        # Generate all frequency masks
        freq_range = torch.arange(n_freq, device=device)
        for _ in range(self.n_freq_masks):
            max_width = min(self.freq_mask_param, max(0, n_freq - 1))
            if max_width <= 0:
                continue
            widths = torch.randint(0, max_width + 1, (batch_size,), device=device)
            if torch.all(widths == 0):
                continue
            max_start = torch.clamp(n_freq - widths, min=0)
            starts = torch.floor(
                torch.rand(batch_size, device=device) * (max_start.to(torch.float32) + 1.0)
            ).to(torch.int64)
            mask = (freq_range.unsqueeze(0) >= starts.unsqueeze(1)) & (freq_range.unsqueeze(0) < (starts + widths).unsqueeze(1))
            if x.dim() == 3:
                mask = mask.unsqueeze(-1).expand(-1, -1, n_time)
            else:
                mask = mask.unsqueeze(1).unsqueeze(-1).expand(-1, n_channels, -1, n_time)
            x = x.masked_fill(mask, self.mask_value)
        
        time_range = torch.arange(n_time, device=device)
        for _ in range(self.n_time_masks):
            max_width = min(self.time_mask_param, max(0, n_time - 1))
            if max_width <= 0:
                continue
            widths = torch.randint(0, max_width + 1, (batch_size,), device=device)
            if torch.all(widths == 0):
                continue
            max_start = torch.clamp(n_time - widths, min=0)
            starts = torch.floor(
                torch.rand(batch_size, device=device) * (max_start.to(torch.float32) + 1.0)
            ).to(torch.int64)
            mask = (time_range.unsqueeze(0) >= starts.unsqueeze(1)) & (time_range.unsqueeze(0) < (starts + widths).unsqueeze(1))
            if x.dim() == 3:
                mask = mask.unsqueeze(1).expand(-1, n_freq, -1)
            else:
                mask = mask.unsqueeze(1).unsqueeze(2).expand(-1, n_channels, n_freq, -1)
            x = x.masked_fill(mask, self.mask_value)
        
        return x


def _resolve_default_threshold() -> int:
    value = os.environ.get("BEATSIGHT_SPECAUG_BATCH_THRESHOLD", "128")
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 128


DEFAULT_BATCHED_THRESHOLD = _resolve_default_threshold()


def get_specaugment(
    config: str = "default",
    n_mels: int = 80,
    n_frames: int = 64,
    *,
    batch_size: int = 0,
    mode: str = "auto",
    batched_threshold: Optional[int] = None,
) -> SpecAugment:
    """
    Factory function to get SpecAugment with preset configurations.
    
    Configs:
    - "none": No augmentation
    - "light": Minimal masking (for small datasets or fine-tuning)
    - "default": Standard SpecAugment (good for most cases)
    - "strong": Aggressive masking (for large datasets or preventing overfitting)
    - "drum": Optimized for drum classification spectrograms
    
    Args:
        config: Configuration preset name
        n_mels: Number of mel bands in spectrogram
        n_frames: Number of time frames in spectrogram
        
    Returns:
        Configured SpecAugment instance
    """
    configs = {
        "none": {
            "freq_mask_param": 0,
            "time_mask_param": 0,
            "n_freq_masks": 0,
            "n_time_masks": 0,
            "prob": 0.0
        },
        "light": {
            "freq_mask_param": max(5, n_mels // 16),
            "time_mask_param": max(5, n_frames // 8),
            "n_freq_masks": 1,
            "n_time_masks": 1,
            "prob": 0.5
        },
        "default": {
            "freq_mask_param": max(10, n_mels // 8),
            "time_mask_param": max(10, n_frames // 4),
            "n_freq_masks": 2,
            "n_time_masks": 2,
            "prob": 0.8
        },
        "strong": {
            "freq_mask_param": max(15, n_mels // 4),
            "time_mask_param": max(15, n_frames // 3),
            "n_freq_masks": 3,
            "n_time_masks": 3,
            "prob": 1.0
        },
        "drum": {
            # Optimized for drum classification:
            # - Moderate freq masking (preserve kick/snare distinction)
            # - Moderate time masking (preserve attack transients)
            "freq_mask_param": max(12, n_mels // 6),
            "time_mask_param": max(8, n_frames // 8),  # Less time masking to preserve transients
            "n_freq_masks": 2,
            "n_time_masks": 2,
            "prob": 0.7
        }
    }
    
    if config not in configs:
        raise ValueError(f"Unknown config '{config}'. Available: {list(configs.keys())}")

    impl_mode = (mode or "auto").lower()
    if impl_mode not in {"auto", "classic", "batched"}:
        raise ValueError("SpecAugment mode must be one of: auto, classic, batched")

    threshold = batched_threshold or DEFAULT_BATCHED_THRESHOLD
    use_batched = False
    if impl_mode == "batched":
        use_batched = True
    elif impl_mode == "auto":
        # Large batches benefit the most; allow opt-in via env/threshold
        use_batched = batch_size >= threshold
        if not use_batched and batch_size >= max(64, threshold // 2):
            use_batched = torch.cuda.is_available()

    augmenter_cls = SpecAugmentBatched if use_batched else SpecAugment
    augmenter = augmenter_cls(**configs[config])
    setattr(augmenter, "implementation", "batched" if use_batched else "classic")
    return augmenter


# Convenience for common drum classification setup
DrumSpecAugment = lambda: get_specaugment("drum", n_mels=80, n_frames=64)
