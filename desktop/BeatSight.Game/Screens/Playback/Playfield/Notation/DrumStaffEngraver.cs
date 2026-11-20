using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;

namespace BeatSight.Game.Screens.Playback.Playfield.Notation
{
    /// <summary>A note handed to the engraver: absolute time, beatmap component and velocity.</summary>
    public readonly record struct DrumStaffInputNote(double Time, string Component, double Velocity);

    public readonly record struct DrumStaffMeasureInfo(int Index, double StartTime, double EndTime, int Beats, double BeatMs);

    /// <summary>
    /// Beat/measure arithmetic over a beatmap's timing points. Beat 0 / measure 0 starts at the timing offset.
    /// </summary>
    public sealed class DrumTempoMap
    {
        private readonly struct Segment
        {
            public Segment(double startTime, double beatMs, int beatsPerMeasure, int startMeasure)
            {
                StartTime = startTime;
                BeatMs = beatMs;
                BeatsPerMeasure = beatsPerMeasure;
                StartMeasure = startMeasure;
            }

            public double StartTime { get; }
            public double BeatMs { get; }
            public int BeatsPerMeasure { get; }
            public int StartMeasure { get; }
            public double MeasureMs => BeatMs * BeatsPerMeasure;
        }

        private readonly List<Segment> segments = new();

        public DrumTempoMap(TimingInfo? timing)
        {
            double origin = timing?.Offset ?? 0;
            var (beats, unit) = parseSignature(timing?.TimeSignature, 4, 4);
            double baseBpm = timing?.Bpm > 0 ? timing.Bpm : TimingInfo.DefaultBpm;

            var points = (timing?.TimingPoints ?? new List<TimingPoint>())
                .Where(p => p.Bpm > 0)
                .OrderBy(p => p.Time)
                .ToList();

            double start = origin;
            double bpm = baseBpm;
            int measure = 0;

            // Points at or before the origin define the starting tempo/signature.
            foreach (var point in points.Where(p => p.Time <= origin))
            {
                bpm = point.Bpm;
                (beats, unit) = parseSignature(point.TimeSignature, beats, unit);
            }

            segments.Add(new Segment(start, beatMs(bpm, unit), beats, measure));

            foreach (var point in points.Where(p => p.Time > origin))
            {
                var previous = segments[^1];
                int measuresBefore = (int)Math.Ceiling((point.Time - previous.StartTime) / previous.MeasureMs - 1e-6);
                (beats, unit) = parseSignature(point.TimeSignature, beats, unit);
                segments.Add(new Segment(point.Time, beatMs(point.Bpm, unit), beats, previous.StartMeasure + Math.Max(1, measuresBefore)));
            }

            BaseBeatMs = segments[0].BeatMs;
        }

        /// <summary>Beat length (ms) at the start of the map; used for a constant horizontal scale.</summary>
        public double BaseBeatMs { get; }

        public DrumStaffMeasureInfo MeasureAt(double time)
        {
            var segment = segmentAt(time);
            int local = (int)Math.Floor((time - segment.StartTime) / segment.MeasureMs);
            return measureInfo(segment, local);
        }

        public DrumStaffMeasureInfo NextMeasure(in DrumStaffMeasureInfo measure)
            => MeasureAt(measure.EndTime + 0.01);

        public int BeatsPerMeasureAt(double time) => segmentAt(time).BeatsPerMeasure;

        public double BeatMsAt(double time) => segmentAt(time).BeatMs;

        private DrumStaffMeasureInfo measureInfo(in Segment segment, int local)
        {
            double start = segment.StartTime + local * segment.MeasureMs;
            return new DrumStaffMeasureInfo(segment.StartMeasure + local, start, start + segment.MeasureMs, segment.BeatsPerMeasure, segment.BeatMs);
        }

        private Segment segmentAt(double time)
        {
            for (int i = segments.Count - 1; i > 0; i--)
            {
                if (time >= segments[i].StartTime)
                    return segments[i];
            }

            return segments[0];
        }

