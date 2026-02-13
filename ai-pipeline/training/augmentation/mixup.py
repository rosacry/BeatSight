"""
Mixup and CutMix Data Augmentation for Drum Classification

This module implements Mixup and CutMix augmentation techniques that can
significantly improve model generalization and calibration.

References:
- Mixup: "mixup: Beyond Empirical Risk Minimization" (Zhang et al., 2017)
- CutMix: "CutMix: Regularization Strategy to Train Strong Classifiers" (Yun et al., 2019)

Why these help drum classification:
- Reduces overconfidence on clear-cut examples
- Improves handling of ambiguous hits (ghost notes, rimshots vs cross-sticks)
- Better generalization to unseen recording conditions
- Acts as implicit label smoothing

Usage:
    from training.augmentation.mixup import MixupCutmix
    
    # In training loop:
    augmenter = MixupCutmix(mixup_alpha=0.4, cutmix_alpha=1.0, prob=0.5)
    
    for features, labels in dataloader:
        features, labels_a, labels_b, lam = augmenter(features, labels)
        outputs = model(features)
        loss = lam * criterion(outputs, labels_a) + (1 - lam) * criterion(outputs, labels_b)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, Tuple

import torch
import torch.nn as nn


@dataclass
class AugmentationResult:
    """Result of mixup/cutmix augmentation."""
    features: torch.Tensor
    labels_a: torch.Tensor
    labels_b: torch.Tensor
    lam: float
    method: str  # "none", "mixup", or "cutmix"


def mixup_data(
    x: torch.Tensor,
    y: torch.Tensor,
    alpha: float = 1.0,
    device: Optional[torch.device] = None
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, float]:
    """
    Apply Mixup augmentation to a batch.
    
    Mixup creates convex combinations of pairs of examples and their labels:
        x_mixed = lam * x_i + (1 - lam) * x_j
        y_mixed = lam * y_i + (1 - lam) * y_j
    
    Args:
        x: Input features of shape (batch, ...)
        y: Labels of shape (batch,)
        alpha: Beta distribution parameter (higher = more mixing)
        device: Device for random tensor generation
        
    Returns:
        Tuple of (mixed_x, y_a, y_b, lam) for computing mixed loss
    """
    if alpha <= 0:
        return x, y, y, 1.0
    
    device = device or x.device
    batch_size = x.size(0)
    
    # Sample lambda from Beta distribution
    lam = torch.distributions.Beta(alpha, alpha).sample().item()
    
    # Random permutation for pairing
    index = torch.randperm(batch_size, device=device)
    
    # Mix features
    mixed_x = lam * x + (1 - lam) * x[index]
    
    return mixed_x, y, y[index], lam


def cutmix_data(
    x: torch.Tensor,
    y: torch.Tensor,
    alpha: float = 1.0,
    device: Optional[torch.device] = None
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, float]:
    """
    Apply CutMix augmentation to a batch.
    
    CutMix cuts and pastes patches between training images:
        x_mixed[..., bbx1:bbx2, bby1:bby2] = x_j[..., bbx1:bbx2, bby1:bby2]
        y_mixed = lam * y_i + (1 - lam) * y_j
    
    For spectrograms, this means mixing frequency-time regions, which:
    - Forces the model to look at multiple frequency bands
    - Prevents over-reliance on single spectral features
    
    Args:
        x: Input features of shape (batch, channels, height, width)
        y: Labels of shape (batch,)
        alpha: Beta distribution parameter
        device: Device for random tensor generation
        
    Returns:
        Tuple of (mixed_x, y_a, y_b, lam) for computing mixed loss
    """
    if alpha <= 0:
        return x, y, y, 1.0
    
    device = device or x.device
    batch_size = x.size(0)
    
    # Sample lambda from Beta distribution
    lam = torch.distributions.Beta(alpha, alpha).sample().item()
    
    # Random permutation for pairing
    index = torch.randperm(batch_size, device=device)
    
    # Generate random bounding box
    _, _, H, W = x.shape
    bbx1, bby1, bbx2, bby2 = _rand_bbox(H, W, lam)
    
    # Cut and paste
    mixed_x = x.clone()
    mixed_x[:, :, bbx1:bbx2, bby1:bby2] = x[index, :, bbx1:bbx2, bby1:bby2]
    
    # Adjust lambda based on actual box area
    lam = 1 - ((bbx2 - bbx1) * (bby2 - bby1) / (H * W))
    
    return mixed_x, y, y[index], lam


def _rand_bbox(H: int, W: int, lam: float) -> Tuple[int, int, int, int]:
    """Generate random bounding box for CutMix."""
    cut_ratio = (1.0 - lam) ** 0.5
    cut_h = int(H * cut_ratio)
    cut_w = int(W * cut_ratio)
    
    # Uniform center point
    cx = random.randint(0, H)
    cy = random.randint(0, W)
    
    # Clamp to image bounds
    bbx1 = max(0, cx - cut_h // 2)
    bby1 = max(0, cy - cut_w // 2)
    bbx2 = min(H, cx + cut_h // 2)
    bby2 = min(W, cy + cut_w // 2)
    
    return bbx1, bby1, bbx2, bby2


class MixupCutmix(nn.Module):
    """
    Combined Mixup and CutMix augmentation module.
    
    Randomly applies either Mixup, CutMix, or no augmentation to each batch.
    
    Args:
        mixup_alpha: Mixup beta distribution parameter (0 to disable)
        cutmix_alpha: CutMix beta distribution parameter (0 to disable)
        prob: Probability of applying any augmentation
        switch_prob: Probability of using CutMix vs Mixup when augmenting
        
    Example:
        augmenter = MixupCutmix(mixup_alpha=0.4, cutmix_alpha=1.0, prob=0.5)
        
        for features, labels in train_loader:
            result = augmenter(features, labels)
            outputs = model(result.features)
            
            # Mixed loss for soft labels
            loss = result.lam * criterion(outputs, result.labels_a) + \
                   (1 - result.lam) * criterion(outputs, result.labels_b)
    """
    
    def __init__(
        self,
        mixup_alpha: float = 0.4,
        cutmix_alpha: float = 1.0,
        prob: float = 0.5,
        switch_prob: float = 0.5,
    ):
        super().__init__()
        self.mixup_alpha = mixup_alpha
        self.cutmix_alpha = cutmix_alpha
        self.prob = prob
        self.switch_prob = switch_prob
        
        # Track which augmentation to use
        self._mixup_enabled = mixup_alpha > 0
        self._cutmix_enabled = cutmix_alpha > 0
    
    def forward(
        self,
        x: torch.Tensor,
        y: torch.Tensor
    ) -> AugmentationResult:
        """
        Apply random augmentation to batch.
        
        Args:
            x: Input features (batch, channels, height, width)
            y: Integer labels (batch,)
            
        Returns:
            AugmentationResult with mixed features and label components
        """
        # Skip augmentation with probability (1 - prob)
        if random.random() > self.prob:
            return AugmentationResult(
                features=x,
                labels_a=y,
                labels_b=y,
                lam=1.0,
                method="none"
            )
        
        # Choose between mixup and cutmix
        use_cutmix = random.random() < self.switch_prob and self._cutmix_enabled
        
        if use_cutmix:
            mixed_x, y_a, y_b, lam = cutmix_data(x, y, self.cutmix_alpha)
            method = "cutmix"
        elif self._mixup_enabled:
            mixed_x, y_a, y_b, lam = mixup_data(x, y, self.mixup_alpha)
            method = "mixup"
        else:
            return AugmentationResult(
                features=x,
                labels_a=y,
                labels_b=y,
                lam=1.0,
                method="none"
            )
        
        return AugmentationResult(
            features=mixed_x,
            labels_a=y_a,
            labels_b=y_b,
            lam=lam,
            method=method
        )
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"mixup_alpha={self.mixup_alpha}, "
            f"cutmix_alpha={self.cutmix_alpha}, "
            f"prob={self.prob}, "
            f"switch_prob={self.switch_prob})"
        )


def mixed_criterion(
    outputs: torch.Tensor,
    labels_a: torch.Tensor,
    labels_b: torch.Tensor,
    lam: float,
    criterion: nn.Module
) -> torch.Tensor:
    """
    Compute loss with mixed labels.
    
    Args:
        outputs: Model predictions (batch, num_classes)
        labels_a: First set of labels
        labels_b: Second set of labels (from shuffled batch)
        lam: Mixing coefficient
        criterion: Loss function (e.g., CrossEntropyLoss)
        
    Returns:
        Mixed loss value
    """
    return lam * criterion(outputs, labels_a) + (1 - lam) * criterion(outputs, labels_b)


class SoftTargetCrossEntropy(nn.Module):
    """
    Cross-entropy loss for soft targets (one-hot or probability distributions).
    
    This is useful when:
    - Using Mixup/CutMix with one-hot encoded targets
    - Performing knowledge distillation
    - Using label smoothing with explicit soft targets
    """
    
    def __init__(self, reduction: str = "mean"):
        super().__init__()
        self.reduction = reduction
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """
        Compute soft cross-entropy loss.
        
        Args:
            pred: Log-softmax predictions (batch, num_classes)
            target: Soft target probabilities (batch, num_classes)
            
        Returns:
            Loss value
        """
        log_probs = torch.log_softmax(pred, dim=-1)
        loss = -(target * log_probs).sum(dim=-1)
        
        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        return loss


def create_soft_labels(
    labels: torch.Tensor,
    num_classes: int,
    smoothing: float = 0.0
) -> torch.Tensor:
    """
    Convert hard labels to soft (one-hot with optional smoothing).
    
    Args:
        labels: Integer labels (batch,)
        num_classes: Number of classes
        smoothing: Label smoothing factor (0.0 = one-hot, 0.1 = typical smoothing)
        
    Returns:
        Soft label tensor (batch, num_classes)
    """
    batch_size = labels.size(0)
    soft = torch.zeros(batch_size, num_classes, device=labels.device)
    soft.fill_(smoothing / (num_classes - 1))
    soft.scatter_(1, labels.unsqueeze(1), 1.0 - smoothing)
    return soft


# =============================================================================
# Integration helpers for train_classifier.py
# =============================================================================

def get_mixup_args(parser):
    """Add mixup/cutmix arguments to an argparse parser."""
    group = parser.add_argument_group("Mixup/CutMix Augmentation")
    group.add_argument(
        "--mixup-alpha",
        type=float,
        default=0.0,
        help="Mixup alpha parameter (0 to disable, 0.2-0.4 typical)",
    )
    group.add_argument(
        "--cutmix-alpha",
        type=float,
        default=0.0,
        help="CutMix alpha parameter (0 to disable, 1.0 typical)",
    )
    group.add_argument(
        "--mixup-prob",
        type=float,
        default=0.5,
        help="Probability of applying mixup/cutmix per batch",
    )
    group.add_argument(
        "--mixup-switch-prob",
        type=float,
        default=0.5,
        help="Probability of using CutMix vs Mixup when augmenting",
    )
    return group


def create_augmenter_from_args(args) -> Optional[MixupCutmix]:
    """Create a MixupCutmix instance from parsed arguments."""
    if args.mixup_alpha > 0 or args.cutmix_alpha > 0:
        return MixupCutmix(
            mixup_alpha=args.mixup_alpha,
            cutmix_alpha=args.cutmix_alpha,
            prob=args.mixup_prob,
            switch_prob=args.mixup_switch_prob,
        )
    return None


# =============================================================================
# Visualization and debugging
# =============================================================================

def visualize_augmentation(
    features: torch.Tensor,
    labels: torch.Tensor,
    num_classes: int = 21,
    save_path: Optional[str] = None
):
    """
    Visualize mixup/cutmix augmentation effects.
    
    Args:
        features: Batch of spectrograms (batch, 1, H, W)
        labels: Integer labels (batch,)
        num_classes: Number of classes
        save_path: Optional path to save visualization
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib required for visualization")
        return
    
    augmenter = MixupCutmix(mixup_alpha=0.4, cutmix_alpha=1.0, prob=1.0)
    
    # Force mixup
    augmenter._cutmix_enabled = False
    mixup_result = augmenter(features, labels)
    
    # Force cutmix
    augmenter._cutmix_enabled = True
    augmenter._mixup_enabled = False
    cutmix_result = augmenter(features, labels)
    
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    
    # Original samples
    for i in range(min(2, features.size(0))):
        axes[0, i].imshow(features[i, 0].cpu().numpy(), aspect='auto', origin='lower')
        axes[0, i].set_title(f"Original (class {labels[i].item()})")
        axes[0, i].axis('off')
    
    # Mixup result
    axes[0, 2].imshow(mixup_result.features[0, 0].cpu().numpy(), aspect='auto', origin='lower')
    axes[0, 2].set_title(f"Mixup (λ={mixup_result.lam:.2f})")
    axes[0, 2].axis('off')
    
    # CutMix result
    axes[0, 3].imshow(cutmix_result.features[0, 0].cpu().numpy(), aspect='auto', origin='lower')
    axes[0, 3].set_title(f"CutMix (λ={cutmix_result.lam:.2f})")
    axes[0, 3].axis('off')
    
    # Difference maps
    axes[1, 2].imshow((mixup_result.features[0, 0] - features[0, 0]).abs().cpu().numpy(), 
                       aspect='auto', origin='lower', cmap='hot')
    axes[1, 2].set_title("Mixup difference")
    axes[1, 2].axis('off')
    
    axes[1, 3].imshow((cutmix_result.features[0, 0] - features[0, 0]).abs().cpu().numpy(),
                       aspect='auto', origin='lower', cmap='hot')
    axes[1, 3].set_title("CutMix difference")
    axes[1, 3].axis('off')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved visualization to {save_path}")
    else:
        plt.show()
    
    plt.close()


