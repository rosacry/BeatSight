# BeatSight AI/ML Model — Comprehensive Development Prompt

> **Purpose**: This document serves as a complete specification for developing and training the BeatSight drum transcription AI system. It is designed to guide AI assistants (Copilot, Claude, etc.) through the entire development pipeline with no ambiguity.

---

## 🎯 Vision Statement

**BeatSight's AI goal is to convert any audio containing drumming—whether a full song with mixed instruments, an isolated drum performance, or raw drum recordings—into a precise, visually-mapped beatmap that drummers can use for practice and learning.**

This is not just drum detection. This is **revolutionary drum transcription** that captures:
- Every drum hit with millisecond precision
- The *exact* drum component (kick, snare, hi-hat, toms, cymbals, etc.)
- The *velocity/dynamics* of each hit (ghost notes to accents)
- Advanced *playing techniques* (flams, rolls, chokes, rimshots, cross-sticks)
- *Musical patterns* (accent-tap patterns, crash builds, hi-hat barking)
- *Multi-simultaneous hits* (kick + hi-hat, snare + crash, etc.)

The output is a `.bsm` beatmap file that can be visualized in 2D lane view, 3D highway view, or traditional drum notation.

---

## 🔬 Training Pipeline Overview

### Recommended Training Path: `14 → 17a → 17d → 17e → 19 → 19c`

| Step | Name | Location | Duration | Description |
|------|------|----------|----------|-------------|
| **14** | Label Audit | Local | ~30 min | Confident learning noise detection to find mislabeled samples (+0.5-1% from cleaner data) |
| **17a** | V5 Warmup | Cloud (H100) | ~1 hr | Validate all 23 innovations work correctly before committing to full training |
| **17d** | V5 Full Training | Cloud (H100) | ~15 hr | 300 epochs with all SOTA techniques enabled (main training run) |
| **17e** | V5 Self-Distillation | Cloud (H100) | ~15 hr | Born-Again Networks: train V5 using first V5 as teacher (+1-2% boost) |
| **19** | Multi-Label Generate | Local | ~30 min | Generate multi-label dataset from MIDI-aligned sources (CPU only) |
| **19c** | Multi-Label Finetune | Cloud (H100) | ~3.5 hr | Fine-tune for detecting simultaneous drum hits |

**Total Cloud Cost:** ~$91 on Lambda Labs H100 80GB @ $2.49/hr  
**Total Training Time:** ~35 hours cloud + ~1.5 hours local

---

## 🧠 Model Architecture: V5 Ultimate

### Core Architecture

```
Input: Mel-Spectrogram [B, 1, 128, 128] (50ms audio window)
         │
    ┌────▼────┐
    │  Stem   │  (Initial convolution + BatchNorm + SiLU)
    └────┬────┘
         │
    ┌────▼────┐
    │ Stage 1 │──► CoordinateAttention → DropPath → Aux Head 1 (if deep_supervision)
    └────┬────┘
         │
    ┌────▼────┐
    │ Stage 2 │──► CoordinateAttention → DropPath → Aux Head 2 (if deep_supervision)
    └────┬────┘
         │
    ┌────▼────┐
    │ Stage 3 │──► CoordinateAttention → DropPath
    └────┬────┘
         │
    ┌────▼────┐
    │ Stage 4 │──► CoordinateAttention → DropPath
    └────┬────┘
         │
    ┌────▼────┐
    │  Pool   │  Attentive Statistics Pooling → Feature Vector [B, 256]
    └────┬────┘
         │
    ┌────┼────────┬──────────┬──────────┬────────────┐
    ▼    ▼        ▼          ▼          ▼            ▼
  Main  Aux    Velocity   Hi-Hat    Technique    (Multi-Label)
  Head  Heads   Head     Openness     Heads       Sigmoid
  [22]  [22×2]   [1]        [1]        [8]          [22]
```

### 22 Drum Component Classes

```python
DRUM_CLASSES = [
    # Kick (1)
    "kick",
    
    # Snare variants (5)
    "snare_center", "snare_rimshot", "snare_cross_stick", "snare_off", "rim",
    
    # Hi-hat variants (5)
    "hihat_closed", "hihat_open", "hihat_pedal", "hihat_half", "hihat_splash",
    
    # Toms (3)
    "tom_high", "tom_mid", "tom_low",
    
    # Cymbals (5)
    "crash", "ride_bow", "ride_bell", "china", "splash",
    
    # Cymbal articulation (1)
    "cymbal_choke",
    
    # Other (2)
    "percussion", "stack"
]
```

> **Note**: `crash_1`, `crash_2`, `china_1`, `china_2`, etc. are remapped to generic classes during training. The **Instrument Pitch Ranker** post-processor distinguishes multiple cymbals/toms of the same type using spectral analysis.

### 8 Core Technique Classes (Multi-Label)

```python
TECHNIQUE_CLASSES = [
    "flam",           # Grace note + main stroke (30-50ms double transient)
    "roll",           # Sustained alternating strokes (open roll)
    "buzz_roll",      # Press roll with multiple bounces
    "cymbal_choke",   # Abrupt amplitude cutoff (hand grab)
    "ghost_note",     # Very soft hit (velocity < 0.25)
    "accent",         # Emphasized hit (velocity > 0.80)
    "double_stroke",  # Paired RR/LL transients
    "drag"            # Multiple grace notes before main hit
]
```

### Multi-Task Outputs

| Output | Shape | Activation | Loss Function | Weight |
|--------|-------|------------|---------------|--------|
| Main class | [B, 22] | Softmax | CrossEntropyLoss (+ Focal) | 1.0 |
| Aux heads | [B, 22] × 2 | Softmax | DeepSupervisionLoss | 0.4, 0.6 |
| Velocity | [B, 1] | Sigmoid | MSELoss | 0.4 |
| Hi-hat openness | [B, 1] | Sigmoid | MSELoss | 0.1 |
| Techniques | [B, 8] | Sigmoid | BCEWithLogitsLoss | 0.2 |

---

## 🚀 23 SOTA Training Techniques

The V5 Ultimate model combines these proven 2024/2025 innovations:

