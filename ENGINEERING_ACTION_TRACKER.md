# BeatSight Engineering Action Tracker

> **Created:** December 3, 2025  
> **Last Updated:** December 3, 2025  
> **Status:** 🟡 In Progress

This document tracks all engineering work identified during the comprehensive codebase analysis. Each item must be completed - no skipping or avoiding issues.

---

## 📊 Overall Progress

| Category | Total | Complete | In Progress | Not Started |
|----------|-------|----------|-------------|-------------|
| 🔴 Priority 1 (Critical) | 4 | 0 | 0 | 4 |
| 🟡 Priority 2 (High Impact) | 5 | 0 | 0 | 5 |
| 🟢 Priority 3 (Features) | 6 | 0 | 0 | 6 |
| 🔵 Priority 4 (Tests) | 9 | 0 | 0 | 9 |
| 📝 Priority 5 (Docs) | 3 | 0 | 0 | 3 |
| 🎨 Priority 6 (UI/UX) | 4 | 1 | 0 | 3 |
| **TOTAL** | **31** | **1** | **0** | **30** |

---

## 🔴 PRIORITY 1: Critical Issues (Fix Immediately)

### 1.1 Frontend: Non-Functional OAuth Buttons
- **Status:** ⬜ Not Started
- **Files:** `frontend/src/pages/LoginPage.tsx` (lines 88-114)
- **Problem:** OAuth buttons render but `onClick={() => {}}` does nothing. Users expect these to work.
- **Solution:** Either implement OAuth properly OR remove buttons and show clear "Email login only" messaging
- **Acceptance Criteria:**
  - [ ] Remove non-functional Google/Apple OAuth buttons
  - [ ] Update UI to clearly show email/password is the only auth method
  - [ ] Add "Social login coming soon" note if desired
- **Notes:** 

---

### 1.2 AI Pipeline: Broken Progress Callback
- **Status:** ⬜ Not Started
- **Files:** `ai-pipeline/modal_app.py` (~line 683)
- **Problem:** `progress_callback=lambda p, m: ...` is passed to `GenerationPipeline.run()` but that method doesn't accept this parameter - silently ignored
- **Solution:** Remove the callback or properly integrate it into the pipeline
- **Acceptance Criteria:**
  - [ ] Audit `GenerationPipeline.run()` method signature
  - [ ] Either add `progress_callback` support to pipeline OR remove the callback from modal_app.py
  - [ ] Verify progress updates still work via other mechanisms (heartbeat, etc.)
- **Notes:**

---

### 1.3 AI Pipeline: Thread Safety in Globals
- **Status:** ⬜ Not Started
- **Files:** 
  - `ai-pipeline/separation/demucs_separator.py` (global `_separator`, `_separator_fast`)
  - `ai-pipeline/transcription/drum_classifier.py` (global `last_classifier_mode`, `last_classifier_model_path`)
- **Problem:** Module-level globals are not thread-safe for concurrent processing
- **Solution:** Refactor to use per-request instances or thread-local storage
- **Acceptance Criteria:**
  - [ ] Identify all global singletons in AI pipeline
  - [ ] Refactor `demucs_separator.py` to be thread-safe
  - [ ] Refactor `drum_classifier.py` to be thread-safe
  - [ ] Add thread safety tests
- **Notes:**

---

### 1.4 Frontend: SSE Connection Memory Leak
- **Status:** ⬜ Not Started
- **Files:** `frontend/src/hooks/useJobProgress.ts`
- **Problem:** EventSource cleanup may not trigger on all unmount scenarios, potential memory leak
- **Solution:** Ensure proper cleanup in all scenarios
- **Acceptance Criteria:**
  - [ ] Audit EventSource cleanup logic
  - [ ] Add cleanup for all unmount scenarios
  - [ ] Test rapid mount/unmount cycles
- **Notes:**

---

## 🟡 PRIORITY 2: High-Impact Technical Debt

### 2.1 Desktop: Decompose EditorScreen.cs
- **Status:** ⬜ Not Started
- **Files:** `desktop/BeatSight.Game/Screens/Editor/EditorScreen.cs` (4,060 lines)
- **Problem:** File is too large, hard to maintain and test
- **Solution:** Extract into smaller focused components
- **Acceptance Criteria:**
  - [ ] Extract `EditorToolbar.cs` - toolbar and tool selection
  - [ ] Extract `EditorTimeline.cs` - timeline view and navigation
  - [ ] Extract `EditorNoteLayer.cs` - note rendering and manipulation
  - [ ] Extract `EditorCommandManager.cs` - undo/redo stack
  - [ ] Main `EditorScreen.cs` reduced to <500 lines (composition only)
  - [ ] All existing functionality preserved
