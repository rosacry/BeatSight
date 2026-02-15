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
    [InlineData(0.5, 1, 2)]
    [InlineData(1.0 / 3.0, 1, 3)]
    [InlineData(0.25, 2, 4)]
    [InlineData(1.0 / 6.0, 2, 6)]
    [InlineData(0.125, 3, 8)]
    public void BeamSubdivisionResolutionMatchesExpectedBuckets(double gapBeats, int expectedLevel, int expectedSubdivision)
    {
        bool resolved = PlaybackPlayfield.TryResolveManuscriptBeamSubdivision(gapBeats, out int levelCount, out int subdivision);
        Assert.True(resolved);
        Assert.Equal(expectedLevel, levelCount);
        Assert.Equal(expectedSubdivision, subdivision);
    }

    [Theory]
    [InlineData(2, 2)]
    [InlineData(3, 3)]
    [InlineData(4, 2)]
    [InlineData(6, 3)]
    [InlineData(8, 4)]
    public void BeamGroupingSpanTicksMatchesSubdivisionFamily(int subdivisionDivisor, int expectedGroupingSpan)
    {
        Assert.Equal(expectedGroupingSpan, PlaybackPlayfield.ResolveManuscriptBeamGroupingSpanTicks(subdivisionDivisor));
    }

    [Theory]
    [InlineData(0.00, 0.25, 4, true)]               // 16ths within first half-beat group
    [InlineData(0.25, 0.50, 4, false)]              // crosses 16th half-beat boundary
    [InlineData(0.50, 0.75, 4, true)]               // 16ths within second half-beat group
    [InlineData(0.0, 1.0 / 6.0, 6, true)]           // 16th-triplet inside group of 3 ticks
    [InlineData(2.0 / 6.0, 3.0 / 6.0, 6, false)]    // crosses 16th-triplet half-beat boundary
    [InlineData(0.0, 1.0 / 3.0, 3, true)]           // 8th-triplet stays beamed across full beat group
    [InlineData(1.0 / 3.0, 2.0 / 3.0, 3, true)]
    [InlineData(0.0, 0.5, 2, true)]                 // 8ths share beat group
    public void BeamPairGroupingRespectsSubdivisionBoundaries(double currentBeatProgress, double nextBeatProgress, int subdivisionDivisor, bool expected)
    {
        Assert.Equal(expected, PlaybackPlayfield.IsManuscriptBeamPairWithinSubdivisionGroup(currentBeatProgress, nextBeatProgress, subdivisionDivisor));
    }

    [Fact]
    public void ManuscriptChordHorizontalOffsetSeparatesCrossVoices()
    {
        float lower = PlaybackPlayfield.ResolveManuscriptChordHorizontalOffset(0, 1, lowerVoice: true, hasCrossVoice: true, noteWidth: 14f);
        float upper = PlaybackPlayfield.ResolveManuscriptChordHorizontalOffset(0, 1, lowerVoice: false, hasCrossVoice: true, noteWidth: 14f);

        Assert.True(lower < -1.5f, $"Expected lower voice offset leftward, got {lower:0.###}");
        Assert.True(upper > 1.5f, $"Expected upper voice offset rightward, got {upper:0.###}");
    }

    [Fact]
    public void ManuscriptChordHorizontalOffsetCentersSameVoiceClusters()
    {
        float left = PlaybackPlayfield.ResolveManuscriptChordHorizontalOffset(0, 3, lowerVoice: false, hasCrossVoice: false, noteWidth: 12f);
        float middle = PlaybackPlayfield.ResolveManuscriptChordHorizontalOffset(1, 3, lowerVoice: false, hasCrossVoice: false, noteWidth: 12f);
        float right = PlaybackPlayfield.ResolveManuscriptChordHorizontalOffset(2, 3, lowerVoice: false, hasCrossVoice: false, noteWidth: 12f);

        Assert.True(left < middle, $"Expected left cluster note offset ordering, left={left:0.###}, middle={middle:0.###}");
        Assert.True(middle < right, $"Expected right cluster note offset ordering, middle={middle:0.###}, right={right:0.###}");
        Assert.InRange(middle, -0.001f, 0.001f);
        Assert.InRange(left + right, -0.02f, 0.02f);
    }

    [Fact]
    public void ManuscriptSimultaneousTimeKeyUsesSubMillisecondBucketing()
    {
        long baseKey = PlaybackPlayfield.ResolveManuscriptSimultaneousTimeKey(1000.0);
        long nearKey = PlaybackPlayfield.ResolveManuscriptSimultaneousTimeKey(1000.24);
        long farKey = PlaybackPlayfield.ResolveManuscriptSimultaneousTimeKey(1000.76);

        Assert.Equal(baseKey, nearKey);
        Assert.NotEqual(baseKey, farKey);
    }

    [Fact]
    public void TieArchLiftMagnitudeStacksOutwardWithClusterIndex()
    {
        float baseLift = PlaybackPlayfield.ResolveManuscriptTieArchLiftMagnitude(88f, tieStackIndex: 0, tieStackCount: 3);
        float middleLift = PlaybackPlayfield.ResolveManuscriptTieArchLiftMagnitude(88f, tieStackIndex: 1, tieStackCount: 3);
        float outerLift = PlaybackPlayfield.ResolveManuscriptTieArchLiftMagnitude(88f, tieStackIndex: 2, tieStackCount: 3);

        Assert.True(baseLift > 0f, $"Expected positive base lift, got {baseLift:0.###}");
        Assert.True(baseLift < middleLift, $"Expected stacked tie lift to increase, base={baseLift:0.###}, middle={middleLift:0.###}");
        Assert.True(middleLift < outerLift, $"Expected stacked tie lift to increase, middle={middleLift:0.###}, outer={outerLift:0.###}");
    }

    [Fact]
    public void TieArchLiftMagnitudeClampsInvalidInputs()
    {
        float invalid = PlaybackPlayfield.ResolveManuscriptTieArchLiftMagnitude(float.NaN, tieStackIndex: -9, tieStackCount: 0);
        float huge = PlaybackPlayfield.ResolveManuscriptTieArchLiftMagnitude(8000f, tieStackIndex: 12, tieStackCount: 9);

        Assert.InRange(invalid, 2.4f, 12f);
        Assert.InRange(huge, 2.4f, 40f);
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
    [InlineData(0.8, false)]    // short spacing should use beam/flag language, not ties
    [InlineData(1.0, false)]    // quarter-step continuity is still too dense for tie cues
    [InlineData(1.5, false)]    // dotted values use duration-dot cue instead
    [InlineData(2.0, true)]     // longer spacing can use tie-style continuity
    [InlineData(2.5, true)]     // long spacing still tied
    [InlineData(4.2, false)]    // too long to tie in dense timeline window
    public void TieCueDetectionMatchesDurationWindow(double gapBeats, bool expected)
    {
        Assert.Equal(expected, PlaybackPlayfield.ShouldRenderManuscriptTieCue(gapBeats));
    }

    [Theory]
    [InlineData(2.0, 0, true)]
    [InlineData(2.0, 1, true)]
    [InlineData(2.0, 2, false)] // avoid long arcs through dense intervening note clusters
    public void TieCueDetectionRejectsDenseInterveningVoiceContext(double gapBeats, int interveningVoiceNotes, bool expected)
    {
        Assert.Equal(expected, PlaybackPlayfield.ShouldRenderManuscriptTieCue(gapBeats, interveningVoiceNotes));
    }
}

