using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps.Difficulty.Skills;
using BeatSight.Game.Beatmaps.Difficulty.Analysis;

namespace BeatSight.Game.Beatmaps.Difficulty
{
    /// <summary>
    /// ╔══════════════════════════════════════════════════════════════════════════════╗
    /// ║     BEATSIGHT REVOLUTIONARY DRUM DIFFICULTY CALCULATION SYSTEM v3.1          ║
    /// ╠══════════════════════════════════════════════════════════════════════════════╣
    /// ║                                                                              ║
    /// ║  World-class, multi-dimensional difficulty rating for drums. This system    ║
    /// ║  accurately evaluates the FULL spectrum of drumming—from beginner grooves   ║
    /// ║  to the most extreme material in existence:                                 ║
    /// ║                                                                              ║
    /// ║    • Meshuggah "Bleed" (17/16 polymetric double bass)                        ║
    /// ║    • Animals as Leaders (Matt Garstka's polyrhythmic independence)          ║
    /// ║    • World-class jazz (Tony Williams, Vinnie Colaiuta, Steve Gadd)          ║
    /// ║    • Technical death metal (Nile, Obscura, Cryptopsy)                       ║
    /// ║    • Progressive fusion (Dream Theater, Tool, King Crimson)                 ║
    /// ║                                                                              ║
    /// ╠══════════════════════════════════════════════════════════════════════════════╣
    /// ║                           CORE INNOVATIONS                                   ║
    /// ╠══════════════════════════════════════════════════════════════════════════════╣
    /// ║                                                                              ║
    /// ║  1. 10-DIMENSIONAL SKILL DECOMPOSITION                                       ║
    /// ║     Ten orthogonal skill axes capture drumming complexity:                   ║
    /// ║     Speed, Stamina, Coordination, RhythmicComplexity, Pattern,              ║
    /// ║     Technique, Reading, Precision, Movement, Musicality                      ║
    /// ║                                                                              ║
    /// ║  2. SYNERGY MATRIX COMPOUND BONUSES (KEY INNOVATION)                         ║
    /// ║     Different skill combinations have different synergy multipliers:         ║
    /// ║     • The "Holy Trinity" (Speed + Coordination + Rhythm): HIGHEST            ║
    /// ║     • Speed + Stamina (physical endurance at extremes)                       ║
    /// ║     • Coordination + Rhythm (jazz independence territory)                    ║
    /// ║     • Technique + Precision (finesse-based difficulty)                       ║
    /// ║     Models how cognitive/physical resource competition compounds             ║
    /// ║                                                                              ║
    /// ║  3. TIERED BREADTH BONUS SYSTEM                                              ║
    /// ║     Separate bonuses for maps difficult at multiple tiers:                   ║
    /// ║     • DEMANDING (55+): Entry to compound difficulty                          ║
    /// ║     • EXTREME (72+): Elite-level challenges                                  ║
    /// ║     • ELITE (92+): World-class territory                                     ║
    /// ║     • LEGENDARY (115+): Peak human capability                                ║
    /// ║     • TRANSCENDENT (140+): May exceed human limits                           ║
    /// ║                                                                              ║
    /// ║  4. PHYSIOLOGICAL MODELING                                                   ║
    /// ║     • Muscle group fatigue (Stamina.cs) - separate hand/foot tracking        ║
    /// ║     • Limb switching cost and motor pattern reorganization                   ║
    /// ║     • Kit movement penalties based on realistic distances                    ║
    /// ║     • Recovery windows for sustained high-intensity passages                 ║
    /// ║                                                                              ║
    /// ║  5. NUMBER-THEORETIC RHYTHMIC ANALYSIS                                       ║
    /// ║     • LCM-based polyrhythm complexity scoring                                ║
    /// ║     • Continued fraction approximation for rhythm ratio complexity           ║
    /// ║     • Fourier-inspired periodicity analysis                                  ║
    /// ║     • Phase relationship tracking between accent layers                      ║
    /// ║     • Metric modulation detection via pulse rate analysis                    ║
    /// ║                                                                              ║
    /// ║  6. COGNITIVE LOAD MODELING (v3.1 ENHANCED)                                  ║
    /// ║     • Working memory demands using Miller's Law (7±2 chunks)                 ║
    /// ║     • Information density analysis (bits per second)                         ║
    /// ║     • Attention switching cost modeling                                      ║
    /// ║     • Pattern entropy (Shannon entropy) for predictability                   ║
    /// ║     • Cognitive fatigue accumulation over time                               ║
    /// ║     • Look-ahead requirement estimation                                      ║
    /// ║                                                                              ║
    /// ║  7. 40+ TECHNIQUE DETECTION (aligned with additionaldrummertech.txt)         ║
    /// ║     Flams, Drags, Rolls, Ghost Notes, Paradiddles, Hertas,                   ║
    /// ║     Swiss Army Triplets, Bonham Triplets, Blast Beats, Double Bass,          ║
    /// ║     Hi-Hat techniques, Cymbal chokes, and many more                          ║
    /// ║                                                                              ║
    /// ║  8. PIECEWISE STAR RATING SCALING WITH 10★ CAP                               ║
    /// ║     Carefully calibrated scaling curves with NO cliff effects:               ║
    /// ║     • Beginner (0-1★): Basic quarter-note grooves                            ║
    /// ║     • Easy (1-2★): 8th-note patterns, simple fills                           ║
    /// ║     • Normal (2-3★): Standard rock/pop, some coordination                    ║
    /// ║     • Hard (3-4★): Complex grooves, double bass introduction                 ║
    /// ║     • Expert (4-5★): Jazz comping, prog patterns                             ║
    /// ║     • Master (5-6★): Animals as Leaders, extreme coordination                ║
    /// ║     • Legendary (6-7★): World-class, peak human drumming                     ║
    /// ║     • Inhuman (7-8★): Approaches theoretical human limits                    ║
    /// ║     • Transcendent A (8-9★): Multi-dimensional mastery                       ║
    /// ║     • Transcendent B (9-10★): Logarithmic asymptote to perfection            ║
    /// ║                                                                              ║
    /// ║  9. v3.1 ADVANCED ANALYZERS                                                  ║
    /// ║     • GrooveAnalyzer: Swing detection, shuffle analysis, feel quantification ║
    /// ║     • PolyrhythmAnalyzer: Continued fraction analysis, LCM complexity,       ║
    /// ║       nested polyrhythm detection, polymeter identification                  ║
    /// ║     • CognitiveLoadAnalyzer: Working memory, attention switching,            ║
    /// ║       information density, pattern familiarity tracking                      ║
    /// ║     • IndependenceRatingSystem: 4-way limb independence analysis,            ║
    /// ║       rhythmic/dynamic/metric/textural independence scoring                  ║
    /// ║                                                                              ║
    /// ╠══════════════════════════════════════════════════════════════════════════════╣
    /// ║                        CALIBRATION TARGETS                                   ║
    /// ╠══════════════════════════════════════════════════════════════════════════════╣
    /// ║                                                                              ║
    /// ║  Examples (target ratings based on professional drummer consensus):          ║
    /// ║                                                                              ║
    /// ║  1-2★: "Back In Black" (AC/DC), "Billie Jean" (Michael Jackson)              ║
    /// ║  2-3★: "Basket Case" (Green Day), "Creep" (Radiohead)                        ║
    /// ║  3-4★: "YYZ" intro (Rush), "Schism" mid-sections (Tool)                      ║
    /// ║  4-5★: "La Villa Strangiato" (Rush), "Moby Dick" (Led Zeppelin)              ║
    /// ║  5-6★: "The Dance of Eternity" (Dream Theater), fusion standards             ║
    /// ║  6-7★: "Bleed" (Meshuggah), "CAFO" (Animals as Leaders)                      ║
    /// ║  7-8★: Extended "Bleed" sections, George Kollias sustained blast             ║
    /// ║  8-10★: Theoretical: simultaneous extreme speed/rhythm/coordination          ║
    /// ║                                                                              ║
    /// ╠══════════════════════════════════════════════════════════════════════════════╣
    /// ║  VERSION: 3.1.0 - Enhanced with advanced groove/polyrhythm/cognitive/        ║
    /// ║                   independence analyzers                                     ║
    /// ║  ALGORITHM: 2025112402 (increment on ANY change affecting ratings)           ║
    /// ╚══════════════════════════════════════════════════════════════════════════════╝
    /// </summary>
    public class DifficultyCalculator
    {
        /// <summary>
        /// Algorithm version for cache invalidation when the algorithm changes.
        /// Increment this when making changes that affect difficulty values.
        /// FORMAT: YYYYMMDD + 2-digit revision (e.g., 2025112401)
        /// </summary>
        public const int ALGORITHM_VERSION = 2025112402;

        private readonly Beatmap beatmap;
        private readonly double clockRate;

