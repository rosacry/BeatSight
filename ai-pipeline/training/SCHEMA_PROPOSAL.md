# Expanded Drum Classifier Schema Proposal

To support the advanced techniques requested (Cowbell, Rimshots, Flams, etc.), we propose expanding the classifier from 12 classes to **25 classes**.

## 1. New Class List

| ID | Label | Description | Source Data Availability |
|----|-------|-------------|--------------------------|
| 0 | `kick` | Standard Bass Drum | High |
| 1 | `snare_center` | Standard Snare Hit | High |
| 2 | `snare_rimshot` | Stick hits head and rim (loud, cracking) | Groove MIDI (Note 40/39) |
| 3 | `snare_cross_stick` | Stick on rim (clicky) | Groove MIDI (Note 37) |
| 4 | `snare_off` | Snare wires off (tom-like) | Low (Rare in datasets) |
| 5 | `hihat_closed` | Closed Hi-Hat | High |
| 6 | `hihat_open` | Open Hi-Hat | High |
| 7 | `hihat_half` | Half-Open Hi-Hat (Sizzle) | Medium (Groove has CC data) |
| 8 | `hihat_pedal` | Foot Chick | Groove MIDI (Note 44) |
| 9 | `hihat_splash` | Foot Splash (fsshh) | Groove MIDI (Note 26) |
| 10 | `tom_high` | High Tom | High |
| 11 | `tom_mid` | Mid Tom | High |
| 12 | `tom_low` | Low/Floor Tom | High |
| 13 | `ride_bow` | Stick tip on Ride body | High |
| 14 | `ride_bell` | Stick shoulder on Ride bell | Groove MIDI (Note 53) |
| 15 | `ride_edge` | Crashing the Ride | Medium |
| 16 | `crash_1` | Standard Crash | High |
| 17 | `crash_2` | Secondary Crash | High |
| 18 | `china` | China Cymbal (Trashy) | High |
| 19 | `splash` | Splash Cymbal (Short) | Groove MIDI (Note 55) |
| 20 | `cowbell` | Cowbell | Groove (Note 56), MedleyDB |
| 21 | `tambourine` | Tambourine | MedleyDB |
| 22 | `clap` | Hand Clap | MedleyDB |
| 23 | `shaker` | Shaker | MedleyDB |
| 24 | `silence` / `background` | No drum | N/A |

## 2. Handling Performance Techniques

Some requests are **Temporal/Gestural** rather than Timbral, meaning they are defined by *time* rather than just *sound*.

| Technique | Handling Strategy |
|-----------|-------------------|
| **Flam** | **Post-Processing**: Detect two `snare_center` hits within < 50ms. The Beatmap Generator will merge them into a "Flam" object. |
| **Drag / Ruff** | **Post-Processing**: Detect 2-3 soft `snare_center` hits before a loud one. |
| **Roll (Single/Double)** | **Post-Processing**: Rapid sequence of hits. |
| **Press/Buzz Roll** | **New Class?**: A "Buzz" has a distinct sustained sound. We might need a `snare_buzz` class if the dataset supports it. (Currently Low availability). |
| **Ghost Notes** | **Dynamics**: These are just `snare_center` with `velocity < 0.3`. The classifier should predict velocity/dynamics. |
| **Cymbal Choke** | **Audio Event**: Hard to detect. Requires detecting the *sudden silence* after a hit. |

## 3. Implementation Plan

1.  **Update Ingestion Scripts**:
    -   Modify `ingest_groove.py` to map notes 37, 40, 26, 55, 56 to the new labels instead of generic ones.
    -   Modify `ingest_medleydb.py` to map "cowbell", "tambourine" to their own classes.
2.  **Update `collect_training_data.py`**:
    -   Expand `DRUM_COMPONENTS` list.
    -   Regenerate training data (this will take time, but we can do it after the current cache run).
3.  **Update Model**:
    -   Change `DrumClassifierCNN` output size to 25.
4.  **Update Beatmap Generator**:
    -   Map `cowbell` -> Special Lane (or dynamic).
    -   Map `snare_rimshot` -> Snare Lane (maybe with different color/accent).
    -   Map `snare_cross_stick` -> Snare Lane (different shape).

## 4. Dynamic Lane Mapping (Preview)
Instead of hardcoded `kick -> lane 0`, we will implement a **Priority-Based Allocator**:
-   **Core Lanes (Fixed)**: Kick (Center), Snare (Left/Right Center).
-   **Dynamic Lanes (Outer)**:
    -   If `cowbell` is present in section -> Allocate Lane 4.
    -   If `tom_high` is present -> Allocate Lane 3.
    -   This allows the map to adapt to the song's instrumentation.
