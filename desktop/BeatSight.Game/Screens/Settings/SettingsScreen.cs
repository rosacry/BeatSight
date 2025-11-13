using System;
using System.Globalization;
using System.IO;
using BeatSight.Game.Calibration;
using BeatSight.Game.Configuration;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
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

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager configManager, GameHost gameHost)
        {
            config = configManager;
            host = gameHost;

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(15, 15, 22, 255)
                },
                new GridContainer
                {
                    RelativeSizeAxes = Axes.Both,
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
                                            Padding = new MarginPadding(30)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            };

            // Show gameplay settings by default
            showSection(new GameplaySettingsSection(config));
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
                        Colour = new Color4(20, 20, 30, 255)
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 30 },
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "⚙ Settings",
                                Font = new FontUsage(size: 32, weight: "Bold"),
                                Colour = Color4.White,
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft
                            },
                            new SpriteText
                            {
                                Text = "Esc — back to menu",
                                Font = new FontUsage(size: 18),
                                Colour = new Color4(180, 185, 200, 255),
                                Anchor = Anchor.CentreRight,
                                Origin = Anchor.CentreRight
                            }
                        }
                    }
                }
            };
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
                        Colour = new Color4(18, 18, 26, 255)
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
                                new SettingsButton("🎮 Gameplay", () => showSection(new GameplaySettingsSection(config))),
                                new SettingsButton("👁 Visual Effects", () => showSection(new VisualSettingsSection(config))),
                                new SettingsButton("🔊 Audio", () => showSection(new AudioSettingsSection(config, host))),
                                new SettingsButton("⌨ Input", () => showSection(new InputSettingsSection(config))),
                                new SettingsButton("⚡ Performance", () => showSection(new PerformanceSettingsSection(config)))
                            }
                        }
                    }
                }
            };
        }

        private void showSection(SettingsSection section)
        {
            currentSection?.Expire();
            currentSection = section;
            contentContainer.Child = currentSection;
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
            private readonly Action action;

            public SettingsButton(string text, Action action)
            {
                this.action = action;

                RelativeSizeAxes = Axes.X;
                Height = 50;
                Masking = true;
                CornerRadius = 8;

                InternalChildren = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(30, 30, 42, 255)
                    },
                    new SpriteText
                    {
                        Text = text,
                        Font = new FontUsage(size: 20),
                        Colour = Color4.White,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Padding = new MarginPadding { Left = 16 }
                    }
                };
            }

            protected override bool OnClick(ClickEvent e)
            {
                action?.Invoke();
                background.FlashColour(new Color4(60, 60, 82, 255), 100);
                return true;
            }

            protected override bool OnHover(HoverEvent e)
            {
                background.FadeColour(new Color4(45, 45, 62, 255), 200, Easing.OutQuint);
                this.ScaleTo(1.02f, 200, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                base.OnHoverLost(e);
                background.FadeColour(new Color4(30, 30, 42, 255), 200, Easing.OutQuint);
                this.ScaleTo(1f, 200, Easing.OutQuint);
            }
        }
    }

    public abstract partial class SettingsSection : CompositeDrawable
    {
        private readonly string title;
        private FillFlowContainer contentFlow = null!;
        private FillFlowContainer sectionBody = null!;

        protected SettingsSection(string title)
        {
            this.title = title;
            RelativeSizeAxes = Axes.Both;
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
                    Colour = Color4.White,
                    Margin = new MarginPadding { Bottom = 10 }
                },
                sectionBody
            });

            InternalChild = new BasicScrollContainer
            {
                RelativeSizeAxes = Axes.Both,
                ClampExtension = 0,
                Child = contentFlow
            };

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

        protected SettingItem CreateEnumDropdown<T>(string label, Bindable<T> bindable, string? description = null) where T : struct, Enum
        {
            return new SettingItem(label, description, new BasicDropdown<T>
            {
                Width = 200,
                Current = bindable,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight
            });
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
    }

    public partial class SettingItem : CompositeDrawable
    {
        public SettingItem(string label, string? description, Drawable control)
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;
            Masking = true;
            CornerRadius = 8;

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(25, 25, 36, 255)
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
                                    Colour = Color4.White
                                },
                                string.IsNullOrEmpty(description) ? Empty() : new SpriteText
                                {
                                    Text = description,
                                    Font = new FontUsage(size: 16),
                                    Colour = new Color4(160, 165, 180, 255)
                                }
                            }
                        },
                        control
                    }
                }
            };
        }
    }

    public partial class GameplaySettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;

        public GameplaySettingsSection(BeatSightConfigManager config) : base("Gameplay Settings")
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
                        "Gameplay Mode",
                        config.GetBindable<GameplayMode>(BeatSightSetting.GameplayMode),
                        "Auto: Scoring and detection enabled. Manual: Play-along mode without scoring."
                    ),
                    CreateEnumDropdown(
                        "Lane View",
                        config.GetBindable<LaneViewMode>(BeatSightSetting.LaneViewMode),
                        "Switch between classic 2D lanes and the new 3D runway view."
                    ),
                    CreateEnumDropdown(
                        "Lane Preset",
                        config.GetBindable<LanePreset>(BeatSightSetting.LanePreset),
                        "Select how many drum lanes to render and how instruments are arranged."
                    ),
                    CreateSlider(
                        "Background Dim",
                        config.GetBindable<double>(BeatSightSetting.BackgroundDim),
                        0,
                        1,
                        0.01,
                        "How much to dim the background during gameplay (0% = bright, 100% = dark)."
                    ),
                    CreateSlider(
                        "Background Blur",
                        config.GetBindable<double>(BeatSightSetting.BackgroundBlur),
                        0,
                        1,
                        0.01,
                        "Amount of blur applied to the background during gameplay."
                    ),
                    CreateCheckbox(
                        "Hit Lighting",
                        config.GetBindable<bool>(BeatSightSetting.HitLighting),
                        "Screen flash effects when hitting notes perfectly."
                    ),
                    CreateCheckbox(
                        "Show Hit Error Meter",
                        config.GetBindable<bool>(BeatSightSetting.ShowHitErrorMeter),
                        "Display timing accuracy visualization bar."
                    ),
                    CreateCheckbox(
                        "Screen Shake on Miss",
                        config.GetBindable<bool>(BeatSightSetting.ScreenShakeOnMiss),
                        "Shake the screen slightly when missing notes."
                    ),
                    CreateCheckbox(
                        "Show Combo Milestones",
                        config.GetBindable<bool>(BeatSightSetting.ShowComboMilestones),
                        "Celebration animations at every 50 combo."
                    )
                }
            };
        }
    }

    public partial class VisualSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;

        public VisualSettingsSection(BeatSightConfigManager config) : base("Visual Effects")
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
                    ),
                    CreateEnumDropdown(
                        "Note Skin",
                        config.GetBindable<NoteSkinOption>(BeatSightSetting.NoteSkin),
                        "Switch the appearance of notes between available skins."
                    ),
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
                    )
                }
            };
        }
    }

    public partial class AudioSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;
        private readonly GameHost host;
        private readonly MicCalibrationManager calibrationManager;
        private Bindable<bool> calibrationCompleted = null!;
        private Bindable<string> calibrationLastUpdated = null!;
        private Bindable<string> calibrationProfilePath = null!;
        private Bindable<string> calibrationDeviceId = null!;
        private SpriteText calibrationStatusText = null!;
        private SpriteText calibrationUpdatedText = null!;
        private SpriteText calibrationPathText = null!;
        private SpriteText calibrationDeviceText = null!;
        private SpriteText calibrationHintText = null!;
        private BasicButton clearCalibrationButton = null!;

        public AudioSettingsSection(BeatSightConfigManager config, GameHost host) : base("Audio Settings")
        {
            this.config = config;
            this.host = host;
            calibrationManager = new MicCalibrationManager(host.Storage);
        }

        protected override Drawable createContent()
        {
            calibrationCompleted = config.GetBindable<bool>(BeatSightSetting.MicCalibrationCompleted);
            calibrationLastUpdated = config.GetBindable<string>(BeatSightSetting.MicCalibrationLastUpdated);
            calibrationProfilePath = config.GetBindable<string>(BeatSightSetting.MicCalibrationProfilePath);
            calibrationDeviceId = config.GetBindable<string>(BeatSightSetting.MicCalibrationDeviceId);

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
                    CreateCheckbox(
                        "Metronome Enabled",
                        config.GetBindable<bool>(BeatSightSetting.MetronomeEnabled),
                        "Enable the click track during playback and previews."
                    ),
                    CreateSlider(
                        "Metronome Volume",
                        config.GetBindable<double>(BeatSightSetting.MetronomeVolume),
                        0,
                        1,
                        0.01,
                        "Adjust the metronome level relative to the music mix."
                    ),
                    CreateEnumDropdown(
                        "Metronome Sound",
                        config.GetBindable<MetronomeSoundOption>(BeatSightSetting.MetronomeSound),
                        "Select the tone used for the metronome click."
                    ),
                    CreateCheckbox(
                        "Prefer Drum Stem Playback",
                        config.GetBindable<bool>(BeatSightSetting.DrumStemPlaybackOnly),
                        "When available, switch playback to the isolated drum stem instead of the full mix."
                    ),
                    CreateCalibrationSetting()
                }
            };
        }

        private SettingItem CreateCalibrationSetting()
        {
            calibrationStatusText = new SpriteText
            {
                Font = new FontUsage(size: 18, weight: "Medium"),
                Colour = Color4.White,
                Text = "Status: Unknown"
            };

            calibrationUpdatedText = new SpriteText
            {
                Font = new FontUsage(size: 14),
                Colour = new Color4(180, 185, 200, 255),
                Text = "Last updated: --"
            };

            calibrationPathText = new SpriteText
            {
                Font = new FontUsage(size: 14),
                Colour = new Color4(150, 155, 170, 255),
                Text = "Profile path: --"
            };

            calibrationDeviceText = new SpriteText
            {
                Font = new FontUsage(size: 14),
                Colour = new Color4(150, 155, 170, 255),
                Text = "Captured device: --"
            };

            calibrationHintText = new SpriteText
            {
                Font = new FontUsage(size: 14),
                Colour = new Color4(160, 165, 180, 255),
                Text = "Launch Live Input to (re)calibrate your kit."
            };

            clearCalibrationButton = new BasicButton
            {
                Text = "Clear Calibration",
                Width = 170,
                Height = 32,
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
            };

            clearCalibrationButton.Action = clearCalibration;

            var control = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 4),
                    Children = new Drawable[]
                    {
                        calibrationStatusText,
                        calibrationUpdatedText,
                        calibrationPathText,
                        calibrationDeviceText,
                        calibrationHintText,
                        new Container
                        {
                            AutoSizeAxes = Axes.Both,
                            Child = clearCalibrationButton
                        }
                    }
                }
            };

            calibrationCompleted.BindValueChanged(_ => updateCalibrationDisplay(), true);
            calibrationLastUpdated.BindValueChanged(_ => updateCalibrationDisplay(), true);
            calibrationProfilePath.BindValueChanged(_ => updateCalibrationDisplay(), true);
            calibrationDeviceId.BindValueChanged(_ => updateCalibrationDisplay(), true);

            return new SettingItem(
                "Microphone Calibration",
                "BeatSight uses this profile for Live Input scoring. Clear to force a fresh capture.",
                control
            );
        }

        private void clearCalibration()
        {
            calibrationManager.Clear();
            calibrationCompleted.Value = false;
            calibrationLastUpdated.Value = string.Empty;
            calibrationProfilePath.Value = string.Empty;
            calibrationDeviceId.Value = string.Empty;
            updateCalibrationDisplay();
            calibrationHintText.Text = "Calibration cleared. Launch Live Input to capture a new profile.";
        }

        private void updateCalibrationDisplay()
        {
            bool hasProfile = calibrationCompleted.Value && !string.IsNullOrWhiteSpace(calibrationProfilePath.Value) && calibrationManager.HasProfile();

            if (!hasProfile)
            {
                calibrationStatusText.Text = "Status: Not calibrated";
                calibrationStatusText.Colour = new Color4(255, 190, 120, 255);
                calibrationUpdatedText.Text = "Last updated: never";
                calibrationPathText.Text = "Profile path: (none)";
                calibrationDeviceText.Text = "Captured device: (none)";
                calibrationHintText.Text = "Launch Live Input from the main menu to run calibration.";
                setButtonState(enabled: false, "Clear Calibration");
                return;
            }

            calibrationStatusText.Text = "Status: Complete";
            calibrationStatusText.Colour = new Color4(120, 255, 140, 255);

            calibrationUpdatedText.Text = $"Last updated: {formatTimestamp(calibrationLastUpdated.Value)}";
            calibrationPathText.Text = formatProfilePath(calibrationProfilePath.Value);
            calibrationDeviceText.Text = formatDeviceName(calibrationDeviceId.Value);
            calibrationHintText.Text = "Need adjustments? Clear the profile or recalibrate in Live Input.";
            setButtonState(enabled: true, "Clear Calibration");
        }

        private void setButtonState(bool enabled, string label)
        {
            clearCalibrationButton.Text = label;
            clearCalibrationButton.Enabled.Value = enabled;
            clearCalibrationButton.Alpha = enabled ? 1f : 0.35f;
        }

        private static string formatProfilePath(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
                return "Profile path: (none)";

            string display = path;
            try
            {
                display = Path.GetFileName(path);
            }
            catch
            {
                // Keep fallback display.
            }

            return $"Profile path: {display}";
        }

        private static string formatDeviceName(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "Captured device: (unknown)";

            return $"Captured device: {value}";
        }

        private static string formatTimestamp(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "never";

            if (!DateTime.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var parsed))
            {
                if (!DateTime.TryParse(value, out parsed))
                    return value;
            }

            try
            {
                var local = parsed.Kind == DateTimeKind.Unspecified ? DateTime.SpecifyKind(parsed, DateTimeKind.Utc).ToLocalTime() : parsed.ToLocalTime();
                return local.ToString("MMM d, yyyy • HH:mm", CultureInfo.CurrentCulture);
            }
            catch
            {
                return parsed.ToString(CultureInfo.CurrentCulture);
            }
        }
    }

    public partial class InputSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;

        public InputSettingsSection(BeatSightConfigManager config) : base("Input Settings")
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
                    CreateSlider(
                        "Audio Offset",
                        config.GetBindable<double>(BeatSightSetting.AudioOffset),
                        -150,
                        150,
                        1,
                        "Adjust timing offset for audio synchronization (in milliseconds)."
                    ),
                    CreateSlider(
                        "Hitsound Offset",
                        config.GetBindable<double>(BeatSightSetting.HitsoundOffset),
                        -150,
                        150,
                        1,
                        "Separate offset for hitsound playback timing (in milliseconds)."
                    ),
                    new SettingItem(
                        "Key Bindings",
                        "Configure drum component key mappings.",
                        new SpriteText
                        {
                            Text = "Coming Soon",
                            Font = new FontUsage(size: 18),
                            Colour = new Color4(150, 150, 170, 255),
                            Anchor = Anchor.CentreRight,
                            Origin = Anchor.CentreRight
                        }
                    )
                }
            };
        }
    }

    public partial class PerformanceSettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;

        public PerformanceSettingsSection(BeatSightConfigManager config) : base("Performance Settings")
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
                        "Frame Limiter",
                        config.GetBindable<FrameLimiterMode>(BeatSightSetting.FrameLimiter),
                        "Limit maximum framerate to reduce system load or enable VSync."
                    ),
                    new SettingItem(
                        "Rendering Info",
                        "Current renderer and performance statistics.",
                        new SpriteText
                        {
                            Text = "See FPS Counter in Visual settings",
                            Font = new FontUsage(size: 16),
                            Colour = new Color4(150, 150, 170, 255),
                            Anchor = Anchor.CentreRight,
                            Origin = Anchor.CentreRight
                        }
                    )
                }
            };
        }
    }
}
