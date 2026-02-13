# Pattern Detection for Drum Transcription

This document describes BeatSight's pattern detection system, which analyzes sequences of detected drum hits to identify higher-level musical patterns that cannot be detected from single-hit analysis alone.

## Overview

The Pattern Detector is a **post-processing module** that runs after the AI classifier has detected individual drum hits. While the AI model classifies single audio windows (e.g., "this is a crash cymbal at velocity 0.7"), the Pattern Detector analyzes sequences to identify:

- **Crash Builds** - Crescendo cymbal patterns leading to climactic hits
- **Accent-Tap Patterns** - Alternating loud/soft strokes (Moeller technique)
- **Hi-Hat Barking** - Quick open-close articulations
- **Continuous Barking** - Repeated bark patterns
- **Hi-Hat Splashes** - Foot-operated sustain effects
- **Crescendos/Decrescendos** - General dynamic changes

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Audio Input                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Onset Detection + AI Classification                 │
│         (single-hit: instrument, velocity, techniques)           │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Pattern Detector                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ CrashBuild      │  │ AccentTap       │  │ HiHatBark       │  │
│  │ Detector        │  │ Detector        │  │ Detector        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │ HiHatSplash     │  │ Crescendo       │                       │
│  │ Detector        │  │ Detector        │                       │
│  └─────────────────┘  └─────────────────┘                       │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               Annotated Events + Pattern List                    │
└─────────────────────────────────────────────────────────────────┘
```

## Detected Patterns

### 1. Crash Builds (Cymbal Crescendos)

**What it detects:** Repeated cymbal hits that crescendo in velocity/intensity leading to a climactic hit.

**Common in:**
- Song transitions
- Pre-chorus builds
- Drop buildups
- Breakdown endings

**Detection criteria:**
- 3+ consecutive cymbal hits (crash, china, splash, ride)
- Increasing velocity trend (≥0.15 increase overall)
- Maximum gap of 0.5 seconds between hits
- Maximum duration of 4 seconds

**Example:**
```
Time:     0.0s    0.25s    0.5s    0.75s    1.0s
Velocity: 0.3  →  0.45  →  0.6  →  0.75  →  0.95  (CLIMAX!)
          ↑        ↑        ↑        ↑        ↑
        crash    crash   crash    crash    CRASH
```

**Output properties:**
```python
{
    "velocity_start": 0.3,
    "velocity_end": 0.95,
    "velocity_peak": 0.95,
    "velocity_trend": 0.65,
    "hit_count": 5,
    "hits_per_second": 5.0,
    "climax_at_end": True,
    "peak_position": 4
}
```

---

### 2. Accent-Tap Patterns (Moeller Technique)

**What it detects:** Alternating high (accent) and low (tap/ghost) velocities, typically using the Moeller whip technique.

**Common in:**
- Funk and R&B grooves
- Gospel drumming
- Linear drumming patterns
- Hi-hat and ride patterns

**Detection criteria:**
- 4+ hits minimum (2 accent-tap pairs)
- Clear velocity contrast (≥0.5 threshold)
- Consistent timing grid
- Same instrument throughout

**Example:**
```
Time:     0.0s    0.125s   0.25s   0.375s   0.5s    0.625s
Velocity: 0.9  →  0.25  →  0.88  →  0.22  →  0.9  →  0.28
          ↑        ↑        ↑        ↑        ↑        ↑
        ACCENT   tap     ACCENT   tap     ACCENT   tap
```

**Output properties:**
```python
{
    "accent_count": 3,
    "tap_count": 3,
    "accent_mean_velocity": 0.89,
    "tap_mean_velocity": 0.25,
    "dynamic_range": 0.64,
    "alternation_score": 1.0,  # Perfect alternation
    "timing_consistency": 0.95,
    "subdivision": "16th_notes",
    "avg_interval": 0.125
}
```

**Visual representation (in beatmap):**
- Accents: 100% opacity, normal size
- Taps: 45% opacity, 0.85x size (already implemented in `DesignSystem.cs`)

---

### 3. Hi-Hat Barking

**What it detects:** Quick open-close hi-hat articulation creating a distinctive "bark" or "chick" sound.

**How it works:**
The drummer opens the hi-hat slightly, strikes it, then quickly closes it with the foot. This creates a short, punchy "bark" sound distinct from:
- Fully open hi-hat (longer sustain)
- Closed hi-hat (no sustain)
- Foot chick (no stick attack)

**Detection criteria:**
- Open hi-hat hit followed by closed hi-hat
- Gap between 15-80ms (typical bark timing)
- Open hit velocity ≥ 0.3 (audible)

**Example:**
```
Time:     0.0s              0.04s
Event:    hihat_open  →  hihat_closed
          ↑ Strike         ↑ Foot close
          
