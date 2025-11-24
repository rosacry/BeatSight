using System;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// Visual indicator for the hit/judgement zone across all playfield view modes.
    /// Adapts its appearance to match the active view (2D lanes, 3D highway, or manuscript).
    /// </summary>
    internal sealed partial class TimingStrikeZone : CompositeDrawable
    {
        private readonly Container strikeBody;
        private readonly Box fill;
        private readonly Box glow;
        private readonly Box rim;
        private readonly Box innerHighlight;
        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private bool useGlobalKick = true;
        private float baselineOffset;
        private float visualHeight;

        // View-specific styling
        private static readonly Color4 TwoDimensionalBorder = new Color4(100, 160, 255, 220);
        private static readonly Color4 TwoDimensionalFill = new Color4(30, 50, 90, 140);
        private static readonly Color4 ThreeDimensionalBorder = new Color4(255, 200, 160, 230);
        private static readonly Color4 ThreeDimensionalFill = new Color4(50, 45, 80, 130);
        private static readonly Color4 ManuscriptLine = new Color4(180, 60, 60, 180);

        public float VisualHitZoneHeight => visualHeight;

        public TimingStrikeZone()
        {
            RelativeSizeAxes = Axes.X;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;
            Width = 0.98f;
            Height = 24f;
            AlwaysPresent = true;
            Alpha = 0.95f;

            strikeBody = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 12,
                BorderThickness = 3,
                BorderColour = TwoDimensionalBorder
            };

            fill = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = TwoDimensionalFill
            };

            glow = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = UITheme.AccentPrimary,
                Alpha = 0.3f,
                Blending = BlendingParameters.Additive
            };

            innerHighlight = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 2,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = new Color4(255, 255, 255, 60)
            };

            rim = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 3,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = TwoDimensionalBorder
            };

            strikeBody.Add(fill);
            strikeBody.Add(glow);
            strikeBody.Add(innerHighlight);

            InternalChildren = new Drawable[]
            {
                strikeBody,
                rim
            };

            updatePalette();
        }

        public void SetLaneLayout(LaneLayout layout)
        {
            // Reserved for future per-lane customization
            _ = layout;
        }

        public void SetKickMode(bool globalKick)
        {
            useGlobalKick = globalKick;
            updatePalette();
        }

        public void SetViewMode(LaneViewMode mode)
        {
            viewMode = mode;
            updatePalette();
        }

        public void UpdateGeometry(float drawWidth, float drawHeight, float hitLineY, float spawnTop, float laneWidth, int lanes, int visibleLanes, int kickLaneIndex, bool globalKick, LaneViewMode mode)
        {
            _ = drawWidth;
            _ = spawnTop;
            _ = laneWidth;
            _ = lanes;
            _ = visibleLanes;
            _ = kickLaneIndex;
            useGlobalKick = globalKick;
            viewMode = mode;

            // Adjust dimensions based on view mode
            float baseHeight = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(drawHeight * 0.055f, 18f, 45f),
                LaneViewMode.Manuscript => 8f,
                _ => 22f // 2D default
            };

            Height = baseHeight;
            visualHeight = baseHeight;

            // Position relative to hit line
            float offsetFromBottom = Math.Clamp(drawHeight - hitLineY - baseHeight / 2f, 0f, drawHeight);
            baselineOffset = offsetFromBottom;
            Y = -baselineOffset;

            // Adjust width based on view mode
            float widthFactor = mode switch
            {
                LaneViewMode.ThreeDimensional => 0.90f,
                LaneViewMode.Manuscript => 0.55f,
                _ => 0.98f
            };
            Width = Math.Clamp(widthFactor, 0.5f, 0.99f);

            // Adjust corner radius
            float cornerRadius = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(baseHeight * 0.4f, 6f, 20f),
                LaneViewMode.Manuscript => 2f,
                _ => Math.Clamp(baseHeight * 0.5f, 6f, 14f)
            };
            strikeBody.CornerRadius = cornerRadius;

            // Adjust border thickness
            strikeBody.BorderThickness = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(baseHeight * 0.22f, 2f, 5f),
                LaneViewMode.Manuscript => 1f,
                _ => 3f
            };

            rim.Height = mode == LaneViewMode.Manuscript ? 2f : 3f;
            rim.Alpha = mode == LaneViewMode.Manuscript ? 0.8f : 0.85f;

            updatePalette();
        }

        private void updatePalette()
        {
            Color4 borderColour;
            Color4 fillColour;
            float glowAlpha;

            switch (viewMode)
            {
                case LaneViewMode.Manuscript:
                    borderColour = ManuscriptLine;
                    fillColour = Color4.Transparent;
                    glowAlpha = 0f;
                    strikeBody.BorderColour = borderColour;
                    fill.Colour = fillColour;
                    glow.Alpha = glowAlpha;
                    rim.Colour = ManuscriptLine;
                    innerHighlight.Alpha = 0f;
                    return;

                case LaneViewMode.ThreeDimensional:
                    borderColour = useGlobalKick
                        ? new Color4(255, 195, 150, 240)
                        : new Color4(180, 200, 255, 240);
                    fillColour = useGlobalKick
                        ? new Color4(55, 40, 85, 120)
                        : new Color4(40, 55, 90, 120);
                    glowAlpha = 0.45f;
                    break;

                default: // 2D
                    borderColour = useGlobalKick
                        ? new Color4(200, 180, 255, 230)
                        : TwoDimensionalBorder;
                    fillColour = useGlobalKick
                        ? new Color4(60, 45, 100, 130)
                        : TwoDimensionalFill;
                    glowAlpha = 0.35f;
                    break;
            }

            strikeBody.BorderColour = borderColour;
            fill.Colour = fillColour;
            glow.Colour = UITheme.Emphasise(borderColour, 1.2f);
            glow.Alpha = glowAlpha;
            rim.Colour = new Color4(borderColour.R, borderColour.G, borderColour.B, 180);
            innerHighlight.Alpha = 0.4f;
        }
    }
}
