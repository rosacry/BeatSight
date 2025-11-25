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
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "song_id": "550e8400-e29b-41d4-a716-446655440000",
  "priority": "standard",
  "state": "queued",
  "error_message": null,
  "requested_by_id": "550e8400-e29b-41d4-a716-446655440000",
  "started_at": null,
  "finished_at": null,
  "created_at": "2025-11-24T12:00:00Z"
}
```

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
    "started_at": "2025-11-24T12:01:00Z",
    "finished_at": "2025-11-24T12:03:00Z",
    "created_at": "2025-11-24T12:00:00Z"
  }
]
```

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

### v1.0.0 (November 2025)
- Initial API release
- Authentication endpoints (register, login, refresh, me)
- Song CRUD operations
- AI job queue management
- Health check endpoint
