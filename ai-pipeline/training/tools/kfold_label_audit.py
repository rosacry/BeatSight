#!/usr/bin/env python3
"""
K-Fold Cross-Validation Label Audit

Enhanced label audit using K-fold cross-validation for more robust noise detection.
Each sample gets evaluated by models trained on different data splits, catching
more mislabeled samples than single-fold evaluation.

Expected improvement: +0.5-1% more noisy labels found compared to single fold.

Usage:
    python kfold_label_audit.py --dataset /path/to/dataset --output /path/to/output
    python kfold_label_audit.py --k 5 --epochs 15 --dataset /path/to/dataset

This script is designed to be run with PYTHONPATH=ai-pipeline.

Reference:
    "Confident Learning: Estimating Uncertainty in Dataset Labels" (Northcutt et al., 2021)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm

logger = logging.getLogger(__name__)


# Import model - matches what train_classifier.py uses
try:
    from transcription.ml_drum_classifier_v2 import DrumClassifierCNNv2
    HAS_V2_MODEL = True
except ImportError:
    HAS_V2_MODEL = False
    DrumClassifierCNNv2 = None  # type: ignore
    logger.warning("DrumClassifierCNNv2 not found - v2 model unavailable")

# Import confident learning utilities
try:
    from training.utils.confident_learning import (
        LabelIssue,
        compute_confident_joint,
        estimate_noise_matrix,
        find_label_issues,
    )
    HAS_CL = True
except ImportError:
    HAS_CL = False
    logger.warning("confident_learning utils not found")


@dataclass
class KFoldAuditConfig:
    """Configuration for K-fold label audit."""
    k: int = 5
    epochs_per_fold: int = 15
    batch_size: int = 256
    lr: float = 0.001
    model_version: str = "v2"
    use_se: bool = True
    device: str = "cuda"
    num_workers: int = 0  # Windows safe
    seed: int = 1337
    amp_dtype: str = "float16"
    noise_threshold: float = 0.5
    min_folds_flagged: int = 2  # Sample must be flagged by at least this many folds


@dataclass
class KFoldAuditResult:
    """Results from K-fold label audit."""
    total_samples: int
    k: int
    issues_per_fold: List[int]
    aggregated_issues: List[LabelIssue]
    multi_fold_issues: List[LabelIssue]  # Flagged by multiple folds
    noise_matrix: np.ndarray
    class_noise_rates: Dict[str, float]
    audit_duration_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "k": self.k,
            "issues_per_fold": self.issues_per_fold,
            "num_aggregated_issues": len(self.aggregated_issues),
            "num_multi_fold_issues": len(self.multi_fold_issues),
            "class_noise_rates": self.class_noise_rates,
            "audit_duration_seconds": self.audit_duration_seconds,
            "issues": [issue.to_dict() for issue in self.multi_fold_issues[:100]],  # Top 100
        }


def create_kfold_splits(
    dataset_size: int,
    k: int,
    seed: int = 1337,
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Create K-fold cross-validation splits.
    
    Returns:
        List of (train_indices, val_indices) tuples
    """
    rng = np.random.RandomState(seed)
    indices = np.arange(dataset_size)
    rng.shuffle(indices)
    
    fold_size = dataset_size // k
    splits = []
    
    for fold_idx in range(k):
        start = fold_idx * fold_size
        end = start + fold_size if fold_idx < k - 1 else dataset_size
        
        val_indices = indices[start:end]
        train_indices = np.concatenate([indices[:start], indices[end:]])
        
        splits.append((train_indices, val_indices))
    
    return splits


