namespace BeatSight.Game.Screens.Mapping
{
    /// <summary>
    /// Computes button visibility and enabled state for the mapping generation screen.
    /// Extracted for unit testing of the Ready/Running/Finished guard logic.
    /// </summary>
    internal static class GenerationUiStateGuard
    {
        public static GenerationUiControlState Compute(bool isRunning, bool isReady, bool isCompleted, bool hasRunBefore, bool hasPendingChanges, bool hasDraft)
        {
            bool startVisible = !isRunning;
            bool startEnabled = !isRunning;

            bool cancelVisible = isRunning;
            bool cancelEnabled = isRunning;

            bool applyEnabled = !isRunning && hasRunBefore && hasPendingChanges;
            bool applyVisible = applyEnabled && !isReady;

            bool openVisible = !isRunning && isCompleted && hasDraft;
            bool openEnabled = openVisible;

            if (isReady)
            {
                applyVisible = false;
                applyEnabled = false;
                openVisible = false;
                openEnabled = false;
            }

            return new GenerationUiControlState(
                startVisible,
                startEnabled,
                cancelVisible,
                cancelEnabled,
                applyVisible,
                applyEnabled,
                openVisible,
                openEnabled);
        }
    }

    internal readonly record struct GenerationUiControlState(
        bool StartVisible,
        bool StartEnabled,
        bool CancelVisible,
        bool CancelEnabled,
        bool ApplyVisible,
        bool ApplyEnabled,
        bool OpenEditorVisible,
        bool OpenEditorEnabled);
}
