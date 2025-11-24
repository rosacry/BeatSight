using System;
using System.Collections.Generic;

namespace BeatSight.Game.Beatmaps
{
    /// <summary>
    /// Extended hit object with articulation and dynamics information
    /// for AI-generated beatmaps and detailed drum analysis.
    /// 
    /// This extends the base HitObject with additional musical expression data
    /// that can be detected by the AI pipeline and visualized in the playfield.
    /// </summary>
    public class HitObjectExtended : HitObject
    {
        #region Articulation Properties

        /// <summary>
        /// The detected articulation type for this hit.
        /// </summary>
        public DrumArticulation Articulation { get; set; } = DrumArticulation.Normal;

        /// <summary>
        /// Additional articulation modifiers (e.g., rimshot + accent).
        /// </summary>
        public DrumArticulationFlags ArticulationFlags { get; set; } = DrumArticulationFlags.None;

        /// <summary>
        /// Specific technique used (e.g., "ghost", "flam", "buzz").
        /// </summary>
        public string? Technique { get; set; }

        /// <summary>
        /// For flamming/grace notes, the time offset of the grace note in ms.
        /// </summary>
        public int? GraceNoteOffset { get; set; }

        /// <summary>
        /// For rolls/buzzes, the number of strokes or the roll density.
        /// </summary>
        public int? StrokeCount { get; set; }

        #endregion

        #region Dynamics Properties

        /// <summary>
        /// Musical dynamics marking (pp to fff).
        /// </summary>
        public DynamicsLevel Dynamics { get; set; } = DynamicsLevel.MezzoForte;

        /// <summary>
        /// Fine-grained velocity value (0.0 to 1.0).
        /// More precise than the base Velocity property.
        /// </summary>
        public double VelocityPrecise { get; set; } = 0.75;

        /// <summary>
        /// Whether this note is part of a crescendo/decrescendo.
        /// </summary>
        public DynamicChange? DynamicChange { get; set; }

        /// <summary>
        /// The accent strength (0.0 = none, 1.0 = maximum accent).
        /// </summary>
        public double AccentStrength { get; set; } = 0.0;

        #endregion

        #region Timing Properties

        /// <summary>
        /// The detected timing offset from the grid in milliseconds.
        /// Positive = late, Negative = early.
        /// </summary>
        public double TimingOffsetMs { get; set; } = 0.0;

        /// <summary>
        /// Whether this note is intentionally swung.
        /// </summary>
        public bool IsSwung { get; set; } = false;

        /// <summary>
        /// Swing ratio if applicable (e.g., 1.5 for triplet swing).
        /// </summary>
        public double? SwingRatio { get; set; }

        #endregion

        #region Pattern Context

        /// <summary>
        /// ID of the pattern this note belongs to (e.g., a fill, groove).
        /// </summary>
        public string? PatternId { get; set; }

        /// <summary>
        /// Position within the pattern (0-based index).
        /// </summary>
        public int? PatternPosition { get; set; }

        /// <summary>
        /// Whether this note starts a new pattern/phrase.
        /// </summary>
        public bool IsPatternStart { get; set; } = false;

        /// <summary>
        /// Type of pattern this belongs to.
        /// </summary>
        public PatternType PatternType { get; set; } = PatternType.Groove;

        #endregion

        #region AI Confidence

        /// <summary>
        /// AI confidence in the component detection (0.0 to 1.0).
        /// </summary>
        public double ComponentConfidence { get; set; } = 1.0;

        /// <summary>
        /// AI confidence in the articulation detection (0.0 to 1.0).
        /// </summary>
        public double ArticulationConfidence { get; set; } = 1.0;

        /// <summary>
        /// AI confidence in the timing detection (0.0 to 1.0).
        /// </summary>
        public double TimingConfidence { get; set; } = 1.0;

        /// <summary>
        /// Whether this note has been manually edited after AI generation.
        /// </summary>
        public bool ManuallyEdited { get; set; } = false;

        #endregion

        #region Visual Hints

        /// <summary>
        /// Suggested visual color override (for complex articulations).
        /// </summary>
        public string? ColorHint { get; set; }

        /// <summary>
        /// Custom label to display (e.g., "L" for left hand).
        /// </summary>
        public string? DisplayLabel { get; set; }

        /// <summary>
        /// Whether to show sticking notation (L/R).
        /// </summary>
        public DrumSticking? Sticking { get; set; }

        #endregion
    }

