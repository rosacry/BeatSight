# Multi-Label Drum Classifier: F1 Plateau Analysis & Proposed Solution

## Executive Summary

We are training a multi-label drum classifier to detect 12 simultaneous drum hit classes from audio spectrograms. **Current best F1: 0.7794. Target: 0.90.**

The model has plateaued despite extensive hyperparameter tuning and 6+ epochs of training. A recent analysis revealed a potential **critical dataset design flaw**: the synthetic multi-label training dataset contains **zero solo (single-label) samples**—every sample has 2-3 classes blended together. This may prevent the model from learning each class's unique acoustic signature.

**We need expert validation:** Is adding solo samples the right approach, or is there a deeper issue we're missing?

---

## 1. Current Situation

### 1.1 Model Architecture
- **Model**: DrumClassifierCNNv5 (v5-large), 7.1M parameters
- **Task**: Multi-label classification (12 classes, simultaneous detection)
- **Input**: Mel spectrograms from isolated drum hit audio
- **Output**: Independent sigmoid per class (BCEWithLogitsLoss)

### 1.2 Current Performance (with optimized thresholds)

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| **Micro F1** | 0.7794 | 0.90 | -0.12 |
| **Macro F1** | 0.7683 | 0.85+ | -0.08 |

### 1.3 Per-Class Breakdown (sorted by F1)

| Class | F1 | Precision | Recall | Gap to 0.90 |
|-------|-----|-----------|--------|-------------|
| **hihat_pedal** | **0.495** | 0.519 | 0.473 | **+0.405** |
| **cross_stick** | **0.671** | 0.757 | 0.602 | **+0.229** |
| **ride_bow** | **0.684** | 0.661 | 0.708 | **+0.216** |
| hihat_closed | 0.725 | 0.704 | 0.747 | +0.175 |
| hihat_open | 0.735 | 0.825 | 0.663 | +0.165 |
| ride_bell | 0.747 | 0.840 | 0.672 | +0.153 |
| tom | 0.767 | 0.762 | 0.771 | +0.133 |
| snare | 0.767 | 0.725 | 0.815 | +0.133 |
| kick | 0.801 | 0.769 | 0.836 | +0.099 |
| crash | 0.868 | 0.917 | 0.825 | +0.032 |
| splash | 0.975 | 0.998 | 0.953 | -0.075 |
| china | 0.985 | 0.998 | 0.973 | -0.085 |

**Key observation**: 3 classes (hihat_pedal, cross_stick, ride_bow) have F1 < 0.70 and are dragging down the overall score.

---

## 2. Training History & Plateau Evidence

### 2.1 Training Progression

| Epoch | Val F1 | Δ from Previous |
|-------|--------|-----------------|
| 1 | 0.7723 | - |
| 2 | 0.7735 | +0.0012 |
| 4 | 0.7747 | +0.0012 |
| 5 | 0.7751 | +0.0004 |
| 6+ | ~0.7751 | ~0 (plateau) |

**Total improvement after 6 epochs: +0.0028** (essentially flat after epoch 2)

### 2.2 What We've Tried

| Approach | Result |
|----------|--------|
| OHEM loss (hard example mining) | Helped initially, then plateaued |
| Balanced sampling (oversample rare classes) | No significant improvement |
| Focal loss with gamma=2.0 | Marginal improvement |
| Per-class threshold tuning | +0.007 Micro F1 (0.7727→0.7794) |
| EMA (exponential moving average) | Slight stability, no F1 gain |
| SpecAugment (drum preset) | No measurable impact |
| Label smoothing (0.02) | No measurable impact |
| Extended training (6+ epochs) | Plateau confirmed |

---

## 3. The Dataset Design Issue (Proposed Root Cause)

### 3.1 Current Multi-Label Dataset Structure

The training dataset was **synthetically generated** by:
1. Taking single-label drum samples from a source dataset
2. Randomly combining 2-3 samples from different classes
3. Blending their spectrograms to simulate simultaneous hits

**Critical finding:**

```
Current Multi-Label Dataset (9M samples):
  1-label (solo): 0 (0.0%)     ← ZERO SOLO SAMPLES
  2-label: 6,006,310 (66.7%)
  3-label: 2,993,690 (33.3%)
```

### 3.2 Co-occurrence Analysis (Weak Classes)

The 3 worst-performing classes always appear blended with other sounds:

**hihat_pedal** (F1=0.495, 837,520 samples):
- Co-occurs with kick: 42.7%
- Co-occurs with tom: 9.8%
- **Never seen in isolation**

**cross_stick** (F1=0.671, 561,572 samples):
- Co-occurs with tom: 14.6%
- Co-occurs with hihat_closed: 14.6%
- **Never seen in isolation**

**ride_bow** (F1=0.684, 1,929,986 samples):
- Co-occurs with hihat_closed: 32.6%
- Co-occurs with kick: 32.6%
- **Never seen in isolation**

