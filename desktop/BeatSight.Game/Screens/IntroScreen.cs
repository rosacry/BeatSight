using BeatSight.Game.Audio;
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
using osuTK;
using osuTK.Graphics;
using System.Collections.Generic;

namespace BeatSight.Game.Screens
{
    public partial class IntroScreen : Screen
    {
        [Resolved]
        private DynamicBackground background { get; set; } = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        private Container content = null!;
        private Container logoContainer = null!;
        private SpriteText mainText = null!;
        private SpriteText subText = null!;
        private Box flashBox = null!;

        // Visual Elements
        private Container gridContainer = null!;
        private Box scannerLine = null!;
        private Container circlesContainer = null!;
        private FillFlowContainer<SpriteText> bootLog = null!;
        private float lastResponsiveWidth = -1f;
        private float lastResponsiveHeight = -1f;

        private Sample? impactSample;
        private Sample? shimmerSample;
        private Sample? glitchSample;
        private Sample? beatSample;

        [BackgroundDependencyLoader]
        private void load(AudioManager audio)
        {
            impactSample = audio.Samples.Get("intro_impact");
            shimmerSample = audio.Samples.Get("intro_shimmer");
            glitchSample = audio.Samples.Get("intro_glitch");
            beatSample = audio.Samples.Get("metronome_tick") ?? audio.Samples.Get("button_hover");
            var metrics = MainMenuResponsiveLayout.Compute(DrawWidth, DrawHeight);

            InternalChildren = new Drawable[]
            {
                content = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Children = new Drawable[]
                    {
                        // 1. Grid / Tech Layer
                        gridContainer = new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Alpha = 0,
                            Children = CreateGridLines()
                        },
                        
                        // Boot Log
                        bootLog = new FillFlowContainer<SpriteText>
                        {
                            Anchor = Anchor.BottomLeft,
                            Origin = Anchor.BottomLeft,
                            Position = new Vector2(metrics.IntroBootMarginX, -metrics.IntroBootMarginY),
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, metrics.IntroBootSpacing),
                            Alpha = 0.6f,
                        },

                        scannerLine = new Box
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = metrics.IntroScannerHeight,
                            Colour = UITheme.AccentSecondary,
                            Alpha = 0,
                            Origin = Anchor.CentreLeft,
                        },
                        
                        // 2. Rhythm Layer
                        circlesContainer = new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                        },

