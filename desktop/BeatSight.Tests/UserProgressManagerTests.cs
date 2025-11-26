using System;
using System.IO;
using System.Threading;
using BeatSight.Game.Progress;
using osu.Framework.Platform;
using Xunit;

namespace BeatSight.Tests;

public class UserProgressManagerTests : IDisposable
{
    private readonly string testDirectory;
    private readonly NativeStorage storage;

    public UserProgressManagerTests()
    {
        testDirectory = Path.Combine(Path.GetTempPath(), $"beatsight_test_{Guid.NewGuid():N}");
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
    public void NewProgressManager_HasNoProgress()
    {
        using var manager = new UserProgressManager(storage);
        var progress = manager.GetProgress("nonexistent");

        Assert.Null(progress);
    }

    [Fact]
    public void RecordPlayStart_IncrementsPlayCount()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_1";

        manager.RecordPlayStart(beatmapId);
        var progress = manager.GetProgress(beatmapId);

        Assert.NotNull(progress);
        Assert.Equal(1, progress!.PlayCount);
        Assert.Equal(beatmapId, progress.BeatmapId);
    }

    [Fact]
    public void RecordPlayStart_MultipleTimes_IncrementsCorrectly()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_2";

        manager.RecordPlayStart(beatmapId);
        manager.RecordPlayStart(beatmapId);
        manager.RecordPlayStart(beatmapId);

        var progress = manager.GetProgress(beatmapId);

