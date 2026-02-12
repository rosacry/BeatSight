using BeatSight.Game.Screens;
using Xunit;

namespace BeatSight.Tests
{
    public class MainMenuResponsiveLayoutTests
    {
        [Fact]
        public void MetricsRemainStableAcrossTargetResolutions()
        {
            var resolutions = new (float Width, float Height)[]
            {
                (1280, 720),
                (1920, 1080),
                (2560, 1440),
                (3440, 1440),
            };

            foreach (var (width, height) in resolutions)
            {
                var metrics = MainMenuResponsiveLayout.Compute(width, height);

                Assert.InRange(metrics.LogoTitleSize, 56f, 84f);
                Assert.InRange(metrics.LogoSubtitleSize, 16f, 27f);
                Assert.InRange(metrics.ButtonFlowSpacing, 16f, 33f);
                Assert.InRange(metrics.LogoY, -230f, -130f);
                Assert.InRange(metrics.IntroCircleSize, 58f, 88f);
                Assert.InRange(metrics.IntroApproachCircleSize, 150f, 220f);
            }
        }

        [Fact]
        public void IntroGeometryMaintainsVisualHierarchy()
        {
            var resolutions = new (float Width, float Height)[]
            {
                (1280, 720),
                (1920, 1080),
                (3440, 1440),
            };

            foreach (var (width, height) in resolutions)
            {
                var metrics = MainMenuResponsiveLayout.Compute(width, height);
                Assert.True(metrics.IntroApproachCircleSize > metrics.IntroCircleSize);
                Assert.True(metrics.IntroCircleSize > metrics.IntroInnerDotSize);
                Assert.True(metrics.IntroCircleBorderThickness > 0);
            }
        }

        [Fact]
        public void CompactViewportReducesTitleAndSpacing()
        {
            var compact = MainMenuResponsiveLayout.Compute(1280, 720);
            var full = MainMenuResponsiveLayout.Compute(1920, 1080);

            Assert.True(compact.LogoTitleSize <= full.LogoTitleSize);
            Assert.True(compact.LogoSubtitleSize <= full.LogoSubtitleSize);
            Assert.True(compact.ButtonFlowSpacing <= full.ButtonFlowSpacing);
        }
    }
}
