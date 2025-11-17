using System;
using System.Collections.Generic;
using osu.Framework.Configuration;
using osu.Framework.Platform;

namespace BeatSight.Game.Configuration
{
    public class BeatSightConfigManager : IniConfigManager<BeatSightSetting>
    {
        private readonly List<Action> resetActions = new();
        private readonly List<Action> trackingInitialisers = new();
        private readonly HashSet<BeatSightSetting> trackedSettings = new();

        /// <summary>
        /// Exposes the full set of settings currently bound to the on-disk user configuration.
        /// Useful for diagnostics and for ensuring new enum members are persisted.
        /// </summary>
        public IReadOnlyCollection<BeatSightSetting> TrackedSettings => trackedSettings;

        protected override string Filename => "beatsight.ini";

        public BeatSightConfigManager(Storage storage)
            : base(storage)
        {
            ensureAllSettingsTracked();
        }

        protected override void InitialiseDefaults()
        {
            // Window / Display
            setDefault(BeatSightSetting.WindowWidth, 1024);
            setDefault(BeatSightSetting.WindowHeight, 576);
            setDefault(BeatSightSetting.WindowFullscreen, false);
            setDefault(BeatSightSetting.WindowDisplayIndex, 0);

            // Playback Settings
            setDefault(BeatSightSetting.GameplayMode, GameplayMode.Manual);
            setDefault(BeatSightSetting.SpeedAdjustmentMin, 0.25);
            setDefault(BeatSightSetting.SpeedAdjustmentMax, 2.0);
            setDefault(BeatSightSetting.BackgroundDim, 0.8);
            setDefault(BeatSightSetting.BackgroundBlur, 0.0);
            setDefault(BeatSightSetting.HitLighting, true);
            setDefault(BeatSightSetting.ScreenShakeOnMiss, false);
            setDefault(BeatSightSetting.LaneViewMode, LaneViewMode.TwoDimensional);
            setDefault(BeatSightSetting.LanePreset, LanePreset.DrumSevenLane);
            setDefault(BeatSightSetting.KickLaneMode, KickLaneMode.GlobalLine);

            // Visual Settings
            setDefault(BeatSightSetting.ShowApproachCircles, true);
            setDefault(BeatSightSetting.ShowParticleEffects, true);
            setDefault(BeatSightSetting.ShowGlowEffects, true);
            setDefault(BeatSightSetting.ShowHitBurstAnimations, true);
            setDefault(BeatSightSetting.ShowComboMilestones, true);
            setDefault(BeatSightSetting.ShowFpsCounter, false);
            setDefault(BeatSightSetting.UIScale, 1.0);
            setDefault(BeatSightSetting.NoteSkin, NoteSkinOption.Classic);

            // Audio Settings
            setDefault(BeatSightSetting.MasterVolume, 1.0);
            setDefault(BeatSightSetting.MasterVolumeEnabled, true);
            setDefault(BeatSightSetting.MusicVolume, 0.8);
            setDefault(BeatSightSetting.MusicVolumeEnabled, true);
            setDefault(BeatSightSetting.EffectVolume, 0.6);
            setDefault(BeatSightSetting.EffectVolumeEnabled, true);
            setDefault(BeatSightSetting.HitsoundVolume, 0.5);
            setDefault(BeatSightSetting.HitsoundVolumeEnabled, true);
            setDefault(BeatSightSetting.MetronomeEnabled, false);
            setDefault(BeatSightSetting.MetronomeVolume, 0.6);
            setDefault(BeatSightSetting.MetronomeSound, MetronomeSoundOption.PercMetronomeQuartz);
            setDefault(BeatSightSetting.DrumStemPlaybackOnly, false);

            // Detection / Analysis
            setDefault(BeatSightSetting.DetectionSensitivity, 60);
            setDefault(BeatSightSetting.DetectionQuantizationGrid, QuantizationGridSetting.Sixteenth);
            setDefault(BeatSightSetting.ShowDetectionDebugOverlay, false);

            // Editor Defaults
            setDefault(BeatSightSetting.EditorTimelineZoomDefault, 1.0);
            setDefault(BeatSightSetting.EditorWaveformScaleDefault, 1.0);
            setDefault(BeatSightSetting.EditorBeatGridVisibleDefault, true);

            // Audio Timing
            setDefault(BeatSightSetting.AudioOffset, 0.0);
            setDefault(BeatSightSetting.HitsoundOffset, 0.0);

            // Performance Settings
            setDefault(BeatSightSetting.FrameLimiterEnabled, false);
            setDefault(BeatSightSetting.FrameLimiterTarget, 144.0);
            setDefault(BeatSightSetting.FrameLimiter, FrameLimiterMode.Unlimited);
        }

