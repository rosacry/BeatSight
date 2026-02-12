using System;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Utils;
using osuTK;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Provides a consistent safe-area padded region for screen contents, optionally enabling scrolling
    /// so long forms do not clip against the window bounds.
    /// </summary>
    public partial class ScreenEdgeContainer : CompositeDrawable
    {
        private readonly SafeAreaContainer safeArea;
        private readonly Container contentContainer;
        private readonly BeatSightScrollContainer? scrollContainer;
        private MarginPadding basePadding;
        private Vector2 lastDrawSize;
        private float lastScale = -1f;

        public ScreenEdgeContainer(bool scrollable = true, Direction scrollDirection = Direction.Vertical)
        {
            RelativeSizeAxes = Axes.Both;
            basePadding = UITheme.ScreenPadding;

            safeArea = new SafeAreaContainer
            {
                RelativeSizeAxes = Axes.Both,
                Padding = basePadding
            };

            contentContainer = new Container
            {
                RelativeSizeAxes = scrollable ? Axes.X : Axes.Both,
                AutoSizeAxes = scrollable ? Axes.Y : Axes.None
            };

            if (scrollable)
            {
                scrollContainer = new BeatSightScrollContainer(scrollDirection)
                {
                    RelativeSizeAxes = Axes.Both,
                    Child = contentContainer
                };

                safeArea.Child = scrollContainer;
            }
            else
            {
                safeArea.Child = contentContainer;
            }

            InternalChild = safeArea;
        }

        /// <summary>
        /// Additional padding to apply on top of the platform safe area.
        /// </summary>
        public MarginPadding EdgePadding
        {
            get => basePadding;
            set
            {
                basePadding = value;
                lastScale = -1f;
                applyResponsivePadding(force: true);
            }
        }

        /// <summary>
        /// Container that hosts screen content. Exposed for callers needing additional layout control.
        /// </summary>
        public Container ContentContainer => contentContainer;

        /// <summary>
        /// Convenience setter for single-child scenarios.
        /// </summary>
        public Drawable? Content
        {
            get => contentContainer.Child;
            set => contentContainer.Child = value;
        }

        protected override void Update()
        {
            base.Update();
            applyResponsivePadding();
        }

        private void applyResponsivePadding(bool force = false)
        {
            if (!force && Precision.AlmostEquals(DrawWidth, lastDrawSize.X) && Precision.AlmostEquals(DrawHeight, lastDrawSize.Y))
                return;

            lastDrawSize = DrawSize;

            float shortAxis = Math.Min(DrawWidth, DrawHeight);
            if (shortAxis <= 0)
                return;

            float scale = Math.Clamp(shortAxis / 1080f, 0.82f, 1.22f);
            if (!force && Math.Abs(scale - lastScale) < 0.001f)
                return;

            lastScale = scale;
            safeArea.Padding = ResponsiveLayout.ScalePadding(basePadding, scale);
        }
    }
}
