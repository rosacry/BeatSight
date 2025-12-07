#!/bin/bash
# =============================================================================
# Quick 5-epoch test to validate FIXED training config
# =============================================================================
# Run this FIRST to verify no class collapse before the full multi-day training
# Expected: 10+ classes learning by epoch 3, balanced acc >15% by epoch 5
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_fixed_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         QUICK TEST - Fixed Config (5 epochs)                     ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ KEY CHANGES FROM BROKEN CONFIG:                                  ║"
echo "║   • sqrt sampling (not uniform) - gentler rebalancing            ║"
echo "║   • NO focal loss - balanced sampling alone is enough            ║"
echo "║   • Lower LR 0.0004 (was 0.0008)                                 ║"
echo "║   • Lower mixup 0.3 (was 0.5) - easier early learning            ║"
echo "║   • Longer warmup 5 epochs (was 2)                               ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ SUCCESS CRITERIA:                                                ║"
echo "║   ✅ 10+ classes showing >0% accuracy by epoch 3                 ║"
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
    --balanced-sampling --sampling-strategy sqrt --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 3 --warmup-lr-factor 0.05 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    --checkpoint-every 1 \
    --val-fraction 0.05 \
    --wandb-project beatsight-config-test-fixed

echo ""
echo "============================================================"
echo "  Test complete! Check the class health output above."
echo "============================================================"
echo ""
echo "✅ GOOD SIGNS (proceed with full training):"
echo "   - 10+ classes showing >0% accuracy by epoch 3"
echo "   - Balanced accuracy >15% by epoch 5"  
echo "   - No class collapse warnings after epoch 3"
echo "   - Train/val loss decreasing consistently"
echo ""
echo "❌ BAD SIGNS (need more adjustments):"
echo "   - Still >10 classes at 0% accuracy"
echo "   - Balanced accuracy <15%"
echo "   - Class collapse warnings persist"
echo ""
echo "If test passes, run: bash ai-pipeline/training/tools/train_v5_balanced_fixed.sh"
echo ""
