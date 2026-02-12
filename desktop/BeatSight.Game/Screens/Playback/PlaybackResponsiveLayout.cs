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
        public static PlaybackResponsiveLayoutMetrics Compute(float viewportWidth, float viewportHeight)
        {
            float width = viewportWidth > 0 ? viewportWidth : 1920f;
            float height = viewportHeight > 0 ? viewportHeight : 1080f;
            float aspect = width / System.Math.Max(1f, height);
            float compactBlend = System.Math.Clamp((860f - height) / 260f, 0f, 1f);
            compactBlend = System.Math.Max(compactBlend, System.Math.Clamp((1500f - width) / 420f, 0f, 1f));
            float ultraWideRelax = System.Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);

            float controlHeight = blend(34f, 30f, compactBlend);

            return new PlaybackResponsiveLayoutMetrics(
                HeaderStatusFont: blend(24f, 20f, compactBlend) + ultraWideRelax * 0.5f,
                HeaderPaddingLeft: ResponsiveLayout.ClampFraction(width, 0.078f, 108f, 164f) + ultraWideRelax * 10f,
                HeaderPaddingRight: ResponsiveLayout.ClampFraction(width, 0.016f, 20f, 34f) + ultraWideRelax * 3f,
                HeaderPaddingTop: ResponsiveLayout.ClampFraction(height, 0.018f, 12f, 24f),
                HeaderPaddingBottom: ResponsiveLayout.ClampFraction(height, 0.006f, 4f, 8f),
                ToolbarBottomPadding: blend(10f, 6f, compactBlend),
                ToolbarCornerRadius: blend(18f, 14f, compactBlend),
                ToolbarInnerPaddingH: blend(20f, 14f, compactBlend) + ultraWideRelax * 2f,
                ToolbarInnerPaddingV: blend(14f, 10f, compactBlend),
                ToolbarSectionSpacing: blend(12f, 9f, compactBlend) + ultraWideRelax * 1f,
                PlaybackRowSpacingX: blend(10f, 8f, compactBlend) + ultraWideRelax * 0.8f,
                PlaybackRowSpacingY: blend(10f, 8f, compactBlend),
                SliderContainerPaddingLeft: blend(18f, 14f, compactBlend),
                SliderContainerPaddingRight: blend(12f, 10f, compactBlend),
                SliderContainerPaddingTop: blend(4f, 3f, compactBlend),
                SliderContainerPaddingBottom: blend(4f, 3f, compactBlend),
                TimelineSliderHeight: blend(12f, 10f, compactBlend),
                HeatmapHeight: blend(10f, 8f, compactBlend),
                TimelineTimeFont: blend(18f, 15.5f, compactBlend) + ultraWideRelax * 0.35f,
                TimelineSeparatorFont: blend(18f, 15.3f, compactBlend) + ultraWideRelax * 0.3f,
                TimelineTimeSpacing: blend(6f, 5f, compactBlend) + ultraWideRelax * 0.8f,
                TimelineTimeTopMargin: blend(20f, 16f, compactBlend),
                GroupTitleFont: blend(18f, 15.4f, compactBlend) + ultraWideRelax * 0.4f,
                GroupPaddingRight: blend(16f, 12f, compactBlend),
                GroupPaddingBottom: blend(8f, 6f, compactBlend),
                GroupFlowSpacingX: blend(8f, 6f, compactBlend),
                GroupFlowSpacingY: blend(4f, 3f, compactBlend),
                ToolbarButtonWidth: blend(110f, 94f, compactBlend),
                ToolbarButtonHeight: controlHeight,
                ToolbarButtonCorner: blend(8f, 7f, compactBlend),
                ToolbarButtonFont: blend(16f, 14f, compactBlend) + ultraWideRelax * 0.3f,
                SidebarButtonHeight: blend(36f, 32f, compactBlend),
                SidebarButtonCorner: blend(8f, 7f, compactBlend),
                SidebarButtonFont: blend(16f, 14f, compactBlend) + ultraWideRelax * 0.25f,
                SliderLabelFont: blend(18f, 15.6f, compactBlend) + ultraWideRelax * 0.4f,
                SliderValueFont: blend(18f, 15.8f, compactBlend) + ultraWideRelax * 0.35f,
                SliderBlockSpacing: blend(6f, 5f, compactBlend),
                DetailSliderHeight: blend(16f, 14f, compactBlend),
                CheckboxLabelFont: blend(12f, 11f, compactBlend));
        }

        private static float blend(float normal, float compact, float t)
            => normal + (compact - normal) * t;
    }
}
