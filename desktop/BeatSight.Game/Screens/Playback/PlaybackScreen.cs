using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Customization;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using BeatSight.Game.Screens.Playback.Playfield;
using osu.Framework.Allocation;
using osu.Framework.Audio;
using osu.Framework.Audio.Sample;
using osu.Framework.Audio.Track;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.IO.Stores;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osu.Framework.Timing;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback
{
    public partial class PlaybackScreen : Screen
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

        private static readonly Dictionary<int, osuTK.Input.Key[]> defaultLaneKeyLayouts = new()
        {
            { 4, new[] { osuTK.Input.Key.D, osuTK.Input.Key.F, osuTK.Input.Key.J, osuTK.Input.Key.K } },
            { 5, new[] { osuTK.Input.Key.S, osuTK.Input.Key.D, osuTK.Input.Key.Space, osuTK.Input.Key.J, osuTK.Input.Key.K } },
            { 6, new[] { osuTK.Input.Key.S, osuTK.Input.Key.D, osuTK.Input.Key.F, osuTK.Input.Key.J, osuTK.Input.Key.K, osuTK.Input.Key.L } },
            { 7, new[] { osuTK.Input.Key.S, osuTK.Input.Key.D, osuTK.Input.Key.F, osuTK.Input.Key.Space, osuTK.Input.Key.J, osuTK.Input.Key.K, osuTK.Input.Key.L } },
            { 8, new[] { osuTK.Input.Key.A, osuTK.Input.Key.S, osuTK.Input.Key.D, osuTK.Input.Key.F, osuTK.Input.Key.J, osuTK.Input.Key.K, osuTK.Input.Key.L, osuTK.Input.Key.Semicolon } }
        };

        private static readonly osuTK.Input.Key[] fallbackLaneKeyOrder =
        {
            osuTK.Input.Key.S,
            osuTK.Input.Key.D,
            osuTK.Input.Key.F,
            osuTK.Input.Key.Space,
            osuTK.Input.Key.J,
            osuTK.Input.Key.K,
            osuTK.Input.Key.L,
            osuTK.Input.Key.Semicolon,
            osuTK.Input.Key.A,
            osuTK.Input.Key.LControl
        };

        private readonly string? requestedBeatmapPath;
        private double fallbackElapsed;
        private bool fallbackRunning;

        protected Beatmap? beatmap;
        protected string? beatmapPath;
        protected Track? track;

        protected PlaybackPlayfield? playfield;
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
            MinValue = 0.0,
            MaxValue = 2.0,
            Default = 1.0,
            Precision = 0.01
        };
        private double offsetMilliseconds;
        private double playbackSpeed = 1.0;
        private bool pausedByZeroSpeed;
        private BasicButton playPauseButton = null!;
        private BasicButton viewModeToggleButton = null!;
        private BasicButton kickLayoutToggleButton = null!;
        private BasicButton metronomeToggleButton = null!;
        private BasicButton mixToggleButton = null!;
        private bool drumsOnlyMode;
        private Bindable<bool> drumStemPreferredSetting = null!;
        private bool drumStemAvailable;
        private string? cachedFullMixPath;
        private string? cachedDrumStemPath;
        private bool isTrackRunning;
        private StorageBackedResourceStore? storageResourceStore;
        private ITrackStore? storageTrackStore;
        private ISampleStore? storageSampleStore;
        private NamespacedResourceStore<byte[]>? embeddedResourceStore;
        private ISampleStore? embeddedSampleStore;

        private Bindable<double> musicVolumeSetting = null!;
        private Bindable<double> masterVolumeSetting = null!;
        private Bindable<double> effectVolumeSetting = null!;
        private Bindable<double> hitsoundVolumeSetting = null!;
        private Bindable<bool> masterVolumeEnabledSetting = null!;
        private Bindable<bool> musicVolumeEnabledSetting = null!;
        private Bindable<bool> effectVolumeEnabledSetting = null!;
        private Bindable<bool> hitsoundVolumeEnabledSetting = null!;
        private Bindable<bool> metronomeEnabledSetting = null!;
        private Bindable<MetronomeSoundOption> metronomeSoundSetting = null!;
        private readonly BindableDouble metronomeVolume = new BindableDouble
        {
            MinValue = 0,
            MaxValue = 1,
            Precision = 0.05,
            Default = 0.6,
            Value = 0.6
        };
        private Sample? metronomeAccentSample;
        private Sample? metronomeRegularSample;
        private SampleChannel? activeMetronomeChannel;
        private SampleChannel? activeMetronomeAccentChannel;
        private int lastMetronomeBeatIndex = -1;
        private bool pendingMetronomePulse;
        private bool suppressMetronomeUntilBeatChange;
        protected event Action<double>? MetronomeTick;

        private Bindable<double> speedMinSetting = null!;
        private Bindable<double> speedMaxSetting = null!;
        private Bindable<KickLaneMode> kickLaneModeSetting = null!;
        private Bindable<double> audioOffsetSetting = null!;
        private Bindable<double> hitsoundOffsetSetting = null!;
        private Bindable<LanePreset> lanePresetSetting = null!;
        private Bindable<LaneViewMode> laneViewModeSetting = null!;
        private Bindable<double> backgroundDimSetting = null!;
        private Bindable<double> backgroundBlurSetting = null!;
        private Bindable<bool> hitLightingEnabled = null!;

        private readonly BindableDouble zoomLevel = new BindableDouble(1.0)
        {
            MinValue = 0.5,
            MaxValue = 1.5,
            Precision = 0.01,
            Default = 1.0
        };
        private readonly BindableBool autoZoom = new BindableBool(true);
        private readonly BindableDouble noteWidthScale = new BindableDouble(1.0)
        {
            MinValue = 0.5,
            MaxValue = 1.5,
            Precision = 0.01,
            Default = 1.0
        };

        private bool offsetSyncInProgress;
        private string currentStatusMessage = "Loading beatmap…";

        private BackButton backButton = null!;
        private BufferedContainer backgroundBlurContainer = null!;
        private Box backgroundBase = null!;
        private Box backgroundDim = null!;
        private Box hitLightingOverlay = null!;
        private Container playfieldContainer = null!;
        private ScrubbableSliderBar timelineSlider = null!;
        private SpriteText timelineCurrentText = null!;
        private SpriteText timelineTotalText = null!;
        private readonly BindableDouble playbackProgress = new BindableDouble { MinValue = 0, MaxValue = 1, Precision = 0.0001 };
        private bool suppressPlaybackProgressUpdate;
        private bool isScrubbingPlayback;
        private bool wasPlayingBeforeScrub;
        private double? pendingSeekNormalized;
        private double cachedTrackDurationMs;

        private LaneLayout currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);

        private const float maxBackgroundBlurSigma = 25f;
        private static readonly Color4 sidebarButtonInactive = new Color4(48, 56, 86, 255);
        private static readonly Color4 sidebarButtonActive = new Color4(92, 138, 220, 255);
        private const string userSkinDirectory = UserAssetDirectories.Skins;
        private const string userMetronomeDirectory = UserAssetDirectories.MetronomeSounds;

        protected IBindable<bool> MetronomeEnabledBinding => metronomeEnabledSetting;
        protected IBindable<MetronomeSoundOption> MetronomeSoundBinding => metronomeSoundSetting;
        protected IBindable<double> MetronomeVolumeBinding => metronomeVolume;
        private bool KickLineEnabled => (kickLaneModeSetting?.Value ?? KickLaneMode.GlobalLine) == KickLaneMode.GlobalLine;

        [Resolved]
        private AudioManager audioManager { get; set; } = null!;

        [Resolved]
        private GameHost host { get; set; } = null!;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        [Resolved]
        private MapPlaybackSettingsManager mapSettings { get; set; } = null!;

        public PlaybackScreen(string? beatmapPath = null)
        {
            requestedBeatmapPath = beatmapPath;
        }


        [BackgroundDependencyLoader]
        private void load()
        {
            // Pre-fetch lane configuration so the playfield reflects user settings before UI construction.
            lanePresetSetting = config.GetBindable<LanePreset>(BeatSightSetting.LanePreset);
            currentLaneLayout = LaneLayoutFactory.Create(lanePresetSetting.Value);

            laneViewModeSetting = config.GetBindable<LaneViewMode>(BeatSightSetting.LaneViewMode);
            kickLaneModeSetting = config.GetBindable<KickLaneMode>(BeatSightSetting.KickLaneMode);

            // Bind zoom and note width to config
            var configZoom = config.GetBindable<double>(BeatSightSetting.PlaybackZoomLevel);
            zoomLevel.Value = configZoom.Value;
            zoomLevel.BindValueChanged(v => configZoom.Value = v.NewValue);
            configZoom.BindValueChanged(v => zoomLevel.Value = v.NewValue);

            var configNoteWidth = config.GetBindable<double>(BeatSightSetting.PlaybackNoteWidth);
            noteWidthScale.Value = configNoteWidth.Value;
            noteWidthScale.BindValueChanged(v => configNoteWidth.Value = v.NewValue);
            configNoteWidth.BindValueChanged(v => noteWidthScale.Value = v.NewValue);

            autoZoom.BindValueChanged(e =>
            {
                if (e.NewValue)
                    zoomLevel.Value = 1.0;

                if (beatmap != null)
                {
                    var settings = mapSettings.Get(beatmap.Metadata.BeatmapId);
                    settings.AutoZoom = e.NewValue;
                    mapSettings.Set(beatmap.Metadata.BeatmapId, settings);
                }
            });

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
                Alpha = 0.5f
            };

            hitLightingOverlay = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = Color4.White,
                Alpha = 0,
                Blending = BlendingParameters.Additive
            };

            backButton = new BackButton
            {
                Margin = BackButton.DefaultMargin,
                Action = () => this.Exit()
            };

            InternalChildren = new Drawable[]
            {
                backgroundBlurContainer,
                backgroundDim,
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Top = BackButton.DefaultMargin.Top },
                    Child = new GridContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        RowDimensions = new[]
                        {
                            new Dimension(GridSizeMode.Absolute, 86),
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
                                createMainContent()
                            }
                        }
                    }
                },
                new SafeAreaContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = BackButton.DefaultMargin,
                    Child = backButton
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

            masterVolumeSetting = config.GetBindable<double>(BeatSightSetting.MasterVolume);
            musicVolumeSetting = config.GetBindable<double>(BeatSightSetting.MusicVolume);
            effectVolumeSetting = config.GetBindable<double>(BeatSightSetting.EffectVolume);
            hitsoundVolumeSetting = config.GetBindable<double>(BeatSightSetting.HitsoundVolume);
            masterVolumeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.MasterVolumeEnabled);
            musicVolumeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.MusicVolumeEnabled);
            effectVolumeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.EffectVolumeEnabled);
            hitsoundVolumeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.HitsoundVolumeEnabled);
            metronomeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.MetronomeEnabled);
            metronomeSoundSetting = config.GetBindable<MetronomeSoundOption>(BeatSightSetting.MetronomeSound);
            metronomeVolume.BindTo(config.GetBindable<double>(BeatSightSetting.MetronomeVolume));

            metronomeEnabledSetting.BindValueChanged(e =>
            {
                pendingMetronomePulse = false;
                updateMetronomeToggle(e.NewValue);
                lastMetronomeBeatIndex = -1;
                if (e.NewValue)
                {
                    suppressMetronomeUntilBeatChange = isPlaybackActive();
                    pendingMetronomePulse = true;
                }
                else
                {
                    suppressMetronomeUntilBeatChange = false;
                    stopMetronomeChannels();
                }
            }, true);
            metronomeSoundSetting.BindValueChanged(e => loadMetronomeSamples(e.NewValue), true);
            drumStemPreferredSetting = config.GetBindable<bool>(BeatSightSetting.DrumStemPlaybackOnly);
            drumStemPreferredSetting.BindValueChanged(e => applyDrumStemPreference(e.NewValue), true);
            lanePresetSetting.BindValueChanged(onLanePresetChanged, true);
            laneViewModeSetting.BindValueChanged(e => updateViewModeToggle(e.NewValue), true);
            kickLaneModeSetting.BindValueChanged(e => updateKickLayoutToggle(e.NewValue), true);
            // Ensure playback speed starts at default before clamping to configured bounds.
            speedAdjustment.Value = speedAdjustment.Default;
            playbackSpeed = speedAdjustment.Value;

            audioOffsetSetting = config.GetBindable<double>(BeatSightSetting.AudioOffset);
            hitsoundOffsetSetting = config.GetBindable<double>(BeatSightSetting.HitsoundOffset);
            speedMinSetting = config.GetBindable<double>(BeatSightSetting.SpeedAdjustmentMin);
            speedMaxSetting = config.GetBindable<double>(BeatSightSetting.SpeedAdjustmentMax);
            speedMinSetting.BindValueChanged(_ => updateSpeedSliderBounds(), true);
            speedMaxSetting.BindValueChanged(_ => updateSpeedSliderBounds(), true);
            audioOffsetSetting.BindValueChanged(_ => syncOffsetWithConfig(), true);

            loadBeatmap();

            offsetAdjustment.BindValueChanged(value =>
            {
                if (offsetSyncInProgress)
                    return;

                offsetSyncInProgress = true;

                offsetMilliseconds = value.NewValue;
                audioOffsetSetting.Value = value.NewValue;
                hitsoundOffsetSetting.Value = value.NewValue;
                if (offsetValueText != null)
                    offsetValueText.Text = formatOffsetLabel(value.NewValue);

                offsetSyncInProgress = false;
            }, true);

            speedAdjustment.BindValueChanged(value =>
            {
                playbackSpeed = value.NewValue;

                if (playbackSpeed <= 0.001)
                {
                    if (isPlaybackActive())
                    {
                        stopPlayback();
                        pausedByZeroSpeed = true;
                    }
                }
                else
                {
                    if (pausedByZeroSpeed)
                    {
                        startPlayback(false);
                        pausedByZeroSpeed = false;
                    }

                    if (track != null)
                    {
                        // Ensure track is running if it should be
                        if (!isTrackRunning && isPlaybackActive())
                        {
                            // If we were in fallback mode, sync track to fallback time
                            if (fallbackRunning)
                            {
                                track.Seek(fallbackElapsed);
                                fallbackRunning = false;
                            }

                            track.Start();
                            isTrackRunning = true;
                        }

                        try
                        {
                            if (playbackSpeed < 0.05)
                            {
                                // For very low speeds, we combine Tempo and Frequency to maintain audibility.
                                // Tempo (Time Stretch) is limited to 0.05x to avoid exceptions/limits.
                                // We use Frequency (Pitch Shift) to achieve the remaining slowdown.
                                track.Tempo.Value = 0.05;
                                track.Frequency.Value = playbackSpeed / 0.05;
                            }
                            else
                            {
                                // Use Tempo (Time Stretch) for normal speeds
                                track.Frequency.Value = 1.0;
                                track.Tempo.Value = playbackSpeed;
                            }
                        }
                        catch
                        {
                            // Fallback safety
                            track.Tempo.Value = Math.Max(0.05, playbackSpeed);
                        }
                    }
                }

                if (speedValueText != null)
                    speedValueText.Text = formatSpeedLabel(value.NewValue);
            }, true);
        }

        private Drawable createHeader()
        {
            statusText = new SpriteText
            {
                Font = BeatSightFont.Section(24f),
                Colour = Color4.White,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
            };

            applyHeaderStatus();

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding { Left = 150, Right = 28, Top = 20, Bottom = 6 },
                Child = statusText
            };
        }

        private Drawable createPlayfieldArea()
        {
            playfield = new PlaybackPlayfield(getCurrentTime)
            {
                RelativeSizeAxes = Axes.Both,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Size = Vector2.One
            };

            playfield.ZoomLevel.BindTo(zoomLevel);
            playfield.AutoZoom.BindTo(autoZoom);
            playfield.NoteWidthScale.BindTo(noteWidthScale);

            playfield.ResultApplied += onPlayfieldResult;
            playfield.SetLaneLayout(currentLaneLayout);
            playfield.SetKickLineMode(KickLineEnabled);
            rebuildLaneKeyBindings();

            return playfieldContainer = new PlayfieldViewportContainer(playfield);
        }

        private Drawable createBottomToolbar()
        {
            timelineSlider = new ScrubbableSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 12,
                Current = playbackProgress
            };

            timelineSlider.ScrubbingChanged += onScrubbingStateChanged;
            playbackProgress.BindValueChanged(onPlaybackProgressChanged);

            timelineCurrentText = new SpriteText
            {
                Text = "0:00",
                Font = BeatSightFont.Section(14f),
                Colour = new Color4(200, 205, 220, 255),
                Shadow = false
            };

            timelineTotalText = new SpriteText
            {
                Text = "--:--",
                Font = BeatSightFont.Section(14f),
                Colour = new Color4(150, 160, 185, 255),
                Shadow = false
            };

            var buttonFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(10, 0),
                Children = new Drawable[]
                {
                    playPauseButton = createToolbarButton("Pause", togglePlayback),
                    createToolbarButton("Restart", restartSessionFromUi)
                }
            };

            var sliderContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding { Left = 18, Right = 12, Top = 4, Bottom = 4 },
                Children = new Drawable[]
                {
                    timelineSlider,
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.BottomRight,
                        Origin = Anchor.BottomRight,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(6, 0),
                        Margin = new MarginPadding { Top = 20 },
                        Children = new Drawable[]
                        {
                            timelineCurrentText,
                            new SpriteText
                            {
                                Text = "/",
                                Font = BeatSightFont.Caption(14f),
                                Colour = new Color4(150, 160, 185, 255),
                                Shadow = false
                            },
                            timelineTotalText
                        }
                    }
                }
            };

            var playbackRow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(8, 10),
                Children = new Drawable[]
                {
                    buttonFlow,
                    sliderContainer
                }
            };

            var controlGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.33f),
                    new Dimension(GridSizeMode.Relative, 0.33f),
                    new Dimension(GridSizeMode.Relative, 0.34f)
                },
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createControlGroup("Timing & Audio", createTimingAudioContent()),
                        createControlGroup("Stage Layout", createStageContent()),
                        createControlGroup("Visuals", createVisualControls())
                    }
                }
            };

            updatePlayPauseButton();

            return new HoverableToolbarContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                Padding = new MarginPadding { Bottom = 10 }, // Prevent clipping at screen edge
                Child = new Container
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Masking = true,
                    CornerRadius = 18,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(14, 16, 26, 180)
                        },
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                                Padding = new MarginPadding { Horizontal = 20, Vertical = 14 },
                                Spacing = new Vector2(12, 12),
                            Children = new Drawable[]
                            {
                                playbackRow,
                                controlGrid
                            }
                        }
                    }
                }
            };
        }

        private BasicButton createToolbarButton(string label, Action action)
        {
            return new BasicButton
            {
                Width = 110,
                Height = 34,
                CornerRadius = 8,
                Masking = true,
                Text = label,
                Action = action,
                BackgroundColour = sidebarButtonInactive
            };
        }

        private Drawable createControlGroup(string title, Drawable content)
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding { Right = 16, Bottom = 8 },
                Child = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(5, 0),
                    Children = new Drawable[]
                    {
                        new SpriteText
                        {
                            Text = title,
                            Font = BeatSightFont.Section(15f),
                            Colour = Color4.White
                        },
                        content
                    }
                }
            };
        }

        private void onScrubbingStateChanged(bool scrubbing)
        {
            isScrubbingPlayback = scrubbing;

            if (scrubbing)
            {
                wasPlayingBeforeScrub = isTrackRunning;
                if (isTrackRunning)
                    stopPlayback();
            }
            else
            {
                pendingSeekNormalized = null; // Cancel any pending throttled seek
                seekToNormalized(playbackProgress.Value, allowStateReset: true);
                updatePlaybackProgressUI();

                if (wasPlayingBeforeScrub)
                    startPlayback(restart: false);
            }
        }

        private void onPlaybackProgressChanged(ValueChangedEvent<double> value)
        {
            if (suppressPlaybackProgressUpdate)
                return;

            if (isScrubbingPlayback)
            {
                pendingSeekNormalized = value.NewValue;
                Scheduler.AddOnce(performPendingSeek);
            }
            else
            {
                seekToNormalized(value.NewValue, allowStateReset: !isScrubbingPlayback);
                updatePlaybackProgressUI();
            }
        }

        private void performPendingSeek()
        {
            if (pendingSeekNormalized.HasValue)
            {
                seekToNormalized(pendingSeekNormalized.Value, allowStateReset: false);
                updatePlaybackProgressUI();
                pendingSeekNormalized = null;
            }
        }

        private void updatePlaybackProgressUI()
        {
            if (timelineSlider == null)
                return;

            double duration = getPlaybackDuration();
            double current = track?.CurrentTime ?? fallbackElapsed;
            updatePlaybackProgressUI(current, duration);
        }

        private void updatePlaybackProgressUI(double currentMs, double durationMs)
        {
            if (timelineSlider == null)
                return;

            if (durationMs > 0)
                currentMs = Math.Clamp(currentMs, 0, durationMs);
            else
                currentMs = Math.Max(0, currentMs);

            suppressPlaybackProgressUpdate = true;
            playbackProgress.Value = durationMs <= 0 ? 0 : Math.Clamp(currentMs / durationMs, 0, 1);
            suppressPlaybackProgressUpdate = false;

            timelineCurrentText.Text = formatTimestamp(currentMs);
            timelineTotalText.Text = durationMs <= 0 ? "--:--" : formatTimestamp(durationMs);
        }

        private void restartSessionFromUi()
        {
            stopPlayback();
            fallbackElapsed = 0;
            startPlayback(true);
            updatePlaybackProgressUI(0, getPlaybackDuration());
        }

        private void seekToNormalized(double normalized, bool allowStateReset)
        {
            double duration = getPlaybackDuration();
            if (duration <= 0)
                return;

            double clamped = Math.Clamp(normalized, 0, 1);
            double targetMs = clamped * duration;
            double previousTime = track?.CurrentTime ?? fallbackElapsed;

            if (track != null)
                track.Seek(targetMs);

            fallbackElapsed = targetMs;

            if (allowStateReset)
            {
                if (targetMs + 5 < previousTime)
                    reloadBeatmapState(targetMs);
                else
                    playfield?.JumpToTime(targetMs);
            }
            else
            {
                playfield?.JumpToTime(targetMs);
            }

            pendingMetronomePulse = true;
        }

        private void reloadBeatmapState(double targetMs)
        {
            if (beatmap == null || playfield == null)
                return;

            playfield.LoadBeatmap(beatmap);
            playfield.SetKickLineMode(KickLineEnabled);
            playfield.JumpToTime(targetMs);
        }

        private double getPlaybackDuration()
        {
            if (track != null && track.Length > 0)
                return track.Length;

            if (cachedTrackDurationMs > 0)
                return cachedTrackDurationMs;

            cachedTrackDurationMs = estimateBeatmapDurationMs();
            return cachedTrackDurationMs;
        }

        private double estimateBeatmapDurationMs()
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
                return 0;

            double lastHit = beatmap.HitObjects.Max(h => h.Time);
            return lastHit + 4000;
        }

        private static string formatTimestamp(double ms)
        {
            if (ms < 0)
                ms = 0;

            TimeSpan t = TimeSpan.FromMilliseconds(ms);
            return $"{(int)t.TotalMinutes}:{t.Seconds:D2}.{t.Milliseconds:D3}";
        }

        private Drawable createMainContent()
        {
            var playfieldArea = new ResponsivePlayfieldContainer(createPlayfieldArea());

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    playfieldArea,
                    createBottomToolbar()
                }
            };
        }

        private Drawable createStageContent()
        {
            viewModeToggleButton = createSidebarButton("Stage View: 2D", toggleLaneViewMode);
            updateViewModeToggle(laneViewModeSetting?.Value ?? LaneViewMode.TwoDimensional);

            kickLayoutToggleButton = createSidebarButton("Kick Lane: Global Line", toggleKickLayout);
            updateKickLayoutToggle(kickLaneModeSetting?.Value ?? KickLaneMode.GlobalLine);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6, 6),
                Children = new Drawable[]
                {
                    viewModeToggleButton,
                    kickLayoutToggleButton
                }
            };
        }

        private Drawable createVisualControls()
        {
            var zoomText = new SpriteText
            {
                Font = BeatSightFont.Section(16f),
                Colour = new Color4(220, 225, 240, 255),
                Text = "1.0x"
            };

            zoomLevel.BindValueChanged(v => zoomText.Text = $"{v.NewValue:0.00}x", true);

            var zoomSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 16,
                Current = zoomLevel,
                KeyboardStepMultiplier = 1, // 0.01 * 1 = 0.01
                DragStepMultiplier = 5 // 0.01 * 5 = 0.05
            };

            zoomSlider.UserChange += () => autoZoom.Value = false;

            var noteWidthText = new SpriteText
            {
                Font = BeatSightFont.Section(16f),
                Colour = new Color4(220, 225, 240, 255),
                Text = "1.0x"
            };

            noteWidthScale.BindValueChanged(v => noteWidthText.Text = $"{v.NewValue:0.00}x", true);

            var noteWidthSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 16,
                Current = noteWidthScale,
                KeyboardStepMultiplier = 1, // 0.01 * 1 = 0.01
                DragStepMultiplier = 5 // 0.01 * 5 = 0.05
            }; var autoZoomCheckbox = new BeatSightCheckbox
            {
                LabelText = "Auto Zoom (BPM Scaled)",
                Current = autoZoom
            };

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    createSliderBlock("Zoom Level", zoomText, zoomSlider, showLabel: true),
                    autoZoomCheckbox,
                    createSliderBlock("Note Width", noteWidthText, noteWidthSlider, showLabel: true)
                }
            };
        }

        private Drawable createSpeedControl()
        {
            speedValueText = new SpriteText
            {
                Font = BeatSightFont.Section(16f),
                Colour = new Color4(220, 225, 240, 255),
                Text = formatSpeedLabel(speedAdjustment.Value)
            };

            var slider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 16,
                Current = speedAdjustment
            };

            return createSliderBlock("Playback speed", speedValueText, slider, showLabel: true);
        }

        private void updateSpeedSliderBounds()
        {
            if (speedMinSetting == null || speedMaxSetting == null)
                return;

            double min = Math.Clamp(speedMinSetting.Value, 0.0, 5.0);
            double max = Math.Clamp(speedMaxSetting.Value, min + 0.05, 5.0);

            speedAdjustment.MinValue = min;
            speedAdjustment.MaxValue = max;

            if (speedAdjustment.Value < min || speedAdjustment.Value > max)
                speedAdjustment.Value = Math.Clamp(speedAdjustment.Value, min, max);
        }

        private Drawable createOffsetControl()
        {
            offsetValueText = new SpriteText
            {
                Font = BeatSightFont.Section(16f),
                Colour = new Color4(220, 225, 240, 255),
                Text = formatOffsetLabel(offsetAdjustment.Value)
            };

            var slider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 16,
                Current = offsetAdjustment
            };

            return createSliderBlock("Global offset", offsetValueText, slider, showLabel: true);
        }

        private void syncOffsetWithConfig()
        {
            if (audioOffsetSetting == null)
                return;

            if (offsetSyncInProgress)
                return;

            offsetSyncInProgress = true;

            double min = offsetAdjustment.MinValue;
            double max = offsetAdjustment.MaxValue;
            double target = Math.Clamp(audioOffsetSetting.Value, min, max);

            if (!audioOffsetSetting.Value.Equals(target))
            {
                audioOffsetSetting.Value = target;
                if (hitsoundOffsetSetting != null)
                    hitsoundOffsetSetting.Value = target;
            }

            offsetAdjustment.Value = target;
            offsetMilliseconds = target;
            if (offsetValueText != null)
                offsetValueText.Text = formatOffsetLabel(target);

            offsetSyncInProgress = false;
        }

        private Drawable createSliderBlock(string label, SpriteText valueText, Drawable slider, bool showLabel = true)
        {
            // Set anchor and origin for the value text
            valueText.Anchor = Anchor.CentreRight;
            valueText.Origin = Anchor.CentreRight;

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 6),
                Children = new Drawable[]
                {
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Children = (showLabel
                            ? new Drawable[]
                            {
                                new SpriteText
                                {
                                    Text = label,
                                    Font = BeatSightFont.Body(16f),
                                    Colour = new Color4(190, 196, 220, 255),
                                    Anchor = Anchor.CentreLeft,
                                    Origin = Anchor.CentreLeft
                                },
                                valueText
                            }
                            : new Drawable[]
                            {
                                valueText
                            })
                    },
                    slider
                }
            };
        }

        private Drawable createTimingAudioContent()
        {
            mixToggleButton = createSidebarButton("Audio: Full Mix", toggleDrumMix);
            metronomeToggleButton = createSidebarButton("Metronome: Off", toggleMetronome);

            updateMixToggle();
            updateMetronomeToggle(metronomeEnabledSetting?.Value ?? false);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    createSpeedControl(),
                    createOffsetControl(),
                    mixToggleButton,
                    metronomeToggleButton
                }
            };
        }

        private BasicButton createSidebarButton(string label, Action action)
        {
            return new BasicButton
            {
                RelativeSizeAxes = Axes.X,
                Height = 36,
                Text = label,
                CornerRadius = 8,
                Masking = true,
                Action = action,
                BackgroundColour = sidebarButtonInactive
            };
        }

        private void toggleLaneViewMode()
        {
            if (laneViewModeSetting == null)
                return;

            var next = laneViewModeSetting.Value switch
            {
                LaneViewMode.TwoDimensional => LaneViewMode.ThreeDimensional,
                LaneViewMode.ThreeDimensional => LaneViewMode.Manuscript,
                LaneViewMode.Manuscript => LaneViewMode.TwoDimensional,
                _ => LaneViewMode.TwoDimensional
            };

            laneViewModeSetting.Value = next;
        }

        private void toggleKickLayout()
        {
            if (kickLaneModeSetting == null)
                return;

            kickLaneModeSetting.Value = kickLaneModeSetting.Value == KickLaneMode.GlobalLine
                ? KickLaneMode.DedicatedLane
                : KickLaneMode.GlobalLine;
        }

        private void updateViewModeToggle(LaneViewMode mode)
        {
            if (viewModeToggleButton == null)
                return;

            string text = mode switch
            {
                LaneViewMode.ThreeDimensional => "Stage View: 3D",
                LaneViewMode.Manuscript => "Stage View: Manuscript",
                _ => "Stage View: 2D"
            };

            viewModeToggleButton.Text = text;
            setButtonState(viewModeToggleButton, mode != LaneViewMode.TwoDimensional);
        }

        private void updateKickLayoutToggle(KickLaneMode mode)
        {
            bool useGlobalLine = mode == KickLaneMode.GlobalLine;

            if (kickLayoutToggleButton != null)
            {
                kickLayoutToggleButton.Text = useGlobalLine ? "Kick Lane: Global Line" : "Kick Lane: Dedicated Lane";
                setButtonState(kickLayoutToggleButton, useGlobalLine);
            }

            playfield?.SetKickLineMode(useGlobalLine);
            applyHeaderStatus();
        }

        private void setStatusMessage(string message)
        {
            currentStatusMessage = message;
            applyHeaderStatus();
        }

        private void appendStatusMessage(string message)
        {
            if (string.IsNullOrWhiteSpace(message))
                return;

            if (string.IsNullOrEmpty(currentStatusMessage))
                currentStatusMessage = message;
            else
                currentStatusMessage = $"{currentStatusMessage}\n{message}";

            applyHeaderStatus();
        }

        private void applyHeaderStatus()
        {
            if (statusText == null)
                return;

            string baseLine = string.IsNullOrWhiteSpace(currentStatusMessage)
                ? ""
                : currentStatusMessage.TrimEnd();

            string kickSuffix = KickLineEnabled
                ? "Kick lane: shared global line"
                : "Kick lane: dedicated lane";

            statusText.Text = string.IsNullOrEmpty(baseLine)
                ? kickSuffix
                : $"{baseLine} • {kickSuffix}";
        }

        private void togglePlayback()
        {
            if (isPlaybackActive())
            {
                stopPlayback();
            }
            else
            {
                if (playbackSpeed <= 0.001)
                    speedAdjustment.Value = 0.05;

                bool restart = isAtPlaybackEnd();
                startPlayback(restart);
            }

            updatePlaybackProgressUI();
        }

        private bool isPlaybackActive()
        {
            if (track != null)
                return isTrackRunning || track.IsRunning || fallbackRunning;

            return fallbackRunning;
        }

        private bool isAtPlaybackEnd()
        {
            double duration = getPlaybackDuration();
            if (duration <= 0)
                return false;

            double current = track?.CurrentTime ?? fallbackElapsed;
            return current >= duration - 1;
        }

        private void updatePlayPauseButton()
        {
            if (playPauseButton == null)
                return;

            bool active = isPlaybackActive();
            playPauseButton.Text = active ? "Pause" : "Play";
            setButtonState(playPauseButton, active);
        }

        private void toggleMetronome()
        {
            if (metronomeEnabledSetting == null)
                return;

            metronomeEnabledSetting.Value = !metronomeEnabledSetting.Value;
        }

        private void updateMetronomeToggle(bool enabled)
        {
            if (metronomeToggleButton == null)
                return;

            metronomeToggleButton.Text = enabled ? "Metronome: On" : "Metronome: Off";
            setButtonState(metronomeToggleButton, enabled);
        }

        private void setButtonState(BasicButton? button, bool active)
        {
            if (button == null)
                return;

            button.BackgroundColour = active ? sidebarButtonActive : sidebarButtonInactive;
        }

        private void onPlayfieldResult(HitResult result, double offset, Color4 accentColour)
        {
            if (hitLightingEnabled?.Value == true && (result == HitResult.Perfect || result == HitResult.Great))
            {
                hitLightingOverlay.Colour = new Color4(accentColour.R, accentColour.G, accentColour.B, 255);
                hitLightingOverlay.FadeTo(0.4f, 60, Easing.OutQuint)
                    .Then()
                    .FadeOut(260, Easing.OutQuad);
            }

        }

        private void loadBeatmap()
        {
            if (!tryResolveBeatmapPath(out string? path))
            {
                setStatusMessage("No beatmaps found. Return to add a map.");
                return;
            }

            try
            {
                beatmap = BeatmapLoader.LoadFromFile(path!);
                beatmapPath = path;

                // Determine layout based on settings and beatmap
                if (lanePresetSetting.Value == LanePreset.AutoDynamic && beatmap.DrumKit.Components.Count > 0)
                {
                    currentLaneLayout = LaneLayoutFactory.CreateFromComponents(beatmap.DrumKit.Components);
                }
                else if (lanePresetSetting.Value == LanePreset.AutoDynamic)
                {
                    currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
                }
                else
                {
                    currentLaneLayout = LaneLayoutFactory.Create(lanePresetSetting.Value);
                }

                DrumLaneHeuristics.ApplyToBeatmap(beatmap, currentLaneLayout);
                playfield?.SetLaneLayout(currentLaneLayout);
                playfield?.LoadBeatmap(beatmap);
                playfield?.SetKickLineMode(KickLineEnabled);

                // Load per-map settings
                var settings = mapSettings.Get(beatmap.Metadata.BeatmapId);
                autoZoom.Value = settings.AutoZoom;

                setStatusMessage($"Loaded: {beatmap.Metadata.Artist} — {beatmap.Metadata.Title}");
                loadTrack();
                fallbackElapsed = 0;
                fallbackRunning = false;
            }
            catch (Exception ex)
            {
                setStatusMessage($"Failed to load beatmap: {ex.Message}");
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
                appendStatusMessage("Beatmap has no audio file declared.");
                createVirtualTrack();
                return;
            }

            string resolvedAudioPath = Path.IsPathRooted(beatmap.Audio.Filename)
                ? beatmap.Audio.Filename
                : Path.Combine(Path.GetDirectoryName(beatmapPath) ?? string.Empty, beatmap.Audio.Filename);

            if (!File.Exists(resolvedAudioPath))
            {
                appendStatusMessage($"Audio file missing: {resolvedAudioPath}");
                createVirtualTrack();
                return;
            }

            try
            {
                prepareAudioCaches(resolvedAudioPath);

                if (cachedFullMixPath == null)
                {
                    appendStatusMessage("Audio load failed (unable to cache track). Using silent timing.");
                    createVirtualTrack();
                    return;
                }

                refreshTrackFromCache();
                fallbackRunning = false;
            }
            catch (Exception ex)
            {
                appendStatusMessage($"Audio load failed ({ex.Message}). Using silent timing.");
                createVirtualTrack();
            }

            updateMixToggle();
        }

        private void createVirtualTrack()
        {
            track = null;
            isTrackRunning = false;
            fallbackRunning = false;
            cachedTrackDurationMs = estimateBeatmapDurationMs();
            updatePlaybackProgressUI();
            updatePlayPauseButton();
        }

        private void startPlayback(bool restart)
        {
            if (track == null && !string.IsNullOrEmpty(cachedFullMixPath))
                refreshTrackFromCache();

            resetMetronomeTracking();

            playfield?.StartSession(restart);

            if (track != null)
            {
                if (restart)
                {
                    track.Seek(0);
                    fallbackElapsed = 0;
                }
                else
                {
                    // Ensure sync when resuming
                    track.Seek(fallbackElapsed);
                }

                try
                {
                    if (playbackSpeed < 0.05)
                    {
                        track.Tempo.Value = 0.05;
                        track.Frequency.Value = playbackSpeed / 0.05;
                    }
                    else
                    {
                        track.Frequency.Value = 1.0;
                        track.Tempo.Value = playbackSpeed;
                    }
                }
                catch
                {
                    track.Tempo.Value = Math.Max(0.05, playbackSpeed);
                }

                track.Start();
                isTrackRunning = true;
                fallbackRunning = false;
            }
            else
            {
                if (restart)
                    fallbackElapsed = 0;

                fallbackRunning = true;
                isTrackRunning = false;
            }

            updatePlayPauseButton();
        }

        private void stopPlayback()
        {
            if (track != null)
            {
                track.Stop();
                isTrackRunning = false;
                fallbackElapsed = track.CurrentTime;
            }
            fallbackRunning = false;
            pendingMetronomePulse = false;
            updatePlayPauseButton();
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
                updatePlaybackProgressUI();
                applyHeaderStatus();
            });
        }

        private static string formatOffsetLabel(double value) => $"{value:+0;-0;0} ms";
        private static string formatSpeedLabel(double value) => $"{value:0.00}x";

        protected double getCurrentTime() => (track?.CurrentTime ?? fallbackElapsed) + offsetMilliseconds;

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Bind background dim setting
            var backgroundDimBindable = config.GetBindable<double>(BeatSightSetting.BackgroundDim);
            backgroundDimBindable.BindValueChanged(e => backgroundDim.Alpha = (float)e.NewValue, true);

            // Bind volume settings
            masterVolumeSetting.BindValueChanged(_ => updateMasterVolumeOutput(), true);
            masterVolumeEnabledSetting.BindValueChanged(_ => updateMasterVolumeOutput(), true);
            musicVolumeSetting.BindValueChanged(_ => updateMusicVolumeOutput(), true);
            musicVolumeEnabledSetting.BindValueChanged(_ => updateMusicVolumeOutput(), true);

            playfield?.SetLaneLayout(currentLaneLayout);
            if (beatmap != null)
                playfield?.LoadBeatmap(beatmap);
        }

        private void updateMasterVolumeOutput()
        {
            double value = masterVolumeSetting?.Value ?? 0;
            bool enabled = masterVolumeEnabledSetting?.Value ?? true;
            audioManager.Volume.Value = enabled ? value : 0;
        }

        private void updateMusicVolumeOutput()
        {
            if (track == null)
                return;

            double value = musicVolumeSetting?.Value ?? 0;
            bool enabled = musicVolumeEnabledSetting?.Value ?? true;
            track.Volume.Value = enabled ? value : 0;
        }

        private double getEffectiveEffectVolume()
        {
            double value = effectVolumeSetting?.Value ?? 0;
            bool enabled = effectVolumeEnabledSetting?.Value ?? true;
            return enabled ? value : 0;
        }

        private double getEffectiveHitsoundVolume()
        {
            double value = hitsoundVolumeSetting?.Value ?? 0;
            bool enabled = hitsoundVolumeEnabledSetting?.Value ?? true;
            return enabled ? value : 0;
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
                fallbackElapsed += Time.Elapsed * playbackSpeed;

            handleMetronome();

            if (!isScrubbingPlayback)
                updatePlaybackProgressUI();
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);
            stopMetronomeChannels();
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
                restartSessionFromUi();
                return true;
            }

            if (e.Key == osuTK.Input.Key.Space && !e.Repeat)
            {
                togglePlayback();
                return true;
            }

            if (!e.Repeat && playfield != null && laneKeyBindings.TryGetValue(e.Key, out int lane))
            {
                if (lane < currentLaneLayout.LaneCount)
                {
                    var result = playfield.HandleInput(lane, getCurrentTime());
                    if (result != HitResult.None)
                        return true;
                }
            }

            return base.OnKeyDown(e);
        }

        private void onLanePresetChanged(ValueChangedEvent<LanePreset> preset)
        {
            if (preset.NewValue == LanePreset.AutoDynamic && beatmap != null && beatmap.DrumKit.Components.Count > 0)
            {
                currentLaneLayout = LaneLayoutFactory.CreateFromComponents(beatmap.DrumKit.Components);
            }
            else if (preset.NewValue == LanePreset.AutoDynamic)
            {
                currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
            }
            else
            {
                currentLaneLayout = LaneLayoutFactory.Create(preset.NewValue);
            }

            playfield?.SetLaneLayout(currentLaneLayout);
            rebuildLaneKeyBindings();

            if (beatmap != null)
            {
                DrumLaneHeuristics.ApplyToBeatmap(beatmap, currentLaneLayout);

                if (IsLoaded)
                    playfield?.LoadBeatmap(beatmap);
            }
        }

        private void rebuildLaneKeyBindings()
        {
            laneKeyBindings.Clear();

            int lanes = currentLaneLayout.LaneCount;
            if (lanes <= 0)
                return;

            if (!defaultLaneKeyLayouts.TryGetValue(lanes, out var layoutKeys))
                layoutKeys = fallbackLaneKeyOrder;

            int keysToAssign = Math.Min(lanes, layoutKeys.Length);

            for (int lane = 0; lane < keysToAssign; lane++)
            {
                var key = layoutKeys[lane];
                laneKeyBindings[key] = lane;
            }

            if (keysToAssign < lanes)
            {
                osu.Framework.Logging.Logger.Log(
                    $"[PlaybackScreen] Lane preset requires {lanes} lanes but only {keysToAssign} default key bindings are available.",
                    osu.Framework.Logging.LoggingTarget.Runtime,
                    osu.Framework.Logging.LogLevel.Important);
            }
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

            string cacheFolder = "PlaybackAudio";
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
                    osu.Framework.Logging.Logger.Log($"[Playback] Failed to cache drum stem '{drumStemSource}': {ex.Message}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
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
                osu.Framework.Logging.Logger.Log($"[Playback] Unable to resolve cached track '{targetRelativePath}'", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
                track = null;
                return;
            }

            track = loadedTrack;
            track.Completed += onTrackCompleted;
            updateMusicVolumeOutput();
            try
            {
                if (playbackSpeed < 0.05)
                {
                    track.Tempo.Value = 0.05;
                    track.Frequency.Value = playbackSpeed / 0.05;
                }
                else
                {
                    track.Frequency.Value = 1.0;
                    track.Tempo.Value = playbackSpeed;
                }
            }
            catch
            {
                track.Tempo.Value = Math.Max(0.05, playbackSpeed);
            }
            fallbackRunning = false;
            isTrackRunning = false;
            cachedTrackDurationMs = track.Length;
            updatePlaybackProgressUI();
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

            osu.Framework.Logging.Logger.Log($"[Playback] Switching audio mode: drumsOnly={targetDrumsOnly}, drumStemAvailable={drumStemAvailable}",
                osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);

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
                osu.Framework.Logging.Logger.Log($"[Playback] Audio mode switched successfully, track loaded: {(drumsOnlyMode ? "Drums Only" : "Full Mix")}",
                    osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
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
                mixToggleButton.Text = "Audio: Full Mix (Drum stem unavailable)";
                mixToggleButton.BackgroundColour = new Color4(80, 90, 120, 255);
                return;
            }

            mixToggleButton.Enabled.Value = true;
            if (drumsOnlyMode)
            {
                mixToggleButton.Text = "Audio: Drums Only";
                mixToggleButton.BackgroundColour = sidebarButtonActive; // Blue when active
            }
            else
            {
                mixToggleButton.Text = "Audio: Full Mix";
                mixToggleButton.BackgroundColour = sidebarButtonInactive; // Grey when inactive
            }
        }

        private void resetMetronomeTracking()
        {
            lastMetronomeBeatIndex = -1;
            pendingMetronomePulse = true;
            suppressMetronomeUntilBeatChange = false;
        }

        private void handleMetronome()
        {
            if (!metronomeEnabledSetting.Value || beatmap == null)
                return;

            if (!(isTrackRunning || fallbackRunning))
                return;

            var timing = beatmap.Timing;
            if (timing == null)
                return;

            double currentTime = getCurrentTime();

            // Find the active timing point for current time
            TimingPoint? activeTimingPoint = null;
            if (timing.TimingPoints != null && timing.TimingPoints.Count > 0)
            {
                // Find the most recent timing point at or before currentTime
                for (int i = timing.TimingPoints.Count - 1; i >= 0; i--)
                {
                    if (timing.TimingPoints[i].Time <= currentTime)
                    {
                        activeTimingPoint = timing.TimingPoints[i];
                        break;
                    }
                }
            }

            // Use the active timing point if found, otherwise use base timing
            double bpm = activeTimingPoint?.Bpm ?? timing.Bpm;
            double offset = activeTimingPoint?.Time ?? timing.Offset;
            string timeSignature = activeTimingPoint?.TimeSignature ?? timing.TimeSignature;

            if (bpm <= 0)
                return;

            double beatDuration = 60000.0 / bpm;
            double songTime = currentTime - offset;

            if (songTime < 0)
                return;

            int beatIndex = (int)Math.Floor(songTime / beatDuration);

            if (suppressMetronomeUntilBeatChange)
            {
                suppressMetronomeUntilBeatChange = false;
                pendingMetronomePulse = false;
                lastMetronomeBeatIndex = beatIndex;
                return;
            }

            if (!pendingMetronomePulse && beatIndex == lastMetronomeBeatIndex)
                return;

            pendingMetronomePulse = false;
            lastMetronomeBeatIndex = beatIndex;

            // Parse time signature to determine if this is an accent beat
            bool isAccentBeat = false;
            if (!string.IsNullOrEmpty(timeSignature) && timeSignature.Contains('/'))
            {
                string[] parts = timeSignature.Split('/');
                if (parts.Length == 2 && int.TryParse(parts[0], out int beatsPerMeasure))
                {
                    // First beat of each measure is accented
                    isAccentBeat = (beatIndex % beatsPerMeasure) == 0;
                }
            }

            playMetronomeSample(isAccentBeat);
            MetronomeTick?.Invoke(currentTime);

            // Debug logging (will be noisy but helps debug)
            if (beatIndex % 4 == 0) // Log every 4th beat to reduce spam
            {
                osu.Framework.Logging.Logger.Log($"[Playback] Metronome tick: beat {beatIndex}, accent={isAccentBeat}, bpm={bpm:F1}",
                    osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
            }
        }

        private void playMetronomeSample(bool isAccent = false)
        {
            ensureMetronomeSamplesLoaded();

            SampleChannel? channel = null;

            try
            {
                var sample = isAccent ? metronomeAccentSample : metronomeRegularSample;
                if (sample != null)
                {
                    channel = sample.GetChannel();
                    if (channel != null)
                    {
                        channel.Volume.Value = getMetronomeGain(isAccent);
                        channel.Balance.Value = 0;
                        channel.Play();
                    }
                }
            }
            catch (Exception ex)
            {
                osu.Framework.Logging.Logger.Log($"[Playback] Failed to play metronome sample: {ex.Message}",
                    osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
            }

            if (channel != null)
            {
                if (isAccent)
                {
                    activeMetronomeAccentChannel?.Stop();
                    activeMetronomeAccentChannel = channel;
                }
                else
                {
                    activeMetronomeChannel?.Stop();
                    activeMetronomeChannel = channel;
                }

                return;
            }

            playFallbackMetronomeSample(isAccent);
        }

        private void ensureMetronomeSamplesLoaded()
        {
            if (metronomeSoundSetting == null)
                return;

            if (metronomeAccentSample == null || metronomeRegularSample == null)
                loadMetronomeSamples(metronomeSoundSetting.Value);
        }

        private void loadMetronomeSamples(MetronomeSoundOption option)
        {
            if (audioManager == null)
                return;

            stopMetronomeChannels();

            ensureAudioStores();

            var (accentPath, regularPath) = MetronomeSampleLibrary.GetSamplePaths(option);

            metronomeAccentSample = tryGetSample(accentPath);
            metronomeRegularSample = tryGetSample(regularPath);

            if ((metronomeAccentSample == null || metronomeRegularSample == null) && option != MetronomeSoundOption.PercMetronomeQuartz)
            {
                loadMetronomeSamples(MetronomeSoundOption.PercMetronomeQuartz);
            }
        }

        private Sample? tryGetSample(string path)
        {
            try
            {
                ensureAudioStores();

                Sample? sample = null;

                if (storageSampleStore != null)
                {
                    string fileName = Path.GetFileName(path);
                    if (!string.IsNullOrEmpty(fileName))
                    {
                        sample = storageSampleStore.Get($"{userMetronomeDirectory}/{fileName}");

                        if (sample == null)
                        {
                            string stem = Path.GetFileNameWithoutExtension(fileName);
                            if (!string.IsNullOrEmpty(stem))
                                sample = storageSampleStore.Get($"{userMetronomeDirectory}/{stem}");
                        }
                    }
                }

                if (sample == null && embeddedSampleStore != null)
                {
                    sample = embeddedSampleStore.Get(path);

                    if (sample == null && Path.HasExtension(path))
                    {
                        string? trimmedEmbedded = Path.ChangeExtension(path, null);
                        if (!string.IsNullOrEmpty(trimmedEmbedded))
                            sample = embeddedSampleStore.Get(trimmedEmbedded);
                    }
                }

                sample ??= audioManager.Samples.Get(path);

                if (sample == null && Path.HasExtension(path))
                {
                    string? trimmed = Path.ChangeExtension(path, null);
                    if (!string.IsNullOrEmpty(trimmed))
                        sample = audioManager.Samples.Get(trimmed);
                }

                if (sample == null)
                    osu.Framework.Logging.Logger.Log($"[Playback] Missing metronome sample: {path}",
                        osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);

                return sample;
            }
            catch (Exception ex)
            {
                osu.Framework.Logging.Logger.Log($"[Playback] Error loading metronome sample '{path}': {ex.Message}",
                    osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
                return null;
            }
        }

        private void stopMetronomeChannels()
        {
            activeMetronomeChannel?.Stop();
            activeMetronomeChannel = null;
            activeMetronomeAccentChannel?.Stop();
            activeMetronomeAccentChannel = null;
        }

        private float getMetronomeGain(bool isAccent)
        {
            double effects = getEffectiveEffectVolume();
            double metronomeLevel = metronomeVolume.Value;

            if (metronomeLevel <= 0.001 || effects <= 0.001)
                return 0f;

            double baseVolume = metronomeLevel * effects;
            double accentBoost = isAccent ? 1.65 : 1.25;
            double mixAttenuation = drumsOnlyMode ? 1.05 : 0.82;

            double emphasised = baseVolume * accentBoost * mixAttenuation;

            if (metronomeLevel >= 0.05)
            {
                double bias = (isAccent ? 0.18 : 0.12) * Math.Clamp(metronomeLevel, 0, 1);
                emphasised += bias;
            }

            return (float)Math.Clamp(emphasised, 0, 1.5);
        }

        protected void TriggerMetronomePreview(bool accent = true, bool triggerVisualPulse = true)
        {
            playMetronomeSample(accent);

            if (triggerVisualPulse)
                MetronomeTick?.Invoke(getCurrentTime());
        }

        private void playFallbackMetronomeSample(bool isAccent)
        {
            foreach (var path in MetronomeSampleLibrary.GetFallbackCandidates(isAccent))
            {
                try
                {
                    var sample = tryGetSample(path);
                    var channel = sample?.GetChannel();
                    if (channel == null)
                        continue;

                    channel.Volume.Value = getMetronomeGain(isAccent) * 0.85f;
                    channel.Balance.Value = 0;
                    channel.Play();
                    return;
                }
                catch
                {
                    // ignore and try the next fallback
                }
            }

            osu.Framework.Logging.Logger.Log("[Playback] No metronome samples available after fallbacks",
                osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
        }

        private void ensureAudioStores()
        {
            if (embeddedResourceStore == null)
            {
                embeddedResourceStore = new NamespacedResourceStore<byte[]>(
                    new DllResourceStore(typeof(global::BeatSight.Game.BeatSightGame).Assembly),
                    "BeatSight.Game.Resources");
            }

            MetronomeSampleBootstrap.EnsureDefaults(host.Storage, embeddedResourceStore, userMetronomeDirectory);
            NoteSkinBootstrap.EnsureDefaults(host.Storage, embeddedResourceStore, userSkinDirectory);

            storageResourceStore ??= new StorageBackedResourceStore(host.Storage);
            storageTrackStore ??= audioManager.GetTrackStore(storageResourceStore);
            storageSampleStore ??= audioManager.GetSampleStore(storageResourceStore);
            embeddedSampleStore ??= audioManager.GetSampleStore(embeddedResourceStore);

            ensureUserAssetDirectory(userSkinDirectory);
            ensureUserAssetDirectory(userMetronomeDirectory);
        }

        private void ensureUserAssetDirectory(string relativePath)
        {
            try
            {
                string fullPath = host.Storage.GetFullPath(relativePath);
                if (!Directory.Exists(fullPath))
                    Directory.CreateDirectory(fullPath);
            }
            catch
            {
                // Ignore failures – the directories are optional conveniences for user customisation.
            }
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

        private partial class ScrubbableSliderBar : BeatSightSliderBar
        {
            public event Action<bool>? ScrubbingChanged;

            private bool scrubbing;

            protected override bool OnMouseDown(MouseDownEvent e)
            {
                setScrubbing(true);
                var handled = base.OnMouseDown(e);
                if (!handled)
                    setScrubbing(false);
                return handled;
            }

            protected override void OnMouseUp(MouseUpEvent e)
            {
                base.OnMouseUp(e);
                setScrubbing(false);
            }

            protected override bool OnDragStart(DragStartEvent e)
            {
                var handled = base.OnDragStart(e);
                if (handled)
                    setScrubbing(true);
                return handled;
            }

            protected override void OnDragEnd(DragEndEvent e)
            {
                base.OnDragEnd(e);
                setScrubbing(false);
            }

            private void setScrubbing(bool value)
            {
                if (scrubbing == value)
                    return;

                scrubbing = value;
                ScrubbingChanged?.Invoke(value);
            }
        }

        private partial class HoverableToolbarContainer : Container
        {
            private MarginPadding cachedPadding;
            private const float PEEK_HEIGHT = 50f; // Increased to ensure accessibility
            private bool initialLayoutDone = false;

            public HoverableToolbarContainer()
            {
                RelativeSizeAxes = Axes.X;
                AutoSizeAxes = Axes.Y;
                Anchor = Anchor.BottomCentre;
                Origin = Anchor.BottomCentre;
                AlwaysPresent = true;
                Alpha = 0f; // Start invisible to prevent flash
            }

            protected override void Update()
            {
                base.Update();

                if (Parent == null || Parent.DrawWidth <= 0)
                    return;

                // Responsive horizontal padding (scales with width, but has limits)
                float horizontalPadding = Math.Clamp(Parent.DrawWidth * 0.03f, 20f, 50f);

                var targetPadding = new MarginPadding
                {
                    Left = horizontalPadding,
                    Right = horizontalPadding,
                    Bottom = 20
                };

                if (!cachedPadding.Equals(targetPadding))
                {
                    Padding = targetPadding;
                    cachedPadding = targetPadding;
                }

                // Initial layout snap
                if (!initialLayoutDone && DrawHeight > PEEK_HEIGHT)
                {
                    initialLayoutDone = true;
                    if (!IsHovered)
                    {
                        float hideOffset = Math.Max(0, DrawHeight - PEEK_HEIGHT);
                        this.Y = hideOffset;
                        this.FadeTo(0f, 500, Easing.OutQuint);
                    }
                }
            }

            protected override bool OnHover(HoverEvent e)
            {
                // Ensure we start from the hidden position if this is the first interaction
                if (!initialLayoutDone && DrawHeight > PEEK_HEIGHT)
                {
                    initialLayoutDone = true;
                    float hideOffset = Math.Max(0, DrawHeight - PEEK_HEIGHT);
                    this.Y = hideOffset;
                }

                this.MoveToY(0, 300, Easing.OutQuint);
                this.FadeTo(1f, 300, Easing.OutQuint);
                return true;
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                float hideOffset = Math.Max(0, DrawHeight - PEEK_HEIGHT);
                this.MoveToY(hideOffset, 500, Easing.OutQuint);
                this.FadeTo(0f, 500, Easing.OutQuint);
            }
        }

        private partial class ResponsivePlayfieldContainer : Container
        {
            private readonly Drawable playfieldContent;
            private MarginPadding cachedPadding;

            public ResponsivePlayfieldContainer(Drawable content)
            {
                RelativeSizeAxes = Axes.Both;
                playfieldContent = content;
                Child = playfieldContent;
            }

            protected override void Update()
            {
                base.Update();

                if (DrawWidth <= 0 || DrawHeight <= 0)
                    return;

                // Dynamically calculate padding based on window size
                float horizontalPadding = Math.Clamp(DrawWidth * 0.03f, 20f, 50f);
                float topPadding = Math.Clamp(DrawHeight * 0.005f, 2f, 8f); // Reduced to minimize whitespace

                // Reduced bottom padding to allow playfield to extend further down
                float bottomPadding = 40f;

                var targetPadding = new MarginPadding
                {
                    Left = horizontalPadding,
                    Right = horizontalPadding,
                    Top = topPadding,
                    Bottom = bottomPadding
                };

                // Only update if padding actually changed (avoid constant recalculation)
                if (!cachedPadding.Equals(targetPadding))
                {
                    Padding = targetPadding;
                    cachedPadding = targetPadding;
                }
            }
        }

        private partial class PlayfieldViewportContainer : Container
        {
            private readonly Container stagePadding;
            private MarginPadding cachedPadding;

            public PlayfieldViewportContainer(Drawable playfield)
            {
                RelativeSizeAxes = Axes.Both;

                var stageSurface = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 28,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Shadow,
                        Colour = new Color4(0, 0, 0, 40),
                        Radius = 32,
                        Roundness = 1f
                    },
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(10, 12, 20, 255)
                        },
                        playfield
                    }
                };

                stagePadding = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Child = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 40, Vertical = 20 },
                        Child = stageSurface
                    }
                };

                InternalChild = stagePadding;
            }

            protected override void Update()
            {
                base.Update();

                if (DrawWidth <= 0 || DrawHeight <= 0)
                    return;

                float horizontal = Math.Clamp(DrawWidth * 0.01f, 8f, 60f);
                float vertical = Math.Clamp(DrawHeight * 0.015f, 8f, 60f);
                var targetPadding = new MarginPadding
                {
                    Left = horizontal,
                    Right = horizontal,
                    Top = vertical,
                    Bottom = vertical + 20
                };

                if (!cachedPadding.Equals(targetPadding))
                {
                    stagePadding.Padding = targetPadding;
                    cachedPadding = targetPadding;
                }
            }
        }

    }
}
