using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps.Difficulty;

namespace BeatSight.Game.Beatmaps.Difficulty.Analysis
{
    /// <summary>
    /// FOUR-WAY LIMB INDEPENDENCE RATING SYSTEM
    /// 
    /// This system provides a sophisticated analysis of limb independence -
    /// arguably the most fundamental and challenging aspect of drumming.
    /// 
    /// INDEPENDENCE DIMENSIONS:
    /// 
    /// 1. RHYTHMIC INDEPENDENCE
    ///    Each limb playing different rhythmic patterns simultaneously.
    /// 
    /// 2. DYNAMIC INDEPENDENCE
    ///    Each limb at different volume levels (ghost notes while accenting).
    /// 
    /// 3. METRIC INDEPENDENCE
    ///    Limbs playing in different meters (3 vs 4, etc.).
    /// 
    /// 4. TEXTURAL INDEPENDENCE
    ///    Different techniques on different limbs simultaneously.
    /// 
    /// INDEPENDENCE LEVELS (0-10 scale):
    ///   0-2: Beginner (unison or simple backbeat)
    ///   2-4: Intermediate (basic rock/pop independence)
    ///   4-6: Advanced (jazz comping, linear patterns)
    ///   6-8: Expert (Vinnie Colaiuta, Steve Gadd territory)
    ///   8-9: Elite (four-way jazz independence, metric modulation)
    ///   9-10: Transcendent (Marco Minnemann, Virgil Donati extremes)
    /// </summary>
    public class IndependenceRatingSystem
    {
        // Voice/Limb tracking
        private readonly LimbVoice rightHand = new("RightHand");
        private readonly LimbVoice leftHand = new("LeftHand");
        private readonly LimbVoice rightFoot = new("RightFoot");
        private readonly LimbVoice leftFoot = new("LeftFoot");

        // Analysis window
        private const int WINDOW_SIZE = 32;
        private readonly List<LimbSnapshot> historyWindow = new();

        /// <summary>
        /// Analyze independence for a hit object.
        /// </summary>
        public IndependenceResult Analyze(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            var result = new IndependenceResult();

            // Update limb voice states
            UpdateLimbVoices(current);

            // Record snapshot
            RecordSnapshot(current);

            // Need enough history for meaningful analysis
            if (historyWindow.Count < 8)
            {
                result.OverallIndependence = 0;
                return result;
            }

            // 1. Rhythmic Independence Analysis
            result.RhythmicIndependence = AnalyzeRhythmicIndependence();

            // 2. Dynamic Independence Analysis
            result.DynamicIndependence = AnalyzeDynamicIndependence();

            // 3. Metric Independence Analysis
            result.MetricIndependence = AnalyzeMetricIndependence();

            // 4. Textural Independence Analysis
            result.TexturalIndependence = AnalyzeTexturalIndependence();

            // 5. Calculate active limb count
            result.ActiveLimbCount = CountActiveLimbs();

            // 6. Inter-limb correlation matrix
            result.CorrelationMatrix = CalculateCorrelationMatrix();

            // 7. Phase relationship complexity
            result.PhaseComplexity = CalculatePhaseComplexity();

            // Calculate overall independence score
            result.OverallIndependence = CalculateOverallScore(result);

            // Generate breakdown
            result.Breakdown = GenerateBreakdown(result);

            return result;
        }

