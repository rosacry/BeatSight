#!/bin/bash
# =============================================================================
# BeatSight Cloud Training - COMPLETE AUTONOMOUS SCRIPT
# =============================================================================
# This script handles EVERYTHING for cloud training:
#   ✅ Environment setup (all BEATSIGHT_* variables)
#   ✅ Python environment activation
#   ✅ Pre-flight validation
#   ✅ Data directory detection and setup
#   ✅ Full training pipeline execution
#   ✅ Auto-shutdown when training completes
#   ✅ GPU idle watchdog (auto-terminate if GPU idle too long)
#   ✅ Checkpoint syncing to remote storage
#   ✅ Training progress notifications
#   ✅ Instance cost tracking
#   ✅ Automatic crash recovery with retry
#   ✅ Maximum cost protection (hard budget limit)
#   ✅ Heartbeat monitoring (detect hung processes)
#
# ONE-LINER TO START TRAINING:
#   ./cloud_training.sh auto
#
# This will:
#   1. Detect/setup all paths automatically
#   2. Run preflight checks
#   3. Start the full training pipeline
#   4. Auto-shutdown when complete
#
# OVERNIGHT PROTECTION:
#   - GPU idle watchdog auto-terminates after 30min idle
#   - Max cost limit triggers auto-shutdown
#   - Crash recovery retries failed phases
#   - Checkpoint sync every 30 minutes
#   - Heartbeat detection for hung processes
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# =============================================================================
# CLOUD CONFIGURATION - Edit these for your setup
# =============================================================================
CLOUD_PROVIDER=${CLOUD_PROVIDER:-"lambda"}  # lambda, aws, gcp
INSTANCE_HOURLY_RATE=${INSTANCE_HOURLY_RATE:-1.29}  # Lambda A100 40GB
AUTO_SHUTDOWN=${AUTO_SHUTDOWN:-true}
SHUTDOWN_DELAY_MINUTES=${SHUTDOWN_DELAY_MINUTES:-5}
IDLE_SHUTDOWN_MINUTES=${IDLE_SHUTDOWN_MINUTES:-30}

# Checkpoint sync configuration
SYNC_INTERVAL_SECONDS=${SYNC_INTERVAL_SECONDS:-1800}  # 30 minutes
REMOTE_BACKUP_PATH=${REMOTE_BACKUP_PATH:-""}  # Set to rsync destination or S3 bucket

# Notification configuration (optional)
SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL:-""}
DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-""}
NTFY_TOPIC=${NTFY_TOPIC:-""}  # ntfy.sh topic for mobile notifications

# =============================================================================
# OVERNIGHT PROTECTION - Critical for unattended training
# =============================================================================
# Maximum cost before auto-shutdown (prevents runaway costs)
MAX_COST_USD=${MAX_COST_USD:-100}  # $100 hard limit (your full pipeline is ~$66)

# Maximum runtime in hours before auto-shutdown (backup protection)
MAX_RUNTIME_HOURS=${MAX_RUNTIME_HOURS:-60}  # 60 hours max (full pipeline is ~51hr)

# Crash recovery: retry failed phases this many times
MAX_RETRIES=${MAX_RETRIES:-2}

# Heartbeat timeout: if no log output for this many minutes, consider process hung
HEARTBEAT_TIMEOUT_MINUTES=${HEARTBEAT_TIMEOUT_MINUTES:-30}

# OOM (Out of Memory) recovery: reduce batch size and retry
OOM_RECOVERY=${OOM_RECOVERY:-true}
OOM_BATCH_SIZE_REDUCTION=${OOM_BATCH_SIZE_REDUCTION:-0.5}  # Reduce batch to 50%

# =============================================================================
# AUTO-DETECT PATHS - Works on Lambda Labs, AWS, GCP, and local
# =============================================================================
setup_environment() {
    log "🔧 Setting up environment..."
    
    # Detect cloud environment and set appropriate paths
    if [ -d "/home/ubuntu" ]; then
        # Lambda Labs / AWS typical setup
        CLOUD_HOME="/home/ubuntu"
    elif [ -d "/home/user" ]; then
        # Some cloud providers use /home/user
        CLOUD_HOME="/home/user"
    else
        CLOUD_HOME="$HOME"
    fi
    
    # Look for data in common locations
    # Priority order:
    #   1. Explicitly set BEATSIGHT_DATA_ROOT
    #   2. /home/ubuntu/beatsight_data (Lambda Labs convention)
    #   3. /data/beatsight (mounted volume)
    #   4. ${REPO_ROOT}/data (local development)
    
    if [ -z "$BEATSIGHT_DATA_ROOT" ]; then
        if [ -d "${CLOUD_HOME}/beatsight_data" ]; then
            export BEATSIGHT_DATA_ROOT="${CLOUD_HOME}/beatsight_data"
        elif [ -d "/data/beatsight" ]; then
            export BEATSIGHT_DATA_ROOT="/data/beatsight"
        elif [ -d "${REPO_ROOT}/data" ]; then
            export BEATSIGHT_DATA_ROOT="${REPO_ROOT}/data"
        else
            log "❌ ERROR: Cannot find data directory!"
            log "   Please set BEATSIGHT_DATA_ROOT or create one of:"
            log "   - ${CLOUD_HOME}/beatsight_data"
            log "   - /data/beatsight"
            log "   - ${REPO_ROOT}/data"
            exit 1
        fi
    fi
    
    # Find the dataset directory (consolidated cache preferred)
    if [ -z "$BEATSIGHT_DATASET_DIR" ]; then
        # Check for consolidated cache first (much faster)
        if [ -d "${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup_consolidated" ]; then
            export BEATSIGHT_DATASET_DIR="${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup_consolidated"
        elif [ -d "${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup" ]; then
            export BEATSIGHT_DATASET_DIR="${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup"
        elif [ -d "${BEATSIGHT_DATA_ROOT}/feature_cache" ]; then
            # Find any consolidated cache
            local consolidated=$(find "${BEATSIGHT_DATA_ROOT}/feature_cache" -name "manifest.json" -type f 2>/dev/null | head -1)
            if [ -n "$consolidated" ]; then
                export BEATSIGHT_DATASET_DIR="$(dirname "$consolidated")"
            else
                export BEATSIGHT_DATASET_DIR="${BEATSIGHT_DATA_ROOT}/feature_cache"
            fi
        else
            log "❌ ERROR: Cannot find dataset directory!"
            log "   Please set BEATSIGHT_DATASET_DIR"
            exit 1
        fi
    fi
    
    # Set cache directory (for training outputs)
    if [ -z "$BEATSIGHT_CACHE_DIR" ]; then
        export BEATSIGHT_CACHE_DIR="${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup"
    fi
    
    # Set labels cache directory
    if [ -z "$BEATSIGHT_LABELS_CACHE_DIR" ]; then
        export BEATSIGHT_LABELS_CACHE_DIR="${BEATSIGHT_DATA_ROOT}/dataset_index"
    fi
    
    # Set output directory for training runs
    if [ -z "$BEATSIGHT_OUTPUT_ROOT" ]; then
        export BEATSIGHT_OUTPUT_ROOT="${BEATSIGHT_DATA_ROOT}/training_output"
    fi
    mkdir -p "$BEATSIGHT_OUTPUT_ROOT"
    
    # Set repo root
    export BEATSIGHT_REPO_ROOT="$REPO_ROOT"
    
    # Set metrics directory
    export BEATSIGHT_METRICS_DIR="${REPO_ROOT}/ai-pipeline/training/reports/metrics"
    mkdir -p "$BEATSIGHT_METRICS_DIR"
    
    # Set run directories
    export BEATSIGHT_RUN_WARMUP="${REPO_ROOT}/ai-pipeline/training/runs/prod_combined_warmup"
    export BEATSIGHT_RUN_V5="${REPO_ROOT}/ai-pipeline/training/runs/v5"
    mkdir -p "$BEATSIGHT_RUN_WARMUP" "$BEATSIGHT_RUN_V5"
    
    # Add ai-pipeline to PYTHONPATH
    export PYTHONPATH="${REPO_ROOT}/ai-pipeline:${PYTHONPATH:-}"
    
    # Print environment summary
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "  Environment Configuration"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "  BEATSIGHT_DATA_ROOT:       $BEATSIGHT_DATA_ROOT"
    log "  BEATSIGHT_DATASET_DIR:     $BEATSIGHT_DATASET_DIR"
    log "  BEATSIGHT_CACHE_DIR:       $BEATSIGHT_CACHE_DIR"
    log "  BEATSIGHT_LABELS_CACHE_DIR: $BEATSIGHT_LABELS_CACHE_DIR"
    log "  BEATSIGHT_OUTPUT_ROOT:     $BEATSIGHT_OUTPUT_ROOT"
    log "  BEATSIGHT_REPO_ROOT:       $BEATSIGHT_REPO_ROOT"
    log "  PYTHONPATH:                $PYTHONPATH"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Verify critical directories exist
    local missing=0
    for dir in "$BEATSIGHT_DATA_ROOT" "$BEATSIGHT_DATASET_DIR"; do
        if [ ! -d "$dir" ]; then
            log "❌ Missing directory: $dir"
            missing=1
        fi
    done
    
    if [ $missing -eq 1 ]; then
        log "❌ Environment setup failed - missing directories"
        exit 1
    fi
    
    log "✅ Environment setup complete"
}