def train_fold_model(
    model: nn.Module,
    train_loader: DataLoader,
    config: KFoldAuditConfig,
    fold_idx: int,
) -> nn.Module:
    """Train model for one fold."""
    device = torch.device(config.device)
    model = model.to(device)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.epochs_per_fold
    )
    criterion = nn.CrossEntropyLoss()
    
    # AMP setup
    amp_dtype = torch.float16 if config.amp_dtype == "float16" else torch.bfloat16
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    
    model.train()
    
    for epoch in range(config.epochs_per_fold):
        epoch_loss = 0.0
        correct = 0
        total = 0
        
        pbar = tqdm(train_loader, desc=f"Fold {fold_idx+1}/{config.k} Epoch {epoch+1}/{config.epochs_per_fold}")
        
        for features, labels in pbar:
            features = features.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            
            optimizer.zero_grad()
            
            with torch.amp.autocast("cuda", dtype=amp_dtype):
                outputs = model(features)
                loss = criterion(outputs, labels)
            
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            
            epoch_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            
            pbar.set_postfix({
                "loss": f"{loss.item():.4f}",
                "acc": f"{100.*correct/total:.1f}%"
            })
        
        scheduler.step()
    
    return model


def get_fold_predictions(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    amp_dtype: torch.dtype,
) -> Tuple[np.ndarray, np.ndarray]:
    """Get predictions for validation fold."""
    model.eval()
    
    all_probs = []
    all_labels = []
    
    with torch.no_grad():
        for features, labels in tqdm(val_loader, desc="Getting predictions"):
            features = features.to(device, non_blocking=True)
            
            with torch.amp.autocast("cuda", dtype=amp_dtype):
                outputs = model(features)
                probs = torch.softmax(outputs, dim=1)
            
            all_probs.append(probs.cpu().numpy())
            all_labels.append(labels.numpy())
    
    return np.concatenate(all_probs), np.concatenate(all_labels)


