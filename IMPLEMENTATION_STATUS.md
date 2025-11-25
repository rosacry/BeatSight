# BeatSight Implementation Status Report
*Generated: November 24, 2025*  
*Last Updated: November 24, 2025*  
*Analysis Scope: Full Codebase*  
*Analyzer: GitHub Copilot (Claude Opus 4.5)*

---

## Executive Summary

| Category | Count | Notes |
|----------|-------|-------|
| **Total Items Requiring Attention** | 24 | Across all priority levels (23 resolved this session) |
| **Critical Blockers** | 2 | Hardware migration, GPU orchestration |
| **High Priority** | 1 | Data migration completion |
| **Medium Priority** | 10 | Remaining polish features |
| **Low Priority / Nice-to-have** | 11 | Future enhancements, optimizations |

### Session Progress (Nov 24)
- ✅ Added backend service tests (`test_songs.py`, `test_ai_jobs.py`)
- ✅ Fixed placeholder documentation in `CONTRIBUTING.md`
- ✅ Renamed `UnitTest1.cs` → `DetectionStatsTests.cs`
- ✅ Added XML documentation to `PlaybackPlayfield.cs` timing constants
- ✅ Enhanced TODO comment in `ai_jobs.py` with implementation guidance
- ✅ **Implemented tempo disambiguation algorithm** in `TempoAuthority.cs` with multi-factor scoring
- ✅ **Added low-confidence banner** to `MappingGenerationScreen.cs`
- ✅ **Created 56 web MVP tickets** in `docs/product/web_mvp_tickets.md`
- ✅ **Added comprehensive GenerationCoordinator tests** (cancellation, error handling, state transitions)
- ✅ **Added comprehensive GenerationStagePlan tests** (edge cases, boundary conditions)
- ✅ **Added generation logging** to `AiBeatmapGenerator.cs` (`[gen] notes=... bpm=... lanes=...`)
- ✅ **Fixed cancellation propagation** in `DemucsExternalProcessBackend.probeDemucs`
- ✅ **Implemented JWT authentication** - `auth.py` service, routes, and dependencies
- ✅ **Created API Reference** - `docs/API_REFERENCE.md` (comprehensive endpoint docs)
- ✅ **Created Deployment Guide** - `docs/DEPLOYMENT.md` (Docker, Azure, security)
- ✅ **Created Cloud Sync Protocol** - `docs/CLOUD_SYNC_PROTOCOL.md` (versioning, delta sync, conflict resolution)
- ✅ **Implemented Karma Service** - `backend/app/services/karma.py` (roles, thresholds, ledger)
- ✅ **Karma API Routes** - Stats, history, leaderboard, role checks
- ✅ **Key Bindings UI** - Controls settings section with 4-8 lane configs
- ✅ **3D Background Effects** - Beat sync, starfield parallax, intensity modes
- ✅ **Skin Editor Screen** - Preview gallery, lane visualization, skin management
- ✅ **View Transition Animations** - 2D/3D/Manuscript entry/exit effects in ViewTransitionManager
- ✅ **Backend Environment Config** - Comprehensive .env.example with 50+ settings
- ✅ **Beatmap Creation Guide** - User documentation in docs/BEATMAP_CREATION_GUIDE.md
- ✅ **Onboarding Flow** - First-run tutorial screen with 5-page walkthrough

### Current State Overview
- **Desktop Application**: ✅ Shipping-quality. Playback, editor, and song selection are functional.
- **AI/ML Pipeline**: 🟡 Training infrastructure ready, awaiting data migration completion.
- **Backend (Web MVP)**: 🟡 Scaffolded, 56 tickets created, **auth implemented**. Ready for core feature work.
- **Mobile**: 🔴 Not started. Queued for Phase 3.

---

## 1. Critical/Blocking Issues

### 1.1 Hardware & Data Migration (✅ COMPLETED)

| File/Location | Issue | Description | Status | Suggested Action |
|--------------|-------|-------------|--------|------------------|
| `E:/data/prod_combined_profile_run/` | ✅ Data migration complete | Dataset successfully moved from C: to E: drive (436GB, 16.3M files) | ✅ Done | Proceed with training |
| `C:/github/BeatSight/data/feature_cache/` | Feature cache on SSD | Keeping on SSD for training performance | ✅ Optimal | No action needed |
| `ai-pipeline/training/` | Training unblocked | Config files updated to point to new E: drive location | ✅ Ready | Run step 5a from `post_export_commands.sh` |

