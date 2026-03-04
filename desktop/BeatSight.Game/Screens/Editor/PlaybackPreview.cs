using System;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.Screens.Playback.Playfield;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;

namespace BeatSight.Game.Screens.Editor
{
    public partial class PlaybackPreview : CompositeDrawable
    {
        private readonly Func<double> currentTimeProvider;
        private readonly Func<double>? snapIntervalProvider;
        private readonly Func<double>? snapOriginProvider;
        private readonly Func<bool>? snapEnabledProvider;
        private readonly Func<double, double>? snapIntervalAtTimeProvider;
        private readonly Func<double, double>? snapOriginAtTimeProvider;
        private PreviewStageContainer stageContainer = null!;
        private PlaybackPlayfield playfield = null!;
        private SpriteText placeholderText = null!;
        private Container editHintContainer = null!;
        private SpriteText editHintText = null!;
        private Container placementGhost = null!;
        private Container placementGhostBody = null!;
        private SpriteText placementGhostText = null!;
        private Beatmap? beatmap;
        private Bindable<LanePreset> lanePresetSetting = null!;
        private Bindable<KickLaneMode> kickLaneModeSetting = null!;
        private Bindable<ThreeDStageProfile> threeDStageProfileSetting = null!;
        private Bindable<double> playbackZoomSetting = null!;
        private Bindable<double> noteWidthSetting = null!;
        private LaneLayout currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
        private bool useGlobalKickLine;
        private string? manuscriptFocusComponent;
        private bool placementGhostBypassSnap;
        private int placementGhostLane;
        private double placementGhostTimeMs;

        public event Action<int, double, bool>? NotePlacementRequested;
        public event Action<int, double>? NoteRemovalRequested;
        public Func<Vector2, bool>? PlacementInputBlockedAtScreenSpace { get; set; }

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        public PlaybackPreview(
            Func<double> currentTimeProvider,
            Func<double>? snapIntervalProvider = null,
            Func<double>? snapOriginProvider = null,
            Func<bool>? snapEnabledProvider = null,
            Func<double, double>? snapIntervalAtTimeProvider = null,
            Func<double, double>? snapOriginAtTimeProvider = null)
        {
            this.currentTimeProvider = currentTimeProvider;
            this.snapIntervalProvider = snapIntervalProvider;
            this.snapOriginProvider = snapOriginProvider;
            this.snapEnabledProvider = snapEnabledProvider;
            this.snapIntervalAtTimeProvider = snapIntervalAtTimeProvider;
            this.snapOriginAtTimeProvider = snapOriginAtTimeProvider;

            RelativeSizeAxes = Axes.Both;
            Masking = false;
            CornerRadius = 0;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            playfield = new PlaybackPlayfield(currentTimeProvider, snapEnabledProvider, snapIntervalAtTimeProvider)
            {
                RelativeSizeAxes = Axes.Both
            };
            playfield.SetPreviewMode(true);
            playfield.AutoZoom.Value = false;
            playfield.SetLaneLayout(currentLaneLayout);

            stageContainer = new PreviewStageContainer(playfield)
            {
                RelativeSizeAxes = Axes.Both
            };

            placeholderText = new SpriteText
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Font = BeatSightFont.Section(18f),
                Colour = new Color4(198, 205, 224, 255),
                Text = "Load or create a beatmap to preview playback",
                Alpha = 0
            };

            editHintText = new SpriteText
            {
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Font = BeatSightFont.Caption(10.8f),
                Colour = new Color4(206, 220, 244, 220),
                Text = "LMB place note | Shift+LMB ignore snap | RMB remove nearest lane note"
            };

