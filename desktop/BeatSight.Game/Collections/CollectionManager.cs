using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using osu.Framework.Logging;
using osu.Framework.Platform;

namespace BeatSight.Game.Collections
{
    /// <summary>
    /// Manages user collections of beatmaps.
    /// </summary>
    public class CollectionManager
    {
        private const string CollectionsFile = "collections.json";

        private readonly Storage storage;
        private List<Collection> collections = new();

        public CollectionManager(Storage storage)
        {
            this.storage = storage;
            Load();
        }

        /// <summary>
        /// Gets all collections.
        /// </summary>
        public IReadOnlyList<Collection> Collections => collections.AsReadOnly();

        /// <summary>
        /// Creates a new collection with the given name.
        /// </summary>
        public Collection CreateCollection(string name, string? description = null)
        {
            var collection = new Collection
            {
                Name = name,
                Description = description
            };

            collections.Add(collection);
            Save();

            Logger.Log($"Created collection: {name}", LoggingTarget.Runtime, LogLevel.Debug);
            return collection;
        }

        /// <summary>
        /// Deletes a collection by ID.
        /// </summary>
        public bool DeleteCollection(Guid collectionId)
        {
            var collection = collections.FirstOrDefault(c => c.Id == collectionId);
            if (collection == null)
                return false;

            collections.Remove(collection);
            Save();

            Logger.Log($"Deleted collection: {collection.Name}", LoggingTarget.Runtime, LogLevel.Debug);
            return true;
        }

        /// <summary>
        /// Renames a collection.
        /// </summary>
        public bool RenameCollection(Guid collectionId, string newName)
        {
            var collection = collections.FirstOrDefault(c => c.Id == collectionId);
            if (collection == null)
                return false;

            collection.Name = newName;
            collection.ModifiedAt = DateTimeOffset.UtcNow;
            Save();

            return true;
        }

        /// <summary>
        /// Adds a beatmap to a collection.
        /// </summary>
        public bool AddToCollection(Guid collectionId, string beatmapId)
        {
            var collection = collections.FirstOrDefault(c => c.Id == collectionId);
            if (collection == null)
                return false;

            if (collection.BeatmapIds.Contains(beatmapId))
                return true; // Already in collection

            collection.BeatmapIds.Add(beatmapId);
            collection.ModifiedAt = DateTimeOffset.UtcNow;
            Save();

            Logger.Log($"Added beatmap {beatmapId} to collection {collection.Name}", LoggingTarget.Runtime, LogLevel.Debug);
            return true;
        }

        /// <summary>
        /// Removes a beatmap from a collection.
        /// </summary>
        public bool RemoveFromCollection(Guid collectionId, string beatmapId)
        {
            var collection = collections.FirstOrDefault(c => c.Id == collectionId);
            if (collection == null)
                return false;

            bool removed = collection.BeatmapIds.Remove(beatmapId);
            if (removed)
            {
                collection.ModifiedAt = DateTimeOffset.UtcNow;
                Save();
            }

            return removed;
        }

        /// <summary>
        /// Gets all collections that contain the specified beatmap.
        /// </summary>
        public IEnumerable<Collection> GetCollectionsForBeatmap(string beatmapId)
        {
            return collections.Where(c => c.BeatmapIds.Contains(beatmapId));
        }

        /// <summary>
        /// Checks if a beatmap is in any collection.
        /// </summary>
        public bool IsInAnyCollection(string beatmapId)
        {
            return collections.Any(c => c.BeatmapIds.Contains(beatmapId));
        }

        /// <summary>
        /// Gets a collection by ID.
        /// </summary>
        public Collection? GetCollection(Guid collectionId)
        {
            return collections.FirstOrDefault(c => c.Id == collectionId);
        }

        private void Load()
        {
            try
            {
                if (!storage.Exists(CollectionsFile))
                {
                    collections = new List<Collection>();
                    return;
                }

                using var stream = storage.GetStream(CollectionsFile);
                if (stream == null)
                {
                    collections = new List<Collection>();
                    return;
                }

                using var reader = new StreamReader(stream);
                string json = reader.ReadToEnd();

                collections = JsonSerializer.Deserialize<List<Collection>>(json, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                }) ?? new List<Collection>();

                Logger.Log($"Loaded {collections.Count} collections", LoggingTarget.Runtime, LogLevel.Debug);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to load collections: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                collections = new List<Collection>();
            }
        }

        private void Save()
        {
            try
            {
                string json = JsonSerializer.Serialize(collections, new JsonSerializerOptions
                {
                    WriteIndented = true
                });

                using var stream = storage.CreateFileSafely(CollectionsFile);
                using var writer = new StreamWriter(stream);
                writer.Write(json);

                Logger.Log($"Saved {collections.Count} collections", LoggingTarget.Runtime, LogLevel.Debug);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to save collections: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }
    }
}
