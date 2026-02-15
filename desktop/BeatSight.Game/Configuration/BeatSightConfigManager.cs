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
            performMigrations();
            ensureAllSettingsTracked();
        }

        private void performMigrations()
        {
            // Migration: SpeedAdjustmentMin default changed from 0.25 to 0.0.
            // Users with old config files will have 0.25 persisted.
            // Also catch cases where it might be slightly off or user set it to something else that breaks balance if Max is 2.0.
            double currentMin = Get<double>(BeatSightSetting.SpeedAdjustmentMin);
            double currentMax = Get<double>(BeatSightSetting.SpeedAdjustmentMax);

            // If Max is default (2.0) and Min is NOT default (0.0), reset Min to 0.0 to ensure balance.
            // This covers 0.25 and any other unbalanced value.
            if (Math.Abs(currentMax - 2.0) < 0.0001 && Math.Abs(currentMin - 0.0) > 0.0001)
            {
                GetBindable<double>(BeatSightSetting.SpeedAdjustmentMin).Value = 0.0;
            }
        }

        protected override void InitialiseDefaults()
        {
            // Window / Display
            setDefault(BeatSightSetting.WindowWidth, 1280);
            setDefault(BeatSightSetting.WindowHeight, 720);
            setDefault(BeatSightSetting.WindowFullscreen, false);
            setDefault(BeatSightSetting.WindowDisplayIndex, 0);

            // Playback Settings
            setDefault(BeatSightSetting.GameplayMode, GameplayMode.Manual);
            setDefault(BeatSightSetting.SpeedAdjustmentMin, 0.0);
            setDefault(BeatSightSetting.SpeedAdjustmentMax, 2.0);
            setDefault(BeatSightSetting.PlaybackZoomLevel, 1.36);
            setDefault(BeatSightSetting.PlaybackNoteWidth, 1.0);
            setDefault(BeatSightSetting.BackgroundDim, 0.8);
            setDefault(BeatSightSetting.BackgroundBlur, 0.0);
            setDefault(BeatSightSetting.HitLighting, true);
            setDefault(BeatSightSetting.ScreenShakeOnMiss, false);
            setDefault(BeatSightSetting.LaneViewMode, LaneViewMode.TwoDimensional);
            setDefault(BeatSightSetting.LanePreset, LanePreset.DrumSevenLane);
            setDefault(BeatSightSetting.KickLaneMode, KickLaneMode.GlobalLine);
            setDefault(BeatSightSetting.ThreeDStageProfile, ThreeDStageProfile.GhClassic);

            // Visual Settings
            setDefault(BeatSightSetting.ShowParticleEffects, true);
            setDefault(BeatSightSetting.ShowGlowEffects, true);
            setDefault(BeatSightSetting.ShowHitBurstAnimations, true);
            setDefault(BeatSightSetting.UseEnhancedViews, true);
            setDefault(BeatSightSetting.ShowComboMilestones, true);
            setDefault(BeatSightSetting.ShowFpsCounter, false);
            setDefault(BeatSightSetting.UIScale, 1.0, 0.5, 1.5, 0.01);
            setDefault(BeatSightSetting.NoteSkin, NoteSkinOption.Classic);
            setDefault(BeatSightSetting.ShowGlobalBackground, true);
            setDefault(BeatSightSetting.GlobalBackgroundOpacity, 0.5);
            setDefault(BeatSightSetting.ShowManuscriptPlaybackHighlighter, true);
            setDefault(BeatSightSetting.ManuscriptCountInGuideMode, ManuscriptCountInGuideMode.Full);

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
            setDefault(BeatSightSetting.EditorTimelineZoomDefault, 1.15);
            setDefault(BeatSightSetting.EditorWaveformScaleDefault, 1.0);
            setDefault(BeatSightSetting.EditorBeatGridVisibleDefault, true);

            // Audio Timing
            setDefault(BeatSightSetting.AudioOffset, 0.0);
            setDefault(BeatSightSetting.HitsoundOffset, 0.0);

            // Performance Settings
            setDefault(BeatSightSetting.FrameLimiterEnabled, false);
            setDefault(BeatSightSetting.FrameLimiterTarget, 144.0);
            setDefault(BeatSightSetting.FrameLimiter, FrameLimiterMode.BasicallyUnlimited);

            // AI / Generation
            setDefault(BeatSightSetting.PythonPath, "python");
            setDefault(BeatSightSetting.ModelVersion, "v1.0");
            setDefault(BeatSightSetting.UseGpu, false);
            setDefault(BeatSightSetting.AcoustIdApiKey, "");
            setDefault(BeatSightSetting.AutoGenerateOnImport, false);
            setDefault(BeatSightSetting.CustomModelPath, "");
            setDefault(BeatSightSetting.DefaultQuantization, "sixteenth");
            setDefault(BeatSightSetting.DefaultSensitivity, 60.0);

            // Developer Mode - enables local AI processing for developers only
            setDefault(BeatSightSetting.DeveloperModeEnabled, false);

            // Local Inference Settings (Developer Mode only)
            setDefault(BeatSightSetting.UseLocalInference, false);
            setDefault(BeatSightSetting.LocalModelPath, "");  // Path to .pth or .onnx model
            setDefault(BeatSightSetting.LocalModelVariant, "full");  // "full", "distilled", or "tiny"
            setDefault(BeatSightSetting.LocalInferenceDevice, "cuda");  // "cuda" or "cpu"
            setDefault(BeatSightSetting.ShowLocalInferenceOption, true);  // Show option in drag-drop dialog

            // Key Bindings (serialized as comma-separated key names)
            setDefault(BeatSightSetting.LaneKeys4, "D,F,J,K");
            setDefault(BeatSightSetting.LaneKeys5, "S,D,Space,J,K");
            setDefault(BeatSightSetting.LaneKeys6, "S,D,F,J,K,L");
            setDefault(BeatSightSetting.LaneKeys7, "S,D,F,Space,J,K,L");
            setDefault(BeatSightSetting.LaneKeys8, "A,S,D,F,J,K,L,Semicolon");

            // Onboarding
            setDefault(BeatSightSetting.HasCompletedOnboarding, false);
            setDefault(BeatSightSetting.OnboardingVersion, 0); // Increment to re-show onboarding
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

        private void setDefault(BeatSightSetting setting, double value, double? min = null, double? max = null, double? precision = null)
        {
            SetDefault(setting, value, min, max, precision);

            var capturedSetting = setting;
            var capturedValue = value;

            resetActions.Add(() =>
            {
                var bindable = GetBindable<double>(capturedSetting);
                bindable.Value = capturedValue;
            });

            trackingInitialisers.Add(() =>
            {
                var bindable = GetBindable<double>(capturedSetting);
                if (trackedSettings.Add(capturedSetting))
                {
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
        PlaybackZoomLevel,
        PlaybackNoteWidth,
        BackgroundDim,
        BackgroundBlur,
        HitLighting,
        ScreenShakeOnMiss,
        LaneViewMode,
        LanePreset,
        KickLaneMode,
        ThreeDStageProfile,

        // Visual
        ShowParticleEffects,
        ShowGlowEffects,
        ShowHitBurstAnimations,
        ShowComboMilestones,
        ShowFpsCounter,
        UIScale,
        NoteSkin,
        ShowGlobalBackground,
        GlobalBackgroundOpacity,
        UseEnhancedViews,
        ShowManuscriptPlaybackHighlighter,
        ManuscriptCountInGuideMode,

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
        FrameLimiterTarget,

        // AI / Generation
        PythonPath,
        ModelVersion,
        UseGpu,
        CustomModelPath,
        AcoustIdApiKey,
        DefaultQuantization,
        DefaultSensitivity,
        AutoGenerateOnImport,

        // Developer Mode
        DeveloperModeEnabled,

        // Local Inference (Developer Mode only)
        UseLocalInference,
        LocalModelPath,
        LocalModelVariant,
        LocalInferenceDevice,
        ShowLocalInferenceOption,

        // Key Bindings
        LaneKeys4,
        LaneKeys5,
        LaneKeys6,
        LaneKeys7,
        LaneKeys8,

        // Onboarding
        HasCompletedOnboarding,
        OnboardingVersion
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
        ThreeDimensional,
        Manuscript
    }

    public enum ManuscriptCountInGuideMode
    {
        Off,
        Compact,
        Full
    }

    public enum KickLaneMode
    {
        GlobalLine,
        DedicatedLane
    }

    public enum ThreeDStageProfile
    {
        Arcade,
        GhClassic,
        Tight
    }

    public enum LanePreset
    {
        DrumFourLane,
        DrumFiveLane,
        DrumSixLane,
        DrumSevenLane,
        DrumEightLane,
        DrumNineLane,
        AutoDynamic,
        Custom
    }

    public enum FrameLimiterMode
    {
        VSync,
        Twice,
        FourTimes,
        EightTimes,
        BasicallyUnlimited
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
