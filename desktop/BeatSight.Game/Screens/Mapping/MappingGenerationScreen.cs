using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.AI.Generation;
using BeatSight.Game.Audio;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.AI;
using BeatSight.Game.Configuration;
using BeatSight.Game.Localization;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Editor;
using BeatSight.Game.Services.Generation;
using BeatSight.Game.UI.Components;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Graphics.Transforms;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osu.Framework.Threading;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Mapping
{
    /// <summary>
    /// Placeholder screen that will host AI-assisted beatmap generation workflows.
    /// </summary>
    public partial class MappingGenerationScreen : Screen
    {
        private readonly ImportedAudioTrack importedTrack;

        private SpriteText statusText = null!;
        private SpriteText summaryText = null!;
        private SpriteText stageLabelText = null!;
        private SpriteText stageProgressText = null!;
        private SpriteText offlineStatusText = null!;
        private Container offlineStatusContainer = null!;
        private Container infoToastContainer = null!;
        private SpriteText infoToastText = null!;
        private BasicButton backButton = null!;
        private BasicButton startButton = null!;
        private BasicButton openInEditorButton = null!;
        private DetectionDebugOverlay debugOverlay = null!;
        private BasicSliderBar<double> sensitivitySlider = null!;
        private BeatSight.Game.UI.Components.Dropdown<QuantizationGridSetting> quantizationDropdown = null!;
        private BasicCheckbox debugOverlayCheckbox = null!;
        private Container progressBarContainer = null!;
        private WeightedProgressBar weightedProgressBar = null!;
        private Container dropdownOverlay = null!;
        private SpriteText heartbeatStatusText = null!;
        private Container warningContainer = null!;
        private SpriteText warningText = null!;
        private Container errorNotificationContainer = null!;
        private SpriteText errorNotificationText = null!;
        private BasicButton copyLogsButton = null!;

        private readonly Bindable<int> detectionSensitivity = new Bindable<int>();
        private readonly Bindable<QuantizationGridSetting> quantizationGrid = new Bindable<QuantizationGridSetting>();
        private readonly Bindable<bool> debugOverlayEnabled = new Bindable<bool>();
        private readonly BindableDouble sensitivityValue = new BindableDouble();
        private readonly Bindable<bool> metronomeEnabled = new Bindable<bool>();
        private readonly Bindable<MetronomeSoundOption> metronomeSound = new Bindable<MetronomeSoundOption>();
        private readonly Bindable<bool> drumStemOnly = new Bindable<bool>();
        private readonly Bindable<NoteSkinOption> noteSkinSelection = new Bindable<NoteSkinOption>();

        private CancellationTokenSource? runCts;
        private Task<GenerationResult>? runTask;
        private AiGenerationResult? lastResult;
        private DetectionStats? currentStats;
        private DrumOnsetAnalysis? latestAnalysis;
        private WaveformData? waveformData;
        private readonly List<string> pipelineLogs = new();
        private bool playbackAvailable = true;
        private bool cancellationRequested;
        private GenerationLaneStats? lastLaneStats;
        private SpriteText sensitivityLockNote = null!;
        private SpriteText debugOverlayNote = null!;
        private BasicButton cancelButton = null!;
        private BasicButton applyButton = null!;
        private BasicButton advancedToggleButton = null!;
        private Container advancedSettingsContainer = null!;
        private FillFlowContainer advancedSettingsBody = null!;
        private FillFlowContainer livePlaybackSettingsContainer = null!;
        private BasicCheckbox metronomeCheckbox = null!;
        private BeatSight.Game.UI.Components.Dropdown<MetronomeSoundOption> metronomeSoundDropdown = null!;
        private BasicCheckbox drumStemCheckbox = null!;
        private BeatSight.Game.UI.Components.Dropdown<NoteSkinOption> noteSkinDropdown = null!;
        private SpriteText livePlaybackStatusText = null!;
        private IReadOnlyDictionary<GenerationStageId, double>? lastStageDurations;
        private string? lastStageDurationSummary;
        private GenerationStageId lastActiveStage = GenerationStageId.ModelLoad;

        private GenerationState currentState = GenerationState.Idle;
        private bool advancedExpanded;
        private bool hasRunAtLeastOnce;
        private bool pendingOptionChange;
        private bool offlineDecodeToastShown;
        private DateTimeOffset? lastProgressUpdate;
        private ScheduledDelegate? heartbeatStatusUpdateDelegate;
        private bool settingsReady;
        private string? lastStageLabelDisplayed;
        private bool detectionStatsToastShown;
        private bool overlayAvailabilityAnnounced;
        private bool confidenceAdviceShown;

        [Resolved]
        private IGenerationCoordinator generationCoordinator { get; set; } = null!;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        [Resolved]
        private Clipboard clipboard { get; set; } = null!;

        public MappingGenerationScreen(ImportedAudioTrack importedTrack)
        {
            this.importedTrack = importedTrack;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            metronomeEnabled.BindTo(config.GetBindable<bool>(BeatSightSetting.MetronomeEnabled));
            metronomeSound.BindTo(config.GetBindable<MetronomeSoundOption>(BeatSightSetting.MetronomeSound));
            drumStemOnly.BindTo(config.GetBindable<bool>(BeatSightSetting.DrumStemPlaybackOnly));
            noteSkinSelection.BindTo(config.GetBindable<NoteSkinOption>(BeatSightSetting.NoteSkin));

            dropdownOverlay = new Container
            {
                RelativeSizeAxes = Axes.Both,
                AlwaysPresent = true,
                // Ensure dropdown menus display above the rest of the configuration UI.
                Depth = -1
            };

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(17, 19, 28, 255)
                },
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Horizontal = 60, Vertical = 40 },
                    Child = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 20),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "AI Beatmap Generation",
                                Font = new FontUsage(size: 36, weight: "Bold"),
                                Colour = Color4.White
                            },
                            createSummaryBox(),
                            createAdvancedSettingsSection(),
                            createLivePlaybackControls(),
                            createStatusArea(),
                            debugOverlay = new DetectionDebugOverlay
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 260,
                                Alpha = 0
                            },
                            startButton = new BasicButton
                            {
                                Text = "Start",
                                RelativeSizeAxes = Axes.X,
                                Height = 48,
                                BackgroundColour = new Color4(90, 155, 110, 255),
                                CornerRadius = 10,
                                Masking = true,
                                Alpha = 1
                            },
                            openInEditorButton = new BasicButton
                            {
                                Text = "Open Draft in Editor",
                                RelativeSizeAxes = Axes.X,
                                Height = 48,
                                BackgroundColour = new Color4(110, 160, 255, 255),
                                CornerRadius = 10,
                                Masking = true,
                                Alpha = 0
                            },
                            applyButton = new BasicButton
                            {
                                Text = "Apply & Re-run",
                                RelativeSizeAxes = Axes.X,
                                Height = 48,
                                BackgroundColour = new Color4(200, 95, 95, 255),
                                CornerRadius = 10,
                                Masking = true,
                                Alpha = 0
                            },
                            cancelButton = new BasicButton
                            {
                                Text = "Cancel",
                                RelativeSizeAxes = Axes.X,
                                Height = 48,
                                BackgroundColour = new Color4(150, 110, 60, 255),
                                CornerRadius = 10,
                                Masking = true,
                                Alpha = 0
                            },
                            backButton = new BasicButton
                            {
                                Text = "Back",
                                RelativeSizeAxes = Axes.X,
                                Height = 48,
                                BackgroundColour = new Color4(70, 75, 95, 255),
                                CornerRadius = 10,
                                Masking = true
                            }
                        }
                    }
                }
            , dropdownOverlay
            };

            startButton.Enabled.Value = true;
            openInEditorButton.Enabled.Value = false;
            applyButton.Enabled.Value = false;
            cancelButton.Enabled.Value = false;

            startButton.Action = () => beginGeneration();
            openInEditorButton.Action = () =>
            {
                if (lastResult?.BeatmapPath != null)
                    this.Push(new EditorScreen(lastResult.BeatmapPath, null, playbackAvailable));
            };

            applyButton.Action = onApplyButton;
            cancelButton.Action = () => cancelGeneration();
            backButton.Action = () =>
            {
                var pending = runTask;
                cancelGeneration();

                if (pending != null)
                {
                    _ = Task.Run(async () =>
                    {
                        try
                        {
                            await Task.WhenAny(pending, Task.Delay(1000)).ConfigureAwait(false);
                        }
                        catch
                        {
                            // ignore cancellation timing exceptions
                        }
                        finally
                        {
                            scheduleToUpdateThread(() => this.Exit());
                        }
                    });
                }
                else
                {
                    this.Exit();
                }
            };

            detectionSensitivity.BindTo(config.GetBindable<int>(BeatSightSetting.DetectionSensitivity));
            quantizationGrid.BindTo(config.GetBindable<QuantizationGridSetting>(BeatSightSetting.DetectionQuantizationGrid));
            debugOverlayEnabled.BindTo(config.GetBindable<bool>(BeatSightSetting.ShowDetectionDebugOverlay));

            debugOverlayEnabled.BindValueChanged(_ =>
            {
                updateDebugOverlayInteractivity();
                updateDebugOverlayVisibility();
            }, true);

            generationCoordinator.Stage.BindValueChanged(onStageChanged, true);
            generationCoordinator.Progress.BindValueChanged(onProgressChanged, true);
            generationCoordinator.Stats.BindValueChanged(onStatsChanged, true);
            generationCoordinator.Analysis.BindValueChanged(onAnalysisChanged, true);
            generationCoordinator.Waveform.BindValueChanged(onWaveformChanged, true);
            generationCoordinator.State.BindValueChanged(e => Scheduler.Add(() => setState(e.NewValue)), true);
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            updateStageDisplay(null, 0, false);
            progressBarContainer.FadeOut(0);
            setState(GenerationState.Idle);
            refreshButtonStates();
            statusText.Text = "Ready to generate. Adjust settings and press Start.";
            setAdvancedExpanded(false, true);
            Scheduler.Add(() => settingsReady = true);
        }

        private Drawable createSummaryBox()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 12,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding(24),
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(23, 25, 36, 255)
                        },
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 6),
                            Children = new Drawable[]
                            {
                                new SpriteText
                                {
                                    Text = importedTrack.DisplayName,
                                    Font = new FontUsage(size: 26, weight: "Medium"),
                                    Colour = Color4.White
                                },
                                new SpriteText
                                {
                                    Text = $"Length: {importedTrack.FormatDuration()} • Size: {importedTrack.FormatFileSize()}",
                                    Font = new FontUsage(size: 18),
                                    Colour = new Color4(180, 185, 205, 255)
                                }
                            }
                        }
                    }
                }
            };
        }

        private Drawable createAdvancedSettingsSection()
        {
            advancedToggleButton = new BasicButton
            {
                Text = "Show advanced settings",
                RelativeSizeAxes = Axes.X,
                Height = 40,
                BackgroundColour = new Color4(40, 45, 60, 255),
                CornerRadius = 10,
                Masking = true
            };
            advancedToggleButton.Action = () => setAdvancedExpanded(!advancedExpanded, false);

            advancedSettingsBody = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 10),
                Children = new Drawable[]
                {
                    createDetectionControls()
                }
            };

            advancedSettingsContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 10,
                AlwaysPresent = true,
                Alpha = 0,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding(18),
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(23, 25, 36, 255)
                        },
                        advancedSettingsBody
                    }
                }
            };
            advancedSettingsContainer.Hide();

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    advancedToggleButton,
                    advancedSettingsContainer
                }
            };
        }

        private Drawable createLivePlaybackControls()
        {
            metronomeCheckbox = new BasicCheckbox
            {
                LabelText = "Metronome"
            };
            metronomeCheckbox.Current.BindTo(metronomeEnabled);

            drumStemCheckbox = new BasicCheckbox
            {
                LabelText = "Drum stem only"
            };
            drumStemCheckbox.Current.BindTo(drumStemOnly);

            metronomeSoundDropdown = new BeatSight.Game.UI.Components.Dropdown<MetronomeSoundOption>
            {
                Width = 200,
                SearchEnabled = true
            };
            metronomeSoundDropdown.OverlayLayer = dropdownOverlay;
            metronomeSoundDropdown.Items = Enum.GetValues<MetronomeSoundOption>();
            metronomeSoundDropdown.Current.BindTo(metronomeSound);

            noteSkinDropdown = new BeatSight.Game.UI.Components.Dropdown<NoteSkinOption>
            {
                Width = 220,
                SearchEnabled = true
            };
            noteSkinDropdown.OverlayLayer = dropdownOverlay;
            noteSkinDropdown.Items = Enum.GetValues<NoteSkinOption>();
            noteSkinDropdown.Current.BindTo(noteSkinSelection);

            livePlaybackStatusText = new SpriteText
            {
                Font = new FontUsage(size: 12),
                Colour = new Color4(170, 200, 240, 255),
                Text = string.Empty
            };

            livePlaybackSettingsContainer = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 10),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = "Live Playback Controls",
                        Font = new FontUsage(size: 22, weight: "Medium"),
                        Colour = new Color4(190, 200, 220, 255)
                    },
                    new SpriteText
                    {
                        Text = "Adjust metronome, drum isolation, and note skin without leaving the workflow.",
                        Font = new FontUsage(size: 14),
                        Colour = new Color4(170, 175, 195, 255)
                    },
                    livePlaybackStatusText,
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(20, 0),
                        Children = new Drawable[]
                        {
                            metronomeCheckbox,
                            drumStemCheckbox
                        }
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(4, 4),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "Metronome Sound",
                                Font = new FontUsage(size: 16),
                                Colour = new Color4(170, 180, 205, 255)
                            },
                            metronomeSoundDropdown
                        }
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(4, 4),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "Note Skin",
                                Font = new FontUsage(size: 16),
                                Colour = new Color4(170, 180, 205, 255)
                            },
                            noteSkinDropdown
                        }
                    }
                }
            };

            updateLivePlaybackInteractivity(true);

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 10,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding(18),
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(23, 25, 36, 255)
                        },
                        livePlaybackSettingsContainer
                    }
                }
            };
        }

        private void setAdvancedExpanded(bool expand, bool immediate)
        {
            if (advancedExpanded == expand)
                return;

            advancedExpanded = expand;

            advancedSettingsContainer.ClearTransforms();

            if (expand)
            {
                advancedSettingsContainer.Show();
                if (immediate)
                {
                    advancedSettingsContainer.Alpha = 1;
                    advancedSettingsContainer.Scale = Vector2.One;
                }
                else
                {
                    advancedSettingsContainer.Scale = new Vector2(1, 0.95f);
                    advancedSettingsContainer.Alpha = 0;
                    advancedSettingsContainer.FadeIn(200, Easing.OutQuint);
                    advancedSettingsContainer.ScaleTo(Vector2.One, 200, Easing.OutQuint);
                }
            }
            else
            {
                if (immediate)
                {
                    advancedSettingsContainer.Hide();
                    advancedSettingsContainer.Alpha = 0;
                    advancedSettingsContainer.Scale = Vector2.One;
                }
                else
                {
                    advancedSettingsContainer.FadeOut(150, Easing.OutQuint);
                    advancedSettingsContainer.ScaleTo(new Vector2(1, 0.95f), 150, Easing.OutQuint)
                        .OnComplete(_ =>
                        {
                            if (!advancedExpanded)
                                advancedSettingsContainer.Hide();
                            advancedSettingsContainer.Scale = Vector2.One;
                        });
                }
            }

            advancedToggleButton.Text = expand ? "Hide advanced settings" : "Show advanced settings";
        }

        private Drawable createDetectionControls()
        {
            sensitivitySlider = new BasicSliderBar<double>
            {
                RelativeSizeAxes = Axes.X,
                Height = 24
            };
            sensitivityValue.MinValue = 0;
            sensitivityValue.MaxValue = 100;
            sensitivitySlider.Current.BindTo(sensitivityValue);

            quantizationDropdown = new BeatSight.Game.UI.Components.Dropdown<QuantizationGridSetting>
            {
                RelativeSizeAxes = Axes.X
            };
            quantizationDropdown.OverlayLayer = dropdownOverlay;
            quantizationDropdown.Items = new[]
            {
                QuantizationGridSetting.Eighth,
                QuantizationGridSetting.Sixteenth,
                QuantizationGridSetting.Triplet,
                QuantizationGridSetting.ThirtySecond,
                QuantizationGridSetting.Quarter
            };

            debugOverlayCheckbox = new BasicCheckbox
            {
                LabelText = "Show Detection Debug Overlay"
            };

            detectionSensitivity.BindValueChanged(e =>
            {
                if (Math.Abs(sensitivityValue.Value - e.NewValue) > 0.01)
                    sensitivityValue.Value = e.NewValue;
            }, true);

            sensitivityValue.BindValueChanged(e =>
            {
                int rounded = (int)Math.Clamp(Math.Round(e.NewValue), 0, 100);
                if (detectionSensitivity.Value != rounded)
                {
                    detectionSensitivity.Value = rounded;
                    handleAdvancedSettingChanged();
                }
            });

            quantizationDropdown.Current.BindTo(quantizationGrid);
            quantizationDropdown.Current.BindValueChanged(_ => handleAdvancedSettingChanged());
            debugOverlayCheckbox.Current.BindTo(debugOverlayEnabled);

            var flow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = "Detection Controls",
                        Font = new FontUsage(size: 22, weight: "Medium"),
                        Colour = new Color4(180, 190, 210, 255)
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 4),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "Detection Sensitivity",
                                Font = new FontUsage(size: 16),
                                Colour = new Color4(170, 180, 205, 255)
                            },
                            sensitivitySlider,
                            sensitivityLockNote = new SpriteText
                            {
                                Text = "Locked while generation is running",
                                Font = new FontUsage(size: 12),
                                Colour = new Color4(210, 110, 110, 255),
                                Alpha = 0
                            }
                        }
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 4),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "Quantization Grid",
                                Font = new FontUsage(size: 16),
                                Colour = new Color4(170, 180, 205, 255)
                            },
                            new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                AutoSizeAxes = Axes.Y,
                                Child = quantizationDropdown
                            }
                        }
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 4),
                        Children = new Drawable[]
                        {
                            debugOverlayCheckbox,
                            debugOverlayNote = new SpriteText
                            {
                                Text = "Available after onset detection",
                                Font = new FontUsage(size: 12),
                                Colour = new Color4(180, 190, 205, 255),
                                Alpha = 1
                            }
                        }
                    }
                }
            };

            flow.Padding = new MarginPadding { Vertical = 10 };

            return flow;
        }

        private Drawable createStatusArea()
        {
            statusText = new SpriteText
            {
                Text = "Preparing analysis pipeline...",
                Font = new FontUsage(size: 20),
                Colour = new Color4(190, 195, 210, 255)
            };

            stageLabelText = new SpriteText
            {
                Text = string.Empty,
                Font = new FontUsage(size: 16),
                Colour = new Color4(140, 180, 255, 255),
                Alpha = 0
            };

            stageProgressText = new SpriteText
            {
                Text = string.Empty,
                Font = new FontUsage(size: 14),
                Colour = new Color4(160, 170, 200, 255),
                Alpha = 0
            };

            summaryText = new SpriteText
            {
                Text = string.Empty,
                Font = new FontUsage(size: 16),
                Colour = new Color4(170, 175, 195, 255),
                Alpha = 0,
                AllowMultiline = true
            };

            var description = new SpriteText
            {
                Text = "The AI workflow will separate drum stems, detect peaks, and draft hit objects aligned with the guitar-hero style lane view.",
                Font = new FontUsage(size: 16),
                Colour = new Color4(170, 175, 195, 255),
                RelativeSizeAxes = Axes.X
            };

            progressBarContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 6,
                CornerRadius = 3,
                Masking = true,
                Alpha = 0,
                Children = new Drawable[]
                {
                    weightedProgressBar = new WeightedProgressBar()
                }
            };

            heartbeatStatusText = new SpriteText
            {
                Text = string.Empty,
                Font = new FontUsage(size: 12),
                Colour = new Color4(150, 155, 175, 255),
                Alpha = 0,
                AllowMultiline = true
            };

            offlineStatusText = new SpriteText
            {
                Text = BeatSightStrings.OfflinePlaybackDisabled,
                Font = new FontUsage(size: 14),
                Colour = new Color4(160, 165, 185, 255)
            };

            offlineStatusContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Alpha = 0,
                Child = offlineStatusText
            };
            offlineStatusContainer.Hide();

            infoToastText = new SpriteText
            {
                Text = string.Empty,
                Font = new FontUsage(size: 15),
                Colour = new Color4(215, 225, 245, 255)
            };

            infoToastContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Alpha = 0,
                Masking = true,
                CornerRadius = 6,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(70, 80, 115, 220)
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding(10),
                        Child = infoToastText
                    }
                }
            };
            infoToastContainer.Hide();

            warningText = new SpriteText
            {
                Text = string.Empty,
                Font = new FontUsage(size: 16),
                Colour = new Color4(255, 230, 180, 255),
                RelativeSizeAxes = Axes.X
            };

            warningContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Alpha = 0,
                Masking = true,
                CornerRadius = 6,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(120, 95, 60, 240)
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding(12),
                        Child = warningText
                    }
                }
            };

            errorNotificationText = new SpriteText
            {
                Text = string.Empty,
                Font = new FontUsage(size: 16),
                Colour = new Color4(255, 205, 215, 255),
                RelativeSizeAxes = Axes.X
            };

            copyLogsButton = new BasicButton
            {
                Text = "Copy logs",
                Width = 120,
                Height = 36,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Action = copyLogsToClipboard
            };

            errorNotificationContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Alpha = 0,
                Masking = true,
                CornerRadius = 6,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(120, 60, 70, 240)
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 8),
                        Padding = new MarginPadding(12),
                        Children = new Drawable[]
                        {
                            errorNotificationText,
                            copyLogsButton
                        }
                    }
                }
            };

            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 10),
                Children = new Drawable[]
                {
                    statusText,
                    stageLabelText,
                    stageProgressText,
                    description,
                    progressBarContainer,
                    heartbeatStatusText,
                    offlineStatusContainer,
                    infoToastContainer,
                    warningContainer,
                    summaryText,
                    errorNotificationContainer
                }
            };
        }

        private void beginGeneration()
        {
            if (currentState.IsActive())
                return;

            if (runTask is { IsCompleted: false })
                return;

            var snapshot = createSnapshot();

            cancellationRequested = false;
            pipelineLogs.Clear();
            playbackAvailable = true;
            currentStats = null;
            latestAnalysis = null;
            waveformData = null;
            lastResult = null;
            lastLaneStats = null;
            debugOverlay.Clear();
            debugOverlay.ShowPlaceholder("Waiting for analysis...");
            debugOverlay.UpdateStatsSummary(null);
            debugOverlay.UpdateStatsSummary(null);
            updateDebugOverlayVisibility();
            updateDebugOverlayInteractivity();

            statusText.Text = "Starting AI-assisted analysis...";
            updateStageDisplay(GenerationStagePlan.GetLabel(GenerationStageId.ModelLoad), 0, false);
            summaryText.FadeOut(150);
            summaryText.Text = string.Empty;

            weightedProgressBar.Reset();
            lastProgressUpdate = null;
            lastStageLabelDisplayed = null;
            detectionStatsToastShown = false;
            overlayAvailabilityAnnounced = false;
            updateHeartbeatStatus(true);
            showWarning(string.Empty);
            errorNotificationContainer.FadeOut(120);
            showOfflineStatus(false);
            clearInfoToast();
            offlineDecodeToastShown = false;
            confidenceAdviceShown = false;
            lastStageDurations = null;
            lastStageDurationSummary = null;
            lastActiveStage = GenerationStageId.ModelLoad;

            updateLivePlaybackInteractivity(true);

            setPendingOptionChange(false);
            setState(GenerationState.Preparing);

            runCts = new CancellationTokenSource();
            var localCts = runCts;

            runTask = generationCoordinator.RunAsync(snapshot, localCts.Token);
            runTask.ContinueWith(task =>
            {
                if (task.IsCompletedSuccessfully)
                {
                    scheduleToUpdateThread(() => handleRunCompletion(task.Result));
                }
                else if (task.IsFaulted)
                {
                    var error = task.Exception?.GetBaseException();
                    scheduleToUpdateThread(() =>
                    {
                        Logger.Error(error, "Generation coordinator faulted");
                        resetRunHandles();
                        var failureText = BeatSightStrings.GenerationFailed.ToString();
                        showErrorNotification(error?.Message ?? failureText);
                        statusText.Text = BeatSightStrings.GenerationFailed;
                        showWarning(string.Empty);
                        hasRunAtLeastOnce = true;
                        setPendingOptionChange(false);
                        setState(GenerationState.Error);
                        showOfflineStatus(false);
                        clearInfoToast();
                        updateDebugOverlayInteractivity();
                        updateDebugOverlayVisibility();
                    });
                }
                else if (task.IsCanceled)
                {
                    scheduleToUpdateThread(() =>
                    {
                        resetRunHandles();
                        statusText.Text = BeatSightStrings.GenerationCancelled;
                        showWarning(string.Empty);
                        setPendingOptionChange(false);
                        setState(GenerationState.Cancelled);
                        showOfflineStatus(false);
                        clearInfoToast();
                        updateDebugOverlayInteractivity();
                        updateDebugOverlayVisibility();
                        cancellationRequested = false;
                    });
                }
            }, TaskScheduler.Default);
        }

        private GenerationParams createSnapshot()
        {
            int sensitivity = (int)Math.Clamp(Math.Round(sensitivityValue.Value), 0, 100);
            return new GenerationParams(importedTrack, sensitivity, mapQuantizationGrid(quantizationGrid.Value), debugOverlayEnabled.Value);
        }

        private static QuantizationGrid mapQuantizationGrid(QuantizationGridSetting setting) => setting switch
        {
            QuantizationGridSetting.Quarter => QuantizationGrid.Quarter,
            QuantizationGridSetting.Eighth => QuantizationGrid.Eighth,
            QuantizationGridSetting.Sixteenth => QuantizationGrid.Sixteenth,
            QuantizationGridSetting.Triplet => QuantizationGrid.Triplet,
            QuantizationGridSetting.ThirtySecond => QuantizationGrid.ThirtySecond,
            _ => QuantizationGrid.Sixteenth
        };

        private void onStageChanged(ValueChangedEvent<GenStage> e)
        {
            if (e.NewValue == GenStage.Cancelled && cancellationRequested)
                showWarning(BeatSightStrings.GenerationCancelled.ToString());
        }

        private void onProgressChanged(ValueChangedEvent<GenerationProgress> e)
        {
            var update = e.NewValue;

            if (!string.IsNullOrWhiteSpace(update.Message))
                statusText.Text = update.Message;
            else
                statusText.Text = update.Stage switch
                {
                    GenStage.AudioInit => "Initialising audio...",
                    GenStage.ModelLoad => "Loading Demucs model...",
                    GenStage.Separation => "Separating drums...",
                    GenStage.OnsetDetection => "Detecting onsets...",
                    GenStage.TempoEstimation => "Estimating tempo...",
                    GenStage.Quantization => "Quantizing grid...",
                    GenStage.Drafting => "Drafting beatmap...",
                    GenStage.Finalising => "Finalising...",
                    GenStage.Completed => "Generation complete.",
                    GenStage.Cancelled => BeatSightStrings.GenerationCancelled.ToString(),
                    GenStage.Failed => BeatSightStrings.GenerationFailed.ToString(),
                    _ => "AI Beatmap Generation"
                };

            string stageLabel = string.IsNullOrWhiteSpace(update.StageLabel)
                ? GenerationStagePlan.GetLabel(update.StageId)
                : update.StageLabel;

            if (update.StageDurations != null)
                lastStageDurations = update.StageDurations;
            lastActiveStage = update.StageId;

            updateStageDisplay(stageLabel, update.StageProgress, update.IsHeartbeat);

            if (update.IsHeartbeat)
            {
                weightedProgressBar.RegisterHeartbeat(update.StageId, update.StageProgress);
            }
            else
            {
                weightedProgressBar.UpdateStageProgress(update.StageId, update.StageProgress, update.Stage is GenStage.Completed or GenStage.Failed or GenStage.Cancelled);
            }

            lastProgressUpdate = DateTimeOffset.UtcNow;

            updateHeartbeatStatus();
        }

        private void onStatsChanged(ValueChangedEvent<DetectionStats?> e)
        {
            currentStats = e.NewValue;
            debugOverlay.UpdateStatsSummary(currentStats);

            if (currentStats == null && latestAnalysis == null)
                debugOverlay.ShowPlaceholder("Waiting for analysis...");

            if (currentStats != null)
            {
                if (!detectionStatsToastShown && currentState.IsActive() && currentStats.PeakCount > 0)
                {
                    var coverage = currentStats.QuantizationCoverage > 0
                        ? $" • {currentStats.QuantizationCoverage:P0} coverage"
                        : string.Empty;
                    showInfoToast($"Detected {currentStats.PeakCount} hits • {currentStats.EstimatedBpm:0.#} BPM{coverage}");
                    detectionStatsToastShown = true;
                }

                if (currentState.IsActive())
                    updateLowConfidenceWarningDuringRun();

            }

            updateDebugOverlayInteractivity();
            updateDebugOverlayVisibility();
        }

        private void onAnalysisChanged(ValueChangedEvent<DrumOnsetAnalysis?> e)
        {
            latestAnalysis = e.NewValue;

            if (latestAnalysis != null)
                notifyOverlayAvailabilityIfNeeded();

            updateOverlayData();
            updateDebugOverlayInteractivity();
            updateDebugOverlayVisibility();
        }

        private void onWaveformChanged(ValueChangedEvent<WaveformData?> e)
        {
            waveformData = e.NewValue;
            updateOverlayData();
            updateDebugOverlayInteractivity();
            updateDebugOverlayVisibility();
        }

        private void updateOverlayData()
        {
            if (debugOverlay == null)
                return;

            if (waveformData != null || latestAnalysis != null)
            {
                debugOverlay.SetData(waveformData, latestAnalysis);
            }
            else
            {
                string placeholder = currentState.IsActive() ? "Waiting for analysis..." : "No analyzer data available.";
                debugOverlay.ShowPlaceholder(placeholder);
            }
        }

        private void notifyOverlayAvailabilityIfNeeded()
        {
            if (overlayAvailabilityAnnounced || latestAnalysis == null)
                return;

            overlayAvailabilityAnnounced = true;

            Scheduler.AddDelayed(() =>
            {
                if (!IsLoaded)
                    return;

                showInfoToast("Analysis ready — toggle the debug overlay for waveform details.");
            }, offlineDecodeToastShown ? 3200 : 400);
        }

        private void updateStageDisplay(string? label, double stageProgress, bool isHeartbeat)
        {
            if (stageLabelText == null || stageProgressText == null)
                return;

            if (string.IsNullOrWhiteSpace(label))
            {
                stageLabelText.FadeOut(150);
                stageProgressText.FadeOut(150);
                lastStageLabelDisplayed = null;
                return;
            }

            if (!string.Equals(lastStageLabelDisplayed, label, StringComparison.Ordinal))
            {
                lastStageLabelDisplayed = label;
                stageLabelText.FinishTransforms();
                stageLabelText.Text = label;
                stageLabelText.FadeIn(150);
                stageLabelText.ScaleTo(1.04f, 120, Easing.OutQuint)
                               .Then()
                               .ScaleTo(1f, 180, Easing.OutQuint);
                stageLabelText.FlashColour(new Color4(200, 230, 255, 255), 160);
            }
            else
            {
                stageLabelText.Text = label;
                if (stageLabelText.Alpha < 0.99f)
                    stageLabelText.FadeIn(150);
            }

            double clamped = double.IsNaN(stageProgress) ? 0 : Math.Clamp(stageProgress, 0, 1);
            string progressLabel = isHeartbeat
                ? $"Stage progress {clamped:P0} • syncing…"
                : $"Stage progress {clamped:P0}";

            if (lastStageDurations is { Count: > 0 } && lastStageDurations.TryGetValue(lastActiveStage, out var stageMs) && stageMs > 0)
                progressLabel += $" • {formatCompactDuration(stageMs)} elapsed";

            stageProgressText.Text = progressLabel;

            if (isHeartbeat)
                stageProgressText.FlashColour(new Color4(190, 210, 255, 255), 90);

            if (!isHeartbeat || stageProgressText.Alpha < 0.99f)
                stageProgressText.FadeIn(150);
        }

        private void updateHeartbeatStatus(bool immediate = false)
        {
            heartbeatStatusUpdateDelegate?.Cancel();
            heartbeatStatusUpdateDelegate = null;

            if (heartbeatStatusText == null)
                return;

            double fadeDuration = immediate ? 0 : 120;

            if (!currentState.IsActive())
            {
                if (lastStageDurations is { Count: > 0 })
                {
                    heartbeatStatusText.Text = buildStageDurationSummary(lastStageDurations, null, includeTotal: true);
                    heartbeatStatusText.Colour = new Color4(150, 155, 175, 255);
                    heartbeatStatusText.FadeIn(fadeDuration);
                }
                else
                {
                    heartbeatStatusText.FadeOut(fadeDuration);
                    heartbeatStatusText.Text = string.Empty;
                    heartbeatStatusText.Colour = new Color4(150, 155, 175, 255);
                }
                return;
            }

            var reference = lastProgressUpdate ?? weightedProgressBar.LastUpdate;

            if (reference == null)
            {
                heartbeatStatusText.Text = "Awaiting first heartbeat…";
                heartbeatStatusText.Colour = new Color4(150, 155, 175, 255);
                heartbeatStatusText.FadeIn(fadeDuration);
                heartbeatStatusUpdateDelegate = Scheduler.AddDelayed(() => updateHeartbeatStatus(), 1000);
                return;
            }

            var elapsed = DateTimeOffset.UtcNow - reference.Value;
            heartbeatStatusText.Text = buildHeartbeatLine(elapsed);

            var staleThreshold = TimeSpan.FromSeconds(6);
            var criticalThreshold = TimeSpan.FromSeconds(12);
            Color4 colour;

            if (elapsed > criticalThreshold)
                colour = new Color4(230, 120, 120, 255);
            else if (elapsed > staleThreshold)
                colour = new Color4(210, 165, 90, 255);
            else
                colour = new Color4(150, 155, 175, 255);

            heartbeatStatusText.Colour = colour;
            heartbeatStatusText.FadeIn(fadeDuration);

            heartbeatStatusUpdateDelegate = Scheduler.AddDelayed(() => updateHeartbeatStatus(), 1000);
        }

        private static string formatElapsed(TimeSpan elapsed)
        {
            if (elapsed.TotalSeconds < 60)
                return $"{elapsed.TotalSeconds:0.0}s";

            if (elapsed.TotalMinutes < 60)
                return $"{elapsed.TotalMinutes:0.#}m";

            if (elapsed.TotalHours < 24)
                return $"{elapsed.TotalHours:0.#}h";

            return $"{elapsed.TotalDays:0.#}d";
        }

        private string buildHeartbeatLine(TimeSpan elapsed)
        {
            if (lastStageDurations is { Count: > 0 })
            {
                string summary = buildStageDurationSummary(lastStageDurations, lastActiveStage, includeTotal: true);
                if (!string.IsNullOrEmpty(summary))
                    return $"{summary} • heartbeat {formatElapsed(elapsed)} ago";
            }

            return $"Last update {formatElapsed(elapsed)} ago";
        }

        private static string formatCompactDuration(double milliseconds)
        {
            if (milliseconds <= 0)
                return "0s";

            var span = TimeSpan.FromMilliseconds(milliseconds);

            if (span.TotalSeconds < 1)
                return $"{milliseconds:0}ms";

            if (span.TotalMinutes < 1)
                return $"{span.TotalSeconds:0.0}s";

            if (span.TotalHours < 1)
                return $"{span.TotalMinutes:0.#}m";

            return $"{span.TotalHours:0.#}h";
        }

        private string buildStageDurationSummary(IReadOnlyDictionary<GenerationStageId, double> durations, GenerationStageId? highlightStage, bool includeTotal, double totalOverrideMs = 0)
        {
            if (durations.Count == 0)
                return string.Empty;

            var ordered = GenerationStagePlan.OrderedStages.Where(durations.ContainsKey).ToList();
            if (ordered.Count == 0)
                ordered.AddRange(durations.Keys);

            var parts = new List<string>();

            foreach (var stage in ordered)
            {
                if (!durations.TryGetValue(stage, out var ms))
                    continue;

                string label = GenerationStagePlan.GetLabel(stage);
                string chunk = $"{label} {formatCompactDuration(ms)}";
                if (highlightStage.HasValue && stage == highlightStage.Value)
                    chunk = $"[{chunk}]";
                parts.Add(chunk);
            }

            double totalMs = totalOverrideMs > 0 ? totalOverrideMs : durations.Sum(pair => Math.Max(pair.Value, 0));
            if (includeTotal && totalMs > 0)
                parts.Add($"Total {formatCompactDuration(totalMs)}");

            return parts.Count > 0 ? string.Join(" • ", parts) : string.Empty;
        }

        private void showOfflineStatus(bool enabled, string? message = null)
        {
            if (offlineStatusContainer == null)
                return;

            if (!enabled)
            {
                offlineStatusContainer.FadeOut(150);
                updateLivePlaybackInteractivity();
                return;
            }

            offlineStatusText.Text = message ?? BeatSightStrings.OfflinePlaybackDisabled.ToString();
            offlineStatusContainer.Show();
            offlineStatusContainer.FadeIn(150);
            updateLivePlaybackInteractivity();
        }

        private void showInfoToast(string message)
        {
            if (infoToastContainer == null)
                return;

            infoToastText.Text = message;
            infoToastContainer.Show();
            infoToastContainer.FadeIn(150);

            Scheduler.AddDelayed(() =>
            {
                if (!infoToastContainer.IsLoaded)
                    return;

                infoToastContainer.FadeOut(250).OnComplete(_ => infoToastContainer.Hide());
            }, 2800);
        }

        private void showInfoToastOnce(string message)
        {
            if (offlineDecodeToastShown)
                return;

            offlineDecodeToastShown = true;
            showInfoToast(message);
        }

        private void clearInfoToast()
        {
            if (infoToastContainer == null)
                return;

            infoToastContainer.FadeOut(150).OnComplete(_ => infoToastContainer.Hide());
        }

        private void resetRunHandles()
        {
            runCts?.Dispose();
            runCts = null;
            runTask = null;
        }

        private void setState(GenerationState newState)
        {
            if (currentState == newState)
                return;

            var previous = currentState;
            currentState = newState;

            bool running = currentState.IsActive();
            updateSensitivityLock(running);

            if (running)
            {
                progressBarContainer.FadeIn(120);
            }
            else if (previous.IsActive() && !running)
            {
                if (currentState == GenerationState.Idle)
                {
                    weightedProgressBar.Reset();
                    progressBarContainer.FadeOut(120);
                    updateStageDisplay(null, 0, false);
                    showOfflineStatus(false);
                    clearInfoToast();
                    cancellationRequested = false;
                }
            }

            refreshButtonStates();
            updateHeartbeatStatus(true);
            updateDebugOverlayInteractivity();
            updateDebugOverlayVisibility();
            updateLivePlaybackInteractivity();
        }

        private void refreshButtonStates()
        {
            if (startButton == null)
                return;

            bool hasDraft = lastResult?.Success == true && !string.IsNullOrEmpty(lastResult?.BeatmapPath);
            bool isRunning = currentState.IsActive();
            bool isReady = currentState == GenerationState.Idle;
            bool isCompleted = currentState == GenerationState.Complete;

            var uiState = GenerationUiStateGuard.Compute(
                isRunning: isRunning,
                isReady: isReady,
                isCompleted: isCompleted,
                hasRunBefore: hasRunAtLeastOnce,
                hasPendingChanges: pendingOptionChange,
                hasDraft: hasDraft);

            startButton.Enabled.Value = uiState.StartEnabled;
            startButton.FadeTo(uiState.StartVisible ? 1f : 0f, 150);

            cancelButton.Enabled.Value = uiState.CancelEnabled;
            cancelButton.FadeTo(uiState.CancelVisible ? 1f : 0f, 150);

            applyButton.Enabled.Value = uiState.ApplyEnabled;
            applyButton.FadeTo(uiState.ApplyVisible ? 1f : 0f, 150);

            openInEditorButton.Enabled.Value = uiState.OpenEditorEnabled;
            openInEditorButton.FadeTo(uiState.OpenEditorVisible ? 1f : 0f, 150);
        }

        private void setPendingOptionChange(bool value)
        {
            if (pendingOptionChange == value)
                return;

            pendingOptionChange = value;
            refreshButtonStates();
        }

        private void onApplyButton()
        {
            if (!pendingOptionChange || currentState.IsActive())
                return;

            beginGeneration();
        }

        private void handleAdvancedSettingChanged()
        {
            if (!settingsReady)
                return;

            if (currentState.IsActive())
                return;

            if (!hasRunAtLeastOnce)
                return;

            setPendingOptionChange(true);
        }

        private void handleRunCompletion(GenerationResult result)
        {
            resetRunHandles();

            pipelineLogs.Clear();
            pipelineLogs.AddRange(result.PipelineResult.Logs);

            if (result.PipelineResult.StageDurations is { Count: > 0 })
            {
                lastStageDurations = result.PipelineResult.StageDurations;
                lastActiveStage = GenerationStageId.Finalise;
                var timelineSummary = buildStageDurationSummary(result.PipelineResult.StageDurations, null, true, result.PipelineResult.TotalDurationMs);
                if (!string.IsNullOrEmpty(timelineSummary))
                {
                    lastStageDurationSummary = timelineSummary;
                    pipelineLogs.Add($"[timeline] {timelineSummary}");
                }
                else
                {
                    lastStageDurationSummary = null;
                }
            }

            playbackAvailable = result.PipelineResult.PlaybackAvailable;

            if (result.PipelineResult.Waveform != null)
                waveformData = result.PipelineResult.Waveform;

            if (result.PipelineResult.Analysis != null)
            {
                latestAnalysis = result.PipelineResult.Analysis;

                if (currentStats == null)
                    currentStats = DetectionStats.FromAnalysis(latestAnalysis, detectionSensitivity.Value, mapQuantizationGrid(quantizationGrid.Value));
            }

            updateOverlayData();
            notifyOverlayAvailabilityIfNeeded();

            lastLaneStats = result.PipelineResult.LaneStats;
            applyResult(result.PipelineResult);
            evaluateDiagnostics(result.PipelineResult);

            hasRunAtLeastOnce = true;
            setPendingOptionChange(false);

            var finalState = result.PipelineResult.Cancelled
                ? GenerationState.Cancelled
                : result.PipelineResult.Success
                    ? GenerationState.Complete
                    : GenerationState.Error;

            setState(finalState);

            if (!playbackAvailable)
            {
                showOfflineStatus(true);
                showInfoToastOnce("Audio output unavailable – using offline decode");
            }
            else
            {
                showOfflineStatus(false);
                if (result.PipelineResult.UsedOfflineDecode)
                    showInfoToast("Playback restored after offline decode fallback");
            }

            updateLivePlaybackInteractivity();

            if (!overlayAvailabilityAnnounced && latestAnalysis != null)
            {
                overlayAvailabilityAnnounced = true;
                Scheduler.AddDelayed(() =>
                {
                    if (!IsLoaded)
                        return;

                    showInfoToast("Analysis ready — toggle the debug overlay for waveform details.");
                }, offlineDecodeToastShown ? 3200 : 400);
            }

            updateDebugOverlayInteractivity();
            updateDebugOverlayVisibility();
            cancellationRequested = false;
        }

        private void applyResult(GenerationPipelineResult result)
        {
            if (result.Success)
                weightedProgressBar.MarkCompleted();

            if (result.Cancelled)
            {
                lastResult = null;
                statusText.Text = result.TotalDurationMs > 0
                    ? $"Run cancelled after {formatCompactDuration(result.TotalDurationMs)}"
                    : BeatSightStrings.GenerationCancelled;
                summaryText.Colour = new Color4(200, 200, 220, 255);
                var cancelledSummary = BeatSightStrings.GenerationCancelledSummary.ToString();
                if (!string.IsNullOrEmpty(lastStageDurationSummary))
                    cancelledSummary = $"{cancelledSummary}\n{lastStageDurationSummary}";
                summaryText.Text = cancelledSummary;
                summaryText.FadeIn(150);
                return;
            }

            if (result.Success && result.Beatmap != null && result.Beatmap.Success && !string.IsNullOrEmpty(result.Beatmap.BeatmapPath))
            {
                lastResult = result.Beatmap;

                if (result.TotalDurationMs > 0)
                    statusText.Text = $"Generation ready in {formatCompactDuration(result.TotalDurationMs)}";
                else
                    statusText.Text = BeatSightStrings.GenerationReady;
                summaryText.Colour = new Color4(150, 205, 255, 255);
                var successSummary = buildSummary(result.Beatmap);
                if (!string.IsNullOrEmpty(lastStageDurationSummary))
                    successSummary = $"{successSummary}\n{lastStageDurationSummary}";
                summaryText.Text = successSummary;
                summaryText.FadeIn(200);

                errorNotificationContainer.FadeOut(150);
            }
            else
            {
                lastResult = result.Beatmap;

                var fallback = BeatSightStrings.UnknownGenerationError.ToString();
                string message = result.FailureReason ?? result.Beatmap?.Error ?? fallback;
                statusText.Text = BeatSightStrings.GenerationFailed;
                summaryText.Colour = new Color4(255, 140, 140, 255);
                if (!string.IsNullOrEmpty(lastStageDurationSummary))
                    message = $"{message}\n{lastStageDurationSummary}";
                summaryText.Text = message;
                summaryText.FadeIn(150);

                showErrorNotification(message);
            }
        }

        private void evaluateDiagnostics(GenerationPipelineResult result)
        {
            var warnings = new List<string>();

            if (!string.IsNullOrWhiteSpace(result.Warning))
            {
                var parts = result.Warning
                    .Split('•', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                    .Where(part => !isOfflineFallbackMessage(part) || !result.UsedOfflineDecode);

                warnings.AddRange(parts);
            }

            if (currentStats?.TryGetTempoAmbiguityMessage(out var tempoAmbiguity) == true)
                warnings.Add(tempoAmbiguity);

            if (currentStats?.TryGetLowConfidenceMessage(out var lowConfidence) == true)
            {
                warnings.Add(lowConfidence);
                if (!confidenceAdviceShown)
                    showConfidenceAdvice(currentStats!);
            }

            if (buildLaneVariationWarning(result) is { Length: > 0 } laneWarning)
                warnings.Add(laneWarning);

            string message = warnings.Count > 0
                ? string.Join(" • ", warnings.Distinct(StringComparer.OrdinalIgnoreCase))
                : string.Empty;

            showWarning(message);
        }

        private static bool isOfflineFallbackMessage(string message)
            => message.Contains("offline decode", StringComparison.OrdinalIgnoreCase) || message.Contains("Audio device slow", StringComparison.OrdinalIgnoreCase);

        private void updateSensitivityLock(bool running)
        {
            sensitivitySlider.Current.Disabled = running;
            quantizationDropdown.Current.Disabled = running;
            if (advancedToggleButton != null)
                advancedToggleButton.Enabled.Value = !running;
            sensitivityLockNote.FadeTo(running ? 1f : 0f, 150);
        }

        private void updateLivePlaybackInteractivity(bool immediate = false)
        {
            if (livePlaybackSettingsContainer == null)
                return;

            bool offline = !playbackAvailable;
            float containerAlpha = offline ? 0.65f : 1f;

            applyInteractivityVisual(metronomeCheckbox, offline, immediate);
            applyInteractivityVisual(drumStemCheckbox, offline, immediate);
            applyInteractivityVisual(metronomeSoundDropdown, offline, immediate);
            applyInteractivityVisual(noteSkinDropdown, false, immediate);

            metronomeCheckbox.Current.Disabled = false;
            drumStemCheckbox.Current.Disabled = false;
            metronomeSoundDropdown.Current.Disabled = false;
            noteSkinDropdown.Current.Disabled = false;

            if (!livePlaybackSettingsContainer.IsLoaded || immediate)
                livePlaybackSettingsContainer.Alpha = containerAlpha;
            else
                livePlaybackSettingsContainer.FadeTo(containerAlpha, 150, Easing.OutQuint);

            if (livePlaybackStatusText != null)
            {
                if (offline)
                {
                    livePlaybackStatusText.Text = "Playback offline — changes apply on reconnect";
                    livePlaybackStatusText.Colour = new Color4(215, 180, 120, 255);
                }
                else if (currentState.IsActive())
                {
                    livePlaybackStatusText.Text = "Live playback running — tweaks update immediately";
                    livePlaybackStatusText.Colour = new Color4(150, 210, 255, 255);
                }
                else
                {
                    livePlaybackStatusText.Text = "Ready — adjust playback before the next run";
                    livePlaybackStatusText.Colour = new Color4(170, 200, 240, 255);
                }
            }
        }

        private static void applyInteractivityVisual(Drawable drawable, bool dimmed, bool immediate)
        {
            if (drawable == null)
                return;

            float alpha = dimmed ? 0.65f : 1f;

            if (!drawable.IsLoaded || immediate)
                drawable.Alpha = alpha;
            else
                drawable.FadeTo(alpha, 120, Easing.OutQuint);
        }

        private void updateDebugOverlayInteractivity()
        {
            bool running = currentState.IsActive();
            bool overlayReady = latestAnalysis != null || waveformData != null;

            debugOverlayCheckbox.Current.Disabled = running || !overlayReady;

            if (!overlayReady)
            {
                debugOverlayNote.Text = running ? "Analyzing audio..." : "Available after onset detection";
                debugOverlayNote.FadeIn(150);
                return;
            }

            if (debugOverlayEnabled.Value)
            {
                debugOverlayNote.FadeOut(150);
            }
            else if (currentStats != null)
            {
                debugOverlayNote.Text = buildStatsSummary(currentStats);
                debugOverlayNote.FadeIn(150);
            }
            else
            {
                debugOverlayNote.Text = "Toggle overlay to inspect analysis";
                debugOverlayNote.FadeIn(150);
            }
        }

        private void updateDebugOverlayVisibility()
        {
            if (debugOverlay == null)
                return;

            bool overlayReady = latestAnalysis != null || waveformData != null;
            float target = debugOverlayEnabled.Value && overlayReady && currentState.AllowsOverlay() ? 1f : 0f;
            debugOverlay.FadeTo(target, 200);
        }

        private void updateLowConfidenceWarningDuringRun()
        {
            if (!currentState.IsActive())
                return;

            if (currentStats == null)
            {
                showWarning(string.Empty);
                return;
            }

            var warnings = new List<string>();

            if (currentStats.TryGetTempoAmbiguityMessage(out var tempoAmbiguity))
                warnings.Add(tempoAmbiguity);

            if (currentStats.TryGetLowConfidenceMessage(out var message))
            {
                warnings.Add(message);
                if (!confidenceAdviceShown)
                    showConfidenceAdvice(currentStats);
            }

            showWarning(warnings.Count > 0 ? string.Join(" • ", warnings.Distinct(StringComparer.OrdinalIgnoreCase)) : string.Empty);
        }

        private void cancelGeneration()
        {
            cancellationRequested = true;

            if (runTask is { IsCompleted: false })
            {
                runCts?.Cancel();
                generationCoordinator.Cancel();
                if (currentState.IsActive())
                    setState(GenerationState.Cancelled);
            }
        }

        private void scheduleToUpdateThread(Action action) => Scheduler.Add(action);

        private void showWarning(string message)
        {
            if (string.IsNullOrWhiteSpace(message))
            {
                warningContainer.FadeOut(150);
                return;
            }

            warningText.Text = message;
            warningContainer.FadeIn(200);
        }

        private void showConfidenceAdvice(DetectionStats stats)
        {
            confidenceAdviceShown = true;
            var issues = stats.GetConfidenceIssues();
            string advice = issues.Count > 0
                ? $"Confidence tips: {string.Join(" • ", issues)}"
                : "Confidence low — try raising sensitivity or switching the quantization grid.";
            showInfoToast(advice);
        }

        private string? buildLaneVariationWarning(GenerationPipelineResult result)
        {
            var laneStats = result.LaneStats;
            if (laneStats == null)
                return null;

            int hitCount = result.Beatmap?.Beatmap?.HitObjects?.Count ?? 0;
            if (hitCount < 12)
                return null;

            bool lowCymbal = laneStats.CymbalSwitches <= 1;
            bool lowTom = laneStats.TomSwitches <= 1;

            if (!lowCymbal && !lowTom)
                return null;

            static string describe(string label, int count) => count switch
            {
                <= 0 => $"no {label} switches",
                1 => $"1 {label} switch",
                _ => $"{count} {label} switches"
            };

            if (lowCymbal && lowTom)
                return $"Lane telemetry: cymbal and tom lanes barely alternate ({describe("cymbal", laneStats.CymbalSwitches)}, {describe("tom", laneStats.TomSwitches)}). Try raising detection sensitivity or adjust lanes manually.";

            if (lowCymbal)
                return $"Lane telemetry: cymbal hits rarely switched lanes ({describe("cymbal", laneStats.CymbalSwitches)}). Consider raising detection sensitivity or editing lanes.";

            return $"Lane telemetry: tom hits rarely switched lanes ({describe("tom", laneStats.TomSwitches)}). Consider raising detection sensitivity or editing lanes.";
        }

        private void showErrorNotification(string message)
        {
            if (string.IsNullOrWhiteSpace(message))
            {
                errorNotificationContainer.FadeOut(150);
                return;
            }

            errorNotificationText.Text = message;
            errorNotificationContainer.FadeIn(200);
        }

        private string buildStatsSummary(DetectionStats stats)
        {
            var parts = new List<string>();

            if (stats.PeakCount > 0)
                parts.Add($"{stats.PeakCount} peaks");

            if (stats.EstimatedBpm > 0)
                parts.Add($"{stats.EstimatedBpm:0.#} BPM");

            parts.Add($"Sensitivity {stats.Sensitivity}");
            parts.Add(stats.Grid switch
            {
                QuantizationGrid.Quarter => "Quarter grid",
                QuantizationGrid.Eighth => "Eighth grid",
                QuantizationGrid.Sixteenth => "Sixteenth grid",
                QuantizationGrid.Triplet => "Triplet grid",
                QuantizationGrid.ThirtySecond => "Thirty-second grid",
                _ => "Sixteenth grid"
            });

            if (stats.QuantizationCoverage > 0)
                parts.Add($"Coverage {stats.QuantizationCoverage:P0}");

            if (stats.QuantizationMeanErrorMs > 0)
                parts.Add($"{stats.QuantizationMeanErrorMs:0.#}ms avg error");

            parts.Add($"Score {stats.ConfidenceScore:P0}");

            double stepMs = stats.QuantizationStepSeconds * 1000.0;
            if (stepMs > 0)
                parts.Add($"{stepMs:0.#}ms step");

            return string.Join(" • ", parts);
        }

        private string buildSummary(AiGenerationResult result)
        {
            var details = new List<string>();
            var beatmap = result.Beatmap;

            if (beatmap?.HitObjects != null && beatmap.HitObjects.Count > 0)
                details.Add($"{beatmap.HitObjects.Count} detected hits");

            var bpm = beatmap?.Timing?.Bpm;
            if (bpm.HasValue && bpm.Value > 0)
                details.Add($"~{Math.Round(bpm.Value)} BPM");

            var difficulty = beatmap?.Metadata?.Difficulty;
            if (difficulty.HasValue && difficulty.Value > 0)
                details.Add($"Difficulty {difficulty.Value:0.0}");

            if (lastLaneStats != null)
                details.Add($"Lane swaps — cymbal {lastLaneStats.CymbalSwitches}, tom {lastLaneStats.TomSwitches}");

            return details.Count > 0
                ? string.Join(" • ", details)
                : "Draft saved to your BeatSight beatmaps folder.";
        }

        private void copyLogsToClipboard()
        {
            if (pipelineLogs.Count == 0)
                return;

            string payload = string.Join('\n', pipelineLogs);

            try
            {
                clipboard.SetText(payload);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to copy logs: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        protected override void Dispose(bool isDisposing)
        {
            cancelGeneration();
            heartbeatStatusUpdateDelegate?.Cancel();
            heartbeatStatusUpdateDelegate = null;
            base.Dispose(isDisposing);
        }
    }
}
