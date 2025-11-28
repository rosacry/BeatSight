// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// Enhanced timing grid overlay with better visual hierarchy,
    /// measure numbers, and BPM-aware rendering.
    /// </summary>
    internal sealed partial class TimingGridOverlayEnhanced : CompositeDrawable
    {
        #region State

        private readonly List<GridMarker> markers = new();
        private readonly List<DrawableGridLineEnhanced> lineBuffer = new();
        private readonly List<MeasureNumber> measureNumberBuffer = new();

        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private bool useGlobalKick = true;
        private LaneLayout? laneLayout;
        private PlaybackPlayfield? playfield;

        private double currentBpm = 120;
        private int beatsPerMeasure = 4;

        #endregion

        #region Configuration

        private Bindable<bool> showSubdivisions = null!;
        private Bindable<bool> showMeasureNumbers = null!;
        private Bindable<float> gridOpacity = null!;

        #endregion

        #region Constants

        private const double preview_multiplier = 1.7;
        private const double past_allowance = 320;
        private const int max_markers = 20000;
        private const float measure_number_offset = 20f;

        #endregion

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager config)
        {
            // These settings may not exist yet - use defaults if not available
            showSubdivisions = new Bindable<bool>(true);
            showMeasureNumbers = new Bindable<bool>(true);
            gridOpacity = new BindableFloat(0.8f);

            RelativeSizeAxes = Axes.Both;
            AlwaysPresent = true;
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            gridOpacity.BindValueChanged(v => this.FadeTo(v.NewValue, 200), true);
        }

        #region Public API

        public void Configure(Beatmap beatmap, LaneLayout layout, bool globalKick)
        {
            laneLayout = layout;
            useGlobalKick = globalKick;
            RebuildMarkers(beatmap);
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

        public void UpdateState(
            double currentTime,
            float drawWidth,
            float drawHeight,
            float spawnTop,
            float hitLineY,
            float travelDistance,
            float laneWidth,
            int totalLanes,
            int visibleLanes,
            int kickLaneIndex,
            LaneViewMode mode,
            bool kickGlobal)
        {
            if (markers.Count == 0 || drawWidth <= 0 || travelDistance <= 0)
            {
                DeactivateLines(0);
                DeactivateMeasureNumbers(0);
                return;
            }

            viewMode = mode;
            useGlobalKick = kickGlobal;

            double previewWindow = (playfield?.ApproachDuration ?? 5000) * preview_multiplier;
            double cutoffPast = -past_allowance;

            int activeLineCount = 0;
            int activeMeasureCount = 0;

            foreach (var marker in markers)
            {
                double delta = marker.Time - currentTime;

                if (delta < cutoffPast)
                    continue;

                if (delta > previewWindow)
                    break;

                // Skip subdivisions if disabled
                if (marker.Type == GridMarkerType.Subdivision && !showSubdivisions.Value)
                    continue;

                float progress = (float)(1 - (delta / (playfield?.ApproachDuration ?? 5000)));
                float clampedProgress = Math.Clamp(progress, 0f, 1.1f);
                float y = hitLineY - travelDistance * (1 - clampedProgress);
                y = Math.Clamp(y, spawnTop, hitLineY + 32f);

                var line = GetLine(activeLineCount++);
                line.UpdateVisual(drawWidth, drawHeight, y, marker.Type, viewMode, currentBpm, beatsPerMeasure);

                // Show measure numbers for measure lines
                if (marker.Type == GridMarkerType.Measure && showMeasureNumbers.Value && viewMode != LaneViewMode.Manuscript)
                {
                    var measureNumber = GetMeasureNumber(activeMeasureCount++);
                    measureNumber.UpdateVisual(y, marker.MeasureNumber, viewMode);
                }
            }

            DeactivateLines(activeLineCount);
            DeactivateMeasureNumbers(activeMeasureCount);
        }

        #endregion

        #region Line Management

        private DrawableGridLineEnhanced GetLine(int index)
        {
            while (lineBuffer.Count <= index)
            {
                var line = new DrawableGridLineEnhanced();
                line.Alpha = 0;
                lineBuffer.Add(line);
                AddInternal(line);
            }

            return lineBuffer[index];
        }

        private void DeactivateLines(int activeCount)
        {
            for (int i = activeCount; i < lineBuffer.Count; i++)
                lineBuffer[i].Deactivate();
        }

        private MeasureNumber GetMeasureNumber(int index)
        {
            while (measureNumberBuffer.Count <= index)
            {
                var number = new MeasureNumber();
                number.Alpha = 0;
                measureNumberBuffer.Add(number);
                AddInternal(number);
            }

            return measureNumberBuffer[index];
        }

        private void DeactivateMeasureNumbers(int activeCount)
        {
            for (int i = activeCount; i < measureNumberBuffer.Count; i++)
                measureNumberBuffer[i].Deactivate();
        }

        #endregion

        #region Marker Generation

        private void RebuildMarkers(Beatmap beatmap)
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

            currentBpm = bpm;

            var timingPoints = beatmap.Timing?.TimingPoints
                ?.OrderBy(tp => tp.Time)
                .ToList() ?? new List<TimingPoint>();

            double segmentStart = offset;
            double currentBpmLocal = bpm;
            string currentSignature = signature;
            int measureCounter = 1;

            foreach (var timingPoint in timingPoints)
            {
                double segmentEnd = Math.Max(segmentStart, timingPoint.Time);
                measureCounter = EmitMarkers(segmentStart, segmentEnd, currentBpmLocal, currentSignature, measureCounter);

                segmentStart = Math.Max(segmentStart, timingPoint.Time);
                if (timingPoint.Bpm > 0)
                {
                    currentBpmLocal = timingPoint.Bpm;
                    currentBpm = currentBpmLocal;
                }
                if (!string.IsNullOrWhiteSpace(timingPoint.TimeSignature))
                    currentSignature = timingPoint.TimeSignature!;
            }

            EmitMarkers(segmentStart, endTime, currentBpmLocal, currentSignature, measureCounter);

            var (beats, _) = ParseSignature(signature);
            beatsPerMeasure = beats;
        }

        private int EmitMarkers(double startTime, double endTime, double bpm, string signature, int measureNumber)
        {
            if (bpm <= 0)
                bpm = 120;

            var (beatsPerMeasureLocal, beatUnit) = ParseSignature(signature);
            double beatLength = 60000.0 / bpm;
            double measureLength = beatLength * beatsPerMeasureLocal;

            if (measureLength <= 0)
                return measureNumber;

            double time = startTime;
            if (time < 0)
                time = 0;

            // Align to measure boundaries
            if (beatLength > 0)
            {
                double remainder = (time - startTime) % beatLength;
                if (remainder != 0)
                    time += beatLength - remainder;
            }

            while (time <= endTime && markers.Count < max_markers)
            {
                for (int beat = 0; beat < beatsPerMeasureLocal && time <= endTime; beat++)
                {
                    bool isMeasure = beat == 0;
                    markers.Add(new GridMarker(
                        time,
                        isMeasure ? GridMarkerType.Measure : GridMarkerType.Beat,
                        isMeasure ? measureNumber : 0,
                        beat
                    ));

                    if (isMeasure)
                        measureNumber++;

                    // Subdivisions based on beat unit
                    int subdivisions = beatUnit switch
                    {
                        4 => 4,  // 16th notes
                        8 => 3,  // Triplets
                        16 => 2, // 32nd notes
                        _ => 2
                    };

                    double subdivisionLength = beatLength / subdivisions;

                    // Only add subdivisions if they're reasonably spaced
                    if (subdivisionLength >= 45)
                    {
                        for (int s = 1; s < subdivisions; s++)
                        {
                            double subTime = time + subdivisionLength * s;
                            if (subTime > endTime)
                                break;

                            markers.Add(new GridMarker(subTime, GridMarkerType.Subdivision, 0, beat));
                        }
                    }

                    time += beatLength;
                }
            }

            return measureNumber;
        }

        private static (int beatsPerMeasure, int beatUnit) ParseSignature(string signature)
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

        #endregion

        #region Supporting Types

        private readonly struct GridMarker
        {
            public double Time { get; }
            public GridMarkerType Type { get; }
            public int MeasureNumber { get; }
            public int BeatInMeasure { get; }

            public GridMarker(double time, GridMarkerType type, int measureNumber, int beatInMeasure)
            {
                Time = time;
                Type = type;
                MeasureNumber = measureNumber;
                BeatInMeasure = beatInMeasure;
            }
        }

        private enum GridMarkerType
        {
            Measure,
            Beat,
            Subdivision
        }

        #endregion

        #region Drawable Components

        /// <summary>
        /// Enhanced grid line with better visual design using the design system.
        /// </summary>
        private sealed partial class DrawableGridLineEnhanced : CompositeDrawable
        {
            private readonly Box line;
            private readonly Box glow;
            private readonly Box accentStripe;

            public DrawableGridLineEnhanced()
            {
                RelativeSizeAxes = Axes.X;
                Anchor = Anchor.BottomCentre;
                Origin = Anchor.BottomCentre;
                Height = 2;
                AlwaysPresent = true;

                InternalChildren = new Drawable[]
                {
                    glow = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Alpha = 0,
                        Blending = BlendingParameters.Additive,
                    },
                    line = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                    },
                    accentStripe = new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 1,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Alpha = 0,
                    },
                };
            }

            public void UpdateVisual(float drawWidth, float drawHeight, float absoluteY, GridMarkerType type, LaneViewMode mode, double bpm, int beatsPerMeasure)
            {
                float offset = Math.Max(0, drawHeight - absoluteY);
                Y = -offset;

                // Manuscript view styling
                if (mode == LaneViewMode.Manuscript)
                {
                    UpdateManuscriptStyle(type);
                    return;
                }

                // 3D view styling
                if (mode == LaneViewMode.ThreeDimensional)
                {
                    Update3DStyle(type, absoluteY, drawHeight);
                    return;
                }

                // 2D view styling (default)
                Update2DStyle(type);
            }

            private void UpdateManuscriptStyle(GridMarkerType type)
            {
                Shear = Vector2.Zero;
                Width = 0.6f;

                (float thickness, Color4 color, float alpha) = type switch
                {
                    GridMarkerType.Measure => (2f, DesignSystem.ColorMeasureLine.Darken(0.5f), 0.9f),
                    GridMarkerType.Beat => (1f, DesignSystem.ColorBeatLine.Darken(0.3f), 0.5f),
                    _ => (1f, DesignSystem.ColorSubdivisionLine.Darken(0.2f), 0.25f),
                };

                Height = thickness;
                line.Colour = color;
                glow.Alpha = 0;
                accentStripe.Alpha = 0;

                // Set alpha directly instead of using transforms to prevent accumulation
                Alpha = alpha;
            }

            private void Update3DStyle(GridMarkerType type, float y, float drawHeight)
            {
                // Apply perspective shear
                Shear = new Vector2(DesignSystem.HighwayShear, 0);
                Width = DesignSystem.HighwayWidthFactor;

                // Calculate depth-based fade
                float depthProgress = y / drawHeight;
                float depthFade = MathF.Pow(depthProgress, 0.5f);

                (float thickness, Color4 color, float baseAlpha) = type switch
                {
                    GridMarkerType.Measure => (4f, DesignSystem.ColorMeasureLine, 0.85f),
                    GridMarkerType.Beat => (2f, DesignSystem.ColorBeatLine, 0.6f),
                    _ => (1f, DesignSystem.ColorSubdivisionLine, 0.35f),
                };

                Height = thickness * (0.5f + depthFade * 0.5f);
                line.Colour = color;

                // Glow effect for measure lines
                if (type == GridMarkerType.Measure)
                {
                    glow.Colour = color.Lighten(0.3f);
                    glow.Alpha = 0.3f * depthFade;
                }
                else
                {
                    glow.Alpha = 0;
                }

                accentStripe.Alpha = 0;

                float targetAlpha = baseAlpha * depthFade;
                // Set alpha directly instead of using transforms to prevent accumulation
                Alpha = targetAlpha;
            }

            private void Update2DStyle(GridMarkerType type)
            {
                Shear = Vector2.Zero;
                Width = 1f;

                (float thickness, Color4 color, float alpha, bool showAccent) = type switch
                {
                    GridMarkerType.Measure => (3f, DesignSystem.ColorMeasureLine, 0.9f, true),
                    GridMarkerType.Beat => (2f, DesignSystem.ColorBeatLine, 0.65f, false),
                    _ => (1f, DesignSystem.ColorSubdivisionLine, 0.4f, false),
                };

                Height = thickness;
                line.Colour = color;

                // Subtle glow for measure lines
                if (type == GridMarkerType.Measure)
                {
                    glow.Colour = color.Lighten(0.2f);
                    glow.Alpha = 0.2f;
                }
                else
                {
                    glow.Alpha = 0;
                }

                // Accent stripe on measure lines
                if (showAccent)
                {
                    accentStripe.Colour = DesignSystem.ColorAccent;
                    accentStripe.Alpha = 0.4f;
                }
                else
                {
                    accentStripe.Alpha = 0;
                }

                // Set alpha directly instead of using transforms to prevent accumulation
                Alpha = alpha;
            }

            public void Deactivate()
            {
                // Clear any pending transforms to prevent accumulation, then fade out
                this.ClearTransforms();
                this.FadeOut(DesignSystem.AnimationMedium, Easing.OutQuint);
            }
        }

        /// <summary>
        /// Measure number display that appears alongside measure lines.
        /// </summary>
        private sealed partial class MeasureNumber : CompositeDrawable
        {
            private readonly SpriteText text;
            private readonly Box background;

            public MeasureNumber()
            {
                AutoSizeAxes = Axes.Both;
                Anchor = Anchor.BottomLeft;
                Origin = Anchor.CentreLeft;
                AlwaysPresent = true;

                InternalChildren = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.Opacity(DesignSystem.ColorSurface, 0.7f),
                    },
                    text = new SpriteText
                    {
                        Font = FontUsage.Default.With(size: 12, weight: "SemiBold"),
                        Colour = DesignSystem.ColorMeasureLine,
                        Padding = new MarginPadding { Horizontal = 4, Vertical = 2 },
                    },
                };

                Masking = true;
                CornerRadius = 3;
            }

            public void UpdateVisual(float y, int measureNumber, LaneViewMode mode)
            {
                Y = -(DrawHeight - y) + Height / 2;
                X = measure_number_offset;

                text.Text = measureNumber.ToString();

                float targetAlpha = mode == LaneViewMode.ThreeDimensional ? 0.6f : 0.8f;
                // Set alpha directly instead of using transforms to prevent accumulation
                Alpha = targetAlpha;
            }

            public void Deactivate()
            {
                // Clear any pending transforms to prevent accumulation, then fade out
                this.ClearTransforms();
                this.FadeOut(DesignSystem.AnimationMedium, Easing.OutQuint);
            }
        }

        #endregion
    }
}
