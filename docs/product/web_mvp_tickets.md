# BeatSight Web MVP Engineering Tickets

*Generated: November 24, 2025*  
*Last Updated: December 3, 2025*  
*Source: `docs/web_mvp_task_breakdown.md`*

This document contains detailed engineering tickets for the Web MVP implementation. Each ticket is formatted for GitHub Issues with clear acceptance criteria, implementation notes, and dependencies.

## Implementation Summary (Dec 3, 2025)

| Epic | Status | Tickets Complete |
|------|--------|------------------|
| **E1: Intake & Fingerprinting** | ✅ Complete | E1-002, E1-003, E1-006, E1-007, E1-008 implemented |
| **E2: AI Generation Pipeline** | ✅ Complete | E2-001, E2-002, E2-003, E2-004, E2-005, E2-006, E2-007 implemented |
| **E3: Web Application & Editor** | ✅ Complete | All milestones implemented |
| **E4: Karma & Verification** | ✅ Complete | All milestones implemented |
| **E5: Monetization** | ✅ Complete | All milestones + credits system implemented |
| **E6: Observability** | ⚠️ Partial | CI/CD complete, monitoring infrastructure pending |

**Note:** Many tickets below still show original `[ ]` checkboxes but are actually complete.
See `docs/web_mvp_task_breakdown.md` for the authoritative status of each task.

---

## Epic 1: Intake & Fingerprinting

### Ticket E1-001: Create S3 Bucket with Lifecycle Policies
**Priority:** P0 - Critical Path  
**Estimate:** 2 hours  
**Labels:** `infrastructure`, `aws`, `storage`

#### Description
Set up S3 bucket infrastructure for storing user-uploaded audio files, generated beatmaps, and separated stems.

#### Acceptance Criteria
- [ ] S3 bucket created with proper naming convention (`beatsight-{env}-uploads`)
- [ ] Lifecycle policies configured:
  - Move to Infrequent Access after 30 days
  - Archive to Glacier after 90 days for non-canonical maps
  - Delete incomplete multipart uploads after 7 days
- [ ] CORS configuration allows uploads from approved domains
- [ ] Server-side encryption enabled (AES-256)
- [ ] Bucket versioning enabled for beatmap files
- [ ] IAM policies for least-privilege access

#### Implementation Notes
```hcl
# Terraform example structure
resource "aws_s3_bucket" "uploads" {
  bucket = "beatsight-${var.environment}-uploads"
  # ... lifecycle rules
}
```

#### Dependencies
- AWS account access
- Terraform state backend configured

---

### Ticket E1-002: Implement Pre-signed Upload API Endpoint
**Priority:** P0 - Critical Path  
**Estimate:** 4 hours  
**Labels:** `backend`, `api`, `storage`

#### Description
Create FastAPI endpoint that generates pre-signed S3 URLs for secure client-side uploads.

#### Acceptance Criteria
- [ ] `POST /api/v1/uploads/presign` endpoint created
- [ ] Request validates file type (MP3, WAV, FLAC, OGG, M4A, AAC)
- [ ] Request validates max file size (500MB)
- [ ] Returns pre-signed URL with 15-minute expiry
- [ ] Returns upload ID for tracking
- [ ] Rate limiting applied (10 uploads/hour for free tier)
- [ ] Unit tests with >80% coverage

#### Request Schema
```python
class PresignRequest(BaseModel):
    filename: str
    content_type: str
    file_size_bytes: int
```

#### Response Schema
```python
class PresignResponse(BaseModel):
    upload_id: UUID
    presigned_url: str
    expires_at: datetime
    fields: dict  # Additional form fields for multipart
```

#### Dependencies
- E1-001 (S3 bucket)
- Backend authentication (can stub initially)

---

### Ticket E1-003: Client-side Upload Integration with Progress Events
**Priority:** P1 - High  
**Estimate:** 6 hours  
**Labels:** `frontend`, `ux`, `storage`

#### Description
Implement drag-and-drop file upload UI with real-time progress feedback.

#### Acceptance Criteria
- [ ] Drag-and-drop zone styled per design system
- [ ] File type validation before upload attempt
- [ ] File size validation with user-friendly error message
- [ ] Upload progress bar with percentage and speed
- [ ] Cancel upload functionality
- [ ] Retry logic for failed uploads (max 3 attempts)
- [ ] Success animation and transition to processing state
- [ ] Accessible: keyboard navigation, screen reader labels

#### Implementation Notes
Use `XMLHttpRequest` or `fetch` with `ReadableStream` for progress tracking:
```typescript
const xhr = new XMLHttpRequest();
xhr.upload.addEventListener('progress', (e) => {
  const percent = (e.loaded / e.total) * 100;
  setProgress(percent);
});
```

