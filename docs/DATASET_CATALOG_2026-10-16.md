# Drum transcription data and model catalog — 2026-10-16

Everything relevant that exists, judged for BeatSight's goal: the best possible any-song drum
transcription. Licenses are not a filter (personal/study use only, user decision 2026-10-16), but
quality, realism, label accuracy and overlap with the frozen evaluation set are. "Use" means it
should improve the model; "skip" means it would add noise, cost or leakage.

## What the research says

- In full mixes the main limit is interference from other instruments. After that, unfamiliar kit
  sounds, weak notes and simultaneous hits each cost about 5%. Kit diversity and augmentation
  (pitch shift, compression, reverb) help ([Weyers et al., ISMIR 2025](https://www.audiolabs-erlangen.de/content/05_fau/professor/00_mueller/03_publications/2025_WeyersUML_LimitationsADT_ISMIR_ePrint.pdf)).
- STAR alone trains a model on par with ADTOF's own data at 5 classes (MDB .79 vs .78–.79, ENST .77
  vs .75–.76). It is the best of the tested sets at 8 and 18 classes. TMIDT and Slakh are clearly
  weaker. Combining ADTOF's two subsets did not help; adding STAR's original mixes helped slightly
  ([STAR paper, TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.244)).
- A 2026 preprint claims state-of-the-art results from realistic synthetic data
  ([arXiv 2601.09520](https://arxiv.org/abs/2601.09520)). Its released code is ADT_STR, which this
  project measured on October 15: .664 vs ADTOF .788 on our MDB benchmark. Published claims must be
  re-measured locally.

## Already local

| Source | Judgment | Why |
|---|---|---|
| STAR train (99.8 h) | **Use, high weight** | Best fine-class training data; real accompaniment |
| STAR validation (MUSDB-based) | **Use** after rebuilding 97 mixes with STAR's script | Validation for real-accompaniment data |
| E-GMD + Groove (403 h) | **Use, down-weighted** | Huge, exact labels, 43 kits, but drums only and no China/splash |
| Slakh2100-redux (107 h) | **Use, low weight**; drop sequence-key tracks | Weaker per STAR paper; 231 k approximate labels |
| ADTOF weights | **Use** as the starting point | Strongest real-music model available |
| ENST, MDB (7 local), reserved charts | **Evaluation only** | Frozen eval set; training on them would fake results |
| MUSDB18-HQ, Cambridge, Telefunken, Signature Sounds, MedleyDB | **Use as unlabelled audio** for teacher (ADTOF) distillation; never the 31 excluded MUSDB songs | Real recordings keep the model honest on real songs |
| IDMT-SMT-Drums v2 | Skip for now | 3 classes, known annotation discrepancies |
| Lakh MIDI (salvaged subset) | Skip | Only useful for synthetic rendering, which STAR already does better |

## Not local yet

| Source | Size / access | Judgment |
|---|---|---|
| **Rhythm-game chart corpus** (Chorus Encore index, ~95,000 community charts; RhythmVerse) | 10–50 MB per chart with audio; download tools exist ([Bridge](https://github.com/Geomitron/Bridge), [Rainbow](https://github.com/renzora/rainbow), [Chorus API](https://github.com/Paturages/chorus)) | **Highest value.** Real commercial recordings with hand-made drum charts: exactly how ADTOF got its 359 h, and the main way to beat it. Needs chart-to-audio alignment cleaning (ADTOF's grooming method), pro-drums/expert filtering, and exclusion of all eval songs by title. Start with a pilot. |
| **ADTOF dataset** (359 h, [on request via Zenodo](https://github.com/MZehren/ADTOF)) | Spectrograms, 5 classes; needs the user's Zenodo request | **High value** for keeping real-music skill during fine-tuning; family labels only |
| MDB Drums, all 23 tracks ([GitHub](https://github.com/CarlSouthall/MDBDrums)) | Small; direct download | **Use for evaluation v2 only.** Its songs overlap the STAR test split and MUSDB |
| RBMA13 ([annotations](http://ifs.tuwien.ac.at/~vogl/datasets/); audio from a Bandcamp album) | 1.7 h electronic music; audio needs the user | **Evaluation v2** (adds electronic genres) |
| MoisesDB ([GitHub](https://github.com/moises-ai/moises-db)) | 240 real multitracks with drum stems, ~149 GB, manual download from the research site | **Medium.** Real drum stems for distillation and kit diversity; user must fetch it |
| StemGMD ([Zenodo](https://zenodo.org/records/7860223)) | 1.13 TB, 10 acoustic kits rendered from Groove performances | **Low.** Too large for C:, and E-GMD already covers these performances with 43 kits |
| TMIDT (Vogl et al., 257 h synthetic) | Availability unclear | **Skip.** STAR beats it at every class granularity |

## Pretrained models

| Model | Judgment |
|---|---|
| ADTOF Frame_RNN (current engine) | Base for fine-tuning; family-level teacher |
| ADT_STR (2026 "realistic synthetic") | Tested locally 2026-10-15: worse (.664 vs .788). Skip |
| YourMT3+ ([arXiv 2407.04822](https://arxiv.org/pdf/2407.04822)) | Multi-instrument; drum scores unclear. Worth one local benchmark later as a possible second teacher |
| MuScriptor ([arXiv 2607.08168](https://arxiv.org/pdf/2607.08168)) | Drums F1 49.6 on its own benchmark. Skip |
| Separate-and-Detect ([arXiv 2608.01093](https://arxiv.org/pdf/2608.01093)) | Deferred after the October 16 feasibility audit (no proven gain, large) |
| DrumSep (MDX23C) | Tested October 16: unreliable on hi-hats. Skip as a labeller |

## Recommended order

1. Build the stem/feature cache for the local manifest and fine-tune ADTOF to 16 classes
   (no downloads needed).
2. Chart-corpus pilot, about 500 drum charts (roughly 5–25 GB): download, align, clean, and measure
   label quality against audio before scaling up. Needs the user's go-ahead.
3. With the user's help: request the ADTOF dataset; fetch MoisesDB; buy or download RBMA13 audio.
4. Evaluation v2: all 23 MDB tracks plus RBMA13, frozen before any model sees it.
