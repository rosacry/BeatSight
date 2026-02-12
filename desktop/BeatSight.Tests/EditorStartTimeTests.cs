using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Editor;
using Xunit;

namespace BeatSight.Tests
{
    public class EditorStartTimeTests
    {
        [Fact]
        public void ResolvePreferredStartTime_UsesPreviewWhenNearbyNotesExist()
        {
            var screen = new EditorScreen();
            var beatmap = CreateBeatmap(previewTime: 10000, hitTimes: new[] { 9600, 12500 });

            SetPrivateField(screen, "beatmap", beatmap);
            SetPrivateField(screen, "trackLength", 309000d);

            (double resolved, string? detail) = InvokePreferredStartResolver(screen);

            Assert.Equal(10000d, resolved);
            Assert.True(string.IsNullOrWhiteSpace(detail));
        }

        [Fact]
        public void ResolvePreferredStartTime_FallsBackWhenPreviewHasNoNearbyNotes()
        {
            var screen = new EditorScreen();
            var beatmap = CreateBeatmap(previewTime: 10000, hitTimes: new[] { 19501 });

            SetPrivateField(screen, "beatmap", beatmap);
            SetPrivateField(screen, "trackLength", 309000d);

            (double resolved, string? detail) = InvokePreferredStartResolver(screen);

            Assert.Equal(17701d, resolved);
            Assert.False(string.IsNullOrWhiteSpace(detail));
            Assert.Contains("first note", detail!, StringComparison.OrdinalIgnoreCase);
        }

        [Fact]
        public void ResolvePreferredStartTime_UsesFirstNoteLeadInWhenNoPreview()
        {
            var screen = new EditorScreen();
            var beatmap = CreateBeatmap(previewTime: null, hitTimes: new[] { 5000, 6200 });

            SetPrivateField(screen, "beatmap", beatmap);
            SetPrivateField(screen, "trackLength", 309000d);

            (double resolved, string? detail) = InvokePreferredStartResolver(screen);

            Assert.Equal(3200d, resolved);
            Assert.True(string.IsNullOrWhiteSpace(detail));
        }

        private static (double resolvedTime, string? detail) InvokePreferredStartResolver(EditorScreen screen)
        {
            var method = typeof(EditorScreen).GetMethod("resolvePreferredStartTime", BindingFlags.Instance | BindingFlags.NonPublic);
            if (method == null)
                throw new InvalidOperationException("resolvePreferredStartTime method not found.");

            object?[] args = { null };
            object? result = method.Invoke(screen, args);

            return ((double)result!, args[0] as string);
        }

        private static Beatmap CreateBeatmap(int? previewTime, IEnumerable<int> hitTimes)
        {
            return new Beatmap
            {
                Metadata = new BeatmapMetadata
                {
                    Title = "Test Song",
                    Artist = "Test Artist",
                    PreviewTime = previewTime
                },
                Audio = new AudioInfo
                {
                    Filename = "test.wav",
                    Duration = 309000
                },
                HitObjects = hitTimes
                    .OrderBy(time => time)
                    .Select(time => new HitObject
                    {
                        Time = time,
                        Component = "kick",
                        Lane = 3
                    })
                    .ToList()
            };
        }

        private static void SetPrivateField(object target, string fieldName, object value)
        {
            var field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null)
                throw new InvalidOperationException($"Field '{fieldName}' not found.");

            field.SetValue(target, value);
        }
    }
}
