using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using osu.Framework.Graphics;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void refreshTimelineLaneEditorControls()
        {
            if (timelineLaneSelectionText == null
                || timelineLaneNameInput == null
                || timelineLaneShortNameInput == null
                || timelineLaneColorInput == null)
            {
                return;
            }

            if (!tryGetEditableLanes(out var lanes))
            {
                suppressLaneEditorFieldSync = true;
                timelineLaneSelectionText.Text = "Lane -";
                timelineLaneNameInput.Current.Value = string.Empty;
                timelineLaneShortNameInput.Current.Value = string.Empty;
                timelineLaneColorInput.Current.Value = string.Empty;
                suppressLaneEditorFieldSync = false;
                return;
            }

            var lane = lanes[timelineLaneEditIndex];
            string fallbackLabel = $"Lane {timelineLaneEditIndex + 1}";
            string laneLabel = LaneManagement.ResolveLaneLabel(beatmap, timelineLaneEditIndex, fallbackLabel);
            timelineLaneSelectionText.Text = $"L{timelineLaneEditIndex + 1} {laneLabel}";

            suppressLaneEditorFieldSync = true;
            timelineLaneNameInput.Current.Value = lane.Name ?? string.Empty;
            timelineLaneShortNameInput.Current.Value = lane.ShortName ?? string.Empty;
            timelineLaneColorInput.Current.Value = lane.ColorHex ?? string.Empty;
            suppressLaneEditorFieldSync = false;

            bool canRemove = lanes.Count > LaneManagement.MinLaneCount;
            timelineLaneRemoveButton?.FadeTo(canRemove ? 1f : 0.56f, 120, Easing.OutQuint);
        }

        private void stepTimelineLaneSelection(int delta)
        {
            if (!tryGetEditableLanes(out var lanes))
                return;

            timelineLaneEditIndex = Math.Clamp(timelineLaneEditIndex + delta, 0, lanes.Count - 1);
            refreshTimelineLaneEditorControls();
        }

        private void applyTimelineLaneEdits()
        {
            if (beatmap == null || suppressLaneEditorFieldSync)
                return;

            if (!LaneManagement.IsLaneEditAllowed(LaneEditScope.Editor, LaneEditOperation.Rename)
                || !LaneManagement.IsLaneEditAllowed(LaneEditScope.Editor, LaneEditOperation.Recolor))
            {
                appendStatusDetail("Lane edit blocked in current context.");
                return;
            }

            if (!tryGetEditableLanes(out var lanes))
                return;

            string laneName = timelineLaneNameInput.Current.Value?.Trim() ?? string.Empty;
            string laneShortName = timelineLaneShortNameInput.Current.Value?.Trim() ?? string.Empty;
            string laneColorText = timelineLaneColorInput.Current.Value?.Trim() ?? string.Empty;

            bool hasColor = !string.IsNullOrWhiteSpace(laneColorText);
            Color4 parsedColor = default;
            if (hasColor && !LaneManagement.TryParseColorHex(laneColorText, out parsedColor))
            {
                appendStatusDetail("Lane color must be #RRGGBB.");
                refreshTimelineLaneEditorControls();
                return;
            }

            var existing = lanes[timelineLaneEditIndex];
            string normalizedName = string.IsNullOrWhiteSpace(laneName) ? existing.Name ?? string.Empty : laneName;
            string normalizedShortName = string.IsNullOrWhiteSpace(laneShortName) ? existing.ShortName ?? string.Empty : laneShortName;
            string normalizedColor = hasColor ? LaneManagement.ToColorHex(parsedColor) : existing.ColorHex ?? string.Empty;

            bool changed = !string.Equals(existing.Name, normalizedName, StringComparison.Ordinal)
                           || !string.Equals(existing.ShortName, normalizedShortName, StringComparison.Ordinal)
                           || !string.Equals(existing.ColorHex, normalizedColor, StringComparison.OrdinalIgnoreCase);
            if (!changed)
            {
                refreshTimelineLaneEditorControls();
                return;
            }

            prepareUndoSnapshot();
            LaneManagement.RenameLane(beatmap, timelineLaneEditIndex, laneName, laneShortName);
            if (hasColor)
                LaneManagement.RecolorLane(beatmap, timelineLaneEditIndex, parsedColor);

            onLaneLayoutMutated($"Updated lane {timelineLaneEditIndex + 1}");
        }

        private void addTimelineLane()
        {
            if (beatmap == null)
                return;

            if (!LaneManagement.IsLaneEditAllowed(LaneEditScope.Editor, LaneEditOperation.Add))
            {
                appendStatusDetail("Adding lanes is not allowed in this context.");
                return;
            }

            prepareUndoSnapshot();
            if (!LaneManagement.AddLane(beatmap, out int addedLane))
            {
                appendStatusDetail($"Max {LaneManagement.MaxLaneCount} lanes reached.");
                refreshTimelineLaneEditorControls();
                return;
            }

            timelineLaneEditIndex = addedLane;
            onLaneLayoutMutated($"Added lane {addedLane + 1}");
        }

        private void removeTimelineLane()
        {
            if (beatmap == null)
                return;

            if (!LaneManagement.IsLaneEditAllowed(LaneEditScope.Editor, LaneEditOperation.Remove))
            {
                appendStatusDetail("Removing lanes is not allowed in this context.");
                return;
            }

            if (!tryGetEditableLanes(out _))
                return;

            prepareUndoSnapshot();
            int removedIndex = timelineLaneEditIndex;
            if (!LaneManagement.RemoveLane(beatmap, removedIndex))
            {
                appendStatusDetail("Cannot remove the last lane.");
                refreshTimelineLaneEditorControls();
                return;
            }

            timelineLaneEditIndex = Math.Max(0, removedIndex - 1);
            onLaneLayoutMutated($"Removed lane {removedIndex + 1}");
        }

        private void moveTimelineLane(int delta)
        {
            if (beatmap == null || delta == 0)
                return;

            if (!LaneManagement.IsLaneEditAllowed(LaneEditScope.Editor, LaneEditOperation.Reorder))
            {
                appendStatusDetail("Lane reorder is not allowed in this context.");
                return;
            }

            if (!tryGetEditableLanes(out var lanes))
                return;

            int fromIndex = timelineLaneEditIndex;
            int toIndex = Math.Clamp(fromIndex + delta, 0, lanes.Count - 1);
            if (toIndex == fromIndex)
                return;

            prepareUndoSnapshot();
            if (!LaneManagement.MoveLane(beatmap, fromIndex, toIndex))
            {
                appendStatusDetail("Lane move failed.");
                refreshTimelineLaneEditorControls();
                return;
            }

            timelineLaneEditIndex = toIndex;
            onLaneLayoutMutated($"Moved lane to position {toIndex + 1}");
        }

        private void onLaneLayoutMutated(string statusDetail)
        {
            if (beatmap == null)
                return;

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            reloadTimeline();
            markUnsaved();
            refreshUnsavedState();
            refreshTimelineToolboxState();
            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
            setStatusDetail(statusDetail);
        }

        private bool tryGetEditableLanes(out List<LaneInfo> lanes)
        {
            lanes = new List<LaneInfo>();
            if (beatmap == null)
                return false;

            lanes = LaneManagement.EnsureLaneLayout(beatmap);
            if (lanes.Count == 0)
                return false;

            timelineLaneEditIndex = Math.Clamp(timelineLaneEditIndex, 0, lanes.Count - 1);
            return true;
        }
    }
}
