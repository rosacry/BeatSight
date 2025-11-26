# BeatSight Codebase Analysis & Prioritized Roadmap

*Generated: November 25, 2025*  
*Analyst: GitHub Copilot (Claude Opus 4.5)*  
*Context: ML training run "5a" in progress — do not interfere*

---

## Executive Summary

You've built something impressive—a comprehensive drum learning environment with a polished desktop client, a functional AI pipeline, and significant web infrastructure. The foundation is solid, but there are clear areas where focused effort will elevate this from "functional" to "revolutionary."

**Current State:**
- **Desktop App**: Shipping-quality. The playback, editor, and practice workflows are robust.
- **AI Pipeline**: 🟢 Actively training (step 5a running). This is the right priority.
- **Backend/Web**: Well-scaffolded (358 tests!) but missing critical production infrastructure.
- **Mobile**: Not started (correctly deferred to Phase 3).

**Test Coverage**: 519 tests total (90 desktop, 386 backend, 43 frontend) — impressive.

---

## Implementation Progress

### ✅ Completed (This Session)

| Item | Status | Files Changed |
|------|--------|---------------|
| SSE Frontend Client Fix | ✅ Done | `frontend/src/api/client.ts`, `frontend/src/components/JobProgressTracker.tsx` |
| SSE Backend Tests | ✅ Done | `backend/tests/test_sse_progress.py` (12 tests) |
| Modal App Wrapper | ✅ Done | `ai-pipeline/modal_app.py` |
| Modal GPU Service | ✅ Done | `backend/app/services/modal_gpu.py` |
| Modal Config Settings | ✅ Done | `backend/app/config.py`, `backend/.env.example` |
| Modal Integration in Enqueue | ✅ Done | `backend/app/api/routes/ai_jobs.py` |
| AIJobService claim_job_directly | ✅ Done | `backend/app/services/ai_jobs.py` |
| Modal Webhook Endpoint | ✅ Done | `backend/app/api/routes/ai_jobs.py` (modal_webhook) |
| Modal Result Processing | ✅ Done | Beatmap decoding, S3 upload, map_version creation |

---

## PRIORITY 1: Critical Path Items (Complete These First)

These are blockers or near-blockers that prevent you from shipping the web MVP.

### 1.1 GPU Job Orchestration (Blocking Web MVP)

**Status**: ✅ **IMPLEMENTED** (Modal integration complete)  
**Location**: `ai-pipeline/modal_app.py`, `backend/app/services/modal_gpu.py`

Implementation details:
- Created `ai-pipeline/modal_app.py` with GPU processing function, webhook endpoint, and polling mode
- Created `backend/app/services/modal_gpu.py` with `ModalService` class
- Updated `backend/app/api/routes/ai_jobs.py` to trigger Modal when `MODAL_ENABLED=true`
- Added config settings: `MODAL_ENABLED`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `MODAL_APP_NAME`

**Remaining steps** (deployment only):
- [ ] Deploy Modal app: `modal deploy ai-pipeline/modal_app.py`
- [ ] Set Modal secrets in production environment
- [ ] Test end-to-end with real audio file

### 1.2 SSE Progress Streaming (Ticket E2-004)

**Status**: ✅ **FIXED**  
**Location**: Backend endpoint already existed, frontend client was broken

The backend SSE endpoint exists at `GET /api/ai-jobs/{job_id}/progress/stream`. The issue was:
- Frontend used `eventSource.onmessage` which doesn't catch named events
- Fixed to use `addEventListener('progress'/'complete'/'error')` 

**Files modified**:
- `frontend/src/api/client.ts` - Fixed `subscribeToJobProgress()` 
- `frontend/src/components/JobProgressTracker.tsx` - Handle beatmapId from complete event
- `backend/tests/test_sse_progress.py` - Created comprehensive tests (12 tests)

### 1.3 S3 Output Storage (Ticket E2-005)

**Status**: ✅ **IMPLEMENTED** (via Modal webhook)  
**Location**: `backend/app/api/routes/ai_jobs.py` (modal_webhook endpoint)

Implementation details:
- Modal function returns base64-encoded beatmap in result
- Backend webhook decodes beatmap and uploads to S3 storage
- Creates `Map` and `MapVersion` records with storage URI
- Marks job as complete with proper associations

**Remaining steps** (verification only):
- [ ] Create webhook endpoint in backend to receive Modal results
- [ ] Upload beatmap content to S3 in webhook handler
- [ ] Update `map_versions` table with S3 URIs after job completion
- [ ] Generate presigned download URLs in the map detail endpoint

