using BeatSight.Game.Screens.Playback.Playfield;
using Xunit;

namespace BeatSight.Tests;

public class PlaybackPlayfieldAutoZoomTests
{
    [Theory]
    [InlineData(90, 4, 0.2, 1.28)]
    [InlineData(120, 4, 1.1, 1.43)]
    [InlineData(180, 4, 2.8, 1.78)]
    [InlineData(220, 7, 3.5, 1.88)]
    public void AutoZoomMultiplierScalesWithDensityAndTempo(
        double bpm,
        double beatsPerMeasure,
        double notesPerBeat,
        double minimumExpected)
    {
        double multiplier = PlaybackPlayfield.CalculateAutoZoomMultiplier(bpm, beatsPerMeasure, notesPerBeat);
        Assert.True(multiplier >= minimumExpected, $"Expected >= {minimumExpected:0.00}, got {multiplier:0.000}");
    }

    [Fact]
    public void AutoZoomMultiplierIsCapped()
    {
        double multiplier = PlaybackPlayfield.CalculateAutoZoomMultiplier(300, 9, 20);
        Assert.InRange(multiplier, 1.939, 1.941);
    }
}
