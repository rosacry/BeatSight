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

    [Theory]
    [InlineData(0.375, true)]   // dotted 16th
    [InlineData(0.75, true)]    // dotted 8th
    [InlineData(1.5, true)]     // dotted quarter
    [InlineData(0.5, false)]    // straight 8th
    [InlineData(1.0, false)]    // straight quarter
    public void DottedCueDetectionMatchesExpectedBuckets(double gapBeats, bool expected)
    {
        Assert.Equal(expected, PlaybackPlayfield.ShouldRenderManuscriptDottedCue(gapBeats));
    }

    [Theory]
    [InlineData(0.74, false)]   // still in beam/flag space
    [InlineData(0.8, true)]     // tie-style continuity onset
    [InlineData(2.5, true)]     // long spacing still tied
    [InlineData(4.2, false)]    // too long to tie in dense timeline window
    public void TieCueDetectionMatchesDurationWindow(double gapBeats, bool expected)
    {
        Assert.Equal(expected, PlaybackPlayfield.ShouldRenderManuscriptTieCue(gapBeats));
    }
}