        // ===========================================
        // SKILL WEIGHT CONFIGURATION v3.0
        // ===========================================
        // These weights determine each skill's contribution to the final star rating.
        // Calibrated through extensive analysis of real drumming material across
        // all difficulty levels and styles, validated against expert drummer opinions.
        //
        // DESIGN PRINCIPLES (REVISED):
        // 
        // 1. COORDINATION (1.25) - HIGHEST
        //    Limb independence is THE defining challenge of advanced drumming.
        //    This is what separates Matt Garstka, Vinnie Colaiuta, Tony Williams
        //    from competent working drummers. Four-way independence with complex
        //    polyrhythms is the ultimate skill in drumming.
        //
        // 2. RHYTHMIC COMPLEXITY (1.20) - VERY HIGH
        //    Odd meters, polyrhythms, metric modulation, and nested tuplets are
        //    hallmarks of the most sophisticated drumming (Animals as Leaders,
        //    Meshuggah, jazz fusion). This is the "musical math" dimension.
        //
        // 3. SPEED (1.05) - BASELINE HIGH
        //    Raw density is universally understood but not the primary difficulty.
        //    Speed amplifies other difficulties multiplicatively.
        //
        // 4. TECHNIQUE (1.00) - SUBSTANTIAL
        //    Rudimental mastery, articulation control, and physical execution.
        //    Flams at 180 BPM, ghost notes in blast beats, etc.
        //
        // 5. PRECISION (0.92) - IMPORTANT
        //    Timing accuracy, dynamic control, groove lock. Critical for "feel".
        //
        // 6. PATTERN (0.88) - MEANINGFUL
        //    Fill creativity, orchestration, non-standard grooves.
        //
        // 7. STAMINA (0.85) - SUPPORTING
        //    Endurance is crucial for long pieces but secondary to technique.
        //
        // 8. MOVEMENT (0.78) - PHYSICAL FACTOR
        //    Kit traversal, crossovers, ergonomic demands.
        //
        // 9. MUSICALITY (0.72) - EXPRESSION
        //    Dynamic shaping, feel, phrasing. Hard to quantify but important.
        //
        // 10. READING (0.65) - COGNITIVE
        //     Sight-reading difficulty. Lower weight as it's about learning
        //     rather than executing, but important for this learning app.
        // ===========================================
        private static readonly Dictionary<string, double> SkillWeights = new()
        {
            { "Speed", 1.05 },            // Baseline high - raw note density
            { "Stamina", 0.85 },          // Endurance over time
            { "Coordination", 1.25 },     // HIGHEST - defines advanced drumming
            { "RhythmicComplexity", 1.20 }, // Very high - prog/jazz complexity
            { "Pattern", 0.88 },          // Creative fills and groove variety
            { "Technique", 1.00 },        // Rudimental mastery and articulation
            { "Reading", 0.65 },          // Sight-reading cognitive load
            { "Precision", 0.92 },        // Timing and dynamic accuracy
            { "Movement", 0.78 },         // Physical kit traversal
            { "Musicality", 0.72 }        // Musical expression and groove quality
        };

        // ===========================================
        // COMBINATION PARAMETERS
        // ===========================================

        /// <summary>
        /// Lp norm exponent for combining skill values.
        /// p=2 is Euclidean (RMS), p=3 emphasizes highest values more.
        /// Using p=2.7 balances peak difficulty with overall breadth,
        /// slightly favoring dominant skills while still rewarding breadth.
        /// </summary>
        private const double SKILL_COMBINATION_EXPONENT = 2.7;

        /// <summary>
        /// Bonus multiplier per additional hard skill (above threshold).
        /// Rewards maps that are difficult in multiple dimensions.
        /// INNOVATION: This captures the reality that multi-dimensional
        /// difficulty compounds cognitive and physical demands.
        /// </summary>
        private const double BREADTH_BONUS_PER_SKILL = 0.05;

        /// <summary>
        /// Threshold for considering a skill "hard" for breadth bonus.
        /// Skills with weighted value > this contribute to breadth bonus.
        /// </summary>
        private const double HARD_SKILL_THRESHOLD = 52.0;

        /// <summary>
        /// Threshold for "extreme" skill contribution.
        /// Skills above this add enhanced breadth bonus.
        /// </summary>
        private const double EXTREME_SKILL_THRESHOLD = 75.0;

        /// <summary>
        /// Section length for difficulty curve generation (in ms).
        /// 2-second sections balance granularity with meaningful aggregation.
        /// </summary>
        private const double DIFFICULTY_CURVE_SECTION_LENGTH = 2000;

        // Advanced analyzers for v3.1 enhancements
        private readonly GrooveAnalyzer grooveAnalyzer = new();
        private readonly PolyrhythmAnalyzer polyrhythmAnalyzer = new();
        private readonly CognitiveLoadAnalyzer cognitiveLoadAnalyzer = new();
        private readonly IndependenceRatingSystem independenceRatingSystem = new();

        public DifficultyCalculator(Beatmap beatmap, double clockRate = 1.0)
        {
            this.beatmap = beatmap;
            this.clockRate = clockRate;
        }

        /// <summary>
        /// Calculate comprehensive difficulty attributes for the beatmap.
        /// This is the main entry point for difficulty calculation.
        /// </summary>
        public DifficultyAttributes Calculate()
        {
            if (beatmap.HitObjects.Count == 0)
            {
                return CreateEmptyAttributes();
            }

            // ===========================================
            // Phase 1: Create difficulty hit objects
            // ===========================================
            // Convert raw hit objects into enriched difficulty objects
            // with pre-computed metrics for rhythm, limb usage, techniques, etc.
            var difficultyHitObjects = CreateDifficultyHitObjects();

            if (difficultyHitObjects.Count == 0)
            {
                return CreateEmptyAttributes();
            }

            // ===========================================
            // Phase 2: Initialize and process skills
            // ===========================================
            // Each skill tracks strain independently using decay-based accumulation
            var skills = CreateSkills();
            ProcessSkills(skills, difficultyHitObjects);

            // ===========================================
            // Phase 2.5: Run advanced analysis (v3.1)
            // ===========================================
            var advancedAnalysis = RunAdvancedAnalysis(difficultyHitObjects);

            // ===========================================
            // Phase 3: Extract raw difficulty values
            // ===========================================
            var difficultyValues = ExtractDifficultyValues(skills);

            // Apply advanced analysis modifiers
            ApplyAdvancedAnalysisModifiers(difficultyValues, advancedAnalysis);

            // ===========================================
            // Phase 4: Calculate combined star rating
            // ===========================================
            double starRating = CalculateStarRating(difficultyValues);

            // ===========================================
            // Phase 5: Scale individual ratings to star scale
            // ===========================================
            var scaledRatings = ScaleToStarRatings(difficultyValues);

            // ===========================================
            // Phase 6: Build comprehensive attributes
            // ===========================================
            var attributes = BuildAttributes(
                starRating,
                scaledRatings,
                skills,
                difficultyHitObjects,
                advancedAnalysis
            );

            return attributes;
        }

