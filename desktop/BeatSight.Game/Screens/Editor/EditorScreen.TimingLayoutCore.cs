using System;
using System.Diagnostics;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics.Containers;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private double getSnapIntervalMs(double? referenceTimeMs = null)
        {
            var timing = resolveTimelineTimingAt(referenceTimeMs ?? currentTime);
            if (timing.Bpm <= 0 || !double.IsFinite(timing.Bpm) || snapDivisor <= 0)
                return 100;

            double beatUnitDuration = 60000.0 / timing.Bpm * (4.0 / Math.Max(1.0, timing.BeatUnitDenominator));
            return beatUnitDuration / snapDivisor;
        }

        private double getSnapOriginMs(double? referenceTimeMs = null)
            => resolveTimelineTimingAt(referenceTimeMs ?? currentTime).SnapOriginMs;

        private (double Bpm, double SnapOriginMs, int BeatsPerMeasure, int BeatUnitDenominator) resolveTimelineTimingAt(double referenceTimeMs)
        {
            if (beatmap == null)
                return (double.NaN, 0, 4, 4);

            double bpm = beatmap.Timing.Bpm;
            double snapOriginMs = beatmap.Timing.Offset;
            string? timeSignature = beatmap.Timing.TimeSignature;

            var timingPoints = beatmap.Timing.TimingPoints;
            if (timingPoints != null && timingPoints.Count > 0)
            {
                int targetMs = (int)Math.Round(referenceTimeMs);
                TimingPoint? activePoint = null;

                foreach (var point in timingPoints.OrderBy(point => point.Time))
                {
                    if (point.Time > targetMs)
                        break;

                    activePoint = point;
                }

                if (activePoint is not null)
                {
                    if (activePoint.Bpm > 0 && double.IsFinite(activePoint.Bpm))
                        bpm = activePoint.Bpm;

                    snapOriginMs = activePoint.Time;

                    if (!string.IsNullOrWhiteSpace(activePoint.TimeSignature))
                        timeSignature = activePoint.TimeSignature;
                }
            }

            int beatsPerMeasure = parseBeatsPerMeasure(timeSignature, fallback: 4);
            int beatUnitDenominator = parseBeatUnitDenominator(timeSignature, fallback: 4);
            return (bpm, snapOriginMs, beatsPerMeasure, beatUnitDenominator);
        }

        private static int parseBeatsPerMeasure(string? timeSignature, int fallback)
        {
            if (string.IsNullOrWhiteSpace(timeSignature))
                return fallback;

            string[] parts = timeSignature.Split('/');
            if (parts.Length <= 0)
                return fallback;

            if (!int.TryParse(parts[0], out int numerator))
                return fallback;

            return Math.Clamp(numerator, 1, 32);
        }

        private static int parseBeatUnitDenominator(string? timeSignature, int fallback)
        {
            if (string.IsNullOrWhiteSpace(timeSignature))
                return fallback;

            string[] parts = timeSignature.Split('/');
            if (parts.Length < 2)
                return fallback;

            if (!int.TryParse(parts[1], out int denominator))
                return fallback;

            return Math.Clamp(denominator, 1, 32);
        }

        private void syncTimelineSnapForCurrentTime(bool force = false)
        {
            if (timeline == null)
                return;

            var timing = resolveTimelineTimingAt(currentTime);
            bool hasValidBpm = timing.Bpm > 0 && double.IsFinite(timing.Bpm);
            int effectiveDivisor = hasValidBpm ? snapDivisor : 0;
            double effectiveBpm = hasValidBpm ? timing.Bpm : double.NaN;
            double effectiveOrigin = timing.SnapOriginMs;
            int effectiveBeatsPerMeasure = timing.BeatsPerMeasure;
            int effectiveBeatUnitDenominator = timing.BeatUnitDenominator;

            if (!force
                && effectiveDivisor == lastTimelineSnapDivisor
                && Math.Abs(effectiveBpm - lastTimelineSnapBpm) <= 0.0001
                && Math.Abs(effectiveOrigin - lastTimelineSnapOrigin) <= 0.0001
                && effectiveBeatsPerMeasure == lastTimelineBeatsPerMeasure
                && effectiveBeatUnitDenominator == lastTimelineBeatUnitDenominator)
            {
                return;
            }

            timeline.SetSnap(effectiveDivisor, effectiveBpm, effectiveOrigin, effectiveBeatsPerMeasure, effectiveBeatUnitDenominator);
            lastTimelineSnapDivisor = effectiveDivisor;
            lastTimelineSnapBpm = effectiveBpm;
            lastTimelineSnapOrigin = effectiveOrigin;
            lastTimelineBeatsPerMeasure = effectiveBeatsPerMeasure;
            lastTimelineBeatUnitDenominator = effectiveBeatUnitDenominator;
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

        private double clampSeekTarget(double timeMs)
        {
            double effectiveLength = getEffectivePlaybackLength();
            return Math.Clamp(timeMs, 0, effectiveLength > 0 ? effectiveLength : Math.Max(timeMs, 0));
        }

        private double quantizeTimeToSnapGrid(double timeMs, bool onlyWhenBeatGridVisible = true)
        {
            double clamped = clampSeekTarget(timeMs);
            if (onlyWhenBeatGridVisible && !beatGridVisible)
                return clamped;

            double snapInterval = Math.Max(0, getSnapIntervalMs(clamped));
            if (!double.IsFinite(snapInterval) || snapInterval <= 0.01)
                return clamped;

            double snapOrigin = getSnapOriginMs(clamped);
            double snapped = Math.Round((clamped - snapOrigin) / snapInterval) * snapInterval + snapOrigin;
            return clampSeekTarget(snapped);
        }

        private void seekToTime(double timeMs)
            => seekToTimeWithOptions(timeMs, ensureTimelineVisible: true, syncTrack: true, syncPreview: true);

        private void seekToTimeWithOptions(
            double timeMs,
            bool ensureTimelineVisible,
            bool syncTrack,
            bool syncPreview,
            SeekInputSource source = SeekInputSource.Programmatic)
        {
            double target = clampSeekTarget(timeMs);
            currentTime = target;
            if (isPlaying)
                resetEditorMetronomeTracking(suppressUntilNextBeat: true);

            if (syncTrack && track != null)
            {
                if (Math.Abs(track.CurrentTime - target) > 1.5)
                    track.Seek(target);

                lastTrackTime = track.CurrentTime;
            }
            else
            {
                lastTrackTime = track?.CurrentTime ?? target;
            }

            timeText.Text = formatTime(currentTime);
            if (timeline != null)
            {
                syncTimelineSnapForCurrentTime();
                timeline.SetCurrentTime(currentTime, ensureVisible: ensureTimelineVisible);
                lastTimelineSyncedTime = currentTime;
            }

            if (syncPreview)
            {
                bool lightweightPreviewSeek = source == SeekInputSource.Wheel
                    || source == SeekInputSource.SeekBar
                    || source == SeekInputSource.Timeline;
                playbackPreview?.JumpToTime(currentTime, lightweightPreviewSeek);
            }

            syncFooterSeekBar();
        }

        private void queueSeekToTime(
            double timeMs,
            bool ensureTimelineVisible = false,
            bool syncTrack = true,
            bool syncPreview = true,
            SeekInputSource source = SeekInputSource.Programmatic,
            double inputDelta = 0)
        {
            pendingSeekTimeMs = clampSeekTarget(timeMs);
            pendingSeekEnsureVisible |= ensureTimelineVisible;
            pendingSeekSyncTrack |= syncTrack;
            pendingSeekSyncPreview |= syncPreview;
            pendingSeekSource = source;
            registerScrubSeekRequest(source, inputDelta);

            if (seekDispatchScheduled)
                return;

            seekDispatchScheduled = true;
            Scheduler.AddOnce(flushQueuedSeek);
        }

        private void flushQueuedSeek()
        {
            seekDispatchScheduled = false;

            if (!pendingSeekTimeMs.HasValue)
                return;

            double target = pendingSeekTimeMs.Value;
            bool ensureVisible = pendingSeekEnsureVisible;
            bool syncTrack = pendingSeekSyncTrack;
            bool syncPreview = pendingSeekSyncPreview;
            SeekInputSource source = pendingSeekSource;

            pendingSeekTimeMs = null;
            pendingSeekEnsureVisible = false;
            pendingSeekSyncTrack = false;
            pendingSeekSyncPreview = false;
            pendingSeekSource = SeekInputSource.Programmatic;

            var stopwatch = Stopwatch.StartNew();
            seekToTimeWithOptions(target, ensureVisible, syncTrack, syncPreview, source);
            stopwatch.Stop();
            recordScrubSeekFlush(source, stopwatch.Elapsed.TotalMilliseconds);
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

            bool toolboxCollapseChanged = timelineToolboxCollapsed != lastTimelineToolboxCollapsedState;

            if (timelineLayoutGrid != null
                && (force
                    || toolboxCollapseChanged
                    || lastTimelineToolboxHeight < 0
                    || Math.Abs(metrics.TimelineToolboxHeight - lastTimelineToolboxHeight) > 0.2f))
            {
                // Keep the toolbox row autosized. Collapse/expand animation is handled by
                // the host container height animation to avoid abrupt clipping.
                timelineLayoutGrid.RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize),
                    new Dimension()
                };
                lastTimelineToolboxHeight = metrics.TimelineToolboxHeight;
                lastTimelineToolboxCollapsedState = timelineToolboxCollapsed;
            }

            float resolvedTopHeight = resolveTimelineTopHeight(metrics, viewport);
            if (timelineTopHeightOverride.HasValue && Math.Abs(timelineTopHeightOverride.Value - resolvedTopHeight) > 0.2f)
                timelineTopHeightOverride = resolvedTopHeight;

            if (editorLayoutGrid != null && (force || lastTimelineSurfaceHeight < 0 || Math.Abs(resolvedTopHeight - lastTimelineSurfaceHeight) > 0.2f))
            {
                editorLayoutGrid.RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, resolvedTopHeight),
                    new Dimension(GridSizeMode.Absolute, timelinePreviewSplitterHeight),
                    new Dimension()
                };
                lastTimelineSurfaceHeight = resolvedTopHeight;
            }

            if (editorWorkspaceGrid != null && (force || lastFooterHeight < 0 || Math.Abs(metrics.FooterHeight - lastFooterHeight) > 0.2f))
            {
                editorWorkspaceGrid.RowDimensions = new[]
                {
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
            syncTimelineToolboxHostHeightToContent();
            updateInspectorToggle(metrics, viewport);
        }

        private float resolveTimelineTopHeight(EditorResponsiveLayoutMetrics metrics, Vector2 viewport)
        {
            float minTopHeight = resolveTimelineTopMinimumHeight(metrics, viewport, timelineToolboxCollapsed);
            float totalHeight = editorLayoutGrid?.DrawHeight > 0 ? editorLayoutGrid.DrawHeight : viewport.Y;
            float minimumPreviewHeight = resolveMinimumPreviewWorkspaceHeight(viewport);
            float maxTopHeight = Math.Max(minTopHeight, totalHeight - timelinePreviewSplitterHeight - minimumPreviewHeight);
            if (maxTopHeight <= minTopHeight + 0.001f)
                return minTopHeight;

            float baseHeight;
            if (timelineTopHeightOverride.HasValue && float.IsFinite(timelineTopHeightOverride.Value))
                baseHeight = timelineTopHeightOverride.Value;
            else
                baseHeight = resolveTimelineTopHeightFromSplitRatio(getConfiguredTimelineSplitRatio(timelineToolboxCollapsed), minTopHeight, maxTopHeight);

            baseHeight += resolvePreviewModeTimelineTopBias(viewport);
            return Math.Clamp(baseHeight, minTopHeight, maxTopHeight);
        }

        private float resolvePreviewModeTimelineTopBias(Vector2 viewport)
        {
            if (previewMode?.Value != EditorPreviewMode.Playfield2D)
                return 0f;

            return ResponsiveLayout.ClampFraction(viewport.Y, 0.038f, 22f, 48f);
        }

        private float resolveMinimumPreviewWorkspaceHeight(Vector2 viewport)
            => resolveMinimumPreviewWorkspaceHeight(viewport, previewMode?.Value == EditorPreviewMode.Playfield2D);

        private static float resolveMinimumPreviewWorkspaceHeight(Vector2 viewport, bool isTwoDimensionalPreview)
        {
            if (!isTwoDimensionalPreview)
                return minimumPreviewWorkspaceHeight;

            float height = viewport.Y > 0 ? viewport.Y : 1080f;
            float responsiveMinimum = ResponsiveLayout.ClampFraction(height, 0.23f, 220f, 300f);
            return Math.Max(minimumPreviewWorkspaceHeight, responsiveMinimum);
        }

        private float resolveTimelineTopMinimumHeight(EditorResponsiveLayoutMetrics metrics, Vector2 viewport, bool? collapsedState = null)
        {
            bool collapsed = collapsedState ?? timelineToolboxCollapsed;
            float densityMinimum = ResponsiveLayout.ClampFraction(viewport.Y, 0.18f, minimumTimelineCoreHeight, 240f);
            float toolboxHeight = collapsed ? resolveTimelineToolboxCollapsedHeight(viewport) : resolveTimelineToolboxExpandedHeight();
            float requiredHeight = minimumTimelineCoreHeight + toolboxHeight;
            return Math.Max(requiredHeight, densityMinimum + toolboxHeight);
        }

        private float resolveTimelineToolboxCollapsedHeight(Vector2 viewport)
            => ResponsiveLayout.ClampFraction(viewport.Y, 0.082f, 72f, 92f);

        private float resolveTimelineToolboxExpandedHeight()
        {
            var viewport = resolveResponsiveViewport();
            var metrics = EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout, footerTipsCollapsed);
            float minimumHeight = Math.Max(metrics.TimelineToolboxHeight, timelineToolboxRowHeight);
            float maximumHeight = Math.Max(
                minimumHeight,
                ResponsiveLayout.ClampFraction(viewport.Y, 0.33f, 180f, 320f));
            float measured = Math.Max(
                timelineToolboxInnerContainer?.DrawHeight ?? 0f,
                timelineToolboxContentFlow?.DrawHeight > 0 && timelineToolboxInnerContainer != null
                    ? timelineToolboxContentFlow.DrawHeight + timelineToolboxInnerContainer.Padding.Top + timelineToolboxInnerContainer.Padding.Bottom
                    : 0f);
            float resolved = Math.Max(minimumHeight, measured);
            return Math.Clamp(resolved, minimumHeight, maximumHeight);
        }

        private double getConfiguredTimelineSplitRatio(bool collapsedState)
        {
            double fallback = collapsedState ? defaultTimelineSplitRatioCollapsed : defaultTimelineSplitRatioExpanded;
            double value = collapsedState
                ? editorTimelineSplitRatioCollapsed?.Value ?? fallback
                : editorTimelineSplitRatioExpanded?.Value ?? fallback;

            if (!double.IsFinite(value))
                return fallback;

            return Math.Clamp(value, 0.0, 1.0);
        }

        private void setConfiguredTimelineSplitRatio(bool collapsedState, double ratio)
        {
            double fallback = collapsedState ? defaultTimelineSplitRatioCollapsed : defaultTimelineSplitRatioExpanded;
            double clamped = Math.Clamp(double.IsFinite(ratio) ? ratio : fallback, 0.0, 1.0);

            if (collapsedState)
            {
                if (editorTimelineSplitRatioCollapsed != null
                    && Math.Abs(editorTimelineSplitRatioCollapsed.Value - clamped) > 0.0001)
                {
                    editorTimelineSplitRatioCollapsed.Value = clamped;
                }

                return;
            }

            if (editorTimelineSplitRatioExpanded != null
                && Math.Abs(editorTimelineSplitRatioExpanded.Value - clamped) > 0.0001)
            {
                editorTimelineSplitRatioExpanded.Value = clamped;
            }
        }

        private void persistTimelineSplitRatioForState(bool collapsedState, float topHeight, EditorResponsiveLayoutMetrics metrics, Vector2 viewport)
        {
            float totalHeight = editorLayoutGrid?.DrawHeight > 0 ? editorLayoutGrid.DrawHeight : viewport.Y;
            float minTopHeight = resolveTimelineTopMinimumHeight(metrics, viewport, collapsedState);
            float minimumPreviewHeight = resolveMinimumPreviewWorkspaceHeight(viewport);
            float maxTopHeight = Math.Max(minTopHeight, totalHeight - timelinePreviewSplitterHeight - minimumPreviewHeight);
            double ratio = resolveTimelineSplitRatioFromHeight(topHeight, minTopHeight, maxTopHeight);
            setConfiguredTimelineSplitRatio(collapsedState, ratio);
        }

        private float resolveTimelineTopHeightForState(EditorResponsiveLayoutMetrics metrics, Vector2 viewport, bool collapsedState)
        {
            float totalHeight = editorLayoutGrid?.DrawHeight > 0 ? editorLayoutGrid.DrawHeight : viewport.Y;
            float minTopHeight = resolveTimelineTopMinimumHeight(metrics, viewport, collapsedState);
            float minimumPreviewHeight = resolveMinimumPreviewWorkspaceHeight(viewport);
            float maxTopHeight = Math.Max(minTopHeight, totalHeight - timelinePreviewSplitterHeight - minimumPreviewHeight);
            return resolveTimelineTopHeightFromSplitRatio(getConfiguredTimelineSplitRatio(collapsedState), minTopHeight, maxTopHeight);
        }

        private static double resolveTimelineSplitRatioFromHeight(float topHeight, float minTopHeight, float maxTopHeight)
        {
            if (maxTopHeight <= minTopHeight + 0.001f)
                return 0.0;

            double ratio = (topHeight - minTopHeight) / (maxTopHeight - minTopHeight);
            if (!double.IsFinite(ratio))
                return 0.0;

            return Math.Clamp(ratio, 0.0, 1.0);
        }

        private static float resolveTimelineTopHeightFromSplitRatio(double ratio, float minTopHeight, float maxTopHeight)
        {
            if (maxTopHeight <= minTopHeight + 0.001f)
                return minTopHeight;

            double clamped = double.IsFinite(ratio) ? Math.Clamp(ratio, 0.0, 1.0) : 0.0;
            return (float)(minTopHeight + (maxTopHeight - minTopHeight) * clamped);
        }
    }
}
