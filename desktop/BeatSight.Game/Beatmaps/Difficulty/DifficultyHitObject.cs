using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty
{
    /// <summary>
    /// Represents which limb is used to play a drum component.
    /// </summary>
    public enum LimbType
    {
        LeftHand,
        RightHand,
        LeftFoot,
        RightFoot,
        Hand,  // Generic hand (either)
        Foot   // Generic foot (either)
    }

    /// <summary>
    /// Classification of drum kit components by type.
    /// </summary>
    public enum DrumType
    {
        Kick,
        Snare,
        HiHat,
        HiHatPedal,
        Tom,
        TomHigh,
        TomMid,
        TomLow,
        Crash,
        Ride,
        RideBell,
        China,
        Splash,
        Stack,
        Cowbell,
        Tambourine,
        Other
    }

    /// <summary>
    /// Technique or articulation type detected on a hit.
    /// These are techniques the AI model can currently detect.
    /// Aligned with additionaldrummertech.txt - only techniques the model accounts for.
    /// 
    /// IMPLEMENTATION NOTE: This enum reflects the techniques that the AI/model
    /// can actually detect and annotate in beatmaps. The difficulty system uses
    /// these to calculate technique-specific strain values.
    /// </summary>
    public enum TechniqueType
    {
        Normal,

        // ========================
        // SNARE & RUDIMENTAL ARTICULATIONS
        // ========================
        Flam,           // Grace note + primary stroke (thick, two-hit sound)
        Drag,           // Ruff - two+ soft grace notes preceding primary
        Roll,           // Open roll - rapid repeated single/double strokes
        BuzzRoll,       // Press/buzz roll - multiple bounces per hand
        DoubleStroke,   // Diddle - RR/LL pairs
        GhostNote,      // Very soft strokes between main hits for feel/texture
        Rimshot,        // Head + rim simultaneously (loud crack)
        CrossStick,     // Side-stick - tip rests on head, shoulder hits rim
        StickshotShot,  // Stick shot - one stick strikes head while other braces on rim
        DeadStroke,     // Muffled stroke - stick stays on head after impact

        // ========================
        // HI-HAT SPECIFIC
        // ========================
        HiHatBark,      // Quick open-close "bark" accent
        HiHatSplash,    // Foot splash - airy "fsshh" sound
        HiHatChick,     // Foot chick (pedal only, no stick)
        HiHatHalfOpen,  // Partially open - controlled sizzle

        // ========================
        // CYMBAL TECHNIQUES
        // ========================
        Choke,          // Grab cymbal after hit to cut sustain
        BellHit,        // Ride/crash bell accent - distinct ping
        CymbalScrape,   // Edge scrape - shimmering effect
        MalletSwell,    // Soft mallet crescendo
        CrashRiding,    // Keeping time on crash cymbal
        CrashBuild,     // Repeated cymbal hits crescendoing into section

        // ========================
        // TOM TECHNIQUES
        // ========================
        TomRimshot,     // Tom head + rim accent

        // ========================
        // BASS DRUM TECHNIQUES
        // ========================
        DoublePedalBurst, // Rapid consecutive double pedal strokes
        SlideDouble,    // Slide/swivel technique for fast doubles
        Feathering,     // Very soft quarter-note pulses (jazz)

        // ========================
        // STACK/EFFECT
        // ========================
        StackHit,       // Short, trashy stack cymbal hit

        // ========================
        // ACCENT PATTERNS & DYNAMICS
        // ========================
        Accent,         // Louder stroke for emphasis
        AccentTap,      // Moeller accent-tap pattern (alternating loud/soft)

        // ========================
        // RUDIMENTAL VOCABULARY (Advanced)
        // ========================
        Paradiddle,     // RLRR LRLL pattern
        ParadiddleDiddle, // Paradiddle ending with RR/LL (triplet-friendly)
        Herta,          // Fast single-single-double burst (R L RR)
        SwissArmyTriplet, // Flam-accented triplet
        BonhamTriplets, // Orchestrated triplets (often R L K)
        FlamTap,        // Flam + tap combination
        FlamAccent,     // Flam with accent

        // ========================
        // LINEAR DRUMMING
        // ========================
        LinearPattern,  // No simultaneous limb hits - one at a time

        // ========================
        // BRUSH/SPECIAL ARTICULATION
        // ========================
        BrushSweep,     // Circular brush motion
        BrushTap        // Articulated brush strike
    }

    /// <summary>
    /// Time signature information for rhythm analysis.
    /// </summary>
    public readonly struct TimeSignature
    {
        public readonly int Numerator;
        public readonly int Denominator;

        public TimeSignature(int numerator, int denominator)
        {
            Numerator = numerator;
            Denominator = denominator;
        }

        public static TimeSignature Parse(string timeSignature)
        {
            if (string.IsNullOrEmpty(timeSignature))
                return new TimeSignature(4, 4);

            var parts = timeSignature.Split('/');
            if (parts.Length != 2)
                return new TimeSignature(4, 4);

            if (int.TryParse(parts[0], out int num) && int.TryParse(parts[1], out int denom))
                return new TimeSignature(num, denom);

            return new TimeSignature(4, 4);
        }

        public double BeatsPerMeasure => Numerator;
        public bool IsOddMeter => Numerator % 2 != 0 || (Numerator != 4 && Numerator != 2);
    }

    /// <summary>
    /// Wraps a HitObject with difficulty calculation metadata.
    /// Contains all pre-computed values needed for skill calculations.
    /// </summary>
    public class DifficultyHitObject
    {
        // ========================
        // Core Properties
        // ========================

        public readonly List<HitObject> BaseObjects;
        public readonly DifficultyHitObject? Previous;
        public readonly double DeltaTime;
        public readonly double StartTime;
        public readonly int Index;

        /// <summary>
        /// Minimum strain time to avoid division by zero and extreme values.
        /// At 300 BPM 32nd notes, this is about 25ms.
        /// </summary>
        private const double MIN_STRAIN_TIME = 25.0;

        // ========================
        // Limb Properties
        // ========================

        public bool HasLeftHand { get; private set; }
        public bool HasRightHand { get; private set; }
        public bool HasLeftFoot { get; private set; }
        public bool HasRightFoot { get; private set; }
        public bool HasHand => HasLeftHand || HasRightHand;
        public bool HasFoot => HasLeftFoot || HasRightFoot;
        public int LimbCount { get; private set; }

        // ========================
        // Note Properties
        // ========================

        public int NoteCount => BaseObjects.Count;
        public double MaxVelocity { get; private set; }
        public double MinVelocity { get; private set; }
        public double AverageVelocity { get; private set; }
        public double VelocityRange => MaxVelocity - MinVelocity;

        // ========================
        // Rhythm Properties
        // ========================

        /// <summary>
        /// Ratio of this delta time to the previous delta time.
        /// Used for rhythm change detection.
        /// </summary>
        public double RhythmRatio { get; private set; } = 1.0;

        /// <summary>
        /// How far off from a simple rhythmic grid this note is.
        /// 0.0 = perfectly on grid, 1.0 = maximally off-grid.
        /// High values indicate swing, humanization, or complex subdivisions.
        /// </summary>
        public double GridDeviation { get; private set; }

        /// <summary>
        /// Whether this note appears to be syncopated (off the beat).
        /// </summary>
        public bool IsSyncopated { get; private set; }

        /// <summary>
        /// The BPM at this point in the beatmap.
        /// </summary>
        public double CurrentBpm { get; private set; } = 120.0;

        /// <summary>
        /// Time signature at this point.
        /// </summary>
        public TimeSignature CurrentTimeSignature { get; private set; } = new TimeSignature(4, 4);

        /// <summary>
        /// Alias for CurrentTimeSignature for convenience.
        /// </summary>
        public TimeSignature TimeSignature => CurrentTimeSignature;

        /// <summary>
        /// Effective strain time (capped at minimum).
        /// </summary>
        public double StrainTime => Math.Max(DeltaTime, MIN_STRAIN_TIME);

        // ========================
        // Pattern Properties
        // ========================

        public List<DrumType> DrumTypes { get; private set; } = new();
        public List<TechniqueType> Techniques { get; private set; } = new();

        /// <summary>
        /// Physical travel distance on the drum kit.
        /// </summary>
        public double TravelDistance { get; private set; }

        /// <summary>
        /// Shannon entropy of recent drum type patterns.
        /// High entropy = unpredictable, low entropy = repetitive.
        /// </summary>
        public double PatternEntropy { get; private set; }

        /// <summary>
        /// Whether this is part of a double bass pattern.
        /// </summary>
        public bool IsDoubleBass { get; private set; }

        /// <summary>
        /// Whether this appears to be part of a blast beat pattern.
        /// </summary>
        public bool IsBlastBeat { get; private set; }

        /// <summary>
        /// Whether this is linear drumming (no simultaneous limb hits).
        /// </summary>
        public bool IsLinear { get; private set; }

        /// <summary>
        /// Speed in notes per second at this point.
        /// </summary>
        public double NotesPerSecond => DeltaTime > 0 ? 1000.0 / DeltaTime : 0;

        // ========================
        // Complexity Metrics
        // ========================

        /// <summary>
        /// Detected polyrhythm type (e.g., "3:2", "4:3").
        /// </summary>
        public string? PolyrhythmType { get; private set; }

        /// <summary>
        /// Whether metric modulation is detected at this point.
        /// </summary>
        public bool IsMetricModulation { get; private set; }

        /// <summary>
        /// Odd grouping detected (5, 7, 9, etc.).
        /// </summary>
        public int? OddGrouping { get; private set; }

        /// <summary>
        /// Movement speed across the kit (distance / time).
        /// </summary>
        public double MovementSpeed { get; private set; }

        // ========================
        // Constructor
        // ========================

        public DifficultyHitObject(
            List<HitObject> hitObjects,
            DifficultyHitObject? previous,
            double clockRate,
            int index,
            double bpm = 120.0,
            string timeSignature = "4/4")
        {
            BaseObjects = hitObjects;
            Previous = previous;
            Index = index;
            CurrentBpm = bpm;
            CurrentTimeSignature = TimeSignature.Parse(timeSignature);

            // Calculate start time (all objects in group have same time)
            if (hitObjects.Count > 0)
                StartTime = hitObjects[0].Time / clockRate;

            // Calculate delta time from previous
            DeltaTime = StartTime - (Previous?.StartTime ?? StartTime);

            // Calculate rhythm ratio
            if (Previous != null && Previous.DeltaTime > 0)
                RhythmRatio = DeltaTime / Previous.DeltaTime;

            // Process each hit object
            ProcessHitObjects(hitObjects);

            // Calculate advanced metrics
            CalculateLimbUsage();
            CalculateVelocityMetrics();
            CalculateRhythmMetrics();
            CalculatePatternMetrics();
            CalculateMovementMetrics();
            DetectSpecialPatterns();
        }

        // ========================
        // Processing Methods
        // ========================

        private void ProcessHitObjects(List<HitObject> hitObjects)
        {
            foreach (var obj in hitObjects)
            {
                DrumTypes.Add(GetDrumType(obj.Component));
                Techniques.Add(GetTechniqueType(obj.Component));
            }
        }

        private void CalculateLimbUsage()
        {
            foreach (var obj in BaseObjects)
            {
                var limb = GetLimbType(obj.Component);
                switch (limb)
                {
                    case LimbType.LeftHand:
                        HasLeftHand = true;
                        break;
                    case LimbType.RightHand:
                        HasRightHand = true;
                        break;
                    case LimbType.LeftFoot:
                        HasLeftFoot = true;
                        break;
                    case LimbType.RightFoot:
                        HasRightFoot = true;
                        break;
                    case LimbType.Hand:
                        // Assign to right hand by default, left if right already used
                        if (!HasRightHand) HasRightHand = true;
                        else HasLeftHand = true;
                        break;
                    case LimbType.Foot:
                        if (!HasRightFoot) HasRightFoot = true;
                        else HasLeftFoot = true;
                        break;
                }
            }

            LimbCount = (HasLeftHand ? 1 : 0) + (HasRightHand ? 1 : 0) +
                        (HasLeftFoot ? 1 : 0) + (HasRightFoot ? 1 : 0);

            // Linear drumming: only one limb active at a time
            IsLinear = LimbCount == 1 && NoteCount == 1;
        }

        private void CalculateVelocityMetrics()
        {
            if (BaseObjects.Count == 0)
            {
                MaxVelocity = MinVelocity = AverageVelocity = 0;
                return;
            }

            var velocities = BaseObjects.Select(o => o.Velocity).ToList();
            MaxVelocity = velocities.Max();
            MinVelocity = velocities.Min();
            AverageVelocity = velocities.Average();
        }

        private void CalculateRhythmMetrics()
        {
            if (RhythmRatio <= 0) return;

            // Grid deviation: how far from common subdivisions
            double[] commonRatios = {
                1.0,    // Same as before
                0.5, 2.0,    // Double/half speed
                0.333, 3.0,  // Triplets
                0.25, 4.0,   // 16ths from 8ths
                0.666, 1.5,  // Triplet feel (shuffle)
                0.75, 1.333, // Dotted rhythms
                0.2, 5.0,    // Quintuplets
                0.143, 7.0,  // Septuplets
                1.25, 0.8,   // 5:4 polyrhythm
                1.75, 0.571, // 7:4 polyrhythm
            };

            double minDifference = commonRatios.Min(r => Math.Abs(RhythmRatio - r));
            GridDeviation = Math.Clamp(minDifference * 3.0, 0, 1);

            // Syncopation detection
            // If we're significantly off the expected grid, it's syncopated
            IsSyncopated = GridDeviation > 0.15 || DetectSyncopation();

            // Polyrhythm detection
            DetectPolyrhythm();
        }

        private bool DetectSyncopation()
        {
            if (Previous == null) return false;

            // Calculate expected position based on beat grid
            double beatLength = 60000.0 / CurrentBpm; // ms per beat
            double positionInBeat = StartTime % beatLength;
            double normalizedPosition = positionInBeat / beatLength;

            // Strong beats are at 0, 0.5 (in 4/4)
            // If we're not near these, it could be syncopated
            double[] strongPositions = { 0, 0.25, 0.5, 0.75 };
            double nearestStrong = strongPositions.Min(p => Math.Abs(normalizedPosition - p));

            return nearestStrong > 0.1; // More than 10% away from strong position
        }

        private void DetectPolyrhythm()
        {
            // Detect common polyrhythmic ratios
            if (Math.Abs(RhythmRatio - 1.5) < 0.08 || Math.Abs(RhythmRatio - 0.666) < 0.08)
            {
                PolyrhythmType = "3:2";
            }
            else if (Math.Abs(RhythmRatio - 1.333) < 0.08 || Math.Abs(RhythmRatio - 0.75) < 0.08)
            {
                PolyrhythmType = "4:3";
            }
            else if (Math.Abs(RhythmRatio - 1.25) < 0.08 || Math.Abs(RhythmRatio - 0.8) < 0.08)
            {
                PolyrhythmType = "5:4";
            }
            else if (Math.Abs(RhythmRatio - 1.75) < 0.08 || Math.Abs(RhythmRatio - 0.571) < 0.08)
            {
                PolyrhythmType = "7:4";
            }

            // Detect odd groupings from ratio
            if (Math.Abs(RhythmRatio - 0.2) < 0.05 || Math.Abs(RhythmRatio - 5.0) < 0.3)
                OddGrouping = 5;
            else if (Math.Abs(RhythmRatio - 0.143) < 0.03 || Math.Abs(RhythmRatio - 7.0) < 0.4)
                OddGrouping = 7;
        }

        private void CalculatePatternMetrics()
        {
            // Calculate entropy from recent history
            var history = new List<DrumType>();
            var curr = this;
            for (int i = 0; i < 16; i++) // Look back 16 notes
            {
                history.AddRange(curr.DrumTypes);
                curr = curr.Previous;
                if (curr == null) break;
            }
            PatternEntropy = CalculateShannonEntropy(history);
        }

        private void CalculateMovementMetrics()
        {
            if (Previous == null)
            {
                TravelDistance = 0;
                MovementSpeed = 0;
                return;
            }

            var currentPositions = DrumTypes.Select(GetDrumPosition).ToList();
            var prevPositions = Previous.DrumTypes.Select(GetDrumPosition).ToList();

            if (!currentPositions.Any() || !prevPositions.Any())
            {
                TravelDistance = 0;
                MovementSpeed = 0;
                return;
            }

            // Calculate minimum movement required (optimal sticking)
            TravelDistance = currentPositions.Min(c => prevPositions.Min(p => GetDistance(c, p)));

            // Movement speed = distance / time
            MovementSpeed = TravelDistance / Math.Max(DeltaTime, MIN_STRAIN_TIME) * 1000.0;
        }

        private void DetectSpecialPatterns()
        {
            // Double bass detection
            IsDoubleBass = HasFoot && Previous != null && Previous.HasFoot && DeltaTime < 150;

            // Blast beat detection: Fast alternating kick/snare with cymbal
            if (Previous != null && DeltaTime < 120)
            {
                bool hasKick = DrumTypes.Contains(DrumType.Kick);
                bool hasSnare = DrumTypes.Contains(DrumType.Snare);
                bool hasCymbal = DrumTypes.Any(d => d == DrumType.HiHat || d == DrumType.Crash || d == DrumType.Ride);

                bool prevHadKick = Previous.DrumTypes.Contains(DrumType.Kick);
                bool prevHadSnare = Previous.DrumTypes.Contains(DrumType.Snare);

                // Classic blast: alternating kick/snare
                IsBlastBeat = (hasKick && prevHadSnare) || (hasSnare && prevHadKick);

                // Bonus if cymbal is riding on top
                if (IsBlastBeat && (hasCymbal || Previous.DrumTypes.Any(d => d == DrumType.HiHat || d == DrumType.Crash)))
                    IsBlastBeat = true;
            }

            // Metric modulation: look for tempo feel shift
            if (Previous?.Previous?.Previous != null)
            {
                var recentDeltas = new List<double> {
                    DeltaTime,
                    Previous.DeltaTime,
                    Previous.Previous.DeltaTime,
                    Previous.Previous.Previous.DeltaTime
                };

                double firstAvg = (recentDeltas[2] + recentDeltas[3]) / 2;
                double lastAvg = (recentDeltas[0] + recentDeltas[1]) / 2;

                double firstVar = Math.Abs(recentDeltas[2] - recentDeltas[3]) / Math.Max(firstAvg, 1);
                double lastVar = Math.Abs(recentDeltas[0] - recentDeltas[1]) / Math.Max(lastAvg, 1);

                // Consistent in each half but different between halves
                IsMetricModulation = firstVar < 0.1 && lastVar < 0.1 && Math.Abs(firstAvg - lastAvg) / Math.Max(firstAvg, 1) > 0.2;
            }
        }

        // ========================
        // Helper Methods
        // ========================

        private static double CalculateShannonEntropy(List<DrumType> symbols)
        {
            if (symbols.Count == 0) return 0;

            var groups = symbols.GroupBy(x => x);
            double entropy = 0;

            foreach (var group in groups)
            {
                double p = (double)group.Count() / symbols.Count;
                entropy -= p * Math.Log(p, 2);
            }

            return entropy;
        }

        private static (double x, double y) GetDrumPosition(DrumType type)
        {
            // Virtual drum kit layout (top-down view, normalized coordinates)
            // Origin (0,0) is drummer's seat, positive Y is forward, positive X is right
            // Extended for complex kits (Animals as Leaders, prog metal)
            return type switch
            {
                // Center
                DrumType.Kick => (0, 0.6),
                DrumType.Snare => (-0.4, 0.7),

                // Left side
                DrumType.HiHat => (-1.0, 0.8),
                DrumType.HiHatPedal => (-0.9, 0.4),

                // Toms (left to right)
                DrumType.TomHigh => (-0.2, 1.1),
                DrumType.TomMid => (0.3, 1.1),
                DrumType.Tom => (0.0, 1.1),  // Generic tom
                DrumType.TomLow => (0.8, 0.8),  // Floor tom

                // Cymbals
                DrumType.Crash => (-0.8, 1.4),
                DrumType.Ride => (0.9, 1.2),
                DrumType.RideBell => (0.85, 1.15),
                DrumType.China => (1.2, 1.3),
                DrumType.Splash => (-0.5, 1.3),
                DrumType.Stack => (0.4, 1.4),

                // Aux
                DrumType.Cowbell => (0.1, 1.0),
                DrumType.Tambourine => (-0.7, 1.2),

                _ => (0, 1.0)
            };
        }

        private static double GetDistance((double x, double y) p1, (double x, double y) p2)
        {
            return Math.Sqrt(Math.Pow(p1.x - p2.x, 2) + Math.Pow(p1.y - p2.y, 2));
        }

        private static LimbType GetLimbType(string component)
        {
            if (string.IsNullOrEmpty(component)) return LimbType.Hand;
            var lower = component.ToLowerInvariant();

            // Foot components
            if (lower.Contains("kick") || lower.Contains("bass") || lower.Contains("bd"))
                return LimbType.RightFoot;
            if (lower.Contains("pedal") || lower.Contains("hh_pedal") || lower.Contains("hihat_pedal"))
                return LimbType.LeftFoot;
            if (lower.Contains("double_kick") || lower.Contains("left_kick"))
                return LimbType.LeftFoot;

            // Hand components - try to infer sticking
            if (lower.Contains("snare") || lower.Contains("tom"))
                return LimbType.Hand;
            if (lower.Contains("hihat") || lower.Contains("hh_"))
                return LimbType.RightHand; // Common right-hand lead
            if (lower.Contains("ride"))
                return LimbType.RightHand;
            if (lower.Contains("crash"))
                return LimbType.Hand; // Could be either

            return LimbType.Hand;
        }

        private static DrumType GetDrumType(string component)
        {
            if (string.IsNullOrEmpty(component)) return DrumType.Other;
            var lower = component.ToLowerInvariant();

            // Kicks
            if (lower.Contains("kick") || lower.Contains("bass") || lower.Contains("bd"))
                return DrumType.Kick;

            // Snare variants
            if (lower.Contains("snare"))
                return DrumType.Snare;

            // Hi-hat variants
            if (lower.Contains("hihat_pedal") || lower.Contains("hh_pedal") || lower.Contains("pedal"))
                return DrumType.HiHatPedal;
            if (lower.Contains("hihat") || lower.Contains("hh_") || lower.Contains("hat"))
                return DrumType.HiHat;

            // Tom variants (specific first)
            if (lower.Contains("tom_high") || lower.Contains("tom_1") || lower.Contains("high_tom"))
                return DrumType.TomHigh;
            if (lower.Contains("tom_mid") || lower.Contains("tom_2") || lower.Contains("mid_tom"))
                return DrumType.TomMid;
            if (lower.Contains("tom_low") || lower.Contains("tom_3") || lower.Contains("floor"))
                return DrumType.TomLow;
            if (lower.Contains("tom"))
                return DrumType.Tom;

            // Cymbal variants
            if (lower.Contains("ride_bell") || lower.Contains("bell"))
                return DrumType.RideBell;
            if (lower.Contains("ride"))
                return DrumType.Ride;
            if (lower.Contains("china"))
                return DrumType.China;
            if (lower.Contains("splash"))
                return DrumType.Splash;
            if (lower.Contains("stack"))
                return DrumType.Stack;
            if (lower.Contains("crash"))
                return DrumType.Crash;
            if (lower.Contains("cymbal"))
                return DrumType.Crash;

            // Aux percussion
            if (lower.Contains("cowbell"))
                return DrumType.Cowbell;
            if (lower.Contains("tambourine"))
                return DrumType.Tambourine;

            return DrumType.Other;
        }

        private static TechniqueType GetTechniqueType(string component)
        {
            if (string.IsNullOrEmpty(component)) return TechniqueType.Normal;
            var lower = component.ToLowerInvariant();

            // ========================
            // RUDIMENTAL VOCABULARY (check first - more specific patterns)
            // ========================
            if (lower.Contains("paradiddle") && lower.Contains("diddle"))
                return TechniqueType.ParadiddleDiddle;
            if (lower.Contains("paradiddle"))
                return TechniqueType.Paradiddle;
            if (lower.Contains("herta"))
                return TechniqueType.Herta;
            if (lower.Contains("swiss") || lower.Contains("swiss_army"))
                return TechniqueType.SwissArmyTriplet;
            if (lower.Contains("bonham") && lower.Contains("triplet"))
                return TechniqueType.BonhamTriplets;
            if (lower.Contains("flam_tap") || lower.Contains("flamtap"))
                return TechniqueType.FlamTap;
            if (lower.Contains("flam_accent") || lower.Contains("flamaccent"))
                return TechniqueType.FlamAccent;

            // ========================
            // SNARE & RUDIMENTAL TECHNIQUES
            // ========================
            if (lower.Contains("flam"))
                return TechniqueType.Flam;
            if (lower.Contains("drag") || lower.Contains("ruff"))
                return TechniqueType.Drag;
            if (lower.Contains("buzz") || lower.Contains("press"))
                return TechniqueType.BuzzRoll;
            if (lower.Contains("roll"))
                return TechniqueType.Roll;
            if (lower.Contains("ghost"))
                return TechniqueType.GhostNote;
            if (lower.Contains("rimshot") || lower.Contains("rim_shot"))
                return TechniqueType.Rimshot;
            if (lower.Contains("cross") || lower.Contains("sidestick") || lower.Contains("side_stick") || lower.Contains("stick_click"))
                return TechniqueType.CrossStick;
            if (lower.Contains("diddle") || lower.Contains("double_stroke"))
                return TechniqueType.DoubleStroke;
            if (lower.Contains("dead") || lower.Contains("mute"))
                return TechniqueType.DeadStroke;
            if (lower.Contains("shot") && lower.Contains("stick"))
                return TechniqueType.StickshotShot;

            // ========================
            // HI-HAT TECHNIQUES
            // ========================
            if (lower.Contains("bark"))
                return TechniqueType.HiHatBark;
            if (lower.Contains("splash") && lower.Contains("hat"))
                return TechniqueType.HiHatSplash;
            if (lower.Contains("chick") || (lower.Contains("pedal") && lower.Contains("hat")))
                return TechniqueType.HiHatChick;
            if (lower.Contains("half") && lower.Contains("open"))
                return TechniqueType.HiHatHalfOpen;
            if (lower.Contains("open") && lower.Contains("hat"))
                return TechniqueType.Normal; // Standard open, not special technique

            // ========================
            // CYMBAL TECHNIQUES
            // ========================
            if (lower.Contains("choke"))
                return TechniqueType.Choke;
            if (lower.Contains("bell"))
                return TechniqueType.BellHit;
            if (lower.Contains("scrape"))
                return TechniqueType.CymbalScrape;
            if (lower.Contains("swell") || lower.Contains("mallet"))
                return TechniqueType.MalletSwell;
            if (lower.Contains("crash") && lower.Contains("rid"))
                return TechniqueType.CrashRiding;
            if (lower.Contains("crash") && lower.Contains("build"))
                return TechniqueType.CrashBuild;

            // ========================
            // STACK/EFFECT
            // ========================
            if (lower.Contains("stack"))
                return TechniqueType.StackHit;

            // ========================
            // TOM TECHNIQUES
            // ========================
            if (lower.Contains("tom") && lower.Contains("rim"))
                return TechniqueType.TomRimshot;

            // ========================
            // BASS DRUM TECHNIQUES
            // ========================
            if (lower.Contains("double") && (lower.Contains("kick") || lower.Contains("bass")))
                return TechniqueType.DoublePedalBurst;
            if (lower.Contains("slide"))
                return TechniqueType.SlideDouble;
            if (lower.Contains("feather"))
                return TechniqueType.Feathering;

            // ========================
            // LINEAR DRUMMING
            // ========================
            if (lower.Contains("linear"))
                return TechniqueType.LinearPattern;

            // ========================
            // BRUSH TECHNIQUES
            // ========================
            if (lower.Contains("brush") && lower.Contains("sweep"))
                return TechniqueType.BrushSweep;
            if (lower.Contains("brush") && lower.Contains("tap"))
                return TechniqueType.BrushTap;

            // ========================
            // ACCENTS & DYNAMICS
            // ========================
            if (lower.Contains("accent") && lower.Contains("tap"))
                return TechniqueType.AccentTap;
            if (lower.Contains("accent"))
                return TechniqueType.Accent;

            return TechniqueType.Normal;
        }

        /// <summary>
        /// Get the previous difficulty hit object at a specific offset.
        /// </summary>
        public DifficultyHitObject? GetPrevious(int backIndex)
        {
            var current = this;
            for (int i = 0; i < backIndex && current != null; i++)
            {
                current = current.Previous;
            }
            return current?.Previous;
        }
    }
}
