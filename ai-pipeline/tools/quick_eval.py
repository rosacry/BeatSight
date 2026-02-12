#!/usr/bin/env python3
"""Quick per-class evaluation for multi-label model."""
import os
import sys
from pathlib import Path

# Add ai-pipeline to path BEFORE any imports
AI_PIPELINE = Path(__file__).parent.parent
sys.path.insert(0, str(AI_PIPELINE))
os.chdir(AI_PIPELINE)

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from sklearn.metrics import precision_recall_fscore_support

from training.models.cnn_v5 import DrumClassifierCNNv5, cnn_v5_large
from training.multilabel.dataset import CachedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS


class MultiLabelDrumClassifier(nn.Module):
    """Wrapper that adapts single-label classifiers for multi-label output."""
    
    def __init__(self, backbone: nn.Module, num_classes: int = 12):
        super().__init__()
        self.backbone = backbone
        self.num_classes = num_classes
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)

CLASS_NAMES = DEFAULT_DRUM_COMPONENTS

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    
    # Load model
    checkpoint_path = Path("runs/v5_multilabel/best_checkpoint.pt")
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Create backbone with matching config (no aux heads)
    backbone = cnn_v5_large(num_classes=12, use_deep_supervision=False, use_multi_task=False)
    model = MultiLabelDrumClassifier(backbone=backbone, num_classes=12)
    model.load_state_dict(ckpt["model_state_dict"])
    model = model.to(device)
    model.eval()
    
    print(f"Loaded checkpoint from epoch {ckpt.get('epoch', '?')}")
    print(f"Best F1: {ckpt.get('best_val_f1', '?')}")
    
    # Skip EMA for now - different state dict format
    ema_model = None
    # EMA state_dict contains wrapper class - would need special handling
    print("Skipping EMA model (different state format)")
    
    # Load validation data
    val_dir = Path("F:/datasets/prod_v5_multilabel/val")
    feature_cache = Path("F:/feature_cache")
    
    dataset = CachedMultiLabelDataset(
        data_dir=val_dir,
        num_classes=12,
        feature_cache_dir=feature_cache,
        is_multilabel=True,
    )
    print(f"Val dataset: {len(dataset)} samples")
    
    # Sample subset for quick eval
    n_samples = min(10000, len(dataset))
    indices = np.random.default_rng(42).choice(len(dataset), n_samples, replace=False)
    
    all_preds = []
    all_probs = []
    all_labels = []
    all_preds_ema = []
    all_probs_ema = []
    
    print(f"\nEvaluating {n_samples} samples...")
    batch_size = 256
    
    with torch.no_grad():
        for i in range(0, n_samples, batch_size):
            batch_indices = indices[i:i+batch_size]
            features = []
            labels = []
            
            for idx in batch_indices:
                feat, label = dataset[int(idx)]
                features.append(feat)
                labels.append(label)
            
            features = torch.stack(features).to(device)
            labels = torch.stack(labels).numpy()
            
            # Main model
            logits = model(features)
            probs = torch.sigmoid(logits).cpu().numpy()
            preds = (probs > 0.5).astype(int)
            
            all_probs.append(probs)
            all_preds.append(preds)
            all_labels.append(labels)
            
            # EMA model
            if ema_model is not None:
                logits_ema = ema_model(features)
                probs_ema = torch.sigmoid(logits_ema).cpu().numpy()
                preds_ema = (probs_ema > 0.5).astype(int)
                all_probs_ema.append(probs_ema)
                all_preds_ema.append(preds_ema)
            
            if (i // batch_size + 1) % 10 == 0:
                print(f"  Batch {i // batch_size + 1}/{(n_samples + batch_size - 1) // batch_size}")
    
    all_probs = np.vstack(all_probs)
    all_preds = np.vstack(all_preds)
    all_labels = np.vstack(all_labels)
    
    # Per-class metrics
    print("\n" + "="*70)
    print("PER-CLASS METRICS @ threshold=0.5 (MAIN MODEL)")
    print("="*70)
    print(f"{'Class':<15} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-"*70)
    
    f1_scores = []
    for i, name in enumerate(CLASS_NAMES):
        p, r, f1, _ = precision_recall_fscore_support(
            all_labels[:, i], all_preds[:, i], average='binary', zero_division=0
        )
        support = all_labels[:, i].sum()
        status = "✓" if f1 >= 0.80 else "⚠" if f1 >= 0.65 else "✗"
        print(f"{name:<15} {p:>10.3f} {r:>10.3f} {f1:>10.3f} {support:>10.0f} {status}")
        f1_scores.append(f1)
    
    macro_f1 = np.mean(f1_scores)
    print("-"*70)
    print(f"{'Macro F1:':<15} {'':<10} {'':<10} {macro_f1:>10.4f}")
    
    # Find optimal thresholds
    print("\n" + "="*70)
    print("OPTIMAL THRESHOLDS (per-class)")
    print("="*70)
    print(f"{'Class':<15} {'Optimal':>10} {'F1@opt':>10} {'Gain':>10}")
    print("-"*70)
    
    optimal_thresholds = []
    optimal_f1s = []
    for i, name in enumerate(CLASS_NAMES):
        best_f1 = 0
        best_t = 0.5
        for t in np.arange(0.20, 0.80, 0.05):
            preds_t = (all_probs[:, i] > t).astype(int)
            _, _, f1, _ = precision_recall_fscore_support(
                all_labels[:, i], preds_t, average='binary', zero_division=0
            )
            if f1 > best_f1:
                best_f1 = f1
                best_t = t
        
        gain = best_f1 - f1_scores[i]
        print(f"{name:<15} {best_t:>10.2f} {best_f1:>10.3f} {'+' if gain >= 0 else ''}{gain:>9.3f}")
        optimal_thresholds.append(best_t)
        optimal_f1s.append(best_f1)
    
    macro_f1_opt = np.mean(optimal_f1s)
    print("-"*70)
    print(f"{'Macro F1:':<15} {'':<10} {macro_f1_opt:>10.4f} {'+' if macro_f1_opt > macro_f1 else ''}{macro_f1_opt - macro_f1:>9.3f}")
    
    # EMA model if available
    if ema_model is not None:
        all_probs_ema = np.vstack(all_probs_ema)
        all_preds_ema = np.vstack(all_preds_ema)
        
        print("\n" + "="*70)
        print("EMA MODEL @ threshold=0.5")
        print("="*70)
        
        f1_ema = []
        for i, name in enumerate(CLASS_NAMES):
            _, _, f1, _ = precision_recall_fscore_support(
                all_labels[:, i], all_preds_ema[:, i], average='binary', zero_division=0
            )
            f1_ema.append(f1)
        
        print(f"Macro F1: {np.mean(f1_ema):.4f}")
        
        # Optimal thresholds for EMA
        ema_opt_f1s = []
        for i in range(12):
            best_f1 = 0
            for t in np.arange(0.20, 0.80, 0.05):
                preds_t = (all_probs_ema[:, i] > t).astype(int)
                _, _, f1, _ = precision_recall_fscore_support(
                    all_labels[:, i], preds_t, average='binary', zero_division=0
                )
                if f1 > best_f1:
                    best_f1 = f1
            ema_opt_f1s.append(best_f1)
        
        print(f"Macro F1 @ optimal thresholds: {np.mean(ema_opt_f1s):.4f}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Main model @ 0.5:        Macro F1 = {macro_f1:.4f}")
    print(f"Main model @ optimal:    Macro F1 = {macro_f1_opt:.4f} (+{macro_f1_opt - macro_f1:.3f})")
    if ema_model is not None:
        print(f"EMA model @ 0.5:         Macro F1 = {np.mean(f1_ema):.4f}")
        print(f"EMA model @ optimal:     Macro F1 = {np.mean(ema_opt_f1s):.4f}")
    print(f"\nGap to 0.90 target: {0.90 - macro_f1_opt:.3f}")
    
    # Top issues
    print("\n" + "="*70)
    print("TOP ISSUES (classes with F1 < 0.75)")
    print("="*70)
    issues = [(name, f1) for name, f1 in zip(CLASS_NAMES, f1_scores) if f1 < 0.75]
    issues.sort(key=lambda x: x[1])
    for name, f1 in issues:
        print(f"  {name}: F1 = {f1:.3f}")
    
    # Recommendations
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    print("1. Use per-class thresholds (configured in threshold_config.py)")
    print("2. Train with --loss-type recall_boost --use-per-class-gamma")
    print("3. Consider increasing recall_boost_weight for hihat_pedal")
    print("4. Wait for SWA to kick in (epoch 24)")

if __name__ == "__main__":
    main()
