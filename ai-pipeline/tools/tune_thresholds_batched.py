#!/usr/bin/env python3
"""
Per-Class Threshold Tuning for Multi-Label Drum Classifier
Using BatchedMultiLabelDataset (manifest-based)

This script finds optimal sigmoid thresholds per class using the same
dataset format as training (BatchedMultiLabelDataset with manifest files).

Usage:
    python tools/tune_thresholds_batched.py \
        --model runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt \
        --manifests F:/datasets/multilabel_real_v3/egmd/egmd_manifest.json \
                    F:/datasets/multilabel_real_v3/groove_midi/groove_manifest.json \
                    F:/datasets/multilabel_real_v3/slakh/slakh_manifest.json \
                    F:/datasets/multilabel_real_v3/lakh_synth/lakh_manifest.json \
        --output runs/v5_multilabel_final_v2/thresholds.json

Output JSON format:
{
    "global_threshold": 0.45,
    "per_class_thresholds": {
        "kick": 0.5,
        "snare": 0.45,
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
from typing import Dict, List, Tuple, Any
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, ConcatDataset
from tqdm import tqdm

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.models.cnn_v5 import cnn_v5_large
from training.multilabel.dataset import BatchedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS

# 12-class drum components (standard order)
CLASS_NAMES = DEFAULT_DRUM_COMPONENTS[:12]


def load_ema_model(
    model_path: str,
    num_classes: int = 12,
    device: str = "cuda",
) -> nn.Module:
    """
    Load trained multi-label model, handling both EMA checkpoints and full checkpoints.
    
    For EMA-only checkpoints (best_multilabel_model_ema.pt):
      - Direct state dict with 'backbone.' prefix
      
    For full checkpoints (best_checkpoint.pt):
      - Nested: checkpoint['ema_state_dict']['ema_model'] with 'backbone.' prefix
    """
    print(f"Loading model: {model_path}")
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    # Create model
    model = cnn_v5_large(num_classes=num_classes)
    
    # Extract state dict based on checkpoint format
    if 'ema_state_dict' in checkpoint:
        # Full checkpoint format
        print("  Detected full checkpoint, extracting EMA weights")
        ema_state = checkpoint['ema_state_dict']
        if isinstance(ema_state, dict) and 'ema_model' in ema_state:
            state_dict = ema_state['ema_model']
        else:
            state_dict = ema_state
    elif 'model_state_dict' in checkpoint:
        # Standard checkpoint format
        print("  Detected standard checkpoint format")
        state_dict = checkpoint['model_state_dict']
    elif 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    else:
        # EMA-only checkpoint (direct state dict)
        print("  Detected EMA-only checkpoint (direct state dict)")
        state_dict = checkpoint
    
    # Strip 'backbone.' prefix if present
    cleaned_state_dict = {}
    has_backbone_prefix = any(k.startswith('backbone.') for k in state_dict.keys())
    if has_backbone_prefix:
        print("  Stripping 'backbone.' prefix from keys")
    
    for key, value in state_dict.items():
        if key.startswith('backbone.'):
            cleaned_state_dict[key[9:]] = value  # len('backbone.') = 9
        else:
            cleaned_state_dict[key] = value
    
    # Load weights
    result = model.load_state_dict(cleaned_state_dict, strict=False)
    if result.missing_keys:
        print(f"  Warning: {len(result.missing_keys)} missing keys")
    if result.unexpected_keys:
        print(f"  Warning: {len(result.unexpected_keys)} unexpected keys")
    
    model.to(device)
    model.eval()
    
    # Verify model works
    with torch.no_grad():
        dummy = torch.randn(1, 1, 128, 128).to(device)
        out = model(dummy)
        print(f"  Model output shape: {out.shape}")
    
    return model


def collect_predictions(
    model: nn.Module,
    dataloader: DataLoader,
    device: str = "cuda",
    max_batches: int = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Collect all predictions (probabilities) and targets from the dataset.
    
    Returns:
        Tuple of (all_probs, all_targets) numpy arrays
    """
    all_probs = []
    all_targets = []
    
    total = len(dataloader) if max_batches is None else min(max_batches, len(dataloader))
    
    with torch.inference_mode():
        for batch_idx, (features, labels) in enumerate(tqdm(dataloader, total=total, desc="Inference")):
            if max_batches and batch_idx >= max_batches:
                break
                
            features = features.to(device)
            logits = model(features)
            probs = torch.sigmoid(logits).cpu().numpy()
            
            all_probs.append(probs)
            all_targets.append(labels.numpy())
    
    return np.concatenate(all_probs), np.concatenate(all_targets)


