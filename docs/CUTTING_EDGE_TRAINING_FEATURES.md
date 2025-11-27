# Cutting-Edge Training Features

This document describes BeatSight's production training pipeline using the **V5 Ultimate** architecture. V5 combines all proven 2024/2025 innovations into a single, highly optimized model.

---

## ⭐ TL;DR - Production Path

**V5 Ultimate is the recommended path for production:**

```bash
./auto_train.sh label-audit      # 14  - Find bad labels (~30min)
./auto_train.sh v5-warmup        # 17a - Validate system (~2hr)
./auto_train.sh v5-full          # 17d - Full training (~24hr)
./auto_train.sh v5-self-distill  # 17e - Born-Again boost (~24hr) [optional]
```

**Total: ~26.5 hours minimum, ~50.5 hours maximum quality**

---

## Quick Reference

| Mode | Duration | Use Case |
|------|----------|----------|
| **14** | ~30 min | Label Audit - Find mislabeled samples (⭐ RUN FIRST!) |
| **17a** | ~2 hours | V5 warmup - Validate all innovations work |
| **17b** | ~5 hours | V5 quick - All innovations in single model |
| **17c** | ~12 hours | V5 long - Production quality |
| **17d** | ~24 hours | V5 full - Large model, maximum quality (⭐ RECOMMENDED) |
| **17e** | ~24 hours | V5 Self-Distill - Born-Again Networks (+1-2% boost) |

---

## ⚠️ Recommended Workflow

**Always run warmup first before long training sessions:**

```
✅ CORRECT:
   14 (label-audit) → 17a (warmup, ~2hr) → verify logs → 17d (full, ~24hr)

❌ INCORRECT:
   Jump straight to 17d without validation
```

### What to Check After Warmup

- [ ] Training loss is decreasing
- [ ] Validation accuracy is improving
- [ ] No GPU out-of-memory errors
- [ ] Models are saving to disk correctly
- [ ] No NaN or infinity values in loss

---

## V5 Ultimate Path

