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
        public static readonly Color4 ScreenBackground = UITheme.Background;
        public static readonly Color4 ScreenBackdropTop = new Color4(24, 30, 42, 90);
        public static readonly Color4 ScreenBackdropBottom = new Color4(11, 14, 20, 130);
        public static readonly Color4 ScreenHeaderGlow = new Color4(56, 196, 236, 18);
        public static readonly Color4 HeaderBackground = UITheme.BackgroundLayer.Opacity(0.96f);
        public static readonly Color4 ControlsBackground = UITheme.Surface.Opacity(0.96f);
        public static readonly Color4 TimelineBackground = new Color4(14, 18, 26, 250);
        public static readonly Color4 TimelineToolbarBackground = UITheme.Surface.Opacity(0.94f);
        public static readonly Color4 PreviewBackground = UITheme.BackgroundLayer.Opacity(0.96f);
        public static readonly Color4 WorkspaceBackground = UITheme.BackgroundLayer.Opacity(0.96f);
        public static readonly Color4 FooterBackground = UITheme.BackgroundLayer.Opacity(0.98f);
        public static readonly Color4 InspectorBackground = UITheme.BackgroundLayer.Opacity(0.96f);
        public static readonly Color4 SectionBackground = UITheme.Surface.Opacity(0.92f);
        public static readonly Color4 CardBackground = UITheme.SurfaceAlt.Opacity(0.85f);
        public static readonly Color4 HistoryBackground = UITheme.Surface.Opacity(0.9f);
        public static readonly Color4 PanelStroke = new Color4(255, 255, 255, 20);
        public static readonly Color4 Divider = UITheme.Divider;

        // Timeline rendering
        public static readonly Color4 TimelineRowLine = new Color4(255, 255, 255, 22);
        public static readonly Color4 TimelineRowFill = new Color4(255, 255, 255, 5);
        public static readonly Color4 TimelineLabelBackground = UITheme.SurfaceAlt;
        public static readonly Color4 TimelineLabelText = UITheme.TextPrimary;
        public static readonly Color4 TimelineSelection = UITheme.AccentPrimary.Opacity(0.22f);
        public static readonly Color4 TimelinePlayhead = new Color4(245, 248, 255, 255);
        public static readonly Color4 TimelineWaveform = new Color4(168, 178, 197, 120);
        public static readonly Color4 TimelineWaveformShadow = new Color4(80, 90, 110, 90);
        public static readonly Color4 HistoryEntryEmphasis = new Color4(237, 245, 255, 255);
        public static readonly Color4 HistoryEntryMuted = new Color4(183, 198, 224, 255);

        // Accent colours for interactive elements
        public static Color4 AccentPlay => UITheme.AccentPrimary;
        public static Color4 AccentSave => UITheme.AccentSuccess;
        public static Color4 AccentUndo => UITheme.SurfaceRaised;
        public static Color4 AccentRedo => UITheme.SurfaceRaised;
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

        /// <summary>
        /// Linearly mixes two colours.
        /// </summary>
        public static Color4 Mix(Color4 first, Color4 second, float amount) => UITheme.Mix(first, second, amount);
    }
}
