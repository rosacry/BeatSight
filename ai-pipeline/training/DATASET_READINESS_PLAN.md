# BeatSight Drum Dataset Plan (Phase 1)

> Goal: a production-grade, leakage-safe, multi-label, dynamics-aware drum event corpus that generalizes across players, kits, rooms, and mic chains—and supports future tasks (openness, technique, velocity regression) without re-collecting data.

---

## 1) Target Capabilities

| Capability | Details | Notes |
|------------|---------|-------|
| Instrument taxonomy | `kick`, `snare`, `rimshot`, `cross_stick`, `hihat_closed`, `hihat_open`, `hihat_pedal`, `hihat_foot_splash`, `ride_bow`, `ride_bell`, `crash`, `crash2`, `splash`, `china`, `tom_high`, `tom_mid`, `tom_low`, `aux_percussion` | Keep `components.json` extensible; include `aliases` and GM mappings. |
| Multi-label events | Any sample may include multiple simultaneous components | Represent as `components: [...]` with per-component attributes. |
| Dynamics | Bucketed (`ghost/light/medium/accent`) and continuous `velocity ∈ [0,1]` | Derive buckets from loudness plus annotator tags; retain raw velocity with provenance. |
| Hi-hat openness | Continuous openness `openness ∈ [0,1]` plus discrete tags (`closed/open/pedal`) | Normalize e-drum CC4 to openness; preserve raw controller values. |
| Technique/position | `strike_position` (center, rim, edge, bell), `stick_type` (stick, brush, rod, mallet), crash `choke` flag, kick `pedal` (`left/right`) | Optional now; keep schema fields reserved. |
| Timing | High-precision `onset_time`, optional `offset_time`, beat/bar indices, tempo, meter (ms) | Enables microtiming analysis. |
| Calibration | Report ECE/Brier; maintain reliability diagrams per class and dynamic bucket | Required for stable downstream thresholds. |

---

## 2) Sources & Licensing

| Source | Type | License (verify) | Status | Integration Plan |
|--------|------|------------------|--------|------------------|
| BeatSight `.bsm` + audio | Labeled from editor | Project-owned | Available | `collect_training_data.py --extract-beatmap` → event slices + provenance YAML |
| ENST-Drums | Multitrack stems + MIDI | Verify research/redistribution terms | Pending | Align MIDI to taxonomy per kit; export per-mic and summed bounces |
| Groove MIDI Dataset | MIDI (+ some audio) | Verify (likely CC-BY-4.0 for MIDI) | Pending | Map GM kit to taxonomy; synth stems where live audio missing; tag synthetic |
| Magenta/DDSP drums | MIDI + rendered audio | Verify CC-BY | Optional | Fill tail classes; mark `is_synthetic=true` |
| User-contributed recordings | Multitrack/mixes | Contributor agreement | Planned | Checklist + rights grant (training, redistribution terms) |

Action: maintain `LICENSES.md` with each source’s terms; include contributor Data Use Agreement (training rights, withdrawal process). Synthetic content must be flagged. Provide a **feature-only release option** (log-mel features or deterministic embeddings defined in `featurespec.yaml`) when audio redistribution is restricted; audio is then access-controlled but provenance hashes remain identical.

---

## 3) Structure & Schema

```
training_data/
  metadata.json                 # {schema_version, created_at, owners}
  components.json               # taxonomy + aliases + GM map
  licenses/                     # LICENSES.md, contributor agreements (ids)
  provenance/                   # YAML per import batch
  audio/
    <split>/{wav,flac}/<session_id>/<sample_id>.wav
  annotations/
    events.jsonl                # event-level rows
  splits/
    split_config.yaml           # rules + seeds
    <name>/train.txt, val.txt, test.txt
  health_reports/
    <date>_health.json
```

### `events.jsonl` (one event per line)

