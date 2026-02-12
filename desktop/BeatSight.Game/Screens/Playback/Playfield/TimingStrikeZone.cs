using System;
using System.Collections.Generic;
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
        private readonly Container laneGuideContainer;
        private readonly List<Box> laneDividerLines = new List<Box>();
        private readonly List<Box> laneAccentCaps = new List<Box>();
        private readonly List<Box> laneFillBands = new List<Box>();
        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private bool useGlobalKick = true;
        private float baselineOffset;
        private float visualHeight;

        // View-specific styling
        private static readonly Color4 TwoDimensionalBorder = new Color4(100, 160, 255, 220);
        private static readonly Color4 TwoDimensionalFill = new Color4(30, 50, 90, 140);
        private static readonly Color4 ManuscriptLine = new Color4(180, 60, 60, 180);
        private static readonly Color4[] LaneCapPalette =
        {
            new Color4(86, 166, 106, 255),
            new Color4(188, 94, 104, 255),
            new Color4(206, 181, 92, 255),
            new Color4(88, 132, 212, 255),
            new Color4(210, 145, 88, 255),
            new Color4(154, 114, 208, 255),
            new Color4(88, 172, 176, 255),
            new Color4(188, 110, 166, 255)
        };

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
            strikeBody.Add(laneGuideContainer = new Container
            {
                RelativeSizeAxes = Axes.Both
            });

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
            _ = kickLaneIndex;
            useGlobalKick = globalKick;
            viewMode = mode;

            // Adjust dimensions based on view mode
            float baseHeight = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(drawHeight * 0.024f, 10f, 17f),
                LaneViewMode.Manuscript => 8f,
                _ => Math.Clamp(drawHeight * 0.028f, 10f, 22f)
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
                LaneViewMode.ThreeDimensional => 0.87f,
                LaneViewMode.Manuscript => 0.55f,
                _ => 0.98f
            };
            Width = Math.Clamp(widthFactor, 0.5f, 0.99f);

            // Adjust corner radius
            float cornerRadius = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(baseHeight * 0.30f, 4f, 10f),
                LaneViewMode.Manuscript => 2f,
                _ => Math.Clamp(baseHeight * 0.5f, 6f, 14f)
            };
            strikeBody.CornerRadius = cornerRadius;

            // Adjust border thickness
            strikeBody.BorderThickness = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(baseHeight * 0.12f, 1f, 2.4f),
                LaneViewMode.Manuscript => 1f,
                _ => 3f
            };

            rim.Height = mode == LaneViewMode.Manuscript ? 2f : 3f;
            rim.Alpha = mode switch
            {
                LaneViewMode.Manuscript => 0.8f,
                LaneViewMode.ThreeDimensional => 0.56f,
                _ => 0.85f
            };

            updateLaneGuides(Math.Max(1, visibleLanes), mode);
            updatePalette();
        }

        private void updateLaneGuides(int visibleLanes, LaneViewMode mode)
        {
            if (laneGuideContainer == null)
                return;

            while (laneDividerLines.Count < visibleLanes - 1)
            {
                var divider = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 1.6f,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre
                };
                laneDividerLines.Add(divider);
                laneGuideContainer.Add(divider);
            }

            while (laneAccentCaps.Count < visibleLanes)
            {
                var cap = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2.4f,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre
                };
                laneAccentCaps.Add(cap);
                laneGuideContainer.Add(cap);
            }

            while (laneFillBands.Count < visibleLanes)
            {
                var fillBand = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft
                };
                laneFillBands.Add(fillBand);
                laneGuideContainer.Add(fillBand);
            }

            for (int i = 0; i < laneFillBands.Count; i++)
            {
                bool active = i < visibleLanes && mode == LaneViewMode.ThreeDimensional;
                laneFillBands[i].Alpha = active ? 0.08f : 0f;
                laneFillBands[i].Width = 1f / visibleLanes;
                laneFillBands[i].X = i / (float)visibleLanes;
                laneFillBands[i].Colour = i % 2 == 0
                    ? new Color4(188, 202, 228, 62)
                    : new Color4(140, 154, 182, 54);
            }

            for (int i = 0; i < laneDividerLines.Count; i++)
            {
                bool active = i < visibleLanes - 1 && mode != LaneViewMode.Manuscript;
                laneDividerLines[i].Alpha = active ? (mode == LaneViewMode.ThreeDimensional ? 0.42f : 0.45f) : 0f;
                laneDividerLines[i].X = (i + 1f) / visibleLanes;
                laneDividerLines[i].Colour = mode == LaneViewMode.ThreeDimensional
                    ? new Color4(198, 216, 248, 132)
                    : new Color4(220, 230, 248, 140);
            }

            for (int i = 0; i < laneAccentCaps.Count; i++)
            {
                bool active = i < visibleLanes && mode == LaneViewMode.ThreeDimensional;
                laneAccentCaps[i].Alpha = active ? 0.30f : 0f;
                laneAccentCaps[i].Width = 1f / visibleLanes;
                laneAccentCaps[i].X = (i + 0.5f) / visibleLanes;
                Color4 accent = LaneCapPalette[i % LaneCapPalette.Length];
                laneAccentCaps[i].Colour = UITheme.Mix(accent, new Color4(210, 224, 244, 255), 0.64f);
            }
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
                        ? new Color4(232, 204, 176, 206)
                        : new Color4(168, 204, 244, 204);
                    fillColour = useGlobalKick
                        ? new Color4(24, 21, 34, 126)
                        : new Color4(16, 25, 40, 122);
                    glowAlpha = 0.10f;
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
            innerHighlight.Alpha = viewMode == LaneViewMode.ThreeDimensional ? 0.13f : 0.4f;
        }
    }
}
