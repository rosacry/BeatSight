# Separate-and-Detect feasibility audit

Verified 2026-10-16, America/New_York. **Do not acquire weights or promote this
candidate from the present evidence.** The release exists, but its documented
inference path does not yet support a faithful full-song comparison. Seventeen
bounded source/PCM probes reproduce coverage, timing and decoder problems.
No neural transcription or new accuracy measurement was performed.

New root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-16-separate-detect-audit-01`.
All 1,836 protected prior files verify. Previous brush-control scores, 988 native
notes, 958 merged events, 860 retained baseline events and 645 non-snare events
reconstruct, including 60 independent matching-cardinality checks. The preceding
90-test log is preserved; those tests were not rerun in this source-only audit.

## Release identity and relevance

- [Author source](https://github.com/ddman1101/Separate-and-detect/tree/0ac2fe6a35a7968d70ecfb8866cad025c350f5bd):
  commit `0ac2fe6a35a7968d70ecfb8866cad025c350f5bd`. 130 bounded code/config/license
  files match their Git blob IDs and saved SHA256 hashes. A separate author
  Beatles example also matches its blob. No repository audio was downloaded.
- [Author weights](https://huggingface.co/ddman1101/Separate-and-Detect/tree/5384a5dcf7456ea5876de2b350438f0cfbe34726):
  revision `5384a5dcf7456ea5876de2b350438f0cfbe34726`. Metadata lists
  `msgld_ob.ckpt` (5,398,491,630 bytes, SHA256
  `cfc681e51395af954edec67921298e8b4099c9222ab433817f675650ad57d19c`)
  and `msgld_obtb.ckpt` (5,398,799,061 bytes, SHA256
  `ffead7341064caf0d6cb87fa0da1abc7d2259648ddfb3b6bd1848ce37d3dbcd1`).
  These are advertised metadata hashes; no weight bytes were acquired or loaded.
- [MusicLDM components](https://zenodo.org/records/10643148) list a 756,843,351-byte
  VAE and 221,242,730-byte HiFi-GAN. One OB checkpoint plus these two components
  totals **6,376,577,711 bytes**, before runtime, detector and perceptual assets.
  Source LICENSE/HF card declare MIT; Zenodo metadata declares CC-BY-4.0.
  These declarations do not resolve all training-data or redistribution rights.

The [paper](https://arxiv.org/html/2608.01093v1), Table 3, reports the following
50ms F1 values. These are author results, not BeatSight measurements:

| Set | Model | Overall | Snare | Toms | HH | Cymbals |
|---|---|---:|---:|---:|---:|---:|
| MDB | ADTOF | .795 | .752 | .520 | .773 | .849 |
| MDB | MSG-LD +OB | .707 | .760 | .268 | .650 | .481 |
| ENST | ADTOF | .709 | .599 | .581 | .777 | .657 |
| ENST | MSG-LD +OB | .640 | .642 | .491 | .630 | .391 |

Kick also improves in the author's comparison. This supports a narrow possible
kick/snare benefit, not a replacement addressing the observed tom/HH/CY errors.
No brush-specific result establishes a solution to BeatSight's brush confusion.
The paper reports roughly 25 seconds per 10 seconds on RTX 6000 Ada; local speed
and memory use remain unmeasured. These figures cannot be directly compared with
our pooled full-recording metrics because inputs, partitions and scoring differ.

## Actual source path and executed probes

`integrated_train.py --separate_only` constructs the model and calls Lightning
validation. The inference YAMLs select `StemGMDOnsetDataset`, 16kHz features,
1024 frames and 160-sample hop: **10.24-second segments**. Stem order is
`kick/snare/toms/hi_hats/cymbals` → `KD/SD/TT/HH/CY`. No separate China, ride,
tom-pitch or brush articulation class is available. The upstream full-mixture
front end is `htdemucs`; BeatSight's previous baseline used `htdemucs_ft`.
Cached inputs could be reused in a future adapted experiment, but that would
need explicit disclosure and a fixed input contract.

`tools/recovery/audit_separate_detect.py` verifies the pinned source before
extracting only inspected methods through AST. It executes native loader methods
on synthetic WAV files and native postfilters on supplied peaks. It does not
import the training module, instantiate networks or mock a successful model run.
Results are in `io-probes-02/results.json`:

1. **Unprocessed tails and excluded songs.** The native duration filter excludes
   files shorter than 10s or at least 640s. The segment list drops partial tails.
   A 75.16s fixture has seven segments ending at 71.68s: **3.48s unread**.
   A 450s fixture ends at 440.32s: **9.68s unread**. Eight duration cases exercise
   exact boundaries and partial tails. Source: `dataset.py:2323-2398`.
2. **Timing roundtrip fails on longer songs.** The loader serializes integer
   seconds; `mdb_onset_evaluation.extract_segment_info` divides this by ten and
   multiplies by 10.24. At actual 430.08s, `_from_430` becomes **440.32s**, an
   entire segment late. The 450s fixture tests all 43 segment names and finds one
   mismatch. Source: `dataset.py:2829`, `mdb_onset_evaluation.py:423-438`.
3. **Input sample rate is assumed to be 44.1kHz.** At requested 10.24s, native
   `read_wav` actually reads 28.224s in a 16kHz file, 10.24s in a 44.1kHz file,
   and 9.408s in a 48kHz file. The latter output includes 13,312 padded zeros.
   Real load arguments and raw ramp PCM verify this before native resampling.
   Source: `dataset.py:2425-2433`. Existing 16kHz cached stems cannot simply be
   handed to this loader without conversion or a disclosed correction.
4. **Onset loss at segment edges.** KD/SD/TT/CY native postfilters discard peaks
   below .2s or above duration−.2s. Supplied .1s and 10.09s peaks disappear from
   a 10.24s segment. Thus adjacent segments can lose true edge attacks even if
   the network detects them. HH has different behavior. These are deterministic
   postfilter tests, not evidence of which real notes the CNN would detect.
5. **Declared spacing arguments are mostly unused.** `min_separation` is read
   only by the HH function; KD/SD/TT/CY ignore it. Supplied .50s/.55s peaks both
   survive those four postfilters despite a .1s argument. Native peak-picking
   may impose other constraints; this test isolates the explicit postfilter.

The first probe attempt stopped because a ramp-amplitude oracle assumed unity
DC gain after torchaudio resampling. The amended harness records actual load
arguments/raw PCM instead. Cases and native source remain unchanged. The failed
`io-probes/` folder, byte-exact original harness, original protocol and amendment
are retained; `io-probes-02/` is the completed run. No rerun overwrote outputs.

The separate single-audio script finds already-generated sibling stem files;
it is not a full-song separator. It emits segment-relative times without a
full-recording assembler. A `generate_long_sample` method exists elsewhere, but
the documented validation path invokes `generate_sample`; its presence does not
repair these observed loader faults.

## Decoder and execution limits

The paper describes thresholds .35–.60 and spacing 30–50ms. Released constants
instead include KD .71236, SD .24426, HH .08598, TT .55712, CY .39458, with spacing
values about 59–194ms, mostly unused as noted above. Filters are class-specific.
The [saved script](https://github.com/ddman1101/Separate-and-detect/blob/0ac2fe6a35a7968d70ecfb8866cad025c350f5bd/single_audio_onset_detection.py)
is reproducible source, but paper-decoder parity is **unresolved**. Do not sweep
these settings or silently select the more favorable description.

The declared Linux environment uses Python3.9, torch1.13.1+cu116 and Lightning1.9.4;
the onset environment uses Python3.10 and madmom. Local recovery runtime is
Python3.11, torch2.5.1+cu121, Lightning2.6.0, NumPy2.3.5. madmom, taming, timm and
torchlibrosa are absent there. Native source imports removed Lightning symbols,
constructs a training perceptual loss in the VAE, and imports CLAP data code
that initializes three Hugging Face tokenizers at import time. Patch conditioning
itself does not require a CLAP checkpoint. Do not blindly install/run the whole
training environment or claim every listed model asset is required for inference.

The launcher also substitutes `ckpt_path=None` if the main path is missing;
an eventual runner must fail closed instead. Its validation path computes losses
and imports evaluation code despite the separation-only label. A native-compatible
minimal loader needs strict checkpoint/key verification and scoped caches before
any useful model run. Current GPU inventory: RTX3080Ti, 12,288MiB total and
5,051MiB free at observation; C: about421GB free. Availability changes, and neither
snapshot proves the model fits. No shared runtime was modified.

## Overlap, decision and next work

The paper declares separator training on StemGMD and IDMT-SMT-Drums, detector
tuning on MDB's MIREX training split, and evaluation on MDB/ENST. The complete
pinned tree exposes no exact split/checkpoint training manifest establishing
exclusion of our seven MusicDelta tracks or six ENST recordings. The release
includes a MusicDelta_Beatles transcription example. Treat these recordings as
exposed development/additional validation; IDMT is explicitly training data.
KLEWS and Adapt remain outside tuning. Generalization is unproved.

**Decision: defer this candidate's weights and comparison.** The full-song
contract fails before neural execution, decoder provenance is inconsistent, and
published family results give weak support for the present bottleneck. This is
a feasibility decision, not a locally measured accuracy rejection. Do not spend
the next session automatically repairing the training framework. Reopen only on
corrected primary evidence or a concrete, discriminating justification.

Next perform one bounded feasibility audit of the **Jarredou/aufr33 six-stem
MDX23C DrumSep release**, starting with the existing local inventory and the
[primary paper's source pointer](https://arxiv.org/html/2509.24853v1).
That paper reuses ADTOF onsets and refines velocities and cymbal/HH subclasses;
it does **not** establish recovery of missed snares or repair of SD/HH confusion.
Check exact checkpoint provenance, mapping, native full-song behavior, overlap
and whether separate family audio offers a testable answer to the measured
confusion before acquiring weights. No blanket suppression, threshold/gain sweep
or new fusion rule follows merely from the paper. If the approach cannot address
the measured issue, record that and stop its acquisition branch.

The previous failed snare merger remains rejected. Any future candidate requires
predeclared development gates, separate validation and full-song m!sa acceptance
in existing practice views. No application/default/user chart changed here.
D:/F: stayed read-only; prior assets, opening corrections and Knuckles'35 disputed
targets remain unchanged/unmasked. The user's guitar-like feedback concerned
REPEATED TAPPING. New artifacts are confined to this C: root; C: preservation is
not an independent-device backup. Read `protocol.json`, its probe amendment,
`evidence/decision.json`, `evidence/verification.json` and the final manifest.
Ignored/untracked paths are inventoried; this does not claim every ignored file
is covered by a content hash. Only the three recovery documents, this report and
the new source-probe helper change in the repository during this audit.
