using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// Manages and coordinates between different playfield view implementations.
    /// Provides a unified API for switching views and delegating rendering.
    /// </summary>
    public partial class PlayfieldViewManager : CompositeDrawable
    {
        private readonly Dictionary<LaneViewMode, IPlayfieldView> views = new();
        private IPlayfieldView? activeView;
        private LaneViewMode currentViewMode = LaneViewMode.TwoDimensional;

        private LaneLayout? currentLayout;
        private bool useGlobalKickLine = true;
        private Beatmap? currentBeatmap;

        private Container? backgroundContainer;
        private Container? strikeZoneContainer;

        private ViewContext? viewContext;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        public PlayfieldViewManager()
        {
            RelativeSizeAxes = Axes.Both;
        }

        private Bindable<bool> useEnhancedViews = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            // Check if enhanced views are preferred (defaults to true for new installs)
            useEnhancedViews = config.GetBindable<bool>(BeatSightSetting.UseEnhancedViews);

            // Register view implementations - prefer enhanced versions
            if (useEnhancedViews.Value)
            {
                RegisterView(new TwoDimensionalLaneViewEnhanced());
                RegisterView(new ThreeDimensionalHighwayViewEnhanced());
                RegisterView(new ManuscriptViewEnhanced());
            }
            else
            {
                // Legacy views for compatibility
                RegisterView(new TwoDimensionalLaneView());
                RegisterView(new ThreeDimensionalHighwayView());
                RegisterView(new ManuscriptView());
            }

            // Create containers for background and strike zone
            backgroundContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Depth = 100 // Behind everything
            };

            strikeZoneContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Depth = -50 // In front of background, behind notes
            };

            AddInternal(backgroundContainer);
            AddInternal(strikeZoneContainer);

            // Listen for enhanced view toggle changes
            useEnhancedViews.BindValueChanged(onEnhancedViewsChanged);
        }

        private void onEnhancedViewsChanged(ValueChangedEvent<bool> e)
        {
            // Clear existing views
            views.Clear();

            // Re-register with appropriate implementations
            if (e.NewValue)
            {
                RegisterView(new TwoDimensionalLaneViewEnhanced());
                RegisterView(new ThreeDimensionalHighwayViewEnhanced());
                RegisterView(new ManuscriptViewEnhanced());
            }
            else
            {
                RegisterView(new TwoDimensionalLaneView());
                RegisterView(new ThreeDimensionalHighwayView());
                RegisterView(new ManuscriptView());
            }

            // Re-initialize views with context
            if (viewContext != null)
            {
                foreach (var view in views.Values)
                {
                    view.Initialize(viewContext);
                    if (currentLayout != null)
                        view.SetLaneLayout(currentLayout);
                    view.SetKickLineMode(useGlobalKickLine);
                    if (currentBeatmap != null)
                        view.LoadBeatmap(currentBeatmap);
                }
            }

            // Re-apply current view mode
            SetViewMode(currentViewMode);
        }

        /// <summary>
        /// Register a view implementation for its view mode.
        /// </summary>
        public void RegisterView(IPlayfieldView view)
        {
            views[view.ViewMode] = view;
        }

        /// <summary>
        /// Initialize all views with the shared context.
        /// </summary>
        public void Initialize(ViewContext context)
        {
            viewContext = context;

            foreach (var view in views.Values)
            {
                view.Initialize(context);
            }
        }

        /// <summary>
        /// Set the active view mode.
        /// </summary>
        public void SetViewMode(LaneViewMode mode)
        {
            if (currentViewMode == mode && activeView != null)
                return;

            currentViewMode = mode;

            if (!views.TryGetValue(mode, out var view))
            {
                // Fallback to 2D if requested mode isn't available
                view = views.GetValueOrDefault(LaneViewMode.TwoDimensional);
            }

            activeView = view;

            // Rebuild visuals for new view
            RebuildVisuals();
        }

        /// <summary>
        /// Set the lane layout for all views.
        /// </summary>
        public void SetLaneLayout(LaneLayout layout)
        {
            currentLayout = layout;

            foreach (var view in views.Values)
            {
                view.SetLaneLayout(layout);
            }

            RebuildVisuals();
        }

        /// <summary>
        /// Set kick line mode for all views.
        /// </summary>
        public void SetKickLineMode(bool useGlobalLine)
        {
            useGlobalKickLine = useGlobalLine;

            foreach (var view in views.Values)
            {
                view.SetKickLineMode(useGlobalLine);
            }

            RebuildVisuals();
        }

        /// <summary>
        /// Load a beatmap into all views.
        /// </summary>
        public void LoadBeatmap(Beatmap? beatmap)
        {
            currentBeatmap = beatmap;

            foreach (var view in views.Values)
            {
                if (beatmap != null)
                    view.LoadBeatmap(beatmap);
            }
        }

        /// <summary>
        /// Get the current active view.
        /// </summary>
        public IPlayfieldView? ActiveView => activeView;

        /// <summary>
        /// Get the hit line Y ratio for the current view.
        /// </summary>
        public float HitLineYRatio => activeView?.HitLineYRatio ?? 0.95f;

        /// <summary>
        /// Get the spawn Y ratio for the current view.
        /// </summary>
        public float SpawnYRatio => activeView?.SpawnYRatio ?? 0f;

        /// <summary>
        /// Update note position using the active view's logic.
        /// </summary>
        public void UpdateNotePosition(
            DrawableNote note,
            float progress,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            NotePositionContext ctx)
        {
            activeView?.UpdateNotePosition(note, progress, drawWidth, drawHeight, hitLineY, travelDistance, ctx);
        }

        /// <summary>
        /// Apply view-specific styling to a note.
        /// </summary>
        public void ApplyNoteStyle(DrawableNote note)
        {
            activeView?.ApplyNoteStyle(note);
        }

        /// <summary>
        /// Update background animations.
        /// </summary>
        public void UpdateBackground(double currentTime)
        {
            activeView?.UpdateBackground(currentTime);
        }

        /// <summary>
        /// Rebuild background and strike zone for current view.
        /// </summary>
        private void RebuildVisuals()
        {
            if (activeView == null || backgroundContainer == null || strikeZoneContainer == null)
                return;

            int laneCount = currentLayout?.LaneCount ?? 7;

            backgroundContainer.Clear();
            var background = activeView.CreateBackground(DrawWidth, DrawHeight, laneCount, useGlobalKickLine);
            if (background != null)
            {
                background.RelativeSizeAxes = Axes.Both;
                backgroundContainer.Add(background);
            }

            strikeZoneContainer.Clear();
            var strikeZone = activeView.CreateStrikeZone();
            if (strikeZone != null)
            {
                strikeZoneContainer.Add(strikeZone);
            }
        }

        protected override void Update()
        {
            base.Update();

            // Let views update their backgrounds
            if (viewContext != null)
            {
                double currentTime = viewContext.CurrentTimeProvider();
                activeView?.UpdateBackground(currentTime);
            }
        }
    }
}
