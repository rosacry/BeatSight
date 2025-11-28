using osu.Framework.Graphics;
using osu.Framework.Graphics.Cursor;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osuTK;
using osuTK.Graphics;
using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Context menu container styled to match BeatSight's theme.
    /// </summary>
    public partial class BeatSightContextMenuContainer : ContextMenuContainer
    {
        protected override Menu CreateMenu() => new BeatSightContextMenu();

        private partial class BeatSightContextMenu : Menu
        {
            public BeatSightContextMenu()
                : base(Direction.Vertical)
            {
                BackgroundColour = UITheme.Surface;
                MaskingContainer.CornerRadius = 8;
                MaskingContainer.EdgeEffect = new osu.Framework.Graphics.Effects.EdgeEffectParameters
                {
                    Type = osu.Framework.Graphics.Effects.EdgeEffectType.Shadow,
                    Colour = Color4.Black.Opacity(0.3f),
                    Radius = 10,
                    Offset = new Vector2(0, 2)
                };
            }

            protected override Menu CreateSubMenu() => new BeatSightContextMenu();

            protected override DrawableMenuItem CreateDrawableMenuItem(MenuItem item) => new BeatSightDrawableMenuItem(item);

            protected override osu.Framework.Graphics.Containers.ScrollContainer<Drawable> CreateScrollContainer(Direction direction)
                => new BeatSightScrollContainer(direction);

            private partial class BeatSightDrawableMenuItem : DrawableMenuItem
            {
                public BeatSightDrawableMenuItem(MenuItem item)
                    : base(item)
                {
                    BackgroundColour = UITheme.Surface;
                    BackgroundColourHover = UITheme.SurfaceAlt;
                }

                protected override Drawable CreateContent() => new BeatSightSpriteText
                {
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                    Padding = new osu.Framework.Graphics.MarginPadding { Horizontal = 12, Vertical = 8 },
                    Font = BeatSightFont.Body(14),
                    Colour = UITheme.TextPrimary
                };
            }
        }
    }
}
