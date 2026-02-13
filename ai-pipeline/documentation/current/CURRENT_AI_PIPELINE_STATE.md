# BeatSight AI Pipeline — Current State & Active Work (Feb 7, 2026)

## PURPOSE OF THIS DOCUMENT

This document describes the **current state of the AI pipeline work** being done in a separate Claude Code session. If you are working on other parts of BeatSight (desktop app, backend, frontend), **do NOT modify any files listed in the "DO NOT TOUCH" section** — they are actively being worked on and changes will conflict.

---

## EXECUTIVE SUMMARY

The AI drum transcription model (CNN V5 Large, 7.1M params, 12-class multi-label) went through a Demucs domain gap fine-tuning process. The fine-tuning exposed three critical problems that are now being systematically fixed:

1. **China/splash blindness** — zero Demucs training data for these classes caused complete detection failure
2. **Training collapse on OOM resume** — checkpoint corruption caused catastrophic forgetting at epoch 4
3. **Probability compression** — model outputs suppressed probabilities on Demucs-separated audio

**Current status**: Generating new Demucs-augmented training data from Slakh2100 (~262K events with china/splash), then will retrain with 6 new safety fixes applied to the training script. Threshold fixes for inference are already applied and partially working.

---

## WHAT'S CURRENTLY RUNNING

```
python scripts/create_demucs_augmented_dataset.py --source slakh
```

This is processing 1,708 Slakh2100 tracks through Demucs separation to create training data with china (262K events) and splash (6.5K events) coverage. Running on GPU, ~23s per track, estimated ~10-11 hours total. Checkpoint/resume enabled — safe to interrupt and restart.

**Output**: `F:/datasets/multilabel_real_v3/slakh2100_demucs/` — batched .npy files + manifest

---

## ROOT CAUSES IDENTIFIED

### Root Cause 1: Zero China/Splash in Demucs Training Data
The three original Demucs-augmented datasets (ENST, EGMD, Groove MIDI) contain **zero china and zero splash events**. The model learned to suppress these classes entirely on Demucs-separated audio.

**Fix**: Adding Slakh2100 Demucs data (in progress). Slakh has 262,641 china + 6,557 splash + 38,934 crash events.

### Root Cause 2: Checkpoint Corruption on OOM Resume
At epoch 4, an OOM crash corrupted the checkpoint's RNG state. `torch.set_rng_state()` requires a ByteTensor but received the wrong type. This caused:
- Val loss spike: 0.0215 → 0.2108 (10x increase)
- China F1: 0.992 → 0.003
- Splash F1: 0.987 → 0.001
- Warning in logs: `[WARN] Failed to restore RNG state: RNG state must be a torch.ByteTensor`

**Fix**: 6 safety patches applied to `train_multilabel.py` (see below).

### Root Cause 3: Probability Compression on Demucs Audio
The finetuned model outputs significantly lower probabilities for all classes on Demucs-separated real audio vs clean validation data. China max probability was 0.12 (threshold was 0.73), splash max was 0.27 (threshold 0.81).

**Fix**: Tiered threshold scaling system in `multilabel_inference.py` + will improve with more Demucs training data.

---

## CHANGES ALREADY APPLIED

### File: `ai-pipeline/transcription/multilabel_inference.py`

1. **4-tier threshold scaling system** (`get_threshold()` method):
   - Common classes (kick, snare, hihat_*, tom, ride_bow): `scale^0.25`
   - Moderate classes (ride_bell, cross_stick): `scale^0.5`
   - Sensitive classes (crash): `scale^0.75`
   - Zero-Demucs classes (china, splash): `scale^0.75 * 0.15`

2. **Crash moved from MODERATE to SENSITIVE tier** — effective threshold 0.67→0.513

3. **`_ZERO_DEMUCS_THRESHOLD_FACTOR = 0.15`** (was 0.55) — china threshold 0.73→0.084, splash 0.81→0.093

4. **`_MAX_COMPONENTS_PER_ONSET = 4`** (was 3)

5. **`_BODY_COOCCURRENCE_MIN_PROB = 0.40`** (was 0.50)

### File: `ai-pipeline/training/multilabel/train_multilabel.py`

6 safety fixes to prevent training collapse:

