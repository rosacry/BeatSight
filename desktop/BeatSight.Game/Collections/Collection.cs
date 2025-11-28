using System;
using System.Collections.Generic;

namespace BeatSight.Game.Collections
{
    /// <summary>
    /// Represents a user-created collection of beatmaps for organization.
    /// </summary>
    public class Collection
    {
        /// <summary>
        /// Unique identifier for the collection.
        /// </summary>
        public Guid Id { get; set; } = Guid.NewGuid();

        /// <summary>
        /// Display name of the collection.
        /// </summary>
        public string Name { get; set; } = string.Empty;

        /// <summary>
        /// Optional description for the collection.
        /// </summary>
        public string? Description { get; set; }

        /// <summary>
        /// When the collection was created.
        /// </summary>
        public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

        /// <summary>
        /// When the collection was last modified.
        /// </summary>
        public DateTimeOffset ModifiedAt { get; set; } = DateTimeOffset.UtcNow;

        /// <summary>
        /// List of beatmap identifiers in this collection.
        /// Each ID is generated from the beatmap's path, title, and artist.
        /// </summary>
        public List<string> BeatmapIds { get; set; } = new();

        /// <summary>
        /// Optional color for the collection (used in UI).
        /// Format: "#RRGGBB"
        /// </summary>
        public string? Color { get; set; }
    }
}
