#!/usr/bin/env python3
"""
Re-tune classification thresholds on ENST real drum data.

This script optimizes per-class thresholds using ENST validation data
to improve performance on real acoustic drum recordings.

Usage:
    python scripts/retune_thresholds_enst.py --model runs/v5_finetuned_enst/best_model.pt
    
The thresholds will be saved to:
    - Model directory (thresholds.json)
    - runs/v5_finetuned_enst/thresholds_enst_tuned.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from tqdm import tqdm

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.multilabel.dataset import DEFAULT_DRUM_COMPONENTS


def load_enst_batches(
    manifest_path: Path,
    split: str = "val",
) -> Tuple[np.ndarray, np.ndarray]:
    """Load ENST batches for threshold tuning.
    
    Args:
        manifest_path: Path to enst_manifest.json
        split: Which split to use ('train' or 'val')
    
    Returns:
        Tuple of (features, labels) arrays
    """
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    batch_dir = manifest_path.parent / "enst_batches"
    
    all_features = []
    all_labels = []
    
    for batch_info in manifest['batches']:
        if batch_info.get('split', 'train') != split:
            continue
        
        features_path = batch_dir / batch_info['features']
        labels_path = batch_dir / batch_info['labels']
        
        features = np.load(features_path)
        labels = np.load(labels_path)
        
        all_features.append(features)
        all_labels.append(labels)
    
    if not all_features:
        raise ValueError(f"No {split} batches found in manifest")
    
    return np.concatenate(all_features), np.concatenate(all_labels)


def load_model(model_path: Path, device: torch.device):
    """Load the trained model."""
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    # Get model state dict
    if 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    elif 'ema_state_dict' in checkpoint:
        state_dict = checkpoint['ema_state_dict']
    else:
        state_dict = checkpoint
    
    # Import model architecture
    from training.multilabel.model import MultiLabelDrumClassifierV5
    
    # Detect model size from state dict
    first_conv = state_dict.get('conv_stem.0.weight', state_dict.get('stem.0.weight'))
    if first_conv is not None:
        base_channels = first_conv.shape[0]
        if base_channels >= 64:
            size = "large"
        elif base_channels >= 48:
            size = "medium"
        else:
            size = "small"
    else:
        size = "large"
    
    model = MultiLabelDrumClassifierV5(
        num_classes=len(DEFAULT_DRUM_COMPONENTS),
        size=size,
    )
    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()
    
    return model


def compute_predictions(
    model: torch.nn.Module,
    features: np.ndarray,
    device: torch.device,
    batch_size: int = 64,
) -> np.ndarray:
    """Get model predictions for all samples."""
    model.eval()
    
    all_probs = []
    
    with torch.no_grad():
        for i in tqdm(range(0, len(features), batch_size), desc="Computing predictions"):
            batch = features[i:i + batch_size]
            
            # Add channel dimension if needed
            if batch.ndim == 3:
                batch = batch[:, np.newaxis, :, :]
            
            x = torch.from_numpy(batch).float().to(device)
            
            logits = model(x)
            probs = torch.sigmoid(logits).cpu().numpy()
            all_probs.append(probs)
    
    return np.concatenate(all_probs)


def find_optimal_thresholds(
    probs: np.ndarray,
    labels: np.ndarray,
    class_names: List[str],
    threshold_range: Tuple[float, float] = (0.1, 0.9),
    num_thresholds: int = 81,
) -> Dict[str, float]:
    """Find optimal threshold for each class using F1 score.
    
    Args:
        probs: Predicted probabilities (N, C)
        labels: Ground truth labels (N, C)
        class_names: List of class names
        threshold_range: (min, max) threshold to search
        num_thresholds: Number of threshold values to try
    
    Returns:
        Dictionary mapping class name to optimal threshold
    """
    num_classes = probs.shape[1]
    thresholds = np.linspace(threshold_range[0], threshold_range[1], num_thresholds)
    
    optimal_thresholds = {}
    
    print("\nOptimizing thresholds per class...")
    print("-" * 70)
    print(f"{'Class':<15} {'Best Thresh':>12} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 70)
    
    for c in range(num_classes):
        class_probs = probs[:, c]
        class_labels = labels[:, c]
        
        # Skip if no positive samples
        if class_labels.sum() == 0:
            print(f"{class_names[c]:<15} {'N/A':>12} {'N/A':>10} {'N/A':>10} {'N/A':>10}")
            optimal_thresholds[class_names[c]] = 0.5
            continue
        
        best_f1 = 0
        best_thresh = 0.5
        best_precision = 0
        best_recall = 0
        
        for thresh in thresholds:
            preds = (class_probs >= thresh).astype(int)
            
            tp = np.sum((preds == 1) & (class_labels == 1))
            fp = np.sum((preds == 1) & (class_labels == 0))
            fn = np.sum((preds == 0) & (class_labels == 1))
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = thresh
                best_precision = precision
                best_recall = recall
        
        optimal_thresholds[class_names[c]] = round(best_thresh, 3)
        print(f"{class_names[c]:<15} {best_thresh:>12.3f} {best_precision:>10.3f} {best_recall:>10.3f} {best_f1:>10.3f}")
    
    print("-" * 70)
    
    return optimal_thresholds


def main():
    parser = argparse.ArgumentParser(description="Re-tune thresholds on ENST data")
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Path to model checkpoint",
    )
    parser.add_argument(
        "--enst-manifest",
        type=Path,
        default=Path("F:/datasets/multilabel_real_v3/enst_real/enst_manifest.json"),
        help="Path to ENST manifest",
    )
    parser.add_argument(
        "--split",
        choices=["train", "val"],
        default="val",
        help="Which split to use for tuning",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for thresholds JSON (default: model_dir/thresholds_enst.json)",
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Device to use",
    )
    args = parser.parse_args()
    
    print("=" * 70)
    print("RE-TUNE THRESHOLDS ON ENST REAL DRUM DATA")
    print("=" * 70)
    print(f"Model: {args.model}")
    print(f"ENST manifest: {args.enst_manifest}")
    print(f"Split: {args.split}")
    print(f"Device: {args.device}")
    print()
    
    device = torch.device(args.device)
    
    # Load ENST data
    print("Loading ENST data...")
    features, labels = load_enst_batches(args.enst_manifest, args.split)
    print(f"  Loaded {len(features):,} samples")
    
    # Load model
    print("\nLoading model...")
    model = load_model(args.model, device)
    print("  Model loaded successfully")
    
    # Compute predictions
    print("\nComputing predictions...")
    probs = compute_predictions(model, features, device)
    
    # Find optimal thresholds
    optimal_thresholds = find_optimal_thresholds(
        probs, labels, DEFAULT_DRUM_COMPONENTS,
    )
    
    # Save thresholds
    output_path = args.output or args.model.parent / "thresholds_enst.json"
    
    result = {
        "tuning_dataset": "enst_real",
        "tuning_split": args.split,
        "tuning_samples": len(features),
        "model": str(args.model),
        "thresholds": optimal_thresholds,
        "class_order": DEFAULT_DRUM_COMPONENTS,
    }
    
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n✓ Thresholds saved to: {output_path}")
    
    # Also save to model directory as primary thresholds
    primary_output = args.model.parent / "thresholds.json"
    if primary_output != output_path:
        with open(primary_output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"✓ Also saved to: {primary_output}")
    
    print("\n" + "=" * 70)
    print("Done! Use these thresholds for inference on real acoustic drums.")
    print("=" * 70)


if __name__ == "__main__":
    main()
