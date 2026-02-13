# BeatSight Web API Reference

This document describes the REST API endpoints available in the BeatSight web backend.

## Base URL

All API endpoints are prefixed with `/api`.

## Authentication

Most endpoints require authentication via JWT Bearer tokens.

```
Authorization: Bearer <access_token>
```

### Auth Endpoints

#### POST /api/auth/register
Register a new user account.

**Request Body:**
```json
{
    "email": "user@example.com",
    "password": "securepassword",
    "display_name": "DrumMaster"
}
```

**Response (201):**
```json
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer"
}
```

#### POST /api/auth/login
Authenticate and obtain tokens.

**Request Body:**
```json
{
    "email": "user@example.com",
    "password": "securepassword"
}
```

**Response (200):**
```json
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer"
}
```

#### POST /api/auth/refresh
Refresh an expired access token.

**Request Body:**
```json
{
    "refresh_token": "eyJ..."
}
```

#### GET /api/auth/me
Get current user's profile. Requires authentication.

**Response (200):**
```json
{
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "DrumMaster",
    "email_verified": true,
    "karma_score": 100,
    "created_at": "2025-01-01T00:00:00Z"
}
```

---

## Songs

#### GET /api/songs
List all songs for the current user.

**Query Parameters:**
- `skip` (int, default: 0) - Pagination offset
- `limit` (int, default: 50) - Page size

**Response (200):**
```json
[
    {
        "id": "uuid",
        "title": "Song Title",
        "artist": "Artist Name",
        "bpm": 120,
        "status": "ready",
        "canonical_map_id": "uuid",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z"
    }
]
```

#### GET /api/songs/{song_id}
Get a single song by ID.

#### POST /api/songs
Create a new song record.

**Request Body:**
```json
{
    "title": "Song Title",
    "artist": "Artist Name",
    "audio_key": "storage/path/to/audio.mp3"
}
```

---

## AI Jobs

#### GET /api/ai-jobs
List AI processing jobs.

**Query Parameters:**
- `song_id` (uuid, optional) - Filter by song
- `state` (string, optional) - Filter by state (queued, processing, complete, failed, cancelled)

**Response (200):**
```json
[
    {
        "id": "uuid",
        "song_id": "uuid",
        "state": "processing",
        "priority": "standard",
        "error_message": null,
        "progress_percent": 45,
        "progress_message": "Separating audio stems...",
        "created_at": "2025-01-01T00:00:00Z",
        "started_at": "2025-01-01T00:00:30Z",
        "finished_at": null
    }
]
```

#### POST /api/ai-jobs
Enqueue a new AI job.

**Request Body:**
```json
{
    "audio_key": "storage/path/to/audio.mp3",
    "priority": 50
}
```

**Response (201):**
```json
{
    "job": { ... },
    "queue_position": 3,
    "estimated_wait_minutes": 15,
    "quota": { ... }
}
```

#### GET /api/ai-jobs/{job_id}
Get job details.

#### POST /api/ai-jobs/{job_id}/cancel
Cancel a queued or processing job.

#### POST /api/ai-jobs/{job_id}/retry
Retry a failed job.

#### GET /api/ai-jobs/quota
Get current user's quota status.

**Response (200):**
```json
{
    "plan": "free",
    "used_this_month": 5,
    "used_today": 1,
    "remaining_month": 10,
    "remaining_today": 4,
    "limit_month": 15,
    "limit_day": 5,
    "resets_at": "2025-02-01T00:00:00Z",
    "priority": 50
}
```

#### GET /api/ai-jobs/queue-length
Get current queue length.

---

## Storage

#### POST /api/storage/upload/{category}
Upload a file directly.

**Request:** Multipart form data with `file` field.

**Response (200):**
```json
{
    "key": "audio/uuid/filename.mp3",
    "url": "https://...",
    "size": 10485760
}
```

#### POST /api/storage/presigned-upload
Get a presigned URL for client-side upload.

**Request Body:**
```json
{
    "category": "audio",
    "filename": "song.mp3",
    "content_type": "audio/mpeg"
}
```

---

## Roles & Permissions (RBAC)

#### GET /api/roles
List all roles (admin only).

#### GET /api/roles/my-roles
Get current user's roles.

#### GET /api/roles/check/{permission}
Check if user has a specific permission.

**Response (200):**
```json
{
    "has_permission": true
}
```

---

## Metadata Detection

#### POST /api/metadata/identify
Identify a song using audio fingerprinting (AcoustID/MusicBrainz).

**Request Body:**
```json
{
    "audio_key": "storage/path/to/audio.mp3"
}
```

**Response (200):**
```json
{
    "title": "Detected Title",
    "artist": "Detected Artist",
    "album": "Album Name",
    "release_date": "2023",
    "confidence": 0.95,
    "provider": "musicbrainz"
}
```

---

## Cloud Sync

#### GET /api/sync/preferences
Get user preferences.

#### PUT /api/sync/preferences
Update user preferences.

**Request Body:**
```json
{
    "theme": "dark",
    "default_quantization": "16th",
    "auto_generate": true
}
```

#### GET /api/sync/status
Get sync status for all clients.

#### POST /api/sync/clients
Register a new sync client.

---

## Billing

#### GET /api/billing/pricing
Get pricing table for display. No authentication required.

**Response (200):**
```json
{
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "ai_quota": 5,
        "features": ["Basic beatmap analysis", "5 AI jobs/month"]
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 9.99,
        "ai_quota": 100,
        "features": ["Advanced analysis", "100 AI jobs/month", "Priority processing"]
    },
    "studio": {
        "name": "Studio",
        "price_monthly": 29.99,
        "ai_quota": -1,
        "features": ["Unlimited AI jobs", "API access", "Premium support"]
    }
}
```

