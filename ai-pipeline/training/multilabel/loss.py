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

from typing import Dict, List, Optional, Union

import numpy as np
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


class RecallBoostFocalLoss(nn.Module):
    """
    Asymmetric Focal Loss optimized for boosting recall.
    
    This addresses low recall on classes like hihat_pedal, cross_stick, ride_bow by using:
    1. ASYMMETRIC gamma: Low gamma for positives (0-1), high gamma for negatives (2-5)
       - Low gamma on positives = STRONG gradients for missed detections (FN)
       - High gamma on negatives = suppress easy negative gradients (reduces FP penalty)
    2. Per-class positive weight boost based on class difficulty
    
    The key insight: Standard focal loss with high gamma suppresses ALL gradients,
    including the positive ones we need for recall. Asymmetric gamma fixes this.
    
    Args:
        per_class_gamma: Dict mapping class index to NEGATIVE gamma value
                        (positive gamma is always 0-1 to keep strong pos gradients)
        recall_boost_weight: Extra weight multiplier for positive samples
        base_gamma: Default gamma for negatives in classes not in per_class_gamma
        reduction: 'mean', 'sum', or 'none'
    """
    
    def __init__(
        self,
        per_class_gamma: Optional[dict] = None,
        recall_boost_weight: float = 1.5,
        base_gamma: float = 2.0,
        label_smoothing: float = 0.0,
        reduction: str = 'mean',
        num_classes: int = 12,
    ):
        super().__init__()
        self.per_class_gamma = per_class_gamma or {}
        self.recall_boost_weight = recall_boost_weight
        self.base_gamma = base_gamma
        self.label_smoothing = label_smoothing
        self.reduction = reduction
        self.num_classes = num_classes
        
        # Build gamma tensors - SEPARATE for positives and negatives
        # Positive gamma: Keep LOW to maintain strong gradients for recall
        # Negative gamma: Use the per-class values to suppress easy negatives
        gamma_pos = torch.zeros(num_classes)  # Low gamma for positives
        gamma_neg = torch.zeros(num_classes)  # High gamma for negatives (from config)
        
        for i in range(num_classes):
            neg_gamma = self.per_class_gamma.get(i, base_gamma)
            # Positive gamma: inverse relationship - higher neg_gamma = lower pos_gamma
            # This ensures hard classes get even stronger positive gradients
            gamma_pos[i] = max(0.0, 1.0 - (neg_gamma - 2.0) * 0.25)  # e.g., neg=5 -> pos=0.25
            gamma_neg[i] = neg_gamma
        
        self.register_buffer('gamma_pos', gamma_pos)
        self.register_buffer('gamma_neg', gamma_neg)
        
        # Build per-class positive weight boost
        # Classes with higher gamma (harder classes) get higher positive weight
        pos_weight_boost = torch.ones(num_classes)
        for i in range(num_classes):
            neg_gamma = self.per_class_gamma.get(i, base_gamma)
            # Scale boost by gamma: gamma=2 -> 1.0x, gamma=5 -> 2.5x
            pos_weight_boost[i] = 1.0 + (neg_gamma - 2.0) * 0.5
        self.register_buffer('pos_weight_boost', pos_weight_boost)
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        """Compute asymmetric recall-boosted focal loss."""
        # Apply label smoothing
        if self.label_smoothing > 0:
            targets = targets * (1 - self.label_smoothing) + 0.5 * self.label_smoothing
        
        # Compute probabilities with clamping for numerical stability
        p = torch.sigmoid(logits).clamp(min=1e-7, max=1 - 1e-7)
        
        # Get gamma tensors on correct device
        gamma_pos = self.gamma_pos.to(logits.device).unsqueeze(0)  # (1, C)
        gamma_neg = self.gamma_neg.to(logits.device).unsqueeze(0)  # (1, C)
        pos_weight_boost = self.pos_weight_boost.to(logits.device).unsqueeze(0)  # (1, C)
        
        # ASYMMETRIC focal weights with numerical stability
        # For positives (y=1): weight = (1-p)^gamma_pos  (low gamma = strong weight)
        # For negatives (y=0): weight = p^gamma_neg  (high gamma = suppress easy negs)
        # Clamp to avoid 0^x = 0 killing gradients or x^0 edge cases
        pos_focal_weight = (1 - p + 1e-7).pow(gamma_pos)  # Miss penalty
        neg_focal_weight = (p + 1e-7).pow(gamma_neg)       # False alarm penalty
        
        # Clamp focal weights to reasonable range to avoid NaN
        pos_focal_weight = pos_focal_weight.clamp(min=1e-7, max=10.0)
        neg_focal_weight = neg_focal_weight.clamp(min=1e-7, max=10.0)
        
        # Combine based on target
        focal_weight = targets * pos_focal_weight + (1 - targets) * neg_focal_weight
        
        # BCE loss (without focal weight applied yet)
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
        
        # Apply focal weight
        loss = focal_weight * bce
        
        # Apply per-class positive weight boost + global recall boost
        # This gives EXTRA emphasis to positive samples of hard classes
        # Cap the total positive weight to avoid extreme values
        total_pos_boost = (self.recall_boost_weight * pos_weight_boost).clamp(max=5.0)
        pos_weight = torch.ones_like(targets)
        pos_weight = pos_weight + targets * (total_pos_boost - 1.0)
        loss = loss * pos_weight
        
        # Final safety clamp
        loss = loss.clamp(max=100.0)
        
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class AdaptiveFocalLoss(nn.Module):
    """
    Adaptive Focal Loss that adjusts gamma based on class difficulty.
    
    Classes with lower F1 during training get higher gamma to focus
    more on their hard examples.
    
    Args:
        initial_gamma: Starting gamma for all classes
        max_gamma: Maximum allowed gamma
        adaptation_rate: How quickly gamma adapts to class performance
        num_classes: Number of classes
    """
    
    def __init__(
        self,
        initial_gamma: float = 2.0,
        max_gamma: float = 5.0,
        adaptation_rate: float = 0.1,
        num_classes: int = 12,
        label_smoothing: float = 0.0,
        reduction: str = 'mean',
    ):
        super().__init__()
        self.max_gamma = max_gamma
        self.adaptation_rate = adaptation_rate
        self.label_smoothing = label_smoothing
        self.reduction = reduction
        
        # Learnable per-class gamma (can be updated based on val metrics)
        self.register_buffer('per_class_gamma', torch.full((num_classes,), initial_gamma))
    
    def update_gamma(self, per_class_f1: torch.Tensor):
        """
        Update gamma based on per-class F1 scores.
        
        Lower F1 -> Higher gamma (focus more on that class)
        """
        # Invert F1: low F1 -> high gamma
        target_gamma = 2.0 + (1.0 - per_class_f1) * 3.0  # Range: 2.0 to 5.0
        target_gamma = target_gamma.clamp(max=self.max_gamma)
        
        # Smooth update
        self.per_class_gamma = (
            (1 - self.adaptation_rate) * self.per_class_gamma + 
            self.adaptation_rate * target_gamma
        )
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        if self.label_smoothing > 0:
            targets = targets * (1 - self.label_smoothing) + 0.5 * self.label_smoothing
        
        p = torch.sigmoid(logits)
        
        # Per-class focal weight - ensure on same device as logits
        gamma = self.per_class_gamma.to(logits.device).unsqueeze(0)
        pt = p * targets + (1 - p) * (1 - targets)
        focal_weight = (1 - pt).pow(gamma)
        
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
        loss = focal_weight * bce
        
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class ClassBalancedFocalBCELoss(nn.Module):
    """
    Class-Balanced Focal BCE Loss for Multi-Label Classification.
    
    This combines the two techniques that achieved 95% on single-label:
    1. Effective number weighting (cb-beta) from CVPR 2019 paper
    2. Focal loss focusing on hard examples
    
    Adapted for multi-label (BCE) instead of single-label (CrossEntropy).
    
    Reference: "Class-Balanced Loss Based on Effective Number of Samples" (Cui et al., 2019)
    
    The effective number captures diminishing returns of additional samples:
        E_n = (1 - β^n) / (1 - β)
    
    Weights are inverse of effective number, giving higher weight to rare classes.
    
    Args:
        class_counts: Number of positive samples per class
        beta: Effective number hyperparameter (0.999 for moderate, 0.9999 for extreme imbalance)
        gamma: Focal loss gamma (2.0 recommended)
        label_smoothing: Label smoothing factor
        reduction: 'mean', 'sum', or 'none'
    """
    
    def __init__(
        self,
        class_counts: Union[List[int], np.ndarray, torch.Tensor],
        beta: float = 0.999,
        gamma: float = 2.0,
        label_smoothing: float = 0.0,
        reduction: str = 'mean',
        extra_class_weights: Optional[torch.Tensor] = None,
    ):
        super().__init__()
        self.gamma = gamma
        self.label_smoothing = label_smoothing
        self.reduction = reduction
        self.beta = beta
        
        # Convert class_counts to numpy
        if isinstance(class_counts, torch.Tensor):
            class_counts = class_counts.cpu().numpy()
        elif isinstance(class_counts, list):
            class_counts = np.array(class_counts)
        
        # Compute effective number of samples per class
        # E_n = (1 - β^n) / (1 - β)
        effective_num = np.array([
            (1.0 - beta ** n) / (1.0 - beta) if n > 0 else 1e-6
            for n in class_counts
        ])
        
        # Weights are inverse of effective number
        weights = 1.0 / effective_num
        
        # Normalize so mean weight = 1
        weights = weights / weights.mean()
        
        # Apply extra per-class weights (e.g., --class-loss-weight china=5.0)
        # This multiplies on top of the CB weights to boost/suppress specific classes
        if extra_class_weights is not None:
            extra_np = extra_class_weights.cpu().numpy()
            weights = weights * extra_np
            print(f"  Extra class weights: {extra_np.round(3)}")
            print(f"  Final weights (CB * extra): {weights.round(3)}")
        
        self.register_buffer('weights', torch.tensor(weights, dtype=torch.float32))
        
        # Log the computed weights
        print(f"[CB-Focal BCE] Beta={beta}, Gamma={gamma}")
        print(f"  Class counts: {class_counts}")
        print(f"  Effective numbers: {effective_num.astype(int)}")
        print(f"  Weights (normalized): {weights.round(3)}")
    
    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute class-balanced focal BCE loss.
        
        Args:
            logits: Raw predictions (B, C)
            targets: Multi-hot targets (B, C)
        
        Returns:
            Loss tensor
        """
        # Apply label smoothing
        if self.label_smoothing > 0:
            targets = targets * (1 - self.label_smoothing) + 0.5 * self.label_smoothing
        
        # Get probabilities
        p = torch.sigmoid(logits)
        
        # Focal weight: pt = p if y=1, (1-p) if y=0
        pt = p * targets + (1 - p) * (1 - targets)
        focal_weight = (1 - pt).pow(self.gamma)
        
        # BCE loss
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
        
        # Apply focal weight
        loss = focal_weight * bce
        
        # Apply class-balanced weights
        loss = loss * self.weights.unsqueeze(0)  # (B, C) * (1, C)
        
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class OnlineHardExampleMiningLoss(nn.Module):
    """
    Online Hard Example Mining (OHEM) Loss for Multi-Label Classification.
    
    This loss focuses training on the hardest examples within each batch:
    1. For each sample, compute per-class loss
    2. Identify "hard" samples where positive class probability is in uncertain range
    3. Weight hard samples higher than easy samples
    
    This is more efficient than offline hard example mining because:
    - No need to pre-extract hard examples
    - Adapts as model improves
    - Can be combined with other loss types
    
    Args:
        hard_fraction: Fraction of batch to treat as "hard" (default: 0.5)
        hard_weight: Weight multiplier for hard examples (default: 3.0)
        p_low: Lower probability threshold for "uncertain" samples (default: 0.2)
        p_high: Upper probability threshold for "uncertain" samples (default: 0.6)
        base_loss: Underlying loss type ('focal' or 'bce')
        gamma: Focal loss gamma if using focal base
        label_smoothing: Label smoothing factor
        per_class_weight: Optional dict mapping class index to extra weight multiplier
    """
    
    def __init__(
        self,
        hard_fraction: float = 0.5,
        hard_weight: float = 3.0,
        p_low: float = 0.2,
        p_high: float = 0.6,
        base_loss: str = 'focal',
        gamma: float = 2.0,
        label_smoothing: float = 0.0,
        reduction: str = 'mean',
        per_class_weight: Optional[Dict[int, float]] = None,
        num_classes: int = 12,
    ):
        super().__init__()
        self.hard_fraction = hard_fraction
        self.hard_weight = hard_weight
        self.p_low = p_low
        self.p_high = p_high
        self.gamma = gamma
        self.label_smoothing = label_smoothing
        self.reduction = reduction
        self.base_loss = base_loss
        
        # Build per-class weight tensor for boosting weak classes
        class_weights = torch.ones(num_classes)
        if per_class_weight:
            for idx, weight in per_class_weight.items():
                class_weights[idx] = weight
        self.register_buffer('class_weights', class_weights)
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute OHEM loss.
        
        Args:
            logits: Raw predictions (before sigmoid), shape (B, C)
            targets: Multi-hot targets, shape (B, C), values in [0, 1]
        
        Returns:
            Loss tensor
        """
        batch_size = logits.size(0)
        
        # Apply label smoothing
        if self.label_smoothing > 0:
            targets_smooth = targets * (1 - self.label_smoothing) + 0.5 * self.label_smoothing
        else:
            targets_smooth = targets
        
        # Compute probabilities
        p = torch.sigmoid(logits)
        
        # Compute per-sample hardness score
        # A sample is "hard" if its positive classes have probabilities in [p_low, p_high]
        # This means the model is uncertain about these positives
        
        # For each sample, find positive classes
        positive_mask = targets > 0.5  # (B, C)
        
        # Check if probabilities are in uncertain range
        uncertain_mask = (p >= self.p_low) & (p <= self.p_high)  # (B, C)
        
        # Sample is hard if ANY positive class is uncertain
        hard_positives = positive_mask & uncertain_mask  # (B, C)
        hardness_score = hard_positives.float().sum(dim=1)  # (B,) - count of uncertain positives
        
        # Also consider high-confidence false positives as hard
        # (model is confidently wrong about negatives)
        fp_mask = (~positive_mask) & (p > 0.6)  # False positive with high confidence
        fp_score = fp_mask.float().sum(dim=1)
        
        # Combined hardness
        hardness_score = hardness_score + 0.5 * fp_score
        
        # Compute per-sample loss (before reduction)
        # Get per-class weights for boosting weak classes
        class_weights = self.class_weights.to(logits.device).unsqueeze(0)  # (1, C)
        
        if self.base_loss == 'focal':
            pt = p * targets_smooth + (1 - p) * (1 - targets_smooth)
            focal_weight = (1 - pt).pow(self.gamma)
            bce = F.binary_cross_entropy_with_logits(logits, targets_smooth, reduction='none')
            # Apply per-class weights to boost weak classes
            weighted_bce = focal_weight * bce * class_weights
            per_sample_loss = weighted_bce.mean(dim=1)  # (B,)
        else:
            bce = F.binary_cross_entropy_with_logits(logits, targets_smooth, reduction='none')
            # Apply per-class weights to boost weak classes
            weighted_bce = bce * class_weights
            per_sample_loss = weighted_bce.mean(dim=1)  # (B,)
        
        # Compute sample weights based on hardness
        # Option 1: Top-k hard samples get higher weight
        k = int(batch_size * self.hard_fraction)
        if k > 0 and k < batch_size:
            _, hard_indices = torch.topk(hardness_score, k)
            sample_weights = torch.ones(batch_size, device=logits.device)
            sample_weights[hard_indices] = self.hard_weight
        else:
            # All samples get weight based on continuous hardness
            sample_weights = 1.0 + (self.hard_weight - 1.0) * (hardness_score / (hardness_score.max() + 1e-8))
        
        # Apply sample weights
        weighted_loss = per_sample_loss * sample_weights
        
        if self.reduction == 'mean':
            return weighted_loss.mean()
        elif self.reduction == 'sum':
            return weighted_loss.sum()
        return weighted_loss


