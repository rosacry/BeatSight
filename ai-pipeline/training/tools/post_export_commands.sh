#!/usr/bin/env bash
# ============================================================================
# BeatSight Post-Export Training Checklist
# ============================================================================
# Run immediately after build_training_dataset.py completes to validate the
# dataset and begin training. Supports resumption on interruption.
#
# Usage:
#   bash ai-pipeline/training/tools/post_export_commands.sh
#
# Prerequisites:
#   - Python environment activated with ai-pipeline dependencies
#   - CUDA available for GPU training
#   - Optional: source beatsight_env.sh first to configure paths
#
# Hardware Profile: RTX 3080 Ti FE (12GB), Ryzen 9800X3D (8c/16t), 32GB DDR5-6000
#                   C: Samsung 990 Pro 2TB NVMe (7000/5100 MB/s) - feature_cache
#                   E: Seagate 2TB HDD (120 MB/s) - dataset
# ============================================================================

set -euo pipefail

# ============================================================================
# LOGGING & ERROR HANDLING
# ============================================================================
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
LOG_DIR="${BEATSIGHT_LOG_DIR:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*"
    if [ -n "$LOG_DIR" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*" >> "${LOG_DIR}/post_export_${TIMESTAMP}.log"
    fi
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2
    if [ -n "$LOG_DIR" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >> "${LOG_DIR}/post_export_${TIMESTAMP}.log"
    fi
}

log_success() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [✓] $*"
    if [ -n "$LOG_DIR" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $*" >> "${LOG_DIR}/post_export_${TIMESTAMP}.log"
    fi
}

cleanup_on_error() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Script failed with exit code $exit_code"
        log_error "Last checkpoint can be resumed with --resume-from flag"
    fi
}

trap cleanup_on_error EXIT

# ============================================================================
# ENVIRONMENT SETUP
# ============================================================================
if [ -z "${BEATSIGHT_REPO_ROOT:-}" ]; then
  if command -v git >/dev/null 2>&1; then
    BEATSIGHT_REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
  fi
  if [ -z "${BEATSIGHT_REPO_ROOT:-}" ]; then
    SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    BEATSIGHT_REPO_ROOT=$(cd "${SCRIPT_DIR}/../../.." && pwd)
  fi
fi

DATA_ROOT_DEFAULT=${DATA_ROOT_DEFAULT:-${BEATSIGHT_REPO_ROOT}/data}
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-$DATA_ROOT_DEFAULT}
# Dataset moved to HDD (E:/data) for space; feature cache stays on SSD for performance
BEATSIGHT_SECONDARY_ROOT=${BEATSIGHT_SECONDARY_ROOT:-/e/data}
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_SECONDARY_ROOT}/prod_combined_profile_run}
BEATSIGHT_CACHE_DIR=${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup}
BEATSIGHT_HEALTH_DIR=${BEATSIGHT_HEALTH_DIR:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/reports/health}
BEATSIGHT_METRICS_DIR=${BEATSIGHT_METRICS_DIR:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/reports/metrics}
BEATSIGHT_RUN_ROOT=${BEATSIGHT_RUN_ROOT:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs}
BEATSIGHT_RUN_WARMUP=${BEATSIGHT_RUN_WARMUP:-${BEATSIGHT_RUN_ROOT}/prod_combined_warmup}
BEATSIGHT_RUN_QUICK=${BEATSIGHT_RUN_QUICK:-${BEATSIGHT_RUN_ROOT}/prod_combined_quick}
BEATSIGHT_RUN_LONG=${BEATSIGHT_RUN_LONG:-${BEATSIGHT_RUN_ROOT}/prod_combined_longrun}
BEATSIGHT_WANDB_ROOT=${BEATSIGHT_WANDB_ROOT:-${BEATSIGHT_REPO_ROOT}/wandb}

export BEATSIGHT_REPO_ROOT BEATSIGHT_DATA_ROOT BEATSIGHT_DATASET_DIR \
       BEATSIGHT_CACHE_DIR BEATSIGHT_HEALTH_DIR BEATSIGHT_METRICS_DIR \
       BEATSIGHT_RUN_ROOT BEATSIGHT_RUN_WARMUP BEATSIGHT_RUN_QUICK \
       BEATSIGHT_RUN_LONG BEATSIGHT_WANDB_ROOT

cat <<EOF
# Resolved environment defaults (override via export before running commands):
#   BEATSIGHT_REPO_ROOT = ${BEATSIGHT_REPO_ROOT}
#   BEATSIGHT_DATA_ROOT = ${BEATSIGHT_DATA_ROOT}
#   BEATSIGHT_DATASET_DIR = ${BEATSIGHT_DATASET_DIR}
#   BEATSIGHT_CACHE_DIR = ${BEATSIGHT_CACHE_DIR}
#   BEATSIGHT_HEALTH_DIR = ${BEATSIGHT_HEALTH_DIR}
#   BEATSIGHT_METRICS_DIR = ${BEATSIGHT_METRICS_DIR}
#   BEATSIGHT_RUN_WARMUP = ${BEATSIGHT_RUN_WARMUP}
#   BEATSIGHT_RUN_QUICK  = ${BEATSIGHT_RUN_QUICK}
#   BEATSIGHT_RUN_LONG   = ${BEATSIGHT_RUN_LONG}
#   BEATSIGHT_WANDB_ROOT = ${BEATSIGHT_WANDB_ROOT}
#
# Source ai-pipeline/training/tools/beatsight_env.sh to populate these automatically,
# or copy the export lines above if you prefer to pin values manually before running the commands below.
EOF

# Print resolved environment for confirmation
echo "---------------------------------------------------"
echo "Environment Configuration:"
echo "  Repo Root:    ${BEATSIGHT_REPO_ROOT}"
echo "  Data Root:    ${BEATSIGHT_DATA_ROOT}"
echo "  Dataset:      ${BEATSIGHT_DATASET_DIR}"
echo "  Run Output:   ${BEATSIGHT_RUN_ROOT}"
echo "---------------------------------------------------"

# --- Functions ---

run_wandb_sync() {
    echo ">>> Syncing W&B..."
    wandb sync "${BEATSIGHT_WANDB_ROOT}"/offline-run-*/ || true
}

run_health_check() {
    echo ">>> Running Dataset Health Check..."
    # Extract manifest path from metadata
    MANIFEST_PATH=$(DATASET_DIR="${BEATSIGHT_DATASET_DIR}" python - <<'PY'
import json, os
from pathlib import Path
dataset = Path(os.environ["DATASET_DIR"])
metadata = dataset / "metadata.json"
with metadata.open("r", encoding="utf-8") as handle:
    data = json.load(handle)
manifest = data.get("manifest")
if not manifest:
    raise SystemExit('metadata.json missing "manifest" entry')
print(manifest)
PY
    )
    
    PYTHONPATH=ai-pipeline python ai-pipeline/training/dataset_health.py \
      --events "${MANIFEST_PATH}" \
      --dataset-metadata "${BEATSIGHT_DATASET_DIR}/metadata.json" \
      --components "${BEATSIGHT_DATASET_DIR}/components.json" \
      --output "${BEATSIGHT_HEALTH_DIR}/prod_combined_dataset_health.json" \
      --html-output "${BEATSIGHT_HEALTH_DIR}/prod_combined_dataset_health.html"
}

