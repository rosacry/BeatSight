# BeatSight AI Pipeline Handoff - Session 3 Dual-Model Ensemble (Updated)

Last updated: 2026-02-12

This handoff replaces stale Session 3 status assumptions and reflects the current training/evaluation path.

## Quick State Summary

- Dual-model ensemble architecture is implemented and available in pipeline code.
- Step 1 (Demucs LR 2e-5 run completion) is complete.
- Step 2 (clean-model continuation) is in progress and has reached epoch 11 in the provided logs.
- Step 3/4/5 are pending and should proceed after Step 2 checkpoint decision.

## Ensemble Architecture (Current)

Goal: use model specialization rather than a single model for all classes.

- Clean continuation model (body drums):
  - kick, snare, hihat_closed, hihat_open, hihat_pedal, tom, cross_stick, ride_bell, ride_bow
- Demucs-focused model (cymbals):
  - crash, china, splash

Production path:

- Use ensemble mode with both model checkpoints and both threshold JSON files.

## What Is Already Done

1. Dual-model arguments and wiring exist in the pipeline stack.
2. Training/threshold command plans are defined and validated.
3. Step 2 training is actively running with non-Demucs datasets excluded.
4. Recent Step 2 logs show best micro-F1 around 0.9133 (epoch 10), with weak-class plateau on hi-hat open/pedal.

## Active Decision Rule For Step 2

Use this stop/continue rule for the running clean continuation:

- Continue while micro-F1 or weak-class F1s improve materially.
- If gains flatten by epochs 12-15, stop Step 2 and move to Step 3.

Reason: maximize total iteration throughput instead of spending many hours for marginal gain.

## Next Steps (Canonical)

1. Finish Step 2 and choose final checkpoint (`runs/v5_multilabel_final_v3_continued`).
2. Run Step 3 Version A (`runs/v5_demucs_cymbal_boost`).
3. Generate Step 4 thresholds for both models.
4. Run Step 5 real-song bakeoff on `0101 - Heir of Grief.flac`:
   - baseline
   - multi-pass
   - global TTA
   - multi-window
   - checkpoint ensemble
5. Select default production inference mode by quality/runtime tradeoff.

## Commands

The authoritative command set is maintained in:

- `ai-pipeline/documentation/current/ACCURACY_IMPROVEMENTS_TRACKER.md`

Use that file as the operational source for exact command invocations.

## Validation Checklist Before Promotion

- Threshold files exist and match their target model checkpoints.
- Real-song output counts are musically plausible (especially cymbal and hi-hat balance).
- At least one dense metal/prog song and one cleaner song are reviewed qualitatively.
- Final chosen runtime mode has documented speed impact and quality rationale.

## Files That Must Stay In Sync

- `ai-pipeline/pipeline/process.py`
- `ai-pipeline/transcription/drum_classifier.py`
- `ai-pipeline/transcription/multilabel_inference.py`
- `ai-pipeline/scripts/generate_thresholds.py`
- `ai-pipeline/documentation/current/ACCURACY_IMPROVEMENTS_TRACKER.md`

## Notes For Future Sessions

- Do not regress to stale assumptions that Step 1 is pending.
- Prefer updating this file and `ACCURACY_IMPROVEMENTS_TRACKER.md` together after each major run.
- Keep archived prompt-style working notes under
  `ai-pipeline/documentation/archive/prompts/session/`.
