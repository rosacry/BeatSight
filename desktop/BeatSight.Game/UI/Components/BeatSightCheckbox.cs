using osu.Framework.Graphics;
using osu.Framework.Graphics.UserInterface;

namespace BeatSight.Game.UI.Components
{
    public partial class BeatSightCheckbox : BasicCheckbox
    {
        private const float default_corner_radius = 5f;

        public BeatSightCheckbox()
        {
            Masking = true;
            CornerRadius = default_corner_radius;
        }
    }
}
