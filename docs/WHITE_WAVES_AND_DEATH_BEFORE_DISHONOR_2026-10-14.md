# Full-song practice drafts — 2026-10-14

## Outcome and intended use

**Later user feedback identified wrong opening cymbals.** See
`OPENING_CORRECTIONS_AND_CHART_BENCHMARK_2026-10-14.md` for separate corrected
packages, direct user evidence, and the next chart-reference evaluation direction.
The original packages described below are preserved model outputs.

Both user-selected songs now have self-contained native practice drafts, compared
with the inherited classifier and two reference input variants. A bounded stereo
input experiment produced a modest improvement on the existing annotated diagnostic.
The current experimental drafts use that stereo-preserving separation path.

**These are unreviewed drafts, not verified transcriptions for learning every note.**
Neither song has an independently checked event annotation here. Their precision,
recall, F1, actual onset errors, and articulation accuracy remain **unmeasured**.
No independent listening/hand-labeling pass was completed. Signal plots and model
disagreement locate review candidates; they do not establish ground truth.

The user said these are the two songs they most want to learn and the reason they
started BeatSight. Keep them as product acceptance examples, especially the technical
opening hi-hat pattern in **Death Before Dishonor**. Do not settle for broad-family
detection if the rhythm and articulation needed to learn those passages remain wrong.

## Artifacts

All new audio, predictions, logs and experiments are in these new C: directories:

- `C:\Users\10ros\BeatSight-Recovery\2026-10-14-white-waves-01`
- `C:\Users\10ros\BeatSight-Recovery\2026-10-14-death-before-dishonor-01`

In each directory, import **`practice-stereo-draft/chart.bsm`** with its adjacent
audio files present. The package includes the estimated drum stem for the native
mixer, review bookmarks, a README, and a hash manifest. Earlier `practice-draft`
packages and every inference arm remain preserved. No application default changed.

`review-v2/review.html` compares all four event lists with original-mix, mono-input
stem and stereo-input stem playback, speed control, looping and family filtering.
`review-v2/summary.json` contains measured agreement and explicitly null accuracy
fields; `review-candidates.json` lists possible missing/extra/wrong-family events.
`review-*.png` contains signal/event plots. The earlier three-way review remains
under `review/`. It also holds the detailed opening hi-hat probe for the second song.

The localhost players can be started independently (no network upload):

```powershell
py -3.11 tools/recovery/serve_review.py --root 'C:\Users\10ros\BeatSight-Recovery\2026-10-14-white-waves-01' --port 8771
py -3.11 tools/recovery/serve_review.py --root 'C:\Users\10ros\BeatSight-Recovery\2026-10-14-death-before-dishonor-01' --port 8772
```

Open `/review-v2/review.html` on the relevant localhost port. Each command is a
foreground server; use separate terminals. The helper binds only 127.0.0.1 and
supports byte ranges, which were necessary for browser audio seeking.

## Source identity and full-song coverage

| Song | Duration | Input SHA-256 |
|---|---:|---|
| WHITE WAVES | 240.011610 s | `ace64325b40d3212155cfaf7211188607c98eb1514caf62f6979bdce16576891` |
| Death Before Dishonor | 204.963492 s | `354df37aba417e080d8104252dd3a12e012cbf3bade5cc0303854076a074d7fb` |

Both decoded as finite stereo 44.1 kHz audio. The MP3's decoded peak exceeds 1.0;
float analysis preserved that value rather than silently clipping it. Originals
were copied and SHA-256 checked. The second file's embedded artist tag is `m!sa`.
All inference covers the complete files; no crops were substituted for song runs.

Native FLAC playback exposed a separate compatibility issue: TrackBass reported
204,000 ms for the 204,963.492 ms FLAC, while the drum WAV had the correct duration.
The final second-song package therefore uses a derived PCM16 WAV. Every decoded
sample equals the original FLAC's PCM16 samples; the original FLAC remains adjacent
and untouched. The native player then reports equal mix/stem lengths and equal seek
positions. This fixes the package discrepancy without claiming its library cause
was identified or modifying the application decoder.

## Full-song output comparison

Counts measure what each system exported, **not correct notes**.

