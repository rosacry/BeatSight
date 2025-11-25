using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps.Difficulty.Skills;
using BeatSight.Game.Beatmaps.Difficulty.Analysis;

namespace BeatSight.Game.Beatmaps.Difficulty
{
    /// <summary>
    /// ╔══════════════════════════════════════════════════════════════════════════════╗
    /// ║           REAL-TIME STAR RATING TRACKER v1.0                                 ║
    /// ╠══════════════════════════════════════════════════════════════════════════════╣
    /// ║                                                                              ║
    /// ║  Revolutionary feature for BeatSight: Live star rating that updates         ║
    /// ║  during beatmap playback, showing users the instantaneous difficulty        ║
    /// ║  of what they're playing in real-time.                                      ║
    /// ║                                                                              ║
    /// ║  KEY FEATURES:                                                               ║
    /// ║                                                                              ║
    /// ║  1. INCREMENTAL STAR RATING                                                  ║
    /// ║     The star rating accumulates as the song progresses, reaching its         ║
    /// ║     final value at either the end of the song OR the hardest section.       ║
    /// ║                                                                              ║
    /// ║  2. DIFFICULTY GRAPH                                                         ║
    /// ║     Users can see a visual representation of difficulty over time,           ║
    /// ║     identifying the hardest parts of the song before they arrive.           ║
    /// ║                                                                              ║
    /// ║  3. PRECISION TO HUNDREDTHS                                                  ║
    /// ║     Star rating is displayed as X.XX (e.g., 5.73★) for fine granularity.   ║
    /// ║                                                                              ║
    /// ║  4. PEAK DETECTION                                                           ║
    /// ║     Identifies and highlights the absolute peak difficulty moment.           ║
    /// ║                                                                              ║
    /// ║  5. SKILL BREAKDOWN IN REAL-TIME                                             ║
    /// ║     Shows which skills are currently being challenged (speed, rhythm, etc.) ║
    /// ║                                                                              ║
    /// ║  INNOVATION: Unlike osu! which only shows final star rating, BeatSight      ║
    /// ║  shows the rating live as it builds, giving users immediate feedback        ║
    /// ║  about the difficulty of each section they're playing.                       ║
    /// ║                                                                              ║
    /// ╚══════════════════════════════════════════════════════════════════════════════╝
    /// </summary>
    public class RealTimeStarRating
    {
        /// <summary>
        /// Algorithm version for cache invalidation.
        /// </summary>
        public const int ALGORITHM_VERSION = DifficultyCalculator.ALGORITHM_VERSION;

        private readonly Beatmap beatmap;
        private readonly double clockRate;

        // Pre-calculated timed attributes
        private List<TimedDifficultyAttributes> timedAttributes = new();

        // Current state during playback
        private int currentIndex = 0;
        private double currentStarRating = 0;
        private double peakStarRating = 0;
        private double peakTime = 0;
        private readonly Dictionary<string, double> currentSkillRatings = new();

        // Smoothing for display
        private double displayedStarRating = 0;
        private const double RATING_SMOOTHING_FACTOR = 0.15;

        /// <summary>
        /// Event fired when the star rating updates.
        /// </summary>
        public event Action<RealTimeRatingUpdate>? OnRatingUpdate;

        /// <summary>
        /// Event fired when a new peak difficulty is reached.
        /// </summary>
        public event Action<PeakDifficultyEvent>? OnPeakReached;

        /// <summary>
        /// Peak star rating in the entire beatmap.
        /// </summary>
        public double PeakStarRating => peakStarRating;

        /// <summary>
        /// Time at which peak difficulty occurs (in milliseconds).
        /// </summary>
        public double PeakTime => peakTime;

        /// <summary>
        /// Current smoothed star rating for display.
        /// </summary>
        public double CurrentDisplayedRating => displayedStarRating;

        public RealTimeStarRating(Beatmap beatmap, double clockRate = 1.0)
        {
            this.beatmap = beatmap;
            this.clockRate = clockRate;
        }

        /// <summary>
        /// Pre-calculate all timed difficulty attributes for the beatmap.
        /// Call this before playback begins.
        /// </summary>
        public void Initialize()
        {
            var calculator = new DifficultyCalculator(beatmap, clockRate);
            timedAttributes = calculator.CalculateTimed();

            // Find peak
            if (timedAttributes.Count > 0)
            {
                var peak = timedAttributes.MaxBy(t => t.StarRating);
                if (peak != null)
                {
                    peakStarRating = peak.StarRating;
                    peakTime = peak.Time;
                }
            }

            // Reset state
            currentIndex = 0;
            currentStarRating = 0;
            displayedStarRating = 0;
            currentSkillRatings.Clear();
        }

