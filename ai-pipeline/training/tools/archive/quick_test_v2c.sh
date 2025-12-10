#!/bin/bash
# =============================================================================
# Quick Test V2c - Improved Balanced Sampling (Higher Data Fraction)
# =============================================================================
# This version addresses the class collapse issue from V2a by:
# 1. Using HIGHER train-fraction (0.50 instead of 0.10)
# 2. Using stratified subset to ensure minimum samples per class
# 3. Using sqrt sampling (less aggressive than uniform)
#
# ROOT CAUSE OF V2A FAILURE:
#   With --train-fraction 0.10, rare classes may have <20 samples!
#   Balanced sampling then just picks the SAME samples repeatedly.
#   This causes overfitting -> class collapse on validation.
#
# FIX: Use more data to ensure sufficient samples per class.
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_v2c_high_data_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║   QUICK TEST V2c - Balanced Sampling with Higher Data Fraction   ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ HYPOTHESIS: More data ensures sufficient samples per class       ║"
echo "║                                                                  ║"
echo "║ CHANGES FROM V2a:                                                ║"
echo "║   • --train-fraction 0.50 (was 0.10) - 5x more data!             ║"
echo "║   • --subset-mode stratified - ensures min samples per class     ║"
echo "║   • --sampling-strategy sqrt (was uniform) - less aggressive     ║"
echo "║                                                                  ║"
echo "║ WHY V2A FAILED:                                                  ║"
echo "║   With 10% data, rare classes had <20 samples. Uniform sampling  ║"
echo "║   picked the same samples repeatedly -> overfitting -> collapse  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

cd "$BEATSIGHT_REPO_ROOT"

export NVIDIA_TF32_OVERRIDE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
export CUDNN_BENCHMARK=1

PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 10 \
    --batch-size 256 \
    --grad-accum-steps 2 \
    --lr 0.0002 \
    --num-workers 8 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.50 --val-fraction 0.10 --subset-mode stratified \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.1 \
    --use-ema --ema-decay 0.999 --ema-warmup-steps 500 \
    --balanced-sampling --sampling-strategy sqrt --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 2 --warmup-lr-factor 0.01 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

echo ""
echo "============================================================"
echo "  V2c Test Complete - High Data Fraction + Sqrt Sampling"
echo "============================================================"
echo ""
echo "✅ SUCCESS CRITERIA:"
echo "   - All 21 classes showing >0% accuracy by epoch 3"
echo "   - Balanced accuracy >40% by epoch 10"
echo "   - NO classes at 0% after epoch 5"
echo ""
echo "Key changes from V2a:"
echo "   • 50% train data (was 10%) - ensures min samples per class"
echo "   • Stratified subset - guarantees class representation"
echo "   • Sqrt sampling - less aggressive oversampling"
echo "   • Label smoothing 0.1 - prevents overconfident predictions"
echo ""
