using System;
using System.IO;
using System.Linq;
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

    #region LoadFromFile Tests

    [Fact]
    public void LoadFromFile_ParsesExpectedMetadata()
    {
        string samplePath = GetSampleBeatmapPath();

        Beatmap beatmap = BeatmapLoader.LoadFromFile(samplePath);

        Assert.Equal("Handcrafted Groove Demo", beatmap.Metadata.Title);
        Assert.Equal("BeatSight Example", beatmap.Metadata.Artist);
        Assert.Equal("BeatSight Team", beatmap.Metadata.Creator);
        Assert.Equal("simple_beat.wav", beatmap.Audio.Filename);
        Assert.Equal("simple_beat.wav", beatmap.Audio.DrumStem);
        Assert.Equal(8000, beatmap.Audio.Duration);
        Assert.Equal("sha256:411ba3ededb98b59ece90eac679ac52af71fd54d626acd0ffc5789c13d97e1ac", beatmap.Audio.Hash);
        Assert.Equal("sha256:411ba3ededb98b59ece90eac679ac52af71fd54d626acd0ffc5789c13d97e1ac", beatmap.Audio.DrumStemHash);
        Assert.Equal(120.0, beatmap.Timing.Bpm, precision: 5);
        Assert.Contains("handcrafted", beatmap.Metadata.Tags, StringComparer.OrdinalIgnoreCase);
        Assert.NotNull(beatmap.Editor?.AiGenerationMetadata);
        Assert.Equal("2025.11-handcrafted", beatmap.Editor!.AiGenerationMetadata!.ModelVersion);
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

    [Fact]
    public void LoadFromFile_ThrowsFileNotFoundForMissingFile()
    {
        string nonexistentPath = Path.Combine(Path.GetTempPath(), $"beatsight-test-{Guid.NewGuid()}.bsm");

        var ex = Assert.Throws<FileNotFoundException>(() => BeatmapLoader.LoadFromFile(nonexistentPath));
        Assert.Contains("not found", ex.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void LoadFromFile_ThrowsForMalformedJson()
    {
        string tempPath = Path.Combine(Path.GetTempPath(), $"beatsight-test-{Guid.NewGuid()}.bsm");

        try
        {
            File.WriteAllText(tempPath, "{ this is not valid json }");

            Assert.ThrowsAny<Exception>(() => BeatmapLoader.LoadFromFile(tempPath));
        }
        finally
        {
            if (File.Exists(tempPath))
                File.Delete(tempPath);
        }
    }

    [Fact]
    public void LoadFromFile_ThrowsForMissingTitle()
    {
        string tempPath = Path.Combine(Path.GetTempPath(), $"beatsight-test-{Guid.NewGuid()}.bsm");

        try
        {
            // Create a beatmap JSON missing the title
            string json = @"{
                ""metadata"": { ""artist"": ""Test Artist"" },
                ""audio"": { ""filename"": ""test.mp3"" },
                ""hitObjects"": [{ ""time"": 100, ""lane"": 0, ""component"": ""kick"" }]
            }";
            File.WriteAllText(tempPath, json);

            var ex = Assert.Throws<InvalidDataException>(() => BeatmapLoader.LoadFromFile(tempPath));
            Assert.Contains("title", ex.Message, StringComparison.OrdinalIgnoreCase);
        }
        finally
        {
            if (File.Exists(tempPath))
                File.Delete(tempPath);
        }
    }

    [Fact]
    public void LoadFromFile_ThrowsForMissingArtist()
    {
        string tempPath = Path.Combine(Path.GetTempPath(), $"beatsight-test-{Guid.NewGuid()}.bsm");

        try
        {
            // Create a beatmap JSON missing the artist
            string json = @"{
                ""metadata"": { ""title"": ""Test Title"" },
                ""audio"": { ""filename"": ""test.mp3"" },
                ""hitObjects"": [{ ""time"": 100, ""lane"": 0, ""component"": ""kick"" }]
            }";
            File.WriteAllText(tempPath, json);

            var ex = Assert.Throws<InvalidDataException>(() => BeatmapLoader.LoadFromFile(tempPath));
            Assert.Contains("artist", ex.Message, StringComparison.OrdinalIgnoreCase);
        }
        finally
        {
            if (File.Exists(tempPath))
                File.Delete(tempPath);
        }
    }

    [Fact]
    public void LoadFromFile_ThrowsForMissingAudioFilename()
    {
        string tempPath = Path.Combine(Path.GetTempPath(), $"beatsight-test-{Guid.NewGuid()}.bsm");

        try
        {
            // Create a beatmap JSON missing the audio filename
            string json = @"{
                ""metadata"": { ""title"": ""Test Title"", ""artist"": ""Test Artist"" },
                ""audio"": { },
                ""hitObjects"": [{ ""time"": 100, ""lane"": 0, ""component"": ""kick"" }]
            }";
            File.WriteAllText(tempPath, json);

            var ex = Assert.Throws<InvalidDataException>(() => BeatmapLoader.LoadFromFile(tempPath));
            Assert.Contains("audio file", ex.Message, StringComparison.OrdinalIgnoreCase);
        }
        finally
        {
            if (File.Exists(tempPath))
                File.Delete(tempPath);
        }
    }

    [Fact]
    public void LoadFromFile_ThrowsForEmptyHitObjects()
    {
        string tempPath = Path.Combine(Path.GetTempPath(), $"beatsight-test-{Guid.NewGuid()}.bsm");

        try
        {
            // Create a beatmap JSON with empty hit objects
            string json = @"{
                ""metadata"": { ""title"": ""Test Title"", ""artist"": ""Test Artist"" },
                ""audio"": { ""filename"": ""test.mp3"" },
                ""hitObjects"": []
            }";
            File.WriteAllText(tempPath, json);

            var ex = Assert.Throws<InvalidDataException>(() => BeatmapLoader.LoadFromFile(tempPath));
            Assert.Contains("hit object", ex.Message, StringComparison.OrdinalIgnoreCase);
        }
        finally
        {
            if (File.Exists(tempPath))
                File.Delete(tempPath);
        }
    }

    #endregion

    #region SaveToFile Tests

    [Fact]
    public void SaveToFile_ThrowsWhenNoHitObjects()
    {
        var beatmap = new Beatmap
        {
            Metadata =
            {
                Title = "Unit Test Track",
                Artist = "Test Artist",
                Creator = "Test"
            },
            Audio =
            {
                Filename = "unit-test.mp3",
                Duration = 1000
            }
        };

        string tempPath = Path.Combine(Path.GetTempPath(), $"beatsight-test-{Guid.NewGuid()}.bsm");

        try
        {
            var ex = Assert.Throws<InvalidDataException>(() => BeatmapLoader.SaveToFile(beatmap, tempPath));
            Assert.Contains("at least one hit object", ex.Message, StringComparison.OrdinalIgnoreCase);
            Assert.False(File.Exists(tempPath));
        }
        finally
        {
            if (File.Exists(tempPath))
                File.Delete(tempPath);
        }
    }

    #endregion

    #region Lane Heuristics Tests

    [Fact]
    public void SampleBeatmap_AlignsWithLaneHeuristics()
    {
        string samplePath = GetSampleBeatmapPath();

        Beatmap beatmap = BeatmapLoader.LoadFromFile(samplePath);

        AssertComponentLane(beatmap, "kick", expectedLane: 3);
        AssertComponentLane(beatmap, "snare", expectedLane: 2);
        AssertComponentLane(beatmap, "hihat_closed", expectedLane: 1);
        AssertComponentLane(beatmap, "ride", expectedLane: 5);
        AssertComponentLane(beatmap, "crash", expectedLane: 0);
        AssertComponentLane(beatmap, "tom_mid", expectedLane: 4);
        AssertComponentLane(beatmap, "tom_low", expectedLane: 4);
    }

    #endregion

    #region Helper Methods

    private static void AssertComponentLane(Beatmap beatmap, string component, int expectedLane)
    {
        var hits = beatmap.HitObjects.Where(h => string.Equals(h.Component, component, StringComparison.OrdinalIgnoreCase)).ToList();
        Assert.NotEmpty(hits);
        Assert.All(hits, h => Assert.Equal(expectedLane, h.Lane));
    }

    #endregion
}