        Assert.Equal(3, progress!.PlayCount);
    }

    [Fact]
    public void RecordCompletion_SetsFlagsCorrectly()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_3";

        manager.RecordPlayStart(beatmapId);
        manager.RecordCompletion(beatmapId, speedMultiplier: 1.0);

        var progress = manager.GetProgress(beatmapId);

        Assert.True(progress!.Completed);
        Assert.Equal(1.0, progress.FurthestProgress);
        Assert.Equal(1.0, progress.SlowestCompletionSpeed);
        Assert.Equal(1.0, progress.FastestCompletionSpeed);
    }

    [Fact]
    public void RecordCompletion_TracksSpeedExtremes()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_4";

        manager.RecordPlayStart(beatmapId);
        manager.RecordCompletion(beatmapId, speedMultiplier: 1.0);
        manager.RecordCompletion(beatmapId, speedMultiplier: 0.5);
        manager.RecordCompletion(beatmapId, speedMultiplier: 1.5);

        var progress = manager.GetProgress(beatmapId);

        Assert.Equal(0.5, progress!.SlowestCompletionSpeed);
        Assert.Equal(1.5, progress.FastestCompletionSpeed);
    }

    [Fact]
    public void RecordPlayProgress_UpdatesFurthestProgress()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_5";

        manager.RecordPlayStart(beatmapId);
        manager.RecordPlayProgress(beatmapId, progressFraction: 0.3, elapsedMs: 1000);
        manager.RecordPlayProgress(beatmapId, progressFraction: 0.6, elapsedMs: 1000);

        var progress = manager.GetProgress(beatmapId);

        Assert.Equal(0.6, progress!.FurthestProgress);
        Assert.Equal(2000, progress.TotalPlayTimeMs);
    }

    [Fact]
    public void RecordPlayProgress_DoesNotDecreaseProgress()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_6";

        manager.RecordPlayStart(beatmapId);
        manager.RecordPlayProgress(beatmapId, progressFraction: 0.8, elapsedMs: 1000);
        manager.RecordPlayProgress(beatmapId, progressFraction: 0.3, elapsedMs: 1000);

        var progress = manager.GetProgress(beatmapId);

        Assert.Equal(0.8, progress!.FurthestProgress);
    }

    [Fact]
    public void ToggleFavorite_TogglesCorrectly()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_7";

        bool first = manager.ToggleFavorite(beatmapId);
        bool second = manager.ToggleFavorite(beatmapId);
        bool third = manager.ToggleFavorite(beatmapId);

        Assert.True(first);
        Assert.False(second);
        Assert.True(third);
    }

    [Fact]
    public void SetPersonalRating_SetsRating()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_8";

        manager.SetPersonalRating(beatmapId, 4);

        var progress = manager.GetProgress(beatmapId);

        Assert.Equal(4, progress!.PersonalRating);
    }

    [Fact]
    public void SetPersonalRating_RejectsInvalidValues()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_9";

        // First create the progress with a valid rating
        manager.SetPersonalRating(beatmapId, 3);

        // Then try to set invalid values - they should not change the existing rating
        manager.SetPersonalRating(beatmapId, 0);
        manager.SetPersonalRating(beatmapId, 6);

        var progress = manager.GetProgress(beatmapId);

        Assert.Equal(3, progress!.PersonalRating); // Should still be 3
    }

    [Fact]
    public void MarkDifficultSection_AddsSection()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_10";

        manager.MarkDifficultSection(beatmapId, startMs: 10000, endMs: 15000, description: "Tricky fill");

        var progress = manager.GetProgress(beatmapId);

        Assert.Single(progress!.DifficultSections);
        Assert.Equal(10000, progress.DifficultSections[0].StartMs);
        Assert.Equal(15000, progress.DifficultSections[0].EndMs);
        Assert.Equal("Tricky fill", progress.DifficultSections[0].Description);
        Assert.False(progress.DifficultSections[0].Mastered);
    }

    [Fact]
    public void MarkSectionMastered_UpdatesSection()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_11";

        manager.MarkDifficultSection(beatmapId, startMs: 20000, endMs: 25000);
        manager.MarkSectionMastered(beatmapId, startMs: 20000, endMs: 25000);

        var progress = manager.GetProgress(beatmapId);

        Assert.True(progress!.DifficultSections[0].Mastered);
    }

    [Fact]
    public void ToggleTag_AddsAndRemovesTags()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_12";

        manager.ToggleTag(beatmapId, "practice");
        var progress1 = manager.GetProgress(beatmapId);
        Assert.Contains("practice", progress1!.Tags);

        manager.ToggleTag(beatmapId, "practice");
        var progress2 = manager.GetProgress(beatmapId);
        Assert.DoesNotContain("practice", progress2!.Tags);
    }

    [Fact]
    public void SetNotes_SetsAndClearsNotes()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_beatmap_13";

        manager.SetNotes(beatmapId, "Focus on the hi-hat pattern");
        var progress1 = manager.GetProgress(beatmapId);
        Assert.Equal("Focus on the hi-hat pattern", progress1!.Notes);

        manager.SetNotes(beatmapId, "  ");
        var progress2 = manager.GetProgress(beatmapId);
        Assert.Null(progress2!.Notes);
    }

    [Fact]
    public void GetFavorites_ReturnsOnlyFavorites()
    {
        using var manager = new UserProgressManager(storage);

        manager.ToggleFavorite("fav_1");
        manager.ToggleFavorite("fav_2");
        manager.RecordPlayStart("not_fav");

        var favorites = manager.GetFavorites();

        Assert.Equal(2, favorites.Count);
        Assert.All(favorites, f => Assert.True(f.IsFavorite));
    }

    [Fact]
    public void GetRecentlyPlayed_ReturnsInOrder()
    {
        using var manager = new UserProgressManager(storage);

        manager.RecordPlayStart("recent_1");
        Thread.Sleep(10);
        manager.RecordPlayStart("recent_2");
        Thread.Sleep(10);
        manager.RecordPlayStart("recent_3");

        var recent = manager.GetRecentlyPlayed(3);

        Assert.Equal(3, recent.Count);
        Assert.Equal("recent_3", recent[0].BeatmapId);
        Assert.Equal("recent_2", recent[1].BeatmapId);
        Assert.Equal("recent_1", recent[2].BeatmapId);
    }

    [Fact]
    public void GenerateBeatmapId_IsDeterministic()
    {
        string id1 = UserProgressManager.GenerateBeatmapId("/path/to/song.bsm", "Test Song", "Test Artist");
        string id2 = UserProgressManager.GenerateBeatmapId("/path/to/song.bsm", "Test Song", "Test Artist");

        Assert.Equal(id1, id2);
    }

    [Fact]
    public void GenerateBeatmapId_DifferentInputsProduceDifferentIds()
    {
        string id1 = UserProgressManager.GenerateBeatmapId("/path/to/song1.bsm");
        string id2 = UserProgressManager.GenerateBeatmapId("/path/to/song2.bsm");

        Assert.NotEqual(id1, id2);
    }

    [Fact]
    public void RecordPracticeSession_AddsSessions()
    {
        using var manager = new UserProgressManager(storage);
        string beatmapId = "test_practice";

        manager.RecordPracticeSession(beatmapId, durationMs: 60000, loopStartMs: 5000, loopEndMs: 10000, speedMultiplier: 0.75);

        var progress = manager.GetProgress(beatmapId);

        Assert.Single(progress!.PracticeSessions);
        Assert.Equal(60000, progress.PracticeSessions[0].DurationMs);
        Assert.Equal(5000, progress.PracticeSessions[0].LoopStartMs);
        Assert.Equal(10000, progress.PracticeSessions[0].LoopEndMs);
        Assert.Equal(0.75, progress.PracticeSessions[0].SpeedMultiplier);
    }

    [Fact]
    public void DataPersists_AcrossInstances()
    {
        string beatmapId = "persist_test";

        // First instance
        using (var manager = new UserProgressManager(storage))
        {
            manager.RecordPlayStart(beatmapId);
            manager.RecordCompletion(beatmapId, speedMultiplier: 1.0);
            manager.ToggleFavorite(beatmapId);
        }

        // Second instance should see the same data
        using (var manager = new UserProgressManager(storage))
        {
            var progress = manager.GetProgress(beatmapId);

            Assert.NotNull(progress);
            Assert.Equal(1, progress!.PlayCount);
            Assert.True(progress.Completed);
            Assert.True(progress.IsFavorite);
        }
    }
}
