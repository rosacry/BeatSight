"""
Training augmentation utilities for BeatSight.

This package provides data augmentation techniques for improving
model generalization and calibration.

Modules:
    mixup: Mixup and CutMix augmentation for mel-spectrograms
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

__all__ = [
    "MixupCutmix",
    "AugmentationResult",
    "mixup_data",
    "cutmix_data",
    "mixed_criterion",
    "SoftTargetCrossEntropy",
    "create_soft_labels",
    "get_mixup_args",
    "create_augmenter_from_args",
]