        /// <summary>
        /// Update the real-time rating based on current playback time.
        /// Call this every frame or at regular intervals during playback.
        /// </summary>
        /// <param name="currentTime">Current playback time in milliseconds.</param>
        /// <returns>The current real-time rating update.</returns>
        public RealTimeRatingUpdate Update(double currentTime)
        {
            if (timedAttributes.Count == 0)
            {
                return new RealTimeRatingUpdate
                {
                    Time = currentTime,
                    CurrentStarRating = 0,
                    DisplayedStarRating = 0,
                    PeakStarRating = 0,
                    PeakTime = 0,
                    Progress = 0,
                    IsAtPeak = false
                };
            }

            // Find the appropriate timed attribute for current time
            while (currentIndex < timedAttributes.Count - 1 &&
                   timedAttributes[currentIndex + 1].Time <= currentTime)
            {
                currentIndex++;
            }

            var currentAttr = timedAttributes[currentIndex];
            currentStarRating = currentAttr.StarRating;

            // Smooth the displayed rating for nice visual transitions
            displayedStarRating = displayedStarRating +
                (currentStarRating - displayedStarRating) * RATING_SMOOTHING_FACTOR;

            // Update skill ratings
            UpdateSkillRatings(currentAttr);

            // Calculate progress
            double totalDuration = timedAttributes[^1].Time - timedAttributes[0].Time;
            double elapsed = currentTime - timedAttributes[0].Time;
            double progress = totalDuration > 0 ? Math.Clamp(elapsed / totalDuration, 0, 1) : 0;

            // Check if we're at the peak
            bool isAtPeak = Math.Abs(currentTime - peakTime) < 1000;

            var update = new RealTimeRatingUpdate
            {
                Time = currentTime,
                CurrentStarRating = Math.Round(currentStarRating * 100) / 100,
                DisplayedStarRating = Math.Round(displayedStarRating * 100) / 100,
                PeakStarRating = Math.Round(peakStarRating * 100) / 100,
                PeakTime = peakTime,
                Progress = progress,
                IsAtPeak = isAtPeak,
                SpeedRating = currentAttr.SpeedRating,
                CoordinationRating = currentAttr.CoordinationRating,
                RhythmRating = currentAttr.RhythmicComplexityRating,
                TechniqueRating = currentAttr.TechniqueRating,
                StaminaRating = currentAttr.StaminaRating,
                InstantaneousDifficulty = currentAttr.InstantaneousDifficulty,
                DominantSkill = GetDominantSkill(currentAttr)
            };

            OnRatingUpdate?.Invoke(update);

            // Fire peak event if we just reached it
            if (isAtPeak && currentIndex > 0 &&
                Math.Abs(timedAttributes[currentIndex - 1].StarRating - peakStarRating) > 0.1)
            {
                OnPeakReached?.Invoke(new PeakDifficultyEvent
                {
                    PeakStarRating = peakStarRating,
                    PeakTime = peakTime,
                    DominantSkills = GetTopSkills(currentAttr, 3)
                });
            }

            return update;
        }

        /// <summary>
        /// Get the difficulty at a specific time without affecting playback state.
        /// </summary>
        public double GetDifficultyAtTime(double time)
        {
            if (timedAttributes.Count == 0) return 0;

            var attr = timedAttributes.LastOrDefault(t => t.Time <= time);
            return attr?.StarRating ?? 0;
        }

        /// <summary>
        /// Get the complete difficulty curve for visualization.
        /// </summary>
        public IReadOnlyList<TimedDifficultyAttributes> GetDifficultyCurve()
        {
            return timedAttributes;
        }

