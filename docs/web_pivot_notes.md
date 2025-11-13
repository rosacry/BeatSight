# BeatSight Web Pivot Notes

## Context & Vision Shift
- Reposition BeatSight primarily as a browser-based learning tool; desktop app remains for power users wanting local inference with identical functionality when offline.
- Maintain a future mobile experience mirroring the web feature set; handheld clients operate against the same APIs and verified map catalog.
- Treat the downloadable version as an optional companion that can still leverage cloud services when online, but can process maps fully client-side if desired.
- Defer or drop the live-microphone scoring feature for now, especially on mobile, until hardware/latency constraints are proven feasible.
- Acknowledge that fully gamified, sensor-driven experiences likely require hardware integrations (drum triggers, e-drums); keep the core offering focused on learning and map editing.

## Song Intake & Map Usage Flow
- Users drag-and-drop audio on the web homepage; a Shazam-like fingerprinting service attempts to resolve song title/artist (and optionally BPM).
- If fingerprinting succeeds, check the server for an existing **verified** map; there must never be more than one verified map per canonical song entry.
- If no verified map exists, prompt the user to submit title/artist metadata manually before saving; auto-generate placeholders when skipped.
- Web clients may only request AI generation when no verified map exists, ensuring minimal duplicate computation.
- Desktop clients connected to the internet should recommend the verified map if found, but permit local AI generation regardless; however, those client-generated maps cannot be uploaded if a verified version already exists on the server.
- Both web and desktop allow local edits to downloaded maps; users may submit edits for review when they intend to fix issues.
- Display an "Unverified Maps" queue containing AI-generated or community maps pending verification; emphasize community review workflows.

## Karma System & Incentives
- Require verified email and phone number for voting; email-only accounts earn enough karma to propose fixes, while combined verification unlocks verifier privileges.
- Downvotes must be accompanied by a proposed correction; submissions enter a review queue for high-karma verifiers.
- When a correction is approved, the fixer receives a significant karma boost, and the verifier receives a smaller reward; misusing verification privileges can drain karma.
- Karma unlocks tangible perks: increased daily AI generation quota, access to advanced editor tooling, seasonal badges, participation in curated map bundles, invite codes, and priority support.
- Introduce seasonal leaderboards and specialist tracks (e.g., "Rock Expert") to keep engagement high; apply gentle karma decay to maintain an active reviewer pool.

## Verification Rules & Map Integrity
- Maintain a single canonical verified map per song, potentially composed of multiple difficulty tiers under the same entry.
- Establish baseline karma thresholds for roles (Fixer, Verifier, Curator) and document escalation paths when disputes arise.
- Provide lightweight diff tooling so reviewers can audition edits rapidly and leave structured feedback.

## Compute & Infrastructure Considerations
- Fingerprinting (Chromaprint/AcoustID-style) per ~4 minute track: <20 seconds CPU time, ~1 core, 60–90 MB RAM; deploy in auto-scaling CPU containers.
- Full AI generation (Demucs separation + transcription + post-processing):
  - On RTX 4090 class GPU: ~3–5 minutes per track, 6–8 GB VRAM, roughly 1.2e12 FLOPs.
  - On A100 80 GB GPU: ~1.5–2 minutes, ~20 GB RAM; cloud cost approximately $0.05–$0.20 per song depending on spot pricing.
- Web flow should enqueue new songs for background processing and notify users on completion via email/push; enforce per-account quotas to contain spend.
- Desktop clients can optionally run the same pipeline locally; ensure compatibility with consumer GPUs and provide progress reporting.

## Mobile Experience
- Ship as a responsive Progressive Web App first: service workers cache verified maps, offline playback supported via WebAudio, 2D lane renderer optimized for touch.
- Consider wrapping the PWA in a Flutter/Capacitor shell later for store distribution while reusing existing web code.
- Mobile editor operates in a simplified review mode: tap/drag for timing adjustments, quick comment annotations, and submission back to the queue.
- Live microphone scoring remains a long-term research item; monitor latency and microphone fidelity before reintroducing.

## Monetization Strategy
- Baseline: free access to verified maps, community edits, and the standard editor across web/mobile; donation options remain available.
- Pro subscription ($6–$10/month): unlimited AI generations (cloud or local), advanced analytics, practice summaries, synced cloud library, priority inference queue, specialty lesson packs, and downloadable stem bundles.
- Marketplace: host curated premium map packs with licensed content; share revenue with high-karma curators and educators.
- Additional revenue: affiliate partnerships for drum gear, sponsored community events, institutional licenses for music schools, and optional compute credit packs once monthly free quota is exceeded.

## Open Questions
- Clarify how multiple difficulty levels coexist under the "single verified map" rule; consider storing variants as linked child charts.
- Define acceptable turnaround time for verifications and ensure tooling supports rapid A/B listening.
- Determine audio storage policy to mitigate licensing risk (e.g., hashed fingerprints, user-provided storage buckets, or short-term caching).
- Document clear karma thresholds and consequences for negligence or abuse in verification workflows.

## Immediate Next Actions
1. Draft a concise pivot-focused product requirements document summarizing the end-to-end web flow, karma roles, and verification lifecycle.
2. Prototype a cost model spreadsheet estimating monthly GPU/CPU spend under different user volumes and caching strategies; evaluate managed GPU services (Modal, AWS Batch, Azure Batch).
3. Design UX wireframes for the drag-and-drop intake, asynchronous processing states, and edit submission pipeline across desktop web and mobile.
4. Identify additional documentation (existing `.md`/`.txt` references) that should be cross-linked here for future contributors, then update this file accordingly.
