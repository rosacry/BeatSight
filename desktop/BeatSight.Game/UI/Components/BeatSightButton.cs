using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;

namespace BeatSight.Game.UI.Components
{
    public partial class BeatSightButton : BasicButton
    {
        private const float default_corner_radius = 8f;

        public BeatSightButton()
        {
            Masking = true;
            CornerRadius = default_corner_radius;
            MaskingSmoothness = 1.5f;
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
