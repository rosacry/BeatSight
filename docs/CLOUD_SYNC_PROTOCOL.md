# BeatSight Cloud Sync Protocol

*Version: 1.0.0*  
*Status: Design Specification*  
*Last Updated: November 2025*

## Overview

The BeatSight Cloud Sync Protocol enables seamless synchronization of beatmaps between desktop clients and the cloud service. It supports:

- **Bidirectional sync**: Upload local maps, download cloud maps
- **Conflict resolution**: Handle concurrent edits gracefully  
- **Delta sync**: Transfer only changed portions to minimize bandwidth
- **Offline-first**: Full functionality without connectivity

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Desktop Client                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Local DB   │  │ Sync Engine │  │   Beatmap Library       │  │
│  │ (SQLite)    │◄─┤             ├──┤   (.bsm files)          │  │
│  └─────────────┘  └──────┬──────┘  └─────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────────┘
                           │ HTTPS/WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Cloud Service                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  PostgreSQL │◄─┤  Sync API   ├──┤   Blob Storage          │  │
│  │  (metadata) │  │  (FastAPI)  │  │   (map files)           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### Sync States

Each beatmap has a `SyncState` tracked locally:

| State | Description |
|-------|-------------|
| `Local` | Created locally, never synced |
| `Synced` | In sync with cloud |
| `Modified` | Local changes pending upload |
| `Conflict` | Both local and cloud modified |
| `CloudOnly` | Exists in cloud, not downloaded |
| `Deleted` | Marked for deletion on next sync |

### Version Vectors

Each beatmap version is identified by:

```json
{
  "beatmapId": "550e8400-e29b-41d4-a716-446655440000",
  "version": 5,
  "localVersion": 3,
  "cloudVersion": 5,
  "lastModified": "2025-11-24T12:00:00Z",
  "checksum": "sha256:abc123...",
  "userId": "user-uuid"
}
```

- `version`: Monotonic counter incremented on any change
- `localVersion`: Last local modification version
- `cloudVersion`: Last known cloud version
- `checksum`: SHA-256 of canonical JSON representation

---

## Sync Protocol

### Phase 1: Discovery

Client sends a sync manifest to discover differences:

```http
POST /api/v1/sync/manifest
Authorization: Bearer <token>
Content-Type: application/json

{
  "clientId": "desktop-abc123",
  "lastSyncTimestamp": "2025-11-24T10:00:00Z",
  "beatmaps": [
    {
      "beatmapId": "550e8400-e29b-41d4-a716-446655440000",
      "version": 5,
      "checksum": "sha256:abc123...",
      "syncState": "synced"
    },
    {
      "beatmapId": "660e8400-e29b-41d4-a716-446655440001",
      "version": 2,
      "checksum": "sha256:def456...",
      "syncState": "modified"
    }
  ]
}
```

Server responds with sync actions:

```json
{
  "serverTimestamp": "2025-11-24T12:00:00Z",
  "actions": [
    {
      "beatmapId": "550e8400-e29b-41d4-a716-446655440000",
      "action": "none",
      "reason": "checksums_match"
    },
    {
      "beatmapId": "660e8400-e29b-41d4-a716-446655440001",
      "action": "upload",
      "reason": "local_newer"
    },
    {
      "beatmapId": "770e8400-e29b-41d4-a716-446655440002",
      "action": "download",
      "reason": "cloud_only",
      "cloudVersion": 1,
      "cloudChecksum": "sha256:ghi789..."
    },
    {
      "beatmapId": "880e8400-e29b-41d4-a716-446655440003",
      "action": "conflict",
      "reason": "both_modified",
      "localVersion": 3,
      "cloudVersion": 4
    }
  ]
}
```

### Phase 2: Transfer

#### Upload (Local → Cloud)

```http
PUT /api/v1/sync/beatmaps/{beatmapId}
Authorization: Bearer <token>
Content-Type: application/json
X-Expected-Version: 4
X-Client-Checksum: sha256:abc123...

{
  "version": "1.0.0",
  "metadata": { ... },
  "timing": { ... },
  "hitObjects": [ ... ]
}
```

