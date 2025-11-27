# BeatSight Ultimate Training Roadmap

*The definitive guide to training, deploying, and monetizing BeatSight's AI*

**Last Updated:** November 27, 2025  
**Goal:** Revolutionary drum transcription AI with patent-protected IP  
**Business Model:** Subscription service (server-side inference)

---

## 🎯 Executive Summary

You want to build the **best possible AI** that is:
1. **Revolutionary** - Novel architecture that's publishable
2. **Monetizable** - Patent-protected IP with competitive moat
3. **Production-ready** - Deployable as a subscription service

**⭐ RECOMMENDED DEFAULT: Path G (V5 Ultimate)**
```
17a → 17d
Total: ~26 hours of training
Result: Best single-model quality with all 2024 innovations

This is the pragmatic choice for shipping a great product fast.
```

**For Novel IP/Patents: Path F (Ultimate)**
```
13b → 12c → 16d → 5× ultimate ensemble → distill
Total: ~280 hours of training
Result: 4 Novel contributions + Maximum accuracy + Cheap deployment

Innovations combined:
1. Wav2Vec2 frozen embeddings (audio foundation model semantics)
2. Multi-resolution spectrograms (3-scale time-frequency analysis)
3. Mamba temporal layers (state-space contextual modeling)
4. Beat-aware positional encoding (musical structure awareness)
5. Drum pattern priors (32 groove prototypes with attention)
```

**Strategy:** Start with Path G for your v1.0, then add Path E/F innovations for a premium tier later.

---

## 📋 Master Checklist

### Phase 0: Quick Production Model (⭐ START HERE)

**Path G: V5 Ultimate (RECOMMENDED DEFAULT)**

| Step | Mode | Duration | Purpose | Status |
|------|------|----------|---------|--------|
| 1 | **17a** (v5-warmup) | ~2 hrs | Validate V5 system works | ⬜ Not Started |
| 2 | **17d** (v5-full) | ~24 hrs | Full V5 with all innovations | ⬜ Not Started |

**Commands:**
```bash
# Step 1: Validate V5
./post_export_commands.sh  # Select 17 (V5 warmup)

# Step 2: Full V5 training
./post_export_commands.sh  # Select 20 (V5 full)
```

This gets you a **production-ready model in ~26 hours** with:
- Coordinate Attention (+1-2%)
- Stochastic Depth/DropPath (+0.5-1%)
- Deep Supervision (+1-2%)
- Gradient Centralization (+0.5-1%)
- Multi-Scale Fusion (+0.5-1%)

**Total improvement: +3-6% over baseline v4**

---

### Phase 1: Advanced Training (For Patents/Research)

**Option A: Ultimate Path (MAXIMUM REVOLUTIONARY - FOR PATENTS)**

| Step | Mode | Duration | Purpose | Status |
|------|------|----------|---------|--------|
| 1 | **13b** (ssl-pretrain-full) | ~12 hrs | SSL pretrain on unlabeled audio | ⬜ Not Started |
| 2 | **12c** (enhanced-long) | ~18 hrs | Train best CNN backbone | ⬜ Not Started |
| 3 | **16a** (ultimate-warmup) | ~5 hrs | Validate ultimate system works | ⬜ Not Started |
| 4 | **16d** (ultimate-full) | ~40 hrs | Full ultimate with pretrained CNN | ⬜ Not Started |
| 5 | **16d** ×4 more | ~160 hrs | Train 4 more ultimate models (different seeds) | ⬜ Not Started |
| 6 | **Ensemble** | ~2 hrs | Combine 5 ultimate models | ⬜ Not Started |
| 7 | **Distill** | ~8 hrs | Compress ensemble for deployment | ⬜ Not Started |

**Commands:**
```bash
# Step 1: SSL Pretraining (optional but recommended)
./post_export_commands.sh  # Select 13b

# Step 2: Train CNN backbone
./post_export_commands.sh  # Select 12c

# Step 3: Validate ultimate (after 12c completes)
./post_export_commands.sh  # Select 16a

# Step 4: Full ultimate training
./post_export_commands.sh  # Select 16d

# Steps 5-7: Manual (see detailed instructions below)
```

**Option B: Temporal Path (FASTER PATENTABLE ALTERNATIVE)**

| Step | Mode | Duration | Purpose | Status |
|------|------|----------|---------|--------|
| 1 | **12c** (enhanced-long) | ~18 hrs | Train best CNN backbone | ⬜ Not Started |
| 2 | **15a** (temporal-warmup) | ~3 hrs | Validate temporal system works | ⬜ Not Started |
| 3 | **15d** (temporal-full) | ~24 hrs | Full temporal model with pretrained CNN | ⬜ Not Started |
| 4 | **15d** ×4 more | ~96 hrs | Train 4 more temporal models (different seeds) | ⬜ Not Started |
| 5 | **Ensemble** | ~2 hrs | Combine 5 temporal models | ⬜ Not Started |
| 6 | **Distill** (11b equivalent) | ~8 hrs | Compress ensemble for deployment | ⬜ Not Started |

