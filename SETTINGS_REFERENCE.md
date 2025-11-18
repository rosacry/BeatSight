# BeatSight Quick Settings Reference

## 🧭 Session Controls

These shortcuts focus on playback, looping, and view management. No score or hit input is recorded—the controls simply steer the visual rehearsal experience.

### Global Shortcuts
- **Space**: Play / pause the current map
- **Esc**: Return to the previous screen
- **[** / **]**: Set loop start and loop end markers at the current timeline position
- **C**: Clear loop markers and resume continuous playback
- **M**: Toggle the metronome overlay
- **Arrow Up / Down**: Increment or decrement the playback speed slider
- **Arrow Left / Right**: Nudge the offset slider (useful when aligning stems to the rendered lanes)
- **Ctrl + Scroll**: Zoom the timeline while the pointer rests over it

### View Toggles (PlaybackScreen)
- **V**: Cycle through view modes (2D lanes, 3D highway, manuscript preview)
- **Shift + V**: Reverse-cycle the view modes
- **K**: Toggle kick-line emphasis when practising double bass patterns

### Editor Preview
- **Space**: Play / pause PlaybackPreview within the editor
- **Shift + Space**: Restart preview from the loop start marker
- **F**: Focus the preview panel
- **Tab**: Jump between timeline, inspector, and preview focus areas

## ⚙️ Settings Overview

### Location
Settings are automatically saved to: `~/.local/share/BeatSight/beatsight.ini`

All BeatSight settings are now bound to this file up front, so every option is present even before you tweak it and any change made in-game (or by editing the file) stays in sync automatically.

### Playback Settings
| Setting | Options | Default | Description |
|---------|---------|---------|-------------|
| **Playback Flow Mode** | Guided / Manual | Guided | Guided keeps all instructional overlays (lane highlights, cue banners). Manual hides guidance layers for screen recordings or when stepping through a transcription frame-by-frame. |
| **Show Section Milestones** | On / Off | On | Displays subtle markers every 50 measures to help track long-form practice sessions. |

### Visual Effects
| Setting | Options | Default | Description |
|---------|---------|---------|-------------|
| **Approach Circles** | On / Off | On | Scaling circles that guide timing |
| **Particle Effects** | On / Off | On | Burst animations on hits |
| **Glow Effects** | On / Off | On | Additive blending glow on notes |
| **Hit Burst Animations** | On / Off | On | Explosion effects on Perfect/Great |

### Audio Settings
| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| **Master Volume** | 0% - 100% | 100% | Overall volume control |
| **Music Volume** | 0% - 100% | 80% | Music track volume |
| **Effect Volume** | 0% - 100% | 60% | Hit sound effects volume |

### Input Settings
| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| **Audio Offset** | -120ms to +120ms | 0ms | Global timing adjustment |

### Playback Adjustments (In-Session)
| Control | Range | Default | Description |
|---------|-------|---------|-------------|
| **Speed Adjustment** | 0.25x - 2.0x | 1.0x | Playback speed (pitch-preserving) |
| **Offset Adjustment** | -120ms to +120ms | 0ms | Per-session timing tweak |

## 🎓 Practice Mode Features

### Section Looping
1. Play the beatmap and find the section you want to practice
2. Press **[** at the start of the section
3. Press **]** at the end of the section
4. The section will now loop automatically
5. Press **C** to clear and return to normal playback

**Visual Feedback:**
- Green text when loop is active
- Shows loop start → end time and duration
- Loop status displayed in the practice overlay and on the transport timeline

### Metronome
- **Toggle:** Press **M** to enable/disable
- **Visual:** Golden flash on beat indicator (top-right)
- **Sync:** Automatically matches beatmap BPM
- **Persistent:** Stays on/off until toggled

### Difficulty Adjustment
- **Slider:** In practice overlay panel (top-center)
- **Range:** 25% - 100%
- **Current:** Display shows current difficulty percentage
- **Future:** Will filter note density based on percentage

## 🎯 Recommended Settings by Use Case

