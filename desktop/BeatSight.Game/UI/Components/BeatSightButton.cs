using System;
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
        private BeatSightSpriteText textSprite = null!;
        private float fontSize = 12f;
        private Box hoverGlow = null!;
        private Box flash = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        public float FontSize
        {
            get => fontSize;
            set
            {
                fontSize = Math.Max(8f, value);

                if (textSprite != null)
                    textSprite.Font = BeatSightFont.Button(fontSize);
            }
        }

        /// <summary>Label colour; use <see cref="UITheme.TextOnAccent"/> on accent-filled buttons for contrast.</summary>
        public Color4 TextColour
        {
            get => textSprite?.Colour ?? Color4.White;
            set
            {
                if (textSprite != null)
                    textSprite.Colour = value;
            }
        }

        public BeatSightButton()
        {
            Masking = true;
            CornerRadius = default_corner_radius;
            MaskingSmoothness = 1.5f;

            // Default set here (not in load) so a colour given in an object initializer is kept. Setting it in
            // load used to repaint every button cyan, inverting toolbar hierarchy (inactive toggles looked primary).
            BackgroundColour = UITheme.AccentPrimary;
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

        protected override bool OnHover(HoverEvent e)
        {
            uiAudio.PlayHover(e.ScreenSpaceMousePosition.X / GetContainingInputManager().DrawSize.X);
            this.ScaleTo(UITheme.HoverScale, UITheme.MotionFast, UITheme.MotionEasing);
            hoverGlow.FadeTo(0.08f, UITheme.MotionFast, UITheme.MotionEasing);
            return base.OnHover(e);
        }

        protected override bool OnClick(ClickEvent e)
        {
            if (Enabled.Value)
            {
                uiAudio.PlayClick();
                flash.FadeTo(0.22f).FadeOut(UITheme.MotionSlow, UITheme.MotionEasing);
            }
            return base.OnClick(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            this.ScaleTo(1f, UITheme.MotionNormal, UITheme.MotionEasing);
            hoverGlow.FadeOut(200);
            base.OnHoverLost(e);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            this.ScaleTo(UITheme.PressScale, 60, UITheme.MotionEasing);
            return base.OnMouseDown(e);
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            this.ScaleTo(IsHovered ? UITheme.HoverScale : 1f, UITheme.MotionNormal, UITheme.MotionEasing);
            base.OnMouseUp(e);
        }

        protected override SpriteText CreateText() => textSprite = new BeatSightSpriteText
        {
            Depth = -1,
            Origin = Anchor.Centre,
            Anchor = Anchor.Centre,
            Font = BeatSightFont.Button(fontSize),
            UseFullGlyphHeight = false
        };
    }
}
