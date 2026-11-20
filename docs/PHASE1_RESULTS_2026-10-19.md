# Phase 1 results: 16-class fine-tune on synthetic data (2026-10-19, Claude)

Run `2026-10-16-finetune-01/runs/phase1-01` (protocol frozen 2026-10-16): ADTOF Frame_RNN with a
16-class head, trained on synthetic/electronic-kit data only (STAR 6,035, E-GMD 35,217, Slakh 1,145,
Groove 846 items). Paused twice at the user's request (resumed from checkpoints at steps 6,000 and
0); stopped early at step 48,000 (lr decayed to 2.4e-6); best validation metric .811 (from .563 at
step 0). Baseline gate passed exactly before scoring.

## Five-family F1 at 50 ms vs ADTOF (paired bootstrap, 10,000 draws; chart tier by artist)

| Test set | Items | ADTOF | Phase 1 | Difference [95% interval] |
|---|---|---|---|---|
| A real, held out from ADTOF | 23 | .643 | .623 | -.021 [-.070, +.026] |
| B real, overlap possible | 48 | .829 | .764 | -.065 [-.101, -.025] |
| C commercial charts | 2 | .867 | .817 | -.051 [-.058, -.042] |
| D synthetic drums, real accompaniment | 26 | .721 | .833 | +.112 [+.070, +.164] |
| E electronic kit | 40 | .730 | .857 | +.127 [+.080, +.172] |
| Real-song chart tier (25 artists) | 26 | .883 | .746 | -.137 [-.158, -.117] |

Chart tier by family: KD -.014, SD -.070, HH -.128, CY -.130, TT -.422 (all intervals below 0).

## 16-class detail (new; ADTOF has none)

Tier B (real ENST/MDB recordings), classes with >= 100 events: HHC .77, HHO .77, RD .63, CR .56,
SS .53, HT .50, LT .31, MT .28, CB .26, RB .01. Synthetic tiers are higher (tier E: RD .96, HHP .82,
CR .83, RB .80). Weak everywhere: rare classes (CH, SP, CB, RB on real audio) and tom identity.

## Reading

Synthetic-only fine-tuning taught the model synthetic timbres and the fine classes, but cost
real-music accuracy: it forgot part of what ADTOF learned from real songs. This fails the
promotion gates (no app change) and is exactly why phase 2 trains on real-song charts.

## Decision (rules written before these results: `docs/PHASE2_PLAN_DRAFT_2026-10-18.md`)

Rule 1: real-tier lower bounds are below -.02, so phase 2 starts from the ADTOF-initialised model
(lr 3e-4), not from phase1-01. Frozen as `2026-10-18-phase2-train-01/protocol.json` (run
`phase2-01`: chart_mode five, p_chart 0.5, chart sources pilot + corpus v1). It starts once chart
corpus v1 is processed and labelled. Candidate for run 2 if real music still drops: distil ADTOF's
own family outputs on real songs as a guard against forgetting.
