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
            endPlaybackZoomInteraction();
            endTimelineZoomInteraction();
            endWaveformScaleInteraction();
            uiAudio.PlayBack();
            stopPlayback(silent: true);
            stopEditorMetronomeChannels();
            disposeTrack();
            return base.OnExiting(e);
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);
            stopEditorMetronomeChannels();
            disposeTrack();
            storageTrackStore?.Dispose();
            storageTrackStore = null;
            storageSampleStore?.Dispose();
            storageSampleStore = null;
            storageResourceStore?.Dispose();
            storageResourceStore = null;
            embeddedSampleStore?.Dispose();
            embeddedSampleStore = null;
            embeddedResourceStore?.Dispose();
            embeddedResourceStore = null;
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
