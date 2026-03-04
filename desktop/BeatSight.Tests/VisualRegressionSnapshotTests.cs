using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using BeatSight.Tests.VisualRegression;
using Xunit.Sdk;
using System.Collections.Generic;
using System.Linq;

namespace BeatSight.Tests
{
    [Collection("VisualRegression")]
    public class VisualRegressionSnapshotTests
    {
        private readonly record struct VisualThresholds(double MaxChangedPixelRatio, double MaxMeanDelta);
        private readonly record struct VisualProfileSelection(
            IReadOnlySet<VisualScene> Scenes,
            IReadOnlySet<VisualResolution> Resolutions);

        private const string updateBaselinesEnvVar = "BEATSIGHT_UPDATE_VISUAL_BASELINES";
        private const string runVisualTestsEnvVar = "BEATSIGHT_RUN_VISUAL_TESTS";
        private const string sceneFilterEnvVar = "BEATSIGHT_VISUAL_SCENES";
        private const string resolutionFilterEnvVar = "BEATSIGHT_VISUAL_RESOLUTIONS";
        private const string profileEnvVar = "BEATSIGHT_VISUAL_PROFILE";
        private const int maxCompareCaptureAttempts = 3;
        private const int maxUpdateCaptureAttempts = 4;

        public static IEnumerable<object[]> SnapshotCases()
        {
            var scenes = resolveSelectedScenes();
            var resolutions = resolveSelectedResolutions();

            foreach (var scene in scenes)
            {
                foreach (var resolution in resolutions)
                {
                    yield return new object[]
                    {
                        scene.ToString(),
                        resolution.Name,
                        resolution.Width,
                        resolution.Height
                    };
                }
            }
        }

        [Theory]
        [MemberData(nameof(SnapshotCases))]
        public void ResponsiveSnapshotMatchesBaseline(string sceneName, string resolutionName, int width, int height)
        {
            if (!OperatingSystem.IsWindows())
                return;

            if (!shouldRunVisualTests())
                return;

            var scene = Enum.Parse<VisualScene>(sceneName);
            bool updateBaselines = shouldUpdateBaselines();

            string baselineRoot = Path.Combine(
                TestPathResolver.ResolveRepositoryRoot(),
                "desktop",
                "BeatSight.Tests",
                "VisualBaselines");

            Directory.CreateDirectory(baselineRoot);
            string baselinePath = Path.Combine(baselineRoot, $"{sceneName}-{resolutionName}.png");

            if (updateBaselines)
            {
                using var baselineCapture = captureStableBaseline(scene, width, height);
                baselineCapture.SaveAsPng(baselinePath);
                return;
            }

            Assert.True(File.Exists(baselinePath),
                $"Baseline missing: {baselinePath}. Set {updateBaselinesEnvVar}=1 and run this test to generate snapshots.");

            using var expected = Image.Load<Rgba32>(baselinePath);
            VisualThresholds thresholds = getThresholds(scene);
            VisualDiffResult? bestResult = null;
            Image<Rgba32>? bestActual = null;
            Image<Rgba32>? bestDiff = null;

            for (int attempt = 1; attempt <= maxCompareCaptureAttempts; attempt++)
            {
                using var attemptActual = LiveVisualCaptureRenderer.Render(scene, width, height);
                VisualDiffResult result = VisualDiffComparer.Compare(expected, attemptActual, out var diff);
                using (diff)
                {
                    if (isWithinThresholds(result, thresholds))
                    {
                        bestActual?.Dispose();
                        bestDiff?.Dispose();
                        return;
                    }

                    bool replaceBest = !bestResult.HasValue
                                       || result.ChangedPixelRatio < bestResult.Value.ChangedPixelRatio
                                       || (Math.Abs(result.ChangedPixelRatio - bestResult.Value.ChangedPixelRatio) < 0.0000001
                                           && result.MeanDelta < bestResult.Value.MeanDelta);

                    if (!replaceBest)
                        continue;

                    bestActual?.Dispose();
                    bestDiff?.Dispose();
                    bestActual = attemptActual.Clone();
                    bestDiff = diff.Clone();
                    bestResult = result;
                }
            }

            Assert.True(bestResult.HasValue, "Visual comparison did not produce a result.");
            Assert.NotNull(bestActual);
            Assert.NotNull(bestDiff);

            using (bestActual)
            using (bestDiff)
            {
                string artifactRoot = Path.Combine(
                    TestPathResolver.ResolveRepositoryRoot(),
                    "desktop",
                    "BeatSight.Tests",
                    "TestResults",
                    "visual-diff");
                Directory.CreateDirectory(artifactRoot);

                string prefix = $"{sceneName}-{resolutionName}";
                string actualPath = Path.Combine(artifactRoot, $"{prefix}.actual.png");
                string diffPath = Path.Combine(artifactRoot, $"{prefix}.diff.png");

                bestActual.SaveAsPng(actualPath);
                bestDiff.SaveAsPng(diffPath);

                string sizeHint = $"{width}x{height}";
                if (!string.IsNullOrWhiteSpace(bestResult.Value.ErrorMessage))
                {
                    throw new XunitException(
                        $"Visual regression failed for {sceneName} @ {sizeHint} after {maxCompareCaptureAttempts} capture attempts: {bestResult.Value.ErrorMessage}." +
                        $"{Environment.NewLine}Actual: {actualPath}" +
                        $"{Environment.NewLine}Diff: {diffPath}");
                }

                throw new XunitException(
                    $"Visual regression failed for {sceneName} @ {sizeHint} after {maxCompareCaptureAttempts} capture attempts." +
                    $"{Environment.NewLine}Changed pixels: {bestResult.Value.ChangedPixels}/{bestResult.Value.TotalPixels} ({bestResult.Value.ChangedPixelRatio:P6})" +
                    $"{Environment.NewLine}Mean delta: {bestResult.Value.MeanDelta:F8}" +
                    $"{Environment.NewLine}Thresholds => changed ratio <= {thresholds.MaxChangedPixelRatio:P6}, mean delta <= {thresholds.MaxMeanDelta:F8}" +
                    $"{Environment.NewLine}Actual: {actualPath}" +
                    $"{Environment.NewLine}Diff: {diffPath}");
            }
        }

