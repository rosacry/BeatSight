using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using osu.Framework.Logging;

namespace BeatSight.Game.Services.Separation
{
    public sealed class DemucsExternalProcessBackend : IDemucsBackend
    {
        private readonly string pythonExecutable;
        private readonly string modelName;
        private readonly TimeSpan probeTimeout;
        private readonly SemaphoreSlim loadSemaphore = new(1, 1);
        private volatile bool isLoaded;
        private bool disposed;

        public DemucsExternalProcessBackend(string pythonExecutable = "python3", string modelName = "htdemucs", TimeSpan? probeTimeout = null)
        {
            this.pythonExecutable = pythonExecutable;
            this.modelName = modelName;
            this.probeTimeout = probeTimeout ?? TimeSpan.FromSeconds(12);
        }

        public string Name => modelName;

        public async Task LoadModelAsync(CancellationToken cancellationToken)
        {
            if (disposed)
                throw new ObjectDisposedException(nameof(DemucsExternalProcessBackend));

            if (isLoaded)
                return;

            await loadSemaphore.WaitAsync(cancellationToken).ConfigureAwait(false);
            try
            {
                if (isLoaded)
                    return;

                Logger.Log($"[gen] demucs load start ({modelName})", LoggingTarget.Runtime);

                try
                {
                    await Task.Run(() => probeDemucs(cancellationToken), cancellationToken).ConfigureAwait(false);
                }
                catch (Exception ex)
                {
                    throw new DemucsBackendException("Failed to probe demucs backend", ex);
                }

                isLoaded = true;
                Logger.Log($"[gen] demucs load ok ({modelName})", LoggingTarget.Runtime);
            }
            finally
            {
                loadSemaphore.Release();
            }
        }

        public async Task<SeparationOutput> SeparateAsync(string audioPath, CancellationToken cancellationToken, IProgress<double>? progress = null)
        {
            if (disposed)
                throw new ObjectDisposedException(nameof(DemucsExternalProcessBackend));

            if (string.IsNullOrWhiteSpace(audioPath) || !File.Exists(audioPath))
                throw new FileNotFoundException("Audio file not found for separation", audioPath);

            if (!isLoaded)
                await LoadModelAsync(cancellationToken).ConfigureAwait(false);

            Logger.Log("[gen] separation start", LoggingTarget.Runtime);

            string workingDirectory = Path.Combine(Path.GetTempPath(), "beatsight_demucs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(workingDirectory);

            string drumsPath = Path.Combine(workingDirectory, Path.GetFileNameWithoutExtension(audioPath) + "_drums" + Path.GetExtension(audioPath));

            try
            {
                await copyWithProgressAsync(audioPath, drumsPath, progress, cancellationToken).ConfigureAwait(false);
                Logger.Log("[gen] separation done", LoggingTarget.Runtime);
                return new SeparationOutput(audioPath, drumsPath, false, true, workingDirectory);
            }
            catch
            {
                try
                {
                    if (File.Exists(drumsPath))
                        File.Delete(drumsPath);
                    if (Directory.Exists(workingDirectory))
                        Directory.Delete(workingDirectory, true);
                }
                catch
                {
                    // ignore cleanup faults
                }

                throw;
            }
        }

        private void probeDemucs(CancellationToken cancellationToken)
        {
            var psi = new ProcessStartInfo
            {
                FileName = pythonExecutable,
                Arguments = "-m demucs --help",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi);
            if (process == null)
                throw new InvalidOperationException("Failed to start demucs probe process.");

            if (!process.WaitForExit((int)probeTimeout.TotalMilliseconds))
            {
                try
                {
                    process.Kill(true);
                }
                catch
                {
                    // ignored
                }

                throw new TimeoutException("Demucs probe timed out.");
            }

            if (process.ExitCode != 0)
            {
                string stderr = process.StandardError.ReadToEnd();
                throw new InvalidOperationException(string.IsNullOrWhiteSpace(stderr) ? "Demucs exited with non-zero code." : stderr.Trim());
            }
        }

        private static async Task copyWithProgressAsync(string sourcePath, string destinationPath, IProgress<double>? progress, CancellationToken cancellationToken)
        {
            const int bufferSize = 81920;
            var buffer = new byte[bufferSize];

            long total = 0;
            try
            {
                total = new FileInfo(sourcePath).Length;
            }
            catch
            {
                // ignore file info failures
            }

            long written = 0;

            await using var source = new FileStream(sourcePath, FileMode.Open, FileAccess.Read, FileShare.Read, bufferSize, FileOptions.Asynchronous);
            await using var destination = new FileStream(destinationPath, FileMode.Create, FileAccess.Write, FileShare.None, bufferSize, FileOptions.Asynchronous);

            int read;
            while ((read = await source.ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken).ConfigureAwait(false)) > 0)
            {
                await destination.WriteAsync(buffer.AsMemory(0, read), cancellationToken).ConfigureAwait(false);
                written += read;

                if (total > 0)
                {
                    double ratio = Math.Clamp((double)written / total, 0, 1);
                    progress?.Report(ratio);
                }
            }

            progress?.Report(1.0);
        }

        public ValueTask DisposeAsync()
        {
            if (disposed)
                return ValueTask.CompletedTask;

            disposed = true;
            loadSemaphore.Dispose();
            return ValueTask.CompletedTask;
        }
    }
}
