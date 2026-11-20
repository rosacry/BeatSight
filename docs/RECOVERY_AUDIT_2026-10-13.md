# BeatSight recovery audit — 2026-10-13

## November 6 run-2 setup (Claude)

User decisions: drop "percussion" from app charts; train on the Bleed chart. Run-2 protocol frozen and hashed before
any run-2 training on real data; a CPU smoke test found that the ADTOF initialisation ties all cymbal (and hi-hat)
members, so an unwarmed exclusivity term would always favour ride; fixed with a 10,000-step warm-up before freezing.
Pipeline v8 (run 2 only) prepared and held paused for the user's start. App change: `adtof_engine/fine.py` drops OT
(engine beatsight-16class-4); not committed. The user started run 2 at 18:45 (set_state + task); P2/P3 scripts
were written while it trained, smoke-tested only on a 4-step stand-in checkpoint (outputs in temp/), and hashed at
18:50 before any phase2-02 checkpoint was scored.

## November 4 resume without D: (Claude)

After 10 days paused (no other writer; Codex open in an unrelated folder), the user asked to proceed. D: was not
connected. Pipeline v6 removed the step-1 D: wait (only the finished mixture cache needs D:), but v6 still stopped
at the prelaunch check, whose manifest exclusion guard reads the E-GMD index on D: (an indirect dependency I missed
by searching only the shell script). v7 runs that check only while phase-1 training is unfinished; every other
remaining step was checked to read only C:. Resumed corpus-v2 at 18:43 under the scheduled task (3,993/6,423).
Run-2 training will need D: for the same guard. ~19:00 the user reconnected D:; the E-GMD index is present and the
prelaunch check re-run read-only passes with the original counts. Paused 2026-11-05 02:55 for the night at the
user's request (set_state first, then bash, then the job): corpus-v2 5,374/6,423, 63 by-design refusals, the
in-flight chart left only a temp folder. Resumed 2026-11-05 14:38 at the user's request after a 14:33 reboot (the
logon run stayed paused as designed); the interrupted chart was redone, no new failures. Paused again 2026-11-05
20:30 at the user's request with 27 charts left (6,333/6,423 + 63 refusals); same order, no partial outputs.
Resumed 2026-11-06 02:51 at the user's request; interrupted chart redone, no new failures. Corpus-v2 processing
finished ~03:03; the user powered the PC off at 04:38 (clean, event 1074) during extended QC, which writes its one
output at the end (none partial). The logon task restarted v7 at 15:06 as designed; QC reruns from scratch (~1.6 h
of CPU work lost, nothing corrupted). "All done" at 17:19 (exit 0): keep rule v1 kept 3,774/6,360 charts
(241.6 h); labels built for all 3,774 (277 held out, 0 failed).

## October 24 Oblivion chart check (Claude)

The user's two Discord/Drive zips were treated as untrusted: listed, extracted only after a zip-slip check into
new folders, unexpected file types skipped, nothing executed. First zip: guitar-only chart (no drums). Second:
Ziggy's pro-drums chart, processed with corpus v2's own functions (CPU) and scored with the frozen tools. Phase 2
beats ADTOF on the chart's audio (.899 vs .840); the user's MP3 of the same recording loses most kicks in dense
double-bass sections (.757). Report: `docs/OBLIVION_CHART_CHECK_2026-10-24.md`. Earlier in this thread I
reported "no Oblivion drum chart exists" from Encore/RhythmVerse searches; that was true only for those sites.

## October 24 GPU reset stop (Claude)

User-initiated clean restart 12:45; auto-resume relaunched pipeline v5 12:49; corpus-v2 processing exited 1 at
12:54:10 together with an NVIDIA driver reset (nvlddmkm 153). Verified no partial outputs (chart
2eb457579635648445a7c015d29444c1: temp folder only, reprocessed successfully after restart). Restarted 15:53
via the scheduled task after the user reported the stop; 6 failure records are the known refusals (5 five-lane,
1 chart longer than its audio). Lost ~3 h of GPU time.

## October 24 cymbal and ghost-note rules (Claude)

User listening feedback recorded (`2026-10-24-listening-feedback-01`). New root `2026-10-24-cymbal-ghost-rules-01`
(CPU, read-only inputs, no training, app unchanged): protocol hashed before results; validation chose C20-all and
ghost T=.75; test sets scored once. Base decode rows equal the previous day's exactly. Cymbal rule: chart tier
+.026 vs ADTOF (was +.024), no tier worse; but it removes every China on the user's songs. Ghost rule: test
precision only .515. An account switch at ~11:12 ended the validation wrapper shell after python had finished
(`evidence/notes.txt`); the pipeline under Task Scheduler was unaffected. Corrected record: the 10-23 diagnosis
protocol's hash changed by my own timestamp-text fix after hashing; noted in its `evidence/protocol.sha256`.
Report: `docs/CYMBAL_GHOST_RULES_2026-10-24.md`.
Follow-up (user chose C20-ridecrash): `adtof_engine/fine.py` `combine_cymbals`, engine version -3, 23/23 tests.
`2026-10-24-model-comparison-03` rebuilt from saved activations: rule-off notes equal comparison-02 on all four
songs; app decode equals the tested research rule; Chinas/splashes kept. An error of mine: the first launcher was
written with printf, which consumed the backslashes; I deleted that broken file and rewrote it (verified CRLF text).

## October 23 tier-B drop diagnosis and hi-hat decode rule (Claude)

