using System;
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

        public static EditorResponsiveLayoutMetrics Compute(float viewportWidth, float viewportHeight, bool currentlyStacked, bool footerHintsCollapsed = false)
        {
            float width = viewportWidth > 0 ? viewportWidth : 1920f;
            float height = viewportHeight > 0 ? viewportHeight : 1080f;

            bool shouldStack = currentlyStacked
                ? width < unstackWidthThreshold || height < unstackHeightThreshold
                : width < stackWidthThreshold || height < stackHeightThreshold;

            float inspectorWidth = ResponsiveLayout.ClampFraction(width, 0.245f, 360f, 540f);
            float timelineTopHeight = ResponsiveLayout.ClampFraction(height, 0.245f, 180f, 320f);
            float timelineToolboxHeight = ResponsiveLayout.ClampFraction(height, 0.102f, 78f, 136f);
            float footerHeight = footerHintsCollapsed
                ? ResponsiveLayout.ClampFraction(height, 0.032f, 24f, 40f)
                : ResponsiveLayout.ClampFraction(height, 0.076f, 56f, 104f);
            float panelGap = ResponsiveLayout.ClampFraction(width, 0.0065f, 8f, 14f);
            float stackedInspectorHeight = ResponsiveLayout.ClampFraction(height, 0.245f, 168f, 320f);

            return new EditorResponsiveLayoutMetrics(
                inspectorWidth,
                timelineTopHeight,
                timelineToolboxHeight,
                footerHeight,
                panelGap,
                stackedInspectorHeight,
                shouldStack);
        }

        internal static float ResolveInspectorActionRowWidthFraction(float viewportWidth, bool stackedLayout, int columnCount, float compactBlend)
        {
            if (!stackedLayout || columnCount >= 4)
                return 1f;

            float width = viewportWidth > 0 ? viewportWidth : 1280f;
            float t = Math.Clamp(compactBlend, 0f, 1f);

            float targetWidth = columnCount switch
            {
                1 => ResponsiveLayout.ClampFraction(width, lerp(0.35f, 0.32f, t), 228f, 420f),
                2 => ResponsiveLayout.ClampFraction(width, lerp(0.62f, 0.56f, t), 440f, 760f),
                3 => ResponsiveLayout.ClampFraction(width, lerp(0.90f, 0.82f, t), 660f, 1080f),
                _ => width
            };

            return Math.Clamp(targetWidth / width, 0.18f, 1f);
        }

        private static float lerp(float start, float end, float t)
            => start + (end - start) * t;
    }
}
