using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.AI;
using BeatSight.Game.AI.Generation;
using BeatSight.Game.Mapping;
using BeatSight.Game.Services.Generation;
using Xunit;

namespace BeatSight.Tests;

public class GenerationCoordinatorTests
{
    [Fact]
    public async Task RunAsync_UsesInjectedPipelineAndReportsCompletion()
    {
        var track = new ImportedAudioTrack(
            originalPath: "/tmp/source.wav",
            storedPath: "/tmp/stored.wav",
            relativeStoragePath: "stored.wav",
            displayName: "Test Track",
            fileSizeBytes: 1024,
            durationMilliseconds: 120_000);

        var pipelineResult = GenerationPipelineResult.CreateSuccess(
            beatmap: new AiGenerationResult { Success = true, BeatmapPath = "beatmap.bsm" },
            analysis: null,
            waveform: null,
            usedFallback: false,
            playbackAvailable: true,
            usedOfflineDecode: false,
            offlineFallbackEncountered: false,
            warning: null,
            logs: Array.Empty<string>());
        Assert.Null(pipelineResult.LaneStats);

        var pipeline = new FakePipeline(() => sequence(pipelineResult));
        var coordinator = new GenerationCoordinator(pipeline, action => action());

        var parameters = new GenerationParams(track, DetectionSensitivity: 60, Quantization: QuantizationGrid.Sixteenth, DebugOverlayEnabled: false, TempoOverride: null);

        var result = await coordinator.RunAsync(parameters, CancellationToken.None);

        Assert.Single(pipeline.CapturedRequests);
        Assert.Same(track, pipeline.CapturedRequests[0].Track);
        Assert.True(result.PipelineResult.Success);
        Assert.Null(result.PipelineResult.LaneStats);
        Assert.Equal(GenStage.Completed, coordinator.Stage.Value);
        Assert.Equal(GenerationState.Complete, coordinator.State.Value);

        coordinator.Dispose();
    }

    [Fact]
    public async Task RunAsync_AppliesTempoOverride()
    {
        var track = new ImportedAudioTrack(
            originalPath: "/tmp/source.wav",
            storedPath: "/tmp/stored.wav",
            relativeStoragePath: "stored.wav",
            displayName: "Test Track",
            fileSizeBytes: 1024,
            durationMilliseconds: 120_000);

        var tempoOverride = new TempoOverride(Bpm: 150, OffsetSeconds: 0.025, StepSeconds: 0.125, ForceQuantization: true);

        var pipelineResult = GenerationPipelineResult.CreateSuccess(
            beatmap: new AiGenerationResult { Success = true, BeatmapPath = "beatmap.bsm" },
            analysis: null,
            waveform: null,
            usedFallback: false,
            playbackAvailable: true,
            usedOfflineDecode: false,
            offlineFallbackEncountered: false,
            warning: null,
            logs: Array.Empty<string>());

        var pipeline = new FakePipeline(() => sequence(pipelineResult));
        var coordinator = new GenerationCoordinator(pipeline, action => action());

        var parameters = new GenerationParams(track, DetectionSensitivity: 60, Quantization: QuantizationGrid.Sixteenth, DebugOverlayEnabled: false, TempoOverride: tempoOverride);

        await coordinator.RunAsync(parameters, CancellationToken.None);

        var options = pipeline.CapturedRequests.Single().Options;
        Assert.Equal(150, options.ForcedBpm);
        Assert.Equal(0.025, options.ForcedOffsetSeconds);
        Assert.Equal(0.125, options.ForcedStepSeconds);
        Assert.True(options.ForceQuantization);

        coordinator.Dispose();
    }

    private static async IAsyncEnumerable<PipelineProgress> sequence(GenerationPipelineResult finalResult)
    {
        yield return new PipelineProgress(
            Phase: PipelinePhase.AudioInit,
            Percent: 0.1,
            Status: "Initialising",
            Warning: null,
            Analysis: null,
            Waveform: null,
            Result: null,
            Timestamp: DateTimeOffset.UtcNow,
            StageId: GenerationStageId.ModelLoad,
            StageProgress: 0.2,
            StageLabel: GenerationStagePlan.StageLabels[GenerationStageId.ModelLoad],
            StageDurations: new Dictionary<GenerationStageId, double>());

        await Task.Yield();

        yield return new PipelineProgress(
            Phase: PipelinePhase.Completed,
            Percent: 1.0,
            Status: "Completed",
            Warning: null,
            Analysis: null,
            Waveform: null,
            Result: finalResult,
            Timestamp: DateTimeOffset.UtcNow,
            StageId: GenerationStageId.Finalise,
            StageProgress: 1.0,
            StageLabel: GenerationStagePlan.StageLabels[GenerationStageId.Finalise],
            StageDurations: new Dictionary<GenerationStageId, double>());
    }

    private sealed class FakePipeline : IGenerationPipeline
    {
        private readonly Func<IAsyncEnumerable<PipelineProgress>> sequenceFactory;

        public FakePipeline(Func<IAsyncEnumerable<PipelineProgress>> sequenceFactory)
        {
            this.sequenceFactory = sequenceFactory;
        }

        public List<GenerationPipelineRequest> CapturedRequests { get; } = new();

        public IAsyncEnumerable<PipelineProgress> RunAsync(GenerationPipelineRequest request, CancellationToken cancellationToken)
        {
            CapturedRequests.Add(request);
            return sequenceFactory();
        }
    }
}