if __name__ == "__main__":
    print("Mixup/CutMix Augmentation Module")
    print("=" * 50)
    
    # Demo with random data
    batch_size = 8
    num_classes = 21
    
    features = torch.randn(batch_size, 1, 128, 128)
    labels = torch.randint(0, num_classes, (batch_size,))
    
    print(f"\nInput shape: {features.shape}")
    print(f"Labels: {labels.tolist()}")
    
    # Test mixup
    mixed_x, y_a, y_b, lam = mixup_data(features, labels, alpha=0.4)
    print("\nMixup (alpha=0.4):")
    print(f"  λ = {lam:.3f}")
    print(f"  y_a: {y_a.tolist()}")
    print(f"  y_b: {y_b.tolist()}")
    
    # Test cutmix
    mixed_x, y_a, y_b, lam = cutmix_data(features, labels, alpha=1.0)
    print("\nCutMix (alpha=1.0):")
    print(f"  λ = {lam:.3f}")
    print(f"  y_a: {y_a.tolist()}")
    print(f"  y_b: {y_b.tolist()}")
    
    # Test combined module
    augmenter = MixupCutmix(mixup_alpha=0.4, cutmix_alpha=1.0, prob=0.8)
    print(f"\n{augmenter}")
    
    result = augmenter(features, labels)
    print("\nAugmentation result:")
    print(f"  Method: {result.method}")
    print(f"  λ = {result.lam:.3f}")
