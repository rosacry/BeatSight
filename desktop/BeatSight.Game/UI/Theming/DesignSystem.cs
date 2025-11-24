using System;
using BeatSight.Game.Screens.Playback.Playfield;
using osu.Framework.Graphics;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Theming
{
    /// <summary>
    /// Comprehensive design system for BeatSight.
    /// Provides consistent spacing, typography, colors, and visual constants
    /// across all playfield views (2D, 3D, Manuscript) and UI surfaces.
    /// 
    /// Design Philosophy:
    /// - High contrast for rhythm game readability at a glance
    /// - Consistent visual language across all view modes
    /// - Support for velocity/dynamics visualization
    /// - Future-proof for articulations and advanced notation
    /// </summary>
    public static class DesignSystem
    {
        #region Spacing System (8px Grid)

        /// <summary>Base unit for all spacing calculations (8px).</summary>
        public const float SpacingUnit = 8f;

        /// <summary>Extra small spacing (4px).</summary>
        public const float SpacingXs = SpacingUnit * 0.5f;

        /// <summary>Small spacing (8px).</summary>
        public const float SpacingSm = SpacingUnit;

        /// <summary>Alias for SpacingSm.</summary>
        public const float SpacingSmall = SpacingSm;

        /// <summary>Medium spacing (16px).</summary>
        public const float SpacingMd = SpacingUnit * 2f;

        /// <summary>Large spacing (24px).</summary>
        public const float SpacingLg = SpacingUnit * 3f;

        /// <summary>Extra large spacing (32px).</summary>
        public const float SpacingXl = SpacingUnit * 4f;

        /// <summary>2XL spacing (48px).</summary>
        public const float Spacing2Xl = SpacingUnit * 6f;

        /// <summary>3XL spacing (64px).</summary>
        public const float Spacing3Xl = SpacingUnit * 8f;

        #endregion

        #region Border Radius

        /// <summary>Small border radius for buttons and small elements (4px).</summary>
        public const float RadiusSm = 4f;

        /// <summary>Medium border radius for cards and panels (8px).</summary>
        public const float RadiusMd = 8f;

        /// <summary>Large border radius for overlays and modals (12px).</summary>
        public const float RadiusLg = 12f;

        /// <summary>Extra large border radius for playfield containers (16px).</summary>
        public const float RadiusXl = 16f;

        /// <summary>Full border radius for pills and circular elements.</summary>
        public const float RadiusFull = 9999f;

        #endregion

        #region Color Palette - Core

        /// <summary>Deep background color for the main canvas.</summary>
        public static readonly Color4 ColorBackground = new Color4(8, 10, 18, 255);

        /// <summary>Elevated surface color for cards and panels.</summary>
        public static readonly Color4 ColorSurface = new Color4(18, 22, 35, 255);

        /// <summary>Higher elevated surface for overlays.</summary>
        public static readonly Color4 ColorSurfaceElevated = new Color4(28, 34, 52, 255);

        /// <summary>Subtle borders and dividers.</summary>
        public static readonly Color4 ColorBorder = new Color4(45, 55, 80, 255);

        /// <summary>Dimmed border for less emphasis.</summary>
        public static readonly Color4 ColorBorderSubtle = new Color4(35, 42, 62, 255);

        #endregion

        #region Color Palette - Text

        /// <summary>Primary text color (white).</summary>
        public static readonly Color4 ColorTextPrimary = new Color4(255, 255, 255, 255);

        /// <summary>Secondary text color for less important text.</summary>
        public static readonly Color4 ColorTextSecondary = new Color4(180, 188, 210, 255);

        /// <summary>Muted text color for hints and disabled states.</summary>
        public static readonly Color4 ColorTextMuted = new Color4(100, 110, 140, 255);

        /// <summary>Inverted text for use on light backgrounds.</summary>
        public static readonly Color4 ColorTextInverted = new Color4(20, 25, 40, 255);

        #endregion

        #region Color Palette - Accents

        /// <summary>Primary accent - cyan neon for highlights and focus.</summary>
        public static readonly Color4 ColorAccentPrimary = new Color4(0, 210, 255, 255);

        /// <summary>Alias for primary accent.</summary>
        public static readonly Color4 ColorAccent = ColorAccentPrimary;

        /// <summary>Secondary accent - magenta for secondary actions.</summary>
        public static readonly Color4 ColorAccentSecondary = new Color4(255, 50, 150, 255);

        /// <summary>Success color - green for positive feedback.</summary>
        public static readonly Color4 ColorSuccess = new Color4(0, 255, 140, 255);

        /// <summary>Warning color - orange for caution states.</summary>
        public static readonly Color4 ColorWarning = new Color4(255, 180, 0, 255);

        /// <summary>Error color - red for negative feedback.</summary>
        public static readonly Color4 ColorError = new Color4(255, 70, 70, 255);

        /// <summary>Early timing indicator color - blue tint.</summary>
        public static readonly Color4 ColorEarly = new Color4(100, 160, 255, 255);

        /// <summary>Late timing indicator color - orange tint.</summary>
        public static readonly Color4 ColorLate = new Color4(255, 160, 80, 255);

        #endregion

        #region Color Palette - Drum Components

        /// <summary>Kick drum color - deep purple/violet.</summary>
        public static readonly Color4 ColorKick = new Color4(180, 130, 255, 255);

        /// <summary>Snare drum color - electric blue.</summary>
        public static readonly Color4 ColorSnare = new Color4(70, 160, 255, 255);

        /// <summary>Hi-hat color - golden yellow.</summary>
        public static readonly Color4 ColorHiHat = new Color4(255, 210, 70, 255);

        /// <summary>Open hi-hat color - brighter gold.</summary>
        public static readonly Color4 ColorHiHatOpen = new Color4(255, 185, 0, 255);

        /// <summary>High tom color - lime green.</summary>
        public static readonly Color4 ColorTomHigh = new Color4(140, 220, 50, 255);

        /// <summary>Mid tom color - teal.</summary>
        public static readonly Color4 ColorTomMid = new Color4(80, 210, 235, 255);

        /// <summary>Low tom color - indigo.</summary>
        public static readonly Color4 ColorTomLow = new Color4(130, 140, 255, 255);

        /// <summary>Crash cymbal color - hot pink.</summary>
        public static readonly Color4 ColorCrash = new Color4(255, 120, 200, 255);

        /// <summary>Ride cymbal color - warm coral.</summary>
        public static readonly Color4 ColorRide = new Color4(255, 160, 140, 255);

        /// <summary>China cymbal color - amber.</summary>
        public static readonly Color4 ColorChina = new Color4(255, 195, 80, 255);

        /// <summary>Default/unknown component color.</summary>
        public static readonly Color4 ColorComponentDefault = new Color4(160, 165, 185, 255);

        /// <summary>
        /// Get the color for a drum component by name.
        /// </summary>
        public static Color4 GetComponentColor(string component)
        {
            if (string.IsNullOrEmpty(component))
                return ColorComponentDefault;

            string lower = component.ToLowerInvariant();

            if (lower.Contains("kick"))
                return ColorKick;
            if (lower.Contains("snare") || lower.Contains("rim") || lower.Contains("cross"))
                return ColorSnare;
            if (lower.Contains("hihat_open") || lower.Contains("hi-hat_open"))
                return ColorHiHatOpen;
            if (lower.Contains("hihat") || lower.Contains("hi-hat"))
                return ColorHiHat;
            if (lower.Contains("tom_high") || lower.Contains("tom high"))
                return ColorTomHigh;
            if (lower.Contains("tom_mid") || lower.Contains("tom mid"))
                return ColorTomMid;
            if (lower.Contains("tom_low") || lower.Contains("tom low") || lower.Contains("floor"))
                return ColorTomLow;
            if (lower.Contains("crash"))
                return ColorCrash;
            if (lower.Contains("ride"))
                return ColorRide;
            if (lower.Contains("china") || lower.Contains("splash"))
                return ColorChina;

            return ColorComponentDefault;
        }

        #endregion

        #region Color Palette - Hit Judgments

        /// <summary>Perfect hit color - bright cyan.</summary>
        public static readonly Color4 ColorJudgmentPerfect = new Color4(0, 255, 220, 255);

        /// <summary>Great hit color - green.</summary>
        public static readonly Color4 ColorJudgmentGreat = new Color4(100, 255, 100, 255);

        /// <summary>Good hit color - yellow.</summary>
        public static readonly Color4 ColorJudgmentGood = new Color4(255, 220, 80, 255);

        /// <summary>Meh hit color - orange.</summary>
        public static readonly Color4 ColorJudgmentMeh = new Color4(255, 150, 50, 255);

        /// <summary>Miss color - red.</summary>
        public static readonly Color4 ColorJudgmentMiss = new Color4(255, 80, 80, 255);

        #endregion

        #region Playfield Visual Constants

        /// <summary>Default hit line position as ratio of playfield height (0 = top, 1 = bottom).</summary>
        public const float DefaultHitLineRatio = 0.92f;

        /// <summary>3D view hit line position (slightly higher for perspective).</summary>
        public const float HitLineRatio3D = 0.88f;

        /// <summary>Manuscript view hit line position.</summary>
        public const float HitLineRatioManuscript = 0.85f;

        /// <summary>Default note width as ratio of lane width.</summary>
        public const float NoteWidthRatio = 0.75f;

        /// <summary>Maximum note width as ratio of lane width.</summary>
        public const float NoteWidthMaxRatio = 0.90f;

        /// <summary>Lane separator width in pixels.</summary>
        public const float LaneSeparatorWidth = 2f;

        /// <summary>Lane separator opacity (0-1).</summary>
        public const float LaneSeparatorOpacity = 0.15f;

        /// <summary>Strike zone height in pixels for 2D mode.</summary>
        public const float StrikeZoneHeight2D = 24f;

        /// <summary>Strike zone height in pixels for 3D mode.</summary>
        public const float StrikeZoneHeight3D = 32f;

        /// <summary>Strike zone height in pixels for manuscript mode.</summary>
        public const float StrikeZoneHeightManuscript = 8f;

        /// <summary>Default strike zone height (alias for 2D).</summary>
        public const float StrikeZoneHeight = StrikeZoneHeight2D;

        /// <summary>Strike zone border color.</summary>
        public static readonly Color4 ColorStrikeZoneBorder = new Color4(100, 110, 140, 180);

        /// <summary>Strike zone fill color.</summary>
        public static readonly Color4 ColorStrikeZoneFill = new Color4(40, 45, 65, 120);

        /// <summary>Manuscript playhead/timeline color.</summary>
        public static readonly Color4 ColorManuscriptPlayhead = new Color4(80, 100, 180, 200);

        #endregion

        #region 3D Perspective Constants

        /// <summary>Vanishing point Y position as ratio (0 = top).</summary>
        public const float VanishingPointRatio = 0.12f;

        /// <summary>Highway width at bottom (hit line) as ratio of screen width.</summary>
        public const float HighwayWidthBottom = 0.88f;

        /// <summary>Highway width at top (vanishing point) as ratio of bottom width.</summary>
        public const float HighwayWidthTopRatio = 0.32f;

        /// <summary>Minimum note scale at vanishing point.</summary>
        public const float MinNoteScale3D = 0.28f;

        /// <summary>Maximum note scale at hit line.</summary>
        public const float MaxNoteScale3D = 1.0f;

        #endregion

        #region Manuscript Constants

        /// <summary>Staff line spacing in pixels.</summary>
        public const float StaffLineSpacing = 10f;

        /// <summary>Number of staff lines.</summary>
        public const int StaffLineCount = 5;

        /// <summary>Staff width as ratio of screen width.</summary>
        public const float StaffWidthRatio = 0.55f;

        /// <summary>Ledger line opacity.</summary>
        public const float LedgerLineOpacity = 0.5f;

        /// <summary>Paper background color (warm off-white).</summary>
        public static readonly Color4 ColorPaper = new Color4(250, 248, 240, 255);

        /// <summary>Staff ink color (near black).</summary>
        public static readonly Color4 ColorInk = new Color4(35, 35, 40, 255);

        /// <summary>Playhead line color for manuscript.</summary>
        public static readonly Color4 ColorPlayhead = new Color4(200, 60, 60, 200);

        #endregion

        #region Timing Grid Constants

        /// <summary>Measure line thickness.</summary>
        public const float MeasureLineThickness = 5f;

        /// <summary>Beat line thickness.</summary>
        public const float BeatLineThickness = 2.5f;

        /// <summary>Subdivision line thickness.</summary>
        public const float SubdivisionLineThickness = 1.5f;

        /// <summary>Measure line color.</summary>
        public static readonly Color4 ColorMeasureLine = new Color4(255, 210, 170, 230);

        /// <summary>Beat line color.</summary>
        public static readonly Color4 ColorBeatLine = new Color4(170, 195, 255, 200);

        /// <summary>Subdivision line color.</summary>
        public static readonly Color4 ColorSubdivisionLine = new Color4(110, 125, 170, 150);

        #endregion

        #region Animation Durations

        /// <summary>Quick micro-animation (100ms).</summary>
        public const double AnimationQuick = 100;

        /// <summary>Fast animation (200ms).</summary>
        public const double AnimationFast = 200;

        /// <summary>Normal animation (300ms).</summary>
        public const double AnimationNormal = 300;

        /// <summary>Slow animation (400ms).</summary>
        public const double AnimationSlow = 400;

        /// <summary>Very slow animation for major transitions (600ms).</summary>
        public const double AnimationVerySlow = 600;

        #endregion

        #region Hit Windows (milliseconds)

        /// <summary>Perfect hit window radius (±35ms).</summary>
        public const double HitWindowPerfect = 35;

        /// <summary>Great hit window radius (±80ms).</summary>
        public const double HitWindowGreat = 80;

        /// <summary>Good hit window radius (±130ms).</summary>
        public const double HitWindowGood = 130;

        /// <summary>Meh hit window radius (±180ms).</summary>
        public const double HitWindowMeh = 180;

        /// <summary>Miss window radius (±220ms).</summary>
        public const double HitWindowMiss = 220;

        #endregion

        #region Velocity/Dynamics Visualization

        /// <summary>Ghost note velocity threshold (below this is a ghost note).</summary>
        public const double GhostNoteThreshold = 0.35;

        /// <summary>Accent note velocity threshold (above this is an accent).</summary>
        public const double AccentNoteThreshold = 0.85;

        /// <summary>Minimum alpha for ghost notes.</summary>
        public const float GhostNoteMinAlpha = 0.45f;

        /// <summary>Calculate note alpha based on velocity (0-1).</summary>
        public static float GetVelocityAlpha(double velocity)
        {
            float v = (float)Math.Clamp(velocity, 0, 1);
            // Ghost notes: 0.0 velocity -> 0.45 alpha
            // Normal notes: 0.5 velocity -> 0.72 alpha
            // Accent notes: 1.0 velocity -> 1.0 alpha
            return GhostNoteMinAlpha + (1f - GhostNoteMinAlpha) * v;
        }

        /// <summary>Calculate note size multiplier based on velocity.</summary>
        public static float GetVelocityScale(double velocity)
        {
            float v = (float)Math.Clamp(velocity, 0, 1);
            // Ghost notes: slightly smaller (0.85x)
            // Normal notes: 1.0x
            // Accent notes: slightly larger (1.1x)
            if (v < GhostNoteThreshold)
                return 0.85f + 0.15f * (v / (float)GhostNoteThreshold);
            if (v > AccentNoteThreshold)
                return 1.0f + 0.1f * ((v - (float)AccentNoteThreshold) / (1f - (float)AccentNoteThreshold));
            return 1.0f;
        }

        #endregion

        #region Utility Methods

        /// <summary>
        /// Blend two colors together.
        /// </summary>
        public static Color4 Blend(Color4 a, Color4 b, float t)
        {
            t = Math.Clamp(t, 0f, 1f);
            return new Color4(
                a.R + (b.R - a.R) * t,
                a.G + (b.G - a.G) * t,
                a.B + (b.B - a.B) * t,
                a.A + (b.A - a.A) * t
            );
        }

        /// <summary>
        /// Adjust color brightness.
        /// </summary>
        public static Color4 Brighten(Color4 color, float factor)
        {
            return new Color4(
                Math.Clamp(color.R * factor, 0f, 1f),
                Math.Clamp(color.G * factor, 0f, 1f),
                Math.Clamp(color.B * factor, 0f, 1f),
                color.A
            );
        }

        /// <summary>
        /// Set color opacity while preserving RGB.
        /// </summary>
        public static Color4 WithOpacity(Color4 color, float opacity)
        {
            return new Color4(color.R, color.G, color.B, Math.Clamp(opacity, 0f, 1f));
        }

        /// <summary>
        /// Linear interpolation helper.
        /// </summary>
        public static float Lerp(float a, float b, float t)
        {
            return a + (b - a) * Math.Clamp(t, 0f, 1f);
        }

        /// <summary>
        /// Smooth step interpolation (ease in-out).
        /// </summary>
        public static float SmoothStep(float t)
        {
            t = Math.Clamp(t, 0f, 1f);
            return t * t * (3f - 2f * t);
        }

        /// <summary>
        /// Perspective-aware interpolation for 3D view.
        /// Creates more realistic depth perception.
        /// </summary>
        public static float PerspectiveLerp(float t)
        {
            t = Math.Clamp(t, 0f, 1f);
            // Quadratic ease-in for natural perspective acceleration
            return t * t * (3f - 2f * t);
        }

        #endregion

        #region Additional Constants for NoteRenderer

        /// <summary>Alias for RadiusSm for smaller elements.</summary>
        public const float RadiusSmall = RadiusSm;

        /// <summary>Default note width for 2D mode.</summary>
        public const float NoteWidth2D = 60f;

        /// <summary>Default note height for 2D mode.</summary>
        public const float NoteHeight2D = 20f;

        /// <summary>Default note width for 3D mode.</summary>
        public const float NoteWidth3D = 55f;

        /// <summary>Default note height for 3D mode.</summary>
        public const float NoteHeight3D = 22f;

        /// <summary>Note corner radius for 3D mode.</summary>
        public const float NoteCornerRadius3D = 10f;

        /// <summary>Note size for manuscript view (circular notes).</summary>
        public const float ManuscriptNoteSize = 20f;

        /// <summary>Shear value for 3D highway perspective.</summary>
        public const float HighwayShear = -0.24f;

        /// <summary>Width factor for 3D highway (relative to container).</summary>
        public const float HighwayWidthFactor = 0.72f;

        /// <summary>Alias for ColorJudgmentMiss.</summary>
        public static readonly Color4 ColorMiss = ColorJudgmentMiss;

        /// <summary>Alias for AnimationNormal.</summary>
        public const double AnimationMedium = AnimationNormal;

        /// <summary>
        /// Get the judgment color for a hit result.
        /// </summary>
        public static Color4 GetJudgmentColor(HitResult result)
        {
            return result switch
            {
                HitResult.Perfect => ColorJudgmentPerfect,
                HitResult.Great => ColorJudgmentGreat,
                HitResult.Good => ColorJudgmentGood,
                HitResult.Meh => ColorJudgmentMeh,
                HitResult.Miss => ColorJudgmentMiss,
                _ => ColorComponentDefault,
            };
        }

        #endregion
    }
}