**Migration Details (completed Nov 25, 2025):**
- Source: `C:\github\BeatSight\data\prod_combined_profile_run`
- Destination: `E:\data\prod_combined_profile_run`
- Total: 435.984 GB across 16,282,317 files in 517 directories
- Duration: ~9 hours
- Speed: 14.7 MB/s (~845 MB/min)

### 1.2 Web MVP Infrastructure

| File/Location | Issue | Description | Suggested Action |
|--------------|-------|-------------|------------------|
| `backend/` | Scaffolded only | FastAPI backend exists but has no workers/queue infrastructure | ✅ Engineering tickets created: `docs/product/web_mvp_tickets.md` (56 tickets) |
| `backend/app/api/routes/ai_jobs.py` L25 | TODO: Authentication | `requested_by=None` hardcoded; user auth not wired | Implement authentication before web launch |
| `docs/web_compute_costs.md` | GPU orchestration undecided | No decision on Modal vs Batch vs custom | Prototype GPU job infrastructure |

---

## 2. Incomplete Implementations

### 2.1 Tempo Disambiguation System

| File | Line(s) | Issue | Description | Suggested Action |
|------|---------|-------|-------------|------------------|
| `desktop/.../TempoAuthority.cs` | 50-100 | ~~Half/double-time errors~~ | ✅ **FIXED Nov 24**: Added `ResolveAmbiguousTempo()` and `ComputeTempoScore()` | Disambiguation now picks best candidate |
| `desktop/.../GenerationPipeline.cs` | 279-288 | ~~Raw tempo passthrough~~ | ✅ Now uses resolved tempo from `TempoAuthority.Evaluate()` | Working correctly |
| `desktop/.../OnsetDetectionService.cs` | 354-396 | Tempo weighting | `selectPrimaryCandidate()` uses coverage-based scoring | Working correctly |
| `personal_notes/notes.txt` L275 | ~~Documented gap~~ | ✅ **RESOLVED**: Tempo disambiguation implemented | Tests added |

### 2.2 Desktop Application Gaps

| File | Line(s) | Issue | Description | Suggested Action |
|------|---------|-------|-------------|------------------|
| `desktop/.../ThreeDHighwayBackground.cs` | - | ✅ **FIXED Nov 24** | Beat sync, starfield parallax, intensity modes implemented | Complete |
| `desktop/.../ViewTransitionManager.cs` | - | ✅ **FIXED Nov 24** | View-specific entry/exit animations with 2D/3D/Manuscript effects | Complete |
| `desktop/.../SettingsScreen.cs` | - | ✅ **FIXED Nov 24** | Skin editor screen created with preview gallery | Complete |
| `desktop/.../MainMenuScreen.cs` | 335 | PlaceholderScreen class | Generic placeholder screen still exists | Remove or repurpose |

### 2.3 ~~Missing~~ Low-Confidence Handling ✅

| File | Issue | Description | Suggested Action |
|------|-------|-------------|------------------|
| `MappingGenerationScreen.cs` | ✅ **FIXED Nov 24** | Added `lowConfidenceBanner` with contextual advice | Prominent banner shows after generation |
| `OnsetDetectionService.cs` | ✅ Implemented | `DetectionStats.GetConfidenceIssues()` provides guidance | Working correctly |
| `AiBeatmapGenerator.cs` | Missing instrumentation | No `[gen] notes=…` log after load; missing BPM/grid summary | Add detailed generation logging |

---

## 3. Missing Features

### 3.1 Features Documented as "Coming Soon"

| Feature | Location | Status | Priority |
|---------|----------|--------|----------|
| Key Bindings customization | `docs/archive/.../FEATURE_LIST.md` L102 | ✅ **Implemented Nov 24** | Complete |
| Performance Graph | `docs/archive/.../FEATURE_LIST.md` L117 | Not started | Low |
| Song filtering/search | `docs/archive/.../FEATURE_LIST.md` L144 | ✅ Complete - text search, sort, genre, confidence | Low |
| Random song selection | `docs/archive/.../FEATURE_LIST.md` L145 | ✅ Added Nov 24 - Random button + SelectRandom() | Low |
| Hit Error Meter | `docs/archive/.../FEATURE_LIST.md` L63 | Not started | Low |

