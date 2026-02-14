using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Editor;
using osu.Framework.Bindables;
using osuTK.Input;
using Xunit;

namespace BeatSight.Tests
{
    public class EditorScreenUtilityTests
    {
        [Fact]
        public void CreateSlugNormalisesNamesForFilesystemUse()
        {
            Assert.Equal(string.Empty, invokePrivateStatic<string>("createSlug", new object?[] { null }));
            Assert.Equal(string.Empty, invokePrivateStatic<string>("createSlug", "___"));
            Assert.Equal("richaadeb-heir-of-grief", invokePrivateStatic<string>("createSlug", "RichaadEB - Heir of Grief"));
            Assert.Equal("song-v2-remaster", invokePrivateStatic<string>("createSlug", "Song (v2) [Remaster]"));
        }

        [Fact]
        public void FormatComponentDisplayNameProducesReadableLabels()
        {
            Assert.Equal("Unknown", invokePrivateStatic<string>("formatComponentDisplayName", ""));
            Assert.Equal("Unknown", invokePrivateStatic<string>("formatComponentDisplayName", "   "));
            Assert.Equal("Hihat Closed", invokePrivateStatic<string>("formatComponentDisplayName", "hihat_closed"));
            Assert.Equal("Ride Bell", invokePrivateStatic<string>("formatComponentDisplayName", "RIDE_BELL"));
        }

        [Fact]
        public void TimeFormattersProduceExpectedOutput()
        {
            Assert.Equal("03:03.045", invokePrivateStatic<string>("formatSongLength", 183045d));
            Assert.Equal("1:01:18.456", invokePrivateStatic<string>("formatSongLength", 3678456d));

            Assert.Equal("00:18.345", invokePrivateStatic<string>("formatTime", 18345d));
            Assert.Equal("01:01:01.000", invokePrivateStatic<string>("formatTime", 3661000d));
        }

        [Fact]
        public void CoerceSnapDivisorPicksNearestSupportedValue()
        {
            var screen = new EditorScreen();

            Assert.Equal(1, invokePrivateInstance<int>(screen, "coerceSnapDivisor", -5));
            Assert.Equal(4, invokePrivateInstance<int>(screen, "coerceSnapDivisor", 5));
            Assert.Equal(16, invokePrivateInstance<int>(screen, "coerceSnapDivisor", 17));
            Assert.Equal(32, invokePrivateInstance<int>(screen, "coerceSnapDivisor", 31));
        }

        [Fact]
        public void PlaybackStatusFiltersClassifySegmentsCorrectly()
        {
            Assert.True(invokePrivateStatic<bool>("isTransientPlaybackStatus", "Playing"));
            Assert.True(invokePrivateStatic<bool>("isTransientPlaybackStatus", "Playback finished"));
            Assert.False(invokePrivateStatic<bool>("isTransientPlaybackStatus", "No changes to save."));

            Assert.True(invokePrivateStatic<bool>("isInspectorLayoutStatus", "Inspector hidden (compact layout)"));
            Assert.True(invokePrivateStatic<bool>("isInspectorLayoutStatus", "Inspector shown (compact layout)"));
            Assert.False(invokePrivateStatic<bool>("isInspectorLayoutStatus", "Ready to map"));
        }

        [Fact]
        public void PruneStatusDetailSegmentsRemovesMatchingEntries()
        {
            var screen = new EditorScreen();

            setPrivateField(screen, "statusDetailText", "Playing, No changes to save., Playing (no audio), Inspector hidden (compact layout)");
            invokePrivateInstance<object?>(
                screen,
                "pruneStatusDetailSegments",
                new Func<string, bool>(s => s.StartsWith("Playing", StringComparison.OrdinalIgnoreCase)));

            var detail = getPrivateField<string?>(screen, "statusDetailText");
            Assert.Equal("No changes to save., Inspector hidden (compact layout)", detail);

            invokePrivateInstance<object?>(
                screen,
                "pruneStatusDetailSegments",
                new Func<string, bool>(_ => true));

            Assert.Null(getPrivateField<string?>(screen, "statusDetailText"));
        }

        [Fact]
        public void ZoomKeyHelpersRecogniseExpectedKeys()
        {
            Assert.True(invokePrivateStatic<bool>("isZoomIncreaseKey", Key.Plus));
            Assert.True(invokePrivateStatic<bool>("isZoomIncreaseKey", Key.KeypadPlus));
            Assert.False(invokePrivateStatic<bool>("isZoomIncreaseKey", Key.Minus));

            Assert.True(invokePrivateStatic<bool>("isZoomDecreaseKey", Key.Minus));
            Assert.True(invokePrivateStatic<bool>("isZoomDecreaseKey", Key.KeypadMinus));
            Assert.False(invokePrivateStatic<bool>("isZoomDecreaseKey", Key.Plus));
        }

