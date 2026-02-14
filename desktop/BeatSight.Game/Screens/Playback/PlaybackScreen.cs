using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Customization;
using BeatSight.Game.Mapping;
using BeatSight.Game.Progress;
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
using BeatSight.Game.Screens;

namespace BeatSight.Game.Screens.Playback
{
    public partial class PlaybackScreen : BeatSightScreen
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
        protected Track? drumTrack; // New
        protected PlaybackPlayfield? playfield;
        private ConfidenceHeatmap? confidenceHeatmap;

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

        private readonly BindableDouble drumVolume = new BindableDouble(1.0) { MinValue = 0, MaxValue = 1, Precision = 0.01 }; // New
        private readonly BindableDouble backingVolume = new BindableDouble(1.0) { MinValue = 0, MaxValue = 1, Precision = 0.01 }; // New

        private SpriteText statusText = null!;
        private SpriteText offsetValueText = null!;
        private SpriteText speedValueText = null!;
        private bool pausedByZeroSpeed;
        private BasicButton playPauseButton = null!;
        private BasicButton viewModeToggleButton = null!;
        private BasicButton kickLayoutToggleButton = null!;
        private BasicButton metronomeToggleButton = null!;
        private BasicButton mixToggleButton = null!;
        private BasicButton loopLowConfidenceButton = null!; // New
        private bool loopLowConfidenceEnabled;
        private double? loopStart;
        private double? loopEnd;
        private PlaybackMixerOverlay mixerOverlay = null!; // New
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
            Precision = 0.01,
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
            MaxValue = 2.0,
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
        private string currentStatusMessage = "Loading beatmap...";

        private BackButton backButton = null!;
        private BufferedContainer backgroundBlurContainer = null!;
        private Box backgroundBase = null!;
        private Box backgroundDim = null!;
        private Box hitLightingOverlay = null!;
        private Container playfieldContainer = null!;
        private ScrubbableSliderBar timelineSlider = null!;
        private SpriteText timelineCurrentText = null!;
        private SpriteText timelineTotalText = null!;
        private SpriteText timelineSeparatorText = null!;
        private FillFlowContainer timelineTimeFlow = null!;
        private Container headerStatusContainer = null!;
        private PlaybackToolbarContainer playbackToolbar = null!;
        private FillFlowContainer toolbarButtonFlow = null!;
        private Container toolbarSliderContainer = null!;
        private FillFlowContainer playbackRowFlow = null!;
        private FillFlowContainer toolbarMainContentFlow = null!;
        private readonly List<Container> toolbarGroupContainers = new();
        private readonly List<FillFlowContainer> toolbarGroupFlows = new();
        private readonly List<BasicButton> toolbarButtons = new();
        private readonly List<BasicButton> sidebarControlButtons = new();
        private readonly List<SpriteText> toolbarSectionTitles = new();
        private readonly List<SpriteText> sliderLabelTexts = new();
        private readonly List<SpriteText> sliderValueTexts = new();
        private readonly List<FillFlowContainer> sliderBlocks = new();
        private readonly List<BeatSightSliderBar> detailSliders = new();
        private readonly List<BeatSightCheckbox> detailCheckboxes = new();
        private readonly BindableDouble playbackProgress = new BindableDouble { MinValue = 0, MaxValue = 1, Precision = 0.0001 };
        private bool suppressPlaybackProgressUpdate;
        private bool isScrubbingPlayback;
        private bool wasPlayingBeforeScrub;
        private double? pendingSeekNormalized;
        private double cachedTrackDurationMs;
        private float lastDensityWidth = -1f;
        private float lastDensityHeight = -1f;

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

        [Resolved]
        private UserProgressManager progressManager { get; set; } = null!;

        // Progress tracking state
        private string? currentBeatmapId;
        private double sessionStartTime;
        private double lastProgressUpdateTime;
        private bool sessionRecorded;

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
                    zoomLevel.Value = 1.12;

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
                BackgroundColour = new Color4(10, 10, 18, 255), // Clear framebuffer to solid color to prevent random flashing
                Child = backgroundBase = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(10, 10, 18, 255) // Fully opaque to prevent uninitialized framebuffer showing through
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

