using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using osu.Framework.Logging;
using osu.Framework.Platform;

namespace BeatSight.Game.Services.Metadata
{
    public class DetectedMetadata
    {
        [JsonProperty("title")]
        public string? Title { get; set; }
        [JsonProperty("artist")]
        public string? Artist { get; set; }
        [JsonProperty("album")]
        public string? Album { get; set; }
        [JsonProperty("release_date")]
        public string? ReleaseDate { get; set; }
        [JsonProperty("source")]
        public string? Source { get; set; }
        [JsonProperty("confidence")]
        public double? Confidence { get; set; }
        [JsonProperty("provider")]
        public string? Provider { get; set; }
    }

    public class MetadataDetectionService
    {
        private readonly GameHost host;
        private string? cachedPythonExecutable;
        private readonly object pythonLookupLock = new();

        public MetadataDetectionService(GameHost host)
        {
            this.host = host;
        }

        public async Task<DetectedMetadata?> DetectMetadataAsync(string audioPath, CancellationToken cancellationToken)
        {
            string pipelineRoot;
            try
            {
                pipelineRoot = locatePipelineRoot();
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to locate AI pipeline: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                return null;
            }

            string pythonExecutable;
            try
            {
                pythonExecutable = resolvePythonExecutable();
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to resolve Python executable: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                return null;
            }

            var startInfo = new ProcessStartInfo
            {
                FileName = pythonExecutable,
                Arguments = $"detect_metadata.py \"{audioPath}\"",
                WorkingDirectory = pipelineRoot,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            startInfo.Environment["PYTHONUNBUFFERED"] = "1";

            using var process = new Process { StartInfo = startInfo };

            try
            {
                if (!process.Start())
                {
                    Logger.Log("Unable to start metadata detection process.", LoggingTarget.Runtime, LogLevel.Error);
                    return null;
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to start Python process: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                return null;
            }

            string output = await process.StandardOutput.ReadToEndAsync(cancellationToken);
            string error = await process.StandardError.ReadToEndAsync(cancellationToken);

            await process.WaitForExitAsync(cancellationToken);

            if (process.ExitCode != 0)
            {
                Logger.Log($"Metadata detection failed (Exit Code {process.ExitCode}): {error}", LoggingTarget.Runtime, LogLevel.Error);
                return null;
            }

            try
            {
                return JsonConvert.DeserializeObject<DetectedMetadata>(output);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to parse metadata JSON: {ex.Message}. Output: {output}", LoggingTarget.Runtime, LogLevel.Error);
                return null;
            }
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

        private string resolvePythonExecutable()
        {
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
    }
}
