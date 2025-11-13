using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using BeatSight.Game.Configuration;

namespace BeatSight.Game.Mapping
{
    /// <summary>
    /// Describes the semantic mapping between drum components and visual lanes.
    /// </summary>
    public sealed class LaneLayout
    {
        private readonly ReadOnlyDictionary<DrumComponentCategory, IReadOnlyList<int>> categoryLookup;
        private readonly List<int> laneIndices;

        internal LaneLayout(LanePreset preset, Dictionary<DrumComponentCategory, int[]> categoryMap, int laneCount)
        {
            if (laneCount <= 0)
                throw new ArgumentOutOfRangeException(nameof(laneCount), "Lane count must be positive.");

            Preset = preset;
            LaneCount = laneCount;

            var normalised = new Dictionary<DrumComponentCategory, IReadOnlyList<int>>();
            foreach (var pair in categoryMap)
            {
                var ordered = pair.Value
                    .Where(index => index >= 0 && index < laneCount)
                    .OrderBy(index => index)
                    .ToArray();

                if (ordered.Length == 0)
                    continue;

                normalised[pair.Key] = Array.AsReadOnly(ordered);
            }

            categoryLookup = new ReadOnlyDictionary<DrumComponentCategory, IReadOnlyList<int>>(normalised);
            laneIndices = Enumerable.Range(0, laneCount).ToList();

            KickLane = ResolveLane(new[] { DrumComponentCategory.Kick, DrumComponentCategory.Snare, DrumComponentCategory.HiHatClosed }, SidePreference.Centre, null);
            SnareLane = ResolveLane(new[] { DrumComponentCategory.Snare, DrumComponentCategory.Rimshot, DrumComponentCategory.CrossStick }, SidePreference.Centre, null);
            HiHatLane = ResolveLane(new[] { DrumComponentCategory.HiHatClosed, DrumComponentCategory.HiHatOpen, DrumComponentCategory.HiHatPedal }, SidePreference.Left, null);
            RideLane = ResolveLane(new[] { DrumComponentCategory.Ride, DrumComponentCategory.Crash, DrumComponentCategory.China }, SidePreference.Right, null);
        }

        public LanePreset Preset { get; }

        public int LaneCount { get; }

        public int KickLane { get; }

        public int SnareLane { get; }

        public int HiHatLane { get; }

        public int RideLane { get; }

        public IReadOnlyList<int> GetLanesFor(DrumComponentCategory category) =>
            categoryLookup.TryGetValue(category, out var lanes) ? lanes : Array.Empty<int>();

        public bool IsLaneValid(int lane) => lane >= 0 && lane < LaneCount;

        public int ClampLane(int lane) => Math.Clamp(lane, 0, LaneCount - 1);

        public int ResolveLane(ReadOnlySpan<DrumComponentCategory> categoryPriority, SidePreference sidePreference, int? storedLane)
        {
            if (storedLane.HasValue && IsLaneValid(storedLane.Value))
                return storedLane.Value;

            foreach (var category in categoryPriority)
            {
                if (!categoryLookup.TryGetValue(category, out var lanes) || lanes.Count == 0)
                    continue;

                if (lanes.Count == 1)
                    return lanes[0];

                int candidate = sidePreference switch
                {
                    SidePreference.Left => lanes.LastOrDefault(index => index <= KickLane, -1),
                    SidePreference.Right => lanes.FirstOrDefault(index => index >= KickLane, -1),
                    _ => -1
                };

                if (candidate >= 0)
                    return candidate;

                if (sidePreference == SidePreference.Centre)
                {
                    int closest = lanes
                        .OrderBy(index => Math.Abs(index - KickLane))
                        .First();
                    return closest;
                }

                return lanes[0];
            }

            return KickLane;
        }

        public IReadOnlyDictionary<DrumComponentCategory, IReadOnlyList<int>> Categories => categoryLookup;

        public IReadOnlyList<int> Lanes => laneIndices;
    }

    public enum DrumComponentCategory
    {
        Unknown,
        Kick,
        Snare,
        Rimshot,
        CrossStick,
        HiHatClosed,
        HiHatOpen,
        HiHatPedal,
        TomHigh,
        TomMid,
        TomLow,
        Ride,
        Crash,
        China,
        Splash,
        Cowbell,
        Percussion
    }

    public enum SidePreference
    {
        Centre,
        Left,
        Right
    }

    internal static class LaneLayoutFactory
    {
        private static readonly Dictionary<LanePreset, LaneLayout> cache = new();
        private static readonly object cacheLock = new();

