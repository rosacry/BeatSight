"""
R-Drop: Regularized Dropout for Improved Generalization

R-Drop is a simple yet powerful regularization method that forces the model
to be consistent under different dropout masks. By running each sample through
the model twice with different dropout, and minimizing the KL divergence between
the two outputs, we get significantly better generalization.

Paper: "R-Drop: Regularized Dropout for Neural Networks" (Liang et al., NeurIPS 2021)
       https://arxiv.org/abs/2106.14448

How it works:
1. Forward pass x through model with dropout → logits_1
2. Forward pass x again with different dropout mask → logits_2
3. Compute standard loss on both: (CE(logits_1, y) + CE(logits_2, y)) / 2
4. Compute consistency loss: KL(logits_1 || logits_2) + KL(logits_2 || logits_1)
5. Total loss = standard_loss + alpha * consistency_loss

Benefits for drum classification:
- Reduces overfitting on small classes (ghost notes, certain cymbals)
- More robust predictions across different recording conditions
- Better calibrated confidence scores
- Minimal implementation overhead

Expected improvement: 0.5-1% accuracy

Usage:
    from training.losses.rdrop import RDropLoss, rdrop_forward
    
    criterion = RDropLoss(alpha=0.5, base_loss='focal')
    
    # In training loop:
    logits_1, logits_2 = rdrop_forward(model, inputs)
    loss = criterion(logits_1, logits_2, labels)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional, Union


class RDropLoss(nn.Module):
    """
    R-Drop Loss combining task loss with consistency regularization.
    
    Args:
        alpha: Weight of the consistency loss (default: 0.5)
               Higher alpha = stronger regularization
               Typical range: 0.1 - 1.0
        base_loss: Base loss function - 'ce' for CrossEntropy, 'focal' for FocalLoss
        focal_gamma: Gamma parameter if using focal loss
        label_smoothing: Label smoothing factor (0.0 = no smoothing)
        reduction: 'mean', 'sum', or 'none'
    
    Example:
        >>> criterion = RDropLoss(alpha=0.5, base_loss='focal')
        >>> logits_1 = model(x)  # First forward pass
        >>> logits_2 = model(x)  # Second forward pass (different dropout)
        >>> loss = criterion(logits_1, logits_2, labels)
    """
    
    def __init__(
        self,
        alpha: float = 0.5,
        base_loss: str = 'ce',
        focal_gamma: float = 2.0,
        label_smoothing: float = 0.0,
        reduction: str = 'mean',
        class_weights: Optional[torch.Tensor] = None,
    ):
        super().__init__()
        self.alpha = alpha
        self.base_loss_type = base_loss
        self.reduction = reduction
        self.class_weights = class_weights
        
        # Setup base loss
        if base_loss == 'ce':
            self.base_loss = nn.CrossEntropyLoss(
                weight=class_weights,
                label_smoothing=label_smoothing,
                reduction=reduction
            )
        elif base_loss == 'focal':
            # Import focal loss if available
            try:
                from training.losses.focal_loss import FocalLoss
                self.base_loss = FocalLoss(
                    gamma=focal_gamma,
                    weight=class_weights,
                    label_smoothing=label_smoothing,
                    reduction=reduction
                )
            except ImportError:
                # Fallback to CE if focal not available
                self.base_loss = nn.CrossEntropyLoss(
                    weight=class_weights,
                    label_smoothing=label_smoothing,
                    reduction=reduction
                )
        else:
            raise ValueError(f"Unknown base_loss: {base_loss}. Use 'ce' or 'focal'")
    
    def compute_kl_loss(
        self,
        logits_1: torch.Tensor,
        logits_2: torch.Tensor,
        temperature: float = 1.0
    ) -> torch.Tensor:
        """
        Compute symmetric KL divergence between two distributions.
        
        KL(P || Q) + KL(Q || P) for symmetry
        """
        # Convert to probabilities
        p = F.softmax(logits_1 / temperature, dim=-1)
        q = F.softmax(logits_2 / temperature, dim=-1)
        
        # Log probabilities
        log_p = F.log_softmax(logits_1 / temperature, dim=-1)
        log_q = F.log_softmax(logits_2 / temperature, dim=-1)
        
        # Symmetric KL
        kl_pq = F.kl_div(log_q, p, reduction='batchmean')
        kl_qp = F.kl_div(log_p, q, reduction='batchmean')
        
        return (kl_pq + kl_qp) / 2
    
    def forward(
        self,
        logits_1: torch.Tensor,
        logits_2: torch.Tensor,
        labels: torch.Tensor,
        mixed_labels: Optional[torch.Tensor] = None,
        lam: Optional[float] = None,
    ) -> torch.Tensor:
        """
        Compute R-Drop loss.
        
        Args:
            logits_1: Output from first forward pass [B, num_classes]
            logits_2: Output from second forward pass [B, num_classes]
            labels: Ground truth labels [B] or soft labels [B, num_classes]
            mixed_labels: Optional second labels for mixup (for mixed_criterion)
            lam: Optional mixup lambda
            
        Returns:
            Combined R-Drop loss
        """
        # Handle mixup case
        if mixed_labels is not None and lam is not None:
            # Mixup loss for both passes
            loss_1 = lam * self.base_loss(logits_1, labels) + (1 - lam) * self.base_loss(logits_1, mixed_labels)
            loss_2 = lam * self.base_loss(logits_2, labels) + (1 - lam) * self.base_loss(logits_2, mixed_labels)
        else:
            # Standard loss for both passes
            loss_1 = self.base_loss(logits_1, labels)
            loss_2 = self.base_loss(logits_2, labels)
        
        # Average task loss
        task_loss = (loss_1 + loss_2) / 2
        
        # Consistency loss (KL divergence)
        kl_loss = self.compute_kl_loss(logits_1, logits_2)
        
        # Combined loss
        total_loss = task_loss + self.alpha * kl_loss
        
        return total_loss
    
    def forward_single(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
    ) -> torch.Tensor:
        """Standard forward without R-Drop (for validation)."""
        return self.base_loss(logits, labels)


def rdrop_forward(
    model: nn.Module,
    inputs: torch.Tensor,
    training: bool = True
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Perform two forward passes through the model for R-Drop.
    
    The model must have dropout enabled for this to be effective.
    
    Args:
        model: The neural network model
        inputs: Input tensor [B, C, H, W]
        training: Whether in training mode (enables dropout variation)
        
    Returns:
        Tuple of (logits_1, logits_2) from two forward passes
    """
    if training:
        model.train()  # Ensure dropout is active
        logits_1 = model(inputs)
        logits_2 = model(inputs)
    else:
        model.eval()
        with torch.no_grad():
            logits_1 = model(inputs)
            logits_2 = logits_1  # Same in eval mode
    
    return logits_1, logits_2


