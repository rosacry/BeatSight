"""
Waveform-Level Audio Augmentation for Drum Classification

This module implements online audio augmentation applied BEFORE spectrogram extraction.
Unlike spectrogram augmentations (Mixup, SpecAugment), these operate on raw audio
and create acoustically realistic variations.

Why this matters for drums:
- Time stretching simulates different tempos and playing dynamics
- Pitch shifting simulates different drum tunings and kit variations
- Room impulse responses simulate different recording environments
- Gain variation simulates different hit intensities
- Noise injection improves robustness to recording conditions

These augmentations are MORE musically meaningful than spectrogram-level
augmentations because they respect the acoustic physics of drum sounds.

Usage:
    from training.augmentation.waveform import WaveformAugment
    
    augmenter = WaveformAugment(
        time_stretch_range=(0.95, 1.05),
        pitch_shift_range=(-2, 2),
        gain_db_range=(-3, 3),
        noise_factor_range=(0.0, 0.005),
    )
    
    # In dataset __getitem__:
    waveform = augmenter(waveform, sample_rate)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Tuple

import numpy as np
import torch

# Optional imports for augmentation
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    import torchaudio
    import torchaudio.functional as F
    import torchaudio.transforms as T
    HAS_TORCHAUDIO = True
except ImportError:
    HAS_TORCHAUDIO = False


@dataclass
class WaveformAugmentConfig:
    """Configuration for waveform augmentation."""
    
    # Time stretching (simulates tempo variation)
    time_stretch: bool = True
    time_stretch_range: Tuple[float, float] = (0.95, 1.05)  # ±5% tempo
    time_stretch_prob: float = 0.3
    
    # Pitch shifting (simulates different drum tuning)
    pitch_shift: bool = True
    pitch_shift_range: Tuple[float, float] = (-2.0, 2.0)  # ±2 semitones
    pitch_shift_prob: float = 0.3
    
    # Gain variation (simulates hit intensity variation)
    gain_variation: bool = True
    gain_db_range: Tuple[float, float] = (-4.0, 4.0)  # ±4 dB
    gain_prob: float = 0.5
    
    # Additive noise (simulates recording noise)
    noise_injection: bool = True
    noise_factor_range: Tuple[float, float] = (0.0, 0.003)
    noise_prob: float = 0.3
    
    # Polarity flip (phase inversion - should be acoustically equivalent)
    polarity_flip: bool = True
    polarity_prob: float = 0.5
    
    # DC offset removal
    remove_dc: bool = True
    
    # Overall probability of applying ANY augmentation
    augment_prob: float = 0.8


class WaveformAugment:
    """
    Online waveform augmentation applied before spectrogram extraction.
    
    This augmenter applies acoustically realistic transformations to
    raw audio that preserve the semantic content while creating useful
    training variations.
    
    Args:
        time_stretch_range: Min/max stretch factors (1.0 = no stretch)
        pitch_shift_range: Min/max semitones to shift
        gain_db_range: Min/max gain change in dB
        noise_factor_range: Min/max noise amplitude factor
        augment_prob: Overall probability of augmenting
        
    Example:
        augmenter = WaveformAugment()
        augmented_waveform = augmenter(waveform, sample_rate=44100)
    """
    
    def __init__(
        self,
        time_stretch_range: Tuple[float, float] = (0.95, 1.05),
        pitch_shift_range: Tuple[float, float] = (-2.0, 2.0),
        gain_db_range: Tuple[float, float] = (-4.0, 4.0),
        noise_factor_range: Tuple[float, float] = (0.0, 0.003),
        augment_prob: float = 0.8,
        time_stretch_prob: float = 0.3,
        pitch_shift_prob: float = 0.3,
        gain_prob: float = 0.5,
        noise_prob: float = 0.3,
        polarity_prob: float = 0.5,
    ):
        self.time_stretch_range = time_stretch_range
        self.pitch_shift_range = pitch_shift_range
        self.gain_db_range = gain_db_range
        self.noise_factor_range = noise_factor_range
        self.augment_prob = augment_prob
        self.time_stretch_prob = time_stretch_prob
        self.pitch_shift_prob = pitch_shift_prob
        self.gain_prob = gain_prob
        self.noise_prob = noise_prob
        self.polarity_prob = polarity_prob
        
        self._use_librosa = HAS_LIBROSA
        self._use_torchaudio = HAS_TORCHAUDIO
        
    def __call__(
        self,
        waveform: torch.Tensor,
        sample_rate: int = 44100,
        training: bool = True
    ) -> torch.Tensor:
        """
        Apply waveform augmentation.
        
        Args:
            waveform: Audio tensor of shape (samples,) or (channels, samples)
            sample_rate: Sample rate in Hz
            training: Whether in training mode (augmentation only in training)
            
        Returns:
            Augmented waveform tensor
        """
        if not training:
            return waveform
            
        # Skip augmentation with probability
        if random.random() > self.augment_prob:
            return waveform
        
        # Handle shape
        squeeze_output = False
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
            squeeze_output = True
        
        # Convert to numpy for librosa operations if needed
        is_numpy = False
        device = waveform.device
        dtype = waveform.dtype
        
        # Apply augmentations
        augmented = waveform.clone()
        
        # 1. Polarity flip (very fast, no quality loss)
        if random.random() < self.polarity_prob:
            augmented = -augmented
        
        # 2. Gain variation (fast, no quality loss)
        if random.random() < self.gain_prob:
            gain_db = random.uniform(*self.gain_db_range)
            gain_linear = 10 ** (gain_db / 20)
            augmented = augmented * gain_linear
        
        # 3. Time stretching (requires librosa, slower)
        if random.random() < self.time_stretch_prob and self._use_librosa:
            rate = random.uniform(*self.time_stretch_range)
            if abs(rate - 1.0) > 0.01:  # Only if meaningful stretch
                augmented = self._time_stretch(augmented, rate, sample_rate)
        
        # 4. Pitch shifting (requires librosa, slower)
        if random.random() < self.pitch_shift_prob and self._use_librosa:
            semitones = random.uniform(*self.pitch_shift_range)
            if abs(semitones) > 0.1:  # Only if meaningful shift
                augmented = self._pitch_shift(augmented, semitones, sample_rate)
        
        # 5. Noise injection (fast)
        if random.random() < self.noise_prob:
            noise_factor = random.uniform(*self.noise_factor_range)
            if noise_factor > 0:
                noise = torch.randn_like(augmented) * noise_factor
                augmented = augmented + noise
        
        # Normalize to prevent clipping
        max_val = augmented.abs().max()
        if max_val > 0.99:
            augmented = augmented * (0.99 / max_val)
        
        # Remove DC offset
        augmented = augmented - augmented.mean(dim=-1, keepdim=True)
        
        if squeeze_output:
            augmented = augmented.squeeze(0)
        
        return augmented.to(device=device, dtype=dtype)
    
    def _time_stretch(
        self,
        waveform: torch.Tensor,
        rate: float,
        sample_rate: int
    ) -> torch.Tensor:
        """Apply time stretching using librosa."""
        if not self._use_librosa:
            return waveform
            
        device = waveform.device
        dtype = waveform.dtype
        
        # Convert to numpy
        audio_np = waveform.squeeze(0).cpu().numpy()
        
        # Apply time stretch
        try:
            stretched = librosa.effects.time_stretch(audio_np, rate=rate)
            return torch.from_numpy(stretched).unsqueeze(0).to(device=device, dtype=dtype)
        except Exception:
            return waveform
    
    def _pitch_shift(
        self,
        waveform: torch.Tensor,
        semitones: float,
        sample_rate: int
    ) -> torch.Tensor:
        """Apply pitch shifting using librosa."""
        if not self._use_librosa:
            return waveform
            
        device = waveform.device
        dtype = waveform.dtype
        
        # Convert to numpy
        audio_np = waveform.squeeze(0).cpu().numpy()
        
        # Apply pitch shift
        try:
            shifted = librosa.effects.pitch_shift(
                audio_np, sr=sample_rate, n_steps=semitones
            )
            return torch.from_numpy(shifted).unsqueeze(0).to(device=device, dtype=dtype)
        except Exception:
            return waveform


class FastWaveformAugment:
    """
    Fast waveform augmentation using only PyTorch operations.
    
    This version avoids librosa/torchaudio for maximum speed,
    but only supports a subset of augmentations:
    - Gain variation
    - Polarity flip
    - Noise injection
    - DC removal
    
    Use this for production training when time stretch/pitch shift
    are not critical.
    """
    
    def __init__(
        self,
        gain_db_range: Tuple[float, float] = (-4.0, 4.0),
        noise_factor_range: Tuple[float, float] = (0.0, 0.003),
        augment_prob: float = 0.8,
        gain_prob: float = 0.5,
        noise_prob: float = 0.3,
        polarity_prob: float = 0.5,
    ):
        self.gain_db_range = gain_db_range
        self.noise_factor_range = noise_factor_range
        self.augment_prob = augment_prob
        self.gain_prob = gain_prob
        self.noise_prob = noise_prob
        self.polarity_prob = polarity_prob
    
    def __call__(
        self,
        waveform: torch.Tensor,
        training: bool = True
    ) -> torch.Tensor:
        """Apply fast waveform augmentation."""
        if not training or random.random() > self.augment_prob:
            return waveform
        
        augmented = waveform
        
        # Polarity flip
        if random.random() < self.polarity_prob:
            augmented = -augmented
        
        # Gain variation
        if random.random() < self.gain_prob:
            gain_db = random.uniform(*self.gain_db_range)
            gain_linear = 10 ** (gain_db / 20)
            augmented = augmented * gain_linear
        
        # Noise injection
        if random.random() < self.noise_prob:
            noise_factor = random.uniform(*self.noise_factor_range)
            if noise_factor > 0:
                noise = torch.randn_like(augmented) * noise_factor
                augmented = augmented + noise
        
        # Normalize
        max_val = augmented.abs().max()
        if max_val > 0.99:
            augmented = augmented * (0.99 / max_val)
        
        # DC removal
        if augmented.dim() == 1:
            augmented = augmented - augmented.mean()
        else:
            augmented = augmented - augmented.mean(dim=-1, keepdim=True)
        
        return augmented


def get_waveform_augment(
    preset: str = "drum",
    fast: bool = False
) -> WaveformAugment:
    """
    Get a waveform augmenter with preset configuration.
    
    Args:
        preset: One of "none", "light", "drum", "heavy"
        fast: Use FastWaveformAugment (no time stretch/pitch shift)
        
    Returns:
        Configured WaveformAugment or FastWaveformAugment
    """
    presets = {
        "none": {
            "augment_prob": 0.0,
        },
        "light": {
            "time_stretch_range": (0.98, 1.02),
            "pitch_shift_range": (-0.5, 0.5),
            "gain_db_range": (-2.0, 2.0),
            "noise_factor_range": (0.0, 0.001),
            "augment_prob": 0.5,
            "time_stretch_prob": 0.2,
            "pitch_shift_prob": 0.2,
        },
        "drum": {
            "time_stretch_range": (0.95, 1.05),
            "pitch_shift_range": (-2.0, 2.0),
            "gain_db_range": (-4.0, 4.0),
            "noise_factor_range": (0.0, 0.003),
            "augment_prob": 0.8,
            "time_stretch_prob": 0.3,
            "pitch_shift_prob": 0.3,
            "gain_prob": 0.5,
            "noise_prob": 0.3,
        },
        "heavy": {
            "time_stretch_range": (0.9, 1.1),
            "pitch_shift_range": (-3.0, 3.0),
            "gain_db_range": (-6.0, 6.0),
            "noise_factor_range": (0.0, 0.005),
            "augment_prob": 0.9,
            "time_stretch_prob": 0.5,
            "pitch_shift_prob": 0.5,
            "gain_prob": 0.7,
            "noise_prob": 0.4,
        },
    }
    
    config = presets.get(preset, presets["drum"])
    
    if fast:
        return FastWaveformAugment(
            gain_db_range=config.get("gain_db_range", (-4.0, 4.0)),
            noise_factor_range=config.get("noise_factor_range", (0.0, 0.003)),
            augment_prob=config.get("augment_prob", 0.8),
            gain_prob=config.get("gain_prob", 0.5),
            noise_prob=config.get("noise_prob", 0.3),
        )
    
    return WaveformAugment(**config)


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Testing WaveformAugment...")
    
    # Create test waveform (1 second of 440Hz sine wave)
    sr = 44100
    t = torch.linspace(0, 1, sr)
    waveform = torch.sin(2 * np.pi * 440 * t)
    
    # Test full augmenter
    augmenter = WaveformAugment()
    print(f"Input shape: {waveform.shape}")
    
    for i in range(3):
        augmented = augmenter(waveform, sr, training=True)
        print(f"Augmented {i+1} shape: {augmented.shape}, "
              f"min={augmented.min():.3f}, max={augmented.max():.3f}")
    
    # Test fast augmenter
    fast_augmenter = FastWaveformAugment()
    for i in range(3):
        augmented = fast_augmenter(waveform, training=True)
        print(f"Fast augmented {i+1} shape: {augmented.shape}")
    
    # Test presets
    for preset in ["none", "light", "drum", "heavy"]:
        aug = get_waveform_augment(preset)
        result = aug(waveform, sr)
        print(f"Preset '{preset}': shape={result.shape}")
    
    print("\n✅ WaveformAugment working!")
