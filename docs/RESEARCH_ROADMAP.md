# BeatSight: Research Roadmap

A guide to BeatSight's training architecture and research potential.

---

## ⭐ Production Path: V5 Ultimate (RECOMMENDED)

**Path G (V5 Ultimate)** is the recommended default for production. It combines all proven 2024/2025 innovations into a single, optimized model.

```bash
# Production Training Path
./auto_train.sh label-audit      # 14  - Find bad labels (~30min)
./auto_train.sh v5-warmup        # 17a - Validate system (~2hr)
./auto_train.sh v5-full          # 17d - Full training (~24hr)
./auto_train.sh v5-self-distill  # 17e - Born-Again boost (~24hr) [optional]

# Total: ~26.5 hours minimum, ~50.5 hours maximum quality
```

See `docs/CUTTING_EDGE_TRAINING_FEATURES.md` for full details.

---

## 🔬 Research Paths (For Patents/Publications)

For novel research contributions and patent-protected IP, there are additional paths available in the legacy menu.

### Novel Contributions Available

| Path | Innovations | Expected Improvement | Training Time |
|------|-------------|---------------------|---------------|
| **Path G (V5)** ⭐ | 22 proven techniques | +14-25% overall | ~26-50 hours |
| **Path E (Temporal)** | 3 novel (Mamba SSM) | +3-8% on edge cases | ~45 hours |
| **Path F (Ultimate)** | 4 novel (Wav2Vec2+Mamba) | +19-37% overall | ~75+ hours |

### Why Path E/F Are Publishable

| Innovation | Why It's Novel |
|------------|----------------|
| **First Mamba/S6 for drums** | Nobody has applied selective state-space models to drum transcription |
| **Audio foundation + SSM fusion** | First to combine Wav2Vec2/HuBERT with Mamba for percussion |
| **Beat-aware positional encoding** | Encodes musical structure (beat, bar, phrase position) |
| **Learnable drum pattern priors** | 32 pattern prototypes with attention |

### Training Research Models

Access these through `legacy` menu option in `post_export_commands.sh`:

```bash
# Temporal Mamba (Path E):
15a) Temporal: Warmup (~3hr)
15d) Temporal: Full   (~24hr)

# Ultimate (Path F):  
16a) Ultimate: Warmup (~5hr)
16d) Ultimate: Full   (~40hr)
```

---

## Implementation Status

| Component | File | Status |
|-----------|------|--------|
| V5 Ultimate Model | `training/models/cnn_v5.py` | ✅ Complete |
| Mamba SSM Core | `training/models/temporal_mamba.py` | ✅ Complete |
| Beat-Aware Encoding | `training/models/temporal_mamba.py` | ✅ Complete |
| Wav2Vec2 Features | `training/models/audio_foundation.py` | ✅ Complete |
| Multi-Resolution Specs | `training/models/multi_resolution.py` | ✅ Complete |
| Sequence Dataset | `training/datasets/sequence_dataset.py` | ✅ Complete |
| Training Script | `training/train_temporal.py` | ✅ Complete |

---

## Architecture Overview (Ultimate Model)

```
┌───────────────────────────────────────────────────────────────────────┐
│  Input: Spectrogram (128×128) + Raw Audio                             │
├───────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────┐       │
│  │ CNN v4      │  │ Wav2Vec2/HuBERT  │  │ Multi-Res Specs    │       │
│  │ (CoordAttn) │  │ (frozen)         │  │ (3 scales)         │       │
│  │ 256-d       │  │ 256-d            │  │ 128-d              │       │
│  └──────┬──────┘  └────────┬─────────┘  └──────────┬─────────┘       │
│        └────────────────┴─────────────────┴──────────┘              │
│                     ┌────────────────────┐                            │
│                     │ Attention Fusion │                            │
│                     └─────────┬──────────┘                            │
│                             │                                        │
│                     ┌───────┴────────┐                            │
│                     │ Beat-Aware      │                            │
│                     │ Pos. Encoding   │                            │
│                     └───────┬────────┘                            │
│                             │                                        │
│                     ┌───────┴────────┐                            │
│                     │ Mamba Layers   │                            │
│                     │ (4-6 layers)   │                            │
│                     └───────┬────────┘                            │
│                             │                                        │
│                     ┌───────┴────────┐                            │
│                     │ Pattern Prior  │                            │
│                     │ (32 prototypes)│                            │
│                     └───────┬────────┘                            │
│                             │                                        │
│                     ┌───────┴────────┐                            │
│                     │ Classifier     │                            │
│                     │ (21 classes)   │                            │
│                     └────────────────┘                            │
└───────────────────────────────────────────────────────────────────────┘
```

---

## The Gap Between "State-of-the-Art User" and "Novel Research"

### Where We Are Now
```
Reading papers → Understanding them → Implementing them → Combining them
```

### Where Novel Research Lives
```
Identifying unsolved problems → Proposing new solutions → Proving they work → Publishing
```

---

## Concrete Paths to Novel Research in Drum Transcription

### 1. Temporal Modeling (Easiest Entry Point)

**The Gap:** Current system classifies each 50ms window independently. Real drummers play *patterns*.

**Novel Contribution:**
```python
# Current: P(snare | spectrogram_t)
# Novel:   P(snare | spectrogram_t, drum_history, tempo, bar_position)
```

**What you'd need:**
- Model drum patterns as sequences (Transformer decoder, state-space models like Mamba)
- Encode musical structure (downbeat, bar position, tempo)
- Show it beats treating hits as independent

**Difficulty:** Medium. People have done this for piano, not well-explored for drums.

---

