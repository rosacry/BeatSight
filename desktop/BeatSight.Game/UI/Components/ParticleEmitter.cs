// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Pooling;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Utils;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A particle emitter for visual effects like sparks, confetti, and hit feedback.
    /// Provides pooled particle rendering for efficient burst effects.
    /// </summary>
    public partial class ParticleEmitter : CompositeDrawable
    {
        /// <summary>
        /// The color of particles.
        /// </summary>
        public Color4 ParticleColour { get; set; } = Color4Extensions.FromHex("00d4ff");

        /// <summary>
        /// Whether particles should use random colors from a palette.
        /// </summary>
        public bool UseRandomColours { get; set; }

        /// <summary>
        /// Color palette for random colors.
        /// </summary>
        public Color4[] ColourPalette { get; set; } = new[]
        {
            Color4Extensions.FromHex("00d4ff"),
            Color4Extensions.FromHex("ff50aa"),
            Color4Extensions.FromHex("00ff88"),
            Color4Extensions.FromHex("ffcc00")
        };

        /// <summary>
        /// Minimum particle size.
        /// </summary>
        public float MinSize { get; set; } = 4f;

        /// <summary>
        /// Maximum particle size.
        /// </summary>
        public float MaxSize { get; set; } = 12f;

        /// <summary>
        /// Minimum particle lifetime in milliseconds.
        /// </summary>
        public double MinLifetime { get; set; } = 400;

        /// <summary>
        /// Maximum particle lifetime in milliseconds.
        /// </summary>
        public double MaxLifetime { get; set; } = 800;

        /// <summary>
        /// Minimum initial velocity.
        /// </summary>
        public float MinVelocity { get; set; } = 100f;

        /// <summary>
        /// Maximum initial velocity.
        /// </summary>
        public float MaxVelocity { get; set; } = 300f;

        /// <summary>
        /// Gravity applied to particles (positive = down).
        /// </summary>
        public float Gravity { get; set; } = 500f;

        /// <summary>
        /// Whether particles should fade out over their lifetime.
        /// </summary>
        public bool FadeOut { get; set; } = true;

        /// <summary>
        /// Whether particles should shrink over their lifetime.
        /// </summary>
        public bool ShrinkOut { get; set; } = true;

        private DrawablePool<Particle> particlePool = null!;
        private Container<Particle> particleContainer = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                particlePool = new DrawablePool<Particle>(50),
                particleContainer = new Container<Particle>
                {
                    RelativeSizeAxes = Axes.Both
                }
            };
        }

        /// <summary>
        /// Emits a burst of particles from a point.
        /// </summary>
        /// <param name="position">The origin point for particles.</param>
        /// <param name="count">Number of particles to emit.</param>
        /// <param name="spread">Angular spread in degrees (360 = all directions).</param>
        /// <param name="baseAngle">Base angle in degrees (0 = right, 90 = down).</param>
        public void Burst(Vector2 position, int count = 10, float spread = 360f, float baseAngle = 0f)
        {
            for (int i = 0; i < count; i++)
            {
                EmitParticle(position, spread, baseAngle);
            }
        }

        /// <summary>
        /// Emits particles in a line between two points.
        /// </summary>
        public void BurstLine(Vector2 start, Vector2 end, int count = 15)
        {
            for (int i = 0; i < count; i++)
            {
                float t = (float)i / Math.Max(1, count - 1);
                Vector2 pos = Vector2.Lerp(start, end, t);
                EmitParticle(pos, 180f, -90f);
            }
        }

        /// <summary>
        /// Emits a ring of particles.
        /// </summary>
        public void BurstRing(Vector2 center, float radius, int count = 20)
        {
            for (int i = 0; i < count; i++)
            {
                float angle = (float)i / count * MathF.PI * 2;
                Vector2 pos = center + new Vector2(MathF.Cos(angle), MathF.Sin(angle)) * radius;
                float outwardAngle = MathHelper.RadiansToDegrees(angle);
                EmitParticle(pos, 30f, outwardAngle);
            }
        }

        private void EmitParticle(Vector2 position, float spread, float baseAngle)
        {
            var particle = particlePool.Get();

            float angle = MathHelper.DegreesToRadians(baseAngle + RNG.NextSingle(-spread / 2, spread / 2));
            float velocity = RNG.NextSingle(MinVelocity, MaxVelocity);

            particle.Configure(
                position: position,
                velocity: new Vector2(MathF.Cos(angle), MathF.Sin(angle)) * velocity,
                colour: UseRandomColours
                    ? ColourPalette[RNG.Next(ColourPalette.Length)]
                    : ParticleColour,
                size: RNG.NextSingle(MinSize, MaxSize),
                lifetime: RNG.NextDouble(MinLifetime, MaxLifetime),
                gravity: Gravity,
                fadeOut: FadeOut,
                shrinkOut: ShrinkOut
            );

            particleContainer.Add(particle);
        }

        /// <summary>
        /// A single particle drawable.
        /// </summary>
        private partial class Particle : PoolableDrawable
        {
            private Box box = null!;

            private Vector2 velocity;
            private float gravity;
            private double lifetime;
            private double elapsed;
            private bool fadeOut;
            private bool shrinkOut;
            private float initialSize;

            [BackgroundDependencyLoader]
            private void load()
            {
                Origin = Anchor.Centre;
                InternalChild = box = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre
                };
            }

            public void Configure(
                Vector2 position,
                Vector2 velocity,
                Color4 colour,
                float size,
                double lifetime,
                float gravity,
                bool fadeOut,
                bool shrinkOut)
            {
                Position = position;
                this.velocity = velocity;
                this.gravity = gravity;
                this.lifetime = lifetime;
                this.fadeOut = fadeOut;
                this.shrinkOut = shrinkOut;
                this.initialSize = size;
                elapsed = 0;

                Size = new Vector2(size);
                Alpha = 1;
                Scale = Vector2.One;
                box.Colour = colour;

                // Random rotation for visual interest
                Rotation = RNG.NextSingle(0, 360);
            }

            protected override void Update()
            {
                base.Update();

                double deltaTime = Clock.ElapsedFrameTime / 1000.0;
                elapsed += Clock.ElapsedFrameTime;

                // Physics update
                velocity.Y += (float)(gravity * deltaTime);
                Position += velocity * (float)deltaTime;
                Rotation += RNG.NextSingle(-180, 180) * (float)deltaTime;

                // Lifetime progress (0 to 1)
                float progress = (float)(elapsed / lifetime);

                if (fadeOut)
                    Alpha = 1f - progress;

                if (shrinkOut)
                    Scale = new Vector2(1f - progress * 0.7f);

                if (elapsed >= lifetime)
                {
                    Expire();
                }
            }
        }
    }

    /// <summary>
    /// A specialized emitter for hit feedback effects.
    /// </summary>
    public partial class HitParticleEmitter : ParticleEmitter
    {
        public HitParticleEmitter()
        {
            MinSize = 3f;
            MaxSize = 8f;
            MinLifetime = 300;
            MaxLifetime = 600;
            MinVelocity = 150f;
            MaxVelocity = 400f;
            Gravity = 600f;
        }

        /// <summary>
        /// Emit particles for a perfect hit.
        /// </summary>
        public void EmitPerfect(Vector2 position)
        {
            ParticleColour = Color4Extensions.FromHex("00ffdc");
            Burst(position, 20, 360f);
        }

        /// <summary>
        /// Emit particles for a great hit.
        /// </summary>
        public void EmitGreat(Vector2 position)
        {
            ParticleColour = Color4Extensions.FromHex("00ff88");
            Burst(position, 15, 360f);
        }

        /// <summary>
        /// Emit particles for a good hit.
        /// </summary>
        public void EmitGood(Vector2 position)
        {
            ParticleColour = Color4Extensions.FromHex("ffcc00");
            Burst(position, 10, 360f);
        }

        /// <summary>
        /// Emit particles for a miss.
        /// </summary>
        public void EmitMiss(Vector2 position)
        {
            ParticleColour = Color4Extensions.FromHex("ff4466");
            Burst(position, 5, 120f, -90f); // Upward sparse burst
        }
    }

    /// <summary>
    /// A confetti emitter for celebration effects.
    /// </summary>
    public partial class ConfettiEmitter : ParticleEmitter
    {
        public ConfettiEmitter()
        {
            UseRandomColours = true;
            ColourPalette = new[]
            {
                Color4Extensions.FromHex("ff4466"),
                Color4Extensions.FromHex("ffaa00"),
                Color4Extensions.FromHex("00ff88"),
                Color4Extensions.FromHex("00d4ff"),
                Color4Extensions.FromHex("ff50aa"),
                Color4Extensions.FromHex("ffcc00")
            };
            MinSize = 6f;
            MaxSize = 14f;
            MinLifetime = 1500;
            MaxLifetime = 3000;
            MinVelocity = 100f;
            MaxVelocity = 250f;
            Gravity = 150f;
        }

        /// <summary>
        /// Emit a celebration burst.
        /// </summary>
        public void Celebrate(Vector2 position, int count = 40)
        {
            Burst(position, count, 120f, -90f);
        }

        /// <summary>
        /// Emit confetti from the top of the screen.
        /// </summary>
        public void CelebrateFromTop(int count = 50)
        {
            for (int i = 0; i < count; i++)
            {
                Vector2 pos = new Vector2(
                    RNG.NextSingle(0, DrawWidth),
                    -20
                );

                // Mostly downward with some spread
                float angle = RNG.NextSingle(-30, 30) + 90; // Pointing down
                float velocity = RNG.NextSingle(MinVelocity, MaxVelocity);

                var particle = new ConfettiParticle
                {
                    Position = pos,
                    Velocity = new Vector2(
                        MathF.Cos(MathHelper.DegreesToRadians(angle)),
                        MathF.Sin(MathHelper.DegreesToRadians(angle))
                    ) * velocity,
                    Colour = ColourPalette[RNG.Next(ColourPalette.Length)],
                    Size = new Vector2(RNG.NextSingle(MinSize, MaxSize), RNG.NextSingle(MinSize * 0.3f, MaxSize * 0.3f)),
                    Lifetime = RNG.NextDouble(MinLifetime, MaxLifetime),
                    Gravity = Gravity
                };

                AddInternal(particle);
            }
        }

        /// <summary>
        /// A rectangular confetti particle that tumbles.
        /// </summary>
        private partial class ConfettiParticle : CompositeDrawable
        {
            public Vector2 Velocity;
            public double Lifetime;
            public float Gravity;

            private double elapsed;
            private float rotationSpeed;

            [BackgroundDependencyLoader]
            private void load()
            {
                Origin = Anchor.Centre;
                Masking = true;
                CornerRadius = 1;
                rotationSpeed = RNG.NextSingle(-360, 360);

                InternalChild = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Colour
                };
            }

            protected override void Update()
            {
                base.Update();

                double deltaTime = Clock.ElapsedFrameTime / 1000.0;
                elapsed += Clock.ElapsedFrameTime;

                Velocity.Y += (float)(Gravity * deltaTime);
                Position += Velocity * (float)deltaTime;
                Rotation += rotationSpeed * (float)deltaTime;

                // Flutter effect
                Velocity.X += RNG.NextSingle(-50, 50) * (float)deltaTime;

                float progress = (float)(elapsed / Lifetime);
                Alpha = 1f - progress * 0.5f;

                if (elapsed >= Lifetime)
                    Expire();
            }
        }
    }

    /// <summary>
    /// A sparkle/star burst emitter for magical effects.
    /// </summary>
    public partial class SparkleEmitter : CompositeDrawable
    {
        public Color4 SparkleColour { get; set; } = Color4Extensions.FromHex("ffcc00");

        private DrawablePool<Sparkle> sparklePool = null!;
        private Container<Sparkle> sparkleContainer = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                sparklePool = new DrawablePool<Sparkle>(30),
                sparkleContainer = new Container<Sparkle>
                {
                    RelativeSizeAxes = Axes.Both
                }
            };
        }

        /// <summary>
        /// Emit sparkles from a point.
        /// </summary>
        public void Emit(Vector2 position, int count = 8)
        {
            for (int i = 0; i < count; i++)
            {
                var sparkle = sparklePool.Get();
                sparkle.Configure(
                    position + new Vector2(RNG.NextSingle(-20, 20), RNG.NextSingle(-20, 20)),
                    SparkleColour,
                    RNG.NextSingle(8, 16),
                    RNG.NextDouble(400, 800)
                );
                sparkleContainer.Add(sparkle);
            }
        }

        /// <summary>
        /// A four-pointed star sparkle.
        /// </summary>
        private partial class Sparkle : PoolableDrawable
        {
            private Box horizontalBar = null!;
            private Box verticalBar = null!;
            private double lifetime;
            private double elapsed;

            [BackgroundDependencyLoader]
            private void load()
            {
                Origin = Anchor.Centre;
                Anchor = Anchor.Centre;

                InternalChildren = new Drawable[]
                {
                    horizontalBar = new Box
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Height = 2
                    },
                    verticalBar = new Box
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Width = 2
                    }
                };
            }

            public void Configure(Vector2 position, Color4 colour, float size, double lifetime)
            {
                Position = position;
                this.lifetime = lifetime;
                elapsed = 0;
                Alpha = 1;
                Scale = Vector2.Zero;

                horizontalBar.Width = size;
                horizontalBar.Colour = colour;
                verticalBar.Height = size;
                verticalBar.Colour = colour;

                // Animate in
                this.ScaleTo(1, lifetime * 0.3, Easing.OutQuint);
                this.RotateTo(RNG.NextSingle(0, 45));
            }

            protected override void Update()
            {
                base.Update();

                elapsed += Clock.ElapsedFrameTime;
                float progress = (float)(elapsed / lifetime);

                if (progress > 0.3f)
                {
                    float fadeProgress = (progress - 0.3f) / 0.7f;
                    Alpha = 1f - fadeProgress;
                    Scale = new Vector2(1f + fadeProgress * 0.5f);
                }

                if (elapsed >= lifetime)
                    Expire();
            }
        }
    }
}
