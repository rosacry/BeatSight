# Path to 90%+ Validation Accuracy

## Current State Analysis

**Current accuracy: 41.05%**  
**Target: 90%+**

### The Root Problem: Extreme Class Imbalance

Your dataset has a **630x imbalance ratio**:

| Tier | Classes | Samples | % of Data |
|------|---------|---------|-----------|
| **RARE** (<100k) | 9 classes | 394,583 | 2.69% |
| **MEDIUM** (100k-500k) | 6 classes | 1,954,427 | 13.31% |
| **COMMON** (500k-2M) | 4 classes | 5,207,423 | 35.47% |
| **DOMINANT** (>2M) | 2 classes | 7,124,715 | 48.53% |

#### Rare Classes (< 100k samples):
```
hihat_closed        :     6,387 (0.04%)  ← CRITICALLY RARE
cymbal_choke        :     7,537 (0.05%)  ← CRITICALLY RARE
crash               :    15,236 (0.10%)
snare_center        :    45,272 (0.31%)
tom_high            :    45,747 (0.31%)
snare               :    53,403 (0.36%)
splash              :    61,715 (0.42%)
cross_stick         :    71,162 (0.48%)
hihat_splash        :    88,124 (0.60%)
```

#### Dominant Classes (> 2M samples):
```
aux_percussion      : 3,100,430 (21.12%)
snare_rimshot       : 4,024,285 (27.41%)
```

### Why 41% is Actually Expected

With 48.5% of your data being just 2 classes, and 2.69% being 9 classes:
- The model learns to be good at `snare_rimshot` and `aux_percussion`
- It essentially ignores `hihat_closed` (6,387 samples vs 4,024,285)
- **Your 41% is mostly from the dominant classes**

---

## The Path to 90%+

### Phase 1: Data Rebalancing (CRITICAL - Expected +20-30%)

#### Option A: Aggressive Oversampling
Oversample rare classes to bring them to at least 500k samples each.

```python
# Target distribution: min 500k per class
targets = {
    'hihat_closed': 500_000,      # 78x oversample
    'cymbal_choke': 500_000,      # 66x oversample
    'crash': 500_000,             # 33x oversample
    # ... etc
}
```

**Pros:** Simple, preserves all rare class data  
**Cons:** Risk of overfitting to rare classes

#### Option B: Balanced Sampling (Recommended)
Use a **class-balanced sampler** that samples each class equally per epoch.

```python
# Each epoch sees equal samples from each class
samples_per_class_per_epoch = 100_000
# 21 classes × 100k = 2.1M samples per epoch
# Rare classes get repeated, common classes get subsampled
```

**Pros:** Every class gets equal attention  
**Cons:** Underutilizes dominant class data

#### Option C: Square Root Sampling (Best Balance)
Sample proportional to sqrt(class_count).

```python
# sqrt(6387) = 80, sqrt(4024285) = 2006
# Ratio becomes 25x instead of 630x
```

**Pros:** Best balance between rare and common  
**Cons:** Still significant imbalance

### Phase 2: Loss Function Improvements (Expected +5-10%)

#### A. Class-Balanced Focal Loss
```python
# Current: effective weights with max 1.9x
# Problem: Not aggressive enough for 630x imbalance

# Solution: Class-balanced loss with beta=0.9999
# This gives ~100x weight to rare classes
CB_beta = 0.9999
effective_num = 1.0 - np.power(CB_beta, class_counts)
weights = (1.0 - CB_beta) / effective_num
weights = weights / weights.sum() * num_classes
```

#### B. LDAM Loss (Label-Distribution-Aware Margin)
Adds class-dependent margins to push rare class embeddings further apart.

#### C. Asymmetric Loss
Harder penalization for false negatives on rare classes.

### Phase 3: Architecture Improvements (Expected +5-10%)

#### A. Separate Heads for Rare vs Common
```
                    ┌─→ Common Class Head (12 classes)
Backbone ──→ Features ─┤
                    └─→ Rare Class Head (9 classes)
```

