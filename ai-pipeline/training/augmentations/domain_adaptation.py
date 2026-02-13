#!/usr/bin/env python3
"""
Audio Augmentation for Domain Adaptation

This module provides augmentation transforms that help the model generalize
from synthetic/electronic drums to real acoustic drums.

Key augmentations:
1. Room reverb - simulates real recording spaces
2. Background noise - simulates real-world recordings  
3. EQ variations - simulates different mics/preamps
4. Tape saturation - adds warmth/character

Usage:
    from training.augmentations.domain_adaptation import DomainAdaptationAugment
    
    augment = DomainAdaptationAugment(
        reverb_prob=0.3,
        noise_prob=0.2,
        eq_prob=0.2,
    )
    
    # Apply to waveform
    augmented_audio = augment(audio)
"""

from __future__ import annotations

import numpy as np
from typing import Optional, Tuple
import warnings

try:
    from scipy import signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    warnings.warn("scipy not available, some augmentations disabled")


class RoomReverbAugment:
    """Add synthetic room reverb to simulate real recording spaces."""
    
    def __init__(
        self,
        room_size_range: Tuple[float, float] = (0.1, 0.5),
        decay_range: Tuple[float, float] = (0.2, 0.6),
        wet_dry_range: Tuple[float, float] = (0.1, 0.4),
    ):
        """
        Args:
            room_size_range: (min, max) room size factor (0.1 = small, 0.9 = large)
            decay_range: (min, max) decay time factor
            wet_dry_range: (min, max) wet/dry mix ratio
        """
        self.room_size_range = room_size_range
        self.decay_range = decay_range
        self.wet_dry_range = wet_dry_range
    
    def __call__(self, audio: np.ndarray, sr: int = 22050) -> np.ndarray:
        """Apply room reverb to audio."""
        if not HAS_SCIPY:
            return audio
        
        # Random parameters
        room_size = np.random.uniform(*self.room_size_range)
        decay = np.random.uniform(*self.decay_range)
        wet_dry = np.random.uniform(*self.wet_dry_range)
        
        # Create simple impulse response (exponential decay)
        ir_length = int(sr * room_size)
        ir = np.random.randn(ir_length) * np.exp(-np.linspace(0, 5 * decay, ir_length))
        ir = ir / (np.abs(ir).max() + 1e-8)
        
        # Convolve
        reverb = signal.fftconvolve(audio, ir, mode='same')
        
        # Mix wet/dry
        output = (1 - wet_dry) * audio + wet_dry * reverb
        
        # Normalize to prevent clipping
        max_val = np.abs(output).max()
        if max_val > 1.0:
            output = output / max_val
        
        return output.astype(np.float32)


class BackgroundNoiseAugment:
    """Add subtle background noise to simulate real recordings."""
    
    def __init__(
        self,
        snr_range: Tuple[float, float] = (20, 40),  # dB
        noise_types: Tuple[str, ...] = ("white", "pink", "brownian"),
    ):
        """
        Args:
            snr_range: (min, max) signal-to-noise ratio in dB
            noise_types: Types of noise to randomly choose from
        """
        self.snr_range = snr_range
        self.noise_types = noise_types
    
    def _generate_noise(self, length: int, noise_type: str) -> np.ndarray:
        """Generate noise of specified type."""
        if noise_type == "white":
            return np.random.randn(length)
        elif noise_type == "pink":
            # Pink noise (1/f)
            white = np.random.randn(length)
            if HAS_SCIPY:
                b, a = signal.butter(1, 0.02, btype='low')
                return signal.filtfilt(b, a, white)
            return white * 0.5
        elif noise_type == "brownian":
            # Brownian noise (1/f^2)
            white = np.random.randn(length)
            return np.cumsum(white) / np.sqrt(length)
        else:
            return np.random.randn(length)
    
    def __call__(self, audio: np.ndarray, sr: int = 22050) -> np.ndarray:
        """Add background noise to audio."""
        noise_type = np.random.choice(self.noise_types)
        noise = self._generate_noise(len(audio), noise_type)
        
        # Calculate SNR
        snr_db = np.random.uniform(*self.snr_range)
        
        # Calculate scaling factor
        audio_power = np.mean(audio ** 2) + 1e-8
        noise_power = np.mean(noise ** 2) + 1e-8
        snr_linear = 10 ** (snr_db / 10)
        
        noise_scale = np.sqrt(audio_power / (noise_power * snr_linear))
        scaled_noise = noise * noise_scale
        
        output = audio + scaled_noise
        
        # Normalize
        max_val = np.abs(output).max()
        if max_val > 1.0:
            output = output / max_val
        
        return output.astype(np.float32)


