"""Training losses package."""

from training.losses.focal_loss import FocalLoss, FocalLossWithMixup, AsymmetricFocalLoss, get_focal_loss
from training.losses.deep_supervision import (
    DeepSupervisionLoss,
    DeepSupervision,
    AuxiliaryHead,
)
from training.losses.class_balanced_loss import (
    ClassBalancedLoss,
    ClassBalancedFocalLoss,
    ClassBalancedCrossEntropy,
    compute_class_balanced_weights,
    compute_effective_number,
    get_class_balanced_loss,
)

__all__ = [
    # Focal Loss
    "FocalLoss",
    "FocalLossWithMixup",
    "AsymmetricFocalLoss",
    "get_focal_loss",
    # Class-Balanced Loss (CVPR 2019)
    "ClassBalancedLoss",
    "ClassBalancedFocalLoss",
    "ClassBalancedCrossEntropy",
    "compute_class_balanced_weights",
    "compute_effective_number",
    "get_class_balanced_loss",
    # Deep Supervision
    "DeepSupervisionLoss",
    "DeepSupervision",
    "AuxiliaryHead",
]
