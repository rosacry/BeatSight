using BeatSight.Game.Screens.Playback.Playfield;
using Xunit;

namespace BeatSight.Tests;

public class PlaybackPlayfieldAutoZoomTests
{
    [Theory]
    [InlineData(90, 4, 0.2, 1.44)]
    [InlineData(120, 4, 1.1, 1.69)]
    [InlineData(180, 4, 2.8, 2.05)]
    [InlineData(220, 7, 3.5, 2.17)]
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
        Assert.InRange(multiplier, 2.199, 2.201);
    }
}