| Song / approach | Kick | Snare | Hi-hat | Tom | Cymbal | Other | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| WHITE WAVES, inherited faithful profile | 615 | 338 | 301 | 48 | 260 | 3 | 1,565 |
| WHITE WAVES, ADTOF full mix | 696 | 481 | 77 | 58 | 540 | 0 | 1,852 |
| WHITE WAVES, ADTOF mono-input separation | 701 | 482 | 173 | 54 | 291 | 0 | 1,701 |
| WHITE WAVES, ADTOF stereo-input separation | 704 | 481 | 173 | 53 | 434 | 0 | 1,845 |
| Death Before Dishonor, inherited faithful profile | 359 | 176 | 148 | 63 | 284 | 0 | 1,030 |
| Death Before Dishonor, ADTOF full mix | 369 | 226 | 168 | 111 | 325 | 0 | 1,199 |
| Death Before Dishonor, ADTOF mono-input separation | 360 | 223 | 274 | 88 | 80 | 0 | 1,025 |
| Death Before Dishonor, ADTOF stereo-input separation | 359 | 226 | 213 | 77 | 203 | 0 | 1,078 |

The ADTOF source and weight pins match the earlier diagnostic. Source modifications
are rejected by preflight; the runner records source/weight hashes, thresholds,
activations, stems, package versions, input/output hashes and logs. MIDI is explicitly
written from picked events (the upstream `return_activations=True` call alone does
not create a MIDI file). Every final package retains the selected event timestamps;
there is no beat snapping or added synthetic rhythm.

The native schema lacks broad hi-hat/tom/cymbal identifiers. The draft uses
`hihat_closed`, `tom_mid`, and `crash` as **display aliases only**. They mean
unspecified hi-hat, tom and cymbal. Openness, pedal/hand technique, ride/crash/china,
tom pitch, sticking and dynamics are not inferred. Velocity 0.8 is a fixed display
default. These limitations are written into chart metadata and package instructions.
Tempo estimates (120.1853 and 135.9992 BPM) and 4/4 are provisional grid metadata;
the grid is hidden and note times do not depend on them.

## Review findings

### WHITE WAVES

- **20–40 s:** full-mix ADTOF predicts one hi-hat versus 64 with mono-input separation.
  Repeated transients appear in the separated signal plot. This is a strong candidate
  for full-mix masking, but neither the full 64 count nor its instrument identity is
  manually verified.
- **84–92 s:** cymbal predictions are 26 from full mix, 5 after mono-input separation,
  and 18 after stereo-input separation. Repeated high-band transients remain visible.
  Preserving spatial information changes this apparent undercoverage substantially;
  the remaining differences require checking against original audio.
- Across the song, the full-mix and mono-separated ADTOF arms pair 1,511 same-family
  events within 50 ms. Conditional median timing difference is 0 ms, p90 10 ms.
  This is stability between inputs to the **same model**, not true onset accuracy.
- The mono-separated and inherited lists pair 1,069 same-family events within 50 ms;
  median absolute difference is 7 ms and signed median inherited-minus-reference is
  +4 ms. There are 133 possible cross-family pairings after same-family matching.
  Simultaneous different instruments can produce such pairs too; do not call all 133
  verified substitutions.
- Both reference input variants agree within 25 ms on 190 snare and 92 kick candidates
  absent from the inherited same-family output within 50 ms. These are targeted
  listening priorities, not measured false-negative counts.

### Death Before Dishonor opening hi-hat

- **10–20 s:** hi-hat predictions are inherited 39, full-mix ADTOF 83, mono-separated
  ADTOF 79, stereo-separated ADTOF 80. The two original ADTOF arms pair 78 events
  within 25 ms; 44 of these have no inherited hi-hat within 50 ms. Their median
  inter-onset interval is 110 ms. Fast subdivisions are present in the model output;
  this does not confirm every subdivision or articulation.
- Of those 44 candidates, eight have no original raw detector peak within 50 ms.
  In a rerun with saved stem and observed processing stages, 34/44 reach the classifier
  input neighborhood. The gate-on rerun reproduces all original exported time/component
  pairs; generated note UUIDs differ. Therefore onset coverage alone cannot explain
  the missing output candidates.
- A controlled section-gate on/off pair used identical sample-array and onset hashes.
  Turning it off increases opening hi-hat output from **39 to 49**, and 14 original
  missing candidates become nearby hi-hat outputs. Snare remains 8 and kick remains 16
  in that interval. This demonstrates a contribution from the inherited loudness gate;
  it does not solve the remaining classification/detection problem or establish that
  every addition is correct. No global gate setting was changed.
- Evidence: `review/intro-hihat-probe.json`, `review/intro-hihat-010-018.png`,
  `intro-gate-probe/summary.json`, both arm `stages.json` files and `baseline-check.json`.

Signal timing proxies in the review summary measure distance to a nearby spectral
flux maximum. They are bounded by a +/-29 ms search and are circular diagnostics.
They must never be reported as true timing accuracy or used to claim note correctness.
No global timing shift was applied to either song.

## Bounded comparison on annotated development recordings

