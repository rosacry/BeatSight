"""
Multi-Label Loss Functions for Drum Classification

This module provides loss functions optimized for multi-label drum classification,
where multiple drum hits can occur simultaneously.

Key differences from single-label:
- Single-label uses CrossEntropyLoss (softmax over all classes)
- Multi-label uses BCEWithLogitsLoss (sigmoid per class, independent)

Classes:
- MultiLabelLoss: Standard BCE with class weighting
- FocalBCELoss: Focal loss variant for handling class imbalance
- AsymmetricLoss: Different penalties for false positives vs false negatives
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class MultiLabelLoss(nn.Module):
    """
    Multi-label classification loss using Binary Cross-Entropy.
    
    Supports:
    - Per-class positive weights (for imbalanced classes)
    - Label smoothing
    - Mixup-compatible soft labels
    
    Args:
        pos_weight: Per-class positive weights for handling imbalance.
                   Shape: (num_classes,). Higher weight = more penalty for missing positives.
        label_smoothing: Smooth labels towards 0.5 (reduces overconfidence)
        reduction: 'mean', 'sum', or 'none'
    """
    
    def __init__(
        self,
        pos_weight: Optional[torch.Tensor] = None,
        label_smoothing: float = 0.0,
        reduction: str = 'mean'
    ):
        super().__init__()
        self.register_buffer('pos_weight', pos_weight)
        self.label_smoothing = label_smoothing
        self.reduction = reduction
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute multi-label BCE loss.
        
        Args:
            logits: Raw predictions (before sigmoid), shape (B, C)
            targets: Multi-hot targets, shape (B, C), values in [0, 1]
        
        Returns:
            Loss tensor (scalar if reduction='mean' or 'sum')
        """
        # Apply label smoothing
        if self.label_smoothing > 0:
            targets = targets * (1 - self.label_smoothing) + 0.5 * self.label_smoothing
        
        # Compute BCE with logits
        loss = F.binary_cross_entropy_with_logits(
            logits, targets,
            pos_weight=self.pos_weight,
            reduction=self.reduction
        )
        
        return loss


