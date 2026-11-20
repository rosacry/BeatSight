# ADTOF frontend conformance and fixed development comparison

Verified 2026-10-15, America/New_York.

The pinned PyTorch frontend has a confirmed frequency-grid mismatch. A new
recovery-only adapter matches the reviewed primary algorithms on the tested
float-PCM boundary, but **does not improve chart accuracy** on the seven existing
development recordings. Its 50-ms F1 is .783532 versus .786303 for the port frontend
with the same primary decoder. No app/default or user-song change was accepted.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-adtof-frontend-audit-01`.
Existing experiments, audio, annotations, pinned weights/source and user-supported
corrections remain unchanged. D: and F: stayed read-only.

## Source findings and conformance boundary

[Original ADTOF preprocessing](https://github.com/MZehren/ADTOF/blob/b3968fb332f69b65ee07c089fc62f436503755db/adtof/io/mir.py)
uses madmom's signal, framing, STFT and logarithmic filtered spectrogram chain.
Its Frame_RNN settings use mono audio, 44,100 Hz input, 100 frames/s, 2,048-sample
windows, 12 bands/octave, 20–20,000 Hz and no difference features. Primary files
from that commit and madmom v0.16.1 are saved with URL/hash receipts in `primary/`.

The [madmom filterbank](https://github.com/CPJKU/madmom/blob/v0.16.1/madmom/audio/filters.py)
anchors logarithmic frequencies to 440 Hz. The preserved port starts at 20 Hz
and repeatedly multiplies by a semitone ratio. Both produce 84 bands, but **66
bands differ**, with a maximum coefficient difference of .666667. The common
shape therefore did not establish feature compatibility.

Two further differences are present in the compared path: the primary
[STFT](https://github.com/CPJKU/madmom/blob/v0.16.1/madmom/audio/stft.py) uses a
float64 Hann window before casting FFT results to complex64; the port casts its
window to float32. Primary [normal framing](https://github.com/CPJKU/madmom/blob/v0.16.1/madmom/audio/signal.py)
uses `ceil(samples / 441)` frames; librosa's centered framing adds one final frame
when the length is exactly divisible by 441. No timing shift was fitted.

`tools/recovery/frontend_adtof_reference.py` implements the fixed **already-decoded,
finite, nonempty mono float32 PCM at 44.1 kHz** contract. It uses the 440-Hz grid,
primary window/end semantics, normalized triangular filters and `log10(1+x)`.
It deliberately rejects integer, float64, stereo, empty and nonfinite arrays.
Sample rate is a caller precondition; an array alone carries no rate metadata.

The independent audit executes only named, reviewed AST definitions from the
hash-recorded primary files: filter construction, `signal_frame`, `fft_frequencies`
and `stft`. No complete downloaded module/import/top-level statement is executed.
A local compatibility wrapper maps old `np.float` to Python `float`. The primary
SciPy FFT fallback is used. Spectrogram projection/log and default frame-count
semantics were reviewed in their source and assembled explicitly.

This verifies that bounded numerical path. It does **not** execute the complete
madmom installation/file loader, integer-PCM scaling, resampling, FFTW, TensorFlow
or the original model. It is not a claim of complete original ADTOF reproduction.

## Frozen excerpts and numerical results

`protocol.json` was written before evaluating the feature comparison. Four fixed
track/family pairs were used: CoolJazz/snare, FreeJazz/snare, Beatles/tom and
FusionJazz/tom. Each contributes the first eligible raw-below-threshold miss
(otherwise its first eligible miss) and first successful control; each anchor
has a four-second original-mix and saved-stem excerpt, giving **16 excerpts**.
The Beatles tom miss uses the declared fallback. Exact anchors, categories and
441-sample-aligned starts are recorded. These selected passages are conformance
probes, not an unbiased accuracy sample.

Both frontends receive identical decoded float32 PCM. Stereo mixes use arithmetic
channel averaging; there is no gain normalization or resampling. Twenty-five
additional synthetic signals cover silence, impulses, seeded noise, six tones,
very short inputs and exact/near hop-multiple lengths. The frozen numerical gate
is `atol=rtol=1e-5` with matching frame counts.

- Adapter filterbank and frame samples exactly match the primary-function oracle.
- Adapter magnitudes and final features match exactly on all **41 signals**.
- On the 16 real excerpts, port feature mean absolute error ranges from
  .003453 to .063281; the largest individual feature difference is 1.115995.
- Replacing **only** the port filterbank leaves a maximum common-frame feature
  difference of 7.75e-7 across the real excerpts. This isolates the grid as the
  dominant numerical discrepancy there; final-frame shape still differs.
- Eleven of 25 synthetic signals expose the extra-frame difference. Twenty-one
  fail the complete port conformance gate. Zero-valued features can hide a grid
  error, so silence alone is insufficient verification.

All stage-level comparisons are in `conformance.json`; no excerpt chart score
was used to select a candidate or tune parameters.

## Full-recording result

The conditional follow-up was declared before the excerpt comparison and then
frozen in `full-recordings/protocol.json` before inference. It uses all seven
existing MDBDrums++ development recordings: 454.934 seconds, 2,461 targets,
including the 32 unsupported OT targets. Each candidate uses the **same saved
mono FLOAT drum stem**, unchanged gain/timeline and the pinned converted weights.
CPU, two threads, seed zero and the existing GRU configuration are fixed.

Both arms use `decode_adtof_reference.py` with unchanged thresholds
`[.22, .24, .32, .22, .30]`. Baseline activations are reused, with every saved
primary-decoder score dictionary reproduced. One full 80sRock control through
the original port exactly reproduces its saved activations (maximum error zero).
Model weights load strictly, with no missing/unexpected keys.

| Tolerance / frontend | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 25 ms / port | 1768 | 385 | 693 | .821180 | .718407 | .766363 |
| 25 ms / primary-aligned | 1767 | 387 | 694 | .820334 | .718001 | .765764 |
| 50 ms / port | 1814 | 339 | 647 | .842545 | .737099 | .786303 |
| 50 ms / primary-aligned | 1808 | 346 | 653 | .839369 | .734661 | .783532 |

At 50 ms both arms have 9.167 ms median absolute matched error and -5.625 ms
median signed error; p90 absolute error is 17.406 ms for baseline and 17.292 ms
for candidate. These describe their respective matched sets, not all targets.

| Recording | Baseline F1, 50 ms | Candidate F1, 50 ms |
|---|---:|---:|
| 80sRock | .821577 | .823529 |
| CoolJazz | .538365 | .551810 |
| SpeedMetal | .946274 | .939551 |
| Beatles | .666667 | .650519 |
| FreeJazz | .777693 | .769823 |
| FusionJazz | .879447 | .878578 |
| Punk | .904523 | .898990 |

| Family | Baseline TP / FP / FN | Candidate TP / FP / FN |
|---|---|---|
| Kick | 587 / 32 / 65 | 585 / 34 / 67 |
| Snare | 578 / 14 / 375 | 577 / 17 / 376 |
| Hi-hat | 299 / 183 / 69 | 297 / 177 / 71 |
| Tom | 38 / 24 / 43 | 38 / 31 / 43 |
| Cymbal | 312 / 86 / 63 | 311 / 87 / 64 |
| Other, unsupported | 0 / 0 / 32 | 0 / 0 / 32 |

The candidate fails the frozen minimum .01 pooled F1 gain. The precision, maximum
track loss, tom-TP and snare-recall safeguards pass, but passing those safeguards
does not turn a loss into an improvement. The frontend source mismatch is real;
correcting it is **not an established accuracy improvement** with these weights.
There was one candidate, no sweep, and no reserved/uncertain chart inference.

`full-recordings/metrics.json` retains per-track/family 25/50-ms results and timing;
each recording folder contains activations, predictions and individual matched/
missed-target exports. Original scores and charts are unchanged.

## Preservation, limits and next step

**62 focused tests pass**, including real chart-parser integration and source
frontend differential checks (61 in the combined run; four frontend checks
rerun after adding the relocated-source hash guard, bringing the unique total to
62). All **52 frozen comparison input/source hashes**
match before and after the full run. **304 prior artifact hashes** match, including
the previous experimental outputs and original/corrected user-song evidence.
The clarified Knuckles repeated-tapping observation and its 35 disputed targets
remain intact; no label deletion or scoring mask was applied.

`evidence/` contains the Git status snapshot, 11,259 ignored-file paths, 67
untracked-file paths, six pre-edit continuity documents, protected-file receipts
and the verified final source/document archive. The final experiment manifest
covers ignored outputs too. These C: copies are preservation, not an independent
device backup. No D:/F: write, training, separation, model/audio download or
application/default change occurred; only seven small public source files were
acquired for the audit.

The benchmark still has unknown pretrained-model overlap and consists of short
complete development recordings. Five broad families cannot establish detailed
drum-kit or cymbal-subtype fidelity. The two m!sa songs remain acceptance material
with their user-supported openings preserved. KLEWS labels/timing are uncertain,
and Adapt must not become a tuning set.

Next, inventory the already-local original-model/checkpoint and conversion
evidence, then audit **layer/weight conversion fidelity** against primary ADTOF
semantics on fixed features. Verify recurrent gate ordering/reset/bias semantics,
normalization and temporal context before claiming model equivalence. A controlled
layer test or exact original-checkpoint comparison should determine whether a
new inference arm is justified. Do not simply toggle a GRU flag and select it on
these scores. If original checkpoint execution is unavailable, record that limit
and distinguish source-semantic checks from end-to-end model parity. No additional
input mixture, frontend grid, threshold sweep or broad retraining is justified
by this result.

## Reproduction

Use the saved receipts and scripts for inspection. For a fresh run, create a new
scoped C: root and copy `primary/` with hash verification; never overwrite this
completed experiment. The helper commands, run sequentially from the repository:

```powershell
$out = 'C:\Users\10ros\BeatSight-Recovery\NEW-adtof-frontend-audit'
.\.venv-recovery\Scripts\python.exe tools/recovery/audit_adtof_frontend.py prepare --output-dir $out
.\.venv-recovery\Scripts\python.exe tools/recovery/audit_adtof_frontend.py run --output-dir $out
.\.venv-recovery\Scripts\python.exe tools/recovery/probe_reference_frontend.py prepare --root $out
.\.venv-recovery\Scripts\python.exe tools/recovery/probe_reference_frontend.py run --root $out
```

The primary receipts retain original absolute provenance paths. The current audit
verifies hashes of the actual files read in the supplied `primary/`, including
relocated copies. This relocation guard was added after the numerical run;
`evidence/audit_adtof_frontend-executed.py` preserves the executed source, whose
paths were the original receipt paths. Algorithm definitions/results are unchanged.