        [Fact]
        public void NotationHotkeyResolverMapsPageKeysAndModifiers()
        {
            Assert.Equal(
                "ShiftLaneUp",
                invokePrivateStaticObject("getNotationHotkeyAction", Key.PageUp, false, false, false).ToString());
            Assert.Equal(
                "ShiftLaneDown",
                invokePrivateStaticObject("getNotationHotkeyAction", Key.PageDown, false, false, false).ToString());

            Assert.Equal(
                "ArticulationUp",
                invokePrivateStaticObject("getNotationHotkeyAction", Key.PageUp, true, false, false).ToString());
            Assert.Equal(
                "ArticulationDown",
                invokePrivateStaticObject("getNotationHotkeyAction", Key.PageDown, true, false, false).ToString());

            Assert.Equal(
                "None",
                invokePrivateStaticObject("getNotationHotkeyAction", Key.PageUp, true, true, false).ToString());
            Assert.Equal(
                "None",
                invokePrivateStaticObject("getNotationHotkeyAction", Key.PageDown, false, false, true).ToString());
            Assert.Equal(
                "None",
                invokePrivateStaticObject("getNotationHotkeyAction", Key.A, false, false, false).ToString());
        }

        [Fact]
        public void NotationArticulationPresetVelocityMappingIsStable()
        {
            Type presetType = typeof(EditorScreen).GetNestedType("NotationArticulationPreset", BindingFlags.NonPublic)
                ?? throw new InvalidOperationException("NotationArticulationPreset enum was not found.");

            object ghost = Enum.Parse(presetType, "Ghost");
            object normal = Enum.Parse(presetType, "Normal");
            object accent = Enum.Parse(presetType, "Accent");

            Assert.Equal(0.25, invokePrivateStatic<double>("getNotationVelocityForPreset", ghost), 3);
            Assert.Equal(0.68, invokePrivateStatic<double>("getNotationVelocityForPreset", normal), 3);
            Assert.Equal(0.95, invokePrivateStatic<double>("getNotationVelocityForPreset", accent), 3);

            Assert.Equal("Ghost", invokePrivateStaticObject("getNotationPresetFromVelocity", 0.10d).ToString());
            Assert.Equal("Normal", invokePrivateStaticObject("getNotationPresetFromVelocity", 0.68d).ToString());
            Assert.Equal("Accent", invokePrivateStaticObject("getNotationPresetFromVelocity", 0.98d).ToString());
        }

        [Fact]
        public void CycleNotationArticulationPresetMutatesSelectedNoteVelocity()
        {
            var screen = new EditorScreen();
            var beatmap = createMinimalBeatmap(new HitObject { Time = 1000, Component = "snare", Velocity = 0.68 });
            var selected = beatmap.HitObjects[0];

            setPrivateField(screen, "beatmap", beatmap);
            setPrivateField(screen, "selectedHitObject", selected);

            invokePrivateInstance<object?>(screen, "cycleNotationArticulationPreset", true);
            Assert.Equal(0.95, selected.Velocity, 3);

            invokePrivateInstance<object?>(screen, "cycleNotationArticulationPreset", false);
            Assert.Equal(0.68, selected.Velocity, 3);

            invokePrivateInstance<object?>(screen, "cycleNotationArticulationPreset", false);
            Assert.Equal(0.25, selected.Velocity, 3);
        }

        [Fact]
        public void ShiftSelectionToAdjacentNotationLaneRequiresManuscriptMode()
        {
            var screen = new EditorScreen();
            var beatmap = createMinimalBeatmap(new HitObject { Time = 1000, Component = "snare", Velocity = 0.68 });
            var selected = beatmap.HitObjects[0];

            setPrivateField(screen, "beatmap", beatmap);
            setPrivateField(screen, "selectedHitObject", selected);
            setPrivateField(screen, "previewMode", new Bindable<EditorPreviewMode>(EditorPreviewMode.Playfield3D));

            invokePrivateInstance<object?>(screen, "shiftSelectionToAdjacentNotationLane", true);
            Assert.Equal("snare", selected.Component);

            setPrivateField(screen, "previewMode", new Bindable<EditorPreviewMode>(EditorPreviewMode.Manuscript));
            invokePrivateInstance<object?>(screen, "shiftSelectionToAdjacentNotationLane", true);
            Assert.Equal("tom_high", selected.Component);

            invokePrivateInstance<object?>(screen, "shiftSelectionToAdjacentNotationLane", false);
            Assert.Equal("snare", selected.Component);
        }

