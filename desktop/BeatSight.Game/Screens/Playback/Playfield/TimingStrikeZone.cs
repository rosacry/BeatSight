using System;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    internal sealed partial class TimingStrikeZone : CompositeDrawable
    {
        private readonly Container strikeBody;
        private readonly Box fill;
        private readonly Box glow;
        private readonly Box rim;
        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private bool useGlobalKick = true;
        private float baselineOffset;
        private float visualHeight;

        public float VisualHitZoneHeight => visualHeight;

        public TimingStrikeZone()
        {
            RelativeSizeAxes = Axes.X;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;
            Width = 0.98f;
            Height = 28f;
            AlwaysPresent = true;
            Alpha = 0.92f;

            strikeBody = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 14,
                BorderThickness = 4,
                BorderColour = new Color4(255, 220, 200, 220)
            };

            fill = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = new Color4(42, 46, 72, 120)
            };

            glow = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = new Color4(255, 214, 170, 80),
                Alpha = 0.35f,
                Blending = BlendingParameters.Additive
            };

            rim = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 3,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = new Color4(255, 245, 230, 140)
            };

            strikeBody.Add(fill);
            strikeBody.Add(glow);

            InternalChildren = new Drawable[]
            {
                strikeBody,
                rim
            };

            updatePalette();
        }

        public void SetLaneLayout(LaneLayout layout)
        {
            // Currently unused, but retained for future per-lane styling customisation.
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

            float baseHeight = mode == LaneViewMode.ThreeDimensional
                ? Math.Clamp(drawHeight * 0.058f, 20f, 50f)
                : 20f;

            Height = baseHeight;
            visualHeight = baseHeight;

            float offsetFromBottom = Math.Clamp(drawHeight - hitLineY - baseHeight / 2f, 0f, drawHeight);
            baselineOffset = offsetFromBottom;
            Y = -baselineOffset;

            float widthFactor = mode == LaneViewMode.ThreeDimensional ? 0.92f : 0.98f;
            Width = Math.Clamp(widthFactor, 0.7f, 0.99f);

            float cornerRadius = Math.Clamp(baseHeight * 0.48f, 6f, 28f);
            strikeBody.CornerRadius = cornerRadius;
            strikeBody.BorderThickness = Math.Clamp(baseHeight * 0.28f, 3f, 6f);
            rim.Height = mode == LaneViewMode.ThreeDimensional ? 4f : 3f;
            rim.Alpha = mode == LaneViewMode.ThreeDimensional ? 0.9f : 0.75f;

            updatePalette();
        }

        private void updatePalette()
        {
            if (viewMode == LaneViewMode.Manuscript)
            {
                strikeBody.BorderColour = new Color4(0, 0, 0, 100);
                fill.Colour = Color4.Transparent;
                glow.Alpha = 0;
                rim.Colour = new Color4(0, 0, 0, 100);
                return;
            }

            var border = useGlobalKick
                ? new Color4(255, 210, 182, 230)
                : new Color4(200, 220, 255, 230); // Made brighter

            var fillColour = useGlobalKick
                ? new Color4(52, 40, 90, 110)
                : new Color4(40, 50, 80, 110);

            strikeBody.BorderColour = border;
            fill.Colour = fillColour;
            glow.Colour = UITheme.Emphasise(border, 1.25f);
            glow.Alpha = 0.48f; // Consistent glow
            rim.Colour = new Color4(border.R, border.G, border.B, 180);
        }
    }
}
