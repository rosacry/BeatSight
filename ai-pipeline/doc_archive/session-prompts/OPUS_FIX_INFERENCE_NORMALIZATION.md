# Opus Session Prompt: Fix the Broken Inference Pipeline

## Context — Read This First

I've spent **6 months** building BeatSight — a rhythm game with AI-generated beatmaps from real songs. The ML pipeline trains a 12-class multi-label drum transcription model (CNN V5 Large, 7.1M params) that reached **0.907 Micro-F1** on validation. The model genuinely works during training/evaluation.

**But when I run it on a real song, the output is completely wrong.** Notes don't match the music at all. I've eliminated post-processing as the cause — running with `--no-genre-detection --no-pattern-repair --no-readability-filter --no-structured-decoding` still produces garbage. The model confidently predicts 4,637 hits, but they don't correspond to the actual drums in the song.

**This session's sole mission: find and fix why inference produces wrong predictions despite a well-trained model.**

---

## The Smoking Gun: Normalization Mismatch

Through investigation, I've identified the **root cause**: the model was trained on data normalized to **[-1, 1]**, but inference feeds it data normalized to **[0, 1]**. The model has literally never seen the input distribution it receives during inference.

### Training (preextracted .npy files that the model trains on):
```python
# File: training/multilabel/preextract_spectrograms.py, lines 72-83
stft = np.abs(librosa.stft(segment, n_fft=2048, hop_length=hop_length))
mel_spec = np.dot(MEL_FB, stft)
mel_db = librosa.amplitude_to_db(mel_spec, ref=np.max)       # amplitude_to_db
mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)  # [0,1]
mel_db = mel_db * 2 - 1                                       # [-1, 1] ← TRAINING RANGE
```

### Inference (what runs on real songs):
```python
# File: transcription/multilabel_inference.py, lines 722-732
full_mel = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=128, fmax=8000, hop_length=512)
full_mel_db = librosa.power_to_db(full_mel, ref=np.max)       # power_to_db (different!)
full_mel_norm = (full_mel_db - mel_min) / (mel_max - mel_min + 1e-8)  # [0,1] ← STOPS HERE
# ❌ MISSING: full_mel_norm = full_mel_norm * 2 - 1
```

### There are actually THREE mismatches:

| Issue | Training | Inference | Severity |
|-------|----------|-----------|----------|
| **Output range** | [-1, 1] | [0, 1] | **CRITICAL** — model never saw [0,1] inputs |
| **dB conversion** | `amplitude_to_db` (20·log10) | `power_to_db` (10·log10) | **HIGH** — different magnitude scale before normalization |
| **Spectrogram method** | Manual `np.abs(stft)` → mel filterbank dot product | `librosa.feature.melspectrogram` | **MEDIUM** — potentially different windowing/padding |

Additionally, there's a possible **windowing mismatch**:
- Training: centered 100ms window around onset, adaptive `hop_length = len(segment) // 128`
- Inference batch: full-audio mel, then extract patch at `onset_frame - 16` to `onset_frame + 112` with fixed `hop_length=512`

---

## Your Tasks

### Task 1: Fix the Normalization (CRITICAL)

Apply the `* 2 - 1` scaling to match training in **ALL** inference paths in `transcription/multilabel_inference.py`:

1. **`_get_raw_probabilities_batch`** (used by adaptive thresholds) — add `full_mel_norm = full_mel_norm * 2 - 1` after the [0,1] normalization
2. **`classify_batch`** — same fix
3. **`_extract_spectrogram`** (single-onset path) — same fix

### Task 2: Fix the dB Conversion (HIGH)

Change inference to use `amplitude_to_db` to match training:

```python
# Instead of:
full_mel = librosa.feature.melspectrogram(...)
full_mel_db = librosa.power_to_db(full_mel, ref=np.max)

# Use:
full_mel = librosa.feature.melspectrogram(...)
# melspectrogram returns power, take sqrt for amplitude
full_mel_amp = np.sqrt(full_mel)
full_mel_db = librosa.amplitude_to_db(full_mel_amp, ref=np.max)
```