#### Dependencies
- E1-002 (Pre-signed URL endpoint)
- Design mockups for upload UI

---

### Ticket E1-004: Virus Scan Lambda Hook
**Priority:** P1 - High  
**Estimate:** 8 hours  
**Labels:** `infrastructure`, `security`, `aws`

#### Description
Deploy Lambda function triggered on S3 upload to scan files with ClamAV before fingerprinting.

#### Acceptance Criteria
- [ ] Lambda function deployed with ClamAV layer
- [ ] S3 event trigger on `PUT` to uploads bucket
- [ ] Scanned files tagged with `scan-status: clean|infected|error`
- [ ] Infected files quarantined to separate bucket
- [ ] CloudWatch metrics for scan latency and infection rate
- [ ] SNS notification on infection detected
- [ ] Scan timeout: 5 minutes max

#### Implementation Notes
Use pre-built ClamAV Lambda layer or Docker container with Lambda.
Consider bucket-native approach with S3 Object Lambda for inline scanning.

#### Dependencies
- E1-001 (S3 bucket)

---

### Ticket E1-005: Containerize Chromaprint Worker
**Priority:** P0 - Critical Path  
**Estimate:** 6 hours  
**Labels:** `infrastructure`, `audio`, `docker`

#### Description
Create Docker container for Chromaprint-based audio fingerprinting worker.

#### Acceptance Criteria
- [ ] Dockerfile with Chromaprint and fpcalc installed
- [ ] Python wrapper script for job consumption
- [ ] Health check endpoint
- [ ] Graceful shutdown handling
- [ ] Resource limits defined (CPU, memory)
- [ ] Multi-arch build (amd64, arm64)
- [ ] Published to ECR

#### Dockerfile Structure
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y chromaprint-tools
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY fingerprint_worker.py .
CMD ["python", "fingerprint_worker.py"]
```

#### Dependencies
- ECR repository created

---

### Ticket E1-006: Implement Fingerprint Job Queue with Redis ✅ COMPLETE
**Priority:** P0 - Critical Path  
**Estimate:** 8 hours  
**Labels:** `backend`, `queue`, `redis`
**Status:** ✅ Completed Nov 25, 2025

#### Description
Set up Redis-based job queue for fingerprint processing with deduplication.

#### Acceptance Criteria
- [x] Redis instance provisioned (ElastiCache or self-hosted)
- [x] Queue implementation using `rq` or `celery`
- [x] Deduplication: skip if fingerprint hash already exists
- [x] Job retry with exponential backoff (max 3 retries)
- [x] Dead letter queue for failed jobs
- [x] Queue metrics exposed (depth, processing time)
- [x] Job TTL: 24 hours

#### Implementation Notes (Nov 25)
- Created `backend/app/db/redis.py` with:
  - `JobQueue` class with priority-based sorted set queue
  - `RedisKeys` namespace management
  - Pub/sub for progress updates (`publish_progress`, `subscribe_progress`)
  - Quota tracking utilities (`get_quota_usage`, `increment_quota_usage`)
  - Caching utilities
- Queue operations: `enqueue`, `dequeue`, `mark_complete`, `mark_failed`, `requeue`
- Uses Redis sorted sets for priority ordering with FIFO within same priority

#### Queue Schema
```python
@dataclass
class FingerprintJob:
    upload_id: UUID
    s3_key: str
    user_id: UUID | None
    created_at: datetime
    attempts: int = 0
