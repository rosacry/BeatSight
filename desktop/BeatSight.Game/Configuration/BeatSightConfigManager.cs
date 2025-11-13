using osu.Framework.Configuration;
using osu.Framework.Platform;

namespace BeatSight.Game.Configuration
{
    public class BeatSightConfigManager : IniConfigManager<BeatSightSetting>
    {
        protected override string Filename => "beatsight.ini";

        public BeatSightConfigManager(Storage storage)
            : base(storage)
        {
        }

        protected override void InitialiseDefaults()
        {
            // Gameplay Settings
            SetDefault(BeatSightSetting.GameplayMode, GameplayMode.Auto);
            SetDefault(BeatSightSetting.SpeedAdjustmentMin, 0.25);
            SetDefault(BeatSightSetting.SpeedAdjustmentMax, 2.0);
            SetDefault(BeatSightSetting.BackgroundDim, 0.8);
            SetDefault(BeatSightSetting.BackgroundBlur, 0.0);
            SetDefault(BeatSightSetting.HitLighting, true);
            SetDefault(BeatSightSetting.ShowHitErrorMeter, true);
            SetDefault(BeatSightSetting.ScreenShakeOnMiss, true);
            SetDefault(BeatSightSetting.LaneViewMode, LaneViewMode.TwoDimensional);
            SetDefault(BeatSightSetting.LanePreset, LanePreset.DrumSevenLane);

            // Visual Effects Settings
            SetDefault(BeatSightSetting.ShowApproachCircles, true);
            SetDefault(BeatSightSetting.ShowParticleEffects, true);
            SetDefault(BeatSightSetting.ShowGlowEffects, true);
            SetDefault(BeatSightSetting.ShowHitBurstAnimations, true);
            SetDefault(BeatSightSetting.ShowComboMilestones, true);
            SetDefault(BeatSightSetting.ShowFpsCounter, false);
            SetDefault(BeatSightSetting.UIScale, 1.0);

            // Audio Settings
            SetDefault(BeatSightSetting.MasterVolume, 1.0);
            SetDefault(BeatSightSetting.MusicVolume, 0.8);
            SetDefault(BeatSightSetting.EffectVolume, 0.6);
            SetDefault(BeatSightSetting.HitsoundVolume, 0.5);
            SetDefault(BeatSightSetting.MetronomeEnabled, true);
            SetDefault(BeatSightSetting.MetronomeVolume, 0.6);
            SetDefault(BeatSightSetting.MetronomeSound, MetronomeSoundOption.Click);
            SetDefault(BeatSightSetting.DrumStemPlaybackOnly, false);

            // Detection / Analysis
            SetDefault(BeatSightSetting.DetectionSensitivity, 60);
            SetDefault(BeatSightSetting.DetectionQuantizationGrid, QuantizationGridSetting.Sixteenth);
            SetDefault(BeatSightSetting.ShowDetectionDebugOverlay, false);

            // Visual Customisation
            SetDefault(BeatSightSetting.NoteSkin, NoteSkinOption.Classic);

            // Editor Defaults
            SetDefault(BeatSightSetting.EditorTimelineZoomDefault, 1.0);
            SetDefault(BeatSightSetting.EditorWaveformScaleDefault, 1.0);
            SetDefault(BeatSightSetting.EditorBeatGridVisibleDefault, true);

            // Input Settings
            SetDefault(BeatSightSetting.AudioOffset, 0.0);
            SetDefault(BeatSightSetting.HitsoundOffset, 0.0);

            // Calibration
            SetDefault(BeatSightSetting.MicCalibrationCompleted, false);
            SetDefault(BeatSightSetting.MicCalibrationLastUpdated, string.Empty);
            SetDefault(BeatSightSetting.MicCalibrationProfilePath, string.Empty);
            SetDefault(BeatSightSetting.MicCalibrationDeviceId, string.Empty);

            // Performance Settings
            SetDefault(BeatSightSetting.FrameLimiter, FrameLimiterMode.Unlimited);
        }
    }

    public enum BeatSightSetting
    {
        // Gameplay
        GameplayMode,
        SpeedAdjustmentMin,
        SpeedAdjustmentMax,
        BackgroundDim,
        BackgroundBlur,
        HitLighting,
        ShowHitErrorMeter,
        ScreenShakeOnMiss,
        LaneViewMode,
        LanePreset,

        // Visual Effects
        ShowApproachCircles,
        ShowParticleEffects,
        ShowGlowEffects,
        ShowHitBurstAnimations,
        ShowComboMilestones,
        ShowFpsCounter,
        UIScale,

        // Audio
        MasterVolume,
        MusicVolume,
        EffectVolume,
        HitsoundVolume,
        MetronomeEnabled,
        MetronomeVolume,
        MetronomeSound,
        DrumStemPlaybackOnly,

        // Input
        AudioOffset,
        HitsoundOffset,

        // Detection / Analysis
        DetectionSensitivity,
        DetectionQuantizationGrid,
        ShowDetectionDebugOverlay,

        // Visual Customisation
        NoteSkin,

        // Editor Defaults
        EditorTimelineZoomDefault,
        EditorWaveformScaleDefault,
        EditorBeatGridVisibleDefault,

        // Calibration
        MicCalibrationCompleted,
        MicCalibrationLastUpdated,
        MicCalibrationProfilePath,
        MicCalibrationDeviceId,

        // Performance
        FrameLimiter
    }

    public enum GameplayMode
    {
        /// <summary>
        /// Auto-play with automatic drum detection and scoring
        /// </summary>
        Auto,

        /// <summary>
        /// Manual play-along mode without scoring or detection
        /// </summary>
        Manual
    }

    public enum FrameLimiterMode
    {
        Unlimited,
        VSync,
        Limit60,
        Limit120,
        Limit240
    }

    public enum LaneViewMode
    {
        TwoDimensional,
        ThreeDimensional
    }

    public enum LanePreset
    {
        DrumFourLane,
        DrumFiveLane,
        DrumSixLane,
        DrumSevenLane,
        DrumEightLane,
        DrumNineLane
    }

    public enum QuantizationGridSetting
    {
        Quarter,
        Eighth,
        Sixteenth,
        Triplet,
        ThirtySecond
    }

    public enum MetronomeSoundOption
    {
        Click,
        Woodblock,
        Cowbell
    }

    public enum NoteSkinOption
    {
        Classic,
        Neon,
        Carbon
    }
}
