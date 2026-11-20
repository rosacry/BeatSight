# Cymbal combine and ghost-note rules for phase 2 (2026-10-24, Claude)

Root `C:\Users\10ros\BeatSight-Recovery\2026-10-24-cymbal-ghost-rules-01` (CPU only, inputs read only, no
training, app unchanged). Motivated by the user's listening feedback
(`2026-10-24-listening-feedback-01/user-feedback.md`): ride and crash together, ride over-played, ghost snares
shown as full notes. `protocol.json` was written and hashed (`evidence/protocol.sha256`, 10:46) before any
result; validation chose each setting; each test set was scored once (`score_once.py`). The base decode is the
app's current 16-class decode (per-class peaks + hi-hat rule W20); its test rows equal yesterday's exactly
(eval 139/139, chart tier 202/202).

## Rule A: one cymbal event per 20 ms

Cymbal peaks within 20 ms of the retained left peak merge into one event with the strongest class. Variants:
ride+bell, ride+bell+crash, all five cymbals.

Validation (686 synthetic items, 106 chart-validation songs, `evidence/validation.json`): all three eligible;
the frozen rule chose **C20-all** (mean cymbal F1 .748). Chart-validation cymbal F1 .826 -> .836 (ridecrash
.836, all .836) with 39% fewer cymbal notes; synthetic cymbal F1 .640 -> .660 (ridecrash .651).

Test, once (`results/compare-C20-all/comparison.md`, frozen `compare_candidates.py`, vs ADTOF):

| Test set | ADTOF | base | C20-all | C20-all vs ADTOF [95%] |
|---|---|---|---|---|
| A real held out (23) | .643 | .608 | .609 | -.035 [-.094, +.021] |
| B ENST/MDB, overlap possible (48) | .829 | .805 | .808 | -.021 [-.050, +.010] |
| C commercial charts (2) | .867 | .893 | .897 | +.029 [-.002, +.065] |
| D synthetic drums (26) | .721 | .802 | .803 | +.082 [+.049, +.123] |
| E electronic kit (40) | .730 | .844 | .844 | +.115 [+.073, +.152] |
| Chart tier (202 songs) | .874 | .898 | .900 | +.026 [+.019, +.033] |
| Chart tier, cymbals (family) | .727 | .808 | .818 | +.091 [+.070, +.115] |

On the chart tier it removed 1,610 false cymbal presences and no correct one (TP 51,207 both).

On the user's songs (saved activations, `evidence/user-songs-cymbal-counts.json`): rides WHITE WAVES 329 -> 127,
Death Before Dishonor 173 -> 83, The Sin and the Sentence 531 -> 147, Bleed 353 -> 101. C20-all also removes
every China (Sin 15, DBD 3, Bleed 2 -> 0) and splash; C20-ridecrash makes the same ride/crash cuts and keeps
them. The user said China is already under-detected. C20-ridecrash was not separately test-scored; it merges a
subset of what C20-all merges, and equals it on chart validation.

## Rule B: ghost snares from onset strength

Ghost when a predicted snare's onset strength (input-feature spectral flux) is below T x the song's median;
velocity 0.25 (the app draws < 0.35 faint and smaller), others 0.8.

Validation (42 songs with >= 20 charted ghosts): AUROC .89; the frozen rule chose **T = .75**, the edge of the
pre-registered grid (F1 .678, precision .62, recall .75); on songs without ghost marking it would call 22% of
snares ghosts. Test, once (`results/ghost-test.json`, 73 held-out songs): **F1 .604, precision .515, recall
.729, AUROC .855**: about half the notes it would show as ghosts are charted as normal hits.

Stricter thresholds trade recall for precision (validation: T .45 precision .82 recall .40; T .35 .87/.29);
those were not test-scored and any new choice is post-test. A learned ghost output trained on the 188,000
ghost-flagged chart notes (run 2) is the better route.

## User decision and what changed (2026-10-24 ~12:00)

The user chose C20-ridecrash for the app and to leave ghost notes for a learned output in run 2.
`ai-pipeline/adtof_engine/fine.py` now applies `combine_cymbals` (RD, RB, CR within 20 ms) after the hi-hat
rule on the `--fine-model` path (engine version `beatsight-16class-3`); ADTOF stays the default. Tests:
23/23 (`tests/test_adtof_fine.py`, `tests/test_adtof_engine.py`), including equality with `rules.py`
C20-ridecrash on random activations. Comparison maps: `2026-10-24-model-comparison-03` (rebuilt from saved
activations; checks in `evidence/rebuild.json`).

## Decisions that were put to the user

- Cymbal rule in the experimental `--fine-model` decode: C20-all (protocol choice) or C20-ridecrash (keeps China).
- Ghost display: wait for a learned ghost output in run 2, or enable a strict loudness threshold now knowing it
  finds fewer ghosts and is not independently tested.
- Run 2 root cause: the chart noisy-OR group loss never penalizes two members firing together (hi-hat and
  cymbal double firing); add a group exclusivity term.