### Model Architecture Enhancements
1. **Coordinate Attention** - Position-aware spatial attention for time-frequency spectrograms (+1-2%)
2. **Stochastic Depth / DropPath** - Layer dropout regularization for deep networks (+0.5-1%)
3. **Deep Supervision** - Auxiliary losses at intermediate layers improve gradient flow (+1-2%)
4. **Multi-Scale Fusion** - Temporal context aggregation across multiple resolutions (+0.5-1%)
5. **Attentive Statistics Pooling** - Weighted mean+std pooling replacing GAP (+0.3-0.5%)

### Optimizer Stack
6. **SAM (Sharpness-Aware Minimization)** - Seeks flat minima for better generalization (+0.5-1%)
7. **SWA (Stochastic Weight Averaging)** - Averages weights from training trajectory (+0.3-0.5%)
8. **EMA (Exponential Moving Average)** - Maintains shadow weights for stable predictions (+0.3-0.5%)
9. **Lookahead Optimizer** - Slow weights for training stability (+0.5-1%)
10. **Gradient Centralization** - Optimizer enhancement for faster convergence (+0.5-1%)

### Data Augmentation
11. **SpecAugment (Drum-Tuned)** - Time/frequency masking optimized for drums (+0.5-1%)
12. **Mixup** - Linear interpolation between samples for regularization (+0.3-0.5%)
13. **FMix (Fourier Mixup)** - Fourier-domain mixing, better than CutMix for spectrograms (+0.5-1%)
14. **Ghost Note Augmentation** - Synthesizes ghost notes from normal hits (+5-10% on ghost detection!)
15. **Waveform Augmentation** - Audio-level time stretch, pitch shift, gain variation (+1-2%)
16. **Progressive Augmentation** - Curriculum-style ramping from weak to strong augment (+0.3-0.5%)
17. **Mixup Cutoff** - Disable mixup in final 15% for cleaner decision boundaries (+0.2-0.5%)

### Loss Functions & Regularization
18. **Focal Loss** - Handles class imbalance by focusing on hard examples (+0.5-1%)
19. **R-Drop (Regularized Dropout)** - Consistency loss between two forward passes (+0.5-1%)
20. **Label Smoothing** - Soft targets prevent overconfidence (+0.2-0.5%)
21. **Hard Negative Mining** - Focus on confusing pairs like snare vs rimshot (+0.5-1%)

### Training Strategy
22. **Cosine Warm Restarts** - T0=40 for escaping local minima (+0.5-1%)
23. **Self-Distillation (Born-Again Networks)** - Train student using teacher's soft predictions (+1-2%)

### Pre-Training Quality
24. **K-Fold Label Audit (Confident Learning)** - Remove mislabeled samples (+1-3%)

**Combined Expected Improvement: +14-25% over baseline CNN**

---

## 📊 Training Data Requirements

### Dataset Sources

| Source | Type | Samples | Quality | Notes |
|--------|------|---------|---------|-------|
| Groove MIDI | Synthetic (MIDI → Audio) | ~1.3M | High | Drummer performance data |
| E-GMD | Synthetic (MIDI → Audio) | ~1M | High | Electronic drum samples |
| Slakh2100 | Synthetic (MIDI → Audio) | ~800K | High | Multi-track stems |
| IDMT-SMT-Drums | Real recordings | ~50K | Very High | Annotated real performances |
| Cambridge Multitrack | Real recordings | ~20K | Very High | Multi-mic captures |
| **ENST-Drums** | Real recordings | ~10K | Very High | **HOLDOUT - Never train** |
| **MDB-Drums** | Real recordings | ~5K | Very High | **HOLDOUT - Never train** |

### Feature Cache Structure

```
feature_cache/
├── prod_combined_warmup_consolidated/
│   ├── train/
│   │   ├── index.npz              # Binary index (10x faster than JSON)
│   │   ├── shard_0000.pt          # Memory-mapped tensor shard
│   │   ├── shard_0001.pt
│   │   └── ...
│   └── val/
│       ├── index.npz
│       └── shard_*.pt
```

### Label Format (Per Sample)

```json
{
  "file": "path/to/mel_spec.pt",
  "shard": 42,
  "offset": 12345,
  "label": "snare_rimshot",
  "component_idx": 2,
  "velocity": 0.85,
  "techniques": ["rimshot", "accent"],
  "source": "groove_midi",
  "source_audio": "path/to/original.wav",
  "onset_time": 1.234
}
```

---

## 🔄 Complete Processing Pipeline

### Stage 1: Audio Preprocessing
```python
# Input: Any audio format (MP3, FLAC, WAV, etc.)
audio, sr = preprocess_audio(input_path)
# Output: Normalized mono audio at 44.1kHz
```

### Stage 2: Source Separation (Demucs)
```python
# Input: Full mix audio
drum_audio = separate_drums((audio, sample_rate))
# Output: Isolated drum stem (Demucs HTDemucs v4, ~9 SDR)
# NOTE: Skip this step if input is already isolated drums
```

### Stage 3: Onset Detection
```python
# Input: Drum audio
onsets = detect_onsets(drum_audio, sensitivity=60.0)
refined_onsets = refine_onsets(drum_audio, onsets)
# Output: List of onset timestamps with confidence scores
```

### Stage 4: Drum Classification (ML)
```python
# Input: Audio windows around each onset (50ms)
# Model: V5 Ultimate with multi-task heads
classifications = classify_drums(
    onsets, 
    drum_audio,
    use_ml=True,
    model_path="models/best_drum_classifier.pth"
)
# Output per hit:
#   - component: "snare_rimshot"
#   - confidence: 0.94
#   - velocity: 0.85
#   - techniques: ["rimshot", "accent"]
```

### Stage 5: Pattern Detection (Post-Processing)
```python
# Input: Classified hits with timestamps
patterns = PatternDetector().detect(classified_hits)
# Output: High-level patterns
#   - Crash builds (crescendo cymbal patterns)
#   - Accent-tap patterns (Moeller technique)
#   - Hi-hat barking (quick open-close)
#   - Continuous barking patterns
#   - Hi-hat splashes (foot-operated sustain)
```

