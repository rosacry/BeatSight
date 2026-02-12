# BeatSight AI Pipeline

Multi-label drum transcription pipeline for BeatSight.

## Current Direction

The project currently uses a dual-model ensemble strategy:

- Clean continuation model for body-drum classes
- Demucs-focused model for cymbal classes
- Threshold calibration per model

For live state and exact training commands, use:

- `ai-pipeline/ACCURACY_IMPROVEMENTS_TRACKER.md`
- `ai-pipeline/OPUS_HANDOFF_SESSION3_DUAL_MODEL_ENSEMBLE.md`
- `ai-pipeline/CURRENT_AI_PIPELINE_STATE.md`

## Quick Start

### Install

```bash
cd ai-pipeline
pip install -r requirements.txt
```

### Run Pipeline

```bash
cd /c/github/BeatSight/ai-pipeline
PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output test_beatmap/test_beatmap_ensemble.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --adaptive-thresholds \
  --force-time-signature 4/4 \
  --no-genre-detection \
  --no-pattern-repair
```

## Layout

```text
ai-pipeline/
  pipeline/          # Main process CLI and generation flow
  transcription/     # Multi-label inference and classifiers
  training/          # Training code
  separation/        # Demucs separation wrappers
  scripts/           # Utility scripts (threshold generation, diagnostics)
  runs/              # Checkpoints and outputs
  doc_archive/       # Archived prompt/temp markdown notes
```

## Documentation Hygiene

- Active docs stay at `ai-pipeline/` root for compatibility.
- One-off prompts and temporary markdown notes are archived under:
  - `ai-pipeline/doc_archive/session-prompts/`

## License

Training/inference code is MIT licensed. Model weights are proprietary.