Response (success):
```json
{
  "beatmapId": "660e8400-e29b-41d4-a716-446655440001",
  "newVersion": 3,
  "cloudChecksum": "sha256:def456...",
  "storageUri": "https://storage.beatsight.io/maps/660e..."
}
```

Response (conflict):
```json
{
  "error": "version_conflict",
  "message": "Cloud version is 5, expected 4",
  "currentCloudVersion": 5,
  "currentCloudChecksum": "sha256:xyz..."
}
```

#### Download (Cloud → Local)

```http
GET /api/v1/sync/beatmaps/{beatmapId}?version=5
Authorization: Bearer <token>
Accept: application/json
```

Response includes full beatmap JSON with metadata headers:

```
X-Beatmap-Version: 5
X-Beatmap-Checksum: sha256:abc123...
X-Last-Modified: 2025-11-24T12:00:00Z
```

### Phase 3: Delta Sync (Optimization)

For large beatmaps, send only changed hit objects using JSON Patch:

```http
PATCH /api/v1/sync/beatmaps/{beatmapId}/delta
Authorization: Bearer <token>
Content-Type: application/json-patch+json
X-Base-Version: 4
X-Base-Checksum: sha256:oldchecksum...

[
  { "op": "replace", "path": "/hitObjects/42/time", "value": 15250 },
  { "op": "add", "path": "/hitObjects/-", "value": { "time": 16000, "component": "kick", "velocity": 0.9, "lane": 0 } },
  { "op": "remove", "path": "/hitObjects/100" }
]
```

Server applies patch, validates, and returns new checksum:

```json
{
  "beatmapId": "...",
  "newVersion": 5,
  "cloudChecksum": "sha256:newchecksum...",
  "patchApplied": true
}
```

---

## Conflict Resolution

### Automatic Resolution (Default)

When both local and cloud have changes:

1. **Last-Write-Wins (LWW)**: By default, most recent `lastModified` wins
2. **Merge**: For additive changes (new hit objects), merge both sets
3. **User Choice**: Prompt user when structural conflicts exist

### Manual Resolution

Client presents diff view:

```json
{
  "conflictId": "conflict-123",
  "localBeatmap": { ... },
  "cloudBeatmap": { ... },
  "differences": [
    {
      "path": "/hitObjects/42/time",
      "localValue": 15200,
      "cloudValue": 15250,
      "type": "value_change"
    },
    {
      "path": "/metadata/difficulty",
      "localValue": 8.5,
      "cloudValue": 9.0,
      "type": "value_change"
    }
  ]
}
```

User resolution submission:

```http
POST /api/v1/sync/conflicts/{conflictId}/resolve
Authorization: Bearer <token>
Content-Type: application/json

{
  "resolution": "use_local",  // or "use_cloud", "merge_custom"
  "customMerge": null  // or full beatmap JSON for "merge_custom"
}
```

---

## Offline Support

### Local Operation Queue

When offline, operations queue locally:

```json
{
  "queue": [
    {
      "id": "op-001",
      "type": "update",
      "beatmapId": "550e8400...",
      "timestamp": "2025-11-24T14:00:00Z",
      "payload": { ... }
    },
    {
      "id": "op-002", 
      "type": "delete",
      "beatmapId": "660e8400...",
      "timestamp": "2025-11-24T14:05:00Z"
    }
  ]
}
```

### Reconnection Flow

1. Client detects connectivity restored
2. Fetches current cloud manifest
3. Replays operation queue with conflict detection
4. Resolves any conflicts (auto or manual)
5. Clears queue on success

---

## Security

### Authentication

- All endpoints require valid JWT access token
- Tokens refreshed automatically before expiry
- Offline queue replay requires fresh authentication

### Authorization

| Action | Requirement |
|--------|-------------|
| Download verified map | Authenticated |
| Upload new map | Authenticated + quota available |
| Edit own map | Authenticated |
| Edit verified map | Authenticated + Fixer role (karma ≥ 100) |
| Delete own map | Authenticated |

