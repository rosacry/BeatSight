using System.Reflection;
using BeatSight.Game.AI;
using Xunit;

namespace BeatSight.Tests;

public class AiBeatmapGeneratorArgumentsTests
{
    [Fact]
    public void BuildArguments_DefaultOptions_UsesGameplayWithManualSensitivityAndGrid()
    {
        var options = new AiGenerationOptions
        {
            DetectionSensitivity = 60,
            QuantizationGrid = QuantizationGrid.Sixteenth
        };

        string args = buildArguments(options);

        Assert.Contains(" --mode gameplay", args, StringComparison.Ordinal);
        Assert.Contains(" --sensitivity 60", args, StringComparison.Ordinal);
        Assert.Contains(" --quantization sixteenth", args, StringComparison.Ordinal);
        Assert.DoesNotContain(" --auto-sensitivity", args, StringComparison.Ordinal);
        Assert.DoesNotContain(" --auto-quantization", args, StringComparison.Ordinal);
    }

    [Fact]
    public void BuildArguments_AutoOptions_UsesTranscriptionWithAutoFlags()
    {
        var options = new AiGenerationOptions
        {
            PipelineMode = AiPipelineMode.Transcription,
            DetectionSensitivity = 77,
            QuantizationGrid = QuantizationGrid.Triplet,
            AutoSensitivity = true,
            AutoQuantization = true
        };

        string args = buildArguments(options);

        Assert.Contains(" --mode transcription", args, StringComparison.Ordinal);
        Assert.Contains(" --auto-sensitivity", args, StringComparison.Ordinal);
        Assert.Contains(" --auto-quantization", args, StringComparison.Ordinal);
        Assert.DoesNotContain(" --sensitivity 77", args, StringComparison.Ordinal);
        Assert.DoesNotContain(" --quantization ", args, StringComparison.Ordinal);
    }

    [Fact]
    public void BuildArguments_ManualNonDefaultGrid_UsesExpectedGridName()
    {
        var options = new AiGenerationOptions
        {
            QuantizationGrid = QuantizationGrid.ThirtySecond,
            AutoQuantization = false
        };

        string args = buildArguments(options);

        Assert.Contains(" --quantization thirtysecond", args, StringComparison.Ordinal);
    }

    [Fact]
    public void BuildArguments_AutoSensitivityOnly_KeepsManualQuantization()
    {
        var options = new AiGenerationOptions
        {
            DetectionSensitivity = 72,
            QuantizationGrid = QuantizationGrid.Triplet,
            AutoSensitivity = true,
            AutoQuantization = false
        };

        string args = buildArguments(options);

        Assert.Contains(" --auto-sensitivity", args, StringComparison.Ordinal);
        Assert.DoesNotContain(" --sensitivity 72", args, StringComparison.Ordinal);
        Assert.Contains(" --quantization triplet", args, StringComparison.Ordinal);
        Assert.DoesNotContain(" --auto-quantization", args, StringComparison.Ordinal);
    }

    [Fact]
    public void BuildArguments_AutoQuantizationOnly_KeepsManualSensitivity()
    {
        var options = new AiGenerationOptions
        {
            DetectionSensitivity = 55,
            QuantizationGrid = QuantizationGrid.Quarter,
            AutoSensitivity = false,
            AutoQuantization = true
        };

        string args = buildArguments(options);

        Assert.Contains(" --sensitivity 55", args, StringComparison.Ordinal);
        Assert.DoesNotContain(" --auto-sensitivity", args, StringComparison.Ordinal);
        Assert.Contains(" --auto-quantization", args, StringComparison.Ordinal);
        Assert.DoesNotContain(" --quantization quarter", args, StringComparison.Ordinal);
    }

    [Fact]
    public void BuildArguments_DefaultThresholdScaleSemantics_DoNotEmitExplicitFlag()
    {
        var options = new AiGenerationOptions();

        string args = buildArguments(options);

        Assert.DoesNotContain(" --threshold-scale ", args, StringComparison.Ordinal);
    }

    [Fact]
    public void BuildArguments_UnsupportedGrid_FallsBackToSixteenth()
    {
        var options = new AiGenerationOptions
        {
            QuantizationGrid = QuantizationGrid.None,
            AutoQuantization = false
        };

        string args = buildArguments(options);

        Assert.Contains(" --quantization sixteenth", args, StringComparison.Ordinal);
    }

    private static string buildArguments(AiGenerationOptions options)
    {
        var method = typeof(AiBeatmapGenerator).GetMethod(
            "buildArguments",
            BindingFlags.NonPublic | BindingFlags.Static);

        Assert.NotNull(method);

        var args = method!.Invoke(
            null,
            new object[] { "input.flac", "output.bsm", "debug.json", options }) as string;

        Assert.False(string.IsNullOrWhiteSpace(args));
        return args!;
    }
}
