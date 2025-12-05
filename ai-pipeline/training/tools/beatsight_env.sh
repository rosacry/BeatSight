#!/usr/bin/env bash
# BeatSight Training Environment Hook
# Source this file to set up environment variables for training workflows.
#
# Usage:
#   source ai-pipeline/training/tools/beatsight_env.sh
#
# Variables can be overridden by exporting them BEFORE sourcing this file:
#   export BEATSIGHT_DATA_ROOT=/custom/path
#   source ai-pipeline/training/tools/beatsight_env.sh

set -a  # Auto-export all variables

# ============================================================================
# REPOSITORY ROOT
# ============================================================================
if [ -z "${BEATSIGHT_REPO_ROOT:-}" ]; then
    if command -v git >/dev/null 2>&1; then
        BEATSIGHT_REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
    fi
    if [ -z "${BEATSIGHT_REPO_ROOT:-}" ]; then
        # Fallback: derive from script location
        SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
        BEATSIGHT_REPO_ROOT=$(cd "${SCRIPT_DIR}/../../.." && pwd)
    fi
fi

# ============================================================================
# DATA PATHS
# ============================================================================
# Primary data root - all heavy assets should live here
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-${BEATSIGHT_REPO_ROOT}/data}

# Secondary data root for overflow/alternate mounts (e.g., external drives)
BEATSIGHT_SECONDARY_ROOT=${BEATSIGHT_SECONDARY_ROOT:-/e/data}

# Dataset directory containing train/val splits (moved to HDD for space)
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_SECONDARY_ROOT}/prod_combined_profile_run}

# Feature cache for precomputed mel spectrograms
BEATSIGHT_CACHE_DIR=${BEATSIGHT_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/feature_cache/prod_combined_warmup}

# Labels cache for fast SSD access to label numpy files
# IMPORTANT: Velocity labels should be copied here for fast loading during training
#   cp /e/data/prod_combined_profile_run/train/train_labels_with_velocity_*.npy data/dataset_index/
#   cp /e/data/prod_combined_profile_run/val/val_labels_with_velocity_*.npy data/dataset_index/
BEATSIGHT_LABELS_CACHE_DIR=${BEATSIGHT_LABELS_CACHE_DIR:-${BEATSIGHT_DATA_ROOT}/dataset_index}

# ============================================================================
# OUTPUT PATHS
# ============================================================================
# Health reports from dataset validation
BEATSIGHT_HEALTH_DIR=${BEATSIGHT_HEALTH_DIR:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/reports/health}

# Metrics outputs from training and evaluation
BEATSIGHT_METRICS_DIR=${BEATSIGHT_METRICS_DIR:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/reports/metrics}

# Training run outputs root
BEATSIGHT_RUN_ROOT=${BEATSIGHT_RUN_ROOT:-${BEATSIGHT_REPO_ROOT}/ai-pipeline/training/runs}

# Preset run directories
BEATSIGHT_RUN_WARMUP=${BEATSIGHT_RUN_WARMUP:-${BEATSIGHT_RUN_ROOT}/prod_combined_warmup}
BEATSIGHT_RUN_QUICK=${BEATSIGHT_RUN_QUICK:-${BEATSIGHT_RUN_ROOT}/prod_combined_quick}
BEATSIGHT_RUN_LONG=${BEATSIGHT_RUN_LONG:-${BEATSIGHT_RUN_ROOT}/prod_combined_longrun}

# Weights & Biases offline runs
BEATSIGHT_WANDB_ROOT=${BEATSIGHT_WANDB_ROOT:-${BEATSIGHT_REPO_ROOT}/wandb}

# ============================================================================
# HARDWARE AUTO-DETECTION
# ============================================================================
# Detect CPU cores/threads (works on Linux, macOS, Windows/MSYS2)
if [ -z "${BEATSIGHT_CPU_CORES:-}" ]; then
    if [ -f /proc/cpuinfo ]; then
        # Linux: count physical cores
        BEATSIGHT_CPU_CORES=$(grep -c "^processor" /proc/cpuinfo 2>/dev/null || echo "8")
    elif command -v sysctl >/dev/null 2>&1; then
        # macOS
        BEATSIGHT_CPU_CORES=$(sysctl -n hw.physicalcpu 2>/dev/null || echo "8")
    elif command -v nproc >/dev/null 2>&1; then
        # Windows with nproc available
        BEATSIGHT_CPU_CORES=$(nproc 2>/dev/null || echo "8")
    else
        # Fallback
        BEATSIGHT_CPU_CORES=8
    fi
fi

# Detect GPU VRAM (NVIDIA only)
if [ -z "${BEATSIGHT_GPU_VRAM_GB:-}" ]; then
    if command -v nvidia-smi >/dev/null 2>&1; then
        BEATSIGHT_GPU_VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
        if [ -n "$BEATSIGHT_GPU_VRAM_MB" ]; then
            BEATSIGHT_GPU_VRAM_GB=$((BEATSIGHT_GPU_VRAM_MB / 1024))
        else
            BEATSIGHT_GPU_VRAM_GB=12  # Fallback for RTX 3080 Ti
        fi
    else
        BEATSIGHT_GPU_VRAM_GB=12  # Fallback
    fi
