# BeatSight Status (November 27, 2025)

## Snapshot
- Desktop reference build: ✅ shipping-quality playback experience and editor skeleton remain green; the live-input experiment has been shelved and its code/config removed to reduce maintenance drag.
- AI pipeline: 🟢 **Training actively running** (warm-up probe step 5a). Hardware-optimized configs created, class weighting added, environment hook implemented. **NEW: Cutting-edge 2024 techniques added. ⭐ RECOMMENDED: Path G (V5 Ultimate, modes 17a-17d) for production training.**
- Web pivot: 🟢 **Priority 1-3 COMPLETE, Verifier Dashboard polish in progress**. Backend scaffold now includes Modal GPU orchestration, SSE streaming, S3 storage, notifications, map edit proposals, type generation, quality/robustness improvements, and verifier diff visualization.
- Documentation: 🟢 consolidated under `docs/Guidebook.md`; historical logs preserved in `docs/archive/`.
- **AI Integrations Verification: ✅ All 39 features in `MISSING_INTEGRATIONS.md` verified as fully implemented and robust.**
- **Desktop/Web Alignment Audit: ✅ Schema alignment verified. Backend `AIGenerationOptions` now matches desktop `AiGenerationOptions`.**

## Session Progress (November 27, 2025)

### Cutting-Edge Training Enhancements (COMPLETE)
- ✅ **Gradient Centralization**: `training/optimizers/gradient_centralization.py`
  - Centralizes gradients to zero-mean before optimizer step (+0.5-1% improvement)
  - Works with any optimizer (AdamW, SGD, etc.)
  
- ✅ **Stochastic Depth (DropPath)**: `training/utils/stochastic_depth.py`
  - Layer-level dropout for regularization (+0.5-1%)
  - Configurable drop rate with linear scaling
  
- ✅ **BEATs Foundation Model**: `training/models/beats.py`
  - Microsoft's audio foundation model (+2-3% potential)
  - Alternative to Wav2Vec2 with better drum classification potential
  - New modes: 18a-18c (beats-warmup, beats-short, beats-long)
  
- ✅ **Deep Supervision**: `training/losses/deep_supervision.py`
  - Auxiliary classification heads at intermediate layers (+1-2%)
  - Better gradient flow throughout network
  
- ✅ **CNN v5 Ultimate Model**: `training/models/cnn_v5.py`
  - Combines ALL innovations: CoordAttn + DropPath + Deep Supervision + Multi-Scale Fusion
  - Three sizes: small (0.5M), base (2.0M), large (4.5M) parameters
  - New modes: 17a-17d (v5-warmup through v5-full)
  
- ✅ **Training Script Integration**: `train_classifier.py`
  - Added --model-version v5/beats choices
  - Added --use-gradient-centralization, --use-deep-supervision flags
  - Added --drop-path-rate, --v5-size arguments
  
- ✅ **Training Tools Updated**:
  - `auto_train.sh`: Modes 17a-17d (v5) and 18a-18c (beats)
  - `post_export_commands.sh`: Menu options for v5 and beats training
  
- ✅ **Documentation Updated**:
  - `CUTTING_EDGE_TRAINING_FEATURES.md`: Path G (V5 Ultimate), Path H (BEATs)
  - `ml_training_runbook.md`: New preset reference
  - `training/README.md`: Comprehensive model architecture docs

## Session Progress (November 26, 2025)

### Verifier Dashboard Polish (COMPLETE)
- ✅ **Diff Visualization Component**:
  - Created `ProposalDiffViewer.tsx` with user-friendly edit display
  - Color-coded action badges (green=add, red=remove, yellow=modify)
  - Time formatting, lane display, old→new value comparison
  - Collapsible raw JSON and full BSM content views
  - Updated `VerifierDashboardPage.tsx` queue and review modal

### Test & Warning Cleanup (COMPLETE)
- ✅ **Backend Tests**: 418 passing, 0 warnings
  - Fixed skipped `test_register_sends_welcome_email` with proper async mocking
  - Fixed FastAPI `on_event` deprecation → lifespan context manager pattern
  - Fixed async mock warnings with sync/async method separation in `create_mock_db()`
  - Added warning filter for internal AsyncMock library quirk

### Priority 3: Quality & Robustness (COMPLETE)
- ✅ **3.1 Error Handling Improvements**:
  - Fixed 3 broad exception handlers with specific types and logging
  - `PlaybackPlayfield.cs` - `InvalidOperationException` with debug logging
  - `ConfidenceHeatmap.cs` - `InvalidOperationException`, `ArgumentException` handling
  - `EditorTimeline.cs` - `IOException`, `JsonException` handling
  
