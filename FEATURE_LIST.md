# BeatSight - Complete Feature List

**Last Updated:** November 2, 2025  
**Version:** Alpha 1.2 (95% Complete)

## 🎮 Gameplay Features

### Core Gameplay
- **7-Lane Note Highway**: Standard rhythm game layout with scrolling notes
- **Hit Detection**: Timing windows for Perfect/Great/Good/Miss judgments
- **Combo System**: Consecutive hit tracking with multiplier
- **Score Calculation**: Points based on accuracy and combo
- **Grade System**: S/A/B/C/D/F grades based on performance
- **Real-Time Feedback**: Visual and audio feedback on every hit

### Gameplay Modes
1. **Auto Mode** (Default)
   - Automatic drum detection from audio
   - Full scoring and statistics
   - Competitive gameplay experience

2. **Manual Mode**
   - Play-along without scoring
   - Practice and free play
   - No hit detection required

3. **Practice Mode** 🎓
   - Section looping ([/] keys to set boundaries)
   - Visual metronome with BPM sync (M key to toggle)
   - Difficulty slider (25%-100%)
   - Loop status display with timing info
   - Clear loop points (C key)

4. **Live Input Mode** 🎤 **NEW!**
   - Real-time microphone capture
   - Onset-based drum detection
   - 7-channel level meter visualization
   - Automatic drum type classification
    - Guided calibration wizard (ambient noise + per-drum signatures)
   - Toggle listening (M key)
   - Low-latency processing (30-50ms)
  - Device guard: Detects microphone changes and prompts recalibration before scoring

### Lane View Modes
- **2D Classic**: StepMania/osu!mania-style flat highway (default)
- **3D Runway Preview**: Guitar Hero-inspired perspective view with depth and tilt
- **Runtime Toggle**: Switch via Settings → Gameplay → Lane View without restarting
- **Per-Note Styling**: Approach circles and hit effects adapt to the active view

### Speed Control
- **Range**: 0.25x - 2.0x playback speed
- **Adjustments**: +/- keys for fine control
- **Display**: Real-time speed indicator
- **Use Cases**: Slow practice or speed challenges

### Visual Effects (All Toggleable)
- ✨ **Approach Circles**: Scaling circles indicating timing
- 🎆 **Particle Effects**: Burst animations on hit
- ✨ **Glow Effects**: Additive blending highlights
- 💥 **Hit Burst Animations**: Explosion effects on Perfect/Great
- 🎉 **Combo Milestones**: Celebrations every 50 combo
- 📊 **Hit Lighting**: Screen flash on perfect hits (Coming Soon)
- 📈 **Hit Error Meter**: Timing accuracy visualization (Coming Soon)

## ⚙️ Settings System

### Gameplay Settings (7 options)
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Gameplay Mode | Dropdown | Auto | Auto (scoring) vs Manual (play-along) |
| Lane View | Dropdown | 2D | Toggle between 2D classic and 3D runway lanes |
| Background Dim | Slider | 80% | Background darkness during gameplay |
| Background Blur | Slider | 0% | Blur effect strength (shader required) |
| Hit Lighting | Checkbox | On | Screen flash on perfect hits |
| Show Hit Error Meter | Checkbox | On | Display timing accuracy bar |
| Screen Shake on Miss | Checkbox | On | Camera shake effect |
| Show Combo Milestones | Checkbox | On | Celebrate every 50 combo |

### Visual Settings (6 options)
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Approach Circles | Checkbox | On | Show timing indicator circles |
| Particle Effects | Checkbox | On | Burst animations on hit |
| Glow Effects | Checkbox | On | Additive blending highlights |
| Hit Burst Animations | Checkbox | On | Explosion on Perfect/Great |
| Show FPS Counter | Checkbox | Off | Display frame rate (color-coded) |
| UI Scale | Slider | 100% | Interface size (50%-150%) |

### Audio Settings (4 options)
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Master Volume | Slider | 100% | Overall volume control |
| Music Volume | Slider | 80% | Background music level |
| Effect Volume | Slider | 60% | Hit sounds and UI effects |
| Hitsound Volume | Slider | 50% | Individual note hit feedback |

