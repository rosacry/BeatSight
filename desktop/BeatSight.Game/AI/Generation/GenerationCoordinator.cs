using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.AI;
using BeatSight.Game.Audio;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.Mapping;
using BeatSight.Game.Localization;
using BeatSight.Game.Services.Generation;
using osu.Framework.Bindables;
using osu.Framework.Logging;

namespace BeatSight.Game.AI.Generation
{
    public enum GenStage
    {
        Idle,
        AudioInit,
        ModelLoad,
        Separation,
        OnsetDetection,
        TempoEstimation,
        Quantization,
        Drafting,
        Finalising,
        Completed,
        Cancelled,
        Failed
    }

    public readonly record struct GenerationParams(
        ImportedAudioTrack Track,
        int DetectionSensitivity,
        QuantizationGrid Quantization,
        bool DebugOverlayEnabled);

    public readonly record struct GenerationProgress(
        GenStage Stage,
        double? Percent,
        string? Message,
        TimeSpan Elapsed,
        IReadOnlyDictionary<string, double>? Metrics = null,
        bool IsHeartbeat = false,
        GenerationStageId StageId = GenerationStageId.ModelLoad,
            double StageProgress = 0,
            string StageLabel = "",
            IReadOnlyDictionary<GenerationStageId, double>? StageDurations = null);

    public readonly record struct GenerationResult(Guid RunId, GenerationPipelineResult PipelineResult);

    public interface IGenerationCoordinator
    {
        Bindable<GenStage> Stage { get; }
        Bindable<GenerationProgress> Progress { get; }
        Bindable<DetectionStats?> Stats { get; }
        Bindable<DrumOnsetAnalysis?> Analysis { get; }
        Bindable<WaveformData?> Waveform { get; }
        Bindable<GenerationState> State { get; }
        Task<GenerationResult> RunAsync(GenerationParams snapshot, CancellationToken cancellationToken, IProgress<GenerationProgress>? observer = null);
        void Cancel();
    }

    public sealed class GenerationCoordinator : IGenerationCoordinator, IDisposable
    {
        private static readonly GenerationProgress idleProgress = new GenerationProgress(GenStage.Idle, 0, "Idle", TimeSpan.Zero, null, false, GenerationStageId.ModelLoad, 0, GenerationStagePlan.StageLabels[GenerationStageId.ModelLoad], new Dictionary<GenerationStageId, double>());

        private readonly IGenerationPipeline pipeline;
        private readonly Action<Action> schedule;
        private readonly Bindable<GenStage> stage = new Bindable<GenStage>(GenStage.Idle);
        private readonly Bindable<GenerationProgress> progress = new Bindable<GenerationProgress>(idleProgress);
        private readonly Bindable<DetectionStats?> stats = new Bindable<DetectionStats?>();
        private readonly Bindable<DrumOnsetAnalysis?> analysis = new Bindable<DrumOnsetAnalysis?>();
        private readonly Bindable<WaveformData?> waveform = new Bindable<WaveformData?>();
        private readonly Bindable<GenerationState> generationState = new Bindable<GenerationState>(GenerationState.Idle);
        private readonly object runLock = new object();

        private CancellationTokenSource? currentCts;
        private Task<GenerationResult>? currentTask;
        private Guid? currentRunId;
        private Timer? heartbeatTimer;
        private GenerationProgress lastProgress = idleProgress;
        private readonly Dictionary<GenerationStageId, TimeSpan> stageStartOffsets = new();
        private readonly Dictionary<GenerationStageId, double> completedStageDurations = new();
        private bool disposed;

        public GenerationCoordinator(IGenerationPipeline pipeline, Action<Action> schedule)
        {
            this.pipeline = pipeline ?? throw new ArgumentNullException(nameof(pipeline));
            this.schedule = schedule ?? throw new ArgumentNullException(nameof(schedule));
        }

        public Bindable<GenStage> Stage => stage;
        public Bindable<GenerationProgress> Progress => progress;
        public Bindable<DetectionStats?> Stats => stats;
        public Bindable<DrumOnsetAnalysis?> Analysis => analysis;
        public Bindable<WaveformData?> Waveform => waveform;
        public Bindable<GenerationState> State => generationState;

