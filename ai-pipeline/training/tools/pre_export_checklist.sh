#!/usr/bin/env bash
# Smoke-test the export pipeline before committing to the full run.
#
# This script performs a limited `build_training_dataset.py` export using the
# current production manifest, captures basic throughput telemetry, and executes
# the dataset health checks against the temporary bundle. Running it up front is
# far cheaper than discovering a root-map typo or metadata regression 45 minutes
# into the full export.
#
# Usage:
#   bash ai-pipeline/training/tools/pre_export_checklist.sh \
#       [manifest] [output_dir]
#
# Environment overrides:
#   EXPORT_LIMIT       -- number of events to export (default: 50000)
#   RAW_PRIMARY        -- primary raw audio root (default: <repo>/data/raw)
#   RAW_SECONDARY      -- secondary raw audio root (default: RAW_PRIMARY)
#   KEEP_SMOKE_OUTPUT  -- set to 1 to keep the smoke dataset on disk
#
# The script writes dataset health reports to
#   ai-pipeline/training/reports/health/preflight_dataset_health.{json,html}
# before optionally deleting the smoke directory.

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=${ROOT_OVERRIDE:-$(cd "$SCRIPT_DIR"/../../.. && pwd)}
MANIFEST=${1:-$ROOT/ai-pipeline/training/data/manifests/prod_combined_events.jsonl}
OUTPUT=${2:-$ROOT/data/prod_combined_smoke_run}
EXPORT_LIMIT=${EXPORT_LIMIT:-50000}
RAW_PRIMARY=${RAW_PRIMARY:-$ROOT/data/raw}
RAW_SECONDARY=${RAW_SECONDARY:-$RAW_PRIMARY}
REPORT_DIR=$ROOT/ai-pipeline/training/reports/health
REPORT_JSON=$REPORT_DIR/preflight_dataset_health.json
REPORT_HTML=$REPORT_DIR/preflight_dataset_health.html

mkdir -p "$REPORT_DIR"

echo "[preflight] starting limited export (limit=$EXPORT_LIMIT)"
PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/build_training_dataset.py \
  "$MANIFEST" \
  "$OUTPUT" \
  --audio-root "$RAW_PRIMARY" \
  --audio-root-map slakh2100=$RAW_PRIMARY/slakh2100 \
  --audio-root-map groove_mididataset=$RAW_PRIMARY/groove_midi \
  --audio-root-map extended_groove_mididataset=$RAW_PRIMARY/egmd \
  --audio-root-map enst_drums=$RAW_PRIMARY/ENST-Drums \
  --audio-root-map idmt_smt_drums_v2=$RAW_PRIMARY/idmt_smt_drums_v2 \
  --audio-root-map musdb18_hq=$RAW_PRIMARY/musdb18_hq \
  --audio-root-map signaturesounds=$RAW_PRIMARY/signaturesounds \
  --audio-root-map telefunken_sessions=$RAW_PRIMARY/telefunken \
  --audio-root-map cambridge_multitrack=$RAW_PRIMARY/cambridge \
  --audio-root-map cambridge_multitrack=$RAW_SECONDARY/cambridge \
  --limit "$EXPORT_LIMIT" \
  --force-rich \
  --profile \
  --overwrite

if [ ! -f "$OUTPUT/metadata.json" ]; then
  echo "[preflight] ERROR: metadata.json missing in smoke export" >&2
  exit 1
fi

echo "[preflight] running dataset health on smoke export"
PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/dataset_health.py \
  --dataset-root "$OUTPUT" \
  --dataset-metadata "$OUTPUT/metadata.json" \
  --report-json "$REPORT_JSON" \
  --report-html "$REPORT_HTML"

echo "[preflight] health reports written to:" "$REPORT_JSON" "$REPORT_HTML"

if [ "${KEEP_SMOKE_OUTPUT:-0}" != "1" ]; then
  echo "[preflight] removing smoke export at $OUTPUT"
  rm -rf "$OUTPUT"
fi

echo "[preflight] complete"
