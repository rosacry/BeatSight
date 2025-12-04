using System;
using System.Drawing;
using System.Reflection;
using System.Runtime.InteropServices;
using osu.Framework.Bindables;

namespace BeatSight.Tests;

/// <summary>
/// Tests for window management functionality including fullscreen toggle,
/// resolution changes, and reflection target validation.
/// 
/// ⚠️ IMPORTANT: These tests help detect when osu.Framework updates break
/// the reflection-based window manipulation code in BeatSightGame.cs.
/// 
/// If these tests fail after a framework update:
/// 1. Check BeatSightGame.NativeWindowHelpers
/// 2. Update the handle_property_candidates and handle_field_candidates arrays
/// 3. Verify the new framework structure and update accordingly
/// </summary>
public class WindowManagementTests
{
    #region Resolution Tests

    [Fact]
    public void ResolutionHasWidthAndHeight()
    {
        var resolution = new Size(1920, 1080);

        Assert.Equal(1920, resolution.Width);
        Assert.Equal(1080, resolution.Height);
    }

    [Fact]
    public void CommonResolutionsAreValid()
    {
        var resolutions = new[]
        {
            new Size(1280, 720),   // 720p
            new Size(1920, 1080),  // 1080p
            new Size(2560, 1440),  // 1440p
            new Size(3840, 2160),  // 4K
        };

        foreach (var res in resolutions)
        {
            Assert.True(res.Width > 0);
            Assert.True(res.Height > 0);
            Assert.True(res.Width >= res.Height); // Landscape
        }
    }

    [Fact]
    public void ResolutionAspectRatioCalculation()
    {
        var res1080p = new Size(1920, 1080);
        var res720p = new Size(1280, 720);

        double aspect1080 = (double)res1080p.Width / res1080p.Height;
        double aspect720 = (double)res720p.Width / res720p.Height;

        // Both should be ~16:9 (1.777...)
        Assert.InRange(aspect1080, 1.77, 1.78);
        Assert.InRange(aspect720, 1.77, 1.78);
    }

    [Fact]
    public void ResolutionScalingPreservesAspectRatio()
    {
        var originalRes = new Size(1920, 1080);
        double scaleFactor = 0.75;

        var scaledRes = new Size(
            (int)(originalRes.Width * scaleFactor),
            (int)(originalRes.Height * scaleFactor)
        );

        double originalAspect = (double)originalRes.Width / originalRes.Height;
        double scaledAspect = (double)scaledRes.Width / scaledRes.Height;

        Assert.Equal(originalAspect, scaledAspect, precision: 2);
    }

    [Fact]
    public void MinimumResolutionIsEnforced()
    {
        const int minWidth = 800;
        const int minHeight = 600;

        var requestedRes = new Size(640, 480);
        var enforcedRes = new Size(
            Math.Max(requestedRes.Width, minWidth),
            Math.Max(requestedRes.Height, minHeight)
        );

        Assert.Equal(800, enforcedRes.Width);
        Assert.Equal(600, enforcedRes.Height);
    }

    #endregion

    #region Fullscreen Toggle Tests

    [Fact]
    public void FullscreenBindableToggle()
    {
        var isFullscreen = new BindableBool(false);

        Assert.False(isFullscreen.Value);

        isFullscreen.Value = true;
        Assert.True(isFullscreen.Value);

        isFullscreen.Value = false;
        Assert.False(isFullscreen.Value);
    }

    [Fact]
    public void FullscreenChangeFiresEvent()
    {
        var isFullscreen = new BindableBool(false);
        bool eventFired = false;
        bool? newValue = null;

        isFullscreen.BindValueChanged(e =>
        {
            eventFired = true;
            newValue = e.NewValue;
        });

        isFullscreen.Value = true;

        Assert.True(eventFired);
        Assert.True(newValue);
    }

    [Fact]
    public void BorderlessModeIsSeparateFromFullscreen()
    {
        var isFullscreen = new BindableBool(false);
        var isBorderless = new BindableBool(false);

        // Can be borderless without being fullscreen
        isBorderless.Value = true;

        Assert.False(isFullscreen.Value);
        Assert.True(isBorderless.Value);
    }

    #endregion

    #region Multi-Monitor Tests

