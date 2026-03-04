using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using BeatSight.Game.Beatmaps;
using BeatSight.Game;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens;
using BeatSight.Game.Screens.Editor;
using BeatSight.Game.Screens.Mapping;
using BeatSight.Game.Screens.Onboarding;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.Screens.Recording;
using BeatSight.Game.Screens.Settings;
using BeatSight.Game.Screens.SongSelect;
using BeatSight.Game.Services.Metadata;
using osu.Framework;
using osu.Framework.Graphics;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osu.Framework.Utils;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing;
using DrawingSize = System.Drawing.Size;

namespace BeatSight.Tests.VisualRegression
{
    internal sealed class VisualCaptureUnavailableException : Exception
    {
        public VisualCaptureUnavailableException(string message, Exception? inner = null)
            : base(message, inner)
        {
        }
    }

    internal static class LiveVisualCaptureRenderer
    {
        private const string suppressedInputHandlersCsv = "OpenTabletDriverHandler PenHandler JoystickHandler TouchHandler";
        private const string editorScrubProbeEnvVar = "BEATSIGHT_EDITOR_SCRUB_PROBE";
        private static readonly char[] inputHandlerSeparators = { ',', ';', ' ' };
        private static readonly string[] inputSuppressionEnvKeys =
        {
            "SDL_JOYSTICK_HIDAPI",
            "SDL_JOYSTICK_RAWINPUT",
            "SDL_JOYSTICK_WGI",
            "SDL_DIRECTINPUT_ENABLED",
            "SDL_XINPUT_ENABLED",
            "SDL_AUTO_UPDATE_JOYSTICKS",
            "SDL_HINT_JOYSTICK_HIDAPI",
            "SDL_HINT_JOYSTICK_RAWINPUT",
            "SDL_HINT_JOYSTICK_WGI",
            "SDL_HINT_DIRECTINPUT_ENABLED",
            "SDL_HINT_XINPUT_ENABLED",
            "SDL_HINT_AUTO_UPDATE_JOYSTICKS",
        };
        private static readonly BindingFlags instanceFlags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        private static readonly string[] windowSizePropertyCandidates =
        {
            "ClientSize",
            "Size",
            "WindowSize",
            "RenderSize",
            "PreferredSize",
            "RequestedSize",
            "DesiredSize",
            "Resolution"
        };

        private static readonly string[] windowSizeMethodCandidates =
        {
            "SetWindowSize",
            "SetClientSize",
            "SetSize",
            "Resize",
            "ResizeWindow",
            "ResizeClient",
            "ResizeClientArea",
            "ChangeSize",
            "RequestResize",
            "RequestResolution",
            "SetResolution",
            "UpdateWindowSize",
            "ApplyWindowSize"
        };

        private static readonly FieldInfo? screenStackField =
            typeof(BeatSightGame).GetField("screenStack", BindingFlags.Instance | BindingFlags.NonPublic);