            editHintContainer = new Container
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                AutoSizeAxes = Axes.Both,
                Margin = new MarginPadding { Left = 12, Top = 12 },
                Alpha = 0,
                Masking = true,
                CornerRadius = 6,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(12, 16, 28, 152)
                    },
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 8, Vertical = 5 },
                        Child = editHintText
                    }
                }
            };

            placementGhost = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.Centre,
                Alpha = 0,
                Children = new Drawable[]
                {
                    placementGhostBody = new Container
                    {
                        Size = new Vector2(28, 10),
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Masking = true,
                        CornerRadius = 5,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(140, 220, 255, 190)
                            },
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(255, 255, 255, 90),
                                Alpha = 0.22f
                            }
                        }
                    },
                    placementGhostText = new SpriteText
                    {
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.BottomCentre,
                        Y = -8,
                        Font = BeatSightFont.Caption(9.6f),
                        Colour = new Color4(214, 228, 252, 235),
                        Text = string.Empty
                    }
                }
            };

            InternalChildren = new Drawable[]
            {
                stageContainer,
                placementGhost,
                editHintContainer,
                placeholderText
            };

            lanePresetSetting = config.GetBindable<LanePreset>(BeatSightSetting.LanePreset);
            lanePresetSetting.BindValueChanged(onLanePresetChanged, true);

            kickLaneModeSetting = config.GetBindable<KickLaneMode>(BeatSightSetting.KickLaneMode);
            kickLaneModeSetting.BindValueChanged(onKickLaneModeChanged, true);

            threeDStageProfileSetting = config.GetBindable<ThreeDStageProfile>(BeatSightSetting.ThreeDStageProfile);
            playfield.StageProfile.BindTo(threeDStageProfileSetting);
            playbackZoomSetting = config.GetBindable<double>(BeatSightSetting.PlaybackZoomLevel);
            playfield.ZoomLevel.BindTo(playbackZoomSetting);
            noteWidthSetting = config.GetBindable<double>(BeatSightSetting.PlaybackNoteWidth);
            playfield.NoteWidthScale.BindTo(noteWidthSetting);
            noteWidthSetting.BindValueChanged(_ => updatePlacementGhostVisualScale(), true);

            updatePlaceholderState();
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            applyBeatmap();
        }

        public void SetBeatmap(Beatmap? beatmap)
        {
            this.beatmap = beatmap;

            if (!IsLoaded)
                return;

            applyBeatmap();
        }

        public void RefreshBeatmap()
        {
            if (!IsLoaded)
                return;

            applyBeatmap();
        }

        public void ForceVisualLayoutRefresh()
        {
            if (!IsLoaded || playfield == null)
                return;

            playfield.ForceVisualLayoutRefresh();
        }

        public double GetFutureViewportDurationMsAtZoom(double zoomLevel)
        {
            if (!IsLoaded || playfield == null)
                return 0;

            return playfield.GetFutureViewportDurationMsAtZoom(zoomLevel);
        }

        public void JumpToTime(double timeMs, bool lightweightSeek = false)
        {
            if (!IsLoaded || playfield == null)
                return;

            playfield.JumpToTime(Math.Max(0, timeMs), lightweightSeek);
        }

        public void SetManuscriptFocusComponent(string? componentName)
        {
            manuscriptFocusComponent = componentName;

            if (!IsLoaded || playfield == null)
                return;

            playfield.SetManuscriptFocusComponent(componentName);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            if (beatmap == null || playfield == null)
                return base.OnMouseDown(e);

            if (isPlacementInputBlocked(e.ScreenSpaceMousePosition))
            {
                placementGhost?.FadeOut(80, Easing.OutQuint);
                return true;
            }

            if (e.Button == MouseButton.Left)
            {
                bool shiftPressed = isShiftPressed();
                if (!tryResolvePlacementAtPointer(e.ScreenSpaceMousePosition, shiftPressed, out int lane, out double timeMs, out bool bypassSnap))
                    return true;

                NotePlacementRequested?.Invoke(lane, timeMs, bypassSnap);
                return true;
            }

            if (e.Button != MouseButton.Right)
                return base.OnMouseDown(e);

            double removalTimeMs = Math.Max(0, currentTimeProvider());
            if (!playfield.TryResolvePlacementFromScreenSpace(e.ScreenSpaceMousePosition, out int laneToRemove, out removalTimeMs))
            {
                if (!playfield.TryResolveLaneFromScreenSpace(e.ScreenSpaceMousePosition, out laneToRemove))
                    return true;
            }

            NoteRemovalRequested?.Invoke(laneToRemove, Math.Max(0, removalTimeMs));
            return true;
        }

        protected override bool OnMouseMove(MouseMoveEvent e)
        {
            if (isPlacementInputBlocked(e.ScreenSpaceMousePosition))
            {
                placementGhost?.FadeOut(80, Easing.OutQuint);
                return true;
            }

            updatePlacementGhost(e.ScreenSpaceMousePosition, isShiftPressed());
            return base.OnMouseMove(e);
        }

        protected override bool OnHover(HoverEvent e)
        {
            if (isPlacementInputBlocked(e.ScreenSpaceMousePosition))
            {
                placementGhost?.FadeOut(80, Easing.OutQuint);
                return true;
            }

            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            placementGhost?.FadeOut(80, Easing.OutQuint);
            base.OnHoverLost(e);
        }

        private void applyBeatmap()
        {
            if (playfield == null)
                return;

            currentLaneLayout = resolvePreviewLaneLayout();

            playfield.SetLaneLayout(currentLaneLayout);
            playfield.SetKickLineMode(useGlobalKickLine);

            var previewBeatmap = cloneBeatmapForPreview(beatmap);
            if (previewBeatmap.HitObjects.Count > 0 && previewBeatmapNeedsLaneResolution(previewBeatmap, currentLaneLayout))
                DrumLaneHeuristics.ApplyToBeatmap(previewBeatmap, currentLaneLayout, preserveStoredLane: true);

            playfield.LoadBeatmap(previewBeatmap);
            playfield.SetManuscriptFocusComponent(manuscriptFocusComponent);

            playfield.JumpToTime(Math.Max(0, currentTimeProvider()));

            updatePlaceholderState();
        }

        private void onLanePresetChanged(ValueChangedEvent<LanePreset> _)
        {
            if (!IsLoaded)
                return;

            applyBeatmap();
        }

        private void onKickLaneModeChanged(ValueChangedEvent<KickLaneMode> mode)
        {
            useGlobalKickLine = mode.NewValue == KickLaneMode.GlobalLine;
            playfield?.SetKickLineMode(useGlobalKickLine);
        }

        private void updatePlaceholderState()
        {
            int noteCount = beatmap?.HitObjects.Count ?? 0;
            bool hasContent = noteCount > 0;

            stageContainer?.FadeTo(hasContent ? 1f : 0.35f, 200, Easing.OutQuint);

            if (placeholderText == null)
                return;

            if (hasContent)
            {
                placeholderText.FadeOut(200, Easing.OutQuint);
                editHintText.Text = "LMB place note | Shift+LMB ignore snap | RMB remove nearest lane note";
                editHintContainer.FadeIn(180, Easing.OutQuint);
            }
            else
            {
                placeholderText.Text = beatmap == null
                    ? "Load or create a beatmap to preview playback"
                    : "Add notes to preview playback";
                placeholderText.FadeIn(200, Easing.OutQuint);
                editHintText.Text = "LMB place notes in the preview area to start mapping";
                editHintContainer.FadeIn(160, Easing.OutQuint);
            }
        }

        private bool tryResolvePlacementAtPointer(Vector2 screenSpacePosition, bool shiftPressed, out int lane, out double timeMs, out bool bypassSnap)
        {
            lane = 0;
            timeMs = Math.Max(0, currentTimeProvider());
            bypassSnap = shiftPressed || shouldBypassSnap();

            if (playfield == null)
                return false;

            // Preview placement should resolve both lane and time from cursor position so
            // users can place notes anywhere inside the playfield bounds.
            if (!playfield.TryResolvePlacementFromScreenSpace(screenSpacePosition, out lane, out double placementTime))
                return false;

            placementTime = Math.Max(0, placementTime);

            if (!bypassSnap)
            {
                double interval = Math.Max(0, snapIntervalAtTimeProvider?.Invoke(placementTime) ?? snapIntervalProvider?.Invoke() ?? 0);
                if (interval > 0.01)
                {
                    double snapOrigin = snapOriginAtTimeProvider?.Invoke(placementTime) ?? snapOriginProvider?.Invoke() ?? beatmap?.Timing.Offset ?? 0;
                    placementTime = Math.Round((placementTime - snapOrigin) / interval) * interval + snapOrigin;
                    placementTime = Math.Max(0, placementTime);
                }
            }

            timeMs = placementTime;
            return true;
        }

        private void updatePlacementGhost(Vector2 screenSpacePosition, bool shiftPressed)
        {
            if (beatmap == null || playfield == null || placementGhost == null)
            {
                placementGhost?.FadeOut(80, Easing.OutQuint);
                return;
            }

            if (!tryResolvePlacementAtPointer(screenSpacePosition, shiftPressed, out int lane, out double timeMs, out bool bypassSnap))
            {
                placementGhost.FadeOut(80, Easing.OutQuint);
                return;
            }

            Vector2 drawPosition = screenSpacePosition;
            if (playfield.TryResolvePlacementScreenSpace(lane, timeMs, out Vector2 snappedScreenSpace))
                drawPosition = snappedScreenSpace;

            placementGhostLane = lane;
            placementGhostTimeMs = timeMs;
            placementGhostBypassSnap = bypassSnap;

            placementGhost.Position = ToLocalSpace(drawPosition);
            string laneLabel = playfield.GetLaneLabelForLogicalLane(lane);
            placementGhostText.Text = bypassSnap
                ? $"{laneLabel} | {formatPreviewTime(timeMs)} | Snap Off"
                : $"{laneLabel} | {formatPreviewTime(timeMs)}";

            if (playfield.TryResolvePlacementNoteSize(lane, timeMs, out Vector2 noteSizeScreen))
                applyPlacementGhostSize(drawPosition, noteSizeScreen);
            else
                updatePlacementGhostVisualScale();

            placementGhost.FadeIn(70, Easing.OutQuint);
        }

        private bool shouldBypassSnap()
        {
            if (snapEnabledProvider == null)
                return false;

            return !snapEnabledProvider();
        }

        private bool isPlacementInputBlocked(Vector2 screenSpacePosition)
            => PlacementInputBlockedAtScreenSpace?.Invoke(screenSpacePosition) ?? false;

        private bool isShiftPressed()
            => GetContainingInputManager()?.CurrentState.Keyboard.ShiftPressed ?? false;

        private static string formatPreviewTime(double milliseconds)
        {
            var clamped = Math.Max(0, milliseconds);
            var time = TimeSpan.FromMilliseconds(clamped);
            if (time.TotalHours >= 1)
                return $"{(int)time.TotalHours:00}:{time.Minutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";

            return $"{(int)time.TotalMinutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";
        }

        private void updatePlacementGhostVisualScale()
        {
            if (placementGhostBody == null)
                return;

            double clamped = Math.Clamp(noteWidthSetting?.Value ?? 1.0, 0.5, 1.5);
            float normalized = (float)((clamped - 0.5) / 1.0);
            bool isTwoDimensional = playfield?.CurrentLaneViewMode == LaneViewMode.TwoDimensional;
            placementGhostBody.Size = isTwoDimensional
                ? new Vector2(
                    56f + (212f - 56f) * normalized,
                    7f + (13f - 7f) * normalized)
                : new Vector2(
                    64f + (248f - 64f) * normalized,
                    10f + (24f - 10f) * normalized);
            placementGhostBody.CornerRadius = placementGhostBody.Height * 0.48f;
        }

        private void applyPlacementGhostSize(Vector2 anchorScreenPosition, Vector2 noteSizeScreen)
        {
            if (placementGhostBody == null)
                return;

            Vector2 halfSize = noteSizeScreen * 0.5f;
            Vector2 localLeft = ToLocalSpace(anchorScreenPosition - new Vector2(halfSize.X, 0));
            Vector2 localRight = ToLocalSpace(anchorScreenPosition + new Vector2(halfSize.X, 0));
            Vector2 localTop = ToLocalSpace(anchorScreenPosition - new Vector2(0, halfSize.Y));
            Vector2 localBottom = ToLocalSpace(anchorScreenPosition + new Vector2(0, halfSize.Y));

            float width = Math.Max(12f, Math.Abs(localRight.X - localLeft.X));
            float height = Math.Max(6f, Math.Abs(localBottom.Y - localTop.Y));
            if (playfield?.CurrentLaneViewMode == LaneViewMode.TwoDimensional)
            {
                width = Math.Clamp(width, 28f, 320f);
                height = Math.Clamp(height, 7f, 14f);
            }

            placementGhostBody.Size = new Vector2(width, height);
            placementGhostBody.CornerRadius = height * 0.48f;
        }

        private LaneLayout resolvePreviewLaneLayout()
        {
            int minimumLaneCount = LaneManagement.ResolveLaneCount(beatmap, fallbackLaneCount: 7);

            // Match PlaybackScreen lane-resolution behavior exactly so the editor preview
            // stays consistent with full playback mode.
            if (lanePresetSetting.Value != LanePreset.AutoDynamic)
            {
                LaneLayout preferredLayout = LaneLayoutFactory.Create(lanePresetSetting.Value);
                if (minimumLaneCount <= preferredLayout.LaneCount)
                    return preferredLayout;
            }

            // If authored data requires more lanes than the selected preset provides,
            // use an auto-dynamic layout sized for authored lane indices to avoid
            // silent remapping of stored lanes.
            return LaneLayoutFactory.CreateAutoDynamic(beatmap?.DrumKit?.Components, minimumLaneCount);
        }

        private static bool previewBeatmapNeedsLaneResolution(Beatmap beatmap, LaneLayout layout)
        {
            if (beatmap.HitObjects == null || beatmap.HitObjects.Count == 0)
                return false;

            // If any stored lane is invalid for the active layout, resolve lanes.
            foreach (var hit in beatmap.HitObjects)
            {
                if (!hit.Lane.HasValue || !layout.IsLaneValid(hit.Lane.Value))
                    return true;
            }

            // Keep authored lane assignments exactly as stored whenever lanes are valid.
            // Heuristic remapping here can silently alter valid .bsm maps.
            return false;
        }

        private static Beatmap cloneBeatmapForPreview(Beatmap? source)
        {
            if (source == null)
                return new Beatmap();

            return new Beatmap
            {
                Version = source.Version,
                Metadata = new BeatmapMetadata
                {
                    Title = source.Metadata.Title,
                    Artist = source.Metadata.Artist,
                    Creator = source.Metadata.Creator,
                    Source = source.Metadata.Source,
                    Tags = new System.Collections.Generic.List<string>(source.Metadata.Tags),
                    Difficulty = source.Metadata.Difficulty,
                    PreviewTime = source.Metadata.PreviewTime,
                    BeatmapId = source.Metadata.BeatmapId,
                    CreatedAt = source.Metadata.CreatedAt,
                    ModifiedAt = source.Metadata.ModifiedAt,
                    Description = source.Metadata.Description,
                    BackgroundFile = source.Metadata.BackgroundFile,
                    ReleaseDate = source.Metadata.ReleaseDate,
                    Provider = source.Metadata.Provider
                },
                Audio = new AudioInfo
                {
                    Filename = source.Audio.Filename,
                    Hash = source.Audio.Hash,
                    Duration = source.Audio.Duration,
                    SampleRate = source.Audio.SampleRate,
                    DrumStem = source.Audio.DrumStem,
                    DrumStemHash = source.Audio.DrumStemHash
                },
                Timing = new TimingInfo
                {
                    Bpm = source.Timing.Bpm,
                    Offset = source.Timing.Offset,
                    TimeSignature = source.Timing.TimeSignature,
                    TimingPoints = source.Timing.TimingPoints?
                        .Select(point => new TimingPoint
                        {
                            Time = point.Time,
                            Bpm = point.Bpm,
                            TimeSignature = point.TimeSignature
                        })
                        .ToList()
                },
                DrumKit = new DrumKitInfo
                {
                    Components = new System.Collections.Generic.List<string>(source.DrumKit.Components),
                    Layout = source.DrumKit.Layout,
                    CustomSamples = source.DrumKit.CustomSamples != null
                        ? new System.Collections.Generic.Dictionary<string, string>(source.DrumKit.CustomSamples)
                        : null,
                    LaneLayout = source.DrumKit.LaneLayout == null
                        ? null
                        : new LaneLayoutInfo
                        {
                            Lanes = source.DrumKit.LaneLayout.Lanes?
                                .Select(lane => new LaneInfo
                                {
                                    Index = lane.Index,
                                    Name = lane.Name,
                                    ShortName = lane.ShortName,
                                    ColorHex = lane.ColorHex
                                })
                                .ToList()
                        }
                },
                HitObjects = source.HitObjects
                    .Select(hit => new HitObject
                    {
                        Time = hit.Time,
                        Component = hit.Component,
                        Velocity = hit.Velocity,
                        Lane = hit.Lane,
                        Duration = hit.Duration
                    })
                    .ToList(),
                Editor = source.Editor == null
                    ? null
                    : new EditorInfo
                    {
                        SnapDivisor = source.Editor.SnapDivisor,
                        VisualLanes = source.Editor.VisualLanes,
                        Bookmarks = source.Editor.Bookmarks == null
                            ? null
                            : new System.Collections.Generic.List<int>(source.Editor.Bookmarks),
                        TimelineZoom = source.Editor.TimelineZoom,
                        WaveformScale = source.Editor.WaveformScale,
                        BeatGridVisible = source.Editor.BeatGridVisible,
                        AiGenerationMetadata = source.Editor.AiGenerationMetadata == null
                            ? null
                            : new AIGenerationMetadata
                            {
                                ModelVersion = source.Editor.AiGenerationMetadata.ModelVersion,
                                Confidence = source.Editor.AiGenerationMetadata.Confidence,
                                ProcessedAt = source.Editor.AiGenerationMetadata.ProcessedAt,
                                ManualEdits = source.Editor.AiGenerationMetadata.ManualEdits,
                                MetadataProvider = source.Editor.AiGenerationMetadata.MetadataProvider,
                                MetadataConfidence = source.Editor.AiGenerationMetadata.MetadataConfidence
                            }
                    }
            };
        }

        private partial class PreviewStageContainer : CompositeDrawable
        {
            public PreviewStageContainer(Drawable playfield)
            {
                RelativeSizeAxes = Axes.Both;
                InternalChild = playfield;
            }
        }
    }
}
