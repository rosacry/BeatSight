#!/bin/bash
# =============================================================================
# BeatSight Auto-Training Script
# =============================================================================
# Production training pipeline for the world's best drum transcription AI.
#
# RECOMMENDED TRAINING PATH (December 2025):
# ─────────────────────────────────────────────────────────────────────────────
#   1. train_production_final.sh     # Base classifier (100 epochs, ~35-40 hrs)
#   2. ./auto_train.sh v5-distill    # 17e - Self-distillation (optional, +1-2%)
#   3. ./auto_train.sh multilabel    # 19c - Simultaneous hits (REQUIRED)
#
# The production_final script uses optimized settings from ablation study:
#   • LR = 0.0002 (not 0.0001)
#   • Effective batch = 512 (not 1024)
#   • Uniform balanced sampling
#   • NO focal loss (caused class collapse)
#
# ABLATION RESULTS (for reference):
#   V7 baseline: 54.27% → A2 (LR 0.0002): 58.74% (+4.47%)
#   V7 baseline: 54.27% → B1 (batch 512): 56.60% (+2.33%)
#   V7 baseline: 54.27% → E1 (10% data):  61.69% (+7.42%)
#
# Usage:
#   ./train_production_final.sh      # Step 1: Base training (START HERE)
#   ./auto_train.sh v5-distill       # Step 2: Optional self-distillation
#   ./auto_train.sh multilabel       # Step 3: Multi-hit detection (REQUIRED)
#   ./auto_train.sh evaluate         # Step 4: Final evaluation
#
# Legacy/Debug modes (still available):
#   ./auto_train.sh label-audit      # Find mislabeled samples
#   ./auto_train.sh v5-warmup        # Quick validation run
#   ./auto_train.sh v5-local-balanced # Old full training (superseded)
#
# =============================================================================

set -o pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source environment variables
if [ -f "$SCRIPT_DIR/beatsight_env.sh" ]; then
    source "$SCRIPT_DIR/beatsight_env.sh"
fi

# Defaults (can be overridden by environment)
BEATSIGHT_REPO_ROOT=${BEATSIGHT_REPO_ROOT:-$REPO_ROOT}
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-${BEATSIGHT_REPO_ROOT}/data}
BEATSIGHT_CACHE_DIR=${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup_consolidated}
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_CACHE_DIR}}
BEATSIGHT_RUN_ROOT=${BEATSIGHT_RUN_ROOT:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/cutting_edge}

# Retry configuration
MAX_RETRIES=999
RETRY_DELAY=30
LOG_DIR="${BEATSIGHT_REPO_ROOT}/logs/auto_train"

# =============================================================================
# SHARED FLAG PRESETS
# =============================================================================

# V5 Model Architecture (Large with all enhancements)
V5_MODEL="--model-version v5 --v5-size large --drop-path-rate 0.15"

# Training Enhancements
V5_MIXUP="--mixup-alpha 0.2 --cutmix-alpha 0.5 --mixup-prob 0.5"
V5_AUGMENT="--specaugment drum"
# CHANGED: Disabled focal loss to prevent class collapse in early training
# Focal loss works AFTER the model learns all classes, not before
V5_LOSS="--label-smoothing 0.1"
V5_EMA="--use-ema --ema-decay 0.9995 --ema-warmup-steps 2000"
V5_EARLY_STOP="--early-stopping --early-stopping-patience 25 --early-stopping-min-delta 0.001 --early-stopping-warmup 10"
V5_GRAD_CKPT="--gradient-checkpointing"

# Balanced Sampling (CRITICAL for rare class accuracy)
# CHANGED: Use 'uniform' for more aggressive balancing with severe imbalance (630x)
V5_BALANCED="--balanced-sampling --sampling-strategy uniform --class-weights none"

# Learning Rate Schedule
# CHANGED: Extended warmup and lower initial LR factor for stability
V5_SCHEDULER="--scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 --warmup-epochs 8 --warmup-lr-factor 0.05"

# =============================================================================
# HARDWARE DETECTION
# =============================================================================
detect_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
        GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
        
        if [[ "$GPU_NAME" == *"H100"* ]] || [[ "$GPU_NAME" == *"A100"* ]]; then
            echo "cloud"
        elif [[ "$GPU_NAME" == *"3080"* ]] || [[ "$GPU_NAME" == *"3090"* ]] || [[ "$GPU_NAME" == *"4080"* ]] || [[ "$GPU_NAME" == *"4090"* ]]; then
            echo "local"
        else
            echo "unknown"
        fi
    else
        echo "none"
    fi
}

