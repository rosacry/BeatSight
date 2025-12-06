// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A stylized spectrum/waveform visualizer for audio feedback.
    /// Displays animated bars that react to audio levels.
    /// </summary>
    public partial class AudioVisualizer : CompositeDrawable
    {
        /// <summary>
        /// Number of bars in the visualizer.
        /// </summary>
        public int BarCount { get; set; } = 32;

        /// <summary>
        /// Gap between bars.
        /// </summary>
        public float BarGap { get; set; } = 2f;

        /// <summary>
        /// Minimum bar height (as a ratio of container height).
        /// </summary>
        public float MinBarHeight { get; set; } = 0.05f;

        /// <summary>
        /// Smoothing factor for bar animations (0-1, higher = smoother).
        /// </summary>
        public float Smoothing { get; set; } = 0.3f;

        /// <summary>
        /// Primary color of the bars.
        /// </summary>
        public Color4 PrimaryColour { get; set; } = Color4Extensions.FromHex("0ea5e9");

        /// <summary>
        /// Secondary color for gradient effect.
        /// </summary>
        public Color4 SecondaryColour { get; set; } = Color4Extensions.FromHex("ec4899");

        /// <summary>
        /// Whether to mirror the visualizer (both directions from center).
        /// </summary>
        public bool Mirrored { get; set; }

        /// <summary>
        /// Whether to use gradient coloring based on bar height.
        /// </summary>
        public bool UseGradient { get; set; } = true;

        /// <summary>
        /// Corner radius of the bars.
        /// </summary>
        public float BarCornerRadius { get; set; } = 2f;

        private Container barContainer = null!;
        private readonly List<Container> bars = new List<Container>();
        private readonly float[] currentValues;
        private readonly float[] targetValues;

        public AudioVisualizer()
        {
            currentValues = new float[128];
            targetValues = new float[128];
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChild = barContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
            };

            createBars();
        }

        private void createBars()
        {
            bars.Clear();
            barContainer.Clear();

            float barWidth = (1f - (BarCount - 1) * BarGap / DrawWidth) / BarCount;

            for (int i = 0; i < BarCount; i++)
            {
                var barContainer2 = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.X,
                    Anchor = Mirrored ? Anchor.Centre : Anchor.BottomLeft,
                    Origin = Mirrored ? Anchor.Centre : Anchor.BottomLeft,
                    X = (float)i / BarCount,
                    Width = barWidth,
                    Height = MinBarHeight,
                    CornerRadius = BarCornerRadius,
                    Masking = BarCornerRadius > 0,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = getBarColour(i),
                    }
                };

                bars.Add(barContainer2);
                barContainer.Add(barContainer2);
            }
        }

        private Color4 getBarColour(int index)
        {
            if (!UseGradient)
                return PrimaryColour;

            float t = (float)index / (BarCount - 1);
            // Linear interpolation between primary and secondary colours
            return new Color4(
                PrimaryColour.R + (SecondaryColour.R - PrimaryColour.R) * t,
                PrimaryColour.G + (SecondaryColour.G - PrimaryColour.G) * t,
                PrimaryColour.B + (SecondaryColour.B - PrimaryColour.B) * t,
                PrimaryColour.A + (SecondaryColour.A - PrimaryColour.A) * t
            );
        }

        /// <summary>
        /// Updates the visualizer with new audio data.
        /// </summary>
        /// <param name="values">Array of normalized values (0-1) for each frequency band.</param>
        public void UpdateValues(float[] values)
        {
            for (int i = 0; i < Math.Min(values.Length, targetValues.Length); i++)
            {
                targetValues[i] = Math.Clamp(values[i], 0f, 1f);
            }
        }

        /// <summary>
        /// Sets a simulated value for demo/preview purposes.
        /// </summary>
        public void SetSimulatedValues()
        {
            for (int i = 0; i < BarCount; i++)
            {
                float baseValue = (float)Math.Sin(Clock.CurrentTime / 300.0 + i * 0.3) * 0.3f + 0.4f;
                float noise = (float)Random.Shared.NextDouble() * 0.2f;
                targetValues[i] = Math.Clamp(baseValue + noise, MinBarHeight, 1f);
            }
        }

        protected override void Update()
        {
            base.Update();

            float deltaTime = (float)Clock.ElapsedFrameTime / 1000f;
            float smoothFactor = 1f - (float)Math.Pow(Smoothing, deltaTime * 60f);

            for (int i = 0; i < bars.Count && i < targetValues.Length; i++)
            {
                currentValues[i] = currentValues[i] + (targetValues[i] - currentValues[i]) * smoothFactor;

                float height = Math.Max(MinBarHeight, currentValues[i]);
                bars[i].Height = height;

                if (UseGradient)
                {
                    // Brighter when higher
                    var baseColour = getBarColour(i);
                    bars[i].Colour = baseColour.Lighten(height * 0.3f);
                }
            }
        }
    }

    /// <summary>
    /// A stylized tempo/BPM indicator with pulsing animation.
    /// </summary>
    public partial class BpmIndicator : CompositeDrawable
    {
        /// <summary>
        /// Current BPM value to display.
        /// </summary>
        public double Bpm
        {
            get => bpm;
            set
            {
                bpm = value;
                updatePulseInterval();
            }
        }

        /// <summary>
        /// Accent colour for the indicator.
        /// </summary>
        public Color4 AccentColour { get; set; } = Color4Extensions.FromHex("0ea5e9");

        /// <summary>
        /// Whether to animate the pulse effect.
        /// </summary>
        public bool Animate { get; set; } = true;

        private double bpm = 120;
        private double beatInterval = 500;
        private double lastBeatTime;
        private Container pulseContainer = null!;
        private Box pulseRing = null!;
        private SpriteText bpmText = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(80);
            Masking = true;
            CornerRadius = 12;

            EdgeEffect = new EdgeEffectParameters
            {
                Type = EdgeEffectType.Shadow,
                Colour = AccentColour.Opacity(0.3f),
                Radius = 15,
            };

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4Extensions.FromHex("1f2937"),
                },
                pulseContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Children = new Drawable[]
                    {
                        pulseRing = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = AccentColour,
                            Alpha = 0,
                        },
                    }
                },
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 2),
                    Children = new Drawable[]
                    {
                        bpmText = new SpriteText
                        {
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Font = new FontUsage("Torus", 24, "Bold"),
                            Colour = Color4.White,
                        },
                        new SpriteText
                        {
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Font = new FontUsage("Torus", 10),
                            Colour = Color4Extensions.FromHex("9ca3af"),
                            Text = "BPM"
                        }
                    }
                }
            };

            updatePulseInterval();
        }

        private void updatePulseInterval()
        {
            beatInterval = bpm > 0 ? 60000 / bpm : 500;
            if (bpmText != null)
                bpmText.Text = ((int)bpm).ToString();
        }

        protected override void Update()
        {
            base.Update();

            if (!Animate) return;

            double currentTime = Clock.CurrentTime;
            if (currentTime - lastBeatTime >= beatInterval)
            {
                lastBeatTime = currentTime;
                triggerPulse();
            }
        }

        private void triggerPulse()
        {
            pulseRing
                .FadeIn(beatInterval * 0.1)
                .Then()
                .FadeOut(beatInterval * 0.9);

            this.ScaleTo(1.05f, beatInterval * 0.1, Easing.OutQuad)
                .Then()
                .ScaleTo(1f, beatInterval * 0.9, Easing.InQuad);
        }

        /// <summary>
        /// Manually trigger a beat pulse.
        /// </summary>
        public void TriggerBeat()
        {
            lastBeatTime = Clock.CurrentTime;
            triggerPulse();
        }
    }

    /// <summary>
    /// A circular meter/gauge for displaying values with animated fill.
    /// </summary>
    public partial class CircularMeter : CompositeDrawable
    {
        /// <summary>
        /// Current value (0-1).
        /// </summary>
        public float Value
        {
            get => targetValue;
            set => targetValue = Math.Clamp(value, 0f, 1f);
        }

        /// <summary>
        /// Label text displayed below the value.
        /// </summary>
        public string Label { get; set; } = "";

        /// <summary>
        /// Accent color for the filled portion.
        /// </summary>
        public Color4 AccentColour { get; set; } = Color4Extensions.FromHex("0ea5e9");

        /// <summary>
        /// Background track color.
        /// </summary>
        public Color4 TrackColour { get; set; } = Color4Extensions.FromHex("374151");

        /// <summary>
        /// Width of the circular track.
        /// </summary>
        public float TrackWidth { get; set; } = 8f;

        /// <summary>
        /// Whether to display the percentage text.
        /// </summary>
        public bool ShowPercentage { get; set; } = true;

        /// <summary>
        /// Animation smoothing factor.
        /// </summary>
        public float Smoothing { get; set; } = 0.2f;

        private float targetValue;
        private float currentValue;
        private SpriteText percentageText = null!;
        private SpriteText labelText = null!;
        private Box progressFill = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(100);

            InternalChildren = new Drawable[]
            {
                // Circular background
                new Circle
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4Extensions.FromHex("1f2937"),
                },
                // Progress bar at bottom
                new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Height = TrackWidth,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Y = -15,
                    Width = 0.7f,
                    Masking = true,
                    CornerRadius = TrackWidth / 2,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = TrackColour,
                        },
                        progressFill = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = AccentColour,
                            Width = 0,
                        }
                    }
                },
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 2),
                    Y = -5,
                    Children = new Drawable[]
                    {
                        percentageText = new SpriteText
                        {
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Font = new FontUsage("Torus", 20, "Bold"),
                            Colour = Color4.White,
                        },
                        labelText = new SpriteText
                        {
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Font = new FontUsage("Torus", 10),
                            Colour = Color4Extensions.FromHex("9ca3af"),
                            Text = Label,
                        }
                    }
                }
            };
        }

        protected override void Update()
        {
            base.Update();

            float deltaTime = (float)Clock.ElapsedFrameTime / 1000f;
            float smoothFactor = 1f - (float)Math.Pow(Smoothing, deltaTime * 60f);

            currentValue += (targetValue - currentValue) * smoothFactor;

            progressFill.Width = currentValue;

            if (ShowPercentage)
                percentageText.Text = $"{(int)(currentValue * 100)}%";

            labelText.Text = Label;
        }

        /// <summary>
        /// Immediately sets the value without animation.
        /// </summary>
        public void SetValueImmediate(float value)
        {
            targetValue = currentValue = Math.Clamp(value, 0f, 1f);
        }
    }

    /// <summary>
    /// A stylized accuracy display with animated bar.
    /// </summary>
    public partial class AccuracyDisplay : CompositeDrawable
    {
        /// <summary>
        /// Accuracy value (0-1).
        /// </summary>
        public float Accuracy
        {
            get => accuracy;
            set
            {
                accuracy = Math.Clamp(value, 0f, 1f);
                updateDisplay();
            }
        }

        private float accuracy = 1f;
        private SpriteText percentageText = null!;
        private SpriteText gradeText = null!;
        private Box progressBar = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(120);

            InternalChildren = new Drawable[]
            {
                // Background track (horizontal bar)
                new Container
                {
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Size = new Vector2(100, 8),
                    CornerRadius = 4,
                    Masking = true,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = Color4Extensions.FromHex("374151"),
                        },
                        progressBar = new Box
                        {
                            RelativeSizeAxes = Axes.Y,
                            Width = 100,
                            Colour = Color4Extensions.FromHex("22c55e"),
                        }
                    }
                },
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Y = -10,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 4),
                    Children = new Drawable[]
                    {
                        percentageText = new SpriteText
                        {
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Font = new FontUsage("Torus", 28, "Bold"),
                            Colour = Color4.White,
                        },
                        gradeText = new SpriteText
                        {
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Font = new FontUsage("Torus", 16, "Bold"),
                        }
                    }
                }
            };

            updateDisplay();
        }

        private void updateDisplay()
        {
            percentageText.Text = $"{accuracy * 100:F2}%";

            var (grade, colour) = getGradeAndColour();
            gradeText.Text = grade;
            gradeText.Colour = colour;

            progressBar.Width = 100 * accuracy;
            progressBar.Colour = colour;
        }

        private (string grade, Color4 colour) getGradeAndColour()
        {
            return accuracy switch
            {
                >= 1.0f => ("SS", Color4Extensions.FromHex("fbbf24")),     // Gold
                >= 0.95f => ("S", Color4Extensions.FromHex("f97316")),     // Orange
                >= 0.90f => ("A", Color4Extensions.FromHex("22c55e")),     // Green
                >= 0.80f => ("B", Color4Extensions.FromHex("3b82f6")),     // Blue
                >= 0.70f => ("C", Color4Extensions.FromHex("a855f7")),     // Purple
                _ => ("D", Color4Extensions.FromHex("ef4444")),            // Red
            };
        }
    }
}
