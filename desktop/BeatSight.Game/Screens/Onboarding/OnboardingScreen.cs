using System;
using System.Collections.Generic;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Onboarding
{
    /// <summary>
    /// First-run onboarding experience for new users.
    /// Guides users through the basics of BeatSight.
    /// </summary>
    public partial class OnboardingScreen : BeatSightScreen
    {
        private const int current_onboarding_version = 1;
        private const float panel_width = 800;
        private const float panel_height = 550;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        private Bindable<bool> hasCompletedOnboarding = null!;
        private Bindable<int> onboardingVersion = null!;

        private int currentPage;
        private Container pageContainer = null!;
        private FillFlowContainer dotsContainer = null!;
        private BeatSightButton backButton = null!;
        private BeatSightButton nextButton = null!;

        private readonly List<OnboardingPage> pages = new();

        public Action? OnComplete;

        public OnboardingScreen()
        {
            RelativeSizeAxes = Axes.Both;
        }

        /// <summary>
        /// Check if onboarding should be shown for this user.
        /// </summary>
        public static bool ShouldShowOnboarding(BeatSightConfigManager config)
        {
            var completed = config.GetBindable<bool>(BeatSightSetting.HasCompletedOnboarding);
            var version = config.GetBindable<int>(BeatSightSetting.OnboardingVersion);

            // Show if never completed or if we have a newer version
            return !completed.Value || version.Value < current_onboarding_version;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            hasCompletedOnboarding = config.GetBindable<bool>(BeatSightSetting.HasCompletedOnboarding);
            onboardingVersion = config.GetBindable<int>(BeatSightSetting.OnboardingVersion);

            // Build pages
            buildPages();

            InternalChildren = new Drawable[]
            {
                // Dim background
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Overlay
                },
                // Main panel
                new Container
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Size = new Vector2(panel_width, panel_height),
                    Masking = true,
                    CornerRadius = 16,
                    BorderColour = UITheme.AccentPrimary,
                    BorderThickness = 2,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = UITheme.Background
                        },
                        // Header with logo/title
                        createHeader(),
                        // Page content
                        pageContainer = new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Padding = new MarginPadding { Top = 80, Bottom = 100, Left = 40, Right = 40 }
                        },
                        // Navigation
                        createNavigation()
                    }
                }
            };

            showPage(0);
        }

        private void buildPages()
        {
            pages.Add(new OnboardingPage
            {
                Title = "Welcome to BeatSight!",
                Description = "BeatSight is a drum learning and visualization tool that uses AI to transcribe drums from any song.\n\n" +
                              "Whether you're a beginner learning your first beat or an advanced drummer studying complex patterns, " +
                              "BeatSight helps you see and practice what you hear.",
                Icon = FontAwesome.Solid.Drum
            });

            pages.Add(new OnboardingPage
            {
                Title = "Generate Beatmaps",
                Description = "Simply drop an audio file into BeatSight and our AI will:\n\n" +
                              "• Separate the drum track from the mix\n" +
                              "• Detect the tempo and time signature\n" +
                              "• Identify each drum hit (kick, snare, hi-hat, etc.)\n" +
                              "• Create a playable beatmap automatically",
                Icon = FontAwesome.Solid.Magic
            });

            pages.Add(new OnboardingPage
            {
                Title = "Multiple Views",
                Description = "Practice with different visualization modes:\n\n" +
                              "• 2D Highway – Classic rhythm game style\n" +
                              "• 3D Perspective – Immersive depth view\n" +
                              "• Sheet Music – Traditional notation for reading\n\n" +
                              "Switch views anytime with the View button or keyboard shortcut.",
                Icon = FontAwesome.Solid.Eye
            });

            pages.Add(new OnboardingPage
            {
                Title = "Practice Tools",
                Description = "Learn at your own pace:\n\n" +
                              "• Adjust playback speed (0.25x to 2x)\n" +
                              "• Loop difficult sections\n" +
                              "• Use the metronome for timing\n" +
                              "• Edit the beatmap if the AI missed something",
                Icon = FontAwesome.Solid.GraduationCap
            });

            pages.Add(new OnboardingPage
            {
                Title = "Ready to Start?",
                Description = "You're all set! Here's how to begin:\n\n" +
                              "1. Click 'Generate' to create your first beatmap\n" +
                              "2. Select any audio file from your computer\n" +
                              "3. Wait for the AI to process (1-2 minutes)\n" +
                              "4. Start practicing!\n\n" +
                              "You can revisit this guide anytime from Settings.",
                Icon = FontAwesome.Solid.Play
            });
        }

        private Drawable createHeader()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 80,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.BackgroundLayer
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(15, 0),
                        Children = new Drawable[]
                        {
                            new SpriteIcon
                            {
                                Icon = FontAwesome.Solid.Drum,
                                Size = new Vector2(36),
                                Colour = UITheme.AccentPrimary
                            },
                            new SpriteText
                            {
                                Text = "BeatSight",
                                Font = FrameworkFont.Regular.With(size: 32),
                                Colour = Color4.White
                            }
                        }
                    },
                    // Skip button
                    new BeatSightButton
                    {
                        Width = 80,
                        Height = 28,
                        Text = "Skip",
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Margin = new MarginPadding { Right = 15 },
                        Action = completeOnboarding
                    }
                }
            };
        }

        private Drawable createNavigation()
        {
            var nav = new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 80,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    },
                    // Page dots
                    dotsContainer = new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(12, 0)
                    },
                    // Back button
                    backButton = new BeatSightButton
                    {
                        Width = 100,
                        Height = 36,
                        Text = "Back",
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Margin = new MarginPadding { Left = 20 },
                        Action = previousPage
                    },
                    // Next/Done button
                    nextButton = new BeatSightButton
                    {
                        Width = 120,
                        Height = 36,
                        Text = "Next",
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Margin = new MarginPadding { Right = 20 },
                        Action = nextPage
                    }
                }
            };

            buildDots();

            return nav;
        }

        private void buildDots()
        {
            dotsContainer?.Clear();

            for (int i = 0; i < pages.Count; i++)
            {
                int pageIndex = i;
                dotsContainer?.Add(new PageDot(i == currentPage)
                {
                    Action = () => showPage(pageIndex)
                });
            }
        }

        private void showPage(int index)
        {
            if (index < 0 || index >= pages.Count)
                return;

            currentPage = index;
            var page = pages[index];

            // Update content
            pageContainer.Clear();
            pageContainer.Add(new FillFlowContainer
            {
                RelativeSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 20),
                Children = new Drawable[]
                {
                    // Icon
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 80,
                        Child = new SpriteIcon
                        {
                            Icon = page.Icon,
                            Size = new Vector2(64),
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Colour = UITheme.AccentPrimary
                        }
                    },
                    // Title
                    new SpriteText
                    {
                        Text = page.Title,
                        Font = FrameworkFont.Regular.With(size: 28),
                        Colour = Color4.White,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre
                    },
                    // Description
                    new TextFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        TextAnchor = Anchor.TopCentre,
                        Text = page.Description
                    }.With(t =>
                    {
                        t.AddText(page.Description, s =>
                        {
                            s.Font = FrameworkFont.Regular.With(size: 16);
                            s.Colour = UITheme.TextSecondary;
                        });
                    })
                }
            });

            // Update navigation
            backButton.Enabled.Value = currentPage > 0;
            backButton.Alpha = currentPage > 0 ? 1f : 0.3f;

            bool isLastPage = currentPage == pages.Count - 1;
            nextButton.Text = isLastPage ? "Get Started" : "Next";

            // Update dots
            updateDots();
        }

        private void updateDots()
        {
            for (int i = 0; i < dotsContainer.Count; i++)
            {
                if (dotsContainer[i] is PageDot dot)
                    dot.SetActive(i == currentPage);
            }
        }

        private void previousPage()
        {
            if (currentPage > 0)
                showPage(currentPage - 1);
        }

        private void nextPage()
        {
            if (currentPage < pages.Count - 1)
                showPage(currentPage + 1);
            else
                completeOnboarding();
        }

        private void completeOnboarding()
        {
            hasCompletedOnboarding.Value = true;
            onboardingVersion.Value = current_onboarding_version;

            this.FadeOut(300, Easing.OutQuad).Expire();
            OnComplete?.Invoke();
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            switch (e.Key)
            {
                case osuTK.Input.Key.Left:
                    previousPage();
                    return true;

                case osuTK.Input.Key.Right:
                case osuTK.Input.Key.Space:
                case osuTK.Input.Key.Enter:
                    nextPage();
                    return true;

                case osuTK.Input.Key.Escape:
                    completeOnboarding();
                    return true;
            }

            return base.OnKeyDown(e);
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            this.FadeInFromZero(400, Easing.OutQuad);
        }

        /// <summary>
        /// Data for a single onboarding page.
        /// </summary>
        private class OnboardingPage
        {
            public string Title { get; init; } = "";
            public string Description { get; init; } = "";
            public IconUsage Icon { get; init; }
        }

        /// <summary>
        /// A dot indicator for page navigation.
        /// </summary>
        private partial class PageDot : CompositeDrawable
        {
            private Box background = null!;
            private bool isActive;

            public Action? Action;

            public PageDot(bool active)
            {
                isActive = active;
                Size = new Vector2(10);
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                Masking = true;
                CornerRadius = 5;

                InternalChild = background = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = isActive ? UITheme.AccentPrimary : Color4.Gray
                };
            }

            public void SetActive(bool active)
            {
                isActive = active;
                background.FadeColour(active ? UITheme.AccentPrimary : Color4.Gray, 200);
                this.ResizeTo(new Vector2(active ? 12 : 10), 200, Easing.OutQuad);
            }

            protected override bool OnHover(HoverEvent e)
            {
                if (!isActive)
                    background.FadeColour(Color4.LightGray, 100);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                if (!isActive)
                    background.FadeColour(Color4.Gray, 100);
                base.OnHoverLost(e);
            }

            protected override bool OnClick(ClickEvent e)
            {
                Action?.Invoke();
                return true;
            }
        }
    }
}