run_sanity_snapshot() {
    echo ">>> Running Sanity Snapshot..."
    DATASET_DIR="${BEATSIGHT_DATASET_DIR}" python - <<'PY'
import json, os
from pathlib import Path
dataset = Path(os.environ["DATASET_DIR"])
metadata = dataset / "metadata.json"
with metadata.open("r", encoding="utf-8") as handle:
    data = json.load(handle)
print(f"Total events processed: {data.get('total_events_processed')}")
print(f"Written clips: {data.get('statistics', {}).get('written_clips')}")
print(f"Missing audio: {data.get('statistics', {}).get('skipped_missing_audio')}")
print(f"Train clips: {data.get('statistics', {}).get('train_clips')}")
print(f"Val clips: {data.get('statistics', {}).get('val_clips')}")
PY
}

run_smoke_tests() {
    echo ">>> Running Smoke Tests..."
    pytest \
      ai-pipeline/tests/test_dataset_health.py \
      ai-pipeline/tests/test_drum_classifier.py \
      || { echo "pytest failures detected"; return 1; }
}

run_preflight_check() {
    echo ">>> Running Pre-flight Check (before expensive cloud training)..."
    echo ""
    echo "  This validates all Python scripts, imports, and model instantiation"
    echo "  to catch errors BEFORE you pay for Lambda Labs compute time."
    echo ""
    PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/preflight_check.py
}
run_precompute_cache() {
    echo ">>> Precomputing Feature Cache..."
    # Defaults tuned for 3080 Ti / 9800X3D on Windows.
    CACHE_BATCH_SIZE=${BEATSIGHT_CACHE_BATCH_SIZE:-96}
    CACHE_WORKERS=${BEATSIGHT_CACHE_WORKERS:-4}
    PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/precompute_feature_cache.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --splits train val \
      --batch-size "${CACHE_BATCH_SIZE}" \
      --num-workers "${CACHE_WORKERS}" \
      --persistent-workers \
      --sample-rate 44100 \
      --n-fft 2048 \
      --hop-length 512 \
      --n-mels 128 \
      --target-frames 128 \
      --cache-dtype float16
}

run_consolidate_cache() {
    echo ">>> Consolidating Feature Cache (100x training speedup)..."
    echo ""
    echo "  This converts 16M individual .pt files into ~256 memory-mapped shards."
    echo ""
    echo "  Benefits:"
    echo "    • 100x faster training (eliminates syscall overhead)"
    echo "    • Memory-mapped for zero-copy tensor access"
    echo "    • OS-level page caching (hot data stays in RAM)"
    echo ""
    
    # Determine input/output paths
    CACHE_PARENT=$(dirname "${BEATSIGHT_CACHE_DIR}")
    CACHE_NAME=$(basename "${BEATSIGHT_CACHE_DIR}")
    CONSOLIDATED_CACHE_DIR="${CACHE_PARENT}/${CACHE_NAME}_consolidated"
    
    echo "  Input:  ${BEATSIGHT_CACHE_DIR}"
    echo "  Output: ${CONSOLIDATED_CACHE_DIR}"
    echo ""
    echo "  ⚡ IN-PLACE MODE: Deletes source .pt files after each shard"
    echo "     Peak storage overhead: ~8 GB (instead of ~500 GB)"
    echo ""
    
    # Check for existing partial conversion
    RESUME_FLAG=""
    if [[ -f "${CONSOLIDATED_CACHE_DIR}/train/index.json" ]] || [[ -f "${CONSOLIDATED_CACHE_DIR}/val/index.json" ]]; then
        echo "  📋 Found existing partial conversion!"
        echo ""
        read -p "  Resume previous conversion? [Y/n]: " resume_confirm
        case "${resume_confirm,,}" in
            n|no)
                echo "  → Starting fresh (will overwrite existing shards)"
                ;;
            *)
                RESUME_FLAG="--resume"
                echo "  → Resuming from checkpoint"
                ;;
        esac
        echo ""
    fi
    
    read -p "  Proceed with in-place consolidation? [Y/n]: " confirm
    case "${confirm,,}" in
        n|no)
            echo "  → Cancelled."
            return 0
            ;;
    esac
    
    # Run in-place consolidation for train and val splits
    # Uses 4 workers to limit peak storage overhead
    if [[ -n "${RESUME_FLAG}" ]]; then
        PYTHONPATH=ai-pipeline python -m training.utils.consolidated_cache convert-inplace \
          --input-dir "${BEATSIGHT_CACHE_DIR}" \
          --output-dir "${CONSOLIDATED_CACHE_DIR}" \
          --split train \
          --split val \
          --workers 4 \
          --dtype float16 \
          ${RESUME_FLAG}
    else
        PYTHONPATH=ai-pipeline python -m training.utils.consolidated_cache convert-inplace \
          --input-dir "${BEATSIGHT_CACHE_DIR}" \
          --output-dir "${CONSOLIDATED_CACHE_DIR}" \
          --split train \
          --split val \
          --workers 4 \
          --dtype float16 <<< "y"
    fi
    
    echo ""
    echo "  ✅ Consolidation complete!"
    echo ""
    echo "  The training pipeline will automatically detect and use the consolidated cache."
    echo "  Empty directories can be cleaned up with:"
    echo "    find ${BEATSIGHT_CACHE_DIR} -type d -empty -delete"
    echo ""
}

run_validate_cache() {
    echo ">>> Validating Consolidated Feature Cache..."
    echo ""
    
    # Determine consolidated cache path
    CACHE_PARENT=$(dirname "${BEATSIGHT_CACHE_DIR}")
    CACHE_NAME=$(basename "${BEATSIGHT_CACHE_DIR}")
    CONSOLIDATED_CACHE_DIR="${CACHE_PARENT}/${CACHE_NAME}_consolidated"
    
    if [[ ! -d "${CONSOLIDATED_CACHE_DIR}" ]]; then
        echo "  ❌ Consolidated cache not found: ${CONSOLIDATED_CACHE_DIR}"
        echo "  Run option 4c first to consolidate the cache."
        return 1
    fi
    
    echo "  Cache: ${CONSOLIDATED_CACHE_DIR}"
    echo ""
    
    read -p "  Also attempt to repair corrupted shards? [y/N]: " repair_confirm
    REPAIR_FLAG=""
    case "${repair_confirm,,}" in
        y|yes)
            REPAIR_FLAG="--repair"
            ;;
    esac
    
    PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/validate_consolidated_cache.py \
      --cache-dir "${CONSOLIDATED_CACHE_DIR}" \
      --split both \
      --json "${BEATSIGHT_HEALTH_DIR}/cache_validation.json" \
      $REPAIR_FLAG
    
    echo ""
    echo "  Validation results saved to: ${BEATSIGHT_HEALTH_DIR}/cache_validation.json"
    echo ""
}