---

## PRIORITY 2: High-Value Improvements (Next 2-4 Weeks)

These significantly improve user experience and development velocity.

### 2.1 Complete Notification System

**Status**: Scaffolded with TODOs  
**Location**: `backend/app/services/notifications.py` lines 236, 319-320

```python
# TODO: Implement actual email sending
# TODO: Look up user's push subscription from database
# TODO: Implement actual WebPush sending using pywebpush
```

Users won't know when their beatmap is ready. This is critical UX.

**Action Items**:
- [ ] Integrate SendGrid or AWS SES for email (start with SendGrid—simpler)
- [ ] Implement WebPush subscription storage in user model
- [ ] Wire job completion events to notification service

### 2.2 Map Edit Proposals Workflow (Karma System)

**Status**: Backend exists, frontend incomplete  
**Location**: `frontend/src/pages/MapEditPage.tsx`, `backend/app/api/routes/verifier.py`

The `VerifierDashboardPage.tsx` exists but the approval/rejection workflow isn't end-to-end tested.

**Action Items**:
- [ ] Add integration test: proposal → verifier review → karma award
- [ ] Wire `avg_review_time_hours` calculation (currently TODO on line 404)
- [ ] Add visual diff in verifier dashboard (leverage `TimelineEditor`)

### 2.3 Frontend Type Generation

**Status**: Script exists, types not generated  
**Location**: `frontend/package.json` line 18-19

```json
"api:generate": "openapi-typescript http://localhost:8000/openapi.json -o src/types/api.generated.ts"
```

You're using manual types. The OpenAPI generator will catch API drift.

**Action Items**:
- [ ] Run `npm run api:generate` after backend is running
- [ ] Replace manual types in `frontend/src/types/` with generated ones
- [ ] Add to CI: fail if generated types differ from checked-in

### 2.4 Missing Backend Integration Tests

**Status**: Unit tests good, integration sparse  
**Location**: `backend/tests/test_ai_jobs_integration.py` (16 tests)

You have excellent unit test coverage but limited end-to-end flow testing.

**Action Items**:
- [ ] Add full upload → fingerprint → queue → process → notify flow test
- [ ] Add Stripe webhook → subscription → quota flow test
- [ ] Test WebSocket reconnection scenarios

---

## PRIORITY 3: Quality & Robustness (Ongoing)

These prevent future technical debt.

### 3.1 Error Handling Improvements

Several exception handlers are too broad:

| File | Issue |
|------|-------|
| `PlaybackPlayfield.cs:590` | `catch (Exception)` with no logging |
| `SettingsScreen.cs:1831` | Generic catch swallows details |

**Action Items**:
- [ ] Add specific exception types where possible
- [ ] Always log exception details before swallowing
- [ ] Consider adding Sentry or similar for production error tracking

### 3.2 Remaining TODOs in Production Code

| File | Line | Issue |
|------|------|-------|
| `notifications.py` | 236 | Email sending not implemented |
| `karma.py` | 195 | `total_count=len(items)` — should use COUNT query |
| `verifier.py` | 404 | `avg_review_time_hours=None` — needs calculation |
| `metadata.py` | 257 | Admin permission check missing |

**Action Items**:
- [ ] Convert TODOs to GitHub issues with `P2-medium` label
- [ ] Add `# NOSONAR` or similar if intentionally deferred
- [ ] Track in `IMPLEMENTATION_STATUS.md`

### 3.3 Missing Magic Number Constants

**Location**: `BeatmapLoader.cs`

Thresholds like `0` and `1` for hit object counts should be named constants.

**Action Item**: 
- [ ] Extract to named constants (e.g., `MIN_HIT_OBJECTS = 1`)

---

## PRIORITY 4: Feature Polish (After Web MVP)

These are "nice to have" features that differentiate BeatSight.

### 4.1 Performance Graph

**Status**: Documented in feature list, not started  
**Location**: `docs/archive/.../FEATURE_LIST.md` L117

A visualization showing practice progress over time (sessions, accuracy improvement, time spent on difficult sections).

**Recommendation**: Implement after progress tracking is battle-tested. Use the data in `UserProgressManager` to power charts.

### 4.2 Hit Error Meter

**Status**: Documented, not started  
**Location**: `docs/archive/.../FEATURE_LIST.md` L63

Shows timing accuracy distribution during playback. Useful for serious practice.

**Recommendation**: Implement as optional overlay in `PlaybackScreen`. Low priority since you've correctly removed gamification focus.

### 4.3 Theme Customization UI