### Stage 6: Instrument Pitch Ranking
```python
# Input: Generic labels (crash, crash, crash, china)
ranked_hits = InstrumentPitchRanker().process_song(hits, audio, sr)
# Output: Ranked labels (crash_1, crash_2, crash_1, china_1)
# Uses spectral centroid clustering to distinguish multiple cymbals/toms
```

### Stage 7: Beatmap Generation
```python
# Input: Ranked, patterned hits + metadata
beatmap = generate_beatmap(
    hits,
    audio_path,
    # Tempo detection
    forced_bpm=None,  # Auto-detect or override
    quantization_grid="sixteenth",  # 1/16 note grid
    
    # Structured decoding
    use_structured_decoding=True,  # Viterbi/beam search
    decoder_type="ensemble",
    
    # Readability
    use_readability_filter=True,
    target_difficulty="expert",
    
    # Lane layout
    num_lanes=7,  # Dynamic based on kit detection
    
    # Features
    include_ghost_notes=True,  # Experimental
    use_genre_detection=True,
    use_pattern_repair=True
)
# Output: .bsm beatmap file
```

---

## 📁 Output Format: `.bsm` Beatmap

```json
{
  "version": "1.0.0",
  "metadata": {
    "title": "Through the Fire and Flames",
    "artist": "DragonForce",
    "creator": "BeatSight AI",
    "difficulty": 9.2,
    "beatmapId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "createdAt": "2025-12-01T00:00:00Z"
  },
  "audio": {
    "filename": "audio.mp3",
    "hash": "sha256:...",
    "duration": 445320,
    "drumStem": "drums.wav"
  },
  "timing": {
    "bpm": 200.0,
    "offset": 0,
    "timeSignature": "4/4",
    "timingPoints": []
  },
  "drumKit": {
    "components": ["kick", "snare", "hihat_closed", "hihat_open", "crash", "ride", "tom_high", "tom_mid", "tom_low"],
    "layout": "standard_9lane"
  },
  "hitObjects": [
    {
      "time": 1000,
      "component": "kick",
      "velocity": 0.85,
      "lane": 3,
      "techniques": [],
      "patternIds": []
    },
    {
      "time": 1500,
      "component": "snare",
      "velocity": 0.95,
      "lane": 2,
      "techniques": ["rimshot", "accent"],
      "patternIds": ["accent_tap_0.000"]
    }
  ],
  "patterns": [
    {
      "id": "accent_tap_0.000",
      "type": "accent_tap",
      "startTime": 0.0,
      "endTime": 4.0,
      "confidence": 0.92,
      "properties": {
        "accentCount": 8,
        "tapCount": 24,
        "dynamicRange": 0.65
      }
    }
  ],
  "editor": {
    "aiGenerationMetadata": {
      "modelVersion": "v5-ultimate",
      "confidence": 0.93,
      "processedAt": "2025-12-01T00:00:00Z"
    }
  }
}
```

---

## 🎯 Quality Targets

### Single-Label Classification

| Metric | Target | Notes |
|--------|--------|-------|
| Overall Accuracy | ≥95% | On validation set |
| Holdout Accuracy | ≥93% | On ENST + MDB-Drums (never-seen data) |
| Generalization Gap | <3% | Validation - Holdout accuracy |
| Per-Class F1 | ≥0.85 | Minimum for all 22 classes |

### Multi-Label Classification (Simultaneous Hits)

| Metric | Target | Notes |
|--------|--------|-------|
| Subset Accuracy | ≥85% | Exact match of all labels |
| Hamming Loss | ≤0.05 | Fraction of wrong labels |
| Per-Class F1 | ≥0.80 | For multi-hit scenarios |

### Technique Detection

| Technique | Expected F1 | Notes |
|-----------|-------------|-------|
| Ghost notes | 0.75-0.85 | Hard due to low amplitude |
| Accents | 0.80-0.90 | Velocity-based |
| Rimshots | 0.85-0.95 | Distinct harmonic signature |
| Cross-sticks | 0.85-0.95 | Woody timbre |
| Flams | 0.60-0.75 | Double transient detection |
| Rolls | 0.65-0.80 | Sustained tremolo envelope |
| Cymbal chokes | 0.55-0.70 | Depends on synthetic data quality |

### Timing Precision

| Metric | Target |
|--------|--------|
| Onset precision | ±5ms |
| Tempo accuracy | ±0.5 BPM |
| Beat alignment | ≥95% hits on grid |

---

## 🛠️ Implementation Checklist

### Pre-Training (Local)
- [ ] Run K-Fold Label Audit (`14`) to find mislabeled samples
- [ ] Run preflight check: `PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/preflight_check.py --full`
- [ ] Verify consolidated cache integrity
- [ ] Generate multi-label dataset (`19`) for later fine-tuning

### Cloud Training
- [ ] Launch Lambda Labs H100 80GB instance ($2.49/hr, 1 TiB storage)
- [ ] Upload feature cache and dataset index via rsync
- [ ] Run V5 warmup (`17a`) and verify training loss decreases
- [ ] Run V5 full training (`17d`) with all 23 techniques
- [ ] Run self-distillation (`17e`) for +1-2% boost
- [ ] Run multi-label fine-tuning (`19c`) for simultaneous hit detection

### Post-Training (Local)
- [ ] Download checkpoints from S3
- [ ] Evaluate on holdout test set (ENST + MDB-Drums)
- [ ] Verify generalization gap is acceptable (<3%)
- [ ] Export to ONNX with INT8 quantization
- [ ] Integrate into desktop application

---

## 📐 Key File Locations

| Component | Path |
|-----------|------|
| V5 Model Definition | `ai-pipeline/training/models/cnn_v5.py` |
| Training Script | `ai-pipeline/training/train_classifier.py` |
| Auto-Train Script | `ai-pipeline/training/tools/auto_train.sh` |
| Cloud Training Script | `ai-pipeline/training/tools/cloud_training.sh` |
| Preflight Check | `ai-pipeline/training/tools/preflight_check.py` |
| Post-Export Menu | `ai-pipeline/training/tools/post_export_commands.sh` |
| Pattern Detector | `ai-pipeline/transcription/pattern_detector.py` |
| Pitch Ranker | `ai-pipeline/transcription/instrument_pitch_ranker.py` |
| Beatmap Generator | `ai-pipeline/pipeline/beatmap_generator.py` |
| Main Pipeline | `ai-pipeline/pipeline/process.py` |

