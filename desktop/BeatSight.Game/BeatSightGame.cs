using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.AI;
using BeatSight.Game.AI.Generation;
using BeatSight.Game.Audio;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Mapping;
using BeatSight.Game.Services.Analysis;
using BeatSight.Game.Services.Decode;
using BeatSight.Game.Services.Generation;
using BeatSight.Game.Services.Separation;
using osu.Framework.Audio;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Logging;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

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
                .BindValueChanged(e => fpsCounter.Alpha = e.NewValue ? 1f : 0f, true);
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (Host.Window != null)
                Host.Window.DragDrop += onWindowDragDrop;

            // Load the main menu
            screenStack.Push(new Screens.MainMenuScreen());
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);

            if (Host.Window != null)
                Host.Window.DragDrop -= onWindowDragDrop;

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
