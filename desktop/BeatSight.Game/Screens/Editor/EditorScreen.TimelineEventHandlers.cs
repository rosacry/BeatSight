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

            if (editorSnapDivisorDefault != null)
                snapDivisor = coerceSnapDivisor(editorSnapDivisorDefault.Value);

            if (editorTimelinePlaybackZoomLinkedDefault != null)
                linkTimelineAndPlaybackZoom = editorTimelinePlaybackZoomLinkedDefault.Value;
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

            if (editorSnapDivisorDefault != null)
                editorSnapDivisorDefault.Value = coerceSnapDivisor(snapDivisor);

            if (editorTimelinePlaybackZoomLinkedDefault != null)
                editorTimelinePlaybackZoomLinkedDefault.Value = linkTimelineAndPlaybackZoom;
        }

        private void onTimelineNoteSelected(HitObject hit)
        {
            selectedHitObject = hit;
            setStatusDetail($"Selected {hit.Component} @ {formatTime(hit.Time)}");
            updateSelectionSummary();

            if (suppressTimelineSelectionSeekCount > 0)
            {
                suppressTimelineSelectionSeekCount--;
                return;
            }

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

            if (requiresHitObjectResort(beatmap.HitObjects, hit))
                beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            queuePlaybackPreviewRefresh();
            markUnsaved();
            refreshUnsavedState();

            if (selectedHitObject != null && !beatmap.HitObjects.Contains(selectedHitObject))
                selectedHitObject = null;

            if (timelineDragInProgress)
            {
                deferredTimelineUiRefreshPending = true;
                return;
            }

            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
        }

        private void onTimelineDragStarted()
            => timelineDragInProgress = true;

        private void onTimelineDragEnded()
        {
            timelineDragInProgress = false;
            flushDeferredTimelineUiRefresh();
            flushPlaybackPreviewRefresh();
        }

        private void flushDeferredTimelineUiRefresh()
        {
            if (!deferredTimelineUiRefreshPending)
                return;

            deferredTimelineUiRefreshPending = false;
            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
        }

        private bool requiresHitObjectResort(System.Collections.Generic.IReadOnlyList<HitObject> hitObjects, HitObject changed)
        {
            int index = -1;
            for (int i = 0; i < hitObjects.Count; i++)
            {
                if (!ReferenceEquals(hitObjects[i], changed))
                    continue;

                index = i;
                break;
            }

            if (index < 0)
                return true;

            if (index > 0 && hitObjects[index - 1].Time > changed.Time)
                return true;

            return index < hitObjects.Count - 1 && hitObjects[index + 1].Time < changed.Time;
        }

        private void queuePlaybackPreviewRefresh()
        {
            if (playbackPreview == null)
                return;

            if (previewRefreshQueued)
                return;

            previewRefreshQueued = true;
            int refreshEpoch = ++previewRefreshEpoch;
            double delay = timelineDragInProgress ? previewRefreshDragDebounceMs : previewRefreshDebounceMs;
            Scheduler.AddDelayed(() =>
            {
                if (refreshEpoch != previewRefreshEpoch)
                    return;

                previewRefreshQueued = false;
                playbackPreview?.RefreshBeatmap();
            }, delay);
        }

        private void flushPlaybackPreviewRefresh()
        {
            if (playbackPreview == null)
                return;

            previewRefreshEpoch++;
            previewRefreshQueued = false;
            playbackPreview.RefreshBeatmap();
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

        private void onPreviewNotePlacementRequested(int lane, double timeMs, bool bypassSnap)
        {
            if (isTimingSetupOverlayVisible() || beatmap == null || timeline == null)
                return;

            suppressQueuedSeekFromDirectPreviewEdit();

            double placementTime = Math.Max(0, timeMs);
            bool bypassTimelineSnap = bypassSnap || !beatGridVisible;
            if (!bypassTimelineSnap)
            {
                double snapInterval = Math.Max(0, getSnapIntervalMs(placementTime));
                if (snapInterval > 0.01)
                {
                    double snapOrigin = getSnapOriginMs(placementTime);
                    placementTime = Math.Round((placementTime - snapOrigin) / snapInterval) * snapInterval + snapOrigin;
                    placementTime = Math.Max(0, placementTime);
                }
            }

            // Insert without timeline-side snapping and without auto-selection.
            // Preview already resolved lane/time from cursor space.
            string laneLabel = getLaneLabelForStatus(lane);
            string snapLabel = bypassTimelineSnap ? " (unsnapped)" : string.Empty;
            if (!timeline.TryAddHitObjectAtTimeAndLane(placementTime, lane, bypassSnap: true, selectInsertedNote: false))
            {
                appendStatusDetail($"Skipped duplicate {laneLabel} @ {formatTime(placementTime)}");
                return;
            }

            setStatusDetail($"Added {laneLabel} @ {formatTime(placementTime)}{snapLabel}");
        }

        private void onPreviewNoteRemovalRequested(int lane, double timeMs)
        {
            if (isTimingSetupOverlayVisible() || beatmap == null || timeline == null)
                return;

            suppressQueuedSeekFromDirectPreviewEdit();
            double removalAnchorTime = Math.Max(0, timeMs);

            if (!timeline.TryDeleteNearestHitObject(removalAnchorTime, lane))
            {
                appendStatusDetail($"No note near {getLaneLabelForStatus(lane)} @ {formatTime(removalAnchorTime)}");
                return;
            }

            setStatusDetail($"Removed nearest {getLaneLabelForStatus(lane)} note @ {formatTime(removalAnchorTime)}");
        }

        private string getLaneLabelForStatus(int lane)
        {
            string? component = timeline?.GetLaneComponentForVisibleLane(lane);
            if (string.IsNullOrWhiteSpace(component))
                return $"lane {lane + 1}";

            return formatComponentDisplayName(component);
        }

        // Direct preview edits should not dispatch delayed wheel/seek-bar scrubs on the same frame,
        // otherwise click placement can appear to jump the whole editor time position.
        private void suppressQueuedSeekFromDirectPreviewEdit()
        {
            pendingSeekTimeMs = null;
            pendingSeekEnsureVisible = false;
            pendingSeekSyncTrack = false;
            pendingSeekSyncPreview = false;
            pendingSeekSource = SeekInputSource.Programmatic;
            seekDispatchScheduled = false;
            finalizeScrubTelemetry();
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

            if (editorLayoutGrid != null)
                applyResponsiveEditorLayout(force: true);
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
