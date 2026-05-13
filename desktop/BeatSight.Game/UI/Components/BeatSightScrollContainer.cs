using System;
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
            private const float dim_size = 7;
            private const float minimum_horizontal_thumb_length = 34f;
            private const float minimum_vertical_thumb_length = 24f;

            public BeatSightScrollbar(Direction direction)
                : base(direction)
            {
                CornerRadius = 4;
                Masking = true;

                Child = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Mix(new Color4(173, 198, 232, 255), UITheme.SurfaceAlt, 0.32f).Opacity(0.78f)
                };
            }

            public override void ResizeTo(float val, int duration = 0, Easing easing = Easing.None)
            {
                float minimumLength = ScrollDirection == Direction.Horizontal
                    ? minimum_horizontal_thumb_length
                    : minimum_vertical_thumb_length;
                float clamped = Math.Max(minimumLength, val);
                Vector2 size = new Vector2(dim_size)
                {
                    [(int)ScrollDirection] = clamped
                };
                this.ResizeTo(size, duration, easing);
            }
        }
    }
}
