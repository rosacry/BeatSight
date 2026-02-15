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

    [Fact]
    public void ThreeDStrikeZonePresentationKeepsTightProfileMostEmphasized()
    {
        var arcade = ThreeDHighwayBackground.ResolveThreeDStrikeZonePresentation(ThreeDStageProfile.Arcade, drawHeight: 1080f);
        var classic = ThreeDHighwayBackground.ResolveThreeDStrikeZonePresentation(ThreeDStageProfile.GhClassic, drawHeight: 1080f);
        var tight = ThreeDHighwayBackground.ResolveThreeDStrikeZonePresentation(ThreeDStageProfile.Tight, drawHeight: 1080f);

        Assert.True(tight.RailAlpha > classic.RailAlpha);
        Assert.True(classic.RailAlpha > arcade.RailAlpha);

        Assert.True(tight.GlowAlpha > classic.GlowAlpha);
        Assert.True(classic.GlowAlpha > arcade.GlowAlpha);

        Assert.True(tight.ReceptorHeightScale > classic.ReceptorHeightScale);
        Assert.True(classic.ReceptorHeightScale > arcade.ReceptorHeightScale);
    }

    [Theory]
    [InlineData(ThreeDStageProfile.Arcade)]
    [InlineData(ThreeDStageProfile.GhClassic)]
    [InlineData(ThreeDStageProfile.Tight)]
    public void ThreeDStrikeZonePresentationValuesStayWithinSafeBounds(ThreeDStageProfile profile)
    {
        var compact = ThreeDHighwayBackground.ResolveThreeDStrikeZonePresentation(profile, drawHeight: 720f);
        var desktop = ThreeDHighwayBackground.ResolveThreeDStrikeZonePresentation(profile, drawHeight: 1080f);
        var tall = ThreeDHighwayBackground.ResolveThreeDStrikeZonePresentation(profile, drawHeight: 1440f);

        Assert.InRange(compact.RailAlpha, 0.35f, 0.9f);
        Assert.InRange(compact.GlowAlpha, 0.35f, 0.9f);
        Assert.InRange(compact.ReceptorHeightScale, 0.8f, 1.3f);
        Assert.InRange(compact.BorderThickness, 1.4f, 2.6f);

        Assert.InRange(desktop.RailAlpha, 0.35f, 0.9f);
        Assert.InRange(desktop.GlowAlpha, 0.35f, 0.9f);
        Assert.InRange(desktop.ReceptorHeightScale, 0.8f, 1.3f);
        Assert.InRange(desktop.BorderThickness, 1.4f, 2.6f);

        Assert.InRange(tall.RailAlpha, 0.35f, 0.9f);
        Assert.InRange(tall.GlowAlpha, 0.35f, 0.9f);
        Assert.InRange(tall.ReceptorHeightScale, 0.8f, 1.3f);
        Assert.InRange(tall.BorderThickness, 1.4f, 2.6f);
    }
}
