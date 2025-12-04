// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from SettingsScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.2

using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Linq;
using BeatSight.Game.Configuration;
using BeatSight.Game.Customization;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Overlays;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Platform;
using osuTK;

namespace BeatSight.Game.Screens.Settings
{
    /// <summary>
    /// Settings section for graphics and display configuration including
    /// monitor selection, resolution, fullscreen mode, and visual effects.
    /// </summary>
    public partial class GraphicsSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;
        private readonly GameHost host;
        private readonly UIScaleWizard uiScaleWizard;
        private readonly Action openSkinEditorAction;
        private Bindable<int>? windowWidth;
        private Bindable<int>? windowHeight;
        private Bindable<bool>? windowFullscreen;
        private Bindable<int>? windowDisplay;
        private SettingsDropdown<MonitorChoice>? monitorDropdown;
        private SettingsDropdown<ResolutionOptionChoice>? resolutionDropdown;
        private MonitorChoice[] monitorChoices = Array.Empty<MonitorChoice>();
        private ResolutionOptionChoice[] resolutionChoices = Array.Empty<ResolutionOptionChoice>();
        private bool suppressMonitorSync;
        private bool suppressResolutionSync;
        private bool monitorRefreshScheduled;
        private bool resolutionRefreshScheduled;

        public GraphicsSettingsSection(BeatSightConfigManager config, GameHost host, Container dropdownOverlay, SettingsTooltipOverlay tooltipOverlay, UIScaleWizard uiScaleWizard, Action openSkinEditor)
            : base("Graphics Settings", dropdownOverlay, tooltipOverlay)
        {
            this.config = config;
            this.host = host;
            this.uiScaleWizard = uiScaleWizard;
            this.openSkinEditorAction = openSkinEditor;
        }

