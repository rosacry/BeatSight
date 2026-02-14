# BeatSight AI Pipeline - Accuracy Improvements Tracker

Last updated: 2026-02-14

This is the live status doc for the dual-model ensemble train/eval loop.

## Goal

Improve real-song drum transcription quality while preserving strong body-drum performance.

- Clean model: primary for body drums (kick/snare/hihat/toms/ride)
- Demucs-focused model: primary for cymbals (crash/china/splash)
- Ensemble output: merged per-class decisions with calibrated thresholds

## Current 5-Step Plan Status

| Step | Description | Status | Notes |
| --- | --- | --- | --- |
| 1 | Demucs LR 2e-5 run completion | COMPLETE | Finished |
| 2 | Clean-model continuation (exclude Demucs datasets) | COMPLETE | Finished (checkpoint selection/summary captured in local run logs) |
| 3 | Version A cymbal-boost Demucs run | IN PROGRESS | Current active background training run |
| 4 | Threshold generation for both models | PENDING | Generate after Step 2 + Step 3 finalize |
| 5 | Real-song bakeoff + production-mode decision | PENDING | Run after Step 4 threshold files exist |

## Step 2 Completion Snapshot (Latest Shared Metrics)

Output directory:

- `runs/v5_multilabel_final_v3_continued`

Best observed from latest provided logs:

- Best micro-F1: `0.9147` (epoch 18)
- Best macro-F1: `0.9153` (epoch 17)
- Best weak-class F1s:
  - `hihat_open`: `0.830` (epoch 15)
  - `hihat_pedal`: `0.824` (epoch 18)

Recent trend:

| Epoch | Micro-F1 | Macro-F1 | hihat_open F1 | hihat_pedal F1 |
| --- | --- | --- | --- | --- |
| 10 | 0.9133 | 0.9137 | 0.825 | 0.820 |
| 11 | 0.9135 | 0.9141 | 0.829 | 0.820 |
| 13 | 0.9139 | 0.9146 | 0.829 | 0.821 |
| 15 | 0.9141 | 0.9148 | 0.830 | 0.821 |
| 17 | 0.9146 | 0.9153 | 0.829 | 0.822 |
| 18 | 0.9147 | 0.9152 | 0.827 | 0.824 |
| 19 | 0.9143 | 0.9148 | 0.827 | 0.822 |

Interpretation:

- Improvement continued beyond epoch 15 (not a hard plateau).
- Step 2 has now completed.
- Use the saved Step 2 best checkpoint and/or selected late-epoch checkpoints as Step 5 candidates.

## Canonical Commands

### Step 2 command (completed)

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m training.multilabel.train_multilabel \
  --dataset "F:/datasets/multilabel_real_v3" \
  --output-dir runs/v5_multilabel_final_v3_continued \
  --pretrained-checkpoint runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
  --exclude-datasets egmd_demucs,slakh2100_demucs,groove_midi_demucs,enst_drums_demucs \
  --model-version v5 \
  --v5-size large \
  --epochs 30 \
  --batch-size 128 \
  --grad-accum-steps 5 \
  --lr 3e-5 \
  --min-lr 3e-7 \
  --amp-dtype bfloat16 \
  --balanced-sampling --balanced-method rare_class \
  --acoustic-oversample 10.0 \
  --loss-type cb_focal \
  --cb-beta 0.999 \
  --gamma 2.0 \
  --label-smoothing 0.02 \
  --specaugment drum \
  --use-ema \
  --ema-decay 0.9995 \
  --scheduler cosine \
  --warmup-epochs 1 \
  --gradient-checkpointing \
  --grad-clip-norm 1.0 \
  --num-workers 4 \
  --prefetch-factor 2 \
  --persistent-workers \
  --pin-memory \
  --checkpoint-every 1 \
  --checkpoint-every-batches 5000 \
  --channels-last
```

### Step 3 command (Version A)

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m training.multilabel.train_multilabel \
  --dataset "F:/datasets/multilabel_real_v3" \
  --output-dir runs/v5_demucs_cymbal_boost/ \
  --pretrained-checkpoint runs/v5_demucs_only_finetune_lr2e5/best_multilabel_model_ema.pt \
  --include-datasets egmd_demucs,slakh2100_demucs,groove_midi_demucs,enst_drums_demucs \
  --model-version v5 --v5-size large \
  --epochs 15 --batch-size 128 --grad-accum-steps 5 \
  --lr 2e-5 --min-lr 2e-7 --amp-dtype bfloat16 \
  --balanced-sampling --balanced-method rare_class \
  --dataset-weight enst_drums_demucs=20 --dataset-weight slakh2100_demucs=3 \
  --loss-type cb_focal --cb-beta 0.999 --gamma 2.0 \
  --class-loss-weight china=5.0 --class-loss-weight crash=5.0 --class-loss-weight splash=5.0 \
  --label-smoothing 0.02 --specaugment drum \
  --use-ema --ema-decay 0.9995 \
  --scheduler cosine --warmup-epochs 1 \
  --gradient-checkpointing --grad-clip-norm 1.0 \
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \
  --checkpoint-every 1 --channels-last
```

