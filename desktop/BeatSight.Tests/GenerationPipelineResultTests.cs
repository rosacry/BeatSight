using System.Collections.Generic;
using BeatSight.Game.AI;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.AI.Generation;
using BeatSight.Game.Services.Generation;
using Xunit;

namespace BeatSight.Tests;

public class GenerationPipelineResultTests
{
    [Fact]
    public void CreateSuccess_OfflinePreviewSmokeTest()
    {
        var beatmap = new AiGenerationResult
        {
            Success = true,
            BeatmapPath = "beatmap.bsm"
        };

        var logs = new List<string> { "[gen] offline decode" };
        var result = GenerationPipelineResult.CreateSuccess(
            beatmap,
            analysis: null,
            waveform: null,
            usedFallback: false,
            playbackAvailable: false,
            usedOfflineDecode: true,
            offlineFallbackEncountered: true,
            warning: "Audio device slow or unavailable — continuing with offline decode (playback disabled).",
            logs: logs);

        Assert.True(result.Success);
        Assert.False(result.PlaybackAvailable);
        Assert.True(result.UsedOfflineDecode);
        Assert.True(result.OfflineFallbackEncountered);
        Assert.Equal(logs, result.Logs);
        Assert.Equal("Audio device slow or unavailable — continuing with offline decode (playback disabled).", result.Warning);
        Assert.Null(result.LaneStats);
        Assert.Empty(result.StageDurations);
        Assert.Equal(0, result.TotalDurationMs);
        Assert.Null(result.DetectionStats);
    }

    [Fact]
    public void CreateSuccess_CarriesDetectionStats()
    {
        var stats = new DetectionStats(
            EstimatedBpm: 128,
            PeakCount: 48,
            AverageConfidence: 0.6,
            MaxDensity: 3.2,
            Sections: Array.Empty<DetectionSectionStats>(),
            Sensitivity: 55,
            Grid: QuantizationGrid.Sixteenth,
            QuantizationCoverage: 0.7,
            QuantizationMeanErrorMs: 12,
            QuantizationMedianErrorMs: 8,
            QuantizationOffsetSeconds: 0.02,
            QuantizationStepSeconds: 0.125,
            ConfidenceScore: 0.65,
            QuantizationCandidates: Array.Empty<QuantizationCandidate>());

        var result = GenerationPipelineResult.CreateSuccess(
            beatmap: new AiGenerationResult { Success = true },
            analysis: null,
            waveform: null,
            usedFallback: false,
            playbackAvailable: true,
            usedOfflineDecode: false,
            offlineFallbackEncountered: false,
            warning: null,
            logs: Array.Empty<string>(),
            detectionStats: stats);

        Assert.Same(stats, result.DetectionStats);
    }
}
