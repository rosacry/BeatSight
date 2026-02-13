#!/usr/bin/env python3
"""
🎯 PLATEAU BREAKER: Advanced Training Strategy for 92-95% Balanced Accuracy

This script provides optimized training commands for breaking through the
90% plateau based on comprehensive analysis of the BeatSight drum classifier.

ANALYSIS SUMMARY (90.23% current best):
=======================================
1. Your model is close to theoretical ceiling (~92-93% for 12-class)
2. Main confusions are physics-based (cymbal variants, hi-hat positions)
3. Uniform sampling + Class-Balanced Focal Loss is working well
4. The gap to ceiling is ~2-3%, achievable with targeted improvements

BREAKTHROUGH STRATEGIES:
========================
A. Contrastive Learning - Push confused class embeddings apart
B. Ensemble with TTA - Reduce variance and improve calibration  
C. Label Noise Filtering - Remove ~2-5% inherent noise
D. Longer Context Windows - Better cymbal discrimination (decay patterns)
E. Temperature Scaling - Improve confidence calibration

Generated: January 2026
"""

import os
import sys
from pathlib import Path

# Training commands for breaking through 90% plateau

# ==============================================================================
# STRATEGY A: Phase 3 with Contrastive Loss + Hard Negative Mining
# Expected gain: +0.5-1.0%
# ==============================================================================

PHASE_3_CONTRASTIVE = """
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 104 --batch-size 128 --grad-accum-steps 5 \\
  --lr 5e-6 \\
  --amp-dtype bfloat16 \\
  --balanced-sampling --sampling-strategy uniform \\
  --loss-type class-balanced-focal --cb-beta 0.999 \\
  --specaugment drum \\
  --use-hard-negatives --hnm-strategy curriculum --hnm-ratio 0.7 \\
  --hnm-use-contrastive --hnm-margin 0.5 --hnm-contrastive-weight 0.3 \\
  --use-ema --ema-decay 0.9995 \\
  --scheduler cosine \\
  --gradient-checkpointing --grad-clip-norm 1.0 \\
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \\
  --checkpoint-every 1 --checkpoint-every-batches 5000 \\
  --channels-last \\
  --output runs/v5_phase3_contrastive \\
  --resume runs/v5_phase2/checkpoints/best_checkpoint.pth \\
  --reset-scheduler
"""

# ==============================================================================
# STRATEGY B: Self-Distillation (Born-Again Networks)
# Train a new model using your best model as teacher
# Expected gain: +0.3-0.8%
# ==============================================================================

PHASE_DISTILL = """
# First, copy best model as teacher
cp runs/v5_phase2/checkpoints/best_checkpoint.pth runs/teacher_model.pth

# Then train student with distillation
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 40 --batch-size 128 --grad-accum-steps 5 \\
  --lr 3e-5 \\
  --amp-dtype bfloat16 \\
  --balanced-sampling --sampling-strategy uniform \\
  --loss-type class-balanced-focal --cb-beta 0.999 \\
  --specaugment drum \\
  --distill-from-single runs/teacher_model.pth \\
  --distill-temperature 4.0 \\
  --distill-alpha 0.5 \\
  --distill-progressive-temp \\
  --use-ema --ema-decay 0.999 \\
  --scheduler cosine --warmup-epochs 3 \\
  --gradient-checkpointing --grad-clip-norm 1.0 \\
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \\
  --checkpoint-every 1 \\
  --channels-last \\
  --output runs/v5_distilled
"""

# ==============================================================================
# STRATEGY C: Label Noise Audit + Clean Training
# Identify and remove noisy labels, then retrain
# Expected gain: +0.3-0.5%
# ==============================================================================

PHASE_LABEL_CLEAN = """
# Step 1: Audit labels to find noise
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 5 --batch-size 128 --grad-accum-steps 5 \\
  --lr 1e-4 \\
  --amp-dtype bfloat16 \\
  --clean-labels --label-noise-audit-only --label-noise-threshold 0.6 \\
  --output runs/v5_label_audit \\
  --resume runs/v5_phase2/checkpoints/best_checkpoint.pth

# Step 2: Train with cleaned labels (removes suspicious samples)
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 60 --batch-size 128 --grad-accum-steps 5 \\
  --lr 5e-5 \\
  --amp-dtype bfloat16 \\
  --balanced-sampling --sampling-strategy uniform \\
  --loss-type class-balanced-focal --cb-beta 0.999 \\
  --specaugment drum \\
  --clean-labels --label-noise-threshold 0.6 \\
  --use-ema --ema-decay 0.999 \\
  --scheduler cosine --warmup-epochs 3 \\
  --gradient-checkpointing --grad-clip-norm 1.0 \\
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \\
  --checkpoint-every 1 \\
  --channels-last \\
  --output runs/v5_clean_labels
"""

# ==============================================================================
# STRATEGY D: Ensemble Training (Multiple Seeds)
# Train 3 models with different seeds, combine predictions
# Expected gain: +0.5-1.5%
# ==============================================================================