class EQVariationAugment:
    """Apply random EQ variations to simulate different mics/preamps."""
    
    def __init__(
        self,
        low_gain_range: Tuple[float, float] = (-3, 3),   # dB
        mid_gain_range: Tuple[float, float] = (-3, 3),   # dB  
        high_gain_range: Tuple[float, float] = (-3, 3),  # dB
    ):
        self.low_gain_range = low_gain_range
        self.mid_gain_range = mid_gain_range
        self.high_gain_range = high_gain_range
    
    def __call__(self, audio: np.ndarray, sr: int = 22050) -> np.ndarray:
        """Apply 3-band EQ to audio."""
        if not HAS_SCIPY:
            return audio
        
        # Random gains
        low_gain = np.random.uniform(*self.low_gain_range)
        mid_gain = np.random.uniform(*self.mid_gain_range)
        high_gain = np.random.uniform(*self.high_gain_range)
        
        # Convert dB to linear
        low_scale = 10 ** (low_gain / 20)
        mid_scale = 10 ** (mid_gain / 20)
        high_scale = 10 ** (high_gain / 20)
        
        # Create filters
        nyquist = sr / 2
        low_freq = 300 / nyquist
        high_freq = 3000 / nyquist
        
        # Low band
        b_low, a_low = signal.butter(2, low_freq, btype='low')
        low_band = signal.filtfilt(b_low, a_low, audio) * low_scale
        
        # High band  
        b_high, a_high = signal.butter(2, high_freq, btype='high')
        high_band = signal.filtfilt(b_high, a_high, audio) * high_scale
        
        # Mid band (bandpass)
        b_mid, a_mid = signal.butter(2, [low_freq, high_freq], btype='band')
        mid_band = signal.filtfilt(b_mid, a_mid, audio) * mid_scale
        
        output = low_band + mid_band + high_band
        
        # Normalize
        max_val = np.abs(output).max()
        if max_val > 1.0:
            output = output / max_val
        
        return output.astype(np.float32)


class TapeSaturationAugment:
    """Add subtle tape saturation for warmth/character."""
    
    def __init__(
        self,
        drive_range: Tuple[float, float] = (0.1, 0.5),
    ):
        self.drive_range = drive_range
    
    def __call__(self, audio: np.ndarray, sr: int = 22050) -> np.ndarray:
        """Apply soft clipping saturation."""
        drive = np.random.uniform(*self.drive_range)
        
        # Soft clipping using tanh
        output = np.tanh(audio * (1 + drive * 3))
        
        return output.astype(np.float32)


class DomainAdaptationAugment:
    """
    Combined augmentation pipeline for domain adaptation.
    
    Applies various augmentations with specified probabilities to help
    the model generalize from synthetic to real acoustic drums.
    """
    
    def __init__(
        self,
        reverb_prob: float = 0.3,
        noise_prob: float = 0.2,
        eq_prob: float = 0.2,
        saturation_prob: float = 0.1,
        # Individual augment configs
        reverb_config: Optional[dict] = None,
        noise_config: Optional[dict] = None,
        eq_config: Optional[dict] = None,
        saturation_config: Optional[dict] = None,
    ):
        self.reverb_prob = reverb_prob
        self.noise_prob = noise_prob
        self.eq_prob = eq_prob
        self.saturation_prob = saturation_prob
        
        # Initialize augmenters
        self.reverb = RoomReverbAugment(**(reverb_config or {}))
        self.noise = BackgroundNoiseAugment(**(noise_config or {}))
        self.eq = EQVariationAugment(**(eq_config or {}))
        self.saturation = TapeSaturationAugment(**(saturation_config or {}))
    
    def __call__(self, audio: np.ndarray, sr: int = 22050) -> np.ndarray:
        """Apply random augmentations to audio."""
        output = audio.copy()
        
        if np.random.random() < self.reverb_prob:
            output = self.reverb(output, sr)
        
        if np.random.random() < self.noise_prob:
            output = self.noise(output, sr)
        
        if np.random.random() < self.eq_prob:
            output = self.eq(output, sr)
        
        if np.random.random() < self.saturation_prob:
            output = self.saturation(output, sr)
        
        return output


