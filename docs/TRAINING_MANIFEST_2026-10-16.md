# Finer-class training manifest v1 — 2026-10-16

Every local labelled item that may be used to train or validate BeatSight's 16-class
drum model, with labels, durations, grouping keys and a guard that proves nothing from the
frozen evaluation set can enter training. No audio was separated or trained.

Root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-train-manifest-01` (`protocol.json` frozen
first; `build_manifest.py`; `manifest.jsonl.gz`, one item per line; `labels/<source>.jsonl.gz`,
one row per unique label set, events `[time_s, fine_index, velocity]`; `summary.json`;
`estimate.json`; `tests/`; `evidence/`). 37 MB.

## Contents (usable)

| Source | Split | Items | Hours | Events | Input |
|---|---|---:|---:|---:|---|
| E-GMD | train / val | 35,217 / 5,031 | 341.4 / 52.2 | 11.1 M / 1.70 M | Drums only, 43 kits |
| Groove (original kit) | train / val | 846 / 120 | 8.4 / 1.2 | 0.27 M / 0.04 M | Drums only |
| STAR | train / val | 6,035 / 22 | 99.8 / 1.5 | 2.54 M / 0.03 M | Full mix |
| Slakh2100-redux | train / val | 1,289 / 270 | 88.9 / 18.4 | 2.44 M / 0.50 M | Full mix |
| **Total** | | **48,830** | **611.8** | **18.6 M** | |

Events per fine class (all usable): kick 3.89 M, snare 4.56 M, side-stick 0.45 M, closed/pedal/open
hi-hat 3.42/1.64/0.72 M, high/mid/low tom 0.49/0.34/0.52 M, ride 1.50 M, ride bell 0.28 M, crash
0.39 M, China 14.6 k, splash 13.1 k, cowbell 11.5 k, other 0.37 M. China and splash come almost
entirely from Slakh (about 14 k and 12 k); STAR adds 255 and 780 and E-GMD none, so they will stay
the weakest classes.

97 STAR validation items are listed but unusable: their mixes are MUSDB-derived and must be built
locally with STAR's mixing script (none of them are among the 31 excluded MUSDB songs).

## Guarantees (tested: 21 tests pass)

- Labels use the frozen evaluation set's taxonomy and ADTOF's mapping tables (imported, not copied).
- The exclusion guard rejects ENST (all three drummers are excluded groups in the frozen file),
  E-GMD/Groove test performances (129 ids), the 40 eval performances, the STAR test split, the 31
  STAR-test/MDB songs in MUSDB, the MDB eval tracks and the reserved chart songs. One injected
  violation per rule is caught; the built manifest passes; 8,679 groups, none in both splits.
- Correction to the earlier plan: ENST drummers 2–3 are **not** usable for training. The frozen
  `exclusions.json` names the whole drummers, and training on the same kits and room would inflate
  tier B.

## Data-quality flags for the training step

- Slakh: 231,461 events come from "sequence" keys (one key plays a pattern), so their labels are
  approximate; 86,678 notes on keys without a known sound were dropped. Slakh trains weaker models
  than STAR (STAR paper, Table 5). Down-weight Slakh and mask or drop sequence-key tracks.
- E-GMD is 56% of all hours and drums only. Sample a few kits per performance per epoch so it does
  not swamp the full-mix data.
- E-GMD label variants: 3,443 unique label sets for its 936 train/validation performances
  (velocities differ by kit render).

## Cache cost (measured, `estimate.json`)

htdemucs_ft separation runs at about 11x real time on the RTX 3080 Ti (60 s STAR, 7.7 min Slakh,
2.2 min E-GMD samples). Separating the 208.6 h of mixtures takes about 18.6 GPU-hours; also
separating the 403 h of drum-only audio about 54.7 h. Storage: float16 features for everything
37 GB; 16-bit FLAC stems for mixtures 31 GB (90 GB for everything). C: had 404 GB free.

Next: the stem and feature cache (resumable, hash-recorded), then ADTOF fine-tuning to 16 classes.
See `DATASET_CATALOG_2026-10-16.md` for sources beyond this manifest.