        public Task<GenerationResult> RunAsync(GenerationParams snapshot, CancellationToken cancellationToken, IProgress<GenerationProgress>? observer = null)
        {
            if (disposed)
                throw new ObjectDisposedException(nameof(GenerationCoordinator));

            lock (runLock)
            {
                if (currentTask is { IsCompleted: false })
                    throw new InvalidOperationException("Generation already in progress.");

                if (snapshot.Track == null)
                    throw new ArgumentException("Generation snapshot missing track.", nameof(snapshot));

                var runId = Guid.NewGuid();
                currentRunId = runId;
                currentCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                var linkedToken = currentCts.Token;
                var stopwatch = Stopwatch.StartNew();
                stats.Value = null;
                analysis.Value = null;
                waveform.Value = null;
                stageStartOffsets.Clear();
                completedStageDurations.Clear();
                stageStartOffsets[GenerationStageId.ModelLoad] = TimeSpan.Zero;
                completedStageDurations[GenerationStageId.ModelLoad] = 0;
                startHeartbeat(runId, observer, stopwatch);
                updateState(runId, GenerationState.Preparing);
                transition(runId, GenStage.AudioInit, 0.01, "Preparing audio", stopwatch, observer, null, GenerationStageId.ModelLoad, 0.0, GenerationStagePlan.StageLabels[GenerationStageId.ModelLoad]);

                var request = new GenerationPipelineRequest(snapshot.Track, new AiGenerationOptions
                {
                    DetectionSensitivity = snapshot.DetectionSensitivity,
                    QuantizationGrid = snapshot.Quantization,
                    ExportDebugAnalysis = snapshot.DebugOverlayEnabled,
                    EnableDrumSeparation = true,
                    ConfidenceThreshold = 0.3,
                    MaxSnapErrorMilliseconds = 12.0
                });

                currentTask = Task.Run(async () =>
                {
                    GenerationPipelineResult? finalResult = null;
                    try
                    {
                        await foreach (var update in pipeline.RunAsync(request, linkedToken).ConfigureAwait(false))
                        {
                            if (linkedToken.IsCancellationRequested)
                                break;

                            if (update.Result != null)
                                finalResult = update.Result;

                            if (update.IsHeartbeat)
                            {
                                sustainHeartbeat(runId, stopwatch, observer);
                                continue;
                            }

                            handleUpdate(runId, snapshot, update, stopwatch, observer);
                            if (update.Waveform != null)
                            {
                                var wave = update.Waveform;
                                schedule(() =>
                                {
                                    if (currentRunId == runId)
                                        waveform.Value = wave;
                                });
                            }
                        }
                    }
                    catch (OperationCanceledException)
                    {
                        transition(runId, GenStage.Cancelled, null, "Generation cancelled", stopwatch, observer, null, GenerationStageId.Finalise, 1.0, GenerationStagePlan.StageLabels[GenerationStageId.Finalise]);
                        finalResult ??= GenerationPipelineResult.CreateCancelled(false, true, false, false, null, null, null, Array.Empty<string>());
                    }
                    catch (Exception ex)
                    {
                        Logger.Error(ex, "Generation coordinator failed");
                        transition(runId, GenStage.Failed, null, ex.Message, stopwatch, observer, null, GenerationStageId.Finalise, 1.0, GenerationStagePlan.StageLabels[GenerationStageId.Finalise]);
                        finalResult ??= GenerationPipelineResult.CreateFailure(ex.Message, false, true, false, false, null, null, null, Array.Empty<string>(), null);
                    }
                    finally
                    {
                        stopwatch.Stop();
                        stopHeartbeat();
                        lock (runLock)
                        {
                            currentCts?.Dispose();
                            currentCts = null;
                            currentRunId = null;
                        }
                        schedule(() =>
                        {
                            waveform.Value = null;
                            analysis.Value = null;
                        });
                    }

                    if (finalResult == null)
                        finalResult = GenerationPipelineResult.CreateFailure("Generation ended unexpectedly.", false, true, false, false, null, null, null, Array.Empty<string>(), null);

                    var terminalStage = finalResult.Success ? GenStage.Completed : finalResult.Cancelled ? GenStage.Cancelled : GenStage.Failed;
                    transition(runId, GenStage.Finalising, 0.98, "Finalising", stopwatch, observer, null, GenerationStageId.Finalise, 0.75, GenerationStagePlan.StageLabels[GenerationStageId.Finalise]);
                    transition(runId, terminalStage, 1.0, messageForResult(finalResult), stopwatch, observer, null, GenerationStageId.Finalise, 1.0, GenerationStagePlan.StageLabels[GenerationStageId.Finalise]);

                    return new GenerationResult(runId, finalResult);
                }, CancellationToken.None);

                return currentTask;
            }
        }

