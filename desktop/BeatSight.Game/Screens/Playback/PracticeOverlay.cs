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
    internal partial class PracticeOverlay : CompositeDrawable
    {
        private readonly SpriteText modeText;
        private readonly SpriteText loopText;
        private readonly SpriteText speedText;
        private readonly SpriteText metronomeText;
        private readonly SpriteText statsText;
        private readonly SpriteText hintText;
        private readonly Box loopBadge;

        public PracticeOverlay()
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;
            Anchor = Anchor.TopCentre;
            Origin = Anchor.TopCentre;
            Padding = new MarginPadding { Horizontal = 32, Vertical = 6 };

            var background = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 14,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = new Color4(0, 0, 0, 60),
                    Radius = 14,
                    Roundness = 1.2f
                }
            };

            background.Add(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    UITheme.Emphasise(UITheme.Surface, 1.05f),
                    UITheme.Emphasise(UITheme.Background, 0.92f))
            });

            loopBadge = new Box
            {
                Size = new Vector2(6, 30),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Margin = new MarginPadding { Left = 12, Right = 10 },
                Colour = UITheme.AccentPrimary,
                Alpha = 0.8f
            };

            modeText = createLabel();
            loopText = createLabel();
            speedText = createLabel();
            metronomeText = createLabel();
            statsText = createLabel(BeatSightFont.Caption(14f));
            hintText = createLabel(BeatSightFont.Caption(13f));
            hintText.Colour = UITheme.TextMuted;

            var content = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(18, 0),
                Padding = new MarginPadding { Left = 26, Right = 26, Top = 10, Bottom = 10 },
                Children = new Drawable[]
                {
                    modeText,
                    loopText,
                    speedText,
                    metronomeText,
                    statsText,
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Width = 0.35f,
                        Child = hintText
                    }
                }
            };

            background.Add(content);

            InternalChildren = new Drawable[]
            {
                background,
                loopBadge
            };

            SetLoopState(null, null, 0);
            SetSpeed(1.0);
            SetMetronome(false);
            SetMode(GameplayMode.Manual);
            SetStats(TimeSpan.Zero, TimeSpan.Zero);
            hintText.Text = "[ start • ] end • C clear • Space play/pause";
        }

        public void SetMode(GameplayMode mode)
        {
            modeText.Text = mode switch
            {
                GameplayMode.Manual => "Flow: Manual",
                GameplayMode.Auto => "Flow: Guided",
                _ => $"Flow: {mode}"
            };
        }

        public void SetLoopState(double? startMs, double? endMs, int loopsCompleted)
        {
            bool hasStart = startMs.HasValue;
            bool hasEnd = endMs.HasValue && endMs > startMs;

            if (!hasStart && !hasEnd)
            {
                loopText.Text = "Loop: inactive ([ to mark start)";
                loopBadge.Colour = UITheme.Divider;
                loopBadge.Alpha = 0.45f;
                return;
            }

            if (hasStart && !hasEnd)
            {
                loopText.Text = $"Loop start set @ {formatTimestamp(startMs!.Value)}";
                loopBadge.Colour = UITheme.AccentSecondary;
                loopBadge.Alpha = 0.7f;
                return;
            }

            double duration = Math.Max(0, endMs!.Value - startMs!.Value);
            loopText.Text = $"Loop: {formatTimestamp(startMs.Value)} → {formatTimestamp(endMs.Value)} ({formatDuration(duration)}) • #{loopsCompleted}";
            loopBadge.Colour = UITheme.AccentPrimary;
            loopBadge.Alpha = 0.9f;
        }

        public void SetSpeed(double speed)
        {
            speedText.Text = $"Speed: {speed:0.00}x";
        }

        public void SetMetronome(bool enabled)
        {
            metronomeText.Text = enabled ? "Metronome: on" : "Metronome: off";
            metronomeText.Colour = enabled ? UITheme.AccentPrimary : UITheme.TextSecondary;
        }

        public void SetStats(TimeSpan sessionElapsed, TimeSpan loopedDuration)
        {
            statsText.Text = $"Session {formatDuration(sessionElapsed.TotalMilliseconds)} • Looped {formatDuration(loopedDuration.TotalMilliseconds)}";
        }

        public void PulseLoop()
        {
            loopBadge.FlashColour(UITheme.AccentPrimary, 120, Easing.OutQuint);
        }

        private SpriteText createLabel(FontUsage? font = null)
        {
            return new BeatSightSpriteText
            {
                Font = font ?? BeatSightFont.Section(14f),
                Colour = UITheme.TextSecondary,
                Alpha = 0.96f
            };
        }

        private static string formatTimestamp(double ms)
        {
            if (ms < 0)
                ms = 0;

            TimeSpan t = TimeSpan.FromMilliseconds(ms);
            return $"{(int)t.TotalMinutes}:{t.Seconds:D2}.{t.Milliseconds:D3}";
        }

        private static string formatDuration(double ms)
        {
            if (ms <= 0)
                return "0.0s";

            double seconds = ms / 1000.0;
            return seconds < 60 ? $"{seconds:0.0}s" : $"{seconds / 60:0.#}m";
        }
    }
}