        private static double beatMs(double bpm, int unit) => 60000.0 / Math.Max(1.0, bpm) * (4.0 / Math.Max(1, unit));

        private static (int Beats, int Unit) parseSignature(string? signature, int fallbackBeats, int fallbackUnit)
        {
            if (string.IsNullOrWhiteSpace(signature))
                return (fallbackBeats, fallbackUnit);

            string[] parts = signature.Split('/');
            int beats = parts.Length > 0 && int.TryParse(parts[0], out int b) && b > 0 ? b : fallbackBeats;
            int unit = parts.Length > 1 && int.TryParse(parts[1], out int u) && u > 0 ? u : fallbackUnit;
            return (Math.Clamp(beats, 1, 16), Math.Clamp(unit, 1, 32));
        }
    }

    public sealed record EngravedNote(DrumNotationSymbol Symbol, double SourceTime, bool Ghost);

    /// <summary>
    /// Simultaneous notes of one voice. <see cref="BeamLevels"/> is the number of beams/flags its written duration
    /// needs (0 = quarter or longer, 1 = eighth, 2 = sixteenth, 3 = thirty-second).
    /// </summary>
    public sealed record EngravedChord(
        DrumVoice Voice,
        double Time,
        int Beat,
        int Slot,
        int Grid,
        IReadOnlyList<EngravedNote> Notes,
        int BeamLevels,
        bool Dotted,
        int BeamGroup)
    {
        public bool IsBeamed => BeamGroup >= 0;
        public int HighestStep => Notes.Max(n => n.Symbol.StaffStep);
        public int LowestStep => Notes.Min(n => n.Symbol.StaffStep);
    }

    /// <summary>A rest of <see cref="Level"/> 0 = quarter, 1 = eighth, 2 = sixteenth; -1 = whole-measure rest.</summary>
    public sealed record EngravedRest(DrumVoice Voice, double Time, int Level);

    public sealed record EngravedTuplet(DrumVoice Voice, int BeamGroup, int Number);

    public sealed record EngravedMeasure(
        DrumStaffMeasureInfo Info,
        IReadOnlyList<double> BeatTimes,
        IReadOnlyList<EngravedChord> Chords,
        IReadOnlyList<EngravedRest> Rests,
        IReadOnlyList<EngravedTuplet> Tuplets);

    /// <summary>
    /// Turns detected drum hits into readable measures: notes are grouped into chords, quantised per beat to the
    /// simplest grid that fits (sixteenths, eighth-note triplets, thirty-seconds, sixteenth triplets), split into
    /// hands (stems up) and feet (stems down), beamed by beat, and given rests where a beat or measure is empty.
    /// </summary>
    public static class DrumStaffEngraver
    {
        private static readonly int[] gridPreference = { 4, 3, 8, 6 };

        /// <summary>Notes closer than this (ms) are one chord.</summary>
        public const double ChordToleranceMs = 25;

        /// <summary>
        /// Notes belong to the measure whose span, shifted back by half a sixteenth, contains them, so a hit a few
        /// milliseconds early on a downbeat is written on that downbeat.
        /// </summary>
        public static double MeasureLeadMs(double beatMs) => beatMs / 8.0;

