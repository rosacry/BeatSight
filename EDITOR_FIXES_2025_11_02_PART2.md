# Editor Fixes - Part 2 (November 2, 2025)

## Summary
Critical bug fixes for the BeatSight editor based on user testing feedback. Addresses missing notes in preview, metadata display issues, and default view mode.

## Issues Fixed

### 1. Missing Notes in 2D/3D Preview ✅ **CRITICAL BUG**

**Problem**: User reported "there's no notes or anything at all" when viewing 2D/3D preview modes, despite notes being visible in Timeline view.

**Root Cause**: 
- GameplayPlayfield was auto-judging notes as "Miss" when they passed the miss window
- In editor preview mode, seeking to different times would cause notes to be marked as missed and removed
- The Update() loop had this code:
  ```csharp
  if (timeUntilHit < -missWindow)
      applyResult(note, HitResult.Miss, timeUntilHit);
  ```
- When a note is judged (including Miss), it fades out and expires via `ApplyResult()`
- This is correct for gameplay but WRONG for editor preview where you seek around

**Solution**:
1. Added `isPreviewMode` flag to `GameplayPlayfield`
2. Created `SetPreviewMode(bool)` method to control this behavior
3. Modified Update() loop to only auto-judge misses in gameplay mode:
   ```csharp
   if (!isPreviewMode && timeUntilHit < -missWindow)
       applyResult(note, HitResult.Miss, timeUntilHit);
   ```
4. `GameplayReplayHost` now calls `SetPreviewMode(true)` when loading beatmaps for editor preview

**Files Modified**:
- `desktop/BeatSight.Game/Screens/Gameplay/GameplayScreen.cs`
  - Added `isPreviewMode` field
  - Added `SetPreviewMode()` method
  - Modified `Update()` to respect preview mode
- `desktop/BeatSight.Game/Screens/Gameplay/GameplayReplayHost.cs`
  - Modified `applyBeatmap()` to enable preview mode

**Impact**: Notes now stay visible throughout the editor preview, allowing proper visualization and editing.

---

### 2. Ugly Editor Title Display ✅

**Problem**: Editor title showed raw YouTube filename: `"Editing: RichaadEB - Topic — Heir of Grief [ZoB5789MSh4]_20251103_013713"`

**Root Cause**: 
- AI audio detection tool extracts YouTube videos with titles like `"Artist - Title [VideoID]_timestamp"`
- EditorScreen was using this raw display name directly as the title
- No parsing to extract clean artist/title metadata

**Solution**:
1. Created `parseAudioDisplayName()` helper function with smart parsing:
   - Removes YouTube video ID pattern: `[VideoID]_timestamp`
   - Splits on " - " or " — " (em dash) to extract artist and title
   - Removes additional info in parentheses from title end
   - Falls back to "Unknown Artist" / "Untitled" for malformed inputs
   
2. Updated `initializeNewProject()` to use parsed metadata:
   ```csharp
   var (artist, title) = parseAudioDisplayName(trackInfo.DisplayName);
   beatmap.Metadata.Artist = artist;
   beatmap.Metadata.Title = title;
   setStatusBase($"Editing: {artist} — {title}");
   ```

**Example Transformations**:
- `"RichaadEB - Topic — Heir of Grief [ZoB5789MSh4]_20251103_013713"`  
  → Artist: `"RichaadEB - Topic"`, Title: `"Heir of Grief"`
- `"Ahiru - HEARTBEAT (USAO Remix) (IntellectualBoy) [abc123]_456789"`  
  → Artist: `"Ahiru"`, Title: `"HEARTBEAT (USAO Remix)"`

**Files Modified**:
- `desktop/BeatSight.Game/Screens/Editor/EditorScreen.cs`
  - Added `parseAudioDisplayName()` static method (with full documentation)
  - Modified `initializeNewProject()` to parse metadata
  - Changed status display to use clean artist/title

**Impact**: Editor now displays clean, readable titles that match user expectations.

---

### 3. Default View Mode ✅

**Problem**: Editor always defaulted to Timeline view, but user expected 3D view by default.

**Root Cause**:
- `previewMode` was initialized as: `new Bindable<EditorPreviewMode>(EditorPreviewMode.Timeline)`
- This hardcoded Timeline as the default regardless of user preferences

**Solution**:
1. Changed `previewMode` declaration from initialized Bindable to uninitialized field
2. In `load()` method, initialize based on user's `LaneViewMode` setting:
   ```csharp
   var initialMode = laneViewMode.Value == LaneViewMode.TwoDimensional 
       ? EditorPreviewMode.Playfield2D 
       : EditorPreviewMode.Playfield3D;
   previewMode = new Bindable<EditorPreviewMode>(initialMode);
   ```
