# BeatSight AI Pipeline — Investigate & Fix Finetuned Model Output Quality

## Archive Metadata

- **Document Type:** Session prompt (archived)
- **Status:** Historical reference only
- **Normalized On:** 2026-02-13
- **Canonical Location:** `ai-pipeline/documentation/archive/prompts/session/`
- **Current Source of Truth:** `ai-pipeline/documentation/current/`

## YOUR MISSION

You are continuing development on **BeatSight**, a commercial AI drum transcription system. The goal: **the best AI drum transcription model in the world** — where any user uploads any song and gets the most accurate visual drum transcription possible.

A fine-tuning run (Demucs domain gap augmentation) has been in progress, and initial testing of the current best checkpoint reveals **severe output quality problems**. Your job is to **investigate root causes and fix them**. Do NOT tune for a specific test song — all fixes must be universal.

---

## PROJECT ARCHITECTURE

BeatSight has three main components:
1. **AI Pipeline** (`ai-pipeline/`) — Python. Audio → `.bsm` beatmap files. Training, inference, pipeline orchestration.
2. **Desktop App** (`desktop/`) — C#/osu!framework rhythm game that plays `.bsm` files.
3. **Backend** (`backend/`) — Python FastAPI backend for cloud processing.

The AI pipeline is the focus. The desktop app and backend are stable.

---

## MODEL ARCHITECTURE

- **CNN V5 Large**: 7,143,308 parameters
- **Input**: (1, 128, 128) mel-spectrogram — 1 channel, 128 mel bins, 128 time frames
- **Output**: 12-class sigmoid (multi-label, not softmax)
- **12 drum classes** (index order):
  - 0: china
  - 1: crash
  - 2: cross_stick
  - 3: hihat_closed
  - 4: hihat_open
  - 5: hihat_pedal
  - 6: kick
  - 7: ride_bell
  - 8: ride_bow
  - 9: snare
  - 10: splash
  - 11: tom

---

## THE DEMUCS DOMAIN GAP APPROACH — FULL BACKSTORY

### The Problem
The model was originally trained on **clean, isolated drum stems** (ENST, Groove MIDI, EGMD datasets with synthesized/recorded clean drums). But at inference time, the pipeline uses **Demucs** (a neural source separation model) to extract drums from full-mix audio. Demucs output has artifacts, residual bleed, and spectral differences from clean stems. This creates a **domain gap** — the model sees different spectral characteristics at inference than it was trained on.

### The Evidence
The pre-finetune model achieved F1=0.9397 on clean validation data but performed significantly worse on real songs processed through Demucs. Specific symptoms:
- Missing cymbal hits (china, splash especially)
- Low overall confidence on real songs
- Inconsistent detection of ride/crash variants

### The Solution (Option B — Fine-tuning with Demucs augmentation)
Rather than retraining from scratch, we fine-tune the existing best checkpoint by:
1. Taking the original clean training audio for each dataset
2. Mixing each clean drum stem with a random non-drum accompaniment (from musdb18) at realistic SNR ratios
3. Running the mix through Demucs to get the separated drum stem
4. Using the Demucs output as the new training audio, paired with the original clean labels

This teaches the model to recognize drum hits in Demucs-processed audio, closing the domain gap.

### Augmentation Completed Successfully
Three phases of augmentation were completed:
- **Phase 1 (ENST)**: 45,014 samples, 23 batches
- **Phase 2 (Groove MIDI)**: 348,091 samples, 176 batches  
- **Phase 3 (EGMD)**: 1,558,959 samples, 780 batches (5,000 files in 7.5 hours)

All stored in `F:/datasets/multilabel_real_v3/` alongside the original clean data.

---

## CURRENT TRAINING STATUS

### Fine-tuning Configuration
```
Checkpoint: runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt (F1=0.9397 on clean)
Output dir: runs/v5_finetune_demucs/
Loss: CB-Focal (beta=0.999, gamma=2.0)
LR: 2e-5 cosine → 2e-7
EMA decay: 0.9995
Epochs: 20
Batch: 128 × 5 grad accum = 640 effective
Warmup: 1 epoch
Label smoothing: 0.02
SpecAugment: drum-specific
Gradient checkpointing: on
AMP: bfloat16
```

