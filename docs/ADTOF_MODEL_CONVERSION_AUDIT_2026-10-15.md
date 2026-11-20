# ADTOF model conversion: pooling correction and original-checkpoint parity

Verified 2026-10-15, America/New_York.

The model-conversion question is now substantially resolved for the tested
configuration. All **50 converted weight tensors exactly match the published
original checkpoint** after the documented layout/gate mapping. Correcting the
port's max-pooling boundary makes its outputs numerically match the actual
original TensorFlow model on fixed features, with **identical decoded charts on
all seven development recordings**. The remaining misses are also present in
the original model on these inputs. More speculative conversion changes are not
justified.

The pooling-only candidate improves 50-ms F1 **.783532 -> .788049**, but fails the
predeclared minimum .01 improvement gate. It is retained as a verified
compatibility correction, not an accuracy promotion or application change.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-adtof-model-audit-01`.
Previous experiments, checkpoints, user charts and corrections remain unchanged.
D: and F: stayed read-only.

## Inventory and bounded acquisition

The current repository and `C:\Users\10ros\BeatSight-Recovery` were searched with
hidden/ignored files included, excluding Git internals, virtual environments,
node_modules and Python caches. `inventory.json` records 510 checkpoint-shaped
file candidates, with no original TensorFlow `.index`/data, HDF5 or Keras-format
checkpoint in those scopes. This was not a whole-computer or archive-content
search. The two local bundled port weights have the same SHA-256:
`1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320`.
The recovery environment initially had no TensorFlow, Keras or h5py.

Subsequent inspection of the pinned original repository tree found the exact
[Frame_RNN_adtofAll_0 checkpoint](https://github.com/MZehren/ADTOF/tree/b3968fb332f69b65ee07c089fc62f436503755db/adtof/models)
named by the converter. Its two files total **5,428,542 bytes**; both were copied
to `original-checkpoint/` and verified against the repository's Git blob SHA-1
as well as recorded SHA-256. This bounded acquisition followed measured conversion
discrepancies; it was not a dataset/model search or bulk download.

An isolated `tf-runtime/` under the new root contains TensorFlow CPU 2.13.1,
Keras 2.13.1 and NumPy 1.24.3. Installation cache and temporary paths were also
scoped under the new root. The existing recovery environment was not modified.
`evidence/runtime-install.log` and `tf-runtime-freeze.txt` record installation.
No old files or experiment directories were cleaned up.

## Source audit and numerical controls

The [original model builder](https://github.com/MZehren/ADTOF/blob/b3968fb332f69b65ee07c089fc62f436503755db/adtof/model/model.py)
uses two CNN blocks: convolution/ReLU, batch normalization, convolution/ReLU,
batch normalization, frequency max pooling and dropout. Three bidirectional
60-unit GRUs feed a five-output sigmoid layer. With Frame_RNN's context 9,
the four convolutions already supply the temporal receptive field; neither
implementation needs extra context concatenation. Flattening is time/frequency/
channel in both, and dropout is disabled for inference.

The preserved port pads `SamePadWidthMaxPool` with **zero**. TensorFlow's
[pooling implementation](https://github.com/tensorflow/tensorflow/blob/v2.13.0/tensorflow/core/kernels/pooling_ops_common.h)
takes maxima over real input positions, initializing to the lowest representable
value. Negative values can occur after batch normalization, even after preceding
ReLU. Zero padding therefore changes boundary outputs. With width 28 and input
`[-1, -2, ..., -28]`, the correct first/last maxima are -1/-27; the port returns
zero at both boundaries. The first pool width 84 needs no padding, but the second
pool width 28 does.

`tools/recovery/model_adtof_reference.py` supplies a recovery-only replacement
using negative-infinity padding for finite activations. It changes only a newly
instantiated model in memory; model state tensors are verified unchanged.

The source audit also found a suspicious default in `dev/convert_weights.py`:
merging the recurrent candidate bias into the input bias changes its reset-gate
scaling. The [Keras GRU equations](https://github.com/keras-team/keras/blob/v2.13.1/keras/layers/rnn/gru.py)
place that recurrent bias inside the reset multiplication. A zero-input/state,
unit candidate-bias example gives .231059 with separate biases and .380797 after
merging. However, **that does not describe the bundled checkpoint**: all six
directions retain 60 nonzero recurrent candidate biases. The later exact original
weight comparison confirms the correct separate-bias mapping. No bias edit or
GRU-flag experiment was performed.

`protocol.json` freezes the source-semantic audit before measurements:

- 300 seeded pooling arrays cover widths 1–100 and negative/mixed/nonnegative
  inputs. The replacement matches independent valid-window maxima in all cases;
  the zero-padding port fails 134 cases.
- The same 16 previously frozen real mix/stem excerpts provide feature frames
  168:232. All 16 expose the second-pool discrepancy; maximum difference .581940.
- 128 local convolution/normalization checks pass `atol=1e-5, rtol=1e-4` against
  independent NumPy equations. Maximum absolute difference is 1.033e-5, with
  relative tolerance accounting for scale.
- Reviewed Keras `GRUCell.call`, executed as an isolated AST function with NumPy
  primitive shims, agrees with all three converted bidirectional layers on real
  and synthetic inputs: 51 bidirectional comparisons, maximum error 9.82e-7.

These initial checks were source-semantic controls, not an original-model run.
`layer-audit.json` preserves that initial limitation. The actual checkpoint
comparison below supersedes its missing-runtime/checkpoint limitation without
overwriting the earlier evidence.

## Pooling-only development comparison

`full-recordings/protocol.json` was frozen before inference. Baseline is the
previous source-aligned frontend run; both arms use identical saved mono FLOAT
drum stems, source-aligned frontend, pinned weights and primary decoder. CPU,
two threads, seed zero, 100 fps and thresholds `[.22,.24,.32,.22,.30]` are unchanged.
No new separation, gain adjustment, fitted timing, threshold sweep or reserved
song inference. All seven complete development recordings are retained, with
2,461 targets including 32 unsupported OT events.

One full 80sRock baseline control exactly reproduces its saved activations. Model
weights load strictly; all state tensors are identical before/after pool replacement.

| Tolerance / pooling | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 25 ms / zero padding | 1767 | 387 | 694 | .820334 | .718001 | .765764 |
| 25 ms / corrected | 1772 | 386 | 689 | .821131 | .720033 | .767266 |
| 50 ms / zero padding | 1808 | 346 | 653 | .839369 | .734661 | .783532 |
| 50 ms / corrected | 1820 | 338 | 641 | .843373 | .739537 | .788049 |

| Recording | Baseline F1, 50 ms | Corrected F1, 50 ms |
|---|---:|---:|
| 80sRock | .823529 | .813008 |
| CoolJazz | .551810 | .531969 |
| SpeedMetal | .939551 | .946274 |
| Beatles | .650519 | .666667 |
| FreeJazz | .769823 | .777862 |
| FusionJazz | .878578 | .877953 |
| Punk | .898990 | .937028 |

| Family | Baseline TP / FP / FN | Corrected TP / FP / FN |
|---|---|---|
| Kick | 585 / 34 / 67 | 589 / 41 / 63 |
| Snare | 577 / 17 / 376 | 578 / 18 / 375 |
| Hi-hat | 297 / 177 / 71 | 303 / 178 / 65 |
| Tom | 38 / 31 / 43 | 38 / 19 / 43 |
| Cymbal | 311 / 87 / 64 | 312 / 82 / 63 |
| Other, unsupported | 0 / 0 / 32 | 0 / 0 / 32 |

At 50 ms, median absolute matched error stays 9.167 ms; p90 changes 17.292 ->
17.500 ms and signed median -5.625 -> -5.417 ms. At 25 ms, corrected median/p90
absolute errors are 9.091/16.659 ms. These are conditional on each arm's matches.
`metrics.json` and individual event exports retain all per-family and track scores.

The .004517 F1 gain fails the predeclared minimum .01 gain. Other safeguards pass:
precision loss <=.01, any-track F1 loss <=.02, tom TP nondecrease, snare recall
loss <=.01. Relative to the older port frontend with primary decoding (.786303),
the corrected frontend/model total is only .001747 higher. This remains a limited
development result, not an established practical accuracy improvement.

## Actual original-checkpoint parity

After discovering the original checkpoint, `original-parity/protocol.json` froze
an exact tensor comparison, the same 16 feature excerpts and all seven full
feature sequences. Features are saved once, hashed, and passed unchanged to both
runtimes. This is a parity test, with no alternative candidate or score selection.

`run_original_adtof_model.py` executes only the reviewed original
`Model._getCRNNFunctional` definition with the actual TensorFlow runtime. It uses
the explicit Frame_RNN configuration and original checkpoint. TensorFlow asserts
that every existing model object was matched when loading. Extra optimizer state
is outside inference. CPU uses two intra-op threads/one inter-op thread, seed zero,
and oneDNN is disabled for this comparison. Runtime/model configuration and
checkpoint variable listings are saved in `tf-model.json`.

The results in `original-parity/comparison.json` establish:

- **50/50 mapped original tensors match the bundled PyTorch tensors exactly**,
  including all convolution/normalization tensors, GRU kernels and separate
  input/recurrent biases, and output weights.
- All 15 corresponding stage boundaries on all 16 excerpts pass
  `atol=1e-5, rtol=1e-4` with corrected pooling. Maximum intermediate absolute
  difference is 2.861e-5; final output maximum is **3.28e-7**.
- The uncorrected pooling model has final excerpt output errors up to .136946.
- On all seven full feature sequences, corrected PyTorch outputs match the
  original TensorFlow outputs within the frozen tolerance; maximum absolute
  difference is **1.13e-6**.
- The unchanged primary decoder produces **exactly identical charts** for all
  seven original/converted output pairs. All corresponding 25/50-ms score
  dictionaries match the corrected pooling result above.

This is actual original-model/weight parity on the tested features, not merely
agreement between two descriptions of equations. It does not execute the complete
original madmom audio file loader, resampler or integer-PCM path. The already
verified frontend contract remains mono float32 PCM at 44.1 kHz; the saved stems
meet that contract. It does not establish accuracy on arbitrary music.

## Verification, preservation and next direction

**66 focused tests pass**, including real chart-parser integration, source frontend
checks, negative pooling boundaries, all width remainders and the primary GRU
bias counterexample. An initial test fixture expected -28 for the last pool;
inspection of its two real values corrected that expectation to -27. The
implementation/oracle agreed before and after this test-only correction.

All **72 frozen pooling-comparison hashes** match before/after; all **61 parity
protocol input/source hashes** match. **358 prior artifact hashes** match. Both
m!sa opening corrections, clarified Knuckles repeated-tapping feedback and its
35 disputed targets are preserved. No chart deletion, scoring mask, app/default
change, training, publishing or external message occurred. D:/F: stayed read-only.

`evidence/` contains pre-edit continuity documents, status and ignored/untracked
file inventories, runtime installation/freeze records, preservation receipts and
the verified final source/document archive. Experiment results/checkpoint/source
files are hash-manifested; installed runtime/cache/temp files have a separate
inventory and are excluded from the evidence-content manifest. These are all C:
copies, not an independent-device backup.

The model still misses **375/953 snares and 43/81 toms** on these separated inputs.
Earlier original-drum oracle probes also retained brush/ghost-note misses, so
separation alone is not an established solution. Five-family output lacks detailed
kit/cymbal articulation, benchmark training overlap is unknown, and these are
short complete development recordings rather than seven commercial full songs.

**Next: stop conversion/input/threshold tweaking and select one meaningfully
different existing pretrained transcription model for a frozen comparison.**
Reuse local inventory and established primary implementations first; require a
reproducible checkpoint, explicit output mapping, simultaneous-hit support and
relevant snare/tom coverage. The inherited BeatSight classifier already lost badly
on these seven recordings; do not blindly rerun it or its many epoch copies.
Document training overlap and use/access terms before acquiring anything new.
Use the same development recordings and per-family 25/50-ms timing scores; only
a convincing improvement should proceed to the full m!sa acceptance songs.
Preserve their corrected openings and keep uncertain KLEWS/previously reserved
Adapt out of parameter selection. Broad retraining/downloads remain unjustified.

## Reproduction entrypoints

Use `.venv-recovery\Scripts\python.exe` for `audit_adtof_model.py`,
`probe_reference_pooling.py`, and `compare_original_adtof_model.py`. The first
two have `prepare` and `run` actions with `--root`; the comparator takes `--root`.
Use the scoped `tf-runtime\Scripts\python.exe` only for
`run_original_adtof_model.py --root ...`. Protocols, source receipts and input
feature hashes identify exact inputs. These completed output folders refuse
overwrite; prepare a fresh C: root for any necessary reproduction. The parity
features use the saved source-aligned frontend: frames 168:232 for each of the
16 prior excerpts and the full sequence for each of the seven saved stems.
