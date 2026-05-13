using System;
using osu.Framework.Logging;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private bool isTelemetrySeekSource(SeekInputSource source)
            => source == SeekInputSource.Wheel
               || source == SeekInputSource.SeekBar
               || source == SeekInputSource.Timeline;

        private void registerScrubSeekRequest(SeekInputSource source, double inputDelta)
        {
            if (!isTelemetrySeekSource(source))
                return;

            if (source == SeekInputSource.Wheel)
                wheelScrubActiveUntil = Time.Current + wheelScrubHoldMs;

            scrubTelemetryLastInputAt = Time.Current;

            if (!scrubTelemetryActive)
            {
                scrubTelemetryActive = true;
                scrubTelemetrySource = source;
                scrubTelemetrySessionStartAt = Time.Current;
                scrubTelemetryQueuedSeekCount = 0;
                scrubTelemetryFlushedSeekCount = 0;
                scrubTelemetryInputDeltaTotal = 0;
                scrubTelemetryFlushTotalMs = 0;
                scrubTelemetryFlushMaxMs = 0;
                scrubTelemetryFrameSampleCount = 0;
                scrubTelemetryFrameTotalMs = 0;
                scrubTelemetryFrameMaxMs = 0;
                scrubFrameAverageMs = scrubFrameTargetMs;
            }
            else if (source != SeekInputSource.Programmatic)
            {
                scrubTelemetrySource = source;
            }

            scrubTelemetryQueuedSeekCount++;
            scrubTelemetryInputDeltaTotal += inputDelta;
        }

        private void recordScrubSeekFlush(SeekInputSource source, double flushMs)
        {
            if (!scrubTelemetryActive || !isTelemetrySeekSource(source))
                return;

            double duration = Math.Max(0, flushMs);
            scrubTelemetryFlushedSeekCount++;
            scrubTelemetryFlushTotalMs += duration;
            scrubTelemetryFlushMaxMs = Math.Max(scrubTelemetryFlushMaxMs, duration);
        }

        private void updateScrubTelemetryFrame()
        {
            if (!scrubTelemetryActive)
                return;

            double frameMs = Math.Max(0, Time.Elapsed);
            scrubTelemetryFrameSampleCount++;
            scrubTelemetryFrameTotalMs += frameMs;
            scrubTelemetryFrameMaxMs = Math.Max(scrubTelemetryFrameMaxMs, frameMs);
            scrubFrameAverageMs = scrubTelemetryFrameSampleCount > 0
                ? scrubTelemetryFrameTotalMs / scrubTelemetryFrameSampleCount
                : scrubFrameTargetMs;

            bool wheelActive = Time.Current <= wheelScrubActiveUntil;
            bool hasRecentInput = Time.Current - scrubTelemetryLastInputAt < scrubTelemetryIdleTimeoutMs;
            if (footerSeekScrubbing || seekDispatchScheduled || wheelActive || hasRecentInput)
                return;

            finalizeScrubTelemetry();
        }

        private void finalizeScrubTelemetry()
        {
            if (!scrubTelemetryActive)
                return;

            double durationMs = Math.Max(0, Time.Current - scrubTelemetrySessionStartAt);
            double avgFrameMs = scrubTelemetryFrameSampleCount > 0
                ? scrubTelemetryFrameTotalMs / scrubTelemetryFrameSampleCount
                : 0;
            double avgFlushMs = scrubTelemetryFlushedSeekCount > 0
                ? scrubTelemetryFlushTotalMs / scrubTelemetryFlushedSeekCount
                : 0;
            double averageInputDelta = scrubTelemetryQueuedSeekCount > 0
                ? scrubTelemetryInputDeltaTotal / scrubTelemetryQueuedSeekCount
                : 0;

            lastScrubSummarySource = scrubTelemetrySource;
            lastScrubSummaryRecordedAt = Time.Current;
            lastScrubSummaryDurationMs = durationMs;
            lastScrubSummaryQueued = scrubTelemetryQueuedSeekCount;
            lastScrubSummaryFlushed = scrubTelemetryFlushedSeekCount;
            lastScrubSummaryAvgFrameMs = avgFrameMs;
            lastScrubSummaryMaxFrameMs = scrubTelemetryFrameMaxMs;
            lastScrubSummaryAvgFlushMs = avgFlushMs;
            lastScrubSummaryMaxFlushMs = scrubTelemetryFlushMaxMs;
            lastScrubSummaryAvgInputDelta = averageInputDelta;

            Logger.Log(
                $"[EditorScreen] ScrubTelemetry source={scrubTelemetrySource} duration={durationMs:0}ms queued={scrubTelemetryQueuedSeekCount} flushed={scrubTelemetryFlushedSeekCount} frame(avg/max)={avgFrameMs:0.00}/{scrubTelemetryFrameMaxMs:0.00}ms flush(avg/max)={avgFlushMs:0.00}/{scrubTelemetryFlushMaxMs:0.00}ms avgInputDelta={averageInputDelta:0.000}",
                LoggingTarget.Runtime,
                LogLevel.Important);

            if (scrubPerfOverlayVisible && scrubTelemetryFrameSampleCount >= 10 && scrubTelemetryFrameMaxMs >= 28)
                appendStatusDetail($"Scrub perf max {scrubTelemetryFrameMaxMs:0.0}ms (avg {avgFrameMs:0.0}ms)");

            updateScrubPerfOverlay(force: true);

            scrubTelemetryActive = false;
            scrubTelemetrySource = SeekInputSource.Programmatic;
            scrubTelemetrySessionStartAt = double.NegativeInfinity;
            scrubTelemetryLastInputAt = double.NegativeInfinity;
            scrubTelemetryQueuedSeekCount = 0;
            scrubTelemetryFlushedSeekCount = 0;
            scrubTelemetryInputDeltaTotal = 0;
            scrubTelemetryFlushTotalMs = 0;
            scrubTelemetryFlushMaxMs = 0;
            scrubTelemetryFrameSampleCount = 0;
            scrubTelemetryFrameTotalMs = 0;
            scrubTelemetryFrameMaxMs = 0;
            scrubFrameAverageMs = scrubFrameTargetMs;
            wheelScrubActiveUntil = double.NegativeInfinity;
        }

        private double getScrubFramePressureScale()
        {
            if (!double.IsFinite(scrubFrameAverageMs) || scrubFrameAverageMs <= scrubFrameTargetMs)
                return 1.0;

            return Math.Clamp(scrubFrameTargetMs / scrubFrameAverageMs, scrubFramePressureFloor, 1.0);
        }

        private double resolveSeekBarScrubSmoothing()
        {
            double smoothing = seekBarSmoothingBase * getScrubFramePressureScale();
            return Math.Clamp(smoothing, seekBarSmoothingFloor, seekBarSmoothingCeiling);
        }
    }
}
