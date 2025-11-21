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
  "--audio-root-map" "musdb18_hq=E:/data/raw/musdb18s"
  "--audio-root-map" "signaturesounds=E:/data/raw/signaturesounds"
  "--audio-root-map" "telefunken_sessions=E:/data/raw/telefunken"
  "--audio-root-map" "medleydb=E:/data/raw/MedleyDB"
)

echo "========================================="
echo "   Batch Dataset Rebuild (24-Class Schema)"
echo "========================================="

# 1. Ingest MedleyDB
echo ">>> Step 1: Ingesting MedleyDB..."
python "${TOOLS_DIR}/ingest_medleydb.py" \
    --medleydb-root "E:/data/raw/MedleyDB" \
    --output-events "${MANIFEST_DIR}/medleydb_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/medleydb_provenance.jsonl"

# 2. Ingest Groove MIDI Dataset
echo ">>> Step 2: Ingesting Groove MIDI Dataset..."
python "${TOOLS_DIR}/ingest_groove.py" \
    --root "E:/data/raw/groove_midi" \
    --output-events "${MANIFEST_DIR}/groove_mididataset_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/groove_mididataset_provenance.jsonl"

# 3. Ingest Slakh2100
echo ">>> Step 3: Ingesting Slakh2100..."
python "${TOOLS_DIR}/ingest_slakh.py" \
    --root "E:/data/raw/slakh2100" \
    --output-events "${MANIFEST_DIR}/slakh2100_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/slakh2100_provenance.jsonl"

# 4. Ingest ENST Drums
echo ">>> Step 4: Ingesting ENST Drums..."
python "${TOOLS_DIR}/ingest_enst.py" \
    --root "E:/data/raw/ENST-Drums" \
    --output-events "${MANIFEST_DIR}/enst_drums_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/enst_drums_provenance.jsonl"

# 5. Ingest Cambridge Multitrack
echo ">>> Step 5: Ingesting Cambridge Multitrack..."
python "${TOOLS_DIR}/ingest_cambridge.py" \
    --root "E:/data/raw/cambridge" \
    --output-events "${MANIFEST_DIR}/cambridge_multitrack_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/cambridge_multitrack_provenance.jsonl"

# 6. Ingest IDMT-SMT-Drums
echo ">>> Step 6: Ingesting IDMT-SMT-Drums..."
python "${TOOLS_DIR}/ingest_idmt.py" \
    --root "E:/data/raw/idmt_smt_drums_v2" \
    --output-events "${MANIFEST_DIR}/idmt_smt_drums_v2_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/idmt_smt_drums_v2_provenance.jsonl"

# 7. Ingest Signature Sounds
echo ">>> Step 7: Ingesting Signature Sounds..."
python "${TOOLS_DIR}/ingest_signaturesounds.py" \
    --root "E:/data/raw/signaturesounds" \
    --output-events "${MANIFEST_DIR}/signaturesounds_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/signaturesounds_provenance.jsonl"

# 8. Ingest Telefunken
echo ">>> Step 8: Ingesting Telefunken..."
python "${TOOLS_DIR}/ingest_telefunken.py" \
    --root "E:/data/raw/telefunken" \
    --output-events "${MANIFEST_DIR}/telefunken_sessions_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/telefunken_sessions_provenance.jsonl"

# 9. Ingest MUSDB18 (HQ)
echo ">>> Step 9: Ingesting MUSDB18..."
python "${TOOLS_DIR}/ingest_musdb.py" \
    --root "E:/data/raw/musdb18s" \
    --output-events "${MANIFEST_DIR}/musdb18_hq_events.jsonl" \
    --output-provenance "${PROVENANCE_DIR}/musdb18_hq_provenance.jsonl"

# 10. Merge Manifests
echo ">>> Step 10: Merging Manifests..."
TARGET_MANIFEST="${MANIFEST_DIR}/prod_combined_events.jsonl"
python "${TOOLS_DIR}/merge_manifests.py" \
    --input "${MANIFEST_DIR}/medleydb_events.jsonl" \
    --input "${MANIFEST_DIR}/groove_mididataset_events.jsonl" \
    --input "${MANIFEST_DIR}/slakh2100_events.jsonl" \
    --input "${MANIFEST_DIR}/enst_drums_events.jsonl" \
    --input "${MANIFEST_DIR}/cambridge_multitrack_events.jsonl" \
    --input "${MANIFEST_DIR}/idmt_smt_drums_v2_events.jsonl" \
    --input "${MANIFEST_DIR}/signaturesounds_events.jsonl" \
    --input "${MANIFEST_DIR}/telefunken_sessions_events.jsonl" \
    --input "${MANIFEST_DIR}/musdb18_hq_events.jsonl" \
    --output "${TARGET_MANIFEST}"

echo "Merged manifest created at: ${TARGET_MANIFEST}"

# 11. Build Dataset
echo ">>> Step 11: Building Training Dataset..."
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
