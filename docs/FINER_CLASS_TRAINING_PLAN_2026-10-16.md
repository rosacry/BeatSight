# Finer-class drum model: training data plan — 2026-10-16

Goal: a model that writes the instrument detail the practice views need: kick, snare,
side-stick, closed/pedal/open hi-hat, high/mid/low tom, ride, ride bell, crash, China,
splash and cowbell. It must match or beat the current ADTOF engine at family level on the
frozen evaluation set. Nothing has been trained or downloaded yet.

**User decision (2026-10-16):** BeatSight is for personal use and study only and will never
be released. Non-commercial and non-redistributable licenses are therefore not a constraint:
every local source and the ADTOF weights may be used, including fine-tuning. Such weights,
data and derived audio must still never be pushed to a public remote or published.

## Evaluation contract (fixed before any training)

- Frozen set: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-eval-set-v1`
  (`EVAL_SET_V1_2026-10-16.md`). Never train, validate, tune or pseudo-label on anything in
  `exclusions.json` (all ENST drummer 1, all 64 ENST minus-one tracks, the 7 local MDB mixes,
  the 2 reserved chart songs, the STAR test split, the E-GMD test split, every kit rendering
  of those performances) or `exclusions-derived-musdb.json`. That file lists 31 MUSDB18-HQ
  folders on D:: every STAR test song is a MUSDB song, and MUSDB also holds MDB's 80s Rock,
  Beatles and Punk. The training manifest builder must fail on any match.
- Gates for a candidate: five-family F1 not below ADTOF on tier A (held-out real .643), tier
  D (STAR .721) and tier E (E-GMD .730), with no drop on tier B (.829) or C (.867) beyond .01.
  Fine-class recall is reported for every class with at least 100 reference events. China (43)
  and splash (59) get counts only. Full-song m!sa checks still come before promotion.

Current ADTOF share of each fine class caught by the right family (all tiers): pedal hi-hat
.16, splash .14, high/mid tom .40/.36, crash .54, snare .60, open hi-hat .66, ride .67; it
never outputs side-stick or cowbell and cannot tell sub-classes apart at all.

## Training sources (all local)

| Source | Size | Labels | Realism | Grouping rule |
|---|---|---|---|---|
| STAR Drums train/validation | 6,035 items (1,228 ISMIR04 + 4,807 Jamendo) / 119 | 18 classes | Synthetic drums over real accompaniment | Source song across kits |
| E-GMD train/validation | 35,217 / 5,031 renders, 43 kits | TD-17 map; no China/splash | Electronic kit, drums only | Performance id |
| Groove MIDI | 2,240 files | Same performances as E-GMD | Electronic kit | Merge with E-GMD ids |
| Slakh2100-redux train/validation | 1,289 tracks / validation split | Drum MIDI, per-kit map in ADTOF's `SLAKH2100_MIDI` table | Fully synthetic | Track |
| ~~ENST drummers 2–3, non-minus-one~~ | — | — | — | **Not usable:** the frozen `exclusions.json` names all three ENST drummers (corrected 2026-10-16, see `TRAINING_MANIFEST_2026-10-16.md`) |
| Cambridge, MUSDB18-HQ (minus 31 excluded), MedleyDB, Signature Sounds, Telefunken | Many real multitracks | None | Real | Teacher pseudo-labels only |

STAR labels come from an automatic transcriber before re-synthesis. They describe the
rendered drums exactly, but not necessarily what the original drummer played. The largest
real-music labelled source would be the ADTOF dataset itself (359 hours of chart-aligned real
music, available on Zenodo **on request**), which needs the user to file the request.

Input must match inference: the app feeds htdemucs_ft-separated mono drum stems into the
model. Training should use stems separated the same way (GPU, about 8x real time), cached
on C: (379 GB free), not the clean rendered stems, or measure the difference explicitly.

## Approaches, in recommended order

1. **Fine-tune ADTOF to 16 classes.** Start the CNN and GRU from the audited weights; replace
   the five-way output with 16 outputs whose initial rows copy the matching family row (for
   example closed, pedal and open hi-hat all start from the hi-hat row). Train on the labelled
   sources. To keep its real-music skill, add a family-level distillation loss: the frozen
   original ADTOF's outputs on separated stems of unlabelled real multitracks are the
   targets. Fastest route to a model that keeps ADTOF's strengths and adds detail.
2. **Sub-class classifier on ADTOF onsets.** Keep ADTOF for timing and family; classify each
   hi-hat, tom or cymbal onset into its sub-class from a short window of the stem. Small and
   quick, useful as a comparison and a fallback if fine-tuning loses family accuracy.
3. **Larger or from-scratch model** only if 1–2 plateau below the gates.

## Bounded next sessions

Status: session 1 is done (`TRAINING_MANIFEST_2026-10-16.md`: 48,830 usable items, 611.8 h,
exclusion guard tested). Source judgments and outside data are in `DATASET_CATALOG_2026-10-16.md`;
the biggest untapped source is a rhythm-game chart corpus (real songs), starting with a pilot.

1. Training manifest: enumerate items per source with durations, fine-class counts and
   groups; implement the Slakh per-kit mapping; fail on any exclusion match.
2. Stem and feature cache: htdemucs_ft stems plus ADTOF frontend features for the manifest,
   with a storage estimate first; resumable and hash-recorded.
3. Fine-tuning pipeline with unit tests and a tiny overfit check, then the first GPU run
   (hours), scored on the frozen set against the gates.
4. Iterate from the measured gaps; try approach 2 for comparison.

GPU: the user granted full use of the RTX 3080 Ti and paused their other training job. Runs
must stay resumable and checkpointed so the user can reclaim the GPU at any time.

## User actions that would help (optional)

- Request the ADTOF dataset on Zenodo (needs the user's account; assistants cannot do it).
- Allow downloading the 16 MDB full mixes not on disk; they would form evaluation set v2,
  not change v1.