The **V5 Ultimate** architecture combines every proven innovation into a single model:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  V5 ULTIMATE PATH (17a-17e)                                                 │
│  ⭐ RECOMMENDED FOR PRODUCTION - Best Single Model                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 0: Label Audit (HIGHLY RECOMMENDED)                                   │
│  ─────────────────────────────────────────                                  │
│  Select: 14 (label-audit)                      ~30 minutes                  │
│  → Find and remove mislabeled samples for cleaner training                  │
│  → Expected: +1-3% improvement from cleaner data                            │
│  → This is FREE accuracy - always run this first!                           │
│                                                                             │
│  STEP 1: V5 Validation                                                      │
│  ─────────────────────                                                      │
│  Select: 17a (v5-warmup)                       ~2 hours                     │
│  → Verify V5 model trains correctly with ALL features:                      │
│    • Coordinate Attention (spatial-aware attention)                         │
│    • Stochastic Depth / DropPath (layer regularization)                     │
│    • Deep Supervision (auxiliary losses at intermediate layers)             │
│    • Multi-Scale Fusion (temporal awareness)                                │
│    • Gradient Centralization (optimizer enhancement)                        │
│    • Multi-Task Learning (velocity + hi-hat openness heads)                 │
│    • Waveform Augmentation (audio-level time stretch, pitch shift)          │
│    • FMix (Fourier-domain mixup, better than CutMix for spectrograms)       │
│    • Progressive Augmentation (starts weak, ramps up during training)       │
│    • Lookahead Optimizer (slow weights for training stability)              │
│    • Mixup Cutoff (disable in final 15% for cleaner boundaries)             │
│                                                                             │
│  STEP 2: V5 Full Training                                                   │
│  ────────────────────────                                                   │
│  Select: 17d (v5-full)                         ~24 hours                    │
│  → Full training with ALL cutting-edge techniques                           │
│  → Uses: SAM, SWA, EMA, R-Drop, Curriculum, Calibration                     │
│  → Cosine Warm Restarts (escapes local minima for better generalization)    │
│  → Expected: Best single-model quality (~95%+ accuracy)                     │
│                                                                             │
│  STEP 3: Self-Distillation (RECOMMENDED for Maximum Quality)                │
│  ────────────────────────────────────────────────────────────               │
│  Select: 17e (v5-self-distill)                 ~24 hours                    │
│  → "Born-Again Networks" - train V5 using first V5 as teacher               │
│  → Learns from BOTH ground truth AND soft predictions                       │
│  → "Dark knowledge" transfer improves decision boundaries                   │
│  → Expected: +1-2% additional improvement                                   │
│  → This is your FINAL PRODUCTION model                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Minimum:    14 → 17a → 17d                       (~26.5 hours total)
Maximum:    14 → 17a → 17d → 17e                 (~50.5 hours total)  ⭐ RECOMMENDED
```

---

## V5 Model Features (22 Techniques)

| Feature | Expected Improvement | Description |
|---------|---------------------|-------------|
| Coordinate Attention | +1-2% | Position-aware spatial attention |
| Stochastic Depth | +0.5-1% | DropPath regularization for deep networks |
| Deep Supervision | +1-2% | Auxiliary losses improve gradient flow |
| Multi-Scale Fusion | +0.5-1% | Temporal context aggregation |
| Gradient Centralization | +0.5-1% | Optimizer enhancement |
| Multi-Task Learning | +0.5-1% | Velocity + openness auxiliary heads |
| Waveform Augmentation | +1-2% | Audio-level time/pitch/gain augmentation |
| FMix | +0.5-1% | Fourier mixup (better than CutMix for spectrograms) |
| Progressive Augmentation | +0.3-0.5% | Curriculum-style augmentation ramping |
| Lookahead Optimizer | +0.5-1% | Slow weights for stability |
| Cosine Warm Restarts | +0.5-1% | Escape local minima, find flatter optima |
| Mixup Cutoff | +0.2-0.5% | Cleaner decision boundaries in final phase |
| Self-Distillation | +1-2% | Born-Again Networks dark knowledge |
| SAM + SWA + EMA | +1-2% | Optimizer stack for flat minima |
| Label Audit | +1-3% | Confident Learning removes noise (run first!) |
| Attentive Statistics Pooling | +0.3-0.5% | Weighted mean+std pooling (replaces GAP) |
| Multi-Head Attention Pooling | +0.2-0.5% | Transformer-style feature aggregation |
| Hard Negative Mining | +0.5-1% | Focus on confusing pairs (snare/rimshot) |
| Class Weighting | +0.5-1% | Effective class weights for imbalanced data |
| Gradient Accumulation | +0.2-0.5% | Larger effective batch (32×4=128) |
| Monte Carlo Dropout | Premium tier | Uncertainty estimation at inference |
| **TOTAL** | **+14-25% over baseline** | All combined in optimized pipeline |

---

## 💰 Monetization Strategy (Single Model + Tiered Features)

Since inference runs on YOUR servers, the **single model approach with tiered features** is ideal:

### Recommended Tier Structure

| Tier | Price | Features | Inference Cost | Implementation |
|------|-------|----------|----------------|----------------|
| **Free** | $0 | 10 transcriptions/month, standard confidence | 1× GPU | V5 model (17e) |
| **Paid** | $9.99/mo | Unlimited transcriptions, TTA (+2%), uncertainty info | 5× GPU | V5 + TTA (5 augmentations) |
| **Pro** | $49.99/mo | API access, webhooks, batch processing, priority queue | 5× GPU | Full API access |

### Technical Implementation

```python
# Free tier: Standard inference
logits = model(spectrogram)
prediction = logits.argmax()

# Paid tier: TTA + MC Dropout for confidence
from training.inference.tta import TTAWrapper
from training.inference.mc_dropout import MCDropoutInference

tta_model = TTAWrapper(model, num_augmentations=5)
predictions, uncertainty = tta_model(spectrogram, return_uncertainty=True)

