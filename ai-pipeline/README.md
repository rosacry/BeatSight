# BeatSight AI Pipeline

> Recovery update (2026-10-13): the
> [recovery audit](../docs/RECOVERY_AUDIT_2026-10-13.md) supersedes historical
> train/eval status. Current results: [phase 2, run 2](../docs/PHASE2_RUN2_RESULTS_2026-11-07.md). Surviving models execute, but measured full-song quality is
> insufficient for automatic teaching. See [recovery tools](../tools/recovery/README.md).
> In transcription mode, no confident hits now causes a failure before saving;
> synthetic fallback patterns remain available only in gameplay mode.

Multi-label drum transcription pipeline for BeatSight.

## Default engine: ADTOF (2026-10-16)

`python -m pipeline.process` now defaults to `--engine adtof`: stereo input
peak-normalized by its mono downmix, htdemucs_ft drum separation, and the ADTOF
Frame_RNN model with madmom-equivalent frontend and peak picking
(`adtof_engine/`, BeatSight's own implementation, bitwise-identical to the audited
2026-10-15 outputs). Notes keep detected times (no quantization); a forced
tempo/offset only sets grid metadata. Output uses five broad families shown as
`kick`, `snare`, `tom_mid`, `hihat_closed`, `crash`. `--mode`, `--sensitivity`,
`--quantization`, `--confidence` and ML flags apply only to `--engine legacy`,
the inherited pipeline kept as a fallback (desktop: AI settings checkbox).

```bash
cd ai-pipeline
python -m pipeline.process --input song.flac --output song.bsm   # ADTOF engine
python -m pipeline.process --engine legacy --input song.flac --output song.bsm
```

Weights are not in Git. Place the audited file at
`ai-pipeline/models/adtof/adtof_frame_rnn_pytorch_weights.pth` (SHA-256
`1bc986e5...7320`) or pass `--adtof-weights`. They are the ADTOF authors' model,
**CC BY-NC-SA 4.0: non-commercial use only**. BeatSight is personal/study use only (user
decision 2026-10-16); never push the weights publicly. Measured results and limits:
`docs/ADTOF_ENGINE_INTEGRATION_2026-10-16.md`. The hosted backend worker still
calls the legacy `process_audio_file` path.

## Historical direction (pre-recovery, unverified)

The project currently uses a dual-model ensemble strategy:

- Clean continuation model for body-drum classes
- Demucs-focused model for cymbal classes
- Threshold calibration per model

For live state and exact training commands, use:

- `ai-pipeline/documentation/current/ACCURACY_IMPROVEMENTS_TRACKER.md`
- `ai-pipeline/documentation/current/OPUS_HANDOFF_SESSION3_DUAL_MODEL_ENSEMBLE.md`
- `ai-pipeline/documentation/current/CURRENT_AI_PIPELINE_STATE.md`

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

Production-candidate tuning path (accuracy-first per song):

- `--mode transcription`
- `--auto-sensitivity`
- `--auto-quantization`

See full run matrix in:

- `ai-pipeline/documentation/current/STEP5_EVALUATION_COMMANDS.md`

## Layout

```text
ai-pipeline/
  pipeline/          # Main process CLI and generation flow
  transcription/     # Multi-label inference and classifiers
  training/          # Training code
  separation/        # Demucs separation wrappers
  scripts/           # Utility scripts (threshold generation, diagnostics)
  runs/              # Checkpoints and outputs
  documentation/
    current/         # Active state trackers and current handoffs
    archive/
      handoffs/      # Historical handoffs and superseded plans
      prompts/       # Session prompts and one-off working notes
```

## Documentation Hygiene

- Active docs live in `ai-pipeline/documentation/current/`.
- Historical/superseded docs live in `ai-pipeline/documentation/archive/handoffs/`.
- One-off prompts and temporary working notes live in:
  - `ai-pipeline/documentation/archive/prompts/session/`
- Index and maintenance rules:
  - `ai-pipeline/documentation/README.md`

## License

Training/inference code is MIT licensed. Model weights are proprietary.
