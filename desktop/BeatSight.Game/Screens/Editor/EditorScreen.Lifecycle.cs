using BeatSight.Game.UI.Components;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Input.Events;
using osu.Framework.Screens;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        public override bool OnExiting(ScreenExitEvent e)
        {
            endTimelineZoomInteraction();
            endWaveformScaleInteraction();
            uiAudio.PlayBack();
            stopPlayback(silent: true);
            disposeTrack();
            return base.OnExiting(e);
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);
            disposeTrack();
            storageTrackStore?.Dispose();
            storageTrackStore = null;
            storageResourceStore?.Dispose();
            storageResourceStore = null;
        }

        private partial class PassiveScrollContainer : BeatSightScrollContainer
        {
            public PassiveScrollContainer(Direction direction = Direction.Vertical)
                : base(direction)
            {
            }

            protected override bool OnDragStart(DragStartEvent e) => false;

            protected override void OnDrag(DragEvent e)
            {
            }
        }
    }
}
