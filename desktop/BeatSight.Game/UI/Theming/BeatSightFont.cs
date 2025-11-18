using System;
using osu.Framework.Graphics.Sprites;

namespace BeatSight.Game.UI.Theming
{
    /// <summary>
    /// Centralised font helpers inspired by osu!'s typography scale.
    /// </summary>
    public static class BeatSightFont
    {
        public const string PrimaryFamily = "Exo 2";
        public const string SecondaryFamily = "Nunito";
        private const float scaleMultiplier = 1.2f;
        private const float pixel_snap = 0.25f;

        public static FontUsage Title(float size = 72f) => createPrimary(size, "Bold");
        public static FontUsage Subtitle(float size = 40f) => createPrimary(size, "SemiBold");
        public static FontUsage Section(float size = 32f) => createPrimary(size, "SemiBold");
        public static FontUsage Body(float size = 24f) => createSecondary(size, "SemiBold");
        public static FontUsage Caption(float size = 20f) => createSecondary(size, "Regular");
        public static FontUsage Numeral(float size = 28f) => createPrimary(size, "Bold");
        public static FontUsage Button(float size = 26f) => createPrimary(size, "Bold");
        public static FontUsage Label(float size = 22f) => createSecondary(size, "SemiBold");

        private static FontUsage createPrimary(float size, string weight) => create(size, weight, useSecondary: false);
        private static FontUsage createSecondary(float size, string weight) => create(size, weight, useSecondary: true);

        private static FontUsage create(float size, string weight, bool useSecondary)
        {
            float scaledSize = size * scaleMultiplier;
            return new FontUsage(useSecondary ? SecondaryFamily : PrimaryFamily, size: snapSize(scaledSize), weight: weight);
        }

        private static float snapSize(float size)
        {
            if (size <= 0)
                return pixel_snap;

            return MathF.Round(size / pixel_snap) * pixel_snap;
        }
    }
}
