using System;

namespace BeatSight.Game.AI.Generation
{
    /// <summary>
    /// Provides an explicit tempo override that can be applied to the AI generation options.
    /// </summary>
    public readonly record struct TempoOverride(
        double Bpm,
        double OffsetSeconds,
        double StepSeconds,
        bool ForceQuantization)
    {
        /// <summary>
        /// Applies this override to the given AI generation options.
        /// </summary>
        /// <param name="options">The options instance that will receive the override values.</param>
        /// <exception cref="ArgumentNullException">Thrown when <paramref name="options"/> is null.</exception>
        public void ApplyTo(AI.AiGenerationOptions options)
        {
            if (options == null)
                throw new ArgumentNullException(nameof(options));

            options.ForcedBpm = Bpm;
            options.ForcedOffsetSeconds = OffsetSeconds;
            options.ForcedStepSeconds = StepSeconds;
            options.ForceQuantization = ForceQuantization;
        }
    }
}