```

#### Dependencies
- E1-005 (Chromaprint worker)
- Redis infrastructure

---

### Ticket E1-007: Integrate AcoustID Lookup with Fallback Form
**Priority:** P1 - High  
**Estimate:** 6 hours  
**Labels:** `backend`, `integration`, `metadata`

#### Description
Query AcoustID service with audio fingerprint to retrieve metadata, with fallback to manual entry.

#### Acceptance Criteria
- [ ] AcoustID API integration with API key management
- [ ] Parse and store: title, artist, album, duration, MusicBrainz ID
- [ ] Handle rate limiting (3 req/sec)
- [ ] Fallback: if no match, return empty metadata with `requires_manual: true`
- [ ] Manual metadata form saves to `songs` table
- [ ] Confidence score stored for match quality

#### Dependencies
- E1-006 (Fingerprint queue)
- AcoustID API key

---

### Ticket E1-008: Intake UX Polish - Loading States & Errors
**Priority:** P2 - Medium  
**Estimate:** 4 hours  
**Labels:** `frontend`, `ux`, `polish`

#### Description
Implement polished loading states, error messages, and transitions for the intake flow.

#### Acceptance Criteria
- [ ] Skeleton loaders during file validation
- [ ] Animated progress states (upload → scanning → fingerprinting → metadata)
- [ ] Error messages with actionable guidance:
  - "File too large" → "Max 500MB. Try compressing or trimming."
  - "Unsupported format" → List supported formats
  - "Upload failed" → Retry button
- [ ] Success state with metadata preview
- [ ] Smooth transitions between states (300ms)

#### Dependencies
- E1-003 (Upload integration)

---

## Epic 2: AI Generation Pipeline

### Ticket E2-001: Define ai_jobs Table and Worker Heartbeat Schema ✅ COMPLETE
**Priority:** P0 - Critical Path  
**Estimate:** 3 hours  
**Labels:** `backend`, `database`, `schema`
**Status:** ✅ Completed Nov 25, 2025

#### Description
Extend existing `ai_jobs` table with worker heartbeat fields for job monitoring.

#### Acceptance Criteria
- [x] Add columns to `ai_jobs`:
  - `worker_id: UUID | None`
  - `last_heartbeat: datetime | None`
  - `progress_percent: int | None`
  - `progress_message: str | None`
- [x] Migration script created (Alembic)
- [ ] Rollback tested
- [x] Index on `(state, priority, created_at)` for queue ordering

#### Implementation Notes (Nov 25)
- Model fields added in `backend/app/models/ai_job.py`
- Schemas added in `backend/app/schemas/ai_jobs.py`
- Service methods added in `backend/app/services/ai_jobs.py`:
  - `heartbeat()`, `update_progress()`, `claim_job()`, `release_job()`, `find_stale_jobs()`
- API endpoints added in `backend/app/api/routes/ai_jobs.py`:
  - `POST /{job_id}/heartbeat`, `PATCH /{job_id}/progress`, `POST /claim`, `POST /{job_id}/release`, `GET /stale/list`
- Alembic migration: `alembic/versions/20241125_..._001_worker_heartbeat_...`
- Unit tests added in `backend/tests/test_ai_jobs.py`

#### Schema Addition
```sql
ALTER TABLE ai_jobs 
ADD COLUMN worker_id UUID,
ADD COLUMN last_heartbeat TIMESTAMP,
ADD COLUMN progress_percent INTEGER,
ADD COLUMN progress_message VARCHAR(255);
```

#### Dependencies
- Existing `ai_jobs` table (already exists in backend)

---

### Ticket E2-002: Build AI Job Enqueue Endpoint with Quota Checks ✅ COMPLETE
**Priority:** P0 - Critical Path  
**Estimate:** 6 hours  
**Labels:** `backend`, `api`, `quota`
**Status:** ✅ Completed Nov 25, 2025

#### Description
Enhance existing AI job endpoint with permission checks and usage quota enforcement.

#### Acceptance Criteria
- [x] Authenticate user (extend existing endpoint)
- [x] Check user's remaining AI generation quota
- [x] Priority based on subscription tier:
  - Free: `STANDARD` priority
  - Pro: `HIGH` priority
- [x] Return 429 if quota exceeded
- [x] Return job ID and estimated wait time
- [ ] Emit `job.enqueued` event for analytics

#### Implementation Notes (Nov 25)
- Created `backend/app/services/quota.py` with:
  - `QuotaLimits` dataclass with plan-specific limits
  - `QuotaStatus` dataclass for current usage
  - `QuotaService` class with `check_quota`, `consume_quota`, `get_priority` methods
  - `QuotaExceededError` exception
- Enhanced `/ai-jobs` endpoint in `backend/app/api/routes/ai_jobs.py`:
  - Returns `AIJobEnqueueResponse` with job, queue_position, estimated_wait, quota
  - Returns 429 with reset time when quota exceeded
  - Auto-sets priority based on subscription tier
- Added `GET /ai-jobs/quota` endpoint for checking quota status
- Added schemas: `QuotaStatusRead`, `AIJobEnqueueResponse`

#### Endpoint Enhancement
```python
@router.post("/ai-jobs")
async def enqueue_job(
    payload: AIJobCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AIJobRead:
    # Check quota
    # Determine priority
    # Enqueue with user context
```

#### Dependencies
- Authentication system
- User subscription/quota tables

---

### Ticket E2-003: Containerize AI Pipeline Worker ✅ COMPLETE
**Priority:** P0 - Critical Path  
**Estimate:** 12 hours  
**Labels:** `infrastructure`, `ai`, `docker`, `gpu`
**Status:** ✅ Completed Nov 25, 2025

#### Description
Adapt existing `ai-pipeline` scripts into a containerized GPU worker.

#### Acceptance Criteria
- [x] Dockerfile with CUDA support
- [x] Worker pulls jobs from API (HTTP-based, not direct Redis)
- [x] Runs `pipeline.process` with job parameters
- [x] Streams progress updates via API
- [ ] Stores outputs to S3:
  - `.bsm` beatmap file
  - Separated stems (if configured)
  - Debug payload (optional)
- [ ] Handles OOM gracefully (retry with reduced batch)
- [ ] GPU utilization metrics exposed

#### Implementation Notes (Nov 25)
- Created `ai-pipeline/Dockerfile`:
  - Based on `nvidia/cuda:12.2-cudnn9-runtime-ubuntu22.04`
  - Installs Python 3.10, FFmpeg, SOX, dependencies
  - Pre-downloads Demucs models during build
  - Health check verifies CUDA availability
- Created `ai-pipeline/pipeline/worker.py`:
  - `Worker` class with graceful shutdown (SIGTERM/SIGINT)
  - `APIClient` for backend communication (claim, heartbeat, progress)
  - `JobProcessor` with background heartbeat task
  - Downloads audio, runs pipeline, uploads results
- Added `ai-worker` service to `backend/docker-compose.yml`:
  - GPU reservation with nvidia driver
  - Uses `--profile gpu` to enable

#### Dockerfile Structure
```dockerfile
FROM nvidia/cuda:12.2-runtime-ubuntu22.04
# Install Python, dependencies, Demucs models
COPY ai-pipeline/ /app/ai-pipeline/
WORKDIR /app/ai-pipeline
CMD ["python", "-m", "pipeline.worker"]
```

#### Dependencies
- E2-001 (Schema updates)
- E1-006 (Redis queue infrastructure)

---

### Ticket E2-004: Implement Progress Callbacks via Redis Pub/Sub
**Priority:** P1 - High  
**Estimate:** 6 hours  
**Labels:** `backend`, `realtime`, `redis`

#### Description
Enable real-time progress updates from GPU workers to API/frontend.

#### Acceptance Criteria
- [x] Worker publishes to `ai-jobs:{job_id}:progress` channel
- [x] Message format: `{percent, message, stage, timestamp}`
- [ ] API endpoint for SSE streaming: `GET /api/v1/ai-jobs/{id}/progress`
- [x] Heartbeat every 5 seconds during processing
- [ ] Auto-cleanup channels after job completion (TTL: 1 hour)

#### Implementation Notes (Nov 25 - Partial)
- Pub/sub utilities created in `backend/app/db/redis.py`:
  - `ProgressUpdate` dataclass
  - `publish_progress()` and `subscribe_progress()` functions
- Worker uses HTTP API for progress updates (simpler than direct Redis pub/sub)
- SSE streaming endpoint still needed for real-time frontend updates

#### Implementation Notes
```python
# Worker side
redis_client.publish(f"ai-jobs:{job_id}:progress", json.dumps({
    "percent": 45,
    "message": "Separating drums...",
    "stage": "demucs"
}))

# API side (SSE)
async def stream_progress(job_id: UUID):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"ai-jobs:{job_id}:progress")
    async for message in pubsub.listen():
        yield f"data: {message['data']}\n\n"
