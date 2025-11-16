using System;
using System.Globalization;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;

namespace BeatSight.Game.Mapping
{
    /// <summary>
    /// Resolves detected drum components to lanes based on the active lane layout.
    /// </summary>
    public static class DrumLaneHeuristics
    {
        private const int maxCategoryDepth = 8;

        /// <summary>
        /// Resolves a detected component string to a lane using the provided layout.
        /// </summary>
        public static int ResolveLane(string? component, LaneLayout layout, int? storedLane = null)
        {
            Span<DrumComponentCategory> categories = stackalloc DrumComponentCategory[maxCategoryDepth];
            var side = buildCategoryPriority(component, categories, out var length);

            if (length == 0)
            {
                categories[0] = DrumComponentCategory.Unknown;
                length = 1;
                side = SidePreference.Centre;
            }

            return layout.ResolveLane(categories[..length], side, storedLane);
        }

        /// <summary>
        /// Legacy helper that resolves using the default seven-lane preset.
        /// </summary>
        public static int ResolveLane(string? component)
            => ResolveLane(component, LaneLayoutFactory.Create(LanePreset.DrumSevenLane));

        /// <summary>
        /// Resolves a coarse DrumType to a lane using the provided layout.
        /// </summary>
        public static int ResolveLane(DrumType type, LaneLayout layout, int? storedLane = null)
        {
            Span<DrumComponentCategory> categories = stackalloc DrumComponentCategory[maxCategoryDepth];
            int length = 0;

            SidePreference side = type switch
            {
                DrumType.HiHatClosed or DrumType.HiHatOpen or DrumType.HiHatPedal or DrumType.HiHatFootSplash => SidePreference.Left,
                DrumType.CrashHigh or DrumType.SplashHigh or DrumType.ChinaHigh or DrumType.TomRackHigh => SidePreference.Left,
                DrumType.RideBow or DrumType.RideBell or DrumType.CrashLow or DrumType.CrashStack or DrumType.SplashLow or DrumType.ChinaLow or DrumType.ChinaStack
                    or DrumType.TomRackLow or DrumType.TomFloorHigh or DrumType.TomFloorLow or DrumType.Cowbell => SidePreference.Right,
                _ => SidePreference.Centre
            };

            switch (type)
            {
                case DrumType.Kick:
                    addCategory(ref length, categories, DrumComponentCategory.Kick);
                    break;

                case DrumType.Snare:
                case DrumType.SnareGhost:
                    addCategory(ref length, categories, DrumComponentCategory.Snare);
                    addCategory(ref length, categories, DrumComponentCategory.Rimshot);
                    addCategory(ref length, categories, DrumComponentCategory.CrossStick);
                    break;

                case DrumType.SnareRimshot:
                    addCategory(ref length, categories, DrumComponentCategory.Rimshot);
                    addCategory(ref length, categories, DrumComponentCategory.Snare);
                    addCategory(ref length, categories, DrumComponentCategory.CrossStick);
                    break;

                case DrumType.SnareCrossStick:
                    addCategory(ref length, categories, DrumComponentCategory.CrossStick);
                    addCategory(ref length, categories, DrumComponentCategory.Snare);
                    break;

                case DrumType.HiHatClosed:
                case DrumType.HiHatOpen:
                case DrumType.HiHatPedal:
                case DrumType.HiHatFootSplash:
                    if (type == DrumType.HiHatPedal)
                        addCategory(ref length, categories, DrumComponentCategory.HiHatPedal);

                    if (type != DrumType.HiHatPedal)
                        addCategory(ref length, categories, DrumComponentCategory.HiHatClosed);

                    if (type == DrumType.HiHatOpen || type == DrumType.HiHatFootSplash)
                        addCategory(ref length, categories, DrumComponentCategory.HiHatOpen);

                    addCategory(ref length, categories, DrumComponentCategory.Crash);
                    addCategory(ref length, categories, DrumComponentCategory.Ride);
                    break;

                case DrumType.RideBow:
                case DrumType.RideBell:
                    addCategory(ref length, categories, DrumComponentCategory.Ride);
                    addCategory(ref length, categories, DrumComponentCategory.Crash);
                    addCategory(ref length, categories, DrumComponentCategory.China);
                    break;

                case DrumType.CrashHigh:
                case DrumType.CrashLow:
                case DrumType.CrashStack:
                    addCategory(ref length, categories, DrumComponentCategory.Crash);
                    addCategory(ref length, categories, DrumComponentCategory.Splash);
                    addCategory(ref length, categories, DrumComponentCategory.Ride);
                    addCategory(ref length, categories, DrumComponentCategory.China);
                    break;

                case DrumType.SplashHigh:
                case DrumType.SplashLow:
                    addCategory(ref length, categories, DrumComponentCategory.Splash);
                    addCategory(ref length, categories, DrumComponentCategory.Crash);
                    addCategory(ref length, categories, DrumComponentCategory.Ride);
                    break;

                case DrumType.ChinaHigh:
                case DrumType.ChinaLow:
                case DrumType.ChinaStack:
                    addCategory(ref length, categories, DrumComponentCategory.China);
                    addCategory(ref length, categories, DrumComponentCategory.Crash);
                    addCategory(ref length, categories, DrumComponentCategory.Ride);
                    break;

                case DrumType.TomRackHigh:
                    addCategory(ref length, categories, DrumComponentCategory.TomHigh);
                    addCategory(ref length, categories, DrumComponentCategory.TomMid);
                    break;

                case DrumType.TomRackMid:
                    addCategory(ref length, categories, DrumComponentCategory.TomMid);
                    addCategory(ref length, categories, DrumComponentCategory.TomHigh);
                    addCategory(ref length, categories, DrumComponentCategory.TomLow);
                    break;

                case DrumType.TomRackLow:
                case DrumType.TomFloorHigh:
                    addCategory(ref length, categories, DrumComponentCategory.TomLow);
                    addCategory(ref length, categories, DrumComponentCategory.TomMid);
                    break;

                case DrumType.TomFloorLow:
                    addCategory(ref length, categories, DrumComponentCategory.TomLow);
                    break;

                case DrumType.Cowbell:
                    addCategory(ref length, categories, DrumComponentCategory.Cowbell);
                    addCategory(ref length, categories, DrumComponentCategory.Percussion);
                    addCategory(ref length, categories, DrumComponentCategory.Ride);
                    break;

                case DrumType.Percussion:
                    addCategory(ref length, categories, DrumComponentCategory.Percussion);
                    addCategory(ref length, categories, DrumComponentCategory.Cowbell);
                    break;

                case DrumType.Unknown:
                    addCategory(ref length, categories, DrumComponentCategory.Unknown);
                    break;

                default:
                    addCategory(ref length, categories, DrumComponentCategory.Unknown);
                    break;
            }

            addCategory(ref length, categories, DrumComponentCategory.Snare);
            addCategory(ref length, categories, DrumComponentCategory.Kick);

            return layout.ResolveLane(categories[..length], side, storedLane);
        }

