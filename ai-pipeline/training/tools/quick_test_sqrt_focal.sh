#!/bin/bash
# =============================================================================
# Quick 5-epoch test - SQRT SAMPLING + FOCAL LOSS (balanced approach)
# =============================================================================
# LESSON LEARNED: Uniform sampling FAILED - too aggressive for 630x imbalance!
#
# The model collapsed to 2-3 classes because:
#   1. Uniform sampling forces equal class probability
#   2. With 630x imbalance, rare classes get oversampled 630x
#   3. Model can't learn feature space when rare examples dominate
#   4. Mixup/cutmix blur the rare class signal further
#
# NEW APPROACH - The "Goldilocks" config:
#   - sqrt sampling: moderate rebalancing (25x instead of 630x)
#   - focal loss γ=1.5: helps hard examples without being extreme
#   - NO mixup early: let model learn clean class boundaries first
#   - Lower EMA decay: faster adaptation in early epochs
#   - Slightly higher LR: sqrt sampling is more stable than uniform
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_sqrt_focal_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     QUICK TEST - SQRT SAMPLING + FOCAL LOSS (5 epochs)           ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ WHY UNIFORM FAILED:                                              ║"
echo "║   • 630x oversampling of rare classes was too aggressive         ║"
echo "║   • Model collapsed to 2-3 classes (18-19 at 0% accuracy)        ║"
echo "║   • Mixup destroyed rare class signal                            ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ NEW APPROACH - SQRT + FOCAL:                                     ║"
echo "║   • sqrt sampling: ~25x rebalancing (not 630x)                   ║"
echo "║   • focal loss γ=1.5: helps hard/rare examples                   ║"
echo "║   • NO mixup: clean class boundaries                             ║"
echo "║   • EMA decay 0.999: faster adaptation                           ║"
echo "║   • LR 0.0005: higher (sqrt is more stable)                      ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ SUCCESS CRITERIA:                                                ║"
echo "║   ✅ 10+ classes showing >0% accuracy by epoch 2                 ║"
echo "║   ✅ 15+ classes showing >0% accuracy by epoch 3                 ║"
echo "║   ✅ Balanced accuracy >15% by epoch 5                           ║"
echo "║   ✅ NO class collapse warnings after epoch 3                    ║"
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
    --lr 0.0005 \
    --num-workers 4 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --cache-warmup --cache-warmup-samples 200000 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --specaugment drum \
    --label-smoothing 0.05 \
    --use-ema --ema-decay 0.999 --ema-warmup-steps 2000 \
    --balanced-sampling --sampling-strategy sqrt --class-weights none \
    --focal-loss --focal-gamma 1.5 \
    --scheduler cosine_warm_restarts --warm-restart-t0 30 --warm-restart-mult 2 \
    --warmup-epochs 1 --warmup-lr-factor 0.1 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    --checkpoint-every 1 \
    --val-fraction 0.05 \
    --wandb-project beatsight-config-test-sqrt

echo ""
echo "============================================================"
echo "  Test complete! Check the class health output above."
echo "============================================================"
echo ""
echo "✅ GOOD SIGNS (proceed with full training):"
echo "   - 10+ classes showing >0% accuracy by epoch 2"
echo "   - 15+ classes showing >0% accuracy by epoch 3"
echo "   - Balanced accuracy >15% by epoch 5"
echo "   - No class collapse warnings after epoch 3"
echo ""
echo "❌ BAD SIGNS (need investigation):"
echo "   - Still >10 classes at 0% accuracy after epoch 3"
echo "   - Balanced accuracy <10%"
echo "   - Training loss not decreasing"
echo ""
echo "If STILL failing, the issue may be in the data/labels, not hyperparameters."
echo ""
