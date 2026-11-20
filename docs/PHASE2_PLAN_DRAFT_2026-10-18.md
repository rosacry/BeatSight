# Phase-2 plan: draft with decision rules (2026-10-18, Claude)

Written BEFORE the phase-1 results exist. When `phase1-01` is scored, apply the rules below
unchanged, write the resulting config into `2026-10-18-phase2-train-01/protocol.json`, hash it,
and only then start the run. Do not tune these rules on the phase-1 or test numbers.

## Evidence this draft uses

- ADTOF baseline: eval set v1 tiers A .643, B .829, C .867, D .721, E .730; real-song chart tier
  (26 songs so far) five-family .883, merged cymbals .920 (KD/SD inflated by the keep rule).
- ADTOF's real-song errors (`chart-test-tier-01/results/adtof-26items-error-breakdown.json`):
  cymbals that coincide with kick/snare are the biggest loss; hi-hat false alarms on kicks and
  cymbals; soft hi-hats missed; tom/snare/kick confusion.
- Chart labels: KD and SD reliable; HH vs CY lanes follow charter conventions (some kept charts
  put hi-hats on cymbal lanes); ghost notes kept; roll lanes masked.
- Tools ready: `p2lib.py`/`p2train.py` (noisy-OR group loss, masks, held-out guards),
  `compare_candidates.py` (paired bootstrap; cluster bootstrap by artist on the chart tier).

## Decision rules

Comparison = `finetune-01/compare_candidates.py --run phase1-01` (eval set v1 and chart tier).

1. **Starting weights.** If phase1-01's 95% interval lower bound is >= -0.02 on tiers A, B, C and
   the chart tier (five-family), start from `phase1-01/best.pt` with lr 1e-4. Otherwise start
   from the ADTOF-initialised 16-class model (`init: adtof`) with lr 3e-4: synthetic-only
   fine-tuning that hurts real music is not a starting point.
2. **Chart supervision.** `chart_mode: five` (KD | SD+SS | toms | hi-hats | cymbals): HH-vs-CY
   confusion is a top error, so the run must learn it from real songs. Merged cymbals is the
   ablation only if rule 6 shows HH/CY getting worse.
3. **Mix.** `p_chart: 0.5` (half of training windows from real songs); synthetic sources keep
   the phase-1 weights for the other half.
4. **Data for run 1.** Kept, non-held-out charts of the pilot and chart corpus v1 (available after
   corpus-01 processing and `chart_labels.py --source corpus`). Corpus v2 joins in run 2 after its
   processing. Run 1 starts as soon as corpus-01 labels exist: stop `run_remaining_pipeline.sh`
   first (it will be in corpus-v2 processing), run phase 2, then rerun the pipeline script.
5. **Schedule and selection.** Same as phase 1: batch 32, validation every 2,000 steps, lr x0.2
   after 3 validations without improvement, stop after 8, at most 80,000 steps. Selection metric
   = equal-weight mean of the phase-1 synthetic metric and chart-validation group F1.
6. **After run 1** (score with the same tools): if the chart tier's CY or HH family F1 drops
   (interval upper bound < 0), try `chart_mode: merged`; if it rises, run 2 adds corpus v2 and
   the clean-stem variant arm.
7. **Clean drum-stem arm (run 2 or later).** For charts with real drum stems
   (`2026-10-18-clean-stems-01`), use clean features instead of separated ones with probability
   0.3. Compare against the same run without it; keep it only if the real-song tiers improve.

## Promotion gates (unchanged from the training plan)

- No significant drop on eval tiers A, B, C or the chart tier (interval upper bound < 0 fails).
- At least one of A, B or the chart tier significantly better (interval lower bound > 0).
- Full-song m!sa checks and the user's own listening before the app default changes; until then
  the model is available only through `process.py --fine-model`.

## Open choices left to the frozen protocol

- Per-chart cymbal handling (five-family for charts with consistent HH/CY lanes, merged for the
  rest) needs a p2lib change; only if run 1 shows convention noise.
- Audio augmentation (gain, EQ, reverb, codec) for robustness: candidate for run 3.
- Crowd-stem ablation (11% of corpus v1 packages include a crowd track in the mix).

## Amendment (2026-10-18 ~21:00, still before any phase-1 result)

The trainer config must now list `chart_sources`; run 1 uses `["pilot", "corpus"]`, run 2 adds
`"corpus2"`. A run refuses to resume if its data fingerprint changes (code amendment 02).
