# API Overview

BeatSight provides a REST API for programmatic access to our AI transcription service.

## Base URL

```
https://api.beatsight.app/v1
```

## Authentication

All API requests require authentication via Bearer token:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.beatsight.app/v1/songs
```

Get your API key from [Settings → API](https://beatsight.app/settings/api).

## Rate Limits

| Plan | Requests/min | Transcriptions/day |
|------|--------------|-------------------|
| Free | 60 | 3 |
| Pro | 300 | 50 |
| Team | 1000 | Unlimited |

## Response Format

All responses are JSON:

```json
{
  "data": { ... },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2025-01-01T00:00:00Z"
  }
}
```

## Error Handling

Errors follow RFC 7807 Problem Details:

```json
{
  "type": "https://api.beatsight.app/errors/validation",
  "title": "Validation Error",
  "status": 400,
  "detail": "File size exceeds limit",
  "instance": "/v1/songs"
}
```

## Common Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/songs` | GET | List your songs |
| `/songs` | POST | Upload a new song |
| `/songs/{id}` | GET | Get song details |
| `/jobs/{id}` | GET | Check transcription status |
| `/credits` | GET | Check credit balance |

## SDKs

Official SDKs coming soon:
- Python (`pip install beatsight`)
- JavaScript (`npm install @beatsight/sdk`)

## OpenAPI Spec

Full API specification available at:
- [openapi.json](https://api.beatsight.app/openapi.json)
- [Swagger UI](https://api.beatsight.app/docs)
