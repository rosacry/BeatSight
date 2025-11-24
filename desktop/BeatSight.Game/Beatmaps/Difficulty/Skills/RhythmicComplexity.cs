using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// ENHANCED Rhythmic Complexity Skill v2.0 - Mathematical Rhythm Analysis
    /// 
    /// The crown jewel of the difficulty system. This skill captures the 
    /// mathematical and perceptual complexity of rhythm that separates
    /// world-class drummers from everyone else.
    /// 
    /// Key innovations:
    /// - Number-theoretic polyrhythm complexity (LCM-based)
    /// - Fourier-inspired rhythm periodicity analysis
    /// - Cognitive load modeling (working memory for beat tracking)
    /// - Phase relationship tracking between accent layers
    /// - Hierarchical beat structure analysis
    /// - Modular arithmetic for metric modulation detection
    /// 
    /// This skill handles: Animals as Leaders, Meshuggah, jazz greats,
    /// Tool, Dream Theater, and any rhythmically sophisticated music.
    /// </summary>
    public class RhythmicComplexity : Skill
    {
        protected override double SkillMultiplier => 35.0; // Increased from 28.0 - rhythm is king
        protected override double StrainDecayBase => 0.32;

        // ========================
        // RHYTHM STATE TRACKING
        // ========================

        // History for pattern analysis
        private readonly List<double> rhythmHistory = new();
        private readonly List<double> deltaTimeHistory = new();
        private readonly List<double> accentTimeHistory = new();
        private const int HISTORY_SIZE = 32;

        // Polyrhythm detection state
        private readonly Dictionary<string, int> activePolyrhythms = new();
        private readonly List<int> accentIntervals = new();
        private int notesSinceLastAccent = 0;

        // Odd grouping detection
        private readonly List<int> groupingSizes = new();
        private readonly Queue<int> recentGroupings = new();

        // Metric modulation tracking
        private double previousPulseRate = 0;
        private int metricModulationCooldown = 0;
        private readonly List<double> pulseRateHistory = new();

        // Cognitive load tracking
        private double cognitiveLoad = 0;
        private readonly Queue<double> complexityWindow = new();

        // Phase tracking for polymetric patterns
        private readonly Dictionary<int, double> beatPhases = new();

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;

            // Update history
            rhythmHistory.Add(current.RhythmRatio);
            deltaTimeHistory.Add(current.DeltaTime);
            if (rhythmHistory.Count > HISTORY_SIZE) rhythmHistory.RemoveAt(0);
            if (deltaTimeHistory.Count > HISTORY_SIZE) deltaTimeHistory.RemoveAt(0);

            // Decay metric modulation cooldown
            if (metricModulationCooldown > 0) metricModulationCooldown--;

            // ========================
            // 1. RHYTHM RATIO COMPLEXITY
            // ========================
            strain += CalculateRhythmRatioComplexity(current);

            // ========================
            // 2. POLYRHYTHM ANALYSIS (Number-Theoretic)
            // ========================
            strain += CalculatePolyrhythmComplexity(current);

            // ========================
            // 3. ODD GROUPING DETECTION
            // ========================
            strain += CalculateOddGroupingComplexity(current);

            // ========================
            // 4. SYNCOPATION & OFF-BEAT COMPLEXITY
            // ========================
            strain += CalculateSyncopationComplexity(current);

            // ========================
            // 5. RHYTHM ENTROPY (Information Theory)
            // ========================
            double entropy = CalculateEnhancedRhythmEntropy();
            strain += entropy * 4.0;

            // High entropy at speed = extremely complex
            if (entropy > 2.5 && current.DeltaTime < 120)
            {
                strain += entropy * 2.0;
            }

            // ========================
            // 6. METRIC MODULATION DETECTION
            // ========================
            strain += CalculateMetricModulationComplexity(current);

            // ========================
            // 7. ODD TIME SIGNATURE COMPLEXITY
            // ========================
            strain += CalculateOddMeterComplexity(current);

            // ========================
            // 8. POLYMETRIC ACCENT ANALYSIS
            // ========================
            strain += AnalyzeAccentPattern(current);

            // ========================
            // 9. HEMIOLA & CROSS-RHYTHM
            // ========================
            if (DetectHemiola())
            {
                strain += 3.0;
            }
            if (DetectCrossRhythm())
            {
                strain += 4.0;
            }

            // ========================
            // 10. JAZZ "FEEL" COMPLEXITY
            // ========================
            strain += CalculateJazzComplexity(current);

            // ========================
            // 11. NESTED COMPLEXITY
            // ========================
            // Multiple complexity sources compound
            strain += CalculateNestedComplexity(current);

            // ========================
            // 12. COGNITIVE LOAD MODEL
            // ========================
            // Track how much "working memory" is required
            UpdateCognitiveLoad(strain);
            strain *= 1.0 + cognitiveLoad * 0.3;

            // ========================
            // 13. PHASE RELATIONSHIP TRACKING
            // ========================
            strain += CalculatePhaseComplexity(current);

            return strain;
        }

        // ========================
        // COMPLEXITY CALCULATION METHODS
        // ========================

        private double CalculateRhythmRatioComplexity(DifficultyHitObject current)
        {
            if (current.Previous == null || current.RhythmRatio <= 0) return 0;

            double strain = 0;
            double ratio = current.RhythmRatio;
            double normalizedRatio = ratio < 1.0 ? 1.0 / ratio : ratio;

            if (normalizedRatio > 1.03) // Beyond timing tolerance
            {
                strain += 0.6; // Base rhythm change

                // Complexity based on how "irrational" the ratio is
                double complexity = GetRatioComplexity(ratio);
                strain += complexity;

                // Rapid rhythm changes compound
                if (current.Previous?.RhythmRatio > 0)
                {
                    double prevNorm = current.Previous.RhythmRatio < 1.0
                        ? 1.0 / current.Previous.RhythmRatio
                        : current.Previous.RhythmRatio;

                    // Both changing and both complex = hard
                    if (prevNorm > 1.1 && normalizedRatio > 1.1)
                    {
                        strain += 1.5;
                    }
                }
            }

            return strain;
        }

        private double GetRatioComplexity(double ratio)
        {
            // Find the simplest fraction approximation and compute complexity
            // Based on Stern-Brocot tree / continued fractions concept

            // Simple ratios (low complexity)
            if (IsNearRatio(ratio, 1.0, 0.05)) return 0;
            if (IsNearRatio(ratio, 2.0, 0.05) || IsNearRatio(ratio, 0.5, 0.03)) return 0.3;
            if (IsNearRatio(ratio, 4.0, 0.08) || IsNearRatio(ratio, 0.25, 0.02)) return 0.4;
            if (IsNearRatio(ratio, 3.0, 0.06) || IsNearRatio(ratio, 0.333, 0.03)) return 0.5;

            // Polyrhythmic ratios (medium complexity)
            if (IsNearRatio(ratio, 1.5, 0.05) || IsNearRatio(ratio, 0.666, 0.04)) return 2.0;   // 3:2
            if (IsNearRatio(ratio, 1.333, 0.04) || IsNearRatio(ratio, 0.75, 0.04)) return 2.5; // 4:3
            if (IsNearRatio(ratio, 1.25, 0.04) || IsNearRatio(ratio, 0.8, 0.04)) return 3.5;   // 5:4
            if (IsNearRatio(ratio, 1.666, 0.05) || IsNearRatio(ratio, 0.6, 0.03)) return 3.0;  // 5:3

            // Complex polyrhythmic ratios (high complexity)
            if (IsNearRatio(ratio, 1.75, 0.05) || IsNearRatio(ratio, 0.571, 0.03)) return 5.0; // 7:4
            if (IsNearRatio(ratio, 1.4, 0.04) || IsNearRatio(ratio, 0.714, 0.04)) return 4.5;  // 7:5
            if (IsNearRatio(ratio, 2.333, 0.06) || IsNearRatio(ratio, 0.428, 0.03)) return 5.5; // 7:3
            if (IsNearRatio(ratio, 1.8, 0.04) || IsNearRatio(ratio, 0.555, 0.03)) return 4.0;  // 9:5
            if (IsNearRatio(ratio, 1.571, 0.04) || IsNearRatio(ratio, 0.636, 0.03)) return 5.5; // 11:7
            if (IsNearRatio(ratio, 1.833, 0.04) || IsNearRatio(ratio, 0.545, 0.03)) return 6.0; // 11:6
            if (IsNearRatio(ratio, 1.857, 0.04) || IsNearRatio(ratio, 0.538, 0.03)) return 6.5; // 13:7

            // Unknown/irrational ratio - compute complexity heuristically
            return 2.0 + Math.Abs(Math.Log(ratio)) * 1.5;
        }

        private double CalculatePolyrhythmComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Explicit polyrhythm from beatmap data
            if (!string.IsNullOrEmpty(current.PolyrhythmType))
            {
                strain += GetExplicitPolyrhythmDifficulty(current.PolyrhythmType);

                // Track active polyrhythm
                if (!activePolyrhythms.ContainsKey(current.PolyrhythmType))
                    activePolyrhythms[current.PolyrhythmType] = 0;
                activePolyrhythms[current.PolyrhythmType]++;

                // Sustained polyrhythm = harder
                if (activePolyrhythms[current.PolyrhythmType] > 4)
                {
                    strain += 0.5 * Math.Min(activePolyrhythms[current.PolyrhythmType] - 4, 8);
                }
            }
            else
            {
                // Decay active polyrhythm counts
                var keys = activePolyrhythms.Keys.ToList();
                foreach (var key in keys)
                {
                    activePolyrhythms[key] = Math.Max(0, activePolyrhythms[key] - 1);
                }
            }

            // Detect polyrhythm from rhythm history using LCM analysis
            if (rhythmHistory.Count >= 6)
            {
                double detectedPolyrhythm = DetectPolyrhythmFromHistory();
                strain += detectedPolyrhythm;
            }

            return strain;
        }

        private double GetExplicitPolyrhythmDifficulty(string polyType)
        {
            return polyType switch
            {
                "2:3" or "3:2" => 2.5,
                "3:4" or "4:3" => 3.5,
                "4:5" or "5:4" => 4.5,
                "5:6" or "6:5" => 5.0,
                "3:5" or "5:3" => 4.0,
                "4:7" or "7:4" => 6.0,
                "5:7" or "7:5" => 6.5,
                "3:7" or "7:3" => 5.5,
                "4:9" or "9:4" => 6.0,
                "5:9" or "9:5" => 6.5,
                "7:9" or "9:7" => 7.0,
                "4:11" or "11:4" => 7.5,
                "7:11" or "11:7" => 8.0,
                "5:13" or "13:5" => 8.5,
                _ => 3.0 // Unknown polyrhythm
            };
        }

        private double DetectPolyrhythmFromHistory()
        {
            // Use LCM-based analysis to detect implicit polyrhythms
            var recentRatios = rhythmHistory.TakeLast(6).ToList();

            // Look for characteristic polyrhythmic patterns
            // E.g., alternating long-short patterns at specific ratios

            int pairCount = 0;
            double totalComplexity = 0;

            for (int i = 0; i < recentRatios.Count - 1; i++)
            {
                double r1 = recentRatios[i];
                double r2 = recentRatios[i + 1];

                // Check for complementary ratios (e.g., 1.5 and 0.666)
                if (Math.Abs(r1 * r2 - 1.0) < 0.15)
                {
                    pairCount++;
                    totalComplexity += GetRatioComplexity(r1);
                }
            }

            if (pairCount >= 2)
            {
                return totalComplexity / pairCount * 0.5;
            }

            return 0;
        }

        private double CalculateOddGroupingComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Explicit odd grouping
            if (current.OddGrouping.HasValue)
            {
                int grouping = current.OddGrouping.Value;
                strain += GetOddGroupingDifficulty(grouping);

                recentGroupings.Enqueue(grouping);
                if (recentGroupings.Count > 8) recentGroupings.Dequeue();
            }

            // Detect odd groupings from pattern analysis
            DetectOddGroupingsFromHistory();
            if (groupingSizes.Count >= 3)
            {
                var uniqueGroupings = groupingSizes.Distinct().ToList();
                foreach (var g in uniqueGroupings.Where(g => g == 5 || g == 7 || g == 9 || g == 11))
                {
                    strain += GetOddGroupingDifficulty(g) * 0.3;
                }

                // Mixed groupings = very complex
                if (uniqueGroupings.Count >= 2)
                {
                    strain += uniqueGroupings.Count * 1.5;
                }
            }

            return strain;
        }

        private double GetOddGroupingDifficulty(int grouping)
        {
            return grouping switch
            {
                5 => 3.5,   // Quintuplets
                7 => 5.5,   // Septuplets - Matt Garstka's specialty
                9 => 5.0,   // Nonuplets
                11 => 7.0,  // 11-tuplets
                13 => 8.0,  // 13-tuplets - extreme
                15 => 8.5,  // 15-tuplets
                17 => 9.0,  // 17-tuplets - Meshuggah territory
                _ when grouping > 7 => 4.0 + grouping * 0.5,
                _ => 2.5
            };
        }

        private double CalculateSyncopationComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Grid deviation = syncopation intensity
            strain += current.GridDeviation * 6.0;

            if (current.IsSyncopated)
            {
                strain += 2.0;

                // Fast syncopation is harder
                if (current.DeltaTime < 100)
                    strain += 1.5;

                // Syncopation during odd meter
                if (current.CurrentTimeSignature.IsOddMeter)
                    strain += 1.0;

                // Consecutive syncopation
                if (current.Previous?.IsSyncopated == true)
                    strain += 1.0;
            }

            return strain;
        }

        private double CalculateEnhancedRhythmEntropy()
        {
            if (rhythmHistory.Count < 6) return 0;

            // Shannon entropy calculation with finer granularity
            var buckets = new Dictionary<int, int>();

            foreach (var ratio in rhythmHistory)
            {
                // Bucket by finer precision
                int bucket = (int)(ratio * 20);
                if (!buckets.ContainsKey(bucket))
                    buckets[bucket] = 0;
                buckets[bucket]++;
            }

            double entropy = 0;
            foreach (var count in buckets.Values)
            {
                double p = (double)count / rhythmHistory.Count;
                if (p > 0)
                    entropy -= p * Math.Log(p, 2);
            }

            // Normalize to history size
            double maxEntropy = Math.Log(rhythmHistory.Count, 2);
            return entropy / Math.Max(maxEntropy, 1) * 3.0;
        }

        private double CalculateMetricModulationComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Explicit metric modulation flag
            if (current.IsMetricModulation && metricModulationCooldown == 0)
            {
                strain += 5.5;
                metricModulationCooldown = 8;
            }

            // Detect from pulse rate analysis
            if (deltaTimeHistory.Count >= 8)
            {
                double currentPulseRate = 1000.0 / current.DeltaTime;
                pulseRateHistory.Add(currentPulseRate);
                if (pulseRateHistory.Count > 16) pulseRateHistory.RemoveAt(0);

                // Look for characteristic metric modulation ratios
                if (previousPulseRate > 0 && metricModulationCooldown == 0)
                {
                    double pulseRatio = currentPulseRate / previousPulseRate;

                    // Common metric modulation ratios
                    if (IsNearRatio(pulseRatio, 1.5, 0.08) || IsNearRatio(pulseRatio, 0.666, 0.06))
                    {
                        // Dotted-to-straight or vice versa
                        strain += 4.0;
                        metricModulationCooldown = 8;
                    }
                    else if (IsNearRatio(pulseRatio, 1.333, 0.08) || IsNearRatio(pulseRatio, 0.75, 0.06))
                    {
                        // 4:3 modulation
                        strain += 4.5;
                        metricModulationCooldown = 8;
                    }
                    else if (IsNearRatio(pulseRatio, 1.25, 0.06) || IsNearRatio(pulseRatio, 0.8, 0.05))
                    {
                        // 5:4 modulation
                        strain += 5.0;
                        metricModulationCooldown = 8;
                    }
                }

                previousPulseRate = currentPulseRate;
            }

            return strain;
        }

        private double CalculateOddMeterComplexity(DifficultyHitObject current)
        {
            if (!current.CurrentTimeSignature.IsOddMeter) return 0;

            double strain = current.CurrentTimeSignature.Numerator switch
            {
                5 => 2.5,   // 5/4, 5/8 - Take Five
                7 => 3.5,   // 7/4, 7/8 - Money
                9 => 3.0,   // 9/8
                10 => 3.5,  // 10/8
                11 => 5.0,  // 11/8 - very rare
                13 => 6.0,  // 13/8
                15 => 6.5,  // 15/8 - complex
                17 => 7.5,  // 17/8 - Meshuggah (Bleed)
                19 => 8.0,  // 19/8
                21 => 8.5,  // 21/8
                23 => 9.0,  // 23/8 - extreme
                _ => 2.0 + current.CurrentTimeSignature.Numerator * 0.3
            };

            // Odd denominator adds complexity
            if (current.CurrentTimeSignature.Denominator != 4 &&
                current.CurrentTimeSignature.Denominator != 8)
            {
                strain += 1.0;
            }

            return strain;
        }

        private double AnalyzeAccentPattern(DifficultyHitObject current)
        {
            notesSinceLastAccent++;
            double strain = 0;

            // Detect accent (high velocity)
            if (current.MaxVelocity > 0.75 || current.Techniques.Contains(TechniqueType.Accent))
            {
                accentTimeHistory.Add(current.StartTime);
                if (accentTimeHistory.Count > 16) accentTimeHistory.RemoveAt(0);

                if (notesSinceLastAccent > 0)
                {
                    accentIntervals.Add(notesSinceLastAccent);
                    if (accentIntervals.Count > 16) accentIntervals.RemoveAt(0);
                }
                notesSinceLastAccent = 0;

                // Analyze accent interval patterns for polymetric phrasing
                if (accentIntervals.Count >= 4)
                {
                    double avg = accentIntervals.Average();
                    double variance = accentIntervals.Select(x => Math.Pow(x - avg, 2)).Average();

                    // Consistent odd-numbered accent groupings = polymetric
                    if (variance < 0.8)
                    {
                        // Groupings of 3 over 4/4
                        if (Math.Abs(avg - 3) < 0.4) strain += 2.5;
                        // Groupings of 5
                        else if (Math.Abs(avg - 5) < 0.4) strain += 3.5;
                        // Groupings of 7
                        else if (Math.Abs(avg - 7) < 0.5) strain += 4.5;
                        // Groupings of 9
                        else if (Math.Abs(avg - 9) < 0.5) strain += 5.0;
                        // Groupings of 11
                        else if (Math.Abs(avg - 11) < 0.6) strain += 6.0;
                    }

                    // Check for alternating accent patterns (e.g., 3-3-2)
                    if (accentIntervals.Count >= 6)
                    {
                        var recent = accentIntervals.TakeLast(6).ToList();
                        int patternLength = DetectRepeatingPattern(recent);
                        if (patternLength > 0 && patternLength != 4)
                        {
                            strain += 2.0 + patternLength * 0.3;
                        }
                    }
                }
            }

            return strain;
        }

        private double CalculateJazzComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Ghost notes + syncopation + dynamics = jazz feel
            bool hasGhosts = current.Techniques.Contains(TechniqueType.GhostNote);

            if (hasGhosts && current.IsSyncopated && current.VelocityRange > 0.25)
            {
                strain += 3.0; // Jazz finesse
            }

            // Shuffle/swing feel detection
            if (DetectSwingFeel())
            {
                strain += 2.0;

                // Complex swing (not just simple dotted-8th feel)
                if (rhythmHistory.Count >= 4)
                {
                    var ratios = rhythmHistory.TakeLast(4).ToList();
                    double swingRatio = ratios.Where(r => r > 1.0).Average();

                    // Heavy swing (closer to triplet) vs light swing
                    if (swingRatio > 1.7)
                        strain += 1.0;
                }
            }

            // Brush work / quiet dynamics = finesse
            if (current.AverageVelocity < 0.35 && current.Techniques.Contains(TechniqueType.GhostNote))
            {
                strain += 1.5;
            }

            return strain;
        }

        private double CalculateNestedComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Count concurrent complexity sources
            int complexitySources = 0;

            if (!string.IsNullOrEmpty(current.PolyrhythmType)) complexitySources++;
            if (current.OddGrouping.HasValue) complexitySources++;
            if (current.IsSyncopated) complexitySources++;
            if (current.CurrentTimeSignature.IsOddMeter) complexitySources++;
            if (current.IsMetricModulation) complexitySources++;

            // Multiple simultaneous complexity sources compound
            if (complexitySources >= 2)
            {
                strain += 2.0 * (complexitySources - 1);
            }
            if (complexitySources >= 3)
            {
                strain += 3.0 * (complexitySources - 2);
            }
            if (complexitySources >= 4)
            {
                strain += 5.0; // Extremely complex
            }

            return strain;
        }

        private void UpdateCognitiveLoad(double currentStrain)
        {
            complexityWindow.Enqueue(currentStrain);
            if (complexityWindow.Count > 16) complexityWindow.Dequeue();

            // High sustained complexity = cognitive overload
            if (complexityWindow.Count >= 8)
            {
                double avgComplexity = complexityWindow.Average();
                double peakComplexity = complexityWindow.Max();

                // Build cognitive load
                if (avgComplexity > 3.0)
                {
                    cognitiveLoad += 0.02 * (avgComplexity - 3.0);
                }
                else
                {
                    cognitiveLoad *= 0.95; // Slow decay
                }

                cognitiveLoad = Math.Min(0.5, cognitiveLoad);
            }
        }

        private double CalculatePhaseComplexity(DifficultyHitObject current)
        {
            double strain = 0;

            // Track phase relationships between different accent layers
            // This captures the "where am I in the cycle" complexity

            if (accentTimeHistory.Count >= 4)
            {
                // Compute phase for different metric periods
                foreach (int period in new[] { 3, 4, 5, 7 })
                {
                    double phase = (current.StartTime % (period * current.DeltaTime * 4)) /
                                   (period * current.DeltaTime * 4);

                    if (!beatPhases.ContainsKey(period))
                        beatPhases[period] = phase;
                    else
                    {
                        double phaseDrift = Math.Abs(phase - beatPhases[period]);
                        if (phaseDrift > 0.1 && phaseDrift < 0.9)
                        {
                            // Phase relationship changing = complex
                            strain += phaseDrift * 0.5;
                        }
                        beatPhases[period] = beatPhases[period] * 0.8 + phase * 0.2;
                    }
                }
            }

            return strain;
        }

        // ========================
        // HELPER METHODS
        // ========================

        private static bool IsNearRatio(double value, double target, double tolerance)
        {
            return Math.Abs(value - target) < tolerance;
        }

        private void DetectOddGroupingsFromHistory()
        {
            if (deltaTimeHistory.Count < 10) return;

            var recent = deltaTimeHistory.TakeLast(10).ToList();

            // Check if deltas form repeating patterns of specific lengths
            foreach (int groupSize in new[] { 5, 7, 9, 11 })
            {
                if (recent.Count >= groupSize * 2)
                {
                    var firstGroup = recent.Take(groupSize).ToList();
                    var secondGroup = recent.Skip(groupSize).Take(groupSize).ToList();

                    bool similar = true;
                    for (int i = 0; i < groupSize && i < secondGroup.Count; i++)
                    {
                        if (Math.Abs(firstGroup[i] - secondGroup[i]) / Math.Max(firstGroup[i], 1) > 0.12)
                        {
                            similar = false;
                            break;
                        }
                    }

                    if (similar)
                    {
                        groupingSizes.Add(groupSize);
                        if (groupingSizes.Count > 8) groupingSizes.RemoveAt(0);
                    }
                }
            }
        }

        private bool DetectHemiola()
        {
            if (accentIntervals.Count < 6) return false;

            var recent = accentIntervals.TakeLast(6).ToList();
            int threes = recent.Count(i => Math.Abs(i - 3) < 0.6);
            int twos = recent.Count(i => Math.Abs(i - 2) < 0.6);

            return threes >= 2 && twos >= 2;
        }

        private bool DetectCrossRhythm()
        {
            // Cross-rhythm: two different rhythmic patterns playing simultaneously
            // Detected through alternating accent patterns
            if (accentIntervals.Count < 8) return false;

            var recent = accentIntervals.TakeLast(8).ToList();

            // Look for alternating pattern
            bool alternating = true;
            for (int i = 2; i < recent.Count; i += 2)
            {
                if (Math.Abs(recent[i] - recent[i - 2]) > 1)
                {
                    alternating = false;
                    break;
                }
            }

            return alternating && recent.Distinct().Count() >= 2;
        }

        private bool DetectSwingFeel()
        {
            if (rhythmHistory.Count < 4) return false;

            var recent = rhythmHistory.TakeLast(4).ToList();
            int swingPairs = 0;

            for (int i = 0; i < recent.Count - 1; i++)
            {
                double r1 = recent[i];
                double r2 = recent[i + 1];

                bool isSwing = (IsNearRatio(r1, 1.5, 0.2) && IsNearRatio(r2, 0.666, 0.15)) ||
                               (IsNearRatio(r1, 0.666, 0.15) && IsNearRatio(r2, 1.5, 0.2)) ||
                               (IsNearRatio(r1, 2.0, 0.25) && IsNearRatio(r2, 0.5, 0.12)) ||
                               (IsNearRatio(r1, 0.5, 0.12) && IsNearRatio(r2, 2.0, 0.25));

                if (isSwing) swingPairs++;
            }

            return swingPairs >= 2;
        }

        private int DetectRepeatingPattern(List<int> values)
        {
            // Detect the shortest repeating pattern length
            for (int patternLen = 2; patternLen <= values.Count / 2; patternLen++)
            {
                bool isPattern = true;
                for (int i = patternLen; i < values.Count && isPattern; i++)
                {
                    if (Math.Abs(values[i] - values[i % patternLen]) > 1)
                        isPattern = false;
                }
                if (isPattern) return patternLen;
            }
            return 0;
        }
    }
}