fi

# ============================================================================
# TRAINING HYPERPARAMETERS (Auto-tuned based on hardware)
# ============================================================================
# Feature cache batch size during precomputation
BEATSIGHT_CACHE_BATCH_SIZE=${BEATSIGHT_CACHE_BATCH_SIZE:-96}

# Number of workers for cache precomputation
BEATSIGHT_CACHE_WORKERS=${BEATSIGHT_CACHE_WORKERS:-4}

# Training batch size based on GPU VRAM:
#   - 8GB:  batch_size=128
#   - 12GB: batch_size=256-384 (RTX 3080 Ti, RTX 3090, etc.)
#   - 16GB: batch_size=384-512
#   - 24GB: batch_size=512-768
if [ -z "${BEATSIGHT_TRAIN_BATCH_SIZE:-}" ]; then
    if [ "$BEATSIGHT_GPU_VRAM_GB" -ge 24 ]; then
        BEATSIGHT_TRAIN_BATCH_SIZE=512
    elif [ "$BEATSIGHT_GPU_VRAM_GB" -ge 16 ]; then
        BEATSIGHT_TRAIN_BATCH_SIZE=384
    elif [ "$BEATSIGHT_GPU_VRAM_GB" -ge 12 ]; then
        BEATSIGHT_TRAIN_BATCH_SIZE=256
    else
        BEATSIGHT_TRAIN_BATCH_SIZE=128
    fi
fi

# Gradient accumulation steps (target effective batch = 1024)
if [ -z "${BEATSIGHT_GRAD_ACCUM_STEPS:-}" ]; then
    BEATSIGHT_GRAD_ACCUM_STEPS=$((1024 / BEATSIGHT_TRAIN_BATCH_SIZE))
    # Clamp to minimum of 1
    [ "$BEATSIGHT_GRAD_ACCUM_STEPS" -lt 1 ] && BEATSIGHT_GRAD_ACCUM_STEPS=1
fi

# DataLoader workers based on CPU cores:
#   - For NVMe mmap caching, fewer workers is often better (less memory pressure)
#   - persistent_workers=True eliminates Windows spawn overhead
#   - With 9800X3D's 96MB X3D cache, workers benefit from cache locality
if [ -z "${BEATSIGHT_TRAIN_WORKERS:-}" ]; then
    # Optimal formula for NVMe mmap: half of cores (avoids thrashing)
    BEATSIGHT_TRAIN_WORKERS=$((BEATSIGHT_CPU_CORES / 2))
    # Clamp between 4 and 12 (diminishing returns beyond 12)
    [ "$BEATSIGHT_TRAIN_WORKERS" -lt 4 ] && BEATSIGHT_TRAIN_WORKERS=4
    [ "$BEATSIGHT_TRAIN_WORKERS" -gt 12 ] && BEATSIGHT_TRAIN_WORKERS=12
fi

# DataLoader workers for validation (half of training workers)
if [ -z "${BEATSIGHT_VAL_WORKERS:-}" ]; then
    BEATSIGHT_VAL_WORKERS=$((BEATSIGHT_TRAIN_WORKERS / 2))
    # Minimum of 2
    [ "$BEATSIGHT_VAL_WORKERS" -lt 2 ] && BEATSIGHT_VAL_WORKERS=2
fi

# Prefetch factor (samples per worker to prefetch)
# Higher prefetch hides I/O latency - 6-10 is optimal for NVMe SSD + memory-mapped cache
# For HDD-based datasets, use lower values (2-4) to avoid excessive memory usage
BEATSIGHT_PREFETCH_FACTOR=${BEATSIGHT_PREFETCH_FACTOR:-8}

set +a  # Stop auto-exporting

# ============================================================================
# VERIFY AND PRINT
# ============================================================================
if [ "${BEATSIGHT_ENV_QUIET:-0}" != "1" ]; then
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║            BeatSight Training Environment Configured             ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║ Repository:    ${BEATSIGHT_REPO_ROOT}"
    echo "║ Data Root:     ${BEATSIGHT_DATA_ROOT}"
    echo "║ Dataset:       ${BEATSIGHT_DATASET_DIR}"
    echo "║ Cache:         ${BEATSIGHT_CACHE_DIR}"
    echo "║ Run Output:    ${BEATSIGHT_RUN_ROOT}"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║ Hardware Detected:                                               ║"
    echo "║   CPU Cores:      ${BEATSIGHT_CPU_CORES}"
    echo "║   GPU VRAM:       ${BEATSIGHT_GPU_VRAM_GB}GB"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║ Training Defaults (auto-tuned):                                  ║"
    echo "║   Batch Size:     ${BEATSIGHT_TRAIN_BATCH_SIZE} (effective: $((BEATSIGHT_TRAIN_BATCH_SIZE * BEATSIGHT_GRAD_ACCUM_STEPS)) with grad_accum)"
    echo "║   Workers:        ${BEATSIGHT_TRAIN_WORKERS} train / ${BEATSIGHT_VAL_WORKERS} val"
    echo "║   Prefetch:       ${BEATSIGHT_PREFETCH_FACTOR}"
    echo "╚══════════════════════════════════════════════════════════════════╝"
fi
