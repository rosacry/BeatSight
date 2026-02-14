using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.AI;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Components;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Logging;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void runPipeline()
        {
            if (string.IsNullOrEmpty(beatmapPath))
            {
                Logger.Log("Cannot run pipeline: Beatmap path is not set. Please save the beatmap first.", LoggingTarget.Runtime, LogLevel.Error);
                return;
            }

            if (beatmap == null)
                return;

            string audioPath = Path.Combine(Path.GetDirectoryName(beatmapPath)!, beatmap.Audio.Filename);
            if (!File.Exists(audioPath))
            {
                Logger.Log($"Cannot run pipeline: Audio file not found at {audioPath}", LoggingTarget.Runtime, LogLevel.Error);
                return;
            }

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

            var audioTrackForGeneration = new ImportedAudioTrack(
                audioPath,
                audioPath,
                Path.GetFileName(audioPath),
                Path.GetFileName(audioPath),
                new FileInfo(audioPath).Length,
                null
            );

            Logger.Log("Starting AI pipeline...", LoggingTarget.Runtime, LogLevel.Important);
            logText.Clear();
            logText.AddParagraph("Starting AI pipeline...", t => t.Colour = Color4.Cyan);
            logOverlay.FadeIn(200);

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
                            Logger.Log("Pipeline completed successfully!", LoggingTarget.Runtime, LogLevel.Important);

                            if (result.Beatmap != null)
                            {
                                beatmap = result.Beatmap;
                                beatmapPath = result.BeatmapPath;
                                trackLength = beatmap.Audio.Duration;
                                reloadTimeline();
                                populateInspectorFromBeatmap();

                                if (result.DebugAnalysisPath != null && File.Exists(result.DebugAnalysisPath))
                                {
                                    try
                                    {
                                        string json = File.ReadAllText(result.DebugAnalysisPath);
                                        timeline?.LoadDebugData(json);
                                    }
                                    catch (Exception ex)
                                    {
                                        Logger.Log($"Failed to load debug analysis: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                                    }
                                }

                                setStatusDetail("Generated new beatmap");
                            }
                        }
                        else
                        {
                            logText.AddParagraph($"Pipeline failed: {result.Error}", t => t.Colour = Color4.Red);
                            Logger.Log($"Pipeline failed: {result.Error}", LoggingTarget.Runtime, LogLevel.Error);
                        }
                    });
                }
                catch (Exception ex)
                {
                    Schedule(() =>
                    {
                        logText.AddParagraph($"Pipeline execution error: {ex.Message}", t => t.Colour = Color4.Red);
                        Logger.Log($"Pipeline execution error: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
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
                Alpha = 0,
                Depth = -100,
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
                    Logger.Error(ex, "Region regeneration failed");
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
