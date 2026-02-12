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
}
