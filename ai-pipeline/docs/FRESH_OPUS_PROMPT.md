## PROMPT START

I'm working on a multi-label drum classifier that detects 12 simultaneous drum hit classes from audio spectrograms. **I've been stuck at F1=0.78 for a while and need to reach 0.90.**

A previous Claude session identified what it believes is the root cause: my synthetic multi-label training dataset has **zero solo samples**—every sample has 2-3 classes blended together. The theory is that the model never learns what each class sounds like in isolation, so it can't distinguish similar-sounding classes when they're mixed.

**I'm skeptical and want your independent analysis.** The previous session went through many iterations of tweaking hyperparameters before landing on this dataset issue. I want to make sure we're not chasing the wrong problem.

## The Situation

- **Model**: CNN with 7.1M parameters, multi-label classification (12 classes)
- **Current best**: Micro F1 = 0.7794 (with per-class threshold tuning)
- **Target**: Micro F1 = 0.90
- **Plateau**: After 6 epochs, F1 improved by only +0.003 total

## The 3 Worst Classes (dragging down overall F1)

| Class | F1 | Issue |
|-------|-----|-------|
| hihat_pedal | 0.495 | P=0.52, R=0.47 - both terrible |
| cross_stick | 0.671 | R=0.60 - missing 40% of samples |
| ride_bow | 0.684 | P=0.66 - too many false positives |

## The Proposed Root Cause

Current multi-label dataset:
- 1-label (solo): **0 samples (0%)**
- 2-label: 6M samples (67%)
- 3-label: 3M samples (33%)

The `hihat_pedal` class co-occurs with `kick` 43% of the time and is NEVER seen alone. The hypothesis is the model learned "kick" but can't recognize "hihat_pedal" when it appears.

## The Proposed Solution

Regenerate dataset with 30% solo samples so the model learns each class's unique acoustic signature.

## What I Need From You

1. **Validate or challenge** this diagnosis. Is the lack of solo samples really the bottleneck, or could there be other issues?

2. **Alternative hypotheses** - What else could cause this plateau? Consider:
   - Model capacity
   - Loss function design
   - The synthetic spectrogram blending approach itself
   - Class similarity issues (hihat_pedal vs kick are acoustically similar)

3. **If solo samples ARE the answer**, what ratio would you recommend? The previous session suggested 30%.

4. **If there's a better approach**, what would you try instead?

Please review the attached files and give me your honest assessment. I've invested a lot in this project and want to make sure I'm solving the right problem.

## PROMPT END

---

## Files to Attach

**In VS Code, you can drag and drop these files into the Claude chat or use @ to reference them:**

### Required (attach these first):
1. `@ai-pipeline/docs/MULTILABEL_F1_PLATEAU_ANALYSIS.md` - The full analysis document I just created
2. `@ai-pipeline/training/multilabel/loss.py` - All loss functions (OHEM, focal, asymmetric, etc.)
3. `@ai-pipeline/training/multilabel/dataset.py` - Dataset class with spectrogram blending logic
4. `@ai-pipeline/training/multilabel/generate_multilabel_dataset.py` - Dataset generator

### Helpful context (attach if possible):
5. `@ai-pipeline/models/cnn_v5.py` - Model architecture
6. `@ai-pipeline/training/multilabel/train_multilabel.py` - Training script

### Optional (for deep dive):
7. `@ai-pipeline/runs/v5_multilabel_ohem/optimal_thresholds.json` - Current per-class metrics

---

## Tips for the New Session

1. **Start fresh** - Don't mention the previous session's conclusions upfront. Let Opus form its own opinion.

2. **Ask for alternatives first** - Before confirming the solo-sample theory, ask "What else could cause this?"

3. **Be specific about constraints** - Mention you can't easily get more raw data, but can regenerate synthetic data.

4. **Ask about fundamental limits** - "Is 0.90 F1 even achievable with synthetic spectral blending?"

5. **Request a prioritized action plan** - Ask for ranked recommendations, not just a list.
