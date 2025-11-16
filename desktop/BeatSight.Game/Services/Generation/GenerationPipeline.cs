using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;
using BeatSight.Game.AI;
using BeatSight.Game.AI.Generation;
using BeatSight.Game.Audio;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.Localization;
using BeatSight.Game.Mapping;
using BeatSight.Game.Services.Analysis;
using BeatSight.Game.Services.Decode;
using BeatSight.Game.Services.Separation;
using Newtonsoft.Json.Linq;
using osu.Framework.Logging;

namespace BeatSight.Game.Services.Generation
{
    public enum PipelinePhase
    {
        AudioInit,
        Separate,
        DecodePcm,
        DetectOnsets,
        Quantize,
        BuildDraft,
        Completed,
        Cancelled,
        Faulted
    }
    public readonly record struct PipelineProgress(
        PipelinePhase Phase,
        double Percent,
        string Status,
        string? Warning,
        DrumOnsetAnalysis? Analysis,
        WaveformData? Waveform,
        GenerationPipelineResult? Result,
        DateTimeOffset Timestamp,
        GenerationStageId StageId,
        double StageProgress,
        string StageLabel,
        bool IsHeartbeat = false,
        IReadOnlyDictionary<GenerationStageId, double>? StageDurations = null)
    {
        public bool IsTerminal => Phase is PipelinePhase.Completed or PipelinePhase.Cancelled or PipelinePhase.Faulted;
        public string PhaseName => Phase.ToString();
    }

    public sealed class GenerationPipeline : IGenerationPipeline, IDisposable
    {
        private readonly AudioEngine audioEngine;
        private readonly DecodeService decodeService;
        private readonly OnsetDetectionService onsetDetectionService;
        private readonly AiBeatmapGenerator beatmapGenerator;
        private readonly IDemucsBackend primaryBackend;
        private readonly IDemucsBackend fallbackBackend;
        private readonly TimeSpan demucsLoadTimeout = TimeSpan.FromSeconds(20);
        private bool disposed;

        public GenerationPipeline(AudioEngine audioEngine, DecodeService decodeService, OnsetDetectionService onsetDetectionService, AiBeatmapGenerator beatmapGenerator, IDemucsBackend primaryBackend, IDemucsBackend fallbackBackend)
        {
            this.audioEngine = audioEngine ?? throw new ArgumentNullException(nameof(audioEngine));
            this.decodeService = decodeService ?? throw new ArgumentNullException(nameof(decodeService));
            this.onsetDetectionService = onsetDetectionService ?? throw new ArgumentNullException(nameof(onsetDetectionService));
            this.beatmapGenerator = beatmapGenerator ?? throw new ArgumentNullException(nameof(beatmapGenerator));
            this.primaryBackend = primaryBackend ?? throw new ArgumentNullException(nameof(primaryBackend));
            this.fallbackBackend = fallbackBackend ?? throw new ArgumentNullException(nameof(fallbackBackend));
        }

        public IAsyncEnumerable<PipelineProgress> RunAsync(GenerationPipelineRequest request, CancellationToken cancellationToken)
        {
            if (disposed)
                throw new ObjectDisposedException(nameof(GenerationPipeline));

            if (request == null)
                throw new ArgumentNullException(nameof(request));

            var channel = Channel.CreateUnbounded<PipelineProgress>(new UnboundedChannelOptions
            {
                SingleReader = true,
                SingleWriter = true
            });

            _ = Task.Run(() => executeAsync(request, channel.Writer, cancellationToken), CancellationToken.None);

            return channel.Reader.ReadAllAsync(cancellationToken);
        }

