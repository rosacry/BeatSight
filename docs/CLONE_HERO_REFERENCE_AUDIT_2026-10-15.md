# Clone Hero reference admission audit — 2026-10-15

**Later continuation:** `CLONE_HERO_SOURCE_CONTROLS_2026-10-15.md` tests the same
screen on Adapt's original drum stem, where it passes despite mix failure.
253/262 full-song snare anchors have a strong energy rise within 10 ms of original
chart time. No reference shift was accepted. A separate fixed original-drum
ADTOF diagnostic was subsequently run; this report's no-inference statement
describes the earlier audit only. The user has now clarified that the Knuckles
guitar-like sound is **“Repeated tapping”**. The follow-up's hash-bound feedback
file lists 35 disputed opening yellow-tom targets without editing chart/scores.

The independent checks rule out the tested audio decoder and `.chart` tempo
conversion as causes of the KLEWS timing discrepancy. They **do not establish an
exact correction**. No chart was shifted, no model was rerun, and the October 14
scores remain unchanged. The user also disputed the Knuckles opening sound:
**“sounds like a guitar hit”**. That passage is not accepted as verified tom truth.

New scoped experiment:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-clone-hero-reference-audit-01`.
The October 14 benchmark and earlier m!sa corrections were read-only. D: and F:
were not targeted by any write or recovery operation.

## Independent checks

`tools/recovery/audit_clone_hero_reference.py` freezes its protocol and source
hash before reading song audio. It uses original chart times and package mixes,
never model event predictions or estimated stems. No new training was needed.

- **Ten original audio files:** FFmpeg and libsndfile produce identical frame
  counts. All 28 non-silent comparison windows have zero-sample best lag; maximum
  PCM difference across files is approximately `6.56e-7`. Two silent windows in
  Adapt's `song.ogg` have no measurable lag. This excludes a 30–50 ms discrepancy
  between these decoders, not every possible playback issue.
- **4,406 `.chart` drum events:** direct integration of raw SyncTrack BPM events
  agrees with YARG within `2.85e-11` ms, including metadata shifts. The two MIDI
  references retain the previous parser validation; this independent clock check
  specifically covers the three `.chart` sources.
- **15 fixed 12-second windows:** positive changes in stereo RMS energy are
  measured in approximately 1 ms blocks around chart snares. Each anchor curve
  is normalized, then averaged and smoothed. The beginning window selects a
  candidate lag rounded to 5 ms; middle and end validate it independently.
  This detector finds energy rises, not authenticated snare onsets.

The frozen gate requires at least five anchors/window, peaks within 10 ms of the
selected candidate, and at least 60% of individual strongest rises within 10 ms
of their window peak. **None of the five songs passed all requirements.** Criteria
were not weakened after seeing the results.

| Song | Beginning / middle / end RMS-rise peak lag | Candidate from beginning | Support fractions |
|---|---|---|---|
| Failure's Not Flattering | -47 / -36 / -35 ms | -45 ms | .267 / .476 / .619 |
| Say Anything (Else) | -43 / -40 / -31 ms | -45 ms | .857 / .579 / .929 |
| Knuckles | -29 / -29 / -29 ms | -30 ms | 1.000 / .722 / .556 |
| Adapt | -3 / -3 / -3 ms | -5 ms | .273 / .308 / .222 |
| DIARRHEA | +6 / +7 / +7 ms | +5 ms | .444 / .059 / .500 |

Negative lag means the energy-rise peak precedes its chart anchor. The KLEWS
flag persists, but RMS-rise peaks differ from the earlier 2048-sample flux peaks.
Neither is automatically a drum onset. Eight synthetic noise-burst calibrations
have 0–4 ms peak error for known 0/2/5/10 ms attack ramps; that is **not** an error
bound for real mixed audio. Timing consistency cannot establish instrument truth.

The first run returned a boundary lag for two completely silent decoder windows.
That output and source remain in the experiment root. The corrected run in
**`validated/` is the audit of record**: silent-window lags/correlations are null
and explicitly unmeasurable. Regression tests cover silence and a known
17-sample decoder shift. Timing profiles and candidate decisions are unchanged.

## Knuckles user observation

The short review asked about the repeated yellow-pad sound in song seconds 0–8.
The user's exact response was **“sounds like a guitar hit”**.
`user-feedback-01.json` preserves the words, context, reference/audio hashes and
bounded interpretation. This passage contains 35 YellowDrum notes, 13 kicks,
10 red/snare notes and one YellowCymbal note.

This is not an exact per-note annotation and does not prove that every yellow
note is guitar or that overlapping drums are absent. No note was removed,
relabelled or shifted. The opening is disputed reference material, and Knuckles
remains unadmitted for model selection because timing and instrument/completeness
checks are unresolved.

The [author's site](https://www.klewshero.com/) describes charts created by a
drummer and tested on an electronic kit; saved chart-list metadata claims hand
authoring. The site was checked again this turn. This establishes stated
provenance, not independent correctness. The raw Knuckles file contains an
`ExpertDrums` track, not a guitar track accidentally selected by the importer.
There is no basis here to claim it was automatically generated.

An eight-second excerpt from the **already saved** Demucs estimated drum stem is
available as a listening aid. `estimated-stem-aid.json` records its source/hash.
It can retain guitar leakage or omit drums; it is not truth and was not used in
the independent timing measurements.

## Review and preserved artifacts

Review: `http://127.0.0.1:8775/review/review.html`.
Recorded feedback plus original/estimated-stem comparison:
`http://127.0.0.1:8775/review/knuckles-feedback.html`.
The October 14 full-song review on port 8774 remains separate and intact.

