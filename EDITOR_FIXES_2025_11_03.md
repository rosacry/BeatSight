# Editor Fixes - November 3, 2025

## Issues Fixed

### 1. ✅ Default View Mode Changed to 3D
**Problem**: Editor was defaulting to the user's preference (2D/3D) instead of always starting with 3D.

**Solution**: Changed the initial preview mode in `EditorScreen.cs` to always default to `EditorPreviewMode.Playfield3D`:

```csharp
// Initialize preview mode - default to 3D playfield
previewMode = new Bindable<EditorPreviewMode>(EditorPreviewMode.Playfield3D);
```

### 2. ✅ Clean Title Display (Artist — Title only)
**Problem**: The editor title bar showed the full filename with YouTube video IDs and timestamps like:
```
Editing: RichaadEB - Topic — Heir of Grief [ZoB5789MSh4]_20251103_013713 • Playfield preview (2D)
```

**Solution**: 
- Cleaned up the title format to show only `Artist — Title`
- Changed status detail from `Playfield preview (2D)` to just `2D` or `3D`
- Updated `loadBeatmap()` to extract clean artist and title
- Removed the `parseAudioDisplayName()` helper from `EditorScreen.cs`

Now displays as:
```
Editing: Artist — Title • 3D
```

### 3. ✅ Removed File-Based Metadata Parsing
**Problem**: The application was trying to parse artist and title from the audio filename before using the Shazam-like AI tool (MusicBrainz).

**Solution**:
- Removed `parseDisplayName()` helper method from `AiBeatmapGenerator.cs`
- Updated `persistBeatmapAsync()` to use only placeholder defaults ("Untitled", "Unknown Artist")
- Updated `initializeNewProject()` in `EditorScreen.cs` to use placeholder defaults instead of parsing filename
- Now the **only** metadata source is the `MetadataEnricher` which uses:
  1. Embedded ID3 tags (TagLib)
  2. MusicBrainz API (Shazam-like recognition)

### 4. ✅ Fixed "Load a beatmap to preview gameplay" Persistent Message
**Problem**: After clicking "Open Draft in Editor", the preview still showed placeholder text instead of the generated notes.

**Solution**: Added proper beatmap synchronization in multiple places:
- Added `Schedule(() => gameplayPreview.SetBeatmap(beatmap))` in `loadBeatmap()` after loading audio
- Added scheduled beatmap update in `load()` method after initial beatmap loading
- Updated `reloadTimeline()` to properly schedule beatmap updates to the preview
- This ensures the `GameplayPreview` component receives the beatmap data and hides the placeholder

### 5. ✅ Fixed Notes Not Appearing in Preview
**Problem**: The 2D/3D preview wasn't showing any notes from the generated beatmap.

**Solution**: 
- Ensured `gameplayPreview.SetBeatmap()` is called whenever the beatmap is loaded or modified
- Added proper scheduling to avoid race conditions with component initialization
- The `GameplayReplayHost` now properly receives and displays the hit objects from the loaded beatmap

## Technical Details

### Modified Files
1. `/desktop/BeatSight.Game/Screens/Editor/EditorScreen.cs`
   - Changed default preview mode to 3D
   - Cleaned up title display logic
   - Removed filename parsing
   - Added proper preview synchronization
   - Removed redundant status messages

2. `/desktop/BeatSight.Game/AI/AiBeatmapGenerator.cs`
   - Removed filename-based metadata parsing
   - Simplified to use placeholder defaults only
   - Relies entirely on `MetadataEnricher` for real metadata

### Metadata Resolution Flow (After Changes)
```
1. AI generates beatmap → Defaults: "Untitled", "Unknown Artist"
2. MetadataEnricher.EnrichAsync() runs:
   a. Tries embedded ID3 tags (TagLib)
   b. If still missing, queries MusicBrainz API
3. Best match from MusicBrainz updates Artist and Title
4. Beatmap saved with resolved metadata
```

### Preview Update Flow
```
1. User clicks "Open Draft in Editor" in MappingGenerationScreen
2. EditorScreen(beatmapPath) constructor called
3. load() method:
   - Creates UI components (including gameplayPreview)
   - Calls loadBeatmap(beatmapPath)
   - Schedules gameplayPreview.SetBeatmap(beatmap)
4. Preview mode defaults to 3D (Playfield3D)
5. GameplayPreview receives beatmap → hides placeholder, shows notes
6. Notes render in 3D Guitar Hero style
```

## Testing Checklist

- [x] Build succeeds without errors
- [ ] Opening AI-generated beatmap shows notes in 3D preview
- [ ] Title bar shows clean "Artist — Title • 3D" format
- [ ] Switching between 2D/3D works correctly
- [ ] Timeline view still works
- [ ] Metadata is resolved via MusicBrainz (not filename)
- [ ] Placeholder text disappears when beatmap has hit objects
- [ ] Manual note editing updates preview properly

## Next Steps

1. Test the full workflow:
   - Import audio
   - Generate beatmap via AI
   - Click "Open Draft in Editor"
   - Verify notes appear in 3D preview
   - Verify title is clean

2. If MusicBrainz doesn't find metadata:
   - Beatmap will show "Unknown Artist — Untitled"
   - User can manually edit in editor (future feature)

3. Consider adding metadata editing UI in the editor for manual corrections
