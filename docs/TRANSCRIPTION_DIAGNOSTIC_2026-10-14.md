# Expanded transcription diagnostic — 2026-10-14

## Finding

The separated-input ADTOF reference substantially outperformed the inherited
BeatSight classifier on the seven selected complete benchmark recordings. This
supports further evaluation of that approach, not immediate default replacement.
Neither system establishes accurate transcription of arbitrary songs, and training
overlap remains unknown. The reference produces only five broad instrument families.

The seven recordings total **454.93 seconds** and have **2,461 annotated hits**,
including 81 toms and 32 other-percussion hits. These are short MusicDelta benchmark
recordings, not seven long commercial songs. They were selected for instrument
coverage before the added tracks were evaluated. No inference thresholds were tuned.

All seven were freshly processed by both systems under their recorded, consistent
configurations. Same-input SHA-256 checks passed. The legacy runs used the same
weight/threshold hashes, settings, and recorded code hashes across tracks; the
reference used the same pinned revision, weights, and thresholds throughout.

## Results

One-to-one matching within the stated tolerance, scored by six instrument families:
kick, snare, hi-hat, tom, cymbal, and other percussion. The reference's unsupported
other percussion is counted as missed, rather than excluded from the denominator.

| System | Tolerance | Precision | Recall | Micro F1 | Mean per-track F1 |
|---|---:|---:|---:|---:|---:|
| Inherited BeatSight | 25 ms | 0.4317 | 0.4311 | 0.4314 | 0.4620 |
| ADTOF after separation | 25 ms | 0.8190 | 0.7005 | 0.7551 | 0.7585 |
| Inherited BeatSight | 50 ms | 0.4906 | 0.4900 | 0.4903 | 0.5235 |
| ADTOF after separation | 50 ms | 0.8409 | 0.7192 | 0.7753 | 0.7779 |

At 50 ms, the inherited system has 1,206 correct matches, 1,252 extra notes, and
1,255 missed notes. The reference has 1,770 correct matches, 335 extra notes, and
691 missed notes. Wrong-family predictions can contribute both an extra and a miss;
these counts are not a unique-event count of classification mistakes.

| Family | Reference hits | Inherited F1 | Reference F1 | Remaining reference misses |
|---|---:|---:|---:|---:|
| Kick | 652 | 0.7761 | 0.9038 | 88 |
| Snare | 953 | 0.5539 | 0.7379 | 387 |
| Hi-hat | 368 | 0.3105 | 0.7062 | 70 |
| Toms | 81 | 0.3538 | 0.5103 | 44 |
| Cymbals | 375 | 0.2272 | 0.7995 | 70 |
| Other percussion | 32 | 0.0000 | 0.0000 | 32 |

The inherited system produces **998 unmatched hi-hat notes** and misses **324/375
cymbal hits**. This is a concrete instrument-error bottleneck. The reference improves
those families but still misses 387/953 snare hits and 44/81 tom hits. It does not
distinguish closed/open hats, individual toms, ride/crash, or brush articulations.

For correctly matched events at 50 ms, median absolute timing error is **10.88 ms**
for the inherited system and **9.17 ms** for the reference; 90th percentiles are
27.96 and 17.29 ms. Signed medians are -0.61 and -6.04 ms respectively. These timing
statistics are conditional on a successful match and do not describe missing notes.
The scorer maximizes match count first, then minimizes absolute timing error. It
does not align, shift, or quantize predictions to improve the score.

## Per recording, 50 ms F1

| Recording | Inherited | Reference |
|---|---:|---:|
| MusicDelta_80sRock | 0.5238 | 0.7915 |
| MusicDelta_CoolJazz | 0.3432 | 0.5176 |
| MusicDelta_SpeedMetal | 0.7855 | 0.9497 |
| MusicDelta_Beatles | 0.5036 | 0.6620 |
| MusicDelta_FreeJazz | 0.4145 | 0.7608 |
| MusicDelta_FusionJazz | 0.4898 | 0.8736 |
| MusicDelta_Punk | 0.6039 | 0.8900 |

## Sources, limits, and reproducibility