    #region Enumerations

    /// <summary>
    /// Drum articulation types that can be detected by the AI.
    /// </summary>
    public enum DrumArticulation
    {
        /// <summary>Standard hit.</summary>
        Normal = 0,

        /// <summary>Accented hit (louder than surrounding notes).</summary>
        Accent = 1,

        /// <summary>Ghost note (very soft, often fills in grooves).</summary>
        Ghost = 2,

        /// <summary>Rimshot (stick hits rim and head simultaneously).</summary>
        Rimshot = 3,

        /// <summary>Cross-stick/side-stick (stick rests on head, hits rim).</summary>
        CrossStick = 4,

        /// <summary>Rim click (stick hits only the rim).</summary>
        RimClick = 5,

        /// <summary>Flam (grace note immediately before main note).</summary>
        Flam = 6,

        /// <summary>Drag (two grace notes before main note).</summary>
        Drag = 7,

        /// <summary>Buzz/press roll.</summary>
        Buzz = 8,

        /// <summary>Open hi-hat.</summary>
        Open = 9,

        /// <summary>Closed/tight hi-hat.</summary>
        Closed = 10,

        /// <summary>Half-open hi-hat.</summary>
        HalfOpen = 11,

        /// <summary>Hi-hat foot splash.</summary>
        FootSplash = 12,

        /// <summary>Choked cymbal.</summary>
        Choke = 13,

        /// <summary>Bell of cymbal.</summary>
        Bell = 14,

        /// <summary>Bow/body of cymbal.</summary>
        Bow = 15,

        /// <summary>Edge of cymbal (crash zone).</summary>
        Edge = 16,

        /// <summary>Muted/deadstroke.</summary>
        Muted = 17,

        /// <summary>Double stroke.</summary>
        Double = 18,

        /// <summary>Single stroke roll.</summary>
        Roll = 19
    }

    /// <summary>
    /// Flags for combining multiple articulation modifiers.
    /// </summary>
    [Flags]
    public enum DrumArticulationFlags
    {
        None = 0,
        Accented = 1 << 0,
        Ghosted = 1 << 1,
        Rimshot = 1 << 2,
        Flammed = 1 << 3,
        Choked = 1 << 4,
        Open = 1 << 5,
        Muted = 1 << 6,
        BellHit = 1 << 7,
        Swung = 1 << 8,
        LeftHand = 1 << 9,
        RightHand = 1 << 10,
        DoubleBass = 1 << 11
    }

    /// <summary>
    /// Standard musical dynamics levels.
    /// </summary>
    public enum DynamicsLevel
    {
        /// <summary>Pianissimo (very soft).</summary>
        Pianissimo = 0,

        /// <summary>Piano (soft).</summary>
        Piano = 1,

        /// <summary>Mezzo-piano (medium soft).</summary>
        MezzoPiano = 2,

        /// <summary>Mezzo-forte (medium loud) - default.</summary>
        MezzoForte = 3,

        /// <summary>Forte (loud).</summary>
        Forte = 4,

        /// <summary>Fortissimo (very loud).</summary>
        Fortissimo = 5,

        /// <summary>Fortississimo (as loud as possible).</summary>
        Fortississimo = 6
    }

    /// <summary>
    /// Dynamic change direction.
    /// </summary>
    public enum DynamicChange
    {
        /// <summary>No change.</summary>
        None = 0,

        /// <summary>Getting louder.</summary>
        Crescendo = 1,

        /// <summary>Getting softer.</summary>
        Decrescendo = 2,

        /// <summary>Sudden loud (sforzando).</summary>
        Sforzando = 3,

        /// <summary>Sudden soft (subito piano).</summary>
        SubitoPiano = 4
    }

    /// <summary>
    /// Pattern types for musical context.
    /// </summary>
    public enum PatternType
    {
        /// <summary>Main groove pattern.</summary>
        Groove = 0,

        /// <summary>Fill pattern.</summary>
        Fill = 1,

        /// <summary>Transition pattern.</summary>
        Transition = 2,

        /// <summary>Breakdown/sparse section.</summary>
        Breakdown = 3,

        /// <summary>Build-up section.</summary>
        BuildUp = 4,

        /// <summary>Intro pattern.</summary>
        Intro = 5,

        /// <summary>Outro pattern.</summary>
        Outro = 6,

        /// <summary>Solo section.</summary>
        Solo = 7,