- **Notes:**

---

### 2.2 Desktop: Decompose SettingsScreen.cs
- **Status:** ⬜ Not Started
- **Files:** `desktop/BeatSight.Game/Screens/Settings/SettingsScreen.cs` (3,226 lines)
- **Problem:** Monolithic settings file
- **Solution:** Extract into section classes
- **Acceptance Criteria:**
  - [ ] Extract `AudioSettingsSection.cs`
  - [ ] Extract `VisualSettingsSection.cs`
  - [ ] Extract `PlaybackSettingsSection.cs`
  - [ ] Extract `KeybindSettingsSection.cs`
  - [ ] Extract `AISettingsSection.cs`
  - [ ] Main `SettingsScreen.cs` reduced to <300 lines
- **Notes:**

---

### 2.3 Desktop: Decompose PlaybackScreen.cs
- **Status:** ⬜ Not Started
- **Files:** `desktop/BeatSight.Game/Screens/Playback/PlaybackScreen.cs` (2,852 lines)
- **Problem:** Core screen too large
- **Solution:** Extract HUD and controls
- **Acceptance Criteria:**
  - [ ] Extract `PlaybackHUD.cs` - score, combo, timing display
  - [ ] Extract `PlaybackControlsOverlay.cs` - pause, speed, loop controls
  - [ ] Main `PlaybackScreen.cs` reduced to <800 lines
- **Notes:**

---

### 2.4 Backend: Add Request ID Middleware
- **Status:** ⬜ Not Started
- **Files:** `backend/app/main.py`
- **Problem:** No request tracing for debugging production issues
- **Solution:** Add middleware to attach unique request IDs
- **Acceptance Criteria:**
  - [ ] Create `RequestIdMiddleware` class
  - [ ] Add to FastAPI middleware chain
  - [ ] Include request ID in all log messages
  - [ ] Return `X-Request-ID` header in responses
  - [ ] Add tests for middleware
- **Notes:**

---

### 2.5 Desktop: Document Window Reflection Fragility
- **Status:** ⬜ Not Started
- **Files:** `desktop/BeatSight.Game/BeatSightGame.cs` (lines 1800-2086)
- **Problem:** Uses reflection to manipulate SDL2 window internals - will break on framework updates
- **Solution:** Document risk, pin framework version, add tests
- **Acceptance Criteria:**
  - [ ] Add detailed comments explaining the reflection usage
  - [ ] Pin osu.Framework version in .csproj with comment explaining why
  - [ ] Create `WindowManagementTests.cs` to detect breakage early
  - [ ] Consider filing upstream feature request
- **Notes:**

---

## 🟢 PRIORITY 3: Feature Completeness

### 3.1 Desktop: Tutorial/Onboarding Mode
- **Status:** ⬜ Not Started
- **Files:** New file: `desktop/BeatSight.Game/Screens/Tutorial/TutorialScreen.cs`
- **Problem:** No guided onboarding for new users
- **Solution:** Create tutorial screen with step-by-step guidance
- **Acceptance Criteria:**
  - [ ] Create `TutorialScreen.cs` base structure
  - [ ] Add step: "Basic notation reading" introduction
  - [ ] Add step: "Drum kit component familiarization"
  - [ ] Add step: "Timing practice exercises"
  - [ ] Add step: "Your first song" guided walkthrough
  - [ ] Add skip option for experienced users
  - [ ] Track tutorial completion in user progress
- **Notes:**

---

### 3.2 Frontend: Connect Achievement System to API
- **Status:** ⬜ Not Started
- **Files:** `frontend/src/pages/ProfilePage.tsx`
- **Problem:** Static achievements array, no backend integration - MOCK DATA
- **Solution:** Create backend endpoints and connect frontend
- **Acceptance Criteria:**
  - [ ] Create `backend/app/routes/achievements.py`
  - [ ] Create `Achievement` database model
  - [ ] Implement achievement unlock logic
  - [ ] Remove static achievements from `ProfilePage.tsx`
  - [ ] Connect to real API endpoints
  - [ ] Add achievement notification toasts
