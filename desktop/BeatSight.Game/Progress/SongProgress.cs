using System;
using System.Collections.Generic;

namespace BeatSight.Game.Progress
{
    /// <summary>
    /// Represents a user's progress and play history for a specific song/beatmap.
    /// </summary>
    public class SongProgress
    {
        /// <summary>
        /// Unique identifier for the beatmap (hash of the .bsm file or composite key).
        /// </summary>
        public string BeatmapId { get; set; } = string.Empty;

        /// <summary>
        /// Total number of times this song has been played.
        /// </summary>
        public int PlayCount { get; set; }

        /// <summary>
        /// Total time spent playing this song in milliseconds.
        /// </summary>
        public long TotalPlayTimeMs { get; set; }

        /// <summary>
        /// The furthest point reached in the song (0.0 to 1.0, percentage of song duration).
        /// </summary>
        public double FurthestProgress { get; set; }

        /// <summary>
        /// Whether the user has completed the song at least once (reached the end).
        /// </summary>
        public bool Completed { get; set; }

        /// <summary>
        /// Date and time of the first play.
        /// </summary>
        public DateTimeOffset FirstPlayedAt { get; set; }

        /// <summary>
        /// Date and time of the most recent play.
        /// </summary>
        public DateTimeOffset LastPlayedAt { get; set; }

        /// <summary>
        /// The slowest speed multiplier used to complete the song (lower = easier).
        /// Null if never completed.
        /// </summary>
        public double? SlowestCompletionSpeed { get; set; }

        /// <summary>
        /// The fastest speed multiplier used to complete the song.
        /// Null if never completed.
        /// </summary>
        public double? FastestCompletionSpeed { get; set; }

        /// <summary>
        /// User's personal rating/difficulty assessment (1-5 scale, optional).
        /// </summary>
        public int? PersonalRating { get; set; }

        /// <summary>
        /// User-added notes or comments about the song.
        /// </summary>
        public string? Notes { get; set; }

        /// <summary>
        /// Whether this song is marked as a favorite.
        /// </summary>
        public bool IsFavorite { get; set; }

        /// <summary>
        /// Tags applied by the user for organization.
        /// </summary>
        public List<string> Tags { get; set; } = new();

        /// <summary>
        /// History of practice sessions with loop regions.
        /// </summary>
        public List<PracticeSession> PracticeSessions { get; set; } = new();

        /// <summary>
        /// Sections identified as difficult that need extra practice.
        /// </summary>
        public List<DifficultSection> DifficultSections { get; set; } = new();
    }

    /// <summary>
    /// Records a single practice session for a song.
    /// </summary>
    public class PracticeSession
    {
        /// <summary>
        /// When the practice session occurred.
        /// </summary>
        public DateTimeOffset Timestamp { get; set; }

        /// <summary>
        /// Duration of the practice session in milliseconds.
        /// </summary>
        public long DurationMs { get; set; }

        /// <summary>
        /// If looping was used, the start time of the loop region in milliseconds.
        /// </summary>
        public double? LoopStartMs { get; set; }

        /// <summary>
        /// If looping was used, the end time of the loop region in milliseconds.
        /// </summary>
        public double? LoopEndMs { get; set; }

        /// <summary>
        /// Speed multiplier used during practice.
        /// </summary>
        public double SpeedMultiplier { get; set; } = 1.0;
    }

    /// <summary>
    /// Marks a section of a song that the user finds difficult.
    /// </summary>
    public class DifficultSection
    {
        /// <summary>
        /// Start time of the section in milliseconds.
        /// </summary>
        public double StartMs { get; set; }

        /// <summary>
        /// End time of the section in milliseconds.
        /// </summary>
        public double EndMs { get; set; }

        /// <summary>
        /// User-provided description of why this section is difficult.
        /// </summary>
        public string? Description { get; set; }

        /// <summary>
        /// When this section was marked.
        /// </summary>
        public DateTimeOffset MarkedAt { get; set; }

        /// <summary>
        /// Whether the user considers this section mastered now.
        /// </summary>
        public bool Mastered { get; set; }
    }
}
