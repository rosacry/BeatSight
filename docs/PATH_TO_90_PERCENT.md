# Path to 90%+ Validation Accuracy

## 🎯 Current Training Status (December 2025)

**Active Training Mode:** `v5-local-balanced` (17d-balanced)  
**Hardware:** RTX 3080 Ti FE (12GB), 9800X3D, 32GB DDR5-6000, Samsung 990 Pro NVMe  
**Training Path:** `14 → 17a → 17d-balanced → 17e-local → 19 → 19c`

### Current Progress
- **Mode:** v5-local-balanced with UNIFORM balanced sampling
- **Speed:** ~2.7 it/s (~0.37s per batch)
- **Per epoch:** ~3 hours
- **Expected total:** 4-7 days (with early stopping at epoch 30-50)

---

## 🚨 Critical Discovery: Catastrophic Class Collapse

**Date: 2025-01-21**

### Per-Class Evaluation Results

We ran per-class evaluation on the "41% accuracy" model and discovered **catastrophic class collapse**:

| Category | Classes | Accuracy |
|----------|---------|----------|
| 🔴 **FAILING** (0%) | **19 classes** | 0.0% - complete collapse! |
| 🟢 **WORKING** (>60%) | **2 classes** | snare_rimshot (91.6%), aux_percussion (77.2%) |

**The model learned NOTHING about 19 out of 21 classes!**

### Confusion Analysis

All samples from failing classes are predicted as the dominant 2 classes:

| True Class | Predicted As |
|------------|--------------|
| china (0%) | 68% snare_rimshot, 32% aux_percussion |
| crash (0%) | 99% snare_rimshot |
| kick (0%) | ~90% snare_rimshot |
| hihat_closed (0%) | 70% snare_rimshot, 30% aux_percussion |
| ALL 19 OTHERS | → dominant 2 classes |

### Why 41% Overall Looks Okay But Is Actually Terrible

The 41% comes from:
- **snare_rimshot**: 27% of val × 91.6% acc = ~24.7%
- **aux_percussion**: 21% of val × 77.2% acc = ~16.2%
- **Total**: ~40.9% (matches our 41%)
- **Everything else**: 0% contribution

**The model is essentially a 2-class classifier that ignores 19 classes!**

---

## Root Cause: Insufficient Class Balancing

The "effective" class weights only provided a **2x ratio** (min=0.901, max=1.908).

For a **630x imbalance**, this is completely insufficient:
- `hihat_closed`: 6,387 samples → weight 1.908
- `snare_rimshot`: 4,024,285 samples → weight 0.901
- **Actual ratio: 2x** (should be ~630x or at least sqrt(630)≈25x)

The model sees snare_rimshot **315 times more often** than hihat_closed, but only down-weights it **2x**. The gradient signal from rare classes is completely drowned out.

---

## ✅ The Fix: Class-Balanced Sampling

### Implementation Complete

Added `--balanced-sampling` option to training:

```bash
# New flags
--balanced-sampling           # Enable class-balanced sampling
--sampling-strategy sqrt      # sqrt (25x), log, or uniform (pure equal)
--class-weights none          # Disable class weights (avoid double-weighting)
```

### How It Works

1. **Compute sample weights** based on inverse class frequency
2. **WeightedRandomSampler** ensures each class is seen more equally
3. **sqrt strategy** provides ~25x rebalancing ratio (vs 2x before)

### v5-local Mode Updated

```bash
# Old (broken):
--class-weights effective --max-class-weight 10.0

# New (fixed):
--balanced-sampling --sampling-strategy sqrt --class-weights none
```

### Expected Impact

| Before | After |
|--------|-------|
| snare_rimshot seen 315x more often | snare_rimshot seen ~5x more often |
| hihat_closed effectively invisible | hihat_closed gets 25x boost |
| 19 classes at 0% accuracy | All classes should learn |

---

## Dataset Analysis

### Class Distribution (630x Imbalance!)