```json
{
  "sample_id": "uuid",
  "session_id": "uuid",
  "track_id": "uuid",
  "drummer_id": "uuid",
  "kit_id": "uuid",
  "room_id": "uuid",
  "source_set": "BeatSight",
  "is_synthetic": false,
  "audio_path": "audio/train/wav/<session_id>/<sample_id>.wav",
  "sample_rate": 48000,
  "bit_depth": 24,
  "channels": 1,
  "onset_time": 12.345,
  "offset_time": 12.510,
  "tempo_bpm": 124.0,
  "meter": "4/4",
  "bar_index": 23,
  "beat_index": 2,
  "components": [
    {
      "label": "snare",
      "velocity": 0.73,
      "dynamic_bucket": "accent",
      "strike_position": "center",
      "openness": null,
      "choke": false,
      "pedal": null
    },
    {
      "label": "hihat_closed",
      "velocity": 0.52,
      "dynamic_bucket": "medium",
      "openness": 0.05,
      "openness_raw": 23,
      "choke": false,
      "pedal": null
    },
    {
      "label": "kick",
      "velocity": 0.68,
      "dynamic_bucket": "accent",
      "openness": null,
      "choke": null,
      "pedal": "left"
    }
  ],
  "context_ms": {"pre": 80, "post": 220},
  "label_method": "human",
  "per_component_confidence": {"snare": 0.97, "hihat_closed": 0.84},
  "bleed_level": "med",
  "mix_context": "full_mix",
  "processing_chain": {"bus_comp": true, "limiter": true, "saturation": false},
  "negative_example": false,
  "notes": "",
  "tags": ["accent", "flam"],
  "mic_setup": {
    "type": "close+overheads",
    "notes": "57 on snare top, KM184 OH"
  },
  "mix_notes": "no bus comp",
  "loudness": {"LUFS_i": -22.1, "peak_dbfs": -2.3},
  "qc": {
    "labeler_ids": ["u1", "u9"],
    "status": "accepted",
    "agreement": {"kappa": 0.82},
    "audio_qc": {"clipping": false, "noise_flag": false}
  }
}
```

JSONL scales better than CSV for nested multi-label attributes and per-component details.

**Windowing policy:** use class-specific context windows (e.g., pre 60–120 ms, post 200–600 ms with longer tails for cymbals). Store the actual values applied per slice in `context_ms`.

### 3.1 Audio Format & Resampling Policy

* Canonical training format: 48 kHz, 24-bit PCM, mono (retain stereo where spatial cues matter and annotate `channels=2`).
* Sampling pipeline: SoX-HQ or libsamplerate "best sinc" for SRC; apply TPDF dither only when exporting 24→16 bit derivatives.
* Channel handling: when collapsing to mono, use energy-preserving `mono = 0.5*(L+R)`; store `channels_original` and `sample_rate_original` in provenance.
* File invariants (CI): reject audio with DC offset > 0.5%, peaks > 0 dBFS, or malformed headers; health checks surface violations.
* Provenance: record a `resample_chain` array per asset detailing each transform (SRC, dither, normalization) and tool version.

### 3.2 Tempo/Meter Timeline

Maintain a session-level sidecar `session_timeline/<session_id>.json` that captures tempo and meter evolution:

```json
{
  "session_id": "uuid",
  "tempo_curve": [
    {"time": 0.0, "tempo_bpm": 128.0},
    {"time": 45.2, "tempo_bpm": 132.0}
  ],
  "meter_changes": [
    {"time": 0.0, "meter": "4/4"},
    {"time": 92.0, "meter": "7/8"}
  ]
}
```

Events continue to log their local `tempo_bpm`/`meter`, but beat and bar indices are computed against this timeline to guarantee consistency during tempo or meter changes.

---

## 4) Splitting & Leakage Control

* Primary split key: `session_id`.
* Isolation groups: ensure the same drummer, kit, or room never crosses splits in baseline.
* Recommended policy: GroupKFold on `(drummer_id, kit_id, room_id)` with seed-controlled stratification by class counts. Stratify by `mix_context` and ensure no single `source_set` exceeds 40% of any split.
* Synthetic isolation: synthetic examples never exceed 20% of train and 10% of val/test; maintain a synthetic-only diagnostic micro-test.
* OOD packs: dedicate `test_ood/` with e-drums, heavy bus-compression mixes, unusual rooms, brushes/mallets.

### 4.1 Multi-mic Alignment QC

* Alignment check: estimate per-session inter-mic delays via transient-focused cross-correlation; flag |delay| > 0.25 ms or drift > 1 sample/min.
* Reporting: optionally persist `mic_geometry` (mic positions/distances) and `alignment_report.json` summarizing delays and drift.
* Gate: sessions with unresolved misalignment are excluded from validation/test splits and marked in train with `alignment_warning=true`.

---

## 5) Quality Workflow

