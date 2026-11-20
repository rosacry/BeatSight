# ENST hi-hat microphone evidence audit — 2026-10-16

**The frozen microphone-transient test fails source specificity.** It triggers
on every isolated hi-hat hit and every snare-only hit. A transient in the hi-hat
microphone cannot establish hi-hat presence, and this test cannot identify which
separation stage removed a real hit. No notes, labels or application defaults
changed; the failed relative-energy rule remains closed.

Root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-enst-hh-presence-audit-01`.
Read `protocol.json`, `measurements/control-gates.json`, `measurements/clock.json`,
`measurements/cases.json`, `evidence/independent-checks.json`, final verification
and artifact manifest. Review players/plots are in `review/index.html`.

## Primary evidence and available inputs

The [ENST paper, sections 2.3 and 3.3–3.6](https://perso.telecom-paristech.fr/grichard/Publications/ISMIR2006_Gillet.pdf)
describes mono individual microphones, stereo dry/wet mixes and common sequence
segmentation. The dry mix changes pan/level; the wet mix also applies processing.
Section 3.5 explicitly identifies snare bleed in the HH microphone and use of
video to disambiguate annotations. It also distinguishes unannotated quiet
periodic timekeeping strokes from annotated offbeat ghost notes. Thus source
annotations and close microphones are useful evidence with explicit limits,
not isolated source truth for every audible event. The
[author page](https://perso.telecom-paristech.fr/grichard/ENST-drums/) describes
the research dataset. Paper/page bytes and SHA-256 are saved; no dataset/model
download occurred. Local research does not imply commercial rights.

For all six existing ENST recordings, original HH microphones and dry mixes are
available on D:. Twelve complete audio files were copied to the new C: root and
verified byte-for-byte. Existing C: snare-mic, wet-mix, Demucs and DrumSep-HH
files are reused read-only. Each recording's six representations have matching
frame counts at 44.1 kHz; expected mono/stereo channel counts are checked. These
are the same 446.32 seconds already exposed in prior tests.

Six labeled isolated-stroke HH-microphone files and their annotations were also
copied with hashes. Control selection was by filename and matching implement,
before waveform measurements:

| Performer | Implement | Positive source file | Negative source file | HH / SD hits |
|---|---|---|---|---:|
| Drummer 1 | Brushes | 016 closed-hi-hat | 013 snare-drum | 3 / 5 |
| Drummer 2 | Sticks | 006 closed-hi-hat | 001 snare-drum | 5 / 5 |
| Drummer 3 | Sticks | 007 closed-hi-hat | 001 snare-drum | 5 / 5 |

Drummer 1's local hit inventory has no closed-HH-stick control. Its brush pair
is not a substitute claim about every technique. All control annotation labels
are exclusively `chh` or `sd` as expected. The 24 new source copies are protected.

## Frozen check and outcome

Protocol SHA-256:
`cd60c59dafd884f421f751e61f823e92b7c2551f04ec2b8a47b8ed2b19d1137a`.
Its 104 protected entries bind code, sources, copies, previous selected cases,
labels and cached outputs. No runtime amendment was required.

The single readout compares broadband mean-square power in the 50 ms after an
anchor with the 50 ms before it:
`10*log10((post + 1e-12)/(pre + 1e-12))`. A fixed rise >= 6 dB is the transient
screen. No bandpass, threshold/window search, normalization, fitted gains or
time shifts. Isolated controls use source onset times. The 20 prior review cases
use the matched HH reference for genuine hits or nearest SD reference for false
HH, with earlier-time tie-breaking; original predictions remain unchanged.

Before measurement, source suitability required >=10 positive/negative controls,
>=80% sensitivity/specificity pooled and for each performer, and >=3 examples
of each type per performer. All size gates pass. **All 13 HH hits and all 15
snare-only hits trigger: sensitivity 100%, specificity 0%.** Every performer has
zero specificity. HH rises span 51.057–78.166 dB; snare-only rises span
48.790–79.994 dB. Silence before isolated strokes makes transient rises large;
this is an attack detector, not evidence of instrument identity.

The predetermined failure action applies: stop using this readout as HH-presence
proof. Do not search another threshold/filter or infer separator loss from it.

## Clock and fixed-case inspection

The diagnostic correlates each HH/snare microphone with the dry stereo mean in
each recording third over a fixed +/-50-ms range. Seventeen of eighteen HH
checks peak at zero lag; bossa's first third peaks at -292 samples (-6.621 ms)
with weak correlation .145. Across both microphones, 30/36 peaks are within
2 ms; six range approximately -8.05 to +3.61 ms. Some coefficients are negative.
This mixed-channel correlation is ambiguous under bleed and phase differences.
It does not prove clock drift or justify shifting audio/labels. No shifts applied.

All 20 previous extreme cases are retained: 12 matched HH and eight false HH
near SD. The HH-microphone readout triggers on all 20. Per-stage values therefore
remain descriptive. The plots show common transients in both microphones,
including false-HH cases, and varying DrumSep-HH responses. At funk 14.661 s and
charleston 20.721 s the DrumSep-HH rise is below the screen despite matched HH,
but the failed source gate prevents a causal claim that the separator removed
the hi-hat. Other true and false cases both have strong separated transients.

All cases have six sample-exact one-second clips (120 total), full feature CSV,
six inspected waveform panels and a 20-case overview. Display traces are scaled
to their own clip peaks and explicitly labeled; saved audio is unnormalized.
This is waveform/source-label inspection, not listening-verified relabeling.

Independent dot-product checks reproduce all 148 feature rows (28 controls plus
120 stage/case combinations), maximum difference 5.33e-15 dB. Direct dot products
verify all 36 reported correlation coefficients at the selected lags within
1.67e-16. The failed specificity decision reproduces independently. These checks
establish arithmetic and preservation, not song-level transcription accuracy.

## Preservation and next step

All 2,346 protected prior files verify. Ninety-nine source/docs files were
snapshotted before changes. D:/F: remained read-only; ignored/untracked assets,
all 2,815 baseline events, opening corrections and Knuckles' repeated-tapping
clarification/35 unchanged targets remain intact. No model inference, runtime
installation, training or broad download was needed. Previous 90-test evidence
remains protected, not rerun. Final recovery snapshots and manifest are saved.
C: copies are preservation against accidental edits, not independent-device backup.

The next useful control has **labeled single-instrument input**, avoiding an
assumption that a microphone channel is pure. Six companion stereo dry-mix files
for these same isolated controls are locally available; metadata and hashes are
saved in `evidence/isolated-dry-inventory.json`, without neural execution.
In a new scoped C: root, predeclare a bounded routing/reconstruction test of the
unchanged DrumSep model on those six complete inputs. Inspect source labels and
audio contracts, keep the same fixed gain/settings, and freeze leakage/fidelity
measurements before inference. This can test whether isolated SD is routed to HH
or isolated HH fails to reach its stem. It is a separator diagnostic, not a
full-song chart rule or proof of mixed-hit performance. No more transient/energy
threshold rescue on the exposed songs. Stop if the control cannot answer the
question. Independent validation and full-song m!sa acceptance still gate any
future promotion; KLEWS/Adapt stay outside tuning and prior rejected routes stay
closed.