run_convert_index_binary() {
    echo ">>> Converting Cache Index to Binary Format (10x faster loading)..."
    echo ""
    
    # Determine consolidated cache path
    CACHE_PARENT=$(dirname "${BEATSIGHT_CACHE_DIR}")
    CACHE_NAME=$(basename "${BEATSIGHT_CACHE_DIR}")
    CONSOLIDATED_CACHE_DIR="${CACHE_PARENT}/${CACHE_NAME}_consolidated"
    
    if [[ ! -d "${CONSOLIDATED_CACHE_DIR}" ]]; then
        echo "  ❌ Consolidated cache not found: ${CONSOLIDATED_CACHE_DIR}"
        echo "  Run option 4c first to consolidate the cache."
        return 1
    fi
    
    echo "  Cache: ${CONSOLIDATED_CACHE_DIR}"
    echo ""
    echo "  This converts index.json (~1GB) to index.npz (~400MB) for 10x faster loading."
    echo "  This is critical for training speed on Windows - each worker must load the index."
    echo ""
    
    for split in train val; do
        split_dir="${CONSOLIDATED_CACHE_DIR}/${split}"
        if [[ -f "${split_dir}/index.json" ]]; then
            echo "  Converting ${split} index..."
            PYTHONPATH=ai-pipeline python -m training.utils.consolidated_cache convert-index \
              --cache-dir "${split_dir}" <<< "y"
            echo ""
        else
            echo "  ⚠️  No index.json found for ${split} split"
        fi
    done
    
    echo "  ✅ Index conversion complete!"
    echo "  Training will now use binary index automatically (10x faster worker startup)"
    echo ""
}

run_generate_cache_mapping() {
    echo ">>> Generating Cache Index Mapping (O(1) lookup, 50x faster training!)..."
    echo ""
    
    # Determine paths
    CACHE_PARENT=$(dirname "${BEATSIGHT_CACHE_DIR}")
    CACHE_NAME=$(basename "${BEATSIGHT_CACHE_DIR}")
    CONSOLIDATED_CACHE_DIR="${CACHE_PARENT}/${CACHE_NAME}_consolidated"
    LABELS_DIR="${BEATSIGHT_DATA_ROOT}/dataset_index"
    
    if [[ ! -d "${CONSOLIDATED_CACHE_DIR}" ]]; then
        echo "  ❌ Consolidated cache not found: ${CONSOLIDATED_CACHE_DIR}"
        echo "  Run option 4c first to consolidate the cache."
        return 1
    fi
    
    echo "  This generates a direct mapping from sample index to cache (shard, offset)."
    echo ""
    echo "  Benefits:"
    echo "    • Eliminates O(log n) binary search on 14M entries"
    echo "    • Reduces first-epoch time by 50x or more"
    echo "    • No string encoding/comparison overhead"
    echo ""
    echo "  Cache: ${CONSOLIDATED_CACHE_DIR}"
    echo "  Labels: ${LABELS_DIR}"
    echo ""
    
    # Generate for train
    TRAIN_FILES="${LABELS_DIR}/train_labels_with_velocity_files.npy"
    if [[ -f "${TRAIN_FILES}" ]]; then
        echo "  📄 Generating train mapping..."
        python tools/generate_cache_index_mapping.py \
          --labels "${TRAIN_FILES}" \
          --cache "${CONSOLIDATED_CACHE_DIR}/train" \
          --output "${LABELS_DIR}/train_cache_mapping.npz"
        echo ""
    else
        echo "  ⚠️  Train labels not found: ${TRAIN_FILES}"
        echo "  Run option 4n first to convert labels to numpy format."
    fi
    
    # Generate for val
    VAL_FILES="${LABELS_DIR}/val_labels_with_velocity_files.npy"
    if [[ -f "${VAL_FILES}" ]]; then
        echo "  📄 Generating val mapping..."
        python tools/generate_cache_index_mapping.py \
          --labels "${VAL_FILES}" \
          --cache "${CONSOLIDATED_CACHE_DIR}/val" \
          --output "${LABELS_DIR}/val_cache_mapping.npz"
        echo ""
    else
        echo "  ⚠️  Val labels not found: ${VAL_FILES}"
    fi
    
    echo "  ✅ Cache mapping generation complete!"
    echo "  Training will now automatically use O(1) lookups (50x faster first epoch)"
    echo ""
}

run_convert_labels_numpy() {
    echo ">>> Converting Labels to NumPy Format (10x faster, 90% less RAM)..."
    echo ""
    echo "  This converts large JSON label files (~5GB) to memory-efficient numpy format."
    echo "  Benefits:"
    echo "    • 10x smaller file size"
    echo "    • 90% less RAM usage during training"
    echo "    • Eliminates MemoryError on Windows multiprocessing"
    echo "    • Faster worker spawn time"
    echo ""
    echo "  Dataset: ${BEATSIGHT_DATASET_DIR}"
    echo ""
    
    # Check which velocity label files exist
    TRAIN_LABELS=""
    VAL_LABELS=""
    
    if [[ -f "${BEATSIGHT_DATASET_DIR}/train/train_labels_with_velocity.json" ]]; then
        TRAIN_LABELS="${BEATSIGHT_DATASET_DIR}/train/train_labels_with_velocity.json"
        echo "  Train labels: train_labels_with_velocity.json"
    elif [[ -f "${BEATSIGHT_DATASET_DIR}/train/train_labels.json" ]]; then
        TRAIN_LABELS="${BEATSIGHT_DATASET_DIR}/train/train_labels.json"
        echo "  Train labels: train_labels.json"
    else
        echo "  ❌ No train labels found!"
        return 1
    fi
    
    if [[ -f "${BEATSIGHT_DATASET_DIR}/val/val_labels_with_velocity.json" ]]; then
        VAL_LABELS="${BEATSIGHT_DATASET_DIR}/val/val_labels_with_velocity.json"
        echo "  Val labels: val_labels_with_velocity.json"
    elif [[ -f "${BEATSIGHT_DATASET_DIR}/val/val_labels.json" ]]; then
        VAL_LABELS="${BEATSIGHT_DATASET_DIR}/val/val_labels.json"
        echo "  Val labels: val_labels.json"
    else
        echo "  ❌ No val labels found!"
        return 1
    fi
    
    # Check if numpy files already exist
    TRAIN_NPY="${TRAIN_LABELS%.json}_labels.npy"
    VAL_NPY="${VAL_LABELS%.json}_labels.npy"
    
    if [[ -f "${TRAIN_NPY}" ]]; then
        echo ""
        echo "  ⚠️  Train numpy files already exist!"
        read -p "  Overwrite? [y/N]: " overwrite_train
        case "${overwrite_train,,}" in
            y|yes)
                ;;
            *)
                TRAIN_LABELS=""
                echo "  → Skipping train labels"
                ;;
        esac
    fi
    
    if [[ -f "${VAL_NPY}" ]]; then
        echo ""
        echo "  ⚠️  Val numpy files already exist!"
        read -p "  Overwrite? [y/N]: " overwrite_val
        case "${overwrite_val,,}" in
            y|yes)
                ;;
            *)
                VAL_LABELS=""
                echo "  → Skipping val labels"
                ;;
        esac
    fi
    
    if [[ -z "${TRAIN_LABELS}" && -z "${VAL_LABELS}" ]]; then
        echo ""
        echo "  Nothing to convert."
        return 0
    fi
    
    echo ""
    read -p "  Proceed with conversion? [Y/n]: " confirm
    case "${confirm,,}" in
        n|no)
            echo "  → Cancelled."
            return 0
            ;;
    esac
    
    echo ""
    
    if [[ -n "${TRAIN_LABELS}" ]]; then
        echo "============================================================"
        echo "Converting train labels..."
        echo "============================================================"
        python tools/convert_labels_to_numpy.py "${TRAIN_LABELS}"
        echo ""
    fi
    
    if [[ -n "${VAL_LABELS}" ]]; then
        echo "============================================================"
        echo "Converting val labels..."
        echo "============================================================"
        python tools/convert_labels_to_numpy.py "${VAL_LABELS}"
        echo ""
    fi
    
    echo "  ✅ Conversion complete!"
    echo ""
    echo "  The training pipeline will automatically detect and use numpy labels."
    echo "  Original JSON files are preserved as backup."
    echo ""
}