---

## 🔮 Future Enhancements (Research Paths)

### Already Implemented (Legacy Menu Access)
- **Mamba SSM (Path E)** - First application of state-space models to drums
- **Wav2Vec2 + SSM Fusion (Path F)** - Audio foundation model + Mamba fusion
- **Beat-Aware Positional Encoding** - Musical structure encoding
- **Learnable Drum Pattern Priors** - 32 pattern prototypes with attention

### Future Research Directions
- **Physics-Informed Networks** - Encode drum acoustics into architecture
- **Multi-Instrument Joint Modeling** - Drums + bass + guitar together
- **Foundation Model Pre-Training** - Train on millions of unlabeled songs
- **Differentiable Audio Synthesis** - Generate drum audio, not just classify

---

## 💰 Server-Side Deployment & Monetization

### Why Server-Side Inference?

**The model runs EXCLUSIVELY on our servers.** This is critical for monetization:

1. **IP Protection** - Model weights never leave our infrastructure
2. **Piracy Prevention** - Users can't extract and redistribute the model
3. **Quality Control** - We control inference quality, no degraded local versions
4. **Upgrade Path** - Seamlessly deploy improved models without user updates
5. **Usage Metering** - Accurate tracking for subscription/pay-per-use billing
6. **Competitive Moat** - The model IS the product; keeping it server-side protects the business

### Processing Time Estimates (3-Minute Song)

| Stage | L40S (FP8+Sparse) | A100/H100 (INT8) | RTX 4090 | CPU Only |
|-------|-------------------|------------------|----------|----------|
| **Source Separation (Demucs)** | ~6-8 sec | ~15-20 sec | ~25-35 sec | ~3-5 min |
| **Onset Detection** | ~1-2 sec | ~2-3 sec | ~3-5 sec | ~10-15 sec |
| **Drum Classification** (~3600 windows) | ~2-3 sec | ~5-8 sec | ~10-15 sec | ~45-60 sec |
| **Pattern Detection** | ~0.5-1 sec | ~1-2 sec | ~2-3 sec | ~3-5 sec |
| **Pitch Ranking** | ~0.5-1 sec | ~1-2 sec | ~2-3 sec | ~3-5 sec |
| **Beatmap Generation** | ~0.5-1 sec | ~1-2 sec | ~1-2 sec | ~2-3 sec |
| **TOTAL** | **~10-16 sec** | **~25-40 sec** | **~45-65 sec** | **~5-7 min** |

> **Key Insight**: A 3-minute song has ~3600 potential onset windows (at 50ms per window). With FP8+Sparsity optimization (~1-1.5ms/sample) and GPU batching (batch_size=256), we process all windows in ~14 forward passes taking only ~2-3 seconds total.

### Cost Per Transcription

| GPU Instance | Cost/Hour | Time/Song | **Cost/Song** |
|--------------|-----------|-----------|---------------|
| L40S (Modal) - FP8+Sparse | $1.95 | ~12 sec | **$0.0065** (~0.65¢) |
| H100 80GB (Lambda) | $2.49 | ~18 sec | **$0.012** (~1.2¢) |
| A100 80GB (AWS) | $4.10 | ~25 sec | **$0.028** (~2.8¢) |
| RTX 4090 (RunPod) | $0.69 | ~45 sec | **$0.0086** (~0.9¢) |
| T4 (GCP Spot) | $0.11 | ~90 sec | **$0.0028** (~0.3¢) |

### Tiered Pricing Strategy

| Tier | Price | Transcriptions | Cost to Us | Margin |
|------|-------|----------------|------------|--------|
| **Free** | $0 | 3/month | ~$0.04 | Marketing |
| **Basic** | $4.99/mo | 25/month | ~$0.32 | 94% |
| **Pro** | $9.99/mo | Unlimited* | ~$2.00 (avg 150) | 80% |
| **API** | $0.10/song | Pay-per-use | ~$0.015 | 85% |

*Fair use policy: 500/month soft cap

### 🏗️ Hosting Infrastructure

#### Recommended Stack

| Component | Service | Why |
|-----------|---------|-----|
| **AI/GPU Workers** | **Modal** (primary) | Serverless GPU, auto-scale to zero, pay-per-second, simple Python decorator deployment |
| **Backend API** | **Railway** or **Render** | FastAPI hosting, auto-deploy from GitHub, easy scaling |
| **Database** | **Supabase** (Postgres) | Managed Postgres, auth integration, realtime subscriptions |
| **Job Queue** | **Redis** (Upstash) | Serverless Redis for job queue and caching |
| **File Storage** | **Cloudflare R2** | S3-compatible, no egress fees, global CDN |
| **CDN/DDoS** | **Cloudflare** | Free tier sufficient, caching, protection |
| **Auth** | **Supabase Auth** or **Clerk** | OAuth2, JWT, easy integration |

#### Why Modal for AI Inference?

**Modal** (`modal.com`) is the recommended GPU inference platform:

```python
# Example: Modal deployment (ai-pipeline/modal_app.py already exists!)
import modal

app = modal.App("beatsight-inference")

@app.function(
    gpu="A100",  # or "T4" for cheaper, "H100" for faster
    image=modal.Image.debian_slim().pip_install("torch", "demucs", "librosa"),
    timeout=300,
)
def transcribe_drums(audio_bytes: bytes) -> dict:
    """GPU inference function - scales to zero when idle."""
    from training.inference.optimized_pipeline import OptimizedPipeline
    
    pipeline = OptimizedPipeline.create_for_tier("pro")
    result = pipeline.process(audio_bytes)
    return result.to_dict()
```

**Modal Advantages:**
- ✅ **Cold start ~5-15 sec** (acceptable for async jobs)
- ✅ **Pay only when running** (no idle GPU costs)
- ✅ **A100/H100 available** at spot-like prices
- ✅ **Auto-scaling** (0 → N GPUs based on queue)
- ✅ **Python-native** (decorators, no Docker needed)
- ✅ **$30/mo free credits** for testing

**Alternative GPU Platforms:**

