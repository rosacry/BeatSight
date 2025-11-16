using System;
using System.IO;
using System.Linq;
using BeatSight.Game.Configuration;
using osu.Framework.IO.Stores;
using osu.Framework.Platform;
using osu.Framework.Logging;

namespace BeatSight.Game.Audio
{
    internal static class MetronomeSampleBootstrap
    {
        private static readonly string[] additionalResourceFiles =
        {
            "Samples/Metronome/Credits.txt"
        };

        private static readonly string[] resourcePaths = Enum.GetValues<MetronomeSoundOption>()
            .SelectMany(option =>
            {
                var (accent, regular) = MetronomeSampleLibrary.GetSamplePaths(option);
                return new[] { accent, regular };
            })
            .Concat(additionalResourceFiles)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();

        private static readonly string[] installSearchFolders =
        {
            UserAssetDirectories.MetronomeSounds,
            Path.Combine("Content", UserAssetDirectories.MetronomeSounds),
            "metronome_sounds"
        };

        public static void EnsureDefaults(Storage storage, IResourceStore<byte[]>? resourceStore, string userDirectory)
        {
            string targetRoot;
            try
            {
                targetRoot = storage.GetFullPath(userDirectory);
                Directory.CreateDirectory(targetRoot);
            }
            catch
            {
                return;
            }

            foreach (var resourcePath in resourcePaths)
            {
                string fileName = Path.GetFileName(resourcePath);
                if (string.IsNullOrEmpty(fileName))
                    continue;

                string targetPath = Path.Combine(targetRoot, fileName);
                if (File.Exists(targetPath))
                    continue;

                if (tryCopyFromResources(resourceStore, resourcePath, targetPath))
                    continue;

                if (tryCopyFromInstallation(fileName, targetPath))
                    continue;

                Logger.Log($"[MetronomeBootstrap] Failed to seed '{fileName}'.", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private static bool tryCopyFromResources(IResourceStore<byte[]>? resourceStore, string resourcePath, string targetPath)
        {
            if (resourceStore == null)
                return false;

            try
            {
                using var stream = resourceStore.GetStream(resourcePath);
                if (stream == null)
                    return false;

                using var output = File.Create(targetPath);
                stream.CopyTo(output);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private static bool tryCopyFromInstallation(string fileName, string targetPath)
        {
            foreach (var folder in installSearchFolders)
            {
                try
                {
                    string candidate = Path.Combine(AppContext.BaseDirectory, folder, fileName);
                    if (!File.Exists(candidate))
                        continue;

                    using var input = File.OpenRead(candidate);
                    using var output = File.Create(targetPath);
                    input.CopyTo(output);
                    return true;
                }
                catch
                {
                    // Try next option.
                }
            }

            return false;
        }
    }
}
