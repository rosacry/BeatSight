# Opus Session Prompt: Post-Training Optimization & Production Deployment

## Archive Metadata

- **Document Type:** Session prompt (archived)
- **Status:** Historical reference only
- **Normalized On:** 2026-02-13
- **Canonical Location:** `ai-pipeline/documentation/archive/prompts/session/`
- **Current Source of Truth:** `ai-pipeline/documentation/current/`

## 🎉 Session Context: World-Class Drum Transcription Model

A 12-class multi-label drum classifier has been successfully trained to **0.90+ F1** (and climbing). This model may represent the **best publicly-available drum transcription system** based on:
- Multi-label detection (simultaneous instruments)
- 12 distinct drum classes (not just kick/snare/hihat)
- Extensive synthesis pipeline for rare classes
- State-of-the-art architecture (CNN V5 Large, 7.1M params)

**Your mission:** Complete the post-training pipeline to make this production-ready.

---

## 📊 Training Results Summary

| Metric | Value | Notes |
|--------|-------|-------|
| **Model** | CNN V5 Large | 7,143,308 parameters |
| **Dataset** | 12.8M samples | EGMD + Groove + Slakh + Lakh-Synth |
| **Micro-F1** | 0.9039+ | Epoch 4, still improving |
| **Macro-F1** | 0.9033+ | Balanced across classes |
| **Run Dir** | `runs/v5_multilabel_final_v2/` | |

### Per-Class F1 Scores (Epoch 4)

| Class | F1 | Status |
|-------|-----|--------|
| splash | 0.990 | 🟢 Excellent |
| china | 0.988 | 🟢 Excellent |
| snare | 0.937 | 🟢 Above target |
| kick | 0.935 | 🟢 Above target |
| tom | 0.932 | 🟢 Above target |
| cross_stick | 0.921 | 🟢 Above target |
| ride_bell | 0.893 | 🟡 Almost |
| crash | 0.892 | 🟡 Almost |
| hihat_closed | 0.878 | 🟡 Improving |
| ride_bow | 0.868 | 🟡 Improving |
| hihat_open | 0.806 | 🟠 Struggling (acoustic confusion) |
| hihat_pedal | 0.800 | 🟠 Struggling (acoustic confusion) |

---

## 🎯 Your Tasks (Priority Order)

### Task 1: Per-Class Threshold Tuning ⚡ HIGH PRIORITY

**Goal:** Find optimal sigmoid threshold for each class to maximize F1.

**Script:** `training/multilabel/tune_thresholds.py`

**Current Issue:** The script uses `CachedMultiLabelDataset` but the training uses `BatchedMultiLabelDataset`. It needs to be updated or you need to create a simpler threshold tuning script.

**Steps:**
1. Load the trained model from `runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt`
2. Run inference on validation set (sources: egmd, groove_midi, slakh, lakh_synth)
3. For each class, sweep thresholds 0.1-0.9 and find optimal F1
4. Save to `runs/v5_multilabel_final_v2/thresholds.json`

**Expected Output:**
```json
{
  "global_threshold": 0.5,
  "per_class_thresholds": {
    "china": 0.45,
    "crash": 0.50,
    "cross_stick": 0.50,
    "hihat_closed": 0.55,
    "hihat_open": 0.40,
    "hihat_pedal": 0.35,
    "kick": 0.45,
    "ride_bell": 0.45,
    "ride_bow": 0.50,
    "snare": 0.55,
    "splash": 0.45,
    "tom": 0.50
  }
}
```

**Dataset Location:** `F:/datasets/multilabel_real_v3/`
- `egmd/egmd_manifest.json`
- `groove_midi/groove_manifest.json`
- `slakh/slakh_manifest.json`
- `lakh_synth/lakh_synth_manifest.json`

---

### Task 2: Full Pipeline Integration Test 🔧 HIGH PRIORITY

**Goal:** Test the complete transcription pipeline end-to-end.

**Script:** `transcription/full_pipeline.py`

**Pipeline Flow:**
```
Audio → Onset Detection → Multi-Label Classification → Count Estimation → Pitch Ranking → Final Events
```

**Test Steps:**
1. Find a test audio file (or use any drum audio)
2. Load the pipeline with the trained model and thresholds
3. Run transcription
4. Verify output events have correct labels

**Test Code:**
```python
from transcription.full_pipeline import DrumTranscriptionPipeline, PipelineConfig

config = PipelineConfig(
    per_class_thresholds=thresholds,  # From Task 1
    enable_pitch_ranking=True,
    enable_count_estimation=True,
)

pipeline = DrumTranscriptionPipeline(
    multilabel_model_path="runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt",
    thresholds_path="runs/v5_multilabel_final_v2/thresholds.json",
    config=config,
)

result = pipeline.transcribe("path/to/test_audio.wav")

# Check results
for event in result.events[:20]:
    print(f"{event.time:.3f}s: {event.label} ({event.confidence:.2f})")
```

