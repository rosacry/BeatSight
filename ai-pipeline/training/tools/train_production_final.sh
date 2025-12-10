#!/bin/bash
# =============================================================================
# BEATSIGHT PRODUCTION TRAINING - FINAL OPTIMIZED CONFIGURATION
# =============================================================================
# Created: December 9, 2025
# Goal: World's best AI model for drum transcription
#
# ABLATION STUDY FINDINGS (recorded for posterity):
# ═══════════════════════════════════════════════════════════════════════════
#
# ROOT CAUSES OF CLASS COLLAPSE (SOLVED):
# ────────────────────────────────────────
# 1. Focal Loss gamma too high
#    - gamma=3.0 with uniform sampling = double-emphasis on rare classes
#    - This caused 17/21 classes to collapse to 0% accuracy
#    - SOLUTION: Remove focal loss entirely, use plain CrossEntropy
#
# 2. Learning rate too low  
#    - 0.0001 was actually too conservative
#    - 0.0002 works better (+4.47% improvement)
#    - SOLUTION: Use LR = 0.0002
#
# 3. Batch size too large
#    - 1024 effective batch was too big for this problem
#    - 512 effective batch generalizes better (+2.33% improvement)
#    - SOLUTION: batch_size=256, grad_accum=2 (effective 512)
#
# 4. Not enough data
#    - 5% data fraction wasn't enough to learn all classes
#    - 10% gave +7.42% improvement (almost linear scaling)
#    - SOLUTION: Use 100% of data (14.6M samples)
#
# IMPORTANT NOTE ON SAMPLING STRATEGY:
# ────────────────────────────────────────
# Earlier scripts (quick_test_sqrt_focal.sh, quick_test_fixed.sh) suggested
# sqrt sampling, but those were written BEFORE we discovered the real issue.
# 
# The actual fix was: UNIFORM sampling + NO focal loss
# All successful tests (V6: 59.24%, V7: 54.27%, E1: 61.69%, A2: 58.74%, B1: 56.60%)
# used UNIFORM sampling. DO NOT change to sqrt - uniform is correct!
#
# ABLATION RESULTS SUMMARY:
# ────────────────────────────────────────
# | Config | Data | Change              | Balanced Acc | vs Baseline |
# |--------|------|---------------------|--------------|-------------|
# | V7     | 5%   | Baseline            | 54.27%       | -           |
# | A1     | 5%   | LR 0.00005 (lower)  | 48.93%       | -5.34% ❌   |
# | A2     | 5%   | LR 0.0002 (higher)  | 58.74%       | +4.47% ✅   |
# | B1     | 5%   | Batch 512 (smaller) | 56.60%       | +2.33% ✅   |
# | E1     | 10%  | More data           | 61.69%       | +7.42% ✅   |
#
# THIS CONFIG COMBINES ALL WINNERS:
# ────────────────────────────────────────
# ✅ 100% data (14,681,148 training samples)
# ✅ LR = 0.0002 (higher learning rate)
# ✅ Effective batch = 512 (batch 256, grad_accum 2)
# ✅ Uniform balanced sampling (WeightedRandomSampler)
# ✅ Plain CrossEntropy loss (NO focal loss)
# ✅ 100 epochs (ambitious goal for world-class accuracy)
# ✅ Cosine annealing with warm restarts
# ✅ Gradient checkpointing for memory efficiency
# ✅ bfloat16 AMP for speed
#
# EXPECTED RESULTS:
# ────────────────────────────────────────
# With 100% data + optimized hyperparameters + 100 epochs:
# Target: 80-85%+ balanced accuracy (world-class)
#
# Hardware: RTX 3080 Ti (12GB), 9800X3D, NVMe
# Estimated time: ~35-40 hours (100 epochs × ~20 min/epoch)
#
# TRAINING PIPELINE (after this script):
# ────────────────────────────────────────
# 1. train_production_final.sh (THIS) - Base classifier training (100 epochs)
# 2. 17e (v5-distill) - Self-distillation from this model (optional, +1-2%)
# 3. 19c (multilabel) - Simultaneous drum detection fine-tuning (REQUIRED)
#
# For world-class results, run this script first. 17e is optional but 19c
# is required for detecting simultaneous drum hits (kick+hihat, snare+crash).
#
# ADDITIONAL FEATURES ENABLED:
# ────────────────────────────────────────
# ✅ EMA (Exponential Moving Average) - smoother, more stable model
# ✅ Mid-epoch checkpoints every 5000 batches (~15 min intervals)
# ✅ Epoch checkpoints every 5 epochs
# ✅ NO early stopping - runs all 100 epochs (Ctrl+C to stop manually)
# ✅ Auto-resume from checkpoint if training interrupted
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load environment
if [ -f "$SCRIPT_DIR/beatsight_env.sh" ]; then
    source "$SCRIPT_DIR/beatsight_env.sh"
