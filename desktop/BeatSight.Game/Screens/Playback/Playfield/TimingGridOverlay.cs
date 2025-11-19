using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    internal sealed partial class TimingGridOverlay : CompositeDrawable
    {
        private readonly List<GridMarker> markers = new List<GridMarker>();
        private readonly List<DrawableGridLine> lineBuffer = new List<DrawableGridLine>();
        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private bool useGlobalKick = true;
        private LaneLayout? laneLayout;
        private PlaybackPlayfield? playfield;

        private const double previewMultiplier = 1.7;
        private const double pastAllowance = 320;

        public TimingGridOverlay()
        {
            RelativeSizeAxes = Axes.Both;
            Alpha = 0.85f;
            AlwaysPresent = true;
        }

        public void Configure(Beatmap beatmap, LaneLayout layout, bool globalKick)
        {
            laneLayout = layout;
            useGlobalKick = globalKick;
            rebuildMarkers(beatmap);
        }

        public void SetLaneLayout(LaneLayout layout)
        {
            laneLayout = layout;
        }

        public void SetKickMode(bool globalKick)
        {
            useGlobalKick = globalKick;
        }

        public void SetViewMode(LaneViewMode mode)
        {
            viewMode = mode;
        }

        public void SetPlayfield(PlaybackPlayfield playfield)
        {
            this.playfield = playfield;
        }

        public void UpdateState(double currentTime, float drawWidth, float drawHeight, float spawnTop, float hitLineY, float travelDistance, float laneWidth, int totalLanes, int visibleLanes, int kickLaneIndex, LaneViewMode mode, bool kickGlobal)
        {
            if (markers.Count == 0 || drawWidth <= 0 || travelDistance <= 0)
            {
                deactivateLines(0);
                return;
            }

            viewMode = mode;
            useGlobalKick = kickGlobal;
            _ = laneWidth;
            _ = totalLanes;
            _ = visibleLanes;
            _ = kickLaneIndex;
            _ = spawnTop;

            double previewWindow = (playfield?.ApproachDuration ?? 5000) * previewMultiplier;
            double cutoffPast = -pastAllowance;

            int activeCount = 0;
            foreach (var marker in markers)
            {
                double delta = marker.Time - currentTime;
                if (delta < cutoffPast)
                    continue;

                if (delta > previewWindow)
                    break;

                float progress = (float)(1 - (delta / (playfield?.ApproachDuration ?? 5000)));
                float clampedProgress = Math.Clamp(progress, 0f, 1.1f);
                float y = hitLineY - travelDistance * (1 - clampedProgress);
                y = Math.Clamp(y, spawnTop, hitLineY + 32f);

                var line = getLine(activeCount++);
                line.UpdateVisual(drawHeight, y, marker.Type, viewMode);
            }

            deactivateLines(activeCount);
        }

        private void deactivateLines(int activeLineCount)
        {
            for (int i = activeLineCount; i < lineBuffer.Count; i++)
                lineBuffer[i].Deactivate();
        }

        private DrawableGridLine getLine(int index)
        {
            while (lineBuffer.Count <= index)
            {
                var line = new DrawableGridLine();
                line.Alpha = 0;
                lineBuffer.Add(line);
                AddInternal(line);
            }

            return lineBuffer[index];
        }

        private void rebuildMarkers(Beatmap beatmap)
        {
            markers.Clear();

            if (beatmap == null)
                return;

            double endTime = beatmap.HitObjects.Count > 0
                ? beatmap.HitObjects[^1].Time + 8000
                : 180000;

            double offset = beatmap.Timing?.Offset ?? 0;
            double bpm = beatmap.Timing?.Bpm ?? 120;
            string signature = beatmap.Timing?.TimeSignature ?? "4/4";

            var timingPoints = beatmap.Timing?.TimingPoints
                ?.OrderBy(tp => tp.Time)
                .ToList() ?? new List<TimingPoint>();

            double segmentStart = offset;
            double currentBpm = bpm;
            string currentSignature = signature;

            foreach (var timingPoint in timingPoints)
            {
                double segmentEnd = Math.Max(segmentStart, timingPoint.Time);
                emitMarkers(segmentStart, segmentEnd, currentBpm, currentSignature);

                segmentStart = Math.Max(segmentStart, timingPoint.Time);
                if (timingPoint.Bpm > 0)
                    currentBpm = timingPoint.Bpm;
                if (!string.IsNullOrWhiteSpace(timingPoint.TimeSignature))
                    currentSignature = timingPoint.TimeSignature!;
            }

            emitMarkers(segmentStart, endTime, currentBpm, currentSignature);
        }

        private void emitMarkers(double startTime, double endTime, double bpm, string signature)
        {
            if (bpm <= 0)
                bpm = 120;

            var (beatsPerMeasure, beatUnit) = parseSignature(signature);
            double beatLength = 60000.0 / bpm;
            double measureLength = beatLength * beatsPerMeasure;

            if (measureLength <= 0)
                return;

            double time = startTime;
            if (time < 0)
                time = 0;

            // ensure we align to measure boundaries
            if (beatLength > 0)
            {
                double remainder = (time - startTime) % beatLength;
                if (remainder != 0)
                    time += beatLength - remainder;
            }

            while (time <= endTime && markers.Count < 20000)
            {
                for (int beat = 0; beat < beatsPerMeasure && time <= endTime; beat++)
                {
                    markers.Add(new GridMarker(time, beat == 0 ? GridMarkerType.Measure : GridMarkerType.Beat));

                    int subdivisions = beatUnit switch
                    {
                        4 => 4,
                        8 => 3,
                        16 => 2,
                        _ => 2
                    };

                    double subdivisionLength = beatLength / subdivisions;
                    if (subdivisionLength >= 45)
                    {
                        for (int s = 1; s < subdivisions; s++)
                        {
                            double subTime = time + subdivisionLength * s;
                            if (subTime > endTime)
                                break;

                            markers.Add(new GridMarker(subTime, GridMarkerType.Subdivision));
                        }
                    }

                    time += beatLength;
                }
            }
        }

        private static (int beatsPerMeasure, int beatUnit) parseSignature(string signature)
        {
            if (string.IsNullOrWhiteSpace(signature))
                return (4, 4);

            var parts = signature.Split('/');
            if (parts.Length != 2)
                return (4, 4);

            if (!int.TryParse(parts[0], out int beats))
                beats = 4;
            if (!int.TryParse(parts[1], out int unit))
                unit = 4;

            beats = Math.Clamp(beats, 1, 16);
            unit = unit switch
            {
                1 or 2 or 4 or 8 or 16 or 32 => unit,
                _ => 4
            };

            return (beats, unit);
        }

        private readonly struct GridMarker
        {
            public GridMarker(double time, GridMarkerType type)
            {
                Time = time;
                Type = type;
            }

            public double Time { get; }
            public GridMarkerType Type { get; }
        }

        private enum GridMarkerType
        {
            Measure,
            Beat,
            Subdivision
        }

        private sealed partial class DrawableGridLine : CompositeDrawable
        {
            private readonly Box line;
            private readonly Box glow;

            public DrawableGridLine()
            {
                RelativeSizeAxes = Axes.X;
                Anchor = Anchor.BottomCentre;
                Origin = Anchor.BottomCentre;
                Height = 2;
                AlwaysPresent = true;

                line = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(255, 255, 255, 180)
                };

                glow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Alpha = 0.25f,
                    Blending = BlendingParameters.Additive
                };

                InternalChildren = new Drawable[]
                {
                    glow,
                    line
                };
            }

            public void UpdateVisual(float drawHeight, float absoluteY, GridMarkerType type, LaneViewMode mode)
            {
                float offset = Math.Max(0, drawHeight - absoluteY);
                Y = -offset;

                if (mode == LaneViewMode.Manuscript)
                {
                    Height = type == GridMarkerType.Measure ? 3f : 1f;
                    Width = 0.6f; // Narrower, just covering the staff
                    Shear = Vector2.Zero;

                    Color4 inkColour = type == GridMarkerType.Measure
                        ? Color4.Black
                        : new Color4(0, 0, 0, 100);

                    line.Colour = inkColour;
                    glow.Alpha = 0;
                    this.FadeTo(1f, 80, Easing.OutQuint);
                    return;
                }

                float thickness = type switch
                {
                    GridMarkerType.Measure => 6f,
                    GridMarkerType.Beat => 3f,
                    _ => 2f
                };

                Height = thickness;

                float widthFactor = mode == LaneViewMode.ThreeDimensional ? 0.9f : 1.0f;
                Width = widthFactor;
                Shear = mode == LaneViewMode.ThreeDimensional ? new Vector2(-0.24f, 0) : Vector2.Zero;

                Color4 lineColour = type switch
                {
                    GridMarkerType.Measure => new Color4(255, 216, 180, 235),
                    GridMarkerType.Beat => new Color4(186, 205, 255, 220),
                    _ => new Color4(120, 132, 182, 180)
                };

                float targetAlpha = type switch
                {
                    GridMarkerType.Measure => 0.82f,
                    GridMarkerType.Beat => 0.58f,
                    _ => 0.36f
                };

                line.Colour = lineColour;
                glow.Colour = UITheme.Emphasise(lineColour, 1.25f);
                glow.Alpha = targetAlpha * 0.4f;
                this.FadeTo(targetAlpha, 80, Easing.OutQuint);
            }

            public void Deactivate()
            {
                this.FadeOut(140, Easing.OutQuint);
            }
        }
    }
}
