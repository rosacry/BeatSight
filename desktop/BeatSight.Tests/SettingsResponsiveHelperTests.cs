using System;
using System.Reflection;
using BeatSight.Game.Screens.Settings;
using Xunit;

namespace BeatSight.Tests
{
    public class SettingsResponsiveHelperTests
    {
        [Fact]
        public void SidebarWidthHelperClampsAcrossViewportSizes()
        {
            float narrow = invokePrivateStatic<float>("getSidebarWidthForViewport", 640f);
            float medium = invokePrivateStatic<float>("getSidebarWidthForViewport", 1366f);
            float wide = invokePrivateStatic<float>("getSidebarWidthForViewport", 3840f);

            Assert.Equal(210f, narrow, 0.001f);
            Assert.InRange(medium, 250f, 270f);
            Assert.Equal(370f, wide, 0.001f);
            Assert.True(narrow <= medium && medium <= wide);
        }

        [Fact]
        public void HeaderHeightHelperClampsAcrossViewportSizes()
        {
            float shortHeight = invokePrivateStatic<float>("getHeaderHeightForViewport", 480f);
            float normalHeight = invokePrivateStatic<float>("getHeaderHeightForViewport", 768f);
            float tallHeight = invokePrivateStatic<float>("getHeaderHeightForViewport", 2160f);

            Assert.Equal(82f, shortHeight, 0.001f);
            Assert.InRange(normalHeight, 84f, 85f);
            Assert.Equal(130f, tallHeight, 0.001f);
            Assert.True(shortHeight <= normalHeight && normalHeight <= tallHeight);
        }

        private static T invokePrivateStatic<T>(string methodName, params object?[] args)
        {
            var method = typeof(SettingsScreen).GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Static)
                ?? throw new InvalidOperationException($"Static method '{methodName}' was not found.");
            return (T)method.Invoke(null, args)!;
        }
    }
}