- **Notes:** Currently uses MOCK DATA - must be replaced with real data

---

### 3.3 Frontend: Profile Avatar Upload
- **Status:** ⬜ Not Started
- **Files:** `frontend/src/pages/ProfilePage.tsx`, `frontend/src/pages/SettingsPage.tsx`
- **Problem:** Avatar URL field exists but no upload UI
- **Solution:** Implement avatar upload with crop/resize
- **Acceptance Criteria:**
  - [ ] Add avatar upload button to profile settings
  - [ ] Implement image cropping UI
  - [ ] Create backend endpoint for avatar upload
  - [ ] Store avatars in cloud storage (S3/Azure)
  - [ ] Update profile display to show uploaded avatar
- **Notes:**

---

### 3.4 Frontend: Notification Preferences API
- **Status:** ⬜ Not Started
- **Files:** `frontend/src/pages/SettingsPage.tsx`
- **Problem:** Notification toggle switches exist but no backend persistence - MOCK DATA
- **Solution:** Create backend endpoints for notification preferences
- **Acceptance Criteria:**
  - [ ] Create `backend/app/routes/notification_preferences.py`
  - [ ] Add notification preferences to User model or separate table
  - [ ] Connect frontend toggles to real API
  - [ ] Implement email notification system (optional but referenced)
- **Notes:** Currently toggles are MOCK - they don't persist

---

### 3.5 Desktop: Activate Cloud Sync
- **Status:** ⬜ Not Started
- **Files:** 
  - `desktop/BeatSight.Game/Services/CloudSyncService.cs` (875 lines - fully implemented)
  - `desktop/BeatSight.Game/Services/StubCloudSyncService.cs` (active by default)
- **Problem:** Full cloud sync implementation exists but stub is active
- **Solution:** Add configuration toggle to enable real cloud sync
- **Acceptance Criteria:**
  - [ ] Add `CloudSyncEnabled` setting to `BeatSightConfigManager`
  - [ ] Add cloud sync toggle to Settings UI
  - [ ] Implement service switching based on setting
  - [ ] Add login/logout flow for cloud sync
  - [ ] Test sync functionality end-to-end
- **Notes:**

---

### 3.6 Frontend: Admin Dashboard Real Data
- **Status:** ⬜ Not Started
- **Files:** `frontend/src/pages/AdminDashboardPage.tsx`
- **Problem:** Dashboard shows MOCK DATA, action buttons don't work
- **Solution:** Connect to real admin API endpoints
- **Acceptance Criteria:**
  - [ ] Connect to `GET /admin/system-stats` endpoint
  - [ ] Connect to `GET /admin/users` endpoint
  - [ ] Implement user management actions (role change, ban, etc.)
  - [ ] Remove all mock/static data
  - [ ] Add loading states and error handling
- **Notes:** Backend endpoints exist, frontend just needs connection

---

## 🔵 PRIORITY 4: Test Coverage

### 4.1 Desktop: EditorScreenTests.cs
- **Status:** ⬜ Not Started
- **Files:** New: `desktop/BeatSight.Tests/EditorScreenTests.cs`
- **Problem:** 4,060-line file with zero tests
- **Acceptance Criteria:**
  - [ ] Test note placement
  - [ ] Test note deletion
  - [ ] Test undo/redo functionality
  - [ ] Test timeline navigation
  - [ ] Test selection mechanics
  - [ ] Test copy/paste
  - [ ] Test save/load
- **Notes:**

---

### 4.2 Desktop: PlaybackScreenTests.cs
- **Status:** ⬜ Not Started
- **Files:** New: `desktop/BeatSight.Tests/PlaybackScreenTests.cs`
- **Problem:** Core user experience has no tests
- **Acceptance Criteria:**
  - [ ] Test view mode switching (2D/3D/Manuscript)
  - [ ] Test speed adjustment
  - [ ] Test loop section functionality
  - [ ] Test pause/resume
  - [ ] Test note hit detection timing
- **Notes:**

---

### 4.3 Desktop: ScreenNavigationTests.cs
- **Status:** ⬜ Not Started
- **Files:** New: `desktop/BeatSight.Tests/ScreenNavigationTests.cs`
- **Problem:** No integration tests for screen flow
- **Acceptance Criteria:**
  - [ ] Test Intro → MainMenu transition
  - [ ] Test MainMenu → SongSelect → Playback flow
  - [ ] Test MainMenu → Settings → back navigation
  - [ ] Test MainMenu → Editor flow
  - [ ] Test back button behavior throughout
