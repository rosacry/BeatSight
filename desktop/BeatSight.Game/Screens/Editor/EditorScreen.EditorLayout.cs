using System;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createEditor()
        {
            var viewport = resolveResponsiveViewport();
            var initialMetrics = EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout, footerTipsCollapsed);
            var sharedSurfacePadding = new MarginPadding { Left = 8, Right = 8, Top = 0, Bottom = 4 };
            const float initialPreviewUtilityStripHeight = 38f;

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

            var previewContentPadding = sharedSurfacePadding;
            previewContentPadding.Top = initialPreviewUtilityStripHeight + 4f;

            previewSurfaceContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 0,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PreviewBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 112f,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.TopLeft,
                        Colour = ColourInfo.GradientVertical(
                            EditorColours.PanelStroke.Opacity(0.18f),
                            Color4.Transparent)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.08f
                    },
                    previewUtilityStripContainer = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = initialPreviewUtilityStripHeight,
                        Masking = true,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = EditorColours.Mix(EditorColours.PreviewBackground, EditorColours.ControlsBackground, 0.42f)
                            },
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = EditorColours.PanelStroke,
                                Alpha = 0.08f
                            },
                            new Box
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 1,
                                Anchor = Anchor.BottomLeft,
                                Origin = Anchor.BottomLeft,
                                Colour = EditorColours.Divider.Opacity(0.84f)
                            },
                            new Container
                            {
                                RelativeSizeAxes = Axes.Both,
                                Padding = new MarginPadding { Left = 12, Right = 10, Top = 5, Bottom = 5 },
                                Children = new Drawable[]
                                {
                                    new Container
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        Width = 1f,
                                        AutoSizeAxes = Axes.Y,
                                        Anchor = Anchor.CentreLeft,
                                        Origin = Anchor.CentreLeft,
                                        Padding = new MarginPadding { Right = 154f },
                                        Child = new FillFlowContainer
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Width = 1f,
                                            AutoSizeAxes = Axes.Y,
                                            Direction = FillDirection.Vertical,
                                            Spacing = new Vector2(0, 2),
                                            Anchor = Anchor.CentreLeft,
                                            Origin = Anchor.CentreLeft,
                                            Children = new Drawable[]
                                            {
                                                previewUtilityTitleText = new SpriteText
                                                {
                                                    Text = "Playfield",
                                                    Font = BeatSightFont.Section(11.8f),
                                                    Colour = EditorColours.TextPrimary,
                                                    UseFullGlyphHeight = false
                                                },
                                                previewUtilityHintText = new SpriteText
                                                {
                                                    Text = "LMB place | Shift no snap | RMB remove",
                                                    Font = BeatSightFont.Caption(9.9f),
                                                    Colour = EditorColours.TextMuted,
                                                    UseFullGlyphHeight = false
                                                }
                                            }
                                        }
                                    },
                                    inspectorToggleButton = new EditorButton("Hide Inspector", EditorColours.AccentUndo)
                                    {
                                        Size = new Vector2(140, 30),
                                        EnableScaleAnimation = false,
                                        Anchor = Anchor.CentreRight,
                                        Origin = Anchor.CentreRight,
                                        Alpha = 0,
                                        Action = toggleInspectorCollapsed
                                    }
                                }
                            }
                        }
                    },
                    previewContentContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = previewContentPadding,
                        Child = playbackPreview
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
                CornerRadius = 0,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.TimelineBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 84f,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.TopLeft,
                        Colour = ColourInfo.GradientVertical(
                            EditorColours.PanelStroke.Opacity(0.2f),
                            Color4.Transparent)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.08f
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = sharedSurfacePadding,
                        Child = timelineLayoutGrid
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

            return editorLayoutGrid;
        }

        private Drawable createEditorWorkspace(Drawable editorBody, Drawable footer)
        {
            editorWorkspaceGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                RowDimensions = new[]
                {
                    new Dimension(),
                    new Dimension(GridSizeMode.Absolute, getInitialFooterHeight())
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        editorBody
                    },
                    new Drawable[]
                    {
                        footer
                    }
                }
            };

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = editorWorkspaceHorizontalInset },
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = editorWorkspaceCornerRadius,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = EditorColours.WorkspaceBackground
                        },
                        new Box
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 180f,
                            Anchor = Anchor.TopLeft,
                            Origin = Anchor.TopLeft,
                            Colour = ColourInfo.GradientVertical(
                                EditorColours.PanelStroke.Opacity(0.16f),
                                Color4.Transparent)
                        },
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = EditorColours.PanelStroke,
                            Alpha = 0.06f
                        },
                        editorWorkspaceGrid
                    }
                }
            };
        }

        private bool isPreviewPlacementBlockedAt(Vector2 screenSpacePosition)
        {
            if (isTimingSetupOverlayVisible())
                return true;

            if (isPointerInsideDrawable(previewUtilityStripContainer, screenSpacePosition))
                return true;

            if (isPointerInsideDrawable(inspectorToggleButton, screenSpacePosition))
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
            float minimumPreviewHeight = resolveMinimumPreviewWorkspaceHeight(viewport);
            float maxTopHeight = Math.Max(minTopHeight, totalHeight - timelinePreviewSplitterHeight - minimumPreviewHeight);

            float nextTopHeight = Math.Clamp(currentTopHeight + deltaY, minTopHeight, maxTopHeight);
            timelineTopHeightOverride = nextTopHeight;
            persistTimelineSplitRatioForState(timelineToolboxCollapsed, nextTopHeight, metrics, viewport);
            applyResponsiveEditorLayout(force: true);
            playbackPreview?.ForceVisualLayoutRefresh();
        }
    }
}
