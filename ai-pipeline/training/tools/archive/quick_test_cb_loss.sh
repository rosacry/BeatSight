#!/bin/bash
# =============================================================================
# Quick 5-epoch test using CLASS-BALANCED LOSS (CVPR 2019)
# =============================================================================
# Alternative to balanced sampling: uses loss reweighting instead
# Compares: sqrt sampling vs class-balanced loss for 630:1 class imbalance
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/cb_loss_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     QUICK TEST - Class-Balanced Loss (CVPR 2019)                 ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ CONFIGURATION:                                                   ║"
echo "║   • Class-Balanced CE Loss (--loss-type class-balanced)          ║"
echo "║   • Beta 0.9999 for extreme imbalance (630:1 ratio)              ║"
echo "║   • NO balanced sampling - CB loss handles imbalance             ║"
echo "║   • Lower LR 0.0004                                              ║"
echo "║   • Mixup 0.3 for augmentation                                   ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ THEORY:                                                          ║"
echo "║   CB Loss uses 'effective number of samples' to compute weights  ║"
echo "║   E_n = (1 - beta^n) / (1 - beta)                                ║"
echo "║   With beta=0.9999, this naturally handles 630:1 imbalance       ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ SUCCESS CRITERIA:                                                ║"
echo "║   ✅ 10+ classes showing >0% accuracy by epoch 3                 ║"
echo "║   ✅ Balanced accuracy >15% by epoch 5                           ║"
echo "║   ✅ Compare with quick_test_fixed.sh (sqrt sampling) results    ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "This will take ~2-3 hours. Watch the class health checks!"
echo ""

cd "$BEATSIGHT_REPO_ROOT"

# GPU optimizations
export NVIDIA_TF32_OVERRIDE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
export CUDNN_BENCHMARK=1

PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 5 \
    --batch-size 512 \
    --grad-accum-steps 2 \
    --lr 0.0004 \
    --num-workers 4 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --cache-warmup --cache-warmup-samples 200000 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.1 --cutmix-alpha 0.3 --mixup-prob 0.3 \
    --specaugment drum \
    --label-smoothing 0.1 \
    --use-ema --ema-decay 0.9998 --ema-warmup-steps 3000 \
    --loss-type class-balanced --cb-beta 0.9999 \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 3 --warmup-lr-factor 0.05 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    CB LOSS TEST COMPLETE                         ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Results: $RUN_DIR"
echo "║ Compare with: quick_test_fixed.sh (sqrt sampling approach)       ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
