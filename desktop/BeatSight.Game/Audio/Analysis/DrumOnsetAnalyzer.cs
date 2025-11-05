using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace BeatSight.Game.Audio.Analysis
{
    public static class DrumOnsetAnalyzer
    {
        public static DrumOnsetAnalysis LoadFromFile(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
                throw new ArgumentException("Path must be provided", nameof(path));

            if (!File.Exists(path))
                throw new FileNotFoundException("Debug analysis file not found", path);

            string json = File.ReadAllText(path);
            return LoadFromJson(json);
        }

        public static DrumOnsetAnalysis LoadFromJson(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
                throw new ArgumentException("JSON payload must not be empty", nameof(json));

            var root = JObject.Parse(json);

            // The python pipeline stores debug payload under a nested structure when invoked via CLI.
            var detectionToken = root["detection"] ?? root.SelectToken("generation.detection");
            var quantizationToken = root.SelectToken("generation.quantization") ?? root["quantization"];
            var sectionsToken = root.SelectToken("generation.sections") ?? root["sections"];

            if (detectionToken == null)
                throw new InvalidDataException("Debug payload missing detection section.");

            if (quantizationToken == null)
                throw new InvalidDataException("Debug payload missing quantization section.");

            double sampleRate = detectionToken.Value<double?>("sample_rate") ?? 44100;
            int hopLength = detectionToken.Value<int?>("hop_length") ?? 256;
            double tempo = detectionToken.Value<double?>("tempo") ?? quantizationToken.Value<double?>("bpm") ?? 120;

            var envelope = toDoubleList(detectionToken["envelope"]);
            var threshold = toDoubleList(detectionToken["adaptive_threshold"]);
            var peaks = parsePeaks(detectionToken["peaks"]);
            var quantization = parseQuantization(quantizationToken);
            var sections = parseSections(sectionsToken);

            return new DrumOnsetAnalysis(sampleRate, hopLength, tempo, envelope, threshold, peaks, quantization, sections);
        }

        private static List<double> toDoubleList(JToken? token)
        {
            if (token == null)
                return new List<double>();

            if (token is JArray array)
                return array.Select(t => (double)t).ToList();

            throw new InvalidDataException("Unexpected JSON token for numeric list.");
        }

        private static List<DrumOnsetPeak> parsePeaks(JToken? token)
        {
            var result = new List<DrumOnsetPeak>();
            if (token is not JArray array)
                return result;

            foreach (var item in array)
            {
                double time = item.Value<double?>("time") ?? 0;
                double confidence = item.Value<double?>("confidence") ?? 0;
                double envelope = item.Value<double?>("envelope") ?? 0;
                double threshold = item.Value<double?>("threshold") ?? 0;
                int frame = item.Value<int?>("frame") ?? 0;
                var bandEnergy = toDoubleList(item["band_energy"]);
                result.Add(new DrumOnsetPeak(time, confidence, envelope, threshold, frame, bandEnergy));
            }

            return result;
        }

        private static QuantizationSummary parseQuantization(JToken? token)
        {
            if (token == null)
                return new QuantizationSummary("sixteenth", 0, 0, 0, 0, 0);

            string grid = token.Value<string?>("grid") ?? "sixteenth";
            double coverage = token.Value<double?>("coverage") ?? 0;
            double meanError = token.Value<double?>("mean_error_ms") ?? 0;
            double medianError = token.Value<double?>("median_error_ms") ?? 0;
            double offset = token.Value<double?>("offset") ?? 0;
            double step = token.Value<double?>("step") ?? 0;
            var candidates = new List<QuantizationCandidate>();

            if (token["candidates"] is JArray array)
            {
                foreach (var candidate in array)
                {
                    double bpm = candidate.Value<double?>("bpm") ?? 0;
                    double candCoverage = candidate.Value<double?>("coverage") ?? 0;
                    double candMeanErrorSeconds = candidate.Value<double?>("mean_error") ?? 0;
                    double candMeanErrorMs = candidate.Value<double?>("mean_error_ms") ?? candMeanErrorSeconds * 1000.0;
                    double candMedianErrorSeconds = candidate.Value<double?>("median_error") ?? 0;
                    double candMedianErrorMs = candidate.Value<double?>("median_error_ms") ?? candMedianErrorSeconds * 1000.0;
                    double candOffset = candidate.Value<double?>("offset") ?? 0;
                    double candStep = candidate.Value<double?>("step") ?? 0;
                    candidates.Add(new QuantizationCandidate(bpm, candCoverage, candMeanErrorMs, candMedianErrorMs, candOffset, candStep));
                }
            }

            return new QuantizationSummary(grid, coverage, meanError, medianError, offset, step, candidates);
        }

        private static List<DrumOnsetSection> parseSections(JToken? token)
        {
            var result = new List<DrumOnsetSection>();
            if (token is not JArray array)
                return result;

            foreach (var section in array)
            {
                int index = section.Value<int?>("section") ?? 0;
                double start = section.Value<double?>("start") ?? 0;
                double end = section.Value<double?>("end") ?? 0;
                int count = section.Value<int?>("count") ?? 0;
                double density = section.Value<double?>("density") ?? 0;
                result.Add(new DrumOnsetSection(index, start, end, count, density));
            }

            return result;
        }
    }

    public class DrumOnsetAnalysis
    {
        public DrumOnsetAnalysis(
            double sampleRate,
            int hopLength,
            double tempo,
            IReadOnlyList<double> envelope,
            IReadOnlyList<double> threshold,
            IReadOnlyList<DrumOnsetPeak> peaks,
            QuantizationSummary quantization,
            IReadOnlyList<DrumOnsetSection> sections)
        {
            SampleRate = sampleRate;
            HopLength = hopLength;
            Tempo = tempo;
            Envelope = envelope;
            AdaptiveThreshold = threshold;
            Peaks = peaks;
            Quantization = quantization;
            Sections = sections;
        }

        public double SampleRate { get; }
        public int HopLength { get; }
        public double Tempo { get; }
        public IReadOnlyList<double> Envelope { get; }
        public IReadOnlyList<double> AdaptiveThreshold { get; }
        public IReadOnlyList<DrumOnsetPeak> Peaks { get; }
        public QuantizationSummary Quantization { get; }
        public IReadOnlyList<DrumOnsetSection> Sections { get; }

        public double DurationSeconds => Envelope.Count * HopLength / Math.Max(1, SampleRate);

        public IEnumerable<double> GetBeatGridTimes()
        {
            if (Quantization.StepSeconds <= 0)
                yield break;

            double duration = DurationSeconds;
            for (double t = Quantization.OffsetSeconds; t <= duration + Quantization.StepSeconds; t += Quantization.StepSeconds)
                yield return t;
        }

        public double AverageTimingErrorMs => Quantization.MeanErrorMilliseconds;
    }

    public readonly struct DrumOnsetPeak
    {
        public DrumOnsetPeak(double time, double confidence, double envelope, double threshold, int frame, IReadOnlyList<double> bandEnergy)
        {
            Time = time;
            Confidence = confidence;
            Envelope = envelope;
            Threshold = threshold;
            Frame = frame;
            BandEnergy = bandEnergy;
        }

        public double Time { get; }
        public double Confidence { get; }
        public double Envelope { get; }
        public double Threshold { get; }
        public int Frame { get; }
        public IReadOnlyList<double> BandEnergy { get; }
    }

    public readonly struct DrumOnsetSection
    {
        public DrumOnsetSection(int index, double start, double end, int count, double density)
        {
            Index = index;
            Start = start;
            End = end;
            Count = count;
            Density = density;
        }

        public int Index { get; }
        public double Start { get; }
        public double End { get; }
        public int Count { get; }
        public double Density { get; }
    }

    public class QuantizationSummary
    {
        public QuantizationSummary(string grid, double coverage, double meanErrorMs, double medianErrorMs, double offsetSeconds, double stepSeconds, IReadOnlyList<QuantizationCandidate>? candidates = null)
        {
            Grid = grid;
            Coverage = coverage;
            MeanErrorMilliseconds = meanErrorMs;
            MedianErrorMilliseconds = medianErrorMs;
            OffsetSeconds = offsetSeconds;
            StepSeconds = stepSeconds;
            Candidates = candidates ?? Array.Empty<QuantizationCandidate>();
        }

        public string Grid { get; }
        public double Coverage { get; }
        public double MeanErrorMilliseconds { get; }
        public double MedianErrorMilliseconds { get; }
        public double OffsetSeconds { get; }
        public double StepSeconds { get; }
        public IReadOnlyList<QuantizationCandidate> Candidates { get; }
    }

    public readonly struct QuantizationCandidate
    {
        public QuantizationCandidate(double bpm, double coverage, double meanErrorMilliseconds, double medianErrorMilliseconds, double offsetSeconds, double stepSeconds)
        {
            Bpm = bpm;
            Coverage = coverage;
            MeanErrorMilliseconds = meanErrorMilliseconds;
            MedianErrorMilliseconds = medianErrorMilliseconds;
            OffsetSeconds = offsetSeconds;
            StepSeconds = stepSeconds;
        }

        public double Bpm { get; }
        public double Coverage { get; }
        public double MeanErrorMilliseconds { get; }
        public double MedianErrorMilliseconds { get; }
        public double OffsetSeconds { get; }
        public double StepSeconds { get; }
    }
}