        private async Task executeAsync(GenerationPipelineRequest request, ChannelWriter<PipelineProgress> writer, CancellationToken cancellationToken)
        {
            var logs = new List<string> { "[gen] pipeline start" };
            var stopwatch = Stopwatch.StartNew();

            SeparationOutput? separationOutput = null;
            WaveformData? waveform = null;
            DrumOnsetAnalysis? latestAnalysis = null;
            GenerationPipelineResult? finalResult = null;
            bool usedFallback = false;
            bool playbackAvailable = audioEngine.IsReady || audioEngine.Manager != null;
            bool offlineDecodeUsed = false;
            bool offlineFallbackEncountered = false;
            string? delayedOfflineWarning = null;
            double averageDetectionConfidence = 0;
            int detectedPeakCount = 0;
            var stageDurationsCapture = new Dictionary<GenerationStageId, double>();
            DetectionStats? finalDetectionStats = null;

            await using var heartbeat = new HeartbeatEmitter(writer, cancellationToken);
            var context = new PipelineContext(writer, heartbeat, cancellationToken);

            try
            {
                IDemucsBackend backend;
                using (new PhaseScope(PipelinePhase.AudioInit, GenerationStageId.ModelLoad, logs, stageDurationsCapture))
                {
                    await context.EmitAsync(PipelinePhase.AudioInit, GenerationStageId.ModelLoad, 0.0, "Initialising audio engine...").ConfigureAwait(false);

                    bool ready = audioEngine.IsReady;
                    if (!ready)
                    {
                        logs.Add("[gen] audio engine pending – waiting for readiness");
                        await context.EmitAsync(PipelinePhase.AudioInit, GenerationStageId.ModelLoad, 0.15, "Waiting for audio playback engine...").ConfigureAwait(false);

                        ready = await audioEngine.WaitForReadyAsync(TimeSpan.FromSeconds(8), cancellationToken).ConfigureAwait(false);
                    }

                    if (ready)
                    {
                        await context.EmitAsync(PipelinePhase.AudioInit, GenerationStageId.ModelLoad, 0.35, "Audio engine ready").ConfigureAwait(false);
                        logs.Add("[gen] audio engine ready");
                    }
                    else
                    {
                        offlineDecodeUsed = true;
                        offlineFallbackEncountered = true;
                        string offlineMessage = "Audio device slow or unavailable — continuing with offline decode.";
                        if (audioEngine.Manager == null)
                        {
                            playbackAvailable = false;
                            offlineMessage += " Playback will be disabled until the audio engine recovers.";
                        }

                        delayedOfflineWarning = offlineMessage;
                        await context.EmitAsync(PipelinePhase.AudioInit, GenerationStageId.ModelLoad, 0.35, offlineMessage).ConfigureAwait(false);
                    }

                    backend = await prepareBackendAsync(context, logs, cancellationToken).ConfigureAwait(false);
                    usedFallback = !ReferenceEquals(backend, primaryBackend);
                }

                var separationProgress = new Progress<double>(value =>
                {
                    if (cancellationToken.IsCancellationRequested)
                        return;

                    double stageProgress = Math.Clamp(value, 0, 1);
                    string message = usedFallback ? "Passthrough separation" : $"Separating drums... {(int)(stageProgress * 100)}%";
                    context.EmitVolatile(PipelinePhase.Separate, GenerationStageId.Separation, stageProgress, message);
                });

                if (request.Options.EnableDrumSeparation)
                {
                    using (new PhaseScope(PipelinePhase.Separate, GenerationStageId.Separation, logs, stageDurationsCapture))
                    {
                        string startMessage = usedFallback
                            ? "Fallback separation – using passthrough audio"
                            : $"Separating drums with {backend.Name}...";

                        await context.EmitAsync(PipelinePhase.Separate, GenerationStageId.Separation, 0.0, startMessage).ConfigureAwait(false);

                        var output = await backend.SeparateAsync(request.AudioPath, cancellationToken, separationProgress).ConfigureAwait(false);
                        separationOutput = output;

                        string completionMessage = output.IsPassthrough
                            ? "Using original mix (no drum stem available)"
                            : "Drum stem ready";

                        context.EmitVolatile(PipelinePhase.Separate, GenerationStageId.Separation, 1.0, completionMessage);
                        logs.Add($"[gen] separation {(output.IsPassthrough ? "passthrough" : "complete")} backend={backend.Name} drums_path={output.DrumsPath}");
                    }
                }
                else
                {
                    logs.Add("[gen] separation disabled by options");
                    await context.EmitAsync(PipelinePhase.Separate, GenerationStageId.Separation, 1.0, "Drum separation skipped").ConfigureAwait(false);
                }

                if (separationOutput.HasValue)
                    request.Options.EnableDrumSeparation = !separationOutput.Value.IsPassthrough;
                else
                    request.Options.EnableDrumSeparation = false;

                var decodeProgress = new Progress<double>(value =>
                {
                    if (cancellationToken.IsCancellationRequested)
                        return;

                    double stageProgress = 0.65 + Math.Clamp(value, 0, 1) * 0.35;
                    context.EmitVolatile(PipelinePhase.DecodePcm, GenerationStageId.Separation, Math.Clamp(stageProgress, 0, 1), $"Decoding audio... {(int)(Math.Clamp(value, 0, 1) * 100)}%");
                });

                DecodedAudio decoded;
                using (new PhaseScope(PipelinePhase.DecodePcm, GenerationStageId.Separation, logs, stageDurationsCapture))
                {
                    string decodePath = separationOutput?.DrumsPath ?? request.AudioPath;
                    decoded = await decodeService.DecodeAsync(decodePath, progress: decodeProgress, cancellationToken: cancellationToken).ConfigureAwait(false);
                    waveform = decoded.Waveform;
                    context.Waveform = waveform;
                    context.EmitVolatile(PipelinePhase.DecodePcm, GenerationStageId.Separation, 1.0, "Audio decoded");
                }

                var detectionParameters = new OnsetDetectionParameters(
                    request.Options.DetectionSensitivity,
                    request.Options.QuantizationGrid,
                    request.Options.MaxSnapErrorMilliseconds);

                var detectionProgress = new Progress<double>(value =>
                {
                    if (cancellationToken.IsCancellationRequested)
                        return;

                    double stageProgress = Math.Clamp(value, 0, 1);
                    context.EmitVolatile(PipelinePhase.DetectOnsets, GenerationStageId.OnsetDetection, stageProgress, $"Detecting onsets... {(int)(stageProgress * 100)}%");
                });

                DetectionIntermediate detection;
                using (new PhaseScope(PipelinePhase.DetectOnsets, GenerationStageId.OnsetDetection, logs, stageDurationsCapture))
                {
                    await context.EmitAsync(PipelinePhase.DetectOnsets, GenerationStageId.OnsetDetection, 0.0, "Analysing transients...").ConfigureAwait(false);
                    detection = await onsetDetectionService.DetectOnsetsAsync(decoded, detectionParameters, detectionProgress, cancellationToken).ConfigureAwait(false);

                    var provisional = new QuantizationSummary(gridToString(request.Options.QuantizationGrid), 0, 0, 0, 0, 0);
                    latestAnalysis = new DrumOnsetAnalysis(
                        detection.SampleRate,
                        detection.HopLength,
                        detection.EstimatedTempo,
                        detection.Envelope,
                        detection.Threshold,
                        detection.Peaks,
                        provisional,
                        detection.Sections);

                    context.Analysis = latestAnalysis;
                    context.EmitVolatile(PipelinePhase.DetectOnsets, GenerationStageId.OnsetDetection, 1.0, $"Detected {detection.Peaks.Count} onsets");
                    logs.Add($"[gen] detection complete (peaks={detection.Peaks.Count})");
                    detectedPeakCount = detection.Peaks.Count;
                    averageDetectionConfidence = detection.Peaks.Count > 0 ? detection.Peaks.Average(p => p.Confidence) : 0;
                }

                var quantizeProgress = new Progress<double>(value =>
                {
                    if (cancellationToken.IsCancellationRequested)
                        return;

                    double stageProgress = Math.Clamp(value, 0, 1);
                    context.EmitVolatile(PipelinePhase.Quantize, GenerationStageId.TempoGrid, stageProgress, "Quantizing grid...");
                });

                QuantizationResult quantization;
                using (new PhaseScope(PipelinePhase.Quantize, GenerationStageId.TempoGrid, logs, stageDurationsCapture))
                {
                    await context.EmitAsync(PipelinePhase.Quantize, GenerationStageId.TempoGrid, 0.0, "Calculating tempo & downbeat...").ConfigureAwait(false);
                    quantization = await onsetDetectionService.QuantizeAsync(detection, detectionParameters, quantizeProgress, cancellationToken).ConfigureAwait(false);
                    latestAnalysis = quantization.Analysis;
                    context.Analysis = latestAnalysis;
                    context.EmitVolatile(PipelinePhase.Quantize, GenerationStageId.TempoGrid, 1.0, "Quantization complete");
                    var detectionStats = DetectionStats.FromAnalysis(latestAnalysis, request.Options.DetectionSensitivity, request.Options.QuantizationGrid);
                    finalDetectionStats = detectionStats;
                    detectedPeakCount = detectionStats.PeakCount;
                    averageDetectionConfidence = detectionStats.AverageConfidence;
                    logs.Add($"[gen] detection quality score={detectionStats.ConfidenceScore:0.00} peaks={detectedPeakCount} coverage={detectionStats.QuantizationCoverage:0.000}");

                    var tempoDecision = TempoAuthority.Evaluate(request.Options, quantization);
                    if (tempoDecision.HasSummary)
                    {
                        if (!string.IsNullOrWhiteSpace(tempoDecision.Warning))
                        {
                            context.AppendWarning(tempoDecision.Warning);
                            logs.Add($"[gen] tempo warning: {tempoDecision.Warning}");
                        }

                        logs.Add(tempoDecision.BuildLog());
                    }

                    bool lowConfidence = detectionStats.ConfidenceScore < 0.6;
                    if (lowConfidence)
                    {
                        request.Options.ForceQuantization = false;
                        request.Options.DownbeatConfidence = Math.Min(detectionStats.QuantizationCoverage, 0.35);
                        string lowConfidenceMessage = detectionStats.TryGetLowConfidenceMessage(out var issues)
                            ? issues
                            : "Low detection confidence – try raising sensitivity or switching the quantization grid.";
                        context.AppendWarning(lowConfidenceMessage);
                        logs.Add($"[gen] detection warning: low confidence (score={detectionStats.ConfidenceScore:0.00}, peaks={detectedPeakCount}, avg_conf={averageDetectionConfidence:0.###}, coverage={detectionStats.QuantizationCoverage:0.###})");
                        logs.Add("[gen] tempo forcing disabled due to confidence check");
                    }
                }

                var aiProgress = new Progress<AiGenerationProgress>(update =>
                {
                    if (cancellationToken.IsCancellationRequested)
                        return;

                    double local = Math.Clamp(update.Progress ?? 0, 0, 1);
                    string message = string.IsNullOrWhiteSpace(update.Message) ? "Drafting beatmap..." : update.Message;
                    context.EmitVolatile(PipelinePhase.BuildDraft, GenerationStageId.DraftMapping, local, message);
                    if (!string.IsNullOrWhiteSpace(update.Message))
                        logs.Add($"[gen] python: {update.Message}");
                });

                AiGenerationResult aiResult;
                GenerationLaneStats? laneTelemetry = null;
                using (new PhaseScope(PipelinePhase.BuildDraft, GenerationStageId.DraftMapping, logs, stageDurationsCapture))
                {
                    await context.EmitAsync(PipelinePhase.BuildDraft, GenerationStageId.DraftMapping, 0.0, "Drafting beatmap...").ConfigureAwait(false);
                    aiResult = await beatmapGenerator.GenerateAsync(request.Track, request.Options, aiProgress, cancellationToken, separationOutput?.DrumsPath).ConfigureAwait(false);
                    logs.Add($"[gen] beatmap generation {(aiResult.Success ? "success" : "fail")}");
                    if (aiResult.Beatmap != null)
                    {
                        int noteCount = aiResult.Beatmap.HitObjects?.Count ?? 0;
                        double appliedBpm = aiResult.Beatmap.Timing?.Bpm ?? request.Options.ForcedBpm ?? finalDetectionStats?.EstimatedBpm ?? 0;
                        double appliedOffsetSeconds = aiResult.Beatmap.Timing != null
                            ? aiResult.Beatmap.Timing.Offset / 1000.0
                            : request.Options.ForcedOffsetSeconds ?? 0;
                        logs.Add($"[gen] beatmap summary notes={noteCount} bpm={appliedBpm:0.###} grid={request.Options.QuantizationGrid} offset={appliedOffsetSeconds:0.000}s");
                    }
                }

                if (!aiResult.Success)
                {
                    if (!playbackAvailable)
                    {
                        if (audioEngine.IsReady)
                        {
                            logs.Add("[gen] audio engine became ready before failure");
                            playbackAvailable = true;
                            offlineDecodeUsed = false;
                            delayedOfflineWarning = null;
                        }
                        else if (!string.IsNullOrWhiteSpace(delayedOfflineWarning))
                        {
                            context.AppendWarning(delayedOfflineWarning);
                        }
                    }

                    string failureReason = aiResult.Error ?? BeatSightStrings.GenerationFailed.ToString();
                    double failureDurationMs = stopwatch.Elapsed.TotalMilliseconds;
                    var failureStageDurations = finalizeStageDurations(stageDurationsCapture, failureDurationMs);
                    finalResult = GenerationPipelineResult.CreateFailure(
                        failureReason,
                        usedFallback,
                        playbackAvailable,
                        offlineDecodeUsed,
                        offlineFallbackEncountered,
                        context.Warning,
                        latestAnalysis,
                        waveform,
                        logs,
                        aiResult,
                        laneStats: laneTelemetry,
                        stageDurations: failureStageDurations,
                        totalDurationMs: failureDurationMs,
                        detectionStats: finalDetectionStats);
                    await context.EmitAsync(PipelinePhase.Faulted, GenerationStageId.DraftMapping, 0.95, finalResult.FailureReason ?? failureReason, resultOverride: finalResult).ConfigureAwait(false);
                    return;
                }

                if (aiResult.Beatmap?.HitObjects is { Count: > 0 } hitObjects)
                {
                    DrumLaneHeuristics.ApplyToBeatmap(aiResult.Beatmap);

                    double bpm = aiResult.Beatmap.Timing?.Bpm ?? request.Options.ForcedBpm ?? 0;
                    double offsetMs = aiResult.Beatmap.Timing?.Offset ?? (int)Math.Round(Math.Clamp(request.Options.ForcedOffsetSeconds ?? 0, -600, 600) * 1000.0);
                    bool multiLane = hitObjects.Any(h => h.Lane.HasValue);
                    var laneSummary = hitObjects
                        .GroupBy(h => h.Lane ?? DrumLaneHeuristics.ResolveLane(h.Component))
                        .OrderBy(g => g.Key)
                        .Select(g => $"L{g.Key}:{g.Count()}");

                    logs.Add($"[gen] notes={hitObjects.Count} bpm={bpm:0.###} offset={offsetMs / 1000.0:0.000}s lanes={(multiLane ? "multi" : "single")} dist=[{string.Join(' ', laneSummary)}]");
                }

                if (!string.IsNullOrWhiteSpace(aiResult.DebugAnalysisPath) && File.Exists(aiResult.DebugAnalysisPath))
                {
                    try
                    {
                        var debugJson = JObject.Parse(File.ReadAllText(aiResult.DebugAnalysisPath));
                        var laneStats = debugJson["generation"]?["lane_stats"];
                        if (laneStats != null)
                        {
                            int cymbalSwitches = laneStats.Value<int?>("cymbal_switches") ?? 0;
                            int tomSwitches = laneStats.Value<int?>("tom_switches") ?? 0;
                            laneTelemetry = new GenerationLaneStats(cymbalSwitches, tomSwitches);
                            logs.Add($"[gen] lane stats cymbal_switches={cymbalSwitches} tom_switches={tomSwitches}");
                        }
                    }
                    catch (Exception ex)
                    {
                        logs.Add($"[gen] lane stats parse failed: {ex.Message}");
                    }
                }

                if (!string.IsNullOrWhiteSpace(aiResult.DrumStemPath))
                    logs.Add($"[gen] drum stem persisted path={aiResult.DrumStemPath}");

                if (!playbackAvailable)
                {
                    if (audioEngine.IsReady)
                    {
                        logs.Add("[gen] audio engine became ready before completion");
                        playbackAvailable = true;
                        offlineDecodeUsed = false;
                        delayedOfflineWarning = null;
                        await context.EmitAsync(PipelinePhase.AudioInit, GenerationStageId.ModelLoad, 0.35, "Audio engine ready (playback restored)").ConfigureAwait(false);
                    }
                    else if (!string.IsNullOrWhiteSpace(delayedOfflineWarning))
                    {
                        context.AppendWarning(delayedOfflineWarning);
                    }
                }

                playbackAvailable = playbackAvailable || audioEngine.IsReady || audioEngine.Manager != null;

                bool engineReady = audioEngine.IsReady || audioEngine.Manager != null;
                if (engineReady)
                {
                    if (!playbackAvailable)
                        logs.Add("[gen] audio engine recovered during run; enabling playback");
                    playbackAvailable = true;
                }
                else
                {
                    playbackAvailable = false;
                    if (!string.IsNullOrWhiteSpace(delayedOfflineWarning))
                        context.AppendWarning(delayedOfflineWarning);
                }

                double successDurationMs = stopwatch.Elapsed.TotalMilliseconds;
                var successStageDurations = finalizeStageDurations(stageDurationsCapture, successDurationMs);
                finalResult = GenerationPipelineResult.CreateSuccess(aiResult, latestAnalysis, waveform, usedFallback, playbackAvailable, offlineDecodeUsed, offlineFallbackEncountered, context.Warning, logs, detectionStats: finalDetectionStats, stageDurations: successStageDurations, totalDurationMs: successDurationMs, laneStats: laneTelemetry);
                await context.EmitAsync(PipelinePhase.Completed, GenerationStageId.Finalise, 1.0, "AI beatmap ready!", resultOverride: finalResult).ConfigureAwait(false);
                logs.Add("[gen] pipeline complete");
            }
            catch (OperationCanceledException)
            {
                logs.Add("[gen] pipeline cancelled");
                if (!playbackAvailable)
                {
                    if (audioEngine.IsReady)
                    {
                        playbackAvailable = true;
                        offlineDecodeUsed = false;
                        delayedOfflineWarning = null;
                    }
                    else if (!string.IsNullOrWhiteSpace(delayedOfflineWarning))
                        context.AppendWarning(delayedOfflineWarning);
                }

                playbackAvailable = playbackAvailable || audioEngine.IsReady || audioEngine.Manager != null;

                double cancelledDurationMs = stopwatch.Elapsed.TotalMilliseconds;
                var cancelledStageDurations = finalizeStageDurations(stageDurationsCapture, cancelledDurationMs);
                finalResult = GenerationPipelineResult.CreateCancelled(usedFallback, playbackAvailable, offlineDecodeUsed, offlineFallbackEncountered, context.Warning, latestAnalysis, waveform, logs, stageDurations: cancelledStageDurations, totalDurationMs: cancelledDurationMs, detectionStats: finalDetectionStats);
                await context.EmitAsync(PipelinePhase.Cancelled, GenerationStageId.Finalise, 1.0, "Generation cancelled", resultOverride: finalResult).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                Logger.Error(ex, "Generation pipeline failed");
                logs.Add($"[gen] pipeline error: {ex.Message}");
                if (!playbackAvailable)
                {
                    if (audioEngine.IsReady)
                    {
                        playbackAvailable = true;
                        offlineDecodeUsed = false;
                        delayedOfflineWarning = null;
                    }
                    else if (!string.IsNullOrWhiteSpace(delayedOfflineWarning))
                        context.AppendWarning(delayedOfflineWarning);
                }

                playbackAvailable = playbackAvailable || audioEngine.IsReady || audioEngine.Manager != null;

                double failureDurationMs = stopwatch.Elapsed.TotalMilliseconds;
                var failureStageDurations = finalizeStageDurations(stageDurationsCapture, failureDurationMs);
                finalResult = GenerationPipelineResult.CreateFailure(
                    ex.Message,
                    usedFallback,
                    playbackAvailable,
                    offlineDecodeUsed,
                    offlineFallbackEncountered,
                    context.Warning,
                    latestAnalysis,
                    waveform,
                    logs,
                    beatmap: null,
                    laneStats: null,
                    stageDurations: failureStageDurations,
                    totalDurationMs: failureDurationMs,
                    detectionStats: finalDetectionStats);
                await context.EmitAsync(PipelinePhase.Faulted, GenerationStageId.Finalise, 1.0, ex.Message, resultOverride: finalResult).ConfigureAwait(false);
            }
            finally
            {
                stopwatch.Stop();
                var finalDurations = finalizeStageDurations(stageDurationsCapture, stopwatch.Elapsed.TotalMilliseconds);
                if (finalDurations.Count > 0)
                {
                    var summary = string.Join(", ", finalDurations.Select(kvp => $"{GenerationStagePlan.GetLabel(kvp.Key)}={kvp.Value:0}ms"));
                    logs.Add($"[gen] phase summary {summary}");
                }
                logs.Add($"[gen] pipeline finished in {stopwatch.ElapsedMilliseconds}ms");
                separationOutput?.Dispose();
                writer.TryComplete();
            }
        }

