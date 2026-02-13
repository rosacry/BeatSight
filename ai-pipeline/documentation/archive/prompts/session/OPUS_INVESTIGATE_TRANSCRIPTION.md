# BeatSight AI Pipeline — Transcription Investigation Prompt

> **Context:** The ML pipeline transcribes drums from audio into `.bsm` beatmaps played
> in a C# desktop rhythm game. The model achieves F1=0.9397 on clean training data, but
> **when the generated beatmap is played alongside the music, it sounds obviously wrong**.
> Notes look plausible in isolation (reasonable counts, correct general balance) but the
> *pattern* does not match what a human hears. Your job is to diagnose **why** and fix it.

---

## 1. What the User Reported

> "It's still classifying all the notes incorrectly. Looking at the desktop, everything
> looks like it's plausible — the onsets are there, the notes exist — but when you play
> it with the music, you can obviously tell that something is wrong with it."

This is a **perceptual accuracy** problem, not a rendering or display bug. The desktop
app is confirmed working (notes aligned in lanes, layout correct). The problem is
upstream: the pipeline is producing incorrect instrument labels, wrong timing, or
generating patterns that don't match the actual drumming.

---

## 2. Project Layout

- **Workspace:** `c:\github\BeatSight`
- **AI pipeline:** `ai-pipeline/` (Python)
- **Desktop app:** `desktop/` (C#, osu!-framework) — **WORKING, DO NOT TOUCH**
- **Test song:** `../test_songs/0101 - Heir of Grief.flac` — RichaadEB, prog metal, 5:09, 161.5 BPM
- **Current output:** `test_beatmap.bsm` (at repo root)

---

## 3. The Model

| Property | Value |
|----------|-------|
| Architecture | CNN V5 Large, 7.1M params |
| Input | `(1, 128, 128)` mel-spectrogram |
| Output | 12-class sigmoid (multi-label) |
| Checkpoint | `runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt` |
| State dict keys | 210 keys with `backbone.` prefix |
| Training F1 | 0.9397 on Groove clean data |
| Training normalization | `[0, 1]` min-max per-sample |

**12 classes (alphabetical = model index):**
china(0), crash(1), cross_stick(2), hihat_closed(3), hihat_open(4), hihat_pedal(5),
kick(6), ride_bell(7), ride_bow(8), snare(9), splash(10), tom(11)

**Per-class thresholds** (`runs/v5_multilabel_final_v3/thresholds.json`):
```
china=0.77  crash=0.71  cross_stick=0.63  hihat_closed=0.42  hihat_open=0.57
hihat_pedal=0.51  kick=0.51  ride_bell=0.72  ride_bow=0.49  snare=0.46
splash=0.77  tom=0.58
```

**Tiered threshold scaling** (`threshold_scale=0.7` default):
- Common classes (kick, snare, hihat_*, tom, ride_bow): **no scaling** — use calibrated thresholds as-is
- Moderate domain gap (ride_bell, cross_stick): `threshold × 0.7`
- Severe domain gap (crash): `threshold × 0.49` (scale²)
- Extreme domain gap (china, splash): `threshold × 0.2401` (scale⁴)

---

## 4. Pipeline Flow

```
Audio file (.flac)
  │
  ├─[1] preprocess_audio()               Load + resample to 44100Hz
  ├─[2] separate_drums()                  Demucs htdemucs_ft → drum stem
  ├─[3] detect_onsets()                   Adaptive threshold onset detection
  ├─[4] classify_drums()                  classify_batch() per-onset:
  │      ├─ 100ms window centered on onset
  │      ├─ Adaptive hop STFT → mel filterbank → amplitude_to_db → [0,1] normalize
  │      ├─ Energy gating (skip if segment RMS < 2% track RMS)
  │      ├─ CNN inference → sigmoid probabilities
  │      └─ Per-class thresholds → {class: prob} dict per onset
  │         One onset can produce MULTIPLE hits (multi-label: kick+crash+hihat)
  │
  ├─[4b]  Viterbi/HMM decoder            Adds metadata only — does NOT change component labels
  ├─[4b2] Genre-aware decoder             Adds metadata only — explicitly preserves multi-label components
  ├─[4b3] Pattern library repair          CAN change component for low-confidence non-cymbal hits
  ├─[4c]  Readability filter              Removes low-confidence toms; preserves ALL cymbals
  ├─[4d]  Pitch ranking                   crash → crash_1/crash_2, tom → tom_1/tom_2
  └─[5]   Beatmap generation              Lane assignment → .bsm JSON
```

**Key finding from investigation:** Steps 4b and 4b2 do NOT change component labels — they
only add metadata (`decoded_state`, `beat_position`, etc.). Step 4b3 CAN change components
but only for low-confidence, non-cymbal hits. So the classifier's output at step 4 is
mostly preserved through to the final beatmap.

**This means the core problem is in step 2 (Demucs separation), step 3 (onset detection),
or step 4 (classification itself) — not post-processing.**

---

## 5. Current Output Analysis

The most recent pipeline run on "Heir of Grief" produced:

```
Total notes: 1716  (from 1542 detected onsets — multi-label means more notes than onsets)
  kick:         539    (31.4%)
  hihat_closed: 450    (26.2%)
  snare:        431    (25.1%)
  crash_1:      111    (6.5%)
  hihat_pedal:   51    (3.0%)
  china_2:       41    (2.4%)
  ride_bell_2:   27    (1.6%)
  hihat_open:    15    (0.9%)
  tom_2:         10    (0.6%)
  china_1:        9    (0.5%)
  tom_1:          8    (0.5%)
  splash_2:       6    (0.3%)
  cross_stick:    5    (0.3%)
  ride_bow_1:     5    (0.3%)
  splash_1:       4    (0.2%)
  ride_bell_1:    4    (0.2%)
```

At first glance this looks plausible for prog metal. The **counts** are in the right
ballpark. But the user says it sounds wrong. The problem is likely:

1. **WHICH onsets** get which labels — the pattern/rhythm is wrong
2. **Multi-label over-detection** — too many instruments firing per onset
3. **Systematic misclassification** — the model consistently confuses certain pairs

---

## 6. RAW DIAGNOSTIC DATA — The Smoking Gun

`diag_results.txt` shows raw sigmoid probabilities on the Demucs-separated test song
(1542 onsets):

```
Class          min   max   mean  | >0.3  >0.5  >0.7
china          0.000 0.635 0.070 |   55     6     0
crash          0.001 0.749 0.158 |  179    27     2
cross_stick    0.001 0.703 0.098 |   44     2     1
hihat_closed   0.045 0.920 0.385 | 1115   299    33
hihat_open     0.001 0.734 0.225 |  352    35     4
hihat_pedal    0.003 0.746 0.250 |  458    65     6
kick           0.005 0.890 0.458 | 1268   629   116
ride_bell      0.000 0.715 0.194 |  314    44     2
ride_bow       0.003 0.577 0.191 |  197     7     0
snare          0.011 0.870 0.393 | 1046   398    71
splash         0.000 0.552 0.052 |   16     2     0
tom            0.010 0.803 0.229 |  361    59     6
```

### 🔴 CRITICAL OBSERVATION: The model "sees" everything everywhere

Look at the **mean probabilities**:
- kick mean = **0.458** — the model gives ~46% kick probability to the AVERAGE onset
- snare mean = **0.393** — ~39% snare probability on average
- hihat_closed mean = **0.385** — ~39% hihat probability on average
- hihat_pedal mean = **0.250** — 25% on average
- hihat_open mean = **0.225** — 23% on average
- tom mean = **0.229** — 23% on average

**The model is not discriminating well on Demucs audio.** On clean training data, these
means are much more separated (eval_correct.txt shows kick mean=0.2771, snare mean=0.4600,
hihat_closed mean=0.2752 — still overlapping but on correctly-labeled data).

On Demucs audio, the model gives moderate probability to kick, snare, AND hihat for
almost every onset. With thresholds at 0.42-0.51, many onsets pass multiple thresholds
simultaneously, causing **multi-label over-detection**.

**Concretely:** 1268 of 1542 onsets (82%) have kick > 0.3. 1046 (68%) have snare > 0.3.
1115 (72%) have hihat_closed > 0.3. This massive overlap means the sigmoid outputs are
poorly calibrated for Demucs-separated audio.

### This is THE core issue: domain gap causing poor discrimination

The model was trained on clean, isolated drum recordings where each class has very
distinct spectral characteristics. Demucs separation introduces artifacts, bleed, and
spectral smearing that make everything look somewhat like kick+snare+hihat to the model.

---

## 7. SECOND ANOMALY: Catastrophic Validation Results

`eval_results.txt` shows evaluation of the SAME model checkpoint on the validation set
(`F:/datasets/multilabel_cached/val/features.npy`, 24,563 samples):

```
Micro-F1=0.0243, Macro-F1=0.0335

splash: GT=233  Pred=16,030  MeanP=0.6235    ← Model predicts splash for 65% of samples!
kick:   GT=7382 Pred=184     MeanP=0.0943    ← Almost no kicks detected
snare:  GT=10440 Pred=313    MeanP=0.1102    ← Almost no snares detected
```

BUT `eval_correct.txt` shows F1=0.9397 on Groove batch_0 (2204 samples) with the SAME
model. So the model works on some data but completely fails on the validation cache.

**Possible explanations:**
1. **Validation cache is corrupted or uses wrong normalization** — features in
   `F:/datasets/multilabel_cached/val/` may have been pre-extracted with [-1,1] normalization
   (an old bug that was fixed in inference but might not have been re-cached for eval)
2. **Label-feature misalignment** — features and labels arrays don't correspond
3. **Wrong dataset** — the val split contains data from a different distribution

**This needs investigation.** If the validation cache is corrupted, it means we have NO
reliable offline evaluation metric. We've been flying blind on model quality for real-world
audio.

**Action:** Re-extract the validation features with the current [0,1] normalization and
re-evaluate. If F1 is still terrible, the model may genuinely have a problem.

---

## 8. HYPOTHESES — Why It Sounds Wrong (Ranked by Likelihood)

### H1: Multi-Label Over-Detection (MOST LIKELY)
With poorly-discriminating sigmoid outputs on Demucs audio, the model detects 2-3
instruments per onset when there should be 1. For example:
- A kick-only hit gets labeled as kick + hihat_closed + snare
- A snare hit gets kick + snare + hihat_closed
This creates a "wall of notes" that doesn't match the actual sparse drumming pattern.

**Diagnostic:** Count how many instruments are detected per onset on average. Compare with
expected values (prog metal: usually 1-2 instruments per onset, occasionally 3 for
accented beats).

```python
import json
from collections import Counter

data = json.load(open('test_beatmap.bsm'))
hits = data['hitObjects']

# Group by time (onset)
from collections import defaultdict
onsets = defaultdict(list)
for h in hits:
    onsets[h['time']].append(h['component'])

sizes = [len(v) for v in onsets.values()]
print(f"Onsets: {len(onsets)}")
print(f"Notes per onset: mean={sum(sizes)/len(sizes):.2f}, max={max(sizes)}")
print(f"Distribution: {Counter(sizes)}")
# Expected: most onsets should have 1-2, some 3, very rarely 4+
```

### H2: Onset Timing Errors
The onset detector runs on Demucs-separated drum audio, not the original mix. Demucs
may introduce subtle timing shifts (a few ms). If onsets are consistently early or late,
the notes won't align with what the ear expects.

**Diagnostic:** Pick a 10-second section, manually tap along with the music to identify
true onset times, and compare with detected onsets. Check for systematic offset.

### H3: Systematic Confusion Between Classes
The model might consistently classify snare hits as kick (or vice versa), or put
hihat_closed on every strong transient. Even if counts look right in aggregate, the
per-onset assignments could be swapped.

**Diagnostic:** Run the model on short segments where the drumming is simple (e.g., a
basic rock beat section) and manually verify each onset's classification.

### H4: Demucs Bleed Creating Ghost Hits
Even with the 2% RMS energy gate, Demucs may let through enough bleed from other
instruments (guitar, bass) that the onset detector fires on non-drum transients.

**Diagnostic:** Compare onset count with expected drum density for the song. For a 5:09
song at 161.5 BPM, 1542 onsets is ~5 onsets per second, which is quite high but
plausible for complex metal drumming.

### H5: Post-Processing Damaging Correct Output
Pattern repair (step 4b3) might be reassigning low-confidence hits incorrectly. Though
it skips cymbals, it can change kick/snare/hihat/tom components.

**Diagnostic:** Run the pipeline with `--no-pattern-repair` flag and compare output.

---

## 9. RECOMMENDED INVESTIGATION PLAN

### Phase 1: Quantify the Problem
1. **Count instruments per onset** (script in H1 above) — is multi-label over-detection happening?
2. **Pick a 10-20 second section** of the test song with a known, simple pattern. Listen to
   it. Note what you hear (e.g., "kick on 1, snare on 2, hihat on every 8th note"). Then
   check what the pipeline produced for those exact timestamps.
3. **Run `diag_probs.py`** to see fresh raw probability distributions.

### Phase 2: Isolate the Failing Component
4. **Run pipeline with `--no-structured-decoding --no-genre-detection --no-pattern-repair`**
   to get raw classifier output without any post-processing. Compare with the full pipeline output.
5. **Run on a CLEAN drum track** (no Demucs needed — a solo drum recording) to confirm
   the model itself works correctly. If it sounds right on clean audio, the problem is
   100% Demucs domain gap.
6. **Investigate the validation cache** — re-run `eval_model.py` after re-extracting
   features with correct normalization. Is the F1=0.0243 a real model failure or corrupted data?

### Phase 3: Fix the Core Issue
Based on findings:

**If over-detection (H1):** The fix is to raise thresholds for common classes on Demucs
audio, or implement a "max N components per onset" post-filter, or use a different
decision strategy (e.g., top-K instead of all-above-threshold).

**If timing (H2):** Apply a global onset correction offset, or improve onset detection
on Demucs audio.

**If confusion (H3):** The model may need Demucs-aware fine-tuning, or a post-hoc
confusion correction matrix.

**If bleed (H4):** Increase the energy gate threshold from 2% to 5-10%, or run a
secondary onset filter that rejects non-drum transients.

---

## 10. Key File Locations

### AI Pipeline Core
| File | Lines | Purpose |
|------|-------|---------|
| `transcription/multilabel_inference.py` | ~1236 | Inference engine — `classify_batch()` L486, `get_threshold()` L339, threshold tiers L322-337 |
| `transcription/drum_classifier.py` | ~574 | Router — `_classify_drums_multilabel()` L390 builds hit dicts with multi-label output |
| `transcription/onset_detector.py` | ~350 | Onset detection on Demucs audio |
| `transcription/instrument_pitch_ranker.py` | ~782 | crash→crash_1/2, tom→tom_1/2 pitch clustering |
| `pipeline/process.py` | ~1098 | Main orchestrator — `threshold_scale=0.7` at L143, pipeline steps L275-600 |
| `pipeline/structured_decoder.py` | ~782 | Viterbi HMM — adds metadata only, does NOT change components |
| `pipeline/genre_aware_decoder.py` | ~790 | Genre decoder — adds metadata only, explicitly preserves components |
| `pipeline/pattern_library.py` | ~842 | Pattern repair — CAN change non-cymbal low-confidence components |
| `pipeline/chart_readability.py` | ~975 | Readability filter — preserves all cymbals |
| `pipeline/beatmap_generator.py` | ~1157 | .bsm JSON generation |
| `transcription/demucs_separator.py` | ~280 | Demucs htdemucs_ft separation |

### Diagnostics & Evaluation
| File | Purpose |
|------|---------|
| `diag_probs.py` | Prints raw sigmoid probability stats per class on test song |
| `diag_results.txt` | Output of diag_probs.py — shows probability distributions |
| `eval_model.py` | Evaluates model on cached validation set |
| `eval_results.txt` | **ANOMALOUS** — F1=0.0243, splash predicted 16K times |
| `eval_correct.txt` | F1=0.9397 on clean Groove batch — model works on clean data |

### Training (reference only — do not modify)
| File | Purpose |
|------|---------|
| `training/multilabel/preextract_spectrograms.py` | Feature extraction — confirms [0,1] normalization |
| `runs/v5_multilabel_final_v3/thresholds.json` | Per-class thresholds |
| `runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt` | Model checkpoint |

---

## 11. What Has Already Been Fixed (Do NOT Re-Fix)

- ✅ **Normalization matched**: Training and inference both use `[0,1]` min-max per-sample
- ✅ **Feature extraction matched**: Both use amplitude_to_db, adaptive hop_length, mel filterbank dot product
- ✅ **Energy gating**: Skips onsets with segment RMS < 2% track RMS
- ✅ **Tiered threshold scaling**: Common classes unscaled, crash at scale², china/splash at scale⁴
- ✅ **Desktop rendering**: Notes properly aligned in lanes, `cachedActiveLaneCount` fix applied
- ✅ **Pitch ranker cluster capping**: Max clusters capped at typical counts
- ✅ **Structured decoders preserve multi-label**: Both Viterbi and genre-aware decoders
  explicitly avoid overwriting component labels (comments in code confirm this)

---

## 12. How to Run

### Generate beatmap
```bash
cd c:\github\BeatSight\ai-pipeline
python -m pipeline.process --input "../test_songs/0101 - Heir of Grief.flac" --output ../test_beatmap.bsm --threshold-scale 0.7
```

### Run without post-processing (isolate classifier quality)
```bash
python -m pipeline.process --input "../test_songs/0101 - Heir of Grief.flac" --output ../test_beatmap_raw.bsm --threshold-scale 0.7 --no-structured-decoding --no-genre-detection --no-pattern-repair
```

### Raw probability diagnostics
```bash
python diag_probs.py
```

### Analyze current beatmap
```python
import json
from collections import Counter, defaultdict
data = json.load(open('../test_beatmap.bsm'))
hits = data['hitObjects']
print("Component counts:", Counter(h['component'] for h in hits))

# Multi-label over-detection check
onsets = defaultdict(list)
for h in hits:
    onsets[h['time']].append(h['component'])
sizes = [len(v) for v in onsets.values()]
print(f"Notes/onset: mean={sum(sizes)/len(sizes):.2f}, max={max(sizes)}")
print(f"Size distribution: {Counter(sizes)}")
```

### Desktop build (for visual testing)
```bash
cd c:\github\BeatSight\desktop
dotnet build BeatSight.Desktop/BeatSight.Desktop.csproj
```

---

## 13. Technical Deep-Dive: Why Discrimination Fails on Demucs Audio

The model's sigmoid outputs are well-calibrated on clean training data where each
instrument has distinct spectral signatures. After Demucs separation:

1. **Spectral bleed**: Demucs imperfectly separates instruments. The "drums" stem contains
   residual guitar/bass energy, especially in the transient attack phase that the model
   relies on for classification.

2. **Phase artifacts**: Neural source separation introduces phase discontinuities that
   create artificial spectral energy in the mel-spectrogram, making many frequency bands
   appear active when they shouldn't be.

3. **Loss of timbral detail**: Demucs smooths out the fine spectral structure that
   distinguishes crash from china, snare from tom, etc. This is why all class probabilities
   converge toward moderate values instead of being clearly high/low.

4. **The 100ms window problem**: The classifier uses a 100ms window centered on each onset.
   At 161.5 BPM (372ms per beat), this window is about 27% of a beat — long enough to
   capture bleed from adjacent drum hits, especially fast hi-hat patterns.

The result: instead of the model outputting [kick=0.95, snare=0.02, hihat=0.03] for a
kick hit, it outputs [kick=0.65, snare=0.35, hihat=0.40] — and with a threshold of 0.42
for hihat, this registers as a kick+hihat hit when it should be kick-only.

---

## 14. Non-Goals, for any of these below, you CAN look into them to see if it could be the issue but don't change anything without my permission

- Do NOT retrain the model from scratch
- Do NOT change the training pipeline or cached training data 
- Do NOT modify the desktop app (it's working correctly)
- Do NOT restructure the pipeline architecture
- Focus on: diagnosing the specific failure mode, fixing thresholds/decision logic,
  evaluating whether the validation cache is corrupted, and improving discrimination
  on Demucs-separated audio through inference-side fixes
