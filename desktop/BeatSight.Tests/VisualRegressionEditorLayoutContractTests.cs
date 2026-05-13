using System;
using BeatSight.Tests.VisualRegression;
using Xunit;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Tests
{
    [Collection("VisualRegression")]
    public class VisualRegressionEditorLayoutContractTests
    {
        private const string runVisualTestsEnvVar = "BEATSIGHT_RUN_VISUAL_TESTS";
        private const string sceneFilterEnvVar = "BEATSIGHT_VISUAL_SCENES";

        [Theory]
        [InlineData("Editor")]
        [InlineData("EditorTwoDimensional")]
        [InlineData("EditorManuscript")]
        public void CompactEditorLayoutContractsStayValidAt720p(string sceneName)
        {
            if (!OperatingSystem.IsWindows())
                return;

            if (!shouldRunVisualTests())
                return;

            if (!shouldRunScene(sceneName))
                return;

            var scene = Enum.Parse<VisualScene>(sceneName);
            LiveVisualCaptureRenderer.ValidateScene(scene, 1280, 720);
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

        private static bool shouldRunScene(string sceneName)
        {
            string? raw = Environment.GetEnvironmentVariable(sceneFilterEnvVar);
            if (string.IsNullOrWhiteSpace(raw))
                return true;

            var tokens = raw
                .Split(new[] { ',', ';', '|' }, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(normalizeToken)
                .ToHashSet();

            if (tokens.Count == 0 || tokens.Contains("all") || tokens.Contains("any"))
                return true;

            var aliases = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["editor2d"] = nameof(VisualScene.EditorTwoDimensional),
                ["editorsheet"] = nameof(VisualScene.EditorManuscript)
            };

            string normalizedScene = normalizeToken(sceneName);
            if (tokens.Contains(normalizedScene))
                return true;

            foreach (var alias in aliases)
            {
                if (normalizeToken(alias.Value) == normalizedScene && tokens.Contains(normalizeToken(alias.Key)))
                    return true;
            }

            return false;
        }

        private static string normalizeToken(string value)
            => new string(value.Where(char.IsLetterOrDigit).ToArray()).ToLowerInvariant();
    }
}
