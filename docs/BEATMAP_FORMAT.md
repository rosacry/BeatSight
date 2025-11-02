# BeatSight Map Format (`.bsm`)

**Version**: 1.0.0  
**Status**: Draft Specification

## Overview

The `.bsm` (BeatSight Map) format is a JSON-based, human-readable file format for storing drum beatmaps. It is designed to be:

- **Version-controlled friendly**: Plain text, minimal diffs
- **Extensible**: Easy to add new properties without breaking compatibility
- **Platform-agnostic**: Works identically on desktop, mobile, and web
- **Human-readable**: Can be edited manually in a text editor
- **Compact**: Not compressed, but efficiently structured

## File Structure

### Basic Example

```json
{
  "version": "1.0.0",
  "metadata": {
    "title": "Through the Fire and Flames",
    "artist": "DragonForce",
    "creator": "username",
    "source": "Guitar Hero III",
    "tags": ["metal", "speed", "insane"],
    "difficulty": 9.2,
    "previewTime": 45000,
    "beatmapId": "550e8400-e29b-41d4-a716-446655440000",
    "createdAt": "2025-11-02T10:30:00Z",
    "modifiedAt": "2025-11-02T12:15:00Z"
  },
  "audio": {
    "filename": "audio.mp3",
    "hash": "sha256:abcdef1234567890...",
    "duration": 445320,
    "sampleRate": 44100,
    "drumStem": "drums.wav",
    "drumStemHash": "sha256:fedcba0987654321..."
  },
  "timing": {
    "bpm": 200.0,
    "offset": 0,
    "timeSignature": "4/4",
    "timingPoints": [
      {
        "time": 0,
        "bpm": 200.0,
        "timeSignature": "4/4"
      },
      {
        "time": 120000,
        "bpm": 210.0,
        "timeSignature": "4/4"
      }
    ]
  },
  "drumKit": {
    "components": [
      "kick",
      "snare",
      "hihat_closed",
      "hihat_open",
      "crash",
      "ride",
      "tom_high",
      "tom_mid",
      "tom_low"
    ],
    "layout": "standard_5piece"
  },
  "hitObjects": [
    {
      "time": 1000,
      "component": "kick",
      "velocity": 0.85,
      "lane": 0
    },
    {
      "time": 1500,
      "component": "snare",
      "velocity": 1.0,
      "lane": 2
    },
    {
      "time": 2000,
      "component": "hihat_closed",
      "velocity": 0.6,
      "lane": 4
    }
  ],
  "editor": {
    "snapDivisor": 4,
    "visualLanes": 7,
    "bookmarks": [5000, 45000, 120000],
    "aiGenerationMetadata": {
      "modelVersion": "beatsight-v1.2.0",
      "confidence": 0.92,
      "processedAt": "2025-11-02T10:30:00Z"
    }
  }
}
```

## Specification

### Root Object

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `version` | string | ✅ | Format version (semantic versioning) |
| `metadata` | object | ✅ | Song and beatmap metadata |
| `audio` | object | ✅ | Audio file information |
| `timing` | object | ✅ | BPM and timing configuration |
| `drumKit` | object | ✅ | Drum kit component definition |
| `hitObjects` | array | ✅ | All drum hits in the beatmap |
| `editor` | object | ❌ | Editor-specific settings and metadata |

---

### `metadata` Object

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `title` | string | ✅ | Song title |
| `artist` | string | ✅ | Song artist/band |
| `creator` | string | ✅ | Beatmap creator username |
| `source` | string | ❌ | Source (album, game, etc.) |
| `tags` | array[string] | ❌ | Search tags (genre, style, etc.) |
| `difficulty` | number | ✅ | Difficulty rating (0.0 - 10.0) |
| `previewTime` | integer | ❌ | Preview start time in milliseconds |
| `beatmapId` | string (UUID) | ✅ | Unique identifier |
| `createdAt` | string (ISO 8601) | ✅ | Creation timestamp |
| `modifiedAt` | string (ISO 8601) | ✅ | Last modification timestamp |
| `description` | string | ❌ | Optional description/notes |

**Difficulty Scale**:
- 0.0 - 1.9: Beginner
- 2.0 - 3.9: Easy
- 4.0 - 5.9: Normal
- 6.0 - 7.9: Hard
- 8.0 - 9.4: Expert
- 9.5 - 10.0: Extreme

---

### `audio` Object

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `filename` | string | ✅ | Main audio file (relative path) |
| `hash` | string | ✅ | SHA-256 hash (for integrity) |
| `duration` | integer | ✅ | Duration in milliseconds |
| `sampleRate` | integer | ✅ | Sample rate in Hz (typically 44100) |
| `drumStem` | string | ❌ | Isolated drum track filename |
| `drumStemHash` | string | ❌ | SHA-256 hash of drum stem |

**Note**: `drumStem` is optional but highly recommended for copyright compliance (transformative use).

---

### `timing` Object

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `bpm` | number | ✅ | Base BPM (beats per minute) |
| `offset` | integer | ✅ | Global timing offset in ms |
| `timeSignature` | string | ✅ | Default time signature (e.g., "4/4") |
| `timingPoints` | array | ❌ | BPM/timing changes during song |

#### `timingPoints` Array Items

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `time` | integer | ✅ | Time in milliseconds |
| `bpm` | number | ✅ | New BPM value |
| `timeSignature` | string | ❌ | New time signature |

---

### `drumKit` Object

Defines which drum components are present in the beatmap.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `components` | array[string] | ✅ | List of drum parts used |
| `layout` | string | ❌ | Preset kit layout identifier |
| `customSamples` | object | ❌ | Custom sample file mappings |

#### Standard Drum Components

