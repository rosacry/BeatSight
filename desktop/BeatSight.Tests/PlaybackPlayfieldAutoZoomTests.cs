using System.Reflection;
using BeatSight.Game.Screens.Playback.Playfield;
using Xunit;

namespace BeatSight.Tests;

public class PlaybackPlayfieldAutoZoomTests
{
    [Theory]
    [InlineData(90, 4, 0.2, 1.18)]
    [InlineData(120, 4, 1.1, 1.42)]
    [InlineData(180, 4, 2.8, 1.78)]
    [InlineData(220, 7, 3.5, 1.87)]
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
        double multiplier = PlaybackPlayfield.CalculateAutoZoomMultiplier(300, 12, 20);
        Assert.InRange(multiplier, 1.949, 1.951);
    }

    [Fact]
    public void FutureViewportDurationScalesInverseWithZoomWhenAutoZoomDisabled()
    {
        var playfield = new PlaybackPlayfield(() => 0);
        playfield.AutoZoom.Value = false;

        double atOne = playfield.GetFutureViewportDurationMsAtZoom(1.0);
        double atTwo = playfield.GetFutureViewportDurationMsAtZoom(2.0);
        double atHalf = playfield.GetFutureViewportDurationMsAtZoom(0.5);

        Assert.InRange(atOne, 1166.0, 1171.0);
        Assert.InRange(atTwo, 809.0, 816.0);
        Assert.InRange(atHalf, 1487.0, 1494.0);
        Assert.True(atHalf > atOne && atOne > atTwo);
    }

    [Fact]
    public void FutureViewportDurationRemainsInverseUnderAutoZoom()
    {
        var playfield = new PlaybackPlayfield(() => 0);
        playfield.AutoZoom.Value = true;

        double atOne = playfield.GetFutureViewportDurationMsAtZoom(1.0);
        double atTwo = playfield.GetFutureViewportDurationMsAtZoom(2.0);

        Assert.True(atOne > 0);
        Assert.True(atTwo > 0);
        Assert.InRange(atOne / atTwo, 1.43, 1.45);
    }

    [Fact]
    public void SnapAwareHeightStaysBelowSnapSpacingForDenseGrid()
    {
        var playfield = new PlaybackPlayfield(
            currentTimeProvider: () => 0,
            snapEnabledProvider: () => true,
            snapIntervalAtTimeProvider: _ => 80.0);

        double noteHeight = invokePrivate<double>(playfield, "resolveTwoDimensionalNoteHeight", 0.0, 700f);
        double approachDuration = playfield.ApproachDuration;
        double snapSpacing = 80.0 / approachDuration * (700f * 0.8f);

        Assert.True(noteHeight > 0);
        Assert.True(snapSpacing > 0);
        Assert.True(noteHeight < snapSpacing);
    }

    [Fact]
    public void SnapAwareHeightDoesNotThrowWhenCollisionCapFallsBelowNominalFloor()
    {
        var playfield = new PlaybackPlayfield(
            currentTimeProvider: () => 0,
            snapEnabledProvider: () => true,
            snapIntervalAtTimeProvider: _ => 4.0);

        float noteHeight = invokePrivate<float>(playfield, "resolveTwoDimensionalNoteHeight", 0.0, 60f);

        Assert.True(float.IsFinite(noteHeight));
        Assert.InRange(noteHeight, 0.99f, 1.01f);
    }

    [Fact]
    public void SnapIntervalFallbackUsesBeatUnitDenominatorFromTimeSignature()
    {
        var playfield = new PlaybackPlayfield(() => 0, () => true, null);
        playfield.LoadBeatmap(new BeatSight.Game.Beatmaps.Beatmap
        {
            Timing = new BeatSight.Game.Beatmaps.TimingInfo
            {
                Bpm = 120,
                TimeSignature = "6/8"
            },
            Editor = new BeatSight.Game.Beatmaps.EditorInfo
            {
                SnapDivisor = 4
            }
        });

        double interval = invokePrivate<double>(playfield, "resolveSnapIntervalMsForCurrentTime", 0.0);
        Assert.InRange(interval, 62.49, 62.51);
    }

    private static T invokePrivate<T>(object target, string methodName, params object[] args)
    {
        var method = target.GetType().GetMethod(methodName, BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException($"Method '{methodName}' not found.");
        object value = method.Invoke(target, args)
            ?? throw new InvalidOperationException($"Method '{methodName}' returned null.");

        if (value is T typed)
            return typed;

        Type targetType = typeof(T);
        if (targetType == typeof(double))
            return (T)(object)Convert.ToDouble(value);
        if (targetType == typeof(float))
            return (T)(object)Convert.ToSingle(value);

        return (T)value;
    }
}
