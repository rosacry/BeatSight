using System;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// A short-lived visual explosion effect spawned when a note crosses the strike zone.
    /// Provides visual feedback that a drum hit has occurred, replacing the abrupt disappearance.
    /// </summary>
    internal sealed partial class HitExplosion : CompositeDrawable
    {
        private const float initial_width = 60f;
        private const float initial_height = 20f;
        private const double expand_duration = 180;
        private const double fade_duration = 240;

        public HitExplosion(Color4 colour, float noteWidth, float noteHeight)
        {
            Origin = Anchor.Centre;
            Anchor = Anchor.TopLeft;
            AutoSizeAxes = Axes.None;
            Size = new Vector2(noteWidth, noteHeight);
            Alpha = 0.9f;

            // Main flash bar
            var flashBar = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = colour,
                Alpha = 0.85f,
            };

            // Bright center highlight
            var highlight = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = Math.Max(4f, noteHeight * 0.35f),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = Color4.White,
                Alpha = 0.7f,
            };

            // Outer glow ring
            var glow = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = colour,
                Alpha = 0.4f,
                Blending = BlendingParameters.Additive,
            };

            InternalChildren = new Drawable[]
            {
                glow,
                flashBar,
                highlight,
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Expand outward
            this.ScaleTo(1.0f)
                .ScaleTo(new Vector2(1.8f, 2.2f), expand_duration, Easing.OutQuint);

            // Flash bright then fade
            this.FadeIn(30)
                .Then()
                .FadeOut(fade_duration, Easing.OutQuint);

            // Expire after animation completes
            this.Delay(fade_duration + 20).Expire();
        }
    }
}
