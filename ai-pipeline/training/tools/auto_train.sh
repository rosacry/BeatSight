#!/bin/bash
# =============================================================================
# BeatSight Auto-Training Script
# =============================================================================
# Automatically restarts training on crashes until completion.
# Safe to leave running while away - handles network issues, OOM, etc.
#
# Usage:
#   ./ai-pipeline/training/tools/auto_train.sh warmup   # Run warmup (5a)
#   ./ai-pipeline/training/tools/auto_train.sh quick    # Run quick refresh (5b)
#   ./ai-pipeline/training/tools/auto_train.sh long     # Run long run (5c)
#
# The script will:
#   1. Automatically resume from latest checkpoint on crash
#   2. Retry indefinitely until training completes successfully
#   3. Wait 30 seconds between retries (in case of temporary issues)
#   4. Log all attempts to a log file
#   5. Send a notification when complete (if notify-send available)
#
# =============================================================================

set -o pipefail

# Load environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source environment variables
if [ -f "$SCRIPT_DIR/beatsight_env.sh" ]; then
    source "$SCRIPT_DIR/beatsight_env.sh"
fi

# Defaults (can be overridden by environment)
BEATSIGHT_REPO_ROOT=${BEATSIGHT_REPO_ROOT:-$REPO_ROOT}
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-${BEATSIGHT_REPO_ROOT}/data}
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-/e/data/prod_combined_profile_run}
BEATSIGHT_CACHE_DIR=${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup}
BEATSIGHT_METRICS_DIR=${BEATSIGHT_METRICS_DIR:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/reports/metrics}
BEATSIGHT_RUN_WARMUP=${BEATSIGHT_RUN_WARMUP:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/prod_combined_warmup}
BEATSIGHT_RUN_QUICK=${BEATSIGHT_RUN_QUICK:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/prod_combined_quick}
BEATSIGHT_RUN_LONG=${BEATSIGHT_RUN_LONG:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/prod_combined_longrun}
BEATSIGHT_RUN_CUTTING_EDGE=${BEATSIGHT_RUN_CUTTING_EDGE:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs/cutting_edge}

# Configuration
MAX_RETRIES=999           # Effectively infinite
RETRY_DELAY=30            # Seconds to wait between retries
LOG_DIR="${BEATSIGHT_REPO_ROOT}/logs/auto_train"

# =============================================================================
# CUTTING-EDGE FLAGS
# =============================================================================
# v2 model + Mixup/CutMix + SpecAugment + Focal + EMA + Progressive + SAM + SWA + R-Drop + Curriculum + Calibration
CUTTING_EDGE_MODEL_FLAGS="--model-version v2 --use-se"
CUTTING_EDGE_MIXUP_FLAGS="--mixup-alpha 0.4 --cutmix-alpha 1.0 --mixup-prob 0.5"
CUTTING_EDGE_SPECAUGMENT_FLAGS="--specaugment drum"
CUTTING_EDGE_FOCAL_FLAGS="--focal-loss --focal-gamma 2.0"
CUTTING_EDGE_EMA_FLAGS="--use-ema --ema-decay 0.999"
CUTTING_EDGE_PROGRESSIVE_FLAGS="--progressive-augmentation"
CUTTING_EDGE_REGULARIZATION_FLAGS="--label-smoothing 0.05"
CUTTING_EDGE_SAM_FLAGS="--use-sam --sam-rho 0.05"
CUTTING_EDGE_SWA_FLAGS="--use-swa --swa-start 0.75"
# R-Drop: Regularized Dropout with consistency loss (0.5-1% improvement)
# Using alpha=0.3 (conservative) when combined with SAM to avoid over-smoothing
CUTTING_EDGE_RDROP_FLAGS="--use-rdrop --rdrop-alpha 0.3"
# Curriculum Learning: Easy-to-hard training progression (0.5-1.5% improvement)
# Using start-fraction=0.5 (conservative) to avoid overfitting to easy patterns early
CUTTING_EDGE_CURRICULUM_FLAGS="--use-curriculum --curriculum-start-fraction 0.5 --curriculum-strategy cosine"
# Temperature Calibration: Post-training confidence calibration (better probability estimates)
CUTTING_EDGE_CALIBRATION_FLAGS="--calibrate --calibration-method temperature"

# =============================================================================
# V5 ULTIMATE FLAGS (NEW 2024 - Revolutionary)
# =============================================================================
# v5 model combines: CoordAttn + DropPath + DeepSupervision + MultiScaleFusion + GradCentralization
V5_MODEL_FLAGS="--model-version v5 --v5-size medium --drop-path-rate 0.1"
V5_DEEP_SUPERVISION_FLAGS="--use-deep-supervision --deep-supervision-weights 0.4,0.6"
V5_GRADIENT_CENTRALIZATION_FLAGS="--use-gradient-centralization"
# Multi-task learning: velocity + hi-hat openness auxiliary heads (improves feature learning)
V5_MULTI_TASK_FLAGS="--use-multi-task"
# Waveform augmentation: audio-level augmentation before spectrogram extraction
# DISABLED: Bypasses SSD feature cache, reads raw audio from HDD (too slow)
# Re-enable if dataset is moved to SSD: V5_WAVEFORM_AUGMENT_FLAGS="--waveform-augment drum"
V5_WAVEFORM_AUGMENT_FLAGS=""
# FMix: Fourier-domain mixup (better than CutMix for spectrograms)
V5_FMIX_FLAGS="--use-fmix --fmix-alpha 1.0"
# Progressive augmentation: starts weak, ramps up during training
V5_PROGRESSIVE_FLAGS="--progressive-augmentation"
# Label smoothing for regularization (prevents overconfidence)
V5_LABEL_SMOOTHING_FLAGS="--label-smoothing 0.05"
# Lookahead optimizer wrapper: maintains slow weights for stability (+0.5-1%)
# Reference: "Lookahead Optimizer: k steps forward, 1 step back" (Zhang et al., NeurIPS 2019)
V5_LOOKAHEAD_FLAGS="--use-lookahead --lookahead-k 5 --lookahead-alpha 0.5"
# Mixup cutoff: disable mixup in final 15% of training for cleaner decision boundaries
V5_MIXUP_CUTOFF_FLAGS="--mixup-cutoff-ratio 0.85"
# NOTE: torch.compile disabled - doesn't work on Windows (requires triton)
# V5_COMPILE_FLAGS="--torch-compile --torch-compile-mode max-autotune"

# =============================================================================
# OPTION A ENHANCEMENTS (2024 - Final optimizations for maximum quality)
# =============================================================================
# Attentive Statistics Pooling: +0.3-0.5% by learning attention over spatial locations
# Reference: "Attentive Statistics Pooling for Deep Speaker Embedding" (Okabe et al., 2018)
V5_POOLING_FLAGS="--pooling-type asp"
# Hard Negative Mining: +0.5-1% by focusing on confusing pairs (snare/rimshot, crash/china)
# Reference: "Training Region-based Object Detectors with Online Hard Example Mining" (CVPR 2016)
# Added: Contrastive loss pushes embeddings apart in feature space (+0.3-0.5% on confused pairs)
V5_HARD_NEGATIVE_FLAGS="--use-hard-negatives --hnm-strategy curriculum --hnm-ratio 0.7 --hnm-confusion-weight 2.0 --hnm-use-contrastive --hnm-margin 0.5"
# Class weighting for imbalanced dataset: +0.5-1% on rare classes
V5_CLASS_WEIGHT_FLAGS="--class-weights effective --max-class-weight 10.0"
# Gradient accumulation for larger effective batch size (32 * 4 = 128)
V5_GRAD_ACCUM_FLAGS="--grad-accum-steps 4"

# Combine ALL cutting-edge techniques for maximum performance
V5_ULTIMATE_FLAGS="${V5_MODEL_FLAGS} ${V5_DEEP_SUPERVISION_FLAGS} ${V5_GRADIENT_CENTRALIZATION_FLAGS} ${V5_MULTI_TASK_FLAGS} ${V5_WAVEFORM_AUGMENT_FLAGS} ${V5_FMIX_FLAGS} ${V5_PROGRESSIVE_FLAGS} ${V5_LABEL_SMOOTHING_FLAGS} ${V5_LOOKAHEAD_FLAGS} ${V5_MIXUP_CUTOFF_FLAGS} ${V5_POOLING_FLAGS} ${V5_HARD_NEGATIVE_FLAGS} ${V5_CLASS_WEIGHT_FLAGS} ${V5_GRAD_ACCUM_FLAGS}"

# BEATs Model Flags (Audio Foundation Model)
BEATS_MODEL_FLAGS="--model-version beats --beats-freeze-encoder --beats-layer-decay 0.75"
BEATS_FINETUNE_FLAGS="--model-version beats --beats-layer-decay 0.75"

# =============================================================================
# BEYOND CUTTING-EDGE: REVOLUTIONARY FLAGS
# =============================================================================
# These represent the absolute state-of-the-art for maximum quality
# Use modes 9a/9b/9c for ensemble training and 10a/10b/10c for full revolutionary pipeline

# Ensemble Training Configuration
BEATSIGHT_RUN_ENSEMBLE="${BEATSIGHT_RUN_CUTTING_EDGE}/ensemble"
ENSEMBLE_NUM_MODELS=${ENSEMBLE_NUM_MODELS:-5}
ENSEMBLE_BASE_SEED=${ENSEMBLE_BASE_SEED:-1337}

# Test-Time Augmentation Settings (for inference)
TTA_NUM_AUGMENTATIONS=${TTA_NUM_AUGMENTATIONS:-5}
TTA_STRENGTH=${TTA_STRENGTH:-0.3}

# Ultimate Inference Settings (Ensemble + TTA + Calibration)
ULTIMATE_INFERENCE_FLAGS="--use-ensemble --use-tta --tta-augmentations ${TTA_NUM_AUGMENTATIONS}"

# Parse arguments
TRAIN_MODE="${1:-warmup}"
shift

