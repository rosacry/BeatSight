# Post-Training Next Steps: Multi-Label Drum Classifier

> Status note (February 12, 2026): this document captures an earlier `multilabel_real_v2` planning pass.
> For the currently active `multilabel_real_v3` dual-model workflow, use
> `ai-pipeline/documentation/current/OPUS_HANDOFF_SESSION3_DUAL_MODEL_ENSEMBLE.md` and
> `ai-pipeline/documentation/current/CURRENT_AI_PIPELINE_STATE.md` as the source of truth.

## Current State (February 2, 2026)

### Training Status
- **Model**: CNN V5 Large (7.1M parameters)
- **Dataset**: 4.8M samples (EGMD 4.6M + Groove 225K) via `BatchedMultiLabelDataset`
- **Run directory**: `runs/v5_real_4.8M_cbfocal/`
- **Current best F1**: **0.9342** (epoch 8, still training to epoch 40)
- **Loss**: CB-Focal (β=0.99999, γ=2.0)

### Key Fix Applied This Session
**Problem**: Train/val split was done on unshuffled batches. EGMD batches are organized by recording source, causing severe distribution mismatch (train had 31% hihat_closed, val had 0.1%).

**Solution**: Added `shuffle_before_split=True` (now default) to `BatchedMultiLabelDataset` in `training/multilabel/dataset.py`. This shuffles batch indices before splitting, ensuring train and val have similar distributions.

### 12-Class Output Labels
```
china, crash, cross_stick, hihat_closed, hihat_open, hihat_pedal,
kick, ride_bell, ride_bow, snare, splash, tom
```

---

## Step 1: Threshold Optimization

**When**: After training completes (or now, using current best checkpoint)

**Script**: `tools/find_optimal_thresholds.py`

**Issue**: This script is hardcoded for the OLD dataset format (`CachedMultiLabelDataset` with `prod_v5_multilabel`). It needs to be updated for the new `BatchedMultiLabelDataset` format.

### Option A: Update `find_optimal_thresholds.py`

Replace the dataset loading section to use:
```python
from training.multilabel.dataset import BatchedMultiLabelDataset
from torch.utils.data import ConcatDataset

manifest_files = [
    'F:/datasets/multilabel_real_v2/egmd/egmd_manifest.json',
    'F:/datasets/multilabel_real_v2/groove/groove_midi/groove_manifest.json',
]

val_datasets = []
for manifest in manifest_files:
    val_ds = BatchedMultiLabelDataset(
        manifest_path=manifest,
        is_train=False,
        num_classes=12,
        shuffle_before_split=True,
        split_seed=42,
    )
    val_datasets.append(val_ds)

val_dataset = ConcatDataset(val_datasets)
```

Also update the model loading to handle EMA weights:
```python
ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)

# EMA weights are nested
if 'ema_state_dict' in ckpt:
    ema_state = ckpt['ema_state_dict']
    if isinstance(ema_state, dict) and 'ema_model' in ema_state:
        state_dict = ema_state['ema_model']
    else:
        state_dict = ema_state
else:
    state_dict = ckpt['model_state_dict']

# Strip 'backbone.' prefix
cleaned = {k.replace('backbone.', ''): v for k, v in state_dict.items()}
model.load_state_dict(cleaned, strict=False)
```

### Option B: Use `tools/diagnose_f1.py`

This script was updated during this session and already works with the new checkpoint format. It includes threshold analysis in its output.

### Expected Output
A JSON file with per-class thresholds:
```json
{
  "thresholds": {
    "china": 0.45,
    "crash": 0.50,
    "cross_stick": 0.50,
    "hihat_closed": 0.55,
    "hihat_open": 0.45,
    "hihat_pedal": 0.35,
    "kick": 0.35,
    "ride_bell": 0.45,
    "ride_bow": 0.50,
    "snare": 0.55,
    "splash": 0.45,
    "tom": 0.60
  }
}
```

---

## Step 2: Per-Class Evaluation

**Script**: `tools/evaluate_multilabel.py` or `tools/diagnose_model.py`

**Purpose**: Get detailed precision/recall/F1 per class to identify any remaining weaknesses.

**Note**: These scripts also need dataset loading updates (same as above).

---

## Step 3: Post-Processing Pipeline Integration

The full transcription pipeline is in `transcription/full_pipeline.py`:

```
Audio → Onset Detection → Multi-Label Classification → Count Estimation → Pitch Ranking → Final Events
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Onset Detection | `transcription/onset_detector.py` | Find drum hit times |
| Classification | `transcription/multilabel_inference.py` | 12-class multi-label detection |
| Count Estimation | `transcription/count_estimation.py` | Detect simultaneous same-class hits (2 crashes) |
| Pitch Ranking | `transcription/instrument_pitch_ranker.py` | Split cymbals/toms by pitch (crash_1, crash_2) |
| Choke Detection | `transcription/cymbal_choke_detector.py` | Detect choked cymbals |
| Rimshot Detection | `transcription/rimshot_detector.py` | Detect snare rimshots vs center hits |
| Post-Processing | `transcription/postprocessing.py` | Orchestrates all post-processors |

### Testing the Pipeline

```python
from transcription.full_pipeline import DrumTranscriptionPipeline, PipelineConfig

pipeline = DrumTranscriptionPipeline(
    multilabel_model_path="runs/v5_real_4.8M_cbfocal/best_checkpoint.pt",
    thresholds_path="runs/v5_real_4.8M_cbfocal/thresholds.json",  # after Step 1
)