| Component ID | Description |
|--------------|-------------|
| `kick` | Bass drum / Kick drum |
| `snare` | Snare drum |
| `hihat_closed` | Closed hi-hat |
| `hihat_open` | Open hi-hat |
| `hihat_pedal` | Hi-hat pedal (foot) |
| `crash` | Crash cymbal |
| `crash2` | Second crash cymbal |
| `ride` | Ride cymbal |
| `ride_bell` | Ride bell |
| `china` | China cymbal |
| `splash` | Splash cymbal |
| `tom_high` | High tom |
| `tom_mid` | Mid tom |
| `tom_low` | Low tom / Floor tom |
| `cowbell` | Cowbell |
| `tambourine` | Tambourine |

**Extensibility**: New components can be added with custom IDs (e.g., `"custom_gong"`).

---

### `hitObjects` Array

Array of drum hits, sorted by time (ascending).

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `time` | integer | ✅ | Hit time in milliseconds |
| `component` | string | ✅ | Drum component ID (from `drumKit.components`) |
| `velocity` | number | ❌ | Hit velocity (0.0 - 1.0, default 0.8) |
| `lane` | integer | ❌ | Visual lane/track number (for rendering) |
| `duration` | integer | ❌ | Sustain duration in ms (for cymbals/open hi-hat) |

**Velocity Scale**:
- 0.0 - 0.3: Ghost notes / Very soft
- 0.4 - 0.6: Soft
- 0.7 - 0.9: Normal
- 0.9 - 1.0: Accent / Loud

**Lane Assignment**: Lanes determine horizontal position in gameplay. Standard 7-lane layout:
- Lane 0: Kick
- Lane 1: Hi-hat (foot)
- Lane 2: Snare
- Lane 3: Hi-hat
- Lane 4: Tom (high)
- Lane 5: Tom (mid/low)
- Lane 6: Cymbals (crash/ride/china)

---

### `editor` Object (Optional)

Contains editor-specific data that doesn't affect gameplay.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `snapDivisor` | integer | ❌ | Note snap divisor (1, 2, 4, 8, 16, etc.) |
| `visualLanes` | integer | ❌ | Number of visual lanes |
| `bookmarks` | array[integer] | ❌ | Bookmarked times in ms |
| `aiGenerationMetadata` | object | ❌ | AI processing information |

#### `aiGenerationMetadata` Object

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `modelVersion` | string | ❌ | AI model version used |
| `confidence` | number | ❌ | Average confidence score (0.0 - 1.0) |
| `processedAt` | string | ❌ | Processing timestamp (ISO 8601) |
| `manualEdits` | boolean | ❌ | Whether map was manually edited after AI |

---

## Version Compatibility

### Forward Compatibility
Parsers MUST ignore unknown properties to support future extensions.

### Backward Compatibility
Breaking changes require a major version bump (e.g., 1.x.x → 2.0.0).

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-02 | Initial specification |

---

## File Naming Convention

**Recommended format**:
```
{artist} - {title} [{creator}].bsm
```

**Examples**:
- `DragonForce - Through the Fire and Flames [BeatSight AI].bsm`
- `Metallica - One [john_drummer].bsm`

**Associated files** (same directory):
- Audio: `{mapname}/audio.mp3`
- Drum stem: `{mapname}/drums.wav`
- Background: `{mapname}/bg.jpg` (optional)

---

## Parsing Guidelines

### JSON Schema Validation
A JSON schema file (`beatsight-map-schema.json`) is provided for validation.

### Error Handling
- **Missing required fields**: Reject the file
- **Invalid values**: Reject or use safe defaults (document behavior)
- **Unknown properties**: Ignore (forward compatibility)

### Performance
- Use streaming JSON parsers for large files
- Index `hitObjects` by time for fast lookup
- Cache parsed beatmaps in memory during gameplay

---

## Example: Minimal Valid Beatmap

```json
{
  "version": "1.0.0",
  "metadata": {
    "title": "Simple Beat",
    "artist": "Test Artist",
    "creator": "testuser",
    "difficulty": 3.0,
    "beatmapId": "550e8400-e29b-41d4-a716-446655440001",
    "createdAt": "2025-11-02T10:00:00Z",
    "modifiedAt": "2025-11-02T10:00:00Z"
  },
  "audio": {
    "filename": "audio.mp3",
    "hash": "sha256:abc123",
    "duration": 60000,
    "sampleRate": 44100
  },
  "timing": {
    "bpm": 120.0,
    "offset": 0,
    "timeSignature": "4/4"
  },
  "drumKit": {
    "components": ["kick", "snare", "hihat_closed"]
  },
  "hitObjects": [
    {"time": 0, "component": "kick", "lane": 0},
    {"time": 500, "component": "hihat_closed", "lane": 3},
    {"time": 1000, "component": "snare", "lane": 2}
  ]
}
```

---

## Tools and Libraries

### Validation
```bash
# Using JSON schema validator
ajv validate -s beatsight-map-schema.json -d beatmap.bsm
```

### Conversion
Future tools may support conversion to/from:
- MIDI files
- MusicXML
- osu! `.osu` format (for comparison)

---

## Community Standards

### Beatmap Quality Guidelines
1. **Timing**: Hits should align with actual drum sounds (±50ms tolerance)
2. **Playability**: Avoid impossible patterns (human physical limits)
3. **Consistency**: Similar sounds should map to same drum components
4. **Difficulty**: Rating should match actual complexity
5. **Metadata**: Accurate artist/title information

### Ranking Criteria (Future)
- Minimum 30 seconds duration
- No more than 10% unsnapped hits
- AI confidence >0.80 OR manually verified
- Peer review by 2+ community members

---

**See Also**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [API_REFERENCE.md](API_REFERENCE.md) - Backend API documentation
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
