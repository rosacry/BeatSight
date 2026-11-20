# ADT_STR: fixed seven-recording development comparison

Verified 2026-10-15, America/New_York.

The paused session is recovered. All **491 prior artifact hashes** in the
accumulated preservation manifests match. The different pretrained model was
tested on all seven development recordings and **rejected in this configuration**:
50-ms F1 falls **.788049 -> .664469**, with 308 fewer matched hits and 240 more
false hits. All five frozen accuracy safeguards fail. No application default,
user chart or m!sa acceptance-song change was made.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-adt-str-comparison-01`.
D: and F: stayed read-only. Earlier experiments and user-supported corrections
are intact. This is recovery of session state and verification of preserved
artifacts, not recovery of the previously lost F-drive audio collection.

## Candidate and acquisition

The prior model inventory contained many copies of the inherited classifier,
which had already performed poorly. Primary-source research identified
[ADT_STR](https://github.com/pier-maker92/ADT_STR), a different encoder-decoder
Transformer with 26 drum/percussion classes. Its
[paper](https://arxiv.org/abs/2601.09520) describes synthetic MIDI/sample training
and evaluation on ENST and MDB. The author-default `setting-tau-0.8` was fixed
before any local inference or scoring; no other weight variant was acquired.

Reproduction identity:

- GitHub source revision: `77dbef225e7029478ebfb916f20c7a00274f0f12`.
- [Author checkpoint repository](https://huggingface.co/Pierfrancesco/adt-str):
  revision `a33c5c6b191a4ca1e0f6dc22140947485eb36ce8`.
- File: `setting-tau-0.8/model.safetensors`, **289,134,056 bytes**.
- SHA-256: `f94d1773d929166e0a3f63d305975aa6667512f8a71d7706872e1f8b23ca930b`.
- Published LFS size/hash match. Downloaded source files match their Git blob IDs.
  The eight inference-related files cross-checked between GitHub and the HF
  bundle are byte-identical.
- Strict model loading accepts **132 state tensors**, with no missing or extra
  keys; the model has **69,000,824 trainable parameters**.

The pinned primary repository's LICENSE and README declare CC-BY-SA-4.0. The HF
model card has no separate license field. Those statements are preserved as
source evidence; they do not establish rights to redistribute training audio or
commercially deploy a derived product. Only local evaluation occurred. No dataset
download, training, public upload or external message was performed.

The authors already evaluated/recommended this variant using MDB. Therefore this
is **development screening, not independent held-out validation**. Musical overlap
with synthetic Lakh-derived training material is unresolved. Estimated separated
stems also differ from the original drum-only evaluation setting.

## Frozen execution and mapping

`selection.json` precedes weight acquisition; `protocol.json` precedes inference.
The baseline is the verified original-parity ADTOF from the previous model audit,
with source-aligned frontend, corrected max pooling and primary decoding.
All seven identical saved mono FLOAT drum stems are used: 454.934 seconds and
2,461 reference events, including all 32 OT targets. No fresh separation,
normalization, onset correction, threshold fitting or masking.

The reviewed native ADT_STR code runs unchanged: 24-kHz torchaudio resampling,
2.56-second chunks, final zero padding, batch size 8, greedy decoding, maximum
512 tokens, float32 CUDA on the RTX 3080 Ti, seed 0, two CPU threads, deterministic
algorithms and TF32 disabled. Only the sampling call is wrapped to save returned
tokens. Inference across the seven recordings took approximately 198.1 seconds,
excluding model startup. All 182 expected chunks, including final partial chunks,
were processed. No output onset falls beyond an input recording's duration.

The existing recovery environment was reused without package installation:
torch/torchaudio **2.5.1+cu121**, transformers **4.57.3**, safetensors **0.5.3**.
Upstream declares torch/torchaudio 2.8.0 and the checkpoint configuration names
transformers 5.3.0. This is a reproducible compatibility execution of the native
source, **not verified parity with the declared upstream runtime**. The rejection
applies to this tested configuration; it is not a claim to have reproduced or
disproved the paper's scores.

Custom output pitches **35–60 are not General MIDI**. For example custom 44 is
open hi-hat, 46 is crash, 49 is China and 50 is tambourine. The adapter follows
the source mapping and the existing MDB taxonomy: side stick and tambourine
remain OT. All 26 classes have explicit mappings; nothing is silently discarded.
Simultaneous hits and distinct same-family predictions survive the adapter.
Native exact-note deduplication remains part of the upstream implementation.
The saved `native-custom-pitches.mid` files retain custom pitches and are **not GM
playback exports**. Scoring uses decoded native notes, not MIDI roundtrips.

## Results

These are scores of the unchanged native exports. Token failures below are an
additional reason the configuration cannot be accepted.

| Tolerance / model | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 25 ms / ADTOF baseline | 1772 | 386 | 689 | .821131 | .720033 | .767266 |
| 25 ms / ADT_STR | 1447 | 643 | 1014 | .692344 | .587972 | .635904 |
| 50 ms / ADTOF baseline | 1820 | 338 | 641 | .843373 | .739537 | .788049 |
| 50 ms / ADT_STR | 1512 | 578 | 949 | .723445 | .614384 | .664469 |

| Recording | Baseline F1, 50 ms | ADT_STR F1, 50 ms |
|---|---:|---:|
| 80sRock | .813008 | .814433 |
| CoolJazz | .531969 | .408377 |
| SpeedMetal | .946274 | .929915 |
| Beatles | .666667 | .868613 |
| FreeJazz | .777862 | .540832 |
| FusionJazz | .877953 | .727273 |
| Punk | .937028 | .791045 |

| Family | Baseline TP / FP / FN | ADT_STR TP / FP / FN |
|---|---|---|
| Kick | 589 / 41 / 63 | 583 / 88 / 69 |
| Snare | 578 / 18 / 375 | 522 / 55 / 431 |
| Hi-hat | 303 / 178 / 65 | 205 / 207 / 163 |
| Tom | 38 / 19 / 43 | 36 / 7 / 45 |
| Cymbal | 312 / 82 / 63 | 144 / 102 / 231 |
| Other | 0 / 0 / 32 | 22 / 119 / 10 |

The extra classes recover 22 OT targets, but introduce 119 OT false predictions.
The largest loss is cymbals (168 fewer matches), followed by hi-hat (98) and
snare (56). Higher tom precision does not compensate for fewer matched toms.
The Beatles improvement does not justify selection when five other tracks regress.

At 50 ms, candidate median absolute matched error is 9.167 ms, p90 17.292 ms and
signed median -5.833 ms; baseline values are 9.167, 17.500 and -5.417 ms. At 25 ms,
candidate median/p90 absolute errors are 8.750/15.208 ms. Timing summaries are
conditional on each model's matches; similar timing does not offset missing hits.

The frozen gate requires F1 gain >=.01, precision loss <=.01, no individual-track
F1 loss >.02, nondecreasing tom matches and snare recall loss <=.01. **All fail**.
No sweep, gain adjustment, beam search, alternative checkpoint, app promotion or
full m!sa acceptance-song run followed this result.

## Native token failure diagnosis

Of 182 chunks, **11 reach 512 tokens without EOS and have incomplete or malformed
grammar**: CoolJazz chunks 9, 29, 30, 38; FreeJazz 7, 14, 20, 23, 28, 32, 39
(zero-based). Some repeat an identical time/pitch/velocity triplet; others loop
on pitch tokens alone. No decoder settings were changed to hide those failures.

There are 3,621 decoded notes before native exact-note deduplication and 2,090
after it. There are no zero-velocity notes. Raw per-batch tokens, native notes,
custom MIDI, resampled inputs, charts, per-event matches and audits are preserved.

The post-run read-only audit independently reconstructs adjacent time/pitch/
velocity triples. All 171 well-formed chunks agree exactly. In fact, **none of
the 182 actual chunks has an association difference** against that reconstruction,
and all seven final native note arrays reproduce exactly. Thus a mapping or
field-association repair is not an evidenced explanation for these measured losses.

A separate small counterexample does reveal a latent native tokenizer bug: it
zips dictionary values with different token-index keys, so an orphan time token
can change a later note's onset. `token-format-audit.json` records the example.
That bug did **not** change these saved outputs versus adjacent-triple decoding.
No corrected chart or opportunistic rescore was produced. The audit oracle first
used float32, while NumPy token decoding yields float64; correcting the oracle's
dtype enabled exact comparison. Candidate inference/results were unchanged.

## Preservation, verification and continuation

**70 focused tests pass**, including the real chart importer, prior source
frontend/model checks and new custom-mapping, simultaneous-hit, token grammar and
tail-chunk controls. All **80 frozen input/source/checkpoint hashes** match after
inference. The 491 prior artifact hashes are rechecked at finalization. Source,
tests, reports and updated continuity documents have a verified final archive.
Git status plus ignored and untracked file inventories were captured before work.
These are C: preservation copies, not an independent-device backup.

The WHITE WAVES China at 1.000 s and Death Before Dishonor kick/crash at 8.750 s
remain intact, including removal of the coincident false hi-hats. Blanket hi-hat
suppression remains rejected. Knuckles' repeated opening tapping remains disputed
as the user described; its 35 tom targets and historical scores are unchanged.
Uncertain KLEWS and reserved Adapt were excluded from model selection.

**Next bounded question:** determine whether the ADT_STR token failure reproduces
under its declared upstream runtime before attributing it solely to model quality.
Use fixed cached chunks, one normal control and the already-identified failure
chunks, with unchanged weights and decoding; a small isolated C: runtime/parity
probe is sufficient. If it reproduces, the already-local original-drum CoolJazz
and FreeJazz controls can separate input-domain failure from failure on clean
drums. Neither diagnostic would authorize tuning on reserved songs or revising
the failed seven-stem result. Do not sweep checkpoints or train broadly.

Reproduction entrypoint: `tools/recovery/compare_adt_str.py prepare|run --root ...`.
Preparation requires source/checkpoint receipts and fails on an existing protocol;
inference refuses an existing output folder. Do not rerun into this completed root.
The root's `selection.json`, `protocol.json`, `full-recordings/metrics.json`,
`evidence/token-format-audit.json` and `evidence/verification.json` are the durable
handoff. The old local review server was not restarted because this comparison
does not require a new listening decision.