### Dataset Weights (14 sub-datasets, 13,378,210 train + 1,508,001 val)
```
Demucs-augmented (boosted):
  enst_drums_demucs=20x
  egmd_demucs=15x
  groove_midi_demucs=15x

Acoustic oversample 10x:
  cambridge_multitrack, idmt_smt_drums_v2, signaturesounds
  telefunken, acoustic_synth, enst_drums
```

### Training Progress (as of last check)
- **Epoch 4/20, ~58% through** (batch 60,630/104,517)
- Epochs 1-3 complete, steady improvement, no overfitting signs:
  - E1: Micro-F1=0.8515, Macro-F1=0.8678, Val Loss=0.0223
  - E2: Micro-F1=0.8560, Macro-F1=0.8696, Val Loss=0.0218
  - E3: Micro-F1=0.8589, Macro-F1=0.8712, Val Loss=0.0215
- ~3.4 hrs/epoch, 104,517 batches per epoch
- Weakest classes: hihat_pedal (0.763), hihat_open (0.781), ride_bow (0.810)
- Near-perfect on val: china (0.992), splash (0.987)

### Hardware
- RTX 3080Ti FE (12GB VRAM), AMD 9800X3D, 32GB DDR5
- F: NVMe (datasets, 98% full), D: USB HDD (raw originals), C: NVMe (code)

---

## THE CRITICAL PROBLEM — OUTPUT QUALITY REGRESSION

### Test Setup
- Test song: `../test_songs/0101 - Heir of Grief.flac` — RichaadEB, prog metal, ~5:09
- Heavy cymbal usage: many crashes, many chinas, splashes, ride, toms, fills throughout
- Pipeline: full pipeline with Demucs separation → onset detection → classification → post-processing → .bsm

### Threshold Tuning Results (on finetuned model)
Tuned thresholds (`runs/v5_finetune_demucs/thresholds.json`):
```json
{
  "china": 0.73, "crash": 0.67, "cross_stick": 0.56,
  "hihat_closed": 0.41, "hihat_open": 0.59, "hihat_pedal": 0.49,
  "kick": 0.41, "ride_bell": 0.63, "ride_bow": 0.45,
  "snare": 0.41, "splash": 0.81, "tom": 0.51
}
```
Tuned metrics: micro_f1=0.8787, macro_f1=0.8883

Old thresholds (pre-finetune, `runs/v5_multilabel_final_v3/thresholds.json`):
```json
{
  "china": 0.77, "crash": 0.71, "cross_stick": 0.63,
  "hihat_closed": 0.42, "hihat_open": 0.57, "hihat_pedal": 0.51,
  "kick": 0.51, "ride_bell": 0.72, "ride_bow": 0.49,
  "snare": 0.46, "splash": 0.77, "tom": 0.58
}
```

### 5-WAY .BSM COMPARISON (Same Song "Heir of Grief")

| File | Total Hits | Notes/sec | Crash | China | Splash | Kick | Snare | Hi-Hat Cl | Ride |
|------|-----------|-----------|-------|-------|--------|------|-------|-----------|------|
| test_beatmap.bsm (original) | 2135 | 7.6 | 129 | 29 | 149 | 537 | 309 | 267 | 249 |
| test_beatmap_threshold_1.bsm | 1843 | 6.5 | 4 | 0 | 0 | 530 | 284 | 380 | 171 |
| test_beatmap_fixed.bsm | 2452 | 8.7 | 129 | 17 | 148 | 534 | 309 | 378 | 262 |
| test_beatmap_fixed_v2.bsm | 2172 | 7.7 | 14 | 1 | 0 | 554 | 286 | 349 | 216 |
| **test_beatmap_finetuned_demucs.bsm** | **1413** | **5.0** | **16** | **0** | **0** | **547** | **285** | **131** | **182** |

**THE FINETUNED MODEL IS THE WORST PERFORMER** — fewest total hits (1413 vs 1843-2452), zero china, zero splash, and dramatically fewer hi-hat detections.

### Finetuned Output Breakdown
```
kick:         547 (38.7%)
snare:        285 (20.2%)
ride_bow_1:   182 (12.9%)
hihat_closed: 131 (9.3%)
tom_1:         73 (5.2%)
hihat_open:    69 (4.9%)
tom_2:         63 (4.5%)
hihat_pedal:   36 (2.5%)
crash_1:       10 (0.7%)
cross_stick:    7 (0.5%)
crash_2:        6 (0.4%)
ride_bell_1:    4 (0.3%)
CHINA:          0 (0.0%)  ← Song has 100+ china hits
SPLASH:         0 (0.0%)  ← Song has splashes throughout
```