The same seven MDB Drums++ diagnostic recordings and annotations were reused,
with audio and annotation hashes rechecked. This is the existing **development**
set, not an independent final test. Training overlap is unknown, annotations have
not been independently audited here, and the 454.93 seconds of short recordings
do not represent these two full user songs.

| Approach | Tolerance | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| ADTOF full mix, newly run | 50 ms | 0.8089 | 0.6124 | 0.6970 |
| ADTOF mono-input separation, preserved predictions rescored | 50 ms | 0.8409 | 0.7192 | 0.7753 |
| Mix cymbals + mono-separated other families | 50 ms | 0.8318 | 0.7135 | 0.7682 |
| ADTOF stereo-input separation, newly run | 50 ms | 0.8431 | 0.7359 | 0.7859 |
| ADTOF mono-input separation | 25 ms | 0.8190 | 0.7005 | 0.7551 |
| ADTOF stereo-input separation | 25 ms | 0.8170 | 0.7131 | 0.7616 |

The fixed family-routing rule worsened the diagnostic and was not adopted. It was
chosen from song discrepancies before scoring, and no threshold search followed.

The stereo experiment retained left/right channels before the same `htdemucs_ft`
wrapper, dividing both by the same mono-derived peak gain, then averaging the drum
output to mono as before. Model, overlap, seed, reference thresholds and downstream
inference remain fixed. This tests spatial information, not a new separator model.
F1 rose on six tracks; SpeedMetal fell from 0.9497 to 0.9463. At 50 ms, kick/snare/
tom/cymbal family F1 rose, but hi-hat F1 slipped 0.7062 to 0.7052. Stereo matched
1,811 reference events, with 337 extra predictions and 650 misses.

Conditional matched-note median absolute timing error is 9.17 ms for mono and
9.37 ms for stereo; p90 is 17.29 versus 17.46 ms, signed medians -6.04 versus -6.25 ms.
The small event-coverage gain is **not a timing improvement**. All scoring is
one-to-one at 25/50 ms without alignment or grid correction.

Evidence under the WHITE WAVES experiment: `routing-diagnostic-full-mix/routing-comparison.json`
and `stereo-diagnostic/metrics.json`, plus stems, activations and predictions.
The result supports stereo input as the next experimental practice candidate,
not default-model promotion or a claim of these songs' accuracy.

## Native compatibility and verification

- Reference and packaged charts pass shared JSON schema and timestamp/component checks.
- Actual `BeatmapLoader`, lane classification and `PlaybackScreen` loaded both final
  packages. Five broad families map to distinct semantic lanes; the current practice
  preset may display additional lanes and a shared kick line.
- Actual 1920x1080 3D captures were saved. The known header/back-button overlap remains;
  this is execution verification, not a passing visual-baseline regression test.
- WHITE WAVES original/stem lengths are 240011.610 ms; both seek to 84004.059 ms.
  Death Before Dishonor's lossless WAV/stem lengths are 204963.492 ms; both seek to
  12297.800 ms. Native TrackBass types were verified. This verifies decoder/seek
  consistency, not perceptual synchronization of every predicted hit.
- Twenty-three recovery/matching/export tests pass, including three new checks for
  one-to-one review matching and rejecting altered stereo-export notes. The local
  range server passed normal, suffix, open-ended and invalid byte-range checks.
  Both four-way review pages were checked live: original/stereo media seeking,
  half-speed selection and hi-hat filtering work; reported lengths match the files.
- The final integrity pass records 79 successful hash comparisons (some paths repeat
  across songs), exact package-to-prediction event equality, equal mix/stem frame
  counts, and the second song's sample-identical FLAC-to-WAV conversion. Source songs,
  used inherited models/thresholds, reference source and separator checkpoints match
  their recorded hashes. Evidence and final helper/native-capture source snapshots
  are in the WHITE WAVES experiment's `final-verification/`. The original packager
  source is preserved separately because an export guard was added after packaging;
  neither finished chart was regenerated or changed.
- No retraining, new model download, audio upload, publication, or external messages.
  D: and F: remained read-only; datasets, checkpoints and unrelated projects were not
  moved or overwritten. New helpers live under `tools/recovery`; product defaults
  and the pre-existing working-tree changes remain intact.

## Next evidence that matters

Independently annotate short, fixed excerpts before further parameter changes:
Death Before Dishonor 10–20 s hi-hats, WHITE WAVES 20–28 s sparse hats and 84–92 s
cymbal pattern, plus a tom fill. Record uncertainty and simultaneous components;
compare the final exported notes at 25/50 ms. Add instrument/technique labels only
when supported by listening or a reliable original source. The next major blocker
is verified note/articulation evidence, not more bulk data or repeated inference.
