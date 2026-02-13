using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Metadata;
using Newtonsoft.Json;
using osu.Framework.Logging;
using osu.Framework.Platform;

namespace BeatSight.Game.AI
{
    /// <summary>
    /// Options for AI beatmap generation.
    /// Must be kept in sync with backend app/schemas/ai_jobs.py AIGenerationOptions.
    /// </summary>
    public class AiGenerationOptions
    {
        public double ConfidenceThreshold { get; set; } = 0.3;  // Lowered from 0.7 to detect more real drum hits
        public bool EnableDrumSeparation { get; set; } = true;
        public string? PythonExecutablePath { get; set; }
        public AiPipelineMode PipelineMode { get; set; } = AiPipelineMode.Gameplay;
        public bool AutoSensitivity { get; set; }
        public bool AutoQuantization { get; set; }
        public int DetectionSensitivity { get; set; } = 60;
        public QuantizationGrid QuantizationGrid { get; set; } = QuantizationGrid.Sixteenth;
        public double MaxSnapErrorMilliseconds { get; set; } = 12.0;
        public bool ExportDebugAnalysis { get; set; } = true;
        public double? ForcedBpm { get; set; }
        public double? ForcedOffsetSeconds { get; set; }
        public double? ForcedStepSeconds { get; set; }
        public bool ForceQuantization { get; set; }
        public double? DownbeatConfidence { get; set; }
        public IReadOnlyList<double>? TempoCandidates { get; set; }
        public double? StartTime { get; set; }
        public double? EndTime { get; set; }

        /// <summary>
        /// Use ML model for drum classification (vs. rule-based).
        /// Matches backend AIGenerationOptions.use_ml_classifier.
        /// </summary>
        public bool UseMlClassifier { get; set; } = true;

        /// <summary>
        /// Path to the ML model checkpoint (.pt or .pth file).
        /// If not set, Python will use its default model path.
        /// </summary>
        public string? MlModelPath { get; set; }

        /// <summary>
        /// Device for ML inference: "cuda", "cpu", or "mps".
        /// Defaults to "cuda" if available, otherwise "cpu".
        /// </summary>
        public string? MlDevice { get; set; }

        /// <summary>
        /// Use multi-label classifier that can detect simultaneous drum hits.
        /// The new v5 model (best_multilabel_model_ema.pt) requires this.
        /// </summary>
        public bool UseMultilabelClassifier { get; set; } = true;

        /// <summary>
        /// Path to per-class thresholds JSON file for multi-label classifier.
        /// If not set, Python will use default thresholds.
        /// </summary>
        public string? MultilabelThresholdsPath { get; set; }

        /// <summary>
        /// Use adaptive thresholds that are computed per-song based on
        /// probability distributions. More accurate but slightly slower.
        /// </summary>
        public bool UseAdaptiveThresholds { get; set; } = false;

        /// <summary>
        /// Method for computing adaptive thresholds: "otsu" (bimodal detection),
        /// "percentile" (top N%), or "knee" (elbow detection).
        /// </summary>
        public string AdaptiveThresholdMethod { get; set; } = "otsu";
    }

    public readonly struct AiGenerationProgress
    {
        public AiGenerationProgress(string message, double? progress = null)
        {
            Message = message;
            Progress = progress;
        }

        public string Message { get; }
        public double? Progress { get; }
    }

    public class AiGenerationResult
    {
        public bool Success { get; init; }
        public string? Error { get; init; }
        public string? BeatmapPath { get; init; }
        public Beatmap? Beatmap { get; init; }
        public string? RawOutputPath { get; init; }
        public string? DebugAnalysisPath { get; init; }
        public string? DrumStemPath { get; init; }
        public IReadOnlyList<string> Logs { get; init; } = Array.Empty<string>();
    }

    /// <summary>
    /// Coordinates execution of the external Python AI beatmap pipeline.
    /// </summary>
    public class AiBeatmapGenerator
    {
        private readonly GameHost host;
        private readonly object pythonLookupLock = new();
        private string? cachedPythonExecutable;

