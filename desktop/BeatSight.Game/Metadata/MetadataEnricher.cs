using System;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Mapping;
using osu.Framework.Logging;
using TagLib;
using TagLibFile = TagLib.File;

namespace BeatSight.Game.Metadata
{
    /// <summary>
    /// Provides fallback metadata enrichment when the AI pipeline cannot resolve artist/title information.
    /// </summary>
    public static class MetadataEnricher
    {
        private const string unknownArtistPlaceholder = "Unknown Artist";
        private static readonly HttpClient httpClient;
        private static readonly SemaphoreSlim musicBrainzGate = new(1, 1);
        private static DateTime lastMusicBrainzRequestUtc = DateTime.MinValue;

        static MetadataEnricher()
        {
            httpClient = new HttpClient
            {
                Timeout = TimeSpan.FromSeconds(12)
            };

            // MusicBrainz requires a descriptive user agent identifying the application and maintainer.
            httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("BeatSight/1.0 (+https://beatsight.app/contact)");
            httpClient.DefaultRequestHeaders.Accept.ParseAdd("application/json");
        }

        public static async Task EnrichAsync(Beatmap beatmap, ImportedAudioTrack track, CancellationToken cancellationToken)
        {
            if (beatmap == null) throw new ArgumentNullException(nameof(beatmap));
            if (track == null) throw new ArgumentNullException(nameof(track));

            bool artistMissing = string.IsNullOrWhiteSpace(beatmap.Metadata.Artist) || string.Equals(beatmap.Metadata.Artist, unknownArtistPlaceholder, StringComparison.OrdinalIgnoreCase);
            bool titleMissing = string.IsNullOrWhiteSpace(beatmap.Metadata.Title);

            if (!artistMissing && !titleMissing)
                return;

            await tryReadEmbeddedTagsAsync(beatmap, track, cancellationToken).ConfigureAwait(false);

            artistMissing = string.IsNullOrWhiteSpace(beatmap.Metadata.Artist) || string.Equals(beatmap.Metadata.Artist, unknownArtistPlaceholder, StringComparison.OrdinalIgnoreCase);
            titleMissing = string.IsNullOrWhiteSpace(beatmap.Metadata.Title);

            if (!artistMissing && !titleMissing)
                return;

            await tryResolveViaMusicBrainzAsync(beatmap, track, titleMissing, artistMissing, cancellationToken).ConfigureAwait(false);
        }

