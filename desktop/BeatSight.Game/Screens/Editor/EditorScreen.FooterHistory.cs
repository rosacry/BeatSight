using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createFooter()
        {
            footerKeyTexts.Clear();
            footerActionTexts.Clear();

            FillFlowContainer? tipFlow = null;
            if (showFooterShortcutHints)
            {
                var tips = new (string key, string action)[]
                {
                    ("Esc", "Clear selection / Back"),
                    ("Space", "Play/Pause"),
                    ("Shift+Space", "Rewind to start"),
                    ("Ctrl+[ / Ctrl+]", "Playback rate"),
                    ("Ctrl+0", "Reset playback rate"),
                    ("Ctrl+T", "Open timing setup"),
                    ("Left/Right", "Seek"),
                    ("Mouse Wheel", "Scrub timeline (Shift = faster)"),
                    ("Seek Bar", "Click/drag to scrub"),
                    ("Ctrl +/-", "Zoom timeline"),
                    ("Alt +/-", "Scale UI"),
                    ("Ctrl+Alt +/-", "Scale waveform"),
                    ("[ / ]", "Change snap"),
                    ("G", "Toggle beat grid"),
                    ("I", "Toggle inspector panel"),
                    (", / .", "Previous/next note"),
                    ("Home / End", "Jump first/last note"),
                    ("PgUp/PgDn", "Shift selection notation lane"),
                    ("Ctrl+PgUp/PgDn", "Cycle selection articulation"),
                    ("1-9", "Quick lane reassign (left->right)"),
                    ("Alt+Left/Right", "Nudge selected note/range"),
                    ("Delete", "Remove selected note/range"),
                    ("Q", "Quantize selected note/range"),
                    ("Ctrl+A", "Select all notes"),
                    ("Ctrl+C / Ctrl+V", "Copy/paste selection"),
                    ("Ctrl+D", "Duplicate selected note/range"),
                    ("Ctrl+S", "Save"),
                    ("Ctrl+Shift+H", "Toggle history panel"),
                    ("Ctrl+Z", "Undo"),
                    ("Ctrl+Y / Ctrl+Shift+Z", "Redo")
                };

                tipFlow = new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(18, 0),
                    Children = tips.Select(t => createTip(t.key, t.action)).ToArray()
                };
            }
            footerTipFlow = tipFlow!;

            footerSeekCurrentText = new SpriteText
            {
                Text = formatTime(0),
                Font = BeatSightFont.Caption(10.6f),
                Colour = EditorColours.TextSecondary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                UseFullGlyphHeight = true
            };

            footerSeekTotalText = new SpriteText
            {
                Text = "--:--.---",
                Font = BeatSightFont.Caption(10.6f),
                Colour = EditorColours.TextSecondary,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                UseFullGlyphHeight = true
            };

            footerSeekSlider = new ScrubbableSliderBar
            {
                RelativeSizeAxes = Axes.Both,
                Current = footerSeekProgress,
                KeyboardStepMultiplier = 1,
                DragStepMultiplier = 1
            };
            footerSeekSlider.ScrubbingChanged += onFooterSeekScrubbingChanged;
            footerSeekProgress.BindValueChanged(onFooterSeekProgressChanged, true);

            footerSeekRow = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize),
                    new Dimension(),
                    new Dimension(GridSizeMode.AutoSize)
                },
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, 26)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.Y,
                            Width = 86,
                            Height = 1,
                            Padding = new MarginPadding { Right = 8 },
                            Child = footerSeekCurrentText
                        },
                        new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Height = 1,
                            Padding = new MarginPadding { Horizontal = 2 },
                            Child = footerSeekSlider
                        },
                        new Container
                        {
                            RelativeSizeAxes = Axes.Y,
                            Width = 86,
                            Height = 1,
                            Padding = new MarginPadding { Left = 8 },
                            Child = footerSeekTotalText
                        }
                    }
                }
            };

            Drawable[] footerRows;
            if (showFooterShortcutHints && tipFlow != null)
            {
                footerRows = new Drawable[]
                {
                    footerSeekRow,
                    footerTipsContainer = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Masking = true,
                        Child = tipFlow
                    }
                };
            }
            else
            {
                footerTipsContainer = null!;
                footerRows = new Drawable[]
                {
                    footerSeekRow
                };
            }

            var root = footerRootContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
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
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding { Horizontal = 15, Vertical = 9 },
                        Child = new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Anchor = Anchor.TopLeft,
                            Origin = Anchor.TopLeft,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 8),
                            Children = footerRows
                        }
                    },
                }
            };

            syncFooterSeekBar();
            return root;
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

        private void toggleFooterShortcutsCollapsed()
        {
            footerTipsCollapsed = true;
            appendStatusDetail(showFooterShortcutHints ? "Shortcuts are always visible" : "Shortcut hint row hidden");
        }

        private void refreshFooterShortcutVisibility(bool animate)
        {
            if (!showFooterShortcutHints || footerTipsContainer == null)
                return;

            footerTipsContainer.AlwaysPresent = true;
            if (animate)
                footerTipsContainer.FadeTo(1f, 140, Easing.OutQuint);
            else
                footerTipsContainer.Alpha = 1f;
        }

        private void onFooterSeekScrubbingChanged(bool scrubbing)
        {
            footerSeekScrubbing = scrubbing;
            if (scrubbing)
            {
                footerSmoothedScrubProgress = footerSeekProgress.Value;
                footerLastQueuedScrubProgress = footerSmoothedScrubProgress;
                footerSmoothedScrubInitialized = true;
                registerScrubSeekRequest(SeekInputSource.SeekBar, 0);
                return;
            }

            if (!scrubbing)
            {
                double length = getEffectivePlaybackLength();
                if (length > 0)
                    seekToTimeWithOptions(length * footerSeekProgress.Value, ensureTimelineVisible: true, syncTrack: true, syncPreview: true);

                footerSmoothedScrubInitialized = false;
                footerLastQueuedScrubProgress = double.NaN;
                syncFooterSeekBar();
            }
        }

        private void onFooterSeekProgressChanged(osu.Framework.Bindables.ValueChangedEvent<double> value)
        {
            if (suppressFooterSeekSync || !footerSeekScrubbing)
                return;

            double length = getEffectivePlaybackLength();
            if (length <= 0)
                return;

            double rawProgress = Math.Clamp(value.NewValue, 0, 1);
            if (!footerSmoothedScrubInitialized)
            {
                footerSmoothedScrubProgress = rawProgress;
                footerLastQueuedScrubProgress = rawProgress;
                footerSmoothedScrubInitialized = true;
            }

            double smoothing = resolveSeekBarScrubSmoothing();
            footerSmoothedScrubProgress += (rawProgress - footerSmoothedScrubProgress) * smoothing;
            if (Math.Abs(rawProgress - footerSmoothedScrubProgress) < seekBarQueueProgressThreshold)
                footerSmoothedScrubProgress = rawProgress;

            if (!double.IsNaN(footerLastQueuedScrubProgress)
                && Math.Abs(footerSmoothedScrubProgress - footerLastQueuedScrubProgress) < seekBarQueueProgressThreshold)
            {
                return;
            }

            footerLastQueuedScrubProgress = footerSmoothedScrubProgress;
            queueSeekToTime(
                length * footerSmoothedScrubProgress,
                ensureTimelineVisible: true,
                syncTrack: false,
                syncPreview: true,
                source: SeekInputSource.SeekBar,
                inputDelta: rawProgress - footerSmoothedScrubProgress);
        }

        private void syncFooterSeekBar()
        {
            if (footerSeekCurrentText == null || footerSeekTotalText == null)
                return;

            double length = getEffectivePlaybackLength();
            double clampedCurrent = length > 0 ? Math.Clamp(currentTime, 0, length) : Math.Max(0, currentTime);
            double progress = length > 0 ? clampedCurrent / length : 0;

            if (!footerSeekScrubbing)
            {
                suppressFooterSeekSync = true;
                footerSeekProgress.Value = progress;
                suppressFooterSeekSync = false;
            }

            footerSeekCurrentText.Text = formatTime(clampedCurrent);
            footerSeekTotalText.Text = length > 0 ? formatTime(length) : "--:--.---";
        }

        private void toggleHistoryPanelVisibility()
        {
            historyPanelVisible = !historyPanelVisible;
            updateHistoryPanel();
            appendStatusDetail(historyPanelVisible ? "History panel shown" : "History panel hidden");
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
            if (anyEntries && historyPanelVisible)
            {
                historyPanel.ClearTransforms();
                historyPanel.X = 18;
                historyPanel.Show();
                historyPanel.FadeInFromZero(130, Easing.OutQuint);
                historyPanel.MoveToX(0, 210, Easing.OutQuint);
            }
            else
            {
                historyPanel.ClearTransforms();
                historyPanel.FadeOut(110, Easing.OutQuint);
                historyPanel.MoveToX(16, 130, Easing.OutQuint);
                Scheduler.AddDelayed(() => historyPanel.Hide(), 132);
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
    }
}
