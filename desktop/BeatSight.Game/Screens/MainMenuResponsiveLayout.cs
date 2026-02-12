using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.Screens
{
    internal readonly record struct MainMenuResponsiveLayoutMetrics(
        float LogoTitleSize,
        float LogoSubtitleSize,
        float LogoSubtitleY,
        float LogoSubtitleSpacing,
        float LogoY,
        float SubtitleToButtonsGap,
        float ButtonFlowSpacing,
        float ButtonFlowMinY,
        float ButtonFlowMaxY,
        float IntroBootFontSize,
        float IntroBootSpacing,
        float IntroBootMarginX,
        float IntroBootMarginY,
        float IntroScannerHeight,
        float IntroCircleSize,
        float IntroApproachCircleSize,
        float IntroCircleBorderThickness,
        float IntroInnerDotSize);

    internal static class MainMenuResponsiveLayout
    {
        public static MainMenuResponsiveLayoutMetrics Compute(float viewportWidth, float viewportHeight)
        {
            float width = viewportWidth > 0 ? viewportWidth : 1920f;
            float height = viewportHeight > 0 ? viewportHeight : 1080f;
            float shortSide = System.Math.Min(width, height);
            float aspect = width / System.Math.Max(1f, height);

            float compactBlend = System.Math.Clamp((820f - height) / 220f, 0f, 1f);
            float ultraWideRelax = System.Math.Clamp((aspect - 2.0f) / 0.8f, 0f, 1f);

            float titleSize = ResponsiveLayout.ClampFraction(height, 0.074f, 56f, 82f) + ultraWideRelax * 1.4f;
            float subtitleSize = ResponsiveLayout.ClampFraction(height, 0.024f, 16f, 26f) + ultraWideRelax * 0.35f;
            float subtitleY = ResponsiveLayout.ClampFraction(height, 0.081f, 54f, 94f);
            float subtitleSpacing = blend(5f, 3.2f, compactBlend) + ultraWideRelax * 0.45f;

            return new MainMenuResponsiveLayoutMetrics(
                titleSize,
                subtitleSize,
                subtitleY,
                subtitleSpacing,
                -ResponsiveLayout.ClampFraction(height, 0.17f, 130f, 230f),
                ResponsiveLayout.ClampFraction(height, 0.065f, 44f, 90f),
                ResponsiveLayout.ClampFraction(height, 0.023f, 16f, 32f),
                ResponsiveLayout.ClampFraction(height, 0.12f, 86f, 190f),
                ResponsiveLayout.ClampFraction(height, 0.23f, 160f, 320f),
                ResponsiveLayout.ClampFraction(height, 0.0135f, 10f, 15f),
                ResponsiveLayout.ClampFraction(height, 0.0064f, 3f, 6f),
                ResponsiveLayout.ClampFraction(width, 0.0115f, 12f, 24f),
                ResponsiveLayout.ClampFraction(height, 0.017f, 12f, 22f),
                ResponsiveLayout.ClampFraction(height, 0.0021f, 1f, 3f),
                ResponsiveLayout.ClampFraction(shortSide, 0.096f, 58f, 88f),
                ResponsiveLayout.ClampFraction(shortSide, 0.245f, 150f, 220f),
                ResponsiveLayout.ClampFraction(shortSide, 0.0046f, 2f, 4.5f),
                ResponsiveLayout.ClampFraction(shortSide, 0.011f, 8f, 12f));
        }

        private static float blend(float normal, float compact, float t)
            => normal + (compact - normal) * t;
    }
}
