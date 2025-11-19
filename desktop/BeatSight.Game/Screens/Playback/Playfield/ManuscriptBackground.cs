using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    public partial class ManuscriptBackground : CompositeDrawable
    {
        public ManuscriptBackground()
        {
            RelativeSizeAxes = Axes.Both;

            // Paper background
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = new Color4(245, 243, 235, 255) // Off-white paper
            });

            // Staff lines container
            var staffContainer = new Container
            {
                RelativeSizeAxes = Axes.Y,
                Width = 300, // Fixed width for the staff? Or relative?
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
            };
            AddInternal(staffContainer);

            // Draw 5 vertical lines
            // Standard staff spacing is usually constant.
            float lineSpacing = 40;
            float totalWidth = lineSpacing * 4;
            staffContainer.Width = totalWidth;

            for (int i = 0; i < 5; i++)
            {
                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 2,
                    RelativePositionAxes = Axes.X,
                    X = i / 4f, // Distribute 0 to 1
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Colour = Color4.Black
                });
            }

            // Clef? Maybe later.
        }
    }
}
