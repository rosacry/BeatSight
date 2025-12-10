#!/bin/bash
# A2: Higher learning rate (0.0002) - does more aggressive learning help?
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
[ -f "$SCRIPT_DIR/beatsight_env.sh" ] && source "$SCRIPT_DIR/beatsight_env.sh"
BEATSIGHT_REPO_ROOT=${BEATSIGHT_REPO_ROOT:-$REPO_ROOT}
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-${BEATSIGHT_REPO_ROOT}/data}
BEATSIGHT_CACHE_DIR=${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup_consolidated}
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_CACHE_DIR}}
RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/ablation_A2_lr_higher_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"
cd "$BEATSIGHT_REPO_ROOT"
export NVIDIA_TF32_OVERRIDE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
echo "======== A2: lr=0.0002 (baseline: 0.0001) ========"
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" --device cuda --epochs 5 \
    --batch-size 256 --grad-accum-steps 4 --lr 0.0002 \
    --num-workers 4 --val-num-workers 2 --prefetch-factor 2 --val-prefetch-factor 2 \
    --persistent-workers --pin-memory --amp-dtype bfloat16 \
    --train-fraction 0.05 --val-fraction 0.05 --subset-mode stratified --min-samples-per-class 50 \
    --model-version v5 --v5-size large --drop-path-rate 0.0 \
    --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 --specaugment none --label-smoothing 0.0 \
    --balanced-sampling --sampling-strategy uniform --class-weights none \
    --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
    --warmup-epochs 0 --warmup-lr-factor 1.0 --gradient-checkpointing \
    --grad-clip-norm 1.0 --weight-decay 0.0 --channels-last --output "$RUN_DIR" --seed 42 \
    2>&1 | tee "$RUN_DIR/training.log"
echo ""; echo "Baseline V7: 54.27% | A1 (lr=0.00005): 48.93%"
