using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps.Difficulty;

namespace BeatSight.Game.Beatmaps.Difficulty.Analysis
{
    /// <summary>
    /// GROOVE ANALYZER - Quantifying "Feel" and Rhythmic Pocket
    /// 
    /// This analyzer captures the elusive quality of "groove" - the subtle timing,
    /// dynamic, and articulation choices that make a drum performance "feel" good.
    /// This is distinct from raw rhythmic complexity; a simple pattern with excellent
    /// groove is different from a complex pattern with poor feel.
    /// 
    /// KEY CONCEPTS:
    /// 
    /// 1. MICRO-TIMING ANALYSIS
    ///    - Swing ratio detection (ratio of long to short in swing pairs)
    ///    - Consistent push/pull against the grid (ahead/behind the beat)
    ///    - Timing variance consistency (tight vs loose feel)
    /// 
    /// 2. DYNAMIC CONTOUR
    ///    - Ghost note density and placement
    ///    - Accent patterns and their regularity
    ///    - Dynamic range within groove patterns
    ///    - Velocity consistency on repeating elements
    /// 
    /// 3. POCKET CONSISTENCY
    ///    - How well the same groove elements match each other
    ///    - Intentional vs unintentional timing deviation
    ///    - Pattern recognition for repeating grooves
    /// 
    /// 4. FEEL CLASSIFICATION
    ///    - Straight vs Shuffle vs Half-Time Shuffle
    ///    - Swing percentage (0% = straight, 66% = triplet swing)
    ///    - Groove family identification
    /// 
    /// DIFFICULTY IMPLICATIONS:
    /// - Executing a specific groove feel precisely is HARD
    /// - Maintaining consistent groove over time requires skill
    /// - Complex grooves (half-time shuffle, implied polyrhythms) are advanced
    /// - Dynamic groove control (ghost notes, accents) is expert-level
    /// </summary>
    public class GrooveAnalyzer
    {
        // Swing ratio tracking
        private readonly Queue<double> swingRatios = new();
        private const int SWING_HISTORY_SIZE = 16;

        // Timing deviation tracking
        private readonly Queue<double> timingDeviations = new();
        private const int TIMING_HISTORY_SIZE = 32;

        // Dynamic tracking
        private readonly Queue<double> velocityHistory = new();
        private const int VELOCITY_HISTORY_SIZE = 32;

        // Pattern detection
        private readonly Queue<PatternElement> patternElements = new();
        private const int PATTERN_HISTORY_SIZE = 64;

        // Groove state
        private GrooveType detectedGroove = GrooveType.Straight;
        private double swingPercentage = 0;
        private double pocketTightness = 1.0;
        private double dynamicGrooveScore = 0;

        /// <summary>
        /// Analyze a hit object for groove characteristics.
        /// Returns a GrooveAnalysisResult with difficulty contribution and analysis data.
        /// </summary>
        public GrooveAnalysisResult Analyze(DifficultyHitObject current)
        {
            var result = new GrooveAnalysisResult();

            if (current.DeltaTime <= 0 || current.Previous == null)
                return result;

            double grooveDifficulty = 0;

            // 1. Swing/Shuffle Detection
            grooveDifficulty += AnalyzeSwing(current);

            // 2. Pocket Analysis
            grooveDifficulty += AnalyzePocket(current);

            // 3. Dynamic Groove
            grooveDifficulty += AnalyzeDynamicGroove(current);

            // 4. Pattern Consistency
            grooveDifficulty += AnalyzePatternConsistency(current);

            // 5. Feel Classification Bonus
            grooveDifficulty += GetFeelDifficultyBonus();

            // Update state
            UpdateHistory(current);

            // Build result
            result.DetectedGroove = detectedGroove;
            result.SwingPercentage = swingPercentage;
            result.PocketTightness = pocketTightness;
            result.DynamicRange = dynamicGrooveScore;
            result.SwingAmount = swingPercentage / 100.0;
            result.GrooveComplexity = grooveDifficulty;
            result.DominantFeel = detectedGroove.ToString();

            return result;
        }

