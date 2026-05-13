using BeatSight.Game.UI.Theming;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    /// <summary>
    /// Editor-specific colour palette derived from the main UI theme.
    /// Provides consistent colours across all editor components.
    /// </summary>
    internal static class EditorColours
    {
        // Screen + panel backgrounds
        public static readonly Color4 ScreenBackground = new Color4(11, 17, 30, 255);
        public static readonly Color4 ScreenBackdropTop = new Color4(40, 63, 108, 104);
        public static readonly Color4 ScreenBackdropBottom = new Color4(16, 24, 42, 130);
        public static readonly Color4 ScreenHeaderGlow = new Color4(84, 136, 230, 50);
        public static readonly Color4 HeaderBackground = new Color4(18, 25, 44, 245);
        public static readonly Color4 ControlsBackground = new Color4(22, 31, 54, 245);
        public static readonly Color4 TimelineBackground = new Color4(15, 23, 41, 245);
        public static readonly Color4 TimelineToolbarBackground = new Color4(20, 28, 49, 240);
        public static readonly Color4 PreviewBackground = new Color4(17, 25, 44, 245);
        public static readonly Color4 WorkspaceBackground = new Color4(15, 22, 39, 245);
        public static readonly Color4 FooterBackground = new Color4(13, 20, 36, 250);
        public static readonly Color4 InspectorBackground = new Color4(17, 24, 43, 245);
        public static readonly Color4 SectionBackground = new Color4(26, 35, 58, 230);
        public static readonly Color4 CardBackground = new Color4(28, 38, 63, 205);
        public static readonly Color4 HistoryBackground = new Color4(24, 32, 56, 220);
        public static readonly Color4 PanelStroke = new Color4(145, 180, 255, 56);
        public static readonly Color4 Divider = new Color4(122, 150, 198, 88);

        // Timeline rendering
        public static readonly Color4 TimelineRowLine = new Color4(118, 142, 190, 96);
        public static readonly Color4 TimelineRowFill = new Color4(26, 38, 64, 120);
        public static readonly Color4 TimelineLabelBackground = new Color4(34, 47, 78, 220);
        public static readonly Color4 TimelineLabelText = new Color4(218, 229, 255, 255);
        public static readonly Color4 TimelineSelection = UITheme.AccentPrimary.Opacity(0.22f);
        public static readonly Color4 TimelinePlayhead = new Color4(245, 248, 255, 255);
        public static readonly Color4 TimelineWaveform = new Color4(120, 188, 255, 176);
        public static readonly Color4 TimelineWaveformShadow = new Color4(52, 98, 165, 120);
        public static readonly Color4 HistoryEntryEmphasis = new Color4(237, 245, 255, 255);
        public static readonly Color4 HistoryEntryMuted = new Color4(183, 198, 224, 255);

        // Accent colours for interactive elements
        public static Color4 AccentPlay => UITheme.AccentSecondary;
        public static Color4 AccentSave => UITheme.AccentPrimary;
        public static Color4 AccentUndo => new Color4(95, 124, 180, 255);
        public static Color4 AccentRedo => new Color4(95, 124, 180, 255);
        public static Color4 Warning => UITheme.AccentWarning;

        // Text colours
        public static Color4 TextPrimary => UITheme.TextPrimary;
        public static Color4 TextSecondary => new Color4(206, 218, 242, 255);
        public static Color4 TextMuted => new Color4(130, 150, 188, 255);

        /// <summary>
        /// Lighten a colour by a factor (1.0 = unchanged, >1 = lighter).
        /// </summary>
        public static Color4 Lighten(Color4 colour, float factor) => UITheme.Emphasise(colour, factor);

        /// <summary>
        /// Apply alpha multiplier to a colour.
        /// </summary>
        public static Color4 WithAlpha(Color4 colour, float alpha) => new Color4(colour.R, colour.G, colour.B, colour.A * alpha);

        /// <summary>
        /// Linearly mixes two colours.
        /// </summary>
        public static Color4 Mix(Color4 first, Color4 second, float amount) => UITheme.Mix(first, second, amount);
    }
}
