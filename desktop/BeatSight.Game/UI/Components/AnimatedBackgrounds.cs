// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Utils;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// An animated gradient background with flowing color transitions.
    /// Creates a mesmerizing, music-responsive atmosphere.
    /// </summary>
    public partial class AnimatedGradientBackground : CompositeDrawable
    {
        private const int blob_count = 6;
        private const float base_animation_duration = 20000f;

        private readonly GradientBlob[] blobs = new GradientBlob[blob_count];

        /// <summary>
        /// Primary color for the gradient blobs.
        /// </summary>
        public Color4 PrimaryColour { get; set; } = Color4Extensions.FromHex("00d4ff");

        /// <summary>
        /// Secondary color for the gradient blobs.
        /// </summary>
        public Color4 SecondaryColour { get; set; } = Color4Extensions.FromHex("ff50aa");

        /// <summary>
        /// Tertiary accent color for variety.
        /// </summary>
        public Color4 TertiaryColour { get; set; } = Color4Extensions.FromHex("7c3aed");

        /// <summary>
        /// Background base color (usually dark).
        /// </summary>
        public Color4 BackgroundColour { get; set; } = new Color4(8, 10, 18, 255);

        /// <summary>
        /// Animation speed multiplier. Higher = faster movement.
        /// </summary>
        public float AnimationSpeed { get; set; } = 1f;

        /// <summary>
        /// Intensity of the effect (0-1). Controls blob opacity.
        /// </summary>
        public float Intensity { get; set; } = 0.4f;

        /// <summary>
        /// Whether to react to beat pulses.
        /// </summary>
        public bool BeatReactive { get; set; } = true;

        private Box backgroundBox = null!;
        private Container blobContainer = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                backgroundBox = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = BackgroundColour
                },
                blobContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true
                }
            };

            // Create gradient blobs
            Color4[] colors = { PrimaryColour, SecondaryColour, TertiaryColour };

            for (int i = 0; i < blob_count; i++)
            {
                var blob = new GradientBlob
                {
                    Colour = colors[i % colors.Length].Opacity(Intensity),
                    Size = new Vector2(RNG.NextSingle(300, 600)),
                    Position = new Vector2(
                        RNG.NextSingle(0, 1) * DrawWidth,
                        RNG.NextSingle(0, 1) * DrawHeight
                    ),
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.Centre,
                    BlurSigma = new Vector2(100 + RNG.NextSingle(0, 50))
                };

                blobs[i] = blob;
                blobContainer.Add(blob);
            }
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Start animations for each blob
            for (int i = 0; i < blobs.Length; i++)
            {
                startBlobAnimation(blobs[i], i);
            }
        }

        private void startBlobAnimation(GradientBlob blob, int index)
        {
            // Calculate unique timing for each blob
            float duration = base_animation_duration / AnimationSpeed;
            float offset = index * (duration / blob_count);

            // Random target positions within bounds
            Vector2 startPos = blob.Position;
            Vector2 targetPos = new Vector2(
                RNG.NextSingle(100, DrawWidth - 100),
                RNG.NextSingle(100, DrawHeight - 100)
            );

            // Animate position
            blob.MoveTo(targetPos, duration + offset, Easing.InOutSine)
                .Then()
                .MoveTo(startPos, duration, Easing.InOutSine)
                .Loop();

            // Animate scale for breathing effect
            float scaleVariation = 0.2f + RNG.NextSingle(0, 0.3f);
            blob.ScaleTo(1 + scaleVariation, duration * 0.7f, Easing.InOutQuad)
                .Then()
                .ScaleTo(1 - scaleVariation * 0.5f, duration * 0.7f, Easing.InOutQuad)
                .Loop();

            // Subtle rotation
            float rotationAmount = 10f + RNG.NextSingle(0, 20f);
            blob.RotateTo(rotationAmount, duration * 0.5f, Easing.InOutSine)
                .Then()
                .RotateTo(-rotationAmount, duration * 0.5f, Easing.InOutSine)
                .Loop();
        }

        /// <summary>
        /// Pulse the background in response to a beat.
        /// </summary>
        /// <param name="intensity">Beat intensity (0-1).</param>
        public void OnBeat(float intensity = 1f)
        {
            if (!BeatReactive) return;

            float pulseScale = 1f + (0.1f * intensity);

            foreach (var blob in blobs)
            {
                blob.ScaleTo(pulseScale, 50, Easing.OutQuint)
                    .Then()
                    .ScaleTo(1f, 300, Easing.OutQuint);

                // Brief brightness increase
                var currentColor = (Color4)blob.Colour;
                var brightColor = currentColor.Lighten(0.3f * intensity);
                blob.FadeColour(brightColor, 50)
                    .Then()
                    .FadeColour(currentColor.Opacity(Intensity), 300);
            }
        }

        /// <summary>
        /// Update the color palette.
        /// </summary>
        public void UpdateColours(Color4 primary, Color4 secondary, Color4? tertiary = null)
        {
            PrimaryColour = primary;
            SecondaryColour = secondary;
            TertiaryColour = tertiary ?? new Color4(
                (primary.R + secondary.R) / 2,
                (primary.G + secondary.G) / 2,
                (primary.B + secondary.B) / 2,
                1f
            );

            Color4[] colors = { PrimaryColour, SecondaryColour, TertiaryColour };

            for (int i = 0; i < blobs.Length; i++)
            {
                blobs[i].FadeColour(colors[i % colors.Length].Opacity(Intensity), 500);
            }
        }

        /// <summary>
        /// Set animation speed dynamically (e.g., based on BPM).
        /// </summary>
        public void SetSpeed(float speed)
        {
            AnimationSpeed = Math.Clamp(speed, 0.1f, 5f);
        }

        /// <summary>
        /// A gradient blob element.
        /// </summary>
        private partial class GradientBlob : BufferedContainer
        {
            public new Vector2 BlurSigma
            {
                get => blurSigma;
                set
                {
                    blurSigma = value;
                    ForceRedraw();
                }
            }

            private Vector2 blurSigma = new Vector2(100);

            public GradientBlob()
            {
                Masking = true;
                CornerRadius = float.MaxValue; // Circular
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                Child = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.White
                };

                // Apply blur
                EffectBlending = BlendingParameters.Additive;
                BlurSigma = blurSigma;
            }
        }
    }

    /// <summary>
    /// A mesh-style animated background with interconnected nodes.
    /// Creates a futuristic, tech-inspired aesthetic.
    /// </summary>
    public partial class MeshBackground : CompositeDrawable
    {
        private const int node_count = 25;
        private const float connection_distance = 200f;
        private const float node_speed = 30f;

        private readonly MeshNode[] nodes = new MeshNode[node_count];
        private Container<MeshNode> nodeContainer = null!;
        private Container lineContainer = null!;

        /// <summary>
        /// Color of the mesh nodes and lines.
        /// </summary>
        public Color4 MeshColour { get; set; } = Color4Extensions.FromHex("00d4ff");

        /// <summary>
        /// Opacity of the mesh effect (0-1).
        /// </summary>
        public float MeshOpacity { get; set; } = 0.3f;

        /// <summary>
        /// Whether nodes should glow.
        /// </summary>
        public bool NodesGlow { get; set; } = true;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                lineContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                },
                nodeContainer = new Container<MeshNode>
                {
                    RelativeSizeAxes = Axes.Both
                }
            };

            // Create nodes
            for (int i = 0; i < node_count; i++)
            {
                var node = new MeshNode
                {
                    Size = new Vector2(4 + RNG.NextSingle(0, 4)),
                    Position = new Vector2(
                        RNG.NextSingle(0, 1) * DrawWidth,
                        RNG.NextSingle(0, 1) * DrawHeight
                    ),
                    Colour = MeshColour.Opacity(MeshOpacity),
                    Velocity = new Vector2(
                        RNG.NextSingle(-1, 1) * node_speed,
                        RNG.NextSingle(-1, 1) * node_speed
                    )
                };

                nodes[i] = node;
                nodeContainer.Add(node);
            }
        }

        protected override void Update()
        {
            base.Update();

            float deltaTime = (float)Clock.ElapsedFrameTime / 1000f;

            // Update node positions
            foreach (var node in nodes)
            {
                node.UpdatePosition(deltaTime, DrawSize);
            }

            // Clear and redraw lines
            lineContainer.Clear();

            // Draw connections between nearby nodes
            for (int i = 0; i < nodes.Length; i++)
            {
                for (int j = i + 1; j < nodes.Length; j++)
                {
                    float distance = Vector2.Distance(nodes[i].Position, nodes[j].Position);

                    if (distance < connection_distance)
                    {
                        float opacity = (1 - distance / connection_distance) * MeshOpacity;

                        lineContainer.Add(new MeshLine
                        {
                            Start = nodes[i].Position,
                            End = nodes[j].Position,
                            Colour = MeshColour.Opacity(opacity),
                            LineWidth = 1f
                        });
                    }
                }
            }
        }

        /// <summary>
        /// Pulse the mesh in response to audio.
        /// </summary>
        public void Pulse(float intensity = 1f)
        {
            foreach (var node in nodes)
            {
                node.ScaleTo(1.5f * intensity, 50, Easing.OutQuint)
                    .Then()
                    .ScaleTo(1f, 200, Easing.OutQuint);
            }
        }

        private partial class MeshNode : Circle
        {
            public Vector2 Velocity { get; set; }

            public void UpdatePosition(float deltaTime, Vector2 bounds)
            {
                Vector2 newPos = Position + Velocity * deltaTime;

                // Bounce off edges
                if (newPos.X < 0 || newPos.X > bounds.X)
                    Velocity = new Vector2(-Velocity.X, Velocity.Y);
                if (newPos.Y < 0 || newPos.Y > bounds.Y)
                    Velocity = new Vector2(Velocity.X, -Velocity.Y);

                Position = new Vector2(
                    Math.Clamp(newPos.X, 0, bounds.X),
                    Math.Clamp(newPos.Y, 0, bounds.Y)
                );
            }
        }

        private partial class MeshLine : Box
        {
            public Vector2 Start { get; set; }
            public Vector2 End { get; set; }
            public float LineWidth { get; set; } = 1f;

            protected override void Update()
            {
                base.Update();

                Vector2 delta = End - Start;
                float length = delta.Length;
                float angle = MathF.Atan2(delta.Y, delta.X);

                Position = Start;
                Size = new Vector2(length, LineWidth);
                Rotation = MathHelper.RadiansToDegrees(angle);
                Origin = Anchor.CentreLeft;
            }
        }
    }

    /// <summary>
    /// A wave/ripple background effect emanating from a center point.
    /// Great for beat visualization.
    /// </summary>
    public partial class RippleBackground : CompositeDrawable
    {
        private const int max_ripples = 10;

        private Container rippleContainer = null!;

        /// <summary>
        /// Color of the ripples.
        /// </summary>
        public Color4 RippleColour { get; set; } = Color4Extensions.FromHex("00d4ff");

        /// <summary>
        /// Duration of ripple expansion in milliseconds.
        /// </summary>
        public double RippleDuration { get; set; } = 2000;

        /// <summary>
        /// Maximum radius of ripples.
        /// </summary>
        public float MaxRadius { get; set; } = 500f;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChild = rippleContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };
        }

        /// <summary>
        /// Emit a ripple from the center.
        /// </summary>
        public void EmitRipple(float intensity = 1f)
        {
            if (rippleContainer.Children.Count >= max_ripples)
                return;

            var ripple = new CircularContainer
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Size = new Vector2(10),
                Masking = true,
                BorderThickness = 2f * intensity,
                BorderColour = RippleColour.Opacity(0.8f),
                Child = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Transparent
                }
            };

            rippleContainer.Add(ripple);

            ripple.ScaleTo(MaxRadius / 5f, RippleDuration, Easing.OutQuint)
                  .FadeOut(RippleDuration, Easing.InQuint)
                  .Expire();
        }

        /// <summary>
        /// Emit ripple from a specific point.
        /// </summary>
        public void EmitRippleAt(Vector2 position, float intensity = 1f)
        {
            if (rippleContainer.Children.Count >= max_ripples)
                return;

            var ripple = new CircularContainer
            {
                Position = position,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.Centre,
                Size = new Vector2(10),
                Masking = true,
                BorderThickness = 2f * intensity,
                BorderColour = RippleColour.Opacity(0.8f),
                Child = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Transparent
                }
            };

            rippleContainer.Add(ripple);

            ripple.ScaleTo(MaxRadius / 5f, RippleDuration, Easing.OutQuint)
                  .FadeOut(RippleDuration, Easing.InQuint)
                  .Expire();
        }
    }
}