1. Ingest → pending events + auto-features (`loudness`, crest factor, spectral centroid).
2. Dual labeling (25–30%): two annotators; disagreements → adjudication queue. Track Cohen’s kappa per class.
3. Audio QC pass: clipping, DC offset, extreme noise, metronome bleed; fix or reject.
4. Dedup and near-dup: audio fingerprints + spectral similarity; cap dup rate ≤ 0.5% per split; remove cross-split families.
5. Normalization: LUFS target per class for training slices (store raw + normalized if needed).
6. Annotator rubric: maintain `docs/labeling_guidelines.md` with canonical examples (ghost vs light, rimshot vs center, ride bow vs crash edge).
7. Calibration pack: 200-clip pack for monthly annotator calibration; track per-annotator accuracy and drift.
8. Deterministic slicing: extractor seeds and DSP versions logged; CI verifies byte-identical crops on rerun.
9. Acceptance gate: block merges violating class balance, dup caps, split isolation, or rubric compliance.

---

## 6) Augmentation (class-aware)

* Phase-safe time shift, small pitch shift for drums, random onset jitter (±5 ms).
* Room IR convolution library (tag IR id).
* EQ/compression saturation emulations (subtle) and additive noise from room tones.
* Per-class rules: avoid long pitch shifts on cymbals; allow moderate on toms/kick; hi-hat openness unaffected by augmentation.
* Capture crash choke behaviour explicitly (shortened envelopes) either via labeled samples or augmentation that applies envelope truncation + decay.
* Offer kick double-stroke augmentation (paired hits with realistic spacing and velocity ratios) when real data is scarce, but always tag synthetic patterns.
* Adversarial processing pack: randomized bus compression, brickwall limiting, bit-depth reduction, MP3/OGG roundtrip, smartphone mic IR—tagged via `processing_chain`.
* Guardrails: do not pitch-shift cymbals beyond ±2%; constrain time-stretch to ±3%; never alter openness labels via augmentation or stretch crash choke envelopes.
* Record every augmentation in provenance for reproducibility.

### Negatives & Hard-Negatives

* Maintain a curated negative pool: handclaps, finger snaps, table/desk knocks, keyboard clicks, metronomes, stick clicks without drum contact, speech plosives, door thuds.
* Weekly `hard_negative_miner.py` harvests false positives from recent model runs on full mixes; clips enter labeling queue; log outputs in `negatives_manifest.jsonl`.
* Keep negatives:positives ratio near 1:4 in training batches; ensure negatives span the same room/mic distribution as positives.
* Reference inputs: `training/examples/hard_negative_predictions_example.jsonl` (predictions) and `training/examples/hard_negative_events_example.jsonl` (ground truth sample) illustrate the JSONL schemas consumed by `hard_negative_miner.py`.

### 6.1 E-drum Vendor Normalization

* Normalize hi-hat openness from CC4 per device using vendor/model-specific curves and calibration offsets; store `device_vendor`, `device_model`, `openness_curve_id`, and `openness_calibration_offset`.
* Persist raw controller data (`openness_raw` 0–127) alongside normalized `openness ∈ [0,1]` to retain reversibility.
* Gate: each e-drum device must cover at least seven deciles of openness distribution in hats data or remains train-only until coverage improves.
* Calibration assets: maintain `training/calibration/openness_curves.json` with audited breakpoints and versioned curve IDs; provenance for each event references the curve id applied by `normalize_openness.py`.

### 6.2 Long-Duration Techniques & Rudiments

* Extend `components.json` articulations for sustained or rudimental events (`buzz`, `double_stroke_roll`, `multiple_bounce`, `swirl`, `swell`).
* Require `offset_time` for these events and restrict augmentation time-stretch to ±1% to protect envelope cues.
* Gate: accumulate ≥ 300 high-quality long-duration events (snare/cymbal focus) with verified offsets before training sign-off.

---

## 7) Dataset Health & Reports

Nightly `dataset_health.py` should emit:

