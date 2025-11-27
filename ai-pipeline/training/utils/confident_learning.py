"""
Confident Learning / Label Noise Detection for Drum Classification

This module provides tools for detecting and handling label noise in
the training dataset. Label noise (mislabeled samples) can significantly
hurt model performance, especially for rare classes.

Based on: "Confident Learning: Estimating Uncertainty in Dataset Labels" (2019)
          https://arxiv.org/abs/1911.00068

Also integrates with the cleanlab library when available for advanced features.

Key capabilities:
1. Identify likely mislabeled samples
2. Estimate the noise matrix (confusion between classes)
3. Clean the dataset by removing or relabeling noisy samples
4. Compute confident learning scores for sample weighting

Expected improvement: +1-3% if dataset has label noise (common in crowd-sourced data)

Usage:
    from training.utils.confident_learning import (
        find_label_issues,
        estimate_noise_matrix,
        clean_labels,
        LabelNoiseDataset,
    )
    
    # Find potentially mislabeled samples
    issues = find_label_issues(probs, labels)
    print(f"Found {len(issues)} potential label issues")
    
    # Optionally use cleanlab if installed
    cleaned_labels = clean_labels(probs, labels, method='prune_by_noise_rate')
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from torch.utils.data import Dataset, Subset

logger = logging.getLogger(__name__)

# Try to import cleanlab for advanced features
try:
    import cleanlab
    from cleanlab import Datalab
    from cleanlab.filter import find_label_issues as cl_find_label_issues
    HAS_CLEANLAB = True
except ImportError:
    cleanlab = None
    Datalab = None
    cl_find_label_issues = None
    HAS_CLEANLAB = False


@dataclass
class LabelIssue:
    """Information about a potential label issue."""
    index: int
    given_label: int
    suggested_label: int
    confidence: float
    given_label_prob: float
    suggested_label_prob: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "given_label": self.given_label,
            "suggested_label": self.suggested_label,
            "confidence": self.confidence,
            "given_label_prob": self.given_label_prob,
            "suggested_label_prob": self.suggested_label_prob,
        }


def compute_confident_joint(
    pred_probs: np.ndarray,
    labels: np.ndarray,
    num_classes: Optional[int] = None,
    calibrate: bool = True,
) -> np.ndarray:
    """
    Compute the confident joint matrix C_ŷ,y.
    
    The confident joint estimates the joint distribution of noisy
    and true labels. Entry C[i][j] represents the count of samples
    labeled as j that likely belong to class i.
    
    Args:
        pred_probs: Model predicted probabilities [N, num_classes]
        labels: Given (possibly noisy) labels [N]
        num_classes: Number of classes (inferred if not provided)
        calibrate: Whether to calibrate the confident joint
    
    Returns:
        Confident joint matrix [num_classes, num_classes]
    """
    if num_classes is None:
        num_classes = pred_probs.shape[1]
    
    n_samples = len(labels)
    
    # Compute per-class thresholds (average prob for samples in each class)
    thresholds = np.zeros(num_classes)
    for c in range(num_classes):
        mask = labels == c
        if mask.sum() > 0:
            thresholds[c] = pred_probs[mask, c].mean()
        else:
            thresholds[c] = 0.5
    
    # Build confident joint
    confident_joint = np.zeros((num_classes, num_classes), dtype=np.int64)
    
    for i in range(n_samples):
        given_label = labels[i]
        pred_label = np.argmax(pred_probs[i])
        
        # Check if prediction is confident (above threshold for that class)
        if pred_probs[i, pred_label] >= thresholds[pred_label]:
            confident_joint[pred_label, given_label] += 1
    
    # Calibrate: normalize so rows sum to class counts
    if calibrate:
        for c in range(num_classes):
            row_sum = confident_joint[c].sum()
            if row_sum > 0:
                class_count = (labels == c).sum()
                if class_count > 0:
                    confident_joint[c] = confident_joint[c] * class_count / row_sum
    
    return confident_joint


def estimate_noise_matrix(
    pred_probs: np.ndarray,
    labels: np.ndarray,
    num_classes: Optional[int] = None,
) -> np.ndarray:
    """
    Estimate the noise transition matrix.
    
    The noise matrix P(ŷ|y*) represents the probability that a sample
    with true label y* is mislabeled as ŷ.
    
    Args:
        pred_probs: Model predicted probabilities [N, num_classes]
        labels: Given (possibly noisy) labels [N]
        num_classes: Number of classes
    
    Returns:
        Noise matrix [num_classes, num_classes]
    """
    if num_classes is None:
        num_classes = pred_probs.shape[1]
    
    confident_joint = compute_confident_joint(pred_probs, labels, num_classes)
    
    # Normalize to get probabilities
    noise_matrix = confident_joint.astype(np.float64)
    
    # Each column should sum to 1 (probability of mislabeling given true class)
    col_sums = noise_matrix.sum(axis=0, keepdims=True)
    col_sums = np.clip(col_sums, 1e-6, None)
    noise_matrix = noise_matrix / col_sums
    
    return noise_matrix


def find_label_issues(
    pred_probs: np.ndarray,
    labels: np.ndarray,
    num_classes: Optional[int] = None,
    n_jobs: int = 1,
    filter_by: str = "prune_by_noise_rate",
    return_indices_ranked_by: str = "self_confidence",
    min_examples_per_class: int = 1,
) -> List[LabelIssue]:
    """
    Find samples that are likely mislabeled.
    
    Uses confident learning to identify samples where the given label
    disagrees with the model's confident prediction.
    
    Args:
        pred_probs: Model predicted probabilities [N, num_classes]
        labels: Given (possibly noisy) labels [N]
        num_classes: Number of classes
        n_jobs: Number of parallel jobs (for cleanlab)
        filter_by: Method for filtering ('prune_by_noise_rate', 'prune_by_class', 'both')
        return_indices_ranked_by: How to rank issues ('self_confidence', 'normalized_margin')
        min_examples_per_class: Minimum examples per class before pruning
    
    Returns:
        List of LabelIssue objects, sorted by confidence (most likely wrong first)
    """
    if num_classes is None:
        num_classes = pred_probs.shape[1]
    
    labels = np.asarray(labels)
    pred_probs = np.asarray(pred_probs)
    
    # Use cleanlab if available for more sophisticated detection
    if HAS_CLEANLAB and cl_find_label_issues is not None:
        try:
            issue_indices = cl_find_label_issues(
                labels=labels,
                pred_probs=pred_probs,
                filter_by=filter_by,
                return_indices_ranked_by=return_indices_ranked_by,
                n_jobs=n_jobs,
                min_examples_per_class=min_examples_per_class,
            )
            
            # Convert to our LabelIssue format
            issues = []
            for idx in issue_indices:
                given_label = labels[idx]
                suggested_label = np.argmax(pred_probs[idx])
                
                if given_label != suggested_label:
                    issue = LabelIssue(
                        index=int(idx),
                        given_label=int(given_label),
                        suggested_label=int(suggested_label),
                        confidence=float(pred_probs[idx, suggested_label]),
                        given_label_prob=float(pred_probs[idx, given_label]),
                        suggested_label_prob=float(pred_probs[idx, suggested_label]),
                    )
                    issues.append(issue)
            
            return issues
            
        except Exception as e:
            logger.warning(f"cleanlab failed, falling back to simple detection: {e}")
    
    # Simple confident learning fallback
    issues = []
    
    # Compute thresholds
    thresholds = np.zeros(num_classes)
    for c in range(num_classes):
        mask = labels == c
        if mask.sum() >= min_examples_per_class:
            thresholds[c] = pred_probs[mask, c].mean()
        else:
            thresholds[c] = 0.5
    
    for i in range(len(labels)):
        given_label = labels[i]
        pred_label = np.argmax(pred_probs[i])
        
        # Check if there's a disagreement
        if pred_label != given_label:
            # Check if prediction is confident
            if pred_probs[i, pred_label] >= thresholds[pred_label]:
                issue = LabelIssue(
                    index=i,
                    given_label=int(given_label),
                    suggested_label=int(pred_label),
                    confidence=float(pred_probs[i, pred_label]),
                    given_label_prob=float(pred_probs[i, given_label]),
                    suggested_label_prob=float(pred_probs[i, pred_label]),
                )
                issues.append(issue)
    
    # Sort by confidence (most likely wrong first)
    issues.sort(key=lambda x: x.confidence, reverse=True)
    
    return issues


def compute_label_quality_scores(
    pred_probs: np.ndarray,
    labels: np.ndarray,
) -> np.ndarray:
    """
    Compute a quality score for each label.
    
    Higher scores indicate more trustworthy labels.
    Can be used for sample weighting during training.
    
    Args:
        pred_probs: Model predicted probabilities [N, num_classes]
        labels: Given labels [N]
    
    Returns:
        Quality scores [N], range [0, 1]
    """
    labels = np.asarray(labels)
    pred_probs = np.asarray(pred_probs)
    
    # Base quality: probability assigned to the given label
    n_samples = len(labels)
    quality_scores = np.zeros(n_samples)
    
    for i in range(n_samples):
        quality_scores[i] = pred_probs[i, labels[i]]
    
    # Normalize to [0, 1] while preserving relative ordering
    # Using percentile ranking
    from scipy import stats
    quality_scores = stats.rankdata(quality_scores) / len(quality_scores)
    
    return quality_scores


def clean_labels(
    pred_probs: np.ndarray,
    labels: np.ndarray,
    method: str = "prune_by_noise_rate",
    n_jobs: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Clean the dataset by identifying and optionally relabeling noisy samples.
    
    Args:
        pred_probs: Model predicted probabilities [N, num_classes]
        labels: Given labels [N]
        method: Cleaning method:
            - 'prune': Remove likely mislabeled samples
            - 'relabel': Replace labels with model predictions for likely issues
            - 'prune_by_noise_rate': Prune proportional to estimated noise rate
        n_jobs: Number of parallel jobs
    
    Returns:
        Tuple of (cleaned_labels, mask_of_kept_samples)
    """
    labels = np.asarray(labels)
    pred_probs = np.asarray(pred_probs)
    n_samples = len(labels)
    
    issues = find_label_issues(pred_probs, labels, n_jobs=n_jobs)
    issue_indices = set(issue.index for issue in issues)
    
    if method == "prune" or method == "prune_by_noise_rate":
        # Remove samples identified as issues
        keep_mask = np.array([i not in issue_indices for i in range(n_samples)])
        cleaned_labels = labels.copy()
        return cleaned_labels, keep_mask
    
    elif method == "relabel":
        # Replace labels with model predictions for issues
        cleaned_labels = labels.copy()
        for issue in issues:
            cleaned_labels[issue.index] = issue.suggested_label
        keep_mask = np.ones(n_samples, dtype=bool)
        return cleaned_labels, keep_mask
    
    else:
        raise ValueError(f"Unknown method: {method}")


