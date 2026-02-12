using System.Linq;
using BeatSight.Game.Screens.Editor;
using Xunit;

namespace BeatSight.Tests
{
    public class EditorCopyProfileTests
    {
        [Fact]
        public void ActiveInspectorProfileMatchesConfiguredTone()
        {
            var expected = EditorInspectorCopy.Resolve(EditorInspectorCopy.ActiveTone);
            var active = EditorInspectorCopy.Active;

            Assert.Equal(expected, active);
            Assert.False(string.IsNullOrWhiteSpace(active.SectionMetadata));
            Assert.False(string.IsNullOrWhiteSpace(active.SelectionButton));
            Assert.False(string.IsNullOrWhiteSpace(active.ShortcutHint));
        }

        [Fact]
        public void UltraShortInspectorProfileUsesShorterLabels()
        {
            var clear = EditorInspectorCopy.Resolve(EditorUiCopyTone.Clear);
            var compact = EditorInspectorCopy.Resolve(EditorUiCopyTone.UltraShort);

            Assert.True(compact.SectionMetadata.Length <= clear.SectionMetadata.Length);
            Assert.True(compact.SectionAi.Length <= clear.SectionAi.Length);
            Assert.True(compact.SelectionButton.Length <= clear.SelectionButton.Length);
            Assert.True(compact.DuplicateButton.Length <= clear.DuplicateButton.Length);
            Assert.True(compact.DeleteButton.Length <= clear.DeleteButton.Length);
        }

        [Fact]
        public void SectionOrderSwitchesToEditFirstInCompactMode()
        {
            var full = EditorInspectorCopy.GetSectionOrder(compact: false);
            var compact = EditorInspectorCopy.GetSectionOrder(compact: true);

            Assert.Equal(EditorInspectorSectionKey.Metadata, full[0]);
            Assert.Equal(EditorInspectorSectionKey.Edit, compact[0]);
            Assert.Equal(EditorInspectorSectionKey.Metadata, compact[^1]);
            Assert.Equal(full.Length, compact.Length);
            Assert.Equal(compact.Length, compact.Distinct().Count());
        }

        [Fact]
        public void TimelineCopyTracksInspectorTone()
        {
            var clear = EditorTimelineCopy.Resolve(EditorUiCopyTone.Clear);
            var shortCopy = EditorTimelineCopy.Resolve(EditorUiCopyTone.UltraShort);
            var active = EditorTimelineCopy.Active;

            Assert.Equal(EditorTimelineCopy.Resolve(EditorInspectorCopy.ActiveTone), active);
            Assert.True(shortCopy.SectionZoom.Length <= clear.SectionZoom.Length);
            Assert.True(shortCopy.SnapSelectionButton.Length <= clear.SnapSelectionButton.Length);
            Assert.True(shortCopy.RegenerateButton.Length <= clear.RegenerateButton.Length);
        }
    }
}