* Per-class counts (real vs synthetic), dynamic bucket histograms, hi-hat openness histogram.
* Dup/near-dup rate, loudness distribution, clipping rate.
* Split isolation checks (no shared drummer/kit/room/session across splits).
* Annotator agreement by class; confusion hot-spots from a probe model; fairness snapshots by genre/tempo/room.
* Export HTML and JSON report to `health_reports/`.
* Enforce coverage gates: global floor via `--min-class-count`, bespoke label floors with `--min-counts-json`, must-have labels via repeatable `--require-label`, and duplicate rate ceilings through `--max-duplication-rate`.
* Flag taxonomy drift by capping `--max-unknown-labels` (default 0) and surface diffs via HTML summaries generated with `--html-output`. Manage required coverage lists via `training/configs/health_require_labels_example.txt`, and seed per-label minima with `training/configs/health_min_counts_example.json`; update both with release-specific thresholds before shipping.
* Gate regressions before shipping by diffing the candidate health report against the last approved baseline with `training/compare_health_reports.py` (block merges if per-class totals regress beyond the agreed tolerance or if new gates fail). Keep the blessed baseline JSON under `training/reports/health/` so CI can retrieve it without extra setup, and archive the CI-produced candidate/baseline diff artifacts for release sign-off.

### 7.1 Streaming Boundary Pack

* Assemble `boundary_pack/` containing events whose onsets fall within the final and initial N frames of adjacent analysis windows (sliding inference scenario).
* Track recall/precision on these boundary clips; add CI checks ensuring boundary recall ≥ 0.95 at the production operating point.
* Reference samples: see `training/examples/boundary_labels_example.jsonl` for label shape and `training/examples/boundary_predictions_example.jsonl` for compatible model outputs.
* Generate fresh packs with `training/generate_boundary_pack.py` by sliding the production window/hop over annotated sessions and exporting the resulting JSONL.

---

## 8) Versioning, Storage & CI

* Data control: DVC (preferred) or git-lfs for audio; remote object storage; SHA256 per file; access controlled via role-based permissions and audit logs.
* Semantic versions: `drums-vMAJOR.MINOR.PATCH`.
* Release artifacts: `CHANGELOG.md`, `health.json`, split seeds, `training_config_hash`, small 10-second per-class demo pack (if license permits).
* CI checks (blocking): schema validation, split isolation, dup cap, health thresholds, license compliance, file hashes.

---

## 9) Evaluation Protocol

* Metrics: per-class precision/recall/F1, macro/micro F1, example-based F1, subset accuracy, label ranking average precision, coverage error, Hamming loss, AUROC, AUPRC, ECE, Brier score.
* Timing: Onset F1@±20 ms and ±50 ms, Offset F1@±80 ms (where measurable).
* Regression: openness MAE/R²; velocity MAE and Spearman ρ (where MIDI ground truth exists).
* Calibration by bucket: ECE per dynamic bucket and openness quartile.
* Breakdowns: drummer, kit, room, dynamic bucket, hi-hat openness deciles, SNR bins, augmentation presence, synthetic vs real, streaming boundary pack.
* Confusions to watch: rimshot vs snare, ride bow vs crash, hihat closed vs snare ghost.
* Thresholding: calibrate on validation via Platt/temp scaling; per-class thresholds optimized for cost, plus open-set rejection thresholding on max-posterior or dedicated rejection head.
* Latency & throughput: Real-Time Factor on target CPU (4-core laptop) and mobile; profile quantized and full-precision variants.
* OOD tests: separate report for `test_ood` and `test_ood_unknown` (open-set percussion, negatives, ambience).

### 9.1 Multi-label Set & Open-set Metrics

* Compute example-based F1, subset accuracy, Hamming loss, label ranking AP, and coverage error for holistic multi-label assessment.
* Evaluate open-set rejection with AUROC/AUPRC using `test_ood_unknown`; report FPR@95%TPR for known-class retention.
* Establish acceptance gate: open-set AUROC ≥ 0.90 on `test_ood_unknown`.
* Example assets: `training/examples/openset_ground_truth_example.jsonl` and `training/examples/openset_predictions_example.jsonl` illustrate the JSONL formats consumed by `openset_eval.py`.

### 9.2 Statistical Significance & Release Checks

* For each release, bootstrap 1,000 resamples to produce 95% CIs for macro-F1, onset F1@±50 ms, and openness MAE.
* Block a release if the new model’s CI is strictly worse than the previous release by >3 macro-F1 points or >0.02 openness MAE.
* Archive CIs in `reports/<version>/bootstrap_metrics.json` for traceability.
* Example JSONL inputs for `bootstrap_eval.py` live in `training/examples/bootstrap_ground_truth_example.jsonl` (ground truth) and `training/examples/bootstrap_predictions_example.jsonl` (model outputs).

