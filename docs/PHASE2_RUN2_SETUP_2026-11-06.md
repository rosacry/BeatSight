# Phase 2, run 2 setup (2026-11-06, Claude)

Frozen protocol: `C:\Users\10ros\BeatSight-Recovery\2026-11-06-phase2-run2-01\protocol.json` (hashed in that root's
`evidence/protocol.sha256` before any run-2 training on real data). Pipeline:
`2026-10-16-feature-cache-01\run_remaining_pipeline_v8.sh` (run 2 only). `run-control\desired-state.json` names v8 and
is held **paused** until the user says to start (then `set_state.ps1 -State running` + `Start-ScheduledTask`).

## User decisions (2026-11-06)

- "Percussion" (OT) output: **dropped from app charts** (no chart lane; tier B 2,621 false vs 32 true hits). Done in
  `ai-pipeline/adtof_engine/fine.py` (`DROPPED_CLASSES = ("OT",)`, `decode_fine(..., drop_classes=())` keeps it),
  engine `beatsight-16class-4`, summary field `dropped_classes`; 24/24 engine/fine tests. ADTOF default unchanged.
- Meshuggah "Bleed" chart: **trained on** (corpus2 2661ba4a...). Bleed scores after run 2 are not a fair test.

## What run 2 changes (everything else as run 1)

| | Run 1 (phase2-01) | Run 2 (phase2-02) |
|---|---|---|
| Real-song charts | pilot + corpus v1: 3,493 train / 106 val (234 h) | + corpus v2: 6,809 train / 287 val (447 h) |
| Hi-hat / cymbal double firing | noisy-OR group loss only | + exclusivity term (sum - max of member probabilities) on HH and CY, weight 1, warmed up over 10,000 steps |
| Ghost notes | none | separate ghost-snare head on the detached trunk (cannot change transcriptions), trained on 3,098 ghost-marking charts |
| Init, schedule, selection | ADTOF init, lr 3e-4, <= 80,000 steps | same (plan rule 1 still says ADTOF init) |

Data check (`evidence/data-check.json`): no duplicate songs across corpora, no chart-tier song in training, the
Oblivion chart is in no corpus. Deferred to run 3 (reasons in the protocol): clean drum-stem arm (only 873 train
charts have clean stems, ~4% of windows), codec/mastering augmentation, HH/CY convention handling, forgetting guard.

Why the warm-up: the ADTOF initialisation copies one cymbal row to RD/RB/CR/CH/SP (and one hi-hat row to
HHC/HHP/HHO), so at step 0 every member is tied and the max would always be the first class (ride) - the
"ride over-played" complaint. Found in the CPU smoke test before freezing.

## After training (pre-registered, each once)

P1 frozen tools vs ADTOF (as run 1). P2 the app decode (W20 + C20 + no percussion) for phase2-02 and phase2-01,
paired vs ADTOF and vs each other; promotion gates judged on P2. P3 ghost threshold on chart validation, then one
test on chart-tier songs with >= 20 ghosts; offered for the app only if test F1 > .604 (the loudness heuristic).
P2/P3 scripts (`score_app_decode.py`, `ghost_select.py`) are written and hashed while training runs; v8 runs them.

## Expected time

Training ~4-4.5 h (run 1: ~3.5 h of steps at ~6.3 steps/s; validation now covers 287 charts), evaluation ~3 min,
chart tier ~10 min (CPU). Pausing is safe: checkpoints every 2,000 steps (~5-6 min).

Tests: `tests/test_r2lib.py` 10/10 (run-1 loss reproduced exactly at weight 0, exclusivity values, trunk state ==
logits, head detached, ghost targets, dataset replays run-1 draws). CPU smoke runs `runs/smoke-r2-01`/`-02`
(train, validate, checkpoint, resume, app loader and evaluation loader read the checkpoint).