        private async Task<IDemucsBackend> prepareBackendAsync(PipelineContext context, List<string> logs, CancellationToken cancellationToken)
        {
            try
            {
                await context.EmitAsync(PipelinePhase.Separate, GenerationStageId.ModelLoad, 0.5, $"Loading Demucs model {primaryBackend.Name}...").ConfigureAwait(false);
                await primaryBackend.LoadModelAsync(cancellationToken).WaitAsync(demucsLoadTimeout, cancellationToken).ConfigureAwait(false);
                logs.Add("[gen] demucs primary ready");
                await context.EmitAsync(PipelinePhase.Separate, GenerationStageId.ModelLoad, 1.0, $"Demucs {primaryBackend.Name} ready").ConfigureAwait(false);
                return primaryBackend;
            }
            catch (TimeoutException ex)
            {
                logs.Add($"[gen] demucs timeout: {ex.Message}");
            }
            catch (Exception ex) when (!cancellationToken.IsCancellationRequested)
            {
                logs.Add($"[gen] demucs error: {ex.Message}");
            }

            context.AppendWarning("Demucs not available; continuing with passthrough.");
            logs.Add("[gen] demucs fallback to passthrough");
            await context.EmitAsync(PipelinePhase.Separate, GenerationStageId.ModelLoad, 1.0, "Falling back to passthrough separation").ConfigureAwait(false);

            try
            {
                await fallbackBackend.LoadModelAsync(cancellationToken).ConfigureAwait(false);
            }
            catch
            {
                // passthrough backend requires no setup
            }

            return fallbackBackend;
        }

