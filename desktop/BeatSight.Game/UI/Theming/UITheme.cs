using System;
using osu.Framework.Graphics;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Theming
{
    /// <summary>
    /// Centralised colour palette and spacing helpers for BeatSight screens.
    /// </summary>
    public static class UITheme
    {
        // 2026-10-24 direction: calm slate neutrals, one cyan accent, and instrument colours (DrumPalette) as the
        // only high-chroma colours on screen. The chrome recedes so notes carry the meaning.
        public static readonly Color4 Background = new Color4(11, 14, 20, 255); // App canvas
        public static readonly Color4 BackgroundLayer = new Color4(16, 20, 28, 255); // Headers, sidebars
        public static readonly Color4 Surface = new Color4(24, 29, 40, 255); // Cards, rows
        public static readonly Color4 SurfaceAlt = new Color4(31, 38, 52, 255); // Controls, raised rows
        public static readonly Color4 SurfaceRaised = new Color4(41, 49, 66, 255); // Hover / pressed controls
        public static readonly Color4 Border = new Color4(48, 57, 76, 255);

        public static readonly Color4 AccentPrimary = new Color4(56, 196, 236, 255); // Primary actions, focus, progress
        public static readonly Color4 AccentSecondary = new Color4(150, 140, 255, 255); // Rare secondary emphasis
        public static readonly Color4 AccentWarning = new Color4(245, 184, 65, 255);
        public static readonly Color4 AccentSuccess = new Color4(61, 214, 140, 255);
        public static readonly Color4 AccentError = new Color4(242, 85, 90, 255); // Destructive actions only

        public static readonly Color4 TextPrimary = new Color4(236, 240, 247, 255);
        public static readonly Color4 TextSecondary = new Color4(168, 178, 197, 255);
        public static readonly Color4 TextMuted = new Color4(112, 122, 145, 255);
        public static readonly Color4 TextOnAccent = new Color4(8, 22, 30, 255);

        public static readonly Color4 Divider = new Color4(255, 255, 255, 22);
        public static readonly Color4 Overlay = new Color4(4, 6, 10, 170); // Dark overlay for modals

        // Type scale (logical pixels at 1080p, before BeatSightFont's 1.2x family scaling is applied by callers
        // that use the semantic helpers). Use these instead of ad-hoc sizes.
        public const float TypeDisplay = 44f;
        public const float TypeTitle = 26f;
        public const float TypeHeading = 19f;
        public const float TypeBody = 15f;
        public const float TypeLabel = 13f;
        public const float TypeCaption = 11.5f;

        // Motion: short, decelerating, never elastic. Gameplay feedback stays inside its lane.
        public const double MotionFast = 120;
        public const double MotionNormal = 220;
        public const double MotionSlow = 360;
        public const Easing MotionEasing = Easing.OutQuint;
        public const float HoverScale = 1.02f;
        public const float PressScale = 0.97f;

        // Layout Constants
        public const float MainLogoTitleSize = 80f;
        public const float MainLogoSubtitleSize = 24f;
        public const float MainLogoSubtitleY = 60f; // Distance from center to subtitle

        public static readonly Color4 KickGlobalFill = new Color4(255, 148, 64, 100); // DrumPalette.Kick
        public static readonly Color4 KickGlobalGlow = new Color4(255, 148, 64, 200);

        public static readonly MarginPadding ScreenPadding = new MarginPadding { Horizontal = 50, Vertical = 40 };

        private static readonly Color4[] lanePalette =
        {
            new Color4(36, 42, 68, 255),
            new Color4(44, 54, 84, 255),
            new Color4(56, 64, 96, 255),
            new Color4(50, 58, 90, 255),
            new Color4(40, 62, 94, 255),
            new Color4(34, 48, 78, 255)
        };

        private static readonly Color4[] laneEdgePalette =
        {
            new Color4(70, 82, 118, 200),
            new Color4(62, 76, 126, 200),
            new Color4(54, 88, 136, 200),
            new Color4(68, 78, 130, 200),
            new Color4(62, 88, 140, 200),
            new Color4(58, 72, 122, 200)
        };

        public static Color4 GetLaneColour(int displayIndex, int laneCount = 0)
        {
            if (laneCount <= 0)
                laneCount = lanePalette.Length;

            int paletteIndex = (displayIndex + lanePalette.Length) % lanePalette.Length;
            int offset = laneCount % lanePalette.Length;
            paletteIndex = (paletteIndex + offset) % lanePalette.Length;

            return lanePalette[paletteIndex];
        }

        public static Color4 GetLaneColourForLogicalIndex(int logicalLaneIndex, int totalLaneCount)
        {
            if (totalLaneCount <= 0)
                totalLaneCount = lanePalette.Length;

            int paletteIndex = modulo(logicalLaneIndex, lanePalette.Length);
            int offset = totalLaneCount % lanePalette.Length;
            paletteIndex = (paletteIndex + offset) % lanePalette.Length;
            return lanePalette[paletteIndex];
        }

        public static Color4 GetLaneEdgeColour(int displayIndex, int laneCount = 0)
        {
            if (laneCount <= 0)
                laneCount = laneEdgePalette.Length;

            int paletteIndex = (displayIndex + laneEdgePalette.Length) % laneEdgePalette.Length;
            int offset = (laneCount * 2) % laneEdgePalette.Length;
            paletteIndex = (paletteIndex + offset) % laneEdgePalette.Length;

            return laneEdgePalette[paletteIndex];
        }

        public static Color4 GetLaneEdgeColourForLogicalIndex(int logicalLaneIndex, int totalLaneCount)
        {
            if (totalLaneCount <= 0)
                totalLaneCount = laneEdgePalette.Length;

            int paletteIndex = modulo(logicalLaneIndex, laneEdgePalette.Length);
            int offset = (totalLaneCount * 2) % laneEdgePalette.Length;
            paletteIndex = (paletteIndex + offset) % laneEdgePalette.Length;
            return laneEdgePalette[paletteIndex];
        }

        public static Color4 Emphasise(Color4 baseColour, float factor)
        {
            float r = (float)System.Math.Clamp(baseColour.R * factor, 0f, 1f);
            float g = (float)System.Math.Clamp(baseColour.G * factor, 0f, 1f);
            float b = (float)System.Math.Clamp(baseColour.B * factor, 0f, 1f);
            return new Color4(r, g, b, baseColour.A);
        }

        public static Color4 Opacity(this Color4 baseColour, float alpha)
        {
            return new Color4(baseColour.R, baseColour.G, baseColour.B, baseColour.A * alpha);
        }

        public static Color4 Mix(Color4 first, Color4 second, float amount)
        {
            amount = (float)Math.Clamp(amount, 0f, 1f);
            float inverse = 1f - amount;
            return new Color4(
                first.R * inverse + second.R * amount,
                first.G * inverse + second.G * amount,
                first.B * inverse + second.B * amount,
                first.A * inverse + second.A * amount);
        }

        private static int modulo(int value, int modulus)
        {
            if (modulus <= 0)
                return 0;

            int result = value % modulus;
            return result < 0 ? result + modulus : result;
        }
    }
}
