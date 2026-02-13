#!/usr/bin/env python3
"""
Accent-Tap Pattern Augmentation Pipeline

This module synthesizes accent-tap sticking patterns from normal drum hits to improve
detection of dynamic variations. Accent-tap patterns (paradiddle accents, flam accents,
etc.) are common in drumming but under-represented in training data.

Strategy:
1. Take medium velocity (0.4-0.7) drum hits as "taps"
2. Take high velocity (0.85-1.0) drum hits as "accents"  
3. Create synthetic accent-tap pattern examples by adjusting velocity
4. Add realistic acoustic modeling (accents have brighter transients)

Expected improvement: +2-5% on accent/tap differentiation

Usage:
    from training.augmentation.accent_tap_augment import AccentTapAugmenter
    
    augmenter = AccentTapAugmenter()
    
    # In dataset __getitem__:
    if augmenter.should_augment(label, velocity):
        waveform, velocity = augmenter.create_variant(waveform, velocity, label)

Author: BeatSight AI Pipeline
Date: November 2025
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Union

import numpy as np
import torch

try:
    import scipy.signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@dataclass
class AccentTapConfig:
    """Configuration for accent-tap pattern augmentation."""
    
    # Velocity thresholds for classification
    accent_velocity_min: float = 0.85  # Above this is an accent
    tap_velocity_max: float = 0.55  # Below this is a tap
    
    # Target velocity ranges for synthesis
    accent_target_range: Tuple[float, float] = (0.85, 0.98)
    tap_target_range: Tuple[float, float] = (0.35, 0.55)
    
    # Probability of applying augmentation to eligible samples
    accent_prob: float = 0.12  # Convert normal to accent
    tap_prob: float = 0.12  # Convert normal to tap
    
    # Acoustic modeling for accents
    accent_brightness_boost: float = 1.3  # High-frequency boost for accents
    accent_transient_sharpen: float = 1.2  # Transient sharpening factor
    
    # Acoustic modeling for taps
    tap_brightness_reduction: float = 0.85  # HF reduction for taps
    tap_softness_factor: float = 1.5  # Attack softening in ms
    
    # Classes eligible for accent-tap augmentation
    eligible_classes: List[str] = field(default_factory=lambda: [
        "snare_center", "snare", "snare_rimshot", "rimshot",
        "hihat_closed", "hihat_open",
        "tom_high", "tom_mid", "tom_low",
        "ride_bow", "ride_bell",
    ])


class AccentTapAugmenter:
    """
    Creates accent and tap variants from normal drum hits.
    
    This helps the model learn to distinguish between:
    - Accents: Loud, bright hits with sharp transients
    - Taps: Quiet, softer hits with gentler attacks
    - Normal: Medium velocity hits
    
    Args:
        config: AccentTapConfig with augmentation parameters
        sample_rate: Audio sample rate (default: 22050)
    """
    
    def __init__(
        self,
        config: Optional[AccentTapConfig] = None,
        sample_rate: int = 22050,
    ):
        self.config = config or AccentTapConfig()
        self.sample_rate = sample_rate
        
        # Pre-compute high-shelf filter for brightness adjustment
        if HAS_SCIPY:
            nyquist = sample_rate / 2
            # High-shelf at 3kHz for brightness adjustment
            self.brightness_freq = 3000
            self.brightness_b, self.brightness_a = self._design_shelf_filter(
                self.brightness_freq / nyquist,
                gain_db=3.0,  # Will be scaled by factor
            )
        else:
            self.brightness_b = self.brightness_a = None
    
    def _design_shelf_filter(self, normalized_freq: float, gain_db: float) -> Tuple[np.ndarray, np.ndarray]:
        """Design a simple high-shelf filter."""
        # Simple IIR approximation of high-shelf
        # This is a simplified design; scipy.signal.iirdesign could be used for better accuracy
        w0 = normalized_freq * np.pi
        A = 10 ** (gain_db / 40)  # amplitude
        
        alpha = np.sin(w0) / 2 * np.sqrt((A + 1/A) * (1/0.7 - 1) + 2)
        cos_w0 = np.cos(w0)
        
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha)
        a0 = (A + 1) - (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha
        
        b = np.array([b0, b1, b2]) / a0
        a = np.array([1.0, a1 / a0, a2 / a0])
        
        return b, a
    
    def should_augment(
        self,
        label: str,
        velocity: float,
    ) -> bool:
        """
        Determine if this sample should be augmented.
        
        Only augments samples in the "normal" velocity range (not already accent or tap).
        
        Args:
            label: Drum class label
            velocity: Original velocity (0-1)
        
        Returns:
            True if this sample should be augmented
        """
        # Check if label is eligible
        if label not in self.config.eligible_classes:
            return False
        
        # Only augment normal velocity range (between tap and accent thresholds)
        if velocity <= self.config.tap_velocity_max or velocity >= self.config.accent_velocity_min:
            return False
        
        # Random probability check (combined accent + tap probability)
        return random.random() < (self.config.accent_prob + self.config.tap_prob)
    
    def create_variant(
        self,
        waveform: Union[np.ndarray, torch.Tensor],
        source_velocity: float,
        label: str = "snare_center",
    ) -> Tuple[Union[np.ndarray, torch.Tensor], float]:
        """
        Convert a normal drum hit to an accent or tap variant.
        
        Args:
            waveform: Audio waveform (numpy array or torch tensor)
            source_velocity: Original velocity of the hit (0-1)
            label: Drum class (affects acoustic modeling)
        
        Returns:
            Tuple of (modified_waveform, new_velocity)
        """
        is_tensor = isinstance(waveform, torch.Tensor)
        if is_tensor:
            device = waveform.device
            waveform = waveform.cpu().numpy()
        
        # Ensure float32
        waveform = waveform.astype(np.float32)
        
        # Decide whether to create accent or tap
        # Weight by their respective probabilities
        accent_weight = self.config.accent_prob
        tap_weight = self.config.tap_prob
        total_weight = accent_weight + tap_weight
        
        if random.random() < (accent_weight / total_weight):
            # Create accent
            waveform, velocity = self._create_accent(waveform, source_velocity, label)
        else:
            # Create tap
            waveform, velocity = self._create_tap(waveform, source_velocity, label)
        
        # Convert back to tensor if input was tensor
        if is_tensor:
            waveform = torch.from_numpy(waveform).to(device)
        
        return waveform, velocity
    
    def _create_accent(
        self,
        waveform: np.ndarray,
        source_velocity: float,
        label: str,
    ) -> Tuple[np.ndarray, float]:
        """Create an accent (loud, bright hit) from a normal hit."""
        # Target velocity
        target_velocity = random.uniform(*self.config.accent_target_range)
        
        # Amplitude scaling - boost gain
        velocity_ratio = target_velocity / max(source_velocity, 0.1)
        gain_linear = velocity_ratio ** 0.7  # Slightly compressed scaling
        
        waveform = waveform * gain_linear
        
        # Apply brightness boost (accents have more high-frequency content)
        if HAS_SCIPY and self.brightness_b is not None:
            # Scale the filter gain by brightness_boost factor
            boost_factor = (self.config.accent_brightness_boost - 1.0) * 3.0  # Convert to dB-ish
            boosted_b = self.brightness_b * (1.0 + boost_factor * 0.3)
            try:
                waveform = scipy.signal.filtfilt(boosted_b, self.brightness_a, waveform)
            except ValueError:
                pass  # Skip filtering if it fails
        
        # Transient sharpening (accents have sharper attacks)
        if len(waveform) > 100:
            attack_samples = min(50, len(waveform) // 10)
            attack = waveform[:attack_samples]
            
            # Enhance the transient by increasing the slope
            sharpen = self.config.accent_transient_sharpen
            envelope = np.linspace(sharpen, 1.0, attack_samples)
            waveform[:attack_samples] = attack * envelope
        
        # Normalize to prevent clipping
        max_val = np.abs(waveform).max()
        if max_val > 0.95:
            waveform = waveform * (0.95 / max_val)
        
        return waveform.astype(np.float32), target_velocity
    
    def _create_tap(
        self,
        waveform: np.ndarray,
        source_velocity: float,
        label: str,
    ) -> Tuple[np.ndarray, float]:
        """Create a tap (quiet, soft hit) from a normal hit."""
        # Target velocity
        target_velocity = random.uniform(*self.config.tap_target_range)
        
        # Amplitude scaling - reduce gain
        velocity_ratio = target_velocity / max(source_velocity, 0.1)
        gain_linear = velocity_ratio ** 0.8  # Slightly expanded scaling for taps
        
        waveform = waveform * gain_linear
        
        # Apply brightness reduction (taps have less high-frequency content)
        if HAS_SCIPY and self.brightness_b is not None:
            # Invert the filter to reduce brightness
            reduction_factor = -(1.0 - self.config.tap_brightness_reduction) * 3.0
            reduced_b = self.brightness_b * (1.0 + reduction_factor * 0.3)
            try:
                waveform = scipy.signal.filtfilt(reduced_b, self.brightness_a, waveform)
            except ValueError:
                pass
        
        # Attack softening (taps have gentler attacks)
        softness_ms = self.config.tap_softness_factor
        softness_samples = int(softness_ms * self.sample_rate / 1000)
        if len(waveform) > softness_samples * 2:
            fade_in = np.linspace(0.0, 1.0, softness_samples) ** 0.7
            waveform[:softness_samples] = waveform[:softness_samples] * fade_in
        
        return waveform.astype(np.float32), target_velocity


def get_accent_tap_augmenter(
    preset: str = "default",
    sample_rate: int = 22050,
) -> AccentTapAugmenter:
    """
    Factory function to create AccentTapAugmenter with preset configurations.
    
    Args:
        preset: Configuration preset ("default", "aggressive", "conservative")
        sample_rate: Audio sample rate
        
    Returns:
        Configured AccentTapAugmenter instance
    """
    if preset == "aggressive":
        config = AccentTapConfig(
            accent_prob=0.20,
            tap_prob=0.20,
            accent_velocity_min=0.80,
            tap_velocity_max=0.60,
            accent_brightness_boost=1.5,
            tap_brightness_reduction=0.75,
        )
    elif preset == "conservative":
        config = AccentTapConfig(
            accent_prob=0.08,
            tap_prob=0.08,
            accent_velocity_min=0.90,
            tap_velocity_max=0.50,
            accent_brightness_boost=1.15,
            tap_brightness_reduction=0.90,
        )
    else:  # default
        config = AccentTapConfig()
    
    return AccentTapAugmenter(config=config, sample_rate=sample_rate)
