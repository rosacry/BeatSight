using BeatSight.Game.Screens.Playback;
using Xunit;

namespace BeatSight.Tests
{
    public class PlaybackResponsiveLayoutTests
    {
        [Fact]
        public void MetricsStayWithinExpectedRangesAcrossTargetResolutions()
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
                var metrics = PlaybackResponsiveLayout.Compute(width, height);

                Assert.InRange(metrics.HeaderStatusFont, 19f, 26f);
                Assert.InRange(metrics.ToolbarButtonHeight, 30f, 34.5f);
                Assert.InRange(metrics.ToolbarButtonWidth, 90f, 112f);
                Assert.InRange(metrics.SidebarButtonHeight, 31f, 36.5f);
                Assert.InRange(metrics.TimelineSliderHeight, 9.5f, 12.5f);
                Assert.InRange(metrics.HeatmapHeight, 7.5f, 10.5f);
                Assert.InRange(metrics.DetailSliderHeight, 13.5f, 16.5f);
            }
        }

        [Fact]
        public void CompactViewportUsesDenserControlsThanFullHd()
        {
            var compact = PlaybackResponsiveLayout.Compute(1280, 720);
            var full = PlaybackResponsiveLayout.Compute(1920, 1080);

            Assert.True(compact.HeaderStatusFont < full.HeaderStatusFont);
            Assert.True(compact.ToolbarButtonHeight < full.ToolbarButtonHeight);
            Assert.True(compact.ToolbarButtonWidth < full.ToolbarButtonWidth);
            Assert.True(compact.SidebarButtonHeight < full.SidebarButtonHeight);
            Assert.True(compact.DetailSliderHeight < full.DetailSliderHeight);
        }

        [Fact]
        public void ManuscriptModeUsesDenserToolbarThanStandardViewAt720p()
        {
            var standard = PlaybackResponsiveLayout.Compute(1280, 720);
            var manuscript = PlaybackResponsiveLayout.Compute(1280, 720, manuscriptMode: true);

            Assert.True(manuscript.ToolbarButtonHeight < standard.ToolbarButtonHeight);
            Assert.True(manuscript.ToolbarButtonWidth < standard.ToolbarButtonWidth);
            Assert.True(manuscript.ToolbarInnerPaddingV < standard.ToolbarInnerPaddingV);
            Assert.True(manuscript.PlaybackRowSpacingY < standard.PlaybackRowSpacingY);
            Assert.True(manuscript.ToolbarSectionSpacing < standard.ToolbarSectionSpacing);
        }

        [Fact]
        public void ToolbarButtonTypographyFitsButtonHeight()
        {
            var resolutions = new (float Width, float Height)[]
            {
                (1280, 720),
                (1920, 1080),
                (3440, 1440),
            };

            foreach (var (width, height) in resolutions)
            {
                var metrics = PlaybackResponsiveLayout.Compute(width, height);
                Assert.True(metrics.ToolbarButtonFont < metrics.ToolbarButtonHeight);
                Assert.True(metrics.SidebarButtonFont < metrics.SidebarButtonHeight);
                Assert.True(metrics.SliderValueFont <= metrics.HeaderStatusFont);
            }
        }
    }
}
