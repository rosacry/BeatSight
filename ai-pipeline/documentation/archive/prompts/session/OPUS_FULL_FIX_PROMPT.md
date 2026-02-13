# BeatSight — Full Fix Handoff Prompt (Generation + Rendering + Lanes)

## Archive Metadata

- **Document Type:** Session prompt (archived)
- **Status:** Historical reference only
- **Normalized On:** 2026-02-13
- **Canonical Location:** `ai-pipeline/documentation/archive/prompts/session/`
- **Current Source of Truth:** `ai-pipeline/documentation/current/`

> **Purpose:** Comprehensive handoff for continuing multi-session work on BeatSight. This prompt covers ALL outstanding issues: ML pipeline generation (crash/china under-detection, tom clustering), desktop rendering (note alignment within lanes), and lane system correctness. You have full authority to modify the pipeline, rendering pipeline, desktop code, or any other code. The ONLY restriction is: **do NOT retrain the ML model**.

---

## 1. Project Overview

**BeatSight** is a rhythm game where an ML pipeline transcribes drum audio into `.bsm` beatmap files, rendered by a C# desktop app built on osu!-framework.

- **Workspace:** `c:\github\BeatSight`
- **AI pipeline:** `ai-pipeline/` (Python 3.11+)
- **Desktop app:** `desktop/` (C# .NET 8.0, osu!-framework, Direct3D 11)
- **Test song:** `../test_songs/0101 - Heir of Grief.flac` — 5:09, RichaadEB, prog metal/rock with heavy cymbal usage (100+ crash, 100+ china, toms, ride throughout)
- **Display:** RTX 3080 Ti, 2560×1440 @ 480Hz

---

## 2. The Three Problem Areas

### 🔴 AREA 1: Pipeline Generation — Crash/China Under-Detection

**Current output:**
```
Total: 1794 hits
kick=580 ✓, hihat_closed=516 ✓, snare=501 ✓
crash=35 ❌ (should be 100+)
china=2  ❌ (should be 100+)
tom=20 ✓ (but clustering wrong — tom_3=18, tom_1=1, tom_2=1)
```

**Root cause analysis:**
- Raw sigmoid diagnostics (`diag_probs.py`) show 198 onsets with crash > 0.3, 81 with crash > 0.5
- China is worse: only 19 onsets with china > 0.3 (model struggles with china on Demucs-separated audio)
- The pipeline uses tiered domain-gap threshold scaling (already implemented):
  - Normal classes (kick, snare, hihat, tom, ride_bow): full threshold
  - `_DOMAIN_GAP_CLASSES` (ride_bell, cross_stick): `base × threshold_scale`
  - `_SEVERE_DOMAIN_GAP_CLASSES` (crash): `base × threshold_scale²`
  - `_EXTREME_DOMAIN_GAP_CLASSES` (china, splash): `base × threshold_scale³`
  - With default `threshold_scale=0.7`: crash effective = 0.49×, china = 0.343×
- **But only 35 crashes survive** to the final .bsm despite ~81 passing threshold → something downstream is eating them

**What to investigate/fix:**

#### A. Decoder chain is eating crashes
Steps 4b/4b2/4b3 can flag or reassign labels. The `structured_decoder.py` adds `decoded_state` and `state_refined` fields when Viterbi disagrees. The downstream code may be honoring these flags to DROP original component labels.

**Action:** Trace crash count through every pipeline stage:
```
After step 4 (classify): crash count = ?
After step 4b (Viterbi): crash count = ?
After step 4b2 (genre-aware): crash count = ?
After step 4b3 (pattern repair): crash count = ?
After step 4c (readability): crash count = ?
After step 4d (pitch ranking): crash count = ?
Final .bsm: crash count = ?
```

Consider **exempting cymbal classes from decoder reassignment** — multi-label classification already determined the correct label set per onset; the Viterbi/genre decoders were designed for single-label and shouldn't overwrite multi-label decisions for well-detected classes.

#### B. China under-detection is fundamentally a model limitation on Demucs audio
Options (all acceptable to try):
1. Lower china threshold much more aggressively (e.g. 0.2× or flat 0.15)
2. Add a **cymbal confusion recovery** pass: if an onset has high crash probability but the spectral profile matches china (broader, trashier), reassign some crashes to china post-hoc
3. Run spectral analysis on the drum stem to identify china-like frequency peaks
4. Accept the limitation and document it

#### C. Fix tom clustering imbalance
`instrument_pitch_ranker.py`, `_cluster_and_rank()` (line ~470):
- 20 tom hits clustered into 3 groups → tom_3=18, tom_1=1, tom_2=1
- The merge logic (cluster < 15% of total → merge into nearest) should catch this but may not be working correctly
- With 20 samples, 3 clusters is too aggressive. Consider: if `n_samples < 30`, default to `min(2, n_clusters)` or even 1
- The `_estimate_n_clusters()` (line ~556) uses elbow method with 30% inertia drop threshold
- `seed=42` is already set for reproducibility

---

### 🔴 AREA 2: Desktop Rendering — Note Alignment Within Lanes

**The problem:** Notes appear visually off-center from their lane columns. Despite switching to `RelativePositionAxes.X` to match lane background positioning, notes still look shifted.

**Current positioning code** (`PlaybackPlayfield.cs`, `updateNotePosition2D`, line ~469):
```csharp
// Note X positioning (relative):
int activeLaneCount = kickUsesGlobalLine ? Math.Max(1, laneCount - 1) : laneCount;
float laneWidth = drawWidth / activeLaneCount;
float baseNoteWidth = laneWidth * 0.45f;
float userScale = (float)NoteWidthScale.Value;
note.Width = Math.Clamp(baseNoteWidth * userScale, 40f, 160f);

int visualLaneIndex = note.Lane;
if (kickUsesGlobalLine && note.Lane > laneLayout.KickLane)
    visualLaneIndex--;

float relativeX = (visualLaneIndex + 0.5f) / activeLaneCount;
note.RelativePositionAxes = Axes.X;
note.Position = new Vector2(relativeX, y);
```

**Lane background positioning** (`updateLayout`, line ~750):
```csharp
float laneWidth = 1.0f / activeLaneCount; // Relative
// Separators at: i * laneWidth (RelativePositionAxes.X)
// Labels at: (i + 0.5f) * laneWidth (RelativePositionAxes.Both, origin BottomCentre)
// Alternating tints at: i * laneWidth, width = laneWidth (RelativePositionAxes.X)
```

**DrawableNote properties:**
```csharp
Size = new Vector2(60, 26);  // Default, overridden by updateNotePosition2D
Origin = Anchor.Centre;       // Set in constructor
// Anchor is NOT set → defaults to Anchor.TopLeft
// RelativePositionAxes.X → X position is fraction of parent width
```

**Key containers:**
- `noteLayer`: `Anchor=Centre, Origin=Centre, RelativeSizeAxes=Both, Width=PlayfieldWidthRatio(1.0f)`
- `laneBackgroundContainer`: Same as noteLayer (`Anchor=Centre, Origin=Centre, RelativeSizeAxes=Both, Width=PlayfieldWidthRatio(1.0f)`)
- Both are siblings in `InternalChildren`, so their coordinate spaces should be identical

**The mystery:** With `note.Origin = Anchor.Centre` and `note.RelativePositionAxes = Axes.X`, setting `note.X = 0.5f/7` should center the note at 1/14th of the parent width. The lane label at that same relative X should be in the same spot. Yet screenshots show notes shifted from their lane centers.

**Possible causes to investigate:**
1. **Anchor mismatch**: Note has `Anchor = TopLeft` (default). The note's position is computed as: `absoluteX = anchorOffset + relativeX × parentWidth`. With `Anchor.TopLeft`, anchorOffset.X = 0. With `Origin.Centre`, the visual center is at `relativeX × parentWidth`. This SHOULD be correct. But the lane backgrounds have `Anchor.TopLeft` too — verify that both resolve identically.

2. **noteLayer vs laneBackgroundContainer DrawWidth difference**: Both have `Width = PlayfieldWidthRatio (1.0f)` and `RelativeSizeAxes = Both`, so they should have identical DrawWidth. But the `noteLayer` is anchored to Centre — could there be a sub-pixel offset from the masking/corner radius on the parent `PlaybackPlayfield` (which has `Masking = true, CornerRadius = 12`)?

3. **`drawWidth` parameter confusion**: `updateNotePosition2D` receives `drawWidth = DrawWidth * PlayfieldWidthRatio` as a parameter and uses it for `laneWidth` calculation used in `note.Width`. But the note's `RelativePositionAxes.X` resolves against the noteLayer's DrawWidth, not the passed `drawWidth`. If the noteLayer has any padding or the parent has any inset, these could differ.

4. **The note Width is absolute while position is relative**: When `note.Width = 80px` and `note.X = 0.0714f (1/14)`, the note CENTER is at `noteLayer.DrawWidth × 0.0714f`, and the note extends ±40px from there. The lane separator is at `RelativeX = 1/7 = 0.1428`. The note right edge is at `noteLayer.DrawWidth × 0.0714 + 40`. If `noteLayer.DrawWidth = 1200px`, note center is at 85.7px, right edge at 125.7px. Separator is at 171.4px. The note should be well within the lane. So overlap into adjacent lanes shouldn't happen unless DrawWidth is much smaller than expected.

5. **Container hierarchy padding**: `PlayfieldViewportContainer` adds padding (`Horizontal = Math.Clamp(DrawWidth * 0.01f, 8f, 60f)`) and its inner container adds `Horizontal=40, Vertical=20`. The playfield sits inside `stageSurface` which has `Masking=true, CornerRadius=28`. All of this shrinks the effective playfield area. The noteLayer inside the playfield uses `Width=1.0f` relative to the PlaybackPlayfield's content area, which should already account for these constraints.

**Recommended debugging approach:**
1. Add temporary runtime logging in `Update()` or `updateNotePosition2D` to print:
   - `noteLayer.DrawWidth` vs `laneBackgroundContainer.DrawWidth`
   - First note's actual `DrawPosition.X` vs expected lane center
   - `DrawWidth` of the PlaybackPlayfield itself
2. If the values match expectations, the issue may be a frame-delay — Width and Position both being set in the same `Update()` but the layout only resolving on the next frame
3. Consider setting **both** `Anchor` and `Origin` to `Centre` on the note, or switching to a different positioning strategy entirely (e.g., put notes directly into per-lane containers)

**Alternative approach — Per-Lane Containers:**
Instead of doing math to position each note, create 7 (or N) `Container` children inside `noteLayer`, each one sized to exactly one lane width. Then set each note's `Anchor = TopCentre, Origin = Centre` and only set Y position. The lane container handles X positioning automatically. This would eliminate all alignment math.

---

### 🟡 AREA 3: Lane System Correctness

The lane system has been mostly fixed but needs end-to-end validation:

**What works:**
- `DrumLaneHeuristics.ApplyToBeatmap()` always re-resolves lanes from component strings → desktop ignores `.bsm`'s stored lane values
- `LaneLayoutFactory.CreateFromComponents()` uses `DrumLaneHeuristics.ClassifyComponent()` for proper classification
- `BuildSevenLane()` preset: Kick=3, Snare=2, HiHat=1, Tom=4, Ride=5, Crash={0,6}, China=6, Splash=6
- Lane labels use desktop canonical ordering (CR, HH, SN, KK, TM, RD, CH for 7-lane dedicated kick)

**What needs validation:**
- When `kickUsesGlobalLine = false` (dedicated kick lane), `activeLaneCount = 7`, visual lane indices = 0-6, no kick-lane skip
- When `kickUsesGlobalLine = true` (global line), `activeLaneCount = 6`, kick renders as full-width bar, visual lanes skip kick index
- The `getLaneLabelForIndex()` has different label sets for each mode — verify these match the actual lane assignments in `BuildSevenLane()`
- Test with `.bsm` files that have different component sets (e.g., missing china, extra toms)

**Current kick mode detection** (`PlaybackScreen.cs` line ~216):
```csharp
private bool KickLineEnabled =>
    (kickLaneModeSetting?.Value ?? KickLaneMode.GlobalLine) == KickLaneMode.GlobalLine;
```
When `KickLaneMode.DedicatedLane` → `KickLineEnabled = false` → `kickUsesGlobalLine = false` → 7 active lanes.

---

## 3. The ML Model (Reference Only — Do NOT Retrain)

| Property | Value |
|----------|-------|
| Architecture | CNN V5 Large, 7.1M params |
| Input | `(1, 128, 128)` mel-spectrogram |
| Output | 12-class sigmoid (multi-label) |
| Checkpoint | `runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt` |
| Validation F1 | 0.9397 on clean training data |
| Training normalization | `[0, 1]` range |

**12 classes (alphabetical = index order):** china(0), crash(1), cross_stick(2), hihat_closed(3), hihat_open(4), hihat_pedal(5), kick(6), ride_bell(7), ride_bow(8), snare(9), splash(10), tom(11)

**Calibrated thresholds** (`thresholds.json`):
```
china=0.77  crash=0.71  cross_stick=0.63  hihat_closed=0.42  hihat_open=0.57
hihat_pedal=0.51  kick=0.51  ride_bell=0.72  ride_bow=0.49  snare=0.46  splash=0.77  tom=0.58
```

---

## 4. Pipeline Architecture

```
Audio file
  │
  ├─[1] preprocess_audio()             Load + resample
  ├─[2] separate_drums()               Demucs source separation → drum stem
  ├─[3] detect_onsets()                 Find onset times
  ├─[4] classify_drums()               Per-onset classification:
  │      └─ MultiLabelDrumClassifier.classify_batch()
  │           - 100ms window centered on onset
  │           - Mel-spectrogram → [0,1] normalize → sigmoid
  │           - Energy gating (skip if RMS < 2% track RMS)
  │           - Per-class thresholds with domain-gap tiers → {class: prob}
  │      └─ One onset CAN produce multiple hits (multi-label)
  │
  ├─[4b] apply_structured_decoding()     Viterbi/HMM — adds decoded_state, state_refined flags
  ├─[4b2] apply_genre_aware_decoding()   Genre-specific transitions
  ├─[4b3] repair_with_patterns()         Pattern library repair
  ├─[4c] filter_chart_for_readability()  Physical constraints, density, clutter
  ├─[4d] InstrumentPitchRanker          crash→crash_1/2, tom→tom_1/2/3
  └─[5] generate_beatmap()              Lane assignment → .bsm JSON
```

**CRITICAL:** Steps 4b, 4b2, 4b3 can flag/modify labels. The structured decoder maps components to coarse `DrumState` (SILENCE, KICK, SNARE, HIHAT, TOM, CYMBAL, GHOST) and runs Viterbi. If Viterbi disagrees with the classifier with > 0.7 confidence, it sets `state_refined=True` and stores `decoded_state`. **Downstream code may use `decoded_state` to override `component`**, causing crash→hihat or china→ride reassignments.

---

## 5. Complete File Map

### AI Pipeline (Python)

| File | Lines | Purpose | Key Code |
|------|-------|---------|----------|
| `pipeline/process.py` | 1098 | Main orchestrator | `process_audio_file()` L102, `threshold_scale=0.7` L143, decoder chain L338-530 |
| `transcription/multilabel_inference.py` | 1231 | Inference engine | `classify_batch()` L486, `get_threshold()` with 3-tier scaling L326, `_DOMAIN_GAP_CLASSES` sets L310-325 |
| `transcription/drum_classifier.py` | ~571 | Router | `_classify_drums_multilabel()` L386, loops over detected classes L498-513 |
| `transcription/instrument_pitch_ranker.py` | 835 | Pitch clustering | `_cluster_and_rank()` L470, `_estimate_n_clusters()` L556, `_merge_small_clusters()` L619 |
| `pipeline/structured_decoder.py` | 782 | Viterbi/HMM | `apply_structured_decoding()` ~L740, `DrumState.from_component()`, adds `state_refined` flag |
| `pipeline/genre_aware_decoder.py` | 785 | Genre decoder | `apply_genre_aware_decoding()`, `GenreProfile` with transition modifiers |
| `pipeline/chart_readability.py` | 944 | Readability filter | Physical constraints, density filtering, preserves cymbals |
| `pipeline/beatmap_generator.py` | ~1157 | .bsm generation | `assign_lanes_dynamic()` L330 |
| `pipeline/dynamic_lane_layout.py` | ~825 | Dynamic lanes | `COMPONENT_CATEGORIES` L120+, `_build_lanes()` L329 |
| `diag_probs.py` | ~200 | Diagnostic | Raw sigmoid probability distributions per class |

### Desktop App (C#)

| File | Lines | Purpose | Key Code |
|------|-------|---------|----------|
| `desktop/BeatSight.Game/Screens/Playback/Playfield/PlaybackPlayfield.cs` | 909 | Main playfield | `updateNotePosition2D()` L469, `updateLayout()` L740, `getLaneLabelForIndex()` L823, `resolveLane()` L716 |
| `desktop/BeatSight.Game/Screens/Playback/Playfield/DrawableNote.cs` | 443 | Note rendering | `Origin=Centre` L132, color resolution L50-90, `SetViewMode()` L210 |
| `desktop/BeatSight.Game/Screens/Playback/PlaybackScreen.cs` | 2547 | Screen orchestrator | `loadBeatmap()` L1347, `KickLineEnabled` L216 |
| `desktop/BeatSight.Game/Screens/Playback/PlayfieldContainers.cs` | 136 | Viewport container | Dynamic padding, `stageSurface` masking with CornerRadius=28 |
| `desktop/BeatSight.Game/Mapping/DrumLaneHeuristics.cs` | 517 | Component→lane | `ApplyToBeatmap()` L190, `ResolveLane()` L23, `ClassifyComponent()` L221 |
| `desktop/BeatSight.Game/Mapping/LaneLayout.cs` | 434 | Lane presets | `BuildSevenLane()` L363, `ResolveLane()` L73 |
| `desktop/BeatSight.Game/Screens/Playback/Playfield/Views/PlayfieldViewBase.cs` | ~110 | View base | `CalculateNoteWidth()` L90 — `laneWidth * 0.45f`, clamped 40-160 |

---

## 6. Current Desktop Container Hierarchy

```
PlaybackScreen
  └─ PlayfieldViewportContainer (RelativeSizeAxes=Both)
       └─ stagePadding (Container, dynamic padding: H=DrawWidth*0.01, 8-60px; V=DrawHeight*0.015+20)
            └─ inner Container (padding: H=40, V=20)
                 └─ stageSurface (Container, Masking=true, CornerRadius=28, shadow)
                      └─ PlaybackPlayfield (CompositeDrawable, RelativeSizeAxes=Both, Masking=true, CornerRadius=12)
                           ├─ Box (background: 26,26,40)
                           ├─ laneBackgroundContainer (Anchor=Centre, Origin=Centre, RelativeSizeAxes=Both, Width=1.0)
                           │    ├─ Box (background: 20,20,30)
                           │    ├─ Alternating tints (odd lanes, RelativePositionAxes=X, alpha=8)
                           │    ├─ Lane separators (RelativePositionAxes=X, X = i/activeLaneCount, alpha=70)
                           │    └─ Lane labels (SpriteText, RelativePositionAxes=Both, X=(i+0.5)/activeLaneCount, Origin=BottomCentre)
                           ├─ TimingGridOverlay (Anchor=Centre, Origin=Centre, RelativeSizeAxes=Both, Width=1.0)
                           ├─ Container (timingStrikeZone wrapper, same axis setup)
                           ├─ noteLayer (Anchor=Centre, Origin=Centre, RelativeSizeAxes=Both, Width=1.0)
                           │    └─ DrawableNote instances (Origin=Centre, Anchor=TopLeft(default), RelativePositionAxes=X for 2D)
                           └─ laneGuideOverlay
```

**Key insight for alignment debugging:** Both `laneBackgroundContainer` and `noteLayer` are siblings with identical transform properties (`Anchor=Centre, Origin=Centre, RelativeSizeAxes=Both, Width=1.0`). Their coordinate spaces should be 100% identical. If notes are off-center, the issue is in how child `DrawableNote` transforms resolve vs how child `Box`/`SpriteText` transforms resolve.

The lane labels use `Anchor=TopLeft, Origin=BottomCentre, RelativePositionAxes=Both`. Notes use `Anchor=TopLeft(default), Origin=Centre, RelativePositionAxes=Axes.X`. Both set `X = (i + 0.5f) / activeLaneCount`. The **only difference** is the note's Anchor is implicitly TopLeft while labels explicitly set it, and the Origin vertical component differs (BottomCentre vs Centre — but this only affects Y).

---

## 7. What's Already Been Fixed (Previous Sessions)

### ✅ AI Pipeline Fixes
1. **Normalization**: All 3 inference paths use `[0,1]` range correctly
2. **Energy gating**: Skips onsets with RMS < 2% of track RMS
3. **Tiered threshold scaling**: 3-tier domain gap (normal/severe/extreme) for cymbal classes
4. **Pitch ranker cluster capping**: `_estimate_n_clusters()` caps at `typical_count[1]`

### ✅ Desktop Rendering Fixes
1. **Note width**: Changed from fixed 90px cap to `laneWidth * 0.45f * userScale`, clamped 40-160px (in PlaybackPlayfield, PlayfieldViewBase, PlayfieldViewBaseNew)
2. **Lane classification**: `CreateFromComponents()` now uses `DrumLaneHeuristics.ClassifyComponent()` instead of broken `Enum.TryParse`
3. **Lane labels**: `getLaneLabelForIndex()` uses desktop canonical ordering, not .bsm pipeline ordering
4. **Lane separators**: Alpha increased from 30→70 for visibility
5. **Lane tints**: Alternating odd-lane background tint (alpha=8) for visual distinction
6. **RelativePositionAxes.X**: Notes now use relative X positioning to match lane backgrounds. Also added `Axes.None` reset for 3D and Manuscript view modes
7. **ApplyToBeatmap**: Always re-resolves all lane assignments from component strings, ignoring stored lane values

### ❌ Still Broken
1. **Notes appear off-center** from their lane columns (screenshots confirm — investigated but not resolved)
2. **Crash count too low** (35 out of expected 100+)
3. **China count critically low** (2 out of expected 100+)
4. **Tom clustering** produces tom_3=18, tom_1=1, tom_2=1

---

## 8. How to Run

### Generate .bsm (pipeline)
```bash
cd c:\github\BeatSight\ai-pipeline
python -m pipeline.process --input "../test_songs/0101 - Heir of Grief.flac" --output ../test_beatmap.bsm --threshold-scale 0.7
```

### Raw probability diagnostics
```bash
cd c:\github\BeatSight\ai-pipeline
python diag_probs.py
```

### Inspect .bsm
```python
import json
from collections import Counter
with open('test_beatmap.bsm') as f:
    data = json.load(f)
hits = data['hitObjects']
print(Counter(h['component'] for h in hits))
print(f"Total: {len(hits)}")
```

### Desktop build
```bash
cd c:\github\BeatSight\desktop
dotnet build BeatSight.Desktop/BeatSight.Desktop.csproj
```

### Desktop tests
```bash
cd c:\github\BeatSight\desktop
dotnet test BeatSight.Tests/BeatSight.Tests.csproj
```
Currently: 200/200 tests passing.

---

## 9. Recommended Fix Order

### Phase 1: Pipeline Generation Fixes
1. **Write a diagnostic script** to trace crash/china counts through every pipeline stage (steps 4→4b→4b2→4b3→4c→4d→5). This reveals exactly where hits are lost.
2. **Fix decoder chain interaction** — if decoders are eating crashes/china, either exempt cymbal classes from decoder reassignment or increase the Viterbi disagreement threshold for cymbals.
3. **Fix china detection** — lower threshold further, or add spectral confusion recovery.
4. **Fix tom clustering** — enforce minimum cluster size relative to sample count. If `n_samples < 30`, use at most 2 clusters.
5. **Regenerate .bsm** and verify counts.

### Phase 2: Desktop Alignment Fix
1. **Add diagnostic logging** to confirm `noteLayer.DrawWidth == laneBackgroundContainer.DrawWidth` at runtime.
2. **If DrawWidths match** — the issue is subtle transform math. Consider the **per-lane container approach**: create N child containers inside `noteLayer`, each exactly 1/N relative width, and add notes to their lane's container with `Anchor=TopCentre, Origin=Centre` and only Y positioning.
3. **If DrawWidths differ** — find the container hierarchy causing the difference and fix it.
4. **Rebuild and test visually** — have user take screenshot to confirm alignment.

### Phase 3: End-to-End Validation
1. Regenerate .bsm with pipeline fixes → verify crash 100+, china 50+, tom clustering balanced
2. Load in desktop → verify all 7 lanes populated correctly
3. Verify notes centered in lanes
4. Test both kick modes (dedicated lane vs global line)

---

## 10. Things You Are Allowed To Change

- ✅ Any pipeline Python code (process.py, decoders, inference, pitch ranker, etc.)
- ✅ Any desktop C# code (playfield, note rendering, lane system, containers, etc.)
- ✅ Pipeline thresholds, scaling factors, decoder parameters
- ✅ Desktop rendering approach (per-lane containers, different positioning strategy, etc.)
- ✅ Add new files, scripts, diagnostic tools
- ✅ Change the pipeline architecture (skip decoders, add new post-processing steps, etc.)
- ✅ Change the rendering pipeline (how notes are positioned, sized, colored, etc.)

## 11. Things You Must NOT Change

- ❌ Do NOT retrain the ML model
- ❌ Do NOT modify the model checkpoint or training code
- ❌ Do NOT change the model architecture or class definitions
- ❌ Do NOT change the 12-class output mapping

---

## 12. Diagnostic Data Reference

### Raw sigmoid probabilities on test song (from `diag_probs.py`):
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

### Effective thresholds with current tiered scaling (threshold_scale=0.7):
```
Normal classes:   kick=0.51, snare=0.46, hihat_closed=0.42, tom=0.58, ride_bow=0.49, hihat_open=0.57, hihat_pedal=0.51
Domain gap (0.7×): ride_bell=0.504, cross_stick=0.441
Severe (0.49×):   crash=0.348
Extreme (0.343×): china=0.264, splash=0.264
```

With these effective thresholds and the diag_probs data:
- Crash: ~198 onsets > 0.3, ~81 > threshold (0.348). But final .bsm has only 35. **~46 crashes lost downstream.**
- China: ~19 onsets > 0.3, ~19 > threshold (0.264). But final .bsm has only 2. **~17 china lost downstream.**
- This strongly implicates the decoder chain (steps 4b-4b3) as the crash/china killer.

---

## 13. osu!-framework Positioning Reference

For debugging the desktop alignment issue, here's how osu-framework resolves positions:

```
For a Drawable with:
  Anchor = TopLeft → anchorOffset = (0, 0)
  Origin = Centre → originOffset = (Width/2, Height/2)
  RelativePositionAxes = Axes.X → X is fraction of parent DrawWidth

Visual position = parentAnchorPoint + position * relativeScale - originOffset

With Anchor.TopLeft, RelativePositionAxes.X, Origin.Centre:
  absoluteX = 0 + relativeX * parentDrawWidth
  visualLeftEdge = absoluteX - Width/2
  visualCenter = absoluteX
  
So note.X = 0.5/7 ≈ 0.0714 with parentDrawWidth = 1200px:
  absoluteX = 85.7px, center at 85.7px
  
Lane separator at RelativeX = 1/7 ≈ 0.1429 with same parent:
  absoluteX = 171.4px
  
Lane center = (0 + 171.4) / 2 = 85.7px ✓ — matches note center

Theory says alignment should be perfect. If it's not, either:
1. The parentDrawWidth differs between noteLayer and laneBackgroundContainer
2. There's a frame delay (width set one frame, position resolved next)
3. There's an interaction with Masking/CornerRadius causing content inset
```