### Step 4 threshold generation

```bash
# Clean model thresholds (Demucs-only manifests)
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python scripts/generate_thresholds.py \
  --model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --output runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --manifests \
    "F:/datasets/multilabel_real_v3/egmd_demucs/egmd_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/enst_drums_demucs/enst_drums_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/groove_midi_demucs/groove_midi_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/slakh2100_demucs/slakh2100_demucs_manifest.json"

# Demucs model thresholds (Demucs-only manifests)
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python scripts/generate_thresholds.py \
  --model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --output runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --manifests \
    "F:/datasets/multilabel_real_v3/egmd_demucs/egmd_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/enst_drums_demucs/enst_drums_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/groove_midi_demucs/groove_midi_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/slakh2100_demucs/slakh2100_demucs_manifest.json"
```

## Step 5 Real-Song Evaluation Matrix

Test input:

- `../test_songs/0101 - Heir of Grief.flac`
- Exact command blocks:
  - `ai-pipeline/documentation/current/STEP5_EVALUATION_COMMANDS.md`

### A) Manual baseline matrix (current fixed settings)

- Run 0 baseline:
  - output: `../test_songs/v5/test_v5_baseline.bsm`
  - flags include: `--sensitivity 80 --quantization thirtysecond --no-readability-filter --force-time-signature 4/4 --no-genre-detection --no-pattern-repair`
- Run 1 baseline + adaptive thresholds:
  - output: `../test_songs/v5/test_v5_baseline_with_adaptive_thresholds.bsm`
  - add: `--adaptive-thresholds`
- Run 2 multi-pass:
  - output: `../test_songs/v5/test_v5_multipass.bsm`
  - add: `--multi-pass`
- Run 3 global TTA:
  - output: `../test_songs/v5/test_v5_tta.bsm`
  - add: `--tta --tta-augmentations 7`
- Run 4 multi-window:
  - output: `../test_songs/v5/test_v5_multiwindow.bsm`
  - add: `--multi-window`
- Run 5 checkpoint ensemble:
  - output: `../test_songs/v5/test_v5_checkpoint_ensemble.bsm`
  - add:
    - `--checkpoint-ensemble`
    - `runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt`
    - `runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0026.pt`
    - `runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0025.pt`
    - `runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0024.pt`

### B) Production-candidate matrix (auto-tuned transcription mode)

Candidate baseline flags:

- `--mode transcription`
- `--auto-sensitivity`
- `--auto-quantization`

Intended removals vs manual baseline commands:

- remove `--force-time-signature`
- remove `--no-genre-detection`
- remove `--no-pattern-repair`

Candidate runs:

- Run 0: `../test_songs/v5/prod/test_v5_baseline_prod.bsm`
- Run 1 (+ adaptive): `../test_songs/v5/prod/test_v5_baseline_with_adaptive_thresholds_prod.bsm`
- Run 2 (+ multi-pass): `../test_songs/v5/prod/test_v5_multipass_prod.bsm`
- Run 3 (+ global TTA): `../test_songs/v5/prod/test_v5_tta_prod.bsm`
- Run 4 (+ multi-window): `../test_songs/v5/prod/test_v5_multiwindow_prod.bsm`
- Run 5 (+ checkpoint ensemble): `../test_songs/v5/prod/test_v5_checkpoint_ensemble_prod.bsm`
  - planned checkpoints:
    - `best_multilabel_model_ema.pt`
    - `checkpoint_epoch_0026.pt`
    - `checkpoint_epoch_0025.pt`
    - `checkpoint_epoch_0024.pt`

## Decision Point After Step 5

Pick one default production inference mode by quality/runtime tradeoff:

1. baseline
2. baseline + adaptive
3. multi-pass
4. global TTA
5. multi-window
6. checkpoint ensemble

## Quality Gates

Before promotion:

1. Validate class balance in output counts (especially crash/china/splash and hi-hat classes).
2. Compare rhythmic plausibility on at least one dense real song.
3. Keep side-by-side summary (metrics + qualitative notation/readability notes).
4. Record final default mode with runtime cost.

## Risks To Watch

- `hihat_open` and `hihat_pedal` remain the weakest classes even with improvements.
- Overproduction of cymbals after threshold/class weighting changes.
- Runtime regression if TTA/multi-window is used as global default.
- Desktop contract drift risk has been mitigated by explicit parity wiring and expanded tests:
  - `desktop/BeatSight.Game/AI/AiBeatmapGenerator.cs`
  - `desktop/BeatSight.Game/AI/Generation/GenerationCoordinator.cs`
  - `desktop/BeatSight.Tests/AiBeatmapGeneratorArgumentsTests.cs`
  - `desktop/BeatSight.Tests/GenerationCoordinatorTests.cs`
