using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics.Effects;

namespace BeatSight.Game.UI.Settings
{
    /// <summary>
    /// Base container for settings panels with consistent styling.
    /// </summary>
    public partial class SettingsPanel : CompositeDrawable
    {
        protected FillFlowContainer ContentFlow { get; private set; } = null!;
        private readonly string title;

        // BeatSight color palette
        protected static readonly Color4 BackgroundColor = new Color4(15, 23, 42, 255); // slate-900
        protected static readonly Color4 SurfaceColor = new Color4(30, 41, 59, 255); // slate-800
        protected static readonly Color4 BorderColor = new Color4(51, 65, 85, 200); // slate-700
        protected static readonly Color4 TextPrimary = Color4.White;
        protected static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255); // slate-400
        protected static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255); // cyan-500
        protected static readonly Color4 PurpleAccent = new Color4(168, 85, 247, 255); // purple-500

        public SettingsPanel(string title = "Settings")
        {
            this.title = title;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChild = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding(20),
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 16,
                    BorderColour = BorderColor,
                    BorderThickness = 1,
                    Children = new Drawable[]
                    {
                        // Background
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = SurfaceColor,
                        },
                        // Content
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Children = new Drawable[]
                            {
                                // Header
                                new Container
                                {
                                    RelativeSizeAxes = Axes.X,
                                    Height = 60,
                                    Padding = new MarginPadding { Horizontal = 24 },
                                    Children = new Drawable[]
                                    {
                                        new Box
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Colour = BackgroundColor.Opacity(0.5f),
                                        },
                                        new SpriteText
                                        {
                                            Anchor = Anchor.CentreLeft,
                                            Origin = Anchor.CentreLeft,
                                            Text = title,
                                            Font = new FontUsage("Inter", 24, "Bold"),
                                            Colour = TextPrimary,
                                        },
                                    },
                                },
                                // Divider
                                new Box
                                {
                                    RelativeSizeAxes = Axes.X,
                                    Height = 1,
                                    Colour = BorderColor,
                                },
                                // Scroll container for content
                                new BasicScrollContainer
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Padding = new MarginPadding(24),
                                    Child = ContentFlow = new FillFlowContainer
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        AutoSizeAxes = Axes.Y,
                                        Direction = FillDirection.Vertical,
                                        Spacing = new Vector2(0, 16),
                                    },
                                },
                            },
                        },
                    },
                },
            };
        }

        /// <summary>
        /// Adds a settings section with a title.
        /// </summary>
        protected void AddSection(string sectionTitle, params Drawable[] items)
        {
            ContentFlow.Add(new SettingsSection(sectionTitle, items));
        }
    }

    /// <summary>
    /// A collapsible settings section with title and items.
    /// </summary>
    public partial class SettingsSection : CompositeDrawable
    {
        private readonly string title;
        private readonly Drawable[] items;
        private FillFlowContainer itemsContainer = null!;
        private bool isExpanded = true;

        public SettingsSection(string title, params Drawable[] items)
        {
            this.title = title;
            this.items = items;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;

            InternalChild = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 12),
                Children = new Drawable[]
                {
                    // Section Header
                    new SettingsSectionHeader(title)
                    {
                        Action = () =>
                        {
                            isExpanded = !isExpanded;
                            itemsContainer.FadeTo(isExpanded ? 1 : 0, 200, Easing.OutQuint);
                            itemsContainer.MoveToY(isExpanded ? 0 : -10, 200, Easing.OutQuint);
                        },
                    },
                    // Items Container
                    itemsContainer = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 8),
                        ChildrenEnumerable = items,
                    },
                },
            };
        }
    }

    /// <summary>
    /// Clickable section header with expand/collapse indicator.
    /// </summary>
    public partial class SettingsSectionHeader : CompositeDrawable
    {
        public System.Action? Action { get; set; }
        private readonly string title;
        private Box hoverBackground = null!;
        private SpriteIcon expandIcon = null!;
        private bool isExpanded = true;

        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);

        public SettingsSectionHeader(string title)
        {
            this.title = title;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            Height = 32;

            InternalChildren = new Drawable[]
            {
                hoverBackground = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.White.Opacity(0.05f),
                    Alpha = 0,
                },
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Horizontal = 8 },
                    Children = new Drawable[]
                    {
                        new SpriteText
                        {
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            Text = title.ToUpperInvariant(),
                            Font = new FontUsage("Inter", 12, "SemiBold"),
                            Colour = TextSecondary,
                        },
                        expandIcon = new SpriteIcon
                        {
                            Anchor = Anchor.CentreRight,
                            Origin = Anchor.CentreRight,
                            Size = new Vector2(12),
                            Icon = FontAwesome.Solid.ChevronDown,
                            Colour = TextSecondary,
                        },
                    },
                },
            };
        }

        protected override bool OnHover(HoverEvent e)
        {
            hoverBackground.FadeIn(100);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            hoverBackground.FadeOut(100);
            base.OnHoverLost(e);
        }

        protected override bool OnClick(ClickEvent e)
        {
            isExpanded = !isExpanded;
            expandIcon.RotateTo(isExpanded ? 0 : -90, 200, Easing.OutQuint);
            Action?.Invoke();
            return true;
        }
    }

    /// <summary>
    /// A basic toggle switch setting item.
    /// </summary>
    public partial class SettingsToggle : CompositeDrawable
    {
        private readonly string label;
        private readonly string? description;
        private bool isEnabled;
        private Container toggle = null!;
        private Container toggleKnob = null!;

        public System.Action<bool>? OnToggled { get; set; }

        private static readonly Color4 TextPrimary = Color4.White;
        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);
        private static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255);
        private static readonly Color4 SurfaceColor = new Color4(30, 41, 59, 255);
        private static readonly Color4 ToggleOffColor = new Color4(51, 65, 85, 255);

        public SettingsToggle(string label, bool defaultValue = false, string? description = null)
        {
            this.label = label;
            this.description = description;
            this.isEnabled = defaultValue;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;
            Padding = new MarginPadding { Horizontal = 8, Vertical = 8 };

            InternalChildren = new Drawable[]
            {
                new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Horizontal,
                    Children = new Drawable[]
                    {
                        // Label and description
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.None,
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 2),
                            Children = new Drawable[]
                            {
                                new SpriteText
                                {
                                    Text = label,
                                    Font = new FontUsage("Inter", 14),
                                    Colour = TextPrimary,
                                },
                                description != null
                                    ? new SpriteText
                                    {
                                        Text = description,
                                        Font = new FontUsage("Inter", 12),
                                        Colour = TextSecondary,
                                    }
                                    : Empty(),
                            },
                        },
                    },
                },
                // Toggle switch (positioned right)
                toggle = new Container
                {
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Size = new Vector2(44, 24),
                    Masking = true,
                    CornerRadius = 12,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = isEnabled ? CyanAccent : ToggleOffColor,
                        },
                        toggleKnob = new Container
                        {
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            Size = new Vector2(20),
                            X = isEnabled ? 22 : 2,
                            Masking = true,
                            CornerRadius = 10,
                            Child = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = Color4.White,
                            },
                        },
                    },
                },
            };
        }

        protected override bool OnClick(ClickEvent e)
        {
            Toggle();
            return true;
        }

        public void Toggle()
        {
            isEnabled = !isEnabled;
            toggleKnob.MoveToX(isEnabled ? 22 : 2, 200, Easing.OutQuint);
            toggle.Child.FadeColour(isEnabled ? CyanAccent : ToggleOffColor, 200);
            OnToggled?.Invoke(isEnabled);
        }
    }

    /// <summary>
    /// A slider setting for numeric values.
    /// </summary>
    public partial class SettingsSlider : CompositeDrawable
    {
        private readonly string label;
        private readonly float minValue;
        private readonly float maxValue;
        private float currentValue;
        private Container sliderFill = null!;
        private SpriteText valueText = null!;

        public System.Action<float>? OnValueChanged { get; set; }

        private static readonly Color4 TextPrimary = Color4.White;
        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);
        private static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255);
        private static readonly Color4 SliderTrackColor = new Color4(51, 65, 85, 255);

        public SettingsSlider(string label, float min = 0, float max = 100, float defaultValue = 50)
        {
            this.label = label;
            this.minValue = min;
            this.maxValue = max;
            this.currentValue = defaultValue;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            Height = 60;
            Padding = new MarginPadding { Horizontal = 8 };

            InternalChildren = new Drawable[]
            {
                new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 8),
                    Children = new Drawable[]
                    {
                        // Label row
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 20,
                            Children = new Drawable[]
                            {
                                new SpriteText
                                {
                                    Anchor = Anchor.CentreLeft,
                                    Origin = Anchor.CentreLeft,
                                    Text = label,
                                    Font = new FontUsage("Inter", 14),
                                    Colour = TextPrimary,
                                },
                                valueText = new SpriteText
                                {
                                    Anchor = Anchor.CentreRight,
                                    Origin = Anchor.CentreRight,
                                    Text = currentValue.ToString("0"),
                                    Font = new FontUsage("Inter", 14, "SemiBold"),
                                    Colour = CyanAccent,
                                },
                            },
                        },
                        // Slider track
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 8,
                            Masking = true,
                            CornerRadius = 4,
                            Children = new Drawable[]
                            {
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = SliderTrackColor,
                                },
                                sliderFill = new Container
                                {
                                    RelativeSizeAxes = Axes.Y,
                                    Width = GetFillWidth(),
                                    Masking = true,
                                    CornerRadius = 4,
                                    Child = new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = CyanAccent,
                                    },
                                },
                            },
                        },
                    },
                },
            };
        }

        private float GetFillWidth()
        {
            return ((currentValue - minValue) / (maxValue - minValue)) * DrawWidth;
        }

        protected override bool OnDragStart(DragStartEvent e) => true;

        protected override void OnDrag(DragEvent e)
        {
            UpdateValue(e.MousePosition.X);
        }

        protected override bool OnClick(ClickEvent e)
        {
            UpdateValue(e.MousePosition.X);
            return true;
        }

        private void UpdateValue(float mouseX)
        {
            float percentage = System.Math.Clamp(mouseX / DrawWidth, 0, 1);
            currentValue = minValue + (percentage * (maxValue - minValue));

            sliderFill.ResizeWidthTo(GetFillWidth(), 50, Easing.OutQuint);
            valueText.Text = currentValue.ToString("0");
            OnValueChanged?.Invoke(currentValue);
        }
    }

    /// <summary>
    /// A dropdown selection setting.
    /// </summary>
    public partial class SettingsDropdown : CompositeDrawable
    {
        private readonly string label;
        private readonly string[] options;
        private int selectedIndex;
        private SpriteText selectedText = null!;
        public System.Action<int, string>? OnSelectionChanged { get; set; }

        private static readonly Color4 TextPrimary = Color4.White;
        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);
        private static readonly Color4 SurfaceColor = new Color4(30, 41, 59, 255);
        private static readonly Color4 BorderColor = new Color4(51, 65, 85, 200);

        public SettingsDropdown(string label, string[] options, int defaultIndex = 0)
        {
            this.label = label;
            this.options = options;
            this.selectedIndex = defaultIndex;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;
            Padding = new MarginPadding { Horizontal = 8, Vertical = 8 };

            InternalChildren = new Drawable[]
            {
                new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 8),
                    Children = new Drawable[]
                    {
                        new SpriteText
                        {
                            Text = label,
                            Font = new FontUsage("Inter", 14),
                            Colour = TextPrimary,
                        },
                        // Dropdown button
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 40,
                            Masking = true,
                            CornerRadius = 8,
                            BorderColour = BorderColor,
                            BorderThickness = 1,
                            Children = new Drawable[]
                            {
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = SurfaceColor,
                                },
                                new Container
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Padding = new MarginPadding { Horizontal = 12 },
                                    Children = new Drawable[]
                                    {
                                        selectedText = new SpriteText
                                        {
                                            Anchor = Anchor.CentreLeft,
                                            Origin = Anchor.CentreLeft,
                                            Text = options[selectedIndex],
                                            Font = new FontUsage("Inter", 14),
                                            Colour = TextPrimary,
                                        },
                                        new SpriteIcon
                                        {
                                            Anchor = Anchor.CentreRight,
                                            Origin = Anchor.CentreRight,
                                            Size = new Vector2(12),
                                            Icon = FontAwesome.Solid.ChevronDown,
                                            Colour = TextSecondary,
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            };
        }

        protected override bool OnClick(ClickEvent e)
        {
            // Cycle through options for simplicity
            selectedIndex = (selectedIndex + 1) % options.Length;
            selectedText.Text = options[selectedIndex];
            OnSelectionChanged?.Invoke(selectedIndex, options[selectedIndex]);
            return true;
        }
    }

    /// <summary>
    /// Audio settings panel with volume controls.
    /// </summary>
    public partial class AudioSettingsPanel : SettingsPanel
    {
        public AudioSettingsPanel() : base("Audio Settings")
        {
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            AddSection("Volume",
                new SettingsSlider("Master Volume", 0, 100, 80),
                new SettingsSlider("Music Volume", 0, 100, 100),
                new SettingsSlider("Sound Effects", 0, 100, 70),
                new SettingsSlider("Metronome Volume", 0, 100, 50)
            );

            AddSection("Playback",
                new SettingsDropdown("Audio Output", new[] { "System Default", "Speakers", "Headphones" }),
                new SettingsSlider("Audio Offset (ms)", -100, 100, 0),
                new SettingsToggle("Enable Audio Normalization", true)
            );

            AddSection("Effects",
                new SettingsToggle("Enable Hit Sounds", true),
                new SettingsToggle("Enable Reverb", false),
                new SettingsDropdown("Hit Sound Pack", new[] { "Default", "Soft", "Drums", "Electronic" })
            );
        }
    }

    /// <summary>
    /// Display settings panel with graphics options.
    /// </summary>
    public partial class DisplaySettingsPanel : SettingsPanel
    {
        public DisplaySettingsPanel() : base("Display Settings")
        {
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            AddSection("Window",
                new SettingsDropdown("Display Mode", new[] { "Windowed", "Borderless", "Fullscreen" }),
                new SettingsDropdown("Resolution", new[] { "1920x1080", "2560x1440", "3840x2160" }),
                new SettingsToggle("VSync", true)
            );

            AddSection("Graphics",
                new SettingsSlider("Frame Rate Limit", 30, 240, 144),
                new SettingsDropdown("Quality Preset", new[] { "Low", "Medium", "High", "Ultra" }),
                new SettingsToggle("Enable Bloom Effects", true),
                new SettingsToggle("Enable Particles", true)
            );

            AddSection("Interface",
                new SettingsSlider("UI Scale", 80, 120, 100),
                new SettingsToggle("Show FPS Counter", false),
                new SettingsToggle("Reduce Motion", false)
            );
        }
    }

    /// <summary>
    /// Gameplay settings panel.
    /// </summary>
    public partial class GameplaySettingsPanel : SettingsPanel
    {
        public GameplaySettingsPanel() : base("Gameplay Settings")
        {
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            AddSection("Difficulty",
                new SettingsDropdown("Difficulty Level", new[] { "Easy", "Normal", "Hard", "Expert" }),
                new SettingsToggle("Auto-adjust Difficulty", true),
                new SettingsSlider("Note Speed", 1, 10, 5)
            );

            AddSection("Timing",
                new SettingsSlider("Visual Offset (ms)", -100, 100, 0),
                new SettingsSlider("Hit Window", 50, 150, 100),
                new SettingsToggle("Show Timing Feedback", true)
            );

            AddSection("Assistance",
                new SettingsToggle("Show Note Guides", true),
                new SettingsToggle("Enable Countdown", true),
                new SettingsDropdown("Practice Mode", new[] { "Normal", "Slow Motion", "Loop Section" })
            );
        }
    }
}
