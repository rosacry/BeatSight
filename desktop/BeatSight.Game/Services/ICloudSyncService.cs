using System;
using System.Threading;
using System.Threading.Tasks;

namespace BeatSight.Game.Services
{
    /// <summary>
    /// Interface for cloud synchronization services.
    /// Currently a placeholder for future implementation.
    /// </summary>
    public interface ICloudSyncService : IDisposable
    {
        /// <summary>
        /// Gets or sets the backend API base URL.
        /// </summary>
        string ApiBaseUrl { get; set; }

        /// <summary>
        /// Gets whether the user is authenticated.
        /// </summary>
        bool IsAuthenticated { get; }

        /// <summary>
        /// Gets the current sync status.
        /// </summary>
        SyncStatus Status { get; }

        /// <summary>
        /// Authenticates with the backend using email and password.
        /// </summary>
        Task<bool> LoginAsync(string email, string password, CancellationToken cancellationToken = default);

        /// <summary>
        /// Logs out and clears stored credentials.
        /// </summary>
        Task LogoutAsync(CancellationToken cancellationToken = default);

        /// <summary>
        /// Syncs user preferences with the cloud.
        /// </summary>
        Task SyncPreferencesAsync(CancellationToken cancellationToken = default);

        /// <summary>
        /// Syncs beatmap progress with the cloud.
        /// </summary>
        Task SyncProgressAsync(CancellationToken cancellationToken = default);

        /// <summary>
        /// Uploads a beatmap to the cloud.
        /// </summary>
        Task<string> UploadBeatmapAsync(string localPath, CancellationToken cancellationToken = default);

        /// <summary>
        /// Downloads a beatmap from the cloud.
        /// </summary>
        Task<string> DownloadBeatmapAsync(string cloudId, string localPath, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Sync status enumeration.
    /// </summary>
    public enum SyncStatus
    {
        Idle,
        Syncing,
        Success,
        Error,
        Offline
    }

    /// <summary>
    /// Stub implementation of cloud sync service.
    /// Used when cloud sync is disabled or not configured.
    /// All operations are no-ops that fail gracefully.
    /// </summary>
    public sealed class StubCloudSyncService : ICloudSyncService
    {
        public string ApiBaseUrl { get; set; } = "https://api.beatsight.app";
        public bool IsAuthenticated => false;
        public SyncStatus Status => SyncStatus.Offline;

        public Task<bool> LoginAsync(string email, string password, CancellationToken cancellationToken = default)
        {
            // Cloud sync not configured - login always fails
            return Task.FromResult(false);
        }

        public Task LogoutAsync(CancellationToken cancellationToken = default)
        {
            return Task.CompletedTask;
        }

        public Task SyncPreferencesAsync(CancellationToken cancellationToken = default)
        {
            // No-op when cloud sync is disabled
            return Task.CompletedTask;
        }

        public Task SyncProgressAsync(CancellationToken cancellationToken = default)
        {
            // No-op when cloud sync is disabled
            return Task.CompletedTask;
        }

        public Task<string> UploadBeatmapAsync(string localPath, CancellationToken cancellationToken = default)
        {
            // Return empty string to indicate offline/no upload
            // Callers should check IsAuthenticated before calling this
            return Task.FromResult(string.Empty);
        }

        public Task<string> DownloadBeatmapAsync(string cloudId, string localPath, CancellationToken cancellationToken = default)
        {
            // Return empty string to indicate offline/no download
            // Callers should check IsAuthenticated before calling this
            return Task.FromResult(string.Empty);
        }

        public void Dispose()
        {
            // Nothing to dispose
        }
    }
}
