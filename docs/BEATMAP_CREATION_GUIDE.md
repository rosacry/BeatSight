# Creating Beatmaps in BeatSight

A step-by-step guide for creating drum practice beatmaps with BeatSight.

## Overview

BeatSight can automatically generate drum beatmaps from any audio file using AI-powered drum transcription. This guide covers both automatic generation and manual editing.

---

## Quick Start (Automatic Generation)

### Step 1: Prepare Your Audio

BeatSight supports these audio formats:
- **MP3** (recommended for compatibility)
- **WAV** (best quality, larger file size)
- **OGG** (good compression)
- **FLAC** (lossless)
- **M4A/AAC**

**Tips for best results:**
- Use high-quality audio (320kbps MP3 or lossless)
- Songs with clear, isolated drums work best
- Avoid heavily compressed or low-bitrate files

### Step 2: Import and Generate

1. **Launch BeatSight** and go to the **Main Menu**
2. Click **"Generate New Map"** or drag an audio file onto the window
3. Select your audio file from the file picker
4. Wait for the AI to process (typically 1-3 minutes)

The AI will:
- Separate the drum track from the full mix
- Detect the tempo (BPM) and time signature
- Identify individual drum hits (kick, snare, hi-hat, etc.)
- Create a playable beatmap

### Step 3: Review and Play

Once generation completes:
1. The beatmap opens in the **Editor** for review
2. Press **Space** to preview playback
3. Click **"Play"** to practice the full map

---

## Understanding the Generation Process

### Stages

| Stage | Description | Duration |
|-------|-------------|----------|
| **Metadata** | Reads song title, artist from file tags | ~1 second |
| **Decoding** | Converts audio to processable format | ~5 seconds |
| **Separation** | Isolates drums from full mix using Demucs | 30-90 seconds |
| **Transcription** | AI analyzes drums and creates notes | 20-60 seconds |
| **Finalization** | Saves beatmap and opens editor | ~1 second |

### Confidence Scores

After generation, you'll see a confidence indicator:

- 🟢 **High (85%+)**: Map should be accurate, minimal editing needed
- 🟡 **Medium (70-84%)**: May need some adjustments
- 🔴 **Low (<70%)**: Complex drums or audio quality issues; expect to edit

**Common reasons for low confidence:**
- Very fast or complex drumming
- Poor audio quality or heavy compression
- Unusual drum sounds (electronic, synths)
- Multiple overlapping percussion elements

---

## Manual Editing

### Opening the Editor

From the Song Select screen:
1. Select your beatmap
2. Click the **"Edit"** button (pencil icon)

### Editor Controls

| Key | Action |
|-----|--------|
| **Space** | Play/Pause |
| **←/→** | Move forward/backward in time |
| **↑/↓** | Change snap divisor |
| **Scroll** | Zoom timeline in/out |
| **1-7** | Select note type (drum component) |
| **Click** | Place note at cursor position |
| **Right-click** | Delete note |
| **Ctrl+S** | Save beatmap |
| **Ctrl+Z** | Undo |
| **Ctrl+Y** | Redo |

### Note Types

BeatSight recognizes these drum components:

| Lane | Component | Color | Description |
|------|-----------|-------|-------------|
| 1 | **Kick** | Red | Bass drum |
| 2 | **Snare** | Blue | Snare drum (center and rim) |
| 3 | **Hi-Hat** | Yellow | Closed, open, and pedal |
| 4 | **Tom** | Green | Rack and floor toms |
| 5 | **Ride** | Cyan | Ride cymbal (bell and bow) |
| 6 | **Crash** | Pink | Crash cymbals |
| 7 | **Other** | White | Splash, china, auxiliary |

### Snap Divisor

The snap divisor controls note placement precision:

| Divisor | Grid | Best For |
|---------|------|----------|
| 1/1 | Whole notes | Very slow sections |
| 1/2 | Half notes | Slow songs |
| 1/4 | Quarter notes | Most common |
| 1/8 | Eighth notes | Fast patterns |
| 1/16 | Sixteenth notes | Rapid fills |
| 1/32 | 32nd notes | Complex patterns |