- ✅ **3.2 Production TODOs Fixed**:
  - `karma.py` - Added `get_karma_history_count()` for proper COUNT query
  - `verifier.py` - Implemented `avg_review_time_hours` calculation via SQL
  - `metadata.py` - Added `ADMIN_SYSTEM` RBAC permission for cache clearing
  
- ✅ **3.3 Magic Number Constants**:
  - Consolidated timing windows to reference `DesignSystem.HitWindow*` constants
  - Extracted `DepthTolerance.ThreeDimensional` and `DepthTolerance.TwoDimensional`
  - Added `PastVisibilityBuffer` constant for clarity

### Web Backend Priority 2 (COMPLETE)
- ✅ **2.1 Notifications**: SendGrid email + WebPush notifications with pywebpush
  - `backend/app/services/notifications.py` - EmailBackend, WebPushBackend
  - `backend/app/models/push_subscription.py` - Browser push subscription model
  - Real email templates for job completion/failure
  
- ✅ **2.2 Map Edit Proposals**: User-submitted beatmap edit proposals
  - `backend/app/api/routes/map_edits.py` - POST/GET/DELETE endpoints
  - Status tracking: pending → merged/rejected/withdrawn
  - Full .bsm content storage for proposed changes
  
- ✅ **2.3 TypeScript Generation**: Type-safe API client
  - `frontend/openapi.json` - OpenAPI 3.1 spec regenerated
  - `frontend/src/types/api.generated.ts` - TypeScript types from spec
  - `AIGenerationOptions` type now matches desktop's `AiGenerationOptions`
  
- ✅ **2.4 Modal GPU Integration Tests**: 18 tests passing
  - `backend/tests/test_modal_gpu.py` - Comprehensive tests
  - GPU pricing estimation, callback verification, error handling

### CI Infrastructure & Docker Fixes (COMPLETE)
- ✅ **Docker Build Fixes**:
  - Fixed missing `README.md` copy for pyproject.toml metadata (commit fce3e4d)
  - Fixed missing `app/` source copy before pip install (commit b09tbcd)
  - Docker build now passes via `act`

