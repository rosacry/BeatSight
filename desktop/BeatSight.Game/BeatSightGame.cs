using System;
using System.IO;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Screens;

namespace BeatSight.Game
{
    public partial class BeatSightGame : osu.Framework.Game
    {
        private ScreenStack screenStack = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            // Initialize the game
            Child = screenStack = new ScreenStack { RelativeSizeAxes = Axes.Both };

            ensureCookieFile();
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Load the main menu
            screenStack.Push(new Screens.MainMenuScreen());
        }

        /// <summary>
        /// The osu! framework attempts to load a "cookie" file for persistent web requests.
        /// Creating an empty placeholder avoids repeated noisy log warnings on startup.
        /// </summary>
        private void ensureCookieFile()
        {
            try
            {
                const string cookieFileName = "cookie";

                string baseDirectory = AppContext.BaseDirectory;
                string cookiePath = Path.Combine(baseDirectory, cookieFileName);

                if (File.Exists(cookiePath))
                    return;

                using var stream = File.Create(cookiePath);
                using var writer = new StreamWriter(stream);
                writer.WriteLine("# BeatSight cookie store");
            }
            catch
            {
                // Non-fatal: if storage is inaccessible we simply leave the warning behaviour unchanged.
            }
        }
    }
}
