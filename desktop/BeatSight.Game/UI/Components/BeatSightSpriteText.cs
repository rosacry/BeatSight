using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Sprites;
using osuTK;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Shared sprite text with gentle spacing and subtle shadow to soften typography.
    /// </summary>
    public partial class BeatSightSpriteText : SpriteText
    {
        private static readonly Vector2 default_spacing = new Vector2(0.6f, 0f);
        private static readonly MarginPadding default_padding = new MarginPadding { Top = 2, Bottom = 4 };
        private static readonly Vector2 shadow_offset = new Vector2(0f, 1.5f);

        public BeatSightSpriteText()
        {
            Font = BeatSightFont.Body();
            Colour = UITheme.TextPrimary;
            Spacing = default_spacing;
            Padding = default_padding;
            Truncate = false;
            AllowMultiline = true;
            UseFullGlyphHeight = true;
            Shadow = true;
            ShadowColour = UITheme.Background.Opacity(0.55f);
            ShadowOffset = shadow_offset;
        }
    }
}
