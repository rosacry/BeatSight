using osu.Framework.Screens;
using osu.Framework.Graphics;

namespace BeatSight.Game.Screens
{
    public partial class BeatSightScreen : Screen
    {
        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            this.FadeInFromZero(400, Easing.OutQuint);
            this.MoveToY(20).MoveToY(0, 400, Easing.OutQuint);
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            this.FadeOut(200, Easing.OutQuad);
            this.ScaleTo(0.95f, 200, Easing.OutQuad);
            return base.OnExiting(e);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            this.FadeOut(200, Easing.OutQuad);
            this.MoveToX(-50, 200, Easing.OutQuad);
        }

        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            this.FadeIn(200, Easing.OutQuad);
            this.MoveToX(0, 200, Easing.OutQuad);
        }
    }
}
