# Tom Pitch Ranking System

## Overview

BeatSight's drum classifier detects **generic tom categories** (tom_high, tom_mid, tom_low) without distinguishing between multiple toms of the same category within a kit. This document describes how the **pitch ranking system** automatically distinguishes multiple toms.

**Implementation:** `ai-pipeline/transcription/instrument_pitch_ranker.py`

## Why Tom Ranking Matters

Many drum kits have multiple toms in the same category:

### Standard 5-Piece Kit (No ranking needed)
```
┌─────────────────────────────────────────┐
│  tom_high (12")  │  tom_mid (13")       │
│─────────────────────────────────────────│
│  tom_low (16" floor)                    │
└─────────────────────────────────────────┘
→ Model handles this fine (one of each)
```

### Extended Metal/Prog Kit (Ranking essential!)
```
┌─────────────────────────────────────────────────────┐
│  tom_high (10")  │  tom_high (12")  │  tom_mid (14")│
│─────────────────────────────────────────────────────│
│  tom_low (16" floor)  │  tom_low (18" floor)       │
└─────────────────────────────────────────────────────┘
→ Both 10" and 12" classified as "tom_high"!
→ Both floor toms classified as "tom_low"!
→ User can't tell which tom is which without ranking
```

### Neil Peart / Mike Portnoy Style (Definitely needs ranking)
```
┌───────────────────────────────────────────────────────────────┐
│  6"  │  8"  │  10" │  12" │  13" │  14" │  15" │  16" │  18" │
└───────────────────────────────────────────────────────────────┘
→ Multiple toms per category
→ Fills traverse specific toms in sequence
→ Visualization must show exact tom positions
```

## Supported Tom Types

| Base Class | Output Labels | Typical Count | Ranking |
|------------|---------------|---------------|---------||
| `tom_high` | tom_high_1, tom_high_2, ... tom_high_N | 1-10+ | High->Low pitch |
| `tom_mid` | tom_mid_1, tom_mid_2, ... tom_mid_N | 1-10+ | High->Low pitch |
| `tom_low` | tom_low_1, tom_low_2, ... tom_low_N | 1-10+ | High->Low pitch |

### Pitch Relationship

```
Tom sizes and typical frequencies:

tom_high_1 (10")  → ~200-250 Hz fundamental
tom_high_2 (12")  → ~170-200 Hz fundamental
tom_mid_1 (13")   → ~150-170 Hz fundamental  
tom_mid_2 (14")   → ~130-150 Hz fundamental
tom_low_1 (16")   → ~100-120 Hz fundamental
tom_low_2 (18")   → ~80-100 Hz fundamental
```

## How It Works

### Step 1: Feature Extraction

For each detected tom hit, extract:

```python
features = {
    'spectral_centroid': 450.0,   # Hz - pitch indicator (lower than cymbals)
    'mfcc': [...],                 # 13 coefficients - shell/head timbre
    'attack_time': 8.5,           # ms - stick attack
    'decay_time': 280.0,          # ms - resonance duration
    'rms_energy': 0.25,           # Loudness
}
```

### Step 2: Clustering

Group tom hits by acoustic similarity:

```
Song with 30 tom_high hits:
  Cluster A (18 hits): spectral_centroid avg = 520 Hz (10" rack tom)
  Cluster B (12 hits): spectral_centroid avg = 380 Hz (12" rack tom)
```

### Step 3: Pitch Ranking

Assign labels based on spectral centroid:

```
Cluster A (520 Hz) → tom_high_1  (higher pitch = smaller tom)
Cluster B (380 Hz) → tom_high_2  (lower pitch = larger tom)
```

## Usage

### Basic Usage

```python
from instrument_pitch_ranker import InstrumentPitchRanker

ranker = InstrumentPitchRanker()

events = [
    {"timestamp": 1.0, "label": "tom_high", "confidence": 0.92},
    {"timestamp": 1.2, "label": "tom_high", "confidence": 0.88},
    {"timestamp": 1.4, "label": "tom_mid", "confidence": 0.90},
    {"timestamp": 1.6, "label": "tom_low", "confidence": 0.95},
    {"timestamp": 1.8, "label": "tom_low", "confidence": 0.91},
]

audio, sr = librosa.load("song.wav", sr=22050, mono=True)
ranked = ranker.process_song(events, audio, sr)

# Results (example tom fill pattern):
# tom_high_1 (10") → tom_high_2 (12") → tom_mid_1 → tom_low_1 (16") → tom_low_2 (18")
```

### Analyzing Tom Fills