# Default per-class gamma settings based on threshold-tuned F1 analysis
# Classes with low F1 get higher gamma for more aggressive gradient focus
# Target: Push ALL classes toward 0.90+ F1
# Formula: gamma = max(2.0, 6.0 - 5.0 * F1) caps at 6.0 for worst performers
DEFAULT_PER_CLASS_GAMMA = {
    0: 2.0,   # china - EXCELLENT (F1=0.985) - minimal boost needed
    1: 2.5,   # crash - GOOD (F1=0.868) - slight boost
    2: 5.0,   # cross_stick - CRITICAL (F1=0.671) - major boost needed
    3: 4.0,   # hihat_closed - LOW (F1=0.725) - significant boost
    4: 4.0,   # hihat_open - LOW (F1=0.735) - significant boost
    5: 6.0,   # hihat_pedal - CRITICAL (F1=0.495) - MAXIMUM boost (worst class)
    6: 3.0,   # kick - OK (F1=0.801) - moderate boost
    7: 4.0,   # ride_bell - LOW (F1=0.747) - significant boost
    8: 5.0,   # ride_bow - CRITICAL (F1=0.684) - major boost needed
    9: 3.0,   # snare - OK (F1=0.767) - moderate boost
    10: 2.0,  # splash - EXCELLENT (F1=0.975) - minimal boost
    11: 3.0,  # tom - OK (F1=0.767) - moderate boost
}


