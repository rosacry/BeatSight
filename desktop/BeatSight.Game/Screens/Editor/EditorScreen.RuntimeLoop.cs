using System;
using osu.Framework.Graphics;
using osu.Framework.Screens;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            uiAudio.PlayTransition();

            // Animate timeline from bottom
            if (timeline != null)
                timeline.MoveToY(100).FadeInFromZero(500).MoveToY(0, 800, Easing.OutQuint);

            // Animate preview from top
            if (playbackPreview != null)
                playbackPreview.MoveToY(-100).FadeInFromZero(500).MoveToY(0, 800, Easing.OutQuint);

            // Animate back button
            if (backButton != null)
                backButton.ScaleTo(0).Delay(200).ScaleTo(1, 600, Easing.OutElastic);
        }

        protected override void Update()
        {
            base.Update();
            applyResponsiveEditorLayout();
            refreshInspectorActionLabelWidths();
            layoutHeaderTimeBadgeContent();

            if (isPlaying)
            {
                if (track != null)
                {
                    double newTime = track.CurrentTime;
                    if (track.IsRunning && newTime > lastTrackTime)
                        currentTime = newTime;
                    else
                        currentTime = Math.Max(0, currentTime + Time.Elapsed * playbackRate);

                    lastTrackTime = newTime;
                }
                else
                {
                    currentTime = Math.Max(0, currentTime + Time.Elapsed * playbackRate);
                }
            }

            double effectiveLength = getEffectivePlaybackLength();
            if (effectiveLength > 0)
                currentTime = Math.Clamp(currentTime, 0, effectiveLength);

            handleEditorMetronome();

            if (isPlaying
                && effectiveLength > 0
                && currentTime >= effectiveLength - 1
                && (track == null || !track.IsRunning))
            {
                stopPlayback(silent: true);
                currentTime = effectiveLength;
                appendStatusDetail("Playback finished");
            }

            if (timelineZoomInteractionActive
                && pendingTimelineZoomPreview.HasValue
                && Time.Current - lastTimelineZoomPreviewAppliedAt >= timelineZoomPreviewMinIntervalMs)
            {
                applyTimelineZoomPreviewNow(pendingTimelineZoomPreview.Value, Time.Current);
            }

            if (waveformScaleInteractionActive
                && pendingWaveformScalePreview.HasValue
                && Time.Current - lastWaveformScalePreviewAppliedAt >= waveformScalePreviewMinIntervalMs)
            {
                applyWaveformScalePreviewNow(pendingWaveformScalePreview.Value, Time.Current);
            }

            if (playbackZoomInteractionActive
                && pendingPlaybackZoomPreview.HasValue
                && Time.Current - lastPlaybackZoomPreviewAppliedAt >= playbackZoomPreviewMinIntervalMs)
            {
                applyPlaybackZoomPreviewNow(pendingPlaybackZoomPreview.Value, Time.Current);
            }

            timeText.Text = formatTime(currentTime);
            if (timeline != null)
            {
                bool timelineNeedsSync = isPlaying
                    || double.IsNaN(lastTimelineSyncedTime)
                    || Math.Abs(currentTime - lastTimelineSyncedTime) >= 0.25;

                if (timelineNeedsSync)
                {
                    syncTimelineSnapForCurrentTime();
                    timeline.SetCurrentTime(currentTime, ensureVisible: true);
                    lastTimelineSyncedTime = currentTime;
                }
            }

            syncFooterSeekBar();
            updateScrubTelemetryFrame();
            updateScrubPerfOverlay();

            if (previewMode?.Value == EditorPreviewMode.Manuscript
                && Time.Current - lastManuscriptFocusSyncAt >= manuscriptFocusSyncIntervalMs)
            {
                syncManuscriptFocus();
                lastManuscriptFocusSyncAt = Time.Current;
            }
        }
    }
}
