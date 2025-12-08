#!/bin/bash
# =============================================================================
# Quick 5-epoch test - UNIFORM SAMPLING (for extreme class imbalance)
# =============================================================================
# CRITICAL FIX: sqrt sampling was TOO CONSERVATIVE for 630x imbalance!
# 
# Class distribution analysis:
#   - Class 17 (snare_rimshot): 4,024,285 samples (27.4%)
#   - Class 0 (aux_percussion):  3,100,430 samples (21.1%)
#   - ...
#   - Class 5 (hihat_closed):        6,387 samples (0.04%)
#   - Class 4 (cymbal_choke):        7,537 samples (0.05%)
#
# With sqrt sampling: only 25x rebalancing (still 100K vs 2.5M per epoch)
# With uniform sampling: TRUE equal probability per class
#
# Expected: ALL 21 classes learning by epoch 5, balanced_acc > 25%
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_uniform_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     QUICK TEST - UNIFORM SAMPLING (5 epochs)                     ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ KEY CHANGES FROM sqrt CONFIG (which FAILED):                     ║"
echo "║   • UNIFORM sampling - TRUE class balance for 630x imbalance     ║"
echo "║   • NO focal loss - balanced sampling alone handles it           ║"
echo "║   • LR 0.0003 (lower for stability with uniform sampling)        ║"
echo "║   • Mixup 0.2 (lower - too much hides rare class examples)       ║"
echo "║   • Longer warmup 5 epochs (let rare classes stabilize)          ║"
echo "║   • Smaller batch 384 (more gradient updates for rare classes)   ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ SUCCESS CRITERIA:                                                ║"
echo "║   ✅ 15+ classes showing >0% accuracy by epoch 3                 ║"
echo "║   ✅ ALL 21 classes showing >0% accuracy by epoch 5              ║"
echo "║   ✅ Balanced accuracy >25% by epoch 5                           ║"
echo "║   ✅ NO class collapse warnings                                  ║"
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
    --batch-size 384 \
    --grad-accum-steps 3 \
    --lr 0.0003 \
    --num-workers 4 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --cache-warmup --cache-warmup-samples 200000 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.1 --cutmix-alpha 0.2 --mixup-prob 0.2 \
    --specaugment drum \
    --label-smoothing 0.05 \
    --use-ema --ema-decay 0.9998 --ema-warmup-steps 5000 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 30 --warm-restart-mult 2 \
    --warmup-epochs 5 --warmup-lr-factor 0.02 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.02 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    --checkpoint-every 1 \
    --val-fraction 0.05 \
    --wandb-project beatsight-config-test-uniform

echo ""
echo "============================================================"
echo "  Test complete! Check the class health output above."
echo "============================================================"
echo ""
echo "✅ GOOD SIGNS (proceed with full training):"
echo "   - 15+ classes showing >0% accuracy by epoch 3"
echo "   - ALL 21 classes showing >0% accuracy by epoch 5"
echo "   - Balanced accuracy >25% by epoch 5"  
echo "   - No class collapse warnings"
echo ""
echo "❌ BAD SIGNS (need investigation):"
echo "   - Still >5 classes at 0% accuracy after epoch 5"
echo "   - Balanced accuracy <20%"
echo "   - Training loss not decreasing"
echo ""
echo "If test passes, update train_v5_balanced_fixed.sh with uniform sampling!"
echo ""
