# BeatSight Web MVP Task Breakdown

_Last updated: 2025-12-03_

## 1. Epic Summary
1. **E1 – Intake & Fingerprinting** ✅ COMPLETE
2. **E2 – AI Generation Pipeline** ✅ COMPLETE
3. **E3 – Web Application & Editor** ✅ COMPLETE
4. **E4 – Karma & Verification System** ✅ COMPLETE
5. **E5 – Monetization & Subscription** ✅ COMPLETE
6. **E6 – Observability & Operations** ⚠️ PARTIAL (CI complete, monitoring pending)

Each epic is split into milestones that can convert directly into tickets.

---

## E1 – Intake & Fingerprinting ✅

### M1: Storage & Upload Flow ✅
- [x] Create S3 bucket with lifecycle policies (infra ticket) - `backend/app/services/storage.py`
- [x] Implement pre-signed upload API (FastAPI endpoint) - `backend/app/api/routes/storage.py`
- [x] Client-side drag/drop integration with progress events - `frontend/src/pages/UploadPage.tsx`
- [ ] Virus scan Lambda hook (ClamAV) before fingerprint queueing - DEFERRED

### M2: Fingerprint Service ✅
- [x] Containerize Chromaprint worker - AcoustID integration in `backend/app/services/acoustid.py`
- [x] Implement fingerprint job queue and dedupe cache (Redis) - `backend/app/db/redis.py`
- [x] Integrate AcoustID lookup + fallback manual metadata form - `backend/app/api/routes/metadata.py`
- [x] Persist candidate metadata and song record in Postgres (`songs` table) - `backend/app/models/song.py`

### M3: UX Polish ✅
- [x] Loading states + error messaging UI - `frontend/src/components/ui/Skeleton.tsx`, Toast system
- [x] Fingerprint retry logic and manual override path - `/metadata/identify-with-retry` endpoint
- [x] Analytics logging for intake funnel completion - `backend/app/services/intake_analytics.py`

---

## E2 – AI Generation Pipeline ✅

### M1: Job Orchestrator ✅
- [x] Define `ai_jobs` table and worker heartbeat fields - `backend/app/models/ai_job.py`
- [x] Build FastAPI endpoint to enqueue AI job (permission checks + quota) - `backend/app/api/routes/ai_jobs.py`
- [x] Implement priority handling (Pro users vs free tier) - `backend/app/services/quota.py`

### M2: GPU Worker Integration ✅
- [x] Adapt existing `ai-pipeline` scripts into containerized worker - `ai-pipeline/Dockerfile`, `ai-pipeline/pipeline/worker.py`
- [x] Implement progress callbacks (Redis pub/sub) - SSE streaming at `/ai-jobs/{id}/progress/stream`
- [x] Store generated `.bsm` and stems in S3 paths, update `map_versions` - Storage service integration

### M3: Notification & Error Handling ✅
- [x] Emit events on job completion/failure - Redis pub/sub + WebSocket
- [x] Send email/WebPush notifications - `backend/app/services/notifications.py`
- [x] Dashboard/CLI to inspect job status for support - Admin dashboard API

---

## E3 – Web Application & Editor ✅

### M1: Frontend Skeleton ✅
- [x] Set up React/Vite with PWA support - `frontend/` with service worker
- [x] Implement auth integration - Self-hosted JWT via `backend/app/services/auth.py`
- [x] Build responsive layout and navigation shell - `frontend/src/components/layout/NavigationShell.tsx`

### M2: Intake & Map Views ✅
- [x] Intake page per `docs/web_ux_flows.md` - `frontend/src/pages/UploadPage.tsx`
- [x] Verified/unverified map detail components with preview player - Map detail pages
- [x] Library page showing saved maps and notifications - `frontend/src/pages/LibraryPage.tsx`

### M3: Timeline-Lite Editor ✅
- [x] Reusable timeline component (WebAudio + Canvas) - `frontend/src/components/timeline/TimelineCanvas.tsx`
- [x] Note editing controls (drag, snap, lane reassignment) - `frontend/src/components/timeline/TimelineEditor.tsx`
- [x] Comment markers + submission modal - Map edit proposal system
- [x] Diff visualization vs canonical map - `frontend/src/components/ProposalDiffViewer.tsx`

