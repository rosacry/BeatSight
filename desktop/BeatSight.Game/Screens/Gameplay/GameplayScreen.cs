using System;
using System.Collections.Generic;
using System.IO;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using osu.Framework.Allocation;
using osu.Framework.Audio;
using osu.Framework.Audio.Track;
using osu.Framework.Audio.Sample;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osu.Framework.Timing;
using osu.Framework.IO.Stores;
using osuTK;
using osuTK.Graphics;
using System.Linq;

namespace BeatSight.Game.Screens.Gameplay
{
    public partial class GameplayScreen : Screen
    {
        private static readonly Dictionary<osuTK.Input.Key, int> laneKeyBindings = new()
        {
            { osuTK.Input.Key.S, 0 },
            { osuTK.Input.Key.D, 1 },
            { osuTK.Input.Key.F, 2 },
            { osuTK.Input.Key.Space, 3 },
            { osuTK.Input.Key.J, 4 },
            { osuTK.Input.Key.K, 5 },
            { osuTK.Input.Key.L, 6 }
        };

        private readonly string? requestedBeatmapPath;
        private double fallbackElapsed;
        private bool fallbackRunning;

        protected Beatmap? beatmap;
        protected string? beatmapPath;
        protected Track? track;

        protected GameplayPlayfield? playfield;
        private SpriteText statusText = null!;
        private SpriteText offsetValueText = null!;
        private SpriteText speedValueText = null!;
        private readonly BindableDouble offsetAdjustment = new BindableDouble
        {
            MinValue = -120,
            MaxValue = 120,
            Default = 0,
            Precision = 1
        };
        private readonly BindableDouble speedAdjustment = new BindableDouble
        {
            MinValue = 0.25,
            MaxValue = 2.0,
            Default = 1.0,
            Precision = 0.05
        };
        private double offsetMilliseconds;
        private double playbackSpeed = 1.0;
        private BasicButton mixToggleButton = null!;
        private bool drumsOnlyMode;
        private Bindable<bool> drumStemPreferredSetting = null!;
        private bool drumStemAvailable;
        private string? cachedFullMixPath;
        private string? cachedDrumStemPath;
        private bool isTrackRunning;
        private StorageBackedResourceStore? storageResourceStore;
        private ITrackStore? storageTrackStore;

        private Bindable<double> musicVolumeSetting = null!;
        private Bindable<double> masterVolumeSetting = null!;
        private Bindable<bool> metronomeEnabledSetting = null!;
        private Bindable<MetronomeSoundOption> metronomeSoundSetting = null!;
        private readonly BindableDouble metronomeVolume = new BindableDouble { MinValue = 0, MaxValue = 1, Precision = 0.05, Default = 0.6, Value = 0.6 };
        private Sample? metronomeSample;
        private int lastMetronomeBeatIndex = -1;
        private bool pendingMetronomePulse;
        protected event Action<double>? MetronomeTick;

        protected IBindable<bool> MetronomeEnabledBinding => metronomeEnabledSetting;
        protected IBindable<MetronomeSoundOption> MetronomeSoundBinding => metronomeSoundSetting;
        protected IBindable<double> MetronomeVolumeBinding => metronomeVolume;

        [Resolved]
        private AudioManager audioManager { get; set; } = null!;

        [Resolved]
        private GameHost host { get; set; } = null!;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        public GameplayScreen(string? beatmapPath = null)
        {
            requestedBeatmapPath = beatmapPath;
        }

        private BufferedContainer backgroundBlurContainer = null!;
        private Box backgroundBase = null!;
        private Box backgroundDim = null!;
        private Box hitLightingOverlay = null!;
        private Container playfieldContainer = null!;

        private Bindable<double> backgroundDimSetting = null!;
        private Bindable<double> backgroundBlurSetting = null!;
        private Bindable<bool> hitLightingEnabled = null!;
        private Bindable<bool> screenShakeEnabled = null!;

        private const float maxBackgroundBlurSigma = 25f;

        [BackgroundDependencyLoader]
        private void load()
        {
            backgroundBlurContainer = new BufferedContainer
            {
                RelativeSizeAxes = Axes.Both,
                Child = backgroundBase = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(10, 10, 18, 255)
                }
            };

            backgroundDim = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = Color4.Black,
                Alpha = 0.8f
            };

