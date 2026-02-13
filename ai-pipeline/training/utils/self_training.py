"""
Self-Training Pipeline for Drum Classification

Self-training (also known as pseudo-labeling) is a semi-supervised learning technique
that uses a trained model's confident predictions on unlabeled data to expand the
training dataset. This creates a virtuous cycle:

    Labeled Data → Train Model → Predict Unlabeled → Add High-Confidence → Retrain

Key Benefits:
- Leverages large amounts of unlabeled audio (YouTube, personal recordings, etc.)
- 1-3% accuracy improvement typical when unlabeled data is abundant
- Particularly effective for rare drum classes that are underrepresented
- Can discover new variations of drum sounds the model hasn't seen

Safety Mechanisms:
- Confidence thresholding to avoid noise amplification
- Agreement filtering with ensemble models
- Class-balanced pseudo-labeling to avoid majority class domination
- Curriculum-based addition (add easiest samples first)

References:
- "Pseudo-Label: The Simple and Efficient Semi-Supervised Learning Method" (Lee, 2013)
- "Self-Training with Noisy Student improves ImageNet classification" (Xie et al., 2020)
- "FixMatch: Simplifying Semi-Supervised Learning with Consistency and Confidence" (2020)

Usage:
    from training.utils.self_training import SelfTrainingPipeline, PseudoLabelDataset
    
    # Initialize with trained teacher model
    pipeline = SelfTrainingPipeline(
        teacher_model=best_model,
        unlabeled_dataloader=unlabeled_loader,
        confidence_threshold=0.95,
        max_samples_per_class=5000,
    )
    
    # Generate pseudo-labels for unlabeled data
    pseudo_labels = pipeline.generate_pseudo_labels()
    
    # Create combined dataset
    combined_dataset = pipeline.create_combined_dataset(
        labeled_dataset=train_dataset,
        pseudo_weight=0.5,  # Weight pseudo-labeled samples at 50%
    )
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, ConcatDataset, WeightedRandomSampler
from tqdm import tqdm

logger = logging.getLogger(__name__)


@dataclass
class PseudoLabel:
    """A single pseudo-labeled sample."""
    sample_id: str
    features: torch.Tensor
    predicted_class: int
    confidence: float
    uncertainty: float = 0.0
    agreement: float = 1.0  # Agreement among ensemble models (if applicable)
    iteration: int = 0  # Which self-training iteration this was added
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "predicted_class": self.predicted_class,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "agreement": self.agreement,
            "iteration": self.iteration,
        }


@dataclass
class SelfTrainingConfig:
    """Configuration for self-training pipeline."""
    
    # Confidence filtering
    confidence_threshold: float = 0.95
    min_confidence_per_class: Dict[int, float] = field(default_factory=dict)
    
    # Class balancing
    max_samples_per_class: int = 10000
    min_samples_per_class: int = 100
    balance_strategy: str = "sqrt"  # "none", "uniform", "sqrt", "log"
    
    # Uncertainty filtering (if ensemble available)
    max_uncertainty: float = 0.1
    min_agreement: float = 0.8
    
    # Curriculum (add samples gradually)
    use_curriculum: bool = True
    curriculum_start_threshold: float = 0.99
    curriculum_end_threshold: float = 0.90
    
    # Quality control
    use_ensemble_filtering: bool = True
    ensemble_agreement_threshold: float = 0.8
    
    # Training dynamics
    pseudo_weight: float = 0.5  # Weight for pseudo-labeled samples in loss
    num_iterations: int = 3  # Number of self-training rounds
    
    # Output
    save_pseudo_labels: bool = True
    output_dir: Optional[Path] = None


class PseudoLabelDataset(Dataset):
    """
    Dataset wrapper for pseudo-labeled samples.
    
    Applies sample weights based on confidence and allows for
    dynamic curriculum-based filtering.
    """
    
    def __init__(
        self,
        pseudo_labels: List[PseudoLabel],
        transform: Optional[Callable] = None,
        weight_by_confidence: bool = True,
        curriculum_progress: float = 1.0,  # 0.0 = only most confident, 1.0 = all
    ):
        self.pseudo_labels = pseudo_labels
        self.transform = transform
        self.weight_by_confidence = weight_by_confidence
        self.curriculum_progress = curriculum_progress
        
        # Filter by curriculum progress
        self._filtered_indices = self._apply_curriculum_filter()
        
        # Compute sample weights
        self.sample_weights = self._compute_weights()
    
    def _apply_curriculum_filter(self) -> List[int]:
        """Filter samples based on curriculum progress."""
        if self.curriculum_progress >= 1.0:
            return list(range(len(self.pseudo_labels)))
        
        # Sort by confidence descending
        sorted_indices = sorted(
            range(len(self.pseudo_labels)),
            key=lambda i: self.pseudo_labels[i].confidence,
            reverse=True
        )
        
        # Take top fraction
        num_to_keep = max(1, int(len(sorted_indices) * self.curriculum_progress))
        return sorted_indices[:num_to_keep]
    
    def _compute_weights(self) -> torch.Tensor:
        """Compute per-sample weights based on confidence."""
        weights = []
        for idx in self._filtered_indices:
            pl = self.pseudo_labels[idx]
            if self.weight_by_confidence:
                # Higher confidence = higher weight
                # Also factor in agreement if available
                weight = pl.confidence * pl.agreement * (1.0 - pl.uncertainty)
            else:
                weight = 1.0
            weights.append(weight)
        
        return torch.tensor(weights, dtype=torch.float32)
    
    def __len__(self) -> int:
        return len(self._filtered_indices)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int, float]:
        actual_idx = self._filtered_indices[idx]
        pl = self.pseudo_labels[actual_idx]
        
        features = pl.features
        if self.transform is not None:
            features = self.transform(features)
        
        return features, pl.predicted_class, self.sample_weights[idx].item()
    
    def get_class_distribution(self) -> Dict[int, int]:
        """Get class distribution of pseudo-labels."""
        distribution = defaultdict(int)
        for idx in self._filtered_indices:
            pl = self.pseudo_labels[idx]
            distribution[pl.predicted_class] += 1
        return dict(distribution)


class SelfTrainingPipeline:
    """
    Complete self-training pipeline for drum classification.
    
    Implements the Noisy Student training approach:
    1. Train initial "teacher" model on labeled data
    2. Generate pseudo-labels for unlabeled data using teacher
    3. Train new "student" model on combined labeled + pseudo-labeled data
    4. Student becomes new teacher; repeat
    
    With proper noise injection (augmentation, dropout), each generation
    of students typically outperforms the teacher.
    """
    
    def __init__(
        self,
        teacher_model: nn.Module,
        config: Optional[SelfTrainingConfig] = None,
        device: Optional[str] = None,
        class_names: Optional[List[str]] = None,
    ):
        self.teacher_model = teacher_model
        self.config = config or SelfTrainingConfig()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.class_names = class_names
        
        # Move model to device
        self.teacher_model.to(self.device)
        self.teacher_model.eval()
        
        # Track statistics
        self.stats = {
            "total_unlabeled": 0,
            "total_pseudo_labeled": 0,
            "per_class_counts": defaultdict(int),
            "confidence_distribution": [],
            "iterations": [],
        }
    
    @torch.no_grad()
    def generate_pseudo_labels(
        self,
        unlabeled_dataloader: DataLoader,
        ensemble_models: Optional[List[nn.Module]] = None,
        progress_bar: bool = True,
    ) -> List[PseudoLabel]:
        """
        Generate pseudo-labels for unlabeled data.
        
        Args:
            unlabeled_dataloader: DataLoader yielding (features, sample_ids)
            ensemble_models: Optional list of additional models for agreement filtering
            progress_bar: Whether to show progress
            
        Returns:
            List of PseudoLabel objects passing the confidence threshold
        """
        self.teacher_model.eval()
        pseudo_labels = []
        
        # Prepare ensemble if provided
        if ensemble_models:
            for model in ensemble_models:
                model.to(self.device)
                model.eval()
        
        iterator = tqdm(
            unlabeled_dataloader,
            desc="Generating pseudo-labels",
            disable=not progress_bar
        )
        
        for batch in iterator:
            if len(batch) == 2:
                features, sample_ids = batch
            else:
                features = batch[0]
                sample_ids = [f"sample_{i}" for i in range(len(features))]
            
            features = features.to(self.device)
            
            # Get teacher predictions
            logits = self.teacher_model(features)
            probs = F.softmax(logits, dim=-1)
            confidences, predictions = probs.max(dim=-1)
            
            # Get ensemble predictions if available
            if ensemble_models:
                all_probs = [probs]
                for model in ensemble_models:
                    model_logits = model(features)
                    all_probs.append(F.softmax(model_logits, dim=-1))
                
                stacked = torch.stack(all_probs, dim=0)
                mean_probs = stacked.mean(dim=0)
                std_probs = stacked.std(dim=0)
                
                # Recalculate confidence from ensemble mean
                confidences, predictions = mean_probs.max(dim=-1)
                
                # Uncertainty = mean std across classes
                uncertainties = std_probs.mean(dim=-1)
                
                # Agreement = fraction of models agreeing with ensemble prediction
                all_preds = torch.stack([p.argmax(dim=-1) for p in all_probs], dim=0)
                agreements = (all_preds == predictions.unsqueeze(0)).float().mean(dim=0)
            else:
                uncertainties = torch.zeros_like(confidences)
                agreements = torch.ones_like(confidences)
            
            # Filter by thresholds and add to pseudo-labels
            for i in range(len(features)):
                sample_id = sample_ids[i] if isinstance(sample_ids[i], str) else f"sample_{sample_ids[i]}"
                confidence = confidences[i].item()
                predicted_class = predictions[i].item()
                uncertainty = uncertainties[i].item()
                agreement = agreements[i].item()
                
                # Check confidence threshold (per-class if specified)
                threshold = self.config.min_confidence_per_class.get(
                    predicted_class, 
                    self.config.confidence_threshold
                )
                
                if confidence < threshold:
                    continue
                
                # Check uncertainty and agreement thresholds
                if self.config.use_ensemble_filtering:
                    if uncertainty > self.config.max_uncertainty:
                        continue
                    if agreement < self.config.min_agreement:
                        continue
                
                # Create pseudo-label
                pl = PseudoLabel(
                    sample_id=sample_id,
                    features=features[i].cpu(),
                    predicted_class=predicted_class,
                    confidence=confidence,
                    uncertainty=uncertainty,
                    agreement=agreement,
                )
                pseudo_labels.append(pl)
                self.stats["per_class_counts"][predicted_class] += 1
                self.stats["confidence_distribution"].append(confidence)
        
        self.stats["total_unlabeled"] = len(unlabeled_dataloader.dataset)
        self.stats["total_pseudo_labeled"] = len(pseudo_labels)
        
        logger.info(
            f"Generated {len(pseudo_labels)} pseudo-labels from "
            f"{self.stats['total_unlabeled']} unlabeled samples "
            f"({100*len(pseudo_labels)/self.stats['total_unlabeled']:.1f}%)"
        )
        
        # Apply class balancing
        pseudo_labels = self._balance_classes(pseudo_labels)
        
        return pseudo_labels
    
    def _balance_classes(self, pseudo_labels: List[PseudoLabel]) -> List[PseudoLabel]:
        """Balance pseudo-labels across classes to prevent majority class domination."""
        if self.config.balance_strategy == "none":
            return pseudo_labels
        
        # Group by class
        by_class: Dict[int, List[PseudoLabel]] = defaultdict(list)
        for pl in pseudo_labels:
            by_class[pl.predicted_class].append(pl)
        
        # Sort each class by confidence (highest first)
        for cls in by_class:
            by_class[cls].sort(key=lambda x: x.confidence, reverse=True)
        
        # Determine target count per class
        class_counts = {cls: len(pls) for cls, pls in by_class.items()}
        
        if self.config.balance_strategy == "uniform":
            # Each class gets same number (up to max)
            target = min(
                self.config.max_samples_per_class,
                max(class_counts.values()) if class_counts else 0
            )
            targets = {cls: min(target, count) for cls, count in class_counts.items()}
        
        elif self.config.balance_strategy == "sqrt":
            # Square root balancing - reduces imbalance while preserving some structure
            max_count = max(class_counts.values()) if class_counts else 0
            targets = {}
            for cls, count in class_counts.items():
                sqrt_target = int(np.sqrt(count) * np.sqrt(max_count))
                targets[cls] = min(
                    self.config.max_samples_per_class,
                    max(self.config.min_samples_per_class, sqrt_target)
                )
        
        elif self.config.balance_strategy == "log":
            # Logarithmic balancing - even more aggressive balancing
            max_count = max(class_counts.values()) if class_counts else 0
            targets = {}
            for cls, count in class_counts.items():
                if count > 0:
                    log_target = int(np.log1p(count) * np.log1p(max_count))
                    targets[cls] = min(
                        self.config.max_samples_per_class,
                        max(self.config.min_samples_per_class, log_target)
                    )
                else:
                    targets[cls] = 0
        else:
            targets = {cls: min(self.config.max_samples_per_class, count) 
                      for cls, count in class_counts.items()}
        
        # Sample from each class
        balanced = []
        for cls, pls in by_class.items():
            n = min(targets.get(cls, len(pls)), len(pls))
            balanced.extend(pls[:n])  # Already sorted by confidence
        
        logger.info(
            f"Balanced pseudo-labels: {len(pseudo_labels)} → {len(balanced)} "
            f"(strategy: {self.config.balance_strategy})"
        )
        
        return balanced
    
    def create_combined_dataset(
        self,
        labeled_dataset: Dataset,
        pseudo_labels: List[PseudoLabel],
        pseudo_weight: Optional[float] = None,
        curriculum_progress: float = 1.0,
    ) -> Dataset:
        """
        Create a combined dataset of labeled and pseudo-labeled samples.
        
        Args:
            labeled_dataset: Original labeled training dataset
            pseudo_labels: Generated pseudo-labels
            pseudo_weight: Weight for pseudo-labeled samples (default from config)
            curriculum_progress: 0.0 to 1.0, controls how many pseudo-labels to include
            
        Returns:
            Combined dataset ready for training
        """
        pseudo_weight = pseudo_weight or self.config.pseudo_weight
        
        # Create pseudo-label dataset
        pseudo_dataset = PseudoLabelDataset(
            pseudo_labels=pseudo_labels,
            weight_by_confidence=True,
            curriculum_progress=curriculum_progress,
        )
        
        # Wrap labeled dataset to include weights
        class WeightedLabeledDataset(Dataset):
            def __init__(self, dataset):
                self.dataset = dataset
            
            def __len__(self):
                return len(self.dataset)
            
            def __getitem__(self, idx):
                item = self.dataset[idx]
                if len(item) == 2:
                    features, label = item
                else:
                    features, label = item[0], item[1]
                return features, label, 1.0  # Full weight for labeled samples
        
        labeled_wrapped = WeightedLabeledDataset(labeled_dataset)
        
        # Combine datasets
        combined = ConcatDataset([labeled_wrapped, pseudo_dataset])
        
        logger.info(
            f"Combined dataset: {len(labeled_dataset)} labeled + "
            f"{len(pseudo_dataset)} pseudo-labeled = {len(combined)} total"
        )
        
        return combined
    
    def create_weighted_sampler(
        self,
        combined_dataset: Dataset,
        labeled_size: int,
        pseudo_size: int,
        labeled_ratio: float = 0.5,
    ) -> WeightedRandomSampler:
        """
        Create a sampler that maintains a balance between labeled and pseudo-labeled.
        
        Args:
            combined_dataset: The combined dataset
            labeled_size: Number of labeled samples
            pseudo_size: Number of pseudo-labeled samples
            labeled_ratio: Target ratio of labeled samples per batch
            
        Returns:
            WeightedRandomSampler for the DataLoader
        """
        # Calculate sampling weights
        labeled_weight = labeled_ratio / labeled_size if labeled_size > 0 else 0
        pseudo_weight = (1 - labeled_ratio) / pseudo_size if pseudo_size > 0 else 0
        
        weights = [labeled_weight] * labeled_size + [pseudo_weight] * pseudo_size
        
        sampler = WeightedRandomSampler(
            weights=weights,
            num_samples=len(weights),
            replacement=True
        )
        
        return sampler
    
    def run_iteration(
        self,
        unlabeled_dataloader: DataLoader,
        labeled_dataset: Dataset,
        train_fn: Callable,
        iteration: int = 0,
        ensemble_models: Optional[List[nn.Module]] = None,
    ) -> Tuple[nn.Module, Dict[str, Any]]:
        """
        Run one iteration of self-training.
        
        Args:
            unlabeled_dataloader: DataLoader for unlabeled data
            labeled_dataset: Original labeled dataset
            train_fn: Function to train a model, signature: (dataset) -> model
            iteration: Current iteration number
            ensemble_models: Optional ensemble for filtering
            
        Returns:
            Tuple of (trained model, iteration statistics)
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Self-Training Iteration {iteration + 1}/{self.config.num_iterations}")
        logger.info(f"{'='*60}\n")
        
        # Generate pseudo-labels
        pseudo_labels = self.generate_pseudo_labels(
            unlabeled_dataloader,
            ensemble_models=ensemble_models,
        )
        
        # Mark iteration
        for pl in pseudo_labels:
            pl.iteration = iteration
        
        # Calculate curriculum progress (ramp up over iterations)
        if self.config.use_curriculum:
            progress = (iteration + 1) / self.config.num_iterations
        else:
            progress = 1.0
        
        # Create combined dataset
        combined = self.create_combined_dataset(
            labeled_dataset=labeled_dataset,
            pseudo_labels=pseudo_labels,
            curriculum_progress=progress,
        )
        
        # Train new model
        logger.info("Training student model on combined dataset...")
        student_model = train_fn(combined)
        
        # Collect stats
        iteration_stats = {
            "iteration": iteration,
            "num_pseudo_labels": len(pseudo_labels),
            "combined_dataset_size": len(combined),
            "curriculum_progress": progress,
            "class_distribution": dict(self.stats["per_class_counts"]),
        }
        self.stats["iterations"].append(iteration_stats)
        
        # Save pseudo-labels if requested
        if self.config.save_pseudo_labels and self.config.output_dir:
            self._save_pseudo_labels(pseudo_labels, iteration)
        
        # Update teacher for next iteration
        self.teacher_model = student_model
        
        return student_model, iteration_stats
    
    def run_full_pipeline(
        self,
        unlabeled_dataloader: DataLoader,
        labeled_dataset: Dataset,
        train_fn: Callable,
        ensemble_models: Optional[List[nn.Module]] = None,
    ) -> Tuple[nn.Module, List[Dict[str, Any]]]:
        """
        Run the complete self-training pipeline for all iterations.
        
        Args:
            unlabeled_dataloader: DataLoader for unlabeled data
            labeled_dataset: Original labeled dataset
            train_fn: Training function
            ensemble_models: Optional ensemble for filtering
            
        Returns:
            Tuple of (final model, list of iteration statistics)
        """
        all_stats = []
        
        for iteration in range(self.config.num_iterations):
            model, stats = self.run_iteration(
                unlabeled_dataloader=unlabeled_dataloader,
                labeled_dataset=labeled_dataset,
                train_fn=train_fn,
                iteration=iteration,
                ensemble_models=ensemble_models,
            )
            all_stats.append(stats)
        
        return model, all_stats
    
    def _save_pseudo_labels(self, pseudo_labels: List[PseudoLabel], iteration: int):
        """Save pseudo-labels to disk."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"pseudo_labels_iter_{iteration}.json"
        
        data = {
            "iteration": iteration,
            "num_samples": len(pseudo_labels),
            "labels": [pl.to_dict() for pl in pseudo_labels],
            "class_distribution": dict(self.stats["per_class_counts"]),
        }
        
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved pseudo-labels to {output_file}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the self-training process."""
        return {
            "total_unlabeled_processed": self.stats["total_unlabeled"],
            "total_pseudo_labeled": self.stats["total_pseudo_labeled"],
            "acceptance_rate": (
                self.stats["total_pseudo_labeled"] / max(1, self.stats["total_unlabeled"])
            ),
            "class_distribution": dict(self.stats["per_class_counts"]),
            "confidence_stats": {
                "mean": np.mean(self.stats["confidence_distribution"]) if self.stats["confidence_distribution"] else 0,
                "std": np.std(self.stats["confidence_distribution"]) if self.stats["confidence_distribution"] else 0,
                "min": min(self.stats["confidence_distribution"]) if self.stats["confidence_distribution"] else 0,
                "max": max(self.stats["confidence_distribution"]) if self.stats["confidence_distribution"] else 0,
            },
            "iterations": self.stats["iterations"],
        }