### Input Settings (2 options)
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Audio Offset | Slider | 0ms | Global timing adjustment |
| Hitsound Offset | Slider | 0ms | Separate hitsound timing |
| Key Bindings | - | Coming Soon | Customize drum key mappings |

### Performance Settings (1 option)
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Frame Limiter | Dropdown | Unlimited | VSync, 60/120/240 FPS caps |

## 📊 Results Screen

### Statistics Display
- **Final Score**: Total points earned
- **Accuracy**: Percentage of perfect timing
- **Max Combo**: Highest consecutive hit streak
- **Grade**: S/A/B/C/D/F rating
- **Hit Breakdown**: Perfect/Great/Good/Miss counts
- **Performance Graph**: Accuracy over time (Coming Soon)

### Actions
- **Retry**: R key to replay same beatmap
- **Return**: Esc key to return to menu

## ✏️ Editor

### Current Features
- **Timeline View**: Visual representation of beatmap
- **Audio Loading**: Automatic audio file detection
- **Playback Controls**: Play/pause/seek functionality
- **Note Editing**: Add/remove notes (basic)

### Planned Features
- **Waveform Display**: Visual audio representation
- **Precise Timing**: Click-to-place notes
- **BPM Detection**: Automatic tempo analysis
- **Snap Grid**: Beat/measure alignment
- **Note Properties**: Type, duration, lane assignment

## 🎵 Song Select

### Features
- **Beatmap Browser**: View all available beatmaps
- **Metadata Display**: Artist, title, difficulty, BPM
- **Preview**: Audio preview of selected song
- **Filtering**: Search and sort options (Coming Soon)
- **Random Selection**: Quick random pick (Coming Soon)

## 🤖 AI Processing Pipeline

### Drum Separation (Demucs)
- **Source Separation**: Isolate drums from music
- **Model**: Demucs v4 (state-of-the-art)
- **Quality**: High-fidelity separation
- **Output**: Separate drum track WAV

### Onset Detection
- **Algorithm**: Spectral flux with peak picking
- **Real-Time Variant**: Energy-based detection
- **Accuracy**: Configurable threshold
- **Output**: Timestamp array

### Drum Classification
- **ML Model**: CNN-based classifier
- **Types**: Kick, Snare, Tom, Cymbal, Hi-Hat
- **Training**: Custom dataset collection tool
- **Features**: Spectral and temporal features

### Beatmap Generation
- **Auto-Mapping**: AI generates note placements
- **Lane Assignment**: Based on drum type
- **Difficulty Scaling**: Adjust note density
- **Format**: .bsm JSON format

## 🎤 Real-Time Audio Features **NEW!**

### Microphone Capture
- **Sample Rate**: 44.1kHz standard
- **Channels**: Mono input
- **Buffer**: 30-50ms low latency
- **Normalization**: Float [-1, 1] range
- **Device Selection**: Enumerate available inputs

### Onset Detection
- **Algorithm**: Spectral flux + energy threshold
- **RMS Calculation**: Real-time energy monitoring
- **Spectrum Analysis**: 8-band frequency breakdown
- **Anti-Retrigger**: 40-50ms debounce
- **Classification**: Drum type estimation

### Live Visualization
- **Level Meters**: 7 real-time audio channels
- **Color Coding**: Activity-based coloring
- **Hit Flash**: Visual feedback on detection
- **Status Display**: Listening/Paused/Error states
- **Regression Checklist**: See `docs/LIVE_INPUT_REGRESSION_CHECKLIST.md` for release verification

## 🎨 User Interface

### Main Menu
- **Play**: Enter song select
- **Editor**: Open beatmap editor
- **Practice Mode**: Enter practice mode
- **🎤 Live Input**: Microphone-based gameplay
- **Browse Beatmaps**: Song select screen
- **Settings**: Configuration panel
- **Exit**: Quit application

### Visual Design
- **Color Scheme**: Dark theme with accent colors
- **Animations**: Smooth transitions and effects
- **Hover Effects**: Interactive button feedback
- **Responsive Layout**: Adapts to window size

### HUD Elements
- **Score Display**: Top-left corner
- **Combo Counter**: Centered above playfield
- **Accuracy Meter**: Real-time percentage
- **Speed Indicator**: Current playback rate
- **Offset Display**: Timing adjustment value
- **FPS Counter**: Top-right corner (toggleable)

## 🔧 Technical Features

