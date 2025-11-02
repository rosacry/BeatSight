using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace BeatSight.Game.Beatmaps
{
    /// <summary>
    /// Centralised beatmap discovery utilities.
    /// </summary>
    public static class BeatmapLibrary
    {
        public sealed class BeatmapEntry
        {
            public required string Path { get; init; }
            public required Beatmap Beatmap { get; init; }
        }

        /// <summary>
        /// Returns the full list of discoverable beatmaps. Directories are scanned on demand.
        /// </summary>
        public static IReadOnlyList<BeatmapEntry> GetAvailableBeatmaps()
        {
            var results = new List<BeatmapEntry>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (var directory in EnumerateSearchDirectories())
            {
                if (!Directory.Exists(directory))
                    continue;

                foreach (var file in Directory.EnumerateFiles(directory, "*.bsm", SearchOption.AllDirectories))
                {
                    string normalisedPath = Path.GetFullPath(file);
                    if (!seen.Add(normalisedPath))
                        continue;

                    try
                    {
                        var beatmap = BeatmapLoader.LoadFromFile(normalisedPath);
                        results.Add(new BeatmapEntry
                        {
                            Path = normalisedPath,
                            Beatmap = beatmap
                        });
                    }
                    catch
                    {
                        // Ignore invalid beatmaps for now – we can surface this via diagnostics later.
                    }
                }
            }

            return results
                .OrderBy(entry => entry.Beatmap.Metadata.Title, StringComparer.OrdinalIgnoreCase)
                .ThenBy(entry => entry.Beatmap.Metadata.Artist, StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        /// <summary>
        /// Attempts to find a fallback beatmap path. Returns true if one is available.
        /// </summary>
        public static bool TryGetDefaultBeatmapPath(out string path)
        {
            foreach (var directory in EnumerateSearchDirectories())
            {
                if (!Directory.Exists(directory))
                    continue;

                var candidate = Directory.EnumerateFiles(directory, "*.bsm", SearchOption.TopDirectoryOnly).FirstOrDefault();
                if (!string.IsNullOrEmpty(candidate))
                {
                    path = Path.GetFullPath(candidate);
                    return true;
                }
            }

            path = string.Empty;
            return false;
        }

        private static IEnumerable<string> EnumerateSearchDirectories()
        {
            string baseDir = AppContext.BaseDirectory;
            string solutionRoot = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", ".."));

            yield return Path.Combine(solutionRoot, "beatmaps");
            yield return Path.Combine(solutionRoot, "shared", "formats");

            var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            if (!string.IsNullOrEmpty(home))
                yield return Path.Combine(home, "BeatSight", "Beatmaps");
        }
    }
}
