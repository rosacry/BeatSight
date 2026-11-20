# Curated chart-reference benchmark — 2026-10-14

**Latest continuation:** `CLONE_HERO_SOURCE_CONTROLS_2026-10-15.md` records strong
original-drum timing support for Adapt and one fixed original-drum ADTOF input
diagnostic. This does not change the original 15-run scores below or promote a
model. The user clarified Knuckles' guitar-like opening as the repeated tapping;
35 yellow-tom targets are disputed, with original notes/scores preserved.

**October 15 continuation:** see `CLONE_HERO_REFERENCE_AUDIT_2026-10-15.md` for
independent decoder/clock checks and the user's Knuckles opening guitar-hit
observation. No offset correction was accepted; the scores below are unchanged.
The new short reference review is on port 8775. Keep KLEWS out of model selection
until its timing and disputed instrument labels are resolved.

This continuation began the accepted Clone Hero/Phase Shift chart comparison in
`C:\Users\10ros\BeatSight-Recovery\2026-10-14-clone-hero-benchmark-01`.
Five complete song packages were acquired from their charters' public download
pages, preserved, hashed and parsed. **This is provisional chart agreement, not
audio-audited transcription accuracy or an independent generalization test.**

## Corpus and frozen split

| Role | Artist — song | Author | Selected reference | Decoded length | Raw Pro Drums notes | 2x kicks |
|---|---|---|---|---:|---:|---:|
| Development | New Found Glory — Failure's Not Flattering | KLEWS | notes.chart | 233.570 s | 1,560 | 0 |
| Development | Cartel — Say Anything (Else) | KLEWS | notes.chart | 229.599 s | 1,266 | 0 |
| Development | Moose Blood — Knuckles | KLEWS | notes.chart | 222.935 s | 1,580 | 0 |
| Reserved | Castillerian — Adapt | Castillerian | notes.mid | 283.648 s | 1,867 | 30 |
| Reserved | Utsu-P — DIARRHEA | Castillerian | notes.mid | 282.400 s | 1,657 | 37 |

Total: 1,252.151 seconds (20.87 minutes), 7,930 raw lane notes. All five have Expert
drum parts; Pro Drums cymbal/tom information is present in the **selected** files.
No independent listening audit has established complete coverage of ghost notes,
rolls, pedal hats, cymbal identities, or other omitted musical events.

