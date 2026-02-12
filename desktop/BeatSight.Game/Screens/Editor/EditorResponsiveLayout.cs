using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.Screens.Editor
{
    internal readonly record struct EditorResponsiveLayoutMetrics(
        float InspectorWidth,
        float TimelineTopHeight,
        float TimelineToolboxHeight,
        float FooterHeight,
        float PanelGap,
        float StackedInspectorHeight,
        bool UseStackedInspector);

    internal static class EditorResponsiveLayout
    {
        private const float stackWidthThreshold = 1320f;
        private const float unstackWidthThreshold = 1420f;
        private const float stackHeightThreshold = 730f;
        private const float unstackHeightThreshold = 790f;

        public static EditorResponsiveLayoutMetrics Compute(float viewportWidth, float viewportHeight, bool currentlyStacked)
        {
            float width = viewportWidth > 0 ? viewportWidth : 1920f;
            float height = viewportHeight > 0 ? viewportHeight : 1080f;

            bool shouldStack = currentlyStacked
                ? width < unstackWidthThreshold || height < unstackHeightThreshold
                : width < stackWidthThreshold || height < stackHeightThreshold;

            float inspectorWidth = ResponsiveLayout.ClampFraction(width, 0.245f, 360f, 540f);
            float timelineTopHeight = ResponsiveLayout.ClampFraction(height, 0.245f, 180f, 320f);
            float timelineToolboxHeight = ResponsiveLayout.ClampFraction(height, 0.108f, 84f, 136f);
            float footerHeight = ResponsiveLayout.ClampFraction(height, 0.09f, 68f, 112f);
            float panelGap = ResponsiveLayout.ClampFraction(width, 0.0065f, 8f, 14f);
            float stackedInspectorHeight = ResponsiveLayout.ClampFraction(height, 0.285f, 180f, 340f);

            return new EditorResponsiveLayoutMetrics(
                inspectorWidth,
                timelineTopHeight,
                timelineToolboxHeight,
                footerHeight,
                panelGap,
                stackedInspectorHeight,
                shouldStack);
        }
    }
}
