using osu.Framework.Localisation;

namespace BeatSight.Game.Localization
{
    /// <summary>
    /// Centralises user-facing strings to facilitate future localisation efforts.
    /// </summary>
    public static class BeatSightStrings
    {
        public static LocalisableString GenerationReady => "AI draft ready!";
        public static LocalisableString GenerationFailed => "Generation failed.";
        public static LocalisableString GenerationCancelled => "Generation cancelled.";
        public static LocalisableString GenerationCancelledSummary => "No draft was created.";
        public static LocalisableString UnknownGenerationError => "An unknown error occurred.";
        public static LocalisableString OfflinePlaybackDisabled => "Playback disabled (offline decode)";
    }
}