| Tier | Classes | Samples | % of Data |
|------|---------|---------|-----------|
| **RARE** (<100k) | 9 classes | 394,583 | 2.69% |
| **MEDIUM** (100k-500k) | 6 classes | 1,954,427 | 13.31% |
| **COMMON** (500k-2M) | 4 classes | 5,207,423 | 35.47% |
| **DOMINANT** (>2M) | 2 classes | 7,124,715 | 48.53% |

#### Rare Classes (< 100k samples):
```
hihat_closed        :     6,387 (0.04%)  ← CRITICALLY RARE (630x less than largest)
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
snare_rimshot       : 4,024,285 (27.41%)  ← MODEL PREDICTS EVERYTHING AS THIS
```

---

## The Path Forward

### Phase 1: Class-Balanced Sampling ✅ IMPLEMENTED
**Expected improvement: +30-40%**

With sqrt rebalancing:
- Rare classes will finally contribute to training
- Model will learn discriminative features for all 21 classes
- Expect significant jump in first few epochs

### Phase 2: Self-Distillation (17e-local)
After v5-local-balanced completes:
```bash
bash ai-pipeline/training/tools/auto_train.sh v5-local-balanced-distill
```
Expected: +1-2% accuracy from dark knowledge transfer

### Phase 3: Multi-Label Training (19 → 19c)
For detecting simultaneous drum hits:
```bash
# Generate multi-label dataset first
bash ai-pipeline/training/tools/post_export_commands.sh
# Select option 19

# Then run multi-label finetuning
bash ai-pipeline/training/tools/auto_train.sh multilabel-finetune
```

---

## Commands

### Run Training with Balanced Sampling (CURRENT)
```bash
cd /c/github/BeatSight
bash ai-pipeline/training/tools/auto_train.sh v5-local-balanced
```

### Run Quick Class Check (during training)
```bash
cd /c/github/BeatSight
PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/quick_class_check.py \
    --checkpoint ai-pipeline/training/runs/cutting_edge/v5/local-balanced/checkpoints/latest_checkpoint.pth \
    --v5-size large
```

### Run Full Per-Class Evaluation (after training)
```bash
cd /c/github/BeatSight
PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/evaluate_per_class_v5.py \
    --checkpoint ai-pipeline/training/runs/cutting_edge/v5/local-balanced/best_drum_classifier.pth \
    --v5-size large \
    --fraction 0.1 \
    --output docs/per_class_analysis.json
```

---

## 🖥️ LOCAL GPU Training Path (Your Hardware)

**Hardware Profile:**
- RTX 3080 Ti FE (12GB VRAM)
- AMD Ryzen 9800X3D (8c/16t)
- 32GB DDR5-6000 MT/s
- C: Samsung 990 Pro 2TB NVMe (7000/5100 MB/s) - feature_cache
- E: Seagate 2TB HDD (120 MB/s) - dataset (not used during training)
- Internet: 580 Mbps down / 520 Mbps up

**Complete Training Path:**
```
14 → 17a → 17d-balanced → 17e-local → 19 → 19c
```

| Step | Mode | Time Estimate | Purpose |
|------|------|---------------|---------|
| 14 | label-audit | ~30 min | Find noisy labels |
| 17a | v5-warmup | ~1 hr | Validate setup |
| 17d-balanced | v5-local-balanced | **4-7 days** | Main training with balanced sampling |
| 17e-local | v5-local-balanced-distill | **4-7 days** | Self-distillation +1-2% |
| 19 | generate-multilabel | ~10 min | Create multi-label dataset |
| 19c | multilabel-finetune | ~1-2 days | Simultaneous drum detection |

**Total: ~15-25 days** for production-ready model

---

## Expected Training Progress

With uniform balanced sampling:
- **Epoch 1**: 8-12% accuracy (learning begins)
- **Epoch 5**: 25-35% accuracy
- **Epoch 10**: 45-55% accuracy
- **Epoch 20**: 65-75% accuracy
- **Epoch 30-50**: 80-90%+ (early stopping likely here)
