using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osuTK;
using Xunit;

namespace BeatSight.Tests
{
    public class ResponsiveLayoutUtilityTests
    {
        [Fact]
        public void ScaleByWidthClampsToConfiguredBounds()
        {
            Assert.Equal(100f, ResponsiveLayout.ScaleByWidth(100f, 1920f), 0.001f);
            Assert.Equal(75f, ResponsiveLayout.ScaleByWidth(100f, 960f), 0.001f);
            Assert.Equal(135f, ResponsiveLayout.ScaleByWidth(100f, 3840f), 0.001f);
        }

        [Fact]
        public void ScaleByHeightClampsToConfiguredBounds()
        {
            Assert.Equal(64f, ResponsiveLayout.ScaleByHeight(64f, 1080f), 0.001f);
            Assert.Equal(48f, ResponsiveLayout.ScaleByHeight(64f, 540f), 0.001f);
            Assert.Equal(86.4f, ResponsiveLayout.ScaleByHeight(64f, 2160f), 0.001f);
        }

        [Fact]
        public void ScaleByShortSideUsesSmallerViewportAxis()
        {
            var ultraWideViewport = new Vector2(2560f, 720f);
            var portraitViewport = new Vector2(900f, 1600f);

            Assert.Equal(75f, ResponsiveLayout.ScaleByShortSide(100f, ultraWideViewport), 0.001f);
            Assert.Equal(83.33f, ResponsiveLayout.ScaleByShortSide(100f, portraitViewport), 0.01f);
        }

        [Fact]
        public void ClampFractionUsesMinimumForInvalidViewport()
        {
            Assert.Equal(14f, ResponsiveLayout.ClampFraction(0f, 0.25f, 14f, 90f), 0.001f);
            Assert.Equal(14f, ResponsiveLayout.ClampFraction(-1f, 0.25f, 14f, 90f), 0.001f);
            Assert.Equal(90f, ResponsiveLayout.ClampFraction(1000f, 0.25f, 14f, 90f), 0.001f);
        }

        [Fact]
        public void ScalePaddingScalesUniformlyAndClampsScaleRange()
        {
            var source = new MarginPadding { Left = 8, Right = 12, Top = 16, Bottom = 20 };

            var scaledDown = ResponsiveLayout.ScalePadding(source, 0.1f);
            Assert.Equal(4f, scaledDown.Left, 0.001f);
            Assert.Equal(6f, scaledDown.Right, 0.001f);
            Assert.Equal(8f, scaledDown.Top, 0.001f);
            Assert.Equal(10f, scaledDown.Bottom, 0.001f);

            var scaledUp = ResponsiveLayout.ScalePadding(source, 3f);
            Assert.Equal(16f, scaledUp.Left, 0.001f);
            Assert.Equal(24f, scaledUp.Right, 0.001f);
            Assert.Equal(32f, scaledUp.Top, 0.001f);
            Assert.Equal(40f, scaledUp.Bottom, 0.001f);
        }
    }
}
