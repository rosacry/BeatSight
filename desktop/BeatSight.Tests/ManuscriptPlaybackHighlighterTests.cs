using BeatSight.Game.Screens.Playback.Playfield.Views;
using Xunit;

namespace BeatSight.Tests;

public class ManuscriptPlaybackHighlighterTests
{
    [Fact]
    public void CursorTrailWidthUsesFallbackBandWhenTimelineUnavailable()
    {
        float width = ManuscriptPlaybackHighlighter.ResolvePlaybackCursorTrailWidth(
            timelineWidth: 1000f,
            timelineDurationMs: 0,
            bpm: 120,
            configuredLookaheadMs: 500,
            hasTimelineWindow: false);

        Assert.InRange(width, 89f, 91f);
    }

    [Theory]
    [InlineData(1000f, 4000.0, 120.0, 500.0, 96.0)] // max-clamped center case
    [InlineData(1000f, 2000.0, 120.0, 500.0, 96.0)] // max clamp case
    [InlineData(1000f, 10000.0, 120.0, 200.0, 60.0)] // min clamp case
    public void CursorTrailWidthTracksTimelineWindowAndClamps(float timelineWidth, double durationMs, double bpm, double lookaheadMs, float expected)
    {
        float width = ManuscriptPlaybackHighlighter.ResolvePlaybackCursorTrailWidth(
            timelineWidth,
            durationMs,
            bpm,
            lookaheadMs,
            hasTimelineWindow: true);

        Assert.InRange(width, expected - 0.01f, expected + 0.01f);
    }
}