### Data Integrity

- All uploads validated against schema
- Checksums verified on both upload and download
- Version vectors prevent phantom writes
- Audit log tracks all modifications

---

## Rate Limits

| Operation | Limit | Window |
|-----------|-------|--------|
| Manifest sync | 60 | 1 minute |
| Upload | 20 | 1 minute |
| Download | 100 | 1 minute |
| Delta patch | 30 | 1 minute |

Exceeded limits return `429 Too Many Requests` with `Retry-After` header.

---

## Client Implementation

### C# Interface (Desktop)

```csharp
public interface IBeatmapSyncService
{
    /// <summary>
    /// Perform full sync cycle with cloud.
    /// </summary>
    Task<SyncResult> SyncAsync(CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get current sync state for a beatmap.
    /// </summary>
    SyncState GetSyncState(Guid beatmapId);
    
    /// <summary>
    /// Queue local changes for sync.
    /// </summary>
    void MarkModified(Guid beatmapId);
    
    /// <summary>
    /// Download a specific beatmap from cloud.
    /// </summary>
    Task<Beatmap> DownloadAsync(Guid beatmapId, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Resolve a sync conflict.
    /// </summary>
    Task ResolveConflictAsync(Guid conflictId, ConflictResolution resolution);
    
    /// <summary>
    /// Event raised when sync status changes.
    /// </summary>
    event EventHandler<SyncStatusChangedEventArgs> SyncStatusChanged;
}

public enum SyncState
{
    Local,
    Synced,
    Modified,
    Conflict,
    CloudOnly,
    Deleted
}

public record SyncResult(
    int Downloaded,
    int Uploaded,
    int Conflicts,
    int Errors,
    TimeSpan Duration
);
```

### Local Database Schema (SQLite)

```sql
CREATE TABLE sync_metadata (
    beatmap_id TEXT PRIMARY KEY,
    local_version INTEGER NOT NULL,
    cloud_version INTEGER,
    local_checksum TEXT NOT NULL,
    cloud_checksum TEXT,
    sync_state TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    last_synced TEXT,
    conflict_data TEXT  -- JSON for unresolved conflicts
);

CREATE TABLE sync_operation_queue (
    id TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL,  -- 'upload', 'delete', 'patch'
    beatmap_id TEXT NOT NULL,
    payload TEXT,  -- JSON
    created_at TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT
);

CREATE INDEX idx_sync_state ON sync_metadata(sync_state);
CREATE INDEX idx_queue_created ON sync_operation_queue(created_at);
```

---

## Error Handling

### Error Codes

| Code | Description | Recovery |
|------|-------------|----------|
| `SYNC_001` | Network unavailable | Queue for retry |
| `SYNC_002` | Authentication expired | Refresh token |
| `SYNC_003` | Version conflict | Present conflict UI |
| `SYNC_004` | Checksum mismatch | Re-download |
| `SYNC_005` | Quota exceeded | Notify user |
| `SYNC_006` | Map not found | Remove local reference |
| `SYNC_007` | Permission denied | Check role/karma |
| `SYNC_008` | Rate limited | Exponential backoff |

### Retry Strategy

```
Attempt 1: Immediate
Attempt 2: 1 second delay
Attempt 3: 5 seconds delay
Attempt 4: 30 seconds delay
Attempt 5: 5 minutes delay
Max attempts: 5, then require manual retry
```

---

## Future Enhancements

1. **Real-time collaboration**: WebSocket-based live editing
2. **Branching**: Fork maps for experimentation
3. **Selective sync**: Sync only favorited maps
4. **Bandwidth optimization**: Binary diff format for hit objects
5. **P2P sync**: Direct client-to-client sync for LAN parties

---

## Changelog

### v1.0.0 (November 2025)
- Initial protocol specification
- Core sync operations (manifest, upload, download, delta)
- Conflict resolution framework
- Offline queue support
- Security and rate limiting
