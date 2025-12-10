#!/bin/bash
# =============================================================================
# HYPERPARAMETER ABLATION STUDY
# =============================================================================
# Baseline: V7 = 54.27% (5% data, 5 epochs, uniform, lr 0.0001, batch 1024)
#
# We'll test ONE variable at a time to find what helps:
#   A) Learning rate: 0.00005 vs 0.0001 vs 0.0002
#   B) Batch size: 512 vs 1024 vs 2048 effective
#   C) Sampling: uniform vs sqrt vs inverse
#   D) Regularization: drop-path 0.1, weight-decay 0.01
#   E) More data: 10% vs 5%
#
# Each test: 5 epochs, 5% data (fast iteration)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [ -f "$SCRIPT_DIR/beatsight_env.sh" ]; then
    source "$SCRIPT_DIR/beatsight_env.sh"
fi

BEATSIGHT_REPO_ROOT=${BEATSIGHT_REPO_ROOT:-$REPO_ROOT}
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-${BEATSIGHT_REPO_ROOT}/data}
BEATSIGHT_CACHE_DIR=${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup_consolidated}
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_CACHE_DIR}}

ABLATION_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/ablation_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$ABLATION_DIR"

cd "$BEATSIGHT_REPO_ROOT"

export NVIDIA_TF32_OVERRIDE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
export CUDNN_BENCHMARK=1

# Common args (V7 baseline)
COMMON_ARGS="--dataset ${BEATSIGHT_DATASET_DIR} \
    --labels-cache-dir ${BEATSIGHT_DATA_ROOT}/dataset_index \
    --feature-cache-dir ${BEATSIGHT_CACHE_DIR} \
    --device cuda \
    --epochs 5 \
    --num-workers 4 --val-num-workers 2 --prefetch-factor 2 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.05 --val-fraction 0.05 \
    --subset-mode stratified --min-samples-per-class 50 \
    --model-version v5 --v5-size large --drop-path-rate 0.0 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.0 \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 0 --warmup-lr-factor 1.0 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.0 \
    --channels-last \
    --seed 42"

echo "========================================================================"
echo "  ABLATION STUDY - Finding Optimal Hyperparameters"
echo "========================================================================"
echo "Output: $ABLATION_DIR"
echo ""
echo "Baseline (V7): 54.27% balanced acc"
echo "  lr=0.0001, batch=256, grad-accum=4, uniform sampling"
echo ""
echo "Tests:"
echo "  A1: lr=0.00005 (lower)"
echo "  A2: lr=0.0002 (higher)"
echo "  B1: effective batch=512 (smaller)"
echo "  B2: effective batch=2048 (larger)"  
echo "  C1: sqrt sampling"
echo "  D1: drop-path=0.1 + weight-decay=0.01"
echo "  E1: 10% data"
echo "========================================================================"
echo ""

# -----------------------------------------------------------------------------
# A1: Lower learning rate (0.00005)
# -----------------------------------------------------------------------------
echo ""
echo "======== A1: lr=0.00005 ========"
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    $COMMON_ARGS \
    --batch-size 256 --grad-accum-steps 4 \
    --lr 0.00005 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --output "$ABLATION_DIR/A1_lr_lower" \
    2>&1 | tee "$ABLATION_DIR/A1_lr_lower.log"

# Extract best balanced acc
A1_RESULT=$(grep "Best validation accuracy" "$ABLATION_DIR/A1_lr_lower.log" | tail -1 | grep -oP '\d+\.\d+')
echo "A1 (lr=0.00005): $A1_RESULT%"

# -----------------------------------------------------------------------------
# A2: Higher learning rate (0.0002)
# -----------------------------------------------------------------------------
echo ""
echo "======== A2: lr=0.0002 ========"
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    $COMMON_ARGS \
    --batch-size 256 --grad-accum-steps 4 \
    --lr 0.0002 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --output "$ABLATION_DIR/A2_lr_higher" \
    2>&1 | tee "$ABLATION_DIR/A2_lr_higher.log"

A2_RESULT=$(grep "Best validation accuracy" "$ABLATION_DIR/A2_lr_higher.log" | tail -1 | grep -oP '\d+\.\d+')
echo "A2 (lr=0.0002): $A2_RESULT%"

# -----------------------------------------------------------------------------
# B1: Smaller effective batch (512)
# -----------------------------------------------------------------------------
echo ""
echo "======== B1: effective batch=512 ========"
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    $COMMON_ARGS \
    --batch-size 256 --grad-accum-steps 2 \
    --lr 0.0001 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --output "$ABLATION_DIR/B1_batch_smaller" \
    2>&1 | tee "$ABLATION_DIR/B1_batch_smaller.log"

