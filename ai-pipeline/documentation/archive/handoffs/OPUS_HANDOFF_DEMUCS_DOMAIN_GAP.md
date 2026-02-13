# BeatSight AI Pipeline Handoff — Demucs Domain Gap & Model Optimization (Feb 9, 2026)

## Archive Metadata

- **Document Type:** Handoff / investigation brief (archived)
- **Status:** Historical reference only
- **Normalized On:** 2026-02-13
- **Canonical Location:** `ai-pipeline/documentation/archive/handoffs/`
- **Current Source of Truth:** `ai-pipeline/documentation/current/`

## PURPOSE

This document is a handoff for a new Claude Opus 4.6 session to continue optimizing the BeatSight drum transcription model. The goal is to achieve the best possible drum classification F1 on real-world (Demucs-separated) audio. The new session is free to modify code, recommend changes, evaluate approaches, and propose new strategies.

---

## THE CORE PROBLEM

BeatSight's inference pipeline processes ALL audio through Demucs separation (htdemucs_ft) before classifying drum hits. The model (CNN V5 Large, 7.1M params, 12-class multi-label sigmoid) performs very differently on clean vs Demucs-separated audio:

| Metric | Clean Data | Demucs Data | Gap |
|--------|-----------|-------------|-----|
| Micro-F1 (raw, threshold=0.5) | 0.865 | 0.522 | +0.343 |
| Micro-F1 (tuned per-class thresholds) | 0.835 | 0.607 | +0.228 |
| Combined Micro-F1 | 0.8023 (misleading — 74% of val is clean) |

**The combined F1 of 0.8023 is misleadingly optimistic.** In production, 100% of audio goes through Demucs, so the real-world performance is the Demucs F1 of ~0.52-0.61 (depending on threshold calibration). The clean F1 of 0.865 is irrelevant to users.

### Per-Class Domain Gap (Epoch 6)

```
Class            Clean F1  Demucs F1     Gap
-------------------------------------------
china               0.973      0.305  +0.668
crash               0.898      0.369  +0.529
cross_stick         0.915      0.589  +0.327
hihat_closed        0.817      0.439  +0.379
hihat_open          0.812      0.567  +0.245
hihat_pedal         0.779      0.550  +0.229
kick                0.870      0.495  +0.375
ride_bell           0.894      0.462  +0.431
ride_bow            0.825      0.568  +0.256
snare               0.892      0.614  +0.278
splash              0.991      0.304  +0.687
tom                 0.911      0.672  +0.242
```

The worst-performing classes on Demucs are china (0.305), splash (0.304), crash (0.369), and hihat_closed (0.439). These are the classes that need the most attention.

---

## CURRENT STATE (Updated by Session 2)

### Training State

**Training was stopped by the user** at epoch 7 (~19%) to await new session recommendations. Best model is epoch 6 (combined F1 = 0.8023, Demucs F1 = 0.522).

Checkpoints available:
- `best_checkpoint.pt` — epoch 6, F1 0.8023
- `latest_checkpoint.pt` — epoch 7 mid-epoch (batch 23,555 / 122,231)
- `checkpoint_epoch_0004.pt`, `checkpoint_epoch_0005.pt`, `checkpoint_epoch_0006.pt`

### Code Changes Made in Session 2

1. **Fixed `_ZERO_DEMUCS_TRAINING_CLASSES` in `multilabel_inference.py`** — Removed the stale Tier 4 "zero-Demucs" designation and 0.15 extreme factor. China and splash moved to Tier 3 (SENSITIVE) alongside crash. The `_ZERO_DEMUCS_TRAINING_CLASSES` frozenset and `_ZERO_DEMUCS_THRESHOLD_FACTOR` constant were removed entirely.

   **BUG THAT WAS FIXED**: Even with `threshold_scale=1.0`, china/splash thresholds were being multiplied by 0.15. So Demucs-only thresholds + scale=1.0 + the 0.15 factor = triple-compensation. This is now fixed — `threshold_scale=1.0` passes thresholds through unmodified.

2. **Added per-individual-Demucs-dataset breakdown** in `evaluate_by_source()` (`train_multilabel.py`) — Each Demucs sub-dataset (egmd_demucs, slakh2100_demucs, groove_midi_demucs, enst_drums_demucs) now reports its own F1 separately. Shows as `Demucs by source: egmd: 0.XXX (N) | slakh: 0.XXX (N) | ...` in training output.