        /// <summary>
        /// Update limb voice states based on current hit.
        /// Uses HasLeftHand/HasRightHand/HasLeftFoot/HasRightFoot from DifficultyHitObject.
        /// </summary>
        private void UpdateLimbVoices(DifficultyHitObject current)
        {
            // Map hit to limbs based on actual limb usage
            if (current.HasRightHand)
            {
                var technique = current.Techniques.FirstOrDefault(t => t != TechniqueType.Normal);
                rightHand.RecordEvent(current.StartTime, current.DeltaTime, current.AverageVelocity,
                    technique != TechniqueType.Normal ? technique.ToString() : "normal");
            }

            if (current.HasLeftHand)
            {
                var technique = current.Techniques.FirstOrDefault(t => t != TechniqueType.Normal);
                leftHand.RecordEvent(current.StartTime, current.DeltaTime, current.AverageVelocity,
                    technique != TechniqueType.Normal ? technique.ToString() : "snare");
            }

            if (current.HasRightFoot)
            {
                rightFoot.RecordEvent(current.StartTime, current.DeltaTime, current.AverageVelocity, "kick");
            }

            if (current.HasLeftFoot)
            {
                leftFoot.RecordEvent(current.StartTime, current.DeltaTime, current.AverageVelocity * 0.5, "hhPedal");
            }
        }

        /// <summary>
        /// Record a snapshot of the current state for window analysis.
        /// </summary>
        private void RecordSnapshot(DifficultyHitObject current)
        {
            var snapshot = new LimbSnapshot
            {
                Time = current.StartTime,
                RightHandActive = current.HasRightHand,
                LeftHandActive = current.HasLeftHand,
                RightFootActive = current.HasRightFoot,
                LeftFootActive = current.HasLeftFoot,
                RightHandVelocity = current.HasRightHand ? current.AverageVelocity : 0,
                LeftHandVelocity = current.HasLeftHand ? current.AverageVelocity : 0,
                RightFootVelocity = current.HasRightFoot ? current.AverageVelocity : 0,
                LeftFootVelocity = current.HasLeftFoot ? current.AverageVelocity : 0,
                DeltaTime = current.DeltaTime
            };

            historyWindow.Add(snapshot);
            if (historyWindow.Count > WINDOW_SIZE)
                historyWindow.RemoveAt(0);
        }

        /// <summary>
        /// Analyze rhythmic independence between limbs.
        /// </summary>
        private double AnalyzeRhythmicIndependence()
        {
            // Calculate rhythm correlation for each limb pair
            var rhActivations = historyWindow.Select(s => s.RightHandActive ? 1.0 : 0.0).ToArray();
            var lhActivations = historyWindow.Select(s => s.LeftHandActive ? 1.0 : 0.0).ToArray();
            var rfActivations = historyWindow.Select(s => s.RightFootActive ? 1.0 : 0.0).ToArray();
            var lfActivations = historyWindow.Select(s => s.LeftFootActive ? 1.0 : 0.0).ToArray();

            // Calculate pair-wise correlations
            double rhLh = CalculateCorrelation(rhActivations, lhActivations);
            double rhRf = CalculateCorrelation(rhActivations, rfActivations);
            double rhLf = CalculateCorrelation(rhActivations, lfActivations);
            double lhRf = CalculateCorrelation(lhActivations, rfActivations);
            double lhLf = CalculateCorrelation(lhActivations, lfActivations);
            double rfLf = CalculateCorrelation(rfActivations, lfActivations);

            // Average decorrelation (inverted correlation) as independence measure
            double avgCorrelation = (Math.Abs(rhLh) + Math.Abs(rhRf) + Math.Abs(rhLf) +
                                     Math.Abs(lhRf) + Math.Abs(lhLf) + Math.Abs(rfLf)) / 6.0;

            // Count how many limbs are actually active
            int activeLimbs = CountActiveLimbs();

            // Scale by active limbs - more limbs being independent is harder
            double limbFactor = activeLimbs switch
            {
                1 => 0,
                2 => 1.0,
                3 => 1.5,
                4 => 2.0,
                _ => 0
            };

            // Independence = decorrelation * limb factor
            return (1.0 - avgCorrelation) * limbFactor * 5.0;
        }