            hitLightingOverlay = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = Color4.White,
                Alpha = 0,
                Blending = BlendingParameters.Additive
            };

            InternalChildren = new Drawable[]
            {
                backgroundBlurContainer,
                backgroundDim,
                new GridContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    RowDimensions = new[]
                    {
                        new Dimension(GridSizeMode.Absolute, 60),
                        new Dimension()
                    },
                    Content = new[]
                    {
                        new Drawable[]
                        {
                            createHeader()
                        },
                        new Drawable[]
                        {
                            createPlayfieldArea()
                        }
                    }
                },
                hitLightingOverlay
            };

            backgroundDimSetting = config.GetBindable<double>(BeatSightSetting.BackgroundDim);
            backgroundDimSetting.BindValueChanged(value =>
            {
                backgroundDim.Alpha = (float)Math.Clamp(value.NewValue, 0, 1);
            }, true);

            backgroundBlurSetting = config.GetBindable<double>(BeatSightSetting.BackgroundBlur);
            backgroundBlurSetting.BindValueChanged(value =>
            {
                float sigma = (float)Math.Clamp(value.NewValue, 0, 1) * maxBackgroundBlurSigma;
                backgroundBlurContainer.BlurSigma = new Vector2(sigma);
                backgroundBlurContainer.ForceRedraw();
            }, true);

            hitLightingEnabled = config.GetBindable<bool>(BeatSightSetting.HitLighting);
            screenShakeEnabled = config.GetBindable<bool>(BeatSightSetting.ScreenShakeOnMiss);

            masterVolumeSetting = config.GetBindable<double>(BeatSightSetting.MasterVolume);
            musicVolumeSetting = config.GetBindable<double>(BeatSightSetting.MusicVolume);
            metronomeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.MetronomeEnabled);
            metronomeSoundSetting = config.GetBindable<MetronomeSoundOption>(BeatSightSetting.MetronomeSound);
            metronomeVolume.BindTo(config.GetBindable<double>(BeatSightSetting.MetronomeVolume));

            metronomeSoundSetting.BindValueChanged(_ => reloadMetronomeSample(), true);
            metronomeEnabledSetting.BindValueChanged(_ => pendingMetronomePulse = false, true);
            drumStemPreferredSetting = config.GetBindable<bool>(BeatSightSetting.DrumStemPlaybackOnly);
            drumStemPreferredSetting.BindValueChanged(e => applyDrumStemPreference(e.NewValue), true);
            reloadMetronomeSample();

            loadBeatmap();

            offsetAdjustment.BindValueChanged(value =>
            {
                offsetMilliseconds = value.NewValue;
                if (offsetValueText != null)
                    offsetValueText.Text = formatOffsetLabel(value.NewValue);
            }, true);

            speedAdjustment.BindValueChanged(value =>
            {
                playbackSpeed = value.NewValue;
                if (track != null)
                    track.Tempo.Value = playbackSpeed;
                if (speedValueText != null)
                    speedValueText.Text = formatSpeedLabel(value.NewValue);
            }, true);
        }

        private Drawable createHeader()
        {
            statusText = new SpriteText
            {
                Text = "Loading beatmap…",
                Font = new FontUsage(size: 24, weight: "Medium"),
                Colour = Color4.White,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
            };

            offsetValueText = new SpriteText
            {
                Font = new FontUsage(size: 18),
                Colour = new Color4(200, 205, 220, 255),
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Text = formatOffsetLabel(0)
            };

            speedValueText = new SpriteText
            {
                Font = new FontUsage(size: 18),
                Colour = new Color4(200, 205, 220, 255),
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Text = formatSpeedLabel(1.0)
            };

            var offsetSlider = new BasicSliderBar<double>
            {
                Width = 220,
                Height = 14,
                Current = offsetAdjustment,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
            };

            var speedSlider = new BasicSliderBar<double>
            {
                Width = 220,
                Height = 14,
                Current = speedAdjustment,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
            };

            var rightColumn = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Spacing = new Vector2(0, 6),
                Children = new Drawable[]
                {
                    speedValueText,
                    speedSlider,
                    mixToggleButton = new BasicButton
                    {
                        Width = 220,
                        Height = 30,
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Text = "Audio: Full Mix",
                        BackgroundColour = new Color4(90, 155, 110, 255),
                        CornerRadius = 6,
                        Masking = true
                    },
                    createSpacer(),
                    offsetValueText,
                    offsetSlider,
                    createSpacer(),
                    new SpriteText
                    {
                        Text = "Esc — back • R — retry",
                        Font = new FontUsage(size: 18),
                        Colour = new Color4(180, 180, 200, 255),
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight
                    }
                }
            };

            mixToggleButton.Action = toggleDrumMix;

            return new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding { Left = 40, Right = 40, Top = 10, Bottom = 10 },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.6f),
                    new Dimension(GridSizeMode.Relative, 0.4f)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Children = new Drawable[] { statusText }
                        },
                        rightColumn
                    }
                }
            };
        }

        private static Container createSpacer() => new Container
        {
            Height = 8,
            Anchor = Anchor.CentreRight,
            Origin = Anchor.CentreRight
        };

        private Drawable createPlayfieldArea()
        {
            playfield = new GameplayPlayfield(getCurrentTime)
            {
                RelativeSizeAxes = Axes.Both,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Size = new Vector2(0.8f, 1f),
                Margin = new MarginPadding { Left = 40, Right = 40, Bottom = 40 }
            };

            playfield.ResultApplied += onPlayfieldResult;

            return playfieldContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    playfield,
                    new HitLine
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 4,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.Centre,
                        Y = -80
                    }
                }
            };
        }

        private void onPlayfieldResult(GameplayPlayfield.HitResult result, double offset, Color4 accentColour)
        {
            if (hitLightingEnabled?.Value == true && (result == GameplayPlayfield.HitResult.Perfect || result == GameplayPlayfield.HitResult.Great))
            {
                hitLightingOverlay.Colour = new Color4(accentColour.R, accentColour.G, accentColour.B, 255);
                hitLightingOverlay.FadeTo(0.4f, 60, Easing.OutQuint)
                    .Then()
                    .FadeOut(260, Easing.OutQuad);
            }

            if (screenShakeEnabled?.Value == true && result == GameplayPlayfield.HitResult.Miss && playfieldContainer != null)
            {
                playfieldContainer.ClearTransforms();
                playfieldContainer.MoveToX(0);
                playfieldContainer.MoveToX(8, 40, Easing.OutQuad)
                    .Then()
                    .MoveToX(-6, 70, Easing.InOutQuad)
                    .Then()
                    .MoveToX(0, 120, Easing.OutElastic);
            }
        }

        private void loadBeatmap()
        {
            if (!tryResolveBeatmapPath(out string? path))
            {
                statusText.Text = "No beatmaps found. Return to add a map.";
                return;
            }

            try
            {
                beatmap = BeatmapLoader.LoadFromFile(path!);
                beatmapPath = path;
                statusText.Text = $"Loaded: {beatmap.Metadata.Artist} — {beatmap.Metadata.Title}";
                loadTrack();
                fallbackElapsed = 0;
                fallbackRunning = false;
            }
            catch (Exception ex)
            {
                statusText.Text = $"Failed to load beatmap: {ex.Message}";
            }
        }

        private bool tryResolveBeatmapPath(out string? path)
        {
            if (!string.IsNullOrEmpty(requestedBeatmapPath))
            {
                path = requestedBeatmapPath;
                return true;
            }

            if (BeatmapLibrary.TryGetDefaultBeatmapPath(out var fallback))
            {
                path = fallback;
                return true;
            }

            path = null;
            return false;
        }

        private void loadTrack()
        {
            disposeTrack();

            if (beatmap == null || beatmapPath == null)
                return;

            if (string.IsNullOrWhiteSpace(beatmap.Audio.Filename))
            {
                statusText.Text += "\nBeatmap has no audio file declared.";
                createVirtualTrack();
                return;
            }

            string resolvedAudioPath = Path.IsPathRooted(beatmap.Audio.Filename)
                ? beatmap.Audio.Filename
                : Path.Combine(Path.GetDirectoryName(beatmapPath) ?? string.Empty, beatmap.Audio.Filename);

            if (!File.Exists(resolvedAudioPath))
            {
                statusText.Text += $"\nAudio file missing: {resolvedAudioPath}";
                createVirtualTrack();
                return;
            }

            try
            {
                prepareAudioCaches(resolvedAudioPath);

                if (cachedFullMixPath == null)
                {
                    statusText.Text += "\nAudio load failed (unable to cache track). Using silent timing.";
                    createVirtualTrack();
                    return;
                }

                refreshTrackFromCache();
                fallbackRunning = false;
            }
            catch (Exception ex)
            {
                statusText.Text += $"\nAudio load failed ({ex.Message}). Using silent timing.";
                createVirtualTrack();
            }

            updateMixToggle();
        }

        private void createVirtualTrack()
        {
            track = null;
            isTrackRunning = false;
        }

        private void startPlayback(bool restart)
        {
            if (track == null && !string.IsNullOrEmpty(cachedFullMixPath))
                refreshTrackFromCache();

            resetMetronomeTracking();

            if (track != null)
            {
                if (restart)
                    track.Seek(0);

                track.Start();
                isTrackRunning = true;
            }
            else
            {
                if (restart)
                    fallbackElapsed = 0;

                fallbackRunning = true;
                isTrackRunning = false;
            }
        }

        private void stopPlayback()
        {
            if (track != null)
            {
                track.Stop();
                isTrackRunning = false;
            }
            fallbackRunning = false;
            pendingMetronomePulse = false;
        }

        private void disposeTrack()
        {
            if (track == null)
                return;

            track.Stop();
            track.Completed -= onTrackCompleted;
            track.Dispose();
            track = null;
            isTrackRunning = false;
        }

        private void onTrackCompleted()
        {
            Schedule(() =>
            {
                stopPlayback();
                isTrackRunning = false;
                showResults();
            });
        }

        private void showResults()
        {
            if (beatmap == null || playfield == null)
                return;

            // Don't show results in manual mode
            var gameplayMode = config.GetBindable<GameplayMode>(BeatSightSetting.GameplayMode);
            if (gameplayMode.Value == GameplayMode.Manual)
            {
                this.Exit();
                return;
            }

            var result = playfield.GetResult();
            if (result == null)
                return;

            result.BeatmapTitle = $"{beatmap.Metadata.Artist} — {beatmap.Metadata.Title}";
            result.BeatmapPath = beatmapPath ?? string.Empty;

            this.Push(new ResultsScreen(result));
        }

        private static string formatOffsetLabel(double value) => $"Offset: {value:+0;-0;0} ms";
        private static string formatSpeedLabel(double value) => $"Speed: {value:0.00}x";

        protected double getCurrentTime() => (track?.CurrentTime ?? fallbackElapsed) + offsetMilliseconds;

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Bind background dim setting
            var backgroundDimBindable = config.GetBindable<double>(BeatSightSetting.BackgroundDim);
            backgroundDimBindable.BindValueChanged(e => backgroundDim.Alpha = (float)e.NewValue, true);

            // Bind volume settings
            masterVolumeSetting.BindValueChanged(e => audioManager.Volume.Value = e.NewValue, true);
            musicVolumeSetting.BindValueChanged(e =>
            {
                if (track != null)
                    track.Volume.Value = e.NewValue;
            }, true);

            if (beatmap != null)
                playfield?.LoadBeatmap(beatmap);
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            startPlayback(restart: true);
        }

        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            startPlayback(restart: false);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            stopPlayback();
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            stopPlayback();
            return base.OnExiting(e);
        }

        protected override void Update()
        {
            base.Update();

            if (fallbackRunning && track == null)
                fallbackElapsed += Time.Elapsed;

            handleMetronome();
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);
            disposeTrack();
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
                this.Exit();
                return true;
            }

            if (e.Key == osuTK.Input.Key.R && !e.Repeat)
            {
                // Retry - restart gameplay
                this.Exit();
                this.Push(new GameplayScreen(beatmapPath));
                return true;
            }

            if (!e.Repeat && playfield != null && laneKeyBindings.TryGetValue(e.Key, out int lane))
            {
                var result = playfield.HandleInput(lane, getCurrentTime());
                if (result != GameplayPlayfield.HitResult.None)
                    return true;
            }

            return base.OnKeyDown(e);
        }

        private void toggleDrumMix()
        {
            if (!drumStemAvailable)
                return;

            drumStemPreferredSetting.Value = !drumStemPreferredSetting.Value;
        }

        private void prepareAudioCaches(string resolvedAudioPath)
        {
            ensureAudioStores();

            cachedFullMixPath = null;
            cachedDrumStemPath = null;
            drumStemAvailable = false;

            if (beatmap == null)
                return;

            string cacheFolder = "GameplayAudio";
            string cachePrefix = sanitizeFileComponent(beatmap.Metadata.BeatmapId ?? string.Empty);

            if (string.IsNullOrEmpty(cachePrefix))
                cachePrefix = sanitizeFileComponent(Path.GetFileNameWithoutExtension(resolvedAudioPath));

            if (string.IsNullOrEmpty(cachePrefix))
                cachePrefix = "beatmap";

            string extension = Path.GetExtension(resolvedAudioPath);
            string cachedName = $"{cachePrefix}_full{extension}";
            string relativePath = Path.Combine(cacheFolder, cachedName).Replace(Path.DirectorySeparatorChar, '/');
            string absolutePath = host.Storage.GetFullPath(relativePath.Replace('/', Path.DirectorySeparatorChar));

            string? mixDirectory = Path.GetDirectoryName(absolutePath);
            if (!string.IsNullOrEmpty(mixDirectory))
                Directory.CreateDirectory(mixDirectory);
            File.Copy(resolvedAudioPath, absolutePath, overwrite: true);
            cachedFullMixPath = relativePath;

            drumsOnlyMode = false;

            string? drumStemSource = resolveDrumStemSourcePath();
            if (!string.IsNullOrEmpty(drumStemSource) && File.Exists(drumStemSource))
            {
                string drumExtension = Path.GetExtension(drumStemSource);
                string drumCachedName = $"{cachePrefix}_drums{drumExtension}";
                string drumRelativePath = Path.Combine(cacheFolder, drumCachedName).Replace(Path.DirectorySeparatorChar, '/');
                string drumAbsolutePath = host.Storage.GetFullPath(drumRelativePath.Replace('/', Path.DirectorySeparatorChar));

                string? drumDirectory = Path.GetDirectoryName(drumAbsolutePath);
                if (!string.IsNullOrEmpty(drumDirectory))
                    Directory.CreateDirectory(drumDirectory);

                try
                {
                    File.Copy(drumStemSource, drumAbsolutePath, overwrite: true);
                    cachedDrumStemPath = drumRelativePath;
                    drumStemAvailable = true;
                }
                catch (Exception ex)
                {
                    osu.Framework.Logging.Logger.Log($"[Gameplay] Failed to cache drum stem '{drumStemSource}': {ex.Message}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
                    cachedDrumStemPath = null;
                    drumStemAvailable = false;
                }
            }

            bool preferDrums = drumStemPreferredSetting?.Value ?? false;
            drumsOnlyMode = drumStemAvailable && preferDrums;
        }

        private void refreshTrackFromCache()
        {
            ensureAudioStores();

            disposeTrack();

            string? targetRelativePath = drumsOnlyMode && drumStemAvailable ? cachedDrumStemPath : cachedFullMixPath;

            if (string.IsNullOrEmpty(targetRelativePath) || storageTrackStore == null)
            {
                track = null;
                return;
            }

            var loadedTrack = storageTrackStore.Get(targetRelativePath);

            if (loadedTrack == null)
            {
                osu.Framework.Logging.Logger.Log($"[Gameplay] Unable to resolve cached track '{targetRelativePath}'", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
                track = null;
                return;
            }

            track = loadedTrack;
            track.Completed += onTrackCompleted;
            track.Volume.Value = musicVolumeSetting.Value;
            track.Tempo.Value = playbackSpeed;
            fallbackRunning = false;
            isTrackRunning = false;
        }

        private void applyDrumStemPreference(bool preferDrumsOnly)
        {
            setDrumMixMode(preferDrumsOnly);
        }

        private void setDrumMixMode(bool drumsOnlyRequested)
        {
            bool targetDrumsOnly = drumsOnlyRequested && drumStemAvailable;

            if (drumsOnlyMode == targetDrumsOnly)
            {
                updateMixToggle();
                return;
            }

            double resumeTime = track?.CurrentTime ?? fallbackElapsed;
            bool wasRunning = isTrackRunning || fallbackRunning;

            drumsOnlyMode = targetDrumsOnly;

            refreshTrackFromCache();

            if (track != null)
            {
                track.Seek(Math.Max(0, resumeTime));
                if (wasRunning)
                {
                    track.Start();
                    isTrackRunning = true;
                }

                fallbackRunning = false;
            }
            else if (wasRunning)
            {
                fallbackElapsed = Math.Max(0, resumeTime);
                fallbackRunning = true;
            }

            pendingMetronomePulse = true;
            updateMixToggle();
        }

        private void updateMixToggle()
        {
            if (mixToggleButton == null)
                return;

            if (!drumStemAvailable)
            {
                mixToggleButton.Enabled.Value = false;
                mixToggleButton.Text = "Audio: Full Mix";
                mixToggleButton.BackgroundColour = new Color4(80, 90, 120, 255);
                return;
            }

            mixToggleButton.Enabled.Value = true;
            if (drumsOnlyMode)
            {
                mixToggleButton.Text = "Audio: Drums Only";
                mixToggleButton.BackgroundColour = new Color4(220, 120, 120, 255);
            }
            else
            {
                mixToggleButton.Text = "Audio: Full Mix";
                mixToggleButton.BackgroundColour = new Color4(90, 155, 110, 255);
            }
        }

        private void resetMetronomeTracking()
        {
            lastMetronomeBeatIndex = -1;
            pendingMetronomePulse = true;
        }

        private void handleMetronome()
        {
            if (!metronomeEnabledSetting.Value || beatmap == null)
                return;

            if (!(isTrackRunning || fallbackRunning))
                return;

            double bpm = beatmap.Timing?.Bpm ?? 0;
            if (bpm <= 0)
                return;

            double beatDuration = 60000.0 / bpm;
            double offset = beatmap.Timing?.Offset ?? 0;
            double songTime = getCurrentTime() - offset;

            if (songTime < 0)
                return;

            int beatIndex = (int)Math.Floor(songTime / beatDuration);

            if (!pendingMetronomePulse && beatIndex == lastMetronomeBeatIndex)
                return;

            pendingMetronomePulse = false;
            lastMetronomeBeatIndex = beatIndex;

            playMetronomeSample();
            MetronomeTick?.Invoke(songTime + offset);
        }

        private void reloadMetronomeSample()
        {
            string samplePath = metronomeSoundSetting.Value switch
            {
                MetronomeSoundOption.Woodblock => "Metronome/woodblock",
                MetronomeSoundOption.Cowbell => "Metronome/cowbell",
                _ => "Metronome/click"
            };

            try
            {
                metronomeSample = audioManager.Samples.Get(samplePath);
            }
            catch (Exception ex)
            {
                metronomeSample = null;
                osu.Framework.Logging.Logger.Log($"[Gameplay] Failed to load metronome sample '{samplePath}': {ex.Message}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
            }
        }

        private void playMetronomeSample()
        {
            if (metronomeSample == null)
                return;

            var channel = metronomeSample.Play();
            if (channel != null)
                channel.Volume.Value = metronomeVolume.Value;
        }

        private void ensureAudioStores()
        {
            storageResourceStore ??= new StorageBackedResourceStore(host.Storage);
            storageTrackStore ??= audioManager.GetTrackStore(storageResourceStore);
        }

        private string? resolveDrumStemSourcePath()
        {
            if (beatmap == null || string.IsNullOrWhiteSpace(beatmap.Audio.DrumStem))
                return null;

            string path = beatmap.Audio.DrumStem!;

            if (!Path.IsPathRooted(path))
            {
                string baseDirectory = Path.GetDirectoryName(beatmapPath ?? string.Empty) ?? string.Empty;
                path = Path.Combine(baseDirectory, path);
            }

            return path;
        }

        private static string sanitizeFileComponent(string value)
        {
            if (string.IsNullOrEmpty(value))
                return string.Empty;

            var invalid = Path.GetInvalidFileNameChars();
            var filtered = new string(value.Where(c => !invalid.Contains(c)).ToArray());
            return string.IsNullOrEmpty(filtered) ? string.Empty : filtered;
        }

        private partial class HitLine : CompositeDrawable
        {
            public HitLine()
            {
                RelativeSizeAxes = Axes.X;
                Height = 4;
                Masking = true;
                CornerRadius = 2;

                InternalChildren = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(255, 184, 108, 255)
                    }
                };
            }
        }
    }

    public partial class GameplayPlayfield : CompositeDrawable
    {
        private const int laneCount = 7;
        private const double approachDuration = 1800; // milliseconds from spawn to hit line
        private const double perfectWindow = 35;
        private const double greatWindow = 80;
        private const double goodWindow = 130;
        private const double mehWindow = 180;
        private const double missWindow = 220;

        private readonly Func<double> currentTimeProvider;
        private readonly List<DrawableNote> notes = new();
        private bool isPreviewMode; // If true, notes won't be auto-judged

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        private Bindable<GameplayMode> gameplayMode = null!;
        private Bindable<bool> showApproachCircles = null!;
        private Bindable<bool> showParticleEffects = null!;
        private Bindable<bool> showGlowEffects = null!;
        private Bindable<bool> showHitBurstAnimations = null!;
        private Bindable<bool> showComboMilestones = null!;
        private Bindable<bool> showHitErrorMeter = null!;

        private Container noteLayer = null!;
        private Container laneBackgroundContainer = null!;
        private Container laneGuideOverlay = null!;
        private ThreeDHighwayBackground? threeDHighwayBackground;
        private SpriteText comboText = null!;
        private SpriteText accuracyText = null!;
        private SpriteText judgementText = null!;
        private HitErrorMeter hitErrorMeter = null!;

        private int combo;
        private int maxCombo;
        private int totalNotes;
        private int judgedNotes;
        private double accuracyScore;
        private int perfectCount;
        private int greatCount;
        private int goodCount;
        private int mehCount;
        private int missCount;

        private Bindable<LaneViewMode> laneViewMode = null!;
        private LaneViewMode currentLaneViewMode;

        public event Action<HitResult, double, Color4>? ResultApplied;

        public GameplayResult? GetResult() => totalNotes == 0 ? null : new GameplayResult
        {
            TotalScore = (int)(accuracyScore * 100000),
            Accuracy = Math.Clamp(accuracyScore / totalNotes, 0, 1) * 100,
            MaxCombo = maxCombo,
            Perfect = perfectCount,
            Great = greatCount,
            Good = goodCount,
            Meh = mehCount,
            Miss = missCount
        };

        public GameplayPlayfield(Func<double> currentTimeProvider)
        {
            this.currentTimeProvider = currentTimeProvider;

            RelativeSizeAxes = Axes.Both;
            Masking = true;
            CornerRadius = 12;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            gameplayMode = config.GetBindable<GameplayMode>(BeatSightSetting.GameplayMode);
            showApproachCircles = config.GetBindable<bool>(BeatSightSetting.ShowApproachCircles);
            showParticleEffects = config.GetBindable<bool>(BeatSightSetting.ShowParticleEffects);
            showGlowEffects = config.GetBindable<bool>(BeatSightSetting.ShowGlowEffects);
            showHitBurstAnimations = config.GetBindable<bool>(BeatSightSetting.ShowHitBurstAnimations);
            showComboMilestones = config.GetBindable<bool>(BeatSightSetting.ShowComboMilestones);
            showHitErrorMeter = config.GetBindable<bool>(BeatSightSetting.ShowHitErrorMeter);
            laneViewMode = config.GetBindable<LaneViewMode>(BeatSightSetting.LaneViewMode);

            laneBackgroundContainer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            noteLayer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            laneGuideOverlay = createGuideOverlay();

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(26, 26, 40, 255)
                },
                laneBackgroundContainer,
                noteLayer,
                laneGuideOverlay,
                createOverlay()
            };

            laneViewMode.BindValueChanged(onLaneViewModeChanged, true);
            showHitErrorMeter.BindValueChanged(onShowHitErrorMeterChanged, true);
        }

        private Drawable createOverlay()
        {
            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Padding = new MarginPadding { Top = 16 },
                Spacing = new Vector2(0, 6),
                Children = new Drawable[]
                {
                    comboText = new SpriteText
                    {
                        Font = new FontUsage(size: 32, weight: "Medium"),
                        Colour = Color4.White,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = "Combo: 0"
                    },
                    accuracyText = new SpriteText
                    {
                        Font = new FontUsage(size: 22),
                        Colour = new Color4(200, 205, 220, 255),
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = "Accuracy: --"
                    },
                    judgementText = new SpriteText
                    {
                        Font = new FontUsage(size: 26, weight: "Medium"),
                        Colour = new Color4(255, 196, 120, 255),
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = "Ready"
                    },
                    hitErrorMeter = new HitErrorMeter
                    {
                        RelativeSizeAxes = Axes.X,
                        Width = 0.8f,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Alpha = showHitErrorMeter.Value ? 1f : 0f
                    }
                }
            };
        }

        private void onShowHitErrorMeterChanged(ValueChangedEvent<bool> state)
        {
            hitErrorMeter.FadeTo(state.NewValue ? 1f : 0f, 200, Easing.OutQuint);
        }

        private Container createGuideOverlay()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Alpha = 0,
                Children = new Drawable[]
                {
                    createGuideEdge(-1),
                    createGuideEdge(1),
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 3,
                        Colour = new Color4(255, 214, 150, 120),
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Y = -80
                    }
                }
            };
        }

        private Drawable createGuideEdge(int direction)
        {
            return new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 4,
                Height = 1,
                Colour = new Color4(80, 90, 130, 160),
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                RelativePositionAxes = Axes.X,
                X = direction * 0.28f,
                Rotation = direction * 16,
                Alpha = 0.6f
            };
        }

        private Drawable createLaneGrid2D()
        {
            var laneContainer = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                ColumnDimensions = Enumerable.Repeat(new Dimension(GridSizeMode.Relative, 1f / laneCount), laneCount).ToArray(),
                Content = new[]
                {
                    Enumerable.Range(0, laneCount).Select(createLaneBackground).ToArray()
                }
            };

            return laneContainer;
        }

        private Drawable createLaneGrid3D()
        {
            threeDHighwayBackground = new ThreeDHighwayBackground(laneCount);
            return threeDHighwayBackground;
        }

        private void onLaneViewModeChanged(ValueChangedEvent<LaneViewMode> mode)
        {
            currentLaneViewMode = mode.NewValue;

            laneBackgroundContainer.Clear();
            threeDHighwayBackground = null;

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
                laneBackgroundContainer.Add(createLaneGrid3D());
            else
                laneBackgroundContainer.Add(createLaneGrid2D());

            laneGuideOverlay.FadeTo(currentLaneViewMode == LaneViewMode.ThreeDimensional ? 1f : 0f, 180, Easing.OutQuint);

            foreach (var note in notes)
                note.SetViewMode(currentLaneViewMode);
        }

        private Drawable createLaneBackground(int laneIndex)
        {
            float intensity = laneIndex % 2 == 0 ? 0.16f : 0.22f;
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4((byte)(intensity * 255), (byte)(intensity * 255), 60, 255)
                    }
                }
            };
        }

        /// <summary>
        /// Sets whether this playfield is in preview mode (editor) or gameplay mode.
        /// In preview mode, notes won't be auto-judged as missed.
        /// </summary>
        public void SetPreviewMode(bool preview)
        {
            isPreviewMode = preview;
        }

        public void LoadBeatmap(Beatmap beatmap)
        {
            osu.Framework.Logging.Logger.Log($"[GameplayPlayfield] LoadBeatmap called: {beatmap.HitObjects.Count} hit objects, preview mode: {isPreviewMode}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);

            noteLayer.Clear();
            notes.Clear();

            combo = 0;
            maxCombo = 0;
            totalNotes = 0;
            judgedNotes = 0;
            accuracyScore = 0;
            perfectCount = 0;
            greatCount = 0;
            goodCount = 0;
            mehCount = 0;
            missCount = 0;

            comboText.Text = "Combo: 0";
            accuracyText.Text = "Accuracy: --";
            judgementText.Text = gameplayMode.Value == GameplayMode.Manual ? "Manual Mode" : "Ready";

            foreach (var hit in beatmap.HitObjects)
            {
                int lane = resolveLane(hit);
                var note = new DrawableNote(hit, lane, showApproachCircles, showGlowEffects, showParticleEffects)
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.Centre,
                };

                noteLayer.Add(note);
                notes.Add(note);
                note.SetViewMode(currentLaneViewMode);
                note.SetApproachProgress(0);
            }

            totalNotes = notes.Count;
            osu.Framework.Logging.Logger.Log($"[GameplayPlayfield] LoadBeatmap complete: {notes.Count} notes added to noteLayer", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
        }

        public HitResult HandleInput(int lane, double inputTime)
        {
            var candidate = notes
                .Where(n => n.Lane == lane && !n.IsJudged)
                .OrderBy(n => Math.Abs(n.HitTime - inputTime))
                .FirstOrDefault();

            if (candidate == null)
                return HitResult.None;

            double offset = inputTime - candidate.HitTime;
            double absOffset = Math.Abs(offset);

            HitResult result;
            if (absOffset <= perfectWindow)
                result = HitResult.Perfect;
            else if (absOffset <= greatWindow)
                result = HitResult.Great;
            else if (absOffset <= goodWindow)
                result = HitResult.Good;
            else if (absOffset <= mehWindow)
                result = HitResult.Meh;
            else
                return HitResult.None;

            applyResult(candidate, result, offset);
            return result;
        }

        protected override void Update()
        {
            base.Update();

            double currentTime = currentTimeProvider();
            threeDHighwayBackground?.UpdateScroll(currentTime);
            float laneWidth = DrawWidth / laneCount;
            float hitLineY = DrawHeight * 0.85f;
            float spawnTop = currentLaneViewMode == LaneViewMode.ThreeDimensional ? DrawHeight * 0.15f : DrawHeight * 0.05f;
            float travelDistance = hitLineY - spawnTop;

            foreach (var note in notes)
            {
                if (note.IsJudged)
                    continue;

                double timeUntilHit = note.HitTime - currentTime;
                double progress = 1 - (timeUntilHit / approachDuration);

                float clampedProgress = (float)Math.Clamp(progress, 0, 1.15);
                note.SetApproachProgress((float)Math.Clamp(progress, 0, 1));

                if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
                    updateNoteTransform3D(note, clampedProgress);
                else
                    updateNoteTransform2D(note, laneWidth, hitLineY, travelDistance, spawnTop, clampedProgress);

                // In preview mode, always show notes (they'll be positioned off-screen if far away)
                // In gameplay mode, hide notes that are way past the hit line
                if (isPreviewMode)
                {
                    // Always visible in preview mode - let the position determine visibility
                    note.Alpha = 1;
                }
                else
                {
                    note.Alpha = timeUntilHit < -200 ? 0 : 1;
                }

                // Only auto-judge misses in actual gameplay, not in editor preview mode
                if (!isPreviewMode && timeUntilHit < -missWindow)
                    applyResult(note, HitResult.Miss, timeUntilHit);
            }
        }

        private void updateNoteTransform2D(DrawableNote note, float laneWidth, float hitLineY, float travelDistance, float spawnTop, float progress)
        {
            float y = hitLineY - travelDistance * (1 - progress);
            y = Math.Clamp(y, spawnTop, hitLineY + 40);

            float x = laneWidth * note.Lane + laneWidth / 2f;

            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;
            setNoteDepth(note, -y);
        }

        private void updateNoteTransform3D(DrawableNote note, float progress)
        {
            float t = Math.Clamp(progress, 0f, 1f);
            float centerX = DrawWidth / 2f;
            float bottomY = DrawHeight * 0.85f;
            float topY = DrawHeight * 0.15f;

            float laneOffset = note.Lane - (laneCount - 1) / 2f;
            float bottomSpacing = DrawWidth * 0.14f;
            float topSpacing = bottomSpacing * 0.42f;

            float xTop = centerX + laneOffset * topSpacing;
            float xBottom = centerX + laneOffset * bottomSpacing;
            float x = lerp(xTop, xBottom, t);
            float y = lerp(topY, bottomY, t);
            y = Math.Clamp(y, topY, bottomY + 40);

            float horizontalTilt = (float)(Math.Atan2(xBottom - xTop, bottomY - topY) * 180 / Math.PI);
            float scale = lerp(0.50f, 1.10f, t);
            float stretch = lerp(0.80f, 1.02f, t);

            if (note.IsKick)
            {
                stretch *= 0.4f;
                scale *= 1.08f;
                y += 5;
            }

            y = Math.Clamp(y, topY, bottomY + 20);

            note.Position = new Vector2(x, y);
            note.Scale = new Vector2(scale, stretch);
            note.Rotation = horizontalTilt;
            setNoteDepth(note, -t * 1000);
        }

        private static float lerp(float start, float end, float amount) => start + (end - start) * amount;

        private void setNoteDepth(DrawableNote note, float depth)
        {
            if (noteLayer != null && note.Parent == noteLayer)
                noteLayer.ChangeChildDepth(note, depth);
        }

        private void applyResult(DrawableNote note, HitResult result, double offset)
        {
            if (note.IsJudged)
                return;

            note.ApplyResult(result);
            ResultApplied?.Invoke(result, offset, note.AccentColour);
            hitErrorMeter?.AddHit(offset, result);

            // Skip scoring in manual mode
            if (gameplayMode.Value == GameplayMode.Manual)
                return;

            judgedNotes++;
            if (result == HitResult.Miss)
            {
                combo = 0;
                missCount++;
            }
            else
            {
                combo++;
                maxCombo = Math.Max(maxCombo, combo);

                // Update counters
                switch (result)
                {
                    case HitResult.Perfect:
                        perfectCount++;
                        break;
                    case HitResult.Great:
                        greatCount++;
                        break;
                    case HitResult.Good:
                        goodCount++;
                        break;
                    case HitResult.Meh:
                        mehCount++;
                        break;
                }
            }

            comboText.Text = $"Combo: {combo}";

            // Add combo milestone animations
            if (showComboMilestones.Value && combo > 0 && combo % 50 == 0)
                comboText.ScaleTo(1.3f, 100, Easing.OutQuint).Then().ScaleTo(1f, 300, Easing.OutBounce);

            accuracyScore += scoreFor(result);
            updateAccuracyText();

            var accent = note.AccentColour;
            string label = result switch
            {
                HitResult.Perfect => "Perfect",
                HitResult.Great => "Great",
                HitResult.Good => "Good",
                HitResult.Meh => "Meh",
                HitResult.Miss => "Miss",
                _ => string.Empty
            };

            if (result != HitResult.Miss)
            {
                int displayOffset = (int)Math.Round(offset);
                string offsetLabel = displayOffset == 0 ? "±0ms" : displayOffset > 0 ? $"+{displayOffset}ms" : $"{displayOffset}ms";
                judgementText.Text = $"{label} {offsetLabel}";
            }
            else
            {
                judgementText.Text = label;
            }

            judgementText.FlashColour(accent, 80, Easing.OutQuint);
        }

        private void updateAccuracyText()
        {
            if (totalNotes == 0 || judgedNotes == 0)
            {
                accuracyText.Text = "Accuracy: --";
                return;
            }

            double accuracy = Math.Clamp(accuracyScore / totalNotes, 0, 1) * 100;
            accuracyText.Text = $"Accuracy: {accuracy:0.00}%";
        }

        private static double scoreFor(HitResult result) => result switch
        {
            HitResult.Perfect => 1.0,
            HitResult.Great => 0.8,
            HitResult.Good => 0.5,
            HitResult.Meh => 0.2,
            _ => 0,
        };

        private static int resolveLane(HitObject hit)
        {
            int lane = hit.Lane ?? DrumLaneHeuristics.ResolveLane(hit.Component);
            return Math.Clamp(lane, 0, laneCount - 1);
        }

        private partial class HitErrorMeter : CompositeDrawable
        {
            private readonly Container markerLayer;

            public HitErrorMeter()
            {
                RelativeSizeAxes = Axes.X;
                Height = 28;
                Masking = true;
                CornerRadius = 8;

                InternalChildren = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(28, 32, 48, 220)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 2,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Colour = new Color4(255, 255, 255, 90)
                    },
                    markerLayer = new Container
                    {
                        RelativeSizeAxes = Axes.Both
                    }
                };
            }

            public void AddHit(double offset, HitResult result)
            {
                float normalized = (float)Math.Clamp(offset / missWindow, -1, 1);

                var marker = new Container
                {
                    Size = new Vector2(8, 20),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    RelativePositionAxes = Axes.X,
                    X = normalized * 0.48f,
                    Alpha = 0,
                    Masking = true,
                    CornerRadius = 3
                };

                marker.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = colourFor(result)
                });

                markerLayer.Add(marker);

                marker.FadeIn(80, Easing.OutQuint)
                      .Then()
                      .Delay(700)
                      .FadeOut(220, Easing.OutQuint)
                      .Expire();

                while (markerLayer.Children.Count > 18)
                    markerLayer.Children.First().Expire();
            }

            private static Color4 colourFor(HitResult result) => result switch
            {
                HitResult.Perfect => new Color4(140, 255, 200, 255),
                HitResult.Great => new Color4(120, 200, 255, 255),
                HitResult.Good => new Color4(255, 230, 140, 255),
                HitResult.Meh => new Color4(255, 170, 120, 255),
                HitResult.Miss => new Color4(255, 110, 140, 255),
                _ => new Color4(200, 200, 220, 255)
            };
        }

        private partial class ThreeDHighwayBackground : CompositeDrawable
        {
            private readonly int laneCount;
            private readonly List<Box> timelineStripes = new List<Box>();

            public ThreeDHighwayBackground(int laneCount)
            {
                this.laneCount = laneCount;
                RelativeSizeAxes = Axes.Both;
                Masking = true;
                CornerRadius = 18;
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                var layers = new List<Drawable>
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(18, 18, 28, 255)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 260,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Colour = new Color4(90, 100, 160, 90)
                    },
                    createLaneSeparatorLayer(),
                    createKickGuideLayer(),
                    createTimelineStripeLayer(),
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 160,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Colour = new Color4(255, 255, 255, 30)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 8,
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        Colour = new Color4(65, 70, 120, 120),
                        Alpha = 0.45f
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 8,
                        Anchor = Anchor.BottomRight,
                        Origin = Anchor.BottomRight,
                        Colour = new Color4(65, 70, 120, 120),
                        Alpha = 0.45f
                    }
                };

                InternalChildren = layers.ToArray();
            }

            private Drawable createLaneSeparatorLayer()
            {
                var container = new Container
                {
                    RelativeSizeAxes = Axes.Both
                };

                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(26, 26, 40, 255),
                    Alpha = 0.55f
                });

                for (int lane = 0; lane < laneCount; lane++)
                {
                    float normalized = laneCount <= 1
                        ? 0
                        : (lane - (laneCount - 1) / 2f) / (laneCount - 1);

                    container.Add(new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 4,
                        Height = 0.9f,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        RelativePositionAxes = Axes.X,
                        X = normalized * 0.62f,
                        Rotation = normalized * 18f,
                        Colour = new Color4(70, 80, 130, 160),
                        Alpha = 0.4f
                    });
                }

                return container;
            }

            private Drawable createKickGuideLayer()
            {
                float kickNormalized = laneCount <= 1
                    ? 0
                    : (0 - (laneCount - 1) / 2f) / (laneCount - 1);

                var band = new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Width = 0.28f,
                    Height = 90,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Y = -40,
                    Shear = new Vector2(-0.25f, 0),
                    RelativePositionAxes = Axes.X,
                    X = kickNormalized * 0.62f,
                    Rotation = kickNormalized * 18f
                };

                band.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(110, 70, 40, 120)
                });

                for (int i = 0; i < 6; i++)
                {
                    band.Add(new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Width = 1f,
                        Height = 3,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Y = -i * 14,
                        Colour = new Color4(255, 190, 140, 180)
                    });
                }

                band.Add(new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Width = 1f,
                    Height = 4,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = new Color4(255, 220, 180, 200)
                });

                return band;
            }

            private Drawable createTimelineStripeLayer()
            {
                var stripeLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                };

                const int stripeCount = 14;
                for (int i = 0; i < stripeCount; i++)
                {
                    float depth = stripeCount <= 1 ? 1f : i / (float)(stripeCount - 1);
                    float width = 0.55f + 0.45f * depth;

                    var stripe = new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 2,
                        Width = width,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Colour = new Color4(255, 255, 255, (byte)(40 + depth * 60)),
                        Alpha = 0.5f,
                        Shear = new Vector2(-0.25f, 0)
                    };

                    stripeLayer.Add(stripe);
                    timelineStripes.Add(stripe);
                }

                return stripeLayer;
            }

            public void UpdateScroll(double currentTime)
            {
                if (timelineStripes.Count == 0 || DrawHeight <= 0)
                    return;

                float baseOffset = (float)((currentTime * 0.0006) % 1.0);

                for (int i = 0; i < timelineStripes.Count; i++)
                {
                    float offset = (i / (float)timelineStripes.Count) + baseOffset;
                    offset -= MathF.Floor(offset);
                    float y = -offset * DrawHeight;
                    timelineStripes[i].Y = y;
                }
            }
        }

        public enum HitResult
        {
            None,
            Miss,
            Meh,
            Good,
            Great,
            Perfect
        }
    }

    internal partial class DrawableNote : CompositeDrawable
    {
        private static readonly Dictionary<string, Color4> componentColours = new Dictionary<string, Color4>
        {
            {"kick", new Color4(255, 105, 97, 255)},
            {"snare", new Color4(64, 156, 255, 255)},
            {"hihat", new Color4(255, 221, 89, 255)},
            {"hihat_closed", new Color4(255, 221, 89, 255)},
            {"hihat_open", new Color4(255, 195, 0, 255)},
            {"tom_high", new Color4(138, 201, 38, 255)},
            {"tom_mid", new Color4(76, 201, 240, 255)},
            {"tom_low", new Color4(128, 128, 255, 255)},
            {"crash", new Color4(255, 159, 243, 255)},
            {"ride", new Color4(250, 177, 160, 255)},
            {"china", new Color4(255, 204, 92, 255)}
        };

        public double HitTime { get; }
        public int Lane { get; }
        public bool IsJudged { get; private set; }
        public string ComponentName { get; }
        public Color4 AccentColour { get; }
        public bool IsKick => isKickNote;

        private readonly Box mainBox;
        private readonly Box highlightStrip;
        private readonly Box? glowBox;
        private readonly CircularContainer? approachCircle;
        private readonly Bindable<bool> showApproachCircles;
        private readonly Bindable<bool> showGlowEffects;
        private readonly Bindable<bool> showParticleEffects;
        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private float approachProgress = 1f;
        private readonly bool isKickNote;

        public DrawableNote(HitObject hitObject, int lane, Bindable<bool> showApproach, Bindable<bool> showGlow, Bindable<bool> showParticles)
        {
            HitTime = hitObject.Time;
            ComponentName = hitObject.Component;
            Lane = lane;
            showApproachCircles = showApproach;
            showGlowEffects = showGlow;
            showParticleEffects = showParticles;
            isKickNote = !string.IsNullOrEmpty(hitObject.Component) && hitObject.Component.IndexOf("kick", StringComparison.OrdinalIgnoreCase) >= 0;

            Size = new Vector2(60, 26);
            CornerRadius = 8;
            Masking = true;

            AccentColour = componentColours.TryGetValue(hitObject.Component.ToLowerInvariant(), out var colour)
                ? colour
                : new Color4(180, 180, 200, 255);

            Colour = AccentColour;

            var children = new List<Drawable>();

            // Add glow box first if enabled
            if (showGlow.Value)
            {
                glowBox = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = AccentColour,
                    Alpha = 0.3f,
                    Blending = BlendingParameters.Additive,
                };
                children.Add(glowBox);
            }

            // Always add main box
            mainBox = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = AccentColour
            };
            children.Add(mainBox);

            highlightStrip = new Box
            {
                RelativeSizeAxes = Axes.X,
                Width = 0.8f,
                Height = 5,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = new Color4(255, 255, 255, 90),
                Alpha = 0.35f
            };
            children.Add(highlightStrip);

            // Add approach circle if enabled
            if (showApproach.Value)
            {
                approachCircle = new CircularContainer
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Size = new Vector2(80, 80),
                    Masking = true,
                    BorderThickness = 3,
                    BorderColour = AccentColour,
                    Alpha = 0.8f,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Alpha = 0,
                        AlwaysPresent = true
                    }
                };
                children.Add(approachCircle);
            }

            InternalChildren = children.ToArray();

            SetViewMode(viewMode);
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Pulse animation for glow (must be started after loading)
            if (showGlowEffects.Value && glowBox != null)
                glowBox.Loop(b => b.FadeTo(0.5f, 600).Then().FadeTo(0.2f, 600));
        }

        protected override void Update()
        {
            base.Update();

            // Approach circle scales down as note gets closer
            if (!IsJudged && showApproachCircles.Value && approachCircle != null && approachCircle.Alpha > 0)
            {
                float progress = Math.Clamp(approachProgress, 0f, 1f);
                approachCircle.Scale = new Vector2(1 + (1 - progress) * 2);
            }
        }

        public void SetViewMode(LaneViewMode mode)
        {
            viewMode = mode;

            if (viewMode == LaneViewMode.TwoDimensional)
            {
                CornerRadius = 8;
                mainBox.Shear = Vector2.Zero;
                Size = new Vector2(60, 26);
                highlightStrip.Alpha = 0.3f;
                highlightStrip.Width = 0.75f;
                highlightStrip.Height = 5;
                highlightStrip.Anchor = Anchor.TopCentre;
                highlightStrip.Origin = Anchor.TopCentre;
                highlightStrip.Colour = new Color4(255, 255, 255, 90);
                if (!IsJudged)
                {
                    Rotation = 0;
                    Scale = Vector2.One;
                }
            }
            else
            {
                CornerRadius = 4;
                mainBox.Shear = new Vector2(-0.25f, 0);
                Size = isKickNote ? new Vector2(88, 20) : new Vector2(74, 24);
                highlightStrip.Alpha = 0.6f;
                highlightStrip.Width = isKickNote ? 1f : 0.9f;
                highlightStrip.Height = isKickNote ? 3 : 5;
                highlightStrip.Anchor = Anchor.TopCentre;
                highlightStrip.Origin = Anchor.TopCentre;
                highlightStrip.Colour = isKickNote
                    ? new Color4(255, 220, 180, 200)
                    : new Color4(255, 255, 255, 130);
            }
        }

        public void SetApproachProgress(float progress) => approachProgress = Math.Clamp(progress, 0f, 1f);

        public void ApplyResult(GameplayPlayfield.HitResult result)
        {
            if (IsJudged)
                return;

            IsJudged = true;

            // Hide approach circle
            if (showApproachCircles.Value && approachCircle != null)
                approachCircle.FadeOut(100);

            switch (result)
            {
                case GameplayPlayfield.HitResult.Miss:
                    this.FlashColour(new Color4(255, 80, 90, 255), 120, Easing.OutQuint);
                    this.FadeColour(new Color4(120, 20, 30, 200), 120, Easing.OutQuint);
                    this.MoveToY(Y + 20, 200, Easing.OutQuint);
                    this.Delay(150).FadeOut(180).Expire();
                    break;

                case GameplayPlayfield.HitResult.Perfect:
                case GameplayPlayfield.HitResult.Great:
                    if (showParticleEffects.Value)
                    {
                        // Burst effect
                        this.ScaleTo(1.4f, 100, Easing.OutQuint);
                        this.FadeOut(150, Easing.OutQuint).Expire();

                        // Glow burst
                        if (showGlowEffects.Value && glowBox != null)
                        {
                            glowBox.ScaleTo(2f, 200, Easing.OutQuint);
                            glowBox.FadeOut(200, Easing.OutQuint);
                        }
                    }
                    else
                    {
                        this.FadeOut(150).Expire();
                    }
                    break;

                default:
                    this.FadeOut(180).ScaleTo(1.2f, 180, Easing.OutQuint).Expire();
                    break;
            }
        }
    }
}