```

#### Dependencies
- E2-003 (Containerized worker)

---

### Ticket E2-005: Store Generated Beatmaps and Stems in S3
**Priority:** P0 - Critical Path  
**Estimate:** 4 hours  
**Labels:** `backend`, `storage`, `ai`

#### Description
Implement storage logic for AI-generated outputs.

#### Acceptance Criteria
- [ ] S3 path structure: `outputs/{song_id}/{job_id}/`
- [ ] Files stored:
  - `beatmap.bsm` (always)
  - `stems/drums.wav` (if separation enabled)
  - `stems/other.wav` (if separation enabled)
  - `debug.json` (if debug mode)
- [ ] Update `map_versions` table with S3 paths
- [ ] Generate pre-signed download URLs (1 hour expiry)
- [ ] Content-Disposition header for downloads

#### Dependencies
- E1-001 (S3 bucket)
- E2-003 (Containerized worker)

---

### Ticket E2-006: Job Completion Notifications (Email & WebPush)
**Priority:** P2 - Medium  
**Estimate:** 8 hours  
**Labels:** `backend`, `notifications`, `email`

#### Description
Notify users when their AI generation job completes or fails.

#### Acceptance Criteria
- [ ] Email notification via SES or SendGrid
  - Subject: "Your beatmap for [Song Title] is ready!"
  - Include direct link to result
- [ ] WebPush notification (if browser permission granted)
- [ ] User preference toggle for notification types
- [ ] Rate limit: max 10 notifications/hour per user
- [ ] Templates for: success, failure, timeout

#### Dependencies
- E2-003 (Containerized worker)
- Email service configuration

---

### Ticket E2-007: Admin Dashboard for AI Job Inspection
**Priority:** P3 - Low  
**Estimate:** 6 hours  
**Labels:** `frontend`, `admin`, `support`

#### Description
Build internal tool for support team to inspect and debug AI jobs.

#### Acceptance Criteria
- [ ] Admin route: `/admin/ai-jobs`
- [ ] List view with filters: status, user, date range
- [ ] Detail view showing:
  - Job parameters
  - Progress history
  - Error logs
  - Retry button
- [ ] Requires admin role
- [ ] Audit log for admin actions

#### Dependencies
- E2-001 (Schema updates)
- Authentication with role system

---

## Epic 3: Web Application & Editor

### Ticket E3-001: Set Up React/Next.js with PWA Support
**Priority:** P0 - Critical Path  
**Estimate:** 8 hours  
**Labels:** `frontend`, `infrastructure`, `pwa`

#### Description
Bootstrap frontend application with Next.js, TypeScript, and PWA capabilities.

#### Acceptance Criteria
- [ ] Next.js 14+ with App Router
- [ ] TypeScript strict mode
- [ ] Tailwind CSS configured
- [ ] PWA manifest with icons (192x192, 512x512)
- [ ] Service worker for offline caching
- [ ] ESLint + Prettier configured
- [ ] Husky pre-commit hooks
- [ ] CI pipeline runs lint and type-check

#### Implementation Notes
```bash
npx create-next-app@latest beatsight-web --typescript --tailwind --app
npx next-pwa # or next.config.js PWA setup
```

#### Dependencies
- None

---

### Ticket E3-002: Implement Authentication Integration (Auth0/Keycloak)
**Priority:** P0 - Critical Path  
**Estimate:** 10 hours  
**Labels:** `frontend`, `backend`, `auth`, `security`

#### Description
Integrate authentication provider for user login/signup.

#### Acceptance Criteria
- [ ] Auth0 or Keycloak tenant configured
- [ ] Social login: Google, GitHub, Discord
- [ ] Email/password login with verification
- [ ] JWT token handling in frontend
- [ ] Backend middleware validates tokens
- [ ] Refresh token rotation
- [ ] Logout clears all sessions
- [ ] PKCE flow for SPA security

#### API Changes
```python
# New dependency
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session)
) -> User:
    payload = decode_jwt(token)
    user = await get_or_create_user(session, payload)
    return user
