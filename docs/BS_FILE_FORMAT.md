# BeatSight Beatmap Format (.bs)

BeatSight uses a JSON-based beatmap format with the `.bs` file extension (also supports `.bsm` for backwards compatibility).

## File Structure

BeatSight beatmaps follow the osu! convention of organizing beatmaps in song folders:

```
~/BeatSight/Songs/
└── {Artist} - {Title} ({Creator})/
    ├── audio.mp3          # Audio file
    ├── background.jpg     # Background image (optional)
    └── {mapname}.bs       # Beatmap file
```

### Example Folder Structure

```
~/BeatSight/Songs/
└── Ahiru - HEARTBEAT (USAO Remix) (IntellectualBoy)/
    ├── audio.mp3
    ├── BG.jpg
    └── heart.bs
```

## .bs File Format (JSON)

The `.bs` file is a JSON document containing all beatmap data:

```json
{
  "Version": "1.0.0",
  "Metadata": {
    "Title": "HEARTBEAT (USAO Remix)",
    "Artist": "Ahiru",
    "Creator": "IntellectualBoy",
    "Source": "LOVEPOTION SIXTYNINE",
    "Tags": ["Sprite Recordings", "ALTER:ANSWERS"],
    "Difficulty": 8.5,
    "PreviewTime": 108169,
    "BeatmapId": "unique-guid",
    "CreatedAt": "2025-11-02T20:13:45Z",
    "ModifiedAt": "2025-11-02T20:45:22Z",
    "Description": "Epic drum map"
  },
  "Audio": {
    "Filename": "audio.mp3",
    "Hash": "sha256-hash-of-audio-file",
    "Duration": 316836,
    "SampleRate": 44100,
    "DrumStem": "drums.mp3",
    "DrumStemHash": "sha256-hash-of-drum-stem"
  },
  "Timing": {
    "Bpm": 180.0,
    "Offset": 170,
    "TimeSignature": "4/4",
    "TimingPoints": [
      {
        "Time": 170,
        "Bpm": 180.0,
        "TimeSignature": "4/4"
      }
    ]
  },
  "DrumKit": {
    "Components": ["Kick", "Snare", "HiHat", "Tom", "Ride", "Crash", "Splash"],
    "Layout": "Standard7",
    "CustomSamples": {
      "Kick": "samples/kick.wav",
      "Snare": "samples/snare.wav"
    }
  },
  "HitObjects": [
    {
      "Time": 2169,
      "Component": "Kick",
      "Velocity": 0.8,
      "Lane": 3,
      "Duration": null
    },
    {
      "Time": 2503,
      "Component": "Snare",
      "Velocity": 0.9,
      "Lane": 2,
      "Duration": null
    }
  ],
  "Editor": {
    "SnapDivisor": 4,
    "VisualLanes": 7,
    "TimelineZoom": 1.0,
    "Bookmarks": [2169, 10000, 50000],
    "AiGenerationMetadata": {
      "ModelVersion": "v1.2",
      "Confidence": 0.87,
      "ProcessedAt": "2025-11-02T20:13:45Z",
      "ManualEdits": false,
      "MetadataProvider": "YouTube",
      "MetadataConfidence": 0.95
    }
  }
}
```

## Field Descriptions

### Metadata
- **Title**: Song title
- **Artist**: Song artist
- **Creator**: Beatmap creator/mapper
- **Source**: Original source (e.g., game, album)
- **Tags**: List of search tags
- **Difficulty**: Difficulty rating (0-10)
- **PreviewTime**: Audio preview start time in milliseconds
- **BeatmapId**: Unique identifier (GUID)
- **CreatedAt**: Creation timestamp (ISO 8601)
- **ModifiedAt**: Last modification timestamp (ISO 8601)
- **Description**: Optional beatmap description

### Audio
- **Filename**: Relative path to audio file (usually "audio.mp3")
- **Hash**: SHA256 hash of audio file for integrity verification
- **Duration**: Total duration in milliseconds
- **SampleRate**: Audio sample rate (typically 44100 Hz)
- **DrumStem**: Optional path to isolated drum track
- **DrumStemHash**: SHA256 hash of drum stem file

### Timing
- **Bpm**: Base BPM (beats per minute)
- **Offset**: Initial timing offset in milliseconds
- **TimeSignature**: Time signature (e.g., "4/4")
- **TimingPoints**: Array of timing changes throughout the song