        public void Cancel()
        {
            lock (runLock)
            {
                currentCts?.Cancel();
            }
        }

        private void handleUpdate(Guid runId, GenerationParams snapshot, PipelineProgress update, Stopwatch stopwatch, IProgress<GenerationProgress>? observer)
        {
            var nextStage = mapStage(update, progress.Value.Stage);
            var message = update.Status;
            var percent = update.Percent;
            var stageId = update.StageId;
            var stageProgress = update.StageProgress;
            var stageLabel = update.StageLabel;
            IReadOnlyDictionary<string, double>? metrics = null;

            if (update.Analysis != null)
            {
                var detectionStats = DetectionStats.FromAnalysis(update.Analysis, snapshot.DetectionSensitivity, snapshot.Quantization);
                metrics = detectionStats.ToMetrics();
                schedule(() =>
                {
                    if (currentRunId == runId)
                    {
                        stats.Value = detectionStats;
                        analysis.Value = update.Analysis;
                    }
                });

                transition(runId, GenStage.OnsetDetection, percent, message, stopwatch, observer, metrics, stageId, stageProgress, stageLabel);
                transition(runId, GenStage.TempoEstimation, percent, tempoMessage(detectionStats), stopwatch, observer, metrics, GenerationStageId.TempoGrid, 0.0, GenerationStagePlan.StageLabels[GenerationStageId.TempoGrid]);
                return;
            }

            if (update.Phase == PipelinePhase.Quantize && stats.Value != null)
                metrics = stats.Value.ToMetrics();

            transition(runId, nextStage, percent, message, stopwatch, observer, metrics, stageId, stageProgress, stageLabel);
        }

        private static string tempoMessage(DetectionStats stats) =>
            stats.EstimatedBpm > 0
                ? $"Tempo estimate {stats.EstimatedBpm:0.#} BPM"
                : "Tempo estimate unavailable";

        private static string messageForResult(GenerationPipelineResult result)
        {
            if (result.Success)
                return "Generation complete";
            if (result.Cancelled)
                return "Generation cancelled";
            return string.IsNullOrWhiteSpace(result.FailureReason) ? BeatSightStrings.GenerationFailed.ToString() : result.FailureReason!;
        }

        private GenStage mapStage(PipelineProgress update, GenStage current)
        {
            return update.Phase switch
            {
                PipelinePhase.AudioInit => GenStage.AudioInit,
                PipelinePhase.Separate when update.Status.Contains("Loading", StringComparison.OrdinalIgnoreCase) => GenStage.ModelLoad,
                PipelinePhase.Separate => GenStage.Separation,
                PipelinePhase.DecodePcm => GenStage.AudioInit,
                PipelinePhase.DetectOnsets => GenStage.OnsetDetection,
                PipelinePhase.Quantize => GenStage.Quantization,
                PipelinePhase.BuildDraft => GenStage.Drafting,
                PipelinePhase.Completed => GenStage.Completed,
                PipelinePhase.Cancelled => GenStage.Cancelled,
                PipelinePhase.Faulted => GenStage.Failed,
                _ => current
            };
        }

