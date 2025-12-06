using System;
using System.Collections.Generic;
using BeatSight.Game.UI.Theming;
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
    /// <summary>
    /// A container that displays animated wave effects, similar to osu!'s overlay containers.
    /// Can be used for overlay backgrounds, transitions, or decorative elements.
    /// </summary>
    public partial class WaveContainer : VisibilityContainer
    {
        public const float WAVE_HEIGHT = 180f;
        public const int WAVE_COUNT = 4;

        private readonly Container waveContainer;
        private readonly List<Wave> waves = new();
        private readonly Box backgroundDim;
        private readonly Container contentContainer;

        protected override Container<Drawable> Content => contentContainer;

        /// <summary>
        /// The color of the wave gradient (from this color to transparent).
        /// </summary>
        public Color4 WaveColour { get; set; } = DesignSystem.ColorSurfaceElevated;

        /// <summary>
        /// The opacity of the background dim behind waves.
        /// </summary>
        public float DimOpacity { get; set; } = 0.6f;

        /// <summary>
        /// Whether waves animate continuously.
        /// </summary>
        public bool AnimateWaves { get; set; } = true;

        /// <summary>
        /// Anchor position for waves (top or bottom).
        /// </summary>
        public Anchor WaveAnchor { get; set; } = Anchor.BottomLeft;

        public WaveContainer()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                backgroundDim = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black,
                    Alpha = 0
                },
                waveContainer = new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Height = WAVE_HEIGHT,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft
                },
                contentContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                }
            };
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            createWaves();
        }

        private void createWaves()
        {
            waveContainer.Anchor = WaveAnchor;
            waveContainer.Origin = WaveAnchor;

            // Create multiple wave layers with varying properties
            Color4[] waveColours =
            {
                WaveColour.Opacity(0.3f),
                WaveColour.Opacity(0.5f),
                WaveColour.Opacity(0.7f),
                WaveColour.Opacity(0.9f)
            };

            float[] heights = { 0.4f, 0.6f, 0.8f, 1.0f };
            double[] durations = { 8000, 6000, 5000, 4000 };

            for (int i = 0; i < WAVE_COUNT; i++)
            {
                var wave = new Wave(waveColours[i], heights[i], durations[i], WaveAnchor);
                waves.Add(wave);
                waveContainer.Add(wave);
            }
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (AnimateWaves)
            {
                foreach (var wave in waves)
                    wave.StartAnimation();
            }
        }

        protected override void PopIn()
        {
            backgroundDim.FadeTo(DimOpacity, 400, Easing.OutQuint);

            // Stagger wave animations
            for (int i = 0; i < waves.Count; i++)
            {
                var wave = waves[i];
                var delay = i * 50;

                wave.Delay(delay)
                    .MoveToY(0, 400, Easing.OutQuint)
                    .FadeIn(300);
            }

            contentContainer.Delay(200).FadeIn(300, Easing.OutQuint);
        }

        protected override void PopOut()
        {
            backgroundDim.FadeOut(400, Easing.OutQuint);
            contentContainer.FadeOut(200, Easing.OutQuint);

            // Reverse wave animation
            for (int i = waves.Count - 1; i >= 0; i--)
            {
                var wave = waves[i];
                var delay = (waves.Count - 1 - i) * 50;

                wave.Delay(delay)
                    .MoveToY(wave.Height, 300, Easing.InQuint)
                    .FadeOut(200);
            }
        }

        /// <summary>
        /// Individual wave element with sine-wave movement animation.
        /// </summary>
        private partial class Wave : CompositeDrawable
        {
            private readonly Color4 colour;
            private readonly float heightRatio;
            private readonly double animationDuration;
            private readonly Anchor anchor;

            private Container waveShape = null!;
            private bool isAnimating;

            public Wave(Color4 colour, float heightRatio, double animationDuration, Anchor anchor)
            {
                this.colour = colour;
                this.heightRatio = heightRatio;
                this.animationDuration = animationDuration;
                this.anchor = anchor;
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                RelativeSizeAxes = Axes.X;
                Height = WAVE_HEIGHT * heightRatio;
                Anchor = anchor;
                Origin = anchor;
                Alpha = 0;
                Y = Height; // Start hidden

                // Wave shape using multiple overlapping circles/curves
                InternalChild = waveShape = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Children = new Drawable[]
                    {
                        // Main wave body
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = ColourInfo.GradientVertical(
                                colour,
                                colour.Opacity(0f)
                            ),
                            Anchor = anchor,
                            Origin = anchor
                        },
                        // Subtle gradient overlay for depth
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = ColourInfo.GradientHorizontal(
                                Color4.White.Opacity(0.05f),
                                Color4.Transparent
                            ),
                            Blending = BlendingParameters.Additive
                        }
                    }
                };
            }

            public void StartAnimation()
            {
                if (isAnimating) return;
                isAnimating = true;
                animate();
            }

            public void StopAnimation()
            {
                isAnimating = false;
                waveShape.ClearTransforms();
            }

            private void animate()
            {
                if (!isAnimating) return;

                // Gentle horizontal sway
                float offset = RNG.NextSingle(-10f, 10f);

                waveShape.MoveToX(offset, animationDuration / 2, Easing.InOutSine)
                    .Then()
                    .MoveToX(-offset, animationDuration / 2, Easing.InOutSine)
                    .OnComplete(_ => animate());
            }
        }
    }

    /// <summary>
    /// A simplified wave line effect for decorative borders or separators.
    /// </summary>
    public partial class WaveLine : CompositeDrawable
    {
        private Color4 colour = DesignSystem.ColorAccentPrimary;
        private float amplitude = 5f;
        private double animationDuration = 2000;

        private Container waveContainer = null!;

        public new Color4 Colour
        {
            get => colour;
            set
            {
                colour = value;
                if (IsLoaded)
                    updateColour();
            }
        }

        public float Amplitude
        {
            get => amplitude;
            set => amplitude = value;
        }

        public double AnimationDuration
        {
            get => animationDuration;
            set => animationDuration = Math.Max(100, value);
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            Height = amplitude * 2 + 2;

            InternalChild = waveContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 2,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Child = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = colour
                }
            };

            startAnimation();
        }

        private void updateColour()
        {
            if (waveContainer?.Child is Box box)
                box.Colour = colour;
        }

        private void startAnimation()
        {
            waveContainer.Loop(c =>
                c.MoveToY(-amplitude, animationDuration / 2, Easing.InOutSine)
                    .Then()
                    .MoveToY(amplitude, animationDuration / 2, Easing.InOutSine)
            );
        }
    }

    /// <summary>
    /// Animated shimmer effect overlay for loading states or highlights.
    /// </summary>
    public partial class ShimmerOverlay : CompositeDrawable
    {
        private Color4 shimmerColour = Color4.White;
        private double animationDuration = 1500;
        private float shimmerWidth = 0.3f;

        private Box shimmerBox = null!;

        public Color4 ShimmerColour
        {
            get => shimmerColour;
            set => shimmerColour = value;
        }

        public double AnimationDuration
        {
            get => animationDuration;
            set => animationDuration = Math.Max(100, value);
        }

        /// <summary>
        /// Width of shimmer band as ratio of container width.
        /// </summary>
        public float ShimmerWidth
        {
            get => shimmerWidth;
            set => shimmerWidth = Math.Clamp(value, 0.1f, 0.5f);
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;
            Masking = true;

            InternalChild = shimmerBox = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 200,
                Colour = shimmerColour.Opacity(0.3f),
                Blending = BlendingParameters.Additive,
                X = -200
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            startShimmer();
        }

        private void startShimmer()
        {
            shimmerBox.Width = DrawWidth * shimmerWidth;
            shimmerBox.X = -shimmerBox.Width;

            shimmerBox.Loop(b =>
                b.MoveToX(DrawWidth + shimmerBox.Width, animationDuration, Easing.None)
                    .Then()
                    .MoveToX(-shimmerBox.Width)
                    .Delay(500)
            );
        }

        protected override void Update()
        {
            base.Update();

            // Update shimmer width if container size changes
            if (Math.Abs(shimmerBox.Width - DrawWidth * shimmerWidth) > 1)
            {
                shimmerBox.Width = DrawWidth * shimmerWidth;
            }
        }
    }
}
