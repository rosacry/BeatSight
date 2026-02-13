# Opus Session Prompt: Desktop App Integration with Trained ML Model

## Archive Metadata

- **Document Type:** Session prompt (archived)
- **Status:** Historical reference only
- **Normalized On:** 2026-02-13
- **Canonical Location:** `ai-pipeline/documentation/archive/prompts/session/`
- **Current Source of Truth:** `ai-pipeline/documentation/current/`

## 🎯 Session Context

A **world-class 12-class multi-label drum transcription model** has been trained and optimized:
- **Model:** CNN V5 Large (7.1M params)
- **Performance:** 0.91 Micro-F1, 0.75 Macro-F1, 0.805 Acoustic-F1
- **Location:** `ai-pipeline/runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt` (28MB)
- **Thresholds:** `ai-pipeline/runs/v5_multilabel_final_v3/thresholds.json`

**Your mission:** Integrate this model into the BeatSight desktop app, fixing bugs and ensuring robust local inference.

---

## 📊 Model Specifications

### 12 Classes
| Class | Description | Threshold |
|-------|-------------|-----------|
| kick | Bass drum | 0.40 |
| snare | Snare drum | 0.60 |
| cross_stick | Rim shot/cross-stick | 0.55 |
| hihat_closed | Closed hi-hat | 0.75 |
| hihat_open | Open hi-hat | 0.35 |
| hihat_pedal | Hi-hat foot | 0.35 |
| ride_bow | Ride cymbal body | 0.55 |
| ride_bell | Ride bell | 0.35 |
| tom | All toms (pitch-ranked → tom_1/2/3) | 0.30 |
| crash | Crash cymbals (pitch-ranked → crash_1/2) | 0.35 |
| china | China cymbal | 0.35 |
| splash | Splash cymbal | 0.65 |

### Architecture
- Input: Mel spectrogram (128 mel bins, 11 frames context)
- Backbone: 6-layer CNN with residual blocks
- Head: Multi-label sigmoid output (12 classes)
- Inference: ~2ms per onset on GPU, ~10ms on CPU

---

## 🔍 Current Integration Architecture

### Desktop App (C#/.NET 8, osu-framework)
```
desktop/
├── BeatSight.Game/
│   ├── AI/
│   │   ├── AiBeatmapGenerator.cs      # Main Python bridge
│   │   ├── BeatmapTimebaseSynchroniser.cs
│   │   └── Generation/
│   │       ├── GenerationCoordinator.cs  # Orchestrates pipeline
│   │       └── TempoOverride.cs
│   ├── Screens/
│   │   ├── Mapping/
│   │   │   └── MappingGenerationScreen.cs  # UI for generation
│   │   └── Playback/
│   │       └── PlaybackScreen.cs      # Has syntax errors!
```

### Python Pipeline
```
ai-pipeline/
├── pipeline/
│   └── process.py          # Main entry point (CLI)
├── transcription/
│   ├── drum_classifier.py  # Wraps ML model
│   ├── ml_drum_classifier_v2.py  # Actual inference
│   ├── instrument_pitch_ranker.py
│   └── onset_detector.py
├── runs/
│   └── v5_multilabel_final_v3/
│       ├── best_multilabel_model_ema.pt  # THE MODEL
│       └── thresholds.json               # Optimized thresholds
```

### Current Integration Flow
1. C# `AiBeatmapGenerator.GenerateAsync()` spawns Python process
2. Python `pipeline.process` does separation → detection → classification
3. JSON beatmap returned to C# via stdout/file

---

## 🐛 Known Issues to Fix

### Issue 1: UseMlClassifier Not Passed to Python (CRITICAL)

**Location:** `desktop/BeatSight.Game/AI/AiBeatmapGenerator.cs`

**Problem:** The `UseMlClassifier` option exists in `AiGenerationOptions` (line 42) but `buildArguments()` method (line 458) NEVER passes `--ml` or `--no-ml` to Python.

**Symptom:** Python always uses default ML behavior, ignoring user's preference.

**Fix:** Add to `buildArguments()`:
```csharp
if (options.UseMlClassifier)
    builder.Append(" --ml");
else
    builder.Append(" --no-ml");
```

### Issue 2: Model Path Not Configurable

**Problem:** C# has `LocalModelPath` in `GenerationParams` but it's never passed to Python CLI.

**Python CLI** accepts: `--ml-model <path>` and `--ml-device <device>`

**Fix:** Add to `buildArguments()`:
```csharp
if (!string.IsNullOrEmpty(options.MlModelPath))
    builder.Append($" --ml-model {quote(options.MlModelPath)}");
if (!string.IsNullOrEmpty(options.MlDevice))  
    builder.Append($" --ml-device {options.MlDevice}");
```

**Also need:** Add `MlModelPath` and `MlDevice` to `AiGenerationOptions` class.

### Issue 3: PlaybackScreen.cs Syntax Errors

