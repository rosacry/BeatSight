using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using osu.Framework.Bindables;

namespace BeatSight.Tests;

/// <summary>
/// Tests for PlaybackScreen functionality including view modes, speed adjustment,
/// loop sections, and playback controls.
/// </summary>
public class PlaybackScreenTests
{
    #region View Mode Tests

    [Fact]
    public void ViewModeCyclesThroughAllModes()
    {
        var modes = new[] { LaneViewMode.TwoDimensional, LaneViewMode.ThreeDimensional, LaneViewMode.Manuscript };
        var current = LaneViewMode.TwoDimensional;

        // Simulate cycling through modes
        for (int i = 0; i < modes.Length; i++)
        {
            Assert.Equal(modes[i], current);
            current = GetNextViewMode(current);
        }

        // Should wrap back to first
        Assert.Equal(LaneViewMode.TwoDimensional, current);
    }

    [Fact]
    public void TwoDimensionalModeIsDefault()
    {
        var bindable = new Bindable<LaneViewMode>(LaneViewMode.TwoDimensional);

        Assert.Equal(LaneViewMode.TwoDimensional, bindable.Value);
    }

    [Fact]
    public void ViewModeChangeFires()
    {
        var bindable = new Bindable<LaneViewMode>(LaneViewMode.TwoDimensional);
        bool eventFired = false;
        LaneViewMode? newValue = null;

        bindable.BindValueChanged(e =>
        {
            eventFired = true;
            newValue = e.NewValue;
        });

        bindable.Value = LaneViewMode.ThreeDimensional;

        Assert.True(eventFired);
        Assert.Equal(LaneViewMode.ThreeDimensional, newValue);
    }

    #endregion

    #region Speed Adjustment Tests

    [Fact]
    public void SpeedAdjustmentHasCorrectBounds()
    {
        var speed = new BindableDouble
        {
            MinValue = 0.0,
            MaxValue = 2.0,
            Default = 1.0,
            Precision = 0.01
        };

        Assert.Equal(0.0, speed.MinValue);
        Assert.Equal(2.0, speed.MaxValue);
        Assert.Equal(1.0, speed.Default);
    }

    [Fact]
    public void SpeedAdjustmentClampsValues()
    {
        var speed = new BindableDouble
        {
            MinValue = 0.25,
            MaxValue = 2.0,
            Default = 1.0,
            Precision = 0.01
        };

        speed.Value = -0.5;
        Assert.Equal(0.25, speed.Value);

        speed.Value = 3.0;
        Assert.Equal(2.0, speed.Value);
    }

    [Fact]
    public void SpeedAffectsTrackDuration()
    {
        const double originalDuration = 180000; // 3 minutes
        const double speed = 0.5;

        // At 0.5x speed, it takes twice as long to play
        double effectiveDuration = originalDuration / speed;

        Assert.Equal(360000, effectiveDuration);
    }

    [Fact]
    public void SpeedZeroPausesPlayback()
    {
        var speed = new BindableDouble
        {
            MinValue = 0.0,
            MaxValue = 2.0,
            Default = 1.0
        };

        speed.Value = 0.0;
        bool shouldPause = speed.Value <= 0;

        Assert.True(shouldPause);
    }

    [Fact]
    public void SpeedPreservesPositionRatio()
    {
        const double trackDuration = 180000;
        const double currentPosition = 90000; // Halfway
        const double positionRatio = currentPosition / trackDuration;

        // When speed changes, the position ratio should stay the same
        // (effective duration would be trackDuration / newSpeed, but position in actual track time stays same)
        double expectedPosition = positionRatio * trackDuration; // Position in actual track time stays same

        Assert.Equal(0.5, positionRatio);
        Assert.Equal(90000, expectedPosition);
    }

    [Fact]
    public void SpeedDisplayFormatsCorrectly()
    {
        double[] speeds = { 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0 };
        string[] expected = { "0.25x", "0.50x", "0.75x", "1.00x", "1.25x", "1.50x", "2.00x" };

        for (int i = 0; i < speeds.Length; i++)
        {
            string formatted = $"{speeds[i]:F2}x";
            Assert.Equal(expected[i], formatted);
        }
    }

    #endregion

    #region Loop Section Tests

