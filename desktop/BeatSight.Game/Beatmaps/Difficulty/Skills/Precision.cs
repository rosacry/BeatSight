using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// ENHANCED Precision Skill v2.0 - Timing Window Analysis
    /// 
    /// This skill measures how "tight" the execution needs to be:
    /// - Micro-timing precision (how small is the acceptable timing window?)
    /// - Dynamic (velocity) precision (how exact must the volume be?)
    /// - Groove consistency requirements (pocket/feel maintenance)
    /// - Sticking precision (stick placement, rebounding)
    /// 
    /// Key insight: Precision difficulty is about the MARGIN OF ERROR.
    /// Jazz and prog often require high precision due to rubato, dynamics,
    /// and subtle feel requirements. Even slow music can be high precision.
    /// 
    /// This skill uses a timing window model similar to rhythm games,
    /// but calibrated for real drumming tolerances.
    /// </summary>
    public class Precision : Skill
    {
        protected override double SkillMultiplier => 22.0; // Increased from 18.0
        protected override double StrainDecayBase => 0.18; // Medium-fast decay

        // ========================
        // PRECISION STATE
        // ========================

        // Timing tracking
        private readonly List<double> recentTimingDeviations = new();
        private readonly List<double> recentVelocities = new();
        private readonly List<double> recentGridDeviations = new();
        private const int TIMING_WINDOW = 20;

        // Groove tracking
        private readonly Queue<double> groovePattern = new();
        private const int GROOVE_WINDOW = 8;
        private double establishedGrooveFeel = 0;

        // Consecutive precision demand tracking
        private int consecutiveHighPrecision = 0;
        private int consecutiveDynamicPrecision = 0;

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;

            // ========================
            // 1. TIMING PRECISION
            // ========================
            strain += CalculateEnhancedTimingPrecision(current);

            // ========================
            // 2. DYNAMIC PRECISION
            // ========================
            strain += CalculateEnhancedDynamicPrecision(current);

            // ========================
            // 3. GROOVE PRECISION
            // ========================
            strain += CalculateEnhancedGroovePrecision(current);

            // ========================
            // 4. SYNCOPATION PRECISION
            // ========================
            strain += CalculateSyncopationPrecision(current);

            // ========================
            // 5. SPEED-PRECISION COMPOUND
            // ========================
            strain = ApplySpeedPrecisionScaling(strain, current);

            // ========================
            // 6. TECHNIQUE PRECISION
            // ========================
            strain += CalculateTechniquePrecision(current);

            // ========================
            // 7. HIT PLACEMENT PRECISION
            // ========================
            strain += CalculateHitPlacementPrecision(current);

            // ========================
            // 8. SUSTAINED PRECISION DEMAND
            // ========================
            strain += CalculateSustainedPrecisionDemand();

            // ========================
            // 9. MICRO-TIMING PRECISION
            // ========================
            strain += CalculateMicroTimingPrecision(current);

            // ========================
            // 10. COORDINATION PRECISION
            // ========================
            strain += CalculateCoordinationPrecision(current);

            // Update histories
            recentTimingDeviations.Add(current.GridDeviation);
            recentVelocities.Add(current.AverageVelocity);
            recentGridDeviations.Add(current.GridDeviation);

            if (recentTimingDeviations.Count > TIMING_WINDOW) recentTimingDeviations.RemoveAt(0);
            if (recentVelocities.Count > TIMING_WINDOW) recentVelocities.RemoveAt(0);
            if (recentGridDeviations.Count > TIMING_WINDOW) recentGridDeviations.RemoveAt(0);

            return strain;
        }

        // ========================
        // ENHANCED TIMING PRECISION
        // ========================

        private double CalculateEnhancedTimingPrecision(DifficultyHitObject current)
        {
            double timingStrain = 0;

            // ========================
            // GRID DEVIATION ANALYSIS
            // ========================
            if (current.GridDeviation > 0.03)
            {
                // Higher deviation = needs more precision to sound right
                double deviationStrain = current.GridDeviation * 4.0;

                // Swing/shuffle zone (deliberate deviation)
                if (current.GridDeviation > 0.12 && current.GridDeviation < 0.38)
                {
                    // This is likely intentional swing feel - requires precision to maintain
                    timingStrain += 2.0;

                    // Consistent swing is harder than random deviation
                    if (recentGridDeviations.Count >= 4)
                    {
                        double avgDev = recentGridDeviations.TakeLast(4).Average();
                        double devVariance = recentGridDeviations.TakeLast(4)
                            .Select(d => Math.Pow(d - avgDev, 2)).Average();

                        if (devVariance < 0.005) // Consistent swing
                            timingStrain += 1.5;
                    }
                }
                else
                {
                    timingStrain += deviationStrain;
                }
            }

            // ========================
            // TIMING WINDOW SIZE
            // ========================
            // Faster notes = smaller effective timing window
            double timingWindow = current.DeltaTime * 0.15; // ~15% of gap is acceptable

            if (timingWindow < 15) // Very tight window (<15ms)
            {
                double tightWindowBonus = (15 - timingWindow) / 10.0;
                timingStrain += tightWindowBonus * 2.0;
                consecutiveHighPrecision++;
            }
            else if (timingWindow < 25) // Tight window
            {
                timingStrain += 0.5;
                consecutiveHighPrecision++;
            }
            else
            {
                consecutiveHighPrecision = Math.Max(0, consecutiveHighPrecision - 1);
            }

            // ========================
            // METRIC MODULATION PRECISION
            // ========================
            if (current.IsMetricModulation)
            {
                timingStrain += 3.0; // Changing time feel requires precise execution
            }

            // ========================
            // ODD GROUPING PRECISION
            // ========================
            if (current.OddGrouping.HasValue)
            {
                int grouping = current.OddGrouping.Value;
                double groupingDifficulty = grouping switch
                {
                    5 => 2.0,   // Quintuplets
                    7 => 3.0,   // Septuplets
                    9 => 3.5,   // Nonuplets
                    11 => 4.0,
                    13 => 4.5,
                    _ => 1.5 + grouping * 0.25
                };
                timingStrain += groupingDifficulty;
            }

            // ========================
            // TIMING CONSISTENCY REQUIREMENT
            // ========================
            if (recentTimingDeviations.Count >= 6)
            {
                double avgDeviation = recentTimingDeviations.Average();
                double deviationVariance = recentTimingDeviations
                    .Select(d => Math.Pow(d - avgDeviation, 2)).Average();

                // Very consistent timing pattern = higher precision needed to maintain
                if (deviationVariance < 0.008 && avgDeviation > 0.08)
                {
                    timingStrain += 2.0;
                }

                // Alternating pattern (like swing)
                if (recentTimingDeviations.Count >= 4)
                {
                    bool isAlternating = true;
                    for (int i = 2; i < 4; i++)
                    {
                        double diff1 = recentTimingDeviations[i] - recentTimingDeviations[i - 1];
                        double diff2 = recentTimingDeviations[i - 1] - recentTimingDeviations[i - 2];
                        if (Math.Sign(diff1) == Math.Sign(diff2))
                        {
                            isAlternating = false;
                            break;
                        }
                    }
                    if (isAlternating)
                        timingStrain += 1.0;
                }
            }

            return timingStrain;
        }

        // ========================
        // ENHANCED DYNAMIC PRECISION
        // ========================

        private double CalculateEnhancedDynamicPrecision(DifficultyHitObject current)
        {
            double dynamicStrain = 0;

            // ========================
            // GHOST NOTE PRECISION
            // ========================
            if (current.Techniques.Contains(TechniqueType.GhostNote))
            {
                dynamicStrain += 2.5; // Ghost notes need very precise velocity

                // Ghost notes mixed with loud notes
                if (current.VelocityRange > 0.35)
                {
                    dynamicStrain += current.VelocityRange * 3.0;
                    consecutiveDynamicPrecision++;
                }
            }

            // ========================
            // DYNAMIC LAYERING PRECISION
            // ========================
            if (current.LimbCount > 1 && current.VelocityRange > 0.2)
            {
                // Playing different volumes simultaneously requires precision
                dynamicStrain += current.VelocityRange * current.LimbCount * 0.7;
            }

            // ========================
            // VELOCITY GRADIENT CONSISTENCY
            // ========================
            if (recentVelocities.Count >= 6)
            {
                // Check for crescendo/decrescendo patterns
                var recent = recentVelocities.TakeLast(6).ToList();
                double[] diffs = new double[recent.Count - 1];
                for (int i = 0; i < diffs.Length; i++)
                {
                    diffs[i] = recent[i + 1] - recent[i];
                }

                double avgDiff = diffs.Average();
                double diffVariance = diffs.Select(d => Math.Pow(d - avgDiff, 2)).Average();

                // Consistent gradient (crescendo/decrescendo)
                if (Math.Abs(avgDiff) > 0.015 && diffVariance < 0.008)
                {
                    // Smooth dynamic change requires precise control
                    dynamicStrain += 2.0 + Math.Abs(avgDiff) * 4.0;
                }

                // Check for specific dynamic patterns (e.g., accented patterns)
                if (diffs.Length >= 4)
                {
                    int signChanges = 0;
                    for (int i = 1; i < diffs.Length; i++)
                    {
                        if (Math.Sign(diffs[i]) != Math.Sign(diffs[i - 1]) &&
                            Math.Abs(diffs[i]) > 0.05)
                            signChanges++;
                    }
                    // Alternating dynamics
                    if (signChanges >= 3)
                        dynamicStrain += 1.5;
                }
            }

            // ========================
            // EXTREME DYNAMICS
            // ========================
            // Very soft playing
            if (current.AverageVelocity < 0.25)
            {
                dynamicStrain += (0.25 - current.AverageVelocity) * 4.0;
            }

            // Extreme velocity transitions
            if (current.Previous != null)
            {
                double velocityJump = Math.Abs(current.AverageVelocity - current.Previous.AverageVelocity);
                if (velocityJump > 0.5)
                {
                    dynamicStrain += velocityJump * 2.5;
                    consecutiveDynamicPrecision++;
                }
                else
                {
                    consecutiveDynamicPrecision = Math.Max(0, consecutiveDynamicPrecision - 1);
                }
            }

            return dynamicStrain;
        }

        // ========================
        // ENHANCED GROOVE PRECISION
        // ========================

        private double CalculateEnhancedGroovePrecision(DifficultyHitObject current)
        {
            double grooveStrain = 0;

            // Track groove pattern
            groovePattern.Enqueue(current.RhythmRatio);
            if (groovePattern.Count > GROOVE_WINDOW)
                groovePattern.Dequeue();

            // ========================
            // POCKET CONSISTENCY
            // ========================
            if (current.Previous != null && current.GetPrevious(1) != null)
            {
                var prev1 = current.Previous;
                var prev2 = current.GetPrevious(1)!;

                double ratio1 = current.DeltaTime / Math.Max(prev1.DeltaTime, 1);
                double ratio2 = prev1.DeltaTime / Math.Max(prev2.DeltaTime, 1);

                // Similar ratios = groove pattern that must be maintained
                if (Math.Abs(ratio1 - ratio2) < 0.08 && ratio1 != 1.0)
                {
                    grooveStrain += 1.5;

                    // Establish groove feel
                    establishedGrooveFeel = establishedGrooveFeel * 0.8 + ratio1 * 0.2;
                }
            }

            // ========================
            // GROOVE FEEL MAINTENANCE
            // ========================
            if (establishedGrooveFeel > 0 && current.RhythmRatio > 0)
            {
                double feelDeviation = Math.Abs(current.RhythmRatio - establishedGrooveFeel);
                if (feelDeviation < 0.1)
                {
                    // Maintaining the established feel
                    grooveStrain += 1.0;
                }
            }

            // ========================
            // BACKBEAT PRECISION
            // ========================
            if (current.DrumTypes.Contains(DrumType.Snare))
            {
                // Snare on 2 and 4 needs to be tight
                grooveStrain += 0.6;

                // Accented snare even more
                if (current.Techniques.Contains(TechniqueType.Accent) ||
                    current.Techniques.Contains(TechniqueType.Rimshot))
                {
                    grooveStrain += 0.4;
                }
            }

            // ========================
            // HI-HAT CONSISTENCY
            // ========================
            if (current.DrumTypes.Contains(DrumType.HiHat))
            {
                if (current.Previous?.DrumTypes.Contains(DrumType.HiHat) == true)
                {
                    // Consecutive hi-hats need consistent timing
                    grooveStrain += 0.4;

                    // Fast hi-hat patterns
                    if (current.DeltaTime < 100)
                        grooveStrain += 0.3;
                }
            }

            // ========================
            // LINEAR PATTERN PRECISION
            // ========================
            if (current.IsLinear && current.DeltaTime < 150)
            {
                grooveStrain += 1.2; // Linear needs precise timing between each hit
            }

            return grooveStrain;
        }

        // ========================
        // SYNCOPATION PRECISION
        // ========================

        private double CalculateSyncopationPrecision(DifficultyHitObject current)
        {
            double strain = 0;

            if (current.IsSyncopated)
            {
                strain += 1.5;

                // Off-beat syncopation needs precision to sound intentional
                if (current.GridDeviation > 0.08)
                {
                    strain += current.GridDeviation * 2.5;
                }

                // Fast syncopation
                if (current.DeltaTime < 100)
                {
                    strain += 1.0;
                }

                // Syncopation while maintaining groove
                if (establishedGrooveFeel > 0)
                {
                    strain += 0.8;
                }
            }

            return strain;
        }

        // ========================
        // SPEED-PRECISION SCALING
        // ========================

        private double ApplySpeedPrecisionScaling(double strain, DifficultyHitObject current)
        {
            // Precision at speed is exponentially harder
            if (current.DeltaTime < 80)
            {
                double speedMultiplier = 1.0 + Math.Pow((80 - current.DeltaTime) / 60.0, 1.5);
                strain *= speedMultiplier;
            }
            else if (current.DeltaTime < 120)
            {
                strain *= 1.0 + (120 - current.DeltaTime) / 150.0;
            }

            return strain;
        }

        // ========================
        // TECHNIQUE PRECISION
        // ========================

        private double CalculateTechniquePrecision(DifficultyHitObject current)
        {
            double strain = 0;

            // Certain techniques require high precision
            if (current.Techniques.Contains(TechniqueType.Flam))
            {
                strain += 1.5; // Flam gap must be precise
            }

            if (current.Techniques.Contains(TechniqueType.Drag))
            {
                strain += 2.0; // Drag has specific timing
            }

            if (current.Techniques.Contains(TechniqueType.HiHatBark))
            {
                strain += 1.2; // Open-close timing
            }

            if (current.Techniques.Contains(TechniqueType.Choke))
            {
                strain += 1.5; // Choke timing is critical
            }

            if (current.Techniques.Contains(TechniqueType.BuzzRoll))
            {
                strain += 1.0; // Sustained pressure precision
            }

            return strain;
        }

        // ========================
        // HIT PLACEMENT PRECISION
        // ========================

        private double CalculateHitPlacementPrecision(DifficultyHitObject current)
        {
            double strain = 0;

            // Multiple hits at once need coordinated placement
            if (current.NoteCount > 1)
            {
                strain += (current.NoteCount - 1) * 0.3;

                // Wide spread across kit
                if (current.TravelDistance > 0.5)
                {
                    strain += current.TravelDistance * 0.5;
                }
            }

            // Bell hits require stick placement precision
            if (current.DrumTypes.Contains(DrumType.RideBell))
            {
                strain += 0.8;
            }

            // Cross-stick placement
            if (current.Techniques.Contains(TechniqueType.CrossStick))
            {
                strain += 1.0;
            }

            return strain;
        }

        // ========================
        // SUSTAINED PRECISION DEMAND
        // ========================

        private double CalculateSustainedPrecisionDemand()
        {
            double strain = 0;

            // Consecutive high precision = accumulating mental load
            if (consecutiveHighPrecision > 6)
            {
                strain += 0.15 * Math.Min(consecutiveHighPrecision - 6, 16);
            }

            if (consecutiveDynamicPrecision > 4)
            {
                strain += 0.12 * Math.Min(consecutiveDynamicPrecision - 4, 12);
            }

            return strain;
        }

        // ========================
        // MICRO-TIMING PRECISION
        // ========================

        private double CalculateMicroTimingPrecision(DifficultyHitObject current)
        {
            double strain = 0;

            // Analyze if the pattern requires micro-timing awareness
            if (recentGridDeviations.Count >= 8)
            {
                var recent = recentGridDeviations.TakeLast(8).ToList();

                // Check for consistent micro-timing pattern
                double avgDev = recent.Average();
                double variance = recent.Select(d => Math.Pow(d - avgDev, 2)).Average();

                // Consistent small deviations = intentional feel that must be precise
                if (variance < 0.003 && avgDev > 0.02 && avgDev < 0.15)
                {
                    strain += 1.5;
                }
            }

            return strain;
        }

        // ========================
        // COORDINATION PRECISION
        // ========================

        private double CalculateCoordinationPrecision(DifficultyHitObject current)
        {
            double strain = 0;

            // Multi-limb hits need precise coordination
            if (current.LimbCount >= 3)
            {
                strain += 0.8;
            }

            if (current.LimbCount >= 4)
            {
                strain += 1.0; // Four-way coordination precision
            }

            // Unison hits (all hitting exactly together)
            if (current.NoteCount > 2 && current.VelocityRange < 0.15)
            {
                // Tight unison = high precision
                strain += 1.2;
            }

            return strain;
        }
    }
}
