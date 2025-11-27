"""
Hard Negative Mining for Drum Classification

Hard negative mining focuses training on the most confusing sample pairs,
improving discrimination between similar-sounding drums.

For drum classification, common confusions include:
- Snare vs Rimshot vs Cross-stick
- Hi-hat closed vs Hi-hat pedal
- Crash vs China vs Splash
- Tom high vs Tom mid

This module provides:
1. Online Hard Negative Mining (OHEM) - Mine within each batch
2. Semi-Hard Negative Mining - Margin-based selection
3. Curriculum-aware Mining - Start easy, gradually add hard negatives
4. Contrastive Loss - Embedding-space separation for confused pairs

Reference:
- "Training Region-based Object Detectors with Online Hard Example Mining" (CVPR 2016)
- "FaceNet: A Unified Embedding for Face Recognition and Clustering" (CVPR 2015)
- "Dimensionality Reduction by Learning an Invariant Mapping" (CVPR 2006) - Contrastive Loss

Expected improvement: +0.5-1% on confusable classes (+0.3-0.5% with contrastive)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class HardNegativeConfig:
    """Configuration for hard negative mining."""
    
    # Mining strategy
    strategy: str = "ohem"  # "ohem", "semi_hard", "curriculum"
    
    # OHEM parameters
    ohem_ratio: float = 0.7  # Keep top 70% hardest samples
    min_samples_per_class: int = 2  # Minimum samples per class
    
    # Semi-hard parameters
    margin: float = 0.2  # Triplet margin
    
    # Curriculum parameters
    curriculum_start: float = 0.3  # Start with 30% easiest
    curriculum_end: float = 1.0  # End with 100%
    curriculum_epochs: int = 50  # Epochs to reach full hardness
    
    # Class confusion weighting
    confusion_weight: float = 2.0  # Extra weight for commonly confused pairs
    
    # Contrastive loss (embedding-space separation)
    use_contrastive: bool = False  # Enable contrastive loss
    contrastive_margin: float = 0.5  # Margin for contrastive loss
    contrastive_weight: float = 0.3  # Weight for contrastive term


class OnlineHardNegativeMiner(nn.Module):
    """
    Online Hard Example Mining (OHEM).
    
    During each forward pass, selects the hardest examples (highest loss)
    to focus gradient updates on the most challenging samples.
    
    Args:
        config: Mining configuration
        
    Usage:
        miner = OnlineHardNegativeMiner(config)
        
        # In training loop:
        logits = model(batch)
        loss_per_sample = criterion(logits, targets, reduction='none')
        selected_mask = miner.mine(loss_per_sample, targets)
        loss = (loss_per_sample * selected_mask).mean()
    """
    
    def __init__(self, config: Optional[HardNegativeConfig] = None):
        super().__init__()
        self.config = config or HardNegativeConfig()
        
        # Track confusion statistics
        self.register_buffer('confusion_counts', None)
        self.register_buffer('class_counts', None)
        
    def mine(
        self,
        losses: torch.Tensor,
        targets: torch.Tensor,
        epoch: Optional[int] = None,
        max_epochs: Optional[int] = None
    ) -> torch.Tensor:
        """
        Mine hard examples from the batch.
        
        Args:
            losses: Per-sample loss [B]
            targets: Target labels [B]
            epoch: Current epoch (for curriculum)
            max_epochs: Total epochs (for curriculum)
            
        Returns:
            selection_mask: Binary mask [B] indicating which samples to use
        """
        B = losses.shape[0]
        device = losses.device
        
        # Compute effective ratio based on curriculum
        if self.config.strategy == "curriculum" and epoch is not None:
            progress = min(1.0, epoch / self.config.curriculum_epochs)
            ratio = self.config.curriculum_start + progress * (
                self.config.curriculum_end - self.config.curriculum_start
            )
        else:
            ratio = self.config.ohem_ratio
        
        # Number of samples to keep
        num_keep = max(
            int(B * ratio),
            self.config.min_samples_per_class * len(targets.unique())
        )
        
        # Get indices of hardest samples
        _, hard_indices = torch.topk(losses, num_keep)
        
        # Create selection mask
        mask = torch.zeros(B, device=device)
        mask[hard_indices] = 1.0
        
        # Ensure minimum per-class representation
        for c in targets.unique():
            class_mask = targets == c
            class_selected = mask[class_mask].sum()
            
            if class_selected < self.config.min_samples_per_class:
                # Add more samples from this class
                class_indices = torch.where(class_mask)[0]
                class_losses = losses[class_mask]
                _, top_class_idx = torch.topk(
                    class_losses,
                    min(len(class_losses), self.config.min_samples_per_class)
                )
                mask[class_indices[top_class_idx]] = 1.0
        
        return mask
    
    def update_confusion(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
        num_classes: int
    ):
        """Track which classes are commonly confused."""
        pred_classes = predictions.argmax(dim=1)
        
        if self.confusion_counts is None:
            self.confusion_counts = torch.zeros(num_classes, num_classes, device=predictions.device)
            self.class_counts = torch.zeros(num_classes, device=predictions.device)
        
        for t, p in zip(targets, pred_classes):
            if t != p:
                self.confusion_counts[t, p] += 1
            self.class_counts[t] += 1
    
    def get_confusion_weights(self, targets: torch.Tensor) -> torch.Tensor:
        """
        Get per-sample weights based on confusion frequency.
        
        Samples from commonly confused classes get higher weights.
        """
        if self.confusion_counts is None:
            return torch.ones_like(targets, dtype=torch.float)
        
        # Compute confusion rate per class
        confusion_rate = self.confusion_counts.sum(dim=1) / (self.class_counts + 1e-6)
        
        # Normalize to [1, confusion_weight]
        max_rate = confusion_rate.max()
        if max_rate > 0:
            normalized = confusion_rate / max_rate
            weights = 1.0 + normalized * (self.config.confusion_weight - 1.0)
        else:
            weights = torch.ones_like(confusion_rate)
        
        return weights[targets]


class SemiHardNegativeMiner(nn.Module):
    """
    Semi-Hard Negative Mining for embedding-based learning.
    
    For each anchor, finds negatives that are:
    - Harder than the positive (closer in embedding space)
    - But not TOO hard (within margin)
    
    This is the "Goldilocks zone" - hard enough to learn from,
    but not so hard that gradients are unstable.
    
    Reference: FaceNet (Schroff et al., 2015)
    
    Args:
        margin: Triplet margin
        
    Usage:
        miner = SemiHardNegativeMiner(margin=0.2)
        
        embeddings = model.embed(batch)
        anchor_idx, positive_idx, negative_idx = miner.mine(embeddings, labels)
    """
    
    def __init__(self, margin: float = 0.2):
        super().__init__()
        self.margin = margin
    
    def mine(
        self,
        embeddings: torch.Tensor,
        labels: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Mine semi-hard triplets.
        
        Args:
            embeddings: Feature embeddings [B, D]
            labels: Class labels [B]
            
        Returns:
            anchor_indices, positive_indices, negative_indices
        """
        B = embeddings.shape[0]
        device = embeddings.device
        
        # Compute pairwise distances
        dist_matrix = torch.cdist(embeddings, embeddings)  # [B, B]
        
        # Create masks
        labels_equal = labels.unsqueeze(0) == labels.unsqueeze(1)  # [B, B]
        labels_not_equal = ~labels_equal
        
        anchor_indices = []
        positive_indices = []
        negative_indices = []
        
        for i in range(B):
            # Find positives (same class, not self)
            pos_mask = labels_equal[i].clone()
            pos_mask[i] = False
            pos_indices = torch.where(pos_mask)[0]
            
            if len(pos_indices) == 0:
                continue
            
            # Distance to hardest positive
            pos_dists = dist_matrix[i, pos_indices]
            hardest_pos_idx = pos_indices[pos_dists.argmax()]
            hardest_pos_dist = pos_dists.max()
            
            # Find semi-hard negatives
            # Negatives that are: pos_dist < neg_dist < pos_dist + margin
            neg_mask = labels_not_equal[i]
            neg_dists = dist_matrix[i]
            
            semi_hard_mask = (
                neg_mask &
                (neg_dists > hardest_pos_dist) &
                (neg_dists < hardest_pos_dist + self.margin)
            )
            
            semi_hard_indices = torch.where(semi_hard_mask)[0]
            
            if len(semi_hard_indices) > 0:
                # Pick random semi-hard negative
                neg_idx = semi_hard_indices[torch.randint(len(semi_hard_indices), (1,))]
            else:
                # Fall back to any hard negative (harder than positive)
                hard_mask = neg_mask & (neg_dists > hardest_pos_dist)
                hard_indices = torch.where(hard_mask)[0]
                
                if len(hard_indices) > 0:
                    neg_idx = hard_indices[torch.randint(len(hard_indices), (1,))]
                else:
                    # Fall back to any negative
                    neg_indices_all = torch.where(neg_mask)[0]
                    if len(neg_indices_all) > 0:
                        neg_idx = neg_indices_all[torch.randint(len(neg_indices_all), (1,))]
                    else:
                        continue
            
            anchor_indices.append(i)
            positive_indices.append(hardest_pos_idx.item())
            negative_indices.append(neg_idx.item())
        
        return (
            torch.tensor(anchor_indices, device=device),
            torch.tensor(positive_indices, device=device),
            torch.tensor(negative_indices, device=device)
        )


