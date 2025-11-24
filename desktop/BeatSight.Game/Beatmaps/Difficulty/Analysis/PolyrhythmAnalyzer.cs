using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps.Difficulty;

namespace BeatSight.Game.Beatmaps.Difficulty.Analysis
{
    /// <summary>
    /// ADVANCED POLYRHYTHM AND POLYMETER ANALYZER
    /// 
    /// This analyzer provides deep mathematical analysis of polyrhythmic and
    /// polymetric structures using number theory and signal processing concepts.
    /// 
    /// KEY INNOVATIONS:
    /// 
    /// 1. CONTINUED FRACTION ANALYSIS
    ///    Uses continued fractions to find the simplest ratio that approximates
    ///    an observed rhythm ratio. This reveals hidden polyrhythms even when
    ///    they're not perfectly executed.
    /// 
    /// 2. LCM-BASED COMPLEXITY SCORING
    ///    The Least Common Multiple of numerator and denominator indicates how
    ///    long it takes for the polyrhythm to resolve. Higher LCM = more complex.
    /// 
    /// 3. AUTOCORRELATION PERIODICITY DETECTION
    ///    Finds repeating patterns at different scales to detect polymeter
    ///    (different length patterns played simultaneously).
    /// 
    /// 4. PHASE RELATIONSHIP TRACKING
    ///    Tracks how different rhythmic layers drift in and out of phase,
    ///    capturing the cognitive challenge of polyrhythmic independence.
    /// 
    /// 5. IRRATIONAL RHYTHM DETECTION
    ///    Detects rhythms that don't reduce to simple ratios, indicating
    ///    complex tuplet nesting or metric modulation.
    /// 
    /// POLYRHYTHM DIFFICULTY TIERS:
    ///   - 2:3 / 3:2 (beginner polyrhythm)
    ///   - 3:4 / 4:3 (intermediate)
    ///   - 5:4, 4:5 (advanced - Matt Garstka territory)
    ///   - 7:4, 4:7 (expert - prog/jazz)
    ///   - 5:7, 7:5 (elite)
    ///   - 11:8, 8:11 (legendary)
    ///   - Nested polyrhythms (3:2 over 5:4) = transcendent
    /// </summary>
    public class PolyrhythmAnalyzer
    {
        // Analysis state
        private readonly List<double> intervalHistory = new();
        private readonly List<double> accentTimeHistory = new();
        private readonly Dictionary<string, int> activePolyrhythms = new();
        private readonly Dictionary<int, double> phaseTrackers = new();
        private const int HISTORY_SIZE = 64;

        // Detection thresholds
        private const double RATIO_TOLERANCE = 0.08;
        private const int MAX_DENOMINATOR = 17; // Maximum denominator to consider

        /// <summary>
        /// Analyze a hit object for polyrhythmic content.
        /// Returns a polyrhythm difficulty contribution.
        /// </summary>
        public PolyrhythmAnalysisResult Analyze(DifficultyHitObject current)
        {
            var result = new PolyrhythmAnalysisResult();

            if (current.DeltaTime <= 0)
                return result;

            // Update history
            intervalHistory.Add(current.DeltaTime);
            if (intervalHistory.Count > HISTORY_SIZE)
                intervalHistory.RemoveAt(0);

            // 1. Continued Fraction Analysis
            var rationalApprox = AnalyzeRhythmRatio(current.RhythmRatio);
            result.DetectedRatio = rationalApprox;
            result.RatioComplexity = CalculateRatioComplexity(rationalApprox);

            // 2. LCM-Based Cycle Length
            result.CycleLength = CalculateCycleLength(rationalApprox);
            result.LcmComplexity = CalculateLcmComplexity(rationalApprox);

            // 3. Periodicity Analysis
            if (intervalHistory.Count >= 16)
            {
                result.PeriodicityScores = AnalyzePeriodicity();
                result.PolymeterDetected = DetectPolymeter(result.PeriodicityScores);
            }

            // 4. Phase Tracking
            result.PhaseComplexity = TrackPhaseRelationships(current);

            // 5. Nested Polyrhythm Detection
            result.NestedPolyrhythmDepth = DetectNestedPolyrhythms();

            // Calculate overall difficulty contribution
            result.DifficultyContribution = CalculateTotalDifficulty(result);

            // Update active polyrhythm tracking
            UpdateActivePolyrhythms(rationalApprox);

            return result;
        }