Gap: 40ms = BARK detected!
```

**Output properties:**
```python
{
    "open_velocity": 0.6,
    "close_velocity": 0.5,
    "gap_ms": 40.0,
    "open_index": 0,
    "close_index": 1
}
```

---

### 4. Continuous Hi-Hat Barking

**What it detects:** Repeated barking patterns in a rhythmic pattern (on beats or specific subdivisions).

**Detection criteria:**
- 3+ consecutive barks
- Maximum gap of 0.5 seconds between barks
- Timing regularity ≥ 0.7

**Example:**
```
Time:     0.0s    0.5s    1.0s    1.5s
Pattern:  BARK    BARK    BARK    BARK
          ↑       ↑       ↑       ↑
        regular 0.5s intervals = continuous barking
```

**Output properties:**
```python
{
    "bark_count": 4,
    "regularity": 0.95,
    "avg_gap_ms": 500.0,
    "barks_per_second": 2.0,
    "child_bark_ids": ["hihat_bark_0.000", "hihat_bark_0.500", ...]
}
```

---

### 5. Hi-Hat Splashes

**What it detects:** Foot-operated open hi-hat with longer sustain, creating an airy "shhh" sound.

**Types:**
- **Foot splash**: Pedal opens then closes (no stick attack)
- **Open splash**: Stick hit with sustained open

**Detection criteria:**
- Hi-hat pedal/foot event or open hi-hat
- Velocity in splash range (0.2-0.7)
- Minimum sustain duration (100ms)

**Output properties:**
```python
{
    "velocity": 0.5,
    "estimated_sustain": 0.2,
    "splash_type": "foot_splash"  # or "open_splash"
}
```

---

## Usage

### Basic Usage

```python
from transcription.pattern_detector import (
    PatternDetector,
    DrumEvent,
    detect_all_patterns,
)

# Create events from your transcription output
events = [
    DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
    DrumEvent(timestamp=0.25, label="crash", velocity=0.5),
    DrumEvent(timestamp=0.5, label="crash", velocity=0.7),
    DrumEvent(timestamp=0.75, label="crash", velocity=0.9),
]

# Detect patterns
detector = PatternDetector()
patterns = detector.detect(events)

for pattern in patterns:
    print(f"{pattern.pattern_type.value}: {pattern.start_time:.2f}s - {pattern.end_time:.2f}s")
    print(f"  Confidence: {pattern.confidence:.2f}")
    print(f"  Properties: {pattern.properties}")
```

### With Transcription Pipeline

```python
from transcription.pattern_detector import annotate_transcription_result

# Your transcription output (list of dicts)
raw_events = [
    {"timestamp": 0.0, "label": "crash", "velocity": 0.3},
    {"timestamp": 0.25, "label": "crash", "velocity": 0.5},
    # ... more events
]

# Annotate with patterns
annotated_events, detected_patterns = annotate_transcription_result(raw_events)

# annotated_events now includes pattern_ids, articulation, dynamic_change
for event in annotated_events:
    if event.get("pattern_ids"):
        print(f"{event['timestamp']:.2f}s: {event['label']}")
        print(f"  Patterns: {event['pattern_ids']}")
        print(f"  Articulation: {event.get('articulation')}")
        print(f"  Dynamic: {event.get('dynamic_change')}")
```

### Custom Configuration

```python
from transcription.pattern_detector import PatternDetector, PatternDetectorConfig

