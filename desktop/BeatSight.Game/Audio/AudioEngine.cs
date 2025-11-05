using System;
using System.Threading;
using System.Threading.Tasks;
using osu.Framework.Audio;
using osu.Framework.Logging;
using TagLib;

namespace BeatSight.Game.Audio
{
    /// <summary>
    /// Provides a lightweight facade over the framework audio stack to expose readiness gates
    /// and utility helpers used by the AI generation pipeline.
    /// </summary>
    public sealed class AudioEngine : IDisposable
    {
        private readonly TaskCompletionSource<bool> readyTcs = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private AudioManager? audioManager;
        private int disposed;

        /// <summary>
        /// Gets whether the underlying audio subsystem has been initialised.
        /// </summary>
        public bool IsReady => readyTcs.Task.IsCompletedSuccessfully;

        /// <summary>
        /// Task that completes once the audio subsystem is initialised.
        /// </summary>
        public Task WhenReady => readyTcs.Task;

        /// <summary>
        /// Waits until the audio manager signals readiness or a timeout/cancellation occurs.
        /// Returns <c>true</c> if readiness was observed.
        /// </summary>
        public async Task<bool> WaitForReadyAsync(TimeSpan timeout, CancellationToken cancellationToken)
        {
            if (IsReady)
                return true;

            using var timeoutCts = new CancellationTokenSource(timeout);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, timeoutCts.Token);

            try
            {
                await readyTcs.Task.WaitAsync(linked.Token).ConfigureAwait(false);
                return true;
            }
            catch (OperationCanceledException) when (timeoutCts.IsCancellationRequested && !cancellationToken.IsCancellationRequested)
            {
                return false;
            }
            catch (OperationCanceledException) when (readyTcs.Task.IsCanceled && !cancellationToken.IsCancellationRequested)
            {
                return false;
            }
        }

        /// <summary>
        /// Gets the resolved framework audio manager, if available.
        /// </summary>
        public AudioManager? Manager => audioManager;

        /// <summary>
        /// Marks the audio engine as ready using the provided <see cref="AudioManager"/> instance.
        /// </summary>
        public void Attach(AudioManager manager)
        {
            if (manager == null)
                throw new ArgumentNullException(nameof(manager));

            if (disposed != 0)
                return;

            if (audioManager == null)
                audioManager = manager;

            readyTcs.TrySetResult(true);
        }

        /// <summary>
        /// Computes an approximate duration for the supplied audio file by reading metadata/PCM without creating a playback track.
        /// </summary>
        public async Task<double?> ComputeDurationFromFileAsync(string filePath, CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(filePath))
                return null;

            return await Task.Run(() =>
            {
                try
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    using var tagFile = File.Create(filePath);
                    return tagFile.Properties.Duration.TotalMilliseconds;
                }
                catch (OperationCanceledException)
                {
                    throw;
                }
                catch (Exception ex)
                {
                    Logger.Error(ex, $"Failed to compute duration for '{filePath}'");
                    return (double?)null;
                }
            }, cancellationToken).ConfigureAwait(false);
        }

        public void Dispose()
        {
            if (Interlocked.Exchange(ref disposed, 1) != 0)
                return;

            readyTcs.TrySetCanceled();
        }
    }
}
