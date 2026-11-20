using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Editor;
using BeatSight.Game.UI.Theming;
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

        [Fact]
        public void SetLaneLayout_RowsFollowThePlayfieldLanes()
        {
            var beatmap = new Beatmap
            {
                Metadata = new BeatmapMetadata
                {
                    Title = "Shared Layout Test",
                    Artist = "BeatSight"
                },
                Audio = new AudioInfo
                {
                    Filename = "test.wav",
                    Duration = 10000
                },
                HitObjects =
                {
                    new HitObject { Time = 1000, Component = "kick" },
                    new HitObject { Time = 1200, Component = "hihat_closed" },
                    new HitObject { Time = 1400, Component = "hihat_open" },
                    new HitObject { Time = 1600, Component = "hihat_closed" }
                }
            };

            var layout = LaneLayoutFactory.Create(LanePreset.DrumNineLane);
            var timeline = new EditorTimeline();
            timeline.SetLaneLayout(layout);
            timeline.LoadBeatmap(beatmap, durationMs: 10000, waveform: null);

            // Row N is playfield lane N, offering the component that lane holds most.
            Assert.Equal("kick", timeline.GetLaneComponentForVisibleLane(DrumLaneHeuristics.ResolveLane("kick", layout)));
            Assert.Equal("hihat_closed", timeline.GetLaneComponentForVisibleLane(DrumLaneHeuristics.ResolveLane("hihat_closed", layout)));

            // An empty lane offers its own instrument for new notes.
            Assert.Equal("ride", timeline.GetLaneComponentForVisibleLane(DrumLaneHeuristics.ResolveLane("ride", layout)));
            Assert.Null(timeline.GetLaneComponentForVisibleLane(layout.LaneCount));
        }

        [Fact]
        public void DescribeLane_ShowsUserLaneNameAndColourOverTheAutomaticIdentity()
        {
            var beatmap = new Beatmap
            {
                Metadata = new BeatmapMetadata
                {
                    Title = "Lane Setup Test",
                    Artist = "BeatSight"
                },
                Audio = new AudioInfo
                {
                    Filename = "test.wav",
                    Duration = 10000
                },
                HitObjects =
                {
                    new HitObject { Time = 1000, Component = "hihat_closed" },
                    new HitObject { Time = 1500, Component = "snare" }
                }
            };

            // Seven lanes: positional default names (Crash, HiHat, Snare, ...) do not match what the lanes hold.
            var layout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
            int hat = DrumLaneHeuristics.ResolveLane("hihat_closed", layout);
            LaneManagement.EnsureLaneLayout(beatmap, layout.LaneCount);
            LaneManagement.RenameLane(beatmap, hat, "Hats", null);
            LaneManagement.RecolorLane(beatmap, hat, DrumPalette.Splash);

            var timeline = new EditorTimeline();
            timeline.SetLaneLayout(layout);
            timeline.LoadBeatmap(beatmap, durationMs: 10000, waveform: null);

            Assert.Equal(layout.LaneCount, timeline.LaneCount);

            var automatic = timeline.DescribeLane(hat, includeCustomisations: false);
            Assert.Equal(LaneIdentityResolver.Resolve(layout, hat).Name, automatic.Name);
            Assert.Equal(LaneIdentityResolver.Resolve(layout, hat).Colour, automatic.Colour);

            var shown = timeline.DescribeLane(hat);
            Assert.Equal("Hats", shown.Name);
            Assert.Equal(LaneManagement.ToColorHex(DrumPalette.Splash), LaneManagement.ToColorHex(shown.Colour));

            // Every other lane only has positional defaults stored, which count as automatic.
            for (int lane = 0; lane < layout.LaneCount; lane++)
            {
                if (lane == hat)
                    continue;

                Assert.Equal(timeline.DescribeLane(lane, includeCustomisations: false), timeline.DescribeLane(lane));
            }
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
