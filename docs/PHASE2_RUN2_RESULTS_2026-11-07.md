# Phase-2 run 2 (phase2-02) results — 2026-11-07

Root: `C:\Users\10ros\BeatSight-Recovery\2026-11-06-phase2-run2-01` (protocol.json frozen 2026-11-06 18:35, scripts
hashed in evidence/protocol.sha256 before any result). Pipeline v8 "run 2 all done" 2026-11-07 01:05:35 (exit 0).
Every procedure below ran once, as pre-registered.

## Training

- Started 2026-11-06 18:45; paused by the user 21:45 at step 56,000 (last.pt), resumed 23:11 (`resumed_at` 56000).
- Stopped by patience at step 76,000 (8 validations without improvement); best checkpoint step 60,000
  (selection metric .8389: synthetic family .812, fine .758, chart-validation group F1 .893 on 287 charts).
- For reference, phase2-01's best was step 70,000 with synthetic family .835 / fine .781. Its chart-validation figure
  used a smaller validation set, so it is not comparable.

## P2: as the app decodes (the gates are judged here)

Engine beatsight-16class-4: per-class thresholds, then W20 hi-hat, then C20 ride/bell/crash, then no percussion.
Paired bootstrap with 10,000 draws; the chart tier uses an artist-cluster bootstrap (98 artists, 202 songs).

| Test set | ADTOF | run 1 | run 2 | run 2 − ADTOF [95%] | run 2 − run 1 [95%] |
|---|---|---|---|---|---|
| A real held-out (23) | .643 | .638 | .622 | −.022 [−.066, +.027] | **−.017 [−.031, −.001]** |
| B real, overlap possible (48) | .829 | .859 | .859 | **+.029 [+.010, +.052]** | −.000 [−.009, +.007] |
| C commercial charts (2) | .867 | .899 | .899 | +.032 [−.011, +.079] | −.000 [−.009, +.010] |
| D synthetic drums + real mix (26) | .721 | .789 | .789 | **+.068** | +.000 |
| E e-drum only (40) | .730 | .842 | .840 | **+.110** | −.002 |
| Chart tier, five families (202) | .874 | .907 | .904 | **+.030 [+.023, +.037]** | −.003 [−.006, +.000] |
| Chart tier, cymbals merged (202) | .913 | .932 | .934 | **+.021 [+.015, +.026]** | +.001 [−.001, +.004] |

Chart tier by family (run 2 − run 1): CY −.003 [−.011, +.005], HH +.002 [−.010, +.013], KD +.001, SD +.001,
**TT −.032 [−.044, −.022]** (run 1 .823, run 2 .791, ADTOF .787).

**Gates against ADTOF:**
- **Run 2 passes:** no tier has an upper bound below 0; B and the chart tier are significantly better.
- **Run 1 also passes now** with the full app decode (B +.029 [+.007, +.055]; chart tier +.033). Its October
  tier-B drop came from the raw decode and was removed by W20, C20 and dropping percussion.

**Run 2 against run 1:** a tie everywhere except toms (worse) and tier A (worse).
- The exclusivity term did not change hi-hat or cymbal family scores beyond what the C20/W20 decode already gives.
- These scores do not separate ride from crash. That question is left to listening.

## P1: frozen tools, raw decode, vs ADTOF (reported alongside)

| Tier | Diff [95%] |
|---|---|
| A | −.043 [−.091, +.007] |
| B | −.028 [−.055, +.001] |
| C | +.025 |
| D | +.079 |
| E | +.112 |
| Chart five-family | +.024 [+.017, +.031] |
| Chart cymbals merged | +.014 [+.009, +.019] |

## P3: ghost snares (learned head)

- **Validation** (115 ghost-marking charts, 42,057 matched snares, 6,169 ghosts): threshold T = 0.30, F1 .865
  (precision .875, recall .857), AUROC .987.
- **Test, once** (73 chart-tier songs with ≥ 20 charted ghosts, 31,837 matched snares, 6,298 ghosts): F1 **.820**
  (precision .824, recall .817), AUROC .977.
- The October loudness heuristic scored F1 .604 on this test set.
- `offer_to_app = true`. Adding it needs the user's OK and an engine change: load `best.pt["ghost"]`, run the head
  on run 2's trunk, and mark snares with probability ≥ 0.30 as ghosts (velocity about 0.3).
- The head reads run 2's trunk, so ghost notes come with run 2's model. Pairing run 1's notes with run 2's ghost
  head would be a new, untested setup.

## What is decided and what is not

- Nothing in the app changed. The desktop still uses ADTOF; the 16-class engine is only reachable through
  `process.py --fine-model`.
- Promotion of either model still needs the user's listening (FINE_MODEL_ENGINE_SUPPORT: desktop wiring waits for a
  model that passes the gates and the listening).
- The Bleed chart is now in training, so it is not a fair test for run 2. Oblivion is in no corpus.
- Run-3 candidates (deferred in the protocol): clean-stem arm and clean-QC rescue, codec/mastering augmentation,
  HH/CY convention handling. New: find out why toms dropped from run 1 to run 2. One possibility is corpus-2 tom
  conventions, or the 60k vs 70k checkpoint; this is untested.

## Listening maps (2026-11-07 evening, user: "Yes, build them")

Root: `C:\Users\10ros\BeatSight-Recovery\2026-11-07-model-comparison-04`. Launcher: `Open model comparison in
BeatSight.cmd`, which uses an isolated library through BEATSIGHT_USER_ASSET_ROOT. The user's own library is not
touched.

**What `build_maps.py` does**
- Runs one seeded htdemucs_ft separation per song (GPU, ~30 s per song) and feeds all three models from it.
- Uses the app decode: ADTOF decoder, and decode_fine for run 1 and run 2.
- For run 2, snares with ghost probability ≥ .30 get velocity 0.25. Playback draws velocity < .35 smaller and fainter.

**Checks (all pass)**
- Audio hashes match the October maps.
- Run 2's hidden-state path equals the model output.
- Ghost velocity is set only on snares.
- All 20 maps pass the beatmap schema.
- The run-1 maps equal October's, minus the dropped percussion notes. WHITE WAVES, DbD, TSatS, Bleed and Oblivion
  (chart audio) are identical. Oblivion (MP3) keeps 4,009 of 4,030 notes, because its separation ran on the GPU
  instead of the CPU.

Ghost snares in run 2's maps:

| Song | Ghost snares / snares |
|---|---|
| WHITE WAVES | 131 / 492 |
| Death Before Dishonor | 45 / 228 |
| The Sin and the Sentence | 8 / 771 |
| Bleed | 2 / 386 |
| Oblivion | 16 / 892 |
| Oblivion (chart audio) | 15 / 917 |

Oblivion against Ziggy's chart, with the frozen chart-tier scorer (`score_oblivion.py`; it reproduces October's
.899 for the October run-1 map). Oblivion is not in any training data. Format: F1, then toms / hi-hat.

| Audio | ADTOF | Run 1 | Run 2 |
|---|---|---|---|
| Chart audio | .840 | **.900** (toms .885 / hi-hat .532) | .886 (toms .848 / hi-hat .462) |
| User's MP3 | .715 | **.756** (toms .663 / hi-hat .167) | .753 (toms .536 / hi-hat .089) |

This one song shows the same tom drop for run 2 as the 202-song tier.

## Files

- `runs/phase2-02/{comparison.md,eval-report.json,thresholds.json}` (P1)
- `results/app-decode-comparison.{md,json}` (P2)
- `results/ghost-validation.json`, `results/ghost-test.json` (P3)
