#!/usr/bin/env python3
"""
Per-Class Threshold Tuning for Multi-Label Drum Classifier

After training, find the optimal sigmoid threshold per class using validation data.
Each class may have a different optimal threshold depending on its precision/recall tradeoff.

This script:
1. Loads a trained multi-label model
2. Runs inference on validation set to get probabilities
3. For each class, finds threshold that maximizes F1 (or another metric)
4. Outputs JSON file with per-class thresholds

Usage:
    python tune_thresholds.py \
        --model runs/v5_multilabel/best_model.pt \
        --val-dir "F:/datasets/prod_v5_multilabel/val" \
        --output runs/v5_multilabel/thresholds.json

    # With custom metric
    python tune_thresholds.py \
        --model runs/v5_multilabel/best_model.pt \
        --val-dir "F:/datasets/prod_v5_multilabel/val" \
        --metric precision \
        --output thresholds_high_precision.json

Output JSON format:
{
    "global_threshold": 0.45,
    "per_class_thresholds": {
        "kick": 0.5,
        "snare": 0.45,
        "crash": 0.35,
        ...
    },
    "per_class_metrics": {
        "kick": {"threshold": 0.5, "f1": 0.92, "precision": 0.91, "recall": 0.93},
        ...
    }
}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from multilabel.dataset import (
    CachedMultiLabelDataset,
    MultiLabelDrumDataset,
    DEFAULT_DRUM_COMPONENTS,
)
from multilabel.metrics import (
    compute_all_metrics,
    find_optimal_thresholds,
    micro_f1,
    macro_f1,
    per_class_f1,
)


def load_model(
    model_path: str,
    num_classes: int = 12,
    device: str = "cuda",
) -> nn.Module:
    """Load a trained multi-label model."""
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    # Determine model architecture
    config = checkpoint.get('config', {})
    model_version = config.get('model_version', 'v5')
    v5_size = config.get('v5_size', 'large')
    
    # Create model
    if model_version == 'v5':
        try:
            from models.cnn_v5 import cnn_v5_small, cnn_v5_medium, cnn_v5_large
            
            size_configs = {
                "small": cnn_v5_small,
                "medium": cnn_v5_medium,
                "large": cnn_v5_large,
            }
            config_fn = size_configs.get(v5_size, cnn_v5_large)
            model = config_fn(
                num_classes=num_classes,
                drop_path_rate=0.0,
                use_deep_supervision=False,
                use_multi_task=False,
            )
            print(f"Created V5 {v5_size} model")
        except ImportError as e:
            print(f"Warning: V5 model import failed ({e}), using basic CNN")
            from transcription.ml_drum_classifier import DrumClassifierCNN
            model = DrumClassifierCNN(num_classes=num_classes)
    else:
        from transcription.ml_drum_classifier import DrumClassifierCNN
        model = DrumClassifierCNN(num_classes=num_classes)
    
    # Load weights
    if 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    elif 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    elif 'model' in checkpoint:
        state_dict = checkpoint['model']
    else:
        state_dict = checkpoint
    
    # Handle backbone prefix
    cleaned_state_dict = {}
    for key, value in state_dict.items():
        if key.startswith('backbone.'):
            cleaned_key = key[len('backbone.'):]
        else:
            cleaned_key = key
        cleaned_state_dict[cleaned_key] = value
    
    missing, unexpected = model.load_state_dict(cleaned_state_dict, strict=False)
    if missing:
        print(f"  Missing keys: {len(missing)}")
    if unexpected:
        print(f"  Unexpected keys: {len(unexpected)}")
    
    model = model.to(device)
    model.eval()
    
    return model


def collect_predictions(
    model: nn.Module,
    dataloader: DataLoader,
    device: str = "cuda",
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Collect all predictions and targets from the validation set.
    
    Returns:
        Tuple of (all_logits, all_targets) tensors
    """
    all_logits = []
    all_targets = []
    
    print("Collecting predictions on validation set...")
    
    with torch.inference_mode():
        for features, labels in tqdm(dataloader, desc="Inference"):
            features = features.to(device)
            logits = model(features)
            
            all_logits.append(logits.cpu())
            all_targets.append(labels.cpu())
    
    return torch.cat(all_logits), torch.cat(all_targets)


