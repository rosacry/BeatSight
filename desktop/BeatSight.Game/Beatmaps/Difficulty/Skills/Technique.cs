using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// ENHANCED Technique Skill v2.0 - Physical Execution Analysis
    /// 
    /// Models the physical difficulty of executing specific drumming articulations.
    /// Goes beyond simple "technique present = bonus" to model:
    /// 
    /// - Technique combinations (harder than sum of parts)
    /// - Speed-dependent technique difficulty scaling
    /// - Context-dependent difficulty (ghost after accent is harder)
    /// - Technique transitions (switching between techniques)
    /// - Motor skill complexity (fine vs gross motor)
    /// - Technique sustainability (can you maintain this?)
    /// - Hand/foot specific technique demands
    /// 
    /// Calibrated against professional drum literature difficulty ratings.
    /// </summary>
    public class Technique : Skill
    {
        protected override double SkillMultiplier => 24.0; // Increased from 20.0
        protected override double StrainDecayBase => 0.12; // Fast decay - technique is momentary

        // ========================
        // TECHNIQUE STATE TRACKING
        // ========================

        // Consecutive technique tracking
        private readonly Dictionary<TechniqueType, int> consecutiveTechniqueCounts = new();
        private TechniqueType? lastTechnique = null;

        // Technique combination tracking
        private readonly Queue<HashSet<TechniqueType>> recentTechniqueHistory = new();
        private const int TECHNIQUE_HISTORY_SIZE = 12;

        // Dynamic context
        private double previousVelocity = 0.5;
        private int consecutiveDynamicJumps = 0;

        // Sustained technique tracking
        private readonly Dictionary<TechniqueType, int> sustainedTechniqueCount = new();

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;

            // ========================
            // 1. BASE TECHNIQUE STRAIN
            // ========================
            var activeTechniques = current.Techniques.Where(t => t != TechniqueType.Normal).ToHashSet();

            foreach (var tech in activeTechniques)
            {
                double techStrain = GetEnhancedTechniqueStrain(tech, current);
                strain += techStrain;
            }

            // ========================
            // 2. SPEED-SCALED TECHNIQUE DIFFICULTY
            // ========================
            strain *= GetSpeedScalingFactor(current.DeltaTime, activeTechniques);

            // ========================
            // 3. CONSECUTIVE TECHNIQUE BONUS
            // ========================
            strain += CalculateConsecutiveTechniqueBonus(activeTechniques, current);

            // ========================
            // 4. TECHNIQUE COMBINATIONS
            // ========================
            if (activeTechniques.Count > 1)
            {
                strain += CalculateTechniqueCombinationBonus(activeTechniques, current);
            }

            // ========================
            // 5. TECHNIQUE TRANSITIONS
            // ========================
            if (current.Previous != null)
            {
                strain += CalculateTechniqueTransitionStrain(activeTechniques, current);
            }

            // ========================
            // 6. DYNAMIC CONTROL COMPLEXITY
            // ========================
            strain += CalculateEnhancedDynamicStrain(current);

            // ========================
            // 7. CONTEXT-DEPENDENT BONUSES
            // ========================
            strain += CalculateContextBonuses(activeTechniques, current);

            // ========================
            // 8. SUSTAINED TECHNIQUE DIFFICULTY
            // ========================
            strain += CalculateSustainedTechniqueDifficulty(activeTechniques);

            // ========================
            // 9. MOTOR COMPLEXITY
            // ========================
            strain += CalculateMotorComplexity(activeTechniques, current);

            // Update history
            recentTechniqueHistory.Enqueue(activeTechniques);
            if (recentTechniqueHistory.Count > TECHNIQUE_HISTORY_SIZE)
                recentTechniqueHistory.Dequeue();

            // Update last technique
            lastTechnique = activeTechniques.FirstOrDefault();

            return strain;
        }

        // ========================
        // ENHANCED TECHNIQUE STRAIN VALUES
        // ========================

        private double GetEnhancedTechniqueStrain(TechniqueType tech, DifficultyHitObject current)
        {
            // Base difficulty values - carefully calibrated against professional drumming literature
            // Scale: 0 = no difficulty, 5+ = very demanding, 8+ = extreme
            double baseStrain = tech switch
            {
                TechniqueType.Normal => 0,

                // ========================
                // RUDIMENTS & SNARE ARTICULATIONS
                // ========================
                TechniqueType.Flam => 2.5,          // Grace note timing precision
                TechniqueType.Drag => 3.0,          // Multiple grace notes
                TechniqueType.Roll => 2.5,          // Open roll - rebound control
                TechniqueType.BuzzRoll => 3.0,      // Press roll - pressure control
                TechniqueType.DoubleStroke => 2.0,  // Basic diddle
                TechniqueType.GhostNote => 1.8,     // Dynamic control for quiet strokes
                TechniqueType.Rimshot => 1.5,       // Precision placement
                TechniqueType.CrossStick => 2.0,    // Position change required
                TechniqueType.StickshotShot => 2.5, // Two-stick coordination
                TechniqueType.DeadStroke => 1.8,    // Controlled stopping

                // ========================
                // HI-HAT TECHNIQUES
                // ========================
                TechniqueType.HiHatBark => 3.0,     // Quick foot coordination
                TechniqueType.HiHatSplash => 2.5,   // Foot technique
                TechniqueType.HiHatChick => 1.2,    // Basic pedal
                TechniqueType.HiHatHalfOpen => 1.5, // Controlled pressure

                // ========================
                // CYMBAL TECHNIQUES
                // ========================
                TechniqueType.Choke => 4.5,         // Hit + grab timing
                TechniqueType.BellHit => 1.3,       // Precision targeting
                TechniqueType.CymbalScrape => 2.0,  // Unusual motion
                TechniqueType.MalletSwell => 2.2,   // Control and touch
                TechniqueType.CrashRiding => 1.8,   // Sustained intensity
                TechniqueType.CrashBuild => 2.5,    // Dynamic shaping

                // ========================
                // TOM TECHNIQUES
                // ========================
                TechniqueType.TomRimshot => 2.0,    // Precision on larger surface

                // ========================
                // BASS DRUM TECHNIQUES
                // ========================
                TechniqueType.DoublePedalBurst => 4.5, // Extreme foot technique
                TechniqueType.SlideDouble => 5.0,   // Advanced single-pedal technique
                TechniqueType.Feathering => 2.0,    // Very soft, controlled

                // ========================
                // STACK/EFFECT
                // ========================
                TechniqueType.StackHit => 1.5,      // Targeting small surface

                // ========================
                // ACCENTS & DYNAMICS
                // ========================
                TechniqueType.Accent => 1.2,        // Basic emphasis
                TechniqueType.AccentTap => 3.0,     // Moeller technique - advanced

                // ========================
                // RUDIMENTAL VOCABULARY (Advanced)
                // ========================
                TechniqueType.Paradiddle => 2.8,       // RLRR LRLL coordination
                TechniqueType.ParadiddleDiddle => 3.2, // Extended pattern
                TechniqueType.Herta => 3.5,            // Fast burst pattern
                TechniqueType.SwissArmyTriplet => 3.8, // Flam-based complexity
                TechniqueType.BonhamTriplets => 4.0,   // Three-limb orchestration
                TechniqueType.FlamTap => 3.2,          // Combined rudiment
                TechniqueType.FlamAccent => 3.0,       // Dynamic + grace note

                // ========================
                // LINEAR DRUMMING
                // ========================
                TechniqueType.LinearPattern => 2.5,    // Isolation between limbs

                // ========================
                // BRUSH TECHNIQUES
                // ========================
                TechniqueType.BrushSweep => 2.5,       // Continuous motion control
                TechniqueType.BrushTap => 2.0,         // Articulation control

                _ => 0.8
            };

            // ========================
            // CONTEXT-BASED ADJUSTMENTS
            // ========================

            // Tom techniques often require non-dominant hand
            if (current.DrumTypes.Contains(DrumType.Tom) || current.DrumTypes.Contains(DrumType.TomLow))
            {
                if (tech == TechniqueType.Roll || tech == TechniqueType.Flam)
                    baseStrain *= 1.15;
            }

            // Techniques on cymbals require different approach
            if (current.DrumTypes.Any(d => d == DrumType.Crash || d == DrumType.Ride || d == DrumType.China))
            {
                if (tech == TechniqueType.Roll)
                    baseStrain *= 1.2; // Cymbal rolls are demanding
            }

            // Rudimental techniques in complex patterns
            if (IsRudimentalTechnique(tech) && current.LimbCount > 2)
            {
                baseStrain *= 1.25;
            }

            return baseStrain;
        }

        /// <summary>
        /// Check if technique is a rudimental pattern.
        /// </summary>
        private static bool IsRudimentalTechnique(TechniqueType tech)
        {
            return tech switch
            {
                TechniqueType.Paradiddle or
                TechniqueType.ParadiddleDiddle or
                TechniqueType.Herta or
                TechniqueType.SwissArmyTriplet or
                TechniqueType.BonhamTriplets or
                TechniqueType.FlamTap or
                TechniqueType.FlamAccent => true,
                _ => false
            };
        }

        private double GetSpeedScalingFactor(double deltaTime, HashSet<TechniqueType> techniques)
        {
            // Non-linear speed scaling - techniques at high speed are exponentially harder
            double speedFactor = 1.0;

            if (deltaTime < 120)
            {
                // Moderate speed bonus
                speedFactor = 1.0 + (120 - deltaTime) / 100.0;
            }
            if (deltaTime < 80)
            {
                // Fast speed - additional scaling
                speedFactor += (80 - deltaTime) / 60.0;
            }
            if (deltaTime < 50)
            {
                // Extreme speed - exponential scaling
                speedFactor += Math.Pow((50 - deltaTime) / 30.0, 1.5);
            }

            // Some techniques scale more with speed
            if (techniques.Contains(TechniqueType.Roll) || techniques.Contains(TechniqueType.BuzzRoll))
            {
                // Rolls require more control at speed
                speedFactor *= 1.2;
            }
            if (techniques.Contains(TechniqueType.Flam) || techniques.Contains(TechniqueType.Drag))
            {
                // Grace notes are very hard at speed
                speedFactor *= 1.3;
            }
            if (techniques.Contains(TechniqueType.GhostNote))
            {
                // Ghost notes at speed require excellent control
                speedFactor *= 1.15;
            }

            return speedFactor;
        }

        private double CalculateConsecutiveTechniqueBonus(HashSet<TechniqueType> techniques, DifficultyHitObject current)
        {
            double bonus = 0;

            foreach (var tech in techniques)
            {
                if (!consecutiveTechniqueCounts.ContainsKey(tech))
                    consecutiveTechniqueCounts[tech] = 0;

                if (tech == lastTechnique)
                {
                    consecutiveTechniqueCounts[tech]++;
                    int count = consecutiveTechniqueCounts[tech];

                    // Repeated techniques compound difficulty
                    if (count > 2)
                    {
                        double compoundFactor = 0.12 * Math.Min(count - 2, 10);
                        bonus += compoundFactor;

                        // Sustained techniques are particularly demanding
                        if (tech == TechniqueType.Roll || tech == TechniqueType.BuzzRoll)
                            bonus += compoundFactor * 0.5;
                        if (tech == TechniqueType.DoublePedalBurst)
                            bonus += compoundFactor * 0.8;
                    }
                }
                else
                {
                    consecutiveTechniqueCounts[tech] = 1;
                }
            }

            // Reset counts for techniques not present
            var presentTechs = techniques.ToHashSet();
            foreach (var key in consecutiveTechniqueCounts.Keys.ToList())
            {
                if (!presentTechs.Contains(key))
                    consecutiveTechniqueCounts[key] = Math.Max(0, consecutiveTechniqueCounts[key] - 1);
            }

            return bonus;
        }

        private double CalculateTechniqueCombinationBonus(HashSet<TechniqueType> techniques, DifficultyHitObject current)
        {
            double bonus = 0;

            // Multiple techniques = motor complexity
            bonus += (techniques.Count - 1) * 1.0;

            // Specific difficult combinations
            // Ghost + Accent = extreme dynamic control
            if (techniques.Contains(TechniqueType.GhostNote) && techniques.Contains(TechniqueType.Accent))
                bonus += 3.0;

            // Flam + Roll = complex rudiment
            if (techniques.Contains(TechniqueType.Flam) &&
                (techniques.Contains(TechniqueType.Roll) || techniques.Contains(TechniqueType.DoubleStroke)))
                bonus += 2.0;

            // Hi-hat technique + Hand technique = limb independence
            if ((techniques.Contains(TechniqueType.HiHatBark) || techniques.Contains(TechniqueType.HiHatSplash)) &&
                techniques.Any(t => IsHandTechnique(t)))
                bonus += 2.5;

            // Double pedal + hand technique = four-way coordination
            if (techniques.Contains(TechniqueType.DoublePedalBurst) && techniques.Any(t => IsHandTechnique(t)))
                bonus += 3.0;

            // Choke + immediate follow = very demanding timing
            if (techniques.Contains(TechniqueType.Choke) && current.DeltaTime < 150)
                bonus += 2.0;

            return bonus;
        }

        private double CalculateTechniqueTransitionStrain(HashSet<TechniqueType> currentTechs, DifficultyHitObject current)
        {
            if (current.Previous == null) return 0;

            double strain = 0;
            var prevTechs = current.Previous.Techniques.Where(t => t != TechniqueType.Normal).ToHashSet();

            if (!prevTechs.Any() || !currentTechs.Any()) return 0;

            // Switching between different techniques
            if (!prevTechs.Overlaps(currentTechs))
            {
                // Speed-dependent transition strain
                double transitionDifficulty = 1.5 + (60.0 / Math.Max(current.DeltaTime, 25.0));
                strain += transitionDifficulty;

                // Specific difficult transitions
                // Accent to Ghost = huge dynamic shift + control
                if (prevTechs.Contains(TechniqueType.Accent) && currentTechs.Contains(TechniqueType.GhostNote))
                    strain += 2.5;

                // Roll to Flam = completely different stroke type
                if ((prevTechs.Contains(TechniqueType.Roll) || prevTechs.Contains(TechniqueType.BuzzRoll)) &&
                    currentTechs.Contains(TechniqueType.Flam))
                    strain += 2.0;

                // Hi-hat technique change
                if (prevTechs.Any(IsHiHatTechnique) && currentTechs.Any(IsHiHatTechnique) &&
                    !prevTechs.Intersect(currentTechs).Any(IsHiHatTechnique))
                    strain += 1.5;
            }

            return strain;
        }

        private double CalculateEnhancedDynamicStrain(DifficultyHitObject current)
        {
            double dynamicStrain = 0;

            // ========================
            // VELOCITY RANGE WITHIN SINGLE HIT
            // ========================
            if (current.VelocityRange > 0.25)
            {
                // Playing different volumes simultaneously
                double rangeStrain = current.VelocityRange * 2.0;

                // More simultaneous notes with wide range = harder
                if (current.NoteCount > 1)
                    rangeStrain *= 1.0 + (current.NoteCount - 1) * 0.2;

                dynamicStrain += rangeStrain;
            }

            // ========================
            // VELOCITY TRANSITIONS
            // ========================
            double velocityChange = Math.Abs(current.AverageVelocity - previousVelocity);

            if (velocityChange > 0.25)
            {
                double transitionStrain = velocityChange * 2.5;

                // Fast velocity changes are much harder
                if (current.DeltaTime < 100)
                    transitionStrain *= 1.5;
                if (current.DeltaTime < 60)
                    transitionStrain *= 1.5;

                // Consecutive dynamic jumps compound
                if (velocityChange > 0.4)
                {
                    consecutiveDynamicJumps++;
                    if (consecutiveDynamicJumps > 2)
                        transitionStrain *= 1.0 + 0.15 * Math.Min(consecutiveDynamicJumps - 2, 6);
                }
                else
                {
                    consecutiveDynamicJumps = Math.Max(0, consecutiveDynamicJumps - 1);
                }

                dynamicStrain += transitionStrain;
            }
            else
            {
                consecutiveDynamicJumps = Math.Max(0, consecutiveDynamicJumps - 1);
            }

            // ========================
            // EXTREME DYNAMIC TRANSITIONS
            // ========================
            if (current.Previous != null)
            {
                // fff to ppp (accent to ghost)
                if (current.Previous.MaxVelocity > 0.85 && current.MaxVelocity < 0.35)
                    dynamicStrain += 3.0;

                // ppp to fff (ghost to accent)
                if (current.Previous.MaxVelocity < 0.35 && current.MaxVelocity > 0.85)
                    dynamicStrain += 2.5;
            }

            // ========================
            // SUSTAINED QUIET PLAYING
            // ========================
            if (current.AverageVelocity < 0.35 && current.DeltaTime < 150)
            {
                dynamicStrain += 0.8; // Finesse under pressure
            }

            // ========================
            // EXTREME LOUD PLAYING
            // ========================
            if (current.MaxVelocity > 0.9 && current.DeltaTime < 100)
            {
                dynamicStrain += 0.5; // Power at speed
            }

            previousVelocity = current.AverageVelocity;

            return dynamicStrain;
        }

        private double CalculateContextBonuses(HashSet<TechniqueType> techniques, DifficultyHitObject current)
        {
            double bonus = 0;

            // ========================
            // GHOST NOTES IN CONTEXT
            // ========================
            if (techniques.Contains(TechniqueType.GhostNote))
            {
                // Coming down from accent
                if (current.Previous?.MaxVelocity > 0.8 ||
                    current.GetPrevious(1)?.MaxVelocity > 0.8)
                {
                    bonus += 2.0;
                }

                // Ghost notes during high activity
                if (current.DeltaTime < 80 && current.LimbCount >= 2)
                {
                    bonus += 1.5;
                }
            }

            // ========================
            // HI-HAT FOOT INDEPENDENCE
            // ========================
            if (techniques.Contains(TechniqueType.HiHatBark) ||
                techniques.Contains(TechniqueType.HiHatChick) ||
                techniques.Contains(TechniqueType.HiHatSplash))
            {
                // Foot technique while hands are busy
                if (current.HasHand && current.DeltaTime < 150)
                    bonus += 1.5;

                // During double bass
                if (current.IsDoubleBass)
                    bonus += 2.0;
            }

            // ========================
            // CYMBAL CHOKE TIMING
            // ========================
            if (techniques.Contains(TechniqueType.Choke))
            {
                bool justHitCymbal = current.Previous?.DrumTypes.Any(d =>
                    d == DrumType.Crash || d == DrumType.China || d == DrumType.Splash) == true;

                if (justHitCymbal)
                {
                    // Choke immediately after hit
                    if (current.DeltaTime < 200)
                        bonus += 2.0;
                    if (current.DeltaTime < 100)
                        bonus += 1.5;
                }
            }

            // ========================
            // CROSS-STICK DURING GROOVE
            // ========================
            if (techniques.Contains(TechniqueType.CrossStick))
            {
                // Cross-stick requires position change
                if (current.DeltaTime < 200)
                    bonus += 1.0;
            }

            // ========================
            // DOUBLE PEDAL IN COORDINATION
            // ========================
            if (techniques.Contains(TechniqueType.DoublePedalBurst) ||
                techniques.Contains(TechniqueType.SlideDouble))
            {
                // With hand activity
                if (current.LimbCount >= 3)
                    bonus += 2.0;

                // At extreme speed
                if (current.DeltaTime < 50)
                    bonus += 2.5;
            }

            return bonus;
        }

        private double CalculateSustainedTechniqueDifficulty(HashSet<TechniqueType> techniques)
        {
            double strain = 0;

            // Track sustained technique usage
            foreach (var tech in techniques)
            {
                if (!sustainedTechniqueCount.ContainsKey(tech))
                    sustainedTechniqueCount[tech] = 0;
                sustainedTechniqueCount[tech]++;

                // Long sustained techniques are very demanding
                if (sustainedTechniqueCount[tech] > 8)
                {
                    double sustainFactor = 0.1 * Math.Min(sustainedTechniqueCount[tech] - 8, 16);

                    // Some techniques are harder to sustain
                    if (tech == TechniqueType.Roll || tech == TechniqueType.BuzzRoll)
                        sustainFactor *= 1.3;
                    if (tech == TechniqueType.DoublePedalBurst)
                        sustainFactor *= 1.5;
                    if (tech == TechniqueType.GhostNote)
                        sustainFactor *= 1.2;

                    strain += sustainFactor;
                }
            }

            // Decay counts for inactive techniques
            foreach (var key in sustainedTechniqueCount.Keys.ToList())
            {
                if (!techniques.Contains(key))
                    sustainedTechniqueCount[key] = Math.Max(0, sustainedTechniqueCount[key] - 2);
            }

            return strain;
        }

        private double CalculateMotorComplexity(HashSet<TechniqueType> techniques, DifficultyHitObject current)
        {
            double complexity = 0;

            // Count motor skill types required
            int fineMotorCount = 0;
            int grossMotorCount = 0;
            int coordinationCount = 0;

            foreach (var tech in techniques)
            {
                if (IsFineMotorTechnique(tech)) fineMotorCount++;
                if (IsGrossMotorTechnique(tech)) grossMotorCount++;
                if (IsCoordinationTechnique(tech)) coordinationCount++;
            }

            // Mixed motor skills = higher complexity
            if (fineMotorCount > 0 && grossMotorCount > 0)
                complexity += 1.5;

            // Multiple coordination demands
            if (coordinationCount > 1)
                complexity += coordinationCount * 0.8;

            // Fine motor at speed
            if (fineMotorCount > 0 && current.DeltaTime < 100)
                complexity += fineMotorCount * 0.5;

            return complexity;
        }

        // ========================
        // HELPER METHODS
        // ========================

        private static bool IsHandTechnique(TechniqueType tech)
        {
            return tech switch
            {
                TechniqueType.Flam or
                TechniqueType.Drag or
                TechniqueType.Roll or
                TechniqueType.BuzzRoll or
                TechniqueType.DoubleStroke or
                TechniqueType.GhostNote or
                TechniqueType.Rimshot or
                TechniqueType.CrossStick or
                TechniqueType.Choke or
                TechniqueType.Accent => true,
                _ => false
            };
        }

        private static bool IsHiHatTechnique(TechniqueType tech)
        {
            return tech switch
            {
                TechniqueType.HiHatBark or
                TechniqueType.HiHatSplash or
                TechniqueType.HiHatChick or
                TechniqueType.HiHatHalfOpen => true,
                _ => false
            };
        }

        private static bool IsFineMotorTechnique(TechniqueType tech)
        {
            return tech switch
            {
                TechniqueType.GhostNote or
                TechniqueType.BuzzRoll or
                TechniqueType.Flam or
                TechniqueType.Drag => true,
                _ => false
            };
        }

        private static bool IsGrossMotorTechnique(TechniqueType tech)
        {
            return tech switch
            {
                TechniqueType.Accent or
                TechniqueType.Rimshot or
                TechniqueType.DoublePedalBurst or
                TechniqueType.Choke => true,
                _ => false
            };
        }

        private static bool IsCoordinationTechnique(TechniqueType tech)
        {
            return tech switch
            {
                TechniqueType.HiHatBark or
                TechniqueType.HiHatSplash or
                TechniqueType.DoublePedalBurst or
                TechniqueType.SlideDouble => true,
                _ => false
            };
        }
    }
}