        private sealed class HeartbeatEmitter : IAsyncDisposable
        {
            private static readonly TimeSpan interval = TimeSpan.FromMilliseconds(500);
            private readonly ChannelWriter<PipelineProgress> writer;
            private readonly CancellationTokenSource cts;
            private readonly Task loop;
            private readonly object sync = new();
            private PipelineProgress? lastProgress;

            public HeartbeatEmitter(ChannelWriter<PipelineProgress> writer, CancellationToken externalToken)
            {
                this.writer = writer;
                cts = CancellationTokenSource.CreateLinkedTokenSource(externalToken);
                loop = Task.Run(async () =>
                {
                    try
                    {
                        while (!cts.Token.IsCancellationRequested)
                        {
                            await Task.Delay(interval, cts.Token).ConfigureAwait(false);
                            PipelineProgress? snapshot;
                            lock (sync)
                                snapshot = lastProgress;

                            if (snapshot.HasValue)
                            {
                                var heartbeat = snapshot.Value with
                                {
                                    Timestamp = DateTimeOffset.UtcNow,
                                    IsHeartbeat = true,
                                    Result = null
                                };

                                writer.TryWrite(heartbeat);
                            }
                        }
                    }
                    catch (TaskCanceledException)
                    {
                        // expected when disposed
                    }
                }, CancellationToken.None);
            }

