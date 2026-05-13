using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void applyPreviewInspectorLayout(EditorResponsiveLayoutMetrics metrics)
        {
            inspectorStackedLayout = metrics.UseStackedInspector;
            bool hideInspector = inspectorCollapsed;

            if (!inspectorStackedLayout)
            {
                previewCellContainer.Padding = new MarginPadding { Right = hideInspector ? 0 : metrics.PanelGap };
                inspectorContainer.RelativeSizeAxes = Axes.Y;
                inspectorContainer.AutoSizeAxes = Axes.None;
                inspectorContainer.Anchor = Anchor.TopRight;
                inspectorContainer.Origin = Anchor.TopRight;
                inspectorContainer.Margin = new MarginPadding { Left = metrics.PanelGap };
                inspectorContainer.Width = metrics.InspectorWidth;
                inspectorContainer.Height = 1f;
                inspectorContainer.Alpha = hideInspector ? 0 : 1f;
                inspectorContainer.AlwaysPresent = !hideInspector;

                if (hideInspector)
                {
                    previewInspectorGrid.RowDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.ColumnDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.Content = new[]
                    {
                        new Drawable[]
                        {
                            previewCellContainer
                        }
                    };
                }
                else
                {
                    previewInspectorGrid.RowDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.ColumnDimensions = new[]
                    {
                        new Dimension(),
                        new Dimension(GridSizeMode.Absolute, metrics.InspectorWidth)
                    };
                    previewInspectorGrid.Content = new[]
                    {
                        new Drawable[]
                        {
                            previewCellContainer,
                            inspectorContainer
                        }
                    };
                }
            }
            else
            {
                previewCellContainer.Padding = new MarginPadding
                {
                    Bottom = hideInspector ? 0 : metrics.PanelGap
                };

                inspectorContainer.RelativeSizeAxes = Axes.X;
                inspectorContainer.AutoSizeAxes = Axes.None;
                inspectorContainer.Anchor = Anchor.TopLeft;
                inspectorContainer.Origin = Anchor.TopLeft;
                inspectorContainer.Margin = new MarginPadding();
                inspectorContainer.Width = 1f;
                inspectorContainer.Height = metrics.StackedInspectorHeight;
                inspectorContainer.Alpha = hideInspector ? 0 : 1;
                inspectorContainer.AlwaysPresent = !hideInspector;

                if (hideInspector)
                {
                    previewInspectorGrid.RowDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.ColumnDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.Content = new[]
                    {
                        new Drawable[]
                        {
                            previewCellContainer
                        }
                    };
                }
                else
                {
                    previewInspectorGrid.RowDimensions = new[]
                    {
                        new Dimension(),
                        new Dimension(GridSizeMode.Absolute, metrics.StackedInspectorHeight)
                    };
                    previewInspectorGrid.ColumnDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.Content = new[]
                    {
                        new Drawable[]
                        {
                            previewCellContainer
                        },
                        new Drawable[]
                        {
                            inspectorContainer
                        }
                    };
                }
            }

            lastInspectorWidth = metrics.InspectorWidth;
            lastStackedInspectorHeight = metrics.StackedInspectorHeight;
            lastPanelGap = metrics.PanelGap;
        }

        private void updateInspectorToggle(EditorResponsiveLayoutMetrics metrics, Vector2 viewport)
        {
            if (inspectorToggleButton == null)
                return;

            float toggleWidth = ResponsiveLayout.ClampFraction(viewport.X, 0.108f, 132f, 176f);
            float toggleHeight = ResponsiveLayout.ClampFraction(viewport.Y, 0.034f, 28f, 38f);
            float toggleInsetX = ResponsiveLayout.ClampFraction(viewport.X, 0.006f, 6f, 12f);

            inspectorToggleButton.Size = new Vector2(toggleWidth, toggleHeight);
            inspectorToggleButton.Margin = new MarginPadding
            {
                Right = toggleInsetX
            };

            inspectorToggleButton.SetLabel(inspectorCollapsed ? "Show Inspector" : "Hide Inspector");
            inspectorToggleButton.UpdateState(true, inspectorCollapsed ? "Show inspector panel (I)." : "Hide inspector panel (I).");
            inspectorToggleButton.FadeTo(inspectorCollapsed ? 0.74f : 0.64f, 160);
        }

        private void toggleInspectorCollapsed()
        {
            if (inspectorContainer == null || inspectorTransitionActive)
                return;

            if (inspectorCollapsed)
            {
                inspectorCollapsed = false;
                applyResponsiveEditorLayout(force: true);

                inspectorContainer.Show();
                inspectorContainer.AlwaysPresent = true;
                inspectorContainer.ClearTransforms();
                inspectorContainer.Alpha = 0;
                if (inspectorStackedLayout)
                {
                    inspectorContainer.Y = 14;
                    inspectorContainer.FadeIn(220, Easing.OutQuint);
                    inspectorContainer.MoveToY(0, 240, Easing.OutQuint);
                }
                else
                {
                    inspectorContainer.X = 22;
                    inspectorContainer.FadeIn(220, Easing.OutQuint);
                    inspectorContainer.MoveToX(0, 240, Easing.OutQuint);
                }

                appendStatusDetail("Inspector shown");
                return;
            }

            inspectorTransitionActive = true;
            inspectorContainer.Show();
            inspectorContainer.AlwaysPresent = true;
            inspectorContainer.ClearTransforms();

            if (inspectorStackedLayout)
            {
                inspectorContainer.FadeOut(190, Easing.OutQuint);
                inspectorContainer.MoveToY(20, 220, Easing.OutQuint);
            }
            else
            {
                inspectorContainer.FadeOut(190, Easing.OutQuint);
                inspectorContainer.MoveToX(28, 220, Easing.OutQuint);
            }

            Scheduler.AddDelayed(() =>
            {
                inspectorCollapsed = true;
                inspectorTransitionActive = false;
                applyResponsiveEditorLayout(force: true);
            }, 236);

            appendStatusDetail("Inspector hidden");
        }

        private float getInitialFooterHeight()
        {
            var viewport = resolveResponsiveViewport();
            return EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout, footerTipsCollapsed).FooterHeight;
        }

        private Vector2 resolveResponsiveViewport()
            => ResponsiveLayout.ResolveViewport(
                this,
                DrawWidth > 0 ? DrawWidth : 1920f,
                DrawHeight > 0 ? DrawHeight : 1080f);
    }
}
