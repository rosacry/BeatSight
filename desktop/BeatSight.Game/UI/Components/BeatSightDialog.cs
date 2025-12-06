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
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A modern, animated dialog/modal component with various styles.
    /// Features backdrop blur effect, animated entry/exit, and customizable buttons.
    /// </summary>
    public partial class BeatSightDialog : VisibilityContainer
    {
        private const float default_width = 450f;
        private const float animation_duration = 300f;

        private Box backdrop = null!;
        private Container dialogContainer = null!;
        private Container contentContainer = null!;
        private FillFlowContainer buttonContainer = null!;

        private string title = "Dialog";
        private string? description;
        private IconUsage? icon;
        private DialogType dialogType = DialogType.Default;

        public string Title
        {
            get => title;
            set => title = value;
        }

        public string? Description
        {
            get => description;
            set => description = value;
        }

        public IconUsage? Icon
        {
            get => icon;
            set => icon = value;
        }

        public DialogType Type
        {
            get => dialogType;
            set => dialogType = value;
        }

        public event Action? OnConfirm;
        public event Action? OnCancel;

        /// <summary>
        /// Whether clicking the backdrop closes the dialog.
        /// </summary>
        public bool CloseOnBackdropClick { get; set; } = true;

        /// <summary>
        /// Whether pressing Escape closes the dialog.
        /// </summary>
        public bool CloseOnEscape { get; set; } = true;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;
            Alpha = 0;

            Children = new Drawable[]
            {
                // Backdrop
                backdrop = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black.Opacity(0.7f),
                },

                // Dialog container
                dialogContainer = new Container
                {
                    Width = default_width,
                    AutoSizeAxes = Axes.Y,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Masking = true,
                    CornerRadius = 16,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Shadow,
                        Colour = GetDialogColor().Opacity(0.3f),
                        Radius = 30,
                        Offset = new Vector2(0, 10),
                    },
                    Children = new Drawable[]
                    {
                        // Background
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(20, 22, 35, 255),
                        },

                        // Gradient overlay at top
                        new Box
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 120,
                            Colour = ColourInfo.GradientVertical(
                                GetDialogColor().Opacity(0.15f),
                                GetDialogColor().Opacity(0f)
                            ),
                        },

                        // Content
                        contentContainer = new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Padding = new MarginPadding(24),
                            Child = new FillFlowContainer
                            {
                                RelativeSizeAxes = Axes.X,
                                AutoSizeAxes = Axes.Y,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 16),
                                Children = new Drawable[]
                                {
                                    // Header with icon
                                    new FillFlowContainer
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        AutoSizeAxes = Axes.Y,
                                        Direction = FillDirection.Vertical,
                                        Spacing = new Vector2(0, 12),
                                        Children = new Drawable[]
                                        {
                                            // Icon
                                            CreateIconContainer(),

                                            // Title
                                            new SpriteText
                                            {
                                                Text = title,
                                                Font = new FontUsage("Torus", 24, "Bold"),
                                                Colour = Color4.White,
                                                Anchor = Anchor.TopCentre,
                                                Origin = Anchor.TopCentre,
                                            },

                                            // Description
                                            new TextFlowContainer(t =>
                                            {
                                                t.Font = new FontUsage("Torus", 14);
                                                t.Colour = new Color4(160, 170, 200, 255);
                                            })
                                            {
                                                RelativeSizeAxes = Axes.X,
                                                AutoSizeAxes = Axes.Y,
                                                Text = description ?? string.Empty,
                                                TextAnchor = Anchor.TopCentre,
                                                Alpha = string.IsNullOrEmpty(description) ? 0 : 1,
                                            },
                                        },
                                    },

                                    // Buttons
                                    buttonContainer = new FillFlowContainer
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        AutoSizeAxes = Axes.Y,
                                        Direction = FillDirection.Horizontal,
                                        Spacing = new Vector2(12, 0),
                                        Anchor = Anchor.TopCentre,
                                        Origin = Anchor.TopCentre,
                                        Margin = new MarginPadding { Top = 8 },
                                    },
                                },
                            },
                        },
                    },
                },
            };

            // Add default buttons based on dialog type
            AddDefaultButtons();
        }

        protected virtual Drawable CreateIconContainer()
        {
            var iconValue = icon ?? GetDefaultIcon();

            return new CircularContainer
            {
                Size = new Vector2(64),
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Masking = true,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = GetDialogColor().Opacity(0.4f),
                    Radius = 15,
                },
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = GetDialogColor().Opacity(0.2f),
                    },
                    new SpriteIcon
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Size = new Vector2(28),
                        Icon = iconValue,
                        Colour = GetDialogColor(),
                    },
                },
            };
        }

        protected virtual void AddDefaultButtons()
        {
            switch (dialogType)
            {
                case DialogType.Confirm:
                    AddButton("Cancel", DialogButtonStyle.Secondary, () =>
                    {
                        OnCancel?.Invoke();
                        Hide();
                    });
                    AddButton("Confirm", DialogButtonStyle.Primary, () =>
                    {
                        OnConfirm?.Invoke();
                        Hide();
                    });
                    break;

                case DialogType.Warning:
                    AddButton("Cancel", DialogButtonStyle.Secondary, () =>
                    {
                        OnCancel?.Invoke();
                        Hide();
                    });
                    AddButton("Continue", DialogButtonStyle.Warning, () =>
                    {
                        OnConfirm?.Invoke();
                        Hide();
                    });
                    break;

                case DialogType.Danger:
                    AddButton("Cancel", DialogButtonStyle.Secondary, () =>
                    {
                        OnCancel?.Invoke();
                        Hide();
                    });
                    AddButton("Delete", DialogButtonStyle.Danger, () =>
                    {
                        OnConfirm?.Invoke();
                        Hide();
                    });
                    break;

                case DialogType.Info:
                case DialogType.Success:
                    AddButton("Got it", DialogButtonStyle.Primary, () =>
                    {
                        OnConfirm?.Invoke();
                        Hide();
                    });
                    break;

                default:
                    AddButton("OK", DialogButtonStyle.Primary, () =>
                    {
                        OnConfirm?.Invoke();
                        Hide();
                    });
                    break;
            }
        }

        /// <summary>
        /// Add a custom button to the dialog.
        /// </summary>
        public void AddButton(string text, DialogButtonStyle style, Action? action = null)
        {
            buttonContainer.Add(new DialogButton(text, style)
            {
                Action = action,
            });
        }

        /// <summary>
        /// Clear all buttons from the dialog.
        /// </summary>
        public void ClearButtons()
        {
            buttonContainer.Clear();
        }

        protected Color4 GetDialogColor()
        {
            return dialogType switch
            {
                DialogType.Success => new Color4(34, 197, 94, 255),
                DialogType.Warning => new Color4(245, 158, 11, 255),
                DialogType.Danger => new Color4(239, 68, 68, 255),
                DialogType.Info => new Color4(59, 130, 246, 255),
                _ => new Color4(0, 212, 255, 255),
            };
        }

        protected IconUsage GetDefaultIcon()
        {
            return dialogType switch
            {
                DialogType.Success => FontAwesome.Solid.Check,
                DialogType.Warning => FontAwesome.Solid.ExclamationTriangle,
                DialogType.Danger => FontAwesome.Solid.Trash,
                DialogType.Info => FontAwesome.Solid.InfoCircle,
                DialogType.Confirm => FontAwesome.Solid.QuestionCircle,
                _ => FontAwesome.Solid.Comment,
            };
        }

        protected override void PopIn()
        {
            this.FadeIn(animation_duration, Easing.OutQuint);
            backdrop.FadeIn(animation_duration * 0.5f, Easing.OutQuint);
            dialogContainer.ScaleTo(0.9f).ScaleTo(1f, animation_duration, Easing.OutBack);
            dialogContainer.FadeIn(animation_duration, Easing.OutQuint);
        }

        protected override void PopOut()
        {
            this.FadeOut(animation_duration * 0.7f, Easing.OutQuint);
            backdrop.FadeOut(animation_duration * 0.7f, Easing.OutQuint);
            dialogContainer.ScaleTo(0.95f, animation_duration * 0.5f, Easing.OutQuint);
            dialogContainer.FadeOut(animation_duration * 0.5f, Easing.OutQuint);
        }

        protected override bool OnClick(ClickEvent e)
        {
            if (CloseOnBackdropClick && !dialogContainer.ReceivePositionalInputAt(e.ScreenSpaceMousePosition))
            {
                OnCancel?.Invoke();
                Hide();
                return true;
            }
            return base.OnClick(e);
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (CloseOnEscape && e.Key == Key.Escape)
            {
                OnCancel?.Invoke();
                Hide();
                return true;
            }
            return base.OnKeyDown(e);
        }

        /// <summary>
        /// A button within the dialog.
        /// </summary>
        private partial class DialogButton : Container
        {
            private readonly string text;
            private readonly DialogButtonStyle style;
            private Box hoverBox = null!;
            private Box backgroundBox = null!;

            public Action? Action;

            public DialogButton(string text, DialogButtonStyle style)
            {
                this.text = text;
                this.style = style;
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                AutoSizeAxes = Axes.X;
                Height = 40;
                Masking = true;
                CornerRadius = 8;

                var bgColor = GetBackgroundColor();
                var textColor = GetTextColor();

                Children = new Drawable[]
                {
                    backgroundBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = bgColor,
                    },
                    hoverBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White.Opacity(0f),
                    },
                    new Container
                    {
                        AutoSizeAxes = Axes.X,
                        RelativeSizeAxes = Axes.Y,
                        Padding = new MarginPadding { Horizontal = 24 },
                        Child = new SpriteText
                        {
                            Text = text,
                            Font = new FontUsage("Torus", 14, "SemiBold"),
                            Colour = textColor,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                        },
                    },
                };

                if (style == DialogButtonStyle.Primary || style == DialogButtonStyle.Danger || style == DialogButtonStyle.Warning)
                {
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Glow,
                        Colour = bgColor.Opacity(0.3f),
                        Radius = 8,
                    };
                }
            }

            private Color4 GetBackgroundColor()
            {
                return style switch
                {
                    DialogButtonStyle.Primary => new Color4(0, 212, 255, 255),
                    DialogButtonStyle.Secondary => new Color4(60, 65, 90, 255),
                    DialogButtonStyle.Danger => new Color4(239, 68, 68, 255),
                    DialogButtonStyle.Warning => new Color4(245, 158, 11, 255),
                    DialogButtonStyle.Success => new Color4(34, 197, 94, 255),
                    _ => new Color4(60, 65, 90, 255),
                };
            }

            private Color4 GetTextColor()
            {
                return style switch
                {
                    DialogButtonStyle.Secondary => new Color4(200, 210, 230, 255),
                    _ => Color4.White,
                };
            }

            protected override bool OnHover(HoverEvent e)
            {
                hoverBox.FadeColour(Color4.White.Opacity(0.1f), 150, Easing.OutQuint);
                this.ScaleTo(1.02f, 150, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                hoverBox.FadeColour(Color4.White.Opacity(0f), 150, Easing.OutQuint);
                this.ScaleTo(1f, 150, Easing.OutQuint);
                base.OnHoverLost(e);
            }

            protected override bool OnClick(ClickEvent e)
            {
                hoverBox.FlashColour(Color4.White.Opacity(0.3f), 200, Easing.OutQuint);
                Action?.Invoke();
                return base.OnClick(e);
            }
        }
    }

    public enum DialogType
    {
        Default,
        Confirm,
        Warning,
        Danger,
        Info,
        Success,
    }

    public enum DialogButtonStyle
    {
        Primary,
        Secondary,
        Danger,
        Warning,
        Success,
    }
}