---

### Task 3: Pitch Ranking Validation 🎵 MEDIUM PRIORITY

**Goal:** Verify cymbal/tom pitch ranking works correctly.

**Implementation:** `transcription/instrument_pitch_ranker.py` (782 lines, complete)

**How Pitch Ranking Works:**
- `crash` → `crash_1, crash_2, crash_3, crash_4` (highest pitch = _1)
- `china` → `china_1, china_2`
- `splash` → `splash_1, splash_2`
- `ride_bow` → `ride_bow_1, ride_bow_2`
- `ride_bell` → `ride_bell_1, ride_bell_2`
- `tom` → `tom_1, tom_2, tom_3, tom_4` (highest pitch = _1)

**Validation Steps:**
1. Find/create test audio with multiple crashes or toms
2. Run the classifier to get base labels
3. Run pitch ranking
4. Verify different cymbals get different suffixes

**Documentation:**
- `docs/CYMBAL_PITCH_RANKING.md` - Technical details
- `docs/TOM_PITCH_RANKING.md` - Tom-specific details
- `docs/INSTRUMENT_PITCH_RANKING.md` - Overview

---

### Task 4: External Benchmark Evaluation 📈 MEDIUM PRIORITY

**Goal:** Validate "best in world" claim with external datasets.

**Potential External Datasets:**
| Dataset | Description | Location |
|---------|-------------|----------|
| ENST-Drums | Real recordings with annotations | `E:/data/raw/ENST-Drums/` (if available) |
| IDMT-SMT-Drums | Synthesized drums | Extract via `extract_multilabel_from_midi.py` |
| MedleyDB | Full mixes with annotations | (may need to download) |

**Evaluation Approach:**
1. Extract test set from external dataset (no overlap with training)
2. Run inference with trained model
3. Compute F1 per class and overall
4. Compare with published baselines

**Note:** The current datasets (EGMD, Groove-MIDI, Slakh) are already comprehensive. External evaluation is for "bragging rights" validation.

---

### Task 5: Production Model Export 📦 LOWER PRIORITY

**Goal:** Export final model for production deployment.

**Model Files to Export:**
- `best_multilabel_model_ema.pt` (29MB) - Best for inference
- `thresholds.json` - Per-class thresholds
- `config.json` - Model configuration

**Export Location:** 
- `ai-pipeline/models/drum_classifier_production/`
- Or: Upload to cloud storage / model registry

---

## 🛠️ Technical Reference

### 12-Class Label Order (CRITICAL)

```python
DEFAULT_DRUM_COMPONENTS = [
    "china",        # 0
    "crash",        # 1
    "cross_stick",  # 2
    "hihat_closed", # 3
    "hihat_open",   # 4
    "hihat_pedal",  # 5
    "kick",         # 6
    "ride_bell",    # 7
    "ride_bow",     # 8
    "snare",        # 9
    "splash",       # 10
    "tom",          # 11
]
```

### EMA Weight Loading (IMPORTANT)

The EMA weights are nested and have a `backbone.` prefix:

```python
import torch
from models.cnn_v5 import cnn_v5_large

# Load checkpoint
ckpt = torch.load(
    "runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt",
    map_location="cuda",
    weights_only=False
)

# EMA checkpoint is the direct state_dict (no nesting)
state_dict = ckpt

# Strip 'backbone.' prefix
cleaned = {k.replace('backbone.', ''): v for k, v in state_dict.items()}

# Create model and load
model = cnn_v5_large(num_classes=12)
model.load_state_dict(cleaned, strict=False)
model.eval()
```

**Alternative (from full checkpoint):**
```python
ckpt = torch.load("runs/v5_multilabel_final_v2/best_checkpoint.pt", weights_only=False)

# Full checkpoint has nested EMA
ema_state = ckpt['ema_state_dict']['ema_model']
cleaned = {k.replace('backbone.', ''): v for k, v in ema_state.items()}
model.load_state_dict(cleaned, strict=False)
```

### Dataset Loading (BatchedMultiLabelDataset)

```python
from training.multilabel.dataset import BatchedMultiLabelDataset
from torch.utils.data import ConcatDataset

manifests = [
    'F:/datasets/multilabel_real_v3/egmd/egmd_manifest.json',
    'F:/datasets/multilabel_real_v3/groove_midi/groove_manifest.json',
    'F:/datasets/multilabel_real_v3/slakh/slakh_manifest.json',
    'F:/datasets/multilabel_real_v3/lakh_synth/lakh_synth_manifest.json',
]

val_datasets = []
for manifest in manifests:
    ds = BatchedMultiLabelDataset(
        manifest_path=manifest,
        is_train=False,  # Validation split
        num_classes=12,
        shuffle_before_split=True,
        split_seed=42,
    )
    val_datasets.append(ds)

val_dataset = ConcatDataset(val_datasets)
```

