# BeatSight Desktop Developer Guide

*Version: 1.0.0*  
*Last Updated: December 2025*

---

## Overview

The BeatSight Desktop client is a cross-platform drum transcription and follow-along learning tool built on the [osu-framework](https://github.com/ppy/osu-framework). It provides real-time audio processing, AI-powered beatmap generation, and visual practice features for drummers.

**Important:** BeatSight is NOT a game. There are no scores, combos, or gamification mechanics. The visual feedback during practice (hit timing indicators) is purely for learning purposes.

---

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Runtime | .NET | 8.0 |
| UI Framework | osu-framework | 2024.x |
| Audio | ManagedBass via osu-framework | - |
| Testing | xUnit | 2.4.x |
| Coverage | Coverlet | 6.0.x |

---

## Project Structure

```
desktop/
├── BeatSight.Desktop/          # Platform-specific entry points
│   ├── BeatSight.Desktop.csproj
│   └── Program.cs
│
├── BeatSight.Game/             # Main game logic
│   ├── AI/                     # AI generation integration
│   ├── Audio/                  # Audio playback and analysis
│   ├── Beatmaps/               # Beatmap data structures
│   ├── Collections/            # Song collection management
│   ├── Configuration/          # App settings and config
│   ├── Customization/          # Skin and theme system
│   ├── Localization/           # i18n support
│   ├── Mapping/                # Beatmap editor components
│   ├── Metadata/               # Song metadata handling
│   ├── Progress/               # User progress tracking
│   ├── Resources/              # Fonts, textures, shaders
│   ├── Screens/                # All UI screens
│   ├── Services/               # Background services
│   └── UI/                     # Reusable UI components
│
└── BeatSight.Tests/            # Unit and integration tests
```

---

## Screen Flow

```
                    ┌─────────────────┐
                    │   IntroScreen   │
                    │   (splash)      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
             ┌──────┤  MainMenuScreen │◄─────────────┐
             │      │                 │              │
             │      └────────┬────────┘              │
             │               │                       │
    ┌────────▼────┐   ┌──────▼──────┐   ┌───────────▼───────┐
    │ SongSelect  │   │  Settings   │   │  OutroScreen      │
    │  Screen     │   │   Screen    │   │  (exit confirm)   │
    └──────┬──────┘   └─────────────┘   └───────────────────┘
           │
    ┌──────▼──────┐
    │ Generation  │───────────┐
    │  Screens    │           │
    └─────────────┘           │
                              │
    ┌─────────────────────────▼───────────────────────────┐
    │                                                      │
    │  ┌───────────┐    ┌───────────┐    ┌───────────┐    │
    │  │  Editor   │◄──►│ Playback  │◄──►│ Recording │    │
    │  │  Screen   │    │  Screen   │    │  Screen   │    │
    │  └───────────┘    └───────────┘    └───────────┘    │
    │                                                      │
    └──────────────────────────────────────────────────────┘
```

### Key Screens

| Screen | File | Purpose |
|--------|------|---------|
| `IntroScreen` | `Screens/IntroScreen.cs` | Splash animation on startup |
| `MainMenuScreen` | `Screens/MainMenuScreen.cs` | Main navigation hub |
| `SongSelectScreen` | `Screens/SongSelect/SongSelectScreen.cs` | Browse and select songs |
| `EditorScreen` | `Screens/Editor/EditorScreen.cs` | Beatmap editing with timeline |
| `PlaybackScreen` | `Screens/Playback/PlaybackScreen.cs` | Practice mode with scrolling notes |
| `SettingsScreen` | `Screens/Settings/SettingsScreen.cs` | App configuration |

---

## Core Services

### Dependency Injection

BeatSight uses osu-framework's dependency injection system. Services are registered in `BeatSightGame.cs`:

```csharp
[BackgroundDependencyLoader]
private void load()
{
    // Register services
    dependencies.Cache(new AudioEngine());
    dependencies.Cache(new DecodeService());
    dependencies.CacheAs<IGenerationCoordinator>(generationCoordinator);
    // ...
}
```

### Key Services

| Service | Interface | Purpose |
|---------|-----------|---------|
| `AudioEngine` | - | Audio playback with ManagedBass |
| `GenerationPipeline` | `IGenerationPipeline` | Orchestrates AI beatmap generation |
| `GenerationCoordinator` | `IGenerationCoordinator` | Manages generation state and UI updates |
| `DecodeService` | - | FFmpeg-based audio decoding |
| `OnsetDetectionService` | - | Beat detection from audio |
| `MetadataDetectionService` | - | Song metadata extraction |
| `CloudSyncService` | `ICloudSyncService` | Sync with web backend |
| `UserProgressManager` | - | Track practice progress |
| `CollectionManager` | - | Manage song collections |

### Generation Pipeline

The beatmap generation flow:

```
Audio File → DecodeService → OnsetDetectionService → AiBeatmapGenerator → Beatmap
                ↓                     ↓                      ↓
           PCM Samples         Onset Events           Drum Pattern
```

Stages are tracked via `GenerationStage` enum:
- `None` → `Preparing` → `Decoding` → `Analyzing` → `Generating` → `Complete`

---

## Configuration System

Settings are managed through `BeatSightConfigManager`:

```csharp
// Access settings
[Resolved]
private BeatSightConfigManager config { get; set; }

var volume = config.GetBindable<double>(BeatSightSetting.MasterVolume);
volume.ValueChanged += e => Logger.Log($"Volume: {e.NewValue}");
```

### Key Settings

| Setting | Type | Description |
|---------|------|-------------|
| `MasterVolume` | `double` | Global audio volume (0.0-1.0) |
| `ScrollSpeed` | `double` | Playback scroll speed multiplier |
| `InputOffset` | `int` | Audio latency compensation (ms) |
| `AutoSaveInterval` | `int` | Editor auto-save frequency (seconds) |
| `SelectedSkinId` | `string` | Current visual skin |
| `UIScale` | `double` | UI scaling factor |

---

## Beatmap Format

Beatmaps are stored as JSON with the `.beatmap.json` extension:

```json
{
  "version": "1.1.0",
  "metadata": {
    "title": "Song Title",
    "artist": "Artist Name",
    "bpm": 120.0
  },
  "events": [
    {
      "time": 1000,
      "lane": "kick",
      "velocity": 0.8
    }
  ]
}
```

See `docs/BEATMAP_FORMAT.md` for the complete specification.

---

## UI Components

### Reusable Components

Located in `UI/Components/`:

| Component | Purpose |
|-----------|---------|
| `BeatSightButton` | Styled button with hover effects |
| `BeatSightSlider` | Audio-style slider control |
| `BeatSightSpriteText` | Themed text rendering |
| `SettingsItem<T>` | Settings row with label and control |
| `LoadingSpinner` | Animated loading indicator |

### Theming

Skins are loaded from `Customization/Skins/` and define:
- Color palettes
- Note shapes and sizes
- Lane configurations
- Timing indicator styles

---

## Testing

### Running Tests

```bash
# Run all tests
dotnet test desktop/BeatSight.Tests/

# Run with coverage
dotnet test desktop/BeatSight.Tests/ --collect:"XPlat Code Coverage"

# Run specific test class
dotnet test --filter "FullyQualifiedName~EditorScreenTests"
```

### Test Patterns

Tests use the osu-framework test infrastructure:

```csharp
public class EditorScreenTests : BeatSightTestScene
{
    private EditorScreen editor = null!;

    [SetUp]
    public void Setup()
    {
        Schedule(() =>
        {
            Clear();
            Add(editor = new EditorScreen());
        });
    }

    [Test]
    public void TestPlayPause()
    {
        AddStep("press play", () => InputManager.Key(Key.Space));
        AddAssert("is playing", () => editor.IsPlaying);
    }
}
```

---

## Debugging Tips

### Common Issues

#### 1. Audio Not Playing

Check:
- `AudioEngine` is properly resolved
- Audio device is available (`audioManager.AudioDevice`)
- File format is supported (MP3, WAV, OGG, FLAC, M4A)

```csharp
Logger.Log($"Audio device: {audioManager.AudioDevice}", LoggingTarget.Runtime);
```

#### 2. Screen Transitions Failing

Ensure:
- Previous screen allows exit (`CanExitScreen` returns true)
- New screen is properly constructed
- ScreenStack is not in transition

```csharp
if (screenStack.CanExit)
    screenStack.Push(new TargetScreen());
```

#### 3. Generation Pipeline Stuck

Check the `GenerationCoordinator` state:
- `CurrentStage` should progress through stages
- `IsGenerating` indicates active processing
- `LastError` contains failure details

```csharp
Logger.Log($"Generation stage: {coordinator.CurrentStage}, Error: {coordinator.LastError}");
```

#### 4. Memory Leaks

Common causes:
- Event handler subscriptions not cleaned up
- Disposable objects not disposed
- Background tasks not cancelled

Use `Dispose()` pattern:

```csharp
protected override void Dispose(bool isDisposing)
{
    volumeBindable.ValueChanged -= onVolumeChanged;
    cancellationSource?.Cancel();
    base.Dispose(isDisposing);
}
```

### Logging

Enable verbose logging:

```csharp
Logger.Level = LogLevel.Verbose;
Logger.Log("Debug message", LoggingTarget.Runtime, LogLevel.Debug);
```

Logs are written to:
- **Windows:** `%APPDATA%/BeatSight/logs/`
- **macOS:** `~/Library/Application Support/BeatSight/logs/`
- **Linux:** `~/.local/share/BeatSight/logs/`

---

## Build and Publish

### Debug Build

```bash
dotnet build BeatSight.sln --configuration Debug
```

### Release Build

```bash
dotnet build BeatSight.sln --configuration Release
```

### Self-Contained Publish

```bash
# Windows
dotnet publish desktop/BeatSight.Desktop -c Release -r win-x64 --self-contained

# macOS (Intel)
dotnet publish desktop/BeatSight.Desktop -c Release -r osx-x64 --self-contained

# macOS (Apple Silicon)
dotnet publish desktop/BeatSight.Desktop -c Release -r osx-arm64 --self-contained

# Linux
dotnet publish desktop/BeatSight.Desktop -c Release -r linux-x64 --self-contained
```

---

## Contributing

### Code Style

- Follow C# naming conventions (PascalCase for public, camelCase for private)
- Use `readonly` for fields that don't change after construction
- Prefer composition over inheritance
- Document public APIs with XML comments

### Pull Request Checklist

- [ ] Tests pass (`dotnet test`)
- [ ] No new warnings (`dotnet build -warnaserror`)
- [ ] Code coverage maintained or improved
- [ ] Documentation updated if API changed

---

## Resources

- [osu-framework Documentation](https://github.com/ppy/osu-framework/wiki)
- [osu-framework API Reference](https://ppy.github.io/osu-framework/)
- [BeatSight Beatmap Format](./BEATMAP_FORMAT.md)
- [BeatSight Architecture Overview](./ARCHITECTURE.md)
