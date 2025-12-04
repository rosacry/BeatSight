// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from PlaybackScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.3

using System;
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
        private const float PEEK_HEIGHT = 50f;
        private bool initialLayoutDone = false;

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

            // Initial layout snap
            if (!initialLayoutDone && DrawHeight > PEEK_HEIGHT)
            {
                initialLayoutDone = true;
                if (!IsHovered)
                {
                    float hideOffset = Math.Max(0, DrawHeight - PEEK_HEIGHT);
                    this.Y = hideOffset;
                    this.FadeTo(0f, 500, Easing.OutQuint);
                }
            }
        }

        protected override bool OnHover(HoverEvent e)
        {
            // Ensure we start from the hidden position if this is the first interaction
            if (!initialLayoutDone && DrawHeight > PEEK_HEIGHT)
            {
                initialLayoutDone = true;
                float hideOffset = Math.Max(0, DrawHeight - PEEK_HEIGHT);
                this.Y = hideOffset;
            }

            this.FadeIn(200, Easing.OutQuint);
            this.MoveToY(0, 200, Easing.OutQuint);
            return true;
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            float hideOffset = Math.Max(0, DrawHeight - PEEK_HEIGHT);
            this.MoveToY(hideOffset, 500, Easing.OutQuint);
            this.FadeTo(0.6f, 500, Easing.OutQuint);
        }
    }
}
