#!/bin/bash
# =============================================================================
# Quick Test V2a Fixed - Scaled Up from Working Minimal Config
# =============================================================================
# The minimal test (v3) worked perfectly: 40.97% balanced acc in 2 epochs
# This scales it up with conservative changes:
#   - Same LR (0.0001) - v2a used 0.0003 which was too high
#   - Sqrt sampling (not uniform) - less aggressive
#   - No EMA - was causing instability in v2a
#   - Larger batch but same effective LR per sample
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_v2a_fixed_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "========================================================================"
echo "  QUICK TEST V2a FIXED - Scaled from Working Minimal Config"
echo "========================================================================"
echo "Output: $RUN_DIR"
echo ""
echo "CHANGES FROM FAILED V2a:"
echo "  - LR: 0.0001 (was 0.0003) - too high caused collapse"
echo "  - Sampling: sqrt (was uniform) - less aggressive"
echo "  - EMA: DISABLED (was 0.999) - was causing mode collapse"
echo "  - Grad accum: 2 (was 4) - smaller effective batch"
echo "  - Warmup: 1 epoch (was 2)"
echo ""
echo "This config mirrors the successful minimal test, just scaled up."
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
    --epochs 10 \
    --batch-size 256 \
    --grad-accum-steps 2 \
    --lr 0.0001 \
    --num-workers 8 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.10 --val-fraction 0.05 \
    --subset-mode stratified --min-samples-per-class 50 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.1 \
    --balanced-sampling --sampling-strategy sqrt --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 1 --warmup-lr-factor 0.1 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

echo ""
echo "========================================================================"
echo "  V2a Fixed Test Complete"
echo "========================================================================"
echo ""
echo "SUCCESS CRITERIA:"
echo "   - No class collapse through all 10 epochs"
echo "   - Balanced accuracy improving steadily"
echo "   - All 21 classes maintaining >0% accuracy"
echo ""