        /// <summary>
        /// Analyze dynamic independence - different velocities across limbs.
        /// </summary>
        private double AnalyzeDynamicIndependence()
        {
            // Get velocity patterns for each limb
            var rhVels = historyWindow.Where(s => s.RightHandActive).Select(s => s.RightHandVelocity).ToArray();
            var lhVels = historyWindow.Where(s => s.LeftHandActive).Select(s => s.LeftHandVelocity).ToArray();
            var rfVels = historyWindow.Where(s => s.RightFootActive).Select(s => s.RightFootVelocity).ToArray();

            if (rhVels.Length < 2 || lhVels.Length < 2)
                return 0;

            double rhMean = rhVels.Average();
            double lhMean = lhVels.Average();
            double rfMean = rfVels.Length > 0 ? rfVels.Average() : 0;

            var means = new[] { rhMean, lhMean, rfMean }.Where(m => m > 0).ToArray();
            if (means.Length < 2) return 0;

            double overallMean = means.Average();
            double variance = means.Select(m => Math.Pow(m - overallMean, 2)).Average();

            double contrast = Math.Sqrt(variance) / 40.0;

            // Bonus for ghost notes (very low velocity on one limb while others are loud)
            bool hasGhostNotes = means.Min() < 50 && means.Max() > 90;
            if (hasGhostNotes)
                contrast += 2.0;

            return Math.Min(10.0, contrast * 5.0);
        }

        /// <summary>
        /// Analyze metric independence - different subdivisions/meters between limbs.
        /// </summary>
        private double AnalyzeMetricIndependence()
        {
            // Analyze periodicity of each limb
            var rhPeriod = DetectPeriodicity(historyWindow.Select(s => s.RightHandActive).ToArray());
            var lhPeriod = DetectPeriodicity(historyWindow.Select(s => s.LeftHandActive).ToArray());
            var rfPeriod = DetectPeriodicity(historyWindow.Select(s => s.RightFootActive).ToArray());

            // Check if periods are coprime (indicating polymeter)
            bool rhLhCoprime = GCD(rhPeriod, lhPeriod) == 1 && rhPeriod > 1 && lhPeriod > 1;
            bool rhRfCoprime = GCD(rhPeriod, rfPeriod) == 1 && rhPeriod > 1 && rfPeriod > 1;
            bool lhRfCoprime = GCD(lhPeriod, rfPeriod) == 1 && lhPeriod > 1 && rfPeriod > 1;

            double score = 0;

            if (rhLhCoprime) score += 3.0;
            if (rhRfCoprime) score += 3.0;
            if (lhRfCoprime) score += 3.0;

            // Bonus for all three being coprime (true 3-way metric independence)
            if (rhLhCoprime && rhRfCoprime && lhRfCoprime)
                score += 4.0;

            return Math.Min(10.0, score);
        }

        /// <summary>
        /// Analyze textural independence - different techniques on different limbs.
        /// </summary>
        private double AnalyzeTexturalIndependence()
        {
            int rhTechniques = rightHand.RecentTechniques.Distinct().Count();
            int lhTechniques = leftHand.RecentTechniques.Distinct().Count();
            int rfTechniques = rightFoot.RecentTechniques.Distinct().Count();
            int lfTechniques = leftFoot.RecentTechniques.Distinct().Count();

            int totalUniqueTechniques = rhTechniques + lhTechniques + rfTechniques + lfTechniques;

            double score = totalUniqueTechniques * 0.8;

            // Bonus if simultaneously using different techniques
            bool simultaneousDifferent = (rhTechniques >= 2 || lhTechniques >= 2) &&
                                         rightHand.RecentTechniques.Any() &&
                                         leftHand.RecentTechniques.Any() &&
                                         !rightHand.RecentTechniques.Intersect(leftHand.RecentTechniques).Any();

            if (simultaneousDifferent)
                score += 3.0;

            return Math.Min(10.0, score);
        }

        /// <summary>
        /// Count number of actively playing limbs.
        /// </summary>
        private int CountActiveLimbs()
        {
            int count = 0;
            int recentCount = Math.Min(16, historyWindow.Count);
            var recent = historyWindow.TakeLast(recentCount).ToList();

            if (recent.Any(s => s.RightHandActive)) count++;
            if (recent.Any(s => s.LeftHandActive)) count++;
            if (recent.Any(s => s.RightFootActive)) count++;
            if (recent.Any(s => s.LeftFootActive)) count++;

            return count;
        }

