using System;
using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.IO.Stores;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        [BackgroundDependencyLoader]
        private void load()
        {
            storageResourceStore ??= new StorageBackedResourceStore(host.Storage);
            storageTrackStore ??= audioManager.GetTrackStore(storageResourceStore);
            laneViewModeBindable = config.GetBindable<LaneViewMode>(BeatSightSetting.LaneViewMode);
            laneViewMode = laneViewModeBindable.GetBoundCopy();
            lanePresetSetting = config.GetBindable<LanePreset>(BeatSightSetting.LanePreset);
            kickLaneModeSetting = config.GetBindable<KickLaneMode>(BeatSightSetting.KickLaneMode);
            uiScaleSetting = config.GetBindable<double>(BeatSightSetting.UIScale);
            masterVolumeSetting = config.GetBindable<double>(BeatSightSetting.MasterVolume);
            musicVolumeSetting = config.GetBindable<double>(BeatSightSetting.MusicVolume);
            masterVolumeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.MasterVolumeEnabled);
            musicVolumeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.MusicVolumeEnabled);
            playbackZoomSetting = config.GetBindable<double>(BeatSightSetting.PlaybackZoomLevel);
            noteWidthSetting = config.GetBindable<double>(BeatSightSetting.PlaybackNoteWidth);

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
            editorSnapDivisorDefault = config.GetBindable<int>(BeatSightSetting.EditorSnapDivisorDefault);
            editorTimelinePlaybackZoomLinkedDefault = config.GetBindable<bool>(BeatSightSetting.EditorTimelinePlaybackZoomLinkedDefault);
            editorTimelineSplitRatioExpanded = config.GetBindable<double>(BeatSightSetting.EditorTimelineSplitRatioExpanded);
            editorTimelineSplitRatioCollapsed = config.GetBindable<double>(BeatSightSetting.EditorTimelineSplitRatioCollapsed);
            editorSnapDivisorDefault.Value = coerceSnapDivisor(editorSnapDivisorDefault.Value);
            editorTimelineSplitRatioExpanded.Value = Math.Clamp(
                double.IsFinite(editorTimelineSplitRatioExpanded.Value) ? editorTimelineSplitRatioExpanded.Value : defaultTimelineSplitRatioExpanded,
                0.0,
                1.0);
            editorTimelineSplitRatioCollapsed.Value = Math.Clamp(
                double.IsFinite(editorTimelineSplitRatioCollapsed.Value) ? editorTimelineSplitRatioCollapsed.Value : defaultTimelineSplitRatioCollapsed,
                0.0,
                1.0);
            initializeEditorMetronome();

            bool previousPersistenceState = suppressEditorDefaultPersistence;
            suppressEditorDefaultPersistence = true;
            applyEditorDefaultsFromConfig();
            suppressEditorDefaultPersistence = previousPersistenceState;

            laneViewMode.BindValueChanged(onLaneViewModeChanged, true);
            previewMode.BindValueChanged(onPreviewModeChanged);

            backButton = new BackButton
            {
                Margin = new MarginPadding(),
                Action = () => this.Exit()
            };

            var editorEdgePadding = new MarginPadding
            {
                Left = UITheme.ScreenPadding.Left + 20,
                Right = UITheme.ScreenPadding.Right + 20,
                Top = UITheme.ScreenPadding.Top + 4,
                Bottom = UITheme.ScreenPadding.Bottom + 12
            };

            var header = createHeader();
            var editor = createEditor();
            var footer = createFooter();
            var workspace = createEditorWorkspace(editor, footer);

            var layoutRoot = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    screenLayoutGrid = new GridContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        RowDimensions = new[]
                        {
                            new Dimension(GridSizeMode.AutoSize),
                            new Dimension()
                        },
                        Content = new[]
                        {
                            new Drawable[] { header },
                            new Drawable[] { workspace }
                        }
                    },
                    historyPanel
                }
            };

            var paddedLayout = new ScreenEdgeContainer(scrollable: false)
            {
                EdgePadding = editorEdgePadding,
                Content = layoutRoot
            };

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
                    Colour = ColourInfo.GradientVertical(
                        EditorColours.ScreenBackdropTop,
                        EditorColours.ScreenBackdropBottom)
                },
                new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 240,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Colour = ColourInfo.GradientVertical(
                        EditorColours.ScreenHeaderGlow,
                        Color4.Transparent)
                },
                paddedLayout,
                quickActionToast = new ToastContainer
                {
                    RelativeSizeAxes = Axes.Both
                },
                createScrubPerfOverlay(),
                createTimingSetupOverlay(),
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
            masterVolumeSetting.BindValueChanged(_ => updateEditorMasterVolumeOutput(), true);
            masterVolumeEnabledSetting.BindValueChanged(_ => updateEditorMasterVolumeOutput(), true);
            musicVolumeSetting.BindValueChanged(_ => updateEditorMusicVolumeOutput(), true);
            musicVolumeEnabledSetting.BindValueChanged(_ => updateEditorMusicVolumeOutput(), true);

            // Ensure preview is synchronized after everything is loaded
            if (beatmap != null && playbackPreview != null)
            {
                playbackPreview.SetBeatmap(beatmap);
            }

            // Make sure the correct preview mode is visible
            onPreviewModeChanged(new ValueChangedEvent<EditorPreviewMode>(previewMode.Value, previewMode.Value));

            updatePlaybackAvailabilityUI();
            applyResponsiveEditorLayout(force: true);
            Schedule(() => applyResponsiveEditorLayout(force: true));
        }
    }
}