        public void ResetToDefaults()
        {
            foreach (var reset in resetActions)
                reset();
        }

        private void ensureAllSettingsTracked()
        {
            if (trackingInitialisers.Count == 0)
                return;

            foreach (var initialise in trackingInitialisers)
                initialise();

            trackingInitialisers.Clear();
        }

        private void setDefault<T>(BeatSightSetting setting, T value)
        {
            SetDefault(setting, value);

            var capturedSetting = setting;
            var capturedValue = value;

            resetActions.Add(() =>
            {
                var bindable = GetBindable<T>(capturedSetting);
                bindable.Value = capturedValue;
            });

            trackingInitialisers.Add(() =>
            {
                var bindable = GetBindable<T>(capturedSetting);
                if (trackedSettings.Add(capturedSetting))
                {
                    // Touch the bindable once so the underlying config manager starts tracking
                    // this setting immediately and persists the default to the user config.
                    var _ = bindable.Value;
                }
            });
        }
    }

    public enum BeatSightSetting
    {
        // Window / Display
        WindowWidth,
        WindowHeight,
        WindowFullscreen,
        WindowDisplayIndex,

        // Playback
        GameplayMode,
        SpeedAdjustmentMin,
        SpeedAdjustmentMax,
        BackgroundDim,
        BackgroundBlur,
        HitLighting,
        ScreenShakeOnMiss,
        LaneViewMode,
        LanePreset,
        KickLaneMode,

        // Visual
        ShowApproachCircles,
        ShowParticleEffects,
        ShowGlowEffects,
        ShowHitBurstAnimations,
        ShowComboMilestones,
        ShowFpsCounter,
        UIScale,
        NoteSkin,

        // Audio
        MasterVolume,
        MasterVolumeEnabled,
        MusicVolume,
        MusicVolumeEnabled,
        EffectVolume,
        EffectVolumeEnabled,
        HitsoundVolume,
        HitsoundVolumeEnabled,
        MetronomeEnabled,
        MetronomeVolume,
        MetronomeSound,
        DrumStemPlaybackOnly,
        AudioOffset,
        HitsoundOffset,

        // Detection / Analysis
        DetectionSensitivity,
        DetectionQuantizationGrid,
        ShowDetectionDebugOverlay,

        // Editor Defaults
        EditorTimelineZoomDefault,
        EditorWaveformScaleDefault,
        EditorBeatGridVisibleDefault,

        // Performance
        FrameLimiter,
        FrameLimiterEnabled,
        FrameLimiterTarget
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

    public enum LaneViewMode
    {
        TwoDimensional,
        ThreeDimensional
    }

    public enum KickLaneMode
    {
        GlobalLine,
        DedicatedLane
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

    public enum FrameLimiterMode
    {
        Unlimited,
        VSync,
        Limit60,
        Limit120,
        Limit240
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
        // Percussion sounds
        PercCan,
        PercCastanet,
        PercChair,
        PercClackhead,
        PercClap,
        PercClickToy,
        PercGlass,
        PercHeadKnock,
        PercKeyboard,
        PercMetal,
        PercMetronomeQuartz, // Default
        PercMouthPop,
        PercMusicStand,
        PercPracticePad,
        PercSnap,
        PercSqueak,
        PercStick,
        PercTambA,
        PercTambB,
        PercTambC,
        PercTambD,
        PercTeeth,
        PercTongue,
        PercTrashCan,
        PercWhistleParty,
        PercWhistleRef,

        // Synth sounds
        SynthBellA,
        SynthBellB,
        SynthBlockA,
        SynthBlockB,
        SynthBlockC,
        SynthBlockD,
        SynthBlockE,
        SynthBlockF,
        SynthBlockG,
        SynthBlockH,
        SynthSineA,
        SynthSineB,
        SynthSineC,
        SynthSineD,
        SynthSineE,
        SynthSineF,
        SynthSquareA,
        SynthSquareB,
        SynthSquareC,
        SynthSquareD,
        SynthSquareE,
        SynthTickA,
        SynthTickB,
        SynthTickC,
        SynthTickD,
        SynthTickE,
        SynthTickF,
        SynthTickG,
        SynthTickH,
        SynthWeirdA,
        SynthWeirdB,
        SynthWeirdC,
        SynthWeirdD,
        SynthWeirdE
    }

    public enum NoteSkinOption
    {
        Classic,
        Neon,
        Carbon
    }
}