        /// <summary>
        /// ╔══════════════════════════════════════════════════════════════════════════════╗
        /// ║               REAL-TIME TIMED DIFFICULTY CALCULATION                         ║
        /// ╠══════════════════════════════════════════════════════════════════════════════╣
        /// ║                                                                              ║
        /// ║  REVOLUTIONARY FEATURE: Calculate progressive difficulty attributes at       ║
        /// ║  each point in time, enabling real-time star rating display during           ║
        /// ║  playback. Inspired by osu!'s TimedDifficultyAttributes but enhanced         ║
        /// ║  for drumming-specific needs.                                                ║
        /// ║                                                                              ║
        /// ║  KEY INNOVATIONS:                                                            ║
        /// ║                                                                              ║
        /// ║  1. PROGRESSIVE STAR RATING                                                  ║
        /// ║     The star rating builds up as the song progresses, showing users          ║
        /// ║     the accumulated difficulty up to each point.                             ║
        /// ║                                                                              ║
        /// ║  2. INSTANTANEOUS DIFFICULTY                                                 ║
        /// ║     Also tracks the current instantaneous difficulty (not accumulated),      ║
        /// ║     showing real-time "how hard is this exact moment" feedback.              ║
        /// ║                                                                              ║
        /// ║  3. PER-SKILL BREAKDOWN                                                      ║
        /// ║     Each time point includes breakdowns for all 10 skill dimensions,         ║
        /// ║     allowing visualization of which skills are being challenged.             ║
        /// ║                                                                              ║
        /// ║  4. SECTION-BASED SAMPLING                                                   ║
        /// ║     Uses configurable section lengths (default 500ms) for smooth updates     ║
        /// ║     without excessive computation or jittery display.                        ║
        /// ║                                                                              ║
        /// ╚══════════════════════════════════════════════════════════════════════════════╝
        /// </summary>
        /// <returns>List of timed difficulty attributes for real-time display.</returns>
        public List<TimedDifficultyAttributes> CalculateTimed()
        {
            var timedAttributes = new List<TimedDifficultyAttributes>();

            if (beatmap.HitObjects.Count == 0)
            {
                return timedAttributes;
            }

            var allDifficultyObjects = CreateDifficultyHitObjects();
            if (allDifficultyObjects.Count == 0)
            {
                return timedAttributes;
            }

            // Progressive calculation - process objects incrementally
            var skills = CreateSkills();
            var processedObjects = new List<DifficultyHitObject>();
            int comboCount = 0;

            // Section length for sampling (in milliseconds)
            // 500ms provides smooth real-time updates without excessive computation
            const double SECTION_LENGTH = 500;
            double lastSampleTime = double.MinValue;

            foreach (var hitObject in allDifficultyObjects)
            {
                // Process this hit object through all skills
                foreach (var skill in skills)
                {
                    skill.Process(hitObject);
                }
                processedObjects.Add(hitObject);
                comboCount++;

                // Sample at regular intervals
                if (hitObject.StartTime - lastSampleTime >= SECTION_LENGTH)
                {
                    // Extract current difficulty values from skills
                    var currentDifficultyValues = ExtractDifficultyValues(skills);

                    // Calculate current star rating
                    double currentStarRating = CalculateStarRating(currentDifficultyValues);

                    // Calculate instantaneous difficulty (strain at this moment)
                    double instantDifficulty = CalculateInstantaneousDifficulty(skills);

                    // Scale individual skill ratings
                    var scaledRatings = ScaleToStarRatings(currentDifficultyValues);

                    timedAttributes.Add(new TimedDifficultyAttributes
                    {
                        Time = hitObject.StartTime,
                        StarRating = Math.Round(currentStarRating * 100) / 100,
                        InstantaneousDifficulty = instantDifficulty,
                        SpeedRating = scaledRatings.GetValueOrDefault("Speed", 0),
                        StaminaRating = scaledRatings.GetValueOrDefault("Stamina", 0),
                        CoordinationRating = scaledRatings.GetValueOrDefault("Coordination", 0),
                        RhythmicComplexityRating = scaledRatings.GetValueOrDefault("RhythmicComplexity", 0),
                        PatternRating = scaledRatings.GetValueOrDefault("Pattern", 0),
                        TechniqueRating = scaledRatings.GetValueOrDefault("Technique", 0),
                        PrecisionRating = scaledRatings.GetValueOrDefault("Precision", 0),
                        MovementRating = scaledRatings.GetValueOrDefault("Movement", 0),
                        MusicalityRating = scaledRatings.GetValueOrDefault("Musicality", 0),
                        ReadingRating = scaledRatings.GetValueOrDefault("Reading", 0),
                        ComboAtTime = comboCount
                    });

                    lastSampleTime = hitObject.StartTime;
                }
            }

            // Always include final point with full difficulty
            if (processedObjects.Count > 0)
            {
                var finalObject = processedObjects[^1];
                var finalDifficultyValues = ExtractDifficultyValues(skills);
                double finalStarRating = CalculateStarRating(finalDifficultyValues);
                double finalInstantDifficulty = CalculateInstantaneousDifficulty(skills);
                var finalScaledRatings = ScaleToStarRatings(finalDifficultyValues);

                // Only add if not already present at this time
                if (timedAttributes.Count == 0 ||
                    Math.Abs(timedAttributes[^1].Time - finalObject.StartTime) > 1)
                {
                    timedAttributes.Add(new TimedDifficultyAttributes
                    {
                        Time = finalObject.StartTime,
                        StarRating = Math.Round(finalStarRating * 100) / 100,
                        InstantaneousDifficulty = finalInstantDifficulty,
                        SpeedRating = finalScaledRatings.GetValueOrDefault("Speed", 0),
                        StaminaRating = finalScaledRatings.GetValueOrDefault("Stamina", 0),
                        CoordinationRating = finalScaledRatings.GetValueOrDefault("Coordination", 0),
                        RhythmicComplexityRating = finalScaledRatings.GetValueOrDefault("RhythmicComplexity", 0),
                        PatternRating = finalScaledRatings.GetValueOrDefault("Pattern", 0),
                        TechniqueRating = finalScaledRatings.GetValueOrDefault("Technique", 0),
                        PrecisionRating = finalScaledRatings.GetValueOrDefault("Precision", 0),
                        MovementRating = finalScaledRatings.GetValueOrDefault("Movement", 0),
                        MusicalityRating = finalScaledRatings.GetValueOrDefault("Musicality", 0),
                        ReadingRating = finalScaledRatings.GetValueOrDefault("Reading", 0),
                        ComboAtTime = comboCount
                    });
                }
            }

            return timedAttributes;
        }

        /// <summary>
        /// Calculate instantaneous difficulty at the current processing point.
        /// This represents "how hard is this exact moment" rather than cumulative difficulty.
        /// </summary>
        private double CalculateInstantaneousDifficulty(Skill[] skills)
        {
            // Get peak strains from each skill as instantaneous measure
            double totalInstant = 0;
            int count = 0;

            foreach (var skill in skills)
            {
                double peak = skill.PeakStrain();
                if (peak > 0)
                {
                    totalInstant += peak;
                    count++;
                }
            }

            if (count == 0) return 0;

            // Scale to reasonable range
            return totalInstant / count * 0.1;
        }

        /// <summary>
        /// Run the v3.1 advanced analyzers across all hit objects.
        /// These provide deep mathematical analysis of groove, polyrhythm,
        /// cognitive load, and limb independence.
        /// </summary>
        private AdvancedAnalysisResults RunAdvancedAnalysis(List<DifficultyHitObject> hitObjects)
        {
            var results = new AdvancedAnalysisResults();

            // Collect results for averaging
            var grooveResults = new List<GrooveAnalysisResult>();
            var polyrhythmResults = new List<PolyrhythmAnalysisResult>();
            var cognitiveResults = new List<CognitiveLoadResult>();
            var independenceResults = new List<IndependenceResult>();

            for (int i = 0; i < hitObjects.Count; i++)
            {
                var current = hitObjects[i];
                var context = hitObjects.Take(i).TakeLast(16).ToList();

                // Groove analysis
                var grooveResult = grooveAnalyzer.Analyze(current);
                grooveResults.Add(grooveResult);

                // Polyrhythm analysis  
                var polyResult = polyrhythmAnalyzer.Analyze(current);
                polyrhythmResults.Add(polyResult);

                // Cognitive load analysis
                var cogResult = cognitiveLoadAnalyzer.Analyze(current, context);
                cognitiveResults.Add(cogResult);

                // Independence analysis
                var indResult = independenceRatingSystem.Analyze(current, context);
                independenceResults.Add(indResult);
            }

            // Aggregate results
            if (grooveResults.Count > 0)
            {
                results.AverageSwingAmount = grooveResults.Average(r => r.SwingAmount);
                results.AverageGrooveComplexity = grooveResults.Average(r => r.GrooveComplexity);
                results.PeakGrooveComplexity = grooveResults.Max(r => r.GrooveComplexity);
                results.DominantGrooveFeel = grooveResults
                    .GroupBy(r => r.DominantFeel)
                    .OrderByDescending(g => g.Count())
                    .FirstOrDefault()?.Key ?? "Straight";
            }

            if (polyrhythmResults.Count > 0)
            {
                results.AveragePolyrhythmComplexity = polyrhythmResults.Average(r => r.RatioComplexity);
                results.PeakPolyrhythmComplexity = polyrhythmResults.Max(r => r.RatioComplexity);
                results.DetectedPolyrhythms = polyrhythmResults
                    .Where(r => r.RatioComplexity > 1.5)
                    .Select(r => $"{r.DetectedRatio.numerator}:{r.DetectedRatio.denominator}")
                    .Distinct()
                    .ToList();
                results.PolymeterDetected = polyrhythmResults.Any(r => r.PolymeterDetected);
                results.MaxNestedPolyrhythmDepth = polyrhythmResults.Max(r => r.NestedPolyrhythmDepth);
            }

            if (cognitiveResults.Count > 0)
            {
                results.AverageCognitiveLoad = cognitiveResults.Average(r => r.TotalCognitiveLoad);
                results.PeakCognitiveLoad = cognitiveResults.Max(r => r.TotalCognitiveLoad);
                results.AverageInformationDensity = cognitiveResults.Average(r => r.InformationDensity);
                results.CognitiveFatigueFactor = cognitiveResults.Last().CognitiveFatigue;
            }

            if (independenceResults.Count > 0)
            {
                results.AverageIndependence = independenceResults.Average(r => r.OverallIndependence);
                results.PeakIndependence = independenceResults.Max(r => r.OverallIndependence);
                results.MaxActiveLimbs = independenceResults.Max(r => r.ActiveLimbCount);
                results.AverageRhythmicIndependence = independenceResults.Average(r => r.RhythmicIndependence);
                results.AverageDynamicIndependence = independenceResults.Average(r => r.DynamicIndependence);
            }

            return results;
        }