1. **`_atomic_torch_save` with `os.fsync()`** — prevents checkpoint corruption from crashes
2. **Checkpoint rotation** — per-epoch checkpoints, keep last 3, enables rollback
3. **RNG state ByteTensor coercion** — fixes the direct cause of epoch 4 collapse
4. **Post-resume validation sanity check** — runs validation after resume, alerts if F1 drops >10%
5. **Class collapse detection** — prevents saving "best" model if any class has F1 < 0.01
6. **Val loss spike detection** — warns at 1.5x increase, CRITICAL alert at 3x

### File: `ai-pipeline/scripts/create_demucs_augmented_dataset.py`

7. **Added `--source slakh` mode** — processes Slakh2100 mix.flac through Demucs
   - Mode A (like ENST): load full mix → Demucs → extract spectrograms at onset times
   - Groups events by track, loads mix.flac from parent directory
   - Pre-Demucs trimming to event span (saves GPU time on tracks with late-starting drums)
   - Native sample rate loading (preserves audio quality for Demucs)
   - Threaded pipeline: CPU feature extraction overlaps with GPU Demucs processing
   - Full checkpoint/resume support
   - Added to `--source all`, `--analyze`, argparse choices, docstring

---

## WHAT COMES NEXT (After Slakh data generation completes)

### Step 1: Retrain the model (v2)
```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m training.multilabel.train_multilabel \
  --dataset "F:/datasets/multilabel_real_v3" \
  --output-dir runs/v5_finetune_demucs_v2 \
  --pretrained-checkpoint runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
  --model-version v5 \
  --v5-size large \
  --epochs 20 \
  --batch-size 128 \
  --grad-accum-steps 5 \
  --lr 2e-5 \
  --min-lr 2e-7 \
  --amp-dtype bfloat16 \
  --balanced-sampling --balanced-method rare_class \
  --acoustic-oversample 10.0 \
  --dataset-weight enst_drums_demucs=20 \
  --dataset-weight egmd_demucs=15 \
  --dataset-weight groove_midi_demucs=15 \
  --dataset-weight slakh2100_demucs=20 \
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

Key points:
- Starting from the **original pretrained model** (not the collapsed finetuned one)
- New output dir `v5_finetune_demucs_v2`
- Added `--dataset-weight slakh2100_demucs=20` for the new Slakh data
- The 6 safety fixes in train_multilabel.py will prevent another collapse

### Step 2: Generate new thresholds
```bash
python scripts/generate_thresholds.py \
  --model-path runs/v5_finetune_demucs_v2/best_multilabel_model_ema.pt \
  --dataset-path F:/datasets/multilabel_real_v3 \
  --output-path runs/v5_finetune_demucs_v2/thresholds.json
```

### Step 3: Test on songs and evaluate all 12 classes
```bash
python -m pipeline.process \
  -i "../test_songs/0101 - Heir of Grief.flac" \
  -o ../test_beatmap_v2.bsm \
  --multilabel-model runs/v5_finetune_demucs_v2/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_finetune_demucs_v2/thresholds.json \
  --threshold-scale 0.7
