#!/usr/bin/env python3
"""
Comprehensive per-class evaluation for multi-label drum classifier.

Evaluates:
- Main model checkpoint
- EMA model (if available)
- Compares performance and identifies problem classes
- Recommends improvements

Usage:
    python evaluate_perclass.py --checkpoint runs/v5_multilabel/best_checkpoint.pt
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from sklearn.metrics import f1_score, precision_recall_fscore_support
from torch.utils.data import DataLoader
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.multilabel.dataset import CachedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS
from training.multilabel.train_multilabel import create_model


def load_checkpoint(checkpoint_path: str, device: torch.device) -> Tuple[torch.nn.Module, dict]:
    """Load model from checkpoint."""
    model = create_model(
        model_version='v5',
        num_classes=12,
        v5_size='large',
        drop_path_rate=0.1
    )
    
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Handle different checkpoint formats
    if 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
    else:
        model.load_state_dict(checkpoint)
    
    model = model.to(device).eval()
    
    return model, checkpoint


def evaluate_model(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    threshold: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run evaluation and return probs, predictions, labels."""
    all_probs = []
    all_labels = []
    
    with torch.no_grad():
        for specs, labels in tqdm(loader, desc="Evaluating"):
            probs = torch.sigmoid(model(specs.to(device)))
            all_probs.append(probs.cpu().numpy())
            all_labels.append(labels.numpy())
    
    all_probs = np.vstack(all_probs)
    all_labels = np.vstack(all_labels)
    all_preds = (all_probs > threshold).astype(float)
    
    return all_probs, all_preds, all_labels


def analyze_per_class(
    probs: np.ndarray,
    labels: np.ndarray,
    class_names: List[str],
) -> Dict:
    """Analyze per-class performance with different thresholds."""
    results = {}
    
    for i, cls in enumerate(class_names):
        # At threshold 0.5
        preds_05 = (probs[:, i] > 0.5).astype(float)
        p_05, r_05, f1_05, _ = precision_recall_fscore_support(
            labels[:, i], preds_05, average='binary', zero_division=0
        )
        
        # Find optimal threshold
        best_f1 = 0
        best_t = 0.5
        for t in np.arange(0.1, 0.9, 0.02):
            preds = (probs[:, i] > t).astype(float)
            if preds.sum() > 0:
                _, _, f1, _ = precision_recall_fscore_support(
                    labels[:, i], preds, average='binary', zero_division=0
                )
                if f1 > best_f1:
                    best_f1 = f1
                    best_t = t
        
        # At optimal threshold
        preds_opt = (probs[:, i] > best_t).astype(float)
        p_opt, r_opt, f1_opt, _ = precision_recall_fscore_support(
            labels[:, i], preds_opt, average='binary', zero_division=0
        )
        
        results[cls] = {
            'support': int(labels[:, i].sum()),
            'at_0.5': {'precision': p_05, 'recall': r_05, 'f1': f1_05},
            'optimal': {'threshold': best_t, 'precision': p_opt, 'recall': r_opt, 'f1': f1_opt},
            'gain': f1_opt - f1_05,
        }
    
    return results