        public static LaneLayout Create(LanePreset preset)
        {
            lock (cacheLock)
            {
                if (!cache.TryGetValue(preset, out var layout))
                {
                    var definition = preset switch
                    {
                        LanePreset.DrumFourLane => BuildFourLane(),
                        LanePreset.DrumFiveLane => BuildFiveLane(),
                        LanePreset.DrumSixLane => BuildSixLane(),
                        LanePreset.DrumSevenLane => BuildSevenLane(),
                        LanePreset.DrumEightLane => BuildEightLane(),
                        LanePreset.DrumNineLane => BuildNineLane(),
                        _ => BuildSevenLane()
                    };

                    layout = new LaneLayout(preset, definition.CategoryMap, definition.LaneCount);
                    cache[preset] = layout;
                }

                return layout;
            }
        }

        private static LanePresetDefinition BuildFourLane()
        {
            var map = new Dictionary<DrumComponentCategory, int[]>
            {
                { DrumComponentCategory.Kick, new[] { 2 } },
                { DrumComponentCategory.Snare, new[] { 1 } },
                { DrumComponentCategory.Rimshot, new[] { 1 } },
                { DrumComponentCategory.CrossStick, new[] { 1 } },
                { DrumComponentCategory.HiHatClosed, new[] { 1 } },
                { DrumComponentCategory.HiHatOpen, new[] { 1 } },
                { DrumComponentCategory.HiHatPedal, new[] { 1 } },
                { DrumComponentCategory.TomHigh, new[] { 1, 3 } },
                { DrumComponentCategory.TomMid, new[] { 1, 3 } },
                { DrumComponentCategory.TomLow, new[] { 3 } },
                { DrumComponentCategory.Ride, new[] { 3 } },
                { DrumComponentCategory.Crash, new[] { 0, 3 } },
                { DrumComponentCategory.China, new[] { 3 } },
                { DrumComponentCategory.Splash, new[] { 0, 3 } },
                { DrumComponentCategory.Cowbell, new[] { 3 } },
                { DrumComponentCategory.Percussion, new[] { 0, 3 } },
                { DrumComponentCategory.Unknown, new[] { 2 } }
            };

            return new LanePresetDefinition(4, map);
        }

        private static LanePresetDefinition BuildFiveLane()
        {
            var map = new Dictionary<DrumComponentCategory, int[]>
            {
                { DrumComponentCategory.Kick, new[] { 2 } },
                { DrumComponentCategory.Snare, new[] { 3 } },
                { DrumComponentCategory.Rimshot, new[] { 3 } },
                { DrumComponentCategory.CrossStick, new[] { 3 } },
                { DrumComponentCategory.HiHatClosed, new[] { 1 } },
                { DrumComponentCategory.HiHatOpen, new[] { 1 } },
                { DrumComponentCategory.HiHatPedal, new[] { 1 } },
                { DrumComponentCategory.TomHigh, new[] { 3 } },
                { DrumComponentCategory.TomMid, new[] { 3 } },
                { DrumComponentCategory.TomLow, new[] { 3, 4 } },
                { DrumComponentCategory.Ride, new[] { 4 } },
                { DrumComponentCategory.Crash, new[] { 0, 4 } },
                { DrumComponentCategory.China, new[] { 4 } },
                { DrumComponentCategory.Splash, new[] { 0 } },
                { DrumComponentCategory.Cowbell, new[] { 4 } },
                { DrumComponentCategory.Percussion, new[] { 0, 4 } },
                { DrumComponentCategory.Unknown, new[] { 2, 3 } }
            };

            return new LanePresetDefinition(5, map);
        }

        private static LanePresetDefinition BuildSixLane()
        {
            var map = new Dictionary<DrumComponentCategory, int[]>
            {
                { DrumComponentCategory.Kick, new[] { 3 } },
                { DrumComponentCategory.Snare, new[] { 2 } },
                { DrumComponentCategory.Rimshot, new[] { 2 } },
                { DrumComponentCategory.CrossStick, new[] { 2 } },
                { DrumComponentCategory.HiHatClosed, new[] { 1 } },
                { DrumComponentCategory.HiHatOpen, new[] { 1 } },
                { DrumComponentCategory.HiHatPedal, new[] { 1 } },
                { DrumComponentCategory.TomHigh, new[] { 4 } },
                { DrumComponentCategory.TomMid, new[] { 4 } },
                { DrumComponentCategory.TomLow, new[] { 4 } },
                { DrumComponentCategory.Ride, new[] { 5 } },
                { DrumComponentCategory.Crash, new[] { 0, 5 } },
                { DrumComponentCategory.China, new[] { 5 } },
                { DrumComponentCategory.Splash, new[] { 0 } },
                { DrumComponentCategory.Cowbell, new[] { 5 } },
                { DrumComponentCategory.Percussion, new[] { 0, 5 } },
                { DrumComponentCategory.Unknown, new[] { 2, 3 } }
            };

            return new LanePresetDefinition(6, map);
        }

