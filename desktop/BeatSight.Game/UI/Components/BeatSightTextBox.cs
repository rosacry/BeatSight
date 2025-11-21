using osu.Framework.Graphics;
using osu.Framework.Graphics.UserInterface;
using osuTK.Graphics;
using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.UI.Components
{
    public partial class BeatSightTextBox : BasicTextBox
    {
        public BeatSightTextBox()
        {
            Masking = true;
            CornerRadius = 8;
            BackgroundUnfocused = UITheme.Surface;
            BackgroundFocused = UITheme.Surface;
            Placeholder.Colour = UITheme.TextMuted;
            TextFlow.Colour = UITheme.TextPrimary;
        }
    }
}