def tune_thresholds_exhaustive(
    logits: torch.Tensor,
    targets: torch.Tensor,
    class_names: List[str],
    thresholds: Optional[List[float]] = None,
    metric: str = "f1",
) -> Dict[str, Dict[str, Any]]:
    """
    Find optimal threshold per class using exhaustive search.
    
    Args:
        logits: Predicted logits, shape (N, C)
        targets: Ground truth labels, shape (N, C)
        class_names: Names for each class
        thresholds: List of thresholds to try
        metric: Metric to optimize ("f1", "precision", "recall")
    
    Returns:
        Dict with optimal thresholds and metrics per class
    """
    if thresholds is None:
        thresholds = np.arange(0.1, 0.9, 0.025).tolist()
    
    probs = torch.sigmoid(logits)
    num_classes = logits.size(1)
    epsilon = 1e-8
    
    results = {}
    
    for i, class_name in enumerate(class_names):
        best_metric_value = -1.0
        best_threshold = 0.5
        best_metrics = {}
        
        target_i = targets[:, i]
        num_positives = target_i.sum().item()
        num_negatives = len(target_i) - num_positives
        
        for t in thresholds:
            pred_i = (probs[:, i] >= t).float()
            
            tp = (pred_i * target_i).sum().item()
            fp = (pred_i * (1 - target_i)).sum().item()
            fn = ((1 - pred_i) * target_i).sum().item()
            tn = ((1 - pred_i) * (1 - target_i)).sum().item()
            
            precision = tp / (tp + fp + epsilon)
            recall = tp / (tp + fn + epsilon)
            f1 = 2 * precision * recall / (precision + recall + epsilon)
            
            # Select optimization target
            if metric == "f1":
                current_metric = f1
            elif metric == "precision":
                current_metric = precision
            elif metric == "recall":
                current_metric = recall
            elif metric == "balanced":
                # Balance between precision and recall with equal weight
                current_metric = (precision + recall) / 2
            else:
                current_metric = f1
            
            if current_metric > best_metric_value:
                best_metric_value = current_metric
                best_threshold = t
                best_metrics = {
                    "threshold": round(t, 3),
                    "f1": round(f1, 4),
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                    "tp": int(tp),
                    "fp": int(fp),
                    "fn": int(fn),
                    "tn": int(tn),
                    "support": int(num_positives),
                }
        
        results[class_name] = best_metrics
        
        print(
            f"  {class_name:15s}: threshold={best_threshold:.3f} "
            f"F1={best_metrics['f1']:.3f} "
            f"P={best_metrics['precision']:.3f} R={best_metrics['recall']:.3f} "
            f"(support={int(num_positives)})"
        )
    
    return results


def tune_global_threshold(
    logits: torch.Tensor,
    targets: torch.Tensor,
    thresholds: Optional[List[float]] = None,
) -> Tuple[float, float]:
    """
    Find optimal global threshold that maximizes micro F1.
    
    Returns:
        Tuple of (best_threshold, best_f1)
    """
    if thresholds is None:
        thresholds = np.arange(0.1, 0.9, 0.025).tolist()
    
    best_f1 = 0.0
    best_threshold = 0.5
    
    for t in thresholds:
        f1 = micro_f1(logits, targets, threshold=t)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
    
    return best_threshold, best_f1


