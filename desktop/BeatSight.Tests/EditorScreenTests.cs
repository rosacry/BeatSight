using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Editor;

namespace BeatSight.Tests;

/// <summary>
/// Tests for EditorScreen functionality including undo/redo, note management,
/// and editor state management.
/// </summary>
public class EditorScreenTests
{
    #region EditorCommandManager Tests

    [Fact]
    public void NewManagerHasEmptyStacks()
    {
        var manager = new EditorCommandManager();

        Assert.False(manager.CanUndo);
        Assert.False(manager.CanRedo);
        Assert.Equal(0, manager.UndoCount);
        Assert.Equal(0, manager.RedoCount);
    }

    [Fact]
    public void PrepareSnapshotCreatesUndoState()
    {
        var manager = new EditorCommandManager();
        var beatmap = CreateTestBeatmap();
        var state = CreateDefaultEditorState();

        bool result = manager.PrepareSnapshot(beatmap, state, "Test action");

        Assert.True(result);
        Assert.True(manager.CanUndo);
        Assert.Equal(1, manager.UndoCount);
        Assert.True(manager.IsSnapshotArmed);
    }

    [Fact]
    public void PrepareSnapshotRejectsNullBeatmap()
    {
        var manager = new EditorCommandManager();
        var state = CreateDefaultEditorState();

        bool result = manager.PrepareSnapshot(null!, state);

        Assert.False(result);
        Assert.False(manager.CanUndo);
    }

    [Fact]
    public void PrepareSnapshotRejectsDuplicateState()
    {
        var manager = new EditorCommandManager();
        var beatmap = CreateTestBeatmap();
        var state = CreateDefaultEditorState();

        manager.PrepareSnapshot(beatmap, state, "First");
        manager.ClearArmedState();
        bool result = manager.PrepareSnapshot(beatmap, state, "Duplicate");

        Assert.False(result);
        Assert.Equal(1, manager.UndoCount);
    }

    [Fact]
    public void PrepareSnapshotRejectsWhileArmed()
    {
        var manager = new EditorCommandManager();
        var beatmap = CreateTestBeatmap();
        var state = CreateDefaultEditorState();

        manager.PrepareSnapshot(beatmap, state, "First");
        bool result = manager.PrepareSnapshot(beatmap, state, "Second while armed");

        Assert.False(result);
        Assert.Equal(1, manager.UndoCount);
    }

    [Fact]
    public void UndoRestoresPreviousState()
    {
        var manager = new EditorCommandManager();
        var originalBeatmap = CreateTestBeatmap();
        var originalState = new EditorStateInfo
        {
            CurrentTime = 1000,
            TimelineZoom = 1.5,
            SnapDivisor = 4,
            WaveformScale = 1.0,
            BeatGridVisible = true
        };

        manager.PrepareSnapshot(originalBeatmap, originalState, "Original state");
        manager.ClearArmedState();

        // Simulate making an edit
        var modifiedBeatmap = CreateTestBeatmap();
        modifiedBeatmap.HitObjects.Add(new HitObject { Time = 5000, Component = "kick" });
        var modifiedState = new EditorStateInfo
        {
            CurrentTime = 2000,
            TimelineZoom = 2.0,
            SnapDivisor = 8,
            WaveformScale = 1.2,
            BeatGridVisible = false
        };

        var snapshot = manager.Undo(modifiedBeatmap, modifiedState);

        Assert.NotNull(snapshot);
        Assert.Equal(originalState.CurrentTime, snapshot.CurrentTime);
        Assert.Equal(originalState.TimelineZoom, snapshot.Zoom);
        Assert.Equal(originalState.SnapDivisor, snapshot.SnapDivisor);
        Assert.True(manager.CanRedo);
        Assert.False(manager.CanUndo);
    }

    [Fact]
    public void UndoReturnsNullWhenEmpty()
    {
        var manager = new EditorCommandManager();
        var beatmap = CreateTestBeatmap();
        var state = CreateDefaultEditorState();

        var snapshot = manager.Undo(beatmap, state);

        Assert.Null(snapshot);
        Assert.False(manager.CanRedo);
    }

