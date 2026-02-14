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
        public enum RestVoice
        {
            Upper,
            Lower
        }

        private readonly Box body;
        private readonly Box stem;
        private readonly Box quarterStrokeA;
        private readonly Box quarterStrokeB;
        private readonly Box quarterStrokeC;
        private readonly Box quarterStrokeD;
        private readonly Box flagPrimary;
        private readonly Box flagSecondary;
        private readonly Box flagTertiary;
        private readonly Circle hookDotPrimary;
        private readonly Circle hookDotSecondary;
        private readonly Circle hookDotTertiary;
        private int glyphLevel;
        private RestVoice voice;

        public DrawableManuscriptRest()
        {
            Size = new Vector2(22, 30);
            RelativePositionAxes = Axes.None;

            body = new Box
            {
                Width = 7f,
                Height = 3.2f,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = Color4.White
            };

            stem = new Box
            {
                Width = 1.6f,
                Height = 14f,
                Anchor = Anchor.Centre,
                Origin = Anchor.BottomCentre,
                Y = 2f,
                Colour = Color4.White
            };

            quarterStrokeA = createQuarterStroke();
            quarterStrokeB = createQuarterStroke();
            quarterStrokeC = createQuarterStroke();
            quarterStrokeD = createQuarterStroke();

            flagPrimary = createFlag();
            flagSecondary = createFlag();
            flagTertiary = createFlag();
            hookDotPrimary = createHookDot();
            hookDotSecondary = createHookDot();
            hookDotTertiary = createHookDot();

            InternalChildren = new Drawable[]
            {
                body,
                stem,
                quarterStrokeA,
                quarterStrokeB,
                quarterStrokeC,
                quarterStrokeD,
                flagPrimary,
                flagSecondary,
                flagTertiary,
                hookDotPrimary,
                hookDotSecondary,
                hookDotTertiary
            };

            SetVoice(RestVoice.Upper);
            SetGlyphLevel(0);
        }

        public void SetGlyphLevel(int level)
        {
            glyphLevel = Math.Clamp(level, 0, 3);
            updateGeometry();
        }

        public void SetVoice(RestVoice restVoice)
        {
            voice = restVoice;
            updateGeometry();
        }

        private static Box createQuarterStroke()
        {
            return new Box
            {
                Width = 8f,
                Height = 2f,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = Color4.White,
                Alpha = 0f
            };
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

        private static Circle createHookDot()
        {
            return new Circle
            {
                Size = new Vector2(2.8f),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = Color4.White,
                Alpha = 0f
            };
        }

        private void updateGeometry()
        {
            updateQuarterGlyph(glyphLevel == 0);
            updateHookedGlyph(glyphLevel);
        }

        private void updateQuarterGlyph(bool visible)
        {
            if (!visible)
            {
                quarterStrokeA.Alpha = 0f;
                quarterStrokeB.Alpha = 0f;
                quarterStrokeC.Alpha = 0f;
                quarterStrokeD.Alpha = 0f;
                return;
            }

            float voiceBias = voice == RestVoice.Lower ? 0.5f : -0.3f;
            configureQuarterStroke(quarterStrokeA, x: -1.8f, y: -8.6f + voiceBias, width: 8.4f, rotation: 62f);
            configureQuarterStroke(quarterStrokeB, x: 0.4f, y: -4.2f + voiceBias, width: 10.0f, rotation: -48f);
            configureQuarterStroke(quarterStrokeC, x: -0.2f, y: 0.3f + voiceBias, width: 8.8f, rotation: 66f);
            configureQuarterStroke(quarterStrokeD, x: 2.1f, y: 4.8f + voiceBias, width: 6.4f, rotation: -18f);
        }

        private void updateHookedGlyph(int level)
        {
            bool visible = level > 0;
            stem.Alpha = visible ? 0.92f : 0f;
            body.Alpha = visible ? 0.88f : 0f;

            if (!visible)
            {
                flagPrimary.Alpha = 0f;
                flagSecondary.Alpha = 0f;
                flagTertiary.Alpha = 0f;
                hookDotPrimary.Alpha = 0f;
                hookDotSecondary.Alpha = 0f;
                hookDotTertiary.Alpha = 0f;
                return;
            }

            float direction = voice == RestVoice.Lower ? -1f : 1f;
            float stemX = voice == RestVoice.Lower ? -1.6f : 0.8f;
            stem.X = stemX;
            stem.Y = 2f + (voice == RestVoice.Lower ? 1.0f : 0f);
            stem.Origin = voice == RestVoice.Lower ? Anchor.TopCentre : Anchor.BottomCentre;

            body.Width = 5.4f;
            body.Height = 2.2f;
            body.X = stemX + (voice == RestVoice.Lower ? -0.8f : 0.7f);
            body.Y = voice == RestVoice.Lower ? 10.2f : -10.2f;

            updateFlag(flagPrimary, hookDotPrimary, level >= 1, direction, stemX, -8.9f, 8.8f);
            updateFlag(flagSecondary, hookDotSecondary, level >= 2, direction, stemX, -4.8f, 8.3f);
            updateFlag(flagTertiary, hookDotTertiary, level >= 3, direction, stemX, -1.0f, 7.8f);
        }

        private static void configureQuarterStroke(Box stroke, float x, float y, float width, float rotation)
        {
            stroke.X = x;
            stroke.Y = y;
            stroke.Width = width;
            stroke.Rotation = rotation;
            stroke.Alpha = 0.92f;
        }

        private static void updateFlag(Box flag, Circle dot, bool visible, float direction, float stemX, float y, float width)
        {
            if (!visible)
            {
                flag.Alpha = 0f;
                dot.Alpha = 0f;
                return;
            }

            float x = stemX + direction * 0.9f;
            flag.X = x;
            flag.Y = y;
            flag.Width = width;
            flag.Rotation = direction * 28f;
            flag.Alpha = 0.9f;

            dot.X = x + direction * (width * 0.42f);
            dot.Y = y - direction * 1.1f;
            dot.Alpha = 0.84f;
        }
    }
}