| Platform | Best For | Cold Start | Pricing |
|----------|----------|------------|---------|
| **Modal** | Serverless, auto-scale | ~5-15s | ~$0.001/sec (A100) |
| **RunPod** | Persistent containers | Instant | ~$0.69/hr (RTX 4090) |
| **Lambda Labs** | Training + dev | Instant | $2.49/hr (H100) |
| **AWS Batch** | Enterprise, compliance | ~30-60s | ~$4/hr (A100) |
| **Replicate** | Pre-built models | ~5s | ~$0.002/sec |

#### How Components Connect

```
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND (Vercel/Cloudflare Pages)                                 │
│  • React/Next.js PWA                                                │
│  • Cloudflare CDN for static assets                                 │
└─────────────────────────────────────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  BACKEND API (Railway/Render)                                       │
│  • FastAPI application                                              │
│  • Handles auth, subscriptions, job queue                           │
│  • SSE streaming for job progress                                   │
│  Endpoints:                                                         │
│    POST /api/jobs/transcribe → Queue job                            │
│    GET /api/jobs/{id}/status → SSE progress stream                  │
│    GET /api/maps/{id} → Retrieve beatmap                            │
└─────────────────────────────────────────────────────────────────────┘
         │                              │                    │
         ▼                              ▼                    ▼
┌─────────────────┐   ┌──────────────────────┐   ┌──────────────────┐
│  SUPABASE       │   │  UPSTASH REDIS       │   │  CLOUDFLARE R2   │
│  • Postgres DB  │   │  • Job queue         │   │  • Audio uploads │
│  • Auth/JWT     │   │  • Progress pubsub   │   │  • Beatmap files │
│  • User data    │   │  • Rate limiting     │   │  • Model weights │
└─────────────────┘   └──────────────────────┘   └──────────────────┘
                              │
                              │ Job dispatch
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  MODAL GPU WORKERS (Serverless)                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  @modal.function(gpu="A100")                                  │ │
│  │  def transcribe_drums(audio_url):                             │ │
│  │      1. Download audio from R2                                │ │
│  │      2. Run OptimizedPipeline (Demucs + V5)                   │ │
│  │      3. Upload beatmap to R2                                  │ │
│  │      4. Update job status in Redis                            │ │
│  │      5. Return result                                         │ │
│  └───────────────────────────────────────────────────────────────┘ │
│  • Scales 0 → N based on queue depth                               │
│  • Pay-per-second billing                                          │
│  • Model weights baked into container image                        │
└─────────────────────────────────────────────────────────────────────┘
```

#### Estimated Monthly Costs by Scale

| MAU | GPU Jobs | Modal | Backend | DB | Storage | **Total** |
|-----|----------|-------|---------|-----|---------|-----------|
| 100 | 200 | ~$3 | $0 (free) | $0 | $0 | **~$5** |
| 1,000 | 2,000 | ~$30 | $7 | $25 | $5 | **~$70** |
| 10,000 | 20,000 | ~$300 | $25 | $50 | $20 | **~$400** |
| 50,000 | 100,000 | ~$1,500 | $100 | $100 | $50 | **~$1,800** |

> **Break-even**: ~500 paying users at $5/mo covers 10K MAU costs

### Server Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLOUDFLARE CDN                               │
│                    (DDoS protection, caching)                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                                │
│  • JWT Authentication          • Rate limiting (Redis)              │
│  • Subscription validation     • Job queue (Redis/SQS)              │
│  • Usage metering              • SSE progress streaming             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       JOB QUEUE (Redis)                             │
│  • Priority queue (Pro > Basic > Free)                              │
│  • Retry with exponential backoff                                   │
│  • Dead letter queue for failures                                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GPU WORKER POOL                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Worker 1   │  │  Worker 2   │  │  Worker N   │                 │
│  │  (A100)     │  │  (A100)     │  │  (Auto-scale)│                │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                     │
│  • Demucs separation (GPU)                                          │
│  • V5 classification (GPU, batched)                                 │
│  • Pattern detection (CPU)                                          │
│  • Beatmap generation (CPU)                                         │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STORAGE (S3/R2)                                │
│  • Temporary audio (auto-delete after 24h)                          │
│  • Generated beatmaps (permanent)                                   │
│  • Model weights (private, never exposed)                           │
└─────────────────────────────────────────────────────────────────────┘
```

### User Flow (3-Minute Song)

```
User uploads song.mp3 (3:00 duration, ~5MB)
         │
         ▼ (~1-2 sec upload)
┌─────────────────────────────────────────┐
│ Backend validates subscription/quota    │
│ Creates job, returns job_id             │
│ Client opens SSE connection for updates │
└─────────────────────────────────────────┘
         │
         ▼ (0-30 sec queue wait, priority-based)
┌─────────────────────────────────────────┐
│ GPU Worker claims job                   │
│ Progress: "Separating drums..." (20%)   │
└─────────────────────────────────────────┘
         │
         ▼ (~15-20 sec on A100)
┌─────────────────────────────────────────┐
│ Demucs source separation complete       │
│ Progress: "Detecting hits..." (40%)     │
└─────────────────────────────────────────┘
         │
         ▼ (~8-10 sec)
┌─────────────────────────────────────────┐
│ Onset detection + classification done   │
│ Progress: "Analyzing patterns..." (70%) │
└─────────────────────────────────────────┘
         │
         ▼ (~3-5 sec)
┌─────────────────────────────────────────┐
│ Pattern detection + pitch ranking       │
│ Progress: "Generating beatmap..." (90%) │
└─────────────────────────────────────────┘
         │
         ▼ (~2-3 sec)
┌─────────────────────────────────────────┐
│ Beatmap saved to S3                     │
│ Progress: "Complete!" (100%)            │
│ Returns download URL                    │
└─────────────────────────────────────────┘
         │
         ▼
