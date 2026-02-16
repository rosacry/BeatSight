using System;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using osu.Framework.Bindables;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void applyEditorDefaultsFromConfig()
        {
            if (editorTimelineZoomDefault != null)
                timelineZoom = Math.Clamp(editorTimelineZoomDefault.Value, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);

            if (editorWaveformScaleDefault != null)
                waveformScale = Math.Clamp(editorWaveformScaleDefault.Value, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);

            if (editorBeatGridVisibleDefault != null)
                beatGridVisible = editorBeatGridVisibleDefault.Value;
        }

        private void persistEditorDefaults()
        {
            if (suppressEditorDefaultPersistence)
                return;

            if (editorTimelineZoomDefault != null)
                editorTimelineZoomDefault.Value = timelineZoom;

            if (editorWaveformScaleDefault != null)
                editorWaveformScaleDefault.Value = waveformScale;

            if (editorBeatGridVisibleDefault != null)
                editorBeatGridVisibleDefault.Value = beatGridVisible;
        }

        private void onTimelineSeekRequested(double timeMs)
        {
            double target = Math.Clamp(timeMs, 0, trackLength > 0 ? trackLength : Math.Max(0, timeMs));
            seekToTime(target);
            if (isPlaying && track != null && !track.IsRunning)
                track.Start();
        }

        private void onTimelineNoteSelected(HitObject hit)
        {
            selectedHitObject = hit;
            setStatusDetail($"Selected {hit.Component} @ {formatTime(hit.Time)}");
            updateSelectionSummary();
            seekToTime(hit.Time);
        }

        private void onTimelineSelectionChanged(double? start, double? end)
        {
            if (start.HasValue && end.HasValue && Math.Abs(end.Value - start.Value) >= 1)
                selectedHitObject = null;

            updateSelectionSummary();
        }

        private void onTimelineNoteChanged(HitObject hit)
        {
            if (beatmap == null)
                return;

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            playbackPreview?.RefreshBeatmap();
            markUnsaved();
            refreshUnsavedState();

            if (selectedHitObject != null && !beatmap.HitObjects.Contains(selectedHitObject))
                selectedHitObject = null;

            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
        }

        private void onTimelineEditBegan()
            => prepareUndoSnapshot();

        private void onTimelineZoomChanged(double zoom)
            => applyTimelineZoom(zoom);

        private void onTimelineSnapDivisorChanged(int divisor)
        {
            if (divisor <= 0)
                return;

            applySnapDivisor(divisor);
        }

        private void onPreviewNotePlacementRequested(int lane, double timeMs)
        {
            if (beatmap == null || timeline == null)
                return;

            if (!timeline.TryAddHitObjectAtTimeAndLane(timeMs, lane))
                return;

            string laneLabel = getLaneLabelForStatus(lane);
            setStatusDetail($"Added {laneLabel} @ {formatTime(timeMs)}");
            if (!isPlaying)
                seekToTime(timeMs);
        }

        private void onPreviewNoteRemovalRequested(int lane, double timeMs)
        {
            if (beatmap == null || timeline == null)
                return;

            if (!timeline.TryDeleteNearestHitObject(timeMs, lane))
            {
                appendStatusDetail($"No note near {getLaneLabelForStatus(lane)} @ {formatTime(timeMs)}");
                return;
            }

            setStatusDetail($"Removed nearest {getLaneLabelForStatus(lane)} note @ {formatTime(timeMs)}");
            if (!isPlaying)
                seekToTime(timeMs);
        }

        private string getLaneLabelForStatus(int lane)
        {
            string? component = timeline?.GetLaneComponentForVisibleLane(lane);
            if (string.IsNullOrWhiteSpace(component))
                return $"lane {lane + 1}";

            return formatComponentDisplayName(component);
        }

        private void onPreviewModeChanged(ValueChangedEvent<EditorPreviewMode> mode)
        {
            switch (mode.NewValue)
            {
                case EditorPreviewMode.Playfield2D:
                    laneViewModeBindable.Value = LaneViewMode.TwoDimensional;
                    setStatusDetail("2D view");
                    break;

                case EditorPreviewMode.Manuscript:
                    laneViewModeBindable.Value = LaneViewMode.Manuscript;
                    setStatusDetail("Sheet Music view");
                    break;

                case EditorPreviewMode.Playfield3D:
                default:
                    laneViewModeBindable.Value = LaneViewMode.ThreeDimensional;
                    setStatusDetail("3D view");
                    break;
            }

            syncManuscriptFocus();
        }

        private void onLaneViewModeChanged(ValueChangedEvent<LaneViewMode> change)
        {
            switch (change.NewValue)
            {
                case LaneViewMode.TwoDimensional:
                    if (previewMode.Value != EditorPreviewMode.Playfield2D)
                        previewMode.Value = EditorPreviewMode.Playfield2D;
                    break;
                case LaneViewMode.ThreeDimensional:
                    if (previewMode.Value != EditorPreviewMode.Playfield3D)
                        previewMode.Value = EditorPreviewMode.Playfield3D;
                    break;
                case LaneViewMode.Manuscript:
                    if (previewMode.Value != EditorPreviewMode.Manuscript)
                        previewMode.Value = EditorPreviewMode.Manuscript;
                    break;
            }

            if (playbackPreview != null)
                Schedule(() => playbackPreview.RefreshBeatmap());

            syncManuscriptFocus();
        }
    }
}
