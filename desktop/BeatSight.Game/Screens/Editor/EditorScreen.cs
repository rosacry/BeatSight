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

        // EditorSnapshot class extracted to EditorCommandManager.cs

    }
}
