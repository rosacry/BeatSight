using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using osu.Framework.Logging;

namespace BeatSight.Game.Services
{
    /// <summary>
    /// Real implementation of cloud sync service that connects to the BeatSight backend API.
    /// </summary>
    public sealed class CloudSyncService : ICloudSyncService
    {
        private readonly HttpClient httpClient;
        private readonly JsonSerializerOptions jsonOptions;

        private string? accessToken;
        private string? refreshToken;
        private DateTime tokenExpiry = DateTime.MinValue;
        private string? clientId;

        private const string CLIENT_TYPE = "desktop";
        private const string TOKEN_STORAGE_KEY = "cloud_sync_tokens";

        public string ApiBaseUrl { get; set; } = "https://api.beatsight.app";
        public bool IsAuthenticated => !string.IsNullOrEmpty(accessToken) && DateTime.UtcNow < tokenExpiry;
        public SyncStatus Status { get; private set; } = SyncStatus.Offline;

        public CloudSyncService()
        {
            httpClient = new HttpClient
            {
                Timeout = TimeSpan.FromSeconds(30)
            };

            jsonOptions = new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
                PropertyNameCaseInsensitive = true
            };

            // Try to load stored tokens on startup
            LoadStoredTokens();
        }

        #region Authentication

        public async Task<bool> LoginAsync(string email, string password, CancellationToken cancellationToken = default)
        {
            try
            {
                Status = SyncStatus.Syncing;

                var loginRequest = new { email, password };
                var response = await httpClient.PostAsJsonAsync(
                    $"{ApiBaseUrl}/api/v1/auth/login",
                    loginRequest,
                    jsonOptions,
                    cancellationToken
                );

                if (!response.IsSuccessStatusCode)
                {
                    Logger.Log($"Login failed with status {response.StatusCode}", LoggingTarget.Network);
                    Status = SyncStatus.Error;
                    return false;
                }

                var tokenResponse = await response.Content.ReadFromJsonAsync<TokenResponse>(jsonOptions, cancellationToken);
                if (tokenResponse == null)
                {
                    Status = SyncStatus.Error;
                    return false;
                }

                accessToken = tokenResponse.AccessToken;
                refreshToken = tokenResponse.RefreshToken;
                tokenExpiry = DateTime.UtcNow.AddMinutes(55); // JWT typically expires in 60 mins, refresh at 55

                // Store tokens securely
                SaveTokens();

                // Update HTTP client auth header
                httpClient.DefaultRequestHeaders.Authorization =
                    new AuthenticationHeaderValue("Bearer", accessToken);

                // Register this device as a sync client
                await RegisterClientAsync(cancellationToken);

                Status = SyncStatus.Idle;
                Logger.Log("Cloud sync login successful", LoggingTarget.Network);
                return true;
            }
            catch (Exception ex)
            {
                Logger.Log($"Login error: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                Status = SyncStatus.Error;
                return false;
            }
        }

        public async Task LogoutAsync(CancellationToken cancellationToken = default)
        {
            try
            {
                // Try to notify server (best effort)
                if (IsAuthenticated)
                {
                    await EnsureAuthenticatedAsync(cancellationToken);
                    // Could call a logout endpoint here if the API has one
                }
            }
            catch
            {
                // Ignore errors during logout
            }
            finally
            {
                accessToken = null;
                refreshToken = null;
                tokenExpiry = DateTime.MinValue;
                clientId = null;

                httpClient.DefaultRequestHeaders.Authorization = null;
                ClearStoredTokens();

                Status = SyncStatus.Offline;
                Logger.Log("Logged out of cloud sync", LoggingTarget.Network);
            }
        }

        private async Task<bool> RefreshTokenAsync(CancellationToken cancellationToken)
        {
            if (string.IsNullOrEmpty(refreshToken))
                return false;

            try
            {
                var refreshRequest = new { refresh_token = refreshToken };
                var response = await httpClient.PostAsJsonAsync(
                    $"{ApiBaseUrl}/api/v1/auth/refresh",
                    refreshRequest,
                    jsonOptions,
                    cancellationToken
                );

                if (!response.IsSuccessStatusCode)
                {
                    Logger.Log($"Token refresh failed: {response.StatusCode}", LoggingTarget.Network);
                    return false;
                }

                var tokenResponse = await response.Content.ReadFromJsonAsync<TokenResponse>(jsonOptions, cancellationToken);
                if (tokenResponse == null)
                    return false;

                accessToken = tokenResponse.AccessToken;
                refreshToken = tokenResponse.RefreshToken;
                tokenExpiry = DateTime.UtcNow.AddMinutes(55);

                httpClient.DefaultRequestHeaders.Authorization =
                    new AuthenticationHeaderValue("Bearer", accessToken);

                SaveTokens();
                Logger.Log("Token refreshed successfully", LoggingTarget.Network);
                return true;
            }
            catch (Exception ex)
            {
                Logger.Log($"Token refresh error: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                return false;
            }
        }

        private async Task EnsureAuthenticatedAsync(CancellationToken cancellationToken)
        {
            if (!IsAuthenticated && !string.IsNullOrEmpty(refreshToken))
            {
                var refreshed = await RefreshTokenAsync(cancellationToken);
                if (!refreshed)
                {
                    throw new InvalidOperationException("Not authenticated. Please login first.");
                }
            }
            else if (!IsAuthenticated)
            {
                throw new InvalidOperationException("Not authenticated. Please login first.");
            }
        }

        private async Task RegisterClientAsync(CancellationToken cancellationToken)
        {
            try
            {
                var clientName = $"{Environment.MachineName}-BeatSight";
                var registerRequest = new { client_name = clientName, client_type = CLIENT_TYPE };

                var response = await httpClient.PostAsJsonAsync(
                    $"{ApiBaseUrl}/api/v1/sync/clients",
                    registerRequest,
                    jsonOptions,
                    cancellationToken
                );

                if (response.IsSuccessStatusCode)
                {
                    var clientResponse = await response.Content.ReadFromJsonAsync<ClientResponse>(jsonOptions, cancellationToken);
                    clientId = clientResponse?.Id?.ToString();
                    Logger.Log($"Registered sync client: {clientId}", LoggingTarget.Network);
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to register sync client: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                // Non-fatal - can still sync without client ID
            }
        }

        #endregion

        #region Preferences Sync

        public async Task SyncPreferencesAsync(CancellationToken cancellationToken = default)
        {
            await EnsureAuthenticatedAsync(cancellationToken);

            try
            {
                Status = SyncStatus.Syncing;

                var response = await httpClient.GetAsync(
                    $"{ApiBaseUrl}/api/v1/sync/preferences",
                    cancellationToken
                );

                if (response.IsSuccessStatusCode)
                {
                    var prefs = await response.Content.ReadFromJsonAsync<PreferencesResponse>(jsonOptions, cancellationToken);
                    if (prefs != null)
                    {
                        // TODO: Apply preferences to local config
                        // This would integrate with BeatSightConfigManager
                        Logger.Log($"Synced preferences (version {prefs.Version})", LoggingTarget.Network);
                    }
                }
                else
                {
                    Logger.Log($"Failed to sync preferences: {response.StatusCode}", LoggingTarget.Network);
                }

                Status = SyncStatus.Success;
            }
            catch (Exception ex)
            {
                Logger.Log($"Preferences sync error: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                Status = SyncStatus.Error;
                throw;
            }
        }

        public async Task UpdatePreferencesAsync(Dictionary<string, object> updates, CancellationToken cancellationToken = default)
        {
            await EnsureAuthenticatedAsync(cancellationToken);

            try
            {
                Status = SyncStatus.Syncing;

                var response = await httpClient.PutAsJsonAsync(
                    $"{ApiBaseUrl}/api/v1/sync/preferences",
                    updates,
                    jsonOptions,
                    cancellationToken
                );

                if (!response.IsSuccessStatusCode)
                {
                    var error = await response.Content.ReadAsStringAsync(cancellationToken);
                    Logger.Log($"Failed to update preferences: {response.StatusCode} - {error}", LoggingTarget.Network);
                    throw new HttpRequestException($"Failed to update preferences: {response.StatusCode}");
                }

                Logger.Log("Preferences updated successfully", LoggingTarget.Network);
                Status = SyncStatus.Success;
            }
            catch (Exception ex)
            {
                Logger.Log($"Preferences update error: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                Status = SyncStatus.Error;
                throw;
            }
        }

        #endregion

        #region Progress Sync

        public async Task SyncProgressAsync(CancellationToken cancellationToken = default)
        {
            await EnsureAuthenticatedAsync(cancellationToken);

            try
            {
                Status = SyncStatus.Syncing;

                // Get sync status first
                var statusResponse = await httpClient.GetAsync(
                    $"{ApiBaseUrl}/api/v1/sync/status",
                    cancellationToken
                );

                if (statusResponse.IsSuccessStatusCode)
                {
                    var status = await statusResponse.Content.ReadFromJsonAsync<SyncStatusResponse>(jsonOptions, cancellationToken);
                    if (status != null)
                    {
                        Logger.Log($"Sync status: {status.SyncedMaps}/{status.TotalMaps} maps synced, {status.Conflicts} conflicts", LoggingTarget.Network);
                    }
                }

                Status = SyncStatus.Success;
            }
            catch (Exception ex)
            {
                Logger.Log($"Progress sync error: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                Status = SyncStatus.Error;
                throw;
            }
        }

        #endregion

        #region Beatmap Sync

        public async Task<string> UploadBeatmapAsync(string localPath, CancellationToken cancellationToken = default)
        {
            await EnsureAuthenticatedAsync(cancellationToken);

            if (!File.Exists(localPath))
            {
                throw new FileNotFoundException("Beatmap file not found", localPath);
            }

            try
            {
                Status = SyncStatus.Syncing;

                // Read the beatmap file
                var beatmapJson = await File.ReadAllTextAsync(localPath, cancellationToken);
                var beatmapHash = ComputeFileHash(localPath);

                // Parse to get beatmap ID
                using var doc = JsonDocument.Parse(beatmapJson);
                var beatmapId = doc.RootElement
                    .GetProperty("metadata")
                    .GetProperty("beatmapId")
                    .GetString() ?? Guid.NewGuid().ToString();

                // Upload via storage endpoint
                using var content = new MultipartFormDataContent();
                var fileContent = new ByteArrayContent(Encoding.UTF8.GetBytes(beatmapJson));
                fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/json");
                content.Add(fileContent, "file", Path.GetFileName(localPath));

                var response = await httpClient.PostAsync(
                    $"{ApiBaseUrl}/api/v1/storage/beatmaps/{beatmapId}",
                    content,
                    cancellationToken
                );

                if (!response.IsSuccessStatusCode)
                {
                    var error = await response.Content.ReadAsStringAsync(cancellationToken);
                    Logger.Log($"Upload failed: {response.StatusCode} - {error}", LoggingTarget.Network);
                    throw new HttpRequestException($"Upload failed: {response.StatusCode}");
                }

                // Update manifest
                await UpdateManifestEntryAsync(beatmapId, 1, beatmapHash, cancellationToken);

                Logger.Log($"Uploaded beatmap: {beatmapId}", LoggingTarget.Network);
                Status = SyncStatus.Success;

                return beatmapId;
            }
            catch (Exception ex)
            {
                Logger.Log($"Upload error: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                Status = SyncStatus.Error;
                throw;
            }
        }

        public async Task<string> DownloadBeatmapAsync(string cloudId, string localPath, CancellationToken cancellationToken = default)
        {
            await EnsureAuthenticatedAsync(cancellationToken);

            try
            {
                Status = SyncStatus.Syncing;

                var response = await httpClient.GetAsync(
                    $"{ApiBaseUrl}/api/v1/storage/beatmaps/{cloudId}",
                    cancellationToken
                );

                if (!response.IsSuccessStatusCode)
                {
                    var error = await response.Content.ReadAsStringAsync(cancellationToken);
                    Logger.Log($"Download failed: {response.StatusCode} - {error}", LoggingTarget.Network);
                    throw new HttpRequestException($"Download failed: {response.StatusCode}");
                }

                var beatmapJson = await response.Content.ReadAsStringAsync(cancellationToken);

                // Ensure directory exists
                var directory = Path.GetDirectoryName(localPath);
                if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                await File.WriteAllTextAsync(localPath, beatmapJson, cancellationToken);

                Logger.Log($"Downloaded beatmap to: {localPath}", LoggingTarget.Network);
                Status = SyncStatus.Success;

                return localPath;
            }
            catch (Exception ex)
            {
                Logger.Log($"Download error: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                Status = SyncStatus.Error;
                throw;
            }
        }

        /// <summary>
        /// Compare local beatmap manifest with cloud to determine sync actions.
        /// </summary>
        public async Task<List<SyncActionItem>> CompareManifestAsync(
            List<ManifestEntry> localEntries,
            CancellationToken cancellationToken = default)
        {
            await EnsureAuthenticatedAsync(cancellationToken);

            try
            {
                var request = new ManifestCompareRequest
                {
                    ClientId = clientId,
                    LastSyncTimestamp = null, // TODO: Store and use last sync time
                    Beatmaps = localEntries
                };

                var response = await httpClient.PostAsJsonAsync(
                    $"{ApiBaseUrl}/api/v1/sync/manifest",
                    request,
                    jsonOptions,
                    cancellationToken
                );

                if (!response.IsSuccessStatusCode)
                {
                    throw new HttpRequestException($"Manifest compare failed: {response.StatusCode}");
                }

                var result = await response.Content.ReadFromJsonAsync<ManifestCompareResponse>(jsonOptions, cancellationToken);
                return result?.Actions ?? new List<SyncActionItem>();
            }
            catch (Exception ex)
            {
                Logger.Log($"Manifest compare error: {ex.Message}", LoggingTarget.Network, LogLevel.Error);
                throw;
            }
        }

        private async Task UpdateManifestEntryAsync(string mapId, int version, string checksum, CancellationToken cancellationToken)
        {
            var response = await httpClient.PostAsync(
                $"{ApiBaseUrl}/api/v1/sync/manifest/{mapId}?version={version}&checksum={Uri.EscapeDataString(checksum)}",
                null,
                cancellationToken
            );

            if (!response.IsSuccessStatusCode)
            {
                Logger.Log($"Failed to update manifest entry: {response.StatusCode}", LoggingTarget.Network);
            }
        }

        #endregion

        #region Token Storage

        // Simple XOR-based obfuscation using machine name as key
        // Note: This is NOT secure encryption, just basic obfuscation to prevent
        // casual token theft. For production, consider platform-specific secure storage
        // (Keychain on macOS, Credential Manager on Windows, Secret Service on Linux)

        private static byte[] ObfuscateBytes(byte[] data)
        {
            var key = Encoding.UTF8.GetBytes(Environment.MachineName + "BeatSight");
            var result = new byte[data.Length];
            for (int i = 0; i < data.Length; i++)
            {
                result[i] = (byte)(data[i] ^ key[i % key.Length]);
            }
            return result;
        }

        private void LoadStoredTokens()
        {
            try
            {
                // Store tokens in user's app data folder
                var tokenPath = GetTokenStoragePath();
                if (!File.Exists(tokenPath))
                    return;

                var obfuscated = File.ReadAllBytes(tokenPath);
                var json = Encoding.UTF8.GetString(ObfuscateBytes(obfuscated));

                var stored = JsonSerializer.Deserialize<StoredTokens>(json, jsonOptions);
                if (stored != null)
                {
                    accessToken = stored.AccessToken;
                    refreshToken = stored.RefreshToken;
                    tokenExpiry = stored.Expiry;
                    clientId = stored.ClientId;

                    if (IsAuthenticated)
                    {
                        httpClient.DefaultRequestHeaders.Authorization =
                            new AuthenticationHeaderValue("Bearer", accessToken);
                        Status = SyncStatus.Idle;
                    }
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to load stored tokens: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                // Non-fatal - just means user needs to login again
            }
        }

        private void SaveTokens()
        {
            try
            {
                var stored = new StoredTokens
                {
                    AccessToken = accessToken,
                    RefreshToken = refreshToken,
                    Expiry = tokenExpiry,
                    ClientId = clientId
                };

                var json = JsonSerializer.Serialize(stored, jsonOptions);
                var bytes = Encoding.UTF8.GetBytes(json);
                var obfuscated = ObfuscateBytes(bytes);

                var tokenPath = GetTokenStoragePath();
                var directory = Path.GetDirectoryName(tokenPath);
                if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                File.WriteAllBytes(tokenPath, obfuscated);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to save tokens: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }

        private void ClearStoredTokens()
        {
            try
            {
                var tokenPath = GetTokenStoragePath();
                if (File.Exists(tokenPath))
                {
                    File.Delete(tokenPath);
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to clear tokens: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }

        private static string GetTokenStoragePath()
        {
            var appData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(appData, "BeatSight", "cloud_tokens.dat");
        }

        private static string ComputeFileHash(string filePath)
        {
            using var sha256 = SHA256.Create();
            using var stream = File.OpenRead(filePath);
            var hash = sha256.ComputeHash(stream);
            return Convert.ToHexString(hash).ToLowerInvariant();
        }

        #endregion

        public void Dispose()
        {
            httpClient.Dispose();
        }

        #region DTOs

        private class TokenResponse
        {
            [JsonPropertyName("access_token")]
            public string AccessToken { get; set; } = "";

            [JsonPropertyName("refresh_token")]
            public string RefreshToken { get; set; } = "";

            [JsonPropertyName("token_type")]
            public string TokenType { get; set; } = "bearer";
        }

        private class ClientResponse
        {
            public Guid? Id { get; set; }
            public string? ClientName { get; set; }
            public string? ClientType { get; set; }
        }

        private class PreferencesResponse
        {
            public int Version { get; set; }
            public string Checksum { get; set; } = "";
            public double ScrollSpeed { get; set; }
            public string NoteSkin { get; set; } = "";
            public int AudioOffsetMs { get; set; }
            public int VisualOffsetMs { get; set; }
            public double BackgroundDim { get; set; }
            public double MasterVolume { get; set; }
            public double MusicVolume { get; set; }
            public double EffectsVolume { get; set; }
            public double HitsoundVolume { get; set; }
            public string Theme { get; set; } = "";
            public string Language { get; set; } = "";

            /// <summary>
            /// Custom settings dictionary for extensible preferences.
            /// Keys include: "developerMode", "showFpsCounter", "enableNotifications",
            /// "autoCheckUpdates", "crashReporting", "analyticsEnabled",
            /// "betaFeatures", "debugOverlay", "verboseLogging", "experimentalFeatures"
            /// </summary>
            public Dictionary<string, object>? CustomSettings { get; set; }
        }

        private class SyncStatusResponse
        {
            public int PreferencesVersion { get; set; }
            public string PreferencesChecksum { get; set; } = "";
            public int TotalMaps { get; set; }
            public int SyncedMaps { get; set; }
            public int PendingUploads { get; set; }
            public int PendingDownloads { get; set; }
            public int Conflicts { get; set; }
            public DateTime? LastSync { get; set; }
            public int Clients { get; set; }
        }

        private class StoredTokens
        {
            public string? AccessToken { get; set; }
            public string? RefreshToken { get; set; }
            public DateTime Expiry { get; set; }
            public string? ClientId { get; set; }
        }

        #endregion
    }

    #region Public DTOs for Manifest Sync

    /// <summary>
    /// Entry in the local beatmap manifest.
    /// </summary>
    public class ManifestEntry
    {
        [JsonPropertyName("map_id")]
        public string MapId { get; set; } = "";

        [JsonPropertyName("version")]
        public int Version { get; set; }

        [JsonPropertyName("checksum")]
        public string Checksum { get; set; } = "";

        [JsonPropertyName("sync_state")]
        public string SyncState { get; set; } = "synced";
    }

    /// <summary>
    /// Request to compare manifests.
    /// </summary>
    public class ManifestCompareRequest
    {
        [JsonPropertyName("client_id")]
        public string? ClientId { get; set; }

        [JsonPropertyName("last_sync_timestamp")]
        public DateTime? LastSyncTimestamp { get; set; }

        [JsonPropertyName("beatmaps")]
        public List<ManifestEntry> Beatmaps { get; set; } = new();
    }

    /// <summary>
    /// Response from manifest comparison.
    /// </summary>
    public class ManifestCompareResponse
    {
        [JsonPropertyName("server_timestamp")]
        public DateTime ServerTimestamp { get; set; }

        [JsonPropertyName("actions")]
        public List<SyncActionItem> Actions { get; set; } = new();
    }

    /// <summary>
    /// Sync action determined by manifest comparison.
    /// </summary>
    public class SyncActionItem
    {
        [JsonPropertyName("map_id")]
        public string MapId { get; set; } = "";

        [JsonPropertyName("action")]
        public string Action { get; set; } = "";

        [JsonPropertyName("reason")]
        public string Reason { get; set; } = "";

        [JsonPropertyName("cloud_version")]
        public int? CloudVersion { get; set; }

        [JsonPropertyName("cloud_checksum")]
        public string? CloudChecksum { get; set; }

        [JsonPropertyName("local_version")]
        public int? LocalVersion { get; set; }
    }

    #endregion
}
