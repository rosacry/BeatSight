#!/usr/bin/env bash
# Handy checklist to run immediately after build_training_dataset.py completes.
# Usage: bash ai-pipeline/training/tools/post_export_commands.sh

set -euo pipefail

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
BEATSIGHT_DATASET_DIR=${BEATSIGHT_DATASET_DIR:-${BEATSIGHT_DATA_ROOT}/prod_combined_profile_run}
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

run_train_warmup() {
    echo ">>> Starting Warmup Training..."
    BS_CACHE_DEBUG=1 \
    PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --warmup-epochs 4 \
      --scheduler cosine \
      --min-lr 0.00002 \
      --batch-size 32 \
      --lr 0.00045 \
      --device cuda \
      --val-fraction 0.12 \
      --cache-dtype float16 \
      --num-workers 2 \
      --val-num-workers 2 \
      --prefetch-factor 1 \
      --val-prefetch-factor 1 \
      --grad-clip-norm 1.0 \
      --weight-decay 0.0001 \
      --torch-compile-mode reduce-overhead \
      --seed 1337 \
      --checkpoint-every 1 \
      --output "${BEATSIGHT_RUN_WARMUP}" \
      --metrics-json "${BEATSIGHT_METRICS_DIR}/prod_combined_warmup.json" \
      --wandb-project beatsight-classifier \
      --wandb-tags prod_combined_24class richer_subset warmup \
      --wandb-run-name prod_combined_warmup_probe_$(date +%Y%m%d) \
      --grad-accum-steps 4
}

run_train_quick() {
    echo ">>> Starting Quick Refresh Training..."
    PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --epochs 60 \
      --scheduler plateau \
      --batch-size 48 \
      --lr 0.0005 \
      --device cuda \
      --cache-dtype float16 \
      --num-workers 8 \
      --val-num-workers 8 \
      --persistent-workers \
      --grad-clip-norm 1.0 \
      --weight-decay 0.0001 \
      --channels-last \
      --torch-compile \
      --torch-compile-mode reduce-overhead \
      --seed 1337 \
      --checkpoint-every 10 \
      --output "${BEATSIGHT_RUN_QUICK}" \
      --metrics-json "${BEATSIGHT_METRICS_DIR}/prod_combined_quick.json" \
      --wandb-project beatsight-classifier \
      --wandb-tags prod_combined_24class quick_refresh cached \
      --wandb-run-name prod_combined_quick_refresh_$(date +%Y%m%d)
}

run_train_long() {
    echo ">>> Starting Long Run Training..."
    export WANDB_RUN_GROUP=prod_combined_longrun_lr28e5
    PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
      --dataset "${BEATSIGHT_DATASET_DIR}" \
      --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
      --warmup-epochs 16 \
      --scheduler cosine \
      --min-lr 0.00002 \
      --batch-size 32 \
      --lr 0.00028 \
      --device cuda \
      --train-fraction 1.0 \
      --val-fraction 0.3 \
      --subset-seed 20251112 \
      --num-workers 4 \
      --val-num-workers 4 \
      --prefetch-factor 2 \
      --val-prefetch-factor 2 \
      --persistent-workers \
      --grad-clip-norm 1.0 \
      --weight-decay 0.0001 \
      --channels-last \
      --torch-compile \
      --torch-compile-mode reduce-overhead \
      --seed 1337 \
      --checkpoint-every 20 \
      --output "${BEATSIGHT_RUN_LONG}" \
      --metrics-json "${BEATSIGHT_METRICS_DIR}/prod_combined_longrun.json" \
      --wandb-tags prod_combined_24class full_corpus longrun lr28e5 richer_split \
      --wandb-run-name prod_combined_longrun_lr28e5_$(date +%Y%m%d) \
      --resume-from "${BEATSIGHT_RUN_WARMUP}/checkpoints/latest_checkpoint.pth"
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

# --- Interactive Menu ---

while true; do
    echo
    echo "========================================="
    echo "   BeatSight Post-Export Checklist"
    echo "========================================="
    echo " 0) Sync W&B (Offline Runs)"
    echo " 1) Dataset Health Check"
    echo " 2) Sanity Snapshot (Metadata)"
    echo " 3) Smoke Tests (pytest)"
    echo " 4) Precompute Feature Cache"
    echo " 5a) Train: Warmup Probe (Recommended First)"
    echo " 5b) Train: Quick Refresh"
    echo " 5c) Train: Long Run"
    echo " 6) Evaluation (Validation Snapshot)"
    echo " 7) Analysis (Post-Run)"
    echo " q) Quit"
    echo "========================================="
    read -p "Select a step to run: " choice

    case $choice in
        0) run_wandb_sync ;;
        1) run_health_check ;;
        2) run_sanity_snapshot ;;
        3) run_smoke_tests ;;
        4) run_precompute_cache ;;
        5a) run_train_warmup ;;
        5b) run_train_quick ;;
        5c) run_train_long ;;
        6) run_eval ;;
        7) run_analysis ;;
        q|Q) echo "Exiting."; exit 0 ;;
        *) echo "Invalid option." ;;
    esac
    
    echo
    read -p "Press Enter to continue..."
done