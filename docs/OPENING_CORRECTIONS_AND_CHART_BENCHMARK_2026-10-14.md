# Opening corrections and chart-reference direction — 2026-10-14

Continuation notice: the proposal below has now been executed as an initial
five-song batch. See `CLONE_HERO_BENCHMARK_2026-10-14.md` for completed fixed-model
runs, reference-timing flags, provenance and next steps. Statements below that
acquisition had not begun describe the earlier opening-correction session.
The two user-supported song corrections remain unchanged.

## User-reviewed corrections

The user identified WHITE WAVES' first cymbal as **China, not hi-hat** and Death
Before Dishonor's main entrance as **crash, not hi-hat**. A follow-up explicitly
located the latter at about **8.75 s**, not the earlier predictions at 2.75/3.59 s.
This is direct user listening evidence. It is not an independent agent listening
pass or a verification of every note, articulation, or precise onset time.

New, separate artifacts:
`C:\Users\10ros\BeatSight-Recovery\2026-10-14-opening-feedback-01`.

| Song | Retained model time | Original stereo draft | Corrected copy |
|---|---:|---|---|
| WHITE WAVES | 1.000 s | hi-hat + unspecified cymbal | one China |
| Death Before Dishonor | 8.750 s | kick + hi-hat + unspecified cymbal | kick + crash |

Native charts are under `corrected-drafts/white-waves/chart.bsm` and
`corrected-drafts/death-before-dishonor/chart.bsm`. Audio companions were copied
and hash-verified. Original drafts and predictions remain untouched. Only these
three explicit operations were applied: remove one HH in each song, and relabel
the first WHITE WAVES cymbal to China. Note totals become 1,844 and 1,077. All
other notes, velocities, and surviving timestamps are unchanged. Earlier Death
Before Dishonor HH predictions remain unresolved; the user's correction does not
validate them.

`feedback.json` retains the user statements, timestamp clarification, original
chart hashes, exact edit selectors, and evidence limits. `corrected-drafts/manifest.json`
records output/copy hashes. `apply_song_feedback.py` refuses existing destinations,
changed source-chart hashes and ambiguous/missing edit targets. It never learns
a global rule from a local correction. Twenty-seven focused tests pass.

The actual C# BeatmapLoader accepts both packages, retaining China and kick+crash
respectively. China is recognized as the China category and maps away from HH.
The existing component-based layout assigns generic crash and China to the same
lane when both are present; distinct cymbal-lane presentation is **not** verified.
The initial stricter lane check failed for this reason, preserved in `native-check.log`.
The final semantic/load check is `native-check-final.log`. No product layout code
or default settings were changed.

`review/review.html` shows the exact before/after instruments with original mix,
estimated drums, speed/loop controls and corrected chart links. Serve this scoped
directory with `tools/recovery/serve_review.py --root <directory> --port 8773`.
The prior ports 8771/8772 still show the original model comparison, not these edits.

## What the model actually did

This was not solely the previously disclosed broad-family alias limitation:
both corrected entrances had an **extra predicted HH alongside CY**. The ADTOF
reference has only five broad output classes and cannot identify China separately
from other cymbals; that specific identity comes from the user.

At WHITE WAVES 1.000 s, all three ADTOF input variants produced an HH/CY pair
(full-mix HH is at 0.990 s). At Death Before Dishonor 8.750 s, full-mix predicts
kick+CY without HH; both separated variants add HH. This directly implicates
input-dependent classifier/peak-picker output in the latter observed error, but
does not establish whether separation introduced a particular acoustic artifact.

Saved activation maxima within +/-20 ms of the selected times:

| Song | Input | HH activation | CY activation |
|---|---|---:|---:|
| WHITE WAVES | full mix | 0.3052 | 0.7529 |
| WHITE WAVES | mono separation | 0.2986 | 0.7440 |
| WHITE WAVES | stereo separation | 0.2770 | 0.7632 |
| Death Before Dishonor | full mix | 0.1145 | 0.8322 |
| Death Before Dishonor | mono separation | 0.4010 | 0.7793 |
| Death Before Dishonor | stereo separation | 0.3861 | 0.8082 |

HH threshold is 0.22; CY threshold is 0.30. These are uncalibrated model outputs,
not probabilities of musical correctness. Evidence: `opening-model-observations.json`.

A single fixed diagnostic removed HH predictions within one 10 ms model frame
of a CY prediction, using saved seven-track stereo predictions. It reproduced the
previous baseline and rechecked annotation hashes. Of 14 removals, the score change
was **eight fewer false positives but six fewer true positives** at both tolerances:

