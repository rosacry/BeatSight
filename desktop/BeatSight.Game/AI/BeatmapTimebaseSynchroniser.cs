using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;

namespace BeatSight.Game.AI
{
    internal static class BeatmapTimebaseSynchroniser
    {
        public static TimebaseSynchronisationResult Apply(Beatmap beatmap, AiGenerationOptions options)
        {
            if (beatmap == null || options == null)
                return TimebaseSynchronisationResult.Empty;

            var timing = beatmap.Timing ??= new TimingInfo();
            timing.TimingPoints ??= new List<TimingPoint>();

            bool bpmAligned = false;
            bool offsetAdjusted = false;
            int offsetDelta = 0;
            int snapDivisor = 0;

            double? forcedBpm = options.ForcedBpm;
            if (forcedBpm.HasValue && (!double.IsFinite(forcedBpm.Value) || forcedBpm.Value <= 0))
                forcedBpm = null;

            double? forcedOffsetSeconds = options.ForcedOffsetSeconds;
            if (forcedOffsetSeconds.HasValue && !double.IsFinite(forcedOffsetSeconds.Value))
                forcedOffsetSeconds = null;

            double? forcedStepSeconds = options.ForcedStepSeconds;
            if (forcedStepSeconds.HasValue && (!double.IsFinite(forcedStepSeconds.Value) || forcedStepSeconds.Value <= 0))
                forcedStepSeconds = null;

            if (forcedBpm.HasValue && forcedBpm.Value > 0 && !doubleEquals(timing.Bpm, forcedBpm.Value))
            {
                timing.Bpm = forcedBpm.Value;
                bpmAligned = true;
            }

            if (timing.TimingPoints.Count == 0)
            {
                timing.TimingPoints.Add(new TimingPoint
                {
                    Time = timing.Offset,
                    Bpm = timing.Bpm,
                    TimeSignature = timing.TimeSignature
                });
            }
            else if (bpmAligned)
            {
                timing.TimingPoints[0].Bpm = timing.Bpm;
            }

            if (forcedOffsetSeconds.HasValue && double.IsFinite(forcedOffsetSeconds.Value))
            {
                int forcedOffsetMs = (int)Math.Round(forcedOffsetSeconds.Value * 1000.0);
                offsetDelta = forcedOffsetMs - timing.Offset;

                if (Math.Abs(offsetDelta) > 1)
                {
                    timing.Offset = forcedOffsetMs;
                    offsetAdjusted = true;
                    shiftTimedCollections(beatmap, offsetDelta);
                }
                else
                {
                    offsetDelta = 0;
                }
            }

            if (forcedStepSeconds.HasValue && forcedStepSeconds.Value > 0 && forcedBpm.HasValue && forcedBpm.Value > 0)
            {
                double beatLength = 60.0 / forcedBpm.Value;
                double divisorExact = beatLength / forcedStepSeconds.Value;
                int divisor = (int)Math.Clamp(Math.Round(divisorExact), 1, 48);
                if (divisor > 0)
                {
                    beatmap.Editor ??= new EditorInfo();
                    beatmap.Editor.SnapDivisor = divisor;
                    snapDivisor = divisor;
                }
            }

            if (offsetAdjusted)
            {
                for (int i = 0; i < timing.TimingPoints.Count; i++)
                    timing.TimingPoints[i].Time += offsetDelta;

                if (timing.TimingPoints.Count > 0)
                    timing.TimingPoints[0].Time = timing.Offset;

                if (bpmAligned)
                    timing.TimingPoints[0].Bpm = timing.Bpm;
            }
            else if (bpmAligned)
            {
                timing.TimingPoints[0].Bpm = timing.Bpm;
            }

            return new TimebaseSynchronisationResult(bpmAligned, offsetAdjusted, offsetDelta, snapDivisor);
        }

        private static void shiftTimedCollections(Beatmap beatmap, int delta)
        {
            if (beatmap.HitObjects != null)
            {
                foreach (var hit in beatmap.HitObjects)
                {
                    hit.Time += delta;
                    if (hit.Time < 0)
                        hit.Time = 0;
                }
            }

            if (beatmap.Editor?.Bookmarks != null)
            {
                for (int i = 0; i < beatmap.Editor.Bookmarks.Count; i++)
                    beatmap.Editor.Bookmarks[i] += delta;
            }
        }

        private static bool doubleEquals(double a, double b)
            => Math.Abs(a - b) <= 0.0001;

        internal readonly struct TimebaseSynchronisationResult
        {
            public static TimebaseSynchronisationResult Empty => new(false, false, 0, 0);

            public TimebaseSynchronisationResult(bool bpmAligned, bool offsetAdjusted, int offsetDelta, int snapDivisor)
            {
                BpmAligned = bpmAligned;
                OffsetAdjusted = offsetAdjusted;
                OffsetDelta = offsetDelta;
                SnapDivisor = snapDivisor;
            }

            public bool BpmAligned { get; }
            public bool OffsetAdjusted { get; }
            public int OffsetDelta { get; }
            public int SnapDivisor { get; }
        }
    }
}
