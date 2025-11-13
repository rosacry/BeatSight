# BeatSight Roadmap (Phase Overview)

## Orientation
- **Phase 1 – Desktop Reference (in flight):** gameplay polish complete; AI pipeline and editor polish wrap up Phase 1.3.
- **Phase 2 – Web MVP (pre-production):** intake → queue → verification flow scoped, pending engineering tickets and infrastructure spikes.
- **Phase 3 – Mobile Apps (queued):** Flutter shell and shared parsers planned post web launch.
- **Phase 4 – Advanced Features (queued):** expands real-time, AI, and sampling capabilities.
- **Phase 5 – Growth (ongoing):** UX, performance, community work once core surfaces ship.

## Near-Term Targets (Q4 2025)
1. **Ship prod_combined retrain** with crash dual-label coverage and calibrated thresholds (export → warm-up probe → evaluate → long run per `docs/ml_training_runbook.md`).
2. **Promote Practice Mode polish** (waveform view, blur shader, hit lighting) to close Phase 1 desktop polish.
3. **Stand up web MVP delivery boards** – convert `docs/web_mvp_task_breakdown.md` into issue tracker milestones.
4. **Decide GPU job orchestration** (Modal vs Batch vs bespoke) to de-risk web inference cost model.

## Phase Gates & Success Criteria
- **Phase 1 exit:** desktop app stable across platforms, practice mode feature-complete, AI classifier promoted from retrain bundle, editor capable of manual authoring.
- **Phase 2 exit:** web users can request, review, and verify AI-assisted maps with karma gating; compute telemetry matches `docs/web_compute_costs.md` assumptions.
- **Phase 3 exit:** Flutter clients deliver 60 FPS gameplay, sync beatmap library, and ship to both stores.

## Backlog Buckets
- **Product backlog:** see `docs/archive/next_steps_2025-11-12.md` for option matrices and feature ideas.
- **Engineering backlog:** `docs/IMPLEMENTATION_GUIDE.md`, `docs/SETUP.md`, and the subsystem-specific READMEs document scaffolding work.
- **Research backlog:** dataset readiness plan (`ai-pipeline/training/DATASET_READINESS_PLAN.md`) and ML runbook govern training experiments.

## Historical Roadmap
For the detailed milestone tables captured prior to this reorganization, reference [`docs/archive/roadmap_2025-11-12.md`](../archive/roadmap_2025-11-12.md).
