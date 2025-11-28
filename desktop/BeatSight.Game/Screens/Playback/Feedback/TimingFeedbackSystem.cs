// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using System.Linq;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Pooling;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;
using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield;
using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.Screens.Playback.Feedback
{
    /// <summary>
    /// Timing analysis feedback system for drum practice.
    /// Provides visual feedback on timing accuracy without gamification elements.
    /// Focuses on helping the user understand their timing patterns for learning.
    /// </summary>
    public partial class TimingFeedbackSystem : CompositeDrawable
    {
        #region Configuration Bindables

        private Bindable<bool> showTimingIndicators = null!;
        private Bindable<bool> showTimingGraph = null!;

        #endregion

        #region Visual Components

        private Container feedbackContainer = null!;
        private TimingDeviationGraph timingGraph = null!;

        private DrawablePool<EarlyLateIndicator> earlyLatePool = null!;

        #endregion

        #region State

        private readonly List<TimingRecord> recentTimings = new();

        #endregion

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager config)
        {
            showTimingIndicators = new Bindable<bool>(true);
            showTimingGraph = new Bindable<bool>(true);

            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                earlyLatePool = new DrawablePool<EarlyLateIndicator>(10),

                feedbackContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                },

                // Timing deviation graph (bottom of screen) - useful for learning
                timingGraph = new TimingDeviationGraph
                {
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Width = 400,
                    Height = 60,
                    Margin = new MarginPadding { Bottom = 100 },
                },
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            showTimingGraph.BindValueChanged(v => timingGraph.FadeTo(v.NewValue ? 1 : 0, 200), true);
        }

        #region Public API

        /// <summary>
        /// Reports timing feedback for a note. Call when auto-hit triggers.
        /// </summary>
        /// <param name="timingError">Timing error in milliseconds (negative = early, positive = late)</param>
        /// <param name="position">Screen position for visual feedback placement</param>
        public void ReportTiming(double timingError, Vector2 position)
        {
            var record = new TimingRecord
            {
                TimingError = timingError,
                Position = position,
                Timestamp = Clock.CurrentTime,
            };

            recentTimings.Add(record);

            // Maintain rolling window of recent timings for analysis
            while (recentTimings.Count > 100)
                recentTimings.RemoveAt(0);

            // Show early/late indicator if timing is off
            if (showTimingIndicators.Value && Math.Abs(timingError) > 10) // Only show if more than 10ms off
                ShowEarlyLateIndicator(record);

            if (showTimingGraph.Value)
                timingGraph.AddDataPoint(timingError);
        }

        /// <summary>
        /// Resets timing analysis state.
        /// </summary>
        public void Reset()
        {
            recentTimings.Clear();
            timingGraph.Clear();
        }

        /// <summary>
        /// Gets the average timing error in milliseconds.
        /// Useful for understanding if user tends to hit early or late.
        /// </summary>
        public double GetAverageTimingError()
        {
            return recentTimings.Count > 0 ? recentTimings.Average(t => t.TimingError) : 0;
        }

        /// <summary>
        /// Gets the timing consistency (standard deviation of timing errors).
        /// Lower values indicate more consistent timing.
        /// </summary>
        public double GetTimingConsistency()
        {
            if (recentTimings.Count < 2)
                return 0;

            double avg = GetAverageTimingError();
            double sumSquaredDiffs = recentTimings.Sum(t => Math.Pow(t.TimingError - avg, 2));
            return Math.Sqrt(sumSquaredDiffs / recentTimings.Count);
        }

        #endregion

        #region Visual Feedback

        private void ShowEarlyLateIndicator(TimingRecord record)
        {
            var indicator = earlyLatePool.Get(i =>
            {
                i.Position = record.Position + new Vector2(0, -30);
                i.Configure(record.TimingError);
            });

            feedbackContainer.Add(indicator);
        }

        #endregion
    }

    #region Supporting Types

    public struct TimingRecord
    {
        public double TimingError;
        public Vector2 Position;
        public double Timestamp;
    }

    #endregion

    #region Visual Components

    /// <summary>
    /// Subtle early/late indicator for timing feedback.
    /// </summary>
    public partial class EarlyLateIndicator : PoolableDrawable
    {
        private SpriteText text = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;
            Origin = Anchor.Centre;

            InternalChild = text = new SpriteText
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Font = FontUsage.Default.With(size: 12),
            };
        }

        public void Configure(double timingError)
        {
            bool isEarly = timingError < 0;
            text.Text = isEarly ? "EARLY" : "LATE";
            text.Colour = isEarly ? DesignSystem.ColorEarly : DesignSystem.ColorLate;
        }

        protected override void PrepareForUse()
        {
            base.PrepareForUse();

            this.FadeIn(30)
                .MoveToOffset(new Vector2(0, -15), 300, Easing.OutQuint)
                .FadeOut(200, Easing.OutQuint)
                .Expire();
        }
    }

    /// <summary>
    /// Rolling graph showing timing deviation over recent hits.
    /// Helps users identify systematic timing issues for practice improvement.
    /// </summary>
    public partial class TimingDeviationGraph : CompositeDrawable
    {
        private readonly List<double> dataPoints = new();
        private Container dotsContainer = null!;

        private const int max_data_points = 50;
        private const float timing_range_ms = 100; // +/- 100ms displayed

        [BackgroundDependencyLoader]
        private void load()
        {
            Masking = true;
            CornerRadius = DesignSystem.RadiusSmall;

            InternalChildren = new Drawable[]
            {
                // Background
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorSurface, 0.8f),
                },

                // Early zone (top half, tinted)
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.Both,
                    Height = 0.5f,
                    Y = 0,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorEarly, 0.1f),
                },

                // Late zone (bottom half, tinted)
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.Both,
                    Height = 0.5f,
                    Y = 0.5f,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorLate, 0.1f),
                },

                // Center line (perfect timing)
                new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorTextSecondary, 0.5f),
                },

                // Dots container
                dotsContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                },

                // Labels
                new SpriteText
                {
                    Text = "EARLY",
                    Font = FontUsage.Default.With(size: 10),
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorEarly, 0.6f),
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Margin = new MarginPadding { Left = 4, Top = 2 },
                },
                new SpriteText
                {
                    Text = "LATE",
                    Font = FontUsage.Default.With(size: 10),
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorLate, 0.6f),
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Margin = new MarginPadding { Left = 4, Bottom = 2 },
                },
            };
        }

        public void AddDataPoint(double timingError)
        {
            dataPoints.Add(timingError);

            while (dataPoints.Count > max_data_points)
                dataPoints.RemoveAt(0);

            RefreshGraph();
        }

        public void Clear()
        {
            dataPoints.Clear();
            dotsContainer.Clear();
        }

        private void RefreshGraph()
        {
            dotsContainer.Clear();

            for (int i = 0; i < dataPoints.Count; i++)
            {
                double timingError = dataPoints[i];
                float x = (float)i / max_data_points;
                float y = (float)(timingError / timing_range_ms) * 0.5f + 0.5f;
                y = Math.Clamp(y, 0.05f, 0.95f);

                // Color based on timing accuracy
                Color4 dotColor = Math.Abs(timingError) switch
                {
                    < 15 => DesignSystem.ColorSuccess,  // Excellent timing
                    < 30 => DesignSystem.ColorWarning,  // Acceptable
                    _ => DesignSystem.ColorError        // Needs work
                };

                dotsContainer.Add(new Circle
                {
                    Size = new Vector2(6),
                    RelativePositionAxes = Axes.Both,
                    X = x,
                    Y = y,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.Centre,
                    Colour = dotColor,
                    Alpha = 0.5f + (float)i / dataPoints.Count * 0.5f,
                });
            }
        }
    }

    #endregion
}
