using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.AI;
using BeatSight.Game.Audio;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.Services.Decode;

namespace BeatSight.Game.Services.Analysis
{
    public sealed class OnsetDetectionService
    {
        public Task<DetectionIntermediate> DetectOnsetsAsync(DecodedAudio audio, OnsetDetectionParameters parameters, IProgress<double>? progress, CancellationToken cancellationToken)
        {
            if (audio.Waveform == null)
                throw new ArgumentException("Decoded audio must include waveform data.", nameof(audio));

            return Task.Factory.StartNew(() => detectInternal(audio.Waveform, parameters, progress, cancellationToken), cancellationToken, TaskCreationOptions.LongRunning, TaskScheduler.Default);
        }

        public Task<QuantizationResult> QuantizeAsync(DetectionIntermediate detection, OnsetDetectionParameters parameters, IProgress<double>? progress, CancellationToken cancellationToken)
        {
            if (detection == null)
                throw new ArgumentNullException(nameof(detection));

            return Task.Factory.StartNew(() => quantizeInternal(detection, parameters, progress, cancellationToken), cancellationToken, TaskCreationOptions.LongRunning, TaskScheduler.Default);
        }

        private DetectionIntermediate detectInternal(WaveformData waveform, OnsetDetectionParameters parameters, IProgress<double>? progress, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            int bucketCount = waveform.BucketCount;
            if (bucketCount == 0)
                throw new InvalidOperationException("Waveform builder returned no samples for detection.");

            double bucketDuration = Math.Max(1e-4, waveform.BucketDurationSeconds);

            var envelope = new double[bucketCount];
            var threshold = new double[bucketCount];
            double maxAmplitude = 0;

            for (int i = 0; i < bucketCount; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();

                float positive = Math.Abs(waveform.Maxima[i]);
                float negative = Math.Abs(waveform.Minima[i]);
                double amplitude = Math.Max(positive, negative);
                envelope[i] = amplitude;
                if (amplitude > maxAmplitude)
                    maxAmplitude = amplitude;
            }

            if (maxAmplitude <= double.Epsilon)
                maxAmplitude = 1;

            for (int i = 0; i < bucketCount; i++)
                envelope[i] = Math.Clamp(envelope[i] / maxAmplitude, 0, 1);

            double sensitivityNorm = Math.Clamp(parameters.Sensitivity / 100.0, 0.05, 1.0);
            double smoothingSeconds = 0.12 + 0.18 * (1 - sensitivityNorm);
            int window = Math.Clamp((int)Math.Round(smoothingSeconds / bucketDuration), 4, 160);
            double thresholdBoost = 0.12 + 0.35 * (1 - sensitivityNorm);

            double runningSum = envelope.Take(window).Sum();
            for (int i = 0; i < bucketCount; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();

                if (i >= window)
                    runningSum += envelope[i] - envelope[i - window];

                double average = runningSum / window;
                threshold[i] = Math.Clamp(average + thresholdBoost, 0, 1);
            }

            var peaks = new List<DrumOnsetPeak>();
            int minSeparationBuckets = Math.Max(3, (int)Math.Round((0.08 + 0.18 * (1 - sensitivityNorm)) / bucketDuration));
            int lastPeakIndex = -minSeparationBuckets;

            for (int i = 1; i < bucketCount - 1; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();

                double current = envelope[i];
                if (current <= envelope[i - 1] || current < envelope[i + 1])
                    continue;

                if (current <= threshold[i])
                    continue;

                if (i - lastPeakIndex < minSeparationBuckets)
                    continue;

                double time = i * bucketDuration;
                double confidence = Math.Clamp(current, 0, 1);

                peaks.Add(new DrumOnsetPeak(
                    time,
                    confidence,
                    current,
                    threshold[i],
                    i,
                    new[]
                    {
                        current,
                        current * 0.75,
                        current * 0.45,
                        current * 0.25
                    }));

                lastPeakIndex = i;

                if (peaks.Count % 50 == 0)
                    progress?.Report(Math.Min(0.8, (double)i / bucketCount));
            }

            double estimatedTempo = estimateTempo(peaks);
            int hopLength = Math.Max(256, (int)Math.Round(bucketDuration * waveform.SampleRate));
            var sections = buildSections(peaks, waveform.DurationSeconds);

            progress?.Report(1.0);

            return new DetectionIntermediate(waveform, envelope, threshold, peaks, sections, waveform.SampleRate, hopLength, estimatedTempo);
        }

