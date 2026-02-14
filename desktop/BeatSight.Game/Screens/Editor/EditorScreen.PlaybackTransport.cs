using System;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void disposeTrack()
        {
            if (track != null)
            {
                track.Completed -= onTrackCompleted;
                track.Stop();
                track.Dispose();
                track = null;
            }

            trackLength = 0;
            lastTrackTime = 0;
            waveformLoadCts?.Cancel();
            waveformLoadCts?.Dispose();
            waveformLoadCts = null;
        }

        private void togglePlayback()
        {
            if (isPlaying)
                stopPlayback();
            else
                startPlayback();
        }

        private void startPlayback()
        {
            double effectiveLength = getEffectivePlaybackLength();
            if (effectiveLength > 0 && currentTime > effectiveLength)
                currentTime = effectiveLength;

            bool audioStarted = false;

            if (track != null && playbackAvailable)
            {
                if (currentTime > track.Length)
                {
                    currentTime = 0;
                    track.Seek(0);
                }
                else
                {
                    double target = Math.Clamp(currentTime, 0, track.Length);
                    if (Math.Abs(track.CurrentTime - target) > 2)
                        track.Seek(target);
                }

                track.Start();
                lastTrackTime = track.CurrentTime;
                audioStarted = true;
            }

            playbackPreview?.JumpToTime(currentTime);
            isPlaying = true;
            updatePlayPauseButtonLabel();
            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);

            if (audioStarted)
                appendStatusDetail("Playing");
            else if (playbackAvailable)
                appendStatusDetail("Playing (no audio)");
            else
                appendStatusDetail("Playing timeline (audio unavailable)");
        }

        private void stopPlayback(bool silent = false)
        {
            if (track != null)
            {
                track.Stop();
                lastTrackTime = track.CurrentTime;
            }

            isPlaying = false;
            updatePlayPauseButtonLabel();

            if (!silent)
                appendStatusDetail("Paused");

            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);
        }

        private void rewindToStart()
        {
            stopPlayback(silent: true);
            seekToTime(0);
            appendStatusDetail("Rewound to start");
        }

        private void updatePlayPauseButtonLabel()
        {
            if (playPauseButton == null)
                return;

            string label = isPlaying ? "Pause" : "Play";
            string tooltip;

            if (playbackAvailable)
            {
                tooltip = isPlaying
                    ? "Pause the preview (Shift+Space rewinds to start)."
                    : "Play the preview (Shift+Space rewinds to start).";
            }
            else
            {
                if (!isPlaying)
                    label = "Play Silent";

                tooltip = isPlaying
                    ? "Pause timeline playback (audio unavailable)."
                    : "Play timeline playback (audio unavailable).";
            }

            playPauseButton.UpdateState(true, tooltip);
            playPauseButton.SetLabel(label);
        }
    }
}
