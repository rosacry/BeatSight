# Frozen snare addition: additional validation — 2026-10-15

## Outcome

The unchanged snare addition **fails the predeclared validation gate**. On six
complete ENST recordings, 50-ms F1 rises **.800204 → .807358**, a **.007154**
gain below the required .01. There are **59 extra matched snares and 35 false
additions**. The other four safeguards pass, but cannot override this failure.
No m!sa acceptance drafts, app/default change, or user-chart replacement follows.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-snare-validation-01`.

This is additional validation outside the seven MusicDelta development tracks,
not established independent generalization: checkpoint-level training exclusion
is unresolved, and ENST is a known upstream evaluation set. The earlier
development pass remains valid evidence for those tracks; its larger gain did
not transfer at the required size to this fixed additional set.

## Frozen selection and source checks

`selection.json` was saved before predictions; `protocol.json` protects **216
entries** and was saved before either inference arm. Recovery checked **1,112
unique prior artifact hashes**. Source/docs were preserved in a verified ZIP,
and ignored/untracked path inventories were saved. D: and F: remained read-only.

Six ENST sequences were selected by named style/implement and drummer group,
without prediction scores: metal and musette brushes (drummer 1), rock-60s and
funk (drummer 2), Charleston and bossa (drummer 3). Total duration **446.32 s**;
**3,071 reference events**, including **751 snares** and **61 OT cross-sticks**.
These are complete dataset recordings of about 69–77 seconds, not full-length
m!sa song acceptance. No selection replacements were made after admission.

Four fixed IDMT loops were also selected as a secondary, drum-only condition.
All four failed annotation admission **before inference**, so none was scored:

| IDMT source | XML event missing from SVL | Additional discrepancy |
|---|---|---|
| RealDrum01_00 | HH at 17.2263 s | None in filename |
| RealDrum01_13 | KD at 6.8267 s | XML declares RealDrum02_00#MIX.wav |
| TechnoDrum01_05 | HH at 16.0815 s | None in filename |
| WaveDrum01_09 | HH at 20.5957 s | None in filename |

The common XML/SVL prefixes agree within 0.01134 ms; each count discrepancy is
the final global XML event. The bundled MATLAB parser uses `events.getLength-1`,
which is a plausible conversion explanation, not proof of the SVL files' history.
Neither format nor filename was silently corrected, and no target was dropped.
The first two preparation attempts stopped on assertions; their source, logs and
partial input copies remain in `inputs`/`inputs-02`. The completed attempt uses
`inputs-03` and records quarantine rather than aborting. No predictions existed
during these admission repairs, and the selection/rule/gates stayed unchanged.

Primary evidence:

- The [ENST authors' dataset page](https://perso.telecom-paristech.fr/grichard/ENST-drums/)
  describes three professional drummers, separate microphone channels and manual
  annotations. Original wet mix, accompaniment, snare mic and text labels were
  copied from the existing D: collection with source/copy SHA256 equality.
- The [IDMT dataset page](https://www.idmt.fraunhofer.de/en/publications/datasets/drums.html)
  describes manual KD/SD/HH labels in XML/SVL. Actual local copies disagree as
  above; the source description did not override the file audit.
- Pinned [ADTOF loader](https://github.com/MZehren/ADTOF/blob/b3968fb332f69b65ee07c089fc62f436503755db/adtof/model/dataLoader.py)
  distinguishes `adtof-all` (ADTOF sources) from `all` (also ENST/MDB/RBMA).
  The checkpoint filename alone cannot prove which exact examples it saw.
- The [E-GMD paper](https://arxiv.org/html/2004.00188) trains on E-GMD and evaluates
  ENST/IDMT. This supports stated dataset roles, not an unseen-benchmark claim.
  Demucs training exclusion is also unestablished.

Four small ADTOF primary files were saved at revision
`b3968fb332f69b65ee07c089fc62f436503755db`, checked against Git blob hashes and
SHA256. The three primary pages are saved locally. No new audio dataset, model,
runtime or training download occurred. Dataset access is not commercial rights.

## Input, annotations and unchanged rule

Each ENST input is **float32 .5 × (stereo wet mix + accompaniment)**, with exact
matching source sample rate, channels and length. This is our fixed equal-gain
constructed condition, not a claimed reproduction of the paper's mixture recipe.
The entire waveform is then normalized by its mono peak and passed through
`htdemucs_ft`, seed 0, using the already-local checkpoint and CUDA. Both models
receive the same saved mono FLOAT stem. No alignment or relative-gain fitting.

Source annotation seconds remain unshifted. The pinned `ENST_MIDI` map is reduced
to the existing six families; `cs` remains OT. No unknown source labels occurred,
and no targets were dropped. Original snare-mic attack profiles in each third
have peaks 4–20 ms after the labels. Bossa has fewer than five SD anchors in its
first two thirds; only its last third is measurable (8 ms). These are supporting
alignment screens, not proof of every perceptual onset or full bossa alignment.

The rule is exactly `native-snare-chronological-addition-v1` from
`compare_snare_addition.py`: retain every baseline event/field; consider native
pitch38 events at native probability >.5 in chronological order; add only beyond
50 ms inclusive of every baseline snare and earlier accepted addition. Other
families do not block. Rejected native events do not block later events. Stable
sort, epsilon 0.000001 ms. No threshold, collision, timing or order sweep.

ADTOF uses the previously checked source-conformant frontend/pooling/decoder.
E-GMD restores all **78 variables exactly** and checks native features against
the direct source frontend. All **3,043 native notes** reproduce from the saved
onset grid. The reused TF2.13 compatibility runtime remains **unproven historical
TF1 parity**. Missing SoX is an import warning; no augmentation or resampling
through SoX executes on these 44.1-kHz stems.

## Results

| Tolerance / arm | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 25 ms baseline | 2327 | 488 | 744 | .826643 | .757734 | .790690 |
| 25 ms addition | 2386 | 523 | 685 | .820213 | .776946 | .797993 |
| 50 ms baseline | 2355 | 460 | 716 | .836590 | .766851 | .800204 |
| 50 ms addition | 2414 | 495 | 657 | .829838 | .786063 | .807358 |

| Recording | Added | Matched / false at 50 ms | Baseline F1 | Addition F1 |
|---|---:|---:|---:|---:|
| Metal sticks | 5 | 2 / 3 | .798144 | .798155 |
| Musette brushes | 65 | 37 / 28 | .455866 | .502083 |
| Rock-60s sticks | 0 | 0 / 0 | .892308 | .892308 |
| Funk sticks | 5 | 5 / 0 | .891986 | .898383 |
| Charleston sticks | 17 | 14 / 3 | .881381 | .891030 |
| Bossa sticks | 2 | 1 / 1 | .834547 | .834891 |

There are 579 native pitch38 events: 482 collide with baseline SD, three with an
earlier addition, and 94 are added. All **2,815 baseline notes** and **2,219
non-snare notes** survive exactly. No previously matched SD reference is lost.

Snare TP/FP/FN changes **520/76/231 → 579/111/172**. Snare recall rises
.692410 → .770972, while snare precision falls **.872483 → .839130**. Added-note
precision is **59/94 = 62.8%**, versus 85.4% in the development experiment.
Other 50-ms family counts are unchanged: KD606/60/98, HH1025/277/174,
TT22/5/47, CY182/42/105, OT0/0/61. The missed toms remain a separate limitation.

All 59 matching additions also match at 25 ms: median absolute error **4.966 ms**,
p90 **11.656 ms**, median signed error **+2.986 ms**. Pooled 50-ms median
absolute/p90 timing stays 5/12 ms. This set does not reproduce the development
additions' early bias; no timing correction is supported from those results.

Frozen primary gates: F1 gain .007154 **fails** .01; precision loss .006751
passes .01; worst track F1 change zero passes −.02; tom TP stays22; snare recall
increases .078562. The primary failure stops progression even though no individual
track F1 decreases. IDMT was not scored and cannot rescue the outcome.

## False-addition review

All **35 false additions** are audited in `evidence/false-addition-inspection.json`,
with original source labels, nearby timings, three waveform pages and **105
sample-exact mix/stem/snare-mic excerpts** in `review/`. Every waveform panel was
visually inspected. This is source-reference/waveform evidence, not listening-
verified relabeling; microphone bleed and brush motion remain ambiguous.

- Nineteen additions coincide with other source families within50ms; thirteen
  coincide with toms. Family counts overlap: HH3, TT13, KD6, CY7, OT1.
- Sixteen have no source event within50ms. All35 are more than100ms from the
  nearest SD reference, so none is merely a near-boundary snare assignment.
- The brush recording contributes **37/59 gains and28/35 false additions**.
  Ten false additions at59.269–61.614s coincide with a labeled tom passage.
  Several other predictions occur in tails or quiet intervals between attacks.
- Bossa's false addition at27.620s coincides with `cs/chh/bd`. The native model's
  grouped snare/x-stick class cannot establish the correct articulation. The
  frozen cross-stick target remains OT; no favorable remapping was made.

## Verification, preservation and next step

**88 recovery tests pass**, all optional integrations enabled. Independent
array-based collision reconstruction reproduces all **2,909 exported events**;
all saved scores, assignments, pooled results and gates reproduce. A separate
greedy matcher confirms **124** per-family/arm/tolerance count checks. Prepared
mixtures and references round-trip exactly. Prior1,112 and protocol216 hashes
verify, with a final source/docs archive and research-artifact manifest.

No old experiment output was overwritten. Incomplete new preparation attempts
are retained. New caches/temp stay inside this scoped C: directory. Existing
ignored/untracked assets are preserved; path inventories are not a claim that
every ignored file was hashed. C: snapshots are not independent-device backup.
WHITE WAVES China at1.000s and Death Before Dishonor kick+crash at8.750s, with
coincident false HH removed, remain exact. Blanket HH/CY suppression stays
rejected. Knuckles' repeated tapping sounds guitar-like per the user; its35
disputed intro tom targets remain unchanged/unmasked. KLEWS and Adapt were not
used. No application/default, corrected chart, or practice-view behavior changed.

Keep this rule frozen and closed as a failed promotion candidate. Do not tune
thresholds/radii or remove the brush recording to turn this result into a pass.
The new measured bottleneck is brush/instrument confusion, with limited overall
benefit from naive snare additions. A useful next discriminating experiment is
one predeclared **original-wet-drum versus separated-stem input control** on the
fixed ENST brush recording, using the same checkpoints/settings. It can test
whether separation contributes to the misses/confusions; it cannot promote the
failed merger or establish generalization. Use a new root, no sweep, and assess
labels/bleed before assigning an acoustic cause. Do not repeat rejected ADT_STR
controls or start broad downloads/retraining. Any later candidate still needs
separate validation and full-song m!sa acceptance in the existing practice views.

Continue from `selection.json`, `protocol.json`, `comparison/metrics.json`,
`evidence/measurements-verification.json`, `evidence/verification.json`,
`evidence/final-artifact-manifest.json`, and `review/review.html`.