### Active Run: `runs/v5_finetune_demucs_v2/`

**Training command** (no `--pretrained-checkpoint`, uses `--resume` for proper auto-resume):
```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m training.multilabel.train_multilabel \
  --dataset "F:/datasets/multilabel_real_v3" \
  --output-dir runs/v5_finetune_demucs_v2/ \
  --resume runs/v5_finetune_demucs_v2/best_checkpoint.pt \
  --model-version v5 --v5-size large \
  --epochs 20 --batch-size 128 --grad-accum-steps 5 \
  --lr 2e-5 --min-lr 2e-7 --amp-dtype bfloat16 \
  --balanced-sampling --balanced-method rare_class \
  --acoustic-oversample 10.0 \
  --dataset-weight enst_drums_demucs=20 \
  --dataset-weight egmd_demucs=15 \
  --dataset-weight groove_midi_demucs=15 \
  --dataset-weight slakh2100_demucs=20 \
  --loss-type cb_focal --cb-beta 0.999 --gamma 2.0 \
  --label-smoothing 0.02 --specaugment drum \
  --use-ema --ema-decay 0.9995 \
  --scheduler cosine --warmup-epochs 1 \
  --gradient-checkpointing --grad-clip-norm 1.0 \
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \
  --checkpoint-every 1 --checkpoint-every-batches 5000 --channels-last
```

### Training Progress (3 epochs of domain gap data)

| Epoch | Combined F1 | Clean F1 | Demucs F1 | Gap | Val Loss | LR |
|-------|-------------|----------|-----------|-----|----------|-----|
| E4 | 0.7995 | 0.863 | 0.514 | +0.349 | 0.0277 | 1.89e-05 |
| E5 | 0.8016 | 0.864 | 0.519 | +0.345 | 0.0274 | 1.81e-05 |
| E6 | 0.8023 | 0.865 | 0.522 | +0.343 | 0.0273 | 1.71e-05 |

**Trend**: Demucs F1 improving slowly (+0.004/epoch). Clean F1 stable. Combined F1 improving. At this rate, Demucs F1 may reach ~0.57-0.58 by epoch 20. The cosine LR decay means later epochs contribute diminishing returns.

### Threshold Results (Generated from epoch 6 best model)

**Mixed thresholds** (full val set, 1.76M samples):
```
Class             Thresh     Prec   Recall       F1    Support
china              0.530    0.899    0.602    0.721     55,665
crash              0.670    0.913    0.836    0.873     58,096
hihat_closed       0.360    0.775    0.816    0.795    427,622
kick               0.390    0.834    0.864    0.849    449,541
snare              0.400    0.884    0.879    0.881    532,688
splash             0.820    0.997    0.977    0.987     65,670
Tuned micro-F1: 0.8345 | Tuned macro-F1: 0.8327
```

**Demucs-only thresholds** (451K Demucs val samples):
```
Class             Thresh     Prec   Recall       F1    Support
china              0.380    0.341    0.492    0.403     26,512
crash              0.620    0.394    0.454    0.422      6,082
hihat_closed       0.330    0.528    0.719    0.609    113,476
kick               0.360    0.531    0.751    0.622     93,475
snare              0.380    0.628    0.763    0.689     95,513
splash             0.620    0.278    0.420    0.334        948
Tuned micro-F1: 0.6072 | Tuned macro-F1: 0.5466
```

**Key insight**: Even with optimal Demucs-specific thresholds, the best achievable Demucs F1 is 0.6072. The model fundamentally struggles with Demucs spectral artifacts. China (34% precision) and splash (28% precision) are particularly bad — the model produces many false positives for these classes on Demucs audio.

### Test Map Results: "Heir of Grief" (prog metal, ~5:09)

All tests used the epoch 6 best model with `threshold_scale=1.0` (no scaling). The inference code fix (removing `_ZERO_DEMUCS_TRAINING_CLASSES`) was applied.

| Approach | Total Hits | China | Kick | Snare | HH Closed | Splash | Crash | Ride Bow | Tom |
|----------|-----------|-------|------|-------|-----------|--------|-------|----------|-----|
| Demucs + Mixed thresh | 2,293 | **1,345** | 315 | 139 | 79 | 110 | 5 | 95 | 118 |
| Demucs + Demucs thresh | 2,529 | **1,374** | 457 | 180 | 154 | 152 | 7 | 41 | 83 |
| **Hybrid classification** | **1,133** | **0** | **470** | 103 | **290** | **0** | **14** | **140** | 88 |