        /// <summary>
        /// Analyze swing/shuffle characteristics.
        /// </summary>
        private double AnalyzeSwing(DifficultyHitObject current)
        {
            double difficulty = 0;

            // Calculate swing ratio from rhythm ratio
            double ratio = current.RhythmRatio;

            // Detect swing pairs (long-short alternation)
            if (ratio > 1.0 && ratio < 3.0)
            {
                swingRatios.Enqueue(ratio);
                if (swingRatios.Count > SWING_HISTORY_SIZE)
                    swingRatios.Dequeue();
            }
            else if (ratio > 0.33 && ratio < 1.0)
            {
                swingRatios.Enqueue(1.0 / ratio);
                if (swingRatios.Count > SWING_HISTORY_SIZE)
                    swingRatios.Dequeue();
            }

            // Analyze swing consistency
            if (swingRatios.Count >= 4)
            {
                var ratios = swingRatios.ToList();
                double avgSwing = ratios.Average();
                double variance = ratios.Select(r => Math.Pow(r - avgSwing, 2)).Average();

                // Detect swing type
                if (avgSwing > 1.4 && avgSwing < 2.2)
                {
                    // This is swing/shuffle territory
                    detectedGroove = avgSwing > 1.8 ? GrooveType.TripletShuffle : GrooveType.Swing;
                    swingPercentage = (avgSwing - 1.0) / 1.0 * 100; // 0% = straight, 100% = triplet

                    // Swing difficulty scales with:
                    // 1. How extreme the swing is
                    // 2. How consistent you need to be
                    difficulty += Math.Abs(avgSwing - 1.5) * 2.0; // Deviation from "standard" swing

                    // Consistent swing is harder than sloppy swing
                    if (variance < 0.05)
                    {
                        difficulty += 2.0; // Very consistent swing = high skill
                    }

                    // Heavy swing (triplet feel) is harder
                    if (avgSwing > 1.9)
                    {
                        difficulty += 1.5;
                    }

                    // Light swing (almost straight) requires precision
                    if (avgSwing < 1.3 && variance < 0.03)
                    {
                        difficulty += 1.0;
                    }
                }
            }

            return difficulty;
        }

        /// <summary>
        /// Analyze pocket consistency (timing tightness).
        /// </summary>
        private double AnalyzePocket(DifficultyHitObject current)
        {
            double difficulty = 0;

            // Grid deviation indicates pocket character
            double deviation = current.GridDeviation;
            timingDeviations.Enqueue(deviation);
            if (timingDeviations.Count > TIMING_HISTORY_SIZE)
                timingDeviations.Dequeue();

            if (timingDeviations.Count >= 8)
            {
                var deviations = timingDeviations.ToList();
                double avgDeviation = deviations.Average();
                double deviationVariance = deviations.Select(d => Math.Pow(d - avgDeviation, 2)).Average();

                // Update pocket tightness (lower variance = tighter pocket)
                pocketTightness = 1.0 / (1.0 + Math.Sqrt(deviationVariance) * 10);

                // Very tight pocket at speed requires high skill
                if (pocketTightness > 0.8 && current.DeltaTime < 100)
                {
                    difficulty += pocketTightness * 2.5;
                }

                // Consistent push/pull (playing consistently behind/ahead)
                // This is intentional feel, not sloppiness
                if (Math.Abs(avgDeviation) > 0.03 && Math.Abs(avgDeviation) < 0.15)
                {
                    if (deviationVariance < 0.02)
                    {
                        // Intentional, consistent push/pull
                        difficulty += 2.0;

                        // Behind the beat (laid back) is a jazz characteristic
                        if (avgDeviation > 0)
                        {
                            difficulty += 0.5;
                        }
                    }
                }

                // Extreme tightness (machine-like) is actually difficult to maintain
                if (deviationVariance < 0.001 && current.DeltaTime < 120)
                {
                    difficulty += 1.5;
                }
            }

            return difficulty;
        }

