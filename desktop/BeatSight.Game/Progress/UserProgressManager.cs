using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json;
using osu.Framework.Logging;
using osu.Framework.Platform;

namespace BeatSight.Game.Progress
{
    /// <summary>
    /// Manages user progress tracking and persistence for practice sessions.
    /// Stores song progress data locally in JSON format for offline use.
    /// </summary>
    public class UserProgressManager : IDisposable
    {
        private const string ProgressFileName = "user_progress.json";
        private const int MaxRecentlyPlayed = 50;

        private readonly Storage storage;
        private readonly object saveLock = new();

        private Dictionary<string, SongProgress> songProgressMap = new();
        private List<string> recentlyPlayedIds = new();
        private bool isDirty;

        /// <summary>
        /// Event fired when song progress is updated.
        /// </summary>
        public event Action<string, SongProgress>? ProgressUpdated;

        public UserProgressManager(Storage storage)
        {
            this.storage = storage;
            load();
        }

        /// <summary>
        /// Gets progress for a specific beatmap by its ID.
        /// </summary>
        public SongProgress? GetProgress(string beatmapId)
        {
            return songProgressMap.TryGetValue(beatmapId, out var progress) ? progress : null;
        }

        /// <summary>
        /// Gets or creates progress for a specific beatmap.
        /// </summary>
        public SongProgress GetOrCreateProgress(string beatmapId)
        {
            if (!songProgressMap.TryGetValue(beatmapId, out var progress))
            {
                progress = new SongProgress
                {
                    BeatmapId = beatmapId,
                    FirstPlayedAt = DateTimeOffset.UtcNow
                };
                songProgressMap[beatmapId] = progress;
                isDirty = true;
            }
            return progress;
        }

        /// <summary>
        /// Records the start of a play session for a beatmap.
        /// Call this when playback begins.
        /// </summary>
        public void RecordPlayStart(string beatmapId)
        {
            var progress = GetOrCreateProgress(beatmapId);
            progress.PlayCount++;
            progress.LastPlayedAt = DateTimeOffset.UtcNow;

            updateRecentlyPlayed(beatmapId);

            isDirty = true;
            save();

            ProgressUpdated?.Invoke(beatmapId, progress);
        }

        /// <summary>
        /// Records progress during playback.
        /// Call this periodically or when the user reaches new milestones.
        /// </summary>
        /// <param name="beatmapId">The beatmap ID</param>
        /// <param name="progressFraction">How far through the song (0.0 to 1.0)</param>
        /// <param name="elapsedMs">Time spent this session in milliseconds</param>
        public void RecordPlayProgress(string beatmapId, double progressFraction, long elapsedMs)
        {
            var progress = GetOrCreateProgress(beatmapId);

            if (progressFraction > progress.FurthestProgress)
                progress.FurthestProgress = Math.Min(progressFraction, 1.0);

            progress.TotalPlayTimeMs += elapsedMs;

            isDirty = true;
        }

        /// <summary>
        /// Records completion of a song (reached the end during playback).
        /// </summary>
        /// <param name="beatmapId">The beatmap ID</param>
        /// <param name="speedMultiplier">Speed at which the song was played</param>
        public void RecordCompletion(string beatmapId, double speedMultiplier)
        {
            var progress = GetOrCreateProgress(beatmapId);

            progress.Completed = true;
            progress.FurthestProgress = 1.0;

            // Track speed range used
            if (!progress.SlowestCompletionSpeed.HasValue || speedMultiplier < progress.SlowestCompletionSpeed)
                progress.SlowestCompletionSpeed = speedMultiplier;
            if (!progress.FastestCompletionSpeed.HasValue || speedMultiplier > progress.FastestCompletionSpeed)
                progress.FastestCompletionSpeed = speedMultiplier;

            isDirty = true;
            save();

            ProgressUpdated?.Invoke(beatmapId, progress);
        }

        /// <summary>
        /// Records a practice session with loop information.
        /// </summary>
        public void RecordPracticeSession(string beatmapId, long durationMs, double? loopStartMs, double? loopEndMs, double speedMultiplier)
        {
            var progress = GetOrCreateProgress(beatmapId);

            progress.PracticeSessions.Add(new PracticeSession
            {
                Timestamp = DateTimeOffset.UtcNow,
                DurationMs = durationMs,
                LoopStartMs = loopStartMs,
                LoopEndMs = loopEndMs,
                SpeedMultiplier = speedMultiplier
            });

            progress.TotalPlayTimeMs += durationMs;

            // Keep practice session history manageable
            if (progress.PracticeSessions.Count > 100)
                progress.PracticeSessions.RemoveRange(0, progress.PracticeSessions.Count - 100);

            isDirty = true;
        }

        /// <summary>
        /// Marks a section as difficult for later practice.
        /// </summary>
        public void MarkDifficultSection(string beatmapId, double startMs, double endMs, string? description = null)
        {
            var progress = GetOrCreateProgress(beatmapId);

            // Check for overlapping sections and merge or skip
            var existing = progress.DifficultSections.FirstOrDefault(
                s => Math.Abs(s.StartMs - startMs) < 1000 && Math.Abs(s.EndMs - endMs) < 1000);

            if (existing != null)
            {
                existing.Description = description ?? existing.Description;
                existing.MarkedAt = DateTimeOffset.UtcNow;
            }
            else
            {
                progress.DifficultSections.Add(new DifficultSection
                {
                    StartMs = startMs,
                    EndMs = endMs,
                    Description = description,
                    MarkedAt = DateTimeOffset.UtcNow
                });
            }

            isDirty = true;
            save();
        }

