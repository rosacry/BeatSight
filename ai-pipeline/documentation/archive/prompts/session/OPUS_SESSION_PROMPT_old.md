# Opus Session Prompt: Post-Training Pipeline Integration

## Context

I'm currently training a 12-class multi-label drum classifier that achieved **F1 = 0.9342** (and likely higher by now). The model is in `runs/v5_real_4.8M_cbfocal/best_checkpoint.pt`. I'm still training it but i would like for you to assume that i've completed it since it's likely a good enough model to go forward with. (but when i finish training completely i'll run the exact same things i did for the current best checkpoint you'll be working with)

This session fixed a critical bug: the train/val split was done on unshuffled batches, causing severe distribution mismatch. The fix is in `training/multilabel/dataset.py` with `shuffle_before_split=True`.

## Your Tasks

### 1. Threshold Optimization
Update `tools/find_optimal_thresholds.py` to work with the new `BatchedMultiLabelDataset` format, then run it to find optimal per-class thresholds. Save results to `runs/v5_real_4.8M_cbfocal/thresholds.json`.

Key changes needed:
- Replace `CachedMultiLabelDataset` with `BatchedMultiLabelDataset`
- Load from manifests at `F:/datasets/multilabel_real_v2/*/manifest.json`
- Handle EMA weights properly (nested in `ema_state_dict['ema_model']`, with `backbone.` prefix)

### 2. Per-Class Evaluation
Run evaluation to get precision/recall/F1 for each of the 12 classes. Identify any weak classes.

### 3. Pipeline Integration Test
Test the full transcription pipeline (`transcription/full_pipeline.py`) with:
- The trained model
- Per-class thresholds from step 1
- Real audio input

Verify:
- Multi-label detection works (kick + hihat detected together)
- Pitch ranking works (`transcription/instrument_pitch_ranker.py`)
- Output format is correct

### 4. Fix Any Issues
If any component fails or has bugs, fix them.

## Key Technical Details

### EMA Weight Loading
```python
ckpt = torch.load(path, weights_only=False)
ema_state = ckpt['ema_state_dict']['ema_model']  # Nested!
state_dict = {k.replace('backbone.', ''): v for k, v in ema_state.items()}
model.load_state_dict(state_dict, strict=False)
```

### Dataset Loading (New Format)
```python
from training.multilabel.dataset import BatchedMultiLabelDataset
val_ds = BatchedMultiLabelDataset(
    manifest_path='F:/datasets/multilabel_real_v2/egmd/egmd_manifest.json',
    is_train=False,
    num_classes=12,
    shuffle_before_split=True,
    split_seed=42,
)
```

### 12 Classes (in order)
```
china, crash, cross_stick, hihat_closed, hihat_open, hihat_pedal,
kick, ride_bell, ride_bow, snare, splash, tom
```

## Reference Documentation
- `docs/CYMBAL_PITCH_RANKING.md` - How cymbal pitch ranking works
- `docs/TOM_PITCH_RANKING.md` - How tom pitch ranking works  
- `NEXT_STEPS_POST_TRAINING.md` - Detailed technical reference (created this session)

## Success Criteria
1. `thresholds.json` generated with optimal per-class thresholds
2. Per-class F1 scores printed, no class below 0.85
3. Full pipeline runs on a test audio file
4. Pitch ranking correctly distinguishes multiple cymbals/toms

---

## Files to Attach as Context

**Required (open these in VS Code before starting):**
1. `ai-pipeline/documentation/archive/handoffs/NEXT_STEPS_POST_TRAINING.md` - Complete technical reference
2. `ai-pipeline/tools/find_optimal_thresholds.py` - Needs updating
3. `ai-pipeline/training/multilabel/dataset.py` - Reference for BatchedMultiLabelDataset
4. `ai-pipeline/transcription/multilabel_inference.py` - Inference code
5. `ai-pipeline/transcription/full_pipeline.py` - Pipeline to test

**Optional (for reference):**
- `ai-pipeline/tools/diagnose_f1.py` - Working example of correct weight loading
- `ai-pipeline/transcription/instrument_pitch_ranker.py` - Pitch ranking implementation
- `docs/CYMBAL_PITCH_RANKING.md`
- `docs/TOM_PITCH_RANKING.md`