New root `2026-10-23-tierb-drop-diagnosis-01` (CPU, inputs read only, no training, pipeline v5 untouched).
Re-run checks: phase2-01 on CPU within 2 events per tier of the stored GPU eval report (10/139 items
differ by threshold-edge rounding); ADTOF beatmaps rescore to the stored counts on 139/139; greedy and
assignment matching agree. Diagnosis: 1,572 of 2,432 tier-B hi-hat false hits are same-stroke sub-class
duplicates; the "other" class has 2,621 false hits. A hi-hat family combine rule was pre-registered and
hashed (`protocol.json`, 20:05) before validation; validation alone chose W20; the test sets were scored
once: tier B -.024 [-.053, +.006], chart tier +.024 [+.018, +.031]; the no-rule control reproduces the
stored comparison exactly (chart tier rows 202/202 identical). Limits: the idea came from tier-B error
analysis; m!sa cross-family errors are unchanged; not listened to; not promoted; app decode unchanged.
Report: `docs/TIERB_DROP_DIAGNOSIS_2026-10-23.md`.
Follow-up (user approved): rule added to `ai-pipeline/adtof_engine/fine.py` (`--fine-model` only); 21/21
engine/fine tests pass; `test_process_pipeline.py::test_process_audio_creates_parent_directories` failed
only because the GPU was hidden for the run (legacy checkpoint saved on CUDA); not rerun on the busy GPU.
New root `2026-10-23-model-comparison-02`: reproduces comparison-01 exactly; app rule equals research rule.
Error found: `os.environ["CUDA_VISIBLE_DEVICES"] = ""` unsets the variable on Windows, so its separation
(and comparison-01's) used the GPU; ~90 s overlap with pipeline v5, no failures. Fixed to "-1".

## October 18 crash recovery (Claude)

Unexpected shutdown ~18:57 (Kernel-Power 41, no driver/WHEA errors). Verified: 175 cache items
since 17:54 (hashes match), 2,317 corpus-v2 downloads (hashes match), 20 recent text files (no
NULs). Repaired: corpus-v2 `downloads.jsonl` NUL tail (damaged copy kept), 90 unverifiable files
quarantined (moved, not deleted) and re-downloaded. An error of mine during the repair (CR CR LF
log endings) broke one download pass; fixed byte-exact. D: missing after reboot made the cache
fail; the old chains then ran corpus-01 processing early for ~12 min (stopped; outputs valid).
Replaced by the strict-order `run_remaining_pipeline.sh`. Evidence:
`chart-corpus-02/evidence/crash-recovery-01.json`, `crash-verify-01.json` (both roots).

## October 16 cache, chart pilot and fine-tune chains (Claude, in progress)

Roots `2026-10-16-feature-cache-01`, `2026-10-16-chart-pilot-01`, `2026-10-16-finetune-01`,
`2026-10-16-eval-features-01` (all new C: roots; D: read-only). User approved the
500-chart pilot (downloads from files.enchor.us), the cache and fine-tuning. Three
concurrent htdemucs jobs thrashed the GPU (4.8x vs 10.5x): smoke run moved to
`evidence/aborted`; GPU work serialized. Baseline gate on float16 eval features: A/B/C
identical, D −2 tp, E −1 tp. Isolated: CPU and GPU stems identical, float32 matches the
app run exactly, float16 alone flips 2/381 and 1/1,243 notes. Amendment 01 (hashed):
float32 eval features for gating; float16 result kept as `baseline-reproduction-float16.json`.
Smoke `runs/smoke-02` (600 steps): loss .109→.088, resume from step 400 works, validation
path checked on cached items. Unattended chains: `resume_after_pilot_eval32.sh`,
`after_caches.sh` (hashes in `finetune-01/evidence/protocol.sha256`). No candidate scored yet.
2026-10-17: drum-only cache 41,214/41,214 (0 missing; 300 random features shape/finite/sha OK).
Float32 gate passed (139/139 items identical to the app run). Pilot 499/500. Snare diagnosis
(ghosts 34.4% of misses vs 9.0% of matches) and ADTOF timing bias (A −2, B −3, D 0, E −2.6 ms)
motivated keep rule v1 (amendment 03, hashed): 344/499 charts kept, 22.57 h. No labels,
QC records, features or stems changed; failed partial extraction renamed, not deleted.
2026-10-17 04:09: user approved the corpus scale-up. New root `2026-10-17-chart-corpus-01`;
protocol and selection (4,560 charts from the pilot's frozen catalog, reproduced exactly)
hashed before the first request; 2-file test download parsed; full sequential download running.
06:13: 4,560/4,560 downloaded (18.54 GB, 0 errors, under the 25 GB cap); all sizes, hashes and
SNG parses verified. Processing waits for phase 1 (`process_after_phase1.sh`, `chain.log`).
2026-10-18: new roots `2026-10-18-chart-test-tier-01` (protocol, amendment 01 and scorer
hashed before any score; split rebuild test passes) and `2026-10-18-phase2-chart-labels-01`
(protocol hashed before the build; 344/344 pilot labels; integrity check 0 problems). Source
roots read only. ADTOF baseline on 26 held-out songs recorded; no candidate scored.

## October 16 training manifest v1 and dataset catalog (Claude)

Root `C:\Users\10ros\BeatSight-Recovery\2026-10-16-train-manifest-01`; read
`docs/TRAINING_MANIFEST_2026-10-16.md` and `docs/DATASET_CATALOG_2026-10-16.md`. Protocol
frozen before the builder. Only D:/C: reads; no downloads, separation of the full set or
training. 48,927 items listed, 48,830 usable (97 STAR validation mixes need STAR's MUSDB
mixing script). Labels via the eval-set taxonomy and ADTOF tables; Slakh sequence-key
events flagged (231,461), unmapped notes dropped (86,678). 21 tests pass; the eval set
re-verifies (994 files). Measured on three real items: htdemucs_ft 10.95–11.3x real time.
Plan corrected: ENST drummers 2–3 are excluded by the frozen file. Web research (STAR paper,
ISMIR 2025 limits study, chart indexes, MoisesDB, StemGMD, MDB repo, RBMA13) recorded with
judgments; the 2026 synthetic-data SOTA claim maps to ADT_STR, already rejected locally.

## October 16 frozen evaluation set v1 and training plan (Claude)

Root `C:\Users\10ros\BeatSight-Recovery\2026-10-16-eval-set-v1`; read
`docs/EVAL_SET_V1_2026-10-16.md`. Protocol frozen before building. Built from local
data only: 139 items, 2.28 GB; MDB families match earlier references, 6 ENST items are
bit-identical to the October 15 inputs; 342 sources (D: originals) re-hash unchanged and
2,972 prior-root artifacts verify. ADTOF overlap tiers come from the pinned ADTOF code
(fold 0 held out; checkpoint scenario spelling `adtofAll` not found in code; paper page
403). Baseline through the app-shaped CLI, 139/139 runs: A .643, B .829, C .867, D .721,
E .730 F1. Diagnostic: drummer 1 kicks are weak at the source (kick-mic attack median
10.8 dB vs 40.9/28.8 dB), which confounds the A/B gap. Derived exclusion of 31 MUSDB
folders (all STAR test songs plus MDB 80s Rock/Beatles/Punk). Plan rewritten after the
user's personal-use decision. No training, downloads or app changes.

## October 16 ADTOF engine integration (Claude)

ADTOF (stereo htdemucs_ft + Frame_RNN) is the app default; legacy is a fallback.
Read `docs/ADTOF_ENGINE_INTEGRATION_2026-10-16.md`; root
`C:\Users\10ros\BeatSight-Recovery\2026-10-16-adtof-engine-integration-01`. Protocol
frozen before runs; amendment 01 adds the audited seed 0 (unseeded first batch
.784356 kept), amendment 02 the UTF-8 launch fix (legacy failed 15/15 before it).
Seeded engine reproduces MDB .788049 and ENST .800204 exactly through the app-shaped
CLI; reserved CH .867158. Legacy .510970/.598113/.575854. Prior roots verified intact
(2,907 artifacts). Tests: 12 new engine, 302 pipeline (4 pre-existing failures
identical with original process.py), 539/539 desktop in a byte-identical sandbox.
EOL-only side effects of the edit tool were reverted line by line. Nothing committed.

## October 16 transcription-first priority (Claude)

The user set transcription accuracy on any song as the first goal and deferred all
UI/graphics/layout work, including the approved zoom restore. Evidence synthesis:
`docs/TRANSCRIPTION_ROUTE_2026-10-16.md`. Verified in source: the app's generate path
(`ai-pipeline/pipeline/process.py`) uses the inherited onset/classifier pipeline;
ADTOF appears only under `tools/recovery`. The local ADTOF port has no LICENSE file.
GPU was 81% busy with an unrelated mkai campaign. No code, model or chart changed.

## October 16 visual baseline diagnosis and full-song screenshot review (Claude)

Latest continuation: **The three failed 1080p comparisons are diagnosed; they are
not a regression.** Read `docs/VISUAL_BASELINE_DIAGNOSIS_2026-10-16.md`. Root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-16-visual-baseline-diagnosis-01`.
Protocol frozen before native runs. A Python comparer reproduces all three prior
changed-pixel counts exactly. Source is unchanged since baseline commit 5d47309;
the sandbox's 376 desktop/shared files are byte-identical to the checkout. Fresh
control captures reproduce the failures (run-to-run 0 to .32%). With only the
manual-zoom remap neutralized in a sandbox copy, manuscript passes (.004272 /
.000362) and its eighth spacing returns to the baseline's 152.0 px (current 459.75).
2D: 92.6% of changed pixels are the hover-only toolbar present in the baseline;
mouse input is not ignored by the harness. 3D: baseline predates several 3D layout
changes; the remap is not its main cause. Default zoom 1.0 now equals 2.9722x,
about 0.5 s look-ahead in all views. All 18 song captures inspected: notes agree
with recorded data; suspected display issues listed in the report. 978 prior-root
artifacts verified intact. No baseline, threshold, app source, chart or default
changed; no listening performed. Next: user decides the intended default
zoom/look-ahead; then a deterministic-toolbar harness fix and one-run baseline
refresh, or return to transcription work.

## October 16 shared Claude Code and Codex continuity

Previous continuation: **Shared Claude Code / Codex handoff installed.**
Read `docs/AI_HANDOFF.md` and `docs/AI_SWITCHING.md`. Both assistants use the same
checkout, recovery files and canonical skill files. 58 local skill packages
preserved (623 files,31,053,758 bytes);60 shared entrypoints include two new
continuation/handoff skills. Both discovery paths resolve to the same file;
all60 pass structural validation. Twelve checkpoint tests pass, including stale
state detection and preservation across assistants. The CLI launcher parses and
rejects a competing launcher before starting a provider. Existing app account
switching/settings/history are unchanged. No Claude model/API call was made.
New root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-claude-handoff-01`.
All3,652 prior artifacts are included in the preservation verification chain.
Read final verification/manifest for the executed hash audit. Conditional service
workflows do not migrate Codex tools/authentication; see AI-Shared/CAPABILITIES.md.
Original skills are archived; a first ZIP failed on pre-1980 timestamps and is
retained. `original-skills-02.zip` is the complete readback-verified archive.
The user keeps the existing Claude close/wait/reopen/log-out/in routine. Open
the SAME local BeatSight Code project and ask to continue from AI_HANDOFF.md.
Optional Start-Claude.cmd / Start-Codex.cmd use existing CLI accounts and normal
permissions. No automatic quota takeover or live-context transfer is claimed.
Next project work: in a NEW C: root, finish the saved full-song visual/listening
review and diagnose three failed visual comparisons. Full audio/all2,921 notes
load,18 sampled seek/play/pause checks pass,536 nonlive-visual desktop tests pass;
musical acceptance remains unproved. No models/charts/defaults changed. Prior
failed correction routes remain closed. D:/F: read-only; preserve all corrections,
Knuckles35 targets/repeated-tapping wording and ignored/untracked assets.

## October 16 full-song practice audit

Latest continuation: **Corrected full-song packages load and sampled transport
checks pass; musical accuracy remains unaccepted and three visual baselines fail.**
Read `docs/FULL_SONG_PRACTICE_AUDIT_2026-10-16.md`. Root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-16-full-song-practice-audit-01`.
2,673 prior artifacts preserved; 59 protocol entries, eight exact song files and
377 source/fixture copies. Complete audio durations 240.011610/204.963492 seconds;
all 1,844/1,077 notes retained. Eighteen seek/play/pause samples pass in three
practice modes; this is not uninterrupted playback or musical acceptance.
536/536 desktop tests pass with live visual tests disabled. Three separately
executed native baseline comparisons fail; no baselines/thresholds changed.
Eighteen song screenshots saved; only three inspected so far. Six fixed passages,
twelve exact clips and offline review/index.html are prepared, not listened to
or browser-tested. DBD HH at2.750/3.590s remains unresolved outside this packet.
User openings, Knuckles35 targets/repeated-tapping wording and all prior notes
are intact. No charts/defaults/application source changed; D:/F: read-only.
Next in a NEW C: root: finish visual/listening review and diagnose baseline
differences before any acceptance. Prior failed model/rule routes stay closed;
independent validation/full-song m!sa checks still gate promotion. The user now
requests a seamless shared Claude Code/Codex handoff; complete that first.

## October 16 isolated DrumSep routing/reconstruction control (hi-hat failure)

New root `C:\Users\10ros\BeatSight-Recovery\2026-10-16-drumsep-isolated-control-01`.
Read `DRUMSEP_ISOLATED_CONTROL_2026-10-16.md`. Initial bootstrap stopped when D:
was unavailable; the user reconnected it. Subsequent complete audit verified all
2,532 prior files with zero missing or changed. Failed bootstrap/interruption
record retained.101 existing source/docs archived before edits with exact readback.

Six already selected isolated dry stereo recordings and six annotations copied
byte-exact from D: to C:.78.28 seconds,13 HH and15 snare source labels. No mono
fold, normalization, gain/time shift or upstream separator.46-entry protocol
frozen before neural inference. Same native source/config/checkpoint/settings;
all319 tensors /109,378,624 values match.36 finite full-length stereo outputs
read back exactly.14.04 seconds neural execution; no package/model/data download.

Predeclared expected-stem dominance, target residual/input energy <=.25 and
off-target energy/input <=.10 apply to all six files and all28 fixed event
windows [-50,+500)ms. All three snare files and15/15 snare events pass. All three
HH files fail; only1/13 HH events passes. Nine HH events have the wrong dominant
output: eight snare, one tom. Drummer3's whole-file HH energy/input is.003094
while snare energy/input is.455956. No arbitrary tolerance alone explains the
family-routing failures. Source labels retained; acoustic purity not assumed.

Independent dot-product arithmetic reproduces34 rows,204 scalar comparisons,
six stem energies per row and all gates (maximum scaled error9.99e-16). Seven
fixed review cases have49 exact clips and six inspected waveform panels. No
auditory relabeling. Good aggregate reconstruction does not validate stem identity.
Close this native DrumSep hi-hat correction/reference route. Isolated-snare
success does not establish specificity when labeled HH also enters its output.
No threshold/window/gain rescue or blanket suppression; previous mixed-energy
and microphone-transient failures stay closed.

All2,815 baseline notes, user-supported openings, Knuckles35 unchanged targets
and repeated-tapping clarification preserved. D:/F: read-only. Ignored inventory
unchanged, existing untracked paths retained. Prior90-test log protected, not
rerun; no application path changed. Final source/docs snapshot, verification and
all-artifact manifest saved. C: copies are not independent-device backups.

Next: NEW C: scope, audit current corrected full-song WHITE WAVES and Death Before
Dishonor packages in the native loader and existing practice views, including
duration/coverage, beginning/middle/end playback/seek and note/lane rendering.
Prepare a small fixed uncertain-passage review; never conflate load/render success
with musical accuracy or full-song acceptance. No new correction candidate is
promoted. Independent validation and m!sa acceptance remain required; KLEWS/Adapt
outside tuning, earlier E-GMD/merger and ADT_STR failures closed, Separate-and-
Detect deferred. No broad downloads/retraining.

## October 16 HH-microphone presence audit (source specificity failed)

New root `C:\Users\10ros\BeatSight-Recovery\2026-10-16-enst-hh-presence-audit-01`.
Read `ENST_HH_PRESENCE_AUDIT_2026-10-16.md`.2,346 prior hashes verify;99 source/docs
preserved. Primary ENST paper/page saved and hashed. The paper explicitly records
HH-mic snare bleed and annotation exclusions for quiet periodic timekeeping.
Original HH-mic and dry stereo audio available for all six existing recordings;
frame/rate/channel contracts checked.24 source audio/annotation copies read back
exactly, with original D: files unmodified. Existing C: stages reused read-only.

104 protected entries freeze a6dB broadband50-ms post/pre energy-rise screen.
Tool-matched isolated controls selected by filename before measurements: drummer1
brushes (no local closed-HH-stick control), drummers2/3 sticks.13/13 HH and15/15
snare-only hits trigger, specificity0 for each performer; source-presence gate
fails. This closes this readout; no parameter rescue or stage-loss attribution.
All20 fixed previous cases remain; HH mic triggers on all12 matched/all8 false HH.
120 six-stage clips round-trip exactly. Six waveform panels/control and case plots
inspected; no listening relabels.148 independent feature rows agree within
5.33e-15dB;36 direct correlation coefficients within1.67e-16.17/18 HH clock checks
peak atzero;30/36 total within2ms. Remaining mixed-channel peaks are ambiguous,
not established clock drift. No audio or annotation shifts applied.

No neural inference, new packages, training, broad acquisition or note/default
change.2,815 baseline events and all prior corrected charts preserved. D:/F:
read-only; ignored/untracked assets, opening corrections, repeated-tapping wording
and Knuckles35 targets intact. Prior90-test evidence protected, not rerun. Final
source/docs archives, verification and manifest saved; no inference running.

Six companion isolated dry mixes are metadata/hash inventoried. Next in NEW C:
scope, predeclare one native DrumSep routing/reconstruction control on these
single-instrument-labeled inputs with unchanged model/gain and frozen leakage/
fidelity criteria. No close-mic purity assumption or further presence/relative-
energy threshold tweaks. This is diagnostic only; independent validation and
complete m!sa practice acceptance still gate any future chart promotion. Reserved
KLEWS/Adapt and previously rejected model routes remain excluded.

## October 16 DrumSep mixed-recording validation (fixed hypothesis failed)

New root `C:\Users\10ros\BeatSight-Recovery\2026-10-16-drumsep-mixed-validation-01`.
Read `DRUMSEP_MIXED_VALIDATION_2026-10-16.md`.2,147 protected prior files verify;
97 preexisting source/docs snapshotted before edits. Existing six ENST recordings
retained,446.32s. Cached htdemucs_ft mono44.1kHz FLOAT PCM duplicated exactly to
stereo/gain1; mixture peak and run hashes checked, no ADTOF/Demucs rerun. Same
DrumSep checkpoint/source/settings;68 protected protocol entries frozen.319
tensors match;36 finite complete stems round-trip exactly.31.18s total inference.
No downloads, packages or training. Oracle versus current comparison changes
upstream separation and stereo representation together; no causal attribution.

Frozen50-ms snare/HH ratio: pooled AUROC .6920769580 fails .8.161 targeted false
HH/1,025 matched HH; medians +2.960/-19.299dB. Only brush has>=10/group and
passes(.909360); breadth requirement unmet. No track removal or brush-only rule.
Of snare-dominant events,90 are target false HH and338 genuine HH,230 with nearby
SD+HH labels. Other116 false HH remain separately tabulated (20 snare-dominant).
Do not interpret stem dominance as absence of a simultaneous real instrument.

All1,302 HH features/7,812 energy windows, source groups, six matching objectives,
rank-sum AUC and failed gates reconstruct independently; max score error1.42e-14dB.
20 fixed exception cases have100 exact mix/drum/snare/HH/tom clips, event CSV,
six inspected waveform panels and a complete-recording plot. No auditory relabels.
All2,815 baseline events remain intact. Prior90-test log protected, not rerun;
actual inference/data checks supply new evidence. Final snapshots, inventories,
verification and manifest saved. D:/F: read-only; corrections/Knuckles35 targets
and repeated-tapping observation retained. No app/default/user-chart changes or
inference left running. KLEWS/Adapt unused. Exact training overlap unresolved.

Close the fixed relative-energy correction hypothesis. No threshold/window/gain
sweep, per-song calibration, track dropping or blanket HH/CY suppression. Next
bounded step is local aligned individual-microphone evidence audit for these
fixed reviewed cases: whether direct HH presence survives separation, with
clock/channel/bleed limits checked. New C: scope; one predeclared presence test
or documented stop before another inference. Independent validation and full-song
m!sa practice acceptance still required before any future correction/promotion.

## October 16 six-stem DrumSep diagnostic (promising; no chart changes)

New root `C:\Users\10ros\BeatSight-Recovery\2026-10-16-drumsep-audit-01`.
Read `DRUMSEP_FAMILY_EVIDENCE_2026-10-16.md`. All 2,042 prior artifacts verify;
95 preexisting source/docs are preserved. Local checkpoint inventory preceded
acquisition. Original author endpoint404; pinned mirrors advertise identical
437,652,699-byte six-stem weight digest, and actual download matches. Two config
copies are identical. Nine native source files match pinned Git blobs. Original
author signature, exact synthetic training contents/exclusions and weight rights
remain unresolved; this is bounded local research, not a provenance guarantee.

12 native overlap/stitching/STFT checks pass. Frozen protocol precedes acquisition
and inference; 22 protected inputs/source entries verify with explicit wrapper
amendment. First attempt failed at CUDA memory reset before initialization and
before weight loading; original code/log/empty output preserved. Only initialization
and a new output path changed. Native model/settings/feature/gates unchanged.
319 tensors/109,378,624 values load exactly with weights_only=True. Existing
PyTorch2.5.1+cu121 runtime; no packages installed. Complete75.16s original brush
drums produce six finite stereo44.1kHz FLOAT stems, exact readback, in8.46s.

Predeclared 50-ms snare/HH mean-square ratio gives AUROC .9477836213 for121 false
HH near SD versus44 matched HH; medians +7.601/-37.457dB. All diagnostic gates
pass.79 positive cases and two genuine HH exceed0dB;42 targeted false HH do not.
All23 true-HH cases near SD+HH source labels are retained. This is selected-group
ranking on exposed original-drum input, not note accuracy or transcription gain.
Other26 false HH remain in full191-event table. Independent dot-product checks
reproduce1,146 stem windows within1.42e-14dB; rank-sum AUC and ordered matching
objective agree. Eight preselected exceptions have32 exact clips, plots and source
contexts. Visual waveform inspection does not establish auditory relabeling.

No app/default/user-chart changes, suppressed/relabelled hits, parameter sweep,
training, broad downloads or reserved-song use. Prior90-test log hash-verified,
not rerun; native/executed diagnostic checks supply new evidence. D:/F: read-only;
opening corrections, repeated-tapping clarification and Knuckles35 targets intact.
Final source/docs archives, ignored/untracked inventory, verification and manifest
saved. No inference running. Next: unchanged-feature diagnostic on all six
previously selected mixed-recording ENST cases, in a new C: root. Verify cached
mono/channel/gain contract and freeze stereo duplication, eligibility and gates
before inference. No chart correction until additional/independent validation
and full-song m!sa acceptance. Previous rejected routes stay closed; no blanket
HH/CY suppression or KLEWS/Adapt tuning.

## October 16 Separate-and-Detect feasibility audit (weights deferred)

New root `C:\Users\10ros\BeatSight-Recovery\2026-10-16-separate-detect-audit-01`.
1,836 protected prior files verify. Prior brush measurements/988 native notes/
958 merged events reconstruct with60 independent matching checks.93 source/docs
files preserved before changes, including ignored/untracked inventories.
130 bounded primary source/config/license files match pinned Git blob IDs and
SHA256; one author Beatles output also verified. Paper/GitHub/HF/Zenodo metadata
saved. Two public checkpoint variants exist; no weights acquired. Minimum named
OB+VAE+vocoder assets total6,376,577,711bytes, excluding runtime/other dependencies.

17 actual source/PCM probes pass in `io-probes-02/`: native loader omits3.48s of
a75.16s fixture and9.68s of450s; rejects <10s or >=640s; filename roundtrip shifts
430.08s to440.32s; native read assumes44.1kHz and misreads16/48kHz files. KD/SD/TT/CY
postfilters discard200ms at each segment edge and ignore min_separation; HH differs.
Supplied-peak tests do not execute neural onset detection. Initial ramp-amplitude
oracle was invalid after resampling; failed folder and byte-exact original harness
preserved, amendment captures real load parameters/raw PCM. Native source unchanged.

Published decoder description conflicts with released constants; paper parity
unestablished. Local runtime is incompatible/incomplete without adaptation; strict
weight loading, memory and speed untested. Paper's overall/tom/HH/CY F1 trails
ADTOF; no brush-specific benefit. Training includesIDMT; MDB tuning/ENST evaluation
exposure and exact split exclusions unresolved. No full-song comparison justified
yet: defer weights and do not automatically repair the entire training framework.
This is a feasibility gate, not a measured local model rejection.

Read `SEPARATE_DETECT_FEASIBILITY_2026-10-16.md`, protocol/amendment, decision,
verification and final manifest. Previous90-test log verified, not rerun; new17
source probes pass. No chart/default change, threshold fitting, model/runtime
download, retraining, m!sa acceptance or inference left running. D:/F: read-only;
prior experiments/ignored assets and all user corrections/Knuckles targets intact.
Next bounded audit: Jarredou/aufr33 six-stem MDX23C DrumSep source, after existing
inventory check. Riley/Dixon refines ADTOF velocity/subclasses; missing-snare repair
is not established. Require actual relevance to measured family confusion and
runnable full-song/checkpoint evidence before weights. KLEWS/Adapt excluded.

## October 16 ENST brush input control (diagnostic; no promotion)

New root `C:\Users\10ros\BeatSight-Recovery\2026-10-16-enst-brush-input-control-01`.
1,647 protected prior files verify, and previous validation's2,909 merged events,
3,043 native notes/scores/gates reproduce without writing to completed folders.
90 source/docs files snapshotted before edits; ignored/untracked paths inventoried.
249-entry protocol frozen before two model runs on the one original wet-drum input.
Same75.16s ENST musette brush recording and416 targets. Fixed .5*wet/previous-mix-
peak then mono; no new input gain choice, separation, threshold/radius/timing sweep.

50ms ADTOF F1 .455866 -> .544542, native E-GMD .473853 -> .507361. ADTOF has111
fewer FP/+13 TP, E-GMD56 fewer FP/+2 TP. Input condition contributes, but separator
damage and accompaniment residue are not causally isolated. Model errors persist:
original ADTOF147 false HH (121 near SD labels); native E-GMD16 tom matches/25
false toms. No automatic input/model/fusion promotion. Merger diagnostic gives
same241 TP with130 fewer FP; original33 additions24 matched/9 false at50ms,
23/10 at25ms. Original input loses10 of37 previously recovered snare targets.

All28 prior false cases and9 original false additions have label/timing/waveform
inspection;111 sample-exact original/separated/snare-mic excerpts. No listening-
verified relabels or masks.90 recovery tests pass. Independent array reconstruction
verifies988 native notes/958 merged exports across both inputs, preserving860
ADTOF/645 non-SD events.60 independent cardinality checks agree; all scores,
assignments, reference transitions and correspondences reproduce. PCM/frontend
roundtrips exact. Both protocols and prior files remain intact after execution.

No app/default/user-chart or m!sa acceptance changes; previous snare-merger failure
remains final. Training-overlap/TF1-parity limitations remain. D:/F: read-only.
Opening corrections, Knuckles repeated-tapping feedback/35 disputed targets,
ignored/untracked assets and previous experiments preserved. KLEWS/Adapt not used.
No downloads/training or inference left running. New caches/temp scoped to C:.
Read `ENST_BRUSH_INPUT_CONTROL_2026-10-16.md`, final verification and manifest.
Next: bounded primary-source feasibility audit of one other approach, beginning
with the prior Separate-and-Detect lead, before deciding on weight acquisition.
Check actual checkpoint, dependencies, mapping, full-song path and dataset overlap.
No gain/threshold retries, tom fusion or repeated rejected ADT_STR controls.

## October 15 additional snare validation (gain gate failed)

New root `C:\Users\10ros\BeatSight-Recovery\2026-10-15-snare-validation-01`.
1,112 prior artifact hashes and216 frozen protocol entries verify;88 tests pass.
Six ENST recordings selected before predictions, with fixed .5*(wet+accompaniment)
mixtures and same htdemucs_ft stems for both models.3,071 reference events remain
unshifted/unmasked. Four IDMT controls quarantined before inference due XML/SVL
final-event discrepancies; one XML also names a different recording. Two failed
preparations and all input copies are retained; inputs-03 completed. No substitution.

Unchanged native-snare-chronological-addition-v1:94 additions,59 matches/35 false
at25/50ms.50ms pooled F1 .800204 -> .807358, gain .007154 fails required .01.
The other four safeguards pass. No m!sa acceptance run or promotion. Snare precision
.872483 -> .839130, recall .692410 -> .770972. Brushes contribute37/59 matches and
28/35 false additions.13 false additions coincide with source toms; all35 are over
100ms from the nearest SD reference.105 exact mix/stem/original-snare-mic excerpts
and35 inspected waveform panels preserve every case. No auditory relabeling.

All2,815 baseline notes and2,219 non-snare events remain exact. Independent merger
reconstruction verifies2,909 exported events; native grid reproduces3,043 notes;
124 independent cardinality checks agree. All scores/assignments/gates reproduce.
Original mixture/reference roundtrips are exact. Source/docs ZIPs and final manifest
provide recovery evidence. Ignored/untracked paths and prior artifacts preserved.
D:/F: read-only. No user/default/app changes, KLEWS/Adapt tuning, broad download or
training. User opening corrections and35 disputed Knuckles targets remain exact.

Primary-source audit documents ENST/IDMT upstream evaluation exposure and unresolved
ADTOF checkpoint/Demucs training exclusion: additional validation, not established
independence. TF2.13 execution is not historical TF1 parity. Bossa's sparse SD labels
prevent a beginning/middle attack-profile check; no timing fit was applied.
Read `SNARE_ADDITION_VALIDATION_2026-10-15.md` and final verification/manifest.
Next discriminating hypothesis: fixed original-wet-drum input control on ENST
brushes to distinguish separation contribution from model confusion. New root,
same settings, no rule retuning or failed-candidate promotion. No inference remains.

## October 15 frozen snare addition (development pass; no promotion)

New scoped root `C:\Users\10ros\BeatSight-Recovery\2026-10-15-oaf-snare-addition-01`.
991 prior artifact hashes match; prior native notes/scores/complementarity were
reproduced before work. One protocol froze a native >.5 pitch38-only addition,
chronological priority and inclusive50ms baseline/addition collisions before
measurement. All 2,158 baseline events and1,562 non-snare events remain exact.

144 additions yield123 extra matched snares and21 false additions at50ms.
Pooled F1 .788049 -> .815872; all five development gates pass. At25ms F1 is
.786059 with100 matched additions and44 false additions. Snare precision falls
.969799 -> .947297 at50ms; addition timing median signed error is -14.412ms.
114/123 gains are CoolJazz/FreeJazz: no independent generalization claim.

All21 false additions were audited against reference timing and waveform panels;
seven are50-100ms from SD, seven coincide with another family, seven have no
nearby reference.42 sample-exact mix/stem excerpts and timelines are saved for
review; no listening-verified correction or reference mask. Independent array
reconstruction verifies2,302 exported events; a separate greedy matcher verifies
136 count checks.52 protocol hashes pass.84 tests pass across the full suite
(83, one optional integration skipped) and the separately enabled integration.

No inference rerun, threshold/radius sweep, download/training, app/default or
user-chart change. Prior experiments and all user corrections remain intact;
D:/F: stayed read-only. Source/docs and before/after inventories are preserved
with final read-back hashes. See `OAF_SNARE_ADDITION_2026-10-15.md` and the root's
final verification/manifest. Next: frozen independent validation with overlap and
label checks, then full-song m!sa acceptance. Keep KLEWS/Adapt outside tuning.

## October 15 official E-GMD comparison (complete; no replacement)

New scoped root `C:\Users\10ros\BeatSight-Recovery\2026-10-15-oaf-drums-comparison-01`.
810 previous artifact hashes and89 frozen protocol entries match. One official
25,658,703-byte checkpoint archive and49 pinned primary files acquired. All78
graph variables restore exactly. Native features match direct source frontend
execution on all seven recordings; every emitted note reconstructs from the
saved grid. Whole-record normalization/PCM16 conversion,512-sample hop and final
partial frame truncation follow executed source. TF2.13 compatibility is not
historical TF1 paper parity. Existing TF runtime remains read-only.

50ms F1 falls .788049 -> .726873; TP1820 ->1654, FP338 ->436. Snare matches rise
578 ->637 and toms38 ->51, while cymbals312 ->86 regress. Three of five frozen
replacement safeguards fail. No promotion, user-song replacement, threshold sweep
or reserved-song inference.76 recovery tests pass in12.38s. All writes stay on C:;
earlier experiments and user corrections remain intact. D:/F: stayed read-only.

Cached matching finds131 E-GMD-only snares and72 ADTOF-only snares. One frozen
snare-addition hypothesis is justified for future development, with independent
validation required; no fusion was run here. Tom gains are concentrated in Beatles
and accompanied by71 false toms. Read `docs/OAF_DRUMS_COMPARISON_2026-10-15.md`.
Current source/docs are archived with read-back hashes; final manifest and
verification are in the root's evidence directory. No inference remains running.
The user asked about long-session quality; this completed milestone is a good
fresh-chat handoff. A starter prompt is in the next-session document; no new chat
has been created or messaged automatically.

## October 15 ADT_STR runtime and input controls (complete)

642 accumulated prior artifact hashes match. A new scoped C: root,
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-adt-str-runtime-controls-01`, contains
an isolated declared-version inference runtime, its installation cache/temp and
a frozen nine-batch / 72-chunk comparison. All eleven known failure chunks and a
normal control keep their original batch companions. Both runtimes reproduce
all 72 token sequences exactly, including the same eleven failures. Intermediate
logits are not all within the strict numeric tolerance (16 values); output
equivalence is the verified boundary. Both full separated controls also reproduce
all prior tokens, resampled input arrays and decoded notes exactly.

Original-drum CoolJazz/FreeJazz pooled 50-ms F1 rises .491756 -> .629808, but
no-EOS chunks increase 11 -> 20. Source evaluation applies per-segment peak
normalization, omitted by the public helper. One frozen seven-stem contrast of
that source rule yields .647707 F1, below raw ADT_STR .664469 and ADTOF .788049.
It recovers 105 matches relative to raw ADT_STR but adds 337 false hits; all five
accuracy safeguards fail. No further gain/variant/decoder trials are justified
without new evidence. No app/default promotion or user-song acceptance run.

74 tests pass. Protocols verify 99/15/29 overlapping file-hash entries; all 642
prior artifact hashes match. Research outputs, current source and continuity
documents are preserved in a verified archive/manifest; runtime/cache/temp have a
separate inventory. No previous environment, dataset/checkpoint or chart was
modified. D:/F: stayed read-only. User corrections and Knuckles feedback remain
intact; no inference process remains. Read
`docs/ADT_STR_RUNTIME_AND_INPUT_CONTROLS_2026-10-15.md` before continuing.

## October 15 pause recovery and ADT_STR comparison (complete)

Verified all 491 accumulated prior experiment artifact hashes after the pause.
No BeatSight inference process was still running. The user corrections and
clarified Knuckles repeated-tapping observation are preserved. New scoped root:
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-adt-str-comparison-01`.
Only one ADT_STR checkpoint was acquired (289,134,056 bytes; published LFS hash
matches), after source/terms review. Source and checkpoint revisions are pinned;
132 tensors load strictly. The frozen seven-stem comparison is complete and
rejected: 50-ms F1 .788049 -> .664469, TP 1820 -> 1512, FP 338 -> 578. All five
accuracy safeguards fail. Eleven of 182 chunks hit the 512-token limit without
EOS and have incomplete/malformed grammar. A read-only cached-token audit
reproduces all seven native note arrays exactly; the separately demonstrated
tokenizer field-association bug did not affect these actual exports.

Seventy focused tests pass; 80 frozen hashes and 491 accumulated prior artifact
hashes match. Source/tests/report/continuity documents are archived and verified.
The existing runtime was reused without installation; torch2.5.1 is not verified
against upstream torch2.8. MDB informed the author's recommendation and is
development evidence only. No application/default, user-chart or reserved-song
change; no full m!sa acceptance run followed failure. D: and F: stayed read-only.
Read `docs/ADT_STR_COMPARISON_2026-10-15.md` for metrics, boundaries and reproduction.
Next is a bounded fixed-chunk runtime check, then existing original-drum controls
if needed; no blind variant sweep or broad training. This recovery restores session
continuity, not the previously lost F-drive training-audio collection.

## Finding

The project is recoverable as a working local application and research pipeline.
Its training-audio collection has not been recovered, and accurate transcription
of arbitrary songs is not established. Restoring a working program and validating
its musical output are separate milestones.

The user explicitly authorizes substantial local changes and asks future agents
to distrust unverified inherited AI work. New work must meet the same standard.
Preservation is not endorsement of the old architecture or model quality.

## Preserved evidence

All paths below are relative to `C:\Users\10ros\BeatSight-Recovery\2026-10-13`.

| Evidence | Verified result |
|---|---|
| `repository.bundle` | Git bundle verified; 79,193,270 bytes |
| `working-tree.patch`, `staged.patch` | Original working tree retained; staged patch empty |
| `preservation_hashes.json` | 358 files / 7,996,492,536 bytes; all copy hashes match |
| Saved model collection | 129 checkpoint files, including both active EMA models |
| `annotations-and-notes.zip` | 150 files / 47,718,968,399 original bytes; 5,594,058,839 compressed bytes |
| `annotations-archive-verification.json` | Every archive entry read back and compared with source hash; all 150 match |
| `storage_inventory.json` | Actual files inventoried, including ignored data |
| `private-email-evidence` | Original relevant Gmail conversations; private links retained outside Git |

These copies are on C: with the source and are not an independent-device backup.
The recovery did not write to F:, reorganize other projects, run undelete tools,
publish files, contact developers, or purchase anything. Reused F-drive space was
not claimed to be recoverable. The `data/raw` directory names are placeholders,
not proof of surviving audio; `F:\datasets` is absent.

The initial tree had 998 pre-existing diffs that disappeared with
`git diff --ignore-space-at-eol`. They were preserved without mass normalization.

## Source collection reconstruction

| Source | Evidence found | Remaining recovery step |
|---|---|---|
| ENST-Drums | Gmail access approval dated 2025-11-06; original FTPS endpoint responds to TLS | Authenticate using the original account before selecting downloads; no login attempted |
| MedleyDB | Zenodo approval dated 2025-11-19 | Restore access through the approved account at record 1649325 |
| Signature Sounds | Original order with 15 ZIP links | All original links returned HTTP 401; reacquire from the current free catalog or obtain refreshed links |
| Surviving manifests/labels | Verified archive described above | Reconnect records only after matching actual reacquired audio |
| GMD / E-GMD | Official public dataset sources remain available | Select needed subsets after the quality bottleneck is established |

Access approval emails do not establish separate custom commercial-training terms.
Historical notes claiming such agreements need the original agreement as evidence.
Passwords, private signed URLs, and full correspondence stay outside tracked files.

Sources: [MedleyDB record](https://zenodo.org/records/1649325),
[Signature Sounds](https://signaturesounds.org/),
[Groove MIDI Dataset](https://magenta.tensorflow.org/datasets/groove),
[Expanded Groove MIDI Dataset](https://magenta.tensorflow.org/datasets/e-gmd).

## Actual execution

The recovered clean EMA and cymbal-boost EMA models both execute on the local
RTX 3080 Ti. Python 3.11 has CUDA-enabled Torch 2.5.1+cu121, Torchaudio 2.5.1,
Librosa 0.11.0, and Demucs. Use `py -3.11`, not bare `python`, which resolves to an
unrelated project's environment.

The full 309-second `0101 - Heir of Grief.flac` produced a self-contained draft in
`demo-heir-of-grief`: `chart.bsm`, the hash-verified audio, model/settings manifest,
debug output, and pipeline log. BeatSight's actual C# `BeatmapLoader.LoadFromFile`
parsed all 1,965 notes with the adjacent audio present. This is execution evidence,
not a musical correctness claim. `native-chart-check.log` records the result.

The recovery CLI refuses existing output folders, requires the exact four model
assets, preserves hashes, and rejects heuristic classifier mode, synthetic fallback,
and missing fallback telemetry. Future runs fix Python/NumPy/Torch seeds to zero;
GPU bitwise reproducibility is not guaranteed.

`.venv-recovery` reuses Python 3.11 site packages and locally adds `pretty_midi` and
`jsonschema`. It is a bootstrap, not a standalone environment. `pip freeze` failed
because an inherited unrelated editable package points at a missing path; the
error is preserved in `python-environment.txt`. `python-distributions.json` records
412 package versions without modifying the unrelated package.

## Measured transcription quality

Three original MDB Drums full mixes: MusicDelta_80sRock, MusicDelta_SpeedMetal,
and MusicDelta_CoolJazz. Reference annotations contain 837 events. Predictions are
the exported chart events, matched one-to-one within 50 ms per drum family.
Precision counts false additions; recall counts missed reference events; F1 balances
both. This is not note-perfect accuracy, articulation accuracy, or a timing-quality
score within that tolerance.

Training overlap is unknown for both the recovered models and the external model.
The small set has no tom reference events. It cannot support broad generalization
or a decision to ship a replacement. Original MDB labels also have documented
annotation limitations; manually reviewed examples and alternative annotations
should accompany further evaluation.

| System | Precision | Recall | F1 |
|---|---:|---:|---:|
| Recovered legacy profile | 0.5084 | 0.5424 | 0.5249 |
| Recovered faithful candidate | 0.5022 | 0.5388 | 0.5199 |
| ADTOF reference, full mix | 0.8046 | 0.5412 | 0.6471 |
| ADTOF reference, Demucs-separated input | 0.7613 | 0.6631 | 0.7088 |

Separation before ADTOF improved recall on these examples. Rock F1 moved from
0.7273 to 0.7863; metal from 0.9541 to 0.9377; jazz from 0.3053 to 0.5093.
This is a stronger candidate, not a validated universal replacement. Its five
output families cannot distinguish hi-hat openness, ride versus crash, or tom
identity. `benchmark-adtof-separated/metrics.json` records this experiment and
its derived drum stems are retained with hashes for reuse.

The faithful profile retains detected timing and disables several structural
rewrites. It did **not** improve overall F1. Its name describes that configuration,
not proven accuracy. These initial recovered-profile runs were exploratory and
unseeded; fine differences should not be interpreted as a reliable ranking.

Canonical rescored evidence: `benchmark-final-comparison.json`. The first
evaluator mapped side-stick to snare; the dataset's Table 1 instead assigns it to
Other. That error was corrected and existing predictions were rescored without
rerunning inference or overwriting the earlier metrics. The correction changes
one true positive in each initial recovered-profile result. ADTOF is unchanged.

Source dataset pinned to `b29e2d63c3a023506f4bf353c5b2e8a558eed135`.
ADTOF source pinned to `85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9`; the weight hash
is recorded and enforced by `tools/recovery/evaluate_adtof.py`. Reproduction of the
reference result matched all three per-track scores, with no missing model keys.
Third-party models are research references outside the app, not bundled releases.

Sources: [MDB Drums](https://github.com/CarlSouthall/MDBDrums),
[dataset paper and class mapping](https://www.open-access.bcu.ac.uk/6179/1/Southall2017a.pdf),
[ADTOF PyTorch reference](https://github.com/xavriley/ADTOF-pytorch),
[updated MDB annotations](https://github.com/xavriley/MDBDrumsPlusPlus).

## Controlled loudness-rule experiment

The inherited ensemble adjusts cymbal thresholds using a fixed absolute RMS cutoff
of 0.145 and deletes all hi-hat detections in passages above it. Absolute amplitude
is not sufficient evidence of instrument identity. A new optional method argument
allows this rule to be evaluated independently; application defaults are unchanged.

`tools/recovery/ablate_sections.py` ran the faithful profile with the rule on/off.
Each pair used identical separated audio and onset lists, verified by SHA-256.
Only the section rule changed; the separator ran once per track.

| Rule | Precision | Recall | F1 |
|---|---:|---:|---:|
| On | 0.4967 | 0.5472 | 0.5208 |
| Off | 0.5086 | 0.5329 | 0.5204 |

Removing it alone does not resolve the underlying model errors. No accuracy
improvement is claimed and no default was promoted. Evidence:
`benchmark-section-ablation/metrics.json` and per-arm `experiment.json` files.

## Implemented corrections and checks

- Quantization estimation now deduplicates simultaneous component onsets and
  rejects nonfinite times, instead of treating chords as zero-length intervals.
- Transcription mode now fails before saving when no classified hits remain;
  it cannot export a fabricated fallback rhythm as a successful transcription.
  Gameplay mode retains its existing fallback behavior. C# already maps nonzero
  Python exit status to a generation failure, so no one-sided CLI change is needed.
- An inherited training test conflated proportional sampling with its minimum
  class quota. Tests now separately verify proportions with the quota disabled
  and the quota's cap/no-duplicate behavior; the sampler itself was not changed.
- Python core/auto-parameter/recovery/training checks: **173 passed, 1 skipped**.
  The skip is the Torch compilation test because Triton is unavailable; ordinary
  CUDA inference and the other GPU tests executed.
- Initial complete desktop suite: **536 passed**. Relevant desktop generation
  contract checks after the transcription change: **32 passed**.
- Opt-in live Playback 1080p visual comparison: **failed**, changed-pixel ratio
  5.884742%, mean delta 0.01196027. Real 3D rendering works, but the old baseline
  and current capture differ in note positions/strike area. Both also show header
  overlap. The baseline was not replaced or its threshold loosened. This capture
  uses the bundled fixture, not the recovered song. Investigate capture timing and
  layout separately; a passing ordinary desktop suite does not cover this failure.

## Decision and remaining work

Resume from a preserved, executable baseline, then evaluate alternative transcription
models and identify failure classes before restarting training. The old headline
"94.55%" and "F1 0.9153" cannot be reused as end-to-end song accuracy. Likewise,
the old external evaluator supplied known onsets, excluding an essential source
of error.

The next quality gate needs a broader, manually checked set with known training
exclusion, actual toms, brushes, ghost notes, cymbal articulations, and varied mixes.
Compare full-mix and separated-input inference, report per-track/per-family errors,
and preserve uncertainty in generated charts. Do not tune on that final test set.
Only then decide whether to replace the model, retrain a measured weakness, or
combine systems. A reliable editable draft may precede fully automatic teaching.

Current alternatives inspected, not yet validated here:
[Separate-and-Detect](https://github.com/ddman1101/Separate-and-detect),
[Inverse Drum Machine](https://github.com/bernardo-torres/inverse-drum-machine),
[drum2midi](https://github.com/miraer/drum2midi), and
[DrumScript](https://github.com/DrumScript/DrumScript).
Their published claims are starting points for local testing, not transferred results.
The `drum2midi` checkout was saved outside this repository at revision
`ef2a36c062341ab0ea585874259ea396a94ae362` for inspection; its full pipeline was
not installed or executed. Existing dependency versions were not replaced.

At the October 13 checkpoint, raw corpus restoration, account-based redownloads,
an independent-device backup, and the live visual mismatch remained incomplete.
No retraining had been started.

## October 14 external-drive discovery and restart checkpoint

The user reconnected D: `Cold_Raw_Data`. All 118,353 source-file references in ten
canonical ingestion provenance inventories are present and nonempty. The initial
180 hash samples match; full recorded-hash checks of ENST, Groove MIDI, IDMT,
Signature Sounds, and Telefunken passed for all 3,326 files. These overlap the
initial sample. This supersedes earlier missing-raw-data conclusions for those
sources. It does not establish complete historical downloads, audio/label quality,
commercial rights, or recovery of the old F: processed training collection.

See [the current inventory](DATA_RECOVERY_INVENTORY_2026-10-14.md) for source counts,
Gmail/PC search coverage, additional verified preservation, STAR/Lakh/checkpoint
survivors, and recommended data use. Pending restart follow-up includes D: Recycle
Bin's 50,209 possible training WAVs, the Lakh archive member-count discrepancy,
and comparison/preservation of 49 cold-storage checkpoints. Scans and hash jobs
finished before the user-requested reboot. No D: or F: writes, retraining, mail
changes, purchases, or publication occurred.

## October 14 continuation after reboot

D: was verified again as `Cold_Raw_Data`. All 50,209 Recycle Bin WAV filenames
were linked to original E-GMD event IDs, across 163 source recordings. Of these,
46,192 appear in the surviving indices (42,058 training, 4,134 validation); their
13-class labels agree with the filenames. A fresh hash check of the corresponding
163 MIDI files passed. They represent 18 distinct MIDI hashes, **five of which occur
in both training and validation** across kit renders. This demonstrates performance
overlap in the saved indices. It does not determine how every checkpoint was trained.

Lakh's archive is damaged: gzip does not reach its end marker, and its last listed
MIDI fails the checksum encoded in its filename. A safe salvage recovered 16,256
original-checksum-matching members into a new C: ZIP; all entries were read back
and SHA-256 verified. They cover 4,592 of the 50,722 historical synthesis selections.
The damaged original is also preserved with a verified SHA-256. No repair was
attempted on D:. Original-byte identity is distinct from MIDI validity.

All 350 empty STAR annotation files have matching empty MIDI and silent 1.5-second
resynthesized drum audio. They are consistent empty examples, not proof of a
drum-free original recording. Historical license summaries and the download guide
now carry notices identifying unsupported permission claims as unverified history.
Additional all-folder Gmail vendor-domain searches found no new custom agreements.

The [next evaluation gate](RECOVERY_EVALUATION_PLAN_2026-10-14.md) specifies
performance grouping, song-level metrics, timing errors, family coverage, and
training-overlap limits before any retraining or model promotion. Recycle Bin
archival preservation subsequently completed for all 50,209 WAVs: every archive
entry was read back and hash-verified, and every WAV decoded successfully with
finite, non-silent samples. All 49 cold-storage checkpoint paths are represented
by 43 new unique, hash-verified C: copies and six identical-content references.
An additional 46 extracted Lakh MIDI files were preserved; 44 pass filename MD5,
bringing checksum-matching MIDI coverage to 16,300 files and 4,602/50,722 historical
synthesis selections. No D: or F: original was modified.

The subsequent seven-recording diagnostic is documented in
[TRANSCRIPTION_DIAGNOSTIC_2026-10-14.md](TRANSCRIPTION_DIAGNOSTIC_2026-10-14.md).
At 50 ms, inherited precision/recall/F1 were 0.4906/0.4900/0.4903, versus
0.8409/0.7192/0.7753 for the separated-input ADTOF reference. Both ran freshly with
hash-checked common inputs and fixed configurations. Updated annotations, short
recordings, and unknown training overlap limit the conclusion. It identifies
instrument mistakes worth addressing; it does not establish arbitrary-song accuracy.

The two-track input probe in that diagnostic shows higher F1 with original isolated
drums than with estimated drum stems, but remaining brush/ghost-note misses even
with oracle input. Both separation/input and transcription limits merit controlled
experiments. No additional model was trained or promoted. The final targeted
recovery/timing check run passed 20 tests. The separate rare-drum event file and
STAR license/mapping/readme metadata were additionally preserved: 34 files,
818,422,081 original bytes, all archive entries read back and hash-verified.

## October 14 user-song drafts and stereo-input experiment

See [the full-song report](WHITE_WAVES_AND_DEATH_BEFORE_DISHONOR_2026-10-14.md).
WHITE WAVES and Death Before Dishonor are the user's motivating drum-learning songs;
the second song's technical opening hi-hats are an explicit acceptance concern.
Four full-song arms were compared: inherited faithful, ADTOF full mix, ADTOF after
mono-input separation, and ADTOF after stereo-input separation. Final experimental
native packages have 1,845 and 1,078 notes, copied/verified audio, isolated stems,
review bookmarks and explicit broad-family limitations. No song-level ground truth
exists here; precision, recall, articulation and timing accuracy remain unmeasured.

A controlled stereo-input change improved the seven-recording diagnostic 50-ms F1
from 0.7753 to 0.7859, on six of seven tracks, with a small hi-hat regression and no
timing improvement. Mixing full-mix cymbals with separated other families worsened
F1 to 0.7682 and was rejected. A paired section-gate probe on the second song raised
opening hi-hat predictions 39 to 49, still below reference 79–83. Matched candidate
absence is not a verified miss; the report separates model agreement from accuracy.

Both packages were loaded and captured in the actual native 3D practice view.
Mix/stem lengths and seek positions were checked. A FLAC duration-reporting mismatch
was avoided in the second final package with a PCM16 WAV whose decoded samples equal
the preserved source; no original was modified. Known header overlap remains and no
baseline was replaced. Twenty recovery/matching tests and targeted byte-range audio
server checks passed. All new experiments are scoped on C:, D:/F: stayed read-only,
and no retraining, default promotion, external message or publication occurred.
## Final full-song integrity check (2026-10-14)

After packaging both current stereo drafts, 79 hash comparisons passed against
recorded song, code, model, stem and package evidence (includes repeated paths).
Exported note times/components equal the selected predictions exactly; source audio
hashes are unchanged. The Death Before Dishonor compatibility WAV again matches
the original decoded PCM sample-for-sample. Both mix/stem frame counts agree.
The final helper/native-capture source snapshot and checks are saved in
`C:\Users\10ros\BeatSight-Recovery\2026-10-14-white-waves-01\final-verification`.
Twenty-three targeted recovery/matching/export tests pass. Both four-way localhost
review pages loaded, sought to the nominated excerpts, and retained half-speed/HH
filter settings. These checks establish integrity and execution, not note accuracy.

## User-identified opening errors and chart-reference direction (2026-10-14)

Direct user feedback corrected WHITE WAVES' first cymbal (draft time 1.000 s) to
China, with no simultaneous HH, and identified Death Before Dishonor's main
entrance at about 8.750 s as crash, not HH. Separate packages remove the two
spurious HH events and relabel the WHITE WAVES CY alias to China. All other notes
and surviving timestamps are unchanged; these edits are user-supported labels,
not independently measured timing or whole-song ground truth.

Evidence and corrected charts are in
`C:\Users\10ros\BeatSight-Recovery\2026-10-14-opening-feedback-01`.
Schema checks, actual native loading and 27 targeted tests pass. The native
component-based layout recognizes China but currently shares its lane with generic
crash; it does not map China to HH. Original drafts/audio/models remain intact.

A fixed diagnostic suppressing every HH within 10 ms of CY removed 8 false
positives but also lost 6 matched true positives on the existing seven recordings;
50 ms F1 fell 0.785854 to 0.785637. Rejected as a blanket rule, with no threshold
search, default change or retraining. The remaining 10/30 full-song candidate pairs
are not all verified errors.

The user proposed comparing against existing Clone Hero drum charts. Recommend
curated Expert Pro Drums full-song references with exact audio/tempo/offset checks,
chart-agreement versus audio-accuracy separation, and training-overlap controls.
ADTOF already derives from rhythm-game chart research, so random community charts
are not automatically an independent test. No Clone Hero corpus has yet been
acquired or evaluated. Full findings, primary sources and concrete next batch:
`docs/OPENING_CORRECTIONS_AND_CHART_BENCHMARK_2026-10-14.md`.

## Documentation and session handoff (2026-10-14)

The user accepted the curated Clone Hero comparison direction and requested durable
documentation. `docs/NEXT_SESSION_CLONE_HERO_BENCHMARK.md` now consolidates the
current evidence, exact corrected-chart paths, known limitations, rejected rule,
unstarted benchmark steps, runtime commands and preservation boundaries. RECOVER
links it as the next-phase starting point. No new benchmark, model change or
musical verification was performed in this documentation turn.

## Curated chart-reference benchmark begun (2026-10-14)

The subsequent execution turn acquired and preserved five author-published song
packages in `C:\Users\10ros\BeatSight-Recovery\2026-10-14-clone-hero-benchmark-01`:
three KLEWS development songs and two Castillerian reserved songs, totaling
1,252.151 seconds. All 15 fixed song/system runs completed. The full report is
`docs/CLONE_HERO_BENCHMARK_2026-10-14.md`; it supersedes the unstarted-benchmark
status above. `selection-v2.json`, `prepared-v2/`, `evaluation-01/` and
`report/summary.json` are the current provenance, imported references, raw runs
and scored report. No charts or predictions were shifted to improve scores.

Reuse of pinned YARG.Core exposed and regression-tested a disco-state leak between
difficulties; a patch in the isolated source checkout fixes it. A thin adapter
preserves Pro Drums, tempo/meter, offsets and 2x kicks. DIARRHEA's bundled MIDI was
selected before inference because its `.chart` lacks the Pro Drums information.
The earlier interpretation remains preserved, not overwritten.

Independent acoustic screens flag all three KLEWS chart references roughly
40–50 ms later than percussive transients; raw-waveform anchors support a material
timing issue, but exact corrections are not certified. Their 25/50 ms scores
cannot support model selection until reference admission. On the two reserved
songs, stereo-separated ADTOF chart-agreement P/R/F1 is .8812/.8326/.8562 at 50 ms,
versus full-mix .8004/.8157/.8080 and inherited faithful .5663/.5231/.5439.
Separation helps Adapt but hurts DIARRHEA; merging HH/CY gives full-mix F1 .9227
versus separated .9083. These are provisional chart comparisons, not verified
musical accuracy. Model training overlap remains unknown despite public-metadata
checks, and no model or application default changed.

Thirty-six focused tests pass. Seventy-eight acquired-member/acceptance-chart
preservation comparisons pass; both RAR archives pass integrity tests. The local
review page loads and switches/ seeks mix and stem audio correctly. Original and
corrected m!sa charts remain intact; D:/F: were read-only. Next work is short
reference alignment/cymbal listening review, then evidence-based rescoring of
saved predictions. No broad download, training, message, upload or publishing ran.

## Reference-admission audit and Knuckles feedback (2026-10-15)

New work is confined to
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-clone-hero-reference-audit-01`.
The full report is `docs/CLONE_HERO_REFERENCE_AUDIT_2026-10-15.md`.
Ten package audio files agree between FFmpeg and libsndfile in frame count;
28 non-silent windows have zero-sample decoder lag. Independent raw-BPM
integration agrees with 4,406 KLEWS `.chart` event times. Neither tested import
path explains the earlier timing flag.

A frozen original-mix RMS-attack screen used beginning windows for candidate
offsets and separate middle/end windows for validation. All five songs fail at
least one support/stability requirement; no criterion was relaxed. KLEWS attack
profile peaks are 29–47 ms early depending on song/window, while earlier flux
peaks were roughly 40–50 ms early. These measure different acoustic features,
not verified drum onsets. No exact offset, reference revision, rescoring or model
change was accepted. Use `validated/audit.json`: an initial diagnostic's two
silent-window boundary lags were corrected to explicitly unmeasurable values,
with original output preserved and regression tests added.

The user listened to the questioned Knuckles 0–8 s opening and replied
**“sounds like a guitar hit”**. The verbatim reply, reference hash and clip hash
are in `user-feedback-01.json`. The passage has 35 yellow-tom chart notes, but
this response is not a per-note deletion/relabel instruction and does not rule
out overlapping drums. The opening is disputed reference material. Original
charts and all m!sa user-supported corrections remain unchanged. The source's
hand-authoring claim was checked, but is not independent label validation.

An 18-passage review on port 8775 includes chart lanes, original audio, waveform
zoom, original Adapt drum stems and clearly labelled trial snare clicks. An
optional excerpt of Knuckles' saved estimated stem was added after user feedback;
it can leak guitar and is not ground truth. No new separation/inference ran.
The older full-song review on port 8774 is intact.

48 focused tests pass. 79 source/output hashes match; all 21 original-audio review
clips match their exact source PCM, and 45 initial media range requests pass.
Browser source/speed/zoom checks pass without claiming agent listening. D:/F:
stayed read-only. Recovery/handoff documents were updated with the new evidence.
Next, resolve bounded instrument/timing ambiguities or keep KLEWS excluded from
model selection; do not tune a model to uncertain references.

## Original-source controls and clarified feedback (2026-10-15)

New work is confined to
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-chart-reference-controls-01`.
The full report is `docs/CLONE_HERO_SOURCE_CONTROLS_2026-10-15.md`. Earlier
experiments, source audio, checkpoints and user-supported m!sa corrections were
preserved. D:/F: stayed read-only; no cleanup, move, training or broad download ran.

Adapt's original six stems reconstruct the prepared mix exactly. On the three
fixed snare windows, the unchanged timing screen fails on the mix and passes on
original drums (31/33 anchors near the window profile peaks). Drum-withheld and
silence controls fail. A full-song follow-up finds 253/262 original snare anchors
have their strongest nearby original-drum energy rise within 10 ms of unshifted
chart time, with every 30-second bin peaking at -3 ms. Keep original chart timing;
neither full-mix detector failure nor the -3 ms feature peak is an accepted
reference correction. This is temporal support, not a complete note-label audit.

An original-drum cymbal waveform screen compares 343 isolated chart events.
Zero of 21,207 cross-family pairs reach the fixed .98 correlation threshold,
versus 106/36,903 same-pad pairs. All eligible pairs were examined; a preserved
protocol wording clarification explains that spectral similarity was descriptive,
not a candidate filter. No cymbal relabel was justified by this result.

One fixed ADTOF inference on the full original drum stem, unchanged weights,
thresholds and timeline, gives Adapt 50-ms P/R/F1 .9242/.9147/.9194, versus the
saved stereo-separated .9290/.8683/.8976. Original-drum TP/FP/FN is 1695/139/158;
merged-cymbal F1 is .9767. It recovers 34 additional tom matches but still misses
37/123 tom targets. Conditional matched timing has median absolute error 7.416 ms
and 90th percentile 12.040 ms. Input losses matter, but removing estimated
separation does not eliminate model/reference disagreements. Source gain/channel
differences prevent attributing the entire contrast to separator quality. This
oracle input is unavailable for ordinary mixtures; Adapt is not a fresh untouched
test after diagnostic inspection. Training overlap and instrument/completeness
questions remain. No threshold/default/model was promoted or baseline score edited.

The user clarified the Knuckles guitar-like sound as **“Repeated tapping”**.
`knuckles-user-feedback-02.json` preserves both verbatim replies, reference/prior
feedback hashes and 35 disputed YellowDrum targets in the opening 0–8 s.
`decisions-feedback-addendum.json` supersedes the earlier pending-clarification
field. These targets are excluded from trusted reference admission/training,
without claiming all are guitar or no drums overlap. Original chart notes and
scores are unchanged; no scoring mask was applied. KLEWS remains excluded from
model selection.

52 focused tests pass, including real YARG integration and four new source-
control tests. All 124 prior source/output/media hash checks match; 29 new clips
pass hash/decoding checks and 20 cymbal clips match original source PCM exactly.
The oracle input round-trips exactly, pinned weights/source pass, and all three
saved baseline score dictionaries reproduce. Six earlier continuity documents
were archived before edits; the final source/document snapshot is read-back
verified under `evidence/`. This is C: preservation, not an independent backup.

Next: one frozen input-preservation comparison on the existing seven annotated
development recordings, reporting per-recording/family 25/50 ms metrics and
timing. Preserve the reserved-song boundary and user corrections; do not optimize
to uncertain chart labels or start broad retraining from this diagnostic.

## Fixed residual-input comparison and decoder audit (2026-10-15)

Completed the planned seven-recording development contrast in
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-mdb-residual-input-01`.
Full report: `docs/MDB_RESIDUAL_INPUT_AND_DECODER_AUDIT_2026-10-15.md`.
The raw full-mix arm already existed in the WHITE WAVES diagnostic root and was
reused. New inference only tested the saved drum stem plus 25% of the residual
between its original normalized mono mix and the stem. Same model, thresholds,
timeline and annotations; no new separation or fraction/threshold sweep.

The candidate failed its frozen gate. At 50 ms TP/FP/FN changed from
1811/337/650 to 1723/326/738; P/R/F1 from .8431/.7359/.7859 to
.8409/.7001/.7641. At 25 ms F1 fell .7616 -> .7463. Six of seven recordings lost
F1. Tom targets gained only two net matches while false tom predictions rose
24 -> 96, mainly on 80sRock and Beatles. HH false positives fell 131 but 47 net
HH matches were also lost. Reject the input recipe, preserving current packages.
The same 1,665 targets matched in both arms have median timing errors 9.375 vs
8.257 ms; that small change does not offset lost coverage and family errors.

The event-level audit retains all matched/missed identities and timings. On the
baseline, 282/377 missed snares and 21/43 missed toms have raw model activations
below current thresholds throughout +/-50 ms windows. Another 86 snare misses
fall below threshold after local-average subtraction; that behavior alone is
not evidence of a bug. Other cases involve peak/grouping/timing/assignment.

A primary-source audit found actual peak-decoder conformance differences in the
pinned PyTorch port: edge padding, peak-strength representation, and strongest
group member versus earliest-event combination. Four small public source files
were saved with hashes; only two reviewed function definitions were compiled
for differential checks, not imported as whole modules. Original ADTOF parameters
confirm that local-average thresholding is intended in both implementations.
The report links the exact primary sources and explains compatibility handling.

New `decode_adtof_reference.py` matches primary madmom v0.16.1 behavior on 1,000
deterministic synthetic vectors and all seven cached baseline charts; 1D/2D
primary-function results also match on 1,000 cases. A concrete two-peak example
returns 100 ms with primary semantics versus 120 ms with the port. Re-decoding
saved activations gives 1768/385/693 at 25 ms (F1 .766363) and 1814/339/647 at
50 ms (F1 .786303). The small gain is not the solution to the major recall
deficit. Primary conformance is verified for this decoder configuration only;
audio preprocessing and model parity remain unverified. Historical charts,
scores, pinned code and application defaults were not changed.

58 focused tests pass, including parser integration and new input/decoder guards.
All 45 contrast source/output hashes match before/after; the new WAV inputs
round-trip exactly and saved activations reproduce baseline predictions/scores.
Broader prior-artifact verification and final source/document snapshots are in
the new root's `evidence/`. Six continuity files were archived/read-back checked
before updates. Both m!sa corrections and clarified Knuckles feedback remain
preserved. D:/F: stayed read-only; no training, broad audio/model download,
publishing or external message occurred.

Next: verify the reference audio frontend against primary semantics using a
small frozen set of saved failure/control excerpts. Avoid another mixture or
threshold sweep until conversion fidelity is established. Keep the existing
development/reference boundaries and do not tune to uncertain Clone Hero labels.

## Audio frontend conformance and fixed comparison (2026-10-15)

Completed the documented frontend audit and its conditional seven-recording
comparison in
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-adtof-frontend-audit-01`.
Full report: `docs/ADTOF_FRONTEND_CONFORMANCE_2026-10-15.md`.
Primary ADTOF/madmom source confirms that the port starts its logarithmic grid
at 20 Hz whereas the original anchors to 440 Hz; 66/84 filter bands differ.
Window precision and exact-hop end framing also differ. Seven small public source
files were acquired with fixed revision/tag, URL and SHA-256 receipts.

New recovery-only `frontend_adtof_reference.py` matches the reviewed primary
float-PCM functions exactly on 25 synthetic signals and 16 frozen four-second
mix/stem failure/control excerpts. Replacing only the port's grid reduces real-
excerpt common-frame feature discrepancy to at most 7.75e-7. The numerical audit
executes selected reviewed AST definitions only, with a local old-NumPy alias;
it does not establish complete madmom file decoding or original-model equivalence.

The corrected feature path failed the predeclared chart-improvement gate. Both
arms use the same saved drum stems, pinned converted weights and verified primary
decoder/thresholds. At 50 ms TP/FP/FN changes 1814/339/647 -> 1808/346/653 and
P/R/F1 .842545/.737099/.786303 -> .839369/.734661/.783532. At 25 ms F1 changes
.766363 -> .765764. Tom matches stay 38 with seven extra false toms; snares lose
one match. The large snare/tom recall gaps remain. One full baseline control
exactly reproduces saved activations, and strict model loading succeeds.

62 unique focused tests pass (61 combined, then four frontend checks after adding
a relocated-source hash guard). 52 comparison hashes match before/after and 304
prior artifact hashes match. Git status, 11,259 ignored paths and 67 untracked
paths are inventoried; six prior continuity documents and final source/docs are
archived. The actually executed audit script is separately preserved before the
later hash-guard change. Current and prior evidence is verified under `evidence/`.

No input/threshold sweep, training, new separation, model/audio download, app/default
promotion or user-chart replacement occurred. m!sa opening corrections, the
Knuckles repeated-tapping observation and all 35 disputed targets survive. D:/F:
stayed read-only. Short development recordings and unknown training overlap
remain limits; no new full-song musical-accuracy claim is supported.

Next: inventory local original-model/checkpoint and conversion evidence, then
audit layer/weight conversion on fixed features. Check recurrent gates/reset/bias,
normalization and temporal context before another inference arm; do not select
GRU variants by score. Distinguish source-semantic checks from original-checkpoint
execution. Keep reserved/uncertain Clone Hero charts out of parameter tuning.

## Model conversion, pooling and actual original-checkpoint parity (2026-10-15)

Completed the next bounded model audit in
`C:\Users\10ros\BeatSight-Recovery\2026-10-15-adtof-model-audit-01`.
Read `docs/ADTOF_MODEL_CONVERSION_AUDIT_2026-10-15.md` for full results and source
links. The local scoped inventory found 510 checkpoint-shaped candidates, none
in original TensorFlow/HDF5/Keras format. It included ignored files but was not
a whole-computer or archive-content search. The original repository tree then
identified the exact published Frame_RNN_adtofAll_0 checkpoint. Its two files,
5,428,542 bytes total, were acquired into the new root and verified against Git
blob IDs and SHA-256. An isolated TensorFlow CPU2.13.1/Keras2.13.1 runtime and its
cache/temp directories were created under that same scoped C: root; the existing
recovery environment and all prior artifacts remain unchanged.

The port pads max pooling with zero, which changes negative batch-normalized
edge values. New recovery-only `model_adtof_reference.py` excludes padded positions
from the maximum. It passes 300 independent valid-window comparisons; all 16 fixed
real excerpts expose the original second-pool error. Convolution/normalization,
context/flattening and primary GRU equations pass the bounded source checks.
The converter's candidate-bias merge default is mathematically incorrect, but
the bundled checkpoint retains separate recurrent biases. No bias edit or GRU
flag selection was attempted.

A frozen pooling-only comparison uses the same saved stems, source-aligned
frontend, weights, thresholds and primary decoder on both arms. At 50 ms
TP/FP/FN changes 1808/346/653 -> 1820/338/641; P/R/F1 changes
.839369/.734661/.783532 -> .843373/.739537/.788049. At 25 ms F1 changes
.765764 -> .767266. This small improvement fails the predeclared .01 F1 gain
gate. The candidate retains 375 snare and 43 tom misses. No app/default or user
song was changed, and no additional threshold/input recipe was selected.

The later actual original-checkpoint test closes the initial source-only audit's
main limitation. All 50 converted tensors match the published original values
exactly after layout/gate mapping. The reviewed original model-construction method
executes in TensorFlow and loads all model objects successfully. On 16 shared
feature excerpts, every corrected intermediate stage meets the frozen numerical
tolerance; maximum final output error is 3.28e-7. Across all seven full shared
feature sequences, maximum activation error is 1.13e-6, and the primary decoder
produces identical charts and 25/50-ms scores. Use `original-parity/comparison.json`;
the earlier missing-checkpoint limitation in `layer-audit.json` is historical.
Complete original audio file loading/resampling remains outside the tested
float-PCM boundary, and training overlap/full-song generalization remain unknown.

66 focused tests pass. All 72 comparison hashes, 61 parity hashes and 358 prior
artifact hashes match. Pre-edit continuity docs and final source/docs are archived;
ignored/untracked files, runtime packages and new artifacts are inventoried with
explicit manifest scopes. Original/corrected m!sa charts and clarified Knuckles
feedback/35 disputed targets are preserved. D:/F: stayed read-only; no training,
dataset download, broad model acquisition, publication or external message occurred.

Next: stop speculative conversion/input/threshold tweaks. Select one meaningfully
different existing pretrained transcription model using primary checkpoint,
mapping, simultaneous-hit and overlap evidence, then freeze a comparison on the
same seven development recordings. The inherited classifier already lost badly;
do not blindly rerun it or sweep its many epoch checkpoints. A substantial
improvement should precede full m!sa acceptance-song evaluation. Keep uncertain
KLEWS and reserved Adapt out of tuning, and preserve the user-supported openings.

