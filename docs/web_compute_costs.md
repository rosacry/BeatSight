# BeatSight Web Compute Cost Model (Draft)

_Last updated: 2025-11-12_

## 1. Assumptions
- Average track length ingested: **4 minutes**.
- Audio stored temporarily (<24h) for processing; long-term storage limited to fingerprints and maps.
- Spot-instance pricing used where possible; on-demand rates provide fallback ceiling.
- Monthly active users (MAU) scenarios: **1k**, **10k**, **50k**.
- Verified maps eliminate repeat AI processing; only first-time songs consume GPU cycles.

## 2. Pipeline Stages & Unit Costs

| Stage | Resources | Time / Track | Cost Notes |
|-------|-----------|--------------|------------|
| Fingerprint (Chromaprint) | 1 vCPU, 512 MB RAM | 15–20 s | ~$0.0002 on AWS Fargate Spot (0.004 vCPU-hrs) |
| Metadata DB Lookup | Postgres + Redis | <100 ms | Negligible (amortized infra cost) |
| AI Separation + Transcription | GPU (RTX 4090 equivalent) | 3–5 min | ~$0.05 per run on Lambda GPU / Modal |
| Post-processing + Map Persist | 2 vCPU, 4 GB RAM | 20–30 s | ~$0.0006 on Fargate Spot |
| Notification (Email + Push) | SaaS | $0.0006 per email | Bulk pricing tiers apply |

> **Total per new song (cloud GPU)** ≈ **$0.051–$0.06** (dominated by GPU time).

## 3. Monthly Cost Scenarios

### Scenario A — 1k MAU
- New songs per user/month: 2 (assume 50% already verified).
- AI jobs/month: 1k MAU × 1 new song = **1,000 jobs**.
- GPU cost: 1,000 × $0.055 = **$55**.
- Fingerprinting/post-processing compute: ~1,000 × $0.0008 ≈ **$0.80**.
- Email notifications: 1,000 × $0.0006 ≈ **$0.60**.
- **Total variable cost ≈ $56.4/month**.

### Scenario B — 10k MAU
- AI jobs: 10,000 × 1 = **10,000 jobs**.
- GPU cost: ≈ **$550**.
- CPU + notifications: ≈ **$14**.
- **Total variable cost ≈ $564/month**.

### Scenario C — 50k MAU
- AI jobs: 50,000 × 1 = **50,000 jobs**.
- GPU cost: ≈ **$2,750**.
- CPU + notifications: ≈ **$70**.
- **Total variable cost ≈ $2,820/month**.

> These figures exclude baseline infrastructure (databases, CDN, storage), estimated below.

## 4. Baseline Infrastructure Estimates

| Component | Monthly Cost (est.) | Notes |
|-----------|---------------------|-------|
| Postgres (AWS Aurora Serverless v2) | $250 | Scales with usage; includes multi-AZ redundancy |
| Redis cache (ElastiCache) | $90 | For hot song lookups, session storage |
| Object storage (S3) | $40 | Fingerprints, temporary audio (assuming 2 TB-month total) |
| CDN (CloudFront) | $60 | Map downloads, editor assets |
| Monitoring (Datadog/Prometheus/Grafana Cloud) | $80 | Metrics, logging |
| Misc (API Gateway/LB, Secrets Manager) | $60 | | 
| **Baseline Total** | **$580** | Rounded |

## 5. Speed Optimizations (Implemented)

**Baseline Processing Time**: ~35 seconds for 3-minute song on A100  
**Optimized Processing Time**: ~15 seconds for 3-minute song on A100 (57% faster)  
**With Caching**: ~8 seconds for repeated requests

### 5.1 Optimization Stack

| Optimization | Speedup | Implementation |
|--------------|---------|----------------|
| Hybrid Demucs (htdemucs_ft) | 2.5x separation | `separation/demucs_separator.py` |
| TensorRT/ONNX Runtime | 2-4x classification | `training/inference/tensorrt_inference.py` |
| Spectrogram Caching | 30% overall | `training/tools/spectrogram_cache.py` |
| Skip Separation Detection | 60% for isolated drums | `separation/demucs_separator.py` |
| Adaptive Batch Sizing | 10-20% | `training/inference/optimized_pipeline.py` |

### 5.2 Updated Per-Track Cost