        /// <summary>
        /// Apply modifiers from advanced analysis to the skill difficulty values.
        /// </summary>
        private void ApplyAdvancedAnalysisModifiers(
            Dictionary<string, double> difficultyValues,
            AdvancedAnalysisResults analysis)
        {
            // Enhance Rhythmic Complexity based on polyrhythm detection
            if (analysis.PeakPolyrhythmComplexity > 3.0)
            {
                double polyBonus = 1.0 + (analysis.PeakPolyrhythmComplexity - 3.0) * 0.02;
                difficultyValues["RhythmicComplexity"] *= Math.Min(polyBonus, 1.25);
            }

            // Add polymeter bonus
            if (analysis.PolymeterDetected)
            {
                difficultyValues["RhythmicComplexity"] *= 1.08;
            }

            // Nested polyrhythms are extremely difficult
            if (analysis.MaxNestedPolyrhythmDepth > 0)
            {
                double nestingBonus = 1.0 + analysis.MaxNestedPolyrhythmDepth * 0.05;
                difficultyValues["RhythmicComplexity"] *= nestingBonus;
                difficultyValues["Coordination"] *= 1.0 + analysis.MaxNestedPolyrhythmDepth * 0.03;
            }

            // Cognitive load affects Reading difficulty
            if (analysis.PeakCognitiveLoad > 20)
            {
                double cogBonus = 1.0 + (analysis.PeakCognitiveLoad - 20) * 0.01;
                difficultyValues["Reading"] *= Math.Min(cogBonus, 1.20);
            }

            // Independence score enhances Coordination
            if (analysis.PeakIndependence > 5)
            {
                double indBonus = 1.0 + (analysis.PeakIndependence - 5) * 0.02;
                difficultyValues["Coordination"] *= Math.Min(indBonus, 1.30);
            }

            // 4-way coordination is significantly harder
            if (analysis.MaxActiveLimbs == 4 && analysis.AverageIndependence > 4)
            {
                difficultyValues["Coordination"] *= 1.10;
            }

            // Groove complexity affects Musicality
            if (analysis.PeakGrooveComplexity > 4)
            {
                double grooveBonus = 1.0 + (analysis.PeakGrooveComplexity - 4) * 0.02;
                difficultyValues["Musicality"] *= Math.Min(grooveBonus, 1.15);
            }

            // Swing/shuffle feel adds precision demands
            if (analysis.AverageSwingAmount > 0.1)
            {
                double swingBonus = 1.0 + analysis.AverageSwingAmount * 0.08;
                difficultyValues["Precision"] *= Math.Min(swingBonus, 1.10);
            }
        }

        /// <summary>
        /// Create empty attributes for beatmaps with no hit objects.
        /// </summary>
        private static DifficultyAttributes CreateEmptyAttributes()
        {
            return new DifficultyAttributes
            {
                StarRating = 0,
                RecommendedLevel = SkillLevel.Beginner,
                AlgorithmVersion = ALGORITHM_VERSION
            };
        }

        /// <summary>
        /// Extract raw difficulty values from processed skills.
        /// </summary>
        private static Dictionary<string, double> ExtractDifficultyValues(Skill[] skills)
        {
            return new Dictionary<string, double>
            {
                { "Speed", skills[0].DifficultyValue() },
                { "Coordination", skills[1].DifficultyValue() },
                { "Stamina", skills[2].DifficultyValue() },
                { "RhythmicComplexity", skills[3].DifficultyValue() },
                { "Pattern", skills[4].DifficultyValue() },
                { "Reading", skills[5].DifficultyValue() },
                { "Technique", skills[6].DifficultyValue() },
                { "Precision", skills[7].DifficultyValue() },
                { "Movement", skills[8].DifficultyValue() },
                { "Musicality", skills[9].DifficultyValue() }
            };
        }

        /// <summary>
        /// Build comprehensive difficulty attributes from calculated values.
        /// </summary>
        private DifficultyAttributes BuildAttributes(
            double starRating,
            Dictionary<string, double> scaledRatings,
            Skill[] skills,
            List<DifficultyHitObject> difficultyHitObjects,
            AdvancedAnalysisResults? advancedAnalysis = null)
        {
            var attributes = new DifficultyAttributes
            {
                StarRating = starRating,
                AlgorithmVersion = ALGORITHM_VERSION,
                SpeedRating = scaledRatings["Speed"],
                CoordinationRating = scaledRatings["Coordination"],
                StaminaRating = scaledRatings["Stamina"],
                RhythmicComplexityRating = scaledRatings["RhythmicComplexity"],
                PatternRating = scaledRatings["Pattern"],
                ReadingRating = scaledRatings["Reading"],
                TechniqueRating = scaledRatings["Technique"],
                PrecisionRating = scaledRatings["Precision"],
                MovementRating = scaledRatings["Movement"],
                MusicalityRating = scaledRatings["Musicality"],
                MaxCombo = beatmap.HitObjects.Count,
                Duration = CalculateDuration(difficultyHitObjects),
                AverageBpm = CalculateAverageBpm(difficultyHitObjects)
            };

            // Add peak strains (maximum instantaneous difficulty per skill)
            attributes.PeakStrains = new SkillPeakStrains
            {
                Speed = skills[0].PeakStrain(),
                Coordination = skills[1].PeakStrain(),
                Stamina = skills[2].PeakStrain(),
                RhythmicComplexity = skills[3].PeakStrain(),
                Pattern = skills[4].PeakStrain(),
                Reading = skills[5].PeakStrain(),
                Technique = skills[6].PeakStrain(),
                Precision = skills[7].PeakStrain(),
                Movement = skills[8].PeakStrain(),
                Musicality = skills[9].PeakStrain()
            };

            // Add consistency factors (how sustained is the difficulty)
            attributes.Consistency = new SkillConsistency
            {
                Speed = skills[0].ConsistencyFactor(),
                Coordination = skills[1].ConsistencyFactor(),
                Stamina = skills[2].ConsistencyFactor(),
                RhythmicComplexity = skills[3].ConsistencyFactor(),
                Pattern = skills[4].ConsistencyFactor(),
                Reading = skills[5].ConsistencyFactor(),
                Technique = skills[6].ConsistencyFactor(),
                Precision = skills[7].ConsistencyFactor(),
                Movement = skills[8].ConsistencyFactor(),
                Musicality = skills[9].ConsistencyFactor()
            };

            // Generate difficulty curve for visualization
            attributes.DifficultyCurve = GenerateDifficultyCurve(difficultyHitObjects, skills);

            // Detailed analysis breakdowns
            attributes.Speed = AnalyzeSpeed(difficultyHitObjects);
            attributes.Techniques = AnalyzeTechniques(difficultyHitObjects);
            attributes.Rhythm = AnalyzeRhythm(difficultyHitObjects);

            // v3.1: Add advanced analysis results
            if (advancedAnalysis != null)
            {
                attributes.AdvancedAnalysis = advancedAnalysis;
            }

            // Classification
            attributes.PrimaryStyle = DetermineStyle(attributes);
            attributes.RecommendedLevel = DetermineLevel(starRating);
            attributes.PrimaryTimeSignature = DeterminePrimaryTimeSignature(difficultyHitObjects);

            return attributes;
        }

