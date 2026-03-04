namespace BeatSight.Tests.VisualRegression
{
    internal enum VisualScene
    {
        Intro,
        MainMenu,
        SongSelect,
        SongSelectEditor,
        Settings,
        Recording,
        Onboarding,
        AudioImportLoading,
        MappingChoice,
        MetadataChoice,
        MappingGeneration,
        Editor,
        Playback,
        EditorTwoDimensional,
        PlaybackTwoDimensional,
        EditorManuscript,
        PlaybackManuscript
    }

    internal readonly record struct VisualResolution(string Name, int Width, int Height)
    {
        public override string ToString() => $"{Name} ({Width}x{Height})";
    }

    internal static class VisualSnapshotCatalog
    {
        internal static readonly VisualResolution[] Resolutions =
        {
            new("720p", 1280, 720),
            new("1080p", 1920, 1080),
            new("1440p", 2560, 1440),
            new("ultrawide", 3440, 1440),
        };

        internal static readonly VisualScene[] Scenes =
        {
            VisualScene.Intro,
            VisualScene.MainMenu,
            VisualScene.SongSelect,
            VisualScene.SongSelectEditor,
            VisualScene.Settings,
            VisualScene.Recording,
            VisualScene.Onboarding,
            VisualScene.AudioImportLoading,
            VisualScene.MappingChoice,
            VisualScene.MetadataChoice,
            VisualScene.MappingGeneration,
            VisualScene.Editor,
            VisualScene.Playback,
            VisualScene.EditorTwoDimensional,
            VisualScene.PlaybackTwoDimensional,
            VisualScene.EditorManuscript,
            VisualScene.PlaybackManuscript
        };
    }
}