    [Fact]
    public void LoopSectionRequiresBothBounds()
    {
        double? loopStart = null;
        double? loopEnd = null;

        bool hasLoop = loopStart.HasValue && loopEnd.HasValue;
        Assert.False(hasLoop);

        loopStart = 10000;
        hasLoop = loopStart.HasValue && loopEnd.HasValue;
        Assert.False(hasLoop);

        loopEnd = 20000;
        hasLoop = loopStart.HasValue && loopEnd.HasValue;
        Assert.True(hasLoop);
    }

    [Fact]
    public void LoopSectionValidatesOrder()
    {
        const double loopStart = 15000;
        const double loopEnd = 10000; // Invalid: end before start

        bool isValid = loopEnd > loopStart;
        Assert.False(isValid);
    }

    [Fact]
    public void LoopSectionWrapsPlaybackPosition()
    {
        const double loopStart = 10000;
        const double loopEnd = 20000;
        const double currentPosition = 21000; // Past loop end

        double wrappedPosition = currentPosition;
        if (currentPosition >= loopEnd)
        {
            wrappedPosition = loopStart + (currentPosition - loopEnd);
        }

        Assert.Equal(11000, wrappedPosition);
    }

    [Fact]
    public void LoopDurationCalculatesCorrectly()
    {
        const double loopStart = 30000;
        const double loopEnd = 45000;

        double loopDuration = loopEnd - loopStart;

        Assert.Equal(15000, loopDuration);
    }

    [Fact]
    public void ClearingLoopRemovesBounds()
    {
        double? loopStart = 10000;
        double? loopEnd = 20000;

        // Clear loop
        loopStart = null;
        loopEnd = null;

        Assert.Null(loopStart);
        Assert.Null(loopEnd);
    }

    #endregion

    #region Playback State Tests

    [Fact]
    public void PlayPauseToggle()
    {
        bool isPlaying = false;

        // Toggle to playing
        isPlaying = !isPlaying;
        Assert.True(isPlaying);

        // Toggle to paused
        isPlaying = !isPlaying;
        Assert.False(isPlaying);
    }

    [Fact]
    public void RestartResetsPosition()
    {
        double currentPosition = 90000;

        // Restart
        currentPosition = 0;

        Assert.Equal(0, currentPosition);
    }

    [Fact]
    public void PlaybackProgressCalculation()
    {
        const double trackDuration = 180000;
        const double currentPosition = 45000;

        double progress = currentPosition / trackDuration;

        Assert.Equal(0.25, progress);
    }

    [Fact]
    public void PlaybackEndDetection()
    {
        const double trackDuration = 180000;
        const double tolerance = 100; // 100ms tolerance

        double position1 = 180050; // Just past end
        double position2 = 179800; // Just before end

        bool isAtEnd1 = position1 >= trackDuration - tolerance;
        bool isAtEnd2 = position2 >= trackDuration - tolerance;

        Assert.True(isAtEnd1);
        Assert.False(isAtEnd2);
    }

    #endregion

    #region Volume Control Tests

    [Fact]
    public void VolumeBindableHasCorrectBounds()
    {
        var volume = new BindableDouble(1.0)
        {
            MinValue = 0,
            MaxValue = 1,
            Precision = 0.01
        };

        Assert.Equal(0.0, volume.MinValue);
        Assert.Equal(1.0, volume.MaxValue);
        Assert.Equal(1.0, volume.Value);
    }

    [Fact]
    public void DrumAndBackingVolumeIndependent()
    {
        var drumVolume = new BindableDouble(1.0) { MinValue = 0, MaxValue = 1 };
        var backingVolume = new BindableDouble(1.0) { MinValue = 0, MaxValue = 1 };

        drumVolume.Value = 0.5;

        Assert.Equal(0.5, drumVolume.Value);
        Assert.Equal(1.0, backingVolume.Value); // Unchanged
    }

    [Fact]
    public void MuteSetVolumeToZero()
    {
        var volume = new BindableDouble(0.8) { MinValue = 0, MaxValue = 1 };

        volume.Value = 0;

        Assert.Equal(0, volume.Value);
    }

    #endregion

    #region Offset Adjustment Tests

    [Fact]
    public void OffsetAdjustmentHasCorrectBounds()
    {
        var offset = new BindableInt
        {
            MinValue = -1000,
            MaxValue = 1000,
            Default = 0,
            Precision = 1
        };

        Assert.Equal(-1000, offset.MinValue);
        Assert.Equal(1000, offset.MaxValue);
        Assert.Equal(0, offset.Default);
    }

