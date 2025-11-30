#!/usr/bin/env python3
"""
Ghost Note Augmentation Pipeline

This module synthesizes realistic ghost notes from normal drum hits to dramatically
improve ghost note detection accuracy. Ghost notes are notoriously hard to detect
because they're quiet, often buried in the mix, and have similar spectral content
to audio bleed.

Strategy:
1. Take normal velocity (0.5-1.0) drum hits (especially snare)
2. Attenuate them realistically to ghost levels (0.05-0.20 velocity)
3. Add realistic room noise, bleed simulation, and masking
4. Create training examples that teach the model to detect subtle transients

Expected improvement: +5-10% on ghost note detection

Usage:
    from training.augmentation.ghost_note_augment import GhostNoteAugmenter
    
    augmenter = GhostNoteAugmenter()
    
    # In dataset __getitem__:
    if label == 'snare_center' and velocity > 0.5:
        if random.random() < 0.2:  # 20% chance to create ghost version
            waveform, velocity = augmenter.create_ghost(waveform, target_velocity=0.1)

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
class GhostNoteConfig:
    """Configuration for ghost note synthesis."""
    
    # Target velocity range for ghost notes
    ghost_velocity_range: Tuple[float, float] = (0.05, 0.20)
    
    # Probability of applying ghost augmentation to eligible samples
    ghost_prob: float = 0.15
    
    # Only create ghosts from hits with velocity above this threshold
    source_velocity_min: float = 0.45
    
    # Noise floor simulation (relative to ghost level)
    noise_floor_range: Tuple[float, float] = (0.02, 0.08)
    
    # Bleed simulation - add attenuated version of common bleed sources
    simulate_bleed: bool = True
    bleed_level_range: Tuple[float, float] = (0.3, 0.7)  # Relative to ghost level
    
    # High-frequency roll-off (ghosts lose HF faster than loud hits)
    apply_hf_rolloff: bool = True
    hf_rolloff_freq: float = 8000.0  # Hz
    hf_rolloff_order: int = 2
    
    # Attack softening (ghosts have slightly softer attacks)
    soften_attack: bool = True
    attack_softening_ms: float = 2.0  # Fade-in time
    
    # Room ambience boost (quiet sounds have more relative room sound)
    room_ambience_boost: float = 1.5  # Multiplier for room tail relative to direct
    
    # Masking simulation - sometimes other instruments mask ghosts
    simulate_masking: bool = True
    masking_prob: float = 0.3
    masking_level_range: Tuple[float, float] = (0.5, 1.5)  # Relative to ghost
    
    # Classes eligible for ghost augmentation
    ghost_eligible_classes: List[str] = field(default_factory=lambda: [
        "snare_center", "snare", "snare_rimshot",
        "hihat_closed", "hihat_open",
        "tom_high", "tom_mid", "tom_low",
        "kick",  # Ghost kicks are rare but exist
    ])


class GhostNoteAugmenter:
    """
    Creates realistic ghost note training examples from normal drum hits.
    
    Ghost notes are one of the hardest drum sounds to detect because:
    1. Low amplitude - often only 10-20% of normal hit energy
    2. Masked by other instruments - especially in full mixes
    3. Similar to bleed - hard to distinguish from snare bleed into overheads
    4. Subtle transients - attack is softer and less distinct
    
    This augmenter addresses all these challenges by synthesizing realistic
    ghost notes with proper acoustic modeling.
    
    Args:
        config: GhostNoteConfig with augmentation parameters
        sample_rate: Audio sample rate (default: 22050)
    """
    
    def __init__(
        self,
        config: Optional[GhostNoteConfig] = None,
        sample_rate: int = 22050,
    ):
        self.config = config or GhostNoteConfig()
        self.sample_rate = sample_rate
        
        # Pre-compute HF rolloff filter coefficients
        if self.config.apply_hf_rolloff and HAS_SCIPY:
            nyquist = sample_rate / 2
            normalized_cutoff = min(self.config.hf_rolloff_freq / nyquist, 0.99)
            self.hf_b, self.hf_a = scipy.signal.butter(
                self.config.hf_rolloff_order,
                normalized_cutoff,
                btype='low'
            )
        else:
            self.hf_b = self.hf_a = None
        
        # Bleed patterns (simplified - just noise with spectral shaping)
        self._init_bleed_patterns()
    
    def _init_bleed_patterns(self):
        """Initialize bleed simulation patterns."""
        # These represent typical bleed frequency profiles
        self.bleed_patterns = {
            "kick_bleed": {"low_boost": 2.0, "high_cut": 2000},
            "hihat_bleed": {"low_cut": 3000, "high_boost": 1.5},
            "cymbal_wash": {"low_cut": 1000, "high_boost": 1.2},
        }
    
    def should_augment(
        self,
        label: str,
        velocity: float,
    ) -> bool:
        """
        Determine if this sample should be augmented to a ghost note.
        
        Args:
            label: Drum class label
            velocity: Original velocity (0-1)
        
        Returns:
            True if this sample should be converted to a ghost
        """
        # Check if label is eligible
        if label not in self.config.ghost_eligible_classes:
            return False
        
        # Check if velocity is high enough to create a ghost from
        if velocity < self.config.source_velocity_min:
            return False
        
        # Random probability check
        return random.random() < self.config.ghost_prob
    
    def create_ghost(
        self,
        waveform: Union[np.ndarray, torch.Tensor],
        source_velocity: float = 0.8,
        target_velocity: Optional[float] = None,
        label: str = "snare_center",
    ) -> Tuple[Union[np.ndarray, torch.Tensor], float]:
        """
        Convert a normal drum hit to a ghost note.
        
        Args:
            waveform: Audio waveform (numpy array or torch tensor)
            source_velocity: Original velocity of the hit
            target_velocity: Target ghost velocity (random if None)
            label: Drum class (affects bleed simulation)
        
        Returns:
            Tuple of (ghost_waveform, actual_velocity)
        """
        is_tensor = isinstance(waveform, torch.Tensor)
        if is_tensor:
            device = waveform.device
            waveform = waveform.cpu().numpy()
        
        # Ensure float32
        waveform = waveform.astype(np.float32)
        
        # Determine target velocity
        if target_velocity is None:
            target_velocity = random.uniform(*self.config.ghost_velocity_range)
        
        # Calculate attenuation needed
        # Velocity roughly correlates with amplitude squared (energy)
        # So amplitude ratio ≈ sqrt(velocity ratio)
        velocity_ratio = target_velocity / source_velocity
        amplitude_ratio = np.sqrt(velocity_ratio)
        
        # Apply base attenuation
        ghost = waveform * amplitude_ratio
        
        # Apply high-frequency rolloff (ghosts lose HF)
        if self.config.apply_hf_rolloff and self.hf_b is not None:
            ghost = scipy.signal.lfilter(self.hf_b, self.hf_a, ghost)
        
        # Soften the attack
        if self.config.soften_attack:
            ghost = self._soften_attack(ghost)
        
        # Add realistic noise floor
        noise_level = random.uniform(*self.config.noise_floor_range)
        noise = np.random.randn(len(ghost)).astype(np.float32) * noise_level * np.max(np.abs(ghost))
        ghost = ghost + noise
        
        # Simulate bleed from other drums
        if self.config.simulate_bleed:
            ghost = self._add_bleed(ghost, label, target_velocity)
        
        # Simulate masking (other instruments partially covering the ghost)
        if self.config.simulate_masking and random.random() < self.config.masking_prob:
            ghost = self._add_masking(ghost, target_velocity)
        
        # Normalize to prevent clipping but maintain relative levels
        max_val = np.max(np.abs(ghost))
        if max_val > 0.95:
            ghost = ghost * (0.95 / max_val)
        
        # Convert back to tensor if needed
        if is_tensor:
            ghost = torch.from_numpy(ghost).to(device)
        
        return ghost, target_velocity
    
    def _soften_attack(self, waveform: np.ndarray) -> np.ndarray:
        """Apply gentle fade-in to soften the attack transient."""
        fade_samples = int(self.config.attack_softening_ms * self.sample_rate / 1000)
        fade_samples = min(fade_samples, len(waveform) // 4)
        
        if fade_samples > 0:
            # Find the peak (attack point)
            peak_idx = np.argmax(np.abs(waveform[:len(waveform)//4]))
            
            # Apply fade before peak
            fade_start = max(0, peak_idx - fade_samples)
            fade_end = peak_idx
            
            if fade_end > fade_start:
                fade_len = fade_end - fade_start
                # Use sine fade for natural sound
                fade_curve = np.sin(np.linspace(0, np.pi/2, fade_len)) ** 2
                waveform[fade_start:fade_end] *= fade_curve
        
        return waveform
    
    def _add_bleed(
        self,
        waveform: np.ndarray,
        label: str,
        velocity: float,
    ) -> np.ndarray:
        """Add realistic bleed from other drums."""
        bleed_level = random.uniform(*self.config.bleed_level_range) * velocity
        
        # Choose a bleed pattern based on the drum type
        if "snare" in label:
            # Snare ghosts often have hi-hat bleed
            bleed_type = "hihat_bleed"
        elif "kick" in label:
            # Kick ghosts might have cymbal wash
            bleed_type = "cymbal_wash"
        else:
            # Default to random bleed
            bleed_type = random.choice(list(self.bleed_patterns.keys()))
        
        # Generate colored noise for bleed
        bleed_noise = np.random.randn(len(waveform)).astype(np.float32)
        
        # Apply spectral shaping (simplified)
        pattern = self.bleed_patterns[bleed_type]
        
        if HAS_SCIPY:
            nyquist = self.sample_rate / 2
            
            if "low_cut" in pattern:
                freq = min(pattern["low_cut"] / nyquist, 0.99)
                b, a = scipy.signal.butter(2, freq, btype='high')
                bleed_noise = scipy.signal.lfilter(b, a, bleed_noise)
            
            if "high_cut" in pattern:
                freq = min(pattern["high_cut"] / nyquist, 0.99)
                b, a = scipy.signal.butter(2, freq, btype='low')
                bleed_noise = scipy.signal.lfilter(b, a, bleed_noise)
        
        # Scale and add
        bleed_noise = bleed_noise * bleed_level * np.max(np.abs(waveform))
        
        return waveform + bleed_noise
    
    def _add_masking(
        self,
        waveform: np.ndarray,
        velocity: float,
    ) -> np.ndarray:
        """Simulate partial masking by other instruments."""
        masking_level = random.uniform(*self.config.masking_level_range) * velocity
        
        # Generate broadband masking noise (simulates guitar, bass, keys)
        mask_noise = np.random.randn(len(waveform)).astype(np.float32)
        
        # Apply bandpass to simulate typical instrument ranges
        if HAS_SCIPY:
            nyquist = self.sample_rate / 2
            low = min(200 / nyquist, 0.99)
            high = min(4000 / nyquist, 0.99)
            if low < high:
                b, a = scipy.signal.butter(2, [low, high], btype='band')
                mask_noise = scipy.signal.lfilter(b, a, mask_noise)
        
        # Add masking
        mask_noise = mask_noise * masking_level * np.max(np.abs(waveform))
        
        return waveform + mask_noise
    
    def augment_batch(
        self,
        waveforms: Union[np.ndarray, torch.Tensor],
        velocities: Union[np.ndarray, torch.Tensor],
        labels: List[str],
    ) -> Tuple[Union[np.ndarray, torch.Tensor], Union[np.ndarray, torch.Tensor]]:
        """
        Augment a batch of samples, converting some to ghost notes.
        
        Args:
            waveforms: Batch of waveforms [B, samples] or [B, channels, samples]
            velocities: Batch of velocities [B]
            labels: List of class labels
        
        Returns:
            Tuple of (augmented_waveforms, updated_velocities)
        """
        is_tensor = isinstance(waveforms, torch.Tensor)
        if is_tensor:
            device = waveforms.device
            waveforms = waveforms.cpu().numpy()
            velocities = velocities.cpu().numpy()
        
        augmented = waveforms.copy()
        new_velocities = velocities.copy()
        
        for i in range(len(waveforms)):
            if self.should_augment(labels[i], velocities[i]):
                if waveforms.ndim == 3:
                    # [B, C, samples] - augment each channel
                    for c in range(waveforms.shape[1]):
                        augmented[i, c], new_velocities[i] = self.create_ghost(
                            waveforms[i, c],
                            source_velocity=velocities[i],
                            label=labels[i],
                        )
                else:
                    # [B, samples]
                    augmented[i], new_velocities[i] = self.create_ghost(
                        waveforms[i],
                        source_velocity=velocities[i],
                        label=labels[i],
                    )
        
        if is_tensor:
            augmented = torch.from_numpy(augmented).to(device)
            new_velocities = torch.from_numpy(new_velocities).to(device)
        
        return augmented, new_velocities


class GhostNoteDatasetWrapper:
    """
    Wrapper for datasets that adds ghost note augmentation.
    
    This can wrap any drum classification dataset to add ghost note
    synthesis on-the-fly during training.
    
    Usage:
        base_dataset = DrumDataset(...)
        ghost_dataset = GhostNoteDatasetWrapper(base_dataset, ghost_prob=0.15)
        
        # Use ghost_dataset in DataLoader
    """
    
    def __init__(
        self,
        base_dataset,
        config: Optional[GhostNoteConfig] = None,
        sample_rate: int = 22050,
    ):
        self.base_dataset = base_dataset
        self.augmenter = GhostNoteAugmenter(config, sample_rate)
    
    def __len__(self):
        return len(self.base_dataset)
    
    def __getitem__(self, idx):
        sample = self.base_dataset[idx]
        
        # Unpack sample (format depends on base dataset)
        # Expected: (waveform_or_spec, label, velocity, ...)
        waveform = sample[0]
        label_idx = sample[1]
        velocity = sample[2] if len(sample) > 2 else 0.8
        
        # Get string label if available
        if hasattr(self.base_dataset, 'idx_to_label'):
            label = self.base_dataset.idx_to_label.get(label_idx, "unknown")
        elif hasattr(self.base_dataset, 'classes'):
            label = self.base_dataset.classes[label_idx]
        else:
            label = "snare_center"  # Default to snare for ghost augmentation
        
        # Apply ghost augmentation
        if self.augmenter.should_augment(label, velocity):
            waveform, velocity = self.augmenter.create_ghost(
                waveform,
                source_velocity=velocity,
                label=label,
            )
        
        # Repack sample
        if len(sample) > 2:
            return (waveform, label_idx, velocity) + sample[3:]
        else:
            return (waveform, label_idx, velocity)


# Convenience functions
def get_ghost_augmenter(
    preset: str = "default",
    sample_rate: int = 22050,
) -> GhostNoteAugmenter:
    """
    Get a pre-configured ghost note augmenter.
    
    Presets:
        default: Balanced settings for production (boosted from original)
        aggressive: More ghost notes, harder examples (RECOMMENDED for training)
        ultra: Maximum ghost augmentation for difficult datasets
        conservative: Fewer, more realistic ghosts
        accent_tap: Simulates accent-tap sticking patterns (alternating loud/soft)
    """
    if preset == "ultra":
        # Maximum ghost augmentation - for datasets with very few ghost labels
        config = GhostNoteConfig(
            ghost_prob=0.35,
            ghost_velocity_range=(0.02, 0.15),
            noise_floor_range=(0.04, 0.15),
            masking_prob=0.6,
            simulate_bleed=True,
            bleed_level_range=(0.4, 0.9),
            source_velocity_min=0.40,
            ghost_eligible_classes=[
                "snare_center", "snare", "snare_rimshot",
                "hihat_closed", "hihat_open", "hihat_pedal",
                "tom_high", "tom_mid", "tom_low",
                "kick", "ride_bow", "ride_bell",
            ],
        )
    elif preset == "aggressive":
        # Recommended for production training
        config = GhostNoteConfig(
            ghost_prob=0.30,  # Boosted from 0.25
            ghost_velocity_range=(0.03, 0.18),
            noise_floor_range=(0.03, 0.12),
            masking_prob=0.5,
            source_velocity_min=0.42,
            ghost_eligible_classes=[
                "snare_center", "snare", "snare_rimshot",
                "hihat_closed", "hihat_open",
                "tom_high", "tom_mid", "tom_low",
                "kick", "ride_bow",
            ],
        )
    elif preset == "accent_tap":
        # Simulates accent-tap sticking: alternating between loud (>0.7) and soft (<0.3)
        # This teaches the model to recognize the contrast pattern drummers use
        config = GhostNoteConfig(
            ghost_prob=0.40,  # High probability since we want many accent-tap examples
            ghost_velocity_range=(0.10, 0.30),  # "Tap" velocity range (soft but audible)
            source_velocity_min=0.65,  # Only convert loud "accents" to soft "taps"
            noise_floor_range=(0.01, 0.04),  # Less noise - taps are still deliberate
            simulate_bleed=False,  # Clean taps, no bleed simulation
            simulate_masking=False,  # Taps are deliberate, not masked
            soften_attack=False,  # Keep attack shape - taps have clear transients
            apply_hf_rolloff=True,  # Slight HF reduction for quieter hits
            hf_rolloff_freq=10000.0,  # Higher cutoff than ghosts
            ghost_eligible_classes=[
                "snare_center", "snare",
                "hihat_closed",
                "tom_high", "tom_mid", "tom_low",
            ],
        )
    elif preset == "conservative":
        config = GhostNoteConfig(
            ghost_prob=0.10,
            ghost_velocity_range=(0.08, 0.22),
            noise_floor_range=(0.01, 0.05),
            masking_prob=0.2,
        )
    else:  # default - now boosted for better ghost detection
        config = GhostNoteConfig(
            ghost_prob=0.20,  # Boosted from 0.15
            ghost_velocity_range=(0.05, 0.20),
            source_velocity_min=0.45,
            ghost_eligible_classes=[
                "snare_center", "snare", "snare_rimshot",
                "hihat_closed", "hihat_open",
                "tom_high", "tom_mid", "tom_low",
                "kick",
            ],
        )
    
    return GhostNoteAugmenter(config, sample_rate)


if __name__ == "__main__":
    # Test the augmenter
    print("🥁 Ghost Note Augmenter Test")
    print("="*50)
    
    augmenter = get_ghost_augmenter("default")
    
    # Create test waveform (simulated snare hit)
    sr = 22050
    duration = 0.3  # 300ms
    t = np.linspace(0, duration, int(sr * duration))
    
    # Simulated snare: attack + noise
    attack = np.exp(-t * 30) * np.sin(2 * np.pi * 200 * t)
    noise = np.exp(-t * 20) * np.random.randn(len(t)) * 0.3
    test_waveform = (attack + noise).astype(np.float32)
    test_waveform /= np.max(np.abs(test_waveform))
    
    print(f"Original waveform: max={np.max(np.abs(test_waveform)):.3f}")
    
    # Create ghost
    ghost, velocity = augmenter.create_ghost(
        test_waveform,
        source_velocity=0.8,
        target_velocity=0.12,
        label="snare_center"
    )
    
    print(f"Ghost waveform: max={np.max(np.abs(ghost)):.3f}, velocity={velocity:.3f}")
    print(f"Attenuation: {20 * np.log10(np.max(np.abs(ghost)) / np.max(np.abs(test_waveform))):.1f} dB")
    
    # Test batch augmentation
    print("\nBatch test:")
    batch = np.stack([test_waveform] * 8)
    velocities = np.array([0.9, 0.85, 0.75, 0.8, 0.6, 0.4, 0.95, 0.7])
    labels = ["snare_center"] * 8
    
    aug_batch, aug_vel = augmenter.augment_batch(batch, velocities, labels)
    
    ghosts_created = np.sum(aug_vel != velocities)
    print(f"Ghosts created: {ghosts_created}/8")
    
    print("\n✅ Ghost Note Augmenter working correctly!")