**Analysis**:
- **Demucs classification massively over-detects china** — 1,345 china hits in a 5-minute track (~4.4/sec) is clearly wrong and produces unusable maps. This is the model's 34% precision on Demucs china manifesting in practice.
- **Hybrid classification eliminates china and splash entirely** — the model can't distinguish these cymbals through full-mix harmonic bleed (guitars mask cymbal characteristics). Zero china/splash is also wrong, but less destructive than 1,345 false china hits.
- **Hybrid has much better kick/hihat/ride balance** — 470 kick, 290 hihat, 140 ride is plausible for prog metal. Demucs approaches severely under-detect these.
- **Neither approach is perfect** — each has its own domain gap. The ideal solution would combine Demucs onset detection with improved Demucs classification (via domain adaptation training).
- **Hybrid is faster** — 67s vs 89s (no silence gating overhead, all 1,544 onsets processed vs 1,407-1,426 after gating).

**Practical implication**: For songs where china/splash are not prominent, hybrid classification produces much more usable maps right now. For songs with heavy china/splash usage, neither approach is good enough yet.

---

## MODEL & ARCHITECTURE

- **Model**: CNN V5 Large, 7,143,308 parameters
- **Input**: (1, 128, 128) mel-spectrogram (power_to_db, fmax=8000, n_mels=128)
- **Output**: 12-class sigmoid (multi-label, NOT softmax)
- **12 classes** (index order): china, crash, cross_stick, hihat_closed, hihat_open, hihat_pedal, kick, ride_bell, ride_bow, snare, splash, tom
- **Spectrogram extraction**: Asymmetric window (1/4 before onset, full window after), 100ms, normalized to [0,1] per-sample
- **EMA**: decay=0.9995, used for best model selection
- **Cosine LR**: T_max=20 epochs, lr=2e-5 -> min_lr=2e-7, 1 warmup epoch

### Training Data: `F:/datasets/multilabel_real_v3/`

| Dataset | Train Samples | Type | Notes |
|---------|-------------|------|-------|
| egmd | 8,770,674 | electronic (clean) | EGMD v1, largest dataset, zero china/splash |
| slakh2100_demucs | 2,267,413 | demucs | Has china (236K) + splash (5.6K) |
| egmd_demucs | 1,402,959 | demucs | Zero china/splash |
| lakh | 1,265,625 | synthetic | Has china (224K) + splash (551K) |
| slakh | 1,238,648 | electronic (clean) | Has china (1.9K) + splash (5.4K) |
| groove_midi_demucs | 312,660 | demucs | Zero china/splash |
| groove_midi | 212,275 | electronic (clean) | Zero china/splash |
| acoustic_synth | 90,000 | synthetic | Has china (35K) + splash (23K) |
| enst_drums | 41,503 | acoustic (clean) | Has china (61) + splash (26) |
| enst_drums_demucs | 39,014 | demucs | Has china (58) + splash (26) |
| idmt_smt_drums_v2 | 4,328 | acoustic (clean) | HH/kick/snare only |
| cambridge_multitrack | 476 | acoustic (clean) | Small |
| telefunken | 27 | acoustic (clean) | Tiny |
| signaturesounds | 21 | acoustic (clean) | Tiny |
| medleydb | 0 | acoustic (clean) | Empty train |

**Total**: 15,645,623 train + 1,762,001 val

**Key data fact**: China and splash on Demucs come almost exclusively from slakh2100_demucs (236K china, 5.6K splash). EGMD_demucs, groove_midi_demucs, and enst_drums_demucs have zero or near-zero china/splash.

---

## CRITICAL CODE FILES

### Training Script
**`ai-pipeline/training/multilabel/train_multilabel.py`** (~1970 lines)

Changes made across sessions:
1. **Demucs source category tracking** in `evaluate_by_source()` — tracks 'demucs' category separately, computes clean aggregate from raw logits
2. **Per-individual-Demucs-dataset breakdown** (Session 2) — each Demucs sub-dataset reports F1 individually
3. **Validation progress bar** — tqdm across all sub-datasets with dataset name, running accuracy, loss
4. **RNG ByteTensor restore fix** — `.cpu().byte()` for both CPU and CUDA RNG states
5. **Mid-epoch resume fix** — Removed broken `Subset + shuffle=False` approach. Now restarts the full epoch with `WeightedRandomSampler` intact.
6. **Domain gap printing** — Shows CLEAN F1, DEMUCS F1, Gap, per-class comparison table, and per-Demucs-dataset breakdown

