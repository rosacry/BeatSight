using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;

namespace BeatSight.Game.Screens.Playback.Playfield.Notation
{
    /// <summary>
    /// Scrolling drum sheet music: a real five-line staff with a percussion clef, standard drum-key note positions,
    /// hands stems-up / feet stems-down, beat-wise beaming, rests, bar lines and a beat ruler. The playhead, ruler,
    /// bar lines and notes share one time-to-x mapping, so "now" is always exactly at the playhead.
    /// </summary>
    public partial class DrumStaffView : CompositeDrawable
    {
        private static readonly Color4 paper = new Color4(14, 18, 26, 255);
        private static readonly Color4 staffInk = new Color4(150, 162, 186, 210);
        private static readonly Color4 ink = new Color4(222, 228, 240, 240);
        private static readonly Color4 barInk = new Color4(176, 188, 210, 220);

        private const float playhead_ratio = 0.22f;
        private const double hit_pulse_ms = 170;

        /// <summary>Compact mode (editor preview): no ruler labels or legend.</summary>
        public bool Compact { get; init; }

        private readonly Box paperBackground;
        private readonly Container staffLineLayer;
        private readonly Container scrollLayer;
        private readonly Box pastShade;
        private readonly Container gutterLayer;
        private readonly Container playheadLayer;
        private readonly FillFlowContainer legend;

        private DrumTempoMap tempo = new DrumTempoMap(null);
        private List<DrumStaffInputNote> notes = new List<DrumStaffInputNote>();
        private readonly Dictionary<int, MeasureDrawable> measures = new Dictionary<int, MeasureDrawable>();
        private IReadOnlyList<DrumNotationSymbol> legendSymbols = Array.Empty<DrumNotationSymbol>();

        private double now;
        private double zoom = 1.0;
        private ManuscriptCountInGuideMode countInMode = ManuscriptCountInGuideMode.Full;
        private string? focusName;
        private bool layoutDirty = true;
        private Vector2 lastLayoutSize;

        // Layout (local pixels)
        private float space;
        private float middleY;
        private float gutterWidth;
        private float playheadX;
        private double pxPerMs;

