using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    public partial class BeatSightScrollContainer : BasicScrollContainer
    {
        public BeatSightScrollContainer(Direction direction = Direction.Vertical)
            : base(direction)
        {
        }

        protected override ScrollbarContainer CreateScrollbar(Direction direction) => new BeatSightScrollbar(direction);

        private partial class BeatSightScrollbar : ScrollbarContainer
        {
            private const float dim_size = 8;

            public BeatSightScrollbar(Direction direction)
                : base(direction)
            {
                CornerRadius = 4;
                Masking = true;

                Child = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.AccentPrimary
                };
            }

            public override void ResizeTo(float val, int duration = 0, Easing easing = Easing.None)
            {
                Vector2 size = new Vector2(dim_size)
                {
                    [(int)ScrollDirection] = val
                };
                this.ResizeTo(size, duration, easing);
            }
        }
    }
}
