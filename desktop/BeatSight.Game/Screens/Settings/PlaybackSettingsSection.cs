// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from SettingsScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.2

using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Customization;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
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
        private Bindable<string> laneProfileJson = null!;
        private readonly List<LaneInfo> editableLaneProfile = new();
        private int laneProfileEditIndex;
        private bool suppressLaneProfileFieldSync;
        private bool suppressLaneProfileBindableSync;
        private SpriteText laneProfileNameText = null!;
        private SpriteText laneProfileShortNameText = null!;
        private BeatSightTextBox laneProfileColorInput = null!;
        private BeatSightButton laneProfilePrevButton = null!;
        private BeatSightButton laneProfileNextButton = null!;
        private BeatSightButton laneProfileApplyButton = null!;
        private BeatSightButton laneProfileMoveLeftButton = null!;
        private BeatSightButton laneProfileMoveRightButton = null!;
        private SpriteText laneProfileSelectionText = null!;
        private Box laneProfileColorPreview = null!;
        private SettingItem laneProfileSettingItem = null!;

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
                    createLaneProfileEditor(),
                    CreateEnumDropdown(
                        "Sheet Count-in Guides",
                        config.GetBindable<ManuscriptCountInGuideMode>(BeatSightSetting.ManuscriptCountInGuideMode),
                        "Control manuscript playhead count-in guide density: hide them, show a compact beat guide, or keep full subdivision guides.",
                        formatManuscriptCountInGuideMode
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

        private SettingItem createLaneProfileEditor()
        {
            laneProfileJson = config.GetBindable<string>(BeatSightSetting.LaneProfileJson);

            laneProfileSelectionText = new SpriteText
            {
                Text = "Lane 1",
                Font = BeatSightFont.Label(14f),
                Colour = UITheme.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            laneProfileNameText = new SpriteText
            {
                Text = "-",
                Font = BeatSightFont.Label(12f),
                Colour = UITheme.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            laneProfileShortNameText = new SpriteText
            {
                Text = "-",
                Font = BeatSightFont.Label(12f),
                Colour = UITheme.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            laneProfileColorInput = new BeatSightTextBox
            {
                Width = 96,
                Height = 32,
                PlaceholderText = "#RRGGBB",
                TextSize = 12f
            };

            laneProfileColorPreview = new Box
            {
                Size = new Vector2(22, 22),
                Colour = UITheme.SurfaceAlt
            };

            laneProfilePrevButton = createLaneProfileButton("<", () => stepLaneProfileSelection(-1), 34);
            laneProfileNextButton = createLaneProfileButton(">", () => stepLaneProfileSelection(1), 34);
            laneProfileApplyButton = createLaneProfileButton("Apply", applyLaneProfileEdits, 64);
            laneProfileMoveLeftButton = createLaneProfileButton("Move -", () => moveLaneProfileLane(-1), 64);
            laneProfileMoveRightButton = createLaneProfileButton("Move +", () => moveLaneProfileLane(1), 64);

            var laneSelectorRow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(6, 0),
                Children = new Drawable[]
                {
                    laneProfilePrevButton,
                    new Container
                    {
                        Width = 168,
                        Height = 32,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Child = laneProfileSelectionText
                    },
                    laneProfileNextButton,
                    laneProfileApplyButton
                }
            };

            var laneEditorRow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(6, 0),
                Children = new Drawable[]
                {
                    createLaneProfileReadOnlyField(148, laneProfileNameText),
                    createLaneProfileReadOnlyField(88, laneProfileShortNameText),
                    laneProfileColorInput,
                    new Container
                    {
                        Size = new Vector2(30, 32),
                        Child = new Container
                        {
                            Size = new Vector2(22, 22),
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Masking = true,
                            CornerRadius = 6,
                            Children = new Drawable[]
                            {
                                laneProfileColorPreview,
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = Color4.White,
                                    Alpha = 0.08f
                                }
                            }
                        }
                    }
                }
            };

            var laneActionsRow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(6, 0),
                Children = new Drawable[]
                {
                    laneProfileMoveLeftButton,
                    laneProfileMoveRightButton
                }
            };

            var laneProfileControl = new FillFlowContainer
            {
                Width = 500,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    laneSelectorRow,
                    laneEditorRow,
                    laneActionsRow
                }
            };

            laneProfileColorInput.Current.BindValueChanged(_ =>
            {
                if (suppressLaneProfileFieldSync)
                    return;
            });

            laneProfileJson.BindValueChanged(_ =>
            {
                if (suppressLaneProfileBindableSync)
                    return;

                loadLaneProfileFromSettings();
                refreshLaneProfileEditorControls();
                laneProfileSettingItem?.SetModified(!laneProfileJson.IsDefault);
            }, true);

            laneProfileSettingItem = CreateSettingItem(
                "Lane Profile",
                "Adjust default lane colors and lane order only. Lane names and lane count come from beatmap configuration.",
                laneProfileControl);
            laneProfileSettingItem.SetDefaultValue("Factory lane profile");
            laneProfileSettingItem.SetModified(!laneProfileJson.IsDefault);
            return laneProfileSettingItem;
        }

        private BeatSightButton createLaneProfileButton(string text, Action action, float width)
            => new BeatSightButton
            {
                Width = width,
                Height = 32,
                Text = text,
                FontSize = 10.8f,
                Action = action
            };

        private Container createLaneProfileReadOnlyField(float width, SpriteText contentText)
            => new Container
            {
                Width = width,
                Height = 32,
                Masking = true,
                CornerRadius = 6,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.SurfaceAlt
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding
                        {
                            Horizontal = 8,
                            Vertical = 6
                        },
                        Child = contentText
                    }
                }
            };

        private void loadLaneProfileFromSettings()
        {
            editableLaneProfile.Clear();
            editableLaneProfile.AddRange(LaneManagement.DeserializeLaneProfile(laneProfileJson.Value, fallbackLaneCount: 7));
            laneProfileEditIndex = Math.Clamp(laneProfileEditIndex, 0, Math.Max(0, editableLaneProfile.Count - 1));
        }

        private void refreshLaneProfileEditorControls()
        {
            if (editableLaneProfile.Count == 0)
                loadLaneProfileFromSettings();

            if (editableLaneProfile.Count == 0)
                return;

            laneProfileEditIndex = Math.Clamp(laneProfileEditIndex, 0, editableLaneProfile.Count - 1);
            var lane = editableLaneProfile[laneProfileEditIndex];

            suppressLaneProfileFieldSync = true;
            laneProfileSelectionText.Text = $"Lane {laneProfileEditIndex + 1}: {lane.ShortName ?? lane.Name ?? "Lane"}";
            laneProfileNameText.Text = lane.Name ?? string.Empty;
            laneProfileShortNameText.Text = lane.ShortName ?? string.Empty;
            laneProfileColorInput.Current.Value = lane.ColorHex ?? string.Empty;
            suppressLaneProfileFieldSync = false;

            laneProfileColorPreview.Colour = LaneManagement.TryParseColorHex(lane.ColorHex, out var laneColor)
                ? laneColor
                : UITheme.SurfaceAlt;

            bool canMoveLeft = laneProfileEditIndex > 0;
            laneProfileMoveLeftButton.Enabled.Value = canMoveLeft;
            laneProfileMoveLeftButton.Alpha = canMoveLeft ? 1f : 0.56f;

            bool canMoveRight = laneProfileEditIndex < editableLaneProfile.Count - 1;
            laneProfileMoveRightButton.Enabled.Value = canMoveRight;
            laneProfileMoveRightButton.Alpha = canMoveRight ? 1f : 0.56f;
        }

        private void stepLaneProfileSelection(int delta)
        {
            if (editableLaneProfile.Count == 0)
                return;

            laneProfileEditIndex = Math.Clamp(laneProfileEditIndex + delta, 0, editableLaneProfile.Count - 1);
            refreshLaneProfileEditorControls();
        }

        private void applyLaneProfileEdits()
        {
            if (editableLaneProfile.Count == 0)
                return;

            if (!LaneManagement.IsLaneEditAllowed(LaneEditScope.Settings, LaneEditOperation.Recolor))
            {
                return;
            }

            var lane = editableLaneProfile[laneProfileEditIndex];
            string colorText = laneProfileColorInput.Current.Value?.Trim() ?? string.Empty;

            if (!string.IsNullOrWhiteSpace(colorText) && !LaneManagement.TryParseColorHex(colorText, out _))
            {
                Logger.Log("[Settings] Ignoring invalid lane color input. Expected #RRGGBB.", LoggingTarget.Runtime, LogLevel.Important);
                refreshLaneProfileEditorControls();
                return;
            }

            lane.ColorHex = colorText;
            commitLaneProfileChanges();
        }

        private void moveLaneProfileLane(int delta)
        {
            if (editableLaneProfile.Count <= 1 || delta == 0)
                return;

            if (!LaneManagement.IsLaneEditAllowed(LaneEditScope.Settings, LaneEditOperation.Reorder))
                return;

            int fromIndex = Math.Clamp(laneProfileEditIndex, 0, editableLaneProfile.Count - 1);
            int toIndex = Math.Clamp(fromIndex + delta, 0, editableLaneProfile.Count - 1);
            if (fromIndex == toIndex)
                return;

            var lane = editableLaneProfile[fromIndex];
            editableLaneProfile.RemoveAt(fromIndex);
            editableLaneProfile.Insert(toIndex, lane);
            laneProfileEditIndex = toIndex;
            commitLaneProfileChanges();
        }

        private void commitLaneProfileChanges()
        {
            string serialized = LaneManagement.SerializeLaneProfile(editableLaneProfile);
            editableLaneProfile.Clear();
            editableLaneProfile.AddRange(LaneManagement.DeserializeLaneProfile(serialized, fallbackLaneCount: 7));
            laneProfileEditIndex = Math.Clamp(laneProfileEditIndex, 0, Math.Max(0, editableLaneProfile.Count - 1));

            suppressLaneProfileBindableSync = true;
            laneProfileJson.Value = serialized;
            suppressLaneProfileBindableSync = false;

            laneProfileSettingItem?.SetModified(!laneProfileJson.IsDefault);
            refreshLaneProfileEditorControls();
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

        private static string formatManuscriptCountInGuideMode(ManuscriptCountInGuideMode mode) => mode switch
        {
            ManuscriptCountInGuideMode.Off => "Off",
            ManuscriptCountInGuideMode.Compact => "Compact",
            ManuscriptCountInGuideMode.Full => "Full",
            _ => mode.ToString()
        };
    }
}
