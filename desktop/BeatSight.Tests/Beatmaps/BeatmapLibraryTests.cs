using System.Linq;
using BeatSight.Game.Beatmaps;
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
}