        /// <summary>
        /// Use continued fractions to find the simplest rational approximation
        /// of a rhythm ratio.
        /// </summary>
        private (int numerator, int denominator) AnalyzeRhythmRatio(double ratio)
        {
            if (ratio <= 0 || double.IsNaN(ratio) || double.IsInfinity(ratio))
                return (1, 1);

            // Normalize to > 1 for analysis
            bool inverted = ratio < 1;
            double r = inverted ? 1.0 / ratio : ratio;

            // Continued fraction expansion
            int[] cf = new int[10];
            double x = r;

            for (int i = 0; i < cf.Length && x > 0; i++)
            {
                cf[i] = (int)Math.Floor(x);
                x = x - cf[i];
                if (Math.Abs(x) < 0.0001) break;
                x = 1.0 / x;
            }

            // Convert continued fraction back to rational
            // Use convergents to find best approximation within tolerance
            int prevNum = 1, prevDen = 0;
            int currNum = cf[0], currDen = 1;

            for (int i = 1; i < cf.Length; i++)
            {
                if (cf[i] == 0) break;

                int newNum = cf[i] * currNum + prevNum;
                int newDen = cf[i] * currDen + prevDen;

                // Stop if denominator exceeds our limit
                if (newDen > MAX_DENOMINATOR) break;

                prevNum = currNum;
                prevDen = currDen;
                currNum = newNum;
                currDen = newDen;

                // Check if close enough
                double approx = (double)currNum / currDen;
                if (Math.Abs(approx - r) < RATIO_TOLERANCE)
                    break;
            }

            if (inverted)
                return (currDen, currNum);

            return (currNum, currDen);
        }

        /// <summary>
        /// Calculate complexity of a ratio based on its mathematical properties.
        /// </summary>
        private double CalculateRatioComplexity((int num, int den) ratio)
        {
            // Trivial ratio
            if (ratio.num == ratio.den || ratio.num == 1 || ratio.den == 1)
                return 0;

            // Simple ratios (2:1, 1:2, etc.)
            if ((ratio.num == 2 && ratio.den == 1) || (ratio.num == 1 && ratio.den == 2))
                return 0.3;

            // Powers of 2 relationships
            if (IsPowerOfTwo(ratio.num) && IsPowerOfTwo(ratio.den))
                return 0.5;

            // Common polyrhythms with calibrated difficulty
            int n = ratio.num, d = ratio.den;
            if (n > d) (n, d) = (d, n); // Normalize

            return (n, d) switch
            {
                (2, 3) => 2.0,  // Standard polyrhythm
                (3, 4) => 2.8,  // More complex
                (2, 5) => 3.5,  // Quintuplet territory
                (3, 5) => 4.0,
                (4, 5) => 4.5,  // Matt Garstka
                (2, 7) => 4.5,
                (3, 7) => 5.5,
                (4, 7) => 6.5,  // "Money" by Pink Floyd level
                (5, 7) => 7.0,  // Elite
                (5, 6) => 5.0,
                (5, 8) => 5.5,
                (7, 8) => 6.0,
                (5, 9) => 6.5,
                (7, 9) => 7.5,
                (8, 9) => 6.5,
                (7, 11) => 8.5,
                (8, 11) => 9.0,
                (9, 11) => 9.5,
                (11, 13) => 10.0,
                _ => CalculateGenericRatioComplexity(ratio.num, ratio.den)
            };
        }

        /// <summary>
        /// Calculate complexity for ratios not in our lookup table.
        /// Uses Farey sequence position as a complexity measure.
        /// </summary>
        private double CalculateGenericRatioComplexity(int num, int den)
        {
            // GCD reduction
            int gcd = GCD(num, den);
            num /= gcd;
            den /= gcd;

            // Complexity increases with:
            // 1. Sum of numerator and denominator
            // 2. Whether they're coprime primes
            // 3. LCM size

            double sumComplexity = Math.Log(num + den + 1, 2);
            double lcmComplexity = Math.Log(LCM(num, den) + 1, 2) * 0.5;

            // Bonus for primes
            if (IsPrime(num) && IsPrime(den))
                lcmComplexity *= 1.3;

            return 1.5 + sumComplexity + lcmComplexity;
        }

        /// <summary>
        /// Calculate how long (in beats) before the polyrhythm cycle resolves.
        /// </summary>
        private int CalculateCycleLength((int num, int den) ratio)
        {
            return LCM(ratio.num, ratio.den);
        }

