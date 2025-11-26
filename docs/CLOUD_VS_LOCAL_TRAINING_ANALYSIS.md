# Cloud Computing vs Local Training Analysis for BeatSight

**Date:** November 26, 2025  
**Hardware Profile:** RTX 3080 Ti, Ryzen 9800X3D, 32GB DDR5-6000, Samsung 990 Pro 2TB NVMe  
**Dataset Size:** ~1TB (feature_cache + prod_combined_profile_run)

---

## Executive Summary

**Verdict: Keep training locally. Use cloud (Modal) only for production inference.**

Your hardware is already in the sweet spot for your model size. The path to "revolutionary" is through better data, smarter architecture, and rigorous evaluation—not throwing H100s at a 385K parameter CNN.

---

## Your Current Hardware Profile

| Component | Specification | Strengths |
|-----------|---------------|-----------|
| **GPU** | RTX 3080 Ti (12GB VRAM) | Excellent for ~385K parameter CNN; Tensor Cores with Ampere; supports AMP float16 |
| **CPU** | AMD Ryzen 9800X3D (8-core, 104MB L3) | Massive L3 cache perfect for DataLoader prefetching; 2-4 workers optimal |
| **RAM** | 32GB DDR5-6000 MT/s | Sufficient for entire dataset in memory |
| **NVMe** | Samsung 990 Pro 2TB (7000/5100 MB/s) | **Eliminates all I/O bottlenecks** for feature cache; float16 cache at ~500GB is trivial |
| **External** | Seagate 2TB (120/120 MB/s) | 58x slower than NVMe—only for cold storage/archives |

---

## Your Dataset & Training Profile

- **~33M manifest events** → ~16.3M materialized training clips
- **~5.24M seconds** of audio clips (~1,456 hours)
- **21 classes** (drums: kick, snare, hi-hat variants, toms, cymbals, etc.)
- **~1TB combined** (feature_cache + prod_combined_profile_run)
- **Training benchmarks** on your 3080 Ti:
  - Warmup (8 epochs): ~45 min, 1200-1500 samples/sec
  - Quick refresh (60 epochs): ~2-3 hours
  - Long run (220 epochs): ~10-14 hours

---

## Why Your Local Setup is Already Exceptional

### 1. Your Model is Not Compute-Bound

- `DrumClassifierCNN` is ~385K parameters—a *tiny* model by modern ML standards
- An A100 (80GB, $2-3/hr) would be **massive overkill** for this architecture
- Cloud GPUs shine for models with billions of parameters (LLMs, diffusion models, transformers)

### 2. Your 3080 Ti is 90%+ Optimal for This Workload

```
Your setup: 1200-1700 samples/sec
A100 80GB:  ~2500-3500 samples/sec (2-3x faster)
H100:       ~4000-5000 samples/sec (3-4x faster)
```

But here's the math:
- **Long run (220 epochs):** 10-14 hours locally → 3-5 hours on H100
- **Cloud cost for H100:** 5 hours × $4.50/hr = **$22.50 per full training run**
- **You do 10+ experimental runs?** That's $225+

### 3. Data Transfer is Your Bottleneck for Cloud

- 1TB upload at 500Mbps = ~4.4 hours to upload initially
- Cloud persistent storage (S3/GCS): ~$23/TB/month
- Every dataset refresh means re-syncing gigabytes
- Your NVMe reads at 7GB/s—cloud storage can't match this latency

### 4. Your Hardware Optimizations are Already Excellent

- `channels_last` memory format ✓
- `torch.compile(mode="reduce-overhead")` ✓
- float16 AMP with GradScaler ✓
- float16 feature cache (50% storage savings) ✓
- Gradient accumulation for effective batch=128 ✓

---

## When Cloud WOULD Make Sense for BeatSight

| Scenario | Recommendation |
|----------|----------------|
| **Production inference (web API)** | ✅ Use Modal/Lambda (already in `modal_app.py`) |
| **Distributed hyperparameter sweeps** | ⚠️ Maybe—only if doing 50+ experiments simultaneously |
| **Training a larger model (transformer-based)** | ✅ Yes—but you'd need to redesign the architecture |
| **Multi-GPU scaling** | ❌ Not beneficial—your model is too small to benefit |

