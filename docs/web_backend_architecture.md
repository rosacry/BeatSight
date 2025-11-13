# BeatSight Web Backend Architecture (Draft)

_Last updated: 2025-11-12_

## 1. High-Level Overview
```
Client (Web / PWA / Mobile Wrapper)
    ↕ HTTPS
API Gateway (FastAPI + GraphQL-lite facade)
    ↕ Internal RPC / Event bus
Services:
  • Fingerprint Service (Chromaprint workers)
  • Song Catalog & Map API (Postgres + Redis)
  • AI Job Orchestrator (Celery/RQ + GPU workers)
  • Karma & Notification Service
  • Billing Service (Stripe webhooks)
Shared Infrastructure:
  • Auth (JWT + OAuth2)
  • Object Storage (S3-compatible)
  • Observability Stack (Prometheus, Grafana, Loki)
```

## 2. Services & Responsibilities

### 2.1 Fingerprint Service
- Stateless FastAPI endpoint receives audio upload references (pre-signed URLs) and queues CPU workers.
- Workers generate Chromaprint fingerprints, query AcoustID/Whisper fallback, and return candidate metadata.
- Results cached in Redis keyed by fingerprint hash → prevents duplicate work.

### 2.2 Song Catalog & Map API
- Core FastAPI app exposing REST/GraphQL endpoints consumed by web client.
- Postgres schema:
  - `songs` (id, fingerprint_hash, title, artist, bpm, canonical_map_id, status)
  - `maps` (id, song_id, difficulty_label, version, state {verified, unverified, archived}, storage_ref)
  - `edits` (id, map_id, proposer_id, diff_payload, status)
  - `users` (id, auth_provider_id, email_verified, phone_verified, karma, roles)
  - `karma_ledger` (id, user_id, amount, reason, associated_entity)
- Redis used for hot artifacts (map metadata, queue status) and rate limiting.

### 2.3 AI Job Orchestrator
- API receives `GenerateMap` request → writes job record to Postgres → enqueues message to worker queue (Celery/RQ/Kafka-based).
- Worker pod (GPU) runs Demucs separation + transcription pipeline (reusing `ai-pipeline/`) with progress heartbeats.
- Output `.bsm` and processed stems stored in S3 (`maps/unverified/{song_id}/{job_id}.bsm`), metadata updated in Postgres.
- On completion, event emitted to Notification service.

### 2.4 Karma & Notification Service
- Listens on internal event bus (e.g., Redis streams, NATS) for actions: upvote/downvote, fix submission, verification decision.
- Applies karma deltas per rules in `docs/web_pivot_notes.md`; persists to ledger and recalculates role eligibility.
- Sends transactional emails/WebPush via SendGrid/Postmark + VAPID service.

### 2.5 Billing Service
- Stripe Checkout integration for subscriptions and bundle purchases.
- Webhook consumer updates Postgres (`subscriptions`, `orders`) and adjusts quotas (AI runs, bundle access).
- Shares user entitlements with API via cached lookups.

## 3. Authentication & Authorization
- OAuth2/JWT via Auth0 or self-hosted Keycloak.
- Tokens carry scopes aligned with karma roles (`fixer`, `verifier`, `curator`, `admin`).
- API gateway enforces scope checks; fine-grained checks in services (e.g., only verifiers can access queue endpoints).
- Email/phone verification handled by Auth provider; phone using Twilio Verify or similar.

## 4. Data Flow Scenarios

### 4.1 New Song Upload (Web)
1. Client uploads audio via pre-signed S3 URL.
2. Client posts metadata request → API triggers fingerprint job.
3. Fingerprint worker returns metadata and checks Postgres for existing verified map.
4. API responds with either existing map data or AI generation prompt.
5. If AI requested, `GenerateMap` job enqueued; upon completion, map stored as `unverified` and user notified.

### 4.2 Fix Submission & Verification
1. User edits map in browser, submits diff payload (JSON patch + commentary).
2. API stores diff in `edits` with `pending` state, emits `EditSubmitted` event.
3. Verifier dashboard queries pending edits; on decision, API updates map state, emits `EditApproved`/`EditRejected`.
4. Karma service adjusts scores for fixer/verifier, triggers notifications.
5. Approved edit publishes new map version, archives previous one for audit.

### 4.3 Subscription Purchase
1. User invokes Stripe Checkout session; upon success, Stripe webhook hits Billing service.
2. Billing service records subscription, credits monthly AI quota/top-level perks.
3. API gateway caches entitlement; front-end reflects Pro status and expanded limits.

## 5. Deployment Topology
- **API Gateway**: FastAPI + Uvicorn behind AWS ALB / Azure App Gateway.
- **Worker Pools**:
  - CPU fingerprint workers (AWS Fargate Spot / Azure Container Apps)
  - GPU inference workers (Modal, RunPod, or self-managed Kubernetes GPU nodes)
- **Databases**: AWS Aurora Postgres Serverless v2 + Redis (ElastiCache) in same VPC.
- **Storage**: S3 buckets with lifecycle policies (unverified stems auto-delete after 30 days unless promoted).
- **Observability**: Prometheus metrics scraped from services; Grafana dashboards; Loki for logs; Alertmanager for paging.

## 6. Security & Compliance Considerations
- Audio uploads virus-scanned (ClamAV Lambda) before processing.
- Signed URLs with limited TTLs to prevent unauthorized sharing.
- Encryption at rest (S3, Postgres, Redis) and in transit (TLS everywhere).
- Access logging + anomaly detection on authentication events.
- GDPR/CCPA compliance: retention policies, data export/delete endpoints.

## 7. Scalability & Cost Controls
- Autoscale fingerprint workers by queue depth; target <30s average wait.
- GPU workers sized via `docs/web_compute_costs.md`; support burst scaling using spot instances with fallback on-demand pool.
- Implement per-user quotas enforced via Redis counters; apply rate limiting to fingerprint and map generation endpoints.
- Monitor compute spend with AWS Budgets / GCP Billing Alerts, tying dashboards to map throughput.

## 8. Backlog / Open Questions
- Decide between Celery (Redis) vs. AWS SQS + Lambda for job orchestration; evaluate reliability and cost.
- Define retention/archival strategy for unverified map versions (audit trail vs. storage cost).
- Explore GraphQL for front-end flexibility vs. REST with filtered endpoints.
- Determine strategy for supporting future desktop sync (webhook to client, or manual download).

## 9. Next Steps
1. Review architecture with stakeholders; confirm service boundaries.
2. Reference `docs/web_backend_schema.md` for ERD/logical schema; iterate as needed.
3. Prototype fingerprint API + worker to validate throughput.
4. Start infrastructure as code (Terraform/Bicep) drafts for core resources.

---

## 10. Implementation Snapshot (2025-11-12)
- `backend/pyproject.toml` and `backend/README.md` establish a Poetry-managed FastAPI service.
- `backend/app/` contains configuration, logging, async SQLAlchemy models mirroring the schema, and routers for songs/AI jobs/health checks.
- Service layer stubs under `backend/app/services/` manage song CRUD and AI job enqueueing against Postgres.
- Initial pytest smoke test (`backend/tests/test_health.py`) verifies health endpoints.
