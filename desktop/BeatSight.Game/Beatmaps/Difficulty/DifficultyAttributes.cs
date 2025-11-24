using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty
{
    /// <summary>
    /// Comprehensive difficulty attributes for a beatmap.
    /// Contains the overall star rating plus detailed breakdowns for each skill component.
    /// 
    /// This class captures the full multi-dimensional difficulty profile of a drumming
    /// beatmap, enabling users to understand not just overall difficulty but the specific
    /// skills required to master the piece.
    /// 
    /// Star Rating Scale (approximate):
    /// 0-1★:   Beginner       - Basic quarter-note patterns, simple grooves
    /// 1-2★:   Easy           - 8th-note patterns, basic fills, moderate tempo
    /// 2-3★:   Normal         - Standard rock/pop, some 16ths, coordination
    /// 3-4★:   Hard           - Complex grooves, fast fills, double bass intro
    /// 4-5★:   Expert         - Jazz comping, prog patterns, demanding coordination
    /// 5-6★:   Master         - Animals as Leaders, extreme coordination/speed
    /// 6-7★:   Legendary      - World-class difficulty, peak human drumming
    /// 7-8★:   Inhuman        - Theoretical maximum, may exceed human capability
    /// 8-10★:  Transcendent   - Multi-dimensional mastery at extreme levels
    /// 
    /// VERSION: 2.0.0
    /// </summary>
    public class DifficultyAttributes
    {
        // ========================
        // Algorithm Metadata
        // ========================

        /// <summary>
        /// Version of the difficulty algorithm used to calculate these attributes.
        /// Used for cache invalidation when the algorithm is updated.
        /// </summary>
        public int AlgorithmVersion { get; set; }

        // ========================
        // Primary Ratings
        // ========================

        /// <summary>
        /// Overall star rating combining all difficulty aspects.
        /// Scale: 0-10+ (most songs fall in 2-6 range)
        /// </summary>
        public double StarRating { get; set; }

        /// <summary>
        /// Speed difficulty - how fast the drummer must play.
        /// Accounts for: BPM, note density, blast beats, double bass, bursts
        /// </summary>
        public double SpeedRating { get; set; }

        /// <summary>
        /// Stamina difficulty - physical endurance requirements.
        /// Accounts for: Duration, sustained high-intensity sections, fatigue accumulation
        /// </summary>
        public double StaminaRating { get; set; }

        /// <summary>
        /// Coordination difficulty - limb independence and synchronization.
        /// Accounts for: Polyrhythms, unison hits, limb switching, four-way coordination
        /// </summary>
        public double CoordinationRating { get; set; }

        /// <summary>
        /// Rhythmic complexity - unusual time signatures, polyrhythms, metric modulation.
        /// Inspired by: Animals as Leaders, Meshuggah, jazz complexity
        /// </summary>
        public double RhythmicComplexityRating { get; set; }

        /// <summary>
        /// Pattern complexity - fill difficulty, groove uniqueness, orchestration.
        /// Accounts for: Fill length, kit coverage, movement patterns
        /// </summary>
        public double PatternRating { get; set; }

        /// <summary>
        /// Technique difficulty - specific drum techniques required.
        /// Accounts for: Flams, rolls, ghost notes, rimshots, hi-hat techniques, chokes
        /// </summary>
        public double TechniqueRating { get; set; }

        /// <summary>
        /// Reading difficulty - visual/cognitive load for sight-reading.
        /// Accounts for: Density, predictability, pattern variation
        /// </summary>
        public double ReadingRating { get; set; }

        /// <summary>
        /// Precision difficulty - timing and dynamic accuracy requirements.
        /// Accounts for: Grid deviation, velocity control, groove consistency
        /// </summary>
        public double PrecisionRating { get; set; }

        /// <summary>
        /// Movement difficulty - physical kit traversal requirements.
        /// Accounts for: Travel distance, crossovers, reach, kit geography
        /// </summary>
        public double MovementRating { get; set; }

        /// <summary>
        /// Musicality difficulty - musical expression and groove requirements.
        /// Accounts for: Dynamic shaping, swing feel, phrasing, textural variety
        /// </summary>
        public double MusicalityRating { get; set; }

        // ========================
        // Metadata
        // ========================

        /// <summary>
        /// Maximum combo (total hit objects).
        /// </summary>
        public int MaxCombo { get; set; }

        /// <summary>
        /// Total duration of the beatmap in seconds.
        /// </summary>
        public double Duration { get; set; }

        /// <summary>
        /// Average BPM of the beatmap.
        /// </summary>
        public double AverageBpm { get; set; }

        /// <summary>
        /// Most common time signature.
        /// </summary>
        public string PrimaryTimeSignature { get; set; } = "4/4";

        // ========================
        // Detailed Strain Analysis
        // ========================

        /// <summary>
        /// Peak strain values for each skill (maximum instantaneous difficulty).
        /// </summary>
        public SkillPeakStrains PeakStrains { get; set; } = new();

        /// <summary>
        /// Consistency factors for each skill (how sustained is the difficulty).
        /// Range: 0-1 where higher = more consistent difficulty throughout
        /// </summary>
        public SkillConsistency Consistency { get; set; } = new();

        /// <summary>
        /// Difficulty over time - used for difficulty graphs.
        /// Each entry is the peak difficulty for a time segment.
        /// </summary>
        public List<DifficultyPoint> DifficultyCurve { get; set; } = new();

        // ========================
        // Skill-Specific Details
        // ========================

        /// <summary>
        /// Detailed breakdown of speed-related difficulty factors.
        /// </summary>
        public SpeedDetails Speed { get; set; } = new();

        /// <summary>
        /// Detailed breakdown of technique usage in the map.
        /// </summary>
        public TechniqueDetails Techniques { get; set; } = new();

        /// <summary>
        /// Detailed breakdown of rhythmic complexity factors.
        /// </summary>
        public RhythmDetails Rhythm { get; set; } = new();

        /// <summary>
        /// Advanced analysis results from v3.1 analyzers.
        /// Includes groove analysis, polyrhythm detection, cognitive load, and independence.
        /// </summary>
        public AdvancedAnalysisResults? AdvancedAnalysis { get; set; }

        // ========================
        // Classification
        // ========================

        /// <summary>
        /// Primary genre/style classification based on difficulty patterns.
        /// </summary>
        public DrumStyle PrimaryStyle { get; set; } = DrumStyle.Rock;

        /// <summary>
        /// Suggested player skill level for this map.
        /// </summary>
        public SkillLevel RecommendedLevel { get; set; } = SkillLevel.Intermediate;

        /// <summary>
        /// Brief human-readable summary of the difficulty.
        /// </summary>
        public string DifficultyDescription => GenerateDescription();

        private string GenerateDescription()
        {
            var aspects = new List<string>();

            if (SpeedRating > 5) aspects.Add("extremely fast");
            else if (SpeedRating > 4) aspects.Add("fast");

            if (StaminaRating > 5) aspects.Add("endurance-heavy");

            if (CoordinationRating > 5) aspects.Add("complex coordination");
            else if (CoordinationRating > 4) aspects.Add("demanding coordination");

            if (RhythmicComplexityRating > 5) aspects.Add("highly complex rhythms");
            else if (RhythmicComplexityRating > 4) aspects.Add("complex rhythms");

            if (TechniqueRating > 5) aspects.Add("advanced techniques");

            if (PrecisionRating > 5) aspects.Add("precision-demanding");

            if (aspects.Count == 0)
            {
                return StarRating switch
                {
                    < 2 => "Accessible for beginners",
                    < 3 => "Standard difficulty",
                    < 4 => "Moderately challenging",
                    < 5 => "Challenging",
                    _ => "Very challenging"
                };
            }

            return string.Join(", ", aspects);
        }
    }

    /// <summary>
    /// Peak strain values for each skill component.
    /// </summary>
    public class SkillPeakStrains
    {
        public double Speed { get; set; }
        public double Stamina { get; set; }
        public double Coordination { get; set; }
        public double RhythmicComplexity { get; set; }
        public double Pattern { get; set; }
        public double Technique { get; set; }
        public double Reading { get; set; }
        public double Precision { get; set; }
        public double Movement { get; set; }
        public double Musicality { get; set; }

        /// <summary>
        /// Maximum peak across all skills.
        /// </summary>
        public double Maximum => new[] { Speed, Stamina, Coordination, RhythmicComplexity,
            Pattern, Technique, Reading, Precision, Movement, Musicality }.Max();
    }

    /// <summary>
    /// Consistency factors for each skill.
    /// Higher values mean difficulty is sustained throughout rather than spiking.
    /// </summary>
    public class SkillConsistency
    {
        public double Speed { get; set; }
        public double Stamina { get; set; }
        public double Coordination { get; set; }
        public double RhythmicComplexity { get; set; }
        public double Pattern { get; set; }
        public double Technique { get; set; }
        public double Reading { get; set; }
        public double Precision { get; set; }
        public double Movement { get; set; }
        public double Musicality { get; set; }
    }

    /// <summary>
    /// A point on the difficulty curve over time.
    /// </summary>
    public class DifficultyPoint
    {
        public double Time { get; set; }
        public double Difficulty { get; set; }
        public double Speed { get; set; }
        public double Coordination { get; set; }
        public double Technique { get; set; }
    }

    /// <summary>
    /// Detailed speed-related metrics.
    /// </summary>
    public class SpeedDetails
    {
        /// <summary>
        /// Maximum notes per second achieved.
        /// </summary>
        public double MaxNotesPerSecond { get; set; }

        /// <summary>
        /// Maximum sustained notes per second (over 2+ seconds).
        /// </summary>
        public double MaxSustainedNPS { get; set; }

        /// <summary>
        /// Percentage of map that is considered "fast" (>6 NPS).
        /// </summary>
        public double FastSectionPercentage { get; set; }

        /// <summary>
        /// Contains blast beats.
        /// </summary>
        public bool HasBlastBeats { get; set; }

        /// <summary>
        /// Contains double bass sections.
        /// </summary>
        public bool HasDoubleBass { get; set; }

        /// <summary>
        /// Maximum BPM for sustained playing.
        /// </summary>
        public double MaxSustainedBpm { get; set; }
    }

    /// <summary>
    /// Detailed technique usage breakdown.
    /// Tracks count of each technique type detected in the beatmap.
    /// </summary>
    public class TechniqueDetails
    {
        // ========================
        // SNARE & RUDIMENTAL
        // ========================
        public int FlamCount { get; set; }
        public int DragCount { get; set; }
        public int RollCount { get; set; }
        public int BuzzRollCount { get; set; }
        public int DoubleStrokeCount { get; set; }
        public int GhostNoteCount { get; set; }
        public int RimshotCount { get; set; }
        public int CrossStickCount { get; set; }
        public int DeadStrokeCount { get; set; }

        // ========================
        // HI-HAT
        // ========================
        public int HiHatBarkCount { get; set; }
        public int HiHatSplashCount { get; set; }
        public int HiHatChickCount { get; set; }

        // ========================
        // CYMBAL
        // ========================
        public int ChokeCount { get; set; }
        public int BellHitCount { get; set; }
        public int CrashRidingCount { get; set; }
        public int CrashBuildCount { get; set; }

        // ========================
        // BASS DRUM
        // ========================
        public int DoublePedalBurstCount { get; set; }
        public int SlideDoubleCount { get; set; }
        public int FeatheringCount { get; set; }

        // ========================
        // ACCENTS & DYNAMICS
        // ========================
        public int AccentCount { get; set; }
        public int AccentTapCount { get; set; }

        // ========================
        // ADVANCED RUDIMENTS
        // ========================
        public int ParadiddleCount { get; set; }
        public int HertaCount { get; set; }
        public int BonhamTripletsCount { get; set; }
        public int SwissArmyTripletCount { get; set; }

        // ========================
        // BRUSH
        // ========================
        public int BrushTechniqueCount { get; set; }

        // ========================
        // LINEAR
        // ========================
        public int LinearPatternCount { get; set; }

        /// <summary>
        /// Total techniques used (all non-normal articulations).
        /// </summary>
        public int TotalTechniques => FlamCount + DragCount + RollCount + BuzzRollCount +
                                       DoubleStrokeCount + GhostNoteCount + RimshotCount +
                                       CrossStickCount + HiHatBarkCount + HiHatSplashCount +
                                       ChokeCount + BellHitCount + DoublePedalBurstCount +
                                       SlideDoubleCount + AccentCount + AccentTapCount +
                                       ParadiddleCount + HertaCount + BonhamTripletsCount +
                                       SwissArmyTripletCount + BrushTechniqueCount + LinearPatternCount;

        /// <summary>
        /// Number of different technique types used.
        /// Higher variety indicates more sophisticated drumming.
        /// </summary>
        public int TechniqueVariety
        {
            get
            {
                int count = 0;
                if (FlamCount > 0) count++;
                if (DragCount > 0) count++;
                if (RollCount > 0) count++;
                if (BuzzRollCount > 0) count++;
                if (DoubleStrokeCount > 0) count++;
                if (GhostNoteCount > 0) count++;
                if (RimshotCount > 0) count++;
                if (CrossStickCount > 0) count++;
                if (DeadStrokeCount > 0) count++;
                if (HiHatBarkCount > 0) count++;
                if (HiHatSplashCount > 0) count++;
                if (HiHatChickCount > 0) count++;
                if (ChokeCount > 0) count++;
                if (BellHitCount > 0) count++;
                if (CrashRidingCount > 0) count++;
                if (DoublePedalBurstCount > 0) count++;
                if (SlideDoubleCount > 0) count++;
                if (FeatheringCount > 0) count++;
                if (AccentCount > 0) count++;
                if (AccentTapCount > 0) count++;
                if (ParadiddleCount > 0) count++;
                if (HertaCount > 0) count++;
                if (BonhamTripletsCount > 0) count++;
                if (SwissArmyTripletCount > 0) count++;
                if (BrushTechniqueCount > 0) count++;
                if (LinearPatternCount > 0) count++;
                return count;
            }
        }

        /// <summary>
        /// Complexity score based on technique usage.
        /// Considers both quantity and diversity of techniques.
        /// </summary>
        public double TechniqueComplexityScore
        {
            get
            {
                // Base score from variety
                double score = TechniqueVariety * 0.5;

                // Bonus for advanced techniques
                score += (ParadiddleCount > 0 ? 1.0 : 0) +
                         (HertaCount > 0 ? 1.5 : 0) +
                         (BonhamTripletsCount > 0 ? 2.0 : 0) +
                         (SwissArmyTripletCount > 0 ? 1.5 : 0) +
                         (AccentTapCount > 0 ? 1.0 : 0);

                // Bonus for technique density
                score += Math.Min(TotalTechniques / 100.0, 2.0);

                return score;
            }
        }
    }

    /// <summary>
    /// Detailed rhythmic complexity metrics.
    /// </summary>
    public class RhythmDetails
    {
        /// <summary>
        /// Contains polyrhythmic passages.
        /// </summary>
        public bool HasPolyrhythms { get; set; }

        /// <summary>
        /// Types of polyrhythms detected (e.g., "3:2", "4:3").
        /// </summary>
        public List<string> PolyrhythmTypes { get; set; } = new();

        /// <summary>
        /// Contains odd time signatures.
        /// </summary>
        public bool HasOddTime { get; set; }

        /// <summary>
        /// Time signatures used.
        /// </summary>
        public List<string> TimeSignatures { get; set; } = new();

        /// <summary>
        /// Contains metric modulation.
        /// </summary>
        public bool HasMetricModulation { get; set; }

        /// <summary>
        /// Percentage of map that is syncopated.
        /// </summary>
        public double SyncopationPercentage { get; set; }

        /// <summary>
        /// Contains odd groupings (quintuplets, septuplets, etc.).
        /// </summary>
        public bool HasOddGroupings { get; set; }
    }

    /// <summary>
    /// Drumming style classification.
    /// </summary>
    public enum DrumStyle
    {
        Rock,
        Metal,
        Jazz,
        Funk,
        Progressive,
        Electronic,
        Latin,
        World,
        Pop,
        Fusion
    }

    /// <summary>
    /// Recommended skill level for the map.
    /// </summary>
    public enum SkillLevel
    {
        Beginner,       // 0-1★
        Novice,         // 1-2★
        Intermediate,   // 2-3★
        Advanced,       // 3-4★
        Expert,         // 4-5★
        Master,         // 5-6★
        Legendary       // 6+★
    }

    /// <summary>
    /// Results from v3.1 advanced analysis components.
    /// Captures deep mathematical analysis of groove, polyrhythm, cognitive load,
    /// and limb independence.
    /// </summary>
    public class AdvancedAnalysisResults
    {
        // ========================
        // Groove Analysis
        // ========================

        /// <summary>
        /// Average swing amount across the beatmap (0 = straight, 0.33 = triplet shuffle).
        /// </summary>
        public double AverageSwingAmount { get; set; }

        /// <summary>
        /// Average groove complexity score.
        /// </summary>
        public double AverageGrooveComplexity { get; set; }

        /// <summary>
        /// Peak groove complexity in any section.
        /// </summary>
        public double PeakGrooveComplexity { get; set; }

        /// <summary>
        /// The dominant groove feel (Straight, Shuffle, Swing, Complex).
        /// </summary>
        public string DominantGrooveFeel { get; set; } = "Straight";

        // ========================
        // Polyrhythm Analysis
        // ========================

        /// <summary>
        /// Average polyrhythm complexity across the map.
        /// </summary>
        public double AveragePolyrhythmComplexity { get; set; }

        /// <summary>
        /// Peak polyrhythm complexity detected.
        /// </summary>
        public double PeakPolyrhythmComplexity { get; set; }

        /// <summary>
        /// List of detected polyrhythm ratios (e.g., "3:2", "5:4", "7:4").
        /// </summary>
        public List<string> DetectedPolyrhythms { get; set; } = new();

        /// <summary>
        /// Whether polymeter (different length patterns) was detected.
        /// </summary>
        public bool PolymeterDetected { get; set; }

        /// <summary>
        /// Maximum nested polyrhythm depth (0 = none, 1+ = nested layers).
        /// </summary>
        public int MaxNestedPolyrhythmDepth { get; set; }

        // ========================
        // Cognitive Load Analysis
        // ========================

        /// <summary>
        /// Average cognitive load score across the beatmap.
        /// </summary>
        public double AverageCognitiveLoad { get; set; }

        /// <summary>
        /// Peak cognitive load in any section.
        /// </summary>
        public double PeakCognitiveLoad { get; set; }

        /// <summary>
        /// Average information density (bits per second approximation).
        /// </summary>
        public double AverageInformationDensity { get; set; }

        /// <summary>
        /// Accumulated cognitive fatigue factor.
        /// </summary>
        public double CognitiveFatigueFactor { get; set; }

        // ========================
        // Independence Analysis
        // ========================

        /// <summary>
        /// Average limb independence score (0-10 scale).
        /// </summary>
        public double AverageIndependence { get; set; }

        /// <summary>
        /// Peak limb independence score.
        /// </summary>
        public double PeakIndependence { get; set; }

        /// <summary>
        /// Maximum number of simultaneously active limbs.
        /// </summary>
        public int MaxActiveLimbs { get; set; }

        /// <summary>
        /// Average rhythmic independence between limbs.
        /// </summary>
        public double AverageRhythmicIndependence { get; set; }

        /// <summary>
        /// Average dynamic independence (velocity contrast between limbs).
        /// </summary>
        public double AverageDynamicIndependence { get; set; }

        /// <summary>
        /// Get a human-readable summary of the advanced analysis.
        /// </summary>
        public string Summary
        {
            get
            {
                var parts = new List<string>();

                if (PeakPolyrhythmComplexity > 5)
                    parts.Add($"Complex polyrhythms ({string.Join(", ", DetectedPolyrhythms.Take(3))})");
                else if (DetectedPolyrhythms.Count > 0)
                    parts.Add($"Polyrhythmic ({DetectedPolyrhythms.FirstOrDefault()})");

                if (PolymeterDetected)
                    parts.Add("Polymetric");

                if (MaxNestedPolyrhythmDepth > 0)
                    parts.Add($"Nested polyrhythms (depth {MaxNestedPolyrhythmDepth + 1})");

                if (PeakIndependence > 7)
                    parts.Add("Extreme independence");
                else if (PeakIndependence > 5)
                    parts.Add("High independence");

                if (MaxActiveLimbs == 4)
                    parts.Add("4-way coordination");

                if (PeakCognitiveLoad > 25)
                    parts.Add("Very high cognitive load");
                else if (PeakCognitiveLoad > 15)
                    parts.Add("High cognitive load");

                if (AverageSwingAmount > 0.15)
                    parts.Add($"{DominantGrooveFeel} feel");

                return parts.Count > 0 ? string.Join(", ", parts) : "Standard drumming patterns";
            }
        }

        /// <summary>
        /// Independence level category.
        /// </summary>
        public string IndependenceLevel => PeakIndependence switch
        {
            < 2 => "Basic",
            < 4 => "Intermediate",
            < 6 => "Advanced",
            < 8 => "Expert",
            < 9 => "Elite",
            _ => "Transcendent"
        };

        /// <summary>
        /// Cognitive load category.
        /// </summary>
        public string CognitiveLoadLevel => PeakCognitiveLoad switch
        {
            < 5 => "Light",
            < 10 => "Moderate",
            < 15 => "Demanding",
            < 22 => "Heavy",
            < 30 => "Extreme",
            _ => "Overwhelming"
        };
    }
}