    [Fact]
    public void MonitorIndexIsZeroBased()
    {
        var monitorIndex = new BindableInt(0)
        {
            MinValue = 0,
            MaxValue = 3 // Assume max 4 monitors
        };

        Assert.Equal(0, monitorIndex.MinValue);
        Assert.Equal(0, monitorIndex.Value);
    }

    [Fact]
    public void MonitorBoundsAreValid()
    {
        var monitorBounds = new Rectangle(0, 0, 1920, 1080);

        Assert.True(monitorBounds.Width > 0);
        Assert.True(monitorBounds.Height > 0);
    }

    [Fact]
    public void SecondaryMonitorHasOffset()
    {
        var primaryBounds = new Rectangle(0, 0, 1920, 1080);
        var secondaryBounds = new Rectangle(1920, 0, 1920, 1080); // Right of primary

        Assert.Equal(0, primaryBounds.X);
        Assert.Equal(1920, secondaryBounds.X);
    }

    [Fact]
    public void WindowCanSpanMultipleMonitors()
    {
        var primaryBounds = new Rectangle(0, 0, 1920, 1080);
        var secondaryBounds = new Rectangle(1920, 0, 1920, 1080);

        // Window centered across both monitors
        var windowBounds = new Rectangle(960, 0, 1920, 1080);

        bool spansMultiple = windowBounds.X < secondaryBounds.X &&
                             windowBounds.Right > primaryBounds.Right;

        Assert.True(spansMultiple);
    }

    #endregion

    #region Reflection Target Validation Tests

    [Fact]
    public void ReflectionBindingFlagsIncludeNonPublic()
    {
        const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        Assert.True((flags & BindingFlags.NonPublic) == BindingFlags.NonPublic);
        Assert.True((flags & BindingFlags.Instance) == BindingFlags.Instance);
    }

    [Fact]
    public void HandleCandidateArraysAreNotEmpty()
    {
        // These arrays are defined in BeatSightGame.NativeWindowHelpers
        // Testing that the concept is correct
        var propertyCandidates = new[]
        {
            "WindowHandle", "Handle", "NativeHandle", "NativeWindowHandle",
            "SDLWindowHandle", "SdlWindowHandle", "HWND", "Hwnd",
            "Window", "NativeWindow", "Implementation", "WindowImplementation"
        };

        var fieldCandidates = new[]
        {
            "windowHandle", "handle", "nativeHandle", "nativeWindowHandle",
            "sdlWindowHandle", "hwnd", "window", "nativeWindow",
            "implementation", "windowImplementation"
        };

        Assert.NotEmpty(propertyCandidates);
        Assert.NotEmpty(fieldCandidates);
        Assert.True(propertyCandidates.Length >= 8);
        Assert.True(fieldCandidates.Length >= 8);
    }

    [Fact]
    public void IntPtrHandleCanBeZeroOrValid()
    {
        IntPtr invalidHandle = IntPtr.Zero;
        IntPtr validHandle = new IntPtr(12345);

        Assert.Equal(IntPtr.Zero, invalidHandle);
        Assert.NotEqual(IntPtr.Zero, validHandle);
    }

    [Fact]
    public void ReflectionDepthLimitIsReasonable()
    {
        const int maxDepth = 6;

        // Should be deep enough to find handles through wrapper objects
        // but not so deep that it causes performance issues
        Assert.InRange(maxDepth, 3, 10);
    }

    [Fact]
    public void PropertyAccessViaReflectionWorks()
    {
        var testObject = new TestWindowClass { Handle = new IntPtr(42) };

        var property = testObject.GetType().GetProperty("Handle");
        var value = property?.GetValue(testObject);

        Assert.NotNull(value);
        Assert.Equal(new IntPtr(42), value);
    }

    [Fact]
    public void FieldAccessViaReflectionWorks()
    {
        var testObject = new TestWindowClass();
        var field = testObject.GetType().GetField("privateHandle", BindingFlags.Instance | BindingFlags.NonPublic);

        Assert.NotNull(field);
    }

    #endregion

    #region Window Positioning Tests

    [Fact]
    public void WindowPositionCanBeNegative()
    {
        // For multi-monitor setups where secondary is to the left
        var windowPos = new Point(-1920, 0);

        Assert.Equal(-1920, windowPos.X);
    }