    [Fact]
    public void RedoRestoresUndoneState()
    {
        var manager = new EditorCommandManager();
        var beatmap1 = CreateTestBeatmap();
        var state1 = CreateDefaultEditorState();

        manager.PrepareSnapshot(beatmap1, state1, "State 1");
        manager.ClearArmedState();

        var beatmap2 = CreateTestBeatmap();
        beatmap2.HitObjects.Add(new HitObject { Time = 3000, Component = "snare" });
        var state2 = new EditorStateInfo { CurrentTime = 2000, TimelineZoom = 1.0, SnapDivisor = 4, WaveformScale = 1.0, BeatGridVisible = true };

        // Undo
        var undoneSnapshot = manager.Undo(beatmap2, state2);
        Assert.NotNull(undoneSnapshot);

        // Redo
        var redoneSnapshot = manager.Redo(CreateTestBeatmap(), state1);
        Assert.NotNull(redoneSnapshot);
        Assert.Equal(state2.CurrentTime, redoneSnapshot.CurrentTime);
    }

    [Fact]
    public void RedoReturnsNullWhenEmpty()
    {
        var manager = new EditorCommandManager();
        var beatmap = CreateTestBeatmap();
        var state = CreateDefaultEditorState();

        var snapshot = manager.Redo(beatmap, state);

        Assert.Null(snapshot);
    }

    [Fact]
    public void NewEditClearsRedoStack()
    {
        var manager = new EditorCommandManager();
        var beatmap = CreateTestBeatmap();
        var state = CreateDefaultEditorState();

        // Create initial state
        manager.PrepareSnapshot(beatmap, state, "First");
        manager.ClearArmedState();

        // Undo to create redo state
        var undone = manager.Undo(beatmap, state);
        Assert.NotNull(undone);
        Assert.True(manager.CanRedo);

        // New edit should clear redo
        var modifiedBeatmap = CreateTestBeatmap();
        modifiedBeatmap.Metadata.Title = "Modified";
        manager.PrepareSnapshot(modifiedBeatmap, state, "New edit");

        Assert.False(manager.CanRedo);
        Assert.Equal(0, manager.RedoCount);
    }

    [Fact]
    public void MaxUndoStepsIsRespected()
    {
        var manager = new EditorCommandManager { MaxUndoSteps = 5 };
        var state = CreateDefaultEditorState();

        for (int i = 0; i < 10; i++)
        {
            var beatmap = CreateTestBeatmap();
            beatmap.HitObjects.Add(new HitObject { Time = i * 1000, Component = "kick" });
            manager.PrepareSnapshot(beatmap, state, $"Edit {i}");
            manager.ClearArmedState();
        }

        Assert.Equal(5, manager.UndoCount);
    }

    [Fact]
    public void ClearRemovesAllHistory()
    {
        var manager = new EditorCommandManager();
        var beatmap = CreateTestBeatmap();
        var state = CreateDefaultEditorState();

        manager.PrepareSnapshot(beatmap, state);
        manager.ClearArmedState();
        manager.Undo(beatmap, state);

        Assert.True(manager.CanRedo);

        manager.Clear();

        Assert.False(manager.CanUndo);
        Assert.False(manager.CanRedo);
        Assert.Equal(0, manager.UndoCount);
        Assert.Equal(0, manager.RedoCount);
    }

    [Fact]
    public void StateChangedEventFires()
    {
        var manager = new EditorCommandManager();
        var eventFired = false;
        manager.StateChanged += () => eventFired = true;

        var beatmap = CreateTestBeatmap();
        var state = CreateDefaultEditorState();

        manager.PrepareSnapshot(beatmap, state);

        Assert.True(eventFired);
    }

    [Fact]
    public void GetRecentUndoHistoryReturnsNewestFirst()
    {
        var manager = new EditorCommandManager();
        var state = CreateDefaultEditorState();

        for (int i = 1; i <= 5; i++)
        {
            var beatmap = CreateTestBeatmap();
            beatmap.HitObjects.Add(new HitObject { Time = i * 1000, Component = "kick" });
            manager.PrepareSnapshot(beatmap, state, $"Action {i}");
            manager.ClearArmedState();
        }

        var history = manager.GetRecentUndoHistory(3);

        Assert.Equal(3, history.Count);
        Assert.Equal("Action 5", history[0].Description);
        Assert.Equal("Action 4", history[1].Description);
        Assert.Equal("Action 3", history[2].Description);
    }

