using osu.Framework.Graphics;
using osu.Framework.Graphics.UserInterface;
using osuTK.Graphics;
using BeatSight.Game.UI.Theming;
using osu.Framework.Input.Events;
using osu.Framework.Graphics.Colour;

namespace BeatSight.Game.UI.Components
{
    public partial class BeatSightTextBox : BasicTextBox
    {
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
        }

        protected override void OnFocus(FocusEvent e)
        {
            base.OnFocus(e);
            this.TransformTo(nameof(BorderColour), (ColourInfo)UITheme.AccentPrimary, 200, Easing.OutQuint);
        }

        protected override void OnFocusLost(FocusLostEvent e)
        {
            base.OnFocusLost(e);
            this.TransformTo(nameof(BorderColour), (ColourInfo)UITheme.SurfaceAlt, 200, Easing.OutQuint);
        }

        protected override bool OnHover(HoverEvent e)
        {
            if (!HasFocus)
                this.TransformTo(nameof(BorderColour), (ColourInfo)UITheme.TextSecondary, 200, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            if (!HasFocus)
                this.TransformTo(nameof(BorderColour), (ColourInfo)UITheme.SurfaceAlt, 200, Easing.OutQuint);
            base.OnHoverLost(e);
        }
    }
}
