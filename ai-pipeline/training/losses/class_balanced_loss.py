"""
Class-Balanced Loss Based on Effective Number of Samples

This implements the loss function from the CVPR 2019 paper:
"Class-Balanced Loss Based on Effective Number of Samples" by Cui et al.

Paper: https://arxiv.org/abs/1901.05555

Key Insight:
-----------
As the number of samples increases, the additional benefit of a newly added
sample diminishes. The paper proposes using the "effective number of samples"
to re-weight the loss, which is computed as:

    E_n = (1 - β^n) / (1 - β)

Where:
- n = number of samples for a class
- β = hyperparameter in (0, 1), typically 0.9, 0.99, 0.999, or 0.9999

The effective number captures diminishing returns:
- When β→0: E_n ≈ 1 (all samples treated equally)
- When β→1: E_n ≈ n (linear scaling with sample count)
- β=0.9999 is recommended for extreme imbalance (>100:1 ratio)

Why this works better than inverse frequency:
--------------------------------------------
- Inverse frequency: weight ∝ 1/n, which can be extreme (e.g., 630x for your dataset)
- Effective number: smoother weighting that accounts for data overlap/redundancy
- The paper shows this consistently outperforms other weighting schemes

Usage:
------
    from training.losses.class_balanced_loss import ClassBalancedLoss
    
    # Compute class counts from your dataset
    class_counts = [1000, 500, 50, 10]  # Example counts
    
    criterion = ClassBalancedLoss(
        class_counts=class_counts,
        num_classes=4,
        beta=0.9999,  # Use 0.9999 for extreme imbalance
        loss_type='focal',  # 'softmax' or 'focal'
        gamma=1.0  # Only used if loss_type='focal'
    )
    
    loss = criterion(logits, targets)
"""

from __future__ import annotations

from typing import List, Optional, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def compute_effective_number(num_samples: int, beta: float) -> float:
    """Compute effective number of samples.
    
    E_n = (1 - β^n) / (1 - β)
    
    Args:
        num_samples: Number of samples for a class
        beta: Hyperparameter in (0, 1)
        
    Returns:
        Effective number of samples
    """
    if beta == 1.0:
        return float(num_samples)
    return (1.0 - beta ** num_samples) / (1.0 - beta)


def compute_class_balanced_weights(
    class_counts: Union[List[int], np.ndarray, torch.Tensor],
    beta: float = 0.9999,
    normalize: bool = True,
) -> torch.Tensor:
    """Compute class-balanced weights based on effective number of samples.
    
    Args:
        class_counts: Number of samples per class
        beta: Hyperparameter controlling the effective number.
              Higher beta = more weight to rare classes.
              Recommended: 0.9999 for extreme imbalance (>100:1)
                          0.999 for moderate imbalance (10:1 - 100:1)
                          0.99 for mild imbalance (<10:1)
        normalize: If True, normalize weights to sum to num_classes
        
    Returns:
        Tensor of per-class weights
    """
    if isinstance(class_counts, torch.Tensor):
        class_counts = class_counts.cpu().numpy()
    elif isinstance(class_counts, list):
        class_counts = np.array(class_counts)
    
    num_classes = len(class_counts)
    
    # Compute effective number for each class
    effective_num = np.array([
        compute_effective_number(n, beta) if n > 0 else 1e-6
        for n in class_counts
    ])
    
    # Weights are inverse of effective number
    weights = 1.0 / effective_num
    
    # Normalize so weights sum to num_classes (mean weight = 1)
    if normalize:
        weights = weights / weights.sum() * num_classes
    
    return torch.tensor(weights, dtype=torch.float32)