**Location:** `desktop/BeatSight.Game/Screens/Playback/PlaybackScreen.cs`

**Problem:** Build log shows 100+ syntax errors starting at line 283. Appears to be a corrupted/truncated file or merge conflict.

**Action:** The file needs investigation and repair. Check git status, possibly restore from a known-good commit.

### Issue 4: Thresholds Not Used

**Problem:** `thresholds.json` was generated during post-training optimization but Python pipeline may not be loading it automatically.

**Verify:** Check `drum_classifier.py` and `ml_drum_classifier_v2.py` to ensure thresholds are loaded.

---

## 📋 Your Tasks (Priority Order)

### Task 1: Fix PlaybackScreen.cs Syntax Errors ⚡ URGENT

1. Check `git diff` for PlaybackScreen.cs
2. If corrupted, restore from last good commit: `git checkout HEAD -- <path>`
3. Verify build passes: `dotnet build` in desktop folder
4. Run tests: `dotnet test`

### Task 2: Wire Up ML Classifier Toggle ⚡ HIGH

1. In `AiBeatmapGenerator.cs` → `buildArguments()`:
   - Add `--ml` when `UseMlClassifier` is true
   - Add `--no-ml` when false

2. Verify Python side accepts these flags (already confirmed in process.py)

### Task 3: Add Model Path Configuration ⚡ HIGH

1. Add to `AiGenerationOptions`:
```csharp
public string? MlModelPath { get; set; }
public string? MlDevice { get; set; } = "cuda";  // or "cpu"
```

2. In `buildArguments()`, pass these to Python CLI

3. Update `GenerationCoordinator` to map `LocalModelPath` → `MlModelPath`

4. Default model path should be relative to ai-pipeline:
   ```
   runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt
   ```

### Task 4: Verify Threshold Loading 🔧 MEDIUM

1. Check `ai-pipeline/transcription/drum_classifier.py`:
   - Does it load `thresholds.json`?
   - Does it use per-class thresholds during inference?

2. If not, add threshold loading logic

### Task 5: Add UI Controls for ML Options 🎨 LOWER

In `MappingGenerationScreen.cs`, add:
- Toggle for "Use ML Classifier" (default: on)
- Optional: Device selector (CPU/CUDA)
- Optional: Custom model path (advanced users)

### Task 6: End-to-End Integration Test ✅ FINAL

1. Launch desktop app
2. Import a test audio file
3. Generate beatmap with ML classifier enabled
4. Verify:
   - Python receives `--ml` flag
   - Model loads from correct path
   - Thresholds are applied
   - Beatmap quality matches expected 0.91 F1 performance

---

## 📁 Files to Attach for This Session

Essential files the agent needs to read:

### Desktop App (C#)
- `desktop/BeatSight.Game/AI/AiBeatmapGenerator.cs`
- `desktop/BeatSight.Game/AI/Generation/GenerationCoordinator.cs`
- `desktop/BeatSight.Game/Screens/Playback/PlaybackScreen.cs`
- `desktop/BeatSight.Game/Screens/Mapping/MappingGenerationScreen.cs`

### Python Pipeline
- `ai-pipeline/pipeline/process.py`
- `ai-pipeline/transcription/drum_classifier.py`
- `ai-pipeline/transcription/ml_drum_classifier_v2.py`

### Reference
- `ai-pipeline/runs/v5_multilabel_final_v3/thresholds.json`
- `ai-pipeline/README.md` (updated with model info)
- `docs/ARCHITECTURE.md`

---

## 🔧 Development Commands

### Build Desktop App
```powershell
cd desktop
dotnet build BeatSight.Desktop
```

### Run Desktop App
```powershell
cd desktop/BeatSight.Desktop
dotnet run
```

### Test Python Pipeline (CLI)
```bash
cd ai-pipeline
python -m pipeline.process --input test.mp3 --output test.bsm --ml
```

### Run Desktop Tests
```powershell
cd desktop
dotnet test BeatSight.Tests
```

---

## ✅ Success Criteria

1. **Build passes:** `dotnet build` completes with 0 errors
2. **Tests pass:** All existing tests green
3. **ML toggle works:** `--ml` / `--no-ml` appears in Python process args
4. **Model loads:** Logs show "Loaded model from runs/v5_multilabel_final_v3/..."
5. **Thresholds applied:** Per-class thresholds from JSON are used
6. **Generation works:** Can generate beatmap from audio file in desktop app

---

## 📚 Additional Context

### Model Training History
- Phase 1: Single-label training → 0.85 F1
- Phase 2: Multi-label training → 0.90 F1  
- Phase 3: Final optimization → **0.91 F1** (current)

### Threshold Tuning Results
- Global threshold: 0.5 (default)
- Per-class optimization improved Micro-F1 from 0.9089 → 0.9150

### External Benchmark (ENST)
- Achieved 0.35 F1 (expected due to domain shift - ENST is dry acoustic)
- Model is optimized for mixed/electronic tracks (production target domain)
