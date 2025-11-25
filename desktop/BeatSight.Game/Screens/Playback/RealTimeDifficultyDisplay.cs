// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using System.Linq;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Beatmaps.Difficulty;
using Color4Extensions = osu.Framework.Extensions.Color4Extensions.Color4Extensions;

namespace BeatSight.Game.Screens.Playback
{
    /// <summary>
    /// ╔══════════════════════════════════════════════════════════════════════════════╗
    /// ║           REAL-TIME DIFFICULTY DISPLAY v1.0                                  ║
    /// ╠══════════════════════════════════════════════════════════════════════════════╣
    /// ║                                                                              ║
    /// ║  Beautiful, animated display showing:                                        ║
    /// ║  • Live star rating to hundredths (e.g., 5.73★)                             ║
    /// ║  • Skill breakdown bars (Speed, Coordination, Rhythm, etc.)                 ║
    /// ║  • Difficulty graph preview                                                  ║
    /// ║  • Peak difficulty indicator                                                 ║
    /// ║  • Dynamic color coding based on difficulty level                           ║
    /// ║                                                                              ║
    /// ║  DESIGN PHILOSOPHY:                                                          ║
    /// ║  - Non-intrusive but informative                                             ║
    /// ║  - Smooth animations for all transitions                                     ║
    /// ║  - Color-coded difficulty tiers                                              ║
    /// ║  - Expandable for detailed skill breakdown                                   ║
    /// ║                                                                              ║
    /// ╚══════════════════════════════════════════════════════════════════════════════╝
    /// </summary>
    public partial class RealTimeDifficultyDisplay : CompositeDrawable
    {
        #region Constants

        private const float COLLAPSED_WIDTH = 180f;
        private const float EXPANDED_WIDTH = 280f;
        private const float HEIGHT = 120f;
        private const float SKILL_BAR_HEIGHT = 4f;
        private const float CORNER_RADIUS = 12f;
        private const double ANIMATION_DURATION = 200;
        private const double PULSE_DURATION = 600;

        #endregion

        #region Difficulty Color Tiers

        private static readonly Color4 TierBeginner = new Color4(100, 200, 100, 255);      // Green
        private static readonly Color4 TierEasy = new Color4(140, 200, 100, 255);          // Light Green
        private static readonly Color4 TierNormal = new Color4(220, 200, 80, 255);         // Yellow
        private static readonly Color4 TierHard = new Color4(255, 160, 60, 255);           // Orange
        private static readonly Color4 TierExpert = new Color4(255, 100, 80, 255);         // Red-Orange
        private static readonly Color4 TierMaster = new Color4(255, 60, 100, 255);         // Red-Pink
        private static readonly Color4 TierLegendary = new Color4(200, 60, 200, 255);      // Purple
        private static readonly Color4 TierInhuman = new Color4(120, 60, 220, 255);        // Deep Purple
        private static readonly Color4 TierTranscendent = new Color4(60, 120, 255, 255);   // Blue (beyond)

        #endregion

        #region Visual Components

        private Container mainContainer = null!;
        private Box backgroundBox = null!;
        private Container starContainer = null!;
        private SpriteText starRatingText = null!;
        private SpriteText starSymbol = null!;
        private SpriteText difficultyLabel = null!;
        private SpriteText peakIndicator = null!;

        private Container skillBarsContainer = null!;
        private Dictionary<string, SkillBar> skillBars = new();

        private Container graphContainer = null!;
        private DifficultyGraphPreview difficultyGraph = null!;
        private Box graphPositionMarker = null!;

        private Box glowOverlay = null!;
        private Box peakPulse = null!;

        #endregion

        #region State

        private readonly BindableBool isExpanded = new BindableBool(false);
        private double currentStarRating = 0;
        private double displayedStarRating = 0;
        private double peakStarRating = 0;
        private bool isAtPeak = false;
        private RealTimeStarRating? ratingTracker;

        #endregion

        #region Bindables

        /// <summary>
        /// Bindable for the current star rating value.
        /// </summary>
        public readonly BindableDouble StarRating = new BindableDouble(0)
        {
            MinValue = 0,
            MaxValue = 12,
            Precision = 0.01
        };

        /// <summary>
        /// Bindable for visibility of the display.
        /// </summary>
        public readonly BindableBool ShowDifficulty = new BindableBool(true);

        #endregion