        /// <summary>
        /// Calculate full correlation matrix between all limb pairs.
        /// </summary>
        private double[,] CalculateCorrelationMatrix()
        {
            var matrix = new double[4, 4];

            var activations = new[]
            {
                historyWindow.Select(s => s.RightHandActive ? 1.0 : 0.0).ToArray(),
                historyWindow.Select(s => s.LeftHandActive ? 1.0 : 0.0).ToArray(),
                historyWindow.Select(s => s.RightFootActive ? 1.0 : 0.0).ToArray(),
                historyWindow.Select(s => s.LeftFootActive ? 1.0 : 0.0).ToArray()
            };

            for (int i = 0; i < 4; i++)
            {
                for (int j = 0; j < 4; j++)
                {
                    matrix[i, j] = i == j ? 1.0 : CalculateCorrelation(activations[i], activations[j]);
                }
            }

            return matrix;
        }

        /// <summary>
        /// Calculate phase complexity - how limbs drift in/out of phase.
        /// </summary>
        private double CalculatePhaseComplexity()
        {
            if (historyWindow.Count < 8) return 0;

            double phaseChanges = 0;
            double prevPhase = 0;

            for (int i = 1; i < historyWindow.Count; i++)
            {
                var curr = historyWindow[i];

                int coincident = 0;
                int total = 0;

                if (curr.RightHandActive) total++;
                if (curr.LeftHandActive) total++;
                if (curr.RightFootActive) total++;
                if (curr.LeftFootActive) total++;

                if (curr.RightHandActive && curr.LeftHandActive) coincident++;
                if (curr.RightHandActive && curr.RightFootActive) coincident++;
                if (curr.LeftHandActive && curr.RightFootActive) coincident++;

                double phase = total > 1 ? (double)coincident / (total - 1) : 1;

                if (Math.Abs(phase - prevPhase) > 0.3)
                    phaseChanges++;

                prevPhase = phase;
            }

            return Math.Min(10.0, phaseChanges * 0.5);
        }

        /// <summary>
        /// Calculate overall independence score.
        /// </summary>
        private double CalculateOverallScore(IndependenceResult result)
        {
            double score = 0;

            // Rhythmic independence is most important
            score += result.RhythmicIndependence * 0.35;
            score += result.DynamicIndependence * 0.20;
            score += result.MetricIndependence * 0.20;
            score += result.TexturalIndependence * 0.15;
            score += result.PhaseComplexity * 0.10;

            // Active limb multiplier
            double limbMultiplier = result.ActiveLimbCount switch
            {
                1 => 0.3,
                2 => 0.6,
                3 => 0.85,
                4 => 1.0,
                _ => 0.3
            };

            return score * limbMultiplier;
        }

        /// <summary>
        /// Generate human-readable breakdown.
        /// </summary>
        private string GenerateBreakdown(IndependenceResult result)
        {
            var parts = new List<string>();

            if (result.RhythmicIndependence > 6)
                parts.Add("Strong rhythmic independence");
            else if (result.RhythmicIndependence > 3)
                parts.Add("Moderate rhythmic independence");

            if (result.DynamicIndependence > 5)
                parts.Add("Dynamic contrast between limbs");

            if (result.MetricIndependence > 3)
                parts.Add("Polymetric elements");

            if (result.TexturalIndependence > 4)
                parts.Add("Multiple simultaneous techniques");

            if (result.ActiveLimbCount == 4)
                parts.Add("Full 4-way coordination");
            else if (result.ActiveLimbCount == 3)
                parts.Add("3-limb coordination");

            return parts.Count > 0 ? string.Join(", ", parts) : "Basic coordination";
        }

