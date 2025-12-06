// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.Textures;
using osu.Framework.Graphics.UserInterface;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A modern circular progress indicator with smooth animations and glow effects.
    /// Inspired by osu!'s loading and progress displays.
    /// </summary>
    public partial class ProgressRing : CompositeDrawable
    {
        protected const float default_size = 64;
        protected const float default_ring_width = 6;
        protected const double animation_duration = 400;
        protected const Easing animation_easing = Easing.OutQuint;

        /// <summary>
        /// The current progress (0 to 1).
        /// </summary>
        public readonly BindableDouble Progress = new BindableDouble();

        /// <summary>
        /// Width of the ring stroke.
        /// </summary>
        public float RingWidth { get; set; } = default_ring_width;

        /// <summary>
        /// Whether to show the percentage text in the center.
        /// </summary>
        public bool ShowPercentage { get; set; } = true;

        /// <summary>
        /// Whether to use gradient color based on progress.
        /// </summary>
        public bool UseProgressGradient { get; set; } = true;

        /// <summary>
        /// Whether to animate progress changes.
        /// </summary>
        public bool AnimateProgress { get; set; } = true;

        /// <summary>
        /// Whether to add glow effect to the ring.
        /// </summary>
        public bool EnableGlow { get; set; } = true;

        private Color4 progressColour = Color4Extensions.FromHex("00d4ff");
        private Color4 backgroundColour = Color4.White.Opacity(0.15f);

        public Color4 ProgressColour
        {
            get => progressColour;
            set
            {
                progressColour = value;
                if (progressArc != null)
                    progressArc.Colour = value;
            }
        }

        public Color4 BackgroundColour
        {
            get => backgroundColour;
            set
            {
                backgroundColour = value;
                if (backgroundRing != null)
                    backgroundRing.Colour = value;
            }
        }

        private CircularProgress backgroundRing = null!;
        private CircularProgress progressArc = null!;
        private CircularProgress glowArc = null!;
        private SpriteText percentageText = null!;
        private Container centerContent = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(default_size);

            InternalChildren = new Drawable[]
            {
                // Background ring
                backgroundRing = new CircularProgress
                {
                    RelativeSizeAxes = Axes.Both,
                    InnerRadius = 1 - (RingWidth / default_size),
                    Colour = backgroundColour,
                    Progress = 1,
                    Rotation = -90
                },

                // Glow layer (behind progress)
                glowArc = new CircularProgress
                {
                    RelativeSizeAxes = Axes.Both,
                    InnerRadius = 1 - (RingWidth * 1.5f / default_size),
                    Colour = progressColour.Opacity(0.3f),
                    Progress = 0,
                    Rotation = -90,
                    Alpha = EnableGlow ? 1 : 0
                },

                // Progress arc
                progressArc = new CircularProgress
                {
                    RelativeSizeAxes = Axes.Both,
                    InnerRadius = 1 - (RingWidth / default_size),
                    Colour = progressColour,
                    Progress = 0,
                    Rotation = -90
                },

                // Center content
                centerContent = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Child = percentageText = new SpriteText
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Font = new FontUsage("Nunito", size: default_size * 0.28f, weight: "Bold"),
                        Colour = Color4.White,
                        Alpha = ShowPercentage ? 1 : 0
                    }
                }
            };

            Progress.BindValueChanged(OnProgressChanged, true);
        }

        private void OnProgressChanged(ValueChangedEvent<double> e)
        {
            double newProgress = Math.Clamp(e.NewValue, 0, 1);

            if (AnimateProgress)
            {
                progressArc.ProgressTo(newProgress, animation_duration, animation_easing);
                glowArc.ProgressTo(newProgress, animation_duration, animation_easing);
            }
            else
            {
                progressArc.Progress = newProgress;
                glowArc.Progress = newProgress;
            }

            // Update color based on progress
            if (UseProgressGradient)
            {
                Color4 targetColour = GetColourForProgress(newProgress);
                progressArc.FadeColour(targetColour, animation_duration);
                glowArc.FadeColour(targetColour.Opacity(0.3f), animation_duration);
            }

            // Update percentage text
            if (ShowPercentage)
            {
                percentageText.Text = $"{(int)(newProgress * 100)}%";
            }

            // Pulse effect at completion
            if (newProgress >= 1 && e.OldValue < 1)
            {
                OnComplete();
            }
        }

        /// <summary>
        /// Called when progress reaches 100%.
        /// </summary>
        protected virtual void OnComplete()
        {
            this.ScaleTo(1.15f, 200, Easing.OutQuint)
                .Then()
                .ScaleTo(1f, 300, Easing.OutQuint);

            progressArc.FlashColour(Color4.White, 400);
            glowArc.FadeTo(0.6f, 100).Then().FadeTo(EnableGlow ? 1 : 0, 300);
        }

        /// <summary>
        /// Gets the gradient color for a given progress value.
        /// </summary>
        protected virtual Color4 GetColourForProgress(double progress) => progress switch
        {
            < 0.25 => Color4Extensions.FromHex("ff4466"),  // Red
            < 0.50 => Color4Extensions.FromHex("ffaa00"),  // Orange  
            < 0.75 => Color4Extensions.FromHex("ffcc00"),  // Yellow
            < 0.90 => Color4Extensions.FromHex("00d4ff"),  // Cyan
            _ => Color4Extensions.FromHex("00ff88")        // Green
        };

        /// <summary>
        /// Sets custom content in the center (replaces percentage text).
        /// </summary>
        public void SetCenterContent(Drawable content)
        {
            percentageText.Alpha = 0;
            centerContent.Add(content);
        }
    }

    /// <summary>
    /// An indeterminate loading ring with spinning animation.
    /// </summary>
    public partial class LoadingRing : CompositeDrawable
    {
        private const float default_size = 48;
        private const float ring_width = 4;
        private const double rotation_duration = 1200;

        private Container spinnerContainer = null!;
        private CircularProgress arc = null!;
        private CircularProgress trailArc = null!;

        public Color4 SpinnerColour { get; set; } = Color4Extensions.FromHex("00d4ff");

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(default_size);

            InternalChild = spinnerContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    // Trail
                    trailArc = new CircularProgress
                    {
                        RelativeSizeAxes = Axes.Both,
                        InnerRadius = 1 - (ring_width / default_size),
                        Colour = SpinnerColour.Opacity(0.2f),
                        Progress = 0.7,
                        Rotation = -90
                    },

                    // Main arc
                    arc = new CircularProgress
                    {
                        RelativeSizeAxes = Axes.Both,
                        InnerRadius = 1 - (ring_width / default_size),
                        Colour = SpinnerColour,
                        Progress = 0.25,
                        Rotation = -90
                    }
                }
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            StartSpinning();
        }

        public void StartSpinning()
        {
            spinnerContainer.RotateTo(0)
                .RotateTo(360, rotation_duration)
                .Loop();

            // Pulsing arc size
            arc.ProgressTo(0.15).ProgressTo(0.35, rotation_duration / 2).Loop();
        }

        public void StopSpinning()
        {
            spinnerContainer.ClearTransforms();
            arc.ClearTransforms();
        }
    }

    /// <summary>
    /// A download/upload progress ring with speed display.
    /// </summary>
    public partial class TransferProgressRing : ProgressRing
    {
        public string SpeedText
        {
            get => speedLabel?.Text.ToString() ?? "";
            set
            {
                if (speedLabel != null)
                    speedLabel.Text = value;
            }
        }

        private SpriteText speedLabel = null!;

        protected override void LoadComplete()
        {
            base.LoadComplete();

            ShowPercentage = false;

            SetCenterContent(new FillFlowContainer
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 2),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Font = new FontUsage("Nunito", size: 12, weight: "Bold"),
                        Colour = Color4.White
                    },
                    speedLabel = new SpriteText
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Font = new FontUsage("Nunito", size: 9),
                        Colour = Color4.White.Opacity(0.7f)
                    }
                }
            });
        }
    }

    /// <summary>
    /// A skill/stat ring for displaying metrics with labels.
    /// </summary>
    public partial class StatRing : CompositeDrawable
    {
        private const float default_size = 80;

        public string Label { get; init; } = "";
        public double Value { get; init; }
        public double MaxValue { get; init; } = 100;
        public Color4 RingColour { get; init; } = Color4Extensions.FromHex("00d4ff");

        private ProgressRing progressRing = null!;
        private SpriteText valueText = null!;
        private SpriteText labelText = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(default_size);
            AutoSizeAxes = Axes.Y;

            InternalChild = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Y,
                Width = default_size,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    new Container
                    {
                        Size = new Vector2(default_size),
                        Children = new Drawable[]
                        {
                            progressRing = new ProgressRing
                            {
                                RelativeSizeAxes = Axes.Both,
                                ProgressColour = RingColour,
                                ShowPercentage = false,
                                UseProgressGradient = false
                            },
                            valueText = new SpriteText
                            {
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                                Font = new FontUsage("Nunito", size: 18, weight: "Bold"),
                                Colour = Color4.White
                            }
                        }
                    },
                    labelText = new SpriteText
                    {
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Font = new FontUsage("Nunito", size: 11),
                        Colour = Color4.White.Opacity(0.7f),
                        Text = Label
                    }
                }
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Animate the ring filling
            progressRing.Progress.Value = Value / MaxValue;
            valueText.Text = Value.ToString("N0");
        }
    }

    /// <summary>
    /// A health/stamina bar styled as a horizontal progress bar with glow.
    /// </summary>
    public partial class GlowingProgressBar : CompositeDrawable
    {
        private const float default_height = 8;
        private const float corner_radius = 4;

        public readonly BindableDouble Progress = new BindableDouble();

        public Color4 BarColour { get; set; } = Color4Extensions.FromHex("00d4ff");
        public bool AnimateChanges { get; set; } = true;

        private Box backgroundBar = null!;
        private Box progressBar = null!;
        private Box glowBar = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Height = default_height;
            Masking = true;
            CornerRadius = corner_radius;

            InternalChildren = new Drawable[]
            {
                backgroundBar = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.White.Opacity(0.1f)
                },
                glowBar = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 0,
                    Colour = BarColour.Opacity(0.4f),
                    Blending = BlendingParameters.Additive
                },
                progressBar = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 0,
                    Colour = BarColour
                }
            };

            Progress.BindValueChanged(e =>
            {
                float width = (float)Math.Clamp(e.NewValue, 0, 1) * DrawWidth;

                if (AnimateChanges)
                {
                    progressBar.ResizeWidthTo(width, 300, Easing.OutQuint);
                    glowBar.ResizeWidthTo(width, 300, Easing.OutQuint);
                }
                else
                {
                    progressBar.Width = width;
                    glowBar.Width = width;
                }
            }, true);
        }
    }
}
