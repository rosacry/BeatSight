using System;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Overlays
{
    /// <summary>
    /// A modal confirmation dialog for destructive actions.
    /// </summary>
    public partial class ConfirmationDialog : VisibilityContainer
    {
        private readonly string title;
        private readonly string message;
        private readonly string confirmText;
        private readonly string cancelText;
        private readonly Action? onConfirm;
        private readonly Action? onCancel;
        private readonly bool isDangerous;

        private Container content = null!;

        /// <summary>
        /// Creates a new confirmation dialog.
        /// </summary>
        /// <param name="title">The dialog title.</param>
        /// <param name="message">The message to display.</param>
        /// <param name="confirmText">Text for the confirm button (default: "Confirm").</param>
        /// <param name="cancelText">Text for the cancel button (default: "Cancel").</param>
        /// <param name="onConfirm">Action to execute when confirmed.</param>
        /// <param name="onCancel">Action to execute when cancelled.</param>
        /// <param name="isDangerous">If true, styles the confirm button as dangerous (red).</param>
        public ConfirmationDialog(
            string title,
            string message,
            string confirmText = "Confirm",
            string cancelText = "Cancel",
            Action? onConfirm = null,
            Action? onCancel = null,
            bool isDangerous = false)
        {
            this.title = title;
            this.message = message;
            this.confirmText = confirmText;
            this.cancelText = cancelText;
            this.onConfirm = onConfirm;
            this.onCancel = onCancel;
            this.isDangerous = isDangerous;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            Children = new Drawable[]
            {
                // Dimmed background
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(0, 0, 0, 0.7f),
                },
                // Dialog content
                content = new Container
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    AutoSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 12,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = UITheme.Surface,
                        },
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Padding = new MarginPadding(30),
                            Spacing = new Vector2(0, 20),
                            Children = new Drawable[]
                            {
                                // Title
                                new BeatSightSpriteText
                                {
                                    Text = title,
                                    Font = BeatSightFont.Title(24),
                                    Colour = isDangerous ? UITheme.AccentWarning : UITheme.TextPrimary,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                // Message
                                new BeatSightSpriteText
                                {
                                    Text = message,
                                    Font = BeatSightFont.Body(16),
                                    Colour = UITheme.TextSecondary,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    MaxWidth = DesignSystem.DialogMaxWidth,
                                },
                                // Buttons
                                new FillFlowContainer
                                {
                                    AutoSizeAxes = Axes.Both,
                                    Direction = FillDirection.Horizontal,
                                    Spacing = new Vector2(15, 0),
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Children = new Drawable[]
                                    {
                                        new DialogButton(cancelText, UITheme.SurfaceAlt)
                                        {
                                            Action = () =>
                                            {
                                                onCancel?.Invoke();
                                                Hide();
                                            }
                                        },
                                        new DialogButton(confirmText, isDangerous ? UITheme.AccentError : UITheme.AccentPrimary)
                                        {
                                            Action = () =>
                                            {
                                                onConfirm?.Invoke();
                                                Hide();
                                            }
                                        },
                                    }
                                }
                            }
                        }
                    }
                }
            };
        }

        protected override void PopIn()
        {
            this.FadeIn(200, Easing.OutQuint);
            content.ScaleTo(0.9f).ScaleTo(1f, 300, Easing.OutElastic);
        }

        protected override void PopOut()
        {
            this.FadeOut(150, Easing.OutQuint);
            content.ScaleTo(0.9f, 150, Easing.OutQuint);
        }

        protected override bool OnClick(ClickEvent e)
        {
            // Close when clicking outside the dialog
            if (!content.ReceivePositionalInputAt(e.ScreenSpaceMousePosition))
            {
                onCancel?.Invoke();
                Hide();
                return true;
            }

            return base.OnClick(e);
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
                onCancel?.Invoke();
                Hide();
                return true;
            }

            if (e.Key == osuTK.Input.Key.Enter)
            {
                onConfirm?.Invoke();
                Hide();
                return true;
            }

            return base.OnKeyDown(e);
        }

        /// <summary>
        /// Simple dialog button.
        /// </summary>
        private partial class DialogButton : BeatSightButton
        {
            public DialogButton(string text, Color4 colour)
            {
                Text = text;
                Size = new Vector2(120, DesignSystem.ButtonHeight);
                BackgroundColour = colour;
            }

            protected override SpriteText CreateText()
            {
                return new BeatSightSpriteText
                {
                    Depth = -1,
                    Origin = Anchor.Centre,
                    Anchor = Anchor.Centre,
                    Font = BeatSightFont.Button(16f),
                    UseFullGlyphHeight = false,
                    Colour = Color4.White,
                };
            }
        }
    }
}
