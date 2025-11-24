using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps.Difficulty;

namespace BeatSight.Game.Beatmaps.Difficulty.Analysis
{
    /// <summary>
    /// COGNITIVE LOAD ANALYZER FOR DRUMMING DIFFICULTY
    /// 
    /// This analyzer models the cognitive (mental) demands of drumming patterns,
    /// separate from the physical difficulty. Based on cognitive psychology research
    /// on working memory capacity and attention.
    /// 
    /// THEORETICAL FOUNDATION:
    /// 
    /// 1. WORKING MEMORY MODEL (Baddeley)
    ///    - Phonological loop: tracking internal "count" and subdivisions
    ///    - Visuospatial sketchpad: mental map of the kit
    ///    - Central executive: coordinating multiple limb patterns
    ///    - Episodic buffer: integrating current beat with song structure
    /// 
    /// 2. MILLER'S LAW (7±2 CHUNKS)
    ///    Working memory can hold ~7 chunks of information. Complex patterns
    ///    that exceed this require more cognitive processing.
    /// 
    /// 3. ATTENTION SWITCHING COSTS
    ///    Every switch between different cognitive tasks has a time cost.
    ///    Drumming requires rapid switching between limb coordination,
    ///    counting, dynamics, and reading ahead.
    /// 
    /// 4. COGNITIVE LOAD THEORY (Sweller)
    ///    - Intrinsic load: inherent complexity of the pattern
    ///    - Extraneous load: difficulty from presentation/notation
    ///    - Germane load: effort spent on skill acquisition
    /// </summary>
    public class CognitiveLoadAnalyzer
    {
        // Configuration
        private const int WORKING_MEMORY_CAPACITY = 7;
        private const double SWITCH_COST_MS = 50;
        private const int ANALYSIS_WINDOW = 16;

        // State tracking
        private readonly Dictionary<string, int> patternFamiliarity = new();
        private readonly List<double> densityHistory = new();
        private readonly List<int> streamCountHistory = new();

        private int chunksAnalyzed = 0;

        /// <summary>
        /// Analyze cognitive load for a hit object in context.
        /// </summary>
        public CognitiveLoadResult Analyze(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            var result = new CognitiveLoadResult();

            // 1. Chunk Analysis - how many "chunks" is this pattern?
            result.ChunkCount = EstimateChunkCount(current, context);
            result.ChunkOverflow = Math.Max(0, result.ChunkCount - WORKING_MEMORY_CAPACITY);

            // 2. Stream Count - how many independent cognitive streams?
            result.SimultaneousStreams = CountSimultaneousStreams(current, context);
            streamCountHistory.Add(result.SimultaneousStreams);
            if (streamCountHistory.Count > 32) streamCountHistory.RemoveAt(0);

            // 3. Attention Switching Load
            result.AttentionSwitches = CountAttentionSwitches(current, context);
            result.SwitchingCost = result.AttentionSwitches * SWITCH_COST_MS;

            // 4. Information Density
            result.InformationDensity = CalculateInformationDensity(current, context);
            densityHistory.Add(result.InformationDensity);
            if (densityHistory.Count > 64) densityHistory.RemoveAt(0);

            // 5. Pattern Novelty - familiar patterns are less load
            result.PatternNovelty = CalculatePatternNovelty(current, context);

            // 6. Look-Ahead Requirements
            result.LookAheadBeats = EstimateLookAheadRequirement(context);

            // 7. Meter Tracking Load
            result.MeterTrackingLoad = CalculateMeterTrackingLoad(current, context);

            // 8. Dynamic Variation Load
            result.DynamicVariationLoad = CalculateDynamicVariationLoad(current, context);

            // 9. Cumulative Fatigue Factor
            result.CognitiveFatigue = CalculateCognitiveFatigue();

            // Calculate total cognitive load
            result.TotalCognitiveLoad = CalculateTotalLoad(result);

            // Update tracking
            UpdateTracking(current, context);

            return result;
        }

