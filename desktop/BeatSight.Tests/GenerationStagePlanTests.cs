using System.Linq;
using BeatSight.Game.Services.Generation;

namespace BeatSight.Tests;

public class GenerationStagePlanTests
{
    [Fact]
    public void StageWeightsSumToUnity()
    {
        double sum = GenerationStagePlan.StageWeights.Values.Sum();
        Assert.Equal(1.0, sum, 5);
    }

    [Fact]
    public void WeightedProgressMonotonicAcrossStages()
    {
        double modelHalf = GenerationStagePlan.ToWeightedProgress(GenerationStageId.ModelLoad, 0.5);
        double separationStart = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Separation, 0);
        Assert.True(modelHalf <= separationStart);

        double separationHalf = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Separation, 0.5);
        Assert.True(separationHalf > separationStart);

        double finalProgress = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Finalise, 1.0);
        Assert.Equal(1.0, finalProgress, 5);
    }

    [Fact]
    public void WeightedProgressCapsAtOne()
    {
        double overProgress = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Finalise, 1.5);
        Assert.Equal(1.0, overProgress, 5);
    }

    [Fact]
    public void GetLabelFallsBackToEnumName()
    {
        string label = GenerationStagePlan.GetLabel((GenerationStageId)999);
        Assert.Equal("999", label);
    }

    [Fact]
    public void OrderedStagesAlignWithWeights()
    {
        foreach (var stage in GenerationStagePlan.OrderedStages)
        {
            Assert.True(GenerationStagePlan.StageWeights.ContainsKey(stage));
        }
    }
}