        [Fact]
        public void MergeHitObjects_ReplacesSelectionRangeAndShiftsRelativeTimes()
        {
            var screen = new EditorScreen();
            var beatmap = createMinimalBeatmap(
                new HitObject { Time = 500, Component = "kick", Velocity = 0.8 },
                new HitObject { Time = 1200, Component = "snare", Velocity = 0.8 },
                new HitObject { Time = 1400, Component = "hihat_closed", Velocity = 0.8 },
                new HitObject { Time = 2500, Component = "tom", Velocity = 0.8 });

            setPrivateField(screen, "beatmap", beatmap);

            var generated = new List<HitObject>
            {
                new() { Time = 100, Component = "kick", Velocity = 0.9 },
                new() { Time = 350, Component = "snare", Velocity = 0.9 },
                new() { Time = 900, Component = "hihat_open", Velocity = 0.9 },
                new() { Time = 2200, Component = "ride_bow", Velocity = 0.9 } // outside range after shift, should drop
            };

            invokePrivateInstance<object?>(screen, "mergeHitObjects", generated, 1000d, 2000d);

            var times = beatmap.HitObjects.Select(h => h.Time).OrderBy(t => t).ToArray();
            Assert.Equal(new[] { 500, 1100, 1350, 1900, 2500 }, times);

            Assert.DoesNotContain(beatmap.HitObjects, h => h.Time == 1200 && h.Component == "snare");
            Assert.DoesNotContain(beatmap.HitObjects, h => h.Time == 1400 && h.Component == "hihat_closed");
            Assert.DoesNotContain(beatmap.HitObjects, h => h.Time == 3200);
        }

        [Fact]
        public void MergeHitObjects_ClearsSelectedHitWhenRemovedAndArmsUndo()
        {
            var screen = new EditorScreen();
            var beatmap = createMinimalBeatmap(
                new HitObject { Time = 1200, Component = "snare", Velocity = 0.8 },
                new HitObject { Time = 2600, Component = "tom", Velocity = 0.8 });

            var selected = beatmap.HitObjects[0];

            setPrivateField(screen, "beatmap", beatmap);
            setPrivateField(screen, "selectedHitObject", selected);

            var generated = new List<HitObject>
            {
                new() { Time = 150, Component = "kick", Velocity = 0.9 }
            };

            invokePrivateInstance<object?>(screen, "mergeHitObjects", generated, 1000d, 2000d);

            Assert.Null(getPrivateField<HitObject?>(screen, "selectedHitObject"));
            Assert.True(getPrivateField<bool>(screen, "hasUnsavedChanges"));
            Assert.False(getPrivateField<bool>(screen, "editSnapshotArmed"));

            var undoStack = getPrivateField<List<EditorSnapshot>>(screen, "undoStack");
            Assert.Single(undoStack);
        }

        [Fact]
        public void ReassignSelectedComponent_ChangesComponentAndTracksUndoState()
        {
            var screen = new EditorScreen();
            var beatmap = createMinimalBeatmap(new HitObject { Time = 1000, Component = "kick", Velocity = 0.8 });
            var selected = beatmap.HitObjects[0];

            setPrivateField(screen, "beatmap", beatmap);
            setPrivateField(screen, "selectedHitObject", selected);

            var reassignBindable = getPrivateField<Bindable<string>>(screen, "componentReassignSelection");
            reassignBindable.Value = "snare";

            invokePrivateInstance<object?>(screen, "reassignSelectedComponent");

            Assert.Equal("snare", selected.Component);
            Assert.True(getPrivateField<bool>(screen, "hasUnsavedChanges"));
            Assert.False(getPrivateField<bool>(screen, "editSnapshotArmed"));

            var undoStack = getPrivateField<List<EditorSnapshot>>(screen, "undoStack");
            Assert.Single(undoStack);
        }

        private static T invokePrivateStatic<T>(string methodName, params object?[]? args)
        {
            var method = typeof(EditorScreen).GetMethod(methodName, BindingFlags.Static | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException($"Static method '{methodName}' was not found.");

            return (T)method.Invoke(null, args)!;
        }

        private static object invokePrivateStaticObject(string methodName, params object?[]? args)
        {
            var method = typeof(EditorScreen).GetMethod(methodName, BindingFlags.Static | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException($"Static method '{methodName}' was not found.");

            return method.Invoke(null, args)!;
        }

        private static T invokePrivateInstance<T>(object target, string methodName, params object?[]? args)
        {
            var method = target.GetType().GetMethod(methodName, BindingFlags.Instance | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException($"Instance method '{methodName}' was not found.");

            return (T)method.Invoke(target, args)!;
        }

        private static void setPrivateField<T>(object target, string name, T value)
        {
            var field = target.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException($"Field '{name}' not found.");
            field.SetValue(target, value);
        }

        private static T getPrivateField<T>(object target, string name)
        {
            var field = target.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException($"Field '{name}' not found.");
            return (T)field.GetValue(target)!;
        }

        private static Beatmap createMinimalBeatmap(params HitObject[] hitObjects)
        {
            return new Beatmap
            {
                Metadata = new BeatmapMetadata
                {
                    Title = "Test",
                    Artist = "BeatSight",
                    Creator = "Tests"
                },
                Timing = new TimingInfo
                {
                    Bpm = 120,
                    TimeSignature = "4/4"
                },
                Audio = new AudioInfo
                {
                    Filename = "test.wav",
                    Duration = 120000
                },
                HitObjects = new System.Collections.Generic.List<HitObject>(hitObjects)
            };
        }
    }
}