        /// <summary>
        /// Estimate how many cognitive "chunks" this pattern requires.
        /// Uses NoteCount and LimbCount from DifficultyHitObject.
        /// </summary>
        private int EstimateChunkCount(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            int chunks = 0;

            // Each unique rhythmic grouping is a chunk
            var recentRhythms = context
                .TakeLast(8)
                .Select(h => QuantizeRhythm(h.RhythmRatio))
                .Distinct()
                .Count();

            chunks += recentRhythms;

            // Each simultaneous note combination is a chunk (use NoteCount)
            chunks += Math.Max(1, current.NoteCount);

            // Technique switches add chunks
            if (current.Techniques.Any(t => t != TechniqueType.Normal) && context.Count > 0)
            {
                var lastTechniques = context.Last().Techniques;
                if (!current.Techniques.SequenceEqual(lastTechniques))
                    chunks++;
            }

            // Time signature tracking is a chunk (use TimeSignature.IsOddMeter)
            if (current.TimeSignature.IsOddMeter)
                chunks += 2;

            return chunks;
        }

        /// <summary>
        /// Count how many independent cognitive streams are active.
        /// Uses LimbCount and DrumTypes from DifficultyHitObject.
        /// </summary>
        private int CountSimultaneousStreams(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            // Start with 1 for primary pattern
            int streams = 1;

            // Hi-hat/ride pattern is its own stream
            if (current.DrumTypes.Contains(DrumType.HiHat) ||
                current.DrumTypes.Contains(DrumType.Ride))
                streams++;

            // Kick independence
            if (current.DrumTypes.Contains(DrumType.Kick) && current.NoteCount > 1)
                streams++;

            // Snare independence
            if (current.DrumTypes.Contains(DrumType.Snare) && current.NoteCount > 1)
                streams++;

            // If we detect polyrhythm, that's another stream
            if (Math.Abs(current.RhythmRatio - 1.0) > 0.15 &&
                Math.Abs(current.RhythmRatio - 0.5) > 0.1 &&
                Math.Abs(current.RhythmRatio - 2.0) > 0.2)
            {
                streams++;
            }

            return Math.Min(streams, 4); // Cap at 4-way independence
        }

        /// <summary>
        /// Count attention switches required in this section.
        /// </summary>
        private int CountAttentionSwitches(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            if (context.Count == 0) return 0;

            int switches = 0;
            var prev = context.Last();

            // Limb switch (use HasLeftHand/HasRightHand etc.)
            if (GetPrimaryLimb(current) != GetPrimaryLimb(prev))
                switches++;

            // Zone switch (hi-hat zone vs snare zone vs toms)
            if (GetKitZone(current) != GetKitZone(prev))
                switches++;

            // Technique switch
            var currentTechnique = current.Techniques.FirstOrDefault(t => t != TechniqueType.Normal);
            var prevTechnique = prev.Techniques.FirstOrDefault(t => t != TechniqueType.Normal);
            if (currentTechnique != prevTechnique && currentTechnique != TechniqueType.Normal)
                switches++;

            // Velocity/dynamic switch (use AverageVelocity)
            if (Math.Abs(current.AverageVelocity - prev.AverageVelocity) > 30)
                switches++;

            return switches;
        }

        /// <summary>
        /// Calculate information density (bits per second approximation).
        /// </summary>
        private double CalculateInformationDensity(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            if (current.DeltaTime <= 0) return 0;

            double bitsPerNote = 0;

            // Positional information (which drum) - log2 of choices
            bitsPerNote += Math.Log2(8); // 8 drum positions

            // Velocity information
            bitsPerNote += Math.Log2(4); // ~4 dynamic levels practically

            // Simultaneous notes multiply information (use NoteCount)
            bitsPerNote *= Math.Max(1, current.NoteCount);

            // Technique adds information
            if (current.Techniques.Any(t => t != TechniqueType.Normal))
                bitsPerNote += 2;

            // Convert to bits per second
            double notesPerSecond = 1000.0 / current.DeltaTime;
            return bitsPerNote * notesPerSecond;
        }

