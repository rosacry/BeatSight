using System;
using System.Collections.Generic;
using System.Globalization;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private SpriteText timingTapBpmText = null!;
        private SpriteText timingPlaybackRateText = null!;
        private readonly Queue<double> timingTapIntervals = new();
        private double? lastTimingTapAtMs;
        private const int maxTimingTapIntervals = 8;

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

            timingSetupHintText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                AllowMultiline = true,
                Font = BeatSightFont.Caption(11f),
                Colour = EditorColours.TextSecondary,
                Text = "Use slower playback while adjusting timing. Apply will update the map immediately."
            };

            timingPlaybackRateText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                Font = BeatSightFont.Caption(11.4f),
                Colour = EditorColours.TextSecondary,
                Text = $"Current playback rate: {playbackRate:0.00}x"
            };

            timingTapBpmText = new SpriteText
            {
                RelativeSizeAxes = Axes.X,
                Font = BeatSightFont.Caption(11.2f),
                Colour = EditorColours.TextSecondary,
                Text = "Tap BPM 4+ times for a stable estimate."
            };

            var panelContent = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(12, 0),
                Padding = new MarginPadding { Horizontal = 22, Vertical = 20 },
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
                        Text = "Set BPM and offset for the song. Optionally move existing notes to preserve beat position."
                    },
                    createTimingField("BPM", timingSetupBpmInput),
                    createTimingField("Offset (ms)", timingSetupOffsetInput),
                    createTimingField("Timing Playback",
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(8, 0),
                            Children = new Drawable[]
                            {
                                new FillFlowContainer
                                {
                                    RelativeSizeAxes = Axes.X,
                                    AutoSizeAxes = Axes.Y,
                                    Direction = FillDirection.Horizontal,
                                    Spacing = new Vector2(8, 0),
                                    Children = new Drawable[]
                                    {
                                        createTimingQuickButton("25%", () => setTimingPlaybackRate(0.25), 62f),
                                        createTimingQuickButton("50%", () => setTimingPlaybackRate(0.5), 62f),
                                        createTimingQuickButton("75%", () => setTimingPlaybackRate(0.75), 62f),
                                        createTimingQuickButton("100%", () => setTimingPlaybackRate(1.0), 68f),
                                        createTimingQuickButton("Play/Pause", togglePlayback, 110f)
                                    }
                                },
                                timingPlaybackRateText
                            }
                        }),
                    createTimingField("Tempo Detection",
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(8, 0),
                            Children = new Drawable[]
                            {
                                new FillFlowContainer
                                {
                                    RelativeSizeAxes = Axes.X,
                                    AutoSizeAxes = Axes.Y,
                                    Direction = FillDirection.Horizontal,
                                    Spacing = new Vector2(8, 0),
                                    Children = new Drawable[]
                                    {
                                        createTimingQuickButton("Tap BPM", registerTimingTap, 110f),
                                        createTimingQuickButton("Clear", resetTimingTapEstimator, 72f)
                                    }
                                },
                                timingTapBpmText
                            }
                        }),
                    timingMoveNotesCheckbox,
                    timingResnapNotesCheckbox,
                    timingSetupHintText,
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(10, 0),
                        Margin = new MarginPadding { Top = 8 },
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

            timingSetupOverlay = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Alpha = 0,
                AlwaysPresent = false,
                Depth = -95,
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
                        Child = new Container
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            RelativeSizeAxes = Axes.Both,
                            Size = new Vector2(0.46f, 0.62f),
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
                                panelContent
                            }
                        }
                    }
                }
            };
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
            timingResnapNotesCheckbox.LabelText = $"Resnap notes to current grid (1/{snapDivisor})";
            timingSetupHintText.Text = $"Current snap: 1/{snapDivisor}. Use rate presets (or Ctrl+[ / Ctrl+]) while tuning. In preview: LMB add, RMB remove.";
            timingPlaybackRateText.Text = $"Current playback rate: {playbackRate:0.00}x";
            resetTimingTapEstimator();

            timingSetupOverlay.Show();
            timingSetupOverlay.AlwaysPresent = true;
            timingSetupOverlay.FadeIn(120, Easing.OutQuint);
            Schedule(() => GetContainingFocusManager()?.ChangeFocus(timingSetupBpmInput));
        }

        private void closeTimingSetupOverlay()
        {
            if (timingSetupOverlay == null || !timingSetupOverlay.IsPresent)
                return;

            timingSetupOverlay.FadeOut(90, Easing.OutQuint);
            Scheduler.AddDelayed(() =>
            {
                timingSetupOverlay.Hide();
                timingSetupOverlay.AlwaysPresent = false;
            }, 95);
        }

        private void applyTimingSetupChanges()
        {
            if (beatmap == null)
            {
                closeTimingSetupOverlay();
                return;
            }

            if (!tryParseTimingSetupInputs(out double newBpm, out double newOffset))
                return;

            double oldBpm = Math.Max(20, beatmap.Timing.Bpm);
            double oldOffset = beatmap.Timing.Offset;
            bool bpmChanged = Math.Abs(newBpm - oldBpm) > 0.0001;
            bool offsetChanged = Math.Abs(newOffset - oldOffset) > 0.5;

            if (!bpmChanged && !offsetChanged)
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
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));

            suppressInspectorFieldSync = true;
            if (bpmInput != null)
                bpmInput.Current.Value = beatmap.Timing.Bpm.ToString("0.##", CultureInfo.InvariantCulture);
            if (offsetInput != null)
                offsetInput.Current.Value = beatmap.Timing.Offset.ToString(CultureInfo.InvariantCulture);
            suppressInspectorFieldSync = false;

            timeline?.SetSnap(snapDivisor, beatmap.Timing.Bpm);
            markUnsaved();
            reloadTimeline();
            updateInspectorStats();

            closeTimingSetupOverlay();
            appendStatusDetail($"Timing applied: {beatmap.Timing.Bpm:0.##} BPM, {beatmap.Timing.Offset:+#;-#;0} ms");
        }

        private void setTimingPlaybackRate(double rate)
        {
            setPlaybackRate(rate, announce: false);
            if (timingPlaybackRateText != null)
                timingPlaybackRateText.Text = $"Current playback rate: {playbackRate:0.00}x";
            appendStatusDetail($"Playback rate {playbackRate:0.00}x");
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

        private void resetTimingTapEstimator()
        {
            timingTapIntervals.Clear();
            lastTimingTapAtMs = null;
            if (timingTapBpmText != null)
                timingTapBpmText.Text = "Tap BPM 4+ times for a stable estimate.";
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
                timingTapBpmText.Text = "Tap BPM 4+ times for a stable estimate.";
                return;
            }

            double estimatedBpm = Math.Clamp(60000.0 / averageInterval, 20, 400);
            timingTapBpmText.Text = $"Estimated BPM: {estimatedBpm:0.##} ({timingTapIntervals.Count + 1} taps)";
            timingSetupBpmInput.Current.Value = estimatedBpm.ToString("0.##", CultureInfo.InvariantCulture);
        }

        private bool isTimingSetupOverlayVisible()
            => timingSetupOverlay != null && timingSetupOverlay.IsPresent && timingSetupOverlay.Alpha > 0.01f;

        private bool tryParseTimingSetupInputs(out double bpm, out double offset)
        {
            bpm = 120;
            offset = 0;
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

            bpm = Math.Clamp(bpm, 20, 400);
            offset = Math.Clamp(offset, -10000, 10000);
            return valid;
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
    }
}
