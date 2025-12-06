// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Toast notification types that define the visual style and icon.
    /// </summary>
    public enum ToastType
    {
        Info,
        Success,
        Warning,
        Error
    }

    /// <summary>
    /// A modern toast notification component with slide-in animations,
    /// auto-dismiss functionality, and visual polish inspired by osu!'s notifications.
    /// </summary>
    public partial class ToastNotification : CompositeDrawable
    {
        private const float toast_width = 350;
        private const float toast_height = 72;
        private const float corner_radius = 12;
        private const float slide_distance = 400;
        private const double appear_duration = 400;
        private const double dismiss_duration = 300;
        private const double default_display_duration = 4000;
        private const Easing slide_easing = Easing.OutQuint;

        public string Title { get; init; } = string.Empty;
        public string Description { get; init; } = string.Empty;
        public ToastType Type { get; init; } = ToastType.Info;
        public double DisplayDuration { get; init; } = default_display_duration;
        public Action? OnDismiss { get; init; }

        private Container mainContainer = null!;
        private Box backgroundBox = null!;
        private Box accentStripe = null!;
        private Box progressBar = null!;
        private SpriteIcon icon = null!;
        private bool isDismissed;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(toast_width, toast_height);
            Origin = Anchor.TopRight;
            Anchor = Anchor.TopRight;
            Alpha = 0;
            Position = new Vector2(slide_distance, 0);

            InternalChild = mainContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = corner_radius,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = Color4.Black.Opacity(0.4f),
                    Radius = 20,
                    Offset = new Vector2(0, 4)
                },
                Children = new Drawable[]
                {
                    // Background
                    backgroundBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("1a1a2e").Opacity(0.95f)
                    },

                    // Accent stripe on the left
                    accentStripe = new Box
                    {
                        Width = 4,
                        RelativeSizeAxes = Axes.Y,
                        Colour = GetAccentColour(Type)
                    },

                    // Content container
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Left = 16, Right = 16, Top = 12, Bottom = 16 },
                        Children = new Drawable[]
                        {
                            // Icon
                            icon = new SpriteIcon
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Size = new Vector2(24),
                                Icon = GetIcon(Type),
                                Colour = GetAccentColour(Type)
                            },

                            // Text container
                            new FillFlowContainer
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 2),
                                Padding = new MarginPadding { Left = 40 },
                                Children = new Drawable[]
                                {
                                    new SpriteText
                                    {
                                        Text = Title,
                                        Font = new FontUsage("Nunito", size: 16, weight: "Bold"),
                                        Colour = Color4.White
                                    },
                                    new SpriteText
                                    {
                                        Text = Description,
                                        Font = new FontUsage("Nunito", size: 13),
                                        Colour = Color4.White.Opacity(0.7f),
                                        MaxWidth = toast_width - 90,
                                        Truncate = true
                                    }
                                }
                            },

                            // Close button
                            new CloseButton
                            {
                                Anchor = Anchor.TopRight,
                                Origin = Anchor.TopRight,
                                Size = new Vector2(20),
                                Position = new Vector2(4, -4),
                                Action = () => Dismiss()
                            }
                        }
                    },

                    // Progress bar at bottom
                    new Container
                    {
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        RelativeSizeAxes = Axes.X,
                        Height = 3,
                        Masking = true,
                        CornerRadius = 1.5f,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = Color4.White.Opacity(0.1f)
                            },
                            progressBar = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = GetAccentColour(Type).Opacity(0.8f),
                                Width = 1
                            }
                        }
                    }
                }
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            Show();
        }

        public override void Show()
        {
            // Slide in from right with glow pulse
            this.FadeIn(appear_duration * 0.5)
                .MoveToX(0, appear_duration, slide_easing);

            // Pulse the accent stripe
            accentStripe.FlashColour(Color4.White, 400, Easing.OutQuint);

            // Animate icon
            icon.ScaleTo(1.3f)
                .ScaleTo(1f, 400, Easing.OutBack);

            // Progress bar countdown
            if (DisplayDuration > 0)
            {
                progressBar.ResizeWidthTo(0, DisplayDuration, Easing.None)
                    .OnComplete(_ => Dismiss());
            }
        }

        public void Dismiss()
        {
            if (isDismissed) return;
            isDismissed = true;

            // Slide out to the right
            this.FadeOut(dismiss_duration, Easing.InQuint)
                .MoveToX(slide_distance, dismiss_duration, Easing.InQuint)
                .OnComplete(_ =>
                {
                    OnDismiss?.Invoke();
                    Expire();
                });
        }

        /// <summary>
        /// Pause the auto-dismiss timer (e.g., on hover).
        /// </summary>
        public void PauseTimer()
        {
            progressBar.ClearTransforms();
        }

        /// <summary>
        /// Resume the auto-dismiss timer with remaining time.
        /// </summary>
        public void ResumeTimer()
        {
            if (isDismissed || progressBar.Width <= 0) return;

            double remainingTime = DisplayDuration * progressBar.Width;
            progressBar.ResizeWidthTo(0, remainingTime, Easing.None)
                .OnComplete(_ => Dismiss());
        }

        protected override bool OnHover(osu.Framework.Input.Events.HoverEvent e)
        {
            PauseTimer();
            mainContainer.ScaleTo(1.02f, 200, Easing.OutQuint);
            backgroundBox.FadeColour(Color4Extensions.FromHex("242444"), 200);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(osu.Framework.Input.Events.HoverLostEvent e)
        {
            ResumeTimer();
            mainContainer.ScaleTo(1f, 200, Easing.OutQuint);
            backgroundBox.FadeColour(Color4Extensions.FromHex("1a1a2e").Opacity(0.95f), 200);
            base.OnHoverLost(e);
        }

        private static Color4 GetAccentColour(ToastType type) => type switch
        {
            ToastType.Success => Color4Extensions.FromHex("00ff88"),
            ToastType.Warning => Color4Extensions.FromHex("ffaa00"),
            ToastType.Error => Color4Extensions.FromHex("ff4466"),
            _ => Color4Extensions.FromHex("00d4ff") // Info - Cyan
        };

        private static IconUsage GetIcon(ToastType type) => type switch
        {
            ToastType.Success => FontAwesome.Solid.CheckCircle,
            ToastType.Warning => FontAwesome.Solid.ExclamationTriangle,
            ToastType.Error => FontAwesome.Solid.TimesCircle,
            _ => FontAwesome.Solid.InfoCircle
        };

        /// <summary>
        /// Small close button for dismissing notifications.
        /// </summary>
        private partial class CloseButton : CompositeDrawable
        {
            public Action? Action { get; set; }

            private Box background = null!;
            private SpriteIcon icon = null!;

            [BackgroundDependencyLoader]
            private void load()
            {
                Masking = true;
                CornerRadius = Size.X / 2;

                InternalChildren = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White.Opacity(0),
                    },
                    icon = new SpriteIcon
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Size = new Vector2(10),
                        Icon = FontAwesome.Solid.Times,
                        Colour = Color4.White.Opacity(0.5f)
                    }
                };
            }

            protected override bool OnHover(osu.Framework.Input.Events.HoverEvent e)
            {
                background.FadeColour(Color4.White.Opacity(0.2f), 150);
                icon.FadeColour(Color4.White, 150);
                this.ScaleTo(1.1f, 150, Easing.OutQuint);
                return true;
            }

            protected override void OnHoverLost(osu.Framework.Input.Events.HoverLostEvent e)
            {
                background.FadeColour(Color4.White.Opacity(0), 150);
                icon.FadeColour(Color4.White.Opacity(0.5f), 150);
                this.ScaleTo(1f, 150, Easing.OutQuint);
            }

            protected override bool OnClick(osu.Framework.Input.Events.ClickEvent e)
            {
                Action?.Invoke();
                return true;
            }
        }
    }

    /// <summary>
    /// Container that manages multiple toast notifications with stacking behavior.
    /// </summary>
    public partial class ToastContainer : CompositeDrawable
    {
        private const float spacing = 12;
        private const float top_margin = 20;
        private const float right_margin = 20;
        private const int max_visible_toasts = 5;

        private FillFlowContainer<ToastNotification> toastFlow = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;
            Anchor = Anchor.TopRight;
            Origin = Anchor.TopRight;

            InternalChild = toastFlow = new FillFlowContainer<ToastNotification>
            {
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, spacing),
                Padding = new MarginPadding { Top = top_margin, Right = right_margin }
            };
        }

        /// <summary>
        /// Shows a new toast notification.
        /// </summary>
        public void ShowToast(string title, string description, ToastType type = ToastType.Info, double? duration = null)
        {
            // Remove oldest if at max
            while (toastFlow.Count >= max_visible_toasts)
            {
                var oldest = toastFlow[0];
                oldest.Dismiss();
            }

            var toast = new ToastNotification
            {
                Title = title,
                Description = description,
                Type = type,
                DisplayDuration = duration ?? 4000,
                OnDismiss = () => RepositionToasts()
            };

            toastFlow.Add(toast);
        }

        /// <summary>
        /// Shows an info toast.
        /// </summary>
        public void Info(string title, string description) =>
            ShowToast(title, description, ToastType.Info);

        /// <summary>
        /// Shows a success toast.
        /// </summary>
        public void Success(string title, string description) =>
            ShowToast(title, description, ToastType.Success);

        /// <summary>
        /// Shows a warning toast.
        /// </summary>
        public void Warning(string title, string description) =>
            ShowToast(title, description, ToastType.Warning);

        /// <summary>
        /// Shows an error toast.
        /// </summary>
        public void Error(string title, string description) =>
            ShowToast(title, description, ToastType.Error);

        /// <summary>
        /// Dismisses all visible toasts.
        /// </summary>
        public void DismissAll()
        {
            foreach (var toast in toastFlow)
                toast.Dismiss();
        }

        private void RepositionToasts()
        {
            // The FillFlowContainer automatically repositions children when one is removed
        }
    }
}
