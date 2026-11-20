# Real-song training data, test tier and phase-2 tooling (2026-10-16 to 2026-10-18, Claude)

Personal/study use only; nothing below is published. All roots are new scoped folders under
`C:\Users\10ros\BeatSight-Recovery`; D: and F: are read only. Every protocol was frozen and hashed
before the step it governs (`evidence/protocol.sha256` in each root).

## Chart data (rhythm-game charts with their real song audio)

| Root | What | Size | Status |
|---|---|---|---|
| `2026-10-16-chart-pilot-01` | 500 reviewed pro-drums charts (Encore) | 32.6 h | Processed; keep rule v1 frozen: 344 kept (22.6 h) |
| `2026-10-17-chart-corpus-01` | remaining 4,560 reviewed charts | 306.8 h, 18.5 GB | Downloaded and hash-verified; processed after phase 1 |
| `2026-10-18-chart-corpus-02` | 6,423 more (drum review not required; songs already held dropped) | 408.7 h | Downloading (40 GB cap); processed features-only after corpus-01 |

- Keep rule v1 (pilot amendment 03) uses only what ADTOF is reliable at on ground truth: kick
  recall and precision >= .85, snare precision >= .85, plain-note snare recall >= .60, merged
  hi-hat+cymbal floors (.40/.50), kick/snare timing IQR <= 15 ms. Raw snare recall is not used:
  34% of ADTOF's chart-snare misses are ghost notes, so it would drop the most detailed charts.
- Label time = chart time + measured offset + 3 ms (ADTOF itself is ~3 ms early on real drums).
- About 41% of corpus-v2 packages are multitrack with the real isolated drum tracks
  (Rock Band layout drums_1 kick, drums_2 snare, drums_3 kit): ~95 h so far.

## Real-song test tier (`2026-10-18-chart-test-tier-01`)

- 8% of primary artists (sha256 rule) are held out of all training: 425 charts / 113 artists in
  pilot + corpus-01, plus 514 corpus-v2 charts by the same artists. Scored set: <= 5 charts per
  artist that pass keep rule v1 (262 candidates, 17.4 h).
- ADTOF on the 26 scorable songs so far: five-family F1 .884 (KD .98, SD .96, TT .83, HH .71,
  CY .72); merged cymbals .920. Kick/snare are inflated by the keep rule; hi-hat, cymbal and tom
  are the fair signals.
- ADTOF's real-song errors: cymbals coinciding with kick/snare are the largest loss; hi-hat false
  alarms on kicks/cymbals; soft hi-hats missed; tom/snare/kick confusion
  (`results/adtof-26items-error-breakdown.json`).

## Labels and training code

- `2026-10-18-phase2-chart-labels-01`: kept charts -> training labels (offset shift, roll-lane
  placeholders dropped and masked, ghost/accent/double-kick flags, held-out marking). Pilot: 344
  charts, 656,965 events, 253 roll masks, 0 failures; 6 tests.
- `2026-10-18-phase2-train-01`: mixed synthetic + chart windows; chart items supervise groups
  (KD | SD+SS | toms | hi-hats | cymbals, or merged cymbals) through a noisy-OR of member
  classes; synthetic items keep 16-class supervision; held-out artists refused twice; 11 tests,
  CPU smoke run and a one-batch overfit check.
- Decision tools: `finetune-01/compare_candidates.py` (paired bootstrap; cluster bootstrap by
  artist on the chart tier; self- and planted-gain tests) and `docs/PHASE2_PLAN_DRAFT_2026-10-18.md`
  (phase-2 rules written before phase-1 results).
- App: `process.py --fine-model DIR` runs a 16-class model; default unchanged
  (`docs/FINE_MODEL_ENGINE_SUPPORT_2026-10-18.md`).

## Clean drum stems (`2026-10-18-clean-stems-01`)

- Features from the real drum sum (normalised like the engine's mix), features only. Sanity on
  2 pilot charts: identical frame counts, zero lag, ~0.91 correlation with separated features.
- Clean-mix QC (amendment 01): ADTOF on the clean drum sum with the frozen QC and keep rule; it
  will show which charts rejected on the separated mix are accurate but in hard mixes. Metric code
  proven identical to the recorded extended QC; quality() differences come only from float16
  feature storage. No training use until a phase-2 protocol amendment.
- Isolated-stem onset QC was rejected: the stems carry heavy bleed.

## Incidents and fixes

- 2026-10-18 ~18:57 the PC hard-reset (no driver/hardware errors logged). Verified after reboot;
  the corpus-v2 download log had a NUL tail (repaired; 90 unverifiable files re-downloaded). My
  repair first wrote CR CR LF line endings and broke one download pass; fixed byte-exact.
- D: was missing after the reboot; the old log-pattern chains then started corpus processing
  early (stopped after ~12 min). Replaced by one strict-order script, now
  `feature-cache-01/run_remaining_pipeline_v2.sh`.
- From 19:51 separation ran ~4x slower: htdemucs_ft's CUDA cache reached 10.7 GB on full-length
  songs and the 12 GB card paged. Separation steps now release cached memory after each song
  (`run_cache_empty_cache.py`, `run_with_empty_cache.py`; outputs unchanged): ~2-3 GB, ~12.5x.
- The GPU runs at 83-89 C with software thermal slowdown; a user-set power cap would help.
