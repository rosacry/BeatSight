# BeatSight Quick Settings Reference

## 🎮 Gameplay Controls

### Standard Gameplay
- **S, D, F**: Left drums (Kick, Hi-hat Pedal, Snare)
- **Space**: Center (Hi-hat)
- **J, K, L**: Right drums (Toms, Crash/Ride/Cymbals)
- **R**: Retry current beatmap
- **Esc**: Return to menu

### Practice Mode (Additional)
- **[**: Set loop start point
- **]**: Set loop end point
- **C**: Clear loop points
- **M**: Toggle metronome on/off
- **All standard controls** also work

## ⚙️ Settings Overview

### Location
Settings are automatically saved to: `~/.local/share/BeatSight/beatsight.ini`

### Gameplay Settings
| Setting | Options | Default | Description |
|---------|---------|---------|-------------|
| **Gameplay Mode** | Auto / Manual | Auto | Auto: Full scoring. Manual: No scoring/results. |
| **Show Combo Milestones** | On / Off | On | Celebration animations every 50 combo |

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

### Gameplay Adjustments (In-Game)
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
- Loop status displayed in practice overlay

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

### First Time Playing
```
✅ All visual effects ON
✅ Gameplay Mode: Auto
✅ Speed: 0.75x (slightly slower)
✅ Combo Milestones: ON
```

### Serious Practice
```
⚠️ Approach Circles: ON (timing guidance)
⚠️ Particle Effects: OFF (less distraction)
⚠️ Glow Effects: OFF (cleaner visuals)
⚠️ Speed: 0.5x - 0.75x (learn patterns slowly)
⚠️ Use Practice Mode with looping!
```

### Performance/Recording
```
🎬 Gameplay Mode: Manual (no UI clutter)
🎬 All visual effects: OFF (clean gameplay)
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

### Perfecting Your Timing
1. Start with **Audio Offset** at 0ms
2. If you're consistently hitting early: **increase** offset (+20ms, +40ms)
3. If you're consistently hitting late: **decrease** offset (-20ms, -40ms)
4. Fine-tune in 5ms increments once you're close

### Learning a New Song
1. **Practice Mode** at 0.5x speed
2. Loop the **first 4-8 measures**
3. Once comfortable, increase to 0.75x
4. Loop the **next section**
5. Eventually practice at 1.0x
6. Finally, try **Auto Mode** for scoring

### Improving Accuracy
- Disable **Particle Effects** and **Glow Effects** for cleaner visuals
- Keep **Approach Circles** ON for timing guidance
- Use **Manual Mode** to focus on technique without score pressure
- Practice with **Metronome** to develop internal timing

### Maximizing Performance
- Run in **Release mode**: `dotnet build --configuration Release`
- Disable unused visual effects in Settings
- Close other applications to free up resources
- Ensure audio drivers are up to date

## 🆘 Troubleshooting

### "My hits aren't registering"
- Check **Audio Offset** in Settings → Input
- Verify your keyboard keys match the defaults (S/D/F/Space/J/K/L)
- Ensure no other application is capturing keyboard input

### "Notes are misaligned with audio"
- Adjust **Audio Offset** in Settings → Input
- Try adjusting **Offset Adjustment** in-game with Up/Down arrows
- Test at different playback speeds to isolate the issue

### "Visual effects are laggy"
- Disable **Particle Effects** and **Glow Effects**
- Build in Release mode for better performance
- Check system resources (CPU/GPU usage)

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
