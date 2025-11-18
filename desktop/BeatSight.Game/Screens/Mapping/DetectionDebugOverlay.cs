using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.AI.Generation;
using BeatSight.Game.Audio;
using BeatSight.Game.Audio.Analysis;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Mapping
{
    public partial class DetectionDebugOverlay : CompositeDrawable
    {
        private const double pixelsPerSecond = 180;
        private const float waveformAlpha = 0.35f;

        private readonly DebugScrollContainer scroll;
        private readonly Container content;
        private readonly MiniWaveformDrawable waveformDrawable;
        private readonly EnvelopeDrawable envelopeDrawable;
        private readonly Container peakLayer;
        private readonly Container gridLayer;
        private readonly FillFlowContainer sectionSummaryFlow;
        private readonly SpriteText placeholderText;
        private SpriteText legendSummaryText = null!;
        private readonly BindableBool showWaveform = new BindableBool(true);
        private readonly BindableBool showEnvelope = new BindableBool(true);
        private readonly BindableBool showThreshold = new BindableBool(true);
        private readonly BindableBool showPeaks = new BindableBool(true);
        private readonly BindableBool showBeatGrid = new BindableBool(true);

        private DrumOnsetAnalysis? analysis;
        private double durationSeconds;
        private DetectionStats? statsSummary;

        public DetectionDebugOverlay()
        {
            RelativeSizeAxes = Axes.Both;
            Masking = true;
            CornerRadius = 10;

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(16, 20, 31, 200)
                },
                scroll = new DebugScrollContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    ScrollbarOverlapsContent = false,
                    Child = content = new Container
                    {
                        RelativeSizeAxes = Axes.Y,
                        Masking = true,
                        CornerRadius = 8,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(24, 28, 40, 255)
                            },
                            gridLayer = new Container
                            {
                                RelativeSizeAxes = Axes.Both
                            },
                            waveformDrawable = new MiniWaveformDrawable
                            {
                                RelativeSizeAxes = Axes.Both,
                                Alpha = waveformAlpha
                            },
                            envelopeDrawable = new EnvelopeDrawable
                            {
                                RelativeSizeAxes = Axes.Both,
                                Anchor = Anchor.BottomLeft,
                                Origin = Anchor.BottomLeft
                            },
                            peakLayer = new Container
                            {
                                RelativeSizeAxes = Axes.Both
                            }
                        }
                    }
                },
                placeholderText = new SpriteText
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Text = "No analyzer data yet...",
                    Font = BeatSightFont.Body(18f),
                    Colour = new Color4(200, 205, 220, 200),
                    Alpha = 0
                },
                createLegendPanel(),
                new Container
                {
                    Anchor = Anchor.TopRight,
                    Origin = Anchor.TopRight,
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Padding = new MarginPadding(12),
                    Child = sectionSummaryFlow = new FillFlowContainer
                    {
                        Anchor = Anchor.TopRight,
                        Origin = Anchor.TopRight,
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 6)
                    }
                }
            };

            showWaveform.BindValueChanged(e => updateWaveformVisibility(e.NewValue, true), true);
            showEnvelope.BindValueChanged(_ => updateEnvelopeVisibility(true), true);
            showThreshold.BindValueChanged(_ => updateEnvelopeVisibility(true), true);
            showPeaks.BindValueChanged(e => updatePeaksVisibility(e.NewValue, true), true);
            showBeatGrid.BindValueChanged(e => updateGridVisibility(e.NewValue, true), true);
        }

        public void Clear()
        {
            analysis = null;
            waveformDrawable.SetData(null, pixelsPerSecond);
            envelopeDrawable.SetEnvelope(Array.Empty<double>(), Array.Empty<double>(), 1, 1);
            peakLayer.Clear();
            gridLayer.Clear();
            sectionSummaryFlow.Clear();
            durationSeconds = 0;
            content.Width = 800;
            ShowPlaceholder("Waiting for analysis...");
            updateWaveformVisibility(showWaveform.Value, false);
            envelopeDrawable.SetChannelVisibility(showEnvelope.Value, showThreshold.Value, animate: false);
            updatePeaksVisibility(showPeaks.Value, false);
            updateGridVisibility(showBeatGrid.Value, false);
            UpdateStatsSummary(null);
        }

        public void SetData(WaveformData? waveform, DrumOnsetAnalysis? analysis)
        {
            this.analysis = analysis;
            durationSeconds = analysis?.DurationSeconds ?? waveform?.DurationSeconds ?? 0;
            double width = Math.Max(1, durationSeconds * pixelsPerSecond);
            content.Width = (float)Math.Clamp(width, 800, 6000);

            waveformDrawable.SetData(waveform, pixelsPerSecond);
            updateWaveformVisibility(showWaveform.Value, false);

            if (analysis != null)
            {
                if (analysis.Peaks.Count == 0)
                    ShowPlaceholder("Analysis pending...");
                else
                    placeholderText.FadeOut(150);

                envelopeDrawable.SetEnvelope(analysis.Envelope, analysis.AdaptiveThreshold, pixelsPerSecond, analysis.HopLength / analysis.SampleRate);
                envelopeDrawable.SetChannelVisibility(showEnvelope.Value, showThreshold.Value, animate: false);
                rebuildPeaks();
                rebuildGrid();
                rebuildSections();
            }
            else
            {
                envelopeDrawable.SetEnvelope(Array.Empty<double>(), Array.Empty<double>(), pixelsPerSecond, 1);
                peakLayer.Clear();
                gridLayer.Clear();
                sectionSummaryFlow.Clear();
                ShowPlaceholder("Waiting for analysis...");
            }

            updatePeaksVisibility(showPeaks.Value, false);
            updateGridVisibility(showBeatGrid.Value, false);
            updateEnvelopeVisibility(false);

            scroll.ScrollToStart();
        }

        public void ShowPlaceholder(string message)
        {
            placeholderText.Text = message;
            placeholderText.FadeIn(150);
        }

        public void UpdateStatsSummary(DetectionStats? stats)
        {
            statsSummary = stats;
            refreshLegendSummary();
        }

        private void refreshLegendSummary()
        {
            if (legendSummaryText == null)
                return;

            if (statsSummary == null)
            {
                legendSummaryText.Text = "No detection stats yet.";
                if (legendSummaryText.IsLoaded)
                    legendSummaryText.FadeTo(0.7f, 120, Easing.OutQuint);
                else
                    legendSummaryText.Alpha = 0.7f;
                return;
            }

            var stats = statsSummary;
            var parts = new List<string>();

            if (stats.PeakCount > 0)
                parts.Add($"Peaks {stats.PeakCount}");

            if (stats.EstimatedBpm > 0)
                parts.Add($"~{stats.EstimatedBpm:0.#} BPM");

            if (stats.QuantizationCoverage > 0)
                parts.Add($"Coverage {stats.QuantizationCoverage:P0}");

            if (stats.QuantizationMeanErrorMs > 0)
                parts.Add($"Mean err {stats.QuantizationMeanErrorMs:0.#}ms");

            parts.Add($"Grid {stats.Grid}");
            parts.Add($"Score {stats.ConfidenceScore:P0}");

            if (stats.TryGetLowConfidenceMessage(out _))
                parts.Add("⚠ Low confidence");

            legendSummaryText.Text = string.Join(" • ", parts);

            if (legendSummaryText.IsLoaded)
                legendSummaryText.FadeTo(1f, 120, Easing.OutQuint);
            else
                legendSummaryText.Alpha = 1f;
        }

        private Drawable createLegendPanel()
        {
            return new Container
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                AutoSizeAxes = Axes.Both,
                Margin = new MarginPadding { Left = 12, Top = 12 },
                Padding = new MarginPadding(12),
                Masking = true,
                CornerRadius = 6,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(26, 30, 45, 220)
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 6),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "Legend & Layers",
                                Font = BeatSightFont.Section(16f),
                                Colour = new Color4(210, 218, 235, 255)
                            },
                            legendSummaryText = new SpriteText
                            {
                                Text = "No detection stats yet.",
                                Font = BeatSightFont.Caption(14f),
                                Colour = new Color4(190, 195, 210, 255),
                                Alpha = 0.7f
                            },
                            createLegendToggle("Waveform", new Color4(110, 170, 255, 255), showWaveform),
                            createLegendToggle("Envelope", new Color4(120, 240, 170, 255), showEnvelope),
                            createLegendToggle("Threshold", new Color4(240, 240, 255, 200), showThreshold),
                            createLegendToggle("Peaks", new Color4(255, 180, 120, 255), showPeaks),
                            createLegendToggle("Beat Grid", new Color4(120, 150, 210, 255), showBeatGrid)
                        }
                    }
                }
            };
        }

        private Drawable createLegendToggle(string label, Color4 colour, BindableBool bindable)
        {
            var checkbox = new BasicCheckbox
            {
                LabelText = label
            };
            checkbox.Current.BindTo(bindable);

            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(6, 0),
                Children = new Drawable[]
                {
                    new Container
                    {
                        Size = new Vector2(12, 12),
                        Masking = true,
                        CornerRadius = 3,
                        Child = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = colour
                        }
                    },
                    checkbox
                }
            };
        }

        private void updateWaveformVisibility(bool visible, bool animate)
        {
            float target = visible ? waveformAlpha : 0f;
            if (!animate || !waveformDrawable.IsLoaded)
                waveformDrawable.Alpha = target;
            else
                waveformDrawable.FadeTo(target, 120, Easing.OutQuint);
        }

        private void updateEnvelopeVisibility(bool animate)
        {
            envelopeDrawable.SetChannelVisibility(showEnvelope.Value, showThreshold.Value, animate);
        }

        private void updatePeaksVisibility(bool visible, bool animate)
        {
            setContainerVisibility(peakLayer, visible, animate);
        }

        private void updateGridVisibility(bool visible, bool animate)
        {
            setContainerVisibility(gridLayer, visible, animate);
        }

        private static void setContainerVisibility(Container container, bool visible, bool animate)
        {
            float target = visible ? 1f : 0f;
            if (!animate || !container.IsLoaded)
                container.Alpha = target;
            else
                container.FadeTo(target, 120, Easing.OutQuint);
        }

        private void rebuildPeaks()
        {
            peakLayer.Clear();
            if (analysis == null || analysis.Peaks.Count == 0)
                return;

            foreach (var peak in analysis.Peaks)
            {
                var marker = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 2,
                    Colour = new Color4(255, 180, 120, peak.Confidence >= 0.7 ? 255 : 160),
                    Alpha = 0.8f,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomCentre,
                    X = (float)(peak.Time * pixelsPerSecond),
                    Height = 0.75f
                };

                peakLayer.Add(marker);
            }
        }

        private void rebuildGrid()
        {
            gridLayer.Clear();
            if (analysis == null)
                return;

            foreach (double time in analysis.GetBeatGridTimes())
            {
                var line = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 1,
                    Colour = new Color4(120, 150, 210, 140),
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomCentre,
                    X = (float)(time * pixelsPerSecond),
                    Height = 1
                };

                gridLayer.Add(line);
            }
        }

        private void rebuildSections()
        {
            sectionSummaryFlow.Clear();
            if (analysis == null || analysis.Sections.Count == 0)
                return;

            foreach (var section in analysis.Sections.OrderBy(s => s.Index).Take(12))
            {
                sectionSummaryFlow.Add(new SpriteText
                {
                    Text = $"Section {section.Index}: {section.Count} hits ({section.Density:0.00}/s)",
                    Font = BeatSightFont.Body(18f),
                    Colour = new Color4(180, 190, 215, 255)
                });
            }
        }

        private partial class DebugScrollContainer : BasicScrollContainer
        {
            public void ScrollToStart(bool animated = true)
            {
                ScrollTo(0, animated);
            }
        }

        private partial class MiniWaveformDrawable : CompositeDrawable
        {
            private WaveformData? waveform;
            private double currentPixelsPerSecond = pixelsPerSecond;
            private readonly FillFlowContainer barFlow;

            public MiniWaveformDrawable()
            {
                RelativeSizeAxes = Axes.Both;
                Masking = true;
                CornerRadius = 6;

                InternalChild = barFlow = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.Y,
                    AutoSizeAxes = Axes.X,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(0.4f, 0)
                };
            }

            public void SetData(WaveformData? waveform, double pixelsPerSecond)
            {
                this.waveform = waveform;
                currentPixelsPerSecond = Math.Max(1, pixelsPerSecond);
                rebuild();
            }

            private void rebuild()
            {
                barFlow.Clear();

                if (waveform == null || waveform.BucketCount == 0)
                    return;

                int downsampleFactor = Math.Max(1, waveform.BucketCount / 800);
                for (int i = 0; i < waveform.BucketCount; i += downsampleFactor)
                {
                    float amplitude = 0f;
                    for (int j = 0; j < downsampleFactor && i + j < waveform.BucketCount; j++)
                    {
                        float value = Math.Max(Math.Abs(waveform.Minima[i + j]), Math.Abs(waveform.Maxima[i + j]));
                        amplitude = Math.Max(amplitude, value);
                    }

                    float height = Math.Clamp(amplitude * 1.3f, 0.08f, 1f);
                    double bucketSeconds = waveform.BucketDurationSeconds * downsampleFactor;
                    double bucketWidth = Math.Max(1, currentPixelsPerSecond * bucketSeconds);

                    barFlow.Add(new Container
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = (float)bucketWidth,
                        Child = new Box
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            RelativeSizeAxes = Axes.Y,
                            Height = height,
                            Width = (float)Math.Max(1, bucketWidth),
                            Colour = new Color4(110, 170, 255, 120)
                        }
                    });
                }
            }
        }

        private partial class EnvelopeDrawable : CompositeDrawable
        {
            private readonly FillFlowContainer envelopeFlow;
            private readonly FillFlowContainer thresholdFlow;

            public EnvelopeDrawable()
            {
                RelativeSizeAxes = Axes.Both;
                Masking = true;

                InternalChildren = new Drawable[]
                {
                    thresholdFlow = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(0.4f, 0)
                    },
                    envelopeFlow = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(0.4f, 0)
                    }
                };
            }

            public void SetEnvelope(IReadOnlyList<double> envelope, IReadOnlyList<double> threshold, double pixelsPerSecond, double secondsPerFrame)
            {
                envelopeFlow.Clear();
                thresholdFlow.Clear();

                if (envelope.Count == 0)
                    return;

                int step = Math.Max(1, envelope.Count / 900);
                double stableFrameSeconds = Math.Max(secondsPerFrame, 1.0 / 44100.0);
                for (int p = 0; p < envelope.Count; p += step)
                {
                    double value = envelope[p];
                    double thresh = p < threshold.Count ? threshold[p] : 0;
                    double frameSeconds = stableFrameSeconds * step;
                    double width = Math.Max(1, pixelsPerSecond * frameSeconds);

                    thresholdFlow.Add(new Container
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = (float)width,
                        Child = new Box
                        {
                            Anchor = Anchor.BottomCentre,
                            Origin = Anchor.BottomCentre,
                            RelativeSizeAxes = Axes.Y,
                            Height = (float)Math.Clamp(thresh, 0, 1),
                            Colour = new Color4(255, 255, 255, 60)
                        }
                    });

                    envelopeFlow.Add(new Container
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = (float)width,
                        Child = new Box
                        {
                            Anchor = Anchor.BottomCentre,
                            Origin = Anchor.BottomCentre,
                            RelativeSizeAxes = Axes.Y,
                            Height = (float)Math.Clamp(value, 0, 1),
                            Colour = new Color4(120, 240, 170, 220)
                        }
                    });
                }
            }

            public void SetChannelVisibility(bool envelopeVisible, bool thresholdVisible, bool animate = true)
            {
                setVisibility(envelopeFlow, envelopeVisible, animate);
                setVisibility(thresholdFlow, thresholdVisible, animate);
            }

            private static void setVisibility(Drawable drawable, bool visible, bool animate)
            {
                float target = visible ? 1f : 0f;
                if (!animate || !drawable.IsLoaded)
                    drawable.Alpha = target;
                else
                    drawable.FadeTo(target, 120, Easing.OutQuint);
            }
        }
    }
}