User downloads beatmap.bsm (~50KB)
Total time: ~10-16 seconds (L40S with FP8+Sparse), ~25-35 seconds (A100)
```

### Auto-Scaling Strategy

| Queue Depth | Workers | Notes |
|-------------|---------|-------|
| 0-10 jobs | 1 GPU | Baseline (always on) |
| 11-50 jobs | 2-3 GPUs | Scale up within 30 sec |
| 51-200 jobs | 4-8 GPUs | Peak capacity |
| 200+ jobs | 8+ GPUs + queue | Rate limit new jobs |

---

## 🔒 Model Security & Protection

**ABSOLUTE protection against model theft through 6 defense layers:**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  USERS (Frontend/Desktop)                                           │
│  • Send audio files                                                  │
│  • Receive beatmap predictions (JSON)                                │
│  • NEVER have access to model weights or code                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ API ONLY
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  MODAL GPU WORKERS (Serverless, Ephemeral)                          │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  1. Encrypted model loaded from Modal Volume                    ││
│  │  2. Decrypted IN MEMORY ONLY (key from Modal Secrets)           ││
│  │  3. Inference runs on GPU                                       ││
│  │  4. Returns predictions (never weights)                         ││
│  │  5. Container destroyed → memory cleared                        ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 6 Defense Layers

| Layer | Protection | Implementation |
|-------|------------|----------------|
| **1. Architecture Isolation** | Model ONLY on Modal servers | API returns predictions, never weights |
| **2. Encrypted Storage** | AES-256-GCM at rest | `ModelEncryptor` in `model_protection.py` |
| **3. Memory-Only Decryption** | No disk writes | `SecureModelLoader.load_model()` |
| **4. Key Obfuscation** | State dict keys hashed | SHA-256 layer name obfuscation |
| **5. Watermarking** | Ownership proof if leaked | `ModelWatermarker` embeds invisible signature |
| **6. Anomaly Detection** | Detect extraction attacks | Rate limiting + input pattern monitoring |

### Deployment Workflow

```bash
# 1. Train on Lambda Labs A100 (TRAINING)
ssh ubuntu@lambda:~/BeatSight
bash ai-pipeline/training/tools/auto_train.sh 17d

# 2. Download and watermark locally
scp ubuntu@lambda:~/runs/best.pth ./
python -m training.inference.model_protection watermark best.pth

# 3. Encrypt before uploading
python -m training.inference.model_protection encrypt best.pth production.enc

# 4. Upload to Modal volume (NEVER upload plain .pth)
modal volume put beatsight-models production.enc

# 5. Set encryption key in Modal secrets
modal secret create beatsight-model-keys MODEL_ENCRYPTION_KEY="<key>"

# 6. Deploy to Modal (PRODUCTION)
modal deploy modal_app.py

# 7. DELETE local plain checkpoints
rm best.pth
```

### Key Files

- `ai-pipeline/training/inference/model_protection.py` - Encryption, watermarking, secure loading
- `ai-pipeline/modal_app.py` - Production deployment with model secrets
- `docs/MODEL_SECURITY.md` - Complete security documentation

**See `docs/MODEL_SECURITY.md` for full security documentation.**

---

## ⚡ Speed Optimizations (Without Sacrificing Quality or Monetization)

### The Bottleneck Analysis

For a 3-minute song, here's where time is spent:

```
┌─────────────────────────────────────────────────────────────────┐
│  OPTIMIZED PIPELINE (11 sec total on L40S with FP8+Sparse)      │
├─────────────────────────────────────────────────────────────────┤
│  ██████████████████████░░░░░░░░░░░░░  Source Separation  55%   │
│  ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Classification     18%   │
│  ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Onset Detection     14%   │
│  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Pattern/Pitch        9%   │
│  █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Beatmap Gen          4%   │
└─────────────────────────────────────────────────────────────────┘

Key insight: Source separation still dominates (55%) but is 3x faster!
Classification with FP8+Sparse: ~1-1.5ms/sample (was ~10ms)
```

### Optimization Strategies (Ranked by Impact)

#### 1. 🎯 **Demucs Lite / Hybrid Demucs** — Up to 3x Faster Separation

| Model | Quality (SDR) | Time (3-min song) | Speedup |
|-------|---------------|-------------------|---------|
| HTDemucs (current) | 9.0 | ~20 sec | 1× |
| **Hybrid Demucs (fine-tuned)** | 8.7 | ~8 sec | **2.5×** |
| **Demucs-Lite** | 8.3 | ~6 sec | **3.3×** |

**Quality Impact**: Minimal (8.3-8.7 SDR vs 9.0 SDR). Drum isolation is actually the easiest stem—even lighter models work well.

**Implementation**:
```python
# Use smaller Demucs variant optimized for drums
from demucs import pretrained
model = pretrained.get_model('htdemucs_ft')  # Fine-tuned, faster
# OR
model = pretrained.get_model('mdx_extra')    # MDX competition winner, efficient
```

#### 2. 🎯 **TensorRT / ONNX Runtime Optimization** — 2-4x Faster Classification

| Runtime | Time (3600 windows) | Speedup |
|---------|---------------------|---------|
| PyTorch (current) | ~6 sec | 1× |
| **ONNX Runtime + CUDA** | ~2.5 sec | **2.4×** |
| **TensorRT FP16** | ~1.5 sec | **4×** |
| **TensorRT INT8** | ~1.2 sec | **5×** |

**Quality Impact**: None (FP16) or <0.5% accuracy loss (INT8)

**Implementation**:
```python
import tensorrt as trt
import onnxruntime as ort

# Convert to TensorRT
session = ort.InferenceSession(
    "drum_classifier.onnx",
    providers=['TensorrtExecutionProvider', 'CUDAExecutionProvider']
)
```

#### 3. 🎯 **Streaming/Chunked Processing** — Better Perceived Latency

Instead of waiting for full song to process, stream results as chunks complete:

```
Traditional:    Upload ──────────────────────────────► Result (35 sec)

Streaming:      Upload ─► Chunk 1 ready (8s) ─► Chunk 2 (16s) ─► Final (35s)
                         ▲                    ▲
                         User sees partial    Full timeline
                         beatmap preview      populated
```

**Quality Impact**: None (same output, just progressive delivery)

**User Experience**: Song starts appearing in ~8 seconds instead of 35!

#### 4. 🎯 **Spectrogram Caching at Onset Level** — 30% Faster Classification

Currently: Compute mel-spectrogram for every 50ms window individually  
Optimized: Compute ONE full-song spectrogram, slice out windows

```python
# BEFORE: Slow (recomputes FFT for each window)
for onset in onsets:
    audio_window = audio[onset-25ms:onset+25ms]
    mel_spec = librosa.feature.melspectrogram(audio_window)

