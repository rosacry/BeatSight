using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void updateSelectionSummary()
        {
            syncManuscriptFocus();

            if (selectionSummaryText == null)
                return;

            string noSelectionText = EditorInspectorCopy.Active.SelectionNoneText;

            if (selectedHitObject != null)
            {
                string laneText = selectedHitObject.Lane.HasValue ? (selectedHitObject.Lane.Value + 1).ToString() : "?";
                string articulation = getNotationPresetLabel(getNotationPresetFromVelocity(selectedHitObject.Velocity));
                selectionSummaryText.Text = $"{selectedHitObject.Component} | Lane {laneText} | {articulation} @ {formatTime(selectedHitObject.Time)}";
                selectionSummaryText.Colour = EditorColours.TextPrimary;
                return;
            }

            if (tryGetSelectionRange(out double start, out double end))
            {
                int noteCount = beatmap?.HitObjects.Count(hit => hit.Time >= start && hit.Time <= end) ?? 0;
                selectionSummaryText.Text = noteCount > 0
                    ? $"{noteCount} notes in range {formatTime(start)} - {formatTime(end)}"
                    : $"Range {formatTime(start)} - {formatTime(end)} (no notes)";
                selectionSummaryText.Colour = noteCount > 0 ? EditorColours.TextPrimary : EditorColours.TextSecondary;
                return;
            }

            if (beatmap?.HitObjects.Count > 0)
            {
                var nextHit = beatmap.HitObjects
                    .Where(hit => hit.Time >= currentTime)
                    .OrderBy(hit => hit.Time)
                    .FirstOrDefault();

                if (nextHit != null)
                {
                    selectionSummaryText.Text = $"{noSelectionText} | Next @ {formatTime(nextHit.Time)}";
                    selectionSummaryText.Colour = EditorColours.TextSecondary;
                    return;
                }

                int lastHit = beatmap.HitObjects.Max(hit => hit.Time);
                selectionSummaryText.Text = $"{noSelectionText} | Past final note ({formatTime(lastHit)})";
                selectionSummaryText.Colour = EditorColours.TextSecondary;
                return;
            }

            selectionSummaryText.Text = noSelectionText;
            selectionSummaryText.Colour = EditorColours.TextSecondary;
        }

        private void syncManuscriptFocus()
        {
            if (playbackPreview == null || previewMode == null)
                return;

            if (previewMode.Value != EditorPreviewMode.Manuscript)
            {
                playbackPreview.SetManuscriptFocusComponent(null);
                return;
            }

            if (selectedHitObject != null)
            {
                playbackPreview.SetManuscriptFocusComponent(selectedHitObject.Component);
                return;
            }

            if (tryGetSelectionRange(out double start, out double end))
            {
                string? selectionComponent = resolveSelectionFocusComponent(start, end);
                playbackPreview.SetManuscriptFocusComponent(selectionComponent);
                return;
            }

            string? nextComponent = beatmap?.HitObjects
                .Where(hit => hit.Time >= currentTime)
                .OrderBy(hit => hit.Time)
                .Select(hit => hit.Component)
                .FirstOrDefault();

            playbackPreview.SetManuscriptFocusComponent(nextComponent);
        }

        private string? resolveSelectionFocusComponent(double start, double end)
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
                return null;

            var selectionHits = beatmap.HitObjects
                .Where(hit => hit.Time >= start && hit.Time <= end)
                .ToList();

            if (selectionHits.Count == 0)
                return null;

            return selectionHits
                .OrderBy(hit => Math.Abs(hit.Time - currentTime))
                .Select(hit => hit.Component)
                .FirstOrDefault();
        }

        private bool tryGetSelectionRange(out double start, out double end)
        {
            start = 0;
            end = 0;

            if (timeline?.SelectionStart is not double selectionStart || timeline.SelectionEnd is not double selectionEnd)
                return false;

            start = Math.Min(selectionStart, selectionEnd);
            end = Math.Max(selectionStart, selectionEnd);
            return end - start >= 1;
        }

        private List<HitObject> getSelectedHitObjectsForEditing(out bool fromRange, out double rangeStart, out double rangeEnd)
        {
            fromRange = false;
            rangeStart = 0;
            rangeEnd = 0;

            if (beatmap == null)
                return new List<HitObject>();

            if (selectedHitObject != null && beatmap.HitObjects.Contains(selectedHitObject))
                return new List<HitObject> { selectedHitObject };

            if (tryGetSelectionRange(out rangeStart, out rangeEnd))
            {
                fromRange = true;
                double start = rangeStart;
                double end = rangeEnd;
                return beatmap.HitObjects
                    .Where(hit => hit.Time >= start && hit.Time <= end)
                    .OrderBy(hit => hit.Time)
                    .ToList();
            }

            return new List<HitObject>();
        }

        private void refreshComponentReassignmentOptions()
        {
            if (componentReassignDropdown == null)
                return;

            var options = new List<string>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            void addOption(string? component)
            {
                if (string.IsNullOrWhiteSpace(component))
                    return;

                string normalized = component.Trim();
                if (seen.Add(normalized))
                    options.Add(normalized);
            }

            foreach (string component in defaultComponentReassignmentOptions)
                addOption(component);

            if (beatmap?.DrumKit?.Components != null)
            {
                foreach (string component in beatmap.DrumKit.Components)
                    addOption(component);
            }

            if (beatmap != null)
            {
                foreach (string component in beatmap.HitObjects.Select(hit => hit.Component))
                    addOption(component);
            }

            if (options.Count == 0)
                options.Add("kick");

            componentReassignDropdown.Items = options.ToArray();

            string currentSelection = componentReassignSelection.Value ?? string.Empty;
            string? resolvedSelection = options.FirstOrDefault(option => string.Equals(option, currentSelection, StringComparison.OrdinalIgnoreCase));
            componentReassignSelection.Value = resolvedSelection ?? options[0];
        }
    }
}
