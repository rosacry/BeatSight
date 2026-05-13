using System;
using System.IO;
using BeatSight.Game.Audio;
using BeatSight.Game.Configuration;
using osu.Framework.Audio;
using osu.Framework.Audio.Sample;
using osu.Framework.Bindables;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.IO.Stores;
using osu.Framework.Logging;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private BasicButton timelineMetronomeButton = null!;
        private SpriteText timelineMetronomeButtonText = null!;
        private Bindable<bool> metronomeEnabledSetting = null!;
        private Bindable<MetronomeSoundOption> metronomeSoundSetting = null!;
        private Bindable<double> metronomeVolumeSetting = null!;
        private Bindable<double> effectVolumeSetting = null!;
        private Bindable<bool> effectVolumeEnabledSetting = null!;
        private ISampleStore? storageSampleStore;
        private NamespacedResourceStore<byte[]>? embeddedResourceStore;
        private ISampleStore? embeddedSampleStore;
        private Sample? metronomeAccentSample;
        private Sample? metronomeRegularSample;
        private SampleChannel? activeEditorMetronomeChannel;
        private SampleChannel? activeEditorMetronomeAccentChannel;
        private int lastEditorMetronomeBeatIndex = -1;
        private bool pendingEditorMetronomePulse;
        private bool suppressEditorMetronomeUntilBeatChange;
        private const string userMetronomeDirectory = UserAssetDirectories.MetronomeSounds;

        private void initializeEditorMetronome()
        {
            metronomeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.MetronomeEnabled);
            metronomeSoundSetting = config.GetBindable<MetronomeSoundOption>(BeatSightSetting.MetronomeSound);
            metronomeVolumeSetting = config.GetBindable<double>(BeatSightSetting.MetronomeVolume);
            effectVolumeSetting = config.GetBindable<double>(BeatSightSetting.EffectVolume);
            effectVolumeEnabledSetting = config.GetBindable<bool>(BeatSightSetting.EffectVolumeEnabled);

            metronomeEnabledSetting.BindValueChanged(e =>
            {
                pendingEditorMetronomePulse = false;
                lastEditorMetronomeBeatIndex = -1;

                if (e.NewValue)
                {
                    suppressEditorMetronomeUntilBeatChange = isPlaying;
                    pendingEditorMetronomePulse = true;
                }
                else
                {
                    suppressEditorMetronomeUntilBeatChange = false;
                    stopEditorMetronomeChannels();
                }

                syncTimelineMetronomeButton();
            }, true);

            metronomeSoundSetting.BindValueChanged(e => loadEditorMetronomeSamples(e.NewValue), true);
        }

        private void toggleEditorMetronome()
        {
            if (metronomeEnabledSetting == null)
                return;

            metronomeEnabledSetting.Value = !metronomeEnabledSetting.Value;
            appendStatusDetail(metronomeEnabledSetting.Value ? "Metronome enabled" : "Metronome disabled");
        }

        private void syncTimelineMetronomeButton()
        {
            if (timelineMetronomeButton == null)
                return;

            bool enabled = metronomeEnabledSetting?.Value ?? false;
            if (timelineMetronomeButtonText != null)
                timelineMetronomeButtonText.Text = enabled ? "Metro On" : "Metro Off";

            timelineMetronomeButton.BackgroundColour = enabled
                ? EditorColours.AccentPlay
                : EditorColours.Lighten(EditorColours.ControlsBackground, 1.18f);
        }

        private void refreshTimingMetronomeControl()
        {
            if (timingMetronomeCheckbox == null || metronomeEnabledSetting == null)
                return;

            if (!ReferenceEquals(timingMetronomeCheckbox.Current, metronomeEnabledSetting))
                timingMetronomeCheckbox.Current = metronomeEnabledSetting;
        }

        private void resetEditorMetronomeTracking(bool suppressUntilNextBeat = false)
        {
            lastEditorMetronomeBeatIndex = -1;
            pendingEditorMetronomePulse = true;
            suppressEditorMetronomeUntilBeatChange = suppressUntilNextBeat;
        }

        private void handleEditorMetronome()
        {
            if (beatmap == null || metronomeEnabledSetting?.Value != true || !isPlaying)
                return;

            var timing = resolveTimelineTimingAt(currentTime);
            if (!(timing.Bpm > 0) || !double.IsFinite(timing.Bpm))
                return;

            double beatDuration = 60000.0 / timing.Bpm;
            double songTime = currentTime - timing.SnapOriginMs;
            if (songTime < 0)
                return;

            int beatIndex = (int)Math.Floor(songTime / beatDuration);
            if (suppressEditorMetronomeUntilBeatChange)
            {
                suppressEditorMetronomeUntilBeatChange = false;
                pendingEditorMetronomePulse = false;
                lastEditorMetronomeBeatIndex = beatIndex;
                return;
            }

            if (!pendingEditorMetronomePulse && beatIndex == lastEditorMetronomeBeatIndex)
                return;

            pendingEditorMetronomePulse = false;
            lastEditorMetronomeBeatIndex = beatIndex;

            bool isAccent = positiveModulo(beatIndex, Math.Max(1, timing.BeatsPerMeasure)) == 0;
            playEditorMetronomeSample(isAccent);
        }

        private void triggerEditorMetronomePreview(bool accent = true)
        {
            playEditorMetronomeSample(accent);
            appendStatusDetail(accent ? "Metronome accent preview" : "Metronome beat preview");
        }

        private void playEditorMetronomeSample(bool isAccent)
        {
            ensureEditorMetronomeSamplesLoaded();

            SampleChannel? channel = null;
            try
            {
                var sample = isAccent ? metronomeAccentSample : metronomeRegularSample;
                if (sample != null)
                {
                    channel = sample.GetChannel();
                    if (channel != null)
                    {
                        channel.Volume.Value = getEditorMetronomeGain(isAccent);
                        channel.Balance.Value = 0;
                        channel.Play();
                    }
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"[Editor] Failed to play metronome sample: {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }

            if (channel != null)
            {
                if (isAccent)
                {
                    activeEditorMetronomeAccentChannel?.Stop();
                    activeEditorMetronomeAccentChannel = channel;
                }
                else
                {
                    activeEditorMetronomeChannel?.Stop();
                    activeEditorMetronomeChannel = channel;
                }

                return;
            }

            playEditorFallbackMetronomeSample(isAccent);
        }

        private void ensureEditorMetronomeSamplesLoaded()
        {
            if (metronomeSoundSetting == null)
                return;

            if (metronomeAccentSample == null || metronomeRegularSample == null)
                loadEditorMetronomeSamples(metronomeSoundSetting.Value);
        }

        private void loadEditorMetronomeSamples(MetronomeSoundOption option)
        {
            if (audioManager == null)
                return;

            stopEditorMetronomeChannels();
            ensureEditorAudioStores();

            var (accentPath, regularPath) = MetronomeSampleLibrary.GetSamplePaths(option);
            metronomeAccentSample = tryGetEditorSample(accentPath);
            metronomeRegularSample = tryGetEditorSample(regularPath);

            if ((metronomeAccentSample == null || metronomeRegularSample == null) && option != MetronomeSoundOption.PercMetronomeQuartz)
                loadEditorMetronomeSamples(MetronomeSoundOption.PercMetronomeQuartz);
        }

        private Sample? tryGetEditorSample(string path)
        {
            try
            {
                ensureEditorAudioStores();
                Sample? sample = null;

                if (storageSampleStore != null)
                {
                    string fileName = Path.GetFileName(path);
                    if (!string.IsNullOrEmpty(fileName))
                    {
                        sample = storageSampleStore.Get($"{userMetronomeDirectory}/{fileName}");
                        if (sample == null)
                        {
                            string stem = Path.GetFileNameWithoutExtension(fileName);
                            if (!string.IsNullOrEmpty(stem))
                                sample = storageSampleStore.Get($"{userMetronomeDirectory}/{stem}");
                        }
                    }
                }

                if (sample == null && embeddedSampleStore != null)
                {
                    sample = embeddedSampleStore.Get(path);
                    if (sample == null && Path.HasExtension(path))
                    {
                        string? trimmedEmbedded = Path.ChangeExtension(path, null);
                        if (!string.IsNullOrEmpty(trimmedEmbedded))
                            sample = embeddedSampleStore.Get(trimmedEmbedded);
                    }
                }

                sample ??= audioManager.Samples.Get(path);
                if (sample == null && Path.HasExtension(path))
                {
                    string? trimmed = Path.ChangeExtension(path, null);
                    if (!string.IsNullOrEmpty(trimmed))
                        sample = audioManager.Samples.Get(trimmed);
                }

                return sample;
            }
            catch (Exception ex)
            {
                Logger.Log($"[Editor] Error loading metronome sample '{path}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                return null;
            }
        }

        private void playEditorFallbackMetronomeSample(bool isAccent)
        {
            foreach (var path in MetronomeSampleLibrary.GetFallbackCandidates(isAccent))
            {
                try
                {
                    var sample = tryGetEditorSample(path);
                    var channel = sample?.GetChannel();
                    if (channel == null)
                        continue;

                    channel.Volume.Value = getEditorMetronomeGain(isAccent) * 0.85f;
                    channel.Balance.Value = 0;
                    channel.Play();
                    return;
                }
                catch
                {
                    // Try next fallback.
                }
            }
        }

        private void stopEditorMetronomeChannels()
        {
            activeEditorMetronomeChannel?.Stop();
            activeEditorMetronomeChannel = null;
            activeEditorMetronomeAccentChannel?.Stop();
            activeEditorMetronomeAccentChannel = null;
        }

        private float getEditorMetronomeGain(bool isAccent)
        {
            double effect = effectVolumeEnabledSetting?.Value == false ? 0 : effectVolumeSetting?.Value ?? 1;
            double metronome = metronomeVolumeSetting?.Value ?? 0.6;
            if (metronome <= 0.001 || effect <= 0.001)
                return 0f;

            // Keep metronome clearly audible over music in editor/timing workflows.
            double effectMix = 0.38 + 0.62 * Math.Clamp(effect, 0, 1);
            double baseLevel = metronome * effectMix;
            double editorMixScale = 1.02;
            double accentFactor = isAccent ? 1.18 : 1.0;
            double blended = baseLevel * editorMixScale * accentFactor;
            return (float)Math.Clamp(blended, 0, 0.92);
        }

        private void ensureEditorAudioStores()
        {
            if (embeddedResourceStore == null)
            {
                embeddedResourceStore = new NamespacedResourceStore<byte[]>(
                    new DllResourceStore(typeof(global::BeatSight.Game.BeatSightGame).Assembly),
                    "BeatSight.Game.Resources");
            }

            MetronomeSampleBootstrap.EnsureDefaults(host.Storage, embeddedResourceStore, userMetronomeDirectory);
            storageResourceStore ??= new StorageBackedResourceStore(host.Storage);
            storageSampleStore ??= audioManager.GetSampleStore(storageResourceStore);
            embeddedSampleStore ??= audioManager.GetSampleStore(embeddedResourceStore);
            ensureEditorUserAssetDirectory(userMetronomeDirectory);
        }

        private void ensureEditorUserAssetDirectory(string relativePath)
        {
            try
            {
                string fullPath = host.Storage.GetFullPath(relativePath);
                if (!Directory.Exists(fullPath))
                    Directory.CreateDirectory(fullPath);
            }
            catch
            {
                // User custom directory creation is best-effort.
            }
        }
    }
}
