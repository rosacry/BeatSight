using System;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createTimelineToolbox()
        {
            timelineMiniButtons.Clear();
            timelineMiniButtonTexts.Clear();
            timelineSectionTitleTexts.Clear();
            timelineSectionControlRows.Clear();
            timelineSectionBodies.Clear();
            timelineToolboxSectionWrappers.Clear();
            var timelineCopy = EditorTimelineCopy.Active;

            timelineZoomValueText = new SpriteText
            {
                Text = $"{timelineZoom:0.00}x",
                Font = BeatSightFont.Caption(11.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
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
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Child = timelineZoomSlider
            };
            timelineZoomSliderContainer = zoomSliderContainer;

            waveformScaleValueText = new SpriteText
            {
                Text = $"{waveformScale:0.00}x",
                Font = BeatSightFont.Caption(11.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
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
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Child = waveformScaleSlider
            };
            timelineWaveformSliderContainer = waveformSliderContainer;

            playbackRateValueText = new SpriteText
            {
                Text = $"{playbackRate:0.00}x",
                Font = BeatSightFont.Caption(11.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            };

            playbackRateSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.Both,
                DragStepMultiplier = 1
            };
            var playbackRateBindable = new BindableDouble(playbackRate)
            {
                MinValue = minPlaybackRate,
                MaxValue = maxPlaybackRate,
                Precision = 0.01
            };
            playbackRateSlider.Current = playbackRateBindable;
            playbackRateSlider.Current.ValueChanged += e =>
            {
                if (suppressPlaybackRateSync)
                    return;

                setPlaybackRate(e.NewValue, announce: false);
            };

            var playbackRateSliderContainer = new Container
            {
                Width = 144,
                Height = 30,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Child = playbackRateSlider
            };
            timelinePlaybackRateSliderContainer = playbackRateSliderContainer;

            double currentPlaybackZoom = Math.Clamp(playbackZoomSetting?.Value ?? 1.0, editorPlaybackZoomMin, editorPlaybackZoomMax);
            if (playbackZoomSetting != null && Math.Abs(playbackZoomSetting.Value - currentPlaybackZoom) > 0.0001)
                playbackZoomSetting.Value = currentPlaybackZoom;

            playbackZoomValueText = new SpriteText
            {
                Text = $"{currentPlaybackZoom:0.00}x",
                Font = BeatSightFont.Caption(11.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            };

            playbackZoomSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.Both,
                DragStepMultiplier = 1
            };
            var playbackZoomBindable = new BindableDouble(currentPlaybackZoom)
            {
                MinValue = editorPlaybackZoomMin,
                MaxValue = editorPlaybackZoomMax,
                Precision = 0.01
            };
            playbackZoomSlider.Current = playbackZoomBindable;
            playbackZoomSlider.PointerAdjustingChanged += adjusting =>
            {
                playbackZoomPointerAdjusting = adjusting;

                if (adjusting)
                {
                    beginPlaybackZoomInteraction();
                    return;
                }

                endPlaybackZoomInteraction();
            };
            playbackZoomSlider.Current.ValueChanged += e =>
            {
                if (suppressPlaybackZoomSync)
                    return;

                if (playbackZoomPointerAdjusting)
                {
                    previewPlaybackZoom(e.NewValue);
                    return;
                }

                setPlaybackZoomScale(e.NewValue, announce: false);
            };
            playbackZoomSetting?.BindValueChanged(_ =>
            {
                syncPlaybackZoomDisplay();

                if (playbackZoomInteractionActive && playbackZoomPointerAdjusting)
                {
                    syncLinkedTimelineZoomFromPlayback(preview: true);
                    return;
                }

                syncLinkedTimelineZoomFromPlayback();
            });

            var playbackZoomSliderContainer = new Container
            {
                Width = 144,
                Height = 30,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Child = playbackZoomSlider
            };
            timelinePlaybackZoomSliderContainer = playbackZoomSliderContainer;

            double currentNoteWidth = Math.Clamp(noteWidthSetting?.Value ?? 1.0, 0.5, 1.5);
            if (noteWidthSetting != null && Math.Abs(noteWidthSetting.Value - currentNoteWidth) > 0.0001)
                noteWidthSetting.Value = currentNoteWidth;
            noteWidthValueText = new SpriteText
            {
                Text = $"{currentNoteWidth:0.00}x",
                Font = BeatSightFont.Caption(11.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            };

            noteWidthSlider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.Both,
                DragStepMultiplier = 1
            };
            var noteWidthBindable = new BindableDouble(currentNoteWidth)
            {
                MinValue = 0.5,
                MaxValue = 1.5,
                Precision = 0.01
            };
            noteWidthSlider.Current = noteWidthBindable;
            noteWidthSlider.Current.ValueChanged += e =>
            {
                if (suppressNoteWidthSync)
                    return;

                setNoteWidthScale(e.NewValue, announce: false);
            };
            noteWidthSetting?.BindValueChanged(_ => syncNoteWidthScaleDisplay());

            var noteWidthSliderContainer = new Container
            {
                Width = 144,
                Height = 30,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Child = noteWidthSlider
            };
            timelineNoteWidthSliderContainer = noteWidthSliderContainer;

            snapDivisorText = new SpriteText
            {
                Text = $"1/{snapDivisor}",
                Font = BeatSightFont.Title(12.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            };

            beatGridCheckbox = new BeatSightCheckbox
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
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

            timelineLinkZoomCheckbox = new BeatSightCheckbox
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                LabelText = timelineCopy.LinkZoomLabel,
                LabelFontSize = 11.8f
            };
            timelineLinkZoomCheckbox.Current.Value = linkTimelineAndPlaybackZoom;
            timelineLinkZoomCheckbox.Current.ValueChanged += e =>
            {
                if (suppressTimelineZoomLinkSync)
                    return;

                setTimelineZoomLink(e.NewValue);
            };

            var zoomSection = createTimelineSliderSection(
                timelineCopy.SectionZoom,
                timelineZoomValueText,
                zoomSliderContainer,
                () => adjustTimelineZoom(false),
                () => adjustTimelineZoom(true),
                () => applyTimelineZoom(1.0));

            var waveformSection = createTimelineSliderSection(
                timelineCopy.SectionWaveform,
                waveformScaleValueText,
                waveformSliderContainer,
                () => adjustWaveformScale(false),
                () => adjustWaveformScale(true),
                () => setWaveformScale(1.0),
                new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Child = new BeatSightCheckbox
                    {
                        LabelText = timelineCopy.DrumStemLabel,
                        LabelFontSize = 11.8f,
                        Current = showDrumStem,
                    }
                });

            var playbackSection = createTimelineSliderSection(
                timelineCopy.SectionPlayback,
                playbackRateValueText,
                playbackRateSliderContainer,
                () => adjustPlaybackRate(false),
                () => adjustPlaybackRate(true),
                resetPlaybackRate);

            var playbackZoomSection = createTimelineSliderSection(
                timelineCopy.SectionPlaybackZoom,
                playbackZoomValueText,
                playbackZoomSliderContainer,
                () => adjustPlaybackZoomScale(false),
                () => adjustPlaybackZoomScale(true),
                () => setPlaybackZoomScale(1.0));

            var toolbarToggleSection = createTimelineSection("Toolbar",
                new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Width = 1f,
                    Height = 32,
                    Child = timelineToolboxToggleButton = new EditorButton("Hide", EditorColours.AccentUndo)
                    {
                        RelativeSizeAxes = Axes.X,
                        Width = 1f,
                        Height = 32,
                        EnableScaleAnimation = false,
                        Alpha = 0,
                        Action = toggleTimelineToolboxCollapsed
                    }
                });

            var noteWidthSection = createTimelineSliderSection(
                timelineCopy.SectionNoteWidth,
                noteWidthValueText,
                noteWidthSliderContainer,
                () => adjustNoteWidthScale(false),
                () => adjustNoteWidthScale(true),
                () => setNoteWidthScale(1.0));

            var snapSection = createTimelineSection(timelineCopy.SectionSnap,
                createTimelineMiniButton("-", () => adjustSnapDivisor(false), 32),
                snapDivisorText,
                createTimelineMiniButton("+", () => adjustSnapDivisor(true), 32));

            var gridSection = createTimelineSection(timelineCopy.SectionOverlay,
                beatGridCheckbox,
                new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Margin = new MarginPadding { Left = 4 },
                    Child = timelineLinkZoomCheckbox
                });

            var firstNoteButton = createTimelineMiniButton(timelineCopy.FirstNoteButton, jumpToFirstNote, 98);
            timelineFirstNoteButton = firstNoteButton;
            timelineFirstNoteButtonText = timelineMiniButtonTexts[^1];

            var lastNoteButton = createTimelineMiniButton(timelineCopy.LastNoteButton, jumpToLastNote, 96);
            timelineLastNoteButton = lastNoteButton;
            timelineLastNoteButtonText = timelineMiniButtonTexts[^1];

            var timingButton = createTimelineMiniButton("Timing", openTimingSetupOverlay, 92);
            timelineTimingButton = timingButton;

            var metronomeButton = createTimelineMiniButton("Metro Off", toggleEditorMetronome, 104);
            timelineMetronomeButton = metronomeButton;
            timelineMetronomeButtonText = timelineMiniButtonTexts[^1];

            var snapSelectionButton = createTimelineMiniButton(timelineCopy.SnapSelectionButton, snapSelectionToTransient, 110);
            timelineSnapAudioButton = snapSelectionButton;
            timelineSnapAudioButtonText = timelineMiniButtonTexts[^1];

            var regenerateButton = createTimelineMiniButton(timelineCopy.RegenerateButton, regenerateRegion, 108);
            timelineRegenerateButton = regenerateButton;
            timelineRegenerateButtonText = timelineMiniButtonTexts[^1];

            var toolsSection = createTimelineSection(timelineCopy.SectionTools,
                firstNoteButton,
                lastNoteButton,
                timingButton,
                metronomeButton,
                snapSelectionButton,
                regenerateButton);

            var laneSection = createTimelineLaneSection();

            var contentFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(12, 8),
                Children = new Drawable[]
                {
                    createTimelineSectionGridRow(
                        (zoomSection, 0.22f),
                        (waveformSection, 0.25f),
                        (playbackSection, 0.19f),
                        (playbackZoomSection, 0.19f),
                        (toolbarToggleSection, 0.15f)),
                    createTimelineSectionGridRow(
                        (noteWidthSection, 0.22f),
                        (snapSection, 0.14f),
                        (gridSection, 0.18f),
                        (toolsSection, 0.46f)),
                    createTimelineSectionGridRow((laneSection, 1f))
                }
            };
            timelineToolboxContentFlow = contentFlow;

            var background = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = EditorColours.TimelineToolbarBackground
            };

            var container = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 0,
                Children = new Drawable[]
                {
                    background,
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.12f
                    },
                    timelineToolboxInnerContainer = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding { Left = 12, Right = 12, Top = 2, Bottom = 8 },
                        Child = contentFlow
                    }
                }
            };
            timelineToolboxContainer = container;
            timelineToolboxHostContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.None,
                Height = timelineToolboxRowHeight,
                Masking = true,
                Child = container
            };

            refreshTimelineToolboxState();
            return timelineToolboxHostContainer;
        }

        private Drawable createTimelineLaneSection()
        {
            var laneNameInput = new BeatSightTextBox
            {
                Width = 98,
                Height = 30,
                PlaceholderText = "Name",
                TextSize = 11.6f
            };
            timelineLaneNameInput = laneNameInput;

            var laneShortInput = new BeatSightTextBox
            {
                Width = 68,
                Height = 30,
                PlaceholderText = "Short",
                TextSize = 11.6f
            };
            timelineLaneShortNameInput = laneShortInput;

            var laneColorInput = new BeatSightTextBox
            {
                Width = 78,
                Height = 30,
                PlaceholderText = "#RRGGBB",
                TextSize = 11.6f
            };
            timelineLaneColorInput = laneColorInput;

            var laneLabel = new SpriteText
            {
                Text = "Lane 1",
                Font = BeatSightFont.Caption(11.6f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Truncate = true,
                MaxWidth = 104,
                UseFullGlyphHeight = false
            };
            timelineLaneSelectionText = laneLabel;

            var laneInlineRow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Full,
                Spacing = new Vector2(6, 0),
                Children = new Drawable[]
                {
                    timelineLanePrevButton = createTimelineMiniButton("<", () => stepTimelineLaneSelection(-1), 32),
                    new Container
                    {
                        Width = 112,
                        Height = 30,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.TopLeft,
                        Child = laneLabel
                    },
                    timelineLaneNextButton = createTimelineMiniButton(">", () => stepTimelineLaneSelection(1), 32),
                    laneNameInput,
                    laneShortInput,
                    laneColorInput,
                    timelineLaneApplyButton = createTimelineMiniButton("Save", applyTimelineLaneEdits, 52),
                    timelineLaneAddButton = createTimelineMiniButton("+", addTimelineLane, 34),
                    timelineLaneRemoveButton = createTimelineMiniButton("-", removeTimelineLane, 34),
                    timelineLaneMoveLeftButton = createTimelineMiniButton("<<", () => moveTimelineLane(-1), 38),
                    timelineLaneMoveRightButton = createTimelineMiniButton(">>", () => moveTimelineLane(1), 38)
                }
            };

            return createTimelineSection("Lanes", laneInlineRow);
        }

        private Drawable createTimelineSectionGridRow(params (Drawable Section, float Weight)[] sections)
        {
            if (sections.Length == 0)
                return new Container { RelativeSizeAxes = Axes.X, Height = 0 };

            var rowChildren = new Drawable[sections.Length];

            for (int i = 0; i < sections.Length; i++)
            {
                bool hasTrailingGap = i < sections.Length - 1;
                var wrapper = new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Width = 1f,
                    AutoSizeAxes = Axes.Y,
                    Padding = new MarginPadding { Right = hasTrailingGap ? 10f : 0f },
                    Children = hasTrailingGap
                        ? new Drawable[]
                        {
                            sections[i].Section,
                            new Box
                            {
                                RelativeSizeAxes = Axes.Y,
                                Height = 0.68f,
                                Width = 1,
                                Anchor = Anchor.CentreRight,
                                Origin = Anchor.CentreRight,
                                Margin = new MarginPadding { Right = 4.5f },
                                Colour = EditorColours.Divider.Opacity(0.22f)
                            }
                        }
                        : new Drawable[]
                        {
                            sections[i].Section
                        }
                };

                timelineToolboxSectionWrappers.Add((wrapper, hasTrailingGap));
                rowChildren[i] = wrapper;
            }

            var rowGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize)
                },
                ColumnDimensions = sections.Select(section => new Dimension(GridSizeMode.Relative, section.Weight)).ToArray(),
                Content = new[]
                {
                    rowChildren
                }
            };

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 10,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.Mix(EditorColours.TimelineToolbarBackground, EditorColours.ControlsBackground, 0.22f)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 40f,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.TopLeft,
                        Colour = ColourInfo.GradientVertical(
                            EditorColours.PanelStroke.Opacity(0.16f),
                            Color4.Transparent)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.09f
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Width = 1f,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding { Horizontal = 1f },
                        Child = rowGrid
                    }
                }
            };
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
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Full,
                Spacing = new Vector2(8, 0),
                Children = controls
            };
            timelineSectionControlRows.Add(controlsRow);

            var sectionBody = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
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
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Child = sectionBody
            };
        }

        private Drawable createTimelineSliderSection(
            string title,
            SpriteText valueText,
            Drawable sliderContainer,
            Action decreaseAction,
            Action increaseAction,
            Action resetAction,
            Drawable? footerContent = null)
        {
            var titleText = new SpriteText
            {
                Text = title,
                Font = BeatSightFont.Caption(12.4f),
                Colour = EditorColours.TextSecondary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };
            timelineSectionTitleTexts.Add(titleText);

            valueText.Anchor = Anchor.CentreRight;
            valueText.Origin = Anchor.CentreRight;
            valueText.Colour = EditorColours.TextPrimary;

            var headerRow = new Container
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                Height = 16f,
                Children = new Drawable[]
                {
                    titleText,
                    valueText
                }
            };

            var controlsRow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Full,
                Spacing = new Vector2(8, 0),
                Children = new Drawable[]
                {
                    createTimelineMiniButton("-", decreaseAction, 32),
                    sliderContainer,
                    createTimelineMiniButton("+", increaseAction, 32),
                    createTimelineMiniButton("Reset", resetAction, 58)
                }
            };
            timelineSectionControlRows.Add(controlsRow);

            Drawable[] bodyChildren = footerContent == null
                ? new Drawable[]
                {
                    headerRow,
                    controlsRow
                }
                : new Drawable[]
                {
                    headerRow,
                    controlsRow,
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Width = 1f,
                        AutoSizeAxes = Axes.Y,
                        Child = footerContent
                    }
                };

            var sectionBody = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6, 5),
                Padding = new MarginPadding { Horizontal = 11, Vertical = 8 },
                Children = bodyChildren
            };
            timelineSectionBodies.Add(sectionBody);

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Child = sectionBody
            };
        }

        private BasicButton createTimelineMiniButton(string text, Action action, float width = 36)
        {
            var button = new BasicButton
            {
                Size = new Vector2(width, 32),
                BackgroundColour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.18f),
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
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
            syncPlaybackRateDisplay();
            syncPlaybackZoomDisplay();
            syncNoteWidthScaleDisplay();
            syncSnapControl();
            syncBeatGridControl();
            syncTimelineZoomLinkControl();
            if (linkTimelineAndPlaybackZoom)
                syncLinkedPlaybackZoomFromTimeline();
            syncTimelineMetronomeButton();
            refreshTimelineLaneEditorControls();
            syncTimelineToolboxCollapseToggle();
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
            syncTimelineZoomDisplay();
            syncLinkedPlaybackZoomFromTimeline();
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
            playbackPreview?.ForceVisualLayoutRefresh();
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
            syncLinkedPlaybackZoomFromTimeline();
            commitTimelineZoomChange();
            playbackPreview?.ForceVisualLayoutRefresh();
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

        private void setPlaybackRate(double rate, bool announce = true)
        {
            double clamped = Math.Clamp(rate, minPlaybackRate, maxPlaybackRate);
            bool changed = Math.Abs(clamped - playbackRate) >= 0.0001;
            playbackRate = clamped;

            applyTrackPlaybackRate();
            syncPlaybackRateDisplay();

            if (announce && changed)
                appendStatusDetail($"Playback rate {playbackRate:0.00}x");
        }

        private void syncPlaybackRateDisplay()
        {
            if (playbackRateValueText != null)
                playbackRateValueText.Text = $"{playbackRate:0.00}x";

            if (playbackRateSlider != null)
            {
                suppressPlaybackRateSync = true;
                playbackRateSlider.Current.Value = playbackRate;
                suppressPlaybackRateSync = false;
            }
        }

        private void syncPlaybackZoomDisplay()
        {
            double clamped = Math.Clamp(playbackZoomSetting?.Value ?? 1.0, editorPlaybackZoomMin, editorPlaybackZoomMax);
            updatePlaybackZoomValueText(clamped);

            if (playbackZoomSlider != null)
            {
                suppressPlaybackZoomSync = true;
                playbackZoomSlider.Current.Value = clamped;
                suppressPlaybackZoomSync = false;
            }
        }

        private void updatePlaybackZoomValueText(double value)
        {
            if (playbackZoomValueText != null)
                playbackZoomValueText.Text = $"{value:0.00}x";
        }

        private void syncNoteWidthScaleDisplay()
        {
            double clamped = Math.Clamp(noteWidthSetting?.Value ?? 1.0, 0.5, 1.5);
            if (noteWidthValueText != null)
                noteWidthValueText.Text = $"{clamped:0.00}x";

            if (noteWidthSlider != null)
            {
                suppressNoteWidthSync = true;
                noteWidthSlider.Current.Value = clamped;
                suppressNoteWidthSync = false;
            }
        }

        private void adjustPlaybackRate(bool increase)
            => setPlaybackRate(playbackRate + (increase ? 0.05 : -0.05));

        private void resetPlaybackRate()
            => setPlaybackRate(1.0);

        private void adjustPlaybackZoomScale(bool increase)
        {
            double current = playbackZoomSetting?.Value ?? 1.0;
            setPlaybackZoomScale(current + (increase ? 0.05 : -0.05));
        }

        private void adjustNoteWidthScale(bool increase)
        {
            double current = noteWidthSetting?.Value ?? 1.0;
            setNoteWidthScale(current + (increase ? 0.05 : -0.05));
        }

        private void setPlaybackZoomScale(double scale, bool announce = true)
        {
            if (playbackZoomSetting == null)
                return;

            double clamped = Math.Clamp(scale, editorPlaybackZoomMin, editorPlaybackZoomMax);
            bool changed = Math.Abs(clamped - playbackZoomSetting.Value) >= 0.0001;
            if (!changed)
            {
                syncPlaybackZoomDisplay();
                return;
            }

            playbackZoomSetting.Value = clamped;
            syncPlaybackZoomDisplay();

            if (announce)
                appendStatusDetail($"Playback zoom {clamped:0.00}x");
        }

        private void beginPlaybackZoomInteraction()
        {
            if (playbackZoomInteractionActive)
                return;

            playbackZoomInteractionActive = true;
            playbackZoomInteractionDirty = false;
            pendingPlaybackZoomPreview = null;
            lastPlaybackZoomPreviewAppliedAt = double.NegativeInfinity;

            if (linkTimelineAndPlaybackZoom && !timelineZoomInteractionActive)
                beginTimelineZoomInteraction();
        }

        private void previewPlaybackZoom(double scale)
        {
            double clamped = Math.Clamp(scale, editorPlaybackZoomMin, editorPlaybackZoomMax);
            if (playbackZoomSetting == null)
            {
                updatePlaybackZoomValueText(clamped);
                return;
            }

            double now = Time.Current;
            if (now - lastPlaybackZoomPreviewAppliedAt < playbackZoomPreviewMinIntervalMs)
            {
                pendingPlaybackZoomPreview = clamped;
                playbackZoomInteractionDirty = true;
                updatePlaybackZoomValueText(clamped);
                return;
            }

            applyPlaybackZoomPreviewNow(clamped, now);
        }

        private void applyPlaybackZoomPreviewNow(double scale, double timestamp)
        {
            double clamped = Math.Clamp(scale, editorPlaybackZoomMin, editorPlaybackZoomMax);
            if (playbackZoomSetting != null && Math.Abs(playbackZoomSetting.Value - clamped) >= 0.0001)
                playbackZoomSetting.Value = clamped;
            else
                updatePlaybackZoomValueText(clamped);

            playbackZoomInteractionDirty = true;
            lastPlaybackZoomPreviewAppliedAt = timestamp;
            pendingPlaybackZoomPreview = null;
        }

        private void endPlaybackZoomInteraction()
        {
            if (!playbackZoomInteractionActive)
                return;

            if (pendingPlaybackZoomPreview.HasValue)
                applyPlaybackZoomPreviewNow(pendingPlaybackZoomPreview.Value, Time.Current);

            playbackZoomInteractionActive = false;
            pendingPlaybackZoomPreview = null;

            if (linkTimelineAndPlaybackZoom)
                endTimelineZoomInteraction();

            if (!playbackZoomInteractionDirty)
            {
                syncPlaybackZoomDisplay();
                return;
            }

            playbackZoomInteractionDirty = false;
            syncPlaybackZoomDisplay();
            playbackPreview?.ForceVisualLayoutRefresh();
        }

        private void setNoteWidthScale(double scale, bool announce = true)
        {
            if (noteWidthSetting == null)
                return;

            double clamped = Math.Clamp(scale, 0.5, 1.5);
            bool changed = Math.Abs(clamped - noteWidthSetting.Value) >= 0.0001;
            if (!changed)
            {
                syncNoteWidthScaleDisplay();
                return;
            }

            noteWidthSetting.Value = clamped;
            syncNoteWidthScaleDisplay();

            if (announce)
                appendStatusDetail($"Note width {clamped:0.00}x");
        }

        private void applyTrackPlaybackRate()
        {
            if (track == null)
                return;

            try
            {
                if (playbackRate < 0.05)
                {
                    track.Tempo.Value = 0.05;
                    track.Frequency.Value = playbackRate / 0.05;
                }
                else
                {
                    track.Frequency.Value = 1.0;
                    track.Tempo.Value = playbackRate;
                }
            }
            catch
            {
                track.Tempo.Value = Math.Max(0.05, playbackRate);
            }
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
            syncTimelineSnapForCurrentTime(force: true);

            if (beatmap != null)
            {
                var editorInfo = ensureEditorInfo();
                editorInfo.SnapDivisor = snapDivisor;
            }

            playbackPreview?.RefreshBeatmap();

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

        private void setTimelineZoomLink(bool linked, bool announce = true)
        {
            if (linkTimelineAndPlaybackZoom == linked)
            {
                syncTimelineZoomLinkControl();
                return;
            }

            linkTimelineAndPlaybackZoom = linked;
            syncTimelineZoomLinkControl();

            if (linkTimelineAndPlaybackZoom)
                syncLinkedPlaybackZoomFromTimeline();

            persistEditorDefaults();

            if (announce)
                appendStatusDetail(linked ? "Timeline/playback zoom linked" : "Timeline/playback zoom unlinked");
        }

        private void syncTimelineZoomLinkControl()
        {
            if (timelineLinkZoomCheckbox == null)
                return;

            suppressTimelineZoomLinkSync = true;
            timelineLinkZoomCheckbox.Current.Value = linkTimelineAndPlaybackZoom;
            suppressTimelineZoomLinkSync = false;
        }

        private void syncLinkedPlaybackZoomFromTimeline()
        {
            if (!linkTimelineAndPlaybackZoom || suppressLinkedZoomPropagation)
                return;

            suppressLinkedZoomPropagation = true;
            setPlaybackZoomScale(mapTimelineZoomToPlaybackZoom(timelineZoom), announce: false);
            suppressLinkedZoomPropagation = false;
        }

        private void syncLinkedTimelineZoomFromPlayback(bool preview = false)
        {
            if (!linkTimelineAndPlaybackZoom || suppressLinkedZoomPropagation)
                return;

            double mappedTimelineZoom = mapPlaybackZoomToTimelineZoom(playbackZoomSetting?.Value ?? 1.0);

            suppressLinkedZoomPropagation = true;
            if (preview)
                previewTimelineZoom(mappedTimelineZoom);
            else
                applyTimelineZoom(mappedTimelineZoom);
            suppressLinkedZoomPropagation = false;
        }

        private double mapTimelineZoomToPlaybackZoom(double zoom)
        {
            // Linked mode should preserve visible future-time window between timeline and playfield.
            // Range-only mapping can drift because each surface applies different zoom curves.
            return mapZoomByViewportDurationProgress(
                sourceZoom: zoom,
                sourceMin: EditorTimeline.MinZoom,
                sourceMax: EditorTimeline.MaxZoom,
                sourceDurationResolver: tryResolveTimelineFutureViewportDuration,
                targetMin: editorPlaybackZoomMin,
                targetMax: editorPlaybackZoomMax,
                targetDurationResolver: tryResolvePlaybackFutureViewportDuration);
        }

        private double mapPlaybackZoomToTimelineZoom(double zoom)
        {
            return mapZoomByViewportDurationProgress(
                sourceZoom: zoom,
                sourceMin: editorPlaybackZoomMin,
                sourceMax: editorPlaybackZoomMax,
                sourceDurationResolver: tryResolvePlaybackFutureViewportDuration,
                targetMin: EditorTimeline.MinZoom,
                targetMax: EditorTimeline.MaxZoom,
                targetDurationResolver: tryResolveTimelineFutureViewportDuration);
        }

        private double? tryResolveTimelineFutureViewportDuration(double zoom)
        {
            if (timeline == null)
                return null;

            double clampedZoom = Math.Clamp(zoom, EditorTimeline.MinZoom, EditorTimeline.MaxZoom);
            double durationMs = timeline.GetFutureViewportDurationMsAtZoom(clampedZoom);
            return double.IsFinite(durationMs) && durationMs > 0.01 ? durationMs : null;
        }

        private double? tryResolvePlaybackFutureViewportDuration(double zoom)
        {
            if (playbackPreview == null)
                return null;

            double clampedZoom = Math.Clamp(zoom, editorPlaybackZoomMin, editorPlaybackZoomMax);
            double durationMs = playbackPreview.GetFutureViewportDurationMsAtZoom(clampedZoom);
            return double.IsFinite(durationMs) && durationMs > 0.01 ? durationMs : null;
        }

        private static double mapZoomByViewportDurationProgress(
            double sourceZoom,
            double sourceMin,
            double sourceMax,
            Func<double, double?> sourceDurationResolver,
            double targetMin,
            double targetMax,
            Func<double, double?> targetDurationResolver)
        {
            double fallback = mapZoomByRange(
                value: sourceZoom,
                sourceMin: sourceMin,
                sourceMax: sourceMax,
                targetMin: targetMin,
                targetMax: targetMax);

            double clampedSourceZoom = Math.Clamp(sourceZoom, Math.Min(sourceMin, sourceMax), Math.Max(sourceMin, sourceMax));
            const double zoomEndpointEpsilon = 0.01;
            const double rangeIdentityEpsilon = 0.0001;

            // If ranges are effectively identical, preserve zoom value identity in linked mode.
            // This avoids surprising divergence like timeline=5.00x mapping to a much lower playback zoom.
            if (Math.Abs(sourceMin - targetMin) <= rangeIdentityEpsilon
                && Math.Abs(sourceMax - targetMax) <= rangeIdentityEpsilon)
            {
                return Math.Clamp(clampedSourceZoom, Math.Min(targetMin, targetMax), Math.Max(targetMin, targetMax));
            }

            // Preserve endpoint identity in linked mode:
            // source min must map to target min and source max must map to target max.
            if (Math.Abs(clampedSourceZoom - sourceMin) <= zoomEndpointEpsilon)
                return targetMin;

            if (Math.Abs(clampedSourceZoom - sourceMax) <= zoomEndpointEpsilon)
                return targetMax;

            double? sourceDurationAtZoom = sourceDurationResolver(clampedSourceZoom);
            double? sourceDurationAtMin = sourceDurationResolver(sourceMin);
            double? sourceDurationAtMax = sourceDurationResolver(sourceMax);
            double? targetDurationAtMin = targetDurationResolver(targetMin);
            double? targetDurationAtMax = targetDurationResolver(targetMax);

            if (!sourceDurationAtZoom.HasValue
                || !sourceDurationAtMin.HasValue
                || !sourceDurationAtMax.HasValue
                || !targetDurationAtMin.HasValue
                || !targetDurationAtMax.HasValue)
                return fallback;

            double sourceSpan = sourceDurationAtMax.Value - sourceDurationAtMin.Value;
            if (!double.IsFinite(sourceSpan) || Math.Abs(sourceSpan) <= 0.0001)
                return fallback;

            double progress = Math.Clamp((sourceDurationAtZoom.Value - sourceDurationAtMin.Value) / sourceSpan, 0, 1);
            if (!double.IsFinite(progress))
                return fallback;

            if (progress <= zoomEndpointEpsilon)
                return targetMin;

            if (progress >= 1 - zoomEndpointEpsilon)
                return targetMax;

            double targetDuration = targetDurationAtMin.Value
                + (targetDurationAtMax.Value - targetDurationAtMin.Value) * progress;

            return mapProgressToZoomByDuration(
                targetDuration: targetDuration,
                targetZoomMin: targetMin,
                targetZoomMax: targetMax,
                durationResolver: targetDurationResolver,
                fallbackZoom: fallback);
        }

        private static double mapProgressToZoomByDuration(
            double targetDuration,
            double targetZoomMin,
            double targetZoomMax,
            Func<double, double?> durationResolver,
            double fallbackZoom)
        {
            double? durationAtMinZoom = durationResolver(targetZoomMin);
            double? durationAtMaxZoom = durationResolver(targetZoomMax);
            if (!durationAtMinZoom.HasValue || !durationAtMaxZoom.HasValue)
                return fallbackZoom;

            double lowerDuration = Math.Min(durationAtMinZoom.Value, durationAtMaxZoom.Value);
            double upperDuration = Math.Max(durationAtMinZoom.Value, durationAtMaxZoom.Value);
            double boundedTargetDuration = Math.Clamp(targetDuration, lowerDuration, upperDuration);

            double durationSpan = Math.Abs(durationAtMaxZoom.Value - durationAtMinZoom.Value);
            double endpointDurationEpsilon = Math.Max(0.5, durationSpan * 0.01);

            if (Math.Abs(boundedTargetDuration - durationAtMinZoom.Value) <= endpointDurationEpsilon)
                return targetZoomMin;

            if (Math.Abs(boundedTargetDuration - durationAtMaxZoom.Value) <= endpointDurationEpsilon)
                return targetZoomMax;

            bool increasingWithZoom = durationAtMaxZoom.Value >= durationAtMinZoom.Value;
            double lowZoom = Math.Min(targetZoomMin, targetZoomMax);
            double highZoom = Math.Max(targetZoomMin, targetZoomMax);

            for (int i = 0; i < 22; i++)
            {
                double midZoom = (lowZoom + highZoom) * 0.5;
                double? midDuration = durationResolver(midZoom);
                if (!midDuration.HasValue)
                    return fallbackZoom;

                if (increasingWithZoom)
                {
                    if (midDuration.Value < boundedTargetDuration)
                        lowZoom = midZoom;
                    else
                        highZoom = midZoom;
                }
                else
                {
                    if (midDuration.Value > boundedTargetDuration)
                        lowZoom = midZoom;
                    else
                        highZoom = midZoom;
                }
            }

            double resolvedZoom = (lowZoom + highZoom) * 0.5;
            return Math.Clamp(resolvedZoom, Math.Min(targetZoomMin, targetZoomMax), Math.Max(targetZoomMin, targetZoomMax));
        }

        private static double mapZoomByRange(
            double value,
            double sourceMin,
            double sourceMax,
            double targetMin,
            double targetMax)
        {
            double sourceRange = sourceMax - sourceMin;
            if (!double.IsFinite(sourceRange) || Math.Abs(sourceRange) <= 0.0001)
                return Math.Clamp(targetMin, Math.Min(targetMin, targetMax), Math.Max(targetMin, targetMax));

            double clamped = Math.Clamp(value, Math.Min(sourceMin, sourceMax), Math.Max(sourceMin, sourceMax));
            double normalized = Math.Clamp((clamped - sourceMin) / sourceRange, 0, 1);
            double mapped = targetMin + (targetMax - targetMin) * normalized;
            return Math.Clamp(mapped, Math.Min(targetMin, targetMax), Math.Max(targetMin, targetMax));
        }

        private void toggleTimelineToolboxCollapsed()
            => setTimelineToolboxCollapsed(!timelineToolboxCollapsed);

        private void setTimelineToolboxCollapsed(bool collapsed)
        {
            if (timelineToolboxCollapsed == collapsed)
            {
                syncTimelineToolboxCollapseToggle();
                return;
            }

            var viewport = resolveResponsiveViewport();
            var metrics = EditorResponsiveLayout.Compute(viewport.X, viewport.Y, inspectorStackedLayout, footerTipsCollapsed);
            bool hasViewport = viewport.X > 0 && viewport.Y > 0;

            if (hasViewport)
            {
                float currentTopHeight = resolveTimelineTopHeight(metrics, viewport);
                persistTimelineSplitRatioForState(timelineToolboxCollapsed, currentTopHeight, metrics, viewport);
            }

            int animationVersion = ++timelineToolboxAnimationVersion;
            timelineToolboxCollapsed = collapsed;
            timelineTopHeightOverride = hasViewport
                ? resolveTimelineTopHeightForState(metrics, viewport, timelineToolboxCollapsed)
                : null;
            timelineToolboxAnimationInProgress = true;
            syncTimelineToolboxCollapseToggle();

            if (timelineToolboxHostContainer != null)
            {
                timelineToolboxHostContainer.ClearTransforms();
                timelineToolboxHostContainer.Show();
                timelineToolboxHostContainer.AlwaysPresent = true;
                timelineToolboxHostContainer.Masking = true;
                enforceTimelineToolboxHostManualSizing();

                if (collapsed)
                {
                    float currentHeight = timelineToolboxHostContainer.DrawHeight > 1
                        ? timelineToolboxHostContainer.DrawHeight
                        : resolveTimelineToolboxExpandedHeight();
                    float collapsedHeight = resolveTimelineToolboxCollapsedHeight(viewport);

                    setTimelineToolboxHostHeightSafely(currentHeight);

                    if (timelineToolboxContainer != null)
                    {
                        timelineToolboxContainer.Show();
                        timelineToolboxContainer.AlwaysPresent = true;
                        timelineToolboxContainer.ClearTransforms();
                        timelineToolboxContainer.Alpha = 1f;
                        timelineToolboxContainer.Y = 0f;
                    }

                    resizeTimelineToolboxHostHeightSafely(collapsedHeight, 190, Easing.OutQuint);
                    Scheduler.AddDelayed(() =>
                    {
                        if (animationVersion != timelineToolboxAnimationVersion)
                            return;

                        if (!timelineToolboxCollapsed || timelineToolboxHostContainer == null)
                            return;

                        timelineToolboxHostContainer.Show();
                        timelineToolboxHostContainer.AlwaysPresent = true;
                        setTimelineToolboxHostHeightSafely(collapsedHeight);
                        timelineToolboxAnimationInProgress = false;
                    }, 204);
                }
                else
                {
                    float expandedHeight = resolveTimelineToolboxExpandedHeight();
                    setTimelineToolboxHostHeightSafely(0);
                    resizeTimelineToolboxHostHeightSafely(expandedHeight, 210, Easing.OutQuint);

                    if (timelineToolboxContainer != null)
                    {
                        timelineToolboxContainer.Show();
                        timelineToolboxContainer.AlwaysPresent = true;
                        timelineToolboxContainer.ClearTransforms();
                        timelineToolboxContainer.Alpha = 0;
                        timelineToolboxContainer.Y = -10;
                        timelineToolboxContainer.FadeIn(175, Easing.OutQuint);
                        timelineToolboxContainer.MoveToY(0, 190, Easing.OutQuint);
                    }

                    Scheduler.AddDelayed(() =>
                    {
                        if (animationVersion != timelineToolboxAnimationVersion)
                            return;

                        if (timelineToolboxCollapsed || timelineToolboxHostContainer == null)
                            return;

                        timelineToolboxHostContainer.ClearTransforms();
                        setTimelineToolboxHostHeightSafely(resolveTimelineToolboxExpandedHeight());
                        timelineToolboxAnimationInProgress = false;
                    }, 220);
                }
            }
            else
            {
                timelineToolboxAnimationInProgress = false;
            }

            applyResponsiveEditorLayout(force: true);
            playbackPreview?.ForceVisualLayoutRefresh();
        }

        private void syncTimelineToolboxCollapseToggle()
        {
            if (timelineToolboxToggleButton == null)
                return;

            bool collapsed = timelineToolboxCollapsed;
            timelineToolboxToggleButton.SetLabel(collapsed ? "Show" : "Hide");
            timelineToolboxToggleButton.UpdateState(true, collapsed ? "Show timeline toolbar." : "Hide timeline toolbar.");
            timelineToolboxToggleButton.FadeTo(collapsed ? 0.74f : 0.62f, 140, Easing.OutQuint);
        }

        private void applyTimelineToolboxDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            float sectionTitleFont = blend(12.1f, 10.9f, compactBlend) + ultraWideRelax * 0.25f;
            float sectionPaddingH = blend(9.4f, 7.8f, compactBlend) + ultraWideRelax * 1.0f;
            float sectionPaddingV = blend(5.8f, 4.9f, compactBlend) + ultraWideRelax * 0.22f;
            float sectionVerticalSpacing = blend(4.2f, 3.6f, compactBlend) + ultraWideRelax * 0.22f;
            float sectionLabelSpacing = blend(7.2f, 5.9f, compactBlend) + ultraWideRelax * 0.85f;
            float sliderHeight = blend(29f, 25.5f, compactBlend);
            float miniButtonHeight = blend(32f, 28f, compactBlend);
            float miniButtonFont = blend(11.9f, 10.8f, compactBlend) + ultraWideRelax * 0.2f;
            bool ultraCompactControls = compactBlend >= 0.72f && viewport.X <= 1460f;

            if (timelineToolboxInnerContainer != null)
            {
                timelineToolboxInnerContainer.Padding = new MarginPadding
                {
                    Left = blend(10f, 8f, compactBlend),
                    Right = blend(10f, 8f, compactBlend),
                    Top = blend(2.2f, 1.8f, compactBlend),
                    Bottom = blend(6.4f, 5.2f, compactBlend)
                };
            }

            if (timelineToolboxContentFlow != null)
                timelineToolboxContentFlow.Spacing = new Vector2(
                    blend(10f, 8.5f, compactBlend) + ultraWideRelax * 1.0f,
                    blend(7f, 5f, compactBlend));

            float sectionGap = blend(8.6f, 5.5f, compactBlend) + ultraWideRelax * 0.7f;
            foreach (var (wrapper, hasTrailingGap) in timelineToolboxSectionWrappers)
                wrapper.Padding = new MarginPadding { Right = hasTrailingGap ? sectionGap : 0f };

            if (timelineZoomSliderContainer != null)
            {
                timelineZoomSliderContainer.Width = blend(170f, 145f, compactBlend);
                timelineZoomSliderContainer.Height = sliderHeight;
            }

            if (timelineWaveformSliderContainer != null)
            {
                timelineWaveformSliderContainer.Width = blend(154f, 130f, compactBlend);
                timelineWaveformSliderContainer.Height = sliderHeight;
            }

            if (timelinePlaybackRateSliderContainer != null)
            {
                timelinePlaybackRateSliderContainer.Width = blend(144f, 116f, compactBlend);
                timelinePlaybackRateSliderContainer.Height = sliderHeight;
            }

            if (timelinePlaybackZoomSliderContainer != null)
            {
                timelinePlaybackZoomSliderContainer.Width = blend(144f, 116f, compactBlend);
                timelinePlaybackZoomSliderContainer.Height = sliderHeight;
            }

            if (timelineNoteWidthSliderContainer != null)
            {
                timelineNoteWidthSliderContainer.Width = blend(144f, 116f, compactBlend);
                timelineNoteWidthSliderContainer.Height = sliderHeight;
            }

            foreach (var body in timelineSectionBodies)
            {
                body.Spacing = new Vector2(0, sectionVerticalSpacing);
                body.Padding = new MarginPadding
                {
                    Horizontal = sectionPaddingH,
                    Top = Math.Max(4f, sectionPaddingV - 1.3f),
                    Bottom = sectionPaddingV
                };
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

            if (timelineFirstNoteButton != null)
                timelineFirstNoteButton.Width = blend(98f, 74f, compactBlend);
            if (timelineLastNoteButton != null)
                timelineLastNoteButton.Width = blend(96f, 72f, compactBlend);
            if (timelineTimingButton != null)
                timelineTimingButton.Width = blend(92f, 78f, compactBlend);
            if (timelineMetronomeButton != null)
                timelineMetronomeButton.Width = blend(104f, 84f, compactBlend);
            if (timelineSnapAudioButton != null)
                timelineSnapAudioButton.Width = blend(110f, 86f, compactBlend);
            if (timelineRegenerateButton != null)
                timelineRegenerateButton.Width = blend(108f, 90f, compactBlend);

            if (timelineFirstNoteButtonText != null)
                timelineFirstNoteButtonText.Text = ultraCompactControls ? "First" : "First Note";
            if (timelineLastNoteButtonText != null)
                timelineLastNoteButtonText.Text = ultraCompactControls ? "Last" : "Last Note";
            if (timelineSnapAudioButtonText != null)
                timelineSnapAudioButtonText.Text = ultraCompactControls ? "Snap" : "Snap Audio";
            if (timelineRegenerateButtonText != null)
                timelineRegenerateButtonText.Text = ultraCompactControls ? "Regen" : "Regenerate";

            if (timelineZoomValueText != null)
                timelineZoomValueText.Font = BeatSightFont.Caption(blend(11.8f, 10.8f, compactBlend));

            if (waveformScaleValueText != null)
                waveformScaleValueText.Font = BeatSightFont.Caption(blend(11.8f, 10.8f, compactBlend));

            if (playbackRateValueText != null)
                playbackRateValueText.Font = BeatSightFont.Caption(blend(11.8f, 10.8f, compactBlend));

            if (playbackZoomValueText != null)
                playbackZoomValueText.Font = BeatSightFont.Caption(blend(11.8f, 10.8f, compactBlend));

            if (noteWidthValueText != null)
                noteWidthValueText.Font = BeatSightFont.Caption(blend(11.8f, 10.8f, compactBlend));

            if (snapDivisorText != null)
                snapDivisorText.Font = BeatSightFont.Title(blend(12.8f, 11.6f, compactBlend));

            if (timelineLinkZoomCheckbox != null)
                timelineLinkZoomCheckbox.LabelFontSize = blend(11.8f, 10.8f, compactBlend);

            if (timelineToolboxToggleButton != null)
            {
                timelineToolboxToggleButton.Height = blend(32f, 28f, compactBlend);
                timelineToolboxToggleButton.SetContentDensity(
                    blend(11.6f, 10.6f, compactBlend),
                    blend(7.4f, 6.6f, compactBlend));
            }

            float previewUtilityHeight = blend(38f, 34f, compactBlend);
            if (previewUtilityStripContainer != null)
                previewUtilityStripContainer.Height = previewUtilityHeight;

            if (previewUtilityTitleText != null)
                previewUtilityTitleText.Font = BeatSightFont.Section(blend(11.8f, 10.8f, compactBlend));

            if (previewUtilityHintText != null)
                previewUtilityHintText.Font = BeatSightFont.Caption(blend(9.9f, 9.0f, compactBlend));

            if (inspectorToggleButton != null)
            {
                inspectorToggleButton.Size = new Vector2(
                    blend(130f, 116f, compactBlend),
                    blend(30f, 28f, compactBlend));
                inspectorToggleButton.SetContentDensity(
                    blend(11.4f, 10.3f, compactBlend),
                    blend(7.2f, 6.2f, compactBlend));
            }

            if (previewContentContainer != null)
            {
                previewContentContainer.Padding = new MarginPadding
                {
                    Left = blend(8f, 7f, compactBlend),
                    Right = blend(8f, 7f, compactBlend),
                    Top = previewUtilityHeight + blend(3f, 2f, compactBlend),
                    Bottom = blend(4f, 3f, compactBlend)
                };
            }

            syncTimelineToolboxHostHeightToContent();
        }

        private void syncTimelineToolboxHostHeightToContent()
        {
            if (timelineToolboxHostContainer == null)
                return;

            if (timelineToolboxAnimationInProgress)
                return;

            enforceTimelineToolboxHostManualSizing();

            if (timelineToolboxCollapsed)
            {
                setTimelineToolboxHostHeightSafely(resolveTimelineToolboxCollapsedHeight(resolveResponsiveViewport()));
                return;
            }

            float expandedHeight = resolveTimelineToolboxExpandedHeight();
            if (Math.Abs(timelineToolboxHostContainer.Height - expandedHeight) > 0.2f)
                setTimelineToolboxHostHeightSafely(expandedHeight);
        }

        private void enforceTimelineToolboxHostManualSizing()
        {
            if (timelineToolboxHostContainer == null)
                return;

            if (timelineToolboxHostContainer.AutoSizeAxes != Axes.None)
                timelineToolboxHostContainer.AutoSizeAxes = Axes.None;
        }

        private void setTimelineToolboxHostHeightSafely(float height)
        {
            if (timelineToolboxHostContainer == null)
                return;

            enforceTimelineToolboxHostManualSizing();

            try
            {
                timelineToolboxHostContainer.Height = height;
            }
            catch (InvalidOperationException)
            {
                timelineToolboxHostContainer.AutoSizeAxes = Axes.None;
                timelineToolboxHostContainer.ClearTransforms();
                timelineToolboxHostContainer.ResizeHeightTo(height, 0);
            }
        }

        private void resizeTimelineToolboxHostHeightSafely(float height, double duration, Easing easing)
        {
            if (timelineToolboxHostContainer == null)
                return;

            enforceTimelineToolboxHostManualSizing();

            try
            {
                timelineToolboxHostContainer.ResizeHeightTo(height, duration, easing);
            }
            catch (InvalidOperationException)
            {
                timelineToolboxHostContainer.AutoSizeAxes = Axes.None;
                timelineToolboxHostContainer.Height = height;
            }
        }
    }
}