### Inference Pipeline
**`ai-pipeline/transcription/multilabel_inference.py`**
- Contains tiered domain gap scaling (3 tiers after Session 2 fix):
  - Tier 1 (common): kick, snare, hihat_*, tom, ride_bow — `scale^0.25`
  - Tier 2 (moderate): ride_bell, cross_stick — `scale^0.5`
  - Tier 3 (sensitive): crash, china, splash — `scale^0.75`
- **Session 2 fix**: `_ZERO_DEMUCS_TRAINING_CLASSES` and `_ZERO_DEMUCS_THRESHOLD_FACTOR` REMOVED. China/splash moved to Tier 3. `threshold_scale=1.0` now passes thresholds through unmodified (previously still applied 0.15 factor).

### Threshold Generator
**`ai-pipeline/scripts/generate_thresholds.py`**
- Per-class F1-maximizing threshold sweep
- Already supports `--manifests` for Demucs-only threshold generation
- No code changes needed

### Pipeline Process
**`ai-pipeline/pipeline/process.py`**
- **Hybrid classification implemented** (lines 276-284): Use Demucs for onset detection only, classify on original full-mix audio. Enable with `--hybrid-classification`. Sets `threshold_scale=1.0` automatically.
- **Default `--threshold-scale` is 0.7** (NOT 1.0). Tests in Session 2 used `--threshold-scale 1.0` explicitly.
- Demucs separation in `ai-pipeline/separation/demucs_separator.py`

**All multilabel CLI arguments in process.py:**

| Argument | Default | Purpose |
|----------|---------|---------|
| `--multilabel` | True | Enable multi-label classifier (on by default) |
| `--no-multilabel` | - | Disable multi-label, fall back to single-label |
| `--multilabel-model` | None | Path to multi-label model checkpoint (.pt) |
| `--multilabel-thresholds` | None | Path to per-class thresholds JSON |
| `--threshold-scale` | 0.7 | Domain gap scale factor (0.5=aggressive, 0.7=balanced, 1.0=strict/no scaling) |
| `--hybrid-classification` | False | Demucs for onsets only, classify on original audio (forces threshold_scale=1.0) |
| `--adaptive-thresholds` | False | Compute per-song optimal thresholds (experimental) |
| `--adaptive-threshold-method` | "otsu" | Method: "otsu", "percentile", or "knee" |

### Drum Classifier (Integration Layer)
**`ai-pipeline/transcription/drum_classifier.py`**
- `classify_drums()` (line ~271): Main entry point, delegates to `_classify_drums_multilabel()` when `use_multilabel=True`
- `_classify_drums_multilabel()` (line ~389): Creates/gets cached `MultiLabelDrumClassifier` instance, passes `threshold_scale` through
- Data flow: `process.py` → `drum_classifier.classify_drums()` → `_classify_drums_multilabel()` → `MultiLabelDrumClassifier.get_cached(threshold_scale=...)` → `classify_batch()` → `_apply_thresholds()` → `_refine_multilabel_detections()`

### Musical Constraint System (Multi-Label Refinement)
**`ai-pipeline/transcription/multilabel_inference.py`** — `_refine_multilabel_detections()` (lines 513-597)

The model produces raw sigmoid detections, then this function applies 4 musical constraint layers to remove domain gap artifacts:

1. **Hi-hat mutual exclusion** — Only one hi-hat articulation (closed/open/pedal) per onset. Keeps highest confidence. `_HIHAT_EXCLUSIVE_GROUP = {'hihat_closed', 'hihat_open', 'hihat_pedal'}`

2. **Kick+snare co-occurrence gate** — Both must exceed 0.40 confidence for co-detection. Otherwise the weaker one is removed. `_BODY_COOCCURRENCE_MIN_PROB = 0.40`

3. **Relative confidence filter** — Secondary detections must be ≥35% of peak confidence. Prevents Demucs bleed causing false multi-label activation. **Cymbals are exempt** (crash, china, splash, ride_bell, ride_bow naturally layer with body drums). `_RELATIVE_CONFIDENCE_RATIO = 0.35`

