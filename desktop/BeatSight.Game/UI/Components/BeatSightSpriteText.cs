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
        private static readonly Vector2 default_spacing = new Vector2(0.1f, 0f);
        private static readonly Vector2 shadow_offset = new Vector2(1f, 1f);

        public BeatSightSpriteText()
        {
            Font = BeatSightFont.Body();
            Colour = UITheme.TextPrimary;
            Spacing = default_spacing;
            Truncate = false;
            AllowMultiline = true;
            UseFullGlyphHeight = false; // Disabled to fix vertical centering issues in buttons
            Shadow = false;
            ShadowColour = new osuTK.Graphics.Color4(0, 0, 0, 128); // Standard semi-transparent black
            ShadowOffset = shadow_offset;
        }
    }
}
