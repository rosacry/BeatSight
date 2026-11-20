# Recovery and evaluation tools

Read the recovery audit (`docs/RECOVERY_AUDIT_2026-10-13.md`) first. These tools use new output locations,
never clear a folder, and do not require the lost training corpus. Generated
charts are unreviewed drafts. No tool here uploads audio or trains a model.

From `C:\github\BeatSight`:

```powershell
py -3.11 tools/recovery/transcribe.py --input 'C:\path\song.flac' --output-dir 'C:\path\new-review-folder' --dry-run
py -3.11 tools/recovery/transcribe.py --input 'C:\path\song.flac' --output-dir 'C:\path\new-review-folder'
```

Use `chart.bsm` with its adjacent audio in BeatSight. `run.json` records hashes,
settings, environment, and completion/failure. A present chart alone is not a
successful run. The default faithful profile retains onset timing and disables
some musical rewrites; it has not demonstrated better F1 than `--profile legacy`.
Both use the same inherited classifier, including its legacy section rule.

The following examples reproduce local research. The evaluation data and reference
checkout were acquired separately and are not bundled. Their individual terms
apply; no third-party models have been packaged into the app.

```powershell
$evidenceRoot = 'C:\Users\10ros\BeatSight-Recovery\2026-10-13'
$tracks = @('MusicDelta_80sRock', 'MusicDelta_SpeedMetal', 'MusicDelta_CoolJazz')

# Full mix -> BeatSight chart -> one-to-one event matching.
py -3.11 tools/recovery/evaluate_mdb.py --dataset "$evidenceRoot\benchmark" --output-dir "$evidenceRoot\new-legacy-evaluation" --profile legacy --tracks $tracks

# Change just the section rule, sharing separated audio between each pair.
py -3.11 tools/recovery/ablate_sections.py --dataset "$evidenceRoot\benchmark" --output-dir "$evidenceRoot\new-section-experiment" --tracks $tracks

# Reference model; source revision and weight SHA-256 must match the audited values.
.\.venv-recovery\Scripts\python.exe tools/recovery/evaluate_adtof.py --reference-repo "$evidenceRoot\reference-adtof" --dataset "$evidenceRoot\benchmark" --output-dir "$evidenceRoot\new-adtof-evaluation" --tracks $tracks

# Same reference model after Demucs separation; saves derived stems and their hashes.
.\.venv-recovery\Scripts\python.exe tools/recovery/evaluate_adtof.py --reference-repo "$evidenceRoot\reference-adtof" --dataset "$evidenceRoot\benchmark" --output-dir "$evidenceRoot\new-adtof-separated-evaluation" --tracks $tracks --separate-drums

# Re-score the original named recovery experiments without rerunning inference.
py -3.11 tools/recovery/rescore.py --root $evidenceRoot --output "$evidenceRoot\new-rescore.json"
```

The six-family mapping follows MDB Drums Table 1: kick KD, snare SD, hi-hat HH,
toms TT, cymbals CY, and side-stick/other percussion OT. ADTOF's broad hi-hat and
cymbal outputs are kept broad; the evaluator does not claim closed/open or ride/crash.
Evaluation is on detected/exported onsets, not ground-truth onsets supplied to a
classifier. Matching is one-to-one within 50 ms. Training overlap is unknown and
these three songs contain no annotated toms, so they are diagnostics only.

`rescore.py` preserves earlier score files and records prediction/annotation hashes.
New experiments should record full per-track and per-family results, and should
not change thresholds based on the eventual held-out test set.

## Full-song comparison and review

The current song report is
`docs/WHITE_WAVES_AND_DEATH_BEFORE_DISHONOR_2026-10-14.md`. All song outputs
must be in a new C: experiment directory. These examples require the existing
pinned reference checkout and local separator weights; no training is involved.

```powershell
$songRoot = 'C:\Users\10ros\BeatSight-Recovery\my-new-song-experiment'
$reference = 'C:\Users\10ros\BeatSight-Recovery\2026-10-13\reference-adtof'
$sourceAudio = 'C:\path\song.flac'
.\.venv-recovery\Scripts\python.exe tools/recovery/transcribe.py --input $sourceAudio --output-dir "$songRoot\inherited-faithful"
.\.venv-recovery\Scripts\python.exe tools/recovery/transcribe_reference.py --input $sourceAudio --output-dir "$songRoot\reference-comparison" --reference-repo $reference --title 'Song' --artist 'Artist'
.\.venv-recovery\Scripts\python.exe tools/recovery/probe_stereo.py --root $songRoot --reference-repo $reference
.\.venv-recovery\Scripts\python.exe tools/recovery/package_song.py --root $songRoot --stereo --bookmarks 10 20
.\.venv-recovery\Scripts\python.exe tools/recovery/review_song.py --root $songRoot --output-name review-v2
py -3.11 tools/recovery/serve_review.py --root $songRoot --port 8771
```

Open `http://127.0.0.1:8771/review-v2/review.html`. The range server binds to
loopback only and does not upload audio. Keep it running while using the page.
For PCM16 FLAC with the observed native duration discrepancy, `package_song.py
--pcm-wav` creates and sample-verifies a lossless playback WAV while preserving
the original. It is not a general-purpose conversion flag.

