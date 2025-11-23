using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;
using System;

namespace BeatSight.Game.UI.Components
{
    public partial class FpsCounter : CompositeDrawable
    {
        private SpriteText fpsText = null!;
        private int frameCount;
        private double elapsed;

        public FpsCounter()
        {
            Anchor = Anchor.TopRight;
            Origin = Anchor.TopRight;
            Margin = new MarginPadding { Top = 10, Right = 10 };
            AutoSizeAxes = Axes.Both;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChildren = new Drawable[]
            {
                new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 8,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = UITheme.Surface.Opacity(0.9f)
                        },
                        new Container
                        {
                            AutoSizeAxes = Axes.Both,
                            Padding = new MarginPadding { Horizontal = 12, Vertical = 8 },
                            Children = new Drawable[]
                            {
                                fpsText = new BeatSightSpriteText
                                {
                                    Text = "FPS: --",
                                    Font = BeatSightFont.Body(14),
                                    Colour = UITheme.TextPrimary,
                                    Anchor = Anchor.Centre,
                                    Origin = Anchor.Centre,
                                }
                            }
                        }
                    }
                }
            };
        }

        protected override void Update()
        {
            base.Update();

            frameCount++;
            elapsed += Clock.ElapsedFrameTime;

            if (elapsed >= 250) // Update every 250ms for snappier feel
            {
                int fps = (int)(frameCount / (elapsed / 1000));
                fpsText.Text = $"{fps} FPS";

                // Color code based on performance
                if (fps >= 60)
                    fpsText.Colour = UITheme.AccentSuccess;
                else if (fps >= 30)
                    fpsText.Colour = UITheme.AccentWarning;
                else
                    fpsText.Colour = UITheme.AccentError;

                frameCount = 0;
                elapsed = 0;
            }
        }
    }
}