run_rebuild_cache() {
    echo ">>> Full Cache Rebuild (4 + 4c combined)..."
    echo ""
    echo "  This runs both steps in sequence:"
    echo "    1. Precompute Feature Cache (raw audio → .pt files)"
    echo "    2. Consolidate Cache (.pt files → memory-mapped shards)"
    echo ""
    echo "  Use this when:"
    echo "    • Starting with a new dataset"
    echo "    • Rebuilding from scratch after changes"
    echo ""
    
    read -p "  Proceed with full cache rebuild? [y/N]: " confirm
    case "${confirm,,}" in
        y|yes)
            echo ""
            echo "============================================================"
            echo "Step 1/2: Precomputing Feature Cache..."
            echo "============================================================"
            run_precompute_cache
            
            echo ""
            echo "============================================================"
            echo "Step 2/2: Consolidating Cache..."
            echo "============================================================"
            # Run consolidation non-interactively (already confirmed above)
            CACHE_PARENT=$(dirname "${BEATSIGHT_CACHE_DIR}")
            CACHE_NAME=$(basename "${BEATSIGHT_CACHE_DIR}")
            CONSOLIDATED_CACHE_DIR="${CACHE_PARENT}/${CACHE_NAME}_consolidated"
            
            PYTHONPATH=ai-pipeline python -m training.utils.consolidated_cache convert-inplace \
              --input-dir "${BEATSIGHT_CACHE_DIR}" \
              --output-dir "${CONSOLIDATED_CACHE_DIR}" \
              --split train \
              --split val \
              --workers 4 \
              --dtype float16 <<< "y"
            
            echo ""
            echo "  ✅ Full cache rebuild complete!"
            echo "  Empty directories can be cleaned up with:"
            echo "    find ${BEATSIGHT_CACHE_DIR} -type d -empty -delete"
            ;;
        *)
            echo "  → Cancelled."
            return 0
            ;;
    esac
}

# Prompt user for resume vs fresh start for training runs
prompt_training_mode() {
    local run_name="$1"
    local checkpoint_dir="$2"
    local latest_checkpoint="${checkpoint_dir}/checkpoints/latest_checkpoint.pth"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Training: ${run_name}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if checkpoint exists
    if [ -f "$latest_checkpoint" ]; then
        echo "  ✓ Found existing checkpoint: ${latest_checkpoint}"
        echo ""
        echo "  Options:"
        echo "    [R] Resume from checkpoint (continue where you left off)"
        echo "    [F] Fresh start (delete old checkpoints, use improved settings)"
        echo "    [C] Cancel (go back to menu)"
        echo ""
        read -p "  Choose [R/F/C]: " mode_choice
        
        case "${mode_choice,,}" in  # lowercase
            r|resume)
                echo "  → Resuming from checkpoint..."
                TRAINING_MODE="resume"
                RESUME_FLAG="--resume-from ${latest_checkpoint}"
                # Don't use new experimental settings when resuming
                CLASS_WEIGHTS_FLAG=""
                LABEL_SMOOTHING_FLAG=""
                ;;
            f|fresh)
                echo "  → Starting fresh with improved settings..."
                echo "  ⚠ Removing old checkpoints in ${checkpoint_dir}..."
                rm -rf "${checkpoint_dir}/checkpoints" 2>/dev/null || true
                rm -f "${checkpoint_dir}/best_drum_classifier.pth" 2>/dev/null || true
                TRAINING_MODE="fresh"
                RESUME_FLAG=""
                # Use improved settings for fresh runs
                # 'effective' strategy handles extreme class imbalance (2M:1 ratio)
                # max-class-weight caps extreme weights to prevent instability
                CLASS_WEIGHTS_FLAG="--class-weights effective --max-class-weight 10.0"
                LABEL_SMOOTHING_FLAG="--label-smoothing 0.05"
                ;;
            c|cancel)
                echo "  → Cancelled."
                return 1
                ;;
            *)
                echo "  → Invalid choice. Cancelled."
                return 1
                ;;
        esac
    else
        echo "  ℹ No existing checkpoint found. Starting fresh."
        echo ""
        echo "  Options:"
        echo "    [S] Start training (with improved settings)"
        echo "    [C] Cancel (go back to menu)"
        echo ""
        read -p "  Choose [S/C]: " mode_choice
        
        case "${mode_choice,,}" in
            s|start)
                TRAINING_MODE="fresh"
                RESUME_FLAG=""
                # Use improved settings for fresh runs
                # 'effective' strategy handles extreme class imbalance (2M:1 ratio)
                CLASS_WEIGHTS_FLAG="--class-weights effective --max-class-weight 10.0"
                LABEL_SMOOTHING_FLAG="--label-smoothing 0.05"
                ;;
            c|cancel)
                echo "  → Cancelled."
                return 1
                ;;
            *)
                echo "  → Invalid choice. Cancelled."
                return 1
                ;;
        esac
    fi
    
    echo ""
    if [ -n "$CLASS_WEIGHTS_FLAG" ]; then
        echo "  📊 Using improved settings:"
        echo "     • Class weights: effective (handles extreme class imbalance)"
        echo "     • Weight cap: 10.0 (prevents training instability)"
        echo "     • Label smoothing: 0.05 (reduces overfitting)"
    else
        echo "  📊 Using original settings (to match existing checkpoint)"
    fi
    echo ""
    
    return 0
}

