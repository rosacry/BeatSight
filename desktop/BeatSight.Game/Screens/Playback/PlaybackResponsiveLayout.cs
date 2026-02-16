using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.Screens.Playback
{
    internal readonly record struct PlaybackResponsiveLayoutMetrics(
        float HeaderStatusFont,
        float HeaderPaddingLeft,
        float HeaderPaddingRight,
        float HeaderPaddingTop,
        float HeaderPaddingBottom,
        float ToolbarBottomPadding,
        float ToolbarCornerRadius,
        float ToolbarInnerPaddingH,
        float ToolbarInnerPaddingV,
        float ToolbarSectionSpacing,
        float PlaybackRowSpacingX,
        float PlaybackRowSpacingY,
        float SliderContainerPaddingLeft,
        float SliderContainerPaddingRight,
        float SliderContainerPaddingTop,
        float SliderContainerPaddingBottom,
        float TimelineSliderHeight,
        float HeatmapHeight,
        float TimelineTimeFont,
        float TimelineSeparatorFont,
        float TimelineTimeSpacing,
        float TimelineTimeTopMargin,
        float GroupTitleFont,
        float GroupPaddingRight,
        float GroupPaddingBottom,
        float GroupFlowSpacingX,
        float GroupFlowSpacingY,
        float ToolbarButtonWidth,
        float ToolbarButtonHeight,
        float ToolbarButtonCorner,
        float ToolbarButtonFont,
        float SidebarButtonHeight,
        float SidebarButtonCorner,
        float SidebarButtonFont,
        float SliderLabelFont,
        float SliderValueFont,
        float SliderBlockSpacing,
        float DetailSliderHeight,
        float CheckboxLabelFont);

    internal static class PlaybackResponsiveLayout
    {
        public static PlaybackResponsiveLayoutMetrics Compute(float viewportWidth, float viewportHeight, bool manuscriptMode = false)
        {
            float width = viewportWidth > 0 ? viewportWidth : 1920f;
            float height = viewportHeight > 0 ? viewportHeight : 1080f;
            float aspect = width / System.Math.Max(1f, height);
            float compactBlend = System.Math.Clamp((860f - height) / 260f, 0f, 1f);
            compactBlend = System.Math.Max(compactBlend, System.Math.Clamp((1500f - width) / 420f, 0f, 1f));
            if (manuscriptMode)
                compactBlend = System.Math.Clamp(compactBlend + 0.22f, 0f, 1f);
            float ultraWideRelax = System.Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);

            float controlHeight = blend(34f, 27.6f, compactBlend);

            return new PlaybackResponsiveLayoutMetrics(
                HeaderStatusFont: blend(24f, 20f, compactBlend) + ultraWideRelax * 0.5f,
                HeaderPaddingLeft: ResponsiveLayout.ClampFraction(width, 0.078f, 108f, 164f) + ultraWideRelax * 10f,
                HeaderPaddingRight: ResponsiveLayout.ClampFraction(width, 0.016f, 20f, 34f) + ultraWideRelax * 3f,
                HeaderPaddingTop: ResponsiveLayout.ClampFraction(height, 0.018f, 12f, 24f),
                HeaderPaddingBottom: ResponsiveLayout.ClampFraction(height, 0.006f, 4f, 8f),
                ToolbarBottomPadding: blend(10f, 5f, compactBlend),
                ToolbarCornerRadius: blend(18f, 13f, compactBlend),
                ToolbarInnerPaddingH: blend(20f, 12f, compactBlend) + ultraWideRelax * 1.6f,
                ToolbarInnerPaddingV: blend(14f, 8f, compactBlend),
                ToolbarSectionSpacing: blend(12f, 7f, compactBlend) + ultraWideRelax * 0.7f,
                PlaybackRowSpacingX: blend(10f, 6f, compactBlend) + ultraWideRelax * 0.65f,
                PlaybackRowSpacingY: blend(10f, 6f, compactBlend),
                SliderContainerPaddingLeft: blend(18f, 12f, compactBlend),
                SliderContainerPaddingRight: blend(12f, 8f, compactBlend),
                SliderContainerPaddingTop: blend(4f, 2.5f, compactBlend),
                SliderContainerPaddingBottom: blend(4f, 2.5f, compactBlend),
                TimelineSliderHeight: blend(12f, 9f, compactBlend),
                HeatmapHeight: blend(10f, 7.2f, compactBlend),
                TimelineTimeFont: blend(18f, 14.8f, compactBlend) + ultraWideRelax * 0.3f,
                TimelineSeparatorFont: blend(18f, 14.6f, compactBlend) + ultraWideRelax * 0.25f,
                TimelineTimeSpacing: blend(6f, 4.5f, compactBlend) + ultraWideRelax * 0.6f,
                TimelineTimeTopMargin: blend(20f, 14f, compactBlend),
                GroupTitleFont: blend(18f, 14.6f, compactBlend) + ultraWideRelax * 0.33f,
                GroupPaddingRight: blend(16f, 10f, compactBlend),
                GroupPaddingBottom: blend(8f, 5f, compactBlend),
                GroupFlowSpacingX: blend(8f, 5.5f, compactBlend),
                GroupFlowSpacingY: blend(4f, 2.5f, compactBlend),
                ToolbarButtonWidth: blend(110f, 86f, compactBlend),
                ToolbarButtonHeight: controlHeight,
                ToolbarButtonCorner: blend(8f, 6.5f, compactBlend),
                ToolbarButtonFont: blend(16f, 13.2f, compactBlend) + ultraWideRelax * 0.22f,
                SidebarButtonHeight: blend(36f, 30f, compactBlend),
                SidebarButtonCorner: blend(8f, 6.5f, compactBlend),
                SidebarButtonFont: blend(16f, 13.2f, compactBlend) + ultraWideRelax * 0.2f,
                SliderLabelFont: blend(18f, 14.4f, compactBlend) + ultraWideRelax * 0.3f,
                SliderValueFont: blend(18f, 14.6f, compactBlend) + ultraWideRelax * 0.28f,
                SliderBlockSpacing: blend(6f, 4.5f, compactBlend),
                DetailSliderHeight: blend(16f, 13f, compactBlend),
                CheckboxLabelFont: blend(12f, 10.4f, compactBlend));
        }

        private static float blend(float normal, float compact, float t)
            => normal + (compact - normal) * t;
    }
}