        private static bool isWithinThresholds(VisualDiffResult result, VisualThresholds thresholds)
        {
            if (!string.IsNullOrWhiteSpace(result.ErrorMessage))
                return false;

            return result.ChangedPixelRatio <= thresholds.MaxChangedPixelRatio
                   && result.MeanDelta <= thresholds.MaxMeanDelta;
        }

        private static VisualThresholds getThresholds(VisualScene scene)
        {
            return scene switch
            {
                // Song select in editor mode has small persistent text rasterisation jitter
                // in live host capture. Keep tolerance narrowly above measured drift.
                VisualScene.SongSelectEditor => new VisualThresholds(0.010, 0.0013),
                // Settings has minor persistent hover/tooltip variance in live host capture.
                // Keep this scoped to settings only so other scenes remain strict.
                VisualScene.Settings => new VisualThresholds(0.018, 0.0019),
                _ => new VisualThresholds(
                    VisualDiffComparer.DefaultMaxChangedPixelRatio,
                    VisualDiffComparer.DefaultMaxMeanDelta)
            };
        }

        private static bool shouldUpdateBaselines()
        {
            string? value = Environment.GetEnvironmentVariable(updateBaselinesEnvVar);
            if (string.IsNullOrWhiteSpace(value))
                return false;

            return value == "1"
                   || value.Equals("true", StringComparison.OrdinalIgnoreCase)
                   || value.Equals("yes", StringComparison.OrdinalIgnoreCase);
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

        private static Image<Rgba32> captureStableBaseline(VisualScene scene, int width, int height)
        {
            VisualThresholds thresholds = getThresholds(scene);
            Image<Rgba32>? bestCapture = null;
            double bestScore = double.MaxValue;

            for (int attempt = 1; attempt <= maxUpdateCaptureAttempts; attempt++)
            {
                using var capture = LiveVisualCaptureRenderer.Render(scene, width, height);

                if (bestCapture == null)
                {
                    bestCapture = capture.Clone();
                    continue;
                }

                VisualDiffResult result = VisualDiffComparer.Compare(bestCapture, capture, out var diff);
                diff.Dispose();

                double stabilityScore = result.ChangedPixelRatio + result.MeanDelta;
                if (stabilityScore < bestScore)
                    bestScore = stabilityScore;

                // If two consecutive captures are already very close, accept the newest frame.
                if (result.ChangedPixelRatio <= Math.Max(thresholds.MaxChangedPixelRatio, 0.01)
                    && result.MeanDelta <= Math.Max(thresholds.MaxMeanDelta, 0.0015))
                {
                    bestCapture.Dispose();
                    bestCapture = capture.Clone();
                    return bestCapture;
                }

                bestCapture.Dispose();
                bestCapture = capture.Clone();
            }

            if (bestCapture == null)
                throw new XunitException($"Could not capture baseline for {scene} at {width}x{height}.");

            return bestCapture;
        }

        private static IReadOnlyList<VisualScene> resolveSelectedScenes()
        {
            HashSet<VisualScene>? filtered = null;
            var profile = resolveProfileSelection();

            var sceneTokens = readTokenList(sceneFilterEnvVar);
            if (sceneTokens.Count > 0)
                filtered = parseSceneFilter(sceneTokens);
            else if (profile != null)
                filtered = new HashSet<VisualScene>(profile.Value.Scenes);

            var selected = filtered == null
                ? VisualSnapshotCatalog.Scenes
                : VisualSnapshotCatalog.Scenes.Where(filtered.Contains).ToArray();

            if (selected.Length == 0)
                throw new InvalidOperationException("Visual scene filter resolved to zero scenes.");

            return selected;
        }

        private static IReadOnlyList<VisualResolution> resolveSelectedResolutions()
        {
            HashSet<VisualResolution>? filtered = null;
            var profile = resolveProfileSelection();

            var resolutionTokens = readTokenList(resolutionFilterEnvVar);
            if (resolutionTokens.Count > 0)
                filtered = parseResolutionFilter(resolutionTokens);
            else if (profile != null)
                filtered = new HashSet<VisualResolution>(profile.Value.Resolutions);

            var selected = filtered == null
                ? VisualSnapshotCatalog.Resolutions
                : VisualSnapshotCatalog.Resolutions.Where(filtered.Contains).ToArray();

            if (selected.Length == 0)
                throw new InvalidOperationException("Visual resolution filter resolved to zero resolutions.");

            return selected;
        }

        private static IReadOnlyList<string> readTokenList(string envVar)
        {
            string? raw = Environment.GetEnvironmentVariable(envVar);
            if (string.IsNullOrWhiteSpace(raw))
                return Array.Empty<string>();

            return raw
                .Split(new[] { ',', ';', '|' }, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .ToArray();
        }

        private static HashSet<VisualScene> parseSceneFilter(IReadOnlyList<string> tokens)
        {
            if (tokens.Any(isAllToken))
                return new HashSet<VisualScene>(VisualSnapshotCatalog.Scenes);

            var map = VisualSnapshotCatalog.Scenes.ToDictionary(
                s => normaliseToken(s.ToString()),
                s => s);
            map["menu"] = VisualScene.MainMenu;
            map["songselectedit"] = VisualScene.SongSelectEditor;
            map["editor2d"] = VisualScene.EditorTwoDimensional;
            map["playback2d"] = VisualScene.PlaybackTwoDimensional;
            map["editorsheet"] = VisualScene.EditorManuscript;
            map["playbacksheet"] = VisualScene.PlaybackManuscript;

            var selected = new HashSet<VisualScene>();
            var unknown = new List<string>();

            foreach (string token in tokens)
            {
                if (map.TryGetValue(normaliseToken(token), out var scene))
                    selected.Add(scene);
                else
                    unknown.Add(token);
            }

            if (unknown.Count > 0)
            {
                throw new InvalidOperationException(
                    $"Unknown {sceneFilterEnvVar} value(s): {string.Join(", ", unknown)}. " +
                    $"Valid scenes: {string.Join(", ", VisualSnapshotCatalog.Scenes.Select(s => s.ToString()))}.");
            }

            return selected;
        }

        private static HashSet<VisualResolution> parseResolutionFilter(IReadOnlyList<string> tokens)
        {
            if (tokens.Any(isAllToken))
                return new HashSet<VisualResolution>(VisualSnapshotCatalog.Resolutions);

            var map = new Dictionary<string, VisualResolution>();
            foreach (var resolution in VisualSnapshotCatalog.Resolutions)
            {
                map[normaliseToken(resolution.Name)] = resolution;
                map[normaliseToken($"{resolution.Width}x{resolution.Height}")] = resolution;
            }

            var selected = new HashSet<VisualResolution>();
            var unknown = new List<string>();

            foreach (string token in tokens)
            {
                if (map.TryGetValue(normaliseToken(token), out var resolution))
                    selected.Add(resolution);
                else
                    unknown.Add(token);
            }

            if (unknown.Count > 0)
            {
                throw new InvalidOperationException(
                    $"Unknown {resolutionFilterEnvVar} value(s): {string.Join(", ", unknown)}. " +
                    $"Valid resolution names: {string.Join(", ", VisualSnapshotCatalog.Resolutions.Select(r => r.Name))}.");
            }

            return selected;
        }

        private static VisualProfileSelection? resolveProfileSelection()
        {
            string? profileRaw = Environment.GetEnvironmentVariable(profileEnvVar);
            if (string.IsNullOrWhiteSpace(profileRaw))
                return null;

            string profile = normaliseToken(profileRaw);

            return profile switch
            {
                "full" => null,
                "smoke" => new VisualProfileSelection(
                    new HashSet<VisualScene>
                    {
                        VisualScene.MainMenu,
                        VisualScene.SongSelectEditor,
                        VisualScene.Editor,
                        VisualScene.Playback
                    },
                    new HashSet<VisualResolution>
                    {
                        VisualSnapshotCatalog.Resolutions.First(r => r.Name == "1080p")
                    }),
                "mapping" => new VisualProfileSelection(
                    new HashSet<VisualScene>
                    {
                        VisualScene.AudioImportLoading,
                        VisualScene.MappingChoice,
                        VisualScene.MetadataChoice,
                        VisualScene.MappingGeneration
                    },
                    new HashSet<VisualResolution>
                    {
                        VisualSnapshotCatalog.Resolutions.First(r => r.Name == "1080p")
                    }),
                "editorplayback" => new VisualProfileSelection(
                    new HashSet<VisualScene>
                    {
                        VisualScene.SongSelectEditor,
                        VisualScene.Editor,
                        VisualScene.Playback,
                        VisualScene.EditorTwoDimensional,
                        VisualScene.PlaybackTwoDimensional
                    },
                    new HashSet<VisualResolution>
                    {
                        VisualSnapshotCatalog.Resolutions.First(r => r.Name == "1080p"),
                        VisualSnapshotCatalog.Resolutions.First(r => r.Name == "1440p")
                    }),
                "editor2d" => new VisualProfileSelection(
                    new HashSet<VisualScene>
                    {
                        VisualScene.EditorTwoDimensional,
                        VisualScene.PlaybackTwoDimensional
                    },
                    new HashSet<VisualResolution>
                    {
                        VisualSnapshotCatalog.Resolutions.First(r => r.Name == "1080p"),
                        VisualSnapshotCatalog.Resolutions.First(r => r.Name == "1440p")
                    }),
                "manuscript" => new VisualProfileSelection(
                    new HashSet<VisualScene>
                    {
                        VisualScene.EditorManuscript,
                        VisualScene.PlaybackManuscript
                    },
                    new HashSet<VisualResolution>
                    {
                        VisualSnapshotCatalog.Resolutions.First(r => r.Name == "1080p"),
                        VisualSnapshotCatalog.Resolutions.First(r => r.Name == "1440p")
                    }),
                _ => throw new InvalidOperationException(
                    $"Unknown {profileEnvVar}='{profileRaw}'. Valid values: full, smoke, mapping, editorplayback, editor2d, manuscript.")
            };
        }

        private static bool isAllToken(string token)
        {
            if (token.Trim() == "*")
                return true;

            string normalised = normaliseToken(token);
            return normalised is "all" or "any";
        }

        private static string normaliseToken(string value)
            => new string(value.Where(char.IsLetterOrDigit).ToArray()).ToLowerInvariant();
    }
}
