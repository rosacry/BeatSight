using System;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createEditor()
        {
            var viewport = resolveResponsiveViewport();
            var initialMetrics = EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout, footerTipsCollapsed);

            timeline = new EditorTimeline
            {
                RelativeSizeAxes = Axes.Both
            };

            timeline.NoteSelected += onTimelineNoteSelected;
            timeline.NoteAdded += onTimelineNoteChanged;
            timeline.NoteChanged += onTimelineNoteChanged;
            timeline.NoteDeleted += onTimelineNoteChanged;
            timeline.EditBegan += onTimelineEditBegan;
            timeline.DragStarted += onTimelineDragStarted;
            timeline.DragEnded += onTimelineDragEnded;
            timeline.ZoomChanged += onTimelineZoomChanged;
            timeline.SnapDivisorChanged += onTimelineSnapDivisorChanged;
            timeline.SelectionChanged += onTimelineSelectionChanged;

            playbackPreview = new PlaybackPreview(
                () => currentTime,
                () => getSnapIntervalMs(),
                () => getSnapOriginMs(),
                () => beatGridVisible,
                referenceTimeMs => getSnapIntervalMs(referenceTimeMs),
                referenceTimeMs => getSnapOriginMs(referenceTimeMs))
            {
                RelativeSizeAxes = Axes.Both
            };
            playbackPreview.PlacementInputBlockedAtScreenSpace = isPreviewPlacementBlockedAt;
            playbackPreview.NotePlacementRequested += onPreviewNotePlacementRequested;
            playbackPreview.NoteRemovalRequested += onPreviewNoteRemovalRequested;

            previewSurfaceContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 16,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PreviewBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.13f
                    },
                    previewContentContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 6, Vertical = 4 },
                        Child = playbackPreview
                    },
                    inspectorToggleButton = new EditorButton("Hide Inspector", EditorColours.AccentUndo)
                    {
                        Size = new Vector2(132, 34),
                        Anchor = Anchor.TopRight,
                        Origin = Anchor.TopRight,
                        Margin = new MarginPadding { Top = 12, Right = 12 },
                        Alpha = 0,
                        Action = toggleInspectorCollapsed
                    }
                }
            };

            previewCellContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Right = initialMetrics.PanelGap },
                Child = previewSurfaceContainer
            };

            inspectorContainer = new Container
            {
                RelativeSizeAxes = Axes.Y,
                Width = initialMetrics.InspectorWidth,
                Margin = new MarginPadding { Left = initialMetrics.PanelGap },
                Padding = new MarginPadding { Top = 1, Bottom = 1 },
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Child = createInspectorPanel()
            };

            previewInspectorGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                RowDimensions = new[]
                {
                    new Dimension()
                },
                ColumnDimensions = new[]
                {
                    new Dimension(),
                    new Dimension(GridSizeMode.Absolute, initialMetrics.InspectorWidth)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        previewCellContainer,
                        inspectorContainer
                    }
                }
            };

            timelineLayoutGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize),
                    new Dimension()
                },
                Content = new[]
                {
                    new Drawable[] { createTimelineToolbox() },
                    new Drawable[] { timeline }
                }
            };

            var timelineSurface = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 16,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.TimelineBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.1f
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 12, Vertical = 6 },
                        Child = timelineLayoutGrid
                    },
                    timelineToolboxToggleButton = new EditorButton("Hide Toolbar", EditorColours.AccentUndo)
                    {
                        Size = new Vector2(138, 34),
                        Anchor = Anchor.TopRight,
                        Origin = Anchor.TopRight,
                        Margin = new MarginPadding { Top = 10, Right = 12 },
                        Alpha = 0,
                        Action = toggleTimelineToolboxCollapsed
                    }
                }
            };

            editorLayoutGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, timelineSurfaceHeight),
                    new Dimension(GridSizeMode.Absolute, timelinePreviewSplitterHeight),
                    new Dimension()
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Padding = new MarginPadding { Bottom = 1 },
                            Child = timelineSurface
                        }
                    },
                    new Drawable[]
                    {
                        timelinePreviewSplitter = new EditorVerticalSplitter
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = timelinePreviewSplitterHeight
                        }
                    },
                    new Drawable[]
                    {
                        previewInspectorGrid
                    }
                }
            };
            timelinePreviewSplitter.DragDeltaY += onTimelinePreviewSplitterDragDeltaY;
            timelinePreviewSplitter.DraggingStateChanged += active =>
            {
                if (!active)
                    appendStatusDetail("Timeline/playfield split adjusted");
            };

            syncTimelineToolboxCollapseToggle();

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 8, Vertical = 4 },
                Child = editorLayoutGrid
            };
        }

        private bool isPreviewPlacementBlockedAt(Vector2 screenSpacePosition)
        {
            if (isTimingSetupOverlayVisible())
                return true;

            if (isPointerInsideDrawable(inspectorToggleButton, screenSpacePosition))
                return true;

            if (isPointerInsideDrawable(timelineToolboxToggleButton, screenSpacePosition))
                return true;

            if (isPointerInsideDrawable(timelinePreviewSplitter, screenSpacePosition))
                return true;

            return isPointerInsideDrawable(inspectorContainer, screenSpacePosition);
        }

        private void onTimelinePreviewSplitterDragDeltaY(float deltaY)
        {
            if (editorLayoutGrid == null)
                return;

            var viewport = resolveResponsiveViewport();
            if (viewport.X <= 0 || viewport.Y <= 0)
                return;

            var metrics = EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout, footerTipsCollapsed);
            float currentTopHeight = resolveTimelineTopHeight(metrics, viewport);
            float totalHeight = editorLayoutGrid.DrawHeight > 0 ? editorLayoutGrid.DrawHeight : viewport.Y;
            float minTopHeight = resolveTimelineTopMinimumHeight(metrics, viewport);
            float maxTopHeight = Math.Max(minTopHeight, totalHeight - timelinePreviewSplitterHeight - minimumPreviewWorkspaceHeight);

            float nextTopHeight = Math.Clamp(currentTopHeight + deltaY, minTopHeight, maxTopHeight);
            timelineTopHeightOverride = nextTopHeight;
            persistTimelineSplitRatioForState(timelineToolboxCollapsed, nextTopHeight, metrics, viewport);
            applyResponsiveEditorLayout(force: true);
            playbackPreview?.ForceVisualLayoutRefresh();
        }
    }
}
