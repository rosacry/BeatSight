using System;
using System.Globalization;
using System.Linq;
using BeatSight.Game.Beatmaps;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void adjustBpmByFactor(double factor)
        {
            if (beatmap == null)
                return;

            setBpm(beatmap.Timing.Bpm * factor);
            suppressInspectorFieldSync = true;
            bpmInput.Current.Value = beatmap.Timing.Bpm.ToString("0.##", CultureInfo.InvariantCulture);
            suppressInspectorFieldSync = false;
        }

        private void resetBpmToDefault()
        {
            double target = initialBeatmapBpm ?? TimingInfo.DefaultBpm;
            setBpm(target);
            suppressInspectorFieldSync = true;
            bpmInput.Current.Value = target.ToString("0.##", CultureInfo.InvariantCulture);
            suppressInspectorFieldSync = false;
        }

        private void jumpToFirstNote()
            => jumpToBoundaryNote(forward: true);

        private void jumpToLastNote()
            => jumpToBoundaryNote(forward: false);

        private void jumpToBoundaryNote(bool forward)
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
            {
                appendStatusDetail("No notes available");
                return;
            }

            var target = forward
                ? beatmap.HitObjects.MinBy(hit => hit.Time)
                : beatmap.HitObjects.MaxBy(hit => hit.Time);

            if (target == null)
            {
                appendStatusDetail("No notes available");
                return;
            }

            if (timeline?.TrySelectHitObject(target) != true)
                onTimelineNoteSelected(target);

            seekToTime(target.Time);
            appendStatusDetail(forward ? $"Jumped to first note ({formatTime(target.Time)})" : $"Jumped to last note ({formatTime(target.Time)})");
        }

        private void jumpToAdjacentNote(bool forward)
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
            {
                appendStatusDetail("No notes available");
                return;
            }

            int index = selectedHitObject != null ? beatmap.HitObjects.IndexOf(selectedHitObject) : -1;
            if (index < 0)
            {
                index = beatmap.HitObjects.FindLastIndex(h => h.Time <= currentTime);
            }

            if (index < 0)
                index = forward ? 0 : beatmap.HitObjects.Count - 1;
            else
                index = Math.Clamp(index + (forward ? 1 : -1), 0, beatmap.HitObjects.Count - 1);

            var target = beatmap.HitObjects[index];
            if (timeline?.TrySelectHitObject(target) != true)
                onTimelineNoteSelected(target);

            seekToTime(target.Time);
        }

        private void centerOnSelection()
        {
            if (selectedHitObject != null)
            {
                if (timeline?.TrySelectHitObject(selectedHitObject) != true)
                    seekToTime(selectedHitObject.Time);
                return;
            }

            if (tryGetSelectionRange(out double start, out double end))
            {
                seekToTime((start + end) / 2.0);
                appendStatusDetail("Centered on selection range");
                return;
            }

            appendStatusDetail("No selection to center");
        }
    }
}