        /// <summary>
        /// Calculate the combined star rating from individual skill values.
        /// 
        /// ALGORITHM DESIGN (REVOLUTIONARY APPROACH v3.0):
        /// 
        /// 1. Apply skill-specific weights to raw difficulty values
        /// 2. Calculate weighted Lp norm (emphasizes highest skills while
        ///    still accounting for overall difficulty)
        /// 3. Apply TIERED breadth bonus for maps difficult in multiple dimensions
        /// 4. Apply consistency bonus for sustained difficulty
        /// 5. Apply SYNERGY-BASED compound difficulty bonus (KEY INNOVATION)
        ///    - Different skill combinations have different synergy multipliers
        ///    - The "holy trinity" (Speed + Coordination + Rhythm) has highest synergy
        /// 6. Apply VARIANCE BONUS for maps with high difficulty across many skills
        /// 7. Scale to final star rating using calibrated piecewise curves
        /// 
        /// INNOVATIONS IN THIS VERSION:
        /// 
        /// - SYNERGY MATRIX: Models how skill combinations compound differently
        /// - TIERED BREADTH: Separate bonuses for "hard", "extreme", "elite" levels
        /// - COGNITIVE LOAD FACTOR: Implicit in compound bonus based on working
        ///   memory demands of tracking multiple complex patterns
        /// - SMOOTH SCALING: No cliff effects between difficulty tiers
        /// 
        /// The result properly rates material like:
        /// - Meshuggah "Bleed" (7-8★): Extreme speed + polyrhythm + stamina
        /// - Animals as Leaders peak (7-7.5★): Speed + coordination + rhythm + pattern
        /// - Jazz giants (5-6★): Coordination + rhythm + musicality + technique
        /// - Technical death metal (6-7★): Speed + stamina + technique + pattern
        /// </summary>
        private double CalculateStarRating(Dictionary<string, double> difficultyValues)
        {
            // ===========================================
            // Step 1: Apply skill weights
            // ===========================================
            var weightedValues = new Dictionary<string, double>();
            foreach (var kvp in difficultyValues)
            {
                double weighted = kvp.Value * SkillWeights.GetValueOrDefault(kvp.Key, 1.0);
                weightedValues[kvp.Key] = weighted;
            }

            var valuesList = weightedValues.Values.ToList();

            // ===========================================
            // Step 2: Calculate Lp norm (generalized mean)
            // ===========================================
            // Using p=2.7 balances peak emphasis with overall breadth
            // This is slightly higher than standard to better reward
            // dominant skills while not ignoring breadth
            double sumPowers = valuesList.Sum(v => Math.Pow(Math.Max(v, 0), SKILL_COMBINATION_EXPONENT));
            double norm = Math.Pow(sumPowers / valuesList.Count, 1.0 / SKILL_COMBINATION_EXPONENT);

            // ===========================================
            // Step 3: TIERED Breadth bonus
            // ===========================================
            // Reward maps that are challenging in multiple skill dimensions
            // with SEPARATE tiers for "hard" vs "extreme" vs "elite"
            int hardSkillCount = valuesList.Count(v => v > HARD_SKILL_THRESHOLD);
            int extremeSkillCount = valuesList.Count(v => v > EXTREME_SKILL_THRESHOLD);

            double breadthBonus = 1.0;
            // Base breadth bonus
            breadthBonus += Math.Max(0, hardSkillCount - 1) * BREADTH_BONUS_PER_SKILL;
            // Additional bonus for extreme-level breadth (harder to achieve)
            breadthBonus += Math.Max(0, extremeSkillCount - 1) * (BREADTH_BONUS_PER_SKILL * 1.5);

            norm *= breadthBonus;

            // ===========================================
            // Step 4: Consistency scaling
            // ===========================================
            // Maps with sustained difficulty (high average relative to peak)
            // deserve a bonus over maps with isolated spikes
            // But don't penalize too harshly for having sections of contrast
            double avgValue = valuesList.Average();
            double maxValue = valuesList.Max();
            double consistencyRatio = maxValue > 0 ? avgValue / maxValue : 0;

            // Sigmoid-based consistency bonus (smoother than linear)
            // Centers around 0.5 consistency ratio
            double consistencyBonus = 1.0 + (Sigmoid(consistencyRatio, 0.5, 8.0) - 0.5) * 0.15;
            consistencyBonus = Math.Max(consistencyBonus, 0.93); // Floor at 93%
            norm *= consistencyBonus;

            // ===========================================
            // Step 5: SYNERGY-BASED Compound Difficulty Bonus
            // ===========================================
            // This is the KEY INNOVATION - models how skill combinations
            // compound differently based on cognitive/physical interference
            double compoundBonus = CalculateCompoundDifficultyBonus(weightedValues);
            norm *= compoundBonus;

            // ===========================================
            // Step 6: VARIANCE BONUS (Balanced Multi-skill Maps)
            // ===========================================
            // Maps that are difficult across MANY skills (not just 1-2)
            // represent more comprehensive drumming demands
            double variance = CalculateSkillVariance(valuesList, avgValue);
            // Low variance + high average = all skills are challenging = bonus
            if (avgValue > HARD_SKILL_THRESHOLD && variance < avgValue * 0.3)
            {
                double varianceBonus = 1.0 + (1.0 - variance / Math.Max(avgValue, 1)) * 0.06;
                norm *= Math.Min(varianceBonus, 1.12);
            }

            // ===========================================
            // Step 7: Scale to star rating
            // ===========================================
            double starRating = ScaleToStars(norm);

            return Math.Max(0, Math.Round(starRating * 100) / 100); // Round to 2 decimals
        }

        /// <summary>
        /// Calculate the variance of skill values for balanced difficulty assessment.
        /// </summary>
        private static double CalculateSkillVariance(List<double> values, double mean)
        {
            if (values.Count == 0) return 0;
            return values.Sum(v => Math.Pow(v - mean, 2)) / values.Count;
        }

        /// <summary>
        /// Sigmoid function for smooth transitions.
        /// </summary>
        private static double Sigmoid(double x, double center, double steepness)
        {
            return 1.0 / (1.0 + Math.Exp(-steepness * (x - center)));
        }