class LabelNoiseDataset(Dataset):
    """
    Dataset wrapper that handles label noise.
    
    Wraps an existing dataset and applies label noise handling:
    - Filters out likely mislabeled samples
    - Optionally relabels suspicious samples
    - Provides sample weights based on label quality
    
    Args:
        dataset: Base dataset
        pred_probs: Model predictions on the dataset
        labels: Current labels (can be different from dataset labels)
        strategy: How to handle noise ('filter', 'relabel', 'weight')
        threshold: Confidence threshold for filtering/relabeling
    """
    
    def __init__(
        self,
        dataset: Dataset,
        pred_probs: np.ndarray,
        labels: Optional[np.ndarray] = None,
        strategy: str = "filter",
        threshold: float = 0.5,
    ):
        self.base_dataset = dataset
        self.pred_probs = np.asarray(pred_probs)
        
        # Get labels if not provided
        if labels is not None:
            self.original_labels = np.asarray(labels)
        else:
            self.original_labels = np.array([
                dataset[i][1] for i in range(len(dataset))
            ])
        
        self.strategy = strategy
        self.threshold = threshold
        
        # Process labels based on strategy
        self._process_labels()
    
    def _process_labels(self):
        """Apply the chosen noise handling strategy."""
        issues = find_label_issues(self.pred_probs, self.original_labels)
        issue_set = {issue.index for issue in issues if issue.confidence >= self.threshold}
        
        n_samples = len(self.original_labels)
        
        if self.strategy == "filter":
            # Keep only clean samples
            self.indices = [i for i in range(n_samples) if i not in issue_set]
            self.labels = self.original_labels[self.indices]
            self.weights = np.ones(len(self.indices))
            
        elif self.strategy == "relabel":
            # Relabel suspicious samples
            self.indices = list(range(n_samples))
            self.labels = self.original_labels.copy()
            for issue in issues:
                if issue.confidence >= self.threshold:
                    self.labels[issue.index] = issue.suggested_label
            self.weights = np.ones(n_samples)
            
        elif self.strategy == "weight":
            # Keep all samples but weight by quality
            self.indices = list(range(n_samples))
            self.labels = self.original_labels
            self.weights = compute_label_quality_scores(self.pred_probs, self.original_labels)
            
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
        
        logger.info(
            f"LabelNoiseDataset: {len(issues)} potential issues found, "
            f"{len(self.indices)} samples kept (strategy={self.strategy})"
        )
    
    def __len__(self) -> int:
        return len(self.indices)
    
    def __getitem__(self, idx: int):
        """Get item with potentially corrected label."""
        original_idx = self.indices[idx]
        item = self.base_dataset[original_idx]
        
        # Replace label with our (possibly corrected) label
        if isinstance(item, tuple):
            return (item[0], self.labels[idx], self.weights[idx])
        else:
            return item
    
    def get_weights(self) -> np.ndarray:
        """Get sample weights for use with WeightedRandomSampler."""
        return self.weights