        public RealTimeDifficultyDisplay()
        {
            Anchor = Anchor.TopRight;
            Origin = Anchor.TopRight;
            Size = new Vector2(COLLAPSED_WIDTH, HEIGHT);
            Margin = new MarginPadding { Top = 10, Right = 10 };
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            Masking = true;
            CornerRadius = CORNER_RADIUS;
            EdgeEffect = new EdgeEffectParameters
            {
                Type = EdgeEffectType.Shadow,
                Colour = Color4Extensions.Opacity(Color4.Black, 0.4f),
                Radius = 8,
                Offset = new Vector2(0, 2)
            };

            InternalChildren = new Drawable[]
            {
                mainContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Children = new Drawable[]
                    {
                        // Background with gradient
                        backgroundBox = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(20, 25, 35, 230)
                        },

                        // Glow overlay for difficulty intensity
                        glowOverlay = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Alpha = 0.15f,
                            Colour = TierBeginner,
                            Blending = BlendingParameters.Additive
                        },

                        // Peak pulse effect
                        peakPulse = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Alpha = 0,
                            Colour = Color4.White,
                            Blending = BlendingParameters.Additive
                        },

                        // Main content
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Padding = new MarginPadding(12),
                            Spacing = new Vector2(0, 6),
                            Children = new Drawable[]
                            {
                                // Star rating row
                                createStarRatingRow(),

                                // Difficulty label
                                difficultyLabel = new SpriteText
                                {
                                    Anchor = Anchor.TopLeft,
                                    Origin = Anchor.TopLeft,
                                    Font = FontUsage.Default.With(size: 11, weight: "SemiBold"),
                                    Colour = Color4Extensions.Opacity(Color4.White, 0.7f),
                                    Text = "BEGINNER"
                                },

                                // Skill bars
                                skillBarsContainer = createSkillBars(),

                                // Mini difficulty graph
                                graphContainer = createDifficultyGraph()
                            }
                        },

