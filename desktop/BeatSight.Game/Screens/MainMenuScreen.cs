using BeatSight.Game.Screens.Editor;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.Screens.Settings;
using BeatSight.Game.Screens.SongSelect;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Utils;

namespace BeatSight.Game.Screens
{
    public partial class MainMenuScreen : BeatSightScreen
    {
        private GameHost host = null!;
        private readonly bool fromIntro;
        private Container logoParallax = null!;
        private bool parallaxEnabled = false;

        public MainMenuScreen(bool fromIntro = false)
        {
            this.fromIntro = fromIntro;
        }

        [BackgroundDependencyLoader]
        private void load(GameHost host)
        {
            this.host = host;
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            FillFlowContainer buttonFlow;
            Container logoContainer;
            SpriteText titleText;
            SpriteText subtitleText;
            Box scannerBeam;

            InternalChildren = new Drawable[]
            {
                // Logo Container - Independent (Moved out of ScreenEdgeContainer to match IntroScreen coordinates)
                logoContainer = new Container
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Y = -180, // Final position
                    Children = new Drawable[]
                    {
                        logoParallax = new Container
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Children = new Drawable[]
                            {
                                titleText = new SpriteText
                                {
                                    Text = "BeatSight",
                                    Font = BeatSightFont.Title(UITheme.MainLogoTitleSize),
                                    Colour = UITheme.AccentPrimary,
                                    Anchor = Anchor.Centre,
                                    Origin = Anchor.Centre,
                                    Shadow = true,
                                    ShadowColour = UITheme.AccentPrimary.Opacity(0.5f),
                                    ShadowOffset = new Vector2(0, 0),
                                },
                                subtitleText = new SpriteText
                                {
                                    Text = "Rhythm Game Analysis Tool",
                                    Font = BeatSightFont.Subtitle(UITheme.MainLogoSubtitleSize),
                                    Colour = UITheme.TextSecondary,
                                    Anchor = Anchor.Centre,
                                    Origin = Anchor.Centre,
                                    Y = UITheme.MainLogoSubtitleY,
                                    Spacing = new Vector2(5, 0),
                                }
                            }
                        }
                    }
                },

