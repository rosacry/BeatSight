# Drum Technique Labels - Current Implementation

> **Created:** December 5, 2025  
> **Updated:** December 5, 2025 (corrected after reviewing technique_heads.py)
> **Status:** ✅ V5 ALREADY IMPLEMENTS TECHNIQUE DETECTION

## ✅ V5 Multi-Task Architecture

The V5 model uses a **multi-task architecture** with separate heads:

```
Main CNN/Transformer → Feature Vector (512-d) 
                      ↓
                ┌─────┼─────┐
                ↓     ↓     ↓
          [Instrument] [Velocity] [Technique]
             Head        Head       Heads
              ↓           ↓          ↓
           21 classes   scalar   multi-label
```

## Instrument Classes (21) - DRUM_COMPONENTS

```
aux_percussion, china, crash, cross_stick, cymbal_choke,
hihat_closed, hihat_foot_splash, hihat_open, hihat_pedal, hihat_splash,
kick, ride_bell, ride_bow, rimshot, snare, snare_center, snare_cross_stick, 
snare_rimshot, splash, tom_high, tom_low, tom_mid
```

## ✅ Technique Detection (Already Implemented)

**Source:** `ai-pipeline/training/models/technique_heads.py`

### Core Techniques (CORE_TECHNIQUES)
| Technique | Detection Method | Status |
|-----------|-----------------|--------|
| `flam` | Double transient (grace note + main) | ✅ Implemented |
| `roll` | Tremolo envelope pattern | ✅ Implemented |
| `buzz_roll` | Press roll with bounces | ✅ Implemented |
| `cymbal_choke` | Sudden amplitude drop | ✅ Implemented |
| `ghost_note` | Low amplitude (velocity < 0.2) | ✅ Implemented |
| `accent` | High amplitude (velocity > 0.8) | ✅ Implemented |
| `double_stroke` | Paired transients (RR/LL) | ✅ Implemented |
| `drag` | Multiple grace notes | ✅ Implemented |

### Supporting Techniques (SUPPORTING_TECHNIQUES)
| Technique | Detection Method | Status |
|-----------|-----------------|--------|
| `rimshot` | Distinct harmonic content | ✅ Implemented |
| `cross_stick` | Woody timbre signature | ✅ Implemented |
| `dead_stroke` | Short decay envelope | ✅ Implemented |
| `mallet_hit` | Rounded transient | ✅ Implemented |
| `brush_sweep` | Noise-like sustained sound | ✅ Implemented |
| `crash_ride` | Specific decay pattern | ✅ Implemented |

## Architecture Details

The technique heads use attention-based detection:

```python
class TechniqueAttention(nn.Module):
    """Each technique has a learnable query vector that attends to the
    input features, allowing the model to focus on technique-specific
    patterns in the spectrogram encoding."""
```

**Configuration:** `TechniqueConfig`
- `input_dim`: 512 (from backbone)
- `hidden_dim`: 256
- `use_attention`: True (attention-based, not simple MLP)
- `num_attention_heads`: 4
- `detection_threshold`: 0.5
- `loss_type`: "focal" (handles class imbalance)

## What's NOT Implemented (Future Considerations)

From `personal_notes/additionaldrummertech.txt`, techniques that are **not** currently detected:

| Category | Techniques | Reason Not Implemented |
|----------|-----------|----------------------|
| Sticking | R/L hand detection | Audio doesn't reveal hand choice |
| Foot technique | Heel-up vs heel-down | Subtle differences, hard to detect |
| Motion-based | Moeller, whip stroke | Movement technique, not audio |
| Half-open degrees | 25%/50%/75% open | Continuous spectrum, hard to discretize |

## Conclusion

**No additional work needed.** The V5 model already has comprehensive technique detection with 14 technique classes via the multi-task technique heads. The original analysis was incorrect - I only looked at `DRUM_COMPONENTS` and missed the `technique_heads.py` module.

---

*Corrected analysis - V5 already supports technique detection*
