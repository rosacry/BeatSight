#!/usr/bin/env bash
# Universal Dataset Workflow: Ingest -> Merge -> Build
# Usage: bash ai-pipeline/training/tools/ingest_and_build.sh [dataset_name] [dataset_root]

set -euo pipefail

# --- 1. Setup & Inputs ---

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DEFAULT_NAME="medleydb"

# Audio Source Map
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

get_default_root() {
    case "$1" in
        "slakh2100") echo "E:/data/raw/slakh2100" ;;
        "groove_mididataset") echo "E:/data/raw/groove_midi" ;;
        "extended_groove_mididataset") echo "E:/data/raw/egmd" ;;
        "enst_drums") echo "E:/data/raw/ENST-Drums" ;;
        "idmt_smt_drums_v2") echo "E:/data/raw/idmt_smt_drums_v2" ;;
        "cambridge_multitrack") echo "E:/data/raw/cambridge" ;;
        "musdb18_hq") echo "E:/data/raw/musdb18_hq" ;;
        "signaturesounds") echo "E:/data/raw/signaturesounds" ;;
        "telefunken_sessions") echo "E:/data/raw/telefunken" ;;
        "medleydb") echo "E:/data/raw/MedleyDB" ;;
        *) echo "E:/data/raw/$1" ;;
    esac
}

if [ "$#" -ge 1 ]; then
    DATASET_NAME=$1
    DEFAULT_ROOT_FOR_NAME=$(get_default_root "$DATASET_NAME")
    DATASET_ROOT=${2:-$DEFAULT_ROOT_FOR_NAME}
    INTERACTIVE=false
else
    INTERACTIVE=true
    echo "========================================="
    echo "   Dataset Ingestion Configuration"
    echo "========================================="
    read -p "Dataset Name (e.g. groove) [${DEFAULT_NAME}]: " INPUT_NAME
    DATASET_NAME=${INPUT_NAME:-$DEFAULT_NAME}
    
    DEFAULT_ROOT_FOR_NAME=$(get_default_root "$DATASET_NAME")
    read -p "Dataset Root Path [${DEFAULT_ROOT_FOR_NAME}]: " INPUT_ROOT
    DATASET_ROOT=${INPUT_ROOT:-$DEFAULT_ROOT_FOR_NAME}
    echo
fi

# --- 2. Derived Configuration ---

TOOLS_DIR="${REPO_ROOT}/ai-pipeline/training/tools"
MANIFEST_DIR="${REPO_ROOT}/ai-pipeline/training/data/manifests"
PROVENANCE_DIR="${REPO_ROOT}/ai-pipeline/training/data/provenance"

# Update derived paths based on current DATASET_NAME
update_paths() {
    INGEST_SCRIPT="${TOOLS_DIR}/ingest_${DATASET_NAME}.py"
    NEW_MANIFEST="${MANIFEST_DIR}/${DATASET_NAME}_events.jsonl"
    NEW_PROVENANCE="${PROVENANCE_DIR}/${DATASET_NAME}_provenance.jsonl"
    BUILD_LOG="${REPO_ROOT}/logs/dataset_build_${DATASET_NAME}.log"
    BUILD_SUMMARY="${REPO_ROOT}/logs/dataset_build_${DATASET_NAME}.summary.json"
}
update_paths

MASTER_MANIFEST="${MANIFEST_DIR}/prod_combined_events.jsonl"
TARGET_MANIFEST="${MANIFEST_DIR}/prod_combined_events_v2.jsonl"

DATASET_OUTPUT_DIR="${REPO_ROOT}/data/prod_combined_profile_run"
AUDIO_ROOT_PRIMARY="E:/data/raw"

# --- 3. Functions ---

run_ingest() {
    echo ">>> Step 1: Ingesting ${DATASET_NAME}..."
    
    # Handle flag naming conventions
    ROOT_ARG_FLAG="--root"
    if [ "${DATASET_NAME}" == "medleydb" ]; then
        ROOT_ARG_FLAG="--medleydb-root"
    fi

    if [ -f "${INGEST_SCRIPT}" ]; then
        python "${INGEST_SCRIPT}" \
            "${ROOT_ARG_FLAG}" "${DATASET_ROOT}" \
            --output-events "${NEW_MANIFEST}" \
            --output-provenance "${NEW_PROVENANCE}"
        echo "Ingestion complete."
    else
        echo "Warning: Ingest script ${INGEST_SCRIPT} not found."
        echo "Assuming manifest ${NEW_MANIFEST} already exists and proceeding."
    fi
    echo
}

run_merge() {
    echo ">>> Step 2: Preparing Manifest..."

    if [ -f "${MASTER_MANIFEST}" ]; then
        echo "Found existing master manifest: ${MASTER_MANIFEST}"
        echo "Merging new data with existing production data..."
        python "${TOOLS_DIR}/merge_manifests.py" \
            --input "${MASTER_MANIFEST}" \
            --input "${NEW_MANIFEST}" \
            --output "${TARGET_MANIFEST}"
        echo "Merged manifest created at: ${TARGET_MANIFEST}"
    else
        echo "No master manifest found (First run?)."
        echo "Initializing new build manifest with ${DATASET_NAME} only."
        cp "${NEW_MANIFEST}" "${TARGET_MANIFEST}"
        echo "Created ${TARGET_MANIFEST}"
    fi
    echo
}

run_build() {
    echo ">>> Step 3: Building Training Dataset..."
    echo "Output Directory: ${DATASET_OUTPUT_DIR}"

    RESUME_FLAG=""
    if [ -d "${DATASET_OUTPUT_DIR}" ]; then
        echo "Existing dataset directory found. Enabling --resume mode."
        RESUME_FLAG="--resume"
    else
        echo "No existing dataset directory. Starting fresh build."
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
    echo
}

# --- 4. Execution ---

if [ "$INTERACTIVE" = false ]; then
    # Automated mode
    run_ingest
    run_merge
    run_build
    exit 0
fi

# Interactive Menu
while true; do
    echo "========================================="
    echo "   Workflow: ${DATASET_NAME}"
    echo "   Root:     ${DATASET_ROOT}"
    echo "========================================="
    echo " 1) Run ALL Steps (Ingest -> Merge -> Build)"
    echo " 2) Ingest Only"
    echo " 3) Merge Only"
    echo " 4) Build Only"
    echo " c) Re-configure Dataset"
    echo " q) Quit"
    echo "========================================="
    read -p "Select an option: " choice

    case $choice in
        1) run_ingest; run_merge; run_build ;;
        2) run_ingest ;;
        3) run_merge ;;
        4) run_build ;;
        c|C) 
            read -p "Dataset Name [${DATASET_NAME}]: " INPUT_NAME
            DATASET_NAME=${INPUT_NAME:-$DATASET_NAME}
            DEFAULT_ROOT_FOR_NAME=$(get_default_root "$DATASET_NAME")
            read -p "Dataset Root [${DEFAULT_ROOT_FOR_NAME}]: " INPUT_ROOT
            DATASET_ROOT=${INPUT_ROOT:-$DEFAULT_ROOT_FOR_NAME}
            update_paths
            ;;
        q|Q) echo "Exiting."; exit 0 ;;
        *) echo "Invalid option." ;;
    esac
    
    echo
    read -p "Press Enter to continue..."
done
