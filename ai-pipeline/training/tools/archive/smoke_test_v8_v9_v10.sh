#!/bin/bash
# =============================================================================
# SMOKE TEST - Verify V8/V9/V10 features work before full training
# =============================================================================
# This runs just 1 epoch with 1% data to verify:
#   1. Class-Balanced Loss loads and computes correctly
#   2. TorchSampler initializes and samples correctly
#   3. Combined mode works without conflicts
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

RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/smoke_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"

cd "$BEATSIGHT_REPO_ROOT"

export NVIDIA_TF32_OVERRIDE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"

echo ""
echo "========================================================================"
echo "  SMOKE TEST 1: Class-Balanced Loss (--loss-type class-balanced)"
echo "========================================================================"
echo ""

PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 1 \
    --batch-size 64 \
    --lr 0.0001 \
    --num-workers 2 --val-num-workers 1 \
    --amp-dtype bfloat16 \
    --train-fraction 0.01 --val-fraction 0.01 \
    --subset-mode stratified --min-samples-per-class 10 \
    --model-version v5 --v5-size small \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --loss-type class-balanced --cb-beta 0.9999 \
    --scheduler cosine \
    --output "$RUN_DIR/smoke1_cb_loss" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/smoke1_cb_loss.log"

SMOKE1_EXIT=${PIPESTATUS[0]}
if [ $SMOKE1_EXIT -eq 0 ]; then
    echo ""
    echo "✅ SMOKE TEST 1 PASSED: Class-Balanced Loss works!"
    echo ""
else
    echo ""
    echo "❌ SMOKE TEST 1 FAILED: Class-Balanced Loss has issues"
    echo ""
    exit 1
fi

echo ""
echo "========================================================================"
echo "  SMOKE TEST 2: TorchSampler (--use-torchsampler)"
echo "========================================================================"
echo ""

PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 1 \
    --batch-size 64 \
    --lr 0.0001 \
    --num-workers 2 --val-num-workers 1 \
    --amp-dtype bfloat16 \
    --train-fraction 0.01 --val-fraction 0.01 \
    --subset-mode stratified --min-samples-per-class 10 \
    --model-version v5 --v5-size small \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --balanced-sampling --use-torchsampler --class-weights none \
    --scheduler cosine \
    --output "$RUN_DIR/smoke2_torchsampler" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/smoke2_torchsampler.log"

SMOKE2_EXIT=${PIPESTATUS[0]}
if [ $SMOKE2_EXIT -eq 0 ]; then
    echo ""
    echo "✅ SMOKE TEST 2 PASSED: TorchSampler works!"
    echo ""
else
    echo ""
    echo "❌ SMOKE TEST 2 FAILED: TorchSampler has issues"
    echo ""
    exit 1
fi

echo ""
echo "========================================================================"
echo "  SMOKE TEST 3: COMBINED (TorchSampler + Class-Balanced Loss)"
echo "========================================================================"
echo ""

PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    --epochs 1 \
    --batch-size 64 \
    --lr 0.0001 \
    --num-workers 2 --val-num-workers 1 \
    --amp-dtype bfloat16 \
    --train-fraction 0.01 --val-fraction 0.01 \
    --subset-mode stratified --min-samples-per-class 10 \
    --model-version v5 --v5-size small \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
    --specaugment none \
    --balanced-sampling --use-torchsampler --class-weights none \
    --loss-type class-balanced --cb-beta 0.9999 \
    --scheduler cosine \
    --output "$RUN_DIR/smoke3_combined" \
    --seed 42 \
    2>&1 | tee "$RUN_DIR/smoke3_combined.log"

SMOKE3_EXIT=${PIPESTATUS[0]}
if [ $SMOKE3_EXIT -eq 0 ]; then
    echo ""
    echo "✅ SMOKE TEST 3 PASSED: Combined mode works!"
    echo ""
else
    echo ""
    echo "❌ SMOKE TEST 3 FAILED: Combined mode has issues"
    echo ""
    exit 1
fi

echo ""
echo "========================================================================"
echo "  ALL SMOKE TESTS PASSED!"
echo "========================================================================"
echo ""
echo "You can now run the full training scripts:"
echo "  V8:  ./ai-pipeline/training/tools/quick_test_v8_cb_loss.sh"
echo "  V9:  ./ai-pipeline/training/tools/quick_test_v9_torchsampler.sh"
echo "  V10: ./ai-pipeline/training/tools/quick_test_v10_combined.sh"
echo ""
echo "Logs saved to: $RUN_DIR"
echo ""
