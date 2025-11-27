"""
Focal Loss for Imbalanced Classification

Focal Loss down-weights easy examples and focuses training on hard negatives.
This is critical for drum classification where class distribution is often
heavily imbalanced (many more kicks than ghost notes, for example).

Reference: "Focal Loss for Dense Object Detection" (Lin et al., 2017)

The focal loss is defined as:
    FL(p_t) = -α_t * (1 - p_t)^γ * log(p_t)

Where:
- p_t = p if y=1, else 1-p (probability of correct class)
- γ (gamma) = focusing parameter (0=standard CE, 2=strong focus on hard examples)
- α = class weight (can be used for class imbalance)

Why this helps drum classification:
- Down-weights easy examples (obvious kicks, clear snares)
- Focuses on hard examples (ghost notes, subtle cymbals, ambiguous hits)
- Better gradient signal from minority classes
- Improves calibration on tail classes

Usage:
    from training.losses.focal_loss import FocalLoss
    
    criterion = FocalLoss(gamma=2.0, alpha=class_weights)
    loss = criterion(logits, targets)
"""

from __future__ import annotations

from typing import Optional, Union

import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """
    Focal Loss for multi-class classification.
    
    Reduces the loss contribution from easy examples and increases
    focus on hard, misclassified examples.
    
    Args:
        gamma: Focusing parameter (0=CE, 2=strong focus). Higher gamma = more focus on hard examples.
        alpha: Class weights. Can be:
            - None: No class weighting
            - float: Applied uniformly
            - Tensor: Per-class weights of shape (num_classes,)
        reduction: 'none', 'mean', or 'sum'
        label_smoothing: Optional label smoothing (0.0 to 1.0)
    """
    
    def __init__(
        self,
        gamma: float = 2.0,
        alpha: Optional[Union[float, torch.Tensor]] = None,
        reduction: str = "mean",
        label_smoothing: float = 0.0
    ):
        super().__init__()
        self.gamma = gamma
        self.reduction = reduction
        self.label_smoothing = label_smoothing
        
        # Handle alpha (class weights)
        if alpha is not None:
            if isinstance(alpha, (list, tuple)):
                alpha = torch.tensor(alpha, dtype=torch.float32)
            elif isinstance(alpha, float):
                alpha = torch.tensor([alpha], dtype=torch.float32)
        self.register_buffer("alpha", alpha)
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute focal loss.
        
        Args:
            inputs: Logits of shape (batch, num_classes)
            targets: Ground truth labels of shape (batch,)
            
        Returns:
            Focal loss value
        """
        num_classes = inputs.size(-1)
        
        # Apply label smoothing if specified
        if self.label_smoothing > 0:
            with torch.no_grad():
                targets_smooth = torch.zeros_like(inputs)
                targets_smooth.fill_(self.label_smoothing / (num_classes - 1))
                targets_smooth.scatter_(1, targets.unsqueeze(1), 1.0 - self.label_smoothing)
            
            # Soft focal loss for smoothed labels
            log_probs = F.log_softmax(inputs, dim=-1)
            probs = torch.exp(log_probs)
            
            # Focal weight: (1 - p)^gamma for each class
            focal_weight = (1 - probs) ** self.gamma
            
            # Cross entropy with smoothed labels
            ce_loss = -targets_smooth * log_probs
            focal_loss = focal_weight * ce_loss
            
            # Apply class weights if provided
            if self.alpha is not None:
                alpha = self.alpha.to(inputs.device)
                if alpha.dim() == 0 or alpha.size(0) == 1:
                    focal_loss = alpha * focal_loss
                else:
                    focal_loss = focal_loss * alpha.unsqueeze(0)
            
            loss = focal_loss.sum(dim=-1)
        else:
            # Standard focal loss for hard labels
            log_probs = F.log_softmax(inputs, dim=-1)
            probs = torch.exp(log_probs)
            
            # Get probability of correct class
            targets_one_hot = F.one_hot(targets, num_classes=num_classes).float()
            pt = (probs * targets_one_hot).sum(dim=-1)  # p_t
            
            # Focal weight: (1 - p_t)^gamma
            focal_weight = (1 - pt) ** self.gamma
            
            # Cross entropy: -log(p_t)
            ce_loss = F.cross_entropy(inputs, targets, reduction='none')
            
            # Focal loss
            loss = focal_weight * ce_loss
            
            # Apply class weights
            if self.alpha is not None:
                alpha = self.alpha.to(inputs.device)
                if alpha.dim() == 0 or alpha.size(0) == 1:
                    loss = alpha * loss
                else:
                    alpha_t = alpha[targets]
                    loss = alpha_t * loss
        
        # Apply reduction
        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        else:
            return loss


class FocalLossWithMixup(nn.Module):
    """
    Focal Loss compatible with Mixup/CutMix augmentation.
    
    When using mixup, targets are (labels_a, labels_b, lam) instead of hard labels.
    This version handles both cases seamlessly.
    
    Usage:
        criterion = FocalLossWithMixup(gamma=2.0)
        
        # Standard training
        loss = criterion(logits, targets)
        
        # With mixup
        loss = criterion(logits, targets_a, targets_b, lam)
    """
    
    def __init__(
        self,
        gamma: float = 2.0,
        alpha: Optional[Union[float, torch.Tensor]] = None,
        reduction: str = "mean",
        label_smoothing: float = 0.0
    ):
        super().__init__()
        self.focal_loss = FocalLoss(
            gamma=gamma,
            alpha=alpha,
            reduction=reduction,
            label_smoothing=label_smoothing
        )
        self.gamma = gamma
        self.reduction = reduction
    
    def forward(
        self,
        inputs: torch.Tensor,
        targets_a: torch.Tensor,
        targets_b: Optional[torch.Tensor] = None,
        lam: float = 1.0
    ) -> torch.Tensor:
        """
        Compute focal loss, with optional mixup support.
        
        Args:
            inputs: Logits of shape (batch, num_classes)
            targets_a: Primary labels (or only labels if no mixup)
            targets_b: Secondary labels for mixup (optional)
            lam: Mixup interpolation coefficient
            
        Returns:
            Loss value
        """
        if targets_b is None:
            # Standard focal loss
            return self.focal_loss(inputs, targets_a)
        else:
            # Mixup focal loss
            loss_a = self.focal_loss(inputs, targets_a)
            loss_b = self.focal_loss(inputs, targets_b)
            return lam * loss_a + (1 - lam) * loss_b


class AsymmetricFocalLoss(nn.Module):
    """
    Asymmetric Focal Loss - different gamma for positive vs negative examples.
    
    Useful when you want to focus more on minority class errors without
    completely ignoring majority class mistakes.
    
    Reference: "Asymmetric Loss For Multi-Label Classification" (Ridnik et al., 2021)
    
    Args:
        gamma_pos: Focusing parameter for positive (correct class) examples
        gamma_neg: Focusing parameter for negative (wrong class) examples
    """
    
    def __init__(
        self,
        gamma_pos: float = 1.0,
        gamma_neg: float = 4.0,
        reduction: str = "mean"
    ):
        super().__init__()
        self.gamma_pos = gamma_pos
        self.gamma_neg = gamma_neg
        self.reduction = reduction
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        num_classes = inputs.size(-1)
        probs = torch.softmax(inputs, dim=-1)
        
        targets_one_hot = F.one_hot(targets, num_classes=num_classes).float()
        
        # Positive loss (correct class)
        pos_probs = (probs * targets_one_hot).sum(dim=-1)
        pos_loss = -((1 - pos_probs) ** self.gamma_pos) * torch.log(pos_probs.clamp(min=1e-8))
        
        # Negative loss (wrong classes) - optional, adds robustness
        # For multi-class, we typically just use positive loss
        
        if self.reduction == "mean":
            return pos_loss.mean()
        elif self.reduction == "sum":
            return pos_loss.sum()
        return pos_loss


def get_focal_loss(
    gamma: float = 2.0,
    class_weights: Optional[torch.Tensor] = None,
    label_smoothing: float = 0.0,
    mixup_compatible: bool = True
) -> nn.Module:
    """
    Factory function to get appropriate focal loss.
    
    Args:
        gamma: Focusing parameter (recommended: 1.0-3.0)
        class_weights: Optional per-class weights for imbalance
        label_smoothing: Optional label smoothing
        mixup_compatible: Whether to return mixup-compatible version
        
    Returns:
        Configured focal loss instance
    """
    if mixup_compatible:
        return FocalLossWithMixup(
            gamma=gamma,
            alpha=class_weights,
            label_smoothing=label_smoothing
        )
    else:
        return FocalLoss(
            gamma=gamma,
            alpha=class_weights,
            label_smoothing=label_smoothing
        )