---

## Advanced: Manual Beatmap Creation

For complete control, you can create beatmaps from scratch.

### Step 1: Create a Song Folder

Create a folder in your BeatSight Songs directory:

```
~/BeatSight/Songs/Artist - Song Title (YourName)/
```

### Step 2: Add Your Audio

Copy your audio file to the folder and name it `audio.mp3` (or `audio.wav`, etc.).

Optional: Add a background image named `background.jpg` or `BG.jpg`.

### Step 3: Create in Editor

1. In BeatSight, go to **Song Select**
2. Click **"Create New"** or **"+"** button
3. Select your song folder
4. Set the BPM and offset manually
5. Start placing notes

### Setting BPM and Offset

**BPM (Beats Per Minute):**
- Use a tap tempo tool or online BPM counter
- Common ranges: 60-90 (slow), 90-140 (medium), 140-200 (fast)

**Offset:**
- The time in milliseconds where the first beat occurs
- Adjust until notes align with the music
- Use the waveform view to find the first drum hit

---

## Best Practices

### For Accurate Maps

1. **Start with AI generation** - Even if you plan to edit, AI gives a solid foundation
2. **Use headphones** - Essential for hearing subtle hits
3. **Work in sections** - Edit 30-60 seconds at a time
4. **Play-test frequently** - Catch timing issues early
5. **Compare with audio** - Use the waveform overlay to verify placement

### For Playable Maps

1. **Be consistent** - Same drum hits should always be in the same lane
2. **Consider difficulty** - Don't map every ghost note for beginners
3. **Leave breathing room** - Dense sections need occasional breaks
4. **Test at different speeds** - Use practice mode to verify patterns

### For Sharing

1. **Fill in metadata** - Title, artist, and your creator name
2. **Add a preview point** - Select an exciting section for the song select preview
3. **Write a description** - Note the difficulty and any special patterns
4. **Test thoroughly** - Play through the entire map before sharing

---

## Troubleshooting

### "BPM Detection seems wrong"

The AI detected half-time or double-time:
1. Open the Editor
2. Go to **Timing** panel
3. Click **"Double BPM"** or **"Halve BPM"**
4. Adjust offset if needed

### "Notes are slightly off-beat"

The offset needs adjustment:
1. Open the Editor
2. Go to **Timing** panel
3. Use the **"Adjust Offset"** slider
4. Fine-tune by ±1-5ms until notes land on beats

### "Missing drum hits"

The AI missed some notes:
1. Listen carefully to identify missing hits
2. Use the Editor to add notes manually
3. Check if the drum stem separation was clean

### "Too many notes / false positives"

The AI detected non-drum sounds:
1. Select and delete incorrect notes
2. Use the **"Clear Lane"** tool for bulk removal
3. Consider re-generating with different settings

### "Low confidence warning"

The AI is uncertain about the transcription:
1. Review the generated map in the Editor
2. Compare with the audio waveform
3. Make corrections as needed
4. This is common for complex or unconventional drums

---

## File Locations

| Platform | Songs Folder |
|----------|--------------|
| **Windows** | `%APPDATA%\BeatSight\Songs\` |
| **macOS** | `~/Library/Application Support/BeatSight/Songs/` |
| **Linux** | `~/.local/share/BeatSight/Songs/` |

Beatmap files use the `.bs` extension (JSON format). See [BS_FILE_FORMAT.md](./BS_FILE_FORMAT.md) for technical details.

---

## Next Steps

- **[Playback Guide](./PLAYBACK_GUIDE.md)** - Learn the playback controls and practice modes
- **[Keyboard Bindings](./SETTINGS_REFERENCE.md)** - Customize your lane keys
- **[Sharing Beatmaps](./SHARING.md)** - Upload to the community (coming soon)

---

*Last updated: November 2025*