The development songs come from [KLEWS's own chart page](https://www.klewshero.com/klews-hero-charts).
The author describes hand charting and drum-kit testing; this is an attribution,
not our accuracy certification. The two reserved packages come from
[Castillerian's own page](https://castillerian.neocities.org/charts), which identifies
the charting workflow and dated versions (Adapt: January 28, 2018 update;
DIARRHEA: February 11, 2018). KLEWS did not expose a semantic release/version in
the downloaded package; exact archive/member SHA-256 is the version identity.
Package metadata is retained verbatim, including apparent date/year differences.

`acquisition.json` contains public source pages, retrieval timestamps, archive
hashes and all member hashes. Source HTML and download evidence remain outside Git.
Public availability establishes access; no custom training, redistribution or
commercial rights agreement was established. The official YARG song set was
excluded because its [terms restrict use to YARG](https://github.com/YARC-Official/Official-Setlist-Public).
No account creation, outgoing message, upload or purchase occurred.

`selection.json` froze song membership, splits, candidates and tolerances before
inference. `selection-v2.json`, also created before inference, changes **only**
DIARRHEA's selected format: the bundled `.chart` loses every cymbal marker and 2x
kick, while the original MIDI retains them. The original files and initial
`prepared/` interpretation remain preserved. Use **`prepared-v2/`** for evaluation.
This format discrepancy is not a second independent song or a model mistake.

## Importer and measured parser defect

Reused [YARG.Core](https://github.com/YARC-Official/YARG.Core) revision
`4b8865781a403a811f42929721436226c77470c6`, with LGPL-3.0-or-later license and
bundled Moonscraper BSD-3-Clause code. The initial upstream ChartDump helper
omits seconds/2x-kick details and defaults to standard four-lane drums without
an ini hint. A thin separate `tools/recovery/ChartReference` adapter instead uses
the public SongChart API and explicitly exports Pro Drums Expert and ExpertPlus.

A synthetic MIDI regression exposed a real state leak: a late Expert disco-flip
event incorrectly affected earlier ExpertPlus notes. A small patch resets that
state at each difficulty in this **isolated source checkout only**. Its exact diff
is `tools/recovery/ChartReference/yarg-difficulty-state.patch`; source/binary hashes
and build logs are in `evidence/parser-provenance.json`. No native application parser,
existing install, source chart, dataset or checkpoint was modified.

Reference semantics were checked against parser code and its linked
[format documentation](https://github.com/TheNathannator/GuitarGame_ChartFormats),
pinned at `3d3640574821e1f7f0ec4be70627893aa88fdff6`. Integration fixtures exercise
tempo changes, positive offsets, MIDI tom markers, disco flips and optional kicks.
The five source tempo maps, meters, raw ticks, lane/dynamics information, and
sections are retained. Adapt's ini delay is +10 ms; other selected offsets/delays
are zero. No estimated or prediction-derived offset is applied.

Audio is decoded from each package. Adapt contains six stems; these are summed
at their original zero positions with one common peak gain, and only tails are
zero-padded. Other packages contain a single song stream. The original compressed
audio is preserved; derived stereo FLOAT WAVs and PCM hashes are recorded. An
obsolete absolute `MusicStream` path embedded in Cartel's chart is ignored in
favor of its adjacent package audio. No path on D: is followed for this input.

## Alignment admission findings

An independent acoustic screen compares chart kick/snare times with positive
spectral flux in fixed beginning/middle/end 12-second windows, without consulting
model predictions or moving notes. `alignment-01/alignment.json` records all
windows and lag curves; PNGs show the unshifted chart over the acoustic evidence.

- **All three KLEWS songs require timing review before model ranking.** Eighteen
  window/family measurements peak approximately 40–50 ms before chart time.
  `klews-snare-waveforms.png` shows nine raw-waveform anchors supporting a material
  early-transient/late-chart discrepancy. The precise correction is not certified.
- A known-onset synthetic attack places this flux estimator's peak about 7.26 ms
  early, so a flux maximum is not an unbiased physical-onset annotation. That
  control does not explain the full KLEWS discrepancy.
- Adapt peaks are 5–10 ms early across its screened bands/windows. DIARRHEA snares
  are near zero; its middle/end kick band prefers +25 ms. These are acoustic
  checks, not a listening verification or proof of instrument labels.

The KLEWS mismatch can dominate the 25/50 ms score and reverse apparent system
ranking near the tolerance boundary. **Do not tune the transcriber to reproduce
this possible reference offset.** No shifted score has replaced the raw scores.
The reserved songs also remain provisional pending short-passage listening review.

## Scoring contract and limits

Three fixed audio-only candidates: inherited `faithful`, ADTOF on the full mix,
and ADTOF after stereo-input `htdemucs_ft` separation (seed 0, overlap .25,
mono-derived peak gain, original ADTOF thresholds, CPU reference inference).
References are never passed to either transcriber. Original event predictions,
activations, stems, logs, weights/code hashes and manifests are retained under
`evaluation-01/`. No retraining, threshold sweep, application-default promotion,
or modification to either m!sa acceptance song occurred.

One-to-one matching maximizes match count, then minimizes absolute time error at
25 and 50 ms. The report includes precision, recall, F1, extra/missing counts,
per-family measures, median/p90 absolute error and median signed timing error.
Possible wrong-family pairs are assigned one-to-one **after** same-family matches;
they may instead represent chart omissions, simultaneous hits or bad reference
timing. They are review candidates, not adjudicated model mistakes.

Primary broad-family proxies: kick, red-pad snare (including model side-stick),
yellow-cymbal HH, remaining tom pads, and blue/green cymbals. Yellow is a playing
convention, not definitive acoustic identity. A second view merges HH/CY to expose
this ambiguity. Neither view measures China, open/closed HH, exact tom pitch, or
measured dynamics. See the [official drum mapping guide](https://wiki.clonehero.net/books/guitars-drums-controllers/page/midi-drums).

Simultaneous same-family lanes are collapsed on **both** sides for family-presence
scoring; raw lane multiplicity is preserved. That produces 7,902 five-family
reference events. Optional 2x kicks are included. The runner's original metrics
reuse MDB's side-stick policy; `report/rescored-metrics.json` and `report/summary.json`
apply the explicit CH broad-snare and family-presence policy and are the report
of record. Neither version changes event timing or the raw predictions.

## Completed fixed-candidate results

All 15 song/system runs completed. Values below are unshifted five-family proxy
F1, shown as **25 ms / 50 ms**. The first three rows are **timing-flagged
references, not valid evidence for selecting a winning model**.

| Song | Inherited faithful | ADTOF full mix | ADTOF stereo-separated |
|---|---:|---:|---:|
| Failure's Not Flattering — timing flag | .0113 / .3330 | .0000 / .5332 | .0014 / .3035 |
| Say Anything (Else) — timing flag | .0102 / .5004 | .0016 / .7677 | .0045 / .4748 |
| Knuckles — timing flag | .0084 / .4604 | .0013 / .7723 | .0086 / .7596 |
| Adapt — reserved | .4540 / .5515 | .7665 / .7692 | .8976 / .8976 |
| DIARRHEA — reserved | .5215 / .5347 | .8489 / .8494 | .8101 / .8101 |

Pooled **reserved-song** agreement at 50 ms (3,500 family-presence references):

| System | Precision | Recall | F1 | TP / extra / missing | Median / p90 absolute timing on matches |
|---|---:|---:|---:|---:|---:|
| Inherited faithful | .5663 | .5231 | .5439 | 1,831 / 1,402 / 1,669 | 7.00 / 26.63 ms |
| ADTOF full mix | .8004 | .8157 | .8080 | 2,855 / 712 / 645 | 1.93 / 10.00 ms |
| ADTOF stereo-separated | .8812 | .8326 | .8562 | 2,914 / 393 / 586 | 3.80 / 12.06 ms |

At 25 ms the reserved F1 values are .4845, .8063 and .8562. Signed median errors
at 50 ms are -1.40, -0.01 and -2.84 ms respectively. Timing is conditional on
matching; it excludes misses and is relative to the chart, not verified onsets.

Reserved per-family precision/recall/F1 at 50 ms:

| Family proxy | Inherited faithful | ADTOF full mix | ADTOF stereo-separated |
|---|---|---|---|
| Kick | .9347 / .8052 / .8651 | .9797 / .9706 / .9751 | .9823 / .9782 / .9802 |
| Snare | .8449 / .4863 / .6173 | .9908 / .9781 / .9844 | .9799 / .9745 / .9772 |
| HH convention | .3051 / .5590 / .3948 | .8196 / .5109 / .6295 | .7978 / .7107 / .7517 |
| Tom | .4091 / .1154 / .1800 | .5862 / .5449 / .5648 | .7732 / .4808 / .5929 |
| Other cymbals convention | .4438 / .1090 / .1750 | .5394 / .8852 / .6703 | .7372 / .7093 / .7230 |

Merging HH/CY changes reserved F1 to .6245 / .9227 / .9083 for inherited, full-mix,
and separated respectively. **The ADTOF ranking reverses under this coarser
interpretation.** That and the opposing per-song separation effects argue for
auditing cymbal labels/input effects before promoting a system. Toms remain a
potential recall bottleneck, subject to reference-label/completeness review.

`report/summary.json` includes development, reserved and all-song results at both
tolerances, per-song/per-family scores and timing. All-song aggregates are retained
for reproducibility, not used as an accuracy headline because the development
references are timing-flagged. Fifteen `*.disagreements.json` files retain unmatched
notes and possible substitutions. The review offers fixed beginning/middle/end
passages for every song and one 8-second disagreement passage per development
song; reserved model-error windows were not mined for tuning.

## Overlap and preservation

All five package-mix hashes and decoded-PCM hashes are distinct. This rules out
exact duplicates in this batch, not alternate mixes/remasters elsewhere. ADTOF's
public metadata was inspected at `b3968fb332f69b65ee07c089fc62f436503755db`.
Its published split definitions cover RBMA/ENST/MDB rather than a complete
crowdsourced-chart training roster; no candidate-name match is **not** evidence
of exclusion. Both inherited-model and ADTOF training overlap remain unknown.
Reserved means not used for local parameter tuning, not unseen by pretrained models.

Local discovery queried both existing read-only SQLite inventories: C:/E:/F: snapshot
and later D: snapshot, including ignored files, `.sng` and chart-looking archive
names. Forty C:/E:/F: hits are unrelated PNG test fixtures/NVIDIA files; D: has no
hits. No eligible local package was found in that bounded query. Archive contents,
excluded paths and files added since the snapshots were not exhaustively searched.

Seventy-eight preservation comparisons passed for acquired members and the four
original/corrected acceptance-chart hashes. ZIP members were read back; both RARs
passed archive integrity checks. D: and F: were read-only throughout. Existing
experiments and corrections remain unchanged. The new experiment is preservation
on C:, not an independent-device backup. No old cleanup/migration scripts ran.

## Reproduce and continue

Use `.venv-recovery\Scripts\python.exe` and the commands in
`tools/recovery/ChartReference/README.md` for the patched, pinned parser build.
All destination folders must be new. The completed root is evidence, not a rerun
target. Freeze any future admission/alignment revisions separately before scoring.

Focused validation: **36 passed**, including real YARG MIDI/.chart integration
and previous recovery, timing, review/export and user-feedback checks. The browser
review loaded, switched songs/candidates, retained half speed, decoded mix/stem
audio, and sought Adapt to 266.738 s with full 283.648 s duration and no media error.
These are execution checks, not listening verification.

Review: `http://127.0.0.1:8774/review/review.html` while the loopback-only server runs.
Check the port before restarting:

```powershell
./.venv-recovery/Scripts/python.exe tools/recovery/serve_review.py `
  --root 'C:\Users\10ros\BeatSight-Recovery\2026-10-14-clone-hero-benchmark-01' --port 8774
```

Main commands used (do not rerun against occupied output directories):

```powershell
$bench = 'C:/Users/10ros/BeatSight-Recovery/2026-10-14-clone-hero-benchmark-01'
./.venv-recovery/Scripts/python.exe tools/recovery/clone_hero_reference.py `
  --root $bench --exporter "$bench/parser-build/bin/ChartReference/release/ChartReference.dll" `
  --selection selection-v2.json --output-name prepared-v2
./.venv-recovery/Scripts/python.exe tools/recovery/benchmark_clone_hero.py `
  --prepared "$bench/prepared-v2" --reference-repo 'C:/Users/10ros/BeatSight-Recovery/2026-10-13/reference-adtof' `
  --output-dir "$bench/evaluation-01"
./.venv-recovery/Scripts/python.exe tools/recovery/audit_chart_alignment.py `
  --prepared "$bench/prepared-v2" --output-dir "$bench/alignment-01"
./.venv-recovery/Scripts/python.exe tools/recovery/report_clone_hero.py --root $bench
```

First next action: listen to the fixed short KLEWS beginning/middle/end windows
and verify reference offset/completeness, retaining the original charts. Check
Knuckles' yellow-pad runs for actual toms versus missing cymbal flags. Inspect
the reserved songs' audio/chart alignment without tuning on their results.
If an offset is supported independently by the audio, create a separate reviewed
reference version and rescore **saved** predictions; do not rerun models or shift
their output to optimize F1. Only after reference admission should a measured
transcription bottleneck drive a one-variable change and recheck of WHITE WAVES
and Death Before Dishonor, preserving the user-supported openings.