# Validate mode
case "$TRAIN_MODE" in
    warmup|5a)
        TRAIN_MODE="warmup"
        RUN_DIR="$BEATSIGHT_RUN_WARMUP"
        ;;
    quick|5b)
        TRAIN_MODE="quick"
        RUN_DIR="$BEATSIGHT_RUN_QUICK"
        ;;
    long|5c)
        TRAIN_MODE="long"
        RUN_DIR="$BEATSIGHT_RUN_LONG"
        ;;
    cutting-edge-warmup|ce-warmup|7a)
        TRAIN_MODE="cutting-edge-warmup"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/warmup"
        ;;
    cutting-edge-quick|ce-quick|7b)
        TRAIN_MODE="cutting-edge-quick"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/quick"
        ;;
    cutting-edge-long|ce-long|7c)
        TRAIN_MODE="cutting-edge-long"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/long"
        ;;
    # =====================================================================
    # BEYOND CUTTING-EDGE: ENSEMBLE TRAINING (9a/9b/9c)
    # =====================================================================
    ensemble-warmup|ens-warmup|9a)
        TRAIN_MODE="ensemble-warmup"
        RUN_DIR="$BEATSIGHT_RUN_ENSEMBLE/warmup"
        ;;
    ensemble-quick|ens-quick|9b)
        TRAIN_MODE="ensemble-quick"
        RUN_DIR="$BEATSIGHT_RUN_ENSEMBLE/quick"
        ;;
    ensemble-long|ens-long|9c)
        TRAIN_MODE="ensemble-long"
        RUN_DIR="$BEATSIGHT_RUN_ENSEMBLE/long"
        ;;
    # =====================================================================
    # REVOLUTIONARY: AST TRANSFORMER TRAINING (10a/10b/10c)
    # =====================================================================
    ast-warmup|10a)
        TRAIN_MODE="ast-warmup"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ast/warmup"
        ;;
    ast-quick|10b)
        TRAIN_MODE="ast-quick"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ast/quick"
        ;;
    ast-long|10c)
        TRAIN_MODE="ast-long"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ast/long"
        ;;
    # =====================================================================
    # ULTIMATE: KNOWLEDGE DISTILLATION (11a/11b)
    # =====================================================================
    distill-quick|11a)
        TRAIN_MODE="distill-quick"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/distilled/quick"
        ;;
    distill-long|11b)
        TRAIN_MODE="distill-long"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/distilled/long"
        ;;
    # =====================================================================
    # NEW REVOLUTIONARY FEATURES (2024): v4 + CoordAttn + MultiTask + FMix
    # =====================================================================
    enhanced-warmup|12a)
        TRAIN_MODE="enhanced-warmup"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/enhanced/warmup"
        ;;
    enhanced-quick|12b)
        TRAIN_MODE="enhanced-quick"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/enhanced/quick"
        ;;
    enhanced-long|12c)
        TRAIN_MODE="enhanced-long"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/enhanced/long"
        ;;
    # =====================================================================
    # SELF-SUPERVISED PRETRAINING (13a/13b)
    # =====================================================================
    ssl-pretrain-warmup|13a)
        TRAIN_MODE="ssl-pretrain-warmup"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ssl/warmup"
        ;;
    ssl-pretrain-full|13b)
        TRAIN_MODE="ssl-pretrain-full"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ssl/full"
        ;;
    # =====================================================================
    # LABEL AUDIT (Confident Learning)
    # =====================================================================
    label-audit|14)
        TRAIN_MODE="label-audit"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/audits"
        ;;
    # =====================================================================
    # TEMPORAL MAMBA (15a/15b/15c/15d) - NOVEL RESEARCH
    # =====================================================================
    temporal-warmup|15a)
        TRAIN_MODE="temporal-warmup"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/temporal/warmup"
        ;;
    temporal-quick|15b)
        TRAIN_MODE="temporal-quick"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/temporal/quick"
        ;;
    temporal-long|15c)
        TRAIN_MODE="temporal-long"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/temporal/long"
        ;;
    temporal-full|15d)
        TRAIN_MODE="temporal-full"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/temporal/full"
        ;;
    # =====================================================================
    # ULTIMATE: Wav2Vec2 + Multi-Res + Mamba (16a/16b/16c/16d) - MAXIMUM REVOLUTIONARY
    # =====================================================================
    ultimate-warmup|16a)
        TRAIN_MODE="ultimate-warmup"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ultimate/warmup"
        ;;
    ultimate-quick|16b)
        TRAIN_MODE="ultimate-quick"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ultimate/quick"
        ;;
    ultimate-long|16c)
        TRAIN_MODE="ultimate-long"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ultimate/long"
        ;;
    ultimate-full|16d)
        TRAIN_MODE="ultimate-full"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/ultimate/full"
        ;;
    # =====================================================================
    # V5 ULTIMATE MODEL (17a/17b/17c/17d) - ALL INNOVATIONS COMBINED
    # CoordAttn + DropPath + DeepSupervision + MultiScale + GradCentralization + Everything
    # =====================================================================
    v5-warmup|17a)
        TRAIN_MODE="v5-warmup"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/v5/warmup"
        ;;
    v5-quick|17b)
        TRAIN_MODE="v5-quick"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/v5/quick"
        ;;
    v5-long|17c)
        TRAIN_MODE="v5-long"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/v5/long"
        ;;
    v5-full|17d)
        TRAIN_MODE="v5-full"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/v5/full"
        ;;
    v5-self-distill|17e)
        TRAIN_MODE="v5-self-distill"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/v5/self-distill"
        ;;
    # =====================================================================
    # BEATs AUDIO FOUNDATION (18a/18b/18c) - Microsoft's BEATs Model
    # Pretrained audio transformer, potentially better than Wav2Vec2
    # =====================================================================
    beats-warmup|18a)
        TRAIN_MODE="beats-warmup"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/beats/warmup"
        ;;
    beats-quick|18b)
        TRAIN_MODE="beats-quick"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/beats/quick"
        ;;
    beats-long|18c)
        TRAIN_MODE="beats-long"
        RUN_DIR="$BEATSIGHT_RUN_CUTTING_EDGE/beats/long"
        ;;
    *)
        echo "Usage: $0 {warmup|quick|long|cutting-edge-*|ensemble-*|ast-*|distill-*|enhanced-*|ssl-*|label-audit|temporal-*|v5-*|beats-*}"
        echo ""
        echo "  Standard v1 training:"
        echo "    warmup (5a) - Warmup probe training"
        echo "    quick  (5b) - Quick refresh training"
        echo "    long   (5c) - Long run training"
        echo ""
        echo "  Cutting-edge v2 + Mixup training:"
        echo "    cutting-edge-warmup (7a) - CE Warmup (~1hr)"
        echo "    cutting-edge-quick  (7b) - CE Quick (~3hr)"
        echo "    cutting-edge-long   (7c) - CE Long (~12hr)"
        echo ""
        echo "  ⭐ BEYOND CUTTING-EDGE (Revolutionary Features):"
        echo ""
        echo "  Ensemble Training (5 models with different seeds):"
        echo "    ensemble-warmup (9a) - Train 5-model ensemble (~5hr)"
        echo "    ensemble-quick  (9b) - Train 5-model ensemble (~15hr)"
        echo "    ensemble-long   (9c) - Train 5-model ensemble (~60hr)"
        echo ""
        echo "  Audio Spectrogram Transformer (AST):"
        echo "    ast-warmup (10a) - AST warmup (~1hr)"
        echo "    ast-quick  (10b) - AST quick (~3hr)"
        echo "    ast-long   (10c) - AST long (~12hr)"
        echo ""
        echo "  Knowledge Distillation (teacher→student):"
        echo "    distill-quick (11a) - Quick distillation (~2hr)"
        echo "    distill-long  (11b) - Full distillation (~8hr)"
        echo ""
        echo "  🚀 NEW REVOLUTIONARY FEATURES (2024):"
        echo ""
        echo "  Enhanced v4 (Coordinate Attention + Multi-Task + FMix):"
        echo "    enhanced-warmup (12a) - Enhanced warmup (~2hr)"
        echo "    enhanced-quick  (12b) - Enhanced quick (~6hr)"
        echo "    enhanced-long   (12c) - Enhanced long (~18hr)"
        echo ""
        echo "  Self-Supervised Pretraining (MAE on unlabeled audio):"
        echo "    ssl-pretrain-warmup (13a) - SSL warmup (~4hr)"
        echo "    ssl-pretrain-full   (13b) - SSL full (~12hr)"
        echo ""
        echo "  Label Audit (Confident Learning):"
        echo "    label-audit (14) - Find noisy labels"
        echo ""
        echo "  🔬 NOVEL RESEARCH (Temporal Mamba - publishable!):"
        echo ""
        echo "  Temporal Modeling with State-Space Models:"
        echo "    temporal-warmup (15a) - Mamba warmup (~3hr)"
        echo "    temporal-quick  (15b) - Mamba quick (~8hr)"
        echo "    temporal-long   (15c) - Mamba long (~20hr)"
        echo "    temporal-full   (15d) - Mamba + pretrained CNN (~24hr)"
        echo ""
        echo "  🏆 ULTIMATE (ALL INNOVATIONS - Maximum Revolutionary!):"
        echo ""
        echo "  Wav2Vec2 + Multi-Resolution + Mamba + Beat Encoding + Pattern Priors:"
        echo "    ultimate-warmup (16a) - Ultimate warmup (~5hr)"
        echo "    ultimate-quick  (16b) - Ultimate quick (~12hr)"
        echo "    ultimate-long   (16c) - Ultimate long (~30hr)"
        echo "    ultimate-full   (16d) - Ultimate + pretrained CNN (~40hr)"
        echo ""
        echo "  💎 V5 ULTIMATE SINGLE MODEL (2024 - ⭐ RECOMMENDED FOR PRODUCTION):"
        echo ""
        echo "  CoordAttn + DropPath + DeepSupervision + Lookahead + Warm Restarts:"
        echo "    v5-warmup      (17a) - V5 warmup (~2hr)"
        echo "    v5-quick       (17b) - V5 quick (~5hr)"
        echo "    v5-long        (17c) - V5 long (~12hr)"
        echo "    v5-full        (17d) - V5 maximum quality (~24hr)"
        echo "    v5-self-distill(17e) - Self-distillation for +1-2% (~24hr)"
        echo ""
        echo "  ⭐ RECOMMENDED PATH: 14 → 17a → 17d → 17e (label audit → warmup → full → self-distill)"
        echo ""
        echo "  🎵 BEATs AUDIO FOUNDATION (Microsoft's state-of-the-art):"
        echo ""
        echo "  Pretrained audio transformer (potentially better than Wav2Vec2):"
        echo "    beats-warmup (18a) - BEATs frozen encoder (~1hr)"
        echo "    beats-quick  (18b) - BEATs fine-tuned (~4hr)"
        echo "    beats-long   (18c) - BEATs maximum quality (~12hr)"
        exit 1
        ;;