def tune_threshold_for_class(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    thresholds: np.ndarray = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Find optimal threshold that maximizes F1 for a single class.
    
    Returns:
        (best_threshold, metrics_dict)
    """
    if thresholds is None:
        thresholds = np.arange(0.05, 0.95, 0.025)
    
    best_f1 = 0.0
    best_threshold = 0.5
    epsilon = 1e-8
    
    num_positives = y_true.sum()
    num_negatives = len(y_true) - num_positives
    
    # Initialize with default metrics in case no threshold improves F1
    best_metrics = {
        "threshold": 0.5,
        "f1": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "tp": 0,
        "fp": 0,
        "fn": int(num_positives),
        "tn": int(num_negatives),
        "support": int(num_positives),
    }
    
    # Skip if no positive samples
    if num_positives == 0:
        return best_threshold, best_metrics
    
    for t in thresholds:
        y_pred = (y_prob >= t).astype(float)
        
        tp = ((y_pred == 1) & (y_true == 1)).sum()
        fp = ((y_pred == 1) & (y_true == 0)).sum()
        fn = ((y_pred == 0) & (y_true == 1)).sum()
        tn = ((y_pred == 0) & (y_true == 0)).sum()
        
        precision = tp / (tp + fp + epsilon)
        recall = tp / (tp + fn + epsilon)
        f1 = 2 * precision * recall / (precision + recall + epsilon)
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
            best_metrics = {
                "threshold": round(float(t), 3),
                "f1": round(float(f1), 4),
                "precision": round(float(precision), 4),
                "recall": round(float(recall), 4),
                "tp": int(tp),
                "fp": int(fp),
                "fn": int(fn),
                "tn": int(tn),
                "support": int(num_positives),
            }
    
    return best_threshold, best_metrics


def tune_global_threshold(
    all_probs: np.ndarray,
    all_targets: np.ndarray,
    thresholds: np.ndarray = None,
) -> Tuple[float, float]:
    """
    Find optimal global threshold that maximizes micro-F1.
    
    Returns:
        (best_threshold, best_micro_f1)
    """
    if thresholds is None:
        thresholds = np.arange(0.1, 0.9, 0.025)
    
    best_f1 = 0.0
    best_threshold = 0.5
    epsilon = 1e-8
    
    for t in thresholds:
        preds = (all_probs >= t).astype(float)
        
        tp = (preds * all_targets).sum()
        fp = (preds * (1 - all_targets)).sum()
        fn = ((1 - preds) * all_targets).sum()
        
        precision = tp / (tp + fp + epsilon)
        recall = tp / (tp + fn + epsilon)
        f1 = 2 * precision * recall / (precision + recall + epsilon)
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
    
    return best_threshold, best_f1


def compute_baseline_metrics(
    all_probs: np.ndarray,
    all_targets: np.ndarray,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """Compute baseline metrics at a fixed threshold."""
    epsilon = 1e-8
    preds = (all_probs >= threshold).astype(float)
    
    # Micro metrics
    tp = (preds * all_targets).sum()
    fp = (preds * (1 - all_targets)).sum()
    fn = ((1 - preds) * all_targets).sum()
    
    micro_precision = tp / (tp + fp + epsilon)
    micro_recall = tp / (tp + fn + epsilon)
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall + epsilon)
    
    # Macro metrics (per-class average)
    class_f1s = []
    for i in range(all_probs.shape[1]):
        tp_i = (preds[:, i] * all_targets[:, i]).sum()
        fp_i = (preds[:, i] * (1 - all_targets[:, i])).sum()
        fn_i = ((1 - preds[:, i]) * all_targets[:, i]).sum()
        
        prec_i = tp_i / (tp_i + fp_i + epsilon)
        rec_i = tp_i / (tp_i + fn_i + epsilon)
        f1_i = 2 * prec_i * rec_i / (prec_i + rec_i + epsilon)
        class_f1s.append(f1_i)
    
    macro_f1 = np.mean(class_f1s)
    
    return {
        "threshold": threshold,
        "micro_f1": round(float(micro_f1), 4),
        "macro_f1": round(float(macro_f1), 4),
        "micro_precision": round(float(micro_precision), 4),
        "micro_recall": round(float(micro_recall), 4),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Tune per-class thresholds for multi-label drum classifier"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to trained model checkpoint (EMA or full)",
    )
    parser.add_argument(
        "--manifests",
        type=str,
        nargs="+",
        required=True,
        help="Paths to manifest JSON files for validation data",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for thresholds JSON",
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
        "--max-samples",
        type=int,
        default=None,
        help="Maximum samples to use (for faster testing)",
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
    
    for manifest in args.manifests:
        if not os.path.exists(manifest):
            print(f"ERROR: Manifest not found: {manifest}")
            sys.exit(1)
    
    print("=" * 80)
    print("PER-CLASS THRESHOLD TUNING FOR MULTI-LABEL DRUM CLASSIFIER")
    print("=" * 80)
    print(f"Model: {args.model}")
    print(f"Manifests: {len(args.manifests)} files")
    print(f"Device: {args.device}")
    print(f"Classes ({len(CLASS_NAMES)}): {CLASS_NAMES}")
    print()
    
    # Load model
    model = load_ema_model(args.model, num_classes=12, device=args.device)
    
    # Create combined validation dataset from all manifests
    print("\nLoading validation datasets...")
    val_datasets = []
    total_val_samples = 0
    
    for manifest_path in args.manifests:
        print(f"  Loading: {manifest_path}")
        val_ds = BatchedMultiLabelDataset(
            manifest_path=manifest_path,
            is_train=False,  # Use validation split
            num_classes=12,
            shuffle_batches=False,
            shuffle_before_split=True,  # Same as training
            split_seed=42,  # Same as training
        )
        val_datasets.append(val_ds)
        print(f"    Validation samples: {len(val_ds):,}")
        total_val_samples += len(val_ds)
    
    combined_dataset = ConcatDataset(val_datasets)
    print(f"\nTotal validation samples: {total_val_samples:,}")
    
    # Create dataloader
    max_batches = None
    if args.max_samples:
        max_batches = args.max_samples // args.batch_size
        print(f"Limiting to ~{args.max_samples:,} samples ({max_batches} batches)")
    
    dataloader = DataLoader(
        combined_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True,
    )
    
    # Collect predictions
    print("\nRunning inference on validation set...")
    all_probs, all_targets = collect_predictions(
        model, dataloader, args.device, max_batches
    )
    print(f"Collected {len(all_probs):,} predictions")
    
    # Compute baseline metrics at threshold=0.5
    print("\n" + "=" * 80)
    print("BASELINE METRICS (threshold=0.5)")
    print("=" * 80)
    baseline = compute_baseline_metrics(all_probs, all_targets, 0.5)
    print(f"  Micro-F1:    {baseline['micro_f1']:.4f}")
    print(f"  Macro-F1:    {baseline['macro_f1']:.4f}")
    print(f"  Precision:   {baseline['micro_precision']:.4f}")
    print(f"  Recall:      {baseline['micro_recall']:.4f}")
    
    # Find optimal global threshold
    print("\n" + "=" * 80)
    print("GLOBAL THRESHOLD TUNING")
    print("=" * 80)
    thresholds = np.arange(0.1, 0.9, args.threshold_step)
    global_threshold, global_f1 = tune_global_threshold(all_probs, all_targets, thresholds)
    print(f"  Best global threshold: {global_threshold:.3f}")
    print(f"  Micro-F1 at optimal:   {global_f1:.4f}")
    
    # Tune per-class thresholds
    print("\n" + "=" * 80)
    print("PER-CLASS THRESHOLD TUNING")
    print("=" * 80)
    print(f"{'Class':<15} {'Threshold':>10} {'F1':>8} {'Precision':>10} {'Recall':>8} {'Support':>10}")
    print("-" * 70)
    
    per_class_thresholds = {}
    per_class_metrics = {}
    
    for i, class_name in enumerate(CLASS_NAMES):
        y_true = all_targets[:, i]
        y_prob = all_probs[:, i]
        
        threshold, metrics = tune_threshold_for_class(y_true, y_prob, thresholds)
        
        per_class_thresholds[class_name] = metrics["threshold"]
        per_class_metrics[class_name] = metrics
        
        print(
            f"{class_name:<15} {metrics['threshold']:>10.3f} {metrics['f1']:>8.4f} "
            f"{metrics['precision']:>10.4f} {metrics['recall']:>8.4f} {metrics['support']:>10,}"
        )
    
    # Compute metrics with tuned thresholds
    print("\n" + "=" * 80)
    print("TUNED METRICS (per-class thresholds)")
    print("=" * 80)
    
    # Apply per-class thresholds
    tuned_preds = np.zeros_like(all_probs)
    for i, class_name in enumerate(CLASS_NAMES):
        t = per_class_thresholds[class_name]
        tuned_preds[:, i] = (all_probs[:, i] >= t).astype(float)
    
    epsilon = 1e-8
    tp = (tuned_preds * all_targets).sum()
    fp = (tuned_preds * (1 - all_targets)).sum()
    fn = ((1 - tuned_preds) * all_targets).sum()
    
    tuned_precision = tp / (tp + fp + epsilon)
    tuned_recall = tp / (tp + fn + epsilon)
    tuned_micro_f1 = 2 * tuned_precision * tuned_recall / (tuned_precision + tuned_recall + epsilon)
    
    tuned_macro_f1 = np.mean([m["f1"] for m in per_class_metrics.values()])
    
    print(f"  Micro-F1:    {tuned_micro_f1:.4f} (was {baseline['micro_f1']:.4f}, Δ={tuned_micro_f1 - baseline['micro_f1']:+.4f})")
    print(f"  Macro-F1:    {tuned_macro_f1:.4f} (was {baseline['macro_f1']:.4f}, Δ={tuned_macro_f1 - baseline['macro_f1']:+.4f})")
    print(f"  Precision:   {tuned_precision:.4f}")
    print(f"  Recall:      {tuned_recall:.4f}")
    
    # Prepare output
    output = {
        "model_path": os.path.abspath(args.model),
        "manifests": [os.path.abspath(m) for m in args.manifests],
        "timestamp": datetime.now().isoformat(),
        "num_samples": len(all_probs),
        "num_classes": len(CLASS_NAMES),
        "class_names": CLASS_NAMES,
        "global_threshold": round(float(global_threshold), 3),
        "per_class_thresholds": per_class_thresholds,
        "per_class_metrics": per_class_metrics,
        "baseline_metrics": baseline,
        "tuned_metrics": {
            "micro_f1": round(float(tuned_micro_f1), 4),
            "macro_f1": round(float(tuned_macro_f1), 4),
            "micro_precision": round(float(tuned_precision), 4),
            "micro_recall": round(float(tuned_recall), 4),
        },
    }
    
    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n" + "=" * 80)
    print("OUTPUT SAVED")
    print("=" * 80)
    print(f"Thresholds saved to: {output_path}")
    
    # Print summary for easy copy-paste
    print("\nPer-class thresholds summary (for config):")
    print("{")
    for class_name in CLASS_NAMES:
        print(f'    "{class_name}": {per_class_thresholds[class_name]},')
    print("}")


if __name__ == "__main__":
    main()
