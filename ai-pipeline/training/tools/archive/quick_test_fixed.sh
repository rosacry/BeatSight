#!/bin/bash
# =============================================================================
# Quick 5-epoch test to validate FIXED training config
# =============================================================================
# Run this FIRST to verify no class collapse before the full multi-day training
# Expected: 10+ classes learning by epoch 3, balanced acc >15% by epoch 5
# =============================================================================
#
# NEW DIAGNOSTICS (Dec 2025):
# ---------------------------
# This test now includes COMPREHENSIVE diagnostic logging:
#   1. PRE-TRAINING: Verifies balanced sampling is working before training
#   2. EPOCH 1: Full deep diagnostic (gradient flow, prediction distribution, etc.)
#   3. EVERY 3 EPOCHS: Class health check
#   4. ON COLLAPSE: Automatic deep diagnostic with root cause analysis
#
# WATCH FOR:
#   ✅ "All 21 classes appearing in batches" at start
#   ✅ Multiple classes predicted in epoch 1 diagnostic
#   ✅ Gradients flowing to all class logits
#   ❌ "PREDICTION COLLAPSE" = model only predicting few classes
#   ❌ "GRADIENT STARVATION" = some classes not getting gradients
#   ❌ "SAMPLING ISSUE" = classes not appearing in batches
#
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
echo "║ NEW DIAGNOSTICS:                                                 ║"
echo "║   📊 Pre-training: Verifies sampling is working                  ║"
echo "║   🔬 Epoch 1: Deep diagnostic with gradient analysis             ║"
echo "║   🏥 Every epoch: Class health checks                            ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ SUCCESS CRITERIA:                                                ║"
echo "║   ✅ 10+ classes showing >0% accuracy by epoch 3                 ║"
echo "║   ✅ Balanced accuracy >15% by epoch 5                           ║"
echo "║   ✅ NO class collapse warnings after epoch 3                    ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "⚡ OPTIMIZED: Using 10% subset (~1.5M samples) - runs in ~30-60 min"
echo "   This is enough to detect class collapse patterns."
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
    --num-workers 8 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.10 --val-fraction 0.05 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.1 --cutmix-alpha 0.3 --mixup-prob 0.3 \
    --specaugment drum \
    --label-smoothing 0.1 \
    --use-ema --ema-decay 0.9998 --ema-warmup-steps 1000 \
    --balanced-sampling --sampling-strategy sqrt --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 2 --warmup-lr-factor 0.05 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

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
