#!/bin/bash
# =============================================================================
# Quick 5-epoch test - MAXIMUM REBALANCING (aggressive settings)
# =============================================================================
# Use this if quick_test_uniform.sh still shows class collapse.
# 
# This adds CLASS WEIGHTS to the loss function ON TOP of uniform sampling.
# This is "double rebalancing" and may overfit to rare classes, but it will
# definitely prevent class collapse.
#
# Expected: ALL 21 classes learning by epoch 3, balanced_acc > 30%
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_aggressive_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║    QUICK TEST - AGGRESSIVE REBALANCING (5 epochs)                ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ MAXIMUM REBALANCING SETTINGS:                                    ║"
echo "║   • UNIFORM sampling (equal probability per class)               ║"
echo "║   • sqrt class weights (extra penalty for common classes)        ║"
echo "║   • Very low LR 0.0002 (prevent overfitting to rare classes)     ║"
echo "║   • NO mixup/cutmix (preserve rare class examples exactly)       ║"
echo "║   • Long warmup 8 epochs (let all classes stabilize)             ║"
echo "║   • Smaller batch 256 (more gradient updates)                    ║"
echo "║   • Higher weight decay 0.03 (regularize against overfitting)    ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ SUCCESS CRITERIA:                                                ║"
echo "║   ✅ ALL 21 classes showing >0% accuracy by epoch 3              ║"
echo "║   ✅ Balanced accuracy >30% by epoch 5                           ║"
echo "║   ✅ Even if per-class variance is high, no zeros allowed        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "This will take ~3-4 hours. Watch the class health checks!"
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
    --batch-size 256 \
    --grad-accum-steps 4 \
    --lr 0.0002 \
    --num-workers 4 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --cache-warmup --cache-warmup-samples 200000 \
    --model-version v5 --v5-size large --drop-path-rate 0.05 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment drum \
    --label-smoothing 0.0 \
    --use-ema --ema-decay 0.9999 --ema-warmup-steps 8000 \
    --balanced-sampling --sampling-strategy uniform --class-weights sqrt \
    --scheduler cosine_warm_restarts --warm-restart-t0 40 --warm-restart-mult 2 \
    --warmup-epochs 8 --warmup-lr-factor 0.01 \
    --gradient-checkpointing \
    --grad-clip-norm 0.5 --weight-decay 0.03 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    --checkpoint-every 1 \
    --val-fraction 0.05 \
    --wandb-project beatsight-config-test-aggressive

echo ""
echo "============================================================"
echo "  Test complete! Check the class health output above."
echo "============================================================"
echo ""
echo "✅ GOOD SIGNS:"
echo "   - ALL 21 classes showing >0% accuracy by epoch 3"
echo "   - Balanced accuracy >30% by epoch 5"  
echo ""
echo "⚠️  WARNING SIGNS (but acceptable):"
echo "   - High variance between class accuracies"
echo "   - Some classes overfitting (val acc < train acc)"
echo ""
echo "❌ BAD SIGNS (data quality issue):"
echo "   - Still any class at exactly 0%"
echo "   - Loss not decreasing"
echo ""
echo "If this works, you may want to back off to the uniform-only config"
echo "for better overall accuracy (less overfitting to rare classes)."
echo ""
