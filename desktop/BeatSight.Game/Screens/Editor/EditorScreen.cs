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
using BeatSight.Game.Screens.Playback;
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
        // Final decomposition map (phase-28 freeze, no behavior changes):
        // - EditorScreen.cs: shared state/constants + cross-partial wiring.
        // - EditorScreen.Initialization/Header/EditorLayout/FooterHistory: primary composition and layout.
        // - EditorScreen.Timeline*/Inspector*/Selection*/Notation*: editing interaction surfaces.
        // - EditorScreen.PlaybackTransport/WaveformTimeline/SaveOperations/SnapshotHistory: persistence + playback/data flows.
        // - EditorScreen.InputHotkeys/RuntimeLoop/Lifecycle/Responsive*: runtime lifecycle and responsiveness.

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
        private Bindable<double> uiScaleSetting = null!;
        private Bindable<double> masterVolumeSetting = null!;
        private Bindable<double> musicVolumeSetting = null!;
        private Bindable<bool> masterVolumeEnabledSetting = null!;
        private Bindable<bool> musicVolumeEnabledSetting = null!;
        private Bindable<double> playbackZoomSetting = null!;
        private Bindable<double> noteWidthSetting = null!;

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
        private bool historyPanelVisible;
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
        private FillFlowContainer headerLeadFlow = null!;
        private float headerContentSpacingY = 4f;
        private Container headerTimeBadgeContainer = null!;
        private SpriteText headerTimeCaptionText = null!;
        private FillFlowContainer headerStatusColumn = null!;
        private Container previewContentContainer = null!;
        private Container previewCellContainer = null!;
        private Container previewSurfaceContainer = null!;
        private Container timelineToolboxContainer = null!;
        private Container timelineToolboxHostContainer = null!;
        private FillFlowContainer timelineToolboxContentFlow = null!;
        private EditorButton timelineToolboxToggleButton = null!;
        private EditorVerticalSplitter timelinePreviewSplitter = null!;
        private Container timelineZoomSliderContainer = null!;
        private Container timelineWaveformSliderContainer = null!;
        private readonly List<BasicButton> timelineMiniButtons = new();
        private readonly List<SpriteText> timelineMiniButtonTexts = new();
        private readonly List<SpriteText> timelineSectionTitleTexts = new();
        private readonly List<FillFlowContainer> timelineSectionControlRows = new();
        private readonly List<FillFlowContainer> timelineSectionBodies = new();
        private BasicButton timelineFirstNoteButton = null!;
        private BasicButton timelineLastNoteButton = null!;
        private BasicButton timelineTimingButton = null!;
        private BasicButton timelineSnapAudioButton = null!;
        private BasicButton timelineRegenerateButton = null!;
        private BasicButton timelineLanePrevButton = null!;
        private BasicButton timelineLaneNextButton = null!;
        private BasicButton timelineLaneAddButton = null!;
        private BasicButton timelineLaneRemoveButton = null!;
        private BasicButton timelineLaneMoveLeftButton = null!;
        private BasicButton timelineLaneMoveRightButton = null!;
        private BasicButton timelineLaneApplyButton = null!;
        private SpriteText timelineFirstNoteButtonText = null!;
        private SpriteText timelineLastNoteButtonText = null!;
        private SpriteText timelineSnapAudioButtonText = null!;
        private SpriteText timelineRegenerateButtonText = null!;
        private SpriteText timelineLaneSelectionText = null!;
        private BeatSightTextBox timelineLaneNameInput = null!;
        private BeatSightTextBox timelineLaneShortNameInput = null!;
        private BeatSightTextBox timelineLaneColorInput = null!;
        private int timelineLaneEditIndex;
        private bool suppressLaneEditorFieldSync;
        private FillFlowContainer inspectorSectionsFlow = null!;
        private Container scrubPerfOverlayContainer = null!;
        private SpriteText scrubPerfOverlayText = null!;
        private Container footerRootContainer = null!;
        private Container footerInnerContainer = null!;
        private FillFlowContainer footerTipFlow = null!;
        private Container footerTipsContainer = null!;
        private bool footerTipsCollapsed = true;
        private GridContainer footerSeekRow = null!;
        private ScrubbableSliderBar footerSeekSlider = null!;
        private SpriteText footerSeekCurrentText = null!;
        private SpriteText footerSeekTotalText = null!;
        private readonly BindableDouble footerSeekProgress = new BindableDouble
        {
            MinValue = 0,
            MaxValue = 1,
            Precision = 0.0001,
            Default = 0
        };
        private bool footerSeekScrubbing;
        private bool suppressFooterSeekSync;
        private bool previewRefreshQueued;
        private int previewRefreshEpoch;
        private bool timelineDragInProgress;
        private int suppressTimelineSelectionSeekCount;
        private bool deferredTimelineUiRefreshPending;
        private double? pendingSeekTimeMs;
        private bool pendingSeekEnsureVisible;
        private bool pendingSeekSyncTrack;
        private bool pendingSeekSyncPreview;
        private SeekInputSource pendingSeekSource;
        private bool seekDispatchScheduled;
        private bool scrubTelemetryActive;
        private SeekInputSource scrubTelemetrySource;
        private double scrubTelemetrySessionStartAt = double.NegativeInfinity;
        private double scrubTelemetryLastInputAt = double.NegativeInfinity;
        private int scrubTelemetryQueuedSeekCount;
        private int scrubTelemetryFlushedSeekCount;
        private double scrubTelemetryInputDeltaTotal;
        private double scrubTelemetryFlushTotalMs;
        private double scrubTelemetryFlushMaxMs;
        private int scrubTelemetryFrameSampleCount;
        private double scrubTelemetryFrameTotalMs;
        private double scrubTelemetryFrameMaxMs;
        private double scrubFrameAverageMs = scrubFrameTargetMs;
        private double wheelScrubActiveUntil = double.NegativeInfinity;
        private bool scrubPerfOverlayVisible;
        private double lastScrubPerfOverlayUpdateAt = double.NegativeInfinity;
        private SeekInputSource lastScrubSummarySource = SeekInputSource.Programmatic;
        private double lastScrubSummaryRecordedAt = double.NegativeInfinity;
        private double lastScrubSummaryDurationMs;
        private int lastScrubSummaryQueued;
        private int lastScrubSummaryFlushed;
        private double lastScrubSummaryAvgFrameMs;
        private double lastScrubSummaryMaxFrameMs;
        private double lastScrubSummaryAvgFlushMs;
        private double lastScrubSummaryMaxFlushMs;
        private double lastScrubSummaryAvgInputDelta;
        private double footerSmoothedScrubProgress;
        private double footerLastQueuedScrubProgress = double.NaN;
        private bool footerSmoothedScrubInitialized;
        private EditorButton inspectorToggleButton = null!;
        private float lastInspectorWidth = -1;
        private float lastTimelineSurfaceHeight = -1;
        private float lastTimelineToolboxHeight = -1;
        private float lastFooterHeight = -1;
        private float lastStackedInspectorHeight = -1;
        private float lastPanelGap = -1;
        private float lastCompactBlend = -1f;
        private bool lastTimelineToolboxCollapsedState;
        // Inspector declaration cluster extracted to EditorScreen.InspectorState.cs.

        private bool isPlaying;
        private double currentTime;
        private double lastTimelineSyncedTime = double.NaN;
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
        private double lastTimelineSnapBpm = double.NaN;
        private double lastTimelineSnapOrigin = double.NaN;
        private int lastTimelineBeatsPerMeasure = 4;
        private int lastTimelineBeatUnitDenominator = 4;
        private int lastTimelineSnapDivisor = -1;

        private BeatSightSliderBar timelineZoomSlider = null!;
        private SpriteText timelineZoomValueText = null!;
        private BeatSightSliderBar waveformScaleSlider = null!;
        private SpriteText waveformScaleValueText = null!;
        private BeatSightSliderBar playbackRateSlider = null!;
        private SpriteText playbackRateValueText = null!;
        private BeatSightSliderBar playbackZoomSlider = null!;
        private SpriteText playbackZoomValueText = null!;
        private BeatSightSliderBar noteWidthSlider = null!;
        private SpriteText noteWidthValueText = null!;
        private SpriteText snapDivisorText = null!;
        private BeatSightCheckbox beatGridCheckbox = null!;
        private BeatSightCheckbox timelineLinkZoomCheckbox = null!;
        private Container timelinePlaybackRateSliderContainer = null!;
        private Container timelinePlaybackZoomSliderContainer = null!;
        private Container timelineNoteWidthSliderContainer = null!;
        private Container timingSetupOverlay = null!;
        private Container timingSetupDialogContainer = null!;
        private BeatSightTextBox timingSetupBpmInput = null!;
        private BeatSightTextBox timingSetupOffsetInput = null!;
        private BeatSightCheckbox timingMoveNotesCheckbox = null!;
        private BeatSightCheckbox timingResnapNotesCheckbox = null!;
        private SpriteText timingSetupHintText = null!;
        private readonly BindableBool timingMoveNotes = new BindableBool(true);
        private readonly BindableBool timingResnapNotes = new BindableBool(true);

        private bool suppressTimelineZoomSync;
        private bool suppressWaveformScaleSync;
        private bool suppressPlaybackRateSync;
        private bool suppressPlaybackZoomSync;
        private bool suppressNoteWidthSync;
        private bool suppressBeatGridSync;
        private bool suppressTimelineZoomLinkSync;
        private bool suppressEditorDefaultPersistence;
        private bool suppressLinkedZoomPropagation;
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
        private bool playbackZoomPointerAdjusting;
        private bool playbackZoomInteractionActive;
        private bool playbackZoomInteractionDirty;
        private double lastPlaybackZoomPreviewAppliedAt = double.NegativeInfinity;
        private double? pendingPlaybackZoomPreview;
        private bool linkTimelineAndPlaybackZoom;
        private bool timelineToolboxCollapsed;
        private int timelineToolboxAnimationVersion;
        private bool timelineToolboxAnimationInProgress;
        private float? timelineTopHeightOverride;

        private Bindable<double> editorTimelineZoomDefault = null!;
        private Bindable<double> editorWaveformScaleDefault = null!;
        private Bindable<bool> editorBeatGridVisibleDefault = null!;
        private Bindable<int> editorSnapDivisorDefault = null!;
        private Bindable<bool> editorTimelinePlaybackZoomLinkedDefault = null!;
        private Bindable<double> editorTimelineSplitRatioExpanded = null!;
        private Bindable<double> editorTimelineSplitRatioCollapsed = null!;

        private bool suppressInspectorFieldSync;
        private HitObject? selectedHitObject;
        private readonly List<HitObject> clipboardNotes = new();
        private double? initialBeatmapBpm;
        private DateTime lastInspectorSnapshotAtUtc = DateTime.MinValue;
        private bool inspectorTransitionActive;

        private const int maxUndoSteps = 50;
        private static readonly bool showFooterShortcutHints = false;
        private const int historyPreviewCount = 3;
        private const double timelineZoomPreviewMinIntervalMs = 12;
        private const double waveformScalePreviewMinIntervalMs = 24;
        private const double playbackZoomPreviewMinIntervalMs = 12;
        private const double previewRefreshDebounceMs = 28;
        private const double previewRefreshDragDebounceMs = 96;
        private const double editorPreviewVisibleMeasures = 2.0;
        private const double editorPlaybackZoomMin = EditorTimeline.MinZoom;
        private const double editorPlaybackZoomMax = EditorTimeline.MaxZoom;
        private const double scrubTelemetryIdleTimeoutMs = 220;
        private const double scrubPerfOverlayRefreshMs = 84;
        private const double scrubFrameTargetMs = 16.7;
        private const double scrubFramePressureFloor = 0.58;
        private const double wheelScrubHoldMs = 160;
        private const double wheelScrubCurveExponent = 1.08;
        private const double wheelScrubBaseMultiplier = 1.20;
        private const double wheelScrubShiftMultiplier = 1.84;
        private const double wheelScrubMagnitudeCap = 3.5;
        private const double seekBarSmoothingBase = 0.30;
        private const double seekBarSmoothingFloor = 0.16;
        private const double seekBarSmoothingCeiling = 0.62;
        private const double seekBarQueueProgressThreshold = 0.0005;
        private const double minPlaybackRate = 0.25;
        private const double maxPlaybackRate = 1.5;
        private const float inspectorButtonColumnSpacing = 7;
        private const float inspectorButtonRowSpacing = 6;
        private const float timelineToolboxRowHeight = 104f;
        private const float timelineSurfaceHeight = 278f;
        private const float timelinePreviewSplitterHeight = 10f;
        private const float minimumPreviewWorkspaceHeight = 188f;
        private const float minimumTimelineCoreHeight = 146f;
        private const double defaultTimelineSplitRatioExpanded = 0.18;
        private const double defaultTimelineSplitRatioCollapsed = 0.02;
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
        private double playbackRate = 1.0;

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

        private enum SeekInputSource
        {
            Programmatic = 0,
            Wheel,
            SeekBar,
            Timeline
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

        // Inspector composition methods extracted to EditorScreen.InspectorComposition.cs.

        // EditorSnapshot class extracted to EditorCommandManager.cs

    }
}
