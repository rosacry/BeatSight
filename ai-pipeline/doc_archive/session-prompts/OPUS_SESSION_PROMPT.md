# BeatSight AI Pipeline — Continuation Session Prompt

> **Context:** You are continuing multi-session work on BeatSight's ML drum transcription pipeline. The model is good (F1=0.94 on training data), but inference on real songs produces wrong output. Several fixes have been applied. You need to diagnose and fix the remaining issues.

---

## 1. Project Overview

**BeatSight** is a rhythm game where an ML pipeline transcribes drum audio into beatmaps (`.bsm` files) rendered by a C# desktop app.

- **Workspace:** `c:\github\BeatSight`
- **AI pipeline:** `ai-pipeline/` (Python)
- **Desktop app:** `desktop/` (C#, osu!-framework)
- **Test song:** `../test_songs/0101 - Heir of Grief.flac` — 5:09, RichaadEB, prog metal/rock. **This song has heavy cymbal usage: 100+ crash hits, 100+ china hits, toms, ride throughout.**

---

## 2. The Model

| Property | Value |
|----------|-------|
| Architecture | CNN V5 Large, 7.1M params |
| Input | `(1, 128, 128)` mel-spectrogram |
| Output | 12-class sigmoid (multi-label) |
| Checkpoint | `runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt` |
| State dict keys | 210 keys with `backbone.` prefix |
| Validation F1 | 0.9397 on clean training data |
| Training normalization | `[0, 1]` — correctly implemented |

**12 classes (alphabetical, matching index):** china(0), crash(1), cross_stick(2), hihat_closed(3), hihat_open(4), hihat_pedal(5), kick(6), ride_bell(7), ride_bow(8), snare(9), splash(10), tom(11)

**File thresholds** (`runs/v5_multilabel_final_v3/thresholds.json`, calibrated on clean training data):
```
china=0.77  crash=0.71  cross_stick=0.63  hihat_closed=0.42  hihat_open=0.57
hihat_pedal=0.51  kick=0.51  ride_bell=0.72  ride_bow=0.49  snare=0.46  splash=0.77  tom=0.58
```

---

## 3. Pipeline Flow

```
Audio file
  │
  ├─[1] preprocess_audio()             Load + resample
  ├─[2] separate_drums()               Demucs source separation → drum stem
  ├─[3] detect_onsets()                 Find onset times
  ├─[4] classify_drums()               Per-onset classification:
  │      └─ _classify_drums_multilabel()
  │           └─ MultiLabelDrumClassifier.classify_batch()
  │                 - 100ms window centered on onset
  │                 - Adaptive hop STFT → mel → dB → [0,1] normalize
  │                 - Energy gating (skip if RMS < 2% track RMS)
  │                 - Sigmoid → per-class thresholds → {class: prob} dict
  │           └─ For EACH onset, for EACH detected class → creates a hit object
  │              (multi-label: one onset can produce kick+crash+hihat hits)
  ├─[4b] apply_structured_decoding()   Viterbi/HMM (can change labels!)
  ├─[4b2] apply_genre_aware_decoding() Genre-specific transitions (can change labels!)
  ├─[4b3] repair_with_patterns()       Pattern library repair (can change labels!)
  ├─[4c] filter_chart_for_readability() Removes low-confidence toms (KEEPS all cymbals)
  ├─[4d] InstrumentPitchRanker         crash→crash_1/2, tom→tom_1/2/3
  └─[5] generate_beatmap()             Lane assignment → .bsm JSON
```

**Key insight:** Steps 4b, 4b2, 4b3 can CHANGE component labels after classification. Crashes detected at step 4 might get reassigned to other classes by Viterbi/genre/pattern decoders.

---

## 4. What's Already Fixed (Do NOT Re-Fix)

### ✅ Normalization
All 3 inference paths in `multilabel_inference.py` use `[0, 1]`:
```python
mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
```

### ✅ Energy Gating
`classify_batch()` skips onsets where segment RMS < 2% of track RMS.

### ✅ Selective Threshold Scaling
Only rare classes get `threshold_scale` (default 0.7): crash, china, splash, ride_bell, cross_stick.
Common classes (kick, snare, hihat_*, tom, ride_bow) keep full calibrated thresholds.
```python
_DOMAIN_GAP_CLASSES = frozenset({'crash', 'china', 'splash', 'ride_bell', 'cross_stick'})
def get_threshold(self, class_name):
    base = self.per_class_thresholds.get(class_name, self.threshold)
    return base * self.threshold_scale if class_name in self._DOMAIN_GAP_CLASSES else base
```

### ✅ Desktop Lane Resolution
`DrumLaneHeuristics.ApplyToBeatmap()` (in `desktop/BeatSight.Game/Mapping/DrumLaneHeuristics.cs`) now always re-resolves lanes from component strings, ignoring stored lane values. Desktop 7-lane preset: crash=0, hihat=1, snare=2, kick=3, toms=4, ride=5, china/splash=6.

### ✅ Pitch Ranker Cluster Capping
`_estimate_n_clusters()` caps at `typical_count[1]` from config (crash→4, china→2, tom→4).

---

## 5. THE THREE CRITICAL PROBLEMS TO FIX

### 🔴 PROBLEM 1: Massively Under-Detecting Crashes and China (MOST IMPORTANT)

**Symptom:** Test song should have 100+ crashes and 100+ china. Current output has only **35 crashes and 2 china**.

**Diagnostic data** from `diag_probs.py` (raw sigmoid probabilities on Demucs-separated test song):

```
Class          min   max   mean  | >0.3  >0.5  >0.7
china          0.000 0.635 0.006 |   19     5     0
crash          0.000 0.749 0.052 |  198    81    12
cross_stick    0.000 0.752 0.017 |   22     9     4
hihat_closed   0.000 0.999 0.352 |  962   640   463
hihat_open     0.000 0.998 0.042 |   48    28    17
hihat_pedal    0.000 0.999 0.046 |   96    70    58
kick           0.000 1.000 0.377 |  940   715   590
ride_bell      0.000 0.715 0.014 |   27    11     1
ride_bow       0.000 0.999 0.044 |   68    37    19
snare          0.000 1.000 0.355 |  979   685   498
splash         0.000 0.552 0.004 |    4     1     0
tom            0.000 0.999 0.021 |   46    29    21
```

**Analysis of the gap:**
- **Crash:** 198 onsets have crash prob > 0.3, **81 have crash prob > 0.5**. With 0.7x scaling, effective threshold = 0.497. So ~81 onsets should pass. But final .bsm only has 35 crashes. **~46 crashes are being LOST between classification (step 4) and beatmap output (step 5).**
- **China:** Only 19 onsets have china prob > 0.3 (vs 100+ expected). Even with 0.5x scaling (threshold → 0.385), only 19 would pass. **The MODEL is failing to detect most china hits on Demucs audio.** Possible causes: (a) onset detector misses them, (b) china cymbals are systematically misclassified as crash/ride on Demucs audio, (c) Demucs severely damages china cymbal frequencies.
- **But the user says 100+ china** — so either the model genuinely cannot detect china on this audio, or the onsets aren't being found.

**Three-pronged investigation needed:**

#### A. Where are crashes going between step 4 and step 5?
The structured decoders (Viterbi at 4b, genre-aware at 4b2, pattern repair at 4b3) can **reassign component labels**. A crash detected at step 4 might get changed to hihat_closed or ride by the HMM decoder if its transition probability model says "crash is unlikely here."

**Action:** Add logging or a diagnostic that compares classified_hits BEFORE and AFTER each decoder step. Count crashes at each stage:
```python
# After step 4:   crash count = ?
# After step 4b:  crash count = ?  (Viterbi)
# After step 4b2: crash count = ?  (genre-aware)
# After step 4b3: crash count = ?  (pattern repair)
# After step 4c:  crash count = ?  (readability - should be same, cymbals preserved)
# After step 4d:  crash count = ?  (pitch ranking - should just rename crash→crash_1/2)
```

If crashes are being lost at step 4b (Viterbi), consider: should cymbal classes be exempt from structured decoding reassignment? The decoders were designed for single-label classification where each onset has ONE class. But multi-label means each onset already has the correct set of classes — the decoders should NOT be reassigning multi-label output.

#### B. Why are only 198 onsets showing crash prob > 0.3 when there should be 100+?
The song has 100+ actual crash hits, and 198 onsets have crash_prob > 0.3 which seems about right (some false positives). But only 81 have crash_prob > 0.5. The threshold at 0.7x is 0.497 → ~81 pass. This is a reasonable raw detection count (81 crashes).

The real issue might be that 81 is close to 100+ when you consider some crashes might fire at the same onset as a snare+kick hit. **81 may actually be correct for the model's capability.**

#### C. China is genuinely hard for the model on Demucs audio
Only 19 onsets have china > 0.3, vs 100+ expected. This is a fundamental model limitation on Demucs-separated audio. Options:
1. **Lower china threshold aggressively** (0.3x or even 0.2x) — but may cause false positives
2. **Accept that china detection is poor on Demucs output** — the Demucs separation may destroy the distinct timbral qualities that distinguish china from crash
3. **Run a confusion analysis:** When the ground truth is china, what does the model predict instead? If china hits get high crash probabilities, consider merging china+crash into a single "cymbal" class and assigning side/type by spectral analysis post-hoc

### 🔴 PROBLEM 2: Tom Clustering Severely Imbalanced

**Symptom:** Pitch ranker produces tom_3=18, tom_1=1, tom_2=1 (total 20 tom hits).

**Root cause:** The k-means clustering in `_cluster_and_rank()` finds 3 clusters but puts 90% of hits in one. With only 20 samples, the elbow method + k-means is unstable. The random initialization (`np.random.randint`) makes it non-reproducible.

**Fix approach:**
1. Set a **minimum cluster size** — if a cluster has < 15% of total hits, merge it into its nearest neighbor
2. Set a **random seed** for k-means reproducibility: `np.random.seed(42)` or pass a seed
3. Consider: with only 20 tom hits, clustering into 3 is aggressive. If the silhouette score or within-cluster variance is poor, default to **1 cluster** (just `tom_1`). A song needs at least ~10 hits per tom type for meaningful clustering.
4. Alternative: use a simpler pitch-based split instead of k-means. Compute spectral centroid for each hit, find natural gaps using Jenks natural breaks or simple percentile-based binning.

**Location:** `ai-pipeline/transcription/instrument_pitch_ranker.py`, specifically:
- `_estimate_n_clusters()` — line ~540
- `_cluster_and_rank()` — line ~480
- `_kmeans()` — line ~610

### 🟡 PROBLEM 3: Validate Desktop Rendering End-to-End

After fixing Problems 1 and 2, regenerate the .bsm and test in the desktop app. The desktop lane fix (always re-resolve from component strings) should display all 7 lanes properly:
- Lane 0 (left): Crash
- Lane 1: HiHat 
- Lane 2: Snare
- Lane 3: Kick (global line)
- Lane 4: Toms
- Lane 5: Ride
- Lane 6 (right): China/Splash

The desktop heuristics correctly handle ranked labels: `tom_1`→TomHigh(Left), `tom_2`→TomMid, `tom_3+`→TomLow(Right), `crash_1`→Left, `crash_2+`→Right.

Build: `dotnet build desktop/BeatSight.Desktop/BeatSight.Desktop.csproj`

---

## 6. Key File Locations

### AI Pipeline
| File | Purpose | Critical Code |
|------|---------|---------------|
| `transcription/multilabel_inference.py` (~1211 lines) | Inference engine | `classify_batch()` at L486, `get_threshold()` at L326, `_DOMAIN_GAP_CLASSES` at L322 |
| `transcription/drum_classifier.py` (~571 lines) | Router | `_classify_drums_multilabel()` at L386 — loops over ALL detected classes per onset (L498-L513) |
| `transcription/instrument_pitch_ranker.py` (~782 lines) | Pitch clustering | `_cluster_and_rank()` at L480, `_estimate_n_clusters()` at L540 |
| `pipeline/process.py` (~1092 lines) | Main orchestrator | Steps 1-5, `threshold_scale` at L143 (default 0.7), decoder chain at L340-L530 |
| `pipeline/beatmap_generator.py` (~1157 lines) | .bsm generation | `assign_lanes_dynamic()` at L330 |
| `pipeline/dynamic_lane_layout.py` (~825 lines) | Dynamic lane layout | `COMPONENT_CATEGORIES` dict at L120+, `_build_lanes()` at L329 |
| `pipeline/chart_readability.py` | Readability filter | Preserves all cymbals, removes low-confidence toms |
| `pipeline/structured_decoder.py` | Viterbi/HMM decoder | **Can reassign component labels — may remove crashes** |
| `pipeline/genre_aware_decoder.py` | Genre decoder | **Can reassign component labels — may remove crashes** |
| `diag_probs.py` | Raw probability diagnostic | Run to see per-class prob distributions |

### Desktop App
| File | Purpose |
|------|---------|
| `desktop/BeatSight.Game/Mapping/DrumLaneHeuristics.cs` (~514 lines) | Component→lane resolution (handles ranked labels) |
| `desktop/BeatSight.Game/Mapping/LaneLayout.cs` (~442 lines) | Lane presets, `BuildSevenLane()` at L363 |
| `desktop/BeatSight.Game/Screens/Playback/PlaybackScreen.cs` (~2547 lines) | Layout selection at L1364, calls ApplyToBeatmap at L1379 |
| `desktop/BeatSight.Game/Configuration/BeatSightConfigManager.cs` | Default: `DrumSevenLane` at L64 |

---

## 7. How to Run

### Pipeline (generate .bsm)
```bash
cd c:\github\BeatSight\ai-pipeline
python -m pipeline.process --input "../test_songs/0101 - Heir of Grief.flac" --output ../test_beatmap.bsm --threshold-scale 0.7
```

### Diagnostics (raw probabilities)
```bash
cd c:\github\BeatSight\ai-pipeline  
python diag_probs.py
```

### Desktop build
```bash
cd c:\github\BeatSight\desktop
dotnet build BeatSight.Desktop/BeatSight.Desktop.csproj
```

### Desktop tests
```bash
cd c:\github\BeatSight\desktop
dotnet test BeatSight.Tests/BeatSight.Tests.csproj --filter "DrumLaneHeuristicsTests"
```

### Inspect .bsm output
```python
import json
with open('test_beatmap.bsm') as f:
    data = json.load(f)
hits = data['hitObjects']
from collections import Counter
print(Counter(h['component'] for h in hits))
print(Counter(h['lane'] for h in hits))
```

---

## 8. Suggested Diagnostic Script

Write and run this to understand exactly where crashes are being lost:

```python
"""Diagnose where crashes are lost in the pipeline."""
# 1. Run steps 1-4 (classify_drums) and count crashes
# 2. Run step 4b (Viterbi) on the same data and count crashes
# 3. Run step 4b2 (genre-aware) and count crashes
# 4. Run step 4b3 (pattern repair) and count crashes
# 5. Compare counts at each stage

# Also: analyze what China hits look like to the model
# For each onset where the true class should be china:
# - What probabilities does the model assign to all 12 classes?
# - Is china being confused with crash? ride? hihat?
```

---

## 9. Current .bsm Output (For Reference)

The most recent pipeline run produced:
```
Total hits: 1794
kick: 580, hihat_closed: 516, snare: 501, hihat_pedal: 58,
ride_bell_2: 36, tom_3: 18, ride_bell_1: 18, crash_2: 15, crash_3: 15,
hihat_open: 15, cross_stick: 6, crash_1: 5, ride_bow_2: 4,
china_1: 2, ride_bow_1: 2, tom_2: 1, tom_1: 1, splash_1: 1
```

**Expected (approximate, based on user's knowledge of the song):**
- kick: ~580 ✓
- snare: ~500 ✓  
- hihat: ~500 ✓
- crash: 100+ (got 35) ❌❌❌
- china: 100+ (got 2) ❌❌❌
- tom: ~20 ✓ (but clustering is wrong)
- ride: ~60 probably OK

---

## 10. Non-Goals

- Do NOT retrain the model
- Do NOT change the training pipeline
- Do NOT change the desktop rendering pipeline beyond the existing ApplyToBeatmap fix
- Do NOT restructure the overall pipeline architecture
- Focus on: diagnosing crash/china loss, fixing thresholds, fixing decoder interactions with multi-label output, fixing pitch ranker clustering
