"""
Curriculum Learning for Drum Classification

Curriculum learning trains models on examples ordered from easy to hard,
mimicking how humans learn. This leads to faster convergence and better
final performance, especially on difficult examples.

Paper: "Curriculum Learning" (Bengio et al., ICML 2009)
       "On The Power of Curriculum Learning in Training Deep Networks" (2020)

How it works:
1. Pre-compute "difficulty" scores for each training sample
2. Early training: Focus on easy examples (high-confidence from a pre-trained model)
3. Mid training: Gradually introduce harder examples
4. Late training: Train on full dataset including hardest cases

Difficulty scoring methods:
1. **Loss-based**: Samples with high loss are "hard"
2. **Confidence-based**: Low-confidence predictions indicate difficulty
3. **Margin-based**: Small gap between top-2 predictions = ambiguous/hard
4. **Human-defined**: Certain classes are inherently harder (ghost notes)

Benefits for drum classification:
- Better handling of ambiguous samples (soft ghost notes, edge cases)
- Faster convergence (learns fundamentals first)
- More stable training with aggressive augmentation
- Improved rare-class performance

Expected improvement: 0.5-1.5% accuracy + faster convergence

Usage:
    from training.utils.curriculum import CurriculumScheduler, compute_difficulty_scores
    
    # Pre-compute difficulty scores
    scores = compute_difficulty_scores(model, train_loader, device)
    
    # Create curriculum scheduler
    curriculum = CurriculumScheduler(
        difficulty_scores=scores,
        total_epochs=100,
        warmup_epochs=10,
        strategy='linear'
    )
    
    # In training loop:
    sampler = curriculum.get_sampler(epoch)
    train_loader = DataLoader(dataset, sampler=sampler)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Sampler, DataLoader
import numpy as np
from typing import Dict, List, Optional, Iterator
from tqdm import tqdm
from pathlib import Path


class DifficultyScorer:
    """
    Computes difficulty scores for training samples.
    
    Multiple scoring methods available:
    - 'loss': Higher loss = harder
    - 'confidence': Lower max probability = harder  
    - 'margin': Smaller gap between top-2 classes = harder
    - 'entropy': Higher entropy = harder (more uncertain)
    """
    
    def __init__(
        self,
        method: str = 'margin',
        temperature: float = 1.0,
    ):
        self.method = method
        self.temperature = temperature
    
    @torch.no_grad()
    def compute_scores(
        self,
        model: nn.Module,
        dataloader: DataLoader,
        device: torch.device,
        criterion: Optional[nn.Module] = None,
    ) -> np.ndarray:
        """
        Compute difficulty scores for all samples in the dataset.
        
        Args:
            model: Trained or partially-trained model
            dataloader: DataLoader for the training set
            device: Device for computation
            criterion: Loss function (required for 'loss' method)
            
        Returns:
            Array of difficulty scores (higher = harder)
        """
        model.eval()
        all_scores = []
        
        for batch_idx, (inputs, labels) in enumerate(tqdm(dataloader, desc="Computing difficulty")):
            inputs = inputs.to(device)
            labels = labels.to(device)
            
            logits = model(inputs)
            
            if self.method == 'loss':
                if criterion is None:
                    criterion = nn.CrossEntropyLoss(reduction='none')
                scores = criterion(logits, labels)
                
            elif self.method == 'confidence':
                probs = F.softmax(logits / self.temperature, dim=-1)
                max_probs = probs.max(dim=-1).values
                scores = 1.0 - max_probs  # Lower confidence = higher difficulty
                
            elif self.method == 'margin':
                probs = F.softmax(logits / self.temperature, dim=-1)
                top2 = probs.topk(2, dim=-1).values
                margin = top2[:, 0] - top2[:, 1]
                scores = 1.0 - margin  # Smaller margin = higher difficulty
                
            elif self.method == 'entropy':
                probs = F.softmax(logits / self.temperature, dim=-1)
                entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1)
                scores = entropy  # Higher entropy = higher difficulty
                
            else:
                raise ValueError(f"Unknown method: {self.method}")
            
            all_scores.append(scores.cpu().numpy())
        
        return np.concatenate(all_scores)
    
    def compute_class_based_scores(
        self,
        labels: List[int],
        hard_classes: List[int],
        medium_classes: List[int],
    ) -> np.ndarray:
        """
        Assign difficulty based on class membership.
        
        Useful when you know certain classes are inherently harder.
        For drums: ghost notes, subtle cymbals, etc.
        """
        scores = np.zeros(len(labels))
        
        for i, label in enumerate(labels):
            if label in hard_classes:
                scores[i] = 0.9  # Hard
            elif label in medium_classes:
                scores[i] = 0.5  # Medium
            else:
                scores[i] = 0.1  # Easy
        
        return scores


class CurriculumSampler(Sampler):
    """
    Sampler that implements curriculum learning by controlling which
    samples are included based on difficulty and training progress.
    """
    
    def __init__(
        self,
        difficulty_scores: np.ndarray,
        data_fraction: float = 1.0,
        sample_weights: Optional[np.ndarray] = None,
    ):
        """
        Args:
            difficulty_scores: Difficulty score for each sample (higher = harder)
            data_fraction: Fraction of data to use (0-1), selected by easiest first
            sample_weights: Optional weights for weighted sampling
        """
        self.difficulty_scores = difficulty_scores
        self.data_fraction = min(1.0, max(0.0, data_fraction))
        self.sample_weights = sample_weights
        
        # Sort indices by difficulty (easiest first)
        self.sorted_indices = np.argsort(difficulty_scores)
        
        # Compute which samples to include
        n_samples = int(len(difficulty_scores) * self.data_fraction)
        self.active_indices = self.sorted_indices[:n_samples]
    
    def __iter__(self) -> Iterator[int]:
        # Shuffle the active indices for each epoch
        perm = np.random.permutation(len(self.active_indices))
        shuffled = self.active_indices[perm]
        return iter(shuffled.tolist())
    
    def __len__(self) -> int:
        return len(self.active_indices)


class CurriculumScheduler:
    """
    Schedules the curriculum progression over training epochs.
    
    Gradually increases the data fraction from easy samples
    to the full dataset.
    """
    
    def __init__(
        self,
        difficulty_scores: np.ndarray,
        total_epochs: int,
        warmup_epochs: int = 5,
        start_fraction: float = 0.3,
        strategy: str = 'linear',
        min_fraction: float = 0.2,
    ):
        """
        Args:
            difficulty_scores: Difficulty score for each sample
            total_epochs: Total training epochs
            warmup_epochs: Epochs before starting curriculum (use full data)
            start_fraction: Initial fraction of easiest samples to use
            strategy: 'linear', 'exponential', 'step', or 'cosine'
            min_fraction: Minimum data fraction to use
        """
        self.difficulty_scores = difficulty_scores
        self.total_epochs = total_epochs
        self.warmup_epochs = warmup_epochs
        self.start_fraction = start_fraction
        self.strategy = strategy
        self.min_fraction = min_fraction
    
    def get_fraction(self, epoch: int) -> float:
        """Get the data fraction for a given epoch."""
        if epoch < self.warmup_epochs:
            return self.start_fraction
        
        # Progress from 0 to 1 over remaining epochs
        progress = (epoch - self.warmup_epochs) / max(1, self.total_epochs - self.warmup_epochs)
        progress = min(1.0, progress)
        
        if self.strategy == 'linear':
            fraction = self.start_fraction + (1.0 - self.start_fraction) * progress
            
        elif self.strategy == 'exponential':
            # Faster ramp-up at the end
            fraction = self.start_fraction + (1.0 - self.start_fraction) * (progress ** 2)
            
        elif self.strategy == 'cosine':
            # Smooth cosine schedule
            fraction = self.start_fraction + (1.0 - self.start_fraction) * (1 - np.cos(progress * np.pi)) / 2
            
        elif self.strategy == 'step':
            # Step-wise increase
            steps = 4
            step_idx = int(progress * steps)
            fraction = self.start_fraction + (1.0 - self.start_fraction) * (step_idx / steps)
            
        else:
            fraction = 1.0
        
        return max(self.min_fraction, min(1.0, fraction))
    
    def step(self, epoch: int) -> None:
        """Update the current epoch (for compatibility with scheduler interface)."""
        self.current_epoch = epoch
    
    def get_current_fraction(self) -> float:
        """Get the data fraction for the current epoch."""
        return self.get_fraction(getattr(self, 'current_epoch', 0))
    
    def get_sample_weights(self, labels: np.ndarray = None) -> np.ndarray:
        """
        Get sample weights for WeightedRandomSampler based on current curriculum fraction.
        
        Samples below the difficulty threshold get higher weights.
        """
        fraction = self.get_current_fraction()
        
        # Handle empty difficulty scores
        if len(self.difficulty_scores) == 0:
            return np.ones(len(labels) if labels is not None else 1)
        
        # Sort samples by difficulty and compute threshold
        sorted_difficulties = np.sort(self.difficulty_scores)
        threshold_idx = int(len(sorted_difficulties) * fraction)
        threshold_idx = min(threshold_idx, len(sorted_difficulties) - 1)
        difficulty_threshold = sorted_difficulties[threshold_idx]
        
        # Samples below threshold get weight 1.0, above get reduced weight
        weights = np.where(
            self.difficulty_scores <= difficulty_threshold,
            1.0,
            0.1  # Reduced but not zero to allow some hard samples
        )
        
        return weights
    
    def get_sampler(self, epoch: int) -> CurriculumSampler:
        """Get the sampler for a given epoch."""
        fraction = self.get_fraction(epoch)
        return CurriculumSampler(
            difficulty_scores=self.difficulty_scores,
            data_fraction=fraction,
        )
    
    def get_schedule_info(self) -> Dict[int, float]:
        """Get the full schedule as a dict mapping epoch -> fraction."""
        return {epoch: self.get_fraction(epoch) for epoch in range(self.total_epochs)}



class AntiCurriculumSampler(CurriculumSampler):
    """
    Anti-curriculum: Start with hard examples, gradually add easy ones.
    
    Sometimes useful for:
    - When easy examples dominate and cause underfitting on hard cases
    - When you want to prioritize rare/hard classes
    """
    
    def __init__(
        self,
        difficulty_scores: np.ndarray,
        data_fraction: float = 1.0,
    ):
        super().__init__(difficulty_scores, data_fraction)
        # Reverse: hardest first
        self.sorted_indices = np.argsort(-difficulty_scores)
        n_samples = int(len(difficulty_scores) * self.data_fraction)
        self.active_indices = self.sorted_indices[:n_samples]


def compute_difficulty_scores(
    model: nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    method: str = 'margin',
    cache_path: Optional[Path] = None,
) -> np.ndarray:
    """
    Convenience function to compute and optionally cache difficulty scores.
    
    Args:
        model: Model to use for scoring
        dataloader: DataLoader for training data
        device: Compute device
        method: Scoring method ('loss', 'confidence', 'margin', 'entropy')
        cache_path: Optional path to cache scores
        
    Returns:
        Array of difficulty scores
    """
    # Check cache
    if cache_path and cache_path.exists():
        print(f"Loading cached difficulty scores from {cache_path}")
        data = np.load(cache_path)
        return data['scores']
    
    # Compute scores
    scorer = DifficultyScorer(method=method)
    scores = scorer.compute_scores(model, dataloader, device)
    
    # Cache if requested
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache_path, scores=scores, method=method)
        print(f"Cached difficulty scores to {cache_path}")
    
    return scores


def get_drum_class_difficulty() -> Dict[str, float]:
    """
    Returns predefined difficulty scores for drum classes based on
    domain knowledge about which sounds are inherently harder to classify.
    
    These scores blend two factors:
    1. **Inherent confusability** - How similar the sound is to other classes
    2. **Rarity in typical datasets** - Rare classes get less training signal
    
    Scale: 0.0 (easiest) to 1.0 (hardest)
    
    Note: These are conservative estimates. Use compute_difficulty_scores()
    with a pre-trained model for empirical difficulty based on actual losses.
    """
    return {
        # Easy - distinctive sounds, common in datasets
        "kick": 0.1,
        "snare": 0.15,
        "snare_center": 0.2,
        "hihat_closed": 0.2,
        "crash": 0.25,
        
        # Medium - some confusion possible, moderately common
        "tom_low": 0.35,
        "tom_mid": 0.4,
        "tom_high": 0.4,
        "hihat_open": 0.4,
        "ride_bow": 0.45,
        "splash": 0.45,
        "china": 0.45,
        
        # Hard - often confused with similar sounds
        "snare_rimshot": 0.55,
        "rimshot": 0.55,
        "ride_bell": 0.55,
        "hihat_pedal": 0.6,
        "hihat_splash": 0.6,
        "cross_stick": 0.65,
        "snare_cross_stick": 0.65,
        
        # Very hard - subtle, rare, or ambiguous
        "hihat_foot_splash": 0.75,
        "aux_percussion": 0.8,
    }


def compute_frequency_adjusted_difficulty(
    labels: List[int],
    class_names: List[str],
    frequency_weight: float = 0.3,
) -> np.ndarray:
    """
    Compute difficulty scores that blend domain knowledge with class frequency.
    
    Rare classes are harder because:
    1. Less training signal available
    2. Often edge cases or unusual techniques
    
    Args:
        labels: List of class indices for each sample
        class_names: List of class names (index -> name mapping)
        frequency_weight: Weight for frequency-based difficulty (0-1)
                         0 = pure domain knowledge, 1 = pure frequency
    
    Returns:
        Per-sample difficulty scores
    """
    from collections import Counter
    
    # Handle empty labels
    if len(labels) == 0:
        print("[CURRICULUM] Warning: Empty labels, returning empty difficulty scores")
        return np.array([])
    
    # Get domain knowledge difficulty
    domain_difficulty = get_drum_class_difficulty()
    
    # Compute class frequencies
    class_counts = Counter(labels)
    total_samples = len(labels)
    
    if not class_counts:
        print("[CURRICULUM] Warning: No class counts, using uniform difficulty")
        return np.full(len(labels), 0.5)
    
    max_count = max(class_counts.values())
    
    # Compute per-sample difficulty
    scores = np.zeros(len(labels))
    
    for i, label in enumerate(labels):
        class_name = class_names[label] if label < len(class_names) else "unknown"
        
        # Domain knowledge difficulty
        domain_score = domain_difficulty.get(class_name, 0.5)
        
        # Frequency-based difficulty (rare = harder)
        # Invert frequency: low frequency -> high difficulty
        freq = class_counts[label] / max_count  # 0 to 1
        freq_score = 1.0 - freq  # Invert: rare (low freq) -> high difficulty
        
        # Blend the two scores
        scores[i] = (1 - frequency_weight) * domain_score + frequency_weight * freq_score
    
    return scores


def create_class_based_curriculum(
    labels: List[int],
    class_names: List[str],
    total_epochs: int,
) -> CurriculumScheduler:
    """
    Create a curriculum scheduler based on predefined class difficulty.
    
    Args:
        labels: List of class indices for each sample
        class_names: List of class names
        total_epochs: Total training epochs
        
    Returns:
        Configured CurriculumScheduler
    """
    class_difficulty = get_drum_class_difficulty()
    
    # Compute per-sample difficulty from class difficulty
    scores = np.array([
        class_difficulty.get(class_names[label], 0.5)
        for label in labels
    ])
    
    return CurriculumScheduler(
        difficulty_scores=scores,
        total_epochs=total_epochs,
        warmup_epochs=max(2, total_epochs // 10),
        start_fraction=0.4,
        strategy='cosine',
    )