                        // 3. Logo Layer
                        logoContainer = new Container
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Children = new Drawable[]
                            {
                                // Match MainMenuScreen structure with an inner container
                                new Container
                                {
                                    Anchor = Anchor.Centre,
                                    Origin = Anchor.Centre,
                                    Children = new Drawable[]
                                    {
                                        mainText = new BeatSightSpriteText
                                        {
                                            Text = AppCopy.ProductName,
                                            Font = BeatSightFont.Title(metrics.LogoTitleSize),
                                            Colour = UITheme.AccentPrimary,
                                            Anchor = Anchor.Centre,
                                            Origin = Anchor.Centre,
                                            Alpha = 0,
                                            Scale = new Vector2(1.5f),
                                            Shadow = true,
                                            ShadowColour = UITheme.AccentPrimary.Opacity(0.5f),
                                            ShadowOffset = new Vector2(0, 0),
                                        },
                                        subText = new BeatSightSpriteText
                                        {
                                            Text = AppCopy.Tagline,
                                            Font = BeatSightFont.Subtitle(metrics.LogoSubtitleSize),
                                            Colour = UITheme.TextSecondary,
                                            Anchor = Anchor.Centre,
                                            Origin = Anchor.Centre,
                                            Y = metrics.LogoSubtitleY,
                                            Alpha = 0,
                                            Spacing = new Vector2(metrics.LogoSubtitleSpacing * 4f, 0),
                                        }
                                    }
                                }
                            }
                        },
                        
                        // 4. FX Layer
                        flashBox = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = Color4.White,
                            Alpha = 0,
                            Blending = BlendingParameters.Additive,
                        }
                    }
                }
            };
        }

        private Drawable[] CreateGridLines()
        {
            var lines = new List<Drawable>();
            // Vertical lines
            for (int i = 0; i <= 20; i++)
            {
                lines.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 1,
                    RelativePositionAxes = Axes.X,
                    X = i / 20f,
                    Colour = Color4.White.Opacity(0.03f)
                });
            }
            // Horizontal lines
            for (int i = 0; i <= 12; i++)
            {
                lines.Add(new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 1,
                    RelativePositionAxes = Axes.Y,
                    Y = i / 12f,
                    Colour = Color4.White.Opacity(0.03f)
                });
            }
            return lines.ToArray();
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            // Sequence

            // Phase 1: Scan & Boot (0 - 800ms)
            gridContainer.FadeIn(500);
            // scannerLine removed

            AddBootLog("INITIALIZING KERNEL...", 100);
            AddBootLog("LOADING AUDIO SUBSYSTEM...", 300);
            AddBootLog("CALIBRATING TIMING...", 500);
            AddBootLog("ANALYSIS ENGINE READY.", 700);

            // Phase 2: Rhythm Construction (800ms - 2000ms)
            // Spawn circles in a triangle pattern with rising pitch
            Scheduler.AddDelayed(() => SpawnHitCircle(new Vector2(-150, -60), 0.8), 400);
            Scheduler.AddDelayed(() => SpawnHitCircle(new Vector2(150, -60), 1.0), 800);
            Scheduler.AddDelayed(() => SpawnHitCircle(new Vector2(0, 120), 1.2), 1200);

            // Phase 3: Convergence & Impact (1600ms)
            Scheduler.AddDelayed(() =>
            {
                // Clear circles
                circlesContainer.FadeOut(200);
                gridContainer.FadeOut(200);
                scannerLine.FadeOut(200);
                bootLog.FadeOut(200);

                // Big Flash
                flashBox.FadeTo(0.25f).FadeOut(1000, Easing.OutExpo);

                // Impact Sound - Layered for depth
                if (uiAudio.AudioEnabled)
                {
                    impactSample?.Play();
                    var deepImpact = impactSample?.GetChannel();
                    if (deepImpact != null)
                    {
                        deepImpact.Frequency.Value = 0.5; // Low rumble
                        deepImpact.Play();
                    }
                }

                // Logo Slam
                mainText.Alpha = 1;
                mainText.ScaleTo(1f, 800, Easing.OutElastic);

                // Background reaction
                background.Glitch(10);

            }, 1600);

            // Phase 4: Subtitle & Polish (2200ms+)
            Scheduler.AddDelayed(() =>
            {
                subText.FadeIn(800);
                var metrics = MainMenuResponsiveLayout.Compute(DrawWidth, DrawHeight);
                subText.TransformTo(nameof(subText.Spacing), new Vector2(metrics.LogoSubtitleSpacing, 0), 800, Easing.OutQuint);
                if (uiAudio.AudioEnabled) shimmerSample?.Play();
            }, 2200);

            // Phase 4.5: Move to Main Menu Position
            Scheduler.AddDelayed(() =>
            {
                var metrics = MainMenuResponsiveLayout.Compute(DrawWidth, DrawHeight);
                logoContainer.MoveToY(metrics.LogoY, 800, Easing.OutQuint);
            }, 3500);

            // Phase 5: Exit (4500ms)
            Scheduler.AddDelayed(() =>
            {
                this.Push(new MainMenuScreen(true));
            }, 4500);
        }

        private void AddBootLog(string text, double delay)
        {
            Scheduler.AddDelayed(() =>
            {
                var metrics = MainMenuResponsiveLayout.Compute(DrawWidth, DrawHeight);
                var t = new SpriteText
                {
                    Text = text,
                    Font = BeatSightFont.Subtitle(metrics.IntroBootFontSize),
                    Colour = UITheme.AccentSecondary,
                    Alpha = 0,
                };
                bootLog.Add(t);
                t.FadeIn(200);
            }, delay);
        }

        private void SpawnHitCircle(Vector2 position, double pitch)
        {
            var metrics = MainMenuResponsiveLayout.Compute(DrawWidth, DrawHeight);
            float circleSize = metrics.IntroCircleSize;
            float approachCircleSize = metrics.IntroApproachCircleSize;

            var circle = new CircularContainer
            {
                Size = new Vector2(circleSize),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Position = position,
                Masking = true,
                BorderColour = UITheme.AccentPrimary,
                BorderThickness = metrics.IntroCircleBorderThickness,
                Alpha = 0,
                Children = new Drawable[]
                {
                    new Box { RelativeSizeAxes = Axes.Both, Alpha = 0, AlwaysPresent = true }, // Hit area
                    new Circle // Inner dot
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Size = new Vector2(metrics.IntroInnerDotSize),
                        Colour = UITheme.AccentPrimary,
                    }
                }
            };

            var approachCircle = new CircularContainer
            {
                Size = new Vector2(approachCircleSize),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Position = position,
                Masking = true,
                BorderColour = UITheme.AccentSecondary,
                BorderThickness = System.Math.Max(1f, metrics.IntroCircleBorderThickness * 0.55f),
                Alpha = 0,
                Child = new Box { RelativeSizeAxes = Axes.Both, Alpha = 0, AlwaysPresent = true }
            };

            circlesContainer.Add(approachCircle);
            circlesContainer.Add(circle);

            // Animation
            circle.FadeIn(200);
            circle.ScaleTo(0.5f).ScaleTo(1f, 400, Easing.OutBack);

            approachCircle.FadeIn(200);
            float targetScale = circleSize / System.Math.Max(1f, approachCircleSize);
            approachCircle.ScaleTo(1f).ScaleTo(targetScale, 400, Easing.InQuad);
            approachCircle.FadeOut(400, Easing.InQuad); // Fade out as it hits

            // Play beat with pitch
            if (uiAudio.AudioEnabled)
            {
                var channel = beatSample?.GetChannel();
                if (channel != null)
                {
                    channel.Frequency.Value = pitch;
                    channel.Play();
                }
            }

            // "Hit" effect after 400ms
            Scheduler.AddDelayed(() =>
            {
                circle.ScaleTo(1.2f, 100).FadeOut(100);
                var ripple = new Circle
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Position = position,
                    Size = new Vector2(circleSize),
                    Colour = UITheme.AccentPrimary.Opacity(0.5f),
                    Blending = BlendingParameters.Additive,
                };
                circlesContainer.Add(ripple);
                ripple.ScaleTo(2f, 300, Easing.OutQuad).FadeOut(300, Easing.OutQuad);
            }, 400);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);

            // Cancel base animations to ensure seamless transition
            this.ClearTransforms();
            this.Alpha = 1;
            this.X = 0;

            // Transition Logic
            // 1. Clean up non-logo elements
            gridContainer.FadeOut(300, Easing.OutQuint);
            circlesContainer.FadeOut(300, Easing.OutQuint);
            bootLog.FadeOut(300, Easing.OutQuint);
            scannerLine.FadeOut(300);

            // 2. Logo Handoff
            // Allow logo to persist to prevent flicker during transition
            // logoContainer.FadeOut(0);

            // 3. Background effect
            // Removed glitch for smoother transition
            // background.Glitch(20);

            // 4. Exit after elements have faded
            this.Delay(300).FadeOut(100);
        }

        protected override bool OnClick(osu.Framework.Input.Events.ClickEvent e)
        {
            // Disable skipping
            return true;
        }

        protected override void Update()
        {
            base.Update();
            applyResponsiveIntroLayout();
        }

        private void applyResponsiveIntroLayout(bool force = false)
        {
            if (DrawWidth <= 0 || DrawHeight <= 0)
                return;

            if (!force
                && System.Math.Abs(DrawWidth - lastResponsiveWidth) < 0.2f
                && System.Math.Abs(DrawHeight - lastResponsiveHeight) < 0.2f)
            {
                return;
            }

            var metrics = MainMenuResponsiveLayout.Compute(DrawWidth, DrawHeight);

            if (mainText != null)
                mainText.Font = BeatSightFont.Title(metrics.LogoTitleSize);

            if (subText != null)
            {
                subText.Font = BeatSightFont.Subtitle(metrics.LogoSubtitleSize);
                subText.Y = metrics.LogoSubtitleY;
            }

            if (bootLog != null)
            {
                bootLog.Position = new Vector2(metrics.IntroBootMarginX, -metrics.IntroBootMarginY);
                bootLog.Spacing = new Vector2(0, metrics.IntroBootSpacing);
                foreach (var line in bootLog.Children)
                    line.Font = BeatSightFont.Subtitle(metrics.IntroBootFontSize);
            }

            if (scannerLine != null)
                scannerLine.Height = metrics.IntroScannerHeight;

            lastResponsiveWidth = DrawWidth;
            lastResponsiveHeight = DrawHeight;
        }

        protected override bool OnKeyDown(osu.Framework.Input.Events.KeyDownEvent e)
        {
            return base.OnKeyDown(e);
        }
    }
}