run_train_warmup() {
    echo ">>> Warmup Training Configuration..."
    
    if ! prompt_training_mode "Warmup Probe" "${BEATSIGHT_RUN_WARMUP}"; then
        return 0
    fi
    
    echo ">>> Starting Warmup Training..."
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
      --wandb-tags prod_combined_24class richer_subset warmup \
      --wandb-run-name prod_combined_warmup_probe_$(date +%Y%m%d) \
      --grad-accum-steps 1 \
      ${CLASS_WEIGHTS_FLAG:-} \
      ${LABEL_SMOOTHING_FLAG:-} \
      ${RESUME_FLAG:-}
}

run_train_quick() {
    echo ">>> Quick Refresh Training Configuration..."
    
    if ! prompt_training_mode "Quick Refresh" "${BEATSIGHT_RUN_QUICK}"; then
        return 0
    fi
    
    echo ">>> Starting Quick Refresh Training..."
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
      --wandb-tags prod_combined_24class quick_refresh cached \
      --wandb-run-name prod_combined_quick_refresh_$(date +%Y%m%d) \
      ${CLASS_WEIGHTS_FLAG:-} \
      ${LABEL_SMOOTHING_FLAG:-} \
      ${RESUME_FLAG:-}
}

run_train_long() {
    echo ">>> Long Run Training Configuration..."
    
    if ! prompt_training_mode "Long Run" "${BEATSIGHT_RUN_LONG}"; then
        return 0
    fi
    
    # For long run, if resuming we use the warmup checkpoint, otherwise fresh start
    if [ "$TRAINING_MODE" = "resume" ]; then
        # Check if long run has its own checkpoint first
        if [ -f "${BEATSIGHT_RUN_LONG}/checkpoints/latest_checkpoint.pth" ]; then
            RESUME_FLAG="--resume-from ${BEATSIGHT_RUN_LONG}/checkpoints/latest_checkpoint.pth"
        else
            # Fall back to warmup checkpoint
            RESUME_FLAG="--resume-from ${BEATSIGHT_RUN_WARMUP}/checkpoints/latest_checkpoint.pth"
        fi
    fi
    
    echo ">>> Starting Long Run Training..."
    export WANDB_RUN_GROUP=prod_combined_longrun_lr28e5
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
      --wandb-mode offline \
      --wandb-tags prod_combined_24class full_corpus longrun lr28e5 richer_split \
      --wandb-run-name prod_combined_longrun_lr28e5_$(date +%Y%m%d) \
      ${CLASS_WEIGHTS_FLAG:-} \
      ${LABEL_SMOOTHING_FLAG:-} \
      ${RESUME_FLAG:-}
}

run_eval() {
    echo ">>> Running Evaluation..."
    PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/evaluate_classifier.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --checkpoint "${BEATSIGHT_RUN_WARMUP}/best_drum_classifier.pth" \
      --device cuda \
      --num-workers 2 \
      --prefetch-factor 1 \
      --pin-memory \
      --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --subset-seed 42 \
      --output-json "${BEATSIGHT_METRICS_DIR}/prod_combined_warmup_eval.json" \
      --misclassified-report "${BEATSIGHT_METRICS_DIR}/prod_combined_warmup_misclassified.json" \
      --max-misclassified 200 \
      --confusion-matrix "${BEATSIGHT_METRICS_DIR}/prod_combined_warmup_confusion.npy" \
      --progress
}

run_analysis() {
    echo ">>> Running Analysis..."
    PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/analyze_classifier.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --model-path "${BEATSIGHT_RUN_WARMUP}/best_drum_classifier.pth" \
      --cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --output-dir "${BEATSIGHT_METRICS_DIR}/../analysis/prod_combined_warmup" \
      --channels-last \
      --topk-misclassified 100
}

# ============================================================================
# CUTTING-EDGE TRAINING (v2 model + Mixup/CutMix)
# ============================================================================
# These use the latest improvements:
#   - v2 model with Squeeze-Excitation attention blocks
#   - Mixup data augmentation (blends samples for regularization)
#   - CutMix augmentation (patches samples together)
#   - Effective class weighting + label smoothing

BEATSIGHT_RUN_CUTTING_EDGE="${BEATSIGHT_RUN_ROOT}/cutting_edge"

# Common cutting-edge flags (v2 model + ALL revolutionary features + Progressive + SAM + SWA + R-Drop + Curriculum + Calibration)
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

# ============================================================================
# V5 ULTIMATE FLAGS (2024 - All innovations in single model)
# ============================================================================
# v5 model combines: CoordAttn + DropPath + DeepSupervision + MultiScale + GradCentralization
# SINGLE-TIER STRATEGY: Use V5-Large for maximum quality, INT8 quantization for speed
# This gives best accuracy while maintaining fast inference via quantization
V5_MODEL_FLAGS="--model-version v5 --v5-size large --drop-path-rate 0.15"
V5_DEEP_SUPERVISION_FLAGS="--use-deep-supervision --deep-supervision-weights 0.4,0.6"
V5_GRADIENT_CENTRALIZATION_FLAGS="--use-gradient-centralization"
# Multi-task learning: velocity + hi-hat openness auxiliary heads (improves feature learning)
# Uses velocity-enriched labels: train_labels_with_velocity.json, val_labels_with_velocity.json
# NOTE: velocity-weight boosted to 0.4 for improved ghost note/accent detection (was 0.3)
# Higher weight teaches model to better distinguish dynamics (ghost vs tap vs accent)
V5_MULTI_TASK_FLAGS="--use-multi-task --velocity-labels-suffix _with_velocity --velocity-weight 0.4"
# Ghost note augmentation: synthesizes ghost notes from normal hits for +5-15% ghost detection
# Using "aggressive" preset: higher probability, more bleed simulation, harder examples
# Also add accent_tap secondary augmentation for accent-tap sticking pattern detection
V5_GHOST_AUGMENT_FLAGS="--ghost-augment --ghost-augment-preset aggressive --ghost-augment-prob 0.25"
# Waveform augmentation: audio-level time stretch, pitch shift, gain variation (+1-2%)
# NOTE: Ghost augment already bypasses cache, so this adds minimal extra I/O cost
V5_WAVEFORM_AUGMENT_FLAGS="--waveform-augment drum"

# BEATs Model Flags (Microsoft's Audio Foundation Model)
BEATS_MODEL_FLAGS="--model-version beats --beats-freeze-encoder --beats-layer-decay 0.75"
BEATS_FINETUNE_FLAGS="--model-version beats --beats-layer-decay 0.75"

