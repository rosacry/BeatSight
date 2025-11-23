using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Extensions.Color4Extensions;
using osuTK;
using osuTK.Graphics;
using BeatSight.Game.Screens;
using BeatSight.Game.Screens.SongSelect;
using BeatSight.Game.Screens.Settings;
using BeatSight.Game.UI;
using osu.Framework.Screens;

namespace BeatSight.Game.UI.Overlays
{
    public partial class UIScaleWizard : OverlayContainer
    {
        private Bindable<double> uiScale = null!;
        private BeatSightSliderBar slider = null!;
        private SpriteText scaleText = null!;
        private Container previewContainer = null!;
        private ScalingContainer previewScaler = null!;

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager config)
        {
            uiScale = config.GetBindable<double>(BeatSightSetting.UIScale);

            RelativeSizeAxes = Axes.Both;

            Children = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(0, 0, 0, 0.8f)
                },
                new Container
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    AutoSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 10,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = UITheme.Surface
                        },
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Padding = new MarginPadding(50),
                            Spacing = new Vector2(0, 20),
                            Children = new Drawable[]
                            {
                                new SpriteText
                                {
                                    Text = "UI Scaling",
                                    Font = BeatSightFont.Title(30),
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                new SpriteText
                                {
                                    Text = "Adjust the slider below to scale the user interface.",
                                    Font = BeatSightFont.Body(20),
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                new Container
                                {
                                    Width = 400,
                                    Height = 40,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Children = new Drawable[]
                                    {
                                        slider = new BeatSightSliderBar
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Current = uiScale,
                                            KeyboardStep = 0.01f,
                                        }
                                    }
                                },
                                new SpriteText
                                {
                                    Text = "Preview Screen",
                                    Font = BeatSightFont.Body(20),
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                new NonInteractiveContainer
                                {
                                    Name = "Preview Monitor",
                                    Width = 640,
                                    Height = 360,
                                    Masking = true,
                                    CornerRadius = 5,
                                    BorderColour = UITheme.AccentPrimary,
                                    BorderThickness = 2,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Children = new Drawable[]
                                    {
                                        new Box
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Colour = Color4.Black
                                        },
                                        new DrawSizePreservingFillContainer
                                        {
                                            TargetDrawSize = new Vector2(1920, 1080),
                                            Strategy = DrawSizePreservationStrategy.Average,
                                            Child = previewScaler = new ScalingContainer
                                            {
                                                RelativeSizeAxes = Axes.None,
                                                Anchor = Anchor.Centre,
                                                Origin = Anchor.Centre,
                                                Child = previewContainer = new Container
                                                {
                                                    RelativeSizeAxes = Axes.Both
                                                }
                                            }
                                        },
                                        new NonInteractiveContainer()
                                    }
                                },
                                scaleText = new SpriteText
                                {
                                    Font = BeatSightFont.Body(24),
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                new BeatSightButton
                                {
                                    Text = "Done",
                                    Width = 100,
                                    Height = 40,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Action = Hide
                                }
                            }
                        }
                    }
                }
            };

            uiScale.BindValueChanged(e =>
            {
                scaleText.Text = $"{e.NewValue:P0}";
                float scale = (float)e.NewValue;
                if (scale < 0.1f) scale = 0.1f;
                previewScaler.Scale = new Vector2(scale);
            }, true);
        }

        private void loadPreview()
        {
            if (previewContainer.Count > 0) return;

            try
            {
                // Use SongSelectScreen for preview as requested.
                var screen = new SongSelectScreen(previewMode: true);
                var stack = new ScreenStack(screen)
                {
                    RelativeSizeAxes = Axes.Both
                };
                previewContainer.Add(stack);
            }
            catch (System.Exception ex)
            {
                // Fallback if screen fails to load
                previewContainer.Add(new SpriteText
                {
                    Text = $"Preview unavailable: {ex.Message}",
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre
                });
            }
        }

        protected override void PopIn()
        {
            loadPreview();
            this.FadeIn(200, Easing.OutQuint);
        }

        protected override void PopOut()
        {
            previewContainer.Clear();
            this.FadeOut(200, Easing.OutQuint);
        }

        private partial class NonInteractiveContainer : Container
        {
            public override bool HandlePositionalInput => false;
            public override bool HandleNonPositionalInput => false;
        }
    }
}