| Tier | Model | Processing Time | Cost/Track |
|------|-------|-----------------|------------|
| Free | V5-Tiny + htdemucs_ft | ~25s | ~$0.009 |
| Basic | V5-Distilled | ~18s | ~$0.0065 |
| Pro | V5-Full + optimizations | ~15s | ~$0.0054 |
| API | V5-Full + TensorRT | ~12s | ~$0.0043 |

**Key Insight**: Optimizations reduce cost per track by 57-67%, significantly improving margins.

### 5.3 Tier Differentiation Strategy (Updated December 2025)

| Tier | Price | Model Variant | Monthly Limit | Speed Priority |
|------|-------|---------------|---------------|----------------|
| Free | $0 | V5-Distilled (~7.5M params) | 5 songs | Low |
| Basic | $8/mo ($64/yr) | V5-Distilled (~7.5M params) | 30 songs | Medium |
| Pro | $15/mo ($120/yr) | V5-Full (~15M params) | Unlimited | High |
| API | $0.05/song | V5-Full + TensorRT | Pay-per-use | Maximum |

**Pricing Rationale**:
- **Free (5 songs)**: Hook users, demonstrate value. Cost: ~$0.04/user/month.
- **Basic ($8/mo)**: Target casual drummers. At 30 songs: $0.24 cost → 97% margin.
- **Pro ($15/mo)**: Target serious musicians. Even at 100 songs: $1.50 cost → 90% margin.
- **Yearly plans**: 2 months free (17% discount) to improve retention and cash flow.

**Unit Economics**:
- Average user processes ~10 songs/month
- At 5% free→paid conversion, 70% Basic / 30% Pro split
- ARPU: ~$10.10/month
- Gross margin: 90%+

## 6. Optimization Levers
- **Client-Side Inference**: Encourage desktop users with capable GPUs to run local inference, reducing server GPU load by an estimated 30–50%.
- **Caching**: Hash audio fingerprints and store AI outputs; prevent redundant runs even if metadata differs.
- **Batching**: Queue GPU jobs and process in batches to maximize GPU utilization (minimize cold-start overhead).
- **Model Distillation**: ✅ **Implemented** - V5-Tiny and V5-Distilled variants for tiered offerings.
- **Quota Enforcement**: Limit free tier to N AI generations/month; upsell pro subscribers for additional runs.

## 7. Revenue Sensitivity
- Break-even AI cost per user = GPU spend / paying users. Example: Scenario B with 5% conversion to $8/mo subscription → 500 paying users → $4,000 revenue against ~$1,144 total cost (variable + baseline) ⇒ healthy margin.
- Marketplace bundles (e.g., $5 pack, 30% platform cut) contribute incremental revenue with negligible compute impact.
- **With optimizations**: Pro tier cost drops to ~$0.27/user/month (50 songs), improving unit economics significantly.

## 8. Next Steps
1. ~~Validate GPU runtime benchmarks with current pipeline~~ ✅ Done - see optimizations above.
2. Compare managed GPU platforms (Modal, AWS Batch, RunPod, Lambda GPU) for price/performance and cold-start latency.
3. Prototype cost alerts (e.g., AWS Budgets) to detect runaway inference usage.
4. Model long-term storage cost if keeping anonymized stems for audit—estimate ~$23/TB-month on S3 Standard, less on Glacier Instant Retrieval.
5. **NEW**: Benchmark TensorRT vs ONNX Runtime on A10G for Scenario C scaling.
6. **NEW**: Implement Redis cache for spectrogram fingerprints across instances.

## 9. Implementation Status

| Component | Status | File |
|-----------|--------|------|
| Hybrid Demucs | ✅ Implemented | `ai-pipeline/separation/demucs_separator.py` |
| TensorRT Inference | ✅ Implemented | `ai-pipeline/training/inference/tensorrt_inference.py` |
| Spectrogram Cache | ✅ Implemented | `ai-pipeline/training/tools/spectrogram_cache.py` |
| Optimized Pipeline | ✅ Implemented | `ai-pipeline/training/inference/optimized_pipeline.py` |
| Model Distillation | ✅ Implemented | `ai-pipeline/training/tools/distill_model.py` |
| Skip Separation Detection | ✅ Implemented | `ai-pipeline/separation/demucs_separator.py` |