### 3.2 Web/Mobile Platforms

| Feature | Status | Notes |
|---------|--------|-------|
| Web application | Planning complete | PRD, schema, UX, costs documented; needs engineering tickets |
| iOS app | Not started | Flutter planned; queued for Phase 3 |
| Android app | Not started | Flutter planned; queued for Phase 3 |
| Real-time microphone scoring | Shelved | Live input experiment removed to reduce maintenance |

### 3.3 AI/ML Capabilities

| Feature | Status | Notes |
|---------|--------|-------|
| Production ML model | Training ready | Awaiting data migration + warm-up probe |
| Multi-technique detection | Partially implemented | Ghost notes, flams, rolls in model definition |
| Velocity estimation | Implemented | In `DrumClassifierCNN` |
| VR mode | Not started | Queued for Phase 4 |

---

## 4. Integration Gaps

### 4.1 Desktop ↔ AI Pipeline

| Integration | Status | Gap Description | Action Required |
|-------------|--------|-----------------|-----------------|
| Tempo authority | ✅ **Working** | `TempoAuthority.Evaluate` injects BPM/offset/step into options; `BeatmapTimebaseSynchroniser.Apply` synchronizes post-generation | Complete |
| Debug metadata binding | ✅ **Working** | Real-time binding via `onStatsChanged`/`onAnalysisChanged`; placeholder shown during early stages (expected) | Complete |
| Cancellation propagation | ✅ **Working** | Propagated through all services; `probeDemucs` fixed to poll with cancellation | Complete |

### 4.2 Backend ↔ Desktop

| Integration | Status | Gap Description | Action Required |
|-------------|--------|-----------------|-----------------|
| Beatmap sync | ✅ **Designed Nov 24** | `docs/CLOUD_SYNC_PROTOCOL.md` - version vectors, delta sync, conflict resolution | Implementation next |
| User authentication | ✅ **Implemented Nov 24** | JWT auth with register/login/refresh endpoints | `poetry install` to add `python-jose` |
| Karma system | ✅ **Implemented Nov 24** | `backend/app/services/karma.py` - roles, thresholds, API routes | Complete |

### 4.3 All 39 AI Integration Features

Per `MISSING_INTEGRATIONS.md` verification (Nov 24, 2025): **✅ All 39 features verified as implemented**

- Song Select Screen: 10/10 ✅
- Playback Screen: 6/6 ✅
- Editor Screen: 13/13 ✅
- Settings Screen: 10/10 ✅

---

## 5. AI/ML Pipeline Status

### 5.1 Training Pipeline

| Component | Status | Notes |
|-----------|--------|-------|
| `train_classifier.py` | ✅ Ready | Class weighting, label smoothing added |
| `DrumSampleDataset` | ✅ Ready | float16 cache, torchaudio optimization |
| `DrumClassifierCNN` | ✅ Ready | ~385K params, 24 classes |
| Hardware configs | ✅ Created | RTX 3080 Ti optimized in `configs/hardware_profiles.json` |
| Environment hook | ✅ Created | `beatsight_env.sh` centralizes paths |
| Post-export script | ✅ Improved | Logging, error handling added |

### 5.2 Model Architecture

| Aspect | Details |
|--------|---------|
| Architecture | 4 conv blocks → global avg pool → dropout → FC |
| Parameters | ~385,000 |
| Input | (N, 1, 128, 128) mel spectrograms |
| Output | 24 drum component classes |
| Inference | CPU real-time capable |

### 5.3 Inference Integration

| Component | Status | Notes |
|-----------|--------|-------|
| `AiBeatmapGenerator.cs` | ✅ Functional | Launches Python process, parses results |
| `drum_classifier.py` | ✅ Dual-mode | ML and heuristic fallback |
| `ml_drum_classifier.py` | ✅ Complete | PyTorch inference wrapper |
| Model loading | ✅ Works | Auto-resolves from `ai-pipeline/models/` |

### 5.4 Data Pipeline

