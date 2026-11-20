using BeatSight.Tests.VisualRegression;
using Xunit;

namespace BeatSight.Tests;

/// <summary>
/// 2026-11-20: live captures render in a window capped at 1920x1080 with the aspect ratio kept, so a large local
/// monitor and CI's virtual display draw the same image. Clamping each axis separately had stretched CI captures.
/// </summary>
public class VisualCaptureWindowSizeTests
{
    [Theory]
    [InlineData(1280, 720, 2560, 1440, 1280, 720)]   // fits: native size
    [InlineData(1920, 1080, 2560, 1440, 1920, 1080)]
    [InlineData(2560, 1440, 2560, 1440, 1920, 1080)] // capped, same aspect
    [InlineData(3440, 1440, 2560, 1440, 1920, 804)]  // ultrawide keeps 43:18
    [InlineData(1280, 720, 1024, 768, 1024, 576)]    // small display: uniform, not 1024x720
    [InlineData(1920, 1080, 1024, 768, 1024, 576)]
    [InlineData(1280, 720, 0, 0, 1280, 720)]         // unknown display bounds
    public void CaptureWindowKeepsAspectWithinCapAndDisplay(int width, int height, int displayWidth, int displayHeight, int expectedWidth, int expectedHeight)
    {
        var (w, h) = LiveVisualCaptureRenderer.captureWindowSize(width, height, displayWidth, displayHeight);
        Assert.Equal(expectedWidth, w);
        Assert.Equal(expectedHeight, h);
    }
}