                // Background is now global
                new ScreenEdgeContainer(scrollable: false)
                {
                    Content = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Children = new Drawable[]
                        {
                            buttonFlow = new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                                Y = 100, // Offset below center
                                Spacing = new Vector2(0, 25),
                                Children = new Drawable[]
                                {
                                    new MenuButton("Playback", UITheme.AccentPrimary)
                                    {
                                        Action = () => this.Push(new SongSelectScreen())
                                    },
                                    new MenuButton("Editor", UITheme.AccentSecondary)
                                    {
                                        Action = () => this.Push(new SongSelectScreen(editorMode: true))
                                    },
                                    new MenuButton("Settings", UITheme.AccentWarning)
                                    {
                                        Action = () => this.Push(new SettingsScreen())
                                    },
                                    new MenuButton("Exit", UITheme.AccentError)
                                    {
                                        Action = exitGame
                                    },
                                }
                            },
                            scannerBeam = new Box
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 2,
                                Colour = UITheme.AccentSecondary,
                                Alpha = 0,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                                Y = -400 // Start above
                            }
                        }
                    }
                }
            };

            if (!fromIntro)
            {
                // Smooth entry animation only if not from intro
                this.FadeInFromZero(800, Easing.OutQuint);
            }
            else
            {
                // Cancel base animations to ensure seamless transition
                this.ClearTransforms();
                this.Alpha = 1;
                this.Y = 0;
            }

            // Breathing animation
            Scheduler.AddDelayed(() =>
            {
                logoParallax.Loop(b => b.ScaleTo(1.02f, 2000, Easing.InOutSine).Then().ScaleTo(1f, 2000, Easing.InOutSine));
            }, 2000);

            if (fromIntro)
            {
                // Transition Sequence

                // 1. Match Intro State
                // Intro ends with Logo at -180 (moved during Intro)
                // logoContainer.Y = -180; // Already set in constructor

                // Show immediately as IntroScreen hides its logo
                logoContainer.Alpha = 1;

                // Intro Title is 80, Main is 80 -> Scale 1.0
                titleText.Scale = Vector2.One;

                // Intro Subtitle is 24, Main is 24 -> Scale 1.0
                subtitleText.Scale = Vector2.One;

                // 2. Animate to Final State
                // Already at final state

                // 3. Scanner Sweep
                // Removed as per user request

                // 4. Decrypt Buttons as scanner passes
                int i = 0;
                foreach (var child in buttonFlow.Children)
                {
                    if (child is MenuButton button)
                    {
                        button.Alpha = 0;
                        // Calculate delay based on position in flow
                        // Start after logo begins moving
                        double delay = 200 + i * 100;

                        Scheduler.AddDelayed(() => button.DecryptIn(300), delay);
                        i++;
                    }
                }

                // Enable parallax after transition
                Scheduler.AddDelayed(() => parallaxEnabled = true, 1200);
            }
            else
            {
                parallaxEnabled = true;

                // Full Title Animation
                titleText.ScaleTo(1f).Then().ScaleTo(1.05f, 1000, Easing.OutQuint).Then().ScaleTo(1f, 1000, Easing.OutQuint);
                titleText.FadeInFromZero(600);

                // Subtitle Animation
                subtitleText.Delay(500).FadeIn(600);

                // Button Stagger Animation
                int i = 0;
                foreach (var child in buttonFlow.Children)
                {
                    if (child is MenuButton button)
                    {
                        button.Alpha = 0;
                        button.Y = 100;
                        button.Scale = new Vector2(0.5f);
                        button.Rotation = RNG.NextSingle(-10, 10);

                        double delay = 700 + i * 100; // Faster start if from intro

                        button.Delay(delay)
                              .FadeIn(400)
                              .MoveToY(0, 1000, Easing.OutElastic)
                              .ScaleTo(1f, 1000, Easing.OutElastic)
                              .RotateTo(0, 1000, Easing.OutElastic);
                        i++;
                    }
                }
            }
        }

        protected override bool OnMouseMove(MouseMoveEvent e)
        {
            if (logoParallax != null && parallaxEnabled)
            {
                Vector2 relativeMouse = e.MousePosition - DrawSize / 2;
                // Parallax effect: Move opposite to mouse or with mouse?
                // Usually opposite gives depth (background), with mouse gives "floating" feel.
                // User requested fix: make it more subtle and standard depth feel.
                logoParallax.MoveTo(relativeMouse * -0.005f, 100, Easing.OutQuad);
            }
            return base.OnMouseMove(e);
        }

        private void exitGame()
        {
            // Manually push OutroScreen for the button click
            // This guarantees the animation plays even if OnExiting interception fails
            this.Push(new OutroScreen());
        }
    }

    public partial class MenuButton : BeatSightButton
    {
        private Color4 baseColour;
        private BeatSightSpriteText spriteText = null!;
        private string originalText = null!;

        public MenuButton(string text, Color4 colour)
        {
            Text = text;
            originalText = text;
            baseColour = colour;
            BackgroundColour = colour.Opacity(0.8f);
            Size = new Vector2(320, 70);
            Anchor = Anchor.TopCentre;
            Origin = Anchor.TopCentre;

            BorderThickness = 3;
            BorderColour = colour;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            // Re-apply the custom colour after the base load might have reset it
            BackgroundColour = baseColour.Opacity(0.8f);
        }

        public void DecryptIn(double duration)
        {
            this.FadeInFromZero(duration);
            this.ScaleTo(new Vector2(1.2f, 0.1f)).ScaleTo(1f, duration, Easing.OutExpo); // Stretch effect

            // Restore text immediately (no scrambling)
            if (spriteText != null)
            {
                spriteText.Text = originalText;
                spriteText.FlashColour(Color4.White, 200, Easing.OutQuint);
            }
        }

        protected override bool OnHover(HoverEvent e)
        {
            BorderColour = Color4.White;
            BackgroundColour = baseColour.Opacity(1f);
            this.ScaleTo(1.05f, 400, Easing.OutElastic);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            BorderColour = baseColour;
            BackgroundColour = baseColour.Opacity(0.8f);
            this.ScaleTo(1f, 400, Easing.OutQuint);
            base.OnHoverLost(e);
        }

        protected override SpriteText CreateText()
        {
            spriteText = new BeatSightSpriteText
            {
                Depth = -1,
                Origin = Anchor.Centre,
                Anchor = Anchor.Centre,
                Font = BeatSightFont.Button(30f),
                UseFullGlyphHeight = false,
                Colour = Color4.White,
                Shadow = true,
                ShadowColour = new Color4(0, 0, 0, 100),
                ShadowOffset = new Vector2(2, 2)
            };
            return spriteText;
        }
    }

    public partial class PlaceholderScreen : Screen
    {
        private readonly string title;

        public PlaceholderScreen(string title)
        {
            this.title = title;
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Background
                },
                new SpriteText
                {
                    Text = $"{title} screen coming soon",
                    Font = BeatSightFont.Title(48f),
                    Colour = UITheme.TextPrimary,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre
                },
                new SpriteText
                {
                    Text = "Press Esc to return",
                    Font = BeatSightFont.Subtitle(24f),
                    Colour = UITheme.TextMuted,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Y = 80
                }
            };
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
                this.Exit();
                return true;
            }

            return base.OnKeyDown(e);
        }
    }
}