fi

BEATSIGHT_REPO_ROOT=${BEATSIGHT_REPO_ROOT:-$REPO_ROOT}
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-${BEATSIGHT_REPO_ROOT}/data}
BEATSIGHT_CACHE_DIR=${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup_consolidated}
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_CACHE_DIR}}

# Create unique run directory
RUN_NAME="v5_production_$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/${RUN_NAME}"
mkdir -p "$RUN_DIR"

# Check for existing checkpoint to resume from
LATEST_CHECKPOINT=""
for dir in "${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/v5_production_"*; do
    if [[ -d "$dir" ]] && [[ -f "${dir}/checkpoints/latest_checkpoint.pth" ]]; then
        LATEST_CHECKPOINT="${dir}/checkpoints/latest_checkpoint.pth"
        RUN_DIR="$dir"
        RUN_NAME=$(basename "$dir")
        echo "📂 Found existing run: $RUN_NAME"
        echo "   Will resume from checkpoint: $LATEST_CHECKPOINT"
        break
    fi
done

cd "$BEATSIGHT_REPO_ROOT"

# CUDA optimizations
export NVIDIA_TF32_OVERRIDE=1
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
export CUDNN_BENCHMARK=1

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                              ║"
echo "║   ██████╗ ███████╗ █████╗ ████████╗███████╗██╗ ██████╗ ██╗  ██╗████████╗    ║"
echo "║   ██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝    ║"
echo "║   ██████╔╝█████╗  ███████║   ██║   ███████╗██║██║  ███╗███████║   ██║       ║"
echo "║   ██╔══██╗██╔══╝  ██╔══██║   ██║   ╚════██║██║██║   ██║██╔══██║   ██║       ║"
echo "║   ██████╔╝███████╗██║  ██║   ██║   ███████║██║╚██████╔╝██║  ██║   ██║       ║"
echo "║   ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝       ║"
echo "║                                                                              ║"
echo "║                    PRODUCTION TRAINING - FINAL CONFIG                        ║"
echo "║                  World's Best AI Drum Transcription Model                    ║"
echo "║                                                                              ║"
echo "╠══════════════════════════════════════════════════════════════════════════════╣"
echo "║                                                                              ║"
echo "║  OPTIMIZED SETTINGS (from ablation study):                                   ║"
echo "║    • Data:       100% (14.6M samples)                                        ║"
echo "║    • Epochs:     100 (ambitious for best accuracy)                           ║"
echo "║    • LR:         0.0002 (higher = +4.47% improvement)                        ║"
echo "║    • Batch:      512 effective (smaller = +2.33% improvement)                ║"
echo "║    • Sampling:   Uniform balanced (no focal loss)                            ║"
echo "║    • Loss:       CrossEntropy (focal gamma caused collapse)                  ║"
echo "║                                                                              ║"
echo "║  ESTIMATED TIME: ~35-40 hours                                                ║"
echo "║  TARGET ACCURACY: 80-85%+ balanced accuracy                                  ║"
echo "║                                                                              ║"
echo "║  CHECKPOINTS: Every 5 epochs + every 5000 batches (~15 min)                  ║"
echo "║  STOP: Ctrl+C anytime (will resume from last checkpoint)                     ║"
echo "║                                                                              ║"
echo "╠══════════════════════════════════════════════════════════════════════════════╣"
echo "║  Output: $RUN_DIR"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Save config to run directory for reproducibility
cat > "$RUN_DIR/config_notes.txt" << 'EOF'
BEATSIGHT PRODUCTION TRAINING CONFIG
====================================
Date: $(date)
Run: production_final

