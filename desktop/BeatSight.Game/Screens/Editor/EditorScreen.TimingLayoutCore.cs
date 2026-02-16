using System;
using System.Linq;
using osu.Framework.Graphics.Containers;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private double getSnapIntervalMs()
        {
            if (beatmap == null || beatmap.Timing.Bpm <= 0 || snapDivisor <= 0)
                return 100;

            return 60000.0 / beatmap.Timing.Bpm / snapDivisor;
        }

        private double resolvePreferredStartTime(out string? startContextDetail)
        {
            startContextDetail = null;

            if (beatmap == null)
                return 0;

            double duration = trackLength > 0
                ? trackLength
                : Math.Max(beatmap.Audio.Duration, beatmap.HitObjects.Count > 0 ? beatmap.HitObjects[^1].Time + 2000 : 0);

            if (beatmap.HitObjects.Count == 0)
            {
                if (beatmap.Metadata.PreviewTime.HasValue && beatmap.Metadata.PreviewTime.Value > 0)
                    return Math.Clamp(beatmap.Metadata.PreviewTime.Value, 0, duration > 0 ? duration : beatmap.Metadata.PreviewTime.Value);

                return 0;
            }

            int firstHit = beatmap.HitObjects.Min(h => h.Time);
            double firstHitStart = Math.Clamp(firstHit - firstNoteLeadInMs, 0, duration > 0 ? duration : firstHit);

            if (beatmap.Metadata.PreviewTime.HasValue && beatmap.Metadata.PreviewTime.Value > 0)
            {
                double previewStart = Math.Clamp(beatmap.Metadata.PreviewTime.Value, 0, duration > 0 ? duration : beatmap.Metadata.PreviewTime.Value);
                bool hasNearbyNotes = beatmap.HitObjects.Any(hit =>
                    hit.Time >= previewStart - previewStartLookBehindMs
                    && hit.Time <= previewStart + previewStartLookAheadMs);

                if (hasNearbyNotes)
                    return previewStart;

                if (Math.Abs(firstHitStart - previewStart) > 1)
                    startContextDetail = $"Preview moved to first note context ({formatTime(firstHit)})";

                return firstHitStart;
            }

            return firstHitStart;
        }

        private double getEffectivePlaybackLength()
        {
            if (trackLength > 0)
                return trackLength;

            if (beatmap == null)
                return 0;

            double metadataDuration = Math.Max(0, beatmap.Audio.Duration);
            double lastNoteDuration = beatmap.HitObjects.Count > 0
                ? beatmap.HitObjects.Max(hit => (double)hit.Time) + 2000
                : 0;

            return Math.Max(metadataDuration, lastNoteDuration);
        }

        private void seekToTime(double timeMs)
        {
            double effectiveLength = getEffectivePlaybackLength();
            double target = Math.Clamp(timeMs, 0, effectiveLength > 0 ? effectiveLength : Math.Max(timeMs, 0));
            currentTime = target;
            track?.Seek(target);
            lastTrackTime = track?.CurrentTime ?? target;
            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);
            playbackPreview?.JumpToTime(currentTime);
        }

        private void refreshInspectorActionLabelWidths()
        {
            foreach (var layout in inspectorActionLayouts)
            {
                float buttonWidth = layout.FillWidth ? layout.Button.DrawWidth : layout.WidthHint;
                if (buttonWidth <= 1f && layout.Button.Parent != null)
                    buttonWidth = layout.Button.Parent.DrawWidth;

                float targetMaxWidth = Math.Max(24f, buttonWidth - 14f);
                if (Math.Abs(layout.Label.MaxWidth - targetMaxWidth) > 0.2f)
                    layout.Label.MaxWidth = targetMaxWidth;
            }
        }

        private void applyResponsiveEditorLayout(bool force = false)
        {
            var viewport = resolveResponsiveViewport();
            if (viewport.X <= 0 || viewport.Y <= 0)
                return;

            var metrics = EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout, footerTipsCollapsed);
            bool inspectorCollapsedBeforeAdjustment = inspectorCollapsed;

            bool inspectorWidthChanged = lastInspectorWidth < 0 || Math.Abs(metrics.InspectorWidth - lastInspectorWidth) > 0.2f;
            bool stackedInspectorHeightChanged = lastStackedInspectorHeight < 0 || Math.Abs(metrics.StackedInspectorHeight - lastStackedInspectorHeight) > 0.2f;
            bool panelGapChanged = lastPanelGap < 0 || Math.Abs(metrics.PanelGap - lastPanelGap) > 0.2f;
            bool stackedModeChanged = metrics.UseStackedInspector != inspectorStackedLayout;
            bool collapsedStateChanged = inspectorCollapsedBeforeAdjustment != inspectorCollapsed;

            if (timelineLayoutGrid != null && (force || lastTimelineToolboxHeight < 0 || Math.Abs(metrics.TimelineToolboxHeight - lastTimelineToolboxHeight) > 0.2f))
            {
                timelineLayoutGrid.RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, metrics.TimelineToolboxHeight),
                    new Dimension()
                };
                lastTimelineToolboxHeight = metrics.TimelineToolboxHeight;
            }

            if (editorLayoutGrid != null && (force || lastTimelineSurfaceHeight < 0 || Math.Abs(metrics.TimelineTopHeight - lastTimelineSurfaceHeight) > 0.2f))
            {
                editorLayoutGrid.RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, metrics.TimelineTopHeight),
                    new Dimension()
                };
                lastTimelineSurfaceHeight = metrics.TimelineTopHeight;
            }

            if (screenLayoutGrid != null && (force || lastFooterHeight < 0 || Math.Abs(metrics.FooterHeight - lastFooterHeight) > 0.2f))
            {
                screenLayoutGrid.RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize),
                    new Dimension(),
                    new Dimension(GridSizeMode.Absolute, metrics.FooterHeight)
                };
                lastFooterHeight = metrics.FooterHeight;
            }

            if (previewInspectorGrid != null
                && previewCellContainer != null
                && inspectorContainer != null
                && (force || inspectorWidthChanged || stackedInspectorHeightChanged || panelGapChanged || stackedModeChanged || collapsedStateChanged))
            {
                applyPreviewInspectorLayout(metrics);
            }

            applyCompactEditorDensity(metrics, viewport, force);
            updateInspectorToggle(metrics, viewport);
        }
    }
}