| Tolerance | Before P/R/F1 | After P/R/F1 |
|---|---|---|
| 50 ms | 0.8431 / 0.7359 / 0.7859 | 0.8458 / 0.7334 / 0.7856 |
| 25 ms | 0.8170 / 0.7131 / 0.7616 | 0.8196 / 0.7107 / 0.7613 |

**Reject the blanket suppression rule.** No threshold search or application-default
change followed. This is the existing development diagnostic with unknown training
overlap, not independent full-song accuracy. The same rule nominates 10 WHITE WAVES
and 30 Death Before Dishonor candidate pairs; only the two explicitly identified
events are corrected. Do not relabel all candidates as errors. Evidence:
`co-detection-diagnostic/metrics.json` and `tools/recovery/probe_cymbal_hihat.py`.

## User proposal: benchmark against existing Clone Hero drum charts

The user accepted this direction on 2026-10-14. The session-ready continuation
is recorded in `NEXT_SESSION_CLONE_HERO_BENCHMARK.md`; acquisition and evaluation
of the proposed chart batch have not begun.

Recommendation: **make curated full-song chart comparisons the next evaluation
track**, keeping the two m!sa songs as acceptance examples. The user should not
have to author entire drum maps from scratch. Use human-authored charts to nominate
errors at scale, and audit selected passages before calling them verified truth.

This approach has direct research precedent: ADTOF's authors describe collecting
rhythm-game charts, converting them to Phase Shift format, and cleaning them into
drum-transcription datasets. Our reference is a PyTorch port with converted original
weights. Therefore a random collection of older community charts is **not automatically
independent** of the reference model's training data. Provenance and overlap checks
are required before a held-out accuracy claim. [ADTOF author repository](https://github.com/MZehren/ADTOF),
[reference-model repository](https://github.com/xavriley/ADTOF-pytorch).

Chart extraction is practical: Clone Hero song packages contain `notes.chart` or
`notes.mid`, audio, and `song.ini`. The task is parsing structured note/timing data,
not reading notes from gameplay screenshots. [Official song-package documentation](https://wiki.clonehero.net/books/clone-hero-manual/page/adding-custom-songs).

Pro Drums distinguishes pads/cymbals, but game representations remain limited.
The official guide maps both closed and open hi-hat inputs to the yellow cymbal;
standard play is not a source of reliable hat openness or arbitrary cymbal subtype.
Do not infer China solely from a lane color. [Official MIDI mapping guide](https://wiki.clonehero.net/books/guitars-drums-controllers/page/midi-drums),
[supported drum modes](https://wiki.clonehero.net/books/guitars-drums-controllers/page/drum-faqs-and-troubleshooting).

### Concrete first comparison batch

1. Select a small set of complete, human-authored Expert Pro Drums charts with
   known author/version and matching original audio. Start with 3 development songs
   and 2 reserved evaluation songs, including dense hats, cymbal changes and tom
   fills. These counts are an operational starting point, not statistical sufficiency.
2. Preserve each package and hashes. Inspect the actual drum part, tempo map,
   offsets, pro-cymbal markers, 2x kick and documented omissions. Use an established
   parser where practical, with version/license recorded; do not guess format codes.
3. Decode the chart's own matching audio. Verify leading silence, offset and
   timing at beginning/middle/end. Do not align AI notes to reference notes in a
   way that conceals timing errors. Record any independently justified alignment.
4. Run the same fixed audio-to-chart candidates. Compare one-to-one at 25/50 ms:
   precision/recall, extra/missed notes, family substitutions, and timing distributions.
   Report per-song and per-family results, not only an aggregate score.
5. Keep **chart agreement** separate from **audio-audited note accuracy**. Score
   exact instruments only when the chart actually identifies them; retain ambiguous
   cymbals/pads as ambiguous. Audit short disagreement excerpts rather than asking
   the user to chart the whole song.
6. Reserve evaluation songs before tuning; check duplicate recordings, alternate
   chart versions and model-training overlap. Unknown overlap remains explicitly
   diagnostic. Retest WHITE WAVES and Death Before Dishonor after a measured change.

No Clone Hero corpus has been acquired or evaluated yet. A read-only query of
the existing PC inventory found no uncompressed `notes.mid`/`song.ini` song library;
the five `.chart` matches are unrelated NVIDIA files. This is not an exhaustive
current absence claim: that snapshot covers C:/E:/F: with recorded exclusions,
does not cover the later-reconnected D:, and this query did not inspect archives
or `.sng` packages. Evidence: `clone-hero-local-inventory.json`.

Do not bulk-download or retrain before this bounded comparison identifies a
specific error worth changing. Preserve D:/F: as read-only. All new evidence above
is on C:, with no model, dataset, original chart or original audio overwritten.