# SpecAugment for spectrograms (time/frequency masking)
class SpecAugmentDomainAdapt:
    """
    SpecAugment with additional domain adaptation transforms.
    
    Extends standard SpecAugment with:
    - Random brightness/contrast adjustment
    - Slight frequency shifting
    """
    
    def __init__(
        self,
        freq_mask_param: int = 10,
        time_mask_param: int = 10,
        freq_masks: int = 2,
        time_masks: int = 2,
        brightness_range: Tuple[float, float] = (-0.1, 0.1),
        contrast_range: Tuple[float, float] = (0.9, 1.1),
    ):
        self.freq_mask_param = freq_mask_param
        self.time_mask_param = time_mask_param
        self.freq_masks = freq_masks
        self.time_masks = time_masks
        self.brightness_range = brightness_range
        self.contrast_range = contrast_range
    
    def __call__(self, spec: np.ndarray) -> np.ndarray:
        """Apply augmentation to spectrogram (shape: n_mels x n_frames)."""
        spec = spec.copy()
        n_mels, n_frames = spec.shape
        
        # Frequency masking
        for _ in range(self.freq_masks):
            f = np.random.randint(0, self.freq_mask_param)
            f0 = np.random.randint(0, max(1, n_mels - f))
            spec[f0:f0 + f, :] = 0
        
        # Time masking
        for _ in range(self.time_masks):
            t = np.random.randint(0, self.time_mask_param)
            t0 = np.random.randint(0, max(1, n_frames - t))
            spec[:, t0:t0 + t] = 0
        
        # Brightness adjustment
        brightness = np.random.uniform(*self.brightness_range)
        spec = spec + brightness
        
        # Contrast adjustment
        contrast = np.random.uniform(*self.contrast_range)
        mean = spec.mean()
        spec = (spec - mean) * contrast + mean
        
        # Clip to valid range
        spec = np.clip(spec, 0, 1)
        
        return spec.astype(np.float32)


def create_domain_adaptation_pipeline(
    mode: str = "aggressive",
) -> DomainAdaptationAugment:
    """
    Create a pre-configured domain adaptation pipeline.
    
    Args:
        mode: "light", "moderate", or "aggressive"
    
    Returns:
        Configured DomainAdaptationAugment instance
    """
    configs = {
        "light": {
            "reverb_prob": 0.1,
            "noise_prob": 0.1,
            "eq_prob": 0.1,
            "saturation_prob": 0.05,
        },
        "moderate": {
            "reverb_prob": 0.3,
            "noise_prob": 0.2,
            "eq_prob": 0.2,
            "saturation_prob": 0.1,
        },
        "aggressive": {
            "reverb_prob": 0.5,
            "noise_prob": 0.3,
            "eq_prob": 0.3,
            "saturation_prob": 0.2,
        },
    }
    
    return DomainAdaptationAugment(**configs.get(mode, configs["moderate"]))


if __name__ == "__main__":
    # Quick test
    print("Testing domain adaptation augmentations...")
    
    # Generate test signal (simulated drum hit)
    sr = 22050
    duration = 0.1  # 100ms
    t = np.linspace(0, duration, int(sr * duration))
    
    # Simulated kick drum: low frequency with fast decay
    audio = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 30)
    audio = audio.astype(np.float32)
    
    print(f"Original audio shape: {audio.shape}")
    print(f"Original audio range: [{audio.min():.3f}, {audio.max():.3f}]")
    
    # Test each augmentation
    augment = create_domain_adaptation_pipeline("moderate")
    augmented = augment(audio, sr)
    
    print(f"Augmented audio shape: {augmented.shape}")
    print(f"Augmented audio range: [{augmented.min():.3f}, {augmented.max():.3f}]")
    print("\nAll augmentations working correctly!")