### 3.3 Source Single-Label Dataset (for reference)

The original isolated drum hits dataset:

```
Source Dataset: 15,217,976 single-label samples
  snare            3,726,478 (24.5%)
  hihat_closed     3,079,108 (20.2%)
  kick             2,678,100 (17.6%)
  hihat_pedal      1,478,672 ( 9.7%)  ← Has plenty of solo samples
  ride_bow         1,454,987 ( 9.6%)  ← Has plenty of solo samples
  tom              1,102,747 ( 7.2%)
  hihat_open         536,111 ( 3.5%)
  cross_stick        414,750 ( 2.7%)  ← Lower count but exists
  crash              298,375 ( 2.0%)
  ride_bell          280,160 ( 1.8%)
  china               90,141 ( 0.6%)
  splash              78,347 ( 0.5%)
```

---

## 4. Proposed Solution

### 4.1 Hypothesis

The model cannot distinguish `hihat_pedal` from `kick` because:
1. `hihat_pedal` always appears blended with other sounds (43% with kick)
2. The model never learned what `hihat_pedal` sounds like **in isolation**
3. When it sees `hihat_pedal` mixed with `kick`, it only recognizes `kick`

### 4.2 Proposed Fix

Regenerate the multi-label dataset with **30% solo samples**:

```
Proposed Dataset Distribution:
  1-label (solo): ~2,700,000 (30%)  ← NEW: Teaches pure class signatures
  2-label: ~4,200,000 (47%)
  3-label: ~2,100,000 (23%)
```

**Rationale**: 
- Solo samples teach the model each class's unique acoustic fingerprint
- Multi-label samples teach the model to detect classes when mixed
- 30% is enough to establish signatures without dominating training

### 4.3 Implementation

The generator script has been updated with a `--solo-ratio` parameter:

```bash
python generate_multilabel_dataset.py \
  --input "F:/datasets/prod_v5_final" \
  --output "F:/datasets/prod_v5_multilabel_v4" \
  --mode synthetic \
  --num-samples 9000000 \
  --max-labels 3 \
  --solo-ratio 0.30
```

---

## 5. Questions for Expert Review

### Primary Question
**Is adding solo samples the correct approach to break this plateau, or are we missing something fundamental?**

### Specific Questions

1. **Dataset Design**: Is 30% solo ratio appropriate, or should it be higher/lower?

2. **Loss Function**: We're using OHEM (Online Hard Example Mining) with focal loss. Should we consider:
   - Asymmetric loss for precision/recall tradeoff?
   - Class-specific loss weighting beyond what we have?
   - A completely different approach?

3. **Architecture**: Is 7.1M parameters sufficient for 12-class multi-label? Should we consider:
   - Larger model?
   - Attention mechanisms specifically for multi-label?
   - Multi-head output structure?

4. **Confusion Patterns**: The weak classes share acoustic similarities:
   - `hihat_pedal` vs `kick` (both low-frequency, percussive)
   - `ride_bow` vs `hihat_closed` (both metallic, sustained)
   - `cross_stick` vs `snare` (same drum, different technique)
   
   Should we add **contrastive loss** or **hard negative mining** specifically for these pairs?

5. **Fundamental Limit**: Is 0.90 F1 achievable with synthetic spectrogram blending, or do we need:
   - Real multi-label recordings?
   - More sophisticated audio mixing (phase alignment, etc.)?
   - Different input representation?

---

## 6. Files to Review

### Core Files (attach these)
1. `training/multilabel/loss.py` - Loss functions including OHEM, focal, asymmetric
2. `training/multilabel/train_multilabel.py` - Training script (lines 1-200, 800-900 for loss setup)
3. `training/multilabel/generate_multilabel_dataset.py` - Dataset generation with new solo-ratio
4. `training/multilabel/dataset.py` - Dataset class with spectrogram blending logic

### Model Architecture
5. `models/cnn_v5.py` - The v5 model architecture (7.1M params)

### Threshold Tuning Results
6. `runs/v5_multilabel_ohem/optimal_thresholds.json` - Per-class thresholds and metrics

---

## 7. Constraints

- **No manual data collection**: User has already invested significant effort in data collection
- **Time budget**: Prefer solutions that can show improvement within 24-48 hours of training
- **Hardware**: Single GPU (RTX-class), can run overnight training sessions
- **Goal**: Reach 0.90 Micro F1 score

---

## 8. What Success Looks Like

| Metric | Current | Minimum Target | Stretch Target |
|--------|---------|----------------|----------------|
| Micro F1 | 0.7794 | 0.85 | 0.90 |
| hihat_pedal F1 | 0.495 | 0.75 | 0.85 |
| cross_stick F1 | 0.671 | 0.80 | 0.85 |
| ride_bow F1 | 0.684 | 0.80 | 0.85 |

If the weakest 3 classes can reach F1 > 0.80, the overall Micro F1 should exceed 0.87.
