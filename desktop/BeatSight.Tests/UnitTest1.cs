using System;
using System.Collections.Generic;
using BeatSight.Game.AI;
using BeatSight.Game.AI.Generation;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.Beatmaps;

namespace BeatSight.Tests;

public class DetectionStatsTests
{
    [Fact]
    public void LowConfidenceMessageWhenMetricsWeak()
    {
        var stats = new DetectionStats(
            EstimatedBpm: 120,
            PeakCount: 4,
            AverageConfidence: 0.2,
            MaxDensity: 0.1,
            Sections: Array.Empty<DetectionSectionStats>(),
            Sensitivity: 60,
            Grid: QuantizationGrid.Sixteenth,
            QuantizationCoverage: 0.3,
            QuantizationMeanErrorMs: 25,
            QuantizationMedianErrorMs: 20,
            QuantizationOffsetSeconds: 0.05,
            QuantizationStepSeconds: 0.125,
            ConfidenceScore: 0.2,
            QuantizationCandidates: Array.Empty<QuantizationCandidate>());

        Assert.True(stats.TryGetLowConfidenceMessage(out var message));
        Assert.Contains("Low detection confidence", message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void NoLowConfidenceMessageWhenMetricsStrong()
    {
        var stats = new DetectionStats(
            EstimatedBpm: 174,
            PeakCount: 128,
            AverageConfidence: 0.82,
            MaxDensity: 6.4,
            Sections: Array.Empty<DetectionSectionStats>(),
            Sensitivity: 60,
            Grid: QuantizationGrid.Sixteenth,
            QuantizationCoverage: 0.78,
            QuantizationMeanErrorMs: 6,
            QuantizationMedianErrorMs: 4,
            QuantizationOffsetSeconds: 0.01,
            QuantizationStepSeconds: 0.125,
            ConfidenceScore: 0.9,
            QuantizationCandidates: Array.Empty<QuantizationCandidate>());

        Assert.False(stats.TryGetLowConfidenceMessage(out _));
    }

    [Fact]
    public void MetricsDictionaryIncludesExpectedKeys()
    {
        var sections = new[]
        {
            new DetectionSectionStats(Index: 1, Start: 0, End: 10, HitCount: 32, HitsPerSecond: 3.2)
        };

        var stats = new DetectionStats(
            EstimatedBpm: 90,
            PeakCount: 64,
            AverageConfidence: 0.65,
            MaxDensity: 5.1,
            Sections: sections,
            Sensitivity: 55,
            Grid: QuantizationGrid.Eighth,
            QuantizationCoverage: 0.62,
            QuantizationMeanErrorMs: 12,
            QuantizationMedianErrorMs: 9,
            QuantizationOffsetSeconds: 0.08,
            QuantizationStepSeconds: 0.1667,
            ConfidenceScore: 0.75,
            QuantizationCandidates: Array.Empty<QuantizationCandidate>());

        var metrics = stats.ToMetrics();

        Assert.Equal(64, metrics["peaks"]);
        Assert.True(metrics.ContainsKey("section_count"));
        Assert.Equal(1, metrics["section_count"]);
        Assert.Equal((double)QuantizationGrid.Eighth, metrics["grid"]);
        Assert.Equal(0.1667, metrics["step_seconds"], 4);
        Assert.Equal(0.75, metrics["confidence_score"], 2);
    }

    [Fact]
    public void TempoAmbiguityMessageWhenAliasDetected()
    {
        var candidates = new[]
        {
            new QuantizationCandidate(120, 0.72, 5, 4, 0.01, 0.125),
            new QuantizationCandidate(60, 0.69, 6, 5, 0.01, 0.25)
        };

        var stats = new DetectionStats(
            EstimatedBpm: 120,
            PeakCount: 42,
            AverageConfidence: 0.7,
            MaxDensity: 4.1,
            Sections: Array.Empty<DetectionSectionStats>(),
            Sensitivity: 55,
            Grid: QuantizationGrid.Sixteenth,
            QuantizationCoverage: 0.72,
            QuantizationMeanErrorMs: 5,
            QuantizationMedianErrorMs: 4,
            QuantizationOffsetSeconds: 0.01,
            QuantizationStepSeconds: 0.125,
            ConfidenceScore: 0.68,
            QuantizationCandidates: candidates);

        Assert.True(stats.TryGetTempoAmbiguityMessage(out var message));
        Assert.Contains("Tempo ambiguous", message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void TimebaseSynchroniserAlignsBeatmap()
    {
        var beatmap = new Beatmap
        {
            Timing = new TimingInfo
            {
                Bpm = 100,
                Offset = 50,
                TimingPoints = new List<TimingPoint>
                {
                    new TimingPoint { Time = 50, Bpm = 100 }
                }
            },
            HitObjects = new List<HitObject>
            {
                new HitObject { Time = 1000, Component = "kick" }
            },
            Editor = new EditorInfo
            {
                Bookmarks = new List<int> { 1000 }
            }
        };

        var options = new AiGenerationOptions
        {
            ForcedBpm = 120,
            ForcedOffsetSeconds = 0.25,
            ForcedStepSeconds = 0.125,
            ForceQuantization = true
        };

        var result = BeatmapTimebaseSynchroniser.Apply(beatmap, options);

        Assert.True(result.BpmAligned);
        Assert.True(result.OffsetAdjusted);
        Assert.Equal(200, result.OffsetDelta);
        Assert.Equal(120, beatmap.Timing.Bpm);
        Assert.Equal(250, beatmap.Timing.Offset);
        Assert.Equal(1200, beatmap.HitObjects[0].Time);
        Assert.Equal(1200, beatmap.Editor?.Bookmarks?[0]);
        Assert.Equal(4, beatmap.Editor?.SnapDivisor);
        Assert.Equal(beatmap.Timing.Offset, beatmap.Timing.TimingPoints?[0].Time);
        Assert.Equal(120, beatmap.Timing.TimingPoints?[0].Bpm);
    }
}