        // Math/Analysis utilities
        private double CalculateCorrelation(double[] x, double[] y)
        {
            if (x.Length != y.Length || x.Length < 2) return 0;

            double xMean = x.Average();
            double yMean = y.Average();

            double numerator = 0;
            double xVar = 0, yVar = 0;

            for (int i = 0; i < x.Length; i++)
            {
                double xDiff = x[i] - xMean;
                double yDiff = y[i] - yMean;
                numerator += xDiff * yDiff;
                xVar += xDiff * xDiff;
                yVar += yDiff * yDiff;
            }

            if (xVar < 0.0001 || yVar < 0.0001) return 0;

            return numerator / Math.Sqrt(xVar * yVar);
        }

        private int DetectPeriodicity(bool[] activations)
        {
            if (activations.Length < 4) return 1;

            for (int period = 2; period <= Math.Min(8, activations.Length / 2); period++)
            {
                int matches = 0;
                int comparisons = 0;

                for (int i = 0; i < activations.Length - period; i++)
                {
                    if (activations[i] == activations[i + period])
                        matches++;
                    comparisons++;
                }

                if (comparisons > 0 && (double)matches / comparisons > 0.8)
                    return period;
            }

            return 1;
        }

        private static int GCD(int a, int b)
        {
            while (b != 0)
            {
                int t = b;
                b = a % b;
                a = t;
            }
            return Math.Max(1, Math.Abs(a));
        }

        /// <summary>
        /// Internal class to track individual limb activity.
        /// </summary>
        private class LimbVoice
        {
            public string Name { get; }
            public List<double> RecentTimes { get; } = new();
            public List<double> RecentIntervals { get; } = new();
            public List<double> RecentVelocities { get; } = new();
            public List<string> RecentTechniques { get; } = new();

            private const int MAX_HISTORY = 32;

            public LimbVoice(string name)
            {
                Name = name;
            }

            public void RecordEvent(double time, double interval, double velocity, string technique)
            {
                RecentTimes.Add(time);
                RecentIntervals.Add(interval);
                RecentVelocities.Add(velocity);
                RecentTechniques.Add(technique);

                while (RecentTimes.Count > MAX_HISTORY)
                {
                    RecentTimes.RemoveAt(0);
                    RecentIntervals.RemoveAt(0);
                    RecentVelocities.RemoveAt(0);
                    RecentTechniques.RemoveAt(0);
                }
            }

            public double AverageInterval => RecentIntervals.Count > 0 ? RecentIntervals.Average() : 0;
            public double AverageVelocity => RecentVelocities.Count > 0 ? RecentVelocities.Average() : 0;
        }

        /// <summary>
        /// Snapshot of limb states at a point in time.
        /// </summary>
        private class LimbSnapshot
        {
            public double Time { get; set; }
            public double DeltaTime { get; set; }
            public bool RightHandActive { get; set; }
            public bool LeftHandActive { get; set; }
            public bool RightFootActive { get; set; }
            public bool LeftFootActive { get; set; }
            public double RightHandVelocity { get; set; }
            public double LeftHandVelocity { get; set; }
            public double RightFootVelocity { get; set; }
            public double LeftFootVelocity { get; set; }
        }
    }

    /// <summary>
    /// Results from independence analysis.
    /// </summary>
    public class IndependenceResult
    {
        public double RhythmicIndependence { get; set; }
        public double DynamicIndependence { get; set; }
        public double MetricIndependence { get; set; }
        public double TexturalIndependence { get; set; }
        public int ActiveLimbCount { get; set; }
        public double[,] CorrelationMatrix { get; set; } = new double[4, 4];
        public double PhaseComplexity { get; set; }
        public double OverallIndependence { get; set; }
        public string Breakdown { get; set; } = "";

        public string Level => OverallIndependence switch
        {
            < 2 => "Basic",
            < 4 => "Intermediate",
            < 6 => "Advanced",
            < 8 => "Expert",
            < 9 => "Elite",
            _ => "Transcendent"
        };
    }
}