# =============================================================================
# DATASET INTEGRITY CHECK - Critical for catching upload issues
# =============================================================================
validate_dataset() {
    log "🔍 Validating dataset integrity..."
    
    local dataset_dir="${BEATSIGHT_DATASET_DIR}"
    local errors=0
    
    # Check manifest exists
    if [ ! -f "${dataset_dir}/manifest.json" ]; then
        log "❌ Missing manifest.json in ${dataset_dir}"
        log "   This file is required for consolidated cache"
        errors=$((errors + 1))
    else
        log "✓ manifest.json found"
        
        # Parse manifest for validation
        local total_samples=$(python3 -c "import json; m=json.load(open('${dataset_dir}/manifest.json')); print(m.get('total_samples', 0))" 2>/dev/null || echo "0")
        local num_shards=$(python3 -c "import json; m=json.load(open('${dataset_dir}/manifest.json')); print(len(m.get('shards', [])))" 2>/dev/null || echo "0")
        
        log "   Total samples: ${total_samples}"
        log "   Number of shards: ${num_shards}"
        
        if [ "$total_samples" -lt 1000000 ]; then
            log "⚠️  Warning: Only ${total_samples} samples found"
            log "   Expected 14M+ samples for full training"
            log "   This may indicate incomplete upload"
        fi
        
        # Check if shards exist
        local missing_shards=0
        for i in $(seq 0 $((num_shards - 1))); do
            local shard_file="${dataset_dir}/shard_$(printf '%05d' $i).bin"
            if [ ! -f "$shard_file" ]; then
                missing_shards=$((missing_shards + 1))
                if [ $missing_shards -le 3 ]; then
                    log "❌ Missing shard: $shard_file"
                fi
            fi
        done
        
        if [ $missing_shards -gt 0 ]; then
            log "❌ ${missing_shards} shard files missing!"
            log "   Upload may be incomplete. Re-run rsync."
            errors=$((errors + 1))
        else
            log "✓ All ${num_shards} shards present"
        fi
        
        # Quick read test - verify first shard is readable
        log "   Testing shard readability..."
        if python3 -c "
import numpy as np
import os
shard_path = os.path.join('${dataset_dir}', 'shard_00000.bin')
if os.path.exists(shard_path):
    data = np.memmap(shard_path, dtype='float16', mode='r')
    print(f'   First shard: {len(data):,} elements, readable OK')
    del data
" 2>/dev/null; then
            log "✓ Shard files are readable"
        else
            log "❌ Failed to read shard file!"
            errors=$((errors + 1))
        fi
    fi
    
    # Check components.json exists (needed for feature reconstruction)
    if [ ! -f "${dataset_dir}/components.json" ]; then
        log "⚠️  Missing components.json - may be OK for some cache types"
    else
        log "✓ components.json found"
    fi
    
    # Calculate dataset size
    local dataset_size=$(du -sh "${dataset_dir}" 2>/dev/null | cut -f1)
    log "   Dataset size: ${dataset_size}"
    
    if [ $errors -gt 0 ]; then
        log ""
        log "❌ Dataset validation FAILED with ${errors} errors!"
        log "   Please fix the issues above before training."
        return 1
    else
        log ""
        log "✅ Dataset validation passed!"
        return 0
    fi
}

# =============================================================================
# PYTHON ENVIRONMENT SETUP
# =============================================================================
setup_python() {
    log "🐍 Setting up Python environment..."
    
    # Check for virtual environment
    if [ -d "${REPO_ROOT}/.venv" ]; then
        source "${REPO_ROOT}/.venv/bin/activate"
        log "   Activated: ${REPO_ROOT}/.venv"
    elif [ -d "${REPO_ROOT}/venv" ]; then
        source "${REPO_ROOT}/venv/bin/activate"
        log "   Activated: ${REPO_ROOT}/venv"
    elif [ -d "${CLOUD_HOME}/venv" ]; then
        source "${CLOUD_HOME}/venv/bin/activate"
        log "   Activated: ${CLOUD_HOME}/venv"
    else
        log "   Using system Python"
    fi
    
    # Verify PyTorch and CUDA
    python -c "import torch; print(f'   PyTorch: {torch.__version__}'); print(f'   CUDA: {torch.cuda.is_available()}')" || {
        log "❌ PyTorch not available!"
        exit 1
    }
    
    log "✅ Python environment ready"
}

# =============================================================================
# PRE-FLIGHT CHECK
# =============================================================================
run_preflight() {
    log "🔍 Running pre-flight checks..."
    
    cd "$REPO_ROOT"
    
    # Run the comprehensive preflight check
    if python ai-pipeline/training/tools/preflight_check.py \
        --cloud \
        --dataset "$BEATSIGHT_DATASET_DIR" \
        --labels-cache-dir "$BEATSIGHT_LABELS_CACHE_DIR"; then
        log "✅ Pre-flight checks passed!"
        return 0
    else
        log "❌ Pre-flight checks FAILED!"
        log "   Fix the issues above before training"
        return 1
    fi
}

# =============================================================================
# Paths (set after environment detection)
# =============================================================================
LOG_DIR="${REPO_ROOT}/logs/cloud_training"
COST_LOG="${LOG_DIR}/cost_tracking.log"
INSTANCE_START_FILE="${LOG_DIR}/.instance_start_time"

mkdir -p "$LOG_DIR"

# =============================================================================
# Utility Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_DIR}/cloud_training.log"
}

send_notification() {
    local title="$1"
    local message="$2"
    
    # Slack
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        curl -s -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"*${title}*\n${message}\"}" \
            "$SLACK_WEBHOOK_URL" >/dev/null 2>&1 || true
    fi
    
    # Discord
    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        curl -s -X POST -H 'Content-type: application/json' \
            --data "{\"content\":\"**${title}**\n${message}\"}" \
            "$DISCORD_WEBHOOK_URL" >/dev/null 2>&1 || true
    fi
    
    # ntfy.sh (great for mobile notifications)
    if [ -n "$NTFY_TOPIC" ]; then
        curl -s -d "$message" -H "Title: $title" \
            "https://ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 || true
    fi
    
    log "📬 Notification sent: $title"
}

get_gpu_utilization() {
    nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "0"
}

get_instance_uptime_hours() {
    if [ -f "$INSTANCE_START_FILE" ]; then
        local start_time=$(cat "$INSTANCE_START_FILE")
        local now=$(date +%s)
        local uptime_seconds=$((now - start_time))
        # Use bc if available, otherwise use awk
        if command -v bc &> /dev/null; then
            echo "scale=2; $uptime_seconds / 3600" | bc
        else
            awk "BEGIN {printf \"%.2f\", $uptime_seconds / 3600}"
        fi
    else
        echo "0"
    fi
}

get_current_cost() {
    local hours=$(get_instance_uptime_hours)
    # Use bc if available, otherwise use awk
    if command -v bc &> /dev/null; then
        echo "scale=2; $hours * $INSTANCE_HOURLY_RATE" | bc
    else
        awk "BEGIN {printf \"%.2f\", $hours * $INSTANCE_HOURLY_RATE}"
    fi
}

# =============================================================================
# Cloud Control Functions
# =============================================================================

init_instance_tracking() {
    if [ ! -f "$INSTANCE_START_FILE" ]; then
        date +%s > "$INSTANCE_START_FILE"
        log "⏱️  Instance tracking started"
        echo "$(date '+%Y-%m-%d %H:%M:%S') | Instance started | Rate: \$${INSTANCE_HOURLY_RATE}/hr" >> "$COST_LOG"
    fi
}

shutdown_instance() {
    local reason="$1"
    local hours=$(get_instance_uptime_hours)
    local cost=$(get_current_cost)
    
    log "🛑 Shutting down instance..."
    log "   Reason: $reason"
    log "   Uptime: ${hours} hours"
    log "   Cost: \$${cost}"
    
    echo "$(date '+%Y-%m-%d %H:%M:%S') | Shutdown: $reason | Uptime: ${hours}hr | Cost: \$${cost}" >> "$COST_LOG"
    
    send_notification "🛑 BeatSight Instance Shutdown" \
        "Reason: $reason\nUptime: ${hours} hours\nTotal Cost: \$${cost}"
    
    # Final checkpoint sync
    if [ -n "$REMOTE_BACKUP_PATH" ]; then
        log "📤 Final checkpoint sync before shutdown..."
        sync_checkpoints_once
    fi
    
    # Shutdown based on provider
    case "$CLOUD_PROVIDER" in
        lambda|aws|gcp)
            sudo shutdown -h +${SHUTDOWN_DELAY_MINUTES} "BeatSight auto-shutdown: $reason"
            ;;
        *)
            log "⚠️  Unknown cloud provider. Please shutdown manually."
            ;;
    esac
}

cancel_shutdown() {
    sudo shutdown -c 2>/dev/null || true
    log "🔄 Scheduled shutdown cancelled"
}

# =============================================================================
# OVERNIGHT PROTECTION FUNCTIONS
# =============================================================================

check_cost_limit() {
    local current_cost=$(get_current_cost)
    local cost_float=$(echo "$current_cost" | tr -d '$')
    
    # Check if we've exceeded max cost
    if (( $(echo "$cost_float >= $MAX_COST_USD" | bc -l 2>/dev/null || echo 0) )); then
        log "💰 COST LIMIT REACHED! Current: \$${current_cost}, Limit: \$${MAX_COST_USD}"
        send_notification "💰 Cost Limit Reached!" \
            "Current cost: \$${current_cost}\nLimit: \$${MAX_COST_USD}\nShutting down to protect your wallet!"
        shutdown_instance "Cost limit (\$${MAX_COST_USD}) reached"
        exit 0
    fi
}

check_runtime_limit() {
    local hours=$(get_instance_uptime_hours)
    local hours_float=$(echo "$hours" | tr -d '$')
    
    # Check if we've exceeded max runtime
    if (( $(echo "$hours_float >= $MAX_RUNTIME_HOURS" | bc -l 2>/dev/null || echo 0) )); then
        log "⏰ MAX RUNTIME REACHED! Current: ${hours}hr, Limit: ${MAX_RUNTIME_HOURS}hr"
        send_notification "⏰ Max Runtime Reached!" \
            "Runtime: ${hours} hours\nLimit: ${MAX_RUNTIME_HOURS} hours\nShutting down as safety measure!"
        shutdown_instance "Max runtime (${MAX_RUNTIME_HOURS}hr) reached"
        exit 0
    fi
}

