# Visual baseline diagnosis — 2026-10-16

The three failed 1080p playback comparisons from the full-song practice audit do
not show a regression after the baselines were committed. The committed baselines
are inconsistent snapshots taken at different points in the work that became one
commit (`5d47309`, 2026-05-13). One capture (2D) also depends on where the
physical mouse cursor happened to be. No baseline, threshold, application source
or default was changed.

Evidence root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-visual-baseline-diagnosis-01`.
Read `protocol.json` (frozen before native runs, hash in `evidence/protocol.sha256`),
`evidence/baseline-measurements.json`, `evidence/native-run-summary.json` and
`evidence/counterfactual.patch`.

## What was established

- No desktop commit follows `5d47309`; `desktop/` and `shared/` have no working-tree
  changes; the three baseline PNGs are blob-identical to HEAD. All 376 desktop/
  shared/script files in the reused sandbox are byte-identical to the checkout.
- A Python reimplementation of `VisualDiffComparer` reproduces the prior changed
  pixel counts exactly (130,571 / 637,696 / 23,201) and mean deltas within 1e-13.
- Fresh native control captures reproduce the failures: manuscript identical to the
  prior capture (0 changed pixels), 2D 0.0099% and 3D 0.32% run-to-run difference.
- `5d47309` changed three things that set the visible note window: it added
  `remapManualZoomForApproachDuration`, changed auto-zoom constants, and lowered
  `BaseVisibleMeasures` from 2.0 to 1.40. At the default zoom 1.0 the remap returns
  **2.9722**, not 1.0. In-code comments still say 1.0x should match the map's pacing.

| Scene | Control (current code) | Remap neutralized (sandbox-only patch) | Cause |
|---|---:|---:|---|
| Manuscript | .011189 FAIL | **.004272 / .000362 PASS** | Baseline captured without the remap |
| 2D | .307167 FAIL | .351795 FAIL | Baseline has the hover toolbar; 92.6% of changed pixels are inside it |
| 3D | .061656 FAIL | .068098 FAIL | Baseline predates several 3D changes (hit line/strike rail, window) |

Manuscript eighth-note spacing: pre-commit baseline 170.5 px, committed baseline
152.0 px, current capture 459.75 px (3.02x; predicted 2.97x), remap-neutralized
capture 152.0 px. The committed 2D baseline already reflects the remap: the current
2D look-ahead is about 2800 ms / 5.13 = 546 ms at 120 BPM, measured 544 ms.

The playback toolbar becomes visible only through `OnHover`. The capture harness
ignores tablet, pen, joystick and touch input but not the mouse, so the real cursor
position decides whether the toolbar appears. It is visible only in the committed 2D
baseline and in none of the nine current captures. The remaining 2D difference
outside the toolbar is grid lines shifted by 1–7 px (about a 1% time-scale change)
and a 1-px header text shift.

The committed 3D baseline closely resembles the pre-commit 3D baseline: notes run
onto the receptor pads and there is no strike rail. Current captures have a raised
strike rail. The remap is not the main 3D cause; neutralizing it makes 3D slightly
worse. The exact intermediate 3D code state was not reconstructed.

## Decisions needed before any baseline refresh

1. **Intended default zoom (product decision).** At default zoom the current code
   shows about 0.55 s of look-ahead in 2D/3D at 120 BPM, about one beat. This may be
   too short for learning full songs, or it may be intentional. The code comments and
   the remap disagree. This is a usability question for the user, not a test fix.
2. **Deterministic toolbar state (harness fix).** Ignore the mouse handler during
   capture, or force a known toolbar state, then decide whether baselines show it.
3. Only after 1–2: regenerate all Playback/Editor baselines from one code state in
   one run and verify compare mode passes. Editor baselines from the same commit were
   not examined here and may share the problem.

## Full-song screenshot review

All 18 WHITE WAVES / Death Before Dishonor captures from the prior audit are now
inspected (`evidence/song-screenshot-review.json`). Drawn notes agree with the
recorded visible-note data at the openings and midpoints; all six end captures are
empty, as expected (last notes 10.1 s and 12.3 s before the end). Both user
corrections render: WHITE WAVES China at 1.000 s and Death Before Dishonor
kick+crash at 8.750 s.

Suspected display problems, not yet fixed or confirmed as defects:

- **Short look-ahead.** No view ever draws more than about 0.5 s of upcoming notes
  (about one beat). In 2D, 0.5 s before the Death Before Dishonor kick+crash, the
  field is still empty. This follows from the zoom remap above.
- **3D China lane labeled "CR".** The seven-lane preset shares lane 6 between Crash
  and China, and the 3D label code checks Crash first. 2D labels the same lane
  "China". 3D header pill colors also differ from the note colors in the same lane.
- **Manuscript ruler offset.** The "Now" tick is not at the green playhead that notes
  are aligned to. Offsets range from about −175 to +408 px; meaning not verified in code.
- **Manuscript staff truncation.** In Death Before Dishonor's opening, the staff lines
  stop near x=868 while the upcoming kick+crash is drawn near x=1630.
- **Manuscript label overlap.** At the WHITE WAVES ending, "M117"/"+2b" overlap the legend.
- Previously known: the Back button covers the start of the title.

No listening was done: this assistant cannot hear audio. The offline packet
`review/index.html` in the full-song audit root is still the place for targeted
listening judgments by the user.

Limits: the counterfactual identifies the cause of the manuscript difference; it
does not say which zoom behavior the product should have. Cursor position was not
controlled or moved. Visual results say nothing about transcription accuracy.
