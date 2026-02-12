using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.Screens.SongSelect
{
    internal readonly record struct SongSelectScreenLayoutMetrics(
        float LeftColumnWidth,
        float HeaderHeight,
        float HorizontalInset,
        float LeftTopPadding,
        float RightTopPadding,
        float BottomPadding,
        float HeaderControlHeight,
        float HeaderContentPadding,
        float HeaderControlSpacing,
        float HeaderFilterSpacing,
        float HeaderFilterLabelSize,
        float HeaderButtonFontSize,
        float SearchWidth,
        float SortWidth,
        float GenreWidth,
        float RandomWidth);

    internal readonly record struct SongSelectDetailsLayoutMetrics(
        float PrimaryButtonWidth,
        float SecondaryButtonWidth,
        float PrimaryButtonHeight,
        float SecondaryButtonHeight,
        float PrimaryButtonFontSize,
        float SecondaryButtonFontSize,
        float ContentSpacing,
        float TitleScale,
        float ArtistScale,
        float BodyFontSize,
        float CaptionFontSize,
        float HintFontSize);

    internal static class SongSelectResponsiveLayout
    {
        public static SongSelectScreenLayoutMetrics ComputeScreen(float viewportWidth, float viewportHeight)
        {
            float width = viewportWidth > 0 ? viewportWidth : 1920f;
            float height = viewportHeight > 0 ? viewportHeight : 1080f;
            float aspect = width / System.Math.Max(1f, height);
            float ultraWideRelax = System.Math.Clamp((aspect - 2.0f) / 0.9f, 0f, 1f);

            float leftTarget = ResponsiveLayout.ClampFraction(width, 0.3f, 320f, 760f);
            float minRightWidth = ResponsiveLayout.ClampFraction(width, 0.45f, 420f, 1100f);
            leftTarget = System.Math.Clamp(leftTarget, 280f, System.Math.Max(280f, width - minRightWidth));

            float headerHeight = ResponsiveLayout.ClampFraction(height, 0.11f, 82f, 128f);
            float horizontalInset = ResponsiveLayout.ClampFraction(width, 0.02f, 18f, 44f);
            float leftTopPadding = headerHeight + ResponsiveLayout.ClampFraction(height, 0.018f, 10f, 26f);
            float rightTopPadding = headerHeight;
            float bottomPadding = ResponsiveLayout.ClampFraction(height, 0.035f, 24f, 52f);
            float controlHeight = ResponsiveLayout.ClampFraction(height, 0.046f, 38f, 52f);

            return new SongSelectScreenLayoutMetrics(
                leftTarget,
                headerHeight,
                horizontalInset,
                leftTopPadding,
                rightTopPadding,
                bottomPadding,
                controlHeight,
                ResponsiveLayout.ClampFraction(width, 0.02f, 20f, 50f) + ultraWideRelax * 4f,
                ResponsiveLayout.ClampFraction(width, 0.006f, 8f, 14f) + ultraWideRelax * 1.5f,
                ResponsiveLayout.ClampFraction(width, 0.012f, 14f, 26f) + ultraWideRelax * 2f,
                ResponsiveLayout.ClampFraction(height, 0.015f, 13f, 17f) + ultraWideRelax * 0.4f,
                System.Math.Clamp(controlHeight * 0.38f, 14f, 18f),
                ResponsiveLayout.ClampFraction(width, 0.17f, 200f, 380f),
                ResponsiveLayout.ClampFraction(width, 0.085f, 120f, 200f),
                ResponsiveLayout.ClampFraction(width, 0.09f, 130f, 210f),
                ResponsiveLayout.ClampFraction(width, 0.058f, 84f, 132f));
        }

        public static SongSelectDetailsLayoutMetrics ComputeDetails(float viewportWidth, float viewportHeight)
        {
            float width = viewportWidth > 0 ? viewportWidth : 640f;
            float height = viewportHeight > 0 ? viewportHeight : 1080f;
            float aspect = width / System.Math.Max(1f, height);
            float ultraWideRelax = System.Math.Clamp((aspect - 1.8f) / 0.9f, 0f, 1f);

            float primaryHeight = ResponsiveLayout.ClampFraction(height, 0.072f, 42f, 58f);
            float secondaryHeight = ResponsiveLayout.ClampFraction(height, 0.058f, 34f, 46f);
            float primaryWidth = ResponsiveLayout.ClampFraction(width, 0.42f, 176f, 280f);
            float secondaryWidth = ResponsiveLayout.ClampFraction(width, 0.36f, 152f, 240f);
            float compactBlend = System.Math.Clamp((820f - height) / 180f, 0f, 1f);

            return new SongSelectDetailsLayoutMetrics(
                primaryWidth,
                secondaryWidth,
                primaryHeight,
                secondaryHeight,
                System.Math.Clamp(primaryHeight * 0.34f, 14f, 20f) + ultraWideRelax * 0.4f,
                System.Math.Clamp(secondaryHeight * 0.36f, 13f, 18f) + ultraWideRelax * 0.35f,
                blend(10f, 8.2f, compactBlend) + ultraWideRelax * 1.3f,
                blend(1f, 0.92f, compactBlend) + ultraWideRelax * 0.05f,
                blend(1f, 0.94f, compactBlend) + ultraWideRelax * 0.04f,
                blend(16.6f, 14.4f, compactBlend) + ultraWideRelax * 0.7f,
                blend(14.8f, 12.8f, compactBlend) + ultraWideRelax * 0.55f,
                blend(16.8f, 14.2f, compactBlend) + ultraWideRelax * 0.6f);
        }

        private static float blend(float normal, float compact, float t)
            => normal + (compact - normal) * t;
    }
}
