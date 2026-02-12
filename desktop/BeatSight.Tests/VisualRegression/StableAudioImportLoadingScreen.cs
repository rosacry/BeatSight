using BeatSight.Game.Screens.Mapping;

namespace BeatSight.Tests.VisualRegression
{
    /// <summary>
    /// Test-only deterministic variant of AudioImportLoadingScreen.
    /// Uses the real loading UI while disabling async import side effects.
    /// </summary>
    internal sealed partial class StableAudioImportLoadingScreen : AudioImportLoadingScreen
    {
        internal StableAudioImportLoadingScreen(string sourcePath)
            : base(sourcePath, autoStartImport: false)
        {
        }
    }
}
