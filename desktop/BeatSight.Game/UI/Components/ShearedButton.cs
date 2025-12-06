using System;
using BeatSight.Game.Audio;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osu.Framework.Localisation;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A modern sheared button inspired by osu!'s UI design language.
    /// Features parallelogram shape, gradient borders, glow effects, and fluid animations.
    /// </summary>
    public partial class ShearedButton : CompositeDrawable
    {
        public const float DEFAULT_HEIGHT = 50f;
        public const float CORNER_RADIUS = 7f;
        public const float BORDER_THICKNESS = 2f;

        /// <summary>
        /// Standard shear value for consistent UI styling across the application.
        /// </summary>
        public static readonly Vector2 SHEAR = new Vector2(0.15f, 0);

        private readonly Container content;
        private readonly Container backgroundLayer;
        private readonly Box background;
        private readonly Box flashLayer;
        private readonly Box glowLayer;
        private readonly BeatSightSpriteText text;
        private readonly Container iconContainer;

        private Color4 darkerColour;
        private Color4 lighterColour;
        private Color4 textColour = Color4.White;
        private Color4 glowColour;
        private bool isPressed;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        public LocalisableString Text
        {
            get => text.Text;
            set => text.Text = value;
        }

        public float TextSize
        {
            get => text.Font.Size;
            set => text.Font = BeatSightFont.Button(value);
        }

        public Color4 DarkerColour
        {
            get => darkerColour;
            set
            {
                darkerColour = value;
                glowColour = value;
                Schedule(updateState);
            }
        }

        public Color4 LighterColour
        {
            get => lighterColour;
            set
            {
                lighterColour = value;
                Schedule(updateState);
            }
        }

        public Color4 TextColour
        {
            get => textColour;
            set
            {
                textColour = value;
                Schedule(updateState);
            }
        }

        public IconUsage? Icon
        {
            set
            {
                iconContainer.Clear();
                if (value != null)
                {
                    iconContainer.Add(new SpriteIcon
                    {
                        Icon = value.Value,
                        Size = new Vector2(20),
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Colour = textColour
                    });
                }
            }
        }

        public Action? Action { get; set; }

        public bool Enabled { get; set; } = true;

        /// <summary>
        /// Creates a new ShearedButton.
        /// </summary>
        /// <param name="width">Fixed width, or null for auto-size.</param>
        /// <param name="height">Button height.</param>
        public ShearedButton(float? width = null, float height = DEFAULT_HEIGHT)
        {
            Height = height;
            Shear = SHEAR;

            // Default colors
            darkerColour = DesignSystem.ColorAccentPrimary.Darken(0.3f);
            lighterColour = DesignSystem.ColorAccentPrimary;
            glowColour = DesignSystem.ColorAccentPrimary;

            InternalChild = content = new Container
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    backgroundLayer = new Container
                    {
                        RelativeSizeAxes = Axes.Y,
                        CornerRadius = CORNER_RADIUS,
                        Masking = true,
                        BorderThickness = BORDER_THICKNESS,
                        EdgeEffect = new EdgeEffectParameters
                        {
                            Type = EdgeEffectType.Glow,
                            Colour = Color4.Transparent,
                            Radius = 15,
                            Roundness = CORNER_RADIUS
                        },
                        Children = new Drawable[]
                        {
                            background = new Box
                            {
                                RelativeSizeAxes = Axes.Both
                            },
                            glowLayer = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = Color4.White,
                                Alpha = 0,
                                Blending = BlendingParameters.Additive
                            },
                            new Container
                            {
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                                AutoSizeAxes = Axes.Both,
                                Shear = -SHEAR, // Counter-shear for content
                                Children = new Drawable[]
                                {
                                    iconContainer = new Container
                                    {
                                        Anchor = Anchor.CentreLeft,
                                        Origin = Anchor.CentreLeft,
                                        AutoSizeAxes = Axes.Both,
                                        Margin = new MarginPadding { Right = 8 }
                                    },
                                    text = new BeatSightSpriteText
                                    {
                                        Font = BeatSightFont.Button(17),
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                    }
                                }
                            },
                            flashLayer = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = Color4.White,
                                Alpha = 0,
                                Blending = BlendingParameters.Additive
                            }
                        }
                    }
                }
            };

            if (width != null)
            {
                Width = width.Value;
                backgroundLayer.RelativeSizeAxes = Axes.Both;
            }
            else
            {
                AutoSizeAxes = Axes.X;
                backgroundLayer.AutoSizeAxes = Axes.X;
                text.Margin = new MarginPadding { Horizontal = 20 };
            }
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            updateState();
            FinishTransforms(true);
        }

        private void updateState()
        {
            var colourDark = darkerColour;
            var colourLight = lighterColour;
            var colourText = textColour;

            if (!Enabled)
            {
                colourDark = colourDark.Darken(0.6f);
                colourLight = colourLight.Darken(0.6f);
                colourText = colourText.Opacity(0.5f);
            }
            else if (IsHovered)
            {
                colourDark = colourDark.Lighten(0.15f);
                colourLight = colourLight.Lighten(0.15f);
            }

            background.FadeColour(colourDark, 150, Easing.OutQuint);
            backgroundLayer.TransformTo(nameof(backgroundLayer.BorderColour),
                ColourInfo.GradientVertical(colourLight, colourDark), 150, Easing.OutQuint);
            text.FadeColour(colourText, 150, Easing.OutQuint);

            // Update icons
            foreach (var drawable in iconContainer)
            {
                if (drawable is SpriteIcon icon)
                    icon.FadeColour(colourText, 150, Easing.OutQuint);
            }
        }

        protected override bool OnHover(HoverEvent e)
        {
            if (!Enabled) return false;

            uiAudio?.PlayHover(e.ScreenSpaceMousePosition.X / (GetContainingInputManager()?.DrawSize.X ?? 1));

            Schedule(updateState);

            // Glow effect
            backgroundLayer.TweenEdgeEffectTo(new EdgeEffectParameters
            {
                Type = EdgeEffectType.Glow,
                Colour = glowColour.Opacity(0.4f),
                Radius = 20,
                Roundness = CORNER_RADIUS
            }, 200, Easing.OutQuint);

            glowLayer.FadeTo(0.1f, 200, Easing.OutQuint);

            return true;
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            Schedule(updateState);

            backgroundLayer.TweenEdgeEffectTo(new EdgeEffectParameters
            {
                Type = EdgeEffectType.Glow,
                Colour = Color4.Transparent,
                Radius = 15,
                Roundness = CORNER_RADIUS
            }, 400, Easing.OutQuint);

            glowLayer.FadeOut(400, Easing.OutQuint);

            base.OnHoverLost(e);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            if (!Enabled) return false;

            isPressed = true;
            content.ScaleTo(0.92f, 2000, Easing.OutQuint);
            return true;
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            isPressed = false;
            content.ScaleTo(1f, 800, Easing.OutElastic);
            base.OnMouseUp(e);
        }

        protected override bool OnClick(ClickEvent e)
        {
            if (!Enabled) return false;

            uiAudio?.PlayClick();
            flashLayer.FadeOutFromOne(600, Easing.OutQuint);

            // Ripple effect
            backgroundLayer.FlashColour(Color4.White, 200, Easing.OutQuint);

            Action?.Invoke();
            return true;
        }
    }

    /// <summary>
    /// Extension methods for color manipulation.
    /// </summary>
    public static class ColorExtensions
    {
        public static Color4 Darken(this Color4 colour, float amount)
        {
            float factor = 1f - Math.Clamp(amount, 0f, 1f);
            return new Color4(
                colour.R * factor,
                colour.G * factor,
                colour.B * factor,
                colour.A
            );
        }

        public static Color4 Lighten(this Color4 colour, float amount)
        {
            amount = Math.Clamp(amount, 0f, 1f);
            return new Color4(
                colour.R + (1f - colour.R) * amount,
                colour.G + (1f - colour.G) * amount,
                colour.B + (1f - colour.B) * amount,
                colour.A
            );
        }
    }
}