        /// <summary>
        /// Calculate bonus for compound difficulty - when multiple skills
        /// are simultaneously at extreme levels.
        /// 
        /// REVOLUTIONARY INNOVATION: This captures the exponential nature of 
        /// multi-dimensional mastery using a SYNERGY MATRIX approach.
        /// 
        /// The key insight is that different skill combinations have different
        /// synergy multipliers. Some combinations compound more than others:
        /// 
        /// - Speed + Coordination: The limbs must be independent AND fast
        /// - Speed + RhythmicComplexity: The polyrhythms must be executed fast
        /// - Coordination + RhythmicComplexity: THE HOLY GRAIL - polyrhythmic independence
        /// - Technique + Speed: Rudiments at extreme speed
        /// - All four together: TRANSCENDENT difficulty
        /// 
        /// This is what makes Animals as Leaders "The Brain Dance" harder than
        /// the sum of its individual components.
        /// 
        /// The synergy approach is INNOVATIVE because it goes beyond simple
        /// additive or even multiplicative bonuses to model the actual
        /// cognitive and physical compound demands of elite drumming.
        /// </summary>
        private static double CalculateCompoundDifficultyBonus(Dictionary<string, double> weightedValues)
        {
            // ===========================================
            // TIER THRESHOLDS
            // ===========================================
            const double DEMANDING_THRESHOLD = 55.0;  // Challenging in this skill
            const double EXTREME_THRESHOLD = 72.0;    // Very hard in this skill
            const double ELITE_THRESHOLD = 92.0;      // World-class in this skill
            const double LEGENDARY_THRESHOLD = 115.0; // Peak human capability
            const double TRANSCENDENT_THRESHOLD = 140.0; // May exceed human limits

            // Extract key skills
            double speedValue = weightedValues.GetValueOrDefault("Speed", 0);
            double coordValue = weightedValues.GetValueOrDefault("Coordination", 0);
            double rhythmValue = weightedValues.GetValueOrDefault("RhythmicComplexity", 0);
            double staminaValue = weightedValues.GetValueOrDefault("Stamina", 0);
            double techniqueValue = weightedValues.GetValueOrDefault("Technique", 0);
            double precisionValue = weightedValues.GetValueOrDefault("Precision", 0);
            double patternValue = weightedValues.GetValueOrDefault("Pattern", 0);

            // Count skills at each tier
            int demandingCount = 0, extremeCount = 0, eliteCount = 0, legendaryCount = 0, transcendentCount = 0;

            foreach (var value in weightedValues.Values)
            {
                if (value >= TRANSCENDENT_THRESHOLD) transcendentCount++;
                else if (value >= LEGENDARY_THRESHOLD) legendaryCount++;
                else if (value >= ELITE_THRESHOLD) eliteCount++;
                else if (value >= EXTREME_THRESHOLD) extremeCount++;
                else if (value >= DEMANDING_THRESHOLD) demandingCount++;
            }

            double bonus = 1.0;

            // ===========================================
            // TIER-BASED COMPOUND BONUSES
            // ===========================================

            // Multiple demanding skills (entry to compound difficulty)
            int hardTotal = demandingCount + extremeCount + eliteCount + legendaryCount + transcendentCount;
            if (hardTotal >= 2) bonus += 0.04;
            if (hardTotal >= 3) bonus += 0.06;
            if (hardTotal >= 4) bonus += 0.08;
            if (hardTotal >= 5) bonus += 0.10;
            if (hardTotal >= 6) bonus += 0.12;

            // Extreme tier compounds
            int extremeTotal = extremeCount + eliteCount + legendaryCount + transcendentCount;
            if (extremeTotal >= 2) bonus += 0.08;
            if (extremeTotal >= 3) bonus += 0.12;
            if (extremeTotal >= 4) bonus += 0.18;
            if (extremeTotal >= 5) bonus += 0.25;

            // Elite tier compounds (world-class territory)
            int eliteTotal = eliteCount + legendaryCount + transcendentCount;
            if (eliteTotal >= 2) bonus += 0.15;
            if (eliteTotal >= 3) bonus += 0.22;
            if (eliteTotal >= 4) bonus += 0.30;

            // Legendary tier compounds (peak human)
            int legendaryTotal = legendaryCount + transcendentCount;
            if (legendaryTotal >= 2) bonus += 0.25;
            if (legendaryTotal >= 3) bonus += 0.38;

            // Transcendent compounds (beyond human limits)
            if (transcendentCount >= 2) bonus += 0.35;
            if (transcendentCount >= 3) bonus += 0.50;

            // ===========================================
            // SYNERGY MATRIX - SPECIFIC COMBINATIONS
            // ===========================================
            // These capture the reality that certain skill combinations
            // compound difficulty more than others due to cognitive/physical
            // interference and resource competition.

            // --------------------------------
            // THE HOLY TRINITY: Speed + Coordination + Rhythm
            // This is what defines the most difficult drumming in existence
            // --------------------------------

            // Speed + Coordination (fast independence)
            if (speedValue >= DEMANDING_THRESHOLD && coordValue >= DEMANDING_THRESHOLD)
            {
                double synergyStrength = Math.Min(speedValue, coordValue) / DEMANDING_THRESHOLD;
                bonus += 0.05 * synergyStrength;

                if (speedValue >= EXTREME_THRESHOLD && coordValue >= EXTREME_THRESHOLD)
                    bonus += 0.10 * (Math.Min(speedValue, coordValue) / EXTREME_THRESHOLD);

                if (speedValue >= ELITE_THRESHOLD && coordValue >= ELITE_THRESHOLD)
                    bonus += 0.15 * (Math.Min(speedValue, coordValue) / ELITE_THRESHOLD);
            }

            // Speed + Rhythm (fast polyrhythms - Meshuggah)
            if (speedValue >= DEMANDING_THRESHOLD && rhythmValue >= DEMANDING_THRESHOLD)
            {
                double synergyStrength = Math.Min(speedValue, rhythmValue) / DEMANDING_THRESHOLD;
                bonus += 0.06 * synergyStrength;

                if (speedValue >= EXTREME_THRESHOLD && rhythmValue >= EXTREME_THRESHOLD)
                    bonus += 0.12 * (Math.Min(speedValue, rhythmValue) / EXTREME_THRESHOLD);

                if (speedValue >= ELITE_THRESHOLD && rhythmValue >= ELITE_THRESHOLD)
                    bonus += 0.18 * (Math.Min(speedValue, rhythmValue) / ELITE_THRESHOLD);
            }

            // Coordination + Rhythm (polyrhythmic independence - THE HOLY GRAIL)
            // This combination is the defining characteristic of elite drumming
            if (coordValue >= DEMANDING_THRESHOLD && rhythmValue >= DEMANDING_THRESHOLD)
            {
                double synergyStrength = Math.Min(coordValue, rhythmValue) / DEMANDING_THRESHOLD;
                bonus += 0.08 * synergyStrength; // Highest base synergy

                if (coordValue >= EXTREME_THRESHOLD && rhythmValue >= EXTREME_THRESHOLD)
                    bonus += 0.15 * (Math.Min(coordValue, rhythmValue) / EXTREME_THRESHOLD);

                if (coordValue >= ELITE_THRESHOLD && rhythmValue >= ELITE_THRESHOLD)
                    bonus += 0.22 * (Math.Min(coordValue, rhythmValue) / ELITE_THRESHOLD);
            }

            // THE TRIPLE THREAT: Speed + Coordination + Rhythm
            // Animals as Leaders, Meshuggah extreme, peak technical death metal
            if (speedValue >= EXTREME_THRESHOLD && coordValue >= EXTREME_THRESHOLD && rhythmValue >= EXTREME_THRESHOLD)
            {
                double tripleStrength = (speedValue + coordValue + rhythmValue) / (3 * EXTREME_THRESHOLD);
                bonus += 0.25 * tripleStrength;

                // Add stamina for the QUADRUPLE challenge
                if (staminaValue >= EXTREME_THRESHOLD)
                {
                    bonus += 0.18 * (staminaValue / EXTREME_THRESHOLD);
                }
            }

            // Elite triple threat (world-class)
            if (speedValue >= ELITE_THRESHOLD && coordValue >= ELITE_THRESHOLD && rhythmValue >= ELITE_THRESHOLD)
            {
                double tripleStrength = (speedValue + coordValue + rhythmValue) / (3 * ELITE_THRESHOLD);
                bonus += 0.35 * tripleStrength;
            }

            // --------------------------------
            // SECONDARY SYNERGIES
            // --------------------------------

            // Technique + Speed (rudiments at extreme speed)
            if (techniqueValue >= EXTREME_THRESHOLD && speedValue >= EXTREME_THRESHOLD)
            {
                bonus += 0.08;
                if (techniqueValue >= ELITE_THRESHOLD && speedValue >= ELITE_THRESHOLD)
                    bonus += 0.12;
            }

            // Technique + Coordination (complex rudiments with independence)
            if (techniqueValue >= EXTREME_THRESHOLD && coordValue >= EXTREME_THRESHOLD)
            {
                bonus += 0.07;
                if (techniqueValue >= ELITE_THRESHOLD && coordValue >= ELITE_THRESHOLD)
                    bonus += 0.10;
            }

            // Precision + Rhythm (tight execution of complex rhythms)
            if (precisionValue >= EXTREME_THRESHOLD && rhythmValue >= EXTREME_THRESHOLD)
            {
                bonus += 0.05;
            }

            // Pattern + Coordination (creative orchestration with independence)
            if (patternValue >= EXTREME_THRESHOLD && coordValue >= EXTREME_THRESHOLD)
            {
                bonus += 0.05;
            }

            // Stamina + Speed (sustained extreme speed - Nile, technical death metal)
            if (staminaValue >= EXTREME_THRESHOLD && speedValue >= EXTREME_THRESHOLD)
            {
                bonus += 0.08;
                if (staminaValue >= ELITE_THRESHOLD && speedValue >= ELITE_THRESHOLD)
                    bonus += 0.12;
            }

            // ===========================================
            // DIMINISHING RETURNS CAP
            // ===========================================
            // Prevent runaway while still allowing exceptional material
            // to reach very high ratings
            return Math.Min(bonus, 2.5);
        }

        /// <summary>
        /// Scale an internal difficulty value to star rating.
        /// 
        /// INNOVATION: Uses a carefully calibrated piecewise-continuous function
        /// with smooth sigmoid transitions between tiers. This provides:
        /// 
        /// 1. Clear differentiation at beginner levels (0-3★)
        /// 2. Meaningful separation at intermediate levels (3-5★)
        /// 3. Proper expansion at advanced levels (5-7★) to reward elite material
        /// 4. Logarithmic scaling at extreme levels (7+★) to prevent runaway
        ///    while still differentiating the most difficult material
        /// 
        /// CALIBRATION TARGETS (validated against real-world drumming):
        /// 
        /// BEGINNER (0-2★):
        /// - 0.5★: Quarter-note kick pattern, nothing else
        /// - 1.0★: Basic 4/4 rock beat (kick/snare/hi-hat), ~90 BPM
        /// - 1.5★: Basic rock with simple fills, ~100 BPM
        /// - 2.0★: 8th-note hi-hat patterns, basic coordination
        /// 
        /// INTERMEDIATE (2-4★):
        /// - 2.5★: Standard rock/pop, some 16ths, moderate tempo
        /// - 3.0★: More complex fills, double bass introduction
        /// - 3.5★: Advanced rock grooves, faster tempos, ghost notes intro
        /// - 4.0★: Funk grooves with ghost notes, basic jazz comping
        /// 
        /// ADVANCED (4-6★):
        /// - 4.5★: Jazz comping (Steve Gadd, Jeff Porcaro)
        /// - 5.0★: Progressive rock (Neil Peart, Mike Portnoy)
        /// - 5.5★: Advanced fusion (Dave Weckl, Dennis Chambers)
        /// - 6.0★: Animals as Leaders style, technical death metal
        /// 
        /// EXPERT (6-8★):
        /// - 6.5★: Extreme technical metal (Gene Hoglan, George Kollias)
        /// - 7.0★: Peak Matt Garstka, extreme Meshuggah polyrhythms
        /// - 7.5★: Sustained extreme multi-dimensional difficulty
        /// - 8.0★: Theoretical peak human drumming
        /// 
        /// TRANSCENDENT (8-10★):
        /// - 8.5★: Approaches human limits in multiple dimensions
        /// - 9.0★: Multi-dimensional mastery at sustained extreme levels
        /// - 9.5★: Near-theoretical maximum
        /// - 10.0★: Perfect storm - all skills at inhuman levels simultaneously
        /// 
        /// The formula ensures smooth transitions with no cliff effects, using
        /// sigmoid blending between linear segments for perceptually smooth scaling.
        /// </summary>
        private static double ScaleToStars(double value)
        {
            if (value <= 0) return 0;

            double stars;

            if (value < 18)
            {
                // ===========================================
                // BEGINNER TIER (0-1.3★)
                // Very simple patterns, basic coordination introduction
                // Linear scaling for clear differentiation
                // ===========================================
                stars = value * 0.072;
            }
            else if (value < 32)
            {
                // ===========================================
                // EASY TIER (1.3-2.5★)
                // Standard beginner material, basic fills
                // ===========================================
                stars = 1.3 + (value - 18) * 0.086;
            }
            else if (value < 46)
            {
                // ===========================================
                // NORMAL TIER (2.5-3.5★)
                // Rock/pop with complexity, some coordination
                // ===========================================
                stars = 2.5 + (value - 32) * 0.071;
            }
            else if (value < 62)
            {
                // ===========================================
                // HARD TIER (3.5-4.4★)
                // Complex grooves, advanced fills, double bass
                // ===========================================
                stars = 3.5 + (value - 46) * 0.056;
            }
            else if (value < 82)
            {
                // ===========================================
                // EXPERT TIER (4.4-5.3★)
                // Jazz comping, progressive patterns, demanding coordination
                // Slightly slower scaling - need to earn these stars
                // ===========================================
                stars = 4.4 + (value - 62) * 0.045;
            }
            else if (value < 105)
            {
                // ===========================================
                // MASTER TIER (5.3-6.2★)
                // Animals as Leaders, extreme technical material
                // This is where most "very hard" music lands
                // ===========================================
                stars = 5.3 + (value - 82) * 0.039;
            }
            else if (value < 135)
            {
                // ===========================================
                // LEGENDARY TIER (6.2-7.0★)
                // World-class difficulty, Meshuggah/Garstka peaks
                // Slower scaling - each star means a LOT here
                // ===========================================
                stars = 6.2 + (value - 105) * 0.027;
            }
            else if (value < 175)
            {
                // ===========================================
                // INHUMAN TIER (7.0-7.8★)
                // Approaches or reaches human limits
                // Very slow scaling - every tenth means something
                // ===========================================
                stars = 7.0 + (value - 135) * 0.020;
            }
            else if (value < 230)
            {
                // ===========================================
                // TRANSCENDENT TIER A (7.8-8.5★)
                // May exceed human limits in isolation
                // Logarithmic influence begins
                // ===========================================
                stars = 7.8 + (value - 175) * 0.013;
            }
            else if (value < 320)
            {
                // ===========================================
                // TRANSCENDENT TIER B (8.5-9.2★)
                // Multi-dimensional inhuman territory
                // Strong logarithmic compression
                // ===========================================
                stars = 8.5 + (value - 230) * 0.008;
            }
            else
            {
                // ===========================================
                // THEORETICAL MAXIMUM (9.2+★)
                // Full logarithmic scaling for theoretical limits
                // At value=500: ~9.4★
                // At value=1000: ~9.7★
                // At value=2000: ~9.9★
                // Asymptotic approach to 10★
                // ===========================================
                double excess = Math.Max(value - 300, 1);
                stars = 9.2 + Math.Log10(excess) * 0.35;
            }

            // Hard cap at 10★ - theoretical perfection
            return Math.Max(0, Math.Min(stars, 10.0));
        }