Or alternatively, compute it the same way as training:
```python
stft = np.abs(librosa.stft(audio, n_fft=2048, hop_length=hop_length))
mel_spec = np.dot(mel_filterbank, stft)
mel_db = librosa.amplitude_to_db(mel_spec, ref=np.max)
```

Decide which approach is cleaner and apply consistently.

### Task 3: Investigate Window/Patch Extraction Consistency (MEDIUM)

Compare how training extracts a spectrogram patch vs how inference does it:

- **Training** (`preextract_spectrograms.py`): Extracts 100ms time-domain audio window centered on onset → computes mel with adaptive hop_length → pads/truncates to 128 frames
- **Inference batch** (`classify_batch`, `_get_raw_probabilities_batch`): Computes mel over ENTIRE audio → extracts 128-frame patch at onset_frame-16 to onset_frame+112

These may produce different spectrograms for the same onset due to:
- Different hop lengths (adaptive vs fixed 512)
- Different windowing (time-domain crop vs frequency-domain crop)
- Different normalization scope (per-onset vs global)

Evaluate whether inference needs to match training's per-onset extraction, or whether the current approach is acceptable after fixing normalization.

### Task 4: Fix the On-the-fly Dataset Path Too

The `MultiLabelDrumDataset._extract_features` method in `dataset.py` also normalizes to [0,1] without the `* 2 - 1` step. This means on-the-fly training (if ever used) would also have a mismatch with batched training. Fix it for consistency.

### Task 5: Re-run Inference and Validate

After fixes, re-run:
```bash
cd ai-pipeline
python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_beatmap.bsm \
  --ml --multilabel \
  --ml-model runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3/thresholds.json \
  --adaptive-thresholds \
  --no-genre-detection --no-pattern-repair --no-readability-filter --no-structured-decoding
```

Compare the detection summary before and after. With correct normalization, you should see:
- Higher confidence scores for strong hits (kick, snare)
- More separation between classes (less "everything activates at 0.15")
- Fewer spurious detections of unlikely instruments

### Task 6: Verify in Desktop App

Build the desktop app and load the corrected beatmap:
```powershell
cd desktop
dotnet build BeatSight.Desktop
dotnet run --project BeatSight.Desktop
```

---

## Model & Training Details

| Property | Value |
|----------|-------|
| Architecture | CNN V5 Large, 7.1M params |
| Input | (1, 128, 128) — 1-channel mel spectrogram |
| Output | 12-class sigmoid (multi-label) |
| Training data | 11.6M samples from 11 sources (preextracted .npy batches) |
| Best F1 | 0.907 Micro-F1 at epoch 8 |
| Checkpoint | `runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt` |
| Thresholds | `runs/v5_multilabel_final_v3/thresholds.json` |

### 12 Classes
china, crash, cross_stick, hihat_closed, hihat_open, hihat_pedal, kick, ride_bell, ride_bow, snare, splash, tom

---

## Evidence That the Model Works (During Training)

Epoch 8 validation results (on preextracted .npy data with [-1,1] normalization):
```
Class              Prec  Recall      F1
china             0.982   0.997   0.990
crash             0.846   0.946   0.893
cross_stick       0.926   0.929   0.928
hihat_closed      0.925   0.839   0.880
hihat_open        0.820   0.826   0.823
hihat_pedal       0.847   0.775   0.809
kick              0.951   0.922   0.936
ride_bell         0.840   0.957   0.895
ride_bow          0.907   0.847   0.876
snare             0.969   0.909   0.938
splash            0.982   0.995   0.988
tom               0.928   0.934   0.931
```

## Evidence That Inference Is Broken

