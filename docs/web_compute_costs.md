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

## 5. Optimization Levers
- **Client-Side Inference**: Encourage desktop users with capable GPUs to run local inference, reducing server GPU load by an estimated 30–50%.
- **Caching**: Hash audio fingerprints and store AI outputs; prevent redundant runs even if metadata differs.
- **Batching**: Queue GPU jobs and process in batches to maximize GPU utilization (minimize cold-start overhead).
- **Model Distillation**: Explore lightweight separation/transcription models for CPU or low-tier GPU execution to lower per-run cost.
- **Quota Enforcement**: Limit free tier to N AI generations/month; upsell pro subscribers for additional runs.

## 6. Revenue Sensitivity
- Break-even AI cost per user = GPU spend / paying users. Example: Scenario B with 5% conversion to $8/mo subscription → 500 paying users → $4,000 revenue against ~$1,144 total cost (variable + baseline) ⇒ healthy margin.
- Marketplace bundles (e.g., $5 pack, 30% platform cut) contribute incremental revenue with negligible compute impact.

## 7. Next Steps
1. Validate GPU runtime benchmarks with current pipeline; adjust per-track cost accordingly.
2. Compare managed GPU platforms (Modal, AWS Batch, RunPod, Lambda GPU) for price/performance and cold-start latency.
3. Prototype cost alerts (e.g., AWS Budgets) to detect runaway inference usage.
4. Model long-term storage cost if keeping anonymized stems for audit—estimate ~$23/TB-month on S3 Standard, less on Glacier Instant Retrieval.