# =============================================================================
# LOGGING
# =============================================================================
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/auto_train_$(date +%Y%m%d_%H%M%S).log"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

# =============================================================================
# CHECKPOINT HANDLING
# =============================================================================
get_checkpoint() {
    local run_dir="$1"
    local checkpoint="${run_dir}/checkpoints/latest_checkpoint.pth"
    if [ -f "$checkpoint" ]; then
        echo "$checkpoint"
    else
        echo ""
    fi
}

# =============================================================================
# PARSE ARGUMENTS
# =============================================================================
TRAIN_MODE="${1:-help}"
shift 2>/dev/null || true

case "$TRAIN_MODE" in
    # =========================================================================
    # V5 PRODUCTION (PRIMARY) - Full optimized training
    # =========================================================================
    # This is the main training command - runs train_production_final.sh
    # Usage: ./auto_train.sh v5
    # =========================================================================
    v5|v5-production|production|prod)
        log "🚀 Starting V5 PRODUCTION training (optimized config)..."
        log "   Delegating to train_production_final.sh"
        exec "$SCRIPT_DIR/train_production_final.sh"
        ;;
    
    # =========================================================================
    # LABEL AUDIT (14) - Find mislabeled samples
    # =========================================================================
    label-audit|audit|14)
        log "🔍 Starting LABEL AUDIT (Confident Learning)..."
        RUN_DIR="${BEATSIGHT_RUN_ROOT}/audits"
        mkdir -p "$RUN_DIR"
        
        cd "$BEATSIGHT_REPO_ROOT"
        PYTHONPATH=ai-pipeline python ai-pipeline/training/audit/audit_labels.py \
            --dataset "${BEATSIGHT_DATASET_DIR}" \
            --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
            --output-dir "$RUN_DIR" \
            --num-workers 4 \
            --device cuda \
            --epochs 15 \
            --k-folds 3 \
            --threshold 0.25
        
        log "✅ Label audit complete! Check $RUN_DIR for noisy labels report."
        ;;
    
    # =========================================================================
    # V5 WARMUP (17a) - Quick validation run
    # =========================================================================
    v5-warmup|warmup|17a)
        log "🚀 Starting V5 WARMUP validation..."
        RUN_DIR="${BEATSIGHT_RUN_ROOT}/v5/warmup"
        mkdir -p "$RUN_DIR"
        
        CHECKPOINT=$(get_checkpoint "$RUN_DIR")
        RESUME_FLAG=""
        [[ -n "$CHECKPOINT" ]] && RESUME_FLAG="--resume-from $CHECKPOINT"
        
        cd "$BEATSIGHT_REPO_ROOT"
        PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
            --dataset "${BEATSIGHT_DATASET_DIR}" \
            --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
            --device cuda \
            --epochs 10 \
            --batch-size 256 \
            --lr 0.001 \
            --num-workers 4 --val-num-workers 2 \
            --persistent-workers --pin-memory \
            --amp-dtype bfloat16 \
            $V5_MODEL $V5_MIXUP $V5_AUGMENT $V5_LOSS $V5_EMA \
            --scheduler cosine --warmup-epochs 2 \
            --grad-clip-norm 1.0 --weight-decay 0.01 \
            --output "$RUN_DIR" \
            --checkpoint-every 2 \
            --wandb-project beatsight-v5 \
            $RESUME_FLAG
        
        log "✅ V5 warmup complete! Check validation metrics before proceeding."
        ;;
    
    # =========================================================================
    # V5 LOCAL BALANCED (17d-balanced) - Full training for local GPU ⭐
    # =========================================================================
    v5-local-balanced|v5-balanced|balanced|17d-balanced|17d)
        log "🎯 Starting V5 LOCAL BALANCED training (UNIFORM sampling)..."
        log "   Hardware: RTX 3080 Ti (12GB), optimized batch/worker settings"
        log "   Critical: Uses UNIFORM balanced sampling for all 21 classes"
        RUN_DIR="${BEATSIGHT_RUN_ROOT}/v5/local-balanced"
        mkdir -p "$RUN_DIR"
        
        # Local GPU optimizations
        export NVIDIA_TF32_OVERRIDE=1
        export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
        export CUDNN_BENCHMARK=1
        
        CHECKPOINT=$(get_checkpoint "$RUN_DIR")
        RESUME_FLAG=""
        [[ -n "$CHECKPOINT" ]] && RESUME_FLAG="--resume-from $CHECKPOINT" && log "   📂 Resuming from checkpoint"
        
        cd "$BEATSIGHT_REPO_ROOT"
        PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
            --dataset "${BEATSIGHT_DATASET_DIR}" \
            --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
            --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
            --device cuda \
            --epochs 100 \
            --batch-size 512 \
            --grad-accum-steps 3 \
            --lr 0.0008 \
            --num-workers 4 --val-num-workers 4 --prefetch-factor 4 --val-prefetch-factor 4 \
            --persistent-workers --pin-memory \
            --amp-dtype bfloat16 \
            --cache-warmup --cache-warmup-samples 500000 \
            $V5_MODEL $V5_MIXUP $V5_AUGMENT $V5_LOSS $V5_EMA \
            $V5_BALANCED $V5_EARLY_STOP $V5_GRAD_CKPT \
            $V5_SCHEDULER \
            --grad-clip-norm 1.0 --weight-decay 0.01 \
            --channels-last \
            --output "$RUN_DIR" \
            --seed 1337 \
            --checkpoint-every 5 --checkpoint-every-batches 5000 \
            --val-fraction 0.05 \
            --wandb-project beatsight-v5 \
            $RESUME_FLAG
        
        log "✅ V5 LOCAL BALANCED training complete!"
        log "📁 Best model: $RUN_DIR/best_drum_classifier.pth"
        ;;
    
    # =========================================================================
    # V5 DISTILL (17e-local) - Self-distillation from production model
    # =========================================================================
    # UPDATED Dec 2025: Uses optimized settings from ablation study
    # - LR: 0.0001 (lower than base training for fine-tuning)
    # - Effective batch: 512 (batch 256, grad_accum 2)
    # - Uniform balanced sampling
    # - No focal loss
    # =========================================================================
    v5-distill|distill|17e-local|17e)
        log "🔄 Starting V5 SELF-DISTILLATION (Born-Again Networks)..."
        RUN_DIR="${BEATSIGHT_RUN_ROOT}/v5/production-distill"
        
        # Find teacher model from production training
        TEACHER_DIRS=(
            "${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/production_final"*
            "${BEATSIGHT_RUN_ROOT}/v5/local-balanced"
        )
        
        TEACHER=""
        for dir in "${TEACHER_DIRS[@]}"; do
            if [[ -d "$dir" ]]; then
                if [[ -f "${dir}/best_drum_classifier_ema.pth" ]]; then
                    TEACHER="${dir}/best_drum_classifier_ema.pth"
                    break
                elif [[ -f "${dir}/best_drum_classifier.pth" ]]; then
                    TEACHER="${dir}/best_drum_classifier.pth"
                    break
                fi
            fi
        done
        
        if [[ -z "$TEACHER" || ! -f "$TEACHER" ]]; then
            log "❌ ERROR: Teacher model not found!"
            log "   Run train_production_final.sh first, then run distillation."
            log "   Searched in:"
            for dir in "${TEACHER_DIRS[@]}"; do
                log "     - $dir"
            done
            exit 1
        fi
        log "   Teacher model: $TEACHER"
        
        mkdir -p "$RUN_DIR"
        export NVIDIA_TF32_OVERRIDE=1
        export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
        
        CHECKPOINT=$(get_checkpoint "$RUN_DIR")
        RESUME_FLAG=""
        [[ -n "$CHECKPOINT" ]] && RESUME_FLAG="--resume-from $CHECKPOINT"
        
        cd "$BEATSIGHT_REPO_ROOT"
        PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
            --dataset "${BEATSIGHT_DATASET_DIR}" \
            --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
            --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
            --device cuda \
            --epochs 50 \
            --batch-size 256 \
            --grad-accum-steps 2 \
            --lr 0.0001 \
            --num-workers 4 --val-num-workers 2 --prefetch-factor 2 \
            --persistent-workers --pin-memory \
            --amp-dtype bfloat16 \
            --model-version v5 --v5-size large --drop-path-rate 0.0 \
            --mixup-alpha 0.0 --cutmix-alpha 0.0 --mixup-prob 0.0 \
            --specaugment none \
            --label-smoothing 0.0 \
            --balanced-sampling --sampling-strategy uniform --class-weights none \
            --scheduler cosine_warm_restarts --warm-restart-t0 20 --warm-restart-mult 2 \
            --warmup-epochs 2 --warmup-lr-factor 0.1 \
            --gradient-checkpointing \
            --distill-from "$TEACHER" --distill-alpha 0.7 --distill-temperature 4.0 \
            --grad-clip-norm 1.0 --weight-decay 0.0 \
            --channels-last \
            --output "$RUN_DIR" \
            --seed 42 \
            --checkpoint-every 5 \
            --early-stopping --early-stopping-patience 15 --early-stopping-min-delta 0.001 \
            $RESUME_FLAG
        
        log "✅ V5 DISTILL training complete!"
        log "📁 Production model: $RUN_DIR/best_drum_classifier.pth"
        ;;
    
    # =========================================================================
    # MULTILABEL (19c) - Simultaneous drum detection
    # =========================================================================
    # PURPOSE: Detect multiple drums hit at the same time (e.g., kick + hi-hat)
    # This is CRITICAL for real drum transcription where simultaneous hits
    # are the norm, not the exception.
    #
    # UPDATED Dec 2025: Uses optimized settings from ablation study
    # =========================================================================
    multilabel|multi|19c|19)
        log "🥁 Starting MULTILABEL fine-tuning (simultaneous drum detection)..."
        RUN_DIR="${BEATSIGHT_RUN_ROOT}/multilabel/finetune"
        MULTILABEL_DATA="${BEATSIGHT_OUTPUT_ROOT:-E:/data}/multilabel_dataset"
        
        # Find pretrained model from production training or distillation
        PRETRAINED_DIRS=(
            "${BEATSIGHT_RUN_ROOT}/v5/production-distill"
            "${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/production_final"*
            "${BEATSIGHT_RUN_ROOT}/v5/local-balanced"
        )
        
        PRETRAINED=""
        for dir in "${PRETRAINED_DIRS[@]}"; do
            if [[ -d "$dir" ]]; then
                if [[ -f "${dir}/best_drum_classifier_ema.pth" ]]; then
                    PRETRAINED="${dir}/best_drum_classifier_ema.pth"
                    break
                elif [[ -f "${dir}/best_drum_classifier.pth" ]]; then
                    PRETRAINED="${dir}/best_drum_classifier.pth"
                    break
                fi
            fi
        done
        
        if [[ -z "$PRETRAINED" || ! -f "$PRETRAINED" ]]; then
            log "⚠️  No pretrained model found. Training from scratch (not recommended)..."
            log "   For best results, run train_production_final.sh first."
            PRETRAINED_FLAG=""
        else
            log "   Pretrained model: $PRETRAINED"
            PRETRAINED_FLAG="--pretrained-checkpoint $PRETRAINED"
        fi
        
        # Check for multilabel dataset
        if [[ ! -d "${MULTILABEL_DATA}" ]] || [[ ! -f "${MULTILABEL_DATA}/multilabel_events.jsonl" ]]; then
            log "⚠️  Multilabel dataset not found at: ${MULTILABEL_DATA}"
            log "   Generating multilabel dataset from training data..."
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/generate_multilabel_dataset.py \
                --input-dir "${BEATSIGHT_DATASET_DIR}" \
                --output-dir "${MULTILABEL_DATA}" \
                --window-ms 30 \
                --min-overlap 2
            
            if [[ ! -f "${MULTILABEL_DATA}/multilabel_events.jsonl" ]]; then
                log "❌ ERROR: Failed to generate multilabel dataset!"
                exit 1
            fi
            log "✅ Multilabel dataset generated!"
        fi
        
        mkdir -p "$RUN_DIR"
        export NVIDIA_TF32_OVERRIDE=1
        export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"
        
        cd "$BEATSIGHT_REPO_ROOT"
        PYTHONPATH=ai-pipeline python ai-pipeline/training/multilabel/train_multilabel.py \
            --dataset "$MULTILABEL_DATA" \
            --events-file "multilabel_events.jsonl" \
            --cache-dir "${BEATSIGHT_CACHE_DIR}" \
            --epochs 50 \
            --batch-size 256 \
            --lr 0.0002 \
            --model-version v5 \
            --v5-size large \
            --drop-path-rate 0.0 \
            --loss-type bce \
            --label-smoothing 0.0 \
            --use-amp \
            $PRETRAINED_FLAG \
            --output-dir "$RUN_DIR"
        
        log "✅ MULTILABEL training complete!"
        log "📁 Model: $RUN_DIR/best_multilabel_model.pt"
        log ""
        log "🎯 Your drum transcription pipeline is now complete!"
        log "   Single-hit classifier + Multi-hit detector = Full transcription"
        ;;
    
    # =========================================================================
    # V5 CLOUD (17d) - Full training for cloud GPU (H100/A100)
    # =========================================================================
    v5-cloud|cloud|17d-cloud)
        log "☁️  Starting V5 CLOUD training (optimized for H100/A100)..."
        RUN_DIR="${BEATSIGHT_RUN_ROOT}/v5/full-cached"
        mkdir -p "$RUN_DIR"
        
        CHECKPOINT=$(get_checkpoint "$RUN_DIR")
        RESUME_FLAG=""
        [[ -n "$CHECKPOINT" ]] && RESUME_FLAG="--resume-from $CHECKPOINT"
        
        cd "$BEATSIGHT_REPO_ROOT"
        PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
            --dataset "${BEATSIGHT_DATASET_DIR}" \
            --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
            --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
            --device cuda \
            --epochs 200 \
            --batch-size 768 \
            --grad-accum-steps 2 \
            --lr 0.002 \
            --num-workers 12 --val-num-workers 6 --prefetch-factor 4 \
            --persistent-workers --pin-memory \
            --amp-dtype bfloat16 \
            --torch-compile --torch-compile-mode max-autotune \
            --cache-warmup --cache-warmup-samples 1000000 \
            $V5_MODEL $V5_MIXUP $V5_AUGMENT $V5_LOSS $V5_EMA \
            $V5_BALANCED $V5_EARLY_STOP $V5_GRAD_CKPT \
            $V5_SCHEDULER \
            --grad-clip-norm 1.0 --weight-decay 0.01 \
            --channels-last \
            --output "$RUN_DIR" \
            --seed 1337 \
            --checkpoint-every 5 \
            --wandb-project beatsight-v5 \
            $RESUME_FLAG
        
        log "✅ V5 CLOUD training complete!"
        ;;
    
    # =========================================================================
    # V5 CLOUD DISTILL (17f) - Self-distillation on cloud GPU
    # =========================================================================
    v5-cloud-distill|cloud-distill|17f)
        log "☁️  Starting V5 CLOUD DISTILLATION..."
        RUN_DIR="${BEATSIGHT_RUN_ROOT}/v5/self-distill-cached"
        TEACHER_DIR="${BEATSIGHT_RUN_ROOT}/v5/full-cached"
        
        TEACHER="${TEACHER_DIR}/best_drum_classifier_ema.pth"
        [[ ! -f "$TEACHER" ]] && TEACHER="${TEACHER_DIR}/best_drum_classifier.pth"
        
        if [[ ! -f "$TEACHER" ]]; then
            log "❌ ERROR: Teacher model not found! Run v5-cloud first."
            exit 1
        fi
        
        mkdir -p "$RUN_DIR"
        
        CHECKPOINT=$(get_checkpoint "$RUN_DIR")
        RESUME_FLAG=""
        [[ -n "$CHECKPOINT" ]] && RESUME_FLAG="--resume-from $CHECKPOINT"
        
        cd "$BEATSIGHT_REPO_ROOT"
        PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
            --dataset "${BEATSIGHT_DATASET_DIR}" \
            --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
            --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
            --device cuda \
            --epochs 200 \
            --batch-size 768 \
            --grad-accum-steps 2 \
            --lr 0.001 \
            --num-workers 12 --val-num-workers 6 --prefetch-factor 4 \
            --persistent-workers --pin-memory \
            --amp-dtype bfloat16 \
            --torch-compile --torch-compile-mode max-autotune \
            $V5_MODEL $V5_MIXUP $V5_AUGMENT $V5_LOSS $V5_EMA \
            $V5_BALANCED $V5_EARLY_STOP $V5_GRAD_CKPT \
            $V5_SCHEDULER \
            --distill-from "$TEACHER" --distill-alpha 0.7 --distill-temperature 4.0 \
            --grad-clip-norm 1.0 --weight-decay 0.01 \
            --channels-last \
            --output "$RUN_DIR" \
            --seed 42 \
            --checkpoint-every 5 \
            --wandb-project beatsight-v5 \
            $RESUME_FLAG
        
        log "✅ V5 CLOUD DISTILL complete!"
        ;;
    
    # =========================================================================
    # EVALUATE (21) - Holdout test set evaluation
    # =========================================================================
    evaluate|eval|21)
        log "📊 Starting HOLDOUT EVALUATION..."
        RUN_DIR="${BEATSIGHT_RUN_ROOT}/evaluation"
        mkdir -p "$RUN_DIR"
        
        # Find best model
        MODEL="${BEATSIGHT_RUN_ROOT}/v5/local-balanced-distill/best_drum_classifier_ema.pth"
        [[ ! -f "$MODEL" ]] && MODEL="${BEATSIGHT_RUN_ROOT}/v5/local-balanced/best_drum_classifier.pth"
        
        if [[ ! -f "$MODEL" ]]; then
            log "❌ ERROR: No model found to evaluate!"
            exit 1
        fi
        log "   Model: $MODEL"
        
        cd "$BEATSIGHT_REPO_ROOT"
        PYTHONPATH=ai-pipeline python ai-pipeline/training/evaluate_holdout.py \
            --model-checkpoint "$MODEL" \
            --holdout-sources "enst_drums,mdb_drums" \
            --output-dir "$RUN_DIR" \
            --device cuda
        
        log "✅ Holdout evaluation complete! Check $RUN_DIR for results."
        ;;
    
    # =========================================================================
    # LEGACY MODE REDIRECT
    # =========================================================================
    legacy|old|experimental)
        log "📦 Legacy modes have been moved to auto_train_legacy.sh"
        log ""
        log "Available legacy modes:"
        log "  - warmup, quick, long (v1 baseline)"
        log "  - cutting-edge-* (v2 SE-attention)"
        log "  - ensemble-* (multi-model ensemble)"
        log "  - ast-* (Audio Spectrogram Transformer)"
        log "  - enhanced-* (v4 CoordAttn)"
        log "  - temporal-* (Mamba research)"
        log "  - ultimate-* (Wav2Vec2 fusion)"
        log "  - beats-* (Microsoft BEATs)"
        log ""
        log "Run: bash auto_train_legacy.sh <mode>"
        ;;
    
    # =========================================================================
    # HELP
    # =========================================================================
    help|--help|-h|*)
        echo ""
        echo "╔══════════════════════════════════════════════════════════════════╗"
        echo "║           BeatSight Training Pipeline (Simplified)               ║"
        echo "╚══════════════════════════════════════════════════════════════════╝"
        echo ""
        echo "🎯 RECOMMENDED PATH (Local GPU - RTX 3080 Ti / 4080 / 4090):"
        echo ""
        echo "   1. ./auto_train.sh label-audit      # 14  - Find bad labels (~30min)"
        echo "   2. ./auto_train.sh v5               # PRODUCTION - Full 100% (~35-40hr) ⭐⭐"
        echo "   3. ./auto_train.sh v5-distill       # 17e - Self-distillation (~35-40hr)"
        echo "   4. ./post_export_commands.sh        # 19  - Generate multilabel data"
        echo "   5. ./auto_train.sh multilabel       # 19c - Multilabel finetune (~6-12hr)"
        echo "   6. ./auto_train.sh evaluate         # 21  - Test on holdout set"
        echo ""
        echo "   Aliases:"
        echo "   ./auto_train.sh v5-production       # Same as v5"
        echo "   ./auto_train.sh v5-warmup           # Quick validation (~2hr, 5% data)"
        echo "   ./auto_train.sh v5-local-balanced   # Legacy alias for v5"
        echo ""
        echo "☁️  CLOUD PATH (Lambda H100 / A100):"
        echo ""
        echo "   ./auto_train.sh v5-cloud            # 17d - Full cached (~24hr)"
        echo "   ./auto_train.sh v5-cloud-distill    # 17f - Self-distillation (~24hr)"
        echo ""
        echo "📦 Legacy modes (v1-v4, experimental): ./auto_train_legacy.sh"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📍 Current: v5 runs train_production_final.sh (100% data, optimized)"
        echo "📖 Full docs: docs/PATH_TO_90_PERCENT.md"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        ;;
esac