#### B. Hierarchical Classification
```
Level 1: Drum Family (Kick, Snare, HiHat, Cymbal, Tom, Aux)
Level 2: Specific Type (snare_rimshot, snare_center, etc.)
```

#### C. Prototype Networks / Metric Learning
Learn embeddings where distance = similarity. Works better for few-shot.

### Phase 4: Data Augmentation for Rare Classes (Expected +5-10%)

#### A. Mixup Between Same-Class Samples
For rare classes, mixup only within the same class to create variations.

#### B. Spectrogram Augmentation
- Time stretching (±10%)
- Pitch shifting (±2 semitones)
- Random EQ
- Room simulation

#### C. Synthetic Data Generation
Use audio synthesis to generate more rare class samples:
- Cymbal chokes: Take crash/china, apply decay envelope
- Ghost notes: Take snare, reduce velocity/volume

### Phase 5: Training Strategy (Expected +3-5%)

#### A. Two-Stage Training
1. **Stage 1:** Train on balanced subset until convergence
2. **Stage 2:** Fine-tune on full dataset with aggressive class weights

#### B. Progressive Class Balancing
- Epoch 1-20: Fully balanced sampling
- Epoch 21-50: Gradually shift toward natural distribution
- Epoch 51+: Class-balanced focal loss only

#### C. Self-Training / Pseudo-Labeling
Use confident predictions to augment rare class data.

---

## Implementation Priority

### Immediate Actions (Do These First)

1. **Implement Class-Balanced Sampler** - Biggest impact
2. **Increase Class Weights Aggressively** - For rare classes
3. **Analyze Per-Class Accuracy** - Know where you're failing

### Short-Term (This Week)

4. **Synthetic Data for Rare Classes** - Especially cymbal_choke, hihat_closed
5. **Hierarchical Classification** - Group similar classes
6. **Two-Stage Training** - Balanced → Fine-tune

### Medium-Term (This Month)

7. **Metric Learning / Prototypes** - For few-shot classes
8. **Label Audit** - Your rare classes may have label noise
9. **Architecture Modifications** - Separate heads

---

## Realistic Timeline to 90%

| Phase | Expected Accuracy | Time |
|-------|-------------------|------|
| Current | 41% | - |
| + Class-Balanced Sampler | 55-60% | 1-2 weeks |
| + Aggressive Weights | 60-65% | +1 week |
| + Two-Stage Training | 65-70% | +1-2 weeks |
| + Synthetic Rare Data | 70-75% | +2 weeks |
| + Hierarchical | 75-80% | +1-2 weeks |
| + Metric Learning | 80-85% | +2 weeks |
| + Ensemble + Tuning | 85-90%+ | +2-4 weeks |

**Total: 2-3 months of focused work**

---

## Next Immediate Step

Before any training, let's analyze per-class accuracy of your current 41% model to confirm where it's failing:

```bash
python ai-pipeline/training/tools/evaluate_per_class.py \
    --model ai-pipeline/training/runs/cutting_edge/v5/full-cached-simple/best_drum_classifier.pth \
    --dataset data/dataset_index
```

This will show you something like:
```
Class               Precision  Recall  F1     Support
aux_percussion      0.82       0.91    0.86   336,651
snare_rimshot       0.79       0.88    0.83   432,613
...
hihat_closed        0.12       0.03    0.05   1,169    ← FAILING
cymbal_choke        0.08       0.02    0.03   1,522    ← FAILING
```

This confirms the strategy and tells us exactly which classes need the most help.

---

## Your Competitive Advantage

If you solve the extreme imbalance problem and achieve 90%+ on 21 drum classes, you'll have:

1. **State-of-the-art drum transcription** - Most papers report on 3-5 classes
2. **Publishable research** - "Class-Imbalanced Learning for Fine-Grained Drum Transcription"
3. **Real product differentiation** - Competitors can't match granularity

**This IS achievable. It just requires systematic work on the imbalance problem, not more epochs of the same training.**
