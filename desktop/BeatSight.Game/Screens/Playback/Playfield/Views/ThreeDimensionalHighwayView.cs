using System;
using System.Collections.Generic;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// 3D highway view renderer (Guitar Hero / Clone Hero style).
    /// Notes travel along a perspective-projected highway toward the player.
    /// Creates a sense of depth and movement.
    /// </summary>
    public class ThreeDimensionalHighwayView : PlayfieldViewBase
    {
        public override Configuration.LaneViewMode ViewMode => Configuration.LaneViewMode.ThreeDimensional;

        // Perspective constants
        private const float VanishingPointYRatio = 0.12f; // Where the horizon sits
        private const float HighwayWidthAtBottomRatio = 0.88f; // Width of highway at hit line
        private const float HighwayWidthAtTopRatio = 0.30f; // Width at vanishing point (perspective)
        private const float MinNoteScale = 0.25f; // Scale at vanishing point
        private const float MaxNoteScale = 1.0f; // Scale at hit line
        private const float HitLinePosition = 0.90f; // Slightly higher for 3D to give note travel room

        // Visual styling
        private static readonly Color4 HorizonGlowColour = new Color4(60, 80, 180, 120);
        private static readonly Color4 HighwaySurfaceTop = new Color4(20, 25, 45, 200);
        private static readonly Color4 HighwaySurfaceBottom = new Color4(35, 45, 75, 240);

        private ThreeDimensionalHighwayBackground? backgroundDrawable;

        public override float HitLineYRatio => HitLinePosition;
        public override float SpawnYRatio => VanishingPointYRatio;

        public override Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick)
        {
            backgroundDrawable = new ThreeDimensionalHighwayBackground(
                laneCount,
                useGlobalKick,
                Layout?.KickLane ?? 3);
            return backgroundDrawable;
        }

        public override Drawable CreateStrikeZone()
        {
            return new ThreeDimensionalStrikeZone();
        }

        public override void UpdateBackground(double currentTime)
        {
            backgroundDrawable?.UpdateScroll(currentTime);
        }

        public override void UpdateNotePosition(
            DrawableNote note,
            float progress,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            NotePositionContext ctx)
        {
            // Clamp progress to valid range with some overflow for smooth transitions
            float t = Math.Clamp(progress, -0.1f, 1.15f);

            // Calculate vanishing point and highway dimensions
            float vanishingPointX = drawWidth / 2;
            float vanishingPointY = drawHeight * VanishingPointYRatio;
            float highwayWidthAtBottom = drawWidth * HighwayWidthAtBottomRatio;
            float highwayWidthAtTop = highwayWidthAtBottom * (HighwayWidthAtTopRatio / HighwayWidthAtBottomRatio);

            int activeLaneCount = ctx.VisibleLaneCount;
            float laneWidthAtBottom = highwayWidthAtBottom / activeLaneCount;
            float laneWidthAtTop = highwayWidthAtTop / activeLaneCount;

            // Interpolate values based on progress (non-linear for better perspective feel)
            float perspectiveT = EaseInPerspective(t);
            float currentHighwayWidth = Lerp(highwayWidthAtTop, highwayWidthAtBottom, perspectiveT);
            float currentLaneWidth = currentHighwayWidth / activeLaneCount;

            // Calculate Y position with perspective
            float y = Lerp(vanishingPointY, hitLineY, perspectiveT);

            // Calculate scale with depth
            float scale = Lerp(MinNoteScale, MaxNoteScale, perspectiveT);

            // Add subtle stretch effect for speed sensation
            float stretch = 1.0f + Math.Abs(t - 0.5f) * 0.15f;

            if (ctx.UseGlobalKickLine && note.IsKick)
            {
                UpdateKickNotePosition3D(note, y, currentHighwayWidth, scale, stretch, drawWidth);
            }
            else
            {
                UpdateLaneNotePosition3D(note, y, currentLaneWidth, scale, stretch, drawWidth, currentHighwayWidth, ctx);
            }

            // Fade notes that pass the hit line
            note.Alpha = y > hitLineY + note.Height / 2 + 2 ? 0 : 1;
        }

        private void UpdateKickNotePosition3D(DrawableNote note, float y, float highwayWidth, float scale, float stretch, float drawWidth)
        {
            note.Width = highwayWidth;
            note.Height = 18 * scale;
            note.Position = new Vector2(drawWidth / 2, y);
            note.Scale = new Vector2(1f, stretch);
            note.Rotation = 0;
        }

        private void UpdateLaneNotePosition3D(
            DrawableNote note,
            float y,
            float laneWidth,
            float scale,
            float stretch,
            float drawWidth,
            float highwayWidth,
            NotePositionContext ctx)
        {
            // Base note size (will be scaled)
            note.Width = 60;
            note.Height = 24;

            // Get visual lane index
            int visualLaneIndex = GetVisualLaneIndex(note.Lane, ctx);

            // Center the highway and calculate X position
            float highwayLeft = (drawWidth - highwayWidth) / 2;
            float x = highwayLeft + laneWidth * visualLaneIndex + laneWidth / 2;

            note.Position = new Vector2(x, y);
            note.Scale = new Vector2(scale, scale * stretch);
            note.Rotation = 0;
        }

        public override void ApplyNoteStyle(DrawableNote note)
        {
            note.SetViewMode(Configuration.LaneViewMode.ThreeDimensional);
        }

        /// <summary>
        /// Easing function for perspective projection.
        /// Creates more realistic depth perception by making objects appear to accelerate as they approach.
        /// </summary>
        private static float EaseInPerspective(float t)
        {
            // Quadratic ease-in for natural perspective feel
            return t * t * (3 - 2 * t);
        }
    }

    /// <summary>
    /// Animated 3D highway background with perspective lanes and scrolling markers.
    /// </summary>
    internal partial class ThreeDimensionalHighwayBackground : CompositeDrawable
    {
        private readonly int laneCount;
        private readonly bool useGlobalKick;
        private readonly int kickLaneIndex;
        private readonly List<Box> scrollingStripes = new();
        private readonly List<float> stripeDepths = new();
        private readonly List<Box> lanePulseGlows = new();

        private Box? horizonGlow;
        private Container? stripeContainer;

        private static readonly Color4[] LanePalette =
        {
            new Color4(64, 156, 255, 255),  // Snare blue
            new Color4(255, 221, 89, 255),  // Hihat gold
            new Color4(138, 201, 38, 255),  // Tom green
            new Color4(255, 159, 243, 255), // Crash pink
            new Color4(250, 177, 160, 255)  // Ride coral
        };

        public ThreeDimensionalHighwayBackground(int laneCount, bool useGlobalKick, int kickLaneIndex)
        {
            this.laneCount = laneCount;
            this.useGlobalKick = useGlobalKick;
            this.kickLaneIndex = kickLaneIndex;

            RelativeSizeAxes = Axes.Both;

            BuildVisuals();
        }

        private void BuildVisuals()
        {
            int visibleLanes = useGlobalKick ? Math.Max(1, laneCount - 1) : laneCount;

            // Horizon glow effect
            horizonGlow = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 80,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Y = 10,
                Colour = ColourInfo.GradientVertical(
                    new Color4(40, 80, 180, 100),
                    Color4.Transparent)
            };

            AddInternal(horizonGlow);

            // Highway surface with perspective gradient
            var highwaySurface = CreateHighwaySurface(visibleLanes);
            AddInternal(highwaySurface);

            // Scrolling depth stripes
            stripeContainer = CreateScrollingStripes();
            AddInternal(stripeContainer);

            // Lane dividers with perspective
            var laneDividers = CreateLaneDividers(visibleLanes);
            AddInternal(laneDividers);
        }

        private Drawable CreateHighwaySurface(int visibleLanes)
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            float laneWidthFactor = Math.Clamp(0.7f / Math.Max(1, visibleLanes), 0.08f, 0.2f);

            for (int i = 0; i < visibleLanes; i++)
            {
                float normalized = visibleLanes <= 1
                    ? 0
                    : (i - (visibleLanes - 1) / 2f) / Math.Max(1, visibleLanes - 1);

                var accentColour = LanePalette[i % LanePalette.Length];

                var laneSurface = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    RelativePositionAxes = Axes.X,
                    X = normalized * 0.6f,
                    Width = laneWidthFactor,
                    Height = 0.95f,
                    Shear = new Vector2(-0.22f, 0),
                    Padding = new MarginPadding { Bottom = 15 }
                };

                // Lane gradient
                var topColour = Color4Extensions.Opacity(UITheme.Emphasise(accentColour, 1.2f), 0.25f);
                var bottomColour = Color4Extensions.Opacity(UITheme.Emphasise(UITheme.Surface, 0.9f), 0.08f);

                laneSurface.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientVertical(topColour, bottomColour)
                });

                // Lane edge highlight
                laneSurface.Add(new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 6,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = UITheme.Emphasise(accentColour, 1.4f),
                    Alpha = 0.6f
                });

                // Pulse glow for lane activity
                var glow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Emphasise(accentColour, 1.3f),
                    Alpha = 0,
                    Blending = BlendingParameters.Additive
                };
                laneSurface.Add(glow);
                lanePulseGlows.Add(glow);

                container.Add(laneSurface);
            }

            return container;
        }

        private Container CreateScrollingStripes()
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            const int stripeCount = 16;

            for (int i = 0; i < stripeCount; i++)
            {
                float depth = stripeCount <= 1 ? 1f : i / (float)(stripeCount - 1);
                float width = 0.5f + 0.5f * depth;

                var stripe = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2,
                    Width = width,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = new Color4(255, 255, 255, (byte)(30 + depth * 50)),
                    Alpha = 0.4f,
                    Shear = new Vector2(-0.22f, 0)
                };

                container.Add(stripe);
                scrollingStripes.Add(stripe);
                stripeDepths.Add(depth);
            }

            return container;
        }

        private Drawable CreateLaneDividers(int visibleLanes)
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            for (int i = 0; i <= visibleLanes; i++)
            {
                float normalized = visibleLanes <= 1
                    ? 0
                    : (i - visibleLanes / 2f) / Math.Max(1, visibleLanes);

                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 3,
                    Height = 0.88f,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    RelativePositionAxes = Axes.X,
                    X = normalized * 0.6f,
                    Rotation = normalized * 15f,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(255, 255, 255, 10),
                        new Color4(255, 255, 255, 50)),
                    Alpha = 0.5f
                });
            }

            return container;
        }

        public void UpdateScroll(double currentTime)
        {
            if (DrawHeight <= 0)
                return;

            // Animate scrolling stripes
            if (scrollingStripes.Count > 0)
            {
                float baseOffset = (float)((currentTime * 0.0005) % 1.0);

                for (int i = 0; i < scrollingStripes.Count; i++)
                {
                    float offset = (i / (float)scrollingStripes.Count) + baseOffset;
                    offset -= MathF.Floor(offset);

                    float depth = stripeDepths[i];
                    float parallax = 0.6f + depth * 0.5f;
                    float y = -offset * DrawHeight * parallax;

                    var stripe = scrollingStripes[i];
                    stripe.Y = y;
                    stripe.Scale = new Vector2(parallax, 1);
                    stripe.Alpha = 0.2f + depth * 0.4f;
                }
            }

            // Animate lane pulse glows
            for (int i = 0; i < lanePulseGlows.Count; i++)
            {
                var glow = lanePulseGlows[i];
                float phaseOffset = i * MathF.PI * 0.4f;
                float wave = (float)Math.Sin(currentTime * 0.002 + phaseOffset);
                float intensity = 0.12f + MathF.Max(0, wave) * 0.25f;
                glow.Alpha = intensity;
            }

            // Animate horizon glow
            horizonGlow?.FadeTo(0.3f + 0.15f * (float)Math.Sin(currentTime * 0.0015), 100);
        }
    }

    /// <summary>
    /// Strike zone visual for 3D highway view.
    /// Wider, with perspective-matching shear.
    /// </summary>
    internal partial class ThreeDimensionalStrikeZone : CompositeDrawable
    {
        private const float ZoneHeight = 28f;

        public ThreeDimensionalStrikeZone()
        {
            RelativeSizeAxes = Axes.X;
            Height = ZoneHeight;
            Width = 0.92f;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;
            Masking = true;
            CornerRadius = 8;
            Shear = new Vector2(-0.1f, 0);

            var fillColour = new Color4(45, 55, 95, 140);
            var borderColour = new Color4(255, 200, 160, 200);

            InternalChildren = new Drawable[]
            {
                // Main fill
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = fillColour
                },
                // Top glow
                new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 4,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = borderColour
                },
                // Additive glow layer
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Emphasise(borderColour, 1.2f),
                    Alpha = 0.3f,
                    Blending = BlendingParameters.Additive
                }
            };
        }

        public void UpdateGeometry(float drawHeight, float hitLineY)
        {
            float offset = Math.Max(0, drawHeight - hitLineY - ZoneHeight / 2f);
            Y = -offset;
        }
    }
}
