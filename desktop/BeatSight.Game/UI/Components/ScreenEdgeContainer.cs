using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;

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
        private readonly BasicScrollContainer? scrollContainer;

        public ScreenEdgeContainer(bool scrollable = true, Direction scrollDirection = Direction.Vertical)
        {
            RelativeSizeAxes = Axes.Both;

            safeArea = new SafeAreaContainer
            {
                RelativeSizeAxes = Axes.Both,
                Padding = UITheme.ScreenPadding
            };

            contentContainer = new Container
            {
                RelativeSizeAxes = scrollable ? Axes.X : Axes.Both,
                AutoSizeAxes = scrollable ? Axes.Y : Axes.None
            };

            if (scrollable)
            {
                scrollContainer = new BasicScrollContainer(scrollDirection)
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
            get => safeArea.Padding;
            set => safeArea.Padding = value;
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
    }
}
