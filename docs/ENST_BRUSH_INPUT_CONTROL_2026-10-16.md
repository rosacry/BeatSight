# ENST brush input control — 2026-10-16

## Outcome

Original wet-drum audio improves both fixed models on the selected brush
recording, but **substantial instrument errors remain**. At50ms, ADTOF F1 rises
**.455866 → .544542**, and native E-GMD rises **.473853 → .507361**. This supports
an input-condition contribution on this recording. It does not isolate separator
damage from residual accompaniment, establish generalization, or reopen the
failed snare-addition promotion decision.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-16-enst-brush-input-control-01`.

No app/default, user chart or practice-view behavior changed. No m!sa acceptance
run, new separation, model download, retraining, or threshold/gain/radius sweep.

## Recovery and frozen contrast

Before inference, **1,647 unique protected files** matched their hashes, including
the previous validation's472 manifest entries and the manifest itself. Previous
2,909 merged events,3,043 native notes, scores, assignments and gates reproduced
using the read-only verifier redirected to this new root.90 existing source/docs
files were archived with hash readback; ignored/untracked paths were inventoried.
`protocol.json` was frozen before inference and protects **249 entries**.

One recording was fixed by the preceding handoff:
`enst-drummer_1-110_minus-one_musette_brushes`,75.16s,416 reference events:
KD87,SD189,HH52,TT26,CY62. It was selected because it contributed28/35 false
additions in the previous validation. This is a diagnostic case selected after
observing errors, not a fresh held-out evaluation or a full-length user song.

The separated condition reuses the exact saved htdemucs_ft output and model
predictions. The only new input is the original stereo wet-drum recording at its
fixed contribution to the previously normalized mixture:

```python
mean((float32(.5) * original_stereo_wet.T.copy()) / 0.2924041748046875, axis=0)
```

The divisor is the saved mixture's mono peak, reproduced from the source audio.
There is no independently selected gain or peak normalization. The mono FLOAT
file has peak .8646872044 and round-trips exactly. Whole-record normalization
inside native E-GMD remains unchanged, as in the previous experiment.

ADTOF retains the checked frontend, corrected pooling, weights and decoder:
CPU,seed0,two threads. E-GMD reuses the **unchanged**
`validate_snare_addition.oaf` execution path, same official checkpoint/hparams,
CPU and native >.5 decoder. All78 variables restore exactly and the native
feature path matches the direct source frontend. Native notes are467 on original
input versus521 cached on separated input. **TF2.13 compatibility is not proven
historical TF1 parity**. Source/runtime/checkpoint artifacts are reused read-only.

Annotations, six-family mapping, event times and scoring tolerances remain fixed.
No masks or reference repairs. Local primary ENST/ADTOF mapping evidence was
rechecked, including `rc2`→59→CY and `mt`→48→TT; those families were not silently
mapped to HH/SD. Original microphone bleed and brush technique are not independent
per-event ground truth. Known upstream ENST evaluation exposure and unresolved
exact ADTOF/Demucs training overlap remain as documented in the
[validation report](SNARE_ADDITION_VALIDATION_2026-10-15.md).

The frozen snare merger is evaluated only as a secondary diagnostic. Original
drums are unavailable for arbitrary full songs, so this control has no promotion
gate. Its completion criteria are input/score verification and full error reporting.

## Results

| Input / model | 50ms TP | FP | FN | Precision | Recall | F1 | 25ms F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Separated / ADTOF |204|275|212|.425887|.490385|.455866|.411173|
| Original / ADTOF |217|164|199|.569554|.521635|.544542|.511920|
| Separated / native E-GMD |222|299|194|.426104|.533654|.473853|.465315|
| Original / native E-GMD |224|243|192|.479657|.538462|.507361|.498301|
| Separated / frozen merger |241|303|175|.443015|.579327|.502083|.460417|
| Original / frozen merger |241|173|175|.582126|.579327|.580723|.546988|

ADTOF produces **111 fewer false hits and13 more matches** on original input;
E-GMD produces **56 fewer false hits and2 more matches**. The merger has130 fewer
false hits and the same total matches, but does not match exactly the same targets.
Do not interpret the unchanged total241 as preserved event-level coverage.

| Family | ADTOF separated TP/FP/FN | ADTOF original | E-GMD separated | E-GMD original |
|---|---:|---:|---:|---:|
| Kick |64/50/23|52/1/35|46/26/41|26/0/61|
| Snare |88/6/101|107/14/82|102/35/87|102/14/87|
| Hi-hat |49/219/3|44/147/8|51/227/1|50/198/2|
| Tom |0/0/26|1/2/25|0/9/26|16/25/10|
| Cymbal |3/0/59|13/0/49|23/2/39|30/6/32|

The effects differ by family. ADTOF gains26 previously missed SD targets and
loses7, for net+19. E-GMD gains30 SD targets and loses30 despite unchanged SD TP.
Kick precision improves while kick recall falls for both. E-GMD recovers16 tom
targets, but also produces25 false toms, so this does not justify tom fusion.

For ADTOF, 50ms median absolute/p90 timing changes7/24.4ms→5/20ms; E-GMD
4.974/11.590ms→5.243/11.774ms. No fitted timing correction was applied. Full25ms
counts, family scores and signed timing errors are retained in metrics.json.

## Snare-addition and instrument-error inspection

The separated input yields65 additions:37 matches/28 false hits at25/50ms.
The original input yields33 additions:24 matches/9 false hits at50ms, and
23/10 at25ms. There are83 native SD collisions with original ADTOF and no
addition-to-addition collisions. All381 original-input ADTOF events and260
non-snare events remain exact. This is **not a new candidate or revised rule**.

Of the28 prior false-addition cases, only3 have an original native snare within
50ms and2 have an accepted original addition nearby:

- 14.860771s persists exactly as a native and added snare (source `chh`).
- 61.068481s persists natively but is blocked by original ADTOF (source `mt/rc2`).
- 61.474830s has an original addition at61.486440s (source `mt/rc2`).

These are descriptive temporal correspondences, not one-to-one scores or proof
that the other25 cases were separator-caused. Original input creates other false
additions. Of37 previously recovered snare references,27 remain matched by the
original-input merger; ten are lost. Overall merged SD gains21 other previously
missed targets and loses15 previously matched targets, for net+6 (125→131).

All28 prior false cases and all9 original false additions are audited with source
labels and37 visually inspected waveform panels. One timestamp appears in both
conditions. `review/` contains **111 sample-exact original/separated/snare-mic
excerpts**, CSV and an HTML review page. Every original false addition is over
100ms from the nearest SD reference; seven coincide with other families within
50ms and two have no nearby source event. No listening-verified relabeling.

The dominant residual error is HH. On original input, **121 of147 ADTOF false HH
predictions coincide with SD labels within50ms**. This is source-label evidence
of family disagreement, not proof that every event is an audible brush stroke.
Native E-GMD has198 false HH predictions, including40 near HH targets already
used by another prediction; the native every-active-frame decoder retains its
duplicate risk. No suppression or deduplication rule was fitted. Blanket HH/CY
suppression remains rejected. Exact contexts are saved in
`evidence/hihat-false-prediction-context.json`.

## Interpretation and next step

Both original-input F1 scores improve, so the input condition matters on this
recording. Waveform differences are visible around kick/tom passages. This
contrast jointly removes separator artifacts and accompaniment residue; it
cannot identify their separate causal contributions. Original input still has
substantial HH/snare confusion and missed hits, so input replacement alone does
not solve the measured problem. Source labels/brush articulation limits remain.

Close this fixed input control and keep the earlier failed merger rejected.
Do not sweep gains/thresholds, remove difficult tracks, or automatically fuse
the16 original-input E-GMD tom matches. No m!sa candidate follows this result.

Next, make a bounded primary-source feasibility audit of **one different
transcription approach**, starting with the previously located Separate-and-Detect
candidate. Recheck its checkpoint/dependency availability, output instrument map,
full-recording inference, dataset overlap, runtime/storage needs and whether its
source/evidence actually addresses the measured family errors. The earlier
release pointer is a lead, not current proof. Do not download weights until that
audit establishes a concrete runnable comparison; do not start broad retraining
or repeat rejected ADT_STR controls. If viable, predeclare one comparison in a
new root using existing development inputs and explicit independent-validation
limits. Any later promotion still requires separate validation and full-song
m!sa acceptance in the existing practice views.

## Verification and preservation

**90 recovery tests passed**, all optional integrations enabled. Independent
array-based reconstruction reproduces988 native notes and958 merged events
across both input conditions, preserving860 baseline events and645 non-snare
events. All scores, assignments, reference changes and case correspondences
reproduce;60 independent cardinality checks agree. Original-input PCM and ADTOF
frontend arrays round-trip exactly.1,647 prior and249 protocol hashes verify.
Read final verification, source/docs snapshots and artifact manifest before reuse.

D:/F: remained read-only. New files/cache/temp stay in this scoped C: root.
Existing ignored/untracked assets and all earlier experiments are preserved;
path inventory is not a claim that every ignored file was hashed. C: snapshots
are local preservation, not independent-device backup. WHITE WAVES China at1.000s
and Death Before Dishonor kick+crash at8.750s retain their coincident-HH removals.
Knuckles'35 disputed intro tom targets remain unchanged/unmasked; the user's
guitar-like feedback concerned repeated tapping. KLEWS and Adapt stay outside
tuning. No inference remains running and no application/default/user chart changed.

Key artifacts: `protocol.json`, `comparison/metrics.json`,
`comparison/reference-changes-50ms.json`, `comparison/prior-addition-correspondence.json`,
`evidence/measurements-verification.json`, `evidence/verification.json`,
`evidence/final-artifact-manifest.json`, and `review/review.html`.
