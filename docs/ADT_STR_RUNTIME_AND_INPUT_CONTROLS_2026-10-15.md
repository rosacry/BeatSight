# ADT_STR runtime and input controls

Verified 2026-10-15, America/New_York. All three controls are complete.

**No candidate is promoted.** Runtime changes leave the tested outputs identical;
original drums improve agreement but retain decoding failures; the source-defined
segment-normalization candidate lowers seven-stem F1 to **.647707**, versus
unnormalized ADT_STR .664469 and the original-parity ADTOF baseline .788049.

The declared inference runtime reproduces **all 72 tested token sequences exactly**,
including the same eleven failed chunks. The earlier decoding failures are not
explained by the tested torch/transformers version difference. This establishes
output equivalence on the selected batches, not exact intermediate numerical
parity or reproduction of the paper's full evaluation environment.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-adt-str-runtime-controls-01`.
All 642 accumulated prior artifact hashes were verified before this work. D: and
F: stayed read-only. Old checkpoints, experiments, user charts and corrections
are preserved. No model weights or datasets were downloaded for this continuation.

## Declared runtime and controls

The isolated `runtime/` contains torch/torchaudio **2.8.0+cu128** and transformers
**5.3.0**, using the same local CPython 3.11.5 (permitted by the source's
Python >=3.10,<3.13 declaration). The
[pinned source requirements](https://github.com/pier-maker92/ADT_STR/blob/77dbef225e7029478ebfb916f20c7a00274f0f12/pyproject.toml)
and checkpoint configuration supplied these version choices. CUDA packages came
from the official [PyTorch previous-version index](https://pytorch.org/get-started/previous-versions/).
Installation cache and temporary files live under the same new root. The previous
environment was not changed. `pip check` reports no broken requirements.

This is an inference-only runtime: training dependencies were not installed, and
TorchCodec is not required for the cached-tensor comparison. The later WAV controls
use torchaudio2.8's installed soundfile backend. It is not the author's complete
training/evaluation environment. The 289-MB pinned checkpoint is reused read-only.

`protocol.json` freezes nine original batches: all eleven known failure chunks,
their unchanged batch companions, and the first 80sRock control batch. There are
72 chunks, each 2.56 seconds. Identical saved float32 24-kHz tensors isolate model
execution from file decoding and resampling. Both runs retain batch size eight,
greedy maximum 512 tokens, seed zero, float32 CUDA, TF32 disabled and deterministic
algorithms. All 132 checkpoint tensors load strictly.

The original runtime (torch2.5.1+cu121 / transformers4.57.3) first reproduced all
saved sequences exactly. The declared runtime then reproduced **72/72 sequences**,
including all eleven incomplete/malformed sequences without EOS. No settings were
tuned and no old predictions or scores were replaced.

Shared-prefix diagnostics compare mel features, encoder outputs and logits under
the first up to 64 identical cached-prefix tokens. Maximum absolute differences:

| Stage | Maximum absolute difference |
|---|---:|
| Mel | 7.80821e-6 |
| Encoder | 6.92904e-6 |
| Logits | 5.76973e-5 |

All mel and encoder arrays pass atol=1e-5, rtol=1e-4. Sixteen logit values across
three batches fail that strict tolerance; all shared-prefix argmax decisions and
all full greedy sequences still match. The numerical failures are retained in
`evidence/numerical-boundary-details.json`; they are not relabeled as parity.
`comparison.json` is the authoritative runtime result.

## Additional primary-source finding

Source review found a real difference between upstream evaluation and the public
transcription helper. `MDBDrumTextParser` serializes 2.56-second segments as dataset
items; `EvalDataset.__getitem__` applies `normalize(audio)` to each item after
resampling. `utils.audio_utils.normalize` divides by that item's absolute peak.
The public `ADTTranscriber` helper loads/resamples/chunks without that operation.

The normalization contrast is therefore one source-defined semantic check, not
a sweep of gains. It retains all seven existing stems, every annotation, the
same checkpoint, native greedy decoding, chunking and exact-note deduplication.
Nonzero chunks use the primary normalization function on CPU; exact silence is
left zero as an explicit guard against the primary function's zero division.
The separate `segment-normalization/protocol.json` was frozen before inference.
Acceptance still requires improvement over the original-parity ADTOF baseline
with the existing precision, per-track, tom and snare safeguards.

This does not reproduce the complete upstream evaluation. Its segmentation can
drop reference notes whose 0.1-second duration crosses a segment boundary, and
tail padding can differ. Our existing full-recording references retain every hit.
MDB also informed the authors' model recommendation; these remain development
results, not independent held-out evidence.

## Original-drum controls

`original-controls/protocol.json` freezes both already-local CoolJazz and FreeJazz
original-drum recordings against the saved separated stems. Sample rates, channel
counts and sample counts match exactly. No alignment, gain normalization or new
separation is applied. The declared runtime executes the same public helper on
both arms. Both separated runs reproduce **every prior batch token, resampled
input array and final note array exactly**. This extends the runtime control to both full affected recordings
and their file loading/resampling path.

| Recording / input | TP | FP | FN | Precision | Recall | F1, 50 ms |
|---|---:|---:|---:|---:|---:|---:|
| CoolJazz / separated | 156 | 149 | 303 | .511475 | .339869 | .408377 |
| CoolJazz / original | 248 | 76 | 211 | .765432 | .540305 | .633461 |
| FreeJazz / separated | 351 | 225 | 371 | .609375 | .486150 | .540832 |
| FreeJazz / original | 407 | 168 | 315 | .707826 | .563712 | .627602 |
| Pooled / separated | 507 | 374 | 674 | .575482 | .429297 | .491756 |
| Pooled / original | 655 | 244 | 526 | .728587 | .554615 | .629808 |

At 25 ms pooled F1 changes .466537 -> .617308. Pooled 50-ms snare matches rise
287 -> 391, but 263/654 snares remain missed on original drums. Tom matches rise
1 -> 6, with 21/27 still missed. Hi-hat matches fall 28 -> 10 and 138/215 cymbal
targets remain missed. Original-input median absolute matched timing is 8.542 ms,
p90 16.458 ms and signed median -8.125 ms; these are conditional on matches.

Original drums improve agreement but do not remove malformed decoding. Chunks
without EOS increase from **11 to 20** (CoolJazz 4 -> 6, FreeJazz 7 -> 14).
Including an additional malformed CoolJazz chunk that does reach EOS, original
audio has 21 chunks with grammar issues. Thus cleaner audio alone is insufficient.

Input levels and recording processing differ along with separation: at 24 kHz,
CoolJazz separated/original peaks are .257752/.297654 and RMS .013177/.010661;
FreeJazz peaks .654880/.746515 and RMS .028344/.030207. These are oracle controls,
not end-to-end scores or a controlled separation-algorithm comparison. The original
files' saved provenance records CC BY-NC-SA4.0. No new audio was downloaded.

## Source-defined normalization result

All seven complete stems were processed once, with all 2,461 targets retained.
All 182 actual normalized input chunks are saved and checked against the frozen
per-segment formula. There were no exactly silent chunks, so the explicit
zero-division guard did not affect this experiment. Runtime was 204.3 seconds,
excluding model startup. No gain selection or rescoring mask was applied.

| Tolerance / model-input | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 25 ms / ADTOF baseline | 1772 | 386 | 689 | .821131 | .720033 | .767266 |
| 25 ms / ADT_STR unnormalized | 1447 | 643 | 1014 | .692344 | .587972 | .635904 |
| 25 ms / ADT_STR normalized | 1548 | 984 | 913 | .611374 | .629013 | .620068 |
| 50 ms / ADTOF baseline | 1820 | 338 | 641 | .843373 | .739537 | .788049 |
| 50 ms / ADT_STR unnormalized | 1512 | 578 | 949 | .723445 | .614384 | .664469 |
| 50 ms / ADT_STR normalized | 1617 | 915 | 844 | .638626 | .657050 | .647707 |

Normalization recovers 105 matches relative to unnormalized ADT_STR, but adds
337 false hits. All five predeclared accuracy safeguards against ADTOF fail.
The candidate also fails token integrity: eleven chunks lack EOS and twelve have
grammar issues. The failure locations change; normalization does not fix them.

| Recording | ADTOF F1 | ADT_STR unnormalized F1 | ADT_STR normalized F1 |
|---|---:|---:|---:|
| 80sRock | .813008 | .814433 | .746269 |
| CoolJazz | .531969 | .408377 | .435766 |
| SpeedMetal | .946274 | .929915 | .927242 |
| Beatles | .666667 | .868613 | .839416 |
| FreeJazz | .777862 | .540832 | .531575 |
| FusionJazz | .877953 | .727273 | .705140 |
| Punk | .937028 | .791045 | .826733 |

| Family | Normalized TP / FP / FN, 50 ms |
|---|---|
| Kick | 584 / 83 / 68 |
| Snare | 557 / 119 / 396 |
| Hi-hat | 265 / 436 / 103 |
| Tom | 36 / 34 / 45 |
| Cymbal | 157 / 166 / 218 |
| Other | 18 / 77 / 14 |

Hi-hat false predictions rise from 207 to 436 relative to unnormalized ADT_STR.
The final quiet 80sRock chunk becomes malformed after normalization. Amplifying
quiet material is a concern, but no new silence cutoff or suppression rule was
chosen after inspecting these results. Normalized 50-ms matched timing has median
absolute 9.167 ms, p90 17.716 ms and signed median -6.042 ms. At 25 ms, median/p90
absolute errors are 8.958/15.833 ms. Similar conditional timing does not repair
instrument false positives and missed notes.

## Preservation and next decision

**74 focused tests pass**, including prior chart-parser and source-model/frontend
integrations plus new original-batch/tail and per-segment normalization controls.
The runtime, original-input and normalization protocols protect 99, 15 and 29
file-hash entries respectively; these overlap and should not be counted as unique
files. All 642 accumulated prior experiment hashes are rechecked at finalization.
Saved charts, scores and exact normalization inputs are independently read back.
`evidence/verification.json` and the final artifact manifest record final counts.

The source/continuity archive, ignored/untracked inventories, package inventory,
installation logs and separate runtime/cache/temp path-size inventory are retained.
This preserves recoverable C: copies; it is not an independent-device backup.
The first test log has 72 passes, before the two normalization tests were added;
`evidence/tests-final.log` has the complete 74-pass result.

WHITE WAVES' China at 1.000 s, Death Before Dishonor's kick/crash at 8.750 s and
their coincident false-hi-hat removals are unchanged. Blanket hi-hat suppression
remains rejected. Knuckles' repeated tapping remains disputed, with 35 opening
tom labels and historical scores unchanged. No uncertain KLEWS or reserved Adapt
inference, m!sa acceptance run, app/default change, broad download, training,
publication or external message occurred.

**Stop ADT_STR runtime/gain/decoder experiments without new primary evidence.**
The tested declared runtime does not explain failures; original audio and the
source-defined normalization do not produce an acceptable path. Keep the
original-parity ADTOF as the development comparison baseline, without claiming
adequate full-song accuracy. The next model search should explicitly target the
remaining snare/brush and tom recall deficit, require a reproducible checkpoint
and usable instrument mapping, and screen one candidate on this same benchmark.
Do not spend another turn sweeping this model's tau variants, gains or decoder
settings. No need to repeat the controls completed here.

Reproduction tools:

- `tools/recovery/probe_adt_str_runtime.py`: prepare, run each runtime, compare.
- `tools/recovery/probe_adt_str_original_drums.py`: conditional paired inputs.
- `tools/recovery/probe_adt_str_normalization.py`: single source-defined contrast.

Use the old recovery Python for preparation/scoring and the new isolated runtime
for declared-runtime inference. All result directories refuse overwrite. Read
`comparison.json`, `original-controls/metrics.json`, `segment-normalization/metrics.json`
and this report before continuing. No inference process remains running.