        private static readonly FieldInfo? globalBackgroundField =
            typeof(BeatSightGame).GetField("globalBackground", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? playbackToolbarField =
            typeof(PlaybackScreen).GetField("playbackToolbar", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? mainMenuLogoParallaxField =
            typeof(MainMenuScreen).GetField("logoParallax", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? mainMenuParallaxEnabledField =
            typeof(MainMenuScreen).GetField("parallaxEnabled", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? songSelectCarouselField =
            typeof(SongSelectScreen).GetField("carousel", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? songSelectBackButtonField =
            typeof(SongSelectScreen).GetField("backButton", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? songSelectApplyResponsiveLayoutMethod =
            typeof(SongSelectScreen).GetMethod("applyResponsiveLayout", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? mappingGenerationHeartbeatDelegateField =
            typeof(MappingGenerationScreen).GetField("heartbeatStatusUpdateDelegate", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? mappingGenerationUpdateHeartbeatStatusMethod =
            typeof(MappingGenerationScreen).GetMethod("updateHeartbeatStatus", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? mappingGenerationClearInfoToastMethod =
            typeof(MappingGenerationScreen).GetMethod("clearInfoToast", BindingFlags.Instance | BindingFlags.NonPublic);

        private static readonly MethodInfo? playbackStopMethod =
            typeof(PlaybackScreen).GetMethod("stopPlayback", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? playbackSeekMethod =
            typeof(PlaybackScreen).GetMethod("seekToNormalized", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? editorStopMethod =
            typeof(EditorScreen).GetMethod("stopPlayback", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? editorSeekMethod =
            typeof(EditorScreen).GetMethod("seekToTime", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? editorQueueSeekMethod =
            typeof(EditorScreen).GetMethod("queueSeekToTime", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? editorFlushQueuedSeekMethod =
            typeof(EditorScreen).GetMethod("flushQueuedSeek", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo? editorFinalizeScrubTelemetryMethod =
            typeof(EditorScreen).GetMethod("finalizeScrubTelemetry", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? playbackLaneViewModeField =
            typeof(PlaybackScreen).GetField("laneViewModeSetting", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorLaneViewModeField =
            typeof(EditorScreen).GetField("laneViewModeBindable", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorTrackLengthField =
            typeof(EditorScreen).GetField("trackLength", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorLastScrubSummaryAvgFrameMsField =
            typeof(EditorScreen).GetField("lastScrubSummaryAvgFrameMs", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorLastScrubSummaryMaxFrameMsField =
            typeof(EditorScreen).GetField("lastScrubSummaryMaxFrameMs", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorLastScrubSummaryAvgFlushMsField =
            typeof(EditorScreen).GetField("lastScrubSummaryAvgFlushMs", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorLastScrubSummaryMaxFlushMsField =
            typeof(EditorScreen).GetField("lastScrubSummaryMaxFlushMs", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorLastScrubSummaryQueuedField =
            typeof(EditorScreen).GetField("lastScrubSummaryQueued", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorLastScrubSummaryFlushedField =
            typeof(EditorScreen).GetField("lastScrubSummaryFlushed", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo? editorLastScrubSummaryDurationMsField =
            typeof(EditorScreen).GetField("lastScrubSummaryDurationMs", BindingFlags.Instance | BindingFlags.NonPublic);

        private static readonly TimeSpan startupTimeout = TimeSpan.FromSeconds(20);
        private static readonly TimeSpan sceneReadyTimeout = TimeSpan.FromSeconds(20);
        private static readonly TimeSpan updateThreadActionTimeout = TimeSpan.FromSeconds(120);
        private static readonly TimeSpan screenshotCaptureTimeout = TimeSpan.FromSeconds(20);

        internal static Image<Rgba32> Render(VisualScene scene, VisualResolution resolution)
            => Render(scene, resolution.Width, resolution.Height);

        internal static Image<Rgba32> Render(VisualScene scene, int width, int height)
            => renderAsync(scene, width, height).GetAwaiter().GetResult();

        private static async Task<Image<Rgba32>> renderAsync(VisualScene scene, int width, int height)
        {
            if (!OperatingSystem.IsWindows())
                throw new VisualCaptureUnavailableException("Live visual capture currently runs only on Windows desktop hosts.");

            resetFrameworkRandomState();
            preseedSuppressedInputHandlersConfig();
            preseedSuppressedInputHandlersProfile();

            string? previousUserAssetRoot = Environment.GetEnvironmentVariable("BEATSIGHT_USER_ASSET_ROOT");
            string? previousCursorNormalisationSkip = Environment.GetEnvironmentVariable("BEATSIGHT_SKIP_CURSOR_NORMALISATION");
            string? visualUserAssetRoot = null;
            string beatmapPath = resolveReferenceBeatmapPath();
            string hostName = $"BeatSight.VisualRegression.{scene}-{width}x{height}.{Guid.NewGuid():N}";
            var host = (GameHost?)null;
            var game = (BeatSightGame?)null;
            Dictionary<string, string?>? previousInputSuppressionEnv = null;
            Task? runTask = null;

            try
            {
                previousInputSuppressionEnv = captureEnvironmentValues(inputSuppressionEnvKeys);
                applyInputSubsystemHints();
                visualUserAssetRoot = prepareDeterministicUserAssetRoot(scene);
                Environment.SetEnvironmentVariable("BEATSIGHT_USER_ASSET_ROOT", visualUserAssetRoot);
                Environment.SetEnvironmentVariable("BEATSIGHT_SKIP_CURSOR_NORMALISATION", "1");
                host = Host.GetSuitableDesktopHost(hostName, new HostOptions { PortableInstallation = true });
                game = new BeatSightGame();

                runTask = Task.Factory.StartNew(
                    () => host.Run(game),
                    CancellationToken.None,
                    TaskCreationOptions.LongRunning,
                    TaskScheduler.Default);

                await waitForCondition(
                    () =>
                    {
                        ensureHostRunTaskHealthy(runTask, "startup/update-thread");
                        return Task.FromResult(host.UpdateThread != null);
                    },
                    startupTimeout,
                    "BeatSight update thread").ConfigureAwait(false);

                await waitForCondition(
                    async () =>
                    {
                        ensureHostRunTaskHealthy(runTask, "startup/screen-stack");
                        return await runOnUpdateThread(host, () => getScreenStack(game) != null).ConfigureAwait(false);
                    },
                    startupTimeout,
                    "BeatSight screen stack").ConfigureAwait(false);

                await runOnUpdateThread(host, () => disableDynamicBackground(game)).ConfigureAwait(false);

                await applyWindowSize(host, width, height).ConfigureAwait(false);

                if (scene != VisualScene.Intro)
                {
                    await waitForCondition(
                        async () =>
                        {
                            ensureHostRunTaskHealthy(runTask, "main-menu-handoff");
                            return await runOnUpdateThread(host, () => getScreenStack(game)?.CurrentScreen is MainMenuScreen).ConfigureAwait(false);
                        },
                        TimeSpan.FromSeconds(10),
                        "MainMenuScreen startup handoff").ConfigureAwait(false);
                }

                Screen targetScreen = await runOnUpdateThread(host, () => pushTargetScene(scene, beatmapPath, game)).ConfigureAwait(false);
                await waitForCondition(
                    async () =>
                    {
                        ensureHostRunTaskHealthy(runTask, $"{scene} load wait");
                        return await runOnUpdateThread(host, () =>
                            targetScreen.IsLoaded && ReferenceEquals(getScreenStack(game)?.CurrentScreen, targetScreen)).ConfigureAwait(false);
                    },
                    sceneReadyTimeout,
                    $"{scene} screen to load").ConfigureAwait(false);

                await waitForConditionOrTimeout(
                    async () => await runOnUpdateThread(host, () =>
                        targetScreen.DrawWidth > 200 && targetScreen.DrawHeight > 120).ConfigureAwait(false),
                    TimeSpan.FromSeconds(4)).ConfigureAwait(false);

                await stabiliseScene(host, scene, targetScreen).ConfigureAwait(false);
                await applyWindowSize(host, width, height).ConfigureAwait(false);
                await runOnUpdateThread(host, () => validateEditorCompactInspectorLayout(targetScreen, width)).ConfigureAwait(false);

                return await captureStableScreenshot(host, targetScreen, width, height).ConfigureAwait(false);
            }
            catch (VisualCaptureUnavailableException)
            {
                throw;
            }
            catch (Exception ex)
            {
                throw new VisualCaptureUnavailableException(
                    $"Failed to capture live {scene} snapshot at {width}x{height}: {ex.Message}", ex);
            }
            finally
            {
                if (runTask != null && host != null && game != null)
                {
                    try
                    {
                        await shutdownHost(host, game, runTask).ConfigureAwait(false);
                    }
                    catch (ObjectDisposedException)
                    {
                        // Teardown race; host/game already disposed by framework.
                    }
                    catch (InvalidOperationException)
                    {
                        // Teardown race from framework scheduler/host state transitions.
                    }
                }

                safeDispose(game);
                safeDispose(host);

                Environment.SetEnvironmentVariable("BEATSIGHT_USER_ASSET_ROOT", previousUserAssetRoot);
                Environment.SetEnvironmentVariable("BEATSIGHT_SKIP_CURSOR_NORMALISATION", previousCursorNormalisationSkip);
                restoreEnvironmentValues(previousInputSuppressionEnv);
                if (!string.IsNullOrWhiteSpace(visualUserAssetRoot))
                {
                    try
                    {
                        Directory.Delete(visualUserAssetRoot, recursive: true);
                    }
                    catch
                    {
                        // Best-effort cleanup only.
                    }
                }
            }
        }

        private static Dictionary<string, string?> captureEnvironmentValues(IEnumerable<string> keys)
        {
            var snapshot = new Dictionary<string, string?>(StringComparer.Ordinal);
            foreach (string key in keys)
                snapshot[key] = Environment.GetEnvironmentVariable(key);
            return snapshot;
        }

        private static void restoreEnvironmentValues(Dictionary<string, string?>? snapshot)
        {
            if (snapshot == null)
                return;

            foreach (var entry in snapshot)
                Environment.SetEnvironmentVariable(entry.Key, entry.Value);
        }

        private static void applyInputSubsystemHints()
        {
            foreach (string key in inputSuppressionEnvKeys)
                Environment.SetEnvironmentVariable(key, "0");
        }

        private static void preseedSuppressedInputHandlersConfig()
        {
            try
            {
                string configPath = Path.Combine(AppContext.BaseDirectory, "framework.ini");
                var lines = File.Exists(configPath)
                    ? File.ReadAllLines(configPath).ToList()
                    : new List<string>();

                if (!ensureIgnoredInputHandlers(lines))
                    return;

                File.WriteAllLines(configPath, lines, Encoding.UTF8);
            }
            catch
            {
                // Best effort only; capture path already has retry and teardown handling.
            }
        }

        private static void preseedSuppressedInputHandlersProfile()
        {
            try
            {
                string inputConfigPath = Path.Combine(AppContext.BaseDirectory, "input.json");
                if (!File.Exists(inputConfigPath))
                    return;

                JsonNode? rootNode = JsonNode.Parse(File.ReadAllText(inputConfigPath));
                if (rootNode is not JsonObject rootObject)
                    return;

                if (rootObject["InputHandlers"] is not JsonArray handlers)
                    return;

                bool changed = false;

                foreach (JsonNode? handlerNode in handlers)
                {
                    if (handlerNode is not JsonObject handlerObject)
                        continue;

                    string? typeName = handlerObject["$type"]?.GetValue<string>();
                    if (!shouldSuppressInputHandler(typeName))
                        continue;

                    bool isEnabled = true;
                    if (handlerObject["Enabled"] is JsonValue enabledValue && enabledValue.TryGetValue<bool>(out bool parsedEnabled))
                        isEnabled = parsedEnabled;

                    if (!isEnabled)
                        continue;

                    handlerObject["Enabled"] = false;
                    changed = true;
                }

                if (!changed)
                    return;

                File.WriteAllText(inputConfigPath, rootObject.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
            }
            catch
            {
                // Best effort only; capture path already has retry and teardown handling.
            }
        }

        private static bool shouldSuppressInputHandler(string? typeName)
        {
            if (string.IsNullOrWhiteSpace(typeName))
                return false;

            foreach (string suppressedName in splitInputHandlerNames(suppressedInputHandlersCsv))
            {
                if (typeName.Contains(suppressedName, StringComparison.OrdinalIgnoreCase))
                    return true;
            }

            return false;
        }

        private static bool ensureIgnoredInputHandlers(List<string> lines)
        {
            const string key = "IgnoredInputHandlers";
            string prefix = key + " =";

            for (int i = 0; i < lines.Count; i++)
            {
                if (!lines[i].StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    continue;

                string currentValue = extractConfigValue(lines[i]);
                var merged = mergeInputHandlerNames(currentValue);
                string updated = $"{key} = {string.Join(" ", merged)}";

                if (string.Equals(lines[i].Trim(), updated, StringComparison.OrdinalIgnoreCase))
                    return false;

                lines[i] = updated;
                return true;
            }

            lines.Add($"{key} = {suppressedInputHandlersCsv}");
            return true;
        }

        private static string[] mergeInputHandlerNames(string value)
        {
            var merged = new List<string>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (var handler in splitInputHandlerNames(value))
            {
                if (seen.Add(handler))
                    merged.Add(handler);
            }

            foreach (var handler in splitInputHandlerNames(suppressedInputHandlersCsv))
            {
                if (seen.Add(handler))
                    merged.Add(handler);
            }

            return merged.ToArray();
        }

        private static IEnumerable<string> splitInputHandlerNames(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return Array.Empty<string>();

            return value.Split(inputHandlerSeparators, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        }

        private static string extractConfigValue(string line)
        {
            int index = line.IndexOf('=');
            return index >= 0 ? line[(index + 1)..].Trim() : string.Empty;
        }

        private static string prepareDeterministicUserAssetRoot(VisualScene scene)
        {
            string root = Path.Combine(
                Path.GetTempPath(),
                "BeatSight.VisualRegression.Assets",
                Guid.NewGuid().ToString("N"));

            string songsPath = Path.Combine(root, UserAssetDirectories.Songs);
            Directory.CreateDirectory(songsPath);

            string templateBeatmapPath = resolveReferenceBeatmapPath();
            string templateAudioPath = resolveReferenceAudioPath();
            string fixtureAudioPath = Path.Combine(songsPath, "simple_beat.wav");
            File.Copy(templateAudioPath, fixtureAudioPath, overwrite: true);

            writeSongSelectFixture(
                templateBeatmapPath,
                songsPath,
                title: "Heir of Grief",
                artist: "RichaadEB",
                creator: "BeatSight AI",
                beatmapId: "heir-of-grief-demo",
                confidence: 0.50,
                modelVersion: "v1.0.0");

            // Existing baselines include this extra generated entry in editor mode.
            if (scene == VisualScene.SongSelectEditor)
            {
                writeSongSelectFixture(
                    templateBeatmapPath,
                    songsPath,
                    title: "The Sin and the Sentence",
                    artist: "Trivium",
                    creator: "BeatSight AI",
                    beatmapId: "sin-and-sentence-demo",
                    confidence: 0.54,
                    modelVersion: "v1.0.0");
            }

            return root;
        }

        private static void writeSongSelectFixture(
            string templateBeatmapPath,
            string songsPath,
            string title,
            string artist,
            string creator,
            string beatmapId,
            double confidence,
            string modelVersion)
        {
            var beatmap = BeatmapLoader.LoadFromFile(templateBeatmapPath);
            beatmap.Metadata.Title = title;
            beatmap.Metadata.Artist = artist;
            beatmap.Metadata.Creator = creator;
            beatmap.Metadata.Difficulty = 10.0;
            beatmap.Metadata.BeatmapId = beatmapId;
            beatmap.Metadata.ModifiedAt = new DateTime(2026, 2, 11, 0, 0, 0, DateTimeKind.Utc);

            beatmap.Audio.Filename = "simple_beat.wav";
            beatmap.Audio.DrumStem = "simple_beat.wav";

            beatmap.Editor ??= new EditorInfo();
            beatmap.Editor.AiGenerationMetadata ??= new AIGenerationMetadata();
            beatmap.Editor.AiGenerationMetadata.Confidence = confidence;
            beatmap.Editor.AiGenerationMetadata.ModelVersion = modelVersion;
            beatmap.Editor.AiGenerationMetadata.ProcessedAt = new DateTime(2026, 2, 11, 0, 0, 0, DateTimeKind.Utc);
            beatmap.Editor.AiGenerationMetadata.ManualEdits = false;

            string beatmapPath = Path.Combine(songsPath, $"{beatmapId}.bsm");
            BeatmapLoader.SaveToFile(beatmap, beatmapPath);
        }

        private static string resolveReferenceBeatmapPath()
        {
            string path = Path.Combine(
                TestPathResolver.ResolveRepositoryRoot(),
                "shared",
                "formats",
                "simple_beat.bsm");

            if (!File.Exists(path))
                throw new VisualCaptureUnavailableException($"Reference beatmap not found: {path}");

            return Path.GetFullPath(path);
        }

        private static string resolveReferenceAudioPath()
        {
            string path = Path.Combine(
                TestPathResolver.ResolveRepositoryRoot(),
                "shared",
                "formats",
                "simple_beat.wav");

            if (!File.Exists(path))
                throw new VisualCaptureUnavailableException($"Reference audio not found: {path}");

            return Path.GetFullPath(path);
        }

        private static ImportedAudioTrack createReferenceImportedTrack()
        {
            string audioPath = resolveReferenceAudioPath();
            var fileInfo = new FileInfo(audioPath);

            var track = new ImportedAudioTrack(
                originalPath: audioPath,
                storedPath: audioPath,
                relativeStoragePath: Path.Combine("shared", "formats", "simple_beat.wav"),
                displayName: "Simple Beat",
                fileSizeBytes: fileInfo.Length,
                durationMilliseconds: 5000);

            track.Title = "Simple Beat";
            track.Artist = "BeatSight";
            return track;
        }

        private static DetectedMetadata createReferenceDetectedMetadata()
        {
            return new DetectedMetadata
            {
                Title = "Simple Beat",
                Artist = "BeatSight",
                Album = "Visual Baselines",
                ReleaseDate = "2026-01-01",
                Source = "visual-regression",
                Confidence = 0.98,
                Provider = "baseline"
            };
        }

        private static Screen pushTargetScene(VisualScene scene, string beatmapPath, BeatSightGame game)
        {
            var stack = getScreenStack(game)
                        ?? throw new VisualCaptureUnavailableException("Could not locate BeatSight screen stack.");

            Screen target = scene switch
            {
                VisualScene.Intro => new IntroScreen(),
                VisualScene.MainMenu => stack.CurrentScreen as MainMenuScreen ?? new MainMenuScreen(),
                VisualScene.SongSelect => new SongSelectScreen(),
                VisualScene.SongSelectEditor => new SongSelectScreen(editorMode: true),
                VisualScene.Settings => new SettingsScreen(),
                VisualScene.Recording => new RecordingScreen(),
                VisualScene.Onboarding => new OnboardingScreen(),
                VisualScene.AudioImportLoading => new StableAudioImportLoadingScreen(resolveReferenceAudioPath()),
                VisualScene.MappingChoice => new MappingChoiceScreen(createReferenceImportedTrack()),
                VisualScene.MetadataChoice => new MetadataChoiceScreen(createReferenceImportedTrack(), createReferenceDetectedMetadata()),
                VisualScene.MappingGeneration => new MappingGenerationScreen(createReferenceImportedTrack()),
                VisualScene.Editor => new EditorScreen(beatmapPath),
                VisualScene.Playback => new PlaybackScreen(beatmapPath),
                VisualScene.EditorTwoDimensional => new EditorScreen(beatmapPath),
                VisualScene.PlaybackTwoDimensional => new PlaybackScreen(beatmapPath),
                VisualScene.EditorManuscript => new EditorScreen(beatmapPath),
                VisualScene.PlaybackManuscript => new PlaybackScreen(beatmapPath),
                _ => throw new ArgumentOutOfRangeException(nameof(scene), scene, "Unsupported visual scene.")
            };

            if (!ReferenceEquals(stack.CurrentScreen, target))
                stack.Push(target);

            return target;
        }

        private static async Task stabiliseScene(GameHost host, VisualScene scene, Screen targetScreen)
        {
            switch (scene)
            {
                case VisualScene.Intro:
                    await Task.Delay(2400).ConfigureAwait(false);
                    break;

                case VisualScene.MainMenu:
                    await Task.Delay(900).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezeMainMenuIfSupported(targetScreen)).ConfigureAwait(false);
                    await Task.Delay(220).ConfigureAwait(false);
                    break;

                case VisualScene.SongSelect:
                case VisualScene.SongSelectEditor:
                    await waitForConditionOrTimeout(
                        async () => await runOnUpdateThread(host, () => isSongSelectHeaderMeasured(targetScreen)).ConfigureAwait(false),
                        TimeSpan.FromSeconds(3)).ConfigureAwait(false);
                    await Task.Delay(1650).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezeSongSelectIfSupported(targetScreen)).ConfigureAwait(false);
                    await Task.Delay(200).ConfigureAwait(false);
                    break;

                case VisualScene.Settings:
                    await Task.Delay(1600).ConfigureAwait(false);
                    break;

                case VisualScene.Recording:
                    await Task.Delay(1200).ConfigureAwait(false);
                    break;

                case VisualScene.Onboarding:
                    await Task.Delay(1000).ConfigureAwait(false);
                    break;

                case VisualScene.AudioImportLoading:
                    await Task.Delay(900).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezeAudioImportLoadingIfSupported(targetScreen)).ConfigureAwait(false);
                    await Task.Delay(160).ConfigureAwait(false);
                    break;

                case VisualScene.MappingChoice:
                case VisualScene.MetadataChoice:
                    await Task.Delay(1400).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezeMappingSelectionScreenIfSupported(targetScreen)).ConfigureAwait(false);
                    await Task.Delay(160).ConfigureAwait(false);
                    break;

                case VisualScene.MappingGeneration:
                    await Task.Delay(1600).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezeMappingGenerationIfSupported(targetScreen)).ConfigureAwait(false);
                    await Task.Delay(220).ConfigureAwait(false);
                    break;

                case VisualScene.Editor:
                    await Task.Delay(2400).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezeEditorIfSupported(targetScreen, LaneViewMode.ThreeDimensional)).ConfigureAwait(false);
                    await Task.Delay(220).ConfigureAwait(false);
                    if (shouldRunEditorScrubProbe())
                    {
                        await runEditorScrubProbe(host, targetScreen).ConfigureAwait(false);
                        await runOnUpdateThread(host, () => freezeEditorIfSupported(targetScreen, LaneViewMode.ThreeDimensional)).ConfigureAwait(false);
                        await Task.Delay(180).ConfigureAwait(false);
                    }
                    break;

                case VisualScene.Playback:
                    await Task.Delay(1400).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezePlaybackIfSupported(targetScreen, LaneViewMode.ThreeDimensional)).ConfigureAwait(false);
                    await waitForConditionOrTimeout(
                        async () => await runOnUpdateThread(host, () => hasVisiblePlaybackToolbar(targetScreen)).ConfigureAwait(false),
                        TimeSpan.FromSeconds(3)).ConfigureAwait(false);
                    await Task.Delay(320).ConfigureAwait(false);
                    break;

                case VisualScene.EditorTwoDimensional:
                    await Task.Delay(2400).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezeEditorIfSupported(targetScreen, LaneViewMode.TwoDimensional)).ConfigureAwait(false);
                    await Task.Delay(220).ConfigureAwait(false);
                    if (shouldRunEditorScrubProbe())
                    {
                        await runEditorScrubProbe(host, targetScreen).ConfigureAwait(false);
                        await runOnUpdateThread(host, () => freezeEditorIfSupported(targetScreen, LaneViewMode.TwoDimensional)).ConfigureAwait(false);
                        await Task.Delay(180).ConfigureAwait(false);
                    }
                    break;

                case VisualScene.PlaybackTwoDimensional:
                    await Task.Delay(1400).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezePlaybackIfSupported(targetScreen, LaneViewMode.TwoDimensional)).ConfigureAwait(false);
                    await waitForConditionOrTimeout(
                        async () => await runOnUpdateThread(host, () => hasVisiblePlaybackToolbar(targetScreen)).ConfigureAwait(false),
                        TimeSpan.FromSeconds(3)).ConfigureAwait(false);
                    await Task.Delay(320).ConfigureAwait(false);
                    break;

                case VisualScene.EditorManuscript:
                    await Task.Delay(2400).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezeEditorIfSupported(targetScreen, LaneViewMode.Manuscript)).ConfigureAwait(false);
                    await Task.Delay(220).ConfigureAwait(false);
                    break;

                case VisualScene.PlaybackManuscript:
                    await Task.Delay(1400).ConfigureAwait(false);
                    await runOnUpdateThread(host, () => freezePlaybackIfSupported(targetScreen, LaneViewMode.Manuscript)).ConfigureAwait(false);
                    await waitForConditionOrTimeout(
                        async () => await runOnUpdateThread(host, () => hasVisiblePlaybackToolbar(targetScreen)).ConfigureAwait(false),
                        TimeSpan.FromSeconds(3)).ConfigureAwait(false);
                    await Task.Delay(320).ConfigureAwait(false);
                    break;

                default:
                    await Task.Delay(1200).ConfigureAwait(false);
                    break;
            }

            await runOnUpdateThread(host, () => targetScreen.FinishTransforms(true)).ConfigureAwait(false);
            await runOnUpdateThread(host, () => targetScreen.ClearTransforms(propagateChildren: true)).ConfigureAwait(false);
            await Task.Delay(120).ConfigureAwait(false);
        }


        private static void freezeEditorIfSupported(Screen screen, LaneViewMode laneViewMode)
        {
            if (screen is not EditorScreen editor)
                return;

            setScreenLaneViewMode(editorLaneViewModeField?.GetValue(editor), laneViewMode);
            editorStopMethod?.Invoke(editor, new object?[] { true });
            editorSeekMethod?.Invoke(editor, new object?[] { 2000d });
        }

        private static bool shouldRunEditorScrubProbe()
        {
            string? value = Environment.GetEnvironmentVariable(editorScrubProbeEnvVar);
            if (string.IsNullOrWhiteSpace(value))
                return false;

            return value == "1"
                   || value.Equals("true", StringComparison.OrdinalIgnoreCase)
                   || value.Equals("yes", StringComparison.OrdinalIgnoreCase);
        }

        private static async Task runEditorScrubProbe(GameHost host, Screen screen)
        {
            if (screen is not EditorScreen editor)
                return;

            if (editorQueueSeekMethod == null || editorFlushQueuedSeekMethod == null)
                return;

            Type? seekInputSourceType = typeof(EditorScreen).GetNestedType("SeekInputSource", BindingFlags.NonPublic);
            if (seekInputSourceType == null || !seekInputSourceType.IsEnum)
                return;

            object wheelSource = Enum.ToObject(seekInputSourceType, 1);
            object seekBarSource = Enum.ToObject(seekInputSourceType, 2);

            double trackLength = await runOnUpdateThread(host, () =>
                Convert.ToDouble(editorTrackLengthField?.GetValue(editor) ?? 8000d)).ConfigureAwait(false);
            double maxTarget = Math.Max(2200, trackLength > 0 ? trackLength - 240 : 7600);

            for (int i = 0; i < 56; i++)
            {
                double normalized = i / 55.0;
                double target = 900 + normalized * (maxTarget - 900);
                double delta = (i % 2 == 0 ? 1.0 : -1.0) * (1.0 + (i % 4) * 0.22);
                await runOnUpdateThread(host, () => invokeEditorScrubSeek(editor, target, wheelSource, delta, syncTrack: true)).ConfigureAwait(false);
                await Task.Delay(8).ConfigureAwait(false);
            }

            for (int i = 0; i < 64; i++)
            {
                double normalized = i / 63.0;
                double arc = 0.5 - 0.5 * Math.Cos(normalized * Math.PI);
                double target = 780 + arc * (maxTarget - 780);
                double delta = normalized - 0.5;
                await runOnUpdateThread(host, () => invokeEditorScrubSeek(editor, target, seekBarSource, delta, syncTrack: false)).ConfigureAwait(false);
                await Task.Delay(7).ConfigureAwait(false);
            }

            await Task.Delay(300).ConfigureAwait(false);
            await runOnUpdateThread(host, () => editorFinalizeScrubTelemetryMethod?.Invoke(editor, null)).ConfigureAwait(false);
            await runOnUpdateThread(host, () =>
            {
                double avgFrameMs = Convert.ToDouble(editorLastScrubSummaryAvgFrameMsField?.GetValue(editor) ?? 0d);
                double maxFrameMs = Convert.ToDouble(editorLastScrubSummaryMaxFrameMsField?.GetValue(editor) ?? 0d);
                double avgFlushMs = Convert.ToDouble(editorLastScrubSummaryAvgFlushMsField?.GetValue(editor) ?? 0d);
                double maxFlushMs = Convert.ToDouble(editorLastScrubSummaryMaxFlushMsField?.GetValue(editor) ?? 0d);
                int queued = Convert.ToInt32(editorLastScrubSummaryQueuedField?.GetValue(editor) ?? 0);
                int flushed = Convert.ToInt32(editorLastScrubSummaryFlushedField?.GetValue(editor) ?? 0);
                double durationMs = Convert.ToDouble(editorLastScrubSummaryDurationMsField?.GetValue(editor) ?? 0d);

                Console.WriteLine(
                    $"[VisualScrubProbe] duration={durationMs:0}ms queued={queued} flushed={flushed} frame(avg/max)={avgFrameMs:0.00}/{maxFrameMs:0.00}ms flush(avg/max)={avgFlushMs:0.00}/{maxFlushMs:0.00}ms");
            }).ConfigureAwait(false);
        }

        private static void invokeEditorScrubSeek(EditorScreen editor, double target, object sourceEnumValue, double inputDelta, bool syncTrack)
        {
            editorQueueSeekMethod?.Invoke(editor, new object?[]
            {
                target,
                true,
                syncTrack,
                true,
                sourceEnumValue,
                inputDelta
            });

            editorFlushQueuedSeekMethod?.Invoke(editor, null);
        }

        private static void validateEditorCompactInspectorLayout(Screen screen, int captureWidth)
        {
            if (captureWidth > 1366)
                return;

            if (screen is not EditorScreen editor)
                return;

            var contract = editor.CaptureInspectorLayoutContract();
            if (!contract.IsStackedLayout)
                return;

            validateCompactInspectorActionRows(contract.ActionRows);
            validateCompactHeaderWidths(contract.Header);
            validateCompactTimelineToolbox(contract.TimelineToolbox);
        }

        private static void validateCompactInspectorActionRows(InspectorActionRowContract[] actionRows)
        {
            if (actionRows.Length == 0)
            {
                throw new VisualCaptureUnavailableException(
                    "Editor compact layout contract failed: inspector action rows were not initialized in stacked mode.");
            }

            foreach (var row in actionRows)
            {
                if (row.ColumnCount < 1)
                    continue;

                (float min, float max) = getCompactRowWidthBounds(row.ColumnCount);
                if (row.WidthFraction < min || row.WidthFraction > max)
                {
                    throw new VisualCaptureUnavailableException(
                        $"Editor compact layout contract failed: columnCount={row.ColumnCount}, width={row.WidthFraction:0.###}, expected range={min:0.###}-{max:0.###}.");
                }

                if (row.WidthFraction < 0.999f && (row.Anchor != Anchor.TopCentre || row.Origin != Anchor.TopCentre))
                {
                    throw new VisualCaptureUnavailableException(
                        $"Editor compact layout contract failed: bounded rows must be centered (anchor={row.Anchor}, origin={row.Origin}).");
                }
            }
        }

        private static void validateCompactHeaderWidths(EditorHeaderLayoutContract header)
        {
            if (header.StatusMaxWidth <= 0 || header.ActionHintMaxWidth <= 0 || header.PlaybackStatusMaxWidth <= 0)
            {
                throw new VisualCaptureUnavailableException(
                    "Editor compact header contract failed: header max-width values were not initialized.");
            }

            if (header.StatusMaxWidth < 450f || header.StatusMaxWidth > 690f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: status max width out of range ({header.StatusMaxWidth:0.###}, expected 450-690).");
            }

            if (header.ActionHintMaxWidth < 820f || header.ActionHintMaxWidth > 1240f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: action hint max width out of range ({header.ActionHintMaxWidth:0.###}, expected 820-1240).");
            }

            if (header.PlaybackStatusMaxWidth < 820f || header.PlaybackStatusMaxWidth > 1240f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: playback status max width out of range ({header.PlaybackStatusMaxWidth:0.###}, expected 820-1240).");
            }

            if (Math.Abs(header.ActionHintMaxWidth - header.PlaybackStatusMaxWidth) > 1.5f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: action/playback hint max widths diverged ({header.ActionHintMaxWidth:0.###} vs {header.PlaybackStatusMaxWidth:0.###}).");
            }

            if (header.ActionHintMaxWidth < header.StatusMaxWidth + 260f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: hint width no longer dominates status width ({header.ActionHintMaxWidth:0.###} vs {header.StatusMaxWidth:0.###}).");
            }

            if (header.PrimaryRowHeight < 58f || header.PrimaryRowHeight > 104f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: primary row height out of range ({header.PrimaryRowHeight:0.###}, expected 58-104).");
            }

            if (header.PrimaryAccentHeight < header.PrimaryRowHeight + 6f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: primary accent does not extend below controls ({header.PrimaryAccentHeight:0.###} vs row {header.PrimaryRowHeight:0.###}).");
            }

            if (header.PrimaryAccentHeight > header.PrimaryRowHeight + 42f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: primary accent depth is excessive ({header.PrimaryAccentHeight:0.###} vs row {header.PrimaryRowHeight:0.###}).");
            }

            if (header.InformationHeight > 1.5f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: header information row unexpectedly occupies height ({header.InformationHeight:0.###}).");
            }

            if (header.InformationAlpha > 0.02f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact header contract failed: header information row unexpectedly visible (alpha={header.InformationAlpha:0.###}).");
            }
        }

        private static void validateCompactTimelineToolbox(EditorTimelineToolboxLayoutContract timelineToolbox)
        {
            if (timelineToolbox.ContentSpacingX <= 0
                || timelineToolbox.ZoomSliderWidth <= 0
                || timelineToolbox.ZoomSliderHeight <= 0
                || timelineToolbox.WaveformSliderWidth <= 0
                || timelineToolbox.WaveformSliderHeight <= 0)
            {
                throw new VisualCaptureUnavailableException(
                    "Editor compact timeline contract failed: timeline toolbox values were not initialized.");
            }

            if (timelineToolbox.ContentSpacingX < 8.5f || timelineToolbox.ContentSpacingX > 13.5f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: content spacing out of range ({timelineToolbox.ContentSpacingX:0.###}, expected 8.5-13.5).");
            }

            if (timelineToolbox.ZoomSliderWidth < 145f || timelineToolbox.ZoomSliderWidth > 170f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: zoom slider width out of range ({timelineToolbox.ZoomSliderWidth:0.###}, expected 145-170).");
            }

            if (timelineToolbox.WaveformSliderWidth < 130f || timelineToolbox.WaveformSliderWidth > 154f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: waveform slider width out of range ({timelineToolbox.WaveformSliderWidth:0.###}, expected 130-154).");
            }

            if (timelineToolbox.ZoomSliderWidth < timelineToolbox.WaveformSliderWidth + 8f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: zoom slider should remain wider than waveform slider ({timelineToolbox.ZoomSliderWidth:0.###} vs {timelineToolbox.WaveformSliderWidth:0.###}).");
            }

            if (timelineToolbox.ZoomSliderHeight < 25f || timelineToolbox.ZoomSliderHeight > 31f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: zoom slider height out of range ({timelineToolbox.ZoomSliderHeight:0.###}, expected 25-31).");
            }

            if (timelineToolbox.WaveformSliderHeight < 25f || timelineToolbox.WaveformSliderHeight > 31f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: waveform slider height out of range ({timelineToolbox.WaveformSliderHeight:0.###}, expected 25-31).");
            }

            if (Math.Abs(timelineToolbox.ZoomSliderHeight - timelineToolbox.WaveformSliderHeight) > 1.5f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: slider heights diverged ({timelineToolbox.ZoomSliderHeight:0.###} vs {timelineToolbox.WaveformSliderHeight:0.###}).");
            }

            if (timelineToolbox.SectionRowSpacingX < 5.8f || timelineToolbox.SectionRowSpacingX > 9.5f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: section row spacing out of range ({timelineToolbox.SectionRowSpacingX:0.###}, expected 5.8-9.5).");
            }

            if (timelineToolbox.MiniButtonHeight < 28f || timelineToolbox.MiniButtonHeight > 33f)
            {
                throw new VisualCaptureUnavailableException(
                    $"Editor compact timeline contract failed: mini button height out of range ({timelineToolbox.MiniButtonHeight:0.###}, expected 28-33).");
            }
        }

        private static (float Min, float Max) getCompactRowWidthBounds(int columnCount)
            => columnCount switch
            {
                <= 1 => (0.17f, 0.34f),
                2 => (0.34f, 0.64f),
                3 => (0.50f, 0.91f),
                _ => (0.99f, 1.01f)
            };

        private static void freezeMainMenuIfSupported(Screen screen)
        {
            if (screen is not MainMenuScreen mainMenu)
                return;

            mainMenu.ClearTransforms(propagateChildren: true);
            mainMenuParallaxEnabledField?.SetValue(mainMenu, false);

            if (mainMenuLogoParallaxField?.GetValue(mainMenu) is Drawable parallax)
            {
                parallax.ClearTransforms(propagateChildren: true);
                parallax.Position = osuTK.Vector2.Zero;
                parallax.Scale = osuTK.Vector2.One;
                parallax.Rotation = 0;
            }
        }

        private static bool isSongSelectHeaderMeasured(Screen screen)
        {
            if (screen is not SongSelectScreen songSelect)
                return true;

            if (songSelectBackButtonField?.GetValue(songSelect) is not Drawable backButton)
                return false;

            return backButton.DrawWidth > 90 && backButton.DrawHeight > 30;
        }

        private static void freezeSongSelectIfSupported(Screen screen)
        {
            if (screen is not SongSelectScreen songSelect)
                return;

            songSelectApplyResponsiveLayoutMethod?.Invoke(songSelect, new object?[] { true });

            if (songSelectCarouselField?.GetValue(songSelect) is Drawable carousel)
            {
                carousel.FinishTransforms(true);
                carousel.ClearTransforms(propagateChildren: true);
            }

            if (songSelectBackButtonField?.GetValue(songSelect) is Drawable backButton)
            {
                backButton.FinishTransforms(true);
                backButton.ClearTransforms(propagateChildren: true);
            }
        }

        private static void freezeMappingSelectionScreenIfSupported(Screen screen)
        {
            if (screen is not MappingChoiceScreen && screen is not MetadataChoiceScreen)
                return;

            screen.FinishTransforms(true);
            screen.ClearTransforms(propagateChildren: true);
        }

        private static void freezeAudioImportLoadingIfSupported(Screen screen)
        {
            if (screen is not AudioImportLoadingScreen)
                return;

            screen.FinishTransforms(true);
            screen.ClearTransforms(propagateChildren: true);
        }

        private static void freezeMappingGenerationIfSupported(Screen screen)
        {
            if (screen is not MappingGenerationScreen mapping)
                return;

            // Stop recurring heartbeat scheduler for deterministic capture.
            if (mappingGenerationHeartbeatDelegateField?.GetValue(mapping) is object delegateInstance)
            {
                delegateInstance.GetType().GetMethod("Cancel", instanceFlags)?.Invoke(delegateInstance, null);
                mappingGenerationHeartbeatDelegateField.SetValue(mapping, null);
            }

            mappingGenerationClearInfoToastMethod?.Invoke(mapping, null);
            mappingGenerationUpdateHeartbeatStatusMethod?.Invoke(mapping, new object?[] { true });
            mapping.FinishTransforms(true);
            mapping.ClearTransforms(propagateChildren: true);
        }

        private static void freezePlaybackIfSupported(Screen screen, LaneViewMode laneViewMode)
        {
            if (screen is not PlaybackScreen playback || playbackStopMethod == null)
                return;

            setScreenLaneViewMode(playbackLaneViewModeField?.GetValue(playback), laneViewMode);
            playbackStopMethod.Invoke(playback, null);
            playbackSeekMethod?.Invoke(playback, new object?[] { 0.25d, true });
        }

        private static void setScreenLaneViewMode(object? bindable, LaneViewMode mode)
        {
            if (bindable == null)
                return;

            var valueProperty = bindable.GetType().GetProperty("Value", instanceFlags);
            if (valueProperty == null || !valueProperty.CanWrite)
                return;

            try
            {
                valueProperty.SetValue(bindable, mode);
            }
            catch
            {
                // Best effort only for deterministic visual capture.
            }
        }

        private static bool hasVisiblePlaybackToolbar(Screen screen)
        {
            if (screen is not PlaybackScreen playback)
                return true;

            if (playbackToolbarField?.GetValue(playback) is not Drawable toolbar)
                return false;

            return toolbar.DrawHeight > 40 && toolbar.Alpha > 0.95f;
        }

        private static void disableDynamicBackground(BeatSightGame game)
        {
            if (globalBackgroundField?.GetValue(game) is Drawable background)
                background.Alpha = 0;
        }

        private static ScreenStack? getScreenStack(BeatSightGame game)
            => screenStackField?.GetValue(game) as ScreenStack;

        private static async Task applyWindowSize(GameHost host, int width, int height)
        {
            DrawingSize effectiveSize = await runOnUpdateThread(host, () =>
            {
                if (host.Window == null)
                    throw new VisualCaptureUnavailableException("Desktop host window was not created.");

                host.Window.WindowState = osu.Framework.Platform.WindowState.Normal;
                var displayBounds = host.Window.PrimaryDisplay.Bounds;
                int targetWidth = Math.Max(960, width);
                int targetHeight = Math.Max(540, height);

                if (displayBounds.Width > 0)
                    targetWidth = Math.Min(targetWidth, displayBounds.Width);

                if (displayBounds.Height > 0)
                    targetHeight = Math.Min(targetHeight, displayBounds.Height);

                if (!trySetWindowSize(host.Window, targetWidth, targetHeight))
                    throw new VisualCaptureUnavailableException($"Could not set capture window size to {targetWidth}x{targetHeight}.");

                return new DrawingSize(targetWidth, targetHeight);
            }).ConfigureAwait(false);

            bool matched = await waitForConditionOrTimeout(
                () => Task.FromResult(windowMatchesSize(host, effectiveSize.Width, effectiveSize.Height)),
                TimeSpan.FromSeconds(6)).ConfigureAwait(false);

            if (!matched)
            {
                // One more force-pass in case the first setter touched outer window size instead of client size.
                await runOnUpdateThread(host, () =>
                {
                    if (host.Window != null)
                        trySetWindowSize(host.Window, effectiveSize.Width, effectiveSize.Height);
                }).ConfigureAwait(false);

                matched = await waitForConditionOrTimeout(
                    () => Task.FromResult(windowMatchesSize(host, effectiveSize.Width, effectiveSize.Height)),
                    TimeSpan.FromSeconds(6)).ConfigureAwait(false);
            }

            if (!matched)
            {
                DrawingSize actual = await runOnUpdateThread(host, () =>
                    host.Window?.ClientSize ?? new DrawingSize(0, 0)).ConfigureAwait(false);

                throw new VisualCaptureUnavailableException(
                    $"Window size did not stabilise at {effectiveSize.Width}x{effectiveSize.Height}; final client size was {actual.Width}x{actual.Height}.");
            }
        }

        private static bool windowMatchesSize(GameHost host, int width, int height)
        {
            var window = host.Window;
            if (window == null)
                return false;

            var current = window.ClientSize;
            return Math.Abs(current.Width - width) <= 1 && Math.Abs(current.Height - height) <= 1;
        }

        private static bool trySetWindowSize(IWindow window, int width, int height)
        {
            foreach (string propertyName in windowSizePropertyCandidates)
            {
                var property = window.GetType().GetProperty(propertyName, instanceFlags);
                if (property == null || !property.CanWrite)
                    continue;

                if (!tryCreateSizeValue(property.PropertyType, width, height, out object? value))
                    continue;

                try
                {
                    property.SetValue(window, value);
                    return true;
                }
                catch
                {
                    // Keep trying alternate targets.
                }
            }

            foreach (string methodName in windowSizeMethodCandidates)
            {
                var method = window.GetType().GetMethod(methodName, instanceFlags);
                if (method == null)
                    continue;

                var parameters = method.GetParameters();
                if (parameters.Length != 1)
                    continue;

                if (!tryCreateSizeValue(parameters[0].ParameterType, width, height, out object? value))
                    continue;

                try
                {
                    method.Invoke(window, new[] { value });
                    return true;
                }
                catch
                {
                    // Keep trying alternate targets.
                }
            }

            return false;
        }

        private static bool tryCreateSizeValue(Type targetType, int width, int height, out object? value)
        {
            var underlying = Nullable.GetUnderlyingType(targetType) ?? targetType;

            if (underlying == typeof(DrawingSize))
            {
                value = new DrawingSize(width, height);
                return true;
            }

            if (underlying.FullName == "osuTK.Vector2i")
            {
                var ctor = underlying.GetConstructor(new[] { typeof(int), typeof(int) });
                if (ctor != null)
                {
                    value = ctor.Invoke(new object[] { width, height });
                    return true;
                }
            }

            if (underlying.FullName == "osuTK.Vector2")
            {
                var ctor = underlying.GetConstructor(new[] { typeof(float), typeof(float) });
                if (ctor != null)
                {
                    value = ctor.Invoke(new object[] { (float)width, (float)height });
                    return true;
                }
            }

            var intCtor = underlying.GetConstructor(new[] { typeof(int), typeof(int) });
            if (intCtor != null)
            {
                value = intCtor.Invoke(new object[] { width, height });
                return true;
            }

            var floatCtor = underlying.GetConstructor(new[] { typeof(float), typeof(float) });
            if (floatCtor != null)
            {
                value = floatCtor.Invoke(new object[] { (float)width, (float)height });
                return true;
            }

            value = null;
            return false;
        }

        private static async Task<T> runOnUpdateThread<T>(GameHost host, Func<T> action)
        {
            if (host.UpdateThread == null)
                throw new VisualCaptureUnavailableException("Host update thread is unavailable.");

            var tcs = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
            host.UpdateThread.Scheduler.Add(() =>
            {
                try
                {
                    tcs.TrySetResult(action());
                }
                catch (Exception ex)
                {
                    tcs.TrySetException(ex);
                }
            });

            Task timeoutTask = Task.Delay(updateThreadActionTimeout);
            Task completed = await Task.WhenAny(tcs.Task, timeoutTask).ConfigureAwait(false);
            if (completed != tcs.Task)
                throw new VisualCaptureUnavailableException($"Timed out waiting for update-thread action after {updateThreadActionTimeout.TotalSeconds:0}s.");

            return await tcs.Task.ConfigureAwait(false);
        }

        private static async Task runOnUpdateThread(GameHost host, Action action)
            => await runOnUpdateThread(host, () =>
            {
                action();
                return true;
            }).ConfigureAwait(false);

        private static async Task waitForCondition(Func<Task<bool>> condition, TimeSpan timeout, string description)
        {
            DateTime deadline = DateTime.UtcNow + timeout;
            while (DateTime.UtcNow < deadline)
            {
                if (await condition().ConfigureAwait(false))
                    return;

                await Task.Delay(60).ConfigureAwait(false);
            }

            throw new VisualCaptureUnavailableException($"Timed out waiting for {description}.");
        }

        private static async Task<bool> waitForConditionOrTimeout(Func<Task<bool>> condition, TimeSpan timeout)
        {
            DateTime deadline = DateTime.UtcNow + timeout;
            while (DateTime.UtcNow < deadline)
            {
                if (await condition().ConfigureAwait(false))
                    return true;

                await Task.Delay(60).ConfigureAwait(false);
            }

            return false;
        }

        private static async Task shutdownHost(GameHost host, BeatSightGame game, Task runTask)
        {
            if (!runTask.IsCompleted)
            {
                try
                {
                    await runOnUpdateThread(host, game.Exit).ConfigureAwait(false);
                }
                catch
                {
                    // Best effort only.
                }

                if (await Task.WhenAny(runTask, Task.Delay(5000)).ConfigureAwait(false) != runTask)
                {
                    try
                    {
                        host.Exit();
                    }
                    catch
                    {
                        // Ignore.
                    }
                }
            }

            try
            {
                await Task.WhenAny(runTask, Task.Delay(5000)).ConfigureAwait(false);
            }
            catch
            {
                // Ignore teardown exceptions; capture path has already surfaced the primary failure.
            }
        }

        private static async Task<Image<Rgba32>> captureStableScreenshot(GameHost host, Screen targetScreen, int width, int height)
        {
            const int maxAttempts = 6;
            string? lastInstabilityReason = null;

            for (int attempt = 0; attempt < maxAttempts; attempt++)
            {
                using var screenshot = await takeScreenshotWithTimeout(host).ConfigureAwait(false);
                var output = normaliseScreenshotDimensions(screenshot, width, height);
                forceOpaqueAlpha(output);

                if (hasLikelyExternalOverlayHint(output))
                {
                    lastInstabilityReason = "Detected likely external overlay hint in capture frame.";
                    output.Dispose();
                    await runOnUpdateThread(host, () => targetScreen.FinishTransforms(true)).ConfigureAwait(false);
                    await Task.Delay(320).ConfigureAwait(false);
                    continue;
                }

                if (!isNearBlackFrame(output))
                    return output;

                lastInstabilityReason = "Captured near-black frame.";
                output.Dispose();

                await runOnUpdateThread(host, () => targetScreen.FinishTransforms(true)).ConfigureAwait(false);
                await Task.Delay(220).ConfigureAwait(false);
            }

            throw new VisualCaptureUnavailableException(
                $"Screenshot capture did not stabilise after {maxAttempts} attempts. Last reason: {lastInstabilityReason ?? "unknown"}");
        }

        private static async Task<Image<Rgba32>> takeScreenshotWithTimeout(GameHost host)
        {
            Task<Image<Rgba32>> screenshotTask = host.TakeScreenshotAsync();
            Task timeoutTask = Task.Delay(screenshotCaptureTimeout);
            Task completed = await Task.WhenAny(screenshotTask, timeoutTask).ConfigureAwait(false);
            if (completed != screenshotTask)
                throw new VisualCaptureUnavailableException($"Timed out waiting for host screenshot after {screenshotCaptureTimeout.TotalSeconds:0}s.");

            return await screenshotTask.ConfigureAwait(false);
        }

        private static void forceOpaqueAlpha(Image<Rgba32> image)
        {
            for (int y = 0; y < image.Height; y++)
            {
                for (int x = 0; x < image.Width; x++)
                {
                    Rgba32 pixel = image[x, y];
                    if (pixel.A == 255)
                        continue;

                    pixel.A = 255;
                    image[x, y] = pixel;
                }
            }
        }

        private static Image<Rgba32> normaliseScreenshotDimensions(Image<Rgba32> screenshot, int targetWidth, int targetHeight)
        {
            if (screenshot.Width == targetWidth && screenshot.Height == targetHeight)
                return screenshot.Clone();

            int widthDelta = Math.Abs(screenshot.Width - targetWidth);
            int heightDelta = Math.Abs(screenshot.Height - targetHeight);

            // Minor size drift (typically from DPI/window manager jitter) is normalised with
            // centre crop/pad to avoid introducing global interpolation noise.
            if (widthDelta <= 2 && heightDelta <= 2)
            {
                var output = new Image<Rgba32>(targetWidth, targetHeight, new Rgba32(0, 0, 0, 255));
                int copyWidth = Math.Min(targetWidth, screenshot.Width);
                int copyHeight = Math.Min(targetHeight, screenshot.Height);

                int sourceOffsetX = (screenshot.Width - copyWidth) / 2;
                int sourceOffsetY = (screenshot.Height - copyHeight) / 2;
                int targetOffsetX = (targetWidth - copyWidth) / 2;
                int targetOffsetY = (targetHeight - copyHeight) / 2;

                for (int y = 0; y < copyHeight; y++)
                {
                    for (int x = 0; x < copyWidth; x++)
                    {
                        output[targetOffsetX + x, targetOffsetY + y] =
                            screenshot[sourceOffsetX + x, sourceOffsetY + y];
                    }
                }

                return output;
            }

            var resized = screenshot.Clone();
            resized.Mutate(x => x.Resize(targetWidth, targetHeight));
            return resized;
        }

        private static bool isNearBlackFrame(Image<Rgba32> image)
        {
            long total = 0;
            int litPixels = 0;
            int pixelCount = image.Width * image.Height;
            if (pixelCount <= 0)
                return true;

            for (int y = 0; y < image.Height; y++)
            {
                for (int x = 0; x < image.Width; x++)
                {
                    var pixel = image[x, y];
                    int brightness = pixel.R + pixel.G + pixel.B;
                    total += brightness;
                    if (brightness >= 24)
                        litPixels++;
                }
            }

            double meanRgb = total / (double)(pixelCount * 3);
            double litPixelRatio = litPixels / (double)pixelCount;

            // Accept dark UI scenes (for example intro/menu backgrounds) while still rejecting
            // genuinely blank captures that contain almost no lit pixels.
            return meanRgb < 0.6 && litPixelRatio < 0.00008;
        }

        /// <summary>
        /// Detects likely NVIDIA/driver overlay hints appearing in the top-right corner.
        /// These are external to BeatSight and should be treated as transient capture noise.
        /// </summary>
        private static bool hasLikelyExternalOverlayHint(Image<Rgba32> image)
        {
            int regionWidth = Math.Clamp((int)(image.Width * 0.28f), 220, 520);
            int regionHeight = Math.Clamp((int)(image.Height * 0.22f), 110, 260);
            int startX = Math.Max(0, image.Width - regionWidth);
            int endX = image.Width;
            int endY = Math.Min(image.Height, regionHeight);

            int brightPixels = 0;
            int greenPixels = 0;
            int redPixels = 0;
            int total = Math.Max(1, (endX - startX) * endY);

            for (int y = 0; y < endY; y++)
            {
                for (int x = startX; x < endX; x++)
                {
                    Rgba32 pixel = image[x, y];
                    int max = Math.Max(pixel.R, Math.Max(pixel.G, pixel.B));
                    int min = Math.Min(pixel.R, Math.Min(pixel.G, pixel.B));
                    int saturation = max - min;

                    if (max >= 72)
                        brightPixels++;

                    if (pixel.G >= 130 && pixel.R <= 130 && pixel.B <= 130 && saturation >= 55)
                        greenPixels++;

                    if (pixel.R >= 130 && pixel.G <= 85 && pixel.B <= 85 && saturation >= 55)
                        redPixels++;
                }
            }

            double brightRatio = brightPixels / (double)total;
            double accentRatio = (greenPixels + redPixels) / (double)total;
            return brightRatio >= 0.045 && accentRatio >= 0.012;
        }

        private static void resetFrameworkRandomState()
        {
            try
            {
                Type rngType = typeof(RNG);
                var flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;

                var directReset = rngType.GetMethod("Reset", flags, binder: null, new[] { typeof(int) }, modifiers: null)
                                 ?? rngType.GetMethod("Reset", flags, binder: null, Type.EmptyTypes, modifiers: null);
                if (directReset != null)
                {
                    var args = directReset.GetParameters().Length == 1 ? new object?[] { 1337 } : null;
                    directReset.Invoke(null, args);
                    return;
                }

                var seedMethod = rngType.GetMethods(flags)
                    .FirstOrDefault(m =>
                    {
                        if (!m.IsStatic)
                            return false;

                        if (!(m.Name.Contains("seed", StringComparison.OrdinalIgnoreCase)
                              || m.Name.Contains("reset", StringComparison.OrdinalIgnoreCase)))
                            return false;

                        var parameters = m.GetParameters();
                        return parameters.Length == 1 && parameters[0].ParameterType == typeof(int);
                    });

                if (seedMethod != null)
                {
                    seedMethod.Invoke(null, new object?[] { 1337 });
                    return;
                }

                var randomField = rngType.GetFields(flags)
                    .FirstOrDefault(f => f.FieldType == typeof(Random)
                                         && f.Name.Contains("random", StringComparison.OrdinalIgnoreCase));
                if (randomField != null)
                {
                    randomField.SetValue(null, new Random(1337));
                }
            }
            catch
            {
                // Best effort only.
            }
        }

        private static void safeDispose(IDisposable? disposable)
        {
            if (disposable == null)
                return;

            try
            {
                disposable.Dispose();
            }
            catch (ObjectDisposedException)
            {
                // Already disposed.
            }
            catch (InvalidOperationException)
            {
                // Ignore disposal ordering races from host shutdown.
            }
        }

        private static void ensureHostRunTaskHealthy(Task? runTask, string stage)
        {
            if (runTask == null)
                return;

            if (runTask.IsFaulted)
            {
                Exception? root = runTask.Exception?.GetBaseException() ?? runTask.Exception;
                throw new VisualCaptureUnavailableException(
                    $"Visual host task faulted during {stage}: {root?.Message ?? "unknown fault"}",
                    root);
            }

            if (runTask.IsCanceled)
                throw new VisualCaptureUnavailableException($"Visual host task cancelled during {stage}.");

            if (runTask.IsCompleted)
                throw new VisualCaptureUnavailableException($"Visual host task completed unexpectedly during {stage}.");
        }
    }
}