def print_analysis(results: Dict, title: str = "Model"):
    """Print formatted analysis."""
    print(f"\n{'='*80}")
    print(f"{title} Per-Class Analysis")
    print('='*80)
    print(f"{'Class':<15} {'P@0.5':>7} {'R@0.5':>7} {'F1@0.5':>7} "
          f"{'OptT':>6} {'F1@Opt':>7} {'Gain':>7} {'Support':>8}")
    print('-'*80)
    
    problem_classes = []
    for cls, data in results.items():
        f1_05 = data['at_0.5']['f1']
        f1_opt = data['optimal']['f1']
        marker = ""
        if f1_05 < 0.7:
            marker = " <<< LOW"
            problem_classes.append((cls, f1_05, data['at_0.5']['recall']))
        elif f1_05 < 0.8:
            marker = " <"
        
        print(f"{cls:<15} "
              f"{data['at_0.5']['precision']:>7.3f} "
              f"{data['at_0.5']['recall']:>7.3f} "
              f"{f1_05:>7.3f} "
              f"{data['optimal']['threshold']:>6.2f} "
              f"{f1_opt:>7.3f} "
              f"{data['gain']:>+7.3f}"
              f"{data['support']:>8}{marker}")
    
    # Summary
    f1_scores_05 = [d['at_0.5']['f1'] for d in results.values()]
    f1_scores_opt = [d['optimal']['f1'] for d in results.values()]
    
    print('-'*80)
    print(f"Macro F1 @ 0.5: {np.mean(f1_scores_05):.4f}")
    print(f"Macro F1 @ optimal: {np.mean(f1_scores_opt):.4f} (+{np.mean(f1_scores_opt) - np.mean(f1_scores_05):.4f})")
    
    if problem_classes:
        print(f"\n{'='*60}")
        print("PROBLEM CLASSES (F1 < 0.70):")
        print('='*60)
        for cls, f1, recall in sorted(problem_classes, key=lambda x: x[1]):
            print(f"  - {cls}: F1={f1:.3f}, Recall={recall:.3f}")
            if recall < 0.5:
                print(f"    RECOMMENDATION: Lower threshold, increase recall_boost_weight")
            elif recall < 0.7:
                print(f"    RECOMMENDATION: Use per-class gamma (higher for this class)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=str, default='runs/v5_multilabel/best_checkpoint.pt')
    parser.add_argument('--val-dir', type=str, default='F:/datasets/prod_v5_multilabel/val')
    parser.add_argument('--feature-cache', type=str, default='F:/feature_cache/train')
    parser.add_argument('--cache-mapping', type=str, default='F:/datasets/prod_v5_final/train/cache_mapping.npz')
    parser.add_argument('--sample-size', type=int, default=30000)
    args = parser.parse_args()
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Load model
    print(f"Loading checkpoint: {args.checkpoint}")
    model, ckpt = load_checkpoint(args.checkpoint, device)
    print(f"  Epoch: {ckpt.get('epoch', 'unknown')}")
    print(f"  Best F1: {ckpt.get('best_val_f1', 'unknown')}")
    
    # Load data
    print(f"\nLoading validation data...")
    val_dataset = CachedMultiLabelDataset(
        data_dir=args.val_dir,
        num_classes=12,
        class_names=DEFAULT_DRUM_COMPONENTS[:12],
        feature_cache_dir=args.feature_cache,
        cache_mapping_path=args.cache_mapping,
    )
    
    np.random.seed(42)
    if args.sample_size and args.sample_size < len(val_dataset):
        indices = np.random.choice(len(val_dataset), args.sample_size, replace=False)
        val_dataset = torch.utils.data.Subset(val_dataset, indices)
    
    loader = DataLoader(val_dataset, batch_size=512, num_workers=4, pin_memory=True)
    print(f"  Samples: {len(val_dataset)}")
    
    # Evaluate
    probs, preds, labels = evaluate_model(model, loader, device)
    
    # Analyze
    class_names = DEFAULT_DRUM_COMPONENTS[:12]
    results = analyze_per_class(probs, labels, class_names)
    print_analysis(results, "Main Model")
    
    # Check for EMA
    ema_path = Path(args.checkpoint).parent / "best_multilabel_model_ema.pt"
    if ema_path.exists():
        print(f"\n\nFound EMA model, evaluating...")
        ema_model, _ = load_checkpoint(str(ema_path), device)
        ema_probs, ema_preds, _ = evaluate_model(ema_model, loader, device)
        ema_results = analyze_per_class(ema_probs, labels, class_names)
        print_analysis(ema_results, "EMA Model")
    
    # Generate recommendations
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS TO REACH F1=0.90")
    print('='*80)
    
    avg_f1 = np.mean([d['at_0.5']['f1'] for d in results.values()])
    gap = 0.90 - avg_f1
    
    print(f"\nCurrent Macro F1: {avg_f1:.4f}")
    print(f"Target: 0.90")
    print(f"Gap: {gap:.4f} ({gap*100:.1f}%)")
    
    if gap > 0.15:
        print("\n1. RESTART TRAINING with recall_boost loss:")
        print("   python train_multilabel.py \\")
        print("       --loss-type recall_boost \\")
        print("       --use-per-class-gamma \\")
        print("       --recall-boost-weight 2.0 \\")
        print("       --resume runs/v5_multilabel/best_checkpoint.pt \\")
        print("       ...")
    
    print("\n2. USE OPTIMAL THRESHOLDS for inference:")
    print("   thresholds = {")
    for cls, data in results.items():
        print(f"       '{cls}': {data['optimal']['threshold']:.2f},")
    print("   }")
    
    print("\n3. FOCUS ON PROBLEM CLASSES:")
    problem_classes = [(c, d['at_0.5']['f1']) for c, d in results.items() if d['at_0.5']['f1'] < 0.75]
    for cls, f1 in sorted(problem_classes, key=lambda x: x[1]):
        print(f"   - {cls}: Current F1={f1:.3f}")


if __name__ == "__main__":
    main()
