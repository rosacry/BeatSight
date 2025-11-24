using System;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Game.Beatmaps.Difficulty.Skills
{
    /// <summary>
    /// Movement/Ergonomics Skill - Physical Kit Traversal Analysis
    /// 
    /// This skill evaluates the physical demands of moving around the drum kit.
    /// Unlike other skills which focus on WHAT you play, this focuses on WHERE
    /// you play it and how efficiently you must navigate the physical space.
    /// 
    /// KEY CONCEPTS:
    /// 
    /// 1. KIT GEOGRAPHY
    ///    Drums have physical positions relative to the drummer:
    ///    - Hi-hat (far left), snare (center-left), kick (center-floor)
    ///    - Toms arranged left-to-right, high-to-low
    ///    - Ride (far right), crashes (overhead arc)
    ///    Large movements between distant drums at speed = high difficulty
    ///    
    /// 2. CROSSOVER PATTERNS
    ///    Playing patterns that cross hands (right over left or vice versa)
    ///    require awkward positioning and add significant difficulty.
    ///    
    /// 3. ECONOMY OF MOTION
    ///    Expert drummers minimize movement. Patterns requiring large
    ///    movements leave less time for setup and are physically harder.
    ///    
    /// 4. SIMULTANEOUS REACH
    ///    Playing drums at opposite ends of the kit simultaneously
    ///    (e.g., hi-hat + floor tom) requires full wingspan.
    ///    
    /// 5. VERTICAL MOVEMENT
    ///    Moving between low drums (kick, floor tom) and high cymbals
    ///    adds a vertical component to the physical demand.
    /// 
    /// This skill rewards orchestrated fills that traverse the kit,
    /// complex cymbal choreography, and patterns like:
    /// - Neil Peart's kit traversals
    /// - Mike Portnoy's elaborate fill orchestrations
    /// - Terry Bozzio's massive kit navigation
    /// </summary>
    public class Movement : Skill
    {
        protected override double SkillMultiplier => 18.0;
        protected override double StrainDecayBase => 0.20; // Medium decay - movement accumulates

        // ========================
        // KIT POSITION MAP
        // ========================
        // Coordinate system: X = left(-) to right(+), Y = near(0) to far(1)
        // Values represent relative distances on a standard 5-piece kit

        private static readonly Dictionary<DrumType, (double X, double Y, double Z)> DrumPositions = new()
        {
            // Cymbals (elevated - Z > 0)
            { DrumType.HiHat,      (-0.7, 0.5, 0.4) },
            { DrumType.Crash,      (-0.4, 0.7, 0.6) },
            { DrumType.Ride,       (0.6, 0.6, 0.4) },
            { DrumType.RideBell,   (0.6, 0.6, 0.4) },
            { DrumType.China,      (0.5, 0.8, 0.7) },
            { DrumType.Splash,     (0.0, 0.6, 0.5) },
            { DrumType.Stack,      (0.3, 0.7, 0.5) },
            
            // Drums (ground level - Z = 0)
            { DrumType.Snare,      (-0.2, 0.3, 0.0) },
            { DrumType.TomHigh,    (-0.1, 0.5, 0.2) },
            { DrumType.TomMid,     (0.15, 0.5, 0.15) },
            { DrumType.Tom,        (0.0, 0.5, 0.15) },
            { DrumType.TomLow,     (0.5, 0.4, 0.0) },
            { DrumType.Kick,       (0.0, 0.0, -0.2) },
            
            // Pedals (floor level)
            { DrumType.HiHatPedal, (-0.7, 0.2, -0.3) },
            
            // Aux percussion
            { DrumType.Cowbell,    (0.2, 0.6, 0.3) },
            { DrumType.Tambourine, (-0.5, 0.6, 0.3) },
            { DrumType.Other,      (0.0, 0.5, 0.2) }
        };

        // Movement history tracking
        private readonly Queue<List<DrumType>> recentDrumPositions = new();
        private const int POSITION_HISTORY_SIZE = 8;

        // Crossover tracking
        private bool lastWasCrossover = false;
        private int consecutiveCrossovers = 0;

        // Sustained movement tracking
        private double accumulatedTravelDistance = 0;
        private int movementWindowCount = 0;

        protected override double StrainValueOf(DifficultyHitObject current)
        {
            if (current.DeltaTime <= 0) return 0;

            double strain = 0;
            var currentDrums = current.DrumTypes;

            if (currentDrums.Count == 0) return 0;

            // ========================
            // 1. BASIC TRAVEL DISTANCE
            // ========================
            strain += CalculateTravelDistanceStrain(current);

            // ========================
            // 2. SPEED-SCALED MOVEMENT
            // ========================
            // Moving fast while covering distance is exponentially harder
            double speedFactor = GetMovementSpeedFactor(current.DeltaTime);
            strain *= speedFactor;

            // ========================
            // 3. CROSSOVER PATTERNS
            // ========================
            strain += CalculateCrossoverStrain(current);

            // ========================
            // 4. SIMULTANEOUS REACH
            // ========================
            if (currentDrums.Count > 1)
            {
                strain += CalculateSimultaneousReachStrain(currentDrums);
            }

            // ========================
            // 5. VERTICAL MOVEMENT
            // ========================
            strain += CalculateVerticalMovementStrain(current);

            // ========================
            // 6. KIT TRAVERSAL PATTERNS
            // ========================
            strain += CalculateTraversalPatternStrain(currentDrums);

            // ========================
            // 7. ACCUMULATED MOVEMENT FATIGUE
            // ========================
            strain += CalculateMovementFatigueBonus();

            // ========================
            // 8. AWKWARD POSITIONS
            // ========================
            strain += CalculateAwkwardPositionStrain(current);

            // Update tracking
            UpdateMovementHistory(currentDrums, current);

            return strain;
        }

        // ========================
        // TRAVEL DISTANCE CALCULATIONS
        // ========================

        private double CalculateTravelDistanceStrain(DifficultyHitObject current)
        {
            if (recentDrumPositions.Count == 0) return 0;

            var previousDrums = recentDrumPositions.Last();
            var currentDrums = current.DrumTypes;

            double maxDistance = 0;

            // Calculate minimum travel distance between drum sets
            foreach (var prevDrum in previousDrums)
            {
                foreach (var currDrum in currentDrums)
                {
                    double dist = GetDistance(prevDrum, currDrum);
                    maxDistance = Math.Max(maxDistance, dist);
                }
            }

            // Scale distance to strain
            // Short distance (< 0.3): minimal strain
            // Medium distance (0.3-0.6): moderate strain
            // Large distance (> 0.6): significant strain
            if (maxDistance < 0.2) return 0;
            if (maxDistance < 0.4) return maxDistance * 1.5;
            if (maxDistance < 0.7) return 0.6 + (maxDistance - 0.4) * 3.0;

            // Extreme distance (full kit traversal)
            return 1.5 + (maxDistance - 0.7) * 5.0;
        }

        private double GetDistance(DrumType from, DrumType to)
        {
            if (!DrumPositions.TryGetValue(from, out var fromPos) ||
                !DrumPositions.TryGetValue(to, out var toPos))
                return 0.3; // Default moderate distance

            double dx = toPos.X - fromPos.X;
            double dy = toPos.Y - fromPos.Y;
            double dz = toPos.Z - fromPos.Z;

            return Math.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        private double GetMovementSpeedFactor(double deltaTime)
        {
            // Slower movements (longer delta) need less speed scaling
            if (deltaTime > 200) return 1.0;
            if (deltaTime > 150) return 1.2;
            if (deltaTime > 100) return 1.5;
            if (deltaTime > 75) return 2.0;
            if (deltaTime > 50) return 3.0;

            // Extreme speed movement
            return 4.0 + (50 - deltaTime) * 0.1;
        }

        // ========================
        // CROSSOVER PATTERNS
        // ========================

        private double CalculateCrossoverStrain(DifficultyHitObject current)
        {
            // Detect if hands need to cross
            bool isCrossover = DetectCrossover(current);

            double strain = 0;

            if (isCrossover)
            {
                strain = 2.5; // Base crossover difficulty

                // Consecutive crossovers are much harder
                if (lastWasCrossover)
                {
                    consecutiveCrossovers++;
                    strain += consecutiveCrossovers * 1.5;
                }
                else
                {
                    consecutiveCrossovers = 1;
                }
            }
            else
            {
                consecutiveCrossovers = 0;
            }

            lastWasCrossover = isCrossover;
            return strain;
        }

        private bool DetectCrossover(DifficultyHitObject current)
        {
            // Simple heuristic: playing hi-hat with right hand while left plays ride
            // or playing drums on opposite side with non-standard hand
            var drums = current.DrumTypes;

            // Hi-hat + ride simultaneously often requires crossover
            if (drums.Contains(DrumType.HiHat) && drums.Contains(DrumType.Ride))
                return true;

            // Hi-hat + floor tom simultaneously
            if (drums.Contains(DrumType.HiHat) && drums.Contains(DrumType.TomLow))
                return true;

            // Check recent pattern for implied crossover
            if (recentDrumPositions.Count >= 2)
            {
                var prev = recentDrumPositions.Last();

                // Quick left-to-right followed by right drum = likely crossover setup
                bool wasLeft = prev.Any(d => GetDrumPosition(d).X < -0.3);
                bool nowRight = drums.Any(d => GetDrumPosition(d).X > 0.3);

                bool wasRight = prev.Any(d => GetDrumPosition(d).X > 0.3);
                bool nowLeft = drums.Any(d => GetDrumPosition(d).X < -0.3);

                // Quick switch suggests crossover
                if ((wasLeft && nowRight) || (wasRight && nowLeft))
                {
                    if (current.DeltaTime < 100)
                        return true;
                }
            }

            return false;
        }

        private (double X, double Y, double Z) GetDrumPosition(DrumType drum)
        {
            return DrumPositions.GetValueOrDefault(drum, (0, 0.5, 0.2));
        }

        // ========================
        // SIMULTANEOUS REACH
        // ========================

        private double CalculateSimultaneousReachStrain(List<DrumType> drums)
        {
            if (drums.Count < 2) return 0;

            double maxSpan = 0;

            // Find the maximum distance between any two drums played simultaneously
            for (int i = 0; i < drums.Count; i++)
            {
                for (int j = i + 1; j < drums.Count; j++)
                {
                    double dist = GetDistance(drums[i], drums[j]);
                    maxSpan = Math.Max(maxSpan, dist);
                }
            }

            // Large simultaneous spans are difficult
            if (maxSpan < 0.4) return 0;
            if (maxSpan < 0.7) return (maxSpan - 0.4) * 3.0;

            // Full wingspan playing
            return 1.5 + (maxSpan - 0.7) * 6.0;
        }

        // ========================
        // VERTICAL MOVEMENT
        // ========================

        private double CalculateVerticalMovementStrain(DifficultyHitObject current)
        {
            if (recentDrumPositions.Count == 0) return 0;

            var prev = recentDrumPositions.Last();
            var curr = current.DrumTypes;

            double maxVertical = 0;

            foreach (var p in prev)
            {
                foreach (var c in curr)
                {
                    var pPos = GetDrumPosition(p);
                    var cPos = GetDrumPosition(c);

                    double dz = Math.Abs(cPos.Z - pPos.Z);
                    maxVertical = Math.Max(maxVertical, dz);
                }
            }

            // Large vertical movements (kick to crash, etc.)
            if (maxVertical < 0.3) return 0;
            if (maxVertical < 0.6) return maxVertical * 2.0;

            return 1.2 + (maxVertical - 0.6) * 4.0;
        }

        // ========================
        // TRAVERSAL PATTERNS
        // ========================

        private double CalculateTraversalPatternStrain(List<DrumType> currentDrums)
        {
            if (recentDrumPositions.Count < 3) return 0;

            double strain = 0;

            // Look for directional movement patterns
            var positions = recentDrumPositions.Select(drums =>
                drums.Count > 0 ? drums.Average(d => GetDrumPosition(d).X) : 0
            ).ToList();

            // Add current
            double currentX = currentDrums.Count > 0
                ? currentDrums.Average(d => GetDrumPosition(d).X)
                : 0;
            positions.Add(currentX);

            // Detect consistent directional movement (fill traversal)
            bool ascending = true;
            bool descending = true;

            for (int i = 1; i < positions.Count; i++)
            {
                if (positions[i] <= positions[i - 1]) ascending = false;
                if (positions[i] >= positions[i - 1]) descending = false;
            }

            // Consistent traversal pattern (like going down the toms)
            if (ascending || descending)
            {
                double totalSpan = Math.Abs(positions.Last() - positions.First());
                strain += totalSpan * 2.0; // Reward consistent kit traversal
            }

            // Zigzag patterns (alternating left-right) are harder
            int directionChanges = 0;
            for (int i = 2; i < positions.Count; i++)
            {
                double prev = positions[i - 1] - positions[i - 2];
                double curr = positions[i] - positions[i - 1];

                if ((prev > 0.1 && curr < -0.1) || (prev < -0.1 && curr > 0.1))
                    directionChanges++;
            }

            if (directionChanges >= 2)
            {
                strain += directionChanges * 1.5; // Zigzag penalty
            }

            return strain;
        }

        // ========================
        // MOVEMENT FATIGUE
        // ========================

        private double CalculateMovementFatigueBonus()
        {
            // Large accumulated movement over time increases difficulty
            if (movementWindowCount < 8) return 0;

            double avgMovement = accumulatedTravelDistance / movementWindowCount;

            // High sustained movement = fatigue
            if (avgMovement > 0.5)
            {
                return (avgMovement - 0.5) * 3.0;
            }

            return 0;
        }

        // ========================
        // AWKWARD POSITIONS
        // ========================

        private double CalculateAwkwardPositionStrain(DifficultyHitObject current)
        {
            double strain = 0;
            var drums = current.DrumTypes;

            // Specific awkward combinations

            // Playing kick while reaching for far cymbals
            if (drums.Contains(DrumType.Kick))
            {
                if (drums.Contains(DrumType.China) || drums.Contains(DrumType.Crash))
                    strain += 1.5;
            }

            // Cross-kit simultaneous hits
            if (drums.Contains(DrumType.HiHat) && drums.Contains(DrumType.RideBell))
                strain += 2.0;

            // Three+ drums simultaneously across kit
            if (drums.Count >= 3)
            {
                var positions = drums.Select(d => GetDrumPosition(d).X).ToList();
                double span = positions.Max() - positions.Min();

                if (span > 0.8)
                    strain += span * 2.5;
            }

            return strain;
        }

        // ========================
        // HISTORY MANAGEMENT
        // ========================

        private void UpdateMovementHistory(List<DrumType> drums, DifficultyHitObject current)
        {
            // Track positions
            recentDrumPositions.Enqueue(new List<DrumType>(drums));
            if (recentDrumPositions.Count > POSITION_HISTORY_SIZE)
                recentDrumPositions.Dequeue();

            // Track accumulated movement
            if (recentDrumPositions.Count >= 2)
            {
                var prev = recentDrumPositions.ElementAt(recentDrumPositions.Count - 2);
                double dist = 0;

                foreach (var p in prev)
                {
                    foreach (var c in drums)
                    {
                        dist = Math.Max(dist, GetDistance(p, c));
                    }
                }

                accumulatedTravelDistance += dist;
                movementWindowCount++;

                // Decay old movement (sliding window effect)
                if (movementWindowCount > 16)
                {
                    accumulatedTravelDistance *= 0.95;
                    movementWindowCount = 16;
                }
            }
        }
    }
}