def run_kfold_audit(
    dataset,
    config: KFoldAuditConfig,
    output_dir: Path,
    num_classes: int,
    class_names: Optional[List[str]] = None,
) -> KFoldAuditResult:
    """
    Run K-fold cross-validation label audit.
    
    Each fold:
    1. Train model on K-1 folds
    2. Get predictions on held-out fold
    3. Run confident learning on that fold
    4. Aggregate issues across all folds
    
    Samples flagged by multiple folds are high-confidence label errors.
    
    Args:
        dataset: PyTorch Dataset with features and labels
        config: K-fold audit configuration
        output_dir: Directory to save results
        num_classes: Number of classes (required)
        class_names: Optional list of class names for reporting
    """
    import time
    from transcription.ml_drum_classifier_v2 import DrumClassifierCNNv2
    
    start_time = time.time()
    
    device = torch.device(config.device)
    amp_dtype = torch.float16 if config.amp_dtype == "float16" else torch.bfloat16
    
    # Create K-fold splits
    n_samples = len(dataset)
    splits = create_kfold_splits(n_samples, config.k, config.seed)
    
    logger.info(f"Running {config.k}-fold label audit on {n_samples} samples")
    
    # Track issues per sample (how many folds flagged it)
    sample_flags = defaultdict(list)  # idx -> list of (fold, suggested_label, confidence)
    all_probs = np.zeros((n_samples, num_classes))
    all_labels = np.zeros(n_samples, dtype=np.int64)
    issues_per_fold = []
    
    for fold_idx, (train_indices, val_indices) in enumerate(splits):
        logger.info(f"\n{'='*60}")
        logger.info(f"Fold {fold_idx + 1}/{config.k}: train={len(train_indices)}, val={len(val_indices)}")
        logger.info(f"{'='*60}")
        
        # Create fold datasets
        train_subset = Subset(dataset, train_indices)
        val_subset = Subset(dataset, val_indices)
        
        train_loader = DataLoader(
            train_subset,
            batch_size=config.batch_size,
            shuffle=True,
            num_workers=config.num_workers,
            pin_memory=True,
        )
        val_loader = DataLoader(
            val_subset,
            batch_size=config.batch_size,
            shuffle=False,
            num_workers=config.num_workers,
            pin_memory=True,
        )
        
        # Create fresh model
        model = DrumClassifierCNNv2(
            num_classes=num_classes,
            use_se=config.use_se,
        )
        
        # Train on this fold
        model = train_fold_model(model, train_loader, config, fold_idx)
        
        # Get predictions on validation fold
        fold_probs, fold_labels = get_fold_predictions(model, val_loader, device, amp_dtype)
        
        # Store predictions for aggregation
        for i, global_idx in enumerate(val_indices):
            all_probs[global_idx] = fold_probs[i]
            all_labels[global_idx] = fold_labels[i]
        
        # Find issues in this fold
        fold_issues = find_label_issues(fold_probs, fold_labels)
        issues_per_fold.append(len(fold_issues))
        
        logger.info(f"Fold {fold_idx + 1}: Found {len(fold_issues)} potential issues")
        
        # Track which samples were flagged
        for issue in fold_issues:
            global_idx = val_indices[issue.index]
            sample_flags[global_idx].append({
                "fold": fold_idx,
                "suggested_label": issue.suggested_label,
                "confidence": issue.confidence,
                "given_label_prob": issue.given_label_prob,
                "suggested_label_prob": issue.suggested_label_prob,
            })
        
        # Clear GPU memory
        del model
        torch.cuda.empty_cache()
    
    # Aggregate results
    logger.info(f"\n{'='*60}")
    logger.info("Aggregating K-fold results")
    logger.info(f"{'='*60}")
    
    # Run confident learning on aggregated predictions
    aggregated_issues = find_label_issues(all_probs, all_labels)
    
    # Find multi-fold issues (higher confidence)
    multi_fold_issues = []
    for idx, flags in sample_flags.items():
        if len(flags) >= config.min_folds_flagged:
            # Take the most common suggested label
            suggested_labels = [f["suggested_label"] for f in flags]
            most_common = max(set(suggested_labels), key=suggested_labels.count)
            avg_confidence = np.mean([f["confidence"] for f in flags])
            
            multi_fold_issues.append(LabelIssue(
                index=idx,
                given_label=int(all_labels[idx]),
                suggested_label=most_common,
                confidence=avg_confidence,
                given_label_prob=all_probs[idx, int(all_labels[idx])],
                suggested_label_prob=all_probs[idx, most_common],
            ))
    
    # Sort by confidence
    multi_fold_issues.sort(key=lambda x: x.confidence, reverse=True)
    
    # Compute noise matrix
    noise_matrix = estimate_noise_matrix(all_probs, all_labels)
    
    # Compute per-class noise rates
    class_noise_rates = {}
    for c in range(num_classes):
        class_mask = all_labels == c
        class_count = class_mask.sum()
        if class_count > 0:
            class_issues = sum(1 for issue in multi_fold_issues if issue.given_label == c)
            noise_rate = class_issues / class_count
            class_name = class_names[c] if class_names else str(c)
            class_noise_rates[class_name] = float(noise_rate)
    
    duration = time.time() - start_time
    
    result = KFoldAuditResult(
        total_samples=n_samples,
        k=config.k,
        issues_per_fold=issues_per_fold,
        aggregated_issues=aggregated_issues,
        multi_fold_issues=multi_fold_issues,
        noise_matrix=noise_matrix,
        class_noise_rates=class_noise_rates,
        audit_duration_seconds=duration,
    )
    
    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save full report
    report = result.to_dict()
    report["timestamp"] = datetime.now().isoformat()
    report["config"] = {
        "k": config.k,
        "epochs_per_fold": config.epochs_per_fold,
        "batch_size": config.batch_size,
        "lr": config.lr,
        "noise_threshold": config.noise_threshold,
        "min_folds_flagged": config.min_folds_flagged,
    }
    
    with open(output_dir / "kfold_label_audit.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Save noise matrix
    np.save(output_dir / "kfold_noise_matrix.npy", noise_matrix)
    
    # Save list of issue indices for filtering
    issue_indices = [issue.index for issue in multi_fold_issues]
    with open(output_dir / "kfold_issue_indices.json", "w") as f:
        json.dump(issue_indices, f)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("K-FOLD LABEL AUDIT SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total samples: {n_samples}")
    logger.info(f"K (folds): {config.k}")
    logger.info(f"Issues per fold: {issues_per_fold}")
    logger.info(f"Aggregated issues (single-fold): {len(aggregated_issues)}")
    logger.info(f"Multi-fold issues (≥{config.min_folds_flagged} folds): {len(multi_fold_issues)}")
    logger.info(f"Duration: {duration/60:.1f} minutes")
    logger.info("\nTop 10 noisiest classes:")
    for class_name, rate in sorted(class_noise_rates.items(), key=lambda x: x[1], reverse=True)[:10]:
        logger.info(f"  {class_name}: {rate*100:.2f}%")
    logger.info(f"\nResults saved to: {output_dir}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="K-Fold Cross-Validation Label Audit")
    parser.add_argument("--dataset-dir", type=str, required=True, help="Path to dataset audio directory")
    parser.add_argument("--labels-cache-dir", type=str, required=True, help="Path to labels cache (train_labels.json)")
    parser.add_argument("--feature-cache-dir", type=str, help="Path to feature cache (consolidated)")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument("--n-folds", type=int, default=5, help="Number of folds (K)")
    parser.add_argument("--epochs-per-fold", type=int, default=15, help="Epochs per fold")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--device", type=str, default="cuda", help="Device")
    parser.add_argument("--num-workers", type=int, default=0, help="DataLoader workers")
    parser.add_argument("--seed", type=int, default=1337, help="Random seed")
    parser.add_argument("--min-folds", type=int, default=2, help="Min folds to flag sample")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Import dataset class from train_classifier
    # This avoids duplicating the complex DrumSampleDataset
    from training.train_classifier import DrumSampleDataset
    
    config = KFoldAuditConfig(
        k=args.n_folds,
        epochs_per_fold=args.epochs_per_fold,
        batch_size=args.batch_size,
        lr=args.lr,
        device=args.device,
        num_workers=args.num_workers,
        seed=args.seed,
        min_folds_flagged=args.min_folds,
    )
    
    # Build paths matching what auto_train.sh uses
    dataset_dir = Path(args.dataset_dir)
    labels_cache_dir = Path(args.labels_cache_dir)
    train_labels = labels_cache_dir / "train_labels.json"
    cache_mapping = labels_cache_dir / "train_cache_mapping.npz"
    components_file = dataset_dir / "components.json"
    
    if not train_labels.exists():
        logger.error(f"Labels file not found: {train_labels}")
        sys.exit(1)
    
    if not components_file.exists():
        logger.error(f"Components file not found: {components_file}")
        sys.exit(1)
    
    # Load num_classes from components.json (matching train_classifier.py)
    with open(components_file) as f:
        components_info = json.load(f)
    num_classes = components_info['num_classes']
    class_names = components_info.get('class_names', None)
    
    logger.info(f"Loaded {num_classes} classes from {components_file}")
    
    # Load dataset - matching train_classifier.py's approach
    dataset = DrumSampleDataset(
        data_dir=dataset_dir,
        labels_file=train_labels,
        cache_dir=Path(args.feature_cache_dir) / "train" if args.feature_cache_dir else None,
        cache_mapping=cache_mapping if cache_mapping.exists() else None,
    )
    
    output_dir = Path(args.output_dir)
    
    result = run_kfold_audit(
        dataset,
        config,
        output_dir,
        num_classes=num_classes,
        class_names=class_names,
    )
    
    print("\n✅ K-fold audit complete!")
    print(f"   Multi-fold issues: {len(result.multi_fold_issues)}")
    print(f"   Results: {output_dir / 'kfold_label_audit.json'}")


if __name__ == "__main__":
    main()