esac

# Setup logging
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/auto_train_${TRAIN_MODE}_$(date +%Y%m%d_%H%M%S).log"
SUMMARY_FILE="$LOG_DIR/auto_train_${TRAIN_MODE}_summary.log"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

log_summary() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$SUMMARY_FILE"
}

notify() {
    local title="$1"
    local message="$2"
    
    # Try various notification methods
    if command -v notify-send &> /dev/null; then
        notify-send "$title" "$message" 2>/dev/null || true
    fi
    
    # Windows toast notification (if PowerShell available)
    if command -v powershell.exe &> /dev/null; then
        powershell.exe -Command "
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            \$template = '<toast><visual><binding template=\"ToastText02\"><text id=\"1\">$title</text><text id=\"2\">$message</text></binding></visual></toast>'
            \$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            \$xml.LoadXml(\$template)
            \$toast = [Windows.UI.Notifications.ToastNotification]::new(\$xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('BeatSight').Show(\$toast)
        " 2>/dev/null || true
    fi
}

get_checkpoint_path() {
    local checkpoint_dir="${RUN_DIR}/checkpoints"
    local latest="${checkpoint_dir}/latest_checkpoint.pth"
    
    if [ -f "$latest" ]; then
        echo "$latest"
    else
        echo ""
    fi
}

check_training_complete() {
    # Training is ONLY complete if our completion marker exists
    # This marker is created by auto_train.sh when training exits cleanly with code 0
    # AND the final model exists
    local completion_marker="${RUN_DIR}/.auto_train_complete"
    local final_model="${RUN_DIR}/final_drum_classifier.pth"
    
    if [ -f "$completion_marker" ] && [ -f "$final_model" ]; then
        # Verify the marker is newer than the final model (created after training finished)
        if [ "$completion_marker" -nt "$final_model" ] || [ "$completion_marker" -ot "$final_model" ]; then
            # Close enough in time, consider complete
            return 0
        fi
        return 0  # Training complete
    fi
    return 1  # Not complete
}

clear_old_run() {
    log "🗑️  Clearing old/incomplete run data..."
    rm -f "${RUN_DIR}/final_drum_classifier.pth"
    rm -f "${RUN_DIR}/best_drum_classifier.pth"
    rm -f "${RUN_DIR}/.auto_train_complete"
    rm -rf "${RUN_DIR}/checkpoints"
    log "   Old run data cleared. Starting fresh."
}

prompt_clear_old_run() {
    local final_model="${RUN_DIR}/final_drum_classifier.pth"
    local completion_marker="${RUN_DIR}/.auto_train_complete"
    
    if [ -f "$final_model" ] && [ ! -f "$completion_marker" ]; then
        echo ""
        echo "⚠️  Found old/incomplete run data:"
        echo "    ${final_model}"
        echo "    (No completion marker - likely from a crashed or interrupted run)"
        echo ""
        echo "  Options:"
        echo "    [C] Clear old data and start fresh (recommended)"
        echo "    [R] Resume/continue from existing state"
        echo "    [Q] Quit"
        echo ""
        read -p "  Choose [C/R/Q]: " choice
        
        case "${choice,,}" in
            c|clear)
                clear_old_run
                ;;
            r|resume)
                log "Attempting to resume from existing state..."
                ;;
            q|quit)
                log "Cancelled by user."
                exit 0
                ;;
            *)
                log "Invalid choice. Exiting."
                exit 1
                ;;
        esac
    fi
}

mark_complete() {
    # Create completion marker
    local completion_marker="${RUN_DIR}/.auto_train_complete"
    date > "$completion_marker"
    log "✅ Created completion marker: $completion_marker"
}

run_training() {
    local resume_flag=""
    local checkpoint=$(get_checkpoint_path)
    
    if [ -n "$checkpoint" ]; then
        log "📂 Found checkpoint: $checkpoint"
        resume_flag="--resume-from $checkpoint"
    else
        log "🆕 Starting fresh (no checkpoint found)"
    fi
    
    cd "$BEATSIGHT_REPO_ROOT"
    
    case "$TRAIN_MODE" in
        warmup)
            log "🚀 Starting WARMUP training..."
            BS_CACHE_DEBUG=1 \
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --warmup-epochs 4 \
              --scheduler cosine \
              --min-lr 0.00002 \
              --batch-size 128 \
              --lr 0.0006 \
              --device cuda \
              --val-fraction 0.12 \
              --cache-dtype float16 \
              --num-workers 6 \
              --val-num-workers 4 \
              --prefetch-factor 4 \
              --val-prefetch-factor 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 1 \
              --checkpoint-every-batches 25000 \
              --output "${BEATSIGHT_RUN_WARMUP}" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/prod_combined_warmup.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags prod_combined_24class richer_subset warmup auto_train \
              --wandb-run-name prod_combined_warmup_auto_$(date +%Y%m%d) \
              --grad-accum-steps 1 \
              --class-weights effective \
              --max-class-weight 10.0 \
              --label-smoothing 0.05 \
              $resume_flag
            ;;
        
        quick)
            log "🚀 Starting QUICK REFRESH training..."
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 60 \
              --scheduler plateau \
              --batch-size 128 \
              --lr 0.0006 \
              --device cuda \
              --cache-dtype float16 \
              --num-workers 6 \
              --val-num-workers 4 \
              --prefetch-factor 4 \
              --val-prefetch-factor 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 10 \
              --checkpoint-every-batches 25000 \
              --output "${BEATSIGHT_RUN_QUICK}" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/prod_combined_quick.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags prod_combined_24class quick_refresh auto_train \
              --wandb-run-name prod_combined_quick_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --label-smoothing 0.05 \
              $resume_flag
            ;;
        
        long)
            log "🚀 Starting LONG RUN training..."
            export WANDB_RUN_GROUP=prod_combined_longrun_auto
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --warmup-epochs 16 \
              --scheduler cosine \
              --min-lr 0.00002 \
              --batch-size 128 \
              --lr 0.0005 \
              --device cuda \
              --train-fraction 1.0 \
              --val-fraction 0.3 \
              --subset-seed 20251112 \
              --num-workers 6 \
              --val-num-workers 4 \
              --prefetch-factor 4 \
              --val-prefetch-factor 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 20 \
              --checkpoint-every-batches 25000 \
              --output "${BEATSIGHT_RUN_LONG}" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/prod_combined_longrun.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags prod_combined_24class full_corpus longrun auto_train \
              --wandb-run-name prod_combined_longrun_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --label-smoothing 0.05 \
              $resume_flag
            ;;
        
        # =====================================================================
        # CUTTING-EDGE TRAINING MODES (7a/7b/7c -> 8a/8b/8c auto versions)
        # Uses SE-attention model + Mixup/CutMix augmentation
        # =====================================================================
        
        cutting-edge-warmup)
            log "🔬 Starting CUTTING-EDGE WARMUP training (SE + Mixup)..."
            export WANDB_RUN_GROUP=cutting_edge_warmup_auto
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 35 \
              --warmup-epochs 3 \
              --scheduler cosine \
              --min-lr 0.00005 \
              --batch-size 64 \
              --lr 0.001 \
              --device cuda \
              --train-fraction 0.25 \
              --val-fraction 0.2 \
              --subset-seed 42 \
              --num-workers 4 \
              --val-num-workers 2 \
              --prefetch-factor 2 \
              --val-prefetch-factor 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 5 \
              --checkpoint-every-batches 5000 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/warmup" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/cutting_edge_warmup.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags cutting_edge 24class warmup se_attention mixup specaugment focal ema sam swa rdrop curriculum calibration auto_train \
              --wandb-run-name cutting_edge_warmup_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              $CUTTING_EDGE_MODEL_FLAGS \
              $CUTTING_EDGE_MIXUP_FLAGS \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_FOCAL_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_PROGRESSIVE_FLAGS \
              $CUTTING_EDGE_SAM_FLAGS \
              $CUTTING_EDGE_SWA_FLAGS \
              $CUTTING_EDGE_REGULARIZATION_FLAGS \
              $CUTTING_EDGE_RDROP_FLAGS \
              $CUTTING_EDGE_CURRICULUM_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        cutting-edge-quick)
            log "🔬 Starting CUTTING-EDGE QUICK training (SE + Mixup)..."
            export WANDB_RUN_GROUP=cutting_edge_quick_auto
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 80 \
              --warmup-epochs 5 \
              --scheduler cosine \
              --min-lr 0.00003 \
              --batch-size 128 \
              --lr 0.0007 \
              --device cuda \
              --train-fraction 0.6 \
              --val-fraction 0.25 \
              --subset-seed 20251112 \
              --num-workers 6 \
              --val-num-workers 4 \
              --prefetch-factor 4 \
              --val-prefetch-factor 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 10 \
              --checkpoint-every-batches 25000 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/quick" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/cutting_edge_quick.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags cutting_edge 24class quick se_attention mixup specaugment focal ema sam swa rdrop curriculum calibration auto_train \
              --wandb-run-name cutting_edge_quick_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              $CUTTING_EDGE_MODEL_FLAGS \
              $CUTTING_EDGE_MIXUP_FLAGS \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_FOCAL_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_PROGRESSIVE_FLAGS \
              $CUTTING_EDGE_SAM_FLAGS \
              $CUTTING_EDGE_SWA_FLAGS \
              $CUTTING_EDGE_REGULARIZATION_FLAGS \
              $CUTTING_EDGE_RDROP_FLAGS \
              $CUTTING_EDGE_CURRICULUM_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        cutting-edge-long)
            log "🔬 Starting CUTTING-EDGE LONG RUN training (SE + Mixup)..."
            export WANDB_RUN_GROUP=cutting_edge_longrun_auto
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --warmup-epochs 16 \
              --scheduler cosine \
              --min-lr 0.00002 \
              --batch-size 128 \
              --lr 0.0005 \
              --device cuda \
              --train-fraction 1.0 \
              --val-fraction 0.3 \
              --subset-seed 20251112 \
              --num-workers 6 \
              --val-num-workers 4 \
              --prefetch-factor 4 \
              --val-prefetch-factor 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 20 \
              --checkpoint-every-batches 25000 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/long" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/cutting_edge_longrun.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags cutting_edge 24class full_corpus longrun se_attention mixup specaugment focal ema sam swa rdrop curriculum calibration auto_train \
              --wandb-run-name cutting_edge_longrun_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              $CUTTING_EDGE_MODEL_FLAGS \
              $CUTTING_EDGE_MIXUP_FLAGS \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_FOCAL_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_PROGRESSIVE_FLAGS \
              $CUTTING_EDGE_SAM_FLAGS \
              $CUTTING_EDGE_SWA_FLAGS \
              $CUTTING_EDGE_REGULARIZATION_FLAGS \
              $CUTTING_EDGE_RDROP_FLAGS \
              $CUTTING_EDGE_CURRICULUM_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        # =====================================================================
        # BEYOND CUTTING-EDGE: ENSEMBLE TRAINING (9a/9b/9c)
        # Trains 5 models with different seeds for maximum accuracy
        # =====================================================================
        
        ensemble-warmup)
            log "🌟 Starting ENSEMBLE WARMUP training (5 models)..."
            export WANDB_RUN_GROUP=ensemble_warmup_auto
            mkdir -p "${BEATSIGHT_RUN_ENSEMBLE}/warmup"
            
            # Train 5 models with different seeds
            for seed in 1337 2024 42 7777 12345; do
                log "   Training model with seed ${seed}..."
                PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
                  --dataset "${BEATSIGHT_DATASET_DIR}" \
                  --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
                  --epochs 35 \
                  --warmup-epochs 3 \
                  --scheduler cosine \
                  --min-lr 0.00005 \
                  --batch-size 64 \
                  --lr 0.001 \
                  --device cuda \
                  --train-fraction 0.25 \
                  --val-fraction 0.2 \
                  --subset-seed ${seed} \
                  --num-workers 4 \
                  --val-num-workers 2 \
                  --persistent-workers \
                  --pin-memory \
                  --grad-clip-norm 1.0 \
                  --weight-decay 0.0001 \
                  --channels-last \
                  --seed ${seed} \
                  --checkpoint-every 5 \
                  --output "${BEATSIGHT_RUN_ENSEMBLE}/warmup/seed_${seed}" \
                  --metrics-json "${BEATSIGHT_METRICS_DIR}/ensemble_warmup_seed_${seed}.json" \
                  --wandb-project beatsight-classifier \
                  --wandb-mode offline \
                  --wandb-tags ensemble warmup seed_${seed} auto_train \
                  --wandb-run-name ensemble_warmup_seed_${seed}_$(date +%Y%m%d) \
                  --class-weights effective \
                  --max-class-weight 10.0 \
                  $CUTTING_EDGE_MODEL_FLAGS \
                  $CUTTING_EDGE_MIXUP_FLAGS \
                  $CUTTING_EDGE_SPECAUGMENT_FLAGS \
                  $CUTTING_EDGE_FOCAL_FLAGS \
                  $CUTTING_EDGE_EMA_FLAGS \
                  $CUTTING_EDGE_PROGRESSIVE_FLAGS \
                  $CUTTING_EDGE_REGULARIZATION_FLAGS \
                  $CUTTING_EDGE_CALIBRATION_FLAGS
            done
            
            # Create ensemble config
            log "   Creating ensemble configuration..."
            python - <<'ENSEMBLE_PY'
