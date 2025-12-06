// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Localisation;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// An animated counter that smoothly rolls between values, inspired by osu!'s
    /// score and combo counters. Supports various number formats and visual styles.
    /// </summary>
    public partial class RollingCounter<T> : CompositeDrawable where T : struct, IEquatable<T>
    {
        protected const double default_roll_duration = 600;
        protected const Easing default_easing = Easing.OutQuint;

        /// <summary>
        /// The current displayed value (may be mid-animation).
        /// </summary>
        public readonly Bindable<T> DisplayedValue = new Bindable<T>();

        /// <summary>
        /// The target value to animate towards.
        /// </summary>
        public readonly Bindable<T> TargetValue = new Bindable<T>();

        /// <summary>
        /// Duration of the rolling animation.
        /// </summary>
        public double RollDuration { get; set; } = default_roll_duration;

        /// <summary>
        /// Easing function for the animation.
        /// </summary>
        public Easing RollEasing { get; set; } = default_easing;

        /// <summary>
        /// Whether to show a leading plus sign for positive changes.
        /// </summary>
        public bool ShowPlusSign { get; set; }

        /// <summary>
        /// Whether to add glow effect when value increases.
        /// </summary>
        public bool GlowOnIncrease { get; set; } = true;

        /// <summary>
        /// Format string for displaying the value.
        /// </summary>
        public string Format { get; set; } = "{0}";

        protected SpriteText DisplayText = null!;
        protected Container GlowContainer = null!;

        private Color4 textColour = Color4.White;
        private Color4 increaseColour = Color4Extensions.FromHex("00ff88");
        private Color4 decreaseColour = Color4Extensions.FromHex("ff4466");

        public Color4 TextColour
        {
            get => textColour;
            set
            {
                textColour = value;
                if (DisplayText != null)
                    DisplayText.Colour = value;
            }
        }

        public Color4 IncreaseColour
        {
            get => increaseColour;
            set => increaseColour = value;
        }

        public Color4 DecreaseColour
        {
            get => decreaseColour;
            set => decreaseColour = value;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;

            InternalChild = GlowContainer = new Container
            {
                AutoSizeAxes = Axes.Both,
                Child = DisplayText = CreateText()
            };

            DisplayedValue.BindValueChanged(v => UpdateDisplay(v.NewValue), true);
            TargetValue.BindValueChanged(v => AnimateToTarget(v.OldValue, v.NewValue), true);
        }

        protected virtual SpriteText CreateText() => new SpriteText
        {
            Font = new FontUsage("Nunito", size: 32, weight: "Bold"),
            Colour = textColour,
            UseFullGlyphHeight = false
        };

        protected virtual void UpdateDisplay(T value)
        {
            DisplayText.Text = FormatValue(value);
        }

        protected virtual LocalisableString FormatValue(T value)
        {
            return string.Format(Format, value);
        }

        protected virtual void AnimateToTarget(T oldValue, T newValue)
        {
            // Override in derived classes for type-specific animation
            DisplayedValue.Value = newValue;
        }

        /// <summary>
        /// Sets the value immediately without animation.
        /// </summary>
        public void SetValueInstant(T value)
        {
            TargetValue.Value = value;
            DisplayedValue.Value = value;
            this.FinishTransforms(true);
        }

        /// <summary>
        /// Triggers a visual pulse effect.
        /// </summary>
        public void Pulse()
        {
            GlowContainer.ScaleTo(1.2f).ScaleTo(1f, 400, Easing.OutQuint);
        }
    }

    /// <summary>
    /// A rolling counter specialized for integer values.
    /// </summary>
    public partial class RollingIntCounter : RollingCounter<int>
    {
        public bool UseCommaSeparator { get; set; } = true;

        protected override LocalisableString FormatValue(int value)
        {
            string formatted = UseCommaSeparator
                ? value.ToString("N0")
                : value.ToString();

            if (ShowPlusSign && value > 0)
                formatted = "+" + formatted;

            return formatted;
        }

        protected override void AnimateToTarget(int oldValue, int newValue)
        {
            bool isIncrease = newValue > oldValue;

            // Apply glow effect
            if (GlowOnIncrease && isIncrease && newValue != 0)
            {
                DisplayText.FadeColour(IncreaseColour, 100)
                    .Then()
                    .FadeColour(TextColour, RollDuration - 100);

                GlowContainer.ScaleTo(1.1f, 100, Easing.OutQuint)
                    .Then()
                    .ScaleTo(1f, RollDuration - 100, Easing.OutQuint);
            }
            else if (newValue < oldValue)
            {
                DisplayText.FadeColour(DecreaseColour, 100)
                    .Then()
                    .FadeColour(TextColour, RollDuration - 100);
            }

            // Animate the value
            this.TransformTo(nameof(DisplayedValue), newValue, RollDuration, RollEasing);
        }
    }

    /// <summary>
    /// A rolling counter specialized for double/float values.
    /// </summary>
    public partial class RollingDoubleCounter : RollingCounter<double>
    {
        public int DecimalPlaces { get; set; } = 2;
        public string Suffix { get; set; } = string.Empty;

        protected override LocalisableString FormatValue(double value)
        {
            string formatted = value.ToString($"N{DecimalPlaces}");

            if (ShowPlusSign && value > 0)
                formatted = "+" + formatted;

            return formatted + Suffix;
        }

        protected override void AnimateToTarget(double oldValue, double newValue)
        {
            bool isIncrease = newValue > oldValue;

            if (GlowOnIncrease && isIncrease)
            {
                DisplayText.FadeColour(IncreaseColour, 100)
                    .Then()
                    .FadeColour(TextColour, RollDuration - 100);

                GlowContainer.ScaleTo(1.1f, 100, Easing.OutQuint)
                    .Then()
                    .ScaleTo(1f, RollDuration - 100, Easing.OutQuint);
            }
            else if (newValue < oldValue)
            {
                DisplayText.FadeColour(DecreaseColour, 100)
                    .Then()
                    .FadeColour(TextColour, RollDuration - 100);
            }

            this.TransformTo(nameof(DisplayedValue), newValue, RollDuration, RollEasing);
        }
    }

    /// <summary>
    /// A rolling counter for displaying percentages.
    /// </summary>
    public partial class RollingPercentageCounter : RollingDoubleCounter
    {
        public RollingPercentageCounter()
        {
            DecimalPlaces = 1;
            Suffix = "%";
        }
    }

    /// <summary>
    /// A rolling counter for displaying time in MM:SS or HH:MM:SS format.
    /// </summary>
    public partial class RollingTimeCounter : RollingCounter<TimeSpan>
    {
        public bool ShowHours { get; set; }
        public bool ShowMilliseconds { get; set; }

        protected override LocalisableString FormatValue(TimeSpan value)
        {
            if (ShowMilliseconds)
                return ShowHours
                    ? $"{(int)value.TotalHours:D2}:{value.Minutes:D2}:{value.Seconds:D2}.{value.Milliseconds / 10:D2}"
                    : $"{(int)value.TotalMinutes:D2}:{value.Seconds:D2}.{value.Milliseconds / 10:D2}";

            return ShowHours
                ? $"{(int)value.TotalHours:D2}:{value.Minutes:D2}:{value.Seconds:D2}"
                : $"{(int)value.TotalMinutes:D2}:{value.Seconds:D2}";
        }

        protected override void AnimateToTarget(TimeSpan oldValue, TimeSpan newValue)
        {
            // For time, simply set the value immediately (animation not straightforward for TimeSpan)
            // A more complex implementation could use a helper double bindable for interpolation
            DisplayedValue.Value = newValue;
        }
    }

    /// <summary>
    /// A stylized score counter with larger font and optional glow effects.
    /// </summary>
    public partial class ScoreCounter : RollingIntCounter
    {
        public int MinDigits { get; set; } = 6;

        public ScoreCounter()
        {
            RollDuration = 800;
            UseCommaSeparator = false;
        }

        protected override SpriteText CreateText() => new SpriteText
        {
            Font = new FontUsage("Nunito", size: 48, weight: "ExtraBold"),
            Colour = TextColour,
            UseFullGlyphHeight = false,
            Shadow = true,
            ShadowColour = Color4.Black.Opacity(0.5f),
            ShadowOffset = new Vector2(0, 2)
        };

        protected override LocalisableString FormatValue(int value)
        {
            return value.ToString().PadLeft(MinDigits, '0');
        }
    }

    /// <summary>
    /// A combo counter with pop animation on increases.
    /// </summary>
    public partial class ComboCounter : RollingIntCounter
    {
        public ComboCounter()
        {
            RollDuration = 200;
            UseCommaSeparator = false;
            Format = "{0}x";
        }

        protected override SpriteText CreateText() => new SpriteText
        {
            Font = new FontUsage("Nunito", size: 40, weight: "Bold"),
            Colour = TextColour,
            UseFullGlyphHeight = false
        };

        protected override void AnimateToTarget(int oldValue, int newValue)
        {
            if (newValue > oldValue)
            {
                // Pop effect on combo increase
                float scaleFactor = 1f + Math.Min((newValue - oldValue) * 0.05f, 0.3f);

                GlowContainer.ScaleTo(scaleFactor, 50, Easing.OutQuint)
                    .Then()
                    .ScaleTo(1f, 200, Easing.OutQuint);

                DisplayText.FadeColour(IncreaseColour, 50)
                    .Then()
                    .FadeColour(TextColour, 200);
            }
            else if (newValue == 0 && oldValue > 0)
            {
                // Combo break effect
                GlowContainer.ScaleTo(0.8f, 100)
                    .Then()
                    .ScaleTo(1f, 300, Easing.OutElastic);

                DisplayText.FadeColour(DecreaseColour, 100)
                    .Then()
                    .FadeColour(TextColour, 300);
            }

            base.AnimateToTarget(oldValue, newValue);
        }
    }

    /// <summary>
    /// An accuracy counter with color coding based on accuracy level.
    /// </summary>
    public partial class AccuracyCounter : RollingPercentageCounter
    {
        public double GoodThreshold { get; set; } = 95;
        public double PerfectThreshold { get; set; } = 99;

        public Color4 PerfectColour { get; set; } = Color4Extensions.FromHex("ffcc00");
        public Color4 GoodColour { get; set; } = Color4Extensions.FromHex("00ff88");
        public Color4 NormalColour { get; set; } = Color4.White;

        public AccuracyCounter()
        {
            RollDuration = 400;
            DecimalPlaces = 2;
        }

        protected override void UpdateDisplay(double value)
        {
            base.UpdateDisplay(value);

            // Color based on accuracy level
            Color4 targetColour = value >= PerfectThreshold ? PerfectColour
                : value >= GoodThreshold ? GoodColour
                : NormalColour;

            DisplayText.FadeColour(targetColour, 200);
        }
    }
}
