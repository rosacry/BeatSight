using System;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// Lightweight manuscript rest glyph used by the live manuscript timeline overlay.
    /// Glyph level:
    /// 0 = quarter/beat rest
    /// 1 = eighth rest
    /// 2 = sixteenth rest
    /// 3 = thirty-second rest
    /// </summary>
    public partial class DrawableManuscriptRest : CompositeDrawable
    {
        private readonly Box body;
        private readonly Box stem;
        private readonly Box flagPrimary;
        private readonly Box flagSecondary;
        private readonly Box flagTertiary;
        private int glyphLevel;

        public DrawableManuscriptRest()
        {
            Size = new Vector2(20, 26);
            RelativePositionAxes = Axes.None;

            body = new Box
            {
                Width = 7f,
                Height = 3f,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = Color4.White
            };

            stem = new Box
            {
                Width = 1.6f,
                Height = 13f,
                Anchor = Anchor.Centre,
                Origin = Anchor.BottomCentre,
                Y = 1f,
                Colour = Color4.White
            };

            flagPrimary = createFlag();
            flagSecondary = createFlag();
            flagTertiary = createFlag();

            InternalChildren = new Drawable[]
            {
                body,
                stem,
                flagPrimary,
                flagSecondary,
                flagTertiary
            };

            SetGlyphLevel(0);
        }

        public void SetGlyphLevel(int level)
        {
            glyphLevel = Math.Clamp(level, 0, 3);
            updateGeometry();
        }

        private static Box createFlag()
        {
            return new Box
            {
                Width = 8f,
                Height = 1.8f,
                Anchor = Anchor.Centre,
                Origin = Anchor.CentreLeft,
                Rotation = 24f,
                Colour = Color4.White,
                Alpha = 0f
            };
        }

        private void updateGeometry()
        {
            bool hasFlags = glyphLevel > 0;
            stem.Alpha = hasFlags ? 0.92f : 0f;
            body.Width = hasFlags ? 6f : 8f;
            body.Height = hasFlags ? 2.4f : 3.2f;
            body.Y = hasFlags ? 2f : 0f;
            body.Alpha = 0.92f;

            updateFlag(flagPrimary, glyphLevel >= 1, x: 0.6f, y: -11.4f, width: 8.6f);
            updateFlag(flagSecondary, glyphLevel >= 2, x: 0.6f, y: -7.6f, width: 8.1f);
            updateFlag(flagTertiary, glyphLevel >= 3, x: 0.6f, y: -4.1f, width: 7.6f);
        }

        private static void updateFlag(Box flag, bool visible, float x, float y, float width)
        {
            if (!visible)
            {
                flag.Alpha = 0f;
                return;
            }

            flag.X = x;
            flag.Y = y;
            flag.Width = width;
            flag.Alpha = 0.9f;
        }
    }
}