        /// <summary>
        /// Analyze dynamic groove characteristics.
        /// </summary>
        private double AnalyzeDynamicGroove(DifficultyHitObject current)
        {
            double difficulty = 0;

            velocityHistory.Enqueue(current.AverageVelocity);
            if (velocityHistory.Count > VELOCITY_HISTORY_SIZE)
                velocityHistory.Dequeue();

            if (velocityHistory.Count >= 8)
            {
                var velocities = velocityHistory.ToList();
                double avgVelocity = velocities.Average();
                double velRange = velocities.Max() - velocities.Min();
                double velVariance = velocities.Select(v => Math.Pow(v - avgVelocity, 2)).Average();

                // Ghost note integration (wide dynamic range with consistent main hits)
                bool hasGhosts = current.Techniques.Contains(TechniqueType.GhostNote);

                if (hasGhosts || velRange > 0.4)
                {
                    // Dynamic groove playing
                    difficulty += velRange * 3.0;

                    // Consistent dynamic pattern (e.g., regular accent pattern)
                    if (velVariance < 0.05 && velRange > 0.3)
                    {
                        difficulty += 2.0; // Controlled dynamics = skill
                    }

                    dynamicGrooveScore = velRange;
                }

                // Accent pattern analysis
                var recentVelocities = velocities.TakeLast(8).ToList();
                int accentPattern = DetectAccentPattern(recentVelocities);
                if (accentPattern > 0 && accentPattern != 4)
                {
                    // Non-standard accent pattern (not 4/4 backbeat)
                    difficulty += 1.5 + (accentPattern > 4 ? 1.0 : 0);
                }
            }

            return difficulty;
        }

        /// <summary>
        /// Analyze pattern consistency for groove repetition.
        /// </summary>
        private double AnalyzePatternConsistency(DifficultyHitObject current)
        {
            double difficulty = 0;

            // Create pattern element
            var element = new PatternElement
            {
                DrumTypes = current.DrumTypes.ToHashSet(),
                RelativeVelocity = current.AverageVelocity,
                RhythmRatio = current.RhythmRatio,
                HasGhost = current.Techniques.Contains(TechniqueType.GhostNote)
            };

            patternElements.Enqueue(element);
            if (patternElements.Count > PATTERN_HISTORY_SIZE)
                patternElements.Dequeue();

            // Look for repeating groove patterns
            if (patternElements.Count >= 16)
            {
                var elements = patternElements.ToList();

                // Check for common pattern lengths (4, 8, 16 beats)
                foreach (int patternLen in new[] { 4, 8, 16 })
                {
                    if (elements.Count >= patternLen * 2)
                    {
                        double consistency = CalculatePatternConsistency(elements, patternLen);

                        if (consistency > 0.7)
                        {
                            // Consistent groove pattern - requires skill to maintain
                            difficulty += consistency * 1.5;

                            // Complex repeating patterns (longer or with variations)
                            if (patternLen >= 8 && consistency > 0.8)
                            {
                                difficulty += 1.0;
                            }
                            break;
                        }
                    }
                }
            }

            return difficulty;
        }

        /// <summary>
        /// Get difficulty bonus based on detected feel type.
        /// </summary>
        private double GetFeelDifficultyBonus()
        {
            return detectedGroove switch
            {
                GrooveType.Straight => 0,
                GrooveType.Swing => 1.5,
                GrooveType.TripletShuffle => 2.0,
                GrooveType.HalfTimeShuffle => 3.5, // Purdie shuffle, Rosanna - very hard
                GrooveType.Train => 2.0,
                GrooveType.SecondLine => 2.5,
                GrooveType.Linear => 2.0,
                _ => 0
            };
        }

        private void UpdateHistory(DifficultyHitObject current)
        {
            // Detect half-time shuffle characteristics
            if (detectedGroove == GrooveType.TripletShuffle &&
                current.Techniques.Contains(TechniqueType.GhostNote) &&
                dynamicGrooveScore > 0.3)
            {
                detectedGroove = GrooveType.HalfTimeShuffle;
            }
        }

