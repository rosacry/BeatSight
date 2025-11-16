using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Drawing;
using System.Linq;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.AI;
using BeatSight.Game.AI.Generation;
using BeatSight.Game.Audio;
using BeatSight.Game.Configuration;
using BeatSight.Game.Customization;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Mapping;
using BeatSight.Game.Services.Analysis;
using BeatSight.Game.Services.Decode;
using BeatSight.Game.Services.Generation;
using BeatSight.Game.Services.Separation;
using osu.Framework.Audio;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Configuration;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Logging;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Platform;
using osu.Framework.IO.Stores;
using FrameworkWindowState = osu.Framework.Platform.WindowState;

namespace BeatSight.Game
{
    public partial class BeatSightGame : osu.Framework.Game
    {
        private ScreenStack screenStack = null!;
        private DependencyContainer dependencies = null!;
        [Resolved(CanBeNull = true)]
        private AudioManager? audioManager { get; set; }

        private AudioEngine audioEngine = null!;
        private GenerationPipeline generationPipeline = null!;
        private GenerationCoordinator generationCoordinator = null!;
        private bool audioAttached;
        private IResourceStore<byte[]>? embeddedResourceStore;

        private IWindow? boundWindow;
        private Bindable<int>? windowWidthSetting;
        private Bindable<int>? windowHeightSetting;
        private Bindable<bool>? windowFullscreenSetting;
        private Bindable<int>? windowDisplaySetting;
        private Bindable<bool>? frameLimiterEnabledSetting;
        private Bindable<double>? frameLimiterTargetSetting;
        private Bindable<Display>? hostDisplayBindable;
        private Bindable<WindowMode>? hostWindowModeBindable;
        private bool suppressWindowFeedback;
        private double defaultMaxDrawHz;
        private double defaultMaxUpdateHz;
        private System.Drawing.Size lastWindowedClientSize = System.Drawing.Size.Empty;
        private FrameworkWindowState lastWindowState = FrameworkWindowState.Normal;

        protected override IReadOnlyDependencyContainer CreateChildDependencies(IReadOnlyDependencyContainer parent) =>
            dependencies = new DependencyContainer(base.CreateChildDependencies(parent));

        private FpsCounter fpsCounter = null!;