        public static EngravedMeasure Engrave(in DrumStaffMeasureInfo measure, IReadOnlyList<DrumStaffInputNote> sortedNotes)
        {
            double lead = MeasureLeadMs(measure.BeatMs);
            var beatTimes = new double[measure.Beats];
            for (int i = 0; i < measure.Beats; i++)
                beatTimes[i] = measure.StartTime + i * measure.BeatMs;

            var chords = new List<EngravedChord>();
            var rests = new List<EngravedRest>();
            var tuplets = new List<EngravedTuplet>();
            int nextGroup = 0;

            int first = lowerBound(sortedNotes, measure.StartTime - lead);
            bool handsAnywhere = false;
            var handsBeatsWithNotes = new bool[measure.Beats];

            for (int beat = 0; beat < measure.Beats; beat++)
            {
                double beatStart = beatTimes[beat];
                double windowStart = beatStart - lead;
                double windowEnd = beatStart + measure.BeatMs - lead;

                var inBeat = new List<DrumStaffInputNote>();
                for (int i = first; i < sortedNotes.Count && sortedNotes[i].Time < windowEnd; i++)
                {
                    if (sortedNotes[i].Time >= windowStart)
                        inBeat.Add(sortedNotes[i]);
                }

                if (inBeat.Count == 0)
                    continue;

                var clusters = clusterByTime(inBeat);
                int grid = chooseGrid(clusters, beatStart, measure.BeatMs);

                foreach (DrumVoice voice in new[] { DrumVoice.Hands, DrumVoice.Feet })
                {
                    // slot -> notes of this voice
                    var bySlot = new SortedDictionary<int, List<EngravedNote>>();
                    foreach (var cluster in clusters)
                    {
                        int slot = slotFor(cluster.Time, beatStart, measure.BeatMs, grid);
                        foreach (var note in cluster.Notes)
                        {
                            var symbol = DrumNotation.Resolve(note.Component);
                            if (symbol.Voice != voice)
                                continue;

                            if (!bySlot.TryGetValue(slot, out var list))
                                bySlot[slot] = list = new List<EngravedNote>();

                            // One head per staff position and head shape (duplicate detections collapse).
                            if (!list.Any(n => n.Symbol.StaffStep == symbol.StaffStep && n.Symbol.Head == symbol.Head))
                                list.Add(new EngravedNote(symbol, note.Time, note.Velocity < 0.35));
                        }
                    }

                    if (bySlot.Count == 0)
                        continue;

                    if (voice == DrumVoice.Hands)
                    {
                        handsAnywhere = true;
                        handsBeatsWithNotes[beat] = true;
                        addLeadingRests(rests, voice, bySlot.Keys.First(), grid, beatStart, measure.BeatMs);
                    }

                    int[] slots = bySlot.Keys.ToArray();
                    int group = slots.Length >= 2 ? nextGroup++ : -1;
                    bool triplet = grid % 3 == 0;

                    for (int i = 0; i < slots.Length; i++)
                    {
                        int nextSlot = i + 1 < slots.Length ? slots[i + 1] : grid;
                        double duration = (nextSlot - slots[i]) / (double)grid;
                        (int levels, bool dotted) = ResolveBeamLevels(duration, triplet);

                        // Inside a beam group every chord needs at least the primary beam.
                        if (group >= 0)
                            levels = Math.Max(1, levels);

                        chords.Add(new EngravedChord(
                            voice,
                            beatStart + slots[i] * measure.BeatMs / grid,
                            beat,
                            slots[i],
                            grid,
                            bySlot[slots[i]].OrderBy(n => n.Symbol.StaffStep).ToArray(),
                            levels,
                            dotted,
                            group));
                    }

                    if (triplet && group >= 0)
                        tuplets.Add(new EngravedTuplet(voice, group, 3));
                }
            }

            if (!handsAnywhere)
            {
                rests.Add(new EngravedRest(DrumVoice.Hands, measure.StartTime + (measure.EndTime - measure.StartTime) / 2, -1));
            }
            else
            {
                for (int beat = 0; beat < measure.Beats; beat++)
                {
                    if (!handsBeatsWithNotes[beat])
                        rests.Add(new EngravedRest(DrumVoice.Hands, beatTimes[beat], 0));
                }
            }

            return new EngravedMeasure(
                measure,
                beatTimes,
                chords.OrderBy(c => c.Time).ThenBy(c => c.Voice).ToArray(),
                rests.OrderBy(r => r.Time).ToArray(),
                tuplets);
        }