            public void Update(PipelineProgress progress)
            {
                lock (sync)
                    lastProgress = progress;
            }

            public async ValueTask DisposeAsync()
            {
                cts.Cancel();
                try
                {
                    await loop.ConfigureAwait(false);
                }
                catch
                {
                    // suppress loop cancellation exceptions
                }

                cts.Dispose();
            }
        }

        private sealed class PipelineContext
        {
            private readonly ChannelWriter<PipelineProgress> writer;
            private readonly HeartbeatEmitter heartbeat;
            private readonly CancellationToken cancellationToken;
            private readonly object warningLock = new();

            private GenerationStageId currentStage = GenerationStageId.ModelLoad;
            private double currentStageProgress;
            private string currentStageLabel = GenerationStagePlan.GetLabel(GenerationStageId.ModelLoad);

            public PipelineContext(ChannelWriter<PipelineProgress> writer, HeartbeatEmitter heartbeat, CancellationToken cancellationToken)
            {
                this.writer = writer;
                this.heartbeat = heartbeat;
                this.cancellationToken = cancellationToken;
            }

            public DrumOnsetAnalysis? Analysis { get; set; }
            public WaveformData? Waveform { get; set; }
            public string? Warning { get; private set; }

            public void AppendWarning(string message)
            {
                if (string.IsNullOrWhiteSpace(message))
                    return;

                lock (warningLock)
                {
                    if (string.IsNullOrWhiteSpace(Warning))
                    {
                        Warning = message;
                        return;
                    }

                    if (Warning.Contains(message, StringComparison.OrdinalIgnoreCase))
                        return;

                    Warning = $"{Warning} • {message}";
                }
            }

