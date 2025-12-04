// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from SettingsScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.2

using System;
using System.Globalization;
using System.IO;
using System.Linq;
using BeatSight.Game.Audio;
using BeatSight.Game.Configuration;
using BeatSight.Game.Customization;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Audio;
using osu.Framework.Audio.Sample;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.IO.Stores;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Settings
{
    /// <summary>
    /// Settings section for audio configuration including volume controls,
    /// metronome settings, and audio offset adjustments.
    /// </summary>
    public partial class AudioSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;
        private readonly GameHost host;
        private StorageBackedResourceStore? storageResourceStore;
        private ISampleStore? storageSampleStore;
        private NamespacedResourceStore<byte[]>? embeddedResourceStore;
        private ISampleStore? embeddedSampleStore;
        private SampleChannel? metronomePreviewChannel;
        private const string userMetronomeDirectory = UserAssetDirectories.MetronomeSounds;
        private const float dropdownMenuMaxHeight = 240;

        [Resolved]
        private AudioManager audioManager { get; set; } = null!;

        public AudioSettingsSection(BeatSightConfigManager config, GameHost host, Container dropdownOverlay, SettingsTooltipOverlay tooltipOverlay)
            : base("Audio Settings", dropdownOverlay, tooltipOverlay)
        {
            this.config = config;
            this.host = host;
        }

        protected override Drawable createContent()
        {
            var masterVolumeEnabled = config.GetBindable<bool>(BeatSightSetting.MasterVolumeEnabled);
            var musicVolumeEnabled = config.GetBindable<bool>(BeatSightSetting.MusicVolumeEnabled);
            var effectVolumeEnabled = config.GetBindable<bool>(BeatSightSetting.EffectVolumeEnabled);
            var hitsoundVolumeEnabled = config.GetBindable<bool>(BeatSightSetting.HitsoundVolumeEnabled);
            var metronomeEnabled = config.GetBindable<bool>(BeatSightSetting.MetronomeEnabled);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 12),
                Children = new Drawable[]
                {
                    CreateSlider(
                        "Master Volume",
                        config.GetBindable<double>(BeatSightSetting.MasterVolume),
                        0,
                        1,
                        0.01,
                        "Overall volume control.",
                        valueFormatter: PercentageFormatter(),
                        toggleBindable: masterVolumeEnabled,
                        toggleMode: SliderToggleMode.ZeroValue
                    ),
                    CreateSlider(
                        "Music Volume",
                        config.GetBindable<double>(BeatSightSetting.MusicVolume),
                        0,
                        1,
                        0.01,
                        "Volume for music tracks.",
                        valueFormatter: PercentageFormatter(),
                        toggleBindable: musicVolumeEnabled,
                        toggleMode: SliderToggleMode.ZeroValue
                    ),
                    CreateSlider(
                        "Effect Volume",
                        config.GetBindable<double>(BeatSightSetting.EffectVolume),
                        0,
                        1,
                        0.01,
                        "Volume for hit sounds and effects.",
                        valueFormatter: PercentageFormatter(),
                        toggleBindable: effectVolumeEnabled,
                        toggleMode: SliderToggleMode.ZeroValue
                    ),
                    CreateSlider(
                        "Hitsound Volume",
                        config.GetBindable<double>(BeatSightSetting.HitsoundVolume),
                        0,
                        1,
                        0.01,
                        "Volume for individual note hit feedback sounds.",
                        valueFormatter: PercentageFormatter(),
                        toggleBindable: hitsoundVolumeEnabled,
                        toggleMode: SliderToggleMode.ZeroValue
                    ),
                    CreateSlider(
                        "Metronome Volume",
                        config.GetBindable<double>(BeatSightSetting.MetronomeVolume),
                        0,
                        1.5,
                        0.01,
                        "Adjust the metronome level relative to the music mix, with extra headroom for loud clicks.",
                        valueFormatter: value => $"{Math.Min(value * 100, 100).ToString("F0", CultureInfo.InvariantCulture)}%",
                        toggleBindable: metronomeEnabled,
                        toggleMode: SliderToggleMode.ZeroValue
                    ),
                    createMetronomeSoundSetting(),
                    createMetronomeAssetSetting(),
                    CreateCheckbox(
                        "Prefer Drum Stem Playback",
                        config.GetBindable<bool>(BeatSightSetting.DrumStemPlaybackOnly),
                        "When available, switch playback to the isolated drum stem instead of the full mix."
                    ),
                    CreateSlider(
                        "Audio Offset",
                        config.GetBindable<double>(BeatSightSetting.AudioOffset),
                        -500,
                        500,
                        1,
                        "Adjust audio timing in milliseconds if playback is out of sync.",
                        valueFormatter: MillisecondsFormatter()
                    )
                }
            };
        }

        protected override void Dispose(bool isDisposing)
        {
            stopPreviewChannel();
            base.Dispose(isDisposing);
        }

        private SettingItem createMetronomeSoundSetting()
        {
            var metronomeSound = config.GetBindable<MetronomeSoundOption>(BeatSightSetting.MetronomeSound);

            var dropdown = new InlineDropdown<MetronomeSoundOption>(dropdownMenuMaxHeight)
            {
                Width = 220,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Items = Enum.GetValues(typeof(MetronomeSoundOption)).Cast<MetronomeSoundOption>().ToArray()
            };

            dropdown.SearchEnabled = true;

            dropdown.OverlayLayer = DropdownOverlay;
            dropdown.Current = metronomeSound;
            dropdown.Current.BindValueChanged(_ => stopPreviewChannel());

            var previewButton = new BeatSightButton
            {
                Size = new Vector2(72, 32),
                Text = "Play",
                BackgroundColour = new Color4(72, 84, 120, 255),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Action = () => playMetronomePreview(dropdown.Current.Value)
            };

            var control = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Children = new Drawable[]
                {
                    previewButton,
                    dropdown
                }
            };

            var setting = CreateSettingItem(
                "Metronome Sound",
                "Select the tone used for the metronome click. Use the play button to preview it immediately.",
                control,
                dropdown);

            setting.SetDefaultValue(metronomeSound.Default.ToString());
            metronomeSound.BindValueChanged(_ => setting.SetModified(!metronomeSound.IsDefault), true);

            return setting;
        }

        private SettingItem createMetronomeAssetSetting()
        {
            var openButton = new BeatSightButton
            {
                Width = 260,
                Height = 32,
                Text = "Open Metronome Sounds Folder",
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Action = () => SettingsScreen.OpenDirectoryExternally(host, userMetronomeDirectory)
            };

            var control = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = openButton
            };

            return CreateSettingItem(
                "Custom Metronome Library",
                "Drop your own accent/regular samples into the folder that opens to extend the metronome library.",
                control);
        }

        private void playMetronomePreview(MetronomeSoundOption option)
        {
            ensureSampleStores();

            var (accentPath, regularPath) = MetronomeSampleLibrary.GetSamplePaths(option);

            Sample? sample = tryGetSample(accentPath) ?? tryGetSample(regularPath);

            if (sample == null)
            {
                foreach (var fallback in MetronomeSampleLibrary.GetFallbackCandidates(true))
                {
                    sample = tryGetSample(fallback);
                    if (sample != null)
                        break;
                }
            }

            if (sample == null)
            {
                Logger.Log($"[Settings] No metronome sample could be previewed for option '{option}'.", LoggingTarget.Runtime, LogLevel.Debug);
                return;
            }

            stopPreviewChannel();

            var channel = sample.GetChannel();
            if (channel == null)
                return;

            double previewVolume = config.GetBindable<double>(BeatSightSetting.MetronomeVolume).Value;
            double effectsVolume = config.GetBindable<double>(BeatSightSetting.EffectVolume).Value;
            channel.Volume.Value = (float)Math.Clamp(previewVolume * effectsVolume, 0, 1.5);
            channel.Play();

            metronomePreviewChannel = channel;
        }

        private void ensureSampleStores()
        {
            if (embeddedResourceStore == null)
            {
                embeddedResourceStore = new NamespacedResourceStore<byte[]>(
                    new DllResourceStore(typeof(global::BeatSight.Game.BeatSightGame).Assembly),
                    "BeatSight.Game.Resources");
            }

            MetronomeSampleBootstrap.EnsureDefaults(host.Storage, embeddedResourceStore, userMetronomeDirectory);
            NoteSkinBootstrap.EnsureDefaults(host.Storage, embeddedResourceStore, UserAssetDirectories.Skins);

            storageResourceStore ??= new StorageBackedResourceStore(host.Storage);
            storageSampleStore ??= audioManager.GetSampleStore(storageResourceStore);
            embeddedSampleStore ??= audioManager.GetSampleStore(embeddedResourceStore);
        }

        private Sample? tryGetSample(string path)
        {
            try
            {
                ensureSampleStores();

                Sample? sample = null;

                if (storageSampleStore != null)
                {
                    string fileName = Path.GetFileName(path);
                    if (!string.IsNullOrEmpty(fileName))
                    {
                        sample = storageSampleStore.Get($"{userMetronomeDirectory}/{fileName}");

                        if (sample == null)
                        {
                            string? stem = Path.GetFileNameWithoutExtension(fileName);
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
                Logger.Log($"[Settings] Error loading metronome preview sample '{path}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                return null;
            }
        }

        private void stopPreviewChannel()
        {
            if (metronomePreviewChannel == null)
                return;

            metronomePreviewChannel.Stop();
            metronomePreviewChannel = null;
        }

        private sealed partial class InlineDropdown<T> : BeatSight.Game.UI.Components.Dropdown<T>
        {
            public InlineDropdown(float maxHeight)
            {
                MenuMaxHeight = maxHeight;
            }
        }
    }
}
