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

    }
}