            public ValueTask EmitAsync(
                PipelinePhase phase,
                GenerationStageId stageId,
                double stageProgress,
                string status,
                string? warningOverride = null,
                DrumOnsetAnalysis? analysisOverride = null,
                WaveformData? waveformOverride = null,
                GenerationPipelineResult? resultOverride = null)
            {
                var progress = createProgress(phase, stageId, stageProgress, status, warningOverride, analysisOverride, waveformOverride, resultOverride, false);
                return writeAsync(progress);
            }

            public void EmitVolatile(
                PipelinePhase phase,
                GenerationStageId stageId,
                double stageProgress,
                string status,
                string? warningOverride = null,
                DrumOnsetAnalysis? analysisOverride = null,
                WaveformData? waveformOverride = null,
                GenerationPipelineResult? resultOverride = null)
            {
                var progress = createProgress(phase, stageId, stageProgress, status, warningOverride, analysisOverride, waveformOverride, resultOverride, false);
                if (writer.TryWrite(progress))
                    heartbeat.Update(progress);
            }

            private PipelineProgress createProgress(
                PipelinePhase phase,
                GenerationStageId stageId,
                double stageProgress,
                string status,
                string? warningOverride,
                DrumOnsetAnalysis? analysisOverride,
                WaveformData? waveformOverride,
                GenerationPipelineResult? resultOverride,
                bool isHeartbeat)
            {
                currentStage = stageId;
                currentStageProgress = stageProgress;
                currentStageLabel = GenerationStagePlan.GetLabel(stageId);

                var effectiveWarning = warningOverride ?? Warning;
                double percent = GenerationStagePlan.ToWeightedProgress(stageId, stageProgress);
                return new PipelineProgress(phase, percent, status, effectiveWarning, analysisOverride ?? Analysis, waveformOverride ?? Waveform, resultOverride, DateTimeOffset.UtcNow, stageId, stageProgress, currentStageLabel, isHeartbeat);
            }

