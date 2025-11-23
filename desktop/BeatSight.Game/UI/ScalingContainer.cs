using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osuTK;

namespace BeatSight.Game.UI
{
    public partial class ScalingContainer : Container
    {
        protected override void Update()
        {
            base.Update();
            if (Parent != null)
            {
                Size = new Vector2(Parent.DrawSize.X / Scale.X, Parent.DrawSize.Y / Scale.Y);
            }
        }
    }
}