Adaptive thresholds on "Heir of Grief" (metal song) show suspiciously low thresholds:
```
cross_stick: threshold=0.150, max=0.477   ← model barely activates
splash:      threshold=0.150, max=0.456   ← never confident
hihat_pedal: threshold=0.150, max=0.491   ← everything is ~0.15
crash:       threshold=0.155, max=0.769   ← should be way more confident
```

This is exactly what you'd expect from feeding [0,1] data to a model trained on [-1,1]: the sigmoid outputs collapse toward 0.5 because the input is in an unfamiliar range.

---

## File Structure

```
ai-pipeline/
├── pipeline/
│   └── process.py                    # Main CLI entry point
├── transcription/
│   ├── multilabel_inference.py       # ⚡ MAIN FIX TARGET — inference code
│   ├── drum_classifier.py            # Wrapper that calls multilabel_inference
│   ├── onset_detector.py             # Onset detection
│   └── adaptive_thresholds.py        # Otsu/percentile threshold estimation
├── training/
│   └── multilabel/
│       ├── preextract_spectrograms.py  # How training data was created
│       ├── dataset.py                  # Dataset classes (BatchedMultiLabelDataset)
│       ├── train_multilabel.py         # Training script
│       └── metrics.py                  # Evaluation metrics
├── runs/
│   └── v5_multilabel_final_v3/
│       ├── best_multilabel_model_ema.pt   # 28MB trained model
│       └── thresholds.json                # Per-class thresholds
└── scripts/
    └── generate_thresholds.py         # Threshold generation script
```

---

## Files to Attach to This Session

### MUST ATTACH (Primary fix targets):
1. `ai-pipeline/transcription/multilabel_inference.py` — **THE main file to fix** (all 3 inference paths)
2. `ai-pipeline/training/multilabel/preextract_spectrograms.py` — reference for correct preprocessing
3. `ai-pipeline/training/multilabel/dataset.py` — reference for how training loads data + secondary fix

### ATTACH FOR CONTEXT:
4. `ai-pipeline/transcription/drum_classifier.py` — wrapper that calls the inference
5. `ai-pipeline/pipeline/process.py` — the CLI pipeline (to verify end-to-end)
6. `ai-pipeline/transcription/onset_detector.py` — verify onset detection is sane
7. `ai-pipeline/transcription/adaptive_thresholds.py` — threshold estimation logic

### ATTACH FOR VALIDATION:
8. `ai-pipeline/runs/v5_multilabel_final_v3/thresholds.json` — current thresholds
9. This prompt file itself

### OPTIONAL (if context budget allows):
10. `ai-pipeline/pipeline/beatmap_generator.py` — how hits become beatmap notes
11. `ai-pipeline/scripts/generate_thresholds.py` — may need the same normalization fix

---

## Success Criteria

1. **Normalization matches**: Inference produces [-1, 1] spectrograms, matching training
2. **dB conversion matches**: Same `amplitude_to_db` path as training
3. **Model produces high-confidence predictions**: Kick/snare/hihat should have probabilities >0.8 on clear hits, not the anemic 0.15-0.5 range we currently see
4. **Adaptive thresholds are sensible**: Otsu thresholds should be 0.3-0.7, not 0.15 for everything
5. **Beatmap sounds right**: Notes align with audible drum hits when played back
6. **Re-run `generate_thresholds.py`**: After fixing inference, the threshold script uses the same inference code, so thresholds should also improve

---

## Commands

```bash
# Run inference pipeline
cd ai-pipeline
python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_beatmap.bsm \
  --ml --multilabel \
  --ml-model runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3/thresholds.json \
  --adaptive-thresholds \
  --no-genre-detection --no-pattern-repair --no-readability-filter --no-structured-decoding

# Regenerate thresholds (after fixing normalization)
PYTHONPATH=. python scripts/generate_thresholds.py \
  --model runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
  --dataset F:/datasets/multilabel_real_v3

# Build and run desktop app
cd ../desktop
dotnet build BeatSight.Desktop
dotnet run --project BeatSight.Desktop
```