#### GET /api/billing/config
Get Stripe configuration for client-side. No authentication required.

**Response (200):**
```json
{
    "publishable_key": "pk_live_...",
    "is_configured": true
}
```

#### GET /api/billing/subscription
Get current user's subscription status. Requires authentication.

**Response (200):**
```json
{
    "plan": "pro",
    "status": "active",
    "ai_quota_remaining": 85,
    "current_period_end": "2025-02-01T00:00:00Z",
    "is_active": true
}
```

#### POST /api/billing/checkout
Create a Stripe checkout session. Requires authentication.

**Request Body:**
```json
{
    "plan": "pro",
    "success_url": "https://app.beatsight.app/billing/success",
    "cancel_url": "https://app.beatsight.app/billing/cancel"
}
```

**Response (200):**
```json
{
    "session_id": "cs_...",
    "checkout_url": "https://checkout.stripe.com/..."
}
```

#### POST /api/billing/portal
Create a Stripe customer portal session. Requires authentication.

**Response (200):**
```json
{
    "portal_url": "https://billing.stripe.com/..."
}
```

#### POST /api/billing/webhook
Handle Stripe webhooks. Requires valid Stripe signature.

---

## Karma

#### GET /api/karma
Get current user's karma summary. Requires authentication.

**Response (200):**
```json
{
    "user_id": "uuid",
    "karma_score": 150,
    "rank": 42,
    "daily_ai_quota": 10,
    "eligible_roles": ["mapper", "curator"],
    "current_roles": ["mapper"]
}
```

#### GET /api/karma/history
Get user's karma history. Requires authentication.

**Query Parameters:**
- `limit` (int, default: 50) - Page size
- `offset` (int, default: 0) - Pagination offset

**Response (200):**
```json
{
    "items": [
        {
            "id": "uuid",
            "delta": 10,
            "reason": "map_upvoted",
            "related_entity_type": "map",
            "related_entity_id": "uuid",
            "recorded_at": "2025-01-15T10:30:00Z"
        }
    ],
    "total_count": 25,
    "limit": 50,
    "offset": 0
}
```

#### GET /api/karma/stats
Get detailed karma statistics. Requires authentication.

**Response (200):**
```json
{
    "current_score": 150,
    "rank": 42,
    "breakdown": [
        {"reason": "map_upvoted", "total": 100, "count": 10},
        {"reason": "daily_login", "total": 50, "count": 50}
    ],
    "eligible_roles": ["mapper", "curator"],
    "current_roles": ["mapper"],
    "daily_ai_quota": 10
}
```

#### GET /api/karma/leaderboard
Get karma leaderboard.

**Query Parameters:**
- `limit` (int, default: 10) - Number of entries
- `offset` (int, default: 0) - Pagination offset

**Response (200):**
```json
{
    "entries": [
        {"rank": 1, "user_id": "uuid", "display_name": "DrumLord", "karma_score": 5000},
        {"rank": 2, "user_id": "uuid", "display_name": "BeatMaster", "karma_score": 4500}
    ],
    "limit": 10,
    "offset": 0
}
```

#### GET /api/karma/thresholds
Get karma thresholds for roles. No authentication required.

**Response (200):**
```json
{
    "thresholds": [
        {"role": "mapper", "threshold": 50, "description": "Can submit maps"},
        {"role": "curator", "threshold": 500, "description": "Can feature maps"}
    ]
}
```

---

## Votes

#### GET /api/maps/{map_id}/votes
Get vote counts for a map.

**Response (200):**
```json
{
    "map_id": "uuid",
    "upvotes": 42,
    "downvotes": 3,
    "score": 39,
    "user_vote": "upvote"
}
```

#### POST /api/maps/{map_id}/vote
Vote on a map. Requires authentication.

**Request Body:**
```json
{
    "action": "upvote"
}
```
Allowed values: `upvote`, `downvote`

**Response (200):**
```json
{
    "map_id": "uuid",
    "upvotes": 43,
    "downvotes": 3,
    "score": 40,
    "user_vote": "upvote"
}
```

#### DELETE /api/maps/{map_id}/vote
Remove vote from a map. Requires authentication.

**Response (200):**
```json
{
    "map_id": "uuid",
    "upvotes": 42,
    "downvotes": 3,
    "score": 39,
    "user_vote": null
}
```

#### POST /api/maps/votes/bulk
Get vote counts for multiple maps in one request.

**Request Body:**
```json
{
    "map_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response (200):**
```json
{
    "votes": {
        "uuid1": {"map_id": "uuid1", "upvotes": 10, "downvotes": 1, "score": 9, "user_vote": null},
        "uuid2": {"map_id": "uuid2", "upvotes": 25, "downvotes": 2, "score": 23, "user_vote": "upvote"}
    }
}
```

---

## Admin

#### GET /api/admin/stats
Get system statistics (admin only).

#### GET /api/admin/users
List all users (admin only).

---

## Health

#### GET /health/live
Liveness probe.

#### GET /health/ready
Readiness probe (checks database connection).

---

## Error Responses

All errors follow this format:

```json
{
    "detail": "Error message here"
}
```

Common status codes:
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing or invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (e.g., email already exists)
- `429` - Rate Limited
- `500` - Internal Server Error

---

## Rate Limiting

API requests are rate-limited per user:
- Anonymous: 100 requests/minute
- Authenticated: 1000 requests/minute
- AI Jobs: Subject to quota limits

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1234567890
```