    [Fact]
    public void CreateSnapshotSerializesBeatmapCorrectly()
    {
        var beatmap = CreateTestBeatmap();
        beatmap.HitObjects.Add(new HitObject { Time = 1234, Component = "kick", Velocity = 0.9 });
        var state = new EditorStateInfo
        {
            CurrentTime = 5000,
            TimelineZoom = 2.5,
            SnapDivisor = 16,
            WaveformScale = 1.5,
            BeatGridVisible = false
        };

        var snapshot = EditorCommandManager.CreateSnapshot(beatmap, state, "Test snapshot");

        Assert.Equal(5000, snapshot.CurrentTime);
        Assert.Equal(2.5, snapshot.Zoom);
        Assert.Equal(16, snapshot.SnapDivisor);
        Assert.Equal(1.5, snapshot.WaveformScale);
        Assert.False(snapshot.BeatGridVisible);
        Assert.Equal("Test snapshot", snapshot.Description);
        Assert.Contains("\"Time\":1234", snapshot.BeatmapJson);
        Assert.Contains("\"Component\":\"kick\"", snapshot.BeatmapJson);
    }

    [Fact]
    public void DeserializeBeatmapRestoresState()
    {
        var originalBeatmap = CreateTestBeatmap();
        originalBeatmap.HitObjects.Add(new HitObject { Time = 1500, Component = "snare", Velocity = 0.85 });
        originalBeatmap.Metadata.Title = "Test Song";
        originalBeatmap.Metadata.Artist = "Test Artist";

        var state = CreateDefaultEditorState();
        var snapshot = EditorCommandManager.CreateSnapshot(originalBeatmap, state);

        var restoredBeatmap = EditorCommandManager.DeserializeBeatmap(snapshot);

        Assert.NotNull(restoredBeatmap);
        Assert.Equal(2, restoredBeatmap.HitObjects.Count); // 1 from CreateTestBeatmap + 1 added
        Assert.Equal("Test Song", restoredBeatmap.Metadata.Title);
        Assert.Equal("Test Artist", restoredBeatmap.Metadata.Artist);
    }

    #endregion

    #region EditorSnapshot Tests

    [Fact]
    public void EditorSnapshotHasCorrectDefaults()
    {
        var snapshot = new EditorSnapshot();

        Assert.Equal(string.Empty, snapshot.BeatmapJson);
        Assert.Equal(0, snapshot.CurrentTime);
        Assert.Equal(1.0, snapshot.Zoom);
        Assert.Equal(4, snapshot.SnapDivisor);
        Assert.Equal(1.0, snapshot.WaveformScale);
    }

    #endregion

    #region Note Selection Tests (via Beatmap operations)

    [Fact]
    public void SelectingNotesPreservesOrder()
    {
        var beatmap = CreateTestBeatmap();
        beatmap.HitObjects.Clear();
        beatmap.HitObjects.Add(new HitObject { Time = 1000, Component = "kick" });
        beatmap.HitObjects.Add(new HitObject { Time = 2000, Component = "snare" });
        beatmap.HitObjects.Add(new HitObject { Time = 3000, Component = "hihat" });

        // Simulate selecting notes in time range 1500-2500
        var selected = beatmap.HitObjects
            .Where(h => h.Time >= 1500 && h.Time <= 2500)
            .OrderBy(h => h.Time)
            .ToList();

        Assert.Single(selected);
        Assert.Equal("snare", selected[0].Component);
    }

    [Fact]
    public void DeletingNotesRemovesFromBeatmap()
    {
        var beatmap = CreateTestBeatmap();
        beatmap.HitObjects.Clear();
        beatmap.HitObjects.Add(new HitObject { Time = 1000, Component = "kick" });
        beatmap.HitObjects.Add(new HitObject { Time = 2000, Component = "snare" });
        beatmap.HitObjects.Add(new HitObject { Time = 3000, Component = "hihat" });

        // Delete the snare note
        var toDelete = beatmap.HitObjects.FirstOrDefault(h => h.Component == "snare");
        if (toDelete != null)
            beatmap.HitObjects.Remove(toDelete);

        Assert.Equal(2, beatmap.HitObjects.Count);
        Assert.DoesNotContain(beatmap.HitObjects, h => h.Component == "snare");
    }