| Status | Details |
|--------|---------|
| Manifests | `prod_combined_events.jsonl` with 3M+ events |
| Audio sources | Slakh2100, Groove MIDI, Cambridge Multitrack, MUSDB18 |
| Export tool | `build_training_dataset.py` with Rich progress |
| Validation | `dataset_health.py` generates JSON + HTML reports |
| **Current blocker** | Data migration from C: to E: in progress |

---

## 6. Technical Debt

### 6.1 Code Quality Issues

| File | Line(s) | Issue | Description | Suggested Action |
|------|---------|-------|-------------|------------------|
| `ai-pipeline/transcription/drum_classifier.py` | L66 | SimpleDrumClassifier | Heuristic classifier retained as fallback | ✅ Documented as intentional fallback |
| `ai-pipeline/tests/` | Various | Mock/Dummy classes | `_Dummy`, `MockDataset`, etc. proliferate | ✅ Consolidated into test_utils.py |
| `desktop/.../EditorScreen.cs` | 3792-3793 | Dummy track objects | `dummyTrack` variable naming | Rename to more descriptive name |
| `desktop/.../Program.cs` | 229 | Reflection hack | Uses reflection to access private `is_debug_build` field | Document or find alternative |

### 6.2 Deprecated/Retired Code

| Component | Status | Notes |
|-----------|--------|-------|
| Live input tracking | Removed | `MicrophoneCapture`, `LiveInputHudOverlay` removed Nov 2025 |
| `PracticeModeScreen` | Shelved | Legacy replay host; functionality folded into `PlaybackScreen` |
| `ResultsScreen` | Shelved | To be re-integrated when performance mode returns |
| `NoSeparationBackend.cs` | Retained | Superseded by `PassthroughBackend` but kept as placeholder |

### 6.3 Magic Numbers / Hardcoded Values

| File | Line(s) | Value | Description | Status |
|------|---------|-------|-------------|--------|
| `PlaybackPlayfield.cs` | 34 | `5000` | `ApproachDuration` default | ✅ Documented, dynamically adjusted by speed multiplier |
| `PlaybackPlayfield.cs` | 41-53 | `35,80,130,180,220` | Timing windows | ✅ Named constants with XML documentation in #region |
| `PlaybackPlayfield.cs` | 59 | `1f` | `PlayfieldWidthRatio` | ✅ Named constant, documented |
| `BeatmapLoader.cs` | Various | `0`, `1` | Hit object count thresholds | Define meaningful constants |

---

## 7. Test Coverage Gaps

### 7.1 Desktop Tests (`BeatSight.Tests`)

| Test File | Coverage | Gaps |
|-----------|----------|------|
| `UnitTest1.cs` | Empty template | Default file; should be removed or populated |
| `BeatmapLoaderTests.cs` | Basic load | Missing edge cases, malformed file tests |
| `BeatmapLibraryTests.cs` | Exists | Need to verify comprehensive coverage |
| `GenerationCoordinatorTests.cs` | Exists | Covers basic flow |
| `GenerationPipelineResultTests.cs` | Exists | Covers result handling |
| `EditorScreenSnapshotTests.cs` | Exists | Reflection-based testing |

**Missing test coverage:**
- Stage progress mapper (noted in `personal_notes/notes.txt`)
- Ready/Running UI guard scenarios
- Offline decode behavior
- Cancellation propagation
- Low-confidence warning display

### 7.2 AI Pipeline Tests (`ai-pipeline/tests`)

| Test File | Status | Notes |
|-----------|--------|-------|
| `test_training_pipeline.py` | ✅ New | Comprehensive training tests added Nov 24 |
| `test_drum_classifier.py` | ✅ Exists | Classifier integration |
| `test_dataset_health.py` | ✅ Exists | Dataset validation |
| `test_onset_detection.py` | ✅ Exists | Onset detection |
| `test_lane_assignment.py` | ✅ Exists | Lane heuristics |
| `test_process_pipeline.py` | ✅ Exists | End-to-end pipeline |

### 7.3 Backend Tests

| Test File | Status | Notes |
|-----------|--------|-------|
| `test_health.py` | ✅ Exists | Health endpoint only |
| `test_songs.py` | ✅ Added | Song service CRUD coverage |
| `test_ai_jobs.py` | ✅ Added | Job lifecycle coverage |

---

## 8. Documentation Needs

### 8.1 Missing Documentation