- **Notes:**

---

### 4.4 Desktop: WindowManagementTests.cs
- **Status:** ⬜ Not Started
- **Files:** New: `desktop/BeatSight.Tests/WindowManagementTests.cs`
- **Problem:** Reflection-based window code untested
- **Acceptance Criteria:**
  - [ ] Test fullscreen toggle
  - [ ] Test resolution changes
  - [ ] Test multi-monitor support
  - [ ] Detect reflection target changes (break early on framework update)
- **Notes:**

---

### 4.5 Frontend: Hook Tests
- **Status:** ⬜ Not Started
- **Files:** New: `frontend/src/hooks/*.test.ts`
- **Problem:** No tests for custom hooks
- **Acceptance Criteria:**
  - [ ] Test `useBilling` hook
  - [ ] Test `useCredits` hook
  - [ ] Test `useJobProgress` hook (SSE logic)
  - [ ] Test `useKeyboardShortcuts` hook
  - [ ] Test `useWaveform` hook
- **Notes:**

---

### 4.6 Frontend: TimelineEditor Tests
- **Status:** ⬜ Not Started
- **Files:** New: `frontend/src/components/timeline/TimelineEditor.test.tsx`
- **Problem:** Complex 709-line component with no tests
- **Acceptance Criteria:**
  - [ ] Test note rendering
  - [ ] Test playback position indicator
  - [ ] Test click-to-seek
  - [ ] Test zoom functionality
  - [ ] Test undo/redo
- **Notes:**

---

### 4.7 AI Pipeline: Thread Safety Tests
- **Status:** ⬜ Not Started
- **Files:** New: `ai-pipeline/tests/test_thread_safety.py`
- **Problem:** No concurrent processing tests
- **Acceptance Criteria:**
  - [ ] Test concurrent Demucs separation
  - [ ] Test concurrent drum classification
  - [ ] Test concurrent pipeline runs
  - [ ] Verify no race conditions
- **Notes:** Depends on 1.3 completion

---

### 4.8 AI Pipeline: Quantization Edge Cases
- **Status:** ⬜ Not Started
- **Files:** `ai-pipeline/tests/test_rhythm_decoder.py`
- **Problem:** Edge cases in quantization not fully tested
- **Acceptance Criteria:**
  - [ ] Test extreme BPM values (30, 300)
  - [ ] Test complex time signatures (5/4, 7/8)
  - [ ] Test tuplet detection edge cases
  - [ ] Test swing ratio boundaries
- **Notes:**

---

### 4.9 Backend: Integration Tests
- **Status:** ⬜ Not Started
- **Files:** New: `backend/tests/integration/`
- **Problem:** Tests use heavy mocking, no real DB tests
- **Acceptance Criteria:**
  - [ ] Set up test database configuration
  - [ ] Create integration test base class
  - [ ] Add full user journey test (register → upload → job → download)
  - [ ] Add subscription flow integration test
- **Notes:**

---

## 📝 PRIORITY 5: Documentation Issues

### 5.1 Fix File Format Conflicts
- **Status:** ⬜ Not Started
- **Files:** 
  - `docs/BEATMAP_FORMAT.md`
  - `docs/BS_FILE_FORMAT.md`
- **Problem:** Documents conflict on extension (`.bs` vs `.bsm`), key casing, lane mapping
- **Solution:** Consolidate to one authoritative document
- **Acceptance Criteria:**
  - [ ] Audit actual implementation in `beatmap_generator.py` and C# code
  - [ ] Update `BEATMAP_FORMAT.md` to match implementation exactly
  - [ ] Add deprecation notice to `BS_FILE_FORMAT.md` redirecting to `BEATMAP_FORMAT.md`
  - [ ] Update all code comments referencing old format
- **Notes:**

---

### 5.2 Create Missing JSON Schema
- **Status:** ⬜ Not Started
- **Files:** 
  - `docs/BEATMAP_FORMAT.md` (references `beatmap_schema.json`)
  - New: `shared/schemas/beatmap_schema.json`
- **Problem:** Schema file referenced but doesn't exist
- **Solution:** Create the JSON schema or remove reference
- **Acceptance Criteria:**
  - [ ] Create `shared/schemas/beatmap_schema.json`
  - [ ] Validate schema against actual .bsm files
  - [ ] Add schema validation to beatmap loading code
  - [ ] Update documentation with schema location