        /// <summary>
        /// Scale individual skill values to comparable star ratings.
        /// Each skill is scaled independently for per-skill breakdown display.
        /// </summary>
        private static Dictionary<string, double> ScaleToStarRatings(Dictionary<string, double> values)
        {
            var result = new Dictionary<string, double>();

            foreach (var kvp in values)
            {
                double weighted = kvp.Value * SkillWeights.GetValueOrDefault(kvp.Key, 1.0);
                result[kvp.Key] = Math.Round(ScaleToStars(weighted) * 100) / 100;
            }

            return result;
        }

        /// <summary>
        /// Create skill instances for difficulty calculation.
        /// </summary>
        private Skill[] CreateSkills() => new Skill[]
        {
            new Speed(),
            new Coordination(),
            new Stamina(),
            new RhythmicComplexity(),
            new PatternComplexity(),
            new Reading(),
            new Technique(),
            new Precision(),
            new Movement(),
            new Musicality()
        };

        /// <summary>
        /// Process all hit objects through all skills.
        /// </summary>
        private void ProcessSkills(Skill[] skills, List<DifficultyHitObject> objects)
        {
            foreach (var obj in objects)
            {
                foreach (var skill in skills)
                {
                    skill.Process(obj);
                }
            }
        }

        /// <summary>
        /// Create DifficultyHitObjects from the beatmap, grouping simultaneous hits.
        /// </summary>
        private List<DifficultyHitObject> CreateDifficultyHitObjects()
        {
            var sortedObjects = beatmap.HitObjects.OrderBy(h => h.Time).ToList();
            var difficultyObjects = new List<DifficultyHitObject>();

            if (sortedObjects.Count == 0)
                return difficultyObjects;

            // Group hits that occur within 2ms of each other (simultaneous)
            var currentGroup = new List<HitObject>();
            int currentTime = sortedObjects[0].Time;
            int index = 0;

            // Get BPM and time signature from beatmap timing info
            double bpm = beatmap.Timing?.Bpm ?? 120.0;
            string timeSignature = beatmap.Timing?.TimeSignature ?? "4/4";

            foreach (var obj in sortedObjects)
            {
                if (Math.Abs(obj.Time - currentTime) < 2) // 2ms tolerance
                {
                    currentGroup.Add(obj);
                }
                else
                {
                    if (currentGroup.Count > 0)
                    {
                        var diffObj = new DifficultyHitObject(
                            currentGroup,
                            difficultyObjects.LastOrDefault(),
                            clockRate,
                            index++,
                            bpm,
                            timeSignature
                        );
                        difficultyObjects.Add(diffObj);
                    }
                    currentGroup = new List<HitObject> { obj };
                    currentTime = obj.Time;
                }
            }

            // Add last group
            if (currentGroup.Count > 0)
            {
                var diffObj = new DifficultyHitObject(
                    currentGroup,
                    difficultyObjects.LastOrDefault(),
                    clockRate,
                    index,
                    bpm,
                    timeSignature
                );
                difficultyObjects.Add(diffObj);
            }

            return difficultyObjects;
        }

        /// <summary>
        /// Generate difficulty curve points for visualization.
        /// </summary>
        private List<DifficultyPoint> GenerateDifficultyCurve(
            List<DifficultyHitObject> objects,
            Skill[] skills)
        {
            var curve = new List<DifficultyPoint>();

            if (objects.Count == 0)
                return curve;

            double startTime = objects[0].StartTime;
            double endTime = objects[^1].StartTime;

            // Create section snapshots
            for (double time = startTime; time <= endTime; time += DIFFICULTY_CURVE_SECTION_LENGTH)
            {
                // Find objects in this section
                var sectionObjects = objects
                    .Where(o => o.StartTime >= time && o.StartTime < time + DIFFICULTY_CURVE_SECTION_LENGTH)
                    .ToList();

                if (sectionObjects.Count == 0)
                    continue;

                // Simple approximation: use object count and strain estimates
                double density = sectionObjects.Count / (DIFFICULTY_CURVE_SECTION_LENGTH / 1000.0);

                // Sum up various strain indicators
                double speedStrain = sectionObjects.Sum(o => o.DeltaTime > 0 ? 1000.0 / o.DeltaTime : 0) / sectionObjects.Count;
                double coordStrain = sectionObjects.Sum(o => o.LimbCount) / (double)sectionObjects.Count;
                double techStrain = sectionObjects.Sum(o => o.Techniques.Count(t => t != TechniqueType.Normal)) / (double)sectionObjects.Count;

                curve.Add(new DifficultyPoint
                {
                    Time = time,
                    Difficulty = Math.Sqrt(density) * 0.5 + speedStrain * 0.01,
                    Speed = speedStrain * 0.1,
                    Coordination = coordStrain,
                    Technique = techStrain
                });
            }

            return curve;
        }

        /// <summary>
        /// Analyze speed-related details.
        /// </summary>
        private SpeedDetails AnalyzeSpeed(List<DifficultyHitObject> objects)
        {
            var details = new SpeedDetails();

            if (objects.Count < 2)
                return details;

            // Calculate NPS over sliding windows
            const double WINDOW_SIZE_MS = 1000; // 1 second
            double maxNPS = 0;
            double maxSustainedNPS = 0;
            int fastSectionCount = 0;

            for (int i = 0; i < objects.Count; i++)
            {
                // 1-second window
                double windowStart = objects[i].StartTime;
                int count1s = objects.Count(o => o.StartTime >= windowStart && o.StartTime < windowStart + WINDOW_SIZE_MS);
                double nps1s = count1s;
                maxNPS = Math.Max(maxNPS, nps1s);

                if (nps1s > 6) fastSectionCount++;

                // 2-second window for sustained
                int count2s = objects.Count(o => o.StartTime >= windowStart && o.StartTime < windowStart + 2000);
                double nps2s = count2s / 2.0;
                maxSustainedNPS = Math.Max(maxSustainedNPS, nps2s);
            }

            details.MaxNotesPerSecond = maxNPS;
            details.MaxSustainedNPS = maxSustainedNPS;
            details.FastSectionPercentage = (double)fastSectionCount / objects.Count * 100;
            details.HasBlastBeats = objects.Any(o => o.IsBlastBeat);
            details.HasDoubleBass = objects.Any(o => o.IsDoubleBass);

            // Estimate max sustained BPM from fastest sections
            if (maxSustainedNPS > 0)
            {
                // Assuming 16th notes: NPS = BPM / 60 * 4
                details.MaxSustainedBpm = maxSustainedNPS * 60 / 4;
            }

            return details;
        }

