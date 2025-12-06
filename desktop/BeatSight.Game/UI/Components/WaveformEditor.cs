// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Cursor;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Localisation;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// An interactive waveform display with zoom, scroll, and selection capabilities.
    /// Used for beatmap editing and audio navigation.
    /// </summary>
    public partial class WaveformEditor : CompositeDrawable, IHasTooltip
    {
        /// <summary>
        /// Event fired when the playback position changes via user interaction.
        /// </summary>
        public event Action<double>? OnSeek;

        /// <summary>
        /// Event fired when a selection is made.
        /// </summary>
        public event Action<double, double>? OnSelectionChanged;

        /// <summary>
        /// Event fired when zoom level changes.
        /// </summary>
        public event Action<float>? OnZoomChanged;

        /// <summary>
        /// Current playback position in milliseconds.
        /// </summary>
        public double CurrentTime
        {
            get => currentTime;
            set
            {
                currentTime = Math.Clamp(value, 0, Duration);
                updatePlayhead();
            }
        }

        /// <summary>
        /// Total duration in milliseconds.
        /// </summary>
        public double Duration { get; set; } = 180000;

        /// <summary>
        /// Current zoom level (1.0 = full view).
        /// </summary>
        public float Zoom
        {
            get => zoom;
            set
            {
                zoom = Math.Clamp(value, MinZoom, MaxZoom);
                updateWaveform();
                OnZoomChanged?.Invoke(zoom);
            }
        }

        /// <summary>
        /// Minimum zoom level.
        /// </summary>
        public float MinZoom { get; set; } = 1f;

        /// <summary>
        /// Maximum zoom level.
        /// </summary>
        public float MaxZoom { get; set; } = 50f;

        /// <summary>
        /// Whether selection mode is enabled.
        /// </summary>
        public bool SelectionEnabled { get; set; } = true;

        /// <summary>
        /// Primary waveform color.
        /// </summary>
        public Color4 WaveformColour { get; set; } = Color4Extensions.FromHex("0ea5e9");

        /// <summary>
        /// Selection highlight color.
        /// </summary>
        public Color4 SelectionColour { get; set; } = Color4Extensions.FromHex("ec489940");

        /// <summary>
        /// Playhead color.
        /// </summary>
        public Color4 PlayheadColour { get; set; } = Color4.White;

        public LocalisableString TooltipText => $"{TimeSpan.FromMilliseconds(CurrentTime):mm\\:ss\\.fff}";

        private double currentTime;
        private float zoom = 1f;
        private double scrollOffset;
        private double? selectionStart;
        private double? selectionEnd;

        private Container waveformContainer = null!;
        private Container selectionOverlay = null!;
        private Box playhead = null!;
        private Box selectionBox = null!;
        private Container timelineContainer = null!;
        private readonly List<Container> waveformBars = new List<Container>();

        private bool isDragging;
        private bool isSelecting;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            Height = 120;

            InternalChildren = new Drawable[]
            {
                // Background
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4Extensions.FromHex("111827"),
                },

                // Timeline container
                timelineContainer = new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 24,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("1f2937"),
                    }
                },

                // Waveform container
                waveformContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Top = 24 },
                },

                // Selection overlay
                selectionOverlay = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Top = 24 },
                    Child = selectionBox = new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Colour = SelectionColour,
                        Alpha = 0,
                    }
                },

                // Playhead
                playhead = new Box
                {
                    Width = 2,
                    RelativeSizeAxes = Axes.Y,
                    Colour = PlayheadColour,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                },
            };

            createWaveform();
            createTimeline();
        }

        private void createWaveform()
        {
            waveformContainer.Clear();
            waveformBars.Clear();

            int barCount = 100;
            float barWidth = 1f / barCount;

            for (int i = 0; i < barCount; i++)
            {
                // Generate demo waveform pattern
                float height = 0.2f + 0.6f * (float)(Math.Sin(i * 0.3) * 0.5 + 0.5) *
                               (float)(Math.Cos(i * 0.7) * 0.3 + 0.7) +
                               (float)new Random(i).NextDouble() * 0.2f;

                var bar = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.X,
                    X = (float)i / barCount,
                    Width = barWidth * 0.8f,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                    Masking = true,
                    CornerRadius = 1,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = (Height - 24) * height,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Colour = WaveformColour,
                    }
                };

                waveformBars.Add(bar);
                waveformContainer.Add(bar);
            }
        }

        private void createTimeline()
        {
            // Add time markers
            int markerCount = 10;

            for (int i = 0; i <= markerCount; i++)
            {
                double time = Duration * i / markerCount;
                var timeSpan = TimeSpan.FromMilliseconds(time);

                timelineContainer.Add(new Container
                {
                    RelativePositionAxes = Axes.X,
                    X = (float)i / markerCount,
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.Centre,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            Width = 1,
                            Height = 8,
                            Colour = Color4Extensions.FromHex("6b7280"),
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                        },
                        new SpriteText
                        {
                            Text = $"{timeSpan:mm\\:ss}",
                            Font = new FontUsage("Torus", 10),
                            Colour = Color4Extensions.FromHex("9ca3af"),
                            Anchor = Anchor.BottomCentre,
                            Origin = Anchor.TopCentre,
                            Y = 2,
                        }
                    }
                });
            }
        }

        private void updateWaveform()
        {
            // Update waveform display based on zoom and scroll
            float visibleWidth = 1f / zoom;

            foreach (var bar in waveformBars)
            {
                // Scale and position bars based on zoom
                bar.Scale = new Vector2(zoom, 1);
            }
        }

        private void updatePlayhead()
        {
            if (Duration <= 0) return;

            float position = (float)(currentTime / Duration);
            playhead.X = DrawWidth * position;
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            if (e.Button == MouseButton.Left)
            {
                isDragging = true;

                if (SelectionEnabled && e.ShiftPressed)
                {
                    isSelecting = true;
                    selectionStart = getTimeFromPosition(e.MousePosition.X);
                }
                else
                {
                    seekToPosition(e.MousePosition.X);
                }

                return true;
            }

            return base.OnMouseDown(e);
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            if (e.Button == MouseButton.Left)
            {
                isDragging = false;

                if (isSelecting && selectionStart.HasValue)
                {
                    selectionEnd = getTimeFromPosition(e.MousePosition.X);
                    OnSelectionChanged?.Invoke(
                        Math.Min(selectionStart.Value, selectionEnd.Value),
                        Math.Max(selectionStart.Value, selectionEnd.Value)
                    );
                }

                isSelecting = false;
            }

            base.OnMouseUp(e);
        }

        protected override bool OnDragStart(DragStartEvent e)
        {
            return isDragging;
        }

        protected override void OnDrag(DragEvent e)
        {
            if (isSelecting && selectionStart.HasValue)
            {
                updateSelection(e.MousePosition.X);
            }
            else if (isDragging)
            {
                seekToPosition(e.MousePosition.X);
            }

            base.OnDrag(e);
        }

        protected override bool OnScroll(ScrollEvent e)
        {
            if (e.ControlPressed)
            {
                // Zoom
                float zoomDelta = e.ScrollDelta.Y > 0 ? 1.2f : 0.8f;
                Zoom *= zoomDelta;
                return true;
            }
            else
            {
                // Scroll horizontally
                scrollOffset = Math.Clamp(scrollOffset - e.ScrollDelta.Y * 1000, 0, Duration);
                return true;
            }
        }

        private void seekToPosition(float x)
        {
            double time = getTimeFromPosition(x);
            CurrentTime = time;
            OnSeek?.Invoke(time);
        }

        private double getTimeFromPosition(float x)
        {
            float normalizedX = Math.Clamp(x / DrawWidth, 0, 1);
            return normalizedX * Duration + scrollOffset;
        }

        private void updateSelection(float x)
        {
            if (!selectionStart.HasValue) return;

            double currentPos = getTimeFromPosition(x);
            double start = Math.Min(selectionStart.Value, currentPos);
            double end = Math.Max(selectionStart.Value, currentPos);

            float startX = (float)((start - scrollOffset) / Duration * DrawWidth);
            float endX = (float)((end - scrollOffset) / Duration * DrawWidth);

            selectionBox.X = startX;
            selectionBox.Width = endX - startX;
            selectionBox.Alpha = 1;
        }

        /// <summary>
        /// Clears the current selection.
        /// </summary>
        public void ClearSelection()
        {
            selectionStart = null;
            selectionEnd = null;
            selectionBox.FadeOut(200);
        }

        /// <summary>
        /// Sets the waveform data.
        /// </summary>
        /// <param name="amplitudes">Array of amplitude values (0-1) for each sample point.</param>
        public void SetWaveformData(float[] amplitudes)
        {
            if (amplitudes == null || amplitudes.Length == 0) return;

            waveformContainer.Clear();
            waveformBars.Clear();

            int barCount = Math.Min(amplitudes.Length, 500);
            float barWidth = 1f / barCount;
            int samplesPerBar = amplitudes.Length / barCount;

            for (int i = 0; i < barCount; i++)
            {
                // Average samples for this bar
                float avgAmplitude = 0;
                int start = i * samplesPerBar;
                int end = Math.Min(start + samplesPerBar, amplitudes.Length);

                for (int j = start; j < end; j++)
                {
                    avgAmplitude += Math.Abs(amplitudes[j]);
                }
                avgAmplitude /= (end - start);

                float height = Math.Clamp(avgAmplitude * 2, 0.1f, 1f);

                var bar = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.X,
                    X = (float)i / barCount,
                    Width = barWidth * 0.8f,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                    Masking = true,
                    CornerRadius = 1,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = (Height - 24) * height,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Colour = WaveformColour,
                    }
                };

                waveformBars.Add(bar);
                waveformContainer.Add(bar);
            }
        }
    }

    /// <summary>
    /// A compact waveform view for track previews.
    /// </summary>
    public partial class MiniWaveform : CompositeDrawable
    {
        /// <summary>
        /// Progress value (0-1).
        /// </summary>
        public float Progress
        {
            get => progress;
            set
            {
                progress = Math.Clamp(value, 0f, 1f);
                updateProgress();
            }
        }

        /// <summary>
        /// Active/played waveform color.
        /// </summary>
        public Color4 ActiveColour { get; set; } = Color4Extensions.FromHex("0ea5e9");

        /// <summary>
        /// Inactive/unplayed waveform color.
        /// </summary>
        public Color4 InactiveColour { get; set; } = Color4Extensions.FromHex("374151");

        private float progress;
        private readonly List<Box> bars = new List<Box>();

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            Height = 32;

            createBars();
        }

        private void createBars()
        {
            ClearInternal();
            bars.Clear();

            int barCount = 50;
            float barWidth = DrawWidth > 0 ? DrawWidth / barCount : 4;

            for (int i = 0; i < barCount; i++)
            {
                float height = 0.3f + 0.7f * (float)(Math.Sin(i * 0.4) * 0.5 + 0.5);

                var bar = new Box
                {
                    Width = barWidth * 0.7f,
                    Height = Height * height,
                    X = i * barWidth,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                    Colour = InactiveColour,
                };

                bars.Add(bar);
                AddInternal(bar);
            }

            updateProgress();
        }

        private void updateProgress()
        {
            int activeCount = (int)(bars.Count * progress);

            for (int i = 0; i < bars.Count; i++)
            {
                bars[i].FadeColour(i < activeCount ? ActiveColour : InactiveColour, 100);
            }
        }

        /// <summary>
        /// Sets waveform amplitudes.
        /// </summary>
        public void SetAmplitudes(float[] amplitudes)
        {
            if (amplitudes == null || amplitudes.Length == 0) return;

            int barCount = Math.Min(amplitudes.Length, 50);
            int samplesPerBar = amplitudes.Length / barCount;

            ClearInternal();
            bars.Clear();

            float barWidth = DrawWidth > 0 ? DrawWidth / barCount : 4;

            for (int i = 0; i < barCount; i++)
            {
                float avgAmplitude = 0;
                int start = i * samplesPerBar;
                int end = Math.Min(start + samplesPerBar, amplitudes.Length);

                for (int j = start; j < end; j++)
                {
                    avgAmplitude += Math.Abs(amplitudes[j]);
                }
                avgAmplitude /= (end - start);

                float height = Math.Clamp(avgAmplitude * 2, 0.2f, 1f);

                var bar = new Box
                {
                    Width = barWidth * 0.7f,
                    Height = Height * height,
                    X = i * barWidth,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                    Colour = InactiveColour,
                };

                bars.Add(bar);
                AddInternal(bar);
            }

            updateProgress();
        }
    }

    /// <summary>
    /// A beat grid overlay for the waveform editor.
    /// Shows beat/measure markers for rhythm visualization.
    /// </summary>
    public partial class BeatGrid : CompositeDrawable
    {
        /// <summary>
        /// Tempo in BPM.
        /// </summary>
        public float BPM
        {
            get => bpm;
            set
            {
                bpm = value;
                regenerateGrid();
            }
        }

        /// <summary>
        /// Beats per measure.
        /// </summary>
        public int BeatsPerMeasure { get; set; } = 4;

        /// <summary>
        /// Grid offset in milliseconds.
        /// </summary>
        public double Offset { get; set; }

        /// <summary>
        /// Duration of the audio in milliseconds.
        /// </summary>
        public double Duration { get; set; }

        /// <summary>
        /// Beat line color.
        /// </summary>
        public Color4 BeatColour { get; set; } = Color4Extensions.FromHex("6b728080");

        /// <summary>
        /// Measure line color.
        /// </summary>
        public Color4 MeasureColour { get; set; } = Color4Extensions.FromHex("9ca3afcc");

        private float bpm = 120;
        private Container gridContainer = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChild = gridContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
            };

            regenerateGrid();
        }

        private void regenerateGrid()
        {
            gridContainer.Clear();

            if (bpm <= 0 || Duration <= 0) return;

            double beatDuration = 60000 / bpm;
            int beatNumber = 0;

            for (double time = Offset; time < Duration; time += beatDuration)
            {
                bool isMeasure = beatNumber % BeatsPerMeasure == 0;
                float position = (float)(time / Duration);

                gridContainer.Add(new Box
                {
                    RelativePositionAxes = Axes.X,
                    X = position,
                    Width = isMeasure ? 2 : 1,
                    RelativeSizeAxes = Axes.Y,
                    Colour = isMeasure ? MeasureColour : BeatColour,
                    Alpha = isMeasure ? 0.8f : 0.5f,
                });

                beatNumber++;

                // Limit to prevent too many lines
                if (beatNumber > 1000) break;
            }
        }
    }
}