```

#### Dependencies
- Auth provider account

---

### Ticket E3-003: Build Responsive Navigation Shell
**Priority:** P1 - High  
**Estimate:** 6 hours  
**Labels:** `frontend`, `ux`, `navigation`

#### Description
Create main application layout with responsive navigation.

#### Acceptance Criteria
- [ ] Header with logo, nav links, user menu
- [ ] Sidebar (desktop) / bottom nav (mobile)
- [ ] Navigation items:
  - Home/Library
  - Upload
  - Queue (pending jobs)
  - Profile/Settings
- [ ] Active state indication
- [ ] Keyboard shortcuts for navigation
- [ ] Dark/light mode toggle

#### Dependencies
- E3-001 (Next.js setup)
- E3-002 (Authentication)

---

### Ticket E3-004: Intake Page per UX Flow
**Priority:** P1 - High  
**Estimate:** 8 hours  
**Labels:** `frontend`, `ux`, `intake`

#### Description
Build the upload/intake page matching `docs/web_ux_flows.md`.

#### Acceptance Criteria
- [ ] Upload zone (drag-drop + click)
- [ ] Processing stages visualization
- [ ] Metadata preview/edit form
- [ ] "Generate Beatmap" CTA
- [ ] Queue position display if jobs pending
- [ ] Link to "How it works" explanation

#### Dependencies
- E1-003 (Upload integration)
- E3-001 (Next.js setup)

---

### Ticket E3-005: Map Detail View with Preview Player
**Priority:** P1 - High  
**Estimate:** 10 hours  
**Labels:** `frontend`, `playback`, `ux`

#### Description
Display beatmap details with audio preview and note visualization.

#### Acceptance Criteria
- [ ] Metadata display: title, artist, BPM, duration, difficulty
- [ ] Audio player with waveform
- [ ] Simple note preview (scrolling lane view)
- [ ] Download button (original audio, beatmap)
- [ ] "Open in Editor" button
- [ ] Verified/unverified badge
- [ ] Share link functionality

#### Implementation Notes
Use Web Audio API + Canvas for lightweight preview.
Consider offloading heavy visualization to Web Worker.

#### Dependencies
- E3-001 (Next.js setup)
- Backend map detail API

---

### Ticket E3-006: Library Page with Saved Maps
**Priority:** P1 - High  
**Estimate:** 6 hours  
**Labels:** `frontend`, `ux`, `library`

#### Description
Display user's saved beatmaps and processing queue.

#### Acceptance Criteria
- [ ] Grid/list toggle view
- [ ] Sort by: date, title, artist
- [ ] Filter by: status (draft, verified, etc.)
- [ ] Search by title/artist
- [ ] Pagination or infinite scroll
- [ ] Empty state with upload CTA

#### Dependencies
- E3-001 (Next.js setup)
- Backend list maps API

---

### Ticket E3-007: Timeline-Lite Editor Component
**Priority:** P2 - Medium  
**Estimate:** 20 hours  
**Labels:** `frontend`, `editor`, `audio`

#### Description
Build reusable timeline component for web-based beatmap editing.

#### Acceptance Criteria
- [ ] WebAudio playback with precise timing
- [ ] Canvas-based note rendering
- [ ] Zoom in/out (0.5x - 4x)
- [ ] Scroll/pan navigation
- [ ] Click to seek
- [ ] Note selection (click, shift-click for range)
- [ ] Note drag (change time)
- [ ] Lane reassignment dropdown
- [ ] Snap to grid toggle
- [ ] Undo/redo (10 levels)
- [ ] Keyboard shortcuts (space=play, del=delete, etc.)

#### Implementation Notes
This is a complex component. Consider:
- Virtual scrolling for performance with many notes
- Web Worker for audio analysis
- Optimistic UI updates

#### Dependencies
- E3-005 (Map detail view)

---

### Ticket E3-008: Comment Markers and Submission Flow
**Priority:** P2 - Medium  
**Estimate:** 8 hours  
**Labels:** `frontend`, `editor`, `collaboration`

#### Description
Allow users to add comments on specific timestamps and submit edits.

#### Acceptance Criteria
- [ ] Comment marker placement on timeline
- [ ] Comment text input (max 500 chars)
- [ ] View existing comments
- [ ] Submit edit proposal with summary
- [ ] Diff visualization: changed notes highlighted
- [ ] Cancel/discard changes

#### Dependencies
- E3-007 (Timeline editor)

---

## Epic 4: Karma & Verification System

### Ticket E4-001: Implement Karma Ledger Table
**Priority:** P1 - High  
**Estimate:** 4 hours  
**Labels:** `backend`, `database`, `karma`

#### Description
Create karma ledger for tracking user reputation changes.

#### Acceptance Criteria
- [ ] `karma_ledger` table with fields:
  - `id`, `user_id`, `delta`, `reason`, `related_entity_id`, `created_at`
- [ ] Trigger to update `users.karma_score` on insert
- [ ] Index on `user_id`, `created_at`
- [ ] Audit trail preserved (no deletions)

#### Schema
```sql
CREATE TABLE karma_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    delta INTEGER NOT NULL,
    reason VARCHAR(50) NOT NULL, -- 'map_verified', 'edit_accepted', etc.
    related_entity_id UUID,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Dependencies
