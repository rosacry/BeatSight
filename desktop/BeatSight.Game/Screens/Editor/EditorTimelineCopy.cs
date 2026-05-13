namespace BeatSight.Game.Screens.Editor
{
    internal readonly record struct EditorTimelineCopyProfile(
        string SectionZoom,
        string SectionWaveform,
        string SectionPlayback,
        string SectionPlaybackZoom,
        string SectionNoteWidth,
        string SectionSnap,
        string SectionOverlay,
        string SectionTools,
        string BeatGridLabel,
        string LinkZoomLabel,
        string DrumStemLabel,
        string FirstNoteButton,
        string LastNoteButton,
        string SnapSelectionButton,
        string RegenerateButton);

    internal static class EditorTimelineCopy
    {
        internal static EditorTimelineCopyProfile Active => Resolve(EditorInspectorCopy.ActiveTone);

        private static readonly EditorTimelineCopyProfile clearProfile = new(
            SectionZoom: "Timeline Zoom",
            SectionWaveform: "Waveform",
            SectionPlayback: "Playback Speed",
            SectionPlaybackZoom: "Playback Zoom",
            SectionNoteWidth: "Note Width",
            SectionSnap: "Snap",
            SectionOverlay: "Overlay",
            SectionTools: "Tools",
            BeatGridLabel: "Beat Grid",
            LinkZoomLabel: "Link Zoom",
            DrumStemLabel: "Drums",
            FirstNoteButton: "First Note",
            LastNoteButton: "Last Note",
            SnapSelectionButton: "Snap Audio",
            RegenerateButton: "Regenerate");

        private static readonly EditorTimelineCopyProfile ultraShortProfile = new(
            SectionZoom: "Zoom",
            SectionWaveform: "Wave",
            SectionPlayback: "Speed",
            SectionPlaybackZoom: "Zoom",
            SectionNoteWidth: "Width",
            SectionSnap: "Snap",
            SectionOverlay: "Grid",
            SectionTools: "Tools",
            BeatGridLabel: "Grid",
            LinkZoomLabel: "Link",
            DrumStemLabel: "Drums",
            FirstNoteButton: "First",
            LastNoteButton: "Last",
            SnapSelectionButton: "Snap",
            RegenerateButton: "Regen");

        internal static EditorTimelineCopyProfile Resolve(EditorUiCopyTone tone)
            => tone == EditorUiCopyTone.UltraShort ? ultraShortProfile : clearProfile;
    }
}