        private static async Task tryReadEmbeddedTagsAsync(Beatmap beatmap, ImportedAudioTrack track, CancellationToken cancellationToken)
        {
            if (!System.IO.File.Exists(track.StoredPath))
                return;

            try
            {
                await Task.Run(() =>
                {
                    using var file = TagLibFile.Create(track.StoredPath);
                    var tag = file.Tag;

                    if (string.IsNullOrWhiteSpace(beatmap.Metadata.Title) && !string.IsNullOrWhiteSpace(tag.Title))
                        beatmap.Metadata.Title = tag.Title;

                    string? artist = tag.Performers?.FirstOrDefault(p => !string.IsNullOrWhiteSpace(p))
                                     ?? tag.AlbumArtists?.FirstOrDefault(p => !string.IsNullOrWhiteSpace(p))
                                     ?? tag.JoinedPerformers;

                    if (!string.IsNullOrWhiteSpace(artist) && (string.IsNullOrWhiteSpace(beatmap.Metadata.Artist) || string.Equals(beatmap.Metadata.Artist, unknownArtistPlaceholder, StringComparison.OrdinalIgnoreCase)))
                        beatmap.Metadata.Artist = artist;

                    if (string.IsNullOrWhiteSpace(beatmap.Metadata.Source) && !string.IsNullOrWhiteSpace(tag.Album))
                        beatmap.Metadata.Source = tag.Album;
                }, cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                Logger.Log($"Embedded tag extraction failed: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private static async Task tryResolveViaMusicBrainzAsync(Beatmap beatmap, ImportedAudioTrack track, bool titleMissing, bool artistMissing, CancellationToken cancellationToken)
        {
            string queryTitle = !string.IsNullOrWhiteSpace(beatmap.Metadata.Title)
                ? beatmap.Metadata.Title
                : track.DisplayName;

            if (string.IsNullOrWhiteSpace(queryTitle))
                return;

            try
            {
                double? durationSeconds = null;

                if (track.DurationMilliseconds.HasValue)
                    durationSeconds = track.DurationMilliseconds.Value / 1000.0;
                else if (beatmap.Audio.Duration > 0)
                    durationSeconds = beatmap.Audio.Duration / 1000.0;

                var resolution = await lookupMusicBrainzAsync(queryTitle, durationSeconds, cancellationToken).ConfigureAwait(false);
                if (resolution == null)
                    return;

                if (artistMissing && !string.IsNullOrWhiteSpace(resolution.Artist))
                    beatmap.Metadata.Artist = resolution.Artist;

                if (titleMissing && !string.IsNullOrWhiteSpace(resolution.Title))
                    beatmap.Metadata.Title = resolution.Title;

                if (!beatmap.Metadata.Tags.Contains("metadata:musicbrainz"))
                    beatmap.Metadata.Tags.Add("metadata:musicbrainz");

                if (beatmap.Editor?.AiGenerationMetadata != null)
                {
                    beatmap.Editor.AiGenerationMetadata.MetadataProvider ??= "musicbrainz";
                    beatmap.Editor.AiGenerationMetadata.MetadataConfidence ??= Math.Clamp(resolution.Score, 0, 1);
                }
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                Logger.Log($"MusicBrainz lookup failed: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private static async Task<MusicBrainzMetadata?> lookupMusicBrainzAsync(string title, double? durationSeconds, CancellationToken cancellationToken)
        {
            await musicBrainzGate.WaitAsync(cancellationToken).ConfigureAwait(false);

            try
            {
                if (lastMusicBrainzRequestUtc != DateTime.MinValue)
                {
                    TimeSpan sinceLast = DateTime.UtcNow - lastMusicBrainzRequestUtc;
                    if (sinceLast < TimeSpan.FromSeconds(1))
                        await Task.Delay(TimeSpan.FromSeconds(1) - sinceLast, cancellationToken).ConfigureAwait(false);
                }

                lastMusicBrainzRequestUtc = DateTime.UtcNow;

                var builder = new StringBuilder();
                builder.Append("recording:\"").Append(title).Append('\"');

                if (durationSeconds.HasValue)
                {
                    int rounded = Math.Max(1, (int)Math.Round(durationSeconds.Value));
                    builder.Append(" AND dur:").Append(rounded);
                }

                string url = "https://musicbrainz.org/ws/2/recording/?query=" + Uri.EscapeDataString(builder.ToString()) + "&fmt=json&limit=5";

                using var request = new HttpRequestMessage(HttpMethod.Get, url);
                using var response = await httpClient.SendAsync(request, cancellationToken).ConfigureAwait(false);
                response.EnsureSuccessStatusCode();

                await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
                using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken).ConfigureAwait(false);

                if (!document.RootElement.TryGetProperty("recordings", out var recordings) || recordings.ValueKind != JsonValueKind.Array)
                    return null;

                MusicBrainzMetadata? best = null;

                foreach (var entry in recordings.EnumerateArray())
                {
                    int score = entry.TryGetProperty("score", out var scoreProp) && scoreProp.TryGetInt32(out var parsedScore)
                        ? parsedScore
                        : 0;

                    string? entryTitle = entry.TryGetProperty("title", out var titleProp) ? titleProp.GetString() : null;
                    string? artist = extractArtist(entry);

                    if (string.IsNullOrWhiteSpace(artist))
                        continue;

                    double normalisedScore = Math.Clamp(score / 100.0, 0, 1);

                    if (best == null || normalisedScore > best.Score || (Math.Abs(normalisedScore - best.Score) < 0.05 && entryTitle != null && string.Equals(entryTitle, title, StringComparison.OrdinalIgnoreCase)))
                        best = new MusicBrainzMetadata(entryTitle ?? title, artist, normalisedScore);
                }

                return best;
            }
            finally
            {
                musicBrainzGate.Release();
            }
        }

        private static string? extractArtist(JsonElement entry)
        {
            if (!entry.TryGetProperty("artist-credit", out var artistCredit) || artistCredit.ValueKind != JsonValueKind.Array)
                return null;

            foreach (var credit in artistCredit.EnumerateArray())
            {
                if (credit.TryGetProperty("name", out var nameProp))
                {
                    string? candidate = nameProp.GetString();
                    if (!string.IsNullOrWhiteSpace(candidate))
                        return candidate;
                }

                if (credit.TryGetProperty("artist", out var artistProp) && artistProp.ValueKind == JsonValueKind.Object && artistProp.TryGetProperty("name", out var nestedName))
                {
                    string? candidate = nestedName.GetString();
                    if (!string.IsNullOrWhiteSpace(candidate))
                        return candidate;
                }
            }

            return null;
        }

        private sealed record MusicBrainzMetadata(string Title, string Artist, double Score);
    }
}
