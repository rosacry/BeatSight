using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using osu.Framework.Bindables;
using osu.Framework.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// Defines the contract for a playfield view renderer.
    /// Each view mode (2D Lane, 3D Highway, Manuscript) implements this interface
    /// to provide consistent behaviour with specialized rendering.
    /// </summary>
    public interface IPlayfieldView
    {
        /// <summary>
        /// The view mode this renderer handles.
        /// </summary>
        Configuration.LaneViewMode ViewMode { get; }

        /// <summary>
        /// Initialize the view with necessary dependencies.
        /// </summary>
        void Initialize(ViewContext context);

        /// <summary>
        /// Configure the view for a specific lane layout.
        /// </summary>
        void SetLaneLayout(LaneLayout layout);

        /// <summary>
        /// Configure kick line display mode.
        /// </summary>
        void SetKickLineMode(bool useGlobalLine);

        /// <summary>
        /// Load a beatmap into this view.
        /// </summary>
        void LoadBeatmap(Beatmap beatmap);

        /// <summary>
        /// Create the background drawable for this view mode.
        /// </summary>
        Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick);

        /// <summary>
        /// Create the strike zone (hit line area) for this view mode.
        /// </summary>
        Drawable CreateStrikeZone();

        /// <summary>
        /// Update a note's visual position and appearance for this view.
        /// </summary>
        void UpdateNotePosition(
            DrawableNote note,
            float progress,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            NotePositionContext positionContext);

        /// <summary>
        /// Apply view-specific styling to a note.
        /// </summary>
        void ApplyNoteStyle(DrawableNote note);

        /// <summary>
        /// Get the hit line Y position as a proportion of draw height (0-1).
        /// </summary>
        float HitLineYRatio { get; }

        /// <summary>
        /// Get the spawn position Y as a proportion of draw height (0-1).
        /// </summary>
        float SpawnYRatio { get; }

        /// <summary>
        /// Called each frame to update any background animations.
        /// </summary>
        void UpdateBackground(double currentTime);
    }

    /// <summary>
    /// Shared context passed to all view implementations.
    /// </summary>
    public class ViewContext
    {
        public required Func<double> CurrentTimeProvider { get; init; }
        public required IBindable<double> ZoomLevel { get; init; }
        public required IBindable<bool> AutoZoom { get; init; }
        public required IBindable<double> NoteWidthScale { get; init; }
        public required IBindable<bool> ShowGlowEffects { get; init; }
        public required IBindable<bool> ShowParticleEffects { get; init; }
        public required double ApproachDuration { get; init; }
    }

    /// <summary>
    /// Context for positioning notes, reducing parameter bloat.
    /// </summary>
    public class NotePositionContext
    {
        public int TotalLaneCount { get; init; }
        public int VisibleLaneCount { get; init; }
        public float LaneWidth { get; init; }
        public int KickLaneIndex { get; init; }
        public bool UseGlobalKickLine { get; init; }
    }
}
