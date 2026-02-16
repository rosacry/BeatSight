using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Editor;
using Xunit;

namespace BeatSight.Tests
{
    public class EditorTimelineBehaviourTests
    {
        [Fact]
        public void SetZoomClampsToTimelineBounds()
        {
            var timeline = createTimelineWithBeatmap(out _);

            timeline.SetZoom(0.01);
            Assert.Equal(EditorTimeline.MinZoom, timeline.CurrentZoom, 3);

            timeline.SetZoom(999);
            Assert.Equal(EditorTimeline.MaxZoom, timeline.CurrentZoom, 3);
        }

        [Fact]
        public void SetSnapNormalisesNonPositiveDivisors()
        {
            var timeline = createTimelineWithBeatmap(out _);

            timeline.SetSnap(0, 120);
            Assert.Equal(1, timeline.CurrentSnapDivisor);

            timeline.SetSnap(-8, 120);
            Assert.Equal(1, timeline.CurrentSnapDivisor);
        }

        [Fact]
        public void SetWaveformScaleClampsToAllowedRange()
        {
            var timeline = createTimelineWithBeatmap(out _);

            timeline.SetWaveformScale(0.1);
            Assert.Equal(EditorTimeline.MinWaveformScale, timeline.CurrentWaveformScale, 3);

            timeline.SetWaveformScale(9.0);
            Assert.Equal(EditorTimeline.MaxWaveformScale, timeline.CurrentWaveformScale, 3);
        }

        [Fact]
        public void BeatGridVisibilityCanBeToggled()
        {
            var timeline = createTimelineWithBeatmap(out _);

            timeline.SetBeatGridVisible(false);
            Assert.False(timeline.BeatGridVisible);

            timeline.SetBeatGridVisible(true);
            Assert.True(timeline.BeatGridVisible);
        }

        [Fact]
        public void TrySelectAndDeleteUnknownHitObjectReturnsFalse()
        {
            var timeline = createTimelineWithBeatmap(out _);
            var unknown = new HitObject { Time = 12345, Component = "ride", Lane = 6 };

            Assert.False(timeline.TrySelectHitObject(unknown));
            Assert.False(timeline.TryDeleteHitObject(unknown));
        }

        [Fact]
        public void LoadDebugDataWithInvalidJsonDoesNotCreateOnsets()
        {
            var timeline = createTimelineWithBeatmap(out _);

            timeline.LoadDebugData("{ this is not valid json");

            Assert.False(timeline.HasDetectedOnsets);
        }

        [Fact]
        public void SnapSelectedNoteToTransientSnapsWhenPeakIsWithinThreshold()
        {
            var timeline = createTimelineWithBeatmap(out var beatmap);
            var target = beatmap.HitObjects[0];

            Assert.True(timeline.TrySelectHitObject(target));

            timeline.LoadDebugData("{\"Detection\":{\"Peaks\":[{\"Time\":1.03,\"Confidence\":0.92}]}}");
            Assert.True(timeline.HasDetectedOnsets);

            int snapped = timeline.SnapSelectedNoteToTransient(maxDistanceMs: 50);

            Assert.Equal(1, snapped);
            Assert.Equal(1030, target.Time);
        }

        [Fact]
        public void SnapSelectedNoteToTransientSkipsWhenPeakIsTooFar()
        {
            var timeline = createTimelineWithBeatmap(out var beatmap);
            var target = beatmap.HitObjects[0];

            Assert.True(timeline.TrySelectHitObject(target));
            timeline.LoadDebugData("{\"Detection\":{\"Peaks\":[{\"Time\":1.30,\"Confidence\":0.92}]}}");

            int snapped = timeline.SnapSelectedNoteToTransient(maxDistanceMs: 50);

            Assert.Equal(0, snapped);
            Assert.Equal(1000, target.Time);
        }

        [Fact]
        public void SetSelectionRangePreservesValuesWithinBounds()
        {
            var timeline = createTimelineWithBeatmap(out _);

            timeline.SetSelectionRange(1200, 5800);

            Assert.Equal(1200, timeline.SelectionStart);
            Assert.Equal(5800, timeline.SelectionEnd);
        }

        [Fact]
        public void TryAddHitObjectAtTimeAndLaneAddsSnappedNote()
        {
            var timeline = createTimelineWithBeatmap(out var beatmap);
            timeline.SetSnap(4, 120); // 125ms grid

            bool added = timeline.TryAddHitObjectAtTimeAndLane(1112, lane: 2);

            Assert.True(added);
            Assert.Equal(3, beatmap.HitObjects.Count);
            Assert.Contains(beatmap.HitObjects, h => h.Lane == 2 && h.Time == 1125);
        }

        [Fact]
        public void TryDeleteNearestHitObjectRemovesClosestNoteWithinLaneAndThreshold()
        {
            var timeline = createTimelineWithBeatmap(out var beatmap);
            timeline.SetSnap(4, 120);
            timeline.TryAddHitObjectAtTimeAndLane(1112, lane: 2); // snapped to 1125
            timeline.TryAddHitObjectAtTimeAndLane(2205, lane: 2); // snapped to 2250

            bool deletedNearFirst = timeline.TryDeleteNearestHitObject(1130, lane: 2, maxDistanceMs: 40);
            bool rejectedWrongLane = timeline.TryDeleteNearestHitObject(2250, lane: 5, maxDistanceMs: 80);

            Assert.True(deletedNearFirst);
            Assert.False(rejectedWrongLane);
            Assert.Equal(3, beatmap.HitObjects.Count);
            Assert.DoesNotContain(beatmap.HitObjects, h => h.Lane == 2 && h.Time == 1125);
            Assert.Contains(beatmap.HitObjects, h => h.Lane == 2 && h.Time == 2250);
        }

        private static EditorTimeline createTimelineWithBeatmap(out Beatmap beatmap)
        {
            beatmap = new Beatmap
            {
                Metadata = new BeatmapMetadata
                {
                    Title = "Timeline Test",
                    Artist = "BeatSight"
                },
                Audio = new AudioInfo
                {
                    Filename = "test.wav",
                    Duration = 120000
                },
                HitObjects = new List<HitObject>
                {
                    new() { Time = 1000, Component = "kick", Lane = 3 },
                    new() { Time = 3000, Component = "snare", Lane = 2 }
                }
            };

            var timeline = new EditorTimeline();
            timeline.LoadBeatmap(beatmap, durationMs: beatmap.Audio.Duration, waveform: null);
            return timeline;
        }
    }
}