### Overall Confidence
- Beatmap-level confidence: **0.468** (very low)
- Mean onset confidence across the file: many onsets below 0.5

---

## USER-REPORTED PROBLEMS (EXAMPLES — NOT EXHAUSTIVE)

The user explicitly states these are **EXAMPLE problems only**. Do NOT assume these are the only issues:

1. **Severely undermapped** — Only generates ~1413 hits when the song should have 2000-3000+. Missing a large percentage of total drum events.
2. **Timing may be off** — Hits might not align perfectly with actual drum strikes.
3. **Zero chinas detected** — The song has extensive china cymbal usage (100+ hits). Not a single one detected.
4. **Zero splashes detected** — The song has splashes. None detected.
5. **Model doesn't seem confident** — Overall confidence 0.468, many individual detections are borderline.
6. **Doesn't catch fills or fast notes** — Fast drum fills (16th/32nd note runs) are being lost.
7. **Many other undiscovered issues** — The user has NOT done an exhaustive analysis. There could be systematic problems with timing, labeling, onset detection, post-processing, or any other part of the pipeline.

**CRITICAL INSTRUCTION**: Investigate ALL aspects of the pipeline. Do NOT laser-focus only on the listed problems. These are symptoms — find the root causes.

---

## FULL PIPELINE FLOW (Audio → .bsm)

The pipeline in `pipeline/process.py` (1,122 lines) runs these steps:

```
Step 1: Preprocess audio (load, resample)
Step 2: Demucs source separation (extract drums stem)
Step 3: Onset detection (transcription/onset_detector.py, 426 lines)
         → Adaptive onset detection with min distance from tempo
Step 4: Classification (transcription/multilabel_inference.py, 1,376 lines)
         → Extract mel-spectrogram window around each onset
         → Run through CNN V5 Large
         → Apply thresholds (with tiered domain-gap scaling)
Step 4b: Structured decoding (pipeline/structured_decoder.py, 781 lines)
         → Does NOT change component labels — metadata only
Step 4b2: Genre-aware decoding (pipeline/genre_aware_decoder.py, 784 lines)
         → Does NOT change component labels — explicitly commented
Step 4b3: Pattern repair (pipeline/pattern_library.py, 841 lines)
         → DOES change low-confidence (<0.6) non-cymbal labels
Step 4c: Readability filter (pipeline/chart_readability.py, 974 lines)
         → Removes hits (sets kept=False), protects cymbals
         → Filtered 98 hits in latest run
Step 4d: Pitch ranking (transcription/instrument_pitch_ranker.py, 840 lines)
         → Adds suffixes: crash→crash_1/crash_2, tom→tom_1/tom_2, etc.
Step 5: Beatmap generation (.bsm JSON output)
```

### CRITICAL: Threshold Scaling System

In `transcription/multilabel_inference.py`, the `get_threshold()` function (around L336) applies **tiered domain-gap scaling**:

```python
# Domain gap class categories
_MODERATE_DOMAIN_GAP_CLASSES = {"ride_bell", "cross_stick", "crash"}
_SENSITIVE_DOMAIN_GAP_CLASSES = {"china", "splash"}

# Tiered scaling with threshold_scale=0.7 (default):
# Common classes (kick, snare, hihat_*, tom, ride_bow):
#   threshold * scale^0.25 = threshold * 0.915  (~8.5% reduction)
# Moderate classes (crash, ride_bell, cross_stick):
#   threshold * scale^0.5 = threshold * 0.837   (~16% reduction)
# Sensitive classes (china, splash):
#   threshold * scale^0.75 = threshold * 0.766   (~24% reduction)
```

**KEY INVESTIGATION POINT**: This scaling was designed to compensate for domain gap when the model was trained on clean data but inference uses Demucs. Now that the model IS trained on Demucs data, this additional scaling might be:
- Redundant (domain gap should be smaller now)
- But the new thresholds were tuned on MIXED val data (both clean and Demucs), so the relationship is complex
- Despite the ~24% reduction on china/splash thresholds, ZERO chinas/splashes are detected — suggesting the model's raw probabilities for these classes are extremely low on real Demucs-separated audio

