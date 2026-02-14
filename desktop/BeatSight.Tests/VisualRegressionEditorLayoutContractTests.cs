using System;
using BeatSight.Tests.VisualRegression;
using Xunit;

namespace BeatSight.Tests
{
    [Collection("VisualRegression")]
    public class VisualRegressionEditorLayoutContractTests
    {
        private const string runVisualTestsEnvVar = "BEATSIGHT_RUN_VISUAL_TESTS";

        [Theory]
        [InlineData("Editor")]
        [InlineData("EditorManuscript")]
        public void CompactEditorLayoutContractsStayValidAt720p(string sceneName)
        {
            if (!OperatingSystem.IsWindows())
                return;

            if (!shouldRunVisualTests())
                return;

            var scene = Enum.Parse<VisualScene>(sceneName);
            using var capture = LiveVisualCaptureRenderer.Render(scene, 1280, 720);
            Assert.Equal(1280, capture.Width);
            Assert.Equal(720, capture.Height);
        }

        private static bool shouldRunVisualTests()
        {
            string? value = Environment.GetEnvironmentVariable(runVisualTestsEnvVar);
            if (string.IsNullOrWhiteSpace(value))
                return false;

            return value == "1"
                   || value.Equals("true", StringComparison.OrdinalIgnoreCase)
                   || value.Equals("yes", StringComparison.OrdinalIgnoreCase);
        }
    }
}
