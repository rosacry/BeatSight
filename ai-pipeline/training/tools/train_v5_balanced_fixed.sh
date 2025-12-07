#!/bin/bash
# =============================================================================
# BeatSight V5 Local Balanced Training - FIXED VERSION
# =============================================================================
# Previous version had CLASS COLLAPSE due to:
#   1. Uniform sampling + Focal gamma 3.0 = double emphasis on rare classes
#   2. This caused the model to ONLY learn hard examples, ignoring easy patterns
#   3. Result: 17/21 classes at 0% accuracy
#
# FIXES APPLIED:
#   1. NO FOCAL LOSS - use balanced sampling alone (it's already aggressive)
#   2. sqrt sampling (not uniform) - gentler rebalancing
#   3. Lower LR (0.0004) - stable with aggressive augmentations
#   4. Longer warmup (5 epochs) - let model learn basics first
#   5. Lower mixup/cutmix probability (0.3) - don't make early learning too hard
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source environment
if [ -f "$SCRIPT_DIR/beatsight_env.sh" ]; then
    source "$SCRIPT_DIR/beatsight_env.sh"
fi

BEATSIGHT_REPO_ROOT=${BEATSIGHT_REPO_ROOT:-$REPO_ROOT}
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-${BEATSIGHT_REPO_ROOT}/data}
BEATSIGHT_CACHE_DIR=${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup_consolidated}
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_CACHE_DIR}}

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/v5_local_balanced_fixed_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     BeatSight V5 Local Balanced Training - FIXED VERSION         ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ KEY FIXES FROM PREVIOUS FAILED RUN:                              ║"
echo "║   ❌ OLD: uniform sampling + focal gamma 3.0 = class collapse    ║"
echo "║   ✅ NEW: sqrt sampling + NO focal loss = stable learning        ║"
echo "║                                                                  ║"
echo "║   ❌ OLD: LR 0.002 + aggressive augmentation = chaotic gradients ║"
echo "║   ✅ NEW: LR 0.0004 + 5 epoch warmup = stable gradients          ║"
echo "║                                                                  ║"
echo "║   ❌ OLD: mixup prob 0.5 from epoch 0 = can't learn basics       ║"
echo "║   ✅ NEW: mixup prob 0.3 + warm restart = learns basics first    ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

cd "$BEATSIGHT_REPO_ROOT"

# GPU optimizations
export NVIDIA_TF32_OVERRIDE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
export CUDNN_BENCHMARK=1
export WANDB_RUN_GROUP=v5_local_balanced_fixed

# Check for existing checkpoint to resume from
CHECKPOINT_DIR="${RUN_DIR}/checkpoints"
LATEST_CHECKPOINT="${CHECKPOINT_DIR}/latest_checkpoint.pth"
RESUME_FLAG=""
if [[ -f "$LATEST_CHECKPOINT" ]]; then
    echo "📂 Found checkpoint: $LATEST_CHECKPOINT"
    echo "   Will resume training from this checkpoint"
    RESUME_FLAG="--resume-from $LATEST_CHECKPOINT"
fi

PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 100 \
    --batch-size 512 \
    --grad-accum-steps 3 \
    --lr 0.0004 \
    --num-workers 4 --val-num-workers 2 --prefetch-factor 4 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --cache-warmup --cache-warmup-samples 300000 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.1 --cutmix-alpha 0.3 --mixup-prob 0.3 \
    --specaugment drum \
    --label-smoothing 0.1 \
    --use-ema --ema-decay 0.9998 --ema-warmup-steps 5000 \
    --balanced-sampling --sampling-strategy sqrt --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 5 --warmup-lr-factor 0.05 \
    --early-stopping --early-stopping-patience 30 --early-stopping-min-delta 0.0005 --early-stopping-warmup 10 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    --checkpoint-every 5 \
    --checkpoint-every-batches 5000 \
    --val-fraction 0.1 \
    --wandb-project beatsight-v5 \
    ${RESUME_FLAG}

echo ""
echo "============================================================"
echo "  Training complete!"
echo "============================================================"
echo "  Output: $RUN_DIR"
echo "============================================================"
