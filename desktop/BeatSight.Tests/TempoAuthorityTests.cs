using System;
using BeatSight.Game.AI;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.Services.Generation;
using BeatSight.Game.Services.Analysis;

namespace BeatSight.Tests;

public class TempoAuthorityTests
{
    [Fact]
    public void SeedsAuthoritativeTimebaseWhenConfidenceLow()
    {
        var options = new AiGenerationOptions
        {
            QuantizationGrid = QuantizationGrid.Sixteenth,
            DetectionSensitivity = 60
        };

        var primaryCandidate = new QuantizationCandidate(
            bpm: 140,
            coverage: 0.62,
            meanErrorMilliseconds: 14.5,
            medianErrorMilliseconds: 10.2,
            offsetSeconds: 0.032,
            stepSeconds: 60.0 / 140.0 / 4);

        var aliasCandidate = new QuantizationCandidate(
            bpm: 70,
            coverage: 0.6,
            meanErrorMilliseconds: 15.8,
            medianErrorMilliseconds: 11.3,
            offsetSeconds: 0.032,
            stepSeconds: 60.0 / 70.0 / 4);

        var summary = new QuantizationSummary(
            grid: "sixteenth",
            coverage: primaryCandidate.Coverage,
            meanErrorMs: primaryCandidate.MeanErrorMilliseconds,
            medianErrorMs: primaryCandidate.MedianErrorMilliseconds,
            offsetSeconds: primaryCandidate.OffsetSeconds,
            stepSeconds: primaryCandidate.StepSeconds,
            candidates: new[] { primaryCandidate, aliasCandidate });

        var analysis = new DrumOnsetAnalysis(
            sampleRate: 44100,
            hopLength: 512,
            tempo: primaryCandidate.Bpm,
            envelope: Array.Empty<double>(),
            threshold: Array.Empty<double>(),
            peaks: Array.Empty<DrumOnsetPeak>(),
            quantization: summary,
            sections: Array.Empty<DrumOnsetSection>());

        var quantization = new QuantizationResult(analysis, primaryCandidate);

        var decision = TempoAuthority.Evaluate(options, quantization);

        Assert.False(options.ForceQuantization);
        Assert.Equal(primaryCandidate.Bpm, options.ForcedBpm);
        Assert.Equal(primaryCandidate.StepSeconds, options.ForcedStepSeconds);
        Assert.Equal(primaryCandidate.OffsetSeconds, options.ForcedOffsetSeconds);
        Assert.NotNull(options.TempoCandidates);
        Assert.Equal(new[] { primaryCandidate.Bpm, aliasCandidate.Bpm }, options.TempoCandidates);

        Assert.True(decision.HasSummary);
        Assert.Equal(primaryCandidate.Bpm, decision.Primary.Bpm);
        Assert.True(decision.Ambiguous);
        Assert.True(decision.Warning?.Contains("Tempo ambiguous", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void TempoCandidatesAreSanitizedAndOrdered()
    {
        var options = new AiGenerationOptions
        {
            QuantizationGrid = QuantizationGrid.Eighth,
            DetectionSensitivity = 70
        };

        var primary = new QuantizationCandidate(
            bpm: 150,
            coverage: 0.74,
            meanErrorMilliseconds: 8.5,
            medianErrorMilliseconds: 6.1,
            offsetSeconds: 0.015,
            stepSeconds: 60.0 / 150.0 / 2);

        var duplicate = new QuantizationCandidate(
            bpm: 150.0004,
            coverage: 0.73,
            meanErrorMilliseconds: 8.6,
            medianErrorMilliseconds: 6.2,
            offsetSeconds: 0.015,
            stepSeconds: 60.0 / 150.0004 / 2);

        var alias = new QuantizationCandidate(
            bpm: 75,
            coverage: 0.7,
            meanErrorMilliseconds: 9.2,
            medianErrorMilliseconds: 6.5,
            offsetSeconds: 0.015,
            stepSeconds: 60.0 / 75.0 / 2);

        var invalid = new QuantizationCandidate(
            bpm: -60,
            coverage: 0.4,
            meanErrorMilliseconds: 30,
            medianErrorMilliseconds: 25,
            offsetSeconds: 0.015,
            stepSeconds: 60.0 / 60.0 / 2);

        var summary = new QuantizationSummary(
            grid: "eighth",
            coverage: primary.Coverage,
            meanErrorMs: primary.MeanErrorMilliseconds,
            medianErrorMs: primary.MedianErrorMilliseconds,
            offsetSeconds: primary.OffsetSeconds,
            stepSeconds: primary.StepSeconds,
            candidates: new[] { primary, duplicate, invalid, alias });

        var analysis = new DrumOnsetAnalysis(
            sampleRate: 48000,
            hopLength: 512,
            tempo: primary.Bpm,
            envelope: Array.Empty<double>(),
            threshold: Array.Empty<double>(),
            peaks: Array.Empty<DrumOnsetPeak>(),
            quantization: summary,
            sections: Array.Empty<DrumOnsetSection>());

        var quantization = new QuantizationResult(analysis, primary);

        TempoAuthority.Evaluate(options, quantization);

        Assert.NotNull(options.TempoCandidates);
        Assert.Equal(new[] { 150d, 75d }, options.TempoCandidates);
    }
}
