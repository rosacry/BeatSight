using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.AI;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.Services.Analysis;

namespace BeatSight.Game.Services.Generation
{
    internal static class TempoAuthority
    {
        private const double aliasTolerance = 0.08;

        internal static TempoDecision Evaluate(AiGenerationOptions options, QuantizationResult quantization)
        {
            if (options == null)
                throw new ArgumentNullException(nameof(options));
            if (quantization == null)
                throw new ArgumentNullException(nameof(quantization));

            var summary = quantization.Analysis?.Quantization;
            if (summary == null)
                return TempoDecision.Empty;

            var rawPrimary = quantization.Candidate;
            IReadOnlyList<QuantizationCandidate> candidates = summary.Candidates ?? Array.Empty<QuantizationCandidate>();
            if (candidates.Count == 0)
                candidates = new[] { rawPrimary };

            double bpm = double.IsFinite(rawPrimary.Bpm) && rawPrimary.Bpm > 0 ? rawPrimary.Bpm : quantization.Bpm;
            if (!double.IsFinite(bpm) || bpm <= 0)
                bpm = 120.0;

            double stepSeconds = double.IsFinite(rawPrimary.StepSeconds) && rawPrimary.StepSeconds > 0
                ? rawPrimary.StepSeconds
                : summary.StepSeconds;

            if (!double.IsFinite(stepSeconds) || stepSeconds <= 0)
                stepSeconds = inferStepSeconds(options.QuantizationGrid, bpm);

            double offsetSeconds = double.IsFinite(rawPrimary.OffsetSeconds)
                ? rawPrimary.OffsetSeconds
                : summary.OffsetSeconds;
            if (!double.IsFinite(offsetSeconds))
                offsetSeconds = 0;

            var primary = new QuantizationCandidate(bpm, rawPrimary.Coverage, rawPrimary.MeanErrorMilliseconds, rawPrimary.MedianErrorMilliseconds, offsetSeconds, stepSeconds);

            double coverage = Math.Clamp(summary.Coverage, 0, 1);
            options.DownbeatConfidence = coverage;

            var alias = FindAliasCandidate(primary, candidates);
            bool ambiguous = alias.HasValue;

            // When ambiguous (half/double-time detected), pick the better tempo
            // based on quantization quality rather than just warning
            QuantizationCandidate resolvedPrimary = primary;
            if (ambiguous && alias.HasValue)
            {
                resolvedPrimary = ResolveAmbiguousTempo(primary, alias.Value);
            }

            bool strongCoverage = resolvedPrimary.Coverage >= 0.68;
            bool preciseMean = resolvedPrimary.MeanErrorMilliseconds <= 10;
            bool preciseMedian = resolvedPrimary.MedianErrorMilliseconds <= 7;
            bool steadyStep = resolvedPrimary.StepSeconds > 0 && resolvedPrimary.StepSeconds <= 1.5;

            // Only force quantization if not ambiguous AND all quality checks pass
            bool force = strongCoverage && preciseMean && preciseMedian && steadyStep && !ambiguous;
            options.ForceQuantization = force;

            double authoritativeBpm = resolvedPrimary.Bpm;
            if (!double.IsFinite(authoritativeBpm) || authoritativeBpm <= 0)
                authoritativeBpm = quantization.Bpm;
            if (!double.IsFinite(authoritativeBpm) || authoritativeBpm <= 0)
                authoritativeBpm = 120.0;

            double authoritativeStep = resolvedPrimary.StepSeconds;
            if (!double.IsFinite(authoritativeStep) || authoritativeStep <= 0)
                authoritativeStep = inferStepSeconds(options.QuantizationGrid, authoritativeBpm);
            authoritativeStep = Math.Max(authoritativeStep, 1e-4);

            double authoritativeOffset = resolvedPrimary.OffsetSeconds;
            if (!double.IsFinite(authoritativeOffset))
                authoritativeOffset = summary.OffsetSeconds;
            if (!double.IsFinite(authoritativeOffset))
                authoritativeOffset = 0;

            options.ForcedBpm = authoritativeBpm;
            options.ForcedStepSeconds = authoritativeStep;
            options.ForcedOffsetSeconds = authoritativeOffset;
            options.TempoCandidates = buildTempoCandidates(resolvedPrimary, candidates);

            string? warning = null;
            if (alias is QuantizationCandidate aliasCandidate)
            {
                bool pickedAlias = Math.Abs(resolvedPrimary.Bpm - aliasCandidate.Bpm) < 0.01;
                warning = pickedAlias
                    ? $"Tempo ambiguous (~{primary.Bpm:0.#} vs ~{aliasCandidate.Bpm:0.#} BPM). Selected ~{aliasCandidate.Bpm:0.#} BPM based on better quantization fit."
                    : $"Tempo ambiguous (~{primary.Bpm:0.#} vs ~{aliasCandidate.Bpm:0.#} BPM). Kept ~{primary.Bpm:0.#} BPM. Try switching quantization grid if misaligned.";
            }

            return new TempoDecision(true, force, ambiguous, resolvedPrimary, alias, candidates, resolvedPrimary.Coverage, authoritativeOffset, summary.Grid, warning);
        }

