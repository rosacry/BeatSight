# BeatSight Web MVP — Product Requirements

## 1. Summary
Build a browser-first BeatSight experience that allows drummers to ingest songs, discover or request AI-generated beatmaps, edit mappings collaboratively, and surface verified community content. Desktop and mobile web clients share the same flow; native desktop remains the power-user option with local inference.

## 2. Goals & Non-Goals
- **Goals**
  - Deliver a frictionless drag-and-drop intake that resolves song metadata, checks for verified beatmaps, and queues AI generation only when necessary.
  - Provide an authoritative catalog of verified maps backed by community karma roles and review tooling.
  - Enable lightweight in-browser editing and correction workflows, with submissions routed to verifiers.
  - Support responsive mobile layouts with touch-oriented review/edit controls.
- **Non-Goals (MVP)**
  - Real-time mic scoring or latency-sensitive gameplay in the browser.
  - Full-featured timeline editor parity with desktop app.
  - Native billing integrations beyond Stripe web checkout.
  - Handling licensing of full-length audio for distribution; focus on user-supplied content and hashed fingerprints.

## 3. Target Users & Personas
- **Learner**: Wants quick access to verified maps to practice on desktop app; uses web for discovery and preview.
- **Fixer**: Finds inaccuracies and submits corrections; may have email-only verification.
- **Verifier**: High-karma community member who reviews fixes, approves/unverifies maps, keeps quality high; requires phone + email verification.
- **Curator/Educator**: Publishes structured packs, monitors karma leaderboards, participates in monetized bundles.

## 4. User Stories
1. As a learner, I drag a song file onto the homepage and immediately see if a verified map exists so I know whether I can start practicing.
2. As a learner, if no verified map exists, I opt in to AI generation, receive a notification when complete, and can preview the result in-browser.
3. As a fixer, I downvote a mapping, supply annotated corrections, and submit for verifier review.
4. As a verifier, I open the pending queue, audition diffs, and approve or reject fixes, rewarding the fixer accordingly.
5. As a curator, I compile approved maps into a themed pack and optionally list it as a paid bundle.

## 5. User Flows
- **Song Intake Flow**
  1. Drag/drop or file picker → compute fingerprint → metadata resolution → server lookup for verified map.
  2. If verified map found: show preview, allow play, download `.bsm`, open editor, or queue desktop sync.
  3. If not found: prompt for metadata confirmation → explain AI queue cost/time → enqueue job → notify user on completion.
- **AI Generation Completion**
  1. Background worker runs separation/transcription → stores map as `Unverified` entry → triggers email/push.
  2. User views AI map, optionally leaves feedback, decides to submit corrections or request verification.
- **Edit & Fix Submission**
  1. User opens web editor (timeline-lite) → adjusts notes/time → includes commentary → submits fix request.
  2. System creates diff snapshot and attaches metadata for verifiers.
- **Verification Workflow**
  1. Verifier dashboard lists pending items sorted by karma weight, recency.
  2. Verifier compares original vs proposed (A/B playback, diff view) → accepts or rejects.
  3. Karma adjustments automatically applied; map state toggled `Verified`/`Needs Work` as appropriate.

## 6. Functional Requirements
- Fingerprint service with fallback metadata entry.
- Canonical song entity storing one verified map with optional difficulty variants.
- AI job queue with states: `Queued`, `Processing`, `Complete`, `Failed`.
- Notification service (email + optional push/WebPush) for job completion, verification outcomes.
- Web editor with essential features: snap, timing shift, lane reassignment, comment markers.
- Karma ledger tracking actions (upvotes, fixes, verifications) with minimum thresholds for roles.
- Audit logging for map changes and verification decisions.

## 7. Non-Functional Requirements
- Responsive layout (>=320px width) with accessible controls; target <2s load on median mobile connection.
- Horizontal scaling capability for fingerprinting CPU workers and GPU inference workers.
- Role-based access control enforced on APIs; use JWT with scopes tied to karma roles.
- Observability: metrics on job queue length, average processing time, verification latency, and karma distribution.
- Data retention policies limiting audio storage (hashed fingerprints + short-term cache for stems).

## 8. Dependencies & Integrations
- Chromaprint/AcoustID or equivalent for fingerprinting.
- Demucs-based pipeline (existing) deployed via containerized GPU workers.
- Stripe (or Paddle) for web subscription billing and marketplace payouts.
- SendGrid/Postmark + WebPush for notifications.
- Database: PostgreSQL (songs, maps, karma ledger) + S3-compatible storage (temporary audio, diff assets).
- Reference `docs/web_backend_schema.md` for canonical data model.

## 9. Analytics & Metrics
- Conversion funnel: drag-drop initiated → map found → AI queued → AI complete → map downloaded.
- Karma health: number of active verifiers, average verification turnaround, fix acceptance rate.
- Compute utilization: GPU minutes per day, cost per successful map, queue wait time.
- Monetization: subscription conversion, bundle sales, donor retention.

## 10. Risks & Mitigations
- **High compute cost**: enforce one-generation-per-song policy; throttle web usage; surface estimated wait times.
- **Quality variance**: rely on karma-gated verifiers, diff tooling, and community feedback loops.
- **Licensing concerns**: avoid storing raw audio long-term; rely on fingerprints and short-lived caches.
- **Mobile UX complexity**: deliver timeline-lite editor first, gather feedback before deeper tooling.

## 11. Roadmap Snapshot
1. Implement fingerprinting + lookup API.
2. Build AI job queue and notification service.
3. Ship web intake UI with asynchronous status tracking.
4. Deliver timeline-lite editor and fix submission pipeline.
5. Launch verifier dashboard and karma ledger.
6. Layer in monetization (subscriptions, bundles) post quality stabilization.

## 12. Open Questions
- How should difficulty variants be modeled under the single verified map constraint? (Possible solution: canonical song entity with `Expert`, `Intermediate`, `Beginner` child charts.)
- Should AI regeneration be allowed after human fixes (e.g., to test new model versions)? If so, how to preserve historical states?
- What SLAs do we commit to for AI job completion and verification turnaround?
- How to handle disputed verifications (appeals, arbitration, karma penalties)?
- Coordinate with `docs/web_mvp_task_breakdown.md` to ensure open questions translate into actionable tasks.
