# Multi-Label Drum Classification

This module enables training drum classifiers that can detect **multiple simultaneous drum hits** (e.g., kick + hi-hat on beat 1, snare + crash on beat 2).

## Why Multi-Label?

The original single-label classifier uses `CrossEntropyLoss` with softmax, which forces the model to predict exactly ONE drum class per audio window. This fails for common drum patterns:

| Pattern | Single-Label | Multi-Label |
|---------|--------------|-------------|
| Kick + Hi-hat | Predicts one (usually kick) | Predicts both ✓ |
| Snare + Crash | Predicts one | Predicts both ✓ |
| Kick + Snare + Hi-hat | Misses 2 drums | Predicts all 3 ✓ |

## Key Differences

| Aspect | Single-Label | Multi-Label |
|--------|--------------|-------------|
| Loss Function | CrossEntropyLoss | BCEWithLogitsLoss |
| Output Activation | Softmax (sums to 1) | Sigmoid (independent per class) |
| Label Format | Integer class index | Multi-hot vector [0,1,0,1,0,...] |
| Metrics | Accuracy, Top-1 | Hamming loss, Subset accuracy, F1 |

## Usage

### 1. Convert Existing Dataset

```bash
# Convert labels.json to multi-label format
python multilabel/convert_to_multilabel.py \
    --input dataset/labels.json \
    --output dataset/labels_multilabel.json

# Optionally merge nearby onsets (within 30ms)
python multilabel/convert_to_multilabel.py \
    --input dataset/labels.json \
    --output dataset/labels_merged.json \
    --merge-threshold 0.03
```

### 2. Train Multi-Label Model

```bash
# Basic training
python multilabel/train_multilabel.py \
    --dataset ./dataset \
    --labels-file labels_multilabel.json \
    --epochs 50

# With focal loss for better handling of rare classes
python multilabel/train_multilabel.py \
    --dataset ./dataset \
    --loss-type focal \
    --gamma 2.0 \
    --use-pos-weight

# Resume from single-label checkpoint
python multilabel/train_multilabel.py \
    --dataset ./dataset \
    --pretrained-checkpoint checkpoints/best_model.pt
```

### 3. Use Multi-Label Model

```python
from multilabel import MultiLabelDrumDataset
from multilabel.train_multilabel import MultiLabelDrumClassifier, create_model

# Load model
model = create_model(model_version="v4", num_classes=21)
checkpoint = torch.load("best_multilabel_model.pt")
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

# Predict
mel_spec = extract_mel_spectrogram(audio)  # Shape: (1, 1, 128, 128)
probs = model.predict_proba(mel_spec)       # Shape: (1, 21)

# Get active drums (above threshold)
threshold = 0.5
active_classes = (probs > threshold).nonzero()
for batch_idx, class_idx in active_classes:
    print(f"Detected: {CLASS_NAMES[class_idx]} ({probs[batch_idx, class_idx]:.1%})")
```

## Module Structure

```
multilabel/
├── __init__.py          # Package exports
├── dataset.py           # MultiLabelDrumDataset class
├── loss.py              # BCEWithLogitsLoss, FocalBCELoss, AsymmetricLoss
├── metrics.py           # Hamming loss, subset accuracy, per-class F1
├── train_multilabel.py  # Training script
├── convert_to_multilabel.py  # Dataset conversion script
└── README.md            # This file
```

## Label Format

### Single-Label (Old)
```json
{"file": "audio/s1.wav", "component_idx": 9}
```

### Multi-Label (New)
```json
{
  "audio_path": "audio/s1.wav",
  "components": [
    {"label": "kick", "velocity": 0.85},
    {"label": "hihat_closed", "velocity": 0.65}
  ]
}
```

## Loss Functions

### BCEWithLogitsLoss (Default)
Standard binary cross-entropy. Good baseline.

### FocalBCELoss (Recommended)
Focal loss down-weights easy examples and focuses on hard ones. Helps with class imbalance (kick/snare are common, china/splash are rare).

```
Loss = -α * (1-p)^γ * log(p)  for positives
     = -(1-α) * p^γ * log(1-p)  for negatives
```

Recommended: `gamma=2.0` for severe imbalance.

### AsymmetricLoss
Different focusing for positives vs negatives. Useful when false negatives (missing a hit) are worse than false positives (extra hit).

## Metrics

| Metric | Description | Range |
|--------|-------------|-------|
| Hamming Loss | Fraction of incorrect labels | [0, 1] (lower is better) |
| Subset Accuracy | Exact match (all labels correct) | [0, 1] (higher is better) |
| Micro F1 | F1 aggregated across all labels | [0, 1] (higher is better) |
| Macro F1 | Average F1 per class | [0, 1] (higher is better) |
| Per-Class F1 | F1 for each drum class | [0, 1] per class |

## Tips

### Class Imbalance
Use `--use-pos-weight` to weight rare classes higher:
```bash
python train_multilabel.py --dataset ./data --use-pos-weight
```

### Optimal Thresholds
The training script automatically finds optimal thresholds:
- Global threshold (single value for all classes)
- Per-class thresholds (different threshold per drum)

Thresholds are saved to `optimal_thresholds.json`.

### Merging Nearby Onsets
If your dataset has separate entries for simultaneous hits, merge them:
```bash
python convert_to_multilabel.py --merge-threshold 0.03  # 30ms window
```

## Expected Performance

| Metric | Single-Label | Multi-Label |
|--------|--------------|-------------|
| Single-drum accuracy | ~85% | ~85% |
| Multi-drum detection | ~50% (misses 1+ drums) | ~75-80% |
| Overall F1 | ~82% | ~85-88% |

The main improvement is for samples with simultaneous hits, which are common in real drumming.