ABLATION FINDINGS:
- Focal Loss gamma=3.0 + uniform sampling = class collapse (17/21 at 0%)
- LR 0.0002 > 0.0001 (+4.47% improvement)
- Batch 512 > 1024 (+2.33% improvement)  
- More data = better (almost linear scaling)

SETTINGS:
- 100% data (14,681,148 training samples)
- 100 epochs
- LR: 0.0002
- Effective batch: 512 (batch 256 × grad_accum 2)
- Uniform balanced sampling
- Plain CrossEntropy loss
- Cosine warm restarts (T0=20, Tmult=2)
- No regularization (drop_path=0, weight_decay=0)
- bfloat16 AMP
- Gradient checkpointing

BASELINE COMPARISON:
- V7 (5% data, 5 epochs): 54.27%
- E1 (10% data, 5 epochs): 61.69%
- Target (100% data, 100 epochs): 80-85%+
EOF

# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING COMMAND - ALL OPTIMIZED SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Build resume flag if checkpoint exists
RESUME_FLAG=""
if [[ -n "$LATEST_CHECKPOINT" ]] && [[ -f "$LATEST_CHECKPOINT" ]]; then
    RESUME_FLAG="--resume-from $LATEST_CHECKPOINT"
    echo ""
    echo "🔄 Resuming from: $LATEST_CHECKPOINT"
    echo ""
fi

PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --device cuda \
    \
    --epochs 100 \
    --batch-size 256 \
    --grad-accum-steps 2 \
    --lr 0.0002 \
    \
    --num-workers 4 \
    --val-num-workers 2 \
    --prefetch-factor 2 \
    --val-prefetch-factor 2 \
    --persistent-workers \
    --pin-memory \
    \
    --amp-dtype bfloat16 \
    \
    --train-fraction 1.0 \
    --val-fraction 1.0 \
    --subset-mode stratified \
    --min-samples-per-class 50 \
    \
    --model-version v5 \
    --v5-size large \
    --drop-path-rate 0.0 \
    \
    --mixup-alpha 0.0 \
    --cutmix-alpha 0.0 \
    --mixup-prob 0.0 \
    --specaugment none \
    --label-smoothing 0.0 \
    \
    --balanced-sampling \
    --sampling-strategy uniform \
    --class-weights none \
    \
    --scheduler cosine_warm_restarts \
    --warm-restart-t0 20 \
    --warm-restart-mult 2 \
    --warmup-epochs 2 \
    --warmup-lr-factor 0.1 \
    \
    --use-ema \
    --ema-decay 0.9995 \
    \
    --gradient-checkpointing \
    --grad-clip-norm 1.0 \
    --weight-decay 0.0 \
    --channels-last \
    \
    --output "$RUN_DIR" \
    --seed 42 \
    --checkpoint-every 5 \
    --checkpoint-every-batches 5000 \
    $RESUME_FLAG \
    2>&1 | tee -a "$RUN_DIR/training.log"

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                        TRAINING COMPLETE!                                    ║"
echo "╠══════════════════════════════════════════════════════════════════════════════╣"
echo "║  Results saved to: $RUN_DIR"
echo "║                                                                              ║"
echo "║  Models produced:                                                            ║"
echo "║    • best_drum_classifier.pth     - Best validation accuracy                 ║"
echo "║    • best_drum_classifier_ema.pth - EMA smoothed (often better)              ║"
echo "║                                                                              ║"
echo "║  Next steps:                                                                 ║"
echo "║    1. Check training.log for final accuracy                                  ║"
echo "║    2. Run evaluate_holdout.py on test set                                    ║"
echo "║    3. (Optional) Run ./auto_train.sh v5-distill for self-distillation        ║"
echo "║    4. (REQUIRED) Run ./auto_train.sh multilabel for simultaneous hits        ║"
echo "║    5. Export model for production                                            ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