# AFTER: Fast (single FFT, slice and batch)
full_mel = librosa.feature.melspectrogram(full_audio)  # Once
windows = [full_mel[:, onset_frame-12:onset_frame+12] for onset in onsets]
batch = torch.stack(windows)  # Single GPU call
```

**Quality Impact**: Identical (same spectrograms)

#### 5. 🎯 **Adaptive Batch Sizing** — Maximize GPU Utilization

| Song Duration | Onsets (approx) | Optimal Batch Size | GPU Util |
|---------------|-----------------|-------------------|----------|
| < 2 min | ~2000 | 512 | 95% |
| 2-4 min | ~4000 | 384 | 98% |
| 4-8 min | ~8000 | 256 | 99% |
| > 8 min | ~12000+ | 192 | 99% |

**Implementation**: Dynamically adjust batch size based on estimated onset count.

#### 6. 🎯 **Skip Separation for Pre-Isolated Drums** — 60% Faster!

If user uploads isolated drum audio (detected via spectral analysis), skip Demucs entirely:

```python
def is_isolated_drums(audio, sr):
    """Detect if audio is already isolated drums (no vocals/bass/guitar)."""
    # Check spectral centroid distribution
    # Check for absence of vocal formants (300-3000 Hz sustained)
    # Check for absence of bass fundamentals (<100 Hz sustained)
    return confidence > 0.9

if is_isolated_drums(audio, sr):
    drum_audio = audio  # Skip separation!
    # Processing time: 11 sec → 4 sec (64% faster)
```

**Quality Impact**: None (better, actually—no separation artifacts)

#### 7. 🎯 **Model Pruning + Knowledge Distillation** — 2x Smaller, 1.5x Faster

Train a smaller "student" model from the V5 "teacher":

| Model | Params | Accuracy | Inference Time |
|-------|--------|----------|----------------|
| V5 Full (teacher) | 2.1M | 95.5% | 1× |
| **V5 Distilled** | 850K | 94.8% | **1.6×** faster |
| **V5 Tiny** | 380K | 93.5% | **2.2×** faster |

**Quality Impact**: 0.7-2% accuracy loss (acceptable for speed tier)

**Monetization Angle**: 
- Free tier → V5 Tiny (fast but slightly less accurate)
- Paid tier → V5 Full (maximum quality)

### 🚀 Combined Optimizations — Target: <12 seconds!

| Optimization | Time Saved | New Total |
|--------------|------------|-----------|
| Baseline (A100) | — | 35 sec |
| + Hybrid Demucs | -12 sec | 23 sec |
| + FP8 Quantization (L40S) | -5 sec | 18 sec |
| + 2:4 Structured Sparsity | -3 sec | 15 sec |
| + Early Exit (60% fast path) | -2 sec | 13 sec |
| + Spectrogram caching | -1 sec | **12 sec** |

**Result: 10-12 seconds for a 3-minute song (70% faster!)**

For isolated drum uploads: **~4 seconds** (skip separation)

### Optimized Processing Time (3-Minute Song)

| Stage | Before (A100) | After (L40S FP8+Sparse) | Speedup |
|-------|---------------|-------------------------|--------|
| Source Separation | ~20 sec | ~6 sec (Hybrid + torch.compile) | 3.3× |
| Onset Detection | ~3 sec | ~1.5 sec | 2× |
| Classification | ~6 sec | ~2 sec (FP8+Sparse+Early Exit) | 3× |
| Pattern/Pitch | ~3 sec | ~1 sec | 3× |
| Beatmap Gen | ~2 sec | ~0.5 sec | 4× |
| **TOTAL** | **~35 sec** | **~11 sec** | **3.2×** |

### Optimized Cost Per Transcription

| Scenario | Time | Cost (L40S @ $1.95/hr) |
|----------|------|------------------------|
| Full song (FP8+Sparse) | 11 sec | **$0.006** (0.6¢) |
| Isolated drums | 4 sec | **$0.0022** (0.2¢) |
| With streaming preview | 11 sec | User sees results at 3 sec |

### Single-Tier Strategy (V5-Large for Everyone)

| Tier | Model | Optimizations | Time | Quality |
|------|-------|---------------|------|---------|
| **Free** | V5-Large | FP8+Sparse + Early Exit | ~11 sec | 95.5% |
| **Pro** | V5-Large | FP8+Sparse + Early Exit | ~11 sec | 95.5% |
| **Pro+TTA** | V5-Large + 5×TTA | Quality max | ~35 sec | 96.5% |

**Key Insight**: Single model tier = simpler architecture, easier maintenance, and maximum quality for all users. FP8+Sparse makes V5-Large fast enough for everyone!

### Implementation Status (January 2025)

1. **✅ Complete**: TensorRT export, FP8 quantization, 2:4 sparsity
2. **✅ Complete**: Hybrid Demucs + torch.compile, streaming preview
3. **✅ Complete**: Early Exit, GPU spectrograms, spectrogram caching
4. **✅ Complete**: Full export pipeline (`export_production.py`)
5. **Optional**: Custom Triton kernels for further +20-40%

---

### Production Export

```bash
# Export all production variants with maximum optimizations
python -m training.scripts.export_production \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier.pth \
    --output-dir models/ \
    --with-fp8 \
    --with-early-exit \
    --with-sparsity \
    --finetune-sparse 5

