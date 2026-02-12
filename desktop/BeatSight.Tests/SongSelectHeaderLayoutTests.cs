using System;
using System.Reflection;
using BeatSight.Game.Screens.SongSelect;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osuTK;
using Xunit;

namespace BeatSight.Tests
{
    public class SongSelectHeaderLayoutTests
    {
        [Fact]
        public void HeaderPaddingReservesSpaceForBackButton()
        {
            var screen = new SongSelectScreen(editorMode: false);
            var viewport = new Vector2(1280, 720);
            var metrics = SongSelectResponsiveLayout.ComputeScreen(viewport.X, viewport.Y);

            var padding = invokeResolveHeaderPadding(screen, metrics, viewport);

            float fallbackButtonHeight = ResponsiveLayout.ClampFraction(viewport.Y, 0.05f, 38f, 58f);
            float fallbackButtonWidth = Math.Clamp(fallbackButtonHeight * 2.72f, 106f, 156f);
            float clearance = ResponsiveLayout.ClampFraction(viewport.X, 0.008f, 10f, 22f);
            float reservedLeft = BackButton.DefaultMargin.Left + fallbackButtonWidth + clearance;

            Assert.True(padding.Left >= reservedLeft - 0.01f);
            Assert.True(padding.Left >= metrics.HeaderContentPadding);
            Assert.Equal(metrics.HeaderContentPadding, padding.Right, 0.001f);
        }

        [Fact]
        public void HeaderPaddingExpandsWhenViewportBecomesWider()
        {
            var screen = new SongSelectScreen(editorMode: false);
            var narrowViewport = new Vector2(1280, 720);
            var wideViewport = new Vector2(2560, 1440);

            var narrowMetrics = SongSelectResponsiveLayout.ComputeScreen(narrowViewport.X, narrowViewport.Y);
            var wideMetrics = SongSelectResponsiveLayout.ComputeScreen(wideViewport.X, wideViewport.Y);

            var narrowPadding = invokeResolveHeaderPadding(screen, narrowMetrics, narrowViewport);
            var widePadding = invokeResolveHeaderPadding(screen, wideMetrics, wideViewport);

            Assert.True(widePadding.Left >= narrowPadding.Left);
            Assert.True(widePadding.Right >= narrowPadding.Right);
        }

        private static MarginPadding invokeResolveHeaderPadding(SongSelectScreen screen, SongSelectScreenLayoutMetrics metrics, Vector2 viewport)
        {
            var method = typeof(SongSelectScreen).GetMethod("resolveHeaderPadding", BindingFlags.Instance | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException("resolveHeaderPadding method not found.");

            return (MarginPadding)method.Invoke(screen, new object[] { metrics, viewport })!;
        }
    }
}
