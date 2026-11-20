# Phase 2, run 1 results: real-song charts + synthetic data (2026-10-23, Claude)

Run `2026-10-18-phase2-train-01/runs/phase2-01` (protocol frozen 2026-10-19 by the pre-written rules):
ADTOF-initialised 16-class Frame_RNN; half of training windows from 3,493 real-song charts
(pilot + chart corpus v1, 233.8 h, keep rule v1), half synthetic (phase-1 data); charts supervise drum
groups through a noisy-OR, roll lanes masked. 80,000 steps (paused/restarted several times from
checkpoints; a Windows Update restart cost ~4 min of training). Best validation metric .859 at step
70,000 (chart validation group F1 .911, synthetic family .834, fine .781).

## Five-family F1 at 50 ms vs ADTOF (paired bootstrap, 10,000 draws; chart tier resamples artists)

| Test set | Items | ADTOF | Phase 2 | Difference [95% interval] |
|---|---|---|---|---|
| A real, held out from ADTOF | 23 | .643 | .603 | -.040 [-.098, +.014] |
| B real, overlap possible | 48 | .829 | .774 | -.055 [-.084, -.023] |
| C commercial charts | 2 | .867 | .888 | +.021 [-.009, +.055] |
| D synthetic drums, real accompaniment | 26 | .721 | .807 | +.086 [+.045, +.135] |
| E electronic kit | 40 | .730 | .844 | +.114 [+.073, +.151] |
| **Real-song chart tier (98 artists)** | **202** | **.874** | **.897** | **+.023 [+.016, +.029]** |
| Chart tier, cymbals merged | 202 | .913 | .922 | +.009 [+.003, +.014] |

Chart tier by family: CY +.081 [+.058, +.105], HH +.072 [+.053, +.091], TT +.036 [+.011, +.061],
SD +.008 [+.003, +.015], KD +.001 [-.001, +.003].

For reference, phase 1 (synthetic only) on the same 202 songs: .749 (toms .43).

## Reading

- On held-out commercial songs, the target use, phase 2 is significantly better than ADTOF, mainly
  where ADTOF is weakest (cymbals, hi-hats, toms), and it keeps most of phase 1's synthetic gains
  plus the 16-class detail.
- On the ENST/MDB studio recordings it is lower; significant on tier B, where ADTOF may have trained
  on the same recordings (overlap possible), not significant on held-out tier A (23 items).
- Gates (`docs/PHASE2_PLAN_DRAFT_2026-10-18.md`): one real tier significantly better (chart tier) but
  tier B shows a significant drop, so phase2-01 is NOT promoted to the app default. It can be tried
  with `process.py --fine-model C:/Users/10ros/BeatSight-Recovery/2026-10-18-phase2-train-01/runs/phase2-01`.

## Next (rule 6: HH and CY rose, so no switch to merged cymbals)

Run 2 adds chart corpus v2 (6,423 charts; processing started 2026-10-23 19:18, ~2 days) and the
clean drum-stem arm (rule 7). The tier-B drop makes the planned forgetting guard (distilling ADTOF's
own family outputs on real audio) a candidate too; each needs a frozen amendment before its run.

## m!sa spot check (user songs, 2026-10-23)

`2026-10-23-model-comparison-01/compare_song.py` (same engine path, separation once, CPU) on the user's
two m!sa songs; beatmaps `adtof.bsm` / `phase2.bsm` with the audio beside them per song folder.
Kick/snare agree almost completely; phase 2 hears far more cymbals, hi-hats and toms (WHITE WAVES:
cymbal 695 vs 402, hi-hat 304 vs 212, tom 102 vs 50; Death Before Dishonor: 352 vs 159, 424 vs 232,
150 vs 73; plus 91 "percussion" hits there). At the user's ear-verified spots both models are wrong at
WHITE WAVES 1.000 s (china only: ADTOF adds closed HH, phase 2 open HH), and at Death Before Dishonor
8.750 s (kick + crash) ADTOF is right while phase 2 adds a false open hi-hat. On the 202-song tier phase 2
still has fewer hi-hat false alarms (11,618 vs 15,275; precision .806 vs .740), so this is a specific
pattern (big crash/china hits heard as open hi-hat), a candidate for run 2's cymbal-convention handling.