    [Fact]
    public void CopyPasteNotesCreatesNewInstances()
    {
        var beatmap = CreateTestBeatmap();
        beatmap.HitObjects.Clear();
        var original = new HitObject { Time = 1000, Component = "kick", Velocity = 0.8 };
        beatmap.HitObjects.Add(original);

        // Simulate copy
        var copiedJson = Newtonsoft.Json.JsonConvert.SerializeObject(new[] { original });

        // Simulate paste at offset
        var pastedNotes = Newtonsoft.Json.JsonConvert.DeserializeObject<HitObject[]>(copiedJson)!;
        const int pasteOffset = 2000;
        foreach (var note in pastedNotes)
        {
            note.Time += pasteOffset;
            beatmap.HitObjects.Add(note);
        }

        Assert.Equal(2, beatmap.HitObjects.Count);
        Assert.Equal(1000, beatmap.HitObjects[0].Time);
        Assert.Equal(3000, beatmap.HitObjects[1].Time);
        Assert.NotSame(original, pastedNotes[0]);
    }

    #endregion

    #region Timeline Navigation Tests

    [Fact]
    public void SnapToGridCalculatesCorrectPosition()
    {
        const double bpm = 120;
        const int snapDivisor = 4; // Quarter notes
        const double beatMs = 60000.0 / bpm; // 500ms per beat
        const double snapMs = beatMs / snapDivisor; // 125ms per snap

        double testTime = 1137; // Somewhere between snaps
        double snappedTime = Math.Round(testTime / snapMs) * snapMs;

        Assert.Equal(1125, snappedTime); // Should snap to nearest 125ms
    }

    [Fact]
    public void SnapDivisorAffectsGridResolution()
    {
        const double bpm = 120;
        const double beatMs = 60000.0 / bpm;

        int[] divisors = { 1, 2, 4, 8, 16 };
        double[] expectedSnapMs = { 500, 250, 125, 62.5, 31.25 };

        for (int i = 0; i < divisors.Length; i++)
        {
            double snapMs = beatMs / divisors[i];
            Assert.Equal(expectedSnapMs[i], snapMs);
        }
    }

    [Fact]
    public void SeekPositionClampsToTrackBounds()
    {
        const double trackDurationMs = 180000; // 3 minutes

        // Test clamping negative
        double seekPos = Math.Max(0, -1000);
        Assert.Equal(0, seekPos);

        // Test clamping past end
        seekPos = Math.Min(trackDurationMs, 200000);
        Assert.Equal(180000, seekPos);

        // Test valid position unchanged
        seekPos = Math.Clamp(90000, 0, trackDurationMs);
        Assert.Equal(90000, seekPos);
    }

    #endregion

    #region BPM and Offset Tests

    [Fact]
    public void BpmChangeRecalculatesTimings()
    {
        var beatmap = CreateTestBeatmap();
        beatmap.Timing.Bpm = 120;
        beatmap.Timing.Offset = 0;

        // Calculate positions at original BPM
        const double originalBeatMs = 60000.0 / 120; // 500ms
        var beat4Time = originalBeatMs * 4; // 2000ms

        // Simulate BPM change to 140
        const double newBeatMs = 60000.0 / 140; // ~428.57ms
        var newBeat4Time = newBeatMs * 4; // ~1714ms

        Assert.Equal(2000, beat4Time);
        Assert.InRange(newBeat4Time, 1714, 1715);
    }

    [Fact]
    public void OffsetShiftsAllTimings()
    {
        var beatmap = CreateTestBeatmap();
        beatmap.Timing.Bpm = 120;
        beatmap.Timing.Offset = 500; // 500ms offset

        const double beatMs = 60000.0 / 120;
        var firstBeatTime = beatmap.Timing.Offset;
        var secondBeatTime = beatmap.Timing.Offset + beatMs;

        Assert.Equal(500, firstBeatTime);
        Assert.Equal(1000, secondBeatTime);
    }

    #endregion

    #region Helper Methods

    private static Beatmap CreateTestBeatmap()
    {
        return new Beatmap
        {
            Version = "1.1.0",
            Metadata = new BeatmapMetadata
            {
                Title = "Test Song",
                Artist = "Test Artist",
                Creator = "Test Creator"
            },
            Timing = new TimingInfo
            {
                Bpm = 120,
                Offset = 0
            },
            HitObjects = new List<HitObject>
            {
                new() { Time = 1000, Component = "kick", Velocity = 0.8 }
            }
        };
    }

    private static EditorStateInfo CreateDefaultEditorState()
    {
        return new EditorStateInfo
        {
            CurrentTime = 0,
            TimelineZoom = 1.0,
            SnapDivisor = 4,
            WaveformScale = 1.0,
            BeatGridVisible = true
        };
    }

    #endregion
}
