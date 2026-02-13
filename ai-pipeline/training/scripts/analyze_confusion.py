#!/usr/bin/env python3
"""
Confusion Matrix Analysis
=========================
Identifies which class pairs are most confused and blocking 95%+ accuracy.

Usage:
    cd /c/github/BeatSight/ai-pipeline
    PYTHONPATH=. python training/scripts/analyze_confusion.py \
        --checkpoint runs/v5_phase1/best_drum_classifier.pth \
        --dataset "F:/datasets/prod_v5_definitive" \
        --feature-cache-dir "F:/feature_cache" \
        --num-samples 5000
"""

import argparse
import sys
import torch
import numpy as np
from pathlib import Path
from collections import defaultdict
import random

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.models.cnn_v5 import cnn_v5_large
from training.utils.consolidated_cache import ConsolidatedCacheReader

CLASS_NAMES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open", 
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom"
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--feature-cache-dir", required=True)
    parser.add_argument("--num-samples", type=int, default=5000)
    args = parser.parse_args()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Load model
    print("\n" + "="*70)
    print("  LOADING MODEL")
    print("="*70)
    
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    state = ckpt.get('model_state_dict', ckpt.get('state_dict', ckpt))
    model = cnn_v5_large(12, drop_path_rate=0.1, use_deep_supervision=False, use_multi_task=False)
    model.load_state_dict(state)
    model.eval().to(device)
    print(f"  ✓ Model loaded")
    
    # Load data
    print("\n" + "="*70)
    print("  LOADING VALIDATION DATA")
    print("="*70)
    
    dataset_path = Path(args.dataset)
    cache_path = Path(args.feature_cache_dir)
    
    labels = np.load(dataset_path / "val" / "val_labels_labels.npy")
    mapping = np.load(dataset_path / "val" / "cache_mapping.npz")
    
    train_cache = ConsolidatedCacheReader(cache_path / "train")
    val_cache = ConsolidatedCacheReader(cache_path / "val")
    
    valid_indices = np.where(mapping['valid'])[0]
    print(f"  ✓ {len(valid_indices):,} valid samples")
    
    # Sample for analysis
    np.random.seed(42)
    sample_indices = np.random.choice(valid_indices, min(args.num_samples, len(valid_indices)), replace=False)
    
    # Build confusion matrix
    print("\n" + "="*70)
    print(f"  ANALYZING {len(sample_indices):,} SAMPLES")
    print("="*70)
    
    confusion = np.zeros((12, 12), dtype=np.int32)
    confidence_when_wrong = defaultdict(list)
    confidence_when_right = defaultdict(list)
    
    with torch.no_grad():
        for i, idx in enumerate(sample_indices):
            if (i + 1) % 1000 == 0:
                print(f"  Processed {i+1}/{len(sample_indices)}...")
            
            cache_split = str(mapping['cache_split'][idx])
            cache = val_cache if cache_split == 'val' else train_cache
            
            feat = cache._read_sample(int(mapping['shard_ids'][idx]), int(mapping['offsets'][idx]))
            if isinstance(feat, np.ndarray):
                feat = torch.from_numpy(feat)
            feat = feat.unsqueeze(0).float().to(device)
            
            logits = model(feat)
            probs = torch.softmax(logits, dim=1)
            conf = probs.max().item()
            pred = logits.argmax(1).item()
            gt = int(labels[idx])
            
            confusion[gt, pred] += 1
            
            if pred == gt:
                confidence_when_right[gt].append(conf)
            else:
                confidence_when_wrong[(gt, pred)].append(conf)
    
    # Analysis
    print("\n" + "="*70)
    print("  CONFUSION MATRIX (rows=GT, cols=Pred)")
    print("="*70)
    
    # Print header
    print(f"\n{'':12s}", end="")
    for name in CLASS_NAMES:
        print(f"{name[:4]:>5s}", end="")
    print(f"{'Total':>7s} {'Acc':>6s}")
    print("-" * 90)
    
    per_class_acc = []
    for i, name in enumerate(CLASS_NAMES):
        row_total = confusion[i].sum()
        correct = confusion[i, i]
        acc = correct / row_total * 100 if row_total > 0 else 0
        per_class_acc.append(acc)
        
        print(f"{name:12s}", end="")
        for j in range(12):
            val = confusion[i, j]
            if i == j:
                print(f"\033[92m{val:5d}\033[0m", end="")  # Green for diagonal
            elif val > row_total * 0.05:  # >5% confusion
                print(f"\033[91m{val:5d}\033[0m", end="")  # Red for significant confusion
            elif val > 0:
                print(f"\033[93m{val:5d}\033[0m", end="")  # Yellow for minor confusion
            else:
                print(f"{val:5d}", end="")
        print(f"{row_total:7d} {acc:5.1f}%")
    
    balanced_acc = np.mean(per_class_acc)
    print(f"\n  Balanced Accuracy: {balanced_acc:.2f}%")
    
    # Top confusions
    print("\n" + "="*70)
    print("  TOP CONFUSIONS (Blocking Path to 95%)")
    print("="*70)
    
    confusions = []
    for gt in range(12):
        for pred in range(12):
            if gt != pred and confusion[gt, pred] > 0:
                row_total = confusion[gt].sum()
                pct = confusion[gt, pred] / row_total * 100
                confusions.append((gt, pred, confusion[gt, pred], pct))
    
    confusions.sort(key=lambda x: x[2], reverse=True)
    
    print(f"\n  {'Ground Truth':15s} → {'Predicted':15s} {'Count':>7s} {'% of GT':>8s} {'Avg Conf':>9s}")
    print("  " + "-" * 60)
    
    total_errors = sum(c[2] for c in confusions)
    cumulative = 0
    
    for gt, pred, count, pct in confusions[:15]:
        cumulative += count
        cumulative_pct = cumulative / total_errors * 100
        
        avg_conf = np.mean(confidence_when_wrong.get((gt, pred), [0]))
        
        print(f"  {CLASS_NAMES[gt]:15s} → {CLASS_NAMES[pred]:15s} {count:7d} {pct:7.1f}% {avg_conf:8.2f}")
    
    # Class-specific analysis
    print("\n" + "="*70)
    print("  PER-CLASS ANALYSIS")
    print("="*70)
    
    print(f"\n  {'Class':15s} {'Accuracy':>10s} {'Samples':>10s} {'Avg Conf':>10s} {'Status':>10s}")
    print("  " + "-" * 60)
    
    for i, name in enumerate(CLASS_NAMES):
        acc = per_class_acc[i]
        samples = confusion[i].sum()
        avg_conf = np.mean(confidence_when_right.get(i, [0]))
        
        if acc >= 95:
            status = "✓ GREAT"
        elif acc >= 90:
            status = "~ GOOD"
        elif acc >= 80:
            status = "⚠ IMPROVE"
        else:
            status = "✗ FOCUS"
        
        print(f"  {name:15s} {acc:9.1f}% {samples:10d} {avg_conf:9.2f} {status:>10s}")
    
    # Recommendations
    print("\n" + "="*70)
    print("  RECOMMENDATIONS TO REACH 95%")
    print("="*70)
    
    weak_classes = [(i, acc) for i, acc in enumerate(per_class_acc) if acc < 90]
    weak_classes.sort(key=lambda x: x[1])
    
    if weak_classes:
        print("\n  1. FOCUS ON THESE CLASSES:")
        for i, acc in weak_classes:
            top_confusion = max([(pred, confusion[i, pred]) for pred in range(12) if pred != i], key=lambda x: x[1])
            print(f"     - {CLASS_NAMES[i]} ({acc:.1f}%) - most confused with {CLASS_NAMES[top_confusion[0]]}")
    
    print("\n  2. TECHNIQUES TO TRY:")
    print("     - Mixup/SpecMix augmentation for confused pairs")
    print("     - Hard negative mining focused on top confusion pairs")
    print("     - Larger model (if not already using v5-xlarge)")
    print("     - Ensemble of 3-5 models with different seeds")
    print("     - Label smoothing (you have this in Phase 2)")
    print("     - Test-Time Augmentation (you have this in Phase 3)")
    
    gap_to_95 = 95 - balanced_acc
    print(f"\n  3. GAP TO 95%: {gap_to_95:.2f} percentage points")
    if gap_to_95 <= 3:
        print("     → Achievable with your current plan + ensembling")
    elif gap_to_95 <= 5:
        print("     → Challenging but possible with focused improvements")
    else:
        print("     → Will require significant additional work")


if __name__ == "__main__":
    main()
