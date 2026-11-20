# DrumSep evidence on mixed-recording pipeline inputs — 2026-10-16

**The fixed snare/hi-hat energy diagnostic fails its pooled gate. Do not turn it
into a correction rule or retune it on these recordings.** A strong snare does
not establish that a simultaneous hi-hat is false. No charts or notes changed.

Root: `C:\Users\10ros\BeatSight-Recovery\2026-10-16-drumsep-mixed-validation-01`.
Read `protocol.json`, `gates-preparation.json`, `separated/completed.json`,
`family-evidence/metrics.json`, `evidence/independent-checks.json`,
`evidence/verification.json` and `evidence/final-artifact-manifest.json`.
The complete event table and review players are under `review/`.

## Fixed question and execution

The earlier [original-drum diagnostic](DRUMSEP_FAMILY_EVIDENCE_2026-10-16.md)
passed on exposed brush audio, AUROC .9478. This continuation asks whether its
unchanged feature works with the actual cached ADTOF input derived from mixed
recordings, and whether the result extends beyond that one brush case.

All six previously admitted ENST cases are retained: metal, musette brushes,
rock-60s, funk, charleston and bossa, totaling 446.32 seconds. None was selected
or removed based on new feature values. The previously quarantined IDMT items
remain excluded for their original annotation problems; no replacement selection.
KLEWS, Adapt and m!sa acceptance songs were not used.

Each original input mixture was `.5*(wet drums + accompaniment)`, divided by
its mono peak and processed by htdemucs_ft. The saved separator output is mono,
44.1-kHz FLOAT. Source code, run hashes, full durations and mixture peak divisors
were checked. That exact cached mono PCM is duplicated into two identical
channels for DrumSep, with gain 1 and no further normalization or resampling.
Both channels and their mono fold round-trip exactly. ADTOF and htdemucs_ft were
not rerun. This tests a practical cached pipeline input; compared with the prior
oracle test, both upstream separation and the stereo-to-mono representation
differ. It does not isolate either as the cause of a changed result.

The same previously verified six-stem checkpoint, pinned native source and
runtime are reused read-only. There were no downloads or package installations.
Native settings remain seed 0, two CPU threads, AMP, no TF32, deterministic
algorithms, chunk 130,560 samples, overlap 4, batch 1, no TTA or normalization.
All 319 checkpoint tensors load exactly and match the prior tensor digests.
Thirty-six finite FLOAT output stems cover all six complete inputs and pass
exact PCM readback. Total observed inference time is 31.18 seconds and peak
allocated CUDA memory is 1,105,517,056 bytes; these are execution observations,
not a speed benchmark. Native source/runtime and training-overlap limitations
from the earlier report still apply.

Protocol SHA-256:
`33069477942da5b5f7a1a7e906189b9ef9eced4b184aa3398385669bbf769a71`.
Its 68 protected entries bind code, checkpoint/source, inputs, prior predictions,
labels and assignments. No amendments or failed inference runs were needed.

## Predeclared measurement and decision

Use exactly the previous feature at each existing ADTOF HH prediction:
`10*log10((snare_mean_square + 1e-12)/(hh_mean_square + 1e-12))`, from a
50-ms stereo window starting at its rounded sample position. No fitted timing,
window, normalization, threshold, gain or model variant. Source-conditioned
positive cases are unmatched HH within 50 ms of an SD reference; negatives are
all matched HH, including genuine simultaneous SD+HH. Other false HH remain in
the event table and are not silently reclassified.

Before reading new feature values, criteria were frozen: pooled AUROC >= .8,
positive median > 0 dB and matched-HH median < 0 dB; those same numerical gates
on every eligible recording; at least two eligible recordings including one
nonbrush. Eligibility requires at least ten examples in each group. All six
recordings still contribute to the pooled result. Small per-recording groups
are descriptive/inconclusive, never replacements or exclusions.

| Recording | Target false HH | Matched HH | AUROC | False/true median dB | Individual status |
|---|---:|---:|---:|---:|---|
| Metal | 0 | 192 | Undefined | n/a / -41.410 | Small group |
| Musette brushes | 145 | 49 | .909360 | +.645 / -42.840 | Pass |
| Rock-60s | 7 | 115 | .997516 | +46.307 / -19.998 | Small group |
| Funk | 2 | 223 | .840807 | +23.144 / -18.266 | Small group |
| Charleston | 7 | 222 | .981982 | +28.247 / +4.897 | Small group; true-HH median has wrong sign |
| Bossa | 0 | 224 | Undefined | n/a / -14.897 | Small group |
| **Pooled** | **161** | **1,025** | **.692077** | **+2.960 / -19.299** | **Fails AUROC** |