There are 18 chart-selected passages: fixed beginning/middle/end windows for all
five songs and Knuckles contrasts at 0–8, 13–21 and 116–124 seconds. No reserved
model-error passages were selected. The page has original audio, lane markers,
waveform zoom, half-speed playback and optional local observation export. It
contains no model event predictions. Adapt also supplies its original author's
drum stem, distinct from estimated separation.

Development passages offer original-chart snare clicks and a uniform **40 ms
earlier comparison stimulus**, based on the existing acoustic flag. This was not
optimized against F1 and is not an accepted reference correction. The original
chart files and scores remain unchanged.

| Path under the new root | Meaning |
|---|---|
| `validated/protocol.json` | Frozen method, code hash and decoder versions |
| `validated/audit.json` | Decoder, clock and fixed-window measurements |
| `validated/*-attacks.png` | Profiles and individual-anchor histograms |
| `review-protocol.json` | Passage selection and click-trial interpretation |
| `review/review-data.json` | Sample bounds, clip hashes and chart provenance |
| `user-feedback-01.json` | Verbatim guitar-hit observation |
| `estimated-stem-aid.json` | Optional Knuckles stem-excerpt provenance |
| `verification.json` | Preservation, PCM and review checks |
| `evidence/docs-before-update.zip` | Recovery documents before these updates |

## Validation and next decision

**48 focused tests pass**, including real YARG integration and 12 new audit/review
checks. New cases cover lag sign/timing at two sample rates, tempo integration,
metadata shifts, rejection of unhandled anchors, silent decoder windows, known
decoder delay, and trial-click placement without shifting original audio.

**79 source/output SHA-256 comparisons pass**, including package files, prepared
references/audio, 15 saved model outputs, five estimated stems and four
original/corrected m!sa charts. All 45 initial review media files pass HTTP range
checks; 21 original mix/author-stem clips exactly match source PCM. The browser
decodes the eight-second Knuckles click trial and 12-second Adapt original stem
at half speed without media errors; source switching and 250 ms zoom work.
These are execution checks, not an agent claim to have listened. The only new
listening evidence is the user's bounded Knuckles observation.

The measured blocker is **reference admission**, not a justified model setting.
Do not rescore with a guessed shift or silently promote chart pads to verified
instruments. Resolve specific opening/contrast notes and timing anchors using
listening evidence or an independently auditable source. Otherwise keep KLEWS
quarantined from model selection and report reserved-song comparisons only with
their existing proxy/overlap limits. Do not fit uncertain references with another
inference or training batch. The next diagnostic should discriminate a named
remaining ambiguity, not merely repeat another onset detector.

To reproduce, choose an unoccupied root and retain all outputs:

```powershell
$bench = 'C:/Users/10ros/BeatSight-Recovery/2026-10-14-clone-hero-benchmark-01'
$newAudit = 'C:/Users/10ros/BeatSight-Recovery/CHOOSE-A-NEW-SCOPED-DIRECTORY'
New-Item -ItemType Directory -Path $newAudit -ErrorAction Stop
.\.venv-recovery\Scripts\python.exe tools/recovery/audit_clone_hero_reference.py `
  --benchmark $bench --output-dir "$newAudit/validated"
.\.venv-recovery\Scripts\python.exe tools/recovery/build_reference_admission_review.py `
  --benchmark $bench --audit-root $newAudit
```

To restart the completed review, check port 8775 is free, then run:

```powershell
.\.venv-recovery\Scripts\python.exe tools/recovery/serve_review.py `
  --root 'C:/Users/10ros/BeatSight-Recovery/2026-10-15-clone-hero-reference-audit-01' --port 8775
```
