namespace BeatSight.Game.Screens.Editor
{
    internal enum EditorUiCopyTone
    {
        Clear,
        UltraShort
    }

    internal enum EditorInspectorSectionKey
    {
        Metadata,
        Edit,
        Stats,
        Ai
    }

    internal readonly record struct EditorInspectorCopyProfile(
        string SectionMetadata,
        string SectionEdit,
        string SectionStats,
        string SectionAi,
        string LabelRelease,
        string LabelProvider,
        string LabelDescription,
        string LabelTempoHints,
        string SelectionButton,
        string QuantizeButton,
        string DuplicateButton,
        string DeleteButton,
        string ReassignApplyButton,
        string ShortcutHint,
        string PlaceholderRelease,
        string PlaceholderProvider,
        string PlaceholderDescription,
        string PlaceholderBpm,
        string PlaceholderOffset,
        string PlaceholderTempoHints,
        string SelectionNoneText);

    internal static class EditorInspectorCopy
    {
        // Switch between concise and ultra-short labeling without touching EditorScreen wiring.
        internal const EditorUiCopyTone ActiveTone = EditorUiCopyTone.Clear;

        internal static EditorInspectorCopyProfile Active => Resolve(ActiveTone);

        private static readonly EditorInspectorCopyProfile clearProfile = new(
            SectionMetadata: "Beatmap",
            SectionEdit: "Edit",
            SectionStats: "Stats",
            SectionAi: "AI Tools",
            LabelRelease: "Release",
            LabelProvider: "Provider",
            LabelDescription: "Notes",
            LabelTempoHints: "Tempo",
            SelectionButton: "Select All",
            QuantizeButton: "Quantize",
            DuplicateButton: "Duplicate",
            DeleteButton: "Delete",
            ReassignApplyButton: "Apply",
            ShortcutHint: "Ctrl+A all | Q quantize | Alt+Arrows nudge | 1-9 quick reassign",
            PlaceholderRelease: "YYYY-MM-DD",
            PlaceholderProvider: "Mapping Group",
            PlaceholderDescription: "Mapper notes",
            PlaceholderBpm: "174",
            PlaceholderOffset: "0",
            PlaceholderTempoHints: "120, 140",
            SelectionNoneText: "No selection");

        private static readonly EditorInspectorCopyProfile ultraShortProfile = new(
            SectionMetadata: "Meta",
            SectionEdit: "Edit",
            SectionStats: "Stats",
            SectionAi: "AI",
            LabelRelease: "Release",
            LabelProvider: "Provider",
            LabelDescription: "Notes",
            LabelTempoHints: "Tempo",
            SelectionButton: "All",
            QuantizeButton: "Quantize",
            DuplicateButton: "Dup",
            DeleteButton: "Del",
            ReassignApplyButton: "Apply",
            ShortcutHint: "Ctrl+A | Q | Alt+Arrows | 1-9",
            PlaceholderRelease: "YYYY-MM-DD",
            PlaceholderProvider: "Group",
            PlaceholderDescription: "Notes",
            PlaceholderBpm: "174",
            PlaceholderOffset: "0",
            PlaceholderTempoHints: "120, 140",
            SelectionNoneText: "No selection");

        internal static EditorInspectorCopyProfile Resolve(EditorUiCopyTone tone)
            => tone == EditorUiCopyTone.UltraShort ? ultraShortProfile : clearProfile;

        internal static EditorInspectorSectionKey[] GetSectionOrder(bool compact)
        {
            if (!compact)
            {
                return new[]
                {
                    EditorInspectorSectionKey.Metadata,
                    EditorInspectorSectionKey.Edit,
                    EditorInspectorSectionKey.Stats,
                    EditorInspectorSectionKey.Ai
                };
            }

            return new[]
            {
                EditorInspectorSectionKey.Edit,
                EditorInspectorSectionKey.Ai,
                EditorInspectorSectionKey.Stats,
                EditorInspectorSectionKey.Metadata
            };
        }
    }
}