        private QuantizationResult quantizeInternal(DetectionIntermediate detection, OnsetDetectionParameters parameters, IProgress<double>? progress, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();

            double baseBpm = detection.EstimatedTempo > 0 ? detection.EstimatedTempo : 120;
            double stepSeconds = computeStepSeconds(parameters.Grid, baseBpm);
            if (!double.IsFinite(stepSeconds) || stepSeconds <= 0)
                stepSeconds = computeStepSeconds(parameters.Grid, 120);

            double offset = computeBestOffset(detection.Peaks, stepSeconds);
            var evaluation = evaluateGrid(detection.Peaks, stepSeconds, offset, parameters.MaxSnapErrorMilliseconds);

            var candidates = buildCandidates(detection, parameters, baseBpm);

            var primaryCandidate = selectPrimaryCandidate(candidates, detection.EstimatedTempo);
            if (!double.IsFinite(primaryCandidate.StepSeconds) || primaryCandidate.StepSeconds <= 0)
            {
                double fallbackStep = computeStepSeconds(parameters.Grid, primaryCandidate.Bpm);
                primaryCandidate = new QuantizationCandidate(
                    primaryCandidate.Bpm,
                    primaryCandidate.Coverage,
                    primaryCandidate.MeanErrorMilliseconds,
                    primaryCandidate.MedianErrorMilliseconds,
                    primaryCandidate.OffsetSeconds,
                    fallbackStep);
            }

            var summary = new QuantizationSummary(
                gridToString(parameters.Grid),
                primaryCandidate.Coverage,
                primaryCandidate.MeanErrorMilliseconds,
                primaryCandidate.MedianErrorMilliseconds,
                primaryCandidate.OffsetSeconds,
                primaryCandidate.StepSeconds,
                candidates);

            var analysis = new DrumOnsetAnalysis(
                detection.SampleRate,
                detection.HopLength,
                primaryCandidate.Bpm,
                detection.Envelope,
                detection.Threshold,
                detection.Peaks,
                summary,
                detection.Sections);

            progress?.Report(1.0);

            return new QuantizationResult(analysis, primaryCandidate);
        }

        private static double estimateTempo(IReadOnlyList<DrumOnsetPeak> peaks)
        {
            if (peaks.Count < 2)
                return 120;

            var intervals = new List<double>(peaks.Count);
            for (int i = 1; i < peaks.Count; i++)
            {
                double delta = peaks[i].Time - peaks[i - 1].Time;
                if (delta >= 0.12 && delta <= 2.0)
                    intervals.Add(delta);
            }

            if (intervals.Count == 0)
                return 120;

            intervals.Sort();
            double median = intervals[intervals.Count / 2];
            if (!double.IsFinite(median) || median <= 0)
                median = intervals.Average();

            if (!double.IsFinite(median) || median <= 0)
                return 120;

            double bpm = 60.0 / median;
            while (bpm < 80)
                bpm *= 2;
            while (bpm > 180)
                bpm /= 2;
            return Math.Clamp(bpm, 60, 240);
        }

        private static IReadOnlyList<DrumOnsetSection> buildSections(IReadOnlyList<DrumOnsetPeak> peaks, double duration)
        {
            if (duration <= 0)
                duration = peaks.Count > 0 ? peaks[^1].Time : 0;

            if (duration <= 0)
                return Array.Empty<DrumOnsetSection>();

            double sectionLength = Math.Clamp(duration / 12.0, 5.0, 20.0);
            int sectionCount = (int)Math.Ceiling(duration / sectionLength);

            var sections = new List<DrumOnsetSection>(sectionCount);
            for (int i = 0; i < sectionCount; i++)
            {
                double start = i * sectionLength;
                double end = Math.Min(duration, start + sectionLength);
                int count = peaks.Count(p => p.Time >= start && p.Time < end);
                double density = sectionLength > 0 ? count / sectionLength : 0;
                sections.Add(new DrumOnsetSection(i + 1, start, end, count, density));
            }

            return sections;
        }

