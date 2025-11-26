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