- User table exists

---

### Ticket E4-002: Implement Roles and User Roles Tables
**Priority:** P1 - High  
**Estimate:** 4 hours  
**Labels:** `backend`, `database`, `auth`

#### Description
Create role-based access control schema.

#### Acceptance Criteria
- [ ] `roles` table: id, name, permissions (JSONB)
- [ ] `user_roles` table: user_id, role_id, granted_at
- [ ] Default roles: `user`, `verifier`, `admin`
- [ ] Permission checks in API middleware
- [ ] Role assignment API (admin only)

#### Roles Definition
```python
ROLES = {
    "user": {"can_upload": True, "can_edit": True},
    "verifier": {"can_verify": True, "can_reject": True},
    "admin": {"all": True}
}
```

#### Dependencies
- E4-001 (Karma ledger)

---

### Ticket E4-003: Background Job for Karma Score Recomputation
**Priority:** P2 - Medium  
**Estimate:** 4 hours  
**Labels:** `backend`, `cron`, `karma`

#### Description
Periodic job to recalculate karma scores and handle decay.

#### Acceptance Criteria
- [ ] Runs daily at 00:00 UTC
- [ ] Recalculates `users.karma_score` from ledger
- [ ] Applies seasonal decay (configurable %)
- [ ] Logs anomalies (large swings)
- [ ] Idempotent execution

#### Dependencies
- E4-001 (Karma ledger)

---

### Ticket E4-004: Verifier Dashboard UI
**Priority:** P1 - High  
**Estimate:** 12 hours  
**Labels:** `frontend`, `verification`, `ux`

#### Description
Build dashboard for verifiers to review and approve map edits.

#### Acceptance Criteria
- [ ] Queue view: pending proposals sorted by age
- [ ] Filters: song, proposer, type of edit
- [ ] Side-by-side diff view
- [ ] Approve/reject buttons with comment
- [ ] Bulk actions (approve multiple)
- [ ] Stats: verified today, pending count

