using System;
using System.Threading;
using System.Threading.Tasks;

namespace BeatSight.Game.Services.Separation
{
    public interface IDemucsBackend : IAsyncDisposable
    {
        string Name { get; }

        Task LoadModelAsync(CancellationToken cancellationToken);

        Task<SeparationOutput> SeparateAsync(string audioPath, CancellationToken cancellationToken, IProgress<double>? progress = null);
    }

    public readonly struct SeparationOutput : IDisposable
    {
        public SeparationOutput(string sourcePath, string drumsPath, bool isPassthrough, bool deleteOnDispose, string? workingDirectory = null)
        {
            SourcePath = sourcePath;
            DrumsPath = drumsPath;
            IsPassthrough = isPassthrough;
            DeleteOnDispose = deleteOnDispose;
            WorkingDirectory = workingDirectory;
        }

        public string SourcePath { get; }
        public string DrumsPath { get; }
        public bool IsPassthrough { get; }
        public string? WorkingDirectory { get; }
        private bool DeleteOnDispose { get; }

        public void Dispose()
        {
            if (!DeleteOnDispose)
                return;

            try
            {
                if (!string.IsNullOrEmpty(DrumsPath) && System.IO.File.Exists(DrumsPath))
                    System.IO.File.Delete(DrumsPath);

                if (!string.IsNullOrEmpty(WorkingDirectory) && System.IO.Directory.Exists(WorkingDirectory))
                {
                    if (System.IO.Directory.GetFileSystemEntries(WorkingDirectory).Length == 0)
                        System.IO.Directory.Delete(WorkingDirectory, true);
                }
            }
            catch
            {
                // Best effort cleanup; ignore IO failures so pipeline completion does not throw.
            }
        }
    }

    public class DemucsBackendException : Exception
    {
        public DemucsBackendException(string message)
            : base(message)
        {
        }

        public DemucsBackendException(string message, Exception innerException)
            : base(message, innerException)
        {
        }
    }
}
