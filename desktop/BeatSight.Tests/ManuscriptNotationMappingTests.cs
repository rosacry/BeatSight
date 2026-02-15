using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using Xunit;

namespace BeatSight.Tests;

public class ManuscriptNotationMappingTests
{
    [Fact]
    public void StaffUnitsFollowReadableLaneOrdering()
    {
        float kick = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("kick");
        float hihat = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("hihat_closed");
        float snare = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("snare");
        float tomHigh = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("tom_high");
        float tomMid = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("tom_mid");
        float tomLow = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("tom_low");
        float ride = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("ride");
        float crash = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("crash");

        Assert.True(kick < hihat);
        Assert.True(hihat < snare);
        Assert.True(snare < tomHigh);
        Assert.True(tomHigh < tomMid);
        Assert.True(tomMid < tomLow);
        Assert.True(tomLow < ride);
        Assert.True(ride < crash);
    }

    [Fact]
    public void ComponentAliasesResolveToExpectedGuideLanes()
    {
        Assert.Equal(
            ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("hihat"),
            ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("hihat_pedal"));

        Assert.Equal(
            ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("crash"),
            ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("china_2"));

        Assert.Equal(
            ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("ride"),
            ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("ride_bell_1"));
    }

    [Fact]
    public void StaffSpacingScalesWithAvailableWidth()
    {
        float crashAt720 = ManuscriptBackgroundEnhanced.GetStaffPositionForComponent("crash", 1280f);
        float crashAt1440 = ManuscriptBackgroundEnhanced.GetStaffPositionForComponent("crash", 2560f);

        Assert.True(System.Math.Abs(crashAt1440) > System.Math.Abs(crashAt720));
    }

    [Fact]
    public void UnknownComponentFallsBackToSnareGuide()
    {
        float unknown = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("mystery_component");
        float snare = ManuscriptBackgroundEnhanced.GetStaffUnitForComponent("snare");

        Assert.Equal(snare, unknown);
    }

    [Fact]
    public void AdjacentNotationComponentMovesOneStepAndClampsAtEdges()
    {
        Assert.Equal("tom_high", ManuscriptBackgroundEnhanced.GetAdjacentNotationComponent("snare", 1));
        Assert.Equal("hihat", ManuscriptBackgroundEnhanced.GetAdjacentNotationComponent("snare", -1));

        // clamp at top/bottom
        Assert.Equal("kick", ManuscriptBackgroundEnhanced.GetAdjacentNotationComponent("kick", -1));
        Assert.Equal("crash", ManuscriptBackgroundEnhanced.GetAdjacentNotationComponent("crash", 1));
    }

    [Fact]
    public void VoiceGroupingFollowsDrummerNotationConventions()
    {
        Assert.Equal(
            ManuscriptBackgroundEnhanced.ManuscriptNotationVoice.Lower,
            ManuscriptBackgroundEnhanced.GetNotationVoiceForComponent("kick"));

        Assert.Equal(
            ManuscriptBackgroundEnhanced.ManuscriptNotationVoice.Lower,
            ManuscriptBackgroundEnhanced.GetNotationVoiceForComponent("cross_stick"));

        Assert.Equal(
            ManuscriptBackgroundEnhanced.ManuscriptNotationVoice.Upper,
            ManuscriptBackgroundEnhanced.GetNotationVoiceForComponent("hihat_closed"));

        Assert.Equal(
            ManuscriptBackgroundEnhanced.ManuscriptNotationVoice.Upper,
            ManuscriptBackgroundEnhanced.GetNotationVoiceForComponent("ride_bell_1"));
    }

    [Fact]
    public void StemDirectionUsesVoiceGrouping()
    {
        Assert.True(ManuscriptBackgroundEnhanced.ShouldUseDownStemForComponent("kick"));
        Assert.True(ManuscriptBackgroundEnhanced.ShouldUseDownStemForComponent("snare"));
        Assert.False(ManuscriptBackgroundEnhanced.ShouldUseDownStemForComponent("hihat"));
        Assert.False(ManuscriptBackgroundEnhanced.ShouldUseDownStemForComponent("tom_low"));
    }

    [Fact]
    public void CrossNoteheadsApplyToCymbalAliases()
    {
        Assert.True(ManuscriptBackgroundEnhanced.UsesCrossNoteheadForComponent("hihat_pedal"));
        Assert.True(ManuscriptBackgroundEnhanced.UsesCrossNoteheadForComponent("china_2"));
        Assert.True(ManuscriptBackgroundEnhanced.UsesCrossNoteheadForComponent("ride_bell"));
        Assert.False(ManuscriptBackgroundEnhanced.UsesCrossNoteheadForComponent("snare"));
        Assert.False(ManuscriptBackgroundEnhanced.UsesCrossNoteheadForComponent("kick"));
    }