| Document | Purpose | Priority | Status |
|----------|---------|----------|--------|
| API reference | Backend endpoint documentation | High | ✅ **Created Nov 24** - `docs/API_REFERENCE.md` |
| Deployment guide | Production deployment steps | High | ✅ **Created Nov 24** - `docs/DEPLOYMENT.md` |
| Beatmap creation guide | User-facing tutorial | Medium | ✅ **Created Nov 24** - docs/BEATMAP_CREATION_GUIDE.md |
| Contribution workflow | Developer onboarding | Medium | Partially covered in `CONTRIBUTING.md` |

### 8.2 Outdated Documentation

| Document | Issue | Action Required |
|----------|-------|-----------------|
| `docs/CONTRIBUTING.md` | ~~Placeholder email~~ | ✅ Fixed Nov 24 - now points to GitHub Issues |
| `docs/archive/.../QUICKSTART.md` L267 | Placeholder Discord: "(placeholder - create community server)" | Create server or remove |
| `docs/archive/roadmap_2025-11-12.md` L391-392 | Placeholder community links | Update or remove |

### 8.3 Well-Maintained Documentation ✅

- `docs/Guidebook.md` - Consolidated reference
- `docs/product/status.md` - Current status
- `docs/product/roadmap.md` - Phase overview
- `docs/ml_training_runbook.md` - Training SOP
- `docs/ARCHITECTURE.md` - System design
- `docs/BS_FILE_FORMAT.md` - Beatmap format spec
- `docs/API_REFERENCE.md` - Backend API documentation (NEW)
- `docs/DEPLOYMENT.md` - Production deployment guide (NEW)
- `ai-pipeline/training/TRAINING_AUDIT_REPORT.md` - Training audit

---

## 9. Configuration & Setup Issues

### 9.1 Environment Variables

| Variable | Purpose | Status |
|----------|---------|--------|
| `BEATSIGHT_DATA_ROOT` | Data storage root | ✅ Documented in `beatsight_env.sh` |
| `BEATSIGHT_DATASET_DIR` | Dataset directory | ✅ Documented |
| `BEATSIGHT_CACHE_DIR` | Feature cache | ✅ Documented |
| `BEATSIGHT_USE_ML_CLASSIFIER` | ML toggle | ✅ Documented |
| `BEATSIGHT_ML_MODEL_PATH` | Model override | ✅ Documented |

### 9.2 Missing Configuration

| Configuration | Purpose | Status |
|---------------|---------|--------|
| CUDA/cuDNN versions | Training reproducibility | 🟡 Noted as open item in runbook |
| Production Python path | Deployment | ✅ Documented in .env.example |
| Backend environment | Web deployment | ✅ **Enhanced Nov 24** - Comprehensive .env.example with 50+ settings |

### 9.3 Platform-Specific Setup

| Platform | Documentation | Status |
|----------|---------------|--------|
| Windows | `README.md` | ✅ Complete |
| Linux | `SETUP_LINUX.md` | ✅ Complete |
| macOS | `SETUP_MACOS.md` | ✅ Complete - Added Nov 24 |
| iOS/Android | Not applicable yet | Phase 3 |

---

## 10. UI/UX Incomplete Elements

### 10.1 Placeholder UI Components

| Component | File | Description | Priority |
|-----------|------|-------------|----------|
| ~~PlaceholderScreen~~ | ~~`MainMenuScreen.cs` L335~~ | ✅ Removed Nov 24 | ~~Low~~ |
| Debug overlay placeholder text | `DetectionDebugOverlay.cs` | "Waiting for analysis..." | Complete (intentional UX) |
| ~~Skin editor toggle~~ | ~~`SettingsScreen.cs` L2325~~ | ✅ Full SkinEditorScreen added Nov 24 | ~~Medium~~ |

### 10.2 UI Features Pending

| Feature | Status | Notes |
|---------|--------|-------|
| Tutorial/onboarding | ✅ **Complete** | OnboardingScreen with 5-page walkthrough |
| In-app help | ✅ **Complete** | HelpOverlay with F1 toggle, context-aware shortcuts |
| Keyboard rebinding UI | ✅ **Complete** | Controls settings section with per-lane-count inputs |
| Theme customization | Partial | `DesignSystem.cs` exists; no user UI |