        public AiBeatmapGenerator(GameHost host)
        {
            this.host = host;
        }

        public async Task<AiGenerationResult> GenerateAsync(ImportedAudioTrack track, AiGenerationOptions? options, IProgress<AiGenerationProgress>? progress, CancellationToken cancellationToken, string? drumStemSourcePath = null)
        {
            if (track == null) throw new ArgumentNullException(nameof(track));

            options ??= new AiGenerationOptions();

            progress?.Report(new AiGenerationProgress("Preparing AI pipeline...", 0.05));

            var logs = new List<string>();
            var errors = new List<string>();

            string pipelineRoot;
            try
            {
                pipelineRoot = locatePipelineRoot();
            }
            catch (Exception ex)
            {
                return failure($"Failed to locate AI pipeline: {ex.Message}");
            }

            string pythonExecutable;
            try
            {
                pythonExecutable = resolvePythonExecutable(options);
            }
            catch (Exception ex)
            {
                return failure(ex.Message);
            }

            string workingDirectory = createWorkingDirectory();
            string outputPath = Path.Combine(workingDirectory, "beatmap.bsm");
            string debugPath = Path.Combine(workingDirectory, "analysis.debug.json");

            var startInfo = new ProcessStartInfo
            {
                FileName = pythonExecutable,
                Arguments = buildArguments(track.StoredPath, outputPath, debugPath, options),
                WorkingDirectory = pipelineRoot,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            startInfo.Environment["PYTHONUNBUFFERED"] = "1";

            if (options.TempoCandidates is { Count: > 0 })
            {
                string candidateSummary = string.Join(", ", options.TempoCandidates
                    .Where(c => double.IsFinite(c) && c > 0)
                    .Select(c => c.ToString("0.###", CultureInfo.InvariantCulture)));
                if (!string.IsNullOrWhiteSpace(candidateSummary))
                    logs.Add($"[gen] tempo candidates {candidateSummary}");
            }

            if (options.ForcedBpm.HasValue)
            {
                double offsetSeconds = options.ForcedOffsetSeconds ?? 0;
                double stepSeconds = options.ForcedStepSeconds ?? 0;
                string mode = options.ForceQuantization ? "forcing" : "seeding";
                logs.Add($"[gen] python {mode} bpm={options.ForcedBpm.Value:0.###} offset={offsetSeconds:0.000}s step={stepSeconds:0.000}s");
            }

            progress?.Report(new AiGenerationProgress("Launching Python process...", 0.08));

            using var process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };

            try
            {
                if (!process.Start())
                    return failure("Unable to start AI pipeline process.");
            }
            catch (Exception ex)
            {
                return failure($"Failed to start Python process: {ex.Message}");
            }

            process.OutputDataReceived += (_, e) =>
            {
                if (string.IsNullOrWhiteSpace(e.Data))
                    return;

                lock (logs)
                    logs.Add(e.Data);

                var trimmed = e.Data.Trim();
                double? stepProgress = tryParseProgress(trimmed);
                progress?.Report(new AiGenerationProgress(trimmed, stepProgress));
            };

            process.ErrorDataReceived += (_, e) =>
            {
                if (string.IsNullOrWhiteSpace(e.Data))
                    return;

                lock (logs)
                    logs.Add($"[ERR] {e.Data}");

                lock (errors)
                    errors.Add(e.Data);

                progress?.Report(new AiGenerationProgress(e.Data.Trim()));
            };

            process.BeginOutputReadLine();
            process.BeginErrorReadLine();

            try
            {
                await process.WaitForExitAsync(cancellationToken);
            }
            catch (OperationCanceledException)
            {
                try
                {
                    if (!process.HasExited)
                        process.Kill(true);
                }
                catch
                {
                    // Ignore kill failures during cancellation.
                }

                throw;
            }

            if (process.ExitCode != 0)
            {
                string errorMessage = errors.LastOrDefault() ?? $"Python process exited with code {process.ExitCode}.";
                return failure(errorMessage);
            }

            progress?.Report(new AiGenerationProgress("Python pipeline complete. Parsing output...", 0.95));

            if (!File.Exists(outputPath))
                return failure("AI pipeline did not produce a beatmap file.");

            Beatmap beatmap;

            try
            {
                string json = await File.ReadAllTextAsync(outputPath, cancellationToken);
                beatmap = JsonConvert.DeserializeObject<Beatmap>(json) ?? throw new InvalidDataException("Beatmap JSON deserialised to null.");
            }
            catch (Exception ex)
            {
                return failure($"Failed to parse generated beatmap: {ex.Message}");
            }

            // Log generation summary after successful beatmap load
            logGenerationSummary(beatmap, options, logs);

            try
            {
                await MetadataEnricher.EnrichAsync(beatmap, track, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                Logger.Log($"Metadata enrichment failed: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }

            var syncResult = BeatmapTimebaseSynchroniser.Apply(beatmap, options);
            if (syncResult.BpmAligned || syncResult.OffsetAdjusted || syncResult.SnapDivisor > 0)
            {
                double bpmForLog = beatmap.Timing?.Bpm ?? options.ForcedBpm ?? 0;
                double offsetForLog = (beatmap.Timing?.Offset ?? 0) / 1000.0;
                logs.Add($"[gen] timebase sync bpm={bpmForLog:0.###} offset={offsetForLog:0.000}s delta={syncResult.OffsetDelta}ms snap={syncResult.SnapDivisor}");
            }

            string finalPath;
            string? persistedDrumStem = null;

            try
            {
                (finalPath, persistedDrumStem) = await persistBeatmapAsync(beatmap, track, drumStemSourcePath, cancellationToken);
            }
            catch (Exception ex)
            {
                return failure($"Failed to save beatmap: {ex.Message}");
            }

            progress?.Report(new AiGenerationProgress("AI beatmap saved.", 1.0));

            return new AiGenerationResult
            {
                Success = true,
                Beatmap = beatmap,
                BeatmapPath = finalPath,
                RawOutputPath = outputPath,
                DebugAnalysisPath = File.Exists(debugPath) ? debugPath : null,
                DrumStemPath = persistedDrumStem,
                Logs = logs.AsReadOnly()
            };

            AiGenerationResult failure(string message)
            {
                Logger.Log($"AI beatmap generation failed: {message}", LoggingTarget.Runtime, LogLevel.Important);
                return new AiGenerationResult
                {
                    Success = false,
                    Error = message,
                    Logs = logs.AsReadOnly()
                };
            }
        }

        /// <summary>
        /// Logs a comprehensive generation summary including note counts, BPM, and grid configuration.
        /// This provides visibility into what the AI pipeline produced for debugging and validation.
        /// </summary>
        private static void logGenerationSummary(Beatmap beatmap, AiGenerationOptions options, List<string> logs)
        {
            int noteCount = beatmap.HitObjects?.Count ?? 0;
            double bpm = beatmap.Timing?.Bpm ?? options.ForcedBpm ?? 0;
            double offsetMs = beatmap.Timing?.Offset ?? 0;
            string mode = options.PipelineMode == AiPipelineMode.Transcription ? "transcription" : "gameplay";
            string sensitivity = options.AutoSensitivity
                ? "auto"
                : Math.Clamp(options.DetectionSensitivity, 0, 100).ToString(CultureInfo.InvariantCulture);
            string grid = options.AutoQuantization ? "auto" : options.QuantizationGrid.ToString();

            // Count notes by lane for distribution insight
            var laneCounts = new Dictionary<int, int>();
            if (beatmap.HitObjects != null)
            {
                foreach (var hit in beatmap.HitObjects)
                {
                    int lane = hit.Lane ?? 0;
                    laneCounts[lane] = laneCounts.GetValueOrDefault(lane, 0) + 1;
                }
            }

            string laneDistribution = laneCounts.Count > 0
                ? string.Join(" ", laneCounts.OrderBy(kv => kv.Key).Select(kv => $"L{kv.Key}:{kv.Value}"))
                : "none";

            logs.Add($"[gen] mode={mode} notes={noteCount} bpm={bpm:0.###} offset={offsetMs:0}ms sensitivity={sensitivity} grid={grid} lanes=[{laneDistribution}]");

            // Log duration coverage if we have timing info
            if (noteCount > 0 && beatmap.HitObjects != null)
            {
                double firstNoteMs = beatmap.HitObjects.Min(h => h.Time);
                double lastNoteMs = beatmap.HitObjects.Max(h => h.Time);
                double spanSeconds = (lastNoteMs - firstNoteMs) / 1000.0;
                double notesPerSecond = spanSeconds > 0 ? noteCount / spanSeconds : 0;
                logs.Add($"[gen] span={spanSeconds:0.0}s density={notesPerSecond:0.00}nps first={firstNoteMs:0}ms last={lastNoteMs:0}ms");
            }
        }

        private static double? tryParseProgress(string line)
        {
            if (string.IsNullOrEmpty(line))
                return null;

            if (line.Contains("Complete", StringComparison.OrdinalIgnoreCase))
                return 1.0;

            int stepIndex = line.IndexOf("Step ", StringComparison.OrdinalIgnoreCase);
            if (stepIndex < 0)
                return null;

            int fractionStart = stepIndex + 5;
            int slashIndex = line.IndexOf('/', fractionStart);
            if (slashIndex < 0)
                return null;

            if (!int.TryParse(line.Substring(fractionStart, slashIndex - fractionStart), out int currentStep))
                return null;

            int totalStart = slashIndex + 1;
            int totalEnd = totalStart;
            while (totalEnd < line.Length && char.IsDigit(line[totalEnd]))
                totalEnd++;

            if (!int.TryParse(line.Substring(totalStart, totalEnd - totalStart), out int totalSteps) || totalSteps <= 0)
                totalSteps = 5;

            double fraction = (double)Math.Clamp(currentStep, 0, totalSteps) / totalSteps;
            return Math.Clamp(fraction, 0.0, 0.99);
        }

        private static string locatePipelineRoot()
        {
            string baseDir = AppContext.BaseDirectory;

            var candidates = new[]
            {
                Path.Combine(baseDir, "ai-pipeline"),
                Path.Combine(baseDir, "..", "ai-pipeline"),
                Path.Combine(baseDir, "..", "..", "ai-pipeline"),
                Path.Combine(baseDir, "..", "..", "..", "..", "..", "ai-pipeline")
            };

            foreach (var candidate in candidates.Select(Path.GetFullPath))
            {
                if (Directory.Exists(candidate))
                    return candidate;
            }

            throw new DirectoryNotFoundException("ai-pipeline directory not found relative to application root.");
        }

        private string resolvePythonExecutable(AiGenerationOptions options)
        {
            if (!string.IsNullOrWhiteSpace(options.PythonExecutablePath))
                return options.PythonExecutablePath;

            lock (pythonLookupLock)
            {
                if (!string.IsNullOrEmpty(cachedPythonExecutable))
                    return cachedPythonExecutable;

                var candidates = OperatingSystem.IsWindows()
                    ? new[] { "python.exe", "python3.exe" }
                    : new[] { "python3", "python" };

                foreach (var candidate in candidates)
                {
                    if (isExecutableAvailable(candidate))
                    {
                        cachedPythonExecutable = candidate;
                        return candidate;
                    }
                }
            }

            throw new InvalidOperationException("Python executable not found. Ensure Python 3 is installed and available on PATH.");
        }

        private static bool isExecutableAvailable(string command)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = command,
                    Arguments = "--version",
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                using var process = Process.Start(psi);
                if (process == null)
                    return false;

                if (!process.WaitForExit(3000))
                    return false;

                return process.ExitCode == 0;
            }
            catch
            {
                return false;
            }
        }

        private string createWorkingDirectory()
        {
            string root = host.Storage.GetFullPath(Path.Combine("AI", "Runs"));
            Directory.CreateDirectory(root);

            string folderName = DateTime.UtcNow.ToString("yyyyMMdd_HHmmssfff", CultureInfo.InvariantCulture);
            string fullPath = Path.Combine(root, folderName);
            Directory.CreateDirectory(fullPath);
            return fullPath;
        }

        private static string buildArguments(string inputPath, string outputPath, string debugPath, AiGenerationOptions options)
        {
            var builder = new StringBuilder();
            builder.Append("-m pipeline.process");
            builder.Append(' ').Append("--input ").Append(quote(inputPath));
            builder.Append(' ').Append("--output ").Append(quote(outputPath));
            builder.Append(' ').Append("--confidence ").Append(options.ConfidenceThreshold.ToString("0.###", CultureInfo.InvariantCulture));
            builder.Append(' ').Append("--mode ").Append(options.PipelineMode == AiPipelineMode.Transcription ? "transcription" : "gameplay");

            if (options.AutoSensitivity)
                builder.Append(" --auto-sensitivity");
            else
                builder.Append(' ').Append("--sensitivity ").Append(Math.Clamp(options.DetectionSensitivity, 0, 100).ToString(CultureInfo.InvariantCulture));

            if (options.AutoQuantization)
                builder.Append(" --auto-quantization");
            else
                builder.Append(' ').Append("--quantization ").Append(toQuantizationCliValue(options.QuantizationGrid));
            builder.Append(' ').Append("--max-snap-error ").Append(Math.Clamp(options.MaxSnapErrorMilliseconds, 2.0, 40.0).ToString("0.###", CultureInfo.InvariantCulture));

            if (options.ExportDebugAnalysis)
                builder.Append(' ').Append("--debug ").Append(quote(debugPath));

            if (!options.EnableDrumSeparation)
                builder.Append(' ').Append("--no-separation");

            if (options.TempoCandidates is { Count: > 0 })
            {
                var csv = string.Join(",",
                    options.TempoCandidates
                        .Where(c => double.IsFinite(c) && c > 0)
                        .Select(c => c.ToString("0.####", CultureInfo.InvariantCulture)));

                if (!string.IsNullOrWhiteSpace(csv))
                    builder.Append(' ').Append("--tempo-candidates ").Append(quote(csv));
            }

            if (options.ForcedBpm.HasValue && options.ForcedBpm.Value > 0)
                builder.Append(' ').Append("--force-bpm ").Append(options.ForcedBpm.Value.ToString("0.####", CultureInfo.InvariantCulture));

            if (options.ForcedOffsetSeconds.HasValue)
            {
                double offset = options.ForcedOffsetSeconds.Value;
                if (!double.IsNaN(offset) && double.IsFinite(offset))
                    builder.Append(' ').Append("--force-offset ").Append(offset.ToString("0.######", CultureInfo.InvariantCulture));
            }

            if (options.ForcedStepSeconds.HasValue && options.ForcedStepSeconds.Value > 0)
                builder.Append(' ').Append("--force-step ").Append(options.ForcedStepSeconds.Value.ToString("0.######", CultureInfo.InvariantCulture));

            if (options.ForceQuantization)
                builder.Append(' ').Append("--force-quantization");

            if (options.StartTime.HasValue)
                builder.Append(' ').Append("--start-time ").Append(options.StartTime.Value.ToString("0.######", CultureInfo.InvariantCulture));

            if (options.EndTime.HasValue)
                builder.Append(' ').Append("--end-time ").Append(options.EndTime.Value.ToString("0.######", CultureInfo.InvariantCulture));

            // ML classifier options
            if (options.UseMlClassifier)
                builder.Append(" --ml");
            else
                builder.Append(" --no-ml");

            if (!string.IsNullOrEmpty(options.MlModelPath))
                builder.Append(" --ml-model ").Append(quote(options.MlModelPath));

            if (!string.IsNullOrEmpty(options.MlDevice))
                builder.Append(" --ml-device ").Append(options.MlDevice);

            // Multi-label classifier options
            if (options.UseMultilabelClassifier)
                builder.Append(" --multilabel");

            if (!string.IsNullOrEmpty(options.MultilabelThresholdsPath))
                builder.Append(" --multilabel-thresholds ").Append(quote(options.MultilabelThresholdsPath));

            // Adaptive thresholds for per-song optimization
            if (options.UseAdaptiveThresholds)
            {
                builder.Append(" --adaptive-thresholds");
                builder.Append(" --adaptive-threshold-method ").Append(options.AdaptiveThresholdMethod);
            }

            return builder.ToString();
        }

        private static string quote(string text)
        {
            if (string.IsNullOrEmpty(text))
                return "\"\"";

            return "\"" + text.Replace("\"", "\\\"") + "\"";
        }

        private static string toQuantizationCliValue(QuantizationGrid grid) => grid switch
        {
            QuantizationGrid.Quarter => "quarter",
            QuantizationGrid.Eighth => "eighth",
            QuantizationGrid.Sixteenth => "sixteenth",
            QuantizationGrid.Triplet => "triplet",
            QuantizationGrid.ThirtySecond => "thirtysecond",
            _ => "sixteenth"
        };

        private async Task<(string BeatmapPath, string? DrumStemPath)> persistBeatmapAsync(Beatmap beatmap, ImportedAudioTrack track, string? drumStemSourcePath, CancellationToken cancellationToken)
        {
            // Ensure basic metadata defaults are set
            if (string.IsNullOrWhiteSpace(beatmap.Metadata.Title))
                beatmap.Metadata.Title = "Untitled";

            if (string.IsNullOrWhiteSpace(beatmap.Metadata.Artist))
                beatmap.Metadata.Artist = "Unknown Artist";

            if (string.IsNullOrWhiteSpace(beatmap.Metadata.Creator))
                beatmap.Metadata.Creator = "BeatSight AI";

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;

            if (beatmap.Editor?.AiGenerationMetadata != null)
            {
                beatmap.Editor.AiGenerationMetadata.ProcessedAt ??= DateTime.UtcNow;
                beatmap.Editor.AiGenerationMetadata.ManualEdits = false;
            }

            // Store generated beatmaps in the roaming user Songs directory.
            string userSongsRoot = UserAssetDirectories.GetPath(UserAssetDirectories.Songs);
            Directory.CreateDirectory(userSongsRoot);

            // Format: {Artist} - {Title} ({Creator})
            string artist = string.IsNullOrWhiteSpace(beatmap.Metadata.Artist) ? "Unknown Artist" : beatmap.Metadata.Artist;
            string title = string.IsNullOrWhiteSpace(beatmap.Metadata.Title) ? "Untitled" : beatmap.Metadata.Title;
            string creator = string.IsNullOrWhiteSpace(beatmap.Metadata.Creator) ? "BeatSight AI" : beatmap.Metadata.Creator;

            string folderName = $"{artist} - {title} ({creator})";
            string slug = createSlug(folderName);
            string beatmapFolder = Path.Combine(userSongsRoot, slug);

            // Handle duplicate folder names
            int counter = 1;
            string originalSlug = slug;
            while (Directory.Exists(beatmapFolder))
            {
                slug = $"{originalSlug}_{counter++}";
                beatmapFolder = Path.Combine(userSongsRoot, slug);
            }

            Directory.CreateDirectory(beatmapFolder);

            string audioFileName = Path.GetFileName(track.StoredPath);
            string audioTargetPath = Path.Combine(beatmapFolder, audioFileName);

            await copyFileAsync(track.StoredPath, audioTargetPath, cancellationToken);

            beatmap.Audio.Filename = audioFileName;
            beatmap.Audio.Hash = computeFileHash(audioTargetPath);

            if (beatmap.Audio.Duration <= 0 && track.DurationMilliseconds.HasValue)
                beatmap.Audio.Duration = (int)Math.Round(track.DurationMilliseconds.Value);

            string? drumStemTargetPath = null;

            if (!string.IsNullOrWhiteSpace(drumStemSourcePath) && File.Exists(drumStemSourcePath))
            {
                string drumName = Path.GetFileName(drumStemSourcePath!);
                if (string.IsNullOrWhiteSpace(drumName))
                    drumName = Path.GetFileNameWithoutExtension(audioFileName) + "_drums" + Path.GetExtension(drumStemSourcePath!);

                drumStemTargetPath = Path.Combine(beatmapFolder, drumName);

                try
                {
                    await copyFileAsync(drumStemSourcePath!, drumStemTargetPath, cancellationToken);
                    beatmap.Audio.DrumStem = drumName;
                    beatmap.Audio.DrumStemHash = computeFileHash(drumStemTargetPath);
                }
                catch (Exception ex) when (!cancellationToken.IsCancellationRequested)
                {
                    Logger.Log($"Failed to persist drum stem: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                    drumStemTargetPath = null;
                    beatmap.Audio.DrumStem = null;
                    beatmap.Audio.DrumStemHash = null;
                }
            }

            // Persist as .bsm so generated maps are discoverable by the in-game library.
            string beatmapSlug = createSlug($"{artist}-{title}");
            string finalBeatmapPath = Path.Combine(beatmapFolder, beatmapSlug + ".bsm");
            BeatmapLoader.SaveToFile(beatmap, finalBeatmapPath);

            return (finalBeatmapPath, drumStemTargetPath);
        }

        private static async Task copyFileAsync(string source, string destination, CancellationToken cancellationToken)
        {
            await using var sourceStream = File.OpenRead(source);
            await using var destStream = File.Create(destination);
            await sourceStream.CopyToAsync(destStream, cancellationToken);
        }

        private static string computeFileHash(string filePath)
        {
            using var sha = SHA256.Create();
            using var stream = File.OpenRead(filePath);
            var hash = sha.ComputeHash(stream);
            var builder = new StringBuilder(hash.Length * 2);
            foreach (byte b in hash)
                builder.Append(b.ToString("x2", CultureInfo.InvariantCulture));

            return "sha256:" + builder.ToString();
        }

        private static string createSlug(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return "beatmap";

            var builder = new StringBuilder();
            foreach (char ch in text)
            {
                if (char.IsLetterOrDigit(ch) || ch == ' ' || ch == '-' || ch == '_')
                {
                    // Keep spaces, hyphens, and underscores for readability
                    builder.Append(ch);
                }
                else if (builder.Length > 0 && builder[^1] != '-')
                {
                    // Replace other special chars with hyphen (but avoid doubles)
                    builder.Append('-');
                }
            }

            string slug = builder.ToString().Trim('-', '_', ' ');

            // Collapse multiple spaces/hyphens
            while (slug.Contains("  "))
                slug = slug.Replace("  ", " ");
            while (slug.Contains("--"))
                slug = slug.Replace("--", "-");

            return string.IsNullOrEmpty(slug) ? "beatmap" : slug;
        }

    }

    public enum AiPipelineMode
    {
        Gameplay,
        Transcription
    }

    /// <summary>
    /// Quantization grid options for snapping detected notes.
    /// Must match backend app/schemas/ai_jobs.py QuantizationGrid.
    /// </summary>
    public enum QuantizationGrid
    {
        None = 0,
        Quarter = 4,
        Eighth = 8,
        Sixteenth = 16,
        Triplet = 3,
        ThirtySecond = 32
    }
}