            private async ValueTask writeAsync(PipelineProgress progress)
            {
                await writer.WriteAsync(progress, cancellationToken).ConfigureAwait(false);
                heartbeat.Update(progress);
            }
        }

        private sealed class PhaseScope : IDisposable
        {
            private readonly PipelinePhase phase;
            private readonly List<string> logs;
            private readonly Stopwatch stopwatch = Stopwatch.StartNew();
            private readonly IDictionary<GenerationStageId, double> stageDurations;
            private readonly GenerationStageId stageId;

            public PhaseScope(PipelinePhase phase, GenerationStageId stageId, List<string> logs, IDictionary<GenerationStageId, double> stageDurations)
            {
                this.phase = phase;
                this.stageId = stageId;
                this.logs = logs;
                this.stageDurations = stageDurations;
                logs.Add($"[gen] stage={phase} ({GenerationStagePlan.GetLabel(stageId)}) start");
            }

            public void Dispose()
            {
                stopwatch.Stop();
                logs.Add($"[gen] stage={phase} ({GenerationStagePlan.GetLabel(stageId)}) done in {stopwatch.ElapsedMilliseconds}ms");
                double elapsed = stopwatch.Elapsed.TotalMilliseconds;
                if (stageDurations.TryGetValue(stageId, out var existing))
                    stageDurations[stageId] = existing + elapsed;
                else
                    stageDurations[stageId] = elapsed;
            }
        }

        private static IReadOnlyDictionary<GenerationStageId, double> finalizeStageDurations(IDictionary<GenerationStageId, double> captured, double totalMilliseconds)
        {
            var result = new Dictionary<GenerationStageId, double>();

            foreach (var kvp in captured)
            {
                if (kvp.Value <= 0)
                    continue;

                result[kvp.Key] = kvp.Value;
            }

            double accounted = result.Values.Sum();
            double remainder = Math.Max(0, totalMilliseconds - accounted);
            if (remainder > 1)
            {
                if (result.TryGetValue(GenerationStageId.Finalise, out var existing))
                    result[GenerationStageId.Finalise] = existing + remainder;
                else
                    result[GenerationStageId.Finalise] = remainder;
            }

            return result;
        }

        private static string gridToString(QuantizationGrid grid) => grid switch
        {
            QuantizationGrid.Quarter => "quarter",
            QuantizationGrid.Eighth => "eighth",
            QuantizationGrid.Sixteenth => "sixteenth",
            QuantizationGrid.Triplet => "triplet",
            QuantizationGrid.ThirtySecond => "thirtysecond",
            _ => "sixteenth"
        };

        public void Dispose()
        {
            if (disposed)
                return;

            disposed = true;
            try
            {
                _ = primaryBackend.DisposeAsync();
            }
            catch
            {
                // ignore disposal failures on shutdown
            }

            try
            {
                _ = fallbackBackend.DisposeAsync();
            }
            catch
            {
                // ignore disposal failures on shutdown
            }
        }
    }

    public sealed class GenerationPipelineRequest
    {
        public GenerationPipelineRequest(ImportedAudioTrack track, AiGenerationOptions options)
        {
            Track = track ?? throw new ArgumentNullException(nameof(track));
            Options = options ?? throw new ArgumentNullException(nameof(options));
        }