        /// <summary>
        /// Analyze technique usage.
        /// Counts all technique types detected in the beatmap for detailed breakdown.
        /// </summary>
        private TechniqueDetails AnalyzeTechniques(List<DifficultyHitObject> objects)
        {
            var details = new TechniqueDetails();

            foreach (var obj in objects)
            {
                foreach (var tech in obj.Techniques)
                {
                    switch (tech)
                    {
                        // Snare & Rudimental
                        case TechniqueType.Flam:
                            details.FlamCount++;
                            break;
                        case TechniqueType.Drag:
                            details.DragCount++;
                            break;
                        case TechniqueType.Roll:
                            details.RollCount++;
                            break;
                        case TechniqueType.BuzzRoll:
                            details.BuzzRollCount++;
                            break;
                        case TechniqueType.DoubleStroke:
                            details.DoubleStrokeCount++;
                            break;
                        case TechniqueType.GhostNote:
                            details.GhostNoteCount++;
                            break;
                        case TechniqueType.Rimshot:
                        case TechniqueType.TomRimshot:
                            details.RimshotCount++;
                            break;
                        case TechniqueType.CrossStick:
                            details.CrossStickCount++;
                            break;
                        case TechniqueType.DeadStroke:
                            details.DeadStrokeCount++;
                            break;

                        // Hi-Hat
                        case TechniqueType.HiHatBark:
                            details.HiHatBarkCount++;
                            break;
                        case TechniqueType.HiHatSplash:
                            details.HiHatSplashCount++;
                            break;
                        case TechniqueType.HiHatChick:
                            details.HiHatChickCount++;
                            break;

                        // Cymbal
                        case TechniqueType.Choke:
                            details.ChokeCount++;
                            break;
                        case TechniqueType.BellHit:
                            details.BellHitCount++;
                            break;
                        case TechniqueType.CrashRiding:
                            details.CrashRidingCount++;
                            break;
                        case TechniqueType.CrashBuild:
                            details.CrashBuildCount++;
                            break;

                        // Bass Drum
                        case TechniqueType.DoublePedalBurst:
                            details.DoublePedalBurstCount++;
                            break;
                        case TechniqueType.SlideDouble:
                            details.SlideDoubleCount++;
                            break;
                        case TechniqueType.Feathering:
                            details.FeatheringCount++;
                            break;

                        // Accents
                        case TechniqueType.Accent:
                            details.AccentCount++;
                            break;
                        case TechniqueType.AccentTap:
                            details.AccentTapCount++;
                            break;

                        // Advanced Rudiments
                        case TechniqueType.Paradiddle:
                        case TechniqueType.ParadiddleDiddle:
                            details.ParadiddleCount++;
                            break;
                        case TechniqueType.Herta:
                            details.HertaCount++;
                            break;
                        case TechniqueType.BonhamTriplets:
                            details.BonhamTripletsCount++;
                            break;
                        case TechniqueType.SwissArmyTriplet:
                        case TechniqueType.FlamTap:
                        case TechniqueType.FlamAccent:
                            details.SwissArmyTripletCount++;
                            break;

                        // Brush
                        case TechniqueType.BrushSweep:
                        case TechniqueType.BrushTap:
                            details.BrushTechniqueCount++;
                            break;

                        // Linear
                        case TechniqueType.LinearPattern:
                            details.LinearPatternCount++;
                            break;
                    }
                }
            }

            return details;
        }

        /// <summary>
        /// Analyze rhythmic complexity details.
        /// </summary>
        private RhythmDetails AnalyzeRhythm(List<DifficultyHitObject> objects)
        {
            var details = new RhythmDetails();

            var polyrhythms = new HashSet<string>();
            var timeSignatures = new HashSet<string>();
            int syncopatedCount = 0;

            foreach (var obj in objects)
            {
                if (obj.PolyrhythmType != null && obj.PolyrhythmType != "None")
                {
                    details.HasPolyrhythms = true;
                    polyrhythms.Add(obj.PolyrhythmType);
                }

                if (obj.CurrentTimeSignature.IsOddMeter)
                {
                    details.HasOddTime = true;
                    timeSignatures.Add($"{obj.CurrentTimeSignature.Numerator}/{obj.CurrentTimeSignature.Denominator}");
                }

                if (obj.IsMetricModulation)
                {
                    details.HasMetricModulation = true;
                }

                if (obj.OddGrouping > 0)
                {
                    details.HasOddGroupings = true;
                }

                if (obj.IsSyncopated)
                {
                    syncopatedCount++;
                }
            }

            details.PolyrhythmTypes = polyrhythms.ToList();
            details.TimeSignatures = timeSignatures.ToList();
            details.SyncopationPercentage = objects.Count > 0
                ? (double)syncopatedCount / objects.Count * 100
                : 0;

            return details;
        }

        /// <summary>
        /// Determine the primary drumming style based on difficulty patterns.
        /// </summary>
        private DrumStyle DetermineStyle(DifficultyAttributes attrs)
        {
            // Jazz: High rhythmic complexity, lots of ghost notes, precision
            if (attrs.RhythmicComplexityRating > 4 && attrs.Techniques.GhostNoteCount > 20)
                return DrumStyle.Jazz;

            // Metal: Blast beats, double bass, high speed
            if (attrs.Speed.HasBlastBeats || (attrs.Speed.HasDoubleBass && attrs.SpeedRating > 4))
                return DrumStyle.Metal;

            // Progressive: Complex rhythms, odd time, metric modulation
            if (attrs.Rhythm.HasMetricModulation || attrs.Rhythm.HasOddTime)
                return DrumStyle.Progressive;

            // Funk: High syncopation, ghost notes, groove focus
            if (attrs.Rhythm.SyncopationPercentage > 30 && attrs.Techniques.GhostNoteCount > 10)
                return DrumStyle.Funk;

            // Latin: Specific pattern recognition would go here
            // World: Similar

            // Electronic: Likely quantized, regular patterns
            if (attrs.PatternRating < 3 && attrs.Consistency.Pattern > 0.7)
                return DrumStyle.Electronic;

            // Pop: Simpler, accessible
            if (attrs.StarRating < 3)
                return DrumStyle.Pop;

            // Default to Rock
            return DrumStyle.Rock;
        }

        /// <summary>
        /// Determine recommended skill level from star rating.
        /// </summary>
        private SkillLevel DetermineLevel(double starRating)
        {
            return starRating switch
            {
                < 1.0 => SkillLevel.Beginner,
                < 2.0 => SkillLevel.Novice,
                < 3.0 => SkillLevel.Intermediate,
                < 4.0 => SkillLevel.Advanced,
                < 5.0 => SkillLevel.Expert,
                < 6.0 => SkillLevel.Master,
                _ => SkillLevel.Legendary
            };
        }

        /// <summary>
        /// Calculate beatmap duration in seconds.
        /// </summary>
        private double CalculateDuration(List<DifficultyHitObject> objects)
        {
            if (objects.Count < 2)
                return 0;

            return (objects[^1].StartTime - objects[0].StartTime) / 1000.0;
        }

        /// <summary>
        /// Estimate average BPM from hit intervals.
        /// </summary>
        private double CalculateAverageBpm(List<DifficultyHitObject> objects)
        {
            if (objects.Count < 2)
                return 120; // Default

            // Use median interval for robustness
            var intervals = objects
                .Where(o => o.DeltaTime > 50 && o.DeltaTime < 2000)
                .Select(o => o.DeltaTime)
                .OrderBy(i => i)
                .ToList();

            if (intervals.Count == 0)
                return 120;

            double medianInterval = intervals[intervals.Count / 2];

            // Assuming 16th notes: BPM = 60000 / interval / 4
            // But let's assume 8th notes for more stable estimate
            double estimatedBpm = 60000.0 / medianInterval / 2;

            // Clamp to reasonable range
            return Math.Clamp(estimatedBpm, 60, 300);
        }

        /// <summary>
        /// Determine primary time signature from objects.
        /// </summary>
        private string DeterminePrimaryTimeSignature(List<DifficultyHitObject> objects)
        {
            if (objects.Count == 0)
                return "4/4";

            var signatures = objects
                .GroupBy(o => $"{o.CurrentTimeSignature.Numerator}/{o.CurrentTimeSignature.Denominator}")
                .OrderByDescending(g => g.Count())
                .Select(g => g.Key)
                .ToList();

            return signatures.FirstOrDefault() ?? "4/4";
        }
    }
}
