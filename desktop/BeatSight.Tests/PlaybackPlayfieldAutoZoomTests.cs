using BeatSight.Game.Screens.Playback.Playfield;
using Xunit;

namespace BeatSight.Tests;

public class PlaybackPlayfieldAutoZoomTests
{
    [Theory]
    [InlineData(90, 4, 0.2, 1.20)]
    [InlineData(120, 4, 1.1, 1.33)]
    [InlineData(180, 4, 2.8, 1.62)]
    [InlineData(220, 7, 3.5, 1.70)]
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
        Assert.InRange(multiplier, 1.779, 1.781);
    }
}
