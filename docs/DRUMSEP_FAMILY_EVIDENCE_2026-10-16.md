# Six-stem DrumSep family-evidence diagnostic — 2026-10-16

The fixed diagnostic passes on one complete original-drum recording. This is a
promising source of instrument evidence, **not an improved transcription or a
promotion decision**. No notes were added, removed, relabeled or moved.

Root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-drumsep-audit-01`.
Read `protocol.json`, `evidence/runtime-amendment-01.json`,
`separated-02/completed.json`, `family-evidence/metrics.json`,
`evidence/independent-checks.json`, `evidence/verification.json` and
`evidence/final-artifact-manifest.json`. The local review is `review/index.html`.

## Why this test

The earlier E-GMD replacement and subsequent snare merger remain rejected. The
original-input control still contained 147 false ADTOF hi-hat predictions, 121
within 50 ms of snare references, alongside 44 matched hi-hats. This tests whether
a different model's separated snare and hi-hat audio contains information that
could distinguish those errors. It does not reopen the failed merger.

The recording is the already-exposed 75.16-second
`enst-drummer_1-110_minus-one_musette_brushes`, with original wet drums at the
previous mixture-component gain. It is an oracle-input diagnostic chosen because
of an observed bottleneck. It is neither an independent holdout nor proof that
the signal survives ordinary mixed-song processing.

## Source, checkpoint and executable boundary

The [Riley/Dixon paper](https://arxiv.org/html/2509.24853v1) reuses ADTOF onsets
and refines velocity and hi-hat/cymbal subclasses. It does not establish missed
snare recovery or snare/hi-hat correction. It describes the separator's private
21.8-hour synthetic MIDI/sample-library training set and 0.27-hour validation set
based on author correspondence; exact contents, brush coverage and exclusions
are unavailable. Its five-class transcription results largely inherit ADTOF,
with zero-velocity omissions. Those omissions were not adopted here.

The original Jarredou author release URL returned HTTP 404. This establishes
current unavailability of that endpoint, not why it is unavailable. A local
filename inventory found no existing matching checkpoint in BeatSight or its
recovery collection. Two pinned Hugging Face mirrors and an openmirlab release
advertise the same six-stem weight digest and byte size:

- [Politrees mirror at revision 929e057b81aa49bc2e6490bef8671f47b2c120f6](https://huggingface.co/Politrees/UVR_resources/tree/929e057b81aa49bc2e6490bef8671f47b2c120f6/models/MDX23C).
- [Sucial mirror at revision 90b617b15bd0dc0b784f3d361faca1b51173fe44](https://huggingface.co/Sucial/MSST-WebUI/tree/90b617b15bd0dc0b784f3d361faca1b51173fe44/All_Models/multi_stem_models).
- [openmirlab mirror release](https://github.com/openmirlab/mdxnet-infer/releases/tag/weights-drumsep-v1), including a byte-identical config copy.

The one downloaded checkpoint is 437,652,699 bytes, SHA-256
`d2a4aa53eb584d21eead358a4e66d1882ad182911be018f052b5da73be9096d0`.
The config is 2,417 bytes, SHA-256
`17d1649a227f841165bdb4c11a42082898192a1ea3ceab7e7e0b9293d6589dd6`.
Mirror agreement and actual byte verification do not establish original-author
signing, exact training provenance or weight redistribution/commercial rights.
The paper-author mirror's five-stem variant is different and was not downloaded.

Nine bounded files from [MSST commit 6fdad13686bb7e84d029ec66f9dbe76e65c93ebf](https://github.com/ZFTurbo/Music-Source-Separation-Training/tree/6fdad13686bb7e84d029ec66f9dbe76e65c93ebf)
match pinned Git blobs and SHA-256. The helper executes the native MDX23C
architecture and five exact native inference functions through reviewed AST
extraction. An attribute-access dict replaces the absent `ml_collections` config
wrapper; unrelated training imports are omitted. Model math is not rewritten.
This is execution of the pinned current source, not established historical
training-runtime or paper-pipeline parity. The paper's ReplayGain/loudness and
velocity processing are not part of this local diagnostic.

Twelve preflight checks pass: nine native overlap/stitching identity fixtures,
including sub-chunk, boundary and complete-recording lengths, plus three native
STFT impulse positions. Full length, stem ordering and timing are retained.
These are I/O checks, not model accuracy tests.

Protocol SHA-256, frozen before weight acquisition and neural inference:
`86719d7dcbe8c8d3bcd38505f9dd3b7128d8de23581e9e3ea3be9fb3dc9266c3`.
Twenty-two protected entries cover input, predictions, labels, assignments,
source and evaluation code. The first run failed before checkpoint loading because
CUDA memory instrumentation preceded CUDA initialization. Original helper bytes,
failed log and empty output folder remain intact. The explicit runtime amendment
initializes CUDA and routes to fresh `separated-02`; model settings and the
predeclared feature/gates are unchanged.

Strict `weights_only=True` loading verifies all 319 tensors and 109,378,624 scalar
values exactly. Existing recovery Python 3.11.5 / PyTorch 2.5.1+cu121 runs on the
3080 Ti; no runtime packages were installed. Six finite, exact-readback FLOAT
stems each cover all 3,314,556 stereo frames at 44.1 kHz. Native order is kick,
snare, toms, hh, ride, crash. Inference took 8.46 seconds, peak allocated CUDA
memory 1,099,504,640 bytes. This is one observed run, not a speed benchmark.

## Frozen measurement and results

The stereo input is `(.5 * float32(wet.T)) / 0.2924041748046875`, with operation
order preserved; its mono fold equals the prior ADTOF original-input PCM exactly.
Settings are seed 0, two CPU threads, CUDA 0, AMP on, TF32 off, deterministic
algorithms on, chunk 130,560 samples, overlap 4, batch 1, no normalization/TTA.
No window, input gain, overlap, checkpoint or decision-threshold search occurred.

For every existing ADTOF hi-hat prediction, take 50 ms of stereo PCM beginning at
its rounded sample position. The fixed feature is
`10*log10((snare_mean_square + 1e-12)/(hh_mean_square + 1e-12))`.
Use source-conditioned groups from the unchanged 50-ms baseline assignment:

| Group | Events | Median snare/HH energy | Above 0 dB |
|---|---:|---:|---:|
| Unmatched HH within 50 ms of a snare reference | 121 | +7.601 dB | 79 |
| Matched HH | 44 | -37.457 dB | 2 |
| Other unmatched HH, retained in event table | 26 | Not a gated group | Not a gated group |

AUROC is **0.9477836213**, above the predeclared 0.8 requirement. Both group
medians have their required signs, and both groups exceed the minimum 10 events.
All diagnostic gates pass. AUROC measures ranking of these two selected groups;
it is **not 94.8% note accuracy**, a deletion precision, or a transcription F1.

Independent dot-product energy calculations check all 1,146 stem windows over
191 predictions; maximum score discrepancy is 1.42e-14 dB. A rank-sum AUC
calculation reproduces the pairwise result. An independent ordered dynamic
program reproduces the cached HH matching objective: 44 matches and total
absolute timing error 0.806 seconds. All group membership and reference contexts
reconstruct. Of the matched HH, 23 have nearby SD and HH references; all remain
in the negative group. No coincidence masking is used.

## Exceptions and review

The saved review plan chose four lowest-scoring false-HH-near-SD cases and four
highest-scoring matched-HH cases, with timestamp tie-breaking. It was written
before diagnostic scoring. All eight have one-second original/snare/HH/tom
clips (32 total), exact PCM readback, source-label contexts and inspected waveform
plots. The full 191-event CSV and score-over-time plot are also saved.

| Existing HH time | Group | Feature | Observed waveform/source context |
|---|---|---:|---|
| 9.310 s | False HH near SD | -28.39 dB | Strong HH-stem transient despite nearby SD-only reference |
| 23.810 s | False HH near SD | -26.21 dB | Weak HH transient over sustained tom-stem energy |
| 25.540 s | False HH near SD | -24.95 dB | HH-stem energy persists from earlier activity |
| 39.430 s | False HH near SD | -21.16 dB | HH transient over strong ongoing tom-stem energy |
| 69.330 s | Matched HH | +10.57 dB | Snare transient and nearby genuine HH/SD labels coexist |
| 16.310 s | Matched HH | +9.36 dB | Nearby HH precedes SD; energy window favors later SD activity |
| 68.980 s | Matched HH | -2.53 dB | Nearby HH and SD references; overlapping instrument energy |
| 34.710 s | Matched HH | -4.10 dB | HH evidence with sustained tom-stem energy |

These are waveform/reference inspections, not listening-verified relabeling.
Stem names do not prove instrument truth. Forty-two targeted false HH lack
snare-dominant energy, and two genuine HH have it. Nearby hits, decay and prediction
timing affect a fixed energy window. A blanket suppression rule is not justified.

## Preservation and next decision

All 2,042 protected prior artifacts verify. The 95 preexisting source/docs files
are preserved before edits; final snapshot includes the new helper and report.
The three continuity files are the only preexisting repo files changed. Final
verification records ignored/untracked inventory, corrections and exact snapshots.
The previous 90-test log remains hash-verified; it was not rerun for this standalone
diagnostic. New evidence is the 12 native probes, strict load, actual complete
separation, independent arithmetic/matching and exact media checks above.

D:/F: remain read-only. Existing app defaults, all ADTOF notes, user charts,
WHITE WAVES China at 1.000 s and Death Before Dishonor kick+crash at 8.750 s with
their false HH removals remain intact. Knuckles' 35 disputed toms are unchanged
and unmasked; the user's repeated-tapping correction is preserved. KLEWS and
Adapt were not used. No training, broad download or inference remains running.
C: snapshots are protection from accidental edits, not independent-device backups.

Next use a **new C: experiment** to predeclare the same feature on the six already
selected complete ENST mixed-recording cases. Reuse cached ADTOF predictions,
references and htdemucs_ft drum PCM; verify its actual channel/gain contract first
(the available `drums.wav` files are mono, so any stereo duplication must be
explicitly frozen and exact). Do not select tracks by feature results or silently
replace the input recipe. Freeze group-size eligibility and pooled/per-recording
gates before inference; report small groups as inconclusive. Reuse this exact
checkpoint and source, with no threshold/window/gain/overlap sweep and no chart
correction yet. This tests practical-input usefulness on already-exposed data,
not independent generalization. A later explicit correction rule still needs
independent validation and full-song m!sa acceptance before promotion.
