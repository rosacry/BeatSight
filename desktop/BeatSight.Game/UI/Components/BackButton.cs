using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
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
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            BackgroundColour = idleColour;
            base.OnHoverLost(e);
        }
    }
}
