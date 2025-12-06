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
        private readonly Func<CancellationToken, IAsyncEnumerable<PipelineProgress>> sequenceFactory;

        public FakePipeline(Func<IAsyncEnumerable<PipelineProgress>> simpleFactory)
            : this(_ => simpleFactory())
        {
        }

        public FakePipeline(Func<CancellationToken, IAsyncEnumerable<PipelineProgress>> sequenceFactory)
        {
            this.sequenceFactory = sequenceFactory;
        }

        public List<GenerationPipelineRequest> CapturedRequests { get; } = new();

        public IAsyncEnumerable<PipelineProgress> RunAsync(GenerationPipelineRequest request, CancellationToken cancellationToken)
        {
            CapturedRequests.Add(request);
            return sequenceFactory(cancellationToken);
        }
    }

    [Fact]
    public async Task RunAsync_CancellationPropagates()
    {
        var track = new ImportedAudioTrack(
            originalPath: "/tmp/source.wav",
            storedPath: "/tmp/stored.wav",
            relativeStoragePath: "stored.wav",
            displayName: "Test Track",
            fileSizeBytes: 1024,
            durationMilliseconds: 120_000);

        using var cts = new CancellationTokenSource();
        var pipelineStarted = new TaskCompletionSource<bool>();
        var firstYieldProcessed = new TaskCompletionSource<bool>();

        var pipeline = new FakePipeline(ct => slowSequence(ct, pipelineStarted, firstYieldProcessed));
        var coordinator = new GenerationCoordinator(pipeline, action => action());

        var parameters = new GenerationParams(track, DetectionSensitivity: 60, Quantization: QuantizationGrid.Sixteenth, DebugOverlayEnabled: false, TempoOverride: null);

        var resultTask = coordinator.RunAsync(parameters, cts.Token);

        // Wait for pipeline to actually start AND first yield to be processed before cancelling
        await pipelineStarted.Task;
        await firstYieldProcessed.Task;
        
        // Small delay to ensure coordinator has processed the first item
        await Task.Delay(50);
        
        cts.Cancel();

        var result = await resultTask;

        Assert.True(result.PipelineResult.Cancelled);
        Assert.Equal(GenerationState.Cancelled, coordinator.State.Value);

        coordinator.Dispose();

        static async IAsyncEnumerable<PipelineProgress> slowSequence([System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct, TaskCompletionSource<bool> started, TaskCompletionSource<bool> firstYieldProcessed)
        {
            // Signal that pipeline has started
            started.TrySetResult(true);

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

            // Signal that the first yield has been processed (we've returned from the yield)
            firstYieldProcessed.TrySetResult(true);

            // Simulate a slow operation that can be cancelled - use longer delay for reliability
            await Task.Delay(500, ct);

            ct.ThrowIfCancellationRequested();

            yield return new PipelineProgress(
                Phase: PipelinePhase.Completed,
                Percent: 1.0,
                Status: "Completed",
                Warning: null,
                Analysis: null,
                Waveform: null,
                Result: GenerationPipelineResult.CreateSuccess(
                    beatmap: new AiGenerationResult { Success = true },
                    analysis: null,
                    waveform: null,
                    usedFallback: false,
                    playbackAvailable: true,
                    usedOfflineDecode: false,
                    offlineFallbackEncountered: false,
                    warning: null,
                    logs: Array.Empty<string>()),
                Timestamp: DateTimeOffset.UtcNow,
                StageId: GenerationStageId.Finalise,
                StageProgress: 1.0,
                StageLabel: GenerationStagePlan.StageLabels[GenerationStageId.Finalise],
                StageDurations: new Dictionary<GenerationStageId, double>());
        }
    }

    [Fact]
    public async Task RunAsync_ErrorStateOnPipelineException()
    {
        var track = new ImportedAudioTrack(
            originalPath: "/tmp/source.wav",
            storedPath: "/tmp/stored.wav",
            relativeStoragePath: "stored.wav",
            displayName: "Test Track",
            fileSizeBytes: 1024,
            durationMilliseconds: 120_000);

        var pipeline = new FakePipeline(() => faultingSequence());
        var coordinator = new GenerationCoordinator(pipeline, action => action());

        var parameters = new GenerationParams(track, DetectionSensitivity: 60, Quantization: QuantizationGrid.Sixteenth, DebugOverlayEnabled: false, TempoOverride: null);

        var result = await coordinator.RunAsync(parameters, CancellationToken.None);

        Assert.False(result.PipelineResult.Success);
        Assert.Equal(GenerationState.Error, coordinator.State.Value);
        Assert.Contains("simulated", result.PipelineResult.FailureReason, StringComparison.OrdinalIgnoreCase);

        coordinator.Dispose();

        static async IAsyncEnumerable<PipelineProgress> faultingSequence()
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

            throw new InvalidOperationException("Simulated pipeline failure");
        }
    }

    [Fact]
    public async Task RunAsync_StateTransitionsCorrectly()
    {
        var track = new ImportedAudioTrack(
            originalPath: "/tmp/source.wav",
            storedPath: "/tmp/stored.wav",
            relativeStoragePath: "stored.wav",
            displayName: "Test Track",
            fileSizeBytes: 1024,
            durationMilliseconds: 120_000);

        var capturedStates = new List<GenerationState>();

        var pipelineResult = GenerationPipelineResult.CreateSuccess(
            beatmap: new AiGenerationResult { Success = true },
            analysis: null,
            waveform: null,
            usedFallback: false,
            playbackAvailable: true,
            usedOfflineDecode: false,
            offlineFallbackEncountered: false,
            warning: null,
            logs: Array.Empty<string>());

        var pipeline = new FakePipeline(() => multiStageSequence(pipelineResult));
        var coordinator = new GenerationCoordinator(pipeline, action => action());
        coordinator.State.BindValueChanged(e => capturedStates.Add(e.NewValue));

        var parameters = new GenerationParams(track, DetectionSensitivity: 60, Quantization: QuantizationGrid.Sixteenth, DebugOverlayEnabled: false, TempoOverride: null);

        await coordinator.RunAsync(parameters, CancellationToken.None);

        // Should have transitioned through preparation states to complete
        Assert.Contains(GenerationState.Preparing, capturedStates);
        Assert.Contains(GenerationState.Complete, capturedStates);
        Assert.Equal(GenerationState.Complete, coordinator.State.Value);

        coordinator.Dispose();

        static async IAsyncEnumerable<PipelineProgress> multiStageSequence(GenerationPipelineResult finalResult)
        {
            yield return new PipelineProgress(
                Phase: PipelinePhase.AudioInit,
                Percent: 0.05,
                Status: "Preparing",
                Warning: null,
                Analysis: null,
                Waveform: null,
                Result: null,
                Timestamp: DateTimeOffset.UtcNow,
                StageId: GenerationStageId.ModelLoad,
                StageProgress: 0.1,
                StageLabel: GenerationStagePlan.StageLabels[GenerationStageId.ModelLoad],
                StageDurations: new Dictionary<GenerationStageId, double>());

            await Task.Yield();

            yield return new PipelineProgress(
                Phase: PipelinePhase.Separate,
                Percent: 0.4,
                Status: "Separating stems",
                Warning: null,
                Analysis: null,
                Waveform: null,
                Result: null,
                Timestamp: DateTimeOffset.UtcNow,
                StageId: GenerationStageId.Separation,
                StageProgress: 0.5,
                StageLabel: GenerationStagePlan.StageLabels[GenerationStageId.Separation],
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
    }

    [Fact]
    public void Cancel_WhileIdle_DoesNotThrow()
    {
        var pipeline = new FakePipeline(() => emptySequence());
        var coordinator = new GenerationCoordinator(pipeline, action => action());

        // Should not throw when cancelling while idle
        coordinator.Cancel();

        Assert.Equal(GenStage.Idle, coordinator.Stage.Value);

        coordinator.Dispose();

        static async IAsyncEnumerable<PipelineProgress> emptySequence()
        {
            await Task.CompletedTask;
            yield break;
        }
    }

    [Fact]
    public async Task RunAsync_ThrowsWhenAlreadyRunning()
    {
        var track = new ImportedAudioTrack(
            originalPath: "/tmp/source.wav",
            storedPath: "/tmp/stored.wav",
            relativeStoragePath: "stored.wav",
            displayName: "Test Track",
            fileSizeBytes: 1024,
            durationMilliseconds: 120_000);

        var tcs = new TaskCompletionSource<bool>();

        var pipeline = new FakePipeline(_ => blockingSequence(tcs));
        var coordinator = new GenerationCoordinator(pipeline, action => action());

        var parameters = new GenerationParams(track, DetectionSensitivity: 60, Quantization: QuantizationGrid.Sixteenth, DebugOverlayEnabled: false, TempoOverride: null);

        // Start first run
        var firstRun = coordinator.RunAsync(parameters, CancellationToken.None);

        // Try to start second run while first is still going
        await Assert.ThrowsAsync<InvalidOperationException>(() => coordinator.RunAsync(parameters, CancellationToken.None));

        // Complete the first run
        tcs.SetResult(true);
        await firstRun;

        coordinator.Dispose();

        static async IAsyncEnumerable<PipelineProgress> blockingSequence(TaskCompletionSource<bool> signal)
        {
            yield return new PipelineProgress(
                Phase: PipelinePhase.AudioInit,
                Percent: 0.1,
                Status: "Waiting",
                Warning: null,
                Analysis: null,
                Waveform: null,
                Result: null,
                Timestamp: DateTimeOffset.UtcNow,
                StageId: GenerationStageId.ModelLoad,
                StageProgress: 0.2,
                StageLabel: GenerationStagePlan.StageLabels[GenerationStageId.ModelLoad],
                StageDurations: new Dictionary<GenerationStageId, double>());

            await signal.Task;

            yield return new PipelineProgress(
                Phase: PipelinePhase.Completed,
                Percent: 1.0,
                Status: "Done",
                Warning: null,
                Analysis: null,
                Waveform: null,
                Result: GenerationPipelineResult.CreateSuccess(
                    beatmap: new AiGenerationResult { Success = true },
                    analysis: null,
                    waveform: null,
                    usedFallback: false,
                    playbackAvailable: true,
                    usedOfflineDecode: false,
                    offlineFallbackEncountered: false,
                    warning: null,
                    logs: Array.Empty<string>()),
                Timestamp: DateTimeOffset.UtcNow,
                StageId: GenerationStageId.Finalise,
                StageProgress: 1.0,
                StageLabel: GenerationStagePlan.StageLabels[GenerationStageId.Finalise],
                StageDurations: new Dictionary<GenerationStageId, double>());
        }
    }
}