using System;
using System.Collections.Generic;

namespace BeatSight.Game.Services.Generation
{
    /// <summary>
    /// High level pipeline stages surfaced to the UI to allow weighted progress reporting.
    /// </summary>
    public enum GenerationStageId
    {
        ModelLoad,
        Separation,
        OnsetDetection,
        TempoGrid,
        DraftMapping,
        Finalise
    }

    public static class GenerationStagePlan
    {
        public static readonly IReadOnlyList<GenerationStageId> OrderedStages = new[]
        {
            GenerationStageId.ModelLoad,
            GenerationStageId.Separation,
            GenerationStageId.OnsetDetection,
            GenerationStageId.TempoGrid,
            GenerationStageId.DraftMapping,
            GenerationStageId.Finalise
        };

        /// <summary>
        /// Stage weights must add up to 1.0 for the weighted progress bar.
        /// </summary>
        public static readonly IReadOnlyDictionary<GenerationStageId, double> StageWeights = new Dictionary<GenerationStageId, double>
        {
            { GenerationStageId.ModelLoad, 0.05 },
            { GenerationStageId.Separation, 0.35 },
            { GenerationStageId.OnsetDetection, 0.20 },
            { GenerationStageId.TempoGrid, 0.10 },
            { GenerationStageId.DraftMapping, 0.25 },
            { GenerationStageId.Finalise, 0.05 }
        };

        /// <summary>
        /// Provides human readable labels for stage display in the UI.
        /// </summary>
        public static readonly IReadOnlyDictionary<GenerationStageId, string> StageLabels = new Dictionary<GenerationStageId, string>
        {
            { GenerationStageId.ModelLoad, "Model Load (Demucs)" },
            { GenerationStageId.Separation, "Separation" },
            { GenerationStageId.OnsetDetection, "Onset & Peak Detection" },
            { GenerationStageId.TempoGrid, "Tempo & Grid" },
            { GenerationStageId.DraftMapping, "Draft Mapping" },
            { GenerationStageId.Finalise, "Finalising" }
        };

        public static string GetLabel(GenerationStageId stage) =>
            StageLabels.TryGetValue(stage, out var label) ? label : stage.ToString();

        public static double ToWeightedProgress(GenerationStageId stage, double stageProgress)
        {
            stageProgress = Math.Clamp(stageProgress, 0, 1);
            double accumulated = 0;

            foreach (var ordered in OrderedStages)
            {
                if (!StageWeights.TryGetValue(ordered, out var weight))
                    continue;

                if (ordered == stage)
                    return Math.Clamp(accumulated + weight * stageProgress, 0, 1);

                accumulated += weight;
            }

            if (StageWeights.TryGetValue(stage, out var stageWeight))
                return Math.Clamp(accumulated + stageWeight * stageProgress, 0, 1);

            return Math.Clamp(stageProgress, 0, 1);
        }
    }
}
