using osu.Framework.Extensions.ObjectExtensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.UserInterface;
using osuTK.Graphics;
using BeatSight.Game.UI.Theming;
using osu.Framework.Input.Events;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Input;
using osu.Framework.Graphics.Containers;

namespace BeatSight.Game.UI.Components
{
    public partial class BeatSightTextBox : BasicTextBox
    {
        private const float textbox_font_size = 24f;

        public BeatSightTextBox()
        {
            Masking = true;
            CornerRadius = 10;
            BackgroundUnfocused = UITheme.SurfaceAlt;
            BackgroundFocused = new Color4(50, 50, 70, 255);
            Placeholder.Colour = UITheme.TextMuted;
            TextFlow.Colour = UITheme.TextPrimary;

            BorderThickness = 2;
            BorderColour = UITheme.SurfaceAlt;

            FontSize = textbox_font_size;
            TextContainer.Height = 1f;
            TextContainer.Padding = new MarginPadding { Left = 12, Right = 12, Top = 2, Bottom = 2 };
        }

        protected override Drawable GetDrawableCharacter(char c)
        {
            var text = createTextSprite(c.ToString());

            // Manually align text to a fixed baseline to prevent vertical jumping between characters
            // of different heights (like 'o' vs 'h'), without enabling UseFullGlyphHeight.
            text.Anchor = Anchor.BottomLeft;
            text.Origin = Anchor.BottomLeft;

            float yOffset = -textbox_font_size * 0.25f; // Baseline offset estimate (25% from bottom)

            // Fix for descenders (g, j, p, q, y) being pushed up
            // Their bounding box bottom is the descender bottom, not the baseline.
            if ("gjpqy".IndexOf(c) != -1)
                yOffset += textbox_font_size * 0.15f; // Push down by estimated descender height

            text.Y = yOffset;

            return new Container
            {
                AutoSizeAxes = Axes.X,
                Height = textbox_font_size,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Child = text
            };
        }

        protected override SpriteText CreatePlaceholder() => createTextSprite(string.Empty, UITheme.TextMuted).With(p =>
        {
            p.Margin = new MarginPadding { Left = 10 };
        });

        private SpriteText createTextSprite(string text, Colour4? colour = null) => new SpriteText
        {
            Text = text,
            Font = BeatSightFont.Body(size: textbox_font_size),
            Colour = colour ?? UITheme.TextPrimary,
            Anchor = Anchor.CentreLeft,
            Origin = Anchor.CentreLeft,
            UseFullGlyphHeight = false,
            AllowMultiline = false,
            Spacing = new Vector2(0.1f, 0),
        };

        protected virtual Color4 FocusBorderColour => UITheme.AccentPrimary;

        protected override void OnFocus(FocusEvent e)
        {
            base.OnFocus(e);
            this.TransformTo(nameof(BorderColour), (ColourInfo)FocusBorderColour, 200, Easing.OutQuint);
        }

        protected override void OnFocusLost(FocusLostEvent e)
        {
            base.OnFocusLost(e);
            this.TransformTo(nameof(BorderColour), (ColourInfo)UITheme.SurfaceAlt, 200, Easing.OutQuint);
        }

        protected virtual bool AllowHoverEffect => true;

        protected override bool OnHover(HoverEvent e)
        {
            if (AllowHoverEffect && !HasFocus)
                this.TransformTo(nameof(BorderColour), (ColourInfo)UITheme.TextSecondary, 200, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            if (AllowHoverEffect && !HasFocus)
                this.TransformTo(nameof(BorderColour), (ColourInfo)UITheme.SurfaceAlt, 200, Easing.OutQuint);
            base.OnHoverLost(e);
        }
    }
}