        public ImportedAudioTrack Track { get; }
        public AiGenerationOptions Options { get; }
        public string AudioPath => Track.StoredPath;
    }

    public sealed class GenerationLaneStats
    {
        public GenerationLaneStats(int cymbalSwitches, int tomSwitches)
        {
            CymbalSwitches = Math.Max(0, cymbalSwitches);
            TomSwitches = Math.Max(0, tomSwitches);
        }

        public int CymbalSwitches { get; }
        public int TomSwitches { get; }
        public int TotalSwitches => CymbalSwitches + TomSwitches;
    }

    public sealed class GenerationPipelineResult
    {
        private GenerationPipelineResult()
        {
        }

        public bool Success { get; private init; }
        public bool Cancelled { get; private init; }
        public bool UsedFallback { get; private init; }
        public bool PlaybackAvailable { get; private init; } = true;
        public bool UsedOfflineDecode { get; private init; }
        public bool OfflineFallbackEncountered { get; private init; }
        public string? Warning { get; private init; }
        public string? FailureReason { get; private init; }
        public AiGenerationResult? Beatmap { get; private init; }
        public DrumOnsetAnalysis? Analysis { get; private init; }
        public WaveformData? Waveform { get; private init; }
        public DetectionStats? DetectionStats { get; private init; }
        public IReadOnlyList<string> Logs { get; private init; } = Array.Empty<string>();
        public GenerationLaneStats? LaneStats { get; private init; }
        public IReadOnlyDictionary<GenerationStageId, double> StageDurations { get; private init; } = new Dictionary<GenerationStageId, double>();
        public double TotalDurationMs { get; private init; }

        public static GenerationPipelineResult CreateSuccess(AiGenerationResult beatmap, DrumOnsetAnalysis? analysis, WaveformData? waveform, bool usedFallback, bool playbackAvailable, bool usedOfflineDecode, bool offlineFallbackEncountered, string? warning, IReadOnlyList<string> logs, DetectionStats? detectionStats = null, IReadOnlyDictionary<GenerationStageId, double>? stageDurations = null, double totalDurationMs = 0, GenerationLaneStats? laneStats = null)
        {
            return new GenerationPipelineResult
            {
                Success = true,
                Beatmap = beatmap,
                Analysis = analysis,
                Waveform = waveform,
                UsedFallback = usedFallback,
                PlaybackAvailable = playbackAvailable,
                UsedOfflineDecode = usedOfflineDecode,
                OfflineFallbackEncountered = offlineFallbackEncountered,
                Warning = warning,
                DetectionStats = detectionStats,
                Logs = logs,
                LaneStats = laneStats,
                StageDurations = stageDurations ?? new Dictionary<GenerationStageId, double>(),
                TotalDurationMs = totalDurationMs
            };
        }

        public static GenerationPipelineResult CreateFailure(string reason, bool usedFallback, bool playbackAvailable, bool usedOfflineDecode, bool offlineFallbackEncountered, string? warning, DrumOnsetAnalysis? analysis, WaveformData? waveform, IReadOnlyList<string> logs, AiGenerationResult? beatmap, GenerationLaneStats? laneStats = null, IReadOnlyDictionary<GenerationStageId, double>? stageDurations = null, double totalDurationMs = 0, DetectionStats? detectionStats = null)
        {
            return new GenerationPipelineResult
            {
                Success = false,
                FailureReason = reason,
                UsedFallback = usedFallback,
                PlaybackAvailable = playbackAvailable,
                UsedOfflineDecode = usedOfflineDecode,
                OfflineFallbackEncountered = offlineFallbackEncountered,
                Warning = warning,
                Analysis = analysis,
                Waveform = waveform,
                DetectionStats = detectionStats,
                Logs = logs,
                Beatmap = beatmap,
                LaneStats = laneStats,
                StageDurations = stageDurations ?? new Dictionary<GenerationStageId, double>(),
                TotalDurationMs = totalDurationMs
            };
        }

        public static GenerationPipelineResult CreateCancelled(bool usedFallback, bool playbackAvailable, bool usedOfflineDecode, bool offlineFallbackEncountered, string? warning, DrumOnsetAnalysis? analysis, WaveformData? waveform, IReadOnlyList<string> logs, GenerationLaneStats? laneStats = null, IReadOnlyDictionary<GenerationStageId, double>? stageDurations = null, double totalDurationMs = 0, DetectionStats? detectionStats = null)
        {
            return new GenerationPipelineResult
            {
                Success = false,
                Cancelled = true,
                UsedFallback = usedFallback,
                PlaybackAvailable = playbackAvailable,
                UsedOfflineDecode = usedOfflineDecode,
                OfflineFallbackEncountered = offlineFallbackEncountered,
                Warning = warning,
                Analysis = analysis,
                Waveform = waveform,
                DetectionStats = detectionStats,
                Logs = logs,
                LaneStats = laneStats,
                StageDurations = stageDurations ?? new Dictionary<GenerationStageId, double>(),
                TotalDurationMs = totalDurationMs
            };
        }
    }
}
