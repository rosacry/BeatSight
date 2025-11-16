using System.IO;
using BeatSight.Game.Configuration;
using osu.Framework.IO.Stores;
using osu.Framework.Platform;

namespace BeatSight.Game.Customization
{
    internal static class NoteSkinBootstrap
    {
        private static readonly (NoteSkinOption Option, string FolderName, string[] Resources)[] defaultSkins =
        {
            (NoteSkinOption.Classic, "Classic", new[]
            {
                "Skins/Classic/manifest.json",
                "Skins/Classic/README.txt"
            }),
            (NoteSkinOption.Neon, "Neon", new[]
            {
                "Skins/Neon/manifest.json",
                "Skins/Neon/README.txt"
            }),
            (NoteSkinOption.Carbon, "Carbon", new[]
            {
                "Skins/Carbon/manifest.json",
                "Skins/Carbon/README.txt"
            })
        };

        public static void EnsureDefaults(Storage storage, IResourceStore<byte[]>? resourceStore, string userDirectory)
        {
            if (resourceStore == null)
                return;

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

            foreach (var (_, folder, resources) in defaultSkins)
            {
                string skinFolder;
                try
                {
                    skinFolder = Path.Combine(targetRoot, folder);
                    Directory.CreateDirectory(skinFolder);
                }
                catch
                {
                    continue;
                }

                foreach (var resourcePath in resources)
                {
                    string fileName = Path.GetFileName(resourcePath);
                    if (string.IsNullOrEmpty(fileName))
                        continue;

                    string targetPath = Path.Combine(skinFolder, fileName);
                    if (File.Exists(targetPath))
                        continue;

                    try
                    {
                        using var stream = resourceStore.GetStream(resourcePath);
                        if (stream == null)
                            continue;

                        using var output = File.Create(targetPath);
                        stream.CopyTo(output);
                    }
                    catch
                    {
                        // Individual file failures are tolerated to avoid blocking other defaults.
                    }
                }
            }
        }
    }
}
