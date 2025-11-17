using osu.Framework.Graphics;
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
    }
}
