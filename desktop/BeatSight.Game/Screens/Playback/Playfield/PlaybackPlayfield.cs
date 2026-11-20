using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Playback.Playfield.Notation;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Logging;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// Primary playfield for rendering notes in lane-based views (2D, 3D highway, manuscript).
    /// Manages note spawning, hit judgment, and visual feedback during playback sessions.
    /// </summary>
    public partial class PlaybackPlayfield : CompositeDrawable
    {
        private LaneLayout laneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
        private int laneCount => Math.Max(1, laneLayout.LaneCount);
        private bool layoutDirty = true;

        /// <summary>
        /// Cached active lane count from the last successful <see cref="updateLayout"/> call.
        /// Used for note positioning to guarantee consistency with drawn backgrounds.
        /// </summary>
        private int cachedActiveLaneCount = 7;

        /// <summary>
        /// Time in milliseconds that notes are visible before reaching the hit zone.
        /// Higher values give more reaction time but reduce note density perception.
        /// Default: 5000ms (5 seconds). Dynamically adjusted based on speed multiplier.
        /// </summary>
        public double ApproachDuration { get; private set; } = 5000;

        #region Timing Windows (from DesignSystem)
        // Use centralized timing windows from DesignSystem for consistency across the application.
        // These are exposed here for local readability while referencing the single source of truth.

        /// <summary>Timing window for "Perfect" judgment (±35ms).</summary>
        private static double perfectWindow => DesignSystem.HitWindowPerfect;

        /// <summary>Timing window for "Great" judgment (±80ms).</summary>
        private static double greatWindow => DesignSystem.HitWindowGreat;

        /// <summary>Timing window for "Good" judgment (±130ms).</summary>
        private static double goodWindow => DesignSystem.HitWindowGood;

        /// <summary>Timing window for "Meh" judgment (±180ms).</summary>
        private static double mehWindow => DesignSystem.HitWindowMeh;

        /// <summary>Timing window beyond which a note is considered missed (±220ms).</summary>
        private static double missWindow => DesignSystem.HitWindowMiss;

        #endregion

        /// <summary>Depth tolerance constants for note layer management.</summary>
        private static class DepthTolerance
        {
            /// <summary>Tolerance for depth updates in 3D view (allows larger changes).</summary>
            public const float ThreeDimensional = 12f;

            /// <summary>Tolerance for depth updates in 2D view (more precise).</summary>
            public const float TwoDimensional = 5f;
        }

        private readonly struct ThreeDProfileTuning
        {
            public ThreeDProfileTuning(
                float vanishingPointYRatio,
                float highwayBottomWidthRatio,
                float highwayTopWidthRatio,
                float progressMax,
                float laneNoteWidthAtTop,
                float laneNoteWidthAtBottom,
                float minNoteWidth,
                float maxNoteWidth,
                float minNoteHeight,
                float maxNoteHeight,
                float kickWidthAtTop,
                float kickWidthAtBottom,
                float perspectiveExponent,
                float widthExponent,
                float yExponent,
                float noteHeightRatioAtTop,
                float noteHeightRatioAtBottom,
                float rotationStrength)
            {
                VanishingPointYRatio = vanishingPointYRatio;
                HighwayBottomWidthRatio = highwayBottomWidthRatio;
                HighwayTopWidthRatio = highwayTopWidthRatio;
                ProgressMax = progressMax;
                LaneNoteWidthAtTop = laneNoteWidthAtTop;
                LaneNoteWidthAtBottom = laneNoteWidthAtBottom;
                MinNoteWidth = minNoteWidth;
                MaxNoteWidth = maxNoteWidth;
                MinNoteHeight = minNoteHeight;
                MaxNoteHeight = maxNoteHeight;
                KickWidthAtTop = kickWidthAtTop;
                KickWidthAtBottom = kickWidthAtBottom;
                PerspectiveExponent = perspectiveExponent;
                WidthExponent = widthExponent;
                YExponent = yExponent;
                NoteHeightRatioAtTop = noteHeightRatioAtTop;
                NoteHeightRatioAtBottom = noteHeightRatioAtBottom;
                RotationStrength = rotationStrength;
            }

            public float VanishingPointYRatio { get; }
            public float HighwayBottomWidthRatio { get; }
            public float HighwayTopWidthRatio { get; }
            public float ProgressMax { get; }
            public float LaneNoteWidthAtTop { get; }
            public float LaneNoteWidthAtBottom { get; }
            public float MinNoteWidth { get; }
            public float MaxNoteWidth { get; }
            public float MinNoteHeight { get; }
            public float MaxNoteHeight { get; }
            public float KickWidthAtTop { get; }
            public float KickWidthAtBottom { get; }
            public float PerspectiveExponent { get; }
            public float WidthExponent { get; }
            public float YExponent { get; }
            public float NoteHeightRatioAtTop { get; }
            public float NoteHeightRatioAtBottom { get; }
            public float RotationStrength { get; }
        }

        private static ThreeDProfileTuning resolveThreeDProfileTuning(ThreeDStageProfile profile)
        {
            return profile switch
            {
                ThreeDStageProfile.Arcade => new ThreeDProfileTuning(
                    vanishingPointYRatio: 0.112f,
                    highwayBottomWidthRatio: 0.80f,
                    highwayTopWidthRatio: 0.12f,
                    progressMax: 1.12f,
                    laneNoteWidthAtTop: 0.25f,
                    laneNoteWidthAtBottom: 0.70f,
                    minNoteWidth: 15f,
                    maxNoteWidth: 122f,
                    minNoteHeight: 8f,
                    maxNoteHeight: 30f,
                    kickWidthAtTop: 0.094f,
                    kickWidthAtBottom: 0.33f,
                    perspectiveExponent: 2.00f,
                    widthExponent: 1.32f,
                    yExponent: 1.22f,
                    noteHeightRatioAtTop: 0.34f,
                    noteHeightRatioAtBottom: 0.23f,
                    rotationStrength: 11.5f),
                ThreeDStageProfile.Tight => new ThreeDProfileTuning(
                    vanishingPointYRatio: 0.070f,
                    highwayBottomWidthRatio: 0.92f,
                    highwayTopWidthRatio: 0.055f,
                    progressMax: 1.36f,
                    laneNoteWidthAtTop: 0.31f,
                    laneNoteWidthAtBottom: 0.86f,
                    minNoteWidth: 17f,
                    maxNoteWidth: 142f,
                    minNoteHeight: 9f,
                    maxNoteHeight: 34f,
                    kickWidthAtTop: 0.106f,
                    kickWidthAtBottom: 0.39f,
                    perspectiveExponent: 2.44f,
                    widthExponent: 1.60f,
                    yExponent: 1.38f,
                    noteHeightRatioAtTop: 0.37f,
                    noteHeightRatioAtBottom: 0.26f,
                    rotationStrength: 16f),
                _ => new ThreeDProfileTuning(
                    vanishingPointYRatio: 0.082f,
                    highwayBottomWidthRatio: 0.88f,
                    highwayTopWidthRatio: 0.064f,
                    progressMax: 1.30f,
                    laneNoteWidthAtTop: 0.30f,
                    laneNoteWidthAtBottom: 0.82f,
                    minNoteWidth: 16f,
                    maxNoteWidth: 142f,
                    minNoteHeight: 9f,
                    maxNoteHeight: 32f,
                    kickWidthAtTop: 0.104f,
                    kickWidthAtBottom: 0.38f,
                    perspectiveExponent: 2.36f,
                    widthExponent: 1.54f,
                    yExponent: 1.36f,
                    noteHeightRatioAtTop: 0.37f,
                    noteHeightRatioAtBottom: 0.26f,
                    rotationStrength: 15.0f)
            };
        }

        internal static (float VanishingPointYRatio, float HighwayBottomWidthRatio, float HighwayTopWidthRatio, float PerspectiveExponent) GetThreeDProfileTuningSnapshot(ThreeDStageProfile profile)
        {
            ThreeDProfileTuning tuning = resolveThreeDProfileTuning(profile);
            return (tuning.VanishingPointYRatio, tuning.HighwayBottomWidthRatio, tuning.HighwayTopWidthRatio, tuning.PerspectiveExponent);
        }

        internal static string FormatThreeDProfileHintLabel(ThreeDStageProfile profile)
        {
            return profile switch
            {
                ThreeDStageProfile.Arcade => "Arcade",
                ThreeDStageProfile.GhClassic => "GH Classic",
                ThreeDStageProfile.Tight => "Tight",
                _ => "GH Classic"
            };
        }

        /// <summary>Width ratio of the playfield relative to container. 1.0 = full width.</summary>
        private const float PlayfieldWidthRatio = 1f;
        private const float PreviewTwoDimensionalHitLineLift = 0.015f;

        /// <summary>Additional visibility buffer after miss window (ms).</summary>
        private const double PastVisibilityBuffer = 600;
        private const double BaseVisibleMeasures = 1.40;
        private const double FutureVisibilityLeadInRatio = 0.24;
        private const double FutureVisibilityLeadInMinMs = 120;
        private const double FutureVisibilityLeadInMaxMs = 360;
        private const double ManualZoomMin = 0.2;
        private const double ManualZoomMax = 5.0;
        private const double PreviewZoomLowEndBoost = 0.22;
        private const double PreviewZoomHighEndBoost = 0.95;
        private const double PreviewZoomLowEndExponent = 1.4;
        private const double PreviewZoomHighEndExponent = 1.8;
        private const double AutoZoomBaseMultiplier = 1.18;
        private const double AutoZoomMaxMultiplier = 1.95;

        private readonly Func<double> currentTimeProvider;
        private readonly Func<bool>? snapEnabledProvider;
        private readonly Func<double, double>? snapIntervalAtTimeProvider;
        private readonly List<DrawableNote> notes = new();
        private readonly List<DrawableNote> kickNoteBuffer = new();
        private int firstActiveNoteIndex;
        private double futureVisibilityWindow => computeFutureVisibilityWindowMs(ApproachDuration);
        private double pastVisibilityWindow => missWindow + PastVisibilityBuffer;
        private bool isPreviewMode; // Preview still auto-judges for visuals, but suppresses result callbacks.

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        private Bindable<GameplayMode> gameplayMode = null!;
        private Bindable<bool> showParticleEffects = null!;
        private Bindable<bool> showGlowEffects = null!;
        private Bindable<bool> showHitBurstAnimations = null!;
        private Bindable<ManuscriptCountInGuideMode> manuscriptCountInGuideModeSetting = null!;

        private Container noteLayer = null!;
        private Container hitExplosionLayer = null!;
        private Container laneBackgroundContainer = null!;
        private Container threeDProfileHintContainer = null!;
        private SpriteText threeDProfileHintText = null!;

        private Container laneGuideOverlay = null!;
        private TimingGridOverlay? timingGridOverlay;
        private TimingStrikeZone? timingStrikeZone;
        // private KickGuideLine? kickGuideLine2D; // Removed unused field
        private ThreeDHighwayBackground? threeDHighwayBackground;
        /// <summary>Drum sheet music for manuscript mode (2026-10-24 rebuild); replaces the old manuscript note drawing.</summary>
        private DrumStaffView? drumStaffView;
        private Container strikeZoneHost = null!;
        private Beatmap? loadedBeatmap;

        private Bindable<LaneViewMode> laneViewMode = null!;
        private LaneViewMode currentLaneViewMode;
        private bool kickUsesGlobalLine = true;
        private string? manuscriptFocusComponent;

        public readonly Bindable<double> ZoomLevel = new Bindable<double>(1.00);
        public readonly Bindable<bool> AutoZoom = new Bindable<bool>(true);
        public readonly Bindable<double> NoteWidthScale = new Bindable<double>(1.0);
        public readonly Bindable<ThreeDStageProfile> StageProfile = new Bindable<ThreeDStageProfile>(ThreeDStageProfile.GhClassic);
        public LaneViewMode CurrentLaneViewMode => currentLaneViewMode;

        public event Action<HitResult, double, Color4, string>? ResultApplied;

        private double cachedBpm = TimingInfo.DefaultBpm;
        private double cachedBeatsPerMeasure = 4;
        private double cachedBeatUnitDenominator = 4;
        private int lastTimingPointIndex = -1;
        private readonly List<TimingPoint> sortedTimingPoints = new();
        private const double previewSeekResetPaddingMs = 260;
        private const double previewLightweightSeekDeltaThresholdMs = 480;
        private const double previewLightweightPrunePaddingMs = 420;
        private double lastJumpTargetTimeMs = double.NaN;
        private float lastLayoutAppliedWidth = float.NaN;
        private float lastLayoutAppliedHeight = float.NaN;

        private const double MinBeamGapBeats = 0.08;
        private const double SingleBeamThresholdBeats = 0.76;
        private const double DoubleBeamThresholdBeats = 0.38;
        private const double TripleBeamThresholdBeats = 0.19;
        private const double MinTieGapBeats = 1.15;
        private const double MaxTieGapBeats = 3.6;
        private const double DottedGapToleranceBeats = 0.075;
        private const int MaxTieInterveningVoiceNotes = 1;
        private const float MaxTieSpanRatio = 0.34f;
        private ThreeDProfileTuning currentThreeDProfileTuning = resolveThreeDProfileTuning(ThreeDStageProfile.GhClassic);

        private readonly struct SheetTimelineWindow
        {
            public SheetTimelineWindow(double startTime, double duration, float leftX, float rightX, float playheadX)
            {
                StartTime = startTime;
                Duration = duration;
                LeftX = leftX;
                RightX = rightX;
                PlayheadX = playheadX;
            }

            public double StartTime { get; }
            public double Duration { get; }
            public float LeftX { get; }
            public float RightX { get; }
            public float PlayheadX { get; }
        }

        public PlaybackPlayfield(
            Func<double> currentTimeProvider,
            Func<bool>? snapEnabledProvider = null,
            Func<double, double>? snapIntervalAtTimeProvider = null)
        {
            this.currentTimeProvider = currentTimeProvider;
            this.snapEnabledProvider = snapEnabledProvider;
            this.snapIntervalAtTimeProvider = snapIntervalAtTimeProvider;

            StageProfile.BindValueChanged(e =>
            {
                currentThreeDProfileTuning = resolveThreeDProfileTuning(e.NewValue);
                threeDHighwayBackground?.SetProfile(e.NewValue);
                updateThreeDProfileHint();
                if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
                    layoutDirty = true;
            }, true);

            RelativeSizeAxes = Axes.Both;
            Masking = true;
            CornerRadius = 12;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            gameplayMode = config.GetBindable<GameplayMode>(BeatSightSetting.GameplayMode);
            showParticleEffects = config.GetBindable<bool>(BeatSightSetting.ShowParticleEffects);
            showGlowEffects = config.GetBindable<bool>(BeatSightSetting.ShowGlowEffects);
            showHitBurstAnimations = config.GetBindable<bool>(BeatSightSetting.ShowHitBurstAnimations);
            manuscriptCountInGuideModeSetting = config.GetBindable<ManuscriptCountInGuideMode>(BeatSightSetting.ManuscriptCountInGuideMode);
            laneViewMode = config.GetBindable<LaneViewMode>(BeatSightSetting.LaneViewMode);

            laneGuideOverlay = createGuideOverlay();
            timingGridOverlay = new TimingGridOverlay
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                RelativeSizeAxes = Axes.Both,
                Width = PlayfieldWidthRatio
            };
            timingGridOverlay.SetPlayfield(this);
            timingStrikeZone = new TimingStrikeZone
            {
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                RelativeSizeAxes = Axes.X,
                Width = 0.98f // Will be relative to the constrained container
            };

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(26, 26, 40, 255)
                },
                laneBackgroundContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Width = PlayfieldWidthRatio
                },
                timingGridOverlay,
                // KickGuideLine removed
                strikeZoneHost = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Width = PlayfieldWidthRatio,
                    Child = timingStrikeZone
                },
                noteLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Width = PlayfieldWidthRatio
                },
                hitExplosionLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Width = PlayfieldWidthRatio
                },
                laneGuideOverlay,
                threeDProfileHintContainer = createThreeDProfileHintOverlay()
            };

            laneViewMode.BindValueChanged(onLaneViewModeChanged, true);
            manuscriptCountInGuideModeSetting.BindValueChanged(e =>
            {
                drumStaffView?.SetCountInGuideMode(e.NewValue);
            }, true);

            if (loadedBeatmap != null)
                LoadBeatmap(loadedBeatmap);
        }

        private Container createGuideOverlay()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Alpha = 0,
                Children = new Drawable[]
                {
                    createGuideEdge(-1),
                    createGuideEdge(1)
                }
            };
        }

        private Box createGuideEdge(int direction)
        {
            return new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 2,
                Anchor = direction < 0 ? Anchor.CentreLeft : Anchor.CentreRight,
                Origin = direction < 0 ? Anchor.CentreLeft : Anchor.CentreRight,
                Colour = new Color4(255, 255, 255, 40)
            };
        }

        private Container createThreeDProfileHintOverlay()
        {
            threeDProfileHintText = new SpriteText
            {
                Font = new FontUsage("Roboto", 11f),
                Colour = new Color4(220, 232, 252, 255),
                Text = string.Empty
            };

            return new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Margin = new MarginPadding { Left = 14, Top = 14 },
                Alpha = 0,
                Child = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 8,
                    BorderThickness = 1f,
                    BorderColour = new Color4(112, 146, 196, 170),
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(18, 29, 52, 230)
                        },
                        new Container
                        {
                            AutoSizeAxes = Axes.Both,
                            Padding = new MarginPadding { Horizontal = 10, Vertical = 5 },
                            Child = threeDProfileHintText
                        }
                    }
                }
            };
        }

        private void updateThreeDProfileHint()
        {
            if (threeDProfileHintContainer == null || threeDProfileHintText == null)
                return;

            // The stage profile is shown on the playback toolbar; keep the note highway free of text overlays.
            threeDProfileHintText.Text = $"3D Stage: {FormatThreeDProfileHintLabel(StageProfile.Value)}";
            threeDProfileHintContainer.Alpha = 0;
        }

        private void onLaneViewModeChanged(ValueChangedEvent<LaneViewMode> e)
        {
            currentLaneViewMode = e.NewValue;
            updateThreeDProfileHint();
            layoutDirty = true;
            updateLayout();
        }

        public void SetLaneLayout(LaneLayout layout)
        {
            laneLayout = layout;
            layoutDirty = true;
            updateLayout();
        }

        public void SetKickLineMode(bool enabled)
        {
            kickUsesGlobalLine = enabled;
            layoutDirty = true;
            updateLayout();
        }

        public void LoadBeatmap(Beatmap beatmap)
        {
            loadedBeatmap = beatmap;
            drumStaffView?.SetBeatmap(beatmap);
            notes.Clear();
            noteLayer?.Clear(false);
            firstActiveNoteIndex = 0;
            sortedTimingPoints.Clear();
            lastTimingPointIndex = -1;

            if (beatmap?.Timing != null)
            {
                cachedBpm = beatmap.Timing.Bpm > 0 ? beatmap.Timing.Bpm : TimingInfo.DefaultBpm;
                (int beatsPerMeasure, int beatUnitDenominator) = parseTimingSignature(beatmap.Timing.TimeSignature, 4, 4);
                cachedBeatsPerMeasure = beatsPerMeasure;
                cachedBeatUnitDenominator = beatUnitDenominator;
            }
            else
            {
                cachedBpm = TimingInfo.DefaultBpm;
                cachedBeatsPerMeasure = 4;
                cachedBeatUnitDenominator = 4;
            }

            if (beatmap == null)
                return;

            foreach (var hitObject in beatmap.HitObjects)
            {
                int lane = resolveLane(hitObject);
                Color4 accentColour = resolveLaneAccentColour(lane, hitObject.Component);
                var note = new DrawableNote(hitObject, lane, showGlowEffects, showParticleEffects, accentColour);
                notes.Add(note);
            }

            // Sort by time to ensure efficient processing
            notes.Sort((a, b) => a.HitTime.CompareTo(b.HitTime));

            if (beatmap.Timing?.TimingPoints != null && beatmap.Timing.TimingPoints.Count > 0)
            {
                sortedTimingPoints.AddRange(beatmap.Timing.TimingPoints.OrderBy(tp => tp.Time));
            }

            timingGridOverlay?.Configure(beatmap, laneLayout, kickUsesGlobalLine);
            updateLayout();
        }

        public void SetPreviewMode(bool preview)
        {
            isPreviewMode = preview;
            layoutDirty = true;
        }

        public void ForceVisualLayoutRefresh()
        {
            layoutDirty = true;
            lastLayoutAppliedWidth = float.NaN;
            lastLayoutAppliedHeight = float.NaN;
        }

        public double GetFutureViewportDurationMsAtZoom(double zoomLevel)
        {
            double currentTime = Math.Max(0, currentTimeProvider());
            double approachDurationAtZoom = computeApproachDurationAtZoom(currentTime, zoomLevel);
            return computeFutureVisibilityWindowMs(approachDurationAtZoom);
        }

        public void SetManuscriptFocusComponent(string? componentName)
        {
            string? normalized = string.IsNullOrWhiteSpace(componentName) ? null : componentName.Trim();
            if (string.Equals(manuscriptFocusComponent, normalized, StringComparison.OrdinalIgnoreCase))
                return;

            manuscriptFocusComponent = normalized;
            drumStaffView?.SetFocusComponent(manuscriptFocusComponent);
        }

        protected override void Update()
        {
            base.Update();

            bool sizeChanged = DrawWidth > 0
                && DrawHeight > 0
                && (!float.IsFinite(lastLayoutAppliedWidth)
                    || !float.IsFinite(lastLayoutAppliedHeight)
                    || Math.Abs(DrawWidth - lastLayoutAppliedWidth) >= 0.5f
                    || Math.Abs(DrawHeight - lastLayoutAppliedHeight) >= 0.5f);

            if (sizeChanged)
                layoutDirty = true;

            // If a previous updateLayout() bailed (e.g. DrawWidth was 0 during init),
            // retry now that the container has been sized.
            if (layoutDirty && DrawWidth > 0 && DrawHeight > 0)
                updateLayout();

            // Don't position notes until backgrounds are drawn with the current layout.
            // This prevents the lane-count mismatch where notes use 8 lanes but backgrounds show 7.
            if (layoutDirty)
                return;

            double currentTime = currentTimeProvider();

            // Calculate approach duration based on zoom settings
            updateApproachDuration(currentTime);

            updateNotes(currentTime);

            // Use the cached lane count from updateLayout() to guarantee consistency
            int activeLaneCount = cachedActiveLaneCount;

            // Calculate effective width (containers are already constrained to this width)
            float effectiveWidth = DrawWidth * PlayfieldWidthRatio;

            // Ensure strike zone geometry is updated every frame to handle resizing
            float hitLineY = resolveHitLineY(DrawHeight);
            float spawnTop = 0f; // Extend grid to top
            float travelDistance = hitLineY - spawnTop;

            if (timingStrikeZone != null)
            {
                timingStrikeZone.UpdateGeometry(effectiveWidth, DrawHeight, hitLineY, spawnTop, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, kickUsesGlobalLine, currentLaneViewMode);
            }

            timingGridOverlay?.UpdateState(currentTime, effectiveWidth, DrawHeight, spawnTop, hitLineY, travelDistance, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, currentLaneViewMode, kickUsesGlobalLine);

            threeDHighwayBackground?.UpdateScroll(currentTime);
            if (currentLaneViewMode == LaneViewMode.Manuscript && drumStaffView != null)
            {
                drumStaffView.SetTime(currentTime);
                drumStaffView.SetZoom(ZoomLevel.Value);
            }
        }

        private void updateApproachDuration(double currentTime)
        {
            // Always calculate BPM-based duration to ensure 1.0x matches the map's pacing
            if (loadedBeatmap?.Timing?.TimingPoints != null)
            {
                var timingPoints = loadedBeatmap.Timing.TimingPoints;

                // Simple optimization: check if next point is reached
                if (lastTimingPointIndex >= 0 && lastTimingPointIndex < timingPoints.Count - 1)
                {
                    if (currentTime >= timingPoints[lastTimingPointIndex + 1].Time)
                    {
                        lastTimingPointIndex++;
                        updateCachedTiming(timingPoints[lastTimingPointIndex]);
                    }
                }

                // If we jumped back or don't have an index, search
                if (lastTimingPointIndex == -1 || (lastTimingPointIndex < timingPoints.Count && currentTime < timingPoints[lastTimingPointIndex].Time))
                {
                    // Binary search or linear search from start
                    var timingPoint = timingPoints.LastOrDefault(tp => tp.Time <= currentTime);
                    if (timingPoint != null)
                    {
                        lastTimingPointIndex = timingPoints.IndexOf(timingPoint);
                        updateCachedTiming(timingPoint);
                    }
                    else
                    {
                        lastTimingPointIndex = -1;
                        cachedBpm = loadedBeatmap.Timing.Bpm > 0 ? loadedBeatmap.Timing.Bpm : TimingInfo.DefaultBpm;
                        (int parsedBeatsPerMeasure, int parsedBeatUnitDenominator) = parseTimingSignature(loadedBeatmap.Timing.TimeSignature, 4, 4);
                        cachedBeatsPerMeasure = parsedBeatsPerMeasure;
                        cachedBeatUnitDenominator = parsedBeatUnitDenominator;
                    }
                }
            }

            double safeBpm = cachedBpm > 0 && double.IsFinite(cachedBpm) ? cachedBpm : TimingInfo.DefaultBpm;
            double safeBeatUnitDenominator = cachedBeatUnitDenominator > 0 && double.IsFinite(cachedBeatUnitDenominator)
                ? cachedBeatUnitDenominator
                : 4.0;
            double beatDuration = 60000.0 / safeBpm * (4.0 / safeBeatUnitDenominator);

            double beatsPerMeasure = Math.Max(1, cachedBeatsPerMeasure);
            double targetVisibleBeats = BaseVisibleMeasures * beatsPerMeasure;
            double effectiveZoom = getEffectiveZoomFactor(currentTime, beatDuration, beatsPerMeasure);
            ApproachDuration = (targetVisibleBeats * beatDuration) / effectiveZoom;
        }

        private double getEffectiveZoomFactor(double currentTime, double beatDuration, double beatsPerMeasure)
        {
            double manualZoom = remapManualZoomForApproachDuration(ZoomLevel.Value);
            if (!AutoZoom.Value)
                return manualZoom;

            double autoZoomMultiplier = calculateAutoZoomMultiplier(currentTime, beatDuration, beatsPerMeasure);
            return manualZoom * autoZoomMultiplier;
        }

        private double calculateAutoZoomMultiplier(double currentTime, double beatDuration, double beatsPerMeasure)
        {
            if (beatDuration <= 0 || beatsPerMeasure <= 0 || notes.Count == 0)
                return AutoZoomBaseMultiplier;

            double lookaheadMs = beatDuration * beatsPerMeasure * 2.0;
            double windowStart = currentTime - beatDuration * 0.5;
            double windowEnd = currentTime + lookaheadMs;
            int sampleCount = 0;

            for (int i = Math.Max(0, firstActiveNoteIndex); i < notes.Count; i++)
            {
                double hitTime = notes[i].HitTime;
                if (hitTime > windowEnd)
                    break;
                if (hitTime >= windowStart)
                    sampleCount++;
            }

            double sampledBeats = lookaheadMs / beatDuration;
            double notesPerBeat = sampledBeats <= 0 ? 0 : sampleCount / sampledBeats;
            return CalculateAutoZoomMultiplier(cachedBpm, beatsPerMeasure, notesPerBeat);
        }

        internal static double CalculateAutoZoomMultiplier(double bpm, double beatsPerMeasure, double notesPerBeat)
        {
            double clampedBpm = Math.Max(1, bpm);
            double clampedMeasure = Math.Max(1, beatsPerMeasure);
            double clampedDensity = Math.Max(0, notesPerBeat);

            // Keep 1.0x manual as a true baseline and let auto-zoom provide a moderate
            // readability lift that scales mostly with local note density.
            double densityNormalized = Math.Clamp((clampedDensity - 0.30) / 1.85, 0.0, 1.0);
            double bpmNormalized = Math.Clamp((clampedBpm - 95.0) / 150.0, 0.0, 1.0);
            double signatureNormalized = Math.Clamp((clampedMeasure - 4.0) / 6.0, 0.0, 1.0);

            double multiplier = AutoZoomBaseMultiplier
                                + 0.52 * densityNormalized
                                + 0.16 * bpmNormalized
                                + 0.09 * signatureNormalized;

            return Math.Clamp(multiplier, AutoZoomBaseMultiplier, AutoZoomMaxMultiplier);
        }

        private void updateCachedTiming(TimingPoint timingPoint)
        {
            if (timingPoint.Bpm > 0) cachedBpm = timingPoint.Bpm;

            if (!string.IsNullOrEmpty(timingPoint.TimeSignature))
            {
                int fallbackBeatsPerMeasure = (int)Math.Clamp(Math.Round(cachedBeatsPerMeasure), 1, 32);
                int fallbackBeatUnitDenominator = (int)Math.Clamp(Math.Round(cachedBeatUnitDenominator), 1, 32);
                (int beatsPerMeasure, int beatUnitDenominator) = parseTimingSignature(
                    timingPoint.TimeSignature,
                    fallbackBeatsPerMeasure,
                    fallbackBeatUnitDenominator);
                cachedBeatsPerMeasure = beatsPerMeasure;
                cachedBeatUnitDenominator = beatUnitDenominator;
            }
        }

        private void updateNotes(double currentTime)
        {
            if (notes.Count == 0)
                return;

            float drawHeight = DrawHeight;
            float effectiveWidth = DrawWidth * PlayfieldWidthRatio;

            float hitLineY = resolveHitLineY(drawHeight);
            float spawnTop = 0f;
            float travelDistance = hitLineY - spawnTop;

            bool staffNotation = currentLaneViewMode == LaneViewMode.Manuscript;
            pruneNotesOutsideVisibilityWindow(currentTime, futureVisibilityWindow);

            // Clean up notes that have fully expired (well past the hit line)
            while (firstActiveNoteIndex < notes.Count && notes[firstActiveNoteIndex].HitTime < currentTime - pastVisibilityWindow)
            {
                noteLayer.Remove(notes[firstActiveNoteIndex], false);
                firstActiveNoteIndex++;
            }

            // Auto-trigger ALL notes that have reached the hit line
            for (int i = firstActiveNoteIndex; i < notes.Count; i++)
            {
                var note = notes[i];
                if (note.HitTime >= currentTime)
                    break;

                if (!note.IsJudged)
                {
                    applyResult(note, HitResult.Perfect, 0);
                }
            }

            // Update visible notes
            for (int i = firstActiveNoteIndex; i < notes.Count; i++)
            {
                var note = notes[i];
                double timeUntilHit = note.HitTime - currentTime;

                if (timeUntilHit > futureVisibilityWindow)
                    break;

                // Don't re-add judged or disposed notes that were already consumed in this timeline state.
                if (note.Parent == null)
                {
                    if (note.IsDisposedPublic || note.IsJudged)
                        continue;

                    noteLayer.Add(note);
                    note.RestartAnimation();
                    note.ApplyKickMode(kickUsesGlobalLine, laneLayout.KickLane);
                }

                // Sheet music is drawn by the staff view; the note drawables only carry judging and hit sounds there.
                if (staffNotation)
                {
                    note.Alpha = 0;
                    continue;
                }

                if (currentLaneViewMode == LaneViewMode.TwoDimensional)
                    note.Height = resolveTwoDimensionalNoteHeight(note.HitTime, drawHeight);

                updateNotePosition(note, (float)timeUntilHit, effectiveWidth, drawHeight, hitLineY, travelDistance);
            }
        }

        private SheetTimelineWindow resolveSheetTimelineWindow(double currentTime, float drawWidth, float drawHeight)
        {
            _ = currentTime;
            _ = drawWidth;
            _ = drawHeight;

            if (drumStaffView == null || !drumStaffView.HasLayout)
                return default;

            // Same mapping the staff view draws with, so editor placement lines up with the notation.
            float left = drumStaffView.TimelineLeftX;
            float right = Math.Max(left + 1f, drumStaffView.DrawWidth);
            double start = drumStaffView.TimeAtX(left);
            return new SheetTimelineWindow(start, drumStaffView.TimeAtX(right) - start, left, right, drumStaffView.PlayheadX);
        }

        private int getBeatIndex(double time, double beatOrigin, double beatDuration)
        {
            if (beatDuration <= 0.0)
                return 0;

            return (int)Math.Floor(((time - beatOrigin) / beatDuration) + 0.0001);
        }

        private void resolveTimingForHitTime(double hitTime, out double beatDuration, out double beatOrigin)
        {
            double bpm = cachedBpm > 0 ? cachedBpm : TimingInfo.DefaultBpm;
            beatOrigin = loadedBeatmap?.Timing?.Offset ?? 0;
            int beatsPerMeasure = (int)Math.Clamp(Math.Round(cachedBeatsPerMeasure), 1, 32);
            int beatUnitDenominator = (int)Math.Clamp(Math.Round(cachedBeatUnitDenominator), 1, 32);

            if (loadedBeatmap?.Timing != null)
                (beatsPerMeasure, beatUnitDenominator) = parseTimingSignature(loadedBeatmap.Timing.TimeSignature, beatsPerMeasure, beatUnitDenominator);

            beatDuration = 60000.0 / Math.Max(1.0, bpm) * (4.0 / Math.Max(1.0, beatUnitDenominator));

            if (sortedTimingPoints.Count == 0)
                return;

            TimingPoint activePoint = sortedTimingPoints[0];
            for (int i = 0; i < sortedTimingPoints.Count; i++)
            {
                if (sortedTimingPoints[i].Time > hitTime)
                    break;

                activePoint = sortedTimingPoints[i];
            }

            if (activePoint.Bpm > 0)
                bpm = activePoint.Bpm;

            if (!string.IsNullOrWhiteSpace(activePoint.TimeSignature))
                (beatsPerMeasure, beatUnitDenominator) = parseTimingSignature(activePoint.TimeSignature, beatsPerMeasure, beatUnitDenominator);

            beatDuration = 60000.0 / Math.Max(1.0, bpm) * (4.0 / Math.Max(1.0, beatUnitDenominator));

            beatOrigin = activePoint.Time;
        }

        private void updateNotePosition(
            DrawableNote note,
            float timeUntilHit,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance)
        {
            // Use the dynamic ApproachDuration here
            float progress = 1 - (timeUntilHit / (float)ApproachDuration);

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
                updateNotePosition3D(note, progress, drawWidth, drawHeight, hitLineY);
            else
                updateNotePosition2D(note, progress, drawWidth, drawHeight, hitLineY, travelDistance);
        }

        private void updateNotePosition2D(DrawableNote note, float progress, float drawWidth, float drawHeight, float hitLineY, float travelDistance)
        {
            float y = hitLineY - travelDistance * (1 - progress);

            if (kickUsesGlobalLine && note.IsKick)
            {
                // Kick notes use full-width global line
                note.Anchor = Anchor.TopLeft;
                note.RelativePositionAxes = Axes.None;
                note.Width = drawWidth;
                note.Position = new Vector2(drawWidth / 2, y);
                note.Scale = Vector2.One;
                note.Rotation = 0;
            }
            else
            {
                // Absolute pixel positioning — no relative axes, no containers
                // Use cachedActiveLaneCount from updateLayout() instead of recomputing,
                // to guarantee consistency between background lanes and note lanes.
                int activeLaneCount = cachedActiveLaneCount;
                float actualParentWidth = noteLayer.DrawWidth;
                float actualLaneWidthPx = actualParentWidth / activeLaneCount;
                note.Width = resolveLaneNoteWidth2D(actualLaneWidthPx);

                int visualLaneIndex = note.Lane;
                if (kickUsesGlobalLine && note.Lane > laneLayout.KickLane)
                    visualLaneIndex--;

                // CRITICAL: use noteLayer.DrawWidth, NOT the passed-in drawWidth (which is PlaybackPlayfield.DrawWidth * ratio).
                // If these differ, notes will be mispositioned!
                float laneCenterX = (visualLaneIndex + 0.5f) * actualLaneWidthPx;

                // Origin = Centre (set in DrawableNote constructor), Anchor = TopLeft
                // So the note's centre point is placed at Position
                note.Anchor = Anchor.TopLeft;
                note.RelativePositionAxes = Axes.None;
                note.Position = new Vector2(laneCenterX, y);
                note.Scale = Vector2.One;
                note.Rotation = 0;
            }

            // Update depth for Z-ordering
            setNoteDepth(note, 0);

            // Unjudged notes past the hit line: hide as safety fallback
            // Judged notes: ApplyResult animation handles the fade-out
            if (!note.IsJudged)
            {
                if (y > hitLineY + note.Height / 2 + 2)
                    note.Alpha = 0;
                else
                    note.Alpha = 1;
            }
        }

        private void updateNotePosition3D(DrawableNote note, float progress, float drawWidth, float drawHeight, float hitLineY)
        {
            note.Anchor = Anchor.TopLeft;
            note.RelativePositionAxes = Axes.None;
            var tuning = currentThreeDProfileTuning;
            float clampedProgress = Math.Clamp(progress, 0f, tuning.ProgressMax);
            float normalizedProgress = clampedProgress / Math.Max(0.001f, tuning.ProgressMax);
            normalizedProgress = Math.Clamp(normalizedProgress, 0f, 1f);
            // Stronger easing exaggerates stage depth so 3D does not collapse into a flat 2D look.
            float perspectiveProgress = 1f - MathF.Pow(1f - normalizedProgress, tuning.PerspectiveExponent);

            float vanishingPointY = drawHeight * tuning.VanishingPointYRatio;
            float highwayWidthAtBottom = drawWidth * tuning.HighwayBottomWidthRatio;
            float highwayWidthAtTop = drawWidth * tuning.HighwayTopWidthRatio;

            int activeLaneCount = cachedActiveLaneCount;
            float widthProgress = MathF.Pow(perspectiveProgress, tuning.WidthExponent);
            float currentHighwayWidth = lerp(highwayWidthAtTop, highwayWidthAtBottom, widthProgress);
            float currentLaneWidth = currentHighwayWidth / activeLaneCount;
            float y = lerp(vanishingPointY, hitLineY, MathF.Pow(perspectiveProgress, tuning.YExponent));
            float noteScaleSetting = (float)Math.Clamp(NoteWidthScale.Value, 0.5, 1.5);
            float laneNoteWidthFactor = lerp(
                tuning.LaneNoteWidthAtTop,
                tuning.LaneNoteWidthAtBottom,
                perspectiveProgress);
            float laneFillWidth = Math.Max(tuning.MinNoteWidth, currentLaneWidth - 2f);
            float baseLaneWidth = Math.Clamp(
                currentLaneWidth * laneNoteWidthFactor,
                tuning.MinNoteWidth,
                tuning.MaxNoteWidth);
            float noteWidth = resolveLaneNoteWidth3D(baseLaneWidth, laneFillWidth, noteScaleSetting, tuning);
            float noteHeight = Math.Clamp(
                noteWidth * lerp(tuning.NoteHeightRatioAtTop, tuning.NoteHeightRatioAtBottom, perspectiveProgress),
                tuning.MinNoteHeight,
                tuning.MaxNoteHeight);

            // A stage much wider than 2:1 (the editor preview) squeezes the travel distance; thin the notes with it so
            // consecutive hits stay separate instead of stacking into one bar. Practice stages are about 2:1 and unchanged.
            float verticalCompression = Math.Clamp(drawHeight / Math.Max(1f, drawWidth * 0.5f), 0.4f, 1f);
            noteHeight = Math.Max(3f, noteHeight * verticalCompression);

            bool isGlobalKickVisual = kickUsesGlobalLine && note.IsKick;
            float baseKickWidth = Math.Clamp(
                currentHighwayWidth * lerp(tuning.KickWidthAtTop, tuning.KickWidthAtBottom, perspectiveProgress),
                28f,
                152f);
            float finalNoteWidth = isGlobalKickVisual
                ? resolveKickWidth3D(baseKickWidth, currentHighwayWidth, noteScaleSetting)
                : noteWidth;
            float finalNoteHeight = isGlobalKickVisual
                ? Math.Clamp(noteHeight * 0.88f, tuning.MinNoteHeight, 26f)
                : noteHeight;

            note.Width = finalNoteWidth;
            note.Height = finalNoteHeight;
            if (isGlobalKickVisual)
                note.ApplyKickLineDimensions(finalNoteWidth, finalNoteHeight, LaneViewMode.ThreeDimensional);

            float x;
            if (isGlobalKickVisual)
            {
                x = drawWidth / 2f;
            }
            else
            {
                // Calculate X
                int visualLaneIndex = note.Lane;
                if (kickUsesGlobalLine && note.Lane > laneLayout.KickLane)
                    visualLaneIndex--;

                // Center the highway
                float highwayLeft = (drawWidth - currentHighwayWidth) / 2;
                x = highwayLeft + currentLaneWidth * visualLaneIndex + currentLaneWidth / 2;
            }

            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            float lateral = (x - drawWidth * 0.5f) / Math.Max(1f, drawWidth * 0.5f);
            note.Rotation = -lateral * (1f - perspectiveProgress) * tuning.RotationStrength;

            setNoteDepth(note, perspectiveProgress);

            // Unjudged notes past the hit line: hide as safety fallback
            // Judged notes: ApplyResult animation handles the fade-out
            if (!note.IsJudged)
            {
                if (y > hitLineY + note.Height / 2 + 2)
                    note.Alpha = 0;
                else
                note.Alpha = lerp(0.5f, 1f, perspectiveProgress);
            }
        }

        private float resolveTwoDimensionalNoteHeight(double currentTime, float drawHeight)
        {
            if (ApproachDuration <= 0 || drawHeight <= 0)
                return 10f;

            double bpm = resolveTimingBpmAt(currentTime);
            double quarterDuration = 60000.0 / bpm;
            double sixteenthDuration = quarterDuration / 4.0;
            float travelDistance = Math.Max(1f, resolveHitLineY(drawHeight));

            // Notes are thin bars of a fixed share of the highway height (about 17 px at 1080p), like other 2D note
            // highways. They used to be 64% of the sixteenth-note gap (up to 44 px), which turned zoomed-in or slower
            // charts into tall bricks. They still never exceed 60% of the sixteenth gap, so fast runs stay separate.
            float sixteenthSpacing = (float)(sixteenthDuration / ApproachDuration * travelDistance);
            float barHeight = Math.Clamp(travelDistance * 0.022f, 8f, 22f);
            float legacyHeight = Math.Clamp(Math.Min(barHeight, sixteenthSpacing * 0.6f), 4f, 22f);

            if (!isSnapCollisionAvoidanceEnabled())
                return legacyHeight;

            double snapIntervalMs = resolveSnapIntervalMsForCurrentTime(currentTime);
            if (!double.IsFinite(snapIntervalMs) || snapIntervalMs <= 0.01)
                return legacyHeight;

            float snapSpacing = (float)(snapIntervalMs / Math.Max(1.0, ApproachDuration) * travelDistance);
            if (!float.IsFinite(snapSpacing) || snapSpacing <= 0.01f)
                return legacyHeight;

            // If spacing is comfortably larger than the current body height, keep legacy sizing
            // to avoid making sparse patterns unnecessarily thin.
            if (snapSpacing >= legacyHeight + 8f)
                return legacyHeight;

            // Drive collision-avoidance from snap density in quarter-note space so signatures
            // like 6/8 and dense divisors (1/6, 1/8, 1/12+) scale consistently.
            double notesPerQuarter = quarterDuration / snapIntervalMs;
            float snapDensity = (float)Math.Clamp((notesPerQuarter - 2.0) / 10.0, 0.0, 1.0);
            float preferredSpacingRatio = lerp(0.70f, 0.42f, snapDensity);
            float minimumSpacingRatio = lerp(0.28f, 0.14f, snapDensity);

            float collisionCap = Math.Max(1.0f, snapSpacing - 1.25f);
            float preferredHeight = snapSpacing * preferredSpacingRatio;
            float lowerBound = Math.Clamp(snapSpacing * minimumSpacingRatio, 1.2f, 7f);
            float effectiveLowerBound = Math.Min(lowerBound, collisionCap);
            float snapAwareHeight = Math.Min(legacyHeight, Math.Max(effectiveLowerBound, preferredHeight));
            float minimumAllowedHeight = Math.Min(1.2f, collisionCap);

            // Tiny 2D preview heights and very dense snap grids can push the collision cap below the
            // nominal 1.2px floor. Clamp against the reduced cap instead of throwing.
            return Math.Clamp(snapAwareHeight, minimumAllowedHeight, collisionCap);
        }

        private bool isSnapCollisionAvoidanceEnabled()
        {
            if (snapEnabledProvider == null)
                return true;

            return snapEnabledProvider();
        }

        private double resolveSnapIntervalMsForCurrentTime(double currentTime)
        {
            double providerInterval = snapIntervalAtTimeProvider?.Invoke(currentTime) ?? double.NaN;
            if (double.IsFinite(providerInterval) && providerInterval > 0.01)
                return providerInterval;

            int divisor = Math.Max(1, loadedBeatmap?.Editor?.SnapDivisor ?? 4);
            double bpm = resolveTimingBpmAt(currentTime);
            if (!double.IsFinite(bpm) || bpm <= 0)
                return double.NaN;

            double beatUnitDenominator = resolveTimingBeatUnitDenominatorAt(currentTime);
            double beatUnitDuration = 60000.0 / bpm * (4.0 / Math.Max(1.0, beatUnitDenominator));
            return beatUnitDuration / divisor;
        }

        private Color4 resolveLaneAccentColour(int lane, string component)
        {
            int resolvedLane = laneLayout.ClampLane(lane);
            if (LaneManagement.TryGetLaneColor(loadedBeatmap, resolvedLane, out Color4 laneColour))
                return laneColour;

            return GetLaneIdentity(resolvedLane).Colour;
        }

        /// <summary>
        /// Name, short label and colour of a logical lane, shared by the 2D, 3D and manuscript views.
        /// Explicit beatmap lane metadata (editor-customised names/colours) takes precedence.
        /// </summary>
        public LaneIdentity GetLaneIdentity(int logicalLane)
        {
            int lane = laneLayout.ClampLane(logicalLane);
            var identity = LaneIdentityResolver.Resolve(laneLayout, lane);

            if (LaneManagement.TryGetLaneColor(loadedBeatmap, lane, out Color4 customColour))
                identity = identity with { Colour = customColour };

            if (LaneManagement.TryGetLaneInfo(loadedBeatmap, lane, out var info) && LaneManagement.IsCustomLaneName(info, lane))
                identity = identity with { Name = info.Name!, ShortName = string.IsNullOrWhiteSpace(info.ShortName) ? identity.ShortName : info.ShortName! };

            return identity;
        }

        private double resolveTimingBpmAt(double currentTime)
        {
            double bpm = loadedBeatmap?.Timing?.Bpm ?? TimingInfo.DefaultBpm;
            if (loadedBeatmap?.Timing?.TimingPoints != null)
            {
                var timingPoint = loadedBeatmap.Timing.TimingPoints.LastOrDefault(tp => tp.Time <= currentTime);
                if (timingPoint != null && timingPoint.Bpm > 0)
                    bpm = timingPoint.Bpm;
            }

            if (!double.IsFinite(bpm) || bpm <= 0)
                bpm = TimingInfo.DefaultBpm;

            return bpm;
        }

        private double resolveTimingBeatsPerMeasureAt(double currentTime)
            => resolveTimingSignatureAt(currentTime).BeatsPerMeasure;

        private double resolveTimingBeatUnitDenominatorAt(double currentTime)
            => resolveTimingSignatureAt(currentTime).BeatUnitDenominator;

        private (double BeatsPerMeasure, double BeatUnitDenominator) resolveTimingSignatureAt(double currentTime)
        {
            int beatsPerMeasure = 4;
            int beatUnitDenominator = 4;

            (beatsPerMeasure, beatUnitDenominator) = parseTimingSignature(loadedBeatmap?.Timing?.TimeSignature, beatsPerMeasure, beatUnitDenominator);

            if (loadedBeatmap?.Timing?.TimingPoints != null)
            {
                var timingPoint = loadedBeatmap.Timing.TimingPoints.LastOrDefault(tp => tp.Time <= currentTime);
                if (timingPoint != null && !string.IsNullOrWhiteSpace(timingPoint.TimeSignature))
                {
                    (beatsPerMeasure, beatUnitDenominator) = parseTimingSignature(timingPoint.TimeSignature, beatsPerMeasure, beatUnitDenominator);
                }
            }

            return (Math.Clamp(beatsPerMeasure, 1, 16), Math.Clamp(beatUnitDenominator, 1, 32));
        }

        private static (int BeatsPerMeasure, int BeatUnitDenominator) parseTimingSignature(
            string? signature,
            int fallbackBeatsPerMeasure,
            int fallbackBeatUnitDenominator)
        {
            int beatsPerMeasure = fallbackBeatsPerMeasure;
            int beatUnitDenominator = fallbackBeatUnitDenominator;
            if (string.IsNullOrWhiteSpace(signature))
                return (beatsPerMeasure, beatUnitDenominator);

            string[] parts = signature.Split('/');
            if (parts.Length > 0 && int.TryParse(parts[0], out int numerator) && numerator > 0)
                beatsPerMeasure = numerator;

            if (parts.Length > 1 && int.TryParse(parts[1], out int denominator) && denominator > 0)
                beatUnitDenominator = denominator;

            return (beatsPerMeasure, beatUnitDenominator);
        }

        private double computeApproachDurationAtZoom(double currentTime, double zoomLevel)
        {
            double bpm = resolveTimingBpmAt(currentTime);
            double beatsPerMeasure = resolveTimingBeatsPerMeasureAt(currentTime);
            double beatUnitDenominator = resolveTimingBeatUnitDenominatorAt(currentTime);
            double beatDuration = 60000.0 / Math.Max(1, bpm) * (4.0 / Math.Max(1.0, beatUnitDenominator));
            double targetVisibleBeats = BaseVisibleMeasures * Math.Max(1, beatsPerMeasure);

            double effectiveZoom = remapManualZoomForApproachDuration(zoomLevel);
            if (isPreviewMode)
                effectiveZoom *= computePreviewZoomBoost(zoomLevel);

            if (AutoZoom.Value)
                effectiveZoom *= calculateAutoZoomMultiplier(currentTime, beatDuration, beatsPerMeasure);

            return (targetVisibleBeats * beatDuration) / Math.Max(0.1, effectiveZoom);
        }

        private static double computePreviewZoomBoost(double zoomLevel)
        {
            double clamped = Math.Clamp(zoomLevel, ManualZoomMin, ManualZoomMax);
            double normalized = (clamped - ManualZoomMin) / (ManualZoomMax - ManualZoomMin);
            double lowEndBoost = PreviewZoomLowEndBoost * Math.Pow(1.0 - normalized, PreviewZoomLowEndExponent);
            double highEndBoost = PreviewZoomHighEndBoost * Math.Pow(normalized, PreviewZoomHighEndExponent);
            return 1.0 + lowEndBoost + highEndBoost;
        }

        private static double computeFutureVisibilityPaddingMs(double approachDurationMs)
        {
            if (!double.IsFinite(approachDurationMs) || approachDurationMs <= 0)
                return FutureVisibilityLeadInMinMs;

            return Math.Clamp(
                approachDurationMs * FutureVisibilityLeadInRatio,
                FutureVisibilityLeadInMinMs,
                FutureVisibilityLeadInMaxMs);
        }

        private static double computeFutureVisibilityWindowMs(double approachDurationMs)
            => Math.Max(0, approachDurationMs + computeFutureVisibilityPaddingMs(approachDurationMs));

        /// <summary>
        /// Manual zoom is a direct multiplier on the map's pacing: 1.0x shows <see cref="BaseVisibleMeasures"/>
        /// measures of look-ahead, 2.0x half of that. (Before 2026-10-24 a curve turned 1.0 into ~2.97x and left
        /// about half a second of look-ahead; saved settings are migrated in BeatSightConfigManager.)
        /// </summary>
        private static double remapManualZoomForApproachDuration(double zoomLevel)
            => Math.Clamp(zoomLevel, ManualZoomMin, ManualZoomMax);

        private void pruneNotesOutsideVisibilityWindow(double currentTime, double futureVisibilityWindowMs)
        {
            if (noteLayer == null || noteLayer.Count == 0)
                return;

            const double visibilityPrunePaddingMs = 120;
            double minVisible = currentTime - pastVisibilityWindow - visibilityPrunePaddingMs;
            double maxVisible = currentTime + futureVisibilityWindowMs + visibilityPrunePaddingMs;

            foreach (var note in noteLayer.Children.OfType<DrawableNote>().ToArray())
            {
                if (note.IsDisposedPublic || note.HitTime < minVisible || note.HitTime > maxVisible)
                    noteLayer.Remove(note, false);
            }
        }

        private float resolveLaneNoteWidth2D(float laneWidthPx)
        {
            float safeLaneWidth = Math.Max(1f, laneWidthPx);
            float noteScale = (float)Math.Clamp(NoteWidthScale.Value, 0.5, 1.5);
            float laneFillWidth = Math.Max(14f, safeLaneWidth - 2f);
            float legacyUpperBound = Math.Min(160f, laneFillWidth);
            float legacyWidth = Math.Clamp(safeLaneWidth * 0.45f * noteScale, 40f, legacyUpperBound);

            if (noteScale <= 1f || laneFillWidth <= legacyUpperBound + 0.01f)
                return legacyWidth;

            float baseWidthAtOne = Math.Clamp(safeLaneWidth * 0.45f, 40f, legacyUpperBound);
            float expansionProgress = Math.Clamp((noteScale - 1f) / 0.5f, 0f, 1f);
            float easedExpansion = expansionProgress * expansionProgress;
            return Math.Clamp(lerp(baseWidthAtOne, laneFillWidth, easedExpansion), 40f, laneFillWidth);
        }

        private static float resolveLaneNoteWidth3D(float baseLaneWidth, float laneFillWidth, float noteScale, ThreeDProfileTuning tuning)
        {
            float legacyWidth = Math.Clamp(baseLaneWidth * noteScale, tuning.MinNoteWidth, tuning.MaxNoteWidth);
            if (noteScale <= 1f || laneFillWidth <= tuning.MaxNoteWidth + 0.01f)
                return legacyWidth;

            float expansionProgress = Math.Clamp((noteScale - 1f) / 0.5f, 0f, 1f);
            float easedExpansion = expansionProgress * expansionProgress;
            return Math.Clamp(lerp(baseLaneWidth, laneFillWidth, easedExpansion), tuning.MinNoteWidth, laneFillWidth);
        }

        private static float resolveKickWidth3D(float baseKickWidth, float currentHighwayWidth, float noteScale)
        {
            float legacyWidth = Math.Clamp(baseKickWidth * noteScale, 28f, 152f);
            float kickFillWidth = Math.Max(baseKickWidth, currentHighwayWidth * 0.98f);
            if (noteScale <= 1f || kickFillWidth <= 152f + 0.01f)
                return legacyWidth;

            float expansionProgress = Math.Clamp((noteScale - 1f) / 0.5f, 0f, 1f);
            float easedExpansion = expansionProgress * expansionProgress;
            return Math.Clamp(lerp(baseKickWidth, kickFillWidth, easedExpansion), 28f, Math.Max(152f, currentHighwayWidth));
        }

        private static float lerp(float start, float end, float amount) => start + (end - start) * amount;

        private float resolveHitLineRatio()
        {
            float baseRatio = currentLaneViewMode switch
            {
                LaneViewMode.ThreeDimensional => DesignSystem.HitLineRatio3D,
                LaneViewMode.Manuscript => DesignSystem.HitLineRatioManuscript,
                _ => DesignSystem.DefaultHitLineRatio
            };

            if (isPreviewMode && currentLaneViewMode == LaneViewMode.TwoDimensional)
                baseRatio -= PreviewTwoDimensionalHitLineLift;

            return Math.Clamp(baseRatio, 0.78f, 0.95f);
        }

        private float resolveHitLineY(float drawHeight)
            => Math.Max(0f, drawHeight * resolveHitLineRatio());

        private void setNoteDepth(DrawableNote note, float depth)
        {
            if (noteLayer == null || note.Parent != noteLayer)
                return;

            // Validate depth is not NaN or Infinity
            if (float.IsNaN(depth) || float.IsInfinity(depth))
            {
                // Log error but don't crash
                return;
            }

            float tolerance = currentLaneViewMode == LaneViewMode.ThreeDimensional
                ? DepthTolerance.ThreeDimensional
                : DepthTolerance.TwoDimensional;

            if (note.ShouldUpdateDepth(depth, tolerance))
            {
                try
                {
                    noteLayer.ChangeChildDepth(note, depth);
                }
                catch (InvalidOperationException ex)
                {
                    // Depth changes can fail during scene graph updates - this is non-critical
                    Logger.Log($"Note depth change failed: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                }
            }
        }

        private void applyResult(DrawableNote note, HitResult result, double offset)
        {
            if (note.IsJudged)
                return;

            note.ApplyResult(result);
            if (!isPreviewMode)
                ResultApplied?.Invoke(result, offset, note.AccentColour, note.ComponentName);

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional && threeDHighwayBackground != null)
            {
                float hitIntensity = result switch
                {
                    HitResult.Perfect => 1.0f,
                    HitResult.Great => 0.82f,
                    HitResult.Good => 0.66f,
                    HitResult.Meh => 0.52f,
                    HitResult.Miss => 0.28f,
                    _ => 0.35f
                };

                if (kickUsesGlobalLine && note.IsKick)
                {
                    threeDHighwayBackground.TriggerBeatPulse(0.5f + 0.45f * hitIntensity);
                }
                else
                {
                    int visualLaneIndex = note.Lane;
                    if (kickUsesGlobalLine && note.Lane > laneLayout.KickLane)
                        visualLaneIndex--;

                    visualLaneIndex = Math.Clamp(visualLaneIndex, 0, Math.Max(0, cachedActiveLaneCount - 1));
                    threeDHighwayBackground.TriggerLaneHit(visualLaneIndex, hitIntensity);
                }
            }

            // Spawn a hit explosion effect at the note's current position
            if (showHitBurstAnimations.Value && hitExplosionLayer != null)
            {
                var explosion = new HitExplosion(note.AccentColour, note.DrawWidth, note.Height);
                explosion.Position = note.Position;
                hitExplosionLayer.Add(explosion);
            }
        }

        public HitResult HandleInput(int lane, double currentTime)
        {
            DrawableNote? targetNote = null;
            double bestDiff = double.MaxValue;

            // Look ahead to find the best candidate
            for (int i = firstActiveNoteIndex; i < notes.Count; i++)
            {
                var note = notes[i];

                // Optimization: if note is too far in future, stop
                if (note.HitTime - currentTime > missWindow)
                    break;

                if (note.IsJudged)
                    continue;

                bool isTarget = false;

                if (kickUsesGlobalLine && note.IsKick)
                {
                    if (lane == laneLayout.KickLane)
                        isTarget = true;
                }
                else
                {
                    if (note.Lane == lane)
                        isTarget = true;
                }

                if (isTarget)
                {
                    double diff = Math.Abs(note.HitTime - currentTime);
                    if (diff < bestDiff)
                    {
                        bestDiff = diff;
                        targetNote = note;
                    }
                }
            }

            if (targetNote != null)
            {
                bool isGhostNote = targetNote.Velocity < 0.4;
                double effectiveMissWindow = missWindow * (isGhostNote ? 1.5 : 1.0);

                if (bestDiff <= effectiveMissWindow)
                {
                    double offset = currentTime - targetNote.HitTime;
                    var result = getHitResult(Math.Abs(offset), isGhostNote);

                    if (result != HitResult.None)
                    {
                        applyResult(targetNote, result, offset);
                        return result;
                    }
                }
            }

            return HitResult.None;
        }

        private HitResult getHitResult(double absOffset, bool isGhostNote = false)
        {
            double multiplier = isGhostNote ? 1.5 : 1.0;

            if (absOffset <= perfectWindow * multiplier) return HitResult.Perfect;
            if (absOffset <= greatWindow * multiplier) return HitResult.Great;
            if (absOffset <= goodWindow * multiplier) return HitResult.Good;
            if (absOffset <= mehWindow * multiplier) return HitResult.Meh;
            if (absOffset <= missWindow * multiplier) return HitResult.Miss;
            return HitResult.None;
        }

        private void applyKickModeToNotes()
        {
            if (notes.Count == 0)
                return;

            int globalLane = laneLayout?.KickLane ?? 0;

            foreach (var note in notes)
                note.ApplyKickMode(kickUsesGlobalLine, globalLane);
        }

        private int resolveLane(HitObject hit)
        {
            // Simple fallback if heuristics fail or aren't available
            if (hit.Lane.HasValue)
                return laneLayout.ClampLane(hit.Lane.Value);

            if (Enum.TryParse<DrumComponentCategory>(hit.Component, true, out var category))
            {
                if (laneLayout.Categories.TryGetValue(category, out var lanes) && lanes.Count > 0)
                {
                    return lanes[0];
                }
            }

            // Fallback for unknown components
            string comp = hit.Component.ToLowerInvariant();
            if (comp.Contains("kick")) return laneLayout.KickLane;
            if (comp.Contains("snare")) return laneLayout.SnareLane;
            if (comp.Contains("hihat")) return laneLayout.HiHatLane;
            if (comp.Contains("ride") || comp.Contains("crash")) return laneLayout.RideLane;

            return 0; // Default
        }

        private void updateLayout()
        {
            if (laneBackgroundContainer == null) return;
            if (DrawWidth <= 0 || DrawHeight <= 0) return;

            layoutDirty = false;
            lastLayoutAppliedWidth = DrawWidth;
            lastLayoutAppliedHeight = DrawHeight;

            laneBackgroundContainer.Clear();

            // The staff view draws its own playhead, ruler and notes; hide the highway-style overlays and the
            // per-note drawables (they still exist for judging and hit sounds).
            bool staffNotation = currentLaneViewMode == LaneViewMode.Manuscript;
            float highwayLayerAlpha = staffNotation ? 0f : 1f;
            strikeZoneHost.Alpha = highwayLayerAlpha;
            noteLayer.Alpha = highwayLayerAlpha;
            hitExplosionLayer.Alpha = highwayLayerAlpha;

            // Calculate active lanes (excluding kick lane if global)
            int activeLaneCount = kickUsesGlobalLine ? Math.Max(1, laneCount - 1) : laneCount;

            // Cache for use in Update() and updateNotePosition2D() so notes
            // are always positioned consistently with the drawn backgrounds.
            cachedActiveLaneCount = activeLaneCount;

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                threeDHighwayBackground = new ThreeDHighwayBackground(laneLayout, kickUsesGlobalLine, StageProfile.Value, GetLaneIdentity);
                drumStaffView = null;
                laneBackgroundContainer.Add(threeDHighwayBackground);

                // if (kickGuideLine2D != null) kickGuideLine2D.Alpha = 0;
                if (timingStrikeZone != null) timingStrikeZone.SetViewMode(LaneViewMode.ThreeDimensional);
                if (timingGridOverlay != null) timingGridOverlay.SetViewMode(LaneViewMode.ThreeDimensional);
            }
            else if (currentLaneViewMode == LaneViewMode.Manuscript)
            {
                threeDHighwayBackground = null;
                drumStaffView = new DrumStaffView { Compact = isPreviewMode };
                drumStaffView.SetBeatmap(loadedBeatmap);
                drumStaffView.SetCountInGuideMode(manuscriptCountInGuideModeSetting.Value);
                drumStaffView.SetZoom(ZoomLevel.Value);
                drumStaffView.SetTime(currentTimeProvider());
                laneBackgroundContainer.Add(drumStaffView);

                // if (kickGuideLine2D != null) kickGuideLine2D.Alpha = 0;
                if (timingStrikeZone != null) timingStrikeZone.SetViewMode(LaneViewMode.Manuscript);
                if (timingGridOverlay != null) timingGridOverlay.SetViewMode(LaneViewMode.Manuscript);
            }
            else
            {
                threeDHighwayBackground = null;
                drumStaffView = null;
                Color4 twoDimensionalBase = isPreviewMode
                    ? new Color4(20, 29, 48, 255)
                    : new Color4(20, 20, 30, 255);
                Color4 twoDimensionalLaneTint = isPreviewMode
                    ? new Color4(120, 168, 255, 20)
                    : new Color4(255, 255, 255, 8);
                // Quiet separators: lanes are identified by note colour and labels, so the grid should not compete.
                Color4 twoDimensionalSeparator = isPreviewMode
                    ? new Color4(178, 212, 255, 70)
                    : new Color4(255, 255, 255, 30);
                // Add 2D background - fully opaque to prevent any bleed-through
                laneBackgroundContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = twoDimensionalBase
                });

                if (isPreviewMode)
                {
                    laneBackgroundContainer.Add(new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 38f,
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        Masking = true,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(28, 41, 68, 188)
                            },
                            new Box
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 1,
                                Anchor = Anchor.TopLeft,
                                Origin = Anchor.TopLeft,
                                Colour = new Color4(146, 184, 255, 82)
                            },
                            new Box
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 1,
                                Anchor = Anchor.BottomLeft,
                                Origin = Anchor.BottomLeft,
                                Colour = new Color4(96, 128, 188, 108)
                            }
                        }
                    });
                }

                // Add lane separators, background tints, and labels
                float laneWidth = 1.0f / activeLaneCount; // Relative to container width
                for (int i = 0; i < activeLaneCount; i++)
                {
                    // Alternating lane background tint for visual lane distinction
                    if (i % 2 == 1)
                    {
                        laneBackgroundContainer.Add(new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            RelativePositionAxes = Axes.X,
                            Anchor = Anchor.TopLeft,
                            Origin = Anchor.TopLeft,
                            X = i * laneWidth,
                            Width = laneWidth,
                            Colour = twoDimensionalLaneTint
                        });
                    }

                    // Lane separator (skip first lane)
                    if (i > 0)
                    {
                        laneBackgroundContainer.Add(new Box
                        {
                            RelativeSizeAxes = Axes.Y,
                            Width = 2,
                            RelativePositionAxes = Axes.X,
                            X = i * laneWidth,
                            Colour = twoDimensionalSeparator
                        });
                    }

                    // Lane label at bottom, in the lane's instrument colour so it doubles as a legend.
                    string label = getLaneLabelForIndex(i, activeLaneCount);
                    laneBackgroundContainer.Add(new SpriteText
                    {
                        Text = label,
                        Font = BeatSightFont.Label(isPreviewMode ? 10f : 13f),
                        Colour = UITheme.Mix(getLaneIdentityForVisualIndex(i).Colour, UITheme.TextPrimary, 0.25f),
                        RelativePositionAxes = Axes.Both,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.BottomCentre,
                        X = (i + 0.5f) * laneWidth,
                        Y = isPreviewMode ? 0.968f : 0.98f
                    });
                }
                float effectiveWidth = DrawWidth * PlayfieldWidthRatio;
                if (timingStrikeZone != null)
                    timingStrikeZone.UpdateGeometry(effectiveWidth, DrawHeight, resolveHitLineY(DrawHeight), 0f, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, kickUsesGlobalLine, currentLaneViewMode);
            }

            applyKickModeToNotes();
        }
        /// Get a human-readable label for a visual lane index.
        /// Prefers explicit beatmap lane metadata when available.
        /// </summary>
        private string getLaneLabelForIndex(int laneIndex, int totalLanes)
            => getLaneIdentityForVisualIndex(laneIndex).Name;

        private LaneIdentity getLaneIdentityForVisualIndex(int laneIndex)
        {
            int logicalLane = laneIndex;
            if (kickUsesGlobalLine && logicalLane >= laneLayout.KickLane)
                logicalLane++;

            return GetLaneIdentity(logicalLane);
        }

        public string GetLaneLabelForLogicalLane(int logicalLane)
        {
            return GetLaneIdentity(logicalLane).Name;
        }

        public bool TryResolveLaneFromScreenSpace(Vector2 screenSpacePosition, out int lane)
        {
            lane = 0;

            if (noteLayer == null || DrawWidth <= 0 || DrawHeight <= 0)
                return false;

            Vector2 local = noteLayer.ToLocalSpace(screenSpacePosition);
            if (local.X < 0 || local.X > noteLayer.DrawWidth || local.Y < 0 || local.Y > noteLayer.DrawHeight)
                return false;

            int activeLaneCount = Math.Max(1, cachedActiveLaneCount);
            float laneWidth = noteLayer.DrawWidth / activeLaneCount;
            if (!float.IsFinite(laneWidth) || laneWidth <= 0)
                return false;

            int visualLane = Math.Clamp((int)(local.X / laneWidth), 0, activeLaneCount - 1);
            int logicalLane = visualLane;

            if (kickUsesGlobalLine && logicalLane >= laneLayout.KickLane)
                logicalLane++;

            lane = laneLayout.ClampLane(logicalLane);
            return true;
        }

        public bool TryResolvePlacementFromScreenSpace(Vector2 screenSpacePosition, out int lane, out double hitTimeMs)
        {
            lane = 0;
            hitTimeMs = Math.Max(0, currentTimeProvider());

            if (!TryResolveLaneFromScreenSpace(screenSpacePosition, out lane))
                return false;

            if (noteLayer == null || DrawWidth <= 0 || DrawHeight <= 0)
                return false;

            Vector2 local = noteLayer.ToLocalSpace(screenSpacePosition);
            if (!tryComputePlacementTimeFromLocalPosition(local, out hitTimeMs))
                hitTimeMs = Math.Max(0, currentTimeProvider());

            return true;
        }

        public bool TryResolvePlacementScreenSpace(int lane, double hitTimeMs, out Vector2 screenSpacePosition)
        {
            screenSpacePosition = Vector2.Zero;

            if (noteLayer == null || DrawWidth <= 0 || DrawHeight <= 0)
                return false;

            if (!tryComputePlacementLocalPosition(lane, hitTimeMs, out Vector2 local))
                return false;

            screenSpacePosition = noteLayer.ToScreenSpace(local);
            return true;
        }

        public bool TryResolvePlacementNoteSize(int lane, double hitTimeMs, out Vector2 noteSizeScreen)
        {
            noteSizeScreen = Vector2.Zero;

            if (noteLayer == null || DrawWidth <= 0 || DrawHeight <= 0)
                return false;

            int resolvedLane = laneLayout.ClampLane(lane);
            bool isGlobalKickVisual = kickUsesGlobalLine && resolvedLane == laneLayout.KickLane;
            if (!tryResolvePlacementNoteSizeLocal(resolvedLane, hitTimeMs, isGlobalKickVisual, out Vector2 localSize))
                return false;

            if (!tryComputePlacementLocalPosition(resolvedLane, hitTimeMs, out Vector2 localAnchor))
                return false;

            Vector2 halfSize = localSize * 0.5f;
            Vector2 leftScreen = noteLayer.ToScreenSpace(localAnchor - new Vector2(halfSize.X, 0));
            Vector2 rightScreen = noteLayer.ToScreenSpace(localAnchor + new Vector2(halfSize.X, 0));
            Vector2 topScreen = noteLayer.ToScreenSpace(localAnchor - new Vector2(0, halfSize.Y));
            Vector2 bottomScreen = noteLayer.ToScreenSpace(localAnchor + new Vector2(0, halfSize.Y));

            noteSizeScreen = new Vector2(
                Math.Max(1f, Math.Abs(rightScreen.X - leftScreen.X)),
                Math.Max(1f, Math.Abs(bottomScreen.Y - topScreen.Y)));
            return true;
        }

        private bool tryResolvePlacementNoteSizeLocal(int resolvedLane, double hitTimeMs, bool isGlobalKickVisual, out Vector2 localSize)
        {
            localSize = new Vector2(28f, 10f);

            if (noteLayer == null || DrawWidth <= 0 || DrawHeight <= 0)
                return false;

            double currentTime = Math.Max(0, currentTimeProvider());
            if (currentLaneViewMode == LaneViewMode.Manuscript)
            {
                // A notehead on the staff view.
                float space = drumStaffView?.StaffSpace > 0 ? drumStaffView.StaffSpace : 12f;
                localSize = new Vector2(space * 1.3f, space * 0.96f);
                return true;
            }

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                if (ApproachDuration <= 0)
                    return false;

                var tuning = currentThreeDProfileTuning;
                float drawWidth = DrawWidth * PlayfieldWidthRatio;
                float drawHeight = DrawHeight;
                double timeUntilHit = hitTimeMs - currentTime;
                float progress = 1f - (float)(timeUntilHit / Math.Max(1.0, ApproachDuration));
                float clampedProgress = Math.Clamp(progress, 0f, tuning.ProgressMax);
                float normalizedProgress = Math.Clamp(clampedProgress / Math.Max(0.001f, tuning.ProgressMax), 0f, 1f);
                float perspectiveProgress = 1f - MathF.Pow(1f - normalizedProgress, tuning.PerspectiveExponent);

                float highwayWidthAtBottom = drawWidth * tuning.HighwayBottomWidthRatio;
                float highwayWidthAtTop = drawWidth * tuning.HighwayTopWidthRatio;
                int activeLaneCount = Math.Max(1, cachedActiveLaneCount);
                float widthProgress = MathF.Pow(perspectiveProgress, tuning.WidthExponent);
                float currentHighwayWidth = lerp(highwayWidthAtTop, highwayWidthAtBottom, widthProgress);
                float currentLaneWidth = currentHighwayWidth / activeLaneCount;

                float noteScaleSetting = (float)Math.Clamp(NoteWidthScale.Value, 0.5, 1.5);
                float laneNoteWidthFactor = lerp(
                    tuning.LaneNoteWidthAtTop,
                    tuning.LaneNoteWidthAtBottom,
                    perspectiveProgress);
                float laneFillWidth = Math.Max(tuning.MinNoteWidth, currentLaneWidth - 2f);
                float baseLaneWidth = Math.Clamp(
                    currentLaneWidth * laneNoteWidthFactor,
                    tuning.MinNoteWidth,
                    tuning.MaxNoteWidth);
                float noteWidth = resolveLaneNoteWidth3D(baseLaneWidth, laneFillWidth, noteScaleSetting, tuning);
                float noteHeight = Math.Clamp(
                    noteWidth * lerp(tuning.NoteHeightRatioAtTop, tuning.NoteHeightRatioAtBottom, perspectiveProgress),
                    tuning.MinNoteHeight,
                    tuning.MaxNoteHeight);

                float baseKickWidth = Math.Clamp(
                    currentHighwayWidth * lerp(tuning.KickWidthAtTop, tuning.KickWidthAtBottom, perspectiveProgress),
                    28f,
                    152f);
                float finalNoteWidth = isGlobalKickVisual
                    ? resolveKickWidth3D(baseKickWidth, currentHighwayWidth, noteScaleSetting)
                    : noteWidth;
                float finalNoteHeight = isGlobalKickVisual
                    ? Math.Clamp(noteHeight * 0.88f, tuning.MinNoteHeight, 26f)
                    : noteHeight;

                localSize = new Vector2(finalNoteWidth, finalNoteHeight);
                return true;
            }

            int laneCount = Math.Max(1, cachedActiveLaneCount);
            float laneWidthPx = noteLayer.DrawWidth / laneCount;
            float width = isGlobalKickVisual ? noteLayer.DrawWidth : resolveLaneNoteWidth2D(laneWidthPx);
            float height = resolveTwoDimensionalNoteHeight(hitTimeMs, DrawHeight);
            localSize = new Vector2(width, height);
            return true;
        }

        private bool tryComputePlacementTimeFromLocalPosition(Vector2 local, out double hitTimeMs)
        {
            double currentTime = Math.Max(0, currentTimeProvider());
            hitTimeMs = currentTime;

            if (ApproachDuration <= 0)
                return false;

            if (currentLaneViewMode == LaneViewMode.Manuscript)
            {
                float effectiveWidth = DrawWidth * PlayfieldWidthRatio;
                SheetTimelineWindow sheetWindow = resolveSheetTimelineWindow(currentTime, effectiveWidth, DrawHeight);
                if (sheetWindow.Duration <= 0)
                    return false;

                float timelineWidth = Math.Max(1f, sheetWindow.RightX - sheetWindow.LeftX);
                double normalized = (local.X - sheetWindow.LeftX) / timelineWidth;
                hitTimeMs = Math.Max(0, sheetWindow.StartTime + normalized * sheetWindow.Duration);
                return true;
            }

            float hitLineY = resolveHitLineY(DrawHeight);
            if (hitLineY <= 0)
                return false;

            double timeUntilHit;
            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                var tuning = currentThreeDProfileTuning;
                float vanishingPointY = DrawHeight * tuning.VanishingPointYRatio;
                float yRange = Math.Max(1f, hitLineY - vanishingPointY);
                float verticalProgress = Math.Clamp((local.Y - vanishingPointY) / yRange, 0f, 1f);
                float perspectiveProgress = MathF.Pow(verticalProgress, 1f / Math.Max(0.001f, tuning.YExponent));
                float normalizedProgress = 1f - MathF.Pow(1f - Math.Clamp(perspectiveProgress, 0f, 1f), 1f / Math.Max(0.001f, tuning.PerspectiveExponent));
                float progress = Math.Clamp(normalizedProgress * tuning.ProgressMax, 0f, tuning.ProgressMax);
                timeUntilHit = (1.0 - progress) * ApproachDuration;
            }
            else
            {
                float progress = local.Y / hitLineY;
                timeUntilHit = (1.0 - progress) * ApproachDuration;
            }

            hitTimeMs = Math.Max(0, currentTime + timeUntilHit);
            return true;
        }

        private bool tryComputePlacementLocalPosition(int lane, double hitTimeMs, out Vector2 localPosition)
        {
            localPosition = Vector2.Zero;

            if (noteLayer == null || DrawWidth <= 0 || DrawHeight <= 0 || ApproachDuration <= 0)
                return false;

            int resolvedLane = laneLayout.ClampLane(lane);
            bool isGlobalKickVisual = kickUsesGlobalLine && resolvedLane == laneLayout.KickLane;
            double currentTime = Math.Max(0, currentTimeProvider());
            double timeUntilHit = hitTimeMs - currentTime;
            float hitLineY = resolveHitLineY(DrawHeight);
            if (hitLineY <= 0)
                return false;

            float x;
            float y;

            if (currentLaneViewMode == LaneViewMode.Manuscript)
            {
                float effectiveWidth = DrawWidth * PlayfieldWidthRatio;
                SheetTimelineWindow sheetWindow = resolveSheetTimelineWindow(currentTime, effectiveWidth, DrawHeight);
                if (sheetWindow.Duration <= 0)
                    return false;

                float timelineWidth = Math.Max(1f, sheetWindow.RightX - sheetWindow.LeftX);
                double normalized = (hitTimeMs - sheetWindow.StartTime) / sheetWindow.Duration;
                x = sheetWindow.LeftX + (float)normalized * timelineWidth;
                y = hitLineY;
            }
            else if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                var tuning = currentThreeDProfileTuning;
                float drawWidth = DrawWidth * PlayfieldWidthRatio;
                float drawHeight = DrawHeight;

                float progress = 1f - (float)(timeUntilHit / Math.Max(1.0, ApproachDuration));
                float clampedProgress = Math.Clamp(progress, 0f, tuning.ProgressMax);
                float normalizedProgress = Math.Clamp(clampedProgress / Math.Max(0.001f, tuning.ProgressMax), 0f, 1f);
                float perspectiveProgress = 1f - MathF.Pow(1f - normalizedProgress, tuning.PerspectiveExponent);

                float vanishingPointY = drawHeight * tuning.VanishingPointYRatio;
                float highwayWidthAtBottom = drawWidth * tuning.HighwayBottomWidthRatio;
                float highwayWidthAtTop = drawWidth * tuning.HighwayTopWidthRatio;

                int activeLaneCount = Math.Max(1, cachedActiveLaneCount);
                float widthProgress = MathF.Pow(perspectiveProgress, tuning.WidthExponent);
                float currentHighwayWidth = lerp(highwayWidthAtTop, highwayWidthAtBottom, widthProgress);
                float currentLaneWidth = currentHighwayWidth / activeLaneCount;
                y = lerp(vanishingPointY, hitLineY, MathF.Pow(perspectiveProgress, tuning.YExponent));

                if (isGlobalKickVisual)
                {
                    x = drawWidth / 2f;
                }
                else
                {
                    int visualLane = resolvedLane;
                    if (kickUsesGlobalLine && visualLane > laneLayout.KickLane)
                        visualLane--;

                    float highwayLeft = (drawWidth - currentHighwayWidth) / 2f;
                    x = highwayLeft + currentLaneWidth * visualLane + currentLaneWidth / 2f;
                }
            }
            else
            {
                float progress = 1f - (float)(timeUntilHit / Math.Max(1.0, ApproachDuration));
                y = hitLineY * progress;

                if (isGlobalKickVisual)
                {
                    x = noteLayer.DrawWidth / 2f;
                }
                else
                {
                    int activeLaneCount = Math.Max(1, cachedActiveLaneCount);
                    int visualLane = resolvedLane;
                    if (kickUsesGlobalLine && visualLane > laneLayout.KickLane)
                        visualLane--;

                    float laneWidth = noteLayer.DrawWidth / activeLaneCount;
                    x = (visualLane + 0.5f) * laneWidth;
                }
            }

            localPosition = new Vector2(
                Math.Clamp(x, 0f, Math.Max(0f, noteLayer.DrawWidth)),
                Math.Clamp(y, 0f, Math.Max(0f, noteLayer.DrawHeight)));
            return true;
        }

        public void JumpToTime(double time, bool lightweightSeek = false)
        {
            double clampedTime = Math.Max(0, time);

            if (lightweightSeek && isPreviewMode && canUseLightweightPreviewSeek(clampedTime))
            {
                resetPreviewNotesAroundTime(clampedTime);
                prunePreviewVisibleNotes(clampedTime);
                hitExplosionLayer?.Clear(false);
                firstActiveNoteIndex = findFirstNoteIndexAtOrAfter(clampedTime - pastVisibilityWindow);
                lastJumpTargetTimeMs = clampedTime;
                return;
            }

            if (isPreviewMode)
                resetPreviewNotesAroundTime(clampedTime);
            else
            {
                foreach (var note in notes)
                    note.Reset();
            }

            noteLayer.Clear(false);
            hitExplosionLayer?.Clear(false);

            firstActiveNoteIndex = findFirstNoteIndexAtOrAfter(clampedTime - pastVisibilityWindow);
            lastJumpTargetTimeMs = clampedTime;
        }

        private bool canUseLightweightPreviewSeek(double targetTimeMs)
        {
            if (double.IsNaN(lastJumpTargetTimeMs))
                return false;

            return Math.Abs(targetTimeMs - lastJumpTargetTimeMs) <= previewLightweightSeekDeltaThresholdMs;
        }

        private void prunePreviewVisibleNotes(double currentTimeMs)
        {
            if (noteLayer == null || noteLayer.Count == 0)
                return;

            double minVisible = currentTimeMs - pastVisibilityWindow - previewLightweightPrunePaddingMs;
            double maxVisible = currentTimeMs + futureVisibilityWindow + previewLightweightPrunePaddingMs;

            foreach (var note in noteLayer.Children.OfType<DrawableNote>().ToArray())
            {
                if (note.HitTime < minVisible || note.HitTime > maxVisible)
                    noteLayer.Remove(note, false);
            }
        }

        private void resetPreviewNotesAroundTime(double time)
        {
            if (notes.Count == 0)
                return;

            double resetStartTime = time - pastVisibilityWindow - previewSeekResetPaddingMs;
            double resetEndTime = time + futureVisibilityWindow + previewSeekResetPaddingMs;

            int resetStartIndex = Math.Max(0, findFirstNoteIndexAtOrAfter(resetStartTime) - 1);
            int resetEndIndex = findFirstNoteIndexAtOrAfter(resetEndTime);

            for (int i = resetStartIndex; i < resetEndIndex; i++)
                notes[i].Reset();
        }

        private int findFirstNoteIndexAtOrAfter(double hitTimeMs)
        {
            int low = 0;
            int high = notes.Count;
            while (low < high)
            {
                int mid = low + (high - low) / 2;
                if (notes[mid].HitTime < hitTimeMs)
                    low = mid + 1;
                else
                    high = mid;
            }

            return low;
        }

        public void StartSession(bool restart)
        {
            if (restart)
            {
                foreach (var note in notes)
                    note.Reset();

                firstActiveNoteIndex = 0;
                noteLayer.Clear(false);
                hitExplosionLayer?.Clear(false);
            }
        }

        public void RegisterInput(int lane)
        {
            double time = currentTimeProvider();
            HandleInput(lane, time);
        }


    }
}