        /// <summary>
        /// Get simplified difficulty graph points for mini visualization.
        /// </summary>
        /// <param name="sampleCount">Number of evenly-spaced samples to return.</param>
        /// <returns>List of graph points for rendering.</returns>
        public List<DifficultyGraphPoint> GetDifficultyGraph(int sampleCount = 100)
        {
            var result = new List<DifficultyGraphPoint>();

            if (timedAttributes.Count == 0 || sampleCount <= 0)
                return result;

            double startTime = timedAttributes[0].Time;
            double endTime = timedAttributes[^1].Time;
            double duration = endTime - startTime;

            if (duration <= 0)
            {
                result.Add(new DifficultyGraphPoint
                {
                    Time = startTime,
                    Progress = 0,
                    StarRating = timedAttributes[0].StarRating
                });
                return result;
            }

            for (int i = 0; i < sampleCount; i++)
            {
                double progress = (double)i / (sampleCount - 1);
                double time = startTime + progress * duration;

                var attr = timedAttributes.LastOrDefault(t => t.Time <= time);
                double rating = attr?.StarRating ?? 0;

                result.Add(new DifficultyGraphPoint
                {
                    Time = time,
                    Progress = progress,
                    StarRating = rating
                });
            }

            return result;
        }

        /// <summary>
        /// Get summary statistics for the entire beatmap.
        /// </summary>
        public DifficultySummary GetSummary()
        {
            if (timedAttributes.Count == 0)
            {
                return new DifficultySummary();
            }

            return new DifficultySummary
            {
                FinalStarRating = timedAttributes[^1].StarRating,
                PeakStarRating = peakStarRating,
                PeakTime = peakTime,
                AverageStarRating = timedAttributes.Average(t => t.StarRating),
                MinStarRating = timedAttributes.Min(t => t.StarRating),
                Variance = CalculateVariance(timedAttributes.Select(t => t.StarRating)),
                HardSectionCount = timedAttributes.Count(t => t.StarRating > peakStarRating * 0.8),
                TotalDuration = timedAttributes[^1].Time - timedAttributes[0].Time,
                DifficultyProfile = ClassifyDifficultyProfile()
            };
        }

        /// <summary>
        /// Reset the tracker to the beginning of the song.
        /// </summary>
        public void Reset()
        {
            currentIndex = 0;
            currentStarRating = 0;
            displayedStarRating = 0;
            currentSkillRatings.Clear();
        }

        /// <summary>
        /// Seek to a specific time in the beatmap.
        /// </summary>
        public void Seek(double time)
        {
            currentIndex = 0;
            for (int i = 0; i < timedAttributes.Count; i++)
            {
                if (timedAttributes[i].Time > time)
                    break;
                currentIndex = i;
            }

            if (currentIndex < timedAttributes.Count)
            {
                displayedStarRating = timedAttributes[currentIndex].StarRating;
            }
        }

        private void UpdateSkillRatings(TimedDifficultyAttributes attr)
        {
            currentSkillRatings["Speed"] = attr.SpeedRating;
            currentSkillRatings["Stamina"] = attr.StaminaRating;
            currentSkillRatings["Coordination"] = attr.CoordinationRating;
            currentSkillRatings["Rhythm"] = attr.RhythmicComplexityRating;
            currentSkillRatings["Technique"] = attr.TechniqueRating;
            currentSkillRatings["Precision"] = attr.PrecisionRating;
            currentSkillRatings["Pattern"] = attr.PatternRating;
            currentSkillRatings["Movement"] = attr.MovementRating;
            currentSkillRatings["Musicality"] = attr.MusicalityRating;
            currentSkillRatings["Reading"] = attr.ReadingRating;
        }

        private string GetDominantSkill(TimedDifficultyAttributes attr)
        {
            var skills = new Dictionary<string, double>
            {
                { "Speed", attr.SpeedRating },
                { "Stamina", attr.StaminaRating },
                { "Coordination", attr.CoordinationRating },
                { "Rhythm", attr.RhythmicComplexityRating },
                { "Technique", attr.TechniqueRating }
            };

            return skills.OrderByDescending(kv => kv.Value).FirstOrDefault().Key ?? "Speed";
        }

        private List<string> GetTopSkills(TimedDifficultyAttributes attr, int count)
        {
            var skills = new Dictionary<string, double>
            {
                { "Speed", attr.SpeedRating },
                { "Stamina", attr.StaminaRating },
                { "Coordination", attr.CoordinationRating },
                { "Rhythm", attr.RhythmicComplexityRating },
                { "Technique", attr.TechniqueRating },
                { "Precision", attr.PrecisionRating }
            };

            return skills.OrderByDescending(kv => kv.Value)
                         .Take(count)
                         .Select(kv => kv.Key)
                         .ToList();
        }

