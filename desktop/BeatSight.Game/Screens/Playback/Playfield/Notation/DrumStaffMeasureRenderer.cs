using System;
using System.Collections.Generic;
using System.Linq;
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
    /// <summary>Draws one engraved measure into a container in the staff view's scrolling content space.</summary>
    internal static class DrumStaffMeasureRenderer
    {
        private static readonly Color4 ink = new Color4(222, 228, 240, 240);
        private static readonly Color4 barInk = new Color4(176, 188, 210, 220);
        private static readonly Color4 ledgerInk = new Color4(150, 162, 186, 220);
        private static readonly Color4 restInk = new Color4(200, 208, 224, 220);

        /// <summary>Stems reach three and a half spaces beyond the outermost head.</summary>
        private const float stem_length_spaces = 3.5f;

        public static void Render(Container target, EngravedMeasure measure, DrumStaffView view, List<(double Time, Drawable[] Heads)> pulseTargets)
        {
            float s = view.Space;
            float headW = DrumStaffGlyphs.HeadWidth(s);
            float stemW = Math.Max(1.2f, s * 0.12f);
            float beamThickness = Math.Max(2f, s * 0.4f);
            float beamGap = Math.Max(1.5f, s * 0.3f);

            // Positions are local to the measure container, whose left edge is the measure start.
            double origin = measure.Info.StartTime;
            float y(float step) => view.YForStep(step);
            float x(double time) => view.SpanX(origin, time);

            drawBarAndRuler(target, measure, view, s);

            // Stem geometry per chord, needed for beams, flags and marks.
            var stems = new Dictionary<EngravedChord, (float StemX, float HeadEnd, float Tip)>();

            foreach (var chord in measure.Chords)
            {
                bool up = chord.Voice == DrumVoice.Hands;
                float cx = x(chord.Time);
                var heads = new List<Drawable>();

                // Seconds (adjacent staff positions) put the second head on the other side of the stem.
                int? previousStep = null;
                bool previousDisplaced = false;
                var ordered = up ? chord.Notes.OrderBy(n => n.Symbol.StaffStep) : chord.Notes.OrderByDescending(n => n.Symbol.StaffStep);

                foreach (var note in ordered)
                {
                    int step = note.Symbol.StaffStep;
                    bool displaced = previousStep.HasValue && Math.Abs(step - previousStep.Value) == 1 && !previousDisplaced;
                    float headX = cx + (displaced ? (up ? headW : -headW) * 0.92f : 0f);

                    drawLedgers(target, step, headX, s, y);

                    var head = DrumStaffGlyphs.CreateHead(note.Symbol, s, note.Ghost);
                    head.Position = new Vector2(headX, y(step));
                    if (view.FocusName != null && view.FocusName != note.Symbol.Name)
                        head.Alpha *= 0.35f;
                    target.Add(head);
                    heads.Add(head);

                    if (note.Ghost)
                        drawGhostParentheses(target, headX, y(step), s);

                    previousStep = step;
                    previousDisplaced = displaced;
                }

                pulseTargets.Add((chord.Time, heads.ToArray()));

                float stemX = up ? cx + headW / 2f - stemW / 2f : cx - headW / 2f + stemW / 2f;
                float headEnd = up ? y(chord.LowestStep) - s * 0.15f : y(chord.HighestStep) + s * 0.15f;
                float tip = up ? y(chord.HighestStep) - stem_length_spaces * s : y(chord.LowestStep) + stem_length_spaces * s;
                stems[chord] = (stemX, headEnd, tip);

                if (chord.Dotted)
                {
                    int dotStep = up ? chord.HighestStep : chord.LowestStep;
                    if (dotStep % 2 == 0)
                        dotStep += 1; // dots sit in spaces
                    target.Add(new Circle
                    {
                        Size = new Vector2(s * 0.36f),
                        Origin = Anchor.Centre,
                        Position = new Vector2(cx + headW * 0.5f + s * 0.55f, y(dotStep)),
                        Colour = ink
                    });
                }
            }

            // Beam groups align their stems to one flat beam.
            foreach (var group in measure.Chords.Where(c => c.IsBeamed).GroupBy(c => (c.Voice, c.BeamGroup)))
            {
                var chords = group.OrderBy(c => c.Time).ToArray();
                bool up = group.Key.Voice == DrumVoice.Hands;
                float beamY = up ? chords.Min(c => stems[c].Tip) : chords.Max(c => stems[c].Tip);

                foreach (var chord in chords)
                {
                    var stem = stems[chord];
                    stems[chord] = (stem.StemX, stem.HeadEnd, beamY);
                }

                drawBeams(target, chords, stems, up, beamY, beamThickness, beamGap, s);

                var tuplet = measure.Tuplets.FirstOrDefault(t => t.Voice == group.Key.Voice && t.BeamGroup == group.Key.BeamGroup);
                if (tuplet != null)
                {
                    float midX = (stems[chords[0]].StemX + stems[chords[^1]].StemX) / 2f;
                    target.Add(new SpriteText
                    {
                        Text = tuplet.Number.ToString(),
                        Font = BeatSightFont.Label(Math.Max(9f, s * 0.95f)),
                        Colour = ink,
                        Origin = Anchor.Centre,
                        Position = new Vector2(midX, up ? beamY - s * 1.05f : beamY + s * 1.05f)
                    });
                }
            }

            foreach (var chord in measure.Chords)
            {
                bool up = chord.Voice == DrumVoice.Hands;
                var (stemX, headEnd, tip) = stems[chord];

                target.Add(new Box
                {
                    Width = stemW,
                    Height = Math.Abs(headEnd - tip),
                    Origin = Anchor.TopCentre,
                    Position = new Vector2(stemX, Math.Min(headEnd, tip)),
                    Colour = ink
                });

                if (!chord.IsBeamed && chord.BeamLevels > 0)
                    drawFlags(target, chord.BeamLevels, stemX, tip, up, s);

                if (chord.Notes.Any(n => n.Symbol.OpenMark))
                {
                    var ring = DrumStaffGlyphs.Ring(s * 0.72f, Math.Max(1.2f, s * 0.13f), ink);
                    ring.Anchor = Anchor.TopLeft;
                    ring.Origin = Anchor.Centre;
                    // Just beyond the stem tip/beam, clear of the beat ruler above.
                    float markY = up ? tip - s * 0.62f : y(chord.HighestStep) - s * 1.4f;
                    ring.Position = new Vector2(x(chord.Time), markY);
                    target.Add(ring);
                }
            }

            foreach (var rest in measure.Rests)
            {
                if (rest.Level < 0)
                {
                    DrumStaffGlyphs.AddRest(target, -1, x(rest.Time), y(2), s, restInk);
                    continue;
                }

                float restX = x(rest.Time) + s * 0.6f;
                DrumStaffGlyphs.AddRest(target, rest.Level, restX, y(rest.Voice == DrumVoice.Hands ? 1 : -3), s, restInk);
            }
        }

        private static void drawBarAndRuler(Container target, EngravedMeasure measure, DrumStaffView view, float s)
        {
            double origin = measure.Info.StartTime;
            // Time-linear layout puts the downbeat's notes at x = 0; the bar line sits in the gap just before them.
            float barX = -s * 1.15f;
            float top = view.YForStep(DrumNotation.TopLineStep);
            float bottom = view.YForStep(DrumNotation.BottomLineStep);

            target.Add(new Box
            {
                Width = Math.Max(1.2f, s * 0.1f),
                Height = bottom - top,
                Origin = Anchor.TopCentre,
                Position = new Vector2(barX, top),
                Colour = barInk
            });

            if (view.Compact)
                return;

            float measureLabelY = view.YForStep(19.6f);
            float beatLabelY = view.YForStep(17.2f);
            float tickTop = view.YForStep(16.0f);

            target.Add(new SpriteText
            {
                Text = (measure.Info.Index + 1).ToString(),
                Font = BeatSightFont.Label(Math.Max(10f, s * 0.66f)),
                Colour = UITheme.TextSecondary,
                Origin = Anchor.CentreLeft,
                Position = new Vector2(3f, measureLabelY)
            });

            var mode = view.CountInMode;
            for (int beat = 0; beat < measure.BeatTimes.Count; beat++)
            {
                float beatX = view.SpanX(origin, measure.BeatTimes[beat]);
                target.Add(new Box
                {
                    Width = 1.2f,
                    Height = s * (beat == 0 ? 0.9f : 0.6f),
                    Origin = Anchor.TopCentre,
                    Position = new Vector2(beatX, tickTop),
                    Colour = beat == 0 ? barInk : UITheme.TextMuted
                });

                if (mode == ManuscriptCountInGuideMode.Off)
                    continue;

                target.Add(new SpriteText
                {
                    Text = (beat + 1).ToString(),
                    Font = BeatSightFont.Label(Math.Max(10f, s * 0.6f)),
                    Colour = UITheme.TextSecondary,
                    Origin = Anchor.Centre,
                    Position = new Vector2(beatX, beatLabelY)
                });

                if (mode == ManuscriptCountInGuideMode.Full)
                {
                    float andX = view.SpanX(origin, measure.BeatTimes[beat] + measure.Info.BeatMs / 2);
                    target.Add(new SpriteText
                    {
                        Text = "&",
                        Font = BeatSightFont.Caption(Math.Max(9f, s * 0.5f)),
                        Colour = UITheme.TextMuted,
                        Origin = Anchor.Centre,
                        Position = new Vector2(andX, beatLabelY)
                    });
                }
            }
        }

        private static void drawLedgers(Container target, int step, float headX, float s, Func<float, float> y)
        {
            float width = s * 2.0f;
            float thickness = Math.Max(1f, s * 0.08f);

            for (int ledger = DrumNotation.TopLineStep + 2; ledger <= step; ledger += 2)
                target.Add(ledgerLine(headX, y(ledger), width, thickness));

            for (int ledger = DrumNotation.BottomLineStep - 2; ledger >= step; ledger -= 2)
                target.Add(ledgerLine(headX, y(ledger), width, thickness));
        }

        private static Drawable ledgerLine(float x, float y, float width, float thickness) => new Box
        {
            Width = width,
            Height = thickness,
            Origin = Anchor.Centre,
            Position = new Vector2(x, y),
            Colour = ledgerInk
        };

        private static void drawGhostParentheses(Container target, float headX, float headY, float s)
        {
            foreach (var (text, dx) in new[] { ("(", -0.95f), (")", 0.95f) })
            {
                target.Add(new SpriteText
                {
                    Text = text,
                    Font = BeatSightFont.Body(Math.Max(8f, s * 1.05f)),
                    Colour = ink,
                    Alpha = 0.7f,
                    Origin = Anchor.Centre,
                    Position = new Vector2(headX + dx * s, headY)
                });
            }
        }

        private static void drawBeams(
            Container target,
            EngravedChord[] chords,
            Dictionary<EngravedChord, (float StemX, float HeadEnd, float Tip)> stems,
            bool up,
            float beamY,
            float thickness,
            float gap,
            float s)
        {
            int maxLevel = chords.Max(c => c.BeamLevels);
            float direction = up ? 1f : -1f; // secondary beams sit towards the heads

            for (int level = 1; level <= maxLevel; level++)
            {
                float levelY = beamY + direction * (level - 1) * (thickness + gap);
                float top = up ? levelY : levelY - thickness;

                if (level == 1)
                {
                    addBeam(target, stems[chords[0]].StemX, stems[chords[^1]].StemX, top, thickness);
                    continue;
                }

                for (int i = 0; i < chords.Length; i++)
                {
                    if (chords[i].BeamLevels < level)
                        continue;

                    bool nextHas = i + 1 < chords.Length && chords[i + 1].BeamLevels >= level;
                    bool previousHas = i > 0 && chords[i - 1].BeamLevels >= level;

                    if (nextHas)
                    {
                        addBeam(target, stems[chords[i]].StemX, stems[chords[i + 1]].StemX, top, thickness);
                    }
                    else if (!previousHas)
                    {
                        // Partial beam (e.g. the sixteenth of a dotted-eighth pair) points into the group.
                        float stub = Math.Min(s * 1.1f, Math.Abs(stems[chords[Math.Max(0, i == chords.Length - 1 ? i - 1 : i + 1)]].StemX - stems[chords[i]].StemX) * 0.5f);
                        float from = stems[chords[i]].StemX;
                        float to = i == chords.Length - 1 ? from - stub : from + stub;
                        addBeam(target, Math.Min(from, to), Math.Max(from, to), top, thickness);
                    }
                }
            }
        }

        private static void addBeam(Container target, float x1, float x2, float top, float thickness)
        {
            target.Add(new Box
            {
                Width = Math.Max(1f, x2 - x1 + 1f),
                Height = thickness,
                Position = new Vector2(x1 - 0.5f, top),
                Colour = ink
            });
        }

        private static void drawFlags(Container target, int levels, float stemX, float tip, bool up, float s)
        {
            // Hooked flag: out and away from the stem, then curling back towards the notehead.
            float thickness = Math.Max(1.4f, s * 0.28f);
            float sign = up ? 1f : -1f;
            for (int i = 0; i < levels; i++)
            {
                float startY = tip + sign * i * s * 0.8f;
                float bendX = stemX + s * 0.95f;
                float bendY = startY + sign * s * 1.0f;
                target.Add(DrumStaffGlyphs.Line(stemX, startY, bendX, bendY, thickness, ink));
                target.Add(DrumStaffGlyphs.Line(bendX, bendY, stemX + s * 0.8f, startY + sign * s * 1.9f, thickness * 0.8f, ink));
            }
        }
    }
}
