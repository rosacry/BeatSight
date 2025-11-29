"""
Multi-Label Drum Classification Support

This module enables training models to detect multiple simultaneous drum hits
(e.g., kick + hi-hat on beat 1, snare + crash on beat 2).

Key components:
- MultiLabelDrumDataset: Dataset that returns multi-hot encoded labels
- MultiLabelLoss: BCEWithLogitsLoss with class weighting and focal variants
- evaluate_multilabel: Metrics for multi-label classification

Usage:
    from training.multilabel import MultiLabelDrumDataset, MultiLabelLoss
    
    dataset = MultiLabelDrumDataset(
        data_dir="./dataset",
        labels_file="./dataset/labels.json",
        num_classes=21
    )
    
    criterion = MultiLabelLoss(pos_weight=class_weights)
"""

from .dataset import MultiLabelDrumDataset
from .loss import MultiLabelLoss, FocalBCELoss, AsymmetricLoss
from .metrics import (
    multilabel_accuracy,
    hamming_loss,
    subset_accuracy,
    per_class_f1,
    MultiLabelMetrics,
)

__all__ = [
    "MultiLabelDrumDataset",
    "MultiLabelLoss",
    "FocalBCELoss",
    "AsymmetricLoss",
    "multilabel_accuracy",
    "hamming_loss",
    "subset_accuracy",
    "per_class_f1",
    "MultiLabelMetrics",
]