---

## 10) Acceptance Gates (Phase 1)

* Coverage: ≥ 1,500 real events for kick, snare, hats, crash; ≥ 800 for others; ≥ 300 for tail classes.
* Technique coverage: ≥ 400 crash events with `choke=true`; ≥ 600 double-kick pairs (both pedals represented) with pedal attribution.
* Dynamics: each frequent class has ≥ 200 events per bucket (`ghost/light/medium/accent`).
* Hi-hat: ≥ 2,000 labeled hat events with openness across deciles.
* Negatives: ≥ 5,000 labeled negatives spanning all rooms; false-positive rate on negatives ≤ 1.0% at operating point.
* Bleed/mix diversity: each split has ≥ 30% `full_mix` examples; `bleed_level` buckets present in all splits.
* Synthetic cap: synthetic ≤ 20% of train, ≤ 10% of val/test per class.
* Annotator agreement: mean kappa ≥ 0.75 on dual-labeled subset; no class < 0.6.
* Dup rate: ≤ 0.5% per split (families merged).
* Timing: Onset F1@±50 ms ≥ 0.90 for kick/snare/hihat on test, ≥ 0.80 on `test_ood`; Offset F1@±80 ms ≥ 0.75 where measured.
* Regression: Hi-hat openness MAE ≤ 0.10 (0–1 scale) on test; velocity MAE ≤ 0.12 on datasets with MIDI ground truth.
* Calibration: ECE ≤ 0.08 on validation; ≤ 0.10 on test (overall and per dynamic bucket).
* Latency: Real-Time Factor ≤ 0.2 on target CPU (batch=1 streaming). Failure blocks release.
* Diversity: each split contains ≥ 20 unique drummers, ≥ 10 unique kits, and tempo coverage across slow (<90 BPM), medium (90–140 BPM), fast (>140 BPM) bins.
* Multi-label set performance: example-based F1 ≥ 0.88 on test, ≥ 0.80 on `test_ood`.
* Open-set robustness: AUROC ≥ 0.90 and FPR@95%TPR ≤ 10% on `test_ood_unknown`.
* Mic alignment: unresolved alignment rate ≤ 1% of sessions in any split; boundary recall ≥ 0.95 on `boundary_pack`.
* Audio format compliance: 100% of assets match canonical format or explicitly declare exceptions with provenance; zero files clip above 0 dBFS.

Merges failing any gate are rejected.

---

## 11) Tooling Deliverables

| Tool | Purpose | Owner |
|------|---------|-------|
| `collect_training_data.py` v2 | Batch manifests; per-component attrs; openness; provenance; audio stats | Dev agent |
| `label_ui` MVP | Spectrogram + waveform; multi-label; openness slider; keyboard hotkeys; adjudication log | Dev agent |
| `dataset_health.py` | Reports and HTML dashboards; CI status emit | Dev agent |
| `splitter.py` | GroupKFold by drummer/kit/room; seeds; OOD pack construction | Dev agent |
| `dedupe.py` | Audio fingerprints + spectral similarity; family detection | Dev agent |
| `augmenter.py` | Class-aware recipes; IRs; logs to provenance | Dev agent |
| `schema_validator.py` | JSON schema for `events.jsonl` and `components.json` | Dev agent |
| `hard_negative_miner.py` | Harvest & curate model false positives into negative set | Dev agent |
| `calibration.py` | Temperature/Platt scaling + reliability diagrams export | Dev agent |
| `feature_dump.py` (`featurespec.yaml`) | Frozen DSP spec & deterministic feature exporter | Dev agent |
| `eval_timing.py` | Onset/offset metrics @ tolerances; regression MAE suite | Dev agent |
| `rt_benchmark.py` | Real-time factor/latency on target devices; quantization checks | Dev agent |
| `align_qc.py` | Multi-mic delay/drift estimation and gating | Dev agent |
| `openset_eval.py` | Unknown-class AUROC/AUPRC & FPR@TPR curves | Dev agent |
| `boundary_eval.py` | Streaming window boundary recall tests | Dev agent |
| `bootstrap_eval.py` | Metric confidence intervals & regression checks | Dev agent |
| `generate_boundary_pack.py` | Build streaming boundary packs from annotated events | Dev agent |

---

## 12) Taxonomy & Mapping (`components.json`)

