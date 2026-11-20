# Evaluation gate after data recovery

## Decision this evaluation must support

Choose a transcription approach that produces useful, faithful full-song drum
charts in the existing practice views. Data volume, classifier accuracy with known
onsets, and a successfully loaded chart do not answer this question. Do not start
a large rebuild or training run just because the raw collection is available again.

## Evidence that changes the plan

- Raw inputs referenced by ten provenance inventories survive on D:. The old F:
  derived collection is still incomplete, but it is no longer necessary to start
  by redownloading the source corpus.
- In 50,209 recovered E-GMD clips, 163 source recordings use 18 different MIDI
  hashes. Five performance hashes occur in both training and validation indices.
  All 163 current MIDI hashes match the original records. Old validation scores
  therefore cannot establish unseen-performance accuracy.
- Across the full original provenance, E-GMD's 45,537 MIDI paths have 4,552 distinct
  byte hashes, GMD's 1,150 have 1,149, and Slakh's 1,708 have 1,653. These counts
  are from recorded hashes, not a fresh full rehash. Distinct hashes can still encode
  the same performance. Never equate file count with independent musical examples.
- The inherited builder's session hashing uses render-specific identifiers. Its
  newer stratified assigner allocates individual components and does not enforce
  performance grouping; Python's process-dependent `hash(label)` also enters its
  random seed. Do not use either mode to establish a clean test split. This is a
  code inspection, not an assertion that every historical run used that revision.
- Existing three-song diagnostics favor ADTOF with separated drums over the
  recovered classifier, but overlap is unknown and the sample has no tom targets.
  Neither model is established as suitable for detailed drum teaching.

## Required data separation

Create new manifests in a scoped C: experiment directory. Preserve all old indices.
Each example should record original source, rights evidence reference, full-song
audio hash, annotation hash/version, performer/song/performance identity, render
kit, original split, and whether it was used for development or final evaluation.

Group all renders of a performance together, including corresponding GMD/E-GMD
performances. Group Slakh derivatives by source MIDI and real music by song/artist
where feasible. Recognize overlapping MedleyDB/MUSDB/STAR items. Hash equality
proves overlap; different hashes or filenames do not prove independence.

Use three explicit evaluation roles:

| Role | Purpose | Permitted conclusion |
|---|---|---|
| Existing diagnostic songs | Reproduce failures and compare changes | Relative diagnostic behavior only |
| Recovered development examples | Find errors across families, dynamics, mixes, kits | Guide design; do not report as final generalization |
| Independently checked, excluded full songs | Final quality gate after choices are frozen | Held-out performance within that set's coverage |

If a reference model's training membership cannot be established, mark its overlap
unknown even when BeatSight's own exclusion is known. Do not silently promote a
public benchmark used for development into the final test set.

## Next bounded experiment

1. Build a small source-grouped development manifest spanning acoustic and electronic
   drums, tom fills, ride versus crash, open/closed/pedal hats, ghost notes, and
   dense mixes. Preserve original full-length timing. Include verified no-drum
   passages to measure invented notes. Do not label an entire STAR original mix
   drum-free merely because its resynthesized MIDI is empty.
2. Inspect timing and instrument labels in each chosen example. Recovered STAR
   labels describe its synthetic drum part; use them to test controlled mixtures,
   not to claim manual ground truth for the original performance. Check Slakh kit
   mappings before interpreting note numbers. Real stems alone are not note labels.
3. Freeze the candidate list and inference settings. Compare the recovered model
   with the separated-input reference on exactly the same full-song inputs. Keep
   instrument-family scoring common between systems, and separately measure the
   detailed articulations that only some systems emit. Missing articulation output
   remains a limitation, not evidence of correct articulation.
4. Identify the largest measured error source: missed/extra onsets, separation loss,
   instrument confusion, articulation confusion, or chart timing/export. Change one
   cause at a time. Introduce new training data only for a demonstrated deficiency.

## Report for each run

- Hashes of source audio, annotations, weights, settings, and code revision;
  output chart, inference logs, duration, runtime, failures, and unsupported classes.
- One-to-one full-song event precision, recall, and F1 at 25 and 50 ms, with per-song
  and per-family counts. Score actual exported notes, never supply true onsets to
  the model during an end-to-end test.
- Absolute and signed timing errors on matched notes, with median and 90th
  percentile, and clear matching policy. A tolerant F1 alone can hide drift.
- Missed hits, invented hits, wrong instruments, simultaneous-hit handling, and
  rare-technique coverage. Do not infer velocity accuracy from correct note names.
- Auditable listening/viewing examples selected by the measured failure categories;
  confirm chart/audio synchronization in the native practice view.
- Training-overlap status and limits of each benchmark. Keep accuracy claims tied
  to the measured population; no promise of accurate transcription of every song.

## Promotion rule

Do not replace the default model based on one aggregate metric or these old three
songs. Require reproducible full-song improvement, no unexplained family regressions,
preserved native chart compatibility, and a documented overlap audit. Establish
numerical acceptance thresholds on development evidence before running the final
held-out gate. Until then, generated charts remain editable, unreviewed drafts.