### Phase 2: Evaluate & Document Results

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 1 | Run evaluation on test set | ⬜ Not Started | **MISSING: Need temporal/ultimate evaluation script** |
| 2 | Measure edge case accuracy | ⬜ Not Started | Ghost notes, swing timing, audio bleed |
| 3 | Compare to CNN baseline | ⬜ Not Started | Need both models trained first |
| 4 | Document results for patent | ⬜ Not Started | Specific numbers, improvements |
| 5 | Create ablation study | ⬜ Not Started | Prove each component contributes |

### Phase 3: Protect IP

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 1 | Draft provisional patent claims | ⬜ Not Started | See PATENT_AND_MONETIZATION_STRATEGY.md |
| 2 | File with USPTO | ⬜ Not Started | ~$320 filing fee |
| 3 | Post preprint to arXiv | ⬜ Not Started | AFTER patent filing! |

### Phase 4: Deploy

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 1 | ONNX export of ultimate model | ⬜ Not Started | **MISSING: Ultimate ONNX export** |
| 2 | Integrate with Modal GPU service | ⬜ Not Started | **MISSING: Ultimate model loading** |
| 3 | Update API endpoints | ⬜ Not Started | Backend exists but uses CNN |
| 4 | Test end-to-end | ⬜ Not Started | Full pipeline validation |

### Phase 5: Publish & Monetize

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 1 | Write ISMIR/SMC paper | ⬜ Not Started | 8-page format |
| 2 | Submit to conference | ⬜ Not Started | ISMIR deadline: ~Oct, SMC: ~Feb |
| 3 | Launch subscription service | ⬜ Not Started | Usage-based pricing (single model) |
| 4 | Approach DAW companies for licensing | ⬜ Not Started | After paper acceptance |

---

## 🔴 Gaps Identified (What's Missing)

### Critical Gaps (Must Fix Before Training Completes)

| Gap | Description | File Needed | Priority |
|-----|-------------|-------------|----------|
| **Ultimate Evaluation Script** | No way to evaluate ultimate model on test set | `evaluate_ultimate.py` | 🔴 Critical |
| **Ultimate ONNX Export** | Current ONNX exporter doesn't handle audio inputs | `onnx_export.py` update | 🔴 Critical |
| **Ultimate Ensemble Training** | No script to train multiple ultimate models | `train_ultimate_ensemble.sh` | 🔴 Critical |
| **Ultimate Distillation** | Can't distill ultimate ensemble | `distill_ultimate.py` | 🔴 Critical |
| **Sequence Dataset with Audio** | Dataset needs to return raw audio for Wav2Vec2 | `sequence_dataset.py` update | 🔴 Critical |

### Important Gaps (Need Before Deployment)

| Gap | Description | Current State | Priority |
|-----|-------------|---------------|----------|
| **Modal Integration** | Modal app doesn't load temporal models | Uses CNN only | 🟡 High |
| **Beat Detection Integration** | Temporal model expects beat positions | Not connected to beat tracker | 🟡 High |
| **Streaming Inference API** | Real-time inference not exposed | Class exists, not wired | 🟡 High |

### Nice-to-Have (Can Wait)

| Gap | Description | Priority |
|-----|-------------|----------|
| Edge case test dataset | Curated ghost notes, swing, bleed examples | 🟢 Low |
| Ablation study scripts | Automated comparison of components | 🟢 Low |
| Paper LaTeX template | Pre-formatted for ISMIR | 🟢 Low |

---

## ✅ What's Already Done

### Training Infrastructure (Complete)

| Component | File | Status |
|-----------|------|--------|
| Temporal Mamba Model | `training/models/temporal_mamba.py` | ✅ Complete (1400+ lines, includes Ultimate) |
| Ultimate Model | `training/models/temporal_mamba.py` | ✅ `UltimateTemporalDrumTranscriber` class |
| Audio Foundation Features | `training/models/audio_foundation.py` | ✅ Complete (~400 lines, Wav2Vec2/HuBERT) |
| Multi-Resolution Specs | `training/models/multi_resolution.py` | ✅ Complete (~450 lines, 3-scale) |
| Sequence Dataset | `training/datasets/sequence_dataset.py` | ✅ Complete (543 lines) |
| Training Script | `training/train_temporal.py` | ✅ Complete (~700 lines, supports --ultimate-mode) |
| Shell Integration | `post_export_commands.sh`, `auto_train.sh` | ✅ Modes 15a-15d, 16a-16d |
| Documentation | `TEMPORAL_MAMBA_IMPLEMENTATION.md` | ✅ Complete |
| Documentation | `CUTTING_EDGE_TRAINING_FEATURES.md` | ✅ Updated with Path F |
| Research Roadmap | `RESEARCH_ROADMAP.md` | ✅ Complete |
| Patent Strategy | `PATENT_AND_MONETIZATION_STRATEGY.md` | ✅ Complete |