                        // Peak indicator badge
                        peakIndicator = new SpriteText
                        {
                            Anchor = Anchor.TopRight,
                            Origin = Anchor.TopRight,
                            Margin = new MarginPadding { Top = 8, Right = 8 },
                            Font = FontUsage.Default.With(size: 9, weight: "Bold"),
                            Colour = Color4.Gold,
                            Text = "PEAK!",
                            Alpha = 0
                        }
                    }
                }
            };

            // Bind events
            ShowDifficulty.BindValueChanged(e =>
            {
                this.FadeTo(e.NewValue ? 1 : 0, ANIMATION_DURATION, Easing.OutQuint);
            }, true);

            isExpanded.BindValueChanged(e =>
            {
                float targetWidth = e.NewValue ? EXPANDED_WIDTH : COLLAPSED_WIDTH;
                this.ResizeWidthTo(targetWidth, ANIMATION_DURATION * 2, Easing.OutQuint);
                skillBarsContainer.FadeTo(e.NewValue ? 1 : 0.6f, ANIMATION_DURATION);
            }, true);

            StarRating.BindValueChanged(e =>
            {
                currentStarRating = e.NewValue;
            }, true);
        }

        private Drawable createStarRatingRow()
        {
            return starContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(4, 0),
                        Children = new Drawable[]
                        {
                            starRatingText = new SpriteText
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Font = FontUsage.Default.With(size: 32, weight: "Bold"),
                                Colour = Color4.White,
                                Text = "0.00"
                            },
                            starSymbol = new SpriteText
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Font = FontUsage.Default.With(size: 28),
                                Colour = Color4.Gold,
                                Text = "★"
                            }
                        }
                    }
                }
            };
        }

        private Container createSkillBars()
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Alpha = 0.6f,
                Child = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 3)
                }
            };

            var skills = new[]
            {
                ("SPD", "Speed", new Color4(255, 100, 100, 255)),
                ("CRD", "Coord", new Color4(100, 200, 255, 255)),
                ("RHY", "Rhythm", new Color4(200, 100, 255, 255)),
                ("TEC", "Tech", new Color4(255, 200, 100, 255)),
                ("STA", "Stamina", new Color4(100, 255, 150, 255))
            };

            var flowContainer = (FillFlowContainer)container.Child;

            foreach (var (abbrev, name, color) in skills)
            {
                var bar = new SkillBar(abbrev, name, color);
                skillBars[abbrev] = bar;
                flowContainer.Add(bar);
            }

            return container;
        }

        private Container createDifficultyGraph()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 20,
                Masking = true,
                CornerRadius = 4,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.Opacity(Color4.Black, 0.3f)
                    },
                    difficultyGraph = new DifficultyGraphPreview
                    {
                        RelativeSizeAxes = Axes.Both
                    },
                    graphPositionMarker = new Box
                    {
                        Width = 2,
                        RelativeSizeAxes = Axes.Y,
                        Colour = Color4.White,
                        Alpha = 0.8f
                    }
                }
            };
        }

        protected override void Update()
        {
            base.Update();

            // Smooth animation towards current star rating
            double delta = currentStarRating - displayedStarRating;
            displayedStarRating += delta * Math.Min(Time.Elapsed / 50.0, 1.0);

            // Update display
            starRatingText.Text = displayedStarRating.ToString("F2");

            // Update colors based on difficulty
            var tierColor = GetTierColor(displayedStarRating);
            glowOverlay.Colour = tierColor;
            starSymbol.Colour = tierColor;

            // Update difficulty label
            difficultyLabel.Text = GetDifficultyTierName(displayedStarRating);
            difficultyLabel.Colour = Color4Extensions.Opacity(tierColor, 0.9f);
        }

        /// <summary>
        /// Initialize with a beatmap for real-time tracking.
        /// </summary>
        public void Initialize(Beatmap beatmap, double clockRate = 1.0)
        {
            ratingTracker = new RealTimeStarRating(beatmap, clockRate);
            ratingTracker.Initialize();
            ratingTracker.OnRatingUpdate += HandleRatingUpdate;
            ratingTracker.OnPeakReached += HandlePeakReached;

            // Initialize the difficulty graph
            var graphPoints = ratingTracker.GetDifficultyGraph(100);
            difficultyGraph.SetData(graphPoints);

            peakStarRating = ratingTracker.PeakStarRating;
        }

        /// <summary>
        /// Update based on current playback time.
        /// </summary>
        public void UpdateTime(double currentTime)
        {
            ratingTracker?.Update(currentTime);
        }

        private void HandleRatingUpdate(RealTimeRatingUpdate update)
        {
            currentStarRating = update.DisplayedStarRating;
            StarRating.Value = update.DisplayedStarRating;

            // Update skill bars
            if (skillBars.TryGetValue("SPD", out var speedBar))
                speedBar.SetValue(update.SpeedRating / 10.0);
            if (skillBars.TryGetValue("CRD", out var coordBar))
                coordBar.SetValue(update.CoordinationRating / 10.0);
            if (skillBars.TryGetValue("RHY", out var rhythmBar))
                rhythmBar.SetValue(update.RhythmRating / 10.0);
            if (skillBars.TryGetValue("TEC", out var techBar))
                techBar.SetValue(update.TechniqueRating / 10.0);
            if (skillBars.TryGetValue("STA", out var staminaBar))
                staminaBar.SetValue(update.StaminaRating / 10.0);

            // Update graph position
            graphPositionMarker.X = (float)(update.Progress * graphContainer.DrawWidth);

            // Handle peak state
            if (update.IsAtPeak != isAtPeak)
            {
                isAtPeak = update.IsAtPeak;
                if (isAtPeak)
                {
                    TriggerPeakAnimation();
                }
                else
                {
                    peakIndicator.FadeOut(ANIMATION_DURATION);
                }
            }
        }

        private void HandlePeakReached(PeakDifficultyEvent peakEvent)
        {
            TriggerPeakAnimation();
        }

        private void TriggerPeakAnimation()
        {
            // Show peak indicator
            peakIndicator.FadeIn(ANIMATION_DURATION / 2).Then().FlashColour(Color4.White, PULSE_DURATION);

            // Pulse the whole display
            peakPulse.FadeTo(0.3f, PULSE_DURATION / 4, Easing.OutQuint)
                     .Then().FadeTo(0, PULSE_DURATION * 0.75, Easing.InQuint);

            // Scale punch
            starContainer.ScaleTo(1.1f, PULSE_DURATION / 4, Easing.OutQuint)
                        .Then().ScaleTo(1f, PULSE_DURATION * 0.75, Easing.OutElastic);
        }

        /// <summary>
        /// Manually set the star rating (for testing or non-tracked mode).
        /// </summary>
        public void SetStarRating(double rating)
        {
            currentStarRating = rating;
            StarRating.Value = rating;
        }

        /// <summary>
        /// Reset the display to initial state.
        /// </summary>
        public void Reset()
        {
            currentStarRating = 0;
            displayedStarRating = 0;
            StarRating.Value = 0;
            isAtPeak = false;
            graphPositionMarker.X = 0;
            peakIndicator.Alpha = 0;

            foreach (var bar in skillBars.Values)
                bar.SetValue(0);
        }

        /// <summary>
        /// Get the color for a difficulty tier.
        /// </summary>
        public static Color4 GetTierColor(double starRating)
        {
            return starRating switch
            {
                < 1 => TierBeginner,
                < 2 => TierEasy,
                < 3 => TierNormal,
                < 4 => TierHard,
                < 5 => TierExpert,
                < 6 => TierMaster,
                < 7 => TierLegendary,
                < 8 => TierInhuman,
                _ => TierTranscendent
            };
        }

        /// <summary>
        /// Get the name for a difficulty tier.
        /// </summary>
        public static string GetDifficultyTierName(double starRating)
        {
            return starRating switch
            {
                < 1 => "BEGINNER",
                < 2 => "EASY",
                < 3 => "NORMAL",
                < 4 => "HARD",
                < 5 => "EXPERT",
                < 6 => "MASTER",
                < 7 => "LEGENDARY",
                < 8 => "INHUMAN",
                _ => "TRANSCENDENT"
            };
        }

        #region Nested Components

        /// <summary>
        /// Individual skill bar component.
        /// </summary>
        private partial class SkillBar : CompositeDrawable
        {
            private readonly Box fillBar;
            private readonly SpriteText label;
            private readonly Color4 barColor;
            private double targetValue = 0;
            private double currentValue = 0;

            public SkillBar(string abbreviation, string name, Color4 color)
            {
                barColor = color;
                RelativeSizeAxes = Axes.X;
                Height = SKILL_BAR_HEIGHT + 10;

                InternalChildren = new Drawable[]
                {
                    label = new SpriteText
                    {
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Font = FontUsage.Default.With(size: 8, weight: "SemiBold"),
                        Colour = Color4Extensions.Opacity(color, 0.8f),
                        Text = abbreviation,
                        Width = 24
                    },
                    new Container
                    {
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        X = 28,
                        RelativeSizeAxes = Axes.X,
                        Width = 0.75f,
                        Height = SKILL_BAR_HEIGHT,
                        Masking = true,
                        CornerRadius = SKILL_BAR_HEIGHT / 2,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = Color4Extensions.Opacity(Color4.White, 0.1f)
                            },
                            fillBar = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Width = 0,
                                Colour = color
                            }
                        }
                    }
                };
            }

            public void SetValue(double value)
            {
                targetValue = Math.Clamp(value, 0, 1);
            }

            protected override void Update()
            {
                base.Update();

                double delta = targetValue - currentValue;
                currentValue += delta * Math.Min(Time.Elapsed / 80.0, 1.0);
                fillBar.Width = (float)currentValue;
            }
        }

        /// <summary>
        /// Mini difficulty graph showing the entire beatmap's difficulty curve.
        /// </summary>
        private partial class DifficultyGraphPreview : CompositeDrawable
        {
            private List<DifficultyGraphPoint> dataPoints = new();

            public DifficultyGraphPreview()
            {
                RelativeSizeAxes = Axes.Both;
            }

            public void SetData(IEnumerable<DifficultyGraphPoint> points)
            {
                dataPoints = points.ToList();
                Invalidate();
            }

            protected override void Update()
            {
                base.Update();

                if (dataPoints.Count < 2) return;

                // Recreate graph visuals
                ClearInternal();

                double maxRating = dataPoints.Max(p => p.StarRating);
                if (maxRating <= 0) maxRating = 1;

                var gradientContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                };

                // Create gradient bars for each segment
                for (int i = 0; i < dataPoints.Count - 1; i++)
                {
                    float xStart = (float)dataPoints[i].Progress;
                    float xEnd = (float)dataPoints[i + 1].Progress;
                    float height = (float)(dataPoints[i].StarRating / maxRating);

                    var color = GetTierColor(dataPoints[i].StarRating);

                    gradientContainer.Add(new Box
                    {
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        RelativePositionAxes = Axes.X,
                        RelativeSizeAxes = Axes.Both,
                        X = xStart,
                        Width = xEnd - xStart,
                        Height = height,
                        Colour = ColourInfo.GradientVertical(
                            Color4Extensions.Opacity(color, 0.8f),
                            Color4Extensions.Opacity(color, 0.3f)
                        )
                    });
                }

                AddInternal(gradientContainer);
            }
        }

        #endregion
    }
}
