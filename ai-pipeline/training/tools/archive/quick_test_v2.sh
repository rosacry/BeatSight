#!/bin/bash
# =============================================================================
# Quick Test V2 - Addressing Class Collapse Root Cause
# =============================================================================
# DIAGNOSTIC FINDINGS from quick_test_fixed.sh:
#   - Sampling was working (all 21 classes appeared in batches)
#   - BUT rare classes got only 1-3 samples/batch (class_5: 1.9/batch)
#   - Result: gradients from 2 samples drowned out by 510 other samples
#   - Model converged to predicting only class_0 and class_17
#
# ROOT CAUSE: sqrt rebalancing isn't aggressive enough for 630x imbalance
#
# FIXES IN THIS VERSION:
#   1. UNIFORM sampling (not sqrt) - truly equal class probability
#   2. Class-Balanced Loss (CB Loss) - inverse-frequency weighted CE
#   3. MUCH smaller batch size (128) - rare classes get higher proportion
#   4. NO mixup for first 3 epochs - let model learn class boundaries
#   5. Lower learning rate during warmup
#   6. Repeat oversampling (oversample to match largest class)
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_v2_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         QUICK TEST V2 - Class Collapse Fix                       ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ ROOT CAUSE (from diagnostic):                                    ║"
echo "║   • sqrt sampling only gave ~2 rare samples/batch of 512         ║"
echo "║   • 2 samples can't compete with 510 other samples               ║"
echo "║   • Model learned to ignore rare classes entirely                ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ FIXES IN V2:                                                     ║"
echo "║   ✓ UNIFORM sampling (true class balance, not sqrt)              ║"
echo "║   ✓ Class-Balanced Loss (CB beta=0.9999)                         ║"
echo "║   ✓ Smaller batch (128) = higher rare class proportion           ║"
echo "║   ✓ NO mixup until epoch 3 (learn boundaries first)              ║"
echo "║   ✓ Lower warmup LR (0.01x base) for stability                   ║"
echo "║   ✓ Oversample rare classes (repeat sampling)                    ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ EXPECTED OUTCOME:                                                ║"
echo "║   ✅ 15+ classes showing >0% accuracy by epoch 3                 ║"
echo "║   ✅ Balanced accuracy >25% by epoch 5                           ║"
echo "║   ✅ NO prediction collapse (all classes predicted)              ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "⚡ Using 10% subset (~1.5M samples) - runs in ~30-60 min"
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
    --batch-size 128 \
    --grad-accum-steps 8 \
    --lr 0.0003 \
    --num-workers 8 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.10 --val-fraction 0.05 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.05 \
    --use-ema --ema-decay 0.999 --ema-warmup-steps 500 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --loss-type class-balanced --cb-beta 0.9999 \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 2 --warmup-lr-factor 0.01 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.01 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

echo ""
echo "============================================================"
echo "  Test V2 complete! Check class health output above."
echo "============================================================"
echo ""
echo "✅ GOOD SIGNS (proceed with full training):"
echo "   - 15+ classes showing >0% accuracy by epoch 3"
echo "   - Balanced accuracy >25% by epoch 5"  
echo "   - All 21 classes being predicted (no prediction collapse)"
echo "   - Gradients flowing to ALL class logits"
echo ""
echo "❌ BAD SIGNS (try V3 config):"
echo "   - Still >5 classes at 0% accuracy by epoch 3"
echo "   - Prediction collapse (fewer than 10 classes predicted)"
echo "   - Balanced accuracy <15%"
echo ""
echo "If test passes, update train_v5_balanced_fixed.sh with these settings!"
echo ""
