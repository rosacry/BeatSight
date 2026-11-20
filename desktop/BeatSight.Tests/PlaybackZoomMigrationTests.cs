using System;
using System.IO;
using BeatSight.Game.Configuration;
using osu.Framework.Platform;
using Xunit;

namespace BeatSight.Tests;

/// <summary>
/// 2026-10-24: playback zoom became a direct multiplier. Saved settings from the old curve are converted once so
/// the look-ahead a user chose does not change; fresh installs and resets start on the new scale.
/// </summary>
public class PlaybackZoomMigrationTests : IDisposable
{
    private readonly string testDirectory;
    private readonly NativeStorage storage;

    public PlaybackZoomMigrationTests()
    {
        testDirectory = Path.Combine(Path.GetTempPath(), $"beatsight_zoom_test_{Guid.NewGuid():N}");
        Directory.CreateDirectory(testDirectory);
        storage = new NativeStorage(testDirectory);
    }

    public void Dispose()
    {
        try
        {
            Directory.Delete(testDirectory, recursive: true);
        }
        catch
        {
            // Best effort cleanup
        }
    }

    [Fact]
    public void ExistingConfigKeepsItsLookAhead()
    {
        File.WriteAllLines(Path.Combine(testDirectory, "beatsight.ini"), new[] { "PlaybackZoomLevel = 0.45" });

        using var config = new BeatSightConfigManager(storage);

        Assert.Equal(2.25, config.Get<double>(BeatSightSetting.PlaybackZoomLevel), 2);
        Assert.Equal(1, config.Get<int>(BeatSightSetting.PlaybackZoomScaleVersion));
    }

    [Fact]
    public void MigrationRunsOnlyOnce()
    {
        File.WriteAllLines(Path.Combine(testDirectory, "beatsight.ini"), new[] { "PlaybackZoomLevel = 2.25", "PlaybackZoomScaleVersion = 1" });

        using var config = new BeatSightConfigManager(storage);

        Assert.Equal(2.25, config.Get<double>(BeatSightSetting.PlaybackZoomLevel), 2);
    }

    [Fact]
    public void FreshInstallStartsAtMapPacing()
    {
        using var config = new BeatSightConfigManager(storage);

        Assert.Equal(1.0, config.Get<double>(BeatSightSetting.PlaybackZoomLevel), 3);
        Assert.Equal(1, config.Get<int>(BeatSightSetting.PlaybackZoomScaleVersion));
    }

    [Fact]
    public void ResetDoesNotRetriggerMigration()
    {
        File.WriteAllLines(Path.Combine(testDirectory, "beatsight.ini"), new[] { "PlaybackZoomLevel = 0.45" });

        using (var config = new BeatSightConfigManager(storage))
        {
            config.ResetToDefaults();
            Assert.Equal(1.0, config.Get<double>(BeatSightSetting.PlaybackZoomLevel), 3);
            Assert.Equal(1, config.Get<int>(BeatSightSetting.PlaybackZoomScaleVersion));
            config.Save();
        }

        using var reopened = new BeatSightConfigManager(storage);
        Assert.Equal(1.0, reopened.Get<double>(BeatSightSetting.PlaybackZoomLevel), 3);
    }
}