        private static double CalculateVariance(IEnumerable<double> values)
        {
            var list = values.ToList();
            if (list.Count == 0) return 0;

            double mean = list.Average();
            return list.Sum(v => Math.Pow(v - mean, 2)) / list.Count;
        }

        private DifficultyProfile ClassifyDifficultyProfile()
        {
            if (timedAttributes.Count < 3)
                return DifficultyProfile.Consistent;

            double variance = CalculateVariance(timedAttributes.Select(t => t.StarRating));
            double mean = timedAttributes.Average(t => t.StarRating);
            double coefficientOfVariation = mean > 0 ? Math.Sqrt(variance) / mean : 0;

            // Analyze shape
            int thirdPoint = timedAttributes.Count / 3;
            int twoThirdPoint = timedAttributes.Count * 2 / 3;

            double firstThirdAvg = timedAttributes.Take(thirdPoint).Average(t => t.StarRating);
            double middleThirdAvg = timedAttributes.Skip(thirdPoint).Take(thirdPoint).Average(t => t.StarRating);
            double lastThirdAvg = timedAttributes.Skip(twoThirdPoint).Average(t => t.StarRating);

            if (coefficientOfVariation < 0.15)
                return DifficultyProfile.Consistent;

            if (lastThirdAvg > firstThirdAvg * 1.3 && lastThirdAvg > middleThirdAvg)
                return DifficultyProfile.BuildUp;

            if (firstThirdAvg > lastThirdAvg * 1.3)
                return DifficultyProfile.FrontLoaded;

            if (middleThirdAvg > firstThirdAvg * 1.2 && middleThirdAvg > lastThirdAvg * 1.2)
                return DifficultyProfile.MidPeak;

            if (coefficientOfVariation > 0.35)
                return DifficultyProfile.Spiky;

            return DifficultyProfile.Varied;
        }
    }

    /// <summary>
    /// Real-time rating update data structure.
    /// </summary>
    public class RealTimeRatingUpdate
    {
        /// <summary>
        /// Current playback time in milliseconds.
        /// </summary>
        public double Time { get; set; }

        /// <summary>
        /// Current star rating at this exact moment (raw).
        /// </summary>
        public double CurrentStarRating { get; set; }

        /// <summary>
        /// Smoothed star rating for display (avoids jitter).
        /// </summary>
        public double DisplayedStarRating { get; set; }

        /// <summary>
        /// Peak star rating in the entire beatmap.
        /// </summary>
        public double PeakStarRating { get; set; }

        /// <summary>
        /// Time at which peak difficulty occurs.
        /// </summary>
        public double PeakTime { get; set; }

        /// <summary>
        /// Progress through the beatmap (0-1).
        /// </summary>
        public double Progress { get; set; }

        /// <summary>
        /// Whether we're currently at or near the peak difficulty.
        /// </summary>
        public bool IsAtPeak { get; set; }

        /// <summary>
        /// Current speed rating.
        /// </summary>
        public double SpeedRating { get; set; }

        /// <summary>
        /// Current coordination rating.
        /// </summary>
        public double CoordinationRating { get; set; }

        /// <summary>
        /// Current rhythmic complexity rating.
        /// </summary>
        public double RhythmRating { get; set; }

        /// <summary>
        /// Current technique rating.
        /// </summary>
        public double TechniqueRating { get; set; }

        /// <summary>
        /// Current stamina rating.
        /// </summary>
        public double StaminaRating { get; set; }

        /// <summary>
        /// Instantaneous difficulty value (pre-scaling).
        /// </summary>
        public double InstantaneousDifficulty { get; set; }

        /// <summary>
        /// The skill currently contributing most to difficulty.
        /// </summary>
        public string DominantSkill { get; set; } = "";

        /// <summary>
        /// Formatted star rating string for display (e.g., "5.73★").
        /// </summary>
        public string FormattedRating => $"{DisplayedStarRating:F2}★";

        /// <summary>
        /// Formatted rating with peak info (e.g., "5.73★ / 6.42★").
        /// </summary>
        public string FormattedWithPeak => $"{DisplayedStarRating:F2}★ / {PeakStarRating:F2}★";
    }

    /// <summary>
    /// Event data when peak difficulty is reached.
    /// </summary>
    public class PeakDifficultyEvent
    {
        public double PeakStarRating { get; set; }
        public double PeakTime { get; set; }
        public List<string> DominantSkills { get; set; } = new();
    }

