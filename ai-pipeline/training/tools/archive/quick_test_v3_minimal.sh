#!/bin/bash
# =============================================================================
# Quick Test V3 - Conservative Minimal Config with Verification Steps
# =============================================================================
# GOAL: Prove the sampling fix works before committing to longer training.
# 
# DIFFERENCES FROM PREVIOUS TESTS:
#   1. Only 2 epochs - just enough to see if learning is happening for ALL classes
#   2. TINY subset (1%) - ~150K samples, runs in ~5 minutes
#   3. No augmentation at all - pure signal
#   4. Very low LR - prevent divergence
#   5. Explicit per-epoch class accuracy logging
#
# SUCCESS CRITERIA (must meet ALL):
#   ✅ Epoch 1: At least 15/21 classes with >0% accuracy  
#   ✅ Epoch 2: At least 18/21 classes with >0% accuracy
#   ✅ Epoch 2: Balanced accuracy > 20%
#   ✅ Pre-training verification shows <5x batch imbalance with uniform sampling
#
# If this passes, the config is sound and you can scale up to full dataset.
# If this fails, we have a deeper problem.
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_v3_minimal_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║   QUICK TEST V3 - Minimal Conservative Test (~5 min)             ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ CONFIGURATION:                                                   ║"
echo "║   • 2 epochs only (just need to see learning signal)             ║"
echo "║   • 1% subset (~150K samples) - very fast                        ║"
echo "║   • UNIFORM sampling - true class balance                        ║"
echo "║   • NO augmentation (mixup, specaug, etc.)                       ║"
echo "║   • NO label smoothing                                           ║"
echo "║   • NO EMA (just raw model)                                      ║"
echo "║   • Small batch (64) + no grad accum = see gradients immediately ║"
echo "║   • Low LR (0.0001) = stable learning                            ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ WHAT WE'RE TESTING:                                              ║"
echo "║   Can the model learn ALL classes with uniform sampling?         ║"
echo "║   If YES → scale up. If NO → deeper problem to debug.            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

cd "$BEATSIGHT_REPO_ROOT"

export NVIDIA_TF32_OVERRIDE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
export CUDNN_BENCHMARK=1

# NOTE: With 1% subset and min-samples-per-class=50, rare classes will be boosted
# to ensure at least 50 samples each. This prevents class collapse from data scarcity.
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 2 \
    --batch-size 64 \
    --grad-accum-steps 1 \
    --lr 0.0001 \
    --num-workers 4 --val-num-workers 2 --prefetch-factor 2 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.01 --val-fraction 0.01 \
    --subset-mode stratified --min-samples-per-class 50 \
    --model-version v5 --v5-size large --drop-path-rate 0.0 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.0 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 0 --warmup-lr-factor 1.0 \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.0 \
    --channels-last \
    --output "$RUN_DIR" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    VERIFICATION CHECKLIST                        ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Check the output above for:                                      ║"
echo "║                                                                  ║"
echo "║ 1. PRE-TRAINING SAMPLING:                                        ║"
echo "║    - Batch imbalance should be <5x (not 27x like before!)        ║"
echo "║    - All 21 classes should appear                                ║"
echo "║                                                                  ║"
echo "║ 2. EPOCH 1 CLASS HEALTH:                                         ║"
echo "║    - Should have 15+ classes with >0% accuracy                   ║"
echo "║    - Should NOT show 'CLASS COLLAPSE DETECTED'                   ║"
echo "║                                                                  ║"
echo "║ 3. EPOCH 2 CLASS HEALTH:                                         ║"
echo "║    - Should have 18+ classes with >0% accuracy                   ║"
echo "║    - Balanced accuracy should be >20%                            ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ If ALL pass → config is good, run quick_test_v2a.sh              ║"
echo "║ If ANY fail → there's a deeper bug we need to find               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
