#!/usr/bin/env python3
"""
Diagnose why F1 is stuck at 0.60 for multi-label drum classifier.

This script:
1. Loads the latest checkpoint
2. Runs inference on validation data
3. Analyzes prediction distributions
4. Computes optimal thresholds per class
5. Shows per-class recall/precision breakdown
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from tqdm import tqdm
from collections import defaultdict
import argparse

from training.models.cnn_v5 import cnn_v5_large
from training.multilabel.dataset import BatchedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS
from training.multilabel.metrics import compute_all_metrics, find_optimal_thresholds

# 12-class drum components (same order as DEFAULT_DRUM_COMPONENTS)
CLASS_NAMES = DEFAULT_DRUM_COMPONENTS[:12]


def load_checkpoint(checkpoint_path: str, device: torch.device, num_classes: int = 12):
    """Load model from checkpoint."""
    print(f"Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Determine model version and size from checkpoint
    if 'model_config' in checkpoint:
        config = checkpoint['model_config']
        model_version = config.get('model_version', 'v5')
        v5_size = config.get('v5_size', 'large')
    else:
        model_version = 'v5'
        v5_size = 'large'
    
    print(f"Model: {model_version} ({v5_size})")
    
    # Create model with correct number of classes
    model = cnn_v5_large(num_classes=num_classes)
    
    # Load weights
    use_ema = True
    if use_ema and 'ema_state_dict' in checkpoint:
        print("Using EMA weights")
        ema_state = checkpoint['ema_state_dict']
        # EMA is stored as {'ema_model': state_dict, 'decay': ..., ...}
        if isinstance(ema_state, dict) and 'ema_model' in ema_state:
            state_dict = ema_state['ema_model']
        else:
            state_dict = ema_state
    else:
        print("Using main model weights (not EMA)")
        state_dict = checkpoint.get('model_state_dict', checkpoint.get('state_dict', checkpoint))
    
    # Remove 'module.' prefix if present
    if any(k.startswith('module.') for k in state_dict.keys()):
        state_dict = {k.replace('module.', ''): v for k, v in state_dict.items()}
    
    # Check if this is a wrapped MultiLabelDrumClassifier
    # The checkpoint may have 'backbone.' prefix
    new_state_dict = {}
    for k, v in state_dict.items():
        if k.startswith('backbone.'):
            new_state_dict[k.replace('backbone.', '')] = v
        else:
            new_state_dict[k] = v
    
    result = model.load_state_dict(new_state_dict, strict=False)
    print(f"Load result: missing={len(result.missing_keys)}, unexpected={len(result.unexpected_keys)}")
    if result.missing_keys:
        print(f"  Missing keys (first 5): {result.missing_keys[:5]}")
    
    model.to(device)
    model.eval()
    
    return model


def analyze_predictions(all_probs: np.ndarray, all_labels: np.ndarray):
    """Analyze prediction distributions per class."""
    print("\n" + "="*80)
    print("PREDICTION ANALYSIS")
    print("="*80)
    
    num_classes = all_probs.shape[1]
    
    for i in range(num_classes):
        probs_i = all_probs[:, i]
        labels_i = all_labels[:, i]
        
        positive_mask = labels_i == 1
        negative_mask = labels_i == 0
        
        pos_probs = probs_i[positive_mask]
        neg_probs = probs_i[negative_mask]
        
        print(f"\n{CLASS_NAMES[i].upper():15s}:")
        print(f"  Positive samples: {positive_mask.sum():,} ({100*positive_mask.mean():.2f}%)")
        print(f"  Negative samples: {negative_mask.sum():,} ({100*negative_mask.mean():.2f}%)")
        
        if len(pos_probs) > 0:
            print(f"  Positive probs: min={pos_probs.min():.3f}, mean={pos_probs.mean():.3f}, max={pos_probs.max():.3f}")
            print(f"    Percentiles: 10%={np.percentile(pos_probs, 10):.3f}, 50%={np.percentile(pos_probs, 50):.3f}, 90%={np.percentile(pos_probs, 90):.3f}")
        
        if len(neg_probs) > 0:
            print(f"  Negative probs: min={neg_probs.min():.3f}, mean={neg_probs.mean():.3f}, max={neg_probs.max():.3f}")
            print(f"    Percentiles: 10%={np.percentile(neg_probs, 10):.3f}, 50%={np.percentile(neg_probs, 50):.3f}, 90%={np.percentile(neg_probs, 90):.3f}")
        
        # Separation quality
        if len(pos_probs) > 0 and len(neg_probs) > 0:
            separation = pos_probs.mean() - neg_probs.mean()
            print(f"  Mean separation: {separation:.3f}")
            
            # How many positives have prob < 0.5?
            low_conf_pos = (pos_probs < 0.5).mean()
            high_conf_neg = (neg_probs >= 0.5).mean()
            print(f"  Positives with prob < 0.5: {100*low_conf_pos:.1f}%")
            print(f"  Negatives with prob >= 0.5: {100*high_conf_neg:.1f}%")


def find_all_thresholds(all_probs: np.ndarray, all_labels: np.ndarray):
    """Find optimal thresholds and compute F1 at different thresholds."""
    print("\n" + "="*80)
    print("THRESHOLD ANALYSIS")
    print("="*80)
    
    num_classes = all_probs.shape[1]
    thresholds_to_try = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    
    # Per-class optimal thresholds
    print("\nOptimal thresholds per class:")
    optimal_thresholds = []
    
    for i in range(num_classes):
        best_f1 = 0
        best_t = 0.5
        
        for t in np.arange(0.05, 0.95, 0.05):
            pred = (all_probs[:, i] >= t).astype(float)
            target = all_labels[:, i]
            
            tp = (pred * target).sum()
            fp = (pred * (1 - target)).sum()
            fn = ((1 - pred) * target).sum()
            
            precision = tp / (tp + fp + 1e-8)
            recall = tp / (tp + fn + 1e-8)
            f1 = 2 * precision * recall / (precision + recall + 1e-8)
            
            if f1 > best_f1:
                best_f1 = f1
                best_t = t
        
        optimal_thresholds.append(best_t)
        print(f"  {CLASS_NAMES[i]:15s}: t={best_t:.2f} -> F1={best_f1:.4f}")
    
    # Global threshold sweep
    print("\nGlobal threshold sweep (micro-F1):")
    for t in thresholds_to_try:
        pred_binary = (all_probs >= t).astype(float)
        
        tp = (pred_binary * all_labels).sum()
        fp = (pred_binary * (1 - all_labels)).sum()
        fn = ((1 - pred_binary) * all_labels).sum()
        
        precision = tp / (tp + fp + 1e-8)
        recall = tp / (tp + fn + 1e-8)
        micro_f1 = 2 * precision * recall / (precision + recall + 1e-8)
        
        print(f"  t={t:.1f}: micro-F1={micro_f1:.4f}, prec={precision:.4f}, recall={recall:.4f}")
    
    # With optimal per-class thresholds
    pred_optimal = np.zeros_like(all_probs)
    for i, t in enumerate(optimal_thresholds):
        pred_optimal[:, i] = (all_probs[:, i] >= t).astype(float)
    
    tp = (pred_optimal * all_labels).sum()
    fp = (pred_optimal * (1 - all_labels)).sum()
    fn = ((1 - pred_optimal) * all_labels).sum()
    
    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    micro_f1 = 2 * precision * recall / (precision + recall + 1e-8)
    
    print(f"\nWith per-class optimal thresholds: micro-F1={micro_f1:.4f}")
    
    return optimal_thresholds


def analyze_class_correlations(all_labels: np.ndarray):
    """Analyze co-occurrence patterns in labels."""
    print("\n" + "="*80)
    print("LABEL CO-OCCURRENCE ANALYSIS")
    print("="*80)
    
    num_classes = all_labels.shape[1]
    
    # Count label occurrences
    print("\nLabel counts:")
    for i in range(num_classes):
        count = all_labels[:, i].sum()
        pct = 100 * count / len(all_labels)
        print(f"  {CLASS_NAMES[i]:15s}: {int(count):,} ({pct:.2f}%)")
    
    # Co-occurrence matrix
    print("\nCo-occurrence (P(B|A)):")
    print(f"{'':15s}", end='')
    for name in CLASS_NAMES:
        print(f"{name[:6]:>8s}", end='')
    print()
    
    for i in range(num_classes):
        print(f"{CLASS_NAMES[i]:15s}", end='')
        for j in range(num_classes):
            if i == j:
                print(f"{'---':>8s}", end='')
            else:
                # P(j | i) = P(i and j) / P(i)
                both = ((all_labels[:, i] == 1) & (all_labels[:, j] == 1)).sum()
                just_i = (all_labels[:, i] == 1).sum()
                prob = both / max(just_i, 1)
                print(f"{prob:>8.2f}", end='')
        print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=str, required=True,
                        help='Path to checkpoint')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to manifest JSON file')
    parser.add_argument('--max-batches', type=int, default=100,
                        help='Max validation batches to process')
    args = parser.parse_args()
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load model
    model = load_checkpoint(args.checkpoint, device, num_classes=12)
    
    # Load validation data
    manifest_path = Path(args.dataset)
    print(f"\nLoading validation data from manifest: {manifest_path}")
    
    # is_train=False to get validation split
    val_dataset = BatchedMultiLabelDataset(manifest_path, is_train=False, num_classes=12)
    print(f"Validation samples: {len(val_dataset):,}")
    
    # Collect predictions
    all_probs = []
    all_labels = []
    
    batch_size = 256
    num_batches = min(len(val_dataset) // batch_size, args.max_batches)
    
    print(f"\nRunning inference on {num_batches} batches...")
    
    with torch.no_grad():
        for batch_idx in tqdm(range(num_batches)):
            # Get batch of samples
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(val_dataset))
            
            features_list = []
            labels_list = []
            
            for i in range(start_idx, end_idx):
                feat, label = val_dataset[i]
                features_list.append(feat)
                labels_list.append(label)
            
            features = torch.stack(features_list).to(device)
            labels = torch.stack(labels_list)
            
            # Forward pass
            logits = model(features)
            probs = torch.sigmoid(logits).cpu().numpy()
            
            all_probs.append(probs)
            all_labels.append(labels.numpy())
    
    all_probs = np.concatenate(all_probs, axis=0)
    all_labels = np.concatenate(all_labels, axis=0)
    
    print(f"\nCollected {len(all_probs):,} samples")
    
    # Run analyses
    analyze_predictions(all_probs, all_labels)
    analyze_class_correlations(all_labels)
    optimal_thresholds = find_all_thresholds(all_probs, all_labels)
    
    # Compute metrics at threshold 0.5
    print("\n" + "="*80)
    print("METRICS AT THRESHOLD 0.5 (CURRENT)")
    print("="*80)
    
    pred_05 = (all_probs >= 0.5).astype(float)
    tp = (pred_05 * all_labels).sum()
    fp = (pred_05 * (1 - all_labels)).sum()
    fn = ((1 - pred_05) * all_labels).sum()
    tn = ((1 - pred_05) * (1 - all_labels)).sum()
    
    print(f"\nGlobal confusion matrix:")
    print(f"  TP: {int(tp):,}")
    print(f"  FP: {int(fp):,}")
    print(f"  FN: {int(fn):,}")
    print(f"  TN: {int(tn):,}")
    
    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    micro_f1 = 2 * precision * recall / (precision + recall + 1e-8)
    
    print(f"\n  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  Micro-F1:  {micro_f1:.4f}")
    
    # Per-class breakdown
    print("\nPer-class breakdown at t=0.5:")
    print(f"{'Class':15s} {'TP':>8s} {'FP':>8s} {'FN':>8s} {'Prec':>8s} {'Recall':>8s} {'F1':>8s}")
    print("-" * 70)
    
    for i in range(len(CLASS_NAMES)):
        pred_i = (all_probs[:, i] >= 0.5).astype(float)
        target_i = all_labels[:, i]
        
        tp_i = (pred_i * target_i).sum()
        fp_i = (pred_i * (1 - target_i)).sum()
        fn_i = ((1 - pred_i) * target_i).sum()
        
        prec_i = tp_i / (tp_i + fp_i + 1e-8)
        rec_i = tp_i / (tp_i + fn_i + 1e-8)
        f1_i = 2 * prec_i * rec_i / (prec_i + rec_i + 1e-8)
        
        print(f"{CLASS_NAMES[i]:15s} {int(tp_i):>8,} {int(fp_i):>8,} {int(fn_i):>8,} {prec_i:>8.4f} {rec_i:>8.4f} {f1_i:>8.4f}")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Current micro-F1 at t=0.5: {micro_f1:.4f}")
    print(f"Optimal thresholds: {optimal_thresholds}")


if __name__ == '__main__':
    main()