run_train_cutting_edge_warmup() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🚀 CUTTING-EDGE WARMUP (v2 + ALL Revolutionary Features)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Features enabled:"
    echo "    ✓ v2 model with Squeeze-Excitation attention (~406K params)"
    echo "    ✓ Progressive augmentation (starts weak, ramps up)"
    echo "    ✓ Mixup augmentation (α=0.3) - blends samples"
    echo "    ✓ CutMix augmentation (α=1.0) - patches samples"
    echo "    ✓ SpecAugment (drum preset) - time/freq masking"
    echo "    ✓ Focal Loss (γ=2.0) - focuses on hard examples"
    echo "    ✓ EMA (decay=0.999) - smoother final weights"
    echo "    ✓ SAM optimizer (ρ=0.05) - seeks flat minima"
    echo "    ✓ SWA (start=75%) - weight averaging"
    echo "    ✓ Effective class weighting + label smoothing (0.1)"
    echo ""
    echo "  Expected improvement: 8-18% over baseline v1"
    echo "  Duration: ~45-60 minutes (8 epochs)"
    echo ""
    
    local output_dir="${BEATSIGHT_RUN_CUTTING_EDGE}/warmup"
    mkdir -p "$output_dir"
    
    echo ">>> Starting Cutting-Edge Warmup Training..."
    PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --epochs 8 \
      --warmup-epochs 2 \
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
      --output "$output_dir" \
      --metrics-json "${BEATSIGHT_METRICS_DIR}/cutting_edge_warmup.json" \
      --wandb-project beatsight-classifier \
      --wandb-mode offline \
      --wandb-tags cutting_edge v2_model mixup specaugment focal ema sam swa rdrop curriculum calibration warmup \
      --wandb-run-name "cutting_edge_warmup_$(date +%Y%m%d_%H%M)" \
      --class-weights effective \
      --max-class-weight 10.0 \
      ${CUTTING_EDGE_MODEL_FLAGS} \
      ${CUTTING_EDGE_MIXUP_FLAGS} \
      ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
      ${CUTTING_EDGE_FOCAL_FLAGS} \
      ${CUTTING_EDGE_EMA_FLAGS} \
      ${CUTTING_EDGE_PROGRESSIVE_FLAGS} \
      ${CUTTING_EDGE_SAM_FLAGS} \
      ${CUTTING_EDGE_SWA_FLAGS} \
      ${CUTTING_EDGE_REGULARIZATION_FLAGS} \
      ${CUTTING_EDGE_RDROP_FLAGS} \
      ${CUTTING_EDGE_CURRICULUM_FLAGS} \
      ${CUTTING_EDGE_CALIBRATION_FLAGS}
}

run_train_cutting_edge_quick() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🚀 CUTTING-EDGE QUICK (v2 + ALL Revolutionary Features)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Duration: ~2-3 hours (60 epochs)"
    echo ""
    
    local output_dir="${BEATSIGHT_RUN_CUTTING_EDGE}/quick"
    mkdir -p "$output_dir"
    
    echo ">>> Starting Cutting-Edge Quick Training..."
    PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --epochs 60 \
      --warmup-epochs 5 \
      --scheduler cosine \
      --min-lr 0.00001 \
      --batch-size 128 \
      --lr 0.0005 \
      --device cuda \
      --val-fraction 0.2 \
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
      --output "$output_dir" \
      --metrics-json "${BEATSIGHT_METRICS_DIR}/cutting_edge_quick.json" \
      --wandb-project beatsight-classifier \
      --wandb-mode offline \
      --wandb-tags cutting_edge v2_model mixup specaugment focal ema sam swa rdrop curriculum calibration quick \
      --wandb-run-name "cutting_edge_quick_$(date +%Y%m%d_%H%M)" \
      --class-weights effective \
      --max-class-weight 10.0 \
      ${CUTTING_EDGE_MODEL_FLAGS} \
      ${CUTTING_EDGE_MIXUP_FLAGS} \
      ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
      ${CUTTING_EDGE_FOCAL_FLAGS} \
      ${CUTTING_EDGE_EMA_FLAGS} \
      ${CUTTING_EDGE_PROGRESSIVE_FLAGS} \
      ${CUTTING_EDGE_SAM_FLAGS} \
      ${CUTTING_EDGE_SWA_FLAGS} \
      ${CUTTING_EDGE_REGULARIZATION_FLAGS} \
      ${CUTTING_EDGE_RDROP_FLAGS} \
      ${CUTTING_EDGE_CURRICULUM_FLAGS} \
      ${CUTTING_EDGE_CALIBRATION_FLAGS}
}

run_train_cutting_edge_long() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🚀 CUTTING-EDGE LONG (v2 + ALL Revolutionary Features)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Duration: ~10-14 hours (220 epochs)"
    echo ""
    
    local output_dir="${BEATSIGHT_RUN_CUTTING_EDGE}/long"
    mkdir -p "$output_dir"
    
    echo ">>> Starting Cutting-Edge Long Training..."
    PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --epochs 220 \
      --warmup-epochs 10 \
      --scheduler cosine \
      --min-lr 0.00001 \
      --batch-size 128 \
      --lr 0.0005 \
      --device cuda \
      --train-fraction 1.0 \
      --val-fraction 0.3 \
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
      --checkpoint-every 20 \
      --checkpoint-every-batches 25000 \
      --output "$output_dir" \
      --metrics-json "${BEATSIGHT_METRICS_DIR}/cutting_edge_long.json" \
      --wandb-project beatsight-classifier \
      --wandb-mode offline \
      --wandb-tags cutting_edge v2_model mixup specaugment focal ema sam swa rdrop curriculum calibration long \
      --wandb-run-name "cutting_edge_long_$(date +%Y%m%d_%H%M)" \
      --class-weights effective \
      --max-class-weight 10.0 \
      ${CUTTING_EDGE_MODEL_FLAGS} \
      ${CUTTING_EDGE_MIXUP_FLAGS} \
      ${CUTTING_EDGE_SPECAUGMENT_FLAGS} \
      ${CUTTING_EDGE_FOCAL_FLAGS} \
      ${CUTTING_EDGE_EMA_FLAGS} \
      ${CUTTING_EDGE_PROGRESSIVE_FLAGS} \
      ${CUTTING_EDGE_SAM_FLAGS} \
      ${CUTTING_EDGE_SWA_FLAGS} \
      ${CUTTING_EDGE_REGULARIZATION_FLAGS} \
      ${CUTTING_EDGE_RDROP_FLAGS} \
      ${CUTTING_EDGE_CURRICULUM_FLAGS} \
      ${CUTTING_EDGE_CALIBRATION_FLAGS}
}

# --- Auto-Training Functions (run until complete, auto-resume on crash) ---

