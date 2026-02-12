using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;

namespace BeatSight.Tests.VisualRegression
{
    internal readonly record struct VisualDiffResult(
        bool IsMatch,
        int ChangedPixels,
        int TotalPixels,
        double ChangedPixelRatio,
        double MeanDelta,
        string? ErrorMessage = null);

    internal static class VisualDiffComparer
    {
        internal const double DefaultMaxChangedPixelRatio = 0.005;
        internal const double DefaultMaxMeanDelta = 0.001;
        private const int perChannelNoiseFloor = 3;
        private const int changedPixelThreshold = 8;

        internal static VisualDiffResult Compare(
            Image<Rgba32> expected,
            Image<Rgba32> actual,
            out Image<Rgba32> diffImage)
        {
            if (expected.Width != actual.Width || expected.Height != actual.Height)
            {
                diffImage = createDimensionMismatchDiff(expected, actual);
                return new VisualDiffResult(
                    IsMatch: false,
                    ChangedPixels: 0,
                    TotalPixels: Math.Max(1, actual.Width * actual.Height),
                    ChangedPixelRatio: 1,
                    MeanDelta: 1,
                    ErrorMessage: $"Image dimension mismatch. Expected {expected.Width}x{expected.Height}, actual {actual.Width}x{actual.Height}.");
            }

            int width = expected.Width;
            int height = expected.Height;
            int total = width * height;
            int changed = 0;
            double deltaAccumulator = 0;

            diffImage = new Image<Rgba32>(width, height);

            for (int y = 0; y < height; y++)
            {
                for (int x = 0; x < width; x++)
                {
                    Rgba32 e = expected[x, y];
                    Rgba32 a = actual[x, y];

                    int dr = Math.Max(0, Math.Abs(e.R - a.R) - perChannelNoiseFloor);
                    int dg = Math.Max(0, Math.Abs(e.G - a.G) - perChannelNoiseFloor);
                    int db = Math.Max(0, Math.Abs(e.B - a.B) - perChannelNoiseFloor);
                    int da = Math.Max(0, Math.Abs(e.A - a.A) - perChannelNoiseFloor);

                    int sum = dr + dg + db + da;
                    if (sum > changedPixelThreshold)
                        changed++;

                    double normalized = sum / (4.0 * 255.0);
                    deltaAccumulator += normalized;

                    if (sum == 0)
                        diffImage[x, y] = new Rgba32(0, 0, 0, 255);
                    else
                    {
                        byte heat = (byte)Math.Clamp((int)Math.Round(normalized * 255.0), 0, 255);
                        diffImage[x, y] = new Rgba32(heat, (byte)(heat / 6), (byte)(heat / 8), 255);
                    }
                }
            }

            double changedRatio = changed / (double)Math.Max(1, total);
            double meanDelta = deltaAccumulator / Math.Max(1, total);
            bool isMatch = changedRatio <= DefaultMaxChangedPixelRatio && meanDelta <= DefaultMaxMeanDelta;

            return new VisualDiffResult(
                IsMatch: isMatch,
                ChangedPixels: changed,
                TotalPixels: total,
                ChangedPixelRatio: changedRatio,
                MeanDelta: meanDelta);
        }

        private static Image<Rgba32> createDimensionMismatchDiff(Image<Rgba32> expected, Image<Rgba32> actual)
        {
            int width = Math.Max(expected.Width, actual.Width);
            int height = Math.Max(expected.Height, actual.Height);
            var image = new Image<Rgba32>(width, height, new Rgba32(32, 0, 0, 255));

            drawRect(image, 0, 0, expected.Width, expected.Height, new Rgba32(220, 70, 70, 255));
            drawRect(image, 0, 0, actual.Width, actual.Height, new Rgba32(70, 220, 220, 120));
            return image;
        }

        private static void drawRect(Image<Rgba32> image, int x, int y, int width, int height, Rgba32 color)
        {
            if (width <= 0 || height <= 0)
                return;

            int xEnd = Math.Min(image.Width, x + width);
            int yEnd = Math.Min(image.Height, y + height);
            if (xEnd <= x || yEnd <= y)
                return;

            for (int row = y; row < yEnd; row++)
            for (int col = x; col < xEnd; col++)
                image[col, row] = color;
        }
    }
}