        /// <summary>
        /// Legacy helper that resolves using the default seven-lane preset.
        /// </summary>
        public static int ResolveLane(DrumType type)
            => ResolveLane(type, LaneLayoutFactory.Create(LanePreset.DrumSevenLane));

        /// <summary>
        /// Ensures all hit objects in the beatmap have lanes resolved with the requested layout.
        /// </summary>
        public static void ApplyToBeatmap(Beatmap? beatmap, LaneLayout layout)
        {
            if (beatmap?.HitObjects == null || beatmap.HitObjects.Count == 0)
                return;

            foreach (var hit in beatmap.HitObjects)
                hit.Lane = ResolveLane(hit.Component, layout, hit.Lane);
        }

        /// <summary>
        /// Legacy helper that applies using a layout derived from lane count.
        /// </summary>
        public static void ApplyToBeatmap(Beatmap? beatmap, int laneCount = 7)
        {
            LanePreset preset = laneCount switch
            {
                4 => LanePreset.DrumFourLane,
                5 => LanePreset.DrumFiveLane,
                6 => LanePreset.DrumSixLane,
                8 => LanePreset.DrumEightLane,
                9 => LanePreset.DrumNineLane,
                _ => LanePreset.DrumSevenLane
            };

            ApplyToBeatmap(beatmap, LaneLayoutFactory.Create(preset));
        }

        private static SidePreference buildCategoryPriority(string? component, Span<DrumComponentCategory> buffer, out int length)
        {
            length = 0;

            if (buffer.Length == 0)
                return SidePreference.Centre;

            if (string.IsNullOrWhiteSpace(component))
            {
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.HiHatClosed);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return SidePreference.Centre;
            }

            string normalized = component
                .Trim()
                .Replace("-", "_", StringComparison.Ordinal)
                .Replace(" ", "_", StringComparison.Ordinal)
                .ToLower(CultureInfo.InvariantCulture);

            bool hasLeftToken = normalized.Contains("left", StringComparison.Ordinal) || normalized.EndsWith("_l", StringComparison.Ordinal) || normalized.Contains("_left_", StringComparison.Ordinal);
            bool hasRightToken = normalized.Contains("right", StringComparison.Ordinal) || normalized.EndsWith("_r", StringComparison.Ordinal) || normalized.Contains("_right_", StringComparison.Ordinal);

