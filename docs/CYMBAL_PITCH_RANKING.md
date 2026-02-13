# Cymbal Pitch Ranking System

## Overview

BeatSight's drum classifier detects **generic cymbal types** (crash, china, splash, ride) without distinguishing between multiple cymbals of the same type within a kit. This document describes how the **pitch ranking system** automatically distinguishes multiple cymbals.

**Implementation:** `ai-pipeline/transcription/instrument_pitch_ranker.py`

## The Problem

Training data labels like `crash_1` and `crash_2` are **kit-relative**, not **acoustically consistent**:

```
Song A (recorded on Kit 1):
  crash_1 = 16" A Custom (bright, ~800Hz centroid)
  crash_2 = 18" K Dark (dark, ~600Hz centroid)

Song B (recorded on Kit 2):  
  crash_1 = 20" China Boy (trashy, ~1200Hz centroid)
  crash_2 = 14" Splash (bright, ~900Hz centroid)
```

A model trained on these labels learns **nothing consistent** because the same label refers to completely different acoustic properties.

## The Solution

1. **Train a robust generic detector** - "crash", "china", "splash" with 60K+ samples each
2. **Post-process with pitch analysis** - Cluster hits by timbre, rank by pitch
3. **Consistent labeling** - `crash_1` always = highest pitch crash in that song

## Supported Cymbal Types

| Base Class | Output Labels | Typical Count | Ranking |
|------------|---------------|---------------|---------||
| `crash` | crash_1, crash_2, ... crash_N | 1-10+ | High->Low pitch |
| `china` | china_1, china_2, ... china_N | 1-10+ | High->Low pitch |
| `splash` | splash_1, splash_2, ... splash_N | 1-10+ | High->Low pitch |
| `ride_bow` | ride_bow_1, ride_bow_2, ... | 1-10+ | High->Low pitch |
| `ride_bell` | ride_bell_1, ride_bell_2, ... | 1-10+ | High->Low pitch |

### Hi-Hats (Not Ranked)

Hi-hat variants (`hihat_closed`, `hihat_open`, `hihat_pedal`, `hihat_splash`, `hihat_foot_splash`) are **not ranked** because:
- Drummers typically have only one hi-hat per kit
- The variants represent playing technique, not different instruments

## How It Works

### Step 1: Feature Extraction

For each detected cymbal hit, extract:

```python
features = {
    'spectral_centroid': 2500.0,  # Hz - primary pitch indicator
    'mfcc': [...],                 # 13 coefficients - timbre fingerprint
    'attack_time': 5.2,           # ms - how quickly it reaches peak
    'decay_time': 450.0,          # ms - how long it rings
    'rms_energy': 0.15,           # Overall loudness
}
```

### Step 2: Clustering

Group hits by acoustic similarity using k-means:

```
Song with 15 crash hits:
  Cluster A (8 hits): spectral_centroid avg = 2800 Hz (bright crash)
  Cluster B (7 hits): spectral_centroid avg = 1900 Hz (dark crash)
```

### Step 3: Pitch Ranking

Assign labels based on spectral centroid (pitch):

```
Cluster A (2800 Hz) → crash_1  (higher pitch = smaller/brighter)
Cluster B (1900 Hz) → crash_2  (lower pitch = larger/darker)
```

## Usage

### Basic Usage

```python
from instrument_pitch_ranker import InstrumentPitchRanker

# Initialize ranker
ranker = InstrumentPitchRanker()

# Process events from classifier
events = [
    {"timestamp": 0.5, "label": "crash", "confidence": 0.95},
    {"timestamp": 2.1, "label": "crash", "confidence": 0.88},
    {"timestamp": 4.0, "label": "crash", "confidence": 0.92},
    {"timestamp": 5.5, "label": "china", "confidence": 0.90},
]

# Load audio
audio, sr = librosa.load("song.wav", sr=22050, mono=True)

# Get ranked labels
ranked = ranker.process_song(events, audio, sr)

# Results:
# [
#   {"timestamp": 0.5, "label": "crash", "ranked_label": "crash_1", ...},
#   {"timestamp": 2.1, "label": "crash", "ranked_label": "crash_2", ...},
#   {"timestamp": 4.0, "label": "crash", "ranked_label": "crash_1", ...},
#   {"timestamp": 5.5, "label": "china", "ranked_label": "china_1", ...},
# ]
```

### Convenience Function

```python
from instrument_pitch_ranker import rank_instruments_in_beatmap

ranked_events = rank_instruments_in_beatmap(events, "song.wav")
```

### With Feature Output (for debugging)

```python
ranked = ranker.process_song(events, audio, sr, return_features=True)

for event in ranked:
    print(f"{event['ranked_label']}: centroid={event['features']['spectral_centroid']:.0f} Hz")
```

## Configuration

Each cymbal type has configurable parameters:

```python
from instrument_pitch_ranker import InstrumentConfig, RankingStrategy

custom_config = {
    "crash": InstrumentConfig(
        base_label="crash",
        supports_multiples=True,
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 4),        # Expect 1-4 crashes per kit
        min_samples_for_clustering=3, # Need 3+ hits to cluster
        centroid_weight=0.7,         # 70% weight on pitch
        mfcc_weight=0.2,             # 20% weight on timbre
        decay_weight=0.1,            # 10% weight on decay time
    ),
}

ranker = InstrumentPitchRanker(configs=custom_config)
```

## Real-World Examples

### Example 1: Standard Rock Kit (2 crashes)

```
Detected: 45 crash hits
Clustering result: 2 clusters
  Cluster A: 22 hits, avg centroid = 3200 Hz (16" A Custom)
  Cluster B: 23 hits, avg centroid = 2100 Hz (18" K Dark)

Output:
  crash_1 → 16" A Custom (22 hits)
  crash_2 → 18" K Dark (23 hits)
```

### Example 2: Metal Kit (4 crashes + 2 chinas)

```
Detected: 80 crash hits, 25 china hits
Clustering result: 4 crash clusters, 2 china clusters

Crashes:
  crash_1 → 14" Fast Crash (10 hits, 3800 Hz)
  crash_2 → 16" A Custom (25 hits, 3100 Hz)
  crash_3 → 18" K Dark (30 hits, 2400 Hz)
  crash_4 → 20" Power Ride (15 hits, 1800 Hz)

Chinas:
  china_1 → 16" Oriental China (12 hits, 2900 Hz)
  china_2 → 20" China Boy (13 hits, 2100 Hz)
```

### Example 3: Single Crash Song

```
Detected: 12 crash hits
Clustering result: 1 cluster (all similar)

Output:
  crash_1 → All 12 hits (single crash in kit)
```

## Advantages Over Training crash_1/crash_2

| Aspect | Training Approach | Pitch Ranking Approach |
|--------|-------------------|----------------------|
| Training data | ~300 crash_1 samples | 68,000+ crash samples |
| Consistency | Kit-relative labels | Song-relative pitch ordering |
| Flexibility | Limited to 2 crashes | Supports 1-4+ crashes |
| Accuracy | Confused between similar cymbals | Clear pitch-based distinction |
| Maintenance | Needs retraining for new cymbals | Just add to config |

## CLI Testing

```bash
python ai-pipeline/transcription/instrument_pitch_ranker.py \
    --audio path/to/song.wav \
    --events path/to/detected_events.json \
    --output ranked_events.json
```

## See Also

- [Tom Pitch Ranking](TOM_PITCH_RANKING.md) - Similar system for rack/floor toms
- [Instrument Pitch Ranker Source](../ai-pipeline/transcription/instrument_pitch_ranker.py)
