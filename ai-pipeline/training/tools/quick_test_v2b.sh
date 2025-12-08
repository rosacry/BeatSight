#!/bin/bash
# =============================================================================
# Quick Test V2b - Class-Balanced Loss ONLY (sqrt sampling)
# =============================================================================
# This version tests whether CB loss alone can fix class collapse,
# without needing aggressive uniform sampling.
#
# APPROACH: Let the loss function do ALL the rebalancing
#   - sqrt sampling (gentler than uniform, provides some diversity)
#   - Class-Balanced CE loss with beta=0.9999
#   - This puts the reweighting in the loss, not the sampler
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/config_test_v2b_cbloss_only_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║   QUICK TEST V2b - Class-Balanced Loss Only (sqrt sampling)      ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ Output: $RUN_DIR"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ HYPOTHESIS: CB loss can compensate for imbalanced sampling       ║"
echo "║                                                                  ║"
echo "║ CONFIGURATION:                                                   ║"
echo "║   • SQRT sampling (moderate rebalancing, more data diversity)    ║"
echo "║   • Class-Balanced CE Loss (beta=0.9999 - aggressive weighting)  ║"
echo "║   • NO mixup/cutmix (clean learning signal)                      ║"
echo "║   • Standard batch size (512)                                    ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║ TRADEOFF: Rare classes seen less often but weighted MORE heavily ║"
echo "║   Might train faster (more unique samples) but gradient variance ║"
echo "║   could be higher due to large per-sample weights for rare.      ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
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
    --epochs 5 \
    --batch-size 512 \
    --grad-accum-steps 2 \
    --lr 0.0003 \
    --num-workers 8 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
    --persistent-workers --pin-memory \
    --amp-dtype bfloat16 \
    --train-fraction 0.10 --val-fraction 0.05 \
    --model-version v5 --v5-size large --drop-path-rate 0.1 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.0 \
    --use-ema --ema-decay 0.999 --ema-warmup-steps 500 \
    --balanced-sampling --sampling-strategy sqrt --class-weights none \
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
echo "  V2b Test Complete - Class-Balanced Loss Only"
echo "============================================================"
echo ""
echo "✅ SUCCESS CRITERIA:"
echo "   - 15+ classes showing >0% accuracy by epoch 3"
echo "   - Balanced accuracy >25% by epoch 5"  
echo "   - All 21 classes being predicted"
echo ""
echo "Compare with V2a (uniform sampling only) to see which works better!"
echo ""
