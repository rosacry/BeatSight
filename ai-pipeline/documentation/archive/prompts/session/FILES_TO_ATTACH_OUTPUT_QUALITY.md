# Files to Attach in New Opus Session

## Archive Metadata

- **Document Type:** Session prompt (archived)
- **Status:** Historical reference only
- **Normalized On:** 2026-02-13
- **Canonical Location:** `ai-pipeline/documentation/archive/prompts/session/`
- **Current Source of Truth:** `ai-pipeline/documentation/current/`

When starting the new session, attach these files (or paste their paths) so the agent has direct access:

## REQUIRED — Attach These Files

### 1. The Handoff Prompt (this session's output)
- `ai-pipeline/documentation/archive/prompts/session/OPUS_INVESTIGATE_OUTPUT_QUALITY.md`

### 2. Core Inference & Pipeline Code
- `ai-pipeline/transcription/multilabel_inference.py` — Core inference (1,376 lines, threshold scaling, feature extraction)
- `ai-pipeline/pipeline/process.py` — Main pipeline orchestrator (1,122 lines)
- `ai-pipeline/transcription/onset_detector.py` — Onset detection (426 lines)

### 3. Post-Processing Pipeline
- `ai-pipeline/pipeline/chart_readability.py` — Readability filter that removes hits (974 lines)
- `ai-pipeline/pipeline/pattern_library.py` — Pattern repair that changes labels (841 lines)

### 4. Training Code
- `ai-pipeline/training/multilabel/train_multilabel.py` — Training loop (1,867 lines)
- `ai-pipeline/training/multilabel/preextract_spectrograms.py` — Feature pre-extraction (239 lines)

### 5. Threshold Tuning
- `ai-pipeline/scripts/generate_thresholds.py` — Threshold optimization (387 lines)

### 6. Configuration / Thresholds
- `ai-pipeline/runs/v5_finetune_demucs/thresholds.json` — New finetuned thresholds
- `ai-pipeline/runs/v5_multilabel_final_v3/thresholds.json` — Old pre-finetune thresholds

### 7. Test Outputs for Comparison
- `test_beatmap_finetuned_demucs.bsm` — Finetuned model output (WORST — 1413 hits)
- `test_beatmap_fixed.bsm` — Best previous output (2452 hits)
- `test_beatmap.bsm` — Original baseline (2135 hits)

## OPTIONAL — Attach If Token Budget Allows

- `ai-pipeline/pipeline/structured_decoder.py` — Structural decoder (no label changes)
- `ai-pipeline/pipeline/genre_aware_decoder.py` — Genre decoder (no label changes)
- `ai-pipeline/transcription/instrument_pitch_ranker.py` — Pitch ranking
- `ai-pipeline/tools/transcribe_song.py` — CLI inference tool
- `ai-pipeline/diag_probs.py` — Diagnostic (WARNING: uses old mismatched pipeline)
- `ai-pipeline/scripts/create_demucs_augmented_dataset.py` — Augmentation script (completed)

## Total: ~12 files required, ~6 optional

The agent can also read any file in the workspace with tools, so don't worry about missing files — these are just for immediate context.
