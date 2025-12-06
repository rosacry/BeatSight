using System;
using System.Collections.Generic;
using BeatSight.Game.UI.Theming;
using BeatSight.Game.Audio;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Utils;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    public partial class DynamicBackground : CompositeDrawable
    {
        private const int PARTICLE_COUNT = 80;
        private const float CONNECTION_DISTANCE = 100f;
        private const int MAX_CONNECTIONS = 200; // Limit total lines to prevent lag

        private readonly List<Particle> particles = new List<Particle>();
        private readonly List<Box> connectionLines = new List<Box>();
        private Container<Box> linesContainer = null!;
        private Container<Particle> particleContainer = null!;

        [Resolved(CanBeNull = true)]
        private UIAudioController? uiAudio { get; set; }

        [BackgroundDependencyLoader]
        private void load()
        {
            if (uiAudio != null)
                uiAudio.OnClickEvent += Pulse;

            RelativeSizeAxes = Axes.Both;

            // 1. Deep, dark background
            InternalChild = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Background
                    },
                    // Vignette effect
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = ColourInfo.GradientVertical(Color4.Black.Opacity(0.0f), Color4.Black.Opacity(0.6f))
                    },
                    linesContainer = new Container<Box>
                    {
                        RelativeSizeAxes = Axes.Both,
                        Alpha = 0.15f, // Lines are subtle
                        Blending = BlendingParameters.Additive
                    },
                    particleContainer = new Container<Particle>
                    {
                        RelativeSizeAxes = Axes.Both,
                        Blending = BlendingParameters.Additive
                    }
                }
            };

            // Initialize line pool
            for (int i = 0; i < MAX_CONNECTIONS; i++)
            {
                var line = new Box
                {
                    Height = 1.5f,
                    Origin = Anchor.CentreLeft,
                    Colour = UITheme.AccentPrimary,
                    Alpha = 0
                };
                connectionLines.Add(line);
                linesContainer.Add(line);
            }

            // Initialize particles
            for (int i = 0; i < PARTICLE_COUNT; i++)
            {
                var p = new Particle();
                particles.Add(p);
                particleContainer.Add(p);
            }
        }

        public void Glitch(float intensity)
        {
            foreach (var p in particles)
            {
                p.Position += new Vector2(RNG.NextSingle(-intensity, intensity), RNG.NextSingle(-intensity, intensity));
                // Flash color
                p.Colour = RNG.NextBool() ? UITheme.AccentPrimary : UITheme.AccentSecondary;
            }
        }

        public void Pulse()
        {
            foreach (var p in particles)
            {
                p.Pulse();
            }
        }

        protected override void Update()
        {
            base.Update();

            var inputManager = GetContainingInputManager();
            Vector2 mousePos = Vector2.Zero;
            bool active = false;

            if (inputManager != null)
            {
                mousePos = ToLocalSpace(inputManager.CurrentState.Mouse.Position);
                active = true;
            }

            // Update particles
            foreach (var p in particles)
            {
                p.UpdatePhysics(mousePos, DrawSize, active);
            }

            // Update connections
            UpdateConnections();
        }

        private void UpdateConnections()
        {
            int lineIndex = 0;

            // Optimization: Only check i against j > i
            for (int i = 0; i < particles.Count; i++)
            {
                var p1 = particles[i];
                if (p1.DepthZ < 0.5f) continue; // Don't connect background particles, keeps it clean

                for (int j = i + 1; j < particles.Count; j++)
                {
                    var p2 = particles[j];
                    if (p2.DepthZ < 0.5f) continue;

                    float distSq = Vector2.DistanceSquared(p1.Position, p2.Position);
                    float thresholdSq = CONNECTION_DISTANCE * CONNECTION_DISTANCE;

                    if (distSq < thresholdSq)
                    {
                        if (lineIndex >= connectionLines.Count) break;

                        var line = connectionLines[lineIndex];
                        lineIndex++;

                        float dist = MathF.Sqrt(distSq);
                        float alpha = 1f - (dist / CONNECTION_DISTANCE);

                        // Position and rotate line
                        Vector2 diff = p2.Position - p1.Position;
                        float angle = MathF.Atan2(diff.Y, diff.X);

                        line.Position = p1.Position;
                        line.Width = dist;
                        line.Rotation = MathHelper.RadiansToDegrees(angle);
                        line.Alpha = alpha * p1.Alpha * p2.Alpha; // Fade with particle alpha
                        line.Colour = Interpolation.ValueAt(0.5f, p1.Colour, p2.Colour, 0, 1);
                    }
                }
            }

            // Hide unused lines
            for (int i = lineIndex; i < connectionLines.Count; i++)
            {
                connectionLines[i].Alpha = 0;
            }
        }

        private partial class Particle : Circle
        {
            public float DepthZ { get; private set; } // 0.0 (far) to 1.0 (near)

            private Vector2 velocity;
            private float baseSize;
            private Color4 baseColour;
            private double timeOffset;

            public Particle()
            {
                RelativePositionAxes = Axes.None;
                Anchor = Anchor.TopLeft;
                Origin = Anchor.Centre;
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                DepthZ = RNG.NextSingle();
                timeOffset = RNG.NextDouble() * 10000;

                // Size depends on depth
                baseSize = (float)Interpolation.Lerp(2f, 6f, DepthZ);
                Size = new Vector2(baseSize);

                // Speed depends on depth (parallax)
                // Slower, more floating feel
                float speed = (float)Interpolation.Lerp(0.02f, 0.15f, DepthZ);
                velocity = new Vector2(RNG.NextSingle(-1f, 1f), RNG.NextSingle(-1f, 1f)).Normalized() * speed;

                // Color
                // Far particles are darker/faded
                var themeCol = RNG.NextBool() ? UITheme.AccentPrimary : UITheme.AccentSecondary;
                baseColour = themeCol;

                Alpha = (float)Interpolation.Lerp(0.1f, 0.5f, DepthZ);
                Colour = baseColour;
            }
            private bool isInitialized = false;

            public void Pulse()
            {
                this.ScaleTo(1.5f, 50, Easing.OutQuint).Then().ScaleTo(1f, 300, Easing.Out);
                this.FlashColour(Color4.White, 200, Easing.Out);
            }

            public void UpdatePhysics(Vector2 mousePos, Vector2 bounds, bool mouseActive)
            {
                if (bounds.X <= 0 || bounds.Y <= 0) return;

                if (!isInitialized)
                {
                    Position = new Vector2(RNG.NextSingle(0, bounds.X), RNG.NextSingle(0, bounds.Y));
                    isInitialized = true;
                }

                // 1. Base Movement
                Position += velocity;

                // 2. Pulse effect
                double time = Time.Current + timeOffset;
                // Slower breathing pulse
                float pulse = (float)Math.Sin(time * 0.0002) * 0.1f + 1f;
                Size = new Vector2(baseSize * pulse);

                // 3. Mouse Interaction
                if (mouseActive)
                {
                    Vector2 dir = Position - mousePos;
                    float dist = dir.Length;

                    // Attraction radius (Gravity well)
                    float attractRadius = 300f;
                    // Repulsion radius (Personal space)
                    float repelRadius = 80f;

                    if (dist < attractRadius)
                    {
                        Vector2 force = Vector2.Zero;

                        if (dist < repelRadius)
                        {
                            // Strong repulsion - reduced intensity
                            float strength = (1 - (dist / repelRadius)) * 0.5f;
                            force = dir.Normalized() * strength;
                        }
                        else
                        {
                            // Gentle attraction / swirl - reduced intensity
                            float strength = (1 - (dist / attractRadius)) * 0.005f;
                            // Add a bit of tangent force for swirl
                            Vector2 tangent = new Vector2(-dir.Y, dir.X).Normalized();

                            force = -dir.Normalized() * strength + tangent * strength * 0.3f;
                        }

                        // Apply force to velocity (with damping)
                        velocity += force * DepthZ; // Near particles react more
                    }
                }

                // 4. Damping / Speed Limit
                // Lower max speed for calmer feel
                float maxSpeed = (float)Interpolation.Lerp(0.1f, 0.4f, DepthZ);
                if (velocity.Length > maxSpeed)
                {
                    velocity = Vector2.Lerp(velocity, velocity.Normalized() * maxSpeed, 0.05f);
                }

                // Keep them moving
                if (velocity.Length < maxSpeed * 0.2f)
                {
                    velocity = velocity.Normalized() * maxSpeed * 0.2f;
                }                // 5. Screen Wrapping
                float margin = 50f;
                if (Position.X < -margin) Position = new Vector2(bounds.X + margin, Position.Y);
                if (Position.X > bounds.X + margin) Position = new Vector2(-margin, Position.Y);
                if (Position.Y < -margin) Position = new Vector2(Position.X, bounds.Y + margin);
                if (Position.Y > bounds.Y + margin) Position = new Vector2(Position.X, -margin);
            }
        }

        /// <summary>
        /// Unsubscribe from events to prevent memory leaks.
        /// The UIAudioController is a long-lived service, so we must clean up
        /// when this background instance is disposed.
        /// </summary>
        protected override void Dispose(bool isDisposing)
        {
            if (uiAudio != null)
                uiAudio.OnClickEvent -= Pulse;

            base.Dispose(isDisposing);
        }
    }
}
