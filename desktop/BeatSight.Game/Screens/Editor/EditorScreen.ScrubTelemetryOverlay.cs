using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createScrubPerfOverlay()
        {
            scrubPerfOverlayText = new SpriteText
            {
                Text = "Scrub Perf",
                Font = BeatSightFont.Caption(10.8f),
                Colour = EditorColours.TextPrimary,
                UseFullGlyphHeight = false
            };

            scrubPerfOverlayContainer = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Margin = new MarginPadding { Top = 88, Right = 18 },
                Masking = true,
                CornerRadius = 8,
                Alpha = 0,
                AlwaysPresent = false,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.Lighten(EditorColours.HeaderBackground, 1.07f).Opacity(0.88f)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.18f
                    },
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 9, Vertical = 7 },
                        Child = scrubPerfOverlayText
                    }
                }
            };

            return scrubPerfOverlayContainer;
        }

        private void toggleScrubPerfOverlay()
        {
            scrubPerfOverlayVisible = !scrubPerfOverlayVisible;
            if (scrubPerfOverlayContainer == null)
                return;

            scrubPerfOverlayContainer.AlwaysPresent = scrubPerfOverlayVisible;
            scrubPerfOverlayContainer.ClearTransforms();
            if (scrubPerfOverlayVisible)
            {
                updateScrubPerfOverlay(force: true);
                scrubPerfOverlayContainer.FadeIn(140, Easing.OutQuint);
                appendStatusDetail("Scrub Perf overlay enabled");
            }
            else
            {
                scrubPerfOverlayContainer.FadeOut(110, Easing.OutQuint);
                appendStatusDetail("Scrub Perf overlay hidden");
            }
        }

        private void updateScrubPerfOverlay(bool force = false)
        {
            if (!scrubPerfOverlayVisible || scrubPerfOverlayText == null)
                return;

            if (!force && Time.Current - lastScrubPerfOverlayUpdateAt < scrubPerfOverlayRefreshMs)
                return;

            string source = scrubTelemetryActive ? scrubTelemetrySource.ToString() : lastScrubSummarySource.ToString();
            double avgFrame = scrubTelemetryActive
                ? (scrubTelemetryFrameSampleCount > 0 ? scrubTelemetryFrameTotalMs / scrubTelemetryFrameSampleCount : 0)
                : lastScrubSummaryAvgFrameMs;
            double maxFrame = scrubTelemetryActive ? scrubTelemetryFrameMaxMs : lastScrubSummaryMaxFrameMs;
            double avgFlush = scrubTelemetryActive
                ? (scrubTelemetryFlushedSeekCount > 0 ? scrubTelemetryFlushTotalMs / scrubTelemetryFlushedSeekCount : 0)
                : lastScrubSummaryAvgFlushMs;
            double maxFlush = scrubTelemetryActive ? scrubTelemetryFlushMaxMs : lastScrubSummaryMaxFlushMs;
            double avgInputDelta = scrubTelemetryActive
                ? (scrubTelemetryQueuedSeekCount > 0 ? scrubTelemetryInputDeltaTotal / scrubTelemetryQueuedSeekCount : 0)
                : lastScrubSummaryAvgInputDelta;
            int queued = scrubTelemetryActive ? scrubTelemetryQueuedSeekCount : lastScrubSummaryQueued;
            int flushed = scrubTelemetryActive ? scrubTelemetryFlushedSeekCount : lastScrubSummaryFlushed;
            double pressureScale = getScrubFramePressureScale();
            string mode = scrubTelemetryActive ? "live" : "last";
            string age = lastScrubSummaryRecordedAt > 0
                ? $"{(Time.Current - lastScrubSummaryRecordedAt) / 1000.0:0.0}s ago"
                : "n/a";

            scrubPerfOverlayText.Text =
                $"Scrub Perf ({mode})\n" +
                $"src {source} | q/f {queued}/{flushed}\n" +
                $"dur {(scrubTelemetryActive ? (Time.Current - scrubTelemetrySessionStartAt) : lastScrubSummaryDurationMs):0}ms | {age}\n" +
                $"frame {avgFrame:0.00}/{maxFrame:0.00} ms\n" +
                $"flush {avgFlush:0.00}/{maxFlush:0.00} ms\n" +
                $"input Δ {avgInputDelta:0.000} | pressure x{pressureScale:0.00}";

            lastScrubPerfOverlayUpdateAt = Time.Current;
        }
    }
}