            mixerOverlay = new PlaybackMixerOverlay(backingVolume, drumVolume)
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                State = { Value = Visibility.Hidden }
            };

            InternalChildren = new Drawable[]
            {
                // Background is now global
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
                            new Dimension(GridSizeMode.AutoSize),
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
                hitLightingOverlay,
                mixerOverlay
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
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            statusText = new SpriteText
            {
                Font = BeatSightFont.Section(metrics.HeaderStatusFont),
                Colour = Color4.White,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
            };

            applyHeaderStatus();

            return headerStatusContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding
                {
                    Left = metrics.HeaderPaddingLeft,
                    Right = metrics.HeaderPaddingRight,
                    Top = metrics.HeaderPaddingTop,
                    Bottom = metrics.HeaderPaddingBottom
                },
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
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            toolbarButtons.Clear();
            sidebarControlButtons.Clear();
            toolbarSectionTitles.Clear();
            sliderLabelTexts.Clear();
            sliderValueTexts.Clear();
            sliderBlocks.Clear();
            detailSliders.Clear();
            detailCheckboxes.Clear();
            toolbarGroupContainers.Clear();
            toolbarGroupFlows.Clear();

            timelineSlider = new ScrubbableSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = metrics.TimelineSliderHeight,
                Current = playbackProgress
            };

            timelineSlider.ScrubbingChanged += onScrubbingStateChanged;
            playbackProgress.BindValueChanged(onPlaybackProgressChanged);

            timelineCurrentText = new SpriteText
            {
                Text = "0:00",
                Font = BeatSightFont.Section(metrics.TimelineTimeFont),
                Colour = new Color4(200, 205, 220, 255),
                Shadow = false
            };

            timelineTotalText = new SpriteText
            {
                Text = "--:--",
                Font = BeatSightFont.Section(metrics.TimelineTimeFont),
                Colour = new Color4(150, 160, 185, 255),
                Shadow = false
            };

            confidenceHeatmap = new ConfidenceHeatmap(1000) // Initial duration, will be updated
            {
                RelativeSizeAxes = Axes.X,
                Height = metrics.HeatmapHeight,
                Margin = new MarginPadding { Bottom = 5 }
            };

            var buttonFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(metrics.PlaybackRowSpacingX, 0),
                Children = new Drawable[]
                {
                    playPauseButton = createToolbarButton("Pause", togglePlayback),
                    createToolbarButton("Restart", restartSessionFromUi),
                    createToolbarButton("Mixer", () => mixerOverlay.ToggleVisibility())
                }
            };
            toolbarButtonFlow = buttonFlow;

            var sliderContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding
                {
                    Left = metrics.SliderContainerPaddingLeft,
                    Right = metrics.SliderContainerPaddingRight,
                    Top = metrics.SliderContainerPaddingTop,
                    Bottom = metrics.SliderContainerPaddingBottom
                },
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Children = new Drawable[]
                        {
                            confidenceHeatmap,
                            timelineSlider
                        }
                    },
                    timelineTimeFlow = new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.BottomRight,
                        Origin = Anchor.BottomRight,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(metrics.TimelineTimeSpacing, 0),
                        Margin = new MarginPadding { Top = metrics.TimelineTimeTopMargin },
                        Children = new Drawable[]
                        {
                            timelineCurrentText,
                            timelineSeparatorText = new SpriteText
                            {
                                Text = "/",
                                Font = BeatSightFont.Caption(metrics.TimelineSeparatorFont),
                                Colour = new Color4(150, 160, 185, 255),
                                Shadow = false
                            },
                            timelineTotalText
                        }
                    }
                }
            };
            toolbarSliderContainer = sliderContainer;

            var playbackRow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(metrics.PlaybackRowSpacingY, metrics.PlaybackRowSpacingY),
                Children = new Drawable[]
                {
                    buttonFlow,
                    sliderContainer
                }
            };
            playbackRowFlow = playbackRow;

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

            return playbackToolbar = new PlaybackToolbarContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                Padding = new MarginPadding { Bottom = metrics.ToolbarBottomPadding }, // Prevent clipping at screen edge
                Child = new Container
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Masking = true,
                    CornerRadius = metrics.ToolbarCornerRadius,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(14, 16, 26, 180)
                        },
                        toolbarMainContentFlow = new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                                Padding = new MarginPadding { Horizontal = metrics.ToolbarInnerPaddingH, Vertical = metrics.ToolbarInnerPaddingV },
                                Spacing = new Vector2(metrics.ToolbarSectionSpacing, metrics.ToolbarSectionSpacing),
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
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            var button = new BeatSightButton
            {
                Width = metrics.ToolbarButtonWidth,
                Height = metrics.ToolbarButtonHeight,
                CornerRadius = metrics.ToolbarButtonCorner,
                Masking = true,
                Text = label,
                FontSize = metrics.ToolbarButtonFont,
                Action = action,
                BackgroundColour = sidebarButtonInactive
            };

            toolbarButtons.Add(button);
            return button;
        }

        private Drawable createControlGroup(string title, Drawable content)
        {
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            var titleText = new SpriteText
            {
                Text = title,
                Font = BeatSightFont.Section(metrics.GroupTitleFont),
                Colour = Color4.White
            };
            toolbarSectionTitles.Add(titleText);

            var groupFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(metrics.GroupFlowSpacingX, metrics.GroupFlowSpacingY),
                Children = new Drawable[]
                {
                    titleText,
                    content
                }
            };

            var groupContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding { Right = metrics.GroupPaddingRight, Bottom = metrics.GroupPaddingBottom },
                Child = groupFlow
            };
            toolbarGroupFlows.Add(groupFlow);
            toolbarGroupContainers.Add(groupContainer);

            return groupContainer;
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

            if (track != null)
            {
                track.Seek(targetMs);
                if (drumTrack != null) drumTrack.Seek(targetMs);
            }

            fallbackElapsed = targetMs;

            // Always fully sync the playfield state when seeking.
            // Previously, forward seeks during scrubbing only called JumpToTime
            // while backward seeks did a full reload, causing inconsistent visuals.
            double playfieldTime = Math.Max(0, targetMs + offsetMilliseconds);
            playfield?.JumpToTime(playfieldTime);

            pendingMetronomePulse = true;
        }

        private void reloadBeatmapState(double targetMs)
        {
            if (beatmap == null || playfield == null)
                return;

            // Ensure lane assignments match the current layout before reloading notes.
            DrumLaneHeuristics.ApplyToBeatmap(beatmap, currentLaneLayout);
            playfield.SetLaneLayout(currentLaneLayout);
            playfield.LoadBeatmap(beatmap);
            playfield.SetKickLineMode(KickLineEnabled);
            playfield.JumpToTime(Math.Max(0, targetMs + offsetMilliseconds));
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
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            viewModeToggleButton = createSidebarButton("Stage View: 2D", toggleLaneViewMode);
            updateViewModeToggle(laneViewModeSetting?.Value ?? LaneViewMode.TwoDimensional);

            kickLayoutToggleButton = createSidebarButton("Kick Lane: Global Line", toggleKickLayout);
            updateKickLayoutToggle(kickLaneModeSetting?.Value ?? KickLaneMode.GlobalLine);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(metrics.SliderBlockSpacing, metrics.SliderBlockSpacing),
                Children = new Drawable[]
                {
                    viewModeToggleButton,
                    kickLayoutToggleButton
                }
            };
        }

        private Drawable createVisualControls()
        {
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            var zoomText = new SpriteText
            {
                Font = BeatSightFont.Section(metrics.SliderValueFont),
                Colour = new Color4(220, 225, 240, 255),
                Text = "1.0x"
            };

            zoomLevel.BindValueChanged(v => zoomText.Text = $"{v.NewValue:0.00}x", true);

            var zoomSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = metrics.DetailSliderHeight,
                Current = zoomLevel,
                KeyboardStepMultiplier = 1, // 0.01 * 1 = 0.01
                DragStepMultiplier = 5 // 0.01 * 5 = 0.05
            };

            zoomSlider.UserChange += () => autoZoom.Value = false;

            var noteWidthText = new SpriteText
            {
                Font = BeatSightFont.Section(metrics.SliderValueFont),
                Colour = new Color4(220, 225, 240, 255),
                Text = "1.0x"
            };

            noteWidthScale.BindValueChanged(v => noteWidthText.Text = $"{v.NewValue:0.00}x", true);

            var noteWidthSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = metrics.DetailSliderHeight,
                Current = noteWidthScale,
                KeyboardStepMultiplier = 1, // 0.01 * 1 = 0.01
                DragStepMultiplier = 5 // 0.01 * 5 = 0.05
            }; var autoZoomCheckbox = new BeatSightCheckbox
            {
                LabelText = "Auto Zoom (Density + BPM)",
                LabelFontSize = metrics.CheckboxLabelFont,
                Current = autoZoom
            };
            detailCheckboxes.Add(autoZoomCheckbox);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, metrics.SliderBlockSpacing + 2f),
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
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            speedValueText = new SpriteText
            {
                Font = BeatSightFont.Section(metrics.SliderValueFont),
                Colour = new Color4(220, 225, 240, 255),
                Text = formatSpeedLabel(speedAdjustment.Value)
            };

            var slider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = metrics.DetailSliderHeight,
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
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            offsetValueText = new SpriteText
            {
                Font = BeatSightFont.Section(metrics.SliderValueFont),
                Colour = new Color4(220, 225, 240, 255),
                Text = formatOffsetLabel(offsetAdjustment.Value)
            };

            var slider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = metrics.DetailSliderHeight,
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
            SpriteText? labelText = null;

            // Set anchor and origin for the value text
            valueText.Anchor = Anchor.CentreRight;
            valueText.Origin = Anchor.CentreRight;
            sliderValueTexts.Add(valueText);
            if (slider is BeatSightSliderBar sliderBar)
                detailSliders.Add(sliderBar);

            var block = new FillFlowContainer
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
                                labelText = new SpriteText
                                {
                                    Text = label,
                                    Font = BeatSightFont.Body(18f),
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

            if (labelText != null)
                sliderLabelTexts.Add(labelText);

            sliderBlocks.Add(block);
            return block;
        }

        private Drawable createTimingAudioContent()
        {
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            mixToggleButton = createSidebarButton("Audio: Full Mix", toggleDrumMix);
            metronomeToggleButton = createSidebarButton("Metronome: Off", toggleMetronome);
            loopLowConfidenceButton = createSidebarButton("Loop Low Confidence: Off", toggleLoopLowConfidence); // New

            updateMixToggle();
            updateMetronomeToggle(metronomeEnabledSetting?.Value ?? false);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, metrics.SliderBlockSpacing + 2f),
                Children = new Drawable[]
                {
                    createSpeedControl(),
                    createOffsetControl(),
                    mixToggleButton,
                    metronomeToggleButton,
                    loopLowConfidenceButton // New
                }
            };
        }

        private BasicButton createSidebarButton(string label, Action action)
        {
            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);
            var button = new BeatSightButton
            {
                RelativeSizeAxes = Axes.X,
                Height = metrics.SidebarButtonHeight,
                Text = label,
                FontSize = metrics.SidebarButtonFont,
                CornerRadius = metrics.SidebarButtonCorner,
                Masking = true,
                Action = action,
                BackgroundColour = sidebarButtonInactive
            };
            sidebarControlButtons.Add(button);
            return button;
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
                LaneViewMode.Manuscript => "Stage View: Sheet Music",
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

        private void onPlayfieldResult(HitResult result, double offset, Color4 accentColour, string component)
        {
            // Hit lighting overlay disabled - was causing seizure-inducing flashing

            if (result != HitResult.Miss && result != HitResult.None)
            {
                playHitsound(component);
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
                if (path == null) throw new InvalidOperationException("Path cannot be null.");
                var loadedMap = BeatmapLoader.LoadFromFile(path);
                if (loadedMap == null) throw new IOException($"Failed to load beatmap from {path}");
                beatmap = loadedMap;
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

                // Update heatmap duration
                confidenceHeatmap?.SetDuration(beatmap.Audio.Duration);

                // Load debug JSON if available
                string debugPath = Path.ChangeExtension(path, ".debug.json");
                if (File.Exists(debugPath))
                {
                    try
                    {
                        string json = File.ReadAllText(debugPath);
                        confidenceHeatmap?.LoadFromDebugJson(json);
                    }
                    catch (Exception ex)
                    {
                        osu.Framework.Logging.Logger.Log($"Failed to load debug JSON: {ex.Message}");
                    }
                }

                // Load per-map settings
                var settings = mapSettings.Get(beatmap.Metadata.BeatmapId);
                autoZoom.Value = settings.AutoZoom;

                setStatusMessage($"Loaded: {beatmap.Metadata.Artist} — {beatmap.Metadata.Title}");
                loadTrack();
                loadCustomSamples();
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
                    if (drumTrack != null) drumTrack.Seek(0);
                    fallbackElapsed = 0;
                }
                else
                {
                    // Ensure sync when resuming
                    track.Seek(fallbackElapsed);
                    if (drumTrack != null) drumTrack.Seek(fallbackElapsed);
                }

                try
                {
                    if (playbackSpeed < 0.05)
                    {
                        track.Tempo.Value = 0.05;
                        track.Frequency.Value = playbackSpeed / 0.05;
                        if (drumTrack != null)
                        {
                            drumTrack.Tempo.Value = 0.05;
                            drumTrack.Frequency.Value = playbackSpeed / 0.05;
                        }
                    }
                    else
                    {
                        track.Frequency.Value = 1.0;
                        track.Tempo.Value = playbackSpeed;
                        if (drumTrack != null)
                        {
                            drumTrack.Frequency.Value = 1.0;
                            drumTrack.Tempo.Value = playbackSpeed;
                        }
                    }
                }
                catch
                {
                    track.Tempo.Value = Math.Max(0.05, playbackSpeed);
                    if (drumTrack != null) drumTrack.Tempo.Value = Math.Max(0.05, playbackSpeed);
                }

                track.Start();
                if (drumTrack != null) drumTrack.Start();

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
                if (drumTrack != null) drumTrack.Stop();
                isTrackRunning = false;
                fallbackElapsed = track.CurrentTime;
            }
            fallbackRunning = false;
            pendingMetronomePulse = false;
            updatePlayPauseButton();
        }

        private void disposeTrack()
        {
            if (track != null)
            {
                track.Stop();
                track.Completed -= onTrackCompleted;
                track.Dispose();
                track = null;
            }
            if (drumTrack != null)
            {
                drumTrack.Stop();
                drumTrack.Dispose();
                drumTrack = null;
            }
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
            {
                DrumLaneHeuristics.ApplyToBeatmap(beatmap, currentLaneLayout);
                playfield?.LoadBeatmap(beatmap);
            }
            playfield?.SetKickLineMode(KickLineEnabled);
        }

        private void updateMasterVolumeOutput()
        {
            double value = masterVolumeSetting?.Value ?? 0;
            bool enabled = masterVolumeEnabledSetting?.Value ?? true;
            audioManager.Volume.Value = enabled ? value : 0;
        }

        private void updateMusicVolumeOutput()
        {
            double value = musicVolumeSetting?.Value ?? 0;
            bool enabled = musicVolumeEnabledSetting?.Value ?? true;
            double baseVol = enabled ? value : 0;

            if (track != null)
                track.Volume.Value = baseVol * backingVolume.Value;

            if (drumTrack != null)
                drumTrack.Volume.Value = baseVol * drumVolume.Value;
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
            startProgressTracking();
        }
        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            startPlayback(restart: false);
            startProgressTracking();
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            stopPlayback();
            saveProgressOnExit();
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            stopPlayback();
            saveProgressOnExit();
            return base.OnExiting(e);
        }

        private void startProgressTracking()
        {
            if (beatmap == null || string.IsNullOrEmpty(beatmapPath)) return;

            currentBeatmapId = UserProgressManager.GenerateBeatmapId(
                beatmapPath,
                beatmap.Metadata?.Title,
                beatmap.Metadata?.Artist);

            sessionStartTime = Time.Current;
            lastProgressUpdateTime = Time.Current;
            sessionRecorded = false;

            // Record play start on first entry
            progressManager.RecordPlayStart(currentBeatmapId);
        }

        private void saveProgressOnExit()
        {
            if (string.IsNullOrEmpty(currentBeatmapId) || sessionRecorded) return;

            double duration = getPlaybackDuration();
            if (duration <= 0) return;

            double currentTime = track?.CurrentTime ?? fallbackElapsed;
            double progressFraction = Math.Clamp(currentTime / duration, 0, 1);
            long elapsedMs = (long)(Time.Current - sessionStartTime);

            // Record progress
            progressManager.RecordPlayProgress(currentBeatmapId, progressFraction, elapsedMs);

            // Check for completion (>95% of song played)
            if (progressFraction >= 0.95)
            {
                progressManager.RecordCompletion(currentBeatmapId, playbackSpeed);
            }

            // If looping was used, record practice session
            if (loopStart.HasValue && loopEnd.HasValue)
            {
                progressManager.RecordPracticeSession(
                    currentBeatmapId,
                    elapsedMs,
                    loopStart.Value,
                    loopEnd.Value,
                    playbackSpeed);
            }

            sessionRecorded = true;
            progressManager.Save();
        }

        protected override void Update()
        {
            base.Update();
            applyResponsivePlaybackDensity();

            if (fallbackRunning && track == null)
                fallbackElapsed += Time.Elapsed * playbackSpeed;

            handleMetronome();

            if (!isScrubbingPlayback)
                updatePlaybackProgressUI();

            if (confidenceHeatmap != null)
            {
                double currentTime = track?.CurrentTime ?? fallbackElapsed;
                confidenceHeatmap.UpdatePosition(currentTime);

                if (loopLowConfidenceEnabled)
                {
                    if (loopStart == null || loopEnd == null)
                    {
                        var section = confidenceHeatmap.GetNextLowConfidenceSection(currentTime);
                        if (section != null)
                        {
                            loopStart = section.Value.Start;
                            loopEnd = section.Value.End;
                            if (track != null) track.Seek(loopStart.Value);
                            if (drumTrack != null) drumTrack.Seek(loopStart.Value);
                        }
                    }
                    else if (currentTime > loopEnd.Value)
                    {
                        if (track != null) track.Seek(loopStart.Value);
                        if (drumTrack != null) drumTrack.Seek(loopStart.Value);
                    }
                }
            }
        }

        private void applyResponsivePlaybackDensity(bool force = false)
        {
            if (DrawWidth <= 0 || DrawHeight <= 0)
                return;

            if (!force
                && lastDensityWidth >= 0
                && Math.Abs(DrawWidth - lastDensityWidth) < 0.2f
                && Math.Abs(DrawHeight - lastDensityHeight) < 0.2f)
            {
                return;
            }

            var metrics = PlaybackResponsiveLayout.Compute(DrawWidth, DrawHeight);

            if (statusText != null)
                statusText.Font = BeatSightFont.Section(metrics.HeaderStatusFont);

            if (headerStatusContainer != null)
            {
                headerStatusContainer.Padding = new MarginPadding
                {
                    Left = metrics.HeaderPaddingLeft,
                    Right = metrics.HeaderPaddingRight,
                    Top = metrics.HeaderPaddingTop,
                    Bottom = metrics.HeaderPaddingBottom
                };
            }

            if (playbackToolbar != null)
            {
                playbackToolbar.Padding = new MarginPadding { Bottom = metrics.ToolbarBottomPadding };
                playbackToolbar.CornerRadius = metrics.ToolbarCornerRadius;
            }

            if (toolbarMainContentFlow != null)
            {
                toolbarMainContentFlow.Padding = new MarginPadding
                {
                    Horizontal = metrics.ToolbarInnerPaddingH,
                    Vertical = metrics.ToolbarInnerPaddingV
                };
                toolbarMainContentFlow.Spacing = new Vector2(metrics.ToolbarSectionSpacing, metrics.ToolbarSectionSpacing);
            }

            if (playbackRowFlow != null)
                playbackRowFlow.Spacing = new Vector2(metrics.PlaybackRowSpacingY, metrics.PlaybackRowSpacingY);

            if (toolbarButtonFlow != null)
                toolbarButtonFlow.Spacing = new Vector2(metrics.PlaybackRowSpacingX, 0);

            if (toolbarSliderContainer != null)
            {
                toolbarSliderContainer.Padding = new MarginPadding
                {
                    Left = metrics.SliderContainerPaddingLeft,
                    Right = metrics.SliderContainerPaddingRight,
                    Top = metrics.SliderContainerPaddingTop,
                    Bottom = metrics.SliderContainerPaddingBottom
                };
            }

            if (timelineSlider != null)
                timelineSlider.Height = metrics.TimelineSliderHeight;

            if (confidenceHeatmap != null)
                confidenceHeatmap.Height = metrics.HeatmapHeight;

            if (timelineCurrentText != null)
                timelineCurrentText.Font = BeatSightFont.Section(metrics.TimelineTimeFont);

            if (timelineTotalText != null)
                timelineTotalText.Font = BeatSightFont.Section(metrics.TimelineTimeFont);

            if (timelineSeparatorText != null)
                timelineSeparatorText.Font = BeatSightFont.Caption(metrics.TimelineSeparatorFont);

            foreach (var title in toolbarSectionTitles)
                title.Font = BeatSightFont.Section(metrics.GroupTitleFont);

            foreach (var group in toolbarGroupContainers)
            {
                group.Padding = new MarginPadding
                {
                    Right = metrics.GroupPaddingRight,
                    Bottom = metrics.GroupPaddingBottom
                };
            }

            foreach (var flow in toolbarGroupFlows)
                flow.Spacing = new Vector2(metrics.GroupFlowSpacingX, metrics.GroupFlowSpacingY);

            foreach (var button in toolbarButtons)
            {
                button.Width = metrics.ToolbarButtonWidth;
                button.Height = metrics.ToolbarButtonHeight;
                button.CornerRadius = metrics.ToolbarButtonCorner;

                if (button is BeatSightButton beatSightButton)
                    beatSightButton.FontSize = metrics.ToolbarButtonFont;
            }

            foreach (var button in sidebarControlButtons)
            {
                button.Height = metrics.SidebarButtonHeight;
                button.CornerRadius = metrics.SidebarButtonCorner;

                if (button is BeatSightButton beatSightButton)
                    beatSightButton.FontSize = metrics.SidebarButtonFont;
            }

            foreach (var text in sliderLabelTexts)
                text.Font = BeatSightFont.Body(metrics.SliderLabelFont);

            foreach (var text in sliderValueTexts)
                text.Font = BeatSightFont.Section(metrics.SliderValueFont);

            foreach (var slider in detailSliders)
                slider.Height = metrics.DetailSliderHeight;

            foreach (var block in sliderBlocks)
                block.Spacing = new Vector2(0, metrics.SliderBlockSpacing);

            foreach (var checkbox in detailCheckboxes)
                checkbox.LabelFontSize = metrics.CheckboxLabelFont;

            if (timelineTimeFlow != null)
            {
                timelineTimeFlow.Spacing = new Vector2(metrics.TimelineTimeSpacing, 0);
                timelineTimeFlow.Margin = new MarginPadding { Top = metrics.TimelineTimeTopMargin };
            }

            lastDensityWidth = DrawWidth;
            lastDensityHeight = DrawHeight;
        }

        protected override void Dispose(bool isDisposing)
        {
            // Clean up resources BEFORE calling base.Dispose
            // This ensures our cleanup happens while the object is still valid
            stopMetronomeChannels();
            disposeTrack();

            base.Dispose(isDisposing);
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

            // Note: Lane key bindings removed - this is a drum analysis tool, notes auto-trigger
            // The HandleInput API is retained for potential future live drum input mode

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

            // IMPORTANT: Re-resolve lane assignments BEFORE setting the layout on the
            // playfield so that hit.Lane values are consistent with the new layout
            // when LoadBeatmap→resolveLane reads them.
            if (beatmap != null)
                DrumLaneHeuristics.ApplyToBeatmap(beatmap, currentLaneLayout);

            playfield?.SetLaneLayout(currentLaneLayout);
            rebuildLaneKeyBindings();

            if (beatmap != null && IsLoaded)
                playfield?.LoadBeatmap(beatmap);
        }

        private void rebuildLaneKeyBindings()
        {
            laneKeyBindings.Clear();

            int lanes = currentLaneLayout.LaneCount;
            if (lanes <= 0)
                return;

            // Try to get keys from config, fall back to defaults
            osuTK.Input.Key[] layoutKeys;
            if (config != null)
            {
                layoutKeys = KeyBindingHelper.GetLaneKeys(config, lanes);
            }
            else if (!defaultLaneKeyLayouts.TryGetValue(lanes, out layoutKeys!))
            {
                layoutKeys = fallbackLaneKeyOrder;
            }

            int keysToAssign = Math.Min(lanes, layoutKeys.Length);

            for (int lane = 0; lane < keysToAssign; lane++)
            {
                var key = layoutKeys[lane];
                laneKeyBindings[key] = lane;
            }

            if (keysToAssign < lanes)
            {
                osu.Framework.Logging.Logger.Log(
                    $"[PlaybackScreen] Lane preset requires {lanes} lanes but only {keysToAssign} key bindings are available.",
                    osu.Framework.Logging.LoggingTarget.Runtime,
                    osu.Framework.Logging.LogLevel.Important);
            }
        }

        private void toggleDrumMix()
        {
            setDrumMixMode(!drumsOnlyMode);
        }

        private void toggleLoopLowConfidence()
        {
            // Check if we have confidence data before enabling
            if (!loopLowConfidenceEnabled && confidenceHeatmap != null && !confidenceHeatmap.HasConfidenceData)
            {
                osu.Framework.Logging.Logger.Log(
                    "[Playback] Cannot enable Loop Low Confidence: No confidence data loaded. Re-generate the beatmap with debug output enabled.",
                    osu.Framework.Logging.LoggingTarget.Runtime,
                    osu.Framework.Logging.LogLevel.Important);
                return;
            }

            loopLowConfidenceEnabled = !loopLowConfidenceEnabled;
            if (loopLowConfidenceButton != null)
            {
                loopLowConfidenceButton.Text = loopLowConfidenceEnabled ? "Loop Low Confidence: On" : "Loop Low Confidence: Off";
                setButtonState(loopLowConfidenceButton, loopLowConfidenceEnabled);
            }

            if (!loopLowConfidenceEnabled)
            {
                loopStart = null;
                loopEnd = null;
            }
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

            string? mainPath = cachedFullMixPath;

            if (string.IsNullOrEmpty(mainPath) || storageTrackStore == null)
            {
                track = null;
                return;
            }

            var loadedTrack = storageTrackStore.Get(mainPath);

            if (loadedTrack == null)
            {
                osu.Framework.Logging.Logger.Log($"[Playback] Unable to resolve cached track '{mainPath}'", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);
                track = null;
                return;
            }

            track = loadedTrack;
            track.Completed += onTrackCompleted;

            // Load drum stem if available
            if (drumStemAvailable && !string.IsNullOrEmpty(cachedDrumStemPath))
            {
                drumTrack = storageTrackStore.Get(cachedDrumStemPath);
            }
            else
            {
                drumTrack = null;
            }

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

        private Dictionary<string, SampleChannel> customSampleChannels = new Dictionary<string, SampleChannel>();

        private void loadCustomSamples()
        {
            customSampleChannels.Clear();
            if (beatmap?.DrumKit?.CustomSamples == null) return;

            string cacheFolder = "PlaybackAudio/Samples/" + sanitizeFileComponent(beatmap.Metadata.BeatmapId);
            string absoluteCacheFolder = host.Storage.GetFullPath(cacheFolder);
            if (!Directory.Exists(absoluteCacheFolder))
                Directory.CreateDirectory(absoluteCacheFolder);

            foreach (var kvp in beatmap.DrumKit.CustomSamples)
            {
                string component = kvp.Key;
                string filename = kvp.Value;

                string sourcePath = Path.IsPathRooted(filename)
                    ? filename
                    : Path.Combine(Path.GetDirectoryName(beatmapPath) ?? "", filename);

                if (!File.Exists(sourcePath)) continue;

                string extension = Path.GetExtension(filename);
                string cachedName = $"{component}{extension}";
                string relativePath = Path.Combine(cacheFolder, cachedName).Replace(Path.DirectorySeparatorChar, '/');
                string absolutePath = Path.Combine(absoluteCacheFolder, cachedName);

                try
                {
                    File.Copy(sourcePath, absolutePath, true);
                    var sample = storageSampleStore?.Get(relativePath);
                    if (sample != null)
                    {
                        customSampleChannels[component] = sample.GetChannel();
                    }
                }
                catch (Exception ex)
                {
                    osu.Framework.Logging.Logger.Log($"Failed to load custom sample for {component}: {ex.Message}");
                }
            }
        }

        private void playHitsound(string component)
        {
            if (hitsoundVolumeEnabledSetting?.Value == false) return;

            double volume = hitsoundVolumeSetting?.Value ?? 1.0;
            if (volume <= 0) return;

            // Try custom sample first
            if (customSampleChannels.TryGetValue(component, out var channel))
            {
                channel.Volume.Value = volume;
                channel.Play();
                return;
            }

            // Fallback to default samples
            string sampleName = getSampleNameForComponent(component);
            if (string.IsNullOrEmpty(sampleName)) return;

            // Try embedded store first for defaults
            var sample = embeddedSampleStore?.Get(sampleName);
            if (sample != null)
            {
                var defaultChannel = sample.GetChannel();
                defaultChannel.Volume.Value = volume;
                defaultChannel.Play();
            }
        }

        private string getSampleNameForComponent(string component)
        {
            return component switch
            {
                "kick" => "Gameplay/kick",
                "snare" => "Gameplay/snare",
                "hihat_closed" => "Gameplay/hihat-closed",
                "hihat_open" => "Gameplay/hihat-open",
                "crash" => "Gameplay/crash",
                "ride" => "Gameplay/ride",
                "tom_high" => "Gameplay/tom-high",
                "tom_mid" => "Gameplay/tom-mid",
                "tom_low" => "Gameplay/tom-low",
                _ => "Gameplay/hit-normal"
            };
        }
    }
}