```python
from instrument_pitch_ranker import get_unique_instruments

ranked = ranker.process_song(events, audio, sr)
instruments = get_unique_instruments(ranked)

print("Toms detected in this song:")
for label, count in sorted(instruments.items()):
    if "tom" in label:
        print(f"  {label}: {count} hits")

# Output:
# Toms detected in this song:
#   tom_high_1: 45 hits
#   tom_high_2: 38 hits
#   tom_low_1: 22 hits
#   tom_low_2: 18 hits
#   tom_mid_1: 30 hits
```

## Configuration

Tom-specific configuration options:

```python
from instrument_pitch_ranker import InstrumentConfig, RankingStrategy

# Custom config for prog/metal with many toms
tom_config = {
    "tom_high": InstrumentConfig(
        base_label="tom_high",
        supports_multiples=True,
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 3),        # Some kits have 3 rack toms in "high" range
        min_samples_for_clustering=3,
        centroid_weight=0.5,         # Pitch matters but...
        mfcc_weight=0.3,             # ...shell timbre also important
        decay_weight=0.2,            # Resonance time varies by size
    ),
    "tom_low": InstrumentConfig(
        base_label="tom_low",
        supports_multiples=True,
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 2),        # 1-2 floor toms typical
        min_samples_for_clustering=3,
        centroid_weight=0.5,
        mfcc_weight=0.3,
        decay_weight=0.2,
    ),
}

ranker = InstrumentPitchRanker(configs=tom_config)
```

## Real-World Examples

### Example 1: Jazz Kit (single of each tom)

```
Detected: 15 tom_high, 12 tom_mid, 8 tom_low
Clustering result: 1 cluster per category

Output:
  tom_high_1 → 12" rack tom (15 hits)
  tom_mid_1 → 14" rack tom (12 hits)  
  tom_low_1 → 16" floor tom (8 hits)
```

### Example 2: Metal Kit (double rack, double floor)

```
Detected: 40 tom_high, 25 tom_mid, 35 tom_low
Clustering result: 2 tom_high, 1 tom_mid, 2 tom_low

Output:
  tom_high_1 → 10" rack tom (22 hits, 580 Hz centroid)
  tom_high_2 → 12" rack tom (18 hits, 420 Hz centroid)
  tom_mid_1 → 14" rack tom (25 hits)
  tom_low_1 → 16" floor tom (20 hits, 320 Hz centroid)
  tom_low_2 → 18" floor tom (15 hits, 240 Hz centroid)
```

### Example 3: Progressive Epic Fill

Input (detected events around a fill):
```
2:45.100 - tom_high (0.95 confidence)
2:45.200 - tom_high (0.92 confidence)
2:45.300 - tom_mid (0.88 confidence)
2:45.400 - tom_low (0.94 confidence)
2:45.500 - tom_low (0.91 confidence)
```

Output (after pitch ranking):
```
2:45.100 - tom_high_1 (10" - bright attack)
2:45.200 - tom_high_2 (12" - slightly darker)
2:45.300 - tom_mid_1 (14" - mid thud)
2:45.400 - tom_low_1 (16" - punchy floor tom)
2:45.500 - tom_low_2 (18" - deep floor tom)
```

This allows accurate visualization of the fill moving across the kit!

## Tom vs Cymbal Ranking Differences

| Aspect | Cymbals | Toms |
|--------|---------|------|
| Frequency range | 1000-4000 Hz centroid | 200-600 Hz centroid |
| Decay time | 500-2000 ms | 100-400 ms |
| Key differentiator | Brightness/shimmer | Shell depth/punch |
| Typical multiples | 2-4 crashes | 2 per category |
| Feature weights | 70% centroid | 50% centroid, 30% MFCC |

## Why Not Just Train tom_high_1, tom_high_2?

Same problem as cymbals - the labels are kit-relative:

```
Recording A: tom_high_1 = 10" Yamaha birch (bright)
Recording B: tom_high_1 = 13" Pearl maple (dark)
```

The model would learn conflicting patterns. Pitch ranking gives **consistent, acoustic-based** labeling.

## CLI Testing

```bash
python ai-pipeline/transcription/instrument_pitch_ranker.py \
    --audio path/to/song_with_tom_fills.wav \
    --events path/to/detected_events.json \
    --output ranked_events.json
```

## See Also

- [Cymbal Pitch Ranking](CYMBAL_PITCH_RANKING.md) - Similar system for crashes/chinas
- [Instrument Pitch Ranker Source](../ai-pipeline/transcription/instrument_pitch_ranker.py)
