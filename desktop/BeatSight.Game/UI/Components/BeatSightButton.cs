using BeatSight.Game.UI.Theming;
using BeatSight.Game.Audio;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    public partial class BeatSightButton : BasicButton
    {
        private const float default_corner_radius = 10f;
        private Box hoverGlow = null!;
        private Box flash = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        public BeatSightButton()
        {
            Masking = true;
            CornerRadius = default_corner_radius;
            MaskingSmoothness = 1.5f;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            BackgroundColour = UITheme.AccentPrimary;

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

        protected override bool OnHover(HoverEvent e)
        {
            uiAudio.PlayHover(e.ScreenSpaceMousePosition.X / GetContainingInputManager().DrawSize.X);
            this.ScaleTo(1.05f, 400, Easing.OutElastic);
            hoverGlow.FadeTo(0.2f, 200, Easing.OutQuint);
            return base.OnHover(e);
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

        protected override void OnHoverLost(HoverLostEvent e)
        {
            this.ScaleTo(1f, 400, Easing.OutElastic);
            hoverGlow.FadeOut(200);
            base.OnHoverLost(e);
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

        protected override SpriteText CreateText() => new BeatSightSpriteText
        {
            Depth = -1,
            Origin = Anchor.Centre,
            Anchor = Anchor.Centre,
            Font = BeatSightFont.Button(),
            UseFullGlyphHeight = false
        };
    }
}