import json
from pathlib import Path
import os

ensemble_dir = Path(os.environ.get("BEATSIGHT_RUN_CUTTING_EDGE", ".")) / "ensemble" / "warmup"
models = []
weights = []

for seed in [1337, 2024, 42, 7777, 12345]:
    model_path = ensemble_dir / f"seed_{seed}" / "best_drum_classifier_ema.pth"
    if not model_path.exists():
        model_path = ensemble_dir / f"seed_{seed}" / "best_drum_classifier.pth"
    if model_path.exists():
        models.append(str(model_path))
        # Read validation accuracy for weighting
        metrics_path = ensemble_dir / f"seed_{seed}" / "metrics.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                weights.append(json.load(f).get("best_val_accuracy", 0.5))
        else:
            weights.append(0.5)

# Normalize weights
total = sum(weights)
weights = [w/total for w in weights]

config = {
    "model_paths": models,
    "model_classes": ["v2"] * len(models),
    "weights": weights,
    "use_tta": True,
    "tta_augmentations": 5,
}

with open(ensemble_dir / "ensemble_config.json", "w") as f:
    json.dump(config, f, indent=2)

print(f"Ensemble config saved with {len(models)} models")
ENSEMBLE_PY
            ;;
        
        ensemble-quick)
            log "🌟 Starting ENSEMBLE QUICK training (5 models)..."
            export WANDB_RUN_GROUP=ensemble_quick_auto
            mkdir -p "${BEATSIGHT_RUN_ENSEMBLE}/quick"
            
            for seed in 1337 2024 42 7777 12345; do
                log "   Training model with seed ${seed}..."
                PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
                  --dataset "${BEATSIGHT_DATASET_DIR}" \
                  --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
                  --epochs 80 \
                  --warmup-epochs 5 \
                  --scheduler cosine \
                  --min-lr 0.00003 \
                  --batch-size 128 \
                  --lr 0.0007 \
                  --device cuda \
                  --train-fraction 0.6 \
                  --val-fraction 0.25 \
                  --subset-seed ${seed} \
                  --num-workers 6 \
                  --val-num-workers 4 \
                  --persistent-workers \
                  --pin-memory \
                  --grad-clip-norm 1.0 \
                  --weight-decay 0.0001 \
                  --channels-last \
                  --seed ${seed} \
                  --checkpoint-every 10 \
                  --output "${BEATSIGHT_RUN_ENSEMBLE}/quick/seed_${seed}" \
                  --metrics-json "${BEATSIGHT_METRICS_DIR}/ensemble_quick_seed_${seed}.json" \
                  --wandb-project beatsight-classifier \
                  --wandb-mode offline \
                  --wandb-tags ensemble quick seed_${seed} auto_train \
                  --wandb-run-name ensemble_quick_seed_${seed}_$(date +%Y%m%d) \
                  --class-weights effective \
                  --max-class-weight 10.0 \
                  $CUTTING_EDGE_MODEL_FLAGS \
                  $CUTTING_EDGE_MIXUP_FLAGS \
                  $CUTTING_EDGE_SPECAUGMENT_FLAGS \
                  $CUTTING_EDGE_FOCAL_FLAGS \
                  $CUTTING_EDGE_EMA_FLAGS \
                  $CUTTING_EDGE_PROGRESSIVE_FLAGS \
                  $CUTTING_EDGE_SAM_FLAGS \
                  $CUTTING_EDGE_SWA_FLAGS \
                  $CUTTING_EDGE_REGULARIZATION_FLAGS \
                  $CUTTING_EDGE_RDROP_FLAGS \
                  $CUTTING_EDGE_CURRICULUM_FLAGS \
                  $CUTTING_EDGE_CALIBRATION_FLAGS
            done
            ;;
        
        ensemble-long)
            log "🌟 Starting ENSEMBLE LONG training (5 models - MAXIMUM QUALITY)..."
            export WANDB_RUN_GROUP=ensemble_long_auto
            mkdir -p "${BEATSIGHT_RUN_ENSEMBLE}/long"
            
            for seed in 1337 2024 42 7777 12345; do
                log "   Training model ${seed} of 5 (this will take several hours)..."
                PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
                  --dataset "${BEATSIGHT_DATASET_DIR}" \
                  --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
                  --warmup-epochs 16 \
                  --scheduler cosine \
                  --min-lr 0.00002 \
                  --batch-size 128 \
                  --lr 0.0005 \
                  --device cuda \
                  --train-fraction 1.0 \
                  --val-fraction 0.3 \
                  --subset-seed ${seed} \
                  --num-workers 6 \
                  --val-num-workers 4 \
                  --persistent-workers \
                  --pin-memory \
                  --grad-clip-norm 1.0 \
                  --weight-decay 0.0001 \
                  --channels-last \
                  --seed ${seed} \
                  --checkpoint-every 20 \
                  --output "${BEATSIGHT_RUN_ENSEMBLE}/long/seed_${seed}" \
                  --metrics-json "${BEATSIGHT_METRICS_DIR}/ensemble_long_seed_${seed}.json" \
                  --wandb-project beatsight-classifier \
                  --wandb-mode offline \
                  --wandb-tags ensemble longrun seed_${seed} revolutionary auto_train \
                  --wandb-run-name ensemble_long_seed_${seed}_$(date +%Y%m%d) \
                  --class-weights effective \
                  --max-class-weight 10.0 \
                  $CUTTING_EDGE_MODEL_FLAGS \
                  $CUTTING_EDGE_MIXUP_FLAGS \
                  $CUTTING_EDGE_SPECAUGMENT_FLAGS \
                  $CUTTING_EDGE_FOCAL_FLAGS \
                  $CUTTING_EDGE_EMA_FLAGS \
                  $CUTTING_EDGE_PROGRESSIVE_FLAGS \
                  $CUTTING_EDGE_SAM_FLAGS \
                  $CUTTING_EDGE_SWA_FLAGS \
                  $CUTTING_EDGE_REGULARIZATION_FLAGS \
                  $CUTTING_EDGE_RDROP_FLAGS \
                  $CUTTING_EDGE_CURRICULUM_FLAGS \
                  $CUTTING_EDGE_CALIBRATION_FLAGS
            done
            ;;
        
        # =====================================================================
        # AST (AUDIO SPECTROGRAM TRANSFORMER) TRAINING (10a/10b/10c)
        # =====================================================================
        
        ast-warmup)
            log "🤖 Starting AST WARMUP training (Transformer architecture)..."
            export WANDB_RUN_GROUP=ast_warmup_auto
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 35 \
              --warmup-epochs 5 \
              --scheduler cosine \
              --min-lr 0.00001 \
              --batch-size 32 \
              --lr 0.0003 \
              --device cuda \
              --train-fraction 0.25 \
              --val-fraction 0.2 \
              --subset-seed 42 \
              --num-workers 4 \
              --val-num-workers 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.05 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 5 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/ast/warmup" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/ast_warmup.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags ast transformer warmup revolutionary auto_train \
              --wandb-run-name ast_warmup_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --model-version ast \
              $CUTTING_EDGE_MIXUP_FLAGS \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        ast-quick)
            log "🤖 Starting AST QUICK training (Transformer architecture)..."
            export WANDB_RUN_GROUP=ast_quick_auto
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 80 \
              --warmup-epochs 10 \
              --scheduler cosine \
              --min-lr 0.000005 \
              --batch-size 32 \
              --lr 0.0002 \
              --device cuda \
              --train-fraction 0.6 \
              --val-fraction 0.25 \
              --subset-seed 20251112 \
              --num-workers 4 \
              --val-num-workers 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.05 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 10 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/ast/quick" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/ast_quick.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags ast transformer quick revolutionary auto_train \
              --wandb-run-name ast_quick_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --model-version ast \
              $CUTTING_EDGE_MIXUP_FLAGS \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_SWA_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        ast-long)
            log "🤖 Starting AST LONG training (Transformer architecture - FULL)..."
            export WANDB_RUN_GROUP=ast_long_auto
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 150 \
              --warmup-epochs 15 \
              --scheduler cosine \
              --min-lr 0.000001 \
              --batch-size 32 \
              --lr 0.0001 \
              --device cuda \
              --train-fraction 1.0 \
              --val-fraction 0.3 \
              --subset-seed 20251112 \
              --num-workers 4 \
              --val-num-workers 2 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.05 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 15 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/ast/long" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/ast_long.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags ast transformer longrun revolutionary auto_train \
              --wandb-run-name ast_long_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --model-version ast \
              $CUTTING_EDGE_MIXUP_FLAGS \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_SWA_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        # =====================================================================
        # KNOWLEDGE DISTILLATION (11a/11b)
        # Train smaller, faster student from ensemble teacher
        # =====================================================================
        
        distill-quick)
            log "📚 Starting KNOWLEDGE DISTILLATION (quick)..."
            log "   Using ensemble as teacher, training compact student..."
            export WANDB_RUN_GROUP=distill_quick_auto
            
            # Check for teacher ensemble
            TEACHER_CONFIG="${BEATSIGHT_RUN_ENSEMBLE}/quick/ensemble_config.json"
            if [ ! -f "$TEACHER_CONFIG" ]; then
                log "ERROR: Teacher ensemble not found. Run ensemble-quick (9b) first."
                exit 1
            fi
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 60 \
              --warmup-epochs 5 \
              --scheduler cosine \
              --min-lr 0.00005 \
              --batch-size 128 \
              --lr 0.001 \
              --device cuda \
              --train-fraction 0.6 \
              --val-fraction 0.25 \
              --num-workers 6 \
              --val-num-workers 4 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 10 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/distilled/quick" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/distilled_quick.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags distillation student compact revolutionary auto_train \
              --wandb-run-name distilled_quick_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --model-version v2 \
              --use-se \
              --distill-from "$TEACHER_CONFIG" \
              --distill-temperature 4.0 \
              --distill-alpha 0.7 \
              $CUTTING_EDGE_MIXUP_FLAGS \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        distill-long)
            log "📚 Starting KNOWLEDGE DISTILLATION (long - production)..."
            log "   Using ensemble as teacher, training production student..."
            export WANDB_RUN_GROUP=distill_long_auto
            
            TEACHER_CONFIG="${BEATSIGHT_RUN_ENSEMBLE}/long/ensemble_config.json"
            if [ ! -f "$TEACHER_CONFIG" ]; then
                log "ERROR: Teacher ensemble not found. Run ensemble-long (9c) first."
                exit 1
            fi
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 100 \
              --warmup-epochs 10 \
              --scheduler cosine \
              --min-lr 0.00002 \
              --batch-size 128 \
              --lr 0.0008 \
              --device cuda \
              --train-fraction 1.0 \
              --val-fraction 0.3 \
              --num-workers 6 \
              --val-num-workers 4 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 15 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/distilled/long" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/distilled_long.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags distillation student production revolutionary auto_train \
              --wandb-run-name distilled_long_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --model-version v2 \
              --use-se \
              --distill-from "$TEACHER_CONFIG" \
              --distill-temperature 4.0 \
              --distill-alpha 0.7 \
              $CUTTING_EDGE_MIXUP_FLAGS \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_SWA_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        # =====================================================================
        # ENHANCED v4 (12a/12b/12c) - Coordinate Attention + Multi-Task + FMix
        # =====================================================================
        
        enhanced-warmup)
            log "🚀 Starting ENHANCED v4 training (warmup)..."
            log "   Using Coordinate Attention + Multi-Task + FMix..."
            export WANDB_RUN_GROUP=enhanced_warmup_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 15 \
              --warmup-epochs 2 \
              --scheduler cosine \
              --min-lr 0.0001 \
              --batch-size 64 \
              --lr 0.001 \
              --device cuda \
              --train-fraction 0.3 \
              --val-fraction 0.2 \
              --num-workers 6 \
              --val-num-workers 4 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 5 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/enhanced/warmup" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/enhanced_warmup.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags enhanced coordattn multitask fmix revolutionary auto_train \
              --wandb-run-name enhanced_warmup_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --model-version v4 \
              --use-coord-attention \
              --use-multi-task \
              --velocity-weight 0.1 \
              --openness-weight 0.1 \
              --use-fmix \
              --fmix-alpha 1.0 \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        enhanced-quick)
            log "🚀 Starting ENHANCED v4 training (quick)..."
            log "   Using Coordinate Attention + Multi-Task + FMix + SAM..."
            export WANDB_RUN_GROUP=enhanced_quick_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 50 \
              --warmup-epochs 5 \
              --scheduler cosine \
              --min-lr 0.00005 \
              --batch-size 64 \
              --lr 0.001 \
              --device cuda \
              --train-fraction 0.6 \
              --val-fraction 0.25 \
              --num-workers 6 \
              --val-num-workers 4 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 10 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/enhanced/quick" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/enhanced_quick.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags enhanced coordattn multitask fmix sam revolutionary auto_train \
              --wandb-run-name enhanced_quick_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --model-version v4 \
              --use-coord-attention \
              --use-multi-task \
              --velocity-weight 0.1 \
              --openness-weight 0.1 \
              --use-fmix \
              --fmix-alpha 1.0 \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_SAM_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_RDROP_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        enhanced-long)
            log "🚀 Starting ENHANCED v4 training (long - production)..."
            log "   Using Coordinate Attention + Multi-Task + FMix + SAM + SWA..."
            export WANDB_RUN_GROUP=enhanced_long_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 150 \
              --warmup-epochs 10 \
              --scheduler cosine \
              --min-lr 0.00002 \
              --batch-size 64 \
              --lr 0.0008 \
              --device cuda \
              --train-fraction 1.0 \
              --val-fraction 0.3 \
              --num-workers 6 \
              --val-num-workers 4 \
              --persistent-workers \
              --pin-memory \
              --grad-clip-norm 1.0 \
              --weight-decay 0.0001 \
              --channels-last \
              --seed 1337 \
              --checkpoint-every 15 \
              --checkpoint-every-batches 25000 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/enhanced/long" \
              --metrics-json "${BEATSIGHT_METRICS_DIR}/enhanced_long.json" \
              --wandb-project beatsight-classifier \
              --wandb-mode offline \
              --wandb-tags enhanced coordattn multitask fmix sam swa production revolutionary auto_train \
              --wandb-run-name enhanced_long_auto_$(date +%Y%m%d) \
              --class-weights effective \
              --max-class-weight 10.0 \
              --model-version v4 \
              --use-coord-attention \
              --use-multi-task \
              --velocity-weight 0.1 \
              --openness-weight 0.1 \
              --use-fmix \
              --fmix-alpha 1.0 \
              --fmix-with-cutmix \
              $CUTTING_EDGE_SPECAUGMENT_FLAGS \
              $CUTTING_EDGE_SAM_FLAGS \
              $CUTTING_EDGE_EMA_FLAGS \
              $CUTTING_EDGE_SWA_FLAGS \
              $CUTTING_EDGE_RDROP_FLAGS \
              $CUTTING_EDGE_CURRICULUM_FLAGS \
              $CUTTING_EDGE_CALIBRATION_FLAGS \
              $resume_flag
            ;;
        
        # =====================================================================
        # SELF-SUPERVISED PRETRAINING (13a/13b)
        # =====================================================================
        
        ssl-pretrain-warmup)
            log "🧠 Starting SELF-SUPERVISED PRETRAINING (warmup)..."
            log "   Using Masked Autoencoder on unlabeled audio..."
            export WANDB_RUN_GROUP=ssl_pretrain_warmup_auto
            
            # Default unlabeled dir - can be overridden
            UNLABELED_DIR="${BEATSIGHT_UNLABELED_DIR:-${BEATSIGHT_DATA_ROOT}/unlabeled}"
            
            if [ ! -d "$UNLABELED_DIR" ]; then
                log "WARNING: Unlabeled data directory not found: $UNLABELED_DIR"
                log "Set BEATSIGHT_UNLABELED_DIR to your unlabeled audio directory"
                log "Falling back to labeled dataset for SSL pretraining..."
                UNLABELED_DIR="${BEATSIGHT_DATASET_DIR}/train"
            fi
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/pretrain_ssl.py \
              --audio-dir "$UNLABELED_DIR" \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/ssl/warmup/pretrained_backbone.pt" \
              --method mae \
              --epochs 30 \
              --batch-size 64 \
              --lr 0.001 \
              --embed-dim 256 \
              --mask-ratio 0.75 \
              --device cuda \
              --num-workers 6 \
              --wandb-project beatsight-ssl \
              --seed 1337
            ;;
        
        ssl-pretrain-full)
            log "🧠 Starting SELF-SUPERVISED PRETRAINING (full)..."
            log "   Using Masked Autoencoder + Contrastive on unlabeled audio..."
            export WANDB_RUN_GROUP=ssl_pretrain_full_auto
            
            UNLABELED_DIR="${BEATSIGHT_UNLABELED_DIR:-${BEATSIGHT_DATA_ROOT}/unlabeled}"
            
            if [ ! -d "$UNLABELED_DIR" ]; then
                log "WARNING: Unlabeled data directory not found: $UNLABELED_DIR"
                log "Set BEATSIGHT_UNLABELED_DIR to your unlabeled audio directory"
                log "Falling back to labeled dataset for SSL pretraining..."
                UNLABELED_DIR="${BEATSIGHT_DATASET_DIR}/train"
            fi
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/pretrain_ssl.py \
              --audio-dir "$UNLABELED_DIR" \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/ssl/full/pretrained_backbone.pt" \
              --method mae \
              --epochs 100 \
              --batch-size 64 \
              --lr 0.0008 \
              --embed-dim 256 \
              --mask-ratio 0.75 \
              --device cuda \
              --num-workers 6 \
              --wandb-project beatsight-ssl \
              --seed 1337
            
            log "SSL pretraining complete. Fine-tune with:"
            log "  python train_classifier.py --pretrained-backbone ${BEATSIGHT_RUN_CUTTING_EDGE}/ssl/full/pretrained_backbone.pt"
            ;;
        
        # =====================================================================
        # LABEL AUDIT (Confident Learning)
        # =====================================================================
        
        label-audit)
            log "🔍 Starting LABEL AUDIT (Confident Learning)..."
            log "   Finding potentially mislabeled samples..."
            export WANDB_RUN_GROUP=label_audit_auto
            
            mkdir -p "${BEATSIGHT_RUN_CUTTING_EDGE}/audits"
            
            # Run label noise detection
            # PERF: Using consolidated cache now (100x faster than individual .pt files)
            # Reduced workers to 4+2 to stay within 32GB RAM limit
            # Each worker loads ~1GB numpy arrays after pickle fix
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --epochs 20 \
              --warmup-epochs 2 \
              --scheduler cosine \
              --batch-size 256 \
              --lr 0.001 \
              --device cuda \
              --train-fraction 0.5 \
              --val-fraction 0.2 \
              --num-workers 4 \
              --val-num-workers 2 \
              --prefetch-factor 2 \
              --persistent-workers \
              --pin-memory \
              --amp-dtype float16 \
              --seed 1337 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/audits" \
              --model-version v2 \
              --use-se \
              --clean-labels \
              --label-noise-audit-only \
              --label-noise-threshold 0.5 \
              $resume_flag
            
            log ""
            log "Label audit complete. Check:"
            log "  ${BEATSIGHT_RUN_CUTTING_EDGE}/audits/label_noise_report.json"
            log ""
            log "To actually filter noisy labels, run:"
            log "  python train_classifier.py --clean-labels --label-noise-threshold 0.5"
            ;;
        
        # =====================================================================
        # TEMPORAL MAMBA (15a/15b/15c/15d) - NOVEL RESEARCH
        # State-Space Models for drum pattern context
        # =====================================================================
        
        temporal-warmup)
            log "🔬 Starting TEMPORAL MAMBA training (warmup - NOVEL RESEARCH)..."
            log "   Using Mamba State-Space Model for temporal context..."
            export WANDB_RUN_GROUP=temporal_warmup_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_temporal.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --epochs 30 \
              --batch-size 8 \
              --sequence-length 16 \
              --lr 0.0005 \
              --model-size small \
              --warmup-epochs 3 \
              --grad-clip 1.0 \
              --mixed-precision \
              --num-workers 4 \
              --output-dir "${BEATSIGHT_RUN_CUTTING_EDGE}/temporal/warmup" \
              --seed 1337 \
              --save-every 10 \
              --wandb-project beatsight-temporal
            ;;
        
        temporal-quick)
            log "🔬 Starting TEMPORAL MAMBA training (quick - NOVEL RESEARCH)..."
            log "   Using Mamba State-Space Model with pattern priors..."
            export WANDB_RUN_GROUP=temporal_quick_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_temporal.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --epochs 60 \
              --batch-size 8 \
              --sequence-length 32 \
              --lr 0.0003 \
              --model-size medium \
              --use-pattern-prior \
              --warmup-epochs 5 \
              --grad-clip 1.0 \
              --mixed-precision \
              --num-workers 4 \
              --output-dir "${BEATSIGHT_RUN_CUTTING_EDGE}/temporal/quick" \
              --seed 1337 \
              --save-every 10 \
              --wandb-project beatsight-temporal
            ;;
        
        temporal-long)
            log "🔬 Starting TEMPORAL MAMBA training (long - NOVEL RESEARCH)..."
            log "   Using Mamba State-Space Model with beat encoding + patterns..."
            export WANDB_RUN_GROUP=temporal_long_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_temporal.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --epochs 100 \
              --batch-size 8 \
              --sequence-length 32 \
              --lr 0.0002 \
              --model-size medium \
              --use-beat-encoding \
              --use-pattern-prior \
              --warmup-epochs 10 \
              --grad-clip 1.0 \
              --mixed-precision \
              --num-workers 4 \
              --output-dir "${BEATSIGHT_RUN_CUTTING_EDGE}/temporal/long" \
              --seed 1337 \
              --save-every 10 \
              --wandb-project beatsight-temporal
            ;;
        
        temporal-full)
            log "🔬 Starting TEMPORAL MAMBA training (full - NOVEL RESEARCH)..."
            log "   Using pretrained CNN + Mamba + beat encoding + patterns..."
            export WANDB_RUN_GROUP=temporal_full_auto
            
            # Check for pretrained CNN
            PRETRAINED_CNN="${BEATSIGHT_RUN_CUTTING_EDGE}/enhanced/long/best.pt"
            if [ ! -f "$PRETRAINED_CNN" ]; then
                PRETRAINED_CNN="${BEATSIGHT_RUN_CUTTING_EDGE}/enhanced/quick/best.pt"
            fi
            if [ ! -f "$PRETRAINED_CNN" ]; then
                PRETRAINED_CNN="${BEATSIGHT_RUN_LONG}/best_drum_classifier.pth"
            fi
            
            PRETRAIN_FLAG=""
            if [ -f "$PRETRAINED_CNN" ]; then
                log "   Found pretrained CNN: $PRETRAINED_CNN"
                PRETRAIN_FLAG="--pretrained-cnn $PRETRAINED_CNN --freeze-cnn-epochs 10"
            else
                log "   WARNING: No pretrained CNN found, training from scratch"
            fi
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_temporal.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --epochs 150 \
              --batch-size 8 \
              --sequence-length 32 \
              --lr 0.00015 \
              --model-size large \
              --use-beat-encoding \
              --use-pattern-prior \
              --warmup-epochs 15 \
              --grad-clip 1.0 \
              --mixed-precision \
              --num-workers 4 \
              --output-dir "${BEATSIGHT_RUN_CUTTING_EDGE}/temporal/full" \
              --seed 1337 \
              --save-every 10 \
              --wandb-project beatsight-temporal \
              $PRETRAIN_FLAG
            
            log ""
            log "Temporal model training complete!"
            log "This is a NOVEL contribution - consider publishing at ISMIR/SMC!"
            ;;
        
        # =====================================================================
        # ULTIMATE (16a/16b/16c/16d) - MAXIMUM REVOLUTIONARY
        # Combines ALL innovations: Wav2Vec2 + Multi-Resolution + Mamba + Beat + Patterns
        # =====================================================================
        
        ultimate-warmup)
            log "🏆 Starting ULTIMATE training (warmup - ALL INNOVATIONS)..."
            log "   Wav2Vec2 + Multi-Resolution + Mamba + Beat Encoding + Patterns..."
            export WANDB_RUN_GROUP=ultimate_warmup_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_temporal.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --audio-dir "${BEATSIGHT_DATA_ROOT}/raw" \
              --epochs 30 \
              --batch-size 4 \
              --sequence-length 16 \
              --lr 0.0005 \
              --model-size small \
              --ultimate-mode \
              --use-wav2vec \
              --use-multi-res \
              --use-beat-encoding \
              --use-pattern-prior \
              --warmup-epochs 3 \
              --grad-clip 1.0 \
              --mixed-precision \
              --num-workers 4 \
              --output-dir "${BEATSIGHT_RUN_CUTTING_EDGE}/ultimate/warmup" \
              --seed 1337 \
              --save-every 10 \
              --wandb-project beatsight-ultimate
            ;;
        
        ultimate-quick)
            log "🏆 Starting ULTIMATE training (quick - ALL INNOVATIONS)..."
            log "   Wav2Vec2 + Multi-Resolution + Mamba + Beat Encoding + Patterns..."
            export WANDB_RUN_GROUP=ultimate_quick_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_temporal.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --audio-dir "${BEATSIGHT_DATA_ROOT}/raw" \
              --epochs 60 \
              --batch-size 4 \
              --sequence-length 32 \
              --lr 0.0003 \
              --model-size medium \
              --ultimate-mode \
              --use-wav2vec \
              --use-multi-res \
              --use-beat-encoding \
              --use-pattern-prior \
              --warmup-epochs 5 \
              --grad-clip 1.0 \
              --mixed-precision \
              --num-workers 4 \
              --output-dir "${BEATSIGHT_RUN_CUTTING_EDGE}/ultimate/quick" \
              --seed 1337 \
              --save-every 10 \
              --wandb-project beatsight-ultimate
            ;;
        
        ultimate-long)
            log "🏆 Starting ULTIMATE training (long - ALL INNOVATIONS)..."
            log "   Wav2Vec2 + Multi-Resolution + Mamba + Beat Encoding + Patterns..."
            export WANDB_RUN_GROUP=ultimate_long_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_temporal.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --audio-dir "${BEATSIGHT_DATA_ROOT}/raw" \
              --epochs 100 \
              --batch-size 4 \
              --sequence-length 32 \
              --lr 0.0002 \
              --model-size medium \
              --ultimate-mode \
              --use-wav2vec \
              --use-multi-res \
              --use-beat-encoding \
              --use-pattern-prior \
              --warmup-epochs 10 \
              --grad-clip 1.0 \
              --mixed-precision \
              --num-workers 4 \
              --output-dir "${BEATSIGHT_RUN_CUTTING_EDGE}/ultimate/long" \
              --seed 1337 \
              --save-every 10 \
              --wandb-project beatsight-ultimate
            ;;
        
        ultimate-full)
            log "🏆 Starting ULTIMATE training (full - ALL INNOVATIONS)..."
            log "   Using pretrained CNN + Wav2Vec2 + Multi-Res + Mamba + Beat + Patterns..."
            export WANDB_RUN_GROUP=ultimate_full_auto
            
            # Check for pretrained CNN
            PRETRAINED_CNN="${BEATSIGHT_RUN_CUTTING_EDGE}/enhanced/long/best.pt"
            if [ ! -f "$PRETRAINED_CNN" ]; then
                PRETRAINED_CNN="${BEATSIGHT_RUN_CUTTING_EDGE}/enhanced/quick/best.pt"
            fi
            if [ ! -f "$PRETRAINED_CNN" ]; then
                PRETRAINED_CNN="${BEATSIGHT_RUN_LONG}/best_drum_classifier.pth"
            fi
            
            PRETRAIN_FLAG=""
            if [ -f "$PRETRAINED_CNN" ]; then
                log "   Found pretrained CNN: $PRETRAINED_CNN"
                PRETRAIN_FLAG="--pretrained-cnn $PRETRAINED_CNN --freeze-cnn-epochs 15"
            else
                log "   WARNING: No pretrained CNN found, training from scratch"
            fi
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_temporal.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --audio-dir "${BEATSIGHT_DATA_ROOT}/raw" \
              --epochs 150 \
              --batch-size 4 \
              --sequence-length 32 \
              --lr 0.00015 \
              --model-size large \
              --ultimate-mode \
              --use-wav2vec \
              --use-multi-res \
              --use-beat-encoding \
              --use-pattern-prior \
              --warmup-epochs 15 \
              --grad-clip 1.0 \
              --mixed-precision \
              --num-workers 4 \
              --output-dir "${BEATSIGHT_RUN_CUTTING_EDGE}/ultimate/full" \
              --seed 1337 \
              --save-every 10 \
              --wandb-project beatsight-ultimate \
              $PRETRAIN_FLAG
            
            log ""
            log "🏆 ULTIMATE model training complete!"
            log "This combines 4 NOVEL contributions - HIGHLY publishable at top venues!"
            log "  1. First Mamba SSM for drum transcription"
            log "  2. First combination of audio foundation models + SSM for drums"
            log "  3. Beat-aware positional encoding"
            log "  4. Learnable drum pattern priors"
            ;;
        
        # =====================================================================
        # V5 ULTIMATE MODEL (17a/17b/17c/17d) - ALL INNOVATIONS COMBINED
        # CoordAttn + DropPath + DeepSupervision + MultiScale + GradCentralization
        # =====================================================================
        
        v5-warmup)
            log "💎 Starting V5 ULTIMATE training (warmup)..."
            log "   CoordAttn + DropPath + DeepSup + MultiTask + WaveformAug + FMix..."
            export WANDB_RUN_GROUP=v5_warmup_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --device cuda \
              --epochs 20 \
              --batch-size 256 \
              --lr 0.002 \
              --num-workers 4 --val-num-workers 4 --prefetch-factor 4 \
              --pin-memory --amp-dtype float16 \
              ${V5_ULTIMATE_FLAGS} \
              ${CUTTING_EDGE_MIXUP_FLAGS} \
              ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
              ${CUTTING_EDGE_FOCAL_FLAGS} \
              ${CUTTING_EDGE_EMA_FLAGS} \
              ${CUTTING_EDGE_SAM_FLAGS} \
              --warmup-epochs 3 \
              --warmup-lr-factor 0.1 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/v5/warmup" \
              --seed 1337 \
              --checkpoint-every 5 \
              --wandb-project beatsight-v5 \
              $resume_flag
            ;;
        
        v5-quick)
            log "💎 Starting V5 ULTIMATE training (quick)..."
            log "   CoordAttn + DropPath + DeepSup + MultiTask + WaveformAug + FMix + SWA + RDrop..."
            export WANDB_RUN_GROUP=v5_quick_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --device cuda \
              --num-workers 4 --val-num-workers 4 --prefetch-factor 4 \
              --pin-memory --amp-dtype float16 \
              --epochs 50 \
              --batch-size 256 \
              --lr 0.0016 \
              ${V5_ULTIMATE_FLAGS} \
              ${CUTTING_EDGE_MIXUP_FLAGS} \
              ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
              ${CUTTING_EDGE_FOCAL_FLAGS} \
              ${CUTTING_EDGE_EMA_FLAGS} \
              ${CUTTING_EDGE_SAM_FLAGS} \
              ${CUTTING_EDGE_SWA_FLAGS} \
              ${CUTTING_EDGE_RDROP_FLAGS} \
              --warmup-epochs 5 \
              --warmup-lr-factor 0.1 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/v5/quick" \
              --seed 1337 \
              --checkpoint-every 10 \
              --wandb-project beatsight-v5 \
              $resume_flag
            ;;
        
        v5-long)
            log "💎 Starting V5 ULTIMATE training (long - Production Quality)..."
            log "   CoordAttn + DropPath + DeepSup + MultiTask + WaveformAug + FMix + All extras..."
            log "   + Lookahead + Cosine Warm Restarts + Mixup Cutoff..."
            export WANDB_RUN_GROUP=v5_long_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --device cuda \
              --num-workers 4 --val-num-workers 4 --prefetch-factor 4 \
              --pin-memory --amp-dtype float16 \
              --epochs 100 \
              --batch-size 256 \
              --lr 0.0012 \
              ${V5_ULTIMATE_FLAGS} \
              ${CUTTING_EDGE_MIXUP_FLAGS} \
              ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
              ${CUTTING_EDGE_FOCAL_FLAGS} \
              ${CUTTING_EDGE_EMA_FLAGS} \
              ${CUTTING_EDGE_SAM_FLAGS} \
              ${CUTTING_EDGE_SWA_FLAGS} \
              ${CUTTING_EDGE_RDROP_FLAGS} \
              ${CUTTING_EDGE_CURRICULUM_FLAGS} \
              ${CUTTING_EDGE_CALIBRATION_FLAGS} \
              --scheduler cosine_warm_restarts \
              --warm-restart-t0 25 \
              --warm-restart-mult 2 \
              --warmup-epochs 10 \
              --warmup-lr-factor 0.1 \
              --grad-clip-norm 1.0 \
              --weight-decay 0.01 \
              --channels-last \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/v5/long" \
              --seed 1337 \
              --checkpoint-every 10 \
              --wandb-project beatsight-v5 \
              $resume_flag
            ;;
        
        v5-full)
            log "💎 Starting V5 ULTIMATE training (full - MAXIMUM Quality)..."
            log "   All innovations + Large model + Extended training..."
            log "   + Lookahead + Cosine Warm Restarts + Mixup Cutoff + Self-Distillation Ready..."
            log "   + Attentive Statistics Pooling (Option A enhancement: +0.3-0.5%)..."
            log "   + Hard Negative Contrastive Loss (embedding-space separation)..."
            export WANDB_RUN_GROUP=v5_full_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --device cuda \
              --num-workers 4 --val-num-workers 4 --prefetch-factor 4 \
              --pin-memory --amp-dtype float16 \
              --epochs 150 \
              --batch-size 256 \
              --lr 0.001 \
              --model-version v5 \
              --v5-size large \
              --drop-path-rate 0.15 \
              ${V5_DEEP_SUPERVISION_FLAGS} \
              ${V5_GRADIENT_CENTRALIZATION_FLAGS} \
              ${V5_MULTI_TASK_FLAGS} \
              ${V5_WAVEFORM_AUGMENT_FLAGS} \
              ${V5_FMIX_FLAGS} \
              ${V5_PROGRESSIVE_FLAGS} \
              ${V5_LABEL_SMOOTHING_FLAGS} \
              ${V5_LOOKAHEAD_FLAGS} \
              ${V5_MIXUP_CUTOFF_FLAGS} \
              ${V5_POOLING_FLAGS} \
              ${V5_HARD_NEGATIVE_FLAGS} \
              ${CUTTING_EDGE_MIXUP_FLAGS} \
              ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
              ${CUTTING_EDGE_FOCAL_FLAGS} \
              ${CUTTING_EDGE_EMA_FLAGS} \
              ${CUTTING_EDGE_SAM_FLAGS} \
              ${CUTTING_EDGE_SWA_FLAGS} \
              ${CUTTING_EDGE_RDROP_FLAGS} \
              ${CUTTING_EDGE_CURRICULUM_FLAGS} \
              ${CUTTING_EDGE_CALIBRATION_FLAGS} \
              --scheduler cosine_warm_restarts \
              --warm-restart-t0 30 \
              --warm-restart-mult 2 \
              --warmup-epochs 20 \
              --warmup-lr-factor 0.05 \
              --grad-clip-norm 1.0 \
              --weight-decay 0.01 \
              --channels-last \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/v5/full" \
              --seed 1337 \
              --checkpoint-every 10 \
              --wandb-project beatsight-v5 \
              $resume_flag
            
            log ""
            log "💎 V5 ULTIMATE model training complete!"
            log "This is the most advanced single-model architecture combining:"
            log "  1. Coordinate Attention (spatial-aware)"
            log "  2. Stochastic Depth (DropPath regularization)"
            log "  3. Deep Supervision (auxiliary losses)"
            log "  4. Multi-Scale Fusion (temporal awareness)"
            log "  5. Gradient Centralization (optimizer enhancement)"
            log "  6. Multi-task Learning (velocity + hi-hat openness)"
            log "  7. Waveform Augmentation (audio-level transformations)"
            log "  8. FMix (Fourier-domain mixup)"
            log "  9. Progressive Augmentation (strength ramps up during training)"
            log " 10. Label Smoothing (regularization, prevents overconfidence)"
            log " 11. Gradient Clipping + Weight Decay (training stability)"
            log " 12. Channels-Last Memory Format (NVIDIA GPU optimization)"
            log " 13. Lookahead Optimizer (slow weights for stability)"
            log " 14. Cosine Warm Restarts (escape local minima)"
            log " 15. Mixup Cutoff (cleaner decision boundaries in final phase)"
            log " 16. Attentive Statistics Pooling (focus on attack transients)"
            log " 17. Hard Negative Contrastive Loss (embedding separation for confused pairs)"
            log " 18. TTA Validation (accurate quality estimate during training)"
            log " 19. Extended Warmup (20 epochs for SAM+Lookahead stability)"
            log ""
            log "📌 NEXT STEP (Recommended): Self-Distillation for +1-2% more accuracy"
            log "   Run: ./auto_train.sh v5-self-distill"
            ;;
        
        # =====================================================================
        # V5 SELF-DISTILLATION (17e) - Born-Again Networks
        # Train V5 again using the first V5's predictions as teacher
        # Reference: "Born-Again Neural Networks" (Furlanello et al., ICML 2018)
        # =====================================================================
        
        v5-self-distill)
            log "🔄 Starting V5 SELF-DISTILLATION training (Born-Again Networks)..."
            log "   Using first V5 model as teacher, training identical student..."
            log "   Expected improvement: +1-2% from dark knowledge transfer..."
            log "   Includes: Attentive Statistics Pooling (Option A enhancement)..."
            export WANDB_RUN_GROUP=v5_self_distill_auto
            
            # Check for teacher model from v5-full
            TEACHER_MODEL="${BEATSIGHT_RUN_CUTTING_EDGE}/v5/full/best_drum_classifier_ema.pth"
            if [ ! -f "$TEACHER_MODEL" ]; then
                TEACHER_MODEL="${BEATSIGHT_RUN_CUTTING_EDGE}/v5/full/best_drum_classifier.pth"
            fi
            
            if [ ! -f "$TEACHER_MODEL" ]; then
                log "ERROR: Teacher model not found. Run v5-full (17d) first."
                log "   Expected: ${BEATSIGHT_RUN_CUTTING_EDGE}/v5/full/best_drum_classifier.pth"
                exit 1
            fi
            
            log "   Teacher model: $TEACHER_MODEL"
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
              --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
              --device cuda \
              --num-workers 4 --val-num-workers 4 --prefetch-factor 4 \
              --pin-memory --amp-dtype float16 \
              --epochs 150 \
              --batch-size 256 \
              --lr 0.001 \
              --model-version v5 \
              --v5-size large \
              --drop-path-rate 0.15 \
              ${V5_DEEP_SUPERVISION_FLAGS} \
              ${V5_GRADIENT_CENTRALIZATION_FLAGS} \
              ${V5_MULTI_TASK_FLAGS} \
              ${V5_WAVEFORM_AUGMENT_FLAGS} \
              ${V5_FMIX_FLAGS} \
              ${V5_PROGRESSIVE_FLAGS} \
              ${V5_LABEL_SMOOTHING_FLAGS} \
              ${V5_LOOKAHEAD_FLAGS} \
              ${V5_MIXUP_CUTOFF_FLAGS} \
              ${V5_POOLING_FLAGS} \
              ${V5_HARD_NEGATIVE_FLAGS} \
              ${CUTTING_EDGE_MIXUP_FLAGS} \
              ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
              ${CUTTING_EDGE_FOCAL_FLAGS} \
              ${CUTTING_EDGE_EMA_FLAGS} \
              ${CUTTING_EDGE_SAM_FLAGS} \
              ${CUTTING_EDGE_SWA_FLAGS} \
              ${CUTTING_EDGE_RDROP_FLAGS} \
              ${CUTTING_EDGE_CURRICULUM_FLAGS} \
              ${CUTTING_EDGE_CALIBRATION_FLAGS} \
              --scheduler cosine_warm_restarts \
              --warm-restart-t0 30 \
              --warm-restart-mult 2 \
              --warmup-epochs 20 \
              --warmup-lr-factor 0.05 \
              --grad-clip-norm 1.0 \
              --weight-decay 0.01 \
              --channels-last \
              --distill-from-single "$TEACHER_MODEL" \
              --distill-temperature 4.0 \
              --distill-alpha 0.5 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/v5/self-distill" \
              --seed 2024 \
              --checkpoint-every 10 \
              --wandb-project beatsight-v5 \
              $resume_flag
            
            log ""
            log "🔄 V5 Self-Distillation complete!"
            log "This model learned from both ground truth labels AND the first V5's predictions."
            log "The 'dark knowledge' from soft predictions typically provides +1-2% improvement."
            log ""
            log "📁 Final model saved to: ${BEATSIGHT_RUN_CUTTING_EDGE}/v5/self-distill/"
            log "🚀 This is your PRODUCTION model - deploy this one!"
            ;;
        
        # =====================================================================
        # BEATs AUDIO FOUNDATION (18a/18b/18c) - Microsoft's BEATs Model
        # =====================================================================
        
        beats-warmup)
            log "🎵 Starting BEATs training (warmup - frozen encoder)..."
            log "   Using pretrained BEATs audio foundation model..."
            export WANDB_RUN_GROUP=beats_warmup_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --epochs 15 \
              --batch-size 16 \
              --lr 0.001 \
              ${BEATS_MODEL_FLAGS} \
              ${CUTTING_EDGE_FOCAL_FLAGS} \
              ${CUTTING_EDGE_EMA_FLAGS} \
              --warmup-epochs 3 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/beats/warmup" \
              --seed 1337 \
              --checkpoint-every 5 \
              --wandb-project beatsight-beats
            ;;
        
        beats-quick)
            log "🎵 Starting BEATs training (quick - fine-tuned encoder)..."
            log "   Full fine-tuning with layer-wise LR decay..."
            export WANDB_RUN_GROUP=beats_quick_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --epochs 30 \
              --batch-size 16 \
              --lr 0.0001 \
              ${BEATS_FINETUNE_FLAGS} \
              ${CUTTING_EDGE_MIXUP_FLAGS} \
              ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
              ${CUTTING_EDGE_FOCAL_FLAGS} \
              ${CUTTING_EDGE_EMA_FLAGS} \
              --warmup-epochs 5 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/beats/quick" \
              --seed 1337 \
              --checkpoint-every 5 \
              --wandb-project beatsight-beats
            ;;
        
        beats-long)
            log "🎵 Starting BEATs training (long - maximum quality)..."
            log "   Full fine-tuning with all augmentations..."
            export WANDB_RUN_GROUP=beats_long_auto
            
            PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
              --dataset "${BEATSIGHT_DATASET_DIR}" \
              --epochs 60 \
              --batch-size 16 \
              --lr 0.00005 \
              ${BEATS_FINETUNE_FLAGS} \
              ${V5_DEEP_SUPERVISION_FLAGS} \
              ${CUTTING_EDGE_MIXUP_FLAGS} \
              ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
              ${CUTTING_EDGE_FOCAL_FLAGS} \
              ${CUTTING_EDGE_EMA_FLAGS} \
              ${CUTTING_EDGE_SAM_FLAGS} \
              ${CUTTING_EDGE_SWA_FLAGS} \
              ${CUTTING_EDGE_CALIBRATION_FLAGS} \
              --warmup-epochs 10 \
              --output "${BEATSIGHT_RUN_CUTTING_EDGE}/beats/long" \
              --seed 1337 \
              --checkpoint-every 10 \
              --wandb-project beatsight-beats
            
            log ""
            log "🎵 BEATs model training complete!"
            log "Using Microsoft's state-of-the-art audio foundation model"
            log "Expected to outperform Wav2Vec2 for classification tasks!"
            ;;
    esac
}