check_heartbeat() {
    # Check if training is still producing output
    local log_file="$REPO_ROOT/logs/auto_train/auto_train_*.log"
    local latest_log=$(ls -t $log_file 2>/dev/null | head -1)
    
    if [ -n "$latest_log" ] && [ -f "$latest_log" ]; then
        local last_modified=$(stat -c %Y "$latest_log" 2>/dev/null || stat -f %m "$latest_log" 2>/dev/null)
        local now=$(date +%s)
        local age_seconds=$((now - last_modified))
        local age_minutes=$((age_seconds / 60))
        
        if [ "$age_minutes" -gt "$HEARTBEAT_TIMEOUT_MINUTES" ]; then
            log "💔 HEARTBEAT TIMEOUT! No log output for ${age_minutes} minutes"
            send_notification "💔 Training May Be Hung" \
                "No log output for ${age_minutes} minutes\nCheck if training is stuck!"
            return 1
        fi
    fi
    return 0
}

detect_oom_error() {
    local log_file="$1"
    
    if [ -f "$log_file" ]; then
        if grep -qi "CUDA out of memory\|RuntimeError.*OOM\|OutOfMemoryError" "$log_file" 2>/dev/null; then
            return 0  # OOM detected
        fi
    fi
    return 1  # No OOM
}

# =============================================================================
# Watchdog - Auto-terminate if GPU idle too long (ENHANCED)
# =============================================================================

run_watchdog() {
    log "🐕 Starting ENHANCED GPU watchdog..."
    log "   Idle threshold: ${IDLE_SHUTDOWN_MINUTES} minutes"
    log "   Max cost: \$${MAX_COST_USD}"
    log "   Max runtime: ${MAX_RUNTIME_HOURS} hours"
    log "   Heartbeat timeout: ${HEARTBEAT_TIMEOUT_MINUTES} minutes"
    log "   Checking every 60 seconds"
    
    local last_active=$(date +%s)
    local idle_threshold_seconds=$((IDLE_SHUTDOWN_MINUTES * 60))
    local check_count=0
    
    while true; do
        local gpu_util=$(get_gpu_utilization)
        
        if [ "$gpu_util" -gt 5 ]; then
            last_active=$(date +%s)
        fi
        
        local idle_time=$(($(date +%s) - last_active))
        local idle_minutes=$((idle_time / 60))
        
        # Check cost limit every 5 minutes
        if [ $((check_count % 5)) -eq 0 ]; then
            check_cost_limit
            check_runtime_limit
        fi
        
        # Check heartbeat every 10 minutes
        if [ $((check_count % 10)) -eq 0 ]; then
            if ! check_heartbeat; then
                log "⚠️  Heartbeat check failed - training may be hung"
                # Don't shutdown immediately, just warn
            fi
        fi
        
        if [ "$idle_time" -gt "$idle_threshold_seconds" ]; then
            log "⚠️  GPU idle for ${idle_minutes} minutes. Triggering shutdown..."
            shutdown_instance "GPU idle for ${idle_minutes} minutes"
            exit 0
        fi
        
        # Log status every 5 minutes
        if [ $((idle_time % 300)) -lt 60 ]; then
            local hours=$(get_instance_uptime_hours)
            local cost=$(get_current_cost)
            log "📊 Watchdog: GPU=${gpu_util}% | Idle=${idle_minutes}min | Uptime=${hours}hr | Cost=\$${cost} (limit: \$${MAX_COST_USD})"
        fi
        
        check_count=$((check_count + 1))
        sleep 60
    done
}

# =============================================================================
# Checkpoint Syncing
# =============================================================================

