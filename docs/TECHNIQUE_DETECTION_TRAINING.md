# Technique Detection Training Guide

This guide explains how to train the drum classifier with technique detection heads.

## Overview

The v5 model now supports multi-label technique detection alongside instrument classification. This enables detection of:

### Core Techniques (8)
| Technique | Detection Method |
|-----------|-----------------|
| `flam` | Double transient pattern (grace + main) |
| `roll` | Sustained tremolo envelope |
| `buzz_roll` | Press roll with multiple bounces |
| `cymbal_choke` | Abrupt amplitude cutoff |
| `ghost_note` | Low velocity (< 0.25) |
| `accent` | High velocity (> 0.75) |
| `double_stroke` | Paired transients (RR/LL diddle) |
| `drag` | Multiple grace notes |

### Supporting Techniques (6)
| Technique | Detection Method |
|-----------|-----------------|
| `rimshot` | Instrument class (snare_rimshot) |
| `cross_stick` | Instrument class (snare_cross_stick) |
| `dead_stroke` | Short decay envelope |
| `mallet_hit` | Rounded transient attack |
| `brush_sweep` | Noise-like sustained sound |
| `crash_ride` | Riding on crash decay pattern |

## Preparation Steps

### 1. Generate Technique Labels

If your training data has velocity information:

```bash
python ai-pipeline/training/tools/generate_technique_labels.py \
    --input-labels E:/data/prod_combined_profile_run/train/index.json \
    --output-labels E:/data/prod_combined_profile_run/train/index_with_techniques.json \
    --technique-preset core \
    --has-velocity
```

For a dry run to see statistics:
```bash
python ai-pipeline/training/tools/generate_technique_labels.py \
    --input-labels E:/data/prod_combined_profile_run/train/index.json \
    --output-labels /dev/null \
    --technique-preset core \
    --dry-run
```

### 2. Synthesize Cymbal Choke Samples

Since cymbal chokes are rare in existing datasets, synthesize them:

```bash
python ai-pipeline/training/tools/synthesize_cymbal_chokes.py \
    --input-dir E:/data/raw/ENST-Drums \
    --output-dir E:/data/synthetic/cymbal_chokes \
    --num-variations 3
```

This applies DSP transforms to existing cymbal samples:
- Abrupt amplitude envelope cutoff
- Damping low-pass filter (hand touching cymbal)
- Optional muting noise burst

The script generates a `train_labels.json` in the output directory with proper technique annotations.

### 3. Use Synthetic Data

There are two approaches to include synthetic cymbal chokes:

**Option A: Separate Dataset Folder**
Place the synthetic chokes in their own data folder:
```
E:/data/synthetic/cymbal_chokes/
├── train_labels.json      # 375 samples with technique labels
├── choke_crash_0000_*.wav
├── choke_crash_0001_*.wav
└── ...
```

Then use multi-dataset training (if supported) or manually concatenate datasets.

**Option B: Merge into Main Dataset**
For large JSON files (>1GB), use streaming merge:
```bash
# 1. Create choke entries
python -c "
import json
from pathlib import Path
chokes = list(Path('E:/data/synthetic/cymbal_chokes').glob('*.wav'))
entries = [{'file': str(f), 'label': 'cymbal_choke', 'component_idx': 21, 
            'velocity': 0.7, 'techniques': ['cymbal_choke']} for f in chokes]
with open('/tmp/chokes.json', 'w') as f:
    for e in entries:
        f.write(', ' + json.dumps(e))
    f.write(']')
"

# 2. Stream merge
INPUT="E:/data/prod_combined_profile_run/train/train_labels_with_techniques.json"
OUTPUT="E:/data/prod_combined_profile_run/train/train_labels_merged.json"
head -c -1 "$INPUT" > "$OUTPUT" && cat /tmp/chokes.json >> "$OUTPUT"
```

**Option C: Use `--extra-labels` (RECOMMENDED)**
The training script now supports merging additional label sources at runtime:
```bash
python train_classifier.py \
    --dataset E:/data/prod_combined_profile_run \
    --extra-labels E:/data/synthetic/cymbal_chokes/train_labels.json \
    ...
```

This is the cleanest approach as it:
- Avoids modifying the main labels file
- Supports multiple extra sources: `--extra-labels file1.json file2.json`
- Automatically merges at dataset load time

## Training Commands

### Basic Training with Technique Heads

```bash
python ai-pipeline/training/train_classifier.py \
    --dataset E:/data/prod_combined_profile_run \
    --model-version v5 \
    --v5-size medium \
    --use-deep-supervision \
    --use-multi-task \
    --use-technique-heads \
    --technique-preset core \
    --technique-weight 0.2 \
    --extra-labels E:/data/synthetic/cymbal_chokes/train_labels.json \
    --epochs 100 \
    --batch-size 64
```

