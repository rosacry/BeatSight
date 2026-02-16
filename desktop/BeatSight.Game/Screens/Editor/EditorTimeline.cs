using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Logging;
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
        public event Action<double?, double?>? SelectionChanged;

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
            content.SelectionChanged += (start, end) => SelectionChanged?.Invoke(start, end);
        }

        public void LoadBeatmap(Beatmap beatmap, double durationMs, WaveformData? waveform)
            => content.LoadBeatmap(beatmap, durationMs, waveform);

        public void LoadDebugData(string jsonContent)
            => content.LoadDebugData(jsonContent);

        public void UpdateWaveform(WaveformData? waveform)
            => content.UpdateWaveform(waveform);

        public void SetCurrentTime(double timeMs, bool ensureVisible = true)
            => content.SetCurrentTime(timeMs, ensureVisible);

        public void SetZoom(double zoom)
            => content.SetZoom(zoom);

        public void BeginZoomInteraction(float? viewportAnchorX = null)
            => content.BeginZoomInteraction(viewportAnchorX);

        public void EndZoomInteraction()
            => content.EndZoomInteraction();

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

        public void SetWaveformScale(double scale, bool forceApply = false)
            => content.SetWaveformScale(scale, forceApply);

        public void PreviewWaveformScale(double scale)
            => content.PreviewWaveformScale(scale);

        public int SnapSelectedNoteToTransient(double maxDistanceMs = 50)
            => content.SnapSelectedNotesToTransients(maxDistanceMs);

        public bool TrySelectHitObject(HitObject hit)
            => content.TrySelectHitObject(hit);

        public bool TryDeleteHitObject(HitObject hit)
            => content.TryDeleteHitObject(hit);

        public bool TryAddHitObjectAtTimeAndLane(double timeMs, int lane)
            => content.TryAddHitObjectAtTimeAndLane(timeMs, lane);

        public bool TryDeleteNearestHitObject(double timeMs, int lane, double maxDistanceMs = 90)
            => content.TryDeleteNearestHitObject(timeMs, lane, maxDistanceMs);

        public void RefreshHitObject(HitObject hit)
            => content.RefreshHitObject(hit);

        public void ClearSelection()
            => content.ClearSelection();

        public void SetSelectionRange(double startMs, double endMs)
            => content.SetSelectionRange(startMs, endMs);

        public double? SelectionStart => content.SelectionStart;
        public double? SelectionEnd => content.SelectionEnd;
        public bool HasDetectedOnsets => content.HasDetectedOnsets;

        public string? GetLaneComponentForVisibleLane(int visibleLaneIndex)
            => content.GetLaneComponentForVisibleLane(visibleLaneIndex);

        private partial class TimelineContent : CompositeDrawable
        {
            private int laneCount = 7;
            private List<string> laneMapping = new List<string>
            {
                "kick", "hihat_pedal", "snare", "hihat_closed", "tom_high", "tom_mid", "crash"
            };
            private const double basePixelsPerSecond = 260;
            private static readonly int[] allowedSnapDivisors = { 1, 2, 3, 4, 6, 8, 12, 16, 24, 32 };
            private static readonly double[] rulerStepCandidatesSeconds = { 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 180, 240, 300, 600 };
            private const double minimumMajorTickSpacing = 80;
            private const double minimumMinorTickSpacing = 40;
            private const int defaultLaneCount = 7;
            private const int maxEditorLaneCount = 9;
            private const double viewportHintRefreshDeltaMs = 35;

            public event Action<double>? SeekRequested;
            public event Action<HitObject>? NoteSelected;
            public event Action<HitObject>? NoteAdded;
            public event Action<HitObject>? NoteChanged;
            public event Action<HitObject>? NoteDeleted;
            public event Action? EditBegan;
            public event Action<double>? ZoomChanged;
            public event Action<int>? SnapDivisorChanged;
            public event Action<double?, double?>? SelectionChanged;

            private const float rulerHeight = 38f;

            private readonly BeatSightScrollContainer scroll;
            private readonly Container timelineSurface;
            private readonly Container contentArea;
            private readonly Container laneBackgrounds;
            private readonly Container laneLabelLayer;
            private readonly Container beatGridLayer;
            private readonly Container debugLayer; // New
            private readonly Container onsetLayer; // New
            private readonly Container viewportHintContainer;
            private readonly SpriteText viewportHintText;
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
            private LaneLayout laneResolutionLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);

            private readonly List<TimelineNoteDrawable> notes = new();
            private TimelineNoteDrawable? selectedNote;
            private float lastLaneHeight = -1;
            private bool laneLayoutDirty = true;
            private bool zoomInteractionActive;
            private double zoomInteractionAnchorTimeMs;
            private double zoomInteractionViewportAnchorX;
            private bool zoomInteractionDeferredLayerRebuild;

            private double PixelsPerSecond => basePixelsPerSecond * zoom;
            public double CurrentZoom => zoom;
            public int CurrentSnapDivisor => snapDivisor;
            public bool BeatGridVisible => beatGridVisible;
            public double CurrentWaveformScale => waveformScale;

            private readonly List<double> detectedOnsets = new();

            private Box selectionBox;
            private double? selectionStart;
            private double? selectionEnd;
            private double lastViewportHintStartMs = double.NaN;
            private double lastViewportHintEndMs = double.NaN;
            private string? lastViewportHintMessage;

            public double? SelectionStart => selectionStart;
            public double? SelectionEnd => selectionEnd;
            public bool HasDetectedOnsets => detectedOnsets.Count > 0;

            public TimelineContent()
            {
                RelativeSizeAxes = Axes.Both;

                InternalChild = scroll = new BeatSightScrollContainer(Direction.Horizontal)
                {
                    RelativeSizeAxes = Axes.Both,
                    ScrollbarVisible = true,
                    Child = contentArea = new Container
                    {
                        RelativeSizeAxes = Axes.Y,
                        AutoSizeAxes = Axes.X,
                        Children = new Drawable[]
                        {
                            timelineSurface = new Container
                            {
                                RelativeSizeAxes = Axes.Y,
                                Height = 1,
                                Padding = new MarginPadding { Bottom = rulerHeight + 2f },
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = EditorColours.TimelineBackground
                                    },
                                    laneBackgrounds = new Container { RelativeSizeAxes = Axes.Both },
                                    beatGridLayer = new Container { RelativeSizeAxes = Axes.Both },
                                    waveformDrawable = new WaveformDrawable { RelativeSizeAxes = Axes.Both, Alpha = 0.42f },
                                    debugLayer = new Container { RelativeSizeAxes = Axes.Both, Alpha = 0.6f },
                                    onsetLayer = new Container { RelativeSizeAxes = Axes.Both, Alpha = 0.4f },
                                    laneLabelLayer = new Container { RelativeSizeAxes = Axes.Both },
                                    selectionBox = new Box { RelativeSizeAxes = Axes.Y, Colour = EditorColours.TimelineSelection, Alpha = 0 },
                                    noteLayer = new Container { RelativeSizeAxes = Axes.Both },
                                    viewportHintContainer = new Container
                                    {
                                        AutoSizeAxes = Axes.Both,
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                        Alpha = 0,
                                        Masking = true,
                                        CornerRadius = 8,
                                        Children = new Drawable[]
                                        {
                                            new Box
                                            {
                                                RelativeSizeAxes = Axes.Both,
                                                Colour = EditorColours.TimelineLabelBackground.Opacity(0.94f)
                                            },
                                            viewportHintText = new SpriteText
                                            {
                                                Font = BeatSightFont.Caption(11.6f),
                                                Colour = EditorColours.TextPrimary,
                                                Margin = new MarginPadding { Horizontal = 12, Vertical = 6 },
                                                Text = string.Empty,
                                                Anchor = Anchor.Centre,
                                                Origin = Anchor.Centre
                                            }
                                        }
                                    },
                                    playhead = new Box
                                    {
                                        Width = 2.4f,
                                        RelativeSizeAxes = Axes.Y,
                                        Colour = EditorColours.TimelinePlayhead,
                                        EdgeSmoothness = new Vector2(1, 0)
                                    },
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        Height = 1,
                                        Anchor = Anchor.BottomLeft,
                                        Origin = Anchor.BottomLeft,
                                        Colour = EditorColours.Divider.Opacity(0.35f)
                                    }
                                }
                            },
                            rulerLayer = new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = rulerHeight,
                                Anchor = Anchor.BottomLeft,
                                Origin = Anchor.BottomLeft,
                                Children = new Drawable[]
                                {
                                    new Box { RelativeSizeAxes = Axes.Both, Colour = EditorColours.TimelineToolbarBackground },
                                    rulerTickLayer = new Container { RelativeSizeAxes = Axes.Both }
                                }
                            }
                        }
                    }
                };

                rebuildLaneBackgrounds();
            }

            public void LoadDebugData(string jsonContent)
            {
                try
                {
                    var root = Newtonsoft.Json.JsonConvert.DeserializeObject<DebugRoot>(jsonContent);
                    if (root?.Detection?.Peaks == null) return;

                    debugLayer.Clear();
                    onsetLayer.Clear();
                    detectedOnsets.Clear(); // Clear previous onsets

                    foreach (var peak in root.Detection.Peaks)
                    {
                        float x = (float)(peak.Time * PixelsPerSecond);

                        // Onset Marker (Faint vertical line)
                        onsetLayer.Add(new Box
                        {
                            Width = 1,
                            RelativeSizeAxes = Axes.Y,
                            Anchor = Anchor.TopLeft,
                            Origin = Anchor.TopCentre,
                            X = x,
                            Colour = Color4.Cyan
                        });

                        // Confidence Peak (Bar at bottom)
                        float height = (float)(peak.Confidence * 100); // Scale height
                        debugLayer.Add(new Box
                        {
                            Width = 4,
                            Height = height,
                            Anchor = Anchor.BottomLeft,
                            Origin = Anchor.BottomCentre,
                            X = x,
                            Y = -20, // Above ruler
                            Colour = Color4.Yellow.Opacity((float)peak.Confidence)
                        });

                        // Add to detected onsets (convert seconds to ms)
                        detectedOnsets.Add(peak.Time * 1000.0);
                    }
                }
                catch (System.IO.IOException ex)
                {
                    Logger.Log($"Failed to load debug data file: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                }
                catch (Newtonsoft.Json.JsonException ex)
                {
                    Logger.Log($"Failed to parse debug data JSON: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                }
            }

            private class DebugRoot
            {
                public DetectionData? Detection { get; set; }
            }

            private class DetectionData
            {
                public List<PeakData>? Peaks { get; set; }
            }

            private class PeakData
            {
                public double Time { get; set; }
                public double Confidence { get; set; }
            }

            public void LoadBeatmap(Beatmap beatmap, double durationMs, WaveformData? waveform)
            {
                this.beatmap = beatmap;
                this.durationMs = Math.Max(durationMs, Math.Max(beatmap.Audio.Duration, 60000));
                this.waveform = waveform;

                resolveLaneConfiguration(beatmap);

                rebuildLaneBackgrounds();
                rebuildWaveform();
                rebuildNotes();
                updateSurfaceWidth();
                SetCurrentTime(0);
                laneLayoutDirty = true;
                updateViewportHint(force: true);
            }

            public void UpdateWaveform(WaveformData? waveform)
            {
                this.waveform = waveform;
                rebuildWaveform();
                rebuildBeatGrid();
            }

            public void SetZoom(double zoom) => setZoomInternal(zoom, false);

            public void BeginZoomInteraction(float? viewportAnchorX = null)
            {
                if (zoomInteractionActive)
                    return;

                double viewportWidth = scroll.DrawWidth;
                double resolvedAnchorX;

                if (viewportAnchorX.HasValue)
                {
                    resolvedAnchorX = viewportAnchorX.Value;
                }
                else
                {
                    // Prefer playhead-centric zoom if visible; otherwise fall back to viewport center.
                    double playheadViewportX = playhead.X - scroll.Current;
                    if (playheadViewportX >= 0 && playheadViewportX <= viewportWidth)
                        resolvedAnchorX = playheadViewportX;
                    else
                        resolvedAnchorX = viewportWidth > 0 ? viewportWidth * 0.5 : 0;
                }

                if (!double.IsFinite(resolvedAnchorX))
                    resolvedAnchorX = 0;

                if (viewportWidth > 0)
                    resolvedAnchorX = Math.Clamp(resolvedAnchorX, 0, viewportWidth);

                zoomInteractionViewportAnchorX = resolvedAnchorX;
                zoomInteractionAnchorTimeMs = PixelsPerSecond > 0
                    ? (scroll.Current + resolvedAnchorX) / PixelsPerSecond * 1000.0
                    : 0;
                zoomInteractionDeferredLayerRebuild = false;
                zoomInteractionActive = true;
            }

            public void EndZoomInteraction()
            {
                zoomInteractionActive = false;

                if (!zoomInteractionDeferredLayerRebuild)
                    return;

                zoomInteractionDeferredLayerRebuild = false;
                rebuildBeatGrid();
                rebuildRuler();
                refreshNotes(updateDepth: false);
                waveformDrawable.SetPixelsPerSecond(PixelsPerSecond);
            }

            public void SetSnap(int divisor, double bpm) => setSnapInternal(divisor, bpm, false);

            public void SetBeatGridVisible(bool visible) => setBeatGridVisibleInternal(visible);

            public void SetWaveformScale(double scale, bool forceApply = false) => setWaveformScaleInternal(scale, forceApply);

            public void PreviewWaveformScale(double scale)
            {
                double clamped = Math.Clamp(scale, MinWaveformScale, MaxWaveformScale);
                waveformDrawable.SetPreviewAmplitudeScale(clamped);
            }

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

            public bool TryAddHitObjectAtTimeAndLane(double timeMs, int lane)
            {
                if (beatmap == null || laneCount <= 0)
                    return false;

                int clampedLane = Math.Clamp(lane, 0, laneCount - 1);
                addNoteAtLane(timeMs, clampedLane);
                return true;
            }

            public bool TryDeleteNearestHitObject(double timeMs, int lane, double maxDistanceMs)
            {
                if (beatmap == null || notes.Count == 0 || laneCount <= 0)
                    return false;

                int targetLane = Math.Clamp(lane, 0, laneCount - 1);
                double threshold = Math.Max(1, maxDistanceMs);
                TimelineNoteDrawable? nearest = null;
                double nearestDistance = threshold;

                foreach (var note in notes)
                {
                    int noteLane = note.HitObject.Lane.HasValue
                        ? Math.Clamp(note.HitObject.Lane.Value, 0, laneCount - 1)
                        : resolveLaneFromComponent(note.HitObject.Component);

                    if (noteLane != targetLane)
                        continue;

                    double delta = Math.Abs(note.HitObject.Time - timeMs);
                    if (delta > nearestDistance)
                        continue;

                    nearest = note;
                    nearestDistance = delta;
                }

                if (nearest == null)
                    return false;

                EditBegan?.Invoke();
                onNoteDeleted(nearest);
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

            public void ClearSelection()
            {
                if (selectedNote != null)
                {
                    selectedNote.SetSelected(false);
                    selectedNote = null;
                }

                clearSelectionRange();
            }

            public void SetSelectionRange(double startMs, double endMs)
            {
                if (durationMs <= 0)
                    return;

                if (selectedNote != null)
                {
                    selectedNote.SetSelected(false);
                    selectedNote = null;
                }

                double lower = Math.Min(startMs, endMs);
                double upper = Math.Max(startMs, endMs);
                double clampedStart = Math.Clamp(lower, 0, durationMs);
                double clampedEnd = Math.Clamp(upper, 0, durationMs);

                selectionStart = clampedStart;
                selectionEnd = clampedEnd;
                updateSelectionVisuals();
                notifySelectionChanged();
            }

            public string? GetLaneComponentForVisibleLane(int visibleLaneIndex)
            {
                if (visibleLaneIndex < 0 || visibleLaneIndex >= laneMapping.Count)
                    return null;

                string component = laneMapping[visibleLaneIndex];
                return string.IsNullOrWhiteSpace(component) ? null : component;
            }

            protected override void Update()
            {
                base.Update();
                refreshLayoutIfNeeded();
                updateViewportHint();
            }

            private void refreshLayoutIfNeeded()
            {
                float laneHeight = laneHeightForNotes();
                if (laneHeight <= 0)
                    return;

                // Notes are initially laid out before draw sizes are fully resolved.
                // Reflow once sizes are stable so lanes/notes don't collapse at the top.
                if (!laneLayoutDirty && Precision.AlmostEquals(laneHeight, lastLaneHeight))
                    return;

                lastLaneHeight = laneHeight;
                laneLayoutDirty = false;

                refreshNotes();
                updateSelectionVisuals();
            }

            public void SetCurrentTime(double timeMs, bool ensureVisible = true)
            {
                float x = (float)(timeMs / 1000.0 * PixelsPerSecond);
                playhead.X = x;

                if (ensureVisible)
                    ScrollToPlayhead();

                updateViewportHint();
            }

            public void SetSelectedNoteTime(double timeMs)
            {
                if (selectedNote != null)
                {
                    selectedNote.HitObject.Time = (int)timeMs;
                    selectedNote.UpdateLayout(PixelsPerSecond, laneHeightForNotes());
                    updateNoteDepth(selectedNote);
                }
            }

            public int SnapSelectedNotesToTransients(double maxDistanceMs)
            {
                if (detectedOnsets.Count == 0 || notes.Count == 0)
                    return 0;

                IReadOnlyList<TimelineNoteDrawable> targets;

                if (selectionStart.HasValue && selectionEnd.HasValue && !Precision.AlmostEquals(selectionStart.Value, selectionEnd.Value))
                {
                    double start = Math.Min(selectionStart.Value, selectionEnd.Value);
                    double end = Math.Max(selectionStart.Value, selectionEnd.Value);
                    targets = notes.Where(note => note.HitObject.Time >= start && note.HitObject.Time <= end).ToList();
                }
                else if (selectedNote != null)
                {
                    targets = new[] { selectedNote };
                }
                else
                {
                    targets = Array.Empty<TimelineNoteDrawable>();
                }

                if (targets.Count == 0)
                    return 0;

                var changes = new List<(TimelineNoteDrawable note, int snappedTime)>(targets.Count);

                foreach (var note in targets)
                {
                    if (!tryGetNearestTransientTime(note.HitObject.Time, maxDistanceMs, out int snappedTime))
                        continue;

                    if (snappedTime == note.HitObject.Time)
                        continue;

                    changes.Add((note, snappedTime));
                }

                if (changes.Count == 0)
                    return 0;

                EditBegan?.Invoke();

                foreach (var (note, snappedTime) in changes)
                {
                    note.HitObject.Time = snappedTime;
                    note.UpdateLayout(PixelsPerSecond, laneHeightForNotes());
                    updateNoteDepth(note);
                    NoteChanged?.Invoke(note.HitObject);
                }

                if (selectionStart.HasValue && selectionEnd.HasValue && targets.Count > 1)
                {
                    selectionStart = targets.Min(note => (double)note.HitObject.Time);
                    selectionEnd = targets.Max(note => (double)note.HitObject.Time);
                    updateSelectionVisuals();
                    notifySelectionChanged();
                }

                return changes.Count;
            }

            public bool SnapHitObjectToNearestTransient(HitObject hitObject, double maxDistanceMs)
            {
                if (!tryGetNearestTransientTime(hitObject.Time, maxDistanceMs, out int snappedTime))
                    return false;

                if (snappedTime == hitObject.Time)
                    return false;

                hitObject.Time = snappedTime;
                NoteChanged?.Invoke(hitObject);
                return true;
            }

            private bool tryGetNearestTransientTime(double time, double maxDistanceMs, out int snappedTime)
            {
                snappedTime = 0;

                if (detectedOnsets.Count == 0)
                    return false;

                double nearest = double.NaN;
                double minDiff = double.MaxValue;

                foreach (var onset in detectedOnsets)
                {
                    double diff = Math.Abs(onset - time);
                    if (diff < minDiff)
                    {
                        minDiff = diff;
                        nearest = onset;
                    }
                }

                if (!double.IsFinite(nearest))
                    return false;

                double effectiveMaxDistance = Math.Max(0, maxDistanceMs);
                if (minDiff > effectiveMaxDistance)
                    return false;

                snappedTime = (int)Math.Round(Math.Max(0, nearest));
                return true;
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
                        float viewportAnchorX = scroll.ToLocalSpace(e.ScreenSpaceMousePosition).X;
                        setZoomInternal(zoom * factor, true, viewportAnchorX);
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
                laneLabelLayer.Clear();
                float laneLabelFontSize = laneCount >= 8 ? 10.8f : 12.2f;
                float laneLabelHorizontalPadding = laneCount >= 8 ? 6f : 9f;

                for (int lane = 0; lane < laneCount; lane++)
                {
                    float fraction = (float)lane / laneCount;
                    var laneBase = UITheme.GetLaneColourForLogicalIndex(lane, laneCount);
                    var laneEdge = UITheme.GetLaneEdgeColourForLogicalIndex(lane, laneCount);
                    var laneFill = EditorColours.Mix(EditorColours.TimelineRowFill, laneBase, 0.42f).Opacity(0.85f);
                    var edgeColour = EditorColours.Mix(EditorColours.TimelineRowLine, laneEdge, 0.55f).Opacity(0.9f);

                    laneBackgrounds.Add(new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Height = 1f / laneCount,
                        RelativePositionAxes = Axes.Y,
                        Y = fraction,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = laneFill
                            },
                            new Box
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 1,
                                Anchor = Anchor.BottomLeft,
                                Origin = Anchor.BottomLeft,
                                Colour = edgeColour
                            }
                        }
                    });

                    laneLabelLayer.Add(new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Height = 1f / laneCount,
                        RelativePositionAxes = Axes.Y,
                        Y = fraction,
                        Child = new Container
                        {
                            AutoSizeAxes = Axes.Both,
                            Masking = true,
                            CornerRadius = 6,
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            X = 10,
                            Children = new Drawable[]
                            {
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = EditorColours.Mix(EditorColours.TimelineLabelBackground, laneBase, 0.26f).Opacity(0.92f)
                                },
                                new SpriteText
                                {
                                    Text = getLaneLabel(lane),
                                    Font = BeatSightFont.Caption(laneLabelFontSize),
                                    Colour = EditorColours.TimelineLabelText,
                                    Margin = new MarginPadding { Horizontal = laneLabelHorizontalPadding, Vertical = 4 },
                                    Alpha = 0.96f
                                }
                            }
                        }
                    });
                }
            }

            private void resolveLaneConfiguration(Beatmap beatmap)
            {
                int laneCountFromLayout = 0;
                if (beatmap.DrumKit?.LaneLayout?.Lanes != null && beatmap.DrumKit.LaneLayout.Lanes.Count > 0)
                    laneCountFromLayout = beatmap.DrumKit.LaneLayout.Lanes.Max(l => l.Index) + 1;

                int laneCountFromHits = beatmap.HitObjects
                    .Where(h => h.Lane.HasValue)
                    .Select(h => h.Lane!.Value)
                    .DefaultIfEmpty(-1)
                    .Max() + 1;

                int laneCountFromEditor = beatmap.Editor?.VisualLanes ?? 0;
                int laneCountFromComponents = 0;
                bool hasExplicitLaneData = laneCountFromLayout > 0 || laneCountFromHits > 0 || laneCountFromEditor > 0;

                if (!hasExplicitLaneData)
                {
                    IReadOnlyList<string> componentSource = beatmap.DrumKit?.Components?.Count > 0
                        ? beatmap.DrumKit.Components
                        : beatmap.HitObjects
                            .Select(h => h.Component)
                            .Where(component => !string.IsNullOrWhiteSpace(component))
                            .Distinct(StringComparer.OrdinalIgnoreCase)
                            .ToList();

                    if (componentSource.Count > 0)
                    {
                        var groupedLayout = LaneLayoutFactory.CreateFromComponents(componentSource.ToList());
                        laneCountFromComponents = groupedLayout.LaneCount;
                    }
                }

                int resolvedLaneCount = Math.Max(
                    Math.Max(laneCountFromLayout, laneCountFromHits),
                    Math.Max(laneCountFromEditor, laneCountFromComponents));

                if (resolvedLaneCount <= 0)
                    resolvedLaneCount = defaultLaneCount;

                laneCount = Math.Clamp(resolvedLaneCount, 1, maxEditorLaneCount);

                laneMapping = buildLaneComponentMapping(beatmap, laneCount);
                rebuildLaneResolutionLayout();
            }

            private List<string> buildLaneComponentMapping(Beatmap beatmap, int count)
            {
                var defaults = new List<string>(new[]
                {
                    "kick",
                    "snare",
                    "hihat_closed",
                    "tom_high",
                    "tom_mid",
                    "crash",
                    "ride_bow"
                });

                while (defaults.Count < count)
                    defaults.Add(defaults[defaults.Count % 7]);

                var result = defaults.Take(count).ToList();

                var byLane = beatmap.HitObjects
                    .Where(h => h.Lane.HasValue && h.Lane.Value >= 0 && h.Lane.Value < count && !string.IsNullOrWhiteSpace(h.Component))
                    .GroupBy(h => h.Lane!.Value)
                    .ToList();

                foreach (var laneGroup in byLane)
                {
                    string mostFrequent = laneGroup
                        .GroupBy(h => h.Component)
                        .OrderByDescending(g => g.Count())
                        .Select(g => g.Key)
                        .FirstOrDefault() ?? result[laneGroup.Key];

                    result[laneGroup.Key] = mostFrequent;
                }

                if (byLane.Count == 0)
                {
                    var fallbackComponents = beatmap.HitObjects
                        .Where(h => !string.IsNullOrWhiteSpace(h.Component))
                        .GroupBy(h => h.Component)
                        .OrderByDescending(group => group.Count())
                        .Select(group => group.Key)
                        .Distinct(StringComparer.OrdinalIgnoreCase)
                        .Take(count)
                        .ToList();

                    for (int i = 0; i < fallbackComponents.Count; i++)
                        result[i] = fallbackComponents[i];
                }

                return result;
            }

            private string getLaneLabel(int laneIndex)
            {
                if (beatmap?.DrumKit?.LaneLayout?.Lanes != null)
                {
                    var laneInfo = beatmap.DrumKit.LaneLayout.Lanes.FirstOrDefault(l => l.Index == laneIndex);
                    if (laneInfo != null)
                    {
                        if (!string.IsNullOrWhiteSpace(laneInfo.ShortName))
                            return laneInfo.ShortName!;

                        if (!string.IsNullOrWhiteSpace(laneInfo.Name))
                            return laneInfo.Name!;
                    }
                }

                if (laneIndex >= 0 && laneIndex < laneMapping.Count)
                    return formatLaneName(laneMapping[laneIndex]);

                return $"Lane {laneIndex + 1}";
            }

            private static string formatLaneName(string component)
            {
                if (string.IsNullOrWhiteSpace(component))
                    return "Lane";

                string raw = component.Replace('_', ' ').Trim();
                if (raw.Length == 0)
                    return "Lane";

                var titleCase = CultureInfo.InvariantCulture.TextInfo.ToTitleCase(raw.ToLowerInvariant());
                return titleCase.Length <= 14 ? titleCase : titleCase[..14];
            }

            private void rebuildLaneResolutionLayout()
            {
                var categoryMap = new Dictionary<DrumComponentCategory, HashSet<int>>();

                for (int lane = 0; lane < laneMapping.Count; lane++)
                {
                    var classification = DrumLaneHeuristics.ClassifyComponent(laneMapping[lane]);
                    foreach (var category in classification.Categories)
                    {
                        if (!categoryMap.TryGetValue(category, out var lanes))
                        {
                            lanes = new HashSet<int>();
                            categoryMap[category] = lanes;
                        }

                        lanes.Add(lane);
                    }
                }

                if (categoryMap.Count == 0)
                {
                    laneResolutionLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
                    return;
                }

                laneResolutionLayout = LaneLayoutFactory.CreateCustom(
                    LanePreset.Custom,
                    Math.Max(1, laneCount),
                    categoryMap.ToDictionary(pair => pair.Key, pair => pair.Value.OrderBy(index => index).ToArray()));
            }

            private void rebuildWaveform()
            {
                waveformDrawable.SetData(waveform, PixelsPerSecond, waveformScale);
            }

            private void rebuildBeatGrid(double? viewStartMs = null, double? viewEndMs = null)
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

                var measureColour = new Color4(247, 212, 152, 220);
                var beatColour = new Color4(138, 178, 232, 178);
                var subdivisionColour = new Color4(104, 128, 175, 132);

                float surfaceWidth = timelineSurface.Width;
                double duration = durationMs;
                double minTime = Math.Clamp(viewStartMs ?? 0, 0, duration);
                double maxTime = Math.Clamp(viewEndMs ?? duration, 0, duration);

                if (maxTime < minTime)
                    (minTime, maxTime) = (maxTime, minTime);

                void addLine(double timeMs, Color4 colour, float alpha, float width)
                {
                    if (timeMs < minTime - 1 || timeMs > maxTime + 1)
                        return;

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
                    int startMeasure = Math.Max(0, (int)Math.Floor(minTime / measureMs) - 1);
                    int endMeasure = Math.Max(startMeasure, (int)Math.Ceiling(maxTime / measureMs) + 1);

                    for (int i = startMeasure; i <= endMeasure; i++)
                    {
                        double time = i * measureMs;
                        addLine(time, measureColour, 0.92f, 2.2f);
                    }
                }

                if (drawBeats)
                {
                    int startBeat = Math.Max(0, (int)Math.Floor(minTime / beatMs) - 1);
                    int endBeat = Math.Max(startBeat, (int)Math.Ceiling(maxTime / beatMs) + 1);

                    for (int i = startBeat; i <= endBeat; i++)
                    {
                        if (drawMeasures && beatsPerMeasure > 0 && i % beatsPerMeasure == 0)
                            continue;

                        double time = i * beatMs;
                        addLine(time, beatColour, 0.66f, 1.15f);
                    }
                }

                if (drawSubdivisions && snapIntervalMs.HasValue)
                {
                    double interval = snapIntervalMs.Value;
                    double beatLengthTolerance = Math.Max(beatMs * 0.01, 0.5);
                    double measureLengthTolerance = Math.Max(measureMs * 0.01, 1);
                    int startSubdivision = Math.Max(0, (int)Math.Floor(minTime / interval) - 1);
                    int endSubdivision = Math.Max(startSubdivision, (int)Math.Ceiling(maxTime / interval) + 1);

                    for (int i = startSubdivision; i <= endSubdivision; i++)
                    {
                        double time = i * interval;

                        if (drawMeasures && isMultiple(time, measureMs, measureLengthTolerance))
                            continue;

                        if (drawBeats && isMultiple(time, beatMs, beatLengthTolerance))
                            continue;

                        addLine(time, subdivisionColour, 0.48f, 1f);
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

            private void rebuildRuler(double? viewStartMs = null, double? viewEndMs = null)
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
                    Colour = EditorColours.Divider.Opacity(0.75f)
                });

                double duration = durationMs;
                double pixelsPerSecond = PixelsPerSecond;
                double minTime = Math.Clamp(viewStartMs ?? 0, 0, duration);
                double maxTime = Math.Clamp(viewEndMs ?? duration, 0, duration);

                if (maxTime < minTime)
                    (minTime, maxTime) = (maxTime, minTime);

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

                int startMajorTick = Math.Max(0, (int)Math.Floor(minTime / majorStepMs) - 1);
                int endMajorTick = Math.Max(startMajorTick, (int)Math.Ceiling(maxTime / majorStepMs) + 1);

                void addTick(double timeMs, bool major)
                {
                    if (timeMs < minTime - 1 || timeMs > maxTime + 1)
                        return;

                    float x = (float)(timeMs / 1000.0 * pixelsPerSecond);
                    if (x < -2 || x > timelineSurface.Width + 4)
                        return;

                    rulerTickLayer.Add(new Box
                    {
                        Width = major ? 2f : 1f,
                        Height = major ? 15f : 9f,
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomCentre,
                        X = x,
                        Colour = major
                            ? new Color4(224, 236, 255, 255)
                            : new Color4(148, 172, 214, 214)
                    });

                    if (!major)
                        return;

                    var label = new SpriteText
                    {
                        Text = formatRulerLabel(timeMs),
                        Font = BeatSightFont.Title(11.6f),
                        Colour = EditorColours.TextSecondary,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.BottomCentre,
                        X = x,
                        Y = -19,
                        Alpha = 0.95f
                    };

                    rulerTickLayer.Add(label);
                }

                for (int i = startMajorTick; i <= endMajorTick; i++)
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
                updateViewportHint(force: true);
            }

            private void refreshNotes(bool updateDepth = true)
            {
                if (notes.Count == 0)
                    return;

                float laneHeight = laneHeightForNotes();

                foreach (var note in notes)
                {
                    note.UpdateLayout(PixelsPerSecond, laneHeight);

                    if (updateDepth)
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
                laneAreaHeight = Math.Max(laneAreaHeight, timelineSurface.DrawHeight - rulerHeight - 2f);
                laneAreaHeight = Math.Max(laneAreaHeight, DrawHeight - rulerHeight - 2f);
                laneAreaHeight = Math.Max(laneAreaHeight, contentArea.DrawSize.Y - rulerHeight - 2f);

                if (laneAreaHeight <= 0)
                    laneAreaHeight = laneCount * 20f;

                return laneAreaHeight / Math.Max(1, laneCount);
            }

            private TimelineNoteDrawable createNoteDrawable(HitObject hit)
            {
                var note = new TimelineNoteDrawable(
                    hit,
                    laneCount,
                    time => (float)(time / 1000.0 * PixelsPerSecond),
                    x => Math.Max(0, x / PixelsPerSecond * 1000),
                    component => resolveLaneFromComponent(component))
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

            private int resolveLaneFromComponent(string component)
            {
                if (!string.IsNullOrWhiteSpace(component))
                {
                    int exact = laneMapping.FindIndex(mapped => string.Equals(mapped, component, StringComparison.OrdinalIgnoreCase));
                    if (exact >= 0)
                        return exact;
                }

                int resolved = DrumLaneHeuristics.ResolveLane(component, laneResolutionLayout);
                return Math.Clamp(resolved, 0, Math.Max(0, laneCount - 1));
            }

            private void onNoteSelected(TimelineNoteDrawable note)
            {
                if (selectedNote != null && selectedNote != note)
                    selectedNote.SetSelected(false);

                clearSelectionRange();
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
                updateViewportHint(force: true);
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
                int lane = resolveLaneFromYPosition(yPosition);
                addNoteAtLane(timeMs, lane);
            }

            private int resolveLaneFromYPosition(float yPosition)
            {
                if (laneCount <= 0)
                    return 0;

                float laneAreaHeight = laneHeightForNotes() * laneCount;
                if (laneAreaHeight <= 0)
                    laneAreaHeight = laneCount;

                float clampedY = Math.Clamp(yPosition, 0, laneAreaHeight);
                return Math.Clamp((int)(clampedY / Math.Max(1, laneAreaHeight) * laneCount), 0, laneCount - 1);
            }

            private void addNoteAtLane(double timeMs, int lane)
            {
                if (beatmap == null || laneCount <= 0)
                    return;

                double snapped = snapIntervalMs.HasValue
                    ? snapToInterval(timeMs, snapIntervalMs.Value)
                    : timeMs;

                int resolvedLane = Math.Clamp(lane, 0, laneCount - 1);
                string component = laneMapping.Count > 0
                    ? laneMapping[Math.Clamp(resolvedLane, 0, laneMapping.Count - 1)]
                    : "kick";

                var hit = new HitObject
                {
                    Time = (int)Math.Round(snapped),
                    Lane = resolvedLane,
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
                updateViewportHint(force: true);
            }

            private void updateSurfaceWidth(bool rebuildStaticLayers = true)
            {
                double pixelWidth = Math.Max(1000, durationMs / 1000.0 * PixelsPerSecond);
                timelineSurface.Width = (float)pixelWidth;

                if (rebuildStaticLayers)
                {
                    rebuildBeatGrid();
                    rebuildRuler();
                }

                laneLayoutDirty = true;
            }

            private static double snapToInterval(double value, double interval)
            {
                if (interval <= 0)
                    return value;

                double snapped = Math.Round(value / interval) * interval;
                return snapped < 0 ? 0 : snapped;
            }

            private void setZoomInternal(double targetZoom, bool notify, float? viewportAnchorX = null)
            {
                double clamped = Math.Clamp(targetZoom, MinZoom, MaxZoom);
                if (Precision.AlmostEquals(clamped, zoom))
                    return;

                double previousPixelsPerSecond = PixelsPerSecond;
                double viewportWidth = scroll.DrawWidth;
                double resolvedViewportAnchorX;
                double anchorTimeMs;

                if (zoomInteractionActive)
                {
                    resolvedViewportAnchorX = zoomInteractionViewportAnchorX;
                    anchorTimeMs = zoomInteractionAnchorTimeMs;
                }
                else
                {
                    if (viewportAnchorX.HasValue)
                    {
                        resolvedViewportAnchorX = viewportAnchorX.Value;
                    }
                    else
                    {
                        // Default to viewport-centred zoom for discrete actions.
                        resolvedViewportAnchorX = viewportWidth > 0 ? viewportWidth * 0.5 : 0;
                    }

                    if (!double.IsFinite(resolvedViewportAnchorX))
                        resolvedViewportAnchorX = 0;

                    if (viewportWidth > 0)
                    {
                        if (resolvedViewportAnchorX < 0 || resolvedViewportAnchorX > viewportWidth)
                            resolvedViewportAnchorX = viewportWidth * 0.5;

                        resolvedViewportAnchorX = Math.Clamp(resolvedViewportAnchorX, 0, viewportWidth);
                    }

                    anchorTimeMs = previousPixelsPerSecond > 0
                        ? (scroll.Current + resolvedViewportAnchorX) / previousPixelsPerSecond * 1000.0
                        : 0;
                }

                zoom = clamped;
                bool deferLayerRebuild = zoomInteractionActive;
                updateSurfaceWidth(rebuildStaticLayers: !deferLayerRebuild);
                restoreZoomAnchor(anchorTimeMs, resolvedViewportAnchorX);

                if (deferLayerRebuild)
                {
                    var (viewStart, viewEnd) = getViewportTimeRangeMs(0.65);
                    rebuildBeatGrid(viewStart, viewEnd);
                    rebuildRuler(viewStart, viewEnd);
                    refreshNotes(updateDepth: false);
                    waveformDrawable.SetPreviewPixelsPerSecond(PixelsPerSecond);
                    zoomInteractionDeferredLayerRebuild = true;
                }
                else
                {
                    refreshNotes(updateDepth: false);
                    waveformDrawable.SetPixelsPerSecond(PixelsPerSecond);
                }

                laneLayoutDirty = false;

                if (notify)
                    ZoomChanged?.Invoke(zoom);
            }

            private (double startMs, double endMs) getViewportTimeRangeMs(double paddingViewportFactor)
            {
                if (durationMs <= 0 || PixelsPerSecond <= 0 || scroll.DrawWidth <= 0)
                    return (0, Math.Max(0, durationMs));

                double viewportDurationMs = scroll.DrawWidth / PixelsPerSecond * 1000.0;
                double paddingMs = Math.Max(0, viewportDurationMs * paddingViewportFactor);
                double startMs = Math.Max(0, scroll.Current / PixelsPerSecond * 1000.0 - paddingMs);
                double endMs = Math.Min(durationMs, (scroll.Current + scroll.DrawWidth) / PixelsPerSecond * 1000.0 + paddingMs);

                if (endMs < startMs)
                    (startMs, endMs) = (endMs, startMs);

                return (startMs, endMs);
            }

            private void updateViewportHint(bool force = false)
            {
                if (viewportHintContainer == null || viewportHintText == null)
                    return;

                var (startMs, endMs) = getViewportTimeRangeMs(0);
                if (!force
                    && double.IsFinite(lastViewportHintStartMs)
                    && Math.Abs(startMs - lastViewportHintStartMs) < viewportHintRefreshDeltaMs
                    && Math.Abs(endMs - lastViewportHintEndMs) < viewportHintRefreshDeltaMs)
                {
                    return;
                }

                lastViewportHintStartMs = startMs;
                lastViewportHintEndMs = endMs;

                string? message = resolveViewportHintMessage(startMs, endMs);
                if (string.Equals(lastViewportHintMessage, message, StringComparison.Ordinal))
                    return;

                lastViewportHintMessage = message;

                if (string.IsNullOrWhiteSpace(message))
                {
                    viewportHintContainer.FadeOut(120, Easing.OutQuint);
                    return;
                }

                viewportHintText.Text = message;
                viewportHintContainer.FadeIn(120, Easing.OutQuint);
            }

            private string? resolveViewportHintMessage(double viewStartMs, double viewEndMs)
            {
                if (beatmap == null)
                    return "Load a beatmap to start editing.";

                if (beatmap.HitObjects.Count == 0)
                    return "No notes yet. Double-click the timeline to add one.";

                int? previous = null;
                int? next = null;

                foreach (var hit in beatmap.HitObjects)
                {
                    if (hit.Time < viewStartMs)
                    {
                        previous = hit.Time;
                        continue;
                    }

                    if (hit.Time <= viewEndMs)
                        return null;

                    next = hit.Time;
                    break;
                }

                if (previous.HasValue && next.HasValue)
                    return $"No notes in view. Prev {formatTimelineHintTime(previous.Value)}  Next {formatTimelineHintTime(next.Value)}";

                if (next.HasValue)
                    return $"No notes in view. Next note at {formatTimelineHintTime(next.Value)} (press .)";

                if (previous.HasValue)
                    return $"Past final note ({formatTimelineHintTime(previous.Value)}). Press , to step back.";

                return "No notes in this beatmap.";
            }

            private static string formatTimelineHintTime(double milliseconds)
            {
                var time = TimeSpan.FromMilliseconds(Math.Max(0, milliseconds));
                if (time.TotalHours >= 1)
                    return $"{(int)time.TotalHours:00}:{time.Minutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";

                return $"{(int)time.TotalMinutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";
            }

            private void restoreZoomAnchor(double anchorTimeMs, double viewportAnchorX)
            {
                if (scroll.DrawWidth <= 0)
                    return;

                double targetX = anchorTimeMs / 1000.0 * PixelsPerSecond;
                double targetScroll = targetX - viewportAnchorX;
                double maxScroll = Math.Max(0, timelineSurface.Width - scroll.DrawWidth);
                // Keep zoom anchoring spatially stable; animated scroll reads as lateral panning.
                scroll.ScrollTo((float)Math.Clamp(targetScroll, 0, maxScroll), false);
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

            private void setWaveformScaleInternal(double scale, bool forceApply = false)
            {
                double clamped = Math.Clamp(scale, MinWaveformScale, MaxWaveformScale);
                if (Precision.AlmostEquals(clamped, waveformScale) && !forceApply)
                    return;

                waveformScale = clamped;
                waveformDrawable.SetAmplitudeScale(waveformScale);
            }

            private void updateSelectionVisuals()
            {
                if (selectionStart.HasValue && selectionEnd.HasValue)
                {
                    double start = Math.Min(selectionStart.Value, selectionEnd.Value);
                    double end = Math.Max(selectionStart.Value, selectionEnd.Value);
                    double duration = end - start;

                    selectionBox.X = (float)(start / 1000.0 * PixelsPerSecond);
                    selectionBox.Width = (float)(duration / 1000.0 * PixelsPerSecond);
                    selectionBox.Alpha = 1;
                }
                else
                {
                    selectionBox.Alpha = 0;
                }
            }

            private void notifySelectionChanged()
                => SelectionChanged?.Invoke(selectionStart, selectionEnd);

            private void clearSelectionRange()
            {
                if (!selectionStart.HasValue && !selectionEnd.HasValue)
                    return;

                selectionStart = null;
                selectionEnd = null;
                updateSelectionVisuals();
                notifySelectionChanged();
            }

            protected override bool OnMouseDown(MouseDownEvent e)
            {
                if (e.Button == MouseButton.Left && e.ShiftPressed)
                {
                    if (selectedNote != null)
                    {
                        selectedNote.SetSelected(false);
                        selectedNote = null;
                    }

                    float x = timelineSurface.ToLocalSpace(e.ScreenSpaceMousePosition).X;
                    double time = x / PixelsPerSecond * 1000;
                    selectionStart = time;
                    selectionEnd = time;
                    updateSelectionVisuals();
                    notifySelectionChanged();
                    return true;
                }

                if (e.Button == MouseButton.Left && !e.ShiftPressed)
                    clearSelectionRange();

                return base.OnMouseDown(e);
            }

            protected override void OnDrag(DragEvent e)
            {
                if (selectionStart.HasValue && e.Button == MouseButton.Left && e.ShiftPressed)
                {
                    float x = timelineSurface.ToLocalSpace(e.ScreenSpaceMousePosition).X;
                    double time = x / PixelsPerSecond * 1000;
                    selectionEnd = time;
                    updateSelectionVisuals();
                    notifySelectionChanged();
                }
                base.OnDrag(e);
            }
        }

        private partial class WaveformDrawable : CompositeDrawable
        {
            private WaveformData? waveform;
            private double pixelsPerSecond = 1;
            private double amplitudeScale = 1.0;
            private double previewHorizontalScale = 1.0;
            private double previewVerticalScale = 1.0;
            private readonly FillFlowContainer barFlow;

            public WaveformDrawable()
            {
                RelativeSizeAxes = Axes.Both;
                Anchor = Anchor.CentreLeft;
                Origin = Anchor.CentreLeft;

                InternalChild = barFlow = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.Y,
                    AutoSizeAxes = Axes.X,
                    Direction = FillDirection.Horizontal,
                    Spacing = Vector2.Zero
                };
            }

            public void SetData(WaveformData? waveform, double pixelsPerSecond, double amplitudeScale = 1.0)
            {
                this.waveform = waveform;
                this.pixelsPerSecond = Math.Max(1, pixelsPerSecond);
                this.amplitudeScale = Math.Clamp(amplitudeScale, MinWaveformScale, MaxWaveformScale);
                previewHorizontalScale = 1.0;
                previewVerticalScale = 1.0;
                applyPreviewScale();
                rebuild();
            }

            public void SetPixelsPerSecond(double pixelsPerSecond)
            {
                this.pixelsPerSecond = Math.Max(1, pixelsPerSecond);
                previewHorizontalScale = 1.0;
                applyPreviewScale();
                updateBucketWidths();
            }

            public void SetPreviewPixelsPerSecond(double pixelsPerSecond)
            {
                double previewPixelsPerSecond = Math.Max(1, pixelsPerSecond);
                if (!double.IsFinite(previewPixelsPerSecond) || this.pixelsPerSecond <= 0)
                    return;

                float ratio = (float)(previewPixelsPerSecond / this.pixelsPerSecond);
                if (!float.IsFinite(ratio) || ratio <= 0)
                    return;

                previewHorizontalScale = ratio;
                applyPreviewScale();
            }

            public void SetAmplitudeScale(double scale)
            {
                amplitudeScale = Math.Clamp(scale, MinWaveformScale, MaxWaveformScale);
                previewVerticalScale = 1.0;
                applyPreviewScale();
                rebuild();
            }

            public void SetPreviewAmplitudeScale(double scale)
            {
                double clamped = Math.Clamp(scale, MinWaveformScale, MaxWaveformScale);
                if (!double.IsFinite(clamped) || amplitudeScale <= 0)
                    return;

                previewVerticalScale = clamped / amplitudeScale;
                applyPreviewScale();
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
                        Colour = EditorColours.TimelineWaveform
                    };

                    var barShadow = new Box
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Width = (float)Math.Max(1, bucketWidth),
                        RelativeSizeAxes = Axes.Y,
                        Height = Math.Min(1f, height + 0.08f),
                        Colour = EditorColours.TimelineWaveformShadow,
                        Y = 0.7f
                    };

                    container.Add(barShadow);
                    container.Add(bar);
                    barFlow.Add(container);
                }
            }

            private void updateBucketWidths()
            {
                if (waveform == null || waveform.BucketCount == 0 || barFlow.Count == 0)
                    return;

                float bucketWidth = (float)Math.Max(1, pixelsPerSecond * waveform.BucketDurationSeconds);

                foreach (Drawable drawable in barFlow.Children)
                {
                    if (drawable is not Container container)
                        continue;

                    container.Width = bucketWidth;

                    foreach (Drawable barDrawable in container.Children)
                    {
                        if (barDrawable is Box box)
                            box.Width = bucketWidth;
                    }
                }
            }

            private void applyPreviewScale()
            {
                float xScale = (float)(double.IsFinite(previewHorizontalScale) && previewHorizontalScale > 0
                    ? previewHorizontalScale
                    : 1.0);
                float yScale = (float)(double.IsFinite(previewVerticalScale) && previewVerticalScale > 0
                    ? previewVerticalScale
                    : 1.0);
                Scale = new Vector2(xScale, yScale);
            }
        }

        private partial class TimelineNoteDrawable : CompositeDrawable
        {
            private const float baseWidth = 20;
            private readonly Func<double, float> timeToX;
            private readonly Func<float, double> xToTime;
            private readonly Func<string, int> resolveLaneFromComponent;
            private readonly int laneCount;
            private readonly Box background;
            private readonly Box border;
            private readonly Box topSheen;
            private readonly Box selectionOverlay;

            public HitObject HitObject { get; }

            public event Action<TimelineNoteDrawable>? Selected;
            public event Action<TimelineNoteDrawable>? DeleteRequested;
            public event Action<TimelineNoteDrawable, double>? Dragged;
            public event Action<TimelineNoteDrawable, int>? LaneChanged;
            public event Action? DragStarted;

            public TimelineNoteDrawable(
                HitObject hitObject,
                int laneCount,
                Func<double, float> timeToX,
                Func<float, double> xToTime,
                Func<string, int> resolveLaneFromComponent)
            {
                HitObject = hitObject;
                this.laneCount = laneCount;
                this.timeToX = timeToX;
                this.xToTime = xToTime;
                this.resolveLaneFromComponent = resolveLaneFromComponent;

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
                    topSheen = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Height = 0.45f,
                        Colour = Color4.White.Opacity(0.12f)
                    },
                    border = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White,
                        Alpha = 0.08f
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
                int lane = resolveEffectiveLane();
                float y = laneHeight * lane + laneHeight / 2;

                Position = new Vector2(x, y);
                Size = new Vector2(baseWidth, Math.Clamp(laneHeight * 0.72f, 16f, 44f));
            }

            public void SetSelected(bool selected)
            {
                selectionOverlay.Alpha = selected ? 0.4f : 0f;
                border.Alpha = selected ? 0.32f : 0.08f;
                this.ScaleTo(selected ? 1.05f : 1f, 120, Easing.OutQuint);
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
                float parentX = Parent?.ToLocalSpace(e.ScreenSpaceMousePosition).X ?? X;
                Dragged?.Invoke(this, xToTime(parentX));
            }

            protected override bool OnScroll(ScrollEvent e)
            {
                if (e.ControlPressed || e.AltPressed)
                    return false;

                int laneDelta = e.ScrollDelta.Y > 0 ? -1 : 1;
                int lane = Math.Clamp(resolveEffectiveLane() + laneDelta, 0, laneCount - 1);
                DragStarted?.Invoke();
                LaneChanged?.Invoke(this, lane);
                return true;
            }

            protected override bool OnHover(HoverEvent e)
            {
                if (selectionOverlay.Alpha <= Precision.FLOAT_EPSILON)
                    border.FadeTo(0.2f, 80, Easing.OutQuint);

                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                if (selectionOverlay.Alpha <= Precision.FLOAT_EPSILON)
                    border.FadeTo(0.08f, 90, Easing.OutQuint);

                base.OnHoverLost(e);
            }

            private static Color4 ResolveColour(string component)
            {
                string key = component?.ToLowerInvariant() ?? string.Empty;
                if (key.StartsWith("kick"))
                    return new Color4(255, 120, 120, 255);

                if (key.StartsWith("snare") || key.StartsWith("cross_stick"))
                    return new Color4(120, 180, 255, 255);

                if (key.StartsWith("hihat_closed"))
                    return new Color4(255, 220, 120, 255);

                if (key.StartsWith("hihat_open") || key.StartsWith("hihat_pedal"))
                    return new Color4(255, 205, 130, 255);

                if (key.StartsWith("tom_") || key.StartsWith("tom"))
                    return new Color4(140, 220, 170, 255);

                if (key.StartsWith("crash") || key.StartsWith("china") || key.StartsWith("splash"))
                    return new Color4(255, 160, 220, 255);

                if (key.StartsWith("ride"))
                    return new Color4(170, 190, 255, 255);

                return new Color4(200, 200, 220, 255);
            }

            private int resolveEffectiveLane()
            {
                if (HitObject.Lane.HasValue && HitObject.Lane.Value >= 0 && HitObject.Lane.Value < laneCount)
                    return HitObject.Lane.Value;

                return Math.Clamp(resolveLaneFromComponent(HitObject.Component), 0, laneCount - 1);
            }

        }
    }
}
