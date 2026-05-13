using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using osu.Framework.Logging;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void reloadTimeline()
        {
            if (timeline == null)
                return;

            if (beatmap == null)
            {
                Logger.Log("[EditorScreen] reloadTimeline: beatmap is NULL", LoggingTarget.Runtime, LogLevel.Important);
                timeline.LoadBeatmap(new Beatmap(), Math.Max(trackLength, 60000), waveformData);
                timeline.SetZoom(timelineZoom);
                timeline.SetSnap(0, double.NaN, 0, 4, 4);
                timeline.SetWaveformScale(waveformScale);
                timeline.SetBeatGridVisible(beatGridVisible);
                timeline.SetCurrentTime(currentTime);
                playbackPreview?.SetBeatmap(null);
                updateInspectorEnabledState(false);
                selectedHitObject = null;
                updateSelectionSummary();
                updateInspectorStats();
                populateInspectorFromBeatmap();
                updatePlaybackAvailabilityUI();
                return;
            }

            double duration = trackLength > 0
                ? trackLength
                : Math.Max(beatmap.Audio.Duration, beatmap.HitObjects.Count > 0 ? beatmap.HitObjects[^1].Time + 5000 : 60000);

            Logger.Log($"[EditorScreen] reloadTimeline: setting beatmap with {beatmap.HitObjects.Count} notes, playbackPreview={(playbackPreview == null ? "NULL" : "exists")}", LoggingTarget.Runtime, LogLevel.Important);

            timeline.LoadBeatmap(beatmap, duration, waveformData);
            timeline.SetZoom(timelineZoom);
            timeline.SetWaveformScale(waveformScale);
            timeline.SetBeatGridVisible(beatGridVisible);
            syncTimelineSnapForCurrentTime(force: true);
            timeline.SetCurrentTime(currentTime);
            playbackPreview?.SetBeatmap(beatmap);
            if (selectedHitObject != null && !beatmap.HitObjects.Contains(selectedHitObject))
                selectedHitObject = null;
            updateSelectionSummary();
            updateInspectorEnabledState(true);
            updateInspectorStats();
            updatePlaybackAvailabilityUI();
        }

        private void queueWaveformLoad(string absolutePath)
        {
            if (string.IsNullOrEmpty(absolutePath) || !File.Exists(absolutePath))
                return;

            waveformLoadCts?.Cancel();
            waveformLoadCts?.Dispose();
            waveformLoadCts = new CancellationTokenSource();
            var token = waveformLoadCts.Token;

            fullTrackWaveform = null;
            drumStemWaveform = null;
            waveformData = null;
            timeline?.UpdateWaveform(null);

            Task.Run(async () =>
            {
                var mainTask = WaveformDataBuilder.BuildAsync(absolutePath, cancellationToken: token);
                Task<WaveformData?>? drumTask = null;

                if (beatmap?.Audio.DrumStem != null && !string.IsNullOrEmpty(beatmapPath))
                {
                    string? beatmapDir = Path.GetDirectoryName(beatmapPath);
                    if (beatmapDir != null)
                    {
                        string drumStemPath = Path.Combine(beatmapDir, beatmap.Audio.DrumStem);
                        if (File.Exists(drumStemPath))
                        {
                            drumTask = WaveformDataBuilder.BuildAsync(drumStemPath, cancellationToken: token);
                        }
                    }
                }

                await mainTask.ConfigureAwait(false);
                if (drumTask != null) await drumTask.ConfigureAwait(false);

                return (Main: mainTask.Result, Drum: drumTask?.Result);
            }, token)
            .ContinueWith(task =>
            {
                if (task.IsCanceled || token.IsCancellationRequested)
                    return;

                if (task.IsFaulted)
                {
                    Schedule(() => appendStatusDetail("Waveform generation failed"));
                    return;
                }

                var result = task.Result;
                if (result.Main == null)
                {
                    Schedule(() => appendStatusDetail("Waveform unavailable"));
                    return;
                }

                fullTrackWaveform = result.Main;
                drumStemWaveform = result.Drum;

                Schedule(() =>
                {
                    if (!token.IsCancellationRequested)
                    {
                        updateWaveformSource();
                        timeline?.SetWaveformScale(waveformScale);
                        timeline?.SetCurrentTime(currentTime);
                    }
                });
            }, TaskScheduler.Default);
        }

        private void updateWaveformSource()
        {
            waveformData = showDrumStem.Value && drumStemWaveform != null ? drumStemWaveform : fullTrackWaveform;
            timeline?.UpdateWaveform(waveformData);
        }

        private void onTrackCompleted()
        {
            Schedule(() =>
            {
                stopPlayback(silent: true);
                currentTime = trackLength;
                timeText.Text = formatTime(currentTime);
                timeline?.SetCurrentTime(currentTime);
                appendStatusDetail("Playback finished");
            });
        }
    }
}