---

## E4 – Karma & Verification System ✅

### M1: Ledger & Roles ✅
- [x] Implement `karma_ledger`, `roles`, and `user_roles` tables - All models in `backend/app/models/`
- [x] Background job to recompute `users.karma_score` - Karma service
- [x] API endpoints for karma history and role eligibility - `backend/app/api/routes/karma.py`

### M2: Verification Workflow ✅
- [x] Build verifier dashboard UI (queue, filters) - `frontend/src/pages/VerifierDashboardPage.tsx`
- [x] Decision endpoint updating `map_edit_proposals` and `map_verification_decisions` - `backend/app/api/routes/verifier.py`
- [x] Karma adjustments + notifications for fixer/verifier - Integrated

### M3: Incentives & Leaderboards ✅
- [x] Leaderboard API + UI components - `backend/app/api/routes/karma.py` leaderboard endpoint
- [ ] Seasonal decay cron job - DEFERRED (not critical for MVP)
- [x] Badge/perk surfacing on profile page - Profile page karma display

---

## E5 – Monetization & Subscription ✅

### M1: Stripe Integration ✅
- [x] Create checkout session endpoint - `backend/app/api/routes/billing.py`
- [x] Handle Stripe webhooks (subscription created, renewed, cancelled) - `backend/app/services/stripe_service.py`
- [x] Update `subscriptions` table and entitlements cache - Subscription model + sync

### M2: Quota Enforcement ✅
- [x] Track AI usage per subscription period - `backend/app/services/quota.py`
- [x] Prevent overage (prompt upsell) - 429 responses with upgrade prompts
- [x] Admin panel to adjust quotas manually - Admin dashboard API

### M3: Credits System (ADDED) ✅
- [x] Credit balance, purchases, transactions tables - `backend/app/models/credits.py`
- [x] Credit packs API and purchase flow - `backend/app/api/routes/credits.py`
- [x] Auto top-up configuration - Credits service
- [x] Frontend credit purchase modal - `frontend/src/components/CreditPurchaseModal.tsx`

---

## E6 – Observability & Operations ⚠️ PARTIAL

### M1: Metrics & Logging ✅
- [x] Expose metrics from API and workers - Prometheus `/metrics` endpoint
- [x] Structured logging with trace IDs - Structlog configuration
- [ ] Deploy Prometheus/Grafana stack - PENDING (infra deployment)

### M2: Alerting & Cost Monitoring ⚠️
- [ ] Configure alert thresholds (GPU queue > 15 min, error rate > 2%) - PENDING
- [ ] Set up AWS Budgets alerts for compute spend - PENDING
- [x] Runbook documentation for on-call - `docs/PRODUCTION_DEPLOYMENT_GUIDE.md`

### M3: CI/CD ✅
- [x] GitHub Actions workflow for backend/unit tests - `.github/workflows/backend.yml`
- [ ] Infrastructure deployment pipeline (Terraform plan/apply) - DEFERRED
- [x] Frontend build + deployment pipeline - `.github/workflows/frontend.yml`

---

## 2. Suggested Sequencing
1. **Weeks 1-2**: E1.M1, E1.M2 (storage + fingerprint service)
2. **Weeks 3-4**: E2.M1, E2.M2 (AI queue + GPU worker)
3. **Weeks 5-6**: E3.M1, E3.M2 (web shell + intake views)
4. **Weeks 7-8**: E4.M1, E4.M2 (karma ledger + verification dashboard)
5. **Weeks 9-10**: E2.M3, E4.M3 (notifications + incentives)
6. **Weeks 11-12**: E5.M1, E5.M2 (monetization + quotas)
7. **Weeks 13+**: E6 epics, marketplace scaffolding, polish

## 3. Dependencies & Notes
- Ensure ai-pipeline containerization is aligned with existing training scripts; reuse config where possible.
- Authentication integration must precede any karma/verification work.
- Frontend editor relies on canonical map APIs; prioritize read endpoints early.
- Monetization can ship post-MVP, but entitlement plumbing should be designed early to avoid refactor.
- Observability tasks run parallel once first services deploy.
