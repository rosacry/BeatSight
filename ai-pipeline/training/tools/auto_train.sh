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

# Configuration
MAX_RETRIES=999           # Effectively infinite
RETRY_DELAY=30            # Seconds to wait between retries
LOG_DIR="${BEATSIGHT_REPO_ROOT}/logs/auto_train"

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
    *)
        echo "Usage: $0 {warmup|quick|long}"
        echo "  warmup (5a) - Warmup probe training"
        echo "  quick  (5b) - Quick refresh training"
        echo "  long   (5c) - Long run training"
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
