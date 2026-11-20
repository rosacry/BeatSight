// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from PlaybackScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.3

using System;
using System.Linq;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Input.Events;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback
{
    /// <summary>
    /// Bottom toolbar container that slides up on hover and partially hides when not interacted with.
    /// Provides responsive padding and smooth animation for playback controls.
    /// </summary>
    public partial class PlaybackToolbarContainer : Container
    {
        private MarginPadding cachedPadding;
        private bool initialLayoutDone = false;

        /// <summary>Visible height while tucked away: the transport/progress row stays on screen.</summary>
        public float PeekHeight { get; set; } = 64f;

        private const float tucked_alpha = 0.92f;

        public PlaybackToolbarContainer()
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;
            AlwaysPresent = true;
            Alpha = 0f; // Start invisible to prevent flash
        }

        protected override void Update()
        {
            base.Update();

            if (Parent == null || Parent.DrawWidth <= 0)
                return;

            // Responsive horizontal padding (scales with width, but has limits)
            float horizontalPadding = Math.Clamp(Parent.DrawWidth * 0.03f, 20f, 50f);

            var targetPadding = new MarginPadding
            {
                Left = horizontalPadding,
                Right = horizontalPadding,
                Bottom = 20
            };

            if (!cachedPadding.Equals(targetPadding))
            {
                Padding = targetPadding;
                cachedPadding = targetPadding;
            }

            // Keep the tucked position in step with the real height: the toolbar's content finishes laying out over
            // several frames, so an offset computed once on the first frame left most of it covering the highway.
            float hideOffset = Math.Max(0, DrawHeight - PeekHeight);
            if (!expanded && DrawHeight > PeekHeight)
            {
                if (!initialLayoutDone)
                {
                    initialLayoutDone = true;
                    // Start tucked, not invisible: progress and play/pause should be visible without hunting.
                    this.FadeTo(tucked_alpha, 300, Easing.OutQuint);
                }

                if (Math.Abs(Y - hideOffset) > 0.5f && !isAnimatingPosition)
                    Y = hideOffset;
            }
        }

        private bool expanded;
        private bool isAnimatingPosition => Transforms.Any(t => t.TargetMember == nameof(Y));

        public bool Expanded => expanded;

        /// <summary>
        /// Expands the full toolbar or tucks it to the peek strip. Hover drives this in normal use; visual capture
        /// calls it directly so screenshots never depend on where the real mouse cursor happens to be.
        /// </summary>
        public void SetExpanded(bool value, bool animate = true)
        {
            expanded = value;
            initialLayoutDone = true;
            ClearTransforms();

            float targetY = value ? 0 : Math.Max(0, DrawHeight - PeekHeight);
            float targetAlpha = value ? 1f : tucked_alpha;
            double duration = animate ? (value ? 220 : 360) : 0;

            this.MoveToY(targetY, duration, Easing.OutQuint);
            this.FadeTo(targetAlpha, duration, Easing.OutQuint);
        }

        /// <summary>When false, hover no longer expands the toolbar (used by visual capture for determinism).</summary>
        public bool ExpandOnHover { get; set; } = true;

        protected override bool OnHover(HoverEvent e)
        {
            if (ExpandOnHover)
                SetExpanded(true);
            return true;
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            if (ExpandOnHover)
                SetExpanded(false);
        }
    }
}
