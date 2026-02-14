using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using Newtonsoft.Json;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void prepareUndoSnapshot()
        {
            if (beatmap == null || editSnapshotArmed)
                return;

            var snapshot = createSnapshot();

            if (undoStack.Count > 0 && undoStack[^1].BeatmapJson == snapshot.BeatmapJson)
                return;

            redoStack.Clear();
            pushSnapshot(undoStack, snapshot);
            editSnapshotArmed = true;
            updateActionButtons();
        }

        private EditorSnapshot createSnapshot()
        {
            if (beatmap == null)
                throw new InvalidOperationException("No beatmap loaded.");

            return new EditorSnapshot
            {
                BeatmapJson = serializeBeatmap(beatmap),
                CurrentTime = currentTime,
                Zoom = timeline?.CurrentZoom ?? timelineZoom,
                SnapDivisor = snapDivisor,
                WaveformScale = waveformScale,
                BeatGridVisible = beatGridVisible,
                Description = !string.IsNullOrWhiteSpace(statusDetailText)
                    ? statusDetailText!
                    : $"State at {formatTime(currentTime)}"
            };
        }

        private void undoLastEdit()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Nothing to undo");
                return;
            }

            if (undoStack.Count == 0)
            {
                appendStatusDetail("Nothing to undo");
                return;
            }

            var currentSnapshot = createSnapshot();
            if (redoStack.Count > 0 && redoStack[^1].BeatmapJson == currentSnapshot.BeatmapJson)
            {
                // Avoid stacking duplicate redo states.
            }
            else
            {
                pushSnapshot(redoStack, currentSnapshot);
            }

            var snapshot = undoStack[^1];
            undoStack.RemoveAt(undoStack.Count - 1);
            restoreSnapshot(snapshot);
            appendStatusDetail("Undo applied");
            updateActionButtons();
        }

        private void redoLastEdit()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Nothing to redo");
                return;
            }

            if (redoStack.Count == 0)
            {
                appendStatusDetail("Nothing to redo");
                return;
            }

            var currentSnapshot = createSnapshot();
            if (undoStack.Count > 0 && undoStack[^1].BeatmapJson == currentSnapshot.BeatmapJson)
            {
                // Existing undo top already reflects current state.
            }
            else
            {
                pushSnapshot(undoStack, currentSnapshot);
            }

            var snapshot = redoStack[^1];
            redoStack.RemoveAt(redoStack.Count - 1);
            restoreSnapshot(snapshot);
            appendStatusDetail("Redo applied");
            updateActionButtons();
        }

        private void restoreSnapshot(EditorSnapshot snapshot)
        {
            bool originalPersistenceState = suppressEditorDefaultPersistence;
            suppressEditorDefaultPersistence = true;

            var restored = JsonConvert.DeserializeObject<Beatmap>(snapshot.BeatmapJson);
            if (restored == null)
            {
                appendStatusDetail("Undo failed");
                suppressEditorDefaultPersistence = originalPersistenceState;
                return;
            }

            beatmap = restored;
            trackLength = beatmap.Audio.Duration;
            snapDivisor = coerceSnapDivisor(snapshot.SnapDivisor > 0 ? snapshot.SnapDivisor : snapDivisor);
            timelineZoom = Math.Clamp(snapshot.Zoom, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);
            waveformScale = Math.Clamp(snapshot.WaveformScale > 0 ? snapshot.WaveformScale : waveformScale, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);
            beatGridVisible = snapshot.BeatGridVisible;
            currentTime = Math.Clamp(snapshot.CurrentTime, 0, trackLength > 0 ? trackLength : snapshot.CurrentTime);

            reloadTimeline();
            timeline.SetCurrentTime(currentTime);
            timeText.Text = formatTime(currentTime);

            var editorInfo = ensureEditorInfo();
            editorInfo.SnapDivisor = snapDivisor;
            editorInfo.TimelineZoom = timelineZoom;
            editorInfo.WaveformScale = waveformScale;
            editorInfo.BeatGridVisible = beatGridVisible;

            populateInspectorFromBeatmap();
            refreshUnsavedState(forceRecompute: true);
            editSnapshotArmed = false;
            lastInspectorSnapshotAtUtc = DateTime.MinValue;
            refreshTimelineToolboxState();

            suppressEditorDefaultPersistence = originalPersistenceState;
            persistEditorDefaults();
        }

        private void refreshUnsavedState(bool forceRecompute = false)
        {
            if (beatmap == null)
            {
                hasUnsavedChanges = false;
                updateStatusText();
                return;
            }

            if (!forceRecompute && hasUnsavedChanges)
            {
                updateStatusText();
                return;
            }

            if (lastSavedSnapshot == null)
            {
                hasUnsavedChanges = true;
            }
            else
            {
                hasUnsavedChanges = serializeBeatmap(beatmap) != lastSavedSnapshot;
            }

            updateStatusText();
        }

        private string serializeBeatmap(Beatmap map)
            => JsonConvert.SerializeObject(map, Formatting.None);

        private void pushSnapshot(List<EditorSnapshot> stack, EditorSnapshot snapshot)
        {
            if (stack.Count >= maxUndoSteps)
                stack.RemoveAt(0);

            stack.Add(snapshot);
        }

        private int coerceSnapDivisor(int divisor)
        {
            if (divisor <= 0)
                return allowedSnapDivisors[0];

            int closest = allowedSnapDivisors[0];
            int minDiff = Math.Abs(divisor - closest);

            for (int i = 1; i < allowedSnapDivisors.Length; i++)
            {
                int candidate = allowedSnapDivisors[i];
                int diff = Math.Abs(candidate - divisor);

                if (diff < minDiff)
                {
                    minDiff = diff;
                    closest = candidate;
                }
            }

            return closest;
        }

        private EditorInfo ensureEditorInfo()
        {
            if (beatmap == null)
                throw new InvalidOperationException("No beatmap loaded.");

            var editor = beatmap.Editor ??= new EditorInfo();

            if (!editor.SnapDivisor.HasValue)
                editor.SnapDivisor = snapDivisor;

            if (!editor.VisualLanes.HasValue)
                editor.VisualLanes = 7;

            if (!editor.TimelineZoom.HasValue)
                editor.TimelineZoom = timelineZoom;

            if (!editor.WaveformScale.HasValue)
                editor.WaveformScale = waveformScale;

            if (!editor.BeatGridVisible.HasValue)
                editor.BeatGridVisible = beatGridVisible;

            return editor;
        }
    }
}