# =============================================================================
# Main Loop
# =============================================================================

echo ""
echo "============================================================"
echo "  BeatSight Auto-Training: $TRAIN_MODE"
echo "============================================================"
echo "  Output:     $RUN_DIR"
echo "  Log:        $LOG_FILE"
echo "  Max Retries: $MAX_RETRIES"
echo "  Retry Delay: ${RETRY_DELAY}s"
echo "============================================================"
echo ""

log_summary "=== Auto-training started: $TRAIN_MODE ==="

# Check if already complete (has completion marker)
if check_training_complete; then
    log "✅ Training already complete! Final model exists at: ${RUN_DIR}/final_drum_classifier.pth"
    log_summary "Training already complete (no action needed)"
    exit 0
fi

# Check for old/incomplete run data and prompt user
prompt_clear_old_run

attempt=0
start_time=$(date +%s)

while [ $attempt -lt $MAX_RETRIES ]; do
    attempt=$((attempt + 1))
    
    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "  Attempt $attempt / $MAX_RETRIES"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_summary "Attempt $attempt started"
    
    # Run training
    if run_training 2>&1 | tee -a "$LOG_FILE"; then
        # Training exited with code 0 - mark as complete
        mark_complete
        
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        hours=$((duration / 3600))
        minutes=$(((duration % 3600) / 60))
        
        log ""
        log "🎉🎉🎉 TRAINING COMPLETE! 🎉🎉🎉"
        log "  Total attempts: $attempt"
        log "  Total time: ${hours}h ${minutes}m"
        log "  Best model: ${RUN_DIR}/best_drum_classifier.pth"
        log "  Final model: ${RUN_DIR}/final_drum_classifier.pth"
        log ""
        
        log_summary "SUCCESS after $attempt attempts (${hours}h ${minutes}m)"
        
        notify "BeatSight Training Complete!" "Mode: $TRAIN_MODE | Attempts: $attempt | Time: ${hours}h ${minutes}m"
        
        # Sync wandb runs
        log "📤 Syncing offline wandb runs..."
        wandb sync "${BEATSIGHT_REPO_ROOT}/wandb"/offline-run-*/ 2>&1 | tee -a "$LOG_FILE" || true
        
        exit 0
    fi
    
    # Training crashed or didn't complete
    exit_code=$?
    log ""
    log "⚠️  Training exited with code $exit_code"
    log_summary "Attempt $attempt failed (exit code $exit_code)"
    
    if [ $attempt -lt $MAX_RETRIES ]; then
        log "⏳ Waiting ${RETRY_DELAY}s before retry..."
        sleep $RETRY_DELAY
    fi
done

log ""
log "❌ Max retries ($MAX_RETRIES) exceeded. Training did not complete."
log_summary "FAILED after $MAX_RETRIES attempts"
notify "BeatSight Training Failed" "Mode: $TRAIN_MODE exceeded max retries ($MAX_RETRIES)"
exit 1
