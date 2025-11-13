# Production Provenance Audit (prod_combined_events.jsonl)

_Updated: 2025-11-08_

## Snapshot
- Manifest: `ai-pipeline/training/data/manifests/prod_combined_events.jsonl`
- Total events inspected: 3,007,914
- Global checks: no missing `source_set` values, no broken `metadata_ref` links, no unknown sources
- Source sets promoted into production: `slakh2100`, `groove_mididataset`, `enst_drums`, `idmt_smt_drums_v2`

## Dataset Coverage

| Source set | Events in manifest | Referenced sessions | Unreferenced provenance sessions | Notes |
|------------|-------------------:|--------------------:|---------------------------------:|-------|
| `slakh2100` | 2,542,864 | 1,708 | 0 | Full coverage; synthetic baseline remains byte-identical to provenance |
| `groove_mididataset` | 411,455 | 1,150 | 0 | Full coverage; GM-to-taxonomy mapping unchanged |
| `enst_drums` | 45,704 | 318 | 0 | Newly merged; parity with provenance confirmed |
| `idmt_smt_drums_v2` | 7,891 | 284 | 0 | Newly merged; parity with provenance confirmed |
| `musdb18_hq` | 0 | 0 | 150 | Multitrack stems still staged pending bleed-aware ingest |
| `signaturesounds` | 0 | 0 | 246 | One-shot packs awaiting density weighting strategy |
| `telefunken_sessions` | 0 | 0 | 143 | Live sessions queued until per-hit annotation pipeline matures |

## Interpretation
- Production manifest now spans Groove MIDI, Slakh2100, ENST Drums, and IDMT SMT V2. All four report zero provenance gaps, validating the merge.
- Staged corpora (MUSDB18 HQ, SignatureSounds, Telefunken) remain inventory-only; their provenance files stay intact so automated audits flag their exclusion explicitly.
- Event count increase (+53,595) leaves global checks clean, demonstrating that provenance discipline scales with additional datasets.

## Inclusion Guidance
### In Production
- **Slakh2100**: Continue treating as synthetic backbone; monitor loudness normalization drift when regenerating stems.
- **Groove MIDI Dataset**: Keep GM mapping validation in regression suite; verify MIDI-to-audio renders remain deterministic.
- **ENST Drums**: Track class balance against Groove/Slakh; add LUFS span check for isolated hits in health gate.
- **IDMT SMT Drums V2**: Ensure loudness normalization stays within readiness thresholds; re-run leakage analysis once additional live sets arrive.

### Staged (Not Yet Merged)
- **MUSDB18 HQ**: Requires improved bleed suppression and onset alignment before manifest promotion.
- **SignatureSounds One-Shots**: Needs sampling-weight policy to avoid skewing event density.
- **Telefunken Sessions**: Await onset/annotation tooling to turn multitrack sessions into unit events.

## Recommended Actions
1. Regenerate `ai-pipeline/training/reports/health` via `run_readiness_checks.py` on the updated manifest and confirm class thresholds remain satisfied.
2. Commit the refreshed provenance baseline (`prod_combined_provenance_audit_baseline.json`) so CI audits track the new coverage.
3. Add regression tests for ENST/IDMT label distributions to guard against future manifest regressions.
4. Keep staging datasets' provenance tagged as inventory-only in `DATASET_READINESS_PLAN.md` to prevent accidental merges.