B1_RESULT=$(grep "Best validation accuracy" "$ABLATION_DIR/B1_batch_smaller.log" | tail -1 | grep -oP '\d+\.\d+')
echo "B1 (batch=512): $B1_RESULT%"

# -----------------------------------------------------------------------------
# B2: Larger effective batch (2048)
# -----------------------------------------------------------------------------
echo ""
echo "======== B2: effective batch=2048 ========"
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    $COMMON_ARGS \
    --batch-size 256 --grad-accum-steps 8 \
    --lr 0.0001 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --output "$ABLATION_DIR/B2_batch_larger" \
    2>&1 | tee "$ABLATION_DIR/B2_batch_larger.log"

B2_RESULT=$(grep "Best validation accuracy" "$ABLATION_DIR/B2_batch_larger.log" | tail -1 | grep -oP '\d+\.\d+')
echo "B2 (batch=2048): $B2_RESULT%"

# -----------------------------------------------------------------------------
# C1: Sqrt sampling
# -----------------------------------------------------------------------------
echo ""
echo "======== C1: sqrt sampling ========"
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    $COMMON_ARGS \
    --batch-size 256 --grad-accum-steps 4 \
    --lr 0.0001 \
    --balanced-sampling --sampling-strategy sqrt --class-weights none \
    --output "$ABLATION_DIR/C1_sqrt_sampling" \
    2>&1 | tee "$ABLATION_DIR/C1_sqrt_sampling.log"

C1_RESULT=$(grep "Best validation accuracy" "$ABLATION_DIR/C1_sqrt_sampling.log" | tail -1 | grep -oP '\d+\.\d+')
echo "C1 (sqrt sampling): $C1_RESULT%"

# -----------------------------------------------------------------------------
# D1: Regularization (drop-path + weight-decay)
# -----------------------------------------------------------------------------
echo ""
echo "======== D1: drop-path=0.1, weight-decay=0.01 ========"
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 5 \
    --num-workers 4 --val-num-workers 2 --prefetch-factor 2 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.05 --val-fraction 0.05 \
    --subset-mode stratified --min-samples-per-class 50 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.0 \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 0 --warmup-lr-factor 1.0 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --seed 42 \
    --batch-size 256 --grad-accum-steps 4 \
    --lr 0.0001 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --output "$ABLATION_DIR/D1_regularization" \
    2>&1 | tee "$ABLATION_DIR/D1_regularization.log"

D1_RESULT=$(grep "Best validation accuracy" "$ABLATION_DIR/D1_regularization.log" | tail -1 | grep -oP '\d+\.\d+')
echo "D1 (regularization): $D1_RESULT%"

# -----------------------------------------------------------------------------
# E1: More data (10%)
# -----------------------------------------------------------------------------
echo ""
echo "======== E1: 10% data ========"
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 5 \
    --num-workers 4 --val-num-workers 2 --prefetch-factor 2 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.10 --val-fraction 0.10 \
    --subset-mode stratified --min-samples-per-class 50 \
    --model-version v5 --v5-size large --drop-path-rate 0.0 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.0 \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 0 --warmup-lr-factor 1.0 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.0 \
    --channels-last \
    --seed 42 \
    --batch-size 256 --grad-accum-steps 4 \
    --lr 0.0001 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --output "$ABLATION_DIR/E1_more_data" \
    2>&1 | tee "$ABLATION_DIR/E1_more_data.log"

E1_RESULT=$(grep "Best validation accuracy" "$ABLATION_DIR/E1_more_data.log" | tail -1 | grep -oP '\d+\.\d+')
echo "E1 (10% data): $E1_RESULT%"

# -----------------------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------------------
echo ""
echo "========================================================================"
echo "  ABLATION STUDY RESULTS"
echo "========================================================================"
echo ""
echo "BASELINE (V7): 54.27%"
echo ""
echo "Learning Rate:"
echo "  A1 (lr=0.00005): $A1_RESULT%"
echo "  A2 (lr=0.0002):  $A2_RESULT%"
echo ""
echo "Batch Size:"
echo "  B1 (eff=512):  $B1_RESULT%"
echo "  B2 (eff=2048): $B2_RESULT%"
echo ""
echo "Sampling:"
echo "  C1 (sqrt): $C1_RESULT%"
echo ""
echo "Regularization:"
echo "  D1 (drop-path+wd): $D1_RESULT%"
echo ""
echo "Data Scale:"
echo "  E1 (10% data): $E1_RESULT%"
echo ""
echo "========================================================================"
echo "Use the best hyperparameter(s) for final training!"
echo "========================================================================"
