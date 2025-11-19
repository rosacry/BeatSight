using System;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    internal sealed partial class KickPulse : CompositeDrawable
    {
        private readonly Container body;
        private readonly Box fill;
        private readonly Box highlight;
        private readonly Box glow;

        public DrawableNote? Note { get; set; }

        public KickPulse()
        {
            RelativeSizeAxes = Axes.X;
            Width = 0.96f;
            Height = 26;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.Centre;
            RelativePositionAxes = Axes.Y;

            glow = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = UITheme.KickGlobalGlow,
                Alpha = 0,
                Blending = BlendingParameters.Additive
            };

            body = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 12
            };

            fill = new Box { RelativeSizeAxes = Axes.Both };
            body.Add(fill);

            highlight = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 4,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Alpha = 0.5f
            };
            body.Add(highlight);

            InternalChildren = new Drawable[]
            {
                    glow,
                    body
            };
        }

        public void ResetState()
        {
            ClearTransforms();
            Alpha = 0;
            Scale = Vector2.One;
            Y = 0;
        }

        public void UpdateVisual(double timeUntil, double previewRange, double pastRange, double window, bool emphasise)
        {
            double clamped = Math.Clamp(timeUntil, -pastRange, previewRange);
            float progress = (float)((previewRange - clamped) / Math.Max(1, window));
            float travel = 0.88f;
            Y = -Math.Clamp(progress, 0f, 1f) * travel;

            float closeness = 1f - (float)Math.Clamp(Math.Abs(timeUntil) / Math.Max(1, previewRange * 0.55 + pastRange), 0, 1);
            float scaleBase = emphasise ? 0.65f : 0.5f;
            float widthScale = 0.95f + closeness * 0.08f;
            float heightScale = 0.55f + closeness * (0.45f + scaleBase * 0.18f);
            Scale = new Vector2(widthScale, heightScale);

            float targetAlpha = Math.Clamp(0.25f + progress * (emphasise ? 0.55f : 0.4f), 0f, 1f);
            Alpha = targetAlpha;

            var accent = Note?.AccentColour ?? new Color4(186, 145, 255, 255);
            var baseColour = adjust(accent, emphasise ? 1.2 : 1.08);
            fill.Colour = ColourInfo.GradientHorizontal(adjust(baseColour, 1.24), adjust(baseColour, 0.76));
            highlight.Colour = adjust(baseColour, emphasise ? 1.34 : 1.18);
            glow.Colour = adjust(accent, emphasise ? 1.65 : 1.4);
            glow.Alpha = 0.2f + closeness * (emphasise ? 0.36f : 0.26f);
        }

        private static Color4 adjust(Color4 colour, double factor)
        {
            return new Color4(
                (float)Math.Clamp(colour.R * factor, 0f, 1f),
                (float)Math.Clamp(colour.G * factor, 0f, 1f),
                (float)Math.Clamp(colour.B * factor, 0f, 1f),
                colour.A);
        }
    }
}
