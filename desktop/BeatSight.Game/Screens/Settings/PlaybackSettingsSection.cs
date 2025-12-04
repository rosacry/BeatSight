// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from SettingsScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.2

using System;
using BeatSight.Game.Configuration;
using BeatSight.Game.Customization;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Settings
{
    /// <summary>
    /// Settings section for playback-related options including lane view,
    /// background dim/blur, and kick lane mode.
    /// </summary>
    public partial class PlaybackSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;
        private readonly GameHost host;

        public PlaybackSettingsSection(BeatSightConfigManager config, GameHost host, Container dropdownOverlay, SettingsTooltipOverlay tooltipOverlay)
            : base("Playback Settings", dropdownOverlay, tooltipOverlay)
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
                    CreateEnumDropdown(
                        "Lane View",
                        config.GetBindable<LaneViewMode>(BeatSightSetting.LaneViewMode),
                        "Switch between classic 2D lanes and the new 3D runway view.",
                        formatLaneViewMode
                    ),
                    CreateEnumDropdown(
                        "Lane Preset",
                        config.GetBindable<LanePreset>(BeatSightSetting.LanePreset),
                        "Choose a fixed lane count or let BeatSight match your detected drum kit automatically.",
                        formatLanePreset
                    ),
                    CreateSlider(
                        "Background Dim",
                        config.GetBindable<double>(BeatSightSetting.BackgroundDim),
                        0,
                        1,
                        0.01,
                        "How much to dim the background during playback (0% = bright, 100% = dark).",
                        valueFormatter: PercentageFormatter()
                    ),
                    CreateSlider(
                        "Background Blur",
                        config.GetBindable<double>(BeatSightSetting.BackgroundBlur),
                        0,
                        1,
                        0.01,
                        "Amount of blur applied to the background during playback.",
                        valueFormatter: PercentageFormatter()
                    ),
                    CreateEnumDropdown(
                        "Kick Lane Mode",
                        config.GetBindable<KickLaneMode>(BeatSightSetting.KickLaneMode),
                        "Switch between a shared timing line or a dedicated lane for kick hits.",
                        formatKickLaneMode
                    ),
                    createOpenSongsFolderButton(),
                    createResetSettingsButton()
                }
            };
        }

        private SettingItem createOpenSongsFolderButton()
        {
            var openButton = new BeatSightButton
            {
                Width = 220,
                Height = 36,
                Text = "Open Songs Folder",
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Action = () => SettingsScreen.OpenDirectoryExternally(host, UserAssetDirectories.Songs)
            };

            var control = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = openButton
            };

            return CreateSettingItem(
                "Songs Library",
                "Open the folder where your beatmaps are stored. Drop .bsm files here to add new songs.",
                control);
        }

        private SettingItem createResetSettingsButton()
        {
            var defaultColour = new Color4(176, 70, 70, 255);
            var confirmColour = new Color4(204, 98, 98, 255);

            var resetButton = new BeatSightButton
            {
                Width = 220,
                Height = 36,
                Text = "Reset All Settings",
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight
            };

            // Override the default theme colour applied in Load
            resetButton.OnLoadComplete += _ => resetButton.BackgroundColour = defaultColour;

            bool awaitingConfirmation = false;

            resetButton.Action = () =>
            {
                if (!awaitingConfirmation)
                {
                    awaitingConfirmation = true;
                    resetButton.Text = "Click again to confirm";
                    resetButton.BackgroundColour = confirmColour;
                    return;
                }

                awaitingConfirmation = false;
                resetButton.Text = "Reset All Settings";
                resetButton.BackgroundColour = defaultColour;

                config.ResetToDefaults();

                // Apply smart defaults for resolution after reset
                try
                {
                    var display = host.Window?.PrimaryDisplay;
                    if (display != null)
                    {
                        var bounds = display.Bounds;
                        int targetWidth = Math.Max(1280, (int)(bounds.Width * 0.8f));
                        int targetHeight = Math.Max(720, (int)(bounds.Height * 0.8f));

                        targetWidth = Math.Min(targetWidth, bounds.Width);
                        targetHeight = Math.Min(targetHeight, bounds.Height);

                        config.SetValue(BeatSightSetting.WindowWidth, targetWidth);
                        config.SetValue(BeatSightSetting.WindowHeight, targetHeight);
                    }
                }
                catch (Exception e)
                {
                    Logger.Log($"Failed to detect screen resolution on reset: {e.Message}", LoggingTarget.Runtime, LogLevel.Important);
                }

                Logger.Log("[Settings] User reset configuration to defaults.", LoggingTarget.Runtime, LogLevel.Important);
            };

            var control = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = resetButton
            };

            return CreateSettingItem(
                "Reset All Settings",
                "Restore every setting to the factory defaults. This affects audio, graphics, and gameplay preferences.",
                control);
        }

        private static string formatLaneViewMode(LaneViewMode mode) => mode switch
        {
            LaneViewMode.TwoDimensional => "2D",
            LaneViewMode.ThreeDimensional => "3D",
            _ => mode.ToString()
        };

        private static string formatLanePreset(LanePreset preset) => preset switch
        {
            LanePreset.DrumFourLane => "4 lanes",
            LanePreset.DrumFiveLane => "5 lanes",
            LanePreset.DrumSixLane => "6 lanes",
            LanePreset.DrumSevenLane => "7 lanes",
            LanePreset.DrumEightLane => "8 lanes",
            LanePreset.DrumNineLane => "9 lanes",
            LanePreset.AutoDynamic => "Auto (match drum kit)",
            _ => preset.ToString()
        };

        private static string formatKickLaneMode(KickLaneMode mode) => mode switch
        {
            KickLaneMode.GlobalLine => "Global Line",
            KickLaneMode.DedicatedLane => "Dedicated Line",
            _ => mode.ToString()
        };
    }
}