class NoisyStudentTraining(SelfTrainingPipeline):
    """
    Noisy Student Training variant with enhanced noise injection.
    
    Key differences from standard self-training:
    - Stronger augmentation on student than teacher
    - Student model can be same size or larger
    - Multiple noise types: input noise, model noise (dropout), data noise
    
    Reference: "Self-Training with Noisy Student improves ImageNet classification" (2020)
    """
    
    def __init__(
        self,
        teacher_model: nn.Module,
        student_augmentation: Optional[Callable] = None,
        teacher_augmentation: Optional[Callable] = None,
        noise_magnitude: float = 0.1,
        **kwargs
    ):
        super().__init__(teacher_model, **kwargs)
        self.student_augmentation = student_augmentation
        self.teacher_augmentation = teacher_augmentation
        self.noise_magnitude = noise_magnitude
    
    @torch.no_grad()
    def generate_pseudo_labels(
        self,
        unlabeled_dataloader: DataLoader,
        ensemble_models: Optional[List[nn.Module]] = None,
        progress_bar: bool = True,
    ) -> List[PseudoLabel]:
        """Generate pseudo-labels with teacher (no noise / weak augmentation)."""
        # Teacher uses weak or no augmentation
        return super().generate_pseudo_labels(
            unlabeled_dataloader,
            ensemble_models=ensemble_models,
            progress_bar=progress_bar,
        )
    
    def create_combined_dataset(
        self,
        labeled_dataset: Dataset,
        pseudo_labels: List[PseudoLabel],
        pseudo_weight: Optional[float] = None,
        curriculum_progress: float = 1.0,
    ) -> Dataset:
        """Create combined dataset with strong augmentation for student."""
        # Create pseudo-label dataset with student augmentation
        pseudo_dataset = PseudoLabelDataset(
            pseudo_labels=pseudo_labels,
            transform=self.student_augmentation,  # Strong augmentation
            weight_by_confidence=True,
            curriculum_progress=curriculum_progress,
        )
        
        # Wrap labeled dataset with augmentation and weights
        class AugmentedLabeledDataset(Dataset):
            def __init__(self, dataset, transform):
                self.dataset = dataset
                self.transform = transform
            
            def __len__(self):
                return len(self.dataset)
            
            def __getitem__(self, idx):
                item = self.dataset[idx]
                features, label = item[0], item[1]
                if self.transform is not None:
                    features = self.transform(features)
                return features, label, 1.0
        
        labeled_augmented = AugmentedLabeledDataset(
            labeled_dataset, 
            self.student_augmentation
        )
        
        combined = ConcatDataset([labeled_augmented, pseudo_dataset])
        
        return combined


