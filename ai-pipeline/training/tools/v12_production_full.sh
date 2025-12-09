#!/bin/bash
# =============================================================================
# V12 PRODUCTION - Full Dataset Training for Best Possible Model
# =============================================================================
# RUN THIS ONLY AFTER V11 PROVES THE CONFIG WORKS
#
# This is the FULL training run:
#   - 100% of training data (14.6M samples)
#   - 20 epochs with warm restarts
#   - All regularization enabled
#   - EMA for smoother final weights
#
# Expected time: ~12-20 hours on RTX 3080 Ti
# Expected result: 70%+ balanced accuracy (revolutionary for 21-class drum)
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/v12_production_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "========================================================================"
echo "  V12 PRODUCTION - Full Dataset Training"
echo "========================================================================"
echo "Output: $RUN_DIR"
echo ""
echo "FULL SCALE TRAINING:"
echo "  - train-fraction 1.0 (100% = 14.6M samples)"
echo "  - epochs 20"
echo "  - batch-size 256, grad-accum 4 (effective 1024)"
echo "  - lr 0.0001 with warmup"
echo "  - UNIFORM sampling"
echo "  - drop-path 0.2, weight-decay 0.02 (stronger regularization)"
echo "  - label-smoothing 0.1"
echo "  - EMA decay 0.9999"
echo ""
echo "Target: 70%+ balanced accuracy"
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
    --epochs 20 \
    --batch-size 256 \
    --grad-accum-steps 4 \
    --lr 0.0001 \
    --num-workers 6 --val-num-workers 3 --prefetch-factor 4 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 1.0 --val-fraction 1.0 \
    --subset-mode stratified --min-samples-per-class 200 \
    --model-version v5 --v5-size large --drop-path-rate 0.2 \
    --mixup-alpha 0.2 --cutmix-alpha 0.0 --mixup-prob 0.5 \
    --specaugment light \
    --label-smoothing 0.1 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 10 --warm-restart-mult 2 \
    --warmup-epochs 2 --warmup-lr-factor 0.01 \
    --ema --ema-decay 0.9999 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.02 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

echo ""
echo "========================================================================"
echo "  V12 PRODUCTION Complete"
echo "========================================================================"
echo ""
echo "This is your PRODUCTION MODEL."
echo "Check: $RUN_DIR"
echo ""
echo "If balanced_acc > 70%, you have a revolutionary drum classifier!"
echo ""
