# Data Audit for Advanced Drum Techniques

## 1. Requested Techniques vs. Current Data

### New Instruments / Classes
| Technique | Status in Groove MIDI | Status in MedleyDB | Action Required |
|-----------|----------------------|--------------------|-----------------|
| **Cowbell** | Mapped to `aux_percussion` (Note 56) | Mapped to `aux_percussion` | Promote to class `cowbell` |
| **Splash** | Mapped to `splash` (Note 55) | Not explicitly mapped (maybe in `cymbal`?) | Promote to class `splash` |
| **China** | Mapped to `china` (Notes 52, 54) | Not explicitly mapped | Already in 12-class list |
| **Ride Bell** | Mapped to `ride_bell` (Notes 53, 59) | Mapped to `ride_bell` | Already in 12-class list |
| **Tambourine**| Not in Groove map? | Mapped to `aux_percussion` | Promote to class `tambourine` |
| **Cross-stick**| Mapped to `cross_stick` (Note 37) | Not explicitly mapped | Promote to class `cross_stick` |

### Articulations (Variations of existing instruments)
| Technique | Status in Groove MIDI | Status in MedleyDB | Action Required |
|-----------|----------------------|--------------------|-----------------|
| **Rimshot** | Mapped to `snare` w/ `strike_position="rimshot"` (Note 40) OR `rimshot` (Note 39) | Not explicitly mapped | Add `articulation` head or separate class `snare_rimshot` |
| **Ghost Notes**| Inferred via velocity < 0.25 (`bucket_velocity`) | Not explicitly mapped | Use velocity/dynamics bucket |
| **Hi-Hat Splash**| Mapped to `hihat_foot_splash` (Note 26) | Not explicitly mapped | Promote to class `hihat_splash` |
| **Hi-Hat Bark** | Not mapped (requires timing logic) | Not mapped | Infer from Open -> Closed quickly? |

### Performance Features (Gestures)
| Technique | Status | Action Required |
|-----------|--------|-----------------|
| **Flam** | Not labeled in MIDI/Audio | Needs heuristic detection (double onset < 30ms) or synthetic generation |
| **Roll** | Not labeled | Needs heuristic (rapid onsets) or synthetic generation |
| **Choke** | Not labeled (Note off?) | Hard to detect in audio without explicit labels. |
| **Swell** | Not labeled | Hard to detect. |

## 2. Pipeline Bottlenecks
1.  **`ingest_medleydb.py`**: Maps many distinct instruments to `aux_percussion`.
2.  **`ingest_groove.py`**: Has rich data (`cross_stick`, `splash`, `rimshot`) but...
3.  **`collect_training_data.py`**: Explicitly rejects any label not in the `DRUM_COMPONENTS` list (12 classes).
4.  **`ml_drum_classifier.py`**: Hardcoded to 12 output classes.

## 3. Proposed Schema Expansion
We should move from a flat 12-class list to a hierarchical or expanded list.

**Option A: Expanded Flat List (Easier to implement)**
Add `cowbell`, `splash`, `cross_stick`, `snare_rimshot`, `hihat_splash` to the main list.
Total classes: ~18-20.

**Option B: Multi-Head Output (Better for Articulations)**
Head 1: Instrument (Kick, Snare, HiHat, Tom, Cymbal, Aux)
Head 2: Articulation (Normal, Rimshot, Bell, Edge, Cross-stick)
Head 3: Performance (Normal, Flam, Roll, Ghost)

**Recommendation**: Start with **Option A** for distinct instruments (Cowbell, Splash) and **Option B** concepts for Snare/HiHat variations if possible, or just distinct classes (`snare_rimshot`) for simplicity.

## 4. Missing Data Strategy
-   **Flams/Rolls**: We likely need to *synthesize* these using the `beatmap_generator` logic reversed, or data augmentation (taking single hits and layering them).
-   **Chokes**: Very hard to find in current datasets. Might need to record custom samples or find a specific dataset.
