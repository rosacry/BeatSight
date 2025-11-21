#!/usr/bin/env bash
# Rebuild Batch Script: Ingests updated datasets and builds the training set in one go.
# Usage: bash ai-pipeline/training/tools/rebuild_batch.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TOOLS_DIR="${REPO_ROOT}/ai-pipeline/training/tools"
MANIFEST_DIR="${REPO_ROOT}/ai-pipeline/training/data/manifests"
PROVENANCE_DIR="${REPO_ROOT}/ai-pipeline/training/data/provenance"
DATASET_OUTPUT_DIR="${REPO_ROOT}/data/prod_combined_profile_run"
BUILD_LOG="${REPO_ROOT}/logs/dataset_build_batch.log"
BUILD_SUMMARY="${REPO_ROOT}/logs/dataset_build_batch.summary.json"

# Audio Configuration (Matches ingest_and_build.sh)
AUDIO_ROOT_PRIMARY="E:/data/raw"
AUDIO_MAP_ARGS=(
  "--audio-root-map" "slakh2100=E:/data/raw/slakh2100"
  "--audio-root-map" "groove_mididataset=E:/data/raw/groove_midi"
  "--audio-root-map" "extended_groove_mididataset=E:/data/raw/egmd"
  "--audio-root-map" "enst_drums=E:/data/raw/ENST-Drums"
  "--audio-root-map" "idmt_smt_drums_v2=E:/data/raw/idmt_smt_drums_v2"
  "--audio-root-map" "cambridge_multitrack=E:/data/raw/cambridge"
  "--audio-root-map" "musdb18_hq=E:/data/raw/musdb18_hq"
  "--audio-root-map" "signaturesounds=E:/data/raw/signaturesounds"
  "--audio-root-map" "telefunken_sessions=E:/data/raw/telefunken"
  "--audio-root-map" "medleydb=E:/data/raw/MedleyDB"
)

echo "========================================="
echo "   Batch Dataset Rebuild (24-Class Schema)"
echo "========================================="

# Helper function to run ingestion steps safely
run_ingest_step() {
    local step_name="$1"
    local marker_file="${MANIFEST_DIR}/.${step_name}_done"
    shift
    if [ -f "$marker_file" ]; then
        echo ">>> Step ${step_name} marked complete. Skipping."
    else
        # Run the command passed as remaining args
        "$@"
        # If successful, touch marker
        touch "$marker_file"
    fi
}

# 1. Ingest MedleyDB
run_ingest_step "medleydb" python "${TOOLS_DIR}/ingest_medleydb.py" \
    --medleydb-root "E:/data/raw/MedleyDB" \
    --output-events "${MANIFEST_DIR}/medleydb_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/medleydb_provenance.jsonl"

# 2. Ingest Groove MIDI Dataset
run_ingest_step "groove_mididataset" python "${TOOLS_DIR}/ingest_groove.py" \
    --root "E:/data/raw/groove_midi" \
    --output-events "${MANIFEST_DIR}/groove_mididataset_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/groove_mididataset_provenance.jsonl"

# 3. Ingest Extended Groove MIDI Dataset (EGMD)
run_ingest_step "egmd" python "${TOOLS_DIR}/ingest_egmd.py" \
    --root "E:/data/raw/egmd" \
    --output-events "${MANIFEST_DIR}/egmd_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/egmd_provenance.jsonl"

# 4. Ingest Slakh2100
run_ingest_step "slakh2100" python "${TOOLS_DIR}/ingest_slakh.py" \
    --root "E:/data/raw/slakh2100" \
    --output-events "${MANIFEST_DIR}/slakh2100_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/slakh2100_provenance.jsonl"

# 5. Ingest ENST Drums
run_ingest_step "enst_drums" python "${TOOLS_DIR}/ingest_enst.py" \
    --root "E:/data/raw/ENST-Drums" \
    --output-events "${MANIFEST_DIR}/enst_drums_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/enst_drums_provenance.jsonl"