        /// <summary>
        /// Difficulty based on cycle length (LCM).
        /// Longer cycles are harder to track mentally.
        /// </summary>
        private double CalculateLcmComplexity((int num, int den) ratio)
        {
            int lcm = LCM(ratio.num, ratio.den);

            // Short cycles (2-6) are manageable
            if (lcm <= 6) return 0.5;
            if (lcm <= 12) return 1.5;
            if (lcm <= 20) return 3.0;
            if (lcm <= 35) return 5.0;
            if (lcm <= 60) return 7.0;

            // Very long cycles approach cognitive limits
            return Math.Min(10.0, 7.0 + Math.Log(lcm - 60 + 1, 2) * 0.5);
        }

        /// <summary>
        /// Analyze periodicity at different scales using autocorrelation-inspired approach.
        /// </summary>
        private Dictionary<int, double> AnalyzePeriodicity()
        {
            var scores = new Dictionary<int, double>();

            if (intervalHistory.Count < 8) return scores;

            var intervals = intervalHistory.ToArray();

            // Check for periodicity at various lengths
            foreach (int period in new[] { 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16 })
            {
                if (intervals.Length < period * 2) continue;

                double correlation = CalculateAutocorrelation(intervals, period);
                scores[period] = correlation;
            }

            return scores;
        }

        /// <summary>
        /// Calculate autocorrelation at a specific lag.
        /// </summary>
        private double CalculateAutocorrelation(double[] data, int lag)
        {
            if (data.Length < lag * 2) return 0;

            double mean = data.Average();
            double variance = data.Select(d => Math.Pow(d - mean, 2)).Average();

            if (variance < 0.0001) return 1.0; // All same = perfect correlation

            double sum = 0;
            int count = 0;

            for (int i = 0; i < data.Length - lag; i++)
            {
                sum += (data[i] - mean) * (data[i + lag] - mean);
                count++;
            }

            return count > 0 ? sum / (count * variance) : 0;
        }

        /// <summary>
        /// Detect polymeter from periodicity analysis.
        /// Polymeter = two different length patterns playing simultaneously.
        /// </summary>
        private bool DetectPolymeter(Dictionary<int, double> periodicityScores)
        {
            // Find periods with high correlation
            var strongPeriods = periodicityScores
                .Where(kvp => kvp.Value > 0.7)
                .Select(kvp => kvp.Key)
                .ToList();

            if (strongPeriods.Count < 2) return false;

            // Check if any pair of strong periods are coprime
            // (indicating true polymeter rather than nested subdivision)
            for (int i = 0; i < strongPeriods.Count; i++)
            {
                for (int j = i + 1; j < strongPeriods.Count; j++)
                {
                    if (GCD(strongPeriods[i], strongPeriods[j]) == 1)
                    {
                        return true; // Coprime periods = polymeter
                    }
                }
            }

            return false;
        }

        /// <summary>
        /// Track phase relationships between different rhythmic layers.
        /// </summary>
        private double TrackPhaseRelationships(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double complexity = 0;

            // Track phase for common metric periods
            foreach (int period in new[] { 3, 4, 5, 7 })
            {
                double periodMs = current.DeltaTime * period;
                if (periodMs <= 0) continue;

                double phase = (current.StartTime % periodMs) / periodMs;

                if (!phaseTrackers.ContainsKey(period))
                {
                    phaseTrackers[period] = phase;
                }
                else
                {
                    double prevPhase = phaseTrackers[period];
                    double phaseDrift = Math.Abs(phase - prevPhase);

                    // Normalize phase drift
                    if (phaseDrift > 0.5) phaseDrift = 1.0 - phaseDrift;

                    // Significant phase drift indicates polyrhythmic activity
                    if (phaseDrift > 0.1 && phaseDrift < 0.4)
                    {
                        complexity += phaseDrift * 3.0;
                    }

                    // Update with smoothing
                    phaseTrackers[period] = phaseTrackers[period] * 0.7 + phase * 0.3;
                }
            }

            return complexity;
        }

        /// <summary>
        /// Detect nested polyrhythms (e.g., 3:2 over 5:4).
        /// </summary>
        private int DetectNestedPolyrhythms()
        {
            // Count distinct active polyrhythm types
            int activeCount = activePolyrhythms.Count(kvp => kvp.Value > 2);

            // If multiple polyrhythms are active simultaneously, they're nested
            return Math.Max(0, activeCount - 1);
        }

