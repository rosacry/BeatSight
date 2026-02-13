# Multi-Label Drum Classification

> **Status:** Ready for implementation  
> **Prerequisite:** Single-label model complete (94.55% balanced accuracy)  
> **Goal:** Detect multiple simultaneous drum hits in one audio window

This module enables training drum classifiers that can detect **multiple simultaneous drum hits** (e.g., kick + hi-hat on beat 1, snare + crash on beat 2).

---

## Why Multi-Label?

The single-label classifier uses `CrossEntropyLoss` with softmax, forcing exactly ONE prediction per audio window. This fails for common drum patterns:

| Pattern | Single-Label | Multi-Label |
|---------|--------------|-------------|
| Kick + Hi-hat | Predicts one (usually kick) | Predicts both ✓ |
| Snare + Crash | Predicts one | Predicts both ✓ |
| Kick + Snare + Hi-hat | Misses 2 drums | Predicts all 3 ✓ |

---

## Architecture: Multi-Label + Post-Processing

### What the ML Model Does (Binary Multi-Label)
The multi-label classifier outputs **binary presence** per class:
```
[china=0, crash=1, cross_stick=0, hihat_closed=1, kick=1, ...]
```
This means "crash, hi-hat, and kick are present" but does NOT specify:
- **Count**: Is it 1 crash or 2 crashes hit together?
- **Pitch**: Is it a high crash or low crash?

### What Post-Processing Does
Two stages of refinement happen AFTER classification:

1. **Count Estimation** (NEW - for multi-label)
   - When `crash=1`, analyze the audio window to detect if it's 1 or 2 crashes
   - Use stereo spread (left crash vs right crash)
   - Use spectral analysis (distinct frequency peaks)
   - Use transient detection (multiple attack transients)

2. **Pitch Ranking** (EXISTING)
   - Already implemented for crashes, toms, chinas, splashes
   - Assigns high/mid/low based on spectral content relative to the song
   - See `transcription/pitch_ranking.py`

### Why This Design?