        private void transition(Guid runId, GenStage stageTarget, double? percent, string? message, Stopwatch stopwatch, IProgress<GenerationProgress>? observer, IReadOnlyDictionary<string, double>? metrics = null, GenerationStageId? stageId = null, double? stageProgress = null, string? stageLabel = null)
        {
            var effectiveStageId = stageId ?? lastProgress.StageId;
            var effectiveStageProgress = stageProgress ?? lastProgress.StageProgress;
            var effectiveStageLabel = stageLabel ?? lastProgress.StageLabel;
            if (string.IsNullOrWhiteSpace(effectiveStageLabel))
                effectiveStageLabel = GenerationStagePlan.StageLabels.TryGetValue(effectiveStageId, out var label) ? label : effectiveStageId.ToString();

            var now = stopwatch.Elapsed;
            var previousStageId = lastProgress.StageId;
            updateStageTracking(previousStageId, effectiveStageId, now);

            if (isTerminalStage(stageTarget))
                finalizeStageDuration(effectiveStageId, now);

            var stageDurationsSnapshot = snapshotStageDurations(effectiveStageId, now);

            var progressPayload = new GenerationProgress(stageTarget, percent, message, now, metrics, false, effectiveStageId, effectiveStageProgress, effectiveStageLabel, stageDurationsSnapshot);
            lastProgress = progressPayload;
            var stateCandidate = resolveState(stageTarget, effectiveStageId);

            schedule(() =>
            {
                if (currentRunId != runId)
                    return;

                if (stage.Value != stageTarget)
                    stage.Value = stageTarget;
                progress.Value = progressPayload;
                if (generationState.Value != stateCandidate)
                    generationState.Value = stateCandidate;
            });
            observer?.Report(progressPayload);
        }

        private void sustainHeartbeat(Guid runId, Stopwatch stopwatch, IProgress<GenerationProgress>? observer)
        {
            var snapshot = lastProgress with { Elapsed = stopwatch.Elapsed, IsHeartbeat = true };
            lastProgress = snapshot;
            schedule(() =>
            {
                if (currentRunId != runId)
                    return;

                progress.Value = snapshot;
            });
            observer?.Report(snapshot);
        }

        private void startHeartbeat(Guid runId, IProgress<GenerationProgress>? observer, Stopwatch stopwatch)
        {
            stopHeartbeat();
            heartbeatTimer = new Timer(_ =>
            {
                var snapshot = lastProgress with { Elapsed = stopwatch.Elapsed, IsHeartbeat = true };
                schedule(() =>
                {
                    if (currentRunId != runId)
                        return;

                    progress.Value = snapshot;
                });
                observer?.Report(snapshot);
            }, null, TimeSpan.FromMilliseconds(500), TimeSpan.FromMilliseconds(500));
        }

        private void updateStageTracking(GenerationStageId previousStage, GenerationStageId currentStage, TimeSpan now)
        {
            if (previousStage != currentStage)
            {
                finalizeStageDuration(previousStage, now);
                stageStartOffsets[currentStage] = now;
                return;
            }

            if (!stageStartOffsets.ContainsKey(currentStage))
                stageStartOffsets[currentStage] = now;
        }

        private static bool isTerminalStage(GenStage stage) => stage is GenStage.Completed or GenStage.Cancelled or GenStage.Failed;

        private void finalizeStageDuration(GenerationStageId stageId, TimeSpan now)
        {
            if (!stageStartOffsets.TryGetValue(stageId, out var start))
                return;

            double duration = Math.Max((now - start).TotalMilliseconds, 0);
            if (completedStageDurations.TryGetValue(stageId, out var existing))
                completedStageDurations[stageId] = existing + duration;
            else
                completedStageDurations[stageId] = duration;

            stageStartOffsets.Remove(stageId);
        }

        private IReadOnlyDictionary<GenerationStageId, double> snapshotStageDurations(GenerationStageId currentStage, TimeSpan now)
        {
            var snapshot = new Dictionary<GenerationStageId, double>(completedStageDurations);

            if (stageStartOffsets.TryGetValue(currentStage, out var start))
            {
                double duration = Math.Max((now - start).TotalMilliseconds, 0);
                snapshot[currentStage] = duration;
            }

            return snapshot;
        }

        private void stopHeartbeat()
        {
            heartbeatTimer?.Dispose();
            heartbeatTimer = null;
        }