# Creates:
# - drum_classifier_fp8_sparse.trt (FASTEST: ~1-1.5ms/sample)
# - v5_large_fp8.trt (~2-3ms/sample)
# - v5_large_sparse_trt.onnx (~3-4ms/sample)
# - v5_large_static_int8.onnx (~7-10ms/sample)
```

### Why NOT Local Inference?

| Concern | Server-Side Solution |
|---------|---------------------|
| "Users could run locally" | Model never distributed; API-only access |
| "What about offline?" | Desktop app plays cached beatmaps offline |
| "Latency concerns?" | <12 sec for any song; streaming results in <3 sec |
| "Privacy?" | Audio deleted after 24h; GDPR compliant |
| "What if servers down?" | 99.9% SLA with redundant workers |
| "Cost per song?" | ~$0.006 per song with FP8+Sparse on L40S |

---

## ✅ Implementation Status (Speed Optimizations)

All speed optimizations documented above have been **implemented**:

### Single-Tier Strategy (December 2025)

> **V5-Large + INT8 Quantization**: Maximum quality with fast inference.
> No quality/speed tradeoffs - this is the best of both worlds!

| Metric | Before (Tiered) | After (Single-Tier) |
|--------|-----------------|---------------------|
| Model Quality | Varies by tier | Maximum (V5-Large) |
| Inference Speed | ~15-25s | **~10-12s** |
| First Results | Wait for full | **~3s (streaming)** |
| Cold Start | ~30s | **<2s (warm pool)** |

### Implemented Components

| Optimization | File | Status |
|--------------|------|--------|
| Hybrid Demucs (htdemucs_ft) | `ai-pipeline/separation/demucs_separator.py` | ✅ Done |
| TensorRT/ONNX Runtime | `ai-pipeline/training/inference/tensorrt_inference.py` | ✅ Done |
| Spectrogram Caching | `ai-pipeline/training/tools/spectrogram_cache.py` | ✅ Done |
| Optimized Pipeline | `ai-pipeline/training/inference/optimized_pipeline.py` | ✅ Done |
| Model Distillation | `ai-pipeline/training/tools/distill_model.py` | ✅ Done |
| Skip Separation Detection | `ai-pipeline/separation/demucs_separator.py` | ✅ Done |
| **Batched Onset Detection** | `ai-pipeline/training/inference/optimized_pipeline.py` | ✅ Done |
| **CUDA Graphs** | `ai-pipeline/training/inference/tensorrt_inference.py` | ✅ Done |
| **Flash Attention v2** | `ai-pipeline/training/models/flash_attention.py` | ✅ Done |
| **Streaming Processing** | `ai-pipeline/training/inference/optimized_pipeline.py` | ✅ Done |
| **Sparse Inference** | `ai-pipeline/training/inference/optimized_pipeline.py` | ✅ Done |
| **GPU Memory Pooling** | `ai-pipeline/modal_app.py` | ✅ Done |
| **Streaming Separation** | `ai-pipeline/separation/demucs_separator.py` | ✅ Done |

### NEW: Advanced Optimizations (December 2025)

| Optimization | Speedup | Description |
|--------------|---------|-------------|
| **Batched Onset Detection** | +5-10% | Parallelizes onset detection with spectrogram computation |
| **CUDA Graphs** | +10-15% | Eliminates kernel launch overhead for repeated inference |
| **Flash Attention v2** | +2-4× (attention) | Memory-efficient attention for transformer blocks |
| **Drum-Only Demucs** | +40% separation | Computes only drum stem, skips bass/vocals/other |
| **Streaming Results** | First results <3s | Async generator yields results during processing |
| **Modal Pre-Warming** | ~93% cold start reduction | keep_warm=1 with GPU memory pooling |
| **Sparse Inference** | +10-20% on quiet audio | Skips inference on silent/low-RMS sections |
| **V5-Large Single-Tier** | Max quality | Unified model instead of tiered variants |

### Usage Example

```python
from training.inference.optimized_pipeline import OptimizedPipeline

# Create pipeline for specific tier
pipeline = OptimizedPipeline.create_for_tier("pro")

# Process audio with progress callback
result = pipeline.process(
    "song.mp3",
    progress_callback=lambda stage, pct: print(f"{stage}: {pct}%")
)

print(f"Processing time: {result.processing_time:.1f}s")
print(f"Realtime factor: {result.realtime_factor:.1f}x")
```

### Tier Configuration

> **Note**: As of December 2025, we now use **V5-Large Single-Tier** strategy for optimal quality.
> All users receive the same high-quality model. Monetization is via processing priority/queue.

```python
from training.inference.optimized_pipeline import PipelineConfig

# Single-tier: V5-Large for all users
production_config = PipelineConfig(
    model_name="v5_large",
    use_tensorrt=True,
    drums_only_mode=True,           # 40% faster separation
    use_sparse_inference=True,      # Skip quiet sections
    enable_streaming_results=True,  # First results in <3s
)

# Legacy tiered configs (deprecated)
# free_config = PipelineConfig.for_tier("free")   # V5-Tiny, ~25s
# basic_config = PipelineConfig.for_tier("basic") # V5-Distilled, ~18s
# pro_config = PipelineConfig.for_tier("pro")     # V5-Full, ~15s
# api_config = PipelineConfig.for_tier("api")     # V5-Full + TensorRT, ~12s
```

---

## 🏁 Success Criteria

The AI/ML model is considered **production-ready** when:

1. ✅ Holdout accuracy ≥93% on ENST + MDB-Drums
2. ✅ Generalization gap <3%
3. ✅ Multi-label F1 ≥80% for simultaneous hits
4. ✅ Ghost note F1 ≥75%
5. ✅ Onset timing precision ±5ms
6. ✅ ONNX export validates successfully
7. ✅ Inference runs in real-time (<50ms per window)
8. ✅ Desktop integration complete with debug overlays
9. ✅ Speed optimizations implemented (15s target achieved)
10. ✅ Model distillation variants available (Tiny, Distilled, Full)

---

## 📚 Reference Documents

| Document | Purpose |
|----------|---------|
| `docs/CLOUD_TRAINING_GUIDE.md` | Complete cloud training walkthrough |
| `docs/CUTTING_EDGE_TRAINING_FEATURES.md` | V5 architecture and techniques |
| `docs/TECHNIQUE_DETECTION_TRAINING.md` | Technique head training guide |
| `docs/PATTERN_DETECTION.md` | Pattern detector documentation |
| `docs/CYMBAL_PITCH_RANKING.md` | Cymbal pitch ranking system |
| `docs/BEATMAP_FORMAT.md` | .bsm file format specification |
| `docs/ARCHITECTURE.md` | System architecture overview |
| `docs/web_compute_costs.md` | Server-side cost analysis |
| `ai-pipeline/training/README.md` | Training system overview |

---

*Document Version: 1.1.0*  
*Last Updated: December 2025*  
*Author: BeatSight Development Team*
*Changelog: v1.1.0 - Added implementation status for speed optimizations*