result = pipeline.transcribe("path/to/song.wav")
for event in result.events[:20]:
    print(f"{event.time:.3f}s: {event.label} ({event.confidence:.2f})")
```

---

## Step 4: Pitch Ranking Validation

**Documentation**:
- `docs/CYMBAL_PITCH_RANKING.md`
- `docs/TOM_PITCH_RANKING.md`

**Implementation**: `transcription/instrument_pitch_ranker.py` (782 lines, complete)

### What It Does
- `crash` → `crash_1`, `crash_2`, `crash_3`, `crash_4` (ranked by pitch, high to low)
- `china` → `china_1`, `china_2`
- `splash` → `splash_1`, `splash_2`
- `ride_bow` → `ride_bow_1`, `ride_bow_2`
- `ride_bell` → `ride_bell_1`, `ride_bell_2`
- `tom` → `tom_1`, `tom_2`, `tom_3`, `tom_4` (ranked by pitch, high to low)

### Testing
```bash
python transcription/instrument_pitch_ranker.py \
    --audio path/to/test.wav \
    --events path/to/classifier_events.json \
    --output ranked_events.json
```

---

## Step 5: Final Integration Test

Run the complete pipeline on real audio files and verify:

1. **Onset detection accuracy** - Are all hits detected?
2. **Classification accuracy** - Are instruments correctly identified?
3. **Multi-label handling** - When kick+hihat hit together, are both detected?
4. **Pitch ranking** - Are multiple crashes/toms distinguished correctly?
5. **Count estimation** - When 2 crashes hit together, do we get 2 events?

---

## Files to Modify

### Priority 1: Update for new dataset format
1. `tools/find_optimal_thresholds.py` - Update dataset loading
2. `tools/evaluate_multilabel.py` - Update dataset loading
3. `tools/diagnose_model.py` - May already work, verify

### Priority 2: Verify working
1. `transcription/multilabel_inference.py` - Check EMA loading
2. `transcription/full_pipeline.py` - Integration test

### Already Fixed This Session
1. `training/multilabel/dataset.py` - Added `shuffle_before_split` for proper train/val split
2. `tools/diagnose_f1.py` - Fixed EMA weight loading

---

## Checkpoint Structure Reference

```python
checkpoint = {
    'epoch': 8,
    'model_state_dict': {...},       # Keys have 'backbone.' prefix
    'optimizer_state_dict': {...},
    'scheduler_state_dict': {...},
    'scaler_state_dict': {...},
    'ema_state_dict': {              # Nested structure
        'ema_model': {...},          # Actual weights (with 'backbone.' prefix)
        'decay': 0.999,
        'updates': 1000,
    },
    'best_val_f1': 0.9342,
    'best_epoch': 8,
    'args': Namespace(...),          # Training arguments
    'batch_idx': 34180,
    'total_batches': 34180,
    'rng': {...},
}
```

### Loading EMA Weights Correctly
```python
ckpt = torch.load(path, map_location='cpu', weights_only=False)

# Extract EMA weights
ema_state = ckpt['ema_state_dict']['ema_model']

# Strip 'backbone.' prefix for raw CNN model
state_dict = {k.replace('backbone.', ''): v for k, v in ema_state.items()}

model = cnn_v5_large(num_classes=12)
model.load_state_dict(state_dict, strict=False)
```

---

## Dataset Reference

### Current Dataset: `F:/datasets/multilabel_real_v2/`

```
multilabel_real_v2/
├── egmd/
│   ├── egmd_manifest.json        # 4,635,498 samples, 1444 batches
│   └── egmd_batches/
│       ├── features_batch_0.npy  # Shape: (N, 128, 128) mel specs
│       ├── labels_batch_0.npy    # Shape: (N, 12) multi-hot labels
│       └── ...
└── groove/
    └── groove_midi/
        ├── groove_manifest.json  # 225,296 samples, 113 batches
        └── groove_batches/
            └── ...
```

### Manifest Format
```json
{
  "dataset": "egmd",
  "total_samples": 4635498,
  "batch_count": 1444,
  "sample_rate": 22050,
  "feature_shape": [128, 128],
  "num_classes": 12,
  "batches": [
    {
      "features": "features_batch_0.npy",
      "labels": "labels_batch_0.npy",
      "samples": 10050,
      "multi_label_ratio": 0.344,
      "split": "train"
    },
    ...
  ]
}
```

### BatchedMultiLabelDataset Usage
```python
from training.multilabel.dataset import BatchedMultiLabelDataset

# Training set
train_ds = BatchedMultiLabelDataset(
    manifest_path='F:/datasets/multilabel_real_v2/egmd/egmd_manifest.json',
    is_train=True,
    num_classes=12,
    shuffle_before_split=True,  # IMPORTANT: now default
    split_seed=42,
)

# Validation set
val_ds = BatchedMultiLabelDataset(
    manifest_path='F:/datasets/multilabel_real_v2/egmd/egmd_manifest.json',
    is_train=False,
    num_classes=12,
    shuffle_before_split=True,
    split_seed=42,
)
```

---

## Summary Checklist

- [ ] Wait for training to complete (currently epoch 9/40, F1=0.9342)
- [ ] Update `find_optimal_thresholds.py` for new dataset format
- [ ] Run threshold optimization, save to `runs/v5_real_4.8M_cbfocal/thresholds.json`
- [ ] Run per-class evaluation to verify no weak classes
- [ ] Test `multilabel_inference.py` with the new checkpoint
- [ ] Test full pipeline on real audio
- [ ] Validate pitch ranking on audio with multiple cymbals/toms
- [ ] Export final model for production