```

### Step 4: If crash still underperforms
- Investigate Demucs separation quality for crash cymbals specifically
- Consider crash-specific threshold tier
- Consider additional crash augmentation

---

## TEST RESULTS SO FAR

### Pipeline test: "Heir of Grief" (prog metal, ~5:09)

| Metric | Before Fix | After Fix | Original Model | Recovery |
|--------|-----------|-----------|----------------|----------|
| Total hits | 1,413 | 1,610 | 2,135 | 75% |
| Splash | 0 | 169 | 149 | **113%** |
| China | 0 | 18 | 29 | **62%** |
| Crash | 16 | 17 | 129 | 13% |
| Kick | 547 | 572 | 815 | 70% |
| Hi-hat closed | 131 | 130 | 451 | 29% |

The threshold fixes recovered splash and china. Crash and overall volume still need the v2 retraining.

---

## MODEL & ARCHITECTURE REFERENCE

- **Model**: CNN V5 Large, 7,143,308 parameters
- **Input**: (1, 128, 128) mel-spectrogram
- **Output**: 12-class sigmoid (multi-label)
- **12 classes** (index order): china, crash, cross_stick, hihat_closed, hihat_open, hihat_pedal, kick, ride_bell, ride_bow, snare, splash, tom
- **Training data**: 12.9M clean samples + ~2M Demucs-augmented (ENST 45K + Groove 348K + EGMD 1.56M) + ~262K Slakh (generating)
- **Inference pipeline**: Audio → Demucs separation → onset detection → mel spectrogram extraction → CNN classification → structured decoding → genre-aware decoding → pattern repair → readability filter → pitch ranking → .bsm output

---

## HARDWARE

- RTX 3080Ti FE (12GB VRAM)
- AMD 9800X3D
- 32GB DDR5
- C: NVMe (code, OS)
- F: Samsung 990 Pro NVMe (datasets, 98% full)
- D: USB HDD (raw audio originals — Slakh2100, ENST, musdb18)

---

## DO NOT TOUCH — Files Under Active AI Pipeline Work

These files are being actively modified in the Claude Code session. Do not edit them:

### Critical — actively modified
- `ai-pipeline/transcription/multilabel_inference.py` — threshold fixes applied
- `ai-pipeline/training/multilabel/train_multilabel.py` — 6 safety fixes applied
- `ai-pipeline/scripts/create_demucs_augmented_dataset.py` — slakh mode added
- `ai-pipeline/runs/v5_finetune_demucs/` — current model outputs (do not delete)
- `ai-pipeline/runs/v5_multilabel_final_v3/` — original pretrained model (do not delete)

### Pipeline code — may be modified soon
- `ai-pipeline/pipeline/process.py`
- `ai-pipeline/pipeline/chart_readability.py`
- `ai-pipeline/pipeline/pattern_library.py`
- `ai-pipeline/pipeline/structured_decoder.py`
- `ai-pipeline/pipeline/genre_aware_decoder.py`
- `ai-pipeline/transcription/onset_detector.py`
- `ai-pipeline/transcription/instrument_pitch_ranker.py`

### Training infrastructure — may be modified soon
- `ai-pipeline/training/` (entire directory)
- `ai-pipeline/scripts/generate_thresholds.py`

### Data — do not modify
- `F:/datasets/multilabel_real_v3/` — training data (generating slakh2100_demucs into here)
- `ai-pipeline/training/data/manifests/` — event manifests

## SAFE TO WORK ON

Everything outside the ai-pipeline is safe:
- `desktop/` — C# desktop application
- `backend/` — FastAPI backend
- `frontend/` — React frontend
- `docs/` — documentation
- `k8s/` — deployment configs
- `.github/` — CI/CD workflows
- `shared/` — format specs

Within ai-pipeline, these are safe:
- `ai-pipeline/pipeline/server.py` — API server
- `ai-pipeline/pipeline/worker.py` — background worker
- `ai-pipeline/separation/` — Demucs separator wrapper
- `ai-pipeline/modal_app.py` — Modal cloud deployment

---

## DECISIONS MADE

1. **Start fresh from original pretrained model** (not the collapsed epoch 3 finetuned) — the finetuned model lost 3-5% F1 on clean data, had no china/splash adaptation, and was plateauing
2. **Slakh2100 is the only additional dataset needed** — investigated all datasets on D: drive, only Slakh has china/splash with onset annotations and full mixes for Demucs
3. **HDD (D: drive) is not a bottleneck for Slakh processing** — GPU Demucs processing dominates at ~20s per track vs <1s HDD read
4. **Demucs-based pipeline is the right approach for now** — alternatives investigated (end-to-end, hybrid dual-input, different separation models). Demucs is correct; current problems are data/calibration issues not architectural. Future V2 architecture could add hybrid dual-input (full mix + Demucs as 2-channel input) for higher ceiling
5. **`--reset-scheduler` is not needed** with `--pretrained-checkpoint` (scheduler is created fresh)

---

## CONTEXT FOR FUTURE SESSIONS

If this Claude Code session runs out of context again, the key information to provide is:
1. This document (`CURRENT_AI_PIPELINE_STATE.md`)
2. Check if Slakh data generation finished: look for `F:/datasets/multilabel_real_v3/slakh2100_demucs/slakh2100_demucs_manifest.json`
3. Check if v2 training started: look for `ai-pipeline/runs/v5_finetune_demucs_v2/`
4. The modified files listed in "DO NOT TOUCH" have changes applied — read them, don't start from scratch
