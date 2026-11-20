# 16-class model support in the ADTOF engine (2026-10-18, Claude)

Experimental and off by default. The app's default engine is still ADTOF (5 broad families).

## What changed

- `ai-pipeline/adtof_engine/fine.py` (new): `FineFrameRnn` (Frame_RNN with a 16-way output, same
  layer names as `2026-10-16-finetune-01/ftlib.py`), `load_fine_model(dir)` (`best.pt` +
  `thresholds.json`, strict load, threshold checks, SHA-256 of both files) and `decode_fine`
  (the ADTOF peak picker with per-class thresholds).
- `adtof_engine/engine.py`: `transcribe(..., fine_model_dir=None)`. With a directory, the same
  audio loading, seeded htdemucs_ft separation and frontend feed the 16-class model; the chart is
  tagged `beatsight-16class` / `experimental` and the summary records the model files' hashes.
  Without it, output is unchanged.
- `pipeline/process.py`: `--fine-model DIR` (only with `--engine adtof`; with `legacy` it exits 2).
- `shared/schemas/beatmap_schema.json`: component enum gains `cross_stick` and `percussion`, which
  the desktop editor already uses (`EditorScreen.cs` quick components, `DrawableNote` colours).

Class to component: KD kick, SD snare, SS cross_stick, HHC hihat_closed, HHP hihat_pedal,
HHO hihat_open, HT tom_high, MT tom_mid, LT tom_low, RD ride, RB ride_bell, CR crash, CH china,
SP splash, CB cowbell, OT percussion.

## Verification

- `ai-pipeline/tests/test_adtof_fine.py`: 6 tests (schema IDs, per-class thresholds, bad-file
  refusal, loading a checkpoint written by the training code, schema-valid 16-class chart,
  CLI routing and legacy refusal). With the 12 ADTOF engine tests: 18/18.
- Full ai-pipeline suite: 308 pass; the same 4 pre-existing failures as before (3 training
  dataset builder, 1 legacy onset). `test_process_audio_creates_parent_directories` fails only
  when CUDA is hidden (legacy classifier checkpoint saved on CUDA); passes with CUDA visible.
- No desktop change yet. Desktop wiring (a setting that passes `--fine-model`) waits for a model
  that passes the promotion gates (eval set v1, chart test tier, m!sa full songs, user listening).

## Use (manual, for testing a candidate)

```bash
.venv-recovery/Scripts/python.exe ai-pipeline/pipeline/process.py --input song.wav --output song.bsm --fine-model C:/Users/10ros/BeatSight-Recovery/2026-10-16-finetune-01/runs/phase1-01
```

## Update 2026-10-23: hi-hat combine rule (Claude, user approved)

`decode_fine` now merges closed/pedal/open hi-hat peaks within 20 ms of the retained left peak into one
event with the strongest class (`fine.combine_hihats`, `HH_COMBINE_SECONDS`; pass
`hh_combine_seconds=None` for plain per-class decoding). Engine version `beatsight-16class-2`; the summary
records `hh_combine_seconds`. Evidence and validation: `docs/TIERB_DROP_DIAGNOSIS_2026-10-23.md`.
`test_adtof_fine.py` + `test_adtof_engine.py`: 21/21 (new: merge, left retention, other families
untouched, equality with the research rule on random activations). The ADTOF default is unchanged.

## Update 2026-10-24: ride / ride-bell / crash combine rule (Claude, user approved)

After the hi-hat rule, `decode_fine` merges ride, ride-bell and crash peaks within 20 ms of the retained left
peak into one event with the strongest class (`fine.combine_cymbals`, `CYMBAL_COMBINE_CLASSES`,
`CYMBAL_COMBINE_SECONDS`; `cymbal_combine_seconds=None` turns it off). China and splash are not merged.
`combine_hihats` and `combine_cymbals` share `combine_classes`. Engine version `beatsight-16class-3`; the summary
records `cymbal_combine_seconds` and `cymbal_combine_classes`. Evidence: `docs/CYMBAL_GHOST_RULES_2026-10-24.md`.
Tests 23/23. The ADTOF default is unchanged.

## Update 2026-11-06: no "percussion" notes (Claude, user decision)

`decode_fine` now leaves the OT class ("percussion") out of charts (`DROPPED_CLASSES = ("OT",)`;
`drop_classes=()` keeps it). Rhythm-game charts have no lane for it, and on eval tier B the first 16-class model's
OT output gave 2,621 false hits vs 32 true. Engine version `beatsight-16class-4`; the summary records
`dropped_classes`. The model's outputs are unchanged. 24/24 `test_adtof_fine.py` + `test_adtof_engine.py` pass.
