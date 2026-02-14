using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.Audio;
using BeatSight.Game.AI;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using Newtonsoft.Json;
using osu.Framework.Allocation;
using osu.Framework.Audio;
using osu.Framework.Audio.Track;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.IO.Stores;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen : BeatSightScreen
    {
        private Beatmap? beatmap;
        private string? beatmapPath;
        private Track? track;
        private ImportedAudioTrack? importedAudio;
        private ITrackStore? storageTrackStore;
        private StorageBackedResourceStore? storageResourceStore;
        private Bindable<LaneViewMode> laneViewModeBindable = null!;
        private Bindable<LaneViewMode> laneViewMode = null!;
        private Bindable<EditorPreviewMode> previewMode = null!;
        private Bindable<LanePreset> lanePresetSetting = null!;
        private Bindable<KickLaneMode> kickLaneModeSetting = null!;

        private EditorTimeline timeline = null!;
        private PlaybackPreview playbackPreview = null!;
        private PreviewToggleButton previewToggle = null!;
        private SpriteText statusText = null!;
        private SpriteText statusDetailLine = null!;
        private SpriteText timeText = null!;
        private SpriteText actionHintText = null!;
        private SpriteText playbackStatusText = null!;
        private SpriteText undoHeaderText = null!;
        private SpriteText redoHeaderText = null!;
        private Container historyPanel = null!;
        private FillFlowContainer undoHistoryFlow = null!;
        private FillFlowContainer redoHistoryFlow = null!;
        private ToastContainer quickActionToast = null!;
        private EditorButton playPauseButton = null!;
        private EditorButton saveButton = null!;
        private EditorButton undoButton = null!;
        private EditorButton redoButton = null!;
        private BackButton backButton = null!;
        private Container inspectorContainer = null!;
        private GridContainer previewInspectorGrid = null!;
        private GridContainer timelineLayoutGrid = null!;
        private GridContainer editorLayoutGrid = null!;
        private GridContainer screenLayoutGrid = null!;
        private Container headerContentContainer = null!;
        private FillFlowContainer headerInformationFlow = null!;
        private FillFlowContainer headerButtonFlow = null!;
        private Container headerTimeBadgeContainer = null!;
        private SpriteText headerTimeCaptionText = null!;
        private FillFlowContainer headerStatusColumn = null!;
        private Container previewContentContainer = null!;
        private Container previewCellContainer = null!;
        private Container previewSurfaceContainer = null!;
        private Container timelineToolboxContainer = null!;
        private FillFlowContainer timelineToolboxContentFlow = null!;
        private Container timelineZoomSliderContainer = null!;
        private Container timelineWaveformSliderContainer = null!;
        private readonly List<BasicButton> timelineMiniButtons = new();
        private readonly List<SpriteText> timelineMiniButtonTexts = new();
        private readonly List<SpriteText> timelineSectionTitleTexts = new();
        private readonly List<FillFlowContainer> timelineSectionControlRows = new();
        private readonly List<FillFlowContainer> timelineSectionBodies = new();
        private FillFlowContainer inspectorSectionsFlow = null!;
        private Container footerRootContainer = null!;
        private Container footerInnerContainer = null!;
        private FillFlowContainer footerTipFlow = null!;
        private EditorButton inspectorToggleButton = null!;
        private float lastInspectorWidth = -1;
        private float lastTimelineSurfaceHeight = -1;
        private float lastTimelineToolboxHeight = -1;
        private float lastFooterHeight = -1;
        private float lastStackedInspectorHeight = -1;
        private float lastPanelGap = -1;
        private float lastCompactBlend = -1f;
        private bool inspectorStackedLayout;
        private bool inspectorCollapsed;
        private readonly List<BeatSightTextBox> inspectorTextBoxes = new();
        private readonly List<BasicButton> inspectorActionButtons = new();
        private readonly List<SpriteText> inspectorActionButtonTexts = new();
        private readonly List<(BasicButton Button, SpriteText Label, bool FillWidth, float WidthHint)> inspectorActionLayouts = new();
        private readonly List<BeatSightSliderBar> inspectorSliders = new();
        private readonly List<FillFlowContainer> inspectorSectionBodies = new();
        private readonly List<FillFlowContainer> inspectorFieldFlows = new();
        private readonly List<SpriteText> inspectorSectionTitleTexts = new();
        private readonly List<SpriteText> inspectorFieldLabelTexts = new();
        private readonly List<SpriteText> footerKeyTexts = new();
        private readonly List<SpriteText> footerActionTexts = new();
        private readonly Dictionary<EditorInspectorSectionKey, Drawable> inspectorSectionsByKey = new();
        private Drawable inspectorMetadataSection = null!;
        private Drawable inspectorTimingSection = null!;
        private Drawable inspectorStatsSection = null!;
        private Drawable inspectorGenerationSection = null!;
        private bool inspectorCompactHierarchy;

        private BasicTextBox releaseInput = null!;
        private BasicTextBox providerInput = null!;
        private BasicTextBox descriptionInput = null!;
        private BasicTextBox titleInput = null!;
        private BasicTextBox artistInput = null!;
        private BasicTextBox creatorInput = null!;
        private BasicTextBox sourceInput = null!;
        private BasicTextBox tagsInput = null!;
        private BasicTextBox bpmInput = null!;
        private BasicTextBox offsetInput = null!;

        private Bindable<string> quantizationGrid = new Bindable<string>("sixteenth");
        private BindableDouble maxSnapError = new BindableDouble(12.0) { MinValue = 1.0, MaxValue = 50.0, Precision = 0.1 };
        private BindableDouble confidenceThreshold = new BindableDouble(0.3) { MinValue = 0.1, MaxValue = 0.9, Precision = 0.01 };
        private BindableDouble detectionSensitivity = new BindableDouble(60.0) { MinValue = 1.0, MaxValue = 100.0, Precision = 1.0 };
        private BindableBool isolateDrums = new BindableBool(true);
        private BindableBool forceQuantization = new BindableBool(false);
        private BindableBool useMlClassifier = new BindableBool(true);
        private BasicTextBox tempoHintsInput = null!;

        private SpriteText noteCountValue = null!;
        private SpriteText selectionSummaryText = null!;
        private SpriteText mapLengthValue = null!;
        private SpriteText densityValue = null!;
        private SpriteText bpmStatValue = null!;
        private BeatSight.Game.UI.Components.Dropdown<string> componentReassignDropdown = null!;
        private readonly Bindable<string> componentReassignSelection = new Bindable<string>("kick");

        private bool isPlaying;
        private double currentTime;
        private double lastManuscriptFocusSyncAt = double.NegativeInfinity;
        private double trackLength;
        private WaveformData? waveformData;
        private WaveformData? fullTrackWaveform;
        private WaveformData? drumStemWaveform;
        private BindableBool showDrumStem = new BindableBool(false);
        private CancellationTokenSource? waveformLoadCts;
        private string statusBaseText = string.Empty;
        private string? statusDetailText;
        private bool hasUnsavedChanges;
        private readonly List<EditorSnapshot> undoStack = new();
        private readonly List<EditorSnapshot> redoStack = new();
        private bool editSnapshotArmed;
        private double timelineZoom = 1.0;
        private int snapDivisor = 4;
        private double waveformScale = 1.0;
        private bool beatGridVisible = true;
        private string? lastSavedSnapshot;
        private bool isSaving;
        private string? hoverHintOverride;
        private string? defaultHintText;
        private double lastTrackTime;
        private readonly bool playbackAvailable;

        private BeatSightSliderBar timelineZoomSlider = null!;
        private SpriteText timelineZoomValueText = null!;
        private BeatSightSliderBar waveformScaleSlider = null!;
        private SpriteText waveformScaleValueText = null!;
        private SpriteText snapDivisorText = null!;
        private BeatSightCheckbox beatGridCheckbox = null!;

        private bool suppressTimelineZoomSync;
        private bool suppressWaveformScaleSync;
        private bool suppressBeatGridSync;
        private bool suppressEditorDefaultPersistence;
        private bool timelineZoomPointerAdjusting;
        private bool timelineZoomInteractionActive;
        private bool timelineZoomInteractionDirty;
        private double lastTimelineZoomPreviewAppliedAt = double.NegativeInfinity;
        private double? pendingTimelineZoomPreview;
        private bool waveformScalePointerAdjusting;
        private bool waveformScaleInteractionActive;
        private bool waveformScaleInteractionDirty;
        private double lastWaveformScalePreviewAppliedAt = double.NegativeInfinity;
        private double? pendingWaveformScalePreview;
        private double? liveWaveformScalePreviewValue;

        private Bindable<double> editorTimelineZoomDefault = null!;
        private Bindable<double> editorWaveformScaleDefault = null!;
        private Bindable<bool> editorBeatGridVisibleDefault = null!;

        private bool suppressInspectorFieldSync;
        private HitObject? selectedHitObject;
        private double? initialBeatmapBpm;
        private DateTime lastInspectorSnapshotAtUtc = DateTime.MinValue;

        private const int maxUndoSteps = 50;
        private const int historyPreviewCount = 5;
        private const double timelineZoomPreviewMinIntervalMs = 24;
        private const double waveformScalePreviewMinIntervalMs = 24;
        private const float inspectorButtonColumnSpacing = 7;
        private const float inspectorButtonRowSpacing = 6;
        private const float timelineToolboxRowHeight = 118f;
        private const float timelineSurfaceHeight = 292f;
        private const double manuscriptFocusSyncIntervalMs = 120;
        private const double firstNoteLeadInMs = 1800;
        private const double previewStartLookBehindMs = 1200;
        private const double previewStartLookAheadMs = 3500;
        private const double notationGhostVelocity = 0.25;
        private const double notationNormalVelocity = 0.68;
        private const double notationAccentVelocity = 0.95;
        private static readonly TimeSpan inspectorSnapshotDebounce = TimeSpan.FromMilliseconds(450);
        private static readonly int[] allowedSnapDivisors = { 1, 2, 3, 4, 6, 8, 12, 16, 24, 32 };
        private static readonly string[] defaultComponentReassignmentOptions =
        {
            "kick",
            "snare",
            "hihat_closed",
            "hihat_open",
            "hihat_pedal",
            "tom_high",
            "tom_mid",
            "tom_low",
            "crash",
            "ride",
            "ride_bell",
            "china",
            "splash",
            "cross_stick"
        };
        private static readonly string[] dedicatedLaneQuickComponents =
        {
            "crash",
            "hihat_closed",
            "snare",
            "kick",
            "tom_mid",
            "ride",
            "china",
            "splash",
            "percussion"
        };

        private static readonly string[] globalKickLaneQuickComponents =
        {
            "crash",
            "hihat_closed",
            "snare",
            "tom_mid",
            "ride",
            "china",
            "splash",
            "percussion"
        };
        private const string offlinePlaybackMessage = "Audio preview disabled - offline decode only.";
        private static readonly string[] transientPlaybackStatusTokens =
        {
            "Playing",
            "Paused",
            "Playback finished",
            "Rewound to start"
        };

        private enum NotationArticulationPreset
        {
            Ghost = 0,
            Normal = 1,
            Accent = 2
        }

        private enum NotationHotkeyAction
        {
            None = 0,
            ShiftLaneUp,
            ShiftLaneDown,
            ArticulationUp,
            ArticulationDown
        }

        [Resolved]
        private AudioManager audioManager { get; set; } = null!;

        [Resolved]
        private GameHost host { get; set; } = null!;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        private Container logOverlay = null!;
        private TextFlowContainer logText = null!;
        private BeatSightScrollContainer logScroll = null!;

        public EditorScreen(string? beatmapPath = null, ImportedAudioTrack? importedAudio = null, bool playbackAvailable = true)
        {
            this.beatmapPath = beatmapPath;
            this.importedAudio = importedAudio;
            this.playbackAvailable = playbackAvailable;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            storageResourceStore ??= new StorageBackedResourceStore(host.Storage);
            storageTrackStore ??= audioManager.GetTrackStore(storageResourceStore);
            laneViewModeBindable = config.GetBindable<LaneViewMode>(BeatSightSetting.LaneViewMode);
            laneViewMode = laneViewModeBindable.GetBoundCopy();
            lanePresetSetting = config.GetBindable<LanePreset>(BeatSightSetting.LanePreset);
            kickLaneModeSetting = config.GetBindable<KickLaneMode>(BeatSightSetting.KickLaneMode);

            // Initialize preview mode based on current setting
            var initialPreviewMode = EditorPreviewMode.Playfield3D;
            switch (laneViewModeBindable.Value)
            {
                case LaneViewMode.TwoDimensional: initialPreviewMode = EditorPreviewMode.Playfield2D; break;
                case LaneViewMode.Manuscript: initialPreviewMode = EditorPreviewMode.Manuscript; break;
                case LaneViewMode.ThreeDimensional: initialPreviewMode = EditorPreviewMode.Playfield3D; break;
            }
            previewMode = new Bindable<EditorPreviewMode>(initialPreviewMode);

            editorTimelineZoomDefault = config.GetBindable<double>(BeatSightSetting.EditorTimelineZoomDefault);
            editorWaveformScaleDefault = config.GetBindable<double>(BeatSightSetting.EditorWaveformScaleDefault);
            editorBeatGridVisibleDefault = config.GetBindable<bool>(BeatSightSetting.EditorBeatGridVisibleDefault);

            bool previousPersistenceState = suppressEditorDefaultPersistence;
            suppressEditorDefaultPersistence = true;
            applyEditorDefaultsFromConfig();
            suppressEditorDefaultPersistence = previousPersistenceState;

            laneViewMode.BindValueChanged(onLaneViewModeChanged, true);
            previewMode.BindValueChanged(onPreviewModeChanged);

            backButton = new BackButton
            {
                Margin = BackButton.DefaultMargin,
                Action = () => this.Exit()
            };

            var editorEdgePadding = new MarginPadding
            {
                Left = UITheme.ScreenPadding.Left + 20,
                Right = UITheme.ScreenPadding.Right + 20,
                Top = UITheme.ScreenPadding.Top + 12,
                Bottom = UITheme.ScreenPadding.Bottom + 12
            };

            var paddedLayout = new ScreenEdgeContainer(scrollable: false)
            {
                EdgePadding = editorEdgePadding,
                Content = screenLayoutGrid = new GridContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    RowDimensions = new[]
                    {
                        new Dimension(GridSizeMode.AutoSize),
                        new Dimension(),
                        new Dimension(GridSizeMode.Absolute, getInitialFooterHeight())
                    },
                    Content = new[]
                    {
                        new Drawable[] { createHeader() },
                        new Drawable[] { createEditor() },
                        new Drawable[] { createFooter() }
                    }
                }
            };

            var backButtonOverlay = new SafeAreaContainer
            {
                RelativeSizeAxes = Axes.Both,
                Padding = BackButton.DefaultMargin,
                Child = backButton
            };

            historyPanel!.Y = editorEdgePadding.Top + 64;

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = EditorColours.ScreenBackground
                },
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Height = 0.48f,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Colour = EditorColours.ScreenBackdropTop
                },
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Height = 0.52f,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Colour = EditorColours.ScreenBackdropBottom.Opacity(0.9f)
                },
                paddedLayout,
                historyPanel!,
                backButtonOverlay,
                quickActionToast = new ToastContainer
                {
                    RelativeSizeAxes = Axes.Both
                },
                createLogOverlay()
            };

            if (!string.IsNullOrEmpty(beatmapPath))
            {
                loadBeatmap(beatmapPath);
            }
            else if (importedAudio != null)
            {
                initializeNewProject(importedAudio);
            }
            else
            {
                // Initialize a blank project if no beatmap or audio is provided
                initializeNewProject(null);
                reloadTimeline();
                updateActionButtons();
                refreshTimelineToolboxState();
                updatePlaybackAvailabilityUI();
            }
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            showDrumStem.BindValueChanged(_ => updateWaveformSource());

            // Ensure preview is synchronized after everything is loaded
            if (beatmap != null && playbackPreview != null)
            {
                playbackPreview.SetBeatmap(beatmap);
            }

            // Make sure the correct preview mode is visible
            onPreviewModeChanged(new ValueChangedEvent<EditorPreviewMode>(previewMode.Value, previewMode.Value));

            updatePlaybackAvailabilityUI();
            applyResponsiveEditorLayout(force: true);
        }

        private Drawable createHeader()
        {
            statusText = new SpriteText
            {
                Text = string.Empty,
                Font = BeatSightFont.Section(18.4f),
                Colour = EditorColours.TextPrimary,
                AllowMultiline = true,
                MaxWidth = 560,
                Truncate = false,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            };

            statusDetailLine = new SpriteText
            {
                Font = BeatSightFont.Caption(11.6f),
                Colour = EditorColours.TextSecondary,
                Alpha = 0,
                AllowMultiline = true,
                MaxWidth = 560,
                Truncate = false,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            };

            var statusColumn = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 5),
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Children = new Drawable[]
                {
                    statusText,
                    statusDetailLine
                }
            };
            headerStatusColumn = statusColumn;

            float safeLeftPadding = (backButton?.Margin.Left ?? 0) + (backButton?.Width ?? 120) + 20;

            timeText = new SpriteText
            {
                Text = formatTime(0),
                Font = BeatSightFont.Numeral(22.4f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Margin = new MarginPadding { Horizontal = 18, Vertical = 2 }
            };

            var timeCaption = new SpriteText
            {
                Text = "TIMELINE",
                Font = BeatSightFont.Caption(9.8f),
                Colour = EditorColours.TextMuted,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };
            headerTimeCaptionText = timeCaption;

            var timeBadge = new Container
            {
                Size = new Vector2(196, 62),
                Masking = true,
                CornerRadius = 12,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.CardBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.14f
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Spacing = new Vector2(0, 3),
                        Padding = new MarginPadding { Horizontal = 14, Vertical = 6 },
                        Children = new Drawable[]
                        {
                            timeCaption,
                            timeText
                        }
                    },
                }
            };
            headerTimeBadgeContainer = timeBadge;

            playPauseButton = new EditorButton("Play", EditorColours.AccentPlay)
            {
                Size = new Vector2(120, 42),
                Action = togglePlayback
            };

            saveButton = new EditorButton("Save", EditorColours.AccentSave)
            {
                Size = new Vector2(120, 42),
                Action = saveBeatmap
            };

            undoButton = new EditorButton("Undo", EditorColours.AccentUndo)
            {
                Size = new Vector2(104, 42),
                Action = undoLastEdit
            };

            redoButton = new EditorButton("Redo", EditorColours.AccentRedo)
            {
                Size = new Vector2(104, 42),
                Action = redoLastEdit
            };

            previewToggle = new PreviewToggleButton(previewMode)
            {
                Size = new Vector2(146, 42),
                Alpha = 0
            };

            playPauseButton.HoverHintChanged += setHoverHint;
            saveButton.HoverHintChanged += setHoverHint;
            undoButton.HoverHintChanged += setHoverHint;
            redoButton.HoverHintChanged += setHoverHint;
            previewToggle.HoverHintChanged += setHoverHint;

            var buttonFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(10, 0),
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Children = new Drawable[]
                {
                    playPauseButton,
                    saveButton,
                    undoButton,
                    redoButton,
                    previewToggle
                }
            };
            headerButtonFlow = buttonFlow;

            actionHintText = new SpriteText
            {
                Font = BeatSightFont.Caption(11.4f),
                Colour = EditorColours.TextSecondary,
                Alpha = 0,
                Text = string.Empty,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                MaxWidth = 1040,
                AllowMultiline = true,
                Truncate = false
            };

            playbackStatusText = new SpriteText
            {
                Font = BeatSightFont.Caption(11.4f),
                Colour = EditorColours.Warning,
                Alpha = 0,
                Text = string.Empty,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                MaxWidth = 1040,
                AllowMultiline = true,
                Truncate = false
            };

            historyPanel = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Child = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    CornerRadius = 9,
                    Masking = true,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = EditorColours.HistoryBackground
                        },
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = EditorColours.PanelStroke,
                            Alpha = 0.16f
                        },
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Horizontal,
                            Spacing = new Vector2(24, 0),
                            Padding = new MarginPadding { Horizontal = 16, Vertical = 9 },
                            Children = new Drawable[]
                            {
                                createHistoryColumn("Undo", out undoHeaderText, out undoHistoryFlow),
                                createHistoryColumn("Redo", out redoHeaderText, out redoHistoryFlow)
                            }
                        }
                    }
                }
            };

            var mainRow = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Children = new Drawable[]
                {
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding { Left = safeLeftPadding, Right = 26 },
                        Child = statusColumn
                    },
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Child = timeBadge
                    },
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.TopRight,
                        Origin = Anchor.TopRight,
                        Child = buttonFlow
                    }
                }
            };
            historyPanel.Hide();

            var informationFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6),
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Children = new Drawable[]
                {
                    actionHintText,
                    playbackStatusText
                }
            };
            headerInformationFlow = informationFlow;

            var content = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(10),
                Children = new Drawable[]
                {
                    mainRow,
                    informationFlow
                }
            };

            var header = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.HeaderBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Height = 0.5f,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.TopLeft,
                        Colour = EditorColours.PanelStroke.Opacity(0.34f)
                    },
                    headerContentContainer = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding { Horizontal = 24, Vertical = 12 },
                        Child = content
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 1,
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        Colour = EditorColours.Divider
                    }
                }
            };

            setStatusBase(string.Empty);
            setStatusDetail("Load or import audio to begin mapping.");
            updateActionButtons();
            updatePlaybackAvailabilityUI();

            return header;
        }


        private Drawable createEditor()
        {
            var viewport = resolveResponsiveViewport();
            var initialMetrics = EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout);

            timeline = new EditorTimeline
            {
                RelativeSizeAxes = Axes.Both
            };

            timeline.SeekRequested += onTimelineSeekRequested;
            timeline.NoteSelected += onTimelineNoteSelected;
            timeline.NoteAdded += onTimelineNoteChanged;
            timeline.NoteChanged += onTimelineNoteChanged;
            timeline.NoteDeleted += onTimelineNoteChanged;
            timeline.EditBegan += onTimelineEditBegan;
            timeline.ZoomChanged += onTimelineZoomChanged;
            timeline.SnapDivisorChanged += onTimelineSnapDivisorChanged;
            timeline.SelectionChanged += onTimelineSelectionChanged;

            playbackPreview = new PlaybackPreview(() => currentTime)
            {
                RelativeSizeAxes = Axes.Both
            };

            previewSurfaceContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 16,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PreviewBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.13f
                    },
                    previewContentContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 10, Vertical = 8 },
                        Child = playbackPreview
                    },
                    inspectorToggleButton = new EditorButton("Hide Inspector", EditorColours.AccentUndo)
                    {
                        Size = new Vector2(132, 34),
                        Anchor = Anchor.TopRight,
                        Origin = Anchor.TopRight,
                        Margin = new MarginPadding { Top = 12, Right = 12 },
                        Alpha = 0,
                        Action = toggleInspectorCollapsed
                    }
                }
            };

            previewCellContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Right = initialMetrics.PanelGap },
                Child = previewSurfaceContainer
            };

            inspectorContainer = new Container
            {
                RelativeSizeAxes = Axes.Y,
                Width = initialMetrics.InspectorWidth,
                Margin = new MarginPadding { Left = initialMetrics.PanelGap },
                Padding = new MarginPadding { Top = 1, Bottom = 1 },
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Child = createInspectorPanel()
            };

            previewInspectorGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                RowDimensions = new[]
                {
                    new Dimension()
                },
                ColumnDimensions = new[]
                {
                    new Dimension(),
                    new Dimension(GridSizeMode.Absolute, initialMetrics.InspectorWidth)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        previewCellContainer,
                        inspectorContainer
                    }
                }
            };

            timelineLayoutGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, timelineToolboxRowHeight),
                    new Dimension()
                },
                Content = new[]
                {
                    new Drawable[] { createTimelineToolbox() },
                    new Drawable[] { timeline }
                }
            };

            var timelineSurface = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 16,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.TimelineBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.1f
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 15, Vertical = 14 },
                        Child = timelineLayoutGrid
                    }
                }
            };

            editorLayoutGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, timelineSurfaceHeight),
                    new Dimension()
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Padding = new MarginPadding { Bottom = 8 },
                            Child = timelineSurface
                        }
                    },
                    new Drawable[]
                    {
                        previewInspectorGrid
                    }
                }
            };

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 8, Vertical = 10 },
                Child = editorLayoutGrid
            };
        }

        private Drawable createInspectorPanel()
        {
            inspectorTextBoxes.Clear();
            inspectorActionButtons.Clear();
            inspectorActionButtonTexts.Clear();
            inspectorActionLayouts.Clear();
            inspectorSliders.Clear();
            inspectorSectionBodies.Clear();
            inspectorFieldFlows.Clear();
            inspectorSectionTitleTexts.Clear();
            inspectorFieldLabelTexts.Clear();
            var inspectorCopy = EditorInspectorCopy.Active;

            releaseInput = createInspectorTextBox(inspectorCopy.PlaceholderRelease);
            releaseInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.ReleaseDate = e.NewValue);

            providerInput = createInspectorTextBox(inspectorCopy.PlaceholderProvider);
            providerInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Provider = e.NewValue ?? string.Empty);

            descriptionInput = createInspectorTextBox(inspectorCopy.PlaceholderDescription);
            descriptionInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Description = e.NewValue ?? string.Empty);

            titleInput = createInspectorTextBox("Song title");
            titleInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Title = e.NewValue ?? string.Empty, refreshStatus: true);

            artistInput = createInspectorTextBox("Artist");
            artistInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Artist = e.NewValue ?? string.Empty, refreshStatus: true);

            creatorInput = createInspectorTextBox("Mapper");
            creatorInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Creator = e.NewValue ?? string.Empty);

            sourceInput = createInspectorTextBox("Source/Album");
            sourceInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Source = string.IsNullOrWhiteSpace(e.NewValue) ? null : e.NewValue);

            tagsInput = createInspectorTextBox("tag1, tag2");
            tagsInput.Current.ValueChanged += e => applyMetadataChange(meta =>
            {
                meta.Tags = string.IsNullOrWhiteSpace(e.NewValue)
                    ? new List<string>()
                    : e.NewValue!.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                        .Select(tag => tag.ToLowerInvariant())
                        .ToList();
            });

            bpmInput = createInspectorTextBox(inspectorCopy.PlaceholderBpm);
            bpmInput.Current.ValueChanged += e => applyBpmText(e.NewValue);

            offsetInput = createInspectorTextBox(inspectorCopy.PlaceholderOffset);
            offsetInput.Current.ValueChanged += e => applyOffsetText(e.NewValue);

            var titleArtistRow = createInspectorFieldPair(("Title", titleInput), ("Artist", artistInput));
            var creatorSourceRow = createInspectorFieldPair(("Creator", creatorInput), ("Source", sourceInput));
            var releaseProviderRow = createInspectorFieldPair((inspectorCopy.LabelRelease, releaseInput), (inspectorCopy.LabelProvider, providerInput));

            inspectorMetadataSection = createInspectorSection(inspectorCopy.SectionMetadata,
                titleArtistRow,
                creatorSourceRow,
                createInspectorField("Tags", tagsInput),
                releaseProviderRow,
                createInspectorField(inspectorCopy.LabelDescription, descriptionInput));

            var timingPairRow = createInspectorFieldPair(("BPM", bpmInput), ("Offset", offsetInput));
            inspectorTimingSection = createInspectorSection(inspectorCopy.SectionEdit,
                createInspectorField("Selection", createSelectionPanel(inspectorCopy)),
                timingPairRow,
                createInspectorButtonRow(("Half", () => adjustBpmByFactor(0.5)), ("x2", () => adjustBpmByFactor(2)), ("Reset", resetBpmToDefault)));

            var notesBadge = createInspectorStatBadge("Notes", out noteCountValue);
            var lengthBadge = createInspectorStatBadge("Length", out mapLengthValue);
            var densityBadge = createInspectorStatBadge("Density", out densityValue);
            var bpmBadge = createInspectorStatBadge("Active BPM", out bpmStatValue);

            var statsGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize),
                    new Dimension(GridSizeMode.AutoSize)
                },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.5f),
                    new Dimension(GridSizeMode.Relative, 0.5f)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createInspectorGridCell(notesBadge, rightPadding: 4),
                        createInspectorGridCell(lengthBadge, leftPadding: 4)
                    },
                    new Drawable[]
                    {
                        createInspectorGridCell(densityBadge, rightPadding: 4),
                        createInspectorGridCell(bpmBadge, leftPadding: 4)
                    }
                }
            };

            inspectorStatsSection = createInspectorSection(inspectorCopy.SectionStats, statsGrid);

            var generationQuantization = new BeatSight.Game.UI.Components.Dropdown<string>
            {
                RelativeSizeAxes = Axes.X,
                Items = new[] { "quarter", "eighth", "sixteenth", "thirty_second" },
                Current = quantizationGrid
            };

            var generationTopRow = createInspectorFieldPair(
                ("Grid", generationQuantization),
                ("Snap (ms)", createGenerationSlider(maxSnapError, value => $"{value:0.0} ms")));
            var generationSensitivityRow = createInspectorFieldPair(
                ("Confidence", createGenerationSlider(confidenceThreshold, value => $"{value:P0} ({value:0.00})")),
                ("Sensitivity", createGenerationSlider(detectionSensitivity, value => $"{value:0}")));

            var generationTogglesRow = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize)
                },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.34f),
                    new Dimension(GridSizeMode.Relative, 0.33f),
                    new Dimension(GridSizeMode.Relative, 0.33f)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createInspectorGridCell(new BeatSightCheckbox { Current = isolateDrums, LabelText = "Isolate", LabelFontSize = 11.2f }, rightPadding: 4),
                        createInspectorGridCell(new BeatSightCheckbox { Current = forceQuantization, LabelText = "Force Quant.", LabelFontSize = 11.2f }, leftPadding: 2, rightPadding: 2),
                        createInspectorGridCell(new BeatSightCheckbox { Current = useMlClassifier, LabelText = "ML Classifier", LabelFontSize = 11.2f }, leftPadding: 4)
                    }
                }
            };

            inspectorGenerationSection = createInspectorSection(inspectorCopy.SectionAi,
                generationTopRow,
                generationSensitivityRow,
                generationTogglesRow,
                createInspectorField(inspectorCopy.LabelTempoHints, tempoHintsInput = createInspectorTextBox(inspectorCopy.PlaceholderTempoHints)),
                new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(9, 0),
                    Children = new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Width = 0.68f,
                            Height = 38,
                            Child = new BeatSightButton
                            {
                                RelativeSizeAxes = Axes.Both,
                                Text = "Run Pipeline",
                                BackgroundColour = UITheme.AccentPrimary,
                                Action = runPipeline
                            }
                        },
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Width = 0.32f,
                            Height = 38,
                            Child = new BeatSightButton
                            {
                                RelativeSizeAxes = Axes.Both,
                                Text = "Logs",
                                BackgroundColour = EditorColours.ControlsBackground,
                                Action = () => logOverlay.FadeIn(200)
                            }
                        }
                    }
                });

            inspectorSectionsByKey.Clear();
            inspectorSectionsByKey[EditorInspectorSectionKey.Metadata] = inspectorMetadataSection;
            inspectorSectionsByKey[EditorInspectorSectionKey.Edit] = inspectorTimingSection;
            inspectorSectionsByKey[EditorInspectorSectionKey.Stats] = inspectorStatsSection;
            inspectorSectionsByKey[EditorInspectorSectionKey.Ai] = inspectorGenerationSection;

            var sections = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(12),
                Padding = new MarginPadding { Horizontal = 12, Vertical = 12 },
                Children = getInspectorSectionsInOrder(compactOrder: false)
            };
            inspectorSectionsFlow = sections;

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 15,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.InspectorBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.12f
                    },
                    new PassiveScrollContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Child = new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Child = sections
                        }
                    }
                }
            };
        }

        private Drawable createSelectionPanel(EditorInspectorCopyProfile inspectorCopy)
        {
            selectionSummaryText = new SpriteText
            {
                Text = inspectorCopy.SelectionNoneText,
                Font = BeatSightFont.Caption(13.4f),
                Colour = EditorColours.TextSecondary,
                RelativeSizeAxes = Axes.X,
                AllowMultiline = true
            };
            componentReassignDropdown = new BeatSight.Game.UI.Components.Dropdown<string>
            {
                RelativeSizeAxes = Axes.X,
                Items = Array.Empty<string>(),
                Current = componentReassignSelection
            };
            refreshComponentReassignmentOptions();

            var navigationRow = createInspectorButtonRow(("Prev", () => jumpToAdjacentNote(false)), ("Next", () => jumpToAdjacentNote(true)), ("Center", centerOnSelection));
            var selectionRow = createInspectorButtonRow((inspectorCopy.SelectionButton, selectAllNotes), (inspectorCopy.QuantizeButton, quantizeSelectedToGrid));
            var transientRow = createInspectorButtonRow(("Snap Audio", snapSelectionToTransient));
            var manuscriptLaneRow = createInspectorButtonRow(("Notation -", () => shiftSelectionToAdjacentNotationLane(false)), ("Notation +", () => shiftSelectionToAdjacentNotationLane(true)));
            var manuscriptArticulationRow = createInspectorButtonRow(
                ("Ghost", () => applyNotationArticulationPreset(NotationArticulationPreset.Ghost)),
                ("Normal", () => applyNotationArticulationPreset(NotationArticulationPreset.Normal)),
                ("Accent", () => applyNotationArticulationPreset(NotationArticulationPreset.Accent)));
            var editRow = createInspectorButtonRow((inspectorCopy.DuplicateButton, duplicateSelectedNote), (inspectorCopy.DeleteButton, deleteSelectedNote));
            var adjustmentRow = createInspectorButtonGrid(2,
                ("Nudge -", () => nudgeSelectedNote(false)),
                ("Nudge +", () => nudgeSelectedNote(true)),
                ("Vel -", () => adjustSelectedVelocity(false)),
                ("Vel +", () => adjustSelectedVelocity(true)));
            var shortcutHint = new SpriteText
            {
                Text = inspectorCopy.ShortcutHint,
                Font = BeatSightFont.Caption(10.8f),
                Colour = EditorColours.TextMuted,
                AllowMultiline = true,
                RelativeSizeAxes = Axes.X
            };
            var componentRow = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize)
                },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.66f),
                    new Dimension(GridSizeMode.Relative, 0.34f)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Padding = new MarginPadding { Right = 6 },
                            Child = componentReassignDropdown
                        },
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Child = createInspectorButton(inspectorCopy.ReassignApplyButton, reassignSelectedComponent, fillWidth: true)
                        }
                    }
                }
            };

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(7),
                Children = new Drawable[]
                {
                    selectionSummaryText,
                    selectionRow,
                    navigationRow,
                    adjustmentRow,
                    componentRow,
                    manuscriptLaneRow,
                    manuscriptArticulationRow,
                    transientRow,
                    editRow,
                    shortcutHint
                }
            };
        }

        private BeatSightTextBox createInspectorTextBox(string placeholder)
        {
            var textBox = new BeatSightTextBox
            {
                RelativeSizeAxes = Axes.X,
                Height = 36,
                PlaceholderText = placeholder,
                CornerRadius = 8,
                FontSize = 13.8f
            };
            inspectorTextBoxes.Add(textBox);
            return textBox;
        }

        private Drawable createGenerationSlider(BindableDouble bindable, Func<double, string> formatter)
        {
            var slider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 26,
                Current = bindable,
                DragStepMultiplier = 1,
                KeyboardStepMultiplier = 1
            };
            inspectorSliders.Add(slider);

            var valueText = new SpriteText
            {
                Font = BeatSightFont.Caption(10.8f),
                Colour = EditorColours.TextSecondary,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Text = formatter(bindable.Value)
            };

            var minText = new SpriteText
            {
                Font = BeatSightFont.Caption(10f),
                Colour = EditorColours.TextMuted,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Text = bindable.MinValue.ToString("0.##", CultureInfo.InvariantCulture)
            };

            var maxText = new SpriteText
            {
                Font = BeatSightFont.Caption(10f),
                Colour = EditorColours.TextMuted,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Text = bindable.MaxValue.ToString("0.##", CultureInfo.InvariantCulture)
            };

            bindable.BindValueChanged(e =>
            {
                valueText.Text = formatter(e.NewValue);
            }, true);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(4, 0),
                Children = new Drawable[]
                {
                    slider,
                    new GridContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 15,
                        ColumnDimensions = new[]
                        {
                            new Dimension(GridSizeMode.Relative, 0.25f),
                            new Dimension(GridSizeMode.Relative, 0.5f),
                            new Dimension(GridSizeMode.Relative, 0.25f)
                        },
                        Content = new[]
                        {
                            new Drawable[]
                            {
                                minText,
                                valueText,
                                maxText
                            }
                        }
                    }
                }
            };
        }

        private void updateSelectionSummary()
        {
            syncManuscriptFocus();

            if (selectionSummaryText == null)
                return;

            string noSelectionText = EditorInspectorCopy.Active.SelectionNoneText;

            if (selectedHitObject != null)
            {
                string laneText = selectedHitObject.Lane.HasValue ? (selectedHitObject.Lane.Value + 1).ToString() : "?";
                string articulation = getNotationPresetLabel(getNotationPresetFromVelocity(selectedHitObject.Velocity));
                selectionSummaryText.Text = $"{selectedHitObject.Component} | Lane {laneText} | {articulation} @ {formatTime(selectedHitObject.Time)}";
                selectionSummaryText.Colour = EditorColours.TextPrimary;
                return;
            }

            if (tryGetSelectionRange(out double start, out double end))
            {
                int noteCount = beatmap?.HitObjects.Count(hit => hit.Time >= start && hit.Time <= end) ?? 0;
                selectionSummaryText.Text = noteCount > 0
                    ? $"{noteCount} notes in range {formatTime(start)} - {formatTime(end)}"
                    : $"Range {formatTime(start)} - {formatTime(end)} (no notes)";
                selectionSummaryText.Colour = noteCount > 0 ? EditorColours.TextPrimary : EditorColours.TextSecondary;
                return;
            }

            if (beatmap?.HitObjects.Count > 0)
            {
                var nextHit = beatmap.HitObjects
                    .Where(hit => hit.Time >= currentTime)
                    .OrderBy(hit => hit.Time)
                    .FirstOrDefault();

                if (nextHit != null)
                {
                    selectionSummaryText.Text = $"{noSelectionText} | Next @ {formatTime(nextHit.Time)}";
                    selectionSummaryText.Colour = EditorColours.TextSecondary;
                    return;
                }

                int lastHit = beatmap.HitObjects.Max(hit => hit.Time);
                selectionSummaryText.Text = $"{noSelectionText} | Past final note ({formatTime(lastHit)})";
                selectionSummaryText.Colour = EditorColours.TextSecondary;
                return;
            }

            selectionSummaryText.Text = noSelectionText;
            selectionSummaryText.Colour = EditorColours.TextSecondary;
        }

        private void syncManuscriptFocus()
        {
            if (playbackPreview == null || previewMode == null)
                return;

            if (previewMode.Value != EditorPreviewMode.Manuscript)
            {
                playbackPreview.SetManuscriptFocusComponent(null);
                return;
            }

            if (selectedHitObject != null)
            {
                playbackPreview.SetManuscriptFocusComponent(selectedHitObject.Component);
                return;
            }

            if (tryGetSelectionRange(out double start, out double end))
            {
                string? selectionComponent = resolveSelectionFocusComponent(start, end);
                playbackPreview.SetManuscriptFocusComponent(selectionComponent);
                return;
            }

            string? nextComponent = beatmap?.HitObjects
                .Where(hit => hit.Time >= currentTime)
                .OrderBy(hit => hit.Time)
                .Select(hit => hit.Component)
                .FirstOrDefault();

            playbackPreview.SetManuscriptFocusComponent(nextComponent);
        }

        private string? resolveSelectionFocusComponent(double start, double end)
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
                return null;

            var selectionHits = beatmap.HitObjects
                .Where(hit => hit.Time >= start && hit.Time <= end)
                .ToList();

            if (selectionHits.Count == 0)
                return null;

            return selectionHits
                .OrderBy(hit => Math.Abs(hit.Time - currentTime))
                .Select(hit => hit.Component)
                .FirstOrDefault();
        }

        private bool tryGetSelectionRange(out double start, out double end)
        {
            start = 0;
            end = 0;

            if (timeline?.SelectionStart is not double selectionStart || timeline.SelectionEnd is not double selectionEnd)
                return false;

            start = Math.Min(selectionStart, selectionEnd);
            end = Math.Max(selectionStart, selectionEnd);
            return end - start >= 1;
        }

        private List<HitObject> getSelectedHitObjectsForEditing(out bool fromRange, out double rangeStart, out double rangeEnd)
        {
            fromRange = false;
            rangeStart = 0;
            rangeEnd = 0;

            if (beatmap == null)
                return new List<HitObject>();

            if (selectedHitObject != null && beatmap.HitObjects.Contains(selectedHitObject))
                return new List<HitObject> { selectedHitObject };

            if (tryGetSelectionRange(out rangeStart, out rangeEnd))
            {
                fromRange = true;
                double start = rangeStart;
                double end = rangeEnd;
                return beatmap.HitObjects
                    .Where(hit => hit.Time >= start && hit.Time <= end)
                    .OrderBy(hit => hit.Time)
                    .ToList();
            }

            return new List<HitObject>();
        }

        private void refreshComponentReassignmentOptions()
        {
            if (componentReassignDropdown == null)
                return;

            var options = new List<string>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            void addOption(string? component)
            {
                if (string.IsNullOrWhiteSpace(component))
                    return;

                string normalized = component.Trim();
                if (seen.Add(normalized))
                    options.Add(normalized);
            }

            foreach (string component in defaultComponentReassignmentOptions)
                addOption(component);

            if (beatmap?.DrumKit?.Components != null)
            {
                foreach (string component in beatmap.DrumKit.Components)
                    addOption(component);
            }

            if (beatmap != null)
            {
                foreach (string component in beatmap.HitObjects.Select(hit => hit.Component))
                    addOption(component);
            }

            if (options.Count == 0)
                options.Add("kick");

            componentReassignDropdown.Items = options.ToArray();

            string currentSelection = componentReassignSelection.Value ?? string.Empty;
            string? resolvedSelection = options.FirstOrDefault(option => string.Equals(option, currentSelection, StringComparison.OrdinalIgnoreCase));
            componentReassignSelection.Value = resolvedSelection ?? options[0];
        }

        private void adjustBpmByFactor(double factor)
        {
            if (beatmap == null)
                return;

            setBpm(beatmap.Timing.Bpm * factor);
            suppressInspectorFieldSync = true;
            bpmInput.Current.Value = beatmap.Timing.Bpm.ToString("0.##", CultureInfo.InvariantCulture);
            suppressInspectorFieldSync = false;
        }

        private void resetBpmToDefault()
        {
            double target = initialBeatmapBpm ?? 120;
            setBpm(target);
            suppressInspectorFieldSync = true;
            bpmInput.Current.Value = target.ToString("0.##", CultureInfo.InvariantCulture);
            suppressInspectorFieldSync = false;
        }

        private void jumpToFirstNote()
            => jumpToBoundaryNote(forward: true);

        private void jumpToLastNote()
            => jumpToBoundaryNote(forward: false);

        private void jumpToBoundaryNote(bool forward)
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
            {
                appendStatusDetail("No notes available");
                return;
            }

            var target = forward
                ? beatmap.HitObjects.MinBy(hit => hit.Time)
                : beatmap.HitObjects.MaxBy(hit => hit.Time);

            if (target == null)
            {
                appendStatusDetail("No notes available");
                return;
            }

            if (timeline?.TrySelectHitObject(target) != true)
                onTimelineNoteSelected(target);

            seekToTime(target.Time);
            appendStatusDetail(forward ? $"Jumped to first note ({formatTime(target.Time)})" : $"Jumped to last note ({formatTime(target.Time)})");
        }

        private void jumpToAdjacentNote(bool forward)
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
            {
                appendStatusDetail("No notes available");
                return;
            }

            int index = selectedHitObject != null ? beatmap.HitObjects.IndexOf(selectedHitObject) : -1;
            if (index < 0)
            {
                index = beatmap.HitObjects.FindLastIndex(h => h.Time <= currentTime);
            }

            if (index < 0)
                index = forward ? 0 : beatmap.HitObjects.Count - 1;
            else
                index = Math.Clamp(index + (forward ? 1 : -1), 0, beatmap.HitObjects.Count - 1);

            var target = beatmap.HitObjects[index];
            if (timeline?.TrySelectHitObject(target) != true)
                onTimelineNoteSelected(target);

            seekToTime(target.Time);
        }

        private void centerOnSelection()
        {
            if (selectedHitObject != null)
            {
                if (timeline?.TrySelectHitObject(selectedHitObject) != true)
                    seekToTime(selectedHitObject.Time);
                return;
            }

            if (tryGetSelectionRange(out double start, out double end))
            {
                seekToTime((start + end) / 2.0);
                appendStatusDetail("Centered on selection range");
                return;
            }

            appendStatusDetail("No selection to center");
        }

        private void selectAllNotes()
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
            {
                appendStatusDetail("No notes available");
                return;
            }

            if (beatmap.HitObjects.Count == 1)
            {
                var onlyHit = beatmap.HitObjects[0];
                selectedHitObject = onlyHit;
                timeline?.TrySelectHitObject(onlyHit);
                seekToTime(onlyHit.Time);
                appendStatusDetail("Selected 1 note");
                return;
            }

            double start = beatmap.HitObjects.Min(hit => hit.Time);
            double end = beatmap.HitObjects.Max(hit => hit.Time);

            selectedHitObject = null;
            timeline?.SetSelectionRange(start, end);
            seekToTime(start);
            appendStatusDetail($"Selected all notes ({beatmap.HitObjects.Count})");
            updateSelectionSummary();
        }

        private void quantizeSelectedToGrid()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to quantize");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to quantize");
                return;
            }

            double interval = getSnapIntervalMs();
            int maxTime = trackLength > 0 ? (int)Math.Round(trackLength) : int.MaxValue;

            var changes = targets
                .Select(hit => new
                {
                    Hit = hit,
                    Snapped = (int)Math.Round(Math.Clamp(Math.Round(hit.Time / interval) * interval, 0, maxTime))
                })
                .Where(change => change.Snapped != change.Hit.Time)
                .ToList();

            if (changes.Count == 0)
            {
                appendStatusDetail($"Selection already quantized to 1/{snapDivisor}");
                return;
            }

            prepareUndoSnapshot();

            foreach (var change in changes)
                change.Hit.Time = change.Snapped;

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            seekToTime(targets.Min(hit => hit.Time));
            appendStatusDetail($"Quantized {changes.Count} note{(changes.Count == 1 ? string.Empty : "s")} to 1/{snapDivisor}");
        }

        private void snapSelectionToTransient()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to snap");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to snap");
                return;
            }

            if (timeline == null)
            {
                appendStatusDetail("Timeline unavailable");
                return;
            }

            if (!timeline.HasDetectedOnsets)
            {
                appendStatusDetail("No transient markers loaded");
                return;
            }

            int snappedCount = timeline.SnapSelectedNoteToTransient();
            if (snappedCount <= 0)
            {
                appendStatusDetail("No selected notes were close enough to transients");
                return;
            }

            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Snapped {snappedCount} note{(snappedCount == 1 ? string.Empty : "s")} to nearest transients");
        }

        private void adjustSelectedVelocity(bool increase)
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to adjust velocity");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to adjust velocity");
                return;
            }

            const double velocityStep = 0.05;
            double delta = increase ? velocityStep : -velocityStep;

            var changes = targets
                .Select(hit => new
                {
                    Hit = hit,
                    Adjusted = Math.Clamp(hit.Velocity + delta, 0.05, 1.0)
                })
                .Where(change => Math.Abs(change.Adjusted - change.Hit.Velocity) > 0.0001)
                .ToList();

            if (changes.Count == 0)
            {
                appendStatusDetail(increase ? "Velocity already at max" : "Velocity already at min");
                return;
            }

            prepareUndoSnapshot();

            foreach (var change in changes)
                change.Hit.Velocity = change.Adjusted;

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Adjusted velocity {(increase ? "up" : "down")} for {changes.Count} note{(changes.Count == 1 ? string.Empty : "s")}");
        }

        private void restoreSelectionAfterBatchEdit(IReadOnlyList<HitObject> targets, bool fromRange)
        {
            if (targets.Count == 1)
            {
                selectedHitObject = targets[0];
                timeline?.TrySelectHitObject(selectedHitObject);
                return;
            }

            selectedHitObject = null;

            if (!fromRange || targets.Count <= 1)
                return;

            double start = targets.Min(hit => hit.Time);
            double end = targets.Max(hit => hit.Time);
            timeline?.SetSelectionRange(start, end);
        }

        private void duplicateSelectedNote()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to duplicate");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out double rangeStart, out double rangeEnd);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to duplicate");
                return;
            }

            prepareUndoSnapshot();

            int maxTime = trackLength > 0 ? (int)Math.Round(trackLength) : int.MaxValue;
            int offsetMs = (int)Math.Round(getSnapIntervalMs());
            if (fromRange)
            {
                int rangeDuration = (int)Math.Round(Math.Max(0, rangeEnd - rangeStart));
                offsetMs = Math.Max(offsetMs, rangeDuration);
            }

            var clones = new List<HitObject>(targets.Count);
            foreach (var source in targets)
            {
                clones.Add(new HitObject
                {
                    Component = source.Component,
                    Lane = source.Lane,
                    Velocity = source.Velocity,
                    Duration = source.Duration,
                    Time = Math.Clamp(source.Time + offsetMs, 0, maxTime)
                });
            }

            beatmap.HitObjects.AddRange(clones);
            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(clones, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            seekToTime(clones.Min(clone => clone.Time));
            appendStatusDetail($"Duplicated {clones.Count} note{(clones.Count == 1 ? string.Empty : "s")}");
        }

        private void deleteSelectedNote()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to delete");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out double rangeStart, out double rangeEnd);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to delete");
                return;
            }

            prepareUndoSnapshot();

            var removalSet = new HashSet<HitObject>(targets);
            int removed = beatmap.HitObjects.RemoveAll(hit => removalSet.Contains(hit));
            if (removed <= 0)
            {
                appendStatusDetail("Unable to delete selected notes");
                return;
            }

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            selectedHitObject = null;
            markUnsaved();
            reloadTimeline();
            if (fromRange && removed > 1 && rangeEnd - rangeStart >= 1)
                timeline?.SetSelectionRange(rangeStart, rangeEnd);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Deleted {removed} note{(removed == 1 ? string.Empty : "s")}");
        }

        private void nudgeSelectedNote(bool forward)
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to nudge");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to nudge");
                return;
            }

            prepareUndoSnapshot();

            double delta = forward ? getSnapIntervalMs() : -getSnapIntervalMs();
            int maxTime = trackLength > 0 ? (int)Math.Round(trackLength) : int.MaxValue;

            foreach (var hit in targets)
                hit.Time = (int)Math.Round(Math.Clamp(hit.Time + delta, 0, maxTime));

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();

            if (targets.Count == 1)
            {
                selectedHitObject = targets[0];
                timeline?.RefreshHitObject(selectedHitObject);
                seekToTime(selectedHitObject.Time);
            }
            else
            {
                reloadTimeline();
                restoreSelectionAfterBatchEdit(targets, fromRange);
                seekToTime(targets.Min(hit => hit.Time));
            }

            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Nudged {targets.Count} note{(targets.Count == 1 ? string.Empty : "s")} {(forward ? "forward" : "backward")}");
        }

        private void reassignSelectedComponent()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to reassign");
                return;
            }

            string targetComponent = componentReassignSelection.Value?.Trim() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(targetComponent))
            {
                appendStatusDetail("Choose an instrument type first");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to reassign");
                return;
            }

            int pendingChanges = targets.Count(hit =>
                !string.Equals(hit.Component, targetComponent, StringComparison.OrdinalIgnoreCase)
                || hit.Lane.HasValue);

            if (pendingChanges == 0)
            {
                appendStatusDetail($"Selection already uses {targetComponent}");
                return;
            }

            prepareUndoSnapshot();

            foreach (var hit in targets)
            {
                hit.Component = targetComponent;
                // Let playback/editor lane heuristics re-resolve from the updated component.
                hit.Lane = null;
            }

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);

            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Reassigned {targets.Count} note{(targets.Count == 1 ? string.Empty : "s")} to {targetComponent}");
        }

        private void shiftSelectionToAdjacentNotationLane(bool towardHigher)
        {
            if (previewMode?.Value != EditorPreviewMode.Manuscript)
            {
                appendStatusDetail("Switch to Sheet Music view to use notation lane shift");
                return;
            }

            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to move");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to move");
                return;
            }

            int direction = towardHigher ? 1 : -1;
            int changed = 0;

            prepareUndoSnapshot();

            foreach (var hit in targets)
            {
                string nextComponent = ManuscriptBackgroundEnhanced.GetAdjacentNotationComponent(hit.Component, direction);
                if (string.Equals(hit.Component, nextComponent, StringComparison.OrdinalIgnoreCase) && !hit.Lane.HasValue)
                    continue;

                hit.Component = nextComponent;
                // Let lane heuristics remap to the current lane layout.
                hit.Lane = null;
                changed++;
            }

            if (changed == 0)
            {
                appendStatusDetail(towardHigher
                    ? "Selection already at highest notation lane"
                    : "Selection already at lowest notation lane");
                return;
            }

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Moved {changed} note{(changed == 1 ? string.Empty : "s")} {(towardHigher ? "up" : "down")} in sheet notation");
        }

        private void applyNotationArticulationPreset(NotationArticulationPreset preset)
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to set articulation");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to set articulation");
                return;
            }

            double targetVelocity = getNotationVelocityForPreset(preset);
            var changes = targets
                .Where(hit => Math.Abs(hit.Velocity - targetVelocity) > 0.0001)
                .ToList();

            if (changes.Count == 0)
            {
                appendStatusDetail($"Selection already set to {getNotationPresetLabel(preset)} articulation");
                return;
            }

            prepareUndoSnapshot();

            foreach (var hit in changes)
                hit.Velocity = targetVelocity;

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Set {changes.Count} note{(changes.Count == 1 ? string.Empty : "s")} to {getNotationPresetLabel(preset)} articulation");
        }

        private void cycleNotationArticulationPreset(bool towardAccent)
        {
            if (beatmap == null)
            {
                appendStatusDetail("Select a note or range to shift articulation");
                return;
            }

            var targets = getSelectedHitObjectsForEditing(out bool fromRange, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to shift articulation");
                return;
            }

            int direction = towardAccent ? 1 : -1;
            var changes = new List<(HitObject Hit, NotationArticulationPreset Preset, double Velocity)>(targets.Count);

            foreach (var hit in targets)
            {
                var currentPreset = getNotationPresetFromVelocity(hit.Velocity);
                int nextIndex = Math.Clamp((int)currentPreset + direction, 0, 2);
                var nextPreset = (NotationArticulationPreset)nextIndex;
                double nextVelocity = getNotationVelocityForPreset(nextPreset);
                if (Math.Abs(nextVelocity - hit.Velocity) <= 0.0001)
                    continue;

                changes.Add((hit, nextPreset, nextVelocity));
            }

            if (changes.Count == 0)
            {
                appendStatusDetail(towardAccent
                    ? "Selection already at accent articulation"
                    : "Selection already at ghost articulation");
                return;
            }

            prepareUndoSnapshot();

            foreach (var change in changes)
                change.Hit.Velocity = change.Velocity;

            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();
            reloadTimeline();
            restoreSelectionAfterBatchEdit(targets, fromRange);
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Shifted articulation {(towardAccent ? "up" : "down")} for {changes.Count} note{(changes.Count == 1 ? string.Empty : "s")}");
        }

        private static NotationArticulationPreset getNotationPresetFromVelocity(double velocity)
        {
            if (velocity <= (notationGhostVelocity + notationNormalVelocity) * 0.5)
                return NotationArticulationPreset.Ghost;

            if (velocity >= (notationNormalVelocity + notationAccentVelocity) * 0.5)
                return NotationArticulationPreset.Accent;

            return NotationArticulationPreset.Normal;
        }

        private static double getNotationVelocityForPreset(NotationArticulationPreset preset)
        {
            return preset switch
            {
                NotationArticulationPreset.Ghost => notationGhostVelocity,
                NotationArticulationPreset.Accent => notationAccentVelocity,
                _ => notationNormalVelocity
            };
        }

        private static string getNotationPresetLabel(NotationArticulationPreset preset)
        {
            return preset switch
            {
                NotationArticulationPreset.Ghost => "ghost",
                NotationArticulationPreset.Accent => "accent",
                _ => "normal"
            };
        }

        private double getSnapIntervalMs()
        {
            if (beatmap == null || beatmap.Timing.Bpm <= 0 || snapDivisor <= 0)
                return 100;

            return 60000.0 / beatmap.Timing.Bpm / snapDivisor;
        }

        private double resolvePreferredStartTime(out string? startContextDetail)
        {
            startContextDetail = null;

            if (beatmap == null)
                return 0;

            double duration = trackLength > 0
                ? trackLength
                : Math.Max(beatmap.Audio.Duration, beatmap.HitObjects.Count > 0 ? beatmap.HitObjects[^1].Time + 2000 : 0);

            if (beatmap.HitObjects.Count == 0)
            {
                if (beatmap.Metadata.PreviewTime.HasValue && beatmap.Metadata.PreviewTime.Value > 0)
                    return Math.Clamp(beatmap.Metadata.PreviewTime.Value, 0, duration > 0 ? duration : beatmap.Metadata.PreviewTime.Value);

                return 0;
            }

            int firstHit = beatmap.HitObjects.Min(h => h.Time);
            double firstHitStart = Math.Clamp(firstHit - firstNoteLeadInMs, 0, duration > 0 ? duration : firstHit);

            if (beatmap.Metadata.PreviewTime.HasValue && beatmap.Metadata.PreviewTime.Value > 0)
            {
                double previewStart = Math.Clamp(beatmap.Metadata.PreviewTime.Value, 0, duration > 0 ? duration : beatmap.Metadata.PreviewTime.Value);
                bool hasNearbyNotes = beatmap.HitObjects.Any(hit =>
                    hit.Time >= previewStart - previewStartLookBehindMs
                    && hit.Time <= previewStart + previewStartLookAheadMs);

                if (hasNearbyNotes)
                    return previewStart;

                if (Math.Abs(firstHitStart - previewStart) > 1)
                    startContextDetail = $"Preview moved to first note context ({formatTime(firstHit)})";

                return firstHitStart;
            }

            return firstHitStart;
        }

        private double getEffectivePlaybackLength()
        {
            if (trackLength > 0)
                return trackLength;

            if (beatmap == null)
                return 0;

            double metadataDuration = Math.Max(0, beatmap.Audio.Duration);
            double lastNoteDuration = beatmap.HitObjects.Count > 0
                ? beatmap.HitObjects.Max(hit => (double)hit.Time) + 2000
                : 0;

            return Math.Max(metadataDuration, lastNoteDuration);
        }

        private void seekToTime(double timeMs)
        {
            double effectiveLength = getEffectivePlaybackLength();
            double target = Math.Clamp(timeMs, 0, effectiveLength > 0 ? effectiveLength : Math.Max(timeMs, 0));
            currentTime = target;
            track?.Seek(target);
            lastTrackTime = track?.CurrentTime ?? target;
            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);
            playbackPreview?.JumpToTime(currentTime);
        }

        // EditorSnapshot class extracted to EditorCommandManager.cs

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            uiAudio.PlayTransition();

            // Animate timeline from bottom
            if (timeline != null)
                timeline.MoveToY(100).FadeInFromZero(500).MoveToY(0, 800, Easing.OutQuint);

            // Animate preview from top
            if (playbackPreview != null)
                playbackPreview.MoveToY(-100).FadeInFromZero(500).MoveToY(0, 800, Easing.OutQuint);

            // Animate history panel from right
            if (historyPanel != null && historyPanel.Alpha > 0.01f)
                historyPanel.MoveToX(100).FadeInFromZero(500).MoveToX(0, 800, Easing.OutQuint);

            // Animate back button
            if (backButton != null)
                backButton.ScaleTo(0).Delay(200).ScaleTo(1, 600, Easing.OutElastic);
        }

        protected override void Update()
        {
            base.Update();
            applyResponsiveEditorLayout();
            refreshInspectorActionLabelWidths();

            if (isPlaying)
            {
                if (track != null)
                {
                    double newTime = track.CurrentTime;
                    if (track.IsRunning && newTime > lastTrackTime)
                        currentTime = newTime;
                    else
                        currentTime = Math.Max(0, currentTime + Time.Elapsed);

                    lastTrackTime = newTime;
                }
                else
                {
                    currentTime = Math.Max(0, currentTime + Time.Elapsed);
                }
            }

            double effectiveLength = getEffectivePlaybackLength();
            if (effectiveLength > 0)
                currentTime = Math.Clamp(currentTime, 0, effectiveLength);

            if (isPlaying
                && effectiveLength > 0
                && currentTime >= effectiveLength - 1
                && (track == null || !track.IsRunning))
            {
                stopPlayback(silent: true);
                currentTime = effectiveLength;
                appendStatusDetail("Playback finished");
            }

            if (timelineZoomInteractionActive
                && pendingTimelineZoomPreview.HasValue
                && Time.Current - lastTimelineZoomPreviewAppliedAt >= timelineZoomPreviewMinIntervalMs)
            {
                applyTimelineZoomPreviewNow(pendingTimelineZoomPreview.Value, Time.Current);
            }

            if (waveformScaleInteractionActive
                && pendingWaveformScalePreview.HasValue
                && Time.Current - lastWaveformScalePreviewAppliedAt >= waveformScalePreviewMinIntervalMs)
            {
                applyWaveformScalePreviewNow(pendingWaveformScalePreview.Value, Time.Current);
            }

            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime, ensureVisible: isPlaying);

            if (previewMode?.Value == EditorPreviewMode.Manuscript
                && Time.Current - lastManuscriptFocusSyncAt >= manuscriptFocusSyncIntervalMs)
            {
                syncManuscriptFocus();
                lastManuscriptFocusSyncAt = Time.Current;
            }
        }

        private void refreshInspectorActionLabelWidths()
        {
            foreach (var layout in inspectorActionLayouts)
            {
                float buttonWidth = layout.FillWidth ? layout.Button.DrawWidth : layout.WidthHint;
                if (buttonWidth <= 1f && layout.Button.Parent != null)
                    buttonWidth = layout.Button.Parent.DrawWidth;

                float targetMaxWidth = Math.Max(24f, buttonWidth - 14f);
                if (Math.Abs(layout.Label.MaxWidth - targetMaxWidth) > 0.2f)
                    layout.Label.MaxWidth = targetMaxWidth;
            }
        }

        private void applyResponsiveEditorLayout(bool force = false)
        {
            var viewport = resolveResponsiveViewport();
            if (viewport.X <= 0 || viewport.Y <= 0)
                return;

            var metrics = EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout);
            bool inspectorCollapsedBeforeAdjustment = inspectorCollapsed;
            if (!metrics.UseStackedInspector && inspectorCollapsed)
                inspectorCollapsed = false;

            bool inspectorWidthChanged = lastInspectorWidth < 0 || Math.Abs(metrics.InspectorWidth - lastInspectorWidth) > 0.2f;
            bool stackedInspectorHeightChanged = lastStackedInspectorHeight < 0 || Math.Abs(metrics.StackedInspectorHeight - lastStackedInspectorHeight) > 0.2f;
            bool panelGapChanged = lastPanelGap < 0 || Math.Abs(metrics.PanelGap - lastPanelGap) > 0.2f;
            bool stackedModeChanged = metrics.UseStackedInspector != inspectorStackedLayout;
            bool collapsedStateChanged = inspectorCollapsedBeforeAdjustment != inspectorCollapsed;

            if (timelineLayoutGrid != null && (force || lastTimelineToolboxHeight < 0 || Math.Abs(metrics.TimelineToolboxHeight - lastTimelineToolboxHeight) > 0.2f))
            {
                timelineLayoutGrid.RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, metrics.TimelineToolboxHeight),
                    new Dimension()
                };
                lastTimelineToolboxHeight = metrics.TimelineToolboxHeight;
            }

            if (editorLayoutGrid != null && (force || lastTimelineSurfaceHeight < 0 || Math.Abs(metrics.TimelineTopHeight - lastTimelineSurfaceHeight) > 0.2f))
            {
                editorLayoutGrid.RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, metrics.TimelineTopHeight),
                    new Dimension()
                };
                lastTimelineSurfaceHeight = metrics.TimelineTopHeight;
            }

            if (screenLayoutGrid != null && (force || lastFooterHeight < 0 || Math.Abs(metrics.FooterHeight - lastFooterHeight) > 0.2f))
            {
                screenLayoutGrid.RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize),
                    new Dimension(),
                    new Dimension(GridSizeMode.Absolute, metrics.FooterHeight)
                };
                lastFooterHeight = metrics.FooterHeight;
            }

            if (previewInspectorGrid != null
                && previewCellContainer != null
                && inspectorContainer != null
                && (force || inspectorWidthChanged || stackedInspectorHeightChanged || panelGapChanged || stackedModeChanged || collapsedStateChanged))
            {
                applyPreviewInspectorLayout(metrics);
            }

            applyCompactEditorDensity(metrics, viewport, force);
            updateInspectorToggle(metrics, viewport);
        }

        private void applyCompactEditorDensity(EditorResponsiveLayoutMetrics metrics, Vector2 viewport, bool force)
        {
            float compactBlend = Math.Clamp((820f - viewport.Y) / 160f, 0f, 1f);
            float widthCompactBlend = Math.Clamp((1500f - viewport.X) / 380f, 0f, 1f);
            compactBlend = Math.Max(compactBlend, widthCompactBlend);
            if (metrics.UseStackedInspector)
                compactBlend = Math.Max(compactBlend, 0.42f);
            else
                compactBlend = Math.Max(0f, compactBlend - 0.28f);

            if (!force && lastCompactBlend >= 0 && Math.Abs(compactBlend - lastCompactBlend) < 0.015f)
                return;

            applyHeaderDensity(compactBlend, viewport);
            applyTimelineToolboxDensity(compactBlend, viewport);
            applyInspectorDensity(compactBlend, viewport);
            applyFooterDensity(compactBlend, viewport);
            applyInspectorHierarchy(compactBlend);

            lastCompactBlend = compactBlend;
        }

        private void applyInspectorHierarchy(float compactBlend)
        {
            if (inspectorSectionsFlow == null
                || inspectorMetadataSection == null
                || inspectorTimingSection == null
                || inspectorStatsSection == null
                || inspectorGenerationSection == null)
            {
                return;
            }

            bool compactOrder = compactBlend >= 0.42f;
            if (compactOrder == inspectorCompactHierarchy)
                return;

            inspectorCompactHierarchy = compactOrder;
            inspectorSectionsFlow.Clear(false);
            foreach (var section in getInspectorSectionsInOrder(compactOrder))
                inspectorSectionsFlow.Add(section);
        }

        private Drawable[] getInspectorSectionsInOrder(bool compactOrder)
        {
            if (inspectorSectionsByKey.Count == 0)
                return Array.Empty<Drawable>();

            var orderedKeys = EditorInspectorCopy.GetSectionOrder(compactOrder);
            var result = new List<Drawable>(orderedKeys.Length);
            foreach (var key in orderedKeys)
            {
                if (inspectorSectionsByKey.TryGetValue(key, out var section))
                    result.Add(section);
            }

            return result.ToArray();
        }

        private void applyHeaderDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            float widthRelax = Math.Clamp((viewport.X - 1920f) / 1200f, 0f, 1f);
            float statusFontSize = blend(18.4f, 16f, compactBlend) + ultraWideRelax * 0.55f;
            float detailFontSize = blend(11.6f, 10.3f, compactBlend) + ultraWideRelax * 0.28f;
            float timeFontSize = blend(22.4f, 19.4f, compactBlend) + ultraWideRelax * 0.7f;
            float timeCaptionFontSize = blend(9.8f, 8.8f, compactBlend) + ultraWideRelax * 0.2f;
            float hintFontSize = blend(11.4f, 10.2f, compactBlend) + ultraWideRelax * 0.25f;
            float buttonHeight = blend(42f, 36f, compactBlend) + ultraWideRelax * 1.1f;
            float buttonFontSize = blend(13.4f, 11.8f, compactBlend) + widthRelax * 0.35f;
            float buttonSpacing = blend(10f, 8f, compactBlend) + ultraWideRelax * 1.25f;
            float horizontalPadding = blend(24f, 18f, compactBlend) + ultraWideRelax * 2.3f;
            float verticalPadding = blend(12f, 9f, compactBlend) + ultraWideRelax * 0.8f;
            float infoSpacing = blend(6f, 4f, compactBlend);
            float contentSpacing = blend(10f, 8f, compactBlend);
            float playButtonWidth = blend(120f, 106f, compactBlend);
            float saveButtonWidth = blend(120f, 106f, compactBlend);
            float undoButtonWidth = blend(104f, 92f, compactBlend);
            float redoButtonWidth = blend(104f, 92f, compactBlend);
            float previewButtonWidth = blend(146f, 126f, compactBlend);
            float timeBadgeWidth = blend(196f, 170f, compactBlend);
            float timeBadgeHeight = blend(62f, 54f, compactBlend);

            statusText.Font = BeatSightFont.Section(statusFontSize);
            statusText.MaxWidth = blend(560f, 480f, compactBlend) + ultraWideRelax * 110f;
            statusDetailLine.Font = BeatSightFont.Caption(detailFontSize);
            statusDetailLine.MaxWidth = statusText.MaxWidth;

            if (headerStatusColumn != null)
                headerStatusColumn.Spacing = new Vector2(0, blend(5f, 3.5f, compactBlend));

            if (headerTimeBadgeContainer != null)
            {
                headerTimeBadgeContainer.Size = new Vector2(timeBadgeWidth, timeBadgeHeight);
                headerTimeBadgeContainer.CornerRadius = blend(12f, 10f, compactBlend);
            }

            if (headerTimeCaptionText != null)
                headerTimeCaptionText.Font = BeatSightFont.Caption(timeCaptionFontSize);

            if (timeText != null)
                timeText.Font = BeatSightFont.Numeral(timeFontSize);

            if (actionHintText != null)
            {
                actionHintText.Font = BeatSightFont.Caption(hintFontSize);
                actionHintText.MaxWidth = blend(1040f, 860f, compactBlend) + ultraWideRelax * 180f;
            }

            if (playbackStatusText != null)
            {
                playbackStatusText.Font = BeatSightFont.Caption(hintFontSize);
                playbackStatusText.MaxWidth = blend(1040f, 860f, compactBlend) + ultraWideRelax * 180f;
            }

            if (headerButtonFlow != null)
                headerButtonFlow.Spacing = new Vector2(buttonSpacing, 0);

            if (playPauseButton != null)
            {
                playPauseButton.Size = new Vector2(playButtonWidth, buttonHeight);
                playPauseButton.SetContentDensity(buttonFontSize, blend(9f, 8f, compactBlend));
            }
            if (saveButton != null)
            {
                saveButton.Size = new Vector2(saveButtonWidth, buttonHeight);
                saveButton.SetContentDensity(buttonFontSize, blend(9f, 8f, compactBlend));
            }
            if (undoButton != null)
            {
                undoButton.Size = new Vector2(undoButtonWidth, buttonHeight);
                undoButton.SetContentDensity(buttonFontSize, blend(9f, 8f, compactBlend));
            }
            if (redoButton != null)
            {
                redoButton.Size = new Vector2(redoButtonWidth, buttonHeight);
                redoButton.SetContentDensity(buttonFontSize, blend(9f, 8f, compactBlend));
            }
            if (previewToggle != null)
            {
                previewToggle.Size = new Vector2(previewButtonWidth, buttonHeight);
                previewToggle.SetContentDensity(
                    labelSize: blend(12.8f, 11.3f, compactBlend) + widthRelax * 0.25f,
                    iconSize: blend(15f, 13.4f, compactBlend),
                    spacing: blend(6f, 5f, compactBlend),
                    cornerRadius: blend(9f, 8f, compactBlend));
            }

            if (headerInformationFlow != null)
                headerInformationFlow.Spacing = new Vector2(0, infoSpacing);

            if (headerContentContainer != null)
                headerContentContainer.Padding = new MarginPadding { Horizontal = horizontalPadding, Vertical = verticalPadding };

            if (headerContentContainer?.Child is FillFlowContainer contentFlow)
                contentFlow.Spacing = new Vector2(0, contentSpacing);
        }

        private void applyInspectorDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            float textBoxHeight = blend(36f, 32f, compactBlend) + ultraWideRelax * 0.8f;
            float textBoxFontSize = blend(13.8f, 12.8f, compactBlend) + ultraWideRelax * 0.22f;
            float sliderHeight = blend(26f, 23f, compactBlend);
            float buttonHeight = blend(34f, 30f, compactBlend) + ultraWideRelax * 0.65f;
            float buttonCorner = blend(7f, 6f, compactBlend);
            float buttonFont = blend(11.6f, 10.5f, compactBlend) + ultraWideRelax * 0.2f;
            float sectionTitleFont = blend(13f, 12f, compactBlend) + ultraWideRelax * 0.35f;
            float fieldLabelFont = blend(11.4f, 10.6f, compactBlend) + ultraWideRelax * 0.25f;
            float sectionSpacing = blend(10.6f, 8.5f, compactBlend) + ultraWideRelax * 0.8f;
            float sectionPaddingH = blend(13f, 11f, compactBlend) + ultraWideRelax * 1.2f;
            float sectionPaddingV = blend(10f, 8f, compactBlend) + ultraWideRelax * 0.65f;
            float fieldSpacing = blend(6.6f, 5.4f, compactBlend);
            float sectionsSpacing = blend(12.8f, 10.7f, compactBlend) + ultraWideRelax * 0.9f;
            float outerPaddingH = blend(12f, 10f, compactBlend) + ultraWideRelax * 1.2f;
            float outerPaddingV = blend(12f, 10f, compactBlend) + ultraWideRelax * 0.6f;

            foreach (var textBox in inspectorTextBoxes)
            {
                textBox.Height = textBoxHeight;
                textBox.TextSize = textBoxFontSize;
                textBox.CornerRadius = blend(8f, 7f, compactBlend);
            }

            foreach (var slider in inspectorSliders)
                slider.Height = sliderHeight;

            foreach (var button in inspectorActionButtons)
            {
                button.Height = buttonHeight;
                button.CornerRadius = buttonCorner;
            }
            foreach (var label in inspectorActionButtonTexts)
                label.Font = BeatSightFont.Button(buttonFont);

            refreshInspectorActionLabelWidths();

            foreach (var titleText in inspectorSectionTitleTexts)
                titleText.Font = BeatSightFont.Section(sectionTitleFont);

            foreach (var labelText in inspectorFieldLabelTexts)
                labelText.Font = BeatSightFont.Caption(fieldLabelFont);

            foreach (var body in inspectorSectionBodies)
            {
                body.Spacing = new Vector2(0, sectionSpacing);
                body.Padding = new MarginPadding { Horizontal = sectionPaddingH, Vertical = sectionPaddingV };
            }

            foreach (var flow in inspectorFieldFlows)
                flow.Spacing = new Vector2(0, fieldSpacing);

            if (inspectorSectionsFlow != null)
            {
                inspectorSectionsFlow.Spacing = new Vector2(0, sectionsSpacing);
                inspectorSectionsFlow.Padding = new MarginPadding { Horizontal = outerPaddingH, Vertical = outerPaddingV };
            }
        }

        private void applyFooterDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            if (footerRootContainer != null)
            {
                footerRootContainer.Padding = new MarginPadding
                {
                    Horizontal = blend(12f, 10f, compactBlend) + ultraWideRelax * 1.2f,
                    Vertical = blend(11f, 8f, compactBlend) + ultraWideRelax * 0.6f
                };
                footerRootContainer.CornerRadius = blend(12f, 10f, compactBlend);
            }

            if (footerInnerContainer != null)
            {
                footerInnerContainer.Padding = new MarginPadding
                {
                    Horizontal = blend(15f, 10f, compactBlend),
                    Vertical = blend(9f, 6f, compactBlend)
                };
            }

            if (footerTipFlow != null)
                footerTipFlow.Spacing = new Vector2(blend(18f, 13f, compactBlend) + ultraWideRelax * 1.5f, 0);

            foreach (var keyText in footerKeyTexts)
            {
                keyText.Font = BeatSightFont.Title(blend(11.2f, 10f, compactBlend));
                keyText.Margin = new MarginPadding
                {
                    Horizontal = blend(7f, 6f, compactBlend),
                    Vertical = blend(4f, 3f, compactBlend)
                };
            }

            foreach (var actionText in footerActionTexts)
                actionText.Font = BeatSightFont.Caption(blend(11f, 10f, compactBlend));
        }

        private static float blend(float normal, float compact, float t)
            => normal + (compact - normal) * t;

        private void applyPreviewInspectorLayout(EditorResponsiveLayoutMetrics metrics)
        {
            inspectorStackedLayout = metrics.UseStackedInspector;
            bool hideStackedInspector = inspectorStackedLayout && inspectorCollapsed;

            if (!inspectorStackedLayout)
            {
                previewCellContainer.Padding = new MarginPadding { Right = metrics.PanelGap };
                inspectorContainer.RelativeSizeAxes = Axes.Y;
                inspectorContainer.AutoSizeAxes = Axes.None;
                inspectorContainer.Anchor = Anchor.TopRight;
                inspectorContainer.Origin = Anchor.TopRight;
                inspectorContainer.Margin = new MarginPadding { Left = metrics.PanelGap };
                inspectorContainer.Width = metrics.InspectorWidth;
                inspectorContainer.Height = 1f;
                inspectorContainer.Alpha = 1f;
                inspectorContainer.AlwaysPresent = true;

                previewInspectorGrid.RowDimensions = new[]
                {
                    new Dimension()
                };
                previewInspectorGrid.ColumnDimensions = new[]
                {
                    new Dimension(),
                    new Dimension(GridSizeMode.Absolute, metrics.InspectorWidth)
                };
                previewInspectorGrid.Content = new[]
                {
                    new Drawable[]
                    {
                        previewCellContainer,
                        inspectorContainer
                    }
                };
            }
            else
            {
                previewCellContainer.Padding = new MarginPadding
                {
                    Bottom = hideStackedInspector ? 0 : metrics.PanelGap
                };

                inspectorContainer.RelativeSizeAxes = Axes.X;
                inspectorContainer.AutoSizeAxes = Axes.None;
                inspectorContainer.Anchor = Anchor.TopLeft;
                inspectorContainer.Origin = Anchor.TopLeft;
                inspectorContainer.Margin = new MarginPadding();
                inspectorContainer.Width = 1f;
                inspectorContainer.Height = metrics.StackedInspectorHeight;
                inspectorContainer.Alpha = hideStackedInspector ? 0 : 1;
                inspectorContainer.AlwaysPresent = !hideStackedInspector;

                if (hideStackedInspector)
                {
                    previewInspectorGrid.RowDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.ColumnDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.Content = new[]
                    {
                        new Drawable[]
                        {
                            previewCellContainer
                        }
                    };
                }
                else
                {
                    previewInspectorGrid.RowDimensions = new[]
                    {
                        new Dimension(),
                        new Dimension(GridSizeMode.Absolute, metrics.StackedInspectorHeight)
                    };
                    previewInspectorGrid.ColumnDimensions = new[]
                    {
                        new Dimension()
                    };
                    previewInspectorGrid.Content = new[]
                    {
                        new Drawable[]
                        {
                            previewCellContainer
                        },
                        new Drawable[]
                        {
                            inspectorContainer
                        }
                    };
                }
            }

            lastInspectorWidth = metrics.InspectorWidth;
            lastStackedInspectorHeight = metrics.StackedInspectorHeight;
            lastPanelGap = metrics.PanelGap;
        }

        private void updateInspectorToggle(EditorResponsiveLayoutMetrics metrics, Vector2 viewport)
        {
            if (inspectorToggleButton == null)
                return;

            float toggleWidth = ResponsiveLayout.ClampFraction(viewport.X, 0.094f, 116f, 172f);
            float toggleHeight = ResponsiveLayout.ClampFraction(viewport.Y, 0.036f, 30f, 40f);
            float toggleInsetX = ResponsiveLayout.ClampFraction(viewport.X, 0.007f, 8f, 14f);
            float toggleInsetY = ResponsiveLayout.ClampFraction(viewport.Y, 0.009f, 8f, 14f);

            inspectorToggleButton.Size = new Vector2(toggleWidth, toggleHeight);
            inspectorToggleButton.Margin = new MarginPadding
            {
                Top = toggleInsetY,
                Right = toggleInsetX
            };

            if (!metrics.UseStackedInspector)
            {
                inspectorToggleButton.UpdateState(false, "Inspector collapse is available in compact layouts.");
                inspectorToggleButton.FadeOut(120);
                return;
            }

            inspectorToggleButton.SetLabel(inspectorCollapsed ? "Show Panel" : "Hide Panel");
            inspectorToggleButton.UpdateState(true, inspectorCollapsed ? "Show inspector panel (I)." : "Hide inspector panel (I).");
            inspectorToggleButton.FadeTo(0.95f, 120);
        }

        private void toggleInspectorCollapsed()
        {
            if (!inspectorStackedLayout)
                return;

            inspectorCollapsed = !inspectorCollapsed;
            applyResponsiveEditorLayout(force: true);
            appendStatusDetail(inspectorCollapsed ? "Inspector hidden (compact layout)" : "Inspector shown (compact layout)");
        }

        private float getInitialFooterHeight()
        {
            var viewport = resolveResponsiveViewport();
            return EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout).FooterHeight;
        }

        private Vector2 resolveResponsiveViewport()
            => ResponsiveLayout.ResolveViewport(
                this,
                DrawWidth > 0 ? DrawWidth : 1920f,
                DrawHeight > 0 ? DrawHeight : 1080f);

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            bool textInputFocused = isTextInputFocused();
            if (textInputFocused)
            {
                if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.S)
                {
                    saveBeatmap();
                    return true;
                }

                return base.OnKeyDown(e);
            }

            if (e.Key == osuTK.Input.Key.Escape)
            {
                if (selectedHitObject != null || tryGetSelectionRange(out _, out _))
                {
                    selectedHitObject = null;
                    timeline?.ClearSelection();
                    updateSelectionSummary();
                    appendStatusDetail("Selection cleared");
                    return true;
                }

                this.Exit();
                return true;
            }

            if (e.Key == osuTK.Input.Key.Space)
            {
                if (e.ShiftPressed)
                    rewindToStart();
                else
                    togglePlayback();
                return true;
            }

            if (!e.ControlPressed && !e.SuperPressed && !e.AltPressed && e.Key == osuTK.Input.Key.I && inspectorStackedLayout)
            {
                toggleInspectorCollapsed();
                return true;
            }

            if (e.AltPressed)
            {
                if (e.Key == osuTK.Input.Key.Left)
                {
                    nudgeSelectedNote(false);
                    return true;
                }

                if (e.Key == osuTK.Input.Key.Right)
                {
                    nudgeSelectedNote(true);
                    return true;
                }
            }

            if (e.Key == osuTK.Input.Key.Home)
            {
                jumpToFirstNote();
                return true;
            }

            if (e.Key == osuTK.Input.Key.End)
            {
                jumpToLastNote();
                return true;
            }

            switch (getNotationHotkeyAction(e.Key, e.ControlPressed, e.AltPressed, e.SuperPressed))
            {
                case NotationHotkeyAction.ArticulationUp:
                    cycleNotationArticulationPreset(true);
                    return true;
                case NotationHotkeyAction.ArticulationDown:
                    cycleNotationArticulationPreset(false);
                    return true;
                case NotationHotkeyAction.ShiftLaneUp:
                    shiftSelectionToAdjacentNotationLane(true);
                    return true;
                case NotationHotkeyAction.ShiftLaneDown:
                    shiftSelectionToAdjacentNotationLane(false);
                    return true;
            }

            if (e.Key == osuTK.Input.Key.Comma)
            {
                jumpToAdjacentNote(false);
                return true;
            }

            if (e.Key == osuTK.Input.Key.Period)
            {
                jumpToAdjacentNote(true);
                return true;
            }

            if (e.Key == osuTK.Input.Key.Delete || e.Key == osuTK.Input.Key.BackSpace)
            {
                deleteSelectedNote();
                return true;
            }

            if (e.Key == osuTK.Input.Key.Left)
            {
                seekRelative(-5000);
                return true;
            }

            if (e.Key == osuTK.Input.Key.Right)
            {
                seekRelative(5000);
                return true;
            }

            if (isControlOrSuper(e))
            {
                bool alt = e.AltPressed;

                if (isZoomIncreaseKey(e.Key))
                {
                    if (alt)
                        adjustWaveformScale(true);
                    else
                        adjustTimelineZoom(true);
                    return true;
                }

                if (isZoomDecreaseKey(e.Key))
                {
                    if (alt)
                        adjustWaveformScale(false);
                    else
                        adjustTimelineZoom(false);
                    return true;
                }
            }

            if (!e.ControlPressed && !e.SuperPressed)
            {
                if (!e.AltPressed)
                {
                    if (tryHandleLaneQuickReassign(e.Key))
                        return true;

                    if (e.Key == osuTK.Input.Key.BracketLeft)
                    {
                        adjustSnapDivisor(false);
                        return true;
                    }

                    if (e.Key == osuTK.Input.Key.BracketRight)
                    {
                        adjustSnapDivisor(true);
                        return true;
                    }

                    if (e.Key == osuTK.Input.Key.G)
                    {
                        toggleBeatGrid();
                        return true;
                    }
                }
            }

            if (isControlOrSuper(e) && e.ShiftPressed && e.Key == osuTK.Input.Key.Z)
            {
                redoLastEdit();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.Y)
            {
                redoLastEdit();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.S)
            {
                saveBeatmap();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.A && !isTextInputFocused())
            {
                selectAllNotes();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.D)
            {
                duplicateSelectedNote();
                return true;
            }

            if (!e.ControlPressed && !e.SuperPressed && !e.AltPressed && e.Key == osuTK.Input.Key.Q && !isTextInputFocused())
            {
                quantizeSelectedToGrid();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.Z)
            {
                undoLastEdit();
                return true;
            }

            return base.OnKeyDown(e);
        }

        private bool tryHandleLaneQuickReassign(osuTK.Input.Key key)
        {
            int laneIndex = key switch
            {
                osuTK.Input.Key.Number1 => 0,
                osuTK.Input.Key.Number2 => 1,
                osuTK.Input.Key.Number3 => 2,
                osuTK.Input.Key.Number4 => 3,
                osuTK.Input.Key.Number5 => 4,
                osuTK.Input.Key.Number6 => 5,
                osuTK.Input.Key.Number7 => 6,
                osuTK.Input.Key.Number8 => 7,
                osuTK.Input.Key.Number9 => 8,
                _ => -1
            };

            if (laneIndex < 0)
                return false;

            if (beatmap == null)
                return true;

            string? component = resolveQuickReassignComponentForVisibleLane(laneIndex);
            if (string.IsNullOrWhiteSpace(component))
            {
                appendStatusDetail($"No lane bound to {laneIndex + 1}");
                return true;
            }

            var targets = getSelectedHitObjectsForEditing(out _, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to reassign");
                quickActionToast?.Warning("Quick Reassign", "Select a note or range first");
                return true;
            }

            int changedCount = targets.Count(hit =>
                !string.Equals(hit.Component, component, StringComparison.OrdinalIgnoreCase)
                || hit.Lane.HasValue);
            if (changedCount <= 0)
            {
                appendStatusDetail($"Selection already uses {component}");
                quickActionToast?.Info("Quick Reassign", $"Already {formatComponentDisplayName(component)}");
                return true;
            }

            componentReassignSelection.Value = component;
            reassignSelectedComponent();
            showQuickReassignToast(component, laneIndex + 1, changedCount);
            return true;
        }

        private void showQuickReassignToast(string component, int laneNumber, int affectedNotes)
        {
            if (quickActionToast == null)
                return;

            string name = formatComponentDisplayName(component);
            string notesLabel = affectedNotes == 1 ? "1 note" : $"{affectedNotes} notes";
            quickActionToast.Success("Quick Reassign", $"Reassigned -> {name} (lane {laneNumber}) | {notesLabel}");
        }

        private static string formatComponentDisplayName(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return "Unknown";

            string raw = component.Replace('_', ' ').Trim();
            if (raw.Length == 0)
                return "Unknown";

            return CultureInfo.InvariantCulture.TextInfo.ToTitleCase(raw.ToLowerInvariant());
        }

        private string? resolveQuickReassignComponentForVisibleLane(int visibleLaneIndex)
        {
            if (visibleLaneIndex < 0)
                return null;

            string? timelineMappedComponent = timeline?.GetLaneComponentForVisibleLane(visibleLaneIndex);
            if (!string.IsNullOrWhiteSpace(timelineMappedComponent))
                return timelineMappedComponent;

            LaneLayout layout = resolveCurrentLaneLayout();
            bool useGlobalKick = kickLaneModeSetting.Value == KickLaneMode.GlobalLine;
            int activeLaneCount = useGlobalKick
                ? Math.Max(1, layout.LaneCount - 1)
                : layout.LaneCount;

            if (visibleLaneIndex >= activeLaneCount)
                return null;

            var source = useGlobalKick
                ? globalKickLaneQuickComponents
                : dedicatedLaneQuickComponents;

            return visibleLaneIndex < source.Length
                ? source[visibleLaneIndex]
                : null;
        }

        private LaneLayout resolveCurrentLaneLayout()
        {
            if (lanePresetSetting.Value == LanePreset.AutoDynamic && beatmap?.DrumKit?.Components?.Count > 0)
                return LaneLayoutFactory.CreateFromComponents(beatmap.DrumKit.Components);

            return lanePresetSetting.Value == LanePreset.AutoDynamic
                ? LaneLayoutFactory.Create(LanePreset.DrumSevenLane)
                : LaneLayoutFactory.Create(lanePresetSetting.Value);
        }

        private static bool isZoomIncreaseKey(osuTK.Input.Key key)
                    => key == osuTK.Input.Key.Plus
                        || key == osuTK.Input.Key.KeypadPlus;

        private static bool isZoomDecreaseKey(osuTK.Input.Key key)
            => key == osuTK.Input.Key.Minus
                        || key == osuTK.Input.Key.KeypadMinus;

        private static NotationHotkeyAction getNotationHotkeyAction(osuTK.Input.Key key, bool controlPressed, bool altPressed, bool superPressed)
        {
            if (altPressed || superPressed)
                return NotationHotkeyAction.None;

            if (key == osuTK.Input.Key.PageUp)
                return controlPressed ? NotationHotkeyAction.ArticulationUp : NotationHotkeyAction.ShiftLaneUp;

            if (key == osuTK.Input.Key.PageDown)
                return controlPressed ? NotationHotkeyAction.ArticulationDown : NotationHotkeyAction.ShiftLaneDown;

            return NotationHotkeyAction.None;
        }

        private bool isTextInputFocused()
        {
            if (titleInput?.HasFocus == true
                || artistInput?.HasFocus == true
                || creatorInput?.HasFocus == true
                || sourceInput?.HasFocus == true
                || tagsInput?.HasFocus == true
                || releaseInput?.HasFocus == true
                || providerInput?.HasFocus == true
                || descriptionInput?.HasFocus == true
                || bpmInput?.HasFocus == true
                || offsetInput?.HasFocus == true
                || tempoHintsInput?.HasFocus == true)
            {
                return true;
            }

            return componentReassignDropdown?.HasFocus == true;
        }

        private void seekRelative(double milliseconds)
        {
            seekToTime(currentTime + milliseconds);
        }

        private static string formatTime(double milliseconds)
        {
            var time = TimeSpan.FromMilliseconds(milliseconds);

            if (time.TotalHours >= 1)
                return $"{(int)time.TotalHours:00}:{time.Minutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";

            return $"{(int)time.TotalMinutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";
        }

        private static bool isControlOrSuper(KeyDownEvent e) => e.ControlPressed || e.SuperPressed;

        public override bool OnExiting(ScreenExitEvent e)
        {
            endTimelineZoomInteraction();
            endWaveformScaleInteraction();
            uiAudio.PlayBack();
            stopPlayback(silent: true);
            disposeTrack();
            return base.OnExiting(e);
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);
            disposeTrack();
            storageTrackStore?.Dispose();
            storageTrackStore = null;
            storageResourceStore?.Dispose();
            storageResourceStore = null;
        }

        private partial class PassiveScrollContainer : BeatSightScrollContainer
        {
            public PassiveScrollContainer(Direction direction = Direction.Vertical)
                : base(direction)
            {
            }

            protected override bool OnDragStart(DragStartEvent e) => false;

            protected override void OnDrag(DragEvent e)
            {
            }
        }

        private void runPipeline()
        {
            if (string.IsNullOrEmpty(beatmapPath))
            {
                osu.Framework.Logging.Logger.Log("Cannot run pipeline: Beatmap path is not set. Please save the beatmap first.", LoggingTarget.Runtime, LogLevel.Error);
                return;
            }

            if (beatmap == null) return;

            string audioPath = Path.Combine(Path.GetDirectoryName(beatmapPath)!, beatmap.Audio.Filename);
            if (!File.Exists(audioPath))
            {
                osu.Framework.Logging.Logger.Log($"Cannot run pipeline: Audio file not found at {audioPath}", LoggingTarget.Runtime, LogLevel.Error);
                return;
            }

            // Prepare options from UI
            var options = new AiGenerationOptions
            {
                ConfidenceThreshold = confidenceThreshold.Value,
                DetectionSensitivity = (int)detectionSensitivity.Value,
                EnableDrumSeparation = isolateDrums.Value,
                ForceQuantization = forceQuantization.Value,
                MaxSnapErrorMilliseconds = maxSnapError.Value,
                QuantizationGrid = parseQuantizationGrid(quantizationGrid.Value),
                PythonExecutablePath = config.Get<string>(BeatSightSetting.PythonPath),
                ExportDebugAnalysis = true
            };

            // Parse tempo hints
            if (!string.IsNullOrWhiteSpace(tempoHintsInput.Text))
            {
                var candidates = new List<double>();
                foreach (var part in tempoHintsInput.Text.Split(','))
                {
                    if (double.TryParse(part.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out double val))
                        candidates.Add(val);
                }
                options.TempoCandidates = candidates;
            }

            // Create a track object for the AI generator from the current audio path
            var audioTrackForGeneration = new ImportedAudioTrack(
                audioPath,
                audioPath,
                Path.GetFileName(audioPath),
                Path.GetFileName(audioPath),
                new FileInfo(audioPath).Length,
                null
            );

            osu.Framework.Logging.Logger.Log("Starting AI pipeline...", LoggingTarget.Runtime, LogLevel.Important);
            logText.Clear();
            logText.AddParagraph("Starting AI pipeline...", t => t.Colour = Color4.Cyan);
            logOverlay.FadeIn(200);

            // Run in background
            Task.Run(async () =>
            {
                var generator = new AiBeatmapGenerator(host);
                var progress = new Progress<AiGenerationProgress>(p =>
                {
                    Schedule(() =>
                    {
                        if (!string.IsNullOrEmpty(p.Message))
                        {
                            logText.AddParagraph(p.Message, t => t.Colour = Color4.White);
                            // Auto-scroll to bottom
                            logScroll?.ScrollToEnd();
                        }
                    });
                });

                try
                {
                    var result = await generator.GenerateAsync(audioTrackForGeneration, options, progress, CancellationToken.None);

                    Schedule(() =>
                    {
                        if (result.Success)
                        {
                            logText.AddParagraph("Pipeline completed successfully!", t => t.Colour = Color4.Green);
                            osu.Framework.Logging.Logger.Log("Pipeline completed successfully!", LoggingTarget.Runtime, LogLevel.Important);

                            // Reload beatmap
                            if (result.Beatmap != null)
                            {
                                beatmap = result.Beatmap;
                                beatmapPath = result.BeatmapPath; // Update path if it changed (e.g. new file)
                                trackLength = beatmap.Audio.Duration;
                                reloadTimeline();
                                populateInspectorFromBeatmap();

                                // Load debug data if available
                                if (result.DebugAnalysisPath != null && File.Exists(result.DebugAnalysisPath))
                                {
                                    try
                                    {
                                        string json = File.ReadAllText(result.DebugAnalysisPath);
                                        timeline?.LoadDebugData(json);
                                    }
                                    catch (Exception ex)
                                    {
                                        osu.Framework.Logging.Logger.Log($"Failed to load debug analysis: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                                    }
                                }

                                setStatusDetail("Generated new beatmap");
                            }
                        }
                        else
                        {
                            logText.AddParagraph($"Pipeline failed: {result.Error}", t => t.Colour = Color4.Red);
                            osu.Framework.Logging.Logger.Log($"Pipeline failed: {result.Error}", LoggingTarget.Runtime, LogLevel.Error);
                        }
                    });
                }
                catch (Exception ex)
                {
                    Schedule(() =>
                    {
                        logText.AddParagraph($"Pipeline execution error: {ex.Message}", t => t.Colour = Color4.Red);
                        osu.Framework.Logging.Logger.Log($"Pipeline execution error: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                    });
                }
            });
        }

        private QuantizationGrid parseQuantizationGrid(string value)
        {
            return value switch
            {
                "quarter" => QuantizationGrid.Quarter,
                "eighth" => QuantizationGrid.Eighth,
                "sixteenth" => QuantizationGrid.Sixteenth,
                "thirty_second" => QuantizationGrid.ThirtySecond,
                _ => QuantizationGrid.Sixteenth
            };
        }

        private Drawable createLogOverlay()
        {
            logText = new TextFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding(10)
            };

            logOverlay = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Width = 0.8f,
                Height = 0.8f,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Masking = true,
                CornerRadius = 10,
                Alpha = 0, // Hidden by default
                Depth = -100, // On top
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.Black.Opacity(0.9f)
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Bottom = 50 },
                        Child = logScroll = new BeatSightScrollContainer
                        {
                            RelativeSizeAxes = Axes.Both,
                            Child = logText
                        }
                    },
                    new BeatSightButton
                    {
                        Text = "Close",
                        Width = 100,
                        Height = 30,
                        Anchor = Anchor.BottomRight,
                        Origin = Anchor.BottomRight,
                        Margin = new MarginPadding(10),
                        Action = () => logOverlay.FadeOut(200)
                    }
                }
            };
            return logOverlay;
        }

        private async void regenerateRegion()
        {
            if (timeline.SelectionStart.HasValue && timeline.SelectionEnd.HasValue)
            {
                double start = Math.Min(timeline.SelectionStart.Value, timeline.SelectionEnd.Value);
                double end = Math.Max(timeline.SelectionStart.Value, timeline.SelectionEnd.Value);

                if (end - start < 100)
                {
                    setStatusBase("Selection too small");
                    setStatusDetail("Select at least 100ms of audio to regenerate");
                    return;
                }

                setStatusBase("Regenerating region...");
                setStatusDetail($"Processing {(end - start) / 1000.0:F1}s section from {start / 1000.0:F1}s to {end / 1000.0:F1}s");

                string? audioPath = null;
                if (importedAudio != null)
                {
                    audioPath = importedAudio.StoredPath;
                }
                else if (!string.IsNullOrEmpty(beatmapPath))
                {
                    string? folder = Path.GetDirectoryName(beatmapPath);
                    if (folder != null)
                        audioPath = Path.Combine(folder, beatmap!.Audio.Filename);
                }

                if (string.IsNullOrEmpty(audioPath) || !File.Exists(audioPath))
                {
                    setStatusBase("Could not locate audio file");
                    setStatusDetail($"Expected at: {audioPath ?? "(unknown)"}");
                    return;
                }

                var generator = new AiBeatmapGenerator(host);
                var options = new AiGenerationOptions
                {
                    StartTime = start / 1000.0,
                    EndTime = end / 1000.0,
                    QuantizationGrid = parseQuantizationGrid(quantizationGrid.Value),
                    ConfidenceThreshold = confidenceThreshold.Value,
                    DetectionSensitivity = (int)detectionSensitivity.Value,
                    EnableDrumSeparation = isolateDrums.Value,
                    ForceQuantization = forceQuantization.Value,
                    MaxSnapErrorMilliseconds = maxSnapError.Value,
                    PythonExecutablePath = config.Get<string>(BeatSightSetting.PythonPath)
                };

                var audioTrackForGeneration = new ImportedAudioTrack(
                    audioPath,
                    audioPath,
                    Path.GetFileName(audioPath),
                    Path.GetFileName(audioPath),
                    new FileInfo(audioPath).Length,
                    null
                );

                try
                {
                    var result = await generator.GenerateAsync(audioTrackForGeneration, options, null, CancellationToken.None);

                    if (result.Success && result.Beatmap?.HitObjects != null)
                    {
                        int noteCount = result.Beatmap.HitObjects.Count;
                        mergeHitObjects(result.Beatmap.HitObjects, start, end);
                        setStatusBase("Region regenerated");
                        setStatusDetail($"Added {noteCount} notes from {start / 1000.0:F1}s to {end / 1000.0:F1}s");
                    }
                    else
                    {
                        setStatusBase("Generation failed");
                        setStatusDetail(result.Error ?? "Unknown error occurred");
                    }
                }
                catch (Exception ex)
                {
                    setStatusBase("Generation error");
                    setStatusDetail(ex.Message);
                    osu.Framework.Logging.Logger.Error(ex, "Region regeneration failed");
                }
            }
            else
            {
                setStatusBase("No region selected");
                setStatusDetail("Use Shift+Drag on the timeline to select a region to regenerate");
            }
        }

        private void mergeHitObjects(List<HitObject> newHits, double start, double end)
        {
            if (beatmap == null)
                return;

            prepareUndoSnapshot();

            int timeShiftMs = 0;
            if (newHits.Count > 0 && start > 0)
            {
                int minGenerated = newHits.Min(h => h.Time);
                int maxGenerated = newHits.Max(h => h.Time);
                double selectionLength = Math.Max(0, end - start);

                // Partial generation commonly returns region-local timestamps.
                // Shift to absolute timeline when output fits inside selection length.
                bool appearsRelative = minGenerated >= 0 && maxGenerated <= selectionLength + 2000;
                if (appearsRelative)
                    timeShiftMs = (int)Math.Round(start);
            }

            beatmap.HitObjects.RemoveAll(h => h.Time >= start && h.Time <= end);

            var hitsToAdd = new List<HitObject>();
            foreach (var hit in newHits)
            {
                int adjustedTime = hit.Time + timeShiftMs;
                if (adjustedTime < start || adjustedTime > end)
                    continue;

                hitsToAdd.Add(new HitObject
                {
                    Time = adjustedTime,
                    Component = hit.Component,
                    Lane = hit.Lane,
                    Velocity = hit.Velocity,
                    Duration = hit.Duration
                });
            }

            beatmap.HitObjects.AddRange(hitsToAdd);
            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;

            if (selectedHitObject != null && !beatmap.HitObjects.Contains(selectedHitObject))
                selectedHitObject = null;

            markUnsaved();
            refreshUnsavedState();
            reloadTimeline();
            updateSelectionSummary();
            updateInspectorStats();
            appendStatusDetail($"Merged {hitsToAdd.Count} regenerated note{(hitsToAdd.Count == 1 ? string.Empty : "s")}");
        }
    }
}
