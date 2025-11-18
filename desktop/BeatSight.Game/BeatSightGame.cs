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
using System.Globalization;
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
using BeatSight.Game.UI.Theming;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
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
        private Container uiScaleRoot = null!;
        private DependencyContainer dependencies = null!;
        [Resolved(CanBeNull = true)]
        private AudioManager? audioManager { get; set; }
        [Resolved]
        private FrameworkConfigManager frameworkConfig { get; set; } = null!;

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
        private Bindable<double>? uiScaleSetting;
        private Bindable<Display>? hostDisplayBindable;
        private Bindable<WindowMode>? hostWindowModeBindable;
        private Bindable<Size>? frameworkFullscreenSizeSetting;
        private bool suppressWindowFeedback;
        private double defaultMaxDrawHz;
        private double defaultMaxUpdateHz;
        private System.Drawing.Size lastWindowedClientSize = System.Drawing.Size.Empty;
        private FrameworkWindowState lastWindowState = FrameworkWindowState.Normal;
        private bool windowHandleWarningLogged;
        private bool windowResizeFailureLogged;
        private bool windowManagedResizeWarningLogged;
        private bool applyingWindowSizeInProgress;
        private bool windowSizeReapplyPending; // ensures batched setting updates (width/height) finish with latest size
        private bool lastRequestedFullscreen;

        private static readonly BindingFlags windowReflectionFlags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy;
        private static readonly string[] windowSizePropertyPreferredNames =
        {
            "ClientSize",
            "WindowSize",
            "Size",
            "RenderSize",
            "PreferredSize",
            "RequestedSize",
            "DesiredSize",
            "Resolution"
        };

        private static readonly string[] windowSizePropertyTokens =
        {
            "size",
            "resolution",
            "dimensions"
        };

        private static readonly string[] windowSizeMethodPreferredNames =
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

        private static readonly string[] windowSizeMethodTokens =
        {
            "resize",
            "size",
            "resolution",
            "dimensions"
        };

        protected override IReadOnlyDependencyContainer CreateChildDependencies(IReadOnlyDependencyContainer parent) =>
            dependencies = new DependencyContainer(base.CreateChildDependencies(parent));

        private FpsCounter fpsCounter = null!;

        private const string audioImportsDirectory = "AudioImports";
        private static readonly string[] supportedAudioExtensions = { ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac" };
        private static readonly string[] bundledFonts =
        {
            "Fonts/Exo2/Exo2-Regular",
            "Fonts/Exo2/Exo2-Medium",
            "Fonts/Exo2/Exo2-SemiBold",
            "Fonts/Exo2/Exo2-Bold",
            "Fonts/Nunito/Nunito-Light",
            "Fonts/Nunito/Nunito-Regular",
            "Fonts/Nunito/Nunito-Medium",
            "Fonts/Nunito/Nunito-SemiBold"
        };

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
            registerFonts();

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
                uiScaleRoot = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Child = screenStack = new ScreenStack { RelativeSizeAxes = Axes.Both }
                },
                fpsCounter = new FpsCounter()
            };

            uiScaleSetting = config.GetBindable<double>(BeatSightSetting.UIScale);
            uiScaleSetting.BindValueChanged(onUiScaleChanged, true);

            // Bind FPS counter visibility
            config.GetBindable<bool>(BeatSightSetting.ShowFpsCounter)
                .BindValueChanged(e =>
                {
                    fpsCounter.AlwaysPresent = e.NewValue;
                    fpsCounter.FadeTo(e.NewValue ? 1f : 0f, 200, Easing.OutQuint);
                }, true);
        }

        private void registerFonts()
        {
            if (embeddedResourceStore == null)
            {
                Logger.Log("Embedded resource store is unavailable; bundled fonts cannot be registered.", LoggingTarget.Runtime, LogLevel.Error);
                return;
            }

            foreach (string font in bundledFonts)
            {
                string resourceKey = getFontResourceKey(font);

                using (var validationStream = Resources.GetStream(resourceKey))
                {
                    if (validationStream == null)
                        Logger.Log($"Font resource '{resourceKey}' missing via Resources store.", LoggingTarget.Runtime, LogLevel.Error);
                    else
                        Logger.Log($"Font resource '{resourceKey}' resolved {validationStream.Length} bytes via Resources store.", LoggingTarget.Runtime, LogLevel.Debug);
                }

                if (!fontResourceExists(resourceKey))
                {
                    Logger.Log($"Font resource '{resourceKey}' is missing from the embedded resources.", LoggingTarget.Runtime, LogLevel.Error);
                    continue;
                }

                try
                {
                    AddFont(Resources, font);
                }
                catch (Exception ex)
                {
                    Logger.Log($"Failed to register font '{font}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Important);
                }
            }
        }

        private void onUiScaleChanged(ValueChangedEvent<double> scaleEvent)
        {
            if (uiScaleRoot == null)
                return;

            float clamped = (float)Math.Clamp(scaleEvent.NewValue, 0.5, 1.5);
            uiScaleRoot.Scale = new Vector2(clamped);
        }

        private static string getFontResourceKey(string font)
        {
            if (font.EndsWith(".ttf", StringComparison.OrdinalIgnoreCase))
                return font;

            return $"{font}.ttf";
        }

        private bool fontResourceExists(string font)
        {
            if (embeddedResourceStore == null)
                return false;

            return embeddedResourceStore.Get(font) != null;
        }

        private WindowMode getPreferredFullscreenMode()
        {
            if (boundWindow == null)
                return WindowMode.Fullscreen;

            var supported = boundWindow.SupportedWindowModes?.ToArray() ?? Array.Empty<WindowMode>();

            if (supported.Contains(WindowMode.Fullscreen))
                return WindowMode.Fullscreen;

            if (supported.Contains(WindowMode.Borderless))
                return WindowMode.Borderless;

            return supported.Contains(WindowMode.Windowed) ? WindowMode.Windowed : WindowMode.Fullscreen;
        }

        private void applyBorderlessFullscreen()
        {
            if (boundWindow == null)
                return;

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

        private void applyFullscreenResolution()
        {
            if (windowWidthSetting == null || windowHeightSetting == null)
                return;

            var resolvedSize = resolveFullscreenSize(windowWidthSetting.Value, windowHeightSetting.Value);

            if (frameworkFullscreenSizeSetting != null && frameworkFullscreenSizeSetting.Value != resolvedSize)
                frameworkFullscreenSizeSetting.Value = resolvedSize;

            if (windowWidthSetting.Value != resolvedSize.Width)
                windowWidthSetting.Value = resolvedSize.Width;

            if (windowHeightSetting.Value != resolvedSize.Height)
                windowHeightSetting.Value = resolvedSize.Height;
        }

        private Size resolveFullscreenSize(int width, int height)
        {
            width = Math.Max(320, width);
            height = Math.Max(240, height);

            Display? display = hostDisplayBindable?.Value ?? boundWindow?.PrimaryDisplay;
            if (display == null)
                return new Size(width, height);

            var modes = display.DisplayModes;

            if (modes != null && modes.Length > 0)
            {
                DisplayMode? exact = null;
                DisplayMode? best = null;

                foreach (var mode in modes)
                {
                    if (mode.Size.Width == width && mode.Size.Height == height)
                    {
                        if (exact == null || mode.RefreshRate > exact.Value.RefreshRate)
                            exact = mode;
                        continue;
                    }

                    if (best == null)
                    {
                        best = mode;
                        continue;
                    }

                    int bestDiff = Math.Abs(best.Value.Size.Width - width) + Math.Abs(best.Value.Size.Height - height);
                    int modeDiff = Math.Abs(mode.Size.Width - width) + Math.Abs(mode.Size.Height - height);

                    if (modeDiff < bestDiff || (modeDiff == bestDiff && mode.RefreshRate > best.Value.RefreshRate))
                        best = mode;
                }

                if (exact != null)
                    return exact.Value.Size;

                if (best != null)
                    return best.Value.Size;

                var fallback = display.FindDisplayMode(new Size(width, height));
                if (fallback.Size.Width > 0 && fallback.Size.Height > 0)
                    return fallback.Size;
            }

            var bounds = display.Bounds;
            if (bounds.Width > 0 && bounds.Height > 0)
                return new Size(Math.Clamp(width, 320, bounds.Width), Math.Clamp(height, 240, bounds.Height));

            return new Size(width, height);
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
            frameworkFullscreenSizeSetting ??= frameworkConfig.GetBindable<Size>(FrameworkSetting.SizeFullscreen);
            lastRequestedFullscreen = windowFullscreenSetting.Value;

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

            ensureDefaultWindowSizeMatchesDisplay();

            hostWindowModeBindable.BindValueChanged(onHostWindowModeChanged);

            boundWindow.Resized += onWindowResized;
            boundWindow.DisplaysChanged += onWindowDisplaysChanged;
            boundWindow.WindowStateChanged += onWindowStateChanged;

            applyMonitorSelection();
            applyWindowMode();

            if (windowFullscreenSetting?.Value != true)
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

            if (windowFullscreenSetting?.Value == true)
            {
                windowSizeReapplyPending = false;
                applyFullscreenResolution();
                return;
            }

            if (suppressWindowFeedback)
            {
                if (applyingWindowSizeInProgress)
                    windowSizeReapplyPending = true;
                return;
            }

            windowSizeReapplyPending = false;

            if (boundWindow.WindowState != FrameworkWindowState.Normal)
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

                Schedule(() =>
                {
                    if (boundWindow == null)
                        return;

                    applyWindowSize();
                });

                return;
            }

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
            applyingWindowSizeInProgress = true;

            Schedule(() =>
            {
                if (boundWindow == null)
                {
                    applyingWindowSizeInProgress = false;
                    suppressWindowFeedback = false;
                    return;
                }

                var originalMin = boundWindow.MinSize;
                var originalMax = boundWindow.MaxSize;

                try
                {
                    boundWindow.MinSize = desired;
                    boundWindow.MaxSize = desired;

                    bool managedResizeApplied = tryApplyManagedWindowSize(desired);

                    if (managedResizeApplied)
                        centerWindowOnCurrentDisplay(desired, applySize: false, logHandleFailure: false);
                    else
                        centerWindowOnCurrentDisplay(desired, applySize: true);
                }
                finally
                {
                    if (boundWindow != null)
                    {
                        boundWindow.MinSize = originalMin;
                        boundWindow.MaxSize = originalMax;
                    }

                    applyingWindowSizeInProgress = false;
                    suppressWindowFeedback = false;

                    if (windowSizeReapplyPending)
                    {
                        windowSizeReapplyPending = false;
                        Schedule(() => applyWindowSize());
                    }
                }
            });
        }

        private void applyWindowMode()
        {
            if (boundWindow == null || windowFullscreenSetting == null)
                return;

            bool wantsFullscreen = windowFullscreenSetting.Value;
            bool wasFullscreenRequested = lastRequestedFullscreen;
            lastRequestedFullscreen = wantsFullscreen;
            bool forceNativeResolution = wantsFullscreen && !wasFullscreenRequested;
            var desiredMode = wantsFullscreen ? getPreferredFullscreenMode() : WindowMode.Windowed;

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

            if (wantsFullscreen)
            {
                if (boundWindow.WindowState == FrameworkWindowState.Normal)
                    lastWindowedClientSize = sanitiseWindowSize(boundWindow.ClientSize);

                if (forceNativeResolution)
                    applyNativeFullscreenResolution();

                applyFullscreenResolution();

                if (desiredMode == WindowMode.Fullscreen)
                    return;

                if (desiredMode == WindowMode.Borderless)
                {
                    applyBorderlessFullscreen();
                    return;
                }

                applyWindowSize();
                return;
            }

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

        private void applyNativeFullscreenResolution()
        {
            if (boundWindow == null || windowWidthSetting == null || windowHeightSetting == null)
                return;

            var targetDisplay = hostDisplayBindable?.Value ?? boundWindow.PrimaryDisplay;
            var bounds = targetDisplay?.Bounds ?? Rectangle.Empty;

            if (bounds.Width <= 0 || bounds.Height <= 0)
                return;

            if (windowWidthSetting.Value == bounds.Width && windowHeightSetting.Value == bounds.Height)
                return;

            suppressWindowFeedback = true;
            try
            {
                if (windowWidthSetting.Value != bounds.Width)
                    windowWidthSetting.Value = bounds.Width;

                if (windowHeightSetting.Value != bounds.Height)
                    windowHeightSetting.Value = bounds.Height;
            }
            finally
            {
                suppressWindowFeedback = false;
            }
        }

        private void ensureDefaultWindowSizeMatchesDisplay()
        {
            if (boundWindow == null || windowWidthSetting == null || windowHeightSetting == null)
                return;

            if (!windowWidthSetting.IsDefault || !windowHeightSetting.IsDefault)
                return;

            if (windowFullscreenSetting?.Value == true)
                return;

            var targetDisplay = hostDisplayBindable?.Value ?? boundWindow.PrimaryDisplay;
            var recommended = calculateRecommendedWindowSize(targetDisplay.Bounds);

            windowWidthSetting.Default = recommended.Width;
            windowHeightSetting.Default = recommended.Height;

            windowWidthSetting.Value = recommended.Width;
            windowHeightSetting.Value = recommended.Height;

            lastWindowedClientSize = recommended;
        }

        private Size calculateRecommendedWindowSize(Rectangle displayBounds)
        {
            const double scale = 0.7;

            if (displayBounds.Width <= 0 || displayBounds.Height <= 0)
                return sanitiseWindowSize(new Size(1024, 576));

            if (displayBounds.Width < 960 || displayBounds.Height < 540)
            {
                int adjustedWidth = Math.Max(320, displayBounds.Width);
                int adjustedHeight = Math.Max(240, displayBounds.Height);
                return new Size(adjustedWidth, adjustedHeight);
            }

            int scaledWidth = Math.Max(960, (int)Math.Round(displayBounds.Width * scale));
            int scaledHeight = Math.Max(540, (int)Math.Round(displayBounds.Height * scale));

            var scaledSize = new Size(scaledWidth, scaledHeight);

            return sanitiseWindowSize(scaledSize);
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

                if (windowFullscreenSetting?.Value == true)
                {
                    applyFullscreenResolution();

                    if (hostWindowModeBindable?.Value == WindowMode.Borderless)
                        applyBorderlessFullscreen();
                }
                else
                {
                    centerWindowOnCurrentDisplay(boundWindow.ClientSize, applySize: false);
                }
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

        private void centerWindowOnCurrentDisplay(Size windowSize, bool applySize, bool logHandleFailure = true)
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
            {
                if (logHandleFailure && !windowHandleWarningLogged)
                {
                    windowHandleWarningLogged = true;
                    Logger.Log("Unable to resolve native window handle; windowed resolution changes may not be applied.", LoggingTarget.Runtime, LogLevel.Debug);
                }

                return;
            }

            suppressWindowFeedback = true;
            try
            {
                if (!NativeWindowHelpers.SetWindowBounds(handle, x, y, windowSize.Width, windowSize.Height, applySize) && !windowResizeFailureLogged)
                {
                    windowResizeFailureLogged = true;
                    int error = Marshal.GetLastWin32Error();
                    Logger.Log($"Failed to apply windowed resolution via native APIs (error {error}).", LoggingTarget.Runtime, LogLevel.Debug);
                }
            }
            finally
            {
                suppressWindowFeedback = false;
            }
        }

        private bool tryApplyManagedWindowSize(Size desired)
        {
            if (boundWindow == null)
                return false;

            var windowType = boundWindow.GetType();

            for (var current = windowType; current != null; current = current.BaseType)
            {
                if (tryApplyManagedWindowSizeToType(boundWindow, current, desired))
                    return true;
            }

            foreach (var interfaceType in windowType.GetInterfaces())
            {
                if (tryApplyManagedWindowSizeToType(boundWindow, interfaceType, desired))
                    return true;
            }

            if (!windowManagedResizeWarningLogged)
            {
                windowManagedResizeWarningLogged = true;
                Logger.Log($"Managed window resize path unavailable on '{windowType.FullName}'. Falling back to native window manipulation.", LoggingTarget.Runtime, LogLevel.Debug);
            }

            return false;
        }

        private bool tryApplyManagedWindowSizeToType(object target, Type reflectionType, Size desired)
        {
            if (reflectionType == null)
                return false;

            if (trySetSizeViaProperties(target, reflectionType, desired))
                return true;

            if (trySetSizeViaMethods(target, reflectionType, desired))
                return true;

            return false;
        }

        private bool trySetSizeViaProperties(object target, Type reflectionType, Size desired)
        {
            foreach (var property in reflectionType.GetProperties(windowReflectionFlags))
            {
                if (!property.CanWrite)
                    continue;

                if (property.GetIndexParameters().Length > 0)
                    continue;

                if (!isLikelySizeProperty(property.Name))
                    continue;

                if (!tryCreateSizeCompatibleValue(desired, property.PropertyType, out var value))
                    continue;

                try
                {
                    property.SetValue(target, value);
                    if (windowClientSizeMatches(desired))
                        return true;
                }
                catch
                {
                    // Ignore and continue probing other properties.
                }
            }

            return false;
        }

        private bool trySetSizeViaMethods(object target, Type reflectionType, Size desired)
        {
            foreach (var method in reflectionType.GetMethods(windowReflectionFlags))
            {
                if (method.IsStatic || method.IsGenericMethod || method.IsSpecialName)
                    continue;

                if (!isLikelySizeMethod(method.Name))
                    continue;

                if (tryInvokeSizeMethod(target, method, desired))
                    return true;
            }

            return false;
        }

        private bool tryInvokeSizeMethod(object target, MethodInfo method, Size desired)
        {
            var parameters = method.GetParameters();

            if (parameters.Length == 1)
            {
                if (parameters[0].IsOut || parameters[0].ParameterType.IsByRef)
                    return false;

                if (!tryCreateSizeCompatibleValue(desired, parameters[0].ParameterType, out var argument))
                    return false;

                try
                {
                    method.Invoke(target, new[] { argument });
                    return windowClientSizeMatches(desired);
                }
                catch
                {
                    return false;
                }
            }

            if (parameters.Length == 2)
            {
                if (parameters[0].IsOut || parameters[0].ParameterType.IsByRef)
                    return false;

                if (parameters[1].IsOut || parameters[1].ParameterType.IsByRef)
                    return false;

                if (!tryConvertDimensionComponent(desired.Width, parameters[0].ParameterType, out var widthArg))
                    return false;

                if (!tryConvertDimensionComponent(desired.Height, parameters[1].ParameterType, out var heightArg))
                    return false;

                try
                {
                    method.Invoke(target, new[] { widthArg, heightArg });
                    return windowClientSizeMatches(desired);
                }
                catch
                {
                    return false;
                }
            }

            return false;
        }

        private static bool tryCreateSizeCompatibleValue(Size size, Type targetType, out object? value)
        {
            var underlying = Nullable.GetUnderlyingType(targetType);
            if (underlying != null)
                return tryCreateSizeCompatibleValue(size, underlying, out value);

            if (targetType == typeof(Size))
            {
                value = size;
                return true;
            }

            if (targetType == typeof(SizeF))
            {
                value = new SizeF(size.Width, size.Height);
                return true;
            }

            if (targetType == typeof(ValueTuple<int, int>))
            {
                value = (size.Width, size.Height);
                return true;
            }

            if (targetType == typeof(ValueTuple<float, float>))
            {
                value = ((float)size.Width, (float)size.Height);
                return true;
            }

            if (targetType == typeof(ValueTuple<double, double>))
            {
                value = ((double)size.Width, (double)size.Height);
                return true;
            }

            if (targetType == typeof(Tuple<int, int>))
            {
                value = Tuple.Create(size.Width, size.Height);
                return true;
            }

            if (targetType == typeof(Tuple<float, float>))
            {
                value = Tuple.Create((float)size.Width, (float)size.Height);
                return true;
            }

            if (targetType == typeof(Tuple<double, double>))
            {
                value = Tuple.Create((double)size.Width, (double)size.Height);
                return true;
            }

            if (targetType.FullName is string fullName)
            {
                switch (fullName)
                {
                    case "osuTK.Vector2i":
                    case "OpenTK.Mathematics.Vector2i":
                    case "osuTK.Vector2I":
                    case "OpenTK.Mathematics.Vector2I":
                        value = Activator.CreateInstance(targetType, size.Width, size.Height);
                        if (value != null)
                            return true;
                        break;
                    case "osuTK.Vector2":
                    case "OpenTK.Mathematics.Vector2":
                    case "System.Numerics.Vector2":
                        value = Activator.CreateInstance(targetType, (float)size.Width, (float)size.Height);
                        if (value != null)
                            return true;
                        break;
                    case "osuTK.Vector2d":
                    case "OpenTK.Mathematics.Vector2d":
                        value = Activator.CreateInstance(targetType, (double)size.Width, (double)size.Height);
                        if (value != null)
                            return true;
                        break;
                    case "System.Drawing.Rectangle":
                        value = new Rectangle(0, 0, size.Width, size.Height);
                        return true;
                    case "System.Drawing.RectangleF":
                        value = new RectangleF(0, 0, size.Width, size.Height);
                        return true;
                }
            }

            if (targetType.IsValueType)
            {
                try
                {
                    value = Activator.CreateInstance(targetType, size.Width, size.Height);
                    if (value != null)
                        return true;
                }
                catch
                {
                    // Ignore and fall through.
                }
            }

            value = null;
            return false;
        }

        private static bool tryConvertDimensionComponent(int component, Type targetType, out object? converted)
        {
            var underlying = Nullable.GetUnderlyingType(targetType) ?? targetType;

            try
            {
                if (underlying == typeof(uint) || underlying == typeof(ulong) || underlying == typeof(ushort) || underlying == typeof(byte))
                {
                    converted = Convert.ChangeType(Math.Max(component, 0), underlying, CultureInfo.InvariantCulture);
                    return true;
                }

                if (underlying == typeof(float) || underlying == typeof(double) || underlying == typeof(decimal))
                {
                    converted = Convert.ChangeType(component, underlying, CultureInfo.InvariantCulture);
                    return true;
                }

                if (underlying == typeof(int) || underlying == typeof(long) || underlying == typeof(short) || underlying == typeof(sbyte))
                {
                    converted = Convert.ChangeType(component, underlying, CultureInfo.InvariantCulture);
                    return true;
                }

                converted = null;
                return false;
            }
            catch
            {
                converted = null;
                return false;
            }
        }

        private static bool isLikelySizeProperty(string? name)
        {
            if (string.IsNullOrEmpty(name))
                return false;

            string lowered = name.ToLowerInvariant();

            if (lowered.Contains("min") || lowered.Contains("max") || lowered.Contains("minimum") || lowered.Contains("maximum") || lowered.Contains("pref") || lowered.Contains("default"))
                return false;

            foreach (var preferred in windowSizePropertyPreferredNames)
            {
                if (string.Equals(preferred, name, StringComparison.OrdinalIgnoreCase))
                    return true;
            }

            foreach (var token in windowSizePropertyTokens)
            {
                if (lowered.Contains(token))
                    return true;
            }

            return false;
        }

        private static bool isLikelySizeMethod(string? name)
        {
            if (string.IsNullOrEmpty(name))
                return false;

            string lowered = name.ToLowerInvariant();

            if (lowered.Contains("min") || lowered.Contains("minimum") || lowered.Contains("max") || lowered.Contains("maximum"))
                return false;

            foreach (var preferred in windowSizeMethodPreferredNames)
            {
                if (string.Equals(preferred, name, StringComparison.OrdinalIgnoreCase))
                    return true;
            }

            foreach (var token in windowSizeMethodTokens)
            {
                if (lowered.Contains(token))
                    return true;
            }

            return false;
        }

        private void applyBorderlessBounds(Rectangle bounds)
        {
            if (boundWindow == null)
                return;

            if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
                return;

            IntPtr handle = NativeWindowHelpers.GetWindowHandle(boundWindow);
            if (handle == IntPtr.Zero)
            {
                if (!windowHandleWarningLogged)
                {
                    windowHandleWarningLogged = true;
                    Logger.Log("Unable to resolve native window handle; windowed resolution changes may not be applied.", LoggingTarget.Runtime, LogLevel.Debug);
                }

                return;
            }

            if (!NativeWindowHelpers.SetWindowBounds(handle, bounds.X, bounds.Y, bounds.Width, bounds.Height, applySize: true) && !windowResizeFailureLogged)
            {
                windowResizeFailureLogged = true;
                int error = Marshal.GetLastWin32Error();
                Logger.Log($"Failed to apply borderless bounds via native APIs (error {error}).", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private Size sanitiseWindowSize(Size requestedSize)
        {
            var bounds = getCurrentDisplayBounds();
            int maxWidth = bounds.Width > 0 ? bounds.Width : int.MaxValue;
            int maxHeight = bounds.Height > 0 ? bounds.Height : int.MaxValue;

            if (boundWindow != null)
            {
                var maxSize = boundWindow.MaxSize;
                if (maxSize.Width > 0)
                    maxWidth = Math.Min(maxWidth, maxSize.Width);
                if (maxSize.Height > 0)
                    maxHeight = Math.Min(maxHeight, maxSize.Height);
            }

            // Ensure the window never shrinks below the core UI's minimum layout.
            const int minWidth = 960;
            const int minHeight = 540;

            // Guard against displays that report extremely small bounds.
            if (maxWidth < minWidth)
                maxWidth = minWidth;
            if (maxHeight < minHeight)
                maxHeight = minHeight;

            int width = Math.Clamp(requestedSize.Width, minWidth, maxWidth);
            int height = Math.Clamp(requestedSize.Height, minHeight, maxHeight);

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

        private static bool sizesApproximatelyEqual(Size a, Size b)
        {
            return Math.Abs(a.Width - b.Width) <= 1 && Math.Abs(a.Height - b.Height) <= 1;
        }

        private bool windowClientSizeMatches(Size desired)
        {
            if (boundWindow == null)
                return false;

            var current = boundWindow.ClientSize;
            return sizesApproximatelyEqual(current, desired);
        }

        private static class NativeWindowHelpers
        {
            private const uint SWP_NOSIZE = 0x0001;
            private const uint SWP_NOZORDER = 0x0004;
            private const uint SWP_NOOWNERZORDER = 0x0200;
            private const uint SWP_NOACTIVATE = 0x0010;
            private const uint SWP_FRAMECHANGED = 0x0020;

            private const int GWL_STYLE = -16;
            private const int GWL_EXSTYLE = -20;
            private const int max_handle_search_depth = 6;

            private static readonly BindingFlags handle_binding_flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
            private static readonly string[] handle_property_candidates =
            {
                "WindowHandle",
                "Handle",
                "NativeHandle",
                "NativeWindowHandle",
                "SDLWindowHandle",
                "SdlWindowHandle",
                "HWND",
                "Hwnd",
                "Window",
                "NativeWindow",
                "Implementation",
                "WindowImplementation",
                "UnderlyingWindow",
                "GameWindow"
            };

            private static readonly string[] handle_field_candidates =
            {
                "windowHandle",
                "handle",
                "nativeHandle",
                "nativeWindowHandle",
                "sdlWindowHandle",
                "hwnd",
                "window",
                "nativeWindow",
                "implementation",
                "windowImplementation",
                "underlyingWindow",
                "gameWindow"
            };

            private static readonly string[] handle_method_candidates =
            {
                "get_WindowHandle",
                "get_Handle",
                "GetWindowHandle",
                "GetHandle",
                "GetNativeHandle",
                "GetHWND",
                "GetWindow",
                "GetNativeWindow"
            };

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
                    flags |= SWP_FRAMECHANGED;

                    RECT rect = new RECT
                    {
                        Left = 0,
                        Top = 0,
                        Right = clientWidth,
                        Bottom = clientHeight
                    };

                    uint style = (uint)GetWindowLong(windowHandle, GWL_STYLE);
                    uint exStyle = (uint)GetWindowLong(windowHandle, GWL_EXSTYLE);

                    if (AdjustWindowRectEx(ref rect, style, bMenu: false, exStyle))
                    {
                        width = rect.Right - rect.Left;
                        height = rect.Bottom - rect.Top;
                    }
                    else
                    {
                        width = clientWidth;
                        height = clientHeight;
                    }

                    width = Math.Max(1, width);
                    height = Math.Max(1, height);
                }
                else
                {
                    flags |= SWP_NOSIZE;
                }

                return SetWindowPos(windowHandle, IntPtr.Zero, x, y, width, height, flags);
            }

            public static IntPtr GetWindowHandle(IWindow window)
            {
                if (window == null)
                    return IntPtr.Zero;

                var visited = new HashSet<object>(ReferenceEqualityComparer.Instance);
                return resolveHandle(window, visited, 0);
            }

            private static IntPtr resolveHandle(object? source, HashSet<object> visited, int depth)
            {
                if (source == null || depth > max_handle_search_depth)
                    return IntPtr.Zero;

                if (tryConvertToIntPtr(source, out var direct) && direct != IntPtr.Zero)
                    return direct;

                Type type = source.GetType();

                if (!type.IsValueType)
                {
                    if (!visited.Add(source))
                        return IntPtr.Zero;
                }

                foreach (var name in handle_property_candidates)
                {
                    var property = type.GetProperty(name, handle_binding_flags);
                    if (property == null || property.GetIndexParameters().Length > 0)
                        continue;

                    object? value;
                    try
                    {
                        value = property.GetValue(source);
                    }
                    catch
                    {
                        continue;
                    }

                    var handle = resolveHandle(value, visited, depth + 1);
                    if (handle != IntPtr.Zero)
                        return handle;
                }

                foreach (var fieldName in handle_field_candidates)
                {
                    var field = type.GetField(fieldName, handle_binding_flags);
                    if (field == null)
                        continue;

                    object? value;
                    try
                    {
                        value = field.GetValue(source);
                    }
                    catch
                    {
                        continue;
                    }

                    var handle = resolveHandle(value, visited, depth + 1);
                    if (handle != IntPtr.Zero)
                        return handle;
                }

                foreach (var methodName in handle_method_candidates)
                {
                    var method = type.GetMethod(methodName, handle_binding_flags, binder: null, Type.EmptyTypes, null);
                    if (method == null)
                        continue;

                    object? value;
                    try
                    {
                        value = method.Invoke(source, null);
                    }
                    catch
                    {
                        continue;
                    }

                    var handle = resolveHandle(value, visited, depth + 1);
                    if (handle != IntPtr.Zero)
                        return handle;
                }

                foreach (var property in type.GetProperties(handle_binding_flags))
                {
                    if (property.GetIndexParameters().Length > 0 || !isHandleType(property.PropertyType))
                        continue;

                    object? value;
                    try
                    {
                        value = property.GetValue(source);
                    }
                    catch
                    {
                        continue;
                    }

                    if (tryConvertToIntPtr(value, out var handle) && handle != IntPtr.Zero)
                        return handle;
                }

                foreach (var field in type.GetFields(handle_binding_flags))
                {
                    if (!isHandleType(field.FieldType))
                        continue;

                    object? value;
                    try
                    {
                        value = field.GetValue(source);
                    }
                    catch
                    {
                        continue;
                    }

                    if (tryConvertToIntPtr(value, out var handle) && handle != IntPtr.Zero)
                        return handle;
                }

                return IntPtr.Zero;
            }

            private static bool tryConvertToIntPtr(object? candidate, out IntPtr handle)
            {
                switch (candidate)
                {
                    case null:
                        handle = IntPtr.Zero;
                        return false;
                    case IntPtr ptr:
                        handle = ptr;
                        return true;
                    case HandleRef handleRef:
                        handle = handleRef.Handle;
                        return true;
                    case UIntPtr uintPtrValue:
                        handle = IntPtr.Size == 8
                            ? new IntPtr(unchecked((long)uintPtrValue.ToUInt64()))
                            : new IntPtr(unchecked((int)uintPtrValue.ToUInt32()));
                        return true;
                    case long longValue:
                        handle = IntPtr.Size == 8 ? new IntPtr(longValue) : new IntPtr(unchecked((int)longValue));
                        return true;
                    case ulong ulongValue:
                        handle = IntPtr.Size == 8 ? new IntPtr(unchecked((long)ulongValue)) : new IntPtr(unchecked((int)ulongValue));
                        return true;
                    case int intValue:
                        handle = new IntPtr(intValue);
                        return true;
                    case uint uintValue:
                        handle = new IntPtr(unchecked((int)uintValue));
                        return true;
                    default:
                        handle = IntPtr.Zero;
                        return false;
                }
            }

            private static bool isHandleType(Type type)
            {
                if (type == typeof(IntPtr) || type == typeof(UIntPtr) || type == typeof(HandleRef))
                    return true;

                if (type == typeof(long) || type == typeof(ulong) || type == typeof(int) || type == typeof(uint))
                    return true;

                return false;
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
                            Font = BeatSightFont.Caption(16f),
                            Colour = UITheme.TextSecondary,
                            Padding = new MarginPadding { Horizontal = 12, Vertical = 6 }
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