class FocalBCELoss(nn.Module):
    """
    Focal Loss for Multi-Label Classification.
    
    Focal loss down-weights easy examples and focuses on hard ones.
    This is especially useful for drum classification where some classes
    (kick, snare) are much more common than others (china, splash).
    
    Loss = -alpha * (1-p)^gamma * log(p)  for positive class
         = -(1-alpha) * p^gamma * log(1-p)  for negative class
    
    where p = sigmoid(logit)
    
    Reference: "Focal Loss for Dense Object Detection" (Lin et al., 2017)
    
    Args:
        gamma: Focusing parameter. Higher = more focus on hard examples.
               gamma=0 is equivalent to standard BCE.
               Recommended: 2.0 for severe imbalance, 1.0 for moderate
        alpha: Per-class weight tensor, shape (num_classes,)
        label_smoothing: Label smoothing factor
        reduction: 'mean', 'sum', or 'none'
    """
    
    def __init__(
        self,
        gamma: float = 2.0,
        alpha: Optional[torch.Tensor] = None,
        label_smoothing: float = 0.0,
        reduction: str = 'mean'
    ):
        super().__init__()
        self.gamma = gamma
        self.register_buffer('alpha', alpha)
        self.label_smoothing = label_smoothing
        self.reduction = reduction
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute focal BCE loss.
        
        Args:
            logits: Raw predictions (before sigmoid), shape (B, C)
            targets: Multi-hot targets, shape (B, C), values in [0, 1]
        
        Returns:
            Loss tensor
        """
        # Apply label smoothing
        if self.label_smoothing > 0:
            targets = targets * (1 - self.label_smoothing) + 0.5 * self.label_smoothing
        
        # Compute probabilities
        p = torch.sigmoid(logits)
        
        # Compute focal weights
        # For positive samples: (1 - p)^gamma
        # For negative samples: p^gamma
        pt = p * targets + (1 - p) * (1 - targets)  # pt = p if y=1, (1-p) if y=0
        focal_weight = (1 - pt).pow(self.gamma)
        
        # Compute BCE
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
        
        # Apply focal weight
        loss = focal_weight * bce
        
        # Apply class weights
        if self.alpha is not None:
            loss = loss * self.alpha.unsqueeze(0)
        
        # Reduce
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class AsymmetricLoss(nn.Module):
    """
    Asymmetric Loss for Multi-Label Classification.
    
    This loss applies different focusing parameters for positive and negative
    samples, which is useful when false negatives are more costly than
    false positives (e.g., missing a drum hit is worse than a false alarm).
    
    Key insight: In drum transcription, missing a hit (FN) degrades user
    experience more than an extra hit (FP) which can be deleted in editor.
    
    Reference: "Asymmetric Loss For Multi-Label Classification" (Ridnik et al., 2021)
    
    Args:
        gamma_neg: Focusing parameter for negative samples (default: 4)
        gamma_pos: Focusing parameter for positive samples (default: 0)
        clip: Probability margin for hard thresholding negatives (default: 0.05)
        disable_torch_grad_focal_loss: Performance optimization
    """
    
    def __init__(
        self,
        gamma_neg: float = 4.0,
        gamma_pos: float = 0.0,
        clip: float = 0.05,
        reduction: str = 'mean'
    ):
        super().__init__()
        self.gamma_neg = gamma_neg
        self.gamma_pos = gamma_pos
        self.clip = clip
        self.reduction = reduction
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute asymmetric loss.
        
        Args:
            logits: Raw predictions (before sigmoid), shape (B, C)
            targets: Multi-hot targets, shape (B, C), values in [0, 1]
        
        Returns:
            Loss tensor
        """
        # Probabilities
        p = torch.sigmoid(logits)
        
        # Asymmetric clipping (probability shifting)
        # This makes the model more confident about negatives
        p_neg = (p - self.clip).clamp(min=0)
        
        # Separate positive and negative losses
        # Positive: -log(p) * (1-p)^gamma_pos
        # Negative: -log(1-p_neg) * p_neg^gamma_neg
        
        pos_loss = targets * torch.log(p.clamp(min=1e-8))
        neg_loss = (1 - targets) * torch.log((1 - p_neg).clamp(min=1e-8))
        
        # Apply asymmetric focusing
        if self.gamma_neg > 0:
            neg_loss = neg_loss * (p_neg ** self.gamma_neg)
        if self.gamma_pos > 0:
            pos_loss = pos_loss * ((1 - p) ** self.gamma_pos)
        
        loss = -(pos_loss + neg_loss)
        
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class MultiLabelLossWithMixup(nn.Module):
    """
    Multi-label loss that supports mixup/cutmix augmentation.
    
    When using mixup, labels are soft (e.g., [0.3, 0.7] instead of [0, 1]).
    This wrapper handles both hard and soft multi-label targets.
    
    Args:
        base_loss: Underlying loss function (MultiLabelLoss, FocalBCELoss, etc.)
    """
    
    def __init__(self, base_loss: nn.Module):
        super().__init__()
        self.base_loss = base_loss
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        lam: Optional[float] = None,
        targets_b: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Compute loss with optional mixup interpolation.
        
        Args:
            logits: Model predictions, shape (B, C)
            targets: Primary targets, shape (B, C)
            lam: Mixup interpolation factor (None if no mixup)
            targets_b: Secondary targets for mixup
        
        Returns:
            Loss tensor
        """
        if lam is not None and targets_b is not None:
            # Mixup: interpolate targets
            mixed_targets = lam * targets + (1 - lam) * targets_b
            return self.base_loss(logits, mixed_targets)
        else:
            return self.base_loss(logits, targets)


def get_multilabel_loss(
    loss_type: str = "bce",
    pos_weight: Optional[torch.Tensor] = None,
    gamma: float = 2.0,
    label_smoothing: float = 0.0,
    **kwargs
) -> nn.Module:
    """
    Factory function to create multi-label loss.
    
    Args:
        loss_type: "bce", "focal", or "asymmetric"
        pos_weight: Per-class positive weights
        gamma: Focusing parameter for focal loss
        label_smoothing: Label smoothing factor
    
    Returns:
        Loss module
    """
    if loss_type == "bce":
        return MultiLabelLoss(
            pos_weight=pos_weight,
            label_smoothing=label_smoothing,
            **kwargs
        )
    elif loss_type == "focal":
        return FocalBCELoss(
            gamma=gamma,
            alpha=pos_weight,
            label_smoothing=label_smoothing,
            **kwargs
        )
    elif loss_type == "asymmetric":
        return AsymmetricLoss(**kwargs)
    else:
        raise ValueError(f"Unknown loss type: {loss_type}. Choose from: bce, focal, asymmetric")
