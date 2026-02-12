using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Editor;
using Xunit;

namespace BeatSight.Tests
{
    public class EditorTimelineSelectionTests
    {
        [Fact]
        public void SetSelectionRange_StoresOrderedValues()
        {
            var timeline = new EditorTimeline();
            timeline.LoadBeatmap(createBeatmap(durationMs: 60000), durationMs: 60000, waveform: null);

            timeline.SetSelectionRange(5000, 1200);

            Assert.Equal(1200, timeline.SelectionStart);
            Assert.Equal(5000, timeline.SelectionEnd);
        }

        [Fact]
        public void SetSelectionRange_ClampsToTimelineDuration()
        {
            var timeline = new EditorTimeline();
            timeline.LoadBeatmap(createBeatmap(durationMs: 10000), durationMs: 10000, waveform: null);

            timeline.SetSelectionRange(-3000, 190000);

            Assert.Equal(0, timeline.SelectionStart);
            Assert.Equal(60000, timeline.SelectionEnd);
        }

        [Fact]
        public void GetLaneComponentForVisibleLane_UsesResolvedLaneMapping()
        {
            var beatmap = new Beatmap
            {
                Metadata = new BeatmapMetadata
                {
                    Title = "Lane Mapping Test",
                    Artist = "BeatSight"
                },
                Audio = new AudioInfo
                {
                    Filename = "test.wav",
                    Duration = 10000
                },
                HitObjects =
                {
                    new HitObject { Time = 1000, Component = "china", Lane = 0 },
                    new HitObject { Time = 2200, Component = "ride", Lane = 1 }
                }
            };

            var timeline = new EditorTimeline();
            timeline.LoadBeatmap(beatmap, durationMs: 10000, waveform: null);

            Assert.Equal("china", timeline.GetLaneComponentForVisibleLane(0));
            Assert.Equal("ride", timeline.GetLaneComponentForVisibleLane(1));
            Assert.Null(timeline.GetLaneComponentForVisibleLane(99));
        }

        private static Beatmap createBeatmap(int durationMs)
        {
            return new Beatmap
            {
                Metadata = new BeatmapMetadata
                {
                    Title = "Selection Test",
                    Artist = "BeatSight"
                },
                Audio = new AudioInfo
                {
                    Filename = "test.wav",
                    Duration = durationMs
                },
                HitObjects =
                {
                    new HitObject { Time = 1000, Component = "kick", Lane = 3 },
                    new HitObject { Time = 5000, Component = "snare", Lane = 2 }
                }
            };
        }
    }
}