# 6. Ingest Cambridge Multitrack
run_ingest_step "cambridge_multitrack" python "${TOOLS_DIR}/ingest_cambridge.py" \
    --roots "E:/data/raw/cambridge" \
    --events-output "${MANIFEST_DIR}/cambridge_multitrack_events.jsonl" \
    --provenance-output "${PROVENANCE_DIR}/cambridge_multitrack_provenance.jsonl" \
    --workers 16

# 7. Ingest IDMT-SMT-Drums
run_ingest_step "idmt_smt_drums_v2" python "${TOOLS_DIR}/ingest_idmt.py" \
    --root "E:/data/raw/idmt_smt_drums_v2" \
    --output-events "${MANIFEST_DIR}/idmt_smt_drums_v2_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/idmt_smt_drums_v2_provenance.jsonl"

# 8. Ingest Signature Sounds
run_ingest_step "signaturesounds" python "${TOOLS_DIR}/ingest_signaturesounds.py" \
    --root "E:/data/raw/signaturesounds" \
    --output-events "${MANIFEST_DIR}/signaturesounds_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/signaturesounds_provenance.jsonl"

# 9. Ingest Telefunken
run_ingest_step "telefunken_sessions" python "${TOOLS_DIR}/ingest_telefunken.py" \
    --root "E:/data/raw/telefunken" \
    --output-events "${MANIFEST_DIR}/telefunken_sessions_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/telefunken_sessions_provenance.jsonl"

# 10. Ingest MUSDB18 (HQ)
run_ingest_step "musdb_hq" python "${TOOLS_DIR}/ingest_musdb.py" \
    --hq-root "E:/data/raw/musdb18_hq" \
    --output-events "${MANIFEST_DIR}/musdb_hq_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/musdb_hq_provenance.jsonl"

# 11. Merge Manifests
echo ">>> Step 11: Merging Manifests..."
TARGET_MANIFEST="${MANIFEST_DIR}/prod_combined_events.jsonl"
python "${TOOLS_DIR}/merge_manifests.py" \
    --input "${MANIFEST_DIR}/medleydb_events.jsonl" \
    --input "${MANIFEST_DIR}/groove_mididataset_events.jsonl" \
    --input "${MANIFEST_DIR}/egmd_events.jsonl" \
    --input "${MANIFEST_DIR}/slakh2100_events.jsonl" \
    --input "${MANIFEST_DIR}/enst_drums_events.jsonl" \
    --input "${MANIFEST_DIR}/cambridge_multitrack_events.jsonl" \
    --input "${MANIFEST_DIR}/idmt_smt_drums_v2_events.jsonl" \
    --input "${MANIFEST_DIR}/signaturesounds_events.jsonl" \
    --input "${MANIFEST_DIR}/telefunken_sessions_events.jsonl" \
    --input "${MANIFEST_DIR}/musdb_hq_events.jsonl" \
    --output "${TARGET_MANIFEST}"
echo "Merged manifest created at: ${TARGET_MANIFEST}"

# 12. Build Dataset
echo ">>> Step 12: Building Training Dataset..."
echo "Output Directory: ${DATASET_OUTPUT_DIR}"

# Check if we can resume (though usually we want a fresh build here)
RESUME_FLAG=""
if [ -d "${DATASET_OUTPUT_DIR}" ]; then
    echo "Existing dataset directory found. Enabling --resume mode."
    RESUME_FLAG="--resume"
fi

python "${TOOLS_DIR}/build_training_dataset.py" \
    "${TARGET_MANIFEST}" \
    "${DATASET_OUTPUT_DIR}" \
    --audio-root "${AUDIO_ROOT_PRIMARY}" \
    "${AUDIO_MAP_ARGS[@]}" \
    --sample-rate 44100 \
    --val-ratio 0.1 \
    --force-rich \
    --checkpoint-every 300000 \
    --heal-missing-clips \
    --clip-fanout 2 \
    --write-workers 16 \
    ${RESUME_FLAG} \
    --log-file "${BUILD_LOG}" \
    --summary-json "${BUILD_SUMMARY}"

echo "========================================="
echo "   Batch Rebuild Complete!"
echo "========================================="
