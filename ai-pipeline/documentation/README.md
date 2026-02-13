# AI Pipeline Documentation Index

Last updated: 2026-02-13

This directory is the canonical home for AI pipeline markdown documentation.

## Structure

- `ai-pipeline/documentation/current/`
  - Active run-state and handoff documents that should reflect the present pipeline/training state.
- `ai-pipeline/documentation/archive/handoffs/`
  - Historical handoffs and superseded execution plans kept for reference.
  - Local index: `ai-pipeline/documentation/archive/handoffs/README.md`
- `ai-pipeline/documentation/archive/prompts/session/`
  - Session prompts, file-attachment notes, and one-off temporary working docs.
  - Local index: `ai-pipeline/documentation/archive/prompts/session/README.md`

## Active Source Of Truth

For current operational status and commands, start with:

1. `ai-pipeline/documentation/current/ACCURACY_IMPROVEMENTS_TRACKER.md`
2. `ai-pipeline/documentation/current/OPUS_HANDOFF_SESSION3_DUAL_MODEL_ENSEMBLE.md`
3. `ai-pipeline/documentation/current/CURRENT_AI_PIPELINE_STATE.md`

## Maintenance Rules

1. Update `ACCURACY_IMPROVEMENTS_TRACKER.md` first after each major milestone.
2. Update active handoff docs in `current/` second.
3. Archive superseded plans/handoffs into `archive/handoffs/` instead of leaving stale files in root.
4. Store session prompts and temporary request artifacts in `archive/prompts/session/`.
