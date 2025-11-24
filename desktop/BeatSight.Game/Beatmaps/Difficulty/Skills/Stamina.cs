using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// ENHANCED Stamina Skill v2.0 - Physiological Fatigue Model
    /// 
    /// Models actual muscle fatigue using exercise physiology principles:
    /// - Aerobic vs Anaerobic threshold tracking
    /// - Muscle group specific fatigue (fast-twitch vs slow-twitch)
    /// - Fatigue accumulation and recovery curves
    /// - Lactate threshold simulation
    /// - Mental fatigue component
    /// - Song structure awareness (verse/chorus energy management)
    /// 
    /// Key insight: Stamina isn't just "sustained playing" - it's about
    /// resource management across different muscle groups and energy systems.
    /// </summary>
    public class Stamina : Skill
    {
        protected override double SkillMultiplier => 22.0; // Increased from 18.0
        protected override double StrainDecayBase => 0.72; // Slow decay - fatigue accumulates

        // ========================
        // MUSCLE GROUP MODELING
        // ========================
        // Each muscle group has its own fatigue state
        private class MuscleGroup
        {
            public double CurrentFatigue { get; set; } = 0;
            public double AerobicCapacity { get; set; } = 1.0;
            public double AnaerobicBuffer { get; set; } = 1.0;  // "Burst" capacity
            public double RecoveryRate { get; set; }
            public double FatigueRate { get; set; }
            public double LastActivityTime { get; set; } = 0;
            public int ConsecutiveHighEffort { get; set; } = 0;

            public MuscleGroup(double recoveryRate, double fatigueRate)
            {
                RecoveryRate = recoveryRate;
                FatigueRate = fatigueRate;
            }

            public void Update(double currentTime, double effort, bool isHighEffort)
            {
                double timeDelta = currentTime - LastActivityTime;
                LastActivityTime = currentTime;

                // Recovery during inactivity
                if (timeDelta > 100)
                {
                    double recoveryTime = timeDelta - 100;
                    CurrentFatigue *= Math.Exp(-RecoveryRate * recoveryTime / 1000.0);
                    AnaerobicBuffer = Math.Min(1.0, AnaerobicBuffer + recoveryTime * 0.0002);
                }

                // Add new fatigue
                double fatigueDelta = effort * FatigueRate;

                // Anaerobic buffer absorbs initial high intensity
                if (isHighEffort && AnaerobicBuffer > 0)
                {
                    double absorbed = Math.Min(AnaerobicBuffer, fatigueDelta * 0.4);
                    AnaerobicBuffer -= absorbed;
                    fatigueDelta -= absorbed;
                }

                CurrentFatigue = Math.Min(3.0, CurrentFatigue + fatigueDelta);

                // Track consecutive high effort
                if (isHighEffort)
                    ConsecutiveHighEffort++;
                else
                    ConsecutiveHighEffort = Math.Max(0, ConsecutiveHighEffort - 1);
            }

            public double GetEffectiveFatigue()
            {
                // Fatigue has exponential impact on difficulty
                double baseFatigue = CurrentFatigue;

                // Consecutive high effort compounds
                if (ConsecutiveHighEffort > 4)
                    baseFatigue *= 1.0 + 0.08 * Math.Min(ConsecutiveHighEffort - 4, 12);

                // Depleted anaerobic buffer makes everything harder
                if (AnaerobicBuffer < 0.3)
                    baseFatigue *= 1.0 + (0.3 - AnaerobicBuffer);

                return baseFatigue;
            }
        }

        // Muscle groups
        private readonly MuscleGroup rightHand = new(0.0012, 0.035);
        private readonly MuscleGroup leftHand = new(0.0012, 0.035);
        private readonly MuscleGroup rightFoot = new(0.0008, 0.045); // Feet recover slower, fatigue faster
        private readonly MuscleGroup leftFoot = new(0.0008, 0.045);
        private readonly MuscleGroup core = new(0.0015, 0.02); // Core is more resilient

        // ========================
        // GLOBAL STAMINA STATE
        // ========================
        private double globalFatigue = 0;
        private double mentalFatigue = 0;
        private double songProgress = 0; // 0.0 to 1.0
        private double peakIntensitySoFar = 0;
        private int consecutiveHighDensity = 0;
        private int consecutiveBlastBeat = 0;
        private double accumulatedEffort = 0;

        // Thresholds based on exercise physiology
        private const double LACTATE_THRESHOLD_MS = 75;  // Below this = anaerobic
        private const double AEROBIC_THRESHOLD_MS = 120; // Above this = sustainable
        private const double VENTILATORY_THRESHOLD_MS = 95; // Moderate intensity zone

        // Pattern tracking
        private readonly Queue<double> recentEfforts = new();
        private const int EFFORT_WINDOW = 32;

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;
            double currentTime = current.StartTime;

            // ========================
            // 1. BASE EFFORT CALCULATION
            // ========================
            double baseEffort = CalculateBaseEffort(current);
            bool isHighEffort = baseEffort > 0.6;

            // ========================
            // 2. UPDATE MUSCLE GROUP FATIGUE
            // ========================
            UpdateMuscleGroups(current, currentTime, baseEffort, isHighEffort);

            // ========================
            // 3. DENSITY-BASED STRAIN
            // ========================
            double densityStrain = current.NoteCount / current.StrainTime * 90.0;
            strain += densityStrain;

            // ========================
            // 4. VELOCITY (LOUDNESS) IMPACT
            // ========================
            // Playing loud is exponentially more tiring
            double velocityFactor = 0.5 + current.AverageVelocity * 0.5;
            velocityFactor = Math.Pow(velocityFactor, 1.5);
            strain *= velocityFactor;

            // Accent chains are exhausting
            if (current.Techniques.Contains(TechniqueType.Accent))
            {
                strain *= 1.2;
            }

            // ========================
            // 5. MUSCLE GROUP FATIGUE CONTRIBUTION
            // ========================
            double muscleStrain = CalculateMuscleGroupStrain(current);
            strain += muscleStrain;

            // ========================
            // 6. ENERGY SYSTEM ANALYSIS
            // ========================
            double energySystemStrain = CalculateEnergySystemStrain(current);
            strain += energySystemStrain;

            // ========================
            // 7. SUSTAINED PATTERN DETECTION
            // ========================
            strain += CalculateSustainedPatternStrain(current);

            // ========================
            // 8. BLAST BEAT ENDURANCE
            // ========================
            if (current.IsBlastBeat)
            {
                consecutiveBlastBeat++;

                // Blast beats are the ultimate stamina test
                double blastStrain = 1.5;

                // Sustained blast beats compound dramatically
                if (consecutiveBlastBeat > 4)
                    blastStrain *= 1.0 + 0.12 * Math.Min(consecutiveBlastBeat - 4, 16);

                // Speed-based blast beat scaling
                if (current.DeltaTime < 50)
                    blastStrain *= 1.4; // >300 BPM equivalent
                else if (current.DeltaTime < 60)
                    blastStrain *= 1.25; // >250 BPM
                else if (current.DeltaTime < 75)
                    blastStrain *= 1.1; // >200 BPM

                strain *= blastStrain;
            }
            else
            {
                consecutiveBlastBeat = Math.Max(0, consecutiveBlastBeat - 2);
            }

            // ========================
            // 9. GLOBAL FATIGUE ACCUMULATION
            // ========================
            UpdateGlobalFatigue(current, baseEffort);
            double globalFatigueFactor = 1.0 + globalFatigue * 0.35;
            strain *= globalFatigueFactor;

            // ========================
            // 10. MENTAL FATIGUE
            // ========================
            // Complex patterns while physically tired = mental strain
            mentalFatigue += current.PatternEntropy * 0.001;
            mentalFatigue *= 0.9995; // Slow decay
            mentalFatigue = Math.Min(0.3, mentalFatigue);
            strain *= 1.0 + mentalFatigue;

            // ========================
            // 11. SONG POSITION AWARENESS
            // ========================
            // Later in the song, same effort feels harder
            songProgress = Math.Min(1.0, currentTime / 300000.0); // Assume 5 min max
            if (songProgress > 0.6)
            {
                double progressFactor = 1.0 + (songProgress - 0.6) * 0.25;
                strain *= progressFactor;
            }

            // ========================
            // 12. PEAK INTENSITY MEMORY
            // ========================
            // If we've already hit high peaks, relative effort feels different
            double currentIntensity = baseEffort;
            if (currentIntensity > peakIntensitySoFar)
            {
                peakIntensitySoFar = currentIntensity;
                strain *= 1.1; // New peak is extra taxing
            }

            // ========================
            // 13. MOVEMENT WHILE FATIGUED
            // ========================
            if (current.TravelDistance > 0.4 && globalFatigue > 0.15)
            {
                double movementPenalty = 1.0 + current.TravelDistance * globalFatigue * 0.8;
                strain *= movementPenalty;
            }

            // ========================
            // 14. MULTI-LIMB COORDINATION FATIGUE
            // ========================
            if (current.LimbCount >= 3)
            {
                strain *= 1.15;

                // Four-way while fatigued is brutal
                if (current.LimbCount >= 4 && globalFatigue > 0.2)
                    strain *= 1.2;
            }

            // Track effort history
            recentEfforts.Enqueue(baseEffort);
            if (recentEfforts.Count > EFFORT_WINDOW)
                recentEfforts.Dequeue();
            accumulatedEffort += baseEffort;

            return strain;
        }

        // ========================
        // HELPER METHODS
        // ========================

        private double CalculateBaseEffort(DifficultyHitObject current)
        {
            double effort = 0;

            // Time-based intensity
            double timeIntensity = Math.Max(0, 1.0 - current.DeltaTime / 200.0);
            effort += timeIntensity * 0.6;

            // Note count
            effort += current.NoteCount * 0.15;

            // Velocity
            effort += current.AverageVelocity * 0.25;

            // Technique demands
            if (current.Techniques.Contains(TechniqueType.Roll) ||
                current.Techniques.Contains(TechniqueType.BuzzRoll))
                effort += 0.3;
            if (current.Techniques.Contains(TechniqueType.DoublePedalBurst) ||
                current.Techniques.Contains(TechniqueType.SlideDouble))
                effort += 0.4;

            return Math.Min(1.0, effort);
        }

        private void UpdateMuscleGroups(DifficultyHitObject current, double time, double effort, bool highEffort)
        {
            // Determine which muscle groups are active
            bool usesRightHand = current.HasHand; // Simplified - could be more specific
            bool usesLeftHand = current.HasHand;
            bool usesRightFoot = current.HasFoot;
            bool usesLeftFoot = current.IsDoubleBass;

            if (usesRightHand)
                rightHand.Update(time, effort, highEffort);
            if (usesLeftHand)
                leftHand.Update(time, effort, highEffort);
            if (usesRightFoot)
                rightFoot.Update(time, effort, highEffort);
            if (usesLeftFoot)
                leftFoot.Update(time, effort, highEffort);

            // Core is always engaged to some degree
            core.Update(time, effort * 0.3, false);
        }

        private double CalculateMuscleGroupStrain(DifficultyHitObject current)
        {
            double strain = 0;

            if (current.HasHand)
            {
                double handFatigue = (rightHand.GetEffectiveFatigue() + leftHand.GetEffectiveFatigue()) / 2;
                strain += handFatigue * 0.4;

                // Roll techniques stress hands specifically
                if (current.Techniques.Contains(TechniqueType.Roll) ||
                    current.Techniques.Contains(TechniqueType.BuzzRoll) ||
                    current.Techniques.Contains(TechniqueType.DoubleStroke))
                {
                    strain += handFatigue * 0.3;
                }
            }

            if (current.HasFoot)
            {
                double footFatigue = rightFoot.GetEffectiveFatigue();
                strain += footFatigue * 0.5;

                // Double bass uses both feet
                if (current.IsDoubleBass)
                {
                    footFatigue = (rightFoot.GetEffectiveFatigue() + leftFoot.GetEffectiveFatigue()) / 2;
                    strain += footFatigue * 0.4;

                    // High-speed double bass when feet are fatigued
                    if (current.DeltaTime < 75 && footFatigue > 0.3)
                        strain += footFatigue * 0.5;
                }
            }

            // Core strain affects overall stability
            double coreFatigue = core.GetEffectiveFatigue();
            strain += coreFatigue * 0.15;

            return strain;
        }

        private double CalculateEnergySystemStrain(DifficultyHitObject current)
        {
            double strain = 0;

            // Classify the current activity by energy system
            if (current.DeltaTime < LACTATE_THRESHOLD_MS)
            {
                // Anaerobic zone - unsustainable
                consecutiveHighDensity++;

                double anaerobicStrain = 1.0 + 0.08 * Math.Min(consecutiveHighDensity, 20);
                strain += anaerobicStrain;

                // Deep anaerobic (extreme speed)
                if (current.DeltaTime < 50)
                {
                    strain += 1.5 + 0.15 * Math.Min(consecutiveHighDensity, 10);
                }
            }
            else if (current.DeltaTime < VENTILATORY_THRESHOLD_MS)
            {
                // Ventilatory threshold zone - challenging but manageable
                consecutiveHighDensity = Math.Max(0, consecutiveHighDensity - 1);
                strain += 0.5;
            }
            else if (current.DeltaTime < AEROBIC_THRESHOLD_MS)
            {
                // Moderate intensity
                consecutiveHighDensity = Math.Max(0, consecutiveHighDensity - 2);
                strain += 0.2;
            }
            else
            {
                // Aerobic zone - sustainable, recovery
                consecutiveHighDensity = Math.Max(0, consecutiveHighDensity - 3);
            }

            return strain;
        }

        private double CalculateSustainedPatternStrain(DifficultyHitObject current)
        {
            if (recentEfforts.Count < 8) return 0;

            double strain = 0;
            double avgRecentEffort = recentEfforts.Average();

            // Sustained high effort is harder than bursts
            if (avgRecentEffort > 0.5)
            {
                // How consistent is the high effort?
                double effortVariance = recentEfforts.Select(e => Math.Pow(e - avgRecentEffort, 2)).Average();

                // Low variance + high average = sustained intensity = hard
                if (effortVariance < 0.05)
                {
                    double sustainBonus = 1.0 + avgRecentEffort * 0.5;
                    strain += sustainBonus;
                }
            }

            return strain;
        }

        private void UpdateGlobalFatigue(DifficultyHitObject current, double effort)
        {
            // Fatigue builds based on effort
            if (effort > 0.3)
            {
                globalFatigue += (effort - 0.3) * 0.005;
            }
            else
            {
                // Recovery during low effort
                globalFatigue -= 0.002;
            }

            // Extra fatigue from sustained high density
            if (consecutiveHighDensity > 8)
            {
                globalFatigue += 0.002 * (consecutiveHighDensity - 8);
            }

            // Clamp to reasonable range
            globalFatigue = Math.Max(0, Math.Min(1.0, globalFatigue));
        }
    }

    /// <summary>
    /// ENHANCED Mono Stamina - Single limb repetition fatigue
    /// Models repetitive strain and muscle-specific endurance limits.
    /// </summary>
    public class MonoStamina : Skill
    {
        protected override double SkillMultiplier => 16.0;
        protected override double StrainDecayBase => 0.68;

        private readonly Dictionary<DrumType, double> drumStrains = new();
        private readonly Dictionary<DrumType, int> consecutiveHits = new();
        private DrumType? lastDrumType = null;

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;
            if (current.DrumTypes.Count == 0) return 0;

            double strain = 0;

            foreach (var drumType in current.DrumTypes)
            {
                if (!drumStrains.ContainsKey(drumType))
                {
                    drumStrains[drumType] = 0;
                    consecutiveHits[drumType] = 0;
                }

                // Decay existing strain
                drumStrains[drumType] *= Math.Pow(0.55, current.DeltaTime / 1000.0);

                // Base strain from speed
                double newStrain = 1.0 / current.StrainTime * 55.0;

                // Track consecutive same-drum hits
                if (lastDrumType == drumType)
                {
                    consecutiveHits[drumType]++;
                    int count = consecutiveHits[drumType];

                    // Mono patterns (repeated single drum) cause specific fatigue
                    if (count > 4)
                    {
                        // Exponential fatigue buildup for repetitive motion
                        double monoFatigue = 1.0 + 0.12 * Math.Pow(Math.Min(count - 4, 16), 1.2);
                        newStrain *= monoFatigue;
                    }

                    // Very long mono streams (16+)
                    if (count > 16)
                    {
                        newStrain *= 1.25;
                    }
                }
                else
                {
                    consecutiveHits[drumType] = 1;
                }

                drumStrains[drumType] += newStrain;
                strain += drumStrains[drumType] * 0.55;

                lastDrumType = drumType;
            }

            return strain;
        }
    }
}