    [Fact]
    public void HiHatArticulationHelpersDistinguishOpenAndClosed()
    {
        Assert.True(ManuscriptBackgroundEnhanced.IsHiHatFamilyComponent("hihat_open"));
        Assert.True(ManuscriptBackgroundEnhanced.IsOpenHiHatComponent("hihat_open"));
        Assert.False(ManuscriptBackgroundEnhanced.IsClosedHiHatComponent("hihat_open"));
        Assert.False(ManuscriptBackgroundEnhanced.IsHalfOpenHiHatComponent("hihat_open"));

        Assert.True(ManuscriptBackgroundEnhanced.IsHiHatFamilyComponent("hihat_half_open"));
        Assert.True(ManuscriptBackgroundEnhanced.IsOpenHiHatComponent("hihat_half_open"));
        Assert.True(ManuscriptBackgroundEnhanced.IsHalfOpenHiHatComponent("hihat_half_open"));
        Assert.False(ManuscriptBackgroundEnhanced.IsClosedHiHatComponent("hihat_half_open"));

        Assert.True(ManuscriptBackgroundEnhanced.IsClosedHiHatComponent("hihat_closed"));
        Assert.True(ManuscriptBackgroundEnhanced.IsClosedHiHatComponent("hihat_pedal"));
        Assert.True(ManuscriptBackgroundEnhanced.IsClosedHiHatComponent("hihat"));
        Assert.False(ManuscriptBackgroundEnhanced.IsOpenHiHatComponent("hihat_closed"));

        Assert.False(ManuscriptBackgroundEnhanced.IsHiHatFamilyComponent("snare"));
    }

    [Fact]
    public void CountInLabelFormattingTracksRelativeTickAndSubdivision()
    {
        Assert.Equal("Now", ManuscriptBackgroundEnhanced.FormatManuscriptCountInLabel(0, 4));
        Assert.Equal("+1/4", ManuscriptBackgroundEnhanced.FormatManuscriptCountInLabel(1, 4));
        Assert.Equal("-2/4", ManuscriptBackgroundEnhanced.FormatManuscriptCountInLabel(-2, 4));
        Assert.Equal("+1b", ManuscriptBackgroundEnhanced.FormatManuscriptCountInLabel(4, 4));
        Assert.Equal("-1b 2/4", ManuscriptBackgroundEnhanced.FormatManuscriptCountInLabel(-6, 4));
        Assert.Equal("+2b", ManuscriptBackgroundEnhanced.FormatManuscriptCountInLabel(8, 4));
        Assert.Equal("+1/3", ManuscriptBackgroundEnhanced.FormatManuscriptCountInLabel(1, 3));
    }

    [Fact]
    public void CountInLookAroundTicksScaleByGuideMode()
    {
        Assert.Equal(0, ManuscriptBackgroundEnhanced.ResolveManuscriptCountInLookAroundTicks(4, ManuscriptCountInGuideMode.Off));
        Assert.Equal(5, ManuscriptBackgroundEnhanced.ResolveManuscriptCountInLookAroundTicks(4, ManuscriptCountInGuideMode.Compact));
        Assert.Equal(8, ManuscriptBackgroundEnhanced.ResolveManuscriptCountInLookAroundTicks(4, ManuscriptCountInGuideMode.Full));
    }

    [Fact]
    public void CountInLabelPolicyRespectsGuideModeDensity()
    {
        Assert.False(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptCountInLabel(ManuscriptCountInGuideMode.Off, isNow: false, isBeat: true, relativeTick: 4, subdivision: 4));
        Assert.True(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptCountInLabel(ManuscriptCountInGuideMode.Compact, isNow: false, isBeat: true, relativeTick: 4, subdivision: 4));
        Assert.False(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptCountInLabel(ManuscriptCountInGuideMode.Compact, isNow: false, isBeat: false, relativeTick: 1, subdivision: 4));
        Assert.True(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptCountInLabel(ManuscriptCountInGuideMode.Full, isNow: false, isBeat: false, relativeTick: 1, subdivision: 4));
    }

    [Fact]
    public void TupletHintPolicyOnlyEnablesTripletSubdivisions()
    {
        Assert.False(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptTupletHint(1));
        Assert.False(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptTupletHint(2));
        Assert.True(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptTupletHint(3));
        Assert.False(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptTupletHint(4));
        Assert.True(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptTupletHint(6));
        Assert.False(ManuscriptBackgroundEnhanced.ShouldRenderManuscriptTupletHint(8));
    }

    [Fact]
    public void TupletHintGroupingAndLabelFormattingStayStable()
    {
        Assert.Equal(3, ManuscriptBackgroundEnhanced.ResolveManuscriptTupletGroupingTicks(3));
        Assert.Equal(3, ManuscriptBackgroundEnhanced.ResolveManuscriptTupletGroupingTicks(6));
        Assert.Equal(0, ManuscriptBackgroundEnhanced.ResolveManuscriptTupletGroupingTicks(4));

        Assert.Equal("3", ManuscriptBackgroundEnhanced.FormatManuscriptTupletHintLabel(3));
        Assert.Equal("3", ManuscriptBackgroundEnhanced.FormatManuscriptTupletHintLabel(6));
        Assert.Equal(string.Empty, ManuscriptBackgroundEnhanced.FormatManuscriptTupletHintLabel(4));
    }

    [Fact]
    public void TupletBracketEmphasisFallsOffWithDistanceFromPlayhead()
    {
        float now = ManuscriptBackgroundEnhanced.ResolveManuscriptTupletBracketEmphasis(0.0);
        float near = ManuscriptBackgroundEnhanced.ResolveManuscriptTupletBracketEmphasis(1.0);
        float far = ManuscriptBackgroundEnhanced.ResolveManuscriptTupletBracketEmphasis(2.5);
        float clamped = ManuscriptBackgroundEnhanced.ResolveManuscriptTupletBracketEmphasis(4.0);

        Assert.InRange(now, 0.99f, 1.01f);
        Assert.InRange(near, 0.72f, 0.74f);
        Assert.InRange(far, 0.31f, 0.33f);
        Assert.InRange(clamped, 0.31f, 0.33f);
        Assert.True(now > near);
        Assert.True(near > far);
    }
}
