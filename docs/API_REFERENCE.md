# BeatSight Backend API Reference

*Version: 1.0.0*  
*Base URL: `https://api.beatsight.io/v1` (production) | `http://localhost:8000` (development)*

---

## Overview

The BeatSight API provides endpoints for managing songs, beatmaps, AI generation jobs, and user authentication. All endpoints return JSON responses and accept JSON request bodies where applicable.

### Authentication

Most endpoints support optional or required JWT authentication. Include the access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### Common Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 202 | Accepted (async job queued) |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid or missing token |
| 404 | Not Found |
| 409 | Conflict - Resource already exists |
| 422 | Validation Error |
| 500 | Internal Server Error |

### Pagination

List endpoints support cursor-based pagination (planned):

```
GET /songs?limit=20&cursor=<cursor_token>
```

---

## Authentication (`/auth`)

### Register

Create a new user account.

```http
POST /auth/register
```

**Request Body:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | string (email) | Yes | Valid email format |
| `password` | string | Yes | 8-128 characters |
| `display_name` | string | Yes | 2-120 characters |

**Example Request:**

```json
{
  "email": "drummer@example.com",
  "password": "securePassword123",
  "display_name": "DrumMaster"
}
```

**Response (201 Created):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| 409 | "An account with this email already exists" |
| 422 | Validation error (password too short, invalid email, etc.) |

---

### Login

Authenticate an existing user.

```http
POST /auth/login
```

**Request Body:**

| Field | Type | Required |
|-------|------|----------|
| `email` | string (email) | Yes |
| `password` | string | Yes |

**Example Request:**

```json
{
  "email": "drummer@example.com",
  "password": "securePassword123"
}
```

