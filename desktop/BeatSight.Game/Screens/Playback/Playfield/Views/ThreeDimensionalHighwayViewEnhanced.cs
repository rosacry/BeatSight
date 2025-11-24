using System;
using System.Collections.Generic;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Extensions.Color4Extensions;
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
    /// Redesigned 3D highway view renderer (Guitar Hero / Clone Hero style).
    /// 
    /// Key improvements:
    /// - Smoother perspective projection with better depth cues
    /// - Animated lane surfaces with subtle color coding
    /// - Enhanced horizon glow and depth fog effects
    /// - Better scrolling stripe animation for speed feedback
    /// - Improved note scaling for consistent visibility
    /// 
    /// Notes travel along a perspective-projected highway toward the player,
    /// creating a sense of depth and forward motion.
    /// </summary>
    public class ThreeDimensionalHighwayViewEnhanced : PlayfieldViewBaseEnhanced
    {
        public override Configuration.LaneViewMode ViewMode => Configuration.LaneViewMode.ThreeDimensional;

        // Position constants from design system
        public override float HitLineYRatio => DesignSystem.HitLineRatio3D;
        public override float SpawnYRatio => DesignSystem.VanishingPointRatio;

        // 3D-specific visual constants
        private const float HighwayShear = -0.18f;
        private const float LaneShear = -0.22f;
        private const float NoteShear = -0.20f;

        // Horizon and fog
        private const float HorizonGlowHeight = 80f;
        private const float DepthFogStart = 0.3f;
        private const float DepthFogIntensity = 0.4f;

        // Lane accent colors (one per lane, cycles)
        private static readonly Color4[] LaneAccents =
        {
            new Color4(70, 160, 255, 255),  // Blue (Snare)
            new Color4(255, 210, 70, 255),  // Yellow (Hi-hat)
            new Color4(140, 220, 50, 255),  // Green (Tom High)
            new Color4(255, 120, 200, 255), // Pink (Crash)
            new Color4(255, 160, 140, 255), // Coral (Ride)
            new Color4(80, 210, 235, 255),  // Teal (Tom Mid)
            new Color4(180, 130, 255, 255)  // Purple (Kick)
        };

        private ThreeDimensionalHighwayBackgroundEnhanced? backgroundDrawable;

        #region Background Creation

        public override Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick)
        {
            backgroundDrawable = new ThreeDimensionalHighwayBackgroundEnhanced(
                laneCount,
                useGlobalKick,
                Layout?.KickLane ?? 3);
            return backgroundDrawable;
        }

        public override void UpdateBackground(double currentTime)
        {
            backgroundDrawable?.UpdateScroll(currentTime);
        }

        #endregion

        #region Strike Zone Creation

        public override Drawable CreateStrikeZone()
        {
            return new ThreeDimensionalStrikeZoneEnhanced();
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
            // Clamp progress with some overflow for smooth entry/exit
            float t = Clamp(progress, -0.1f, 1.15f);

            // Apply perspective easing
            float perspectiveT = ApplyPerspectiveEasing(t);

            // Calculate 3D positions
            float vanishingPointX = drawWidth / 2;
            float vanishingPointY = drawHeight * DesignSystem.VanishingPointRatio;

            float highwayWidthAtBottom = drawWidth * DesignSystem.HighwayWidthBottom;
            float highwayWidthAtTop = highwayWidthAtBottom * DesignSystem.HighwayWidthTopRatio;

            int activeLaneCount = ctx.VisibleLaneCount;
            float laneWidthAtBottom = highwayWidthAtBottom / activeLaneCount;
            float laneWidthAtTop = highwayWidthAtTop / activeLaneCount;

            // Interpolate based on perspective progress
            float currentHighwayWidth = Lerp(highwayWidthAtTop, highwayWidthAtBottom, perspectiveT);
            float currentLaneWidth = currentHighwayWidth / activeLaneCount;

            // Calculate Y with perspective
            float y = Lerp(vanishingPointY, hitLineY, perspectiveT);

            // Calculate scale with depth
            float scale = Calculate3DScale(perspectiveT);

            // Add stretch effect for speed sensation
            float stretch = CalculateStretchFactor(t);

            if (ctx.UseGlobalKickLine && note.IsKick)
            {
                UpdateKickNotePosition3D(note, y, currentHighwayWidth, scale, stretch, drawWidth);
            }
            else
            {
                UpdateLaneNotePosition3D(note, y, currentLaneWidth, scale, stretch, drawWidth, currentHighwayWidth, ctx);
            }

            // Fade notes that pass hit line
            note.Alpha = y > hitLineY + note.Height / 2 + 2 ? 0 : 1;
        }

        private void UpdateKickNotePosition3D(
            DrawableNote note,
            float y,
            float highwayWidth,
            float scale,
            float stretch,
            float drawWidth)
        {
            float kickHeight = 16f * scale;

            note.Width = highwayWidth;
            note.Height = kickHeight;
            note.Position = new Vector2(drawWidth / 2, y);
            note.Scale = new Vector2(1f, stretch);
            note.Rotation = 0;

            // Apply kick-specific dimensions
            note.ApplyKickLineDimensions(highwayWidth, kickHeight, ViewMode);
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
            // Base note dimensions
            float baseWidth = 55f;
            float baseHeight = 22f;

            note.Width = baseWidth;
            note.Height = baseHeight;

            // Get visual lane index
            int visualLaneIndex = GetVisualLaneIndex(note.Lane, ctx);

            // Center the highway and calculate X position
            float highwayLeft = (drawWidth - highwayWidth) / 2;
            float x = highwayLeft + laneWidth * visualLaneIndex + laneWidth / 2;

            note.Position = new Vector2(x, y);
            note.Scale = new Vector2(scale, scale * stretch);
            note.Rotation = 0;
        }

        /// <summary>
        /// Calculate stretch factor for speed sensation.
        /// Notes stretch slightly when accelerating toward the player.
        /// </summary>
        private float CalculateStretchFactor(float progress)
        {
            // Maximum stretch at the middle of approach
            float distFromCenter = Math.Abs(progress - 0.5f);
            return 1.0f + (0.5f - distFromCenter) * 0.3f;
        }

        public override void ApplyNoteStyle(DrawableNote note)
        {
            note.SetViewMode(Configuration.LaneViewMode.ThreeDimensional);
        }

        #endregion
    }

    /// <summary>
    /// Enhanced animated 3D highway background with perspective lanes and scrolling markers.
    /// </summary>
    internal partial class ThreeDimensionalHighwayBackgroundEnhanced : CompositeDrawable
    {
        private readonly int laneCount;
        private readonly bool useGlobalKick;
        private readonly int kickLaneIndex;

        private readonly List<Box> scrollingStripes = new();
        private readonly List<float> stripeDepths = new();
        private readonly List<Box> lanePulseGlows = new();

        private Box? horizonGlow;
        private Box? horizonLine;
        private Container? stripeContainer;
        private Container? laneContainer;

        // Lane accent colors
        private static readonly Color4[] LaneAccents =
        {
            new Color4(70, 160, 255, 255),  // Blue
            new Color4(255, 210, 70, 255),  // Yellow
            new Color4(140, 220, 50, 255),  // Green
            new Color4(255, 120, 200, 255), // Pink
            new Color4(255, 160, 140, 255), // Coral
            new Color4(80, 210, 235, 255),  // Teal
            new Color4(180, 130, 255, 255)  // Purple
        };

        public ThreeDimensionalHighwayBackgroundEnhanced(int laneCount, bool useGlobalKick, int kickLaneIndex)
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

            // Deep space gradient background
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    new Color4(8, 12, 25, 255),
                    new Color4(18, 25, 45, 255))
            });

            // Horizon glow effect
            horizonGlow = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 100,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Y = 5,
                Colour = ColourInfo.GradientVertical(
                    new Color4(50, 90, 200, 90),
                    Color4.Transparent)
            };
            AddInternal(horizonGlow);

            // Horizon line
            horizonLine = new Box
            {
                RelativeSizeAxes = Axes.X,
                Width = 0.5f,
                Height = 2,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Y = DrawHeight * DesignSystem.VanishingPointRatio,
                Colour = new Color4(100, 150, 255, 150)
            };
            AddInternal(horizonLine);

            // Highway surface
            laneContainer = CreateHighwaySurface(visibleLanes);
            AddInternal(laneContainer);

            // Scrolling depth stripes
            stripeContainer = CreateScrollingStripes();
            AddInternal(stripeContainer);

            // Lane dividers with perspective
            var laneDividers = CreateLaneDividers(visibleLanes);
            AddInternal(laneDividers);
        }

        private Container CreateHighwaySurface(int visibleLanes)
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            // Calculate lane width factor based on visible lanes
            float laneWidthFactor = Math.Clamp(0.65f / Math.Max(1, visibleLanes), 0.07f, 0.18f);

            for (int i = 0; i < visibleLanes; i++)
            {
                // Calculate horizontal position with perspective spread
                float normalized = visibleLanes <= 1
                    ? 0
                    : (i - (visibleLanes - 1) / 2f) / Math.Max(1, visibleLanes - 1);

                var accentColour = LaneAccents[i % LaneAccents.Length];

                // Lane surface container
                var laneSurface = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    RelativePositionAxes = Axes.X,
                    X = normalized * 0.55f,
                    Width = laneWidthFactor,
                    Height = 0.92f,
                    Shear = new Vector2(-0.20f, 0),
                    Padding = new MarginPadding { Bottom = 20 }
                };

                // Lane gradient (dark at horizon, lighter at bottom)
                var topColour = Color4Extensions.Opacity(DesignSystem.Brighten(accentColour, 1.1f), 0.18f);
                var bottomColour = Color4Extensions.Opacity(DesignSystem.ColorSurface, 0.05f);

                laneSurface.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientVertical(topColour, bottomColour)
                });

                // Lane edge highlight at horizon
                laneSurface.Add(new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 4,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = DesignSystem.Brighten(accentColour, 1.3f),
                    Alpha = 0.5f
                });

                // Animated pulse glow for lane activity
                var pulseGlow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = DesignSystem.Brighten(accentColour, 1.2f),
                    Alpha = 0,
                    Blending = BlendingParameters.Additive
                };
                laneSurface.Add(pulseGlow);
                lanePulseGlows.Add(pulseGlow);

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

            const int stripeCount = 18;

            for (int i = 0; i < stripeCount; i++)
            {
                // Depth factor (0 = nearest, 1 = farthest)
                float depth = stripeCount <= 1 ? 1f : i / (float)(stripeCount - 1);

                // Width scales with depth (narrower at horizon)
                float width = 0.4f + 0.55f * (1 - depth);

                var stripe = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 1.5f,
                    Width = width,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = new Color4(255, 255, 255, (byte)(20 + (1 - depth) * 40)),
                    Alpha = 0.3f,
                    Shear = new Vector2(-0.20f, 0)
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

                // Rotation for perspective effect
                float rotation = normalized * 12f;

                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 2,
                    Height = 0.85f,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    RelativePositionAxes = Axes.X,
                    X = normalized * 0.55f,
                    Rotation = rotation,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(255, 255, 255, 8),
                        new Color4(255, 255, 255, 40)),
                    Alpha = 0.45f
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
                // Speed factor based on time
                float baseOffset = (float)((currentTime * 0.0004) % 1.0);

                for (int i = 0; i < scrollingStripes.Count; i++)
                {
                    // Each stripe has a phase offset
                    float offset = (i / (float)scrollingStripes.Count) + baseOffset;
                    offset -= MathF.Floor(offset);

                    // Depth affects parallax speed
                    float depth = stripeDepths[i];
                    float parallax = 0.55f + (1 - depth) * 0.55f;
                    float y = -offset * DrawHeight * parallax;

                    var stripe = scrollingStripes[i];
                    stripe.Y = y;
                    stripe.Scale = new Vector2(parallax, 1);
                    stripe.Alpha = 0.15f + (1 - depth) * 0.35f;
                }
            }

            // Animate lane pulse glows (subtle wave effect)
            for (int i = 0; i < lanePulseGlows.Count; i++)
            {
                var glow = lanePulseGlows[i];
                float phaseOffset = i * MathF.PI * 0.35f;
                float wave = (float)Math.Sin(currentTime * 0.0018 + phaseOffset);
                float intensity = 0.08f + MathF.Max(0, wave) * 0.18f;
                glow.Alpha = intensity;
            }

            // Pulse horizon glow
            if (horizonGlow != null)
            {
                float horizonPulse = 0.28f + 0.12f * (float)Math.Sin(currentTime * 0.0012);
                horizonGlow.Alpha = horizonPulse;
            }
        }

        /// <summary>
        /// Pulse a specific lane when a note is hit.
        /// </summary>
        public void PulseLane(int laneIndex, Color4 color)
        {
            if (laneIndex >= 0 && laneIndex < lanePulseGlows.Count)
            {
                var glow = lanePulseGlows[laneIndex];
                glow.Colour = color;
                glow.FadeTo(0.6f, 50).Then().FadeTo(0.1f, 200);
            }
        }
    }

    /// <summary>
    /// Enhanced strike zone visual for 3D highway view.
    /// Features perspective-matching shear and prominent glow.
    /// </summary>
    internal partial class ThreeDimensionalStrikeZoneEnhanced : CompositeDrawable
    {
        private readonly Container body;
        private readonly Box fill;
        private readonly Box topGlow;
        private readonly Box centerLine;

        public ThreeDimensionalStrikeZoneEnhanced()
        {
            RelativeSizeAxes = Axes.X;
            Height = DesignSystem.StrikeZoneHeight3D;
            Width = 0.90f;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;

            body = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = DesignSystem.RadiusMd,
                Shear = new Vector2(-0.08f, 0),
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = DesignSystem.WithOpacity(new Color4(255, 180, 140, 255), 0.2f),
                    Radius = 12,
                    Roundness = 6
                }
            };

            fill = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    new Color4(50, 45, 85, 120),
                    new Color4(40, 55, 90, 150))
            };

            topGlow = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 4,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = new Color4(255, 190, 150, 220)
            };

            centerLine = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 1,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Y = -1,
                Colour = DesignSystem.WithOpacity(DesignSystem.ColorTextPrimary, 0.12f)
            };

            body.AddRange(new Drawable[]
            {
                fill,
                topGlow,
                centerLine
            });

            // Additive glow layer
            body.Add(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = new Color4(255, 200, 160, 60),
                Alpha = 0.25f,
                Blending = BlendingParameters.Additive
            });

            InternalChild = body;
        }

        public void UpdateGeometry(float drawHeight, float hitLineY)
        {
            float offset = Math.Max(0, drawHeight - hitLineY - Height / 2f);
            Y = -offset;
        }

        public void PulseHit(Color4 color)
        {
            topGlow.Colour = color;
            topGlow.FadeColour(new Color4(255, 190, 150, 220), DesignSystem.AnimationFast);

            body.TransformTo(nameof(body.EdgeEffect), new EdgeEffectParameters
            {
                Type = EdgeEffectType.Glow,
                Colour = DesignSystem.WithOpacity(color, 0.5f),
                Radius = 20,
                Roundness = 8
            }, DesignSystem.AnimationQuick);

            body.Delay(DesignSystem.AnimationQuick).TransformTo(nameof(body.EdgeEffect), new EdgeEffectParameters
            {
                Type = EdgeEffectType.Glow,
                Colour = DesignSystem.WithOpacity(new Color4(255, 180, 140, 255), 0.2f),
                Radius = 12,
                Roundness = 6
            }, DesignSystem.AnimationFast);
        }
    }
}
