using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// Base class for calculating a specific aspect of difficulty.
    /// Implements strain-based difficulty calculation following the osu! algorithm design.
    /// 
    /// The calculation works by:
    /// 1. Processing hit objects sequentially
    /// 2. Accumulating strain values that decay over time
    /// 3. Recording peak strains for each section
    /// 4. Computing a weighted sum of peaks for the final difficulty value
    /// </summary>
    public abstract class Skill
    {
        // ========================
        // Configuration
        // ========================

        /// <summary>
        /// The length of each strain section in milliseconds.
        /// Sections are used to capture peak difficulty values.
        /// </summary>
        protected virtual int SectionLength => 400;

        /// <summary>
        /// The weight by which each strain value decays when computing difficulty.
        /// Higher values mean lower peaks contribute more to final difficulty.
        /// </summary>
        protected virtual double DecayWeight => 0.9;

        /// <summary>
        /// Strain values are multiplied by this number.
        /// Used to balance different skills against each other.
        /// </summary>
        protected abstract double SkillMultiplier { get; }

        /// <summary>
        /// Determines how quickly strain decays for this skill.
        /// For example, 0.15 means strain decays to 15% of its value in one second.
        /// Lower values = faster decay (momentary difficulty)
        /// Higher values = slower decay (cumulative difficulty)
        /// </summary>
        protected abstract double StrainDecayBase { get; }

        // ========================
        // State
        // ========================

        /// <summary>
        /// The current accumulated strain level.
        /// </summary>
        protected double CurrentStrain { get; private set; }

        /// <summary>
        /// Peak strain values for each section.
        /// </summary>
        private readonly List<double> strainPeaks = new();

        /// <summary>
        /// Individual strain values for each hit object.
        /// Useful for detailed analysis and consistency calculations.
        /// </summary>
        protected readonly List<double> ObjectStrains = new();

        /// <summary>
        /// The current section's peak strain value.
        /// </summary>
        private double currentSectionPeak;

        /// <summary>
        /// The end time of the current section.
        /// </summary>
        private double currentSectionEnd;

        /// <summary>
        /// Count of objects processed.
        /// </summary>
        protected int ObjectCount { get; private set; }

        // ========================
        // Processing
        // ========================

        /// <summary>
        /// Process a hit object and update strain values.
        /// </summary>
        public void Process(DifficultyHitObject current)
        {
            // Initialize first section
            if (ObjectCount == 0)
            {
                currentSectionEnd = Math.Ceiling(current.StartTime / SectionLength) * SectionLength;
            }

            // Handle section transitions
            while (current.StartTime > currentSectionEnd)
            {
                SaveCurrentPeak();
                StartNewSectionFrom(currentSectionEnd, current);
                currentSectionEnd += SectionLength;
            }

            // Calculate strain for this object
            double strain = CalculateStrain(current);

            // Update section peak
            currentSectionPeak = Math.Max(strain, currentSectionPeak);

            // Store individual strain
            ObjectStrains.Add(strain);

            ObjectCount++;
        }

        /// <summary>
        /// Calculate the strain value for a hit object.
        /// Applies decay from previous strain and adds new strain.
        /// </summary>
        private double CalculateStrain(DifficultyHitObject current)
        {
            // Apply decay based on time since last object
            CurrentStrain *= StrainDecay(current.DeltaTime);

            // Add new strain from this object
            CurrentStrain += StrainValueOf(current) * SkillMultiplier;

            return CurrentStrain;
        }

        /// <summary>
        /// Calculate the initial strain for a new section.
        /// This preserves some strain from the previous section.
        /// </summary>
        protected virtual double CalculateInitialStrain(double time, DifficultyHitObject current)
        {
            if (current.Previous == null) return 0;
            return CurrentStrain * StrainDecay(time - current.Previous.StartTime);
        }

        /// <summary>
        /// Save the current section's peak strain.
        /// </summary>
        private void SaveCurrentPeak()
        {
            strainPeaks.Add(currentSectionPeak);
        }

        /// <summary>
        /// Start a new strain section.
        /// </summary>
        private void StartNewSectionFrom(double time, DifficultyHitObject current)
        {
            // Initialize new section with decayed strain from previous section
            currentSectionPeak = CalculateInitialStrain(time, current);
        }

        /// <summary>
        /// Calculate strain decay over a time period.
        /// </summary>
        protected double StrainDecay(double ms) => Math.Pow(StrainDecayBase, ms / 1000.0);

        // ========================
        // Abstract Methods
        // ========================

        /// <summary>
        /// Calculate the raw strain value for a hit object.
        /// This value is then multiplied by SkillMultiplier.
        /// </summary>
        protected abstract double StrainValueOf(DifficultyHitObject current);

        // ========================
        // Difficulty Calculation
        // ========================

        /// <summary>
        /// Get all section peak strains including the current section.
        /// </summary>
        public IEnumerable<double> GetCurrentStrainPeaks()
        {
            return strainPeaks.Append(currentSectionPeak);
        }

        /// <summary>
        /// Get individual object strains.
        /// </summary>
        public IEnumerable<double> GetObjectStrains() => ObjectStrains;

        /// <summary>
        /// Calculate the final difficulty value.
        /// Uses a weighted sum of peaks, with higher peaks weighted more.
        /// </summary>
        public virtual double DifficultyValue()
        {
            double difficulty = 0;
            double weight = 1;

            // Filter out zero peaks and sort descending
            var peaks = GetCurrentStrainPeaks()
                .Where(p => p > 0)
                .OrderByDescending(p => p);

            // Weighted sum of peaks
            foreach (double strain in peaks)
            {
                difficulty += strain * weight;
                weight *= DecayWeight;
            }

            return difficulty;
        }

        /// <summary>
        /// Calculate the number of strains weighted against the top strain.
        /// This measures consistency - how many notes are near the difficulty of the hardest.
        /// </summary>
        public virtual double CountTopWeightedStrains()
        {
            if (ObjectStrains.Count == 0) return 0;

            double difficultyValue = DifficultyValue();
            if (difficultyValue == 0) return ObjectStrains.Count;

            // What would the top strain be if all strains were identical?
            double consistentTopStrain = difficultyValue / 10;

            if (consistentTopStrain == 0) return ObjectStrains.Count;

            // Weighted sum based on how close each strain is to the consistent top
            return ObjectStrains.Sum(s => 1.1 / (1 + Math.Exp(-10 * (s / consistentTopStrain - 0.88))));
        }

        /// <summary>
        /// Get the peak strain value (highest single section).
        /// </summary>
        public double PeakStrain()
        {
            var peaks = GetCurrentStrainPeaks().ToList();
            return peaks.Count > 0 ? peaks.Max() : 0;
        }

        /// <summary>
        /// Get the average strain across all sections.
        /// </summary>
        public double AverageStrain()
        {
            var peaks = GetCurrentStrainPeaks().ToList();
            return peaks.Count > 0 ? peaks.Average() : 0;
        }

        /// <summary>
        /// Get the consistency factor (how consistent the difficulty is throughout).
        /// 1.0 = perfectly consistent, lower = more peaks/valleys.
        /// </summary>
        public double ConsistencyFactor()
        {
            if (ObjectStrains.Count == 0) return 0;

            var topStrains = ObjectStrains.OrderByDescending(s => s).Take(1 + ObjectStrains.Count / 20).ToList();
            if (topStrains.Count == 0) return 0;

            double topAverage = topStrains.Average();
            if (topAverage == 0) return 0;

            return ObjectStrains.Sum() / (topAverage * ObjectStrains.Count);
        }
    }

    /// <summary>
    /// Utility class for difficulty calculations.
    /// </summary>
    public static class DifficultyCalculationUtils
    {
        /// <summary>
        /// Calculate the Lp norm of multiple values.
        /// p=2 is Euclidean norm, higher p emphasizes the largest value more.
        /// </summary>
        public static double Norm(double p, params double[] values)
        {
            if (values.Length == 0) return 0;
            if (p <= 0) throw new ArgumentException("p must be positive");

            double sum = values.Sum(v => Math.Pow(Math.Abs(v), p));
            return Math.Pow(sum, 1.0 / p);
        }

        /// <summary>
        /// Linear interpolation.
        /// </summary>
        public static double Lerp(double a, double b, double t)
        {
            return a + (b - a) * Math.Clamp(t, 0, 1);
        }

        /// <summary>
        /// Reverse linear interpolation - find t given a value between a and b.
        /// </summary>
        public static double ReverseLerp(double value, double a, double b)
        {
            if (Math.Abs(b - a) < 0.0001) return 0;
            return Math.Clamp((value - a) / (b - a), 0, 1);
        }

        /// <summary>
        /// Smooth step function for gradual transitions.
        /// </summary>
        public static double SmoothStep(double edge0, double edge1, double x)
        {
            double t = Math.Clamp((x - edge0) / (edge1 - edge0), 0, 1);
            return t * t * (3 - 2 * t);
        }

        /// <summary>
        /// Calculate the power mean of values.
        /// p=1 is arithmetic mean, p=2 is quadratic mean, p→∞ approaches max.
        /// </summary>
        public static double PowerMean(double p, IEnumerable<double> values)
        {
            var list = values.ToList();
            if (list.Count == 0) return 0;

            if (p == 0)
            {
                // Geometric mean
                return Math.Pow(list.Aggregate(1.0, (a, b) => a * b), 1.0 / list.Count);
            }

            double sum = list.Sum(v => Math.Pow(v, p));
            return Math.Pow(sum / list.Count, 1.0 / p);
        }
    }
}