---

## Path to "Revolutionary" Quality

If you want the model to be **exceptional and extraordinary**, the bottleneck is **not compute power**—it's:

### 1. Data Quality & Diversity (Highest Impact)

- Your 11 source datasets (Slakh, Groove, Cambridge, ENST, etc.) are excellent
- Focus on cleaning edge cases: hi-hat ↔ snare confusions, cymbal class separation
- The 21-class taxonomy with techniques (bark, metric modulation, variable meter) is sophisticated

### 2. Architecture Improvements (High Impact, Minimal Compute Cost)

- Consider adding **Squeeze-Excitation blocks** for channel attention
- Experiment with **EfficientNet-style** compound scaling
- Add **temporal context** via LSTM/Transformer head on top of CNN

### 3. Training Refinements (Already Partially Implemented)

- Class weighting (`sqrt`, `log`, `effective` strategies) ✓
- Label smoothing ✓
- Mixup/CutMix augmentation (not yet implemented—high value)

### 4. Ensemble Methods (For Production)

- Train 3-5 models with different seeds
- Average predictions for ~2-3% accuracy boost at inference

---

## Cost Comparison Summary

| Approach | Long Run Cost | Monthly (10 runs) | Notes |
|----------|---------------|-------------------|-------|
| **Your 3080 Ti** | ~$3 electricity | ~$30 | Full control, zero latency |
| **Modal A10G** | ~$15/run | ~$150 | Cold starts, data sync overhead |
| **RunPod A100** | ~$20/run | ~$200 | Overkill for your model size |
| **AWS p4d.24xlarge** | ~$100/run | ~$1000 | Enterprise-grade, not needed |

---

## Cloud Providers Reference (If Needed Later)

### Modal (Already Integrated)
- **Best for:** Production inference, serverless GPU
- **Pricing:** A10G ~$0.60/hr, scales to zero
- **Integration:** Already in `ai-pipeline/modal_app.py`

### RunPod
- **Best for:** Spot GPU instances, community cloud
- **Pricing:** A100 80GB ~$1.99/hr (spot), ~$3.09/hr (on-demand)
- **Good for:** Hyperparameter sweeps with many parallel jobs

### Lambda Labs
- **Best for:** Reserved GPU instances
- **Pricing:** A100 ~$1.29/hr (when available)
- **Caveat:** Often sold out

### AWS/GCP/Azure
- **Best for:** Enterprise, compliance requirements
- **Pricing:** p4d.24xlarge (8×A100) ~$32/hr
- **Overkill:** For your current model size

---

## Future Model Upgrade Considerations

If you decide to evolve the architecture to something more sophisticated, cloud GPU would make sense:

| Model Type | Parameters | Cloud Recommendation |
|------------|------------|---------------------|
| Current CNN | ~385K | ❌ Stay local |
| Larger CNN + Attention | 5-10M | ⚠️ Local still fine |
| Drum Transcription Transformer | ~50M | ✅ Consider cloud |
| End-to-end Transformer | 100M+ | ✅ Cloud required |

---

## Key Takeaways

1. **Your 3080 Ti can train overnight while you sleep**—that's already optimal productivity
2. **Cloud compute ≠ better model**—data quality and architecture matter more
3. **Modal is perfect for production inference** (already set up in your codebase)
4. **Only consider cloud training if:**
   - Model grows to 50M+ parameters
   - You need 4+ GPUs for data parallelism
   - You're running 50+ hyperparameter experiments simultaneously

---

## References

- Training runbook: `docs/ml_training_runbook.md`
- Hardware profiles: `ai-pipeline/training/configs/hardware_profiles.json`
- Modal integration: `ai-pipeline/modal_app.py`
- Compute cost model: `docs/web_compute_costs.md`
- Training audit: `ai-pipeline/training/TRAINING_AUDIT_REPORT.md`
