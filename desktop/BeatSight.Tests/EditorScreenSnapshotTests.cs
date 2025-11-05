using System.Reflection;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Editor;
using osu.Framework.Bindables;
using osu.Framework.Graphics.Sprites;
using Xunit;

namespace BeatSight.Tests
{
    public class EditorScreenSnapshotTests
    {
        [Fact]
        public void SnapshotRestoresWaveformScaleAndBeatGrid()
        {
            var screen = new EditorScreen();
            var timeline = new EditorTimeline();
            var beatmap = new Beatmap
            {
                Editor = new EditorInfo()
            };

            const double initialZoom = 1.4;
            const double initialWaveform = 1.8;
            const int initialSnap = 8;
            const bool initialGridVisible = false;
            const double initialTime = 12345;

            beatmap.Editor!.SnapDivisor = initialSnap;
            beatmap.Editor.TimelineZoom = initialZoom;
            beatmap.Editor.WaveformScale = initialWaveform;
            beatmap.Editor.BeatGridVisible = initialGridVisible;

            setPrivateField(screen, "timeline", timeline);
            setPrivateField(screen, "beatmap", beatmap);
            setPrivateField(screen, "timelineZoom", initialZoom);
            setPrivateField(screen, "waveformScale", initialWaveform);
            setPrivateField(screen, "snapDivisor", initialSnap);
            setPrivateField(screen, "beatGridVisible", initialGridVisible);
            setPrivateField(screen, "currentTime", initialTime);
            setPrivateField(screen, "timeText", new SpriteText());
            setPrivateField(screen, "editorTimelineZoomDefault", new BindableDouble(initialZoom));
            setPrivateField(screen, "editorWaveformScaleDefault", new BindableDouble(initialWaveform));
            setPrivateField(screen, "editorBeatGridVisibleDefault", new BindableBool(initialGridVisible));

            timeline.SetZoom(initialZoom);
            timeline.SetWaveformScale(initialWaveform);
            timeline.SetBeatGridVisible(initialGridVisible);
            timeline.SetSnap(initialSnap, 120);

            var snapshot = invokePrivateMethod(screen, "createSnapshot");
            Assert.NotNull(snapshot);
            var snapshotType = snapshot!.GetType();

            Assert.Equal(initialWaveform, (double)snapshotType.GetProperty("WaveformScale")!.GetValue(snapshot)!);
            Assert.Equal(initialGridVisible, (bool)snapshotType.GetProperty("BeatGridVisible")!.GetValue(snapshot)!);

            const double mutatedZoom = 0.6;
            const double mutatedWaveform = 0.7;
            const int mutatedSnap = 4;
            const bool mutatedGrid = true;

            setPrivateField(screen, "timelineZoom", mutatedZoom);
            setPrivateField(screen, "waveformScale", mutatedWaveform);
            setPrivateField(screen, "snapDivisor", mutatedSnap);
            setPrivateField(screen, "beatGridVisible", mutatedGrid);

            var mutatedBeatmap = new Beatmap { Editor = new EditorInfo() };
            setPrivateField(screen, "beatmap", mutatedBeatmap);

            invokePrivateMethod(screen, "restoreSnapshot", snapshot);

            Assert.Equal(initialZoom, (double)getPrivateField(screen, "timelineZoom"));
            Assert.Equal(initialWaveform, (double)getPrivateField(screen, "waveformScale"));
            Assert.Equal(initialSnap, (int)getPrivateField(screen, "snapDivisor"));
            Assert.Equal(initialGridVisible, (bool)getPrivateField(screen, "beatGridVisible"));

            var restoredBeatmap = (Beatmap)getPrivateField(screen, "beatmap");
            Assert.NotNull(restoredBeatmap.Editor);
            Assert.Equal(initialWaveform, restoredBeatmap.Editor!.WaveformScale);
            Assert.Equal(initialGridVisible, restoredBeatmap.Editor!.BeatGridVisible);

            var restoredTimeline = (EditorTimeline)getPrivateField(screen, "timeline");
            Assert.NotNull(restoredTimeline);
        }

        private static void setPrivateField<T>(object target, string name, T value)
            => target.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(target, value);

        private static object getPrivateField(object target, string name)
            => target.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(target)!;

        private static object? invokePrivateMethod(object target, string name, params object[]? parameters)
        {
            var method = target.GetType().GetMethod(name, BindingFlags.Instance | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException($"Method '{name}' not found on {target.GetType().Name}.");
            return method.Invoke(target, parameters);
        }
    }
}