        /// <summary>
        /// Calculate how novel/unfamiliar this pattern is.
        /// </summary>
        private double CalculatePatternNovelty(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            string sig = CreatePatternSignature(current, context);

            if (patternFamiliarity.TryGetValue(sig, out int count))
            {
                return 1.0 / (1.0 + count * 0.1);
            }

            return 1.0;
        }

        /// <summary>
        /// Estimate how many beats ahead the drummer needs to read.
        /// </summary>
        private int EstimateLookAheadRequirement(IReadOnlyList<DifficultyHitObject> context)
        {
            if (context.Count < 4) return 1;

            int complexity = 0;

            foreach (var hit in context.TakeLast(8))
            {
                if (hit.NoteCount > 2) complexity++;
                if (hit.Techniques.Any(t => t != TechniqueType.Normal)) complexity++;
                if (hit.TimeSignature.IsOddMeter) complexity += 2;
            }

            return Math.Min(8, 1 + complexity / 2);
        }

        /// <summary>
        /// Calculate cognitive load from meter tracking.
        /// </summary>
        private double CalculateMeterTrackingLoad(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            double load = 0;

            // Odd time signatures require active counting
            if (current.TimeSignature.IsOddMeter)
                load += 3.0;

            // Metric modulation is very demanding (use CurrentBpm)
            if (context.Count > 1)
            {
                var prev = context.Last();
                if (Math.Abs(current.CurrentBpm - prev.CurrentBpm) > 5)
                    load += 2.0;
            }

            // Polyrhythms require tracking multiple meters
            if (Math.Abs(current.RhythmRatio - 1.0) > 0.1)
            {
                load += EstimateRatioComplexity(current.RhythmRatio) * 0.5;
            }

            return load;
        }

        /// <summary>
        /// Calculate load from dynamic variations.
        /// </summary>
        private double CalculateDynamicVariationLoad(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            if (context.Count < 4) return 0;

            var velocities = context.TakeLast(8).Select(h => h.AverageVelocity).ToList();
            velocities.Add(current.AverageVelocity);

            double mean = velocities.Average();
            double variance = velocities.Select(v => Math.Pow(v - mean, 2)).Average();
            double stdDev = Math.Sqrt(variance);

            return Math.Min(5.0, stdDev / 25.0);
        }

        /// <summary>
        /// Calculate cumulative cognitive fatigue.
        /// </summary>
        private double CalculateCognitiveFatigue()
        {
            if (chunksAnalyzed < 32) return 0;

            double avgDensity = densityHistory.Count > 0 ? densityHistory.Average() : 0;
            double avgStreams = streamCountHistory.Count > 0 ? streamCountHistory.Average() : 1;

            double fatigueFactor = (avgDensity / 50.0) * (avgStreams / 2.0);
            double durationFactor = Math.Min(2.0, chunksAnalyzed / 200.0);

            return fatigueFactor * durationFactor;
        }

        /// <summary>
        /// Calculate total cognitive load score.
        /// </summary>
        private double CalculateTotalLoad(CognitiveLoadResult result)
        {
            double total = 0;

            total += result.ChunkOverflow * 3.0;
            total += (result.SimultaneousStreams - 1) * 2.0;
            total += result.AttentionSwitches * 0.5;
            total += Math.Min(5.0, result.InformationDensity / 30.0);
            total += result.PatternNovelty * 2.0;
            total += (result.LookAheadBeats - 1) * 0.5;
            total += result.MeterTrackingLoad;
            total += result.DynamicVariationLoad;
            total *= (1.0 + result.CognitiveFatigue * 0.3);

            return total;
        }

