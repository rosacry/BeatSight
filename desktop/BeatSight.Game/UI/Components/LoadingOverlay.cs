using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;
using BeatSight.Game.UI.Theming;
using osu.Framework.Extensions.Color4Extensions;

namespace BeatSight.Game.UI.Components
{
    public partial class LoadingOverlay : VisibilityContainer
    {
        private readonly Container content;
        private readonly CircularContainer ring1;
        private readonly CircularContainer ring2;
        private readonly CircularContainer core;
        private readonly BeatSightSpriteText text;

        public LoadingOverlay()
        {
            RelativeSizeAxes = Axes.Both;
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;
            Alpha = 0;

            Children = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4Extensions.Opacity(Color4.Black, 0.9f),
                },
                content = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Children = new Drawable[]
                    {
                        // Outer Ring
                        ring1 = new CircularContainer
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Size = new Vector2(120),
                            Masking = true,
                            BorderThickness = 3,
                            BorderColour = UITheme.AccentPrimary,
                            Child = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Alpha = 0,
                                AlwaysPresent = true
                            }
                        },
                        // Inner Ring
                        ring2 = new CircularContainer
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Size = new Vector2(80),
                            Masking = true,
                            BorderThickness = 3,
                            BorderColour = UITheme.AccentSecondary,
                            Child = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Alpha = 0,
                                AlwaysPresent = true
                            }
                        },
                        // Core Pulse
                        core = new CircularContainer
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Size = new Vector2(40),
                            Masking = true,
                            Child = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = Color4.White
                            }
                        },
                        text = new BeatSightSpriteText
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Text = "LOADING BEATMAP",
                            Font = BeatSightFont.Section(size: 24),
                            Colour = Color4.White,
                            Y = 100,
                            Alpha = 0.8f
                        }
                    }
                }
            };
        }

        protected override void PopIn()
        {
            this.FadeIn(300, Easing.OutQuint);

            // Reset transforms
            ring1.ClearTransforms();
            ring2.ClearTransforms();
            core.ClearTransforms();
            text.ClearTransforms();

            // Animations
            ring1.ScaleTo(0.9f).Then().ScaleTo(1.1f, 1500, Easing.InOutSine).Loop();
            ring1.RotateTo(0).RotateTo(360, 3000, Easing.InOutSine).Loop();

            ring2.ScaleTo(1.1f).Then().ScaleTo(0.9f, 1500, Easing.InOutSine).Loop();
            ring2.RotateTo(360).RotateTo(0, 2000, Easing.InOutSine).Loop();

            core.ScaleTo(0.8f).Then().ScaleTo(1.2f, 500, Easing.OutQuint).Then().ScaleTo(0.8f, 500, Easing.InQuint).Loop();
            core.FadeTo(0.5f).Then().FadeTo(1f, 500, Easing.OutQuint).Then().FadeTo(0.5f, 500, Easing.InQuint).Loop();

            text.FadeInFromZero(500).Then().FadeTo(0.5f, 800, Easing.InOutSine).Loop();
        }

        protected override void PopOut()
        {
            this.FadeOut(300, Easing.OutQuint);
        }
    }
}
