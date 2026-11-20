# Clone Hero source controls and fixed original-drum probe — 2026-10-15

**Later continuation:** `MDB_RESIDUAL_INPUT_AND_DECODER_AUDIT_2026-10-15.md`
completes the next bounded development experiment. The 25% residual-input
candidate is rejected. A source-conformant decoder helper is verified, but its
small cached-output score change does not solve the recall deficit. This report's
measurements and original files remain preserved.

Adapt's original drum stem supports retaining its existing chart timing. The
earlier full-mix attack screen failed because it was not a reliable timing test
under that mix condition. A fixed ADTOF run on the original drum stem improves
chart agreement but leaves tom and cymbal mismatches. Neither result establishes
complete musical accuracy or supports a model/default promotion.

New scoped experiment:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-chart-reference-controls-01`.
The October 14 benchmark, October 15 reference audit, datasets, checkpoints and
user-supported m!sa corrections were preserved. D: and F: remained read-only.
There was one new fixed inference, no training, new separation or broad download.

## Source control for the timing screen

`probe_reference_attack_controls.py` reconstructs Adapt's prepared mix from its
six original stems using the recorded common gain and timeline. Reconstructed
full-mix PCM exactly matches the prepared file. Summing the separately grouped
drums and other instruments differs by at most `1.7881393432617188e-7` through
float rounding. Source hashes, sample rates and lengths are checked first.

The protocol was saved before measurement. The same three fixed 12-second snare
windows and unchanged RMS-energy-rise algorithm from the previous audit were
applied to four inputs. No model events determine anchors or offsets.

| Input | Beginning / middle / end profile peak (ms) | Fraction of anchors within 10 ms of each peak | Prior frozen gate |
|---|---|---|---|
| Original reconstructed mix | -3 / -3 / -3 | .273 / .308 / .222 | Fail |
| Original author drum stem | -3 / -3 / -3 | 1.000 / 1.000 / .778 | Pass |
| Remaining five stems, drum file withheld | +24 / +28 / -5 | .182 / .154 / .222 | Fail |
| Silence | Unmeasurable | Unmeasurable | Fail |

The drum input supports 31/33 anchors near the window peaks. Full-mix failure
therefore cannot be treated as evidence that this chart is misaligned. The
withheld-drums end window also has a near-zero aggregate peak: rhythmic
coincidence alone cannot authenticate instrument identity. Source filenames do
not prove bleed-free stems. `controls.json` and `adapt-source-control.png` retain
the measurements; nine exact-condition clips support inspection.

An explicitly recorded follow-up uses all **262 original snare chart anchors**
in fixed 30-second bins. **253/262 (96.6%)** have their strongest nearby original-
drum energy rise within 10 ms of the unchanged chart time; the same 253 are within
25 ms. Every bin's aggregate profile peaks at -3 ms. This gives temporal support
across the full song, without apparent global drift. It does not authenticate
every snare label or identify uncharted notes. The remaining nine anchors are
not confirmed chart mistakes. Individual peaks around -3 and +8 ms also explain
why an aggregate detector peak is not an exact correction. **No -5 ms or other
reference shift was accepted.** See `full-song/snare-timing.json` and its PNG.

## Cymbal waveform screen

`audit_cymbal_similarity.py` compares 80 ms original-drum waveforms at unchanged
chart times, with up to 5 ms lag and a predeclared .98 normalized-correlation
threshold. It includes 343 cymbal events without another charted onset from
30 ms before to 90 ms after: 262 yellow, 79 blue and two green. Eligible pairs
are at least one second apart. This is a sample-reuse review screen, not an
instrument classifier or an audio listening judgment.

- Across HH/CY proxy families: **0/21,207 pairs** reach .98; maximum .957751.
- Within the same pad: **106/36,903 pairs** reach .98; maximum .997013.

All eligible pairs were compared. Log-spectrum cosine is descriptive only;
`cymbal-similarity/protocol-clarification.json` corrects misleading wording in
the preserved initial protocol/source without changing any results. Twenty
clips from the top five pairs per group match source PCM exactly. No cymbal
relabel was accepted. Different velocities, ringing and sample variation mean
that zero cross-family matches cannot certify the chart's HH/CY identities.

## Full-song original-drum input probe

`probe_chart_original_drums.py` ran the pinned ADTOF weights once on Adapt's
original `drums.ogg`, using the prepared mix's gain `0.5822069276353555`, stereo
PCM and a 251-sample zero tail to preserve the full timeline. Thresholds remain
`[.22, .24, .32, .22, .30]`, 100 fps, seed 0, CPU; no offset or parameter was
selected from results. The pinned source revision is
`85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9`; weight SHA-256 is
`1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320`.
The new input round-trips exactly as float PCM. Saved predictions from the three
October 14 arms reproduce their previous score dictionaries exactly.

Unshifted five-family chart agreement at 50 ms, for Adapt only:

| Input/system | TP / FP / FN | Precision | Recall | F1 | HH/CY-merged F1 |
|---|---|---:|---:|---:|---:|
| Original drums, fixed ADTOF | 1695 / 139 / 158 | .9242 | .9147 | .9194 | .9767 |
| Saved stereo-input separation, ADTOF | 1609 / 123 / 244 | .9290 | .8683 | .8976 | .9478 |
| Saved full mix, ADTOF | 1405 / 395 / 448 | .7806 | .7582 | .7692 | .9331 |
| Saved inherited faithful | 1018 / 821 / 835 | .5536 | .5494 | .5515 | .6570 |

Original-drum and saved stereo-separated counts are unchanged at 25 ms. For
matched original-drum predictions, median absolute timing error is 7.416 ms,
90th percentile 12.040 ms and signed median -7.416 ms, all relative to chart
targets and conditional on a match.

| Family | Targets | Saved stereo-separated TP / FP / FN | Original-drum TP / FP / FN |
|---|---:|---|---|
| Kick | 584 | 584 / 3 / 0 | 584 / 1 / 0 |
| Snare | 262 | 259 / 8 / 3 | 262 / 0 / 0 |
| Tom | 123 | 52 / 4 / 71 | 86 / 6 / 37 |
| HH proxy | 578 | 519 / 93 / 59 | 521 / 69 / 57 |
| CY proxy | 306 | 195 / 15 / 111 | 242 / 63 / 64 |

Original drums recover 86 additional target matches, mainly CY (+47) and toms
(+34), while false positives rise from 123 to 139. Tom recall remains .6992.
Merging cymbals collapses two reference targets and 44 original-drum predictions;
its TP/FP/FN is 1778/12/73. The merged view cannot validate HH versus other cymbal
identity. These are chart-proxy disagreements, not individually verified errors.

This source is an **oracle diagnostic input**, unavailable for ordinary full-mix
transcription. The saved separated input has different normalization and is
mono, so this contrast does not isolate separator quality alone. Adapt is a
previously reserved song now inspected diagnostically; do not tune parameters
on it or describe this follow-up as a newly untouched test. Training overlap,
chart completeness and broad instrument identities remain unresolved. The
original 15-run benchmark scores and all application defaults remain unchanged.

## Knuckles listening evidence

The user clarified that **“sounds like a guitar hit”** refers to **“Repeated
tapping”**, rather than just the first prominent strum. The verbatim observation,
clarification, original reference hash and 35 YellowDrum event records in the
0–8 s opening are preserved in `knuckles-user-feedback-02.json`.
`decisions-feedback-addendum.json` supersedes the earlier pending-clarification
field in `decisions.json`.

Those 35 tom-proxy targets are disputed and excluded from trusted reference
admission/training. This is a reference-status decision, not a per-note guitar
annotation or a claim that no drums overlap the figure. Original chart notes
and existing scores are unchanged; no scoring mask has been applied. A future
masked evaluation must handle uncertain predictions as well as targets rather
than simply deleting reference notes. KLEWS remains excluded from model
selection because timing and reference-label questions are unresolved.

## Verification, preserved evidence and next action

The combined focused suite passes **52 tests**, including parser integration,
source reconstruction, hash rejection, independent-window admission, silence,
and known waveform reuse controls. **124 prior source/output/media hash checks
match** (79 prior preservation entries plus 45 prior review media entries).
Twenty-nine new clips pass hash, shape, rate and finite-PCM checks; all 20 cymbal
comparison clips also match the original source samples exactly. Details are in
`verification.json`; protocols preserve source hashes and executed helper copies.
`evidence/docs-before-update.zip` preserves six prior continuity documents.
The final source/document snapshot and read-back manifest are under `evidence/`.
Copies on C: protect against accidental edits, not loss of that device.

The next model experiment belongs on the **existing seven annotated development
recordings**, with one frozen input-preservation variable and unchanged weights,
thresholds and matching. Reuse saved predictions where possible and report all
recordings/families at 25/50 ms, including timing and unmatched events. Use the
observed tom/input losses as a hypothesis; do not optimize against Adapt or the
uncertain KLEWS charts. No broad download, retraining or global HH suppression
is justified by this diagnostic alone. Preserve the two specific m!sa opening
corrections and update recovery after the next measured result.

## Reproduction

Run from `C:\github\BeatSight`; choose a fresh C: root. These commands must not
target a completed experiment directory.

```powershell
$benchmark = 'C:\Users\10ros\BeatSight-Recovery\2026-10-14-clone-hero-benchmark-01'
$priorAudit = 'C:\Users\10ros\BeatSight-Recovery\2026-10-15-clone-hero-reference-audit-01'
$reference = 'C:\Users\10ros\BeatSight-Recovery\2026-10-13\reference-adtof'
$experiment = 'C:\Users\10ros\BeatSight-Recovery\NEW-source-controls'
.\.venv-recovery\Scripts\python.exe tools/recovery/probe_reference_attack_controls.py --benchmark $benchmark --prior-audit $priorAudit --output-dir $experiment
.\.venv-recovery\Scripts\python.exe tools/recovery/probe_reference_attack_controls.py --benchmark $benchmark --output-dir $experiment --extend-full-song
.\.venv-recovery\Scripts\python.exe tools/recovery/audit_cymbal_similarity.py --benchmark $benchmark --output-dir "$experiment\cymbal-similarity"
.\.venv-recovery\Scripts\python.exe tools/recovery/probe_chart_original_drums.py --benchmark $benchmark --reference-repo $reference --output-dir "$experiment\oracle-original-drums"
```

Human feedback is provenance to preserve, not a result regenerated by these
commands. The current JSON clarification supersedes the older review page's
uncertainty about which opening sound the user meant.