4. **Max components per onset** — Hard cap of 4 simultaneous instruments. Beyond 4 is almost certainly artifact. `_MAX_COMPONENTS_PER_ONSET = 4`

### Dataset
**`ai-pipeline/training/multilabel/dataset.py`**
- `BatchedMultiLabelDataset` with `shuffle_before_split=True`

---

## BUGS FIXED ACROSS SESSIONS

1. **RNG ByteTensor restore** — Checkpoint loaded with `map_location=device` (CUDA) moved RNG tensors to GPU, but `torch.set_rng_state()` requires CPU ByteTensor. Fixed with `.cpu().byte()`.

2. **Mid-epoch resume catastrophic forgetting** — `Subset + shuffle=False` on ConcatDataset caused sequential traversal (8.77M EGMD samples in a row with zero china/splash). Epoch 4 collapsed: Micro-F1 0.7964 -> 0.6989, china F1 0.715 -> 0.042, splash F1 0.974 -> 0.015. Fixed by restarting full epoch with proper `WeightedRandomSampler`.

3. **`--pretrained-checkpoint` blocking auto-resume** — The flag's presence disabled auto-resume detection. Removed from resume commands.

4. **`_ZERO_DEMUCS_TRAINING_CLASSES` triple-compensation bug** (Session 2) — Even with `threshold_scale=1.0`, china/splash got multiplied by 0.15. With Demucs-only thresholds (already calibrated for Demucs) + scale 1.0 + 0.15 factor, thresholds were reduced to ~6-9% of their calibrated values. Fixed by removing the entire Tier 4 system.

---

## STRATEGIES TO EXPLORE (Prioritized, Updated After Testing)

### Session 2 Honest Assessment

Continuing the current mixed-data training (74% clean, 26% Demucs) to epoch 20 will produce **diminishing returns**: Demucs F1 at +0.004/epoch means ~0.57-0.58 raw by epoch 20, or ~0.63-0.65 with tuned thresholds. The model optimizes primarily for clean because that's the majority. It won't fix the china problem (1,345 false positives).

**Recommended priority order:**
1. **Strategy 5 (ensemble)** — No training needed, just a pipeline change. Gives immediately better maps.
2. **Strategy 2 (Demucs-only fine-tuning)** — Most impactful training change. The model already knows what drums sound like; it just needs to learn Demucs artifacts. Could push Demucs F1 from 0.607 to 0.70+.
3. **Strategy 3 (continue to epoch 20)** — Only if GPU time is "free" and nothing else is actionable.
4. **Strategy 4 (increased Demucs weights)** — For a fresh run if Demucs-only fine-tuning hits a ceiling.

### Strategy 1: Hybrid Classification (TESTED — Mixed Results)

**Result**: Hybrid gives much better kick/hihat/ride balance but completely fails on china/splash. See test map comparison table above.

**When to use**: Songs without prominent china/splash cymbals. Hybrid produces 1,133 well-balanced hits vs 2,293 china-dominated hits from Demucs classification.

**Limitation**: The model was trained on isolated drum stems. Full-mix audio has guitar/bass/vocal bleed that masks cymbal characteristics. China and splash have 0 detections in hybrid mode.

**Possible improvement**: Train or fine-tune the model on full-mix audio spectrograms (not just Demucs/clean stems) to handle harmonic bleed. This would require re-extracting spectrograms from full-mix audio at the same onset times.

### Strategy 2: Demucs-Only Fine-Tuning Stage (VIABLE, NEEDS IMPLEMENTATION)

Take the best checkpoint and fine-tune exclusively on the 4 Demucs datasets:
- slakh2100_demucs (2.27M), egmd_demucs (1.4M), groove_midi_demucs (312K), enst_drums_demucs (39K)

Use a very low LR (e.g., 5e-6) to gently adapt without catastrophic forgetting.

**Implementation needed**: The training script loads ALL manifests in the dataset directory. To do Demucs-only training:
a) Create a separate dataset directory with only Demucs manifests (symlinks), OR
b) Add `--include-manifests` / `--exclude-manifests` CLI args to the training script, OR
c) Set all non-Demucs dataset weights to 0 (may cause sampler issues)

### Strategy 3: Continue Current Training to Epoch 20

Let the current run finish. Demucs F1 improving at +0.004/epoch → ~0.57-0.58 by epoch 20. The per-source Demucs breakdown (newly implemented) will show which Demucs datasets are improving fastest.