The pitch of "high crash" varies per song - what's high in one kit is low in another. Similarly, detecting *how many* crashes requires song-specific audio analysis, not learned features. Keeping the ML model as simple binary classification:
- Easier to train (binary labels)
- More generalizable (doesn't overfit to specific kits)
- Leverages deterministic audio analysis for the nuanced parts

---

## Key Differences from Single-Label

| Aspect | Single-Label | Multi-Label |
|--------|--------------|-------------|
| Loss Function | CrossEntropyLoss | BCEWithLogitsLoss |
| Output Activation | Softmax (sums to 1) | Sigmoid (independent per class) |
| Label Format | Integer class index | Multi-hot vector [0,1,0,1,0,...] |
| Metrics | Accuracy, Top-1 | Hamming loss, Subset accuracy, F1 |
| Classes | 12 | 12 (same structure) |

---

## 12-Class Structure (Same as Single-Label)

| Index | Class | Description |
|-------|-------|-------------|
| 0 | china | China cymbal |
| 1 | crash | Crash cymbal |
| 2 | cross_stick | Cross-stick (side stick) |
| 3 | hihat_closed | Closed hi-hat |
| 4 | hihat_open | Open hi-hat |
| 5 | hihat_pedal | Hi-hat pedal (foot) |
| 6 | kick | Kick drum |
| 7 | ride_bell | Ride bell |
| 8 | ride_bow | Ride bow |
| 9 | snare | Snare drum |
| 10 | splash | Splash cymbal |
| 11 | tom | Tom (all toms merged) |

---

## Usage

### 0. Discover Available Multi-Label Sources (Run First!)

Before generating synthetic data, check what real multi-label data you have:

```bash
# Scan drives for known multi-label datasets
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/multilabel/discover_multilabel_sources.py \
    --drives "D:/" "F:/" \
    --output multilabel_sources.json
```

**Known multi-label sources (with MIDI + audio pairs):**
- **E-GMD** (D:/data/raw/egmd) - 25K+ MIDI files from 10 drummers with audio
- **Groove MIDI** (D:/data/raw/groove_midi) - Professional drummer recordings
- **ENST-Drums** (D:/data/raw/ENST-Drums) - Isolated tracks + annotations
- **Slakh2100** (D:/data/raw/slakh2100) - Synthesized multi-track with MIDI

### 1. Extract Real Multi-Label Data from MIDI

The best multi-label data comes from MIDI files that have precise timing of all drum hits:

```bash
# First, install dependencies
pip install mido pretty_midi

# Analyze what's available
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/multilabel/extract_multilabel_from_midi.py \
    --sources egmd groove_midi \
    --mode analyze

# Extract multi-label training data
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/multilabel/extract_multilabel_from_midi.py \
    --sources egmd groove_midi \
    --output "F:/datasets/multilabel_real" \
    --feature-cache-dir "F:/feature_cache" \
    --mode extract
```

### 2. Analyze Single-Label Dataset

Analyze the source dataset distribution to understand class balance:
```bash
python training/multilabel/generate_multilabel_dataset.py \
    --input "F:/datasets/prod_v5_final" \
    --mode analyze
```

### 3. Generate Synthetic Multi-Label Dataset

**Option A: Synthetic Multi-Label (Combines real with synthetic)**

Generates multi-label training data by combining single-label samples according to realistic drum patterns (kick+hi-hat, snare+crash, etc.):
```bash
python training/multilabel/generate_multilabel_dataset.py \
    --input "F:/datasets/prod_v5_final" \
    --output "F:/datasets/prod_v5_multilabel" \
    --feature-cache-dir "F:/feature_cache" \
    --mode synthetic \
    --num-samples 5000000
```

### 4. Combine Real + Synthetic Data (Recommended Workflow)

The ideal training set combines:
1. **Real multi-label data** from MIDI datasets (authentic simultaneous hits)
2. **Synthetic multi-label data** from single-label blending (augmentation)

```bash
# After extracting real data and generating synthetic data:
# Merge them into a single training set
# (Use standard tools like np.concatenate on the .npy files)
```

**Option B: Merge nearby onsets (30ms window)**
```bash
python training/multilabel/convert_to_multilabel.py \
    --input "F:/datasets/prod_v5_final" \
    --output "F:/datasets/prod_v5_final_multilabel" \
    --merge-threshold 0.03
```

### 5. Train Multi-Label Model

**Phase 1: Initial training with SAM optimizer (recommended):**
```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/multilabel/train_multilabel.py \
  --train-dir "F:/datasets/prod_v5_multilabel/train" \
  --val-dir "F:/datasets/prod_v5_multilabel/val" \
  --source-dataset "F:/datasets/prod_v5_final" \
  --feature-cache-dir "F:/feature_cache" \
  --pretrained runs/v5_phase2/checkpoints/best_checkpoint.pth \
  --model-version v5 --v5-size large \
  --epochs 60 --batch-size 128 --grad-accum-steps 5 \
  --lr 1e-4 --amp-dtype bfloat16 \
  --loss-type focal --gamma 2.0 \
  --specaugment drum --use-sam --sam-adaptive \
  --scheduler cosine --warmup-epochs 3 \
  --gradient-checkpointing --grad-clip-norm 1.0 \
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \
  --checkpoint-every 1 --checkpoint-every-batches 5000 \
  --channels-last --output-dir runs/multilabel_v1
```

**Phase 2: Fine-tuning with EMA and SWA:**
```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/multilabel/train_multilabel.py \
  --train-dir "F:/datasets/prod_v5_multilabel/train" \
  --val-dir "F:/datasets/prod_v5_multilabel/val" \
  --source-dataset "F:/datasets/prod_v5_final" \
  --feature-cache-dir "F:/feature_cache" \
  --model-version v5 --v5-size large \
  --epochs 84 --batch-size 128 --grad-accum-steps 5 \
  --lr 1e-5 \
  --amp-dtype bfloat16 \
  --loss-type focal --gamma 2.0 \
  --specaugment drum \
  --label-smoothing 0.1 \
  --use-swa --swa-start 0.5 \
  --use-ema --ema-decay 0.999 \
  --scheduler cosine --warmup-epochs 1 \
  --gradient-checkpointing --grad-clip-norm 1.0 \
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \
  --checkpoint-every 1 --checkpoint-every-batches 5000 \
  --channels-last \
  --output-dir runs/multilabel_v1 \
  --resume runs/multilabel_v1/latest_checkpoint.pt \
  --reset-scheduler
```

**Simple training (fewer options):**
```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/multilabel/train_multilabel.py \
  --train-dir "F:/datasets/prod_v5_multilabel/train" \
  --val-dir "F:/datasets/prod_v5_multilabel/val" \
  --source-dataset "F:/datasets/prod_v5_final" \
  --feature-cache-dir "F:/feature_cache" \
  --pretrained runs/v5_phase2/checkpoints/best_checkpoint.pth \
  --model-version v5 --v5-size large \
  --epochs 50 --batch-size 128 \
  --lr 1e-5 --amp-dtype bfloat16 \
  --output-dir runs/multilabel_v1
```

### 6. Use Multi-Label Model for Inference

```python
import torch
from training.models.cnn_v5 import DrumClassifierCNNv5

# Load model (same architecture, different final layer)
model = DrumClassifierCNNv5(num_classes=12, size="large")
checkpoint = torch.load("best_multilabel_model.pth")
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

# Predict
with torch.no_grad():
    logits = model(mel_spec)  # Shape: (B, 12)
    probs = torch.sigmoid(logits)  # Independent probabilities

# Get active drums (above threshold)
threshold = 0.5
active_classes = (probs > threshold).nonzero()
CLASS_NAMES = ["china", "crash", "cross_stick", "hihat_closed", "hihat_open", 
               "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom"]

for batch_idx, class_idx in active_classes:
    print(f"Detected: {CLASS_NAMES[class_idx]} ({probs[batch_idx, class_idx]:.1%})")
```

---

## Module Structure

```
multilabel/
├── __init__.py                   # Package exports
├── dataset.py                    # MultiLabelDrumDataset & CachedMultiLabelDataset
├── loss.py                       # BCEWithLogitsLoss, FocalBCELoss, AsymmetricLoss
├── metrics.py                    # Hamming loss, subset accuracy, per-class F1
├── train_multilabel.py           # Training script
├── convert_to_multilabel.py      # Dataset conversion (onset merging)
├── generate_multilabel_dataset.py # Synthetic multi-label generation
└── README.md                     # This file
```

---

## Label Format

### Single-Label (Current)
```json
{"audio_path": "audio/s1.wav", "component_idx": 9}
```

### Multi-Label (New)
```json
{
  "audio_path": "audio/s1.wav",
  "components": [
    {"label": "kick", "idx": 6},
    {"label": "hihat_closed", "idx": 3}
  ]
}
```

Or as multi-hot vector:
```json
{
  "audio_path": "audio/s1.wav",
  "labels": [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0]
}
```

---

## Loss Functions

### BCEWithLogitsLoss (Default)
Standard binary cross-entropy. Good baseline for balanced datasets.

### FocalBCELoss (Recommended)
Focal loss down-weights easy examples and focuses on hard ones. Helps when some drum combinations are rare.

```
Loss = -α * (1-p)^γ * log(p)  for positives
     = -(1-α) * p^γ * log(1-p)  for negatives
```

Recommended settings:
- `gamma=2.0` for severe imbalance
- `alpha=0.25` for positive samples

### AsymmetricLoss
Different focusing for positives vs negatives. Useful when false negatives (missing a hit) are worse than false positives (extra hit).

---

## Metrics

| Metric | Description | Range |
|--------|-------------|-------|
| **Hamming Loss** | Fraction of incorrect labels | [0, 1] (lower is better) |
| **Subset Accuracy** | Exact match (all labels correct) | [0, 1] (higher is better) |
| **Micro F1** | F1 aggregated across all labels | [0, 1] (higher is better) |
| **Macro F1** | Average F1 per class | [0, 1] (higher is better) |
| **Per-Class F1** | F1 for each drum class | [0, 1] per class |

### Expected Performance

| Metric | Single-Label | Multi-Label (Est.) |
|--------|--------------|---------------------|
| Single-drum accuracy | 94.55% | ~93% |
| Multi-drum detection | ~50% | 75-85% |
| Overall Micro F1 | ~92% | ~88-92% |
| Subset accuracy | N/A | ~60-70% |

---

## Tips

### Class Imbalance
Use `--use-pos-weight` to weight rare combinations higher:
```bash
python train_multilabel.py --dataset ./data --use-pos-weight
```

### Threshold Tuning
Default threshold is 0.5, but optimal thresholds vary per class:
```bash
python train_multilabel.py --dataset ./data --tune-thresholds
```

### Transfer Learning
Starting from single-label checkpoint is strongly recommended:
- Converges faster (features already learned)
- Better final accuracy
- Only needs to learn multi-label relationships

---

## TODO for Implementation

### Multi-Label Training
1. [x] Update `dataset.py` with 12-class mapping and CachedMultiLabelDataset
2. [x] Update `convert_to_multilabel.py` to use 12-class mapping
3. [x] Create `generate_multilabel_dataset.py` for synthetic multi-label generation
4. [x] Update `train_multilabel.py` with proper defaults and source dataset support
5. [ ] Generate full multi-label dataset (5M+ samples)
6. [ ] Train multi-label model from single-label checkpoint
7. [ ] Tune per-class thresholds
8. [ ] Evaluate on held-out multi-label test set

### Count Estimation Post-Processing
7. [ ] Create `transcription/count_estimation.py` module
8. [ ] Implement stereo spread analysis (left/right panning detection)
9. [ ] Implement spectral peak counting (multiple fundamentals)
10. [ ] Implement transient detection (multiple attacks in window)
11. [ ] Integrate with existing pitch ranking pipeline
12. [ ] Test on songs with known double-crash/double-tom hits

### Production Integration
13. [ ] Update transcription pipeline to use multi-label model
14. [ ] Chain: ML prediction → count estimation → pitch ranking
15. [ ] Handle variable number of predictions per window

---

## Known Limitation: Same-Class Multiplicity

The multi-label model outputs **binary** presence (class present or not), NOT counts.

| Scenario | Model Output | Count Estimation Needed |
|----------|--------------|------------------------|
| 1 crash | `crash=1` | Detect 1 crash |
| 2 crashes together | `crash=1` | Detect 2 crashes |
| 3 toms together | `tom=1` | Detect 3 toms |

**Solution**: Post-processing analyzes the audio when a class is detected:
- **Stereo spread**: Left crash + right crash = 2 crashes
- **Spectral peaks**: Multiple distinct fundamentals = multiple toms
- **Transient count**: Multiple attack transients in window = multiple hits

This keeps ML simple (binary) while deterministic audio analysis handles counting.

---

*Last updated: January 2026*
