using System;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Localisation;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    public partial class BeatSightCheckbox : Checkbox
    {
        private readonly Box fillBox;
        private readonly Container checkboxContainer;
        private readonly SpriteIcon checkIcon;
        private readonly SpriteText labelSpriteText;
        private readonly FillFlowContainer fillFlowContainer;
        private float labelFontSize = 12f;

        public Color4 CheckedColor { get; set; } = UITheme.AccentPrimary;
        public Color4 UncheckedColor { get; set; } = UITheme.Surface;
        public int FadeDuration { get; set; } = 80;

        public LocalisableString LabelText
        {
            get => labelSpriteText.Text;
            set => labelSpriteText.Text = value;
        }

        public float LabelSpacing
        {
            get => fillFlowContainer.Spacing.X;
            set => fillFlowContainer.Spacing = new Vector2(value, 0);
        }

        public float LabelFontSize
        {
            get => labelFontSize;
            set
            {
                labelFontSize = Math.Max(8f, value);
                labelSpriteText.Font = BeatSightFont.Body(labelFontSize);
            }
        }

        public bool RightHandedCheckbox
        {
            get => fillFlowContainer.GetLayoutPosition(labelSpriteText) < -0.5f;
            set => fillFlowContainer.SetLayoutPosition(labelSpriteText, value ? -1 : 1);
        }

        public BeatSightCheckbox()
        {
            AutoSizeAxes = Axes.Both;

            checkboxContainer = new Container
            {
                Size = new Vector2(20),
                Masking = true,
                CornerRadius = 4,
                // Unchecked boxes keep a light outline so they read as controls on any surface.
                BorderColour = UITheme.TextMuted,
                BorderThickness = 2,
                Children = new Drawable[]
                {
                    fillBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                    },
                    checkIcon = new SpriteIcon
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Size = new Vector2(11),
                        Icon = FontAwesome.Solid.Check,
                        Colour = UITheme.TextOnAccent,
                        Alpha = 0
                    }
                }
            };

            fillFlowContainer = new FillFlowContainer
            {
                Direction = FillDirection.Horizontal,
                AutoSizeAxes = Axes.Both,
                Spacing = new Vector2(8f, 0f),
                Children = new Drawable[]
                {
                    checkboxContainer,
                    labelSpriteText = new BeatSightSpriteText
                    {
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Depth = float.MinValue,
                        Font = BeatSightFont.Body(labelFontSize),
                        Colour = UITheme.TextPrimary
                    }
                }
            };

            Child = fillFlowContainer;

            Current.BindValueChanged(onCurrentChanged, true);
        }

        private void onCurrentChanged(ValueChangedEvent<bool> state)
        {
            fillBox.FadeColour(state.NewValue ? CheckedColor : UncheckedColor, FadeDuration);
            checkIcon.FadeTo(state.NewValue ? 1 : 0, FadeDuration);
            checkboxContainer.BorderColour = state.NewValue ? CheckedColor : UITheme.TextMuted;
        }
    }
}
