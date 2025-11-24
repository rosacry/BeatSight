using System;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using osu.Framework.Bindables;
using osu.Framework.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// Base class for playfield view implementations.
    /// Provides common functionality and sensible defaults.
    /// </summary>
    public abstract class PlayfieldViewBase : IPlayfieldView
    {
        public abstract Configuration.LaneViewMode ViewMode { get; }

        protected ViewContext? Context { get; private set; }
        protected LaneLayout? Layout { get; private set; }
        protected bool UseGlobalKickLine { get; private set; } = true;
        protected Beatmap? LoadedBeatmap { get; private set; }

        protected int LaneCount => Layout?.LaneCount ?? 7;
        protected int KickLane => Layout?.KickLane ?? 3;
        protected int VisibleLaneCount => UseGlobalKickLine ? Math.Max(1, LaneCount - 1) : LaneCount;

        public virtual float HitLineYRatio => 0.95f;
        public virtual float SpawnYRatio => 0f;

        public virtual void Initialize(ViewContext context)
        {
            Context = context ?? throw new ArgumentNullException(nameof(context));
        }

        public virtual void SetLaneLayout(LaneLayout layout)
        {
            Layout = layout ?? throw new ArgumentNullException(nameof(layout));
        }

        public virtual void SetKickLineMode(bool useGlobalLine)
        {
            UseGlobalKickLine = useGlobalLine;
        }

        public virtual void LoadBeatmap(Beatmap beatmap)
        {
            LoadedBeatmap = beatmap;
        }

        public abstract Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick);
        public abstract Drawable CreateStrikeZone();
        public abstract void UpdateNotePosition(
            DrawableNote note,
            float progress,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            NotePositionContext positionContext);

        public virtual void ApplyNoteStyle(DrawableNote note)
        {
            // Default: no-op, subclasses can override
        }

        public virtual void UpdateBackground(double currentTime)
        {
            // Default: no-op, subclasses can override for animations
        }

        /// <summary>
        /// Linear interpolation helper.
        /// </summary>
        protected static float Lerp(float start, float end, float amount)
            => start + (end - start) * amount;

        /// <summary>
        /// Calculate visual lane index accounting for global kick line mode.
        /// </summary>
        protected int GetVisualLaneIndex(int lane, NotePositionContext ctx)
        {
            if (ctx.UseGlobalKickLine && lane > ctx.KickLaneIndex)
                return lane - 1;
            return lane;
        }

        /// <summary>
        /// Calculate note width based on lane width and user scale preference.
        /// </summary>
        protected float CalculateNoteWidth(float laneWidth, float userScale)
        {
            // Base fill: 80% of lane width
            // User scale at 1.0x equals 75% of the base (matching legacy 0.75x)
            // Cap at 100% of lane width for visual cleanliness
            float effectiveScale = userScale * 0.75f;
            float scale = Math.Min(1.25f, effectiveScale);
            return laneWidth * 0.8f * scale;
        }
    }
}