        /// <summary>
        /// Beams (or flags) for a written duration in beats. Triplet grids are compared at their straight
        /// equivalent (an eighth-note triplet is beamed like an eighth).
        /// </summary>
        public static (int Levels, bool Dotted) ResolveBeamLevels(double durationBeats, bool triplet)
        {
            double d = triplet ? durationBeats * 1.5 : durationBeats;
            const double eps = 1e-6;

            if (d >= 1 - eps)
                return (0, false);
            if (Math.Abs(d - 0.75) < eps)
                return (1, true);
            if (d >= 0.5 - eps)
                return (1, false);
            if (Math.Abs(d - 0.375) < eps)
                return (2, true);
            if (d >= 0.25 - eps)
                return (2, false);
            return (3, false);
        }

        /// <summary>Chooses the simplest grid whose slots keep every chord within tolerance and distinct.</summary>
        internal static int ChooseGrid(IReadOnlyList<double> chordTimes, double beatStart, double beatMs)
        {
            var clusters = chordTimes.Select(t => new Cluster(t, Array.Empty<DrumStaffInputNote>())).ToList();
            return chooseGrid(clusters, beatStart, beatMs);
        }

        private sealed record Cluster(double Time, IReadOnlyList<DrumStaffInputNote> Notes);

        private static List<Cluster> clusterByTime(List<DrumStaffInputNote> notes)
        {
            var clusters = new List<Cluster>();
            var current = new List<DrumStaffInputNote>();
            double anchor = double.NaN;

            foreach (var note in notes.OrderBy(n => n.Time))
            {
                if (current.Count > 0 && note.Time - anchor > ChordToleranceMs)
                {
                    clusters.Add(new Cluster(current.Average(n => n.Time), current.ToArray()));
                    current.Clear();
                }

                if (current.Count == 0)
                    anchor = note.Time;
                current.Add(note);
            }

            if (current.Count > 0)
                clusters.Add(new Cluster(current.Average(n => n.Time), current.ToArray()));

            return clusters;
        }

        private static int chooseGrid(List<Cluster> clusters, double beatStart, double beatMs)
        {
            double toleranceMs = Math.Min(30.0, beatMs / 10.0);
            int bestGrid = 4;
            double bestError = double.MaxValue;

            foreach (int grid in gridPreference)
            {
                var used = new HashSet<int>();
                double maxError = 0;
                bool distinct = true;

                foreach (var cluster in clusters)
                {
                    int slot = slotFor(cluster.Time, beatStart, beatMs, grid);
                    double slotTime = beatStart + slot * beatMs / grid;
                    maxError = Math.Max(maxError, Math.Abs(cluster.Time - slotTime));
                    if (!used.Add(slot))
                        distinct = false;
                }

                if (distinct && maxError <= toleranceMs)
                    return grid;

                double score = maxError + (distinct ? 0 : beatMs);
                if (score < bestError)
                {
                    bestError = score;
                    bestGrid = grid;
                }
            }

            return bestGrid;
        }

        private static int slotFor(double time, double beatStart, double beatMs, int grid)
        {
            int slot = (int)Math.Round((time - beatStart) / beatMs * grid);
            return Math.Clamp(slot, 0, grid - 1);
        }

        private static void addLeadingRests(List<EngravedRest> rests, DrumVoice voice, int firstSlot, int grid, double beatStart, double beatMs)
        {
            if (firstSlot <= 0)
                return;

            double gap = firstSlot / (double)grid;
            bool triplet = grid % 3 == 0;
            double straight = triplet ? gap * 1.5 : gap;

            if (Math.Abs(straight - 0.75) < 1e-6)
            {
                rests.Add(new EngravedRest(voice, beatStart, 1));
                rests.Add(new EngravedRest(voice, beatStart + beatMs * 0.5, 2));
                return;
            }

            int level = straight >= 0.5 - 1e-6 ? 1 : 2;
            rests.Add(new EngravedRest(voice, beatStart, level));
        }

        private static int lowerBound(IReadOnlyList<DrumStaffInputNote> notes, double time)
        {
            int lo = 0, hi = notes.Count;
            while (lo < hi)
            {
                int mid = (lo + hi) / 2;
                if (notes[mid].Time < time)
                    lo = mid + 1;
                else
                    hi = mid;
            }

            return lo;
        }
    }
}
