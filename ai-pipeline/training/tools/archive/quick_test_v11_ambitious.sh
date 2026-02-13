#!/bin/bash
# =============================================================================
# V11 AMBITIOUS - Full Scale Training for Revolutionary Results
# =============================================================================
# Goal: Push beyond 54.27% to new heights
#
# What we learned:
#   - V7 (54.27%): Uniform sampling + low LR + no focal = best so far
#   - V8 (53.88%): Class-Balanced Loss didn't help on top of uniform sampling
#   - More epochs = still improving (V8 was climbing at epoch 5)
#
# V11 Strategy - SCALE UP:
#   1. 10% data instead of 5% (2x more training data)
#   2. 10 epochs instead of 5 (2x more training time)
#   3. Keep V7's winning formula (uniform sampling, no focal, lr 0.0001)
#   4. Add mild regularization to prevent overfitting with more epochs
#
# Expected time: ~2 hours on RTX 3080 Ti
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/v11_ambitious_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "========================================================================"
echo "  V11 AMBITIOUS - Pushing for Revolutionary Results"
echo "========================================================================"
echo "Output: $RUN_DIR"
echo ""
echo "Building on V7 (54.27% balanced acc) with SCALE:"
echo "  - train-fraction 0.10 (10% = 1.47M samples, 2x more data)"
echo "  - epochs 10 (2x longer training)"
echo "  - batch-size 256, grad-accum 4 (effective 1024)"
echo "  - lr 0.0001 (proven optimal)"
echo "  - UNIFORM sampling (best for class balance)"
echo "  - drop-path 0.1 (mild regularization for longer training)"
echo "  - weight-decay 0.01 (prevent overfitting)"
echo ""
echo "Target: Break 60% balanced accuracy"
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
    --grad-accum-steps 4 \
    --lr 0.0001 \
    --num-workers 4 --val-num-workers 2 --prefetch-factor 2 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.10 --val-fraction 0.10 \
    --subset-mode stratified --min-samples-per-class 100 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.1 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 10 --warm-restart-mult 2 \
    --warmup-epochs 1 --warmup-lr-factor 0.1 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

echo ""
echo "========================================================================"
echo "  V11 AMBITIOUS Complete"
echo "========================================================================"
echo ""
echo "Results comparison:"
echo "  V7  baseline:  54.27% balanced acc (5% data, 5 epochs)"
echo "  V11 ambitious: Check $RUN_DIR/training.log"
echo ""
echo "If V11 > 60%, we're on track for revolutionary results!"
echo "Next step: Full dataset training with best config."
echo ""
