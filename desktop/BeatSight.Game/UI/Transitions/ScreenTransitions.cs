using System;
using System.Linq;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Transitions
{
    /// <summary>
    /// A collection of enhanced screen transitions for polished navigation.
    /// </summary>
    public static class ScreenTransitions
    {
        // Standard timing constants
        public const double SHORT_DURATION = 200;
        public const double MEDIUM_DURATION = 400;
        public const double LONG_DURATION = 600;

        // Brand colors for gradient effects
        public static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255);
        public static readonly Color4 FuchsiaAccent = new Color4(217, 70, 239, 255);

        /// <summary>
        /// Applies a fade + slide up entrance animation (default BeatSight style).
        /// </summary>
        public static void FadeSlideIn(Drawable drawable, double duration = MEDIUM_DURATION)
        {
            drawable.FadeInFromZero(duration, Easing.OutQuint);
            drawable.MoveToY(20).MoveToY(0, duration, Easing.OutQuint);
        }

        /// <summary>
        /// Applies a fade + scale down exit animation.
        /// </summary>
        public static void FadeScaleOut(Drawable drawable, double duration = SHORT_DURATION)
        {
            drawable.FadeOut(duration, Easing.OutQuad);
            drawable.ScaleTo(0.95f, duration, Easing.OutQuad);
        }

        /// <summary>
        /// Applies a horizontal slide out (for suspending screens).
        /// </summary>
        public static void SlideOutLeft(Drawable drawable, double duration = SHORT_DURATION)
        {
            drawable.FadeOut(duration, Easing.OutQuad);
            drawable.MoveToX(-50, duration, Easing.OutQuad);
        }

        /// <summary>
        /// Applies a horizontal slide in from left (for resuming screens).
        /// </summary>
        public static void SlideInFromLeft(Drawable drawable, double duration = SHORT_DURATION)
        {
            drawable.FadeIn(duration, Easing.OutQuad);
            drawable.MoveToX(0, duration, Easing.OutQuad);
        }

        /// <summary>
        /// Applies a dramatic zoom-in entrance for important screens.
        /// </summary>
        public static void ZoomIn(Drawable drawable, double duration = MEDIUM_DURATION)
        {
            drawable.FadeInFromZero(duration, Easing.OutExpo);
            drawable.ScaleTo(0.8f).ScaleTo(1f, duration, Easing.OutExpo);
        }

        /// <summary>
        /// Applies a zoom-out exit animation.
        /// </summary>
        public static void ZoomOut(Drawable drawable, double duration = MEDIUM_DURATION)
        {
            drawable.FadeOut(duration * 0.8, Easing.InQuad);
            drawable.ScaleTo(1.1f, duration, Easing.InQuad);
        }

        /// <summary>
        /// Applies a slide from right entrance (for forward navigation).
        /// </summary>
        public static void SlideFromRight(Drawable drawable, double duration = MEDIUM_DURATION)
        {
            drawable.FadeInFromZero(duration, Easing.OutQuint);
            drawable.MoveToX(100).MoveToX(0, duration, Easing.OutQuint);
        }

        /// <summary>
        /// Applies a slide to right exit (for backward navigation).
        /// </summary>
        public static void SlideToRight(Drawable drawable, double duration = MEDIUM_DURATION)
        {
            drawable.FadeOut(duration, Easing.InQuint);
            drawable.MoveToX(100, duration, Easing.InQuint);
        }

        /// <summary>
        /// Applies a bounce entrance for playful UI elements.
        /// </summary>
        public static void BounceIn(Drawable drawable, double duration = MEDIUM_DURATION)
        {
            drawable.FadeInFromZero(duration * 0.5);
            drawable.ScaleTo(0f).ScaleTo(1.1f, duration * 0.6, Easing.OutQuint)
                   .Then().ScaleTo(1f, duration * 0.4, Easing.OutBounce);
        }

        /// <summary>
        /// Applies a rotation + fade entrance for decorative elements.
        /// </summary>
        public static void SpinIn(Drawable drawable, double duration = LONG_DURATION)
        {
            drawable.FadeInFromZero(duration, Easing.OutQuint);
            drawable.ScaleTo(0.5f).ScaleTo(1f, duration, Easing.OutQuint);
            drawable.RotateTo(-180).RotateTo(0, duration, Easing.OutQuint);
        }

        /// <summary>
        /// Applies a staggered fade in for child elements in a container.
        /// </summary>
        public static void StaggeredFadeIn(Container container, double staggerDelay = 50, double itemDuration = 300)
        {
            double currentDelay = 0;

            foreach (var child in container.Children)
            {
                child.Alpha = 0;
                child.MoveToY(20);

                using (child.BeginDelayedSequence(currentDelay))
                {
                    child.FadeIn(itemDuration, Easing.OutQuint);
                    child.MoveToY(0, itemDuration, Easing.OutQuint);
                }

                currentDelay += staggerDelay;
            }
        }

        /// <summary>
        /// Applies a wave-like fade in from left to right.
        /// </summary>
        public static void WaveFadeIn(Container container, double duration = 600)
        {
            var children = container.Children.ToList();
            if (children.Count == 0) return;

            double delayPerChild = duration / (children.Count + 1);
            double currentDelay = 0;

            foreach (var child in children)
            {
                child.Alpha = 0;
                child.MoveToX(-30);

                using (child.BeginDelayedSequence(currentDelay))
                {
                    child.FadeIn(duration * 0.5, Easing.OutQuint);
                    child.MoveToX(0, duration * 0.5, Easing.OutQuint);
                }

                currentDelay += delayPerChild;
            }
        }
    }

    /// <summary>
    /// An enhanced base screen with configurable transitions.
    /// </summary>
    public partial class AnimatedScreen : Screen
    {
        /// <summary>
        /// The type of entrance animation to use.
        /// </summary>
        protected virtual TransitionType EnterTransition => TransitionType.FadeSlide;

        /// <summary>
        /// The type of exit animation to use.
        /// </summary>
        protected virtual TransitionType ExitTransition => TransitionType.FadeScale;

        /// <summary>
        /// Duration of the entrance animation in milliseconds.
        /// </summary>
        protected virtual double EnterDuration => ScreenTransitions.MEDIUM_DURATION;

        /// <summary>
        /// Duration of the exit animation in milliseconds.
        /// </summary>
        protected virtual double ExitDuration => ScreenTransitions.SHORT_DURATION;

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            ApplyEnterTransition();
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            ApplyExitTransition();
            return base.OnExiting(e);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            ScreenTransitions.SlideOutLeft(this, ExitDuration);
        }

        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            ScreenTransitions.SlideInFromLeft(this, EnterDuration);
        }

        protected virtual void ApplyEnterTransition()
        {
            switch (EnterTransition)
            {
                case TransitionType.FadeSlide:
                    ScreenTransitions.FadeSlideIn(this, EnterDuration);
                    break;
                case TransitionType.Zoom:
                    ScreenTransitions.ZoomIn(this, EnterDuration);
                    break;
                case TransitionType.SlideFromRight:
                    ScreenTransitions.SlideFromRight(this, EnterDuration);
                    break;
                case TransitionType.Bounce:
                    ScreenTransitions.BounceIn(this, EnterDuration);
                    break;
                case TransitionType.Spin:
                    ScreenTransitions.SpinIn(this, EnterDuration);
                    break;
                case TransitionType.None:
                    this.Show();
                    break;
            }
        }

        protected virtual void ApplyExitTransition()
        {
            switch (ExitTransition)
            {
                case TransitionType.FadeScale:
                    ScreenTransitions.FadeScaleOut(this, ExitDuration);
                    break;
                case TransitionType.Zoom:
                    ScreenTransitions.ZoomOut(this, ExitDuration);
                    break;
                case TransitionType.SlideToRight:
                    ScreenTransitions.SlideToRight(this, ExitDuration);
                    break;
                case TransitionType.FadeSlide:
                    this.FadeOut(ExitDuration);
                    this.MoveToY(20, ExitDuration, Easing.InQuad);
                    break;
                case TransitionType.None:
                    this.Hide();
                    break;
            }
        }
    }

    /// <summary>
    /// Types of screen transitions available.
    /// </summary>
    public enum TransitionType
    {
        None,
        FadeSlide,
        FadeScale,
        Zoom,
        SlideFromRight,
        SlideToRight,
        Bounce,
        Spin
    }

    /// <summary>
    /// A container that applies staggered animations to its children.
    /// </summary>
    public partial class StaggeredContainer : Container
    {
        public double StaggerDelay { get; set; } = 50;
        public double ItemDuration { get; set; } = 300;

        public void AnimateIn()
        {
            ScreenTransitions.StaggeredFadeIn(this, StaggerDelay, ItemDuration);
        }

        public void AnimateOut()
        {
            double currentDelay = 0;

            foreach (var child in Children.Reverse())
            {
                using (child.BeginDelayedSequence(currentDelay))
                {
                    child.FadeOut(ItemDuration * 0.5, Easing.InQuint);
                    child.MoveToY(-20, ItemDuration * 0.5, Easing.InQuint);
                }

                currentDelay += StaggerDelay * 0.5;
            }
        }
    }

    /// <summary>
    /// A transition overlay that creates a curtain/wipe effect between screens.
    /// </summary>
    public partial class TransitionCurtain : CompositeDrawable
    {
        private readonly Box leftCurtain;
        private readonly Box rightCurtain;

        public TransitionCurtain()
        {
            RelativeSizeAxes = Axes.Both;
            Alpha = 0;

            InternalChildren = new Drawable[]
            {
                leftCurtain = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientHorizontal(
                        ScreenTransitions.CyanAccent.Opacity(0.95f),
                        ScreenTransitions.CyanAccent.Opacity(0.7f)),
                    RelativePositionAxes = Axes.X,
                    Width = 0.5f,
                    X = -0.5f,
                },
                rightCurtain = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientHorizontal(
                        ScreenTransitions.FuchsiaAccent.Opacity(0.7f),
                        ScreenTransitions.FuchsiaAccent.Opacity(0.95f)),
                    RelativePositionAxes = Axes.X,
                    Width = 0.5f,
                    Anchor = Anchor.TopRight,
                    Origin = Anchor.TopRight,
                    X = 0.5f,
                },
            };
        }

        /// <summary>
        /// Plays the curtain close animation.
        /// </summary>
        public void Close(double duration = 400)
        {
            this.FadeIn();
            leftCurtain.MoveToX(0, duration, Easing.OutQuint);
            rightCurtain.MoveToX(0, duration, Easing.OutQuint);
        }

        /// <summary>
        /// Plays the curtain open animation.
        /// </summary>
        public void Open(double duration = 400)
        {
            leftCurtain.MoveToX(-0.5f, duration, Easing.InQuint);
            rightCurtain.MoveToX(0.5f, duration, Easing.InQuint)
                       .OnComplete(_ => this.FadeOut());
        }

        /// <summary>
        /// Plays a full close-then-open transition.
        /// </summary>
        public void PlayTransition(double closeDuration = 400, double holdDuration = 100, double openDuration = 400)
        {
            Close(closeDuration);

            using (BeginDelayedSequence(closeDuration + holdDuration))
            {
                Open(openDuration);
            }
        }
    }

    /// <summary>
    /// A circular reveal transition overlay.
    /// </summary>
    public partial class CircularReveal : CompositeDrawable
    {
        private readonly Container revealContainer;

        public CircularReveal()
        {
            RelativeSizeAxes = Axes.Both;
            Alpha = 0;
            Masking = true;

            InternalChild = revealContainer = new Container
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Size = Vector2.Zero,
                Masking = true,
                CornerRadius = 0,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = ScreenTransitions.CyanAccent.Opacity(0.5f),
                    Radius = 20,
                },
                Child = new Circle
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ScreenTransitions.CyanAccent,
                },
            };
        }

        /// <summary>
        /// Plays an expanding circle reveal from center.
        /// </summary>
        public void Expand(double duration = 600)
        {
            this.FadeIn();
            float maxSize = MathF.Max(DrawWidth, DrawHeight) * 2;
            revealContainer.ResizeTo(0).ResizeTo(new Vector2(maxSize), duration, Easing.OutQuint)
                       .FadeIn().FadeOut(duration, Easing.InQuad);
        }

        /// <summary>
        /// Plays a contracting circle reveal to center.
        /// </summary>
        public void Contract(double duration = 600)
        {
            this.FadeIn();
            float maxSize = MathF.Max(DrawWidth, DrawHeight) * 2;
            revealContainer.ResizeTo(maxSize).ResizeTo(0, duration, Easing.InQuint);

            using (BeginDelayedSequence(duration))
            {
                this.FadeOut();
            }
        }
    }

    /// <summary>
    /// A loading spinner with BeatSight branding.
    /// </summary>
    public partial class BrandedSpinner : CompositeDrawable
    {
        private readonly Circle innerCircle;
        private readonly Circle outerRing;

        public BrandedSpinner()
        {
            Size = new Vector2(48);
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;

            InternalChildren = new Drawable[]
            {
                outerRing = new Circle
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Transparent,
                    BorderColour = ColourInfo.GradientHorizontal(
                        ScreenTransitions.CyanAccent,
                        ScreenTransitions.FuchsiaAccent),
                    BorderThickness = 3,
                    Masking = true,
                },
                innerCircle = new Circle
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Size = new Vector2(12),
                    Colour = ColourInfo.GradientVertical(
                        ScreenTransitions.CyanAccent,
                        ScreenTransitions.FuchsiaAccent),
                },
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Continuous rotation animation
            outerRing.Spin(1200, RotationDirection.Clockwise)
                    .Loop();

            // Pulsing inner circle
            innerCircle.ScaleTo(1f)
                      .ScaleTo(0.8f, 600, Easing.InOutQuad)
                      .Then()
                      .ScaleTo(1f, 600, Easing.InOutQuad)
                      .Loop();
        }
    }
}
