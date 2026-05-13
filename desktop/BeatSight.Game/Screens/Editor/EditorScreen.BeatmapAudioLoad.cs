using System;
using System.IO;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Mapping;
using osu.Framework.Logging;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void loadBeatmap(string path)
        {
            try
            {
                beatmap = BeatmapLoader.LoadFromFile(path);
                beatmapPath = path;
                initialBeatmapBpm = beatmap.Timing.Bpm;

                // Set clean status with just artist and title
                string artist = beatmap.Metadata.Artist ?? "Unknown Artist";
                string title = beatmap.Metadata.Title ?? "Untitled";
                setStatusBase($"Editing: {artist} - {title}");
                setStatusDetail(playbackAvailable ? null : offlinePlaybackMessage);

                hasUnsavedChanges = false;
                undoStack.Clear();
                redoStack.Clear();
                editSnapshotArmed = false;
                lastInspectorSnapshotAtUtc = DateTime.MinValue;
                int fallbackSnapDivisor = coerceSnapDivisor(beatmap.Editor?.SnapDivisor ?? snapDivisor);
                snapDivisor = coerceSnapDivisor(editorSnapDivisorDefault?.Value ?? fallbackSnapDivisor);
                linkTimelineAndPlaybackZoom = editorTimelinePlaybackZoomLinkedDefault?.Value ?? linkTimelineAndPlaybackZoom;
                bool previousPersistenceState = suppressEditorDefaultPersistence;
                suppressEditorDefaultPersistence = true;

                if (beatmap.Editor?.TimelineZoom.HasValue == true)
                    timelineZoom = Math.Clamp(beatmap.Editor.TimelineZoom!.Value, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);
                else
                    timelineZoom = Math.Clamp(editorTimelineZoomDefault?.Value ?? timelineZoom, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);

                if (beatmap.Editor?.WaveformScale.HasValue == true)
                    waveformScale = Math.Clamp(beatmap.Editor.WaveformScale!.Value, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);
                else
                    waveformScale = Math.Clamp(editorWaveformScaleDefault?.Value ?? waveformScale, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);

                beatGridVisible = beatmap.Editor?.BeatGridVisible ?? (editorBeatGridVisibleDefault?.Value ?? true);

                suppressEditorDefaultPersistence = previousPersistenceState;
                updateStatusText();
                trackLength = beatmap.Audio.Duration;
                currentTime = resolvePreferredStartTime(out string? startContextDetail);
                snapCurrentTimeToGridOnBeatmapLoad();
                if (timeText != null)
                    timeText.Text = formatTime(currentTime);
                reloadTimeline();
                if (!string.IsNullOrWhiteSpace(startContextDetail))
                    appendStatusDetail(startContextDetail);
                var editorInfo = ensureEditorInfo();
                editorInfo.TimelineZoom = timelineZoom;
                editorInfo.SnapDivisor = snapDivisor;
                editorInfo.WaveformScale = waveformScale;
                editorInfo.BeatGridVisible = beatGridVisible;
                refreshTimelineToolboxState();
                lastSavedSnapshot = serializeBeatmap(beatmap);
                populateInspectorFromBeatmap();

                // Load debug data if available
                string debugPath = Path.ChangeExtension(path, ".debug.json");
                if (File.Exists(debugPath))
                {
                    try
                    {
                        string json = File.ReadAllText(debugPath);
                        timeline?.LoadDebugData(json);
                    }
                    catch (Exception ex)
                    {
                        osu.Framework.Logging.Logger.Log($"Failed to load debug data: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                    }
                }

                // Load audio track
                loadAudioTrackFromBeatmap();
                if (!playbackAvailable)
                    appendStatusDetail(offlinePlaybackMessage);
                updateActionButtons();
                updatePlaybackAvailabilityUI();
            }
            catch (Exception ex)
            {
                setStatusBase(string.Empty);
                setStatusDetail($"Failed to load beatmap: {ex.Message}");
                reloadTimeline();
                updateActionButtons();
                beatmap = null;
                initialBeatmapBpm = null;
                populateInspectorFromBeatmap();
            }
        }

        private void initializeNewProject(ImportedAudioTrack? trackInfo)
        {
            beatmap = new Beatmap
            {
                Metadata =
                {
                    Title = "Untitled",
                    Artist = "Unknown Artist",
                    Creator = Environment.UserName ?? "BeatSight Mapper",
                    BeatmapId = Guid.NewGuid().ToString(),
                    CreatedAt = DateTime.UtcNow,
                    ModifiedAt = DateTime.UtcNow
                },
                Audio =
                {
                    Filename = trackInfo?.RelativeStoragePath ?? string.Empty,
                    Duration = trackInfo?.DurationMilliseconds.HasValue == true
                        ? (int)Math.Round(trackInfo.DurationMilliseconds.Value)
                        : 60000 // Default 1 minute for blank projects
                },
                Editor = new EditorInfo
                {
                    SnapDivisor = coerceSnapDivisor(editorSnapDivisorDefault?.Value ?? 4),
                    VisualLanes = 7,
                    TimelineZoom = editorTimelineZoomDefault?.Value ?? 1.32,
                    WaveformScale = editorWaveformScaleDefault?.Value ?? 1.0,
                    BeatGridVisible = editorBeatGridVisibleDefault?.Value ?? true
                }
            };

            initialBeatmapBpm = beatmap.Timing.Bpm;

            setStatusBase("Editing: Unknown Artist - Untitled");
            setStatusDetail(playbackAvailable ? "Ready to map" : offlinePlaybackMessage);
            hasUnsavedChanges = true;
            undoStack.Clear();
            redoStack.Clear();
            editSnapshotArmed = false;
            lastInspectorSnapshotAtUtc = DateTime.MinValue;
            lastSavedSnapshot = null;
            snapDivisor = coerceSnapDivisor(editorSnapDivisorDefault?.Value ?? 4);
            suppressEditorDefaultPersistence = true;
            applyEditorDefaultsFromConfig();
            suppressEditorDefaultPersistence = false;
            updateStatusText();
            trackLength = beatmap?.Audio.Duration ?? 0;
            currentTime = 0;
            if (timeText != null)
                timeText.Text = formatTime(currentTime);
            reloadTimeline();
            ensureEditorInfo();
            refreshTimelineToolboxState();
            populateInspectorFromBeatmap();
            if (trackInfo != null)
                loadAudioTrackFromStorage(trackInfo.RelativeStoragePath);
            if (!playbackAvailable)
                appendStatusDetail(offlinePlaybackMessage);
            updateActionButtons();
            updatePlaybackAvailabilityUI();
        }

        private void loadAudioTrackFromBeatmap()
        {
            if (beatmap == null || beatmapPath == null)
                return;

            if (isVisualCaptureMode())
            {
                disposeTrack();
                track = null;
                trackLength = beatmap.Audio.Duration > 0
                    ? beatmap.Audio.Duration
                    : Math.Max(trackLength, 60000);
                reloadTimeline();
                refreshTimelineToolboxState();
                return;
            }

            disposeTrack();

            if (string.IsNullOrWhiteSpace(beatmap.Audio.Filename))
            {
                appendStatusDetail("No audio associated with beatmap");
                track = null;
                return;
            }

            string resolvedAudioPath = Path.IsPathRooted(beatmap.Audio.Filename)
                ? beatmap.Audio.Filename
                : Path.Combine(Path.GetDirectoryName(beatmapPath) ?? string.Empty, beatmap.Audio.Filename);

            if (!File.Exists(resolvedAudioPath))
            {
                appendStatusDetail("Audio file missing");
                return;
            }

            try
            {
                string cacheDirectory = host.Storage.GetFullPath("EditorAudio");
                Directory.CreateDirectory(cacheDirectory);

                string cachedName = $"{beatmap.Metadata.BeatmapId}_editor_{Path.GetFileName(resolvedAudioPath)}";
                string cachedPath = Path.Combine(cacheDirectory, cachedName);

                File.Copy(resolvedAudioPath, cachedPath, overwrite: true);

                string relativePath = Path.Combine("EditorAudio", cachedName).Replace(Path.DirectorySeparatorChar, '/');

                loadAudioTrackFromStorage(relativePath);
            }
            catch (Exception ex)
            {
                appendStatusDetail($"Audio load failed: {ex.Message}");
                track = null;
            }
        }

        private void loadAudioTrackFromStorage(string relativePath)
        {
            if (isVisualCaptureMode())
            {
                disposeTrack();
                track = null;
                trackLength = beatmap?.Audio.Duration ?? trackLength;
                reloadTimeline();
                refreshTimelineToolboxState();
                return;
            }

            disposeTrack();

            try
            {
                var store = storageTrackStore ?? audioManager.Tracks;
                var loadedTrack = store.Get(relativePath);

                if (loadedTrack == null)
                    throw new FileNotFoundException($"Audio track '{relativePath}' could not be resolved in storage.");

                track = loadedTrack;
                track.Completed += onTrackCompleted;
                applyTrackPlaybackRate();
                updateEditorMasterVolumeOutput();
                updateEditorMusicVolumeOutput();
                trackLength = track.Length;
                if (currentTime > 0)
                    track.Seek(Math.Clamp(currentTime, 0, trackLength));
                lastTrackTime = track.CurrentTime;

                if (beatmap != null && trackLength > 0)
                    beatmap.Audio.Duration = (int)Math.Round(trackLength);

                snapCurrentTimeToGridOnBeatmapLoad();
                reloadTimeline();
                refreshTimelineToolboxState();

                var absolutePath = host.Storage.GetFullPath(relativePath.Replace('/', Path.DirectorySeparatorChar));
                if (!File.Exists(absolutePath))
                    throw new FileNotFoundException($"Audio asset missing at {absolutePath}");

                queueWaveformLoad(absolutePath);
                appendStatusDetail("Audio loaded");
            }
            catch (Exception ex)
            {
                appendStatusDetail($"Audio load failed: {ex.Message}");
                track = null;
            }
        }

        private static bool isVisualCaptureMode()
        {
            string? value = Environment.GetEnvironmentVariable("BEATSIGHT_RUN_VISUAL_TESTS");
            if (string.IsNullOrWhiteSpace(value))
                return false;

            return value == "1"
                   || value.Equals("true", StringComparison.OrdinalIgnoreCase)
                   || value.Equals("yes", StringComparison.OrdinalIgnoreCase);
        }

        private void snapCurrentTimeToGridOnBeatmapLoad()
        {
            if (beatmap == null || !beatGridVisible)
                return;

            double snapped = quantizeTimeToSnapGrid(currentTime, onlyWhenBeatGridVisible: false);
            if (!double.IsFinite(snapped))
                return;

            if (Math.Abs(snapped - currentTime) <= 0.01)
                return;

            currentTime = snapped;
            if (track != null && Math.Abs(track.CurrentTime - currentTime) > 1.5)
                track.Seek(currentTime);
        }

        private static int cleanupDuplicateLaneTimeNotes(Beatmap map)
        {
            if (map.HitObjects == null || map.HitObjects.Count <= 1)
                return 0;

            int laneCount = Math.Max(1, LaneManagement.ResolveLaneCount(map, fallbackLaneCount: map.Editor?.VisualLanes ?? 7));
            var uniquePositions = new System.Collections.Generic.HashSet<(int Lane, int Time)>();
            var deduped = new System.Collections.Generic.List<HitObject>(map.HitObjects.Count);
            int removed = 0;

            foreach (var hit in map.HitObjects)
            {
                int lane = resolveLaneForCleanup(hit, laneCount);
                if (!uniquePositions.Add((lane, hit.Time)))
                {
                    removed++;
                    continue;
                }

                deduped.Add(hit);
            }

            if (removed <= 0)
                return 0;

            map.HitObjects = deduped;
            map.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            map.Metadata.ModifiedAt = DateTime.UtcNow;
            return removed;
        }

        private static int resolveLaneForCleanup(HitObject hit, int laneCount)
        {
            int lane = hit.Lane ?? DrumLaneHeuristics.ResolveLane(hit.Component);
            return Math.Clamp(lane, 0, Math.Max(0, laneCount - 1));
        }
    }
}
