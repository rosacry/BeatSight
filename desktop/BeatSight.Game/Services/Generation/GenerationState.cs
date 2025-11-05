using System;

namespace BeatSight.Game.Services.Generation
{
    /// <summary>
    /// High-level UI state for the AI generation workflow.
    /// This abstracts pipeline phases into user-facing lifecycle states.
    /// </summary>
    public enum GenerationState
    {
        Idle,
        Preparing,
        LoadingDemucs,
        SeparatingStems,
        DetectingOnsets,
        EstimatingTempo,
        DraftingNotes,
        Finalizing,
        Complete,
        Cancelled,
        Error
    }

    public static class GenerationStateExtensions
    {
        public static bool IsActive(this GenerationState state) => state switch
        {
            GenerationState.Idle => false,
            GenerationState.Complete => false,
            GenerationState.Cancelled => false,
            GenerationState.Error => false,
            _ => true
        };

        public static bool AllowsOverlay(this GenerationState state) => state >= GenerationState.DetectingOnsets && state != GenerationState.Error;

        public static string ToDisplayString(this GenerationState state) => state switch
        {
            GenerationState.Idle => "Idle",
            GenerationState.Preparing => "Preparing audio",
            GenerationState.LoadingDemucs => "Loading Demucs",
            GenerationState.SeparatingStems => "Separating stems",
            GenerationState.DetectingOnsets => "Detecting onsets",
            GenerationState.EstimatingTempo => "Estimating tempo",
            GenerationState.DraftingNotes => "Drafting notes",
            GenerationState.Finalizing => "Finalising",
            GenerationState.Complete => "Complete",
            GenerationState.Cancelled => "Cancelled",
            GenerationState.Error => "Error",
            _ => state.ToString()
        };
    }
}
