using System;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback
{
    /// <summary>
    /// Enhanced practice mode overlay for drum analysis and learning.
    /// 
    /// Features:
    /// - Loop region selection with visual feedback
    /// - Speed adjustment display
    /// - Metronome status
    /// - Session statistics
    /// - Contextual keyboard hints
    /// 
    /// Designed as an analysis/learning tool, not a game interface.
    /// </summary>
    internal partial class PracticeOverlay : CompositeDrawable
    {
        #region Visual Components

        private readonly Container mainContainer;
        private readonly SpriteText modeText;
        private readonly SpriteText loopText;
        private readonly SpriteText speedText;
        private readonly SpriteText metronomeText;
        private readonly SpriteText statsText;
        private readonly SpriteText hintText;
        private readonly Box loopBadge;
        private readonly Box loopProgressBar;
        private readonly Container loopProgressContainer;

        #endregion

        #region State

        private double? currentLoopStart;
        private double? currentLoopEnd;
        private int currentLoopsCompleted;
        private double currentSpeed = 1.0;
        private bool metronomeEnabled;
        private GameplayMode currentMode = GameplayMode.Manual;

        #endregion

        #region Design Constants

        private static readonly Color4 LoopActiveColor = new Color4(100, 180, 255, 255);
        private static readonly Color4 LoopInactiveColor = new Color4(80, 80, 100, 180);
        private static readonly Color4 LoopPendingColor = new Color4(255, 180, 80, 220);
        private const float BadgeWidth = 6f;
        private const float BadgeHeight = 32f;
        private const float CornerRadiusValue = 16f;
        private const double PulseAnimationDuration = 150;

        #endregion

        public PracticeOverlay()
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;
            Anchor = Anchor.TopCentre;
            Origin = Anchor.TopCentre;
            Padding = new MarginPadding { Horizontal = 24, Vertical = 8 };

            mainContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = CornerRadiusValue,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = new Color4(0, 0, 0, 80),
                    Radius = 16,
                    Roundness = 2f,
                    Offset = new Vector2(0, 2)
                }
            };

            // Gradient background
            mainContainer.Add(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    UITheme.Emphasise(UITheme.Surface, 1.08f),
                    UITheme.Emphasise(UITheme.Background, 0.88f))
            });

            // Subtle top border highlight
            mainContainer.Add(new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 1,
                Colour = new Color4(255, 255, 255, 15),
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            });

            // Loop indicator badge (vertical bar on left side)
            loopBadge = new Box
            {
                Size = new Vector2(BadgeWidth, BadgeHeight),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Margin = new MarginPadding { Left = 14 },
                Colour = LoopInactiveColor,
                Alpha = 0.6f
            };

            // Loop progress indicator (shows progress through current loop)
            loopProgressContainer = new Container
            {
                Size = new Vector2(BadgeWidth, BadgeHeight),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Margin = new MarginPadding { Left = 14 },
                Masking = true,
                Alpha = 0,
                Child = loopProgressBar = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 0,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Colour = LoopActiveColor.Opacity(0.8f)
                }
            };

            modeText = CreateLabel(isBold: true);
            loopText = CreateLabel();
            speedText = CreateLabel();
            metronomeText = CreateLabel();
            statsText = CreateLabel(fontSize: 13f);
            hintText = CreateLabel(fontSize: 12f);
            hintText.Colour = UITheme.TextMuted;

            var content = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(20, 0),
                Padding = new MarginPadding { Left = 32, Right = 20, Top = 12, Bottom = 12 },
                Children = new Drawable[]
                {
                    CreateInfoSection(modeText),
                    CreateSeparator(),
                    CreateInfoSection(loopText),
                    CreateSeparator(),
                    CreateInfoSection(speedText),
                    CreateSeparator(),
                    CreateInfoSection(metronomeText),
                    CreateSeparator(),
                    CreateInfoSection(statsText),
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Child = hintText
                    }
                }
            };

            mainContainer.Add(content);

            InternalChildren = new Drawable[]
            {
                mainContainer,
                loopBadge,
                loopProgressContainer
            };

            // Initialize with defaults
            SetLoopState(null, null, 0);
            SetSpeed(1.0);
            SetMetronome(false);
            SetMode(GameplayMode.Manual);
            SetStats(TimeSpan.Zero, TimeSpan.Zero);
            UpdateHints();
        }

        #region Public API

        public void SetMode(GameplayMode mode)
        {
            currentMode = mode;
            modeText.Text = mode switch
            {
                GameplayMode.Manual => "Manual Mode",
                GameplayMode.Auto => "Guided Mode",
                _ => mode.ToString()
            };
        }

        public void SetLoopState(double? startMs, double? endMs, int loopsCompleted)
        {
            currentLoopStart = startMs;
            currentLoopEnd = endMs;
            currentLoopsCompleted = loopsCompleted;

            bool hasStart = startMs.HasValue;
            bool hasEnd = endMs.HasValue && endMs > startMs;

            if (!hasStart && !hasEnd)
            {
                loopText.Text = "Loop: off";
                loopBadge.Colour = LoopInactiveColor;
                loopBadge.FadeTo(0.5f, 200);
                loopProgressContainer.FadeOut(200);
                UpdateHints();
                return;
            }

            if (hasStart && !hasEnd)
            {
                loopText.Text = $"Loop: {FormatTimestamp(startMs!.Value)} → ...";
                loopBadge.Colour = LoopPendingColor;
                loopBadge.FadeTo(0.85f, 150);
                loopProgressContainer.FadeOut(150);
                UpdateHints();
                return;
            }

            double duration = endMs!.Value - startMs!.Value;
            string durationStr = FormatDuration(duration);
            loopText.Text = loopsCompleted > 0
                ? $"Loop: {FormatTimestamp(startMs.Value)} → {FormatTimestamp(endMs.Value)} ({durationStr}) ×{loopsCompleted}"
                : $"Loop: {FormatTimestamp(startMs.Value)} → {FormatTimestamp(endMs.Value)} ({durationStr})";

            loopBadge.Colour = LoopActiveColor;
            loopBadge.FadeTo(0.95f, 150);
            loopProgressContainer.FadeIn(200);
            UpdateHints();
        }

        /// <summary>
        /// Update loop progress visualization (0-1).
        /// </summary>
        public void SetLoopProgress(float progress)
        {
            if (!currentLoopStart.HasValue || !currentLoopEnd.HasValue)
                return;

            progress = Math.Clamp(progress, 0f, 1f);
            loopProgressBar.ResizeHeightTo(BadgeHeight * progress, 50, Easing.OutQuad);
        }

        public void SetSpeed(double speed)
        {
            currentSpeed = speed;
            string speedLabel = speed < 0.8 ? "Slow" : speed > 1.2 ? "Fast" : "Speed";
            speedText.Text = $"{speedLabel}: {speed:0.00}x";

            // Color coding for speed
            speedText.Colour = speed switch
            {
                < 0.5 => new Color4(255, 150, 100, 255),
                < 0.8 => new Color4(255, 200, 100, 255),
                > 1.5 => new Color4(100, 200, 255, 255),
                > 1.2 => new Color4(150, 220, 180, 255),
                _ => UITheme.TextSecondary
            };
        }

        public void SetMetronome(bool enabled)
        {
            metronomeEnabled = enabled;
            metronomeText.Text = enabled ? "Metro: ON" : "Metro: OFF";
            metronomeText.Colour = enabled ? LoopActiveColor : UITheme.TextMuted;
        }

        public void SetStats(TimeSpan sessionElapsed, TimeSpan loopedDuration)
        {
            string sessionStr = FormatDuration(sessionElapsed.TotalMilliseconds);
            string loopedStr = FormatDuration(loopedDuration.TotalMilliseconds);
            statsText.Text = $"Session: {sessionStr} / {loopedStr} looped";
        }

        public void PulseLoop()
        {
            loopBadge.FlashColour(Color4.White, PulseAnimationDuration, Easing.OutQuint);
            loopProgressBar.Height = 0; // Reset progress on loop
        }

        /// <summary>
        /// Flash the entire overlay to indicate an action.
        /// </summary>
        public void FlashAction()
        {
            mainContainer.FlashColour(new Color4(255, 255, 255, 30), 100, Easing.OutQuint);
        }

        #endregion

        #region Hint System

        private void UpdateHints()
        {
            bool hasLoop = currentLoopStart.HasValue && currentLoopEnd.HasValue;
            bool hasPartialLoop = currentLoopStart.HasValue && !currentLoopEnd.HasValue;

            if (hasLoop)
            {
                hintText.Text = "C clear • [ ] adjust • Space ▶/⏸";
            }
            else if (hasPartialLoop)
            {
                hintText.Text = "] set end • C cancel • Space ▶/⏸";
            }
            else
            {
                hintText.Text = "[ set loop start • Space ▶/⏸ • R restart";
            }
        }

        #endregion

        #region Factory Helpers

        private static SpriteText CreateLabel(float fontSize = 14f, bool isBold = false)
        {
            return new BeatSightSpriteText
            {
                Font = isBold ? BeatSightFont.Section(fontSize) : BeatSightFont.Caption(fontSize),
                Colour = UITheme.TextSecondary,
                Alpha = 0.96f
            };
        }

        private static Container CreateInfoSection(SpriteText text)
        {
            return new Container
            {
                AutoSizeAxes = Axes.Both,
                Child = text
            };
        }

        private static Box CreateSeparator()
        {
            return new Box
            {
                Size = new Vector2(1, 16),
                Colour = UITheme.Divider,
                Alpha = 0.4f,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };
        }

        #endregion

        #region Formatting Helpers

        private static string FormatTimestamp(double ms)
        {
            if (ms < 0) ms = 0;

            TimeSpan t = TimeSpan.FromMilliseconds(ms);
            return $"{(int)t.TotalMinutes}:{t.Seconds:D2}.{t.Milliseconds / 100:D1}";
        }

        private static string FormatDuration(double ms)
        {
            if (ms <= 0) return "0s";

            double seconds = ms / 1000.0;
            if (seconds < 60) return $"{seconds:0.0}s";
            if (seconds < 3600) return $"{seconds / 60:0.0}m";
            return $"{seconds / 3600:0.0}h";
        }

        #endregion
    }
}