### Checkpoint Structure Reference

```python
checkpoint = {
    'epoch': N,
    'model_state_dict': {...},       # Keys have 'backbone.' prefix
    'optimizer_state_dict': {...},
    'scheduler_state_dict': {...},
    'ema_state_dict': {              # Nested structure
        'ema_model': {...},          # Actual weights (with 'backbone.' prefix)
        'decay': 0.999,
        'updates': N,
    },
    'best_val_f1': 0.90+,
    'best_epoch': N,
    'args': Namespace(...),          # Training arguments
}
```

---

## 📁 Key Files Reference

### Must-Read Files (Attach These)
| File | Purpose | Lines |
|------|---------|-------|
| `training/multilabel/tune_thresholds.py` | Per-class threshold tuning | 536 |
| `training/multilabel/dataset.py` | BatchedMultiLabelDataset | ~800 |
| `transcription/multilabel_inference.py` | Inference module | 734 |
| `transcription/full_pipeline.py` | Full pipeline | 667 |
| `transcription/instrument_pitch_ranker.py` | Pitch ranking | 782 |

### Documentation
| File | Purpose |
|------|---------|
| `docs/CYMBAL_PITCH_RANKING.md` | Cymbal ranking details |
| `docs/TOM_PITCH_RANKING.md` | Tom ranking details |
| `docs/INSTRUMENT_PITCH_RANKING.md` | Pitch ranking overview |
| `NEXT_STEPS_POST_TRAINING.md` | Previous session notes |

### Model Files
| File | Size | Purpose |
|------|------|---------|
| `runs/v5_multilabel_final_v2/best_checkpoint.pt` | 114MB | Full training state |
| `runs/v5_multilabel_final_v2/best_multilabel_model.pt` | 86MB | Model only |
| `runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt` | 29MB | EMA model (best!) |
| `runs/v5_multilabel_final_v2/latest_checkpoint.pt` | 114MB | Latest checkpoint |

---

## ⚠️ Known Issues & Gotchas

### 1. Hi-Hat Confusion
`hihat_open` (0.806) and `hihat_pedal` (0.800) have lower F1 due to acoustic similarity.
- **Workaround:** Consider merging these classes or accepting the confusion
- **Not a bug:** This is an inherent limitation of acoustic classification

### 2. Threshold Sensitivity
Some classes (especially rare ones like china/splash) are very threshold-sensitive.
- **Solution:** Use per-class thresholds from Task 1

### 3. BatchedMultiLabelDataset vs CachedMultiLabelDataset
Old code uses `CachedMultiLabelDataset`. New training uses `BatchedMultiLabelDataset`.
- **Solution:** Update scripts to use the new dataset format

---

## ✅ Success Checklist

- [ ] **Thresholds:** `thresholds.json` generated with optimal per-class values
- [ ] **Pipeline Test:** Full pipeline runs on test audio without errors
- [ ] **Multi-label:** When kick+hihat hit together, both are detected
- [ ] **Pitch Ranking:** Multiple crashes get crash_1, crash_2 labels
- [ ] **Validation:** All 12 classes have F1 ≥ 0.80 with tuned thresholds
- [ ] **Export:** Production model saved to dedicated directory

---

## 💡 Tips for This Session

1. **Start with Task 1** (threshold tuning) - it improves all downstream tasks
2. **Use the EMA model** (`best_multilabel_model_ema.pt`) - it's smaller and better
3. **Test incrementally** - verify each component before moving to the next
4. **Create a simple threshold script** if `tune_thresholds.py` is too complex to update
5. **Document any fixes** - update this file or `NEXT_STEPS_POST_TRAINING.md`

---

## 📞 Quick Start Commands

```bash
# Navigate to ai-pipeline
cd c:/github/BeatSight/ai-pipeline

# Check training is still running (optional)
nvidia-smi

# Verify model files exist
ls -la runs/v5_multilabel_final_v2/

# Run threshold tuning (after updating script)
python training/multilabel/tune_thresholds.py \
    --model runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt \
    --output runs/v5_multilabel_final_v2/thresholds.json

# Test full pipeline (after Task 1 complete)
python transcription/full_pipeline.py \
    --model runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt \
    --thresholds runs/v5_multilabel_final_v2/thresholds.json \
    --audio path/to/test.wav
```

---

*Created: February 4, 2026*
*Previous Session: Training breakthrough to 0.90+ F1*
*Status: Training complete, ready for post-processing*