        /// <summary>
        /// Resolves ambiguous tempo by selecting the candidate with better quantization fit.
        /// Uses a weighted scoring system that considers coverage, accuracy, and tempo preference.
        /// </summary>
        /// <remarks>
        /// Prefers the alias (half/double) over primary when:
        /// - Coverage is significantly better (>3%)
        /// - Or coverage is similar but mean error is lower
        /// - Applies a slight bias toward "musically typical" tempos (80-160 BPM range)
        /// </remarks>
        internal static QuantizationCandidate ResolveAmbiguousTempo(QuantizationCandidate primary, QuantizationCandidate alias)
        {
            // Score based on quantization quality
            double primaryScore = ComputeTempoScore(primary);
            double aliasScore = ComputeTempoScore(alias);

            // If scores are very close, prefer the tempo in a more typical range (80-160 BPM)
            if (Math.Abs(primaryScore - aliasScore) < 0.02)
            {
                bool primaryInRange = primary.Bpm >= 80 && primary.Bpm <= 160;
                bool aliasInRange = alias.Bpm >= 80 && alias.Bpm <= 160;

                if (aliasInRange && !primaryInRange)
                    return alias;
                if (primaryInRange && !aliasInRange)
                    return primary;
            }

            return aliasScore > primaryScore ? alias : primary;
        }

        /// <summary>
        /// Computes a quality score for a tempo candidate based on coverage and accuracy.
        /// Higher scores indicate better quantization fit.
        /// </summary>
        internal static double ComputeTempoScore(QuantizationCandidate candidate)
        {
            // Base score from coverage (0-1)
            double score = Math.Clamp(candidate.Coverage, 0, 1);

            // Penalty for high mean error (normalize to 0-0.3 range)
            double meanPenalty = candidate.MeanErrorMilliseconds > 0
                ? Math.Clamp(candidate.MeanErrorMilliseconds / 20.0, 0, 0.3)
                : 0;

            // Penalty for high median error (normalize to 0-0.2 range)
            double medianPenalty = candidate.MedianErrorMilliseconds > 0
                ? Math.Clamp(candidate.MedianErrorMilliseconds / 18.0, 0, 0.2)
                : 0;

            // Small bonus for tempos in "typical" drumming range
            double rangeBonus = 0;
            if (candidate.Bpm >= 80 && candidate.Bpm <= 160)
                rangeBonus = 0.02;
            else if (candidate.Bpm >= 60 && candidate.Bpm <= 180)
                rangeBonus = 0.01;

            return score - meanPenalty - medianPenalty + rangeBonus;
        }

        private static IReadOnlyList<double> buildTempoCandidates(QuantizationCandidate primary, IReadOnlyList<QuantizationCandidate> candidates)
        {
            var result = new List<double>(4);

            void tryAdd(double value)
            {
                if (!double.IsFinite(value) || value <= 0)
                    return;

                if (result.Any(existing => Math.Abs(existing - value) <= 1e-3))
                    return;

                result.Add(value);
            }

            tryAdd(primary.Bpm);

            if (candidates != null)
            {
                foreach (var candidate in candidates)
                    tryAdd(candidate.Bpm);
            }

            return result.Count > 0 ? result.AsReadOnly() : Array.Empty<double>();
        }

