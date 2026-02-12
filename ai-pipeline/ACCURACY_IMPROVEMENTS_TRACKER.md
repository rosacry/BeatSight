# BeatSight AI Pipeline - Accuracy Improvements Tracker

Last updated: 2026-02-12

This tracker is the live status document for the dual-model ensemble training/evaluation loop.

## Goal

Improve real-song drum transcription quality while preserving strong body-drum performance.

- Clean model: primary for body drums (kick/snare/hihat/toms/ride)
- Demucs-focused model: primary for cymbals (crash/china/splash)
- Ensemble output: merged per-class decisions with calibrated thresholds

## Current 5-Step Plan Status

| Step | Description | Status | Notes |
| --- | --- | --- | --- |
| 1 | Demucs LR 2e-5 run completion | COMPLETE | Finished |
| 2 | Clean-model continuation (exclude Demucs datasets) | IN PROGRESS | Running; logs show progress through epoch 11 |
| 3 | Version A cymbal-boost Demucs run | PENDING | Start after Step 2 checkpoint decision |
| 4 | Threshold generation for both models | PENDING | Generate after Step 2 + Step 3 are finalized |
| 5 | Real-song bakeoff (baseline/multipass/tta/multi-window/checkpoint ensemble) | PENDING | Run after Step 4 thresholds are available |

## Step 2 (Running) Snapshot

Output directory:

- `runs/v5_multilabel_final_v3_continued`

Best observed so far from provided logs:

- Best micro-F1: `0.9133` (epoch 10)
- Best macro-F1: `0.9137` (epoch 10)
- Persistent weak classes: `hihat_open`, `hihat_pedal`

Recent trend from provided logs:

| Epoch | Micro-F1 | Macro-F1 | hihat_open F1 | hihat_pedal F1 |
| --- | --- | --- | --- | --- |
| 1 | 0.9099 | 0.9102 | 0.824 | 0.813 |
| 5 | 0.9122 | 0.9126 | 0.827 | 0.817 |
| 8 | 0.9124 | 0.9130 | 0.826 | 0.818 |
| 9 | 0.9129 | 0.9133 | 0.827 | 0.820 |
| 10 | 0.9133 | 0.9137 | 0.825 | 0.820 |

Interpretation:

- Step 2 is still improving, but gains are small and concentrated.
- If no meaningful gain appears by epochs 12-15, move to Step 3.

## Canonical Commands

### Step 2 command (currently running)

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m training.multilabel.train_multilabel \
  --dataset "F:/datasets/multilabel_real_v3" \
  --output-dir runs/v5_multilabel_final_v3_continued \
  --pretrained-checkpoint runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
  --exclude-datasets egmd_demucs,slakh2100_demucs,groove_midi_demucs,enst_drums_demucs \
  --model-version v5 --v5-size large \
  --epochs 30 --batch-size 128 --grad-accum-steps 5 \
  --lr 3e-5 --min-lr 3e-7 --amp-dtype bfloat16 \
  --balanced-sampling --balanced-method rare_class \
  --acoustic-oversample 10.0 \
  --loss-type cb_focal --cb-beta 0.999 --gamma 2.0 \
  --label-smoothing 0.02 --specaugment drum \
  --use-ema --ema-decay 0.9995 \
  --scheduler cosine --warmup-epochs 1 \
  --gradient-checkpointing --grad-clip-norm 1.0 \
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \
  --checkpoint-every 1 --checkpoint-every-batches 5000 --channels-last
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
# Clean model thresholds (Demucs manifests)
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python scripts/generate_thresholds.py \
  --model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --output runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --manifests \
    "F:/datasets/multilabel_real_v3/egmd_demucs/egmd_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/enst_drums_demucs/enst_drums_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/groove_midi_demucs/groove_midi_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/slakh2100_demucs/slakh2100_demucs_manifest.json"

# Demucs model thresholds
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python scripts/generate_thresholds.py \
  --model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --output runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --manifests \
    "F:/datasets/multilabel_real_v3/egmd_demucs/egmd_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/enst_drums_demucs/enst_drums_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/groove_midi_demucs/groove_midi_demucs_manifest.json" \
    "F:/datasets/multilabel_real_v3/slakh2100_demucs/slakh2100_demucs_manifest.json"
```

## Step 5 Real-Song Evaluation Runs

Use `../test_songs/0101 - Heir of Grief.flac` and compare these outputs:

1. Baseline ensemble
2. Multi-pass (`--multi-pass`)
3. Global TTA (`--tta --tta-augmentations 7`)
4. Multi-window (`--multi-window`)
5. Checkpoint ensemble (`--checkpoint-ensemble ...`)

Expected decision point:

- Pick one runtime mode for default production behavior.
- Keep slower modes as optional high-quality toggles.

## Quality Gates

Before promoting any run:

1. Validate class balance in output counts (especially crash/china/splash and hi-hat classes).
2. Compare rhythmic plausibility on at least one dense real song.
3. Keep a side-by-side summary (precision/recall/F1 + qualitative map readability notes).

## Key Risks To Watch

- `hihat_open` and `hihat_pedal` plateauing despite overall micro-F1 gains.
- Overproduction of cymbals after aggressive threshold/class weighting.
- Runtime regression if TTA or multi-window is enabled globally.
