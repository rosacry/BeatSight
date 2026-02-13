# Drum Classifier Class Structure History

**Archive Document** - Historical reference for class structure evolution

---

## Timeline

| Date | Version | Classes | Key Changes |
|------|---------|---------|-------------|
| Pre-Dec 2025 | v1 (21-class) | 21 | Original granular structure |
| Dec 2025 | v2 (13-class) | 13 | Merged tom variants, consolidated cymbals |
| Jan 1, 2026 | v3 (12-class) | 12 | Merged rimshot → snare |

---

## V1: 21-Class Structure (Original)

```
china, crash, cross_stick, hihat_closed, hihat_open, hihat_pedal,
kick, ride_bell, ride_bow, rimshot, snare, splash, tom_high,
tom_mid, tom_low, snare_center, snare_cross_stick, snare_rimshot,
hihat_foot_splash, hihat_splash, ...
```

**Issues:**
- Too many rare classes with insufficient data
- Tom variants (high/mid/low) better handled by pitch analysis
- Snare variants caused confusion

---

## V2: 13-Class Structure (Dec 2025)

| Index | Class |
|-------|-------|
| 0 | china |
| 1 | crash |
| 2 | cross_stick |
| 3 | hihat_closed |
| 4 | hihat_open |
| 5 | hihat_pedal |
| 6 | kick |
| 7 | ride_bell |
| 8 | ride_bow |
| 9 | rimshot |
| 10 | snare |
| 11 | splash |
| 12 | tom |

**Best Result:** 85.00% Balanced Accuracy (Epoch 32)

**Training Run:** `v5_specaug_focal_phase1`

**Issues:**
- Rimshot (269:1 imbalance) was still problematic
- Rimshot and snare acoustically very similar
- Better to detect rimshot via acoustic analysis post-classification

---

## V3: 12-Class Structure (Current - Jan 2026)

| Index | Class | Samples |
|-------|-------|---------|
| 0 | china | 2,081 |
| 1 | crash | 580,178 |
| 2 | cross_stick | 90,195 |
| 3 | hihat_closed | 2,815,697 |
| 4 | hihat_open | 490,698 |
| 5 | hihat_pedal | 238,339 |
| 6 | kick | 4,270,679 |
| 7 | ride_bell | 109,555 |
| 8 | ride_bow | 648,671 |
| 9 | snare | 4,555,883 |
| 10 | splash | 6,550 |
| 11 | tom | 2,922,867 |

**Total Samples:** 16,731,393

**Current Best:** 83.37% Balanced Accuracy (Epoch 16)

**Training Run:** `12class_phase2_specaug_focal`

**Rationale for rimshot merge:**
- Rimshot = stick hitting head + rim simultaneously
- Acoustically ~95% similar to snare hits
- Post-processing can detect the difference via:
  - Higher frequency content at ~2-4kHz (rim click)
  - Characteristic attack transient
- Removing 269:1 class imbalance improves overall model performance

---

## Label Remapping Rules

From `training/excluded_classes.py`:

```python
LABEL_REMAPPING = {
    # Rimshot variants → snare
    "rimshot": "snare",
    "snare_rimshot": "snare",
    
    # Tom variants → unified tom
    "tom_high": "tom",
    "tom_mid": "tom",
    "tom_low": "tom",
    
    # Snare variants → snare
    "snare_center": "snare",
    
    # Cross-stick → cross_stick
    "snare_cross_stick": "cross_stick",
    
    # Hi-hat variants
    "hihat_foot_splash": "hihat_pedal",
    "hihat_splash": "hihat_open",
}
```

---

## Key Insights

1. **Fewer classes = better per-class accuracy** when classes are acoustically similar
2. **Post-processing** is more effective than classification for subtle distinctions
3. **Tom pitch differentiation** handled by spectral analysis, not classification
4. **Rimshot detection** can be done via attack transient analysis

---

*Archived: January 6, 2026*
