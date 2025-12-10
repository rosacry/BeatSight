#!/bin/bash
# =============================================================================
# Quick 5-epoch test to validate training config before full run
# =============================================================================
# Usage: bash ai-pipeline/training/tools/quick_test_config.sh
#
# This runs 5 epochs with frequent class health checks.
# If class collapse still occurs, stop and adjust hyperparameters.
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "============================================================"
echo "  QUICK CONFIG TEST (5 epochs)"
echo "============================================================"
echo "Output: $RUN_DIR"
echo ""
echo "This will run ~1.5 hours. Watch for class health at epoch 2-3."
echo "If 15+ classes still have 0% accuracy, STOP and adjust config."
echo "============================================================"
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
    --lr 0.0008 \
    --num-workers 4 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --cache-warmup --cache-warmup-samples 200000 \
    --model-version v5 --v5-size large --drop-path-rate 0.15 \
    --mixup-alpha 0.2 --cutmix-alpha 0.5 --mixup-prob 0.5 \
    --specaugment drum \
    --label-smoothing 0.1 \
    --use-ema --ema-decay 0.9995 --ema-warmup-steps 2000 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 2 --warmup-lr-factor 0.05 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    --checkpoint-every 1 \
    --val-fraction 0.05 \
    --wandb-project beatsight-config-test

echo ""
echo "============================================================"
echo "  Test complete! Check the class health output above."
echo "============================================================"
echo ""
echo "GOOD SIGNS (proceed with full training):"
echo "  - 10+ classes showing >0% accuracy by epoch 3"
echo "  - Balanced accuracy >15% by epoch 5"
echo "  - No class collapse warnings"
echo ""
echo "BAD SIGNS (adjust config before full training):"
echo "  - 15+ classes still at 0% accuracy"
echo "  - Balanced accuracy <10%"
echo "  - Class collapse detected"
echo ""
