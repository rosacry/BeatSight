// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Button style variants for AnimatedIconButton.
    /// </summary>
    public enum IconButtonStyle
    {
        /// <summary>
        /// Circular button with solid background.
        /// </summary>
        Circular,

        /// <summary>
        /// Rounded square button.
        /// </summary>
        Rounded,

        /// <summary>
        /// Transparent button with only icon visible.
        /// </summary>
        Transparent,

        /// <summary>
        /// Outlined button with border.
        /// </summary>
        Outlined,

        /// <summary>
        /// Pill-shaped button for icon + text.
        /// </summary>
        Pill
    }

    /// <summary>
    /// A highly customizable icon button with smooth animations, glow effects,
    /// and multiple style variants. Inspired by osu!'s animated buttons.
    /// </summary>
    public partial class AnimatedIconButton : CompositeDrawable
    {
        private const float default_size = 40;
        private const float corner_radius = 8;
        private const double hover_duration = 200;
        private const double click_duration = 150;

        #region Properties

        /// <summary>
        /// The icon to display.
        /// </summary>
        public IconUsage Icon
        {
            get => icon;
            set
            {
                icon = value;
                if (iconSprite != null)
                    iconSprite.Icon = value;
            }
        }

        /// <summary>
        /// Optional label text (only shown in Pill style).
        /// </summary>
        public string Label
        {
            get => label;
            set
            {
                label = value;
                if (labelText != null)
                    labelText.Text = value;
            }
        }

        /// <summary>
        /// The style variant of the button.
        /// </summary>
        public IconButtonStyle Style { get; init; } = IconButtonStyle.Circular;

        /// <summary>
        /// Primary accent color.
        /// </summary>
        public Color4 AccentColour { get; init; } = Color4Extensions.FromHex("00d4ff");

        /// <summary>
        /// Background color (for solid styles).
        /// </summary>
        public Color4 BackgroundColour { get; init; } = Color4Extensions.FromHex("1a1a2e");

        /// <summary>
        /// Icon color.
        /// </summary>
        public Color4 IconColour { get; init; } = Color4.White;

        /// <summary>
        /// Size of the icon relative to button size.
        /// </summary>
        public float IconScale { get; init; } = 0.5f;

        /// <summary>
        /// Whether to show glow effect on hover.
        /// </summary>
        public bool EnableGlow { get; init; } = true;

        /// <summary>
        /// Whether the button spins on click.
        /// </summary>
        public bool SpinOnClick { get; init; }

        /// <summary>
        /// Whether the button pulses continuously.
        /// </summary>
        public bool PulseEnabled { get; init; }

        /// <summary>
        /// Whether the button is enabled.
        /// </summary>
        public bool Enabled
        {
            get => enabled;
            set
            {
                enabled = value;
                UpdateEnabledState();
            }
        }

        /// <summary>
        /// Click action.
        /// </summary>
        public Action? Action { get; set; }

        /// <summary>
        /// Tooltip text shown on hover.
        /// </summary>
        public string TooltipText { get; init; } = "";

        #endregion

        private IconUsage icon = FontAwesome.Solid.Play;
        private string label = "";
        private bool enabled = true;

        private Container backgroundContainer = null!;
        private Box backgroundBox = null!;
        private Box borderBox = null!;
        private Container contentContainer = null!;
        private SpriteIcon iconSprite = null!;
        private SpriteText labelText = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = Style == IconButtonStyle.Pill
                ? new Vector2(default_size * 2.5f, default_size)
                : new Vector2(default_size);

            InternalChild = backgroundContainer = CreateBackground();
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (PulseEnabled)
                StartPulse();
        }

        private Container CreateBackground()
        {
            float radius = Style switch
            {
                IconButtonStyle.Circular => default_size / 2,
                IconButtonStyle.Rounded => corner_radius,
                IconButtonStyle.Pill => default_size / 2,
                _ => corner_radius
            };

            var container = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = radius,
                Children = new Drawable[]
                {
                    // Background
                    backgroundBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = GetBackgroundColour()
                    },

                    // Border (for outlined style)
                    borderBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Style == IconButtonStyle.Outlined ? AccentColour : Color4.Transparent,
                        Alpha = Style == IconButtonStyle.Outlined ? 1 : 0
                    },

                    // Content
                    contentContainer = CreateContent()
                }
            };

            // Add edge effect for glow-capable styles
            if (EnableGlow && Style != IconButtonStyle.Transparent)
            {
                container.EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = AccentColour.Opacity(0),
                    Radius = 15
                };
            }

            return container;
        }

        private Container CreateContent()
        {
            if (Style == IconButtonStyle.Pill && !string.IsNullOrEmpty(Label))
            {
                return new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Child = new FillFlowContainer
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(8, 0),
                        Children = new Drawable[]
                        {
                            iconSprite = new SpriteIcon
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Size = new Vector2(default_size * IconScale),
                                Icon = Icon,
                                Colour = IconColour
                            },
                            labelText = new SpriteText
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Text = Label,
                                Font = new FontUsage("Nunito", size: 14, weight: "SemiBold"),
                                Colour = IconColour
                            }
                        }
                    }
                };
            }

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Child = iconSprite = new SpriteIcon
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Size = new Vector2(default_size * IconScale),
                    Icon = Icon,
                    Colour = IconColour
                }
            };
        }

        private Color4 GetBackgroundColour() => Style switch
        {
            IconButtonStyle.Transparent => Color4.Transparent,
            IconButtonStyle.Outlined => Color4.Transparent,
            _ => BackgroundColour
        };

        protected override bool OnHover(HoverEvent e)
        {
            if (!enabled) return false;

            // Scale up
            backgroundContainer.ScaleTo(1.1f, hover_duration, Easing.OutQuint);

            // Brighten background
            backgroundBox.FadeColour(
                Style == IconButtonStyle.Transparent
                    ? AccentColour.Opacity(0.1f)
                    : BackgroundColour.Lighten(0.2f),
                hover_duration);

            // Show glow
            if (EnableGlow && Style != IconButtonStyle.Transparent)
            {
                backgroundContainer.TweenEdgeEffectTo(new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = AccentColour.Opacity(0.4f),
                    Radius = 20
                }, hover_duration, Easing.OutQuint);
            }

            // Icon animation
            iconSprite.FadeColour(AccentColour, hover_duration);
            iconSprite.ScaleTo(1.1f, hover_duration, Easing.OutQuint);

            // Label animation (Pill style)
            labelText?.FadeColour(AccentColour, hover_duration);

            return true;
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            if (!enabled) return;

            backgroundContainer.ScaleTo(1f, hover_duration, Easing.OutQuint);
            backgroundBox.FadeColour(GetBackgroundColour(), hover_duration);

            if (EnableGlow && Style != IconButtonStyle.Transparent)
            {
                backgroundContainer.TweenEdgeEffectTo(new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = AccentColour.Opacity(0),
                    Radius = 15
                }, hover_duration, Easing.OutQuint);
            }

            iconSprite.FadeColour(IconColour, hover_duration);
            iconSprite.ScaleTo(1f, hover_duration, Easing.OutQuint);
            labelText?.FadeColour(IconColour, hover_duration);
        }

        protected override bool OnClick(ClickEvent e)
        {
            if (!enabled) return false;

            // Click animation
            backgroundContainer.ScaleTo(0.9f, click_duration / 2, Easing.OutQuint)
                .Then()
                .ScaleTo(1.1f, click_duration, Easing.OutQuint);

            // Flash effect
            backgroundBox.FlashColour(AccentColour, 200);

            // Spin if enabled
            if (SpinOnClick)
            {
                iconSprite.RotateTo(360, 400, Easing.OutQuint)
                    .Then()
                    .RotateTo(0);
            }

            Action?.Invoke();
            return true;
        }

        private void UpdateEnabledState()
        {
            this.FadeTo(enabled ? 1f : 0.5f, 200);
        }

        /// <summary>
        /// Starts a continuous pulse animation.
        /// </summary>
        public void StartPulse()
        {
            backgroundContainer.ScaleTo(1.05f, 800, Easing.InOutSine)
                .Then()
                .ScaleTo(1f, 800, Easing.InOutSine)
                .Loop();

            if (EnableGlow)
            {
                // Use a simple approach - alternate glow with Scheduler
                Scheduler.AddDelayed(() =>
                {
                    backgroundContainer.TweenEdgeEffectTo(new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Glow,
                        Colour = AccentColour.Opacity(0.3f),
                        Radius = 25
                    }, 800, Easing.InOutSine);

                    Scheduler.AddDelayed(() =>
                    {
                        backgroundContainer.TweenEdgeEffectTo(new EdgeEffectParameters
                        {
                            Type = EdgeEffectType.Glow,
                            Colour = AccentColour.Opacity(0.1f),
                            Radius = 15
                        }, 800, Easing.InOutSine);
                    }, 800);
                }, 0, true);
            }
        }

        /// <summary>
        /// Stops the pulse animation.
        /// </summary>
        public void StopPulse()
        {
            backgroundContainer.ClearTransforms();
            backgroundContainer.ScaleTo(1f, 200, Easing.OutQuint);
        }

        /// <summary>
        /// Flashes the button to draw attention.
        /// </summary>
        public void Flash()
        {
            backgroundBox.FlashColour(AccentColour, 400);
            iconSprite.ScaleTo(1.3f, 100, Easing.OutQuint)
                .Then()
                .ScaleTo(1f, 300, Easing.OutQuint);
        }
    }

    /// <summary>
    /// A toggle button that switches between two states with visual feedback.
    /// </summary>
    public partial class AnimatedToggleButton : AnimatedIconButton
    {
        /// <summary>
        /// Icon shown when toggled on.
        /// </summary>
        public IconUsage IconOn { get; init; } = FontAwesome.Solid.ToggleOn;

        /// <summary>
        /// Icon shown when toggled off.
        /// </summary>
        public IconUsage IconOff { get; init; } = FontAwesome.Solid.ToggleOff;

        /// <summary>
        /// Color when toggled on.
        /// </summary>
        public Color4 OnColour { get; init; } = Color4Extensions.FromHex("00ff88");

        /// <summary>
        /// Color when toggled off.
        /// </summary>
        public Color4 OffColour { get; init; } = Color4.White.Opacity(0.5f);

        /// <summary>
        /// Whether the toggle is currently on.
        /// </summary>
        public bool IsOn
        {
            get => isOn;
            set
            {
                isOn = value;
                UpdateToggleState();
            }
        }

        /// <summary>
        /// Action called when toggle state changes.
        /// </summary>
        public new Action<bool>? Action { get; set; }

        private bool isOn;

        [BackgroundDependencyLoader]
        private void load()
        {
            base.Action = () =>
            {
                IsOn = !IsOn;
                Action?.Invoke(IsOn);
            };

            UpdateToggleState();
        }

        private void UpdateToggleState()
        {
            Icon = IsOn ? IconOn : IconOff;
            // Note: Additional color animations would go here
        }
    }

    /// <summary>
    /// A play/pause button that toggles between states.
    /// </summary>
    public partial class PlayPauseButton : AnimatedToggleButton
    {
        public PlayPauseButton()
        {
            IconOn = FontAwesome.Solid.Pause;
            IconOff = FontAwesome.Solid.Play;
            OnColour = Color4Extensions.FromHex("00d4ff");
        }

        /// <summary>
        /// Whether playback is active (showing pause icon).
        /// </summary>
        public bool IsPlaying
        {
            get => IsOn;
            set => IsOn = value;
        }
    }

    /// <summary>
    /// A favorite/like button with heart icon.
    /// </summary>
    public partial class FavoriteButton : AnimatedToggleButton
    {
        public FavoriteButton()
        {
            IconOn = FontAwesome.Solid.Heart;
            IconOff = FontAwesome.Regular.Heart;
            OnColour = Color4Extensions.FromHex("ff4466");
            Style = IconButtonStyle.Transparent;
        }

        /// <summary>
        /// Whether the item is favorited.
        /// </summary>
        public bool IsFavorite
        {
            get => IsOn;
            set => IsOn = value;
        }
    }

    /// <summary>
    /// A mute/unmute button for audio control.
    /// </summary>
    public partial class MuteButton : AnimatedToggleButton
    {
        public MuteButton()
        {
            IconOn = FontAwesome.Solid.VolumeMute;
            IconOff = FontAwesome.Solid.VolumeUp;
            OnColour = Color4Extensions.FromHex("ff4466");
            OffColour = Color4.White;
            Style = IconButtonStyle.Transparent;
        }

        /// <summary>
        /// Whether audio is muted.
        /// </summary>
        public bool IsMuted
        {
            get => IsOn;
            set => IsOn = value;
        }
    }
}