def save_label_issues_report(
    issues: List[LabelIssue],
    output_path: Union[str, Path],
    class_names: Optional[List[str]] = None,
    max_issues: int = 1000,
):
    """
    Save a detailed report of label issues to JSON.
    
    Args:
        issues: List of LabelIssue objects
        output_path: Path to save the report
        class_names: Optional list of class names for readability
        max_issues: Maximum number of issues to save
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Summarize by class
    class_summary = Counter()
    for issue in issues:
        key = (issue.given_label, issue.suggested_label)
        class_summary[key] += 1
    
    report = {
        "total_issues": len(issues),
        "issues": [issue.to_dict() for issue in issues[:max_issues]],
        "class_confusion_summary": [
            {
                "given": given,
                "given_name": class_names[given] if class_names else None,
                "suggested": suggested,
                "suggested_name": class_names[suggested] if class_names else None,
                "count": count,
            }
            for (given, suggested), count in class_summary.most_common(50)
        ],
    }
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Saved label issues report to {output_path}")


def run_label_audit(
    model: torch.nn.Module,
    dataset: Dataset,
    device: torch.device,
    batch_size: int = 64,
    num_workers: int = 4,
    output_dir: Optional[Path] = None,
    class_names: Optional[List[str]] = None,
) -> Tuple[List[LabelIssue], np.ndarray]:
    """
    Run a full label audit on a dataset.
    
    Args:
        model: Trained model for generating predictions
        dataset: Dataset to audit
        device: Compute device
        batch_size: Batch size for inference
        num_workers: DataLoader workers
        output_dir: Directory to save reports (optional)
        class_names: List of class names
    
    Returns:
        Tuple of (issues, pred_probs)
    """
    from torch.utils.data import DataLoader
    
    model.eval()
    
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )
    
    all_probs = []
    all_labels = []
    
    with torch.no_grad():
        for batch in loader:
            inputs, labels = batch[0], batch[1]
            inputs = inputs.to(device)
            
            outputs = model(inputs)
            probs = torch.softmax(outputs, dim=1)
            
            all_probs.append(probs.cpu().numpy())
            all_labels.append(labels.numpy())
    
    pred_probs = np.concatenate(all_probs, axis=0)
    labels = np.concatenate(all_labels, axis=0)
    
    issues = find_label_issues(pred_probs, labels)
    
    logger.info(f"Found {len(issues)} potential label issues in {len(labels)} samples")
    
    if output_dir:
        output_dir = Path(output_dir)
        save_label_issues_report(
            issues,
            output_dir / "label_issues.json",
            class_names=class_names,
        )
        
        # Save noise matrix
        noise_matrix = estimate_noise_matrix(pred_probs, labels)
        np.save(output_dir / "noise_matrix.npy", noise_matrix)
        
        logger.info(f"Saved audit reports to {output_dir}")
    
    return issues, pred_probs