#### Dependencies
- E4-002 (Roles)
- E3-007 (Timeline component for diff view)

---

### Ticket E4-005: Verification Decision Endpoint
**Priority:** P1 - High  
**Estimate:** 6 hours  
**Labels:** `backend`, `api`, `verification`

#### Description
API endpoint to record verification decisions.

#### Acceptance Criteria
- [ ] `POST /api/v1/proposals/{id}/decision`
- [ ] Body: `{decision: "approve"|"reject", comment: string}`
- [ ] Updates `map_edit_proposals` status
- [ ] Creates `map_verification_decisions` record
- [ ] Awards karma to fixer (if approved)
- [ ] Awards karma to verifier
- [ ] Triggers notifications

#### Dependencies
- E4-002 (Roles)
- E4-001 (Karma ledger)

---

### Ticket E4-006: Karma Leaderboard API and UI
**Priority:** P3 - Low  
**Estimate:** 6 hours  
**Labels:** `frontend`, `backend`, `gamification`

#### Description
Display top contributors by karma.

#### Acceptance Criteria
- [ ] API: `GET /api/v1/leaderboard?period=week|month|all`
- [ ] Returns top 50 users with karma, verified count
- [ ] UI: leaderboard page with rankings
- [ ] Current user's rank highlighted
- [ ] Badges displayed next to names

#### Dependencies
- E4-001 (Karma ledger)

---

## Epic 5: Monetization & Subscription

### Ticket E5-001: Create Stripe Checkout Session Endpoint
**Priority:** P1 - High  
**Estimate:** 6 hours  
**Labels:** `backend`, `payments`, `stripe`

#### Description
Implement Stripe Checkout for subscription purchases.

#### Acceptance Criteria
- [ ] `POST /api/v1/subscriptions/checkout`
- [ ] Creates Stripe Checkout session
- [ ] Supports monthly and annual plans
- [ ] Redirect URLs for success/cancel
- [ ] Price IDs from environment config
- [ ] Customer created/linked in Stripe

#### Dependencies
- Stripe account configured
- E3-002 (Authentication)

---

### Ticket E5-002: Handle Stripe Webhooks
**Priority:** P0 - Critical Path  
**Estimate:** 8 hours  
**Labels:** `backend`, `payments`, `webhooks`

#### Description
Process Stripe webhook events for subscription lifecycle.

#### Acceptance Criteria
- [ ] Webhook endpoint: `POST /api/v1/webhooks/stripe`
- [ ] Signature verification
- [ ] Handle events:
  - `checkout.session.completed` → create subscription
  - `invoice.paid` → extend subscription
  - `customer.subscription.deleted` → cancel subscription
  - `invoice.payment_failed` → send warning email
- [ ] Idempotent processing
- [ ] Event logging for audit

#### Dependencies
- E5-001 (Checkout endpoint)

---

### Ticket E5-003: Track AI Usage per Subscription Period
**Priority:** P1 - High  
**Estimate:** 4 hours  
**Labels:** `backend`, `quota`, `usage`

#### Description
Track and enforce AI generation usage limits.

#### Acceptance Criteria
- [ ] `usage` table: user_id, period_start, period_end, ai_jobs_count
- [ ] Increment on job completion
- [ ] Reset on subscription renewal
- [ ] API to check remaining quota
- [ ] Tier limits:
  - Free: 5 generations/month
  - Pro: 100 generations/month

#### Dependencies
- E5-002 (Webhook handling)

---

### Ticket E5-004: Quota Exceeded UX and Upsell
**Priority:** P2 - Medium  
**Estimate:** 4 hours  
**Labels:** `frontend`, `monetization`, `ux`

#### Description
Display upgrade prompt when user exceeds quota.

#### Acceptance Criteria
- [ ] Modal shown when generation blocked
- [ ] Display: current usage, limit, reset date
- [ ] "Upgrade to Pro" CTA
- [ ] Alternative: "Wait until [date]"
- [ ] Track conversion events

#### Dependencies
- E5-003 (Usage tracking)
- E5-001 (Checkout endpoint)

---

## Epic 6: Observability & Operations

### Ticket E6-001: Deploy Prometheus/Grafana Stack
**Priority:** P1 - High  
**Estimate:** 8 hours  
**Labels:** `infrastructure`, `monitoring`, `devops`

#### Description
Set up monitoring infrastructure for API and workers.

#### Acceptance Criteria
- [ ] Prometheus deployed (EKS or EC2)
- [ ] Grafana deployed with persistent storage
- [ ] Service discovery for backend services
- [ ] Default dashboards:
  - API latency and error rates
  - Queue depth and processing time
  - GPU utilization (if applicable)
- [ ] Retention: 30 days