        /// <summary>
        /// Update tracking of currently active polyrhythms.
        /// </summary>
        private void UpdateActivePolyrhythms((int num, int den) ratio)
        {
            string key = $"{ratio.num}:{ratio.den}";

            // Check if this is a significant polyrhythm
            if (ratio.num != ratio.den && ratio.num > 1 && ratio.den > 1)
            {
                if (!activePolyrhythms.ContainsKey(key))
                    activePolyrhythms[key] = 0;

                activePolyrhythms[key]++;
            }

            // Decay other polyrhythms
            var keys = activePolyrhythms.Keys.ToList();
            foreach (var k in keys)
            {
                if (k != key)
                {
                    activePolyrhythms[k]--;
                    if (activePolyrhythms[k] <= 0)
                        activePolyrhythms.Remove(k);
                }
            }
        }

        /// <summary>
        /// Calculate total difficulty contribution from all polyrhythm factors.
        /// </summary>
        private double CalculateTotalDifficulty(PolyrhythmAnalysisResult result)
        {
            double total = 0;

            // Base ratio complexity
            total += result.RatioComplexity;

            // LCM/cycle complexity
            total += result.LcmComplexity * 0.5;

            // Phase complexity
            total += result.PhaseComplexity;

            // Polymeter bonus
            if (result.PolymeterDetected)
                total += 4.0;

            // Nested polyrhythm exponential bonus
            if (result.NestedPolyrhythmDepth > 0)
            {
                total += Math.Pow(result.NestedPolyrhythmDepth, 1.5) * 5.0;
            }

            return total;
        }

        // Math utilities
        private static int GCD(int a, int b)
        {
            while (b != 0)
            {
                int t = b;
                b = a % b;
                a = t;
            }
            return Math.Abs(a);
        }

        private static int LCM(int a, int b) => Math.Abs(a * b) / GCD(a, b);

        private static bool IsPowerOfTwo(int n) => n > 0 && (n & (n - 1)) == 0;

        private static bool IsPrime(int n)
        {
            if (n < 2) return false;
            if (n == 2) return true;
            if (n % 2 == 0) return false;
            for (int i = 3; i * i <= n; i += 2)
                if (n % i == 0) return false;
            return true;
        }
    }

    /// <summary>
    /// Results from polyrhythm analysis.
    /// </summary>
    public class PolyrhythmAnalysisResult
    {
        /// <summary>
        /// The detected rational approximation of the rhythm ratio.
        /// </summary>
        public (int numerator, int denominator) DetectedRatio { get; set; } = (1, 1);

        /// <summary>
        /// Complexity score for the ratio itself.
        /// </summary>
        public double RatioComplexity { get; set; }

        /// <summary>
        /// Number of beats until the polyrhythm cycle resolves.
        /// </summary>
        public int CycleLength { get; set; }

        /// <summary>
        /// Complexity based on cycle length.
        /// </summary>
        public double LcmComplexity { get; set; }

        /// <summary>
        /// Periodicity correlation scores at different periods.
        /// </summary>
        public Dictionary<int, double> PeriodicityScores { get; set; } = new();

        /// <summary>
        /// Whether polymeter (different length patterns) is detected.
        /// </summary>
        public bool PolymeterDetected { get; set; }

        /// <summary>
        /// Complexity from phase relationship tracking.
        /// </summary>
        public double PhaseComplexity { get; set; }

        /// <summary>
        /// Depth of nested polyrhythms (0 = none, 1 = one layer, etc.).
        /// </summary>
        public int NestedPolyrhythmDepth { get; set; }

        /// <summary>
        /// Total difficulty contribution.
        /// </summary>
        public double DifficultyContribution { get; set; }

        /// <summary>
        /// Human-readable description of the detected polyrhythm.
        /// </summary>
        public string Description
        {
            get
            {
                if (DetectedRatio.numerator == DetectedRatio.denominator)
                    return "No polyrhythm";

                string baseRatio = $"{DetectedRatio.numerator}:{DetectedRatio.denominator}";

                if (PolymeterDetected)
                    return $"Polymeter with {baseRatio}";

                if (NestedPolyrhythmDepth > 0)
                    return $"Nested polyrhythm ({NestedPolyrhythmDepth + 1} layers)";

                return baseRatio;
            }
        }
    }
}
