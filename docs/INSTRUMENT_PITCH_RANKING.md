# Instrument Pitch Ranking System

## Overview

BeatSight uses a **pitch ranking post-processor** to automatically distinguish multiple instruments of the same type within a song. This allows the classifier to train on generic labels (crash, tom_high) while the post-processor provides specific labels (crash_1, crash_2, tom_high_1) based on acoustic analysis.

## Documentation

| Document | Description |
|----------|-------------|
| [CYMBAL_PITCH_RANKING.md](CYMBAL_PITCH_RANKING.md) | Ranking for crashes, chinas, splashes, rides |
| [TOM_PITCH_RANKING.md](TOM_PITCH_RANKING.md) | Ranking for high, mid, and low toms |

## Implementation

**Source:** `ai-pipeline/transcription/instrument_pitch_ranker.py`

## Quick Start

```python
from instrument_pitch_ranker import InstrumentPitchRanker, rank_instruments_in_beatmap

# Method 1: Full control
ranker = InstrumentPitchRanker()
audio, sr = librosa.load("song.wav", sr=22050)
ranked_events = ranker.process_song(events, audio, sr)

# Method 2: Convenience function
ranked_events = rank_instruments_in_beatmap(events, "song.wav")
```

## Supported Instruments

### Cymbals (see [CYMBAL_PITCH_RANKING.md](CYMBAL_PITCH_RANKING.md))
- `crash` → crash_1, crash_2, crash_3, crash_4
- `china` → china_1, china_2
- `splash` → splash_1, splash_2
- `ride_bow` → ride_bow_1, ride_bow_2
- `ride_bell` → ride_bell_1, ride_bell_2

### Toms (see [TOM_PITCH_RANKING.md](TOM_PITCH_RANKING.md))
- `tom_high` → tom_high_1, tom_high_2
- `tom_mid` → tom_mid_1, tom_mid_2
- `tom_low` → tom_low_1, tom_low_2

### Not Ranked
- `hihat_*` - Single hi-hat per kit (technique variants, not multiple instruments)
- `kick` - Single kick drum per kit
- `snare*` - Single snare per kit (rimshot/center/cross_stick are techniques)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLASSIFIER OUTPUT                            │
│  crash, crash, crash, china, tom_high, tom_high, tom_low, ...  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               INSTRUMENT PITCH RANKER                           │
│                                                                 │
│  1. Extract audio segment around each hit                      │
│  2. Compute features (spectral centroid, MFCCs, decay)         │
│  3. Cluster hits by timbre similarity                          │
│  4. Rank clusters by pitch (high→low)                          │
│  5. Assign _1, _2, _3 suffixes                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RANKED OUTPUT                                │
│  crash_1, crash_2, crash_1, china_1, tom_high_1, tom_high_2... │
└─────────────────────────────────────────────────────────────────┘
```

## Why This Approach?

| Problem | Solution |
|---------|----------|
| Training labels (crash_1, crash_2) are kit-relative | Train on generic "crash", rank by actual pitch |
| Only ~300 crash_1 samples vs 68K crash samples | More training data = better detection |
| Can't handle songs with 3+ crashes | Pitch ranking scales to any count |
| Model confused between similar cymbals | Clear acoustic-based distinction |

## CLI Testing

```bash
python ai-pipeline/transcription/instrument_pitch_ranker.py \
    --audio song.wav \
    --events detected_events.json \
    --output ranked_events.json
```
