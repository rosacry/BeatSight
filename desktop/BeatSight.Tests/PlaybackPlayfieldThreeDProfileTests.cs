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

    [Fact]
    public void ThreeDHitFeedbackPresentationKeepsTightProfileMostIntense()
    {
        var arcade = ThreeDHighwayBackground.ResolveThreeDHitFeedbackPresentation(ThreeDStageProfile.Arcade, drawHeight: 1080f);
        var classic = ThreeDHighwayBackground.ResolveThreeDHitFeedbackPresentation(ThreeDStageProfile.GhClassic, drawHeight: 1080f);
        var tight = ThreeDHighwayBackground.ResolveThreeDHitFeedbackPresentation(ThreeDStageProfile.Tight, drawHeight: 1080f);

        Assert.True(tight.BeatPulsePeakAlpha > classic.BeatPulsePeakAlpha);
        Assert.True(classic.BeatPulsePeakAlpha > arcade.BeatPulsePeakAlpha);

        Assert.True(tight.RailPulseBoost > classic.RailPulseBoost);
        Assert.True(classic.RailPulseBoost > arcade.RailPulseBoost);

        Assert.True(tight.LaneGlowPeakAlpha > classic.LaneGlowPeakAlpha);
        Assert.True(classic.LaneGlowPeakAlpha > arcade.LaneGlowPeakAlpha);
    }

    [Theory]
    [InlineData(ThreeDStageProfile.Arcade)]
    [InlineData(ThreeDStageProfile.GhClassic)]
    [InlineData(ThreeDStageProfile.Tight)]
    public void ThreeDHitFeedbackPresentationValuesStayWithinSafeBounds(ThreeDStageProfile profile)
    {
        var compact = ThreeDHighwayBackground.ResolveThreeDHitFeedbackPresentation(profile, drawHeight: 720f);
        var desktop = ThreeDHighwayBackground.ResolveThreeDHitFeedbackPresentation(profile, drawHeight: 1080f);
        var tall = ThreeDHighwayBackground.ResolveThreeDHitFeedbackPresentation(profile, drawHeight: 1440f);

        Assert.InRange(compact.BeatPulsePeakAlpha, 0.03f, 0.09f);
        Assert.InRange(compact.HorizonPeakAlpha, 0.18f, 0.36f);
        Assert.InRange(compact.HorizonRestingAlpha, 0.08f, 0.16f);
        Assert.InRange(compact.RailPulseBoost, 0.18f, 0.36f);
        Assert.InRange(compact.GlowPulseBoost, 0.16f, 0.34f);
        Assert.InRange(compact.LaneGlowPeakAlpha, 0.45f, 0.92f);
        Assert.InRange(compact.LaneGlowDecayAlpha, 0.18f, 0.40f);
        Assert.InRange(compact.LaneFillEmphasis, 1.1f, 1.4f);
        Assert.InRange(compact.LaneFillRestingAlpha, (byte)80, (byte)120);

        Assert.InRange(desktop.BeatPulsePeakAlpha, 0.03f, 0.09f);
        Assert.InRange(desktop.HorizonPeakAlpha, 0.18f, 0.36f);
        Assert.InRange(desktop.HorizonRestingAlpha, 0.08f, 0.16f);
        Assert.InRange(desktop.RailPulseBoost, 0.18f, 0.36f);
        Assert.InRange(desktop.GlowPulseBoost, 0.16f, 0.34f);
        Assert.InRange(desktop.LaneGlowPeakAlpha, 0.45f, 0.92f);
        Assert.InRange(desktop.LaneGlowDecayAlpha, 0.18f, 0.40f);
        Assert.InRange(desktop.LaneFillEmphasis, 1.1f, 1.4f);
        Assert.InRange(desktop.LaneFillRestingAlpha, (byte)80, (byte)120);

        Assert.InRange(tall.BeatPulsePeakAlpha, 0.03f, 0.09f);
        Assert.InRange(tall.HorizonPeakAlpha, 0.18f, 0.36f);
        Assert.InRange(tall.HorizonRestingAlpha, 0.08f, 0.16f);
        Assert.InRange(tall.RailPulseBoost, 0.18f, 0.36f);
        Assert.InRange(tall.GlowPulseBoost, 0.16f, 0.34f);
        Assert.InRange(tall.LaneGlowPeakAlpha, 0.45f, 0.92f);
        Assert.InRange(tall.LaneGlowDecayAlpha, 0.18f, 0.40f);
        Assert.InRange(tall.LaneFillEmphasis, 1.1f, 1.4f);
        Assert.InRange(tall.LaneFillRestingAlpha, (byte)80, (byte)120);
    }
}
