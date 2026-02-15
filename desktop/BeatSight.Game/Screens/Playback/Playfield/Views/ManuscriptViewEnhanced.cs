using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// Redesigned manuscript view renderer (traditional drum notation style).
    /// 
    /// Key improvements:
    /// - Proper staff notation layout following standard percussion conventions
    /// - Clean, musician-friendly visual design
    /// - Better component-to-position mapping
    /// - Support for dynamics and articulation visualization
    /// - Cleaner playhead and measure markers
    /// - **Playback position highlighter** - A sweeping highlight overlay that moves
    ///   left-to-right across the staff, with its right edge indicating the current
    ///   playback position for timing reference.
    /// 
    /// Notes are placed on a staff following standard percussion notation,
    /// designed for musicians familiar with reading sheet music.
    /// </summary>
    public class ManuscriptViewEnhanced : PlayfieldViewBaseEnhanced
    {
        public override Configuration.LaneViewMode ViewMode => Configuration.LaneViewMode.Manuscript;

        // Position constants
        public override float HitLineYRatio => DesignSystem.HitLineRatioManuscript;
        public override float SpawnYRatio => 0f;

        // Staff layout constants
        private const float NoteheadDiameter = 16f;
        private const float StemLength = 38f;
        private const float StemWidth = 1.5f;

        private ManuscriptBackgroundEnhanced? backgroundDrawable;

        /// <summary>
        /// Bindable to control whether the playback position highlighter is enabled.
        /// When true, a semi-transparent overlay sweeps across the staff indicating timing.
        /// </summary>
        public readonly BindableBool ShowPlaybackHighlighter = new BindableBool(true);

        #region Background Creation

        public override Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick)
        {
            backgroundDrawable = new ManuscriptBackgroundEnhanced();

            // Bind the highlighter visibility to our setting
            backgroundDrawable.PlaybackHighlighter.Enabled.BindTo(ShowPlaybackHighlighter);

            return backgroundDrawable;
        }

        /// <summary>
        /// Update the playback position highlighter.
        /// Should be called each frame with the current playback time.
        /// </summary>
        public override void UpdateBackground(double currentTimeMs)
        {
            base.UpdateBackground(currentTimeMs);
            backgroundDrawable?.UpdatePlaybackPosition(currentTimeMs, CurrentBpm);
        }

        /// <summary>
        /// Load hit objects into the highlighter for per-note glow effects.
        /// </summary>
        public override void LoadBeatmap(Beatmap beatmap)
        {
            base.LoadBeatmap(beatmap);

            // Convert beatmap hit objects to highlighter format
            if (beatmap?.HitObjects != null && backgroundDrawable != null)
            {
                var hitObjectInfos = new List<HitObjectInfo>();
                for (int i = 0; i < beatmap.HitObjects.Count; i++)
                {
                    var ho = beatmap.HitObjects[i];
                    hitObjectInfos.Add(new HitObjectInfo
                    {
                        Index = i,
                        TimeMs = ho.Time,
                        ComponentName = ho.Component ?? "snare",
                        XPosition = ManuscriptBackgroundEnhanced.GetStaffPositionForComponent(ho.Component ?? "snare"),
                        YPosition = 0 // Will be calculated dynamically based on scroll position
                    });
                }
                backgroundDrawable.PlaybackHighlighter.LoadHitObjects(hitObjectInfos);
            }
        }

        #endregion

        #region Strike Zone Creation

        public override Drawable CreateStrikeZone()
        {
            return new ManuscriptStrikeZoneEnhanced();
        }

        #endregion

        #region Note Position Updates

        public override void UpdateNotePosition(
            DrawableNote note,
            float progress,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            NotePositionContext ctx)
        {
            // Calculate Y position (notes scroll top to bottom)
            float y = CalculateY(progress, hitLineY, travelDistance);

            // Calculate X position based on component (staff position)
            float x = CalculateManuscriptX(note.ComponentName, drawWidth);

            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;

            // Fade notes that pass the hit line
            note.Alpha = IsNoteVisible(y, hitLineY, note.Height) ? 1 : 0;
        }

        public override void ApplyNoteStyle(DrawableNote note)
        {
            note.SetViewMode(Configuration.LaneViewMode.Manuscript);
        }

        #endregion
    }

    /// <summary>
    /// Enhanced manuscript-style background with traditional staff lines.
    /// Designed to look like professional sheet music paper.
    /// Includes a playback position highlighter for timing guidance.
    /// </summary>
    internal partial class ManuscriptBackgroundEnhanced : CompositeDrawable
    {
        public enum ManuscriptNotationVoice
        {
            Lower = 0,
            Upper = 1
        }

        private const float ManuscriptStaffWidthRatio = 0.84f;
        private const float ManuscriptStaffHeightRatio = 0.86f;
        private const float ManuscriptStaffCenterYRatio = 0.56f;
        private const float StaffUnitMin = -3.5f;
        private const float StaffUnitMax = 3.5f;
        private const float StaffUnitRange = StaffUnitMax - StaffUnitMin;
        private const float BaseGuideAlpha = 0.010f;

        // Staff dimensions
        private const int StaffLineCount = 5;
        private const float LineThickness = 1.2f;
        private const float LedgerLineThickness = 0.9f;
        private const int LedgerLinesAbove = 2;
        private const int LedgerLinesBelow = 2;

        // Dark sheet music colors inspired by modern tab readers.
        private static readonly Color4 PaperBackground = new Color4(16, 22, 33, 255);
        private static readonly Color4 PaperVignette = new Color4(10, 14, 22, 255);
        private static readonly Color4 StaffLineColor = new Color4(206, 218, 238, 218);
        private static readonly Color4 LedgerLineColor = new Color4(170, 186, 214, 168);
        private static readonly Color4 LabelColor = new Color4(220, 232, 248, 228);

        private Container? staffContainer;
        private Container? timelineMeasureBandLayer;
        private Container? timelineMarkerLayer;
        private Container? timelinePlayheadCountInLayer;
        private Container? timelineTupletLabelLayer;
        private Container? timelineMeasureLabelLayer;
        private ClefIndicatorEnhanced? clefIndicator;
        private readonly List<(Box Line, float Unit)> staffGuideLines = new();
        private readonly List<ComponentGuideVisual> componentGuideVisuals = new();
        private readonly List<Box> timelineMeasureBands = new();
        private readonly List<Box> timelineMarkers = new();
        private readonly List<Box> timelinePlayheadCountInTicks = new();
        private readonly List<SpriteText> timelinePlayheadCountInLabels = new();
        private readonly List<SpriteText> timelineTupletLabels = new();
        private readonly List<Box> timelineTupletBracketRails = new();
        private readonly List<Box> timelineTupletBracketLeftHooks = new();
        private readonly List<Box> timelineTupletBracketRightHooks = new();
        private readonly List<SpriteText> timelineMeasureLabels = new();
        private SpriteText? timelinePlayheadLabel;
        private string? focusedGuideKey;
        private double timelineStartMs;
        private double timelineDurationMs;
        private float timelineLeftX;
        private float timelineRightX;
        private float timelinePlayheadX;
        private bool hasTimelineWindow;
        private double timelineBpm = 120;
        private double timelineBeatOriginMs;
        private int timelineBeatsPerMeasure = 4;
        private int timelineSubdivisionDivisor = 1;
        private bool timelineWindowDirty;
        private ManuscriptCountInGuideMode countInGuideMode = ManuscriptCountInGuideMode.Full;

        private sealed record ComponentGuide(string Key, string Label, float Unit, Color4 Color);

        private sealed class ComponentGuideVisual
        {
            public ComponentGuideVisual(ComponentGuide guide, Box fill, Box rail, SpriteText topLabel, SpriteText bottomLabel)
            {
                Guide = guide;
                Fill = fill;
                Rail = rail;
                TopLabel = topLabel;
                BottomLabel = bottomLabel;
            }

            public ComponentGuide Guide { get; }
            public Box Fill { get; }
            public Box Rail { get; }
            public SpriteText TopLabel { get; }
            public SpriteText BottomLabel { get; }
        }

        private static readonly ComponentGuide[] componentGuides =
        {
            new("kick", "KK", -3.5f, DesignSystem.ColorKick),
            new("hihat", "HH", -2.5f, DesignSystem.ColorHiHat),
            new("snare", "SN", -1.5f, DesignSystem.ColorSnare),
            new("tom_high", "T1", -0.5f, DesignSystem.ColorTomHigh),
            new("tom_mid", "T2", 0.5f, DesignSystem.ColorTomMid),
            new("tom_low", "T3", 1.5f, DesignSystem.ColorTomLow),
            new("ride", "RD", 2.5f, DesignSystem.ColorRide),
            new("crash", "CR", 3.5f, DesignSystem.ColorCrash)
        };

        private static readonly string[] notationCycleComponents =
        {
            "kick",
            "hihat",
            "snare",
            "tom_high",
            "tom_mid",
            "tom_low",
            "ride",
            "crash"
        };

        /// <summary>
        /// The playback position highlighter that sweeps across the staff.
        /// </summary>
        public ManuscriptPlaybackHighlighter PlaybackHighlighter { get; private set; } = null!;

        public ManuscriptBackgroundEnhanced()
        {
            RelativeSizeAxes = Axes.Both;
            BuildVisuals();
        }

        private void BuildVisuals()
        {
            // Paper background with subtle gradient
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(PaperBackground, PaperVignette)
            });

            // Subtle top vignette for depth
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    new Color4(88, 118, 168, 24),
                    Color4.Transparent),
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre
            });

            // Subtle bottom shadow
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    Color4.Transparent,
                    new Color4(0, 0, 0, 36)),
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre
            });

            // Staff container
            staffContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Width = ManuscriptStaffWidthRatio,
                Height = ManuscriptStaffHeightRatio,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };

            timelineMeasureBandLayer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };
            staffContainer.Add(timelineMeasureBandLayer);

            timelineMarkerLayer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };
            staffContainer.Add(timelineMarkerLayer);

            timelinePlayheadCountInLayer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };
            staffContainer.Add(timelinePlayheadCountInLayer);

            timelineTupletLabelLayer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };
            staffContainer.Add(timelineTupletLabelLayer);

            timelineMeasureLabelLayer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };
            staffContainer.Add(timelineMeasureLabelLayer);

            timelinePlayheadLabel = new SpriteText
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Font = new FontUsage("Roboto", 10.4f),
                Colour = new Color4(216, 232, 252, 238),
                Alpha = 0f
            };
            timelineMeasureLabelLayer.Add(timelinePlayheadLabel);

            buildComponentGuides();
            buildStaffLines();

            AddInternal(staffContainer);

            // Playback position highlighter - sweeps across the staff to indicate timing
            PlaybackHighlighter = new ManuscriptPlaybackHighlighter
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                RelativeSizeAxes = Axes.Both,
                Depth = -1 // Render above staff lines but below notes
            };
            AddInternal(PlaybackHighlighter);

            // Percussion clef indicator
            clefIndicator = new ClefIndicatorEnhanced
            {
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Y = 20
            };
            AddInternal(clefIndicator);

            // Component legend (positioned at top right)
            AddInternal(CreateComponentLegend());
        }

        protected override void Update()
        {
            base.Update();

            if (staffContainer != null)
            {
                updateStaffGeometry(DrawWidth, DrawHeight);
            }
        }

        /// <summary>
        /// Update the playback position for the highlighter.
        /// </summary>
        public void UpdatePlaybackPosition(double timeMs, double bpm)
        {
            double sanitizedBpm = Math.Max(1, bpm);
            if (Math.Abs(timelineBpm - sanitizedBpm) > 0.01)
            {
                timelineBpm = sanitizedBpm;
                timelineWindowDirty = true;
            }

            PlaybackHighlighter?.UpdatePlaybackPosition(timeMs, bpm);
        }

        public void SetTimelineWindow(
            double startTimeMs,
            double durationMs,
            float playheadX,
            float leftX,
            float rightX,
            int beatsPerMeasure = 4,
            double beatOriginMs = 0,
            int subdivisionDivisor = 1)
        {
            timelineStartMs = startTimeMs;
            timelineDurationMs = durationMs;
            timelineLeftX = leftX;
            timelineRightX = rightX;
            timelinePlayheadX = playheadX;
            hasTimelineWindow = durationMs > 1 && rightX > leftX;
            timelineBeatsPerMeasure = Math.Max(1, beatsPerMeasure);
            timelineBeatOriginMs = beatOriginMs;
            timelineSubdivisionDivisor = Math.Clamp(subdivisionDivisor, 1, 8);
            timelineWindowDirty = true;
            PlaybackHighlighter?.SetTimelineWindow(startTimeMs, durationMs, playheadX, leftX, rightX);
        }

        public void SetFocusedComponent(string? component)
        {
            string? next = string.IsNullOrWhiteSpace(component)
                ? null
                : mapGuideKey(normalizeComponentKey(component));

            if (string.Equals(focusedGuideKey, next, StringComparison.Ordinal))
                return;

            focusedGuideKey = next;
            updateGuideFocusVisuals();
        }

        public void SetCountInGuideMode(ManuscriptCountInGuideMode mode)
        {
            if (countInGuideMode == mode)
                return;

            countInGuideMode = mode;
            timelineWindowDirty = true;

            if (countInGuideMode == ManuscriptCountInGuideMode.Off)
                clearTimelinePlayheadCountInGuides();
        }

        private void buildStaffLines()
        {
            if (staffContainer == null)
                return;

            // Main 5-line percussion staff.
            for (int i = 0; i < StaffLineCount; i++)
            {
                float unit = i - (StaffLineCount - 1) / 2f;
                addStaffGuideLine(unit, LineThickness, StaffLineColor, 1f);
            }

            for (int i = 1; i <= LedgerLinesAbove; i++)
            {
                float unit = ((StaffLineCount - 1) / 2f) + i;
                addStaffGuideLine(unit, LedgerLineThickness, LedgerLineColor, DesignSystem.LedgerLineOpacity);
            }

            for (int i = 1; i <= LedgerLinesBelow; i++)
            {
                float unit = -(((StaffLineCount - 1) / 2f) + i);
                addStaffGuideLine(unit, LedgerLineThickness, LedgerLineColor, DesignSystem.LedgerLineOpacity);
            }
        }

        private void addStaffGuideLine(float unit, float thickness, Color4 color, float alpha)
        {
            if (staffContainer == null)
                return;

            var line = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = thickness,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = color,
                Alpha = alpha
            };

            staffContainer.Add(line);
            staffGuideLines.Add((line, unit));
        }

        private void buildComponentGuides()
        {
            if (staffContainer == null)
                return;

            foreach (ComponentGuide guide in componentGuides)
            {
                var fill = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Height = 28f,
                    Colour = DesignSystem.WithOpacity(guide.Color, BaseGuideAlpha)
                };

                var rail = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Height = 1.5f,
                    Colour = DesignSystem.WithOpacity(guide.Color, 0.08f)
                };

                var topLabel = new SpriteText
                {
                    Text = guide.Label,
                    Font = new FontUsage("Roboto", 11f),
                    Colour = LabelColor,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft
                };

                var bottomLabel = new SpriteText
                {
                    Text = guide.Label,
                    Font = new FontUsage("Roboto", 10f),
                    Colour = LabelColor,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Alpha = 0f
                };

                staffContainer.Add(fill);
                staffContainer.Add(rail);
                staffContainer.Add(topLabel);
                staffContainer.Add(bottomLabel);

                componentGuideVisuals.Add(new ComponentGuideVisual(guide, fill, rail, topLabel, bottomLabel));
            }

            updateGuideFocusVisuals();
        }

        private void updateStaffGeometry(float drawWidth, float drawHeight)
        {
            float spacing = GetStaffSpacingForDrawArea(drawWidth, drawHeight);
            float laneHeight = Math.Clamp(spacing * 0.80f, 14f, 36f);
            float labelSize = Math.Clamp(drawWidth / 168f, 9.2f, 13.6f);
            float leftLabelInset = Math.Clamp(drawWidth * 0.024f, 18f, 38f);
            float rightLabelInset = Math.Clamp(drawWidth * 0.018f, 14f, 30f);
            float centerY = GetStaffCenterYForDrawHeight(drawHeight);
            float localWidth = staffContainer?.DrawWidth > 0
                ? staffContainer.DrawWidth
                : GetTimelineWidthForDrawWidth(drawWidth);

            foreach (var (line, unit) in staffGuideLines)
                line.Y = centerY - unit * spacing;

            foreach (ComponentGuideVisual visual in componentGuideVisuals)
            {
                float y = centerY - visual.Guide.Unit * spacing;
                visual.Fill.Y = y;
                visual.Fill.Height = laneHeight;
                visual.Fill.Width = 1f;
                visual.Rail.Y = y;
                visual.TopLabel.Y = y;
                visual.BottomLabel.Y = y;
                visual.TopLabel.Font = new FontUsage("Roboto", labelSize);
                visual.BottomLabel.Font = new FontUsage("Roboto", Math.Max(8.4f, labelSize - 0.9f));
                visual.TopLabel.X = leftLabelInset;
                visual.BottomLabel.X = Math.Max(rightLabelInset, localWidth - rightLabelInset);
            }

            float timelineWidth = GetTimelineWidthForDrawWidth(drawWidth);
            PlaybackHighlighter?.SetStaffDimensions(drawWidth / 2f, timelineWidth);
            timelineWindowDirty = true;
            updateTimelineMarkersIfNeeded();
        }

        private void updateGuideFocusVisuals()
        {
            bool hasFocus = !string.IsNullOrWhiteSpace(focusedGuideKey);

            foreach (ComponentGuideVisual visual in componentGuideVisuals)
            {
                bool isFocused = hasFocus && string.Equals(visual.Guide.Key, focusedGuideKey, StringComparison.Ordinal);
                float fillAlpha = hasFocus ? (isFocused ? 0.12f : 0.004f) : BaseGuideAlpha;
                float railAlpha = hasFocus ? (isFocused ? 0.22f : 0.028f) : 0.042f;
                float labelAlpha = hasFocus ? (isFocused ? 0.82f : 0.16f) : 0.18f;
                Color4 guideColor = hasFocus && isFocused ? visual.Guide.Color : StaffLineColor;

                visual.Fill.Colour = DesignSystem.WithOpacity(guideColor, fillAlpha);
                visual.Rail.Colour = DesignSystem.WithOpacity(guideColor, railAlpha);
                visual.TopLabel.Alpha = labelAlpha;
                visual.BottomLabel.Alpha = hasFocus && isFocused ? labelAlpha * 0.32f : 0f;
            }
        }

        private void updateTimelineMarkersIfNeeded()
        {
            if (!timelineWindowDirty)
                return;

            timelineWindowDirty = false;

            if (timelineMarkerLayer == null)
            {
                clearTimelinePlayheadCountInGuides();
                clearTimelineTupletLabels();
                if (timelinePlayheadLabel != null)
                    timelinePlayheadLabel.Alpha = 0f;
                return;
            }

            if (!hasTimelineWindow || timelineDurationMs <= 1)
            {
                for (int i = 0; i < timelineMeasureBands.Count; i++)
                    timelineMeasureBands[i].Alpha = 0f;
                for (int i = 0; i < timelineMarkers.Count; i++)
                    timelineMarkers[i].Alpha = 0f;
                for (int i = 0; i < timelineMeasureLabels.Count; i++)
                    timelineMeasureLabels[i].Alpha = 0f;
                clearTimelinePlayheadCountInGuides();
                clearTimelineTupletLabels();
                if (timelinePlayheadLabel != null)
                    timelinePlayheadLabel.Alpha = 0f;
                return;
            }

            if (timelineRightX - timelineLeftX <= 1f)
            {
                for (int i = 0; i < timelineMeasureBands.Count; i++)
                    timelineMeasureBands[i].Alpha = 0f;
                for (int i = 0; i < timelineMarkers.Count; i++)
                    timelineMarkers[i].Alpha = 0f;
                for (int i = 0; i < timelineMeasureLabels.Count; i++)
                    timelineMeasureLabels[i].Alpha = 0f;
                clearTimelinePlayheadCountInGuides();
                clearTimelineTupletLabels();
                if (timelinePlayheadLabel != null)
                    timelinePlayheadLabel.Alpha = 0f;
                return;
            }

            double beatDuration = 60000.0 / Math.Max(1.0, timelineBpm);
            if (beatDuration <= 1)
                return;

            double windowStart = timelineStartMs;
            double windowEnd = windowStart + timelineDurationMs;
            int beatsPerMeasure = Math.Max(1, timelineBeatsPerMeasure);
            updateTimelineMeasureBands(windowStart, windowEnd, beatDuration, beatsPerMeasure);
            int subdivision = Math.Clamp(timelineSubdivisionDivisor, 1, 8);
            updateTimelineMeasureLabels(windowStart, windowEnd, beatDuration, beatsPerMeasure);
            updateTimelineTupletLabels(windowStart, windowEnd, beatDuration, subdivision);
            double subDuration = beatDuration / subdivision;
            int ticksPerMeasure = beatsPerMeasure * subdivision;
            int firstTickIndex = (int)Math.Floor((windowStart - timelineBeatOriginMs) / subDuration) - 1;
            int lastTickIndex = (int)Math.Ceiling((windowEnd - timelineBeatOriginMs) / subDuration) + 1;

            int markerCount = 0;
            for (int tickIndex = firstTickIndex; tickIndex <= lastTickIndex; tickIndex++)
            {
                double tickTime = timelineBeatOriginMs + tickIndex * subDuration;
                float progress = (float)((tickTime - windowStart) / timelineDurationMs);
                if (progress < -0.02f || progress > 1.02f)
                    continue;

                int measureRemainder = positiveModulo(tickIndex, ticksPerMeasure);
                bool isMeasure = measureRemainder == 0;
                bool isBeat = !isMeasure && positiveModulo(tickIndex, subdivision) == 0;
                bool isHalfBeat = !isMeasure
                                  && !isBeat
                                  && subdivision % 2 == 0
                                  && positiveModulo(tickIndex, subdivision / 2) == 0;
                bool isTripletGuide = !isMeasure
                                      && !isBeat
                                      && subdivision % 3 == 0
                                      && positiveModulo(tickIndex, subdivision / 3) == 0;
                bool isSubBeat = !isMeasure && !isBeat && (isHalfBeat || isTripletGuide);
                bool showMinorSubdivision = !isMeasure && !isBeat && !isSubBeat && subdivision >= 6;

                if (!isMeasure && !isBeat && !isSubBeat && !showMinorSubdivision)
                    continue;

                Box marker = getTimelineMarker(markerCount++);
                marker.X = Math.Clamp(progress, 0f, 1f);
                if (isMeasure)
                {
                    marker.Width = 1.8f;
                    marker.Colour = new Color4(214, 226, 248, 90);
                    marker.Alpha = 0.30f;
                }
                else if (isBeat)
                {
                    marker.Width = 1.2f;
                    marker.Colour = new Color4(184, 198, 224, 74);
                    marker.Alpha = 0.18f;
                }
                else if (isSubBeat)
                {
                    marker.Width = 0.9f;
                    marker.Colour = new Color4(164, 178, 204, 58);
                    marker.Alpha = 0.11f;
                }
                else
                {
                    marker.Width = 0.8f;
                    marker.Colour = new Color4(156, 170, 198, 46);
                    marker.Alpha = 0.07f;
                }
            }

            for (int i = markerCount; i < timelineMarkers.Count; i++)
                timelineMarkers[i].Alpha = 0f;

            updateTimelinePlayheadLabel(beatDuration, beatsPerMeasure, subdivision);
            updateTimelinePlayheadCountInGuides(beatDuration, beatsPerMeasure, subdivision);
        }

        private Box getTimelineMarker(int index)
        {
            while (timelineMarkers.Count <= index)
            {
                var marker = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Height = 1f,
                    RelativePositionAxes = Axes.X,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Alpha = 0f
                };
                timelineMarkers.Add(marker);
                timelineMarkerLayer?.Add(marker);
            }

            return timelineMarkers[index];
        }

        private void updateTimelineMeasureBands(double windowStart, double windowEnd, double beatDuration, int beatsPerMeasure)
        {
            if (timelineMeasureBandLayer == null || beatsPerMeasure <= 0 || beatDuration <= 1 || timelineDurationMs <= 1)
            {
                for (int i = 0; i < timelineMeasureBands.Count; i++)
                    timelineMeasureBands[i].Alpha = 0f;
                return;
            }

            double measureDuration = beatDuration * beatsPerMeasure;
            if (measureDuration <= 1)
            {
                for (int i = 0; i < timelineMeasureBands.Count; i++)
                    timelineMeasureBands[i].Alpha = 0f;
                return;
            }

            int firstMeasure = (int)Math.Floor((windowStart - timelineBeatOriginMs) / measureDuration) - 1;
            int lastMeasure = (int)Math.Ceiling((windowEnd - timelineBeatOriginMs) / measureDuration) + 1;

            int bandCount = 0;
            for (int measureIndex = firstMeasure; measureIndex <= lastMeasure; measureIndex++)
            {
                double startMs = timelineBeatOriginMs + measureIndex * measureDuration;
                double endMs = startMs + measureDuration;
                double clippedStart = Math.Max(startMs, windowStart);
                double clippedEnd = Math.Min(endMs, windowEnd);
                if (clippedEnd - clippedStart <= 1)
                    continue;

                float startProgress = (float)((clippedStart - windowStart) / timelineDurationMs);
                float endProgress = (float)((clippedEnd - windowStart) / timelineDurationMs);
                float width = Math.Clamp(endProgress - startProgress, 0f, 1f);
                if (width <= 0.0005f)
                    continue;

                Box band = getTimelineMeasureBand(bandCount++);
                band.X = Math.Clamp(startProgress, 0f, 1f);
                band.Width = width;
                band.Colour = new Color4(124, 144, 182, 255);
                band.Alpha = positiveModulo(measureIndex, 2) == 0 ? 0.042f : 0.020f;
            }

            for (int i = bandCount; i < timelineMeasureBands.Count; i++)
                timelineMeasureBands[i].Alpha = 0f;
        }

        private Box getTimelineMeasureBand(int index)
        {
            while (timelineMeasureBands.Count <= index)
            {
                var band = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.X,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Width = 0f,
                    Alpha = 0f
                };
                timelineMeasureBands.Add(band);
                timelineMeasureBandLayer?.Add(band);
            }

            return timelineMeasureBands[index];
        }

        private void updateTimelineMeasureLabels(double windowStart, double windowEnd, double beatDuration, int beatsPerMeasure)
        {
            if (timelineMeasureLabelLayer == null || beatsPerMeasure <= 0 || beatDuration <= 1 || timelineDurationMs <= 1)
            {
                for (int i = 0; i < timelineMeasureLabels.Count; i++)
                    timelineMeasureLabels[i].Alpha = 0f;
                return;
            }

            double measureDuration = beatDuration * beatsPerMeasure;
            if (measureDuration <= 1)
            {
                for (int i = 0; i < timelineMeasureLabels.Count; i++)
                    timelineMeasureLabels[i].Alpha = 0f;
                return;
            }

            int firstMeasure = (int)Math.Floor((windowStart - timelineBeatOriginMs) / measureDuration) - 1;
            int lastMeasure = (int)Math.Ceiling((windowEnd - timelineBeatOriginMs) / measureDuration) + 1;

            int labelCount = 0;
            float minSpacing = Math.Clamp((timelineRightX - timelineLeftX) * 0.07f, 40f, 76f);
            float lastPlacedX = float.NegativeInfinity;

            for (int measureIndex = firstMeasure; measureIndex <= lastMeasure; measureIndex++)
            {
                double startMs = timelineBeatOriginMs + measureIndex * measureDuration;
                if (startMs < windowStart || startMs > windowEnd)
                    continue;

                float progress = (float)((startMs - windowStart) / timelineDurationMs);
                float x = timelineLeftX + Math.Clamp(progress, 0f, 1f) * (timelineRightX - timelineLeftX);
                if (x - lastPlacedX < minSpacing)
                    continue;

                SpriteText label = getTimelineMeasureLabel(labelCount++);
                label.Text = $"M{measureIndex + 1}";
                label.X = x + 4f;
                label.Y = 8f;
                label.Alpha = 0.44f;
                lastPlacedX = x;
            }

            for (int i = labelCount; i < timelineMeasureLabels.Count; i++)
                timelineMeasureLabels[i].Alpha = 0f;
        }

        private SpriteText getTimelineMeasureLabel(int index)
        {
            while (timelineMeasureLabels.Count <= index)
            {
                var label = new SpriteText
                {
                    RelativePositionAxes = Axes.None,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Font = new FontUsage("Roboto", 10f),
                    Colour = new Color4(194, 208, 234, 226),
                    Alpha = 0f
                };
                timelineMeasureLabels.Add(label);
                timelineMeasureLabelLayer?.Add(label);
            }

            return timelineMeasureLabels[index];
        }

        private void updateTimelineTupletLabels(double windowStart, double windowEnd, double beatDuration, int subdivision)
        {
            if (timelineTupletLabelLayer == null
                || timelineDurationMs <= 1
                || beatDuration <= 1
                || !ShouldRenderManuscriptTupletHint(subdivision))
            {
                clearTimelineTupletLabels();
                return;
            }

            int groupingTicks = ResolveManuscriptTupletGroupingTicks(subdivision);
            if (groupingTicks <= 0)
            {
                clearTimelineTupletLabels();
                return;
            }

            double subDuration = beatDuration / Math.Max(1, subdivision);
            if (subDuration <= 0)
            {
                clearTimelineTupletLabels();
                return;
            }

            int firstTick = (int)Math.Floor((windowStart - timelineBeatOriginMs) / subDuration) - groupingTicks;
            int lastTick = (int)Math.Ceiling((windowEnd - timelineBeatOriginMs) / subDuration) + groupingTicks;
            int firstGroup = (int)Math.Floor(firstTick / (double)groupingTicks) - 1;
            int lastGroup = (int)Math.Ceiling(lastTick / (double)groupingTicks) + 1;
            float width = timelineRightX - timelineLeftX;
            float minSpacing = Math.Clamp(width * 0.085f, 58f, 108f);
            float minBracketSpan = Math.Clamp(width * 0.055f, 28f, 66f);
            float clampedPlayheadX = Math.Clamp(timelinePlayheadX, timelineLeftX, timelineRightX);
            double playheadProgress = Math.Clamp((clampedPlayheadX - timelineLeftX) / Math.Max(1f, width), 0f, 1f);
            double playheadTimeMs = timelineStartMs + timelineDurationMs * playheadProgress;
            float lastPlacedX = float.NegativeInfinity;
            int labelCount = 0;
            int bracketCount = 0;

            for (int groupIndex = firstGroup; groupIndex <= lastGroup; groupIndex++)
            {
                int groupStartTick = groupIndex * groupingTicks;
                int groupEndTick = groupStartTick + groupingTicks;
                double groupStartTime = timelineBeatOriginMs + groupStartTick * subDuration;
                double groupEndTime = timelineBeatOriginMs + groupEndTick * subDuration;
                if (groupEndTime < windowStart || groupStartTime > windowEnd)
                    continue;

                float startProgress = (float)((groupStartTime - windowStart) / timelineDurationMs);
                float endProgress = (float)((groupEndTime - windowStart) / timelineDurationMs);
                float startX = timelineLeftX + Math.Clamp(startProgress, 0f, 1f) * width;
                float endX = timelineLeftX + Math.Clamp(endProgress, 0f, 1f) * width;
                float span = endX - startX;
                if (span < minBracketSpan)
                    continue;

                double centerTime = (groupStartTime + groupEndTime) * 0.5;
                float progress = (float)((centerTime - windowStart) / timelineDurationMs);
                float x = timelineLeftX + Math.Clamp(progress, 0f, 1f) * width;
                if (x - lastPlacedX < minSpacing)
                    continue;

                float hookInset = Math.Clamp(span * 0.08f, 2f, 8f);
                float railStartX = startX + hookInset;
                float railEndX = endX - hookInset;
                float railWidth = Math.Max(8f, railEndX - railStartX);
                float railY = 25f;
                double distanceBeats = Math.Abs((centerTime - playheadTimeMs) / beatDuration);
                float emphasis = ResolveManuscriptTupletBracketEmphasis(distanceBeats);
                float hookHeight = Math.Clamp(4.4f + emphasis * 1.6f, 4.4f, 6.0f);
                float bracketAlpha = Math.Clamp(0.24f + emphasis * 0.34f, 0.24f, 0.58f);
                byte bracketBlue = (byte)Math.Clamp(226 + (int)Math.Round(emphasis * 20f), 0, 255);
                Color4 bracketColor = new Color4(196, 212, bracketBlue, 228);

                Box rail = getTimelineTupletBracketRail(bracketCount);
                rail.X = railStartX;
                rail.Y = railY;
                rail.Width = railWidth;
                rail.Height = Math.Clamp(1.15f + emphasis * 0.35f, 1.15f, 1.5f);
                rail.Colour = bracketColor;
                rail.Alpha = bracketAlpha;

                Box leftHook = getTimelineTupletBracketLeftHook(bracketCount);
                leftHook.X = railStartX;
                leftHook.Y = railY;
                leftHook.Width = 1.3f;
                leftHook.Height = hookHeight;
                leftHook.Colour = bracketColor;
                leftHook.Alpha = bracketAlpha;

                Box rightHook = getTimelineTupletBracketRightHook(bracketCount);
                rightHook.X = railStartX + railWidth;
                rightHook.Y = railY;
                rightHook.Width = 1.3f;
                rightHook.Height = hookHeight;
                rightHook.Colour = bracketColor;
                rightHook.Alpha = bracketAlpha;

                SpriteText label = getTimelineTupletLabel(labelCount++);
                label.Text = FormatManuscriptTupletHintLabel(subdivision);
                label.X = Math.Clamp(x, timelineLeftX + 8f, timelineRightX - 16f);
                label.Y = railY + 6.2f;
                label.Alpha = Math.Clamp(0.34f + emphasis * 0.28f, 0.34f, 0.62f);
                lastPlacedX = x;
                bracketCount++;
            }

            for (int i = labelCount; i < timelineTupletLabels.Count; i++)
                timelineTupletLabels[i].Alpha = 0f;
            for (int i = bracketCount; i < timelineTupletBracketRails.Count; i++)
                timelineTupletBracketRails[i].Alpha = 0f;
            for (int i = bracketCount; i < timelineTupletBracketLeftHooks.Count; i++)
                timelineTupletBracketLeftHooks[i].Alpha = 0f;
            for (int i = bracketCount; i < timelineTupletBracketRightHooks.Count; i++)
                timelineTupletBracketRightHooks[i].Alpha = 0f;
        }

        private SpriteText getTimelineTupletLabel(int index)
        {
            while (timelineTupletLabels.Count <= index)
            {
                var label = new SpriteText
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Font = new FontUsage("Roboto", 11.4f, weight: "Bold"),
                    Colour = new Color4(206, 220, 242, 234),
                    Alpha = 0f
                };
                timelineTupletLabels.Add(label);
                timelineTupletLabelLayer?.Add(label);
            }

            return timelineTupletLabels[index];
        }

        private Box getTimelineTupletBracketRail(int index)
        {
            while (timelineTupletBracketRails.Count <= index)
            {
                var rail = new Box
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Alpha = 0f
                };
                timelineTupletBracketRails.Add(rail);
                timelineTupletLabelLayer?.Add(rail);
            }

            return timelineTupletBracketRails[index];
        }

        private Box getTimelineTupletBracketLeftHook(int index)
        {
            while (timelineTupletBracketLeftHooks.Count <= index)
            {
                var hook = new Box
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Alpha = 0f
                };
                timelineTupletBracketLeftHooks.Add(hook);
                timelineTupletLabelLayer?.Add(hook);
            }

            return timelineTupletBracketLeftHooks[index];
        }

        private Box getTimelineTupletBracketRightHook(int index)
        {
            while (timelineTupletBracketRightHooks.Count <= index)
            {
                var hook = new Box
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Alpha = 0f
                };
                timelineTupletBracketRightHooks.Add(hook);
                timelineTupletLabelLayer?.Add(hook);
            }

            return timelineTupletBracketRightHooks[index];
        }

        private void clearTimelineTupletLabels()
        {
            for (int i = 0; i < timelineTupletLabels.Count; i++)
                timelineTupletLabels[i].Alpha = 0f;
            for (int i = 0; i < timelineTupletBracketRails.Count; i++)
                timelineTupletBracketRails[i].Alpha = 0f;
            for (int i = 0; i < timelineTupletBracketLeftHooks.Count; i++)
                timelineTupletBracketLeftHooks[i].Alpha = 0f;
            for (int i = 0; i < timelineTupletBracketRightHooks.Count; i++)
                timelineTupletBracketRightHooks[i].Alpha = 0f;
        }

        private void updateTimelinePlayheadLabel(double beatDuration, int beatsPerMeasure, int subdivision)
        {
            if (timelinePlayheadLabel == null
                || !hasTimelineWindow
                || timelineDurationMs <= 1
                || beatDuration <= 1
                || beatsPerMeasure <= 0)
            {
                if (timelinePlayheadLabel != null)
                    timelinePlayheadLabel.Alpha = 0f;
                return;
            }

            float width = timelineRightX - timelineLeftX;
            if (width <= 1f)
            {
                timelinePlayheadLabel.Alpha = 0f;
                return;
            }

            float clampedPlayheadX = Math.Clamp(timelinePlayheadX, timelineLeftX, timelineRightX);
            double progress = Math.Clamp((clampedPlayheadX - timelineLeftX) / width, 0f, 1f);
            double playheadTimeMs = timelineStartMs + timelineDurationMs * progress;
            double beatPosition = (playheadTimeMs - timelineBeatOriginMs) / beatDuration;
            int beatIndex = (int)Math.Floor(beatPosition + 0.000001);
            int measureIndex = (int)Math.Floor(beatIndex / (double)beatsPerMeasure);
            int measureNumber = Math.Max(1, measureIndex + 1);
            int beatInMeasure = positiveModulo(beatIndex, beatsPerMeasure) + 1;

            double beatPhase = beatPosition - Math.Floor(beatPosition);
            if (beatPhase < 0)
                beatPhase += 1.0;
            int subdivisionIndex = Math.Clamp((int)Math.Floor(beatPhase * subdivision + 0.0001), 0, Math.Max(0, subdivision - 1));

            timelinePlayheadLabel.Text = subdivision > 1
                ? $"Now M{measureNumber} B{beatInMeasure}.{subdivisionIndex + 1}/{subdivision}"
                : $"Now M{measureNumber} B{beatInMeasure}";
            timelinePlayheadLabel.X = Math.Clamp(clampedPlayheadX + 10f, timelineLeftX + 6f, Math.Max(timelineLeftX + 90f, timelineRightX - 186f));
            timelinePlayheadLabel.Y = 8f;
            timelinePlayheadLabel.Alpha = 0.66f;
        }

        private void updateTimelinePlayheadCountInGuides(double beatDuration, int beatsPerMeasure, int subdivision)
        {
            if (timelinePlayheadCountInLayer == null
                || !hasTimelineWindow
                || timelineDurationMs <= 1
                || beatDuration <= 1
                || beatsPerMeasure <= 0
                || subdivision <= 0
                || countInGuideMode == ManuscriptCountInGuideMode.Off)
            {
                clearTimelinePlayheadCountInGuides();
                return;
            }

            float width = timelineRightX - timelineLeftX;
            if (width <= 1f)
            {
                clearTimelinePlayheadCountInGuides();
                return;
            }

            float clampedPlayheadX = Math.Clamp(timelinePlayheadX, timelineLeftX, timelineRightX);
            double playheadProgress = Math.Clamp((clampedPlayheadX - timelineLeftX) / width, 0f, 1f);
            double playheadTimeMs = timelineStartMs + timelineDurationMs * playheadProgress;
            double subDuration = beatDuration / subdivision;
            if (subDuration <= 0)
            {
                clearTimelinePlayheadCountInGuides();
                return;
            }

            int playheadTick = (int)Math.Round((playheadTimeMs - timelineBeatOriginMs) / subDuration, MidpointRounding.AwayFromZero);
            int lookAroundTicks = ResolveManuscriptCountInLookAroundTicks(subdivision, countInGuideMode);
            if (lookAroundTicks <= 0)
            {
                clearTimelinePlayheadCountInGuides();
                return;
            }

            float minLabelSpacing = countInGuideMode == ManuscriptCountInGuideMode.Compact
                ? Math.Clamp(width * 0.052f, 34f, 62f)
                : Math.Clamp(width * 0.032f, 24f, 46f);
            float lastLabelX = float.NegativeInfinity;
            int tickCount = 0;
            int labelCount = 0;

            for (int relativeTick = -lookAroundTicks; relativeTick <= lookAroundTicks; relativeTick++)
            {
                int tickIndex = playheadTick + relativeTick;
                double tickTime = timelineBeatOriginMs + tickIndex * subDuration;
                float progress = (float)((tickTime - timelineStartMs) / timelineDurationMs);
                if (progress < -0.04f || progress > 1.04f)
                    continue;

                float x = timelineLeftX + Math.Clamp(progress, 0f, 1f) * width;
                bool isNow = relativeTick == 0;
                bool isBeat = positiveModulo(tickIndex, subdivision) == 0;
                bool isHalfBeat = !isBeat
                                  && subdivision % 2 == 0
                                  && positiveModulo(tickIndex, subdivision / 2) == 0;
                bool isSubBeat = !isNow && !isBeat && !isHalfBeat;

                if (!ShouldRenderManuscriptCountInTick(countInGuideMode, isNow, isBeat, isHalfBeat, isSubBeat))
                    continue;

                Box tick = getTimelinePlayheadCountInTick(tickCount++);
                tick.X = x;
                tick.Colour = isNow
                    ? new Color4(192, 228, 255, 210)
                    : isBeat
                        ? new Color4(176, 204, 236, 164)
                        : isHalfBeat
                            ? new Color4(162, 186, 220, 136)
                            : new Color4(148, 170, 204, 106);
                tick.Width = isNow ? 2.0f : isBeat ? 1.4f : 1.0f;
                tick.Height = isNow ? 18f : isBeat ? 14f : isHalfBeat ? 10f : 7f;
                tick.Alpha = isNow ? 0.78f : isBeat ? 0.52f : isHalfBeat ? 0.40f : 0.30f;

                bool showLabel = ShouldRenderManuscriptCountInLabel(countInGuideMode, isNow, isBeat, relativeTick, subdivision);
                if (!showLabel)
                    continue;

                if (!isNow && x - lastLabelX < minLabelSpacing)
                    continue;

                SpriteText label = getTimelinePlayheadCountInLabel(labelCount++);
                label.Text = FormatManuscriptCountInLabel(relativeTick, subdivision);
                label.X = Math.Clamp(x + 2f, timelineLeftX + 4f, timelineRightX - 80f);
                label.Y = 22f;
                label.Alpha = isNow ? 0.72f : 0.54f;
                lastLabelX = x;
            }

            for (int i = tickCount; i < timelinePlayheadCountInTicks.Count; i++)
                timelinePlayheadCountInTicks[i].Alpha = 0f;
            for (int i = labelCount; i < timelinePlayheadCountInLabels.Count; i++)
                timelinePlayheadCountInLabels[i].Alpha = 0f;
        }

        private Box getTimelinePlayheadCountInTick(int index)
        {
            while (timelinePlayheadCountInTicks.Count <= index)
            {
                var tick = new Box
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Y = 4f,
                    Width = 1f,
                    Height = 0f,
                    Alpha = 0f
                };
                timelinePlayheadCountInTicks.Add(tick);
                timelinePlayheadCountInLayer?.Add(tick);
            }

            return timelinePlayheadCountInTicks[index];
        }

        private SpriteText getTimelinePlayheadCountInLabel(int index)
        {
            while (timelinePlayheadCountInLabels.Count <= index)
            {
                var label = new SpriteText
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Font = new FontUsage("Roboto", 9.2f),
                    Colour = new Color4(192, 210, 236, 224),
                    Alpha = 0f
                };
                timelinePlayheadCountInLabels.Add(label);
                timelinePlayheadCountInLayer?.Add(label);
            }

            return timelinePlayheadCountInLabels[index];
        }

        private void clearTimelinePlayheadCountInGuides()
        {
            for (int i = 0; i < timelinePlayheadCountInTicks.Count; i++)
                timelinePlayheadCountInTicks[i].Alpha = 0f;
            for (int i = 0; i < timelinePlayheadCountInLabels.Count; i++)
                timelinePlayheadCountInLabels[i].Alpha = 0f;
        }

        internal static int ResolveManuscriptCountInLookAroundTicks(int subdivision, ManuscriptCountInGuideMode mode)
        {
            if (mode == ManuscriptCountInGuideMode.Off)
                return 0;

            int safeSubdivision = Math.Max(1, subdivision);
            return mode == ManuscriptCountInGuideMode.Compact
                ? Math.Clamp(safeSubdivision + 1, 3, 8)
                : Math.Clamp(safeSubdivision * 2, 4, 12);
        }

        internal static bool ShouldRenderManuscriptCountInTick(ManuscriptCountInGuideMode mode, bool isNow, bool isBeat, bool isHalfBeat, bool isSubBeat)
        {
            if (mode == ManuscriptCountInGuideMode.Off)
                return false;

            if (isNow || isBeat)
                return true;

            return mode == ManuscriptCountInGuideMode.Compact
                ? isHalfBeat
                : isHalfBeat || isSubBeat;
        }

        internal static bool ShouldRenderManuscriptCountInLabel(ManuscriptCountInGuideMode mode, bool isNow, bool isBeat, int relativeTick, int subdivision)
        {
            if (mode == ManuscriptCountInGuideMode.Off)
                return false;

            if (isNow)
                return true;

            if (mode == ManuscriptCountInGuideMode.Compact)
                return isBeat && Math.Abs(relativeTick) <= Math.Max(2, subdivision);

            return isBeat || (Math.Abs(relativeTick) <= 2 && subdivision >= 3);
        }

        internal static string FormatManuscriptCountInLabel(int relativeTick, int subdivision)
        {
            int safeSubdivision = Math.Max(1, subdivision);
            if (relativeTick == 0)
                return "Now";

            int absoluteTick = Math.Abs(relativeTick);
            char sign = relativeTick > 0 ? '+' : '-';
            int beatPart = absoluteTick / safeSubdivision;
            int subPart = absoluteTick % safeSubdivision;

            if (subPart == 0)
                return $"{sign}{Math.Max(1, beatPart)}b";

            if (beatPart == 0)
                return $"{sign}{subPart}/{safeSubdivision}";

            return $"{sign}{beatPart}b {subPart}/{safeSubdivision}";
        }

        internal static bool ShouldRenderManuscriptTupletHint(int subdivision)
            => subdivision is 3 or 6;

        internal static int ResolveManuscriptTupletGroupingTicks(int subdivision)
        {
            if (subdivision == 3)
                return 3;
            if (subdivision == 6)
                return 3;

            return 0;
        }

        internal static string FormatManuscriptTupletHintLabel(int subdivision)
            => ShouldRenderManuscriptTupletHint(subdivision) ? "3" : string.Empty;

        internal static float ResolveManuscriptTupletBracketEmphasis(double distanceBeats)
        {
            if (double.IsNaN(distanceBeats) || double.IsInfinity(distanceBeats))
                return 0.32f;

            double normalized = Math.Clamp(Math.Abs(distanceBeats) / 2.5, 0.0, 1.0);
            return (float)(1.0 - 0.68 * normalized);
        }

        private static int positiveModulo(int value, int divisor)
        {
            if (divisor <= 0)
                return 0;

            int remainder = value % divisor;
            return remainder < 0 ? remainder + divisor : remainder;
        }

        private Drawable CreateComponentLegend()
        {
            // Compact notation hint panel.
            var legend = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 1),
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Margin = new MarginPadding { Top = 12, Right = 12 },
                Alpha = 0.62f
            };

            legend.Add(new SpriteText
            {
                Text = "Percussion notation map",
                Font = new FontUsage("Roboto", 10.5f),
                Colour = new Color4(206, 220, 242, 230)
            });

            foreach (ComponentGuide guide in componentGuides)
            {
                legend.Add(new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(4, 0),
                    Children = new Drawable[]
                    {
                        new Circle
                        {
                            Size = new Vector2(6, 6),
                            Colour = DesignSystem.WithOpacity(guide.Color, 0.72f)
                        },
                        new SpriteText
                        {
                            Text = $"{guide.Label} {getGuideDisplayName(guide.Key)}",
                            Font = new FontUsage("Roboto", 9.6f),
                            Colour = new Color4(182, 196, 222, 238)
                        }
                    }
                });
            }

            return legend;
        }

        private static string getGuideDisplayName(string key)
        {
            return key switch
            {
                "kick" => "Kick",
                "hihat" => "Hi-Hat",
                "snare" => "Snare",
                "tom_high" => "Tom High",
                "tom_mid" => "Tom Mid",
                "tom_low" => "Tom Low",
                "ride" => "Ride",
                "crash" => "Crash/China",
                _ => "Perc"
            };
        }

        /// <summary>
        /// Get the X offset for a component on the staff.
        /// Static utility method for use by other classes.
        /// </summary>
        public static float GetStaffPositionForComponent(string component)
            => GetStaffPositionForComponent(component, 1920f);

        public static float GetStaffPositionForComponent(string component, float drawWidth)
            => GetStaffUnitForComponent(component) * GetStaffSpacingForDrawWidth(drawWidth);

        public static IReadOnlyList<string> GetNotationCycleComponents()
            => notationCycleComponents;

        public static int GetNotationIndexForComponent(string? component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return 2; // snare center lane

            string mapped = mapGuideKey(normalizeComponentKey(component));
            for (int i = 0; i < notationCycleComponents.Length; i++)
            {
                if (string.Equals(notationCycleComponents[i], mapped, StringComparison.Ordinal))
                    return i;
            }

            return 2;
        }

        public static string GetAdjacentNotationComponent(string? component, int direction)
        {
            int step = Math.Sign(direction);
            if (step == 0)
                return notationCycleComponents[GetNotationIndexForComponent(component)];

            int current = GetNotationIndexForComponent(component);
            int next = Math.Clamp(current + step, 0, notationCycleComponents.Length - 1);
            return notationCycleComponents[next];
        }

        public static float GetStaffUnitForComponent(string component)
        {
            if (string.IsNullOrEmpty(component))
                return 0f;

            string key = normalizeComponentKey(component);
            key = mapGuideKey(key);

            return key switch
            {
                "kick" => -3.5f,
                "hihat" => -2.5f,
                "snare" => -1.5f,
                "tom_high" => -0.5f,
                "tom_mid" => 0.5f,
                "tom_low" => 1.5f,
                "ride" => 2.5f,
                "crash" => 3.5f,
                _ => -1.5f
            };
        }

        public static ManuscriptNotationVoice GetNotationVoiceForComponent(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return ManuscriptNotationVoice.Lower;

            string key = mapGuideKey(normalizeComponentKey(component));
            return key switch
            {
                "kick" => ManuscriptNotationVoice.Lower,
                "snare" => ManuscriptNotationVoice.Lower,
                _ => ManuscriptNotationVoice.Upper
            };
        }

        public static bool ShouldUseDownStemForComponent(string component)
            => GetNotationVoiceForComponent(component) == ManuscriptNotationVoice.Lower;

        public static bool UsesCrossNoteheadForComponent(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return false;

            string normalized = normalizeComponentKey(component);
            if (normalized is "ride_bell" or "cowbell")
                return false;

            string key = mapGuideKey(normalized);
            return key is "hihat" or "ride" or "crash";
        }

        public static bool UsesDiamondNoteheadForComponent(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return false;

            string key = normalizeComponentKey(component);
            return key is "ride_bell" or "cowbell";
        }

        public static bool IsHiHatFamilyComponent(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return false;

            string key = normalizeComponentKey(component);
            return key is "hihat" or "hihat_closed" or "hihat_open" or "hihat_half_open" or "hihat_pedal";
        }

        public static bool IsOpenHiHatComponent(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return false;

            string key = normalizeComponentKey(component);
            return key is "hihat_open" or "hihat_half_open";
        }

        public static bool IsHalfOpenHiHatComponent(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return false;

            string key = normalizeComponentKey(component);
            return key is "hihat_half_open";
        }

        public static bool IsClosedHiHatComponent(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return false;

            string key = normalizeComponentKey(component);
            return key is "hihat" or "hihat_closed" or "hihat_pedal";
        }

        public static float GetStaffSpacingForDrawWidth(float drawWidth)
        {
            float staffWidth = Math.Max(320f, drawWidth * ManuscriptStaffWidthRatio);
            float usableWidth = staffWidth * 0.92f;
            return Math.Clamp(usableWidth / (StaffUnitRange + 1f), 42f, 140f);
        }

        public static float GetTimelineWidthForDrawWidth(float drawWidth)
            => Math.Max(320f, drawWidth * ManuscriptStaffWidthRatio);

        public static float GetStaffCenterYForDrawHeight(float drawHeight)
            => drawHeight * ManuscriptStaffCenterYRatio;

        public static float GetStaffSpacingForDrawArea(float drawWidth, float drawHeight)
        {
            float spacingByWidth = GetTimelineWidthForDrawWidth(drawWidth) / (StaffUnitRange + 2.4f);
            float staffHeight = Math.Max(180f, drawHeight * ManuscriptStaffHeightRatio);
            float spacingByHeight = staffHeight / (StaffUnitRange + 6f);
            return Math.Clamp(Math.Min(spacingByWidth, spacingByHeight), 18f, 88f);
        }

        public static float GetStaffYForComponent(string component, float drawWidth, float drawHeight)
        {
            float centerY = GetStaffCenterYForDrawHeight(drawHeight);
            float spacing = GetStaffSpacingForDrawArea(drawWidth, drawHeight);
            return centerY - GetStaffUnitForComponent(component) * spacing;
        }

        private static string mapGuideKey(string key)
        {
            return key switch
            {
                "hihat_closed" => "hihat",
                "hihat_open" => "hihat",
                "hihat_half_open" => "hihat",
                "hihat_pedal" => "hihat",
                "ride_bell" => "ride",
                "china" => "crash",
                "splash" => "crash",
                "cowbell" => "tom_mid",
                _ => key
            };
        }

        private static string normalizeComponentKey(string component)
        {
            string key = component.ToLowerInvariant();

            // Strip ranked suffix: crash_1 -> crash, ride_bell_2 -> ride_bell
            int underscore = key.LastIndexOf('_');
            if (underscore > 0 && underscore < key.Length - 1)
            {
                bool numericSuffix = true;
                for (int i = underscore + 1; i < key.Length; i++)
                {
                    if (!char.IsDigit(key[i]))
                    {
                        numericSuffix = false;
                        break;
                    }
                }

                if (numericSuffix)
                    key = key[..underscore];
            }

            if (key.Contains("kick") || key.Contains("bass")) return "kick";
            if (key.Contains("snare") || key.Contains("rim") || key.Contains("cross") || key.Contains("side"))
                return "snare";
            if (key.Contains("hat") || key.Contains("hh"))
            {
                if (key.Contains("pedal") || key.Contains("foot"))
                    return "hihat_pedal";
                if (key.Contains("half") || key.Contains("semi"))
                    return "hihat_half_open";
                if (key.Contains("open"))
                    return "hihat_open";
                if (key.Contains("closed") || key.Contains("tight"))
                    return "hihat_closed";

                return "hihat_closed";
            }
            if (key.Contains("tom_high")) return "tom_high";
            if (key.Contains("tom_low") || key.Contains("floor")) return "tom_low";
            if (key.Contains("tom")) return "tom_mid";
            if (key.Contains("crash")) return "crash";
            if (key.Contains("china")) return "china";
            if (key.Contains("splash")) return "splash";
            if (key.Contains("cowbell")) return "cowbell";
            if (key.Contains("ride_bell") || key.Contains("bell")) return "ride_bell";
            if (key.Contains("ride")) return "ride";

            return key;
        }
    }

    /// <summary>
    /// Enhanced percussion clef indicator.
    /// The percussion clef consists of two vertical bars.
    /// </summary>
    internal partial class ClefIndicatorEnhanced : CompositeDrawable
    {
        private const float BarWidth = 4f;
        private const float BarHeight = 32f;
        private const float BarSpacing = 10f;

        public ClefIndicatorEnhanced()
        {
            Size = new Vector2(BarSpacing + BarWidth * 2, BarHeight);

            InternalChildren = new Drawable[]
            {
                // Left bar
                new Box
                {
                    Width = BarWidth,
                    Height = BarHeight,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = -BarSpacing / 2,
                    Colour = new Color4(35, 38, 45, 255)
                },
                // Right bar
                new Box
                {
                    Width = BarWidth,
                    Height = BarHeight,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = BarSpacing / 2,
                    Colour = new Color4(35, 38, 45, 255)
                }
            };
        }
    }

    /// <summary>
    /// Enhanced strike zone for manuscript view.
    /// A subtle horizontal playhead line.
    /// </summary>
    internal partial class ManuscriptStrikeZoneEnhanced : CompositeDrawable
    {
        private readonly Box mainLine;
        private readonly Box glowLine;

        public ManuscriptStrikeZoneEnhanced()
        {
            RelativeSizeAxes = Axes.X;
            Height = DesignSystem.StrikeZoneHeightManuscript;
            Width = DesignSystem.StaffWidthRatio + 0.1f;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;

            // Subtle glow behind the line
            glowLine = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 6,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = DesignSystem.WithOpacity(DesignSystem.ColorPlayhead, 0.3f),
                Blending = BlendingParameters.Additive
            };

            // Main playhead line
            mainLine = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 2,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = DesignSystem.ColorPlayhead
            };

            // End markers (vertical ticks at the edges)
            var leftMarker = new Box
            {
                Width = 2,
                Height = 10,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.Centre,
                Colour = DesignSystem.ColorPlayhead,
                Alpha = 0.6f
            };

            var rightMarker = new Box
            {
                Width = 2,
                Height = 10,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.Centre,
                Colour = DesignSystem.ColorPlayhead,
                Alpha = 0.6f
            };

            InternalChildren = new Drawable[]
            {
                glowLine,
                mainLine,
                leftMarker,
                rightMarker
            };
        }

        public void UpdateGeometry(float drawHeight, float hitLineY)
        {
            float offset = Math.Max(0, drawHeight - hitLineY - Height / 2f);
            Y = -offset;
        }

        public void PulseHit(Color4 color)
        {
            mainLine.Colour = color;
            mainLine.FadeColour(DesignSystem.ColorPlayhead, DesignSystem.AnimationFast);

            glowLine.FadeTo(0.5f, DesignSystem.AnimationQuick)
                   .Then()
                   .FadeTo(0.3f, DesignSystem.AnimationFast);
        }
    }

    /// <summary>
    /// Specialized note renderer for manuscript view.
    /// Creates notation-style note heads with stems.
    /// </summary>
    public partial class ManuscriptNoteDrawable : CompositeDrawable
    {
        private readonly Circle notehead;
        private readonly Box stem;
        private Box? accentMark;

        public ManuscriptNoteDrawable(Color4 color, double velocity)
        {
            Size = new Vector2(16, 16);
            Origin = Anchor.Centre;

            bool isGhost = velocity < DesignSystem.GhostNoteThreshold;
            bool isAccent = velocity > DesignSystem.AccentNoteThreshold;
            float alpha = DesignSystem.GetVelocityAlpha(velocity);

            // Notehead (filled circle for regular notes, open for ghost notes)
            notehead = new Circle
            {
                Size = new Vector2(14, 12),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = color,
                Alpha = alpha
            };

            // Stem (goes up for notes above middle line, down for below)
            stem = new Box
            {
                Width = 1.5f,
                Height = 35,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.BottomCentre,
                X = -2,
                Y = -6,
                Colour = color,
                Alpha = alpha
            };

            InternalChildren = new Drawable[] { notehead, stem };

            // Accent mark (horizontal line above note)
            if (isAccent)
            {
                accentMark = new Box
                {
                    Width = 12,
                    Height = 2,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.BottomCentre,
                    Y = -stem.Height - 8,
                    Colour = color,
                    Alpha = alpha * 0.8f
                };
                AddInternal(accentMark);
            }

            // Ghost note styling (parentheses or X notehead)
            if (isGhost)
            {
                notehead.BorderThickness = 1.5f;
                notehead.BorderColour = color;
                notehead.Colour = Color4.Transparent;
            }
        }

        /// <summary>
        /// Set stem direction (true = up, false = down).
        /// </summary>
        public void SetStemDirection(bool up)
        {
            if (up)
            {
                stem.Anchor = Anchor.CentreRight;
                stem.Origin = Anchor.BottomCentre;
                stem.X = -2;
                stem.Y = -6;
            }
            else
            {
                stem.Anchor = Anchor.CentreLeft;
                stem.Origin = Anchor.TopCentre;
                stem.X = 2;
                stem.Y = 6;
            }
        }
    }
}
