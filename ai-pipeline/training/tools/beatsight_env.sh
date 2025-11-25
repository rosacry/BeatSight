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
# TRAINING HYPERPARAMETERS (Hardware-Optimized Defaults for RTX 3080 Ti)
# ============================================================================
# Feature cache batch size during precomputation
BEATSIGHT_CACHE_BATCH_SIZE=${BEATSIGHT_CACHE_BATCH_SIZE:-96}

# Number of workers for cache precomputation
BEATSIGHT_CACHE_WORKERS=${BEATSIGHT_CACHE_WORKERS:-4}

# Training batch size (effective batch = batch_size * grad_accum_steps)
BEATSIGHT_TRAIN_BATCH_SIZE=${BEATSIGHT_TRAIN_BATCH_SIZE:-32}

# Gradient accumulation steps (effective batch = 32 * 4 = 128)
BEATSIGHT_GRAD_ACCUM_STEPS=${BEATSIGHT_GRAD_ACCUM_STEPS:-4}

# DataLoader workers for training (2-4 optimal for Windows with NVMe)
BEATSIGHT_TRAIN_WORKERS=${BEATSIGHT_TRAIN_WORKERS:-2}

# DataLoader workers for validation
BEATSIGHT_VAL_WORKERS=${BEATSIGHT_VAL_WORKERS:-2}

# Prefetch factor (samples per worker to prefetch)
BEATSIGHT_PREFETCH_FACTOR=${BEATSIGHT_PREFETCH_FACTOR:-2}

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
    echo "║ Training Defaults (RTX 3080 Ti optimized):                       ║"
    echo "║   Batch Size:     ${BEATSIGHT_TRAIN_BATCH_SIZE} (effective: $((BEATSIGHT_TRAIN_BATCH_SIZE * BEATSIGHT_GRAD_ACCUM_STEPS)) with grad_accum)"
    echo "║   Workers:        ${BEATSIGHT_TRAIN_WORKERS} train / ${BEATSIGHT_VAL_WORKERS} val"
    echo "║   Prefetch:       ${BEATSIGHT_PREFETCH_FACTOR}"
    echo "╚══════════════════════════════════════════════════════════════════╝"
fi
