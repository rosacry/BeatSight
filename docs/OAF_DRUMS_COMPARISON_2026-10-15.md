# Official E-GMD / Onsets and Frames comparison — 2026-10-15

## Outcome

The single frozen E-GMD checkpoint **fails the replacement gate**. It recovers
more snares and toms, but loses cymbals and overall precision/recall. No app/default
promotion, user-song replacement, threshold sweep or acceptance-song inference.
All 810 earlier artifact hashes match; 76 recovery tests pass.

New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-oaf-drums-comparison-01`.
D: and F: stayed read-only. Previous experiments and user-supported corrections
are unchanged. This continuation recovered session state, not the lost F: audio.

## Selection and reproducibility

- [Official implementation and checkpoint instructions](https://github.com/magenta/magenta/blob/c15687ebd1c1cc12658cd468c737d3c24c02b918/magenta/models/onsets_frames_transcription/README.md).
  Source revision `c15687ebd1c1cc12658cd468c737d3c24c02b918`; 49 bounded source
  files verified against the Git tree's blob hashes. Original files are unchanged.
- [Official checkpoint](https://storage.googleapis.com/magentadata/models/onsets_frames_transcription/e-gmd_checkpoint.zip):
  25,658,703-byte archive, SHA256
  `09765ae0ff19c7d769a3c20e158eba3b9cd279429b02e498b1e911d16f82e2c0`.
  Step 569400; all **78 graph variables / 4,490,488 scalar values** restore exactly
  from checkpoint tensors. Extra optimizer checkpoint state is not inference state.
- Source is Apache-2.0. The [E-GMD dataset page](https://magenta.tensorflow.org/datasets/e-gmd)
  states CC-BY-4.0 for that dataset. A separate explicit checkpoint license was not
  located; public access is not a conclusion about all commercial rights.
- Noise-to-Notes: no runnable author checkpoint found in the bounded primary
  search. Separate-and-Detect now has an
  [author checkpoint release](https://github.com/ddman1101/Separate-and-detect#checkpoint-release),
  so it remains a future option; it requires separate VAE/vocoder components.
  Neither candidate was downloaded or benchmarked here. `selection.json` was
  saved before the E-GMD checkpoint download and before local inference.

The read-only existing TF2.13.1 CPU runtime is reused from the ADTOF model audit.
New dependencies, build cache, temporary files and outputs stay in this root.
Numerical packages: Keras2.13.1, tf-slim1.1.0, librosa0.7.2, note-seq0.0.3,
NumPy1.23.5, SciPy1.10.1, numba0.57.1, protobuf3.20.3.
Small import aliases restore `numba.decorators.jit` and Keras's legacy layer
module location. Package initialization skips unrelated Magenta generation code;
the required primary common function and all transcription functions execute
unchanged. Import probe failures/logs are retained. Missing SoX is an import-time
warning: augmentation is disabled, all inputs already have the target sample rate,
and no SoX transformation is executed.

This is **TF2.13 compatibility execution, not demonstrated TF1.15 paper-runtime
parity**. Exact variable restoration does not establish historical numerical
parity. The complete resolved dependency inventory and import paths are recorded.

## Frozen input and scoring contract

`protocol.json` protects 89 input/source/checkpoint entries. Same seven complete
MusicDelta development recordings, 454.934 seconds, 2,461 unchanged reference
events, including 32 OT targets. Same saved mono 44.1-kHz float Demucs stems;
no fresh separation, extra training data, gain fit or per-song settings.

Native `process_record` normalizes the whole recording and converts it to PCM16.
Native `provide_batch` computes the mel features and truncates their final partial
frame. The executed setting is **spec_hop_length=512**, 86.1328125 frames/s;
the separate `hop_length=441` field/comment does not control this path. Native
features match a separate direct invocation of the source frontend exactly on all
seven recordings. The source model runs whole recordings, batch1, float32 CPU,
seed0, two intra-op / one inter-op threads; oneDNN optimizations disabled.

Native sigmoid >0.5 onset decisions and `predict_sequence(onsets_only=True)` are
unchanged. Every active onset frame becomes a note, including adjacent active
frames and simultaneous hits. All 2,090 notes are independently reconstructed
from the saved activation grid; 56 adjacent active pairs remain unfiltered. No
predictions fall beyond the recording ends. Native protobuf, Groove-pitch MIDI,
notes, PCM16 input, feature arrays and probabilities are retained per recording.

The actual source training map is **8-hit**, with 88 possible output pitches.
It merges snare/x-stick/clap, tom/conga, HH/tambourine/maracas and ride-bell/cowbell.
Those articulations cannot be recovered from the grouped outputs. Groove extended
pitch semantics are explicit: e.g.22/26 are HH and58 is a tom rim, not generic GM
vibraslap. All emitted base pitches map literally to the existing six-family
benchmark. Unknown pitches would remain OT; no references/predictions are dropped.
This model does not establish fine kit or brush-articulation accuracy.

One-to-one family matching maximizes matches, then minimizes timing error, at
25/50ms. The established original-parity ADTOF is the baseline. Frozen 50ms gates:
F1 gain >=.01, precision loss <=.01, worst recording F1 loss <=.02, tom matches do
not decrease, snare recall loss <=.01. Only the latter two pass. These are
development safeguards, not automatic product promotion.

## Results

| Tolerance / model | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 25ms ADTOF | 1772 | 386 | 689 | .821131 | .720033 | .767266 |
| 25ms E-GMD | 1595 | 495 | 866 | .763158 | .648111 | .700945 |
| 50ms ADTOF | 1820 | 338 | 641 | .843373 | .739537 | .788049 |
| 50ms E-GMD | 1654 | 436 | 807 | .791388 | .672085 | .726873 |

| Family, 50ms | ADTOF TP / FP / FN | E-GMD TP / FP / FN |
|---|---:|---:|
| Kick | 589 / 41 / 63 | 569 / 62 / 83 |
| Snare | 578 / 18 / 375 | 637 / 57 / 316 |
| Hi-hat | 303 / 178 / 65 | 311 / 217 / 57 |
| Tom | 38 / 19 / 43 | 51 / 71 / 30 |
| Cymbal | 312 / 82 / 63 | 86 / 29 / 289 |
| Other | 0 / 0 / 32 | 0 / 0 / 32 |

| Recording | ADTOF F1, 50ms | E-GMD F1, 50ms |
|---|---:|---:|
| 80sRock | .813008 | .707692 |
| CoolJazz | .531969 | .579841 |
| SpeedMetal | .946274 | .931507 |
| Beatles | .666667 | .787004 |
| FreeJazz | .777862 | .689766 |
| FusionJazz | .877953 | .755245 |
| Punk | .937028 | .767568 |

E-GMD timing at50ms: median absolute9.432ms, p90 absolute17.802ms, median
signed-6.752ms; at25ms:9.154/16.340/-6.661ms. Seven measured processing loops
total9.945s, excluding graph construction/imports; this is not whole-application
runtime. E-GMD yields166 fewer matches and98 additional false hits overall.

E-GMD training uses electronic drum-kit performances. Exact benchmark overlap was
not established; these seven tracks are repeatedly inspected development data.
Short complete recordings and estimated stems do not demonstrate full-song
generalization or paper-original-drum results. The curated Clone Hero target
ambiguities, including Knuckles, remain unchanged.

## Cached complementarity audit and next experiment

`evidence/complementarity.json` compares reference indices from the two cached
50ms assignments; it does not create a merged chart or report an oracle score.
For snares:506 matched by both,131 E-GMD-only,72 ADTOF-only,244 missed by both.
E-GMD has57 false snares versus18. Of its131 newly matched snares,69 are CoolJazz
and51 FreeJazz. This is a measured reason to investigate **snare additions while
retaining existing ADTOF hits**, rather than wholesale replacement.

For toms:34 both,17 E-GMD-only,4 ADTOF-only,26 neither. E-GMD has71 false toms
versus19;54 occur in 80sRock/CoolJazz, which have no tom references. Fifteen of
the17 new tom matches are Beatles. Do not infer general tom improvement from
that concentration. No fusion, deduplication change or threshold sweep was run.

Next, in a fresh chat: verify these results, then predeclare **one snare-only
addition rule** using saved native outputs and a fixed collision policy. Keep all
existing ADTOF events and all other families. Evaluate with the same development
gates and inspect added false hits; do not select a radius/confidence rule by
sweeping these seven tracks. Gains need independent validation and the documented
m!sa full-song acceptance checks before any default/chart replacement. Keep
uncertain KLEWS and reserved Adapt outside tuning. No broad download/retraining.

## Continuity and verification

New repo helpers: `tools/recovery/oaf_runtime.py`, `compare_oaf_drums.py`,
`test_oaf_drums.py`. Eight preflight tests passed; the full recovery suite passed
**76 tests in12.38s**, with prior parser/model/frontend integrations enabled.
The suite verifies tooling; measured song scores determine quality.

Before/after verification covers810 prior artifacts and89 protocol entries.
Final verification re-scores every saved chart at both tolerances, reconstructs
all native onset grids, validates pooled metrics/gates, and archives current
source/recovery documents with read-back hashes. Research artifacts have a final
hash manifest; dependencies/cache/temp have a separate inventory. No inference
remains running. Read `evidence/verification.json` and
`evidence/final-artifact-manifest.json` before continuing.

User corrections remain: WHITE WAVES China at1.000s and Death Before Dishonor
kick+crash at8.750s, with their coincident false HH removed. Blanket HH/CY
suppression stays rejected. Knuckles feedback means **repeated tapping** sounds
guitar-like; its35 disputed intro tom targets remain unmasked and unchanged.

The user asked whether the long chat might reduce quality. Recommended handoff:
finish this bounded experiment, then use a fresh chat with the repository state.
Compaction supports long work, but neither session length nor a fresh chat proves
accuracy. Primary-source checks, preserved artifacts and reproducible measurements
remain the safeguards. No new chat was created or messaged automatically.
