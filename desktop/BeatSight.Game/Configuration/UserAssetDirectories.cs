using System;
using System.IO;

namespace BeatSight.Game.Configuration
{
    internal static class UserAssetDirectories
    {
        public const string MetronomeSounds = "MetronomeSounds";
        public const string Skins = "Skins";
        public const string Songs = "Songs";

        public static string RootPath
        {
            get
            {
                string? overrideRoot = Environment.GetEnvironmentVariable("BEATSIGHT_USER_ASSET_ROOT");
                if (!string.IsNullOrWhiteSpace(overrideRoot))
                    return Path.GetFullPath(overrideRoot);

                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "BeatSight");
            }
        }

        public static string GetPath(string relativePath) => Path.Combine(RootPath, relativePath);
    }
}