        internal static QuantizationCandidate? FindAliasCandidate(QuantizationCandidate primary, IReadOnlyList<QuantizationCandidate> candidates)
        {
            if (candidates == null)
                return null;

            QuantizationCandidate? alias = null;

            foreach (var candidate in candidates)
            {
                if (isSameCandidate(primary, candidate))
                    continue;

                if (candidate.Bpm <= 0 || primary.Bpm <= 0)
                    continue;

                double ratio = primary.Bpm >= candidate.Bpm
                    ? primary.Bpm / candidate.Bpm
                    : candidate.Bpm / primary.Bpm;

                if (!isPowerOfTwoRatio(ratio))
                    continue;

                double coverageGap = primary.Coverage - candidate.Coverage;
                bool coverageClose = coverageGap <= 0.06;
                bool accuracyClose = Math.Abs(primary.MeanErrorMilliseconds - candidate.MeanErrorMilliseconds) <= 6
                                     && Math.Abs(primary.MedianErrorMilliseconds - candidate.MedianErrorMilliseconds) <= 5;
                bool altReliable = candidate.Coverage >= 0.55;

                if (coverageClose && accuracyClose && altReliable)
                {
                    alias = candidate;
                    break;
                }
            }

            return alias;
        }

        private static bool isSameCandidate(QuantizationCandidate a, QuantizationCandidate b)
        {
            return Math.Abs(a.Bpm - b.Bpm) < 0.001
                   && Math.Abs(a.Coverage - b.Coverage) < 0.0001
                   && Math.Abs(a.OffsetSeconds - b.OffsetSeconds) < 0.0001;
        }

        private static bool isPowerOfTwoRatio(double ratio)
        {
            if (!double.IsFinite(ratio) || ratio <= 0)
                return false;

            double log2 = Math.Log(ratio, 2);
            double nearest = Math.Round(log2);
            return Math.Abs(log2 - nearest) <= aliasTolerance;
        }

        private static double inferStepSeconds(QuantizationGrid grid, double bpm)
        {
            if (!double.IsFinite(bpm) || bpm <= 0)
                bpm = 120.0;

            double beatLength = 60.0 / bpm;
            double divisor = grid switch
            {
                QuantizationGrid.Quarter => 1,
                QuantizationGrid.Eighth => 2,
                QuantizationGrid.Triplet => 3,
                QuantizationGrid.Sixteenth => 4,
                QuantizationGrid.ThirtySecond => 8,
                _ => 4
            };

            return beatLength / Math.Max(divisor, 1);
        }
    }

    internal readonly record struct TempoDecision(
        bool HasSummary,
        bool ForceQuantization,
        bool Ambiguous,
        QuantizationCandidate Primary,
        QuantizationCandidate? AmbiguousWith,
        IReadOnlyList<QuantizationCandidate> Candidates,
        double Coverage,
        double OffsetSeconds,
        string Grid,
        string? Warning)
    {
        public static TempoDecision Empty { get; } = new TempoDecision(false, false, false, default, null, Array.Empty<QuantizationCandidate>(), 0, 0, "sixteenth", null);

        public string BuildLog()
        {
            string aliasSummary = AmbiguousWith.HasValue
                ? $" alias=~{AmbiguousWith.Value.Bpm:0.###}({AmbiguousWith.Value.Coverage:P1})"
                : string.Empty;

            string candidateSummary = Candidates.Count > 0
                ? string.Join(", ", Candidates.Take(4).Select(c => $"{c.Bpm:0.#}/{c.Coverage:P0}"))
                : $"{Primary.Bpm:0.#}/{Primary.Coverage:P0}";

            return $"[gen] tempo decision bpm={Primary.Bpm:0.###} grid={Grid} offset={OffsetSeconds:0.000}s step={Primary.StepSeconds:0.000}s coverage={Coverage:P1} mean_error={Primary.MeanErrorMilliseconds:0.###}ms median_error={Primary.MedianErrorMilliseconds:0.###}ms forced={(ForceQuantization ? "yes" : "no")}{aliasSummary} candidates=[{candidateSummary}]";
        }
    }
}
