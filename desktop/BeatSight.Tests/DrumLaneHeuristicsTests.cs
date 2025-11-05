using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Mapping;
using Xunit;

namespace BeatSight.Tests;

public class DrumLaneHeuristicsTests
{
    [Theory]
    [InlineData("kick", 3)]
    [InlineData("snare", 2)]
    [InlineData("hihat_open", 1)]
    [InlineData("ride", 5)]
    [InlineData("splash", 6)]
    [InlineData("tom_mid", 4)]
    public void ResolveLane_ByComponent_UsesSevenLaneLayout(string component, int expectedLane)
    {
        Assert.Equal(expectedLane, DrumLaneHeuristics.ResolveLane(component));
    }

    [Theory]
    [InlineData(DrumType.Kick, 3)]
    [InlineData(DrumType.Snare, 2)]
    [InlineData(DrumType.HiHat, 1)]
    [InlineData(DrumType.Tom, 4)]
    [InlineData(DrumType.Cymbal, 5)]
    public void ResolveLane_ByType_UsesConsistentMapping(DrumType type, int expectedLane)
    {
        Assert.Equal(expectedLane, DrumLaneHeuristics.ResolveLane(type));
    }

    [Fact]
    public void ApplyToBeatmap_AssignsMissingLanes()
    {
        var beatmap = new Beatmap
        {
            HitObjects =
            {
                new HitObject { Component = "kick" },
                new HitObject { Component = "snare" },
                new HitObject { Component = "ride", Lane = 10 },
                new HitObject { Component = "tom_high" }
            }
        };

        DrumLaneHeuristics.ApplyToBeatmap(beatmap);

        Assert.Collection(beatmap.HitObjects,
            h => Assert.Equal(3, h.Lane),
            h => Assert.Equal(2, h.Lane),
            h => Assert.Equal(5, h.Lane),
            h => Assert.Equal(4, h.Lane));
    }
}