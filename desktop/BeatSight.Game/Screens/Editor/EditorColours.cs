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
        // Background colours
        public static readonly Color4 ScreenBackground = UITheme.Background;
        public static readonly Color4 HeaderBackground = UITheme.Surface;
        public static readonly Color4 ControlsBackground = UITheme.SurfaceAlt;
        public static readonly Color4 TimelineBackground = UITheme.Surface;
        public static readonly Color4 TimelineToolbarBackground = UITheme.SurfaceAlt;
        public static readonly Color4 PreviewBackground = UITheme.BackgroundLayer;
        public static readonly Color4 HistoryBackground = UITheme.SurfaceAlt.Opacity(0.8f);
        public static readonly Color4 Divider = UITheme.Divider;

        // Accent colours for interactive elements
        public static Color4 AccentPlay => UITheme.AccentSecondary;
        public static Color4 AccentSave => UITheme.AccentPrimary;
        public static Color4 AccentUndo => UITheme.SurfaceAlt;
        public static Color4 AccentRedo => UITheme.SurfaceAlt;
        public static Color4 Warning => UITheme.AccentWarning;

        // Text colours
        public static Color4 TextPrimary => UITheme.TextPrimary;
        public static Color4 TextSecondary => UITheme.TextSecondary;
        public static Color4 TextMuted => UITheme.TextMuted;

        /// <summary>
        /// Lighten a colour by a factor (1.0 = unchanged, >1 = lighter).
        /// </summary>
        public static Color4 Lighten(Color4 colour, float factor) => UITheme.Emphasise(colour, factor);

        /// <summary>
        /// Apply alpha multiplier to a colour.
        /// </summary>
        public static Color4 WithAlpha(Color4 colour, float alpha) => new Color4(colour.R, colour.G, colour.B, colour.A * alpha);
    }
}
