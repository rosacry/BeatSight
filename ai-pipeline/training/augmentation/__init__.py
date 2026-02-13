"""
Training augmentation utilities for BeatSight.

This package provides data augmentation techniques for improving
model generalization and calibration.

Modules:
    mixup: Mixup and CutMix augmentation for mel-spectrograms
    ghost_note_augment: Ghost note synthesis for improved soft-hit detection
    waveform: Waveform-level audio augmentation (time stretch, pitch shift)
    specaugment: SpecAugment frequency/time masking
    fmix: Fourier-domain mixup
"""

from .mixup import (
    MixupCutmix,
    AugmentationResult,
    mixup_data,
    cutmix_data,
    mixed_criterion,
    SoftTargetCrossEntropy,
    create_soft_labels,
    get_mixup_args,
    create_augmenter_from_args,
)

from .ghost_note_augment import (
    GhostNoteAugmenter,
    GhostNoteConfig,
    GhostNoteDatasetWrapper,
    get_ghost_augmenter,
)

__all__ = [
    # Mixup/CutMix
    "MixupCutmix",
    "AugmentationResult",
    "mixup_data",
    "cutmix_data",
    "mixed_criterion",
    "SoftTargetCrossEntropy",
    "create_soft_labels",
    "get_mixup_args",
    "create_augmenter_from_args",
    # Ghost Note Augmentation
    "GhostNoteAugmenter",
    "GhostNoteConfig",
    "GhostNoteDatasetWrapper",
    "get_ghost_augmenter",
]