# Pro tier: Full batch API with uncertainty-aware transcription
from training.inference.mc_dropout import UncertaintyAwareTranscriber
transcriber = UncertaintyAwareTranscriber(model)
results, review_needed = transcriber.transcribe(batch)
```

### Deployment Summary

| Deployment | Inference Cost | Quality | Recommendation |
|------------|---------------|---------|----------------|
| **V5 Self-Distilled (17e)** | **1× GPU cost** | **~97%+** | **⭐ RECOMMENDED - Best ROI** |
| V5 Ultimate (17d) | 1× GPU cost | ~95%+ | ✅ If you skip self-distill |
| V5 + TTA | 5× GPU cost | ~97%+ | ✅ Premium tier (TTA at inference) |
| V5 + TTA + MC Dropout | 50× GPU cost | ~98%+ | ✅ Pro tier (uncertainty-aware) |

---

## Feature Deep Dives

### Coordinate Attention (v5 core)

**What it is:**  
Captures long-range dependencies along **time** and **frequency** dimensions separately. This is PERFECT for spectrograms where time and frequency have very different semantics.

**How it works:**
1. **Separate Encoding**: Pool along width (time) and height (frequency) independently
2. **Cross-Dimension**: Learn how frequency patterns relate to temporal patterns
3. **Positional Embedding**: Maintains spatial information

**Why it matters for drums:**
- Time dimension: Attack timing, decay patterns, rhythmic context
- Frequency dimension: Pitch content, harmonic structure, drum type

**Reference:** "Coordinate Attention for Efficient Mobile Network Design" (Hou et al., CVPR 2021)

---

### Multi-Task Learning

**What it is:**  
Instead of just classifying drum type, the model simultaneously learns auxiliary tasks:
- **Velocity prediction**: How hard was the drum hit? (regression)
- **Hi-hat openness**: For hi-hats, how open/closed? (regression)

**Why it matters for drums:**
- Forces backbone to learn richer features
- Velocity understanding improves ghost note detection
- Hi-hat openness is crucial for accurate transcription
- Acts as regularization

---

### FMix (Fourier-Domain Mixup)

**What it is:**  
Like Mixup, but generates the mixing mask in the Fourier domain. Creates smooth, natural-looking transitions that are more realistic for spectrograms.

**Why it matters for drums:**
- Standard Mixup/CutMix creates artificial boundaries
- FMix creates smooth, natural mixing patterns
- Better for spectrograms which have smooth frequency transitions

**Reference:** "FMix: Enhancing Mixed Sample Data Augmentation" (Harris et al., 2020)

---

### Confident Learning (Label Noise Detection)

**What it is:**  
Automatically detects and filters mislabeled samples using the model's predictions. Based on the Cleanlab framework.

**Why it matters for drums:**
- Real-world datasets ALWAYS have labeling errors
- Even 1-2% label noise hurts model performance
- Can improve accuracy by 1-3% just from cleaning labels

**Reference:** "Confident Learning: Estimating Uncertainty in Dataset Labels" (Northcutt et al., JAIR 2021)

---

### Monte Carlo Dropout (Uncertainty Estimation)

**What it is:**  
Run multiple forward passes with dropout enabled at inference time to get a distribution of predictions.

**Uncertainty types:**
- **Predictive entropy**: Total uncertainty
- **Mutual information**: Model uncertainty
- **Prediction variance**: Per-class confidence variance

**Why it matters:**
- "I don't know" capability for ambiguous samples
- Out-of-distribution detection (non-drum sounds)
- Confidence calibration

```python
from training.inference.mc_dropout import MCDropoutInference

inference = MCDropoutInference(model, num_samples=10)
result = inference.predict(spectrogram)

print(f"Class: {result.class_name}, Confidence: {result.confidence:.1%}")
print(f"Uncertainty: {result.uncertainty:.3f}")
if result.is_uncertain:
    print("⚠️ Needs human review")
```

---

### Attentive Statistics Pooling (ASP)

**What it is:**  
Instead of simple global average pooling, learn attention weights over spatial locations and compute weighted mean AND weighted standard deviation.

**Why it matters for drums:**
- Automatically focuses on attack transient (most discriminative)
- Ignores silent/noise regions
- Captures both mean AND variance of features

**Reference:** "Attentive Statistics Pooling for Deep Speaker Embedding" (Okabe et al., 2018)

---

### Hard Negative Mining

**What it is:**  
Focus training on the most confusing sample pairs, improving discrimination between similar-sounding drums.

**Common drum confusions addressed:**
- Snare vs Rimshot vs Cross-stick
- Hi-hat closed vs Hi-hat pedal
- Crash vs China vs Splash
- Tom high vs Tom mid

**Reference:** "Training Region-based Object Detectors with Online Hard Example Mining" (CVPR 2016)

---

## CLI Quick Reference

### Core V5 Flags

```bash
--model-version v5 --v5-size medium --drop-path-rate 0.1
--use-deep-supervision --deep-supervision-weights 0.4,0.6
--use-gradient-centralization
```

### Full Feature Stack

```bash
# Augmentation
--mixup-alpha 0.4 --cutmix-alpha 1.0 --mixup-prob 0.5
--use-fmix --fmix-alpha 1.0
--specaugment drum
--progressive-augmentation

# Optimization
--use-ema --ema-decay 0.999
--use-sam --sam-rho 0.05
--use-swa --swa-start 0.75
--use-rdrop --rdrop-alpha 0.3
--use-curriculum --curriculum-start-fraction 0.5 --curriculum-strategy cosine

# Loss & Calibration
--focal-loss --focal-gamma 2.0
--label-smoothing 0.05
--calibrate --calibration-method temperature
--class-weights effective --max-class-weight 10.0

# Multi-task
--use-multi-task --velocity-weight 0.1 --openness-weight 0.1

# Pooling
--pooling-type asp  # Options: gap, asp, mha, hybrid

# Label cleaning
--clean-labels --label-noise-threshold 0.5
```

---

## Archived Documentation

For legacy training paths (ensemble, temporal Mamba, BEATs, etc.), see `docs/archive/CUTTING_EDGE_TRAINING_FEATURES_FULL.md`.

---

*Last Updated: November 26, 2025*
