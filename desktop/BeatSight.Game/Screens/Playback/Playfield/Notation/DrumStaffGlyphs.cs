using System;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Notation
{
    /// <summary>
    /// Notation glyphs drawn from primitives (the app ships no music font). Sizes are in staff spaces
    /// (<c>space</c> = distance between two staff lines).
    /// </summary>
    internal static class DrumStaffGlyphs
    {
        public static float HeadWidth(float space) => space * 1.3f;
        public static float HeadHeight(float space) => space * 0.96f;

        /// <summary>A notehead centred on its origin.</summary>
        public static Drawable CreateHead(DrumNotationSymbol symbol, float space, bool ghost)
        {
            Color4 colour = symbol.Colour;
            var head = new Container
            {
                Size = new Vector2(HeadWidth(space), HeadHeight(space)),
                Origin = Anchor.Centre,
                Alpha = ghost ? 0.62f : 1f,
            };

            switch (symbol.Head)
            {
                case DrumNotehead.Cross:
                    addCross(head, space * 1.12f, Math.Max(1.6f, space * 0.2f), colour);
                    break;

                case DrumNotehead.CircledCross:
                    head.Add(ring(space * 1.18f, Math.Max(1.2f, space * 0.13f), colour));
                    addCross(head, space * 0.82f, Math.Max(1.3f, space * 0.15f), colour);
                    break;

                case DrumNotehead.Diamond:
                    head.Add(new Box
                    {
                        Size = new Vector2(space * 0.74f),
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Rotation = 45,
                        Colour = colour
                    });
                    break;

                case DrumNotehead.Triangle:
                    head.Add(new Triangle
                    {
                        Size = new Vector2(space * 1.05f, space * 0.92f),
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Colour = colour
                    });
                    break;

                default:
                    // Oval notehead: a pill tilted like an engraved head.
                    head.Add(new Container
                    {
                        Size = new Vector2(space * 1.22f, space * 0.84f),
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Rotation = -20,
                        Masking = true,
                        CornerRadius = space * 0.42f,
                        Child = new Box { RelativeSizeAxes = Axes.Both, Colour = colour }
                    });
                    break;
            }

            if (ghost)
                head.Scale = new Vector2(0.78f);

            return head;
        }

        /// <summary>A straight stroke from (x1, y1) to (x2, y2).</summary>
        public static Drawable Line(float x1, float y1, float x2, float y2, float thickness, Color4 colour)
        {
            float dx = x2 - x1;
            float dy = y2 - y1;
            return new Box
            {
                Origin = Anchor.CentreLeft,
                Position = new Vector2(x1, y1),
                Width = MathF.Sqrt(dx * dx + dy * dy),
                Height = thickness,
                Rotation = MathF.Atan2(dy, dx) * 180f / MathF.PI,
                Colour = colour,
                EdgeSmoothness = new Vector2(1f)
            };
        }

        /// <summary>A hollow circle (open hi-hat mark, cross-stick ring).</summary>
        public static Drawable Ring(float diameter, float thickness, Color4 colour) => ring(diameter, thickness, colour);

        /// <summary>
        /// Adds a rest glyph centred at (cx, cy). Level 0 = quarter, 1 = eighth, 2 = sixteenth, -1 = whole-measure.
        /// </summary>
        public static void AddRest(Container target, int level, float cx, float cy, float space, Color4 colour)
        {
            float s = space;
            void line(float ax, float ay, float bx, float by, float t) => target.Add(Line(cx + ax * s, cy + ay * s, cx + bx * s, cy + by * s, Math.Max(1.2f, t * s), colour));
            void dot(float ax, float ay, float d) => target.Add(new Circle
            {
                Size = new Vector2(d * s),
                Origin = Anchor.Centre,
                Position = new Vector2(cx + ax * s, cy + ay * s),
                Colour = colour
            });

            switch (level)
            {
                case -1:
                    // Whole-measure rest: a block hanging from the fourth line (cy is that line).
                    target.Add(new Box
                    {
                        Size = new Vector2(1.3f * s, 0.5f * s),
                        Origin = Anchor.TopCentre,
                        Position = new Vector2(cx, cy),
                        Colour = colour
                    });
                    break;

                case 0:
                    line(0.10f, -1.45f, 0.52f, -0.72f, 0.22f);
                    line(0.52f, -0.72f, -0.02f, -0.02f, 0.42f);
                    line(-0.02f, -0.02f, 0.48f, 0.72f, 0.22f);
                    line(0.48f, 0.72f, -0.05f, 1.02f, 0.30f);
                    line(-0.05f, 1.02f, 0.22f, 1.48f, 0.22f);
                    break;

                case 1:
                    dot(-0.18f, -0.52f, 0.46f);
                    line(-0.05f, -0.40f, 0.46f, -0.62f, 0.16f);
                    line(0.46f, -0.62f, 0.02f, 0.95f, 0.18f);
                    break;

                default:
                    dot(-0.05f, -0.55f, 0.44f);
                    dot(-0.30f, 0.30f, 0.44f);
                    line(0.08f, -0.44f, 0.58f, -0.64f, 0.16f);
                    line(-0.17f, 0.42f, 0.33f, 0.20f, 0.16f);
                    line(0.58f, -0.64f, -0.02f, 1.62f, 0.18f);
                    break;
            }
        }

        private static void addCross(Container head, float length, float thickness, Color4 colour)
        {
            float half = length / 2f / MathF.Sqrt(2f);
            float cx = head.Width / 2f;
            float cy = head.Height / 2f;
            head.Add(Line(cx - half, cy - half, cx + half, cy + half, thickness, colour));
            head.Add(Line(cx - half, cy + half, cx + half, cy - half, thickness, colour));
        }

        private static Drawable ring(float diameter, float thickness, Color4 colour) => new CircularContainer
        {
            Size = new Vector2(diameter),
            Anchor = Anchor.Centre,
            Origin = Anchor.Centre,
            Masking = true,
            BorderThickness = thickness,
            BorderColour = colour,
            Child = new Box { RelativeSizeAxes = Axes.Both, Alpha = 0, AlwaysPresent = true }
        };
    }
}