### DrumKit
- **Components**: List of drum components used (Kick, Snare, HiHat, Tom, Ride, Crash, Splash)
- **Layout**: Drum kit layout name (e.g., "Standard7")
- **CustomSamples**: Optional mapping of components to custom sample files

### HitObjects
Array of note/hit objects, each containing:
- **Time**: Time in milliseconds when the note should be hit
- **Component**: Drum component (Kick, Snare, HiHat, Tom, Ride, Crash, Splash)
- **Velocity**: Hit velocity/intensity (0.0-1.0)
- **Lane**: Visual lane number (0-6 for 7-lane layout)
- **Duration**: Hold duration in milliseconds (null for regular notes)

### Editor
Optional editor-specific metadata:
- **SnapDivisor**: Beat snap divisor (1, 2, 3, 4, 6, 8, 12, 16, etc.)
- **VisualLanes**: Number of visual lanes displayed
- **TimelineZoom**: Timeline zoom level (0.2-5.0)
- **Bookmarks**: Array of bookmarked timestamps
- **AiGenerationMetadata**: Metadata about AI-generated content

## Lane Mapping

The default 7-lane layout maps to drum components as follows:

| Lane | Position | Component | Description |
|------|----------|-----------|-------------|
| 0    | Far Left | Crash     | Crash cymbal |
| 1    | Left     | HiHat     | Hi-hat |
| 2    | Left-Center | Snare  | Snare drum |
| 3    | Center   | Kick      | Kick/bass drum |
| 4    | Right-Center | Tom    | Tom drum |
| 5    | Right    | Ride      | Ride cymbal |
| 6    | Far Right | Splash   | Splash/china cymbal |

## osu! File Support

BeatSight can also import osu! beatmap files (`.osu` format). When opening a `.osu` file:

1. The file is automatically detected by extension
2. Metadata (title, artist, creator, BPM, etc.) is extracted
3. Hit objects are converted to BeatSight format
4. Column positions are mapped to drum components
5. The beatmap can be saved as a `.bs` file

### osu! Column to Drum Component Mapping

For osu!mania maps, columns are mapped to drum components:

| osu! Column | BeatSight Lane | Component |
|-------------|----------------|-----------|
| 0           | 0              | Crash |
| 1           | 1              | HiHat |
| 2           | 2              | Snare |
| 3           | 3              | Kick |
| 4           | 4              | Tom |
| 5           | 5              | Ride |
| 6           | 6              | Splash |

## File Naming Conventions

### Beatmap Files
- Format: `{slug}.bs`
- Slug is derived from artist and title (lowercase, alphanumeric + hyphens)
- Example: `ahiru-heartbeat-usao-remix.bs`

### Song Folders
- Format: `{Artist} - {Title} ({Creator})/`
- Example: `Ahiru - HEARTBEAT (USAO Remix) (IntellectualBoy)/`

### Audio Files
- Primary audio: `audio.mp3` (or `audio.wav`, `audio.ogg`)
- Drum stem: `drums.mp3` (optional)
- Background: `BG.jpg` or `BG.png` (optional)

## Validation Rules

When saving a beatmap, the following validation is performed:

1. **Title** must not be empty
2. **Artist** must not be empty
3. **Audio.Filename** must be specified
4. **HitObjects** must contain at least one note
5. HitObjects are automatically sorted by time
6. File hash is computed and stored for audio integrity

## Migration from osu!

To convert an osu! beatmap to BeatSight format:

1. Open the `.osu` file in BeatSight Editor
2. The file is automatically parsed and converted
3. Review the generated drum mapping
4. Save the beatmap - it will be saved as `.bs` format

## Version History

- **1.0.0** (2025-11-02): Initial .bs format specification
  - JSON-based format
  - Support for 7-lane drum mapping
  - osu! file import capability
  - SHA256 file integrity verification

## See Also

- [BEATMAP_FORMAT.md](BEATMAP_FORMAT.md) - Detailed format specification
- [ARCHITECTURE.md](ARCHITECTURE.md) - Overall system architecture
- [osu! file format documentation](https://osu.ppy.sh/wiki/en/Client/File_formats/Osu_%28file_format%29)
