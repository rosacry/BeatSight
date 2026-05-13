using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Input.Events;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private SpriteText timingTapBpmText = null!;
        private SpriteText timingPlaybackRateText = null!;
        private SpriteText timingOffsetAssistText = null!;
        private SpriteText timingDetectionSummaryText = null!;
        private SpriteText timingBpmValueText = null!;
        private SpriteText timingOffsetValueText = null!;
        private SpriteText timingTimeSignatureValueText = null!;
        private SpriteText timingSectionValueText = null!;
        private SpriteText timingSectionHintText = null!;
        private BeatSightTextBox timingSetupTimeSignatureInput = null!;
        private BeatSightCheckbox timingMetronomeCheckbox = null!;
        private readonly List<TimingPoint> timingSetupDraftPoints = new();
        private readonly Queue<double> timingTapIntervals = new();
        private readonly Queue<double> timingOffsetSuggestions = new();
        private string timingSetupGlobalTimeSignature = "4/4";
        private int timingSetupSelectedPointIndex = -1;
        private double? lastTimingTapAtMs;
        private const int maxTimingTapIntervals = 8;
        private const int maxTimingOffsetSamples = 12;
        private static readonly string[] commonTimeSignatures =
        {
            "2/4",
            "3/4",
            "4/4",
            "5/4",
            "6/4",
            "3/8",
            "6/8",
            "7/8",
            "9/8",
            "12/8"
        };

        private Drawable createTimingSetupOverlay()
        {
            timingSetupBpmInput = new BeatSightTextBox
            {
                RelativeSizeAxes = Axes.X,
                Height = 40,
                PlaceholderText = "BPM",
                CornerRadius = 8,
                FontSize = 14f
            };

            timingSetupOffsetInput = new BeatSightTextBox
            {
                RelativeSizeAxes = Axes.X,
                Height = 40,
                PlaceholderText = "Offset (ms)",
                CornerRadius = 8,
                FontSize = 14f
            };

            timingSetupTimeSignatureInput = new BeatSightTextBox
            {
                RelativeSizeAxes = Axes.X,
                Height = 40,
                PlaceholderText = "4/4",
                CornerRadius = 8,
                FontSize = 14f
            };

            timingMoveNotesCheckbox = new BeatSightCheckbox
            {
                LabelText = "Move placed notes when BPM/offset changes",
                LabelFontSize = 12f,
                Current = timingMoveNotes
            };

            timingResnapNotesCheckbox = new BeatSightCheckbox
            {
                LabelText = "Resnap notes to current grid (1/" + snapDivisor + ")",
                LabelFontSize = 12f,
                Current = timingResnapNotes
            };

            timingMetronomeCheckbox = new BeatSightCheckbox
            {
                LabelText = "Metronome while previewing timing",
                LabelFontSize = 12f,
                Current = metronomeEnabledSetting
            };

            timingSectionValueText = new SpriteText
            {
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                X = 12,
                Font = BeatSightFont.Caption(12.5f),
                Colour = EditorColours.TextPrimary
            };

            timingSectionHintText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                AllowMultiline = true,
                Font = BeatSightFont.Caption(11.2f),
                Colour = EditorColours.TextSecondary,
                Text = "Global timing section"
            };

            timingSetupHintText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                AllowMultiline = true,
                Font = BeatSightFont.Caption(11f),
                Colour = EditorColours.TextSecondary,
                Text = "T tap BPM | Up/Down BPM | Left/Right offset | [ / ] meter | PgUp/PgDn sections | Ins add split | Esc cancel."
            };

            timingPlaybackRateText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                Font = BeatSightFont.Caption(11.4f),
                Colour = EditorColours.TextSecondary,
                Text = $"Playback: {playbackRate:0.00}x"
            };

            timingTapBpmText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                Font = BeatSightFont.Caption(11.2f),
                Colour = EditorColours.TextSecondary,
                Text = "Tap BPM on each beat to estimate tempo."
            };

            timingOffsetAssistText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                Font = BeatSightFont.Caption(11.2f),
                Colour = EditorColours.TextSecondary,
                Text = "Use offset +/- to align the first downbeat with the music."
            };

            timingDetectionSummaryText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                AllowMultiline = true,
                Font = BeatSightFont.Caption(11.2f),
                Colour = EditorColours.TextSecondary,
                Text = "Auto Detect uses waveform and placed notes when available."
            };

            var quickActionRow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Children = new Drawable[]
                {
                    createTimingQuickButton("Tap BPM", registerTimingTap, 124f),
                    createTimingQuickButton("Auto Detect", autoDetectTimingFromContext, 132f),
                    createTimingQuickButton("Play/Pause", togglePlayback, 120f),
                    createTimingQuickButton("Clear Taps", clearTimingDetectors, 112f)
                }
            };

            var sectionSelectorRow = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[] { new Dimension(GridSizeMode.AutoSize) },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, 52),
                    new Dimension(GridSizeMode.Distributed),
                    new Dimension(GridSizeMode.Absolute, 52)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createTimingQuickButton("<", () => nudgeTimingSection(-1), 52),
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 32,
                            Masking = true,
                            CornerRadius = 8,
                            Children = new Drawable[]
                            {
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = EditorColours.ControlsBackground
                                },
                                timingSectionValueText
                            }
                        },
                        createTimingQuickButton(">", () => nudgeTimingSection(1), 52)
                    }
                }
            };

            var sectionActionsRow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Children = new Drawable[]
                {
                    createTimingQuickButton("Add Split @ Now", addTimingSplitAtCurrentTime, 156f),
                    createTimingQuickButton("Remove Split", removeSelectedTimingSplit, 132f)
                }
            };

            var panelContent = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 10),
                Padding = new MarginPadding { Horizontal = 22, Vertical = 18 },
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = "Timing Setup",
                        Font = BeatSightFont.Section(20f),
                        Colour = EditorColours.TextPrimary
                    },
                    new SpriteText
                    {
                        RelativeSizeAxes = Axes.X,
                        AllowMultiline = true,
                        Font = BeatSightFont.Caption(11.6f),
                        Colour = EditorColours.TextSecondary,
                        Text = "Set BPM, offset, meter, then apply."
                    },
                    createTimingValueStepperField("BPM", out timingBpmValueText, () => nudgeTimingBpm(-0.1), () => nudgeTimingBpm(0.1)),
                    createTimingValueStepperField("Offset (ms)", out timingOffsetValueText, () => nudgeTimingOffset(-1), () => nudgeTimingOffset(1)),
                    createTimingValueStepperField("Time Signature", out timingTimeSignatureValueText, () => nudgeTimingTimeSignature(-1), () => nudgeTimingTimeSignature(1)),
                    createTimingField(
                        "Timing Sections",
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 8),
                            Children = new Drawable[]
                            {
                                sectionSelectorRow,
                                sectionActionsRow
                            }
                        }),
                    timingSectionHintText,
                    createTimingField("Quick Actions", quickActionRow),
                    timingTapBpmText,
                    timingOffsetAssistText,
                    timingDetectionSummaryText,
                    timingPlaybackRateText,
                    createTimingField(
                        "Metronome",
                        timingMetronomeCheckbox),
                    timingMoveNotesCheckbox,
                    timingResnapNotesCheckbox,
                    timingSetupHintText,
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(10, 0),
                        Margin = new MarginPadding { Top = 6 },
                        Children = new Drawable[]
                        {
                            new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Width = 0.34f,
                                Height = 36,
                                Child = new BeatSightButton
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Text = "Cancel",
                                    BackgroundColour = EditorColours.ControlsBackground,
                                    Action = closeTimingSetupOverlay
                                }
                            },
                            new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Width = 0.66f,
                                Height = 36,
                                Child = new BeatSightButton
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Text = "Apply Timing",
                                    BackgroundColour = EditorColours.AccentSave,
                                    Action = applyTimingSetupChanges
                                }
                            }
                        }
                    }
                }
            };

            var panelScroll = new BeatSightScrollContainer
            {
                RelativeSizeAxes = Axes.Both,
                Child = panelContent
            };

            var overlay = new TimingSetupOverlayContainer
            {
                RelativeSizeAxes = Axes.Both,
                Alpha = 0,
                AlwaysPresent = false,
                Depth = -95,
                DismissRequested = closeTimingSetupOverlay,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Overlay.Opacity(0.86f)
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Child = timingSetupDialogContainer = new Container
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            RelativeSizeAxes = Axes.Both,
                            Size = new Vector2(0.52f, 0.66f),
                            Masking = true,
                            CornerRadius = 14,
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
                                    Alpha = 0.17f
                                },
                                panelScroll
                            }
                        }
                    }
                }
            };
            overlay.DialogContainer = timingSetupDialogContainer;
            timingSetupOverlay = overlay;
            timingSetupOverlay.Hide();

            return timingSetupOverlay;
        }

        private Drawable createTimingQuickButton(string text, Action action, float width)
        {
            return new Container
            {
                AutoSizeAxes = Axes.Y,
                Width = width,
                Child = new BeatSightButton
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 32,
                    Text = text,
                    BackgroundColour = EditorColours.ControlsBackground,
                    Action = action
                }
            };
        }

        private Drawable createTimingValueStepperField(string label, out SpriteText valueText, Action decrement, Action increment)
        {
            valueText = new SpriteText
            {
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                X = 12,
                Font = BeatSightFont.Caption(12.5f),
                Colour = EditorColours.TextPrimary
            };

            return createTimingField(
                label,
                new GridContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    RowDimensions = new[] { new Dimension(GridSizeMode.AutoSize) },
                    ColumnDimensions = new[]
                    {
                        new Dimension(GridSizeMode.Absolute, 52),
                        new Dimension(GridSizeMode.Distributed),
                        new Dimension(GridSizeMode.Absolute, 52)
                    },
                    Content = new[]
                    {
                        new Drawable[]
                        {
                            createTimingQuickButton("-", decrement, 52),
                            new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 32,
                                Masking = true,
                                CornerRadius = 8,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = EditorColours.ControlsBackground
                                    },
                                    valueText
                                }
                            },
                            createTimingQuickButton("+", increment, 52)
                        }
                    }
                });
        }

        private Drawable createTimingFieldRow(params (string Label, Drawable Input)[] fields)
        {
            int count = Math.Max(1, fields.Length);

            return new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[] { new Dimension(GridSizeMode.AutoSize) },
                ColumnDimensions = Enumerable.Repeat(new Dimension(GridSizeMode.Relative, 1f / count), count).ToArray(),
                Content = new[]
                {
                    fields.Select((field, index) => (Drawable)new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding
                        {
                            Left = index == 0 ? 0 : 5,
                            Right = index == count - 1 ? 0 : 5
                        },
                        Child = createTimingField(field.Label, field.Input)
                    }).ToArray()
                }
            };
        }

        private Drawable createTimingField(string label, Drawable input)
        {
            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 5),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = label,
                        Font = BeatSightFont.Caption(11.6f),
                        Colour = EditorColours.TextSecondary
                    },
                    input
                }
            };
        }

        private void openTimingSetupOverlay()
        {
            if (beatmap == null || timingSetupOverlay == null)
            {
                appendStatusDetail("Load a beatmap before editing timing");
                return;
            }

            timingSetupBpmInput.Current.Value = beatmap.Timing.Bpm.ToString("0.##", CultureInfo.InvariantCulture);
            timingSetupOffsetInput.Current.Value = beatmap.Timing.Offset.ToString(CultureInfo.InvariantCulture);
            timingSetupGlobalTimeSignature = normalizeTimeSignature(beatmap.Timing.TimeSignature, "4/4");
            timingSetupTimeSignatureInput.Current.Value = timingSetupGlobalTimeSignature;
            timingResnapNotesCheckbox.LabelText = $"Resnap notes to current grid (1/{snapDivisor})";
            timingSetupHintText.Text = $"Current snap: 1/{snapDivisor}. T tap BPM | Up/Down BPM | Left/Right offset | [ / ] meter | PgUp/PgDn sections | Space play/pause.";
            timingPlaybackRateText.Text = $"Playback: {playbackRate:0.00}x";
            loadTimingSectionDraft();
            selectTimingSection(-1);
            clearTimingDetectors();
            refreshTimingMetronomeControl();
            syncTimingSetupReadouts();

            timingSetupOverlay.Show();
            timingSetupOverlay.AlwaysPresent = true;
            timingSetupOverlay.ClearTransforms();
            timingSetupOverlay.FadeIn(140, Easing.OutQuint);

            if (timingSetupDialogContainer != null)
            {
                timingSetupDialogContainer.ClearTransforms();
                timingSetupDialogContainer.Y = 20;
                timingSetupDialogContainer.Scale = new Vector2(0.96f);
                timingSetupDialogContainer.FadeIn(120, Easing.OutQuint);
                timingSetupDialogContainer.MoveToY(0, 220, Easing.OutQuint);
                timingSetupDialogContainer.ScaleTo(1f, 240, Easing.OutBack);
            }

        }

        private void closeTimingSetupOverlay()
        {
            if (timingSetupOverlay == null || !timingSetupOverlay.IsPresent)
                return;

            timingSetupOverlay.ClearTransforms();
            timingSetupOverlay.FadeOut(170, Easing.OutQuint);
            if (timingSetupDialogContainer != null)
            {
                timingSetupDialogContainer.ClearTransforms();
                timingSetupDialogContainer.FadeOut(150, Easing.OutQuint);
                timingSetupDialogContainer.MoveToY(22, 190, Easing.OutQuint);
                timingSetupDialogContainer.ScaleTo(0.94f, 190, Easing.OutQuint);
            }

            Scheduler.AddDelayed(() =>
            {
                timingSetupOverlay.Hide();
                timingSetupOverlay.AlwaysPresent = false;
                if (timingSetupDialogContainer != null)
                {
                    timingSetupDialogContainer.Y = 0;
                    timingSetupDialogContainer.Scale = Vector2.One;
                }
            }, 196);
        }

        private void applyTimingSetupChanges()
        {
            if (beatmap == null)
            {
                closeTimingSetupOverlay();
                return;
            }

            if (!tryParseTimingSetupInputs(out double newBpm, out double newOffset, out string newTimeSignature))
                return;

            double oldBpm = Math.Max(20, beatmap.Timing.Bpm);
            double oldOffset = beatmap.Timing.Offset;
            string oldTimeSignature = normalizeTimeSignature(beatmap.Timing.TimeSignature, "4/4");
            var oldTimingPoints = normalizeTimingPoints(beatmap.Timing.TimingPoints);
            var newTimingPoints = normalizeTimingPoints(timingSetupDraftPoints);
            bool bpmChanged = Math.Abs(newBpm - oldBpm) > 0.0001;
            bool offsetChanged = Math.Abs(newOffset - oldOffset) > 0.5;
            bool timeSignatureChanged = !string.Equals(newTimeSignature, oldTimeSignature, StringComparison.Ordinal);
            bool timingPointsChanged = !timingPointSetsEqual(oldTimingPoints, newTimingPoints);

            if (!bpmChanged && !offsetChanged && !timeSignatureChanged && !timingPointsChanged)
            {
                closeTimingSetupOverlay();
                appendStatusDetail("Timing unchanged");
                return;
            }

            prepareUndoSnapshot();

            if (beatmap.HitObjects.Count > 0)
            {
                if (timingMoveNotes.Value)
                    remapHitObjectsForTiming(oldBpm, oldOffset, newBpm, newOffset, timingResnapNotes.Value);
                else if (timingResnapNotes.Value)
                    resnapHitObjectsToGrid(newBpm, newOffset);
            }

            beatmap.Timing.Bpm = newBpm;
            beatmap.Timing.Offset = (int)Math.Round(newOffset);
            beatmap.Timing.TimeSignature = newTimeSignature;
            beatmap.Timing.TimingPoints = newTimingPoints.Count > 0 ? newTimingPoints : null;
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));

            suppressInspectorFieldSync = true;
            if (bpmInput != null)
                bpmInput.Current.Value = beatmap.Timing.Bpm.ToString("0.##", CultureInfo.InvariantCulture);
            if (offsetInput != null)
                offsetInput.Current.Value = beatmap.Timing.Offset.ToString(CultureInfo.InvariantCulture);
            suppressInspectorFieldSync = false;

            markUnsaved();
            syncTimelineSnapForCurrentTime(force: true);
            reloadTimeline();
            updateInspectorStats();

            closeTimingSetupOverlay();
            appendStatusDetail($"Timing applied: {beatmap.Timing.Bpm:0.##} BPM, {beatmap.Timing.Offset:+#;-#;0} ms, {beatmap.Timing.TimeSignature} ({newTimingPoints.Count} split point{(newTimingPoints.Count == 1 ? string.Empty : "s")})");
        }

        private void setTimingPlaybackRate(double rate)
        {
            setPlaybackRate(rate, announce: false);
            if (timingPlaybackRateText != null)
                timingPlaybackRateText.Text = $"Playback: {playbackRate:0.00}x";
            appendStatusDetail($"Playback rate {playbackRate:0.00}x");
        }

        private void syncTimingSetupReadouts()
        {
            if (timingSetupBpmInput != null
                && double.TryParse(timingSetupBpmInput.Current.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out double bpm)
                && timingBpmValueText != null)
            {
                timingBpmValueText.Text = $"{Math.Clamp(bpm, 20, 400):0.##}";
            }

            if (timingSetupOffsetInput != null
                && double.TryParse(timingSetupOffsetInput.Current.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out double offset)
                && timingOffsetValueText != null)
            {
                timingOffsetValueText.Text = $"{Math.Clamp(offset, -10000, 10000):+0.##;-0.##;0} ms";
            }

            if (timingTimeSignatureValueText != null)
            {
                string signature = getSelectedTimingSectionSignature();
                timingTimeSignatureValueText.Text = signature;
                if (timingSetupTimeSignatureInput != null)
                    timingSetupTimeSignatureInput.Current.Value = signature;
            }

            if (timingSectionValueText != null)
            {
                if (timingSetupSelectedPointIndex < 0)
                    timingSectionValueText.Text = "Global";
                else if (timingSetupSelectedPointIndex < timingSetupDraftPoints.Count)
                    timingSectionValueText.Text = $"Split @ {formatTime(timingSetupDraftPoints[timingSetupSelectedPointIndex].Time)}";
            }

            if (timingSectionHintText != null)
            {
                int sectionCount = timingSetupDraftPoints.Count + 1;
                int sectionNumber = timingSetupSelectedPointIndex < 0
                    ? 1
                    : Math.Clamp(timingSetupSelectedPointIndex + 2, 2, sectionCount);
                timingSectionHintText.Text = timingSetupSelectedPointIndex < 0
                    ? $"Section {sectionNumber}/{sectionCount}. Global timing."
                    : $"Section {sectionNumber}/{sectionCount}. Time-signature split at {formatTime(timingSetupDraftPoints[timingSetupSelectedPointIndex].Time)}.";
            }
        }

        private void nudgeTimingBpm(double deltaBpm)
        {
            if (!double.TryParse(timingSetupBpmInput.Current.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out double parsed))
                parsed = beatmap?.Timing.Bpm ?? TimingInfo.DefaultBpm;

            double next = Math.Clamp(parsed + deltaBpm, 20, 400);
            timingSetupBpmInput.Current.Value = next.ToString("0.##", CultureInfo.InvariantCulture);
            syncTimingSetupReadouts();
        }

        private void loadTimingSectionDraft()
        {
            timingSetupDraftPoints.Clear();

            if (beatmap?.Timing?.TimingPoints == null)
                return;

            foreach (var point in beatmap.Timing.TimingPoints.OrderBy(point => point.Time))
            {
                if (point.Time < 0)
                    continue;

                timingSetupDraftPoints.Add(new TimingPoint
                {
                    Time = point.Time,
                    Bpm = point.Bpm,
                    TimeSignature = string.IsNullOrWhiteSpace(point.TimeSignature)
                        ? null
                        : normalizeTimeSignature(point.TimeSignature, timingSetupGlobalTimeSignature)
                });
            }
        }

        private void selectTimingSection(int index)
        {
            int maxIndex = timingSetupDraftPoints.Count - 1;
            timingSetupSelectedPointIndex = Math.Clamp(index, -1, maxIndex);
            syncTimingSetupReadouts();
        }

        private void nudgeTimingSection(int delta)
        {
            int maxIndex = timingSetupDraftPoints.Count - 1;
            int next = Math.Clamp(timingSetupSelectedPointIndex + Math.Sign(delta), -1, maxIndex);
            if (next == timingSetupSelectedPointIndex)
                return;

            selectTimingSection(next);
        }

        private void addTimingSplitAtCurrentTime()
        {
            string signature = getSelectedTimingSectionSignature();
            int splitTime = (int)Math.Round(Math.Max(0, currentTime));

            int existingIndex = timingSetupDraftPoints.FindIndex(point => point.Time == splitTime);
            if (existingIndex >= 0)
            {
                timingSetupDraftPoints[existingIndex].TimeSignature = signature;
                selectTimingSection(existingIndex);
                appendStatusDetail($"Updated split @ {formatTime(splitTime)} to {signature}");
                return;
            }

            timingSetupDraftPoints.Add(new TimingPoint
            {
                Time = splitTime,
                Bpm = 0,
                TimeSignature = signature
            });
            timingSetupDraftPoints.Sort((a, b) => a.Time.CompareTo(b.Time));

            int newIndex = timingSetupDraftPoints.FindIndex(point => point.Time == splitTime && string.Equals(point.TimeSignature, signature, StringComparison.Ordinal));
            selectTimingSection(newIndex);
            appendStatusDetail($"Added split @ {formatTime(splitTime)} ({signature})");
        }

        private void removeSelectedTimingSplit()
        {
            if (timingSetupSelectedPointIndex < 0 || timingSetupSelectedPointIndex >= timingSetupDraftPoints.Count)
            {
                appendStatusDetail("Select a split section first");
                return;
            }

            var point = timingSetupDraftPoints[timingSetupSelectedPointIndex];
            bool hasBpm = point.Bpm > 0 && double.IsFinite(point.Bpm);
            if (hasBpm)
            {
                point.TimeSignature = null;
                timingSetupDraftPoints[timingSetupSelectedPointIndex] = point;
                selectTimingSection(timingSetupSelectedPointIndex);
                appendStatusDetail($"Cleared time signature override @ {formatTime(point.Time)}");
                return;
            }

            timingSetupDraftPoints.RemoveAt(timingSetupSelectedPointIndex);
            selectTimingSection(Math.Min(timingSetupSelectedPointIndex - 1, timingSetupDraftPoints.Count - 1));
            appendStatusDetail($"Removed split @ {formatTime(point.Time)}");
        }

        private string getSelectedTimingSectionSignature()
        {
            if (timingSetupSelectedPointIndex >= 0 && timingSetupSelectedPointIndex < timingSetupDraftPoints.Count)
            {
                string? value = timingSetupDraftPoints[timingSetupSelectedPointIndex].TimeSignature;
                if (tryNormalizeTimeSignature(value, out string selected))
                    return selected;
            }

            return normalizeTimeSignature(timingSetupGlobalTimeSignature, "4/4");
        }

        private void nudgeTimingTimeSignature(int delta)
        {
            int direction = Math.Sign(delta);
            if (direction == 0)
                return;

            string current = getSelectedTimingSectionSignature();
            int currentIndex = Array.IndexOf(commonTimeSignatures, current);
            if (currentIndex < 0)
                currentIndex = Array.IndexOf(commonTimeSignatures, "4/4");

            int nextIndex = Math.Clamp(currentIndex + direction, 0, commonTimeSignatures.Length - 1);
            string next = commonTimeSignatures[nextIndex];

            if (timingSetupSelectedPointIndex >= 0 && timingSetupSelectedPointIndex < timingSetupDraftPoints.Count)
                timingSetupDraftPoints[timingSetupSelectedPointIndex].TimeSignature = next;
            else
                timingSetupGlobalTimeSignature = next;

            syncTimingSetupReadouts();
        }

        private void registerTimingTap()
        {
            double now = Time.Current;
            if (lastTimingTapAtMs.HasValue)
            {
                double interval = now - lastTimingTapAtMs.Value;
                if (interval >= 180 && interval <= 2200)
                {
                    timingTapIntervals.Enqueue(interval);
                    while (timingTapIntervals.Count > maxTimingTapIntervals)
                        timingTapIntervals.Dequeue();
                }
                else
                {
                    timingTapIntervals.Clear();
                }
            }

            lastTimingTapAtMs = now;
            updateTimingTapEstimate();
        }

        private void registerTimingOffsetTap()
        {
            if (!tryParseTimingBaseValues(out double bpm, out double offset))
                return;

            double beatLengthMs = 60000.0 / Math.Max(1, bpm);
            if (!double.IsFinite(beatLengthMs) || beatLengthMs <= 0.01)
                return;

            double tapTime = Math.Max(0, currentTime);
            double nearestBeatIndex = Math.Round((tapTime - offset) / beatLengthMs);
            double nearestBeatTime = offset + nearestBeatIndex * beatLengthMs;
            double delta = normaliseBeatDelta(tapTime - nearestBeatTime, beatLengthMs);
            double suggestedOffset = Math.Clamp(offset + delta, -10000, 10000);

            timingOffsetSuggestions.Enqueue(suggestedOffset);
            while (timingOffsetSuggestions.Count > maxTimingOffsetSamples)
                timingOffsetSuggestions.Dequeue();

            updateTimingOffsetEstimateFromSamples();
        }

        private void updateTimingOffsetEstimateFromSamples()
        {
            if (timingOffsetAssistText == null)
                return;

            if (timingOffsetSuggestions.Count < 1)
            {
                timingOffsetAssistText.Text = "Use offset +/- to align the first downbeat with the music.";
                return;
            }

            double[] samples = timingOffsetSuggestions.OrderBy(v => v).ToArray();
            int mid = samples.Length / 2;
            double median = samples.Length % 2 == 0
                ? (samples[mid - 1] + samples[mid]) * 0.5
                : samples[mid];
            double averageDeviation = samples.Select(value => Math.Abs(value - median)).Average();

            timingOffsetAssistText.Text = $"Offset guide: {median:+0.##;-0.##;0} ms ({samples.Length} tap{(samples.Length == 1 ? string.Empty : "s")}, avg +/-{averageDeviation:0.##} ms)";
            if (samples.Length >= 3)
                timingSetupOffsetInput.Current.Value = median.ToString("0.##", CultureInfo.InvariantCulture);
            syncTimingSetupReadouts();
        }

        private void clearTimingDetectors()
        {
            resetTimingTapEstimator();
            resetTimingOffsetEstimator();
            if (timingDetectionSummaryText != null)
                timingDetectionSummaryText.Text = "Auto Detect uses waveform and placed notes when available.";
        }

        private void resetTimingTapEstimator()
        {
            timingTapIntervals.Clear();
            lastTimingTapAtMs = null;
            if (timingTapBpmText != null)
                timingTapBpmText.Text = "Tap BPM on each beat to estimate tempo.";
        }

        private void resetTimingOffsetEstimator()
        {
            timingOffsetSuggestions.Clear();
            if (timingOffsetAssistText != null)
                timingOffsetAssistText.Text = "Use offset +/- to align the first downbeat with the music.";
        }

        private void updateTimingTapEstimate()
        {
            if (timingTapBpmText == null)
                return;

            if (timingTapIntervals.Count < 2)
            {
                timingTapBpmText.Text = "Keep tapping to estimate BPM...";
                return;
            }

            double sum = 0;
            foreach (double interval in timingTapIntervals)
                sum += interval;

            double averageInterval = sum / timingTapIntervals.Count;
            if (averageInterval <= 0)
            {
                timingTapBpmText.Text = "Tap BPM on each beat to estimate tempo.";
                return;
            }

            double rawBpm = 60000.0 / averageInterval;
            double correctedBpm = Math.Clamp(rawBpm / Math.Max(0.05, playbackRate), 20, 400);
            timingTapBpmText.Text = $"Estimated BPM: {correctedBpm:0.##} ({timingTapIntervals.Count + 1} taps @ {playbackRate:0.00}x)";
            timingSetupBpmInput.Current.Value = correctedBpm.ToString("0.##", CultureInfo.InvariantCulture);
            syncTimingSetupReadouts();
        }

        private void nudgeTimingOffset(double deltaMs)
        {
            double parsed = 0;
            if (!double.TryParse(timingSetupOffsetInput.Current.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out parsed))
                parsed = beatmap?.Timing.Offset ?? 0;

            double next = Math.Clamp(parsed + deltaMs, -10000, 10000);
            timingSetupOffsetInput.Current.Value = next.ToString("0.##", CultureInfo.InvariantCulture);
            timingOffsetAssistText.Text = $"Offset adjusted to {next:+0.##;-0.##;0} ms";
            syncTimingSetupReadouts();
        }

        private void setTimingOffsetToCurrentPosition()
        {
            double now = Math.Max(0, currentTime);
            timingSetupOffsetInput.Current.Value = now.ToString("0", CultureInfo.InvariantCulture);
            timingOffsetAssistText.Text = $"Offset set to current time {formatTime(now)}";
            syncTimingSetupReadouts();
        }

        private void autoDetectTimingFromContext()
        {
            if (beatmap == null)
                return;

            if (!tryAutoDetectTiming(out double bpm, out double offset, out string timeSignature, out string summary))
            {
                timingDetectionSummaryText.Text = "Auto detect needs waveform data or enough placed notes.";
                appendStatusDetail("Auto timing unavailable - add notes or wait for waveform load");
                return;
            }

            timingSetupBpmInput.Current.Value = bpm.ToString("0.##", CultureInfo.InvariantCulture);
            timingSetupOffsetInput.Current.Value = offset.ToString("0.##", CultureInfo.InvariantCulture);
            timingSetupGlobalTimeSignature = normalizeTimeSignature(timeSignature, "4/4");
            if (timingSetupSelectedPointIndex < 0)
                timingSetupTimeSignatureInput.Current.Value = timingSetupGlobalTimeSignature;
            timingDetectionSummaryText.Text = summary;
            appendStatusDetail($"Auto-detected {bpm:0.##} BPM | {offset:+0.##;-0.##;0} ms | {timeSignature}");
            syncTimingSetupReadouts();
        }

        private bool tryAutoDetectTiming(out double bpm, out double offset, out string timeSignature, out string summary)
        {
            bpm = beatmap?.Timing.Bpm ?? TimingInfo.DefaultBpm;
            offset = beatmap?.Timing.Offset ?? 0;
            timeSignature = normalizeTimeSignature(beatmap?.Timing.TimeSignature, "4/4");
            summary = string.Empty;

            bool usedWaveform = false;
            bool usedHitObjects = false;
            bool bpmDetected = false;

            if (waveformData != null && tryEstimateBpmFromWaveform(waveformData, out double waveformBpm))
            {
                bpm = waveformBpm;
                bpmDetected = true;
                usedWaveform = true;
            }
            else if (beatmap != null && tryEstimateBpmFromHitObjects(beatmap.HitObjects, out double hitObjectBpm))
            {
                bpm = hitObjectBpm;
                bpmDetected = true;
                usedHitObjects = true;
            }

            if (!bpmDetected)
                return false;

            if (waveformData != null && tryEstimateOffsetFromWaveform(waveformData, bpm, out double waveformOffset))
            {
                offset = waveformOffset;
                usedWaveform = true;
            }
            else if (beatmap != null && tryEstimateOffsetFromHitObjects(beatmap.HitObjects, bpm, out double hitOffset))
            {
                offset = hitOffset;
                usedHitObjects = true;
            }

            if (beatmap != null && beatmap.HitObjects.Count >= 12)
                timeSignature = estimateTimeSignatureFromHitObjects(beatmap.HitObjects, bpm, offset, timeSignature);

            string source = usedWaveform && usedHitObjects
                ? "waveform + hit data"
                : usedWaveform
                    ? "waveform"
                    : "hit data";
            summary = $"Auto detect ({source}): {bpm:0.##} BPM, {offset:+0.##;-0.##;0} ms, {timeSignature}.";
            return true;
        }

        private static bool tryEstimateBpmFromWaveform(WaveformData waveform, out double bpm)
        {
            bpm = TimingInfo.DefaultBpm;
            if (waveform.BucketCount < 128 || waveform.BucketDurationSeconds <= 0)
                return false;

            double[] onsetEnvelope = buildWaveformOnsetEnvelope(waveform);
            int count = onsetEnvelope.Length;
            if (count < 128)
                return false;

            double bucketMs = waveform.BucketDurationSeconds * 1000.0;
            int minLag = Math.Max(1, (int)Math.Round((60000.0 / 220.0) / bucketMs));
            int maxLag = Math.Min(count / 2, (int)Math.Round((60000.0 / 60.0) / bucketMs));
            if (maxLag <= minLag)
                return false;

            int bestLag = 0;
            double bestScore = double.NegativeInfinity;

            for (int lag = minLag; lag <= maxLag; lag++)
            {
                double sum = 0;
                int pairs = count - lag;
                for (int i = 0; i < pairs; i++)
                    sum += onsetEnvelope[i] * onsetEnvelope[i + lag];

                double score = pairs > 0 ? sum / pairs : double.NegativeInfinity;
                if (!double.IsFinite(score))
                    continue;

                if (score > bestScore)
                {
                    bestScore = score;
                    bestLag = lag;
                }
            }

            if (bestLag <= 0 || !double.IsFinite(bestScore))
                return false;

            double rawBpm = 60000.0 / (bestLag * bucketMs);
            bpm = Math.Clamp(normaliseBpmToCommonRange(rawBpm), 20, 400);
            return true;
        }

        private static bool tryEstimateOffsetFromWaveform(WaveformData waveform, double bpm, out double offsetMs)
        {
            offsetMs = 0;
            if (waveform.BucketCount < 64 || waveform.BucketDurationSeconds <= 0 || bpm <= 0)
                return false;

            double beatLengthMs = 60000.0 / bpm;
            if (beatLengthMs <= 0.01 || !double.IsFinite(beatLengthMs))
                return false;

            double[] onsetEnvelope = buildWaveformOnsetEnvelope(waveform);
            if (onsetEnvelope.Length < 64)
                return false;

            double bucketMs = waveform.BucketDurationSeconds * 1000.0;
            double durationMs = waveform.DurationSeconds * 1000.0;
            int phaseSteps = Math.Clamp((int)Math.Round(beatLengthMs / Math.Max(1, bucketMs)), 24, 144);

            double bestPhase = 0;
            double bestScore = double.NegativeInfinity;

            for (int phaseStep = 0; phaseStep < phaseSteps; phaseStep++)
            {
                double phaseMs = phaseStep * beatLengthMs / phaseSteps;
                double score = 0;
                int sampleCount = 0;

                for (double beatTime = phaseMs; beatTime < durationMs; beatTime += beatLengthMs)
                {
                    int bucketIndex = (int)Math.Round(beatTime / bucketMs);
                    if (bucketIndex < 0 || bucketIndex >= onsetEnvelope.Length)
                        continue;

                    double localEnergy = onsetEnvelope[bucketIndex];
                    if (bucketIndex > 0)
                        localEnergy = Math.Max(localEnergy, onsetEnvelope[bucketIndex - 1] * 0.85);
                    if (bucketIndex + 1 < onsetEnvelope.Length)
                        localEnergy = Math.Max(localEnergy, onsetEnvelope[bucketIndex + 1] * 0.85);

                    score += localEnergy;
                    sampleCount++;
                }

                if (sampleCount <= 0)
                    continue;

                double average = score / sampleCount;
                if (average > bestScore)
                {
                    bestScore = average;
                    bestPhase = phaseMs;
                }
            }

            if (!double.IsFinite(bestScore))
                return false;

            if (bestPhase > beatLengthMs * 0.5)
                bestPhase -= beatLengthMs;

            offsetMs = Math.Clamp(bestPhase, -10000, 10000);
            return true;
        }

        private static bool tryEstimateBpmFromHitObjects(IReadOnlyList<HitObject> hitObjects, out double bpm)
        {
            bpm = TimingInfo.DefaultBpm;
            if (hitObjects.Count < 4)
                return false;

            var distinctTimes = hitObjects
                .Select(hit => hit.Time)
                .Distinct()
                .OrderBy(time => time)
                .ToArray();

            if (distinctTimes.Length < 4)
                return false;

            var intervals = new List<int>(distinctTimes.Length);
            for (int i = 1; i < distinctTimes.Length; i++)
            {
                int delta = distinctTimes[i] - distinctTimes[i - 1];
                if (delta >= 50 && delta <= 2000)
                    intervals.Add(delta);
            }

            if (intervals.Count < 3)
                return false;

            intervals.Sort();
            double medianInterval = intervals.Count % 2 == 0
                ? (intervals[intervals.Count / 2 - 1] + intervals[intervals.Count / 2]) * 0.5
                : intervals[intervals.Count / 2];

            if (medianInterval <= 0)
                return false;

            bpm = Math.Clamp(normaliseBpmToCommonRange(60000.0 / medianInterval), 20, 400);
            return true;
        }

        private static bool tryEstimateOffsetFromHitObjects(IReadOnlyList<HitObject> hitObjects, double bpm, out double offsetMs)
        {
            offsetMs = 0;
            if (hitObjects.Count < 3 || bpm <= 0)
                return false;

            double beatLengthMs = 60000.0 / bpm;
            if (beatLengthMs <= 0.01 || !double.IsFinite(beatLengthMs))
                return false;

            double sumSin = 0;
            double sumCos = 0;
            double totalWeight = 0;

            foreach (var hit in hitObjects)
            {
                double phaseMs = positiveRemainder(hit.Time, beatLengthMs);
                double angle = (phaseMs / beatLengthMs) * 2.0 * Math.PI;
                double weight = getDownbeatWeight(hit.Component);
                sumSin += Math.Sin(angle) * weight;
                sumCos += Math.Cos(angle) * weight;
                totalWeight += weight;
            }

            if (totalWeight <= 0.001)
                return false;

            double meanAngle = Math.Atan2(sumSin, sumCos);
            if (meanAngle < 0)
                meanAngle += 2.0 * Math.PI;

            double phase = meanAngle / (2.0 * Math.PI) * beatLengthMs;
            if (phase > beatLengthMs * 0.5)
                phase -= beatLengthMs;

            offsetMs = Math.Clamp(phase, -10000, 10000);
            return true;
        }

        private static string estimateTimeSignatureFromHitObjects(IReadOnlyList<HitObject> hitObjects, double bpm, double offsetMs, string fallback)
        {
            if (hitObjects.Count < 12 || bpm <= 0)
                return fallback;

            double beatLengthMs = 60000.0 / bpm;
            if (beatLengthMs <= 0.01 || !double.IsFinite(beatLengthMs))
                return fallback;

            int[] candidates = { 3, 4, 5, 6, 7 };
            int bestCandidate = 4;
            double bestScore = double.NegativeInfinity;
            double fourScore = double.NegativeInfinity;

            foreach (int beatsPerMeasure in candidates)
            {
                var slots = new double[beatsPerMeasure];
                int alignedCount = 0;

                foreach (var hit in hitObjects)
                {
                    double beatPosition = (hit.Time - offsetMs) / beatLengthMs;
                    int nearestBeat = (int)Math.Round(beatPosition);
                    if (Math.Abs(beatPosition - nearestBeat) > 0.24)
                        continue;

                    int slot = positiveModulo(nearestBeat, beatsPerMeasure);
                    double weight = getDownbeatWeight(hit.Component);
                    slots[slot] += weight;
                    alignedCount++;
                }

                if (alignedCount < Math.Max(12, beatsPerMeasure * 3))
                    continue;

                double downbeat = slots[0];
                double others = 0;
                for (int i = 1; i < slots.Length; i++)
                    others += slots[i];

                double otherAverage = others / Math.Max(1, beatsPerMeasure - 1);
                double dominance = downbeat / Math.Max(0.001, otherAverage);
                double coverage = alignedCount / (double)hitObjects.Count;
                double score = dominance + coverage * 0.45;

                if (beatsPerMeasure == 4)
                    fourScore = score;

                if (score > bestScore)
                {
                    bestScore = score;
                    bestCandidate = beatsPerMeasure;
                }
            }

            if (bestScore == double.NegativeInfinity)
                return fallback;

            if (bestCandidate != 4 && fourScore > double.NegativeInfinity)
            {
                if (bestScore < fourScore * 1.35 || (bestScore - fourScore) < 0.45)
                    bestCandidate = 4;
            }

            return $"{bestCandidate}/4";
        }

        private static double[] buildWaveformOnsetEnvelope(WaveformData waveform)
        {
            int count = waveform.BucketCount;
            var energy = new double[count];
            for (int i = 0; i < count; i++)
                energy[i] = Math.Max(Math.Abs(waveform.Minima[i]), Math.Abs(waveform.Maxima[i]));

            var onset = new double[count];
            const int radius = 4;
            for (int i = 0; i < count; i++)
            {
                int start = Math.Max(0, i - radius);
                int end = Math.Min(count - 1, i + radius);
                double total = 0;
                int window = 0;

                for (int j = start; j <= end; j++)
                {
                    total += energy[j];
                    window++;
                }

                double mean = window > 0 ? total / window : 0;
                onset[i] = Math.Max(0, energy[i] - mean * 0.92);
            }

            double max = onset.Max();
            if (max > 0.0001)
            {
                for (int i = 0; i < onset.Length; i++)
                    onset[i] /= max;
            }

            return onset;
        }

        private bool isTimingSetupOverlayVisible()
            => timingSetupOverlay != null && timingSetupOverlay.IsPresent && timingSetupOverlay.Alpha > 0.01f;

        private bool tryParseTimingSetupInputs(out double bpm, out double offset, out string timeSignature)
        {
            bpm = TimingInfo.DefaultBpm;
            offset = 0;
            timeSignature = normalizeTimeSignature(timingSetupGlobalTimeSignature, "4/4");
            bool valid = true;

            if (!double.TryParse(timingSetupBpmInput.Current.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out bpm)
                || bpm <= 0)
            {
                timingSetupBpmInput.FlashColour(EditorColours.Warning, 180);
                valid = false;
            }

            if (!double.TryParse(timingSetupOffsetInput.Current.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out offset))
            {
                timingSetupOffsetInput.FlashColour(EditorColours.Warning, 180);
                valid = false;
            }

            if (!tryNormalizeTimeSignature(timingSetupGlobalTimeSignature, out timeSignature))
            {
                valid = false;
            }

            bpm = Math.Clamp(bpm, 20, 400);
            offset = Math.Clamp(offset, -10000, 10000);
            return valid;
        }

        private bool tryParseTimingBaseValues(out double bpm, out double offset)
        {
            bpm = TimingInfo.DefaultBpm;
            offset = 0;

            bool bpmParsed = double.TryParse(timingSetupBpmInput.Current.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out bpm);
            bool offsetParsed = double.TryParse(timingSetupOffsetInput.Current.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out offset);
            if (!bpmParsed || bpm <= 0)
            {
                timingSetupBpmInput.FlashColour(EditorColours.Warning, 180);
                return false;
            }

            if (!offsetParsed)
            {
                timingSetupOffsetInput.FlashColour(EditorColours.Warning, 180);
                return false;
            }

            bpm = Math.Clamp(bpm, 20, 400);
            offset = Math.Clamp(offset, -10000, 10000);
            return true;
        }

        private static bool tryNormalizeTimeSignature(string? value, out string normalized)
        {
            normalized = "4/4";
            if (string.IsNullOrWhiteSpace(value))
                return false;

            string[] parts = value.Trim().Split('/');
            if (parts.Length != 2)
                return false;

            if (!int.TryParse(parts[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out int beatsPerMeasure))
                return false;

            if (!int.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int beatUnit))
                return false;

            beatsPerMeasure = Math.Clamp(beatsPerMeasure, 1, 32);
            if (beatUnit is not (1 or 2 or 4 or 8 or 16))
                return false;

            normalized = $"{beatsPerMeasure}/{beatUnit}";
            return true;
        }

        private static string normalizeTimeSignature(string? value, string fallback)
            => tryNormalizeTimeSignature(value, out string normalized) ? normalized : fallback;

        private static List<TimingPoint> normalizeTimingPoints(IReadOnlyList<TimingPoint>? source)
        {
            var normalized = new List<TimingPoint>();
            if (source == null || source.Count == 0)
                return normalized;

            foreach (var point in source.OrderBy(point => point.Time))
            {
                if (point.Time < 0)
                    continue;

                bool hasBpm = point.Bpm > 0 && double.IsFinite(point.Bpm);
                bool hasSignature = tryNormalizeTimeSignature(point.TimeSignature, out string signature);
                if (!hasBpm && !hasSignature)
                    continue;

                normalized.Add(new TimingPoint
                {
                    Time = point.Time,
                    Bpm = hasBpm ? point.Bpm : 0,
                    TimeSignature = hasSignature ? signature : null
                });
            }

            return normalized;
        }

        private static bool timingPointSetsEqual(IReadOnlyList<TimingPoint> a, IReadOnlyList<TimingPoint> b)
        {
            if (a.Count != b.Count)
                return false;

            for (int i = 0; i < a.Count; i++)
            {
                if (a[i].Time != b[i].Time)
                    return false;

                if (Math.Abs(a[i].Bpm - b[i].Bpm) > 0.0001)
                    return false;

                string aSig = normalizeTimeSignature(a[i].TimeSignature, string.Empty);
                string bSig = normalizeTimeSignature(b[i].TimeSignature, string.Empty);
                if (!string.Equals(aSig, bSig, StringComparison.Ordinal))
                    return false;
            }

            return true;
        }

        private static int positiveModulo(int value, int modulus)
        {
            if (modulus <= 0)
                return 0;

            int result = value % modulus;
            return result < 0 ? result + modulus : result;
        }

        private static double positiveRemainder(double value, double modulus)
        {
            if (modulus <= 0)
                return 0;

            double result = value % modulus;
            if (result < 0)
                result += modulus;

            return result;
        }

        private static double normaliseBpmToCommonRange(double bpm)
        {
            if (!double.IsFinite(bpm) || bpm <= 0)
                return TimingInfo.DefaultBpm;

            while (bpm < 70)
                bpm *= 2;
            while (bpm > 220)
                bpm /= 2;

            return bpm;
        }

        private static double getDownbeatWeight(string? component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return 1.0;

            string key = component.ToLowerInvariant();
            if (key.Contains("crash") || key.Contains("china"))
                return 2.0;
            if (key.Contains("kick"))
                return 1.8;
            if (key.Contains("snare"))
                return 1.5;
            if (key.Contains("ride"))
                return 1.3;
            if (key.Contains("hihat"))
                return 1.1;

            return 1.0;
        }

        private static double normaliseBeatDelta(double deltaMs, double beatLengthMs)
        {
            if (beatLengthMs <= 0)
                return deltaMs;

            while (deltaMs > beatLengthMs * 0.5)
                deltaMs -= beatLengthMs;

            while (deltaMs < -beatLengthMs * 0.5)
                deltaMs += beatLengthMs;

            return deltaMs;
        }

        private void remapHitObjectsForTiming(double oldBpm, double oldOffset, double newBpm, double newOffset, bool resnapToGrid)
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
                return;

            double oldBeatLengthMs = 60000.0 / Math.Max(1, oldBpm);
            double newBeatLengthMs = 60000.0 / Math.Max(1, newBpm);
            double snapIntervalMs = newBeatLengthMs / Math.Max(1, snapDivisor);

            foreach (var hit in beatmap.HitObjects)
            {
                double beatPosition = (hit.Time - oldOffset) / oldBeatLengthMs;
                double remappedTime = newOffset + beatPosition * newBeatLengthMs;

                if (resnapToGrid)
                    remappedTime = newOffset + Math.Round((remappedTime - newOffset) / snapIntervalMs) * snapIntervalMs;

                hit.Time = (int)Math.Round(Math.Max(0, remappedTime));
            }
        }

        private void resnapHitObjectsToGrid(double bpm, double offset)
        {
            if (beatmap == null || beatmap.HitObjects.Count == 0)
                return;

            double beatLengthMs = 60000.0 / Math.Max(1, bpm);
            double snapIntervalMs = beatLengthMs / Math.Max(1, snapDivisor);

            foreach (var hit in beatmap.HitObjects)
            {
                double snapped = offset + Math.Round((hit.Time - offset) / snapIntervalMs) * snapIntervalMs;
                hit.Time = (int)Math.Round(Math.Max(0, snapped));
            }
        }

        private partial class TimingSetupOverlayContainer : Container
        {
            public Container? DialogContainer { get; set; }
            public Action? DismissRequested { get; set; }

            public override bool HandlePositionalInput => true;

            protected override bool OnMouseDown(MouseDownEvent e)
            {
                bool handledByChildren = base.OnMouseDown(e);
                if (DialogContainer == null || !IsPresent || Alpha <= 0.01f)
                    return handledByChildren;

                if (!DialogContainer.ReceivePositionalInputAt(e.ScreenSpaceMousePosition))
                {
                    DismissRequested?.Invoke();
                    return true;
                }

                // Always consume while modal is visible so timeline/playfield never receive clicks behind it.
                return true;
            }

            protected override bool OnClick(ClickEvent e)
            {
                base.OnClick(e);
                return IsPresent && Alpha > 0.01f;
            }

            protected override bool OnDoubleClick(DoubleClickEvent e)
            {
                base.OnDoubleClick(e);
                return IsPresent && Alpha > 0.01f;
            }

            protected override bool OnScroll(ScrollEvent e)
            {
                bool handledByChildren = base.OnScroll(e);
                return handledByChildren || (IsPresent && Alpha > 0.01f);
            }
        }
    }
}