class ClassBalancedLoss(nn.Module):
    """
    Class-Balanced Loss using effective number of samples.
    
    This loss combines class-balanced weighting with either softmax cross-entropy
    or focal loss. The weighting is based on the effective number of samples,
    which provides smoother rebalancing than simple inverse frequency.
    
    Args:
        class_counts: Number of samples per class (list or tensor)
        num_classes: Total number of classes
        beta: Effective number hyperparameter (0.9999 recommended for extreme imbalance)
        loss_type: 'softmax' for cross-entropy, 'focal' for focal loss
        gamma: Focal loss focusing parameter (only used if loss_type='focal')
        label_smoothing: Label smoothing factor (0.0 to 0.1 typical)
        reduction: 'mean', 'sum', or 'none'
    """
    
    def __init__(
        self,
        class_counts: Union[List[int], np.ndarray, torch.Tensor],
        num_classes: int,
        beta: float = 0.9999,
        loss_type: str = "focal",
        gamma: float = 1.0,
        label_smoothing: float = 0.0,
        reduction: str = "mean",
    ):
        super().__init__()
        
        self.num_classes = num_classes
        self.beta = beta
        self.loss_type = loss_type
        self.gamma = gamma
        self.label_smoothing = label_smoothing
        self.reduction = reduction
        
        # Compute and register class-balanced weights
        weights = compute_class_balanced_weights(class_counts, beta, normalize=True)
        self.register_buffer("weights", weights)
        
        # Print weight statistics
        print(f"\n[CLASS-BALANCED LOSS] Initialized with beta={beta}")
        print(f"   Loss type: {loss_type}" + (f" (gamma={gamma})" if loss_type == "focal" else ""))
        print(f"   Weight range: [{weights.min():.4f}, {weights.max():.4f}]")
        print(f"   Weight ratio (max/min): {weights.max() / weights.min():.2f}x")
        
        # Show top 5 highest weighted classes
        top_k = min(5, num_classes)
        top_indices = torch.topk(weights, top_k).indices
        print(f"   Top {top_k} weighted classes: {top_indices.tolist()}")
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute class-balanced loss.
        
        Args:
            inputs: Logits of shape (batch, num_classes)
            targets: Ground truth labels of shape (batch,) or one-hot (batch, num_classes)
            
        Returns:
            Class-balanced loss value
        """
        # Handle one-hot encoded targets (from mixup)
        if targets.dim() == 2:
            return self._forward_soft_targets(inputs, targets)
        
        # Ensure weights are on the right device
        weights = self.weights.to(inputs.device)
        
        # Get per-sample weights based on target class
        sample_weights = weights[targets]  # Shape: (batch,)
        
        if self.loss_type == "softmax":
            # Standard cross-entropy with class-balanced weights
            if self.label_smoothing > 0:
                loss = F.cross_entropy(
                    inputs, targets,
                    reduction='none',
                    label_smoothing=self.label_smoothing
                )
            else:
                loss = F.cross_entropy(inputs, targets, reduction='none')
            
            # Apply class-balanced weights
            loss = loss * sample_weights
            
        elif self.loss_type == "focal":
            # Focal loss with class-balanced weights
            log_probs = F.log_softmax(inputs, dim=-1)
            probs = torch.exp(log_probs)
            
            # Get probability of correct class
            pt = probs.gather(1, targets.unsqueeze(1)).squeeze(1)
            
            # Focal weight: (1 - p_t)^gamma
            focal_weight = (1 - pt) ** self.gamma
            
            # Cross entropy: -log(p_t)
            ce_loss = F.cross_entropy(inputs, targets, reduction='none')
            
            # Combine focal weight and class-balanced weight
            loss = focal_weight * ce_loss * sample_weights
            
        else:
            raise ValueError(f"Unknown loss_type: {self.loss_type}")
        
        # Apply reduction
        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        return loss
    
    def _forward_soft_targets(
        self, inputs: torch.Tensor, targets: torch.Tensor
    ) -> torch.Tensor:
        """Handle soft/mixed targets (from mixup/cutmix).
        
        Args:
            inputs: Logits of shape (batch, num_classes)
            targets: Soft labels of shape (batch, num_classes)
        """
        weights = self.weights.to(inputs.device)
        
        log_probs = F.log_softmax(inputs, dim=-1)
        probs = torch.exp(log_probs)
        
        if self.loss_type == "focal":
            # Soft focal loss: weight by (1 - p)^gamma for each class
            focal_weight = (1 - probs) ** self.gamma
            ce_loss = -targets * log_probs
            loss = focal_weight * ce_loss
        else:
            # Soft cross-entropy
            loss = -targets * log_probs
        
        # Apply class-balanced weights per class
        loss = loss * weights.unsqueeze(0)  # Broadcast: (batch, num_classes) * (1, num_classes)
        
        # Sum over classes, then apply reduction
        loss = loss.sum(dim=-1)
        
        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        return loss


class ClassBalancedFocalLoss(ClassBalancedLoss):
    """Convenience class for Class-Balanced Focal Loss.
    
    Combines the benefits of:
    1. Class-balanced weighting (effective number of samples)
    2. Focal loss (focus on hard examples)
    
    This is often the best choice for extreme class imbalance.
    
    Args:
        class_counts: Number of samples per class
        num_classes: Total number of classes  
        beta: Effective number hyperparameter (default: 0.9999)
        gamma: Focal loss gamma (default: 1.0, use lower than standard focal)
        label_smoothing: Label smoothing factor
    """
    
    def __init__(
        self,
        class_counts: Union[List[int], np.ndarray, torch.Tensor],
        num_classes: int,
        beta: float = 0.9999,
        gamma: float = 1.0,
        label_smoothing: float = 0.0,
        reduction: str = "mean",
    ):
        super().__init__(
            class_counts=class_counts,
            num_classes=num_classes,
            beta=beta,
            loss_type="focal",
            gamma=gamma,
            label_smoothing=label_smoothing,
            reduction=reduction,
        )


class ClassBalancedCrossEntropy(ClassBalancedLoss):
    """Convenience class for Class-Balanced Cross-Entropy.
    
    Uses effective number weighting with standard cross-entropy.
    Good baseline when focal loss is too aggressive.
    
    Args:
        class_counts: Number of samples per class
        num_classes: Total number of classes
        beta: Effective number hyperparameter (default: 0.9999)
        label_smoothing: Label smoothing factor
    """
    
    def __init__(
        self,
        class_counts: Union[List[int], np.ndarray, torch.Tensor],
        num_classes: int,
        beta: float = 0.9999,
        label_smoothing: float = 0.0,
        reduction: str = "mean",
    ):
        super().__init__(
            class_counts=class_counts,
            num_classes=num_classes,
            beta=beta,
            loss_type="softmax",
            gamma=0.0,
            label_smoothing=label_smoothing,
            reduction=reduction,
        )


def get_class_balanced_loss(
    class_counts: Union[List[int], np.ndarray, torch.Tensor],
    num_classes: int,
    loss_type: str = "focal",
    beta: float = 0.9999,
    gamma: float = 1.0,
    label_smoothing: float = 0.0,
) -> ClassBalancedLoss:
    """Factory function to create a class-balanced loss.
    
    Args:
        class_counts: Number of samples per class
        num_classes: Total number of classes
        loss_type: 'focal' or 'softmax'
        beta: Effective number hyperparameter
        gamma: Focal loss gamma (ignored if loss_type='softmax')
        label_smoothing: Label smoothing factor
        
    Returns:
        Configured ClassBalancedLoss instance
    """
    return ClassBalancedLoss(
        class_counts=class_counts,
        num_classes=num_classes,
        beta=beta,
        loss_type=loss_type,
        gamma=gamma,
        label_smoothing=label_smoothing,
    )