generate_multilabel_dataset() {
    local script="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/tools/generate_multilabel_dataset.py"
    local output_dir="${BEATSIGHT_OUTPUT_ROOT:-E:/data}/multilabel_dataset"
    
    if [ ! -f "$script" ]; then
        echo "ERROR: generate_multilabel_dataset.py not found at ${script}"
        return 1
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🥁 GENERATE MULTI-LABEL DATASET"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  This creates training data for simultaneous drum detection!"
    echo ""
    echo "  Sources (MIDI-aligned only):"
    echo "    • groove_mididataset (278MB) - studio recordings"
    echo "    • egmd (9.6GB) - electronic drum MIDI"
    echo "    • slakh2100 (1.8GB) - multi-track MIDI"
    echo "    • enst_drums (28MB) - studio recordings"
    echo ""
    echo "  Expected output: ~500K+ events, ~40% multi-label"
    echo "  Output: ${output_dir}"
    echo ""
    echo "  Time estimate: ~10-15 minutes"
    echo ""
    read -p "  Generate multi-label dataset? [Y/n]: " confirm
    
    case "${confirm,,}" in
        n|no)
            echo "  → Cancelled."
            return 0
            ;;
    esac
    
    mkdir -p "${output_dir}"
    
    # Full generation (all MIDI sources)
    python "$script" \
        --sources groove_mididataset egmd slakh2100 enst_drums \
        --output "${output_dir}/multilabel_events.jsonl" \
        --verbose
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "  ✅ Multi-label dataset generated successfully!"
        echo "  📁 Output: ${output_dir}"
        echo ""
        echo "  Next step: Run 19c) Multi-Label: Finetune"
    else
        echo ""
        echo "  ❌ Dataset generation failed. Check the error above."
        return 1
    fi
}

run_auto_train() {
    local mode="$1"
    local script="${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/tools/auto_train.sh"
    
    if [ ! -f "$script" ]; then
        echo "ERROR: auto_train.sh not found at ${script}"
        return 1
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🤖 AUTO-TRAINING MODE: ${mode}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  This will run training until COMPLETE, automatically restarting on ANY crash."
    echo "  Perfect for overnight runs or while you're away."
    echo ""
    echo "  Features:"
    echo "    ✓ Automatic resume from latest checkpoint on crash"
    echo "    ✓ Checkpoints saved every 25,000 batches (mid-epoch protection)"
    echo "    ✓ Wandb runs offline (no network-related crashes)"
    echo "    ✓ 30-second delay between retries (handles temp issues)"
    echo "    ✓ Desktop notification when complete (Windows toast)"
    echo "    ✓ Detailed logs in logs/auto_train/"
    echo ""
    echo "  Press Ctrl+C to stop (training can be resumed later)"
    echo ""
    read -p "  Start auto-training? [Y/n]: " confirm
    
    case "${confirm,,}" in
        n|no)
            echo "  → Cancelled."
            return 0
            ;;
    esac
    
    bash "$script" "$mode"
}

# --- Legacy Training Menu (archived paths) ---

show_legacy_menu() {
    while true; do
        echo
        echo "┌─────────────────────────────────────────────────────────────────────┐"
        echo "│  LEGACY TRAINING MODES (for experimentation/research)              │"
        echo "│  See docs/archive/CUTTING_EDGE_TRAINING_FEATURES_FULL.md          │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  BASELINE (v1):                                                    │"
        echo "│   5a) Train: Warmup Probe                                          │"
        echo "│   5b) Train: Quick Refresh                                         │"
        echo "│   5c) Train: Long Run                                              │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  CUTTING-EDGE (v2 + Mixup):                                        │"
        echo "│   7a) Cutting-Edge: Warmup (~1hr)                                  │"
        echo "│   7b) Cutting-Edge: Quick  (~3hr)                                  │"
        echo "│   7c) Cutting-Edge: Long   (~12hr)                                 │"
        echo "│   8a-c) Auto-Train Cutting-Edge (unattended)                       │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  ENSEMBLE:                                                         │"
        echo "│   9a) Ensemble: Warmup (5 models, ~5hr)                            │"
        echo "│   9b) Ensemble: Quick  (5 models, ~15hr)                           │"
        echo "│   9c) Ensemble: Long   (5 models, ~60hr)                           │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  TRANSFORMER:                                                      │"
        echo "│   10a) AST: Warmup (~1hr)                                          │"
        echo "│   10b) AST: Quick  (~3hr)                                          │"
        echo "│   10c) AST: Long   (~12hr)                                         │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  DISTILLATION:                                                     │"
        echo "│   11a) Distill: Quick (~2hr)                                       │"
        echo "│   11b) Distill: Long  (~8hr)                                       │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  ENHANCED v4:                                                      │"
        echo "│   12a) Enhanced: Warmup (~2hr)                                     │"
        echo "│   12b) Enhanced: Quick  (~6hr)                                     │"
        echo "│   12c) Enhanced: Long   (~18hr)                                    │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  SSL PRETRAINING:                                                  │"
        echo "│   13a) SSL: Warmup (~4hr)                                          │"
        echo "│   13b) SSL: Full   (~12hr)                                         │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  TEMPORAL MAMBA (Novel Research):                                  │"
        echo "│   15a-d) Temporal models (~3-24hr)                                 │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  ULTIMATE (Wav2Vec2+MultiRes+Mamba):                               │"
        echo "│   16a-d) Ultimate models (~5-40hr)                                 │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│  BEATs (Microsoft Audio Foundation):                               │"
        echo "│   18a) BEATs: Warmup (~1hr)                                        │"
        echo "│   18b) BEATs: Quick  (~4hr)                                        │"
        echo "│   18c) BEATs: Long   (~12hr)                                       │"
        echo "├─────────────────────────────────────────────────────────────────────┤"
        echo "│   back) Return to main menu                                        │"
        echo "└─────────────────────────────────────────────────────────────────────┘"
        read -p "Select legacy mode: " legacy_choice

        case $legacy_choice in
            # Baseline
            5a) run_train_warmup; break ;;
            5b) run_train_quick; break ;;
            5c) run_train_long; break ;;
            # Auto-training baseline
            6a) run_auto_train warmup; break ;;
            6b) run_auto_train quick; break ;;
            6c) run_auto_train long; break ;;
            # Cutting-edge
            7a) run_train_cutting_edge_warmup; break ;;
            7b) run_train_cutting_edge_quick; break ;;
            7c) run_train_cutting_edge_long; break ;;
            8a) run_auto_train cutting-edge-warmup; break ;;
            8b) run_auto_train cutting-edge-quick; break ;;
            8c) run_auto_train cutting-edge-long; break ;;
            # Ensemble
            9a) run_auto_train ensemble-warmup; break ;;
            9b) run_auto_train ensemble-quick; break ;;
            9c) run_auto_train ensemble-long; break ;;
            # AST Transformer
            10a) run_auto_train ast-warmup; break ;;
            10b) run_auto_train ast-quick; break ;;
            10c) run_auto_train ast-long; break ;;
            # Distillation
            11a) run_auto_train distill-quick; break ;;
            11b) run_auto_train distill-long; break ;;
            # Enhanced v4
            12a) run_auto_train enhanced-warmup; break ;;
            12b) run_auto_train enhanced-quick; break ;;
            12c) run_auto_train enhanced-long; break ;;
            # SSL Pretraining
            13a) run_auto_train ssl-pretrain-warmup; break ;;
            13b) run_auto_train ssl-pretrain-full; break ;;
            # Temporal Mamba
            15a) run_auto_train temporal-warmup; break ;;
            15b) run_auto_train temporal-quick; break ;;
            15c) run_auto_train temporal-long; break ;;
            15d) run_auto_train temporal-full; break ;;
            # Ultimate
            16a) run_auto_train ultimate-warmup; break ;;
            16b) run_auto_train ultimate-quick; break ;;
            16c) run_auto_train ultimate-long; break ;;
            16d) run_auto_train ultimate-full; break ;;
            # BEATs
            18a) run_auto_train beats-warmup; break ;;
            18b) run_auto_train beats-quick; break ;;
            18c) run_auto_train beats-long; break ;;
            # Return
            back|b) return ;;
            *) echo "Invalid option." ;;
        esac
    done
}