**Response (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| 401 | "Invalid email or password" |

---

### Refresh Token

Exchange a refresh token for new access and refresh tokens.

```http
POST /auth/refresh
```

**Request Body:**

| Field | Type | Required |
|-------|------|----------|
| `refresh_token` | string | Yes |

**Response (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| 401 | "Invalid or expired refresh token" |

---

### Get Current User

Retrieve the authenticated user's profile.

```http
GET /auth/me
```

**Headers:**
- `Authorization: Bearer <access_token>` (required)

**Response (200 OK):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "drummer@example.com",
  "display_name": "DrumMaster",
  "email_verified": false,
  "karma_score": 0,
  "created_at": "2025-11-24T12:00:00Z"
}
```

---

## Songs (`/songs`)

### Create Song

Register a new song in the database.

```http
POST /songs
```

**Request Body:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | string | Yes | Max 255 chars |
| `artist` | string | Yes | Max 255 chars |
| `bpm` | integer | No | 40-400 |
| `fingerprint_hash` | string | Yes | Max 128 chars (audio fingerprint) |

**Example Request:**

```json
{
  "title": "Tom Sawyer",
  "artist": "Rush",
  "bpm": 88,
  "fingerprint_hash": "af3b2c1d4e5f6a7b8c9d0e1f2a3b4c5d"
}
```

**Response (201 Created):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Tom Sawyer",
  "artist": "Rush",
  "bpm": 88,
  "status": "pending",
  "canonical_map_id": null,
  "created_at": "2025-11-24T12:00:00Z",
  "updated_at": "2025-11-24T12:00:00Z",
  "maps": []
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| 409 | "Song already exists" (duplicate fingerprint) |

---

### List Songs

Retrieve all songs.

```http
GET /songs
```

**Response (200 OK):**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Tom Sawyer",
    "artist": "Rush",
    "bpm": 88,
    "status": "mapped",
    "canonical_map_id": "660e8400-e29b-41d4-a716-446655440001",
    "created_at": "2025-11-24T12:00:00Z",
    "updated_at": "2025-11-24T13:00:00Z",
    "maps": [
      {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "difficulty_label": "Normal",
        "is_canonical": true,
        "state": "published",
        "current_version_id": "770e8400-e29b-41d4-a716-446655440002"
      }
    ]
  }
]
```

---

### Get Song

Retrieve a specific song by ID.

```http
GET /songs/{song_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `song_id` | UUID | The song's unique identifier |

**Response (200 OK):** Same as single item in list response.

**Error Responses:**

| Code | Detail |
|------|--------|
| 404 | "Song not found" |

---

### Update Song

Update song metadata.

```http
PATCH /songs/{song_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `song_id` | UUID | The song's unique identifier |

**Request Body:** (all fields optional)

| Field | Type | Constraints |
|-------|------|-------------|
| `title` | string | Max 255 chars |
| `artist` | string | Max 255 chars |
| `bpm` | integer | 40-400 |
| `status` | string | One of: `pending`, `mapped`, `verified`, `archived` |
| `canonical_map_id` | UUID | Reference to canonical beatmap |

**Example Request:**

```json
{
  "bpm": 176,
  "status": "verified"
}
```

**Response (200 OK):** Updated song object.

---

## AI Jobs (`/ai-jobs`)

### Enqueue Job

Queue an AI beatmap generation job.

```http
POST /ai-jobs
```

**Headers:**
- `Authorization: Bearer <access_token>` (optional - associates job with user)

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `song_id` | UUID | Yes | Song to generate beatmap for |
| `priority` | string | No | `standard` (default) or `priority` |

**Example Request:**

```json
{
  "song_id": "550e8400-e29b-41d4-a716-446655440000",
  "priority": "standard"
}
```

**Response (202 Accepted):**

```json
{
  "job": {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "song_id": "550e8400-e29b-41d4-a716-446655440000",
    "priority": "standard",
    "state": "queued",
    "error_message": null,
    "requested_by_id": "550e8400-e29b-41d4-a716-446655440000",
    "worker_id": null,
    "last_heartbeat": null,
    "progress_percent": null,
    "progress_message": null,
    "started_at": null,
    "finished_at": null,
    "created_at": "2025-11-24T12:00:00Z"
  },
  "queue_position": 3,
  "estimated_wait_minutes": 9,
  "quota": {
    "plan": "free",
    "used_this_month": 5,
    "used_today": 1,
    "remaining_month": 5,
    "remaining_today": 2,
    "limit_month": 10,
    "limit_day": 3,
    "resets_at": "2025-12-01T00:00:00Z",
    "priority": 50
  }
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| 404 | Song not found |
| 429 | Quota exceeded (see response body for details) |

**429 Response:**

```json
{
  "detail": {
    "message": "AI generation quota exceeded",
    "limit": 10,
    "used": 10,
    "resets_at": "2025-12-01T00:00:00Z"
  }
}
```

---

### Get Quota Status

Get current AI generation quota for the authenticated user.

```http
GET /ai-jobs/quota
```

**Headers:**
- `Authorization: Bearer <access_token>` (optional - returns anonymous limits if not provided)

**Response (200 OK):**

```json
{
  "plan": "free",
  "used_this_month": 5,
  "used_today": 1,
  "remaining_month": 5,
  "remaining_today": 2,
  "limit_month": 10,
  "limit_day": 3,
  "resets_at": "2025-12-01T00:00:00Z",
  "priority": 50
}
```

**Quota Limits by Plan:**

| Plan | Monthly Limit | Daily Limit | Priority |
|------|---------------|-------------|----------|
| Anonymous | 3 | 1 | 25 (low) |
| Free | 10 | 3 | 50 (standard) |
| Pro | 100 | 20 | 100 (high) |

---

### List Jobs

List AI jobs with optional filtering.

```http
GET /ai-jobs?song_id={song_id}
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `song_id` | UUID | No | Filter by song |

**Response (200 OK):**

```json
[
  {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "song_id": "550e8400-e29b-41d4-a716-446655440000",
    "priority": "standard",
    "state": "complete",
    "error_message": null,
    "requested_by_id": "550e8400-e29b-41d4-a716-446655440000",
    "worker_id": "990e8400-e29b-41d4-a716-446655440000",
    "last_heartbeat": "2025-11-24T12:02:55Z",
    "progress_percent": 100,
    "progress_message": "Complete",
    "started_at": "2025-11-24T12:01:00Z",
    "finished_at": "2025-11-24T12:03:00Z",
    "created_at": "2025-11-24T12:00:00Z"
  }
]
```

---

### Get Job

Retrieve a specific AI job by ID.

```http
GET /ai-jobs/{job_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | UUID | The job's unique identifier |

**Response (200 OK):** Same as single item in list response.

**Error Responses:**

| Code | Detail |
|------|--------|
| 404 | "Job {job_id} not found" |

---

### Stream Job Progress (SSE)

Stream real-time progress updates for a job via Server-Sent Events.

```http
GET /ai-jobs/{job_id}/progress/stream
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | UUID | The job's unique identifier |

**Response:** `text/event-stream`

The stream sends the following event types:

| Event | Description |
|-------|-------------|
| `status` | Initial job status when connecting |
| `progress` | Progress updates (percent, message, stage) |
| `complete` | Job completed successfully |
| `error` | Job failed or was cancelled |
| `timeout` | Connection closed due to inactivity |

**Event Examples:**

```
event: status
data: {"job_id": "880e8400-...", "status": "processing", "percent": 45, "message": "Separating drums..."}

event: progress
data: {"percent": 60, "message": "Transcribing notes...", "stage": "transcription", "timestamp": "2025-11-24T12:02:00Z"}

event: complete
data: {"job_id": "880e8400-...", "status": "completed", "beatmap_id": "aa0e8400-..."}

event: error
data: {"job_id": "880e8400-...", "status": "failed", "error": "Processing failed: out of memory"}
```

**Client Usage Example (JavaScript):**

```javascript
const eventSource = new EventSource('/api/v1/ai-jobs/{job_id}/progress/stream');

eventSource.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`Progress: ${data.percent}% - ${data.message}`);
  updateProgressBar(data.percent);
});

eventSource.addEventListener('complete', (e) => {
  const data = JSON.parse(e.data);
  console.log('Job completed! Beatmap:', data.beatmap_id);
  eventSource.close();
});

eventSource.addEventListener('error', (e) => {
  if (e.data) {
    const data = JSON.parse(e.data);
    console.error('Job failed:', data.error);
  }
  eventSource.close();
});
```

**Error Responses:**

| Code | Detail |
|------|--------|
| 404 | "Job {job_id} not found" |

---

## Credits (`/credits`)

Manage user credit balance for pay-per-use AI generations beyond subscription limits.

### Get Balance

Get current user's credit balance.

```http
GET /credits/balance
```

**Authentication:** Required

**Response (200 OK):**

```json
{
  "purchased_credits": 25,
  "bonus_credits": 5,
  "total_credits": 30,
  "auto_topup_enabled": false,
  "auto_topup_pack": null,
  "auto_topup_threshold": 0
}
```

---

### Get Credit Packs

List available credit packs for purchase.

```http
GET /credits/packs
```

**Authentication:** Not required

**Response (200 OK):**

```json
[
  {
    "id": "starter",
    "name": "Starter Pack",
    "description": "5 credits for casual use",
    "credits": 5,
    "price_cents": 175,
    "price_dollars": 1.75,
    "per_credit_cents": 35.0,
    "savings_percent": 0
  },
  {
    "id": "value",
    "name": "Value Pack",
    "description": "15 credits - Save 14%",
    "credits": 15,
    "price_cents": 450,
    "price_dollars": 4.50,
    "per_credit_cents": 30.0,
    "savings_percent": 14
  },
  {
    "id": "power",
    "name": "Power Pack",
    "description": "40 credits - Save 29%",
    "credits": 40,
    "price_cents": 1000,
    "price_dollars": 10.00,
    "per_credit_cents": 25.0,
    "savings_percent": 29
  }
]
```

---

### Purchase Credits

Create a Stripe checkout session to purchase a credit pack.

```http
POST /credits/purchase
```

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pack_type` | string | Yes | Pack ID: `starter`, `value`, or `power` |

**Example Request:**

```json
{
  "pack_type": "value"
}
```

**Response (200 OK):**

```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "session_id": "cs_test_abc123..."
}
```

Redirect the user to `checkout_url` to complete the purchase. After successful payment, user is redirected to `/credits/success?session_id={session_id}`.

---

### Get Purchase History

Get user's credit purchase history.

```http
GET /credits/history?limit=20&offset=0
```

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max items to return (1-100) |
| `offset` | integer | 0 | Items to skip |

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "uuid",
      "pack_type": "value",
      "credits_amount": 15,
      "price_cents": 450,
      "is_fulfilled": true,
      "fulfilled_at": "2025-12-02T10:30:00Z",
      "created_at": "2025-12-02T10:29:45Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

---

### Configure Auto Top-up

Enable or disable automatic credit purchases when balance is low.

```http
PUT /credits/auto-topup
```

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | Yes | Enable/disable auto top-up |
| `threshold` | integer | No | Trigger when balance <= this value |
| `pack_type` | string | No | Pack to auto-purchase |

**Example Request (Enable):**

```json
{
  "enabled": true,
  "threshold": 3,
  "pack_type": "value"
}
```

**Example Request (Disable):**

```json
{
  "enabled": false
}
```

**Response (200 OK):**

```json
{
  "auto_topup_enabled": true,
  "auto_topup_threshold": 3,
  "auto_topup_pack": "value"
}
```

---

### Credit Consumption Flow

Credits are automatically consumed when:
1. User exceeds their subscription quota (Free: 3/month, Pro: 50/month)
2. User has available credits in their balance
3. Bonus credits are consumed before purchased credits

The consumption happens during AI job creation. If the user has no subscription quota remaining and no credits, the job creation will fail with a 402 Payment Required error.

---

## Worker Endpoints (`/ai-jobs` - Internal)

These endpoints are used by AI worker processes and should not be called by clients.

### Claim Job

Claim the next available job for processing.

```http
POST /ai-jobs/claim?worker_id={worker_id}
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `worker_id` | UUID | Yes | Worker's unique identifier |

**Response (200 OK):** Job object or `null` if no jobs available.

---

### Worker Heartbeat

Signal that a worker is still processing a job.

```http
POST /ai-jobs/{job_id}/heartbeat?worker_id={worker_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | UUID | The job being processed |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `worker_id` | UUID | Yes | Worker's unique identifier |

**Response (204 No Content)**

**Error Responses:**

| Code | Detail |
|------|--------|
| 404 | "Job {job_id} not found" |
| 409 | "Job is being processed by another worker" |

---

### Update Progress

Update job progress during processing.

```http
PATCH /ai-jobs/{job_id}/progress
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `progress_percent` | integer | Yes | 0-100 |
| `progress_message` | string | No | Status message |

**Example Request:**

```json
{
  "progress_percent": 65,
  "progress_message": "Transcribing drum notes..."
}
```

**Response (204 No Content)**

---

### Release Job

Release a job back to the queue for retry.

```http
POST /ai-jobs/{job_id}/release
```

**Response (204 No Content)**

---

### List Stale Jobs

List jobs with stale heartbeats (for orchestration).

```http
GET /ai-jobs/stale/list?threshold_seconds={seconds}
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold_seconds` | integer | 300 | Heartbeat staleness threshold |

**Response (200 OK):** Array of stale job objects.

---

### Job States

| State | Description |
|-------|-------------|
| `queued` | Job is waiting to be processed |
| `processing` | Job is currently running |
| `complete` | Job finished successfully |
| `failed` | Job encountered an error |
| `cancelled` | Job was cancelled by user |

---

## Health (`/health`)

### Health Check

Check API health status.

```http
GET /health
```

**Response (200 OK):**

```json
{
  "status": "ok",
  "timestamp": "2025-11-24T12:00:00Z"
}
```

---

## Data Types

### Song Status

| Value | Description |
|-------|-------------|
| `pending` | Song registered but no beatmap yet |
| `mapped` | Has at least one beatmap |
| `verified` | Beatmap reviewed and approved |
| `archived` | Song/beatmap no longer active |

### Map State

| Value | Description |
|-------|-------------|
| `draft` | Beatmap is being edited |
| `review` | Submitted for community review |
| `published` | Available for play |
| `rejected` | Did not pass review |

### Priority Tiers

| Value | Description |
|-------|-------------|
| `standard` | Normal queue priority |
| `priority` | Expedited processing (premium users) |

---

## Common Response Codes (Extended)

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 202 | Accepted (async job queued) |
| 204 | No Content (success with no body) |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid or missing token |
| 404 | Not Found |
| 409 | Conflict - Resource already exists or state conflict |
| 422 | Validation Error |
| 429 | Too Many Requests - Rate limit or quota exceeded |
| 500 | Internal Server Error |

---

## Rate Limits

| Endpoint Group | Limit | Window |
|----------------|-------|--------|
| Authentication | 10 requests | 1 minute |
| Songs (read) | 100 requests | 1 minute |
| Songs (write) | 20 requests | 1 minute |
| AI Jobs | 5 requests | 1 minute |

Rate limit headers:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Webhooks (Planned)

Future webhook support for job completion notifications:

```json
{
  "event": "ai_job.complete",
  "timestamp": "2025-11-24T12:03:00Z",
  "data": {
    "job_id": "880e8400-e29b-41d4-a716-446655440000",
    "song_id": "550e8400-e29b-41d4-a716-446655440000",
    "state": "complete"
  }
}
```

---

## SDK Support (Planned)

Official SDKs will be available for:
- TypeScript/JavaScript
- Python
- C# (desktop integration)

---

## Changelog

### v1.1.0 (November 2025)
- Added quota management endpoints (`GET /ai-jobs/quota`)
- Added SSE progress streaming (`GET /ai-jobs/{id}/progress/stream`)
- Added worker coordination endpoints (claim, heartbeat, release, stale)
- Enhanced job response with queue position and estimated wait time
- Added 429 response for quota exceeded scenarios
- Job objects now include `worker_id`, `last_heartbeat`, `progress_percent`, `progress_message`

### v1.0.0 (November 2025)
- Initial API release
- Authentication endpoints (register, login, refresh, me)
- Song CRUD operations
- AI job queue management
- Health check endpoint
