using System;
using System.Collections.Generic;
using System.Linq;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Effects
{
    /// <summary>
    /// A collection of visual effects and decorative elements.
    /// </summary>
    public static class VisualEffects
    {
        // Brand colors
        public static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255);
        public static readonly Color4 FuchsiaAccent = new Color4(217, 70, 239, 255);
        public static readonly Color4 AmberAccent = new Color4(245, 158, 11, 255);
        public static readonly Color4 EmeraldAccent = new Color4(16, 185, 129, 255);

        /// <summary>
        /// Creates a gradient glow effect for a drawable.
        /// </summary>
        public static GlowEffect CreateBrandGlow(float sigma = 20, float strength = 1.5f)
        {
            return new GlowEffect
            {
                Colour = ColourInfo.GradientHorizontal(CyanAccent.Opacity(0.6f), FuchsiaAccent.Opacity(0.6f)),
                BlurSigma = new Vector2(sigma),
                Strength = strength,
            };
        }

        /// <summary>
        /// Creates a subtle shadow for elevated elements.
        /// </summary>
        public static EdgeEffectParameters CreateElevationShadow(float radius = 20, float offset = 5)
        {
            return new EdgeEffectParameters
            {
                Type = EdgeEffectType.Shadow,
                Colour = Color4.Black.Opacity(0.4f),
                Radius = radius,
                Offset = new Vector2(0, offset),
            };
        }
    }

    /// <summary>
    /// Animated particle field background.
    /// </summary>
    public partial class ParticleField : CompositeDrawable
    {
        private readonly List<Particle> particles = new();
        private readonly int particleCount;
        private readonly float maxSpeed;
        private readonly Color4 color;

        public ParticleField(int count = 50, float speed = 30f, Color4? particleColor = null)
        {
            particleCount = count;
            maxSpeed = speed;
            color = particleColor ?? VisualEffects.CyanAccent.Opacity(0.3f);
            RelativeSizeAxes = Axes.Both;
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            var random = new Random();

            for (int i = 0; i < particleCount; i++)
            {
                var particle = new Particle
                {
                    Position = new Vector2(
                        (float)random.NextDouble() * DrawWidth,
                        (float)random.NextDouble() * DrawHeight),
                    Size = new Vector2(2 + (float)random.NextDouble() * 3),
                    Colour = color.Opacity(0.2f + (float)random.NextDouble() * 0.3f),
                    Velocity = new Vector2(
                        ((float)random.NextDouble() - 0.5f) * maxSpeed,
                        ((float)random.NextDouble() - 0.5f) * maxSpeed),
                };

                particles.Add(particle);
                AddInternal(particle);
            }
        }

        protected override void Update()
        {
            base.Update();

            float elapsed = (float)Clock.ElapsedFrameTime / 1000f;

            foreach (var particle in particles)
            {
                particle.Position += particle.Velocity * elapsed;

                // Wrap around edges
                if (particle.X < 0) particle.X = DrawWidth;
                if (particle.X > DrawWidth) particle.X = 0;
                if (particle.Y < 0) particle.Y = DrawHeight;
                if (particle.Y > DrawHeight) particle.Y = 0;
            }
        }

        private partial class Particle : Circle
        {
            public Vector2 Velocity { get; set; }
        }
    }

    /// <summary>
    /// Animated gradient mesh background.
    /// </summary>
    public partial class GradientMeshBackground : CompositeDrawable
    {
        private readonly Box[] gradientLayers;
        private readonly Color4[] colors;

        public GradientMeshBackground(Color4[]? customColors = null)
        {
            RelativeSizeAxes = Axes.Both;
            colors = customColors ?? new[]
            {
                VisualEffects.CyanAccent.Opacity(0.15f),
                VisualEffects.FuchsiaAccent.Opacity(0.15f),
                VisualEffects.AmberAccent.Opacity(0.1f),
            };

            gradientLayers = new Box[colors.Length];

            for (int i = 0; i < colors.Length; i++)
            {
                gradientLayers[i] = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientVertical(
                        colors[i],
                        colors[i].Opacity(0)),
                    Alpha = 0.5f,
                    Blending = BlendingParameters.Additive,
                };
                AddInternal(gradientLayers[i]);
            }
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Animate gradient positions for a dynamic effect
            for (int i = 0; i < gradientLayers.Length; i++)
            {
                var layer = gradientLayers[i];
                float delay = i * 2000;
                float duration = 8000 + i * 1000;

                layer.MoveToY(0)
                    .Then(delay)
                    .MoveToY(-0.3f, duration, Easing.InOutSine)
                    .Then()
                    .MoveToY(0.3f, duration, Easing.InOutSine)
                    .Loop();
            }
        }
    }

    /// <summary>
    /// A pulsing glow ring effect.
    /// </summary>
    public partial class PulsingGlowRing : CompositeDrawable
    {
        private readonly Container innerRing;
        private readonly Container outerRing;
        private readonly Color4 glowColor;

        public PulsingGlowRing(float size = 100, Color4? color = null)
        {
            Size = new Vector2(size);
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;
            glowColor = color ?? VisualEffects.CyanAccent;

            InternalChildren = new Drawable[]
            {
                outerRing = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = size / 2,
                    BorderColour = glowColor.Opacity(0.3f),
                    BorderThickness = 2,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Glow,
                        Colour = glowColor.Opacity(0.4f),
                        Radius = 15,
                    },
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.Transparent,
                    },
                },
                innerRing = new Container
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    RelativeSizeAxes = Axes.Both,
                    Size = new Vector2(0.6f),
                    Masking = true,
                    CornerRadius = size * 0.3f,
                    BorderColour = glowColor.Opacity(0.6f),
                    BorderThickness = 3,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Glow,
                        Colour = glowColor.Opacity(0.6f),
                        Radius = 10,
                    },
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.Transparent,
                    },
                },
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Outer ring pulse
            outerRing.ScaleTo(1f)
                    .ScaleTo(1.2f, 2000, Easing.InOutSine)
                    .FadeTo(0.3f, 2000, Easing.InOutSine)
                    .Then()
                    .ScaleTo(1f, 2000, Easing.InOutSine)
                    .FadeTo(1f, 2000, Easing.InOutSine)
                    .Loop();

            // Inner ring counter-pulse
            innerRing.ScaleTo(0.6f)
                    .ScaleTo(0.5f, 1500, Easing.InOutSine)
                    .Then()
                    .ScaleTo(0.6f, 1500, Easing.InOutSine)
                    .Loop();
        }
    }

    /// <summary>
    /// Animated waveform bars for audio visualization feel.
    /// </summary>
    public partial class WaveformBars : CompositeDrawable
    {
        private readonly Container[] bars;
        private readonly int barCount;
        private readonly Color4 barColor;

        public WaveformBars(int count = 5, float width = 4, float spacing = 3, Color4? color = null)
        {
            barCount = count;
            barColor = color ?? VisualEffects.CyanAccent;

            float totalWidth = count * width + (count - 1) * spacing;
            Size = new Vector2(totalWidth, 20);
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;

            bars = new Container[count];

            for (int i = 0; i < count; i++)
            {
                bars[i] = new Container
                {
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Width = width,
                    Height = 5,
                    X = i * (width + spacing),
                    CornerRadius = width / 2,
                    Masking = true,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = ColourInfo.GradientVertical(barColor, barColor.Opacity(0.5f)),
                    }
                };
                AddInternal(bars[i]);
            }
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            var random = new Random();

            for (int i = 0; i < barCount; i++)
            {
                float delay = (float)random.NextDouble() * 200;
                float duration = 400 + (float)random.NextDouble() * 300;
                float targetHeight = 8 + (float)random.NextDouble() * 12;

                bars[i].ResizeHeightTo(5)
                      .Then((int)delay)
                      .ResizeHeightTo(targetHeight, duration, Easing.InOutQuad)
                      .Then()
                      .ResizeHeightTo(5, duration, Easing.InOutQuad)
                      .Loop();
            }
        }
    }

    /// <summary>
    /// A beat indicator that pulses on rhythm.
    /// </summary>
    public partial class BeatIndicator : CompositeDrawable
    {
        private readonly Circle beatCircle;
        private readonly Container glowContainer;
        private readonly Color4 beatColor;

        public BeatIndicator(float size = 24, Color4? color = null)
        {
            Size = new Vector2(size);
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;
            beatColor = color ?? VisualEffects.AmberAccent;

            InternalChildren = new Drawable[]
            {
                glowContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = size / 2,
                    Alpha = 0,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Glow,
                        Colour = beatColor.Opacity(0.8f),
                        Radius = 8,
                    },
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = beatColor.Opacity(0.5f),
                    },
                },
                beatCircle = new Circle
                {
                    RelativeSizeAxes = Axes.Both,
                    Size = new Vector2(0.5f),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Colour = beatColor,
                },
            };
        }

        /// <summary>
        /// Triggers a beat pulse animation.
        /// </summary>
        public void Pulse()
        {
            beatCircle.ScaleTo(1.5f)
                     .ScaleTo(1f, 200, Easing.OutQuint);

            glowContainer.FadeTo(0.8f)
                     .FadeTo(0, 200, Easing.OutQuint);
        }

        /// <summary>
        /// Starts automatic pulsing at the specified BPM.
        /// </summary>
        public void StartAutoPulse(float bpm)
        {
            float beatInterval = 60000f / bpm;

            Scheduler.AddDelayed(() =>
            {
                Pulse();
            }, beatInterval, true);
        }
    }

    /// <summary>
    /// Glowing divider line for section separation.
    /// </summary>
    public partial class GlowingDivider : CompositeDrawable
    {
        public GlowingDivider(bool horizontal = true, Color4? color = null)
        {
            var dividerColor = color ?? VisualEffects.CyanAccent;

            if (horizontal)
            {
                RelativeSizeAxes = Axes.X;
                Height = 1;
            }
            else
            {
                RelativeSizeAxes = Axes.Y;
                Width = 1;
            }

            InternalChild = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientHorizontal(
                    dividerColor.Opacity(0),
                    dividerColor.Opacity(0.8f)),
            }.WithEffect(new GlowEffect
            {
                Colour = dividerColor.Opacity(0.5f),
                BlurSigma = new Vector2(5),
                Strength = 1f,
            });
        }
    }

    /// <summary>
    /// Animated corner accent decoration.
    /// </summary>
    public partial class CornerAccent : CompositeDrawable
    {
        private readonly Box horizontal;
        private readonly Box vertical;

        public CornerAccent(float length = 40, float thickness = 2, Anchor corner = Anchor.TopLeft, Color4? color = null)
        {
            var accentColor = color ?? VisualEffects.CyanAccent;
            Size = new Vector2(length);
            Anchor = corner;
            Origin = corner;

            // Determine rotation based on corner
            float rotationOffset = corner switch
            {
                Anchor.TopRight => 90,
                Anchor.BottomRight => 180,
                Anchor.BottomLeft => 270,
                _ => 0
            };

            InternalChildren = new Drawable[]
            {
                horizontal = new Box
                {
                    Width = length,
                    Height = thickness,
                    Colour = ColourInfo.GradientHorizontal(accentColor, accentColor.Opacity(0)),
                },
                vertical = new Box
                {
                    Width = thickness,
                    Height = length,
                    Colour = ColourInfo.GradientVertical(accentColor, accentColor.Opacity(0)),
                },
            };

            Rotation = rotationOffset;
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Subtle pulsing animation
            this.FadeTo(0.6f)
               .FadeTo(1f, 2000, Easing.InOutSine)
               .Then()
               .FadeTo(0.6f, 2000, Easing.InOutSine)
               .Loop();
        }
    }
}