Updated MIDI annotations come from [MDB Drums++](https://github.com/xavriley/MDBDrumsPlusPlus)
at `13aa81750e74810aec7ca17a75fe438961613d82`. Audio reuses existing local mixes
where available; two additional mixes came from [original MDB Drums](https://github.com/CarlSouthall/MDBDrums)
at `b29e2d63c3a023506f4bf353c5b2e8a558eed135`. Upstream audio/annotation terms are
CC BY-NC-SA 4.0; this is local research. Original annotations, updated annotations,
audio, converted family labels, and source hashes are kept separately.

The updated annotations have not been independently audited note by note here.
Their changes, including some onset timing, affect scores. Therefore these numbers
must not be directly compared as model improvement against the earlier three-song
scores that used original annotations. Both systems here use the same updated
annotations. Ground-truth MIDI tempo changes are respected; no label timing shift
was introduced. Unmapped pitches in other MDB Drums++ tracks remain a preflight
issue; the seven selected tracks use an explicit, recorded family mapping.

The ADTOF PyTorch reference source is pinned to
`85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9` and its weight SHA-256 to
`1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320`.
These results include source separation from the full mix. They do not establish
the benefit of separation on these seven tracks, because a paired full-mix-only
reference arm was not run on this expanded set.

Later continuations supersede the missing-full-mix statement above: the WHITE
WAVES report records the completed seven-track raw full-mix and stereo-separated
comparisons. `MDB_RESIDUAL_INPUT_AND_DECODER_AUDIT_2026-10-15.md` adds a rejected
fixed residual-input candidate, target-level failure buckets and a primary
decoder conformance audit. Historical numbers below remain unchanged.

## Targeted input probe: brushes and ghost notes

The original MDB annotations mark 286 CoolJazz snare events as brush strokes and
206 FreeJazz snare events as ghost notes; the [original paper's taxonomy](https://musicinformatics.gatech.edu/wp-content_nondefault/uploads/2017/10/Wu-et-al_2017_MDB-Drums-An-Annotated-Subset-of-MedleyDB-for-Automatic-Drum-Transcription.pdf)
defines those categories. This identifies meaningful technique coverage rather
than treating the entire failure as generic jazz difficulty.

A follow-up kept the reference model and updated labels fixed, and compared
full-mix input with its separated input and the original isolated drum recording.
Two small original drum stems and subclass files were retrieved from the pinned
MDB source and Git-blob-verified. The original isolated stem is an **oracle input**
for diagnosis, not an achievable full-song transcription result.

| Recording | Full mix F1 | Separated mix F1 | Original isolated drums F1 |
|---|---:|---:|---:|
| CoolJazz | 0.3009 | 0.5176 | 0.7273 |
| FreeJazz | 0.6418 | 0.7608 | 0.8458 |

All scores use 50 ms family matching. CoolJazz snare matches rise from 113 with
separation to 175 with original drums, but 126/301 snare hits remain missed even
with that oracle input. FreeJazz still misses 104/353 snare hits with original
drums. The input representation/separation and the transcription model both need
attention; merely replacing the separator cannot be assumed to solve everything.
Input balance and recording differences also matter, so this is not a controlled
comparison of two separation algorithms. No thresholds were tuned on these examples.

Evidence: `diagnostic-mdb-brush-probe/sources.json` and
`diagnostic-mdb-brush-probe/inference/input-comparison.json`, with input and
prediction hashes, logs, reference weights, and unchanged thresholds.

Private artifacts under `C:\Users\10ros\BeatSight-Recovery\2026-10-13`:

- `diagnostic-mdb-plus-seven-inputs/sources.json`: exact input provenance and mapping.
- `diagnostic-mdb-plus-new-four-legacy` and `diagnostic-mdb-plus-old-three-legacy`:
  full legacy logs, native chart outputs, audio, settings, and weight/code hashes.
- Corresponding `*-adtof-separated` folders: reference logs, predicted events,
  MIDI files, and derived drum stems. These are research outputs, not a new native
  app integration or an automatic default replacement.
- `diagnostic-mdb-plus-seven-comparison.json`: per-track, per-family, 25/50 ms scores,
  individual timing errors, prediction hashes, and configurations.

`tools/recovery/compare_diagnostics.py` reproduces the score from saved predictions
and rejects changed inputs/configurations. Six targeted timing-scorer tests passed,
covering duplicate events, nearest matching, cardinality priority, wrong instruments,
tolerance boundaries, empty predictions, and invalid times.

## Next action

Use the measured brush/ghost-note and tom failures to choose a bounded separation
or transcription experiment, and establish an excluded longer-song test set. Then decide whether
an optional reference-backed chart path is useful and how to represent its broad
labels honestly in the practice view. Preserve uncertainty and editing support.
Do not spend effort rebuilding the entire old clip collection to reproduce a model
whose instrument mistakes are already measured. No training or default model
change was made in this experiment.
