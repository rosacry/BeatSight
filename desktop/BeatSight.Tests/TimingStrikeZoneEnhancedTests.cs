using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield;
using Xunit;

namespace BeatSight.Tests;

public class TimingStrikeZoneEnhancedTests
{
    [Fact]
    public void ThreeDModeUsesTallerHitZoneThanTwoDimensional()
    {
        var strikeZone = new TimingStrikeZoneEnhanced();

        strikeZone.UpdateGeometry(
            drawWidth: 1280f,
            drawHeight: 720f,
            hitLineY: 670f,
            spawnTop: 0f,
            laneWidth: 120f,
            lanes: 7,
            visibleLanes: 7,
            kickLaneIndex: 3,
            globalKick: true,
            mode: LaneViewMode.TwoDimensional);
        float twoDHeight = strikeZone.Height;

        strikeZone.UpdateGeometry(
            drawWidth: 1280f,
            drawHeight: 720f,
            hitLineY: 670f,
            spawnTop: 0f,
            laneWidth: 120f,
            lanes: 7,
            visibleLanes: 7,
            kickLaneIndex: 3,
            globalKick: true,
            mode: LaneViewMode.ThreeDimensional);

        Assert.True(strikeZone.Height > twoDHeight);
        Assert.True(strikeZone.VisualHitZoneHeight >= 24f);
    }

    [Fact]
    public void ThreeDModeMaintainsStrongVisibility()
    {
        var strikeZone = new TimingStrikeZoneEnhanced();

        strikeZone.UpdateGeometry(
            drawWidth: 1920f,
            drawHeight: 1080f,
            hitLineY: 1000f,
            spawnTop: 0f,
            laneWidth: 140f,
            lanes: 7,
            visibleLanes: 7,
            kickLaneIndex: 3,
            globalKick: false,
            mode: LaneViewMode.ThreeDimensional);

        Assert.True(strikeZone.Alpha >= 0.95f);
    }
}