### Strategy 4: Increased Demucs Weights (Next Full Training Run)

If the current run finishes and Demucs F1 is still < 0.60:
```bash
--dataset-weight slakh2100_demucs=40 \
--dataset-weight egmd_demucs=30 \
--dataset-weight groove_midi_demucs=30 \
--dataset-weight enst_drums_demucs=40
```

### Strategy 5: Combined Approach (Hybrid + Demucs Ensemble)

Use hybrid classification for body drums (kick, snare, hihat, tom, ride) where it excels, and Demucs classification for cymbal classes (china, splash, crash) where it detects more. This would require modifying the inference pipeline to run both paths and merge results.

### Strategy 6: Spectrogram Denoising / Domain Transfer (Research, High Effort)

Train a small U-Net to learn the mapping: `demucs_spectrogram -> clean_spectrogram`. Paired training data exists (same performances in EGMD/Slakh as both clean and Demucs versions).

### Strategy 7: Domain-Aware Model (Architectural Change)

Add a domain indicator input to the model (0=clean, 1=Demucs), or add a second input channel for the full-mix spectrogram alongside the Demucs spectrogram (dual-input model).

---

## DEMUCS TECHNICAL REFERENCE

### Model Used: htdemucs_ft
- Hybrid Transformer Demucs (fine-tuned variant)
- 2.5x faster than htdemucs, minimal quality loss
- SDR: ~9.0 dB on MUSDB HQ test set
- Separates: drums, bass, vocals, other (4 stems)
- Max segment: 7.8 seconds for Transformer attention
- Repository: https://github.com/facebookresearch/demucs (archived)
- Active fork: https://github.com/adefossez/demucs

### Why Demucs Hurts Classification
1. **Spectral smearing** of transients — drum attacks are fastest musical transients; Demucs STFT smooths sharp spectral peaks that distinguish china from crash
2. **Harmonic bleeding** — drums are non-harmonic (noise bursts), Demucs trained primarily on harmonic separation
3. **Training distribution mismatch** — Demucs trained on MUSDB18 (150 songs), production audio has much broader genre diversity
4. **No drum-specific model available** — htdemucs_drums exists but is still general-purpose, not optimized for drum subclass preservation

### Separation Alternatives
- No significantly better models exist for drum separation as of Jan 2025
- The Sparse Hybrid Transformer (9.20 SDR) requires custom CUDA code and isn't publicly available as a pretrained model
- Band-Split RNN achieves similar SDR (~9.0)

---

## CODEBASE STRUCTURE

```
c:\github\BeatSight\
├── ai-pipeline/                    # Python ML pipeline
│   ├── training/
│   │   └── multilabel/
│   │       ├── train_multilabel.py # Main training script (~1970 lines)
│   │       └── dataset.py          # BatchedMultiLabelDataset
│   ├── transcription/
│   │   ├── multilabel_inference.py # Inference + thresholds + domain gap scaling
│   │   └── full_pipeline.py        # Full transcription pipeline
│   ├── pipeline/
│   │   ├── process.py              # CLI pipeline entry, hybrid classification
│   │   ├── structured_decoder.py   # Musical structure analysis
│   │   ├── genre_aware_decoder.py  # Genre-specific decoding
│   │   ├── pattern_library.py      # Pattern repair
│   │   └── chart_readability.py    # Difficulty filtering
│   ├── separation/
│   │   └── demucs_separator.py     # Demucs wrapper
│   ├── scripts/
│   │   ├── generate_thresholds.py  # Threshold optimization
│   │   └── create_demucs_augmented_dataset.py
│   ├── runs/
│   │   ├── v5_multilabel_final_v3/ # Original pretrained model (DO NOT DELETE)
│   │   └── v5_finetune_demucs_v2/  # Current training run
│   └── models/
│       └── drum_classifier_production/
├── desktop/                        # C# osu!framework desktop app
└── test_songs/                     # Test audio files
```

---

## HARDWARE

- GPU: RTX 3080Ti FE (12GB VRAM)
- CPU: AMD 9800X3D
- RAM: 32GB DDR5
- C: NVMe (code, OS)
- F: Samsung 990 Pro NVMe (datasets, running low on space)
- Training speed: ~10 it/s, ~4 hours per epoch

---

## KEY DECISIONS ALREADY MADE

