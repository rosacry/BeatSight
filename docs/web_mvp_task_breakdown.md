# BeatSight Web MVP Task Breakdown

_Last updated: 2025-11-12_

## 1. Epic Summary
1. **E1 – Intake & Fingerprinting**
2. **E2 – AI Generation Pipeline**
3. **E3 – Web Application & Editor**
4. **E4 – Karma & Verification System**
5. **E5 – Monetization & Subscription**
6. **E6 – Observability & Operations**

Each epic is split into milestones that can convert directly into tickets.

---

## E1 – Intake & Fingerprinting

### M1: Storage & Upload Flow
- [ ] Create S3 bucket with lifecycle policies (infra ticket)
- [ ] Implement pre-signed upload API (FastAPI endpoint)
- [ ] Client-side drag/drop integration with progress events
- [ ] Virus scan Lambda hook (ClamAV) before fingerprint queueing

### M2: Fingerprint Service
- [ ] Containerize Chromaprint worker
- [ ] Implement fingerprint job queue and dedupe cache (Redis)
- [ ] Integrate AcoustID lookup + fallback manual metadata form
- [ ] Persist candidate metadata and song record in Postgres (`songs` table)

### M3: UX Polish
- [ ] Loading states + error messaging UI
- [ ] Fingerprint retry logic and manual override path
- [ ] Analytics logging for intake funnel completion

---

## E2 – AI Generation Pipeline

### M1: Job Orchestrator
- [ ] Define `ai_jobs` table and worker heartbeat fields
- [ ] Build FastAPI endpoint to enqueue AI job (permission checks + quota)
- [ ] Implement priority handling (Pro users vs free tier)

### M2: GPU Worker Integration
- [ ] Adapt existing `ai-pipeline` scripts into containerized worker
- [ ] Implement progress callbacks (Redis pub/sub)
- [ ] Store generated `.bsm` and stems in S3 paths, update `map_versions`

### M3: Notification & Error Handling
- [ ] Emit events on job completion/failure
- [ ] Send email/WebPush notifications
- [ ] Dashboard/CLI to inspect job status for support

---

## E3 – Web Application & Editor

### M1: Frontend Skeleton
- [ ] Set up React/Next.js (or chosen framework) with PWA support
- [ ] Implement auth integration (Auth0/Keycloak)
- [ ] Build responsive layout and navigation shell

### M2: Intake & Map Views
- [ ] Intake page per `docs/web_ux_flows.md`
- [ ] Verified/unverified map detail components with preview player
- [ ] Library page showing saved maps and notifications

### M3: Timeline-Lite Editor
- [ ] Reusable timeline component (WebAudio + Canvas)
- [ ] Note editing controls (drag, snap, lane reassignment)
- [ ] Comment markers + submission modal
- [ ] Diff visualization vs canonical map

---

## E4 – Karma & Verification System

### M1: Ledger & Roles
- [ ] Implement `karma_ledger`, `roles`, and `user_roles` tables
- [ ] Background job to recompute `users.karma_score`
- [ ] API endpoints for karma history and role eligibility

### M2: Verification Workflow
- [ ] Build verifier dashboard UI (queue, filters)
- [ ] Decision endpoint updating `map_edit_proposals` and `map_verification_decisions`
- [ ] Karma adjustments + notifications for fixer/verifier

### M3: Incentives & Leaderboards
- [ ] Leaderboard API + UI components
- [ ] Seasonal decay cron job
- [ ] Badge/perk surfacing on profile page

---

## E5 – Monetization & Subscription

### M1: Stripe Integration
- [ ] Create checkout session endpoint
- [ ] Handle Stripe webhooks (subscription created, renewed, cancelled)
- [ ] Update `subscriptions` table and entitlements cache

### M2: Quota Enforcement
- [ ] Track AI usage per subscription period
- [ ] Prevent overage (prompt upsell)
- [ ] Admin panel to adjust quotas manually

### M3: Marketplace Foundations
- [ ] Schema additions for bundles/purchases (future placeholder)
- [ ] Basic purchase flow for curated packs (beta flag)

---

## E6 – Observability & Operations

### M1: Metrics & Logging
- [ ] Deploy Prometheus/Grafana stack
- [ ] Expose metrics from API and workers (queue depth, job latency)
- [ ] Structured logging with trace IDs

### M2: Alerting & Cost Monitoring
- [ ] Configure alert thresholds (GPU queue > 15 min, error rate > 2%)
- [ ] Set up AWS Budgets alerts for compute spend
- [ ] Runbook documentation for on-call

### M3: CI/CD
- [ ] GitHub Actions workflow for backend/unit tests
- [ ] Infrastructure deployment pipeline (Terraform plan/apply)
- [ ] Frontend build + deployment pipeline (Vercel/CloudFront)

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