        /// <summary>
        /// Detect accent pattern length from velocity history.
        /// </summary>
        private int DetectAccentPattern(List<double> velocities)
        {
            double threshold = velocities.Average() + velocities.Max() * 0.3;

            var accentPositions = new List<int>();
            for (int i = 0; i < velocities.Count; i++)
            {
                if (velocities[i] > threshold)
                    accentPositions.Add(i);
            }

            if (accentPositions.Count < 2) return 0;

            // Calculate intervals
            var intervals = new List<int>();
            for (int i = 1; i < accentPositions.Count; i++)
            {
                intervals.Add(accentPositions[i] - accentPositions[i - 1]);
            }

            if (intervals.Count == 0) return 0;

            // Find most common interval
            var groups = intervals.GroupBy(i => i).OrderByDescending(g => g.Count());
            return groups.First().Key;
        }

        /// <summary>
        /// Calculate consistency of a pattern repeating at a given length.
        /// </summary>
        private double CalculatePatternConsistency(List<PatternElement> elements, int patternLength)
        {
            if (elements.Count < patternLength * 2) return 0;

            int matches = 0;
            int comparisons = 0;

            for (int i = patternLength; i < elements.Count; i++)
            {
                var current = elements[i];
                var reference = elements[i % patternLength];

                // Compare elements
                double similarity = ComputeElementSimilarity(current, reference);
                if (similarity > 0.7)
                    matches++;
                comparisons++;
            }

            return comparisons > 0 ? (double)matches / comparisons : 0;
        }

        private double ComputeElementSimilarity(PatternElement a, PatternElement b)
        {
            double score = 0;

            // Drum type similarity
            int overlap = a.DrumTypes.Intersect(b.DrumTypes).Count();
            int union = a.DrumTypes.Union(b.DrumTypes).Count();
            if (union > 0)
                score += (double)overlap / union * 0.4;

            // Velocity similarity
            double velDiff = Math.Abs(a.RelativeVelocity - b.RelativeVelocity);
            score += (1.0 - velDiff) * 0.3;

            // Rhythm similarity
            double ratioSim = 1.0 - Math.Min(Math.Abs(a.RhythmRatio - b.RhythmRatio), 1.0);
            score += ratioSim * 0.2;

            // Ghost note match
            if (a.HasGhost == b.HasGhost)
                score += 0.1;

            return score;
        }

        /// <summary>
        /// Get current groove analysis results.
        /// </summary>
        public GrooveAnalysisResult GetResults()
        {
            return new GrooveAnalysisResult
            {
                DetectedGroove = detectedGroove,
                SwingPercentage = swingPercentage,
                PocketTightness = pocketTightness,
                DynamicRange = dynamicGrooveScore
            };
        }

        private class PatternElement
        {
            public HashSet<DrumType> DrumTypes { get; set; } = new();
            public double RelativeVelocity { get; set; }
            public double RhythmRatio { get; set; }
            public bool HasGhost { get; set; }
        }
    }

    /// <summary>
    /// Types of groove feel.
    /// </summary>
    public enum GrooveType
    {
        Straight,        // No swing
        Swing,           // Light swing (50-60%)
        TripletShuffle,  // Heavy swing (66%)
        HalfTimeShuffle, // Purdie/Rosanna shuffle
        Train,           // Train beat
        SecondLine,      // New Orleans style
        Linear           // Linear groove (no overlapping hits)
    }

    /// <summary>
    /// Results of groove analysis.
    /// </summary>
    public class GrooveAnalysisResult
    {
        public GrooveType DetectedGroove { get; set; }
        public double SwingPercentage { get; set; }
        public double PocketTightness { get; set; }
        public double DynamicRange { get; set; }

        /// <summary>
        /// Swing amount as a 0-1 fraction (0 = straight, 0.33 = triplet shuffle).
        /// </summary>
        public double SwingAmount { get; set; }

        /// <summary>
        /// Overall groove complexity score.
        /// </summary>
        public double GrooveComplexity { get; set; }

        /// <summary>
        /// String representation of the dominant groove feel.
        /// </summary>
        public string DominantFeel { get; set; } = "Straight";
    }
}
