using BeatSight.Game.UI.Theming;
using BeatSight.Game.Audio;
using System;
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
        private static readonly Color4 idleColour = UITheme.SurfaceAlt;
        private static readonly Color4 hoverColour = UITheme.SurfaceRaised;
        private const float designWidth = 120f;
        private const float designHeight = 44f;

        public static readonly MarginPadding DefaultMargin = new MarginPadding { Left = 24, Top = 24 };

        private BeatSightSpriteText labelSprite = null!;
        private Box hoverGlow = null!;
        private Box flash = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        public BackButton()
        {
            Width = designWidth;
            Height = designHeight;
            CornerRadius = 10;
            Masking = true;
            Anchor = Anchor.TopLeft;
            Origin = Anchor.TopLeft;
            BackgroundColour = idleColour;
            BorderThickness = 1;
            BorderColour = UITheme.Border;
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

        protected override SpriteText CreateText() => labelSprite = new BeatSightSpriteText
        {
            Depth = -1,
            Origin = Anchor.Centre,
            Anchor = Anchor.Centre,
            Font = BeatSightFont.Button(20f),
            UseFullGlyphHeight = false
        };

        protected override void LoadComplete()
        {
            base.LoadComplete();
            applyResponsiveSize(force: true);
        }

        protected override void Update()
        {
            base.Update();
            applyResponsiveSize();
        }

        protected override bool OnHover(HoverEvent e)
        {
            BackgroundColour = hoverColour;
            uiAudio.PlayHover(e.ScreenSpaceMousePosition.X / GetContainingInputManager().DrawSize.X);
            this.ScaleTo(UITheme.HoverScale, UITheme.MotionFast, UITheme.MotionEasing);
            hoverGlow.FadeTo(0.08f, UITheme.MotionFast, UITheme.MotionEasing);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            BackgroundColour = idleColour;
            this.ScaleTo(1f, UITheme.MotionNormal, UITheme.MotionEasing);
            hoverGlow.FadeOut(200);
            base.OnHoverLost(e);
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

        private void applyResponsiveSize(bool force = false)
        {
            if (Parent == null)
                return;

            float targetHeight = ResponsiveLayout.ClampFraction(Parent.DrawHeight, 0.05f, 38f, 58f);
            float targetWidth = Math.Clamp(targetHeight * 2.72f, 106f, 156f);
            float cornerRadius = Math.Clamp(targetHeight * 0.24f, 8f, 14f);
            float labelSize = Math.Clamp(targetHeight * 0.44f, 16f, 23f);

            if (force || Math.Abs(Height - targetHeight) > 0.1f)
                Height = targetHeight;

            if (force || Math.Abs(Width - targetWidth) > 0.1f)
                Width = targetWidth;

            if (force || Math.Abs(CornerRadius - cornerRadius) > 0.1f)
                CornerRadius = cornerRadius;

            if (labelSprite != null)
                labelSprite.Font = BeatSightFont.Button(labelSize);
        }
    }
}
