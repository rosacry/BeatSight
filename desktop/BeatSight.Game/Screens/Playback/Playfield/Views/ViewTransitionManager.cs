using System;
using System.Collections.Generic;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// Manages smooth animated transitions between different playfield view modes.
    /// 
    /// Provides professional-quality transitions including:
    /// - Crossfade between backgrounds
    /// - Scale/perspective animations for notes
    /// - Strike zone morphing
    /// - View-specific entry/exit animations
    /// 
    /// This is a drum analysis tool - transitions should be smooth but not disruptive
    /// to the learning experience.
    /// </summary>
    public partial class ViewTransitionManager : CompositeDrawable
    {
        #region Transition Constants

        /// <summary>Duration of crossfade transitions in milliseconds.</summary>
        private const double CrossfadeDuration = 400;

        /// <summary>Duration of scale transitions in milliseconds.</summary>
        private const double ScaleTransitionDuration = 350;

        /// <summary>Duration of position transitions in milliseconds.</summary>
        private const double PositionTransitionDuration = 300;

        /// <summary>Easing curve for smooth transitions.</summary>
        private static readonly Easing TransitionEasing = Easing.OutQuint;

        // Note: EntryEasing and ExitEasing reserved for future animation expansion

        #endregion

        #region State

        private LaneViewMode currentMode = LaneViewMode.TwoDimensional;
        private LaneViewMode targetMode = LaneViewMode.TwoDimensional;
        private bool isTransitioning;
        private double transitionStartTime;
        private double transitionDuration;

        private Container? oldBackgroundContainer;
        private Container? oldStrikeZoneContainer;

        // Transition effect containers
        private Container? transitionOverlay;
        private Box? flashOverlay;
        private Container? wipeContainer;

        /// <summary>Event fired when a transition completes.</summary>
        public event Action<LaneViewMode>? TransitionCompleted;

        /// <summary>Event fired when a transition starts.</summary>
        public event Action<LaneViewMode, LaneViewMode>? TransitionStarted;

        #endregion

        #region Properties

        /// <summary>Whether a transition is currently in progress.</summary>
        public bool IsTransitioning => isTransitioning;

        /// <summary>The current active view mode.</summary>
        public LaneViewMode CurrentMode => currentMode;

        /// <summary>Progress of the current transition (0-1).</summary>
        public float TransitionProgress { get; private set; }

        #endregion

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        private Bindable<bool> reducedMotion = null!;

        public ViewTransitionManager()
        {
            RelativeSizeAxes = Axes.Both;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            // Check for reduced motion preference (accessibility)
            // For now, we'll use a reasonable default
            reducedMotion = new Bindable<bool>(false);

            // Create transition overlay for effects
            AddInternal(transitionOverlay = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Alpha = 0,
                Children = new Drawable[]
                {
                    flashOverlay = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White,
                        Alpha = 0
                    },
                    wipeContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Masking = true,
                        Alpha = 0
                    }
                }
            });
        }

        #region Public API

        /// <summary>
        /// Start a transition to a new view mode.
        /// </summary>
        /// <param name="newMode">The target view mode.</param>
        /// <param name="immediate">If true, skip animation and switch immediately.</param>
        public void TransitionTo(LaneViewMode newMode, bool immediate = false)
        {
            if (newMode == currentMode && !isTransitioning)
                return;

            if (immediate || reducedMotion.Value)
            {
                CompleteTransitionImmediate(newMode);
                return;
            }

            StartTransition(newMode);
        }

        /// <summary>
        /// Cancel any ongoing transition and snap to the current target.
        /// </summary>
        public void CancelTransition()
        {
            if (!isTransitioning)
                return;

            CompleteTransitionImmediate(targetMode);
        }

        /// <summary>
        /// Get the interpolated parameters for note positioning during a transition.
        /// </summary>
        public TransitionParameters GetTransitionParameters()
        {
            if (!isTransitioning)
            {
                return new TransitionParameters
                {
                    Progress = 1f,
                    FromMode = currentMode,
                    ToMode = currentMode,
                    IsComplete = true
                };
            }

            return new TransitionParameters
            {
                Progress = TransitionProgress,
                FromMode = currentMode,
                ToMode = targetMode,
                IsComplete = false
            };
        }

        #endregion

        #region Transition Implementation

        private void StartTransition(LaneViewMode newMode)
        {
            if (isTransitioning)
            {
                // Queue or override? For now, complete current and start new
                CompleteTransitionImmediate(targetMode);
            }

            targetMode = newMode;
            isTransitioning = true;
            transitionStartTime = Time.Current;
            transitionDuration = GetTransitionDuration(currentMode, newMode);
            TransitionProgress = 0f;

            TransitionStarted?.Invoke(currentMode, newMode);

            // Apply entry animations based on target mode
            ApplyEntryAnimation(newMode);
        }

        private void CompleteTransitionImmediate(LaneViewMode newMode)
        {
            currentMode = newMode;
            targetMode = newMode;
            isTransitioning = false;
            TransitionProgress = 1f;

            // Clean up any transition containers
            CleanupTransitionContainers();

            TransitionCompleted?.Invoke(newMode);
        }

        protected override void Update()
        {
            base.Update();

            if (!isTransitioning)
                return;

            double elapsed = Time.Current - transitionStartTime;
            TransitionProgress = Math.Clamp((float)(elapsed / transitionDuration), 0f, 1f);

            if (TransitionProgress >= 1f)
            {
                CompleteTransitionImmediate(targetMode);
            }
        }

        private double GetTransitionDuration(LaneViewMode from, LaneViewMode to)
        {
            // Transitions involving 3D take slightly longer for smoother feel
            if (from == LaneViewMode.ThreeDimensional || to == LaneViewMode.ThreeDimensional)
                return CrossfadeDuration * 1.2;

            // Manuscript transitions are quicker since the layout is quite different
            if (from == LaneViewMode.Manuscript || to == LaneViewMode.Manuscript)
                return CrossfadeDuration * 0.9;

            return CrossfadeDuration;
        }

        private void ApplyEntryAnimation(LaneViewMode mode)
        {
            // Apply view-specific entry animations
            switch (mode)
            {
                case LaneViewMode.TwoDimensional:
                    ApplyTwoDimensionalEntry();
                    break;

                case LaneViewMode.ThreeDimensional:
                    ApplyThreeDimensionalEntry();
                    break;

                case LaneViewMode.Manuscript:
                    ApplyManuscriptEntry();
                    break;
            }
        }

        /// <summary>
        /// Entry animation for 2D highway view - slides up from bottom with slight fade.
        /// </summary>
        private void ApplyTwoDimensionalEntry()
        {
            if (transitionOverlay == null) return;

            // Subtle bottom-to-top wipe effect
            transitionOverlay.Alpha = 1;

            using (transitionOverlay.BeginDelayedSequence(0))
            {
                // Quick flash at transition start
                flashOverlay?.FadeTo(0.15f, 50)
                    .Then()
                    .FadeOut(CrossfadeDuration * 0.6, Easing.OutQuad);

                // Fade out overlay as new view settles
                transitionOverlay.Delay(CrossfadeDuration * 0.8)
                    .FadeOut(CrossfadeDuration * 0.3);
            }
        }

        /// <summary>
        /// Entry animation for 3D highway view - perspective zoom with depth effect.
        /// </summary>
        private void ApplyThreeDimensionalEntry()
        {
            if (transitionOverlay == null) return;

            transitionOverlay.Alpha = 1;

            using (transitionOverlay.BeginDelayedSequence(0))
            {
                // Dramatic flash for perspective shift
                flashOverlay?.FadeTo(0.25f, 80, Easing.OutQuint)
                    .Then()
                    .FadeOut(CrossfadeDuration * 0.8, Easing.OutExpo);

                // Apply a scale-in effect to simulate depth
                transitionOverlay.ScaleTo(1.1f)
                    .ScaleTo(1f, CrossfadeDuration, Easing.OutQuint);

                transitionOverlay.Delay(CrossfadeDuration * 0.9)
                    .FadeOut(CrossfadeDuration * 0.2);
            }
        }

        /// <summary>
        /// Entry animation for manuscript view - clean horizontal wipe like turning a page.
        /// </summary>
        private void ApplyManuscriptEntry()
        {
            if (transitionOverlay == null || wipeContainer == null) return;

            transitionOverlay.Alpha = 1;

            // Create page-turn wipe effect
            var wipeBox = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = BeatSightColors.BackgroundDark,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };
            wipeContainer.Clear();
            wipeContainer.Add(wipeBox);
            wipeContainer.Alpha = 1;

            using (wipeContainer.BeginDelayedSequence(0))
            {
                // Wipe from left to right
                wipeBox.Width = 0;
                wipeBox.ResizeWidthTo(1f, CrossfadeDuration * 0.5, Easing.OutQuad)
                    .Then()
                    .ResizeWidthTo(0f, CrossfadeDuration * 0.5, Easing.InQuad);

                // Move origin to right side for exit
                wipeBox.Delay(CrossfadeDuration * 0.5)
                    .TransformTo(nameof(wipeBox.Origin), Anchor.CentreRight, 0)
                    .TransformTo(nameof(wipeBox.Anchor), Anchor.CentreRight, 0);
            }

            transitionOverlay.Delay(CrossfadeDuration)
                .FadeOut(100);
        }

        /// <summary>
        /// Apply exit animation for the current view mode.
        /// </summary>
        public void ApplyExitAnimation(LaneViewMode mode, Action? onComplete = null)
        {
            double exitDuration = CrossfadeDuration * 0.6;

            switch (mode)
            {
                case LaneViewMode.TwoDimensional:
                    // Fade down and slightly scale
                    this.FadeTo(0.5f, exitDuration, Easing.OutQuad);
                    break;

                case LaneViewMode.ThreeDimensional:
                    // Zoom out effect
                    this.ScaleTo(0.95f, exitDuration, Easing.InQuad);
                    this.FadeTo(0.3f, exitDuration, Easing.OutQuad);
                    break;

                case LaneViewMode.Manuscript:
                    // Slide left
                    this.MoveToX(-20, exitDuration, Easing.InQuad);
                    this.FadeTo(0.5f, exitDuration, Easing.OutQuad);
                    break;
            }

            Scheduler.AddDelayed(() =>
            {
                // Reset transforms
                this.FadeTo(1f, 0);
                this.ScaleTo(1f, 0);
                this.MoveToX(0, 0);
                onComplete?.Invoke();
            }, exitDuration);
        }

        /// <summary>
        /// Get the icon/indicator color for a view mode during transition.
        /// </summary>
        public Color4 GetModeTransitionColor(LaneViewMode mode)
        {
            return mode switch
            {
                LaneViewMode.TwoDimensional => new Color4(100, 180, 255, 255),    // Blue
                LaneViewMode.ThreeDimensional => new Color4(255, 150, 100, 255),  // Orange
                LaneViewMode.Manuscript => new Color4(180, 255, 150, 255),        // Green
                _ => Color4.White
            };
        }

        private void CleanupTransitionContainers()
        {
            oldBackgroundContainer?.Expire();
            oldBackgroundContainer = null;
            oldStrikeZoneContainer?.Expire();
            oldStrikeZoneContainer = null;
        }

        #endregion

        #region Interpolation Helpers

        /// <summary>
        /// Interpolate a note's position during a transition.
        /// </summary>
        public Vector2 InterpolateNotePosition(
            Vector2 fromPosition,
            Vector2 toPosition,
            float noteProgress)
        {
            float t = ApplyEasing(TransitionProgress, TransitionEasing);
            return Vector2.Lerp(fromPosition, toPosition, t);
        }

        /// <summary>
        /// Interpolate a note's scale during a transition.
        /// </summary>
        public Vector2 InterpolateNoteScale(
            Vector2 fromScale,
            Vector2 toScale)
        {
            float t = ApplyEasing(TransitionProgress, TransitionEasing);
            return Vector2.Lerp(fromScale, toScale, t);
        }

        /// <summary>
        /// Interpolate alpha for crossfade effect.
        /// </summary>
        public float InterpolateAlpha(bool isNewElement)
        {
            float t = ApplyEasing(TransitionProgress, TransitionEasing);
            return isNewElement ? t : 1f - t;
        }

        private static float ApplyEasing(float t, Easing easing)
        {
            return easing switch
            {
                Easing.OutQuint => 1f - MathF.Pow(1f - t, 5f),
                Easing.OutBack => 1f + 2.70158f * MathF.Pow(t - 1f, 3f) + 1.70158f * MathF.Pow(t - 1f, 2f),
                Easing.InQuad => t * t,
                Easing.InOutQuad => t < 0.5f ? 2f * t * t : 1f - MathF.Pow(-2f * t + 2f, 2f) / 2f,
                _ => t
            };
        }

        #endregion
    }

    /// <summary>
    /// Parameters describing the current state of a view transition.
    /// </summary>
    public struct TransitionParameters
    {
        /// <summary>Progress of the transition (0-1).</summary>
        public float Progress { get; init; }

        /// <summary>The source view mode.</summary>
        public LaneViewMode FromMode { get; init; }

        /// <summary>The target view mode.</summary>
        public LaneViewMode ToMode { get; init; }

        /// <summary>Whether the transition is complete.</summary>
        public bool IsComplete { get; init; }

        /// <summary>Get the eased progress value.</summary>
        public float EasedProgress => 1f - MathF.Pow(1f - Progress, 3f);
    }
}
