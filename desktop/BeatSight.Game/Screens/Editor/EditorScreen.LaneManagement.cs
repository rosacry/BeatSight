using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void refreshTimelineLaneEditorControls()
        {
            if (timelineLaneChipFlow == null
                || timelineLaneNameInput == null
                || timelineLaneShortNameInput == null
                || timelineLaneColorInput == null)
            {
                return;
            }

            // Lanes are the timeline rows (the playfield's lanes). Showing them never writes to the chart.
            int laneCount = beatmap == null || timeline == null ? 0 : timeline.LaneCount;
            if (laneCount <= 0)
            {
                timelineLaneChipFlow.Clear();
                lastLaneChipSignature = null;
                suppressLaneEditorFieldSync = true;
                timelineLaneNameInput.Current.Value = string.Empty;
                timelineLaneShortNameInput.Current.Value = string.Empty;
                timelineLaneColorInput.Current.Value = string.Empty;
                suppressLaneEditorFieldSync = false;
                return;
            }

            timelineLaneEditIndex = Math.Clamp(timelineLaneEditIndex, 0, laneCount - 1);

            var lanes = new List<LaneIdentity>(laneCount);
            for (int i = 0; i < laneCount; i++)
                lanes.Add(timeline!.DescribeLane(i));
            refreshTimelineLaneChips(lanes);

            int index = timelineLaneEditIndex;
            var automatic = timeline!.DescribeLane(index, includeCustomisations: false);
            bool customName = LaneManagement.TryGetLaneInfo(beatmap, index, out var info) && LaneManagement.IsCustomLaneName(info, index);
            bool customColour = LaneManagement.TryGetLaneColor(beatmap, index, out Color4 laneColour);

            // Empty fields show the automatic values as placeholders.
            suppressLaneEditorFieldSync = true;
            timelineLaneNameInput.PlaceholderText = automatic.Name;
            timelineLaneNameInput.Current.Value = customName ? info.Name ?? string.Empty : string.Empty;
            timelineLaneShortNameInput.PlaceholderText = automatic.ShortName;
            timelineLaneShortNameInput.Current.Value = customName ? info.ShortName ?? string.Empty : string.Empty;
            timelineLaneColorInput.PlaceholderText = LaneManagement.ToColorHex(automatic.Colour);
            timelineLaneColorInput.Current.Value = customColour ? LaneManagement.ToColorHex(laneColour) : string.Empty;
            suppressLaneEditorFieldSync = false;

            string? selectedHex = customColour ? LaneManagement.ToColorHex(laneColour) : null;
            timelineLaneAutoSwatch?.SetSelected(selectedHex == null);
            foreach (var swatch in timelineLaneSwatches)
                swatch.SetSelected(selectedHex != null && string.Equals(swatch.Hex, selectedHex, StringComparison.OrdinalIgnoreCase));

            timelineLaneRemoveButton?.FadeTo(laneCount > LaneManagement.MinLaneCount ? 1f : 0.45f, 120, Easing.OutQuint);
            timelineLaneAddButton?.FadeTo(laneCount < LaneManagement.MaxLaneCount ? 1f : 0.45f, 120, Easing.OutQuint);
            timelineLaneMoveLeftButton?.FadeTo(index > 0 ? 1f : 0.45f, 120, Easing.OutQuint);
            timelineLaneMoveRightButton?.FadeTo(index < laneCount - 1 ? 1f : 0.45f, 120, Easing.OutQuint);
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

            int index = timelineLaneEditIndex;
            string? laneName = emptyToNull(timelineLaneNameInput.Current.Value);
            string? laneShortName = emptyToNull(timelineLaneShortNameInput.Current.Value);
            string? laneColorText = emptyToNull(timelineLaneColorInput.Current.Value);

            // A short label alone still names the lane.
            if (laneName == null && laneShortName != null)
                laneName = laneShortName;

            Color4 parsedColor = default;
            if (laneColorText != null && !LaneManagement.TryParseColorHex(laneColorText, out parsedColor))
            {
                appendStatusDetail("Lane colour must be #RRGGBB.");
                refreshTimelineLaneEditorControls();
                return;
            }

            // Compare with what the lane shows now: its custom values, or automatic (null).
            bool hadCustomName = LaneManagement.TryGetLaneInfo(beatmap, index, out var info) && LaneManagement.IsCustomLaneName(info, index);
            string? currentName = hadCustomName ? info.Name : null;
            string? currentShort = hadCustomName ? emptyToNull(info.ShortName) : null;
            string? currentColour = LaneManagement.TryGetLaneColor(beatmap, index, out Color4 currentLaneColour)
                ? LaneManagement.ToColorHex(currentLaneColour)
                : null;
            string? targetColour = laneColorText != null ? LaneManagement.ToColorHex(parsedColor) : null;

            bool nameChanged = !string.Equals(currentName, laneName, StringComparison.Ordinal)
                               || (laneName != null && !string.Equals(currentShort, laneShortName, StringComparison.Ordinal));
            bool colourChanged = !string.Equals(currentColour, targetColour, StringComparison.OrdinalIgnoreCase);
            if (!nameChanged && !colourChanged)
            {
                refreshTimelineLaneEditorControls();
                return;
            }

            if (!tryGetEditableLanes(out _))
                return;

            prepareUndoSnapshot();

            // Null name/colour store the positional defaults, which every view reads as "automatic".
            if (nameChanged)
                LaneManagement.RenameLane(beatmap, index, laneName, laneShortName);
            if (colourChanged)
                LaneManagement.RecolorLane(beatmap, index, targetColour != null ? parsedColor : DrumPalette.ForLane(index));

            onLaneLayoutMutated($"Updated lane {index + 1}");

            static string? emptyToNull(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();
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

            if (!tryGetEditableLanes(out _))
                return;

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

            // Editing writes lane entries for every row the timeline shows (the playfield's lane count).
            lanes = LaneManagement.EnsureLaneLayout(beatmap, timeline?.LaneCount ?? 7);
            if (lanes.Count == 0)
                return false;

            timelineLaneEditIndex = Math.Clamp(timelineLaneEditIndex, 0, lanes.Count - 1);
            return true;
        }
    }
}