        protected override Drawable createContent()
        {
            windowWidth ??= config.GetBindable<int>(BeatSightSetting.WindowWidth);
            windowHeight ??= config.GetBindable<int>(BeatSightSetting.WindowHeight);
            windowFullscreen ??= config.GetBindable<bool>(BeatSightSetting.WindowFullscreen);
            windowDisplay ??= config.GetBindable<int>(BeatSightSetting.WindowDisplayIndex);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 12),
                Children = new Drawable[]
                {
                    createMonitorSetting(),
                    createResolutionSetting(),
                    CreateCheckbox(
                        "Fullscreen Mode",
                        windowFullscreen!,
                        "Toggle fullscreen rendering. When off, BeatSight uses the resolution specified above."
                    ),
                    CreateSlider(
                        "Background Opacity",
                        config.GetBindable<double>(BeatSightSetting.GlobalBackgroundOpacity),
                        0.0, 1.0, 0.01,
                        "Adjust the visibility of the background particles.",
                        val => $"{val:P0}",
                        toggleBindable: config.GetBindable<bool>(BeatSightSetting.ShowGlobalBackground),
                        toggleMode: SliderToggleMode.ZeroValue
                    ),
                    createFrameLimiterSetting(),
                    CreateEnumDropdown(
                        "Skin",
                        config.GetBindable<NoteSkinOption>(BeatSightSetting.NoteSkin),
                        "Switch the appearance of notes between available skins.",
                        enableSearch: true
                    ),
                    createSkinManagementSetting(),
                    CreateCheckbox(
                        "Show FPS Counter",
                        config.GetBindable<bool>(BeatSightSetting.ShowFpsCounter),
                        "Display frames per second in the corner."
                    ),
                    CreateSettingItem(
                        "UI Scale",
                        "Adjust the size of all UI elements.",
                        new BeatSightButton
                        {
                            Text = "Adjust...",
                            Size = new Vector2(100, 30),
                            Anchor = Anchor.CentreRight,
                            Origin = Anchor.CentreRight,
                            Action = () => uiScaleWizard.Show()
                        }
                    ),
                    CreateCheckbox(
                        "Particle Effects",
                        config.GetBindable<bool>(BeatSightSetting.ShowParticleEffects),
                        "Show burst animations when notes are triggered."
                    ),
                    CreateCheckbox(
                        "Glow Effects",
                        config.GetBindable<bool>(BeatSightSetting.ShowGlowEffects),
                        "Show glowing effects with additive blending."
                    ),
                    CreateCheckbox(
                        "Hit Burst Animations",
                        config.GetBindable<bool>(BeatSightSetting.ShowHitBurstAnimations),
                        "Show explosion animations on triggered notes."
                    )
                }
            };
        }

        private SettingItem createSkinManagementSetting()
        {
            var openButton = new BeatSightButton
            {
                Width = 160,
                Height = 32,
                Text = "Open Skins Folder",
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Action = () => SettingsScreen.OpenDirectoryExternally(host, UserAssetDirectories.Skins)
            };

            var editorButton = new BeatSightButton
            {
                Width = 160,
                Height = 32,
                Text = "Skin Editor",
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Action = openSkinEditorAction
            };

            var control = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Children = new Drawable[] { openButton, editorButton }
            };

            return CreateSettingItem(
                "Skin Tools",
                "Manage installed skins or prepare to create your own. The editor toggle is placeholder until development finishes.",
                control);
        }

        private SettingItem createMonitorSetting()
        {
            monitorDropdown = new SettingsDropdown<MonitorChoice>(dropdown_menu_max_height)
            {
                Width = 220,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight
            };

            monitorDropdown.OverlayLayer = DropdownOverlay;
            monitorDropdown.ScrollViewport = ScrollViewport;
            monitorDropdown.Current.BindValueChanged(e =>
            {
                if (suppressMonitorSync || windowDisplay == null)
                    return;

                if (windowDisplay.Value != e.NewValue.Index)
                    windowDisplay.Value = e.NewValue.Index;
            });

            windowDisplay?.BindValueChanged(_ => scheduleMonitorRefresh(), true);

            updateMonitorDropdownItems();

            var setting = CreateSettingItem(
                "Monitor",
                "Choose which display BeatSight launches on.",
                monitorDropdown);

            if (windowDisplay != null)
            {
                setting.SetDefaultValue("Primary");
                windowDisplay.BindValueChanged(_ => setting.SetModified(!windowDisplay.IsDefault), true);
            }

            return setting;
        }

        private SettingItem createResolutionSetting()
        {
            resolutionDropdown = new SettingsDropdown<ResolutionOptionChoice>(dropdown_menu_max_height)
            {
                Width = 220,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight
            };

            resolutionDropdown.OverlayLayer = DropdownOverlay;
            resolutionDropdown.ScrollViewport = ScrollViewport;
            resolutionDropdown.Current.BindValueChanged(e =>
            {
                if (suppressResolutionSync || windowWidth == null || windowHeight == null)
                    return;

                if (windowWidth.Value != e.NewValue.Width)
                    windowWidth.Value = e.NewValue.Width;
                if (windowHeight.Value != e.NewValue.Height)
                    windowHeight.Value = e.NewValue.Height;
            });

            windowWidth?.BindValueChanged(_ => scheduleResolutionRefresh(), true);
            windowHeight?.BindValueChanged(_ => scheduleResolutionRefresh(), true);

            updateResolutionDropdownItems();

            var setting = CreateSettingItem(
                "Resolution",
                "Choose the render resolution. Fullscreen selects the display mode; windowed uses it for the window size.",
                resolutionDropdown);

            void updateModified()
            {
                bool modified = (windowWidth != null && !windowWidth.IsDefault) || (windowHeight != null && !windowHeight.IsDefault);
                setting.SetModified(modified);
            }

            if (windowWidth != null) windowWidth.BindValueChanged(_ => updateModified(), true);
            if (windowHeight != null) windowHeight.BindValueChanged(_ => updateModified(), true);

            setting.SetDefaultValue("Native");

            return setting;
        }

        private SettingItem createFrameLimiterSetting()
        {
            return CreateEnumDropdown(
                "Frame Limiter",
                config.GetBindable<FrameLimiterMode>(BeatSightSetting.FrameLimiter),
                "Limit the frame rate to reduce power consumption or latency.",
                val =>
                {
                    switch (val)
                    {
                        case FrameLimiterMode.VSync: return "VSync";
                        case FrameLimiterMode.Twice: return "2x refresh rate";
                        case FrameLimiterMode.FourTimes: return "4x refresh rate";
                        case FrameLimiterMode.EightTimes: return "8x refresh rate";
                        case FrameLimiterMode.BasicallyUnlimited: return "Basically Unlimited";
                        default: return val.ToString();
                    }
                }
            );
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (host.Window != null)
                host.Window.DisplaysChanged += onDisplaysChanged;

            updateMonitorDropdownItems();
            updateResolutionDropdownItems();
        }

        protected override void Dispose(bool isDisposing)
        {
            if (host.Window != null)
                host.Window.DisplaysChanged -= onDisplaysChanged;

            base.Dispose(isDisposing);
        }

        private void scheduleMonitorRefresh()
        {
            if (monitorRefreshScheduled)
                return;

            monitorRefreshScheduled = true;
            Schedule(() =>
            {
                monitorRefreshScheduled = false;
                updateMonitorDropdownItems();
            });
        }

        private void scheduleResolutionRefresh()
        {
            if (resolutionRefreshScheduled)
                return;

            resolutionRefreshScheduled = true;
            Schedule(() =>
            {
                resolutionRefreshScheduled = false;
                updateResolutionDropdownItems();
            });
        }

        private void updateMonitorDropdownItems()
        {
            if (monitorDropdown == null)
                return;

            var displays = host.Window?.Displays ?? ImmutableArray<Display>.Empty;
            monitorChoices = displays.Length == 0
                ? new[] { new MonitorChoice(0, "Primary Display") }
                : displays.Select(d => new MonitorChoice(d.Index, $"{d.Index + 1}: {d.Name}"))
                          .OrderBy(choice => choice.Index)
                          .ToArray();
            if (monitorChoices.Length == 0)
                monitorChoices = new[] { new MonitorChoice(0, "Primary Display") };

            suppressMonitorSync = true;
            try
            {
                monitorDropdown.Items = monitorChoices;

                int targetIndex = windowDisplay?.Value ?? 0;
                var selection = monitorChoices.FirstOrDefault(choice => choice.Index == targetIndex);
                if (!selection.IsValid)
                    selection = monitorChoices[0];

                monitorDropdown.Current.Value = selection;
            }
            finally
            {
                suppressMonitorSync = false;
            }

            updateResolutionDropdownItems();
        }

        private void updateResolutionDropdownItems()
        {
            if (resolutionDropdown == null || windowWidth == null || windowHeight == null)
                return;

            bool isFullscreen = windowFullscreen?.Value == true;
            var display = getDisplayByIndex(windowDisplay?.Value ?? 0);

            var modeSizes = new HashSet<(int Width, int Height)>();

            if (display is Display displayValue)
            {
                foreach (var mode in displayValue.DisplayModes)
                {
                    var size = mode.Size;

                    if (size.Width < 800 || size.Height < 600)
                        continue;

                    modeSizes.Add((size.Width, size.Height));
                }
            }

            if (modeSizes.Count == 0)
            {
                modeSizes.Add((1280, 720));
                modeSizes.Add((1600, 900));
                modeSizes.Add((1920, 1080));
            }

            modeSizes.Add((Math.Max(800, windowWidth.Value), Math.Max(600, windowHeight.Value)));
            if (isFullscreen && display is Display fullscreenDisplay)
                modeSizes.Add((fullscreenDisplay.Bounds.Width, fullscreenDisplay.Bounds.Height));

            resolutionChoices = modeSizes
                .Select(size => new ResolutionOptionChoice(
                    size.Width,
                    size.Height,
                    !displayHasResolution(display, size) && size.Width == windowWidth.Value && size.Height == windowHeight.Value))
                .OrderBy(choice => choice.Width)
                .ThenBy(choice => choice.Height)
                .ToArray();

            suppressResolutionSync = true;
            bool originalDisabled = resolutionDropdown.Current.Disabled;
            bool targetDisabledState = originalDisabled;
            try
            {
                if (resolutionDropdown.Current.Disabled)
                    resolutionDropdown.Current.Disabled = false;

                resolutionDropdown.Items = resolutionChoices;

                var selection = resolutionChoices.FirstOrDefault(choice => choice.Width == windowWidth.Value && choice.Height == windowHeight.Value);
                if (!selection.IsValid && isFullscreen && display is Display displayForFullscreen)
                {
                    var displaySelection = resolutionChoices.FirstOrDefault(choice => choice.Width == displayForFullscreen.Bounds.Width && choice.Height == displayForFullscreen.Bounds.Height);
                    if (displaySelection.IsValid)
                        selection = displaySelection;
                }
                if (!selection.IsValid)
                    selection = resolutionChoices[^1];

                resolutionDropdown.Current.Value = selection;
            }
            finally
            {
                resolutionDropdown.Current.Disabled = targetDisabledState;
                suppressResolutionSync = false;
            }
        }

        private Display? getDisplayByIndex(int index)
        {
            var displays = host.Window?.Displays ?? ImmutableArray<Display>.Empty;
            if (displays.Length == 0)
                return null;

            foreach (var display in displays)
            {
                if (display.Index == index)
                    return display;
            }

            return displays[0];
        }

        private static bool displayHasResolution(Display? display, (int Width, int Height) size)
        {
            if (display is not Display displayValue)
                return false;

            foreach (var mode in displayValue.DisplayModes)
            {
                if (mode.Size.Width == size.Width && mode.Size.Height == size.Height)
                    return true;
            }

            return false;
        }

        private void onDisplaysChanged(IEnumerable<Display> _)
        {
            scheduleMonitorRefresh();
        }

        private readonly struct MonitorChoice : IEquatable<MonitorChoice>
        {
            public MonitorChoice(int index, string label)
            {
                Index = index;
                Label = label;
            }

            public int Index { get; }
            public string Label { get; }
            public bool IsValid => !string.IsNullOrEmpty(Label);
            public bool Equals(MonitorChoice other) => Index == other.Index && Label == other.Label;
            public override bool Equals(object? obj) => obj is MonitorChoice other && Equals(other);
            public override int GetHashCode() => HashCode.Combine(Index, Label);
            public override string ToString() => Label;
        }

        private readonly struct ResolutionOptionChoice : IEquatable<ResolutionOptionChoice>
        {
            public ResolutionOptionChoice(int width, int height, bool isCustom)
            {
                Width = width;
                Height = height;
                IsCustom = isCustom;
            }

            public int Width { get; }
            public int Height { get; }
            public bool IsCustom { get; }
            public bool IsValid => Width > 0 && Height > 0;

            public bool Equals(ResolutionOptionChoice other) => Width == other.Width && Height == other.Height;
            public override bool Equals(object? obj) => obj is ResolutionOptionChoice other && Equals(other);
            public override int GetHashCode() => HashCode.Combine(Width, Height);
            public override string ToString()
            {
                string label = $"{Width} x {Height}";
                return IsCustom ? label + " (Custom)" : label;
            }
        }
    }
}
