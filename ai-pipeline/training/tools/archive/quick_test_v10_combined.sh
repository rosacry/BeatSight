#!/bin/bash
# =============================================================================
# Quick Test V10 - COMBINED: TorchSampler + Class-Balanced Loss
# =============================================================================
# V7: 54.27% balanced accuracy (baseline - all 21 classes learning)
# V8: Class-Balanced Loss alone
# V9: TorchSampler alone
# V10: BOTH techniques combined - maximum imbalance handling
#
# Strategy:
#   1. TorchSampler ensures each batch sees balanced class distribution
#   2. Class-Balanced Loss re-weights gradients for minority classes
#
# These two techniques are COMPLEMENTARY:
#   - Sampling addresses batch composition (what samples we see)
#   - Loss re-weighting addresses gradient magnitude (how much we learn)
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_v10_combined_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "========================================================================"
echo "  V10 - COMBINED: TorchSampler + Class-Balanced Loss"
echo "========================================================================"
echo "Output: $RUN_DIR"
echo ""
echo "Building on V7 (54.27% balanced acc):"
echo "  - train-fraction 0.05 (5%)"
echo "  - batch-size 256, grad-accum 4 (effective 1024)"
echo "  - lr 0.0001"
echo ""
echo "NEW in V10: BOTH techniques combined!"
echo "  --use-torchsampler       (better sampling)"
echo "  --loss-type class-balanced --cb-beta 0.9999 (loss re-weighting)"
echo ""
echo "TorchSampler: Ensures batches have balanced class distribution"
echo "Class-Balanced Loss: Re-weights gradients based on effective samples"
echo ""
echo "Together, these attack imbalance from BOTH directions!"
echo ""
echo "NOTE: Install torchsampler first: pip install torchsampler"
echo "========================================================================"
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
    --lr 0.0001 \
    --num-workers 4 --val-num-workers 2 --prefetch-factor 2 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.05 --val-fraction 0.05 \
    --subset-mode stratified --min-samples-per-class 50 \
    --model-version v5 --v5-size large --drop-path-rate 0.0 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.0 \
    --balanced-sampling --use-torchsampler --class-weights none \
    --loss-type class-balanced --cb-beta 0.9999 \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 0 --warmup-lr-factor 1.0 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.0 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

echo ""
echo "========================================================================"
echo "  V10 Complete - Full Imbalance Attack!"
echo "========================================================================"
echo ""
echo "Comparison targets:"
echo "  V7  (baseline):      54.27% balanced acc"
echo "  V8  (CB Loss):       ??? %"
echo "  V9  (TorchSampler):  ??? %"
echo "  V10 (COMBINED):      ??? %"
echo ""
echo "If V10 is best, use this config for full training!"
echo ""