        /// <summary>Improvised/free section.</summary>
        Free = 8
    }

    /// <summary>
    /// Sticking notation for drum parts.
    /// </summary>
    public enum DrumSticking
    {
        /// <summary>Not specified.</summary>
        Unspecified = 0,

        /// <summary>Right hand.</summary>
        Right = 1,

        /// <summary>Left hand.</summary>
        Left = 2,

        /// <summary>Right foot.</summary>
        RightFoot = 3,

        /// <summary>Left foot.</summary>
        LeftFoot = 4,

        /// <summary>Both hands together.</summary>
        Both = 5
    }

    #endregion

    #region Pattern Definition

    /// <summary>
    /// Represents a detected musical pattern in the beatmap.
    /// </summary>
    public class DrumPattern
    {
        /// <summary>Unique identifier for this pattern.</summary>
        public string PatternId { get; set; } = Guid.NewGuid().ToString();

        /// <summary>Human-readable name for the pattern.</summary>
        public string? Name { get; set; }

        /// <summary>Type of pattern.</summary>
        public PatternType Type { get; set; } = PatternType.Groove;

        /// <summary>Start time in milliseconds.</summary>
        public int StartTime { get; set; }

        /// <summary>End time in milliseconds.</summary>
        public int EndTime { get; set; }

        /// <summary>Duration in beats.</summary>
        public double DurationBeats { get; set; }

        /// <summary>IDs of hit objects belonging to this pattern.</summary>
        public List<int> HitObjectIndices { get; set; } = new();

        /// <summary>AI confidence in pattern detection.</summary>
        public double Confidence { get; set; } = 1.0;

        /// <summary>Whether this pattern repeats elsewhere in the beatmap.</summary>
        public bool IsRepeating { get; set; } = false;

        /// <summary>Indices of similar patterns in the beatmap.</summary>
        public List<int>? SimilarPatternIndices { get; set; }

        /// <summary>Tags for this pattern (e.g., "linear", "syncopated").</summary>
        public List<string>? Tags { get; set; }
    }

    #endregion

    #region Extended Beatmap Info

    /// <summary>
    /// Extended AI generation metadata for detailed transcription info.
    /// </summary>
    public class AIGenerationMetadataExtended : AIGenerationMetadata
    {
        /// <summary>Articulation detection model version.</summary>
        public string? ArticulationModelVersion { get; set; }

        /// <summary>Average articulation confidence across all notes.</summary>
        public double? AverageArticulationConfidence { get; set; }

        /// <summary>Number of notes with low confidence (&lt; 0.7).</summary>
        public int? LowConfidenceNoteCount { get; set; }

        /// <summary>Detected patterns in the beatmap.</summary>
        public List<DrumPattern>? DetectedPatterns { get; set; }

        /// <summary>Overall groove feel detection (straight, swing, etc.).</summary>
        public string? GrooveFeel { get; set; }

        /// <summary>Detected swing amount if applicable (0.0 to 1.0).</summary>
        public double? SwingAmount { get; set; }

        /// <summary>Primary time feel (e.g., "half-time", "double-time").</summary>
        public string? TimeFeel { get; set; }

        /// <summary>Detected genre/style hints.</summary>
        public List<string>? StyleHints { get; set; }

        /// <summary>Statistics about the transcription.</summary>
        public TranscriptionStatistics? Statistics { get; set; }
    }

    /// <summary>
    /// Statistics about a transcription.
    /// </summary>
    public class TranscriptionStatistics
    {
        /// <summary>Total number of hits.</summary>
        public int TotalHits { get; set; }

        /// <summary>Hits per component.</summary>
        public Dictionary<string, int>? HitsPerComponent { get; set; }

        /// <summary>Average velocity.</summary>
        public double AverageVelocity { get; set; }

        /// <summary>Velocity standard deviation.</summary>
        public double VelocityStdDev { get; set; }

        /// <summary>Average hits per minute (density).</summary>
        public double AverageHitsPerMinute { get; set; }

        /// <summary>Maximum hits per second (peak density).</summary>
        public double MaxHitsPerSecond { get; set; }

        /// <summary>Number of unique patterns detected.</summary>
        public int UniquePatternCount { get; set; }

        /// <summary>Percentage of notes that are ghost notes.</summary>
        public double GhostNotePercentage { get; set; }

        /// <summary>Percentage of notes that are accented.</summary>
        public double AccentedNotePercentage { get; set; }
    }

    #endregion
}