### Full V5 ULTIMATE Training

```bash
python ai-pipeline/training/train_classifier.py \
    --dataset E:/data/prod_combined_profile_run \
    --model-version v5 \
    --v5-size medium \
    --use-deep-supervision \
    --use-multi-task \
    --use-technique-heads \
    --technique-preset core \
    --technique-weight 0.2 \
    --velocity-weight 0.4 \
    --ghost-augment aggressive \
    --ghost-augment-prob 0.25 \
    --use-gradient-centralization \
    --optimizer adamw \
    --lr 1e-3 \
    --weight-decay 0.01 \
    --epochs 100 \
    --batch-size 64 \
    --amp \
    --num-workers 8
```

## Model Outputs

When using technique heads, the model returns 5 outputs:

```python
main, aux, vel, opn, tech = model(x, return_all=True)

# main: [B, 22] - Instrument class logits (22 classes with cymbal_choke)
# aux: List[[B, 22]] - Auxiliary deep supervision outputs
# vel: [B] - Velocity prediction (0-1)
# opn: [B] - Hi-hat openness prediction (0-1)
# tech: [B, 8] - Technique logits (8 core techniques)
```

### Inference

```python
from training.models.cnn_v5 import DrumClassifierCNNv5

model = DrumClassifierCNNv5(
    num_classes=22,
    use_multi_task=True,
    use_technique_heads=True,
    technique_preset="core",
)
model.load_state_dict(torch.load("checkpoint.pt")["model_state_dict"])
model.eval()

# Get predictions
with torch.no_grad():
    logits = model(mel_spec, return_all=False)  # Just classification
    
    # Or full multi-task output
    main, aux, vel, opn, tech = model(mel_spec, return_all=True)
    
    # Decode techniques
    tech_probs = torch.sigmoid(tech)
    detected = tech_probs > 0.5  # [B, 8] boolean
```

## Technique Presets

| Preset | Count | Techniques |
|--------|-------|------------|
| `core` | 8 | flam, roll, buzz_roll, cymbal_choke, ghost_note, accent, double_stroke, drag |
| `full` | 14 | core + rimshot, cross_stick, dead_stroke, mallet_hit, brush_sweep, crash_ride |
| `minimal` | 3 | ghost_note, accent, cymbal_choke |
| `articulation` | 5 | rimshot, cross_stick, dead_stroke, flam, drag |

## Loss Weights

Tune these based on your data distribution:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--technique-weight` | 0.2 | Weight for technique detection loss |
| `--velocity-weight` | 0.4 | Weight for velocity prediction loss |
| `--openness-weight` | 0.1 | Weight for hi-hat openness loss |

## Expected Results

With proper technique labels and training:

| Technique | Expected F1 |
|-----------|-------------|
| ghost_note | 0.75-0.85 |
| accent | 0.80-0.90 |
| rimshot | 0.85-0.95 |
| cross_stick | 0.85-0.95 |
| flam | 0.60-0.75 |
| roll | 0.65-0.80 |
| cymbal_choke | 0.55-0.70 |

Note: cymbal_choke accuracy depends heavily on synthetic sample quality.

## Troubleshooting

### "TechniqueHeads not available"
Ensure `technique_heads.py` is in `training/models/`:
```bash
ls ai-pipeline/training/models/technique_heads.py
```

### Low technique detection accuracy
1. Check technique label distribution with `--dry-run`
2. Increase `--technique-weight` to 0.3-0.5
3. Use `--technique-preset minimal` first, then expand

### Out of memory
Technique heads add ~100K parameters. Reduce batch size:
```bash
--batch-size 32
```

## Architecture

```
Input Mel-Spectrogram [B, 1, 128, 128]
         │
    ┌────▼────┐
    │  Stem   │
    └────┬────┘
         │
    ┌────▼────┐
    │ Stage 1 │───► Aux Head 1 (if deep_sup)
    └────┬────┘
         │
    ┌────▼────┐
    │ Stage 2 │───► Aux Head 2 (if deep_sup)
    └────┬────┘
         │
    ┌────▼────┐
    │ Stage 3 │
    └────┬────┘
         │
    ┌────▼────┐
    │ Stage 4 │
    └────┬────┘
         │
    ┌────▼────┐
    │  Pool   │ Feature Vector [B, 256]
    └────┬────┘
         │
    ┌────┼────┬────┬────┐
    ▼    ▼    ▼    ▼    ▼
 Class  Vel  Open Tech Head
  [22]  [1]  [1]   [8]
```
