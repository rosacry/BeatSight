using BeatSight.Game.Screens.Playback.Playfield;
using Xunit;

namespace BeatSight.Tests;

public class PlaybackPlayfieldManuscriptSubdivisionTests
{
    [Fact]
    public void SubdivisionDefaultsToQuarterWhenNoStableSubdivisionAppears()
    {
        int divisor = PlaybackPlayfield.ResolveManuscriptSubdivisionDivisor(new[] { 1.0, 0.94, 1.02 });
        Assert.Equal(1, divisor);
    }

    [Fact]
    public void SubdivisionDetectsEighthPulse()
    {
        int divisor = PlaybackPlayfield.ResolveManuscriptSubdivisionDivisor(new[] { 0.5, 0.49, 0.51 });
        Assert.Equal(2, divisor);
    }

    [Fact]
    public void SubdivisionDetectsEighthTriplets()
    {
        int divisor = PlaybackPlayfield.ResolveManuscriptSubdivisionDivisor(new[] { 1.0 / 3.0, 0.334, 0.332 });
        Assert.Equal(3, divisor);
    }

    [Fact]
    public void SubdivisionDetectsSixteenthGrid()
    {
        int divisor = PlaybackPlayfield.ResolveManuscriptSubdivisionDivisor(new[] { 0.25, 0.249, 0.252 });
        Assert.Equal(4, divisor);
    }

    [Fact]
    public void SubdivisionDetectsSixteenthTripletGrid()
    {
        int divisor = PlaybackPlayfield.ResolveManuscriptSubdivisionDivisor(new[] { 1.0 / 6.0, 0.167, 0.165 });
        Assert.Equal(6, divisor);
    }

    [Fact]
    public void SubdivisionDetectsThirtySecondDensity()
    {
        int divisor = PlaybackPlayfield.ResolveManuscriptSubdivisionDivisor(new[] { 0.125, 0.124, 0.126 });
        Assert.Equal(8, divisor);
    }

    [Theory]
    [InlineData(1.0, 0)]
    [InlineData(0.75, 0)]
    [InlineData(0.5, 1)]
    [InlineData(0.375, 1)]
    [InlineData(0.25, 2)]
    [InlineData(0.1875, 2)]
    [InlineData(0.125, 3)]
    [InlineData(0.08, 3)]
    public void RestGlyphLevelMatchesRhythmicGap(double gapBeats, int expectedLevel)
    {
        int level = PlaybackPlayfield.ResolveManuscriptRestGlyphLevel(gapBeats);
        Assert.Equal(expectedLevel, level);
    }

    [Theory]
    [InlineData(2.0, 2)]
    [InlineData(1.5, 2)]
    [InlineData(1.0, 1)]
    [InlineData(0.76, 1)]
    [InlineData(0.5, 0)]
    [InlineData(0.12, 0)]
    public void RestSpanEmphasisMatchesRhythmicGap(double gapBeats, int expectedLevel)
    {
        int level = PlaybackPlayfield.ResolveManuscriptRestSpanEmphasisLevel(gapBeats);
        Assert.Equal(expectedLevel, level);
    }
}
