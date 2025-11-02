using System;
using System.IO;
using BeatSight.Game.Beatmaps;
using Xunit;

namespace BeatSight.Tests.Beatmaps;

public class BeatmapLoaderTests
{
    private static string GetSolutionRoot()
    {
        return Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", ".."));
    }

    private static string GetSampleBeatmapPath()
    {
        string root = GetSolutionRoot();
        string path = Path.Combine(root, "shared", "formats", "simple_beat.bsm");
        if (!File.Exists(path))
            throw new FileNotFoundException($"Sample beatmap not found at {path}. The test relies on the curated fixture shipped with the repository.");
        return path;
    }

    [Fact]
    public void LoadFromFile_ParsesExpectedMetadata()
    {
        string samplePath = GetSampleBeatmapPath();

        Beatmap beatmap = BeatmapLoader.LoadFromFile(samplePath);

        Assert.Equal("Simple Practice Beat", beatmap.Metadata.Title);
        Assert.Equal("BeatSight Example", beatmap.Metadata.Artist);
        Assert.Equal("BeatSight Team", beatmap.Metadata.Creator);
        Assert.Equal("simple_beat.mp3", beatmap.Audio.Filename);
        Assert.Equal(120.0, beatmap.Timing.Bpm, precision: 5);
    }

    [Fact]
    public void LoadFromFile_SortsHitObjectsByTime()
    {
        string samplePath = GetSampleBeatmapPath();

        Beatmap beatmap = BeatmapLoader.LoadFromFile(samplePath);

        Assert.NotEmpty(beatmap.HitObjects);

        int previous = int.MinValue;
        foreach (var hit in beatmap.HitObjects)
        {
            Assert.True(hit.Time >= previous, "Hit objects must be sorted ascending by time");
            previous = hit.Time;
        }
    }
}
