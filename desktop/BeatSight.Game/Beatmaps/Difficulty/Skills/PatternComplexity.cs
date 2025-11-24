using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// ENHANCED Pattern Complexity Skill v2.0 - Musical Intelligence
    /// 
    /// Evaluates the compositional and orchestrational sophistication of drum patterns.
    /// Goes beyond "how hard to play" to measure "how creative/complex is the writing."
    /// 
    /// Key concepts:
    /// - Pattern novelty and non-repetitiveness
    /// - Kit coverage and orchestration breadth
    /// - Fill sophistication (not just speed, but creativity)
    /// - Linear vs. layered pattern complexity
    /// - Section transitions and song structure awareness
    /// - Groove uniqueness (departure from standard patterns)
    /// - Voice leading and melodic movement
    /// - Dynamic orchestration (using timbre for expression)
    /// </summary>
    public class PatternComplexity : Skill
    {
        protected override double SkillMultiplier => 22.0; // Increased from 18.0
        protected override double StrainDecayBase => 0.22;

        // ========================
        // PATTERN STATE TRACKING
        // ========================

        // Pattern history
        private readonly List<List<DrumType>> patternHistory = new();
        private readonly List<HashSet<DrumType>> recentDrumSets = new();
        private readonly List<PatternFingerprint> fingerprintHistory = new();
        private const int PATTERN_HISTORY_SIZE = 20;

        // Fill detection
        private int potentialFillLength = 0;
        private bool inFill = false;
        private readonly List<DrumType> currentFillPath = new();

        // Groove analysis
        private readonly Dictionary<string, int> groovePatternCounts = new();
        private int measurePosition = 0;

        // Voice leading
        private double lastAveragePosition = 0;
        private readonly List<double> positionHistory = new();

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;

            // Update history
            patternHistory.Add(current.DrumTypes);
            recentDrumSets.Add(current.DrumTypes.ToHashSet());
            var fingerprint = CreatePatternFingerprint(current);
            fingerprintHistory.Add(fingerprint);

            if (patternHistory.Count > PATTERN_HISTORY_SIZE) patternHistory.RemoveAt(0);
            if (recentDrumSets.Count > PATTERN_HISTORY_SIZE) recentDrumSets.RemoveAt(0);
            if (fingerprintHistory.Count > PATTERN_HISTORY_SIZE) fingerprintHistory.RemoveAt(0);

            // ========================
            // 1. PATTERN NOVELTY
            // ========================
            double noveltyScore = CalculateEnhancedNovelty(current, fingerprint);
            strain += noveltyScore * 2.0;

            // ========================
            // 2. KIT COVERAGE (ORCHESTRATION BREADTH)
            // ========================
            strain += CalculateKitCoverage();

            // ========================
            // 3. PATTERN ENTROPY
            // ========================
            strain += current.PatternEntropy * 2.5;

            // ========================
            // 4. FILL ANALYSIS
            // ========================
            strain += AnalyzeFill(current);

            // ========================
            // 5. GROOVE UNIQUENESS
            // ========================
            double grooveUniqueness = CalculateEnhancedGrooveUniqueness(current);
            strain += grooveUniqueness * 1.5;

            // ========================
            // 6. ORCHESTRATION COMPLEXITY
            // ========================
            strain += CalculateOrchestrationComplexity(current);

            // ========================
            // 7. KIT MOVEMENT ANALYSIS
            // ========================
            strain += AnalyzeMovementPattern(current);

            // ========================
            // 8. LINEAR PATTERN ANALYSIS
            // ========================
            if (current.IsLinear)
            {
                strain += CalculateLinearComplexity(current);
            }

            // ========================
            // 9. SECTION TRANSITION DETECTION
            // ========================
            if (IsLikelyTransition())
            {
                strain += 2.5;
            }

            // ========================
            // 10. EFFECT CYMBAL USAGE
            // ========================
            strain += CalculateEffectCymbalUsage(current);

            // ========================
            // 11. VOICE LEADING COMPLEXITY
            // ========================
            strain += CalculateVoiceLeading(current);

            // ========================
            // 12. PATTERN DEVELOPMENT
            // ========================
            strain += CalculatePatternDevelopment();

            // Track measure position (simplified)
            measurePosition = (measurePosition + 1) % 16;

            return strain;
        }

        // ========================
        // PATTERN FINGERPRINT
        // ========================

        private class PatternFingerprint
        {
            public HashSet<DrumType> DrumTypes { get; set; } = new();
            public bool IsSyncopated { get; set; }
            public double RhythmRatio { get; set; }
            public int NoteCount { get; set; }
            public double AveragePosition { get; set; }
        }

        private PatternFingerprint CreatePatternFingerprint(DifficultyHitObject current)
        {
            return new PatternFingerprint
            {
                DrumTypes = current.DrumTypes.ToHashSet(),
                IsSyncopated = current.IsSyncopated,
                RhythmRatio = current.RhythmRatio,
                NoteCount = current.NoteCount,
                AveragePosition = current.DrumTypes.Count > 0
                    ? current.DrumTypes.Select(d => GetDrumPosition(d).x).Average()
                    : 0
            };
        }

        // ========================
        // ENHANCED NOVELTY CALCULATION
        // ========================

        private double CalculateEnhancedNovelty(DifficultyHitObject current, PatternFingerprint fingerprint)
        {
            if (fingerprintHistory.Count < 4) return 1.0;

            double novelty = 0;
            int recentMatches = 0;

            // Check against recent fingerprints
            for (int i = fingerprintHistory.Count - 2; i >= Math.Max(0, fingerprintHistory.Count - 8); i--)
            {
                var historic = fingerprintHistory[i];
                double similarity = CalculateFingerprintSimilarity(fingerprint, historic);

                if (similarity > 0.8)
                    recentMatches++;
            }

            // Novelty inversely related to matches
            if (recentMatches == 0)
                novelty = 1.5; // Very novel
            else if (recentMatches == 1)
                novelty = 1.0; // Somewhat novel
            else if (recentMatches < 4)
                novelty = 0.5; // Moderate repetition
            else
                novelty = 0.2; // Highly repetitive

            // Bonus for introducing new drum types
            var allRecentDrums = recentDrumSets.TakeLast(8).SelectMany(s => s).ToHashSet();
            var newDrums = fingerprint.DrumTypes.Except(allRecentDrums).Count();
            novelty += newDrums * 0.5;

            return novelty;
        }

        private double CalculateFingerprintSimilarity(PatternFingerprint a, PatternFingerprint b)
        {
            // Drum type overlap
            double drumSimilarity = 0;
            if (a.DrumTypes.Count > 0 && b.DrumTypes.Count > 0)
            {
                int overlap = a.DrumTypes.Intersect(b.DrumTypes).Count();
                drumSimilarity = (double)overlap / Math.Max(a.DrumTypes.Count, b.DrumTypes.Count);
            }

            // Rhythm similarity
            double rhythmSimilarity = Math.Abs(a.RhythmRatio - b.RhythmRatio) < 0.1 ? 1.0 : 0;

            // Note count similarity
            double countSimilarity = a.NoteCount == b.NoteCount ? 1.0 : 0.5;

            return (drumSimilarity * 0.5 + rhythmSimilarity * 0.3 + countSimilarity * 0.2);
        }

        // ========================
        // KIT COVERAGE
        // ========================

        private double CalculateKitCoverage()
        {
            double strain = 0;

            if (recentDrumSets.Count < 8) return 0;

            int uniqueDrums = recentDrumSets.TakeLast(8)
                .SelectMany(s => s)
                .Distinct()
                .Count();

            // More variety = more complex orchestration
            if (uniqueDrums > 3)
                strain += (uniqueDrums - 3) * 0.5;
            if (uniqueDrums > 5)
                strain += (uniqueDrums - 5) * 0.4;
            if (uniqueDrums > 7)
                strain += (uniqueDrums - 7) * 0.3; // Exceptional coverage

            // Bonus for using non-standard voices
            var hasEffects = recentDrumSets.TakeLast(8).Any(s =>
                s.Contains(DrumType.China) ||
                s.Contains(DrumType.Stack) ||
                s.Contains(DrumType.Splash));
            if (hasEffects)
                strain += 0.5;

            return strain;
        }

        // ========================
        // FILL ANALYSIS
        // ========================

        private double AnalyzeFill(DifficultyHitObject current)
        {
            double strain = 0;
            bool isFillCandidate = IsPotentialFill(current);

            if (isFillCandidate)
            {
                potentialFillLength++;
                inFill = true;
                currentFillPath.AddRange(current.DrumTypes);

                // Base fill strain
                strain += 0.5;

                // Longer fills are harder
                if (potentialFillLength > 4)
                    strain += 0.3 * Math.Min(potentialFillLength - 4, 12);

                // Fast fills
                if (current.DeltaTime < 100)
                    strain += 1.5;
                if (current.DeltaTime < 60)
                    strain += 1.0;

                // Fill using many toms (around-the-kit)
                int tomCount = current.DrumTypes.Count(IsTomType);
                if (tomCount > 0)
                    strain += tomCount * 0.6;

                // Multiple toms in one hit
                if (tomCount > 1)
                    strain += 0.5;

                // Fill path complexity
                if (currentFillPath.Count >= 4)
                {
                    double pathComplexity = CalculateFillPathComplexity();
                    strain += pathComplexity;
                }
            }
            else
            {
                if (inFill && potentialFillLength > 3)
                {
                    // End of fill - award completion bonus
                    double fillBonus = potentialFillLength * 0.25;

                    // Longer, more complex fills
                    if (potentialFillLength > 8)
                        fillBonus += 1.0;

                    // Check if fill ended with crash
                    if (current.DrumTypes.Contains(DrumType.Crash))
                        fillBonus += 0.8;

                    strain += fillBonus;
                }

                potentialFillLength = 0;
                inFill = false;
                currentFillPath.Clear();
            }

            return strain;
        }

        private double CalculateFillPathComplexity()
        {
            if (currentFillPath.Count < 4) return 0;

            // Analyze the path of the fill around the kit
            var positions = currentFillPath.Select(d => GetDrumPosition(d).x).ToList();

            // Direction changes
            int directionChanges = 0;
            double lastDirection = 0;

            for (int i = 1; i < positions.Count; i++)
            {
                double direction = positions[i] - positions[i - 1];
                if (lastDirection != 0 && Math.Sign(direction) != Math.Sign(lastDirection))
                    directionChanges++;
                lastDirection = direction;
            }

            // Voice variety in fill
            int uniqueVoices = currentFillPath.Distinct().Count();

            return directionChanges * 0.3 + uniqueVoices * 0.2;
        }

        // ========================
        // GROOVE UNIQUENESS
        // ========================

        private double CalculateEnhancedGrooveUniqueness(DifficultyHitObject current)
        {
            double uniqueness = 0;

            // Track groove patterns
            string grooveKey = CreateGrooveKey(current);
            if (!groovePatternCounts.ContainsKey(grooveKey))
                groovePatternCounts[grooveKey] = 0;
            groovePatternCounts[grooveKey]++;

            // Rare groove pattern = unique
            int totalPatterns = groovePatternCounts.Values.Sum();
            double patternFrequency = (double)groovePatternCounts[grooveKey] / Math.Max(totalPatterns, 1);

            if (patternFrequency < 0.1)
                uniqueness += 1.5; // Very unique
            else if (patternFrequency < 0.2)
                uniqueness += 0.8; // Somewhat unique

            // Standard pattern deviation
            bool hasSnare = current.DrumTypes.Contains(DrumType.Snare);
            bool hasKick = current.DrumTypes.Contains(DrumType.Kick);
            bool hasHat = current.DrumTypes.Contains(DrumType.HiHat);

            // Snare on unusual beat positions
            if (hasSnare && current.IsSyncopated)
                uniqueness += 1.0;

            // Ghost snare placement
            if (hasSnare && current.Techniques.Contains(TechniqueType.GhostNote))
                uniqueness += 0.8;

            // Kick patterns with interesting placement
            if (hasKick && current.GridDeviation > 0.1)
                uniqueness += 0.7;

            // Double kick pattern creativity
            if (hasKick && current.IsDoubleBass && current.IsSyncopated)
                uniqueness += 1.0;

            // Hi-hat variation beyond straight 8ths/16ths
            if (hasHat && Math.Abs(current.RhythmRatio - 1.0) > 0.1 && Math.Abs(current.RhythmRatio - 0.5) > 0.1)
                uniqueness += 0.5;

            return uniqueness;
        }

        private string CreateGrooveKey(DifficultyHitObject current)
        {
            // Create a simple key representing the groove pattern
            var drums = string.Join(",", current.DrumTypes.OrderBy(d => d).Select(d => d.ToString()));
            var rhythmClass = current.RhythmRatio < 0.8 ? "S" : (current.RhythmRatio > 1.2 ? "L" : "N");
            return $"{drums}_{rhythmClass}_{(current.IsSyncopated ? "Y" : "N")}";
        }

        // ========================
        // ORCHESTRATION COMPLEXITY
        // ========================

        private double CalculateOrchestrationComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Playing different drums at once = complex voicing
            if (current.NoteCount > 1)
            {
                var types = current.DrumTypes.Distinct().ToList();

                // Different drum types at once
                if (types.Count > 1)
                {
                    strain += types.Count * 0.5;

                    // Analyze specific voicings
                    bool hasCymbal = types.Any(IsCymbalType);
                    bool hasTom = types.Any(IsTomType);
                    bool hasSnare = types.Contains(DrumType.Snare);
                    bool hasKick = types.Contains(DrumType.Kick);

                    // Tom + Cymbal (orchestral accent)
                    if (hasTom && hasCymbal)
                        strain += 0.6;

                    // Full kit hit
                    if (hasSnare && hasKick && hasCymbal)
                        strain += 1.0;

                    // Stacked toms (multiple toms together)
                    if (types.Count(IsTomType) > 1)
                        strain += 0.8;

                    // Unusual cymbal combinations
                    if (types.Count(IsCymbalType) > 1)
                        strain += 0.7;
                }
            }

            // Timbral variety over time
            if (recentDrumSets.Count >= 8)
            {
                var recentTimbres = recentDrumSets.TakeLast(8)
                    .SelectMany(s => s.Select(GetTimbreClass))
                    .Distinct()
                    .Count();

                if (recentTimbres > 3)
                    strain += (recentTimbres - 3) * 0.3;
            }

            return strain;
        }

        // ========================
        // LINEAR PATTERN COMPLEXITY
        // ========================

        private double CalculateLinearComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Linear drumming has its own complexity metric
            // One voice at a time, but the sequence matters

            if (patternHistory.Count >= 6)
            {
                var recentVoices = patternHistory.TakeLast(6).SelectMany(p => p).ToList();

                // Voice changes in linear pattern
                int voiceChanges = 0;
                for (int i = 1; i < recentVoices.Count; i++)
                {
                    if (recentVoices[i] != recentVoices[i - 1])
                        voiceChanges++;
                }

                // Many voice changes = complex linear pattern
                if (voiceChanges > 3)
                    strain += voiceChanges * 0.35;

                // Check for odd groupings in linear pattern
                var uniqueVoices = recentVoices.Distinct().Count();
                if (uniqueVoices >= 4)
                    strain += 1.0;
            }

            // Speed of linear pattern
            if (current.DeltaTime < 80)
                strain += 0.5;

            return strain;
        }

        // ========================
        // MOVEMENT ANALYSIS
        // ========================

        private double AnalyzeMovementPattern(DifficultyHitObject current)
        {
            double strain = 0;

            // Calculate average position
            double avgPosition = current.DrumTypes.Count > 0
                ? current.DrumTypes.Select(d => GetDrumPosition(d).x).Average()
                : lastAveragePosition;

            positionHistory.Add(avgPosition);
            if (positionHistory.Count > 12) positionHistory.RemoveAt(0);

            // Movement distance
            double movement = Math.Abs(avgPosition - lastAveragePosition);
            if (movement > 0.3)
                strain += movement * 0.6;

            // Zigzag pattern detection
            if (positionHistory.Count >= 4)
            {
                int directionChanges = 0;
                double lastDirection = 0;

                for (int i = 1; i < positionHistory.Count; i++)
                {
                    double direction = positionHistory[i] - positionHistory[i - 1];
                    if (Math.Abs(direction) > 0.1)
                    {
                        if (lastDirection != 0 && Math.Sign(direction) != Math.Sign(lastDirection))
                            directionChanges++;
                        lastDirection = direction;
                    }
                }

                // Zigzag patterns are cognitively demanding
                if (directionChanges >= 3)
                    strain += directionChanges * 0.25;
            }

            lastAveragePosition = avgPosition;
            return strain;
        }

        // ========================
        // VOICE LEADING
        // ========================

        private double CalculateVoiceLeading(DifficultyHitObject current)
        {
            // Melodic/tonal movement around the kit
            if (patternHistory.Count < 4) return 0;

            double strain = 0;

            // Get pitch-like ordering of drums
            var recentPitches = patternHistory.TakeLast(4)
                .Select(p => p.Count > 0 ? p.Max(d => GetDrumPitch(d)) : 0)
                .ToList();

            // Check for melodic contour (ascending or descending patterns)
            bool ascending = recentPitches[0] < recentPitches[1] && recentPitches[1] < recentPitches[2];
            bool descending = recentPitches[0] > recentPitches[1] && recentPitches[1] > recentPitches[2];

            // Reward clear directional movement across drums
            if (ascending || descending)
            {
                strain += 0.8;
            }

            // Complex contour (up then down, etc.)
            if (recentPitches.Distinct().Count() >= 3)
            {
                bool hasArc = (recentPitches[0] < recentPitches[1] && recentPitches[1] > recentPitches[2]) ||
                              (recentPitches[0] > recentPitches[1] && recentPitches[1] < recentPitches[2]);
                if (hasArc)
                    strain += 0.6;
            }

            return strain;
        }

        // ========================
        // PATTERN DEVELOPMENT
        // ========================

        private double CalculatePatternDevelopment()
        {
            // Detect if the pattern is "developing" over time
            // (Adding elements, building complexity)
            if (fingerprintHistory.Count < 12) return 0;

            double strain = 0;

            var firstQuarter = fingerprintHistory.Take(4).ToList();
            var lastQuarter = fingerprintHistory.TakeLast(4).ToList();

            // Compare average complexity
            double earlyComplexity = firstQuarter.Average(f => f.NoteCount + f.DrumTypes.Count * 0.5);
            double lateComplexity = lastQuarter.Average(f => f.NoteCount + f.DrumTypes.Count * 0.5);

            // Growing complexity = development
            if (lateComplexity > earlyComplexity * 1.3)
                strain += 1.0;

            return strain;
        }

        // ========================
        // EFFECT CYMBAL USAGE
        // ========================

        private double CalculateEffectCymbalUsage(DifficultyHitObject current)
        {
            double strain = 0;

            if (current.DrumTypes.Contains(DrumType.Stack))
                strain += 0.6;
            if (current.DrumTypes.Contains(DrumType.China))
                strain += 0.5;
            if (current.DrumTypes.Contains(DrumType.Splash))
                strain += 0.4;

            // Effect cymbals at interesting moments
            if ((current.DrumTypes.Contains(DrumType.China) || current.DrumTypes.Contains(DrumType.Stack)) &&
                current.IsSyncopated)
                strain += 0.5;

            return strain;
        }

        // ========================
        // HELPER METHODS
        // ========================

        private bool IsPotentialFill(DifficultyHitObject current)
        {
            bool hasToms = current.DrumTypes.Any(IsTomType);
            bool isMoving = current.TravelDistance > 0.3;
            bool isFast = current.DeltaTime < 150;
            bool isNonRepetitive = patternHistory.Count >= 2 &&
                !current.DrumTypes.ToHashSet().SetEquals(patternHistory[patternHistory.Count - 1].ToHashSet());

            return hasToms || (isMoving && isFast && isNonRepetitive);
        }

        private bool IsLikelyTransition()
        {
            if (patternHistory.Count < 8) return false;

            bool hasCrash = patternHistory.Last().Contains(DrumType.Crash);
            if (hasCrash && potentialFillLength > 2)
                return true;

            // Check for pattern discontinuity
            var firstHalf = patternHistory.Take(4).SelectMany(p => p).ToHashSet();
            var secondHalf = patternHistory.Skip(4).Take(4).SelectMany(p => p).ToHashSet();

            int overlap = firstHalf.Intersect(secondHalf).Count();
            int total = firstHalf.Union(secondHalf).Count();

            return total > 0 && (double)overlap / total < 0.35;
        }

        private static bool IsTomType(DrumType t) =>
            t == DrumType.Tom || t == DrumType.TomHigh || t == DrumType.TomMid || t == DrumType.TomLow;

        private static bool IsCymbalType(DrumType t) =>
            t == DrumType.Crash || t == DrumType.Ride || t == DrumType.China ||
            t == DrumType.Splash || t == DrumType.Stack;

        private static string GetTimbreClass(DrumType t) => t switch
        {
            DrumType.Kick => "Low",
            DrumType.Snare => "Mid",
            DrumType.TomLow => "Low-Mid",
            DrumType.Tom or DrumType.TomMid => "Mid",
            DrumType.TomHigh => "High-Mid",
            DrumType.HiHat or DrumType.HiHatPedal => "High",
            DrumType.Crash or DrumType.Splash or DrumType.China or DrumType.Stack => "Bright",
            DrumType.Ride or DrumType.RideBell => "Wash",
            _ => "Other"
        };

        private static double GetDrumPitch(DrumType t) => t switch
        {
            DrumType.Kick => 1,
            DrumType.TomLow => 2,
            DrumType.Tom or DrumType.TomMid => 3,
            DrumType.TomHigh => 4,
            DrumType.Snare => 5,
            DrumType.HiHat or DrumType.HiHatPedal => 6,
            DrumType.Ride or DrumType.RideBell => 7,
            DrumType.Crash or DrumType.Splash => 8,
            DrumType.China or DrumType.Stack => 9,
            _ => 5
        };

        private static (double x, double y) GetDrumPosition(DrumType type) => type switch
        {
            DrumType.Kick => (0, 0.6),
            DrumType.Snare => (-0.4, 0.7),
            DrumType.HiHat => (-1.0, 0.8),
            DrumType.HiHatPedal => (-0.9, 0.4),
            DrumType.TomHigh => (-0.2, 1.1),
            DrumType.TomMid => (0.3, 1.1),
            DrumType.Tom => (0.0, 1.1),
            DrumType.TomLow => (0.8, 0.8),
            DrumType.Crash => (-0.8, 1.4),
            DrumType.Ride => (0.9, 1.2),
            DrumType.RideBell => (0.85, 1.15),
            DrumType.China => (1.2, 1.3),
            DrumType.Splash => (-0.5, 1.3),
            DrumType.Stack => (0.4, 1.4),
            _ => (0, 1.0)
        };
    }
}