### Deployment Infrastructure (Partial)

| Component | File | Status |
|-----------|------|--------|
| ONNX Export | `training/export/onnx_export.py` | ✅ Works for CNN, ❌ Not for temporal |
| Modal GPU Service | `ai-pipeline/modal_app.py` | ✅ Works for CNN, ❌ Not for temporal |
| Backend API | `backend/app/` | ✅ Complete infrastructure |
| Evaluation Script | `tools/evaluate_classifier.py` | ✅ Works for CNN, ❌ Not for temporal |

---

## 📝 Detailed Implementation Plan

### Step 1: Train CNN Backbone (12c)

**Status:** ⬜ Not Started

```bash
cd /c/github/BeatSight/ai-pipeline/training/tools
./post_export_commands.sh
# Select: 12c (enhanced-long)
```

**Expected Duration:** ~18 hours  
**Output:** `$BEATSIGHT_RUN_CUTTING_EDGE/enhanced/long/best.pt`

**What This Does:**
- Trains v4 model with Coordinate Attention
- Multi-task learning (drum type + intensity)
- FMix augmentation
- All cutting-edge features

### Step 2: Validate Temporal System (15a)

**Status:** ⬜ Not Started  
**Prerequisite:** Step 1 complete

```bash
./post_export_commands.sh
# Select: 15a (temporal-warmup)
```

**Expected Duration:** ~3 hours  
**Purpose:** Verify temporal training works before committing to long run

**What to Check:**
- [ ] Loss decreasing
- [ ] No GPU OOM errors
- [ ] Sequence batching working
- [ ] wandb logging (if enabled)

### Step 3: Full Temporal Training (15d)

**Status:** ⬜ Not Started  
**Prerequisite:** Step 2 passes validation

```bash
./post_export_commands.sh
# Select: 15d (temporal-full)
```

**Expected Duration:** ~24 hours  
**Output:** `$BEATSIGHT_RUN_CUTTING_EDGE/temporal/full/best.pt`

**What This Does:**
- Uses pretrained CNN from Step 1
- Freezes CNN for first 10 epochs
- Full Mamba temporal modeling
- Beat-aware positional encoding
- Drum pattern priors

### Step 4: Train Temporal Ensemble (4 More Models)

**Status:** ⬜ Not Started  
**Prerequisite:** Step 3 complete

**⚠️ MISSING IMPLEMENTATION**

Need to create: `train_temporal_ensemble.sh`

```bash
# Proposed implementation:
for seed in 42 1337 2024 9999; do
    python train_temporal.py \
        --dataset "$BEATSIGHT_DATASET_DIR" \
        --epochs 150 \
        --seed $seed \
        --pretrained-cnn "$ENHANCED_CNN_PATH" \
        --output-dir "$OUTPUT_DIR/temporal_seed_$seed"
done
```

### Step 5: Combine Ensemble

**Status:** ⬜ Not Started  
**Prerequisite:** Step 4 complete

**⚠️ MISSING IMPLEMENTATION**

Need to create: `ensemble_temporal.py`

Functionality needed:
- Load 5 temporal models
- Create wrapper that averages predictions
- Support for different weighting schemes

### Step 6: Distill to Single Model

**Status:** ⬜ Not Started  
**Prerequisite:** Step 5 complete

**⚠️ MISSING IMPLEMENTATION**

Need to create: `distill_temporal.py`

Functionality needed:
- Teacher: 5-model temporal ensemble
- Student: Single temporal model (or even single CNN)
- Knowledge distillation with soft targets
- Temperature scaling for soft labels

---

## 🔧 Implementation Tasks (Priority Order)

### Task 1: Create Temporal Evaluation Script 🔴

**File:** `ai-pipeline/training/tools/evaluate_temporal.py`

**Requirements:**
```python
# Must support:
- Load TemporalDrumTranscriber checkpoint
- Evaluate on sequence dataset (not individual windows)
- Report per-class F1, especially for edge cases:
  - Ghost notes (snare, tom)
  - Hi-hat variations (open/closed/pedal)
  - Soft hits vs silence
- Compare to CNN baseline
- Output JSON report for patent documentation
```

