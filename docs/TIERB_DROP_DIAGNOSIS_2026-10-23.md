# Phase 2 tier-B drop: diagnosis and a hi-hat decode rule (2026-10-23, Claude)

Root `C:\Users\10ros\BeatSight-Recovery\2026-10-23-tierb-drop-diagnosis-01` (CPU only, every input read only,
no training). Read `protocol.json` first: it was written and hashed (`evidence/protocol.sha256`, 20:05)
after the diagnosis and before any validation number of the rule.

## Why phase2-01 lost on ENST/MDB tier B

`diagnose.py` re-ran phase2-01 on the eval set on CPU (within 2 events per tier of the stored GPU report;
ADTOF's beatmaps rescore exactly) and attributed every false hit to what the ground truth has within 50 ms
(`evidence/diagnosis.json`). It was not forgetting: kick is equal, snare and toms are better. The drop is:

- **Hi-hat double firing.** 1,572 of phase 2's 2,432 tier-B hi-hat false hits are a second or third hi-hat
  sub-class (closed, pedal, open) on a stroke another prediction already matched. ADTOF has one hi-hat
  output, so it cannot do this. Eval v1 scores every fine prediction as a hit; training validation
  collapsed only exact-time duplicates, so model selection never saw it.
- **The "other" class.** 2,621 false "other" hits on tier B (32 true), mostly on hi-hat and ride strokes;
  it also displaces truth hi-hats (about 390 tier-A hi-hats are missed where "other" fires instead). It is learned
  only from synthetic data (E-GMD, STAR, Slakh) and tuned on synthetic validation.
- **Pedal hi-hat.** ENST has no pedal hi-hat label at all; phase 2 predicts 1,560 on tier B (14 match).
- Cymbals stay lower on tier B (.719 vs .811), partly crash/ride/ride-bell duplicates.

## Rule, validation-only choice and single test scoring

Rule `hh_family_combine` (protocol stage 2): after the unchanged peak picking, closed/pedal/open hi-hat
peaks within W of the retained left peak become one event with the strongest sub-class label. A hi-hat is
one instrument; ADTOF's decoder already keeps one event per class within 20 ms. Variants W20 and W50 only.

Validation only (686 synthetic items + 106 chart-validation songs, `evidence/validation-combine.json`):
W20 chosen by the frozen rule. All-family F1 +.0061 synthetic / +.0011 charts; hi-hat F1 +.0178 / +.0068.
STAR's hi-hat F1 alone dips .756 to .749 (its labels contain simultaneous hi-hat sub-classes). Most
cross-sub-class pairs are 0-10 ms apart, so W50 adds nothing.

Test sets scored once (`results/`, frozen `compare_candidates.py`; 'none' = same CPU predictions without
the rule, identical to the stored phase2-01 comparison, chart tier 202/202 rows identical):

| Test set | ADTOF | phase2-01 | phase2-01 + W20 | W20 vs ADTOF [95%] |
|---|---|---|---|---|
| A real held out (23) | .643 | .603 | .608 | -.035 [-.094, +.021] |
| B real, overlap possible (48) | .829 | .774 | .805 | -.024 [-.053, +.006] |
| C commercial charts (2) | .867 | .888 | .893 | +.026 [-.003, +.058] |
| D synthetic drums (26) | .721 | .807 | .802 | +.081 [+.048, +.122] |
| E electronic kit (40) | .730 | .844 | .844 | +.115 [+.073, +.152] |
| Chart tier (202 songs, 98 artists) | .874 | .897 | .898 | +.024 [+.018, +.031] |
| Chart tier, cymbals merged | .913 | .922 | .923 | +.010 [+.004, +.016] |

Chart-tier hi-hat +.072 to +.079 [+.060, +.098]; the chart tier was not used for the diagnosis. Tier B
hi-hat F1 .778 to .870 (ADTOF .858); tier B without the "other" family .859 vs ADTOF .839.

## What this does and does not mean

- With W20 decoding, phase2-01 passes the numeric promotion gates (no significant drop on A, B, C or the
  chart tier; chart tier significantly better). The idea came from looking at tier B; its parameters were
  fixed beforehand and chosen on validation, and the untouched chart tier agrees.
- Not promoted: the gates also require full-song m!sa checks and the user's listening. The rule cannot fix
  the two ear-verified m!sa errors (crash + open hi-hat on the same big hit: a cross-family confusion).
  It does remove same-stroke hi-hat duplicates there (Death Before Dishonor: 117 of 424 hi-hat events
  are in pairs within 20 ms; WHITE WAVES 30 of 304).
- In the app since 2026-10-23 ~21:00 (user approved): `ai-pipeline/adtof_engine/fine.py` applies the rule
  on the experimental `--fine-model` path (engine version beatsight-16class-2); ADTOF stays the default.
  Tests check it against the research implementation. New m!sa beatmaps for listening:
  `2026-10-23-model-comparison-02` (ADTOF vs "Phase 2 + hi-hat fix").

## Inputs for the run-2 amendment

- Decode and select with the rule: run 2's validation should score like eval v1 (no duplicate collapse)
  with `hh_family_combine` W20, so selection sees what the app shows.
- Forgetting guard (ADTOF distillation): lower priority. KD/SD/TT did not regress; the remaining tier-B gap
  is the "other" class and cymbals, which ADTOF distillation does not address ("other" has no ADTOF row).
- "Other"/percussion: the largest remaining loss. On chart validation 1,804 "other" predictions fall
  mostly on charted snare/hi-hat notes (27% on no charted note). Options need the user: stop emitting it
  in practice charts (tier D cost about .013 in the diagnostic), or keep it and fix it in training.
- Cymbal convention (crash/china heard as open hi-hat) remains the m!sa issue. A ride/ride-bell combine
  (same cymbal) is a candidate; it needs its own pre-registered validation, not a test-set sweep.