- **Notes:**

---

### 5.3 Document Undocumented Tools
- **Status:** ⬜ Not Started
- **Files:** 
  - `tools/BmFontGenerator/`
  - `tools/FontStoreInspector/`
- **Problem:** Tools exist with no documentation
- **Solution:** Add README files
- **Acceptance Criteria:**
  - [ ] Add `tools/BmFontGenerator/README.md`
  - [ ] Add `tools/FontStoreInspector/README.md`
  - [ ] Include purpose, usage, and examples
- **Notes:**

---

## 🎨 PRIORITY 6: UI/UX Polish

### 6.1 Manuscript Playback Highlighter
- **Status:** ✅ Complete
- **Files:** 
  - `desktop/BeatSight.Game/Screens/Playback/Playfield/Views/ManuscriptPlaybackHighlighter.cs` (created)
  - `desktop/BeatSight.Game/Screens/Playback/Playfield/Views/ManuscriptViewEnhanced.cs` (modified)
  - `desktop/BeatSight.Game/Configuration/BeatSightConfigManager.cs` (modified)
- **Problem:** User requested sweeping highlight overlay for timing guidance
- **Solution:** Created `ManuscriptPlaybackHighlighter` component
- **Acceptance Criteria:**
  - [x] Create highlighter component with amber overlay
  - [x] Implement left-to-right sweep synchronized with playback
  - [x] Add per-note glow rings approaching hit time
  - [x] Add user setting `ShowManuscriptPlaybackHighlighter`
  - [x] Integrate into `ManuscriptViewEnhanced`
- **Notes:** Completed December 3, 2025

---

### 6.2 Empty State Illustrations
- **Status:** ⬜ Not Started
- **Files:** Multiple frontend pages
- **Problem:** Generic error messages, no empty state graphics
- **Solution:** Design and implement empty states
- **Acceptance Criteria:**
  - [ ] Design empty state illustration for beatmap library
  - [ ] Design empty state for "No AI jobs"
  - [ ] Design empty state for "No search results"
  - [ ] Implement in `LibraryPage.tsx`
  - [ ] Implement in `JobQueuePage.tsx`
- **Notes:**

---

### 6.3 Frontend Canvas Performance
- **Status:** ⬜ Not Started
- **Files:** `frontend/src/components/timeline/TimelineCanvas.tsx`
- **Problem:** Full redraw on every frame, performance bottleneck
- **Solution:** Implement layer separation
- **Acceptance Criteria:**
  - [ ] Separate static layer (grid, labels) from dynamic layer (notes, playhead)
  - [ ] Only redraw dynamic layer on each frame
  - [ ] Implement dirty rect tracking
  - [ ] Measure and document performance improvement
- **Notes:**

---

### 6.4 Loading States Completion
- **Status:** ⬜ Not Started
- **Files:** Various frontend pages
- **Problem:** Some pages missing loading indicators
- **Solution:** Add skeleton/spinner states
- **Acceptance Criteria:**
  - [ ] Add loading state to `AdminDashboardPage.tsx`
  - [ ] Add loading state to `ProfilePage.tsx` (achievements section)
  - [ ] Add loading state to `SettingsPage.tsx` (preferences load)
  - [ ] Consistent loading pattern across all pages
- **Notes:**

---

## 🚫 Explicitly Out of Scope

The following items are **NOT** tracked here as they are part of the separate PRODUCTION_DEPLOYMENT_GUIDE workflow:

- ML model training (Steps 14-19)
- Lambda Labs deployment
- Modal deployment configuration
- Model encryption/security
- Cloud training infrastructure
- S3 checkpoint management

---

## 📅 Implementation Log

### December 3, 2025
- Created `ENGINEERING_ACTION_TRACKER.md`
- ✅ Completed 6.1: Manuscript Playback Highlighter
- Starting Priority 1 critical fixes...

---

## 🔄 How to Update This Document

When completing an item:
1. Change status from `⬜ Not Started` to `🟡 In Progress` when starting
2. Check off acceptance criteria as completed
3. Change status to `✅ Complete` when all criteria met
4. Add entry to Implementation Log with date
5. Update the Overall Progress table at the top

---

## 📌 Current Focus

**Now Working On:** Priority 1.1 - Non-Functional OAuth Buttons

**Next Up:** Priority 1.2 - AI Pipeline Progress Callback