### 2. Physics-Informed Neural Networks

**The Gap:** Model treats spectrograms as arbitrary images. Drums have known physics.

**Novel Contribution:**
```python
# Encode: snare resonance ~200Hz, kick fundamental ~60Hz, cymbal decay curves
# Constraint: predictions must be physically plausible
```

**What you'd need:**
- Acoustic models of drum sounds
- Differentiable physics simulation
- Show physics constraints improve generalization

**Difficulty:** Hard. Requires acoustics knowledge + ML.

---

### 3. Self-Supervised Drum Foundation Model

**The Gap:** We train on ~10K labeled samples. YouTube has millions of drum videos.

**Novel Contribution:**
```
Pretrain on 1M+ unlabeled drum recordings
→ Learn general "drum understanding"
→ Fine-tune on small labeled set
→ Beat supervised-only by 20%+
```

**What you'd need:**
- Scrape/collect massive unlabeled drum audio
- Design pretext tasks (predict masked drums, contrastive drum pairs)
- Compute resources (this is expensive)
- Show transfer learning works for drums specifically

**Difficulty:** Medium-Hard. Data collection is the bottleneck.

---

### 4. Multi-Instrument Joint Transcription

**The Gap:** Current systems do drums OR guitar OR vocals separately.

**Novel Contribution:**
```
Single model that understands:
- Drums, bass, guitar, vocals simultaneously
- How they interact (drums follow guitar riffs, etc.)
- Musical context improves all transcriptions
```

**What you'd need:**
- Multi-instrument dataset with aligned labels
- Architecture that shares representations
- Show joint modeling beats separate models

**Difficulty:** Hard. Dataset creation is brutal.

---

### 5. Differentiable Drum Synthesis (Most Novel)

**The Gap:** We classify. We don't *understand* drums.

**Novel Contribution:**
```python
# Instead of: spectrogram → "snare"
# Do:         spectrogram → drum_params → reconstructed_spectrogram
#             (invert and generate, not just classify)
```

**What you'd need:**
- Differentiable drum synthesizer
- Train to reconstruct, get transcription as byproduct
- Show this learns better representations

**Difficulty:** Very Hard. Closest to PhD-level work.

---

## What You'd Actually Need to Do

### Skills to Develop

| Skill | How to Get It |
|-------|---------------|
| **Math foundations** | Linear algebra, probability, optimization (3-6 months of study) |
| **Read papers critically** | Read 2-3 papers/week, implement from scratch |
| **Identify gaps** | What do papers NOT solve? What assumptions break? |
| **Run experiments** | Ablations, baselines, statistical significance |
| **Write clearly** | Your idea means nothing if you can't explain it |

### Concrete Next Steps

1. **Pick ONE direction above** that excites you most

2. **Do a literature review:**
   - Search "drum transcription" on arXiv, Google Scholar
   - Find the 10 most-cited papers
   - Read them and note what they DON'T do

3. **Implement a baseline from a paper:**
   - Not using their code—implement yourself
   - This forces deep understanding

4. **Find a small novel twist:**
   - "What if I added X?"
   - "They assumed Y, but what if Z?"

5. **Run rigorous experiments:**
   - Multiple seeds, confidence intervals
   - Compare to published baselines fairly

6. **Write it up:**
   - Even if not published, writing crystallizes thinking

---

## Honest Reality Check

| Path | Time Investment | Prerequisite |
|------|-----------------|--------------|
| Publish at workshop | 3-6 months | Undergrad ML knowledge |
| Publish at conference | 6-12 months | Strong ML foundations |
| Publish at top venue (NeurIPS, ICML) | 1-2 years | Usually requires PhD advisor/collaborators |

### The Secret Nobody Tells You

Most "novel" papers are **small incremental improvements**:
- "We added attention to X"
- "We tried method A on domain B"
- "We combined X and Y for the first time"

The bar is lower than it looks. The hard part is:
1. **Doing the work** (most people don't)
2. **Writing it clearly** (most people can't)
3. **Positioning it correctly** (knowing what reviewers want)

---

## If You Want to Start Today

**Easiest novel contribution for BeatSight:**

> ### "Temporal Context Improves Drum Transcription: A State-Space Approach"

1. Take current v4 model (your strong baseline)
2. Add a Mamba/S4 layer on top to model temporal context
3. Show 3-5% improvement on standard benchmarks
4. Write 8-page paper

**That's publishable at a music information retrieval workshop (ISMIR, SMC) within 6 months.**

---

## Key Conferences & Venues

| Venue | Focus | Deadline (typical) |
|-------|-------|-------------------|
| ISMIR | Music Information Retrieval | May-June |
| SMC | Sound and Music Computing | March-April |
| ICASSP | Audio/Signal Processing | October |
| NeurIPS (workshop) | General ML | September |
| DAFx | Digital Audio Effects | March |

---

## Recommended Reading

### Foundational Papers
1. Vogl et al. (2017) - "Drum Transcription via Joint Beat and Drum Modeling"
2. Cartwright & Bello (2018) - "Increasing Drum Transcription Vocabulary Using Data Augmentation"
3. Jacques & Roebel (2021) - "Automatic Drum Transcription with Convolutional Neural Networks"

### State-Space Models (for temporal modeling)
1. Gu et al. (2022) - "Efficiently Modeling Long Sequences with Structured State Spaces" (S4)
2. Gu & Dao (2023) - "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"

### Music Foundation Models
1. Huang et al. (2022) - "Mulan: A Joint Embedding of Music Audio and Natural Language"
2. Agostinelli et al. (2023) - "MusicLM: Generating Music From Text"
