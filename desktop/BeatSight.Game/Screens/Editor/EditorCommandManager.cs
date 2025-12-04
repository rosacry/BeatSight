using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using Newtonsoft.Json;

namespace BeatSight.Game.Screens.Editor
{
    /// <summary>
    /// Manages undo/redo functionality for the editor using snapshot-based state management.
    /// 
    /// This class maintains two stacks of editor snapshots:
    /// - UndoStack: Previous states that can be reverted to
    /// - RedoStack: States undone that can be re-applied
    /// 
    /// Usage:
    /// - Call PrepareSnapshot() before making any edit
    /// - Call Undo()/Redo() to navigate history
    /// - Use CanUndo/CanRedo to check availability
    /// </summary>
    public class EditorCommandManager
    {
        private readonly List<EditorSnapshot> undoStack = new();
        private readonly List<EditorSnapshot> redoStack = new();
        private bool snapshotArmed;

        /// <summary>
        /// Maximum number of undo steps to retain.
        /// Older snapshots are discarded when this limit is reached.
        /// </summary>
        public int MaxUndoSteps { get; set; } = 50;

        /// <summary>
        /// Number of history items to show in preview panels.
        /// </summary>
        public int HistoryPreviewCount { get; set; } = 5;

        /// <summary>
        /// Whether there are states available to undo.
        /// </summary>
        public bool CanUndo => undoStack.Count > 0;

        /// <summary>
        /// Whether there are states available to redo.
        /// </summary>
        public bool CanRedo => redoStack.Count > 0;

        /// <summary>
        /// Number of available undo steps.
        /// </summary>
        public int UndoCount => undoStack.Count;

        /// <summary>
        /// Number of available redo steps.
        /// </summary>
        public int RedoCount => redoStack.Count;

        /// <summary>
        /// Whether a snapshot has been prepared and is waiting for an edit.
        /// </summary>
        public bool IsSnapshotArmed => snapshotArmed;

        /// <summary>
        /// Event fired when undo/redo state changes.
        /// </summary>
        public event Action? StateChanged;

        /// <summary>
        /// Get recent undo history for display.
        /// </summary>
        /// <param name="count">Maximum items to return</param>
        /// <returns>Most recent undo snapshots (newest first)</returns>
        public IReadOnlyList<EditorSnapshot> GetRecentUndoHistory(int? count = null)
        {
            int take = count ?? HistoryPreviewCount;
            var result = new List<EditorSnapshot>();

            for (int i = undoStack.Count - 1; i >= 0 && result.Count < take; i--)
                result.Add(undoStack[i]);

            return result;
        }

        /// <summary>
        /// Get recent redo history for display.
        /// </summary>
        /// <param name="count">Maximum items to return</param>
        /// <returns>Most recent redo snapshots (newest first)</returns>
        public IReadOnlyList<EditorSnapshot> GetRecentRedoHistory(int? count = null)
        {
            int take = count ?? HistoryPreviewCount;
            var result = new List<EditorSnapshot>();

            for (int i = redoStack.Count - 1; i >= 0 && result.Count < take; i--)
                result.Add(redoStack[i]);

            return result;
        }

        /// <summary>
        /// Prepare a snapshot before making an edit.
        /// Call this before any operation that modifies the beatmap.
        /// </summary>
        /// <param name="beatmap">Current beatmap state</param>
        /// <param name="editorState">Current editor state (time, zoom, etc.)</param>
        /// <param name="description">Optional description of the action about to be performed</param>
        /// <returns>True if snapshot was created, false if already armed or duplicate</returns>
        public bool PrepareSnapshot(Beatmap beatmap, EditorStateInfo editorState, string? description = null)
        {
            if (beatmap == null || snapshotArmed)
                return false;

            var snapshot = CreateSnapshot(beatmap, editorState, description);

            // Don't create duplicate snapshots
            if (undoStack.Count > 0 && undoStack[^1].BeatmapJson == snapshot.BeatmapJson)
                return false;

            // Clear redo stack when new edit is made
            redoStack.Clear();

            PushSnapshot(undoStack, snapshot);
            snapshotArmed = true;
            StateChanged?.Invoke();

            return true;
        }

        /// <summary>
        /// Convenience method to arm the snapshot flag.
        /// </summary>
        public void ArmSnapshot(Beatmap beatmap, EditorStateInfo editorState, string? description = null)
            => PrepareSnapshot(beatmap, editorState, description);

        /// <summary>
        /// Reset the snapshot armed state after an edit completes.
        /// </summary>
        public void ClearArmedState()
        {
            snapshotArmed = false;
        }

