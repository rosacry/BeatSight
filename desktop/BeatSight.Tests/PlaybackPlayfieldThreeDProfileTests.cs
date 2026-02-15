using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield;
using Xunit;

namespace BeatSight.Tests;

public class PlaybackPlayfieldThreeDProfileTests
{
    [Fact]
    public void ThreeDProfilesDefineDistinctPerspectiveBands()
    {
        var arcade = PlaybackPlayfield.GetThreeDProfileTuningSnapshot(ThreeDStageProfile.Arcade);
        var classic = PlaybackPlayfield.GetThreeDProfileTuningSnapshot(ThreeDStageProfile.GhClassic);
        var tight = PlaybackPlayfield.GetThreeDProfileTuningSnapshot(ThreeDStageProfile.Tight);

        Assert.True(arcade.HighwayTopWidthRatio > classic.HighwayTopWidthRatio);
        Assert.True(classic.HighwayTopWidthRatio > tight.HighwayTopWidthRatio);

        Assert.True(tight.HighwayBottomWidthRatio > classic.HighwayBottomWidthRatio);
        Assert.True(classic.HighwayBottomWidthRatio > arcade.HighwayBottomWidthRatio);

        Assert.True(arcade.VanishingPointYRatio > classic.VanishingPointYRatio);
        Assert.True(classic.VanishingPointYRatio > tight.VanishingPointYRatio);
    }

    [Fact]
    public void TightProfileUsesStrongestPerspectiveCurve()
    {
        var arcade = PlaybackPlayfield.GetThreeDProfileTuningSnapshot(ThreeDStageProfile.Arcade);
        var classic = PlaybackPlayfield.GetThreeDProfileTuningSnapshot(ThreeDStageProfile.GhClassic);
        var tight = PlaybackPlayfield.GetThreeDProfileTuningSnapshot(ThreeDStageProfile.Tight);

        Assert.True(tight.PerspectiveExponent > classic.PerspectiveExponent);
        Assert.True(classic.PerspectiveExponent > arcade.PerspectiveExponent);
    }

    [Fact]
    public void GhClassicProfileKeepsHighwayFootprintInGhStyleRange()
    {
        var classic = PlaybackPlayfield.GetThreeDProfileTuningSnapshot(ThreeDStageProfile.GhClassic);

        Assert.InRange(classic.HighwayTopWidthRatio, 0.06f, 0.08f);
        Assert.InRange(classic.HighwayBottomWidthRatio, 0.86f, 0.90f);
        Assert.InRange(classic.VanishingPointYRatio, 0.08f, 0.09f);
    }

    [Theory]
    [InlineData(ThreeDStageProfile.Arcade, "Arcade")]
    [InlineData(ThreeDStageProfile.GhClassic, "GH Classic")]
    [InlineData(ThreeDStageProfile.Tight, "Tight")]
    public void ThreeDProfileHintLabelsAreStable(ThreeDStageProfile profile, string expected)
    {
        Assert.Equal(expected, PlaybackPlayfield.FormatThreeDProfileHintLabel(profile));
    }
}
