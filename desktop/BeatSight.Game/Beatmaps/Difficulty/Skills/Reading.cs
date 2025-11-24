using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// ENHANCED Reading Skill v2.0 - Visual Processing Model
    /// 
    /// This skill measures sight-reading and visual processing difficulty.
    /// Critical for a drum learning application where users follow along.
    /// 
    /// Key innovations:
    /// - Visual working memory model (how many things to track at once)
    /// - Predictability scoring (can you anticipate what's coming?)
    /// - Visual saliency (what draws attention)
    /// - Information density per visual frame
    /// - Pattern recognition load
    /// - Metric confusion potential
    /// 
    /// This is distinct from playing difficulty - a simple but unpredictable
    /// pattern might be easy to play but hard to read.
    /// </summary>
    public class Reading : Skill
    {
        protected override double SkillMultiplier => 18.0; // Increased from 15.0
        protected override double StrainDecayBase => 0.38;

        // ========================
        // VISUAL PROCESSING STATE
        // ========================

        // History for pattern prediction
        private readonly List<double> deltaTimeHistory = new();
        private readonly List<int> noteCountHistory = new();
        private readonly List<HashSet<DrumType>> drumHistory = new();
        private const int HISTORY_SIZE = 16;

        // Visual memory model
        private readonly Queue<double> visualLoadHistory = new();
        private const int VISUAL_MEMORY_SLOTS = 7; // Miller's law: 7 ± 2

        // Reading state
        private double lastDensitySpike = 0;
        private int consecutivePredictable = 0;
        private int consecutiveUnpredictable = 0;

        // Pattern recognition
        private readonly Dictionary<string, int> seenPatterns = new();
        private int totalPatternsSeen = 0;

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            // Update history
            deltaTimeHistory.Add(current.DeltaTime);
            noteCountHistory.Add(current.NoteCount);
            drumHistory.Add(current.DrumTypes.ToHashSet());
            if (deltaTimeHistory.Count > HISTORY_SIZE) deltaTimeHistory.RemoveAt(0);
            if (noteCountHistory.Count > HISTORY_SIZE) noteCountHistory.RemoveAt(0);
            if (drumHistory.Count > HISTORY_SIZE) drumHistory.RemoveAt(0);

            double strain = 0;

            // ========================
            // 1. VISUAL DENSITY
            // ========================
            strain += CalculateVisualDensity(current);

            // ========================
            // 2. DENSITY SPIKES
            // ========================
            strain += CalculateDensitySpikes(current);

            // ========================
            // 3. PATTERN PREDICTABILITY
            // ========================
            double predictability = CalculateEnhancedPredictability(current);
            strain += ApplyPredictabilityEffect(predictability);

            // ========================
            // 4. RHYTHMIC READABILITY
            // ========================
            strain += CalculateRhythmicReadability(current);

            // ========================
            // 5. VISUAL WORKING MEMORY LOAD
            // ========================
            strain += CalculateVisualMemoryLoad(current);

            // ========================
            // 6. VISUAL CHAOS (Movement + Density)
            // ========================
            strain += CalculateVisualChaos(current);

            // ========================
            // 7. TECHNIQUE VISUAL COMPLEXITY
            // ========================
            strain += CalculateTechniqueVisualComplexity(current);

            // ========================
            // 8. NOTE COUNT VARIATION
            // ========================
            strain += CalculateNoteCountVariation();

            // ========================
            // 9. INFORMATION OVERLOAD
            // ========================
            if (DetectInformationOverload(current))
            {
                strain *= 1.4;
            }

            // ========================
            // 10. METRIC CONFUSION
            // ========================
            strain += CalculateMetricConfusion(current);

            // ========================
            // 11. VISUAL SALIENCY COMPETITION
            // ========================
            strain += CalculateSaliencyCompetition(current);

            // ========================
            // 12. PATTERN FAMILIARITY
            // ========================
            strain += CalculatePatternFamiliarity(current);

            // Update visual load history
            visualLoadHistory.Enqueue(strain);
            if (visualLoadHistory.Count > HISTORY_SIZE)
                visualLoadHistory.Dequeue();

            return strain;
        }

        // ========================
        // VISUAL DENSITY CALCULATION
        // ========================

        private double CalculateVisualDensity(DifficultyHitObject current)
        {
            double strain = 0;

            // Base density
            double density = 1000.0 / Math.Max(current.StrainTime, 25.0);
            strain += density * 0.15;

            // Multiple simultaneous notes
            if (current.NoteCount > 1)
            {
                strain += current.NoteCount * 0.4;

                // Many simultaneous notes are visually overwhelming
                if (current.NoteCount > 3)
                    strain += (current.NoteCount - 3) * 0.3;
            }

            return strain;
        }

        // ========================
        // DENSITY SPIKES
        // ========================

        private double CalculateDensitySpikes(DifficultyHitObject current)
        {
            double strain = 0;

            if (deltaTimeHistory.Count >= 6)
            {
                double recentAvg = deltaTimeHistory.TakeLast(4).Average();
                double olderAvg = deltaTimeHistory.Take(4).Average();

                // Sudden increase in density
                if (recentAvg < olderAvg * 0.55)
                {
                    double spikeMultiplier = 1.0 + (olderAvg - recentAvg) / Math.Max(olderAvg, 1);
                    strain += Math.Min(spikeMultiplier, 2.5);
                    lastDensitySpike = current.StartTime;
                }

                // Recent spike = lingering reading difficulty
                if (current.StartTime - lastDensitySpike < 2500)
                {
                    strain += 0.5;
                }
            }

            return strain;
        }

        // ========================
        // ENHANCED PREDICTABILITY
        // ========================

        private double CalculateEnhancedPredictability(DifficultyHitObject current)
        {
            if (deltaTimeHistory.Count < 4) return 0.5;

            double predictability = 0;

            // 1. Timing consistency
            var recentDeltas = deltaTimeHistory.TakeLast(6).ToList();
            double avgDelta = recentDeltas.Average();
            double timingVariance = recentDeltas.Sum(d => Math.Pow(d - avgDelta, 2)) / recentDeltas.Count;
            double timingConsistency = 1.0 / (1.0 + timingVariance * 0.0005);
            predictability += timingConsistency * 0.3;

            // 2. Note count consistency
            var recentCounts = noteCountHistory.TakeLast(6).ToList();
            int uniqueCounts = recentCounts.Distinct().Count();
            double countConsistency = 1.0 / uniqueCounts;
            predictability += countConsistency * 0.25;

            // 3. Drum pattern consistency
            if (drumHistory.Count >= 4)
            {
                var recent = drumHistory.TakeLast(4).ToList();
                int similarPairs = 0;
                for (int i = 1; i < recent.Count; i++)
                {
                    int overlap = recent[i].Intersect(recent[i - 1]).Count();
                    int union = recent[i].Union(recent[i - 1]).Count();
                    if (union > 0 && (double)overlap / union > 0.5)
                        similarPairs++;
                }
                predictability += (similarPairs / 3.0) * 0.25;
            }

            // 4. Rhythm ratio consistency
            double ratioConsistency = Math.Abs(current.RhythmRatio - 1.0) < 0.15 ? 1.0 : 0.3;
            predictability += ratioConsistency * 0.2;

            return predictability;
        }

        private double ApplyPredictabilityEffect(double predictability)
        {
            double strain = 0;

            if (predictability > 0.75)
            {
                // Very predictable = easier to read
                consecutivePredictable++;
                consecutiveUnpredictable = 0;
                strain -= 0.3 * Math.Min(consecutivePredictable, 5) * 0.1;
            }
            else if (predictability < 0.35)
            {
                // Unpredictable = harder to read
                consecutiveUnpredictable++;
                consecutivePredictable = 0;
                strain += 1.5 + 0.2 * Math.Min(consecutiveUnpredictable, 8);
            }
            else
            {
                consecutivePredictable = Math.Max(0, consecutivePredictable - 1);
                consecutiveUnpredictable = Math.Max(0, consecutiveUnpredictable - 1);
            }

            return strain;
        }

        // ========================
        // RHYTHMIC READABILITY
        // ========================

        private double CalculateRhythmicReadability(DifficultyHitObject current)
        {
            double strain = 0;

            // Off-beat notes are harder to follow
            if (current.IsSyncopated)
            {
                strain += 1.2;

                // Consecutive syncopation
                if (current.Previous?.IsSyncopated == true)
                    strain += 0.5;
            }

            // Grid deviation
            strain += current.GridDeviation * 3.0;

            // Complex rhythm ratios
            if (!IsSimpleRatio(current.RhythmRatio) && Math.Abs(current.RhythmRatio - 1.0) > 0.1)
            {
                strain += 2.0;

                // Polyrhythmic ratios are especially hard to read
                if (IsPolyrhythmicRatio(current.RhythmRatio))
                    strain += 1.5;
            }

            return strain;
        }

        // ========================
        // VISUAL WORKING MEMORY
        // ========================

        private double CalculateVisualMemoryLoad(DifficultyHitObject current)
        {
            double strain = 0;

            // Count distinct elements to track
            int elementsToTrack = 0;

            // Different drum types
            elementsToTrack += current.DrumTypes.Distinct().Count();

            // Techniques add visual elements
            elementsToTrack += current.Techniques.Where(t => t != TechniqueType.Normal).Count();

            // Dynamics add information
            if (current.VelocityRange > 0.3)
                elementsToTrack++;

            // Exceeding visual memory capacity
            if (elementsToTrack > VISUAL_MEMORY_SLOTS)
            {
                double overloadFactor = (elementsToTrack - VISUAL_MEMORY_SLOTS) * 0.5;
                strain += overloadFactor;
            }

            // Sustained high memory load
            if (visualLoadHistory.Count >= 6)
            {
                double avgLoad = visualLoadHistory.Average();
                if (avgLoad > 3.0)
                {
                    strain += (avgLoad - 3.0) * 0.3;
                }
            }

            return strain;
        }

        // ========================
        // VISUAL CHAOS
        // ========================

        private double CalculateVisualChaos(DifficultyHitObject current)
        {
            double strain = 0;

            // Movement across visual field
            if (current.TravelDistance > 0.3)
            {
                strain += current.TravelDistance * 1.0;
            }

            // Fast movement
            if (current.MovementSpeed > 1.0)
            {
                strain += current.MovementSpeed * 0.5;
            }

            // Simultaneous movement and density
            if (current.TravelDistance > 0.4 && current.DeltaTime < 100)
            {
                strain += 1.5;
            }

            return strain;
        }

        // ========================
        // TECHNIQUE VISUAL COMPLEXITY
        // ========================

        private double CalculateTechniqueVisualComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            foreach (var tech in current.Techniques)
            {
                strain += tech switch
                {
                    // Ghost notes are subtle and easy to miss
                    TechniqueType.GhostNote => 0.8,

                    // Grace notes require visual attention
                    TechniqueType.Flam or TechniqueType.Drag => 0.5,

                    // Rolls are visually distinct but need tracking
                    TechniqueType.Roll or TechniqueType.BuzzRoll => 0.3,

                    // Chokes need visual anticipation
                    TechniqueType.Choke => 0.4,

                    // Most others don't significantly impact reading
                    _ => 0
                };
            }

            // Multiple techniques = visual complexity
            int techCount = current.Techniques.Count(t => t != TechniqueType.Normal);
            if (techCount > 1)
                strain += techCount * 0.3;

            return strain;
        }

        // ========================
        // NOTE COUNT VARIATION
        // ========================

        private double CalculateNoteCountVariation()
        {
            if (noteCountHistory.Count < 6) return 0;

            var recent = noteCountHistory.TakeLast(6).ToList();
            int countVariance = recent.Distinct().Count();

            if (countVariance > 2)
            {
                return (countVariance - 2) * 0.4;
            }

            return 0;
        }

        // ========================
        // INFORMATION OVERLOAD
        // ========================

        private bool DetectInformationOverload(DifficultyHitObject current)
        {
            // When everything is happening at once
            return current.DeltaTime < 75 &&
                   current.NoteCount > 2 &&
                   current.TravelDistance > 0.4;
        }

        // ========================
        // METRIC CONFUSION
        // ========================

        private double CalculateMetricConfusion(DifficultyHitObject current)
        {
            double strain = 0;

            // Odd meters are harder to follow
            if (current.CurrentTimeSignature.IsOddMeter)
            {
                strain += 1.0;

                // Very unusual meters
                if (current.CurrentTimeSignature.Numerator > 9)
                    strain += 0.5;
            }

            // Metric modulation is very confusing
            if (current.IsMetricModulation)
            {
                strain += 2.5;
            }

            // Polyrhythm visual confusion
            if (!string.IsNullOrEmpty(current.PolyrhythmType))
            {
                strain += 1.5;
            }

            return strain;
        }

        // ========================
        // SALIENCY COMPETITION
        // ========================

        private double CalculateSaliencyCompetition(DifficultyHitObject current)
        {
            if (current.NoteCount <= 1) return 0;

            double strain = 0;

            // When multiple visually prominent elements compete for attention
            var drums = current.DrumTypes.ToList();

            int prominentCount = 0;
            if (drums.Contains(DrumType.Crash) || drums.Contains(DrumType.China))
                prominentCount++;
            if (drums.Contains(DrumType.Snare) && current.Techniques.Contains(TechniqueType.Accent))
                prominentCount++;
            if (drums.Contains(DrumType.Kick))
                prominentCount++;

            if (prominentCount > 1)
            {
                strain += prominentCount * 0.4;
            }

            return strain;
        }

        // ========================
        // PATTERN FAMILIARITY
        // ========================

        private double CalculatePatternFamiliarity(DifficultyHitObject current)
        {
            // Track pattern frequency
            string patternKey = CreatePatternKey(current);

            if (!seenPatterns.ContainsKey(patternKey))
                seenPatterns[patternKey] = 0;
            seenPatterns[patternKey]++;
            totalPatternsSeen++;

            // Novel patterns are harder to read
            double frequency = (double)seenPatterns[patternKey] / Math.Max(totalPatternsSeen, 1);

            if (frequency < 0.05)
                return 1.0; // Very unfamiliar
            else if (frequency < 0.15)
                return 0.5; // Somewhat unfamiliar

            return 0;
        }

        private string CreatePatternKey(DifficultyHitObject current)
        {
            var drums = string.Join(",", current.DrumTypes.OrderBy(d => d).Take(3));
            var rhythmClass = current.RhythmRatio < 0.75 ? "F" : (current.RhythmRatio > 1.25 ? "S" : "N");
            return $"{drums}_{rhythmClass}_{current.NoteCount}";
        }

        // ========================
        // HELPER METHODS
        // ========================

        private static bool IsSimpleRatio(double ratio)
        {
            double[] simple = { 1.0, 2.0, 0.5, 4.0, 0.25, 3.0, 0.333 };
            return simple.Any(r => Math.Abs(ratio - r) < 0.1);
        }

        private static bool IsPolyrhythmicRatio(double ratio)
        {
            double[] poly = { 1.5, 0.666, 1.333, 0.75, 1.25, 0.8, 1.75, 0.571 };
            return poly.Any(r => Math.Abs(ratio - r) < 0.08);
        }
    }
}