        private static LanePresetDefinition BuildSevenLane()
        {
            var map = new Dictionary<DrumComponentCategory, int[]>
            {
                { DrumComponentCategory.Kick, new[] { 3 } },
                { DrumComponentCategory.Snare, new[] { 2 } },
                { DrumComponentCategory.Rimshot, new[] { 2 } },
                { DrumComponentCategory.CrossStick, new[] { 2 } },
                { DrumComponentCategory.HiHatClosed, new[] { 1 } },
                { DrumComponentCategory.HiHatOpen, new[] { 1 } },
                { DrumComponentCategory.HiHatPedal, new[] { 1 } },
                { DrumComponentCategory.TomHigh, new[] { 4 } },
                { DrumComponentCategory.TomMid, new[] { 4 } },
                { DrumComponentCategory.TomLow, new[] { 4 } },
                { DrumComponentCategory.Ride, new[] { 5 } },
                { DrumComponentCategory.Crash, new[] { 0, 6 } },
                { DrumComponentCategory.China, new[] { 6 } },
                { DrumComponentCategory.Splash, new[] { 6 } },
                { DrumComponentCategory.Cowbell, new[] { 5 } },
                { DrumComponentCategory.Percussion, new[] { 5, 6 } },
                { DrumComponentCategory.Unknown, new[] { 2, 3 } }
            };

            return new LanePresetDefinition(7, map);
        }

        private static LanePresetDefinition BuildEightLane()
        {
            var map = new Dictionary<DrumComponentCategory, int[]>
            {
                { DrumComponentCategory.Kick, new[] { 3 } },
                { DrumComponentCategory.Snare, new[] { 2 } },
                { DrumComponentCategory.Rimshot, new[] { 2 } },
                { DrumComponentCategory.CrossStick, new[] { 2 } },
                { DrumComponentCategory.HiHatClosed, new[] { 1 } },
                { DrumComponentCategory.HiHatOpen, new[] { 1 } },
                { DrumComponentCategory.HiHatPedal, new[] { 1 } },
                { DrumComponentCategory.TomHigh, new[] { 4 } },
                { DrumComponentCategory.TomMid, new[] { 4, 5 } },
                { DrumComponentCategory.TomLow, new[] { 5 } },
                { DrumComponentCategory.Ride, new[] { 6 } },
                { DrumComponentCategory.Crash, new[] { 0, 7 } },
                { DrumComponentCategory.China, new[] { 7 } },
                { DrumComponentCategory.Splash, new[] { 0 } },
                { DrumComponentCategory.Cowbell, new[] { 6 } },
                { DrumComponentCategory.Percussion, new[] { 0, 6, 7 } },
                { DrumComponentCategory.Unknown, new[] { 2, 3, 4 } }
            };

            return new LanePresetDefinition(8, map);
        }

        private static LanePresetDefinition BuildNineLane()
        {
            var map = new Dictionary<DrumComponentCategory, int[]>
            {
                { DrumComponentCategory.Kick, new[] { 4 } },
                { DrumComponentCategory.Snare, new[] { 3 } },
                { DrumComponentCategory.Rimshot, new[] { 3 } },
                { DrumComponentCategory.CrossStick, new[] { 3 } },
                { DrumComponentCategory.HiHatClosed, new[] { 1 } },
                { DrumComponentCategory.HiHatOpen, new[] { 2 } },
                { DrumComponentCategory.HiHatPedal, new[] { 1 } },
                { DrumComponentCategory.TomHigh, new[] { 5 } },
                { DrumComponentCategory.TomMid, new[] { 5, 6 } },
                { DrumComponentCategory.TomLow, new[] { 6 } },
                { DrumComponentCategory.Ride, new[] { 7 } },
                { DrumComponentCategory.Crash, new[] { 0, 8 } },
                { DrumComponentCategory.China, new[] { 8 } },
                { DrumComponentCategory.Splash, new[] { 0 } },
                { DrumComponentCategory.Cowbell, new[] { 7 } },
                { DrumComponentCategory.Percussion, new[] { 0, 7, 8 } },
                { DrumComponentCategory.Unknown, new[] { 3, 4, 5 } }
            };

            return new LanePresetDefinition(9, map);
        }

        private sealed class LanePresetDefinition
        {
            public LanePresetDefinition(int laneCount, Dictionary<DrumComponentCategory, int[]> categoryMap)
            {
                LaneCount = laneCount;
                CategoryMap = categoryMap;
            }

            public int LaneCount { get; }

            public Dictionary<DrumComponentCategory, int[]> CategoryMap { get; }
        }
    }
}
