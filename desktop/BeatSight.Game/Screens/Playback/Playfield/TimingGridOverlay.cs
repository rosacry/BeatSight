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
        private int snapDivisor = 4;

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
            snapDivisor = Math.Max(1, beatmap.Editor?.SnapDivisor ?? 4);
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
            if (viewMode == LaneViewMode.Manuscript)
            {
                // Manuscript now draws timeline markers in its own background layer.
                deactivateLines(0);
                return;
            }

            useGlobalKick = kickGlobal;
            _ = laneWidth;
            _ = totalLanes;
            _ = visibleLanes;
            _ = kickLaneIndex;
            _ = spawnTop;

            double approachDuration = playfield?.ApproachDuration ?? 5000;
            bool simplifyForThreeDimensional = viewMode == LaneViewMode.ThreeDimensional;
            double previewWindow = simplifyForThreeDimensional
                ? approachDuration * 0.72
                : approachDuration * previewMultiplier;
            double cutoffPast = -pastAllowance;
            float previousRenderedY = float.NegativeInfinity;

            int activeCount = 0;
            foreach (var marker in markers)
            {
                if (simplifyForThreeDimensional && marker.Type == GridMarkerType.Subdivision)
                    continue;

                if (simplifyForThreeDimensional
                    && marker.Type == GridMarkerType.Beat
                    && marker.BeatInMeasure != 2)
                    continue;

                double delta = marker.Time - currentTime;
                if (delta < cutoffPast)
                    continue;

                if (simplifyForThreeDimensional && marker.Type == GridMarkerType.Beat)
                {
                    float beatProgress = (float)(1 - (delta / approachDuration));
                    if (beatProgress < 0.28f)
                        continue;
                }

                if (delta > previewWindow)
                    break;

                float progress = (float)(1 - (delta / approachDuration));
                float clampedProgress = Math.Clamp(progress, 0f, 1.1f);
                float y = hitLineY - travelDistance * (1 - clampedProgress);
                y = Math.Clamp(y, spawnTop, hitLineY + 32f);

                if (simplifyForThreeDimensional)
                {
                    if (Math.Abs(y - previousRenderedY) < 38f)
                        continue;

                    previousRenderedY = y;
                }

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
            double bpm = beatmap.Timing?.Bpm ?? TimingInfo.DefaultBpm;
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
                bpm = TimingInfo.DefaultBpm;

            var (beatsPerMeasure, _) = parseSignature(signature);
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

            while (time <= endTime && markers.Count < 120000)
            {
                for (int beat = 0; beat < beatsPerMeasure && time <= endTime; beat++)
                {
                    markers.Add(new GridMarker(time, beat == 0 ? GridMarkerType.Measure : GridMarkerType.Beat, beat));

                    int subdivisions = Math.Clamp(snapDivisor, 1, 32);

                    double subdivisionLength = beatLength / subdivisions;
                    if (subdivisionLength >= 45)
                    {
                        for (int s = 1; s < subdivisions; s++)
                        {
                            double subTime = time + subdivisionLength * s;
                            if (subTime > endTime)
                                break;

                            markers.Add(new GridMarker(subTime, GridMarkerType.Subdivision, beat));
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
            public GridMarker(double time, GridMarkerType type, int beatInMeasure = 0)
            {
                Time = time;
                Type = type;
                BeatInMeasure = beatInMeasure;
            }

            public double Time { get; }
            public GridMarkerType Type { get; }
            public int BeatInMeasure { get; }
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
                    Height = 2.2f;
                    Width = 0.66f;
                    Shear = Vector2.Zero;

                    Color4 inkColour = new Color4(18, 22, 30, 184);

                    line.Colour = inkColour;
                    glow.Alpha = 0;
                    // Set alpha directly instead of using transforms to prevent accumulation
                    Alpha = 0.56f;
                    return;
                }

                float thickness = type switch
                {
                    GridMarkerType.Measure => 6f,
                    GridMarkerType.Beat => 3f,
                    _ => 2f
                };
                if (mode == LaneViewMode.ThreeDimensional)
                    thickness *= 0.46f;

                Height = thickness;

                float widthFactor = mode == LaneViewMode.ThreeDimensional ? 0.72f : 1.0f;
                Width = widthFactor;
                Shear = Vector2.Zero;

                Color4 lineColour = mode == LaneViewMode.ThreeDimensional
                    ? type switch
                    {
                        GridMarkerType.Measure => new Color4(210, 198, 176, 188),
                        GridMarkerType.Beat => new Color4(118, 148, 194, 148),
                        _ => new Color4(76, 96, 130, 94)
                    }
                    : type switch
                    {
                        GridMarkerType.Measure => new Color4(255, 216, 180, 235),
                        GridMarkerType.Beat => new Color4(186, 205, 255, 220),
                        _ => new Color4(120, 132, 182, 180)
                    };

                float targetAlpha = mode == LaneViewMode.ThreeDimensional
                    ? type switch
                    {
                        GridMarkerType.Measure => 0.18f,
                        GridMarkerType.Beat => 0.07f,
                        _ => 0.04f
                    }
                    : type switch
                    {
                        GridMarkerType.Measure => 0.82f,
                        GridMarkerType.Beat => 0.58f,
                        _ => 0.36f
                    };

                line.Colour = lineColour;
                glow.Colour = UITheme.Emphasise(lineColour, mode == LaneViewMode.ThreeDimensional ? 1.08f : 1.25f);
                glow.Alpha = targetAlpha * (mode == LaneViewMode.ThreeDimensional ? 0.12f : 0.4f);
                // Set alpha directly instead of using transforms to prevent accumulation
                Alpha = targetAlpha;
            }

            public void Deactivate()
            {
                this.ClearTransforms();
                Alpha = 0;
            }
        }
    }
}