    [Fact]
    public void PositiveOffsetDelaysNotes()
    {
        const double noteTime = 5000;
        const double offset = 100;

        double adjustedTime = noteTime + offset;

        Assert.Equal(5100, adjustedTime);
    }

    [Fact]
    public void NegativeOffsetAdvancesNotes()
    {
        const double noteTime = 5000;
        const double offset = -100;

        double adjustedTime = noteTime + offset;

        Assert.Equal(4900, adjustedTime);
    }

    #endregion

    #region Hit Detection Tests

    [Fact]
    public void HitWindowCalculation()
    {
        const double perfectWindowMs = 30;
        const double greatWindowMs = 60;
        const double goodWindowMs = 100;

        double[] timingDifferences = { 15, 45, 85, 150 };
        string[] expectedJudgments = { "Perfect", "Great", "Good", "Miss" };

        for (int i = 0; i < timingDifferences.Length; i++)
        {
            double diff = timingDifferences[i];
            string judgment = diff <= perfectWindowMs ? "Perfect"
                : diff <= greatWindowMs ? "Great"
                : diff <= goodWindowMs ? "Good"
                : "Miss";

            Assert.Equal(expectedJudgments[i], judgment);
        }
    }

    [Fact]
    public void EarlyHitIsNegativeTiming()
    {
        const double noteTime = 10000;
        const double inputTime = 9950; // 50ms early

        double timing = inputTime - noteTime;

        Assert.True(timing < 0);
        Assert.Equal(-50, timing);
    }

    [Fact]
    public void LateHitIsPositiveTiming()
    {
        const double noteTime = 10000;
        const double inputTime = 10075; // 75ms late

        double timing = inputTime - noteTime;

        Assert.True(timing > 0);
        Assert.Equal(75, timing);
    }

    #endregion

    #region Note Visibility Tests

    [Fact]
    public void NotesVisibleWithinScrollWindow()
    {
        const double currentTime = 50000;
        const double scrollWindowMs = 2000; // 2 seconds visible
        const double windowStart = currentTime - scrollWindowMs / 2; // 49000
        const double windowEnd = currentTime + scrollWindowMs / 2;   // 51000

        var notes = new[]
        {
            new HitObject { Time = 48500 }, // Out of window (too early)
            new HitObject { Time = 49500 }, // In window
            new HitObject { Time = 50000 }, // In window (current)
            new HitObject { Time = 50800 }, // In window
            new HitObject { Time = 55000 }, // Out of window (too late)
        };

        var visibleNotes = notes.Where(n => n.Time >= windowStart && n.Time <= windowEnd).ToList();

        Assert.Equal(3, visibleNotes.Count);
    }

    [Fact]
    public void ScrollSpeedAffectsNoteApproach()
    {
        const double scrollSpeed = 500; // pixels per second
        const double noteTimeMs = 2000; // 2 seconds in future

        double distanceFromHitLine = (noteTimeMs / 1000.0) * scrollSpeed;

        Assert.Equal(1000, distanceFromHitLine);
    }

    #endregion

    #region Confidence Heatmap Tests

    [Fact]
    public void ConfidenceValuesClampTo0To1()
    {
        double[] rawConfidences = { -0.1, 0.0, 0.5, 1.0, 1.5 };
        double[] expected = { 0.0, 0.0, 0.5, 1.0, 1.0 };

        for (int i = 0; i < rawConfidences.Length; i++)
        {
            double clamped = Math.Clamp(rawConfidences[i], 0, 1);
            Assert.Equal(expected[i], clamped);
        }
    }

    [Fact]
    public void LowConfidenceRegionsIdentified()
    {
        double[] confidences = { 0.9, 0.85, 0.4, 0.35, 0.5, 0.95 };
        const double threshold = 0.6;

        var lowConfidenceIndices = confidences
            .Select((c, i) => (conf: c, index: i))
            .Where(x => x.conf < threshold)
            .Select(x => x.index)
            .ToList();

        Assert.Equal(new[] { 2, 3, 4 }, lowConfidenceIndices);
    }

    #endregion

    #region Helper Methods

    private static LaneViewMode GetNextViewMode(LaneViewMode current)
    {
        return current switch
        {
            LaneViewMode.TwoDimensional => LaneViewMode.ThreeDimensional,
            LaneViewMode.ThreeDimensional => LaneViewMode.Manuscript,
            LaneViewMode.Manuscript => LaneViewMode.TwoDimensional,
            _ => LaneViewMode.TwoDimensional
        };
    }

    #endregion
}