Native `hihat_closed`, `tom_mid`, and `crash` are broad-family display aliases.
The scripts do not infer articulation, dynamics, or a verified beat grid. Agreement
and spectral-flux distances are review aids, never accuracy measurements.
`probe_song_gate.py` compares a saved-stem section-gate pair without changing app
defaults. `evaluate_stereo.py` repeats the annotated diagnostic with spatial input
retained; existing development-set limitations still apply.

## Applying specific listening feedback

`apply_song_feedback.py --feedback <feedback.json> --output-dir <new-C-directory>`
creates separate native packages from hash-bound chart sources. Each edit must
identify one exact time/component pair and explicitly remove or relabel it. It
preserves all other notes and records user evidence separately from predictions.
See `docs/OPENING_CORRECTIONS_AND_CHART_BENCHMARK_2026-10-14.md` and its linked
feedback file for the two applied opening corrections. `probe_cymbal_hihat.py`
tests a fixed HH/CY overlap suppression rule on existing predictions; that rule
lost valid annotated hits and was rejected. Do not apply it to other song notes.

## Curated chart-reference comparison

The initial five-song experiment is documented in
`docs/CLONE_HERO_BENCHMARK_2026-10-14.md`. `ChartReference/` wraps pinned YARG.Core;
`clone_hero_reference.py` prepares original charts and package mixes in a new C:
folder. `benchmark_clone_hero.py` runs fixed audio-only candidates, and
`report_clone_hero.py` rescales neither audio nor timestamps: it scores preserved
predictions with the explicit policy in `clone_hero_scoring.py` and builds the
local review. `audit_chart_alignment.py` screens independent acoustic alignment.
Read the report's reference-admission flags before interpreting any F1. These
helpers do not promote models or alter the desktop application. See
`ChartReference/README.md` for the measured parser fix and integration tests.

`audit_clone_hero_reference.py` independently compares decoders, integrates raw
`.chart` BPM events, and measures original-mix attack timing under a frozen gate.
`build_reference_admission_review.py` creates short source-traceable listening
passages and optional snare-click trials, without model event overlays. The
October 15 audit rejected automatic offset admission; trial clicks are not
corrected references. Read `docs/CLONE_HERO_REFERENCE_AUDIT_2026-10-15.md` for
results, the verbatim user guitar-hit observation, and reproducible commands.

## Original-source chart controls

`probe_reference_attack_controls.py` contrasts Adapt's reconstructed original
mix, author drum stem, other stems and silence using the unchanged prior timing
screen. `--extend-full-song` adds all snare anchors in fixed bins without fitting
a reference offset. `audit_cymbal_similarity.py` screens original-drum waveform
reuse across chart cymbal pads; similarities are review cues, not labels.
`probe_chart_original_drums.py` runs one pinned ADTOF original-drum input probe
and checks that saved baseline scores reproduce. It is diagnostic only; no
parameter tuning or promotion is allowed from this reserved-song probe.

See `docs/CLONE_HERO_SOURCE_CONTROLS_2026-10-15.md` for results, provenance,
limits and commands using a fresh C: directory. The focused suite includes
`test_reference_attack_controls.py` for source reconstruction, hash rejection,
window/silence admission and known waveform controls. Existing artifacts remain
read-only; the full-mix screen failure is not proof of a bad reference.

## Fixed development input and decoder checks

`probe_residual_input.py prepare` freezes the 25% residual-audio contrast using
saved stereo-separation stems, verifies provenance/baseline reproduction, and
writes exact float inputs in a new C: directory. `run` verifies that frozen state
and performs only the new candidate inference. Repeated runs cannot overwrite
completed/partial output. `analyze_residual_input.py` exports matched-target
gains/losses and activation failure buckets without tuning.

The candidate failed; do not repeat it at new fractions. The raw full-mix arm
already exists for all seven recordings. See
`docs/MDB_RESIDUAL_INPUT_AND_DECODER_AUDIT_2026-10-15.md` for evidence and commands.
`decode_adtof_reference.py` provides a recovery-only fixed decoder checked against
primary madmom v0.16.1 functions. It leaves the pinned checkout and old exports
unchanged. Its synthetic and cached-chart parity does not establish frontend or
model parity. Tests are `test_residual_input.py` and
`test_adtof_reference_decoder.py`.

## External-drive recovery utilities (preservation only, historical tools)

`inventory_pc.py` creates a metadata inventory, including ignored files and logged
exclusions. `build_data_ledger.py` combines original provenance with the private
inventory checks; it requires a new output JSON. The October 14 inventory and
evaluation plan under `docs/` explain the findings and their limits.

`preserve_external_survivors.py` reads the explicitly inventoried D: Recycle Bin
WAVs and cold-storage checkpoints. It requires a new C: output directory, never
restores anything in place, and verifies archived/copied bytes. Do not rerun it
into a completed or partially written directory. A ZIP's presence alone does not
mean preservation passed: require the matching verification JSON.

`salvage_lakh.py` copies and hash-verifies a damaged archive, inflates readable
bytes into a new C: directory, and salvages only safe-named MIDI members matching
the original MD5 filename. It never extracts arbitrary archive paths. It records
gzip truncation, rejects mismatching members, and verifies its result ZIP. Hash
identity does not establish valid MIDI or correct drum annotations. This tool is
for the known local damaged LMD archive, not a general hostile-archive extractor.