```json
{
  "schema_version": "1.0",
  "classes": [
    {"id": "kick", "aliases": ["bd", "bass_drum"], "gm": [36]},
    {"id": "snare", "aliases": ["sd"], "gm": [38, 40]},
    {"id": "rimshot", "aliases": ["snare_rimshot"]},
    {"id": "cross_stick", "aliases": ["sidestick"], "gm": [37]},
    {"id": "hihat_closed", "gm": [42, 44]},
    {"id": "hihat_open", "gm": [46]},
    {"id": "hihat_pedal", "gm": [44]},
    {"id": "hihat_foot_splash"},
    {"id": "ride_bow", "gm": [51]},
    {"id": "ride_bell", "gm": [53]},
    {"id": "crash", "aliases": ["crash_1"], "gm": [49, 57]},
    {"id": "crash2", "aliases": ["crash_2"]},
    {"id": "splash"},
    {"id": "china", "aliases": ["china_1"]},
    {"id": "china2", "aliases": ["china_2"]},
    {"id": "tom_high", "gm": [50]},
    {"id": "tom_mid", "gm": [47, 48]},
    {"id": "tom_low", "gm": [45, 43]},
    {"id": "aux_percussion"}
  ],
  "groups": {
    "drums": ["kick", "snare", "rimshot", "cross_stick", "tom_high", "tom_mid", "tom_low"],
    "cymbals": ["hihat_closed", "hihat_open", "hihat_pedal", "hihat_foot_splash", "ride_bow", "ride_bell", "crash", "crash2", "splash", "china", "china2"],
    "aux": ["aux_percussion"]
  },
  "mutually_exclusive_subclasses": {
    "ride": ["ride_bow", "ride_bell"],
    "hihat_state": ["hihat_closed", "hihat_open", "hihat_pedal", "hihat_foot_splash"]
  }
}
```

### 12.1 ID Stability & Deprecation

* Treat `sample_id` as immutable; deleting or replacing samples produces a `tombstones.jsonl` entry `{sample_id, reason, replaced_by?}`.
* Maintain `redirects.jsonl` for legacy-to-current ID mapping when clips are re-sliced; ingestion CI forbids reuse of historical IDs.
* Release notes enumerate any deprecations and associated tombstones to preserve reproducibility.

---

## 13) Governance, Ethics & Safety

* Dataset card: document sources, kit/room distributions, annotator process, known limitations (underrepresented genres, brushes).
* Model card: intended use (transcription, education), out-of-scope (redistribution of copyrighted stems, surveillance), failure modes.
* Privacy: no voices; remove speech fragments; takedown process for contributors.
* Licensing: ensure training/redistribution rights; mark synthetic vs real; respect third-party terms.
* Access control: role-based permissions and audit logs on dataset pulls; hash verification on ingest/release.
* Takedown SLA: respond within five business days; tombstone IDs preserved; retrain notes recorded.
* Bias monitoring: per-genre/tempo/room/kit performance table appended to dataset card.

---

## 14) Unlabeled Pretraining (Optional)

* Aggregate drum-heavy unlabeled audio (license-compatible) and run self-supervised pretraining (contrastive, masked spectrogram).
* Use labeled set primarily for supervised fine-tuning and calibration.
* Track uplift on tail classes and OOD robustness.

---

## 15) Immediate Next Steps

1. Finalize schema and validators (`events.jsonl`, `components.json`, JSON schema files).
2. Ship `splitter.py` with group isolation + seeds; write splits for v0.1.
3. Upgrade `collect_training_data.py` to emit multi-label, openness, and provenance.
4. Label UI prototype with multi-label, openness slider, hotkeys, adjudication log.
5. Stand up CI checks (schema, splits, dup cap, license checks, deterministic slicing).
6. Implement `hard_negative_miner.py` pipeline with `negatives_manifest.jsonl`.
7. Draft contributor agreement + `LICENSES.md` and access-control policy.
8. Create first health report and define baseline acceptance gates.
9. Ship new QA/eval utilities (`align_qc.py`, `boundary_eval.py`, `openset_eval.py`, `bootstrap_eval.py`) and wire into CI.
10. Capture vendor-specific CC4→openness calibration curves and encode them in `components.json` + provenance.
11. Build streaming `boundary_pack/` and `test_ood_unknown` splits for open-set evaluation.

---

Document owner: AI Pipeline Team

Last updated: 2025-11-04