        public DrumStaffView()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                paperBackground = new Box { RelativeSizeAxes = Axes.Both, Colour = paper },
                staffLineLayer = new Container { RelativeSizeAxes = Axes.Both },
                // Measures are positioned individually (each with its real on-screen bounds) so osu!'s culling
                // never treats far-scrolled content as masked away.
                scrollLayer = new Container { RelativeSizeAxes = Axes.Both },
                pastShade = new Box { RelativeSizeAxes = Axes.Y, Colour = paper, Alpha = 0.5f },
                gutterLayer = new Container { RelativeSizeAxes = Axes.Y },
                playheadLayer = new Container { RelativeSizeAxes = Axes.Both },
                legend = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Direction = FillDirection.Full,
                    Spacing = new Vector2(22, 6),
                }
            };
        }

        #region Public API

        public void SetBeatmap(Beatmap? beatmap)
        {
            tempo = new DrumTempoMap(beatmap?.Timing);
            notes = beatmap?.HitObjects?
                        .Select(h => new DrumStaffInputNote(h.Time, h.Component, h.Velocity))
                        .OrderBy(n => n.Time)
                        .ToList()
                    ?? new List<DrumStaffInputNote>();

            legendSymbols = notes
                .Select(n => DrumNotation.Resolve(n.Component))
                .GroupBy(s => s.Name)
                .Select(g => g.First())
                .OrderByDescending(s => s.StaffStep)
                .ThenBy(s => s.Name, StringComparer.Ordinal)
                .ToArray();

            layoutDirty = true;
        }

        public void SetTime(double timeMs) => now = timeMs;

        public void SetZoom(double value)
        {
            double clamped = Math.Clamp(value, 0.2, 5.0);
            if (Math.Abs(clamped - zoom) < 0.0001)
                return;

            zoom = clamped;
            layoutDirty = true;
        }

        /// <summary>
        /// Emphasises one instrument (e.g. the editor's selected note); other noteheads are drawn faded.
        /// </summary>
        public void SetFocusComponent(string? component)
        {
            string? key = string.IsNullOrWhiteSpace(component) ? null : DrumNotation.Resolve(component).Name;
            if (string.Equals(key, focusName, StringComparison.Ordinal))
                return;

            focusName = key;
            layoutDirty = true;
        }

        internal string? FocusName => focusName;

        public void SetCountInGuideMode(ManuscriptCountInGuideMode mode)
        {
            if (countInMode == mode)
                return;

            countInMode = mode;
            layoutDirty = true;
        }

        public bool HasLayout => pxPerMs > 0 && DrawWidth > 0;
        public float PlayheadX => playheadX;
        public float TimelineLeftX => gutterWidth;
        public float StaffSpace => space;

        public float XAtTime(double timeMs) => playheadX + (float)((timeMs - now) * pxPerMs);

        public double TimeAtX(float x) => pxPerMs <= 0 ? now : now + (x - playheadX) / pxPerMs;

        public float YForStep(float staffStep) => middleY - staffStep * space / 2f;

        /// <summary>The component written closest to <paramref name="y"/> (for editor placement on the staff).</summary>
        public string ComponentAtY(float y)
        {
            float step = (middleY - y) / Math.Max(1f, space / 2f);
            return DrumNotation.BottomToTop
                .OrderBy(c => Math.Abs(DrumNotation.Resolve(c).StaffStep - step))
                .First();
        }

        #endregion

        protected override void Update()
        {
            base.Update();

            if (DrawWidth <= 1 || DrawHeight <= 1)
                return;

            if (layoutDirty || Vector2.DistanceSquared(DrawSize, lastLayoutSize) > 0.25f)
                relayout();

            syncVisibleMeasures();
            foreach (var measure in measures.Values)
                measure.X = XAtTime(measure.Info.StartTime);
            updateHitPulses();
        }

        #region Layout

        private void relayout()
        {
            layoutDirty = false;
            lastLayoutSize = DrawSize;

            float width = DrawWidth;
            float height = DrawHeight;

            bool showLegend = !Compact && legendSymbols.Count > 0;
            float legendHeight = showLegend ? 36f : 0f;
            float unitsAbove = Compact ? 7.8f : 10.4f;
            const float unitsBelow = 6.8f;
            float available = Math.Max(40f, height - legendHeight - 10f);

            space = Math.Clamp(available / (unitsAbove + unitsBelow), 5f, 22f);
            float slack = Math.Max(0f, available - (unitsAbove + unitsBelow) * space);
            middleY = 5f + slack / 2f + unitsAbove * space;

            gutterWidth = 5.4f * space + 10f;
            playheadX = gutterWidth + (width - gutterWidth) * playhead_ratio;

            double beatMs = Math.Max(60.0, tempo.BaseBeatMs);
            double measureMs = beatMs * tempo.BeatsPerMeasureAt(0);
            double measuresAhead = Math.Clamp(2.0 / Math.Sqrt(zoom), 0.75, 4.0);
            double futureWidth = Math.Max(100.0, width - playheadX);
            double minPxPerMs = 2.4 * space / (beatMs / 4.0); // keeps sixteenths at least 2.4 staff spaces apart
            pxPerMs = Math.Max(futureWidth / (measuresAhead * measureMs), minPxPerMs);

            buildStaffLines(width);
            buildGutter(height);
            buildPlayhead(height);

            pastShade.X = gutterWidth;
            pastShade.Width = Math.Max(0, playheadX - gutterWidth);

            legend.Alpha = showLegend ? 1 : 0;
            legend.Padding = new MarginPadding { Left = gutterWidth, Right = 16, Bottom = 8 };
            buildLegend();

            foreach (var measure in measures.Values)
                scrollLayer.Remove(measure, true);
            measures.Clear();
        }

        private void buildStaffLines(float width)
        {
            staffLineLayer.Clear();
            float thickness = Math.Max(1f, space * 0.075f);

            for (int step = DrumNotation.BottomLineStep; step <= DrumNotation.TopLineStep; step += 2)
            {
                staffLineLayer.Add(new Box
                {
                    Width = width,
                    Height = thickness,
                    Origin = Anchor.CentreLeft,
                    Y = YForStep(step),
                    Colour = staffInk
                });
            }
        }

        private void buildGutter(float height)
        {
            gutterLayer.Clear();
            gutterLayer.Width = gutterWidth;

            gutterLayer.Add(new Box { RelativeSizeAxes = Axes.Both, Colour = paper });
            gutterLayer.Add(new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 1,
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Colour = UITheme.Divider
            });

            float thickness = Math.Max(1f, space * 0.075f);
            for (int step = DrumNotation.BottomLineStep; step <= DrumNotation.TopLineStep; step += 2)
            {
                gutterLayer.Add(new Box
                {
                    X = 8f,
                    Width = gutterWidth - 8f,
                    Height = thickness,
                    Origin = Anchor.CentreLeft,
                    Y = YForStep(step),
                    Colour = staffInk
                });
            }

            // Percussion clef: two thick bars over the middle three lines.
            float clefTop = YForStep(2);
            float clefHeight = YForStep(-2) - clefTop;
            for (int i = 0; i < 2; i++)
            {
                gutterLayer.Add(new Box
                {
                    X = 8f + space * 0.9f + i * space * 0.75f,
                    Y = clefTop,
                    Width = space * 0.42f,
                    Height = clefHeight,
                    Colour = ink
                });
            }

            // Time signature (from the start of the map).
            int beats = tempo.BeatsPerMeasureAt(0);
            float numeralSize = space * 2.05f / 1.2f;
            float numeralX = 8f + space * 3.6f;
            gutterLayer.Add(new SpriteText
            {
                Text = beats.ToString(),
                Font = BeatSightFont.Numeral(numeralSize),
                Colour = ink,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.Centre,
                X = numeralX,
                Y = YForStep(2)
            });
            gutterLayer.Add(new SpriteText
            {
                Text = "4",
                Font = BeatSightFont.Numeral(numeralSize),
                Colour = ink,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.Centre,
                X = numeralX,
                Y = YForStep(-2)
            });

            _ = height;
        }

        private void buildPlayhead(float height)
        {
            playheadLayer.Clear();
            float top = Compact ? YForStep(9) : YForStep(19.5f);
            float bottom = YForStep(-12);

            playheadLayer.Add(new Box
            {
                X = playheadX,
                Y = top,
                Width = 2.5f,
                Height = Math.Max(10f, bottom - top),
                Origin = Anchor.TopCentre,
                Colour = UITheme.AccentPrimary,
                Alpha = 0.9f
            });

            playheadLayer.Add(new Triangle
            {
                X = playheadX,
                Y = top,
                Size = new Vector2(12, 9),
                Origin = Anchor.TopCentre,
                Rotation = 180,
                Colour = UITheme.AccentPrimary
            });

            _ = height;
        }

        private void buildLegend()
        {
            legend.Clear();
            if (Compact)
                return;

            foreach (var symbol in legendSymbols)
            {
                legend.Add(new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(7, 0),
                    Children = new Drawable[]
                    {
                        new Container
                        {
                            Size = new Vector2(20, 18),
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            Child = DrumStaffGlyphs.CreateHead(symbol, 11f, ghost: false).With(d =>
                            {
                                d.Anchor = Anchor.Centre;
                                d.Origin = Anchor.Centre;
                            })
                        },
                        new SpriteText
                        {
                            Text = symbol.Name,
                            Font = BeatSightFont.Label(12.5f),
                            Colour = UITheme.TextSecondary,
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft
                        }
                    }
                });
            }

            // Wrapping flows need one anchor for all children; keep the hint text top-aligned like the items.
            legend.Add(new Container
            {
                AutoSizeAxes = Axes.X,
                Height = 18,
                Child = new SpriteText
                {
                    Text = "Stems up: hands     Stems down: feet",
                    Font = BeatSightFont.Caption(11.5f),
                    Colour = UITheme.TextMuted,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft
                }
            });
        }

        #endregion

        #region Measures

        private void syncVisibleMeasures()
        {
            if (pxPerMs <= 0)
                return;

            double startTime = TimeAtX(gutterWidth) - tempo.BaseBeatMs;
            double endTime = TimeAtX(DrawWidth) + tempo.BaseBeatMs;

            var wanted = new HashSet<int>();
            var info = tempo.MeasureAt(startTime);
            for (int guard = 0; guard < 64 && info.StartTime <= endTime; guard++)
            {
                wanted.Add(info.Index);
                if (!measures.ContainsKey(info.Index))
                {
                    var engraved = DrumStaffEngraver.Engrave(info, notes);
                    var drawable = new MeasureDrawable(engraved, this);
                    measures[info.Index] = drawable;
                    scrollLayer.Add(drawable);
                }

                info = tempo.NextMeasure(info);
            }

            foreach (int index in measures.Keys.Where(k => !wanted.Contains(k)).ToArray())
            {
                scrollLayer.Remove(measures[index], true);
                measures.Remove(index);
            }
        }

        private void updateHitPulses()
        {
            foreach (var measure in measures.Values)
            {
                if (measure.Info.EndTime < now - hit_pulse_ms - 50 || measure.Info.StartTime > now + 50)
                {
                    if (measure.PulseActive)
                        measure.ResetPulse();
                    continue;
                }

                measure.UpdatePulse(now, hit_pulse_ms);
            }
        }

        /// <summary>Horizontal distance (px) covered by a time span at the current scale.</summary>
        internal float SpanX(double fromMs, double toMs) => (float)((toMs - fromMs) * pxPerMs);

        internal float Space => space;

        internal ManuscriptCountInGuideMode CountInMode => countInMode;

        private sealed partial class MeasureDrawable : Container
        {
            private readonly List<(double Time, Drawable[] Heads)> pulseTargets = new List<(double, Drawable[])>();

            public DrumStaffMeasureInfo Info { get; }
            public bool PulseActive { get; private set; }

            public MeasureDrawable(EngravedMeasure measure, DrumStaffView view)
            {
                Info = measure.Info;
                RelativeSizeAxes = Axes.Y;
                Width = Math.Max(1f, view.SpanX(measure.Info.StartTime, measure.Info.EndTime));
                Masking = false;
                DrumStaffMeasureRenderer.Render(this, measure, view, pulseTargets);
            }

            public void UpdatePulse(double now, double windowMs)
            {
                PulseActive = true;
                foreach (var (time, heads) in pulseTargets)
                {
                    double since = now - time;
                    float scale = since >= 0 && since <= windowMs
                        ? 1f + 0.45f * (float)(1 - since / windowMs)
                        : 1f;

                    foreach (var head in heads)
                        head.Scale = new Vector2(scale);
                }
            }

            public void ResetPulse()
            {
                PulseActive = false;
                foreach (var (_, heads) in pulseTargets)
                {
                    foreach (var head in heads)
                        head.Scale = Vector2.One;
                }
            }
        }

        #endregion
    }
}
