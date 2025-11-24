using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;
using Newtonsoft.Json.Linq;

namespace BeatSight.Game.Screens.Playback
{
    public partial class ConfidenceHeatmap : CompositeDrawable
    {
        private readonly List<ConfidencePoint> points = new();
        private double totalDuration;
        private readonly Container barContainer;
        private readonly Box cursor;

        public ConfidenceHeatmap(double duration)
        {
            totalDuration = duration;
            RelativeSizeAxes = Axes.X;
            Height = 20;

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black.Opacity(0.5f)
                },
                barContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 4
                },
                cursor = new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = 2,
                    Colour = Color4.White,
                    Origin = Anchor.Centre
                }
            };
        }

        public void LoadFromDebugJson(string jsonContent)
        {
            try
            {
                var json = JObject.Parse(jsonContent);
                var peaks = json["detection"]?["peaks"] as JArray;

                if (peaks == null) return;

                points.Clear();
                barContainer.Clear();

                foreach (var peak in peaks)
                {
                    double time = peak["time"]?.Value<double>() * 1000 ?? 0; // Convert to ms
                    double confidence = peak["confidence"]?.Value<double>() ?? 0;

                    points.Add(new ConfidencePoint { Time = time, Confidence = confidence });
                }

                // Generate visual segments
                // We can group them into chunks or draw individual lines
                // For a heatmap, chunks are better.

                double chunkSize = 1000; // 1 second chunks
                int chunks = (int)Math.Ceiling(totalDuration / chunkSize);

                for (int i = 0; i < chunks; i++)
                {
                    double startTime = i * chunkSize;
                    double endTime = (i + 1) * chunkSize;

                    var chunkPoints = points.Where(p => p.Time >= startTime && p.Time < endTime).ToList();

                    Color4 color = Color4.Gray; // No data
                    if (chunkPoints.Any())
                    {
                        double avgConfidence = chunkPoints.Average(p => p.Confidence);
                        color = getConfidenceColor(avgConfidence);
                    }

                    barContainer.Add(new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        RelativePositionAxes = Axes.X,
                        X = (float)(startTime / totalDuration),
                        Width = (float)(chunkSize / totalDuration),
                        Colour = color
                    });
                }
            }
            catch (Exception)
            {
                // Ignore parsing errors
            }
        }

        public void UpdatePosition(double currentTime)
        {
            float progress = (float)(currentTime / totalDuration);
            cursor.RelativePositionAxes = Axes.X;
            cursor.X = Math.Clamp(progress, 0, 1);
        }

        public void SetDuration(double duration)
        {
            totalDuration = duration;
            // Clear existing bars as they are now invalid scale
            barContainer.Clear();
            points.Clear();
        }

        private Color4 getConfidenceColor(double confidence)
        {
            // Red (low) -> Yellow (med) -> Green (high)
            if (confidence < 0.5) return Color4.Red;
            if (confidence < 0.8) return Color4.Yellow;
            return Color4.Green;
        }

        private struct ConfidencePoint
        {
            public double Time;
            public double Confidence;
        }

        /// <summary>
        /// Returns whether any confidence data has been loaded.
        /// </summary>
        public bool HasConfidenceData => points.Count > 0;

        public (double Start, double End)? GetNextLowConfidenceSection(double currentTime, double threshold = 0.7)
        {
            // Return null early if no data is loaded
            if (points.Count == 0)
                return null;

            // Find a point after currentTime with low confidence
            var nextLow = points
                .Where(p => p.Time > currentTime && p.Confidence < threshold)
                .OrderBy(p => p.Time)
                .FirstOrDefault();

            if (nextLow.Time == 0 && nextLow.Confidence == 0 && !points.Contains(nextLow))
                return null; // Not found (struct default check)

            // Define a section around it (e.g., 2 seconds)
            double start = Math.Max(0, nextLow.Time - 1000);
            double end = Math.Min(totalDuration, nextLow.Time + 1000);

            return (start, end);
        }
    }
}
