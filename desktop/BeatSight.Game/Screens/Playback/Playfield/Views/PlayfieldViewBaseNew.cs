using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// Enhanced base class for playfield view implementations.
    /// Provides comprehensive shared functionality including timing calculations,
    /// position math, note styling, and common utilities.
    /// 
    /// Architecture Notes:
    /// - All views share the same coordinate system conventions
    /// - Y-axis: 0 = top, increasing downward (spawn → hit line)
    /// - X-axis: 0 = left, increasing rightward (lane positioning)
    /// - Progress: 0 = just spawned, 1 = at hit line
    /// </summary>
    public abstract class PlayfieldViewBaseEnhanced : IPlayfieldView
    {
        #region Abstract Properties

        /// <summary>The view mode this renderer handles.</summary>
        public abstract Configuration.LaneViewMode ViewMode { get; }

        /// <summary>Get the hit line Y position as a proportion of draw height (0-1).</summary>
        public abstract float HitLineYRatio { get; }

        /// <summary>Get the spawn position Y as a proportion of draw height (0-1).</summary>
        public abstract float SpawnYRatio { get; }

        #endregion

        #region Protected State

        /// <summary>Shared context containing timing and settings bindings.</summary>
        protected ViewContext? Context { get; private set; }

        /// <summary>Current lane layout configuration.</summary>
        protected LaneLayout? Layout { get; private set; }

        /// <summary>Whether kick notes use a global line across all lanes.</summary>
        protected bool UseGlobalKickLine { get; private set; } = true;

        /// <summary>Currently loaded beatmap.</summary>
        protected Beatmap? LoadedBeatmap { get; private set; }

        /// <summary>Current beats per minute for timing calculations.</summary>
        protected double CurrentBpm { get; set; } = 120;

        /// <summary>Current time signature beats per measure.</summary>
        protected int BeatsPerMeasure { get; set; } = 4;

        /// <summary>Current time signature beat unit (4 = quarter note, 8 = eighth note).</summary>
        protected int BeatUnit { get; set; } = 4;

        #endregion

        #region Computed Properties

        /// <summary>Total number of lanes in the layout.</summary>
        protected int LaneCount => Layout?.LaneCount ?? 7;

        /// <summary>Index of the kick lane.</summary>
        protected int KickLane => Layout?.KickLane ?? 3;

        /// <summary>Number of lanes visible (excludes kick if using global line).</summary>
        protected int VisibleLaneCount => UseGlobalKickLine ? Math.Max(1, LaneCount - 1) : LaneCount;

        /// <summary>Current approach duration in milliseconds.</summary>
        protected double ApproachDuration => Context?.ApproachDuration ?? 5000;

        /// <summary>Current zoom level (1.0 = default).</summary>
        protected double ZoomLevel => Context?.ZoomLevel.Value ?? 1.0;

        /// <summary>Current note width scale preference (1.0 = default).</summary>
        protected double NoteWidthScale => Context?.NoteWidthScale.Value ?? 1.0;

        /// <summary>Whether to show glow effects.</summary>
        protected bool ShowGlowEffects => Context?.ShowGlowEffects.Value ?? true;

        /// <summary>Whether to show particle effects.</summary>
        protected bool ShowParticleEffects => Context?.ShowParticleEffects.Value ?? true;

        #endregion

        #region Initialization

        /// <summary>
        /// Initialize the view with necessary dependencies.
        /// </summary>
        public virtual void Initialize(ViewContext context)
        {
            Context = context ?? throw new ArgumentNullException(nameof(context));
        }

        /// <summary>
        /// Configure the view for a specific lane layout.
        /// </summary>
        public virtual void SetLaneLayout(LaneLayout layout)
        {
            Layout = layout ?? throw new ArgumentNullException(nameof(layout));
        }

        /// <summary>
        /// Configure kick line display mode.
        /// </summary>
        public virtual void SetKickLineMode(bool useGlobalLine)
        {
            UseGlobalKickLine = useGlobalLine;
        }

        /// <summary>
        /// Load a beatmap into this view.
        /// </summary>
        public virtual void LoadBeatmap(Beatmap beatmap)
        {
            LoadedBeatmap = beatmap;
        }

        #endregion

        #region Abstract Methods

        /// <summary>Create the background drawable for this view mode.</summary>
        public abstract Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick);

        /// <summary>Create the strike zone (hit line area) for this view mode.</summary>
        public abstract Drawable CreateStrikeZone();

        /// <summary>Update a note's visual position and appearance for this view.</summary>
        public abstract void UpdateNotePosition(
            DrawableNote note,
            float progress,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            NotePositionContext positionContext);

        #endregion

        #region Virtual Methods (Override in subclasses for customization)

        /// <summary>
        /// Apply view-specific styling to a note.
        /// Called when a note is first added to the playfield or when view mode changes.
        /// </summary>
        public virtual void ApplyNoteStyle(DrawableNote note)
        {
            note.SetViewMode(ViewMode);
        }

        /// <summary>
        /// Called each frame to update any background animations.
        /// </summary>
        public virtual void UpdateBackground(double currentTime)
        {
            // Default: no-op. Subclasses can override for animated backgrounds.
        }

        #endregion

        #region Shared Position Calculation Methods

        /// <summary>
        /// Calculate the visual lane index, accounting for global kick line mode.
        /// When global kick is enabled, lanes after the kick lane shift left by one.
        /// </summary>
        protected int GetVisualLaneIndex(int lane, NotePositionContext ctx)
        {
            if (ctx.UseGlobalKickLine && lane > ctx.KickLaneIndex)
                return lane - 1;
            return lane;
        }

        /// <summary>
        /// Calculate note width based on lane width and user scale preference.
        /// Uses design system constants for consistent sizing.
        /// </summary>
        protected float CalculateNoteWidth(float laneWidth, float userScale)
        {
            // Target ~45% of lane width for balanced look across resolutions
            float baseNoteWidth = laneWidth * 0.45f;
            return Math.Clamp(baseNoteWidth * userScale, 40f, 160f);
        }

        /// <summary>
        /// Calculate the X position for a note in a standard lane layout.
        /// </summary>
        protected float CalculateLaneX(int visualLaneIndex, float drawWidth, int visibleLaneCount)
        {
            float laneWidth = drawWidth / visibleLaneCount;
            return laneWidth * visualLaneIndex + laneWidth / 2;
        }

        /// <summary>
        /// Calculate Y position based on progress and view geometry.
        /// </summary>
        protected float CalculateY(float progress, float hitLineY, float travelDistance)
        {
            return hitLineY - travelDistance * (1 - progress);
        }

        /// <summary>
        /// Determine if a note should be visible based on its Y position.
        /// </summary>
        protected bool IsNoteVisible(float y, float hitLineY, float noteHeight)
        {
            // Note is visible if it hasn't fully passed the hit line
            return y <= hitLineY + noteHeight / 2 + 2;
        }

        /// <summary>
        /// Calculate alpha for a note based on position and velocity.
        /// Handles fadeout as notes pass the hit line.
        /// </summary>
        protected float CalculateNoteAlpha(float y, float hitLineY, float noteHeight, double velocity = 1.0)
        {
            if (!IsNoteVisible(y, hitLineY, noteHeight))
                return 0f;

            return DesignSystem.GetVelocityAlpha(velocity);
        }

        #endregion

        #region 3D Perspective Calculations

        /// <summary>
        /// Apply perspective easing for 3D view.
        /// Creates more realistic depth perception by making objects
        /// appear to accelerate as they approach.
        /// </summary>
        protected float ApplyPerspectiveEasing(float progress)
        {
            return DesignSystem.PerspectiveLerp(progress);
        }

        /// <summary>
        /// Calculate 3D perspective scale based on progress.
        /// </summary>
        protected float Calculate3DScale(float perspectiveProgress)
        {
            return Lerp(DesignSystem.MinNoteScale3D, DesignSystem.MaxNoteScale3D, perspectiveProgress);
        }

        /// <summary>
        /// Calculate highway width at a given depth.
        /// </summary>
        protected float CalculateHighwayWidth(float perspectiveProgress, float drawWidth)
        {
            float bottomWidth = drawWidth * DesignSystem.HighwayWidthBottom;
            float topWidth = bottomWidth * DesignSystem.HighwayWidthTopRatio;
            return Lerp(topWidth, bottomWidth, perspectiveProgress);
        }

        /// <summary>
        /// Calculate Y position for 3D view using perspective.
        /// </summary>
        protected float Calculate3DY(float perspectiveProgress, float drawHeight)
        {
            float vanishingPointY = drawHeight * DesignSystem.VanishingPointRatio;
            float hitLineY = drawHeight * DesignSystem.HitLineRatio3D;
            return Lerp(vanishingPointY, hitLineY, perspectiveProgress);
        }

        #endregion

        #region Manuscript Position Calculations

        /// <summary>
        /// Staff position mapping for drum components.
        /// Returns a float where 0 = middle line, positive = above, negative = below.
        /// Each unit represents one staff line/space distance.
        /// </summary>
        protected static readonly Dictionary<string, float> StaffPositions = new()
        {
            // Below the staff (bass drum area)
            ["kick"] = -2.5f,

            // On the staff (snare area)
            ["snare"] = 0f,
            ["rimshot"] = 0f,
            ["cross_stick"] = 0f,

            // Above center (tom area)
            ["tom_low"] = 0.5f,
            ["tom_mid"] = 1f,
            ["tom_high"] = 1.5f,

            // Top of staff and above (hi-hat area)
            ["hihat_closed"] = 2f,
            ["hihat_open"] = 2f,
            ["hihat_pedal"] = -2f,
            ["hihat"] = 2f,

            // Above staff (cymbals)
            ["ride"] = 2.5f,
            ["crash"] = 3f,
            ["china"] = 3f,
            ["splash"] = 3f,

            // Miscellaneous
            ["cowbell"] = 2f,
            ["percussion"] = 1f
        };

        /// <summary>
        /// Get the staff position for a drum component.
        /// </summary>
        protected static float GetStaffPosition(string component)
        {
            if (string.IsNullOrEmpty(component))
                return 0f;

            string key = component.ToLowerInvariant();

            if (StaffPositions.TryGetValue(key, out float position))
                return position;

            // Try partial matches for compound names
            foreach (var kvp in StaffPositions)
            {
                if (key.Contains(kvp.Key))
                    return kvp.Value;
            }

            return 0f; // Default to middle of staff
        }

        /// <summary>
        /// Calculate X position for manuscript view based on component.
        /// </summary>
        protected float CalculateManuscriptX(string component, float drawWidth)
        {
            float staffCenterX = drawWidth / 2;
            float staffPos = GetStaffPosition(component);
            return staffCenterX + staffPos * DesignSystem.StaffLineSpacing;
        }

        #endregion

        #region Utility Methods

        /// <summary>Linear interpolation.</summary>
        protected static float Lerp(float start, float end, float amount)
            => start + (end - start) * amount;

        /// <summary>Clamp a value between min and max.</summary>
        protected static float Clamp(float value, float min, float max)
            => Math.Max(min, Math.Min(max, value));

        /// <summary>
        /// Smooth step interpolation for easing.
        /// </summary>
        protected static float SmoothStep(float t)
        {
            t = Clamp(t, 0f, 1f);
            return t * t * (3f - 2f * t);
        }

        /// <summary>
        /// Get note color based on component name.
        /// </summary>
        protected static Color4 GetNoteColor(string component)
        {
            return DesignSystem.GetComponentColor(component);
        }

        /// <summary>
        /// Calculate timing progress from time values.
        /// </summary>
        protected float CalculateProgress(double timeUntilHit, double approachDuration)
        {
            if (approachDuration <= 0)
                return 1f;
            return 1f - (float)(timeUntilHit / approachDuration);
        }

        #endregion
    }

    /// <summary>
    /// Context information passed when updating note positions in enhanced views.
    /// Contains all the layout and configuration data needed for positioning.
    /// </summary>
    public readonly struct EnhancedNotePositionContext
    {
        /// <summary>Total number of lanes in the layout.</summary>
        public readonly int TotalLaneCount;

        /// <summary>Number of visible lanes (may exclude kick lane).</summary>
        public readonly int VisibleLaneCount;

        /// <summary>Index of the kick lane.</summary>
        public readonly int KickLaneIndex;

        /// <summary>Whether kick uses a global line across all lanes.</summary>
        public readonly bool UseGlobalKickLine;

        /// <summary>Current approach duration in milliseconds.</summary>
        public readonly double ApproachDuration;

        /// <summary>Current note width scale preference.</summary>
        public readonly float NoteWidthScale;

        public EnhancedNotePositionContext(
            int totalLaneCount,
            int visibleLaneCount,
            int kickLaneIndex,
            bool useGlobalKickLine,
            double approachDuration,
            float noteWidthScale)
        {
            TotalLaneCount = totalLaneCount;
            VisibleLaneCount = visibleLaneCount;
            KickLaneIndex = kickLaneIndex;
            UseGlobalKickLine = useGlobalKickLine;
            ApproachDuration = approachDuration;
            NoteWidthScale = noteWidthScale;
        }
    }
}