class RDropWrapper:
    """
    Wrapper to easily integrate R-Drop into existing training loops.
    
    Usage:
        rdrop = RDropWrapper(model, criterion, alpha=0.5)
        
        # In training loop:
        loss = rdrop.compute_loss(inputs, labels)
        loss.backward()
    """
    
    def __init__(
        self,
        model: nn.Module,
        base_criterion: nn.Module,
        alpha: float = 0.5,
    ):
        self.model = model
        self.base_criterion = base_criterion
        self.alpha = alpha
    
    def compute_loss(
        self,
        inputs: torch.Tensor,
        labels: torch.Tensor,
        return_logits: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
        """
        Compute R-Drop loss with two forward passes.
        
        Returns:
            loss if return_logits=False
            (loss, logits_1, logits_2) if return_logits=True
        """
        self.model.train()
        
        logits_1 = self.model(inputs)
        logits_2 = self.model(inputs)
        
        # Base losses
        loss_1 = self.base_criterion(logits_1, labels)
        loss_2 = self.base_criterion(logits_2, labels)
        task_loss = (loss_1 + loss_2) / 2
        
        # KL consistency
        p = F.softmax(logits_1, dim=-1)
        q = F.softmax(logits_2, dim=-1)
        kl_loss = (
            F.kl_div(F.log_softmax(logits_1, dim=-1), q, reduction='batchmean') +
            F.kl_div(F.log_softmax(logits_2, dim=-1), p, reduction='batchmean')
        ) / 2
        
        total_loss = task_loss + self.alpha * kl_loss
        
        if return_logits:
            return total_loss, logits_1, logits_2
        return total_loss


def get_rdrop_loss(
    alpha: float = 0.5,
    base_loss: str = 'focal',
    focal_gamma: float = 2.0,
    label_smoothing: float = 0.1,
    class_weights: Optional[torch.Tensor] = None,
) -> RDropLoss:
    """
    Factory function to create R-Drop loss with recommended settings.
    
    Args:
        alpha: R-Drop consistency weight (0.5 is a good default)
        base_loss: 'ce' or 'focal'
        focal_gamma: Focal loss gamma (only used if base_loss='focal')
        label_smoothing: Label smoothing factor
        class_weights: Optional class weights for imbalanced datasets
        
    Returns:
        Configured RDropLoss instance
    """
    return RDropLoss(
        alpha=alpha,
        base_loss=base_loss,
        focal_gamma=focal_gamma,
        label_smoothing=label_smoothing,
        class_weights=class_weights,
    )
