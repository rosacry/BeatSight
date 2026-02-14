# BeatSight AI Pipeline Handoff - Session 3 Dual-Model Ensemble

Last updated: 2026-02-14

This handoff reflects the current training plan and command matrix in active use.

## Quick State Summary

- Dual-model ensemble architecture is implemented in pipeline code.
- Step 1 is complete.
- Step 2 is still running and now has logs through epoch 20 (partial), with best micro-F1 0.9147 (epoch 18).
- Steps 3/4/5 remain pending and should proceed exactly in sequence after Step 2 checkpoint selection.

## Ensemble Architecture (Current)

- Clean continuation model (body drums):
  - kick, snare, hihat_closed, hihat_open, hihat_pedal, tom, cross_stick, ride_bell, ride_bow
- Demucs-focused model (cymbals):
  - crash, china, splash

Production path:

- Use ensemble mode with both model checkpoints plus both threshold JSON files.

## Current Decision Rules

### Step 2

- Keep current run until completion (epoch 30), unless significant divergence appears.
- At completion, select checkpoint by:
  - micro-F1
  - macro-F1
  - weak-class F1 trend (`hihat_open`, `hihat_pedal`)

### Step 5

- Compare both inference matrices:
  1. manual baseline matrix (fixed sensitivity/quantization/no-readability-filter path)
  2. production-candidate matrix (`--mode transcription --auto-sensitivity --auto-quantization`)
- Decide default production mode by quality/runtime tradeoff.

## Canonical Execution Order

1. Finish Step 2 and select final clean checkpoint.
2. Run Step 3 Version A (`runs/v5_demucs_cymbal_boost`).
3. Generate Step 4 thresholds:
   - `thresholds_demucs_calibrated.json`
   - `thresholds_demucs_only.json`
4. Run Step 5 bakeoff on `0101 - Heir of Grief.flac`.
5. Select default inference mode and document rationale.

## Source of Truth for Commands

Use this file for workflow context and use the tracker for exact command text:

- `ai-pipeline/documentation/current/ACCURACY_IMPROVEMENTS_TRACKER.md`

## Files That Must Stay In Sync

- `ai-pipeline/pipeline/process.py`
- `ai-pipeline/transcription/drum_classifier.py`
- `ai-pipeline/transcription/multilabel_inference.py`
- `ai-pipeline/scripts/generate_thresholds.py`
- `ai-pipeline/documentation/current/ACCURACY_IMPROVEMENTS_TRACKER.md`

## Risk Notes

- Weak classes still lag (`hihat_open`, `hihat_pedal`) despite overall gains.
- If adaptive thresholds reduce quality on real songs, keep non-adaptive baseline as fallback.
- Desktop parity for pipeline flags is now explicitly wired and test-covered:
  - `--mode`
  - `--auto-sensitivity`
  - `--auto-quantization`
  - Coverage files:
    - `desktop/BeatSight.Tests/AiBeatmapGeneratorArgumentsTests.cs`
    - `desktop/BeatSight.Tests/GenerationCoordinatorTests.cs`