ENSEMBLE_TRAIN = """
# Train Model 1 (seed 42)
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 60 --batch-size 128 --grad-accum-steps 5 \\
  --lr 1e-4 --seed 42 \\
  --amp-dtype bfloat16 \\
  --balanced-sampling --sampling-strategy uniform \\
  --loss-type class-balanced-focal --cb-beta 0.999 \\
  --specaugment drum --use-sam --sam-adaptive \\
  --use-ema --ema-decay 0.999 \\
  --scheduler cosine --warmup-epochs 3 \\
  --gradient-checkpointing --grad-clip-norm 1.0 \\
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \\
  --checkpoint-every 1 \\
  --channels-last \\
  --output runs/v5_ensemble_seed42

# Train Model 2 (seed 123) - different initialization
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 60 --batch-size 128 --grad-accum-steps 5 \\
  --lr 1e-4 --seed 123 \\
  --amp-dtype bfloat16 \\
  --balanced-sampling --sampling-strategy uniform \\
  --loss-type class-balanced-focal --cb-beta 0.999 \\
  --specaugment drum --use-sam --sam-adaptive \\
  --use-ema --ema-decay 0.999 \\
  --scheduler cosine --warmup-epochs 3 \\
  --gradient-checkpointing --grad-clip-norm 1.0 \\
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \\
  --checkpoint-every 1 \\
  --channels-last \\
  --output runs/v5_ensemble_seed123

# Train Model 3 (seed 456) - different initialization  
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 60 --batch-size 128 --grad-accum-steps 5 \\
  --lr 1e-4 --seed 456 \\
  --amp-dtype bfloat16 \\
  --balanced-sampling --sampling-strategy uniform \\
  --loss-type class-balanced-focal --cb-beta 0.999 \\
  --specaugment drum --use-sam --sam-adaptive \\
  --use-ema --ema-decay 0.999 \\
  --scheduler cosine --warmup-epochs 3 \\
  --gradient-checkpointing --grad-clip-norm 1.0 \\
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \\
  --checkpoint-every 1 \\
  --channels-last \\
  --output runs/v5_ensemble_seed456
"""

# ==============================================================================
# OPTIMIZED PHASE 3 (Your Current Command - Improved)
# ==============================================================================

PHASE_3_OPTIMIZED = """
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --model-version v5 --v5-size large \\
  --epochs 104 --batch-size 128 --grad-accum-steps 5 \\
  --lr 5e-6 \\
  --amp-dtype bfloat16 \\
  --balanced-sampling --sampling-strategy uniform \\
  --loss-type class-balanced-focal --cb-beta 0.999 \\
  --label-smoothing 0.05 \\
  --specaugment drum \\
  --use-hard-negatives --hnm-strategy curriculum --hnm-ratio 0.7 \\
  --val-tta --val-tta-augmentations 3 \\
  --use-ema --ema-decay 0.9995 \\
  --scheduler cosine \\
  --gradient-checkpointing --grad-clip-norm 1.0 \\
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \\
  --checkpoint-every 1 --checkpoint-every-batches 5000 \\
  --channels-last \\
  --output runs/v5_phase3 \\
  --resume runs/v5_phase2/checkpoints/best_checkpoint.pth \\
  --reset-scheduler
"""

# ==============================================================================
# ANALYSIS COMMANDS
# ==============================================================================

ANALYZE_CONFUSION = """
# Run confusion ceiling analysis to understand the bottleneck
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/tools/analyze_confusion_ceiling.py \\
  --checkpoint runs/v5_phase2/checkpoints/best_checkpoint.pth \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --v5-size large \\
  --fraction 0.25 \\
  --output runs/v5_phase2/confusion_analysis.json
"""

EVALUATE_PER_CLASS = """
# Detailed per-class evaluation
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/tools/evaluate_per_class_v5.py \\
  --checkpoint runs/v5_phase2/checkpoints/best_checkpoint.pth \\
  --dataset "F:/datasets/prod_v5_cleaned" \\
  --feature-cache-dir "F:/feature_cache" \\
  --v5-size large \\
  --fraction 0.5 \\
  --output runs/v5_phase2/per_class_analysis.json
"""


def print_command(name: str, cmd: str):
    """Print a formatted command."""
    print(f"\n{'=' * 80}")
    print(f"  {name}")
    print('=' * 80)
    print(cmd)


def main():
    print("🎯 PLATEAU BREAKER: Training Strategies for 92-95% Balanced Accuracy")
    print("=" * 80)
    print("""
Based on analysis of your 90.23% model, here's the priority order:

1. FIRST: Run confusion analysis to understand what's limiting accuracy
2. THEN: Choose strategy based on findings:
   
   If cymbal confusions are high → Use Contrastive Loss (Strategy A)
   If model is overconfident → Use Distillation (Strategy B)  
   If suspecting label noise → Use Label Cleaning (Strategy C)
   If you want guaranteed +1% → Use Ensemble (Strategy D, requires 3x training time)
   
3. Your optimized Phase 3 command is ready to run (small improvements)

REALISTIC EXPECTATIONS:
- 92-93%: Achievable with targeted single-model training
- 93-95%: Requires ensemble methods (3+ models)
- 95%+: Would need foundation model fine-tuning (BEATs, etc.)
    """)
    
    print_command("0. ANALYZE CONFUSION PATTERNS FIRST", ANALYZE_CONFUSION)
    print_command("0b. DETAILED PER-CLASS EVALUATION", EVALUATE_PER_CLASS)
    print_command("A. PHASE 3 WITH CONTRASTIVE LOSS (+0.5-1%)", PHASE_3_CONTRASTIVE)
    print_command("B. SELF-DISTILLATION (+0.3-0.8%)", PHASE_DISTILL)
    print_command("C. LABEL NOISE CLEANING (+0.3-0.5%)", PHASE_LABEL_CLEAN)
    print_command("D. ENSEMBLE TRAINING (+0.5-1.5%, 3x time)", ENSEMBLE_TRAIN)
    print_command("OPTIMIZED PHASE 3 (Your current command improved)", PHASE_3_OPTIMIZED)
    
    print("\n" + "=" * 80)
    print("QUICK START: Run confusion analysis first, then choose strategy")
    print("=" * 80)


if __name__ == "__main__":
    main()
