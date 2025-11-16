using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Gameplay;
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
    internal static class EditorColours
    {
        public static readonly Color4 ScreenBackground = UITheme.Background;
        public static readonly Color4 HeaderBackground = UITheme.Surface;
        public static readonly Color4 ControlsBackground = UITheme.SurfaceAlt;
        public static readonly Color4 TimelineBackground = UITheme.Surface;
        public static readonly Color4 TimelineToolbarBackground = UITheme.SurfaceAlt;
        public static readonly Color4 PreviewBackground = UITheme.BackgroundLayer;
        public static readonly Color4 HistoryBackground = UITheme.SurfaceAlt.Opacity(0.8f);
        public static readonly Color4 Divider = UITheme.Divider;

        public static Color4 AccentPlay => UITheme.AccentSecondary;
        public static Color4 AccentSave => UITheme.AccentPrimary;
        public static Color4 AccentUndo => UITheme.SurfaceAlt;
        public static Color4 AccentRedo => UITheme.SurfaceAlt;

        public static Color4 Warning => UITheme.AccentWarning;

        public static Color4 TextPrimary => UITheme.TextPrimary;
        public static Color4 TextSecondary => UITheme.TextSecondary;
        public static Color4 TextMuted => UITheme.TextMuted;

        public static Color4 Lighten(Color4 colour, float factor) => UITheme.Emphasise(colour, factor);

        public static Color4 WithAlpha(Color4 colour, float alpha) => new Color4(colour.R, colour.G, colour.B, colour.A * alpha);
    }

    public partial class EditorScreen : Screen
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

        private EditorTimeline timeline = null!;
        private GameplayPreview gameplayPreview = null!;
        private PreviewToggleButton previewToggle = null!;
        private SpriteText statusText = null!;
        private SpriteText timeText = null!;
        private SpriteText actionHintText = null!;
        private SpriteText playbackStatusText = null!;
        private SpriteText undoHeaderText = null!;
        private SpriteText redoHeaderText = null!;
        private Container historyPanel = null!;
        private FillFlowContainer undoHistoryFlow = null!;
        private FillFlowContainer redoHistoryFlow = null!;
        private EditorButton playPauseButton = null!;
        private EditorButton saveButton = null!;
        private EditorButton undoButton = null!;
        private EditorButton redoButton = null!;
        private BackButton backButton = null!;

        private bool isPlaying;
        private double currentTime;
        private double trackLength;
        private WaveformData? waveformData;
        private CancellationTokenSource? waveformLoadCts;
        private string statusBaseText = "BeatSight Editor";
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

        private BasicSliderBar<double> timelineZoomSlider = null!;
        private SpriteText timelineZoomValueText = null!;
        private BasicSliderBar<double> waveformScaleSlider = null!;
        private SpriteText waveformScaleValueText = null!;
        private SpriteText snapDivisorText = null!;
        private BasicCheckbox beatGridCheckbox = null!;

        private bool suppressTimelineZoomSync;
        private bool suppressWaveformScaleSync;
        private bool suppressBeatGridSync;
        private bool suppressEditorDefaultPersistence;

        private Bindable<double> editorTimelineZoomDefault = null!;
        private Bindable<double> editorWaveformScaleDefault = null!;
        private Bindable<bool> editorBeatGridVisibleDefault = null!;

        private const int maxUndoSteps = 50;
        private const int historyPreviewCount = 5;
        private static readonly int[] allowedSnapDivisors = { 1, 2, 3, 4, 6, 8, 12, 16, 24, 32 };
        private const string offlinePlaybackMessage = "Audio preview disabled — offline decode only.";

        private enum EditorPreviewMode
        {
            Playfield2D,
            Playfield3D
        }

        [Resolved]
        private AudioManager audioManager { get; set; } = null!;

        [Resolved]
        private GameHost host { get; set; } = null!;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

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

        private void updateStatusText()
        {
            if (statusText == null)
                return;

            string? detail = statusDetailText;

            if (hasUnsavedChanges)
                detail = string.IsNullOrWhiteSpace(detail) ? "Unsaved changes" : $"{detail}, Unsaved changes";

            statusText.Text = string.IsNullOrWhiteSpace(detail)
                ? statusBaseText
                : $"{statusBaseText} • {detail}";
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
                previewToggle.Enabled.Value = true;
                previewToggle.FadeTo(playbackAvailable ? 1f : 0.85f, 150);
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
                            : "No changes to save.";

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
            defaultHintText = !canSave ? saveTooltip : !canUndo ? undoTooltip : !canRedo ? redoTooltip : null;

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

            // Initialize preview mode - default to 3D playfield
            previewMode = new Bindable<EditorPreviewMode>(EditorPreviewMode.Playfield3D);

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

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = EditorColours.ScreenBackground
                },
                new GridContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    RowDimensions = new[]
                    {
                        new Dimension(GridSizeMode.Absolute, 60),
                        new Dimension(GridSizeMode.Absolute, 120),
                        new Dimension(),
                        new Dimension(GridSizeMode.Absolute, 80)
                    },
                    Content = new[]
                    {
                        new Drawable[] { createHeader() },
                        new Drawable[] { createControls() },
                        new Drawable[] { createEditor() },
                        new Drawable[] { createFooter() }
                    }
                },
                backButton
            };

            if (!string.IsNullOrEmpty(beatmapPath))
            {
                loadBeatmap(beatmapPath);
            }
            else if (importedAudio != null)
            {
                initializeNewProject(importedAudio);
            }
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Ensure preview is synchronized after everything is loaded
            if (beatmap != null && gameplayPreview != null)
            {
                gameplayPreview.SetBeatmap(beatmap);
            }

            // Make sure the correct preview mode is visible
            onPreviewModeChanged(new ValueChangedEvent<EditorPreviewMode>(previewMode.Value, previewMode.Value));

            updatePlaybackAvailabilityUI();
        }

        private Drawable createHeader()
        {
            statusText = new SpriteText
            {
                Text = "BeatSight Editor",
                Font = new FontUsage(size: 28, weight: "Bold"),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            setStatusBase("BeatSight Editor");
            setStatusDetail(null);

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 30 },
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.HeaderBackground
                    },
                    statusText,
                    new SpriteText
                    {
                        Text = "Esc — back to menu",
                        Font = new FontUsage(size: 18),
                        Colour = EditorColours.TextSecondary,
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight
                    }
                }
            };
        }

        private Drawable createControls()
        {
            timeText = new SpriteText
            {
                Text = formatTime(0),
                Font = new FontUsage(size: 32, weight: "Medium"),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre
            };

            playPauseButton = new EditorButton("▶ Play", EditorColours.AccentPlay)
            {
                Size = new Vector2(120, 40),
                Action = togglePlayback
            };
            playPauseButton.HoverHintChanged += setHoverHint;
            playPauseButton.UpdateState(true, "Play or pause the preview. Shift+Space rewinds to start.");

            saveButton = new EditorButton("Save", EditorColours.AccentSave)
            {
                Size = new Vector2(120, 40),
                Action = saveBeatmap
            };

            undoButton = new EditorButton("Undo", EditorColours.AccentUndo)
            {
                Size = new Vector2(120, 40),
                Action = undoLastEdit
            };

            redoButton = new EditorButton("Redo", EditorColours.AccentRedo)
            {
                Size = new Vector2(120, 40),
                Action = redoLastEdit
            };

            saveButton.HoverHintChanged += setHoverHint;
            undoButton.HoverHintChanged += setHoverHint;
            redoButton.HoverHintChanged += setHoverHint;
            previewToggle = new PreviewToggleButton(previewMode)
            {
                Size = new Vector2(120, 40)
            };
            previewToggle.HoverHintChanged += setHoverHint;

            var controls = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 30, Vertical = 15 },
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.ControlsBackground
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Spacing = new Vector2(0, 10),
                        Children = new Drawable[]
                        {
                            timeText,
                            new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Horizontal,
                                Spacing = new Vector2(10, 0),
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre,
                                Children = new Drawable[]
                                {
                                    playPauseButton,
                                    saveButton,
                                    undoButton,
                                    redoButton,
                                    previewToggle
                                }
                            },
                            actionHintText = new SpriteText
                            {
                                Font = new FontUsage(size: 14),
                                Colour = EditorColours.TextSecondary,
                                Alpha = 0,
                                Text = string.Empty,
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre,
                                MaxWidth = 700,
                                AllowMultiline = true
                            },
                            playbackStatusText = new SpriteText
                            {
                                Font = new FontUsage(size: 14),
                                Colour = EditorColours.Warning,
                                Alpha = 0,
                                Text = string.Empty,
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre,
                                MaxWidth = 700,
                                AllowMultiline = true
                            },
                            historyPanel = new Container
                            {
                                AutoSizeAxes = Axes.Both,
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre,
                                Child = new Container
                                {
                                    AutoSizeAxes = Axes.Both,
                                    CornerRadius = 6,
                                    Masking = true,
                                    Children = new Drawable[]
                                    {
                                        new Box
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Colour = EditorColours.HistoryBackground
                                        },
                                        new FillFlowContainer
                                        {
                                            AutoSizeAxes = Axes.Both,
                                            Direction = FillDirection.Horizontal,
                                            Spacing = new Vector2(20, 0),
                                            Padding = new MarginPadding { Horizontal = 14, Vertical = 10 },
                                            Children = new Drawable[]
                                            {
                                                createHistoryColumn("Undo", out undoHeaderText, out undoHistoryFlow),
                                                createHistoryColumn("Redo", out redoHeaderText, out redoHistoryFlow)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            };

            updateActionButtons();
            updatePlaybackAvailabilityUI();
            return controls;
        }

        private Drawable createEditor()
        {
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

            gameplayPreview = new GameplayPreview(() => currentTime)
            {
                RelativeSizeAxes = Axes.Both
            };

            var timelineSection = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 30, Vertical = 10 },
                Child = new GridContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    RowDimensions = new[]
                    {
                        new Dimension(GridSizeMode.Absolute, 70),
                        new Dimension()
                    },
                    Content = new[]
                    {
                        new Drawable[] { createTimelineToolbox() },
                        new Drawable[] { timeline }
                    }
                }
            };

            return new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, 220),
                    new Dimension()
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        timelineSection
                    },
                    new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Padding = new MarginPadding { Horizontal = 40, Vertical = 20 },
                            Child = gameplayPreview
                        }
                    }
                }
            };
        }

        private Drawable createTimelineToolbox()
        {
            timelineZoomValueText = new SpriteText
            {
                Text = $"{timelineZoom:0.00}x",
                Font = new FontUsage(size: 14, weight: "Bold"),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            timelineZoomSlider = new BasicSliderBar<double>
            {
                RelativeSizeAxes = Axes.Both
            };
            var zoomBindable = new BindableDouble(timelineZoom)
            {
                MinValue = EditorTimeline.MinZoom,
                MaxValue = EditorTimeline.MaxZoom
            };
            timelineZoomSlider.Current = zoomBindable;
            timelineZoomSlider.Current.ValueChanged += e =>
            {
                if (suppressTimelineZoomSync)
                    return;

                applyTimelineZoom(e.NewValue);
            };

            var zoomSliderContainer = new Container
            {
                Width = 260,
                Height = 28,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Child = timelineZoomSlider
            };

            waveformScaleValueText = new SpriteText
            {
                Text = $"{waveformScale:0.00}x",
                Font = new FontUsage(size: 14, weight: "Bold"),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            waveformScaleSlider = new BasicSliderBar<double>
            {
                RelativeSizeAxes = Axes.Both
            };
            var waveformBindable = new BindableDouble(waveformScale)
            {
                MinValue = EditorTimeline.MinWaveformScale,
                MaxValue = EditorTimeline.MaxWaveformScale
            };
            waveformScaleSlider.Current = waveformBindable;
            waveformScaleSlider.Current.ValueChanged += e =>
            {
                if (suppressWaveformScaleSync)
                    return;

                setWaveformScale(e.NewValue);
            };

            var waveformSliderContainer = new Container
            {
                Width = 200,
                Height = 28,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Child = waveformScaleSlider
            };

            snapDivisorText = new SpriteText
            {
                Text = $"1/{snapDivisor}",
                Font = new FontUsage(size: 14, weight: "Bold"),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            beatGridCheckbox = new BasicCheckbox
            {
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                LabelText = "Beat grid"
            };
            beatGridCheckbox.Current.Value = beatGridVisible;
            beatGridCheckbox.Current.ValueChanged += e =>
            {
                if (suppressBeatGridSync)
                    return;

                setBeatGridVisibility(e.NewValue);
            };

            var zoomSection = createTimelineSection("Timeline Zoom",
                createTimelineMiniButton("−", () => adjustTimelineZoom(false)),
                zoomSliderContainer,
                createTimelineMiniButton("+", () => adjustTimelineZoom(true)),
                createTimelineMiniButton("Reset", () => applyTimelineZoom(1.0), 58),
                timelineZoomValueText);

            var waveformSection = createTimelineSection("Waveform",
                waveformSliderContainer,
                createTimelineMiniButton("Reset", () => setWaveformScale(1.0), 58),
                waveformScaleValueText);

            var snapSection = createTimelineSection("Snap",
                createTimelineMiniButton("−", () => adjustSnapDivisor(false)),
                snapDivisorText,
                createTimelineMiniButton("+", () => adjustSnapDivisor(true)));

            var gridSection = createTimelineSection("Overlay", beatGridCheckbox);

            var contentFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(30, 0),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Children = new Drawable[]
                {
                    zoomSection,
                    waveformSection,
                    snapSection,
                    gridSection
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
                Padding = new MarginPadding { Horizontal = 18, Vertical = 12 },
                Masking = true,
                CornerRadius = 10,
                Children = new Drawable[]
                {
                    background,
                    contentFlow
                }
            };

            refreshTimelineToolboxState();
            return container;
        }

        private Drawable createTimelineSection(string title, params Drawable[] controls)
        {
            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6, 6),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = title,
                        Font = new FontUsage(size: 13, weight: "Bold"),
                        Colour = EditorColours.TextSecondary
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(8, 0),
                        Children = controls
                    }
                }
            };
        }

        private BasicButton createTimelineMiniButton(string text, Action action, float width = 36)
        {
            var button = new BasicButton
            {
                Size = new Vector2(width, 28),
                BackgroundColour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.08f),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Masking = true,
                CornerRadius = 6,
                Action = action
            };

            button.Add(new SpriteText
            {
                Text = text,
                Font = new FontUsage(size: text.Length > 2 ? 13 : 16, weight: "Bold"),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            });

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

        private void applyTimelineZoom(double zoom)
        {
            double clamped = Math.Clamp(zoom, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);
            if (Math.Abs(clamped - timelineZoom) < 0.0001)
            {
                syncTimelineZoomDisplay();
                return;
            }

            prepareUndoSnapshot();

            timelineZoom = clamped;
            timeline?.SetZoom(timelineZoom);

            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.TimelineZoom = timelineZoom;
            }

            markUnsaved();
            refreshUnsavedState();
            syncTimelineZoomDisplay();
            persistEditorDefaults();
        }

        private void updateWaveformScaleDisplay()
        {
            if (waveformScaleValueText != null)
                waveformScaleValueText.Text = $"{waveformScale:0.00}x";

            if (waveformScaleSlider != null)
            {
                suppressWaveformScaleSync = true;
                waveformScaleSlider.Current.Value = waveformScale;
                suppressWaveformScaleSync = false;
            }
        }

        private void setWaveformScale(double scale)
        {
            double clamped = Math.Clamp(scale, EditorTimeline.MinWaveformScale, EditorTimeline.MaxWaveformScale);
            if (Math.Abs(clamped - waveformScale) < 0.0001)
            {
                updateWaveformScaleDisplay();
                return;
            }

            prepareUndoSnapshot();

            waveformScale = clamped;
            timeline?.SetWaveformScale(waveformScale);

            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.WaveformScale = waveformScale;
            }

            markUnsaved();
            refreshUnsavedState();
            updateWaveformScaleDisplay();
            persistEditorDefaults();
        }

        private void adjustWaveformScale(bool increase)
            => setWaveformScale(waveformScale + (increase ? 0.1 : -0.1));

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

            prepareUndoSnapshot();

            snapDivisor = adjusted;
            timeline?.SetSnap(snapDivisor, beatmap?.Timing.Bpm ?? 120);

            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.SnapDivisor = snapDivisor;
            }

            markUnsaved();
            refreshUnsavedState();
            syncSnapControl();
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

            prepareUndoSnapshot();

            beatGridVisible = visible;
            timeline?.SetBeatGridVisible(beatGridVisible);

            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.BeatGridVisible = beatGridVisible;
            }

            markUnsaved();
            refreshUnsavedState();
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
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 30 },
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.HeaderBackground
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Spacing = new Vector2(30, 0),
                        Children = new Drawable[]
                        {
                            createTip("Space", "Play/Pause"),
                            createTip("Shift+Space", "Rewind to start"),
                            createTip("←/→", "Seek"),
                            createTip("Ctrl +/-", "Zoom timeline"),
                            createTip("Ctrl+Alt +/-", "Scale waveform"),
                            createTip("[ / ]", "Change snap"),
                            createTip("G", "Toggle beat grid"),
                            createTip("Ctrl+S", "Save"),
                            createTip("Ctrl+Z", "Undo"),
                            createTip("Ctrl+Y / Ctrl+Shift+Z", "Redo")
                        }
                    }
                }
            };
        }

        private Drawable createTip(string key, string action)
        {
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
                        CornerRadius = 4,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = EditorColours.ControlsBackground
                            },
                            new SpriteText
                            {
                                Text = key,
                                Font = new FontUsage(size: 16, weight: "Bold"),
                                Colour = EditorColours.TextPrimary,
                                Margin = new MarginPadding { Horizontal = 8, Vertical = 4 }
                            }
                        }
                    },
                    new SpriteText
                    {
                        Text = action,
                        Font = new FontUsage(size: 16),
                        Colour = EditorColours.TextSecondary,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    }
                }
            };
        }

        private Drawable createHistoryColumn(string title, out SpriteText headerText, out FillFlowContainer listFlow)
        {
            headerText = new SpriteText
            {
                Text = title,
                Font = new FontUsage(size: 15, weight: "Bold"),
                Colour = EditorColours.TextPrimary
            };

            listFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(2)
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
            historyPanel.Alpha = anyEntries ? 1f : 0.3f;
        }

        private void updateHistoryColumn(IReadOnlyList<EditorSnapshot> stack, SpriteText? header, FillFlowContainer listFlow, string title)
        {
            if (header != null)
                header.Text = stack.Count > 0 ? $"{title} ({stack.Count})" : $"{title} (empty)";

            listFlow.Clear();

            if (stack.Count == 0)
            {
                listFlow.Add(createHistoryPlaceholder());
                return;
            }

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

            string details = $"{formatTime(snapshot.CurrentTime)} • Snap {snapValue} • Zoom {zoomValue:0.00}";

            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(2, 0),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = title,
                        Font = new FontUsage(size: emphasise ? 13 : 12, weight: emphasise ? "Bold" : "Medium"),
                        Colour = emphasise ? EditorColours.TextPrimary : EditorColours.TextSecondary
                    },
                    new SpriteText
                    {
                        Text = details,
                        Font = new FontUsage(size: 11),
                        Colour = EditorColours.TextMuted
                    }
                }
            };
        }

        private Drawable createHistoryPlaceholder()
        {
            return new SpriteText
            {
                Text = "No entries yet",
                Font = new FontUsage(size: 11),
                Colour = EditorColours.TextMuted
            };
        }

        private void onTimelineSeekRequested(double timeMs)
        {
            double target = Math.Clamp(timeMs, 0, trackLength > 0 ? trackLength : Math.Max(0, timeMs));
            currentTime = target;
            track?.Seek(target);
            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);
            if (isPlaying && track != null && !track.IsRunning)
                track.Start();
        }

        private void onTimelineNoteSelected(HitObject hit)
        {
            setStatusDetail($"Selected {hit.Component} @ {formatTime(hit.Time)}");
        }

        private void onTimelineNoteChanged(HitObject hit)
        {
            if (beatmap == null)
                return;

            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            gameplayPreview?.RefreshBeatmap();
            markUnsaved();
            refreshUnsavedState();
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

                case EditorPreviewMode.Playfield3D:
                default:
                    laneViewModeBindable.Value = LaneViewMode.ThreeDimensional;
                    setStatusDetail("3D view");
                    break;
            }
        }

        private void onLaneViewModeChanged(ValueChangedEvent<LaneViewMode> change)
        {
            if (gameplayPreview != null)
            {
                Schedule(() => gameplayPreview.RefreshBeatmap());
            }
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

            refreshUnsavedState();
            editSnapshotArmed = false;
            refreshTimelineToolboxState();

            suppressEditorDefaultPersistence = originalPersistenceState;
            persistEditorDefaults();
        }

        private void refreshUnsavedState()
        {
            if (beatmap == null)
            {
                hasUnsavedChanges = false;
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
                refreshUnsavedState();
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
                : Path.Combine(targetDirectory, $"{slug}.bs");

            if (!isExistingBeatmap)
            {
                int counter = 1;
                while (File.Exists(targetPath))
                {
                    targetPath = Path.Combine(targetDirectory, $"{slug}-{counter++}.bs");
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

            // Use ~/BeatSight/Songs instead of ~/BeatSight/Beatmaps to match osu! convention
            string baseDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "BeatSight", "Songs");
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

        private class EditorSnapshot
        {
            public required string BeatmapJson { get; init; }
            public double CurrentTime { get; init; }
            public double Zoom { get; init; }
            public int SnapDivisor { get; init; }
            public double WaveformScale { get; init; }
            public bool BeatGridVisible { get; init; }
            public string Description { get; init; } = string.Empty;
        }

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
                gameplayPreview?.SetBeatmap(null);
                return;
            }

            double duration = trackLength > 0
                ? trackLength
                : Math.Max(beatmap.Audio.Duration, beatmap.HitObjects.Count > 0 ? beatmap.HitObjects[^1].Time + 5000 : 60000);

            Logger.Log($"[EditorScreen] reloadTimeline: setting beatmap with {beatmap.HitObjects.Count} notes, gameplayPreview={(gameplayPreview == null ? "NULL" : "exists")}", LoggingTarget.Runtime, LogLevel.Important);

            timeline.LoadBeatmap(beatmap, duration, waveformData);
            timeline.SetZoom(timelineZoom);
            timeline.SetSnap(snapDivisor, beatmap.Timing.Bpm);
            timeline.SetWaveformScale(waveformScale);
            timeline.SetBeatGridVisible(beatGridVisible);
            timeline.SetCurrentTime(currentTime);
            gameplayPreview?.SetBeatmap(beatmap);
        }
        private void queueWaveformLoad(string absolutePath)
        {
            if (string.IsNullOrEmpty(absolutePath) || !File.Exists(absolutePath))
                return;

            waveformLoadCts?.Cancel();
            waveformLoadCts?.Dispose();
            waveformLoadCts = new CancellationTokenSource();
            var token = waveformLoadCts.Token;

            waveformData = null;
            timeline?.UpdateWaveform(null);

            Task.Run(async () => await WaveformDataBuilder.BuildAsync(absolutePath, cancellationToken: token).ConfigureAwait(false), token)
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
                            if (result == null)
                            {
                                Schedule(() => appendStatusDetail("Waveform unavailable"));
                                return;
                            }

                            waveformData = result;
                            Schedule(() =>
                            {
                                if (!token.IsCancellationRequested)
                                {
                                    timeline?.UpdateWaveform(waveformData);
                                    timeline?.SetWaveformScale(waveformScale);
                                    timeline?.SetCurrentTime(currentTime);
                                }
                            });
                        }, TaskScheduler.Default);
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

                // Set clean status with just artist and title
                string artist = beatmap.Metadata.Artist ?? "Unknown Artist";
                string title = beatmap.Metadata.Title ?? "Untitled";
                setStatusBase($"Editing: {artist} — {title}");
                setStatusDetail(playbackAvailable ? null : offlinePlaybackMessage);

                hasUnsavedChanges = false;
                undoStack.Clear();
                redoStack.Clear();
                editSnapshotArmed = false;
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
                reloadTimeline();
                var editorInfo = ensureEditorInfo();
                editorInfo.TimelineZoom = timelineZoom;
                editorInfo.SnapDivisor = snapDivisor;
                editorInfo.WaveformScale = waveformScale;
                editorInfo.BeatGridVisible = beatGridVisible;
                refreshTimelineToolboxState();
                lastSavedSnapshot = serializeBeatmap(beatmap);

                // Load audio track
                loadAudioTrackFromBeatmap();
                if (!playbackAvailable)
                    appendStatusDetail(offlinePlaybackMessage);
                updateActionButtons();
                updatePlaybackAvailabilityUI();
            }
            catch (Exception ex)
            {
                setStatusBase("BeatSight Editor");
                setStatusDetail($"Failed to load: {ex.Message}");
                updateActionButtons();
            }
        }

        private void initializeNewProject(ImportedAudioTrack trackInfo)
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
                    Filename = trackInfo.RelativeStoragePath,
                    Duration = trackInfo.DurationMilliseconds.HasValue
                        ? (int)Math.Round(trackInfo.DurationMilliseconds.Value)
                        : 0
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

            setStatusBase("Editing: Unknown Artist — Untitled");
            setStatusDetail(playbackAvailable ? "Ready to map" : offlinePlaybackMessage);
            hasUnsavedChanges = true;
            undoStack.Clear();
            redoStack.Clear();
            editSnapshotArmed = false;
            lastSavedSnapshot = null;
            snapDivisor = 4;
            suppressEditorDefaultPersistence = true;
            applyEditorDefaultsFromConfig();
            suppressEditorDefaultPersistence = false;
            updateStatusText();
            trackLength = beatmap.Audio.Duration;
            reloadTimeline();
            ensureEditorInfo();
            refreshTimelineToolboxState();
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
            if (trackLength > 0 && currentTime > trackLength)
                currentTime = trackLength;

            bool audioStarted = false;

            if (track != null && playbackAvailable)
            {
                if (currentTime > track.Length)
                {
                    currentTime = 0;
                    track.Seek(0);
                }

                track.Start();
                lastTrackTime = track.CurrentTime;
                audioStarted = true;
            }

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
            currentTime = 0;
            track?.Seek(0);
            lastTrackTime = track?.CurrentTime ?? 0;
            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);
            appendStatusDetail("Rewound to start");
        }

        private void updatePlayPauseButtonLabel()
        {
            if (playPauseButton == null)
                return;

            string label = isPlaying ? "⏸ Pause" : "▶ Play";
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
                    label = "▶ Play (silent)";

                tooltip = isPlaying
                    ? "Pause timeline playback (audio unavailable)."
                    : "Play timeline playback (audio unavailable).";
            }

            playPauseButton.UpdateState(true, tooltip);
            playPauseButton.SetLabel(label);
        }

        protected override void Update()
        {
            base.Update();

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

            if (trackLength > 0)
                currentTime = Math.Clamp(currentTime, 0, trackLength);

            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
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

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.Z)
            {
                undoLastEdit();
                return true;
            }

            return base.OnKeyDown(e);
        }

        private static bool isZoomIncreaseKey(osuTK.Input.Key key)
                    => key == osuTK.Input.Key.Plus
                        || key == osuTK.Input.Key.KeypadPlus;

        private static bool isZoomDecreaseKey(osuTK.Input.Key key)
            => key == osuTK.Input.Key.Minus
                        || key == osuTK.Input.Key.KeypadMinus;

        private void seekRelative(double milliseconds)
        {
            double maximum = trackLength > 0 ? trackLength : track?.Length ?? Math.Max(currentTime + Math.Abs(milliseconds), 0);
            currentTime = Math.Clamp(currentTime + milliseconds, 0, maximum);
            track?.Seek(currentTime);
            timeText.Text = formatTime(currentTime);
            timeline?.SetCurrentTime(currentTime);
        }

        private static string formatTime(double milliseconds)
        {
            var time = TimeSpan.FromMilliseconds(milliseconds);
            return $"{time.Minutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";
        }

        private static bool isControlOrSuper(KeyDownEvent e) => e.ControlPressed || e.SuperPressed;

        public override bool OnExiting(ScreenExitEvent e)
        {
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

        private partial class PreviewToggleButton : BasicButton
        {
            private readonly Box background;
            private readonly SpriteText label;
            private readonly Bindable<EditorPreviewMode> previewMode;
            private readonly Color4 colour2D = UITheme.AccentPrimary;
            private readonly Color4 colour3D = UITheme.AccentSecondary;

            public event Action<string?>? HoverHintChanged;

            public PreviewToggleButton(Bindable<EditorPreviewMode> previewMode)
            {
                this.previewMode = previewMode.GetBoundCopy();

                Masking = true;
                CornerRadius = 8;

                AddRange(new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both
                    },
                    label = new SpriteText
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Font = new FontUsage(size: 18, weight: "Medium"),
                        Colour = EditorColours.TextPrimary
                    }
                });

                Action = toggleMode;
                this.previewMode.BindValueChanged(updateState, true);
            }

            private void toggleMode()
            {
                previewMode.Value = previewMode.Value == EditorPreviewMode.Playfield2D
                    ? EditorPreviewMode.Playfield3D
                    : EditorPreviewMode.Playfield2D;
            }

            private void updateState(ValueChangedEvent<EditorPreviewMode> state)
            {
                bool is3D = state.NewValue == EditorPreviewMode.Playfield3D;
                label.Text = is3D ? "3D View" : "2D View";
                background.FadeColour(is3D ? colour3D : colour2D, 200, Easing.OutQuint);
            }

            protected override bool OnHover(HoverEvent e)
            {
                string tooltip = previewMode.Value == EditorPreviewMode.Playfield3D
                    ? "Switch to 2D flat osu!mania-style lane view"
                    : "Switch to 3D Guitar Hero-style lane view";
                HoverHintChanged?.Invoke(tooltip);

                var targetColour = previewMode.Value == EditorPreviewMode.Playfield3D ? colour3D : colour2D;
                background.FadeColour(EditorColours.Lighten(targetColour, 1.15f), 140, Easing.OutQuint);
                this.ScaleTo(1.05f, 140, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                base.OnHoverLost(e);
                HoverHintChanged?.Invoke(null);

                var targetColour = previewMode.Value == EditorPreviewMode.Playfield3D ? colour3D : colour2D;
                background.FadeColour(targetColour, 180, Easing.OutQuint);
                this.ScaleTo(1f, 180, Easing.OutQuint);
            }

        }

        private partial class EditorButton : BasicButton
        {
            private readonly Box background;
            private readonly Color4 hoverColour;
            private readonly Color4 idleColour;
            private readonly Color4 disabledColour;
            private readonly SpriteText label;
            private string baseText;

            public string StatusMessage { get; private set; } = string.Empty;
            public event Action<string?>? HoverHintChanged;

            public EditorButton(string text, Color4 colour)
            {
                baseText = text;
                hoverColour = EditorColours.Lighten(colour, 1.15f);
                idleColour = colour;
                disabledColour = EditorColours.Lighten(colour, 0.6f);

                Masking = true;
                CornerRadius = 8;

                AddInternal(background = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = idleColour
                });

                AddInternal(label = new SpriteText
                {
                    Text = text,
                    Font = new FontUsage(size: 20),
                    Colour = EditorColours.TextPrimary,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre
                });

                Enabled.BindValueChanged(e => updateEnabledState(e.NewValue), true);
            }

            public void SetLabel(string text)
            {
                if (string.IsNullOrWhiteSpace(text))
                    text = baseText;

                baseText = text;
                label.Text = text;
                base.Text = text;
            }

            public void UpdateState(bool enabled, string tooltip)
            {
                StatusMessage = tooltip;
                label.Text = baseText;
                Enabled.Value = enabled;

                if (IsHovered)
                    HoverHintChanged?.Invoke(StatusMessage);
            }

            protected override bool OnHover(HoverEvent e)
            {
                HoverHintChanged?.Invoke(StatusMessage);

                if (!Enabled.Value)
                    return false;

                background.FadeColour(hoverColour, 200, Easing.OutQuint);
                this.ScaleTo(1.05f, 200, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                base.OnHoverLost(e);
                background.FadeColour(Enabled.Value ? idleColour : disabledColour, 200, Easing.OutQuint);
                this.ScaleTo(1f, 200, Easing.OutQuint);
                HoverHintChanged?.Invoke(null);
            }

            private void updateEnabledState(bool enabled)
            {
                background.FadeColour(enabled ? idleColour : disabledColour, 200, Easing.OutQuint);
                this.FadeTo(enabled ? 1f : 0.5f, 200, Easing.OutQuint);
                if (!enabled)
                    this.ScaleTo(1f, 200, Easing.OutQuint);
                label.FadeColour(enabled ? EditorColours.TextPrimary : EditorColours.Lighten(EditorColours.TextPrimary, 0.8f), 200, Easing.OutQuint);
            }
        }

    }
}
