using System;
using System.IO;
using Newtonsoft.Json;

namespace BeatSight.Game.Beatmaps
{
    /// <summary>
    /// Handles loading and saving beatmap files
    /// </summary>
    public static class BeatmapLoader
    {
        public static Beatmap LoadFromFile(string path)
        {
            if (!File.Exists(path))
                throw new FileNotFoundException($"Beatmap file not found: {path}");

            string json = File.ReadAllText(path);
            var beatmap = JsonConvert.DeserializeObject<Beatmap>(json);

            if (beatmap == null)
                throw new InvalidDataException("Failed to parse beatmap file");

            ValidateBeatmap(beatmap);
            return beatmap;
        }

        public static void SaveToFile(Beatmap beatmap, string path)
        {
            ValidateBeatmap(beatmap);

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;

            string json = JsonConvert.SerializeObject(beatmap, Formatting.Indented);
            File.WriteAllText(path, json);
        }

        private static void ValidateBeatmap(Beatmap beatmap)
        {
            if (string.IsNullOrEmpty(beatmap.Metadata.Title))
                throw new InvalidDataException("Beatmap must have a title");

            if (string.IsNullOrEmpty(beatmap.Metadata.Artist))
                throw new InvalidDataException("Beatmap must have an artist");

            if (string.IsNullOrEmpty(beatmap.Audio.Filename))
                throw new InvalidDataException("Beatmap must reference an audio file");

            if (beatmap.HitObjects.Count == 0)
                throw new InvalidDataException("Beatmap must have at least one hit object");

            // Sort hit objects by time
            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
        }
    }
}