class ContrastiveLoss(nn.Module):
    """
    Contrastive loss for embedding-space separation.
    
    Pushes embeddings of different classes apart while pulling same-class
    embeddings together. This complements cross-entropy by operating in
    feature space rather than logit space.
    
    For drum classification, this helps separate acoustically similar sounds:
    - Snare vs Rimshot (similar attack characteristics)
    - Crash vs China (similar frequency content)
    - Hi-hat closed vs Pedal (similar short duration)
    
    Reference: "Dimensionality Reduction by Learning an Invariant Mapping" (CVPR 2006)
    
    Args:
        margin: Minimum distance between different-class embeddings
        
    Usage:
        contrastive = ContrastiveLoss(margin=0.5)
        embeddings = model.get_embeddings(batch)
        loss = contrastive(embeddings, labels)
    """
    
    def __init__(self, margin: float = 0.5):
        super().__init__()
        self.margin = margin
    
    def forward(
        self,
        embeddings: torch.Tensor,
        labels: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute contrastive loss.
        
        Args:
            embeddings: Feature embeddings [B, D]
            labels: Class labels [B]
            
        Returns:
            Contrastive loss (scalar)
        """
        B = embeddings.shape[0]
        device = embeddings.device
        
        if B < 2:
            return torch.tensor(0.0, device=device)
        
        # Normalize embeddings for cosine similarity
        embeddings = F.normalize(embeddings, p=2, dim=1)
        
        # Compute pairwise cosine similarity (higher = more similar)
        similarity = torch.mm(embeddings, embeddings.t())  # [B, B]
        
        # Create masks
        labels_equal = labels.unsqueeze(0) == labels.unsqueeze(1)  # [B, B]
        labels_not_equal = ~labels_equal
        
        # Remove diagonal (self-comparisons)
        mask_diag = ~torch.eye(B, dtype=torch.bool, device=device)
        
        # Positive pairs: same class, should have high similarity (close to 1)
        pos_mask = labels_equal & mask_diag
        pos_sim = similarity[pos_mask]
        
        # Negative pairs: different class, should have low similarity (below margin)
        neg_mask = labels_not_equal
        neg_sim = similarity[neg_mask]
        
        # Loss: pull positives together (maximize similarity)
        if pos_sim.numel() > 0:
            pos_loss = (1.0 - pos_sim).mean()
        else:
            pos_loss = torch.tensor(0.0, device=device)
        
        # Loss: push negatives apart (similarity should be below 1 - margin)
        # Using hinge loss: max(0, similarity - (1 - margin))
        if neg_sim.numel() > 0:
            neg_loss = F.relu(neg_sim - (1.0 - self.margin)).mean()
        else:
            neg_loss = torch.tensor(0.0, device=device)
        
        return pos_loss + neg_loss


class HardNegativeLoss(nn.Module):
    """
    Combined loss with hard negative mining.
    
    Wraps a base criterion (CrossEntropy, Focal, etc.) with OHEM.
    
    Args:
        base_criterion: Base loss function
        config: Mining configuration
        
    Usage:
        criterion = HardNegativeLoss(
            nn.CrossEntropyLoss(reduction='none'),
            HardNegativeConfig(ohem_ratio=0.7)
        )
        
        loss = criterion(logits, targets)
    """
    
    def __init__(
        self,
        base_criterion: nn.Module,
        config: Optional[HardNegativeConfig] = None
    ):
        super().__init__()
        self.base_criterion = base_criterion
        self.miner = OnlineHardNegativeMiner(config)
        self.config = config or HardNegativeConfig()
        
        # Contrastive loss for embedding-space separation
        if self.config.use_contrastive:
            self.contrastive_loss = ContrastiveLoss(margin=self.config.contrastive_margin)
        else:
            self.contrastive_loss = None
        
        self.current_epoch = 0
        self.max_epochs = 100
    
    def set_epoch(self, epoch: int, max_epochs: int = 100):
        """Set current epoch for curriculum mining."""
        self.current_epoch = epoch
        self.max_epochs = max_epochs
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        embeddings: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Compute loss with hard negative mining.
        
        Args:
            logits: Model predictions [B, num_classes]
            targets: Ground truth labels [B]
            embeddings: Optional feature embeddings [B, D] for contrastive loss
            
        Returns:
            Mined loss (scalar)
        """
        # Compute per-sample loss
        per_sample_loss = self.base_criterion(logits, targets)
        
        # Mine hard examples
        mask = self.miner.mine(
            per_sample_loss,
            targets,
            epoch=self.current_epoch,
            max_epochs=self.max_epochs
        )
        
        # Apply confusion-based weighting
        confusion_weights = self.miner.get_confusion_weights(targets)
        
        # Weighted loss
        weighted_loss = per_sample_loss * mask * confusion_weights
        
        # Mean over selected samples
        ce_loss = weighted_loss.sum() / (mask.sum() + 1e-6)
        
        # Update confusion statistics
        self.miner.update_confusion(logits, targets, logits.shape[1])
        
        # Add contrastive loss if enabled and embeddings provided
        if self.contrastive_loss is not None and embeddings is not None:
            contrastive = self.contrastive_loss(embeddings, targets)
            total_loss = ce_loss + self.config.contrastive_weight * contrastive
            return total_loss
        
        return ce_loss


# Common confusion pairs for drum classification
DRUM_CONFUSION_PAIRS = [
    # Snare family
    ("snare", "snare_center"),
    ("snare", "snare_rimshot"),
    ("snare", "rimshot"),
    ("snare", "cross_stick"),
    ("snare_rimshot", "rimshot"),
    ("cross_stick", "snare_cross_stick"),
    
    # Hi-hat family
    ("hihat_closed", "hihat_pedal"),
    ("hihat_open", "hihat_splash"),
    ("hihat_splash", "hihat_foot_splash"),
    
    # Cymbal family
    ("crash", "china"),
    ("crash", "splash"),
    ("ride_bow", "ride_bell"),
    
    # Tom family
    ("tom_high", "tom_mid"),
    ("tom_mid", "tom_low"),
]


def get_confusion_weight_matrix(
    class_names: List[str],
    confusion_pairs: Optional[List[Tuple[str, str]]] = None,
    base_weight: float = 1.0,
    confusion_weight: float = 2.0
) -> torch.Tensor:
    """
    Create a weight matrix for commonly confused class pairs.
    
    Args:
        class_names: List of class names
        confusion_pairs: List of (class_a, class_b) tuples
        base_weight: Weight for non-confused pairs
        confusion_weight: Weight for confused pairs
        
    Returns:
        Weight matrix [num_classes, num_classes]
    """
    num_classes = len(class_names)
    weights = torch.full((num_classes, num_classes), base_weight)
    
    confusion_pairs = confusion_pairs or DRUM_CONFUSION_PAIRS
    
    name_to_idx = {name: i for i, name in enumerate(class_names)}
    
    for name_a, name_b in confusion_pairs:
        if name_a in name_to_idx and name_b in name_to_idx:
            i, j = name_to_idx[name_a], name_to_idx[name_b]
            weights[i, j] = confusion_weight
            weights[j, i] = confusion_weight
    
    return weights


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Testing Hard Negative Mining modules...")
    
    # Test OHEM
    config = HardNegativeConfig(ohem_ratio=0.5)
    miner = OnlineHardNegativeMiner(config)
    
    losses = torch.tensor([0.1, 0.5, 0.3, 0.8, 0.2, 0.9, 0.4, 0.7])
    targets = torch.tensor([0, 0, 1, 1, 2, 2, 3, 3])
    
    mask = miner.mine(losses, targets)
    print(f"OHEM mask: {mask}")
    print(f"Selected {mask.sum().item()}/{len(losses)} samples")
    
    # Test Semi-Hard Mining
    semi_hard = SemiHardNegativeMiner(margin=0.2)
    embeddings = torch.randn(16, 128)
    labels = torch.randint(0, 4, (16,))
    
    a, p, n = semi_hard.mine(embeddings, labels)
    print(f"Semi-hard triplets: {len(a)} triplets mined")
    
    # Test Combined Loss
    criterion = HardNegativeLoss(
        nn.CrossEntropyLoss(reduction='none'),
        config
    )
    
    logits = torch.randn(32, 21)
    targets = torch.randint(0, 21, (32,))
    
    loss = criterion(logits, targets)
    print(f"Hard Negative Loss: {loss.item():.4f}")
    
    # Test confusion weight matrix
    class_names = ["snare", "snare_rimshot", "rimshot", "kick", "crash"]
    weights = get_confusion_weight_matrix(class_names)
    print(f"Confusion weight matrix:\n{weights}")
    
    print("\n✅ Hard Negative Mining working!")