def get_multilabel_loss(
    loss_type: str = "bce",
    pos_weight: Optional[torch.Tensor] = None,
    gamma: float = 2.0,
    label_smoothing: float = 0.0,
    per_class_gamma: Optional[dict] = None,
    recall_boost_weight: float = 1.0,
    num_classes: int = 12,
    hard_fraction: float = 0.5,
    hard_weight: float = 3.0,
    class_counts: Optional[Union[List[int], np.ndarray, torch.Tensor]] = None,
    cb_beta: float = 0.999,
    extra_class_weights: Optional[torch.Tensor] = None,
    **kwargs
) -> nn.Module:
    """
    Factory function to create multi-label loss.
    
    Args:
        loss_type: "bce", "focal", "asymmetric", "recall_boost", "adaptive", "ohem", or "cb_focal"
        pos_weight: Per-class positive weights
        gamma: Focusing parameter for focal loss
        label_smoothing: Label smoothing factor
        per_class_gamma: Dict mapping class index to gamma (for recall_boost)
        recall_boost_weight: Extra weight for positive samples (for recall_boost)
        num_classes: Number of output classes
        hard_fraction: Fraction of batch treated as hard examples (for ohem)
        hard_weight: Weight multiplier for hard examples (for ohem)
        class_counts: Per-class sample counts (for cb_focal)
        cb_beta: Class-balanced beta hyperparameter (for cb_focal)
    
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
    elif loss_type == "recall_boost":
        return RecallBoostFocalLoss(
            per_class_gamma=per_class_gamma or DEFAULT_PER_CLASS_GAMMA,
            recall_boost_weight=recall_boost_weight,
            base_gamma=gamma,
            label_smoothing=label_smoothing,
            num_classes=num_classes,
            **kwargs
        )
    elif loss_type == "adaptive":
        return AdaptiveFocalLoss(
            initial_gamma=gamma,
            label_smoothing=label_smoothing,
            num_classes=num_classes,
            **kwargs
        )
    elif loss_type == "ohem":
        # Build per-class weight from per_class_gamma - weak classes get higher weight
        per_class_weight = None
        if per_class_gamma:
            per_class_weight = {
                idx: 1.0 + (g - 2.0) * 0.5  # gamma=2 -> 1.0x, gamma=5 -> 2.5x
                for idx, g in per_class_gamma.items()
            }
        return OnlineHardExampleMiningLoss(
            hard_fraction=hard_fraction,
            hard_weight=hard_weight,
            gamma=gamma,
            label_smoothing=label_smoothing,
            per_class_weight=per_class_weight,
            num_classes=num_classes,
            **kwargs
        )
    elif loss_type == "cb_focal":
        # Class-balanced focal BCE loss (the technique that got 95% on single-label)
        if class_counts is None:
            raise ValueError("cb_focal loss requires class_counts to compute effective number weights")
        return ClassBalancedFocalBCELoss(
            class_counts=class_counts,
            beta=cb_beta,
            gamma=gamma,
            label_smoothing=label_smoothing,
            extra_class_weights=extra_class_weights,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown loss type: {loss_type}. Choose from: bce, focal, asymmetric, recall_boost, adaptive, ohem, cb_focal")
