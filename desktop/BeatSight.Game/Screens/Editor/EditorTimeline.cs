using System;
using System.Collections.Generic;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Input.Events;
using osu.Framework.Utils;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorTimeline : CompositeDrawable
    {
        public const double MinZoom = 0.2;
        public const double MaxZoom = 5;
        public const double MinWaveformScale = 0.5;
        public const double MaxWaveformScale = 2.5;

        private readonly TimelineContent content;

        public event Action<double>? SeekRequested;
        public event Action<HitObject>? NoteSelected;
        public event Action<HitObject>? NoteAdded;
        public event Action<HitObject>? NoteChanged;
        public event Action<HitObject>? NoteDeleted;
        public event Action? EditBegan;
        public event Action<double>? ZoomChanged;
        public event Action<int>? SnapDivisorChanged;

        public EditorTimeline()
        {
            RelativeSizeAxes = Axes.Both;
            Masking = true;
            CornerRadius = 12;

            InternalChild = content = new TimelineContent();
            content.SeekRequested += t => SeekRequested?.Invoke(t);
            content.NoteSelected += h => NoteSelected?.Invoke(h);
            content.NoteAdded += h => NoteAdded?.Invoke(h);
            content.NoteChanged += h => NoteChanged?.Invoke(h);
            content.NoteDeleted += h => NoteDeleted?.Invoke(h);
            content.EditBegan += () => EditBegan?.Invoke();
            content.ZoomChanged += z => ZoomChanged?.Invoke(z);
            content.SnapDivisorChanged += d => SnapDivisorChanged?.Invoke(d);
        }

        public void LoadBeatmap(Beatmap beatmap, double durationMs, WaveformData? waveform)
            => content.LoadBeatmap(beatmap, durationMs, waveform);

        public void UpdateWaveform(WaveformData? waveform)
            => content.UpdateWaveform(waveform);

        public void SetCurrentTime(double timeMs)
            => content.SetCurrentTime(timeMs);

        public void SetZoom(double zoom)
            => content.SetZoom(zoom);

        public void SetSnap(int divisor, double bpm)
            => content.SetSnap(divisor, bpm);

        public void ScrollToCurrentTime()
            => content.ScrollToPlayhead();

        public double CurrentZoom => content.CurrentZoom;
        public int CurrentSnapDivisor => content.CurrentSnapDivisor;
        public bool BeatGridVisible => content.BeatGridVisible;
        public double CurrentWaveformScale => content.CurrentWaveformScale;

        public void SetBeatGridVisible(bool visible)
            => content.SetBeatGridVisible(visible);

        public void SetWaveformScale(double scale)
            => content.SetWaveformScale(scale);

        public bool TrySelectHitObject(HitObject hit)
            => content.TrySelectHitObject(hit);

        public bool TryDeleteHitObject(HitObject hit)
            => content.TryDeleteHitObject(hit);

        public void RefreshHitObject(HitObject hit)
            => content.RefreshHitObject(hit);

        private partial class TimelineContent : CompositeDrawable
        {
            private int laneCount = 7;
            private List<string> laneMapping = new List<string>
            {
                "kick", "hihat_pedal", "snare", "hihat_closed", "tom_high", "tom_mid", "crash"
            };
            private const double basePixelsPerSecond = 220;
            private static readonly int[] allowedSnapDivisors = { 1, 2, 3, 4, 6, 8, 12, 16, 24, 32 };
            private static readonly double[] rulerStepCandidatesSeconds = { 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 180, 240, 300, 600 };
            private const double minimumMajorTickSpacing = 80;
            private const double minimumMinorTickSpacing = 40;

            public event Action<double>? SeekRequested;
            public event Action<HitObject>? NoteSelected;
            public event Action<HitObject>? NoteAdded;
            public event Action<HitObject>? NoteChanged;
            public event Action<HitObject>? NoteDeleted;
            public event Action? EditBegan;
            public event Action<double>? ZoomChanged;
            public event Action<int>? SnapDivisorChanged;

            private const float rulerHeight = 32f;

            private readonly BasicScrollContainer scroll;
            private readonly Container timelineSurface;
            private readonly Container contentArea;
            private readonly Container laneBackgrounds;
            private readonly Container beatGridLayer;
            private readonly WaveformDrawable waveformDrawable;
            private readonly Container noteLayer;
            private readonly Box playhead;
            private readonly Container rulerLayer;
            private readonly Container rulerTickLayer;

            private Beatmap? beatmap;
            private WaveformData? waveform;
            private double durationMs;
            private double zoom = 1.0;
            private double? snapIntervalMs;
            private int snapDivisor = 4;
            private double bpm = 120.0;
            private bool beatGridVisible = true;
            private double waveformScale = 1.0;

            private readonly List<TimelineNoteDrawable> notes = new();
            private TimelineNoteDrawable? selectedNote;

            private double PixelsPerSecond => basePixelsPerSecond * zoom;
            public double CurrentZoom => zoom;
            public int CurrentSnapDivisor => snapDivisor;
            public bool BeatGridVisible => beatGridVisible;
            public double CurrentWaveformScale => waveformScale;

            public TimelineContent()
            {
                RelativeSizeAxes = Axes.Both;

                InternalChild = scroll = new TimelineScrollContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    ScrollbarOverlapsContent = false,
                    Child = timelineSurface = new Container
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 2000,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(26, 28, 38, 255)
                            },
                            contentArea = new Container
                            {
                                RelativeSizeAxes = Axes.Both,
                                Padding = new MarginPadding { Top = rulerHeight, Bottom = 16 },
                                Children = new Drawable[]
                                {
                                    laneBackgrounds = new Container
                                    {
                                        RelativeSizeAxes = Axes.Both
                                    },
                                    beatGridLayer = new Container
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Alpha = 0.9f
                                    },
                                    waveformDrawable = new WaveformDrawable
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Alpha = 0.45f
                                    },
                                    noteLayer = new Container
                                    {
                                        RelativeSizeAxes = Axes.Both
                                    },
                                    playhead = new Box
                                    {
                                        RelativeSizeAxes = Axes.Y,
                                        Width = 3,
                                        Colour = new Color4(255, 172, 120, 255),
                                        Anchor = Anchor.TopLeft,
                                        Origin = Anchor.TopCentre
                                    }
                                }
                            },
                            rulerLayer = new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = rulerHeight,
                                Anchor = Anchor.TopLeft,
                                Origin = Anchor.TopLeft,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = new Color4(38, 42, 58, 230)
                                    },
                                    rulerTickLayer = new Container
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Padding = new MarginPadding { Left = 12, Right = 12 }
                                    }
                                }
                            }
                        }
                    }
                };

                rebuildLaneBackgrounds();
            }

            public void LoadBeatmap(Beatmap beatmap, double durationMs, WaveformData? waveform)
            {
                this.beatmap = beatmap;
                this.durationMs = Math.Max(durationMs, Math.Max(beatmap.Audio.Duration, 60000));
                this.waveform = waveform;

                if (beatmap.DrumKit != null && beatmap.DrumKit.Components.Count > 0)
                {
                    laneMapping = new List<string>(beatmap.DrumKit.Components);
                    laneCount = laneMapping.Count;
                }
                else
                {
                    // Fallback to default 7-lane layout
                    laneMapping = new List<string> { "kick", "hihat_pedal", "snare", "hihat_closed", "tom_high", "tom_mid", "crash" };
                    laneCount = 7;
                }

                rebuildLaneBackgrounds();
                rebuildWaveform();
                rebuildNotes();
                updateSurfaceWidth();
                SetCurrentTime(0);
            }

            public void UpdateWaveform(WaveformData? waveform)
            {
                this.waveform = waveform;
                rebuildWaveform();
                rebuildBeatGrid();
            }

            public void SetZoom(double zoom) => setZoomInternal(zoom, false);

            public void SetSnap(int divisor, double bpm) => setSnapInternal(divisor, bpm, false);

            public void SetBeatGridVisible(bool visible) => setBeatGridVisibleInternal(visible);

            public void SetWaveformScale(double scale) => setWaveformScaleInternal(scale);

            public bool TrySelectHitObject(HitObject hit)
            {
                var note = findNoteDrawable(hit);
                if (note == null)
                    return false;

                onNoteSelected(note);
                SetCurrentTime(hit.Time);
                return true;
            }

            public bool TryDeleteHitObject(HitObject hit)
            {
                var note = findNoteDrawable(hit);
                if (note == null)
                    return false;

                onNoteDeleted(note);
                return true;
            }

            public void RefreshHitObject(HitObject hit)
            {
                var note = findNoteDrawable(hit);
                if (note == null)
                    return;

                note.UpdateLayout(PixelsPerSecond, laneHeightForNotes());
                updateNoteDepth(note);
            }

            public void SetCurrentTime(double timeMs)
            {
                float x = (float)(timeMs / 1000.0 * PixelsPerSecond);
                playhead.X = x;
                ScrollToPlayhead();
            }

            public void ScrollToPlayhead()
            {
                double playheadX = playhead.X;
                double viewStart = scroll.Current;
                double viewEnd = viewStart + scroll.DrawWidth;

                if (playheadX < viewStart)
                {
                    scroll.ScrollTo((float)Math.Max(0, playheadX - 20));
                }
                else if (playheadX > viewEnd)
                {
                    scroll.ScrollTo((float)Math.Max(0, playheadX - scroll.DrawWidth / 2));
                }
            }

            protected override bool OnClick(ClickEvent e)
            {
                if (!IsLoaded)
                    return base.OnClick(e);

                var local = timelineSurface.ToLocalSpace(e.ScreenSpaceMousePosition);
                double timeMs = Math.Max(0, local.X / PixelsPerSecond * 1000);
                SeekRequested?.Invoke(timeMs);
                return true;
            }

            protected override bool OnDoubleClick(DoubleClickEvent e)
            {
                var local = timelineSurface.ToLocalSpace(e.ScreenSpaceMousePosition);
                double timeMs = Math.Max(0, local.X / PixelsPerSecond * 1000);
                var laneLocal = laneBackgrounds.ToLocalSpace(e.ScreenSpaceMousePosition);
                EditBegan?.Invoke();
                addNoteAt(timeMs, laneLocal.Y);
                return true;
            }

            protected override bool OnScroll(ScrollEvent e)
            {
                if (e.ControlPressed)
                {
                    double delta = e.ScrollDelta.Y != 0 ? e.ScrollDelta.Y : -e.ScrollDelta.X;
                    if (Math.Abs(delta) > Precision.FLOAT_EPSILON)
                    {
                        double factor = delta > 0 ? 1.1 : 1 / 1.1;
                        setZoomInternal(zoom * factor, true);
                        return true;
                    }
                }

                if (e.AltPressed)
                {
                    double delta = e.ScrollDelta.Y != 0 ? e.ScrollDelta.Y : -e.ScrollDelta.X;
                    if (Math.Abs(delta) > Precision.FLOAT_EPSILON)
                    {
                        adjustSnapFromScroll(delta > 0);
                        return true;
                    }
                }

                return base.OnScroll(e);
            }

            private void rebuildLaneBackgrounds()
            {
                laneBackgrounds.Clear();
                for (int lane = 0; lane < laneCount; lane++)
                {
                    float fraction = (float)lane / laneCount;
                    laneBackgrounds.Add(new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Width = 1f / laneCount,
                        RelativePositionAxes = Axes.X,
                        X = fraction,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = lane % 2 == 0
                                    ? new Color4(34, 36, 50, 255)
                                    : new Color4(30, 32, 45, 255)
                            },
                            new Box
                            {
                                RelativeSizeAxes = Axes.Y,
                                Width = 1,
                                Anchor = Anchor.CentreRight,
                                Origin = Anchor.CentreRight,
                                Colour = new Color4(48, 52, 70, 180)
                            }
                        }
                    });
                }
            }

            private void rebuildWaveform()
            {
                waveformDrawable.SetData(waveform, PixelsPerSecond, waveformScale);
            }

            private void rebuildBeatGrid()
            {
                if (!beatGridVisible)
                {
                    beatGridLayer.Clear();
                    beatGridLayer.FadeOut(120, Easing.OutQuint);
                    return;
                }

                beatGridLayer.Clear();

                if (durationMs <= 0 || PixelsPerSecond <= 0)
                    return;

                const int beatsPerMeasure = 4;
                double effectiveBpm = bpm > 0 && double.IsFinite(bpm) ? bpm : 120.0;
                double beatMs = 60000.0 / effectiveBpm;
                if (!double.IsFinite(beatMs) || beatMs <= 0)
                    return;

                double measureMs = beatMs * beatsPerMeasure;
                double beatPixels = beatMs / 1000.0 * PixelsPerSecond;
                double measurePixels = measureMs / 1000.0 * PixelsPerSecond;
                double subdivisionPixels = snapIntervalMs.HasValue ? snapIntervalMs.Value / 1000.0 * PixelsPerSecond : 0;

                bool drawMeasures = measurePixels >= 12;
                bool drawBeats = beatPixels >= 8;
                bool drawSubdivisions = snapIntervalMs.HasValue && subdivisionPixels >= 10 && subdivisionPixels < measurePixels;

                if (!drawMeasures && !drawBeats && !drawSubdivisions)
                    return;

                var measureColour = new Color4(245, 205, 140, 200);
                var beatColour = new Color4(150, 190, 235, 160);
                var subdivisionColour = new Color4(125, 150, 190, 120);

                float surfaceWidth = timelineSurface.Width;
                double duration = durationMs;

                void addLine(double timeMs, Color4 colour, float alpha, float width)
                {
                    float x = (float)(timeMs / 1000.0 * PixelsPerSecond);
                    if (x > surfaceWidth + 2)
                        return;

                    beatGridLayer.Add(new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = width,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.TopCentre,
                        X = x,
                        Colour = colour,
                        Alpha = alpha
                    });
                }

                if (drawMeasures)
                {
                    int measureCount = (int)Math.Ceiling(duration / measureMs);
                    for (int i = 0; i <= measureCount; i++)
                    {
                        double time = i * measureMs;
                        addLine(time, measureColour, 0.95f, 2.2f);
                    }
                }

                if (drawBeats)
                {
                    int beatCount = (int)Math.Ceiling(duration / beatMs);
                    for (int i = 0; i <= beatCount; i++)
                    {
                        if (drawMeasures && beatsPerMeasure > 0 && i % beatsPerMeasure == 0)
                            continue;

                        double time = i * beatMs;
                        addLine(time, beatColour, 0.7f, 1.2f);
                    }
                }

                if (drawSubdivisions && snapIntervalMs.HasValue)
                {
                    double interval = snapIntervalMs.Value;
                    double beatLengthTolerance = Math.Max(beatMs * 0.01, 0.5);
                    double measureLengthTolerance = Math.Max(measureMs * 0.01, 1);
                    int subdivisionCount = (int)Math.Ceiling(duration / interval);

                    for (int i = 0; i <= subdivisionCount; i++)
                    {
                        double time = i * interval;

                        if (drawMeasures && isMultiple(time, measureMs, measureLengthTolerance))
                            continue;

                        if (drawBeats && isMultiple(time, beatMs, beatLengthTolerance))
                            continue;

                        addLine(time, subdivisionColour, 0.5f, 1f);
                    }
                }

                static bool isMultiple(double value, double modulus, double tolerance)
                {
                    if (modulus <= 0)
                        return false;

                    double remainder = value % modulus;
                    return remainder <= tolerance || modulus - remainder <= tolerance;
                }
            }

            private void rebuildRuler()
            {
                if (rulerTickLayer == null)
                    return;

                rulerTickLayer.Clear();

                rulerTickLayer.Add(new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 1,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Colour = new Color4(70, 82, 110, 255)
                });

                double duration = durationMs;
                double pixelsPerSecond = PixelsPerSecond;

                if (duration <= 0 || pixelsPerSecond <= 0)
                    return;

                double majorStepSeconds = rulerStepCandidatesSeconds[^1];

                foreach (double candidate in rulerStepCandidatesSeconds)
                {
                    majorStepSeconds = candidate;
                    if (candidate * pixelsPerSecond >= minimumMajorTickSpacing)
                        break;
                }

                if (majorStepSeconds <= 0)
                    majorStepSeconds = 1;

                int subdivisions = majorStepSeconds switch
                {
                    >= 120 => 4,
                    >= 30 => 6,
                    _ => 4
                };

                double minorStepSeconds = majorStepSeconds / subdivisions;
                bool drawMinor = minorStepSeconds * pixelsPerSecond >= minimumMinorTickSpacing;

                double majorStepMs = majorStepSeconds * 1000;
                double minorStepMs = minorStepSeconds * 1000;

                int majorTickCount = (int)Math.Ceiling(duration / majorStepMs);

                void addTick(double timeMs, bool major)
                {
                    float x = (float)(timeMs / 1000.0 * pixelsPerSecond);
                    if (x < -2 || x > timelineSurface.Width + 4)
                        return;

                    rulerTickLayer.Add(new Box
                    {
                        Width = major ? 2f : 1f,
                        Height = major ? 14f : 8f,
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomCentre,
                        X = x,
                        Colour = major
                            ? new Color4(220, 232, 255, 255)
                            : new Color4(140, 160, 200, 200)
                    });

                    if (!major)
                        return;

                    var label = new SpriteText
                    {
                        Text = formatRulerLabel(timeMs),
                        Font = BeatSightFont.Title(12f),
                        Colour = EditorColours.TextSecondary,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.BottomCentre,
                        X = x,
                        Y = -18,
                        Alpha = 0.95f
                    };

                    rulerTickLayer.Add(label);
                }

                for (int i = 0; i <= majorTickCount; i++)
                {
                    double majorTime = i * majorStepMs;
                    addTick(majorTime, true);

                    if (!drawMinor)
                        continue;

                    for (int s = 1; s < subdivisions; s++)
                    {
                        double minorTime = majorTime + s * minorStepMs;
                        if (minorTime >= (i + 1) * majorStepMs || minorTime > duration)
                            break;

                        addTick(minorTime, false);
                    }
                }
            }

            private static string formatRulerLabel(double timeMs)
            {
                var span = TimeSpan.FromMilliseconds(Math.Max(0, timeMs));

                if (span.TotalHours >= 1)
                    return $"{(int)span.TotalHours}:{span.Minutes:00}:{span.Seconds:00}.{span.Milliseconds:000}";

                return $"{(int)span.TotalMinutes:00}:{span.Seconds:00}.{span.Milliseconds:000}";
            }

            private partial class TimelineScrollContainer : BasicScrollContainer
            {
                protected override bool OnDragStart(DragStartEvent e) => false;

                protected override void OnDrag(DragEvent e)
                {
                }
            }

            private void rebuildNotes()
            {
                noteLayer.Clear();
                notes.Clear();
                selectedNote = null;

                if (beatmap == null)
                    return;

                foreach (var hit in beatmap.HitObjects)
                {
                    var note = createNoteDrawable(hit);
                    notes.Add(note);
                    noteLayer.Add(note);
                }

                refreshNotes();
            }

            private void refreshNotes()
            {
                if (notes.Count == 0)
                    return;

                float laneHeight = laneHeightForNotes();

                foreach (var note in notes)
                {
                    note.UpdateLayout(PixelsPerSecond, laneHeight);
                    updateNoteDepth(note);
                }
            }

            private TimelineNoteDrawable? findNoteDrawable(HitObject hit)
            {
                for (int i = 0; i < notes.Count; i++)
                {
                    if (ReferenceEquals(notes[i].HitObject, hit))
                        return notes[i];
                }

                return null;
            }

            private float laneHeightForNotes()
            {
                float laneAreaHeight = laneBackgrounds.DrawHeight;
                if (laneAreaHeight <= 0)
                    laneAreaHeight = contentArea.DrawSize.Y;

                if (laneAreaHeight <= 0)
                    laneAreaHeight = 1;

                return laneAreaHeight / Math.Max(1, laneCount);
            }

            private TimelineNoteDrawable createNoteDrawable(HitObject hit)
            {
                var note = new TimelineNoteDrawable(hit, laneCount, time => (float)(time / 1000.0 * PixelsPerSecond), x => Math.Max(0, x / PixelsPerSecond * 1000))
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.CentreLeft
                };

                note.Selected += onNoteSelected;
                note.DeleteRequested += onNoteDeleted;
                note.Dragged += onNoteDragged;
                note.LaneChanged += onNoteLaneChanged;
                note.DragStarted += () => EditBegan?.Invoke();

                return note;
            }

            private void onNoteSelected(TimelineNoteDrawable note)
            {
                if (selectedNote != null && selectedNote != note)
                    selectedNote.SetSelected(false);

                selectedNote = note;
                note.SetSelected(true);
                NoteSelected?.Invoke(note.HitObject);
            }

            private void onNoteDeleted(TimelineNoteDrawable note)
            {
                if (beatmap == null)
                    return;

                beatmap.HitObjects.Remove(note.HitObject);
                noteLayer.Remove(note, true);
                notes.Remove(note);

                if (selectedNote == note)
                    selectedNote = null;

                NoteDeleted?.Invoke(note.HitObject);
            }

            private void onNoteDragged(TimelineNoteDrawable note, double timeMs)
            {
                if (beatmap == null)
                    return;

                double snapped = snapIntervalMs.HasValue
                    ? snapToInterval(timeMs, snapIntervalMs.Value)
                    : timeMs;

                note.HitObject.Time = (int)Math.Round(snapped);
                note.UpdateLayout(PixelsPerSecond, laneHeightForNotes());
                updateNoteDepth(note);
                NoteChanged?.Invoke(note.HitObject);
            }

            private void onNoteLaneChanged(TimelineNoteDrawable note, int lane)
            {
                note.HitObject.Lane = lane;
                note.UpdateLayout(PixelsPerSecond, laneHeightForNotes());
                NoteChanged?.Invoke(note.HitObject);
            }

            private void updateNoteDepth(TimelineNoteDrawable note)
            {
                noteLayer.ChangeChildDepth(note, -note.HitObject.Time);
            }

            private void addNoteAt(double timeMs, float yPosition)
            {
                if (beatmap == null)
                    return;

                double snapped = snapIntervalMs.HasValue
                    ? snapToInterval(timeMs, snapIntervalMs.Value)
                    : timeMs;

                float laneAreaHeight = laneHeightForNotes() * laneCount;
                if (laneAreaHeight <= 0)
                    laneAreaHeight = laneCount;

                float clampedY = Math.Clamp(yPosition, 0, laneAreaHeight);
                int lane = Math.Clamp((int)(clampedY / Math.Max(1, laneAreaHeight) * laneCount), 0, laneCount - 1);
                string component = laneMapping[lane];

                var hit = new HitObject
                {
                    Time = (int)Math.Round(snapped),
                    Lane = lane,
                    Component = component,
                    Velocity = 0.8
                };

                EditBegan?.Invoke();
                beatmap.HitObjects.Add(hit);
                beatmap.HitObjects.Sort((a, b) => a.Time.CompareTo(b.Time));

                var note = createNoteDrawable(hit);
                notes.Add(note);
                noteLayer.Add(note);
                note.UpdateLayout(PixelsPerSecond, laneHeightForNotes());
                updateNoteDepth(note);
                NoteAdded?.Invoke(hit);
                onNoteSelected(note);
            }

            private void updateSurfaceWidth()
            {
                double pixelWidth = Math.Max(1000, durationMs / 1000.0 * PixelsPerSecond);
                timelineSurface.Width = (float)pixelWidth;
                rebuildBeatGrid();
                rebuildRuler();
            }

            private static double snapToInterval(double value, double interval)
            {
                if (interval <= 0)
                    return value;

                double snapped = Math.Round(value / interval) * interval;
                return snapped < 0 ? 0 : snapped;
            }

            private void setZoomInternal(double targetZoom, bool notify)
            {
                double clamped = Math.Clamp(targetZoom, MinZoom, MaxZoom);
                if (Precision.AlmostEquals(clamped, zoom))
                    return;

                zoom = clamped;
                updateSurfaceWidth();
                refreshNotes();
                rebuildWaveform();
                ScrollToPlayhead();

                if (notify)
                    ZoomChanged?.Invoke(zoom);
            }

            private void setSnapInternal(int divisor, double bpm, bool notify)
            {
                this.bpm = bpm;
                snapDivisor = divisor <= 0 ? 1 : divisor;

                if (divisor <= 0 || bpm <= 0)
                {
                    snapIntervalMs = null;
                }
                else
                {
                    snapIntervalMs = 60000.0 / bpm / divisor;
                }

                rebuildBeatGrid();

                if (notify)
                    SnapDivisorChanged?.Invoke(snapDivisor);
            }

            private void adjustSnapFromScroll(bool increase)
            {
                if (allowedSnapDivisors.Length == 0)
                    return;

                int index = Array.IndexOf(allowedSnapDivisors, snapDivisor);
                if (index < 0)
                {
                    index = Array.BinarySearch(allowedSnapDivisors, snapDivisor);
                    if (index < 0)
                        index = Math.Clamp(~index, 0, allowedSnapDivisors.Length - 1);
                }

                int newIndex = Math.Clamp(index + (increase ? 1 : -1), 0, allowedSnapDivisors.Length - 1);
                int newDivisor = allowedSnapDivisors[newIndex];
                if (newDivisor == snapDivisor)
                    return;

                setSnapInternal(newDivisor, bpm, true);
            }

            private void setBeatGridVisibleInternal(bool visible)
            {
                if (beatGridVisible == visible)
                    return;

                beatGridVisible = visible;

                if (beatGridVisible)
                {
                    rebuildBeatGrid();
                    beatGridLayer.FadeTo(0.9f, 120, Easing.OutQuint);
                }
                else
                {
                    beatGridLayer.Clear();
                    beatGridLayer.FadeOut(120, Easing.OutQuint);
                }
            }

            private void setWaveformScaleInternal(double scale)
            {
                double clamped = Math.Clamp(scale, MinWaveformScale, MaxWaveformScale);
                if (Precision.AlmostEquals(clamped, waveformScale))
                    return;

                waveformScale = clamped;
                waveformDrawable.SetAmplitudeScale(waveformScale);
            }

        }

        private partial class WaveformDrawable : CompositeDrawable
        {
            private WaveformData? waveform;
            private double pixelsPerSecond = 1;
            private double amplitudeScale = 1.0;
            private readonly FillFlowContainer barFlow;

            public WaveformDrawable()
            {
                RelativeSizeAxes = Axes.Both;

                InternalChild = barFlow = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.Y,
                    AutoSizeAxes = Axes.X,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(0.5f, 0)
                };
            }

            public void SetData(WaveformData? waveform, double pixelsPerSecond, double amplitudeScale = 1.0)
            {
                this.waveform = waveform;
                this.pixelsPerSecond = Math.Max(1, pixelsPerSecond);
                this.amplitudeScale = Math.Clamp(amplitudeScale, MinWaveformScale, MaxWaveformScale);
                rebuild();
            }

            public void SetAmplitudeScale(double scale)
            {
                amplitudeScale = Math.Clamp(scale, MinWaveformScale, MaxWaveformScale);
                rebuild();
            }

            private void rebuild()
            {
                barFlow.Clear();

                if (waveform == null || waveform.BucketCount == 0)
                    return;

                double bucketSeconds = waveform.BucketDurationSeconds;
                double bucketWidth = Math.Max(1, pixelsPerSecond * bucketSeconds);

                for (int i = 0; i < waveform.BucketCount; i++)
                {
                    float amplitude = Math.Max(Math.Abs(waveform.Minima[i]), Math.Abs(waveform.Maxima[i]));
                    float height = Math.Clamp(amplitude * (float)(1.2f * amplitudeScale), 0.08f, 1f);

                    var container = new Container
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = (float)bucketWidth,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    };

                    var bar = new Box
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Width = (float)Math.Max(1, bucketWidth),
                        RelativeSizeAxes = Axes.Y,
                        Height = height,
                        Colour = new Color4(110, 180, 255, 150)
                    };

                    container.Add(bar);
                    barFlow.Add(container);
                }
            }
        }

        private partial class TimelineNoteDrawable : CompositeDrawable
        {
            private const float baseWidth = 18;
            private readonly Func<double, float> timeToX;
            private readonly Func<float, double> xToTime;
            private readonly int laneCount;
            private readonly Box background;
            private readonly Box selectionOverlay;

            public HitObject HitObject { get; }

            public event Action<TimelineNoteDrawable>? Selected;
            public event Action<TimelineNoteDrawable>? DeleteRequested;
            public event Action<TimelineNoteDrawable, double>? Dragged;
            public event Action<TimelineNoteDrawable, int>? LaneChanged;
            public event Action? DragStarted;

            public TimelineNoteDrawable(HitObject hitObject, int laneCount, Func<double, float> timeToX, Func<float, double> xToTime)
            {
                HitObject = hitObject;
                this.laneCount = laneCount;
                this.timeToX = timeToX;
                this.xToTime = xToTime;

                Size = new Vector2(baseWidth, 30);
                CornerRadius = 5;
                Masking = true;
                Colour = ResolveColour(hitObject.Component);

                InternalChildren = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Colour
                    },
                    selectionOverlay = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(255, 255, 255, 80),
                        Alpha = 0
                    }
                };
            }

            public void UpdateLayout(double pixelsPerSecond, float laneHeight)
            {
                float x = timeToX(HitObject.Time);
                int lane = Math.Clamp(HitObject.Lane ?? resolveLaneFromComponent(HitObject.Component), 0, laneCount - 1);
                float y = laneHeight * lane + laneHeight / 2;

                Position = new Vector2(x, y);
                Size = new Vector2(baseWidth, Math.Max(16, laneHeight * 0.7f));
            }

            public void SetSelected(bool selected)
            {
                selectionOverlay.Alpha = selected ? 0.4f : 0f;
            }

            protected override bool OnClick(ClickEvent e)
            {
                Selected?.Invoke(this);
                return true;
            }

            protected override bool OnMouseDown(MouseDownEvent e)
            {
                if (e.Button == MouseButton.Right)
                {
                    DragStarted?.Invoke();
                    DeleteRequested?.Invoke(this);
                    return true;
                }

                return base.OnMouseDown(e);
            }

            protected override bool OnDragStart(DragStartEvent e)
            {
                DragStarted?.Invoke();
                return true;
            }

            protected override void OnDrag(DragEvent e)
            {
                float localX = ToLocalSpace(e.ScreenSpaceMousePosition).X;
                Dragged?.Invoke(this, xToTime(localX));
            }

            protected override bool OnScroll(ScrollEvent e)
            {
                if (e.ControlPressed || e.AltPressed)
                    return false;

                int laneDelta = e.ScrollDelta.Y > 0 ? -1 : 1;
                int lane = Math.Clamp((HitObject.Lane ?? resolveLaneFromComponent(HitObject.Component)) + laneDelta, 0, laneCount - 1);
                DragStarted?.Invoke();
                LaneChanged?.Invoke(this, lane);
                return true;
            }

            private static Color4 ResolveColour(string component)
            {
                string key = component?.ToLowerInvariant() ?? string.Empty;
                return key switch
                {
                    "kick" => new Color4(255, 120, 120, 255),
                    "snare" => new Color4(120, 180, 255, 255),
                    "hihat_closed" => new Color4(255, 220, 120, 255),
                    "hihat_open" => new Color4(255, 200, 120, 255),
                    "tom_high" => new Color4(150, 210, 160, 255),
                    "tom_mid" => new Color4(120, 210, 210, 255),
                    "tom_low" => new Color4(140, 160, 230, 255),
                    "crash" => new Color4(255, 160, 220, 255),
                    _ => new Color4(200, 200, 220, 255)
                };
            }

            private static int resolveLaneFromComponent(string component) => DrumLaneHeuristics.ResolveLane(component);
        }
    }
}