        private const string audioImportsDirectory = "AudioImports";
        private static readonly string[] supportedAudioExtensions = { ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac" };

        [BackgroundDependencyLoader]
        private void load()
        {
            // Initialize configuration
            var config = new BeatSightConfigManager(Host.Storage);
            dependencies.Cache(config);

            var aiGenerator = new AiBeatmapGenerator(Host);
            dependencies.Cache(aiGenerator);

            audioEngine = new AudioEngine();
            dependencies.Cache(audioEngine);

            embeddedResourceStore = new NamespacedResourceStore<byte[]>(new DllResourceStore(typeof(BeatSightGame).Assembly), "BeatSight.Game.Resources");
            Resources.AddStore(embeddedResourceStore);

            var decodeService = new DecodeService();
            dependencies.Cache(decodeService);

            var onsetDetectionService = new OnsetDetectionService();
            dependencies.Cache(onsetDetectionService);

            generationPipeline = new GenerationPipeline(audioEngine, decodeService, onsetDetectionService, aiGenerator, new DemucsExternalProcessBackend(), new PassthroughBackend());
            dependencies.Cache(generationPipeline);
            dependencies.CacheAs<IGenerationPipeline>(generationPipeline);

            generationCoordinator = new GenerationCoordinator(generationPipeline, action => Schedule(action));
            dependencies.CacheAs<IGenerationCoordinator>(generationCoordinator);

            // Initialize the game
            Children = new Drawable[]
            {
                screenStack = new ScreenStack { RelativeSizeAxes = Axes.Both },
                fpsCounter = new FpsCounter()
            };

            // Bind FPS counter visibility
            config.GetBindable<bool>(BeatSightSetting.ShowFpsCounter)
                .BindValueChanged(e =>
                {
                    fpsCounter.AlwaysPresent = e.NewValue;
                    fpsCounter.FadeTo(e.NewValue ? 1f : 0f, 200, Easing.OutQuint);
                }, true);
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (boundWindow == null)
                initialiseWindowBindings(dependencies.Get<BeatSightConfigManager>());

            if (Host.Window != null)
            {
                Host.Window.DragDrop += onWindowDragDrop;
                Host.Window.CursorConfineRect = null;
                Host.Window.CursorState = CursorState.Default;
            }

            ensureCursorSettings();

            bootstrapDefaultUserAssets();

            Logger.Log("If you use a graphics tablet, lift the pen off the surface while BeatSight is running to prevent the cursor from being held in place.", LoggingTarget.Runtime, LogLevel.Important);

            // Load the main menu
            screenStack.Push(new Screens.MainMenuScreen());
        }

        private void bootstrapDefaultUserAssets()
        {
            if (embeddedResourceStore == null)
                return;

            try
            {
                ensureUserDirectory(UserAssetDirectories.MetronomeSounds);
                ensureUserDirectory(UserAssetDirectories.Skins);
                ensureUserDirectory(UserAssetDirectories.Songs);

                MetronomeSampleBootstrap.EnsureDefaults(Host.Storage, embeddedResourceStore, UserAssetDirectories.MetronomeSounds);
                NoteSkinBootstrap.EnsureDefaults(Host.Storage, embeddedResourceStore, UserAssetDirectories.Skins);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to seed default user assets: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private void initialiseWindowBindings(BeatSightConfigManager config)
        {
            if (Host.Window == null)
                return;

            if (boundWindow != null)
                return;

            boundWindow = Host.Window;

            defaultMaxDrawHz = Host.MaximumDrawHz;
            defaultMaxUpdateHz = Host.MaximumUpdateHz;

            windowWidthSetting = config.GetBindable<int>(BeatSightSetting.WindowWidth);
            windowHeightSetting = config.GetBindable<int>(BeatSightSetting.WindowHeight);
            windowFullscreenSetting = config.GetBindable<bool>(BeatSightSetting.WindowFullscreen);
            windowDisplaySetting = config.GetBindable<int>(BeatSightSetting.WindowDisplayIndex);
            frameLimiterEnabledSetting = config.GetBindable<bool>(BeatSightSetting.FrameLimiterEnabled);
            frameLimiterTargetSetting = config.GetBindable<double>(BeatSightSetting.FrameLimiterTarget);

            lastWindowState = boundWindow.WindowState;
            if (lastWindowState == FrameworkWindowState.Normal)
            {
                lastWindowedClientSize = boundWindow.ClientSize;
            }
            else
            {
                int initialWidth = Math.Max(960, windowWidthSetting.Value);
                int initialHeight = Math.Max(540, windowHeightSetting.Value);
                lastWindowedClientSize = new Size(initialWidth, initialHeight);
            }

            windowWidthSetting.BindValueChanged(_ => applyWindowSize());
            windowHeightSetting.BindValueChanged(_ => applyWindowSize());
            windowFullscreenSetting.BindValueChanged(_ => applyWindowMode());
            windowDisplaySetting.BindValueChanged(_ => applyMonitorSelection());
            frameLimiterEnabledSetting.BindValueChanged(_ => applyFrameLimiter());
            frameLimiterTargetSetting.BindValueChanged(_ => applyFrameLimiter());

            hostDisplayBindable = boundWindow.CurrentDisplayBindable;
            hostDisplayBindable.BindValueChanged(onHostDisplayChanged);

            hostWindowModeBindable = boundWindow.WindowMode;
            bool hostStartsFullscreen = hostWindowModeBindable.Value != WindowMode.Windowed;

            if (windowFullscreenSetting.Value != hostStartsFullscreen)
            {
                suppressWindowFeedback = true;
                try
                {
                    windowFullscreenSetting.Value = hostStartsFullscreen;
                }
                finally
                {
                    suppressWindowFeedback = false;
                }
            }

            hostWindowModeBindable.BindValueChanged(onHostWindowModeChanged);

            boundWindow.Resized += onWindowResized;
            boundWindow.DisplaysChanged += onWindowDisplaysChanged;
            boundWindow.WindowStateChanged += onWindowStateChanged;

            applyMonitorSelection();
            applyWindowMode();
            applyWindowSize();
            applyFrameLimiter();
        }

        private void ensureUserDirectory(string relativePath)
        {
            try
            {
                string path = Host.Storage.GetFullPath(relativePath);
                Directory.CreateDirectory(path);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to prepare user directory '{relativePath}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private void applyWindowSize()
        {
            if (boundWindow == null || windowWidthSetting == null || windowHeightSetting == null)
                return;

            if (suppressWindowFeedback)
                return;

            if (windowFullscreenSetting?.Value == true)
                return;

            int width = Math.Max(960, windowWidthSetting.Value);
            int height = Math.Max(540, windowHeightSetting.Value);

            var minSize = boundWindow.MinSize;
            if (minSize.Width > 0)
                width = Math.Max(width, minSize.Width);
            if (minSize.Height > 0)
                height = Math.Max(height, minSize.Height);

            if (hostDisplayBindable != null)
            {
                var bounds = hostDisplayBindable.Value.Bounds;
                if (bounds.Width > 0)
                    width = Math.Min(width, bounds.Width);
                if (bounds.Height > 0)
                    height = Math.Min(height, bounds.Height);
            }

            var desired = sanitiseWindowSize(new Size(width, height));
            lastWindowedClientSize = desired;

            if (boundWindow.WindowState != FrameworkWindowState.Normal)
                return;

            if (boundWindow.ClientSize == desired)
                return;

            suppressWindowFeedback = true;
            try
            {
                var originalMin = boundWindow.MinSize;
                var originalMax = boundWindow.MaxSize;

                boundWindow.MinSize = desired;
                boundWindow.MaxSize = desired;

                Schedule(() =>
                {
                    if (boundWindow == null)
                        return;

                    boundWindow.MinSize = originalMin;
                    boundWindow.MaxSize = originalMax;

                    centerWindowOnCurrentDisplay(desired, applySize: true);
                });
            }
            finally
            {
                suppressWindowFeedback = false;
            }
        }

        private void applyWindowMode()
        {
            if (boundWindow == null || windowFullscreenSetting == null)
                return;

            var desiredMode = windowFullscreenSetting.Value ? WindowMode.Borderless : WindowMode.Windowed;

            if (hostWindowModeBindable != null && hostWindowModeBindable.Value != desiredMode)
            {
                suppressWindowFeedback = true;
                try
                {
                    hostWindowModeBindable.Value = desiredMode;
                }
                finally
                {
                    suppressWindowFeedback = false;
                }
            }

            if (windowFullscreenSetting.Value)
            {
                if (boundWindow.WindowState == FrameworkWindowState.Normal)
                    lastWindowedClientSize = sanitiseWindowSize(boundWindow.ClientSize);

                var displayBounds = getCurrentDisplayBounds();
                suppressWindowFeedback = true;
                try
                {
                    applyBorderlessBounds(displayBounds);
                    boundWindow.WindowState = FrameworkWindowState.Maximised;
                }
                finally
                {
                    suppressWindowFeedback = false;
                }
            }
            else
            {
                suppressWindowFeedback = true;
                try
                {
                    boundWindow.WindowState = FrameworkWindowState.Normal;
                }
                finally
                {
                    suppressWindowFeedback = false;
                }

                applyWindowSize();
            }
        }

        private void applyMonitorSelection()
        {
            if (boundWindow == null || windowDisplaySetting == null)
                return;

            var displays = boundWindow.Displays;
            if (displays.Length == 0)
                return;

            int clampedIndex = Math.Clamp(windowDisplaySetting.Value, 0, displays.Length - 1);

            if (clampedIndex != windowDisplaySetting.Value)
            {
                suppressWindowFeedback = true;
                try
                {
                    windowDisplaySetting.Value = clampedIndex;
                }
                finally
                {
                    suppressWindowFeedback = false;
                }
            }

            if (hostDisplayBindable == null)
                return;

            var targetDisplay = displays[clampedIndex];

            if (hostDisplayBindable.Value.Index == targetDisplay.Index)
                return;

            suppressWindowFeedback = true;
            try
            {
                hostDisplayBindable.Value = targetDisplay;
            }
            finally
            {
                suppressWindowFeedback = false;
            }

            Schedule(() =>
            {
                if (boundWindow == null)
                    return;

                centerWindowOnCurrentDisplay(boundWindow.ClientSize, applySize: false);
            });
        }

        private void applyFrameLimiter()
        {
            if (frameLimiterEnabledSetting == null || frameLimiterTargetSetting == null)
                return;

            double target = Math.Clamp(frameLimiterTargetSetting.Value, 30, 1000);

            if (frameLimiterEnabledSetting.Value)
            {
                Host.MaximumDrawHz = target;
                Host.MaximumUpdateHz = target;
            }
            else
            {
                Host.MaximumDrawHz = defaultMaxDrawHz;
                Host.MaximumUpdateHz = defaultMaxUpdateHz;
            }
        }

        private void onHostDisplayChanged(ValueChangedEvent<Display> e)
        {
            if (windowDisplaySetting == null)
                return;

            if (suppressWindowFeedback)
                return;

            suppressWindowFeedback = true;
            try
            {
                if (windowDisplaySetting.Value != e.NewValue.Index)
                    windowDisplaySetting.Value = e.NewValue.Index;
            }
            finally
            {
                suppressWindowFeedback = false;
            }
        }

        private void onHostWindowModeChanged(ValueChangedEvent<WindowMode> e)
        {
            if (windowFullscreenSetting == null)
                return;

            if (suppressWindowFeedback)
                return;

            bool isFullscreen = e.NewValue != WindowMode.Windowed;

            if (isFullscreen && boundWindow != null && windowFullscreenSetting.Value == false)
                lastWindowedClientSize = sanitiseWindowSize(boundWindow.ClientSize);

            suppressWindowFeedback = true;
            try
            {
                if (windowFullscreenSetting.Value != isFullscreen)
                    windowFullscreenSetting.Value = isFullscreen;
            }
            finally
            {
                suppressWindowFeedback = false;
            }
        }

        private void onWindowResized()
        {
            if (boundWindow == null || windowWidthSetting == null || windowHeightSetting == null)
                return;

            if (suppressWindowFeedback)
                return;

            if (windowFullscreenSetting?.Value == true)
                return;

            if (boundWindow.WindowState != FrameworkWindowState.Normal)
                return;

            var currentSize = boundWindow.ClientSize;
            var sanitised = sanitiseWindowSize(currentSize);
            bool needsReapply = !sizesApproximatelyEqual(currentSize, sanitised);

            if (needsReapply)
                currentSize = sanitised;

            lastWindowedClientSize = currentSize;

            suppressWindowFeedback = true;
            try
            {
                if (windowWidthSetting.Value != currentSize.Width)
                    windowWidthSetting.Value = currentSize.Width;
                if (windowHeightSetting.Value != currentSize.Height)
                    windowHeightSetting.Value = currentSize.Height;
            }
            finally
            {
                suppressWindowFeedback = false;
            }

            if (needsReapply)
                Schedule(() => applyWindowSize());
        }

        private void onWindowDisplaysChanged(IEnumerable<Display> displays)
        {
            if (windowDisplaySetting == null)
                return;

            if (displays == null)
                return;

            var displayList = displays.ToList();

            if (displayList.Count == 0)
                return;

            int clampedIndex = Math.Clamp(windowDisplaySetting.Value, 0, displayList.Count - 1);

            if (windowDisplaySetting.Value != clampedIndex)
            {
                suppressWindowFeedback = true;
                try
                {
                    windowDisplaySetting.Value = clampedIndex;
                }
                finally
                {
                    suppressWindowFeedback = false;
                }
            }

            applyMonitorSelection();
        }

        private void onWindowStateChanged(FrameworkWindowState state)
        {
            if (boundWindow == null || windowFullscreenSetting == null)
                return;

            var previousState = lastWindowState;
            lastWindowState = state;

            if (state == FrameworkWindowState.Normal && previousState != FrameworkWindowState.Normal)
            {
                Schedule(() =>
                {
                    if (boundWindow == null)
                        return;

                    applyWindowSize();
                });
            }
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);

            if (Host.Window != null)
                Host.Window.DragDrop -= onWindowDragDrop;

            if (boundWindow != null)
            {
                boundWindow.Resized -= onWindowResized;
                boundWindow.DisplaysChanged -= onWindowDisplaysChanged;
                boundWindow.WindowStateChanged -= onWindowStateChanged;
            }

            hostDisplayBindable?.UnbindAll();
            hostWindowModeBindable?.UnbindAll();
            boundWindow = null;

            dependencies?.Get<BeatSightConfigManager>()?.Dispose();
            generationCoordinator?.Dispose();
            generationPipeline?.Dispose();
            audioEngine?.Dispose();
        }

        private void onWindowDragDrop(string path)
        {
            Schedule(() => handleFileDrop(path));
        }

        private void handleFileDrop(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
                return;

            string extension = Path.GetExtension(path).ToLowerInvariant();
            if (Array.IndexOf(supportedAudioExtensions, extension) < 0)
            {
                Logger.Log($"Ignored dropped file '{path}' (unsupported extension)", LoggingTarget.Runtime, LogLevel.Important);
                return;
            }

            Task.Run(async () =>
            {
                try
                {
                    var imported = await importAudioFileAsync(path, CancellationToken.None).ConfigureAwait(false);
                    Schedule(() => screenStack.Push(new MappingChoiceScreen(imported)));
                }
                catch (Exception ex)
                {
                    Logger.Error(ex, $"Failed to import dropped file '{path}'");
                }
            });
        }

        private void ensureCursorSettings()
        {
            const string frameworkConfigFile = "framework.ini";

            try
            {
                using var stream = Host.Storage.GetStream(frameworkConfigFile, FileAccess.ReadWrite, FileMode.OpenOrCreate);
                using var reader = new StreamReader(stream, leaveOpen: true);
                var lines = new List<string>();

                string? line;
                while ((line = reader.ReadLine()) != null)
                    lines.Add(line);

                bool changed = false;
                changed |= upsertConfigValue(lines, "WindowMode", "Windowed");
                changed |= upsertConfigValue(lines, "Fullscreen", "False");
                changed |= upsertConfigValue(lines, "ConfineMouseMode", "Fullscreen");
                changed |= upsertConfigValue(lines, "MapAbsoluteInputToWindow", "False");
                changed |= upsertConfigValue(lines, "IgnoredInputHandlers", string.Empty);

                if (changed)
                {
                    stream.SetLength(0);
                    stream.Seek(0, SeekOrigin.Begin);

                    using var writer = new StreamWriter(stream, leaveOpen: true);
                    foreach (var entry in lines)
                        writer.WriteLine(entry);

                    writer.Flush();
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to normalise cursor settings: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private static bool upsertConfigValue(List<string> lines, string key, string value)
        {
            string newLine = $"{key} = {value}";
            string prefix = key + " =";

            for (int i = 0; i < lines.Count; i++)
            {
                if (!lines[i].StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    continue;

                if (string.Equals(lines[i].Trim(), newLine, StringComparison.OrdinalIgnoreCase))
                    return false;

                lines[i] = newLine;
                return true;
            }

            lines.Add(newLine);
            return true;
        }

        private async Task<ImportedAudioTrack> importAudioFileAsync(string path, CancellationToken cancellationToken)
        {
            string importRoot = Host.Storage.GetFullPath(audioImportsDirectory);
            Directory.CreateDirectory(importRoot);

            string safeName = ImportedAudioTrack.CreateSafeFileName(path);
            string targetPath = Path.Combine(importRoot, safeName);

            int attempt = 1;
            while (File.Exists(targetPath))
            {
                string candidate = Path.GetFileNameWithoutExtension(safeName) + $"_{attempt}" + Path.GetExtension(safeName);
                targetPath = Path.Combine(importRoot, candidate);
                attempt++;
            }

            const int bufferSize = 81920;
            await using (var source = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, bufferSize, FileOptions.Asynchronous))
            await using (var destination = new FileStream(targetPath, FileMode.CreateNew, FileAccess.Write, FileShare.None, bufferSize, FileOptions.Asynchronous))
            {
                await source.CopyToAsync(destination, cancellationToken).ConfigureAwait(false);
            }

            string relativePath = Path.Combine(audioImportsDirectory, Path.GetFileName(targetPath)).Replace(Path.DirectorySeparatorChar, '/');
            double? duration = await audioEngine.ComputeDurationFromFileAsync(targetPath, cancellationToken).ConfigureAwait(false);
            var info = new FileInfo(targetPath);

            string displayName = Path.GetFileNameWithoutExtension(path);
            return new ImportedAudioTrack(path, targetPath, relativePath, displayName, info.Length, duration);
        }

        protected override void Update()
        {
            base.Update();

            if (!audioAttached && audioManager != null)
            {
                audioEngine.Attach(audioManager);
                audioAttached = true;
            }

            if (Host.Window != null)
            {
                if (Host.Window.CursorState != CursorState.Default)
                    Host.Window.CursorState = CursorState.Default;

                if (Host.Window.CursorConfineRect != null)
                    Host.Window.CursorConfineRect = null;
            }

        }

        private void centerWindowOnCurrentDisplay(Size windowSize, bool applySize)
        {
            if (boundWindow == null)
                return;

            if (windowFullscreenSetting?.Value == true)
                return;

            if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
                return;

            if (boundWindow.WindowState == FrameworkWindowState.Maximised || boundWindow.WindowState == FrameworkWindowState.Fullscreen)
                return;

            Rectangle bounds;

            if (hostDisplayBindable != null)
                bounds = hostDisplayBindable.Value.Bounds;
            else
                bounds = boundWindow.PrimaryDisplay.Bounds;

            int x = bounds.X + Math.Max(0, (bounds.Width - windowSize.Width) / 2);
            int y = bounds.Y + Math.Max(0, (bounds.Height - windowSize.Height) / 2);

            IntPtr handle = NativeWindowHelpers.GetWindowHandle(boundWindow);
            if (handle == IntPtr.Zero)
                return;

            suppressWindowFeedback = true;
            try
            {
                if (!NativeWindowHelpers.SetWindowBounds(handle, x, y, windowSize.Width, windowSize.Height, applySize))
                {
                    int error = Marshal.GetLastWin32Error();
                    Logger.Log($"Failed to reposition window: {error}", LoggingTarget.Runtime, LogLevel.Debug);
                }
            }
            finally
            {
                suppressWindowFeedback = false;
            }
        }

        private void applyBorderlessBounds(Rectangle bounds)
        {
            if (boundWindow == null)
                return;

            if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
                return;

            IntPtr handle = NativeWindowHelpers.GetWindowHandle(boundWindow);
            if (handle == IntPtr.Zero)
                return;

            if (!NativeWindowHelpers.SetWindowBounds(handle, bounds.X, bounds.Y, bounds.Width, bounds.Height, applySize: true))
            {
                int error = Marshal.GetLastWin32Error();
                Logger.Log($"Failed to apply borderless bounds: {error}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private Size sanitiseWindowSize(Size requestedSize)
        {
            var bounds = getCurrentDisplayBounds();

            int maxWidth = bounds.Width > 0 ? bounds.Width : int.MaxValue;
            int maxHeight = bounds.Height > 0 ? bounds.Height : int.MaxValue;

            int width = Math.Clamp(requestedSize.Width, 960, maxWidth);
            int height = Math.Clamp(requestedSize.Height, 540, maxHeight);

            double aspect = getCurrentDisplayAspectRatio();

            if (aspect > 0 && maxWidth < int.MaxValue && maxHeight < int.MaxValue)
            {
                int heightFromWidth = (int)Math.Round(width / aspect);
                int widthFromHeight = (int)Math.Round(height * aspect);

                if (Math.Abs(heightFromWidth - height) <= Math.Abs(widthFromHeight - width))
                    height = Math.Clamp(heightFromWidth, 540, maxHeight);
                else
                    width = Math.Clamp(widthFromHeight, 960, maxWidth);
            }

            return new Size(width, height);
        }

        private Rectangle getCurrentDisplayBounds()
        {
            if (hostDisplayBindable != null)
                return hostDisplayBindable.Value.Bounds;

            if (boundWindow != null)
                return boundWindow.PrimaryDisplay.Bounds;

            if (lastWindowedClientSize.Width > 0 && lastWindowedClientSize.Height > 0)
                return new Rectangle(0, 0, lastWindowedClientSize.Width, lastWindowedClientSize.Height);

            return new Rectangle(0, 0, 1920, 1080);
        }

        private double getCurrentDisplayAspectRatio()
        {
            var bounds = getCurrentDisplayBounds();
            if (bounds.Height > 0)
                return (double)bounds.Width / bounds.Height;

            if (lastWindowedClientSize.Height > 0)
                return (double)lastWindowedClientSize.Width / lastWindowedClientSize.Height;

            return 16d / 9d;
        }

        private static bool sizesApproximatelyEqual(Size a, Size b)
        {
            return Math.Abs(a.Width - b.Width) <= 1 && Math.Abs(a.Height - b.Height) <= 1;
        }

        private static class NativeWindowHelpers
        {
            private const uint SWP_NOSIZE = 0x0001;
            private const uint SWP_NOZORDER = 0x0004;
            private const uint SWP_NOOWNERZORDER = 0x0200;
            private const uint SWP_NOACTIVATE = 0x0010;

            private const int GWL_STYLE = -16;
            private const int GWL_EXSTYLE = -20;

            [StructLayout(LayoutKind.Sequential)]
            private struct RECT
            {
                public int Left;
                public int Top;
                public int Right;
                public int Bottom;
            }

            [DllImport("user32.dll", SetLastError = true)]
            private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

            [DllImport("user32.dll", SetLastError = true)]
            private static extern bool AdjustWindowRectEx(ref RECT lpRect, uint dwStyle, bool bMenu, uint dwExStyle);

            [DllImport("user32.dll", SetLastError = true)]
            private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

            public static bool SetWindowBounds(IntPtr windowHandle, int x, int y, int clientWidth, int clientHeight, bool applySize)
            {
                uint flags = SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE;

                int width = 0;
                int height = 0;

                if (applySize)
                {
                    RECT rect = new RECT
                    {
                        Left = 0,
                        Top = 0,
                        Right = clientWidth,
                        Bottom = clientHeight
                    };

                    uint style = (uint)GetWindowLong(windowHandle, GWL_STYLE);
                    uint exStyle = (uint)GetWindowLong(windowHandle, GWL_EXSTYLE);

                    if (!AdjustWindowRectEx(ref rect, style, bMenu: false, exStyle))
                        return false;

                    width = rect.Right - rect.Left;
                    height = rect.Bottom - rect.Top;
                }
                else
                {
                    flags |= SWP_NOSIZE;
                }

                return SetWindowPos(windowHandle, IntPtr.Zero, x, y, width, height, flags);
            }

            public static IntPtr GetWindowHandle(IWindow window)
            {
                var type = window.GetType();
                var handleProperty = type.GetProperty("WindowHandle", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (handleProperty != null)
                {
                    var value = handleProperty.GetValue(window);
                    if (value is IntPtr propertyHandle)
                        return propertyHandle;
                    if (value is long longHandle)
                        return new IntPtr(longHandle);
                }

                var method = type.GetMethod("get_WindowHandle", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (method != null)
                {
                    var value = method.Invoke(window, null);
                    if (value is IntPtr methodHandle)
                        return methodHandle;
                    if (value is long longHandle)
                        return new IntPtr(longHandle);
                }

                return IntPtr.Zero;
            }
        }
    }

    public partial class FpsCounter : CompositeDrawable
    {
        private SpriteText fpsText = null!;
        private int frameCount;
        private double elapsed;

        public FpsCounter()
        {
            Anchor = Anchor.TopRight;
            Origin = Anchor.TopRight;
            Margin = new MarginPadding(10);
            AutoSizeAxes = Axes.Both;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChildren = new Drawable[]
            {
                new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 5,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(0, 0, 0, 180)
                        },
                        fpsText = new SpriteText
                        {
                            Text = "FPS: 0",
                            Font = new FontUsage(size: 18, weight: "Bold"),
                            Colour = Color4.White,
                            Padding = new MarginPadding { Horizontal = 10, Vertical = 5 }
                        }
                    }
                }
            };
        }

        protected override void Update()
        {
            base.Update();

            frameCount++;
            elapsed += Clock.ElapsedFrameTime;

            if (elapsed >= 500) // Update every 500ms
            {
                int fps = (int)(frameCount / (elapsed / 1000));
                fpsText.Text = $"FPS: {fps}";

                // Color code based on performance
                if (fps >= 60)
                    fpsText.Colour = new Color4(120, 255, 120, 255);
                else if (fps >= 30)
                    fpsText.Colour = new Color4(255, 215, 0, 255);
                else
                    fpsText.Colour = new Color4(255, 100, 100, 255);

                frameCount = 0;
                elapsed = 0;
            }
        }
    }
}