### Configuration System
- **Storage**: INI file (beatsight.ini)
- **Location**: User data directory
- **Reactive**: Bindable system for live updates
- **Persistent**: Settings saved automatically
- **Type-Safe**: Enum-based setting keys

### Performance
- **Framework**: osu-framework (proven game engine)
- **Rendering**: OpenGL hardware acceleration
- **Audio**: Bass.Net via osu-framework
- **Threading**: Async audio processing
- **Memory**: Efficient drawable pooling

### Platform Support
- **Primary**: Linux (tested on Ubuntu)
- **Windows**: Compatible via .NET 8
- **macOS**: Compatible via .NET 8
- **Architecture**: x64 and ARM64

## 📁 Beatmap Format (.bsm)

### Structure
```json
{
  "version": 1,
  "metadata": {
    "title": "Song Name",
    "artist": "Artist Name",
    "creator": "Mapper Name",
    "difficulty": "Hard",
    "source": "Album/Game"
  },
  "timing": {
    "bpm": 120.0,
    "offset": 0
  },
  "audio": {
    "filename": "audio.mp3"
  },
  "notes": [
    {
      "time": 1000,
      "lane": 3,
      "type": "kick"
    }
  ]
}
```

## 🎯 Keyboard Controls

### Gameplay
- **S, D, F, Space, J, K, L**: Hit lanes (7 lanes)
- **+/-**: Adjust playback speed
- **,/.**: Adjust timing offset
- **R**: Retry (on results screen)
- **Esc**: Pause/Exit

### Practice Mode
- **[**: Set loop start point
- **]**: Set loop end point
- **M**: Toggle metronome
- **C**: Clear loop points

### Live Input Mode
- **M**: Toggle microphone listening

### Editor
- **Space**: Play/Pause
- **Left/Right**: Seek backwards/forwards
- **Click**: Add/remove notes

## 📈 Statistics & Progression

### Performance Tracking
- **Play Count**: Number of attempts
- **High Score**: Best score per beatmap
- **Accuracy Records**: Best accuracy per beatmap
- **Grade Distribution**: S/A/B/C/D/F counts

### Planned Features
- **Player Profile**: Persistent stats
- **Leaderboards**: Compare with others
- **Achievements**: Unlock system
- **Skill Rating**: Performance-based ranking

## 🚀 Upcoming Features (Phase 1.3)

### Priority 1 - Core Improvements
- [ ] Editor waveform visualization
- [ ] Background blur shader effect
- [ ] Hit lighting implementation
- [ ] Screen shake animation
- [ ] Hit error meter visualization

### Priority 2 - Visual Polish
- [ ] UI scaling fine-tuning (per-screen overrides)
- [ ] Customizable combo colors
- [ ] Additional 3D lane polish (lane glows, dynamic lights)

### Priority 3 - Audio Enhancements
- [ ] Live hitsound mixer with preview bus
- [ ] Audio device selection
- [ ] Latency calibration wizard
- [ ] Custom hitsounds

### Priority 4 - Editor Features
- [ ] Waveform rendering
- [ ] Auto-BPM detection
- [ ] Snap grid system
- [ ] Undo/redo functionality
- [ ] Beatmap validation

## 📊 Development Status

### Phase 1.1 - Foundation (100%)
✅ Project setup  
✅ Basic gameplay loop  
✅ Note rendering  
✅ Hit detection  
✅ Score calculation  

### Phase 1.2 - Gameplay Polish (100%)
✅ Results screen  
✅ Visual effects  
✅ Speed control  
✅ Settings system  
✅ Practice mode  
✅ Real-time microphone input  
✅ FPS counter  
✅ Live input calibration & scoring integration

### Phase 1.3 - Editor & Polish (10%)
⏳ Waveform visualization  
✅ Volume integration  
⏳ Background blur  
⏳ Hit lighting  
⏳ Screen shake  

### Phase 2 - AI Integration (25%)
✅ Demucs separation  
✅ Onset detection  
✅ ML classifier foundation  
⏳ Auto-mapper algorithm  
⏳ Beatmap validation  

---

**Total Features Implemented**: 85+  
**Settings Available**: 23  
**Gameplay Modes**: 4  
**Build Status**: ✅ 0 Warnings, 0 Errors