        public void Dispose()
        {
            if (disposed)
                return;

            disposed = true;
            stopHeartbeat();
            generationState.Value = GenerationState.Idle;
            lock (runLock)
            {
                currentCts?.Cancel();
                currentCts?.Dispose();
                currentCts = null;
                currentRunId = null;
            }
        }
        private void updateState(Guid runId, GenerationState newState)
        {
            schedule(() =>
            {
                if (currentRunId != runId)
                    return;

                if (generationState.Value != newState)
                    generationState.Value = newState;
            });
        }

        private static GenerationState resolveState(GenStage stage, GenerationStageId stageId)
        {
            return stage switch
            {
                GenStage.Idle => GenerationState.Idle,
                GenStage.AudioInit => stageId switch
                {
                    GenerationStageId.Separation => GenerationState.SeparatingStems,
                    _ => GenerationState.Preparing
                },
                GenStage.ModelLoad => GenerationState.LoadingDemucs,
                GenStage.Separation => GenerationState.SeparatingStems,
                GenStage.OnsetDetection => GenerationState.DetectingOnsets,
                GenStage.TempoEstimation => GenerationState.EstimatingTempo,
                GenStage.Quantization => GenerationState.EstimatingTempo,
                GenStage.Drafting => GenerationState.DraftingNotes,
                GenStage.Finalising => GenerationState.Finalizing,
                GenStage.Completed => GenerationState.Complete,
                GenStage.Cancelled => GenerationState.Cancelled,
                GenStage.Failed => GenerationState.Error,
                _ => GenerationState.Preparing
            };
        }
    }

    public sealed record DetectionSectionStats(int Index, double Start, double End, int HitCount, double HitsPerSecond);