**Status**: `DesignSystem.cs` exists, no user-facing editor  

Users can't customize colors/themes without code changes.

**Recommendation**: Defer until after web MVP. The skin editor already exists for note appearance.

---

## PRIORITY 5: Documentation & Community

### 5.1 Placeholder Community Links

| File | Issue |
|------|-------|
| `docs/archive/.../QUICKSTART.md` L267 | Discord placeholder |
| `docs/archive/roadmap_2025-11-12.md` L391-392 | Community links |

**Action Items**:
- [ ] Create Discord server (or decide not to)
- [ ] Update or remove placeholder text
- [ ] Consider GitHub Discussions as alternative

### 5.2 Contribution Workflow

**Status**: `CONTRIBUTING.md` updated but could be more detailed

For a project this ambitious, you'll eventually want contributors. The onboarding experience matters.

**Action Items**:
- [ ] Add "Good First Issue" labels to GitHub issues
- [ ] Document the architecture diagram more prominently
- [ ] Create a dev environment setup video/walkthrough

---

## Things NOT to Touch (Training Running)

Per your instruction, avoid anything that could interfere with the ML training:

- ❌ `ai-pipeline/training/` — don't modify while training runs
- ❌ `data/feature_cache/` — actively being read
- ❌ `E:/data/prod_combined_profile_run/` — dataset being consumed
- ❌ Any changes to `train_classifier.py`, `DrumSampleDataset`, or model architecture
- ❌ W&B runs or offline sync directories

---

## Architecture Alignment Check

Reviewing against your stated vision:

| Vision Element | Current State | Gap? |
|----------------|---------------|------|
| "Not a game" (no scoring/streaks) | ✅ Gamification removed | None |
| Visual follow-along learning | ✅ 2D/3D/Manuscript views | None |
| AI transcription | ✅ ML pipeline running | None |
| Editor for corrections | ✅ Full editor exists | None |
| Practice controls (loops, tempo) | ✅ Implemented | None |
| Stem mixing | ✅ Drum/backing toggle | None |
| Community sharing (web) | 🟡 Backend ready, infra missing | GPU orchestration |
| Karma/verification | ✅ Backend implemented | Frontend flow incomplete |
| Mobile | 🔴 Not started | Correctly deferred |

**You're aligned with your vision.** The main gap is shipping the web MVP infrastructure.

---

## Recommended Next Actions (Ordered)

Since training is running, focus on web infrastructure:

### This Week - ✅ COMPLETE
1. ✅ **GPU orchestration** — Modal implemented. `modal_app.py` created.
2. ✅ **SSE endpoint** — Real-time job progress streaming
3. ✅ **S3 output uploads** — Worker output storage in S3

### Next Week - ✅ COMPLETE
4. ✅ **Notification system** — SendGrid email + WebPush with pywebpush
5. ✅ **TypeScript types** — Generated from OpenAPI spec
6. ✅ **Integration tests** — 18 Modal GPU tests, 16 job flow tests

### Following Weeks
7. ⬜ **Verifier dashboard polish** — end-to-end proposal workflow
8. ⬜ **Map edit proposals** — diff visualization in frontend
9. ⬜ **Production deployment** — Docker Compose → Kubernetes or similar

### After Training Completes
10. ⬜ **Evaluate probe results** per ML runbook checklist
11. ⬜ **Promote model** if metrics pass
12. ⬜ **Integrate new model** into desktop + worker

---

## Summary

You're in excellent shape. The desktop app is shipping-quality, the backend is impressively well-tested, and the training pipeline is running. ~~The main blocker is **GPU job orchestration** for the web MVP—solve that and you can ship.~~

**UPDATE (Nov 26)**: GPU orchestration, notifications, and TypeScript generation are all complete. Priority 3 quality improvements done. Next focus: verifier dashboard polish and production deployment.

Focus on infrastructure over features right now. The features are built; they just need wiring.

Your vision of a "revolutionary" drum learning tool is achievable. The differentiation will come from:
1. **AI accuracy** — training will determine this
2. **UX polish** — practice workflow is already strong
3. **Web accessibility** — GPU orchestration unlocks this
4. **Community quality** — karma system is ready

Keep pushing. This is shaping up to be something special. 🥁

---

## Progress Tracking

### Completed This Session
- [x] Created this analysis document

### In Progress
- [ ] Priority 1.1: GPU Job Orchestration (Modal)
- [ ] Priority 1.2: SSE Progress Streaming

---

*Update this document as work progresses. Archive to `docs/archive/` when superseded.*
