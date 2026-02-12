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

        private void setStatusBase(string text)
        {
            statusBaseText = text;
            updateStatusText();
            updateActionButtons();
        }

        private void setStatusDetail(string? detail)
        {
            statusDetailText = string.IsNullOrWhiteSpace(detail) ? null : detail;
            updateStatusText();
        }

        private void appendStatusDetail(string detail)
        {
            if (string.IsNullOrWhiteSpace(detail))
                return;

            if (isTransientPlaybackStatus(detail))
                pruneStatusDetailSegments(isTransientPlaybackStatus);
            else if (isInspectorLayoutStatus(detail))
                pruneStatusDetailSegments(isInspectorLayoutStatus);

            if (string.IsNullOrWhiteSpace(statusDetailText))
            {
                statusDetailText = detail;
            }
            else if (!statusDetailText.Contains(detail, StringComparison.OrdinalIgnoreCase))
            {
                statusDetailText = $"{statusDetailText}, {detail}";
            }

            updateStatusText();
        }

        private static bool isTransientPlaybackStatus(string detail)
            => transientPlaybackStatusTokens.Any(token => detail.StartsWith(token, StringComparison.OrdinalIgnoreCase));

        private static bool isInspectorLayoutStatus(string detail)
            => detail.StartsWith("Inspector hidden", StringComparison.OrdinalIgnoreCase)
               || detail.StartsWith("Inspector shown", StringComparison.OrdinalIgnoreCase);

        private void pruneStatusDetailSegments(Func<string, bool> shouldRemove)
        {
            if (string.IsNullOrWhiteSpace(statusDetailText))
                return;

            var segments = statusDetailText
                .Split(", ", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Where(segment => !shouldRemove(segment))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();

            statusDetailText = segments.Length > 0 ? string.Join(", ", segments) : null;
        }

        private void updateStatusText()
        {
            if (statusText != null)
            {
                statusText.Text = statusBaseText;
                statusText.Alpha = string.IsNullOrWhiteSpace(statusBaseText) ? 0 : 1;
            }

            string? detail = statusDetailText;

            if (!string.IsNullOrWhiteSpace(detail))
                detail = detail.Replace(", ", " | ");

            if (hasUnsavedChanges)
                detail = string.IsNullOrWhiteSpace(detail) ? "Unsaved changes" : $"{detail} | Unsaved changes";

            if (statusDetailLine != null)
            {
                bool showDetail = !string.IsNullOrWhiteSpace(detail);
                statusDetailLine.Text = showDetail ? detail! : string.Empty;
                statusDetailLine.Alpha = showDetail ? 1 : 0;
            }
        }

        private void setHoverHint(string? hint)
        {
            hoverHintOverride = string.IsNullOrWhiteSpace(hint) ? null : hint;
            refreshHintText();
        }

        private void refreshHintText()
        {
            if (actionHintText == null)
                return;

            string? display = hoverHintOverride ?? defaultHintText;
            actionHintText.Text = display ?? string.Empty;
            actionHintText.Alpha = string.IsNullOrEmpty(display) ? 0 : 1;
        }

        private void updatePlaybackAvailabilityUI()
        {
            if (playPauseButton != null)
                updatePlayPauseButtonLabel();

            if (previewToggle != null)
            {
                previewToggle.SetAvailability(true, null);

                float targetAlpha = playbackAvailable ? 1f : 0.75f;
                previewToggle.FadeTo(targetAlpha, 150);
            }

            if (playbackStatusText != null)
            {
                if (playbackAvailable)
                    playbackStatusText.FadeOut(150);
                else
                {
                    playbackStatusText.Text = offlinePlaybackMessage;
                    playbackStatusText.FadeIn(150);
                }
            }

            if (!playbackAvailable)
                appendStatusDetail(offlinePlaybackMessage);
        }

        private void updateActionButtons()
        {
            if (saveButton == null || undoButton == null || redoButton == null)
                return;

            var currentBeatmap = beatmap;
            bool hasBeatmap = currentBeatmap != null;
            bool hasHitObjects = currentBeatmap != null && currentBeatmap.HitObjects.Count > 0;

            bool canSave = hasBeatmap && hasUnsavedChanges && !isSaving && hasHitObjects;
            bool canUndo = hasBeatmap && undoStack.Count > 0;
            bool canRedo = hasBeatmap && redoStack.Count > 0;

            string saveTooltip = !hasBeatmap
                ? "Load or create a beatmap to enable saving."
                : isSaving
                    ? "Save is already running."
                    : !hasHitObjects
                        ? "Add at least one hit object before saving."
                        : hasUnsavedChanges
                            ? $"Save beatmap ({currentBeatmap!.HitObjects.Count} notes)."
                            : "All changes are saved.";

            string undoTooltip = !hasBeatmap
                ? "Load a beatmap to undo changes."
                : canUndo
                    ? $"{undoStack.Count} undo step{(undoStack.Count == 1 ? string.Empty : "s")} available (max {maxUndoSteps})."
                    : "No edits to undo yet.";

            string redoTooltip = !hasBeatmap
                ? "Load a beatmap to redo changes."
                : canRedo
                    ? $"{redoStack.Count} redo step{(redoStack.Count == 1 ? string.Empty : "s")} available."
                    : undoStack.Count > 0
                        ? "Undo an action to enable redo."
                        : "No actions to redo yet.";

            saveButton.UpdateState(canSave, saveTooltip);
            undoButton.UpdateState(canUndo, undoTooltip);
            redoButton.UpdateState(canRedo, redoTooltip);

            if (!hasBeatmap)
            {
                defaultHintText = "Load or create a beatmap to begin mapping.";
            }
            else if (isSaving || !hasHitObjects)
            {
                defaultHintText = saveTooltip;
            }
            else if (hasUnsavedChanges)
            {
                defaultHintText = $"Unsaved changes: press Ctrl+S to save ({currentBeatmap!.HitObjects.Count} notes).";
            }
            else if (!canUndo && !canRedo)
            {
                defaultHintText = null;
            }
            else if (!canUndo)
            {
                defaultHintText = undoTooltip;
            }
            else if (!canRedo)
            {
                defaultHintText = redoTooltip;
            }
            else
            {
                defaultHintText = null;
            }

            refreshHintText();
            updateHistoryPanel();
        }

        private void markUnsaved()
        {
            editSnapshotArmed = false;
            hasUnsavedChanges = true;
            redoStack.Clear();
            if (beatmap?.Editor?.AiGenerationMetadata != null)
                beatmap.Editor.AiGenerationMetadata.ManualEdits = true;
            updateStatusText();
            updateActionButtons();
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

        private Drawable createTimelineToolbox()
        {
            timelineMiniButtons.Clear();
            timelineMiniButtonTexts.Clear();
            timelineSectionTitleTexts.Clear();
            timelineSectionControlRows.Clear();
            timelineSectionBodies.Clear();
            var timelineCopy = EditorTimelineCopy.Active;

            timelineZoomValueText = new SpriteText
            {
                Text = $"{timelineZoom:0.00}x",
                Font = BeatSightFont.Caption(11.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            timelineZoomSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.Both,
                DragStepMultiplier = 1
            };
            var zoomBindable = new BindableDouble(timelineZoom)
            {
                MinValue = EditorTimeline.MinZoom,
                MaxValue = EditorTimeline.MaxZoom,
                Precision = 0.01
            };
            timelineZoomSlider.Current = zoomBindable;
            timelineZoomSlider.PointerAdjustingChanged += adjusting =>
            {
                timelineZoomPointerAdjusting = adjusting;

                if (adjusting)
                {
                    beginTimelineZoomInteraction();
                    return;
                }

                endTimelineZoomInteraction();
            };
            timelineZoomSlider.Current.ValueChanged += e =>
            {
                if (suppressTimelineZoomSync)
                    return;

                if (timelineZoomPointerAdjusting)
                {
                    previewTimelineZoom(e.NewValue);
                    return;
                }

                applyTimelineZoom(e.NewValue);
            };

            var zoomSliderContainer = new Container
            {
                Width = 170,
                Height = 30,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Child = timelineZoomSlider
            };
            timelineZoomSliderContainer = zoomSliderContainer;

            waveformScaleValueText = new SpriteText
            {
                Text = $"{waveformScale:0.00}x",
                Font = BeatSightFont.Caption(11.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            waveformScaleSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.Both,
                DragStepMultiplier = 1
            };
            var waveformBindable = new BindableDouble(waveformScale)
            {
                MinValue = EditorTimeline.MinWaveformScale,
                MaxValue = EditorTimeline.MaxWaveformScale,
                Precision = 0.01
            };
            waveformScaleSlider.Current = waveformBindable;
            waveformScaleSlider.PointerAdjustingChanged += adjusting =>
            {
                waveformScalePointerAdjusting = adjusting;

                if (adjusting)
                {
                    beginWaveformScaleInteraction();
                    return;
                }

                endWaveformScaleInteraction();
            };
            waveformScaleSlider.Current.ValueChanged += e =>
            {
                if (suppressWaveformScaleSync)
                    return;

                if (waveformScalePointerAdjusting)
                {
                    previewWaveformScale(e.NewValue);
                    return;
                }

                setWaveformScale(e.NewValue);
            };

            var waveformSliderContainer = new Container
            {
                Width = 154,
                Height = 30,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Child = waveformScaleSlider
            };
            timelineWaveformSliderContainer = waveformSliderContainer;

            snapDivisorText = new SpriteText
            {
                Text = $"1/{snapDivisor}",
                Font = BeatSightFont.Title(12.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            beatGridCheckbox = new BeatSightCheckbox
            {
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                LabelText = timelineCopy.BeatGridLabel,
                LabelFontSize = 11.8f
            };
            beatGridCheckbox.Current.Value = beatGridVisible;
            beatGridCheckbox.Current.ValueChanged += e =>
            {
                if (suppressBeatGridSync)
                    return;

                setBeatGridVisibility(e.NewValue);
            };

            var zoomSection = createTimelineSection(timelineCopy.SectionZoom,
                createTimelineMiniButton("-", () => adjustTimelineZoom(false), 32),
                zoomSliderContainer,
                createTimelineMiniButton("+", () => adjustTimelineZoom(true), 32),
                createTimelineMiniButton("Reset", () => applyTimelineZoom(1.0), 58),
                timelineZoomValueText);

            var waveformSection = createTimelineSection(timelineCopy.SectionWaveform,
                createTimelineMiniButton("-", () => adjustWaveformScale(false), 32),
                waveformSliderContainer,
                createTimelineMiniButton("+", () => adjustWaveformScale(true), 32),
                createTimelineMiniButton("Reset", () => setWaveformScale(1.0), 58),
                waveformScaleValueText,
                new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Margin = new MarginPadding { Left = 4 },
                    Child = new BeatSightCheckbox
                    {
                        LabelText = timelineCopy.DrumStemLabel,
                        LabelFontSize = 11.8f,
                        Current = showDrumStem,
                    }
                });

            var snapSection = createTimelineSection(timelineCopy.SectionSnap,
                createTimelineMiniButton("-", () => adjustSnapDivisor(false), 32),
                snapDivisorText,
                createTimelineMiniButton("+", () => adjustSnapDivisor(true), 32));

            var gridSection = createTimelineSection(timelineCopy.SectionOverlay, beatGridCheckbox);

            var toolsSection = createTimelineSection(timelineCopy.SectionTools,
                createTimelineMiniButton(timelineCopy.FirstNoteButton, jumpToFirstNote, 98),
                createTimelineMiniButton(timelineCopy.LastNoteButton, jumpToLastNote, 96),
                createTimelineMiniButton(timelineCopy.SnapSelectionButton, snapSelectionToTransient, 116),
                createTimelineMiniButton(timelineCopy.RegenerateButton, regenerateRegion, 116));

            var contentFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(12, 0),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Children = new Drawable[]
                {
                    zoomSection,
                    waveformSection,
                    snapSection,
                    gridSection,
                    toolsSection
                }
            };
            timelineToolboxContentFlow = contentFlow;

            var horizontalScroll = new PassiveScrollContainer(Direction.Horizontal)
            {
                RelativeSizeAxes = Axes.Both,
                ScrollbarVisible = false,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Y,
                    AutoSizeAxes = Axes.X,
                    Child = contentFlow
                }
            };

            var background = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = EditorColours.TimelineToolbarBackground
            };

            var container = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 13, Vertical = 10 },
                Masking = true,
                CornerRadius = 12,
                Children = new Drawable[]
                {
                    background,
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.12f
                    },
                    horizontalScroll
                }
            };
            timelineToolboxContainer = container;

            refreshTimelineToolboxState();
            return container;
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

        private Drawable createInspectorSection(string title, params Drawable[] content)
        {
            var titleText = new SpriteText
            {
                Text = title,
                Font = BeatSightFont.Section(13f),
                Colour = EditorColours.TextPrimary
            };
            inspectorSectionTitleTexts.Add(titleText);

            var sectionBody = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(10),
                Padding = new MarginPadding { Horizontal = 13, Vertical = 10 },
                Children = new Drawable[]
                {
                    titleText
                }.Concat(content).ToArray()
            };
            inspectorSectionBodies.Add(sectionBody);

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 9,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.SectionBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.08f
                    },
                    sectionBody
                }
            };
        }

        private Drawable createInspectorField(string label, Drawable control)
        {
            var labelText = new SpriteText
            {
                Text = label,
                Font = BeatSightFont.Caption(11.4f),
                Colour = EditorColours.TextSecondary,
                RelativeSizeAxes = Axes.X,
                AllowMultiline = true,
                Truncate = false
            };
            inspectorFieldLabelTexts.Add(labelText);

            var fieldFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6),
                Children = new Drawable[]
                {
                    labelText,
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Child = control
                    }
                }
            };
            inspectorFieldFlows.Add(fieldFlow);
            return fieldFlow;
        }

        private Drawable createInspectorFieldPair((string label, Drawable control) left, (string label, Drawable control) right)
        {
            return new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
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
                        createInspectorGridCell(createInspectorField(left.label, left.control), rightPadding: 4),
                        createInspectorGridCell(createInspectorField(right.label, right.control), leftPadding: 4)
                    }
                }
            };
        }

        private Drawable createInspectorGridCell(Drawable child, float leftPadding = 0, float rightPadding = 0)
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding
                {
                    Left = leftPadding,
                    Right = rightPadding
                },
                Child = child
            };
        }

        private Drawable createInspectorButtonRow(params (string label, Action action)[] buttons)
            => createInspectorButtonGrid(buttons.Length, buttons);

        private Drawable createInspectorButtonGrid(int columns, params (string label, Action action)[] buttons)
        {
            if (buttons.Length == 0)
                return new Container { RelativeSizeAxes = Axes.X, Height = 0 };

            int columnCount = Math.Clamp(columns, 1, buttons.Length);
            int rowCount = (buttons.Length + columnCount - 1) / columnCount;

            var columnDimensions = new Dimension[columnCount];
            for (int i = 0; i < columnCount; i++)
                columnDimensions[i] = new Dimension(GridSizeMode.Relative, 1f / columnCount);

            var content = new Drawable[rowCount][];
            for (int row = 0; row < rowCount; row++)
            {
                var rowChildren = new Drawable[columnCount];
                for (int column = 0; column < columnCount; column++)
                {
                    int buttonIndex = row * columnCount + column;
                    bool hasButton = buttonIndex < buttons.Length;
                    float rightPadding = column < columnCount - 1 ? inspectorButtonColumnSpacing : 0;
                    float bottomPadding = row < rowCount - 1 ? inspectorButtonRowSpacing : 0;

                    rowChildren[column] = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding
                        {
                            Right = rightPadding,
                            Bottom = bottomPadding
                        },
                        Child = hasButton
                            ? createInspectorButton(buttons[buttonIndex].label, buttons[buttonIndex].action, fillWidth: true)
                            : new Container { RelativeSizeAxes = Axes.X, Height = 0 }
                    };
                }

                content[row] = rowChildren;
            }

            return new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = Enumerable.Repeat(new Dimension(GridSizeMode.AutoSize), rowCount).ToArray(),
                ColumnDimensions = columnDimensions,
                Content = content
            };
        }

        private Drawable createInspectorButton(string text, Action action, float width = 88, bool fillWidth = false)
        {
            var button = new BasicButton
            {
                Height = 34,
                Masking = true,
                CornerRadius = 7,
                BackgroundColour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.16f),
                Action = action
            };
            inspectorActionButtons.Add(button);

            if (fillWidth)
                button.RelativeSizeAxes = Axes.X;
            else
                button.Size = new Vector2(width, 34);

            float maxTextWidth = fillWidth ? Math.Max(48f, width - 14f) : Math.Max(24f, width - 14f);

            var labelText = new SpriteText
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Text = text,
                Font = BeatSightFont.Button(11.8f),
                Colour = EditorColours.TextPrimary,
                Truncate = true,
                MaxWidth = maxTextWidth,
                UseFullGlyphHeight = false
            };
            inspectorActionButtonTexts.Add(labelText);
            inspectorActionLayouts.Add((button, labelText, fillWidth, width));
            button.Child = labelText;

            return button;
        }

        private Drawable createInspectorStatBadge(string label, out SpriteText valueLabel)
        {
            valueLabel = new SpriteText
            {
                Text = "--",
                Font = BeatSightFont.Title(14.8f),
                Colour = EditorColours.TextPrimary
            };

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 7,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.Lighten(EditorColours.CardBackground, 1.05f)
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(3),
                        Padding = new MarginPadding { Horizontal = 9, Vertical = 7 },
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = label,
                                Font = BeatSightFont.Caption(10.2f),
                                Colour = EditorColours.TextSecondary
                            },
                            valueLabel
                        }
                    }
                }
            };
        }

        private void applyMetadataChange(Action<BeatmapMetadata> mutation, bool refreshStatus = false)
        {
            if (beatmap == null || suppressInspectorFieldSync)
                return;

            prepareInspectorUndoSnapshot();
            mutation(beatmap.Metadata);
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();

            if (refreshStatus)
                refreshMetadataStatus();
        }

        private void prepareInspectorUndoSnapshot()
        {
            if (beatmap == null || editSnapshotArmed)
                return;

            DateTime now = DateTime.UtcNow;
            if (now - lastInspectorSnapshotAtUtc < inspectorSnapshotDebounce)
                return;

            prepareUndoSnapshot();
            if (editSnapshotArmed)
                lastInspectorSnapshotAtUtc = now;
        }

        private void refreshMetadataStatus()
        {
            if (beatmap == null)
                return;

            string artist = string.IsNullOrWhiteSpace(beatmap.Metadata.Artist) ? "Unknown Artist" : beatmap.Metadata.Artist;
            string title = string.IsNullOrWhiteSpace(beatmap.Metadata.Title) ? "Untitled" : beatmap.Metadata.Title;
            setStatusBase($"Editing: {artist} - {title}");
        }

        private void applyBpmText(string? value)
        {
            if (beatmap == null || suppressInspectorFieldSync)
                return;

            if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out double bpm) && bpm > 0)
            {
                setBpm(bpm);
            }
            else if (!string.IsNullOrWhiteSpace(value))
            {
                bpmInput?.FlashColour(EditorColours.Warning, 200);
            }
        }

        private void applyOffsetText(string? value)
        {
            if (beatmap == null || suppressInspectorFieldSync)
                return;

            if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out double offset))
            {
                prepareInspectorUndoSnapshot();
                beatmap.Timing.Offset = (int)Math.Round(offset);
                beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
                markUnsaved();
            }
            else if (!string.IsNullOrWhiteSpace(value))
            {
                offsetInput?.FlashColour(EditorColours.Warning, 200);
            }
        }

        private void setBpm(double bpm)
        {
            if (beatmap == null)
                return;

            prepareInspectorUndoSnapshot();
            beatmap.Timing.Bpm = Math.Clamp(bpm, 20, 400);
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            timeline?.SetSnap(snapDivisor, beatmap.Timing.Bpm);
            bpmStatValue.Text = $"{beatmap.Timing.Bpm:0.##} BPM";
            markUnsaved();
            updateInspectorStats();
        }

        private void updateInspectorStats()
        {
            if (noteCountValue == null)
                return;

            int noteCount = beatmap?.HitObjects.Count ?? 0;
            double duration = trackLength > 0
                ? trackLength
                : beatmap?.Audio.Duration ?? 0;

            double minutes = duration > 0 ? duration / 60000.0 : 0;
            double density = minutes > 0 ? noteCount / minutes : 0;

            noteCountValue.Text = noteCount.ToString();
            mapLengthValue.Text = duration > 0 ? formatSongLength(duration) : "--";
            densityValue.Text = density > 0 ? $"{density:0.0} notes/min" : "--";
            bpmStatValue.Text = beatmap != null ? $"{beatmap.Timing.Bpm:0.##} BPM" : "--";
        }

        private static string formatSongLength(double milliseconds)
        {
            var span = TimeSpan.FromMilliseconds(Math.Max(0, milliseconds));
            if (span.TotalHours >= 1)
                return $"{(int)span.TotalHours}:{span.Minutes:00}:{span.Seconds:00}.{span.Milliseconds:000}";
            return $"{(int)span.TotalMinutes:00}:{span.Seconds:00}.{span.Milliseconds:000}";
        }

        private void updateInspectorEnabledState(bool enabled)
        {
            setTextBoxEnabled(titleInput, enabled);
            setTextBoxEnabled(artistInput, enabled);
            setTextBoxEnabled(creatorInput, enabled);
            setTextBoxEnabled(sourceInput, enabled);
            setTextBoxEnabled(tagsInput, enabled);
            setTextBoxEnabled(releaseInput, enabled);
            setTextBoxEnabled(providerInput, enabled);
            setTextBoxEnabled(descriptionInput, enabled);
            setTextBoxEnabled(bpmInput, enabled);
            setTextBoxEnabled(offsetInput, enabled);
        }

        private void setTextBoxEnabled(BasicTextBox? textBox, bool enabled)
        {
            if (textBox == null)
                return;

            textBox.ReadOnly = !enabled;
            textBox.FadeTo(enabled ? 1f : 0.4f, 120, Easing.OutQuint);
        }

        private void populateInspectorFromBeatmap()
        {
            if (titleInput == null)
                return;

            suppressInspectorFieldSync = true;

            if (beatmap == null)
            {
                titleInput.Current.Value = string.Empty;
                artistInput.Current.Value = string.Empty;
                creatorInput.Current.Value = string.Empty;
                sourceInput.Current.Value = string.Empty;
                tagsInput.Current.Value = string.Empty;
                releaseInput.Current.Value = string.Empty;
                providerInput.Current.Value = string.Empty;
                descriptionInput.Current.Value = string.Empty;
                bpmInput.Current.Value = string.Empty;
                offsetInput.Current.Value = string.Empty;
            }
            else
            {
                titleInput.Current.Value = beatmap.Metadata.Title ?? string.Empty;
                artistInput.Current.Value = beatmap.Metadata.Artist ?? string.Empty;
                creatorInput.Current.Value = beatmap.Metadata.Creator ?? string.Empty;
                sourceInput.Current.Value = beatmap.Metadata.Source ?? string.Empty;
                tagsInput.Current.Value = beatmap.Metadata.Tags != null && beatmap.Metadata.Tags.Count > 0
                    ? string.Join(", ", beatmap.Metadata.Tags)
                    : string.Empty;
                releaseInput.Current.Value = beatmap.Metadata.ReleaseDate ?? string.Empty;
                providerInput.Current.Value = beatmap.Metadata.Provider ?? string.Empty;
                descriptionInput.Current.Value = beatmap.Metadata.Description ?? string.Empty;
                bpmInput.Current.Value = beatmap.Timing.Bpm.ToString("0.##", CultureInfo.InvariantCulture);
                offsetInput.Current.Value = beatmap.Timing.Offset.ToString(CultureInfo.InvariantCulture);
            }

            suppressInspectorFieldSync = false;

            refreshMetadataStatus();
            updateInspectorEnabledState(beatmap != null);
            updateInspectorStats();
            refreshComponentReassignmentOptions();
            updateSelectionSummary();
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

        private Drawable createTimelineSection(string title, params Drawable[] controls)
        {
            var titleText = new SpriteText
            {
                Text = title,
                Font = BeatSightFont.Caption(12.4f),
                Colour = EditorColours.TextSecondary
            };
            timelineSectionTitleTexts.Add(titleText);

            var controlsRow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Children = controls
            };
            timelineSectionControlRows.Add(controlsRow);

            var sectionBody = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6, 5),
                Padding = new MarginPadding { Horizontal = 11, Vertical = 8 },
                Children = new Drawable[]
                {
                    titleText,
                    controlsRow
                }
            };
            timelineSectionBodies.Add(sectionBody);

            return new Container
            {
                AutoSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 9,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.08f)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.11f
                    },
                    sectionBody
                }
            };
        }

        private BasicButton createTimelineMiniButton(string text, Action action, float width = 36)
        {
            var button = new BasicButton
            {
                Size = new Vector2(width, 32),
                BackgroundColour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.18f),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Masking = true,
                CornerRadius = 8,
                Action = action
            };
            timelineMiniButtons.Add(button);

            var labelText = new SpriteText
            {
                Text = text,
                Font = BeatSightFont.Button(11.9f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Truncate = true,
                MaxWidth = Math.Max(18, width - 12),
                UseFullGlyphHeight = false
            };
            timelineMiniButtonTexts.Add(labelText);
            button.Add(labelText);

            return button;
        }

        private void refreshTimelineToolboxState()
        {
            syncTimelineZoomDisplay();
            updateWaveformScaleDisplay();
            syncSnapControl();
            syncBeatGridControl();
        }

        private void syncTimelineZoomDisplay()
        {
            if (timelineZoomValueText != null)
                timelineZoomValueText.Text = $"{timelineZoom:0.00}x";

            if (timelineZoomSlider != null)
            {
                suppressTimelineZoomSync = true;
                timelineZoomSlider.Current.Value = timelineZoom;
                suppressTimelineZoomSync = false;
            }
        }

        private void adjustTimelineZoom(bool increase)
        {
            double factor = increase ? 1.2 : 1 / 1.2;
            applyTimelineZoom(timelineZoom * factor);
        }

        private void beginTimelineZoomInteraction()
        {
            if (timelineZoomInteractionActive)
                return;

            timeline?.BeginZoomInteraction();
            timelineZoomInteractionActive = true;
            timelineZoomInteractionDirty = false;
            pendingTimelineZoomPreview = null;
            lastTimelineZoomPreviewAppliedAt = double.NegativeInfinity;
        }

        private void previewTimelineZoom(double zoom)
        {
            double clamped = Math.Clamp(zoom, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);
            if (Math.Abs(clamped - timelineZoom) < 0.0001)
            {
                timelineZoomValueText.Text = $"{clamped:0.00}x";
                return;
            }

            double now = Time.Current;
            if (now - lastTimelineZoomPreviewAppliedAt < timelineZoomPreviewMinIntervalMs)
            {
                pendingTimelineZoomPreview = clamped;
                timelineZoomValueText.Text = $"{clamped:0.00}x";
                timelineZoomInteractionDirty = true;
                return;
            }

            applyTimelineZoomPreviewNow(clamped, now);
        }

        private void applyTimelineZoomPreviewNow(double zoom, double timestamp)
        {
            timelineZoom = zoom;
            timeline?.SetZoom(timelineZoom);
            timelineZoomValueText.Text = $"{timelineZoom:0.00}x";
            timelineZoomInteractionDirty = true;
            lastTimelineZoomPreviewAppliedAt = timestamp;
            pendingTimelineZoomPreview = null;
        }

        private void endTimelineZoomInteraction()
        {
            if (!timelineZoomInteractionActive)
                return;

            if (pendingTimelineZoomPreview.HasValue)
                applyTimelineZoomPreviewNow(pendingTimelineZoomPreview.Value, Time.Current);

            timeline?.EndZoomInteraction();
            timelineZoomInteractionActive = false;

            if (!timelineZoomInteractionDirty)
            {
                syncTimelineZoomDisplay();
                return;
            }

            timelineZoomInteractionDirty = false;
            commitTimelineZoomChange();
        }

        private void commitTimelineZoomChange()
        {
            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.TimelineZoom = timelineZoom;
            }

            syncTimelineZoomDisplay();
            persistEditorDefaults();
        }

        private void applyTimelineZoom(double zoom)
        {
            double clamped = Math.Clamp(zoom, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);
            if (Math.Abs(clamped - timelineZoom) < 0.0001)
            {
                syncTimelineZoomDisplay();
                return;
            }

            timelineZoom = clamped;
            timeline?.SetZoom(timelineZoom);
            commitTimelineZoomChange();
        }

        private void beginWaveformScaleInteraction()
        {
            if (waveformScaleInteractionActive)
                return;

            waveformScaleInteractionActive = true;
            waveformScaleInteractionDirty = false;
            pendingWaveformScalePreview = null;
            liveWaveformScalePreviewValue = null;
            lastWaveformScalePreviewAppliedAt = double.NegativeInfinity;
        }

        private void previewWaveformScale(double scale)
        {
            double clamped = Math.Clamp(scale, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);
            if (liveWaveformScalePreviewValue.HasValue && Math.Abs(clamped - liveWaveformScalePreviewValue.Value) < 0.0001)
            {
                updateWaveformScaleValueText(clamped);
                return;
            }

            double now = Time.Current;
            if (now - lastWaveformScalePreviewAppliedAt < waveformScalePreviewMinIntervalMs)
            {
                pendingWaveformScalePreview = clamped;
                waveformScaleInteractionDirty = true;
                updateWaveformScaleValueText(clamped);
                return;
            }

            applyWaveformScalePreviewNow(clamped, now);
        }

        private void applyWaveformScalePreviewNow(double scale, double timestamp)
        {
            double clamped = Math.Clamp(scale, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);
            liveWaveformScalePreviewValue = clamped;
            timeline?.PreviewWaveformScale(clamped);
            updateWaveformScaleValueText(clamped);
            waveformScaleInteractionDirty = true;
            lastWaveformScalePreviewAppliedAt = timestamp;
            pendingWaveformScalePreview = null;
        }

        private void endWaveformScaleInteraction()
        {
            if (!waveformScaleInteractionActive)
                return;

            if (pendingWaveformScalePreview.HasValue)
                applyWaveformScalePreviewNow(pendingWaveformScalePreview.Value, Time.Current);

            waveformScaleInteractionActive = false;

            double committed = liveWaveformScalePreviewValue ?? waveformScale;
            liveWaveformScalePreviewValue = null;
            pendingWaveformScalePreview = null;

            if (!waveformScaleInteractionDirty)
            {
                updateWaveformScaleDisplay();
                return;
            }

            waveformScaleInteractionDirty = false;
            setWaveformScale(committed, forceApply: true);
        }

        private void updateWaveformScaleValueText(double value)
        {
            if (waveformScaleValueText != null)
                waveformScaleValueText.Text = $"{value:0.00}x";
        }

        private void updateWaveformScaleDisplay()
        {
            updateWaveformScaleValueText(waveformScale);

            if (waveformScaleSlider != null)
            {
                suppressWaveformScaleSync = true;
                waveformScaleSlider.Current.Value = waveformScale;
                suppressWaveformScaleSync = false;
            }
        }

        private void setWaveformScale(double scale, bool forceApply = false)
        {
            double clamped = Math.Clamp(scale, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);
            bool changed = Math.Abs(clamped - waveformScale) >= 0.0001;

            if (!changed && !forceApply)
            {
                updateWaveformScaleDisplay();
                return;
            }

            waveformScale = clamped;
            timeline?.SetWaveformScale(waveformScale, forceApply);

            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.WaveformScale = waveformScale;
            }

            updateWaveformScaleDisplay();
            persistEditorDefaults();
        }

        private void adjustWaveformScale(bool increase)
        {
            if (waveformScaleInteractionActive)
                endWaveformScaleInteraction();

            setWaveformScale(waveformScale + (increase ? 0.1 : -0.1));
        }

        private void adjustSnapDivisor(bool increase)
        {
            int index = Array.IndexOf(allowedSnapDivisors, snapDivisor);
            if (index < 0)
            {
                int search = Array.BinarySearch(allowedSnapDivisors, snapDivisor);
                index = search >= 0 ? search : Math.Clamp(~search, 0, allowedSnapDivisors.Length - 1);
            }

            int newIndex = Math.Clamp(index + (increase ? 1 : -1), 0, allowedSnapDivisors.Length - 1);
            int newDivisor = allowedSnapDivisors[newIndex];
            if (newDivisor == snapDivisor)
            {
                syncSnapControl();
                return;
            }

            applySnapDivisor(newDivisor);
        }

        private void applySnapDivisor(int divisor)
        {
            int adjusted = coerceSnapDivisor(divisor);
            if (adjusted == snapDivisor)
            {
                syncSnapControl();
                return;
            }

            snapDivisor = adjusted;
            timeline?.SetSnap(snapDivisor, beatmap?.Timing.Bpm ?? 120);

            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.SnapDivisor = snapDivisor;
            }

            syncSnapControl();
            persistEditorDefaults();
        }

        private void syncSnapControl()
        {
            if (snapDivisorText != null)
                snapDivisorText.Text = $"1/{snapDivisor}";
        }

        private void setBeatGridVisibility(bool visible)
        {
            if (beatGridVisible == visible)
            {
                syncBeatGridControl();
                return;
            }

            beatGridVisible = visible;
            timeline?.SetBeatGridVisible(beatGridVisible);

            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.BeatGridVisible = beatGridVisible;
            }

            syncBeatGridControl();
            persistEditorDefaults();
        }

        private void syncBeatGridControl()
        {
            if (beatGridCheckbox == null)
                return;

            suppressBeatGridSync = true;
            beatGridCheckbox.Current.Value = beatGridVisible;
            suppressBeatGridSync = false;
        }

        private void toggleBeatGrid()
            => setBeatGridVisibility(!beatGridVisible);

        private void applyEditorDefaultsFromConfig()
        {
            if (editorTimelineZoomDefault != null)
                timelineZoom = Math.Clamp(editorTimelineZoomDefault.Value, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);

            if (editorWaveformScaleDefault != null)
                waveformScale = Math.Clamp(editorWaveformScaleDefault.Value, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);

            if (editorBeatGridVisibleDefault != null)
                beatGridVisible = editorBeatGridVisibleDefault.Value;
        }

        private void persistEditorDefaults()
        {
            if (suppressEditorDefaultPersistence)
                return;

            if (editorTimelineZoomDefault != null)
                editorTimelineZoomDefault.Value = timelineZoom;

            if (editorWaveformScaleDefault != null)
                editorWaveformScaleDefault.Value = waveformScale;

            if (editorBeatGridVisibleDefault != null)
                editorBeatGridVisibleDefault.Value = beatGridVisible;
        }

        private Drawable createFooter()
        {
            footerKeyTexts.Clear();
            footerActionTexts.Clear();

            var tips = new (string key, string action)[]
            {
                ("Esc", "Clear selection / Back"),
                ("Space", "Play/Pause"),
                ("Shift+Space", "Rewind to start"),
                ("Left/Right", "Seek"),
                ("Ctrl +/-", "Zoom timeline"),
                ("Ctrl+Alt +/-", "Scale waveform"),
                ("[ / ]", "Change snap"),
                ("G", "Toggle beat grid"),
                ("I", "Toggle inspector panel (compact)"),
                (", / .", "Previous/next note"),
                ("Home / End", "Jump first/last note"),
                ("PgUp/PgDn", "Shift selection notation lane"),
                ("Ctrl+PgUp/PgDn", "Cycle selection articulation"),
                ("1-9", "Quick lane reassign (left->right)"),
                ("Alt+Left/Right", "Nudge selected note/range"),
                ("Delete", "Remove selected note/range"),
                ("Q", "Quantize selected note/range"),
                ("Ctrl+A", "Select all notes"),
                ("Ctrl+D", "Duplicate selected note/range"),
                ("Ctrl+S", "Save"),
                ("Ctrl+Z", "Undo"),
                ("Ctrl+Y / Ctrl+Shift+Z", "Redo")
            };

            var tipFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(18, 0),
                Children = tips.Select(t => createTip(t.key, t.action)).ToArray()
            };
            footerTipFlow = tipFlow;

            var horizontalScroll = new BeatSightScrollContainer(Direction.Horizontal)
            {
                RelativeSizeAxes = Axes.Both,
                ScrollbarVisible = false,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Y,
                    AutoSizeAxes = Axes.X,
                    Child = tipFlow
                }
            };

            return footerRootContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 12, Vertical = 11 },
                Masking = true,
                CornerRadius = 12,
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
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.1f
                    },
                    footerInnerContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 15, Vertical = 9 },
                        Child = horizontalScroll
                    },
                }
            };
        }

        private Drawable createTip(string key, string action)
        {
            var keyText = new SpriteText
            {
                Text = key,
                Font = BeatSightFont.Title(11.2f),
                Colour = EditorColours.TextPrimary,
                Margin = new MarginPadding { Horizontal = 7, Vertical = 4 },
                UseFullGlyphHeight = false
            };
            footerKeyTexts.Add(keyText);

            var actionText = new SpriteText
            {
                Text = action,
                Font = BeatSightFont.Caption(11f),
                Colour = EditorColours.TextSecondary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };
            footerActionTexts.Add(actionText);

            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Children = new Drawable[]
                {
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Masking = true,
                        CornerRadius = 6,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.18f)
                            },
                            keyText
                        }
                    },
                    actionText
                }
            };
        }

        private Drawable createHistoryColumn(string title, out SpriteText headerText, out FillFlowContainer listFlow)
        {
            headerText = new SpriteText
            {
                Text = title,
                Font = BeatSightFont.Title(11f),
                Colour = EditorColours.TextPrimary
            };

            listFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(3)
            };

            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6),
                Children = new Drawable[]
                {
                    headerText,
                    listFlow
                }
            };
        }

        private void updateHistoryPanel()
        {
            if (historyPanel == null || undoHistoryFlow == null || redoHistoryFlow == null)
                return;

            updateHistoryColumn(undoStack, undoHeaderText, undoHistoryFlow, "Undo");
            updateHistoryColumn(redoStack, redoHeaderText, redoHistoryFlow, "Redo");

            bool anyEntries = undoStack.Count > 0 || redoStack.Count > 0;
            if (anyEntries)
            {
                historyPanel.Show();
                historyPanel.FadeTo(1f, 120, Easing.OutQuint);
            }
            else
            {
                historyPanel.Hide();
            }
        }

        private void updateHistoryColumn(IReadOnlyList<EditorSnapshot> stack, SpriteText? header, FillFlowContainer listFlow, string title)
        {
            if (header != null)
                header.Text = $"{title} ({stack.Count})";

            listFlow.Clear();

            if (stack.Count == 0)
                return;

            int startIndex = Math.Max(0, stack.Count - historyPreviewCount);
            for (int i = stack.Count - 1; i >= startIndex; i--)
            {
                bool isNewest = i == stack.Count - 1;
                listFlow.Add(createHistoryEntry(stack[i], isNewest));
            }
        }

        private Drawable createHistoryEntry(EditorSnapshot snapshot, bool emphasise)
        {
            string title = string.IsNullOrWhiteSpace(snapshot.Description)
                ? formatTime(snapshot.CurrentTime)
                : snapshot.Description;

            int snapValue = snapshot.SnapDivisor > 0 ? snapshot.SnapDivisor : snapDivisor;
            double zoomValue = snapshot.Zoom > 0 ? snapshot.Zoom : timelineZoom;

            string details = $"{formatTime(snapshot.CurrentTime)} | Snap {snapValue} | Zoom {zoomValue:0.00}";

            return new Container
            {
                AutoSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 5,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = emphasise
                            ? EditorColours.Lighten(EditorColours.CardBackground, 1.15f)
                            : EditorColours.Lighten(EditorColours.CardBackground, 1.02f)
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(1, 0),
                        Padding = new MarginPadding { Horizontal = 6, Vertical = 4 },
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = title,
                                Font = BeatSightFont.Body(9.6f),
                                Colour = emphasise ? EditorColours.HistoryEntryEmphasis : EditorColours.HistoryEntryMuted
                            },
                            new SpriteText
                            {
                                Text = details,
                                Font = BeatSightFont.Caption(8.8f),
                                Colour = EditorColours.TextMuted
                            }
                        }
                    }
                }
            };
        }

        private Drawable createHistoryPlaceholder()
        {
            return new SpriteText
            {
                Text = "No entries yet",
                Font = BeatSightFont.Caption(8.8f),
                Colour = EditorColours.TextMuted
            };
        }

        private void onTimelineSeekRequested(double timeMs)
        {
            double target = Math.Clamp(timeMs, 0, trackLength > 0 ? trackLength : Math.Max(0, timeMs));
            seekToTime(target);
            if (isPlaying && track != null && !track.IsRunning)
                track.Start();
        }

        private void onTimelineNoteSelected(HitObject hit)
        {
            selectedHitObject = hit;
            setStatusDetail($"Selected {hit.Component} @ {formatTime(hit.Time)}");
            updateSelectionSummary();
            seekToTime(hit.Time);
        }

        private void onTimelineSelectionChanged(double? start, double? end)
        {
            if (start.HasValue && end.HasValue && Math.Abs(end.Value - start.Value) >= 1)
                selectedHitObject = null;

            updateSelectionSummary();
        }

        private void onTimelineNoteChanged(HitObject hit)
        {
            if (beatmap == null)
                return;

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            playbackPreview?.RefreshBeatmap();
            markUnsaved();
            refreshUnsavedState();

            if (selectedHitObject != null && !beatmap.HitObjects.Contains(selectedHitObject))
                selectedHitObject = null;

            refreshComponentReassignmentOptions();
            updateSelectionSummary();
            updateInspectorStats();
        }

        private void onTimelineEditBegan()
            => prepareUndoSnapshot();

        private void onTimelineZoomChanged(double zoom)
            => applyTimelineZoom(zoom);

        private void onTimelineSnapDivisorChanged(int divisor)
        {
            if (divisor <= 0)
                return;

            applySnapDivisor(divisor);
        }

        private void onPreviewModeChanged(ValueChangedEvent<EditorPreviewMode> mode)
        {
            switch (mode.NewValue)
            {
                case EditorPreviewMode.Playfield2D:
                    laneViewModeBindable.Value = LaneViewMode.TwoDimensional;
                    setStatusDetail("2D view");
                    break;

                case EditorPreviewMode.Manuscript:
                    laneViewModeBindable.Value = LaneViewMode.Manuscript;
                    setStatusDetail("Sheet Music view");
                    break;

                case EditorPreviewMode.Playfield3D:
                default:
                    laneViewModeBindable.Value = LaneViewMode.ThreeDimensional;
                    setStatusDetail("3D view");
                    break;
            }

            syncManuscriptFocus();
        }

        private void onLaneViewModeChanged(ValueChangedEvent<LaneViewMode> change)
        {
            // Sync previewMode to match the setting
            switch (change.NewValue)
            {
                case LaneViewMode.TwoDimensional:
                    if (previewMode.Value != EditorPreviewMode.Playfield2D)
                        previewMode.Value = EditorPreviewMode.Playfield2D;
                    break;
                case LaneViewMode.ThreeDimensional:
                    if (previewMode.Value != EditorPreviewMode.Playfield3D)
                        previewMode.Value = EditorPreviewMode.Playfield3D;
                    break;
                case LaneViewMode.Manuscript:
                    if (previewMode.Value != EditorPreviewMode.Manuscript)
                        previewMode.Value = EditorPreviewMode.Manuscript;
                    break;
            }

            if (playbackPreview != null)
            {
                Schedule(() => playbackPreview.RefreshBeatmap());
            }

            syncManuscriptFocus();
        }

        private void prepareUndoSnapshot()
        {
            if (beatmap == null || editSnapshotArmed)
                return;

            var snapshot = createSnapshot();

            if (undoStack.Count > 0 && undoStack[^1].BeatmapJson == snapshot.BeatmapJson)
                return;

            redoStack.Clear();
            pushSnapshot(undoStack, snapshot);
            editSnapshotArmed = true;
            updateActionButtons();
        }

        private EditorSnapshot createSnapshot()
        {
            if (beatmap == null)
                throw new InvalidOperationException("No beatmap loaded.");

            return new EditorSnapshot
            {
                BeatmapJson = serializeBeatmap(beatmap),
                CurrentTime = currentTime,
                Zoom = timeline?.CurrentZoom ?? timelineZoom,
                SnapDivisor = snapDivisor,
                WaveformScale = waveformScale,
                BeatGridVisible = beatGridVisible,
                Description = !string.IsNullOrWhiteSpace(statusDetailText)
                    ? statusDetailText!
                    : $"State at {formatTime(currentTime)}"
            };
        }

        private void undoLastEdit()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Nothing to undo");
                return;
            }

            if (undoStack.Count == 0)
            {
                appendStatusDetail("Nothing to undo");
                return;
            }

            var currentSnapshot = createSnapshot();
            if (redoStack.Count > 0 && redoStack[^1].BeatmapJson == currentSnapshot.BeatmapJson)
            {
                // Avoid stacking duplicate redo states.
            }
            else
            {
                pushSnapshot(redoStack, currentSnapshot);
            }

            var snapshot = undoStack[^1];
            undoStack.RemoveAt(undoStack.Count - 1);
            restoreSnapshot(snapshot);
            appendStatusDetail("Undo applied");
            updateActionButtons();
        }

        private void redoLastEdit()
        {
            if (beatmap == null)
            {
                appendStatusDetail("Nothing to redo");
                return;
            }

            if (redoStack.Count == 0)
            {
                appendStatusDetail("Nothing to redo");
                return;
            }

            var currentSnapshot = createSnapshot();
            if (undoStack.Count > 0 && undoStack[^1].BeatmapJson == currentSnapshot.BeatmapJson)
            {
                // Existing undo top already reflects current state.
            }
            else
            {
                pushSnapshot(undoStack, currentSnapshot);
            }

            var snapshot = redoStack[^1];
            redoStack.RemoveAt(redoStack.Count - 1);
            restoreSnapshot(snapshot);
            appendStatusDetail("Redo applied");
            updateActionButtons();
        }

        private void restoreSnapshot(EditorSnapshot snapshot)
        {
            bool originalPersistenceState = suppressEditorDefaultPersistence;
            suppressEditorDefaultPersistence = true;

            var restored = JsonConvert.DeserializeObject<Beatmap>(snapshot.BeatmapJson);
            if (restored == null)
            {
                appendStatusDetail("Undo failed");
                suppressEditorDefaultPersistence = originalPersistenceState;
                return;
            }

            beatmap = restored;
            trackLength = beatmap.Audio.Duration;
            snapDivisor = coerceSnapDivisor(snapshot.SnapDivisor > 0 ? snapshot.SnapDivisor : snapDivisor);
            timelineZoom = Math.Clamp(snapshot.Zoom, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);
            waveformScale = Math.Clamp(snapshot.WaveformScale > 0 ? snapshot.WaveformScale : waveformScale, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);
            beatGridVisible = snapshot.BeatGridVisible;
            currentTime = Math.Clamp(snapshot.CurrentTime, 0, trackLength > 0 ? trackLength : snapshot.CurrentTime);

            reloadTimeline();
            timeline.SetCurrentTime(currentTime);
            timeText.Text = formatTime(currentTime);

            var editorInfo = ensureEditorInfo();
            editorInfo.SnapDivisor = snapDivisor;
            editorInfo.TimelineZoom = timelineZoom;
            editorInfo.WaveformScale = waveformScale;
            editorInfo.BeatGridVisible = beatGridVisible;

            populateInspectorFromBeatmap();
            refreshUnsavedState(forceRecompute: true);
            editSnapshotArmed = false;
            lastInspectorSnapshotAtUtc = DateTime.MinValue;
            refreshTimelineToolboxState();

            suppressEditorDefaultPersistence = originalPersistenceState;
            persistEditorDefaults();
        }

        private void refreshUnsavedState(bool forceRecompute = false)
        {
            if (beatmap == null)
            {
                hasUnsavedChanges = false;
                updateStatusText();
                return;
            }

            if (!forceRecompute && hasUnsavedChanges)
            {
                updateStatusText();
                return;
            }

            if (lastSavedSnapshot == null)
            {
                hasUnsavedChanges = true;
            }
            else
            {
                hasUnsavedChanges = serializeBeatmap(beatmap) != lastSavedSnapshot;
            }

            updateStatusText();
        }

        private string serializeBeatmap(Beatmap map)
            => JsonConvert.SerializeObject(map, Formatting.None);

        private void pushSnapshot(List<EditorSnapshot> stack, EditorSnapshot snapshot)
        {
            if (stack.Count >= maxUndoSteps)
                stack.RemoveAt(0);

            stack.Add(snapshot);
        }

        private int coerceSnapDivisor(int divisor)
        {
            if (divisor <= 0)
                return allowedSnapDivisors[0];

            int closest = allowedSnapDivisors[0];
            int minDiff = Math.Abs(divisor - closest);

            for (int i = 1; i < allowedSnapDivisors.Length; i++)
            {
                int candidate = allowedSnapDivisors[i];
                int diff = Math.Abs(candidate - divisor);

                if (diff < minDiff)
                {
                    minDiff = diff;
                    closest = candidate;
                }
            }

            return closest;
        }

        private EditorInfo ensureEditorInfo()
        {
            if (beatmap == null)
                throw new InvalidOperationException("No beatmap loaded.");

            var editor = beatmap.Editor ??= new EditorInfo();

            if (!editor.SnapDivisor.HasValue)
                editor.SnapDivisor = snapDivisor;

            if (!editor.VisualLanes.HasValue)
                editor.VisualLanes = 7;

            if (!editor.TimelineZoom.HasValue)
                editor.TimelineZoom = timelineZoom;

            if (!editor.WaveformScale.HasValue)
                editor.WaveformScale = waveformScale;

            if (!editor.BeatGridVisible.HasValue)
                editor.BeatGridVisible = beatGridVisible;

            return editor;
        }

        private void saveBeatmap()
        {
            if (isSaving)
            {
                appendStatusDetail("Save already in progress");
                return;
            }

            if (beatmap == null)
            {
                appendStatusDetail("Nothing to save yet");
                return;
            }

            if (beatmap.HitObjects.Count == 0)
            {
                setStatusDetail("Add at least one hit object before saving");
                return;
            }

            EditorInfo editorInfo;
            try
            {
                editorInfo = ensureEditorInfo();
                editorInfo.SnapDivisor = snapDivisor;
                editorInfo.TimelineZoom = timelineZoom;
                editorInfo.WaveformScale = waveformScale;
                editorInfo.BeatGridVisible = beatGridVisible;
            }
            catch (Exception ex)
            {
                appendStatusDetail(ex.Message);
                return;
            }

            isSaving = true;
            setStatusDetail("Saving...");
            updateActionButtons();

            try
            {
                string savedPath = saveBeatmapInternal(beatmap);
                beatmapPath = savedPath;
                lastSavedSnapshot = serializeBeatmap(beatmap);
                hasUnsavedChanges = false;
                editSnapshotArmed = false;
                setStatusDetail($"Saved {Path.GetFileName(savedPath)}");
                reloadTimeline();
                refreshTimelineToolboxState();
                updateStatusText();
                updateActionButtons();
            }
            catch (Exception ex)
            {
                setStatusDetail($"Save failed: {ex.Message}");
                refreshUnsavedState(forceRecompute: true);
            }
            finally

            {
                isSaving = false;
                updateActionButtons();
            }
        }

        private string saveBeatmapInternal(Beatmap map)
        {
            if (map != beatmap)
                throw new InvalidOperationException("Beatmap reference changed during save");

            if (string.IsNullOrWhiteSpace(map.Metadata.Title) || string.IsNullOrWhiteSpace(map.Metadata.Artist))
                throw new InvalidOperationException("Please provide both title and artist before saving");

            if (map.HitObjects.Count == 0)
                throw new InvalidOperationException("Add at least one hit object before saving");

            string audioSource = resolveAudioSourceForSave();

            string targetDirectory;
            bool isExistingBeatmap = !string.IsNullOrEmpty(beatmapPath);

            if (isExistingBeatmap)
            {
                targetDirectory = Path.GetDirectoryName(beatmapPath!) ?? throw new InvalidOperationException("Beatmap path invalid");
            }
            else
            {
                targetDirectory = prepareNewBeatmapFolder();
            }

            Directory.CreateDirectory(targetDirectory);

            string slug = createSlug($"{map.Metadata.Artist}-{map.Metadata.Title}");
            if (string.IsNullOrWhiteSpace(slug))
                slug = $"beatmap-{DateTime.UtcNow:yyyyMMddHHmmss}";

            string targetPath = isExistingBeatmap
                ? beatmapPath!
                : Path.Combine(targetDirectory, $"{slug}.bsm");

            if (!isExistingBeatmap)
            {
                int counter = 1;
                while (File.Exists(targetPath))
                {
                    targetPath = Path.Combine(targetDirectory, $"{slug}-{counter++}.bsm");
                }
            }

            string destAudioFile = Path.GetFileName(audioSource);
            if (string.IsNullOrEmpty(destAudioFile))
                throw new InvalidOperationException("Unable to determine audio filename");

            string destAudioPath = Path.Combine(targetDirectory, destAudioFile);

            string sourceHash = computeFileHash(audioSource);
            bool requiresCopy = !File.Exists(destAudioPath) || !string.Equals(computeFileHash(destAudioPath), sourceHash, StringComparison.OrdinalIgnoreCase);

            if (requiresCopy)
            {
                File.Copy(audioSource, destAudioPath, overwrite: true);
            }

            map.Audio.Filename = destAudioFile;
            map.Audio.Hash = sourceHash;

            if (trackLength > 0)
                map.Audio.Duration = (int)Math.Round(trackLength);

            BeatmapLoader.SaveToFile(map, targetPath);

            return targetPath;
        }

        private string resolveAudioSourceForSave()
        {
            if (beatmap == null)
                throw new InvalidOperationException("No beatmap loaded");

            if (!string.IsNullOrWhiteSpace(beatmap.Audio.Filename))
            {
                string? candidate = resolveAudioAbsolutePath(beatmap.Audio.Filename);
                if (!string.IsNullOrEmpty(candidate))
                    return candidate;
            }

            throw new InvalidOperationException("Audio reference missing; please import audio before saving");
        }

        private string? resolveAudioAbsolutePath(string audioReference)
        {
            if (string.IsNullOrWhiteSpace(audioReference))
                return null;

            if (Path.IsPathRooted(audioReference) && File.Exists(audioReference))
                return audioReference;

            if (beatmapPath != null)
            {
                string beatmapDirectory = Path.GetDirectoryName(beatmapPath) ?? string.Empty;
                string candidate = Path.Combine(beatmapDirectory, audioReference);
                if (File.Exists(candidate))
                    return candidate;
            }

            string storageCandidate = host.Storage.GetFullPath(audioReference.Replace('/', Path.DirectorySeparatorChar));
            if (File.Exists(storageCandidate))
                return storageCandidate;

            return null;
        }

        private string prepareNewBeatmapFolder()
        {
            if (beatmap == null)
                throw new InvalidOperationException("No beatmap loaded");

            // Store editor-created beatmaps in the roaming user Songs directory.
            string baseDirectory = UserAssetDirectories.GetPath(UserAssetDirectories.Songs);
            Directory.CreateDirectory(baseDirectory);

            // Format: {artist} - {title} ({creator})
            string artist = string.IsNullOrWhiteSpace(beatmap.Metadata.Artist) ? "Unknown Artist" : beatmap.Metadata.Artist;
            string title = string.IsNullOrWhiteSpace(beatmap.Metadata.Title) ? "Untitled" : beatmap.Metadata.Title;
            string creator = string.IsNullOrWhiteSpace(beatmap.Metadata.Creator) ? "Unknown" : beatmap.Metadata.Creator;

            string folderName = $"{artist} - {title} ({creator})";
            string slug = createSlug(folderName);

            if (string.IsNullOrWhiteSpace(slug))
                slug = $"beatmap-{DateTime.UtcNow:yyyyMMddHHmmss}";

            string target = Path.Combine(baseDirectory, slug);
            int counter = 1;
            while (Directory.Exists(target))
            {
                target = Path.Combine(baseDirectory, $"{slug}-{counter++}");
            }

            Directory.CreateDirectory(target);
            return target;
        }

        private static string computeFileHash(string path)
        {
            using var stream = File.OpenRead(path);
            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(stream);

            var builder = new StringBuilder(hash.Length * 2);
            foreach (byte b in hash)
                builder.AppendFormat("{0:x2}", b);

            return builder.ToString();
        }

        private static string createSlug(string? value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return string.Empty;

            var builder = new StringBuilder();

            foreach (char c in value)
            {
                char lower = char.ToLowerInvariant(c);

                if (char.IsLetterOrDigit(lower))
                {
                    builder.Append(lower);
                    continue;
                }

                if (builder.Length > 0 && builder[^1] != '-')
                    builder.Append('-');
            }

            while (builder.Length > 0 && builder[^1] == '-')
                builder.Length--;

            return builder.ToString();
        }

        // EditorSnapshot class extracted to EditorCommandManager.cs

        private void reloadTimeline()
        {
            if (timeline == null)
                return;

            if (beatmap == null)
            {
                Logger.Log("[EditorScreen] reloadTimeline: beatmap is NULL", LoggingTarget.Runtime, LogLevel.Important);
                timeline.LoadBeatmap(new Beatmap(), Math.Max(trackLength, 60000), waveformData);
                timeline.SetZoom(timelineZoom);
                timeline.SetSnap(snapDivisor, 120);
                timeline.SetWaveformScale(waveformScale);
                timeline.SetBeatGridVisible(beatGridVisible);
                timeline.SetCurrentTime(currentTime);
                playbackPreview?.SetBeatmap(null);
                updateInspectorEnabledState(false);
                selectedHitObject = null;
                updateSelectionSummary();
                updateInspectorStats();
                populateInspectorFromBeatmap();
                updatePlaybackAvailabilityUI();
                return;
            }

            double duration = trackLength > 0
                ? trackLength
                : Math.Max(beatmap.Audio.Duration, beatmap.HitObjects.Count > 0 ? beatmap.HitObjects[^1].Time + 5000 : 60000);

            Logger.Log($"[EditorScreen] reloadTimeline: setting beatmap with {beatmap.HitObjects.Count} notes, playbackPreview={(playbackPreview == null ? "NULL" : "exists")}", LoggingTarget.Runtime, LogLevel.Important);

            timeline.LoadBeatmap(beatmap, duration, waveformData);
            timeline.SetZoom(timelineZoom);
            timeline.SetSnap(snapDivisor, beatmap.Timing.Bpm);
            timeline.SetWaveformScale(waveformScale);
            timeline.SetBeatGridVisible(beatGridVisible);
            timeline.SetCurrentTime(currentTime);
            playbackPreview?.SetBeatmap(beatmap);
            if (selectedHitObject != null && !beatmap.HitObjects.Contains(selectedHitObject))
                selectedHitObject = null;
            updateSelectionSummary();
            updateInspectorEnabledState(true);
            updateInspectorStats();
            updatePlaybackAvailabilityUI();
        }
        private void queueWaveformLoad(string absolutePath)
        {
            if (string.IsNullOrEmpty(absolutePath) || !File.Exists(absolutePath))
                return;

            waveformLoadCts?.Cancel();
            waveformLoadCts?.Dispose();
            waveformLoadCts = new CancellationTokenSource();
            var token = waveformLoadCts.Token;

            fullTrackWaveform = null;
            drumStemWaveform = null;
            waveformData = null;
            timeline?.UpdateWaveform(null);

            Task.Run(async () =>
            {
                var mainTask = WaveformDataBuilder.BuildAsync(absolutePath, cancellationToken: token);
                Task<WaveformData?>? drumTask = null;

                if (beatmap?.Audio.DrumStem != null && !string.IsNullOrEmpty(beatmapPath))
                {
                    string? beatmapDir = Path.GetDirectoryName(beatmapPath);
                    if (beatmapDir != null)
                    {
                        string drumStemPath = Path.Combine(beatmapDir, beatmap.Audio.DrumStem);
                        if (File.Exists(drumStemPath))
                        {
                            drumTask = WaveformDataBuilder.BuildAsync(drumStemPath, cancellationToken: token);
                        }
                    }
                }

                await mainTask.ConfigureAwait(false);
                if (drumTask != null) await drumTask.ConfigureAwait(false);

                return (Main: mainTask.Result, Drum: drumTask?.Result);
            }, token)
            .ContinueWith(task =>
            {
                if (task.IsCanceled || token.IsCancellationRequested)
                    return;

                if (task.IsFaulted)
                {
                    Schedule(() => appendStatusDetail("Waveform generation failed"));
                    return;
                }

                var result = task.Result;
                if (result.Main == null)
                {
                    Schedule(() => appendStatusDetail("Waveform unavailable"));
                    return;
                }

                fullTrackWaveform = result.Main;
                drumStemWaveform = result.Drum;

                Schedule(() =>
                {
                    if (!token.IsCancellationRequested)
                    {
                        updateWaveformSource();
                        timeline?.SetWaveformScale(waveformScale);
                        timeline?.SetCurrentTime(currentTime);
                    }
                });
            }, TaskScheduler.Default);
        }

        private void updateWaveformSource()
        {
            waveformData = showDrumStem.Value && drumStemWaveform != null ? drumStemWaveform : fullTrackWaveform;
            timeline?.UpdateWaveform(waveformData);
        }

        private void onTrackCompleted()
        {
            Schedule(() =>
            {
                stopPlayback(silent: true);
                currentTime = trackLength;
                timeText.Text = formatTime(currentTime);
                timeline?.SetCurrentTime(currentTime);
                appendStatusDetail("Playback finished");
            });
        }

        private void loadBeatmap(string path)
        {
            try
            {
                beatmap = BeatmapLoader.LoadFromFile(path);
                beatmapPath = path;
                initialBeatmapBpm = beatmap.Timing.Bpm;

                // Set clean status with just artist and title
                string artist = beatmap.Metadata.Artist ?? "Unknown Artist";
                string title = beatmap.Metadata.Title ?? "Untitled";
                setStatusBase($"Editing: {artist} - {title}");
                setStatusDetail(playbackAvailable ? null : offlinePlaybackMessage);

                hasUnsavedChanges = false;
                undoStack.Clear();
                redoStack.Clear();
                editSnapshotArmed = false;
                lastInspectorSnapshotAtUtc = DateTime.MinValue;
                snapDivisor = coerceSnapDivisor(beatmap.Editor?.SnapDivisor ?? 4);
                bool previousPersistenceState = suppressEditorDefaultPersistence;
                suppressEditorDefaultPersistence = true;

                if (beatmap.Editor?.TimelineZoom.HasValue == true)
                    timelineZoom = Math.Clamp(beatmap.Editor.TimelineZoom!.Value, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);
                else
                    timelineZoom = Math.Clamp(editorTimelineZoomDefault?.Value ?? timelineZoom, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);

                if (beatmap.Editor?.WaveformScale.HasValue == true)
                    waveformScale = Math.Clamp(beatmap.Editor.WaveformScale!.Value, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);
                else
                    waveformScale = Math.Clamp(editorWaveformScaleDefault?.Value ?? waveformScale, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);

                beatGridVisible = beatmap.Editor?.BeatGridVisible ?? (editorBeatGridVisibleDefault?.Value ?? true);

                suppressEditorDefaultPersistence = previousPersistenceState;
                updateStatusText();
                trackLength = beatmap.Audio.Duration;
                currentTime = resolvePreferredStartTime(out string? startContextDetail);
                if (timeText != null)
                    timeText.Text = formatTime(currentTime);
                reloadTimeline();
                if (!string.IsNullOrWhiteSpace(startContextDetail))
                    appendStatusDetail(startContextDetail);
                var editorInfo = ensureEditorInfo();
                editorInfo.TimelineZoom = timelineZoom;
                editorInfo.SnapDivisor = snapDivisor;
                editorInfo.WaveformScale = waveformScale;
                editorInfo.BeatGridVisible = beatGridVisible;
                refreshTimelineToolboxState();
                lastSavedSnapshot = serializeBeatmap(beatmap);
                populateInspectorFromBeatmap();

                // Load debug data if available
                string debugPath = Path.ChangeExtension(path, ".debug.json");
                if (File.Exists(debugPath))
                {
                    try
                    {
                        string json = File.ReadAllText(debugPath);
                        timeline?.LoadDebugData(json);
                    }
                    catch (Exception ex)
                    {
                        osu.Framework.Logging.Logger.Log($"Failed to load debug data: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                    }
                }

                // Load audio track
                loadAudioTrackFromBeatmap();
                if (!playbackAvailable)
                    appendStatusDetail(offlinePlaybackMessage);
                updateActionButtons();
                updatePlaybackAvailabilityUI();
            }
            catch (Exception ex)
            {
                setStatusBase(string.Empty);
                setStatusDetail($"Failed to load beatmap: {ex.Message}");
                reloadTimeline();
                updateActionButtons();
                beatmap = null;
                initialBeatmapBpm = null;
                populateInspectorFromBeatmap();
            }
        }

        private void initializeNewProject(ImportedAudioTrack? trackInfo)
        {
            beatmap = new Beatmap
            {
                Metadata =
                {
                    Title = "Untitled",
                    Artist = "Unknown Artist",
                    Creator = Environment.UserName ?? "BeatSight Mapper",
                    BeatmapId = Guid.NewGuid().ToString(),
                    CreatedAt = DateTime.UtcNow,
                    ModifiedAt = DateTime.UtcNow
                },
                Audio =
                {
                    Filename = trackInfo?.RelativeStoragePath ?? string.Empty,
                    Duration = trackInfo?.DurationMilliseconds.HasValue == true
                        ? (int)Math.Round(trackInfo.DurationMilliseconds.Value)
                        : 60000 // Default 1 minute for blank projects
                },
                Editor = new EditorInfo
                {
                    SnapDivisor = 4,
                    VisualLanes = 7,
                    TimelineZoom = editorTimelineZoomDefault?.Value ?? 1.0,
                    WaveformScale = editorWaveformScaleDefault?.Value ?? 1.0,
                    BeatGridVisible = editorBeatGridVisibleDefault?.Value ?? true
                }
            };

            initialBeatmapBpm = beatmap.Timing.Bpm;

            setStatusBase("Editing: Unknown Artist - Untitled");
            setStatusDetail(playbackAvailable ? "Ready to map" : offlinePlaybackMessage);
            hasUnsavedChanges = true;
            undoStack.Clear();
            redoStack.Clear();
            editSnapshotArmed = false;
            lastInspectorSnapshotAtUtc = DateTime.MinValue;
            lastSavedSnapshot = null;
            snapDivisor = 4;
            suppressEditorDefaultPersistence = true;
            applyEditorDefaultsFromConfig();
            suppressEditorDefaultPersistence = false;
            updateStatusText();
            trackLength = beatmap?.Audio.Duration ?? 0;
            currentTime = 0;
            if (timeText != null)
                timeText.Text = formatTime(currentTime);
            reloadTimeline();
            ensureEditorInfo();
            refreshTimelineToolboxState();
            populateInspectorFromBeatmap();
            if (trackInfo != null)
                loadAudioTrackFromStorage(trackInfo.RelativeStoragePath);
            if (!playbackAvailable)
                appendStatusDetail(offlinePlaybackMessage);
            updateActionButtons();
            updatePlaybackAvailabilityUI();
        }

        private void loadAudioTrackFromBeatmap()
        {
            if (beatmap == null || beatmapPath == null)
                return;

            disposeTrack();

            if (string.IsNullOrWhiteSpace(beatmap.Audio.Filename))
            {
                appendStatusDetail("No audio associated with beatmap");
                track = null;
                return;
            }

            string resolvedAudioPath = Path.IsPathRooted(beatmap.Audio.Filename)
                ? beatmap.Audio.Filename
                : Path.Combine(Path.GetDirectoryName(beatmapPath) ?? string.Empty, beatmap.Audio.Filename);

            if (!File.Exists(resolvedAudioPath))
            {
                appendStatusDetail("Audio file missing");
                return;
            }

            try
            {
                string cacheDirectory = host.Storage.GetFullPath("EditorAudio");
                Directory.CreateDirectory(cacheDirectory);

                string cachedName = $"{beatmap.Metadata.BeatmapId}_editor_{Path.GetFileName(resolvedAudioPath)}";
                string cachedPath = Path.Combine(cacheDirectory, cachedName);

                File.Copy(resolvedAudioPath, cachedPath, overwrite: true);

                string relativePath = Path.Combine("EditorAudio", cachedName).Replace(Path.DirectorySeparatorChar, '/');

                loadAudioTrackFromStorage(relativePath);
            }
            catch (Exception ex)
            {
                appendStatusDetail($"Audio load failed: {ex.Message}");
                track = null;
            }
        }

        private void loadAudioTrackFromStorage(string relativePath)
        {
            disposeTrack();

            try
            {
                var store = storageTrackStore ?? audioManager.Tracks;
                var loadedTrack = store.Get(relativePath);

                if (loadedTrack == null)
                    throw new FileNotFoundException($"Audio track '{relativePath}' could not be resolved in storage.");

                track = loadedTrack;
                track.Completed += onTrackCompleted;
                trackLength = track.Length;
                if (currentTime > 0)
                    track.Seek(Math.Clamp(currentTime, 0, trackLength));
                lastTrackTime = track.CurrentTime;

                if (beatmap != null && trackLength > 0)
                    beatmap.Audio.Duration = (int)Math.Round(trackLength);

                reloadTimeline();
                refreshTimelineToolboxState();

                var absolutePath = host.Storage.GetFullPath(relativePath.Replace('/', Path.DirectorySeparatorChar));
                if (!File.Exists(absolutePath))
                    throw new FileNotFoundException($"Audio asset missing at {absolutePath}");

                queueWaveformLoad(absolutePath);
                appendStatusDetail("Audio loaded");
            }
            catch (Exception ex)
            {
                appendStatusDetail($"Audio load failed: {ex.Message}");
                track = null;
            }
        }

        private void disposeTrack()
        {
            if (track != null)
            {
                track.Completed -= onTrackCompleted;
                track.Stop();
                track.Dispose();
                track = null;
            }

            trackLength = 0;
            lastTrackTime = 0;
            waveformLoadCts?.Cancel();
            waveformLoadCts?.Dispose();
            waveformLoadCts = null;
        }

        private void togglePlayback()
        {
            if (isPlaying)
                stopPlayback();
            else
                startPlayback();
        }

        private void startPlayback()
        {
            double effectiveLength = getEffectivePlaybackLength();
            if (effectiveLength > 0 && currentTime > effectiveLength)
                currentTime = effectiveLength;

            bool audioStarted = false;

            if (track != null && playbackAvailable)
            {
                if (currentTime > track.Length)
                {
                    currentTime = 0;
                    track.Seek(0);
                }
                else
                {
                    double target = Math.Clamp(currentTime, 0, track.Length);
                    if (Math.Abs(track.CurrentTime - target) > 2)
                        track.Seek(target);
                }

                track.Start();
                lastTrackTime = track.CurrentTime;
                audioStarted = true;
            }

            playbackPreview?.JumpToTime(currentTime);
            isPlaying = true;
            updatePlayPauseButtonLabel();
            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);

            if (audioStarted)
                appendStatusDetail("Playing");
            else if (playbackAvailable)
                appendStatusDetail("Playing (no audio)");
            else
                appendStatusDetail("Playing timeline (audio unavailable)");
        }

        private void stopPlayback(bool silent = false)
        {
            if (track != null)
            {
                track.Stop();
                lastTrackTime = track.CurrentTime;
            }

            isPlaying = false;
            updatePlayPauseButtonLabel();

            if (!silent)
                appendStatusDetail("Paused");

            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);
        }

        private void rewindToStart()
        {
            stopPlayback(silent: true);
            seekToTime(0);
            appendStatusDetail("Rewound to start");
        }

        private void updatePlayPauseButtonLabel()
        {
            if (playPauseButton == null)
                return;

            string label = isPlaying ? "Pause" : "Play";
            string tooltip;

            if (playbackAvailable)
            {
                tooltip = isPlaying
                    ? "Pause the preview (Shift+Space rewinds to start)."
                    : "Play the preview (Shift+Space rewinds to start).";
            }
            else
            {
                if (!isPlaying)
                    label = "Play Silent";

                tooltip = isPlaying
                    ? "Pause timeline playback (audio unavailable)."
                    : "Play timeline playback (audio unavailable).";
            }

            playPauseButton.UpdateState(true, tooltip);
            playPauseButton.SetLabel(label);
        }

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

        private void applyTimelineToolboxDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            float sectionTitleFont = blend(12.4f, 11.1f, compactBlend) + ultraWideRelax * 0.3f;
            float sectionPaddingH = blend(11f, 9f, compactBlend) + ultraWideRelax * 1.2f;
            float sectionPaddingV = blend(8f, 7f, compactBlend) + ultraWideRelax * 0.45f;
            float sectionVerticalSpacing = blend(6f, 5f, compactBlend) + ultraWideRelax * 0.55f;
            float sectionLabelSpacing = blend(8f, 6f, compactBlend) + ultraWideRelax * 1.05f;
            float sliderHeight = blend(30f, 26f, compactBlend);
            float miniButtonHeight = blend(32f, 28f, compactBlend);
            float miniButtonFont = blend(11.9f, 10.8f, compactBlend) + ultraWideRelax * 0.2f;

            if (timelineToolboxContainer != null)
            {
                timelineToolboxContainer.Padding = new MarginPadding
                {
                    Horizontal = blend(13f, 10f, compactBlend),
                    Vertical = blend(10f, 8f, compactBlend)
                };
            }

            if (timelineToolboxContentFlow != null)
                timelineToolboxContentFlow.Spacing = new Vector2(blend(12f, 9f, compactBlend) + ultraWideRelax * 1.3f, 0);

            if (timelineZoomSliderContainer != null)
            {
                timelineZoomSliderContainer.Width = blend(170f, 146f, compactBlend);
                timelineZoomSliderContainer.Height = sliderHeight;
            }

            if (timelineWaveformSliderContainer != null)
            {
                timelineWaveformSliderContainer.Width = blend(154f, 132f, compactBlend);
                timelineWaveformSliderContainer.Height = sliderHeight;
            }

            foreach (var body in timelineSectionBodies)
            {
                body.Spacing = new Vector2(0, sectionVerticalSpacing);
                body.Padding = new MarginPadding { Horizontal = sectionPaddingH, Vertical = sectionPaddingV };
            }

            foreach (var titleText in timelineSectionTitleTexts)
                titleText.Font = BeatSightFont.Caption(sectionTitleFont);

            foreach (var row in timelineSectionControlRows)
                row.Spacing = new Vector2(sectionLabelSpacing, 0);

            foreach (var button in timelineMiniButtons)
            {
                button.Height = miniButtonHeight;
                button.CornerRadius = blend(8f, 7f, compactBlend);
            }
            foreach (var label in timelineMiniButtonTexts)
                label.Font = BeatSightFont.Button(miniButtonFont);

            if (timelineZoomValueText != null)
                timelineZoomValueText.Font = BeatSightFont.Caption(blend(11.8f, 10.8f, compactBlend));

            if (waveformScaleValueText != null)
                waveformScaleValueText.Font = BeatSightFont.Caption(blend(11.8f, 10.8f, compactBlend));

            if (snapDivisorText != null)
                snapDivisorText.Font = BeatSightFont.Title(blend(12.8f, 11.6f, compactBlend));

            if (previewContentContainer != null)
            {
                previewContentContainer.Padding = new MarginPadding
                {
                    Horizontal = blend(10f, 8f, compactBlend),
                    Vertical = blend(8f, 6f, compactBlend)
                };
            }
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
