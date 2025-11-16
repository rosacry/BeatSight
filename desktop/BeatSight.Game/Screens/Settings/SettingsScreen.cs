using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Drawing;
using BeatSight.Game.Audio;
using BeatSight.Game.Customization;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Audio;
using osu.Framework.Audio.Sample;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.IO.Stores;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Settings
{
    public partial class SettingsScreen : Screen
    {
        private BeatSightConfigManager config = null!;
        private GameHost host = null!;

        private Container contentContainer = null!;
        private SettingsSection? currentSection;
        private BackButton backButton = null!;
        private readonly Dictionary<SettingsCategory, SettingsButton> sectionButtons = new();
        private SettingsCategory currentCategory = SettingsCategory.Playback;
        private Container dropdownOverlay = null!;
        private Container overlayRoot = null!;

        private enum SettingsCategory
        {
            Playback,
            Audio,
            Graphics
        }

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager configManager, GameHost gameHost)
        {
            config = configManager;
            host = gameHost;

            backButton = new BackButton
            {
                Action = () => this.Exit(),
                Margin = BackButton.DefaultMargin,
                Depth = -10
            };

            dropdownOverlay = new Container
            {
                RelativeSizeAxes = Axes.Both,
                AlwaysPresent = true,
                Masking = false,
                Depth = -5
            };

            overlayRoot = new Container
            {
                RelativeSizeAxes = Axes.Both,
                AlwaysPresent = true,
                Depth = -10,
                Children = new Drawable[]
                {
                    dropdownOverlay,
                    backButton
                }
            };

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Background,
                    Depth = 2 // Background at the very back
                },
                new GridContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Depth = 1, // Render below dropdowns
                    RowDimensions = new[]
                    {
                        new Dimension(GridSizeMode.Absolute, 80),
                        new Dimension()
                    },
                    Content = new[]
                    {
                        new Drawable[] { createHeader() },
                        new Drawable[]
                        {
                            new GridContainer
                            {
                                RelativeSizeAxes = Axes.Both,
                                ColumnDimensions = new[]
                                {
                                    new Dimension(GridSizeMode.Absolute, 250),
                                    new Dimension()
                                },
                                Content = new[]
                                {
                                    new Drawable[]
                                    {
                                        createSidebar(),
                                        contentContainer = new Container
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Padding = UITheme.ScreenPadding
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                overlayRoot
            };


            // Show playback settings by default
            showSection(SettingsCategory.Playback);
        }


        private Drawable createSidebar()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.SurfaceAlt
                    },
                    new BasicScrollContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        ClampExtension = 0,
                        Child = new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 4),
                            Padding = new MarginPadding(20),
                            Children = new Drawable[]
                            {
                                createSectionButton(SettingsCategory.Playback, "Playback"),
                                createSectionButton(SettingsCategory.Audio, "Audio"),
                                createSectionButton(SettingsCategory.Graphics, "Graphics")
                            }
                        }
                    }
                }
            };
        }

        private SettingsButton createSectionButton(SettingsCategory category, string text)
        {
            var button = new SettingsButton(text, () => showSection(category));
            sectionButtons[category] = button;
            if (category == currentCategory)
                button.SetSelected(true);
            return button;
        }

        private void showSection(SettingsCategory category)
        {
            if (currentCategory == category && currentSection != null && contentContainer.Child == currentSection)
                return;

            // Ensure any dropdown menus currently hosted in the shared overlay are disposed
            // before tearing down the owning section. This prevents orphaned menus from
            // lingering at the screen origin when the source control disappears.
            dropdownOverlay.Clear(disposeChildren: true);

            currentCategory = category;
            currentSection = createSectionInstance(category);
            contentContainer.Child = currentSection;

            foreach (var entry in sectionButtons)
                entry.Value.SetSelected(entry.Key == category);
        }

        private SettingsSection createSectionInstance(SettingsCategory category)
        {
            switch (category)
            {
                case SettingsCategory.Playback:
                    return new PlaybackSettingsSection(config, dropdownOverlay);
                case SettingsCategory.Audio:
                    return new AudioSettingsSection(config, host, dropdownOverlay);
                case SettingsCategory.Graphics:
                    return new GraphicsSettingsSection(config, host, dropdownOverlay);
                default:
                    throw new ArgumentOutOfRangeException(nameof(category), category, null);
            }
        }

        private Drawable createHeader()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 30 },
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "Settings",
                                Font = new FontUsage(size: 32, weight: "Bold"),
                                Colour = UITheme.TextPrimary,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre
                            }
                        }
                    }
                }
            };
        }

        internal static void OpenDirectoryExternally(GameHost host, string relativePath)
        {
            try
            {
                string fullPath = host.Storage.GetFullPath(relativePath);
                Directory.CreateDirectory(fullPath);
                launchFileBrowser(fullPath);
            }
            catch (Exception ex)
            {
                Logger.Log($"[Settings] Failed to open directory '{relativePath}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private static void launchFileBrowser(string path)
        {
            try
            {
                if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = "explorer.exe",
                        Arguments = $"\"{path}\"",
                        UseShellExecute = true
                    });
                }
                else if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
                {
                    Process.Start("open", path);
                }
                else
                {
                    Process.Start("xdg-open", path);
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"[Settings] Failed to launch file browser for '{path}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
                this.Exit();
                return true;
            }

            return base.OnKeyDown(e);
        }

        private partial class SettingsButton : CompositeDrawable
        {
            private readonly Box background;
            private readonly Box accentBar;
            private readonly SpriteText label;
            private readonly Action action;
            private bool isSelected;

            public SettingsButton(string text, Action action)
            {
                this.action = action;

                RelativeSizeAxes = Axes.X;
                Height = 50;
                Masking = true;
                CornerRadius = 8;

                InternalChildren = new Drawable[]
                {
                    accentBar = new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 6,
                        Colour = UITheme.AccentPrimary,
                        Alpha = 0,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    },
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    },
                    label = new SpriteText
                    {
                        Text = text,
                        Font = new FontUsage(size: 20),
                        Colour = UITheme.TextSecondary,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Padding = new MarginPadding { Left = 24 }
                    }
                };
            }

            public void SetSelected(bool selected)
            {
                if (isSelected == selected)
                {
                    updateVisualState();
                    return;
                }

                isSelected = selected;
                updateVisualState();
            }

            protected override bool OnClick(ClickEvent e)
            {
                action?.Invoke();
                return true;
            }

            protected override bool OnHover(HoverEvent e)
            {
                updateVisualState(true);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                base.OnHoverLost(e);
                updateVisualState();
            }

            private void updateVisualState(bool hovering = false)
            {
                Colour4 baseColour = isSelected ? UITheme.Emphasise(UITheme.Surface, 1.18f) : UITheme.Surface;

                if (hovering)
                    baseColour = UITheme.Emphasise(baseColour, 1.06f);

                background.FadeColour(baseColour, 200, Easing.OutQuint);
                accentBar.FadeTo(isSelected ? 1f : 0f, 200, Easing.OutQuint);
                label.FadeColour(isSelected ? UITheme.TextPrimary : UITheme.TextSecondary, 200, Easing.OutQuint);
                this.ScaleTo(hovering ? 1.02f : 1f, 200, Easing.OutQuint);
            }
        }
    }

    public abstract partial class SettingsSection : CompositeDrawable
    {
        private readonly string title;
        protected Container DropdownOverlay { get; }
        private BasicScrollContainer sectionScrollContainer = null!;
        private FillFlowContainer contentFlow = null!;
        private FillFlowContainer sectionBody = null!;
        protected const float dropdown_menu_max_height = 240;
        protected BasicScrollContainer ScrollViewport => sectionScrollContainer;

        protected SettingsSection(string title, Container dropdownOverlay)
        {
            this.title = title;
            RelativeSizeAxes = Axes.Both;
            DropdownOverlay = dropdownOverlay;
        }

        [BackgroundDependencyLoader]
        private void loadSection()
        {
            contentFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 30)
            };

            sectionBody = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 30)
            };

            contentFlow.AddRange(new Drawable[]
            {
                new SpriteText
                {
                    Text = title,
                    Font = new FontUsage(size: 28, weight: "Bold"),
                    Colour = UITheme.TextPrimary,
                    Margin = new MarginPadding { Bottom = 10 }
                },
                sectionBody
            });

            sectionScrollContainer = new BasicScrollContainer
            {
                RelativeSizeAxes = Axes.Both,
                ClampExtension = 0,
                Child = contentFlow
            };

            InternalChild = sectionScrollContainer;

            rebuildContent();
        }

        protected void rebuildContent()
        {
            if (sectionBody == null)
                return;

            sectionBody.Clear(false);
            sectionBody.Add(createContent());
        }

        protected abstract Drawable createContent();

        protected SettingItem CreateCheckbox(string label, Bindable<bool> bindable, string? description = null)
        {
            var checkbox = new BasicCheckbox
            {
                Current = bindable,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };

            return new SettingItem(label, description, new Container
            {
                Size = new Vector2(24, 24),
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = checkbox
            });
        }

        protected SettingItem CreateEnumDropdown<T>(string label, Bindable<T> bindable, string? description = null, Func<T, string>? formatter = null, bool enableSearch = false) where T : struct, Enum
        {
            if (formatter == null)
            {
                var directDropdown = new SettingsDropdown<T>(dropdown_menu_max_height)
                {
                    Width = 220,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    SearchEnabled = enableSearch
                };

                directDropdown.OverlayLayer = DropdownOverlay;
                directDropdown.ScrollViewport = ScrollViewport;
                directDropdown.Current = bindable;
                directDropdown.Items = Enum.GetValues(typeof(T)).Cast<T>().ToArray();

                return new SettingItem(label, description, directDropdown);
            }

            var items = Enum.GetValues(typeof(T)).Cast<T>().Select(value => new EnumChoice<T>(formatter(value), value)).ToArray();

            var mappedDropdown = new SettingsDropdown<EnumChoice<T>>(dropdown_menu_max_height)
            {
                Width = 220,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Items = items,
                SearchEnabled = enableSearch
            };

            mappedDropdown.OverlayLayer = DropdownOverlay;
            mappedDropdown.ScrollViewport = ScrollViewport;
            mappedDropdown.Current.BindValueChanged(e =>
            {
                if (!EqualityComparer<T>.Default.Equals(bindable.Value, e.NewValue.Value))
                    bindable.Value = e.NewValue.Value;
            });

            bindable.BindValueChanged(e =>
            {
                var target = items.FirstOrDefault(choice => EqualityComparer<T>.Default.Equals(choice.Value, e.NewValue));
                if (!target.Equals(default(EnumChoice<T>)) && !mappedDropdown.Current.Value.Equals(target))
                    mappedDropdown.Current.Value = target;
            }, true);

            return new SettingItem(label, description, mappedDropdown);
        }

        protected SettingItem CreateSlider(string label, Bindable<double> bindable, double min, double max, double precision, string? description = null)
        {
            var sliderBindable = new BindableDouble
            {
                MinValue = min,
                MaxValue = max,
                Precision = precision
            };

            sliderBindable.BindTo(bindable);

            var container = new Container
            {
                Width = 250,
                Height = 24,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Children = new Drawable[]
                {
                    new BasicSliderBar<double>
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 16,
                        Current = sliderBindable,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    }
                }
            };

            return new SettingItem(label, description, container);
        }

        protected sealed partial class SettingsDropdown<T> : BeatSight.Game.UI.Components.Dropdown<T>
        {
            public SettingsDropdown(float menuMaxHeight)
            {
                MenuMaxHeight = menuMaxHeight;
            }
        }

        private readonly struct EnumChoice<T> : IEquatable<EnumChoice<T>> where T : struct, Enum
        {
            public EnumChoice(string label, T value)
            {
                Label = label;
                Value = value;
            }

            public string Label { get; }
            public T Value { get; }
            public override string ToString() => Label;
            public bool Equals(EnumChoice<T> other) => EqualityComparer<T>.Default.Equals(Value, other.Value) && Label == other.Label;
            public override bool Equals(object? obj) => obj is EnumChoice<T> other && Equals(other);
            public override int GetHashCode() => HashCode.Combine(Label, Value);
        }
    }

    public partial class SettingItem : CompositeDrawable
    {
        public SettingItem(string label, string? description, Drawable control)
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;
            InternalChildren = new Drawable[]
            {
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 8,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    }
                },
                new Container
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Padding = new MarginPadding(20),
                    Children = new Drawable[]
                    {
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 6),
                            Children = new Drawable[]
                            {
                                new SpriteText
                                {
                                    Text = label,
                                    Font = new FontUsage(size: 22, weight: "Medium"),
                                    Colour = UITheme.TextPrimary
                                },
                                string.IsNullOrEmpty(description) ? Empty() : new SpriteText
                                {
                                    Text = description,
                                    Font = new FontUsage(size: 16),
                                    Colour = UITheme.TextSecondary
                                }
                            }
                        },
                        control
                    }
                }
            };
        }
    }

    public partial class PlaybackSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;

        public PlaybackSettingsSection(BeatSightConfigManager config, Container dropdownOverlay) : base("Playback Settings", dropdownOverlay)
        {
            this.config = config;
        }

        protected override Drawable createContent()
        {
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
                    CreateSlider(
                        "Background Dim",
                        config.GetBindable<double>(BeatSightSetting.BackgroundDim),
                        0,
                        1,
                        0.01,
                        "How much to dim the background during playback (0% = bright, 100% = dark)."
                    ),
                    CreateSlider(
                        "Background Blur",
                        config.GetBindable<double>(BeatSightSetting.BackgroundBlur),
                        0,
                        1,
                        0.01,
                        "Amount of blur applied to the background during playback."
                    ),
                    CreateEnumDropdown(
                        "Kick Lane Mode",
                        config.GetBindable<KickLaneMode>(BeatSightSetting.KickLaneMode),
                        "Switch between a shared timing line or a dedicated lane for kick hits.",
                        formatKickLaneMode
                    ),
                    createResetSettingsButton()
                }
            };
        }

        private SettingItem createResetSettingsButton()
        {
            var defaultColour = new Color4(176, 70, 70, 255);
            var confirmColour = new Color4(204, 98, 98, 255);

            var resetButton = new BasicButton
            {
                Width = 220,
                Height = 36,
                Text = "Reset All Settings",
                BackgroundColour = defaultColour,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight
            };

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
                Logger.Log("[Settings] User reset configuration to defaults.", LoggingTarget.Runtime, LogLevel.Important);
            };

            var control = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = resetButton
            };

            return new SettingItem(
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

        private static string formatKickLaneMode(KickLaneMode mode) => mode switch
        {
            KickLaneMode.GlobalLine => "Global Line",
            KickLaneMode.DedicatedLane => "Dedicated Line",
            _ => mode.ToString()
        };
    }

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

        public AudioSettingsSection(BeatSightConfigManager config, GameHost host, Container dropdownOverlay) : base("Audio Settings", dropdownOverlay)
        {
            this.config = config;
            this.host = host;
        }

        protected override Drawable createContent()
        {
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
                        "Overall volume control."
                    ),
                    CreateSlider(
                        "Music Volume",
                        config.GetBindable<double>(BeatSightSetting.MusicVolume),
                        0,
                        1,
                        0.01,
                        "Volume for music tracks."
                    ),
                    CreateSlider(
                        "Effect Volume",
                        config.GetBindable<double>(BeatSightSetting.EffectVolume),
                        0,
                        1,
                        0.01,
                        "Volume for hit sounds and effects."
                    ),
                    CreateSlider(
                        "Hitsound Volume",
                        config.GetBindable<double>(BeatSightSetting.HitsoundVolume),
                        0,
                        1,
                        0.01,
                        "Volume for individual note hit feedback sounds."
                    ),
                    CreateSlider(
                        "Metronome Volume",
                        config.GetBindable<double>(BeatSightSetting.MetronomeVolume),
                        0,
                        1.5,
                        0.01,
                        "Adjust the metronome level relative to the music mix, with extra headroom for loud clicks."
                    ),
                    CreateCheckbox(
                        "Metronome",
                        config.GetBindable<bool>(BeatSightSetting.MetronomeEnabled),
                        "Enable or disable the click track during playback and previews."
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
                        "Adjust audio timing in milliseconds if playback is out of sync."
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

            var previewButton = new BasicButton
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

            return new SettingItem(
                "Metronome Sound",
                "Select the tone used for the metronome click. Use the play button to preview it immediately.",
                control);
        }

        private SettingItem createMetronomeAssetSetting()
        {
            var openButton = new BasicButton
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

            return new SettingItem(
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

    public partial class GraphicsSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;
        private readonly GameHost host;
        private Bindable<int>? windowWidth;
        private Bindable<int>? windowHeight;
        private Bindable<bool>? windowFullscreen;
        private Bindable<int>? windowDisplay;
        private Bindable<bool>? frameLimiterEnabled;
        private Bindable<double>? frameLimiterTarget;
        private SettingsDropdown<MonitorChoice>? monitorDropdown;
        private SettingsDropdown<ResolutionOptionChoice>? resolutionDropdown;
        private MonitorChoice[] monitorChoices = Array.Empty<MonitorChoice>();
        private ResolutionOptionChoice[] resolutionChoices = Array.Empty<ResolutionOptionChoice>();
        private BasicSliderBar<double>? frameLimiterSlider;
        private SpriteText? frameLimiterValueText;
        private BindableDouble? frameLimiterSliderBindable;
        private bool frameLimiterValueSync;
        private bool suppressMonitorSync;
        private bool suppressResolutionSync;
        private bool monitorRefreshScheduled;
        private bool resolutionRefreshScheduled;

        public GraphicsSettingsSection(BeatSightConfigManager config, GameHost host, Container dropdownOverlay) : base("Graphics Settings", dropdownOverlay)
        {
            this.config = config;
            this.host = host;
        }

        protected override Drawable createContent()
        {
            windowWidth ??= config.GetBindable<int>(BeatSightSetting.WindowWidth);
            windowHeight ??= config.GetBindable<int>(BeatSightSetting.WindowHeight);
            windowFullscreen ??= config.GetBindable<bool>(BeatSightSetting.WindowFullscreen);
            windowDisplay ??= config.GetBindable<int>(BeatSightSetting.WindowDisplayIndex);
            frameLimiterEnabled ??= config.GetBindable<bool>(BeatSightSetting.FrameLimiterEnabled);
            frameLimiterTarget ??= config.GetBindable<double>(BeatSightSetting.FrameLimiterTarget);

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
                    CreateSlider(
                        "UI Scale",
                        config.GetBindable<double>(BeatSightSetting.UIScale),
                        0.5,
                        1.5,
                        0.01,
                        "Adjust the size of all UI elements (50% - 150%)."
                    ),
                    CreateCheckbox(
                        "Approach Circles",
                        config.GetBindable<bool>(BeatSightSetting.ShowApproachCircles),
                        "Show circles that scale down as notes approach."
                    ),
                    CreateCheckbox(
                        "Particle Effects",
                        config.GetBindable<bool>(BeatSightSetting.ShowParticleEffects),
                        "Show burst animations when hitting notes."
                    ),
                    CreateCheckbox(
                        "Glow Effects",
                        config.GetBindable<bool>(BeatSightSetting.ShowGlowEffects),
                        "Show glowing effects with additive blending."
                    ),
                    CreateCheckbox(
                        "Hit Burst Animations",
                        config.GetBindable<bool>(BeatSightSetting.ShowHitBurstAnimations),
                        "Show explosion animations on perfect/great hits."
                    )
                }
            };
        }

        private SettingItem createSkinManagementSetting()
        {
            var openButton = new BasicButton
            {
                Width = 160,
                Height = 32,
                Text = "Open Skins Folder",
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Action = () => SettingsScreen.OpenDirectoryExternally(host, UserAssetDirectories.Skins)
            };

            var editorButton = new BasicButton
            {
                Width = 160,
                Height = 32,
                Text = "Skin Editor (Soon)"
            };
            editorButton.Anchor = Anchor.CentreLeft;
            editorButton.Origin = Anchor.CentreLeft;
            editorButton.Enabled.Value = false;

            var control = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Children = new Drawable[] { openButton, editorButton }
            };

            return new SettingItem(
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

            return new SettingItem(
                "Monitor",
                "Choose which display BeatSight launches on.",
                monitorDropdown);
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

            return new SettingItem(
                "Resolution",
                "Choose the render resolution. Fullscreen selects the display mode; windowed uses it for the window size.",
                resolutionDropdown);
        }

        private SettingItem createFrameLimiterSetting()
        {
            frameLimiterSliderBindable = new BindableDouble
            {
                MinValue = 60,
                MaxValue = computeFrameLimiterCeiling(),
                Precision = 1
            };

            if (frameLimiterTarget != null)
            {
                frameLimiterSliderBindable.Value = Math.Clamp(
                    frameLimiterTarget.Value,
                    frameLimiterSliderBindable.MinValue,
                    frameLimiterSliderBindable.MaxValue);
            }
            else
            {
                frameLimiterSliderBindable.Value = frameLimiterSliderBindable.MinValue;
            }

            frameLimiterSlider = new BasicSliderBar<double>
            {
                RelativeSizeAxes = Axes.X,
                Height = 16,
                Current = frameLimiterSliderBindable
            };

            frameLimiterValueText = new SpriteText
            {
                Font = new FontUsage(size: 16),
                Colour = UITheme.TextSecondary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            frameLimiterSliderBindable.BindValueChanged(e =>
            {
                frameLimiterValueText.Text = $"{Math.Round(e.NewValue)} Hz";

                if (frameLimiterTarget == null)
                    return;

                if (frameLimiterValueSync)
                    return;

                frameLimiterValueSync = true;
                try
                {
                    frameLimiterTarget.Value = e.NewValue;
                }
                finally
                {
                    frameLimiterValueSync = false;
                }
            }, true);

            if (frameLimiterTarget != null)
            {
                frameLimiterTarget.BindValueChanged(e =>
                {
                    if (frameLimiterSliderBindable == null)
                        return;

                    if (frameLimiterValueSync)
                        return;

                    frameLimiterValueSync = true;
                    try
                    {
                        frameLimiterSliderBindable.Value = e.NewValue;
                    }
                    finally
                    {
                        frameLimiterValueSync = false;
                    }
                }, true);
            }

            if (frameLimiterEnabled != null)
            {
                bool enabledNow = frameLimiterEnabled.Value;
                frameLimiterSliderBindable.Disabled = !enabledNow;
                frameLimiterSlider.Alpha = enabledNow ? 1f : 0.5f;

                frameLimiterEnabled.BindValueChanged(e =>
                {
                    bool enabled = e.NewValue;
                    frameLimiterSliderBindable.Disabled = !enabled;
                    frameLimiterSlider.FadeTo(enabled ? 1f : 0.5f, 200, Easing.OutQuint);
                    frameLimiterValueText?.FadeColour(enabled ? UITheme.TextSecondary : UITheme.TextMuted, 200, Easing.OutQuint);
                }, true);
            }

            updateFrameLimiterSliderRange();

            var checkbox = new BasicCheckbox
            {
                Current = frameLimiterEnabled!,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };

            var control = new FillFlowContainer
            {
                Width = 320,
                AutoSizeAxes = Axes.Y,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(12, 0),
                        Children = new Drawable[]
                        {
                            new Container
                            {
                                Size = new Vector2(24),
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Child = checkbox
                            },
                            frameLimiterValueText
                        }
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 20,
                        Child = frameLimiterSlider
                    }
                }
            };

            return new SettingItem(
                "Frame Limiter",
                "Throttle BeatSight's rendering speed to save power or match your monitor.",
                control);
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (host.Window != null)
                host.Window.DisplaysChanged += onDisplaysChanged;

            updateMonitorDropdownItems();
            updateResolutionDropdownItems();
            updateFrameLimiterSliderRange();
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
            updateFrameLimiterSliderRange();
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

            updateFrameLimiterSliderRange();
        }

        private void updateFrameLimiterSliderRange()
        {
            if (frameLimiterSliderBindable == null)
                return;

            double ceiling = Math.Max(60, computeFrameLimiterCeiling());
            frameLimiterSliderBindable.MinValue = 60;
            frameLimiterSliderBindable.MaxValue = ceiling;

            if (frameLimiterTarget != null && frameLimiterTarget.Value > ceiling)
                frameLimiterTarget.Value = ceiling;

            if (frameLimiterSliderBindable.Value > ceiling)
                frameLimiterSliderBindable.Value = ceiling;

            if (frameLimiterSliderBindable.Value < frameLimiterSliderBindable.MinValue)
                frameLimiterSliderBindable.Value = frameLimiterSliderBindable.MinValue;
        }

        private double computeFrameLimiterCeiling()
        {
            var display = getDisplayByIndex(windowDisplay?.Value ?? 0);

            if (display is Display displayValue)
            {
                double maxRefresh = 0;
                foreach (var mode in displayValue.DisplayModes)
                    maxRefresh = Math.Max(maxRefresh, mode.RefreshRate);

                if (maxRefresh >= 30)
                    return Math.Clamp(maxRefresh, 60, 1000);
            }

            return 240;
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