### Pipeline CLI Args (process.py)
```
--input                    Input audio file
--output                   Output .bsm file
--multilabel-model         Path to model checkpoint
--multilabel-thresholds    Path to thresholds.json
--threshold-scale          Threshold scale factor (default 0.7)
--adaptive-thresholds      Enable adaptive thresholds
--no-structured-decoding   Disable step 4b
--no-genre-detection       Disable step 4b2
--no-pattern-repair        Disable step 4b3
--no-readability-filter    Disable step 4c
```

---

## KEY CODEBASE FILES

### Inference & Detection
| File | Lines | Purpose |
|------|-------|---------|
| `transcription/multilabel_inference.py` | 1,376 | Core inference engine, 3 paths, threshold scaling |
| `transcription/onset_detector.py` | 426 | Adaptive onset detection |
| `transcription/instrument_pitch_ranker.py` | 840 | Assigns pitch suffixes |

### Pipeline Post-Processing
| File | Lines | Purpose |
|------|-------|---------|
| `pipeline/process.py` | 1,122 | Main orchestrator |
| `pipeline/structured_decoder.py` | 781 | Structural analysis (no label changes) |
| `pipeline/genre_aware_decoder.py` | 784 | Genre detection (no label changes) |
| `pipeline/pattern_library.py` | 841 | Pattern repair (CHANGES low-conf labels) |
| `pipeline/chart_readability.py` | 974 | Readability filter (REMOVES hits) |

### Training & Evaluation
| File | Lines | Purpose |
|------|-------|---------|
| `training/multilabel/train_multilabel.py` | 1,867 | Training loop, --resume and --pretrained-checkpoint |
| `training/multilabel/preextract_spectrograms.py` | 239 | Pre-extraction (uses SR=44100, amplitude_to_db) |
| `scripts/generate_thresholds.py` | 387 | Per-class threshold optimization on val data |
| `scripts/create_demucs_augmented_dataset.py` | 1,647 | Demucs augmentation (completed) |

### Diagnostics
| File | Lines | Purpose |
|------|-------|---------|
| `diag_probs.py` | 98 | Diagnostic tool — WARNING: uses OLD mismatched feature pipeline |
| `tools/transcribe_song.py` | 249 | CLI inference tool |

### Feature Extraction Details (ALL paths now use)
- Sample rate: 22050 (inference) — NOTE: preextract uses 44100
- Normalization: [0,1] range (min-max after power_to_db)
- dB conversion: power_to_db 
- Window: asymmetric extraction around onset
- Mel bins: 128, Time frames: 128

---

## INVESTIGATION AREAS (Prioritized)

### 1. Raw Model Probability Analysis (HIGHEST PRIORITY)
Before touching any pipeline code, diagnose what the model is actually outputting:
- Run inference directly on a few segments and dump raw sigmoid probabilities
- Compare probabilities for the same audio between old model and new finetuned model
- Check: Are china/splash probabilities genuinely near-zero, or are they above zero but below threshold?
- Check: Is the model outputting reasonable probabilities for ALL classes?

**Diagnostic approach**: Create a script that bypasses the full pipeline, loads the model, extracts spectrograms from known segments (where chinas/crashes exist), and prints raw class probabilities.

### 2. Threshold & Scaling Interaction
- The splash threshold is 0.81 — very high. Even with 24% scaling reduction (→ 0.62), are raw probs reaching 0.62?
- Are the tuned thresholds appropriate for Demucs-separated real audio?
- Does threshold_scale=0.7 still make sense for a Demucs-trained model?
- Try running with threshold_scale=1.0 (no scaling) since the model should now handle Demucs natively

### 3. Onset Detection Quality
- Are onsets being detected at all for fast fills?
- Is the minimum distance parameter too large, causing close-together onsets to merge?
- Check onset_detector.py's adaptive parameters

### 4. Feature Extraction Consistency
- Compare training feature extraction (preextract at SR=44100 with amplitude_to_db) vs inference feature extraction (SR=22050 with power_to_db)
- This SR mismatch could be significant! Training sees 44100 spectrograms, inference generates 22050 spectrograms
- Verify normalization is truly identical between training and inference paths

