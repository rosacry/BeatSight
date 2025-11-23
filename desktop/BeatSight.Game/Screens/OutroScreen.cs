using System;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Audio;
using osu.Framework.Audio.Sample;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Screens;
using osu.Framework.Utils;
using osu.Framework.Logging;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens
{
    public partial class OutroScreen : Screen
    {
        private Container logoContainer = null!;
        private SpriteText mainText = null!;
        private SpriteText subText = null!;
        private Box flashBox = null!;
        private Box blackOutBox = null!;

        private Sample? glitchSample;
        // private Sample? powerDownSample;

        [BackgroundDependencyLoader]
        private void load(AudioManager audio)
        {
            glitchSample = audio.Samples.Get("intro_glitch");
            // powerDownSample = audio.Samples.Get("outro_powerdown"); // Assuming we might have this or reuse something

            InternalChildren = new Drawable[]
            {
                // Background is now global
                logoContainer = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Children = new Drawable[]
                    {
                        mainText = new SpriteText
                        {
                            Text = "BeatSight",
                            Font = BeatSightFont.Title(UITheme.MainLogoTitleSize),
                            Colour = UITheme.AccentPrimary,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Alpha = 1,
                            Scale = Vector2.One,
                        },
                        subText = new SpriteText
                        {
                            Text = "SYSTEM SHUTDOWN",
                            Font = BeatSightFont.Subtitle(UITheme.MainLogoSubtitleSize),
                            Colour = UITheme.TextSecondary,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Y = UITheme.MainLogoSubtitleY,
                            Alpha = 0,
                            Spacing = new Vector2(2, 0),
                        }
                    }
                },
                flashBox = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.White,
                    Alpha = 0,
                    Blending = BlendingParameters.Additive,
                },
                blackOutBox = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black,
                    Alpha = 0,
                }
            };
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            Logger.Log("OutroScreen entered", LoggingTarget.Runtime, LogLevel.Important);

            // Animation Sequence

            // 1. Initial state - Logo is there (assuming we transition from main menu or similar state)
            // If we want to make it feel like we are leaving the app, we might want to capture the previous screen? 
            // But for now, let's just show the logo "shutting down".

            // 2. "System Shutdown" text appears
            subText.FadeIn(300, Easing.OutQuint);
            subText.MoveToY(UITheme.MainLogoSubtitleY, 300, Easing.OutQuint);

            // 3. Glitch and distort
            using (BeginDelayedSequence(500))
            {
                // Glitch loop
                for (int i = 0; i < 15; i++)
                {
                    double delay = i * 40;
                    Scheduler.AddDelayed(() =>
                    {
                        mainText.Alpha = RNG.NextSingle(0.5f, 1f);
                        mainText.Position = new Vector2(RNG.NextSingle(-10, 10), RNG.NextSingle(-5, 5));
                        mainText.Colour = RNG.NextBool() ? UITheme.AccentPrimary : UITheme.AccentSecondary;

                        // Randomly scale
                        if (RNG.NextBool())
                            mainText.Scale = new Vector2(RNG.NextSingle(0.9f, 1.1f));

                        // Play glitch sound occasionally
                        /*
                        if (i % 4 == 0)
                        {
                            var channel = glitchSample?.GetChannel();
                            if (channel != null)
                            {
                                channel.Volume.Value = 0.3;
                                channel.Play();
                            }
                        }
                        */
                    }, delay);
                }

                // 4. Collapse/Implode
                Scheduler.AddDelayed(() =>
                {
                    mainText.ScaleTo(new Vector2(1.5f, 0.05f), 200, Easing.InExpo)
                            .Then()
                            .ScaleTo(0, 100, Easing.InExpo);

                    subText.FadeOut(200);

                    flashBox.FadeTo(0.25f, 50).Then().FadeOut(300);
                }, 800);
            }

            // 5. Fade to black (CRT turn off style maybe?)
            using (BeginDelayedSequence(1200))
            {
                blackOutBox.FadeIn(400, Easing.OutExpo);

                // Horizontal line collapse effect (simulated with container scaling if we had a container for everything)
                // For now, just fade to black.
            }

            // 6. Actually Exit
            Scheduler.AddDelayed(() =>
            {
                if (Game is BeatSightGame beatSightGame)
                {
                    beatSightGame.ForceExit();
                }
                else
                {
                    Game.Exit();
                }
            }, 1800);
        }
    }
}
