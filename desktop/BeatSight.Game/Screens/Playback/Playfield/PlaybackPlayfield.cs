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

        /// <summary>Shared 3D playfield geometry tuning for playback and editor preview.</summary>
        private static class ThreeDimensionalTuning
        {
            public const float VanishingPointYRatio = 0.11f;
            public const float HighwayBottomWidthRatio = 0.74f;
            public const float HighwayTopWidthRatio = 0.12f;
            public const float ProgressMin = 0.0f;
            public const float ProgressMax = 1.12f;
            public const float LaneNoteWidthAtTop = 0.24f;
            public const float LaneNoteWidthAtBottom = 0.63f;
            public const float MinNoteWidth = 14f;
            public const float MaxNoteWidth = 108f;
            public const float MinNoteHeight = 8f;
            public const float MaxNoteHeight = 28f;
            public const float KickWidthAtTop = 0.075f;
            public const float KickWidthAtBottom = 0.30f;
        }

        private static class SheetMusicTuning
        {
            public const float TimelineWidthRatio = 0.84f;
            public const float TimelineCenterYRatio = 0.56f;
            public const double VisibleMeasures = 2.0;
            public const float PlayheadRatio = 0.24f;
            public const float NoteWidthRatio = 0.018f;
            public const float NoteHeightRatio = 0.56f;
            public const float MinNoteWidth = 9f;
            public const float MaxNoteWidth = 28f;
            public const float MinNoteHeight = 9f;
            public const float MaxNoteHeight = 26f;
        }

        /// <summary>Width ratio of the playfield relative to container. 1.0 = full width.</summary>
        private const float PlayfieldWidthRatio = 1f;
        private const float HitLineYRatio = 0.935f;

        /// <summary>Additional visibility buffer after miss window (ms).</summary>
        private const double PastVisibilityBuffer = 600;
        private const double BaseVisibleMeasures = 2.15;
        private const double AutoZoomBaseMultiplier = 1.08;
        private const double AutoZoomMaxMultiplier = 1.42;

        private readonly Func<double> currentTimeProvider;
        private readonly List<DrawableNote> notes = new();
        private readonly List<DrawableNote> kickNoteBuffer = new();
        private int firstActiveNoteIndex;
        private double futureVisibilityWindow => ApproachDuration + 900;
        private double pastVisibilityWindow => missWindow + PastVisibilityBuffer;
        private bool isPreviewMode; // Preview still auto-judges for visuals, but suppresses result callbacks.

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        private Bindable<GameplayMode> gameplayMode = null!;
        private Bindable<bool> showParticleEffects = null!;
        private Bindable<bool> showGlowEffects = null!;
        private Bindable<bool> showHitBurstAnimations = null!;

        private Container noteLayer = null!;
        private Container hitExplosionLayer = null!;
        private Container laneBackgroundContainer = null!;
        private Container manuscriptBeamLayer = null!;

        private Container laneGuideOverlay = null!;
        private TimingGridOverlay? timingGridOverlay;
        private TimingStrikeZone? timingStrikeZone;
        // private KickGuideLine? kickGuideLine2D; // Removed unused field
        private ThreeDHighwayBackground? threeDHighwayBackground;
        private ManuscriptBackgroundEnhanced? manuscriptBackground;
        private Beatmap? loadedBeatmap;

        private Bindable<LaneViewMode> laneViewMode = null!;
        private LaneViewMode currentLaneViewMode;
        private bool kickUsesGlobalLine = true;
        private string? manuscriptFocusComponent;

        public readonly Bindable<double> ZoomLevel = new Bindable<double>(1.0);
        public readonly Bindable<bool> AutoZoom = new Bindable<bool>(true);
        public readonly Bindable<double> NoteWidthScale = new Bindable<double>(1.0);

        public event Action<HitResult, double, Color4, string>? ResultApplied;

        private double cachedBpm = 120;
        private double cachedBeatsPerMeasure = 4;
        private int lastTimingPointIndex = -1;
        private readonly List<TimingPoint> sortedTimingPoints = new();

        private const float ManuscriptPrimaryBeamThickness = 3.2f;
        private const float ManuscriptSecondaryBeamThickness = 2.4f;
        private const float ManuscriptBeamSpacing = 5.2f;
        private const float ManuscriptBeamAlpha = 0.84f;
        private const double MinBeamGapBeats = 0.08;
        private const double SingleBeamThresholdBeats = 0.76;
        private const double DoubleBeamThresholdBeats = 0.38;
        private const double TripleBeamThresholdBeats = 0.19;
        private static readonly Color4 manuscriptBeamColor = new Color4(42, 50, 66, 255);

        private readonly struct ManuscriptBeamAnchor
        {
            public ManuscriptBeamAnchor(
                DrawableNote note,
                ManuscriptBackgroundEnhanced.ManuscriptNotationVoice voice,
                int notationIndex,
                bool stemDown,
                float stemX,
                float stemTipY,
                double hitTime,
                double beatDuration,
                double beatOrigin)
            {
                Note = note;
                Voice = voice;
                NotationIndex = notationIndex;
                StemDown = stemDown;
                StemX = stemX;
                StemTipY = stemTipY;
                HitTime = hitTime;
                BeatDuration = beatDuration;
                BeatOrigin = beatOrigin;
            }

            public DrawableNote Note { get; }
            public ManuscriptBackgroundEnhanced.ManuscriptNotationVoice Voice { get; }
            public int NotationIndex { get; }
            public bool StemDown { get; }
            public float StemX { get; }
            public float StemTipY { get; }
            public double HitTime { get; }
            public double BeatDuration { get; }
            public double BeatOrigin { get; }
        }

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

        public PlaybackPlayfield(Func<double> currentTimeProvider)
        {
            this.currentTimeProvider = currentTimeProvider;

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
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Width = PlayfieldWidthRatio,
                    Child = timingStrikeZone
                },
                manuscriptBeamLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Width = PlayfieldWidthRatio
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
                laneGuideOverlay
            };

            laneViewMode.BindValueChanged(onLaneViewModeChanged, true);

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

        private void onLaneViewModeChanged(ValueChangedEvent<LaneViewMode> e)
        {
            currentLaneViewMode = e.NewValue;
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
            notes.Clear();
            noteLayer.Clear(false);
            manuscriptBeamLayer.Clear(false);
            firstActiveNoteIndex = 0;
            sortedTimingPoints.Clear();

            if (beatmap == null)
                return;

            foreach (var hitObject in beatmap.HitObjects)
            {
                int lane = resolveLane(hitObject);
                var note = new DrawableNote(hitObject, lane, showGlowEffects, showParticleEffects);
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
        }

        public void SetManuscriptFocusComponent(string? componentName)
        {
            string? normalized = string.IsNullOrWhiteSpace(componentName) ? null : componentName.Trim();
            if (string.Equals(manuscriptFocusComponent, normalized, StringComparison.OrdinalIgnoreCase))
                return;

            manuscriptFocusComponent = normalized;
            manuscriptBackground?.SetFocusedComponent(manuscriptFocusComponent);
        }

        protected override void Update()
        {
            base.Update();

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
            float hitLineY = DrawHeight * HitLineYRatio;
            float spawnTop = 0f; // Extend grid to top
            float travelDistance = hitLineY - spawnTop;

            if (timingStrikeZone != null)
            {
                timingStrikeZone.UpdateGeometry(effectiveWidth, DrawHeight, hitLineY, spawnTop, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, kickUsesGlobalLine, currentLaneViewMode);
            }

            timingGridOverlay?.UpdateState(currentTime, effectiveWidth, DrawHeight, spawnTop, hitLineY, travelDistance, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, currentLaneViewMode, kickUsesGlobalLine);

            threeDHighwayBackground?.UpdateScroll(currentTime);
            if (currentLaneViewMode == LaneViewMode.Manuscript && manuscriptBackground != null)
            {
                SheetTimelineWindow sheetWindow = resolveSheetTimelineWindow(currentTime, effectiveWidth, DrawHeight);
                resolveTimingForHitTime(currentTime, out double beatDuration, out double beatOrigin);
                int markerSubdivision = resolveManuscriptTimelineSubdivision(sheetWindow, beatDuration);
                manuscriptBackground.SetTimelineWindow(
                    sheetWindow.StartTime,
                    sheetWindow.Duration,
                    sheetWindow.PlayheadX,
                    sheetWindow.LeftX,
                    sheetWindow.RightX,
                    (int)Math.Max(1, Math.Round(cachedBeatsPerMeasure)),
                    beatOrigin,
                    markerSubdivision);
                manuscriptBackground.UpdatePlaybackPosition(currentTime, cachedBpm);
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
                        cachedBpm = loadedBeatmap.Timing.Bpm;
                        cachedBeatsPerMeasure = 4; // Default
                    }
                }
            }

            double beatDuration = 60000.0 / cachedBpm;

            double beatsPerMeasure = Math.Max(1, cachedBeatsPerMeasure);
            double targetVisibleBeats = BaseVisibleMeasures * beatsPerMeasure;
            double effectiveZoom = getEffectiveZoomFactor(currentTime, beatDuration, beatsPerMeasure);
            ApproachDuration = (targetVisibleBeats * beatDuration) / effectiveZoom;
        }

        private double getEffectiveZoomFactor(double currentTime, double beatDuration, double beatsPerMeasure)
        {
            double manualZoom = Math.Max(0.1, ZoomLevel.Value);
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

            // Density drives the majority of zoom-in pressure, with smaller boosts for higher tempos
            // and compound signatures so dense charts remain legible.
            double densityNormalized = Math.Clamp((clampedDensity - 0.70) / 1.90, 0.0, 1.0);
            double bpmNormalized = Math.Clamp((clampedBpm - 110.0) / 150.0, 0.0, 1.0);
            double signatureNormalized = Math.Clamp((clampedMeasure - 4.0) / 6.0, 0.0, 1.0);

            double multiplier = AutoZoomBaseMultiplier
                                + 0.22 * densityNormalized
                                + 0.12 * bpmNormalized
                                + 0.04 * signatureNormalized;

            return Math.Clamp(multiplier, AutoZoomBaseMultiplier, AutoZoomMaxMultiplier);
        }

        private void updateCachedTiming(TimingPoint timingPoint)
        {
            if (timingPoint.Bpm > 0) cachedBpm = timingPoint.Bpm;

            if (!string.IsNullOrEmpty(timingPoint.TimeSignature))
            {
                var parts = timingPoint.TimeSignature.Split('/');
                if (parts.Length > 0 && int.TryParse(parts[0], out int num))
                    cachedBeatsPerMeasure = num;
            }
        }

        private void updateNotes(double currentTime)
        {
            if (notes.Count == 0)
            {
                clearManuscriptBeams();
                return;
            }

            float drawHeight = DrawHeight;
            float effectiveWidth = DrawWidth * PlayfieldWidthRatio;

            float hitLineY = drawHeight * HitLineYRatio;
            float spawnTop = 0f;
            float travelDistance = hitLineY - spawnTop;

            // Calculate note height based on 16th note duration
            double bpm = 120;
            if (loadedBeatmap?.Timing != null)
            {
                var timingPoints = loadedBeatmap.Timing.TimingPoints;
                var timingPoint = timingPoints?.LastOrDefault(tp => tp.Time <= currentTime);

                if (timingPoint != null && timingPoint.Bpm > 0)
                    bpm = timingPoint.Bpm;
                else
                    bpm = loadedBeatmap.Timing.Bpm;
            }
            if (bpm <= 0) bpm = 120;

            double beatDuration = 60000.0 / bpm;
            double sixteenthDuration = beatDuration / 4.0;

            // Use the dynamic ApproachDuration here
            float noteHeight = (float)(sixteenthDuration / ApproachDuration * travelDistance);
            noteHeight = Math.Max(10f, noteHeight * 0.6f); // Scale height down visually
            SheetTimelineWindow sheetWindow = default;
            if (currentLaneViewMode == LaneViewMode.Manuscript)
                sheetWindow = resolveSheetTimelineWindow(currentTime, effectiveWidth, drawHeight);

            List<ManuscriptBeamAnchor>? manuscriptBeamAnchors = currentLaneViewMode == LaneViewMode.Manuscript
                ? new List<ManuscriptBeamAnchor>()
                : null;

            double activeFutureVisibilityWindow = futureVisibilityWindow;
            if (currentLaneViewMode == LaneViewMode.Manuscript && sheetWindow.Duration > 0)
                activeFutureVisibilityWindow = Math.Max(activeFutureVisibilityWindow, sheetWindow.Duration + 500);

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

                if (timeUntilHit > activeFutureVisibilityWindow)
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

                // Reset height to calculated height
                note.Height = noteHeight;

                updateNotePosition(
                    note,
                    (float)timeUntilHit,
                    effectiveWidth,
                    drawHeight,
                    hitLineY,
                    travelDistance,
                    sheetWindow);

                if (manuscriptBeamAnchors != null && !note.IsJudged && note.Alpha > 0.01f)
                    manuscriptBeamAnchors.Add(createManuscriptBeamAnchor(note));
            }

            if (manuscriptBeamAnchors != null)
                updateManuscriptBeams(manuscriptBeamAnchors);
            else
                clearManuscriptBeams();
        }

        private SheetTimelineWindow resolveSheetTimelineWindow(double currentTime, float drawWidth, float drawHeight)
        {
            double beatsPerMeasure = Math.Max(1, cachedBeatsPerMeasure);
            double beatDuration = cachedBpm > 0 ? 60000.0 / cachedBpm : 500.0;
            double measureDuration = Math.Max(beatDuration, beatDuration * beatsPerMeasure);
            double effectiveZoom = getEffectiveZoomFactor(currentTime, beatDuration, beatsPerMeasure);
            double windowDuration = (measureDuration * SheetMusicTuning.VisibleMeasures) / effectiveZoom;
            double playheadRatio = Math.Clamp(SheetMusicTuning.PlayheadRatio, 0.12f, 0.88f);
            double origin = loadedBeatmap?.Timing?.Offset ?? 0.0;
            double mapEnd = origin + windowDuration;
            if (loadedBeatmap?.HitObjects?.Count > 0)
            {
                double lastHit = loadedBeatmap.HitObjects.Max(hit => (double)hit.Time);
                mapEnd = Math.Max(mapEnd, lastHit + measureDuration * 0.8);
            }

            // Songsterr-like behavior: keep playhead anchored while the notation scrolls.
            double targetWindowStart = currentTime - windowDuration * playheadRatio;
            double minStart = origin - windowDuration * 0.06;
            double maxStart = Math.Max(minStart, mapEnd - windowDuration * (1.0 - playheadRatio));
            double windowStart = Math.Clamp(targetWindowStart, minStart, maxStart);

            float timelineWidth = Math.Max(260f, drawWidth * SheetMusicTuning.TimelineWidthRatio);
            float leftX = (drawWidth - timelineWidth) * 0.5f;
            float rightX = leftX + timelineWidth;
            float playheadX = leftX + timelineWidth * (float)playheadRatio;

            _ = drawHeight;
            return new SheetTimelineWindow(windowStart, windowDuration, leftX, rightX, playheadX);
        }

        private int resolveManuscriptTimelineSubdivision(in SheetTimelineWindow sheetWindow, double beatDuration)
        {
            if (loadedBeatmap?.HitObjects == null || loadedBeatmap.HitObjects.Count < 2 || beatDuration <= 1 || sheetWindow.Duration <= 1)
                return 1;

            double windowPadding = beatDuration * 0.15;
            double windowStart = sheetWindow.StartTime - windowPadding;
            double windowEnd = sheetWindow.StartTime + sheetWindow.Duration + windowPadding;

            var windowHitTimes = loadedBeatmap.HitObjects
                .Where(hit => hit.Time >= windowStart && hit.Time <= windowEnd)
                .Select(hit => (double)hit.Time)
                .OrderBy(time => time)
                .ToList();

            if (windowHitTimes.Count < 2)
                return 1;

            List<double> beatGaps = new();
            double previous = windowHitTimes[0];
            for (int i = 1; i < windowHitTimes.Count; i++)
            {
                double deltaMs = windowHitTimes[i] - previous;
                previous = windowHitTimes[i];

                // Skip stacked chord hits or effectively identical timestamps.
                if (deltaMs < 1.0)
                    continue;

                double gapBeats = deltaMs / beatDuration;
                if (gapBeats <= 0 || gapBeats > 1.05)
                    continue;

                beatGaps.Add(gapBeats);
            }

            return ResolveManuscriptSubdivisionDivisor(beatGaps);
        }

        internal static int ResolveManuscriptSubdivisionDivisor(IEnumerable<double> beatGaps)
        {
            int count8 = 0;
            int count6 = 0;
            int count4 = 0;
            int count3 = 0;
            int count2 = 0;

            foreach (double gap in beatGaps)
            {
                if (gap <= 0)
                    continue;

                if (Math.Abs(gap - 0.125) <= 0.030)
                    count8++;
                else if (Math.Abs(gap - (1.0 / 6.0)) <= 0.032)
                    count6++;
                else if (Math.Abs(gap - 0.25) <= 0.040)
                    count4++;
                else if (Math.Abs(gap - (1.0 / 3.0)) <= 0.045)
                    count3++;
                else if (Math.Abs(gap - 0.5) <= 0.060)
                    count2++;
            }

            if (count8 >= 2)
                return 8;

            if (count6 >= 2)
                return 6;

            if (count4 >= 2)
                return 4;

            if (count3 >= 2)
                return 3;

            if (count2 >= 1)
                return 2;

            return 1;
        }

        private ManuscriptBeamAnchor createManuscriptBeamAnchor(DrawableNote note)
        {
            bool stemDown = ManuscriptBackgroundEnhanced.ShouldUseDownStemForComponent(note.ComponentName);
            var voice = ManuscriptBackgroundEnhanced.GetNotationVoiceForComponent(note.ComponentName);
            int notationIndex = ManuscriptBackgroundEnhanced.GetNotationIndexForComponent(note.ComponentName);

            float noteWidth = Math.Max(10f, note.Width);
            float noteHeight = Math.Max(7f, note.Height);
            float stemHeight = Math.Clamp(noteHeight * 2.65f, 16f, 44f);

            float stemX = stemDown
                ? note.Position.X - noteWidth * 0.5f + noteWidth * 0.34f
                : note.Position.X + noteWidth * 0.5f - noteWidth * 0.34f;

            float stemRootY = note.Position.Y + (stemDown ? -noteHeight * 0.04f : noteHeight * 0.04f);
            float stemTipY = stemDown
                ? stemRootY + stemHeight
                : stemRootY - stemHeight;

            resolveTimingForHitTime(note.HitTime, out double beatDuration, out double beatOrigin);

            return new ManuscriptBeamAnchor(
                note,
                voice,
                notationIndex,
                stemDown,
                stemX,
                stemTipY,
                note.HitTime,
                beatDuration,
                beatOrigin);
        }

        private void updateManuscriptBeams(List<ManuscriptBeamAnchor> anchors)
        {
            clearManuscriptBeams();

            if (anchors.Count == 0)
                return;

            foreach (var anchor in anchors)
                anchor.Note.SetManuscriptFlagCount(0);

            addManuscriptBeamsForVoice(anchors, ManuscriptBackgroundEnhanced.ManuscriptNotationVoice.Upper);
            addManuscriptBeamsForVoice(anchors, ManuscriptBackgroundEnhanced.ManuscriptNotationVoice.Lower);
        }

        private void addManuscriptBeamsForVoice(
            List<ManuscriptBeamAnchor> anchors,
            ManuscriptBackgroundEnhanced.ManuscriptNotationVoice voice)
        {
            var voiceAnchors = anchors
                .Where(anchor => anchor.Voice == voice)
                .OrderBy(anchor => anchor.HitTime)
                .ToList();

            if (voiceAnchors.Count == 0)
                return;

            var beamedNotes = new HashSet<DrawableNote>();
            for (int i = 0; i < voiceAnchors.Count - 1; i++)
            {
                var current = voiceAnchors[i];
                var next = voiceAnchors[i + 1];

                if (!tryGetBeamLevelCount(current, next, out int levelCount))
                    continue;

                for (int level = 0; level < levelCount; level++)
                    addManuscriptBeamSegment(current, next, level);

                beamedNotes.Add(current.Note);
                beamedNotes.Add(next.Note);
            }

            for (int i = 0; i < voiceAnchors.Count; i++)
            {
                var anchor = voiceAnchors[i];
                if (beamedNotes.Contains(anchor.Note))
                {
                    anchor.Note.SetManuscriptFlagCount(0);
                    continue;
                }

                int standaloneFlags = resolveStandaloneManuscriptFlagCount(voiceAnchors, i);
                anchor.Note.SetManuscriptFlagCount(standaloneFlags);
            }
        }

        private int resolveStandaloneManuscriptFlagCount(List<ManuscriptBeamAnchor> voiceAnchors, int index)
        {
            if (index < 0 || index >= voiceAnchors.Count)
                return 0;

            var current = voiceAnchors[index];
            double nearestGap = double.MaxValue;

            for (int i = index - 1; i >= 0; i--)
            {
                if (voiceAnchors[i].NotationIndex != current.NotationIndex)
                    continue;

                nearestGap = (current.HitTime - voiceAnchors[i].HitTime) / Math.Max(1.0, current.BeatDuration);
                break;
            }

            for (int i = index + 1; i < voiceAnchors.Count; i++)
            {
                if (voiceAnchors[i].NotationIndex != current.NotationIndex)
                    continue;

                double gap = (voiceAnchors[i].HitTime - current.HitTime) / Math.Max(1.0, current.BeatDuration);
                nearestGap = Math.Min(nearestGap, gap);
                break;
            }

            // Fall back to nearest note in the same voice when this lane is sparse.
            if (double.IsPositiveInfinity(nearestGap) || nearestGap == double.MaxValue)
            {
                if (index > 0)
                    nearestGap = Math.Min(nearestGap, (current.HitTime - voiceAnchors[index - 1].HitTime) / Math.Max(1.0, current.BeatDuration));
                if (index < voiceAnchors.Count - 1)
                    nearestGap = Math.Min(nearestGap, (voiceAnchors[index + 1].HitTime - current.HitTime) / Math.Max(1.0, current.BeatDuration));
            }

            if (double.IsPositiveInfinity(nearestGap) || nearestGap == double.MaxValue || nearestGap <= 0 || nearestGap > SingleBeamThresholdBeats)
                return 0;

            int beamLevel = GetManuscriptBeamLevelCount(nearestGap);
            return Math.Clamp(beamLevel, 0, 3);
        }

        private bool tryGetBeamLevelCount(in ManuscriptBeamAnchor current, in ManuscriptBeamAnchor next, out int levelCount)
        {
            levelCount = 0;

            if (next.HitTime <= current.HitTime)
                return false;

            // In the rotated timeline manuscript, cross-lane beams become long diagonals.
            // Keep grouping lane-local to maintain drummer readability.
            if (current.NotationIndex != next.NotationIndex)
                return false;

            double beatDuration = (current.BeatDuration + next.BeatDuration) * 0.5;
            if (beatDuration <= 0)
                return false;

            int currentBeat = getBeatIndex(current.HitTime, current.BeatOrigin, current.BeatDuration);
            int nextBeat = getBeatIndex(next.HitTime, next.BeatOrigin, next.BeatDuration);
            if (currentBeat != nextBeat)
                return false;

            double gapBeats = (next.HitTime - current.HitTime) / beatDuration;
            int resolvedLevelCount = GetManuscriptBeamLevelCount(gapBeats);
            if (resolvedLevelCount <= 0)
                return false;

            levelCount = resolvedLevelCount;
            return true;
        }

        internal static int GetManuscriptBeamLevelCount(double gapBeats)
        {
            if (gapBeats < MinBeamGapBeats || gapBeats > SingleBeamThresholdBeats)
                return 0;

            // Snap to common drummer subdivisions so beam groupings stay stable:
            // 8th (1/2 beat), 8th-triplet (1/3), 16th (1/4), 16th-triplet (1/6), 32nd (1/8).
            ReadOnlySpan<double> allowedSteps = stackalloc double[]
            {
                0.5, 1.0 / 3.0, 0.25, 1.0 / 6.0, 0.125
            };

            double snapped = gapBeats;
            double smallestDelta = double.MaxValue;
            for (int i = 0; i < allowedSteps.Length; i++)
            {
                double delta = Math.Abs(gapBeats - allowedSteps[i]);
                if (delta < smallestDelta)
                {
                    smallestDelta = delta;
                    snapped = allowedSteps[i];
                }
            }

            // Reject intervals that are too far from useful rhythmic buckets.
            if (smallestDelta > 0.065)
                return 0;

            // Subdivision-aware mapping:
            // 1/2, 1/3 => single beam (8th family)
            // 1/4, 1/6 => double beam (16th family)
            // 1/8      => triple beam (32nd family)
            if (Math.Abs(snapped - 0.125) < 0.0001)
                return 3;

            if (Math.Abs(snapped - 0.25) < 0.0001 || Math.Abs(snapped - (1.0 / 6.0)) < 0.0001)
                return 2;

            return 1;
        }

        private void addManuscriptBeamSegment(in ManuscriptBeamAnchor start, in ManuscriptBeamAnchor end, int beamLevel)
        {
            float direction = start.StemDown ? 1f : -1f;
            float densityScale = Math.Clamp(DrawHeight / 1080f, 0.78f, 1.18f);
            float offset = direction * beamLevel * ManuscriptBeamSpacing * densityScale;

            Vector2 beamStart = new Vector2(start.StemX, start.StemTipY + offset);
            Vector2 beamEnd = new Vector2(end.StemX, end.StemTipY + offset);
            Vector2 delta = beamEnd - beamStart;
            float length = delta.Length;
            if (length < 6f)
                return;

            float thickness = beamLevel == 0
                ? ManuscriptPrimaryBeamThickness
                : ManuscriptSecondaryBeamThickness;
            thickness *= densityScale;

            manuscriptBeamLayer.Add(new Box
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.CentreLeft,
                Position = beamStart,
                Width = length,
                Height = thickness,
                Rotation = MathF.Atan2(delta.Y, delta.X) * 180f / MathF.PI,
                Colour = manuscriptBeamColor,
                Alpha = ManuscriptBeamAlpha
            });
        }

        private void clearManuscriptBeams()
        {
            manuscriptBeamLayer.Clear(false);
        }

        private int getBeatIndex(double time, double beatOrigin, double beatDuration)
        {
            if (beatDuration <= 0.0)
                return 0;

            return (int)Math.Floor(((time - beatOrigin) / beatDuration) + 0.0001);
        }

        private void resolveTimingForHitTime(double hitTime, out double beatDuration, out double beatOrigin)
        {
            beatDuration = cachedBpm > 0 ? 60000.0 / cachedBpm : 500;
            beatOrigin = loadedBeatmap?.Timing?.Offset ?? 0;

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
                beatDuration = 60000.0 / activePoint.Bpm;

            beatOrigin = activePoint.Time;
        }

        private void updateNotePosition(
            DrawableNote note,
            float timeUntilHit,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            in SheetTimelineWindow sheetWindow)
        {
            // Use the dynamic ApproachDuration here
            float progress = 1 - (timeUntilHit / (float)ApproachDuration);

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                updateNotePosition3D(note, progress, drawWidth, drawHeight, hitLineY);
            }
            else if (currentLaneViewMode == LaneViewMode.Manuscript)
            {
                updateNotePositionManuscript(note, timeUntilHit, drawWidth, drawHeight, sheetWindow);
            }
            else
            {
                updateNotePosition2D(note, progress, drawWidth, drawHeight, hitLineY, travelDistance);
            }
        }

        private void updateNotePositionManuscript(
            DrawableNote note,
            float timeUntilHit,
            float drawWidth,
            float drawHeight,
            in SheetTimelineWindow sheetWindow)
        {
            float timelineWidth = Math.Max(120f, sheetWindow.RightX - sheetWindow.LeftX);
            double normalized = sheetWindow.Duration <= 0
                ? 0.0
                : (note.HitTime - sheetWindow.StartTime) / sheetWindow.Duration;

            float x = sheetWindow.LeftX + (float)(normalized * timelineWidth);
            float y = ManuscriptBackgroundEnhanced.GetStaffYForComponent(note.ComponentName, drawWidth, drawHeight);
            float staffSpacing = ManuscriptBackgroundEnhanced.GetStaffSpacingForDrawArea(drawWidth, drawHeight);
            float noteScaleSetting = (float)Math.Clamp(NoteWidthScale.Value, 0.65, 1.75);

            float noteWidth = Math.Clamp(
                timelineWidth * SheetMusicTuning.NoteWidthRatio * noteScaleSetting,
                SheetMusicTuning.MinNoteWidth,
                SheetMusicTuning.MaxNoteWidth);
            float noteHeight = Math.Clamp(
                staffSpacing * SheetMusicTuning.NoteHeightRatio,
                SheetMusicTuning.MinNoteHeight,
                SheetMusicTuning.MaxNoteHeight);
            note.Width = noteWidth;
            note.Height = noteHeight;

            // Force sheet-music glyph proportions so mode switches do not leave 3D bar widths behind.
            note.SetViewMode(LaneViewMode.Manuscript);
            note.RelativePositionAxes = Axes.None;
            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;

            setNoteDepth(note, 0);

            // Unjudged notes past the hit line: hide as safety fallback
            // Judged notes: ApplyResult animation handles the fade-out
            if (!note.IsJudged)
            {
                bool inTimeline = x >= sheetWindow.LeftX - note.Width && x <= sheetWindow.RightX + note.Width;
                bool inRecentPast = timeUntilHit >= -(float)Math.Max(420, pastVisibilityWindow);
                if (!inTimeline || !inRecentPast)
                    note.Alpha = 0;
                else
                    note.Alpha = 1;
            }

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
                float laneWidthPx = drawWidth / activeLaneCount;

                float baseNoteWidth = laneWidthPx * 0.45f;
                float userScale = (float)NoteWidthScale.Value;
                note.Width = Math.Clamp(baseNoteWidth * userScale, 40f, 160f);

                int visualLaneIndex = note.Lane;
                if (kickUsesGlobalLine && note.Lane > laneLayout.KickLane)
                    visualLaneIndex--;

                // CRITICAL: use noteLayer.DrawWidth, NOT the passed-in drawWidth (which is PlaybackPlayfield.DrawWidth * ratio).
                // If these differ, notes will be mispositioned!
                float actualParentWidth = noteLayer.DrawWidth;
                float actualLaneWidthPx = actualParentWidth / activeLaneCount;
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
            float clampedProgress = Math.Clamp(progress, ThreeDimensionalTuning.ProgressMin, ThreeDimensionalTuning.ProgressMax);
            float normalizedProgress = (clampedProgress - ThreeDimensionalTuning.ProgressMin)
                                       / (ThreeDimensionalTuning.ProgressMax - ThreeDimensionalTuning.ProgressMin);
            normalizedProgress = Math.Clamp(normalizedProgress, 0f, 1f);
            // Stronger easing exaggerates stage depth so 3D does not collapse into a flat 2D look.
            float perspectiveProgress = 1f - MathF.Pow(1f - normalizedProgress, 1.90f);

            float vanishingPointY = drawHeight * ThreeDimensionalTuning.VanishingPointYRatio;
            float highwayWidthAtBottom = drawWidth * ThreeDimensionalTuning.HighwayBottomWidthRatio;
            float highwayWidthAtTop = drawWidth * ThreeDimensionalTuning.HighwayTopWidthRatio;

            int activeLaneCount = cachedActiveLaneCount;
            float widthProgress = MathF.Pow(perspectiveProgress, 1.28f);
            float currentHighwayWidth = lerp(highwayWidthAtTop, highwayWidthAtBottom, widthProgress);
            float currentLaneWidth = currentHighwayWidth / activeLaneCount;
            float y = lerp(vanishingPointY, hitLineY, MathF.Pow(perspectiveProgress, 1.18f));
            float noteScaleSetting = (float)Math.Clamp(NoteWidthScale.Value, 0.65, 1.75);
            float laneNoteWidthFactor = lerp(
                ThreeDimensionalTuning.LaneNoteWidthAtTop,
                ThreeDimensionalTuning.LaneNoteWidthAtBottom,
                perspectiveProgress);
            float noteWidth = Math.Clamp(
                currentLaneWidth * laneNoteWidthFactor * noteScaleSetting,
                ThreeDimensionalTuning.MinNoteWidth,
                ThreeDimensionalTuning.MaxNoteWidth);
            float noteHeight = Math.Clamp(
                noteWidth * lerp(0.34f, 0.23f, perspectiveProgress),
                ThreeDimensionalTuning.MinNoteHeight,
                ThreeDimensionalTuning.MaxNoteHeight);

            bool isGlobalKickVisual = kickUsesGlobalLine && note.IsKick;
            float finalNoteWidth = isGlobalKickVisual
                ? Math.Clamp(
                    currentHighwayWidth * lerp(ThreeDimensionalTuning.KickWidthAtTop, ThreeDimensionalTuning.KickWidthAtBottom, perspectiveProgress) * noteScaleSetting,
                    28f,
                    152f)
                : noteWidth;
            float finalNoteHeight = isGlobalKickVisual
                ? Math.Clamp(noteHeight * 0.88f, ThreeDimensionalTuning.MinNoteHeight, 24f)
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
            note.Rotation = -lateral * (1f - perspectiveProgress) * 12.0f;

            setNoteDepth(note, perspectiveProgress);

            // Unjudged notes past the hit line: hide as safety fallback
            // Judged notes: ApplyResult animation handles the fade-out
            if (!note.IsJudged)
            {
                if (y > hitLineY + note.Height / 2 + 2)
                    note.Alpha = 0;
                else
                    note.Alpha = lerp(0.46f, 1f, perspectiveProgress);
            }
        }
        private static float lerp(float start, float end, float amount) => start + (end - start) * amount;

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

            laneBackgroundContainer.Clear();

            // Calculate active lanes (excluding kick lane if global)
            int activeLaneCount = kickUsesGlobalLine ? Math.Max(1, laneCount - 1) : laneCount;

            // Cache for use in Update() and updateNotePosition2D() so notes
            // are always positioned consistently with the drawn backgrounds.
            cachedActiveLaneCount = activeLaneCount;

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                threeDHighwayBackground = new ThreeDHighwayBackground(laneLayout, kickUsesGlobalLine);
                manuscriptBackground = null;
                laneBackgroundContainer.Add(threeDHighwayBackground);

                // if (kickGuideLine2D != null) kickGuideLine2D.Alpha = 0;
                if (timingStrikeZone != null) timingStrikeZone.SetViewMode(LaneViewMode.ThreeDimensional);
                if (timingGridOverlay != null) timingGridOverlay.SetViewMode(LaneViewMode.ThreeDimensional);
            }
            else if (currentLaneViewMode == LaneViewMode.Manuscript)
            {
                threeDHighwayBackground = null;
                manuscriptBackground = new ManuscriptBackgroundEnhanced();
                manuscriptBackground.SetFocusedComponent(manuscriptFocusComponent);
                laneBackgroundContainer.Add(manuscriptBackground);

                // if (kickGuideLine2D != null) kickGuideLine2D.Alpha = 0;
                if (timingStrikeZone != null) timingStrikeZone.SetViewMode(LaneViewMode.Manuscript);
                if (timingGridOverlay != null) timingGridOverlay.SetViewMode(LaneViewMode.Manuscript);
            }
            else
            {
                threeDHighwayBackground = null;
                manuscriptBackground = null;
                // Add 2D background - fully opaque to prevent any bleed-through
                laneBackgroundContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(20, 20, 30, 255)
                });

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
                            Colour = new Color4(255, 255, 255, 8)
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
                            Colour = new Color4(255, 255, 255, 70)
                        });
                    }

                    // Lane label at bottom
                    string label = getLaneLabelForIndex(i, activeLaneCount);
                    laneBackgroundContainer.Add(new SpriteText
                    {
                        Text = label,
                        Font = FrameworkFont.Regular.With(size: 11),
                        Colour = new Color4(255, 255, 255, 120),
                        RelativePositionAxes = Axes.Both,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.BottomCentre,
                        X = (i + 0.5f) * laneWidth,
                        Y = 0.98f
                    });
                }
                float effectiveWidth = DrawWidth * PlayfieldWidthRatio;
                if (timingStrikeZone != null)
                    timingStrikeZone.UpdateGeometry(effectiveWidth, DrawHeight, DrawHeight * HitLineYRatio, 0f, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, kickUsesGlobalLine, currentLaneViewMode);
            }

            clearManuscriptBeams();
            applyKickModeToNotes();
        }
        /// Get a human-readable label for a visual lane index.
        /// Always uses the desktop's canonical lane ordering since lanes are re-resolved
        /// by DrumLaneHeuristics.ApplyToBeatmap (ignoring the .bsm pipeline layout).
        /// </summary>
        private string getLaneLabelForIndex(int laneIndex, int totalLanes)
        {
            if (kickUsesGlobalLine)
            {
                // When kick uses global line, visual lanes skip the kick position.
                // Map visual lane index to the semantic lane labels.
                return laneIndex switch
                {
                    0 => "Crash",
                    1 => "HiHat",
                    2 => "Snare",
                    3 => "Tom",
                    4 => "Ride",
                    5 => "China",
                    6 => "Splash",
                    7 => "Perc",
                    _ => $"Lane {laneIndex + 1}"
                };
            }

            return laneIndex switch
            {
                0 => "Crash",
                1 => "HiHat",
                2 => "Snare",
                3 => "Kick",
                4 => "Tom",
                5 => "Ride",
                6 => "China",
                7 => "Splash",
                8 => "Perc",
                _ => $"Lane {laneIndex + 1}"
            };
        }

        public void JumpToTime(double time)
        {
            // Reset ALL notes to ensure clean state after seeking.
            // Previously only notes after the target time were reset,
            // causing notes before the target to stay in their judged/expired
            // state, producing different visuals when seeking back and forth.
            foreach (var note in notes)
            {
                note.Reset();
            }

            noteLayer.Clear(false);
            hitExplosionLayer?.Clear(false);

            // Advance firstActiveNoteIndex past notes that are already out of view
            firstActiveNoteIndex = 0;
            double visibilityStart = time - pastVisibilityWindow;

            while (firstActiveNoteIndex < notes.Count && notes[firstActiveNoteIndex].HitTime < visibilityStart)
            {
                firstActiveNoteIndex++;
            }
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