- ✅ **Local CI with `act`** (replaced manual scripts):
  - Uses [`act`](https://github.com/nektos/act) to run **actual GitHub Actions workflows** in Docker
  - `./scripts/act-local.sh` - Lists jobs and runs them locally
  - Example: `./scripts/act-local.sh backend-lint` runs the real `ci.yml` backend-lint job
  - **100% parity with GitHub Actions** - no more "works locally, fails in CI"
  - Requires: Docker Desktop + `winget install nektos.act`

- ✅ **AI Pipeline Test Import Fixes**:
  - Fixed `ModuleNotFoundError` for `tests.test_utils` 
  - Changed imports to use `from test_utils import ...` directly
  - Updated: `conftest.py`, `test_onset_detection.py`, `test_training_pipeline.py`
  - 99 tests passing, 2 skipped

- ✅ **Validated All Checks**:
  - Backend lint: 0 errors
  - .NET: 90 tests passing
  - AI pipeline: 99 tests passing (2 skipped)
  - Updated `docs/CONTRIBUTING.md` with requirement to run `./scripts/act-local.sh` before pushing

### Desktop/Web Alignment Audit (Deep Dive)

**Verified against desktop source code:**

1. **DrumComponent Types** ✅ FIXED
   - Frontend now has 21 components matching desktop `DrumComponentCategory` + AI pipeline labels
   - Added: `rimshot`, `cross_stick`, `hihat_pedal`, `hihat_foot_splash`, `ride_bow`, `ride_bell`, `crash2`, `aux_percussion`, `cowbell`, `unknown`
   - Source: `desktop/BeatSight.Game/Mapping/LaneLayout.cs` + `ai-pipeline/training/configs/health_required_labels_prod.txt`

2. **AIJobCreate schema** ✅ FIXED
   - Updated to include all generation options from desktop
   - Source: `desktop/BeatSight.Game/AI/AiBeatmapGenerator.cs` → `AiGenerationOptions`

3. **HitObject.id field** ✅ ACCEPTABLE
   - Frontend needs `id` for React keys (desktop doesn't have it)
   - Solution: Generate client-side IDs when loading .bsm from API

4. **UserPreferences** 🟡 PARTIAL
   - Backend has ~15 settings; desktop has 50+ in `BeatSightConfigManager.cs`
   - Many desktop settings are platform-specific (window, frame limiter, visuals)
   - Sync-worthy settings (audio volumes, AI defaults, keybindings) should be added later

5. **Karma System** ✅ NOT GAMIFICATION
   - Backend karma is for community moderation (fixer/verifier roles for beatmap edits)
   - Similar to Stack Overflow reputation - controls edit privileges, not gameplay scoring
   - No practice scores, streaks, combos, or achievements exist

6. **Web Editor Scope** ✅ INTENTIONAL
   - TimelineEditor (581 lines) is simpler than desktop EditorScreen (4000+ lines)
   - Web focuses on review/edit of AI-generated maps, not full authoring
   - Full creation workflow is desktop-only

## Session Progress (November 25, 2025)

### Progress Tracking System
- ✅ Implemented `UserProgressManager` with JSON-based persistence
- ✅ Practice session tracking (loop regions, speed multipliers, duration)
- ✅ Favorites, tags, and notes per song
- ✅ Difficult section marking for focused rehearsal
- ✅ 20 unit tests for progress tracking (all passing)
- ✅ **Song Select integration** - Practice history displayed in BeatmapDetailsPanel
- ✅ **Favorite toggle button** - Quick access to mark/unmark favorites
- ✅ **Favorites filter** - Checkbox to show only favorited songs in carousel

### Code Quality
- ✅ Removed gamification (achievements, stats) - BeatSight is a practice tool, not a game
- ✅ Expanded `BeatmapLoaderTests` with 6 edge case tests (malformed files, validation errors)
- ✅ Fixed status document inconsistencies
- ✅ **Current test count: 90 tests** (all passing)

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
- **AI Training:** 🟢 Warm-up probe (step 5a) currently running. Monitor W&B for convergence metrics.
- **Web MVP Planning:** Architecture, schema, UX, and cost models are ready. Needs engineering tickets and service spikes.
- **Practice Mode:** ✅ Progress tracking implemented. Desktop app now persists practice history, favorites, and notes.
- **Test Coverage:** Test suite expanded to 90 tests. Additional edge cases for beatmap validation added.

## Web Frontend Progress (November 25, 2025)

### Latest Updates (Evening Session)
- ✅ **E2E Testing**: Playwright installed with Chromium
  - `e2e/auth.spec.ts` - Login/register flow tests
  - `e2e/navigation.spec.ts` - Navigation bar tests
  - `e2e/pwa.spec.ts` - PWA feature tests
  - `e2e/accessibility.spec.ts` - Accessibility tests
  - Scripts: `npm run test:e2e`, `test:e2e:ui`, `test:e2e:headed`

- ✅ **UI Polish Components**:
  - `Skeleton.tsx` - Loading placeholder components (12 variants)
  - `Toast.tsx` - Toast notification system with context provider
  - `useKeyboardShortcuts.tsx` - Keyboard shortcuts with help modal (press `?`)

- ✅ **CI/CD Pipelines**: GitHub Actions workflows
  - `.github/workflows/frontend.yml` - lint → test → build → e2e
  - `.github/workflows/backend.yml` - lint, test (postgres+redis), security, docker
  - `.github/workflows/desktop.yml` - build (Win/Mac/Linux), publish artifacts
  - `.github/workflows/ai-pipeline.yml` - lint, test (with ffmpeg)

- ✅ **API Documentation**: OpenAPI tags with descriptions for all 10 endpoint groups

- ✅ **TypeScript API Client**:
  - Installed `openapi-typescript` and `openapi-fetch`
  - `api/typedClient.ts` - Type-safe API client with auth middleware
  - `types/api.generated.ts` - Generated types (placeholder, run `npm run api:generate`)

- ✅ **Real-Time Job Updates (WebSocket)**:
  - Backend: `app/api/routes/websocket.py` - WebSocket endpoint at `/ws/jobs`
  - Frontend: `hooks/useJobWebSocket.ts` - React hook for real-time updates
  - Features: Job progress, completion, failure notifications via Redis pub/sub
  - Auto-reconnect, ping/pong keepalive, React Query cache integration

- ✅ **Rate Limiting Middleware**:
  - `app/services/rate_limit.py` - Sliding window rate limiting using Redis
  - Tier-based limits: anonymous (30/min), authenticated (100), premium (500), admin (1000)
  - Endpoint-specific limits for AI jobs and auth endpoints
  - X-RateLimit-* headers, Retry-After on 429
  - **Backend tests**: 358 passing (+13 billing tests)

- ✅ **Stripe Payment Integration**:
  - `app/services/stripe_service.py` - Full Stripe integration service
    - Checkout session creation for subscription upgrades
    - Customer portal for subscription management
    - Webhook handler for events (subscription create/update/delete, payment success/failure)
    - Subscription sync from Stripe to database
  - `app/api/routes/billing.py` - Billing endpoints:
    - `GET /billing/config` - Public Stripe configuration
    - `GET /billing/subscription` - Current subscription status
    - `POST /billing/checkout` - Create checkout session
    - `POST /billing/portal` - Create customer portal session
    - `POST /billing/webhook` - Handle Stripe webhooks
  - Plans: Free (3 jobs/month), Pro Monthly ($9.99, 100 jobs), Pro Yearly ($7.99/mo)
  - 13 comprehensive tests for billing service

- ✅ **Pricing Page** (`PricingPage.tsx`):
  - Monthly/yearly billing toggle with 20% yearly discount
  - Plan comparison cards with features
  - FAQ accordion section
  - Stripe checkout integration
  - Auth-aware CTA buttons

- ✅ **Landing Page** (`LandingPage.tsx`):
  - Hero section with animated gradient background
  - Stats display (19 drum classes, 85% accuracy, <2min processing)
  - 3-step how-it-works feature cards
  - Technology section with AI capabilities
  - Pricing preview cards
  - CTA section and footer with links

- ✅ **Subscription Management**:
  - `hooks/useBilling.ts` - React hooks for billing operations
  - `api/billing.ts` - Billing API client
  - `types/billing.ts` - TypeScript types for billing
  - `components/SubscriptionSettings.tsx` - Settings page subscription section
  - Quota display with progress bar

- ✅ **Environment & Config**:
  - `frontend/.env.example` - Frontend environment template
  - `vite.config.ts` - WebSocket proxy added
  - `frontend/README.md` - Updated with testing and env docs

### Completed Features
- ✅ **Authentication System**: JWT-based auth with login, register, token refresh
  - `authStore.ts` - Zustand store with persist middleware
  - `LoginPage.tsx`, `RegisterPage.tsx` - Full auth UI
  - `ProtectedRoute.tsx` - Route guard for authenticated pages
  - `UserMenu.tsx` - Dropdown with profile, settings, logout
  
- ✅ **Navigation Shell**: Responsive app layout
  - `NavigationShell.tsx` - Mobile menu, breadcrumbs, active route highlighting
  - Icons for all navigation items
  - Auth-aware navigation (different items for logged in/out)

- ✅ **PWA Support**: Progressive Web App configuration
  - `manifest.json` - App manifest with icons, shortcuts
  - `sw.js` - Service worker with offline caching
  - `offline.html` - Offline fallback page
  - `usePWA.ts` - Hooks for install prompt, online status, SW updates
  - `PWAPrompts.tsx` - Install banner, offline indicator, update notification

- ✅ **Core Pages**:
  - `LibraryPage.tsx` - Song library with search, filter, sort
  - `ProfilePage.tsx` - User profile with stats and activity
  - `SettingsPage.tsx` - Account, preferences, notifications settings
  - `UploadPage.tsx` - Drag-drop upload with progress
  - `JobQueuePage.tsx`, `JobDetailPage.tsx` - Job monitoring

- ✅ **Error Handling**:
  - `ErrorBoundary.tsx` - React error boundary with fallback UI
  - `LoadingSpinner`, `PageLoader`, `EmptyState` - Loading states

- ✅ **Integration Testing**:
  - Vitest + React Testing Library + MSW setup
  - 27 frontend tests covering:
    - Auth API (login, register, token refresh)
    - Songs API (CRUD operations)
    - AI Jobs API (create, status)
    - Auth UI (form validation, submission)
    - State management (auth store persistence)

### Backend Test Coverage
- **358 tests passing** across all services:
  - Billing/Stripe: 13 tests
  - Rate Limiting: 17 tests
  - WebSocket: 12 tests
  - RBAC System: 39 tests
  - AcoustID Integration: 27 tests  
  - Cloud Sync: 21 tests
  - Alert Thresholds: 31 tests
  - Auth, Jobs, Storage, Songs: remaining tests

### Desktop App Status
- Cloud sync interface stub created (`ICloudSyncService.cs`)
- Full implementation pending backend deployment to production
- Local playback, beatmap generation, and progress tracking fully functional

### API Documentation
- See `docs/WEB_API_REFERENCE.md` for complete endpoint documentation

## Reference Map
- Deep status log (Nov 2025): [`docs/archive/current_status_2025-11-12.md`](../archive/current_status_2025-11-12.md)
- Action backlog & option matrix: [`docs/archive/next_steps_2025-11-12.md`](../archive/next_steps_2025-11-12.md)
- Roadmap detail (pre-restructure): [`docs/archive/roadmap_2025-11-12.md`](../archive/roadmap_2025-11-12.md)
- Live input regression checklist (historical reference): [`docs/LIVE_INPUT_REGRESSION_CHECKLIST.md`](../LIVE_INPUT_REGRESSION_CHECKLIST.md)
- ML training SOP: [`docs/ml_training_runbook.md`](../ml_training_runbook.md)
- Web API Reference: [`docs/WEB_API_REFERENCE.md`](../WEB_API_REFERENCE.md)

_Update cadence: refresh this summary when a blocker clears or a focus area changes; archive the older snapshot under `docs/archive/` when you roll a new dated entry._