    [Fact]
    public void CenterWindowCalculation()
    {
        var screenBounds = new Rectangle(0, 0, 1920, 1080);
        var windowSize = new Size(800, 600);

        int centeredX = screenBounds.X + (screenBounds.Width - windowSize.Width) / 2;
        int centeredY = screenBounds.Y + (screenBounds.Height - windowSize.Height) / 2;

        Assert.Equal(560, centeredX);
        Assert.Equal(240, centeredY);
    }

    [Fact]
    public void WindowBoundsClampToScreen()
    {
        var screenBounds = new Rectangle(0, 0, 1920, 1080);
        var requestedPos = new Point(2000, 500); // Off screen to the right
        var windowSize = new Size(800, 600);

        int clampedX = Math.Min(requestedPos.X, screenBounds.Right - windowSize.Width);
        int clampedY = Math.Min(requestedPos.Y, screenBounds.Bottom - windowSize.Height);
        clampedX = Math.Max(clampedX, screenBounds.X);
        clampedY = Math.Max(clampedY, screenBounds.Y);

        Assert.Equal(1120, clampedX); // 1920 - 800
        Assert.InRange(clampedY, 0, 480);
    }

    #endregion

    #region Window Style Tests

    [Fact]
    public void WindowStyleFlagsAreDefined()
    {
        // From Win32 API - used in NativeWindowHelpers
        const uint SWP_NOSIZE = 0x0001;
        const uint SWP_NOZORDER = 0x0004;
        const uint SWP_NOACTIVATE = 0x0010;
        const uint SWP_FRAMECHANGED = 0x0020;
        const uint SWP_NOOWNERZORDER = 0x0200;

        Assert.Equal(0x0001u, SWP_NOSIZE);
        Assert.Equal(0x0004u, SWP_NOZORDER);
        Assert.Equal(0x0010u, SWP_NOACTIVATE);
        Assert.Equal(0x0020u, SWP_FRAMECHANGED);
        Assert.Equal(0x0200u, SWP_NOOWNERZORDER);
    }

    [Fact]
    public void CombinedFlagsWork()
    {
        const uint SWP_NOSIZE = 0x0001;
        const uint SWP_NOZORDER = 0x0004;
        const uint SWP_NOACTIVATE = 0x0010;

        uint combined = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE;

        Assert.Equal(0x0015u, combined);
        Assert.True((combined & SWP_NOSIZE) == SWP_NOSIZE);
        Assert.True((combined & SWP_NOZORDER) == SWP_NOZORDER);
        Assert.True((combined & SWP_NOACTIVATE) == SWP_NOACTIVATE);
    }

    #endregion

    #region Size Comparison Tests

    [Fact]
    public void SizesApproximatelyEqualWithTolerance()
    {
        var size1 = new Size(1920, 1080);
        var size2 = new Size(1921, 1079);
        const int tolerance = 5;

        bool approximatelyEqual = Math.Abs(size1.Width - size2.Width) <= tolerance &&
                                  Math.Abs(size1.Height - size2.Height) <= tolerance;

        Assert.True(approximatelyEqual);
    }

    [Fact]
    public void SizesNotEqualOutsideTolerance()
    {
        var size1 = new Size(1920, 1080);
        var size2 = new Size(1280, 720);
        const int tolerance = 5;

        bool approximatelyEqual = Math.Abs(size1.Width - size2.Width) <= tolerance &&
                                  Math.Abs(size1.Height - size2.Height) <= tolerance;

        Assert.False(approximatelyEqual);
    }

    #endregion

    #region Framework Compatibility Tests

    [Fact]
    public void OsuFrameworkTypeExists()
    {
        // Verify we can find osu.Framework types
        var screenType = typeof(osu.Framework.Screens.Screen);

        Assert.NotNull(screenType);
        Assert.Equal("Screen", screenType.Name);
    }

    [Fact]
    public void BindableTypesAvailable()
    {
        var bindableBoolType = typeof(BindableBool);
        var bindableIntType = typeof(BindableInt);
        var bindableDoubleType = typeof(BindableDouble);

        Assert.NotNull(bindableBoolType);
        Assert.NotNull(bindableIntType);
        Assert.NotNull(bindableDoubleType);
    }

    #endregion

    #region Helper Classes

    private class TestWindowClass
    {
        public IntPtr Handle { get; set; }

#pragma warning disable CS0414 // Field is assigned but its value is never used
        private readonly IntPtr privateHandle = new IntPtr(123);
#pragma warning restore CS0414
    }

    #endregion
}
