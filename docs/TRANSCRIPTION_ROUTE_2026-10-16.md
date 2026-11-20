# Transcription route — 2026-10-16

User priority (2026-10-16): the AI should transcribe any song as accurately as
possible **before** any UI/graphics/layout polish. Inherited (pre-recovery) AI work
is treated as unverified. This note condenses the measured evidence into a route.
It adds no new experiment; numbers come from the reports named below.

## Where accuracy stands

| Path | Where it runs | Measured F1 at 50 ms |
|---|---|---|
| Inherited onset detector + classifier | **The app's actual "generate chart" path** (`ai-pipeline/pipeline/process.py`) | .490 on 7 MDB recordings; .544 on 2 reserved Clone Hero charts |
| Stereo htdemucs_ft separation → ADTOF Frame-RNN → primary decoder | Recovery tools only (`tools/recovery/transcribe_reference.py`, `package_song.py`); produced both m!sa drafts | .788 on 7 MDB; .800 on 6 ENST; .856 on 2 reserved charts |

Sources: `TRANSCRIPTION_DIAGNOSTIC_2026-10-14.md`, `ADTOF_MODEL_CONVERSION_AUDIT_2026-10-15.md`,
`SNARE_ADDITION_VALIDATION_2026-10-15.md`, `CLONE_HERO_BENCHMARK_2026-10-14.md`.
Benchmark overlap with model training data is unknown; these are diagnostics, not
guaranteed accuracy on unseen songs. Chart scores are five-family agreement proxies.

Remaining ADTOF errors on the 7 MDB recordings (50 ms): snare 375 misses of 953
(concentrated in jazz/brush), hi-hat 178 false hits (precision .63), toms 38 of 81
found, cymbals 63 misses. On the two rock/metal reserved charts kick and snare are
about .98 F1; the hi-hat convention is .75. Errors persist when the model gets the
original isolated drums, so the model itself, not only separation, limits accuracy.

**Resolution gap.** ADTOF outputs five families only: kick, snare, toms (one class),
hi-hat, cymbals. It cannot express China vs crash vs ride, open vs closed hi-hat, or
which tom. The practice views and the user's own corrections (China at 1.000 s in
WHITE WAVES) need those distinctions. No local model has been shown to resolve them.

Closed routes (do not repeat): E-GMD Onsets-and-Frames replacement, frozen E-GMD
snare additions (validation gain .007 < .01), ADT_STR, DrumSep energy/presence and
isolated-stem correction, HH-microphone gating, threshold/gain/window sweeps,
blanket HH/CY suppression. Separate-and-Detect stays deferred.

## Honest ceiling

No published system transcribes every song perfectly. Off-the-shelf models on real
mixtures sit around .8–.9 F1 for five broad families, lower for finer classes. A
realistic goal: the best measurable automatic draft plus fast correction in the
editor, and a model that improves from verified corrections.

## Recommended route

1. **DONE 2026-10-16** (`ADTOF_ENGINE_INTEGRATION_2026-10-16.md`: end-to-end F1
   .788/.800/.867 vs legacy .511/.598/.576). **Put the measured-better engine in the app (no training, no downloads).** Make
   stereo separation + ADTOF + primary decoder the app's transcription engine, keep
   the inherited path only as an explicit fallback, keep the desktop/CLI contract in
   sync, and re-measure through the real app path (audio → `chart.bsm`) on the same
   fixed benchmarks. Expected effect on the benchmark: about .49 → .79 F1. Licensing:
   the local ADTOF PyTorch port has no LICENSE file; personal local use is fine, but
   rights must be established before distributing the app or weights.
2. **Broaden the fixed evaluation.** "Any song" needs held-out real recordings across
   genres with known training overlap (ENST, MDB, IDMT, admitted Clone Hero charts,
   plus a few targeted user-verified passages from the m!sa songs). Freeze it before
   any training, and group performances across kit renders.
3. **Train a finer-class model.** Candidates: STAR (181 GB on D:, resynthesized drums
   with real accompaniment, per-track license limits), E-GMD, Groove MIDI, Slakh.
   Target at least kick, snare, closed/open HH, ride, crash, China/splash and
   high/mid/low toms. Requires GPU time; the RTX 3080 Ti was 81% busy with the separate
   mkai training campaign on 2026-10-16, so schedule with the user. ENST commercial use
   needs extra consent; STAR rights are per track.

**Update (later 2026-10-16):** step 2 is done (`EVAL_SET_V1_2026-10-16.md`) and step 3 is
planned in `FINER_CLASS_TRAINING_PLAN_2026-10-16.md`. The user decided BeatSight is personal
and study use only, so the license and rights caveats above no longer restrict which data
or models are used; the user then gave the assistant full GPU access.

Step 1 is the largest measured gain available now and needs no new data. Steps 2–3
are where "near-perfect" and fine instrument detail must come from.

## Deferred until transcription is good

All UI polish: zoom/look-ahead restore (approved by the user; see
`VISUAL_BASELINE_DIAGNOSIS_2026-10-16.md`), deterministic toolbar capture, baseline
refresh, 3D/manuscript layout problems. The user's saved PlaybackZoomLevel is 0.2;
handle that setting deliberately when the zoom restore happens.
