using System;
using System.Collections.Generic;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;

namespace BeatSight.Game.Mapping
{
    /// <summary>
    /// Provides consistent heuristics for mapping drum components or detected drum types to BeatSight's 7-lane layout.
    /// </summary>
    public static class DrumLaneHeuristics
    {
        private static readonly Dictionary<string, int> componentToLane = new(StringComparer.OrdinalIgnoreCase)
        {
            {"crash", 0},
            {"crash_left", 0},
            {"crash_right", 0},
            {"crash2", 0},
            {"hi_hat", 1},
            {"hihat", 1},
            {"hihat_closed", 1},
            {"hihat_open", 1},
            {"hihat_pedal", 1},
            {"snare", 2},
            {"rimshot", 2},
            {"kick", 3},
            {"bass", 3},
            {"tom_high", 4},
            {"tom_mid", 4},
            {"tom_low", 4},
            {"floor_tom", 4},
            {"ride", 5},
            {"ride_bell", 5},
            {"cowbell", 5},
            {"china", 6},
            {"splash", 6},
            {"stack", 6}
        };

        public static int ResolveLane(string? component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return 3;

            if (componentToLane.TryGetValue(component, out var lane))
                return lane;

            string normalized = component.Replace("-", string.Empty, StringComparison.Ordinal)
                                          .Replace(" ", string.Empty, StringComparison.Ordinal)
                                          .ToLowerInvariant();

            if (componentToLane.TryGetValue(normalized, out lane))
                return lane;

            if (normalized.Contains("kick"))
                return 3;
            if (normalized.Contains("snare"))
                return 2;
            if (normalized.Contains("hat"))
                return 1;
            if (normalized.Contains("tom"))
                return 4;
            if (normalized.Contains("ride"))
                return 5;
            if (normalized.Contains("crash") || normalized.Contains("china") || normalized.Contains("splash"))
                return normalized.Contains("china") ? 6 : 0;

            return 3;
        }

        public static int ResolveLane(DrumType type) => type switch
        {
            DrumType.Kick => 3,
            DrumType.Snare => 2,
            DrumType.HiHat => 1,
            DrumType.Tom => 4,
            DrumType.Cymbal => 5,
            _ => 3
        };

        /// <summary>
        /// Applies default lane values to the provided hit objects where missing or out of range.
        /// </summary>
        public static void ApplyToBeatmap(Beatmap? beatmap, int laneCount = 7)
        {
            if (beatmap?.HitObjects == null || beatmap.HitObjects.Count == 0)
                return;

            int maxLane = Math.Max(1, laneCount) - 1;

            foreach (var hit in beatmap.HitObjects)
            {
                int resolvedLane;

                if (hit.Lane is int existing && existing >= 0 && existing <= maxLane)
                    resolvedLane = existing;
                else
                    resolvedLane = ResolveLane(hit.Component);

                hit.Lane = Math.Clamp(resolvedLane, 0, maxLane);
            }
        }
    }
}