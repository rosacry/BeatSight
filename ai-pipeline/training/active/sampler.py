"""
Active Learning for Drum Classification

Active learning intelligently selects the most informative samples
for labeling, reducing annotation cost while maintaining model quality.

Strategies:
1. Uncertainty Sampling - Select samples the model is least confident about
2. Diversity Sampling - Select samples that are most different from each other
3. Query-by-Committee - Select samples where ensemble members disagree
4. Core-set Selection - Select representative samples covering the feature space

Expected benefit: Achieve same accuracy with 30-50% less labeled data

Usage:
    from training.active.sampler import (
        ActiveLearner,
        UncertaintySampler,
        DiversitySampler,
        run_active_learning_cycle,
    )
    
    sampler = UncertaintySampler(model, strategy='entropy')
    selected_indices = sampler.select(pool_data, n_samples=100)
    
    # Human labels these, then retrain
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, Subset

logger = logging.getLogger(__name__)


class ActiveSampler(ABC):
    """Base class for active learning samplers."""
    
    @abstractmethod
    def select(
        self,
        pool_loader: DataLoader,
        n_samples: int,
    ) -> List[int]:
        """
        Select samples from the pool for labeling.
        
        Args:
            pool_loader: DataLoader for unlabeled pool
            n_samples: Number of samples to select
        
        Returns:
            List of indices to label
        """
        pass


class UncertaintySampler(ActiveSampler):
    """
    Uncertainty-based active learning sampler.
    
    Selects samples where the model is most uncertain.
    
    Strategies:
    - 'entropy': Maximum entropy of prediction distribution
    - 'least_confidence': Lowest probability for predicted class
    - 'margin': Smallest margin between top 2 predictions
    - 'variation_ratio': Ratio of samples not predicted as most likely class
    """
    
    def __init__(
        self,
        model: nn.Module,
        device: torch.device,
        strategy: str = 'entropy',
    ):
        self.model = model
        self.device = device
        self.strategy = strategy
    
    def _compute_uncertainty(
        self,
        probs: np.ndarray,
    ) -> np.ndarray:
        """Compute uncertainty scores for each sample."""
        
        if self.strategy == 'entropy':
            # Shannon entropy: -sum(p * log(p))
            entropy = -np.sum(probs * np.log(probs + 1e-10), axis=1)
            return entropy
        
        elif self.strategy == 'least_confidence':
            # 1 - max probability
            return 1 - np.max(probs, axis=1)
        
        elif self.strategy == 'margin':
            # Difference between top 2 probabilities
            sorted_probs = np.sort(probs, axis=1)
            margin = sorted_probs[:, -1] - sorted_probs[:, -2]
            return 1 - margin  # Lower margin = higher uncertainty
        
        elif self.strategy == 'variation_ratio':
            # Ratio of samples not in mode class
            return 1 - np.max(probs, axis=1)
        
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def select(
        self,
        pool_loader: DataLoader,
        n_samples: int,
    ) -> List[int]:
        """Select most uncertain samples."""
        self.model.eval()
        
        all_probs = []
        all_indices = []
        
        with torch.no_grad():
            for batch_idx, batch in enumerate(pool_loader):
                inputs = batch[0].to(self.device)
                
                outputs = self.model(inputs)
                probs = F.softmax(outputs, dim=1).cpu().numpy()
                
                all_probs.append(probs)
                
                # Track original indices
                batch_size = inputs.shape[0]
                start_idx = batch_idx * pool_loader.batch_size
                all_indices.extend(range(start_idx, start_idx + batch_size))
        
        all_probs = np.concatenate(all_probs, axis=0)
        
        # Compute uncertainty scores
        uncertainty = self._compute_uncertainty(all_probs)
        
        # Select top-k most uncertain
        selected_relative = np.argsort(uncertainty)[-n_samples:]
        selected_indices = [all_indices[i] for i in selected_relative]
        
        logger.info(
            f"Selected {len(selected_indices)} samples with "
            f"uncertainty range [{uncertainty[selected_relative[0]]:.4f}, "
            f"{uncertainty[selected_relative[-1]]:.4f}]"
        )
        
        return selected_indices


class DiversitySampler(ActiveSampler):
    """
    Diversity-based active learning sampler.
    
    Selects samples that are maximally diverse (cover different regions
    of the feature space).
    
    Methods:
    - 'kmeans': K-means++ initialization on features
    - 'coreset': Greedy core-set selection (maximum minimum distance)
    """
    
    def __init__(
        self,
        model: nn.Module,
        device: torch.device,
        method: str = 'coreset',
    ):
        self.model = model
        self.device = device
        self.method = method
    
    def _extract_features(
        self,
        pool_loader: DataLoader,
    ) -> Tuple[np.ndarray, List[int]]:
        """Extract feature representations from model."""
        self.model.eval()
        
        all_features = []
        all_indices = []
        
        # Hook to capture features before classifier
        features_captured = []
        
        def hook(module, input, output):
            if isinstance(output, tuple):
                output = output[0]
            if output.dim() == 4:
                output = F.adaptive_avg_pool2d(output, 1).flatten(1)
            elif output.dim() == 3:
                output = output.mean(dim=1)
            features_captured.append(output.detach().cpu())
        
        # Try to find the layer before classifier
        # Common patterns: model.features, model.global_pool, etc.
        hook_layer = None
        for name, module in self.model.named_modules():
            if 'global_pool' in name or 'avgpool' in name:
                hook_layer = module
                break
            if isinstance(module, nn.AdaptiveAvgPool2d):
                hook_layer = module
                break
        
        if hook_layer is None:
            # Fallback: hook the last conv/linear before output
            modules = list(self.model.modules())
            for module in reversed(modules):
                if isinstance(module, (nn.Conv2d, nn.Linear)) and \
                   module != list(self.model.modules())[-1]:
                    hook_layer = module
                    break
        
        if hook_layer is None:
            raise RuntimeError("Could not find appropriate layer for feature extraction")
        
        handle = hook_layer.register_forward_hook(hook)
        
        try:
            with torch.no_grad():
                for batch_idx, batch in enumerate(pool_loader):
                    inputs = batch[0].to(self.device)
                    features_captured.clear()
                    
                    _ = self.model(inputs)
                    
                    if features_captured:
                        all_features.append(features_captured[0])
                    
                    batch_size = inputs.shape[0]
                    start_idx = batch_idx * pool_loader.batch_size
                    all_indices.extend(range(start_idx, start_idx + batch_size))
        finally:
            handle.remove()
        
        all_features = torch.cat(all_features, dim=0).numpy()
        
        return all_features, all_indices
    
    def _coreset_selection(
        self,
        features: np.ndarray,
        n_samples: int,
    ) -> List[int]:
        """Greedy core-set selection (k-center)."""
        n_total = len(features)
        
        # Start with random sample
        selected = [np.random.randint(n_total)]
        
        # Compute distances to selected set
        min_distances = np.full(n_total, np.inf)
        
        for _ in range(n_samples - 1):
            # Update min distances with last selected
            last_selected = selected[-1]
            distances = np.linalg.norm(features - features[last_selected], axis=1)
            min_distances = np.minimum(min_distances, distances)
            
            # Select point with maximum min distance (furthest from current set)
            min_distances[selected] = -1  # Exclude already selected
            next_idx = np.argmax(min_distances)
            selected.append(next_idx)
        
        return selected
    
    def _kmeans_pp_selection(
        self,
        features: np.ndarray,
        n_samples: int,
    ) -> List[int]:
        """K-means++ style selection."""
        n_total = len(features)
        
        # First center: random
        selected = [np.random.randint(n_total)]
        
        for _ in range(n_samples - 1):
            # Compute squared distances to nearest center
            min_sq_distances = np.full(n_total, np.inf)
            for center_idx in selected:
                sq_distances = np.sum((features - features[center_idx]) ** 2, axis=1)
                min_sq_distances = np.minimum(min_sq_distances, sq_distances)
            
            min_sq_distances[selected] = 0  # Exclude selected
            
            # Sample proportional to squared distance
            probs = min_sq_distances / min_sq_distances.sum()
            next_idx = np.random.choice(n_total, p=probs)
            selected.append(next_idx)
        
        return selected
    
    def select(
        self,
        pool_loader: DataLoader,
        n_samples: int,
    ) -> List[int]:
        """Select diverse samples."""
        features, pool_indices = self._extract_features(pool_loader)
        
        if self.method == 'coreset':
            selected_relative = self._coreset_selection(features, n_samples)
        elif self.method == 'kmeans':
            selected_relative = self._kmeans_pp_selection(features, n_samples)
        else:
            raise ValueError(f"Unknown method: {self.method}")
        
        selected_indices = [pool_indices[i] for i in selected_relative]
        
        logger.info(f"Selected {len(selected_indices)} diverse samples")
        
        return selected_indices


class QueryByCommitteeSampler(ActiveSampler):
    """
    Query-by-Committee active learning.
    
    Uses disagreement among ensemble members to select samples.
    Higher disagreement = more informative samples.
    """
    
    def __init__(
        self,
        models: List[nn.Module],
        device: torch.device,
        measure: str = 'vote_entropy',
    ):
        self.models = models
        self.device = device
        self.measure = measure
    
    def _compute_disagreement(
        self,
        predictions: np.ndarray,  # [n_models, n_samples, n_classes]
    ) -> np.ndarray:
        """Compute disagreement scores."""
        
        if self.measure == 'vote_entropy':
            # Entropy of the vote distribution
            votes = np.argmax(predictions, axis=2)  # [n_models, n_samples]
            n_samples = votes.shape[1]
            n_classes = predictions.shape[2]
            
            disagreement = np.zeros(n_samples)
            for i in range(n_samples):
                vote_counts = np.bincount(votes[:, i], minlength=n_classes)
                vote_probs = vote_counts / vote_counts.sum()
                entropy = -np.sum(vote_probs * np.log(vote_probs + 1e-10))
                disagreement[i] = entropy
            
            return disagreement
        
        elif self.measure == 'kl_divergence':
            # Average KL divergence from consensus
            consensus = predictions.mean(axis=0)  # [n_samples, n_classes]
            
            kl_sum = np.zeros(predictions.shape[1])
            for model_pred in predictions:
                kl = np.sum(model_pred * np.log(model_pred / (consensus + 1e-10) + 1e-10), axis=1)
                kl_sum += kl
            
            return kl_sum / len(predictions)
        
        else:
            raise ValueError(f"Unknown measure: {self.measure}")
    
    def select(
        self,
        pool_loader: DataLoader,
        n_samples: int,
    ) -> List[int]:
        """Select samples with highest committee disagreement."""
        
        all_predictions = []
        all_indices = []
        
        for model in self.models:
            model.eval()
        
        with torch.no_grad():
            for batch_idx, batch in enumerate(pool_loader):
                inputs = batch[0].to(self.device)
                
                # Get predictions from all models
                batch_preds = []
                for model in self.models:
                    outputs = model(inputs)
                    probs = F.softmax(outputs, dim=1).cpu().numpy()
                    batch_preds.append(probs)
                
                all_predictions.append(np.stack(batch_preds, axis=0))
                
                batch_size = inputs.shape[0]
                start_idx = batch_idx * pool_loader.batch_size
                all_indices.extend(range(start_idx, start_idx + batch_size))
        
        # [n_models, n_samples, n_classes]
        all_predictions = np.concatenate(all_predictions, axis=1)
        
        disagreement = self._compute_disagreement(all_predictions)
        
        selected_relative = np.argsort(disagreement)[-n_samples:]
        selected_indices = [all_indices[i] for i in selected_relative]
        
        logger.info(
            f"Selected {len(selected_indices)} samples with "
            f"disagreement range [{disagreement[selected_relative[0]]:.4f}, "
            f"{disagreement[selected_relative[-1]]:.4f}]"
        )
        
        return selected_indices


class HybridSampler(ActiveSampler):
    """
    Hybrid sampler combining uncertainty and diversity.
    
    First selects top-k uncertain samples, then diversifies among them.
    """
    
    def __init__(
        self,
        model: nn.Module,
        device: torch.device,
        uncertainty_ratio: float = 2.0,  # Select 2x candidates, then diversify
    ):
        self.uncertainty_sampler = UncertaintySampler(model, device, 'entropy')
        self.diversity_sampler = DiversitySampler(model, device, 'coreset')
        self.uncertainty_ratio = uncertainty_ratio
    
    def select(
        self,
        pool_loader: DataLoader,
        n_samples: int,
    ) -> List[int]:
        """Select samples balancing uncertainty and diversity."""
        
        # First: get 2x uncertain samples
        n_candidates = int(n_samples * self.uncertainty_ratio)
        uncertain_indices = self.uncertainty_sampler.select(pool_loader, n_candidates)
        
        # Create subset loader for diversity selection
        pool_dataset = pool_loader.dataset
        candidate_subset = Subset(pool_dataset, uncertain_indices)
        candidate_loader = DataLoader(
            candidate_subset,
            batch_size=pool_loader.batch_size,
            shuffle=False,
        )
        
        # Select diverse samples from uncertain candidates
        diverse_relative = self.diversity_sampler.select(candidate_loader, n_samples)
        
        # Map back to original indices
        selected_indices = [uncertain_indices[i] for i in diverse_relative]
        
        return selected_indices


@dataclass
class ActiveLearningConfig:
    """Configuration for active learning."""
    strategy: str = 'hybrid'  # 'uncertainty', 'diversity', 'qbc', 'hybrid'
    uncertainty_method: str = 'entropy'
    diversity_method: str = 'coreset'
    samples_per_round: int = 100
    initial_labeled_ratio: float = 0.1
    max_rounds: int = 10


class ActiveLearner:
    """
    Complete active learning pipeline.
    
    Manages the iterative process of:
    1. Train model on labeled data
    2. Select informative samples from pool
    3. Get labels for selected samples
    4. Add to labeled set and repeat
    """
    
    def __init__(
        self,
        model_factory: Callable[[], nn.Module],
        config: ActiveLearningConfig,
        device: torch.device,
    ):
        self.model_factory = model_factory
        self.config = config
        self.device = device
        
        self.labeled_indices: List[int] = []
        self.pool_indices: List[int] = []
        self.round_history: List[Dict[str, Any]] = []
    
    def initialize(
        self,
        dataset: Dataset,
        initial_indices: Optional[List[int]] = None,
    ):
        """Initialize labeled and pool sets."""
        n_total = len(dataset)
        
        if initial_indices is not None:
            self.labeled_indices = list(initial_indices)
        else:
            n_initial = int(n_total * self.config.initial_labeled_ratio)
            self.labeled_indices = list(np.random.permutation(n_total)[:n_initial])
        
        self.pool_indices = [i for i in range(n_total) if i not in set(self.labeled_indices)]
        
        logger.info(
            f"Initialized active learning: {len(self.labeled_indices)} labeled, "
            f"{len(self.pool_indices)} in pool"
        )
    
    def _create_sampler(self, model: nn.Module) -> ActiveSampler:
        """Create sampler based on config."""
        if self.config.strategy == 'uncertainty':
            return UncertaintySampler(
                model, self.device, self.config.uncertainty_method
            )
        elif self.config.strategy == 'diversity':
            return DiversitySampler(
                model, self.device, self.config.diversity_method
            )
        elif self.config.strategy == 'hybrid':
            return HybridSampler(model, self.device)
        else:
            raise ValueError(f"Unknown strategy: {self.config.strategy}")
    
    def run_round(
        self,
        dataset: Dataset,
        train_fn: Callable[[DataLoader], nn.Module],
        batch_size: int = 32,
    ) -> Dict[str, Any]:
        """
        Run one round of active learning.
        
        Args:
            dataset: Full dataset
            train_fn: Function that trains model on DataLoader, returns model
            batch_size: Batch size for training
        
        Returns:
            Round statistics
        """
        # Create labeled subset
        labeled_subset = Subset(dataset, self.labeled_indices)
        labeled_loader = DataLoader(
            labeled_subset,
            batch_size=batch_size,
            shuffle=True,
        )
        
        # Train model
        model = train_fn(labeled_loader)
        model = model.to(self.device)
        
        # Create pool loader
        pool_subset = Subset(dataset, self.pool_indices)
        pool_loader = DataLoader(
            pool_subset,
            batch_size=batch_size,
            shuffle=False,
        )
        
        # Select samples
        sampler = self._create_sampler(model)
        n_select = min(self.config.samples_per_round, len(self.pool_indices))
        
        if n_select > 0:
            selected_relative = sampler.select(pool_loader, n_select)
            selected_indices = [self.pool_indices[i] for i in selected_relative]
            
            # Update sets
            self.labeled_indices.extend(selected_indices)
            self.pool_indices = [i for i in self.pool_indices if i not in set(selected_indices)]
        else:
            selected_indices = []
        
        # Record round info
        round_info = {
            'round': len(self.round_history),
            'labeled_size': len(self.labeled_indices),
            'pool_size': len(self.pool_indices),
            'selected': len(selected_indices),
        }
        self.round_history.append(round_info)
        
        logger.info(
            f"Round {round_info['round']}: labeled={round_info['labeled_size']}, "
            f"pool={round_info['pool_size']}, selected={round_info['selected']}"
        )
        
        return round_info
    
    def get_labeled_subset(self, dataset: Dataset) -> Subset:
        """Get current labeled subset."""
        return Subset(dataset, self.labeled_indices)
    
    def get_pool_subset(self, dataset: Dataset) -> Subset:
        """Get current unlabeled pool."""
        return Subset(dataset, self.pool_indices)
