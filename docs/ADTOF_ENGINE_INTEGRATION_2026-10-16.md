# ADTOF engine integration — 2026-10-16

The app's chart generation now uses the measured-better engine by default:
stereo htdemucs_ft drum separation plus the ADTOF Frame_RNN model. The inherited
pipeline is kept as a selectable fallback. Through the same command line the
desktop app launches, the new default scores .20 to .29 F1 higher than the old one
on every fixed benchmark. It is also faster. This is benchmark agreement on five
broad families, not verified accuracy on any arbitrary song.

Evidence root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-adtof-engine-integration-01`
(`protocol.json` frozen before runs, amendments 01–02, `evidence/end-to-end-metrics.json`,
`evidence/parity.json`, test logs, sandbox build, all run outputs).

## What changed

- `ai-pipeline/adtof_engine/`: BeatSight's own implementation of the published
  Frame_RNN (frontend, network, peak picking) plus an engine that writes a `.bsm`.
  Its activations are **bitwise identical** (max difference 0.0) to the audited
  2026-10-15 model outputs on all seven fixture recordings, with identical decoded
  events (2,158). Separation is seeded with 0 as in the audited runs, so the same audio
  always gives the same chart.
- `pipeline/process.py`: `--engine adtof|legacy` (default `adtof`) and `--adtof-weights`.
  Note times are never quantized; a forced tempo/offset from the desktop only sets grid
  metadata. With no detected hits the engine fails instead of inventing notes.
- Desktop: `AiGenerationOptions.Engine` (default ADTOF) is sent as `--engine`; mapping and
  editor generation read the new **Use legacy transcription engine (fallback)** checkbox
  shown in AI settings without developer mode (`UseLegacyTranscriptionEngine`, default
  off). A passthrough desktop preview separation no longer switches off the engine's
  own separation. The Python process now gets `PYTHONIOENCODING=utf-8` and UTF-8 decoding.
- Weights: `ai-pipeline/models/adtof/` (git-ignored) with a NOTICE; SHA-256 checked at load.

## Pre-existing bug found and fixed

Every legacy run first failed with `UnicodeEncodeError`. The inherited pipeline prints an
emoji when a file has no metadata tags. With redirected stdout, Windows Python uses
cp1252 and crashes. The desktop launcher set no UTF-8 option, and none is set in the
user's environment, so the old engine would also have failed in the app on untagged files.

## End-to-end results (app-shaped CLI, 50 ms, pooled)

Arguments match the desktop mapping defaults (`--confidence 0.3 --mode gameplay
--sensitivity 60 --quantization sixteenth --max-snap-error 12 --ml --multilabel`), with
no forced tempo from the desktop's C# analysis. RTX 3080 Ti for separation.

| Benchmark | ADTOF P / R / F1 | Legacy P / R / F1 | ADTOF time | Legacy time |
|---|---|---|---:|---:|
| 7 MDB recordings | .843 / .740 / **.788049** | .609 / .440 / .510970 | 116 s | 175 s |
| 6 ENST mixtures | .837 / .767 / **.800204** | .711 / .516 / .598113 | 102 s | 152 s |
| 2 reserved Clone Hero charts | .895 / .841 / **.867158** | .653 / .515 / .575854 | 80 s | 140 s |

MDB and ENST reproduce the audited same-configuration baselines exactly. The first,
unseeded batch scored .784356 / .797684 / .866892; integer-millisecond note times change
nothing (audited predictions score identically when rounded). The reserved songs
(.867) were never used for tuning; the older pinned-port configuration scored .856.

Per family, ADTOF at 50 ms (F1): kick .92/.88/.98, snare .75/.77/.98, hi-hat
.71/.82/.77, cymbal .81/.71/.76, tom .55/.46/.59 (MDB/ENST/Clone Hero). Snare misses
concentrate in jazz and brushes; toms and hi-hat/cymbal confusion remain the weak spots.
Legacy cymbal F1 is only .33/.16/.10.

## Verification

- 12 new engine tests (contract, schema, unquantized times, forced offset as metadata,
  time window, wrong-weights refusal, pooling, CLI routing, real-fixture bitwise parity).
- ai-pipeline suite: 302 existing pass. 4 existing failures (3 training-dataset builder,
  1 legacy onset test) fail identically with the original `process.py`; unrelated.
- Desktop suite in a sandbox byte-identical to the checkout (1,618 files): **539/539**
  (3 new tests, 2 extended). The 10-line separation hand-off in `GenerationPipeline`
  has no test harness; it is covered by review only.

## Limits and decisions for the user

- **License.** ADTOF weights are CC BY-NC-SA 4.0 (non-commercial, share-alike). The user
  has since decided BeatSight is personal/study use only, so this is not a constraint; the
  weights must still never be pushed publicly or published.
- **Five broad families only.** Charts show `hihat_closed`, `tom_mid` and `crash` for any
  hi-hat, tom and cymbal. China, open hi-hat and individual toms need a new model.
- **Python environment.** The app runs plain `python`; on this PC that resolves first to
  `C:\github\edisim\.venv`, which only works because it shares Python 3.11's packages.
  Setting BeatSight's Python path to `C:\Users\10ros\AppData\Local\Programs\Python\Python311\python.exe`
  would remove that dependency (not changed without the user's say-so).
- The desktop's own htdemucs preview separation still runs for the playback stem, so
  separation happens twice. The hosted backend worker still uses the legacy path.
- Not covered: the full UI flow, C# tempo forcing on real songs (unit-tested only), the
  user's two m!sa songs end to end, musical acceptance. Training overlap is unknown.

Next (transcription first): broaden the frozen evaluation set, then the finer-class
training route in `TRANSCRIPTION_ROUTE_2026-10-16.md`.
