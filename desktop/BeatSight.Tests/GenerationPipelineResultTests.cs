using System.Collections.Generic;
using BeatSight.Game.AI;
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
    }
}