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
            bool hideStackedInspector = inspectorStackedLayout && inspectorCollapsed;

            if (!inspectorStackedLayout)
            {
                previewCellContainer.Padding = new MarginPadding { Right = metrics.PanelGap };
                inspectorContainer.RelativeSizeAxes = Axes.Y;
                inspectorContainer.AutoSizeAxes = Axes.None;
                inspectorContainer.Anchor = Anchor.TopRight;
                inspectorContainer.Origin = Anchor.TopRight;
                inspectorContainer.Margin = new MarginPadding { Left = metrics.PanelGap };
                inspectorContainer.Width = metrics.InspectorWidth;
                inspectorContainer.Height = 1f;
                inspectorContainer.Alpha = 1f;
                inspectorContainer.AlwaysPresent = true;

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
            else
            {
                previewCellContainer.Padding = new MarginPadding
                {
                    Bottom = hideStackedInspector ? 0 : metrics.PanelGap
                };

                inspectorContainer.RelativeSizeAxes = Axes.X;
                inspectorContainer.AutoSizeAxes = Axes.None;
                inspectorContainer.Anchor = Anchor.TopLeft;
                inspectorContainer.Origin = Anchor.TopLeft;
                inspectorContainer.Margin = new MarginPadding();
                inspectorContainer.Width = 1f;
                inspectorContainer.Height = metrics.StackedInspectorHeight;
                inspectorContainer.Alpha = hideStackedInspector ? 0 : 1;
                inspectorContainer.AlwaysPresent = !hideStackedInspector;

                if (hideStackedInspector)
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

            float toggleWidth = ResponsiveLayout.ClampFraction(viewport.X, 0.094f, 116f, 172f);
            float toggleHeight = ResponsiveLayout.ClampFraction(viewport.Y, 0.036f, 30f, 40f);
            float toggleInsetX = ResponsiveLayout.ClampFraction(viewport.X, 0.007f, 8f, 14f);
            float toggleInsetY = ResponsiveLayout.ClampFraction(viewport.Y, 0.009f, 8f, 14f);

            inspectorToggleButton.Size = new Vector2(toggleWidth, toggleHeight);
            inspectorToggleButton.Margin = new MarginPadding
            {
                Top = toggleInsetY,
                Right = toggleInsetX
            };

            if (!metrics.UseStackedInspector)
            {
                inspectorToggleButton.UpdateState(false, "Inspector collapse is available in compact layouts.");
                inspectorToggleButton.FadeOut(120);
                return;
            }

            inspectorToggleButton.SetLabel(inspectorCollapsed ? "Show Panel" : "Hide Panel");
            inspectorToggleButton.UpdateState(true, inspectorCollapsed ? "Show inspector panel (I)." : "Hide inspector panel (I).");
            inspectorToggleButton.FadeTo(0.95f, 120);
        }

        private void toggleInspectorCollapsed()
        {
            if (!inspectorStackedLayout)
                return;

            inspectorCollapsed = !inspectorCollapsed;
            applyResponsiveEditorLayout(force: true);
            appendStatusDetail(inspectorCollapsed ? "Inspector hidden (compact layout)" : "Inspector shown (compact layout)");
        }

        private float getInitialFooterHeight()
        {
            var viewport = resolveResponsiveViewport();
            return EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout).FooterHeight;
        }

        private Vector2 resolveResponsiveViewport()
            => ResponsiveLayout.ResolveViewport(
                this,
                DrawWidth > 0 ? DrawWidth : 1920f,
                DrawHeight > 0 ? DrawHeight : 1080f);
    }
}
