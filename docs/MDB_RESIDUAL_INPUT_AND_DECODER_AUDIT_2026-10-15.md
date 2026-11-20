# Fixed input contrast and decoder conformance — 2026-10-15

Adding back 25% of the audio removed by separation **failed the frozen development
gate**. It lost 88 matched targets and added 72 false tom predictions for only two
net additional tom matches. The candidate is rejected; do not sweep mixture
fractions or promote it to the user songs. A separate source audit confirmed
decoder differences in the pinned PyTorch port, but reproducing the primary
decoder barely changes 50-ms F1. Most recall failures remain unresolved.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-mdb-residual-input-01`.
All existing experiments, model files and user-supported corrections remain
preserved. D:/F: stayed read-only. Seven bounded audio inferences ran; no new
separation, training, audio download or application-default change occurred.

## Frozen input comparison

The current files showed that raw full-mix inference on these seven recordings
already existed under `2026-10-14-white-waves-01/routing-diagnostic-full-mix`.
The earlier source-control handoff had not identified that completed comparison.
Its saved predictions were reused as context, not rerun.

`probe_residual_input.py prepare` freezes the protocol before inference. For all
seven previously selected MDB Drums++ recordings, the candidate is:

`saved_mono_drum_stem + .25 * (normalized_mono_mix - saved_mono_drum_stem)`

The mono-peak divisor and operation order reproduce the original stereo-input
separation preprocessing. There is no new normalization, clipping or time shift.
Saved drum stems, annotations, predictions and activations were hash checked;
saved activations regenerate the baseline predictions exactly, and both 25/50 ms
baseline score dictionaries reproduce. All seven candidate float WAVs round-trip
exactly. Existing full-mix predictions have different gain and are context only.

Weights remain SHA-256
`1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320`,
reference revision `85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9`, thresholds
`[.22,.24,.32,.22,.30]`, 100 fps, CPU, two threads and seed 0. No parameter search.

The frozen 50-ms gate requires at least .01 pooled F1 gain, at most .01 precision
loss, at most .02 F1 loss on any recording, no decrease in tom matches and at most
.01 snare-recall loss. Passing would only warrant separate acceptance-song review.
The candidate fails pooled F1, recording-regression and snare-recall requirements.

The seven complete short recordings total 454.934 s and 2,461 targets. Unknown
training overlap and unaudited annotation details remain limitations. The six-
family scoring retains 32 OT targets unsupported by the five-family model.
These are development measurements, not independent full-song accuracy.

| Input | Tolerance | TP / FP / FN | Precision | Recall | F1 |
|---|---:|---|---:|---:|---:|
| Saved stereo-separated baseline | 25 ms | 1755 / 393 / 706 | .8170 | .7131 | .7616 |
| Fixed 25% residual candidate | 25 ms | 1683 / 366 / 778 | .8214 | .6839 | .7463 |
| Saved stereo-separated baseline | 50 ms | 1811 / 337 / 650 | .8431 | .7359 | .7859 |
| Fixed 25% residual candidate | 50 ms | 1723 / 326 / 738 | .8409 | .7001 | .7641 |
| Saved raw full mix, context | 50 ms | 1507 / 356 / 954 | .8089 | .6124 | .6970 |

| Recording | Baseline 50-ms F1 | Candidate 50-ms F1 |
|---|---:|---:|
| 80sRock | .8201 | .7984 |
| CoolJazz | .5384 | .5646 |
| SpeedMetal | .9463 | .9393 |
| Beatles | .6690 | .6104 |
| FreeJazz | .7762 | .7382 |
| FusionJazz | .8794 | .8626 |
| Punk | .9040 | .7793 |

Only CoolJazz improves in F1, by removing many false HH predictions while also
losing genuine annotated matches. It is not a recall improvement on that track.

## Failure localization

All per-recording/family 25/50 ms scores, signed timing errors, unmatched target
times and unmatched predictions are retained in `metrics.json` and each track's
`events-25ms.json` / `events-50ms.json`. Post-result analysis does not tune inputs.

| Family | Baseline TP / FP / FN | Candidate TP / FP / FN | Newly matched / lost target identities |
|---|---|---|---|
| KD | 586 / 31 / 66 | 568 / 44 / 84 | 11 / 29 |
| SD | 576 / 15 / 377 | 550 / 10 / 403 | 29 / 55 |
| HH | 299 / 181 / 69 | 252 / 50 / 116 | 1 / 48 |
| TT | 38 / 24 / 43 | 40 / 96 / 41 | 4 / 2 |
| CY | 312 / 86 / 63 | 313 / 126 / 62 | 13 / 12 |
| OT | 0 / 0 / 32 | 0 / 0 / 32 | 0 / 0 |

Of the 72 additional false tom predictions, 38 occur on 80sRock and 25 on
Beatles. Punk adds 41 false cymbal predictions and loses 17 HH matches.
These are annotation-relative mistakes; instrument identity has not been
independently heard/verified by the agent. No global family-suppression rule is
supported by these aggregate differences.

On all matched events, median absolute timing is 9.375 ms for baseline and
8.190 ms for the candidate; p90 is 17.462/16.667 ms. On the **same 1,665 target
identities matched by both**, medians are 9.375/8.257 ms and p90 17.292/16.550 ms.
This small timing change does not compensate for the lost coverage and family
mistakes. No alignment correction was applied.

`analyze_residual_input.py` also examines fixed +/-50 ms windows around every
missed target using saved activations and the unchanged thresholds:

| Baseline family | Raw activation never reaches threshold | Raw reaches it, local-mean subtraction falls below | Other peak/grouping/timing/assignment cases |
|---|---:|---:|---:|
| KD | 57 | 7 | 2 |
| SD | 282 | 86 | 9 |
| HH | 64 | 5 | 0 |
| TT | 21 | 7 | 15 |
| CY | 42 | 17 | 4 |

The remaining 32 misses are unsupported OT. High raw response is not proof of
an onset, and subtraction is not by itself a decoder bug. The model still has
weak raw responses near 282 missed snares and 21 missed toms. The reviewed figure
is `analysis/comparison-v2.png`; the first layout and executed analysis source
remain preserved. `analysis/failures.json` contains every target-level bucket.

## Primary decoder conformance

The source audit saved four small public source files with URL/hash provenance
under `decoder-source-audit/`. No package or full downloaded module was imported.
Only the two reviewed function definitions were compiled for the differential
check, with the obsolete `np.float` alias mapped to Python float and smoothing
fixed to the identity at zero.

[Original ADTOF's peak picker](https://github.com/MZehren/ADTOF/blob/b3968fb332f69b65ee07c089fc62f436503755db/adtof/model/peakPicking.py)
sets the same averaging, maximum-window and combination parameters. The pinned
port nevertheless differs from [madmom v0.16.1 peak picking](https://github.com/CPJKU/madmom/blob/v0.16.1/madmom/features/onsets.py):
the primary code zero-pads averaging and finds maxima of threshold-masked raw
responses; the port edge-pads and finds maxima after subtraction.
[Primary note combination](https://github.com/CPJKU/madmom/blob/v0.16.1/madmom/features/notes.py)
retains the earliest event, using [left-event merging](https://github.com/CPJKU/madmom/blob/v0.16.1/madmom/utils/__init__.py);
the port chooses the strongest member of a contiguous group. With peaks at
100/120 ms of strengths .6/.9, the primary result is 100 ms and the port is 120 ms.
Local-average thresholding is intentional in both implementations.

`decode_adtof_reference.py` is a new recovery-only implementation of the reviewed
fixed decoder. It matches the primary functions on 1,000 deterministic random,
sparse and plateau vectors; primary 1D/2D results agree on all 1,000 cases. Its
seven saved-recording charts exactly match the primary-function outputs.
This establishes this decoder's tested conformance, not model/frontend parity.

Re-decoding **only the seven saved baseline activations**, without inference or
tuning, retains 2,029 exact component/time entries and replaces 119 old entries
with 124 new ones. An event can appear in both change counts when only time moves.

| Decoder | 25-ms TP / FP / FN | 25-ms F1 | 50-ms TP / FP / FN | 50-ms F1 |
|---|---|---:|---|---:|
| Preserved PyTorch port | 1755 / 393 / 706 | .7616 | 1811 / 337 / 650 | .7859 |
| Reviewed primary semantics | 1768 / 385 / 693 | .7664 | 1814 / 339 / 647 | .7863 |

This small change does not explain the major missing-hit problem. New predictions
are separate artifacts under `decoder-source-audit/cached-comparison/`; the
pinned checkout, historical scores and current practice packages were not edited.
Do not describe all prior port results as an exact reproduction of original ADTOF.

## Verification and next action

**58 focused tests pass**, including source controls, parser integration, residual
input timeline/gain guards and decoder counterexamples. All 45 input-comparison
source/artifact hashes match before and after execution. Broader preservation
checks and source/document snapshots are recorded under `evidence/`; six earlier
continuity documents were archived and read-back checked before edits.
The clarification that Knuckles' repeated tapping sounds guitar-like and both
m!sa opening corrections remain intact. C: copies are not a separate-device backup.

Do not repeat the residual blend at new fractions. The next bounded verification
is the reference **audio frontend's conformance**, using saved local mix/stem
excerpts and original implementation semantics, before attributing weak snare/tom
responses entirely to weights or starting threshold searches/retraining. The
decoder mismatch demonstrated why conversion fidelity cannot be assumed. Preserve
the current development references and uncertain Clone Hero labels, use the new
miss-time export to select a small fixed set of failure and successful-control
windows, and keep full-song/reserved results out of parameter tuning. No new
recording/model download is needed to establish that comparison's protocol.

## Reproduction

Use a fresh C: root; do not rerun into this completed experiment:

```powershell
$data = 'C:\Users\10ros\BeatSight-Recovery\2026-10-13\diagnostic-mdb-plus-seven-inputs'
$saved = 'C:\Users\10ros\BeatSight-Recovery\2026-10-14-white-waves-01'
$reference = 'C:\Users\10ros\BeatSight-Recovery\2026-10-13\reference-adtof'
$out = 'C:\Users\10ros\BeatSight-Recovery\NEW-mdb-residual-input'
.\.venv-recovery\Scripts\python.exe tools/recovery/probe_residual_input.py prepare --output-dir $out --dataset $data --baseline "$saved\stereo-diagnostic" --full-mix "$saved\routing-diagnostic-full-mix" --reference-repo $reference
.\.venv-recovery\Scripts\python.exe tools/recovery/probe_residual_input.py run --output-dir $out
.\.venv-recovery\Scripts\python.exe tools/recovery/analyze_residual_input.py --root $out
```

The source-conformance experiment scripts, pinned fetched files and their
verification are preserved under `decoder-source-audit/`. They are distinct
from the original frozen audio-input contrast and do not alter its rejection.
