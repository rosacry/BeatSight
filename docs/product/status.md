# BeatSight Status (November 24, 2025)

## Snapshot
- Desktop reference build: ✅ shipping-quality playback experience and editor skeleton remain green; the live-input experiment has been shelved and its code/config removed to reduce maintenance drag.
- AI pipeline: ✅ **Training pipeline audit complete.** Hardware-optimized configs created, class weighting added, environment hook implemented. Ready for warmup probe.
- Web pivot: 🟡 planning artifacts published (PRD, schema, UX, costs); backend FastAPI scaffold alive but workstreams not yet staffed.
- Documentation: 🟢 consolidated under `docs/Guidebook.md`; historical logs preserved in `docs/archive/`.
- **AI Integrations Verification: ✅ All 39 features in `MISSING_INTEGRATIONS.md` verified as fully implemented and robust.**
- **Training Pipeline Audit: ✅ Comprehensive review complete. See `ai-pipeline/training/TRAINING_AUDIT_REPORT.md`.**
- **Codebase Analysis: ✅ Full implementation status report generated. See [`IMPLEMENTATION_STATUS.md`](../../IMPLEMENTATION_STATUS.md).**

## Training Pipeline Improvements (November 24, 2025)

### New Files Created
- `ai-pipeline/training/tools/beatsight_env.sh` - Environment configuration hook
- `ai-pipeline/training/configs/hardware_profiles.json` - RTX 3080 Ti optimized presets
- `ai-pipeline/tests/test_training_pipeline.py` - Comprehensive training tests
- `ai-pipeline/training/TRAINING_AUDIT_REPORT.md` - Full audit documentation

### Training Enhancements
- Added `--class-weights` option (none/balanced/sqrt) for imbalanced classes
- Added `--label-smoothing` for regularization
- Improved `post_export_commands.sh` with logging and error handling
- Updated `ml_training_runbook.md` with hardware-specific commands

### Hardware Profile (Reference)
| Component | Specification |
|-----------|---------------|
| GPU | RTX 3080 Ti FE (12GB VRAM) |
| CPU | AMD Ryzen 9800X3D (8-core) |
| RAM | 32GB DDR5-6000 |
| Storage | Samsung 990 Pro NVMe |

## AI & Model Integrations Verification (November 24, 2025)

A comprehensive code review was performed against all items in `MISSING_INTEGRATIONS.md`. All features marked as completed are verified as implemented:

### Song Select Screen (10/10 ✅)
- **AI Generation Indicators**: Badge, confidence score, model version all display from `AiGenerationMetadata`
- **Filtering & Sorting**: Confidence filter, genre dropdown, "Date Generated" sort mode
- **Metadata Display**: Source, Release Date, Tags, Provider fields in `BeatmapDetailsPanel`
- **Creation Workflow**: "New from Audio (AI)" button triggers import workflow

### Playback Screen (6/6 ✅)
- **Drum Stem Mixing**: `MixerOverlay` with Mute/Solo/Balance, volume bindables for backing and drum tracks
- **Confidence Heatmap**: `ConfidenceHeatmap` component loads debug.json and renders color-coded timeline
- **Ghost Note Scoring**: 1.5x lenient timing windows for notes with velocity < 0.4
- **Loop Low Confidence**: Auto-loop sections below confidence threshold
- **Custom Sample Loading**: `loadCustomSamples()` reads from `DrumKit.CustomSamples` dictionary

### Editor Screen (13/13 ✅)
- **Generation Panel**: "Run Pipeline" and "Logs" buttons in inspector panel
- **Parameter Controls**: All AI parameters (confidence, sensitivity, quantization, tempo hints, etc.)
- **Extended Metadata Fields**: Release Date, Provider, Description inputs
- **Region Re-generation**: `regenerateRegion()` processes time selection with custom parameters
- **Stem Waveform Toggle**: `showDrumStem` bindable switches between full track and drum stem
- **Onset Markers**: Cyan vertical lines drawn in `EditorTimeline` debug layer
- **Debug Visualization**: Yellow confidence peaks from debug.json
- **Pipeline Logs**: Real-time log overlay with scrolling output

### Settings Screen (10/10 ✅)
- **AI Pipeline Configuration**: Dedicated `AISettingsSection` category
- **Python Environment Path**: TextBox bound to `PythonPath` setting
- **Model Checkpoints**: Dropdown with v1.0/v2.0 options
- **GPU/CUDA Toggle**: Checkbox bound to `UseGpu` setting
- **Custom Model Path**: TextBox for .pth file path
- **AcoustID API Key**: Masked TextBox for external service
- **Default Generation Settings**: Quantization dropdown, sensitivity slider, auto-generate toggle
- **Cache Management**: Buttons to clear feature_cache and separation temp directories

## Critical Actions
1. **Hardware unblock** – wait for the replacement HDD (due today), then migrate `prod_combined_profile_run`, `feature_cache`, checkpoints, W&B offline runs, and any other heavyweight assets from the old WSL mounts fully onto `C:` so Git Bash/.NET workflows stay on the native volume.
2. **Centralise data paths** – ✅ landed. `common_paths.py`, training CLI defaults, the environment hook (`ai-pipeline/training/tools/beatsight_env.sh`), and `post_export_commands.sh` now resolve everything from `BEATSIGHT_DATA_ROOT`/friends.
3. **Script refresh** – ✅ complete. All training utilities consume the new env hook; documentation examples point to the helper script.
4. **Dataset export (runbook step 4)** – execute `build_training_dataset.py` for `prod_combined_events.jsonl`, run the checklist, and log outputs per `docs/ml_training_runbook.md`.
5. **Warm-up probe (runbook step 5a)** – run the cached probe, then evaluate it immediately using the criteria in the runbook (per-class recall >0.25, confusion shrinkage, W&B F1 trend, loss curve behaviour, misclassified audit).
6. **Long run gate** – only launch step 5c after the probe passes the checks; monitor W&B confusion matrices during the long run and re-evaluate with `--fraction 0.3` before promoting.
7. **Web MVP staffing** – pick a kick-off focus (queue infrastructure, fingerprint service, or UX shell) and translate `docs/web_mvp_task_breakdown.md` into issues.

## Active Initiatives
- **AI Readiness:** Cambridge ingest restored, weights refreshed, BEATSIGHT env hook merged. Awaiting drive delivery and final data migration before exporter + retrain resume.
- **Web MVP Planning:** Architecture, schema, UX, and cost models are ready. Needs engineering tickets and service spikes.
- **Practice Mode Polish:** Stage 0.2 hygiene landed; waveform view, blur shader, and hit-lighting are the next desktop polish tasks.
- **Performance Mode Exploration:** low-risk design spikes for optional scoring overlays are underway; no runtime changes until accuracy metrics and hardware input plans solidify.

## Reference Map
- Deep status log (Nov 2025): [`docs/archive/current_status_2025-11-12.md`](../archive/current_status_2025-11-12.md)
- Action backlog & option matrix: [`docs/archive/next_steps_2025-11-12.md`](../archive/next_steps_2025-11-12.md)
- Roadmap detail (pre-restructure): [`docs/archive/roadmap_2025-11-12.md`](../archive/roadmap_2025-11-12.md)
- Live input regression checklist (historical reference): [`docs/LIVE_INPUT_REGRESSION_CHECKLIST.md`](../LIVE_INPUT_REGRESSION_CHECKLIST.md)
- ML training SOP: [`docs/ml_training_runbook.md`](../ml_training_runbook.md)

_Update cadence: refresh this summary when a blocker clears or a focus area changes; archive the older snapshot under `docs/archive/` when you roll a new dated entry._