    public sealed record DetectionStats(
        double EstimatedBpm,
        int PeakCount,
        double AverageConfidence,
        double MaxDensity,
        IReadOnlyList<DetectionSectionStats> Sections,
        int Sensitivity,
        QuantizationGrid Grid,
        double QuantizationCoverage,
        double QuantizationMeanErrorMs,
        double QuantizationMedianErrorMs,
        double QuantizationOffsetSeconds,
        double QuantizationStepSeconds,
        double ConfidenceScore,
        IReadOnlyList<QuantizationCandidate> QuantizationCandidates)
    {
        public static DetectionStats FromAnalysis(DrumOnsetAnalysis analysis, int sensitivity, QuantizationGrid grid)
        {
            if (analysis == null)
                throw new ArgumentNullException(nameof(analysis));

            double avgConfidence = 0;
            if (analysis.Peaks.Count > 0)
                avgConfidence = Math.Clamp(analysis.Peaks.Sum(p => p.Confidence) / analysis.Peaks.Count, 0.0, 1.0);

            var sections = new List<DetectionSectionStats>(analysis.Sections.Count);
            double maxDensity = 0;
            foreach (var section in analysis.Sections)
            {
                double density = section.Density;
                if (density > maxDensity)
                    maxDensity = density;

                sections.Add(new DetectionSectionStats(section.Index, section.Start, section.End, section.Count, density));
            }

            var quant = analysis.Quantization;
            double coverage = quant?.Coverage ?? 0;
            double meanError = quant?.MeanErrorMilliseconds ?? 0;
            double medianError = quant?.MedianErrorMilliseconds ?? 0;
            double offsetSeconds = quant?.OffsetSeconds ?? 0;
            double stepSeconds = quant?.StepSeconds ?? 0;
            var candidates = quant?.Candidates ?? Array.Empty<QuantizationCandidate>();

            double confidenceScore = computeConfidenceScore(sections, analysis.Peaks.Count, avgConfidence, coverage, meanError, maxDensity);

            return new DetectionStats(analysis.Tempo, analysis.Peaks.Count, avgConfidence, maxDensity, sections, sensitivity, grid, coverage, meanError, medianError, offsetSeconds, stepSeconds, confidenceScore, candidates);
        }

        public IReadOnlyDictionary<string, double> ToMetrics()
        {
            var metrics = new Dictionary<string, double>
            {
                ["peaks"] = PeakCount,
                ["tempo"] = EstimatedBpm,
                ["avg_confidence"] = AverageConfidence,
                ["max_density"] = MaxDensity,
                ["sensitivity"] = Sensitivity,
                ["grid"] = (double)Grid,
                ["coverage"] = QuantizationCoverage,
                ["mean_error_ms"] = QuantizationMeanErrorMs,
                ["median_error_ms"] = QuantizationMedianErrorMs,
                ["offset_seconds"] = QuantizationOffsetSeconds,
                ["step_seconds"] = QuantizationStepSeconds,
                ["confidence_score"] = ConfidenceScore
            };

            if (Sections.Count > 0)
                metrics["section_count"] = Sections.Count;

            if (QuantizationCandidates.Count > 0)
                metrics["tempo_candidate_count"] = QuantizationCandidates.Count;

            if (TryGetTempoAmbiguityMessage(out _))
                metrics["tempo_alias_detected"] = 1;

            return metrics;
        }

        public bool TryGetLowConfidenceMessage(out string message)
        {
            var issues = new List<string>();

            if (PeakCount < 16)
                issues.Add($"Only {PeakCount} peaks detected");

            if (AverageConfidence < 0.45)
                issues.Add($"Average confidence {AverageConfidence:0.00}");

            if (QuantizationCoverage < 0.5)
                issues.Add($"Grid coverage {QuantizationCoverage:P0}");

            if (QuantizationMeanErrorMs > 18)
                issues.Add($"Mean error {QuantizationMeanErrorMs:0.#} ms");

            bool lowScore = ConfidenceScore < 0.6;
            if (!lowScore && issues.Count == 0)
            {
                message = string.Empty;
                return false;
            }

            var tips = new List<string>();
            if (PeakCount < 16)
                tips.Add("raise sensitivity");
            if (QuantizationCoverage < 0.5)
                tips.Add("try a different quantization grid");
            if (AverageConfidence < 0.45)
                tips.Add("use a cleaner mix or isolate drums more");

            string tipsText = tips.Count > 0 ? $" Try to {string.Join(" / ", tips)}." : string.Empty;
            string scoreText = lowScore ? $"Score {ConfidenceScore:P0}. " : string.Empty;
            string issueText = issues.Count > 0 ? string.Join("; ", issues) : "Confidence score below target";

            message = $"Low detection confidence — {issueText}. {scoreText}{tipsText}".Trim();
            return true;
        }

        public IReadOnlyList<string> GetConfidenceIssues()
        {
            var issues = new List<string>();

            if (PeakCount < 16)
                issues.Add("Not enough drum peaks detected");

            if (AverageConfidence < 0.45)
                issues.Add("Onset confidence is weak");

            if (QuantizationCoverage < 0.5)
                issues.Add("Quantization grid coverage is low");

            if (QuantizationMeanErrorMs > 18)
                issues.Add("Quantization error is high");

            return issues;
        }

        private static double computeConfidenceScore(IReadOnlyList<DetectionSectionStats> sections, int peakCount, double averageConfidence, double coverage, double meanError, double maxDensity)
        {
            double coverageScore = Math.Clamp(coverage, 0, 1);
            double confidenceScore = Math.Clamp(averageConfidence, 0, 1);
            double densityScore = sections.Count > 0
                ? Math.Clamp(maxDensity / 5.0, 0, 1)
                : Math.Clamp(maxDensity / 5.0, 0, 1);
            double errorScore = 1 - Math.Clamp(meanError / 20.0, 0, 1);

            double weighted = coverageScore * 0.45
                              + confidenceScore * 0.25
                              + densityScore * 0.15
                              + errorScore * 0.15;

            if (peakCount < 18)
            {
                double penalty = Math.Clamp((18 - peakCount) / 40.0, 0, 0.25);
                weighted -= penalty;
            }

            return Math.Clamp(weighted, 0, 1);
        }

        public bool TryGetTempoAmbiguityMessage(out string message)
        {
            message = string.Empty;

            if (QuantizationCandidates.Count == 0)
                return false;

            var primary = QuantizationCandidates[0];
            var alias = TempoAuthority.FindAliasCandidate(primary, QuantizationCandidates);
            if (!alias.HasValue)
                return false;

            message = $"Tempo ambiguous (~{primary.Bpm:0.#} vs ~{alias.Value.Bpm:0.#} BPM). Try halving/doubling the tempo or switching the quantization grid.";
            return true;
        }
    }
}