### 10.3 Mobile UI

| Aspect | Status | Notes |
|--------|--------|-------|
| Touch-optimized playback | Not started | Phase 3 |
| Simplified editor | Not started | Phase 3 |
| Beatmap browser | Not started | Phase 3 |

---

## Appendix A: All TODO/FIXME Comments

### Backend
| File | Line | Comment |
|------|------|---------|
| `backend/app/api/routes/ai_jobs.py` | 25 | `# TODO: wire authenticated user id` |

### Desktop (C#)
No explicit `TODO` or `FIXME` comments found in source files.

### AI Pipeline (Python)
No explicit `TODO` or `FIXME` comments found in core source files.

### Documentation
| File | Line | Comment |
|------|------|---------|
| `docs/archive/.../QUICKSTART.md` | 102 | `# TODO section` reference |
| `docs/archive/.../QUICKSTART.md` | 286 | `### 📋 TODO` header |

---

## Appendix B: Feature Completion Matrix

### Audio Processing
| Feature | Status | Notes |
|---------|--------|-------|
| Audio file import (multiple formats) | ✅ Complete | MP3, WAV, OGG, FLAC, M4A, AAC |
| Stem separation (drums from full mix) | ✅ Complete | Demucs HTDemucs v4 |
| Tempo/BPM detection | ✅ Complete | librosa-based |
| Time signature detection | ✅ Complete | 4/4 default with override |
| Metadata extraction | ✅ Complete | Embedded tags + MusicBrainz fallback |

### Drum Transcription (AI/ML)
| Feature | Status | Notes |
|---------|--------|-------|
| Onset detection | ✅ Complete | Spectral flux + envelope following |
| Instrument classification | ✅ Complete | 24 classes (kick, snare, hi-hat variants, etc.) |
| Velocity estimation | ✅ Complete | In ML model |
| Technique detection | 🟡 Partial | Ghost notes, flams in model; rolls pending |
| Model training pipeline | ✅ Ready | Awaiting data migration |
| Model inference integration | ✅ Complete | Desktop ↔ Python bridge works |
| Confidence scoring | ✅ Complete | Per-onset confidence |

### Beatmap System
| Feature | Status | Notes |
|---------|--------|-------|
| Beatmap file format (.bsm) | ✅ Complete | JSON-based, documented |
| Beatmap editor | ✅ Complete | Full timeline editor |
| Import from osu! | ✅ Complete | `.osu` parsing |
| Export capabilities | ✅ Complete | Save/export .bsm |
| Beatmap validation | ✅ Complete | `BeatmapLoader.Validate()` |

### Visualization Modes
| Feature | Status | Notes |
|---------|--------|-------|
| 2D mode (highway/lane) | ✅ Complete | `TwoDimensionalLaneViewEnhanced` |
| 3D mode (spatial) | ✅ Complete | `ThreeDimensionalHighwayViewEnhanced` |
| Manuscript mode (notation) | ✅ Complete | `ManuscriptViewEnhanced` |
| Mode switching | ✅ Complete | Toggle in playback/editor |
| Customizable layouts | 🟡 Partial | Presets exist; full customization pending |

### Playback & Learning
| Feature | Status | Notes |
|---------|--------|-------|
| Audio sync with visualization | ✅ Complete | <10ms target |
| Speed adjustment | ✅ Complete | 0.0-2.0x range |
| Loop sections | ✅ Complete | `PracticeOverlay` |
| Progress tracking | 🔴 Not started | No persistent progress |
| Performance scoring | 🔴 Shelved | Live input removed |

### User Experience
| Feature | Status | Notes |
|---------|--------|-------|
| Settings/preferences | ✅ Complete | Comprehensive `SettingsScreen` |
| Keyboard customization | ✅ Complete | Controls settings section with per-lane inputs |
| Tutorial/onboarding | ✅ Complete | OnboardingScreen with 5-page walkthrough |
| In-app help | ✅ Complete | HelpOverlay with F1 toggle, context-aware |

---

## Appendix C: File-by-File Analysis (Key Files)

