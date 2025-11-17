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
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.IO.Stores;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osu.Framework.Timing;
using osuTK;
using osuTK.Graphics;

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
        private bool metronomeInitialised;
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
        private bool KickLineEnabled => kickLaneModeSetting?.Value == KickLaneMode.GlobalLine;

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
                new GridContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    RowDimensions = new[]
                    {
                        new Dimension(GridSizeMode.Absolute, 55),
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
                },
                backButton,
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
                pendingMetronomePulse = true;
                if (!e.NewValue)
                {
                    stopMetronomeChannels();
                }
                else if (metronomeInitialised)
                {
                    TriggerMetronomePreview(accent: true);
                }

                metronomeInitialised = true;
            }, true);
            metronomeSoundSetting.BindValueChanged(e => loadMetronomeSamples(e.NewValue), true);
            drumStemPreferredSetting = config.GetBindable<bool>(BeatSightSetting.DrumStemPlaybackOnly);
            drumStemPreferredSetting.BindValueChanged(e => applyDrumStemPreference(e.NewValue), true);
            lanePresetSetting = config.GetBindable<LanePreset>(BeatSightSetting.LanePreset);
            lanePresetSetting.BindValueChanged(onLanePresetChanged, true);
            laneViewModeSetting = config.GetBindable<LaneViewMode>(BeatSightSetting.LaneViewMode);
            laneViewModeSetting.BindValueChanged(e => updateViewModeToggle(e.NewValue), true);
            kickLaneModeSetting = config.GetBindable<KickLaneMode>(BeatSightSetting.KickLaneMode);
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
                Font = new FontUsage(size: 24, weight: "Medium"),
                Colour = Color4.White,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
            };

            applyHeaderStatus();

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding { Left = 150, Right = 28, Top = 6, Bottom = 4 },
                Child = statusText
            };
        }

        private Drawable createPlayfieldArea()
        {
            playfield = new GameplayPlayfield(getCurrentTime)
            {
                RelativeSizeAxes = Axes.Both,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Size = Vector2.One
            };

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
                Font = new FontUsage(size: 14, weight: "Medium"),
                Colour = new Color4(200, 205, 220, 255)
            };

            timelineTotalText = new SpriteText
            {
                Text = "--:--",
                Font = new FontUsage(size: 14, weight: "Medium"),
                Colour = new Color4(150, 160, 185, 255)
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
                        Children = new Drawable[]
                        {
                            timelineCurrentText,
                            new SpriteText
                            {
                                Text = "/",
                                Font = new FontUsage(size: 14),
                                Colour = new Color4(150, 160, 185, 255)
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
                    new Dimension(GridSizeMode.Relative, 0.5f),
                    new Dimension(GridSizeMode.Relative, 0.5f)
                },
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize),
                    new Dimension(GridSizeMode.AutoSize)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createControlGroup("Stage Layout", createViewModeControls()),
                        createControlGroup("Playback Speed", createSpeedControl())
                    },
                    new Drawable[]
                    {
                        createControlGroup("Timing Offset", createOffsetControl()),
                        createControlGroup("Audio", createAudioControls())
                    }
                }
            };

            updatePlayPauseButton();

            return new ResponsiveToolbarContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
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
                            Colour = new Color4(14, 16, 26, 220)
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
                            Font = new FontUsage(size: 15, weight: "Medium"),
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

            if (!scrubbing)
            {
                seekToNormalized(playbackProgress.Value, allowStateReset: true);
                updatePlaybackProgressUI();
            }
        }

        private void onPlaybackProgressChanged(ValueChangedEvent<double> value)
        {
            if (suppressPlaybackProgressUpdate)
                return;

            seekToNormalized(value.NewValue, allowStateReset: !isScrubbingPlayback);
            updatePlaybackProgressUI();
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

            int totalSeconds = (int)Math.Round(ms / 1000.0);
            int minutes = totalSeconds / 60;
            int seconds = totalSeconds % 60;
            return $"{minutes}:{seconds:D2}";
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

        private Drawable createViewModeControls()
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
                    new SpriteText
                    {
                        Text = "Toggle between 2D lanes and the 3D stage.",
                        Font = new FontUsage(size: 13),
                        Colour = new Color4(170, 180, 210, 255),
                        Alpha = 0.9f
                    },
                    kickLayoutToggleButton,
                    new SpriteText
                    {
                        Text = "Switch kick drum between a shared timing line and per-pad notes.",
                        Font = new FontUsage(size: 13),
                        Colour = new Color4(170, 180, 210, 255),
                        Alpha = 0.9f
                    }
                }
            };
        }

        private Drawable createSpeedControl()
        {
            speedValueText = new SpriteText
            {
                Font = new FontUsage(size: 16, weight: "Medium"),
                Colour = new Color4(220, 225, 240, 255),
                Text = formatSpeedLabel(speedAdjustment.Value)
            };

            var slider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 16,
                Current = speedAdjustment
            };

            return createSliderBlock("Playback speed", speedValueText, slider, showLabel: false);
        }

        private void updateSpeedSliderBounds()
        {
            if (speedMinSetting == null || speedMaxSetting == null)
                return;

            double min = Math.Clamp(speedMinSetting.Value, 0.1, 5.0);
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
                Font = new FontUsage(size: 16, weight: "Medium"),
                Colour = new Color4(220, 225, 240, 255),
                Text = formatOffsetLabel(offsetAdjustment.Value)
            };

            var slider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 16,
                Current = offsetAdjustment
            };

            return createSliderBlock("Global offset", offsetValueText, slider, showLabel: false);
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
                                    Font = new FontUsage(size: 16),
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

        private Drawable createAudioControls()
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

            var next = laneViewModeSetting.Value == LaneViewMode.TwoDimensional
                ? LaneViewMode.ThreeDimensional
                : LaneViewMode.TwoDimensional;

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

            bool is3D = mode == LaneViewMode.ThreeDimensional;
            viewModeToggleButton.Text = is3D ? "Stage View: 3D" : "Stage View: 2D";
            setButtonState(viewModeToggleButton, is3D);
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
                bool restart = isAtPlaybackEnd();
                startPlayback(restart);
            }

            updatePlaybackProgressUI();
        }

        private bool isPlaybackActive()
        {
            if (track != null)
                return isTrackRunning || track.IsRunning;

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

        private void onPlayfieldResult(GameplayPlayfield.HitResult result, double offset, Color4 accentColour)
        {
            if (hitLightingEnabled?.Value == true && (result == GameplayPlayfield.HitResult.Perfect || result == GameplayPlayfield.HitResult.Great))
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
                DrumLaneHeuristics.ApplyToBeatmap(beatmap, currentLaneLayout);
                playfield?.SetLaneLayout(currentLaneLayout);
                playfield?.LoadBeatmap(beatmap);
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
                    track.Seek(0);

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
                fallbackElapsed += Time.Elapsed;

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
                    if (result != GameplayPlayfield.HitResult.None)
                        return true;
                }
            }

            return base.OnKeyDown(e);
        }

        private void onLanePresetChanged(ValueChangedEvent<LanePreset> preset)
        {
            currentLaneLayout = LaneLayoutFactory.Create(preset.NewValue);

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
                    $"[GameplayScreen] Lane preset requires {lanes} lanes but only {keysToAssign} default key bindings are available.",
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
            updateMusicVolumeOutput();
            track.Tempo.Value = playbackSpeed;
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

            osu.Framework.Logging.Logger.Log($"[Gameplay] Switching audio mode: drumsOnly={targetDrumsOnly}, drumStemAvailable={drumStemAvailable}",
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
                osu.Framework.Logging.Logger.Log($"[Gameplay] Audio mode switched successfully, track loaded: {(drumsOnlyMode ? "Drums Only" : "Full Mix")}",
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
                osu.Framework.Logging.Logger.Log($"[Gameplay] Metronome tick: beat {beatIndex}, accent={isAccentBeat}, bpm={bpm:F1}",
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
                osu.Framework.Logging.Logger.Log($"[Gameplay] Failed to play metronome sample: {ex.Message}",
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
                    osu.Framework.Logging.Logger.Log($"[Gameplay] Missing metronome sample: {path}",
                        osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Debug);

                return sample;
            }
            catch (Exception ex)
            {
                osu.Framework.Logging.Logger.Log($"[Gameplay] Error loading metronome sample '{path}': {ex.Message}",
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

            osu.Framework.Logging.Logger.Log("[Gameplay] No metronome samples available after fallbacks",
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
                var handled = base.OnMouseDown(e);
                if (handled)
                    setScrubbing(true);
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

        private partial class ResponsiveToolbarContainer : Container
        {
            private MarginPadding cachedPadding;

            public ResponsiveToolbarContainer()
            {
                RelativeSizeAxes = Axes.X;
                AutoSizeAxes = Axes.Y;
                Anchor = Anchor.BottomCentre;
                Origin = Anchor.BottomCentre;
            }

            protected override void Update()
            {
                base.Update();

                if (Parent == null || Parent.DrawWidth <= 0)
                    return;

                // Responsive horizontal padding (scales with width, but has limits)
                float horizontalPadding = Math.Clamp(Parent.DrawWidth * 0.03f, 20f, 50f);

                // Responsive bottom padding (scales with height, but has limits)
                float bottomPadding = Math.Clamp(Parent.DrawHeight * 0.025f, 16f, 32f);

                var targetPadding = new MarginPadding
                {
                    Left = horizontalPadding,
                    Right = horizontalPadding,
                    Bottom = bottomPadding
                };

                if (!cachedPadding.Equals(targetPadding))
                {
                    Padding = targetPadding;
                    cachedPadding = targetPadding;
                }
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

                // Calculate bottom padding based on available height to prevent toolbar overlap
                // Ensure at least 240px for toolbar controls, scale up to 320px for larger windows
                float toolbarSpace = Math.Clamp(DrawHeight * 0.40f, 240f, 320f);
                float bottomPadding = toolbarSpace + 25f; // Extra 25px safety margin

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
                        Padding = new MarginPadding { Horizontal = 18, Vertical = 16 },
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
    public partial class GameplayPlayfield : CompositeDrawable
    {
        private LaneLayout laneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
        private int laneCount => Math.Max(1, laneLayout.LaneCount);
        private const double approachDuration = 1800; // milliseconds from spawn to hit line
        private const double perfectWindow = 35;
        private const double greatWindow = 80;
        private const double goodWindow = 130;
        private const double mehWindow = 180;
        private const double missWindow = 220;

        private readonly Func<double> currentTimeProvider;
        private readonly List<DrawableNote> notes = new();
        private readonly List<DrawableNote> kickNoteBuffer = new();
        private int firstActiveNoteIndex;
        private const double futureVisibilityWindow = approachDuration + 900;
        private const double pastVisibilityWindow = missWindow + 600;
        private bool isPreviewMode; // If true, notes won't be auto-judged

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        private Bindable<GameplayMode> gameplayMode = null!;
        private Bindable<bool> showApproachCircles = null!;
        private Bindable<bool> showParticleEffects = null!;
        private Bindable<bool> showGlowEffects = null!;
        private Bindable<bool> showHitBurstAnimations = null!;

        private Container noteLayer = null!;
        private Container laneBackgroundContainer = null!;
        private Container laneGuideOverlay = null!;
        private TimingGridOverlay? timingGridOverlay;
        private TimingStrikeZone? timingStrikeZone;
        private KickGuideLine? kickGuideLine2D;
        private ThreeDHighwayBackground? threeDHighwayBackground;
        private Beatmap? loadedBeatmap;

        private Bindable<LaneViewMode> laneViewMode = null!;
        private LaneViewMode currentLaneViewMode;
        private bool kickUsesGlobalLine = true;

        public event Action<HitResult, double, Color4>? ResultApplied;

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
            timingGridOverlay = new TimingGridOverlay();
            timingStrikeZone = new TimingStrikeZone();
            kickGuideLine2D = createKickGuideLine2D();

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(26, 26, 40, 255)
                },
                laneBackgroundContainer,
                timingGridOverlay,
                kickGuideLine2D,
                timingStrikeZone,
                noteLayer,
                laneGuideOverlay
            };

            laneViewMode.BindValueChanged(onLaneViewModeChanged, true);

            if (loadedBeatmap != null)
                LoadBeatmap(loadedBeatmap);
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

        private KickGuideLine createKickGuideLine2D()
        {
            // Create a dynamic kick line that shows kick note positions
            var kickLine = new KickGuideLine
            {
                RelativeSizeAxes = Axes.Both,
                Alpha = 0, // Hidden by default
            };

            return kickLine;
        }

        private Drawable createLaneGrid3D()
        {
            threeDHighwayBackground = new ThreeDHighwayBackground(laneLayout, kickUsesGlobalLine);
            return threeDHighwayBackground;
        }

        private void onLaneViewModeChanged(ValueChangedEvent<LaneViewMode> mode)
        {
            currentLaneViewMode = mode.NewValue;

            rebuildLaneBackground();

            laneGuideOverlay.FadeTo(currentLaneViewMode == LaneViewMode.ThreeDimensional ? 1f : 0f, 180, Easing.OutQuint);

            timingGridOverlay?.SetViewMode(currentLaneViewMode);
            timingStrikeZone?.SetViewMode(currentLaneViewMode);

            if (kickGuideLine2D != null)
            {
                kickGuideLine2D.FadeTo(kickUsesGlobalLine && currentLaneViewMode == LaneViewMode.TwoDimensional ? 1f : 0f, 180, Easing.OutQuint);
                kickGuideLine2D.ResetVisuals();
            }

            foreach (var note in notes)
                note.SetViewMode(currentLaneViewMode);
        }

        private void rebuildLaneBackground()
        {
            if (laneBackgroundContainer == null)
                return;

            laneBackgroundContainer.Clear();
            threeDHighwayBackground = null;

            if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
            {
                laneBackgroundContainer.Add(createLaneGrid3D());
                threeDHighwayBackground?.ResetKickTimeline();
                threeDHighwayBackground?.SetKickGuideVisible(kickUsesGlobalLine);
            }
            else
            {
                laneBackgroundContainer.Add(createLaneGrid2D());
            }
        }

        private Drawable createLaneGrid2D()
        {
            int totalLanes = laneCount;
            int kickLane = laneLayout?.KickLane ?? 0;

            var visibleLanes = new List<int>();
            for (int lane = 0; lane < totalLanes; lane++)
            {
                if (!kickUsesGlobalLine || lane != kickLane)
                    visibleLanes.Add(lane);
            }

            if (visibleLanes.Count == 0)
                visibleLanes.Add(kickLane);

            int displayedLanes = visibleLanes.Count;
            var columnDimensions = Enumerable.Repeat(new Dimension(GridSizeMode.Relative, 1f / displayedLanes), displayedLanes).ToArray();

            int totalLogicalLanes = laneLayout?.LaneCount ?? totalLanes;

            var columns = visibleLanes
                .Select((laneIndex, displayIndex) => createLaneBackground(laneIndex, displayIndex, displayedLanes, totalLogicalLanes, laneIndex == kickLane && !kickUsesGlobalLine))
                .ToArray();

            return new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                ColumnDimensions = columnDimensions,
                Content = new[] { columns }
            };
        }

        private Drawable createLaneBackground(int laneIndex, int displayIndex, int visibleLaneCount, int totalLaneCount, bool emphasiseKick)
        {
            ColourInfo laneFill;

            if (emphasiseKick)
            {
                var top = UITheme.Emphasise(UITheme.KickGlobalFill, 1.15f);
                var bottom = UITheme.Emphasise(UITheme.KickGlobalFill, 0.82f);
                laneFill = ColourInfo.GradientVertical(top, bottom);
            }
            else
            {
                var colour = UITheme.GetLaneColour(displayIndex, visibleLaneCount);
                laneFill = ColourInfo.SingleColour(colour);
            }

            var edgeColour = emphasiseKick
                ? UITheme.Emphasise(UITheme.KickGlobalGlow, 0.85f)
                : UITheme.GetLaneEdgeColour(displayIndex, visibleLaneCount);

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = laneFill
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 3,
                        Anchor = Anchor.TopRight,
                        Origin = Anchor.TopRight,
                        Colour = edgeColour,
                        Alpha = emphasiseKick ? 0.55f : 0.38f
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

        public void SetLaneLayout(LaneLayout layout)
        {
            if (layout == null)
                throw new ArgumentNullException(nameof(layout));

            if (ReferenceEquals(laneLayout, layout))
                return;

            laneLayout = layout;
            rebuildLaneBackground();
            timingGridOverlay?.SetLaneLayout(laneLayout);
            timingStrikeZone?.SetLaneLayout(laneLayout);
            applyKickModeToNotes();
        }

        public void SetKickLineMode(bool useGlobalLine)
        {
            kickUsesGlobalLine = useGlobalLine;
            applyKickModeToNotes();

            if (IsLoaded)
                rebuildLaneBackground();

            threeDHighwayBackground?.ResetKickTimeline();
            threeDHighwayBackground?.SetKickGuideVisible(kickUsesGlobalLine);
            timingGridOverlay?.SetKickMode(kickUsesGlobalLine);
            timingStrikeZone?.SetKickMode(kickUsesGlobalLine);

            // Show/hide the 2D kick guide line
            if (kickGuideLine2D != null)
            {
                kickGuideLine2D.FadeTo(
                    useGlobalLine && currentLaneViewMode == LaneViewMode.TwoDimensional ? 1f : 0f,
                    180,
                    Easing.OutQuint);

                kickGuideLine2D.ResetVisuals();
            }
        }

        public void JumpToTime(double timeMs)
        {
            if (notes.Count == 0)
                return;

            double cutoff = timeMs - pastVisibilityWindow;
            int index = notes.FindIndex(n => n.HitTime >= cutoff);

            if (index < 0)
                firstActiveNoteIndex = notes.Count;
            else
                firstActiveNoteIndex = Math.Max(0, index - 2);

            for (int i = 0; i < firstActiveNoteIndex && i < notes.Count; i++)
                notes[i].Alpha = 0;
        }

        public void StartSession(bool restart)
        {
            if (!restart)
                return;

            if (loadedBeatmap != null)
            {
                LoadBeatmap(loadedBeatmap);
                return;
            }

            noteLayer.Clear();
            notes.Clear();
            resetSessionState();
        }

        private void resetSessionState()
        {
            firstActiveNoteIndex = 0;
            kickNoteBuffer.Clear();
        }

        public void LoadBeatmap(Beatmap beatmap)
        {
            if (beatmap == null)
                throw new ArgumentNullException(nameof(beatmap));

            loadedBeatmap = beatmap;
            osu.Framework.Logging.Logger.Log($"[GameplayPlayfield] LoadBeatmap called: {beatmap.HitObjects.Count} hit objects, preview mode: {isPreviewMode}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);

            if (noteLayer == null)
                return;

            noteLayer.Clear();
            notes.Clear();

            resetSessionState();

            var generatedNotes = new List<DrawableNote>(beatmap.HitObjects.Count);

            foreach (var hit in beatmap.HitObjects)
            {
                int lane = resolveLane(hit);
                var note = new DrawableNote(hit, lane, showApproachCircles, showGlowEffects, showParticleEffects)
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.Centre,
                    Alpha = 0 // Start invisible to prevent flashing at (0,0) before first Update
                };

                generatedNotes.Add(note);
            }

            generatedNotes.Sort((a, b) => a.HitTime.CompareTo(b.HitTime));

            foreach (var note in generatedNotes)
            {
                noteLayer.Add(note);
                notes.Add(note);
                note.SetViewMode(currentLaneViewMode);
                note.SetApproachProgress(0);
            }

            firstActiveNoteIndex = 0;
            osu.Framework.Logging.Logger.Log($"[GameplayPlayfield] LoadBeatmap complete: {notes.Count} notes added to noteLayer", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
            applyKickModeToNotes();
            timingGridOverlay?.Configure(beatmap, laneLayout, kickUsesGlobalLine);
            timingGridOverlay?.SetViewMode(currentLaneViewMode);
            timingStrikeZone?.SetLaneLayout(laneLayout);
            timingStrikeZone?.SetKickMode(kickUsesGlobalLine);
            timingStrikeZone?.SetViewMode(currentLaneViewMode);
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

            // Don't process updates if the component hasn't been sized yet
            if (DrawWidth <= 0 || DrawHeight <= 0)
                return;

            var startTime = System.Diagnostics.Stopwatch.StartNew();

            double currentTime = currentTimeProvider();
            threeDHighwayBackground?.UpdateScroll(currentTime);
            int lanes = laneCount;

            // When kick line mode is enabled, calculate lane width excluding the kick lane
            int displayedLanes = lanes;
            if (kickUsesGlobalLine && currentLaneViewMode == LaneViewMode.TwoDimensional)
                displayedLanes = Math.Max(1, lanes - 1); // One less lane displayed

            float laneWidth = displayedLanes > 0 ? DrawWidth / displayedLanes : 0;
            float hitLineY = DrawHeight * 0.85f;
            float spawnTop = currentLaneViewMode == LaneViewMode.ThreeDimensional ? DrawHeight * 0.15f : DrawHeight * 0.05f;
            float travelDistance = hitLineY - spawnTop;

            timingStrikeZone?.UpdateGeometry(DrawWidth, DrawHeight, hitLineY, spawnTop, laneWidth, lanes, displayedLanes, laneLayout?.KickLane ?? 0, kickUsesGlobalLine, currentLaneViewMode);
            timingGridOverlay?.UpdateState(currentTime, DrawWidth, DrawHeight, spawnTop, hitLineY, travelDistance, laneWidth, lanes, displayedLanes, laneLayout?.KickLane ?? 0, currentLaneViewMode, kickUsesGlobalLine);

            int noteCount = notes.Count;
            if (noteCount == 0)
                return;

            double pastCutoff = isPreviewMode ? double.NegativeInfinity : currentTime - pastVisibilityWindow;
            if (!isPreviewMode)
            {
                // Safety check to prevent infinite loop
                int safetyCounter = 0;
                const int maxIterations = 10000; // Prevent infinite loops

                while (firstActiveNoteIndex < noteCount && safetyCounter < maxIterations)
                {
                    var candidate = notes[firstActiveNoteIndex];
                    if (!candidate.IsJudged && candidate.HitTime >= pastCutoff)
                        break;

                    firstActiveNoteIndex++;
                    safetyCounter++;
                }

                if (safetyCounter >= maxIterations)
                {
                    osu.Framework.Logging.Logger.Log($"[GameplayPlayfield] Warning: Hit safety limit while processing notes. firstActiveNoteIndex: {firstActiveNoteIndex}, noteCount: {noteCount}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
                }
            }
            else
            {
                firstActiveNoteIndex = 0;
            }

            int startIndex = isPreviewMode ? 0 : Math.Max(0, firstActiveNoteIndex - 2);
            int notesProcessed = 0;
            const int maxNotesPerFrame = 500; // Prevent processing too many notes in one frame

            for (int i = startIndex; i < noteCount && notesProcessed < maxNotesPerFrame; i++)
            {
                var note = notes[i];

                double timeUntilHit = note.HitTime - currentTime;
                if (!isPreviewMode && timeUntilHit > futureVisibilityWindow)
                    break;

                if (note.IsJudged)
                    continue;

                notesProcessed++;

                double progress = 1 - (timeUntilHit / approachDuration);

                float clampedProgress = (float)Math.Clamp(progress, 0, 1.15);
                note.SetApproachProgress((float)Math.Clamp(progress, 0, 1));

                if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
                    updateNoteTransform3D(note, clampedProgress);
                else
                    updateNoteTransform2D(note, laneWidth, hitLineY, travelDistance, spawnTop, clampedProgress);

                if (isPreviewMode)
                {
                    note.Alpha = 1;
                }
                else
                {
                    note.Alpha = timeUntilHit < -50 ? 0 : 1;
                }

                if (!isPreviewMode && timeUntilHit < -missWindow)
                    applyResult(note, HitResult.Miss, timeUntilHit);
            }

            if (kickUsesGlobalLine)
            {
                float strikeZoneHeight = timingStrikeZone?.VisualHitZoneHeight ?? 0f;
                if (currentLaneViewMode == LaneViewMode.TwoDimensional)
                    kickGuideLine2D?.UpdateBaseline(DrawHeight, hitLineY, strikeZoneHeight);

                kickNoteBuffer.Clear();
                const double previewWindow = approachDuration * 1.4;
                const double pastAllowance = 220;

                foreach (var note in notes)
                {
                    if (!note.IsKick || note.IsJudged)
                        continue;

                    double timeUntil = note.HitTime - currentTime;
                    if (timeUntil < -pastAllowance)
                        continue;

                    if (timeUntil > previewWindow)
                    {
                        if (kickNoteBuffer.Count > 0)
                            break;

                        continue;
                    }

                    kickNoteBuffer.Add(note);

                    if (kickNoteBuffer.Count >= 8)
                        break;
                }

                if (currentLaneViewMode == LaneViewMode.TwoDimensional && kickGuideLine2D != null)
                    kickGuideLine2D.UpdateKickNotes(kickNoteBuffer, currentTime, DrawHeight, approachDuration);

                if (currentLaneViewMode == LaneViewMode.ThreeDimensional)
                    threeDHighwayBackground?.UpdateKickTimeline(kickNoteBuffer, currentTime, approachDuration);
            }

            startTime.Stop();
            if (startTime.ElapsedMilliseconds > 16) // Log if Update takes longer than one frame (16ms at 60fps)
            {
                osu.Framework.Logging.Logger.Log($"[GameplayPlayfield] Slow Update: {startTime.ElapsedMilliseconds}ms, notes: {noteCount}, processed: {notesProcessed}, firstActive: {firstActiveNoteIndex}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
            }
        }

        private void updateNoteTransform2D(DrawableNote note, float laneWidth, float hitLineY, float travelDistance, float spawnTop, float progress)
        {
            // Additional safety check
            if (DrawWidth <= 0 || DrawHeight <= 0 || laneWidth <= 0)
                return;

            // Special handling for kick notes in global line mode
            if (note.IsKick && kickUsesGlobalLine)
            {
                float targetBandY = hitLineY;
                float fullWidth = DrawWidth * 0.92f;
                float thickness = Math.Clamp(DrawHeight * 0.028f, 14f, 30f);

                float x = DrawWidth / 2f;
                float kickNoteY = targetBandY - travelDistance * (1f - progress);
                kickNoteY = Math.Clamp(kickNoteY, spawnTop + thickness * 0.5f, targetBandY + thickness * 0.7f);

                note.ApplyKickLineDimensions(fullWidth, thickness, LaneViewMode.TwoDimensional);
                note.Position = new Vector2(x, kickNoteY);
                note.Scale = Vector2.One;
                note.Rotation = 0;
                setNoteDepth(note, -kickNoteY - 2f);
                return;
            }

            // Regular note positioning
            float noteY = hitLineY - travelDistance * (1 - progress);
            noteY = Math.Clamp(noteY, spawnTop, hitLineY + 40);

            // Adjust lane index when kick line mode is enabled
            int displayLane = note.Lane;
            if (kickUsesGlobalLine && currentLaneViewMode == LaneViewMode.TwoDimensional)
            {
                int kickLane = laneLayout?.KickLane ?? 0;
                if (displayLane > kickLane)
                    displayLane--;
                else if (displayLane == kickLane)
                    displayLane = Math.Max(0, displayLane - 1);
            }

            float noteX = laneWidth * displayLane + laneWidth / 2f;

            note.Position = new Vector2(noteX, noteY);
            note.Scale = Vector2.One;
            note.Rotation = 0;
            setNoteDepth(note, -noteY);
        }

        private void updateNoteTransform3D(DrawableNote note, float progress)
        {
            // Additional safety check
            if (DrawWidth <= 0 || DrawHeight <= 0)
                return;

            float t = Math.Clamp(progress, 0f, 1f);
            float centerX = DrawWidth / 2f;
            float bottomY = DrawHeight * 0.85f;
            float topY = DrawHeight * 0.15f;

            int lanes = laneCount;
            int kickLaneIndex = laneLayout?.KickLane ?? 0;
            int visualLaneCount = kickUsesGlobalLine ? Math.Max(1, lanes - 1) : lanes;

            float displayLane = note.Lane;

            if (kickUsesGlobalLine)
            {
                if (note.IsKick)
                {
                    displayLane = (visualLaneCount - 1) / 2f;
                }
                else
                {
                    if (displayLane > kickLaneIndex)
                        displayLane -= 1;
                    else if (displayLane == kickLaneIndex)
                        displayLane = Math.Max(0, displayLane - 1);
                }
            }

            float laneOffset = visualLaneCount <= 1
                ? 0
                : displayLane - (visualLaneCount - 1) / 2f;
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
                if (kickUsesGlobalLine)
                {
                    float width = Math.Min(DrawWidth * (0.72f + visualLaneCount * 0.04f), DrawWidth * 0.94f);
                    float thickness = Math.Clamp(DrawHeight * 0.035f, 12f, 40f) * (0.9f + t * 0.5f);

                    note.ApplyKickLineDimensions(width, thickness, LaneViewMode.ThreeDimensional);
                    note.Position = new Vector2(centerX, y);
                    note.Scale = new Vector2(1f, lerp(0.92f, 1.1f, t));
                    note.Rotation = -4f + t * 6f;
                    setNoteDepth(note, -t * 1050f - 40f);
                    return;
                }

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
            if (noteLayer == null || note.Parent != noteLayer)
                return;

            // Validate depth is not NaN or Infinity
            if (float.IsNaN(depth) || float.IsInfinity(depth))
            {
                osu.Framework.Logging.Logger.Log($"[GameplayPlayfield] Invalid depth value: {depth}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
                return;
            }

            float tolerance = currentLaneViewMode == LaneViewMode.ThreeDimensional ? 12f : 5f;

            if (note.ShouldUpdateDepth(depth, tolerance))
            {
                try
                {
                    noteLayer.ChangeChildDepth(note, depth);
                }
                catch (Exception ex)
                {
                    osu.Framework.Logging.Logger.Log($"[GameplayPlayfield] Error changing note depth: {ex.Message}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Error);
                }
            }
        }

        private void applyResult(DrawableNote note, HitResult result, double offset)
        {
            if (note.IsJudged)
                return;

            note.ApplyResult(result);
            ResultApplied?.Invoke(result, offset, note.AccentColour);
        }

        private void applyKickModeToNotes()
        {
            if (notes.Count == 0)
                return;

            int globalLane = laneLayout?.KickLane ?? 0;

            foreach (var note in notes)
                note.ApplyKickMode(kickUsesGlobalLine, globalLane);
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);
        }
        private int resolveLane(HitObject hit)
        {
            int lane = DrumLaneHeuristics.ResolveLane(hit.Component, laneLayout, hit.Lane);
            return laneLayout.ClampLane(lane);
        }

        private sealed partial class TimingStrikeZone : CompositeDrawable
        {
            private readonly Container strikeBody;
            private readonly Box fill;
            private readonly Box glow;
            private readonly Box rim;
            private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
            private bool useGlobalKick = true;
            private float baselineOffset;
            private float visualHeight;

            public float VisualHitZoneHeight => visualHeight;

            public TimingStrikeZone()
            {
                RelativeSizeAxes = Axes.X;
                Anchor = Anchor.BottomCentre;
                Origin = Anchor.BottomCentre;
                Width = 0.98f;
                Height = 28f;
                AlwaysPresent = true;
                Alpha = 0.92f;

                strikeBody = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 14,
                    BorderThickness = 4,
                    BorderColour = new Color4(255, 220, 200, 220)
                };

                fill = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(42, 46, 72, 120)
                };

                glow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(255, 214, 170, 80),
                    Alpha = 0.35f,
                    Blending = BlendingParameters.Additive
                };

                rim = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 3,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = new Color4(255, 245, 230, 140)
                };

                strikeBody.Add(fill);
                strikeBody.Add(glow);

                InternalChildren = new Drawable[]
                {
                    strikeBody,
                    rim
                };

                updatePalette();
            }

            public void SetLaneLayout(LaneLayout layout)
            {
                // Currently unused, but retained for future per-lane styling customisation.
                _ = layout;
            }

            public void SetKickMode(bool globalKick)
            {
                useGlobalKick = globalKick;
                updatePalette();
            }

            public void SetViewMode(LaneViewMode mode)
            {
                viewMode = mode;
                updatePalette();
            }

            public void UpdateGeometry(float drawWidth, float drawHeight, float hitLineY, float spawnTop, float laneWidth, int lanes, int visibleLanes, int kickLaneIndex, bool globalKick, LaneViewMode mode)
            {
                _ = drawWidth;
                _ = spawnTop;
                _ = laneWidth;
                _ = lanes;
                _ = visibleLanes;
                _ = kickLaneIndex;
                useGlobalKick = globalKick;
                viewMode = mode;

                float baseHeight = mode == LaneViewMode.ThreeDimensional
                    ? Math.Clamp(drawHeight * 0.058f, 20f, 50f)
                    : Math.Clamp(drawHeight * 0.038f, 18f, 36f);

                Height = baseHeight;
                visualHeight = baseHeight;

                float offsetFromBottom = Math.Clamp(drawHeight - hitLineY - baseHeight / 2f, 0f, drawHeight);
                baselineOffset = offsetFromBottom;
                Y = -baselineOffset;

                float widthFactor = mode == LaneViewMode.ThreeDimensional ? 0.92f : 0.98f;
                Width = Math.Clamp(widthFactor, 0.7f, 0.99f);

                float cornerRadius = Math.Clamp(baseHeight * 0.48f, 8f, 28f);
                strikeBody.CornerRadius = cornerRadius;
                strikeBody.BorderThickness = Math.Clamp(baseHeight * 0.28f, 3f, 6f);
                rim.Height = mode == LaneViewMode.ThreeDimensional ? 4f : 3f;
                rim.Alpha = mode == LaneViewMode.ThreeDimensional ? 0.9f : 0.75f;

                updatePalette();
            }

            private void updatePalette()
            {
                var border = useGlobalKick
                    ? new Color4(255, 210, 182, 230)
                    : new Color4(182, 205, 255, 220);

                var fillColour = useGlobalKick
                    ? new Color4(52, 40, 90, 110)
                    : new Color4(34, 42, 68, 110);

                strikeBody.BorderColour = border;
                fill.Colour = fillColour;
                glow.Colour = UITheme.Emphasise(border, 1.12f);
                glow.Alpha = useGlobalKick ? 0.48f : 0.28f;
                rim.Colour = new Color4(border.R, border.G, border.B, 180);
            }
        }

        private sealed partial class TimingGridOverlay : CompositeDrawable
        {
            private readonly List<GridMarker> markers = new List<GridMarker>();
            private readonly List<DrawableGridLine> lineBuffer = new List<DrawableGridLine>();
            private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
            private bool useGlobalKick = true;
            private LaneLayout? laneLayout;

            private const double previewMultiplier = 1.7;
            private const double pastAllowance = 320;

            public TimingGridOverlay()
            {
                RelativeSizeAxes = Axes.Both;
                Alpha = 0.85f;
                AlwaysPresent = true;
            }

            public void Configure(Beatmap beatmap, LaneLayout layout, bool globalKick)
            {
                laneLayout = layout;
                useGlobalKick = globalKick;
                rebuildMarkers(beatmap);
            }

            public void SetLaneLayout(LaneLayout layout)
            {
                laneLayout = layout;
            }

            public void SetKickMode(bool globalKick)
            {
                useGlobalKick = globalKick;
            }

            public void SetViewMode(LaneViewMode mode)
            {
                viewMode = mode;
            }

            public void UpdateState(double currentTime, float drawWidth, float drawHeight, float spawnTop, float hitLineY, float travelDistance, float laneWidth, int totalLanes, int visibleLanes, int kickLaneIndex, LaneViewMode mode, bool kickGlobal)
            {
                if (markers.Count == 0 || drawWidth <= 0 || travelDistance <= 0)
                {
                    deactivateLines(0);
                    return;
                }

                viewMode = mode;
                useGlobalKick = kickGlobal;
                _ = laneWidth;
                _ = totalLanes;
                _ = visibleLanes;
                _ = kickLaneIndex;
                _ = spawnTop;

                double previewWindow = GameplayPlayfield.approachDuration * previewMultiplier;
                double cutoffPast = -pastAllowance;

                int activeCount = 0;
                foreach (var marker in markers)
                {
                    double delta = marker.Time - currentTime;
                    if (delta < cutoffPast)
                        continue;

                    if (delta > previewWindow)
                        break;

                    float progress = (float)(1 - (delta / GameplayPlayfield.approachDuration));
                    float clampedProgress = Math.Clamp(progress, 0f, 1.1f);
                    float y = hitLineY - travelDistance * (1 - clampedProgress);
                    y = Math.Clamp(y, spawnTop, hitLineY + 32f);

                    var line = getLine(activeCount++);
                    line.UpdateVisual(drawHeight, y, marker.Type, viewMode);
                }

                deactivateLines(activeCount);
            }

            private void deactivateLines(int activeLineCount)
            {
                for (int i = activeLineCount; i < lineBuffer.Count; i++)
                    lineBuffer[i].Deactivate();
            }

            private DrawableGridLine getLine(int index)
            {
                while (lineBuffer.Count <= index)
                {
                    var line = new DrawableGridLine();
                    line.Alpha = 0;
                    lineBuffer.Add(line);
                    AddInternal(line);
                }

                return lineBuffer[index];
            }

            private void rebuildMarkers(Beatmap beatmap)
            {
                markers.Clear();

                if (beatmap == null)
                    return;

                double endTime = beatmap.HitObjects.Count > 0
                    ? beatmap.HitObjects[^1].Time + 8000
                    : 180000;

                double offset = beatmap.Timing?.Offset ?? 0;
                double bpm = beatmap.Timing?.Bpm ?? 120;
                string signature = beatmap.Timing?.TimeSignature ?? "4/4";

                var timingPoints = beatmap.Timing?.TimingPoints
                    ?.OrderBy(tp => tp.Time)
                    .ToList() ?? new List<TimingPoint>();

                double segmentStart = offset;
                double currentBpm = bpm;
                string currentSignature = signature;

                foreach (var timingPoint in timingPoints)
                {
                    double segmentEnd = Math.Max(segmentStart, timingPoint.Time);
                    emitMarkers(segmentStart, segmentEnd, currentBpm, currentSignature);

                    segmentStart = Math.Max(segmentStart, timingPoint.Time);
                    if (timingPoint.Bpm > 0)
                        currentBpm = timingPoint.Bpm;
                    if (!string.IsNullOrWhiteSpace(timingPoint.TimeSignature))
                        currentSignature = timingPoint.TimeSignature!;
                }

                emitMarkers(segmentStart, endTime, currentBpm, currentSignature);
            }

            private void emitMarkers(double startTime, double endTime, double bpm, string signature)
            {
                if (bpm <= 0)
                    bpm = 120;

                var (beatsPerMeasure, beatUnit) = parseSignature(signature);
                double beatLength = 60000.0 / bpm;
                double measureLength = beatLength * beatsPerMeasure;

                if (measureLength <= 0)
                    return;

                double time = startTime;
                if (time < 0)
                    time = 0;

                // ensure we align to measure boundaries
                if (beatLength > 0)
                {
                    double remainder = (time - startTime) % beatLength;
                    if (remainder != 0)
                        time += beatLength - remainder;
                }

                while (time <= endTime && markers.Count < 20000)
                {
                    for (int beat = 0; beat < beatsPerMeasure && time <= endTime; beat++)
                    {
                        markers.Add(new GridMarker(time, beat == 0 ? GridMarkerType.Measure : GridMarkerType.Beat));

                        int subdivisions = beatUnit switch
                        {
                            4 => 4,
                            8 => 3,
                            16 => 2,
                            _ => 2
                        };

                        double subdivisionLength = beatLength / subdivisions;
                        if (subdivisionLength >= 45)
                        {
                            for (int s = 1; s < subdivisions; s++)
                            {
                                double subTime = time + subdivisionLength * s;
                                if (subTime > endTime)
                                    break;

                                markers.Add(new GridMarker(subTime, GridMarkerType.Subdivision));
                            }
                        }

                        time += beatLength;
                    }
                }
            }

            private static (int beatsPerMeasure, int beatUnit) parseSignature(string signature)
            {
                if (string.IsNullOrWhiteSpace(signature))
                    return (4, 4);

                var parts = signature.Split('/');
                if (parts.Length != 2)
                    return (4, 4);

                if (!int.TryParse(parts[0], out int beats))
                    beats = 4;
                if (!int.TryParse(parts[1], out int unit))
                    unit = 4;

                beats = Math.Clamp(beats, 1, 16);
                unit = unit switch
                {
                    1 or 2 or 4 or 8 or 16 or 32 => unit,
                    _ => 4
                };

                return (beats, unit);
            }

            private readonly struct GridMarker
            {
                public GridMarker(double time, GridMarkerType type)
                {
                    Time = time;
                    Type = type;
                }

                public double Time { get; }
                public GridMarkerType Type { get; }
            }

            private enum GridMarkerType
            {
                Measure,
                Beat,
                Subdivision
            }

            private sealed partial class DrawableGridLine : CompositeDrawable
            {
                private readonly Box line;
                private readonly Box glow;

                public DrawableGridLine()
                {
                    RelativeSizeAxes = Axes.X;
                    Anchor = Anchor.BottomCentre;
                    Origin = Anchor.BottomCentre;
                    Height = 2;
                    AlwaysPresent = true;

                    line = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(255, 255, 255, 180)
                    };

                    glow = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Alpha = 0.25f,
                        Blending = BlendingParameters.Additive
                    };

                    InternalChildren = new Drawable[]
                    {
                        glow,
                        line
                    };
                }

                public void UpdateVisual(float drawHeight, float absoluteY, GridMarkerType type, LaneViewMode mode)
                {
                    float offset = Math.Max(0, drawHeight - absoluteY);
                    Y = -offset;

                    float thickness = type switch
                    {
                        GridMarkerType.Measure => 6f,
                        GridMarkerType.Beat => 3f,
                        _ => 2f
                    };

                    Height = thickness;

                    float widthFactor = mode == LaneViewMode.ThreeDimensional ? 0.9f : 0.96f;
                    Width = widthFactor;
                    Shear = mode == LaneViewMode.ThreeDimensional ? new Vector2(-0.24f, 0) : Vector2.Zero;

                    Color4 lineColour = type switch
                    {
                        GridMarkerType.Measure => new Color4(255, 216, 180, 235),
                        GridMarkerType.Beat => new Color4(186, 205, 255, 220),
                        _ => new Color4(120, 132, 182, 180)
                    };

                    float targetAlpha = type switch
                    {
                        GridMarkerType.Measure => 0.82f,
                        GridMarkerType.Beat => 0.58f,
                        _ => 0.36f
                    };

                    line.Colour = lineColour;
                    glow.Colour = UITheme.Emphasise(lineColour, 1.25f);
                    glow.Alpha = targetAlpha * 0.4f;
                    this.FadeTo(targetAlpha, 80, Easing.OutQuint);
                }

                public void Deactivate()
                {
                    this.FadeOut(140, Easing.OutQuint);
                }
            }
        }

        private partial class KickGuideLine : Container
        {
            private const float minLineHeight = 18f;
            private const float maxLineHeight = 48f;
            private float currentLineHeight = 26f;
            private readonly Box glowFill;
            private readonly Box pulseOverlay;
            private readonly Box sweepHighlight;
            private readonly Box ambientGlow;
            private readonly Container lineContainer;
            private double lastPulseTime;
            private float baselineCentre;

            public KickGuideLine()
            {
                RelativeSizeAxes = Axes.Both;

                ambientGlow = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = currentLineHeight * 3.6f,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.Centre,
                    Colour = UITheme.KickGlobalGlow,
                    Alpha = 0f,
                    Blending = BlendingParameters.Additive
                };

                lineContainer = new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Height = currentLineHeight,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.Centre,
                    Masking = true,
                    CornerRadius = Math.Clamp(currentLineHeight / 2f, 10f, 18f),
                    Alpha = 0f,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Glow,
                        Colour = UITheme.Emphasise(UITheme.KickGlobalGlow, 1.2f),
                        Radius = 14,
                        Roundness = 1.4f
                    }
                };

                var baseFill = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientVertical(
                        UITheme.Emphasise(UITheme.KickGlobalFill, 1.08f),
                        UITheme.Emphasise(UITheme.KickGlobalFill, 0.82f))
                };

                glowFill = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.KickGlobalGlow,
                    Alpha = 0f,
                    Blending = BlendingParameters.Additive
                };

                sweepHighlight = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 0.12f,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                    RelativePositionAxes = Axes.X,
                    Colour = new Color4(240, 220, 255, 140),
                    Alpha = 0.42f,
                    Blending = BlendingParameters.Additive
                };

                var topEdge = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 3,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = UITheme.Emphasise(UITheme.KickGlobalGlow, 1.38f)
                };

                var bottomEdge = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 4,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = UITheme.Emphasise(UITheme.KickGlobalFill, 0.9f)
                };

                pulseOverlay = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Emphasise(UITheme.KickGlobalGlow, 1.18f),
                    Alpha = 0,
                    Blending = BlendingParameters.Additive
                };

                lineContainer.AddRange(new Drawable[]
                {
                    baseFill,
                    glowFill,
                    topEdge,
                    bottomEdge,
                    pulseOverlay,
                    sweepHighlight
                });

                InternalChildren = new Drawable[]
                {
                    ambientGlow,
                    lineContainer
                };

                baselineCentre = currentLineHeight / 2f;
                applyBaselineOffset();
                sweepHighlight.X = -0.22f;
            }

            protected override void LoadComplete()
            {
                base.LoadComplete();

                sweepHighlight.ClearTransforms();
                sweepHighlight.MoveToX(-0.22f)
                    .Loop(sequence => sequence
                        .MoveToX(1.18f, 2800, Easing.InOutSine)
                        .Then()
                        .MoveToX(-0.22f)
                        .Delay(240));
            }

            public void ResetVisuals()
            {
                pulseOverlay.FinishTransforms(true);
                pulseOverlay.Alpha = 0;
                glowFill.Alpha = 0f;
                lineContainer.Alpha = 0f;
                ambientGlow.Alpha = 0f;
                lastPulseTime = double.NegativeInfinity;
            }

            public void UpdateBaseline(float viewportHeight, float hitLineY, float strikeZoneHeight)
            {
                if (viewportHeight <= 0 || float.IsNaN(viewportHeight) || float.IsInfinity(viewportHeight))
                    return;

                float targetHeight = strikeZoneHeight > 0
                    ? Math.Clamp(strikeZoneHeight * 0.9f, minLineHeight, maxLineHeight)
                    : Math.Clamp(viewportHeight * 0.038f, minLineHeight, maxLineHeight);

                if (Math.Abs(targetHeight - currentLineHeight) > 0.5f)
                    applyLineHeight(targetHeight);

                float maxCentre = Math.Max(currentLineHeight / 2f, viewportHeight - currentLineHeight / 2f);
                float desiredCentre = Math.Clamp(hitLineY, currentLineHeight / 2f, maxCentre);

                if (Math.Abs(desiredCentre - baselineCentre) <= 0.5f)
                    return;

                baselineCentre = desiredCentre;
                applyBaselineOffset();
            }

            public void UpdateKickNotes(IEnumerable<DrawableNote> kickNotes, double currentTime, float drawHeight, double approachDuration)
            {
                if (approachDuration <= 0)
                {
                    ResetVisuals();
                    return;
                }

                double nearestFuture = double.MaxValue;
                double nearestPast = double.MaxValue;

                foreach (var note in kickNotes)
                {
                    if (note == null)
                        continue;

                    double delta = note.HitTime - currentTime;
                    if (delta >= 0)
                        nearestFuture = Math.Min(nearestFuture, delta);
                    else
                        nearestPast = Math.Min(nearestPast, -delta);
                }

                double previewRange = Math.Max(approachDuration * 1.2, 260);
                double intensity = 0;

                if (nearestFuture < double.MaxValue)
                    intensity = Math.Max(intensity, 1 - Math.Clamp(nearestFuture / previewRange, 0, 1));

                if (nearestPast < double.MaxValue)
                    intensity = Math.Max(intensity, Math.Clamp(1 - nearestPast / 200.0, 0, 1));

                float targetGlow = Math.Clamp((float)intensity * 0.6f, 0f, 0.6f);
                glowFill.FadeTo(targetGlow, 90, Easing.OutQuint);

                float targetLineAlpha = (float)Math.Clamp(intensity * 0.9f, 0f, 0.85f);
                lineContainer.FadeTo(targetLineAlpha, 90, Easing.OutQuint);
                ambientGlow.FadeTo(Math.Clamp((float)intensity * 0.55f, 0f, 0.6f), 120, Easing.OutQuint);

                if (intensity > 0.65 && currentTime - lastPulseTime > 160)
                {
                    lastPulseTime = currentTime;
                    pulseOverlay.FinishTransforms(true);
                    pulseOverlay.Alpha = 0;
                    pulseOverlay.Scale = Vector2.One;
                    pulseOverlay.FadeTo(0.78f, 70, Easing.OutQuint)
                        .ScaleTo(new Vector2(1.05f, 1.4f), 280, Easing.OutQuint)
                        .Then()
                        .FadeOut(280, Easing.OutQuint);
                }
            }

            private void applyBaselineOffset()
            {
                lineContainer.Y = baselineCentre;
                ambientGlow.Y = baselineCentre;
            }

            private void applyLineHeight(float height)
            {
                currentLineHeight = height;
                lineContainer.Height = height;
                lineContainer.CornerRadius = Math.Clamp(height / 2f, 10f, 20f);
                ambientGlow.Height = Math.Clamp(height * 3.6f, height + 24f, height * 4.4f);
            }
        }

        private partial class ThreeDHighwayBackground : CompositeDrawable
        {
            private readonly LaneLayout laneLayout;
            private readonly bool kickLaneSuppressed;
            private int laneCount => Math.Max(1, laneLayout.LaneCount);
            private int visibleLaneCount => Math.Max(1, laneOrder.Count);
            private readonly List<Box> timelineStripes = new List<Box>();
            private readonly List<float> timelineStripeDepth = new List<float>();
            private readonly List<Box> lanePulseLights = new List<Box>();
            private readonly List<float> lanePulseOffsets = new List<float>();
            private Box? horizonGlow;
            private Box? specularSweep;
            private Container? kickGuideBand;
            private Container? kickPulseContainer;
            private readonly Dictionary<DrawableNote, KickPulse> activeKickPulses = new Dictionary<DrawableNote, KickPulse>();
            private readonly Stack<KickPulse> kickPulsePool = new Stack<KickPulse>();
            private readonly List<DrawableNote> kickPulseFrameNotes = new List<DrawableNote>();
            private readonly List<DrawableNote> kickPulseRemovalBuffer = new List<DrawableNote>();
            private readonly List<int> laneOrder = new List<int>();
            private static readonly Color4[] laneAccentPalette =
            {
                new Color4(108, 209, 255, 255),
                new Color4(255, 164, 196, 255),
                new Color4(255, 228, 138, 255),
                new Color4(154, 236, 196, 255),
                new Color4(255, 182, 128, 255)
            };

            public ThreeDHighwayBackground(LaneLayout layout, bool suppressKickLane)
            {
                laneLayout = layout ?? throw new ArgumentNullException(nameof(layout));
                kickLaneSuppressed = suppressKickLane;
                RelativeSizeAxes = Axes.Both;
                Masking = true;
                CornerRadius = 18;

                for (int lane = 0; lane < laneLayout.LaneCount; lane++)
                {
                    if (kickLaneSuppressed && lane == laneLayout.KickLane)
                        continue;

                    laneOrder.Add(lane);
                }

                if (laneOrder.Count == 0)
                    laneOrder.Add(laneLayout.KickLane);
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                lanePulseLights.Clear();
                lanePulseOffsets.Clear();

                var baseLayer = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Background
                };

                horizonGlow = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 220,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = new Color4(255, 214, 170, 90),
                    Alpha = 0.24f
                };

                var topGradient = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 260,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(118, 156, 255, 40),
                        UITheme.Emphasise(UITheme.BackgroundLayer, 0.92f))
                };

                specularSweep = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 120,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    RelativePositionAxes = Axes.X,
                    X = -0.45f,
                    Colour = new Color4(255, 255, 255, 60),
                    Alpha = 0.22f,
                    Blending = BlendingParameters.Additive,
                    Shear = new Vector2(-0.3f, 0)
                };

                var depthFog = createDepthFogLayer();

                var lowerGlow = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 160,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(255, 215, 180, 60),
                        UITheme.Surface)
                };

                var leftRail = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 8,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Colour = UITheme.GetLaneEdgeColour(0, visibleLaneCount),
                    Alpha = 0.52f
                };

                var rightRail = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 8,
                    Anchor = Anchor.BottomRight,
                    Origin = Anchor.BottomRight,
                    Colour = UITheme.GetLaneEdgeColour(1, visibleLaneCount),
                    Alpha = 0.52f
                };

                var layers = new List<Drawable>
                {
                    baseLayer,
                    horizonGlow,
                    topGradient,
                    createLaneSurfaceLayer(),
                    createLaneSeparatorLayer(),
                    createKickGuideLayer(),
                    createTimelineStripeLayer(),
                    depthFog,
                    specularSweep,
                    lowerGlow,
                    leftRail,
                    rightRail
                };

                InternalChildren = layers.ToArray();
            }

            public void SetKickGuideVisible(bool visible)
            {
                if (kickGuideBand == null)
                    return;

                kickGuideBand.FadeTo(visible ? 1f : 0f, 180, Easing.OutQuint);
                kickPulseContainer?.FadeTo(visible ? 1f : 0f, 180, Easing.OutQuint);
            }

            public void ResetKickTimeline()
            {
                kickPulseFrameNotes.Clear();
                kickPulseRemovalBuffer.Clear();

                foreach (var kvp in activeKickPulses)
                    kickPulseRemovalBuffer.Add(kvp.Key);

                foreach (var note in kickPulseRemovalBuffer)
                    releasePulse(note);

                kickPulseRemovalBuffer.Clear();
                kickPulseFrameNotes.Clear();
            }

            public void UpdateKickTimeline(IEnumerable<DrawableNote> kickNotes, double currentTime, double approachDuration)
            {
                if (kickGuideBand == null || kickPulseContainer == null || approachDuration <= 0)
                    return;

                kickPulseFrameNotes.Clear();

                DrawableNote? primaryNote = null;
                double closestFuture = double.MaxValue;

                const double previewMultiplier = 1.4;
                const double pastRange = 220;
                double previewRange = Math.Max(approachDuration * previewMultiplier, 300);
                double window = previewRange + pastRange;

                foreach (var note in kickNotes)
                {
                    if (note == null)
                        continue;

                    kickPulseFrameNotes.Add(note);

                    double timeUntil = note.HitTime - currentTime;
                    if (timeUntil >= 0 && timeUntil < closestFuture)
                    {
                        closestFuture = timeUntil;
                        primaryNote = note;
                    }

                    var pulse = getOrCreatePulse(note);
                    pulse.UpdateVisual(timeUntil, previewRange, pastRange, window, note == primaryNote);
                }

                kickPulseRemovalBuffer.Clear();
                foreach (var existing in activeKickPulses.Keys)
                {
                    if (!kickPulseFrameNotes.Contains(existing))
                        kickPulseRemovalBuffer.Add(existing);
                }

                foreach (var note in kickPulseRemovalBuffer)
                    releasePulse(note);

                kickPulseFrameNotes.Clear();
                kickPulseRemovalBuffer.Clear();
            }

            protected override void LoadComplete()
            {
                base.LoadComplete();

                horizonGlow?.Loop(sequence => sequence
                    .FadeTo(0.35f, 1200, Easing.InOutSine)
                    .Then()
                    .FadeTo(0.18f, 1200, Easing.InOutSine));

                specularSweep?.Loop(sequence => sequence
                    .MoveToX(0.45f, 2600, Easing.InOutSine)
                    .Then()
                    .MoveToX(-0.45f, 2600, Easing.InOutSine));
            }

            private Drawable createLaneSurfaceLayer()
            {
                var container = new Container
                {
                    RelativeSizeAxes = Axes.Both
                };

                float laneWidthFactor = Math.Clamp(0.68f / Math.Max(1, visibleLaneCount), 0.08f, 0.18f);

                for (int index = 0; index < laneOrder.Count; index++)
                {
                    float normalized = visibleLaneCount <= 1
                        ? 0
                        : (index - (visibleLaneCount - 1) / 2f) / Math.Max(1, visibleLaneCount - 1);

                    var accentColour = laneAccentPalette[index % laneAccentPalette.Length];

                    var laneSurface = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        RelativePositionAxes = Axes.X,
                        X = normalized * 0.62f,
                        Width = laneWidthFactor,
                        Height = 0.96f,
                        Shear = new Vector2(-0.26f, 0),
                        Padding = new MarginPadding { Bottom = 18 }
                    };

                    var laneTopColour = UITheme.Emphasise(accentColour, 1.28f);
                    var laneBottomColour = UITheme.Emphasise(UITheme.Surface, 0.88f);

                    laneSurface.Add(new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = ColourInfo.GradientVertical(laneTopColour, laneBottomColour)
                    });

                    laneSurface.Add(new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 8,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Colour = UITheme.Emphasise(accentColour, 1.55f),
                        Alpha = 0.7f
                    });

                    var glow = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Emphasise(accentColour, 1.42f),
                        Alpha = 0,
                        Blending = BlendingParameters.Additive
                    };

                    laneSurface.Add(glow);
                    lanePulseLights.Add(glow);
                    lanePulseOffsets.Add(normalized);

                    container.Add(laneSurface);
                }

                return container;
            }

            private Drawable createDepthFogLayer()
            {
                return new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(0, 0, 0, 0),
                        UITheme.Emphasise(UITheme.BackgroundLayer, 0.78f)),
                    Alpha = 0.68f
                };
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
                    Colour = UITheme.SurfaceAlt,
                    Alpha = 0.52f
                });

                for (int index = 0; index < laneOrder.Count; index++)
                {
                    float normalized = visibleLaneCount <= 1
                        ? 0
                        : (index - (visibleLaneCount - 1) / 2f) / Math.Max(1, visibleLaneCount - 1);

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
                        Colour = UITheme.Emphasise(UITheme.GetLaneEdgeColour(index, visibleLaneCount), 1.05f),
                        Alpha = 0.42f
                    });
                }

                return container;
            }

            private Drawable createKickGuideLayer()
            {
                kickPulseContainer = null;

                if (kickLaneSuppressed)
                {
                    kickGuideBand = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Width = 0.96f,
                        Height = 72,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Y = -42,
                        Shear = new Vector2(-0.25f, 0),
                        Masking = true,
                        CornerRadius = 16,
                        EdgeEffect = new EdgeEffectParameters
                        {
                            Type = EdgeEffectType.Glow,
                            Colour = new Color4(120, 90, 200, 80),
                            Radius = 12,
                            Roundness = 2.4f
                        }
                    };

                    kickGuideBand.Add(new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = ColourInfo.GradientVertical(
                            new Color4(120, 90, 200, 140),
                            new Color4(42, 28, 86, 235))
                    });

                    kickPulseContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both
                    };

                    kickGuideBand.Add(kickPulseContainer);

                    kickGuideBand.Add(new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Width = 1f,
                        Height = 6,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Colour = new Color4(220, 200, 255, 210)
                    });

                    for (int i = 1; i <= 6; i++)
                    {
                        kickGuideBand.Add(new Box
                        {
                            RelativeSizeAxes = Axes.X,
                            Width = 1f,
                            Height = 3,
                            Anchor = Anchor.BottomCentre,
                            Origin = Anchor.BottomCentre,
                            Y = -i * 10,
                            Colour = new Color4(150, 120, 220, 150)
                        });
                    }
                }
                else
                {
                    kickPulseContainer = null;

                    float kickNormalized = laneCount <= 1
                        ? 0
                        : (laneLayout.KickLane - (laneCount - 1) / 2f) / (laneCount - 1);

                    kickGuideBand = new Container
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

                    kickGuideBand.Add(new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(80, 60, 110, 160)
                    });

                    for (int i = 0; i < 6; i++)
                    {
                        kickGuideBand.Add(new Box
                        {
                            RelativeSizeAxes = Axes.X,
                            Width = 1f,
                            Height = 3,
                            Anchor = Anchor.BottomCentre,
                            Origin = Anchor.BottomCentre,
                            Y = -i * 14,
                            Colour = new Color4(200, 170, 240, 180)
                        });
                    }

                    kickGuideBand.Add(new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Width = 1f,
                        Height = 4,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Colour = new Color4(230, 210, 255, 220)
                    });
                }

                kickGuideBand.Alpha = 0;
                return kickGuideBand;
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
                    timelineStripeDepth.Add(depth);
                }

                return stripeLayer;
            }

            private KickPulse getOrCreatePulse(DrawableNote note)
            {
                if (activeKickPulses.TryGetValue(note, out var existing))
                    return existing;

                var pulse = kickPulsePool.Count > 0 ? kickPulsePool.Pop() : new KickPulse();

                if (pulse.Parent != kickPulseContainer && kickPulseContainer != null)
                    kickPulseContainer.Add(pulse);

                pulse.ResetState();
                pulse.Note = note;
                activeKickPulses[note] = pulse;
                return pulse;
            }

            private void releasePulse(DrawableNote note)
            {
                if (!activeKickPulses.TryGetValue(note, out var pulse))
                    return;

                activeKickPulses.Remove(note);

                if (pulse.Parent == kickPulseContainer)
                    kickPulseContainer?.Remove(pulse, false);

                pulse.ResetState();
                pulse.Note = null;
                kickPulsePool.Push(pulse);
            }

            public void UpdateScroll(double currentTime)
            {
                if (DrawHeight <= 0)
                    return;

                if (timelineStripes.Count > 0)
                {
                    float baseOffset = (float)((currentTime * 0.0006) % 1.0);

                    for (int i = 0; i < timelineStripes.Count; i++)
                    {
                        float offset = (i / (float)timelineStripes.Count) + baseOffset;
                        offset -= MathF.Floor(offset);
                        float depth = timelineStripeDepth[i];
                        float parallax = 0.65f + depth * 0.45f;
                        float y = -offset * DrawHeight * parallax;
                        var stripe = timelineStripes[i];
                        stripe.Y = y;
                        stripe.Scale = new Vector2(parallax, 1);
                        stripe.Alpha = 0.25f + depth * 0.45f;
                    }
                }

                if (lanePulseLights.Count > 0)
                {
                    for (int i = 0; i < lanePulseLights.Count; i++)
                    {
                        var glow = lanePulseLights[i];
                        float offset = lanePulseOffsets.Count > i ? lanePulseOffsets[i] : 0;
                        float wave = (float)Math.Sin(currentTime * 0.002 + offset * MathF.PI);
                        float intensity = 0.18f + MathF.Max(0, wave) * 0.32f;
                        glow.Alpha = intensity;
                        glow.Scale = new Vector2(1f, 1.05f + MathF.Max(0, (float)Math.Sin(currentTime * 0.003 + offset * 2)) * 0.08f);
                    }
                }
            }

            private sealed partial class KickPulse : CompositeDrawable
            {
                private readonly Container body;
                private readonly Box fill;
                private readonly Box highlight;
                private readonly Box glow;

                public DrawableNote? Note { get; set; }

                public KickPulse()
                {
                    RelativeSizeAxes = Axes.X;
                    Width = 0.96f;
                    Height = 26;
                    Anchor = Anchor.BottomCentre;
                    Origin = Anchor.Centre;
                    RelativePositionAxes = Axes.Y;
                    AlwaysPresent = true;
                    Alpha = 0;

                    glow = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Alpha = 0,
                        Blending = BlendingParameters.Additive
                    };

                    body = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Masking = true,
                        CornerRadius = 12
                    };

                    fill = new Box { RelativeSizeAxes = Axes.Both };
                    body.Add(fill);

                    highlight = new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 4,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Alpha = 0.5f
                    };
                    body.Add(highlight);

                    InternalChildren = new Drawable[]
                    {
                        glow,
                        body
                    };
                }

                public void ResetState()
                {
                    ClearTransforms();
                    Alpha = 0;
                    Scale = Vector2.One;
                    Y = 0;
                }

                public void UpdateVisual(double timeUntil, double previewRange, double pastRange, double window, bool emphasise)
                {
                    double clamped = Math.Clamp(timeUntil, -pastRange, previewRange);
                    float progress = (float)((previewRange - clamped) / Math.Max(1, window));
                    float travel = 0.88f;
                    Y = -Math.Clamp(progress, 0f, 1f) * travel;

                    float closeness = 1f - (float)Math.Clamp(Math.Abs(timeUntil) / Math.Max(1, previewRange * 0.55 + pastRange), 0, 1);
                    float scaleBase = emphasise ? 0.65f : 0.5f;
                    float widthScale = 0.95f + closeness * 0.08f;
                    float heightScale = 0.55f + closeness * (0.45f + scaleBase * 0.18f);
                    Scale = new Vector2(widthScale, heightScale);

                    float targetAlpha = Math.Clamp(0.25f + progress * (emphasise ? 0.55f : 0.4f), 0f, 1f);
                    Alpha = targetAlpha;

                    var accent = Note?.AccentColour ?? new Color4(186, 145, 255, 255);
                    var baseColour = adjust(accent, emphasise ? 1.2 : 1.08);
                    fill.Colour = ColourInfo.GradientHorizontal(adjust(baseColour, 1.24), adjust(baseColour, 0.76));
                    highlight.Colour = adjust(baseColour, emphasise ? 1.34 : 1.18);
                    glow.Colour = adjust(accent, emphasise ? 1.65 : 1.4);
                    glow.Alpha = 0.2f + closeness * (emphasise ? 0.36f : 0.26f);
                }

                private static Color4 adjust(Color4 colour, double factor)
                {
                    return new Color4(
                        (float)Math.Clamp(colour.R * factor, 0f, 1f),
                        (float)Math.Clamp(colour.G * factor, 0f, 1f),
                        (float)Math.Clamp(colour.B * factor, 0f, 1f),
                        colour.A);
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
            {"kick", new Color4(186, 145, 255, 255)},
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
        public int Lane { get; private set; }
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
        private readonly int originalLane;
        private bool kickGlobalMode;
        private float lastAppliedDepth = float.NaN;

        public DrawableNote(HitObject hitObject, int lane, Bindable<bool> showApproach, Bindable<bool> showGlow, Bindable<bool> showParticles)
        {
            HitTime = hitObject.Time;
            ComponentName = hitObject.Component;
            Lane = lane;
            originalLane = lane;
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
                    Alpha = 0.7f, // Slightly more transparent to reduce overlap visual issues
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
            // Only start if the note hasn't been judged yet
            if (!IsJudged && showGlowEffects.Value && glowBox != null)
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
                mainBox.Shear = Vector2.Zero;
                if (isKickNote && kickGlobalMode)
                {
                    float assumedHeight = Height > 0 ? Height : 18f;
                    CornerRadius = Math.Min(assumedHeight / 2f, 9f);
                    highlightStrip.Anchor = Anchor.Centre;
                    highlightStrip.Origin = Anchor.Centre;
                    highlightStrip.Width = 1f;
                    highlightStrip.Height = Math.Clamp(assumedHeight * 0.3f, 3f, 8f);
                    highlightStrip.Alpha = 0.55f;
                    highlightStrip.Y = -assumedHeight * 0.1f;
                    highlightStrip.Colour = new Color4(255, 244, 255, 180);
                    if (glowBox != null)
                        glowBox.Alpha = 0.4f;
                    return;
                }

                CornerRadius = 8;
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
                mainBox.Shear = new Vector2(-0.25f, 0);
                if (isKickNote && kickGlobalMode)
                {
                    float assumedHeight = Height > 0 ? Height : 18f;
                    CornerRadius = Math.Min(assumedHeight / 2.2f, 10f);
                    highlightStrip.Anchor = Anchor.Centre;
                    highlightStrip.Origin = Anchor.Centre;
                    highlightStrip.Width = 1f;
                    highlightStrip.Height = Math.Clamp(assumedHeight * 0.24f, 2f, 6f);
                    highlightStrip.Alpha = 0.6f;
                    highlightStrip.Y = -assumedHeight * 0.14f;
                    highlightStrip.Colour = new Color4(255, 230, 210, 210);
                    if (glowBox != null)
                        glowBox.Alpha = 0.5f;
                    return;
                }

                CornerRadius = 4;
                Size = isKickNote ? new Vector2(88, 20) : new Vector2(74, 24);
                highlightStrip.Alpha = 0.6f;
                highlightStrip.Width = isKickNote ? 1f : 0.9f;
                highlightStrip.Height = isKickNote ? 3 : 5;
                highlightStrip.Colour = isKickNote
                    ? new Color4(255, 220, 180, 200)
                    : new Color4(255, 255, 255, 130);
                highlightStrip.Anchor = Anchor.TopCentre;
                highlightStrip.Origin = Anchor.TopCentre;
            }
        }

        public void ApplyKickMode(bool useGlobalLine, int globalLane)
        {
            if (!isKickNote)
                return;

            kickGlobalMode = useGlobalLine;
            Lane = useGlobalLine ? globalLane : originalLane;

            // Refresh geometry to reflect the new presentation.
            SetViewMode(viewMode);
        }

        public void SetApproachProgress(float progress) => approachProgress = Math.Clamp(progress, 0f, 1f);

        public void ApplyKickLineDimensions(float width, float height, LaneViewMode mode)
        {
            if (!isKickNote || !kickGlobalMode)
                return;

            Width = width;
            Height = height;

            if (mode == LaneViewMode.TwoDimensional)
            {
                CornerRadius = Math.Min(height / 2f, 9f);
                highlightStrip.Anchor = Anchor.Centre;
                highlightStrip.Origin = Anchor.Centre;
                highlightStrip.Width = 1f;
                highlightStrip.Height = Math.Clamp(height * 0.32f, 3f, 8f);
                highlightStrip.Y = -height * 0.1f;
                highlightStrip.Alpha = 0.58f;
                highlightStrip.Colour = new Color4(255, 244, 255, 190);
                if (glowBox != null)
                    glowBox.Alpha = 0.42f;
            }
            else
            {
                CornerRadius = Math.Min(height / 2.4f, 11f);
                highlightStrip.Anchor = Anchor.Centre;
                highlightStrip.Origin = Anchor.Centre;
                highlightStrip.Width = 1f;
                highlightStrip.Height = Math.Clamp(height * 0.26f, 2f, 6f);
                highlightStrip.Y = -height * 0.16f;
                highlightStrip.Alpha = 0.64f;
                highlightStrip.Colour = new Color4(255, 228, 205, 210);
                if (glowBox != null)
                    glowBox.Alpha = 0.5f;
            }
        }

        internal bool ShouldUpdateDepth(float targetDepth, float tolerance)
        {
            if (float.IsNaN(lastAppliedDepth) || Math.Abs(lastAppliedDepth - targetDepth) >= tolerance)
            {
                lastAppliedDepth = targetDepth;
                return true;
            }

            return false;
        }

        public void ApplyResult(GameplayPlayfield.HitResult result)
        {
            if (IsJudged)
                return;

            IsJudged = true;

            // CRITICAL: Clear all ongoing transformations (including infinite loops) to prevent accumulation
            this.ClearTransforms();
            mainBox?.ClearTransforms();
            highlightStrip?.ClearTransforms();
            glowBox?.ClearTransforms();
            approachCircle?.ClearTransforms();

            // Hide approach circle
            if (showApproachCircles.Value && approachCircle != null)
                approachCircle.FadeOut(100);

            switch (result)
            {
                case GameplayPlayfield.HitResult.Miss:
                    this.FlashColour(new Color4(255, 80, 90, 255), 90, Easing.OutQuint);
                    this.FadeColour(new Color4(120, 20, 30, 200), 120, Easing.OutQuint);
                    this.MoveToY(Y + 18, 160, Easing.OutQuint);
                    this.FadeOut(140, Easing.OutQuint).Expire();
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
