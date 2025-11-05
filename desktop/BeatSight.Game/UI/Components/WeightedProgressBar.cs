using System;
using System.Collections.Generic;
using BeatSight.Game.Services.Generation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Transforms;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Displays weighted generation progress based on <see cref="GenerationStagePlan"/>.
    /// Keeps progress monotonically increasing and smooth across stage transitions.
    /// </summary>
    public partial class WeightedProgressBar : CompositeDrawable
    {
        private const double smoothingHalfLifeSeconds = 0.35;
        private const double minRatePerFrame = 0.02;
        private const double maxRatePerFrame = 0.4;

        private readonly Box fill;
        private readonly Box background;
        private readonly Box heartbeatPulse;
        private readonly IReadOnlyDictionary<GenerationStageId, double> stageCaps;

        private double currentValue;
        private double targetValue;
        private double currentStageProgress;

        public WeightedProgressBar()
        {
            RelativeSizeAxes = Axes.X;
            Height = 6;
            Masking = true;
            CornerRadius = 3;

            stageCaps = buildStageCaps();

            InternalChildren = new Drawable[]
            {
                background = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(35, 40, 55, 255)
                },
                fill = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Width = 0,
                    Colour = new Color4(110, 170, 255, 255)
                },
                heartbeatPulse = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Alpha = 0,
                    Colour = new Color4(160, 220, 255, 120)
                }
            };
        }

        public DateTimeOffset? LastUpdate { get; private set; }
        public DateTimeOffset? LastHeartbeat { get; private set; }
        public GenerationStageId CurrentStage { get; private set; } = GenerationStageId.ModelLoad;
        public double CurrentValue => currentValue;
        public double CurrentStageProgress => currentStageProgress;
        public double TargetValue => targetValue;

        public void Reset()
        {
            currentValue = 0;
            targetValue = 0;
            currentStageProgress = 0;
            fill.Width = 0;
            fill.FinishTransforms();
            heartbeatPulse.FinishTransforms();
            heartbeatPulse.Alpha = 0;
            LastUpdate = null;
            LastHeartbeat = null;
            CurrentStage = GenerationStageId.ModelLoad;
        }

        public void UpdateStageProgress(GenerationStageId stageId, double stageProgress, bool immediate = false)
        {
            stageProgress = Math.Clamp(stageProgress, 0, 1);
            double weighted = GenerationStagePlan.ToWeightedProgress(stageId, stageProgress);
            if (weighted < currentValue)
                weighted = currentValue;

            targetValue = Math.Clamp(weighted, 0, 1);
            CurrentStage = stageId;
            LastUpdate = DateTimeOffset.UtcNow;
            LastHeartbeat = LastUpdate;
            currentStageProgress = stageProgress;

            pulseHeartbeat();

            if (immediate)
            {
                currentValue = targetValue;
                fill.Width = (float)currentValue;
            }
        }

        public void RegisterHeartbeat(GenerationStageId stageId, double stageProgress)
        {
            CurrentStage = stageId;
            currentStageProgress = Math.Max(currentStageProgress, Math.Clamp(stageProgress, 0, 1));
            LastHeartbeat = DateTimeOffset.UtcNow;
            LastUpdate = LastHeartbeat;

            double weighted = GenerationStagePlan.ToWeightedProgress(stageId, currentStageProgress);
            if (weighted > targetValue)
                targetValue = Math.Clamp(weighted, 0, 1);

            pulseHeartbeat();
        }

        protected override void Update()
        {
            base.Update();

            if (Math.Abs(currentValue - targetValue) <= 0.0001)
            {
                fill.Width = (float)currentValue;
                return;
            }

            double diff = targetValue - currentValue;

            if (diff <= 0)
            {
                currentValue = Math.Max(currentValue, targetValue);
            }
            else
            {
                double dt = Math.Clamp(Time.Elapsed / 1000.0, 0.0, 1.0);
                double rate = 1 - Math.Pow(0.5, dt / smoothingHalfLifeSeconds);
                rate = Math.Clamp(rate, minRatePerFrame, maxRatePerFrame);

                if (stageCaps.TryGetValue(CurrentStage, out var cap))
                    diff = Math.Min(diff, Math.Max(cap - currentValue, 0));

                currentValue += diff * rate;
            }

            fill.Width = (float)currentValue;
        }

        public void MarkCompleted()
        {
            UpdateStageProgress(GenerationStageId.Finalise, 1, true);
        }

        private void pulseHeartbeat()
        {
            heartbeatPulse.FinishTransforms();
            heartbeatPulse.Alpha = 0;
            heartbeatPulse.FadeTo(0.35f, 80, Easing.OutQuint)
                          .Then()
                          .FadeOut(260, Easing.OutQuint);
        }

        private static IReadOnlyDictionary<GenerationStageId, double> buildStageCaps()
        {
            var caps = new Dictionary<GenerationStageId, double>();

            foreach (var stage in GenerationStagePlan.OrderedStages)
                caps[stage] = GenerationStagePlan.ToWeightedProgress(stage, 1);

            return caps;
        }
    }
}
