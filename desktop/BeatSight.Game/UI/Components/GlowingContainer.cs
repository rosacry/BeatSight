using System;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A container that provides customizable glow effects on hover or always-on.
    /// Inspired by osu!'s glowing UI elements for premium visual feedback.
    /// </summary>
    public partial class GlowingContainer : Container
    {
        private Color4 glowColour = DesignSystem.ColorAccentPrimary;
        private float glowRadius = 20f;
        private float glowIntensity = 0.5f;
        private bool glowOnHover = true;
        private bool alwaysGlow;
        private float hoverScale = 1.02f;

        private Container glowContainer = null!;

        /// <summary>
        /// The color of the glow effect.
        /// </summary>
        public Color4 GlowColour
        {
            get => glowColour;
            set
            {
                glowColour = value;
                if (glowContainer != null)
                    updateGlow();
            }
        }

        /// <summary>
        /// The radius/spread of the glow effect.
        /// </summary>
        public float GlowRadius
        {
            get => glowRadius;
            set
            {
                glowRadius = value;
                if (glowContainer != null)
                    updateGlow();
            }
        }

        /// <summary>
        /// The intensity/opacity of the glow (0-1).
        /// </summary>
        public float GlowIntensity
        {
            get => glowIntensity;
            set
            {
                glowIntensity = Math.Clamp(value, 0f, 1f);
                if (glowContainer != null)
                    updateGlow();
            }
        }

        /// <summary>
        /// Whether to show glow only on hover.
        /// </summary>
        public bool GlowOnHover
        {
            get => glowOnHover;
            set
            {
                glowOnHover = value;
                if (glowContainer != null)
                    updateGlow();
            }
        }

        /// <summary>
        /// Whether to always show the glow effect.
        /// </summary>
        public bool AlwaysGlow
        {
            get => alwaysGlow;
            set
            {
                alwaysGlow = value;
                if (glowContainer != null)
                    updateGlow();
            }
        }

        /// <summary>
        /// Scale factor when hovered.
        /// </summary>
        public float HoverScale
        {
            get => hoverScale;
            set => hoverScale = value;
        }

        public GlowingContainer()
        {
            Masking = true;
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Wrap content in glow container
            var existingChildren = InternalChildren;
            ClearInternal(false);

            glowContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = Color4.Transparent,
                    Radius = glowRadius,
                    Roundness = CornerRadius
                }
            };

            AddInternal(glowContainer);

            foreach (var child in existingChildren)
            {
                glowContainer.Add(child);
            }

            updateGlow();
        }

        private void updateGlow()
        {
            if (glowContainer == null) return;

            bool shouldGlow = alwaysGlow || (glowOnHover && IsHovered);
            var targetColour = shouldGlow ? glowColour.Opacity(glowIntensity) : Color4.Transparent;

            glowContainer.TweenEdgeEffectTo(new EdgeEffectParameters
            {
                Type = EdgeEffectType.Glow,
                Colour = targetColour,
                Radius = glowRadius,
                Roundness = CornerRadius
            }, 200, Easing.OutQuint);
        }

        protected override bool OnHover(HoverEvent e)
        {
            updateGlow();
            this.ScaleTo(hoverScale, 300, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            updateGlow();
            this.ScaleTo(1f, 300, Easing.OutQuint);
            base.OnHoverLost(e);
        }
    }

    /// <summary>
    /// A pulsing glow effect that can be triggered programmatically.
    /// Useful for highlighting important UI elements.
    /// </summary>
    public partial class PulsingGlowContainer : GlowingContainer
    {
        private bool isPulsing;
        private double pulseInterval = 1500;
        private float pulseIntensityMin = 0.2f;
        private float pulseIntensityMax = 0.8f;

        /// <summary>
        /// Interval between pulse peaks in milliseconds.
        /// </summary>
        public double PulseInterval
        {
            get => pulseInterval;
            set => pulseInterval = Math.Max(100, value);
        }

        /// <summary>
        /// Minimum glow intensity during pulse cycle.
        /// </summary>
        public float PulseIntensityMin
        {
            get => pulseIntensityMin;
            set => pulseIntensityMin = Math.Clamp(value, 0f, 1f);
        }

        /// <summary>
        /// Maximum glow intensity during pulse peak.
        /// </summary>
        public float PulseIntensityMax
        {
            get => pulseIntensityMax;
            set => pulseIntensityMax = Math.Clamp(value, 0f, 1f);
        }

        /// <summary>
        /// Start the pulsing animation.
        /// </summary>
        public void StartPulsing()
        {
            if (isPulsing) return;
            isPulsing = true;
            AlwaysGlow = true;
            doPulse();
        }

        /// <summary>
        /// Stop the pulsing animation.
        /// </summary>
        public void StopPulsing()
        {
            isPulsing = false;
            AlwaysGlow = false;
            GlowIntensity = 0;
        }

        private void doPulse()
        {
            if (!isPulsing) return;

            GlowIntensity = pulseIntensityMin;

            this.TransformTo(nameof(GlowIntensity), pulseIntensityMax, pulseInterval / 2, Easing.InOutSine)
                .Then()
                .TransformTo(nameof(GlowIntensity), pulseIntensityMin, pulseInterval / 2, Easing.InOutSine)
                .OnComplete(_ => doPulse());
        }

        /// <summary>
        /// Trigger a single pulse animation.
        /// </summary>
        public void Pulse()
        {
            AlwaysGlow = true;
            GlowIntensity = pulseIntensityMin;

            this.TransformTo(nameof(GlowIntensity), pulseIntensityMax, 150, Easing.OutQuint)
                .Then()
                .TransformTo(nameof(GlowIntensity), 0f, 600, Easing.OutQuint)
                .OnComplete(_ =>
                {
                    if (!isPulsing)
                        AlwaysGlow = false;
                });
        }
    }

    /// <summary>
    /// A container with animated border gradient effect.
    /// Creates a "scanning" or "energy flow" visual effect around the border.
    /// </summary>
    public partial class AnimatedBorderContainer : Container
    {
        private float borderThickness = 2f;
        private Color4 borderColour1 = DesignSystem.ColorAccentPrimary;
        private Color4 borderColour2 = DesignSystem.ColorAccentSecondary;
        private double animationDuration = 3000;
        private bool isAnimating;

        private Container borderContainer = null!;

        public new float BorderThickness
        {
            get => borderThickness;
            set
            {
                borderThickness = value;
                if (borderContainer != null)
                    borderContainer.BorderThickness = value;
            }
        }

        public Color4 BorderColour1
        {
            get => borderColour1;
            set => borderColour1 = value;
        }

        public Color4 BorderColour2
        {
            get => borderColour2;
            set => borderColour2 = value;
        }

        public double AnimationDuration
        {
            get => animationDuration;
            set => animationDuration = Math.Max(100, value);
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            var existingChildren = InternalChildren;
            ClearInternal(false);

            borderContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = CornerRadius,
                BorderThickness = borderThickness,
                BorderColour = borderColour1
            };

            AddInternal(borderContainer);

            foreach (var child in existingChildren)
            {
                borderContainer.Add(child);
            }
        }

        /// <summary>
        /// Start the border color animation.
        /// </summary>
        public void StartAnimation()
        {
            if (isAnimating) return;
            isAnimating = true;
            animateBorder();
        }

        /// <summary>
        /// Stop the border animation.
        /// </summary>
        public void StopAnimation()
        {
            isAnimating = false;
            borderContainer.ClearTransforms();
            borderContainer.BorderColour = borderColour1;
        }

        private void animateBorder()
        {
            if (!isAnimating || borderContainer == null) return;

            borderContainer.TransformTo(nameof(borderContainer.BorderColour), borderColour2, animationDuration / 2, Easing.InOutSine)
                .Then()
                .TransformTo(nameof(borderContainer.BorderColour), borderColour1, animationDuration / 2, Easing.InOutSine)
                .OnComplete(_ => animateBorder());
        }
    }
}
