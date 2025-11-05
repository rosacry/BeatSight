# Implementation Guide - Remaining Features

**Date**: November 2, 2025  
**Status**: Phase 1.2 (95% Complete) → Phase 1.3

## Quick Implementation Tasks

### 1. Volume Control Integration ⏱️ 30 minutes

**File**: `GameplayScreen.cs`

Add to `LoadComplete()`:
```csharp
// Bind volume settings to audio
var masterVolume = config.GetBindable<double>(BeatSightSetting.MasterVolume);
var musicVolume = config.GetBindable<double>(BeatSightSetting.MusicVolume);

masterVolume.BindValueChanged(e => audioManager.Volume.Value = e.NewValue, true);
musicVolume.BindValueChanged(e =>
{
    if (track != null)
        track.Volume.Value = e.NewValue;
}, true);
```

Also update `loadAudioTrack()`:
```csharp
if (track != null)
{
    var musicVolume = config.GetBindable<double>(BeatSightSetting.MusicVolume);
    track.Volume.Value = musicVolume.Value;
}
```

---

### 2. Connect Live Input to Scoring ⏱️ 1-2 hours

**Step 1**: Make playfield accessible in `GameplayScreen.cs`
```csharp
protected GameplayPlayfield? playfield; // Change from private
```

**Step 2**: Add hit registration API in GameplayPlayfield class:
```csharp
public void RegisterHit(int lane, double currentTime)
{
    if (lane < 0 || lane >= laneCount || inputBlocked)
        return;

    if (laneCooldowns[lane] > 0)
        return;

    var judgement = checkForHit(lane, currentTime);
    applyResult(lane, judgement);
    laneCooldowns[lane] = 50;
}
```

**Step 3**: Update `LiveInputModeScreen.cs` `simulateLaneHit()`:
```csharp
private void simulateLaneHit(int lane)
{
    Schedule(() =>
    {
        if (playfield != null)
        {
            double currentTime = getCurrentTime();
            playfield.RegisterHit(lane, currentTime);
        }
    });
}
```

---

### 3. Note Filtering by Difficulty ⏱️ 1 hour

**File**: `PracticeModeScreen.cs`

Add method:
```csharp
private void applyDifficultyFilter(double percentage)
{
    if (beatmap == null)
        return;

    // Keep notes based on percentage
    var totalNotes = beatmap.Notes.Count;
    var keepCount = (int)(totalNotes * percentage);
    
    // Keep evenly distributed notes
    var filteredNotes = beatmap.Notes
        .Where((note, index) => index < keepCount || (index % (int)(1.0 / percentage)) == 0)
        .ToList();

    // Reload beatmap with filtered notes
    var filtered = new Beatmap
    {
        Metadata = beatmap.Metadata,
        Timing = beatmap.Timing,
        Audio = beatmap.Audio,
        Notes = filteredNotes
    };

    playfield?.LoadBeatmap(filtered);
}
```

Update difficulty slider binding:
```csharp
difficulty.BindValueChanged(e =>
{
    difficultyText.Text = $"Difficulty: {e.NewValue * 100:0}%";
    applyDifficultyFilter(e.NewValue);
});
```

---

### 4. Editor Waveform (Simplified) ⏱️ 2 hours

**Create**: `BeatSight.Game/Graphics/WaveformGraph.cs`

```csharp
using osu.Framework.Graphics;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Containers;
using osuTK;
using System;

namespace BeatSight.Game.Graphics
{
    public partial class WaveformGraph : CompositeDrawable
    {
        public WaveformGraph()
        {
            RelativeSizeAxes = Axes.Both;
        }

        public void GenerateFromDuration(double durationMs, double bpm)
        {
            // Generate visual bars based on BPM
            var container = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal
            };

            int barCount = (int)(durationMs / (60000.0 / bpm)); // Beats
            
            for (int i = 0; i < barCount; i++)
            {
                float height = 0.3f + (float)(Math.Sin(i * 0.5) * 0.3);
                
                container.Add(new Box
                {
                    Width = 2,
                    RelativeSizeAxes = Axes.Y,
                    Height = height,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Colour = Color4.Gray
                });
            }

            InternalChild = container;
        }
    }
}
```

**Add to EditorScreen.cs**:
```csharp
private WaveformGraph waveform = null!;

// In createTimeline():
waveform = new WaveformGraph
{
    RelativeSizeAxes = Axes.Both,
    Alpha = 0.4f
},

// After loading beatmap:
if (beatmap != null)
{
    waveform.GenerateFromDuration(track?.Length ?? 180000, beatmap.Timing.Bpm);
}
```

---

### 5. Background Blur (Using osu-framework) ⏱️ 1 hour

**File**: `GameplayScreen.cs`

Replace background Box with BufferedContainer:
```csharp
private BufferedContainer backgroundContainer = null!;

// In load():
InternalChildren = new Drawable[]
{
    backgroundContainer = new BufferedContainer
    {
        RelativeSizeAxes = Axes.Both,
        Child = new Box
        {
            RelativeSizeAxes = Axes.Both,
            Colour = new Color4(10, 10, 18, 255)
        }
    },
    backgroundDim = new Box { ... },
    // ... rest
};

// In LoadComplete():
var blurBindable = config.GetBindable<double>(BeatSightSetting.BackgroundBlur);
blurBindable.BindValueChanged(e =>
{
    backgroundContainer.BlurSigma = new Vector2((float)(e.NewValue * 10f));
}, true);
```

---

## Testing Commands

After each implementation:
```bash
# Build
cd ~/github/BeatSight
dotnet build

# Run in debug
cd desktop/BeatSight.Desktop
dotnet run

# Check for errors
dotnet build 2>&1 | grep -i error
```

---

## Priority Order

1. **Volume Control** (30 min) - Quick win, immediate impact
2. **Note Filtering** (1 hour) - Completes practice mode feature
3. **Live Input Scoring** (1-2 hours) - Enables full microphone gameplay
4. **Background Blur** (1 hour) - Visual polish
5. **Waveform** (2 hours) - Editor improvement

**Total Time**: 5.5-6.5 hours to 100% Phase 1.2+1.3

---

## Current Status Summary

✅ **Completed** (95%):
- Configuration system (23 settings)
- Settings UI (5 sections)
- Practice mode (looping, metronome)
- Live input mode (capture, detection)
- FPS counter
- Background dim
- Visual effects (5 toggleable)
- Speed control (0.25x-2.0x)

🚧 **Remaining** (5%):
- Volume integration
- Live input scoring
- Note filtering
- Waveform display
- Background blur

---

## Build Status
✅ 0 Warnings, 0 Errors  
✅ Release build successful  
✅ All dependencies resolved
