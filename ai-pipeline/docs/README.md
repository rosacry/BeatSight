# AI Pipeline Docs Index

This directory organizes operational AI pipeline notes.

## Active Operational Docs (root `ai-pipeline/`)

These remain at the root because tooling and handoffs refer to these exact paths:

- `ACCURACY_IMPROVEMENTS_TRACKER.md`
- `CURRENT_AI_PIPELINE_STATE.md`
- `NEXT_STEPS_POST_TRAINING.md`
- `OPUS_HANDOFF_SESSION3_DUAL_MODEL_ENSEMBLE.md`
- `OPUS_HANDOFF_DEMUCS_DOMAIN_GAP.md`

## Archive

Prompt-style and temporary working markdown files are archived under:

- `ai-pipeline/docs/archive/session-prompts/`

These files are kept for historical context but are not the source of truth.

## Update Policy

When training/evaluation state changes:

1. Update `ACCURACY_IMPROVEMENTS_TRACKER.md` first.
2. Update the relevant handoff doc next.
3. Archive one-off prompt files instead of keeping them in the root.
