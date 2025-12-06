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
using osu.Framework.Utils;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A animated countdown timer with visual feedback.
    /// </summary>
    public partial class CountdownTimer : CompositeDrawable
    {
        /// <summary>
        /// Duration of the countdown in seconds.
        /// </summary>
        public int DurationSeconds { get; set; } = 3;

        /// <summary>
        /// Whether to pulse on each second.
        /// </summary>
        public bool PulseOnSecond { get; set; } = true;

        /// <summary>
        /// Accent color.
        /// </summary>
        public Color4 AccentColour { get; set; } = Color4Extensions.FromHex("0ea5e9");

        /// <summary>
        /// Fired when countdown completes.
        /// </summary>
        public Action? OnComplete { get; set; }

        /// <summary>
        /// Fired on each second tick.
        /// </summary>
        public Action<int>? OnTick { get; set; }

        private SpriteText countText = null!;
        private Box progressBar = null!;
        private Container pulseContainer = null!;
        private double startTime;
        private bool isRunning;
        private int lastSecond = -1;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(120);
            Masking = true;
            CornerRadius = 60;

            InternalChildren = new Drawable[]
            {
                pulseContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Child = new Circle
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = AccentColour.Opacity(0.2f),
                    }
                },
                new Circle
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4Extensions.FromHex("374151"),
                    Size = new Vector2(0.9f),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                },
                new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 4,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Y = -10,
                    Width = 0.8f,
                    Masking = true,
                    CornerRadius = 2,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = Color4Extensions.FromHex("1f2937"),
                        },
                        progressBar = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = AccentColour,
                            Width = 1,
                        }
                    }
                },
                countText = new SpriteText
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Font = new FontUsage("Torus", 48, "Bold"),
                    Colour = Color4.White,
                    Text = DurationSeconds.ToString(),
                }
            };
        }

        /// <summary>
        /// Start the countdown.
        /// </summary>
        public void Start()
        {
            startTime = Clock.CurrentTime;
            isRunning = true;
            lastSecond = -1;
            progressBar.Width = 1;
        }

        /// <summary>
        /// Stop the countdown.
        /// </summary>
        public void Stop()
        {
            isRunning = false;
        }

        /// <summary>
        /// Reset the countdown without starting.
        /// </summary>
        public void Reset()
        {
            isRunning = false;
            lastSecond = -1;
            progressBar.Width = 1;
            countText.Text = DurationSeconds.ToString();
        }

        protected override void Update()
        {
            base.Update();

            if (!isRunning) return;

            double elapsed = (Clock.CurrentTime - startTime) / 1000.0;
            double remaining = DurationSeconds - elapsed;

            if (remaining <= 0)
            {
                isRunning = false;
                countText.Text = "GO!";
                countText.ScaleTo(1.5f).ScaleTo(1f, 300, Easing.OutQuad);
                OnComplete?.Invoke();
                return;
            }

            int currentSecond = (int)Math.Ceiling(remaining);
            progressBar.Width = (float)(remaining / DurationSeconds);

            if (currentSecond != lastSecond)
            {
                lastSecond = currentSecond;
                countText.Text = currentSecond.ToString();
                OnTick?.Invoke(currentSecond);

                if (PulseOnSecond)
                {
                    countText.ScaleTo(1.3f).ScaleTo(1f, 200, Easing.OutQuad);
                    pulseContainer.ScaleTo(1.2f).ScaleTo(1f, 400, Easing.OutQuad);
                }
            }
        }
    }

    /// <summary>
    /// An animated score display with rolling numbers.
    /// </summary>
    public partial class ScoreDisplay : CompositeDrawable
    {
        /// <summary>
        /// Current score value.
        /// </summary>
        public long Score
        {
            get => targetScore;
            set => targetScore = value;
        }

        /// <summary>
        /// Score roll animation speed (digits per second).
        /// </summary>
        public float RollSpeed { get; set; } = 50000f;

        /// <summary>
        /// Number of digits to display (padded with zeros).
        /// </summary>
        public int DigitCount { get; set; } = 8;

        /// <summary>
        /// Score color.
        /// </summary>
        public Color4 ScoreColour { get; set; } = Color4.White;

        private long targetScore;
        private double currentScore;
        private SpriteText scoreText = null!;
        private Container glowContainer = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                glowContainer = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                },
                scoreText = new SpriteText
                {
                    Font = new FontUsage("Torus", 36, "Bold"),
                    Colour = ScoreColour,
                    Text = new string('0', DigitCount),
                }
            };
        }

        protected override void Update()
        {
            base.Update();

            if (Math.Abs(currentScore - targetScore) > 0.5)
            {
                float delta = (float)(Clock.ElapsedFrameTime / 1000.0 * RollSpeed);
                if (currentScore < targetScore)
                    currentScore = Math.Min(currentScore + delta, targetScore);
                else
                    currentScore = Math.Max(currentScore - delta, targetScore);

                scoreText.Text = ((long)currentScore).ToString().PadLeft(DigitCount, '0');
            }
        }

        /// <summary>
        /// Add score with visual feedback.
        /// </summary>
        public void AddScore(long amount)
        {
            targetScore += amount;

            // Pulse effect
            scoreText.ScaleTo(1.1f).ScaleTo(1f, 150, Easing.OutQuad);
        }

        /// <summary>
        /// Set score immediately without animation.
        /// </summary>
        public void SetScoreImmediate(long value)
        {
            targetScore = value;
            currentScore = value;
            scoreText.Text = value.ToString().PadLeft(DigitCount, '0');
        }
    }

    /// <summary>
    /// A combo display with animated increments and milestones.
    /// </summary>
    public partial class AnimatedComboDisplay : CompositeDrawable
    {
        /// <summary>
        /// Current combo value.
        /// </summary>
        public int Combo
        {
            get => combo;
            set
            {
                int oldCombo = combo;
                combo = Math.Max(0, value);

                if (combo > oldCombo)
                    onComboIncrease();
                else if (combo == 0 && oldCombo > 0)
                    onComboBreak();

                updateDisplay();
            }
        }

        /// <summary>
        /// Combo milestones for extra effects (e.g., 50, 100, 200).
        /// </summary>
        public int[] Milestones { get; set; } = { 25, 50, 100, 200, 500 };

        /// <summary>
        /// Accent color.
        /// </summary>
        public Color4 AccentColour { get; set; } = Color4Extensions.FromHex("0ea5e9");

        /// <summary>
        /// Milestone color.
        /// </summary>
        public Color4 MilestoneColour { get; set; } = Color4Extensions.FromHex("fbbf24");

        /// <summary>
        /// Fired when combo breaks.
        /// </summary>
        public Action? OnComboBreak { get; set; }

        /// <summary>
        /// Fired when a milestone is reached.
        /// </summary>
        public Action<int>? OnMilestone { get; set; }

        private int combo;
        private SpriteText comboText = null!;
        private SpriteText labelText = null!;
        private Container effectContainer = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                effectContainer = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                },
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, -4),
                    Children = new Drawable[]
                    {
                        comboText = new SpriteText
                        {
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Font = new FontUsage("Torus", 48, "Bold"),
                            Colour = AccentColour,
                            Text = "0",
                        },
                        labelText = new SpriteText
                        {
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Font = new FontUsage("Torus", 14, "Bold"),
                            Colour = Color4Extensions.FromHex("9ca3af"),
                            Text = "COMBO",
                        }
                    }
                }
            };
        }

        private void updateDisplay()
        {
            comboText.Text = combo.ToString();
        }

        private void onComboIncrease()
        {
            // Check for milestone
            foreach (int milestone in Milestones)
            {
                if (combo == milestone)
                {
                    triggerMilestoneEffect();
                    OnMilestone?.Invoke(milestone);
                    return;
                }
            }

            // Regular increment effect
            comboText.ScaleTo(1.2f).ScaleTo(1f, 100, Easing.OutQuad);
        }

        private void triggerMilestoneEffect()
        {
            comboText.Colour = MilestoneColour;
            comboText.ScaleTo(1.5f).ScaleTo(1f, 300, Easing.OutElastic);

            using (comboText.BeginDelayedSequence(500))
            {
                comboText.FadeColour(AccentColour, 300);
            }

            // Burst effect
            var burst = new Circle
            {
                Size = new Vector2(20),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = MilestoneColour,
                Alpha = 0.5f,
            };

            effectContainer.Add(burst);
            burst.ScaleTo(10f, 500, Easing.OutQuad)
                 .FadeOut(500, Easing.OutQuad)
                 .Expire();
        }

        private void onComboBreak()
        {
            OnComboBreak?.Invoke();

            comboText.Colour = Color4Extensions.FromHex("ef4444");
            comboText.ScaleTo(0.5f, 100, Easing.InQuad);

            using (comboText.BeginDelayedSequence(200))
            {
                comboText.FadeColour(AccentColour, 300);
                comboText.ScaleTo(1f, 200, Easing.OutQuad);
            }
        }

        /// <summary>
        /// Increment combo by 1.
        /// </summary>
        public void Increment() => Combo++;

        /// <summary>
        /// Reset combo to 0.
        /// </summary>
        public void Break() => Combo = 0;
    }

    /// <summary>
    /// A stylized hit indicator that shows feedback for note accuracy.
    /// </summary>
    public partial class HitIndicator : CompositeDrawable
    {
        /// <summary>
        /// Show a hit result.
        /// </summary>
        public void ShowHit(GameplayHitResult result)
        {
            var (text, colour) = GetResultDisplay(result);

            var label = new SpriteText
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Font = new FontUsage("Torus", 24, "Bold"),
                Colour = colour,
                Text = text,
                Alpha = 0,
            };

            AddInternal(label);

            label.FadeIn(50)
                 .ScaleTo(0.5f).ScaleTo(1.2f, 100, Easing.OutQuad)
                 .Then()
                 .MoveToY(-30, 400, Easing.OutQuad)
                 .FadeOut(300)
                 .ScaleTo(0.8f, 300)
                 .Expire();
        }

        public static (string text, Color4 colour) GetResultDisplay(GameplayHitResult result)
        {
            return result switch
            {
                GameplayHitResult.Perfect => ("PERFECT", Color4Extensions.FromHex("fbbf24")),
                GameplayHitResult.Great => ("GREAT", Color4Extensions.FromHex("22c55e")),
                GameplayHitResult.Good => ("GOOD", Color4Extensions.FromHex("3b82f6")),
                GameplayHitResult.Ok => ("OK", Color4Extensions.FromHex("a855f7")),
                GameplayHitResult.Miss => ("MISS", Color4Extensions.FromHex("ef4444")),
                _ => ("", Color4.White)
            };
        }
    }

    /// <summary>
    /// Hit result types for accuracy feedback.
    /// </summary>
    public enum GameplayHitResult
    {
        Perfect,
        Great,
        Good,
        Ok,
        Miss
    }

    /// <summary>
    /// An animated streak/multiplier display.
    /// </summary>
    public partial class MultiplierDisplay : CompositeDrawable
    {
        /// <summary>
        /// Current multiplier value.
        /// </summary>
        public float Multiplier
        {
            get => multiplier;
            set
            {
                float oldValue = multiplier;
                multiplier = Math.Max(1f, value);

                if (multiplier > oldValue)
                    onMultiplierIncrease();

                updateDisplay();
            }
        }

        /// <summary>
        /// Max multiplier value.
        /// </summary>
        public float MaxMultiplier { get; set; } = 4f;

        /// <summary>
        /// Accent color at max multiplier.
        /// </summary>
        public Color4 MaxColour { get; set; } = Color4Extensions.FromHex("fbbf24");

        private float multiplier = 1f;
        private SpriteText multiplierText = null!;
        private Box fillBar = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(100, 40);

            InternalChildren = new Drawable[]
            {
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 8,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = Color4Extensions.FromHex("374151"),
                        },
                        fillBar = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = Color4Extensions.FromHex("0ea5e9"),
                            Width = 0,
                        }
                    }
                },
                multiplierText = new SpriteText
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Font = new FontUsage("Torus", 20, "Bold"),
                    Colour = Color4.White,
                    Text = "1.0x",
                }
            };
        }

        private void updateDisplay()
        {
            multiplierText.Text = $"{multiplier:F1}x";

            float progress = (multiplier - 1f) / (MaxMultiplier - 1f);
            fillBar.ResizeWidthTo(progress, 200, Easing.OutQuad);

            // Interpolate color based on multiplier (linear interpolation)
            var startColour = Color4Extensions.FromHex("0ea5e9");
            var colour = new Color4(
                startColour.R + (MaxColour.R - startColour.R) * progress,
                startColour.G + (MaxColour.G - startColour.G) * progress,
                startColour.B + (MaxColour.B - startColour.B) * progress,
                startColour.A + (MaxColour.A - startColour.A) * progress
            );
            fillBar.FadeColour(colour, 200);

            if (multiplier >= MaxMultiplier)
            {
                fillBar.FlashColour(Color4.White, 200);
            }
        }

        private void onMultiplierIncrease()
        {
            multiplierText.ScaleTo(1.2f).ScaleTo(1f, 150, Easing.OutQuad);
        }
    }
}