1. **Mid-epoch resume restarts full epoch** — The old Subset+shuffle=False approach caused catastrophic forgetting. Now saves model weights at mid-epoch but restarts from epoch start with WeightedRandomSampler on resume.
2. **`--pretrained-checkpoint` removed from resume commands** — It blocks auto-resume. Use `--resume path/to/checkpoint.pt` instead.
3. **EMA model used for inference** — `best_multilabel_model_ema.pt` not `best_multilabel_model.pt`
4. **`_ZERO_DEMUCS_TRAINING_CLASSES` FIXED** (Session 2) — China and splash moved to Tier 3 (SENSITIVE) alongside crash. The 0.15 extreme factor and Tier 4 system removed entirely.
5. **train_classifier.py (single-label) handles mid-epoch resume correctly** — Uses `_DeterministicWeightedSampler` with `start_sample_index` tensor slicing, preserving class balance. No fix needed.
6. **Hybrid classification tested** (Session 2) — Gives better body drum balance but zero china/splash. Neither pure Demucs nor hybrid is a complete solution.

---

## WHAT THE USER WANTS

The user wants to build the best drum classifier model possible and achieve the highest Demucs F1 score achievable. They are motivated and willing to invest compute time. They want:

1. Honest evaluation of what's achievable vs what's aspirational
2. Data-driven decisions, not guesses
3. Multiple strategies explored and compared
4. Code changes implemented, not just recommended
5. The new session is free to modify, recommend, evaluate, and propose anything (earlier sessions had "do not modify" restrictions — those are lifted)

**User's current sentiment** (end of Session 2): Hesitant about continuing the current training run. Expressed concern that the model "doesn't feel as though it's getting to where I want." Was told honestly that current trajectory gives ~0.63-0.65 with tuned thresholds by epoch 20. Was receptive to Demucs-only fine-tuning and ensemble approach as higher-impact alternatives.

**Key clarification from Session 2**: The user asked about `--threshold-scale` vs `--hybrid-classification` and now understands these are two different approaches (classify on Demucs-separated vs classify on full-mix audio), not combinable parameters.

---

## IMMEDIATE NEXT STEPS FOR THE NEW SESSION

### Completed (by Session 2):
- [x] Check training state — Stopped at epoch 7 (~19%), best is epoch 6
- [x] Test hybrid classification — Results show better body drum balance but zero china/splash
- [x] Test Demucs-only thresholds with `threshold_scale=1.0` — User ran both, results in test map table above
- [x] Fix `_ZERO_DEMUCS_TRAINING_CLASSES` in multilabel_inference.py — Removed Tier 4, china/splash now Tier 3
- [x] Add per-source Demucs breakdown to evaluate_by_source — Implemented, shows per-dataset F1

### Recommended (by Session 2, not yet started):
1. **Implement Strategy 5 (hybrid + Demucs ensemble)** — No training needed. Use hybrid for body drums (kick, snare, hihat, tom, ride) + Demucs for cymbals (crash, china, splash). Merge results per-onset. This should give ~470 kicks + 290 hihats (from hybrid) AND some china/crash detections (from Demucs) — the best of both worlds.
2. **Implement Demucs-only fine-tuning (Strategy 2)** — Needs manifest filtering support in training script. Create a Demucs-only dataset directory (symlinks) or add `--include-manifests` / `--exclude-manifests` CLI args. Use very low LR (5e-6) on the epoch 6 best checkpoint to avoid catastrophic forgetting.
3. **Re-generate thresholds** after any new training for updated model
4. **Test on additional songs** beyond "Heir of Grief" to validate across genres

---

## FILES TO READ FIRST

1. This document
2. `ai-pipeline/documentation/current/CURRENT_AI_PIPELINE_STATE.md` (older state doc, some info superseded by this)
3. `ai-pipeline/training/multilabel/train_multilabel.py` — the training script with all fixes
4. `ai-pipeline/transcription/multilabel_inference.py` — inference with domain gap scaling (FIXED in Session 2)
5. `ai-pipeline/transcription/drum_classifier.py` — integration layer between pipeline and multilabel classifier
6. `ai-pipeline/scripts/generate_thresholds.py` — threshold optimization
7. `ai-pipeline/pipeline/process.py` — CLI pipeline with hybrid classification
8. `ai-pipeline/runs/v5_finetune_demucs_v2/thresholds.json` — mixed thresholds
9. `ai-pipeline/runs/v5_finetune_demucs_v2/thresholds_demucs_only.json` — Demucs-only thresholds
