"""
Multi-Label Classification Metrics

Metrics specifically designed for multi-label drum classification where
multiple classes can be active simultaneously.

Key metrics:
- Hamming Loss: Fraction of incorrectly predicted labels
- Subset Accuracy: Exact match (all labels must be correct)
- Per-class F1: F1 score for each class independently
- Micro/Macro F1: Aggregated F1 across all classes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F


@dataclass
class MultiLabelMetrics:
    """Container for multi-label classification metrics."""
    
    hamming_loss: float
    subset_accuracy: float
    micro_f1: float
    macro_f1: float
    per_class_f1: Dict[str, float]
    per_class_precision: Dict[str, float]
    per_class_recall: Dict[str, float]
    
    # Additional useful metrics
    avg_labels_per_sample: float
    samples_with_multilabel: int
    total_samples: int
    
    def __repr__(self) -> str:
        return (
            f"MultiLabelMetrics(\n"
            f"  hamming_loss={self.hamming_loss:.4f},\n"
            f"  subset_accuracy={self.subset_accuracy:.4f},\n"
            f"  micro_f1={self.micro_f1:.4f},\n"
            f"  macro_f1={self.macro_f1:.4f},\n"
            f"  samples_with_multilabel={self.samples_with_multilabel}/{self.total_samples}\n"
            f")"
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        result = {
            "hamming_loss": self.hamming_loss,
            "subset_accuracy": self.subset_accuracy,
            "micro_f1": self.micro_f1,
            "macro_f1": self.macro_f1,
            "avg_labels_per_sample": self.avg_labels_per_sample,
            "samples_with_multilabel": self.samples_with_multilabel,
            "total_samples": self.total_samples,
        }
        # Add per-class metrics with prefix
        for name, value in self.per_class_f1.items():
            result[f"f1/{name}"] = value
        return result


def hamming_loss(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    threshold: float = 0.5
) -> float:
    """
    Compute Hamming Loss (fraction of incorrectly predicted labels).
    
    Lower is better. Range: [0, 1]
    
    Args:
        predictions: Predicted probabilities or logits, shape (N, C)
        targets: Ground truth multi-hot labels, shape (N, C)
        threshold: Classification threshold for predictions
    
    Returns:
        Hamming loss value
    """
    if predictions.requires_grad:
        predictions = predictions.detach()
    
    # Apply threshold
    pred_binary = (torch.sigmoid(predictions) >= threshold).float()
    
    # Count mismatches
    mismatches = (pred_binary != targets).float().sum()
    total = predictions.numel()
    
    return (mismatches / total).item()


def subset_accuracy(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    threshold: float = 0.5
) -> float:
    """
    Compute Subset Accuracy (exact match ratio).
    
    A prediction is correct only if ALL labels are correct.
    This is a strict metric - partial matches don't count.
    
    Args:
        predictions: Predicted probabilities or logits, shape (N, C)
        targets: Ground truth multi-hot labels, shape (N, C)
        threshold: Classification threshold
    
    Returns:
        Subset accuracy (fraction of exact matches)
    """
    if predictions.requires_grad:
        predictions = predictions.detach()
    
    pred_binary = (torch.sigmoid(predictions) >= threshold).float()
    
    # Check if all labels match for each sample
    exact_matches = (pred_binary == targets).all(dim=1).float()
    
    return exact_matches.mean().item()


def multilabel_accuracy(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    threshold: float = 0.5
) -> float:
    """
    Compute per-sample accuracy averaged across samples.
    
    For each sample: accuracy = intersection / union of predicted and true labels
    
    Args:
        predictions: Predicted probabilities or logits, shape (N, C)
        targets: Ground truth multi-hot labels, shape (N, C)
        threshold: Classification threshold
    
    Returns:
        Average per-sample accuracy
    """
    if predictions.requires_grad:
        predictions = predictions.detach()
    
    pred_binary = (torch.sigmoid(predictions) >= threshold).float()
    
    # Intersection and union per sample
    intersection = (pred_binary * targets).sum(dim=1)
    union = ((pred_binary + targets) > 0).float().sum(dim=1)
    
    # Avoid division by zero (samples with no labels)
    accuracies = intersection / union.clamp(min=1e-8)
    
    return accuracies.mean().item()


def per_class_f1(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    class_names: Optional[List[str]] = None,
    threshold: float = 0.5,
    epsilon: float = 1e-8
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """
    Compute F1 score for each class independently.
    
    Args:
        predictions: Predicted probabilities or logits, shape (N, C)
        targets: Ground truth multi-hot labels, shape (N, C)
        class_names: Names for each class (optional)
        threshold: Classification threshold
        epsilon: Small value to avoid division by zero
    
    Returns:
        Tuple of (f1_dict, precision_dict, recall_dict)
    """
    if predictions.requires_grad:
        predictions = predictions.detach()
    
    pred_binary = (torch.sigmoid(predictions) >= threshold).float()
    num_classes = predictions.size(1)
    
    if class_names is None:
        class_names = [f"class_{i}" for i in range(num_classes)]
    
    f1_dict = {}
    precision_dict = {}
    recall_dict = {}
    
    for i in range(num_classes):
        pred_i = pred_binary[:, i]
        target_i = targets[:, i]
        
        tp = (pred_i * target_i).sum()
        fp = (pred_i * (1 - target_i)).sum()
        fn = ((1 - pred_i) * target_i).sum()
        
        precision = tp / (tp + fp + epsilon)
        recall = tp / (tp + fn + epsilon)
        f1 = 2 * precision * recall / (precision + recall + epsilon)
        
        name = class_names[i] if i < len(class_names) else f"class_{i}"
        f1_dict[name] = f1.item()
        precision_dict[name] = precision.item()
        recall_dict[name] = recall.item()
    
    return f1_dict, precision_dict, recall_dict


def micro_f1(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    threshold: float = 0.5,
    epsilon: float = 1e-8
) -> float:
    """
    Compute Micro-averaged F1 score.
    
    Aggregates TP, FP, FN across all classes before computing F1.
    This gives more weight to frequent classes.
    
    Args:
        predictions: Predicted probabilities or logits, shape (N, C)
        targets: Ground truth multi-hot labels, shape (N, C)
        threshold: Classification threshold
    
    Returns:
        Micro F1 score
    """
    if predictions.requires_grad:
        predictions = predictions.detach()
    
    pred_binary = (torch.sigmoid(predictions) >= threshold).float()
    
    tp = (pred_binary * targets).sum()
    fp = (pred_binary * (1 - targets)).sum()
    fn = ((1 - pred_binary) * targets).sum()
    
    precision = tp / (tp + fp + epsilon)
    recall = tp / (tp + fn + epsilon)
    f1 = 2 * precision * recall / (precision + recall + epsilon)
    
    return f1.item()


def macro_f1(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    threshold: float = 0.5
) -> float:
    """
    Compute Macro-averaged F1 score.
    
    Computes F1 per class, then averages.
    This gives equal weight to all classes.
    
    Args:
        predictions: Predicted probabilities or logits, shape (N, C)
        targets: Ground truth multi-hot labels, shape (N, C)
        threshold: Classification threshold
    
    Returns:
        Macro F1 score
    """
    f1_dict, _, _ = per_class_f1(predictions, targets, threshold=threshold)
    return np.mean(list(f1_dict.values()))


def compute_all_metrics(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    class_names: Optional[List[str]] = None,
    threshold: float = 0.5
) -> MultiLabelMetrics:
    """
    Compute all multi-label metrics.
    
    Args:
        predictions: Predicted logits, shape (N, C)
        targets: Ground truth multi-hot labels, shape (N, C)
        class_names: Names for each class
        threshold: Classification threshold
    
    Returns:
        MultiLabelMetrics object with all metrics
    """
    if predictions.requires_grad:
        predictions = predictions.detach()
    
    # Per-class metrics
    f1_dict, prec_dict, recall_dict = per_class_f1(
        predictions, targets, class_names, threshold
    )
    
    # Aggregated metrics
    h_loss = hamming_loss(predictions, targets, threshold)
    s_acc = subset_accuracy(predictions, targets, threshold)
    mi_f1 = micro_f1(predictions, targets, threshold)
    ma_f1 = np.mean(list(f1_dict.values()))
    
    # Label statistics
    labels_per_sample = targets.sum(dim=1)
    avg_labels = labels_per_sample.mean().item()
    multilabel_count = (labels_per_sample > 1).sum().item()
    
    return MultiLabelMetrics(
        hamming_loss=h_loss,
        subset_accuracy=s_acc,
        micro_f1=mi_f1,
        macro_f1=ma_f1,
        per_class_f1=f1_dict,
        per_class_precision=prec_dict,
        per_class_recall=recall_dict,
        avg_labels_per_sample=avg_labels,
        samples_with_multilabel=multilabel_count,
        total_samples=len(predictions),
    )


class MultiLabelMetricTracker:
    """
    Track multi-label metrics across batches during training/evaluation.
    
    Usage:
        tracker = MultiLabelMetricTracker(class_names)
        for batch in dataloader:
            logits = model(batch)
            tracker.update(logits, targets)
        metrics = tracker.compute()
    """
    
    def __init__(self, class_names: Optional[List[str]] = None, threshold: float = 0.5):
        self.class_names = class_names
        self.threshold = threshold
        self.reset()
    
    def reset(self) -> None:
        """Reset accumulated predictions and targets."""
        self.all_predictions: List[torch.Tensor] = []
        self.all_targets: List[torch.Tensor] = []
    
    def update(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor
    ) -> None:
        """Add batch of predictions and targets."""
        self.all_predictions.append(predictions.detach().cpu())
        self.all_targets.append(targets.detach().cpu())
    
    def compute(self) -> MultiLabelMetrics:
        """Compute metrics from all accumulated data."""
        predictions = torch.cat(self.all_predictions, dim=0)
        targets = torch.cat(self.all_targets, dim=0)
        
        return compute_all_metrics(
            predictions, targets,
            class_names=self.class_names,
            threshold=self.threshold
        )
    
    def compute_and_reset(self) -> MultiLabelMetrics:
        """Compute metrics and reset for next epoch."""
        metrics = self.compute()
        self.reset()
        return metrics


def find_optimal_thresholds(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    thresholds: Optional[List[float]] = None
) -> Tuple[float, Dict[str, float]]:
    """
    Find optimal classification threshold(s) using validation data.
    
    Args:
        predictions: Predicted logits, shape (N, C)
        targets: Ground truth labels, shape (N, C)
        thresholds: List of thresholds to try
    
    Returns:
        Tuple of (best_global_threshold, per_class_thresholds)
    """
    if thresholds is None:
        thresholds = np.arange(0.1, 0.9, 0.05).tolist()
    
    # Find best global threshold
    best_f1 = 0.0
    best_threshold = 0.5
    
    for t in thresholds:
        f1 = micro_f1(predictions, targets, threshold=t)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
    
    # Find per-class thresholds
    probs = torch.sigmoid(predictions)
    num_classes = predictions.size(1)
    per_class_thresholds = {}
    
    for i in range(num_classes):
        best_class_f1 = 0.0
        best_class_t = 0.5
        
        for t in thresholds:
            pred_i = (probs[:, i] >= t).float()
            target_i = targets[:, i]
            
            tp = (pred_i * target_i).sum()
            fp = (pred_i * (1 - target_i)).sum()
            fn = ((1 - pred_i) * target_i).sum()
            
            precision = tp / (tp + fp + 1e-8)
            recall = tp / (tp + fn + 1e-8)
            f1 = 2 * precision * recall / (precision + recall + 1e-8)
            
            if f1 > best_class_f1:
                best_class_f1 = f1
                best_class_t = t
        
        per_class_thresholds[f"class_{i}"] = best_class_t
    
    return best_threshold, per_class_thresholds
