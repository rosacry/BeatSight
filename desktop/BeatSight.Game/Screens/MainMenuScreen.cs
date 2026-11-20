using BeatSight.Game.Screens.Editor;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.Screens.Recording;
using BeatSight.Game.Screens.Settings;
using BeatSight.Game.Screens.SongSelect;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using System;
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
        private Container logoContainer = null!;
        private SpriteText logoTitleText = null!;
        private SpriteText logoSubtitleText = null!;
        private FillFlowContainer buttonFlow = null!;
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
                    Y = -180, // Updated responsively in updateMenuLayout()
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
                                    Text = AppCopy.ProductName,
                                    Font = BeatSightFont.Title(UITheme.MainLogoTitleSize),
                                    Colour = UITheme.AccentPrimary,
                                    Anchor = Anchor.Centre,
                                    Origin = Anchor.Centre,
                                    Shadow = true,
                                    ShadowColour = UITheme.AccentPrimary.Opacity(0.25f),
                                    ShadowOffset = new Vector2(0, 0),
                                },
                                subtitleText = new SpriteText
                                {
                                    Text = AppCopy.Tagline,
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
                                Y = 120,
                                Spacing = new Vector2(0, 25),
                                Children = new Drawable[]
                                {
                                    // One primary action; everything else is neutral so the menu has a clear hierarchy.
                                    new MenuButton("Playback", MenuButtonStyle.Primary)
                                    {
                                        Action = () => this.Push(new SongSelectScreen())
                                    },
                                    new MenuButton("Editor", MenuButtonStyle.Secondary)
                                    {
                                        Action = () => this.Push(new SongSelectScreen(editorMode: true))
                                    },
                                    new MenuButton("Record", MenuButtonStyle.Secondary)
                                    {
                                        Action = () => this.Push(new RecordingScreen())
                                    },
                                    new MenuButton("Settings", MenuButtonStyle.Secondary)
                                    {
                                        Action = () => this.Push(new SettingsScreen())
                                    },
                                    new MenuButton("Exit", MenuButtonStyle.Quiet)
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

            updateMenuLayout();
            logoTitleText = titleText;
            logoSubtitleText = subtitleText;

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
                        double delay = i * 100;

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
                titleText.FadeInFromZero(UITheme.MotionSlow, UITheme.MotionEasing);

                // Subtitle Animation
                subtitleText.Delay(150).FadeIn(UITheme.MotionSlow, UITheme.MotionEasing);

                // Button stagger: short fade and rise, no rotation or bounce.
                int i = 0;
                foreach (var child in buttonFlow.Children)
                {
                    if (child is MenuButton button)
                    {
                        button.Alpha = 0;
                        button.Y = 14;

                        double delay = 350 + i * 60;

                        button.Delay(delay)
                              .FadeIn(UITheme.MotionNormal, UITheme.MotionEasing)
                              .MoveToY(0, UITheme.MotionSlow, UITheme.MotionEasing);
                        i++;
                    }
                }
            }
        }

        protected override void Update()
        {
            base.Update();
            updateMenuLayout();
        }

        private void updateMenuLayout()
        {
            if (logoContainer == null || buttonFlow == null)
                return;

            var metrics = MainMenuResponsiveLayout.Compute(DrawWidth, DrawHeight);

            logoContainer.Y = metrics.LogoY;
            buttonFlow.Spacing = new Vector2(0, metrics.ButtonFlowSpacing);

            if (logoTitleText != null)
                logoTitleText.Font = BeatSightFont.Title(metrics.LogoTitleSize);

            if (logoSubtitleText != null)
            {
                logoSubtitleText.Font = BeatSightFont.Subtitle(metrics.LogoSubtitleSize);
                logoSubtitleText.Y = metrics.LogoSubtitleY;
                logoSubtitleText.Spacing = new Vector2(metrics.LogoSubtitleSpacing, 0);
            }

            if (buttonFlow.DrawHeight <= 0)
                return;

            float desiredTop = logoContainer.Y + metrics.LogoSubtitleY + metrics.SubtitleToButtonsGap;
            float desiredCentre = desiredTop + buttonFlow.DrawHeight * 0.5f;
            buttonFlow.Y = Math.Clamp(desiredCentre, metrics.ButtonFlowMinY, metrics.ButtonFlowMaxY);
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

    public enum MenuButtonStyle
    {
        /// <summary>The one main action: filled accent.</summary>
        Primary,
        /// <summary>Other destinations: neutral surface with a subtle border.</summary>
        Secondary,
        /// <summary>Leaving the app: text-weight button, never louder than the rest.</summary>
        Quiet
    }

    public partial class MenuButton : BeatSightButton
    {
        private readonly MenuButtonStyle style;
        private BeatSightSpriteText spriteText = null!;
        private string originalText = null!;
        private float lastWidth;
        private float lastHeight;

        public MenuButton(string text, MenuButtonStyle style)
        {
            Text = text;
            originalText = text;
            this.style = style;
            Size = new Vector2(320, 70);
            Anchor = Anchor.TopCentre;
            Origin = Anchor.TopCentre;
            CornerRadius = 12;
        }

        private Color4 idleBackground => style switch
        {
            MenuButtonStyle.Primary => UITheme.AccentPrimary,
            MenuButtonStyle.Secondary => UITheme.Surface,
            _ => UITheme.Background.Opacity(0f)
        };

        private Color4 hoverBackground => style switch
        {
            MenuButtonStyle.Primary => UITheme.Emphasise(UITheme.AccentPrimary, 1.12f),
            MenuButtonStyle.Secondary => UITheme.SurfaceAlt,
            _ => UITheme.Surface
        };

        private Color4 textColour => style switch
        {
            MenuButtonStyle.Primary => UITheme.TextOnAccent,
            MenuButtonStyle.Secondary => UITheme.TextPrimary,
            _ => UITheme.TextSecondary
        };

        [BackgroundDependencyLoader]
        private void load()
        {
            // Applied after the base load, which resets the background to the accent colour.
            BackgroundColour = idleBackground;
            BorderThickness = style == MenuButtonStyle.Secondary ? 1.5f : 0;
            BorderColour = UITheme.Border;

            // CreateText runs from the base constructor before the style is known, so colour the label here.
            if (spriteText != null)
                spriteText.Colour = textColour;
        }

        protected override void Update()
        {
            base.Update();

            if (Parent == null)
                return;

            float targetWidth = ResponsiveLayout.ClampFraction(Parent.DrawWidth, 0.2f, 240f, 380f);
            float targetHeight = ResponsiveLayout.ClampFraction(Parent.DrawHeight, 0.062f, 44f, 64f);
            if (style == MenuButtonStyle.Quiet)
                targetHeight *= 0.8f;
            float targetFont = Math.Clamp(targetHeight * 0.36f, 15f, 24f);

            if (Math.Abs(targetWidth - lastWidth) > 0.2f)
            {
                Width = targetWidth;
                lastWidth = targetWidth;
            }

            if (Math.Abs(targetHeight - lastHeight) > 0.2f)
            {
                Height = targetHeight;
                lastHeight = targetHeight;
            }

            if (spriteText != null)
                spriteText.Font = BeatSightFont.Button(style == MenuButtonStyle.Quiet ? targetFont * 0.85f : targetFont);
        }

        public void DecryptIn(double duration)
        {
            this.FadeInFromZero(duration, UITheme.MotionEasing);
            this.MoveToY(10).MoveToY(0, duration, UITheme.MotionEasing);

            if (spriteText != null)
                spriteText.Text = originalText;
        }

        protected override bool OnHover(HoverEvent e)
        {
            BackgroundColour = hoverBackground;
            if (style == MenuButtonStyle.Secondary)
                BorderColour = UITheme.AccentPrimary.Opacity(0.7f);
            if (spriteText != null && style == MenuButtonStyle.Quiet)
                spriteText.FadeColour(UITheme.TextPrimary, UITheme.MotionFast, UITheme.MotionEasing);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            BackgroundColour = idleBackground;
            BorderColour = UITheme.Border;
            if (spriteText != null && style == MenuButtonStyle.Quiet)
                spriteText.FadeColour(textColour, UITheme.MotionNormal, UITheme.MotionEasing);
            base.OnHoverLost(e);
        }

        protected override SpriteText CreateText()
        {
            spriteText = new BeatSightSpriteText
            {
                Depth = -1,
                Origin = Anchor.Centre,
                Anchor = Anchor.Centre,
                Font = BeatSightFont.Button(22f),
                UseFullGlyphHeight = false
            };
            return spriteText;
        }
    }
}