### Desktop Application

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `BeatSightGame.cs` | 2047 | ✅ Stable | Main game class |
| `PlaybackScreen.cs` | 2783 | ✅ Complete | Primary playback |
| `EditorScreen.cs` | 4052 | ✅ Complete | Full editor |
| `SettingsScreen.cs` | 2400+ | ✅ Complete | All settings |
| `SongSelectScreen.cs` | 1000+ | ✅ Complete | Beatmap browser |
| `MappingGenerationScreen.cs` | 2000+ | ✅ Complete | AI generation UI |
| `AiBeatmapGenerator.cs` | 624 | ✅ Complete | Python bridge |
| `GenerationPipeline.cs` | 820+ | 🟡 Needs work | Tempo authority gap |
| `PlaybackPlayfield.cs` | 790 | ✅ Complete | Lane rendering |

### AI Pipeline

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `process.py` | 392 | ✅ Complete | Main entry point |
| `beatmap_generator.py` | 774 | ✅ Complete | Beatmap output |
| `drum_classifier.py` | 285 | ✅ Complete | Dual-mode classifier |
| `ml_drum_classifier.py` | 319 | ✅ Complete | CNN model |
| `onset_detector.py` | 200+ | ✅ Complete | Detection |
| `train_classifier.py` | 1140 | ✅ Enhanced | Training script |
| `build_training_dataset.py` | 1500+ | ✅ Complete | Dataset export |

### Backend

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `main.py` | 33 | ✅ Scaffold | FastAPI entry |
| `services/songs.py` | 65 | ✅ Basic | Song CRUD |
| `services/ai_jobs.py` | 55 | ✅ Basic | Job lifecycle |
| `models/*.py` | Various | ✅ Defined | SQLAlchemy models |

---

## Appendix D: Recommended Priority Order

### Immediate (This Week)
1. ⏳ **Wait for data migration** to complete (robocopy C: → E:)
2. 🔬 **Run warm-up probe** (step 5a) after migration
3. 📊 **Evaluate probe results** per ML runbook checklist

### Short-Term (Next 2 Weeks)
4. 🎯 **Complete long training run** if probe passes
5. ~~🔧 **Fix tempo disambiguation** in `GenerationPipeline.cs`~~ ✅ **DONE**
6. 🧪 **Add missing unit tests** for state machine, progress mapper
7. ~~📝 **Add low-confidence banner** to `MappingGenerationScreen`~~ ✅ **DONE**

### Medium-Term (Next Month)
8. ~~🌐 **Staff web MVP engineering tickets**~~ ✅ **DONE** - 56 tickets in `docs/product/web_mvp_tickets.md`
9. 🔐 **Implement backend authentication**
10. 🎨 **Complete skin editor** (remove placeholder status)
11. ⌨️ **Build keyboard rebinding UI**
12. 📱 **Begin Flutter mobile prototype**

### Long-Term (Quarter)
13. 🚀 **Launch web MVP** with queue infrastructure
14. 📊 **Implement progress tracking** system
15. 🎤 **Revisit live input/scoring** once measurement confidence is high
16. 🥽 **Explore VR mode** prototype

---

## Appendix E: Data Location Reference

✅ **Data Migration Completed** (Nov 25, 2025)

| Data Type | Location | Drive | Notes |
|-----------|----------|-------|-------|
| Dataset (`prod_combined_profile_run`) | `E:/data/prod_combined_profile_run` | HDD | 436GB, 16.3M files |
| Feature Cache | `C:/github/BeatSight/data/feature_cache/` | SSD | Kept on SSD for training performance |
| Checkpoints/Runs | `C:/github/BeatSight/ai-pipeline/training/runs/` | SSD | Training outputs |

**Configuration files updated:**
- `ai-pipeline/training/common_paths.py` - Default `dataset_root()` now returns `E:/data/prod_combined_profile_run`
- `ai-pipeline/training/tools/beatsight_env.sh` - `BEATSIGHT_SECONDARY_ROOT` set to `/e/data`
- `ai-pipeline/training/tools/post_export_commands.sh` - Dataset path updated
- `ai-pipeline/training/tools/ingest_and_build.sh` - Output directory updated

**To run training:**
```bash
cd /c/github/BeatSight
source ai-pipeline/training/tools/beatsight_env.sh
bash ai-pipeline/training/tools/post_export_commands.sh
# Select option 5a for warmup training
```
3. Execute step 5a from `post_export_commands.sh`

---

*End of Implementation Status Report*