config = PatternDetectorConfig(
    # Crash build settings
    crash_build_min_hits=4,              # Require 4+ hits
    crash_build_max_duration=3.0,        # Max 3 seconds
    crash_build_min_velocity_increase=0.2,  # Need 0.2 velocity increase
    
    # Accent-tap settings
    accent_tap_min_hits=6,               # Require 6+ hits
    accent_tap_velocity_threshold=0.55,  # Higher threshold for accent
    
    # Bark settings
    bark_max_gap=0.06,                   # Max 60ms gap
    bark_min_open_velocity=0.4,          # Louder open hit required
    
    # General
    min_confidence=0.6,                  # Higher confidence threshold
)

detector = PatternDetector(config)
```

---

## Integration with Desktop App

The pattern detector output maps directly to `HitObjectExtended` properties in the C# desktop app:

| Pattern Property | HitObjectExtended Property |
|------------------|---------------------------|
| `articulation="bark"` | `Articulation = DrumArticulation.Open` + `ArticulationFlags \|= Choked` |
| `articulation="accent"` | `Articulation = DrumArticulation.Accent` |
| `articulation="tap"` | `Articulation = DrumArticulation.Ghost` |
| `articulation="splash"` | `Articulation = DrumArticulation.FootSplash` |
| `dynamic_change="crescendo"` | `DynamicChange = DynamicChange.Crescendo` |
| `pattern_ids` | `PatternId` (first ID) |

### Velocity-Based Opacity

The desktop app already implements velocity-based opacity (from `DesignSystem.cs`):

```csharp
// Ghost notes (low velocity): 45% opacity
// Normal notes: ~72% opacity  
// Accent notes (high velocity): 100% opacity
public static float GetVelocityAlpha(double velocity)
{
    float v = (float)Math.Clamp(velocity, 0, 1);
    return GhostNoteMinAlpha + (1f - GhostNoteMinAlpha) * v;
}
```

This means accent-tap patterns will automatically display with:
- **Accents**: Full brightness (100% opacity)
- **Taps/Ghosts**: Translucent (45% opacity)

---

## Pattern Categories

Patterns are organized into categories for filtering and display:

| Category | Patterns |
|----------|----------|
| **DYNAMIC** | crash_build, accent_tap, crescendo, decrescendo, sforzando |
| **ARTICULATION** | hihat_bark, hihat_bark_continuous, hihat_splash, hihat_foot_chick |
| **RHYTHMIC** | (future: fills, polyrhythms) |
| **STRUCTURAL** | (future: transitions, breakdowns) |

---

## Future Enhancements

The pattern detector is designed to be extensible. Future patterns to implement:

### High Priority
- [ ] **Crash-Ride Detection**: Timekeeping on crash cymbal
- [ ] **Roll Detection**: Sustained rapid strokes
- [ ] **Fill Detection**: Transitional patterns between sections

### Medium Priority
- [ ] **Groove Detection**: Identify groove type (funk, rock, jazz)
- [ ] **Polyrhythm Detection**: Conflicting subdivisions
- [ ] **Linear Drumming**: No simultaneous limbs

### Research Required
- [ ] **Sticking Patterns**: Paradiddles, hertas (needs temporal modeling)
- [ ] **Style Classification**: Metal vs jazz vs funk
- [ ] **Metric Modulation**: Tempo reinterpretation

---

## Performance

The pattern detector is designed for real-time use:

- **1000 events**: ~10ms processing time
- **Memory**: O(n) where n = number of events
- **Complexity**: O(n²) worst case for overlapping patterns

For very long sequences (10,000+ events), consider processing in chunks by song section.

---

## Testing

Run the test suite:

```bash
cd BeatSight
source .venv/Scripts/activate  # or .venv/bin/activate on Linux
PYTHONPATH=ai-pipeline python -m pytest ai-pipeline/tests/test_pattern_detector.py -v
```

All 38 tests should pass, covering:
- Crash build detection
- Accent-tap detection
- Hi-hat bark detection
- Continuous barking detection
- Splash detection
- Edge cases and robustness

---

## References

- **Moeller Technique**: [Wikipedia](https://en.wikipedia.org/wiki/Moeller_method)
- **Hi-Hat Articulations**: Vic Firth Education - "Hi-Hat Techniques"
- **Crash Builds**: Common in EDM production, transitions
