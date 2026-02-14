using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Playback.Playfield.Views;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void reassignSelectedComponent()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to reassign");
                return;
            }

            string targetComponent = componentReassignSelection.Value?.Trim() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(targetComponent))
            {
                appendStatusDetail("Choose an instrument type first");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to reassign");
                return;
            }

            int pendingChanges = targets.Count(hit =>
                !string.Equals(hit.Component, targetComponent, StringComparison.OrdinalIgnoreCase)
                || hit.Lane.HasValue);

            if (pendingChanges == 0)
            {
                appendStatusDetail($"Selection already uses {targetComponent}");
                return;
            }

            prepareUndoSnapshot();

            foreach (var hit in targets)
            {
                hit.Component = targetComponent;
                // Let playback/editor lane heuristics re-resolve from the updated component.
                hit.Lane = null;
            }

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);

            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Reassigned {targets.Count} note{(targets.Count == 1 ? string.Empty : "s")} to {targetComponent}");
        }

        private void shiftSelectionToAdjacentNotationLane(bool towardHigher)
        {
            if (previewMode?.Value != EditorPreviewMode.Manuscript)
            {
                appendStatusDetail("Switch to Sheet Music view to use notation lane shift");
                return;
            }

            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to move");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to move");
                return;
            }

            int direction = towardHigher ? 1 : -1;
            int changed = 0;

            prepareUndoSnapshot();

            foreach (var hit in targets)
            {
                string nextComponent = ManuscriptBackgroundEnhanced.GetAdjacentNotationComponent(hit.Component, direction);
                if (string.Equals(hit.Component, nextComponent, StringComparison.OrdinalIgnoreCase) && !hit.Lane.HasValue)
                    continue;

                hit.Component = nextComponent;
                // Let lane heuristics remap to the current lane layout.
                hit.Lane = null;
                changed++;
            }

            if (changed == 0)
            {
                appendStatusDetail(towardHigher
                    ? "Selection already at highest notation lane"
                    : "Selection already at lowest notation lane");
                return;
            }

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Moved {changed} note{(changed == 1 ? string.Empty : "s")} {(towardHigher ? "up" : "down")} in sheet notation");
        }

        private void applyNotationArticulationPreset(NotationArticulationPreset preset)
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to set articulation");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to set articulation");
                return;
            }

            double targetVelocity = getNotationVelocityForPreset(preset);
            var changes = targets
                .Where(hit => Math.Abs(hit.Velocity - targetVelocity) > 0.0001)
                .ToList();

            if (changes.Count == 0)
            {
                appendStatusDetail($"Selection already set to {getNotationPresetLabel(preset)} articulation");
                return;
            }

            prepareUndoSnapshot();

            foreach (var hit in changes)
                hit.Velocity = targetVelocity;

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Set {changes.Count} note{(changes.Count == 1 ? string.Empty : "s")} to {getNotationPresetLabel(preset)} articulation");
        }

        private void cycleNotationArticulationPreset(bool towardAccent)
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to shift articulation");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to shift articulation");
                return;
            }

            int direction = towardAccent ? 1 : -1;
            var changes = new List<(HitObject Hit, NotationArticulationPreset Preset, double Velocity)>(targets.Count);

            foreach (var hit in targets)
            {
                var currentPreset = getNotationPresetFromVelocity(hit.Velocity);
                int nextIndex = Math.Clamp((int)currentPreset + direction, 0, 2);
                var nextPreset = (NotationArticulationPreset)nextIndex;
                double nextVelocity = getNotationVelocityForPreset(nextPreset);
                if (Math.Abs(nextVelocity - hit.Velocity) <= 0.0001)
                    continue;

                changes.Add((hit, nextPreset, nextVelocity));
            }

            if (changes.Count == 0)
            {
                appendStatusDetail(towardAccent
                    ? "Selection already at accent articulation"
                    : "Selection already at ghost articulation");
                return;
            }

            prepareUndoSnapshot();

            foreach (var change in changes)
                change.Hit.Velocity = change.Velocity;

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Shifted articulation {(towardAccent ? "up" : "down")} for {changes.Count} note{(changes.Count == 1 ? string.Empty : "s")}");
        }

        private static NotationArticulationPreset getNotationPresetFromVelocity(double velocity)
        {
            if (velocity <= (notationGhostVelocity + notationNormalVelocity) * 0.5)
                return NotationArticulationPreset.Ghost;

            if (velocity >= (notationNormalVelocity + notationAccentVelocity) * 0.5)
                return NotationArticulationPreset.Accent;

            return NotationArticulationPreset.Normal;
        }

        private static double getNotationVelocityForPreset(NotationArticulationPreset preset)
        {
            return preset switch
            {
                NotationArticulationPreset.Ghost => notationGhostVelocity,
                NotationArticulationPreset.Accent => notationAccentVelocity,
                _ => notationNormalVelocity
            };
        }

        private static string getNotationPresetLabel(NotationArticulationPreset preset)
        {
            return preset switch
            {
                NotationArticulationPreset.Ghost => "ghost",
                NotationArticulationPreset.Accent => "accent",
                _ => "normal"
            };
        }
    }
}