### First Time Studying a Song
```
✅ All visual effects ON
✅ Playback Flow: Guided
✅ Speed: 0.75x (slightly slower)
✅ Section Milestones: ON
```

### Deep Practice Blocks
```
⚠️ Approach Circles: ON (timing guidance)
⚠️ Particle Effects: OFF (less distraction)
⚠️ Glow Effects: OFF (cleaner visuals)
⚠️ Speed: 0.5x - 0.75x (learn patterns slowly)
⚠️ Use loop markers aggressively
```

### Capture / Presentation
```
🎬 Playback Flow: Manual (no guidance overlays)
🎬 All visual effects: OFF (clean capture)
🎬 Speed: 1.0x (normal speed)
🎬 Offset: Adjust for recording latency
```

### Low-End Hardware
```
💻 Particle Effects: OFF
💻 Glow Effects: OFF
💻 Hit Burst Animations: OFF
💻 Approach Circles: ON (minimal impact)
💻 Speed: 1.0x (avoid processing overhead)
```

## 📝 Tips & Tricks

### Aligning Audio & Visuals
1. Start with **Audio Offset** at 0ms
2. If cymbals visually lead the music, **increase** offset (+20ms, +40ms)
3. If the audio feels late compared to the lane visuals, **decrease** offset (-20ms, -40ms)
4. Fine-tune in 5ms increments once you're close

### Learning a New Song
1. **Practice Mode** at 0.5x speed
2. Loop the **first 4-8 measures**
3. Once comfortable, increase to 0.75x
4. Loop the **next section**
5. Eventually practice at 1.0x
6. Switch to the manuscript or 3D view to test memorisation

### Improving Focus
- Disable **Particle Effects** and **Glow Effects** for cleaner visuals
- Keep **Approach Circles** ON for timing guidance
- Use **Manual Flow** to hide overlays when you want a distraction-free lane
- Practice with **Metronome** to develop internal timing

### Maximizing Performance
- Run in **Release mode**: `dotnet build --configuration Release`
- Disable unused visual effects in Settings
- Close other applications to free up resources
- Ensure audio drivers are up to date

## 🆘 Troubleshooting

### "Playback feels out of sync"
- Adjust **Audio Offset** in Settings → Input
- Nudge the **Offset Adjustment** slider in-session
- Confirm you loaded the correct drum stem (full mix vs drums-only can highlight transient differences)

### "Loop markers won't clear"
- Press **C** or click the inline "Clear" button near the transport bar
- Ensure neither loop point is locked in the editor (timeline context menu → unlock)

### "Visual effects are laggy"
- Disable **Particle Effects** and **Glow Effects**
- Build in Release mode for better performance
- Check system resources (CPU/GPU usage)

### "Metronome is missing"
- Confirm **Metronome Enabled** is ON in Settings → Audio
- Ensure a metronome sound set is installed under `UserData/MetronomeSounds`
- Press **M** once to re-sync the overlay; it will flash gold on the next beat

### "Settings aren't saving"
- Check file permissions on `~/.local/share/BeatSight/`
- Verify `beatsight.ini` exists and is writable
- Try manually creating the directory: `mkdir -p ~/.local/share/BeatSight`

## 🔄 Resetting to Defaults

### Manual Reset
Delete the config file:
```fish
rm ~/.local/share/BeatSight/beatsight.ini
```

### In-App Reset (Future Feature)
A "Reset to Defaults" button will be added in Settings → General

## 📚 Additional Resources

- **Full Documentation**: `/home/chrig/github/BeatSight/docs/`
- **Session Summary**: `/home/chrig/github/BeatSight/SESSION_SUMMARY_2025_11_02_PART2.md`
- **Architecture Guide**: `/home/chrig/github/BeatSight/docs/ARCHITECTURE.md`
- **Beatmap Format**: `/home/chrig/github/BeatSight/docs/BEATMAP_FORMAT.md`

---

**Last Updated:** November 2, 2025  
**Version:** 1.2 (Phase 1.2 - 90% Complete)  
**Build Status:** ✅ 0 Warnings, 0 Errors