        private static double computeStepSeconds(QuantizationGrid grid, double bpm)
        {
            if (!double.IsFinite(bpm) || bpm <= 0)
                return 0;

            double beatLength = 60.0 / bpm; // quarter note length
            double divider = grid switch
            {
                QuantizationGrid.Quarter => 1,
                QuantizationGrid.Eighth => 2,
                QuantizationGrid.Sixteenth => 4,
                QuantizationGrid.Triplet => 3,
                QuantizationGrid.ThirtySecond => 8,
                _ => 1
            };
            return beatLength / divider;
        }

        private static (double Coverage, double MeanErrorMilliseconds, double MedianErrorMilliseconds) evaluateGrid(
            IReadOnlyList<DrumOnsetPeak> peaks,
            double stepSeconds,
            double offsetSeconds,
            double maxSnapErrorMs)
        {
            if (peaks.Count == 0 || stepSeconds <= 0)
                return (0, 0, 0);

            var errors = new List<double>(peaks.Count);
            int aligned = 0;

            foreach (var peak in peaks)
            {
                double index = Math.Round((peak.Time - offsetSeconds) / stepSeconds);
                double alignedTime = offsetSeconds + index * stepSeconds;
                double error = Math.Abs(peak.Time - alignedTime);
                errors.Add(error);

                if (error * 1000 <= maxSnapErrorMs)
                    aligned++;
            }

            errors.Sort();
            double meanMs = errors.Count > 0 ? errors.Average() * 1000 : 0;
            double medianMs = errors.Count > 0 ? errors[errors.Count / 2] * 1000 : 0;
            double coverage = errors.Count > 0 ? (double)aligned / errors.Count : 0;
            return (coverage, meanMs, medianMs);
        }

        private static double computeBestOffset(IReadOnlyList<DrumOnsetPeak> peaks, double stepSeconds)
        {
            if (peaks.Count == 0 || stepSeconds <= 0)
                return 0;

            double bestOffset = 0;
            double bestScore = double.MaxValue;
            int limit = Math.Min(6, peaks.Count);

            for (int i = 0; i < limit; i++)
            {
                double candidate = peaks[i].Time % stepSeconds;
                if (candidate < 0)
                    candidate += stepSeconds;

                double score = 0;
                foreach (var peak in peaks)
                {
                    double index = Math.Round((peak.Time - candidate) / stepSeconds);
                    double alignedTime = candidate + index * stepSeconds;
                    score += Math.Abs(peak.Time - alignedTime);
                }

                if (score < bestScore)
                {
                    bestScore = score;
                    bestOffset = candidate;
                }
            }

            return bestOffset;
        }

        private static IReadOnlyList<QuantizationCandidate> buildCandidates(DetectionIntermediate detection, OnsetDetectionParameters parameters, double baseBpm)
        {
            var result = new List<QuantizationCandidate>();
            var candidateBpms = new HashSet<double>();

            if (baseBpm > 0)
                candidateBpms.Add(baseBpm);
            if (baseBpm * 2 <= 240)
                candidateBpms.Add(baseBpm * 2);
            if (baseBpm / 2 >= 60)
                candidateBpms.Add(baseBpm / 2);
            candidateBpms.Add(Math.Clamp(baseBpm * 1.5, 60, 240));

            foreach (double bpm in candidateBpms)
            {
                double step = computeStepSeconds(parameters.Grid, bpm);
                if (step <= 0)
                    continue;

                double offset = computeBestOffset(detection.Peaks, step);
                var eval = evaluateGrid(detection.Peaks, step, offset, parameters.MaxSnapErrorMilliseconds);
                result.Add(new QuantizationCandidate(bpm, eval.Coverage, eval.MeanErrorMilliseconds, eval.MedianErrorMilliseconds, offset, step));
            }

            return result.OrderByDescending(c => c.Coverage).ThenBy(c => c.MeanErrorMilliseconds).ToList();
        }

