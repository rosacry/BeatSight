#!/usr/bin/env python3
"""
Deep Analysis: What would it take to reach 0.90 F1?

This script analyzes the current model's performance and identifies
the exact improvements needed to reach the 0.90 F1 target.
"""

import sys
sys.path.insert(0, '.')

import numpy as np
import torch
from pathlib import Path

# Configuration
CHECKPOINT_PATH = "runs/v5_multilabel/best_checkpoint.pt"
VAL_DIR = Path("F:/datasets/prod_v5_multilabel/val")
SOURCE_DIR = Path("F:/datasets/prod_v5_final")
CACHE_DIR = Path("F:/feature_cache")

CLASS_NAMES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom"
]

def main():
    from training.multilabel.dataset import CachedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS
    from training.multilabel.train_multilabel import create_model
    from torch.utils.data import DataLoader
    from tqdm import tqdm
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load model
    print(f"\nLoading model from {CHECKPOINT_PATH}...")
    model = create_model(
        model_version='v5',
        num_classes=12,
        pretrained_checkpoint=CHECKPOINT_PATH,
        v5_size='large',
    )
    model = model.to(device)
    model.eval()
    
    # Load validation dataset
    print(f"\nLoading validation dataset...")
    val_dataset = CachedMultiLabelDataset(
        data_dir=VAL_DIR,
        num_classes=12,
        class_names=DEFAULT_DRUM_COMPONENTS[:12],
        feature_cache_dir=CACHE_DIR / "train",
        cache_mapping_path=SOURCE_DIR / "train" / "cache_mapping.npz",
        is_multilabel=True,
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=512,
        shuffle=False,
        num_workers=4,
        pin_memory=True,
    )
    
    # Sample only 100k for faster analysis
    max_samples = 100000
    print(f"Validation samples: {len(val_dataset):,} (analyzing first {max_samples:,})")
    
    # Collect all predictions and labels
    print("\nRunning inference on validation set...")
    all_probs = []
    all_labels = []
    
    with torch.no_grad():
        samples_processed = 0
        for features, labels in tqdm(val_loader, desc="Inference"):
            features = features.to(device)
            logits = model(features)
            probs = torch.sigmoid(logits)
            all_probs.append(probs.cpu())
            all_labels.append(labels)
            samples_processed += len(features)
            if samples_processed >= max_samples:
                break
    
    probs = torch.cat(all_probs, dim=0).numpy()
    labels = torch.cat(all_labels, dim=0).numpy()
    
    print(f"\nProbs shape: {probs.shape}")
    print(f"Labels shape: {labels.shape}")
    
    # Current metrics at threshold 0.5
    print("\n" + "=" * 70)
    print("CURRENT PERFORMANCE (threshold=0.5)")
    print("=" * 70)
    
    preds = (probs >= 0.5).astype(np.float32)
    
    def compute_f1(p, r):
        return 2 * p * r / (p + r + 1e-8)
    
    total_tp = 0
    total_fp = 0
    total_fn = 0
    
    class_metrics = []
    for i, name in enumerate(CLASS_NAMES):
        tp = np.sum((preds[:, i] == 1) & (labels[:, i] == 1))
        fp = np.sum((preds[:, i] == 1) & (labels[:, i] == 0))
        fn = np.sum((preds[:, i] == 0) & (labels[:, i] == 1))
        
        precision = tp / (tp + fp + 1e-8)
        recall = tp / (tp + fn + 1e-8)
        f1 = compute_f1(precision, recall)
        support = int(np.sum(labels[:, i]))
        
        class_metrics.append({
            'name': name, 'tp': tp, 'fp': fp, 'fn': fn,
            'precision': precision, 'recall': recall, 'f1': f1, 'support': support
        })
        
        total_tp += tp
        total_fp += fp
        total_fn += fn
    
    micro_precision = total_tp / (total_tp + total_fp + 1e-8)
    micro_recall = total_tp / (total_tp + total_fn + 1e-8)
    micro_f1 = compute_f1(micro_precision, micro_recall)
    macro_f1 = np.mean([m['f1'] for m in class_metrics])
    
    print(f"\nMicro F1: {micro_f1:.4f} (P={micro_precision:.4f}, R={micro_recall:.4f})")
    print(f"Macro F1: {macro_f1:.4f}")
    
    print(f"\n{'Class':<15} {'Prec':>8} {'Rec':>8} {'F1':>8} {'Support':>10} {'FN (missed)':>12}")
    print("-" * 65)
    
    # Sort by F1 to show worst classes first
    for m in sorted(class_metrics, key=lambda x: x['f1']):
        print(f"{m['name']:<15} {m['precision']:>8.3f} {m['recall']:>8.3f} {m['f1']:>8.3f} {m['support']:>10,} {m['fn']:>12,}")
    
    # What would 0.90 Micro F1 require?
    print("\n" + "=" * 70)
    print("REQUIREMENTS TO REACH 0.90 MICRO F1")
    print("=" * 70)
    
    current_tp = total_tp
    current_fp = total_fp
    current_fn = total_fn
    
    # To get 0.90 F1, we need: 2*P*R/(P+R) = 0.90
    # If we assume P=R (balanced), then P=R=0.90
    # Current: P={micro_precision:.4f}, R={micro_recall:.4f}
    
    print(f"\nCurrent: TP={current_tp:,}, FP={current_fp:,}, FN={current_fn:,}")
    print(f"Current: Precision={micro_precision:.4f}, Recall={micro_recall:.4f}, F1={micro_f1:.4f}")
    
    # Calculate how many FN we need to convert to TP to reach 0.90 recall
    # (assuming precision stays the same)
    target_f1 = 0.90
    
    # Option 1: Only improve recall (fix false negatives)
    # F1 = 2PR/(P+R) = 0.90, with P fixed
    # R = 0.90 * P / (2P - 0.90)
    if 2 * micro_precision - target_f1 > 0:
        required_recall = target_f1 * micro_precision / (2 * micro_precision - target_f1)
        required_recall = min(required_recall, 1.0)
        # Recall = TP / (TP + FN), so TP = Recall * (TP + FN)
        # New FN = (TP + FN) - TP_new = (TP + FN) * (1 - required_recall)
        total_positives = current_tp + current_fn
        required_tp = int(required_recall * total_positives)
        fn_to_fix = required_tp - current_tp
        print(f"\nOption 1: Keep precision constant ({micro_precision:.4f})")
        print(f"  Required recall: {required_recall:.4f}")
        print(f"  FN to convert to TP: {fn_to_fix:,} ({100*fn_to_fix/current_fn:.1f}% of current FN)")
    
    # Option 2: Balance P and R at 0.90
    # Need TP / (TP + FP) = 0.90 AND TP / (TP + FN) = 0.90
    target_pr = 0.90
    total_positives = current_tp + current_fn  # Ground truth positives
    required_tp_balanced = int(target_pr * total_positives)
    required_fp_balanced = int(required_tp_balanced / target_pr - required_tp_balanced)
    
    print(f"\nOption 2: Achieve P=R=0.90")
    print(f"  Required TP: {required_tp_balanced:,} (current: {current_tp:,}, need +{required_tp_balanced - current_tp:,})")
    print(f"  Max allowed FP: {required_fp_balanced:,} (current: {current_fp:,}, need -{current_fp - required_fp_balanced:,})")
    print(f"  Max allowed FN: {total_positives - required_tp_balanced:,} (current: {current_fn:,})")
    
    # Per-class breakdown of what needs to improve
    print("\n" + "=" * 70)
    print("PER-CLASS IMPROVEMENTS NEEDED FOR 0.90 F1")
    print("=" * 70)
    
    total_fn_to_fix = 0
    total_fp_to_fix = 0
    
    print(f"\n{'Class':<15} {'Curr F1':>8} {'Target':>8} {'FN→TP needed':>14} {'FP→TN needed':>14}")
    print("-" * 65)
    
    for m in sorted(class_metrics, key=lambda x: x['f1']):
        target_class_f1 = 0.90
        current_f1 = m['f1']
        
        # How many FN need to become TP to reach 0.90 F1 for this class?
        # Assuming FP stays constant
        tp, fp, fn = m['tp'], m['fp'], m['fn']
        
        # F1 = 2*TP / (2*TP + FP + FN) = 0.90
        # 2*TP = 0.90 * (2*TP + FP + FN)
        # 2*TP - 1.8*TP = 0.90 * (FP + FN)
        # 0.2*TP = 0.90 * (FP + FN)
        # TP = 4.5 * (FP + FN)
        
        # If we only convert FN to TP:
        # Let x = FN converted to TP
        # New TP = tp + x, New FN = fn - x
        # F1 = 2*(tp+x) / (2*(tp+x) + fp + (fn-x)) = 0.90
        # 2*(tp+x) = 0.90 * (2*(tp+x) + fp + fn - x)
        # 2*(tp+x) = 0.90 * (2*tp + 2*x + fp + fn - x)
        # 2*(tp+x) = 0.90 * (2*tp + x + fp + fn)
        # 2*tp + 2*x = 1.8*tp + 0.9*x + 0.9*fp + 0.9*fn
        # 2*x - 0.9*x = 1.8*tp - 2*tp + 0.9*fp + 0.9*fn
        # 1.1*x = -0.2*tp + 0.9*fp + 0.9*fn
        # x = (-0.2*tp + 0.9*fp + 0.9*fn) / 1.1
        
        x = (-0.2 * tp + 0.9 * fp + 0.9 * fn) / 1.1
        x = max(0, x)  # Can't be negative
        x = min(x, fn)  # Can't fix more FN than exist
        
        # Also calculate FP reduction needed if we can't fix enough FN
        # If x = fn (all FN fixed), what FP reduction is needed?
        new_tp = tp + fn  # All FN become TP
        # F1 = 2*new_tp / (2*new_tp + new_fp) = 0.90
        # new_fp = 2*new_tp/0.90 - 2*new_tp = 2*new_tp*(1/0.90 - 1) = 2*new_tp*0.111
        max_fp_for_perfect_recall = 2 * new_tp * (1/0.9 - 1)
        fp_reduction = max(0, fp - max_fp_for_perfect_recall)
        
        fn_to_fix = int(x)
        fp_to_fix = int(fp_reduction) if fn_to_fix >= fn else 0
        
        total_fn_to_fix += fn_to_fix
        total_fp_to_fix += fp_to_fix
        
        print(f"{m['name']:<15} {current_f1:>8.3f} {target_class_f1:>8.3f} {fn_to_fix:>14,} {fp_to_fix:>14,}")
    
    print("-" * 65)
    print(f"{'TOTAL':<15} {'':<8} {'':<8} {total_fn_to_fix:>14,} {total_fp_to_fix:>14,}")
    
    # Analyze probability distributions for missed samples
    print("\n" + "=" * 70)
    print("PROBABILITY ANALYSIS OF MISSED SAMPLES (False Negatives)")
    print("=" * 70)
    
    print(f"\n{'Class':<15} {'FN':>8} {'p≥0.3':>10} {'p≥0.4':>10} {'p≥0.45':>10} {'Mean p':>10}")
    print("-" * 65)
    
    easy_fixes = 0  # FN with p >= 0.4 (just need threshold tuning)
    hard_fixes = 0  # FN with p < 0.3 (model doesn't see them)
    
    for i, name in enumerate(CLASS_NAMES):
        fn_mask = (preds[:, i] == 0) & (labels[:, i] == 1)
        fn_probs = probs[fn_mask, i]
        
        if len(fn_probs) > 0:
            p_ge_30 = np.sum(fn_probs >= 0.3)
            p_ge_40 = np.sum(fn_probs >= 0.4)
            p_ge_45 = np.sum(fn_probs >= 0.45)
            mean_p = np.mean(fn_probs)
            
            easy_fixes += p_ge_40
            hard_fixes += np.sum(fn_probs < 0.3)
            
            print(f"{name:<15} {len(fn_probs):>8,} {p_ge_30:>10,} {p_ge_40:>10,} {p_ge_45:>10,} {mean_p:>10.3f}")
    
    print("-" * 65)
    print(f"\nEasy fixes (p≥0.4, threshold tuning): {easy_fixes:,} ({100*easy_fixes/current_fn:.1f}% of FN)")
    print(f"Hard fixes (p<0.3, model can't see): {hard_fixes:,} ({100*hard_fixes/current_fn:.1f}% of FN)")
    
    # Final recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS TO REACH 0.90 F1")
    print("=" * 70)
    
    print("""
IMMEDIATE GAINS (can get you to ~0.80-0.82):
1. Threshold optimization: Use per-class thresholds instead of 0.5
   - Already found optimal thresholds that gave +2% Macro F1
   - Easy FN fixes: {easy_fixes:,} samples just need lower thresholds

2. Continue balanced sampling training (current approach)
   - Epoch 4 F1: 0.7696 (+0.12% over baseline)
   - May plateau around 0.78-0.80

MEDIUM EFFORT (can get you to ~0.85):
3. Hard Example Mining: Fine-tune on samples where model is uncertain (p=0.3-0.5)
   - Focus training on confusing samples
   - Can be combined with balanced sampling

4. Label smoothing adjustments: Current 0.05 may be too aggressive
   - Try 0.02 or remove for rare classes

5. Asymmetric loss tuning: Less aggressive than previous attempt
   - gamma_pos=1.0, gamma_neg=3.0 (not 5.0)

HARDER BUT NECESSARY FOR 0.90+:
6. Architecture changes:
   - Add class-specific attention heads
   - Larger model (more capacity for rare classes)
   
7. Data augmentation for rare classes:
   - Pitch shifting for hihat_pedal
   - Time stretching for cross_stick
   - Mixup between rare class samples

8. The "hard fixes" problem: {hard_fixes:,} samples where model predicts p<0.3
   - These are truly ambiguous or mislabeled
   - May need manual review of training data quality
""".format(easy_fixes=easy_fixes, hard_fixes=hard_fixes))


if __name__ == '__main__':
    main()
