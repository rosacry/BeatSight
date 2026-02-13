# BeatSight AI Pipeline - Current State

Last updated: 2026-02-13

## Purpose

This is the fast status snapshot for current execution.
For full commands and evaluation matrices, use:

- `ai-pipeline/documentation/current/ACCURACY_IMPROVEMENTS_TRACKER.md`

For handoff context:

- `ai-pipeline/documentation/current/OPUS_HANDOFF_SESSION3_DUAL_MODEL_ENSEMBLE.md`

## Active Work

### Training state

- Step 1: COMPLETE
- Step 2: IN PROGRESS (running through epoch 20 partial in latest shared logs)
- Step 3: PENDING (start after Step 2 checkpoint selection)
- Step 4: PENDING (threshold generation after Steps 2 and 3)
- Step 5: PENDING (real-song bakeoff + production mode decision)

### Latest Step 2 headline metrics

- Best micro-F1: 0.9147 (epoch 18)
- Best macro-F1: 0.9153 (epoch 17)
- Weak classes remain:
  - hihat_open
  - hihat_pedal

## Active Pipeline Patch Set Status

The in-progress pipeline patch set is currently test-validated:

- Added: `ai-pipeline/pipeline/auto_parameters.py`
- Added: `ai-pipeline/tests/test_auto_parameters.py`
- Modified:
  - `ai-pipeline/pipeline/process.py`
  - `ai-pipeline/pipeline/structured_decoder.py`
  - `ai-pipeline/pipeline/chart_readability.py`
  - `ai-pipeline/pipeline/genre_aware_decoder.py`
  - `ai-pipeline/pipeline/pattern_library.py`

Validation run (latest local):

- `python -m pytest ai-pipeline/tests/test_auto_parameters.py -q` -> pass
- `python -m pytest ai-pipeline/tests/test_process_pipeline.py ai-pipeline/tests/test_full_pipeline.py ai-pipeline/tests/test_multilabel_inference.py ai-pipeline/tests/test_count_estimation.py -q` -> pass
- `python -m pytest ai-pipeline/tests/test_dataset_health.py ai-pipeline/tests/test_structured_decoder.py ai-pipeline/tests/test_lane_assignment.py -q` -> pass

Desktop contract parity update:

- `--mode`, `--auto-sensitivity`, and `--auto-quantization` are now wired in desktop CLI argument construction.
- Coverage added in:
  - `desktop/BeatSight.Tests/AiBeatmapGeneratorArgumentsTests.cs`

## Next Action

1. Let Step 2 finish and select final checkpoint using documented criteria.
2. Kick Step 3 Version A immediately after Step 2 completion.
3. Keep tracker/handoff synchronized at each phase transition.