sync_checkpoints_once() {
    if [ -z "$REMOTE_BACKUP_PATH" ]; then
        log "⚠️  REMOTE_BACKUP_PATH not set. Skipping sync."
        return 1
    fi
    
    log "📤 Syncing checkpoints to: $REMOTE_BACKUP_PATH"
    
    # Check if it's an S3 path
    if [[ "$REMOTE_BACKUP_PATH" == s3://* ]]; then
        aws s3 sync "$CHECKPOINT_DIR" "$REMOTE_BACKUP_PATH" \
            --exclude "*.log" \
            --exclude "wandb/*" \
            2>&1 | tee -a "${LOG_DIR}/sync.log"
    # Check if it's a GCS path
    elif [[ "$REMOTE_BACKUP_PATH" == gs://* ]]; then
        gsutil -m rsync -r "$CHECKPOINT_DIR" "$REMOTE_BACKUP_PATH" \
            2>&1 | tee -a "${LOG_DIR}/sync.log"
    # Otherwise assume rsync destination
    else
        rsync -avP --exclude='*.log' --exclude='wandb/' \
            "$CHECKPOINT_DIR/" "$REMOTE_BACKUP_PATH/" \
            2>&1 | tee -a "${LOG_DIR}/sync.log"
    fi
    
    log "✅ Checkpoint sync complete"
}

run_checkpoint_sync() {
    log "🔄 Starting checkpoint sync daemon..."
    log "   Sync interval: ${SYNC_INTERVAL_SECONDS} seconds"
    log "   Remote path: ${REMOTE_BACKUP_PATH:-'NOT SET'}"
    
    if [ -z "$REMOTE_BACKUP_PATH" ]; then
        log "❌ ERROR: REMOTE_BACKUP_PATH not set!"
        log "   Set it with: export REMOTE_BACKUP_PATH='user@host:/path/to/backup'"
        log "   Or for S3:   export REMOTE_BACKUP_PATH='s3://bucket/beatsight/'"
        exit 1
    fi
    
    while true; do
        sync_checkpoints_once
        
        local hours=$(get_instance_uptime_hours)
        local cost=$(get_current_cost)
        log "💰 Running cost: \$${cost} (${hours} hours)"
        
        sleep "$SYNC_INTERVAL_SECONDS"
    done
}

# =============================================================================
# PRE-TRAINING VERIFICATION - Critical safety check before spending $$$
# =============================================================================
verify_before_training() {
    log "🔍 Running COMPREHENSIVE pre-training verification..."
    log "   (This catches issues that would otherwise waste cloud $$$)"
    log ""
    
    local errors=0
    local warnings=0
    
    # 1. Verify GPU is available and functional
    if ! nvidia-smi &>/dev/null; then
        log "❌ FATAL: nvidia-smi failed - GPU not available!"
        errors=$((errors + 1))
    else
        local gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
        local gpu_mem=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
        local gpu_util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1)
        log "✓ GPU: $gpu_name ($gpu_mem, ${gpu_util}% util)"
        
        # Check if it's the expected A100 40GB
        if [[ "$gpu_name" == *"A100"* ]] && [[ "$gpu_mem" == *"40"* ]]; then
            log "  → Perfect! This is the target A100 40GB"
        elif [[ "$gpu_name" == *"A100"* ]]; then
            log "  → A100 detected (may be 80GB variant)"
        else
            log "  ⚠️  Not an A100 - batch sizes may need adjustment"
            warnings=$((warnings + 1))
        fi
    fi
    
    # 2. Verify dataset is accessible and complete
    local dataset_dir="${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATASET_DIR}}"
    if [ -z "$dataset_dir" ] || [ ! -d "$dataset_dir" ]; then
        log "❌ FATAL: Dataset directory not found: $dataset_dir"
        errors=$((errors + 1))
    else
        # Check for manifest
        if [ -f "$dataset_dir/manifest.json" ]; then
            local sample_count=$(python3 -c "import json; m=json.load(open('$dataset_dir/manifest.json')); print(m.get('total_samples', 0))" 2>/dev/null || echo "0")
            local shard_count=$(python3 -c "import json; m=json.load(open('$dataset_dir/manifest.json')); print(len(m.get('shards', [])))" 2>/dev/null || echo "0")
            
            if [ "$sample_count" -lt 1000000 ]; then
                log "⚠️  WARNING: Only $sample_count samples found (expected 14M+)"
                log "   This may indicate incomplete data upload"
                warnings=$((warnings + 1))
            else
                log "✓ Dataset verified: ${sample_count} samples in ${shard_count} shards"
            fi
            
            # Verify shards exist
            local missing_shards=0
            for i in $(seq 0 $((shard_count - 1)) | head -5); do
                local shard_file="${dataset_dir}/shard_$(printf '%05d' $i).bin"
                if [ ! -f "$shard_file" ]; then
                    missing_shards=$((missing_shards + 1))
                fi
            done
            if [ "$missing_shards" -gt 0 ]; then
                log "❌ FATAL: Shard files missing! Upload incomplete."
                errors=$((errors + 1))
            fi
        else
            log "⚠️  Warning: No manifest.json found in $dataset_dir"
            log "   Training may still work but slower (non-consolidated cache)"
            warnings=$((warnings + 1))
        fi
    fi
    
    # 3. Verify labels cache
    local labels_dir="${BEATSIGHT_LABELS_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/dataset_index}"
    if [ -d "$labels_dir" ]; then
        local label_count=$(find "$labels_dir" -name "*labels*.json" -type f 2>/dev/null | wc -l)
        if [ "$label_count" -gt 0 ]; then
            log "✓ Labels cache: ${label_count} label files found"
        else
            log "⚠️  Warning: No label files found in $labels_dir"
            warnings=$((warnings + 1))
        fi
    else
        log "⚠️  Warning: Labels cache directory not found: $labels_dir"
        warnings=$((warnings + 1))
    fi
    
    # 4. Verify Python and training imports work
    if ! python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
        log "❌ FATAL: PyTorch CUDA not available!"
        errors=$((errors + 1))
    else
        local torch_version=$(python3 -c "import torch; print(torch.__version__)" 2>/dev/null)
        local cuda_version=$(python3 -c "import torch; print(torch.version.cuda)" 2>/dev/null)
        log "✓ PyTorch ${torch_version} with CUDA ${cuda_version}"
        
        # Check bfloat16 support (A100 feature)
        if python3 -c "import torch; torch.tensor([1.0], dtype=torch.bfloat16).cuda()" 2>/dev/null; then
            log "  → bfloat16 supported (optimal for A100)"
        else
            log "  ⚠️  bfloat16 not available, using float16"
        fi
    fi
    
    # 5. Verify training model loads
    log ""
    log "Testing model instantiation..."
    if python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/ai-pipeline')
from training.models.cnn_v5 import DrumClassifierCNNv5
model = DrumClassifierCNNv5(num_classes=21, use_deep_supervision=True, use_technique_heads=True)
print(f'  → V5 model: {sum(p.numel() for p in model.parameters()):,} parameters')
" 2>/dev/null; then
        log "✓ V5 model instantiates correctly"
    else
        log "❌ FATAL: V5 model failed to instantiate!"
        log "   Run preflight_check.py for detailed error"
        errors=$((errors + 1))
    fi
    
    # 6. Verify auto_train.sh exists and is executable
    if [ ! -x "$SCRIPT_DIR/auto_train.sh" ]; then
        if [ -f "$SCRIPT_DIR/auto_train.sh" ]; then
            chmod +x "$SCRIPT_DIR/auto_train.sh"
            log "✓ Made auto_train.sh executable"
        else
            log "❌ FATAL: auto_train.sh not found!"
            errors=$((errors + 1))
        fi
    else
        log "✓ auto_train.sh is executable"
    fi
    
    # 7. Verify sufficient disk space (need ~100GB for checkpoints)
    local free_gb=$(df -BG "$REPO_ROOT" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
    if [ -n "$free_gb" ] && [ "$free_gb" -lt 50 ]; then
        log "⚠️  WARNING: Only ${free_gb}GB disk space free"
        log "   Training may fail if checkpoints exceed available space"
        warnings=$((warnings + 1))
    else
        log "✓ Sufficient disk space: ${free_gb}GB free"
    fi
    
    # 8. Verify PYTHONPATH is set
    if [[ "$PYTHONPATH" != *"ai-pipeline"* ]]; then
        export PYTHONPATH="${REPO_ROOT}/ai-pipeline:${PYTHONPATH:-}"
        log "✓ Added ai-pipeline to PYTHONPATH"
    else
        log "✓ PYTHONPATH includes ai-pipeline"
    fi
    
    # 9. Test that training script parses without errors
    log ""
    log "Testing training script argument parsing..."
    if python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/ai-pipeline')
import argparse
exec(open('${REPO_ROOT}/ai-pipeline/training/train_classifier.py').read().split('if __name__')[0])
print('  → Training script imports correctly')
" 2>/dev/null; then
        log "✓ Training script parses correctly"
    else
        log "⚠️  Could not fully verify training script (may still work)"
        warnings=$((warnings + 1))
    fi
    
    # 10. Check remote backup path is set (critical for overnight safety)
    if [ -n "$REMOTE_BACKUP_PATH" ]; then
        log "✓ Remote backup configured: $REMOTE_BACKUP_PATH"
    else
        log "⚠️  REMOTE_BACKUP_PATH not set!"
        log "   Checkpoints will be saved locally only."
        log "   Set it for overnight safety: export REMOTE_BACKUP_PATH='s3://bucket/path'"
        warnings=$((warnings + 1))
    fi
    
    # Summary
    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ "$errors" -gt 0 ]; then
        log "❌ PRE-TRAINING VERIFICATION FAILED!"
        log "   $errors critical error(s), $warnings warning(s)"
        log "   Fix the errors above before continuing."
        log ""
        return 1
    elif [ "$warnings" -gt 0 ]; then
        log "⚠️  Pre-training verification passed with $warnings warning(s)"
        log "   Training can proceed, but consider addressing warnings."
        log ""
        return 0
    else
        log "✅ Pre-training verification PASSED!"
        log "   All checks passed. Ready to train."
        log ""
        return 0
    fi
}

# =============================================================================
# Training Pipeline
# =============================================================================

run_training_pipeline() {
    local modes=("$@")
    
    # Source saved environment if available
    if [ -f "$REPO_ROOT/.cloud_env" ]; then
        log "📋 Loading saved environment from .cloud_env"
        source "$REPO_ROOT/.cloud_env"
    fi
    
    # Also source beatsight_env.sh if exists (local development)
    if [ -f "$SCRIPT_DIR/beatsight_env.sh" ]; then
        source "$SCRIPT_DIR/beatsight_env.sh"
    fi
    
    # Verify we have required environment
    if [ -z "$BEATSIGHT_CACHE_DIR" ] && [ -z "$BEATSIGHT_DATASET_DIR" ]; then
        log "⚠️  WARNING: BEATSIGHT_CACHE_DIR and BEATSIGHT_DATASET_DIR not set!"
        log "   Run './cloud_training.sh auto' or './cloud_training.sh setup' first"
        log "   Or set manually: export BEATSIGHT_CACHE_DIR=/path/to/cache"
    fi
    
    # ═══════════════════════════════════════════════════════════════════════
    # PRE-TRAINING VERIFICATION - Don't waste $$$ on broken setup
    # ═══════════════════════════════════════════════════════════════════════
    if ! verify_before_training; then
        log ""
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "  💰 MONEY-SAVER: Training aborted due to verification failures"
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log ""
        log "  This saved you from wasting cloud compute time!"
        log "  Fix the issues above and run again."
        log ""
        return 1
    fi
    
    if [ ${#modes[@]} -eq 0 ]; then
        # Default: full V5 pipeline (17a → 17d → 17e → 19 → 19c)
        # Note: multilabel-generate is a data generation step, not training
        modes=("v5-warmup" "v5-full" "v5-self-distill" "multilabel-generate" "multilabel-finetune")
    fi
    
    init_instance_tracking
    
    # ═══════════════════════════════════════════════════════════════════════
    # Crash Recovery: Check for interrupted session
    # ═══════════════════════════════════════════════════════════════════════
    local resume_phase=""
    local resume_index=0
    
    if [ "$CRASH_RECOVERY_ENABLED" = true ] && [ -f "$LAST_PHASE_FILE" ]; then
        local last_phase=$(cat "$LAST_PHASE_FILE" 2>/dev/null)
        if [ -n "$last_phase" ]; then
            log "📋 Detected interrupted session at phase: $last_phase"
            
            # Find the index of the last phase
            for i in "${!modes[@]}"; do
                if [ "${modes[$i]}" = "$last_phase" ]; then
                    resume_index=$i
                    resume_phase="$last_phase"
                    break
                fi
            done
            
            if [ -n "$resume_phase" ]; then
                log "🔄 Resuming from phase $((resume_index + 1))/${#modes[@]}: $resume_phase"
                send_notification "🔄 Training Resumed" \
                    "Resuming from phase: $resume_phase\nProgress: $((resume_index + 1))/${#modes[@]}"
            fi
        fi
    fi
    
    local start_time=$(date +%s)
    local total_modes=${#modes[@]}
    local completed=$resume_index
    
    log "🚀 Starting BeatSight Cloud Training Pipeline"
    log "   Modes: ${modes[*]}"
    log "   Auto-shutdown: $AUTO_SHUTDOWN"
    log "   Hourly rate: \$${INSTANCE_HOURLY_RATE}"
    log "   Max cost limit: \$${MAX_COST_USD}"
    log "   Max runtime: ${MAX_RUNTIME_HOURS} hours"
    log "   Crash recovery: $CRASH_RECOVERY_ENABLED"
    
    if [ "$completed" -eq 0 ]; then
        send_notification "🚀 BeatSight Training Started" \
            "Pipeline: ${modes[*]}\nInstance: ${CLOUD_PROVIDER}\nRate: \$${INSTANCE_HOURLY_RATE}/hr\nMax cost: \$${MAX_COST_USD}"
    fi
    
    for ((idx=resume_index; idx<${#modes[@]}; idx++)); do
        local mode="${modes[$idx]}"
        completed=$((idx + 1))
        
        # Save current phase for crash recovery
        echo "$mode" > "$LAST_PHASE_FILE"
        
        # Update heartbeat
        date +%s > "$HEARTBEAT_FILE"
        
        log ""
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "  Phase $completed/$total_modes: $mode"
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        local phase_start=$(date +%s)
        local phase_success=false
        local retry_count=0
        
        # Get saved retry count for this phase
        if [ -f "$RETRY_COUNT_FILE" ]; then
            retry_count=$(cat "$RETRY_COUNT_FILE" 2>/dev/null || echo "0")
        fi
        
        while [ "$phase_success" = false ] && [ "$retry_count" -lt "$MAX_RETRIES" ]; do
            # Handle special modes that are not auto_train.sh steps
            if [ "$mode" = "multilabel-generate" ]; then
                log "🥁 Generating multi-label dataset..."
                log "   This converts single-label data to multi-label format"
                
                MULTILABEL_OUTPUT="${BEATSIGHT_OUTPUT_ROOT:-/home/ubuntu/beatsight_data}/multilabel_dataset"
                mkdir -p "$MULTILABEL_OUTPUT"
                
                PYTHONPATH=ai-pipeline python ai-pipeline/training/multilabel/generate_multilabel_dataset.py \
                    --events-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
                    --output-dir "$MULTILABEL_OUTPUT" \
                    --window-ms 30 \
                    --min-overlap 0.5
                
                if [ $? -eq 0 ]; then
                    log "✅ Multi-label dataset generated at: $MULTILABEL_OUTPUT"
                    phase_success=true
                else
                    log "❌ Multi-label dataset generation FAILED! (attempt $((retry_count + 1))/$MAX_RETRIES)"
                    retry_count=$((retry_count + 1))
                    echo "$retry_count" > "$RETRY_COUNT_FILE"
                    
                    if [ "$retry_count" -lt "$MAX_RETRIES" ] && [ "$CRASH_RECOVERY_ENABLED" = true ]; then
                        log "🔄 Retrying in 60 seconds..."
                        sleep 60
                    fi
                fi
            else
                # Run training via auto_train.sh
                if bash "$SCRIPT_DIR/auto_train.sh" "$mode"; then
                    phase_success=true
                else
                    log "❌ Phase $mode FAILED! (attempt $((retry_count + 1))/$MAX_RETRIES)"
                    retry_count=$((retry_count + 1))
                    echo "$retry_count" > "$RETRY_COUNT_FILE"
                    
                    if [ "$retry_count" -lt "$MAX_RETRIES" ] && [ "$CRASH_RECOVERY_ENABLED" = true ]; then
                        log "🔄 Retrying in 60 seconds..."
                        send_notification "⚠️ Training Error - Retrying" \
                            "Phase: $mode\nAttempt: $((retry_count))/$MAX_RETRIES\nRetrying in 60s..."
                        sleep 60
                    fi
                fi
            fi
            
            # Update heartbeat after each attempt
            date +%s > "$HEARTBEAT_FILE"
        done
        
        # Reset retry count for next phase
        echo "0" > "$RETRY_COUNT_FILE"
        
        if [ "$phase_success" = true ]; then
            local phase_end=$(date +%s)
            local phase_duration=$(( (phase_end - phase_start) / 60 ))
            local hours=$(get_instance_uptime_hours)
            local cost=$(get_current_cost)
            
            log "✅ Phase $mode complete! (${phase_duration} min)"
            log "   Running total: \$${cost} (${hours} hours)"
            
            send_notification "✅ Phase Complete: $mode" \
                "Duration: ${phase_duration} min\nProgress: $completed/$total_modes\nCost so far: \$${cost}"
            
            # Sync checkpoints after each phase
            if [ -n "$REMOTE_BACKUP_PATH" ]; then
                sync_checkpoints_once
            fi
        else
            log "❌ Phase $mode FAILED after $MAX_RETRIES attempts!"
            send_notification "❌ Training Failed: $mode" \
                "Phase $completed/$total_modes failed after $MAX_RETRIES retries.\nCheck logs for details."
            
            if [ "$AUTO_SHUTDOWN" = true ]; then
                shutdown_instance "Training failed at phase: $mode (after $MAX_RETRIES retries)"
            fi
            exit 1
        fi
    done
    
    # All phases complete - clean up state files
    rm -f "$LAST_PHASE_FILE" "$RETRY_COUNT_FILE" 2>/dev/null
    
    # All phases complete!
    local end_time=$(date +%s)
    local total_duration=$(( (end_time - start_time) / 60 ))
    local total_hours=$(get_instance_uptime_hours)
    local total_cost=$(get_current_cost)
    
    log ""
    log "🎉🎉🎉 ALL TRAINING PHASES COMPLETE! 🎉🎉🎉"
    log "   Total duration: ${total_duration} minutes"
    log "   Total cost: \$${total_cost}"
    log "   Phases completed: $total_modes"
    
    send_notification "🎉 BeatSight Training Complete!" \
        "All ${total_modes} phases finished!\nTotal time: ${total_duration} min\nTotal cost: \$${total_cost}"
    
    # Auto-shutdown if enabled
    if [ "$AUTO_SHUTDOWN" = true ]; then
        log ""
        log "🛑 Auto-shutdown enabled. Instance will terminate in ${SHUTDOWN_DELAY_MINUTES} minutes."
        log "   Run 'sudo shutdown -c' to cancel."
        shutdown_instance "Training pipeline complete"
    fi
}

# =============================================================================
# Cost Estimation
# =============================================================================

show_cost_estimate() {
    local hours=$(get_instance_uptime_hours)
    local current_cost=$(get_current_cost)
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  💰 BeatSight Cloud Cost Estimate"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Instance Rate:     \$${INSTANCE_HOURLY_RATE}/hour"
    echo "  Current Uptime:    ${hours} hours"
    echo "  Current Cost:      \$${current_cost}"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────────┐"
    echo "  │ Estimated Total Cost (Full Pipeline on A100 40GB)      │"
    echo "  ├─────────────────────────────────────────────────────────┤"
    echo "  │ v5-warmup:           ~1.5 hr  =  \$1.94                 │"
    echo "  │ v5-full (300 ep):    ~22 hr   =  \$28.38                │"
    echo "  │ v5-self-distill:     ~22 hr   =  \$28.38                │"
    echo "  │ multilabel-generate: ~0.5 hr  =  \$0.65                 │"
    echo "  │ multilabel-finetune: ~5 hr    =  \$6.45                 │"
    echo "  ├─────────────────────────────────────────────────────────┤"
    echo "  │ TOTAL:               ~51 hr   =  ~\$66                  │"
    echo "  └─────────────────────────────────────────────────────────┘"
    echo ""
    
    if [ -f "$COST_LOG" ]; then
        echo "  📋 Cost History:"
        tail -10 "$COST_LOG" | sed 's/^/     /'
        echo ""
    fi
}

# =============================================================================
# Setup tmux Session
# =============================================================================

setup_tmux_session() {
    local session_name="beatsight"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🚀 BeatSight Cloud Training - Complete Setup & Launch"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # =========================================================================
    # STEP 1: Environment Setup
    # =========================================================================
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 1: Setting up environment                                      │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    setup_environment
    
    # =========================================================================
    # STEP 2: Verify Python
    # =========================================================================
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 2: Verifying Python environment                                │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    setup_python
    
    # =========================================================================
    # STEP 3: Validate Dataset
    # =========================================================================
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 3: Validating dataset integrity                                │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    if ! validate_dataset; then
        echo ""
        echo "❌ Dataset validation failed! Please fix the issues above."
        echo ""
        echo "Common fixes:"
        echo "  1. Re-upload dataset: rsync -avP /path/to/feature_cache ubuntu@$(hostname -I | awk '{print $1}'):/home/ubuntu/beatsight_data/"
        echo "  2. Set path manually: export BEATSIGHT_DATASET_DIR=/path/to/dataset"
        echo ""
        return 1
    fi
    
    # =========================================================================
    # STEP 4: Run Preflight Checks
    # =========================================================================
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 4: Running preflight checks                                    │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    if ! run_preflight; then
        echo ""
        echo "❌ Preflight checks failed! Please fix the issues above."
        echo ""
        return 1
    fi
    
    # =========================================================================
    # STEP 5: Initialize cost tracking
    # =========================================================================
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 5: Initializing training session                               │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    init_instance_tracking
    
    # Show cost estimate
    show_cost_estimate
    
    # =========================================================================
    # STEP 6: Create tmux session
    # =========================================================================
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 6: Creating tmux session with all services                     │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    # Kill existing session if any
    tmux kill-session -t "$session_name" 2>/dev/null || true
    
    # Create log directory
    mkdir -p "$REPO_ROOT/logs/auto_train"
    
    # Create new session with training in first window
    tmux new-session -d -s "$session_name" -n "training"
    
    # Window 0: Training - run the full pipeline
    tmux send-keys -t "$session_name:training" \
        "cd $REPO_ROOT && source .cloud_env 2>/dev/null; bash ai-pipeline/training/tools/cloud_training.sh run-pipeline 2>&1 | tee logs/cloud_training/training_\$(date +%Y%m%d_%H%M%S).log" Enter
    
    # Window 1: Watchdog - monitors GPU and auto-terminates if idle
    tmux new-window -t "$session_name" -n "watchdog"
    tmux send-keys -t "$session_name:watchdog" \
        "cd $REPO_ROOT && source .cloud_env 2>/dev/null; bash ai-pipeline/training/tools/cloud_training.sh watchdog" Enter
    
    # Window 2: Checkpoint Sync (if configured)
    if [ -n "$REMOTE_BACKUP_PATH" ]; then
        tmux new-window -t "$session_name" -n "sync"
        tmux send-keys -t "$session_name:sync" \
            "cd $REPO_ROOT && source .cloud_env 2>/dev/null; bash ai-pipeline/training/tools/cloud_training.sh sync-checkpoints" Enter
    fi
    
    # Window 3: GPU Monitor
    tmux new-window -t "$session_name" -n "gpu"
    tmux send-keys -t "$session_name:gpu" "watch -n 2 nvidia-smi" Enter
    
    # Window 4: Logs
    tmux new-window -t "$session_name" -n "logs"
    tmux send-keys -t "$session_name:logs" \
        "tail -f $REPO_ROOT/logs/auto_train/auto_train_*.log $REPO_ROOT/logs/cloud_training/*.log 2>/dev/null || echo 'Waiting for logs...'; sleep 5; tail -f $REPO_ROOT/logs/auto_train/auto_train_*.log $REPO_ROOT/logs/cloud_training/*.log" Enter
    
    # Window 5: Shell - for manual commands if needed
    tmux new-window -t "$session_name" -n "shell"
    tmux send-keys -t "$session_name:shell" \
        "cd $REPO_ROOT && source .cloud_env 2>/dev/null; echo ''; echo '🔧 Ready for manual commands. Environment loaded.'; echo '   BEATSIGHT_DATASET_DIR=$BEATSIGHT_DATASET_DIR'; echo ''" Enter
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ SETUP COMPLETE - tmux Session Created: $session_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Windows:"
    echo "    0: training      - Main training pipeline (17a → 17d → 17e → 19c)"
    echo "    1: watchdog      - GPU idle watchdog (auto-shutdown after 30min idle)"
    if [ -n "$REMOTE_BACKUP_PATH" ]; then
        echo "    2: sync          - Checkpoint syncing to $REMOTE_BACKUP_PATH"
        echo "    3: gpu           - Real-time GPU monitor"
        echo "    4: logs          - Training logs (tail -f)"
        echo "    5: shell         - Interactive shell"
    else
        echo "    2: gpu           - Real-time GPU monitor"
        echo "    3: logs          - Training logs (tail -f)"
        echo "    4: shell         - Interactive shell"
    fi
    echo ""
    echo "  🔑 Key Commands:"
    echo "    tmux attach -t $session_name     # Attach to session"
    echo "    Ctrl+B, D                        # Detach (training continues!)"
    echo "    Ctrl+B, 0-5                      # Jump to window"
    echo "    Ctrl+B, N/P                      # Next/Previous window"
    echo ""
    echo "  💰 Cost Protection:"
    echo "    • Max cost limit: \$${MAX_COST_USD} (auto-shutdown if exceeded)"
    echo "    • GPU idle timeout: ${IDLE_SHUTDOWN_MINUTES} minutes"
    echo "    • Max runtime: ${MAX_RUNTIME_HOURS} hours"
    echo ""
    echo "  📊 Expected Training Path:"
    echo "    17a → V5 Warmup (~1.5 hr, ~\$1.94)"
    echo "    17d → V5 Full (~22 hr, ~\$28.38)"
    echo "    17e → V5 Self-Distill (~22 hr, ~\$28.38)"
    echo "    19c → Multi-Label Finetune (~5 hr, ~\$6.45)"
    echo "    ────────────────────────────"
    echo "    Total: ~51 hr, ~\$65"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🎯 To attach now, run:"
    echo ""
    echo "     tmux attach -t $session_name"
    echo ""
    echo "  You can safely close this SSH session after attaching!"
    echo "  Training will continue even if you disconnect."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Save environment for future sessions
    cat > "$REPO_ROOT/.cloud_env" << EOF
# BeatSight Cloud Training Environment
# Generated by cloud_training.sh start-session on $(date)
# Source this file to restore environment: source .cloud_env
export CLOUD_PROVIDER="$CLOUD_PROVIDER"
export INSTANCE_HOURLY_RATE="$INSTANCE_HOURLY_RATE"
export BEATSIGHT_REPO_ROOT="$BEATSIGHT_REPO_ROOT"
export BEATSIGHT_DATA_ROOT="$BEATSIGHT_DATA_ROOT"
export BEATSIGHT_CACHE_DIR="$BEATSIGHT_CACHE_DIR"
export BEATSIGHT_DATASET_DIR="$BEATSIGHT_DATASET_DIR"
export BEATSIGHT_LABELS_CACHE_DIR="$BEATSIGHT_LABELS_CACHE_DIR"
export BEATSIGHT_OUTPUT_ROOT="$BEATSIGHT_OUTPUT_ROOT"
export PYTHONPATH="$PYTHONPATH"
export AUTO_SHUTDOWN="$AUTO_SHUTDOWN"
export MAX_COST_USD="$MAX_COST_USD"
export MAX_RUNTIME_HOURS="$MAX_RUNTIME_HOURS"
export REMOTE_BACKUP_PATH="$REMOTE_BACKUP_PATH"
EOF
    
    log "✅ Environment saved to $REPO_ROOT/.cloud_env"
}

# =============================================================================
# FULL AUTOMATIC SETUP - Does EVERYTHING upon execute
# =============================================================================

full_auto_setup() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🤖 BeatSight FULL AUTOMATIC Cloud Setup"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  This will automatically:"
    echo "    1. Detect cloud provider (Lambda/AWS/GCP)"
    echo "    2. Install all Python dependencies"
    echo "    3. Find and setup data paths"
    echo "    4. Verify GPU availability"
    echo "    5. Run preflight checks"
    echo "    6. Start training in tmux session"
    echo ""
    
    local errors=0
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Detect Cloud Provider
    # ═══════════════════════════════════════════════════════════════════════
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 1/6: Detecting Cloud Provider                                  │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    if [ -f /etc/lambda-stack ]; then
        CLOUD_PROVIDER="lambda"
        INSTANCE_HOURLY_RATE="${INSTANCE_HOURLY_RATE:-1.29}"
        echo "  ✅ Detected: Lambda Labs"
        echo "     Rate: \$${INSTANCE_HOURLY_RATE}/hr"
    elif [ -f /sys/hypervisor/uuid ] && grep -qi "ec2" /sys/hypervisor/uuid 2>/dev/null; then
        CLOUD_PROVIDER="aws"
        INSTANCE_HOURLY_RATE="${INSTANCE_HOURLY_RATE:-3.06}"
        echo "  ✅ Detected: AWS EC2"
        echo "     Rate: \$${INSTANCE_HOURLY_RATE}/hr"
    elif curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/" &>/dev/null; then
        CLOUD_PROVIDER="gcp"
        INSTANCE_HOURLY_RATE="${INSTANCE_HOURLY_RATE:-2.93}"
        echo "  ✅ Detected: Google Cloud"
        echo "     Rate: \$${INSTANCE_HOURLY_RATE}/hr"
    else
        CLOUD_PROVIDER="unknown"
        INSTANCE_HOURLY_RATE="${INSTANCE_HOURLY_RATE:-1.29}"
        echo "  ⚠️  Unknown provider, assuming Lambda Labs pricing"
    fi
    
    export CLOUD_PROVIDER INSTANCE_HOURLY_RATE
    echo ""
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: Verify GPU
    # ═══════════════════════════════════════════════════════════════════════
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 2/6: Verifying GPU                                             │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    if ! command -v nvidia-smi &>/dev/null; then
        echo "  ❌ FATAL: nvidia-smi not found!"
        echo "     Cannot proceed without GPU drivers"
        exit 1
    fi
    
    local gpu_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    if [ -z "$gpu_info" ]; then
        echo "  ❌ FATAL: No GPU detected!"
        exit 1
    fi
    
    local gpu_name=$(echo "$gpu_info" | cut -d',' -f1)
    local gpu_memory=$(echo "$gpu_info" | cut -d',' -f2 | tr -d ' ')
    local gpu_count=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)
    
    echo "  ✅ GPU: $gpu_name"
    echo "     Memory: $gpu_memory"
    echo "     Count: $gpu_count"
    
    # Verify sufficient VRAM
    local vram_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')
    if [ "$vram_mb" -lt 30000 ]; then
        echo "  ⚠️  WARNING: Only ${vram_mb}MB VRAM. Recommend 40GB+ A100"
        echo "     Training may need reduced batch size"
    fi
    echo ""
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Install Python Dependencies
    # ═══════════════════════════════════════════════════════════════════════
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 3/6: Installing Python Dependencies                            │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    cd "$REPO_ROOT"
    
    # Check for venv
    if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
        echo "  📦 Creating Python virtual environment..."
        python3 -m venv venv
        source venv/bin/activate
        echo "  ✅ Created and activated venv"
    elif [ -d "venv" ]; then
        source venv/bin/activate
        echo "  ✅ Activated existing venv"
    elif [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "  ✅ Activated existing .venv"
    fi
    
    # Install requirements
    if [ -f "ai-pipeline/requirements.txt" ]; then
        echo "  📦 Installing ai-pipeline requirements..."
        pip install -q -r ai-pipeline/requirements.txt 2>&1 | tail -5
        echo "  ✅ ai-pipeline requirements installed"
    fi
    
    # Install torch if not present (Lambda usually has it)
    if ! python -c "import torch" 2>/dev/null; then
        echo "  📦 Installing PyTorch with CUDA..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        echo "  ✅ PyTorch installed"
    else
        local torch_version=$(python -c "import torch; print(torch.__version__)")
        local cuda_avail=$(python -c "import torch; print(torch.cuda.is_available())")
        echo "  ✅ PyTorch $torch_version (CUDA: $cuda_avail)"
    fi
    
    # Install wandb for experiment tracking
    if ! python -c "import wandb" 2>/dev/null; then
        echo "  📦 Installing wandb..."
        pip install -q wandb
    fi
    echo "  ✅ wandb available"
    
    # Install tqdm, einops, etc
    pip install -q tqdm einops timm tensorboard h5py 2>/dev/null
    echo "  ✅ Training utilities installed"
    echo ""
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4: Setup Data Paths
    # ═══════════════════════════════════════════════════════════════════════
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 4/6: Setting Up Data Paths                                     │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    # Common cloud data locations to search
    local search_paths=(
        "/home/ubuntu/beatsight_data"
        "/home/ubuntu/data"
        "/mnt/data"
        "/data"
        "$HOME/data"
        "$REPO_ROOT/data"
        "/home/ubuntu/BeatSight/data"
    )
    
    local found_data_root=""
    local found_cache_dir=""
    local found_dataset_dir=""
    
    echo "  🔍 Searching for data directories..."
    
    for path in "${search_paths[@]}"; do
        if [ -d "$path" ]; then
            echo "     Found: $path"
            
            # Look for consolidated cache (our production dataset)
            for cache_candidate in \
                "$path/feature_cache/prod_combined_warmup_consolidated" \
                "$path/prod_combined_warmup_consolidated" \
                "$path/feature_cache/"*"consolidated"* \
                "$path/"*"consolidated"*; do
                
                if [ -d "$cache_candidate" ] && [ -f "$cache_candidate/manifest.json" ]; then
                    found_cache_dir="$cache_candidate"
                    echo "     ✅ Found consolidated cache: $found_cache_dir"
                    break 2
                fi
            done
            
            # If we found a data root but no cache yet, keep looking
            if [ -z "$found_data_root" ]; then
                found_data_root="$path"
            fi
        fi
    done
    
    # Set environment variables
    if [ -n "$found_cache_dir" ]; then
        export BEATSIGHT_CACHE_DIR="$found_cache_dir"
        export BEATSIGHT_DATA_ROOT="$(dirname "$(dirname "$found_cache_dir")")"
        echo "  ✅ BEATSIGHT_CACHE_DIR=$BEATSIGHT_CACHE_DIR"
        echo "  ✅ BEATSIGHT_DATA_ROOT=$BEATSIGHT_DATA_ROOT"
        
        # Count samples
        if [ -f "$found_cache_dir/manifest.json" ]; then
            local sample_count=$(python3 -c "import json; m=json.load(open('$found_cache_dir/manifest.json')); print(m.get('total_samples', 'unknown'))" 2>/dev/null || echo "unknown")
            echo "     📊 Dataset: $sample_count samples"
        fi
    else
        echo "  ⚠️  WARNING: No consolidated cache found!"
        echo "     Expected: .../feature_cache/prod_combined_warmup_consolidated/"
        echo ""
        echo "  You need to either:"
        echo "    1. Upload your data: rsync -avP data/ ubuntu@cloud:/home/ubuntu/beatsight_data/"
        echo "    2. Set BEATSIGHT_CACHE_DIR manually"
        echo ""
        errors=$((errors + 1))
    fi
    
    # Set other paths
    export BEATSIGHT_REPO_ROOT="$REPO_ROOT"
    export BEATSIGHT_DATASET_DIR="${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_DATA_ROOT}/dataset_index}"
    export BEATSIGHT_OUTPUT_ROOT="${BEATSIGHT_OUTPUT_ROOT:-${BEATSIGHT_DATA_ROOT}/checkpoints}"
    
    # Create output directories
    mkdir -p "$BEATSIGHT_OUTPUT_ROOT"
    mkdir -p "$REPO_ROOT/logs/auto_train"
    
    echo "  ✅ BEATSIGHT_REPO_ROOT=$BEATSIGHT_REPO_ROOT"
    echo "  ✅ BEATSIGHT_OUTPUT_ROOT=$BEATSIGHT_OUTPUT_ROOT"
    echo ""
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4.5: Validate Dataset Integrity (CRITICAL)
    # ═══════════════════════════════════════════════════════════════════════
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 4.5/6: Validating Dataset Integrity                            │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    if [ -n "$BEATSIGHT_CACHE_DIR" ]; then
        # Use the cache dir for validation
        export BEATSIGHT_DATASET_DIR="${BEATSIGHT_CACHE_DIR}"
        if validate_dataset; then
            echo "  ✅ Dataset validation passed!"
        else
            echo ""
            echo "  ❌ CRITICAL: Dataset validation FAILED!"
            echo "     Training cannot proceed with corrupt/incomplete data."
            echo ""
            echo "  Fix by re-uploading with:"
            echo "    rsync -avP --progress /path/to/feature_cache/consolidated ubuntu@cloud:/home/ubuntu/beatsight_data/feature_cache/"
            echo ""
            errors=$((errors + 1))
        fi
    else
        echo "  ⚠️  No cache directory set, skipping dataset validation"
    fi
    echo ""
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 5: Run Preflight Checks
    # ═══════════════════════════════════════════════════════════════════════
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 5/6: Running Preflight Checks                                  │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    
    local preflight_script="$REPO_ROOT/ai-pipeline/training/tools/preflight_check.py"
    
    if [ -f "$preflight_script" ]; then
        echo "  🔍 Running comprehensive preflight checks..."
        echo ""
        
        # Run preflight with quick mode for cloud (skip slow checks)
        if python "$preflight_script" --quick 2>&1 | tee /tmp/preflight_output.txt; then
            echo ""
            echo "  ✅ All preflight checks passed!"
        else
            echo ""
            echo "  ❌ Preflight checks failed!"
            echo "     Review output above for details"
            errors=$((errors + 1))
        fi
    else
        echo "  ⚠️  Preflight script not found at: $preflight_script"
        echo "     Skipping preflight checks..."
    fi
    echo ""
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 6: Summary and Start Training
    # ═══════════════════════════════════════════════════════════════════════
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ STEP 6/6: Setup Summary                                             │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    echo ""
    echo "  Cloud Provider:    $CLOUD_PROVIDER"
    echo "  Hourly Rate:       \$${INSTANCE_HOURLY_RATE}"
    echo "  GPU:               $gpu_name ($gpu_memory)"
    echo "  Data Root:         ${BEATSIGHT_DATA_ROOT:-NOT SET}"
    echo "  Cache Dir:         ${BEATSIGHT_CACHE_DIR:-NOT SET}"
    echo "  Output Dir:        ${BEATSIGHT_OUTPUT_ROOT:-NOT SET}"
    echo "  Auto-Shutdown:     $AUTO_SHUTDOWN"
    echo ""
    
    if [ "$errors" -gt 0 ]; then
        echo "  ⚠️  There were $errors setup issue(s). Please review and fix."
        echo ""
        echo "  Common fixes:"
        echo "    1. Upload data: rsync -avP /path/to/data ubuntu@cloud:beatsight_data/"
        echo "    2. Set paths manually: export BEATSIGHT_CACHE_DIR=/path/to/cache"
        echo ""
        echo "  After fixing, run: $0 auto"
        return 1
    fi
    
    echo "  ✅ Setup complete! Ready to train."
    echo ""
    
    # Write environment to file for future sessions
    cat > "$REPO_ROOT/.cloud_env" << EOF
# BeatSight Cloud Training Environment
# Generated by cloud_training.sh auto on $(date)
export CLOUD_PROVIDER="$CLOUD_PROVIDER"
export INSTANCE_HOURLY_RATE="$INSTANCE_HOURLY_RATE"
export BEATSIGHT_REPO_ROOT="$BEATSIGHT_REPO_ROOT"
export BEATSIGHT_DATA_ROOT="$BEATSIGHT_DATA_ROOT"
export BEATSIGHT_CACHE_DIR="$BEATSIGHT_CACHE_DIR"
export BEATSIGHT_DATASET_DIR="$BEATSIGHT_DATASET_DIR"
export BEATSIGHT_OUTPUT_ROOT="$BEATSIGHT_OUTPUT_ROOT"
export AUTO_SHUTDOWN="$AUTO_SHUTDOWN"
export INSTANCE_HOURLY_RATE="$INSTANCE_HOURLY_RATE"
EOF
    echo "  📝 Environment saved to: $REPO_ROOT/.cloud_env"
    echo "     Source it in new shells: source .cloud_env"
    echo ""
    
    return 0
}

run_auto_full() {
    # This is the ONE COMMAND to rule them all
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🚀 BeatSight AUTO - Complete Hands-Off Cloud Training"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  This script will:"
    echo "    1. Set up the entire environment automatically"
    echo "    2. Run all preflight checks"
    echo "    3. Start training in a tmux session"
    echo "    4. Run GPU watchdog to prevent idle charges"
    echo "    5. Auto-shutdown when training completes"
    echo ""
    echo "  Estimated cost: ~\$66 for full V5 pipeline on A100 40GB"
    echo "  Estimated time: ~51 hours"
    echo ""
    
    # Run full setup
    if ! full_auto_setup; then
        echo ""
        echo "  ❌ Setup failed. Please fix issues above and retry."
        exit 1
    fi
    
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────────┐"
    echo "│ 🎬 Starting Training in tmux Session                                │"
    echo "└─────────────────────────────────────────────────────────────────────┘"
    echo ""
    
    # Source environment
    source "$REPO_ROOT/.cloud_env" 2>/dev/null || true
    
    # Setup tmux session
    setup_tmux_session
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Training is now running in tmux session 'beatsight'"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  To attach and monitor:"
    echo "    tmux attach -t beatsight"
    echo ""
    echo "  To detach (training continues!):"
    echo "    Press Ctrl+B, then D"
    echo ""
    echo "  The instance will auto-shutdown when training completes."
    echo "  Estimated completion: ~51 hours from now"
    echo ""
    echo "  💰 Make sure you've set up REMOTE_BACKUP_PATH to save checkpoints!"
    echo "     export REMOTE_BACKUP_PATH='s3://bucket/path' (or rsync path)"
    echo ""
}

# =============================================================================
# Quick Start Guide
# =============================================================================

show_quickstart() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🚀 BeatSight Cloud Training Quick Start"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  EASIEST: Use the 'auto' command for complete hands-off training:"
    echo ""
    echo "    ./cloud_training.sh auto"
    echo ""
    echo "  This will automatically set up everything and start training!"
    echo ""
    echo "  ─────────────────────────────────────────────────────────────"
    echo ""
    echo "  MANUAL SETUP (if auto doesn't work):"
    echo ""
    echo "  1. Set up checkpoint backup (IMPORTANT!):"
    echo ""
    echo "     # Option A: rsync to your local machine"
    echo "     export REMOTE_BACKUP_PATH='user@your-ip:/path/to/backup/'"
    echo ""
    echo "     # Option B: S3 bucket"
    echo "     export REMOTE_BACKUP_PATH='s3://your-bucket/beatsight/'"
    echo ""
    echo "     # Option C: Google Cloud Storage"
    echo "     export REMOTE_BACKUP_PATH='gs://your-bucket/beatsight/'"
    echo ""
    echo "  2. (Optional) Set up notifications:"
    echo ""
    echo "     # Mobile notifications via ntfy.sh (free, easy!)"
    echo "     export NTFY_TOPIC='your-secret-topic'"
    echo ""
    echo "     # Or Slack/Discord webhooks"
    echo "     export SLACK_WEBHOOK_URL='https://hooks.slack.com/...'"
    echo ""
    echo "  3. Start training with auto-managed tmux session:"
    echo ""
    echo "     ./cloud_training.sh start-session"
    echo ""
    echo "  4. Detach and let it run (training continues!):"
    echo ""
    echo "     # Press: Ctrl+B, then D"
    echo ""
    echo "  5. Check progress anytime:"
    echo ""
    echo "     tmux attach -t beatsight"
    echo ""
    echo "  ⚡ The instance will AUTO-SHUTDOWN when training completes!"
    echo ""
}

# =============================================================================
# Data Transfer Helper
# =============================================================================

show_data_transfer() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📦 BeatSight Data Transfer Guide"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Your consolidated cache is at:"
    echo "    data/feature_cache/prod_combined_warmup_consolidated/"
    echo ""
    echo "  Data size: ~533 GB (250 shards, 14.6M samples)"
    echo ""
    echo "  ─────────────────────────────────────────────────────────────"
    echo "  OPTION 1: rsync (recommended for Lambda Labs)"
    echo "  ─────────────────────────────────────────────────────────────"
    echo ""
    echo "  # From your local machine to cloud:"
    echo "  rsync -avP --progress \\"
    echo "    data/feature_cache/prod_combined_warmup_consolidated \\"
    echo "    ubuntu@<CLOUD_IP>:/home/ubuntu/beatsight_data/feature_cache/"
    echo ""
    echo "  # Transfer rate: ~50-100 MB/s typical"
    echo "  # Time estimate: 1.5-3 hours for 533 GB"
    echo ""
    echo "  ─────────────────────────────────────────────────────────────"
    echo "  OPTION 2: S3 (for AWS or cross-cloud)"
    echo "  ─────────────────────────────────────────────────────────────"
    echo ""
    echo "  # Upload to S3:"
    echo "  aws s3 sync data/feature_cache/prod_combined_warmup_consolidated \\"
    echo "    s3://your-bucket/beatsight/consolidated/ --storage-class STANDARD"
    echo ""
    echo "  # Download on cloud instance:"
    echo "  aws s3 sync s3://your-bucket/beatsight/consolidated/ \\"
    echo "    /home/ubuntu/beatsight_data/feature_cache/prod_combined_warmup_consolidated"
    echo ""
    echo "  ─────────────────────────────────────────────────────────────"
    echo "  OPTION 3: GCS (for Google Cloud)"
    echo "  ─────────────────────────────────────────────────────────────"
    echo ""
    echo "  # Upload to GCS:"
    echo "  gsutil -m cp -r data/feature_cache/prod_combined_warmup_consolidated \\"
    echo "    gs://your-bucket/beatsight/"
    echo ""
    echo "  ─────────────────────────────────────────────────────────────"
    echo "  OPTION 4: Lambda Labs Persistent Storage"
    echo "  ─────────────────────────────────────────────────────────────"
    echo ""
    echo "  Lambda Labs offers persistent storage that survives instance termination."
    echo "  Upload once, reuse across training runs!"
    echo ""
    echo "  1. Create persistent storage in Lambda dashboard"
    echo "  2. Upload data to persistent storage"
    echo "  3. Mount when launching instance: /home/ubuntu/beatsight_data"
    echo ""
    echo "  ─────────────────────────────────────────────────────────────"
    echo "  WHAT TO UPLOAD"
    echo "  ─────────────────────────────────────────────────────────────"
    echo ""
    echo "  REQUIRED:"
    echo "    ✅ data/feature_cache/prod_combined_warmup_consolidated/"
    echo "       └── All 250 .bin shards + manifest.json + components.json"
    echo ""
    echo "  OPTIONAL (for checkpoint resume):"
    echo "    📁 ai-pipeline/training/runs/v5/latest/"
    echo "       └── Any existing checkpoints you want to resume from"
    echo ""
    echo "  NOT NEEDED (regenerated automatically):"
    echo "    ❌ data/dataset_index/ (generated from cache)"
    echo "    ❌ data/raw/ (original audio files)"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

show_usage() {
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  auto                     🚀 RECOMMENDED: Complete hands-off setup + training"
    echo "  overnight                🌙 Safe overnight training with cost protection"
    echo "  setup                    Just run setup (no training)"
    echo "  run-pipeline [modes...]  Run training pipeline (default: full V5 pipeline)"
    echo "  data-transfer            Show how to upload data to cloud"
    echo "  watchdog                 Start GPU idle watchdog"
    echo "  sync-checkpoints         Start checkpoint sync daemon"
    echo "  sync-once                Sync checkpoints once"
    echo "  cost-estimate            Show current and estimated costs"
    echo "  start-session            Create tmux session with all services"
    echo "  quickstart               Show quick start guide"
    echo "  shutdown [reason]        Manually trigger shutdown"
    echo "  cancel-shutdown          Cancel scheduled shutdown"
    echo "  status                   Show current training status and protections"
    echo ""
    echo "🌙 Overnight Protection (safe for unattended training):"
    echo "  MAX_COST_USD             Maximum cost before shutdown [default: 100]"
    echo "  MAX_RUNTIME_HOURS        Maximum hours before shutdown [default: 72]"
    echo "  CRASH_RECOVERY_ENABLED   Auto-retry on failure [default: true]"
    echo "  MAX_RETRIES              Max retries per phase [default: 3]"
    echo ""
    echo "Environment Variables:"
    echo "  CLOUD_PROVIDER           Cloud provider (lambda, aws, gcp) [default: lambda]"
    echo "  INSTANCE_HOURLY_RATE     Hourly rate in USD [default: 1.29]"
    echo "  AUTO_SHUTDOWN            Auto-shutdown when complete [default: true]"
    echo "  SHUTDOWN_DELAY_MINUTES   Minutes before shutdown [default: 5]"
    echo "  IDLE_SHUTDOWN_MINUTES    Shutdown after GPU idle [default: 30]"
    echo "  REMOTE_BACKUP_PATH       rsync/S3/GCS path for checkpoints"
    echo "  SYNC_INTERVAL_SECONDS    Checkpoint sync interval [default: 1800]"
    echo "  NTFY_TOPIC               ntfy.sh topic for notifications"
    echo "  SLACK_WEBHOOK_URL        Slack webhook for notifications"
    echo "  DISCORD_WEBHOOK_URL      Discord webhook for notifications"
    echo ""
    echo "Examples:"
    echo "  # EASIEST: Complete hands-off training"
    echo "  $0 auto"
    echo ""
    echo "  # SAFEST: Overnight training with \$80 cost cap"
    echo "  MAX_COST_USD=80 $0 overnight"
    echo ""
    echo "  # Full pipeline with auto-shutdown"
    echo "  $0 run-pipeline"
    echo ""
    echo "  # Just v5-full and multilabel"
    echo "  $0 run-pipeline v5-full multilabel-finetune"
    echo ""
    echo "  # Set up everything in tmux"
    echo "  export REMOTE_BACKUP_PATH='s3://my-bucket/beatsight/'"
    echo "  export NTFY_TOPIC='beatsight-training'"
    echo "  $0 start-session"
    echo ""
}

# Show overnight protection status
show_overnight_status() {
    local hours=$(get_instance_uptime_hours 2>/dev/null || echo "0")
    local cost=$(get_current_cost 2>/dev/null || echo "0.00")
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🛡️  Overnight Protection Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Current Status:"
    echo "    Uptime:        ${hours} hours / ${MAX_RUNTIME_HOURS} max"
    echo "    Cost:          \$${cost} / \$${MAX_COST_USD} max"
    echo ""
    echo "  Protection Settings:"
    echo "    Max Cost:      \$${MAX_COST_USD}"
    echo "    Max Runtime:   ${MAX_RUNTIME_HOURS} hours"
    echo "    Crash Recovery: ${CRASH_RECOVERY_ENABLED}"
    echo "    Max Retries:   ${MAX_RETRIES}"
    echo "    Idle Shutdown: ${IDLE_SHUTDOWN_MINUTES} minutes"
    echo ""
    
    if [ -f "$LAST_PHASE_FILE" ]; then
        local current_phase=$(cat "$LAST_PHASE_FILE" 2>/dev/null)
        echo "  Current Phase: $current_phase"
    fi
    
    if [ -f "$HEARTBEAT_FILE" ]; then
        local last_heartbeat=$(cat "$HEARTBEAT_FILE" 2>/dev/null)
        local now=$(date +%s)
        local heartbeat_age=$(( (now - last_heartbeat) / 60 ))
        echo "  Last Heartbeat: ${heartbeat_age} minutes ago"
    fi
    
    echo ""
}

# Run overnight mode with extra safety
run_overnight() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🌙 BeatSight OVERNIGHT Mode - Safe Unattended Training"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  ✅ Overnight Protection Features Enabled:"
    echo ""
    echo "    💰 Cost Protection:"
    echo "       Max cost before auto-shutdown: \$${MAX_COST_USD}"
    echo "       At \$${INSTANCE_HOURLY_RATE}/hr, this is ~$((MAX_COST_USD * 100 / ${INSTANCE_HOURLY_RATE%.*} / 100)) hours"
    echo ""
    echo "    ⏱️  Runtime Protection:"
    echo "       Max runtime: ${MAX_RUNTIME_HOURS} hours ($(echo "scale=1; ${MAX_RUNTIME_HOURS}/24" | bc 2>/dev/null || echo "${MAX_RUNTIME_HOURS}") days)"
    echo ""
    echo "    🔄 Crash Recovery:"
    echo "       Auto-retry on failure: ${CRASH_RECOVERY_ENABLED}"
    echo "       Max retries per phase: ${MAX_RETRIES}"
    echo "       Resume from interrupted phase: YES"
    echo ""
    echo "    🛑 Idle Protection:"
    echo "       GPU idle timeout: ${IDLE_SHUTDOWN_MINUTES} minutes"
    echo "       Stuck training detection: 30 minutes (via heartbeat)"
    echo ""
    echo "    📱 Notifications (if configured):"
    if [ -n "$NTFY_TOPIC" ]; then
        echo "       ntfy.sh topic: $NTFY_TOPIC ✅"
    else
        echo "       ntfy.sh: Not configured"
    fi
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        echo "       Slack webhook: Configured ✅"
    fi
    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        echo "       Discord webhook: Configured ✅"
    fi
    echo ""
    echo "    💾 Checkpoint Backup:"
    if [ -n "$REMOTE_BACKUP_PATH" ]; then
        echo "       Remote path: $REMOTE_BACKUP_PATH ✅"
        echo "       Sync interval: Every ${SYNC_INTERVAL_SECONDS} seconds"
    else
        echo "       ⚠️  REMOTE_BACKUP_PATH not set!"
        echo "       Checkpoints will be saved locally only."
        echo "       Set it to avoid losing work on errors:"
        echo "       export REMOTE_BACKUP_PATH='s3://bucket/path'"
    fi
    echo ""
    echo "  Press Ctrl+C now if you want to adjust settings."
    echo "  Starting in 10 seconds..."
    echo ""
    
    sleep 10
    
    # Run with all protections
    run_auto_full
}

case "${1:-}" in
    auto)
        run_auto_full
        ;;
    overnight)
        run_overnight
        ;;
    setup)
        full_auto_setup
        ;;
    data-transfer)
        show_data_transfer
        ;;
    run-pipeline)
        shift
        run_training_pipeline "$@"
        ;;
    watchdog)
        run_watchdog
        ;;
    sync-checkpoints)
        run_checkpoint_sync
        ;;
    sync-once)
        sync_checkpoints_once
        ;;
    cost-estimate)
        show_cost_estimate
        ;;
    start-session)
        setup_tmux_session
        ;;
    quickstart)
        show_quickstart
        ;;
    status)
        show_overnight_status
        ;;
    shutdown)
        shift
        shutdown_instance "${1:-Manual shutdown}"
        ;;
    cancel-shutdown)
        cancel_shutdown
        ;;
    *)
        show_usage
        ;;
esac