            SidePreference side = SidePreference.Centre;

            if (isKick(normalized))
            {
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.HiHatClosed);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return SidePreference.Centre;
            }

            if (isSnare(normalized))
            {
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.Rimshot);
                addCategory(ref length, buffer, DrumComponentCategory.CrossStick);
                addCategory(ref length, buffer, DrumComponentCategory.HiHatClosed);
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return SidePreference.Centre;
            }

            if (isHiHat(normalized))
            {
                bool isPedal = normalized.Contains("pedal", StringComparison.Ordinal) || normalized.Contains("foot", StringComparison.Ordinal);
                bool isOpen = !isPedal && (normalized.Contains("open", StringComparison.Ordinal) || normalized.Contains("splash", StringComparison.Ordinal));

                if (isPedal)
                    addCategory(ref length, buffer, DrumComponentCategory.HiHatPedal);

                if (isOpen)
                    addCategory(ref length, buffer, DrumComponentCategory.HiHatOpen);

                addCategory(ref length, buffer, DrumComponentCategory.HiHatClosed);
                addCategory(ref length, buffer, DrumComponentCategory.Crash);
                addCategory(ref length, buffer, DrumComponentCategory.Ride);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return SidePreference.Left;
            }

            if (isTom(normalized, out var tomCategory, out var tomSide))
            {
                if (tomSide != SidePreference.Centre)
                    side = tomSide;

                addCategory(ref length, buffer, tomCategory);
                addCategory(ref length, buffer, DrumComponentCategory.TomMid);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return side;
            }

            if (isRide(normalized))
            {
                addCategory(ref length, buffer, DrumComponentCategory.Ride);
                addCategory(ref length, buffer, DrumComponentCategory.Crash);
                addCategory(ref length, buffer, DrumComponentCategory.China);
                addCategory(ref length, buffer, DrumComponentCategory.Cowbell);
                addCategory(ref length, buffer, DrumComponentCategory.Percussion);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return SidePreference.Right;
            }

            if (isCrash(normalized))
            {
                side = determineCrashSide(normalized, hasLeftToken, hasRightToken);
                addCategory(ref length, buffer, DrumComponentCategory.Crash);
                addCategory(ref length, buffer, DrumComponentCategory.Splash);
                addCategory(ref length, buffer, DrumComponentCategory.Ride);
                addCategory(ref length, buffer, DrumComponentCategory.China);
                addCategory(ref length, buffer, DrumComponentCategory.Percussion);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return side;
            }

            if (isChina(normalized))
            {
                addCategory(ref length, buffer, DrumComponentCategory.China);
                addCategory(ref length, buffer, DrumComponentCategory.Crash);
                addCategory(ref length, buffer, DrumComponentCategory.Ride);
                addCategory(ref length, buffer, DrumComponentCategory.Percussion);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return SidePreference.Right;
            }

            if (isSplash(normalized))
            {
                addCategory(ref length, buffer, DrumComponentCategory.Splash);
                addCategory(ref length, buffer, DrumComponentCategory.Crash);
                addCategory(ref length, buffer, DrumComponentCategory.Ride);
                addCategory(ref length, buffer, DrumComponentCategory.Percussion);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return hasRightToken ? SidePreference.Right : SidePreference.Left;
            }

            if (isCowbell(normalized) || isPercussion(normalized))
            {
                addCategory(ref length, buffer, DrumComponentCategory.Cowbell);
                addCategory(ref length, buffer, DrumComponentCategory.Percussion);
                addCategory(ref length, buffer, DrumComponentCategory.Ride);
                addCategory(ref length, buffer, DrumComponentCategory.Snare);
                addCategory(ref length, buffer, DrumComponentCategory.Kick);
                addCategory(ref length, buffer, DrumComponentCategory.Unknown);
                return hasRightToken ? SidePreference.Right : SidePreference.Centre;
            }

            addCategory(ref length, buffer, DrumComponentCategory.Unknown);
            addCategory(ref length, buffer, DrumComponentCategory.Snare);
            addCategory(ref length, buffer, DrumComponentCategory.Kick);
            return SidePreference.Centre;
        }

        private static void addCategory(ref int length, Span<DrumComponentCategory> buffer, DrumComponentCategory category)
        {
            if (length >= buffer.Length)
                return;

            for (int i = 0; i < length; i++)
            {
                if (buffer[i] == category)
                    return;
            }

            buffer[length++] = category;
        }

        private static bool isKick(string tokenized) =>
            tokenized.Contains("kick", StringComparison.Ordinal) ||
            tokenized.Contains("bd", StringComparison.Ordinal) ||
            tokenized.Contains("bass", StringComparison.Ordinal);

        private static bool isSnare(string tokenized) =>
            tokenized.Contains("snare", StringComparison.Ordinal) ||
            tokenized.Contains("sidestick", StringComparison.Ordinal) ||
            tokenized.Contains("stickshot", StringComparison.Ordinal) ||
            tokenized.Contains("rimshot", StringComparison.Ordinal) ||
            tokenized.Contains("cross", StringComparison.Ordinal);

        private static bool isHiHat(string tokenized) =>
            tokenized.Contains("hihat", StringComparison.Ordinal) ||
            tokenized.Contains("hi_hat", StringComparison.Ordinal) ||
            tokenized.Contains("hat", StringComparison.Ordinal) ||
            tokenized.Contains("hh", StringComparison.Ordinal);

        private static bool isTom(string tokenized, out DrumComponentCategory category, out SidePreference side)
        {
            side = SidePreference.Centre;
            category = DrumComponentCategory.TomMid;

            if (!tokenized.Contains("tom", StringComparison.Ordinal) && !tokenized.Contains("rack", StringComparison.Ordinal) && !tokenized.Contains("floor", StringComparison.Ordinal))
                return false;

            if (tokenized.Contains("floor", StringComparison.Ordinal) || tokenized.Contains("low", StringComparison.Ordinal) || tokenized.Contains("flr", StringComparison.Ordinal))
            {
                category = DrumComponentCategory.TomLow;
                side = SidePreference.Right;
                return true;
            }

            if (tokenized.Contains("high", StringComparison.Ordinal) || tokenized.Contains("rack", StringComparison.Ordinal) || tokenized.Contains("tom1", StringComparison.Ordinal))
            {
                category = DrumComponentCategory.TomHigh;
                side = SidePreference.Left;
                return true;
            }

            if (tokenized.Contains("mid", StringComparison.Ordinal) || tokenized.Contains("tom2", StringComparison.Ordinal))
            {
                category = DrumComponentCategory.TomMid;
                return true;
            }

            int digit = extractTrailingDigit(tokenized);
            if (digit == 1)
            {
                category = DrumComponentCategory.TomHigh;
                side = SidePreference.Left;
            }
            else if (digit >= 3)
            {
                category = DrumComponentCategory.TomLow;
                side = SidePreference.Right;
            }
            else if (digit == 2)
            {
                category = DrumComponentCategory.TomMid;
            }

            return true;
        }

        private static bool isRide(string tokenized) =>
            tokenized.Contains("ride", StringComparison.Ordinal) || tokenized.Contains("bell", StringComparison.Ordinal);

        private static bool isCrash(string tokenized) =>
            tokenized.Contains("crash", StringComparison.Ordinal) || tokenized.Contains("stack", StringComparison.Ordinal);

        private static bool isChina(string tokenized) => tokenized.Contains("china", StringComparison.Ordinal);

        private static bool isSplash(string tokenized) => tokenized.Contains("splash", StringComparison.Ordinal);

        private static bool isCowbell(string tokenized) => tokenized.Contains("cowbell", StringComparison.Ordinal);

        private static bool isPercussion(string tokenized) =>
            tokenized.Contains("perc", StringComparison.Ordinal) ||
            tokenized.Contains("clap", StringComparison.Ordinal) ||
            tokenized.Contains("block", StringComparison.Ordinal) ||
            tokenized.Contains("wood", StringComparison.Ordinal) ||
            tokenized.Contains("tamb", StringComparison.Ordinal) ||
            tokenized.Contains("shaker", StringComparison.Ordinal) ||
            tokenized.Contains("triangle", StringComparison.Ordinal) ||
            tokenized.Contains("clave", StringComparison.Ordinal);

        private static SidePreference determineCrashSide(string tokenized, bool hasLeftToken, bool hasRightToken)
        {
            if (hasLeftToken && !hasRightToken)
                return SidePreference.Left;

            if (hasRightToken && !hasLeftToken)
                return SidePreference.Right;

            int digit = extractTrailingDigit(tokenized);

            return digit switch
            {
                1 => SidePreference.Left,
                >= 2 => SidePreference.Right,
                _ => SidePreference.Centre
            };
        }

        private static int extractTrailingDigit(string tokenized)
        {
            for (int i = tokenized.Length - 1; i >= 0; i--)
            {
                if (char.IsDigit(tokenized[i]))
                    return tokenized[i] - '0';
            }

            return -1;
        }
    }
}
