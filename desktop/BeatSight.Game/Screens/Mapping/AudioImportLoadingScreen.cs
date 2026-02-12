using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.Audio;
using BeatSight.Game.Mapping;
using BeatSight.Game.Services.Metadata;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;

namespace BeatSight.Game.Screens.Mapping
{
    /// <summary>
    /// Loading screen shown immediately when user drops an audio file.
    /// Handles import and metadata detection, then navigates to the appropriate screen.
    /// </summary>
    public partial class AudioImportLoadingScreen : BeatSightScreen
    {
        private const string audio_imports_directory = "AudioImports";

        private readonly string sourcePath;
        private readonly bool autoStartImport;
        private SpriteText statusText = null!;
        private SpriteText detailText = null!;
        private Container progressSpinner = null!;
        private CancellationTokenSource? cts;

        [Resolved]
        private GameHost host { get; set; } = null!;

        [Resolved]
        private AudioEngine audioEngine { get; set; } = null!;

        [Resolved]
        private MetadataDetectionService metadataService { get; set; } = null!;

        public AudioImportLoadingScreen(string sourcePath)
            : this(sourcePath, autoStartImport: true)
        {
        }

        internal AudioImportLoadingScreen(string sourcePath, bool autoStartImport)
        {
            this.sourcePath = sourcePath;
            this.autoStartImport = autoStartImport;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(18, 18, 28, 255)
                },
                new FillFlowContainer
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 20),
                    Children = new Drawable[]
                    {
                        progressSpinner = new Container
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Size = new Vector2(60),
                            Child = new CircularContainer
                            {
                                RelativeSizeAxes = Axes.Both,
                                Masking = true,
                                BorderThickness = 4,
                                BorderColour = UITheme.AccentPrimary,
                                Child = new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = Color4.Transparent
                                }
                            }
                        },
                        statusText = new SpriteText
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Text = "Importing audio file...",
                            Font = BeatSightFont.Title(28f),
                            Colour = Color4.White
                        },
                        detailText = new SpriteText
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Text = Path.GetFileName(sourcePath),
                            Font = BeatSightFont.Section(18f),
                            Colour = new Color4(180, 185, 200, 255)
                        }
                    }
                }
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (!autoStartImport)
            {
                // Deterministic test mode: keep loading UI visible without background import tasks
                // or transitions to downstream mapping screens.
                progressSpinner.ClearTransforms(propagateChildren: true);
                progressSpinner.Rotation = 0;
                statusText.Text = "Importing audio file...";
                detailText.Text = Path.GetFileName(sourcePath);
                return;
            }

            // Start spinner animation
            progressSpinner.Spin(2000, RotationDirection.Clockwise).Loop();

            // Start import process
            cts = new CancellationTokenSource();
            _ = processImportAsync(cts.Token);
        }

        private async Task processImportAsync(CancellationToken cancellationToken)
        {
            try
            {
                // Step 1: Copy file
                Schedule(() =>
                {
                    statusText.Text = "Copying audio file...";
                    detailText.Text = "Please wait";
                });

                var imported = await importAudioFileAsync(sourcePath, cancellationToken).ConfigureAwait(false);

                // Step 2: Detect metadata
                Schedule(() =>
                {
                    statusText.Text = "Detecting song information...";
                    detailText.Text = "Identifying song metadata";
                });

                var metadata = await metadataService.DetectMetadataAsync(imported.StoredPath, cancellationToken).ConfigureAwait(false);

                // Step 3: Navigate to appropriate screen
                if (metadata != null && (metadata.Confidence > 0.8 || metadata.Provider == "acoustid"))
                {
                    if (!string.IsNullOrEmpty(metadata.Title))
                        imported.Title = metadata.Title;
                    if (!string.IsNullOrEmpty(metadata.Artist))
                        imported.Artist = metadata.Artist;
                    if (!string.IsNullOrEmpty(metadata.Title))
                        imported.DisplayName = metadata.Title;

                    Schedule(() => this.Push(new MappingChoiceScreen(imported)));
                }
                else
                {
                    Schedule(() => this.Push(new MetadataChoiceScreen(imported, metadata)));
                }
            }
            catch (OperationCanceledException)
            {
                Logger.Log("Audio import cancelled", LoggingTarget.Runtime, LogLevel.Debug);
                Schedule(() => this.Exit());
            }
            catch (Exception ex)
            {
                Logger.Error(ex, "Failed to import audio file");
                Schedule(() =>
                {
                    statusText.Text = "Import failed";
                    detailText.Text = ex.Message;
                    progressSpinner.FadeOut(200);
                });
            }
        }

        private async Task<ImportedAudioTrack> importAudioFileAsync(string path, CancellationToken cancellationToken)
        {
            string importRoot = host.Storage.GetFullPath(audio_imports_directory);
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

            string relativePath = Path.Combine(audio_imports_directory, Path.GetFileName(targetPath)).Replace(Path.DirectorySeparatorChar, '/');
            double? duration = await audioEngine.ComputeDurationFromFileAsync(targetPath, cancellationToken).ConfigureAwait(false);
            var info = new FileInfo(targetPath);

            string displayName = Path.GetFileNameWithoutExtension(path);
            return new ImportedAudioTrack(path, targetPath, relativePath, displayName, info.Length, duration);
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            cts?.Cancel();
            return base.OnExiting(e);
        }

        protected override void Dispose(bool isDisposing)
        {
            cts?.Cancel();
            cts?.Dispose();
            base.Dispose(isDisposing);
        }
    }
}
