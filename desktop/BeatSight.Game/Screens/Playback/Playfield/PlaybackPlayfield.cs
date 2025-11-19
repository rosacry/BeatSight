using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    public partial class PlaybackPlayfield : CompositeDrawable
    {
        private LaneLayout laneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
        private int laneCount => Math.Max(1, laneLayout.LaneCount);

        // Changed from const to property to allow dynamic adjustment
        public double ApproachDuration { get; private set; } = 5000;

        private const double perfectWindow = 35;
        private const double greatWindow = 80;
        private const double goodWindow = 130;
        private const double mehWindow = 180;
        private const double missWindow = 220;
        private const float PlayfieldWidthRatio = 1f; // Constrain playfield width

        private readonly Func<double> currentTimeProvider;
        private readonly List<DrawableNote> notes = new();
        private readonly List<DrawableNote> kickNoteBuffer = new();
        private int firstActiveNoteIndex;
        private double futureVisibilityWindow => ApproachDuration + 900;
        private const double pastVisibilityWindow = missWindow + 600;
        private bool isPreviewMode; // If true, notes won't be auto-judged

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        private Bindable<GameplayMode> gameplayMode = null!;
        private Bindable<bool> showApproachCircles = null!;
        private Bindable<bool> showParticleEffects = null!;
        private Bindable<bool> showGlowEffects = null!;
        private Bindable<bool> showHitBurstAnimations = null!;

        private Container noteLayer = null!;
        private Container laneBackgroundContainer = null!;
        private Container laneGuideOverlay = null!;
        private TimingGridOverlay? timingGridOverlay;
        private TimingStrikeZone? timingStrikeZone;
        // private KickGuideLine? kickGuideLine2D; // Removed unused field
        private ThreeDHighwayBackground? threeDHighwayBackground;
        private Beatmap? loadedBeatmap;

        private Bindable<LaneViewMode> laneViewMode = null!;
        private LaneViewMode currentLaneViewMode;
        private bool kickUsesGlobalLine = true;

        public readonly Bindable<double> ZoomLevel = new Bindable<double>(1.0);
        public readonly Bindable<bool> AutoZoom = new Bindable<bool>(true);
        public readonly Bindable<double> NoteWidthScale = new Bindable<double>(1.0);

        public event Action<HitResult, double, Color4>? ResultApplied;

        private double cachedBpm = 120;
        private double cachedBeatsPerMeasure = 4;
        private int lastTimingPointIndex = -1;

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
            showApproachCircles = config.GetBindable<bool>(BeatSightSetting.ShowApproachCircles);
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
                noteLayer = new Container
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
            updateLayout();
        }

        public void SetLaneLayout(LaneLayout layout)
        {
            laneLayout = layout;
            updateLayout();
        }

        public void SetKickLineMode(bool enabled)
        {
            kickUsesGlobalLine = enabled;
            updateLayout();
        }

        public void LoadBeatmap(Beatmap beatmap)
        {
            loadedBeatmap = beatmap;
            notes.Clear();
            noteLayer?.Clear();
            firstActiveNoteIndex = 0;

            if (beatmap == null)
                return;

            foreach (var hitObject in beatmap.HitObjects)
            {
                int lane = resolveLane(hitObject);
                var note = new DrawableNote(hitObject, lane, showApproachCircles, showGlowEffects, showParticleEffects);
                notes.Add(note);
            }

            // Sort by time to ensure efficient processing
            notes.Sort((a, b) => a.HitTime.CompareTo(b.HitTime));

            timingGridOverlay?.Configure(beatmap, laneLayout, kickUsesGlobalLine);
            updateLayout();
        }

        public void SetPreviewMode(bool preview)
        {
            isPreviewMode = preview;
        }

        protected override void Update()
        {
            base.Update();

            double currentTime = currentTimeProvider();

            // Calculate approach duration based on zoom settings
            updateApproachDuration(currentTime);

            updateNotes(currentTime);

            int activeLaneCount = kickUsesGlobalLine ? Math.Max(1, laneCount - 1) : laneCount;

            // Calculate effective width (containers are already constrained to this width)
            float effectiveWidth = DrawWidth * PlayfieldWidthRatio;

            // Ensure strike zone geometry is updated every frame to handle resizing
            float hitLineY = DrawHeight * 0.95f;
            float spawnTop = 0f; // Extend grid to top
            float travelDistance = hitLineY - spawnTop;

            if (timingStrikeZone != null)
            {
                timingStrikeZone.UpdateGeometry(effectiveWidth, DrawHeight, hitLineY, spawnTop, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, kickUsesGlobalLine, currentLaneViewMode);
            }

            timingGridOverlay?.UpdateState(currentTime, effectiveWidth, DrawHeight, spawnTop, hitLineY, travelDistance, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, currentLaneViewMode, kickUsesGlobalLine);

            threeDHighwayBackground?.UpdateScroll(currentTime);
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

            // Default to showing 10 beats (2.5 measures in 4/4) at 1.0 zoom to match original ~5000ms feel
            double targetVisibleBeats = 10 * cachedBeatsPerMeasure / 4.0;

            // Apply ZoomLevel: Zooming In (Value > 1) means seeing LESS time (shorter duration)
            // Zooming Out (Value < 1) means seeing MORE time (longer duration)
            // So we divide by ZoomLevel
            double zoomFactor = Math.Max(0.1, ZoomLevel.Value);

            ApproachDuration = (targetVisibleBeats * beatDuration) / zoomFactor;
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
                return;

            float drawHeight = DrawHeight;
            float effectiveWidth = DrawWidth * PlayfieldWidthRatio;

            float hitLineY = drawHeight * 0.95f; // Moved down from 0.93f
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

            // Prune passed notes
            while (firstActiveNoteIndex < notes.Count && notes[firstActiveNoteIndex].HitTime < currentTime - pastVisibilityWindow)
            {
                var note = notes[firstActiveNoteIndex];
                if (!note.IsJudged && !isPreviewMode)
                    applyResult(note, HitResult.Miss, currentTime - note.HitTime);

                if (note.Parent != null)
                    noteLayer.Remove(note, false);

                firstActiveNoteIndex++;
            }

            // Update visible notes
            for (int i = firstActiveNoteIndex; i < notes.Count; i++)
            {
                var note = notes[i];
                double timeUntilHit = note.HitTime - currentTime;

                if (timeUntilHit > futureVisibilityWindow)
                    break;

                if (note.Parent == null)
                {
                    if (note.IsDisposedPublic)
                        continue;

                    noteLayer.Add(note);
                    note.RestartAnimation();
                    note.ApplyKickMode(kickUsesGlobalLine, laneLayout.KickLane);
                }

                // Reset height to calculated height
                note.Height = noteHeight;

                updateNotePosition(note, (float)timeUntilHit, effectiveWidth, drawHeight, hitLineY, travelDistance);
            }
        }

        private void updateNotePosition(DrawableNote note, float timeUntilHit, float drawWidth, float drawHeight, float hitLineY, float travelDistance)
        {
            // Use the dynamic ApproachDuration here
            float progress = 1 - (timeUntilHit / (float)ApproachDuration);
            note.SetApproachProgress(progress);

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                updateNotePosition3D(note, progress, drawWidth, drawHeight, hitLineY);
            }
            else if (currentLaneViewMode == LaneViewMode.Manuscript)
            {
                updateNotePositionManuscript(note, progress, drawWidth, drawHeight, hitLineY, travelDistance);
            }
            else
            {
                updateNotePosition2D(note, progress, drawWidth, drawHeight, hitLineY, travelDistance);
            }
        }

        private void updateNotePositionManuscript(DrawableNote note, float progress, float drawWidth, float drawHeight, float hitLineY, float travelDistance)
        {
            float y = hitLineY - travelDistance * (1 - progress);

            // Determine X position based on component (Staff position)
            float staffCenter = drawWidth / 2;
            float lineSpacing = 40; // Must match ManuscriptBackground
            float staffPos = getStaffPosition(note.ComponentName);

            float x = staffCenter + staffPos * lineSpacing;

            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;

            setNoteDepth(note, 0);

            // Disappear logic: after passing hit line + half height + padding
            if (y > hitLineY + note.Height / 2 + 2)
                note.Alpha = 0;
            else
                note.Alpha = 1;
        }

        private float getStaffPosition(string component)
        {
            // Map components to staff positions (0 = center line)
            // Lines are at -2, -1, 0, 1, 2
            // Spaces are at -1.5, -0.5, 0.5, 1.5

            component = component.ToLowerInvariant();
            if (component.Contains("kick")) return -2.5f; // Below bottom line
            if (component.Contains("snare")) return 0f; // Middle line
            if (component.Contains("hihat")) return 2.5f; // Above top line
            if (component.Contains("tom_high")) return 1.5f; // Top space
            if (component.Contains("tom_mid")) return 1f; // Top line
            if (component.Contains("tom_low")) return 0.5f; // Upper middle space
            if (component.Contains("ride")) return 3f; // Way above
            if (component.Contains("crash")) return 3.5f; // Way way above
            if (component.Contains("china")) return 3.5f;
            if (component.Contains("splash")) return 3f;
            if (component.Contains("cowbell")) return 2f;

            return 0f;
        }

        private void updateNotePosition2D(DrawableNote note, float progress, float drawWidth, float drawHeight, float hitLineY, float travelDistance)
        {
            float y = hitLineY - travelDistance * (1 - progress);

            if (kickUsesGlobalLine && note.IsKick)
            {
                note.Width = drawWidth;
                note.Position = new Vector2(drawWidth / 2, y);
                note.Scale = Vector2.One;
                note.Rotation = 0;
            }
            else
            {
                // Determine X position based on lane, adjusting for removed kick column
                int activeLaneCount = kickUsesGlobalLine ? Math.Max(1, laneCount - 1) : laneCount;
                float laneWidth = drawWidth / activeLaneCount;

                // Scale note width to lane width (80% fill)
                // Apply NoteWidthScale here, but cap at 100% lane width (1.25 * 0.8 = 1.0)
                // User requested 1.0x to be equivalent to old 0.75x
                float effectiveScale = (float)NoteWidthScale.Value * 0.75f;
                float scale = Math.Min(1.25f, effectiveScale);
                note.Width = (float)(laneWidth * 0.8f * scale);

                int visualLaneIndex = note.Lane;
                if (kickUsesGlobalLine && note.Lane > laneLayout.KickLane)
                {
                    visualLaneIndex--;
                }

                float x = laneWidth * visualLaneIndex + laneWidth / 2;

                note.Position = new Vector2(x, y);
                note.Scale = Vector2.One;
                note.Rotation = 0;
            }

            // Update depth for Z-ordering
            setNoteDepth(note, 0);

            // Disappear logic
            if (y > hitLineY + note.Height / 2 + 2)
                note.Alpha = 0;
            else
                note.Alpha = 1;
        }

        private void updateNotePosition3D(DrawableNote note, float progress, float drawWidth, float drawHeight, float hitLineY)
        {
            // Perspective projection logic
            float t = Math.Clamp(progress, -0.2f, 1.2f);

            // Vanishing point at top center
            float vanishingPointX = drawWidth / 2;
            float vanishingPointY = drawHeight * 0.15f;

            // Lane width at bottom (hit line)
            float highwayWidthAtBottom = drawWidth * 0.85f;

            // Adjust for removed kick column
            int activeLaneCount = kickUsesGlobalLine ? Math.Max(1, laneCount - 1) : laneCount;
            float laneWidthAtBottom = highwayWidthAtBottom / activeLaneCount;

            // Lane width at top (vanishing point area)
            float highwayWidthAtTop = highwayWidthAtBottom * 0.35f;
            float laneWidthAtTop = highwayWidthAtTop / activeLaneCount;

            // Interpolate width based on progress (linear in screen space for now, could be perspective correct)
            float currentHighwayWidth = lerp(highwayWidthAtTop, highwayWidthAtBottom, t);
            float currentLaneWidth = currentHighwayWidth / activeLaneCount;

            // Calculate Y
            float y = lerp(vanishingPointY, hitLineY, t);

            // Scale note based on perspective
            float scale = lerp(0.35f, 1.0f, t);

            // Apply some stretch effect for speed sensation
            float stretch = 1.0f + Math.Abs(t - 0.5f) * 0.2f;

            if (kickUsesGlobalLine && note.IsKick)
            {
                note.Width = currentHighwayWidth;
                note.Position = new Vector2(drawWidth / 2, y);
                note.Scale = new Vector2(1f, stretch);
                note.Rotation = 0;
            }
            else
            {
                note.Width = 60;
                // Calculate X
                int visualLaneIndex = note.Lane;
                if (kickUsesGlobalLine && note.Lane > laneLayout.KickLane)
                {
                    visualLaneIndex--;
                }

                // Center the highway
                float highwayLeft = (drawWidth - currentHighwayWidth) / 2;
                float x = highwayLeft + currentLaneWidth * visualLaneIndex + currentLaneWidth / 2;

                note.Position = new Vector2(x, y);
                note.Scale = new Vector2(scale, scale * stretch);
                note.Rotation = 0;
            }

            setNoteDepth(note, t);

            // Disappear logic
            if (y > hitLineY + note.Height / 2 + 2)
                note.Alpha = 0;
            else
                note.Alpha = 1;
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

            float tolerance = currentLaneViewMode == LaneViewMode.ThreeDimensional ? 12f : 5f;

            if (note.ShouldUpdateDepth(depth, tolerance))
            {
                try
                {
                    noteLayer.ChangeChildDepth(note, depth);
                }
                catch (Exception)
                {
                    // Ignore depth change errors
                }
            }
        }

        private void applyResult(DrawableNote note, HitResult result, double offset)
        {
            if (note.IsJudged)
                return;

            note.ApplyResult(result);
            ResultApplied?.Invoke(result, offset, note.AccentColour);
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

            if (targetNote != null && bestDiff <= missWindow)
            {
                double offset = currentTime - targetNote.HitTime;
                var result = getHitResult(Math.Abs(offset));

                if (result != HitResult.None)
                {
                    applyResult(targetNote, result, offset);
                    return result;
                }
            }

            return HitResult.None;
        }

        private HitResult getHitResult(double absOffset)
        {
            if (absOffset <= perfectWindow) return HitResult.Perfect;
            if (absOffset <= greatWindow) return HitResult.Great;
            if (absOffset <= goodWindow) return HitResult.Good;
            if (absOffset <= mehWindow) return HitResult.Meh;
            if (absOffset <= missWindow) return HitResult.Miss;
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

            laneBackgroundContainer.Clear();

            // Calculate active lanes (excluding kick lane if global)
            int activeLaneCount = kickUsesGlobalLine ? Math.Max(1, laneCount - 1) : laneCount;

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                threeDHighwayBackground = new ThreeDHighwayBackground(laneLayout, kickUsesGlobalLine);
                laneBackgroundContainer.Add(threeDHighwayBackground);

                // if (kickGuideLine2D != null) kickGuideLine2D.Alpha = 0;
                if (timingStrikeZone != null) timingStrikeZone.SetViewMode(LaneViewMode.ThreeDimensional);
                if (timingGridOverlay != null) timingGridOverlay.SetViewMode(LaneViewMode.ThreeDimensional);
            }
            else if (currentLaneViewMode == LaneViewMode.Manuscript)
            {
                threeDHighwayBackground = null;
                laneBackgroundContainer.Add(new ManuscriptBackground());

                // if (kickGuideLine2D != null) kickGuideLine2D.Alpha = 0;
                if (timingStrikeZone != null) timingStrikeZone.SetViewMode(LaneViewMode.Manuscript);
                if (timingGridOverlay != null) timingGridOverlay.SetViewMode(LaneViewMode.Manuscript);
            }
            else
            {
                threeDHighwayBackground = null;
                // Add 2D background
                laneBackgroundContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(20, 20, 30, 200)
                });

                // Add lane separators
                float effectiveWidth = DrawWidth * PlayfieldWidthRatio;
                float laneWidth = 1.0f / activeLaneCount; // Relative to container width (which is effectiveWidth)
                for (int i = 1; i < activeLaneCount; i++)
                {
                    laneBackgroundContainer.Add(new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 2,
                        RelativePositionAxes = Axes.X,
                        X = i * laneWidth,
                        Colour = new Color4(255, 255, 255, 30)
                    });
                }
                if (timingStrikeZone != null)
                    timingStrikeZone.UpdateGeometry(effectiveWidth, DrawHeight, DrawHeight * 0.95f, 0f, effectiveWidth / activeLaneCount, activeLaneCount, activeLaneCount, laneLayout.KickLane, kickUsesGlobalLine, currentLaneViewMode);
            }

            applyKickModeToNotes();
        }

        public void JumpToTime(double time)
        {
            firstActiveNoteIndex = 0;

            double visibilityStart = time - pastVisibilityWindow;

            while (firstActiveNoteIndex < notes.Count && notes[firstActiveNoteIndex].HitTime < visibilityStart)
            {
                firstActiveNoteIndex++;
            }

            foreach (var note in notes)
            {
                if (note.HitTime > time)
                {
                    note.Reset();
                }
            }

            noteLayer.Clear(false);
        }

        public void StartSession(bool restart)
        {
            if (restart)
            {
                foreach (var note in notes)
                    note.Reset();

                firstActiveNoteIndex = 0;
                noteLayer.Clear(false);
            }
        }
    }
}
