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

echo

cat <<'EOF'
# 0. Sync any offline W&B runs (optional but recommended)
wandb sync "${BEATSIGHT_WANDB_ROOT}"/offline-run-*/ || true

# 1. Dataset health check
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

# 2. Manifest vs metadata sanity snapshot
DATASET_DIR="${BEATSIGHT_DATASET_DIR}" python - <<'PY'
import json, os
from pathlib import Path

dataset = Path(os.environ["DATASET_DIR"])
metadata = dataset / "metadata.json"
with metadata.open("r", encoding="utf-8") as handle:
    data = json.load(handle)
print("Total events processed:", data.get("total_events_processed"))
print("Written clips:", data.get("statistics", {}).get("written_clips"))
print("Missing audio:", data.get("statistics", {}).get("skipped_missing_audio"))
print("Train clips:", data.get("statistics", {}).get("train_clips"))
print("Val clips:", data.get("statistics", {}).get("val_clips"))
PY

# 3. Regression smoke tests for the training pipeline
pytest \
  ai-pipeline/tests/test_dataset_health.py \
  ai-pipeline/tests/test_drum_classifier.py \
  || { echo "pytest failures detected"; exit 1; }

# 4. Optionally pre-fill the feature cache (speeds up first warm-up run)
PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/precompute_feature_cache.py \
  --dataset "${BEATSIGHT_DATASET_DIR}" \
  --cache-dir "${BEATSIGHT_CACHE_DIR}" \
  --splits train val \
  --batch-size 128 \
  --num-workers 8 \
  --persistent-workers \
  --sample-rate 44100 \
  --n-fft 2048 \
  --hop-length 512 \
  --n-mels 128 \
  --target-frames 128 \
  --cache-dtype float16

# 5. Kick off training (choose the preset that fits your budget)

# 5a. Cached warm-up probe (resumable, ~95 min after cache populate)
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
  --wandb-tags prod_combined_20251110 richer_subset warmup \
  --wandb-run-name prod_combined_warmup_probe_$(date +%Y%m%d) \
  --grad-accum-steps 4

# 5b. Baseline refresh (~3.5h on 3080 Ti with warm cache)
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
  --wandb-tags prod_combined_20251110 quick_refresh cached \
  --wandb-run-name prod_combined_quick_refresh_$(date +%Y%m%d)

# 5c. Unlimited-runtime long run (~13.5h, same hardware)
WANDB_RUN_GROUP=prod_combined_longrun_lr28e5 \
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
  --wandb-tags prod_combined_20251110 full_corpus longrun lr28e5 richer_split \
  --wandb-run-name prod_combined_longrun_lr28e5_$(date +%Y%m%d) \
  --resume-from "${BEATSIGHT_RUN_WARMUP}/checkpoints/latest_checkpoint.pth"

# 6. Validation snapshot (quick post-run evaluation)
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

# 7. Post-run analysis (perform after checkpoints land)
PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/analyze_classifier.py \
  --dataset "${BEATSIGHT_DATASET_DIR}" \
  --model-path "${BEATSIGHT_RUN_WARMUP}/best_drum_classifier.pth" \
  --cache-dir "${BEATSIGHT_CACHE_DIR}" \
  --output-dir "${BEATSIGHT_METRICS_DIR}/../analysis/prod_combined_warmup" \
  --channels-last \
  --topk-misclassified 100

# - Inspect W&B curves for loss/accuracy, LR trends, and anomalies.
# - Review the evaluator outputs for class-level accuracy/confusion before deeper dives.
# - Review the JSON/CSV outputs in reports/analysis for class-level drift and misclassified clips.
# - Re-run the manifest snapshot above and compare against prior exports for drift.

# Target metrics checkpoint: expect >=93% val accuracy and <=0.45 val loss before promoting models.

# Resume tip: latest checkpoints land in <output>/checkpoints/latest_checkpoint.pth.
# Relaunch with: ... --resume-from <output>/checkpoints/latest_checkpoint.pth

# Tip: Re-run 5c with different seeds (unique WANDB_RUN_GROUP + seeding env vars) for ensembles.
EOF