def main():
    parser = argparse.ArgumentParser(
        description="Tune per-class thresholds for multi-label drum classifier"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to trained model checkpoint",
    )
    parser.add_argument(
        "--val-dir",
        type=str,
        required=True,
        help="Path to validation dataset directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for thresholds JSON",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="f1",
        choices=["f1", "precision", "recall", "balanced"],
        help="Metric to optimize (default: f1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Batch size for inference",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of data loading workers",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Device for inference",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use cached dataset if available",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Feature cache directory",
    )
    parser.add_argument(
        "--components",
        type=str,
        default=None,
        help="Path to components.json (for class names)",
    )
    parser.add_argument(
        "--threshold-step",
        type=float,
        default=0.025,
        help="Step size for threshold search (default: 0.025)",
    )
    
    args = parser.parse_args()
    
    # Validate paths
    if not os.path.exists(args.model):
        print(f"ERROR: Model not found: {args.model}")
        sys.exit(1)
    if not os.path.exists(args.val_dir):
        print(f"ERROR: Validation directory not found: {args.val_dir}")
        sys.exit(1)
    
    # Load class names
    if args.components and os.path.exists(args.components):
        with open(args.components) as f:
            class_names = json.load(f)
    else:
        # Try to load from val_dir
        components_path = Path(args.val_dir).parent / "components.json"
        if components_path.exists():
            with open(components_path) as f:
                comp_data = json.load(f)
                # Handle both dict and list formats
                if isinstance(comp_data, dict) and 'components' in comp_data:
                    class_names = comp_data['components']
                elif isinstance(comp_data, list):
                    class_names = comp_data
                else:
                    class_names = DEFAULT_DRUM_COMPONENTS
        else:
            class_names = DEFAULT_DRUM_COMPONENTS
    
    num_classes = len(class_names)
    print(f"Classes ({num_classes}): {class_names}")
    
    # Load model
    print(f"\nLoading model: {args.model}")
    model = load_model(args.model, num_classes=num_classes, device=args.device)
    
    # Create dataset
    print(f"\nLoading validation dataset: {args.val_dir}")
    
    val_dir = Path(args.val_dir)
    
    if args.use_cache and args.cache_dir:
        # Try to find cache mapping
        cache_mapping = val_dir / "cache_mapping.npz"
        if not cache_mapping.exists():
            cache_mapping = val_dir.parent / "cache_mapping.npz"
        
        dataset = CachedMultiLabelDataset(
            data_dir=val_dir,
            num_classes=num_classes,
            class_names=class_names,
            feature_cache_dir=Path(args.cache_dir),
            cache_mapping_path=cache_mapping if cache_mapping.exists() else None,
            is_multilabel=True,
        )
    else:
        # Find labels file
        labels_file = val_dir / "events.jsonl"
        if not labels_file.exists():
            labels_file = val_dir / "labels.json"
        dataset = MultiLabelDrumDataset(
            data_dir=val_dir,
            labels_file=labels_file,
            num_classes=num_classes,
            class_names=class_names,
        )
    
    print(f"  Samples: {len(dataset)}")
    
    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True,
    )
    
    # Collect predictions
    logits, targets = collect_predictions(model, dataloader, args.device)
    print(f"  Collected {len(logits)} predictions")
    
    # Tune global threshold
    print("\n=== GLOBAL THRESHOLD TUNING ===")
    thresholds = np.arange(0.1, 0.9, args.threshold_step).tolist()
    global_threshold, global_f1 = tune_global_threshold(logits, targets, thresholds)
    print(f"  Best global threshold: {global_threshold:.3f} (micro F1: {global_f1:.4f})")
    
    # Compute baseline metrics at 0.5
    print("\n=== BASELINE METRICS (threshold=0.5) ===")
    baseline_metrics = compute_all_metrics(logits, targets, class_names, threshold=0.5)
    print(f"  Micro F1: {baseline_metrics.micro_f1:.4f}")
    print(f"  Macro F1: {baseline_metrics.macro_f1:.4f}")
    print(f"  Subset Accuracy: {baseline_metrics.subset_accuracy:.4f}")
    
    # Tune per-class thresholds
    print(f"\n=== PER-CLASS THRESHOLD TUNING (optimize: {args.metric}) ===")
    per_class_results = tune_thresholds_exhaustive(
        logits, targets, class_names, thresholds, args.metric
    )
    
    # Compute metrics with tuned thresholds
    print("\n=== TUNED METRICS ===")
    
    # Build per-class threshold dict for evaluation
    per_class_thresholds = {
        name: result["threshold"]
        for name, result in per_class_results.items()
    }
    
    # Compute metrics with per-class thresholds
    probs = torch.sigmoid(logits)
    pred_tuned = torch.zeros_like(probs)
    for i, class_name in enumerate(class_names):
        t = per_class_thresholds.get(class_name, 0.5)
        pred_tuned[:, i] = (probs[:, i] >= t).float()
    
    # Calculate tuned metrics
    tp = (pred_tuned * targets).sum().item()
    fp = (pred_tuned * (1 - targets)).sum().item()
    fn = ((1 - pred_tuned) * targets).sum().item()
    tuned_precision = tp / (tp + fp + 1e-8)
    tuned_recall = tp / (tp + fn + 1e-8)
    tuned_micro_f1 = 2 * tuned_precision * tuned_recall / (tuned_precision + tuned_recall + 1e-8)
    
    # Macro F1
    class_f1s = [per_class_results[cn]["f1"] for cn in class_names]
    tuned_macro_f1 = np.mean(class_f1s)
    
    print(f"  Micro F1: {tuned_micro_f1:.4f} (vs {baseline_metrics.micro_f1:.4f} baseline, "
          f"+{tuned_micro_f1 - baseline_metrics.micro_f1:+.4f})")
    print(f"  Macro F1: {tuned_macro_f1:.4f} (vs {baseline_metrics.macro_f1:.4f} baseline, "
          f"+{tuned_macro_f1 - baseline_metrics.macro_f1:+.4f})")
    
    # Prepare output
    output = {
        "model_path": os.path.abspath(args.model),
        "val_dir": os.path.abspath(args.val_dir),
        "optimization_metric": args.metric,
        "num_samples": len(logits),
        "num_classes": num_classes,
        "class_names": class_names,
        "global_threshold": round(global_threshold, 3),
        "global_micro_f1": round(global_f1, 4),
        "per_class_thresholds": per_class_thresholds,
        "per_class_metrics": per_class_results,
        "baseline_metrics": {
            "threshold": 0.5,
            "micro_f1": round(baseline_metrics.micro_f1, 4),
            "macro_f1": round(baseline_metrics.macro_f1, 4),
            "subset_accuracy": round(baseline_metrics.subset_accuracy, 4),
        },
        "tuned_metrics": {
            "micro_f1": round(tuned_micro_f1, 4),
            "macro_f1": round(tuned_macro_f1, 4),
        },
    }
    
    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n=== OUTPUT ===")
    print(f"Saved thresholds to: {output_path}")
    print("\nPer-class thresholds summary:")
    for class_name in class_names:
        t = per_class_thresholds[class_name]
        f1 = per_class_results[class_name]["f1"]
        print(f"  {class_name}: {t:.3f} (F1={f1:.3f})")


if __name__ == "__main__":
    main()
