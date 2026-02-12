using BeatSight.Game.Screens.SongSelect;
using Xunit;

namespace BeatSight.Tests
{
    public class SongSelectResponsiveLayoutTests
    {
        [Fact]
        public void ScreenMetricsRemainWithinExpectedRangesAtTargetResolutions()
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
                var metrics = SongSelectResponsiveLayout.ComputeScreen(width, height);

                Assert.InRange(metrics.LeftColumnWidth, 280f, 760f);
                Assert.InRange(metrics.HeaderHeight, 82f, 128f);
                Assert.InRange(metrics.HeaderControlHeight, 38f, 52f);
                Assert.InRange(metrics.HeaderContentPadding, 20f, 56f);
                Assert.InRange(metrics.HeaderControlSpacing, 8f, 16f);
                Assert.InRange(metrics.HeaderFilterSpacing, 14f, 29f);
                Assert.InRange(metrics.SearchWidth, 200f, 380f);
                Assert.InRange(metrics.SortWidth, 120f, 200f);
                Assert.InRange(metrics.GenreWidth, 130f, 210f);
                Assert.InRange(metrics.RandomWidth, 84f, 132f);
            }
        }

        [Fact]
        public void DetailsMetricsScaleDownCleanlyForCompactViewports()
        {
            var compact = SongSelectResponsiveLayout.ComputeDetails(1280, 720);
            var full = SongSelectResponsiveLayout.ComputeDetails(1920, 1080);

            Assert.True(compact.PrimaryButtonHeight < full.PrimaryButtonHeight);
            Assert.True(compact.PrimaryButtonWidth <= full.PrimaryButtonWidth);
            Assert.True(compact.BodyFontSize < full.BodyFontSize);
            Assert.True(compact.TitleScale < full.TitleScale);

            Assert.InRange(compact.PrimaryButtonHeight, 42f, 58f);
            Assert.InRange(compact.SecondaryButtonHeight, 34f, 46f);
            Assert.InRange(compact.PrimaryButtonWidth, 176f, 280f);
            Assert.InRange(compact.SecondaryButtonWidth, 152f, 240f);
            Assert.InRange(compact.BodyFontSize, 14f, 18f);
            Assert.InRange(compact.CaptionFontSize, 12f, 16f);
        }

        [Fact]
        public void ScreenMetricsPreserveMinimumRightPaneWidth()
        {
            var resolutions = new (float Width, float Height)[]
            {
                (1280, 720),
                (1366, 768),
                (1600, 900),
                (1920, 1080),
                (2560, 1440),
                (3440, 1440),
            };

            foreach (var (width, height) in resolutions)
            {
                var metrics = SongSelectResponsiveLayout.ComputeScreen(width, height);
                float rightPaneWidth = width - metrics.LeftColumnWidth;
                float minRightWidth = BeatSight.Game.UI.Theming.ResponsiveLayout.ClampFraction(width, 0.45f, 420f, 1100f);

                Assert.True(rightPaneWidth >= minRightWidth - 0.5f,
                    $"Right pane width dropped below minimum at {width}x{height}. Right={rightPaneWidth:0.##}, Min={minRightWidth:0.##}");
            }
        }

        [Fact]
        public void WiderViewportsIncreasePrimaryHeaderControlWidths()
        {
            var narrow = SongSelectResponsiveLayout.ComputeScreen(1280, 720);
            var standard = SongSelectResponsiveLayout.ComputeScreen(1920, 1080);
            var wide = SongSelectResponsiveLayout.ComputeScreen(2560, 1440);

            Assert.True(narrow.SearchWidth <= standard.SearchWidth && standard.SearchWidth <= wide.SearchWidth);
            Assert.True(narrow.SortWidth <= standard.SortWidth && standard.SortWidth <= wide.SortWidth);
            Assert.True(narrow.GenreWidth <= standard.GenreWidth && standard.GenreWidth <= wide.GenreWidth);
            Assert.True(narrow.RandomWidth <= standard.RandomWidth && standard.RandomWidth <= wide.RandomWidth);
        }
    }
}