**Suggested Implementation:**
```python
def evaluate_temporal(
    checkpoint_path: str,
    dataset_path: str,
    output_path: str,
    baseline_checkpoint: Optional[str] = None
) -> dict:
    """
    Evaluate temporal model and optionally compare to baseline.
    
    Returns:
        Dictionary with:
        - overall_f1: float
        - per_class_f1: dict[str, float]
        - edge_case_f1: dict[str, float]  # ghost_notes, swing, bleed
        - confusion_matrix: np.ndarray
        - comparison: dict (if baseline provided)
    """
```

### Task 2: Update ONNX Export for Temporal 🔴

**File:** `ai-pipeline/training/export/onnx_export.py`

**Current State:** Only handles CNN with fixed input shape  
**Needed:** Handle sequence input for temporal model

**Changes Required:**
```python
def export_temporal_onnx(
    model: TemporalDrumTranscriber,
    output_path: str,
    sequence_length: int = 32,
    ...
):
    """
    Export temporal model to ONNX.
    
    Input shape: [batch, seq_len, 1, 128, 128]
    Output shape: [batch, seq_len, num_classes]
    
    Special handling:
    - Mamba state-space model
    - Beat positional encoding (optional inputs)
    """
```

### Task 3: Create Temporal Ensemble Script 🔴

**File:** `ai-pipeline/training/tools/train_temporal_ensemble.sh`

**Functionality:**
- Train 5 temporal models with different seeds
- Use same pretrained CNN for all
- Track all runs in wandb with group tag
- Save all checkpoints with consistent naming

### Task 4: Create Temporal Distillation Script 🔴

**File:** `ai-pipeline/training/distill_temporal.py`

**Functionality:**
- Load ensemble of temporal models as teacher
- Train student model with soft targets
- Temperature scaling (T=2-4 typical)
- Optional: Distill to single CNN for maximum speed

### Task 5: Update Modal for Temporal 🟡

**File:** `ai-pipeline/modal_app.py`

**Changes:**
- Add temporal model loading option
- Handle sequence-based inference
- Support streaming inference mode
- Add model selection parameter (CNN vs temporal)

---

## 📊 Success Metrics

### Training Success

| Metric | CNN Baseline (Path A) | Temporal (Path E) | Target |
|--------|----------------------|-------------------|--------|
| Overall F1 | ~88-92% | ? | >92% |
| Ghost notes F1 | ~65-70% | ? | >80% |
| Swing timing | ~75-80% | ? | >88% |
| Audio bleed | ~70-75% | ? | >82% |

### Deployment Success

| Metric | Target | Notes |
|--------|--------|-------|
| Inference latency | <200ms per window | For real-time playback |
| Throughput | >1000 windows/second | Batch processing |
| Model size (ONNX) | <100MB | For edge deployment option |

### Business Success

| Metric | Target | Timeline |
|--------|--------|----------|
| Patent filed | 1 provisional | Before arXiv posting |
| Paper submitted | ISMIR or SMC | Within 6 months |
| Subscription launch | Live | Within 3 months |
| First licensing deal | 1 DAW company | Within 12 months |

---

## 📅 Recommended Timeline

| Week | Focus | Key Deliverable |
|------|-------|-----------------|
| **1** | Training 12c | CNN backbone complete |
| **2** | Training 15a + 15d | First temporal model |
| **2-3** | Build evaluation script | Measure improvements |
| **3** | File provisional patent | IP protected |
| **3-4** | Train ensemble (4 more models) | 5 temporal models |
| **4** | Distill + ONNX export | Deployable model |
| **4-5** | Modal integration | End-to-end working |
| **5-6** | Write paper | Draft for submission |
| **6** | Launch beta | First paying customers |
| **6-8** | Submit to ISMIR/SMC | Publication in progress |

---

## 📚 Related Documentation

| Document | Purpose |
|----------|---------|
| `CUTTING_EDGE_TRAINING_FEATURES.md` | All training modes and features |
| `TEMPORAL_MAMBA_IMPLEMENTATION.md` | Technical details of temporal model |
| `RESEARCH_ROADMAP.md` | Publication strategy |
| `PATENT_AND_MONETIZATION_STRATEGY.md` | IP and business strategy |
| `DEPLOYMENT.md` | Production deployment guide |
| `IMPLEMENTATION_STATUS.md` | Overall project status |

---

## 🚀 Quick Start

**If you're ready to start training right now:**

```bash
# 1. Navigate to training tools
cd /c/github/BeatSight/ai-pipeline/training/tools

# 2. Start CNN backbone training (~18 hours)
./post_export_commands.sh
# Select: 12c

# 3. Monitor training
tail -f logs/training.log

# 4. After 12c completes, start temporal warmup
./post_export_commands.sh
# Select: 15a

# 5. If warmup looks good, start full temporal
./post_export_commands.sh
# Select: 15d
```

**After training completes, come back to this document and work through the Phase 2-5 checklists.**

---

*This document is the single source of truth for BeatSight's AI training and deployment roadmap. Update status checkboxes as you complete each step.*
