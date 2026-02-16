using BeatSight.Game.Screens.Editor;
using Xunit;

namespace BeatSight.Tests
{
    public class EditorResponsiveLayoutTests
    {
        [Fact]
        public void RequestedResolutionSweepProducesStableLayoutMetrics()
        {
            var resolutions = new (float Width, float Height, bool ExpectStacked)[]
            {
                (1280, 720, true),
                (1366, 768, false),
                (1920, 1080, false),
                (2560, 1440, false),
                (3440, 1440, false),
            };

            foreach (var resolution in resolutions)
            {
                var metrics = EditorResponsiveLayout.Compute(resolution.Width, resolution.Height, currentlyStacked: false);
                Assert.Equal(resolution.ExpectStacked, metrics.UseStackedInspector);

                Assert.InRange(metrics.InspectorWidth, 360f, 540f);
                Assert.InRange(metrics.TimelineTopHeight, 180f, 320f);
                Assert.InRange(metrics.TimelineToolboxHeight, 78f, 136f);
                Assert.InRange(metrics.FooterHeight, 52f, 112f);
                Assert.InRange(metrics.PanelGap, 8f, 14f);
                Assert.InRange(metrics.StackedInspectorHeight, 168f, 320f);

                if (!metrics.UseStackedInspector)
                {
                    float previewWidth = resolution.Width - metrics.InspectorWidth - metrics.PanelGap;
                    Assert.True(previewWidth >= 700f, $"Preview area too narrow at {resolution.Width}x{resolution.Height}: {previewWidth:0.##}.");
                }
            }
        }

        [Fact]
        public void InspectorStackingUsesHysteresisAroundThresholds()
        {
            bool stacked = false;

            stacked = EditorResponsiveLayout.Compute(1300, 720, stacked).UseStackedInspector;
            Assert.True(stacked);

            stacked = EditorResponsiveLayout.Compute(1370, 768, stacked).UseStackedInspector;
            Assert.True(stacked);

            stacked = EditorResponsiveLayout.Compute(1460, 860, stacked).UseStackedInspector;
            Assert.False(stacked);
        }

        [Fact]
        public void CompactViewportUsesTighterBottomChromeBudgetAt720p()
        {
            var compact = EditorResponsiveLayout.Compute(1280, 720, currentlyStacked: false);
            var full = EditorResponsiveLayout.Compute(1920, 1080, currentlyStacked: false);

            Assert.True(compact.UseStackedInspector);
            Assert.True(compact.FooterHeight < full.FooterHeight);
            Assert.True(compact.TimelineToolboxHeight < full.TimelineToolboxHeight);
            Assert.True(compact.StackedInspectorHeight <= 185f, $"Expected compact stacked inspector cap around 720p, got {compact.StackedInspectorHeight:0.##}.");
            Assert.True(compact.FooterHeight <= 62f, $"Expected compact footer cap around 720p, got {compact.FooterHeight:0.##}.");
        }

        [Fact]
        public void VerticalBudgetLeavesRoomForPreviewAndInspectorContent()
        {
            var resolutions = new (float Width, float Height)[]
            {
                (1280, 720),
                (1366, 768),
                (1920, 1080),
                (2560, 1440),
            };

            foreach (var (width, height) in resolutions)
            {
                var metrics = EditorResponsiveLayout.Compute(width, height, currentlyStacked: false);
                float consumedHeight = metrics.TimelineTopHeight + metrics.TimelineToolboxHeight + metrics.FooterHeight + metrics.PanelGap * 2f;
                float remainingHeight = height - consumedHeight;
                float minimumWorkspaceHeight = metrics.UseStackedInspector ? 200f : 260f;

                Assert.True(remainingHeight >= minimumWorkspaceHeight,
                    $"Editor workspace too short at {width}x{height}. Remaining={remainingHeight:0.##}, Min={minimumWorkspaceHeight:0.##}");
            }
        }

        [Fact]
        public void UnstackedLayoutKeepsPreviewWiderThanInspector()
        {
            var resolutions = new (float Width, float Height)[]
            {
                (1366, 768),
                (1920, 1080),
                (2560, 1440),
                (3440, 1440),
            };

            foreach (var (width, height) in resolutions)
            {
                var metrics = EditorResponsiveLayout.Compute(width, height, currentlyStacked: false);
                if (metrics.UseStackedInspector)
                    continue;

                float previewWidth = width - metrics.InspectorWidth - metrics.PanelGap;
                Assert.True(previewWidth > metrics.InspectorWidth,
                    $"Preview became narrower than inspector at {width}x{height}. Preview={previewWidth:0.##}, Inspector={metrics.InspectorWidth:0.##}");
            }
        }
    }
}
