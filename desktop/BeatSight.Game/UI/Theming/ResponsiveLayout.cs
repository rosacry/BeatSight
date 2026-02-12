using System;
using osu.Framework.Graphics;
using osuTK;

namespace BeatSight.Game.UI.Theming
{
    /// <summary>
    /// Central helper for converting design-time fixed values into viewport-adaptive values.
    /// </summary>
    public static class ResponsiveLayout
    {
        private const float designWidth = 1920f;
        private const float designHeight = 1080f;

        public static float ScaleByWidth(float value, float viewportWidth, float minScale = 0.75f, float maxScale = 1.35f)
            => value * resolveScale(viewportWidth, designWidth, minScale, maxScale);

        public static float ScaleByHeight(float value, float viewportHeight, float minScale = 0.75f, float maxScale = 1.35f)
            => value * resolveScale(viewportHeight, designHeight, minScale, maxScale);

        public static float ScaleByShortSide(float value, Vector2 viewport, float minScale = 0.75f, float maxScale = 1.35f)
        {
            float shortSide = Math.Min(viewport.X, viewport.Y);
            return ScaleByHeight(value, shortSide, minScale, maxScale);
        }

        public static float ClampFraction(float viewport, float fraction, float minValue, float maxValue)
        {
            if (viewport <= 0)
                return minValue;

            return Math.Clamp(viewport * fraction, minValue, maxValue);
        }

        public static MarginPadding ScalePadding(MarginPadding padding, float scale)
        {
            scale = Math.Clamp(scale, 0.5f, 2.0f);
            return new MarginPadding
            {
                Left = padding.Left * scale,
                Right = padding.Right * scale,
                Top = padding.Top * scale,
                Bottom = padding.Bottom * scale
            };
        }

        /// <summary>
        /// Resolves a responsive viewport in screen-space pixels, falling back to local draw size.
        /// This avoids double-scaling when the global UI container is transformed.
        /// </summary>
        public static Vector2 ResolveViewport(Drawable drawable, float fallbackWidth = designWidth, float fallbackHeight = designHeight)
        {
            if (drawable != null)
            {
                var quad = drawable.ScreenSpaceDrawQuad;
                float screenWidth = (quad.TopRight - quad.TopLeft).Length;
                float screenHeight = (quad.BottomLeft - quad.TopLeft).Length;

                if (screenWidth > 1f && screenHeight > 1f)
                    return new Vector2(screenWidth, screenHeight);

                if (drawable.DrawWidth > 1f && drawable.DrawHeight > 1f)
                    return new Vector2(drawable.DrawWidth, drawable.DrawHeight);
            }

            return new Vector2(fallbackWidth, fallbackHeight);
        }

        private static float resolveScale(float viewportAxis, float baseline, float minScale, float maxScale)
        {
            if (viewportAxis <= 0 || baseline <= 0)
                return 1f;

            float ratio = viewportAxis / baseline;
            return Math.Clamp(ratio, minScale, maxScale);
        }
    }
}
