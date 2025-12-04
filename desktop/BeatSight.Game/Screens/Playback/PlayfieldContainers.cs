// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from PlaybackScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.3

using System;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback
{
    /// <summary>
    /// Container for the playfield viewport with responsive padding and stage surface styling.
    /// Provides shadow effects and rounded corners for the playfield area.
    /// </summary>
    public partial class PlayfieldViewportContainer : Container
    {
        private readonly Container stagePadding;
        private MarginPadding cachedPadding;

        public PlayfieldViewportContainer(Drawable playfield)
        {
            RelativeSizeAxes = Axes.Both;

            var stageSurface = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 28,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = new Color4(0, 0, 0, 40),
                    Radius = 32,
                    Roundness = 1f
                },
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(10, 12, 20, 255)
                    },
                    playfield
                }
            };

            stagePadding = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Horizontal = 40, Vertical = 20 },
                    Child = stageSurface
                }
            };

            InternalChild = stagePadding;
        }

        protected override void Update()
        {
            base.Update();

            if (DrawWidth <= 0 || DrawHeight <= 0)
                return;

            float horizontal = Math.Clamp(DrawWidth * 0.01f, 8f, 60f);
            float vertical = Math.Clamp(DrawHeight * 0.015f, 8f, 60f);
            var targetPadding = new MarginPadding
            {
                Left = horizontal,
                Right = horizontal,
                Top = vertical,
                Bottom = vertical + 20
            };

            if (!cachedPadding.Equals(targetPadding))
            {
                stagePadding.Padding = targetPadding;
                cachedPadding = targetPadding;
            }
        }
    }

    /// <summary>
    /// Responsive container for playfield content with dynamic padding based on window size.
    /// Provides optimal spacing for the playfield area.
    /// </summary>
    public partial class ResponsivePlayfieldContainer : Container
    {
        private readonly Drawable playfieldContent;
        private MarginPadding cachedPadding;

        public ResponsivePlayfieldContainer(Drawable content)
        {
            RelativeSizeAxes = Axes.Both;
            playfieldContent = content;
            Child = playfieldContent;
        }

        protected override void Update()
        {
            base.Update();

            if (DrawWidth <= 0 || DrawHeight <= 0)
                return;

            // Dynamically calculate padding based on window size
            float horizontalPadding = Math.Clamp(DrawWidth * 0.03f, 20f, 50f);
            float topPadding = Math.Clamp(DrawHeight * 0.005f, 2f, 8f); // Reduced to minimize whitespace

            // Reduced bottom padding to allow playfield to extend further down
            float bottomPadding = 40f;

            var targetPadding = new MarginPadding
            {
                Left = horizontalPadding,
                Right = horizontalPadding,
                Top = topPadding,
                Bottom = bottomPadding
            };

            // Only update if padding actually changed (avoid constant recalculation)
            if (!cachedPadding.Equals(targetPadding))
            {
                Padding = targetPadding;
                cachedPadding = targetPadding;
            }
        }
    }
}
