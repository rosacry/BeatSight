using System;
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
        private Container dialogContainer = null!;
        private NonInteractiveContainer previewMonitor = null!;
        private BeatSightButton doneButton = null!;
        private float lastDialogPadding = -1;
        private float lastPreviewWidth = -1;

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager config)
        {
            uiScale = config.GetBindable<double>(BeatSightSetting.UIScale);

            RelativeSizeAxes = Axes.Both;

            previewMonitor = new NonInteractiveContainer
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
            };

            Children = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(0, 0, 0, 0.8f)
                },
                dialogContainer = new Container
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
                                    Width = DesignSystem.SliderWidth,
                                    Height = DesignSystem.ControlHeight,
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
                                previewMonitor,
                                scaleText = new SpriteText
                                {
                                    Font = BeatSightFont.Body(24),
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                doneButton = new BeatSightButton
                                {
                                    Text = "Done",
                                    Width = 100,
                                    Height = DesignSystem.ButtonHeight,
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
                float scale = (float)e.NewValue * 1.15f;
                if (scale < 0.1f) scale = 0.1f;
                previewScaler.Scale = new Vector2(scale);
            }, true);

            applyResponsiveLayout(force: true);
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

        protected override void Update()
        {
            base.Update();
            applyResponsiveLayout();
        }

        private void applyResponsiveLayout(bool force = false)
        {
            if (DrawWidth <= 0 || DrawHeight <= 0 || dialogContainer == null || previewMonitor == null || doneButton == null)
                return;

            float dialogPadding = ResponsiveLayout.ClampFraction(DrawHeight, 0.045f, 28f, 56f);
            float previewWidth = ResponsiveLayout.ClampFraction(DrawWidth, 0.34f, 420f, 780f);
            float previewHeight = MathF.Round(previewWidth * 9f / 16f);
            float buttonHeight = ResponsiveLayout.ClampFraction(DrawHeight, 0.04f, 34f, 46f);

            if (force || Math.Abs(dialogPadding - lastDialogPadding) > 0.2f)
            {
                if (dialogContainer.Children[1] is FillFlowContainer flow)
                {
                    flow.Padding = new MarginPadding(dialogPadding);
                }
                lastDialogPadding = dialogPadding;
            }

            if (force || Math.Abs(previewWidth - lastPreviewWidth) > 0.2f)
            {
                previewMonitor.Width = previewWidth;
                previewMonitor.Height = previewHeight;
                doneButton.Width = ResponsiveLayout.ClampFraction(previewWidth, 0.18f, 92f, 160f);
                doneButton.Height = buttonHeight;
                doneButton.FontSize = Math.Clamp(buttonHeight * 0.40f, 13f, 18f);
                lastPreviewWidth = previewWidth;
            }
        }

        private partial class NonInteractiveContainer : Container
        {
            public override bool HandlePositionalInput => false;
            public override bool HandleNonPositionalInput => false;
        }
    }
}
