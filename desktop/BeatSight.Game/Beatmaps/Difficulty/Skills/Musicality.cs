using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// Musicality Skill - Musical Expression and Groove Analysis
    /// 
    /// This skill measures the musical sophistication and expressiveness of
    /// a drum part beyond pure technical execution. While other skills measure
    /// HOW HARD something is to play, Musicality measures HOW MUSICAL it is.
    /// 
    /// KEY CONCEPTS:
    /// 
    /// 1. DYNAMIC RANGE AND SHAPING
    ///    The span between quietest and loudest notes, and how dynamics
    ///    are shaped over phrases. Wide dynamic range with intentional
    ///    shaping indicates musical sophistication.
    ///    
    /// 2. GROOVE CONSISTENCY
    ///    How well the pattern maintains a consistent pocket or feel.
    ///    This includes swing feel, push/pull against the beat, and
    ///    intentional timing nuances that create groove.
    ///    
    /// 3. PHRASING AND STRUCTURE
    ///    Musical drumming has phrases that breathe—buildups, releases,
    ///    question-and-answer patterns, and structural awareness.
    ///    
    /// 4. TEXTURAL VARIETY
    ///    Using the full timbral palette of the kit—different drums,
    ///    cymbals, articulations, and sound colors in musical ways.
    ///    
    /// 5. SWING/FEEL EXECUTION
    ///    The difficulty of executing specific feels (straight, shuffle,
    ///    half-time shuffle, jazz swing, etc.) at various tempos.
    ///    
    /// 6. ACCENT PATTERNS
    ///    Sophisticated accent placement that creates melodic interest
    ///    within the groove or fill.
    /// 
    /// This skill rewards musical drummers like:
    /// - Steve Gadd (supreme groove and musicality)
    /// - Vinnie Colaiuta (dynamic mastery)
    /// - Jeff Porcaro (Rosanna shuffle, feel)
    /// - Tony Williams (jazz phrasing and interaction)
    /// - Questlove (pocket and groove)
    /// </summary>
    public class Musicality : Skill
    {
        protected override double SkillMultiplier => 16.0;
        protected override double StrainDecayBase => 0.08; // Slow decay - musicality accumulates

        // ========================
        // DYNAMIC TRACKING
        // ========================
        private readonly Queue<double> velocityHistory = new();
        private const int VELOCITY_HISTORY_SIZE = 32;

        private double phraseDynamicPeak = 0;
        private double phraseDynamicTrough = 1.0;
        private int phraseNoteCount = 0;

        // ========================
        // GROOVE TRACKING
        // ========================
        private readonly Queue<double> timingDeviations = new();
        private const int TIMING_HISTORY_SIZE = 16;

        private readonly Queue<double> deltaTimeHistory = new();
        private const int DELTA_HISTORY_SIZE = 16;

        // ========================
        // TEXTURE TRACKING
        // ========================
        private readonly HashSet<DrumType> usedDrumTypes = new();
        private readonly HashSet<TechniqueType> usedTechniques = new();
        private int textureWindowCount = 0;

        // ========================
        // ACCENT TRACKING
        // ========================
        private readonly Queue<(double velocity, int position)> accentPattern = new();
        private const int ACCENT_HISTORY_SIZE = 16;
        private int beatPosition = 0;

        // ========================
        // SWING/FEEL TRACKING
        // ========================
        private readonly Queue<double> swingRatios = new();
        private const int SWING_HISTORY_SIZE = 8;

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;

            // ========================
            // 1. DYNAMIC EXPRESSION
            // ========================
            strain += CalculateDynamicExpressionStrain(current);

            // ========================
            // 2. GROOVE FEEL
            // ========================
            strain += CalculateGrooveFeelStrain(current);

            // ========================
            // 3. TEXTURAL VARIETY
            // ========================
            strain += CalculateTexturalVarietyStrain(current);

            // ========================
            // 4. ACCENT SOPHISTICATION
            // ========================
            strain += CalculateAccentSophisticationStrain(current);

            // ========================
            // 5. SWING/SHUFFLE EXECUTION
            // ========================
            strain += CalculateSwingExecutionStrain(current);

            // ========================
            // 6. PHRASE STRUCTURE
            // ========================
            strain += CalculatePhraseStructureStrain(current);

            // ========================
            // 7. TEMPO-DEPENDENT FEEL
            // ========================
            strain *= GetTempoFeelMultiplier(current.CurrentBpm);

            // Update histories
            UpdateMusicialityHistories(current);

            return strain;
        }

        // ========================
        // DYNAMIC EXPRESSION
        // ========================

        private double CalculateDynamicExpressionStrain(DifficultyHitObject current)
        {
            double strain = 0;
            double velocity = current.AverageVelocity;

            if (velocityHistory.Count < 4) return 0;

            // Track phrase dynamics
            phraseDynamicPeak = Math.Max(phraseDynamicPeak, velocity);
            phraseDynamicTrough = Math.Min(phraseDynamicTrough, velocity);
            phraseNoteCount++;

            // Calculate recent dynamic range
            double recentMax = velocityHistory.Max();
            double recentMin = velocityHistory.Min();
            double dynamicRange = recentMax - recentMin;

            // Wide dynamic range is musical
            if (dynamicRange > 0.3)
            {
                strain += dynamicRange * 2.0;
            }

            // Dynamic changes (crescendo/decrescendo)
            var velocityList = velocityHistory.ToList();
            velocityList.Add(velocity);

            // Check for consistent crescendo/decrescendo
            bool crescendo = true;
            bool decrescendo = true;

            for (int i = velocityList.Count - 4; i < velocityList.Count - 1; i++)
            {
                if (i < 0) continue;
                if (velocityList[i + 1] < velocityList[i]) crescendo = false;
                if (velocityList[i + 1] > velocityList[i]) decrescendo = false;
            }

            // Intentional dynamic shaping
            if (crescendo || decrescendo)
            {
                double shapeAmount = Math.Abs(velocityList.Last() - velocityList[^4]);
                strain += shapeAmount * 3.0;
            }

            // Sudden dynamic contrasts (sfz, subito piano)
            var recentVelocities = velocityHistory.TakeLast(3).ToList();
            if (recentVelocities.Count >= 2)
            {
                double velocityJump = Math.Abs(velocity - recentVelocities.Last());
                if (velocityJump > 0.4)
                {
                    strain += velocityJump * 2.5; // Dramatic dynamic shift
                }
            }

            return strain;
        }

        // ========================
        // GROOVE FEEL
        // ========================

        private double CalculateGrooveFeelStrain(DifficultyHitObject current)
        {
            double strain = 0;

            if (deltaTimeHistory.Count < 4) return 0;

            // Analyze timing consistency for groove
            var deltas = deltaTimeHistory.ToList();
            deltas.Add(current.DeltaTime);

            // Calculate variance in timing (low variance = tight pocket)
            double avgDelta = deltas.Average();
            double variance = deltas.Sum(d => Math.Pow(d - avgDelta, 2)) / deltas.Count;
            double stdDev = Math.Sqrt(variance);

            // Very tight groove (low deviation) at fast tempos is difficult
            if (stdDev < avgDelta * 0.05) // Within 5% = tight groove
            {
                double tightnessDifficulty = (1.0 - stdDev / avgDelta) * 2.0;
                strain += tightnessDifficulty;
            }

            // Intentional push/pull (consistent slight deviation)
            double avgDeviation = timingDeviations.Count > 0 ? timingDeviations.Average() : 0;
            if (Math.Abs(avgDeviation) > 0.02 && Math.Abs(avgDeviation) < 0.1)
            {
                // Consistent slight push or pull = intentional feel
                strain += Math.Abs(avgDeviation) * 8.0;
            }

            // Ghost note groove complexity
            if (current.Techniques.Contains(TechniqueType.GhostNote))
            {
                // Ghost notes in groove context = musical
                if (current.DrumTypes.Contains(DrumType.Snare))
                {
                    strain += 1.5;
                }
            }

            return strain;
        }

        // ========================
        // TEXTURAL VARIETY
        // ========================

        private double CalculateTexturalVarietyStrain(DifficultyHitObject current)
        {
            // Track drum and technique usage
            foreach (var drum in current.DrumTypes)
                usedDrumTypes.Add(drum);

            foreach (var tech in current.Techniques)
                if (tech != TechniqueType.Normal)
                    usedTechniques.Add(tech);

            textureWindowCount++;

            // Calculate variety strain periodically
            if (textureWindowCount < 16) return 0;

            double strain = 0;

            // Reward wide timbral palette
            int drumVariety = usedDrumTypes.Count;
            if (drumVariety >= 5)
            {
                strain += (drumVariety - 4) * 0.3;
            }

            // Reward technique variety
            int techVariety = usedTechniques.Count;
            if (techVariety >= 3)
            {
                strain += (techVariety - 2) * 0.5;
            }

            // Specific musical techniques
            if (usedTechniques.Contains(TechniqueType.GhostNote) &&
                usedTechniques.Contains(TechniqueType.Accent))
            {
                strain += 1.0; // Ghost-accent interplay is musical
            }

            if (usedTechniques.Contains(TechniqueType.HiHatBark) ||
                usedTechniques.Contains(TechniqueType.HiHatSplash))
            {
                strain += 0.8; // Hi-hat expression
            }

            // Reset window periodically
            if (textureWindowCount >= 32)
            {
                usedDrumTypes.Clear();
                usedTechniques.Clear();
                textureWindowCount = 0;
            }

            return strain;
        }

        // ========================
        // ACCENT SOPHISTICATION
        // ========================

        private double CalculateAccentSophisticationStrain(DifficultyHitObject current)
        {
            double strain = 0;
            double velocity = current.AverageVelocity;

            // Track accent pattern
            bool isAccent = velocity > 0.7 || current.Techniques.Contains(TechniqueType.Accent);
            accentPattern.Enqueue((velocity, beatPosition % 16));
            if (accentPattern.Count > ACCENT_HISTORY_SIZE)
                accentPattern.Dequeue();

            beatPosition++;

            if (accentPattern.Count < 8) return 0;

            // Analyze accent placement
            var accents = accentPattern.Where(a => a.velocity > 0.7).ToList();

            // Syncopated accents (off beat positions)
            int syncopatedAccents = accents.Count(a =>
                a.position % 4 != 0 && // Not on downbeat
                a.position % 2 != 0    // Not on strong beat
            );

            if (syncopatedAccents >= 2)
            {
                strain += syncopatedAccents * 0.8;
            }

            // Accent groupings (3s in 4/4, etc.)
            if (accents.Count >= 3)
            {
                // Check for grouping patterns
                var intervals = new List<int>();
                for (int i = 1; i < accents.Count; i++)
                {
                    int interval = (accents[i].position - accents[i - 1].position + 16) % 16;
                    intervals.Add(interval);
                }

                // Consistent unusual groupings (like 3-3-3-3-4 in 16)
                if (intervals.Distinct().Count() <= 2 && intervals.Any(i => i == 3 || i == 5 || i == 7))
                {
                    strain += 2.0; // Sophisticated accent grouping
                }
            }

            return strain;
        }

        // ========================
        // SWING EXECUTION
        // ========================

        private double CalculateSwingExecutionStrain(DifficultyHitObject current)
        {
            double strain = 0;

            // Calculate swing ratio from consecutive notes
            if (deltaTimeHistory.Count >= 2)
            {
                var recentDeltas = deltaTimeHistory.TakeLast(2).ToList();
                if (recentDeltas[1] > 0)
                {
                    double ratio = recentDeltas[0] / recentDeltas[1];
                    swingRatios.Enqueue(ratio);
                    if (swingRatios.Count > SWING_HISTORY_SIZE)
                        swingRatios.Dequeue();
                }
            }

            if (swingRatios.Count < 4) return 0;

            var ratios = swingRatios.ToList();
            double avgRatio = ratios.Average();

            // Detect swing/shuffle feel
            // Straight: ratio ≈ 1.0
            // Light swing: ratio ≈ 1.3-1.5
            // Heavy swing (triplet): ratio ≈ 2.0
            // Shuffle: alternating pattern

            // Consistent swing feel is difficult to execute
            if (avgRatio > 1.2 && avgRatio < 2.5)
            {
                // How consistent is the swing?
                double swingVariance = ratios.Sum(r => Math.Pow(r - avgRatio, 2)) / ratios.Count;
                double consistency = 1.0 / (1.0 + swingVariance * 10);

                // Tight swing feel = musical difficulty
                strain += consistency * 2.0;

                // Specific feel bonuses
                if (avgRatio >= 1.8 && avgRatio <= 2.2)
                {
                    strain += 1.5; // Triplet swing (jazz)
                }
                else if (avgRatio >= 1.4 && avgRatio <= 1.6)
                {
                    strain += 1.0; // Light swing
                }
            }

            // Half-time shuffle (Rosanna-style) detection
            // This requires more sophisticated pattern analysis
            // For now, reward shuffle patterns with ghost notes
            if (avgRatio > 1.5 && current.Techniques.Contains(TechniqueType.GhostNote))
            {
                strain += 2.0; // Shuffle with ghosts = musical
            }

            return strain;
        }

        // ========================
        // PHRASE STRUCTURE
        // ========================

        private double CalculatePhraseStructureStrain(DifficultyHitObject current)
        {
            double strain = 0;

            // Detect phrase boundaries
            bool isPhraseEnd = false;

            // Long note gap suggests phrase break
            if (current.DeltaTime > 500)
            {
                isPhraseEnd = true;
            }

            // Crash cymbal often marks phrase boundaries
            if (current.DrumTypes.Contains(DrumType.Crash))
            {
                // Phrase-appropriate crash placement
                if (phraseNoteCount >= 8 && phraseNoteCount <= 32)
                {
                    strain += 0.5; // Well-placed phrase marker
                }
            }

            // Evaluate completed phrase
            if (isPhraseEnd && phraseNoteCount >= 4)
            {
                // Phrase had dynamic arc
                double phraseArc = phraseDynamicPeak - phraseDynamicTrough;
                if (phraseArc > 0.3)
                {
                    strain += phraseArc * 2.0; // Musical phrasing
                }

                // Reset phrase tracking
                phraseDynamicPeak = 0;
                phraseDynamicTrough = 1.0;
                phraseNoteCount = 0;
            }

            // Build-up patterns (crescendo into phrase end)
            if (velocityHistory.Count >= 4)
            {
                var recentVels = velocityHistory.TakeLast(4).ToList();
                bool isBuildUp = true;

                for (int i = 1; i < recentVels.Count; i++)
                {
                    if (recentVels[i] < recentVels[i - 1]) isBuildUp = false;
                }

                if (isBuildUp && current.AverageVelocity > 0.8)
                {
                    strain += 1.5; // Musical build-up
                }
            }

            return strain;
        }

        // ========================
        // TEMPO FEEL MULTIPLIER
        // ========================

        private double GetTempoFeelMultiplier(double bpm)
        {
            // Certain tempos are harder to groove at musically
            // Very slow (ballad): hard to maintain feel
            // Very fast: less room for expression
            // Medium: sweet spot for musicality

            if (bpm < 60) return 1.3;       // Slow ballad feel is demanding
            if (bpm < 80) return 1.2;       // Slow groove
            if (bpm < 120) return 1.0;      // Comfortable groove tempo
            if (bpm < 160) return 1.1;      // Up-tempo - less room for nuance
            if (bpm < 200) return 1.2;      // Fast - musicality under pressure

            return 1.3;                     // Very fast - hard to be musical
        }

        // ========================
        // HISTORY MANAGEMENT
        // ========================

        private void UpdateMusicialityHistories(DifficultyHitObject current)
        {
            // Velocity
            velocityHistory.Enqueue(current.AverageVelocity);
            if (velocityHistory.Count > VELOCITY_HISTORY_SIZE)
                velocityHistory.Dequeue();

            // Delta time
            deltaTimeHistory.Enqueue(current.DeltaTime);
            if (deltaTimeHistory.Count > DELTA_HISTORY_SIZE)
                deltaTimeHistory.Dequeue();

            // Timing deviation (grid deviation)
            timingDeviations.Enqueue(current.GridDeviation);
            if (timingDeviations.Count > TIMING_HISTORY_SIZE)
                timingDeviations.Dequeue();
        }
    }
}
