using System;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// Redesigned 2D lane view renderer (osu!mania / StepMania style).
    /// 
    /// Key improvements over original:
    /// - Cleaner lane separation with subtle gradients
    /// - Better note sizing and spacing
    /// - Improved hit zone visualization
    /// - Support for velocity/dynamics display
    /// - Consistent design system integration
    /// 
    /// Notes fall vertically down distinct lanes with clear column separation,
    /// optimized for readability and precise timing visualization.
    /// </summary>
    public class TwoDimensionalLaneViewEnhanced : PlayfieldViewBaseEnhanced
    {
        public override Configuration.LaneViewMode ViewMode => Configuration.LaneViewMode.TwoDimensional;

        // Position constants from design system
        public override float HitLineYRatio => DesignSystem.DefaultHitLineRatio;
        public override float SpawnYRatio => 0f;

        // Local visual constants
        private const float LaneGradientStrength = 0.08f;
        private const float EdgeGlowIntensity = 0.15f;

        // Lane background colors (alternating for visual distinction)
        private static readonly Color4 LaneDark = new Color4(14, 18, 28, 255);
        private static readonly Color4 LaneLight = new Color4(20, 26, 38, 255);

        #region Background Creation

        public override Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick)
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            int visibleLanes = useGlobalKick ? Math.Max(1, laneCount - 1) : laneCount;
            float laneWidthRatio = 1f / visibleLanes;

            // Base gradient background
            container.Add(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    DesignSystem.ColorBackground,
                    DesignSystem.ColorSurface)
            });

            // Alternating lane backgrounds
            for (int i = 0; i < visibleLanes; i++)
            {
                bool isAlternate = i % 2 == 0;
                var baseColor = isAlternate ? LaneDark : LaneLight;

                // Subtle vertical gradient for depth
                var topColor = DesignSystem.Brighten(baseColor, 0.85f);
                var bottomColor = DesignSystem.Brighten(baseColor, 1.1f);

                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.X,
                    Width = laneWidthRatio,
                    X = i * laneWidthRatio,
                    Colour = ColourInfo.GradientVertical(topColor, bottomColor)
                });
            }

            // Lane dividers
            AddLaneDividers(container, visibleLanes, laneWidthRatio);

            // Edge highlights (left and right borders)
            AddEdgeHighlights(container);

            // Kick zone indicator (if global kick is enabled)
            if (useGlobalKick)
            {
                AddKickZoneIndicator(container);
            }

            return container;
        }

        private void AddLaneDividers(Container container, int visibleLanes, float laneWidthRatio)
        {
            for (int i = 1; i < visibleLanes; i++)
            {
                // Main separator line
                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = DesignSystem.LaneSeparatorWidth,
                    RelativePositionAxes = Axes.X,
                    X = i * laneWidthRatio,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorBorder, DesignSystem.LaneSeparatorOpacity)
                });

                // Subtle glow on each side
                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 8,
                    RelativePositionAxes = Axes.X,
                    X = i * laneWidthRatio,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorAccentPrimary, 0.03f),
                    Blending = BlendingParameters.Additive
                });
            }
        }

        private void AddEdgeHighlights(Container container)
        {
            // Left edge
            container.Add(new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 3,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Colour = ColourInfo.GradientVertical(
                    DesignSystem.WithOpacity(DesignSystem.ColorAccentPrimary, 0.1f),
                    DesignSystem.WithOpacity(DesignSystem.ColorAccentPrimary, 0.25f))
            });

            // Right edge
            container.Add(new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 3,
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Colour = ColourInfo.GradientVertical(
                    DesignSystem.WithOpacity(DesignSystem.ColorAccentPrimary, 0.1f),
                    DesignSystem.WithOpacity(DesignSystem.ColorAccentPrimary, 0.25f))
            });
        }

        private void AddKickZoneIndicator(Container container)
        {
            // Subtle bottom indicator for kick zone
            container.Add(new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 2,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                Y = -DesignSystem.StrikeZoneHeight2D - 4,
                Colour = DesignSystem.WithOpacity(DesignSystem.ColorKick, 0.4f)
            });
        }

        #endregion

        #region Strike Zone Creation

        public override Drawable CreateStrikeZone()
        {
            return new TwoDimensionalStrikeZoneEnhanced();
        }

        #endregion

        #region Note Position Updates

        public override void UpdateNotePosition(
            DrawableNote note,
            float progress,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            NotePositionContext ctx)
        {
            // Calculate Y position based on progress
            float y = CalculateY(progress, hitLineY, travelDistance);

            if (ctx.UseGlobalKickLine && note.IsKick)
            {
                UpdateKickNotePosition(note, y, drawWidth, drawHeight, hitLineY);
            }
            else
            {
                UpdateLaneNotePosition(note, y, drawWidth, ctx);
            }

            // Set visibility based on position
            note.Alpha = IsNoteVisible(y, hitLineY, note.Height) ? 1 : 0;
        }

        private void UpdateKickNotePosition(DrawableNote note, float y, float drawWidth, float drawHeight, float hitLineY)
        {
            // Kick notes span the full width as a horizontal bar
            float kickNoteHeight = Math.Clamp(drawHeight * 0.022f, 10f, 22f);

            note.Width = drawWidth * 0.98f; // Slight margin
            note.Height = kickNoteHeight;
            note.Position = new Vector2(drawWidth / 2, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;

            // Apply kick-specific styling
            note.ApplyKickLineDimensions(note.Width, kickNoteHeight, ViewMode);
        }

        private void UpdateLaneNotePosition(DrawableNote note, float y, float drawWidth, NotePositionContext ctx)
        {
            float laneWidth = drawWidth / ctx.VisibleLaneCount;
            int visualLaneIndex = GetVisualLaneIndex(note.Lane, ctx);

            // Calculate note width based on user preference
            float userScale = (float)(Context?.NoteWidthScale?.Value ?? 1.0);
            note.Width = CalculateNoteWidth(laneWidth, userScale);

            // Center note in lane
            float x = CalculateLaneX(visualLaneIndex, drawWidth, ctx.VisibleLaneCount);

            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;
        }

        public override void ApplyNoteStyle(DrawableNote note)
        {
            note.SetViewMode(Configuration.LaneViewMode.TwoDimensional);
        }

        #endregion
    }

    /// <summary>
    /// Enhanced strike zone visual for 2D lane view.
    /// Features cleaner design with better visual hierarchy.
    /// </summary>
    internal partial class TwoDimensionalStrikeZoneEnhanced : CompositeDrawable
    {
        private readonly Container body;
        private readonly Box fill;
        private readonly Box glowTop;
        private readonly Box glowBottom;
        private readonly Box hitLine;

        public TwoDimensionalStrikeZoneEnhanced()
        {
            RelativeSizeAxes = Axes.X;
            Height = DesignSystem.StrikeZoneHeight2D;
            Width = 0.995f;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;

            // Main container with masking and corner radius
            body = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = DesignSystem.RadiusMd,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorAccentPrimary, 0.15f),
                    Radius = 8,
                    Roundness = 4
                }
            };

            // Fill color
            fill = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    new Color4(45, 60, 120, 140),
                    new Color4(35, 50, 100, 160))
            };

            // Top glow line (main hit indicator)
            glowTop = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 3,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = DesignSystem.ColorAccentPrimary
            };

            // Subtle bottom accent
            glowBottom = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 1.5f,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                Colour = DesignSystem.WithOpacity(DesignSystem.ColorTextPrimary, 0.2f)
            };

            // Center hit line (for precise timing reference)
            hitLine = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 1,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Y = -2,
                Colour = DesignSystem.WithOpacity(DesignSystem.ColorTextPrimary, 0.15f)
            };

            body.AddRange(new Drawable[]
            {
                fill,
                glowTop,
                glowBottom,
                hitLine
            });

            InternalChild = body;
        }

        /// <summary>
        /// Update the strike zone geometry based on current playfield dimensions.
        /// </summary>
        public void UpdateGeometry(float drawHeight, float hitLineY)
        {
            float offset = Math.Max(0, drawHeight - hitLineY - Height / 2f);
            Y = -offset;
        }

        /// <summary>
        /// Pulse the glow when a note is hit (for visual feedback).
        /// </summary>
        public void PulseHit(Color4 color)
        {
            glowTop.Colour = color;
            glowTop.FadeColour(DesignSystem.ColorAccentPrimary, DesignSystem.AnimationFast);

            body.TransformTo(nameof(body.EdgeEffect), new EdgeEffectParameters
            {
                Type = EdgeEffectType.Glow,
                Colour = DesignSystem.WithOpacity(color, 0.4f),
                Radius = 15,
                Roundness = 6
            }, DesignSystem.AnimationQuick);

            body.Delay(DesignSystem.AnimationQuick).TransformTo(nameof(body.EdgeEffect), new EdgeEffectParameters
            {
                Type = EdgeEffectType.Glow,
                Colour = DesignSystem.WithOpacity(DesignSystem.ColorAccentPrimary, 0.15f),
                Radius = 8,
                Roundness = 4
            }, DesignSystem.AnimationFast);
        }
    }
}
