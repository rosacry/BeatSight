using osu.Framework.Screens;
using osu.Framework.Graphics;

namespace BeatSight.Game.Screens
{
    public partial class BeatSightScreen : Screen
    {
        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            this.FadeInFromZero(200);
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            this.FadeOut(200);
            return base.OnExiting(e);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            this.FadeOut(200);
        }

        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            this.FadeIn(200);
        }
    }
}
