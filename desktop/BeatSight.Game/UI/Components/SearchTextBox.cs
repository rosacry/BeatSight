using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input;
using osu.Framework.Input.Events;
using osuTK.Input;
using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.UI.Components
{
    public partial class SearchTextBox : BeatSightTextBox
    {
        protected override Color4 FocusBorderColour => UITheme.SurfaceAlt;
        protected override bool AllowHoverEffect => false;

        public SearchTextBox()
        {
            BackgroundFocused = UITheme.SurfaceAlt;
        }

        private bool animateChanges = true;

        protected override Caret CreateCaret() => base.CreateCaret().With(c =>
        {
            c.Alpha = 0;
            c.Colour = Color4.Transparent;
            c.OnUpdate += d => d.Alpha = 0;
        });

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == Key.Escape && Text.Length > 0)
            {
                Text = string.Empty;
                return true;
            }

            return base.OnKeyDown(e);
        }

        public void FocusAndAppend(char c)
        {
            Text += c;
            GetContainingFocusManager()?.ChangeFocus(this);

            var input = GetContainingInputManager();
            if (input != null)
            {
                var state = input.CurrentState;
                for (int i = 0; i < Text.Length + 1; i++)
                    base.OnKeyDown(new KeyDownEvent(state, Key.Right));
            }
        }

        public void SetTextWithoutAnimation(string text)
        {
            animateChanges = false;
            Text = text;
            Scheduler.Add(() => animateChanges = true);
        }

        protected override Drawable GetDrawableCharacter(char c)
        {
            var drawable = base.GetDrawableCharacter(c);

            if (animateChanges)
            {
                // Add pop-in animation
                drawable.OnLoadComplete += d =>
                {
                    d.FadeInFromZero(200, Easing.OutQuint);
                    d.MoveToY(-10).MoveToY(0, 400, Easing.OutElastic);
                };
            }

            return drawable;
        }
    }
}
