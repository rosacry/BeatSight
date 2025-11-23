using BeatSight.Game.UI.Theming;
using BeatSight.Game.Audio;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Consistent back button styling used across BeatSight screens.
    /// </summary>
    public partial class BackButton : BasicButton
    {
        private static readonly Color4 idleColour = new Color4(58, 70, 112, 255);
        private static readonly Color4 hoverColour = new Color4(98, 140, 220, 255);

        public static readonly MarginPadding DefaultMargin = new MarginPadding { Left = 24, Top = 24 };

        private Box hoverGlow = null!;
        private Box flash = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        public BackButton()
        {
            Width = 120;
            Height = 44;
            CornerRadius = 10;
            Masking = true;
            Anchor = Anchor.TopLeft;
            Origin = Anchor.TopLeft;
            BackgroundColour = idleColour;
            Text = "Back";
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            Add(hoverGlow = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = Color4.White,
                Alpha = 0,
                Blending = BlendingParameters.Additive
            });

            Add(flash = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = Color4.White,
                Alpha = 0,
                Blending = BlendingParameters.Additive
            });
        }

        protected override SpriteText CreateText() => new BeatSightSpriteText
        {
            Depth = -1,
            Origin = Anchor.Centre,
            Anchor = Anchor.Centre,
            Font = BeatSightFont.Button(20f),
            UseFullGlyphHeight = false
        };

        protected override bool OnHover(HoverEvent e)
        {
            BackgroundColour = hoverColour;
            uiAudio.PlayHover(e.ScreenSpaceMousePosition.X / GetContainingInputManager().DrawSize.X);
            this.ScaleTo(1.05f, 400, Easing.OutElastic);
            hoverGlow.FadeTo(0.2f, 200, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            BackgroundColour = idleColour;
            this.ScaleTo(1f, 400, Easing.OutElastic);
            hoverGlow.FadeOut(200);
            base.OnHoverLost(e);
        }

        protected override bool OnClick(ClickEvent e)
        {
            if (Enabled.Value)
            {
                uiAudio.PlayClick();
                flash.FadeTo(0.5f).FadeOut(500, Easing.OutQuint);
            }
            return base.OnClick(e);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            this.ScaleTo(0.95f, 50, Easing.OutQuint);
            return base.OnMouseDown(e);
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            this.ScaleTo(IsHovered ? 1.05f : 1f, 800, Easing.OutElastic);
            base.OnMouseUp(e);
        }
    }
}
