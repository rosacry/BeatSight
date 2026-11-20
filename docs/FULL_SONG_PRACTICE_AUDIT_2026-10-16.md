# Full-song practice audit — 2026-10-16

The existing corrected WHITE WAVES and Death Before Dishonor packages load their
complete audio and all 2,921 chart notes in the native practice screen. Sampled
seek, playback and pause checks pass in 3D, 2D and manuscript views. This establishes
basic playback behavior, not musical accuracy or full-song acceptance.

Evidence root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-full-song-practice-audit-01`.
Read `plan.json`, `protocol.json`, per-song `runtime/*/completed.json`,
`evidence/verification.json` and `evidence/final-artifact-manifest.json`.

## What was verified

All 2,673 protected prior artifacts and 103 previous source/doc snapshots were
checked before work. Eight song-package files and 377 desktop/source fixture
files were copied exactly. Native runs use a Release sandbox build and scoped
user assets; no application source, user chart, model or default was changed.
The 59-entry protocol was frozen before execution. Original protocol SHA-256:
`396915c2b52fd9ce7146b37206e5aa1a95ae4668b316a3682ce5abee3895e006`.

| Song | Actual audio duration | Notes | Last note | Uncharted tail |
|---|---:|---:|---:|---:|
| WHITE WAVES | 240.011610 s | 1,844 | 229.870 s | 10.141610 s |
| Death Before Dishonor | 204.963492 s | 1,077 | 192.700 s | 12.263492 s |

Both full mixes and drum tracks are actual TrackBass instances. There are no
notes outside the audio or duplicate time/component pairs. Eighteen planned
seeks have zero timing error; eighteen approximately one-second playback samples
pass the declared clock gate, with maximum errors 15.932 ms and 0.6345 ms.
All eighteen pause checks have zero drift. Both final backward seeks pass.
This is sampled transport behavior, not uninterrupted full-song playback.
Handlers were invoked through the native screen; mouse/keyboard usability was
not tested. All 2,921 input note times and instruments survive each stage.

WHITE WAVES retains China only at 1.000 s (actual screen logical lane 6).
Death Before Dishonor retains kick plus crash at 8.750 s (lanes 3 and 0).
Neither has the removed coincident false HH. Prior 2,815 ENST baseline notes,
Knuckles' 35 disputed targets and the **Repeated tapping** correction remain
protected by the prior artifact hashes. Blanket HH/CY suppression stays rejected.

## Tests and visual limitations

The full desktop suite passes 536/536 with live visual tests disabled. An earlier
run failed nine tests because two script fixtures were missing from the sandbox;
the exact fixtures were copied and the complete suite rerun. Logs are preserved.
Three separate real native 1080p baseline comparisons all FAIL:

| Scene | Changed pixel ratio | Mean delta |
|---|---:|---:|
| Playback | .0629683 | .0125631 |
| PlaybackTwoDimensional | .307531 | .0335700 |
| PlaybackManuscript | .0111888 | .0017779 |

Original gates remain .005 and .001. No baseline or threshold was updated. The
cause of the differences remains unresolved. These were inherited-code captures;
passing nonvisual tests cannot override these failures. All three baseline pairs
were visually inspected. Of 18 new full-song captures, only WHITE WAVES 3D index0,
2D index1 and manuscript index1 were visually inspected before the user requested
the Claude migration. Remaining screenshots need inspection. Header/back-button
overlap is visible in inherited baseline and current captures. The toolbar hides
until hover by design; its initial absence is not established as a defect.
Manuscript spacing uses estimated tempo; rhythm notation accuracy is unverified.

## Fixed listening review and next action

`review/index.html` contains six predeclared opening/midpoint/ending passages,
twelve exact FLOAT audio clips (full mix and estimated drums), timelines and
absolute-time event tables. Clip PCM was checked against the decoded source.
It is an offline file; browser interaction and auditory review are NOT completed.
A local HTTP-server launch was blocked by tool policy and no server was started.
The user then prioritized migration. No clips were labeled from sound. Audio in
the tails does not by itself prove missing drum notes. Death Before Dishonor's
unresolved HH at 2.750/3.590 s is outside this six-passage set and unchanged.

Continue with a NEW scoped C: review root. Inspect remaining captures and the
fixed listening packet, establish timing/instrument evidence, and investigate
the three visual differences before accepting or changing baselines. Request
only targeted listening judgments if the next assistant cannot actually hear
the audio. Do not ask the user to chart entire songs. No correction candidate is
promoted; independent validation and complete m!sa practice acceptance remain
required. Prior E-GMD replacement/merger, ADT_STR and DrumSep HH routes stay closed;
Separate-and-Detect remains deferred. Keep KLEWS/Adapt outside tuning.

D:/F: stayed read-only. Existing experiments and ignored/untracked assets are
preserved. Local C: copies are not independent-device backups. No inference or
native audit process remains running. Migration handoff is a separate milestone.
