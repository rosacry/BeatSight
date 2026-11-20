# Frozen E-GMD snare addition — 2026-10-15

## Outcome

The single predeclared snare addition **passes all five development gates**.
At 50 ms, pooled F1 rises **.788049 → .815872**, with **123 extra matched
snares and 21 false additions**. Every original ADTOF event is retained; all
other families are identical. This is a candidate for independent validation,
not a promoted model, app default, or replacement user chart.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-oaf-snare-addition-01`.

Recovery verified **991 unique protected files**: the preceding experiment's
810 prior entries, 89 protocol entries and 169 final-manifest entries, with
overlap removed and the manifest itself included. All 2,090 saved E-GMD notes,
both tolerance scores and the complementarity counts were reproduced. The
repository inventory includes 11,263 ignored paths and 88 untracked paths before
this change; those path lists are inventories, not claims that every ignored
file was hashed. Source/documents were archived with read-back verification.

## Predeclared rule and execution

`protocol.json` and `prepared.json` were saved before scoring the merged charts.
They protect 52 input/code entries. The only candidate is
`native-snare-chronological-addition-v1`:

1. Keep every ADTOF event, including its timestamp and all fields.
2. Consider only native E-GMD pitch 38 events, already decoded at native onset
   probability strictly greater than .5. No additional confidence filter.
3. Visit those events in ascending time, breaking ties by native event index.
   Reject a candidate within **50 ms inclusive** of any ADTOF snare, including
   one later in time. Otherwise reject it within 50 ms of an earlier accepted
   addition. A rejected native event never blocks a later one.
4. Copy accepted events exactly, then stably sort all events by time. Other
   families never block a snare and are never removed or changed.

The floating-point boundary epsilon is 0.000001 ms. The radius uses the existing
50-ms evaluation tolerance as a fixed duplicate window; it was not selected by
comparing scores. This is a heuristic with a known risk: genuine flams/fast rolls
within 50 ms may be blocked, and duplicate attacks farther apart may survive.
Earliest-first does not imply strongest or best-timed.

The merger receives predictions only. Annotations enter afterwards for scoring.
Of 694 native snare events, 544 collide with baseline snares, six collide with
earlier additions, and 144 are added. No parameter/radius/order sweep, timing
shift, relabeling, new separation, model inference, download or training occurred.

Same seven complete MusicDelta development recordings: 454.934 seconds, 2,461
reference events, including 32 OT targets. Scoring retains the existing six-family
mapping and maximizes one-to-one matches, then minimizes absolute timing error.
See the [preceding source/runtime audit](OAF_DRUMS_COMPARISON_2026-10-15.md) for
pinned official source/checkpoint provenance. Those saved source hashes were
verified again. The cached execution remains TF2.13 compatibility, **not proven
historical TF1 runtime parity**. E-GMD's grouped snare/x-stick/clap output cannot
establish those individual articulations or brush technique.

## Results

| Tolerance / arm | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 25 ms ADTOF | 1772 | 386 | 689 | .821131 | .720033 | .767266 |
| 25 ms addition | 1872 | 430 | 589 | .813206 | .760666 | .786059 |
| 50 ms ADTOF | 1820 | 338 | 641 | .843373 | .739537 | .788049 |
| 50 ms addition | 1943 | 359 | 518 | .844049 | .789516 | .815872 |

| Recording | Added | Matched / false additions at 50 ms | Baseline F1 | Addition F1 |
|---|---:|---:|---:|---:|
| 80sRock | 0 | 0 / 0 | .813008 | .813008 |
| CoolJazz | 82 | 69 / 13 | .531969 | .641204 |
| SpeedMetal | 2 | 1 / 1 | .946274 | .946459 |
| Beatles | 0 | 0 / 0 | .666667 | .666667 |
| FreeJazz | 50 | 45 / 5 | .777862 | .815194 |
| FusionJazz | 7 | 5 / 2 | .877953 | .881720 |
| Punk | 3 | 3 / 0 | .937028 | .945000 |

Snare 50-ms TP/FP/FN changes **578/18/375 → 701/39/252**. Recall rises
.606506 → .735572, while snare precision falls **.969799 → .947297**. Snare
F1 rises .746288 → .828116. At 25 ms, snare TP/FP/FN is 672/68/281 and precision
is .908108. The global precision gate does not guarantee unchanged family precision.

All other 50-ms family counts remain: KD 589/41/63; HH 303/178/65;
TT 38/19/43; CY 312/82/63; OT 0/0/32. Their 25-ms counts are also unchanged.
All 2,158 baseline events and 1,562 non-snare events survive exactly. No previously
matched snare reference becomes unmatched at 50 ms.

The fixed 50-ms safeguards all pass: F1 gain .027823 ≥ .01; pooled precision
improves .000675; worst recording F1 change is zero (limit −.02); tom matches
remain 38; snare recall increases .129066 (allowed loss .01).

Timing is a limitation, not a fitted correction. For the 123 matched additions at
50 ms, median absolute error is **15.708 ms**, p90 **31.014 ms**, and median signed
error **−14.412 ms** (early). Only 100 additions match at 25 ms; 44 do not.
Pooled 50-ms timing changes from median absolute/p90 9.167/17.500 ms to
9.337/18.700 ms. A larger tolerant match count does not establish tighter timing.

## False-addition inspection

Every one of the 21 false additions is exported in
`evidence/false-additions.json` and inspected in
`evidence/false-addition-inspection.json`. None has any SD reference within
50 ms, so these are not merely optimal-assignment ties consuming a nearby snare.

| Inspection group | Count | Evidence |
|---|---:|---|
| Nearest snare 50–100 ms away | 7 | All CoolJazz; timing versus extra-hit ambiguity |
| Another family within 50 ms | 7 | Four FreeJazz tom coincidences; one SpeedMetal HH; one FreeJazz KD; one FusionJazz KD+CY |
| No reference within 50 ms and snare over 100 ms away | 7 | Six CoolJazz; one FusionJazz |

These are reference-based candidate explanations, not verified instrument labels.
All 21 waveform panels were inspected. Several CoolJazz predictions precede a
nearby stronger transient or occur in a decaying/quiet interval; waveform shape
alone cannot identify a snare, validate an annotation, or justify a global shift.
No listening-based correction or scoring mask was made.

`review/review.html` presents every case with a reference/prediction timeline and
42 mix/stem excerpts. Every excerpt is sample-exact float PCM from the saved
input, with 1.5 seconds on each side (clipped at source ends), no normalization.
`review/false-additions-overview.png` and `false-additions.csv` provide compact
inspection views. Clip hashes, source hashes and exact frame boundaries are in
`review/clip-manifest.json`.

The earlier reference-aware complementarity count was 131 native-only snare
targets, not an achievable merger score. Eight of those targets remain missed:
six native events collide with ADTOF, one collides with an earlier addition, and
one accepted event is optimally assigned to a different reference. Specifically,
FreeJazz 100.275374 s matches 100.292708 s, leaving 100.245833 s missed. This
assignment detail does not authorize changing the collision policy.

## Verification and preservation

Recovery tests: **84 passed in total**. The full run passed 83 with the optional
native-tokenizer integration skipped because its source variable was absent;
that one integration then passed separately with the pinned source enabled.
Parser, frontend and original-model integrations were enabled in the full run.
There was no rejected ADT_STR inference/control rerun. Preflight passed 19 tests.

Independent array-based reconstruction reproduces all **2,302 exported events**
without calling the merger. All saved scores, event assignments and gate decisions
reproduce. A separate greedy matcher confirms 136 per-arm/family/tolerance count
checks. All 991 prior hashes, 52 frozen protocol hashes and 42 excerpt roundtrips
pass. The verifier initially used the wrong text encoding for a test log; changing
that log-reader to UTF-8 fixed the check without altering rule, charts or scores.
Read `evidence/measurements-verification.json`, final `verification.json`, and
`final-artifact-manifest.json` before continuing.

D: and F: stayed read-only. New experiment files, caches and temporary files are
inside the scoped C: root. Existing experiments and ignored/untracked assets were
preserved. C: snapshots are local preservation, not independent-device backup.
No application default or user chart changed. Corrections remain WHITE WAVES
China at 1.000 s and Death Before Dishonor kick+crash at 8.750 s, with coincident
false HH removed. Blanket HH/CY suppression remains rejected. Knuckles' repeated
tapping sounds guitar-like per the user; its 35 disputed intro tom targets remain
unchanged and unmasked. KLEWS and Adapt were not used for tuning.

## Next step and limits

The gain is concentrated: **114/123 new matches (92.7%) are CoolJazz/FreeJazz**.
These seven repeatedly inspected, short recordings have unresolved training
overlap. This is development evidence, not independent full-song accuracy.

Keep this exact rule frozen. Next, use the existing local inventory to identify
separate annotated recordings with verified audio/label alignment and documented
performance/song overlap against both model training sources. Predeclare the
validation set and criteria before evaluation; do not tune the rule on it.
If training exclusion cannot be established, call it additional validation,
not proven independent generalization. Keep KLEWS's uncertain references and
reserved Adapt outside tuning. Do not sweep this rule on the seven development
recordings or start broad downloads/retraining.

Before promotion, also require full-song m!sa acceptance in the existing practice
views: preserve both supported opening corrections; verify native loading,
beginning/middle/end sync and seeking; inspect added snares, missed hits, rolls,
fills, quiet passages and simultaneous components against audio. Without checked
full-song labels, do not claim measured m!sa precision/recall. The current result
does not authorize replacing either corrected chart or an application default.
