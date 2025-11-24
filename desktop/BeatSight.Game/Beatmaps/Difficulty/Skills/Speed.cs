using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// Evaluates the speed/density difficulty of the beatmap.
    /// 
    /// Speed difficulty represents the raw physical demand of note density—how fast
    /// must the drummer's hands and feet move to hit all the notes on time.
    /// 
    /// KEY DESIGN PRINCIPLES:
    /// 
    /// 1. NONLINEAR SPEED SCALING
    ///    Speed difficulty doesn't scale linearly—16th notes at 200 BPM aren't just
    ///    2x harder than at 100 BPM, they're exponentially more difficult due to
    ///    physical limits of muscle twitch speed, rebound control, and endurance.
    ///    
    /// 2. TECHNIQUE-SPECIFIC SPEED BONUSES
    ///    - Double bass at speed is one of the most demanding skills in drumming
    ///    - Blast beats require alternating limbs at extreme speeds
    ///    - Single-stroke rolls demand precise rebound control
    ///    - These get multiplicative bonuses at extreme speeds
    ///    
    /// 3. SUSTAINED SPEED vs BURST
    ///    Sustained fast playing is harder than isolated bursts due to fatigue.
    ///    Track consecutive fast notes and apply exponential strain bonuses.
    ///    
    /// 4. CONTEXT-DEPENDENT DIFFICULTY
    ///    Playing fast while:
    ///    - Moving around the kit
    ///    - Playing at high volumes
    ///    - Maintaining multiple limbs simultaneously
    ///    All compound the difficulty multiplicatively.
    /// 
    /// SPEED TIERS (ms between notes → notes/second):
    /// - Normal:      > 100ms   (< 10 NPS)
    /// - Fast:        66-100ms  (10-15 NPS)
    /// - Very Fast:   50-66ms   (15-20 NPS) - Blast beat territory
    /// - Insane:      40-50ms   (20-25 NPS) - World-class speed
    /// - Superhuman:  30-40ms   (25-33 NPS) - Peak human capability
    /// - Transcendent: < 30ms   (> 33 NPS) - May exceed human limits
    /// 
    /// This skill rewards extreme drummers like:
    /// - Matt Garstka (Animals as Leaders) - complex patterns at speed
    /// - Gene Hoglan (Death, Strapping Young Lad) - superhuman double bass
    /// - George Kollias (Nile) - sustained blast beats
    /// - Marco Minnemann (The Aristocrats) - technical speed + complexity
    /// </summary>
    public class Speed : Skill
    {
        // ===========================================
        // SKILL CONFIGURATION
        // ===========================================

        /// <summary>
        /// Main multiplier for speed strain values.
        /// Calibrated so that extreme speed produces values in the 80-120 range.
        /// </summary>
        protected override double SkillMultiplier => 28.0;

        /// <summary>
        /// Fast decay (0.3 = 30% remains after 1 second).
        /// Speed is momentary—you're either playing fast or you're not.
        /// Faster decay means isolated fast notes don't inflate rating.
        /// </summary>
        protected override double StrainDecayBase => 0.30;

        // ===========================================
        // SPEED THRESHOLDS (milliseconds between notes)
        // ===========================================
        // These thresholds define the speed tiers with carefully calibrated
        // bonus multipliers for each tier.

        /// <summary>10 NPS - where "fast" begins</summary>
        private const double FAST_THRESHOLD = 100;

        /// <summary>15 NPS - very fast, demanding for most drummers</summary>
        private const double VERY_FAST_THRESHOLD = 66;

        /// <summary>20 NPS - blast beat territory, elite speed</summary>
        private const double INSANE_THRESHOLD = 50;

        /// <summary>25 NPS - world-class, near peak human capability</summary>
        private const double WORLD_CLASS_THRESHOLD = 40;

        /// <summary>33 NPS - superhuman, theoretical human limits</summary>
        private const double SUPERHUMAN_THRESHOLD = 30;

        // ===========================================
        // BURST TRACKING
        // ===========================================

        /// <summary>Number of consecutive fast notes</summary>
        private int consecutiveFastNotes = 0;

        /// <summary>Minimum notes to consider a "burst"</summary>
        private const int BURST_THRESHOLD = 4;

        /// <summary>Previous drum types for jackhammer detection</summary>
        private List<DrumType> previousDrumTypes = new();

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;

            // ===========================================
            // 1. BASE SPEED STRAIN
            // ===========================================
            // Inverse relationship: faster = exponentially harder
            // Using StrainTime (capped minimum) to avoid extreme values
            double baseSpeed = 1.0 / current.StrainTime;
            strain += baseSpeed * 55.0;

            // ===========================================
            // 2. TIERED SPEED BONUSES
            // ===========================================
            // Apply multiplicative bonuses for each speed tier breached
            strain *= CalculateSpeedBonus(current.DeltaTime);

            // ===========================================
            // 3. DOUBLE BASS BONUS
            // ===========================================
            // Double bass drumming at speed is one of the most demanding
            // physical skills in drumming. Apply substantial bonuses.
            if (current.IsDoubleBass)
            {
                strain *= CalculateDoubleBassBonus(current.DeltaTime);
            }

            // ===========================================
            // 4. BLAST BEAT BONUS
            // ===========================================
            // Blast beats require coordinating alternating kicks/snares
            // with cymbal riding at extreme speeds.
            if (current.IsBlastBeat)
            {
                strain *= CalculateBlastBeatBonus(current);
            }

            // ===========================================
            // 5. BURST PATTERN BONUS
            // ===========================================
            // Sustained fast playing is harder than isolated fast notes.
            // Track consecutive fast notes and apply scaling bonus.
            strain *= CalculateBurstBonus(current.DeltaTime);

            // ===========================================
            // 6. SAME-DRUM REPETITION (JACKHAMMER) BONUS
            // ===========================================
            // Hitting the same surface rapidly requires precise rebound
            // control and is taxing on specific muscle groups.
            strain *= CalculateJackhammerBonus(current);

            // ===========================================
            // 7. MULTI-NOTE DENSITY BONUS
            // ===========================================
            // Multiple drums hit simultaneously at speed compounds difficulty
            if (current.NoteCount > 1)
            {
                double densityBonus = 1.0 + (current.NoteCount - 1) * 0.18;
                strain *= densityBonus;
            }

            // ===========================================
            // 8. MOVEMENT WHILE FAST BONUS
            // ===========================================
            // Moving around the kit while playing fast requires
            // exceptional motor control and spatial awareness.
            if (current.TravelDistance > 0 && current.DeltaTime < FAST_THRESHOLD)
            {
                double movementBonus = 1.0 + current.TravelDistance * 0.35 *
                    (FAST_THRESHOLD / Math.Max(current.DeltaTime, SUPERHUMAN_THRESHOLD));
                strain *= Math.Min(movementBonus, 2.2); // Cap at 2.2x
            }

            // ===========================================
            // 9. VELOCITY (VOLUME) CONSIDERATION
            // ===========================================
            // Playing loud and fast is harder than quiet and fast due to
            // the energy required for each stroke.
            if (current.AverageVelocity > 0.75 && current.DeltaTime < FAST_THRESHOLD)
            {
                double velocityBonus = 1.0 + (current.AverageVelocity - 0.75) * 0.4;
                strain *= velocityBonus;
            }

            // ===========================================
            // 10. LINEAR DRUMMING ADJUSTMENT
            // ===========================================
            // Linear patterns (one limb at a time) at speed have their own
            // challenges but are slightly easier than multi-limb coordination.
            if (current.IsLinear && current.Previous?.IsLinear == true)
            {
                strain *= 0.96; // Small reduction
            }

            // Update tracking state for next iteration
            previousDrumTypes = current.DrumTypes.ToList();

            return strain;
        }

        /// <summary>
        /// Calculate tiered speed bonus based on delta time.
        /// Uses smooth transitions between tiers to avoid cliff effects.
        /// </summary>
        private static double CalculateSpeedBonus(double deltaTime)
        {
            if (deltaTime >= FAST_THRESHOLD)
                return 1.0;

            double bonus = 1.0;

            if (deltaTime < SUPERHUMAN_THRESHOLD)
            {
                // Superhuman tier: 2.8x + exponential scaling
                bonus = 2.8 + Math.Pow((SUPERHUMAN_THRESHOLD - deltaTime) / 8.0, 1.6);
            }
            else if (deltaTime < WORLD_CLASS_THRESHOLD)
            {
                // World-class tier: 2.2x base
                double progress = (WORLD_CLASS_THRESHOLD - deltaTime) / (WORLD_CLASS_THRESHOLD - SUPERHUMAN_THRESHOLD);
                bonus = 2.2 + progress * 0.6;
            }
            else if (deltaTime < INSANE_THRESHOLD)
            {
                // Insane tier: 1.8x base
                double progress = (INSANE_THRESHOLD - deltaTime) / (INSANE_THRESHOLD - WORLD_CLASS_THRESHOLD);
                bonus = 1.8 + progress * 0.4;
            }
            else if (deltaTime < VERY_FAST_THRESHOLD)
            {
                // Very fast tier: 1.4x base
                double progress = (VERY_FAST_THRESHOLD - deltaTime) / (VERY_FAST_THRESHOLD - INSANE_THRESHOLD);
                bonus = 1.4 + progress * 0.4;
            }
            else
            {
                // Fast tier: 1.0-1.4x
                double progress = (FAST_THRESHOLD - deltaTime) / (FAST_THRESHOLD - VERY_FAST_THRESHOLD);
                bonus = 1.0 + progress * 0.4;
            }

            return bonus;
        }

        /// <summary>
        /// Calculate bonus for double bass patterns at speed.
        /// World-class double bass drummers can exceed 20 kicks/second/foot.
        /// </summary>
        private static double CalculateDoubleBassBonus(double deltaTime)
        {
            double bonus = 1.35; // Base double bass bonus

            if (deltaTime < 45) // > 22 kicks/sec per foot - superhuman
                bonus = 2.6;
            else if (deltaTime < 55) // > 18 kicks/sec - world-class
                bonus = 2.2;
            else if (deltaTime < 70) // > 14 kicks/sec - very demanding
                bonus = 1.8;
            else if (deltaTime < 90) // > 11 kicks/sec - challenging
                bonus = 1.5;

            return bonus;
        }

        /// <summary>
        /// Calculate bonus for blast beat patterns.
        /// Accounts for limb count and speed compound difficulty.
        /// </summary>
        private double CalculateBlastBeatBonus(DifficultyHitObject current)
        {
            double bonus = 1.45; // Base blast beat bonus

            if (current.DeltaTime < WORLD_CLASS_THRESHOLD)
                bonus = 2.3;
            else if (current.DeltaTime < INSANE_THRESHOLD)
                bonus = 1.9;
            else if (current.DeltaTime < VERY_FAST_THRESHOLD)
                bonus = 1.65;

            // Additional bonus for 4-limb blast variations
            if (current.LimbCount >= 4)
                bonus *= 1.25;
            else if (current.LimbCount >= 3)
                bonus *= 1.12;

            return bonus;
        }

        /// <summary>
        /// Calculate bonus for sustained fast playing (bursts/streams).
        /// Longer bursts are exponentially harder due to fatigue.
        /// </summary>
        private double CalculateBurstBonus(double deltaTime)
        {
            if (deltaTime < FAST_THRESHOLD)
            {
                consecutiveFastNotes++;

                if (consecutiveFastNotes >= BURST_THRESHOLD)
                {
                    // Exponential scaling for longer bursts
                    int burstLength = consecutiveFastNotes - BURST_THRESHOLD + 1;

                    // Cap at 16 notes to prevent extreme values
                    int cappedLength = Math.Min(burstLength, 16);

                    // 10% bonus per burst note, compounds
                    return 1.0 + 0.08 * cappedLength * (1.0 + 0.03 * cappedLength);
                }
            }
            else
            {
                // Gradual reset allows brief pauses in streams
                consecutiveFastNotes = Math.Max(0, consecutiveFastNotes - 2);
            }

            return 1.0;
        }

        /// <summary>
        /// Calculate bonus for hitting the same drum surface rapidly.
        /// Requires precise rebound control and is physically demanding.
        /// </summary>
        private double CalculateJackhammerBonus(DifficultyHitObject current)
        {
            if (current.Previous == null || current.DeltaTime >= FAST_THRESHOLD)
                return 1.0;

            var sameTypes = current.DrumTypes.Intersect(previousDrumTypes).ToList();
            if (!sameTypes.Any())
                return 1.0;

            double bonus = 1.12;

            // Snare/tom jackhammers are particularly demanding
            bool hasSnareTomJack = sameTypes.Any(t =>
                t == DrumType.Snare || t == DrumType.Tom ||
                t == DrumType.TomHigh || t == DrumType.TomMid || t == DrumType.TomLow);

            if (hasSnareTomJack)
                bonus = 1.22;

            // Kick jackhammer (heel-toe, swivel) is very demanding
            bool hasKickJack = sameTypes.Contains(DrumType.Kick);
            if (hasKickJack && current.DeltaTime < VERY_FAST_THRESHOLD)
                bonus = 1.4;

            // Hi-hat jackhammer at speed requires excellent wrist control
            bool hasHatJack = sameTypes.Contains(DrumType.HiHat);
            if (hasHatJack && current.DeltaTime < INSANE_THRESHOLD)
                bonus = 1.3;

            return bonus;
        }
    }
}