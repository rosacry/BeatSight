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

    [Fact]
    public void NegativeProgressClampsToZero()
    {
        double negativeProgress = GenerationStagePlan.ToWeightedProgress(GenerationStageId.ModelLoad, -0.5);
        Assert.True(negativeProgress >= 0.0);
    }

    [Fact]
    public void ZeroProgressReturnsStageBaseline()
    {
        // ModelLoad at 0% should be 0
        double modelZero = GenerationStagePlan.ToWeightedProgress(GenerationStageId.ModelLoad, 0);
        Assert.Equal(0.0, modelZero, 5);

        // Separation at 0% should be at ModelLoad weight (0.05)
        double separationZero = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Separation, 0);
        Assert.Equal(0.05, separationZero, 5);
    }

    [Fact]
    public void StageProgressIsLinearWithinStage()
    {
        double start = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Separation, 0);
        double quarter = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Separation, 0.25);
        double half = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Separation, 0.5);
        double threeQuarter = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Separation, 0.75);
        double end = GenerationStagePlan.ToWeightedProgress(GenerationStageId.Separation, 1.0);

        // Should progress linearly within the stage weight
        double weight = GenerationStagePlan.StageWeights[GenerationStageId.Separation];
        Assert.Equal(start + weight * 0.25, quarter, 5);
        Assert.Equal(start + weight * 0.5, half, 5);
        Assert.Equal(start + weight * 0.75, threeQuarter, 5);
        Assert.Equal(start + weight, end, 5);
    }

    [Fact]
    public void AllStagesHaveLabels()
    {
        foreach (var stage in GenerationStagePlan.OrderedStages)
        {
            string label = GenerationStagePlan.GetLabel(stage);
            Assert.False(string.IsNullOrWhiteSpace(label));
            Assert.NotEqual(stage.ToString(), label); // Should have a human-readable label, not just enum name
        }
    }

    [Fact]
    public void StageOrderMatchesExpectedPipelineSequence()
    {
        var stages = GenerationStagePlan.OrderedStages.ToList();

        // Verify expected pipeline order
        Assert.Equal(GenerationStageId.ModelLoad, stages[0]);
        Assert.Equal(GenerationStageId.Separation, stages[1]);
        Assert.Equal(GenerationStageId.OnsetDetection, stages[2]);
        Assert.Equal(GenerationStageId.TempoGrid, stages[3]);
        Assert.Equal(GenerationStageId.DraftMapping, stages[4]);
        Assert.Equal(GenerationStageId.Finalise, stages[5]);
    }

    [Fact]
    public void WeightsReflectExpectedRelativeDurations()
    {
        // Separation should be the heaviest stage (Demucs is slowest)
        double separationWeight = GenerationStagePlan.StageWeights[GenerationStageId.Separation];
        Assert.True(separationWeight >= 0.30, "Separation should be weighted heavily (30%+)");

        // Model load and finalise should be lightweight
        double modelWeight = GenerationStagePlan.StageWeights[GenerationStageId.ModelLoad];
        double finaliseWeight = GenerationStagePlan.StageWeights[GenerationStageId.Finalise];
        Assert.True(modelWeight <= 0.10, "ModelLoad should be lightweight (10% or less)");
        Assert.True(finaliseWeight <= 0.10, "Finalise should be lightweight (10% or less)");
    }

    [Theory]
    [InlineData(GenerationStageId.ModelLoad)]
    [InlineData(GenerationStageId.Separation)]
    [InlineData(GenerationStageId.OnsetDetection)]
    [InlineData(GenerationStageId.TempoGrid)]
    [InlineData(GenerationStageId.DraftMapping)]
    [InlineData(GenerationStageId.Finalise)]
    public void EachStageProgressStartsWherePreceededStageEnds(GenerationStageId stage)
    {
        var stages = GenerationStagePlan.OrderedStages.ToList();
        int index = stages.IndexOf(stage);

        double stageStart = GenerationStagePlan.ToWeightedProgress(stage, 0);

        if (index == 0)
        {
            Assert.Equal(0.0, stageStart, 5);
        }
        else
        {
            var previousStage = stages[index - 1];
            double previousEnd = GenerationStagePlan.ToWeightedProgress(previousStage, 1.0);
            Assert.Equal(previousEnd, stageStart, 5);
        }
    }
}