        /// <summary>
        /// Marks a difficult section as mastered.
        /// </summary>
        public void MarkSectionMastered(string beatmapId, double startMs, double endMs)
        {
            var progress = GetProgress(beatmapId);
            if (progress == null) return;

            var section = progress.DifficultSections.FirstOrDefault(
                s => Math.Abs(s.StartMs - startMs) < 1000 && Math.Abs(s.EndMs - endMs) < 1000);

            if (section != null)
            {
                section.Mastered = true;
                isDirty = true;
                save();
            }
        }

        /// <summary>
        /// Toggles favorite status for a song.
        /// </summary>
        public bool ToggleFavorite(string beatmapId)
        {
            var progress = GetOrCreateProgress(beatmapId);
            progress.IsFavorite = !progress.IsFavorite;

            isDirty = true;
            save();

            ProgressUpdated?.Invoke(beatmapId, progress);
            return progress.IsFavorite;
        }

        /// <summary>
        /// Sets user's personal difficulty rating for a song (1-5 scale).
        /// </summary>
        public void SetPersonalRating(string beatmapId, int rating)
        {
            if (rating < 1 || rating > 5) return;

            var progress = GetOrCreateProgress(beatmapId);
            progress.PersonalRating = rating;

            isDirty = true;
            save();

            ProgressUpdated?.Invoke(beatmapId, progress);
        }

        /// <summary>
        /// Adds or removes a tag from a song.
        /// </summary>
        public void ToggleTag(string beatmapId, string tag)
        {
            var progress = GetOrCreateProgress(beatmapId);

            if (progress.Tags.Contains(tag))
                progress.Tags.Remove(tag);
            else
                progress.Tags.Add(tag);

            isDirty = true;
            save();
        }

        /// <summary>
        /// Sets user notes for a song.
        /// </summary>
        public void SetNotes(string beatmapId, string notes)
        {
            var progress = GetOrCreateProgress(beatmapId);
            progress.Notes = string.IsNullOrWhiteSpace(notes) ? null : notes;

            isDirty = true;
            save();
        }

        /// <summary>
        /// Gets all songs marked as favorites.
        /// </summary>
        public IReadOnlyList<SongProgress> GetFavorites()
        {
            return songProgressMap.Values.Where(p => p.IsFavorite).ToList();
        }

        /// <summary>
        /// Gets songs that need practice (have difficult sections not yet mastered).
        /// </summary>
        public IReadOnlyList<SongProgress> GetSongsNeedingPractice()
        {
            return songProgressMap.Values
                .Where(p => p.DifficultSections.Any(s => !s.Mastered))
                .OrderByDescending(p => p.DifficultSections.Count(s => !s.Mastered))
                .ToList();
        }

        /// <summary>
        /// Gets recently played song progress entries.
        /// </summary>
        public IReadOnlyList<SongProgress> GetRecentlyPlayed(int count = 10)
        {
            return songProgressMap.Values
                .OrderByDescending(p => p.LastPlayedAt)
                .Take(count)
                .ToList();
        }

        /// <summary>
        /// Generates a deterministic beatmap ID from file path and metadata.
        /// </summary>
        public static string GenerateBeatmapId(string filePath, string? title = null, string? artist = null)
        {
            // Use a combination of normalized path and optional metadata for uniqueness
            var normalizedPath = Path.GetFullPath(filePath).ToLowerInvariant().Replace('\\', '/');
            var input = $"{normalizedPath}|{title ?? ""}|{artist ?? ""}";

            using var sha256 = SHA256.Create();
            var bytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(input));
            return Convert.ToBase64String(bytes).Substring(0, 22).Replace('/', '_').Replace('+', '-');
        }

        /// <summary>
        /// Forces a save of all progress data.
        /// </summary>
        public void Save()
        {
            save();
        }

        private void load()
        {
            try
            {
                using var progressStream = storage.GetStream(ProgressFileName, FileAccess.Read, FileMode.OpenOrCreate);
                if (progressStream.Length > 0)
                {
                    using var reader = new StreamReader(progressStream);
                    var json = reader.ReadToEnd();
                    var loaded = JsonConvert.DeserializeObject<ProgressData>(json);
                    if (loaded != null)
                    {
                        songProgressMap = loaded.Songs ?? new Dictionary<string, SongProgress>();
                        recentlyPlayedIds = loaded.RecentlyPlayedIds ?? new List<string>();
                    }
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to load progress data: {ex.Message}", LoggingTarget.Runtime, LogLevel.Important);
            }
        }

        private void save()
        {
            if (!isDirty) return;

            lock (saveLock)
            {
                try
                {
                    var data = new ProgressData
                    {
                        Songs = songProgressMap,
                        RecentlyPlayedIds = recentlyPlayedIds
                    };

                    var json = JsonConvert.SerializeObject(data, Formatting.Indented);
                    using var stream = storage.CreateFileSafely(ProgressFileName);
                    using var writer = new StreamWriter(stream);
                    writer.Write(json);

                    isDirty = false;
                }
                catch (Exception ex)
                {
                    Logger.Log($"Failed to save progress data: {ex.Message}", LoggingTarget.Runtime, LogLevel.Important);
                }
            }
        }

        private void updateRecentlyPlayed(string beatmapId)
        {
            recentlyPlayedIds.Remove(beatmapId);
            recentlyPlayedIds.Insert(0, beatmapId);
            if (recentlyPlayedIds.Count > MaxRecentlyPlayed)
                recentlyPlayedIds.RemoveRange(MaxRecentlyPlayed, recentlyPlayedIds.Count - MaxRecentlyPlayed);
        }

        public void Dispose()
        {
            if (isDirty)
                save();
        }

        /// <summary>
        /// Internal data structure for JSON serialization.
        /// </summary>
        private class ProgressData
        {
            public Dictionary<string, SongProgress>? Songs { get; set; }
            public List<string>? RecentlyPlayedIds { get; set; }
        }
    }
}
