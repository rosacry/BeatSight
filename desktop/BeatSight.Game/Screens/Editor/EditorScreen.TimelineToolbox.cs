using System;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osuTK;

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

            playbackRateValueText = new SpriteText
            {
                Text = $"{playbackRate:0.00}x",
                Font = BeatSightFont.Caption(11.8f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
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
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Child = playbackRateSlider
            };
            timelinePlaybackRateSliderContainer = playbackRateSliderContainer;

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

            var playbackSection = createTimelineSection("Playback",
                createTimelineMiniButton("-", () => adjustPlaybackRate(false), 32),
                playbackRateSliderContainer,
                createTimelineMiniButton("+", () => adjustPlaybackRate(true), 32),
                createTimelineMiniButton("Reset", resetPlaybackRate, 58),
                playbackRateValueText);

            var snapSection = createTimelineSection(timelineCopy.SectionSnap,
                createTimelineMiniButton("-", () => adjustSnapDivisor(false), 32),
                snapDivisorText,
                createTimelineMiniButton("+", () => adjustSnapDivisor(true), 32));

            var gridSection = createTimelineSection(timelineCopy.SectionOverlay, beatGridCheckbox);

            var firstNoteButton = createTimelineMiniButton(timelineCopy.FirstNoteButton, jumpToFirstNote, 98);
            timelineFirstNoteButton = firstNoteButton;
            timelineFirstNoteButtonText = timelineMiniButtonTexts[^1];

            var lastNoteButton = createTimelineMiniButton(timelineCopy.LastNoteButton, jumpToLastNote, 96);
            timelineLastNoteButton = lastNoteButton;
            timelineLastNoteButtonText = timelineMiniButtonTexts[^1];

            var timingButton = createTimelineMiniButton("Timing", openTimingSetupOverlay, 92);
            timelineTimingButton = timingButton;

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
                snapSelectionButton,
                regenerateButton);

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
                    playbackSection,
                    snapSection,
                    gridSection,
                    toolsSection
                }
            };
            timelineToolboxContentFlow = contentFlow;

            var horizontalScroll = new PassiveScrollContainer(Direction.Horizontal)
            {
                RelativeSizeAxes = Axes.Both,
                ScrollbarVisible = true,
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
            syncPlaybackRateDisplay();
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

        private void adjustPlaybackRate(bool increase)
            => setPlaybackRate(playbackRate + (increase ? 0.05 : -0.05));

        private void resetPlaybackRate()
            => setPlaybackRate(1.0);

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

        private void applyTimelineToolboxDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            float sectionTitleFont = blend(12.4f, 11.1f, compactBlend) + ultraWideRelax * 0.3f;
            float sectionPaddingH = blend(11f, 9f, compactBlend) + ultraWideRelax * 1.2f;
            float sectionPaddingV = blend(8f, 7f, compactBlend) + ultraWideRelax * 0.45f;
            float sectionVerticalSpacing = blend(6f, 5f, compactBlend) + ultraWideRelax * 0.55f;
            float sectionLabelSpacing = blend(8f, 5.8f, compactBlend) + ultraWideRelax * 1.05f;
            float sliderHeight = blend(30f, 26f, compactBlend);
            float miniButtonHeight = blend(32f, 28f, compactBlend);
            float miniButtonFont = blend(11.9f, 10.8f, compactBlend) + ultraWideRelax * 0.2f;
            bool ultraCompactControls = compactBlend >= 0.72f && viewport.X <= 1460f;

            if (timelineToolboxContainer != null)
            {
                timelineToolboxContainer.Padding = new MarginPadding
                {
                    Horizontal = blend(13f, 10f, compactBlend),
                    Vertical = blend(10f, 8f, compactBlend)
                };
            }

            if (timelineToolboxContentFlow != null)
                timelineToolboxContentFlow.Spacing = new Vector2(blend(12f, 8.5f, compactBlend) + ultraWideRelax * 1.3f, 0);

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

            if (timelineFirstNoteButton != null)
                timelineFirstNoteButton.Width = blend(98f, 74f, compactBlend);
            if (timelineLastNoteButton != null)
                timelineLastNoteButton.Width = blend(96f, 72f, compactBlend);
            if (timelineTimingButton != null)
                timelineTimingButton.Width = blend(92f, 78f, compactBlend);
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
    }
}
