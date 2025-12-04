// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from PlaybackScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.3

using System;
using BeatSight.Game.UI.Components;
using osu.Framework.Input.Events;

namespace BeatSight.Game.Screens.Playback
{
    /// <summary>
    /// Slider bar that reports when the user is actively scrubbing (dragging).
    /// Used for timeline seeking to differentiate between user interaction and programmatic updates.
    /// </summary>
    public partial class ScrubbableSliderBar : BeatSightSliderBar
    {
        /// <summary>
        /// Fired when the scrubbing state changes.
        /// True when user starts dragging, false when they release.
        /// </summary>
        public event Action<bool>? ScrubbingChanged;

        private bool scrubbing;

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            setScrubbing(true);
            var handled = base.OnMouseDown(e);
            if (!handled)
                setScrubbing(false);
            return handled;
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            base.OnMouseUp(e);
            setScrubbing(false);
        }

        protected override bool OnDragStart(DragStartEvent e)
        {
            var handled = base.OnDragStart(e);
            if (handled)
                setScrubbing(true);
            return handled;
        }

        protected override void OnDragEnd(DragEndEvent e)
        {
            base.OnDragEnd(e);
            setScrubbing(false);
        }

        private void setScrubbing(bool value)
        {
            if (scrubbing == value)
                return;

            scrubbing = value;
            ScrubbingChanged?.Invoke(value);
        }
    }
}
