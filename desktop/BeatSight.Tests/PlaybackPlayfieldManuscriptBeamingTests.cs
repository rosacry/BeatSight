using BeatSight.Game.Screens.Playback.Playfield;
using Xunit;

namespace BeatSight.Tests;

public class PlaybackPlayfieldManuscriptBeamingTests
{
    [Theory]
    [InlineData(0.5, 1)]             // 8th
    [InlineData(1.0 / 3.0, 1)]       // 8th triplet
    [InlineData(0.25, 2)]            // 16th
    [InlineData(1.0 / 6.0, 2)]       // 16th triplet
    [InlineData(0.125, 3)]           // 32nd
    [InlineData(0.248, 2)]           // near 16th snap tolerance
    [InlineData(0.34, 1)]            // near 8th-triplet bucket
    public void BeamLevelCountMatchesSubdivisionBuckets(double gapBeats, int expected)
    {
        Assert.Equal(expected, PlaybackPlayfield.GetManuscriptBeamLevelCount(gapBeats));
    }

    [Theory]
    [InlineData(0.05)]   // too close / likely unplayable cluster
    [InlineData(0.82)]   // larger than eighth-note grouping threshold
    [InlineData(0.41)]   // no stable bucket match after snapping tolerance
    public void BeamLevelCountRejectsUnstableIntervals(double gapBeats)
    {
        Assert.Equal(0, PlaybackPlayfield.GetManuscriptBeamLevelCount(gapBeats));
    }
}

