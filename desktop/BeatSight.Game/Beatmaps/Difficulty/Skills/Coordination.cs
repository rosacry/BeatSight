using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// Evaluates limb coordination and independence difficulty.
    /// 
    /// Coordination is THE defining skill that separates advanced drummers from 
    /// intermediate ones. The ability to play different rhythms simultaneously
    /// with different limbs (four-way independence) is the hallmark of jazz, prog,
    /// and world-class technical drumming.
    /// 
    /// KEY DESIGN PRINCIPLES:
    /// 
    /// 1. FOUR-WAY INDEPENDENCE IS KING
    ///    - Using all four limbs simultaneously is exponentially harder
    ///    - Different rhythms per limb (polyrhythmic independence) is the holy grail
    ///    - This is what makes Matt Garstka, Vinnie Colaiuta, Steve Gadd legends
    /// 
    /// 2. LIMB SWITCHING COST
    ///    - Rapid switching between different limb combinations has a cost
    ///    - The brain needs time to reorganize motor patterns
    ///    - Fast switching = high cognitive and motor load
    /// 
    /// 3. PHYSICAL MOVEMENT COORDINATION
    ///    - Moving around the kit while coordinating limbs is challenging
    ///    - Large movements require body position changes
    ///    - This compounds with limb independence demands
    /// 
    /// 4. POLYRHYTHMIC COORDINATION
    ///    - Different subdivisions in different limbs is extremely difficult
    ///    - 3:2 is standard, 5:4 and 7:4 are advanced
    ///    - This creates compound coordination demands
    /// 
    /// COORDINATION SCENARIOS (increasing difficulty):
    /// - Basic: One hand + kick (standard rock beat)
    /// - Intermediate: Two hands + kick (fills with hi-hat foot)
    /// - Advanced: Three limbs with different patterns
    /// - Expert: Four-way independence with syncopation
    /// - Master: Polyrhythmic four-way independence
    /// - Legendary: Metric modulation while maintaining independence
    /// </summary>
    public class Coordination : Skill
    {
        // ===========================================
        // SKILL CONFIGURATION
        // ===========================================

        /// <summary>
        /// High multiplier reflects that coordination is THE defining advanced skill.
        /// </summary>
        protected override double SkillMultiplier => 24.0;

        /// <summary>
        /// Moderate decay (0.20 = 20% remains after 1 second).
        /// Coordination challenges need sustained attention but aren't purely cumulative.
        /// </summary>
        protected override double StrainDecayBase => 0.20;

        // ===========================================
        // LIMB STATE TRACKING
        // ===========================================

        private bool lastWasHand = false;
        private bool lastWasFoot = false;
        private int limbSwitchCount = 0;
        private int consecutiveFourWay = 0;
        private readonly List<int> recentLimbCounts = new();
        private const int LIMB_HISTORY_SIZE = 8;

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;

            // Track limb history
            recentLimbCounts.Add(current.LimbCount);
            if (recentLimbCounts.Count > LIMB_HISTORY_SIZE)
                recentLimbCounts.RemoveAt(0);

            // ===========================================
            // 1. UNISON HITS (MULTIPLE LIMBS SIMULTANEOUSLY)
            // ===========================================
            strain += CalculateUnisonStrain(current);

            // ===========================================
            // 2. LIMB SWITCHING COST
            // ===========================================
            strain += CalculateLimbSwitchingStrain(current);

            // ===========================================
            // 3. LIMB INDEPENDENCE (DIFFERENT PATTERNS)
            // ===========================================
            strain += CalculateIndependenceStrain(current);

            // ===========================================
            // 4. PHYSICAL MOVEMENT COORDINATION
            // ===========================================
            strain += CalculateMovementStrain(current);

            // ===========================================
            // 5. CROSS-OVER PATTERNS
            // ===========================================
            strain += CalculateCrossOverStrain(current);

            // ===========================================
            // 6. HI-HAT FOOT COORDINATION
            // ===========================================
            strain += CalculateHiHatFootStrain(current);

            // ===========================================
            // 7. LINEAR VS STACKED COORDINATION
            // ===========================================
            strain += CalculateLinearStackedStrain(current);

            // ===========================================
            // 8. METRIC MODULATION COORDINATION
            // ===========================================
            if (current.IsMetricModulation)
            {
                // Changing time feel while maintaining coordination is very demanding
                strain += 4.0;
            }

            // ===========================================
            // 9. FOUR-WAY INDEPENDENCE BONUS
            // ===========================================
            strain += CalculateFourWayBonus(current);

            // ===========================================
            // 10. SPEED-COORDINATION COMPOUND
            // ===========================================
            // Fast coordination is exponentially harder
            if (current.DeltaTime < 100 && current.LimbCount > 2)
            {
                double speedCompound = 1.0 + (100 - current.DeltaTime) / 100.0;
                strain *= speedCompound;
            }

            // Update state for next iteration
            lastWasHand = current.HasHand;
            lastWasFoot = current.HasFoot;

            return strain;
        }

        /// <summary>
        /// Calculate strain from hitting multiple drums simultaneously.
        /// Using multiple limbs at once requires precise synchronization.
        /// </summary>
        private double CalculateUnisonStrain(DifficultyHitObject current)
        {
            if (current.LimbCount <= 1)
                return 0;

            // Exponential scaling: more limbs = dramatically harder
            // 2 limbs: ~2.3x, 3 limbs: ~4.3x, 4 limbs: ~7.3x
            double unisonStrain = Math.Pow(current.LimbCount, 1.7);

            // 4 limbs simultaneously is extremely difficult
            if (current.LimbCount >= 4)
            {
                unisonStrain *= 1.35;
                consecutiveFourWay++;
            }
            else
            {
                consecutiveFourWay = Math.Max(0, consecutiveFourWay - 1);
            }

            // Fast unison hits are harder
            if (current.DeltaTime < 150)
                unisonStrain *= 1.25;
            if (current.DeltaTime < 80)
                unisonStrain *= 1.15;

            return unisonStrain;
        }

        /// <summary>
        /// Calculate strain from switching between limb combinations.
        /// The brain needs time to reorganize motor patterns.
        /// </summary>
        private double CalculateLimbSwitchingStrain(DifficultyHitObject current)
        {
            if (current.Previous == null)
                return 0;

            bool currentHand = current.HasHand;
            bool currentFoot = current.HasFoot;

            // Detect significant limb combination changes
            bool handToFoot = lastWasHand && !lastWasFoot && currentFoot && !currentHand;
            bool footToHand = lastWasFoot && !lastWasHand && currentHand && !currentFoot;
            bool combinationChange = (lastWasHand != currentHand) || (lastWasFoot != currentFoot);

            if (!combinationChange)
            {
                limbSwitchCount = Math.Max(0, limbSwitchCount - 1);
                return 0;
            }

            limbSwitchCount++;

            // Base switching strain scaled by speed
            double switchSpeed = 150.0 / Math.Max(current.DeltaTime, 30.0);
            double switchStrain = 2.5 * Math.Pow(switchSpeed, 1.35);

            // Hand ↔ foot switches are particularly demanding
            if (handToFoot || footToHand)
                switchStrain *= 1.2;

            // Frequent switching compounds difficulty
            if (limbSwitchCount > 3)
            {
                double frequencyBonus = 1.0 + 0.12 * Math.Min(limbSwitchCount - 3, 6);
                switchStrain *= frequencyBonus;
            }

            return switchStrain;
        }

        /// <summary>
        /// Calculate strain from playing different patterns with different limbs.
        /// True limb independence is the hallmark of advanced drumming.
        /// </summary>
        private double CalculateIndependenceStrain(DifficultyHitObject current)
        {
            if (!current.HasHand || !current.HasFoot)
                return 0;

            double independenceStrain = 2.5; // Base: hands + feet playing

            // Syncopated patterns with multiple limbs = independence challenge
            if (current.IsSyncopated)
                independenceStrain += 2.0;

            // Polyrhythmic independence (different subdivisions per limb)
            if (!string.IsNullOrEmpty(current.PolyrhythmType))
            {
                independenceStrain += current.PolyrhythmType switch
                {
                    "3:2" => 2.5,  // Common but still challenging
                    "4:3" => 3.0,  // More complex
                    "5:4" => 4.5,  // Quintuplet feel - Matt Garstka territory
                    "7:4" => 5.5,  // Septuplet - extremely advanced
                    _ => 2.0
                };
            }

            // Odd groupings with limb independence
            if (current.OddGrouping.HasValue)
            {
                independenceStrain += current.OddGrouping.Value switch
                {
                    5 => 2.5,
                    7 => 3.5,
                    9 => 3.0,
                    11 => 4.0,
                    _ => 1.5
                };
            }

            // Fast independence is harder
            if (current.DeltaTime < 100)
                independenceStrain *= 1.35;
            else if (current.DeltaTime < 150)
                independenceStrain *= 1.15;

            // Both hands active with different patterns
            if (current.HasLeftHand && current.HasRightHand)
            {
                // Two-hand independence adds challenge
                independenceStrain += 1.5;
            }

            return independenceStrain;
        }

        /// <summary>
        /// Calculate strain from physical movement while coordinating.
        /// Moving around the kit while maintaining coordination is challenging.
        /// </summary>
        private double CalculateMovementStrain(DifficultyHitObject current)
        {
            if (current.TravelDistance <= 0)
                return 0;

            double movementSpeed = current.MovementSpeed;
            double movementStrain = Math.Pow(movementSpeed, 1.25) * 0.9;

            // Large movements are harder
            if (current.TravelDistance > 1.0)
                movementStrain *= 1.35;
            if (current.TravelDistance > 1.5)
                movementStrain *= 1.25;

            // Moving while coordinating multiple limbs
            if (current.LimbCount > 1)
                movementStrain *= 1.0 + current.LimbCount * 0.12;

            return movementStrain;
        }

        /// <summary>
        /// Calculate strain from hand crossing patterns.
        /// Cross-overs require precise spatial coordination.
        /// </summary>
        private double CalculateCrossOverStrain(DifficultyHitObject current)
        {
            if (!current.HasLeftHand || !current.HasRightHand)
                return 0;

            double crossOverStrain = 0;

            // Detect potential cross-over: hi-hat with other cymbals/toms
            bool hasHiHat = current.DrumTypes.Contains(DrumType.HiHat);
            bool hasRightSideHit = current.DrumTypes.Any(d =>
                d == DrumType.Ride || d == DrumType.RideBell ||
                d == DrumType.TomMid || d == DrumType.TomLow ||
                d == DrumType.China);

            if (hasHiHat && hasRightSideHit)
            {
                crossOverStrain = 2.0;

                // Fast cross-overs are particularly demanding
                if (current.DeltaTime < 100)
                    crossOverStrain *= 1.3;
            }

            return crossOverStrain;
        }

        /// <summary>
        /// Calculate strain from hi-hat foot work while hands are busy.
        /// The left foot doing independent work while hands play is challenging.
        /// </summary>
        private double CalculateHiHatFootStrain(DifficultyHitObject current)
        {
            bool hasHiHatPedal = current.DrumTypes.Contains(DrumType.HiHatPedal) ||
                                 current.Techniques.Contains(TechniqueType.HiHatChick);

            if (!hasHiHatPedal)
                return 0;

            double hiHatStrain = 1.2;

            // Hi-hat foot work while hands are active
            if (current.HasHand)
                hiHatStrain = 1.8;

            // Hi-hat foot + bass drum coordination (both feet)
            if (current.DrumTypes.Contains(DrumType.Kick))
                hiHatStrain = 3.0;

            // Fast hi-hat foot work
            if (current.DeltaTime < 150)
                hiHatStrain *= 1.2;

            return hiHatStrain;
        }

        /// <summary>
        /// Calculate strain difference between linear and stacked patterns.
        /// Each has its own coordination challenges.
        /// </summary>
        private double CalculateLinearStackedStrain(DifficultyHitObject current)
        {
            double strain = 0;

            if (current.IsLinear)
            {
                // Linear drumming: clean limb separation, no overlap
                // This requires precise timing to avoid ghost overlap
                if (current.DeltaTime < 80)
                    strain += 1.2; // Fast linear is demanding
            }
            else if (current.NoteCount > 2)
            {
                // Stacked notes: precise synchronization of multiple hits
                strain += 0.6 * current.NoteCount;
            }

            return strain;
        }

        /// <summary>
        /// Calculate bonus for sustained four-way independence.
        /// Maintaining all four limbs active independently is elite-level.
        /// </summary>
        private double CalculateFourWayBonus(DifficultyHitObject current)
        {
            if (consecutiveFourWay < 2)
                return 0;

            // Sustained four-way independence is extremely demanding
            double bonus = 2.0 + 0.5 * Math.Min(consecutiveFourWay - 2, 6);

            return bonus;
        }
    }
}