    /// <summary>
    /// Summary statistics for the entire beatmap difficulty.
    /// </summary>
    public class DifficultySummary
    {
        public double FinalStarRating { get; set; }
        public double PeakStarRating { get; set; }
        public double PeakTime { get; set; }
        public double AverageStarRating { get; set; }
        public double MinStarRating { get; set; }
        public double Variance { get; set; }
        public int HardSectionCount { get; set; }
        public double TotalDuration { get; set; }
        public DifficultyProfile DifficultyProfile { get; set; }

        /// <summary>
        /// Standard deviation of difficulty.
        /// </summary>
        public double StandardDeviation => Math.Sqrt(Variance);

        /// <summary>
        /// Human-readable profile description.
        /// </summary>
        public string ProfileDescription => DifficultyProfile switch
        {
            DifficultyProfile.Consistent => "Consistent difficulty throughout",
            DifficultyProfile.BuildUp => "Builds up to finale",
            DifficultyProfile.FrontLoaded => "Hardest at the start",
            DifficultyProfile.MidPeak => "Peak difficulty in the middle",
            DifficultyProfile.Spiky => "Highly variable difficulty spikes",
            DifficultyProfile.Varied => "Varied difficulty sections",
            _ => "Unknown profile"
        };
    }

    /// <summary>
    /// Classification of how difficulty is distributed over time.
    /// </summary>
    public enum DifficultyProfile
    {
        /// <summary>Relatively constant difficulty throughout.</summary>
        Consistent,

        /// <summary>Difficulty increases toward the end (like many prog songs).</summary>
        BuildUp,

        /// <summary>Hardest section is at the start.</summary>
        FrontLoaded,

        /// <summary>Peak difficulty in the middle of the song.</summary>
        MidPeak,

        /// <summary>Large difficulty spikes throughout (varied sections).</summary>
        Spiky,

        /// <summary>Multiple distinct difficulty levels throughout.</summary>
        Varied
    }

    /// <summary>
    /// Timed difficulty attributes - represents difficulty at a specific point in time.
    /// Inspired by osu!'s TimedDifficultyAttributes for progressive difficulty display.
    /// </summary>
    public class TimedDifficultyAttributes
    {
        /// <summary>
        /// Time in milliseconds at which these attributes apply.
        /// </summary>
        public double Time { get; set; }

        /// <summary>
        /// Progressive star rating up to this point (accumulated difficulty).
        /// </summary>
        public double StarRating { get; set; }

        /// <summary>
        /// Instantaneous difficulty at this specific point (not accumulated).
        /// </summary>
        public double InstantaneousDifficulty { get; set; }

        // Individual skill ratings at this point
        public double SpeedRating { get; set; }
        public double StaminaRating { get; set; }
        public double CoordinationRating { get; set; }
        public double RhythmicComplexityRating { get; set; }
        public double PatternRating { get; set; }
        public double TechniqueRating { get; set; }
        public double PrecisionRating { get; set; }
        public double MovementRating { get; set; }
        public double MusicalityRating { get; set; }
        public double ReadingRating { get; set; }

        /// <summary>
        /// Maximum combo achieved up to this point.
        /// </summary>
        public int ComboAtTime { get; set; }

        /// <summary>
        /// Clone this attributes object.
        /// </summary>
        public TimedDifficultyAttributes Clone()
        {
            return new TimedDifficultyAttributes
            {
                Time = Time,
                StarRating = StarRating,
                InstantaneousDifficulty = InstantaneousDifficulty,
                SpeedRating = SpeedRating,
                StaminaRating = StaminaRating,
                CoordinationRating = CoordinationRating,
                RhythmicComplexityRating = RhythmicComplexityRating,
                PatternRating = PatternRating,
                TechniqueRating = TechniqueRating,
                PrecisionRating = PrecisionRating,
                MovementRating = MovementRating,
                MusicalityRating = MusicalityRating,
                ReadingRating = ReadingRating,
                ComboAtTime = ComboAtTime
            };
        }
    }

    /// <summary>
    /// Simplified point for difficulty graph visualization.
    /// </summary>
    public class DifficultyGraphPoint
    {
        /// <summary>
        /// Time in milliseconds.
        /// </summary>
        public double Time { get; set; }

        /// <summary>
        /// Progress through the beatmap (0-1).
        /// </summary>
        public double Progress { get; set; }

        /// <summary>
        /// Star rating at this point.
        /// </summary>
        public double StarRating { get; set; }
    }
}