        /// <summary>
        /// Update internal tracking after analysis.
        /// </summary>
        private void UpdateTracking(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            chunksAnalyzed++;

            string sig = CreatePatternSignature(current, context);
            if (!patternFamiliarity.ContainsKey(sig))
                patternFamiliarity[sig] = 0;
            patternFamiliarity[sig]++;

            if (patternFamiliarity.Count > 500)
            {
                var toRemove = patternFamiliarity
                    .OrderBy(kvp => kvp.Value)
                    .Take(100)
                    .Select(kvp => kvp.Key)
                    .ToList();

                foreach (var key in toRemove)
                    patternFamiliarity.Remove(key);
            }
        }

        // Helper methods
        private string CreatePatternSignature(DifficultyHitObject current, IReadOnlyList<DifficultyHitObject> context)
        {
            int rhythmBucket = (int)(QuantizeRhythm(current.RhythmRatio) * 10);
            int zone = GetKitZone(current);
            int simul = Math.Min(4, current.NoteCount);

            return $"{rhythmBucket}_{zone}_{simul}";
        }

        private double QuantizeRhythm(double ratio)
        {
            double[] common = { 0.25, 0.333, 0.5, 0.667, 0.75, 1.0, 1.333, 1.5, 2.0 };
            return common.OrderBy(c => Math.Abs(c - ratio)).First();
        }

        private string GetPrimaryLimb(DifficultyHitObject hit)
        {
            if (hit.HasRightFoot) return "RightFoot";
            if (hit.HasLeftHand && hit.DrumTypes.Contains(DrumType.Snare)) return "LeftHand";
            if (hit.HasRightHand) return "RightHand";
            if (hit.HasLeftFoot) return "LeftFoot";
            return "Unknown";
        }

        private int GetKitZone(DifficultyHitObject hit)
        {
            // Zone 0: Hi-hat side (left)
            // Zone 1: Snare/center
            // Zone 2: Toms
            // Zone 3: Cymbal/right
            // Zone 4: Kick
            if (hit.DrumTypes.Contains(DrumType.Kick)) return 4;
            if (hit.DrumTypes.Contains(DrumType.HiHat)) return 0;
            if (hit.DrumTypes.Contains(DrumType.Snare)) return 1;
            if (hit.DrumTypes.Any(d => d == DrumType.Crash || d == DrumType.Ride || d == DrumType.China)) return 3;
            if (hit.DrumTypes.Any(d => d == DrumType.Tom || d == DrumType.TomHigh || d == DrumType.TomMid || d == DrumType.TomLow)) return 2;
            return 1;
        }

        private double EstimateRatioComplexity(double ratio)
        {
            if (Math.Abs(ratio - 1.0) < 0.05) return 0;
            if (Math.Abs(ratio - 0.5) < 0.05 || Math.Abs(ratio - 2.0) < 0.1) return 0.5;
            if (Math.Abs(ratio - 0.667) < 0.05 || Math.Abs(ratio - 1.5) < 0.05) return 1.5;
            if (Math.Abs(ratio - 0.75) < 0.05 || Math.Abs(ratio - 1.333) < 0.05) return 2.0;

            return 3.0 + Math.Abs(Math.Log(ratio)) * 2.0;
        }
    }

    /// <summary>
    /// Results from cognitive load analysis.
    /// </summary>
    public class CognitiveLoadResult
    {
        public int ChunkCount { get; set; }
        public int ChunkOverflow { get; set; }
        public int SimultaneousStreams { get; set; }
        public int AttentionSwitches { get; set; }
        public double SwitchingCost { get; set; }
        public double InformationDensity { get; set; }
        public double PatternNovelty { get; set; }
        public int LookAheadBeats { get; set; }
        public double MeterTrackingLoad { get; set; }
        public double DynamicVariationLoad { get; set; }
        public double CognitiveFatigue { get; set; }
        public double TotalCognitiveLoad { get; set; }

        public string LoadCategory => TotalCognitiveLoad switch
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
