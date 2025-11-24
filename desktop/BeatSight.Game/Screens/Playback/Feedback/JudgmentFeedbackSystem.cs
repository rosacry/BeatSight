// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using System.Linq;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
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
    /// Centralized judgment feedback system that provides visual feedback for hits
    /// without cluttering the screen. Supports multiple feedback styles optimized
    /// for different practice scenarios.
    /// </summary>
    public partial class JudgmentFeedbackSystem : CompositeDrawable
    {
        #region Configuration Bindables

        private Bindable<bool> showJudgments = null!;
        private Bindable<bool> showEarlyLate = null!;
        private Bindable<bool> showTimingGraph = null!;
        private Bindable<JudgmentDisplayStyle> displayStyle = null!;

        #endregion

        #region Visual Components

        private Container judgmentContainer = null!;
        private TimingDeviationGraph timingGraph = null!;
        private JudgmentCounter judgmentCounter = null!;
        private ComboDisplay comboDisplay = null!;

        private DrawablePool<JudgmentPopup> judgmentPool = null!;
        private DrawablePool<EarlyLateIndicator> earlyLatePool = null!;

        #endregion

        #region State

        private readonly List<JudgmentRecord> recentJudgments = new();
        private int currentCombo;
        private int maxCombo;

        #endregion

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager config)
        {
            // Use defaults for now - these settings can be added to BeatSightSetting later
            showJudgments = new Bindable<bool>(true);
            showEarlyLate = new Bindable<bool>(true);
            showTimingGraph = new Bindable<bool>(false);

            // Default to popup style if not configured
            displayStyle = new Bindable<JudgmentDisplayStyle>(JudgmentDisplayStyle.Popup);

            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                // Pool for judgment popups
                judgmentPool = new DrawablePool<JudgmentPopup>(10),
                earlyLatePool = new DrawablePool<EarlyLateIndicator>(10),

                // Main judgment display container
                judgmentContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                },

                // Timing deviation graph (bottom of screen)
                timingGraph = new TimingDeviationGraph
                {
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Width = 400,
                    Height = 60,
                    Margin = new MarginPadding { Bottom = 100 },
                },

                // Judgment counter (top right)
                judgmentCounter = new JudgmentCounter(),

                // Combo display (center)
                comboDisplay = new ComboDisplay
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Y = -100,
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
        /// Reports a judgment for display. Call this when a note is hit.
        /// </summary>
        /// <param name="result">The hit result</param>
        /// <param name="timingError">Timing error in milliseconds (negative = early, positive = late)</param>
        /// <param name="position">Screen position where the hit occurred (for popup placement)</param>
        /// <param name="laneIndex">Optional lane index for lane-specific feedback</param>
        public void ReportJudgment(HitResult result, double timingError, Vector2 position, int? laneIndex = null)
        {
            var record = new JudgmentRecord
            {
                Result = result,
                TimingError = timingError,
                Position = position,
                LaneIndex = laneIndex,
                Timestamp = Clock.CurrentTime,
            };

            recentJudgments.Add(record);

            // Maintain rolling window of recent judgments
            while (recentJudgments.Count > 100)
                recentJudgments.RemoveAt(0);

            // Update combo
            if (result != HitResult.Miss)
            {
                currentCombo++;
                maxCombo = Math.Max(maxCombo, currentCombo);
            }
            else
            {
                currentCombo = 0;
            }

            // Display feedback based on settings
            if (showJudgments.Value)
                ShowJudgmentPopup(record);

            if (showEarlyLate.Value && result != HitResult.Perfect && result != HitResult.Miss)
                ShowEarlyLateIndicator(record);

            if (showTimingGraph.Value)
                timingGraph.AddDataPoint(timingError, result);

            judgmentCounter.UpdateCount(result);
            comboDisplay.UpdateCombo(currentCombo, result);
        }

        /// <summary>
        /// Resets all judgment state. Call when starting a new section or restarting.
        /// </summary>
        public void Reset()
        {
            recentJudgments.Clear();
            currentCombo = 0;
            maxCombo = 0;

            timingGraph.Clear();
            judgmentCounter.Reset();
            comboDisplay.Reset();
        }

        /// <summary>
        /// Gets the current accuracy as a percentage (0-100).
        /// </summary>
        public double GetAccuracy()
        {
            if (recentJudgments.Count == 0)
                return 100;

            double totalWeight = 0;
            double earnedWeight = 0;

            foreach (var judgment in recentJudgments)
            {
                totalWeight += 1;
                earnedWeight += GetResultWeight(judgment.Result);
            }

            return totalWeight > 0 ? (earnedWeight / totalWeight) * 100 : 100;
        }

        /// <summary>
        /// Gets the average timing error in milliseconds.
        /// </summary>
        public double GetAverageTimingError()
        {
            var hits = recentJudgments.Where(j => j.Result != HitResult.Miss).ToList();
            return hits.Count > 0 ? hits.Average(j => j.TimingError) : 0;
        }

        #endregion

        #region Visual Feedback Methods

        private void ShowJudgmentPopup(JudgmentRecord record)
        {
            var popup = judgmentPool.Get(p =>
            {
                p.Position = record.Position;
                p.Configure(record.Result);
            });

            judgmentContainer.Add(popup);
        }

        private void ShowEarlyLateIndicator(JudgmentRecord record)
        {
            var indicator = earlyLatePool.Get(i =>
            {
                i.Position = record.Position + new Vector2(0, -30);
                i.Configure(record.TimingError);
            });

            judgmentContainer.Add(indicator);
        }

        private static double GetResultWeight(HitResult result) => result switch
        {
            HitResult.Perfect => 1.0,
            HitResult.Great => 0.9,
            HitResult.Good => 0.7,
            HitResult.Meh => 0.4,
            HitResult.Miss => 0.0,
            _ => 0.0,
        };

        #endregion
    }

    #region Supporting Types

    public enum JudgmentDisplayStyle
    {
        Popup,
        Minimal,
        LaneGlow,
        Hidden,
    }

    public struct JudgmentRecord
    {
        public HitResult Result;
        public double TimingError;
        public Vector2 Position;
        public int? LaneIndex;
        public double Timestamp;
    }

    #endregion

    #region Visual Components

    /// <summary>
    /// Animated judgment text that pops up and fades out.
    /// </summary>
    public partial class JudgmentPopup : PoolableDrawable
    {
        private SpriteText text = null!;
        private Container glowContainer = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;
            Origin = Anchor.Centre;

            InternalChildren = new Drawable[]
            {
                glowContainer = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                },
                text = new SpriteText
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Font = FontUsage.Default.With(size: 24, weight: "Bold"),
                },
            };
        }

        public void Configure(HitResult result)
        {
            text.Text = GetResultText(result);
            text.Colour = DesignSystem.GetJudgmentColor(result);

            glowContainer.EdgeEffect = new EdgeEffectParameters
            {
                Type = EdgeEffectType.Glow,
                Colour = DesignSystem.WithOpacity(DesignSystem.GetJudgmentColor(result), 0.5f),
                Radius = 10,
            };
        }

        protected override void PrepareForUse()
        {
            base.PrepareForUse();

            this.FadeIn(50)
                .ScaleTo(1.2f)
                .ScaleTo(1f, 100, Easing.OutQuint)
                .Then()
                .MoveToOffset(new Vector2(0, -30), 400, Easing.OutQuint)
                .FadeOut(300, Easing.OutQuint)
                .Expire();
        }

        private static string GetResultText(HitResult result) => result switch
        {
            HitResult.Perfect => "PERFECT",
            HitResult.Great => "GREAT",
            HitResult.Good => "GOOD",
            HitResult.Meh => "MEH",
            HitResult.Miss => "MISS",
            _ => "",
        };
    }

    /// <summary>
    /// Subtle early/late indicator that appears near judgments.
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
    /// Helps players identify systematic timing issues.
    /// </summary>
    public partial class TimingDeviationGraph : CompositeDrawable
    {
        private readonly List<TimingDataPoint> dataPoints = new();
        private Container dotsContainer = null!;
        private Box centerLine = null!;
        private Box earlyZone = null!;
        private Box lateZone = null!;

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
                earlyZone = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.Both,
                    Height = 0.5f,
                    Y = 0,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorEarly, 0.1f),
                },

                // Late zone (bottom half, tinted)
                lateZone = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.Both,
                    Height = 0.5f,
                    Y = 0.5f,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorLate, 0.1f),
                },

                // Center line (perfect timing)
                centerLine = new Box
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

        public void AddDataPoint(double timingError, HitResult result)
        {
            dataPoints.Add(new TimingDataPoint
            {
                TimingError = timingError,
                Result = result,
            });

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
                var point = dataPoints[i];
                float x = (float)i / max_data_points;
                float y = (float)(point.TimingError / timing_range_ms) * 0.5f + 0.5f;
                y = Math.Clamp(y, 0.05f, 0.95f);

                dotsContainer.Add(new Circle
                {
                    Size = new Vector2(6),
                    RelativePositionAxes = Axes.Both,
                    X = x,
                    Y = y,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.Centre,
                    Colour = DesignSystem.GetJudgmentColor(point.Result),
                    Alpha = 0.5f + (float)i / dataPoints.Count * 0.5f, // Fade in older points
                });
            }
        }

        private struct TimingDataPoint
        {
            public double TimingError;
            public HitResult Result;
        }
    }

    /// <summary>
    /// Displays count of each judgment type during the session.
    /// </summary>
    public partial class JudgmentCounter : CompositeDrawable
    {
        private readonly Dictionary<HitResult, int> counts = new();
        private FillFlowContainer flowContainer = null!;
        private readonly Dictionary<HitResult, SpriteText> countTexts = new();

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;
            Anchor = Anchor.TopRight;
            Origin = Anchor.TopRight;
            Margin = new MarginPadding { Top = 10, Right = 10 };
            Masking = true;
            CornerRadius = DesignSystem.RadiusSmall;

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorSurface, 0.8f),
                },
                flowContainer = new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Vertical,
                    Padding = new MarginPadding(DesignSystem.SpacingSmall),
                    Spacing = new Vector2(0, 2),
                },
            };

            // Initialize counters for each result type
            foreach (HitResult result in Enum.GetValues<HitResult>())
            {
                counts[result] = 0;

                var row = new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(DesignSystem.SpacingSmall, 0),
                    Children = new Drawable[]
                    {
                        new Circle
                        {
                            Size = new Vector2(8),
                            Colour = DesignSystem.GetJudgmentColor(result),
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                        },
                        countTexts[result] = new SpriteText
                        {
                            Text = "0",
                            Font = FontUsage.Default.With(size: 14),
                            Colour = DesignSystem.ColorTextPrimary,
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                        },
                    },
                };

                flowContainer.Add(row);
            }
        }

        public void UpdateCount(HitResult result)
        {
            counts[result]++;
            countTexts[result].Text = counts[result].ToString();
            countTexts[result].FlashColour(Color4.White, 100);
        }

        public void Reset()
        {
            foreach (var result in counts.Keys.ToList())
            {
                counts[result] = 0;
                countTexts[result].Text = "0";
            }
        }
    }

    /// <summary>
    /// Displays the current combo with animation.
    /// </summary>
    public partial class ComboDisplay : CompositeDrawable
    {
        private SpriteText comboText = null!;
        private SpriteText comboLabel = null!;
        private Container glowContainer = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;
            Alpha = 0; // Hidden until first hit

            InternalChildren = new Drawable[]
            {
                glowContainer = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                },
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Vertical,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Spacing = new Vector2(0, -4),
                    Children = new Drawable[]
                    {
                        comboText = new SpriteText
                        {
                            Font = FontUsage.Default.With(size: 48, weight: "Bold"),
                            Colour = DesignSystem.ColorTextPrimary,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                        },
                        comboLabel = new SpriteText
                        {
                            Text = "COMBO",
                            Font = FontUsage.Default.With(size: 14),
                            Colour = DesignSystem.ColorTextSecondary,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                        },
                    },
                },
            };
        }

        public void UpdateCombo(int combo, HitResult result)
        {
            if (combo == 0)
            {
                // Combo break animation
                this.ScaleTo(1.5f, 100)
                    .FadeOut(200);
                return;
            }

            comboText.Text = combo.ToString();

            if (combo == 1)
            {
                this.FadeIn(100);
            }

            // Pulse animation on hit
            this.ScaleTo(1.1f, 50, Easing.OutQuint)
                .Then()
                .ScaleTo(1f, 100, Easing.OutQuint);

            // Color based on result quality
            var targetColor = DesignSystem.GetJudgmentColor(result);
            comboText.FadeColour(targetColor, 50)
                     .Then()
                     .FadeColour(DesignSystem.ColorTextPrimary, 200);

            // Milestone effects at certain combo thresholds
            if (combo % 50 == 0)
            {
                glowContainer.EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = DesignSystem.WithOpacity(DesignSystem.ColorAccent, 0.8f),
                    Radius = 30,
                };

                glowContainer.FadeEdgeEffectTo(0, 500);
            }
        }

        public void Reset()
        {
            this.FadeOut(100);
            comboText.Text = "0";
        }
    }

    #endregion
}
