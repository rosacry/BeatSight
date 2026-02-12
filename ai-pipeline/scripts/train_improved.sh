#!/bin/bash
# ============================================================================
# IMPROVED MULTI-LABEL TRAINING - Targeting F1 = 0.90
# ============================================================================
# 
# This script restarts training with improvements to address low-recall classes:
# - recall_boost loss with per-class gamma (higher for hihat_pedal, cross_stick)
# - recall_boost_weight = 2.0 to penalize false negatives more
# - Continued training from best checkpoint with new loss
#
# Usage:
#   ./train_improved.sh [resume|fresh]
#
# ============================================================================

cd /c/github/BeatSight/ai-pipeline

# Configuration
CHECKPOINT="runs/v5_multilabel/best_checkpoint.pt"
OUTPUT_DIR="runs/v5_multilabel_improved"
EPOCHS=40
BATCH_SIZE=128
LR=2e-5  # Lower LR for fine-tuning with new loss

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "=============================================="
echo "IMPROVED MULTI-LABEL TRAINING"
echo "=============================================="
echo "Output: $OUTPUT_DIR"
echo "Loss: recall_boost with per-class gamma"
echo "Recall boost weight: 2.0"
echo "=============================================="

# Main training command
python training/multilabel/train_multilabel.py \
    --train-dir "F:/datasets/prod_v5_multilabel/train" \
    --val-dir "F:/datasets/prod_v5_multilabel/val" \
    --source-dataset "F:/datasets/prod_v5_final" \
    --feature-cache-dir "F:/feature_cache" \
    \
    --model-version v5 \
    --v5-size large \
    --num-classes 12 \
    \
    --loss-type recall_boost \
    --use-per-class-gamma \
    --recall-boost-weight 2.0 \
    --gamma 2.0 \
    --label-smoothing 0.05 \
    \
    --epochs $EPOCHS \
    --batch-size $BATCH_SIZE \
    --lr $LR \
    --min-lr 1e-6 \
    --weight-decay 0.01 \
    \
    --scheduler cosine \
    --warmup-epochs 2 \
    \
    --use-amp \
    --amp-dtype bfloat16 \
    \
    --use-ema \
    --ema-decay 0.999 \
    \
    --use-swa \
    --swa-start 20 \
    --swa-lr 5e-6 \
    \
    --output-dir "$OUTPUT_DIR" \
    --checkpoint-every 2 \
    ${1:+--resume "$CHECKPOINT"}  # Add --resume if first arg is "resume"

echo ""
echo "Training complete! Check $OUTPUT_DIR for checkpoints."
