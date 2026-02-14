using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void selectAllNotes()
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
            {
                appendStatusDetail("No notes available");
                return;
            }

            if (beatmap.HitObjects.Count == 1)
            {
                var onlyHit = beatmap.HitObjects[0];
                selectedHitObject = onlyHit;
                timeline?.TrySelectHitObject(onlyHit);
                seekToTime(onlyHit.Time);
                appendStatusDetail("Selected 1 note");
                return;
            }

            double start = beatmap.HitObjects.Min(hit => hit.Time);
            double end = beatmap.HitObjects.Max(hit => hit.Time);

            selectedHitObject = null;
            timeline?.SetSelectionRange(start, end);
            seekToTime(start);
            appendStatusDetail($"Selected all notes ({beatmap.HitObjects.Count})");
            updateSelectionSummary();
        }

        private void quantizeSelectedToGrid()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to quantize");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to quantize");
                return;
            }

            double interval = getSnapIntervalMs();
            int maxTime = trackLength > 0 ? (int)Math.Round(trackLength) : int.MaxValue;

            var changes = targets
                .Select(hit => new
                {
                    Hit = hit,
                    Snapped = (int)Math.Round(Math.Clamp(Math.Round(hit.Time / interval) * interval, 0, maxTime))
                })
                .Where(change => change.Snapped != change.Hit.Time)
                .ToList();

            if (changes.Count == 0)
            {
                appendStatusDetail($"Selection already quantized to 1/{snapDivisor}");
                return;
            }

            prepareUndoSnapshot();

            foreach (var change in changes)
                change.Hit.Time = change.Snapped;

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            seekToTime(targets.Min(hit => hit.Time));
            appendStatusDetail($"Quantized {changes.Count} note{(changes.Count == 1 ? string.Empty : "s")} to 1/{snapDivisor}");
        }

        private void snapSelectionToTransient()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to snap");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to snap");
                return;
            }

            if (timeline == null)
            {
                appendStatusDetail("Timeline unavailable");
                return;
            }

            if (!timeline.HasDetectedOnsets)
            {
                appendStatusDetail("No transient markers loaded");
                return;
            }

            int snappedCount = timeline.SnapSelectedNoteToTransient();
            if (snappedCount <= 0)
            {
                appendStatusDetail("No selected notes were close enough to transients");
                return;
            }

            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Snapped {snappedCount} note{(snappedCount == 1 ? string.Empty : "s")} to nearest transients");
        }

        private void adjustSelectedVelocity(bool increase)
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to adjust velocity");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to adjust velocity");
                return;
            }

            const double velocityStep = 0.05;
            double delta = increase ? velocityStep : -velocityStep;

            var changes = targets
                .Select(hit => new
                {
                    Hit = hit,
                    Adjusted = Math.Clamp(hit.Velocity + delta, 0.05, 1.0)
                })
                .Where(change => Math.Abs(change.Adjusted - change.Hit.Velocity) > 0.0001)
                .ToList();

            if (changes.Count == 0)
            {
                appendStatusDetail(increase ? "Velocity already at max" : "Velocity already at min");
                return;
            }

            prepareUndoSnapshot();

            foreach (var change in changes)
                change.Hit.Velocity = change.Adjusted;

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Adjusted velocity {(increase ? "up" : "down")} for {changes.Count} note{(changes.Count == 1 ? string.Empty : "s")}");
        }

        private void restoreSelectionAfterBatchEdit(IReadOnlyList<HitObject> targets, bool fromRange)
        {
            if (targets.Count == 1)
            {
                selectedHitObject = targets[0];
                timeline?.TrySelectHitObject(selectedHitObject);
                return;
            }

            selectedHitObject = null;

            if (!fromRange || targets.Count <= 1)
                return;

            double start = targets.Min(hit => hit.Time);
            double end = targets.Max(hit => hit.Time);
            timeline?.SetSelectionRange(start, end);
        }

        private void duplicateSelectedNote()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to duplicate");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out double rangeStart, out double rangeEnd);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to duplicate");
                return;
            }

            prepareUndoSnapshot();

            int maxTime = trackLength > 0 ? (int)Math.Round(trackLength) : int.MaxValue;
            int offsetMs = (int)Math.Round(getSnapIntervalMs());
            if (fromRange)
            {
                int rangeDuration = (int)Math.Round(Math.Max(0, rangeEnd - rangeStart));
                offsetMs = Math.Max(offsetMs, rangeDuration);
            }

            var clones = new List<HitObject>(targets.Count);
            foreach (var source in targets)
            {
                clones.Add(new HitObject
                {
                    Component = source.Component,
                    Lane = source.Lane,
                    Velocity = source.Velocity,
                    Duration = source.Duration,
                    Time = Math.Clamp(source.Time + offsetMs, 0, maxTime)
                });
            }

            beatmap.HitObjects.AddRange(clones);
            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(clones, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            seekToTime(clones.Min(clone => clone.Time));
            appendStatusDetail($"Duplicated {clones.Count} note{(clones.Count == 1 ? string.Empty : "s")}");
        }

        private void deleteSelectedNote()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to delete");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out double rangeStart, out double rangeEnd);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to delete");
                return;
            }

            prepareUndoSnapshot();

            var removalSet = new HashSet<HitObject>(targets);
            int removed = beatmap.HitObjects.RemoveAll(hit => removalSet.Contains(hit));
            if (removed <= 0)
            {
                appendStatusDetail("Unable to delete selected notes");
                return;
            }

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            selectedHitObject = null;
            markUnsaved();
            reloadTimeline();
            if (fromRange && removed > 1 && rangeEnd - rangeStart >= 1)
                timeline?.SetSelectionRange(rangeStart, rangeEnd);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Deleted {removed} note{(removed == 1 ? string.Empty : "s")}");
        }

        private void nudgeSelectedNote(bool forward)
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to nudge");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to nudge");
                return;
            }

            prepareUndoSnapshot();

            double delta = forward ? getSnapIntervalMs() : -getSnapIntervalMs();
            int maxTime = trackLength > 0 ? (int)Math.Round(trackLength) : int.MaxValue;

            foreach (var hit in targets)
                hit.Time = (int)Math.Round(Math.Clamp(hit.Time + delta, 0, maxTime));

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();

            if (targets.Count == 1)
            {
                selectedHitObject = targets[0];
                timeline?.RefreshHitObject(selectedHitObject);
                seekToTime(selectedHitObject.Time);
            }
            else
            {
                reloadTimeline();
                restoreSelectionAfterBatchEdit(targets, fromRange);
                seekToTime(targets.Min(hit => hit.Time));
            }

            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Nudged {targets.Count} note{(targets.Count == 1 ? string.Empty : "s")} {(forward ? "forward" : "backward")}");
        }
    }
}