# --- Interactive Menu ---

while true; do
    echo
    echo "╔═════════════════════════════════════════════════════════════════════╗"
    echo "║               BeatSight Post-Export Checklist                       ║"
    echo "╠═════════════════════════════════════════════════════════════════════╣"
    echo "║  UTILITIES:                                                         ║"
    echo "║   pre) Pre-flight Check (run before cloud!) ⭐ REQUIRED             ║"
    echo "║   0) Sync W&B (Offline Runs)                                        ║"
    echo "║   1) Dataset Health Check                                           ║"
    echo "║   2) Sanity Snapshot (Metadata)                                     ║"
    echo "║   3) Smoke Tests (pytest)                                           ║"
    echo "║   4) Precompute Feature Cache                                       ║"
    echo "║   4c) Consolidate Cache (100x speedup)                              ║"
    echo "║   4i) Convert Index to Binary (10x faster worker loading) ⭐ PERF   ║"
    echo "║   4m) Generate Cache Mapping (O(1) lookup, 50x faster!) ⭐ FAST     ║"
    echo "║   4v) Validate Cache (check for corruption)                         ║"
    echo "║   4r) Rebuild Cache (4 + 4c combined) ⚡ NEW DATA                    ║"
    echo "║   4n) Convert Labels to NumPy (fixes MemoryError) ⭐ REQUIRED       ║"
    echo "╠═════════════════════════════════════════════════════════════════════╣"
    echo "║  💎 V5 ULTIMATE - PRODUCTION PATH (⭐ RECOMMENDED)                   ║"
    echo "║─────────────────────────────────────────────────────────────────────║"
    echo "║   14)  Label Audit: Find noisy labels (~30min) ⭐ RUN FIRST!        ║"
    echo "║   14k) Label Audit K-Fold: 5-fold cross-val (~2hr) 🔬 RIGOROUS      ║"
    echo "║   17a) V5: Warmup - validates all innovations (~1hr)                ║"
    echo "║   17b) V5: Quick  - all innovations in one (~5hr)                   ║"
    echo "║   17c) V5: Long   - production quality (~12hr)                      ║"
    echo "║   17d) V5: Full   - large model, max quality (~24hr) ⭐ RECOMMENDED ║"
    echo "║   17e) V5: Self-Distill - Born-Again +1-2% (~24hr)                  ║"
    echo "║                                                                     ║"
    echo "║   ⭐ PATH: 14 → 17a → 17d → 17e (~50 hours total)                  ║"
    echo "║   🔬 RIGOROUS: 14 → 17a → 17d → 17e → 21 (+ holdout eval)          ║"
    echo "╠═════════════════════════════════════════════════════════════════════╣"
    echo "║  🥁 MULTI-LABEL - SIMULTANEOUS DRUM DETECTION                       ║"
    echo "║─────────────────────────────────────────────────────────────────────║"
    echo "║   19)  Generate Multi-Label Dataset (~10min) ⭐ RUN FIRST!          ║"
    echo "║   19a) Multi-Label: Warmup - validate setup (~2hr)                  ║"
    echo "║   19b) Multi-Label: Full   - production quality (~12hr)             ║"
    echo "║   19c) Multi-Label: Finetune - from V5 pretrained (~6hr) ⭐ BEST    ║"
    echo "║                                                                     ║"
    echo "║   Detects: kick+hihat, snare+crash, any simultaneous combo!         ║"
    echo "║   ⭐ FULL PATH: 14 → 17a → 17d → 17e → 19 → 19c                     ║"
    echo "╠═════════════════════════════════════════════════════════════════════╣"
    echo "║  EVALUATION & ANALYSIS:                                             ║"
    echo "║   21)     Holdout Eval: Final test on unseen sources (~15min) 🔬    ║"
    echo "║   eval)   Evaluation (Validation Snapshot)                          ║"
    echo "║   analyze) Analysis (Post-Run)                                      ║"
    echo "╠═════════════════════════════════════════════════════════════════════╣"
    echo "║  LEGACY OPTIONS (see docs/archive for details):                     ║"
    echo "║   legacy) Show all legacy training modes                            ║"
    echo "╠═════════════════════════════════════════════════════════════════════╣"
    echo "║   q) Quit                                                           ║"
    echo "╚═════════════════════════════════════════════════════════════════════╝"
    read -p "Select a step to run: " choice

    case $choice in
        0) run_wandb_sync ;;
        1) run_health_check ;;
        2) run_sanity_snapshot ;;
        3) run_smoke_tests ;;
        4) run_precompute_cache ;;
        4c) run_consolidate_cache ;;
        4i) run_convert_index_binary ;;
        4m) run_generate_cache_mapping ;;
        4v) run_validate_cache ;;
        4r) run_rebuild_cache ;;
        4n) run_convert_labels_numpy ;;
        # Pre-flight check
        pre) run_preflight_check ;;
        # V5 ULTIMATE: Single Model with All Innovations (⭐ RECOMMENDED)
        14) run_auto_train label-audit ;;
        14k) run_auto_train label-audit-kfold ;;
        17a) run_auto_train v5-warmup ;;
        17b) run_auto_train v5-quick ;;
        17c) run_auto_train v5-long ;;
        17d) run_auto_train v5-full ;;
        17e) run_auto_train v5-self-distill ;;
        # Multi-Label: Simultaneous Drum Detection
        19) generate_multilabel_dataset ;;
        19a) run_auto_train multilabel-warmup ;;
        19b) run_auto_train multilabel-full ;;
        19c) run_auto_train multilabel-finetune ;;
        # Evaluation & Analysis
        21) run_auto_train evaluate-holdout ;;
        eval) run_eval ;;
        analyze) run_analysis ;;
        # Legacy menu
        legacy) show_legacy_menu ;;
        q|Q) echo "Exiting."; exit 0 ;;
        *) echo "Invalid option. Use 'legacy' to see all training modes." ;;
    esac
    
    echo
    read -p "Press Enter to continue..."
done