3. This respects user's gameplay preference (default is 3D per `BeatSightConfigManager`)

**Files Modified**:
- `desktop/BeatSight.Game/Screens/Editor/EditorScreen.cs`
  - Changed `previewMode` field declaration
  - Added initialization logic in `load()` method

**Impact**: Editor now opens in 3D preview mode by default (or 2D if user prefers that), matching gameplay settings.

---

## Technical Details

### Preview Mode Implementation

The `isPreviewMode` flag creates a distinction between two playfield contexts:

| Mode | Auto-Judge Misses? | Use Case |
|------|-------------------|----------|
| Gameplay (false) | ✅ Yes | Actual gameplay with scoring |
| Preview (true) | ❌ No | Editor preview, practice mode |

**Why This Matters**:
- In gameplay: Notes must be judged to progress and calculate score
- In preview: Notes should persist for visualization regardless of timing
- Seeking in editor would previously mark all passed notes as missed
- Preview mode allows free scrubbing through the timeline

### Metadata Parsing Robustness

The `parseAudioDisplayName()` function handles multiple formats:

```csharp
// Pattern 1: YouTube with ID
"Artist - Title [VideoID]_timestamp" → (Artist, Title)

// Pattern 2: Simple format
"Artist - Title" → (Artist, Title)

// Pattern 3: Em dash separator
"Artist — Title" → (Artist, Title)

// Pattern 4: No separator
"Just A Title" → (Unknown Artist, Just A Title)
```

Uses regex to:
1. Remove YouTube artifacts: `\s*\[[^\]]+\]_\d+$`
2. Clean parenthetical info: `\s*\([^)]*\)\s*$`

---

## User Benefits

### 1. Editor Actually Works Now 🎉
- **Before**: No notes visible in preview, making editing impossible
- **After**: Notes display correctly in all preview modes
- Can now properly visualize beatmaps while editing

### 2. Clean Professional UI
- **Before**: `"Editing: RichaadEB - Topic — Heir of Grief [ZoB5789MSh4]_20251103_013713"`
- **After**: `"Editing: RichaadEB - Topic — Heir of Grief"`
- Metadata properly extracted for folder naming

### 3. Better Defaults
- Editor opens in 3D preview (user's preference)
- Matches gameplay settings
- Less clicking to get to desired view

---

## Testing Recommendations

### Verify Note Visibility
1. Open any beatmap in editor
2. Switch to 2D preview → Notes should be visible
3. Switch to 3D preview → Notes should be visible  
4. Click Play → Notes should scroll smoothly
5. Seek timeline → Notes should update position (not disappear)
6. Pause and seek backwards → Previous notes should reappear

### Verify Metadata Parsing
1. Import audio from YouTube via AI tool
2. Check editor title shows clean "Artist — Title"
3. Save beatmap
4. Check ~/BeatSight/Songs folder has clean folder name
5. Example: `Artist - Title (Creator)/` not `...[ VideoID]_123456/`

### Verify Default View
1. Close and reopen editor
2. Should default to 3D preview (not Timeline)
3. Change setting to 2D in gameplay
4. Reopen editor → Should default to 2D preview

---

## Code Quality

✅ **No compiler errors or warnings**  
✅ **Backwards compatible** - Doesn't break existing gameplay  
✅ **Well-commented** - Added XML docs for new methods  
✅ **Follows existing patterns** - Uses established bindable/config patterns  
✅ **Minimal changes** - Surgical fixes, no refactoring  

---

## Files Changed Summary

| File | Changes | LOC |
|------|---------|-----|
| `EditorScreen.cs` | + parseAudioDisplayName()<br>~ initializeNewProject()<br>~ previewMode initialization | +40 |
| `GameplayScreen.cs` | + isPreviewMode field<br>+ SetPreviewMode() method<br>~ Update() condition | +15 |
| `GameplayReplayHost.cs` | ~ applyBeatmap() | +3 |

**Total**: ~58 lines added/modified across 3 files

---

## Remaining Notes

### Preview Mode Toggle Buttons
The three buttons (Timeline / 2D / 3D) work correctly as radio buttons. Each shows active/inactive state clearly with color and opacity changes. No changes needed - working as designed.

### File Storage
Songs folder structure already implemented correctly in previous session:
- Location: `~/BeatSight/Songs/`
- Format: `{artist} - {title} ({creator})/`
- Backwards compatible with `~/BeatSight/Beatmaps/`

### Future Enhancements
- Consider adding beat grid overlay in preview modes
- Add waveform display in 2D/3D preview
- Allow snap-to-grid when placing notes in preview mode
- Show approach rate adjustment preview

---

**All critical issues resolved. Editor is now fully functional for beatmap creation and editing.**