#### Dependencies
- Kubernetes cluster or VM infrastructure

---

### Ticket E6-002: Expose Application Metrics
**Priority:** P1 - High  
**Estimate:** 6 hours  
**Labels:** `backend`, `monitoring`, `metrics`

#### Description
Add Prometheus metrics to API and workers.

#### Acceptance Criteria
- [ ] `/metrics` endpoint on all services
- [ ] Metrics:
  - `http_requests_total{method, path, status}`
  - `http_request_duration_seconds{method, path}`
  - `ai_jobs_queue_depth`
  - `ai_job_duration_seconds{stage}`
  - `ai_job_errors_total{error_type}`
- [ ] FastAPI middleware for automatic HTTP metrics

#### Dependencies
- E6-001 (Prometheus stack)

---

### Ticket E6-003: Configure Alert Thresholds
**Priority:** P2 - Medium  
**Estimate:** 4 hours  
**Labels:** `monitoring`, `alerting`, `devops`

#### Description
Set up alerting rules for critical conditions.

#### Acceptance Criteria
- [ ] Alert rules in Prometheus/Alertmanager:
  - GPU queue > 15 minutes: warning
  - Error rate > 2%: critical
  - API latency p99 > 5s: warning
  - Service down: critical
- [ ] Slack/PagerDuty integration
- [ ] Runbook links in alert messages

#### Dependencies
- E6-002 (Metrics exposed)

---

### Ticket E6-004: AWS Budget Alerts
**Priority:** P2 - Medium  
**Estimate:** 2 hours  
**Labels:** `infrastructure`, `cost`, `aws`

#### Description
Configure AWS Budgets for cost monitoring.

#### Acceptance Criteria
- [ ] Monthly budget: $X (configurable)
- [ ] Alerts at 50%, 80%, 100% of budget
- [ ] Email notification to ops team
- [ ] Breakdown by service (EC2, S3, etc.)

#### Dependencies
- AWS account

---

### Ticket E6-005: GitHub Actions CI Pipeline
**Priority:** P0 - Critical Path  
**Estimate:** 6 hours  
**Labels:** `ci`, `devops`, `testing`

#### Description
Set up continuous integration for backend and frontend.

#### Acceptance Criteria
- [ ] Workflow triggers on PR and push to main
- [ ] Backend:
  - Lint (ruff)
  - Type check (mypy)
  - Unit tests (pytest)
  - Coverage report
- [ ] Frontend:
  - Lint (ESLint)
  - Type check (tsc)
  - Unit tests (Jest/Vitest)
  - Build verification
- [ ] Status checks required for merge

#### Dependencies
- Repository configured

---

### Ticket E6-006: Infrastructure Deployment Pipeline
**Priority:** P1 - High  
**Estimate:** 8 hours  
**Labels:** `ci`, `infrastructure`, `terraform`

#### Description
Automate infrastructure changes via Terraform in CI.

#### Acceptance Criteria
- [ ] Terraform plan on PR (comment with diff)
- [ ] Terraform apply on merge to main
- [ ] State stored in S3 with DynamoDB locking
- [ ] Separate workspaces for staging/production
- [ ] Manual approval gate for production

#### Dependencies
- Terraform state backend
- AWS credentials in GitHub secrets

---

### Ticket E6-007: Frontend Deployment Pipeline
**Priority:** P1 - High  
**Estimate:** 4 hours  
**Labels:** `ci`, `frontend`, `deployment`

#### Description
Automate frontend deployment to Vercel or CloudFront.

#### Acceptance Criteria
- [ ] Preview deployments on PR
- [ ] Production deployment on merge to main
- [ ] Environment variables injected
- [ ] Cache invalidation on deploy
- [ ] Rollback capability

#### Dependencies
- E6-005 (CI pipeline)
- Vercel/CloudFront configured

---

## Summary

| Epic | Tickets | P0 | P1 | P2 | P3 |
|------|---------|----|----|----|----|
| E1 - Intake | 8 | 3 | 4 | 1 | 0 |
| E2 - AI Pipeline | 7 | 4 | 2 | 1 | 1 |
| E3 - Web App | 8 | 2 | 4 | 2 | 0 |
| E4 - Karma | 6 | 0 | 4 | 1 | 1 |
| E5 - Monetization | 4 | 1 | 2 | 1 | 0 |
| E6 - Observability | 7 | 1 | 4 | 2 | 0 |
| **Total** | **40** | **11** | **20** | **8** | **2** |

**Estimated Total Effort:** ~250 hours (assuming single developer)

---

*Next Steps:*
1. Import tickets to GitHub Issues
2. Assign to sprint milestones per sequencing in `web_mvp_task_breakdown.md`
3. Add story points after team review
4. Create epic tracking issues to group related tickets
