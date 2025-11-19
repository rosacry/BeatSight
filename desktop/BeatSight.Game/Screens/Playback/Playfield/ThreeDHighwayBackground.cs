using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    internal sealed partial class ThreeDHighwayBackground : CompositeDrawable
    {
        private readonly LaneLayout laneLayout;
        private readonly bool kickUsesGlobalLine;
        private readonly bool kickLaneSuppressed;
        private Box? horizonGlow;
        private Box? specularSweep;
        private int visibleLaneCount;
        private List<int> laneOrder = new();
        private Color4[] laneAccentPalette = {
            new Color4(64, 156, 255, 255),  // Snare blue
            new Color4(255, 221, 89, 255),  // Hihat gold
            new Color4(138, 201, 38, 255),  // Tom green
            new Color4(255, 159, 243, 255)  // Crash pink
        };

        private readonly List<Box> timelineStripes = new();
        private readonly List<float> timelineStripeDepth = new();
        private readonly List<Box> lanePulseLights = new();
        private readonly List<float> lanePulseOffsets = new();
        private readonly Stack<KickPulse> kickPulsePool = new();
        private readonly Dictionary<DrawableNote, KickPulse> activeKickPulses = new();
        private Container? kickPulseContainer;
        private Container? kickGuideBand;

        public ThreeDHighwayBackground(LaneLayout laneLayout, bool kickUsesGlobalLine)
        {
            this.laneLayout = laneLayout;
            this.kickUsesGlobalLine = kickUsesGlobalLine;
            this.kickLaneSuppressed = kickUsesGlobalLine;
            RelativeSizeAxes = Axes.Both;

            visibleLaneCount = laneLayout?.LaneCount ?? 4;
            laneOrder = Enumerable.Range(0, visibleLaneCount).ToList();

            InternalChildren = new Drawable[]
            {
                horizonGlow = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 100,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = Color4Extensions.Opacity(Color4.Blue, 0.5f)
                },
                specularSweep = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 50,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Colour = Color4Extensions.Opacity(Color4.White, 0.2f)
                },
                createLaneSurfaceLayer()
            };

            if (kickUsesGlobalLine)
            {
                kickPulseContainer = new Container { RelativeSizeAxes = Axes.Both };
                AddInternal(kickPulseContainer);
            }
        }

        public void ResetKickTimeline() { }
        public void SetKickGuideVisible(bool visible) { }

        public void UpdateKickTimeline(IEnumerable<DrawableNote> notes, double time, double duration)
        {
            // Stub implementation
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            horizonGlow?.Loop(sequence => sequence
                .FadeTo(0.35f, 1200, Easing.InOutSine)
                .Then()
                .FadeTo(0.18f, 1200, Easing.InOutSine));

            specularSweep?.Loop(sequence => sequence
                .MoveToX(0.45f, 2600, Easing.InOutSine)
                .Then()
                .MoveToX(-0.45f, 2600, Easing.InOutSine));
        }

        private Drawable createLaneSurfaceLayer()
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            float laneWidthFactor = Math.Clamp(0.68f / Math.Max(1, visibleLaneCount), 0.08f, 0.18f);

            for (int index = 0; index < laneOrder.Count; index++)
            {
                float normalized = visibleLaneCount <= 1
                    ? 0
                    : (index - (visibleLaneCount - 1) / 2f) / Math.Max(1, visibleLaneCount - 1);

                var accentColour = laneAccentPalette[index % laneAccentPalette.Length];

                var laneSurface = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    RelativePositionAxes = Axes.X,
                    X = normalized * 0.62f,
                    Width = laneWidthFactor,
                    Height = 0.96f,
                    Shear = new Vector2(-0.26f, 0),
                    Padding = new MarginPadding { Bottom = 18 }
                };

                var laneTopColour = Color4Extensions.Opacity(UITheme.Emphasise(accentColour, 1.28f), 0.3f);
                var laneBottomColour = Color4Extensions.Opacity(UITheme.Emphasise(UITheme.Surface, 0.88f), 0.1f);

                laneSurface.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientVertical(laneTopColour, laneBottomColour)
                });

                laneSurface.Add(new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 8,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = UITheme.Emphasise(accentColour, 1.55f),
                    Alpha = 0.7f
                });

                var glow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Emphasise(accentColour, 1.42f),
                    Alpha = 0,
                    Blending = BlendingParameters.Additive
                };

                laneSurface.Add(glow);
                lanePulseLights.Add(glow);
                lanePulseOffsets.Add(normalized);

                container.Add(laneSurface);
            }

            return container;
        }

        private Drawable createDepthFogLayer()
        {
            return new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    new Color4(0, 0, 0, 0),
                    UITheme.Emphasise(UITheme.BackgroundLayer, 0.78f)),
                Alpha = 0.68f
            };
        }

        private Drawable createLaneSeparatorLayer()
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            container.Add(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = UITheme.SurfaceAlt,
                Alpha = 0.52f
            });

            for (int index = 0; index < laneOrder.Count; index++)
            {
                float normalized = visibleLaneCount <= 1
                    ? 0
                    : (index - (visibleLaneCount - 1) / 2f) / Math.Max(1, visibleLaneCount - 1);

                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 4,
                    Height = 0.9f,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    RelativePositionAxes = Axes.X,
                    X = normalized * 0.62f,
                    Rotation = normalized * 18f,
                    Colour = UITheme.Emphasise(UITheme.GetLaneEdgeColour(index, visibleLaneCount), 1.05f),
                    Alpha = 0.42f
                });
            }

            return container;
        }

        private Drawable createKickGuideLayer()
        {
            kickPulseContainer = null;

            if (kickLaneSuppressed)
            {
                var kickLane = new ThreeDKickLane(laneLayout.LaneCount);
                kickPulseContainer = kickLane.PulseContainer;
                kickGuideBand = kickLane;
                return kickLane;
            }

            return new Container();
        }

        private Drawable createTimelineStripeLayer()
        {
            var stripeLayer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            const int stripeCount = 14;
            for (int i = 0; i < stripeCount; i++)
            {
                float depth = stripeCount <= 1 ? 1f : i / (float)(stripeCount - 1);
                float width = 0.55f + 0.45f * depth;

                var stripe = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2,
                    Width = width,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = new Color4(255, 255, 255, (byte)(40 + depth * 60)),
                    Alpha = 0.5f,
                    Shear = new Vector2(-0.25f, 0)
                };

                stripeLayer.Add(stripe);
                timelineStripes.Add(stripe);
                timelineStripeDepth.Add(depth);
            }

            return stripeLayer;
        }

        private KickPulse getOrCreatePulse(DrawableNote note)
        {
            if (activeKickPulses.TryGetValue(note, out var existing))
                return (KickPulse)existing;

            var pulse = new KickPulse();
            if (kickPulseContainer != null)
                kickPulseContainer.Add(pulse);

            activeKickPulses[note] = pulse;
            return pulse;
        }

        private void releasePulse(DrawableNote note)
        {
            if (activeKickPulses.TryGetValue(note, out var pulse))
            {
                activeKickPulses.Remove(note);
                pulse.Expire();
            }
        }

        public void UpdateScroll(double currentTime)
        {
            if (DrawHeight <= 0)
                return;

            if (timelineStripes.Count > 0)
            {
                float baseOffset = (float)((currentTime * 0.0006) % 1.0);

                for (int i = 0; i < timelineStripes.Count; i++)
                {
                    float offset = (i / (float)timelineStripes.Count) + baseOffset;
                    offset -= MathF.Floor(offset);
                    float depth = timelineStripeDepth[i];
                    float parallax = 0.65f + depth * 0.45f;
                    float y = -offset * DrawHeight * parallax;
                    var stripe = timelineStripes[i];
                    stripe.Y = y;
                    stripe.Scale = new Vector2(parallax, 1);
                    stripe.Alpha = 0.25f + depth * 0.45f;
                }
            }

            if (lanePulseLights.Count > 0)
            {
                for (int i = 0; i < lanePulseLights.Count; i++)
                {
                    var glow = lanePulseLights[i];
                    float offset = lanePulseOffsets.Count > i ? lanePulseOffsets[i] : 0;
                    float wave = (float)Math.Sin(currentTime * 0.002 + offset * MathF.PI);
                    float intensity = 0.18f + MathF.Max(0, wave) * 0.32f;
                    glow.Alpha = intensity;
                    glow.Scale = new Vector2(1f, 1.05f + MathF.Max(0, (float)Math.Sin(currentTime * 0.003 + offset * 2)) * 0.08f);
                }
            }
        }
    }
}