### 5. Post-Processing Over-Filtering
- chart_readability.py filtered 98 hits — is this too aggressive?
- pattern_library.py changes low-confidence labels — could it be swapping cymbals to other classes?
- Run pipeline with `--no-pattern-repair --no-readability-filter` to see raw model output

### 6. BPM/Tempo Detection
- The beatmap shows bpm=126.82 but analysis.tempo=60.09 — are these consistent?
- Wrong tempo could cause timing issues and affect onset detection minimum distance

### 7. Training Data Balance
- The Demucs datasets have massive sample counts (1.5M EGMD alone) — are they overwhelming acoustic/clean data?
- Check if the model is "forgetting" what cymbals sound like in clean contexts
- Val data is mixed (clean + Demucs) — are per-class F1 scores masking issues?

### 8. Epoch Checkpoint Selection
- Current best is from epoch 3 — training is still running
- Later epochs may improve, but could also overfit to Demucs characteristics
- May need to test multiple epoch checkpoints

---

## COMMANDS FOR INVESTIGATION

### Run pipeline on test song (standard)
```bash
cd /c/github/BeatSight/ai-pipeline
python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_beatmap_finetuned_demucs.bsm \
  --multilabel-model runs/v5_finetune_demucs/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_finetune_demucs/thresholds.json \
  --threshold-scale 0.7
```

### Run pipeline WITHOUT post-processing (raw model output)
```bash
python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_beatmap_raw.bsm \
  --multilabel-model runs/v5_finetune_demucs/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_finetune_demucs/thresholds.json \
  --threshold-scale 1.0 \
  --no-structured-decoding \
  --no-genre-detection \
  --no-pattern-repair \
  --no-readability-filter
```

### Run threshold tuning
```bash
python scripts/generate_thresholds.py \
  --model-path runs/v5_finetune_demucs/best_multilabel_model_ema.pt \
  --dataset-path F:/datasets/multilabel_real_v3 \
  --output-path runs/v5_finetune_demucs/thresholds.json
```

### Compare with OLD model
```bash
python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_beatmap_old_model.bsm \
  --multilabel-model runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3/thresholds.json \
  --threshold-scale 0.7
```

### Resume training (if it stops)
Same full training command but use `--resume runs/v5_finetune_demucs/latest_checkpoint.pt` instead of `--pretrained-checkpoint`.

---

## EXISTING .BSM FILES FOR COMPARISON

All in the repo root (`C:/github/BeatSight/`):
1. `test_beatmap.bsm` — Original model, original pipeline (Feb 6 08:59, 541KB) — 2135 hits
2. `test_beatmap_threshold_1.bsm` — With threshold tuning (Feb 6 09:04, 494KB) — 1843 hits
3. `test_beatmap_fixed.bsm` — After normalization fix (Feb 6 09:28, 594KB) — 2452 hits
4. `test_beatmap_fixed_v2.bsm` — After further fixing (Feb 6 09:58, 549KB) — 2172 hits
5. `test_beatmap_finetuned_demucs.bsm` — Finetuned model (Feb 7 10:32, 424KB) — 1413 hits ← WORST

---

## WHAT SUCCESS LOOKS LIKE

At minimum, the finetuned model should:
- Output MORE hits than the pre-finetune model on this song (ideally 2500-3500+ for a dense prog metal track)
- Detect china hits (dozens to 100+)
- Detect splash hits
- Have higher overall confidence (>0.65)
- Catch fast fills and 16th/32nd note passages
- Work well on ANY song, not just this test song

The ultimate goal: output quality that a professional drummer would recognize as an accurate transcription.

---

## IMPORTANT NOTES

1. **Training is still running** — Don't interrupt it. Use the current `best_multilabel_model_ema.pt` for testing. Later checkpoints may be better.
2. **Don't overfit to the test song** — All changes must generalize. Test on multiple songs if possible.
3. **The problems listed are EXAMPLES** — Investigate systematically, don't just fix the obvious issues.
4. **Check for root causes** — A single root cause (like SR mismatch between training and inference) could explain many symptoms.
5. **The SR discrepancy is suspicious** — Training preextract uses SR=44100, inference uses SR=22050. This is worth investigating deeply.
6. **F: drive is 87% full** — User has 227GB free of 1.81TB on their F: drive
