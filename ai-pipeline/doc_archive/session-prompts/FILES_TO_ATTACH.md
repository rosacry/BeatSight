# Files to Attach for Post-Training Session

## 📎 Essential Files (Must Attach)

Open these files in VS Code tabs before starting the Claude session:

### Core Scripts
1. **`ai-pipeline/OPUS_POST_TRAINING_PROMPT.md`** ← THE MAIN PROMPT
2. **`ai-pipeline/training/multilabel/tune_thresholds.py`** - Needs updating for threshold tuning
3. **`ai-pipeline/training/multilabel/dataset.py`** - BatchedMultiLabelDataset reference
4. **`ai-pipeline/transcription/multilabel_inference.py`** - Inference module
5. **`ai-pipeline/transcription/full_pipeline.py`** - Pipeline to test

### Documentation
6. **`ai-pipeline/NEXT_STEPS_POST_TRAINING.md`** - Previous session context

## 📎 Optional (For Deep Dives)

### Pitch Ranking
- `ai-pipeline/transcription/instrument_pitch_ranker.py` - Full implementation
- `docs/CYMBAL_PITCH_RANKING.md` - Cymbal ranking docs
- `docs/TOM_PITCH_RANKING.md` - Tom ranking docs

### Model Architecture
- `ai-pipeline/models/cnn_v5.py` - Model definition
- `ai-pipeline/training/multilabel/train_multilabel.py` - Training script

### Metrics & Evaluation
- `ai-pipeline/training/multilabel/metrics.py` - Metric functions
- `ai-pipeline/tools/diagnose_f1.py` - Working example of correct weight loading

## 🎯 How to Start the Session

1. **Open VS Code** in `c:\github\BeatSight`

2. **Open Essential Files** (Ctrl+P, type filename):
   - `OPUS_POST_TRAINING_PROMPT.md`
   - `tune_thresholds.py`
   - `dataset.py`
   - `multilabel_inference.py`
   - `full_pipeline.py`
   - `NEXT_STEPS_POST_TRAINING.md`

3. **Start Claude** (Ctrl+I or click Copilot)

4. **Paste this message:**
   ```
   Please read the OPUS_POST_TRAINING_PROMPT.md file I have attached. 
   This is a continuation session for post-training optimization of 
   my drum transcription model that achieved 0.90+ F1.
   
   Start with Task 1: Per-Class Threshold Tuning.
   ```

## 📂 Directory Quick Reference

```
c:\github\BeatSight\
├── ai-pipeline\
│   ├── OPUS_POST_TRAINING_PROMPT.md  ← MAIN PROMPT
│   ├── NEXT_STEPS_POST_TRAINING.md
│   ├── runs\
│   │   └── v5_multilabel_final_v2\
│   │       ├── best_checkpoint.pt         (114MB)
│   │       ├── best_multilabel_model.pt   (86MB)
│   │       ├── best_multilabel_model_ema.pt (29MB) ← BEST MODEL
│   │       └── thresholds.json            (TO CREATE)
│   ├── training\multilabel\
│   │   ├── tune_thresholds.py
│   │   ├── dataset.py
│   │   └── metrics.py
│   ├── transcription\
│   │   ├── full_pipeline.py
│   │   ├── multilabel_inference.py
│   │   └── instrument_pitch_ranker.py
│   └── models\
│       └── cnn_v5.py
├── docs\
│   ├── CYMBAL_PITCH_RANKING.md
│   ├── TOM_PITCH_RANKING.md
│   └── INSTRUMENT_PITCH_RANKING.md
└── F:\datasets\multilabel_real_v3\   ← TRAINING DATA
    ├── egmd\
    ├── groove_midi\
    ├── slakh\
    └── lakh_synth\
```

## 🔑 Key Information to Remember

- **12 Classes:** china, crash, cross_stick, hihat_closed, hihat_open, hihat_pedal, kick, ride_bell, ride_bow, snare, splash, tom
- **Best Model:** `best_multilabel_model_ema.pt` (29MB, EMA weights)
- **F1 Score:** 0.9039 Micro-F1, 0.9033 Macro-F1 (Epoch 4)
- **Dataset:** 12.8M samples across 4 sources
