# Temporal Modeling: What It Is and Why It Matters

Understanding how BeatSight currently processes audio and what temporal modeling would add.

---

## What the Current Model DOES Do

```
Song: |----snare----kick----hihat-snare-kick-kick-hihat-snare----|
       ↓     ↓      ↓       ↓     ↓    ↓    ↓     ↓     ↓
Window: [1]  [2]   [3]     [4]   [5]  [6]  [7]   [8]   [9]
       ↓     ↓      ↓       ↓     ↓    ↓    ↓     ↓     ↓
Output: snare kick  hihat  snare kick kick hihat snare  ...
```

**Each 50ms window is classified independently.** Fast fills, blast beats, whatever—if there's a drum hit in that window, it gets detected.

| Scenario | Status | Notes |
|----------|--------|-------|
| ✅ Fast drumming | Works fine | Each hit is in a window |
| ✅ Complex fills | Works fine | Each hit classified |
| ✅ Overlapping hits | Works fine | Multi-label classification |

---

## What I Meant by "Patterns"

The model doesn't know that window [5] comes after window [4]. It treats each window as if it's the only one.

### Current Approach

```python
# For each window, independently:
P(snare | spectrogram_window_5) = 0.92  # Just looks at this window
```

### What Temporal Modeling Would Add

```python
# Knows what came before:
P(snare | spectrogram_window_5, "just played kick-kick") = 0.97
# Context: "drummers often do kick-kick-snare"
```

---

## Why This Matters (Edge Cases)

The current model can get confused in these situations:

### 1. Ambiguous Ghost Notes

**Problem:**
- Quiet snare hit at 0.3 confidence
- Is it a real hit or just noise?

**With Temporal Context:**
- If model knew "we're in the middle of a fill," it might boost confidence to 0.7
- Pattern recognition: "ghost notes are common in this groove"

### 2. Bleed/Crosstalk

**Problem:**
- Kick drum mic picks up some snare resonance
- Model sees weak snare signal, unsure if it's a new hit

**With Temporal Context:**
- If it knew "snare was just hit 50ms ago," it could say "probably bleed, not new hit"
- Reduces false positives from mic bleed

### 3. Swing/Groove Timing

**Problem:**
- Hi-hat slightly off-grid
- Is it a timing error or intentional swing?

**With Temporal Context:**
- Model with tempo awareness: "this is a swung 8th, not an error"
- Understands musical timing, not just raw milliseconds

---

## Performance Comparison

| Scenario | Current Model | With Temporal |
|----------|---------------|---------------|
| Fast 16th notes | ✅ Detects fine | ✅ Same |
| Blast beats | ✅ Detects fine | ✅ Same |
| Complex fills | ✅ Detects fine | ✅ Same |
| Quiet ghost notes | ⚠️ Might miss | ✅ Context helps |
| Audio bleed | ⚠️ False positives | ✅ Context helps |
| Weird timing | ⚠️ Timing jitter | ✅ Tempo-aware |

### Expected Accuracy

| Model Type | Accuracy Range |
|------------|----------------|
| **Current (independent windows)** | 85-92% |
| **With temporal modeling** | 88-95% |

The improvement comes from handling **edge cases**—the ambiguous situations where context would help.

---

## Key Insight

**It's not about detecting fast stuff—it's about handling ambiguous situations where context would help.**

For clean recordings with clear hits, the current model is already excellent. Temporal modeling helps with:
- Noisy recordings
- Live performances with bleed
- Complex grooves with ghost notes
- Non-standard timing (swing, rubato)

---

## How Temporal Modeling Would Work

### Architecture Change

```
Current:
[Window] → [CNN Encoder] → [Classifier] → [Predictions]

With Temporal:
[Window 1] → [CNN] ─┐
[Window 2] → [CNN] ─┼→ [Temporal Model (Mamba/Transformer)] → [Predictions]
[Window 3] → [CNN] ─┤
[Window 4] → [CNN] ─┘
```

### What the Temporal Model Learns

1. **Drum patterns:** kick-snare-kick-snare (basic rock beat)
2. **Fill structures:** build-ups, crashes on downbeat
3. **Groove timing:** where swing falls, ghost note placement
4. **Musical form:** verse patterns vs. chorus patterns

---

## Implementation Complexity

| Aspect | Difficulty |
|--------|------------|
| Adding Mamba/S4 layer | Medium (well-documented) |
| Training with sequences | Medium (need to batch sequences) |
| Getting tempo/beat info | Hard (requires beat tracking) |
| Proving improvement | Medium (need good test set) |

This is the **easiest path to novel research**—well-understood techniques applied to an under-explored domain.