        /// <summary>
        /// Perform an undo operation.
        /// </summary>
        /// <param name="currentBeatmap">Current beatmap to save to redo stack</param>
        /// <param name="currentState">Current editor state</param>
        /// <returns>The snapshot to restore, or null if nothing to undo</returns>
        public EditorSnapshot? Undo(Beatmap currentBeatmap, EditorStateInfo currentState)
        {
            if (!CanUndo)
                return null;

            // Save current state to redo stack
            var currentSnapshot = CreateSnapshot(currentBeatmap, currentState, "Before undo");

            if (redoStack.Count == 0 || redoStack[^1].BeatmapJson != currentSnapshot.BeatmapJson)
            {
                PushSnapshot(redoStack, currentSnapshot);
            }

            var snapshot = undoStack[^1];
            undoStack.RemoveAt(undoStack.Count - 1);
            snapshotArmed = false;
            StateChanged?.Invoke();

            return snapshot;
        }

        /// <summary>
        /// Perform a redo operation.
        /// </summary>
        /// <param name="currentBeatmap">Current beatmap to save to undo stack</param>
        /// <param name="currentState">Current editor state</param>
        /// <returns>The snapshot to restore, or null if nothing to redo</returns>
        public EditorSnapshot? Redo(Beatmap currentBeatmap, EditorStateInfo currentState)
        {
            if (!CanRedo)
                return null;

            // Save current state to undo stack
            var currentSnapshot = CreateSnapshot(currentBeatmap, currentState, "Before redo");

            if (undoStack.Count == 0 || undoStack[^1].BeatmapJson != currentSnapshot.BeatmapJson)
            {
                PushSnapshot(undoStack, currentSnapshot);
            }

            var snapshot = redoStack[^1];
            redoStack.RemoveAt(redoStack.Count - 1);
            snapshotArmed = false;
            StateChanged?.Invoke();

            return snapshot;
        }

        /// <summary>
        /// Clear all undo/redo history.
        /// </summary>
        public void Clear()
        {
            undoStack.Clear();
            redoStack.Clear();
            snapshotArmed = false;
            StateChanged?.Invoke();
        }

        /// <summary>
        /// Create a snapshot from current state.
        /// </summary>
        public static EditorSnapshot CreateSnapshot(Beatmap beatmap, EditorStateInfo state, string? description = null)
        {
            return new EditorSnapshot
            {
                BeatmapJson = SerializeBeatmap(beatmap),
                CurrentTime = state.CurrentTime,
                Zoom = state.TimelineZoom,
                SnapDivisor = state.SnapDivisor,
                WaveformScale = state.WaveformScale,
                BeatGridVisible = state.BeatGridVisible,
                Description = description ?? $"State at {FormatTime(state.CurrentTime)}"
            };
        }

        /// <summary>
        /// Deserialize a beatmap from a snapshot.
        /// </summary>
        public static Beatmap? DeserializeBeatmap(EditorSnapshot snapshot)
        {
            return JsonConvert.DeserializeObject<Beatmap>(snapshot.BeatmapJson);
        }

        /// <summary>
        /// Serialize a beatmap to JSON.
        /// </summary>
        public static string SerializeBeatmap(Beatmap beatmap)
        {
            return JsonConvert.SerializeObject(beatmap, Formatting.None);
        }

        private void PushSnapshot(List<EditorSnapshot> stack, EditorSnapshot snapshot)
        {
            if (stack.Count >= MaxUndoSteps)
                stack.RemoveAt(0);

            stack.Add(snapshot);
        }

        private static string FormatTime(double timeMs)
        {
            var ts = TimeSpan.FromMilliseconds(timeMs);
            return ts.TotalHours >= 1
                ? $"{(int)ts.TotalHours}:{ts.Minutes:D2}:{ts.Seconds:D2}.{ts.Milliseconds / 100}"
                : $"{ts.Minutes}:{ts.Seconds:D2}.{ts.Milliseconds / 100}";
        }
    }

    /// <summary>
    /// Current editor state information used for snapshots.
    /// </summary>
    public struct EditorStateInfo
    {
        public double CurrentTime { get; init; }
        public double TimelineZoom { get; init; }
        public int SnapDivisor { get; init; }
        public double WaveformScale { get; init; }
        public bool BeatGridVisible { get; init; }
    }

    /// <summary>
    /// A snapshot of editor state for undo/redo.
    /// </summary>
    public class EditorSnapshot
    {
        /// <summary>
        /// Serialized beatmap JSON.
        /// </summary>
        public string BeatmapJson { get; init; } = string.Empty;

        /// <summary>
        /// Playback position at time of snapshot.
        /// </summary>
        public double CurrentTime { get; init; }

        /// <summary>
        /// Timeline zoom level.
        /// </summary>
        public double Zoom { get; init; } = 1.0;

        /// <summary>
        /// Snap divisor setting.
        /// </summary>
        public int SnapDivisor { get; init; } = 4;

        /// <summary>
        /// Waveform scale setting.
        /// </summary>
        public double WaveformScale { get; init; } = 1.0;

        /// <summary>
        /// Whether beat grid was visible.
        /// </summary>
        public bool BeatGridVisible { get; init; } = true;

        /// <summary>
        /// Human-readable description of this state.
        /// </summary>
        public string Description { get; init; } = string.Empty;
    }
}