# Convenience function for quick setup
def create_self_training_pipeline(
    model: nn.Module,
    unlabeled_data_path: Union[str, Path],
    confidence_threshold: float = 0.95,
    num_iterations: int = 3,
    output_dir: Optional[Union[str, Path]] = None,
) -> SelfTrainingPipeline:
    """
    Create a self-training pipeline with sensible defaults.
    
    Args:
        model: Trained teacher model
        unlabeled_data_path: Path to unlabeled audio files
        confidence_threshold: Minimum confidence for pseudo-labeling
        num_iterations: Number of self-training rounds
        output_dir: Where to save pseudo-labels
        
    Returns:
        Configured SelfTrainingPipeline
    """
    config = SelfTrainingConfig(
        confidence_threshold=confidence_threshold,
        num_iterations=num_iterations,
        balance_strategy="sqrt",
        use_curriculum=True,
        output_dir=Path(output_dir) if output_dir else None,
    )
    
    return SelfTrainingPipeline(
        teacher_model=model,
        config=config,
    )


if __name__ == "__main__":
    # Demo usage
    print("Self-Training Pipeline for Drum Classification")
    print("=" * 50)
    print()
    print("Usage example:")
    print("""
    from training.utils.self_training import SelfTrainingPipeline, SelfTrainingConfig
    
    # Configure
    config = SelfTrainingConfig(
        confidence_threshold=0.95,
        max_samples_per_class=5000,
        balance_strategy="sqrt",
        num_iterations=3,
    )
    
    # Create pipeline
    pipeline = SelfTrainingPipeline(
        teacher_model=trained_model,
        config=config,
    )
    
    # Run self-training
    final_model, stats = pipeline.run_full_pipeline(
        unlabeled_dataloader=unlabeled_loader,
        labeled_dataset=train_dataset,
        train_fn=train_model_fn,
    )
    
    print(f"Final model trained with {stats[-1]['combined_dataset_size']} samples")
    """)