        private static string gridToString(QuantizationGrid grid) => grid switch
        {
            QuantizationGrid.Quarter => "quarter",
            QuantizationGrid.Eighth => "eighth",
            QuantizationGrid.Sixteenth => "sixteenth",
            QuantizationGrid.Triplet => "triplet",
            QuantizationGrid.ThirtySecond => "thirtysecond",
            _ => "sixteenth"
        };

        private static QuantizationCandidate selectPrimaryCandidate(IReadOnlyList<QuantizationCandidate> candidates, double estimatedTempo)
        {
            if (candidates.Count == 0)
                return new QuantizationCandidate(estimatedTempo > 0 ? estimatedTempo : 120, 0, 0, 0, 0, 60.0 / Math.Max(estimatedTempo > 0 ? estimatedTempo : 120, 1e-6) / 4);

            double bestScore = double.NegativeInfinity;
            QuantizationCandidate best = candidates[0];
            double maxCoverage = candidates.Max(c => c.Coverage);
            double tempoReference = estimatedTempo > 0 ? estimatedTempo : candidates.FirstOrDefault(c => c.Bpm > 0).Bpm;
            if (tempoReference <= 0)
                tempoReference = 120;

            foreach (var candidate in candidates)
            {
                double coverage = Math.Clamp(candidate.Coverage, 0, 1);
                double coverageBonus = candidate.Coverage >= maxCoverage - 0.01 ? 0.03 : 0;
                if (candidate.Coverage >= maxCoverage + 0.05)
                    coverageBonus += 0.05;

                double meanPenalty = candidate.MeanErrorMilliseconds > 0 ? Math.Clamp(candidate.MeanErrorMilliseconds / 18.0, 0, 0.35) : 0;
                double medianPenalty = candidate.MedianErrorMilliseconds > 0 ? Math.Clamp(candidate.MedianErrorMilliseconds / 16.0, 0, 0.2) : 0;

                double tempoPenalty = 0;
                if (tempoReference > 0 && candidate.Bpm > 0)
                {
                    double ratio = candidate.Bpm / tempoReference;
                    if (ratio > 0)
                    {
                        double deviation = Math.Abs(Math.Log(ratio) / Math.Log(2));
                        tempoPenalty = Math.Min(deviation, 2.0) * 0.08;
                    }
                }

                double score = coverage + coverageBonus - meanPenalty - medianPenalty - tempoPenalty;

                if (score > bestScore)
                {
                    bestScore = score;
                    best = candidate;
                }
            }

            return best;
        }
    }

    public readonly record struct OnsetDetectionParameters(int Sensitivity, QuantizationGrid Grid, double MaxSnapErrorMilliseconds);

    public sealed class DetectionIntermediate
    {
        public DetectionIntermediate(WaveformData waveform, double[] envelope, double[] threshold, IReadOnlyList<DrumOnsetPeak> peaks,
            IReadOnlyList<DrumOnsetSection> sections, double sampleRate, int hopLength, double estimatedTempo)
        {
            Waveform = waveform;
            Envelope = envelope;
            Threshold = threshold;
            Peaks = peaks;
            Sections = sections;
            SampleRate = sampleRate;
            HopLength = hopLength;
            EstimatedTempo = estimatedTempo;
        }

        public WaveformData Waveform { get; }
        public double[] Envelope { get; }
        public double[] Threshold { get; }
        public IReadOnlyList<DrumOnsetPeak> Peaks { get; }
        public IReadOnlyList<DrumOnsetSection> Sections { get; }
        public double SampleRate { get; }
        public int HopLength { get; }
        public double EstimatedTempo { get; }
    }

    public sealed class QuantizationResult
    {
        public QuantizationResult(DrumOnsetAnalysis analysis, QuantizationCandidate candidate)
        {
            Analysis = analysis;
            Candidate = candidate;
        }

        public DrumOnsetAnalysis Analysis { get; }
        public QuantizationCandidate Candidate { get; }
        public double Bpm => Candidate.Bpm;
        public double StepSeconds => Candidate.StepSeconds;
        public double OffsetSeconds => Candidate.OffsetSeconds;
    }
}
