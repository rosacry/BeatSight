# DrumSep isolated hi-hat/snare control — 2026-10-16

The unchanged separator fails the predeclared isolated-hit control. All 15 snare
events pass, but only 1 of 13 hi-hat events passes. All three complete hi-hat
recordings fail; all three snare recordings pass. These outputs are unsuitable
as reliable hi-hat-presence/absence references for correcting transcription.
No chart, application default, instrument label or timing was changed.

Root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-drumsep-isolated-control-01`.
Read `protocol.json`, `separated/completed.json`, `measurements/summary.json`,
`measurements/events.json`, `evidence/independent-checks.json`,
`evidence/verification.json` and `evidence/final-artifact-manifest.json`.
The seven fixed review cases, 49 exact clips and six waveform panels are in
`review/index.html`. No auditory relabeling was performed.

## Recovery and inputs

The first bootstrap stopped because D: was unavailable. The user reconnected it;
subsequent verification checked **all 2,532 prior artifacts**, with zero missing
or changed files. The failed bootstrap and interruption record remain saved.
The 101 existing source/document files were archived with exact hash readback
before any repository edits. D: and F: remained read-only.

Six companion isolated-stroke stereo `dry_mix` recordings were already selected
by filenames and inventoried in the preceding microphone audit. They contain
13 source-labeled closed-hi-hat hits and 15 snare hits across three drummers.
Drummer 1 uses brushes because that local kit has no closed-hi-hat-stick control;
drummers 2 and 3 use sticks. No recordings or events were replaced or excluded.
Six audio files and six original annotation files were copied byte-exact to C:.

These are the full original stereo PCM16 recordings, totaling **78.28 seconds**,
decoded to float32 at 44,100 Hz with gain 1. There is no normalization, resampling,
mono fold, upstream Demucs pass or audio/annotation shift. Source labels describe
the intended isolated instrument; room noise and sympathetic resonance can remain.
Individual microphone purity is not assumed. These are small exposed controls,
not a mixed-song test, independent holdout or proof of training exclusion.

## Frozen execution and measurements

Protocol SHA-256, saved before inference:
`a18fa6dd714746cefdef6c123679c785a4ffb98f8a20b56d2aad5053ba11585c`.
Its 46 protected entries cover code, source, checkpoint, inputs and declarations.

The source/checkpoint boundary is the same as
`DRUMSEP_FAMILY_EVIDENCE_2026-10-16.md`: nine pinned native MSST files at commit
`6fdad13686bb7e84d029ec66f9dbe76e65c93ebf`, unchanged config and six-stem weights
SHA-256 `d2a4aa53eb584d21eead358a4e66d1882ad182911be018f052b5da73be9096d0`.
All 319 tensors / 109,378,624 scalar values match the prior strict-load tensor
hashes. This verifies current pinned native execution, not historical training
runtime parity, training exclusions or weight commercial rights.

Settings remain seed 0, CUDA, two CPU threads, chunk 130,560 samples, overlap 4,
batch 1, AMP enabled, TF32 disabled, deterministic algorithms enabled, no TTA or
normalization. Six complete inputs produce 36 full-length finite stereo FLOAT
outputs with exact PCM readback. Neural execution totaled **14.04 seconds**.
Existing 12 native stitching/STFT checks are hash-protected; they were not rerun.

Every complete file and every fixed **[-50 ms, +500 ms)** event window is measured
using float64 squared-sample sums across both channels. Windows do not overlap
or require clipping. No fitted gain, time alignment or threshold search is used.

- Routing: expected stem energy must strictly exceed each other stem's energy.
- Reconstruction: `sum((input - expected_stem)^2) / sum(input^2) <= 0.25`.
- Leakage: `sum(other_stem_squared_energies) / sum(input^2) <= 0.10`.

All three conditions must hold for every file and event to pass this control.
These are locally chosen conservative diagnostic tolerances, not published
standards or deployment gates. Uncentered waveform cosine and reconstruction
error of the sum of all stems are also reported descriptively. Stem energy
ratios are not additive fractions of the source: cross terms exist.

## Results

All values below are complete-file ratios, not transcription precision/recall.

| Source control | Expected energy / input | Target reconstruction error | Off-target energy / input | Strongest output | Events passing |
|---|---:|---:|---:|---|---:|
| Drummer 1, brushed HH | 0.314163 | 0.358622 | 0.187950 | HH | 0/3 |
| Drummer 1, brushed snare | 0.764750 | 0.042392 | 0.015391 | Snare | 5/5 |
| Drummer 2, stick HH | 0.226883 | 0.412032 | 0.140855 | HH | 1/5 |
| Drummer 2, stick snare | 0.966634 | 0.001590 | 0.000643 | Snare | 5/5 |
| Drummer 3, stick HH | 0.003094 | 0.942280 | 0.484679 | Snare | 0/5 |
| Drummer 3, stick snare | 0.891739 | 0.008505 | 0.001250 | Snare | 5/5 |

The result is not explained solely by strict fidelity tolerances: **9 of 13 HH
event windows have the wrong dominant output** (eight snare, one tom). The other
four are HH-dominant, but three still fail fidelity or leakage. All 15 snare
event windows are snare-dominant and pass all criteria.

The predeclared review selects each file's highest target-error event and highest
leakage event, with earlier-time ties and duplicate selections merged. The six
waveform panels were inspected. Notable cases, retaining source labels:

- Drummer 1 HH at 0.413 s: target error 0.62775, leakage 0.21918, tom-dominant.
  The brushed recording is quieter; this does not justify an after-the-fact gain
  search. Whole-file tom energy/input is 0.17585.
- Drummer 2 HH at 5.534 s: error 0.67205, leakage 0.30401, snare-dominant. Three
  of five HH event windows in this recording are snare-dominant.
- Drummer 3 HH at 0.259 s: error 0.99726, leakage 0.75171, snare-dominant.
  All five HH windows are snare-dominant. Whole-file HH energy/input is only
  0.003094, while snare energy/input is 0.455956.
- Worst snare reconstruction windows still pass: error 0.09897 for drummer 1,
  0.00203 for drummer 2 and 0.02863 for drummer 3.

Summing all six outputs gives whole-file reconstruction error between 0.000542
and 0.074096. This can coexist with poor instrument routing; reconstruction of
the mixture does not validate each output's instrument identity.

## Verification and decision

An independent dot-product implementation reproduces all **34 measurement rows**
(six full files and 28 events), 204 scalar comparisons, six energies per row,
dominant outputs and every gate. Maximum scaled numeric difference is
`9.992007221626409e-16`. All 49 review clips match their exact source PCM windows.
Three synthetic measurement controls distinguish correct routing, wrong-family
routing and total signal loss before inference.

The previous 90-test recovery log is protected, not rerun; no application path
changed. Final verification checks prior hashes, the 46-entry protocol, 12 source
copies, 36 outputs, all 2,815 baseline notes, corrected openings, Knuckles'
35 unchanged targets and the user's **Repeated tapping** clarification. Ignored
path inventory is unchanged and existing untracked paths are retained. This is
not a full content-hash audit of every ignored asset. C: copies are local
preservation, not an independent-device backup.

Close this native DrumSep hi-hat correction/reference route under the tested
contract. Good isolated-snare behavior does not establish snare specificity:
labeled HH itself enters the snare output. Do not use snare dominance as HH
absence, relabel source annotations, retune gains/windows, or revive blanket
HH/CY suppression. The failed mixed-song energy rule and microphone-transient
presence rule remain closed. No song-level accuracy gain has been established.

## Next bounded work

Return to the actual full-song learning workflow. In a new scoped C: root,
audit the existing corrected WHITE WAVES and Death Before Dishonor drafts in
the native loader and existing practice views: complete audio/chart coverage,
beginning/middle/end playback and seeking, event/lane rendering and retained
user corrections. Reuse saved packages before inference. Prepare a small fixed
review set of musically uncertain passages; keep load/render facts separate
from audio-verified timing and instrument accuracy. Do not claim acceptance
from a loader test or ask the user to chart whole songs manually.

There is no new correction candidate to promote. Future candidates still need
independent validation and full-song m!sa acceptance. KLEWS/Adapt stay outside
tuning; E-GMD replacement/merger and ADT_STR failures stay closed, and
Separate-and-Detect remains deferred. No broad downloads or retraining.
