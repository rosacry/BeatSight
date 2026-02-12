using System;
using System.IO;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using Xunit;

namespace BeatSight.Tests.Beatmaps;

public class BeatmapLibraryTests
{
    [Fact]
    public void GetAvailableBeatmaps_ContainsSampleBeatmap()
    {
        var beatmaps = BeatmapLibrary.GetAvailableBeatmaps();

        var sample = beatmaps.FirstOrDefault(entry => entry.Beatmap.Metadata.BeatmapId == "handcrafted-groove-001");
        Assert.NotNull(sample);
        Assert.Equal("Handcrafted Groove Demo", sample!.Beatmap.Metadata.Title);
    }

    [Fact]
    public void TryGetDefaultBeatmapPath_ReturnsExistingFile()
    {
        bool success = BeatmapLibrary.TryGetDefaultBeatmapPath(out string path);

        Assert.True(success, "Default beatmap path should resolve when a curated sample exists.");
        Assert.False(string.IsNullOrWhiteSpace(path));
        Assert.EndsWith("simple_beat.bsm", path);
    }

    [Fact]
    public void GetAvailableBeatmaps_IncludesLegacyBsFiles()
    {
        string songsDirectory = UserAssetDirectories.GetPath(UserAssetDirectories.Songs);
        string uniqueDirectory = Path.Combine(songsDirectory, $"legacy-bs-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(uniqueDirectory);

        string beatmapPath = Path.Combine(uniqueDirectory, "legacy-entry.bs");
        string beatmapId = $"legacy-{Guid.NewGuid():N}";

        try
        {
            var beatmap = new Beatmap
            {
                Metadata =
                {
                    BeatmapId = beatmapId,
                    Title = "Legacy Format Test",
                    Artist = "BeatSight Tests",
                    Creator = "BeatSight",
                },
                Audio =
                {
                    Filename = "legacy.wav",
                    Duration = 1200
                },
                HitObjects =
                {
                    new HitObject { Time = 100, Component = "kick", Lane = 3 }
                }
            };

            BeatmapLoader.SaveToFile(beatmap, beatmapPath);

            var beatmaps = BeatmapLibrary.GetAvailableBeatmaps();
            Assert.Contains(beatmaps, entry => entry.Beatmap.Metadata.BeatmapId == beatmapId);
        }
        finally
        {
            if (Directory.Exists(uniqueDirectory))
                Directory.Delete(uniqueDirectory, recursive: true);
        }
    }
}
