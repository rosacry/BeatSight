# AI Training System

This directory contains tools for training and improving the drum classification model.

## Overview

The training system consists of three main components:

1. **Data Collection** (`collect_training_data.py`) - Collect and label drum samples
2. **ML Classifier** (`../transcription/ml_drum_classifier.py`) - PyTorch CNN model
3. **Training Script** (`train_classifier.py`) - Train the model

## Quick Start

### 1. Collect Training Data

```bash
# Add a single sample
python collect_training_data.py --add-sample audio.mp3 1.234 kick

# Extract from a beatmap (best method!)
python collect_training_data.py --extract-beatmap beatmap.bsm audio.mp3

# Check statistics
python collect_training_data.py --stats

# Export dataset for training
python collect_training_data.py --export dataset
```

### 2. Train the Model

```bash
# Train with default settings
python train_classifier.py --dataset ./dataset --epochs 50

# Train with GPU
python train_classifier.py --dataset ./dataset --epochs 100 --batch-size 64 --device cuda

# Custom learning rate
python train_classifier.py --dataset ./dataset --lr 0.0001 --epochs 75
```

### 3. Use the Trained Model

1. Copy the generated `best_drum_classifier.pth` into `ai-pipeline/models/`.
2. Run the processor; it will automatically pick up the model when present, or specify it explicitly:
   ```bash
   python -m pipeline.process --input song.mp3 --output beatmap.bsm \
       --ml-model models/best_drum_classifier.pth
   ```
3. Environment variables offer further control:
   - `BEATSIGHT_ML_MODEL_PATH` – custom absolute/relative path to the `.pth`
   - `BEATSIGHT_USE_ML_CLASSIFIER=0` – disable ML and fall back to heuristics

## Data Collection Tips

### From Beatmaps
The easiest way to collect data is to use existing beatmaps:

```bash
# Process multiple beatmaps
for file in ../shared/formats/*.bsm; do
    python collect_training_data.py --extract-beatmap "$file" "${file%.bsm}.mp3"
done
```

### Manual Labeling
For precise labeling:

1. Open audio file in Audacity or similar
2. Find drum hit timestamps
3. Add each sample:
   ```bash
   python collect_training_data.py --add-sample audio.mp3 <time> <component>
   ```

### Recommended Data Distribution

For best results, aim for:
- Minimum 100 samples per component
- Balanced distribution across all components
- Variety of sources (different drummers, songs, recording styles)

| Component | Minimum Samples | Recommended |
|-----------|----------------|-------------|
| kick | 100 | 500+ |
| snare | 100 | 500+ |
| hihat_closed | 150 | 750+ |
| hihat_open | 50 | 250+ |
| crash | 75 | 300+ |
| ride | 75 | 300+ |
| tom_high | 50 | 200+ |
| tom_mid | 50 | 200+ |
| tom_low | 50 | 200+ |

## Model Architecture

```
DrumClassifierCNN
├── Conv2D(1→32) + BatchNorm + ReLU + MaxPool
├── Conv2D(32→64) + BatchNorm + ReLU + MaxPool
├── Conv2D(64→128) + BatchNorm + ReLU + MaxPool
├── Conv2D(128→256) + BatchNorm + ReLU + AdaptiveAvgPool
├── Flatten
├── Dropout(0.3)
└── Linear(256→12)

Total Parameters: ~840K
Input: 128x128 mel-spectrogram
Output: 12-class probability distribution
```

## Training Tips

### Hyperparameters

| Parameter | Default | Recommended Range | Notes |
|-----------|---------|-------------------|-------|
| Epochs | 50 | 30-100 | Monitor validation loss |
| Batch Size | 32 | 16-64 | Depends on GPU memory |
| Learning Rate | 0.001 | 0.0001-0.01 | Use scheduler |
| Dropout | 0.3 | 0.2-0.5 | Prevent overfitting |

### Preventing Overfitting

- Use data augmentation (time stretching, pitch shifting)
- Increase dropout rate
- Add more training data
- Use early stopping

### GPU Acceleration

Training on GPU is 10-50x faster:

```bash
# Check if CUDA is available
python -c "import torch; print(torch.cuda.is_available())"

# Train with GPU
python train_classifier.py --dataset ./dataset --device cuda --batch-size 64
```

## Advanced Usage

### Data Augmentation

Add augmentation to `DrumSampleDataset.__getitem__()`:

```python
# Time stretching
if random.random() > 0.5:
    audio = librosa.effects.time_stretch(audio, rate=random.uniform(0.9, 1.1))

# Pitch shifting
if random.random() > 0.5:
    audio = librosa.effects.pitch_shift(audio, sr=self.sr, n_steps=random.randint(-2, 2))

# Add noise
if random.random() > 0.5:
    noise = np.random.randn(len(audio)) * 0.005
    audio = audio + noise
```

### Transfer Learning

Start from a pre-trained model:

```python
model = DrumClassifierCNN(num_classes=12)
model.load_state_dict(torch.load("pretrained_model.pth"), strict=False)
```

### Fine-tuning

Freeze early layers and train only the final layers:

```python
# Freeze conv layers
for param in model.conv1.parameters():
    param.requires_grad = False
for param in model.conv2.parameters():
    param.requires_grad = False

# Train only later layers
optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=0.0001)
```

## Evaluation

### Per-class Accuracy

Add to validation function:

```python
from sklearn.metrics import classification_report

# After validation
print(classification_report(all_labels, all_predictions, target_names=component_names))
```

### Confusion Matrix

```python
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

cm = confusion_matrix(all_labels, all_predictions)
plt.figure(figsize=(12, 10))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=component_names, yticklabels=component_names)
plt.xlabel('Predicted')
plt.ylabel('True')
plt.title('Drum Classifier Confusion Matrix')
plt.savefig('confusion_matrix.png')
```

## Distributed Training (Future)

For community-driven model training:

1. Contributors run training client
2. Central server aggregates gradients
3. Improved model distributed to all

See `ROADMAP.md` Phase 4 for details.

## Troubleshooting

### Low Accuracy
- Check data distribution (balanced?)
- Increase training data
- Add data augmentation
- Tune hyperparameters

### Overfitting
- Validation accuracy much lower than training?
- Increase dropout
- Add L2 regularization
- Reduce model complexity

### Out of Memory
- Reduce batch size
- Use mixed precision training
- Reduce input size

## References

- [Drum transcription survey](https://arxiv.org/abs/1806.06676)
- [ENST-Drums database](http://www.telecom-paristech.fr/~grichard/ENST-drums/)
- [PyTorch audio tutorial](https://pytorch.org/audio/stable/tutorials/audio_classification_tutorial.html)

## Contributing

See `docs/CONTRIBUTING.md` for guidelines on contributing training data and model improvements.
