using System;
using System.Collections.Generic;
using BeatSight.Game.UI.Theming;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Notation
{
    public enum DrumNotehead
    {
        /// <summary>Filled oval (drums).</summary>
        Normal,
        /// <summary>"x" (cymbals, hi-hat).</summary>
        Cross,
        /// <summary>Filled diamond (ride bell).</summary>
        Diamond,
        /// <summary>"x" in a ring (cross-stick).</summary>
        CircledCross,
        /// <summary>Outlined triangle (cowbell, other percussion).</summary>
        Triangle
    }

    /// <summary>Hands are written stems-up (upper voice); feet stems-down (lower voice).</summary>
    public enum DrumVoice
    {
        Hands = 0,
        Feet = 1
    }

    /// <summary>
    /// Where and how one drum component is written on a five-line staff.
    /// <see cref="StaffStep"/> counts half-spaces from the middle line: +4 is the top line, -4 the bottom line,
    /// +6 the first ledger line above.
    /// </summary>
    public readonly record struct DrumNotationSymbol(
        string Key,
        string Name,
        int StaffStep,
        DrumNotehead Head,
        DrumVoice Voice,
        bool OpenMark,
        Color4 Colour);

    /// <summary>
    /// Standard drum-set notation (Percussive Arts Society / Weinberg drum key, as used by most method books and
    /// transcription sites): kick in the bottom space, floor tom in the second space, snare in the third space,
    /// mid/high toms on the fourth line/space, ride "x" on the top line, hi-hat "x" above the staff, crash "x" on
    /// the first ledger line, china above it, hi-hat pedal "x" below the staff.
    /// </summary>
    public static class DrumNotation
    {
        public const int TopLineStep = 4;
        public const int BottomLineStep = -4;

        /// <summary>Components ordered from the lowest staff position to the highest (editor up/down reassignment).</summary>
        private static readonly string[] bottomToTop =
        {
            "hihat_pedal",
            "kick",
            "tom_low",
            "snare",
            "tom_mid",
            "tom_high",
            "ride",
            "hihat",
            "crash",
            "china"
        };

        public static IReadOnlyList<string> BottomToTop => bottomToTop;

        public static DrumNotationSymbol Resolve(string? component)
        {
            string key = NormalizeComponentKey(component);
            Color4 colour = DrumPalette.ForComponent(key == "percussion" ? "percussion" : key);

            return key switch
            {
                "kick" => new DrumNotationSymbol(key, "Kick", -3, DrumNotehead.Normal, DrumVoice.Feet, false, colour),
                "hihat_pedal" => new DrumNotationSymbol(key, "Hi-hat foot", -5, DrumNotehead.Cross, DrumVoice.Feet, false, colour),
                "snare" => new DrumNotationSymbol(key, "Snare", 1, DrumNotehead.Normal, DrumVoice.Hands, false, colour),
                "cross_stick" => new DrumNotationSymbol(key, "Cross-stick", 1, DrumNotehead.CircledCross, DrumVoice.Hands, false, DrumPalette.Snare),
                "tom_low" => new DrumNotationSymbol(key, "Floor tom", -1, DrumNotehead.Normal, DrumVoice.Hands, false, colour),
                "tom_mid" => new DrumNotationSymbol(key, "Mid tom", 2, DrumNotehead.Normal, DrumVoice.Hands, false, colour),
                "tom_high" => new DrumNotationSymbol(key, "High tom", 3, DrumNotehead.Normal, DrumVoice.Hands, false, colour),
                "ride" => new DrumNotationSymbol(key, "Ride", 4, DrumNotehead.Cross, DrumVoice.Hands, false, colour),
                "ride_bell" => new DrumNotationSymbol(key, "Ride bell", 4, DrumNotehead.Diamond, DrumVoice.Hands, false, colour),
                "hihat_open" => new DrumNotationSymbol(key, "Open hi-hat", 5, DrumNotehead.Cross, DrumVoice.Hands, true, colour),
                "hihat_half_open" => new DrumNotationSymbol(key, "Half-open hi-hat", 5, DrumNotehead.Cross, DrumVoice.Hands, true, DrumPalette.HiHatOpen),
                "hihat" => new DrumNotationSymbol(key, "Hi-hat", 5, DrumNotehead.Cross, DrumVoice.Hands, false, colour),
                "crash" => new DrumNotationSymbol(key, "Crash", 6, DrumNotehead.Cross, DrumVoice.Hands, false, colour),
                "splash" => new DrumNotationSymbol(key, "Splash", 6, DrumNotehead.Cross, DrumVoice.Hands, false, colour),
                "china" => new DrumNotationSymbol(key, "China", 7, DrumNotehead.Cross, DrumVoice.Hands, false, colour),
                "cowbell" => new DrumNotationSymbol(key, "Cowbell", 3, DrumNotehead.Triangle, DrumVoice.Hands, false, DrumPalette.Percussion),
                _ => new DrumNotationSymbol("percussion", "Percussion", 2, DrumNotehead.Triangle, DrumVoice.Hands, false, DrumPalette.Percussion),
            };
        }

        /// <summary>The next component one staff position up (direction &gt; 0) or down (&lt; 0); clamps at the ends.</summary>
        public static string Adjacent(string? component, int direction)
        {
            int index = IndexInCycle(component);
            int step = Math.Sign(direction);
            return bottomToTop[Math.Clamp(index + step, 0, bottomToTop.Length - 1)];
        }

        public static int IndexInCycle(string? component)
        {
            string key = NormalizeComponentKey(component) switch
            {
                "hihat_open" or "hihat_half_open" => "hihat",
                "ride_bell" => "ride",
                "cross_stick" => "snare",
                "splash" => "crash",
                "cowbell" or "percussion" => "snare",
                var other => other
            };

            int index = Array.IndexOf(bottomToTop, key);
            return index >= 0 ? index : Array.IndexOf(bottomToTop, "snare");
        }

        /// <summary>
        /// Maps beatmap component names (including ranked suffixes like "crash_2" and synonyms) to notation keys.
        /// </summary>
        public static string NormalizeComponentKey(string? component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return "snare";

            string key = component.Trim().ToLowerInvariant().Replace('-', '_').Replace(' ', '_');

            int underscore = key.LastIndexOf('_');
            if (underscore > 0 && underscore < key.Length - 1)
            {
                bool numericSuffix = true;
                for (int i = underscore + 1; i < key.Length; i++)
                {
                    if (!char.IsDigit(key[i]))
                    {
                        numericSuffix = false;
                        break;
                    }
                }

                if (numericSuffix)
                    key = key[..underscore];
            }

            if (key.Contains("kick") || key.Contains("bass"))
                return "kick";
            if (key.Contains("cross_stick") || key.Contains("xstick") || key.Contains("side_stick") || key.Contains("sidestick") || key.Contains("rim"))
                return "cross_stick";
            if (key.Contains("snare"))
                return "snare";
            if (key.Contains("hat") || key.Contains("hh"))
            {
                if (key.Contains("pedal") || key.Contains("foot"))
                    return "hihat_pedal";
                if (key.Contains("half") || key.Contains("semi"))
                    return "hihat_half_open";
                if (key.Contains("open"))
                    return "hihat_open";
                return "hihat";
            }

            if (key.Contains("tom"))
            {
                if (key.Contains("high") || key.Contains("rack"))
                    return "tom_high";
                if (key.Contains("low") || key.Contains("floor"))
                    return "tom_low";
                return "tom_mid";
            }

            if (key.Contains("floor"))
                return "tom_low";
            if (key.Contains("bell") && key.Contains("ride"))
                return "ride_bell";
            if (key.Contains("cowbell"))
                return "cowbell";
            if (key.Contains("ride"))
                return "ride";
            if (key.Contains("china"))
                return "china";
            if (key.Contains("splash"))
                return "splash";
            if (key.Contains("crash") || key.Contains("cymbal"))
                return "crash";
            if (key.Contains("bell"))
                return "ride_bell";

            return "percussion";
        }
    }
}
