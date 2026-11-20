using System;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Theming
{
    /// <summary>
    /// The single source of instrument colours for every practice view (2D, 3D, manuscript legend) and the editor.
    /// Hues follow Rock Band / Clone Hero drum conventions where they exist (snare red, hi-hat yellow, ride blue,
    /// crash green, kick orange) and give every canonical lane its own hue family so neighbouring lanes never
    /// share a colour. The UI chrome stays low-chroma so these colours carry the meaning on screen.
    /// </summary>
    public static class DrumPalette
    {
        public static readonly Color4 Crash = new Color4(61, 220, 151, 255);
        public static readonly Color4 HiHat = new Color4(255, 210, 74, 255);
        public static readonly Color4 HiHatOpen = new Color4(255, 229, 138, 255);
        public static readonly Color4 HiHatPedal = new Color4(204, 168, 60, 255);
        public static readonly Color4 Snare = new Color4(255, 84, 104, 255);
        public static readonly Color4 Kick = new Color4(255, 148, 64, 255);
        public static readonly Color4 Tom = new Color4(169, 139, 255, 255);
        public static readonly Color4 TomHigh = new Color4(195, 168, 255, 255);
        public static readonly Color4 TomMid = new Color4(169, 139, 255, 255);
        public static readonly Color4 TomLow = new Color4(139, 108, 240, 255);
        public static readonly Color4 Ride = new Color4(74, 168, 255, 255);
        public static readonly Color4 RideBell = new Color4(140, 203, 255, 255);
        public static readonly Color4 China = new Color4(240, 101, 200, 255);
        public static readonly Color4 Splash = new Color4(54, 211, 201, 255);
        public static readonly Color4 Percussion = new Color4(163, 174, 196, 255);

        /// <summary>
        /// Colours of the canonical lanes, by lane index:
        /// 0 Crash, 1 Hi-hat, 2 Snare, 3 Kick, 4 Tom, 5 Ride, 6 China, 7 Splash, 8 Percussion.
        /// </summary>
        public static readonly Color4[] CanonicalLanes =
        {
            Crash,
            HiHat,
            Snare,
            Kick,
            Tom,
            Ride,
            China,
            Splash,
            Percussion
        };

        /// <summary>Colour for a canonical lane index (wraps for out-of-range indices).</summary>
        public static Color4 ForLane(int laneIndex)
            => CanonicalLanes[((laneIndex % CanonicalLanes.Length) + CanonicalLanes.Length) % CanonicalLanes.Length];

        /// <summary>
        /// Colour for a beatmap component name such as "hihat_open", "tom_low" or "crash_2".
        /// </summary>
        public static Color4 ForComponent(string? component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return Percussion;

            string key = component.Trim().ToLowerInvariant().Replace('-', '_').Replace(' ', '_');

            if (key.Contains("kick") || key.Contains("bass"))
                return Kick;
            if (key.Contains("snare") || key.Contains("rim") || key.Contains("cross"))
                return Snare;
            if (key.Contains("hihat") || key.Contains("hi_hat") || key.Contains("hat"))
            {
                if (key.Contains("open"))
                    return HiHatOpen;
                if (key.Contains("pedal") || key.Contains("foot"))
                    return HiHatPedal;
                return HiHat;
            }

            if (key.Contains("tom"))
            {
                if (key.Contains("high") || key.Contains("rack"))
                    return TomHigh;
                if (key.Contains("low") || key.Contains("floor"))
                    return TomLow;
                return TomMid;
            }

            if (key.Contains("floor"))
                return TomLow;
            if (key.Contains("ride"))
                return key.Contains("bell") ? RideBell : Ride;
            if (key.Contains("china"))
                return China;
            if (key.Contains("splash"))
                return Splash;
            if (key.Contains("crash") || key.Contains("cymbal"))
                return Crash;

            return Percussion;
        }

        /// <summary>
        /// Text colour that stays readable on top of an instrument colour.
        /// </summary>
        public static Color4 OnColour(Color4 background)
        {
            float luminance = 0.2126f * background.R + 0.7152f * background.G + 0.0722f * background.B;
            return luminance > 0.45f ? new Color4(14, 17, 24, 255) : new Color4(244, 246, 250, 255);
        }

        /// <summary>
        /// The pre-2026-10-24 lane defaults. Charts and settings saved with exactly these values are treated as
        /// "never customised" and shown with the current palette instead.
        /// </summary>
        internal static readonly string[] LegacyLaneDefaultHex =
        {
            "#FAB542",
            "#F2A42A",
            "#FF4256",
            "#7544F9",
            "#4491FF",
            "#F5712C",
            "#FF52B2",
            "#5CD4D0",
            "#78B9FF"
        };

        internal static bool IsLegacyDefault(string? hex, int laneIndex)
        {
            if (string.IsNullOrWhiteSpace(hex) || laneIndex < 0 || laneIndex >= LegacyLaneDefaultHex.Length)
                return false;

            string normalized = hex.Trim();
            if (!normalized.StartsWith("#", StringComparison.Ordinal))
                normalized = "#" + normalized;
            if (normalized.Length == 9)
                normalized = normalized[..7];

            return string.Equals(normalized, LegacyLaneDefaultHex[laneIndex], StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>
        /// True when <paramref name="hex"/> is the colour the editor writes by position for <paramref name="laneIndex"/>
        /// (Crash, HiHat, Snare, ... order). Like the legacy defaults it says nothing about what the lane holds.
        /// </summary>
        internal static bool IsPositionalDefault(string? hex, int laneIndex)
        {
            if (IsLegacyDefault(hex, laneIndex))
                return true;

            if (string.IsNullOrWhiteSpace(hex) || laneIndex < 0)
                return false;

            string normalized = hex.Trim().TrimStart('#');
            if (normalized.Length == 8)
                normalized = normalized[..6];

            // Lanes past the canonical nine get wrapped defaults (same rule as LaneManagement's fallback colour).
            var c = ForLane(laneIndex);
            string expected = $"{(int)Math.Round(c.R * 255):X2}{(int)Math.Round(c.G * 255):X2}{(int)Math.Round(c.B * 255):X2}";
            return string.Equals(normalized, expected, StringComparison.OrdinalIgnoreCase);
        }
    }
}
