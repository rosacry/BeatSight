using System.Collections.Generic;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using Xunit;

namespace BeatSight.Tests;

public class LaneLayoutFactoryTests
{
    [Fact]
    public void CreateFromComponentsRespectsMinimumLaneCountFloor()
    {
        var layout = LaneLayoutFactory.CreateFromComponents(
            new List<string> { "kick", "snare", "hihat_closed" },
            minimumLaneCount: 7);

        Assert.Equal(7, layout.LaneCount);
        Assert.InRange(layout.KickLane, 0, layout.LaneCount - 1);
        Assert.InRange(layout.SnareLane, 0, layout.LaneCount - 1);
        Assert.InRange(layout.HiHatLane, 0, layout.LaneCount - 1);
    }

    [Fact]
    public void CreateAutoDynamicFallsBackToRequestedLanePresetWhenComponentsMissing()
    {
        var layout = LaneLayoutFactory.CreateAutoDynamic(components: null, minimumLaneCount: 9);

        Assert.Equal(9, layout.LaneCount);
        Assert.Equal(LanePreset.DrumNineLane, layout.Preset);
    }
}
