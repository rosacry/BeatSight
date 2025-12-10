#!/bin/bash
# =============================================================================
# Quick Test V2a - Aggressive Uniform Sampling ONLY (no CB loss)
# =============================================================================
# This version tests whether uniform sampling alone can fix class collapse.
# Using CB loss + uniform sampling might be over-correcting (double-weighting).
#
# APPROACH: Let uniform sampling do ALL the rebalancing
#   - Each class has equal probability of being sampled
#   - Standard CrossEntropy loss (no reweighting)
#   - This is the cleanest approach
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_v2a_uniform_only_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║   QUICK TEST V2a - Uniform Sampling Only (no CB loss)            ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ HYPOTHESIS: Uniform sampling alone should fix class collapse     ║"
echo "║                                                                  ║"
echo "║ CONFIGURATION:                                                   ║"
echo "║   • UNIFORM sampling (each class equally likely to be sampled)   ║"
echo "║   • Standard CrossEntropy (no class reweighting)                 ║"
echo "║   • NO mixup/cutmix (clean learning signal)                      ║"
echo "║   • Small batch (128) for better rare class representation       ║"
echo "║   • Lower LR for stable learning                                 ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ EXPECTED: ~24 samples/class/batch with uniform sampling          ║"
echo "║   (512 / 21 classes ≈ 24 samples each)                           ║"
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
    --epochs 5 \
    --batch-size 256 \
    --grad-accum-steps 4 \
    --lr 0.0003 \
    --num-workers 8 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.10 --val-fraction 0.05 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.0 \
    --use-ema --ema-decay 0.999 --ema-warmup-steps 500 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
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
echo "  V2a Test Complete - Uniform Sampling Only"
echo "============================================================"
echo ""
echo "✅ SUCCESS CRITERIA:"
echo "   - 18+ classes showing >0% accuracy by epoch 3"
echo "   - Balanced accuracy >30% by epoch 5"  
echo "   - All 21 classes being predicted"
echo ""
echo "Compare with V2b (CB loss only) to see which approach works better!"
echo ""