The pooled ranking fails the .8 gate. Only one recording has sufficient groups,
so the separate breadth requirement is also unmet. Good descriptive AUCs for
tiny nonbrush groups cannot override this decision. Brush still passes its own
criterion, but that does not rescue the six-recording result.

The feature ranks within some recordings better than across recordings. This
is a measured limitation of comparing instrument energy levels across songs,
not evidence that a fitted per-song gain or threshold would generalize. No such
repair was attempted. AUROC is not note accuracy or transcription F1.

## Failure evidence

The full table contains 1,302 HH predictions: 161 targeted false hits, 1,025
matched hits and 116 other false hits. Ninety targeted false hits have
snare-dominant energy, but so do **338 matched HH** (33.0%). Of those 338, 230
have both SD and HH source references within 50 ms. All remain in the analysis.
These are descriptive signs of the frozen feature, not an applied deletion rule.
The other 20 snare-dominant false HH remain separately identified.

The fixed review selects two lowest positive scores and two highest matched-HH
scores per recording, taking all when fewer exist. Twenty cases have 100 exact
one-second mix/cached-drum/snare/HH/tom clips. All six waveform panels and the
full-recording feature plot were inspected. Source contexts and observations:

- Metal at 63.290/31.340 s and rock at 69.690/.480 s: genuine SD+HH references
  coincide with dominant snare-stem transients. A weaker HH stem is not absence.
- Brushes at 10.000/17.980 s: targeted false HH have very weak snare-stem output
  despite nearby SD labels. At 69.330 s, genuine SD+HH coexist with dominant SD.
- Funk at 55.780/14.650 s: genuine SD+HH can score about +45 dB, comparable to
  the false-HH case at 47.190 s. Raw energy ratio cannot safely equate those hits.
- Charleston at 22.450/20.720 s: genuine SD+HH score +47.814/+39.076 dB,
  exceeding the two reviewed false-HH cases (+22.943/+23.857 dB).
- Bossa at 38.630/30.590 s: source HH+KD+OT labels coincide with strong
  snare-stem output, illustrating that stem names and reference families are
  not interchangeable. No labels were remapped or masked.

This is waveform and source-label inspection, not listening-verified relabeling.
Individual microphone bleed, annotation limitations and separator leakage remain
possible explanations; no causal claim is inferred from these plots alone.

Independent dot-product calculations reproduce all 7,812 stem energy windows
over 1,302 predictions (maximum score error 1.42e-14 dB). Rank-sum AUC reproduces
each defined result and the pooled score. Six independent ordered matching
checks reproduce the cached HH cardinality and total timing-error objectives.
Group membership, medians, zero-sign counts and the final failed decision agree.

## Preservation and next boundary

All 2,147 prior artifacts verify, including the completed first DrumSep audit.
Ninety-seven preexisting source/docs files are snapshotted before changes; the
new helper/report extend the final snapshot. All 2,815 existing baseline events
remain untouched. No app/default/user-chart changes or full-song accuracy gain
are claimed. D:/F: stay read-only. Ignored/untracked assets and the WHITE WAVES,
Death Before Dishonor and Knuckles corrections/35 targets remain intact.
The previous 90-test log is protected, not rerun; this standalone experiment
uses actual model execution and independent data checks. No inference remains
running. C: preservation is not an independent-device backup.

**Close this fixed relative-energy hypothesis for note correction.** Do not
rescue it with threshold/window/gain sweeps, track dropping, a brush-only special
case or blanket HH/CY suppression. The saved separator capability can support
other justified questions, but its stem energy is not sufficient evidence of
instrument absence. Earlier E-GMD replacement/merger and ADT_STR failures stay
closed; Separate-and-Detect remains deferred.

Next, before another model run, audit the locally available aligned ENST
individual-microphone evidence for the fixed reviewed genuine SD+HH and false-HH
cases. Establish whether direct HH-presence evidence survives the existing
separators, distinguishing attenuation from the faulty dominance assumption.
Microphone bleed is supporting evidence, not automatic ground truth. This should
produce one predeclared, independently checkable presence test or a documented
stop; do not launch another metric tweak. Use a new scoped C: root and no broad
downloads. Any later correction still needs independent validation and complete
m!sa practice-view acceptance before promotion.
